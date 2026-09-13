"""Real Chromium business checks. Set FACTORY_PLAYWRIGHT_MODULE to run locally."""
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from orchestration.business import run_business_tests
from orchestration.execution_policy import BusinessCase


@pytest.fixture
def business_site():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == '/missing':
                self.send_response(404)
                self.end_headers()
                return
            persist = '' if self.path == '/broken' else "localStorage.setItem('name',input.value);"
            html = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>业务验收演练</title><style>body{font-family:sans-serif;max-width:600px;margin:30px auto;padding:20px}input,button{padding:12px;margin:10px 0;max-width:100%;box-sizing:border-box}</style>
<h1>客户资料</h1><label for="name">姓名</label><input id="name"><button id="save">保存</button><p id="status"></p>
<script>const input=document.getElementById('name');input.value=localStorage.getItem('name')||'';
document.getElementById('save').onclick=()=>{''' + persist + '''document.getElementById('status').textContent='保存成功';};</script></html>'''
            raw = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.mark.skipif(not os.environ.get('FACTORY_PLAYWRIGHT_MODULE'), reason='Requires configured Chromium/Playwright')
def test_actual_browser_detects_lost_data_and_missing_page(business_site, tmp_path):
    def scenario(route):
        return BusinessCase(name='资料保存后刷新仍保留',steps=[
            {'action':'visit','target':route}, {'action':'fill','target':'姓名','value':'张三'},
            {'action':'click','target':'保存'}, {'action':'text','target':'保存成功'},
            {'action':'reload'}, {'action':'value','target':'姓名','value':'张三'}])
    good=run_business_tests(business_site,[scenario('/')],tmp_path/'good')
    assert good['passed'], good
    assert {c['width'] for c in good['cases']} == {390,1440}
    assert all((tmp_path/'good'/c['screenshot']).is_file() for c in good['cases'])
    broken=run_business_tests(business_site,[scenario('/broken')],tmp_path/'broken')
    assert not broken['passed'] and all(not c['passed'] for c in broken['cases'])
    missing=run_business_tests(business_site,[BusinessCase(name='缺失页面',steps=[{'action':'visit','target':'/missing'},{'action':'text','target':'客户资料'}])],tmp_path/'missing')
    assert not missing['passed']


def test_business_requires_local_target_and_assertions(tmp_path):
    with pytest.raises(ValueError):
        run_business_tests('https://external.example',[],tmp_path)
    assert not run_business_tests('http://127.0.0.1:12345',[],tmp_path)['passed']


def test_missing_browser_runtime_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('FACTORY_NODE', str(tmp_path/'missing-node.exe'))
    result=run_business_tests('http://127.0.0.1:12345',[BusinessCase(name='test',steps=[{'action':'text','target':'Hello'}])],tmp_path)
    assert not result['passed'] and result['error']
