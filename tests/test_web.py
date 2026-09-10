import json
import re
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from orchestration.web import Jobs, make_server
from orchestration.state import ProjectPhase


def wait_until(fn):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(.01)
    pytest.fail('后台任务超时')


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr('orchestration.config.get_api_key', lambda: 'test-only')
    def execute(state,llm,*,approver,preview_approver,emit):
        emit('分析需求')
        approved,feedback=approver(state)
        state.gate_1_approved=approved
        state.gate_1_feedback=feedback
        state.phase=ProjectPhase.BUILD_DONE if approved else ProjectPhase.PLAN_REJECTED
        return state
    jobs=Jobs(execute_fn=execute,llm_factory=lambda:object())
    srv=make_server(0,jobs)
    thread=threading.Thread(target=srv.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{srv.server_port}'
    with urlopen(base) as response:
        html=response.read().decode()
    token=re.search("const token='([^']+)'",html).group(1)
    def request(path,body=None,headers=None):
        req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,
                    headers=headers if headers is not None else {'X-Factory-Token':token,'Content-Type':'application/json'})
        with urlopen(req) as response:
            return json.load(response)
    yield jobs,request
    for ident,j in list(jobs.items.items()):
        if j['waiting'] and j['decision'] is None:
            jobs.decide(ident,j['waiting'],False,'test teardown')
    srv.shutdown()
    srv.server_close()
    thread.join(2)


def test_submit_poll_reject_and_report(server):
    jobs,request=server
    ident=request('/api/jobs',{'idea':'中文任务工具','requirements':['不要登录']})['id']
    wait_until(lambda:jobs.snapshot(ident)['waiting']=='plan')
    snap=request('/api/jobs/'+ident)
    assert snap['state']['requirements']==['不要登录']
    request('/api/jobs/'+ident+'/decision',{'stage':'plan','approved':False,'feedback':'修改方案'})
    wait_until(lambda:jobs.snapshot(ident)['done'])
    assert request('/api/jobs/'+ident)['state']['phase']=='plan_rejected'


def test_csrf_and_dns_rebinding_blocked(server):
    _,request=server
    for headers in [{},{'Host':'attacker.example'}]:
        with pytest.raises(HTTPError) as exc:
            request('/api/jobs',{'idea':'x'},headers=headers)
        assert exc.value.code==403


def test_invalid_input_and_concurrent_jobs(server):
    jobs,request=server
    with pytest.raises(HTTPError):
        request('/api/jobs',{'idea':' '})
    ident=request('/api/jobs',{'idea':'x'})['id']
    wait_until(lambda:jobs.snapshot(ident)['waiting']=='plan')
    with pytest.raises(HTTPError):
        request('/api/jobs',{'idea':'second'})
    with pytest.raises(HTTPError):
        request('/api/jobs/'+ident+'/decision',{'stage':'preview','approved':True})


def test_model_setup_failure_is_visible():
    def fail(): raise RuntimeError('模型不可用')
    jobs=Jobs(llm_factory=fail)
    ident=jobs.start('x',[])
    wait_until(lambda:jobs.snapshot(ident)['done'])
    assert jobs.snapshot(ident)['state']['errors']==['模型不可用']
