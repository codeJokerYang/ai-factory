import io
import json
import zipfile
import subprocess
import sys
from contextlib import contextmanager

import pytest

from orchestration.execution_policy import ExecutionLimits, MeteredLLM, cost_summary, BusinessCase
from orchestration.state import ProjectState, ProjectPhase
from orchestration.history import History
from orchestration.web import Jobs
from orchestration.delivery import capture_artifacts, make_bundle
from tests.test_history import record
from tests.test_projects import completed
from tests.test_web import wait_until, server


class UsageClient:
    def __init__(self):
        self.calls = 0
        self.last_usage = None

    def complete(self, **kwargs):
        self.calls += 1
        self.last_usage = dict(input_tokens=100, output_tokens=200, cache_read_input_tokens=50)
        return 'ok'


def test_usage_reserves_before_call_and_prices_are_snapshotted():
    state = ProjectState(project_id='run', idea='test', limits=ExecutionLimits(max_calls=1))
    client = UsageClient()
    events = []
    prices = {'test': dict(currency='CNY', input_per_million=2, output_per_million=8)}
    meter = MeteredLLM(client, state, lambda s: events.append((client.calls, s.model_calls[-1]['status'])), prices)
    meter.complete(model='test', system='sys', prompt='prompt', max_tokens=20)
    assert events == [(0, 'started'), (1, 'completed')]
    assert state.model_calls[0]['cost'] == pytest.approx(.0019)
    assert cost_summary(state.model_calls)['estimated']['CNY'] == pytest.approx(.0019)
    with pytest.raises(ValueError, match='预算'):
        meter.complete(model='test', system='sys', prompt='prompt')
    assert client.calls == 1


def test_amount_and_token_caps_block_before_provider_and_unknown_is_not_zero():
    client = UsageClient()
    state = ProjectState(project_id='run', idea='x', limits=ExecutionLimits(max_tokens=1000))
    meter = MeteredLLM(client, state, lambda s: None)
    with pytest.raises(ValueError):
        meter.complete(model='test', system='', prompt='')
    state.limits = ExecutionLimits(max_cost=.000001)
    with pytest.raises(ValueError, match='单价'):
        meter.complete(model='test', system='', prompt='')
    meter.prices = {'test': dict(currency='CNY', input_per_million=2, output_per_million=8)}
    with pytest.raises(ValueError, match='金额预算'):
        meter.complete(model='test', system='', prompt='')
    assert client.calls == 0
    state.limits = ExecutionLimits()
    meter.prices = {}
    meter.complete(model='test', system='', prompt='')
    summary = cost_summary(state.model_calls)
    assert summary['estimated'] == {} and summary['unpriced_calls'] == 1


def test_failed_provider_keeps_reserved_budget():
    class Fail:
        def complete(self, **kwargs):
            raise RuntimeError('timeout')
    state = ProjectState(project_id='x', idea='x')
    meter = MeteredLLM(Fail(), state, lambda s: None)
    with pytest.raises(RuntimeError):
        meter.complete(model='test', system='', prompt='')
    assert state.model_calls[0]['status'] == 'failed'
    assert state.model_calls[0]['reserved_tokens'] > 0 and state.model_calls[0]['cost'] is None


def test_global_costs_do_not_count_recovery_ancestors_twice():
    store=History()
    call=dict(run_id='old',reserved_tokens=1000,input_tokens=10,output_tokens=20,cost=.5,price={'currency':'CNY'})
    store.save(record('old',model_calls=[call]))
    store.save(record('new',model_calls=[call,dict(call,run_id='new',cost=.2)],resumed_from='old'))
    assert store.costs()['calls']==2
    assert store.costs()['estimated']['CNY']==pytest.approx(.7)


