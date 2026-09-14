import json
import sqlite3

import pytest

from orchestration.history import History
from orchestration.revisions import apply_patch_response, digest, file_diff
from orchestration.schemas import GeneratedFile
from orchestration.web import Jobs
from orchestration.state import ProjectPhase
from tests.test_history import record
from tests.test_web import wait_until


def completed(ident='v1', **changes):
    result = record(ident, requirements=[], phase='gate_2_approved', gate_2_approved=True,
                    build_passed=True, generated_files=[dict(path='app/page.tsx', content='original')],
                    security_report={'passed': True}, code_review={'passed': True},
                    acceptance_report={'original_request_satisfied': True, 'checks': [], 'summary': 'checked'})
    result['state'].update(changes)
    return result


def test_additive_migration_of_old_database_and_rollback_survives_restart(tmp_path):
    path = tmp_path / 'old.sqlite3'
    old = completed()
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY,created TEXT,updated TEXT,title TEXT,status TEXT,document TEXT)')
    raw = json.dumps(old)
    db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)', ('v1', old['created_at'], old['updated_at'], 'old', 'accepted', raw))
    db.commit()
    db.close()
    store = History(path)
    assert store.project('v1')['current_version'] == 'v1'
    assert store.db.execute('SELECT document FROM tasks').fetchone()[0] == raw
    store.save(completed('v2', workspace_id='v1', base_version='v1', expected_version='v1'))
    assert store.project('v1')['current_version'] == 'v2'
    store.restore_version('v1', 'v1')
    store.close()
    store = History(path)
    assert store.project('v1')['current_version'] == 'v1'
    assert len(store.project('v1')['versions']) == 2
    assert [e['action'] for e in store.project('v1')['events']] == ['restore', 'promote', 'promote']


def test_three_revisions_failure_and_stale_promotion_keep_selected_version():
    store = History()
    store.save(completed())
    for index in (2, 3, 4):
        previous = 'v' + str(index - 1)
        store.save(completed('v' + str(index), workspace_id='v1', base_version=previous, expected_version=previous))
    store.save(completed('bad', workspace_id='v1', base_version='v4', expected_version='v4', phase='failed'))
    assert store.project('v1')['current_version'] == 'v4'
    store.save(completed('stale', workspace_id='v1', base_version='v1', expected_version='v1'))
    assert store.project('v1')['current_version'] == 'v4'
    with pytest.raises(ValueError):
        store.restore_version('v1', 'bad')
    store.save(completed('other'))
    with pytest.raises(ValueError):
        store.restore_version('v1', 'other')
    running = completed('running', workspace_id='v1')
    running.update(done=False, waiting='plan')
    store.save(running)
    with pytest.raises(ValueError):
        store.restore_version('v1', 'v1')


@pytest.mark.parametrize('field,value', [('build_passed', False), ('security_report', None),
    ('code_review', {'passed': False}), ('acceptance_report', None), ('gate_2_approved', False)])
def test_missing_quality_evidence_never_promotes(field, value):
    store = History()
    store.save(completed(**{field: value}))
    assert store.project('v1')['current_version'] is None


def test_imported_acceptance_flags_cannot_bypass_missing_requirement_evidence():
    store = History()
    store.save(completed(requirements=['必须保留联系方式']))
    assert store.project('v1')['current_version'] is None


def test_delta_preserves_unmentioned_files_through_three_changes():
    files = [GeneratedFile(path='app/page.tsx', content='v1'), GeneratedFile(path='lib/keep.ts', content='keep exactly\n')]
    for index in (2, 3, 4):
        raw = json.dumps({'changes': [dict(path='app/page.tsx', before_sha256=digest(files[0].content), content='v' + str(index))]})
        files, _ = apply_patch_response(raw, files)
        assert files[1].content == 'keep exactly\n'
    assert files[0].content == 'v4'


@pytest.mark.parametrize('change', [
    dict(path='../app/page.tsx', before_sha256=None, content='bad'),
    dict(path='app/page.tsx', before_sha256='wrong', content='bad'),
    dict(path='app/page.tsx', before_sha256=digest('old'), content=None),
    dict(path='package.json', before_sha256=None, content='bad'),
    dict(path='APP/page.tsx', before_sha256=None, content='bad'),
    dict(path='lib/missing.ts', before_sha256=None, content=None),
    dict(path='app/page.tsx', before_sha256=digest('old'), content=123),
])
def test_invalid_patch_cannot_mutate_source(change):
    original = [GeneratedFile(path='app/page.tsx', content='old')]
    with pytest.raises(ValueError):
        apply_patch_response(json.dumps({'changes': [change]}), original)
    assert original[0].content == 'old'


def test_duplicate_and_full_output_refused_and_explicit_delete_supported():
    original = [GeneratedFile(path='app/page.tsx', content='old'), GeneratedFile(path='lib/delete.ts', content='unused')]
    change = dict(path='lib/delete.ts', before_sha256=digest('unused'), content=None)
    with pytest.raises(ValueError):
        apply_patch_response(json.dumps({'changes': [change, change]}), original)
    with pytest.raises(ValueError):
        apply_patch_response(json.dumps({'files': []}), original)
    files, _ = apply_patch_response(json.dumps({'changes': [change]}), original)
    assert len(files) == 1
    diff = file_diff([f.model_dump() for f in original], [f.model_dump() for f in files])
    assert diff[0]['kind'] == 'deleted' and diff[0]['path'] == 'lib/delete.ts'


