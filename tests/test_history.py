import json
import threading
from contextlib import contextmanager

import pytest

from orchestration.history import History, HistoryPreview, now_iso
from orchestration.state import ProjectState, ProjectPhase
from orchestration.web import Jobs
from tests.test_web import wait_until


def record(ident='test1', **state_changes):
    state = ProjectState(project_id=ident, idea='做中文作品集', requirements=['中文']).model_dump(mode='json')
    state.update(state_changes)
    return dict(id=ident, state=state, created_at=now_iso(), updated_at=now_iso(),
                done=True, waiting=None, logs=['已完成本地记录'], decisions=[])


def test_restart_retains_failed_task_and_feedback(tmp_path):
    path = tmp_path / 'history.sqlite3'
    def execute(state, llm, *, approver, preview_approver, emit, checkpoint):
        state = state.model_copy(update={'phase': ProjectPhase.WAITING_GATE_1})
        checkpoint(state)
        emit('准备方案审批')
        approved, feedback = approver(state)
        state.phase = ProjectPhase.PLAN_REJECTED
        state.gate_1_feedback = feedback
        return state
    jobs = Jobs(execute, lambda: object(), history_path=path)
    ident = jobs.start('我今天要做作品集', ['保留数据'])
    wait_until(lambda: jobs.snapshot(ident)['waiting'] == 'plan')
    jobs.decide(ident, 'plan', False, '先补充需求')
    wait_until(lambda: jobs.snapshot(ident)['done'])
    reopened = Jobs(history_path=path)
    saved = reopened.snapshot(ident)
    assert saved['state']['idea'] == '我今天要做作品集'
    assert saved['state']['requirements'] == ['保留数据']
    assert saved['state']['gate_1_feedback'] == '先补充需求'
    assert saved['decisions'][0]['feedback'] == '先补充需求'
    assert saved['logs'] == ['准备方案审批']
    assert reopened.listing()['tasks'][0]['status'] == 'rejected'


def test_unfinished_checkpoint_becomes_interrupted_not_accepted(tmp_path):
    path = tmp_path / 'db.sqlite3'
    store = History(path)
    item = record(phase='waiting_gate_2', build_dir='/generated/app', preview_ready=True,
                  preview_url='http://127.0.0.1:12345')
    item.update(done=False, waiting='preview')
    store.save(item)
    store.close()
    restarted = History(path)
    saved = restarted.get('test1')
    assert saved['done'] and saved['waiting'] is None
    assert saved['state']['phase'] == 'interrupted'
    assert saved['state']['build_dir'] == '/generated/app'
    assert saved['state']['preview_url'] is None
    assert restarted.listing()['tasks'][0]['status'] == 'interrupted'


def test_archive_not_evicted_and_credentials_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'secret-real-credential-123')
    store = History(tmp_path / 'db.sqlite3')
    for i in range(65):
        item = record(str(i))
        item['logs'] = ['provider error: secret-real-credential-123']
        store.save(item)
    assert store.listing()['total'] == 65
    assert len(store.listing(offset=60, limit=30)['tasks']) == 5
    assert store.get('0')['logs'] == ['provider error: [REDACTED]']
    assert 'secret-real-credential-123' not in (tmp_path / 'db.sqlite3').read_bytes().decode('latin1')
    with pytest.raises(KeyError):
        store.get("' OR 1=1 --")


def test_old_report_import_is_idempotent_and_corruption_is_visible(tmp_path):
    reports = tmp_path / 'runs'
    (reports / 'old').mkdir(parents=True)
    (reports / 'old' / 'report.json').write_text(ProjectState(project_id='old', idea='旧任务').model_dump_json(), encoding='utf-8')
    (reports / 'broken').mkdir()
    (reports / 'broken' / 'report.json').write_text('{bad', encoding='utf-8')
    store = History(tmp_path / 'db.sqlite3')
    store.import_reports(reports)
    store.import_reports(reports)
    assert store.listing()['total'] == 1
    assert store.get('old')['state']['phase'] == 'interrupted'
    assert store.get('old')['source'] == 'legacy_report'
    assert store.listing()['warnings']


def preview_record(tmp_path):
    target = tmp_path / 'generated' / 'app'
    (target / 'node_modules' / 'next').mkdir(parents=True)
    (target / 'package.json').write_text(json.dumps({'scripts': {'dev': 'next dev'}}))
    return record(build_dir=str(target), build_passed=True, security_report={'passed': True})


def test_preview_start_ready_stop_and_cleanup(tmp_path):
    closed = threading.Event()
    @contextmanager
    def factory(target, ready_timeout):
        try:
            yield 'http://127.0.0.1:54321', True
        finally:
            closed.set()
    item = preview_record(tmp_path)
    manager = HistoryPreview(tmp_path / 'generated', factory)
    manager.start(item)
    wait_until(lambda: manager.snapshot(item['id'])['status'] == 'ready')
    assert manager.snapshot(item['id'])['url'].endswith(':54321')
    manager.stop(item['id'])
    wait_until(closed.is_set)
    wait_until(lambda: manager.snapshot(item['id'])['status'] == 'stopped')


def test_preview_timeout_is_visible_and_retryable(tmp_path):
    @contextmanager
    def factory(target, ready_timeout):
        yield 'http://127.0.0.1:54321', False
    manager = HistoryPreview(tmp_path / 'generated', factory)
    item = preview_record(tmp_path)
    for _ in range(2):
        manager.start(item)
        wait_until(lambda: manager.snapshot(item['id'])['status'] == 'failed')
        assert '30 秒' in manager.snapshot(item['id'])['error']


def test_preview_refuses_missing_unverified_external_and_changed_script(tmp_path):
    manager = HistoryPreview(tmp_path / 'generated')
    item = preview_record(tmp_path)
    for changes in [{'build_dir': str(tmp_path)}, {'build_dir': str(tmp_path / 'generated' / 'gone')},
                    {'build_passed': False}, {'security_report': {'passed': False}}]:
        other = {**item, 'state': {**item['state'], **changes}}
        with pytest.raises(ValueError):
            manager.start(other)
    target = tmp_path / 'generated' / 'app'
    (target / 'package.json').write_text(json.dumps({'scripts': {'dev': 'echo unsafe'}}))
    with pytest.raises(ValueError, match='启动脚本'):
        manager.start(item)
