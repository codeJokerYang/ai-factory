import json
from contextlib import contextmanager

import pytest

from orchestration import config
from orchestration.acceptance import AcceptanceReport, check_acceptance
from orchestration.agents.builder import Builder, _parse_output
from orchestration.agents.reviewer import Reviewer
from orchestration.build_cli import execute
from orchestration.gate2 import make_gate_2
from orchestration.instructions import parse_request
from orchestration.llm import MockLLM
from orchestration.schemas import CodeReview, GeneratedFile, SecurityReport
from orchestration.state import ProjectPhase, ProjectState
from orchestration.verify import VerifyResult
from tests.test_pipeline_mock import PLANNER_JSON, ARCHITECT_JSON, DECOMPOSER_JSON


def test_file_and_explicit_requirements(tmp_path):
    path = tmp_path / '需求.md'
    path.write_text('必须中文，不要登录', encoding='utf-8-sig')
    args = parse_request(['任务工具', '--instructions-file', str(path), '--require', '刷新保留'], build=True)
    assert args.idea == '任务工具\n\n必须中文，不要登录'
    assert args.requirements == ['刷新保留']
    assert not args.generate_only


@pytest.mark.parametrize('argv', [[], ['x', '--typo'], ['x', '--require', ' '], ['x', '--generate-only', '--gate2']])
def test_invalid_inputs_fail(argv):
    with pytest.raises(SystemExit):
        parse_request(argv, build=True)


@pytest.mark.parametrize('path', ['package.json', 'app/.env', '.npmrc', 'next.config.mjs', 'app/../package.json'])
def test_generated_config_is_rejected(path):
    with pytest.raises(ValueError):
        _parse_output(json.dumps({'files': [{'path': 'app/page.tsx', 'content': 'x'}, {'path': path, 'content': '{}'}]}))


def test_repairs_keep_original_request_and_requirements():
    llm = MockLLM(responses={'[agent:builder]': json.dumps({'files': [{'path':'app/page.tsx','content':'fixed'}]})})
    state = ProjectState(project_id='t', idea='不允许登录', requirements=['必须使用中文'])
    builder = Builder(llm)
    builder.repair(state, 'compiler error')
    builder.revise(state, 'review feedback')
    assert all('不允许登录' in c['prompt'] and '必须使用中文' in c['prompt'] for c in llm.calls)


@pytest.mark.parametrize('checks', [[], [{'id':'R2','status':'missing'}], [{'id':'R1','status':'missing'}]*2])
def test_acceptance_requires_exact_requirement_ids(checks):
    state = ProjectState(project_id='t', idea='test', requirements=['中文'])
    llm = MockLLM(responses={'[agent:acceptance]': json.dumps(dict(checks=checks,original_request_satisfied=True,summary='ok'))})
    with pytest.raises(ValueError):
        check_acceptance(state,llm,'test')


def test_invented_evidence_cannot_pass():
    state = ProjectState(project_id='t', idea='test', requirements=['中文'], generated_files=[GeneratedFile(path='app/page.tsx',content='hello')])
    llm = MockLLM(responses={'[agent:acceptance]': json.dumps(dict(checks=[dict(id='R1',status='implemented',file='app/page.tsx',evidence='你好')],original_request_satisfied=True,summary='ok'))})
    check_acceptance(state,llm,'test')
    assert not state.acceptance_report.passed


@pytest.mark.parametrize('field,value', [('build_passed',False),('build_passed',None),('preview_ready',False),('code_review',None),('security_report',None),('acceptance_report',None)])
def test_gate_cannot_override_failed_checks(field,value):
    state = ProjectState(project_id='t',idea='x',build_passed=True,preview_ready=True,
                         code_review=CodeReview(passed=True),security_report=SecurityReport(),
                         acceptance_report=AcceptanceReport(original_request_satisfied=True,summary='ok'))
    setattr(state,field,value)
    make_gate_2(lambda _: pytest.fail('审批不应被调用'))(state)
    assert state.phase == ProjectPhase.FAILED
    assert not state.gate_2_approved


def test_review_parse_failure_does_not_keep_old_pass():
    state=ProjectState(project_id='t',idea='x',generated_files=[GeneratedFile(path='app/page.tsx',content='x')],code_review=CodeReview(passed=True))
    Reviewer(MockLLM()).run(state)
    assert state.code_review is None


def pipeline_llm():
    return MockLLM(responses={
        '[agent:planner]':PLANNER_JSON,'[agent:architect]':ARCHITECT_JSON,'[agent:decomposer]':DECOMPOSER_JSON,
        '[agent:builder]':json.dumps({'files':[{'path':'app/page.tsx','content':'export default function Page(){return <main>中文</main>}'}]}),
        '[agent:reviewer]':json.dumps({'passed':True,'issues':[]}),
        '[agent:acceptance]':json.dumps({'original_request_satisfied':True,'summary':'代码核对通过','checks':[{'id':'R1','status':'implemented','file':'app/page.tsx','evidence':'中文'}]})})


