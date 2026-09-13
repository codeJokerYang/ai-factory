"""Local, single-user web entry. Run: python -m orchestration.web."""
from __future__ import annotations

import argparse
import json
import secrets
import threading
import time
import uuid
import inspect
import sqlite3
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config
from .state import ProjectState, ProjectPhase
from .history import History, HistoryPreview, now_iso, redact

MAX_BODY = 128 * 1024


class Jobs:
    def __init__(self, execute_fn=None, llm_factory=None, history_path=None, reports_dir=None, preview_factory=None):
        from .build_cli import execute
        from .llm import AnthropicLLM
        self.execute = execute_fn or execute
        self.llm_factory = llm_factory or AnthropicLLM
        self.lock = threading.RLock()
        self.items = {}
        self.history = History(history_path)
        if reports_dir is not None:
            self.history.import_reports(reports_dir)
        self.previews = HistoryPreview(config.GENERATED_DIR, preview_factory)

    def _persist(self, ident):
        job = self.items[ident]
        job['updated_at'] = now_iso()
        self.history.save(self.snapshot(ident))

    def listing(self, offset=0, limit=30):
        return self.history.listing(offset, limit)

    def start(self, idea, requirements, *, base_version=None, client_name=''):
        if not isinstance(idea, str) or not idea.strip() or len(idea) > 30000:
            raise ValueError('需求不能为空且不超过 30000 字符')
        if (not isinstance(requirements, list) or len(requirements) > 100
                or any(not isinstance(r, str) or not r.strip() or len(r) > 2000 for r in requirements)):
            raise ValueError('要求格式错误；最多 100 条，每条不超过 2000 字符')
        if not isinstance(client_name, str) or len(client_name) > 120:
            raise ValueError('客户名称最多 120 字符')
        if base_version is not None and (not isinstance(base_version, str) or len(base_version) > 100):
            raise ValueError('基准版本无效')
        with self.lock:
            if any(not j['done'] for j in self.items.values()):
                raise ValueError('已有任务运行中，请先完成审批或等待任务结束')
            if len(self.items) >= 50:
                del self.items[next(iter(self.items))]
            ident = uuid.uuid4().hex[:12]
            state = ProjectState(project_id=ident, idea=idea.strip(), requirements=[r.strip() for r in requirements])
            state.workspace_id = ident
            state.client_name = client_name.strip()
            if base_version:
                base_record = self.snapshot(base_version)
                base = ProjectState.model_validate(base_record['state'])
                if not base_record['done'] or not base.generated_files:
                    raise ValueError('基准任务必须已经结束且有生成源码')
                project = self.history.project(base.workspace_id or base_version)
                if project['current_version'] and project['current_version'] != base_version:
                    raise ValueError('请基于当前可用版本修改；如需旧版本，请先恢复该版本')
                from .security import validate_feature_files
                validate_feature_files(base.generated_files)
                from .revisions import verify_base_snapshot
                verify_base_snapshot(base, config.GENERATED_DIR)
                state.workspace_id = project['id']
                state.base_version = base_version
                state.expected_version = project['current_version']
                state.client_name = project['client']
                state.idea = base.idea
                state.requirements = list(dict.fromkeys(base.requirements + state.requirements))
                if len(state.requirements) > 100:
                    raise ValueError('累计要求超过 100 条，请精简新增要求')
                state.change_requests = base.change_requests + [idea.strip()]
                if sum(map(len, state.change_requests)) > 60000:
                    raise ValueError('累计修改要求超过上下文上限，请人工整理项目需求')
                state.generated_files = base.generated_files
                state.extra_dependencies = base.extra_dependencies
            self.items[ident] = dict(state=state, logs=[], done=False, waiting=None, decision=None,
                                     event=threading.Event(), decisions=[], created_at=now_iso(), updated_at=now_iso())
            try:
                self._persist(ident)
            except Exception:
                del self.items[ident]
                raise
        threading.Thread(target=self._run, args=(ident,), daemon=True).start()
        return ident

    def _run(self, ident):
        job = self.items[ident]

        def emit(message):
            with self.lock:
                job['logs'].append(str(message))
                self._persist(ident)

        def checkpoint(state):
            with self.lock:
                job['state'] = state
                self._persist(ident)

        def approve(stage, state):
            with self.lock:
                job['state'] = state
                job['decision'] = None
                job['event'].clear()
                job['waiting'] = stage
                self._persist(ident)
            signaled = job['event'].wait(1800)
            with self.lock:
                result = job['decision'] if signaled else (False, '审批等待超时')
                job['waiting'] = None
                return result

        try:
            extra = {'checkpoint': checkpoint} if 'checkpoint' in inspect.signature(self.execute).parameters else {}
            state = self.execute(job['state'], self.llm_factory(),
                                 approver=lambda s: approve('plan', s),
                                 preview_approver=lambda s: approve('preview', s), emit=emit, **extra)
            with self.lock:
                job['state'] = state
        except Exception as exc:
            with self.lock:
                job['state'].phase = ProjectPhase.FAILED
                job['state'].errors.append(str(exc))
        finally:
            with self.lock:
                job['waiting'] = None
                job['done'] = True
                try:
                    self._persist(ident)
                except (OSError, sqlite3.Error) as exc:
                    job['state'].errors.append('历史保存失败，请下载报告：' + str(exc))

    def decide(self, ident, stage, approved, feedback):
        if type(approved) is not bool or not isinstance(feedback, str) or len(feedback) > 5000:
            raise ValueError('审批数据格式错误')
        with self.lock:
            job = self.items[ident]
            if job['done'] or job['waiting'] != stage or job['decision'] is not None:
                raise ValueError('没有对应的待审批阶段，或已审批')
            job['decision'] = (approved, feedback or None)
            entry = dict(stage=stage, approved=approved, feedback=feedback, at=now_iso())
            job['decisions'].append(entry)
            try:
                self._persist(ident)
            except Exception:
                job['decision'] = None
                job['decisions'].pop()
                raise
            job['event'].set()

    def snapshot(self, ident):
        with self.lock:
            if ident not in self.items:
                return self.history.get(ident)
            j = self.items[ident]
            return redact(dict(id=ident, done=j['done'], waiting=j['waiting'], logs=list(j['logs']),
                        created_at=j['created_at'], updated_at=j['updated_at'], decisions=list(j['decisions']),
                        state=j['state'].model_dump(mode='json')))