def test_resume_uses_only_safe_checkpoint_and_is_idempotent(tmp_path):
    path = tmp_path / 'history.sqlite3'
    store = History(path)
    item = record('old', phase='planning', completed_steps=['分析需求'], product_spec={'project_name':'safe','one_liner':'x','target_users':'u'})
    item.update(done=False)
    store.save(item)
    # A failed step mutates its working state, but must not replace the completed point.
    item['state']['product_spec']['project_name'] = 'unsafe partial'
    item['state']['phase'] = 'failed'
    item['state']['model_calls'] = [dict(run_id='old', reserved_tokens=1500, input_tokens=None, output_tokens=None, status='failed', cost=None)]
    item['done'] = True
    store.save(item)
    store.close()
    def execute(state, llm, **kwargs):
        state.phase = ProjectPhase.FAILED
        return state
    jobs = Jobs(execute, lambda: object(), history_path=path)
    ident = jobs.resume('old')
    wait_until(lambda: jobs.snapshot(ident)['done'])
    assert jobs.resume('old') == ident
    state = jobs.snapshot(ident)['state']
    assert state['product_spec']['project_name'] == 'safe'
    assert state['resumed_from'] == 'old'
    assert state['gate_1_approved'] is False
    assert state['model_calls'][0]['reserved_tokens'] == 1500
    assert jobs.history.get('old')['state']['product_spec']['project_name'] == 'unsafe partial'


def test_resume_without_checkpoint_replans_and_rejects_stale_or_rejected():
    jobs = Jobs(lambda s, llm, **kw: s.model_copy(update={'phase':ProjectPhase.FAILED}), lambda: object())
    jobs.history.save(record('old', phase='interrupted'))
    ident = jobs.resume('old')
    wait_until(lambda: jobs.snapshot(ident)['done'])
    assert jobs.snapshot(ident)['state']['completed_steps'] == []
    jobs.history.save(record('reject', phase='plan_rejected'))
    with pytest.raises(ValueError, match='拒绝'):
        jobs.resume('reject')
    jobs.history.save(completed('new', workspace_id='old'))
    with pytest.raises(ValueError, match='过期'):
        jobs.resume(ident)


def test_real_business_failure_blocks_gate_even_with_other_checks():
    from orchestration.gate2 import make_gate_2
    state = ProjectState.model_validate(completed()['state'])
    state.delivery_mode = True
    state.preview_ready = True
    state.business_report = {'passed':False, 'cases':[{'passed':False}]}
    make_gate_2(lambda s: pytest.fail('must not approve'))(state)
    assert state.phase == ProjectPhase.FAILED


def test_bundle_is_verified_excludes_credentials_and_detects_tampering(tmp_path):
    from orchestration.scaffold import write_app
    from orchestration.schemas import GeneratedFile
    target = tmp_path / 'generated' / 'app'
    write_app(target, 'site', [GeneratedFile(path='app/page.tsx', content='export default function Page(){return <main>Hi</main>}')])
    (target / 'package-lock.json').write_text('{}')
    (target / '.env.local').write_text('SECRET=do-not-export')
    report = completed(build_dir=str(target), delivery_mode=True,
        business_cases=[{'name':'real check','steps':[{'action':'text','target':'Hi'}]}],
        business_report={'passed':True,'cases':[{'name':'real check','passed':True,'width':w,'steps':1} for w in [1440,390]]}, artifact_hashes=capture_artifacts(target))
    data = make_bundle(report, tmp_path / 'generated')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert '.env.local' not in archive.namelist()
        assert 'package-lock.json' in archive.namelist()
        assert json.loads(archive.read('factory-manifest.json'))['status'] == 'local_handoff_not_deployed'
    (target / 'app/page.tsx').write_text('changed')
    with pytest.raises(ValueError, match='变化'):
        make_bundle(report, tmp_path / 'generated')
    report['state']['delivery_mode'] = False
    with pytest.raises(ValueError, match='交付模式'):
        make_bundle(report, tmp_path / 'generated')


def test_server_lease_excludes_second_process_and_can_reopen(tmp_path):
    from orchestration.lease import ServerLease
    path = tmp_path / 'lease'
    first = ServerLease(path)
    with pytest.raises(RuntimeError):
        ServerLease(path)
    first.close()
    ServerLease(path).close()