def test_job_revision_loads_source_keeps_original_contract_and_failed_candidate():
    def execute(state, llm, **kwargs):
        state.phase = ProjectPhase.FAILED
        return state
    jobs = Jobs(execute, lambda: object())
    base = completed()
    jobs.history.save(base)
    ident = jobs.start('把标题改成新版', ['增加联系方式'], base_version='v1')
    wait_until(lambda: jobs.snapshot(ident)['done'])
    result = jobs.snapshot(ident)['state']
    assert result['idea'] == base['state']['idea']
    assert result['change_requests'] == ['把标题改成新版']
    assert result['generated_files'] == base['state']['generated_files']
    assert result['workspace_id'] == 'v1'
    assert result['requirements'] == ['增加联系方式']
    assert jobs.history.project('v1')['current_version'] == 'v1'
    assert jobs.history.get('v1') == base


def test_project_api_auth_changes_and_restore(server):
    from urllib.error import HTTPError
    jobs, request = server
    jobs.history.save(completed())
    jobs.history.save(completed('v2', workspace_id='v1', base_version='v1', expected_version='v1',
                                generated_files=[dict(path='app/page.tsx', content='modified')]))
    assert request('/api/projects')['projects'][0]['current_version'] == 'v2'
    assert len(request('/api/projects/v1')['versions']) == 2
    assert request('/api/jobs/v2/changes')['files'][0]['kind'] == 'modified'
    assert request('/api/projects/v1/restore', {'version': 'v1'})['current_version'] == 'v1'
    for url in ('/api/projects', '/api/projects/v1', '/api/jobs/v2/changes'):
        with pytest.raises(HTTPError) as exc:
            request(url, headers={})
        assert exc.value.code == 403
    with pytest.raises(HTTPError):
        request('/api/projects/v1/restore', {'version': 'v2'}, headers={'Origin': 'https://other.example'})
    ident = request('/api/jobs', {'idea': '修改标题', 'base_version': 'v1'})['id']
    wait_until(lambda: jobs.snapshot(ident)['waiting'] == 'plan')
    assert request('/api/jobs/'+ident)['state']['base_version'] == 'v1'


def test_finished_version_is_immutable():
    store = History()
    item = completed()
    store.save(item)
    store.save(item)  # Identical repeat is idempotent.
    item['state']['generated_files'][0]['content'] = 'overwritten'
    with pytest.raises(ValueError, match='不可覆盖'):
        store.save(item)
    assert store.get('v1')['state']['generated_files'][0]['content'] == 'original'


def test_local_manual_edits_and_outside_paths_are_not_silently_discarded(tmp_path):
    from orchestration.revisions import verify_base_snapshot
    from orchestration.state import ProjectState
    root = tmp_path / 'generated'
    target = root / 'old'
    (target / 'app').mkdir(parents=True)
    page = target / 'app/page.tsx'
    page.write_text('original', encoding='utf-8')
    state = ProjectState.model_validate(completed(build_dir=str(target))['state'])
    verify_base_snapshot(state, root)
    page.write_text('manually edited', encoding='utf-8')
    with pytest.raises(ValueError, match='手动修改'):
        verify_base_snapshot(state, root)
    state.build_dir = str(tmp_path)
    with pytest.raises(ValueError, match='generated'):
        verify_base_snapshot(state, root)
    state.build_dir = str(root / 'deleted')
    verify_base_snapshot(state, root)


def test_full_revision_pipeline_preserves_untouched_files_and_base_directory(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from orchestration import config
    from orchestration.build_cli import execute
    from orchestration.state import ProjectState
    from orchestration.verify import VerifyResult
    from tests.test_instruction_workflow import pipeline_llm
    monkeypatch.setattr(config, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(config, 'GENERATED_DIR', tmp_path / 'generated')
    monkeypatch.setattr('orchestration.knowledge_cache.save_knowledge_case', lambda *a: None)
    monkeypatch.setattr('orchestration.build_cli.record_case_saved', lambda *a: None)
    results = [VerifyResult(False, 'build', 'fix type'), VerifyResult(True, 'ok', 'compiled')]
    monkeypatch.setattr('orchestration.verify.verify_app', lambda *a, **kw: results.pop(0))
    @contextmanager
    def preview(*args):
        yield 'http://localhost:3000', True
    monkeypatch.setattr('orchestration.preview.dev_server', preview)
    llm = pipeline_llm()
    llm.responses['[agent:builder]'] = json.dumps({'changes': []})
    base_dir = tmp_path / 'generated' / 'old'
    base_dir.mkdir(parents=True)
    (base_dir / 'keep.txt').write_text('unchanged')
    files = [GeneratedFile(path='app/page.tsx', content='export default function Page(){return <main>中文</main>}'),
             GeneratedFile(path='lib/keep.ts', content='export const keep = 123;')]
    state = ProjectState(project_id='next', workspace_id='old', base_version='old', idea='原始作品集',
                         change_requests=['保留中文标题'], requirements=['中文'], generated_files=files)
    result = execute(state, llm, approver=lambda s: (True, None), preview_approver=lambda s: (True, None), emit=lambda _: None)
    assert result.phase == ProjectPhase.GATE_2_APPROVED
    assert result.repair_attempts == 1
    assert (base_dir / 'keep.txt').read_text() == 'unchanged'
    from pathlib import Path
    assert (Path(result.build_dir) / 'lib/keep.ts').read_text() == files[1].content
    assert all('保留中文标题' in call['prompt'] and '原始作品集' in call['prompt'] for call in llm.calls)
    calls = [c for c in llm.calls if '[agent:builder]' in c['system']]
    assert len(calls) == 2 and all('before_sha256' in c['prompt'] for c in calls)


# Reuse only the HTTP fixture; it uses a fake model and never starts npm.
from tests.test_web import server