def make_server(port=8765, jobs=None):
    jobs = jobs or Jobs(history_path=config.PROJECT_ROOT / '.factory' / 'history.sqlite3',
                        reports_dir=config.PROJECT_ROOT / '.factory' / 'runs')
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, status, data, mime='application/json; charset=utf-8'):
            raw = data if isinstance(data, bytes) else data.encode('utf-8') if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def local_request(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            return self.headers.get('Host') in allowed

        def do_GET(self):
            if not self.local_request():
                return self.reply(403, {'error': '仅允许本机访问'})
            if self.path == '/':
                html = Path(__file__).with_name('web_ui.html').read_text(encoding='utf-8').replace('__TOKEN__', token)
                return self.reply(200, html, 'text/html; charset=utf-8')
            # Public artwork only: never turn this into arbitrary filesystem serving.
            if self.path == '/assets/glacier.png':
                asset = Path(__file__).with_name('assets') / 'glacier.png'
                return self.reply(200, asset.read_bytes(), 'image/png')
            if self.headers.get('X-Factory-Token') != token:
                return self.reply(403, {'error': '会话无效，请刷新页面'})
            parsed = urlsplit(self.path)
            if parsed.path == '/api/jobs':
                try:
                    query = parse_qs(parsed.query)
                    return self.reply(200, jobs.listing(int(query.get('offset', ['0'])[0]), int(query.get('limit', ['30'])[0])))
                except (ValueError, sqlite3.Error) as exc:
                    return self.reply(400, {'error': str(exc)})
            if parsed.path == '/api/projects':
                return self.reply(200, jobs.history.projects())
            if parsed.path.startswith('/api/projects/'):
                try:
                    return self.reply(200, jobs.history.project(parsed.path.split('/')[-1]))
                except KeyError:
                    return self.reply(404, {'error': '项目不存在'})
            if self.path.startswith('/api/jobs/') and self.path.endswith('/changes'):
                try:
                    return self.reply(200, jobs.history.changes(self.path.split('/')[3]))
                except KeyError:
                    return self.reply(404, {'error': '任务不存在'})
            if self.path.startswith('/api/jobs/') and self.path.endswith('/preview'):
                return self.reply(200, jobs.previews.snapshot(self.path.split('/')[3]))
            if self.path.startswith('/api/jobs/'):
                try:
                    return self.reply(200, jobs.snapshot(self.path.split('/')[-1]))
                except KeyError:
                    return self.reply(404, {'error': '任务不存在，请从本地任务历史重新选择'})
            return self.reply(404, {'error': 'not found'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            if not self.local_request() or self.headers.get('X-Factory-Token') != token or (origin and origin not in allowed):
                return self.reply(403, {'error': '请求来源或会话无效'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_BODY:
                    return self.reply(413, {'error': '请求过大或为空'})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('请求必须是 JSON 对象')
                if self.path == '/api/jobs':
                    if not config.get_api_key():
                        return self.reply(400, {'error': '请先在本地 .env 配置模型 API 凭据并重启服务；不要将密钥填入需求框'})
                    ident = jobs.start(data.get('idea'), data.get('requirements', []), base_version=data.get('base_version'), client_name=data.get('client_name', ''))
                    return self.reply(202, {'id': ident})
                if self.path.startswith('/api/projects/') and self.path.endswith('/restore'):
                    with jobs.lock:
                        return self.reply(200, jobs.history.restore_version(self.path.split('/')[3], data.get('version')))
                if self.path.startswith('/api/jobs/') and self.path.endswith('/decision'):
                    jobs.decide(self.path.split('/')[3], data.get('stage'), data.get('approved'), data.get('feedback', ''))
                    return self.reply(200, {'ok': True})
                if self.path.startswith('/api/jobs/') and self.path.endswith('/preview'):
                    ident = self.path.split('/')[3]
                    if data.get('action') == 'stop':
                        return self.reply(200, jobs.previews.stop(ident))
                    if data.get('action') != 'start':
                        raise ValueError('预览操作无效')
                    return self.reply(202, jobs.previews.start(jobs.snapshot(ident)))
                return self.reply(404, {'error': 'not found'})
            except (ValueError, KeyError, UnicodeError) as exc:
                return self.reply(400, {'error': str(exc)})
            except (OSError, sqlite3.Error):
                return self.reply(503, {'error': '本地历史存储不可用，请检查磁盘空间与文件权限；任务未能保存'})

    class LocalServer(ThreadingHTTPServer):
        # Windows SO_REUSEADDR permits two processes to bind the same local port.
        allow_reuse_address = False if __import__('os').name == 'nt' else True

        def server_close(self):
            jobs.previews.stop()
            super().server_close()

    return LocalServer(('127.0.0.1', port), Handler)


def main(argv=None):
    from dotenv import load_dotenv
    parser = argparse.ArgumentParser(description='AI Factory 本地网页工作台')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    load_dotenv(config.PROJECT_ROOT / '.env')
    server = make_server(args.port)
    print(f'AI Factory: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