def test_abrupt_process_exit_releases_lease_and_retains_recoverable_checkpoint(tmp_path):
    from orchestration.lease import ServerLease
    script='''import os,sys
from pathlib import Path
from orchestration.history import History,now_iso
from orchestration.lease import ServerLease
from orchestration.state import ProjectState
root=Path(sys.argv[1]);lease=ServerLease(root/'lease');store=History(root/'history.sqlite3')
state=ProjectState(project_id='crashed',idea='recover me',completed_steps=['分析需求'],product_spec={'project_name':'safe','one_liner':'x','target_users':'u'})
store.save(dict(id='crashed',done=False,waiting=None,logs=[],decisions=[],created_at=now_iso(),updated_at=now_iso(),state=state.model_dump(mode='json')))
os._exit(17)
'''
    child=subprocess.run([sys.executable,'-c',script,str(tmp_path)],capture_output=True,timeout=15)
    assert child.returncode==17,child.stderr
    lease=ServerLease(tmp_path/'lease')
    try:
        store=History(tmp_path/'history.sqlite3')
        assert store.get('crashed')['state']['phase']=='interrupted'
        assert store.recovery_state('crashed')['product_spec']['project_name']=='safe'
        store.close()
    finally:
        lease.close()


def test_new_api_price_validation_resume_and_bundle_guards(server):
    from urllib.error import HTTPError
    jobs, request = server
    price = request('/api/prices', dict(model='test', currency='CNY', input_per_million=2, output_per_million=8))
    assert price['model'] == 'test'
    assert request('/api/prices')['prices']['test']['input_per_million'] == 2
    with pytest.raises(HTTPError):
        request('/api/prices', dict(model='test', currency='CNY', input_per_million=-2, output_per_million=8))
    with pytest.raises(HTTPError):
        request('/api/jobs', dict(idea='x', delivery_mode=True))
    jobs.history.save(record('old', phase='interrupted'))
    ident = request('/api/jobs/old/resume', {})['id']
    assert request('/api/jobs/old/resume', {})['id'] == ident
    with pytest.raises(HTTPError):
        request('/api/jobs/old/bundle')
    for url in ['/api/prices','/api/jobs/old/bundle']:
        with pytest.raises(HTTPError) as exc:
            request(url, headers={})
        assert exc.value.code == 403


def test_resume_pipeline_skips_completed_model_steps_but_rechecks(tmp_path, monkeypatch):
    from orchestration import config
    from orchestration.build_cli import execute
    from orchestration.schemas import ProductSpec, Architecture, Dag, GeneratedFile
    from orchestration.verify import VerifyResult
    from tests.test_instruction_workflow import pipeline_llm
    from tests.test_pipeline_mock import DECOMPOSER_JSON
    monkeypatch.setattr(config,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(config,'GENERATED_DIR',tmp_path/'generated')
    monkeypatch.setattr('orchestration.verify.verify_app',lambda *a,**kw:VerifyResult(True,'ok','built'))
    monkeypatch.setattr('orchestration.knowledge_cache.save_knowledge_case',lambda *a:None)
    monkeypatch.setattr('orchestration.build_cli.record_case_saved',lambda *a:None)
    @contextmanager
    def preview(*args):
        yield 'http://127.0.0.1:3000',True
    monkeypatch.setattr('orchestration.preview.dev_server',preview)
    llm = pipeline_llm()
    state = ProjectState(project_id='resume', idea='原始需求', resumed_from='old',
        completed_steps=['分析需求','设计方案','拆解任务','生成代码'], requirements=['中文'],
        product_spec=ProductSpec(project_name='app',one_liner='x',target_users='u'),
        architecture=Architecture(stack={},deploy_target='local'), dag=Dag(**json.loads(DECOMPOSER_JSON)),
        generated_files=[GeneratedFile(path='app/page.tsx',content='export default function Page(){return <main>中文</main>}')])
    approvals=[]
    result=execute(state,llm,approver=lambda s:(approvals.append('plan') or True,None),preview_approver=lambda s:(approvals.append('preview') or True,None),emit=lambda s:None)
    assert result.phase == ProjectPhase.GATE_2_APPROVED
    assert approvals == ['plan','preview']
    assert not any(any(marker in c['system'] for marker in ['[agent:planner]','[agent:architect]','[agent:decomposer]','[agent:builder]']) for c in llm.calls)
    assert len(result.model_calls)==len(llm.calls)