def test_full_pipeline_repair_final_review_and_report(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(config,'GENERATED_DIR',tmp_path/'generated')
    monkeypatch.setattr('orchestration.build_cli.record_cache_lookup', lambda *a: None)
    monkeypatch.setattr('orchestration.build_cli.record_case_saved', lambda *a: None)
    monkeypatch.setattr('orchestration.knowledge_cache.save_knowledge_case', lambda *a: None)
    results=[VerifyResult(False,'build','type error'),VerifyResult(True,'ok','compiled')]
    monkeypatch.setattr('orchestration.verify.verify_app',lambda *a,**kw:results.pop(0))
    @contextmanager
    def preview(*args):
        yield 'http://localhost:3000',True
    monkeypatch.setattr('orchestration.preview.dev_server',preview)
    llm=pipeline_llm()
    state=execute(ProjectState(project_id='test',idea='原始指令不可丢失',requirements=['中文']),llm,
                  approver=lambda s:(True,None),preview_approver=lambda s:(True,None),emit=lambda _:None)
    assert state.phase==ProjectPhase.GATE_2_APPROVED
    assert state.repair_attempts==1
    assert len([c for c in llm.calls if '[agent:reviewer]' in c['system']])==2
    assert all('原始指令不可丢失' in c['prompt'] for c in llm.calls)
    report=json.loads((tmp_path/'.factory/runs/test/report.json').read_text(encoding='utf-8'))
    assert report['gate_2_approved']


def test_rejected_plan_never_builds(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'PROJECT_ROOT',tmp_path)
    llm=pipeline_llm()
    state=execute(ProjectState(project_id='t',idea='x'),llm,approver=lambda s:(False,'不符合'),emit=lambda _:None)
    assert state.phase==ProjectPhase.PLAN_REJECTED
    assert not any('[agent:builder]' in c['system'] for c in llm.calls)


def test_provider_failure_persists_failure_report(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'PROJECT_ROOT',tmp_path)
    def fail(*a): raise RuntimeError('provider offline')
    state=execute(ProjectState(project_id='t',idea='x'),MockLLM(handler=fail),approver=lambda s:(True,None),emit=lambda _:None)
    assert state.phase==ProjectPhase.FAILED
    assert (tmp_path/'.factory/runs/t/report.json').exists()


def test_repair_removes_stale_generated_files_but_preserves_manual_edits(tmp_path):
    from orchestration.scaffold import write_app
    page=GeneratedFile(path='app/page.tsx',content='page')
    old=GeneratedFile(path='lib/old.ts',content='old')
    write_app(tmp_path,'test',[page,old])
    write_app(tmp_path,'test',[page])
    assert not (tmp_path/'lib/old.ts').exists()
    write_app(tmp_path,'test',[page,old])
    (tmp_path/'lib/old.ts').write_text('manual',encoding='utf-8')
    with pytest.raises(ValueError,match='手动修改'):
        write_app(tmp_path,'test',[page])


def test_security_blocks_before_npm(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(config,'GENERATED_DIR',tmp_path/'generated')
    monkeypatch.setattr('orchestration.build_cli.record_cache_lookup',lambda *a:None)
    monkeypatch.setattr('orchestration.verify.verify_app',lambda *a,**kw:pytest.fail('不能运行 npm'))
    llm=pipeline_llm()
    llm.responses['[agent:builder]']=json.dumps({'files':[{'path':'app/page.tsx','content':'import x from "child_process";'}]})
    state=execute(ProjectState(project_id='t',idea='x'),llm,approver=lambda s:(True,None),emit=lambda _:None)
    assert state.phase==ProjectPhase.FAILED
    assert state.security_report.passed is False


def test_failed_build_never_opens_preview(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'PROJECT_ROOT',tmp_path)
    monkeypatch.setattr(config,'GENERATED_DIR',tmp_path/'generated')
    monkeypatch.setattr('orchestration.build_cli.record_cache_lookup',lambda *a:None)
    monkeypatch.setattr('orchestration.verify.verify_app',lambda *a,**kw:VerifyResult(False,'install','offline'))
    monkeypatch.setattr('orchestration.preview.dev_server',lambda *a:pytest.fail('不能预览'))
    state=execute(ProjectState(project_id='t',idea='x'),pipeline_llm(),approver=lambda s:(True,None),
                  preview_approver=lambda s:pytest.fail('不能验收'),emit=lambda _:None)
    assert state.phase==ProjectPhase.FAILED
    assert state.build_passed is False
