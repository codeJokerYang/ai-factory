"""Local task archive. SQLite commits each checkpoint; credentials are never copied."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .state import ProjectState, ProjectPhase


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def redact(value):
    """Keep full task data, but remove known credentials even from provider errors."""
    secrets = [os.environ.get(key, '') for key in (
        'DEEPSEEK_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'OPENAI_API_KEY')]
    def clean(item):
        if isinstance(item, str):
            for secret in secrets:
                if len(secret) >= 8:
                    item = item.replace(secret, '[REDACTED]')
            item = re.sub(r'\bsk-[A-Za-z0-9_-]{16,}\b', '[REDACTED]', item)
            return re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._~-]{12,}', 'Bearer [REDACTED]', item)
        if isinstance(item, list):
            return [clean(x) for x in item]
        if isinstance(item, dict):
            return {key: clean(val) for key, val in item.items()}
        return item
    return clean(value)


def status_of(record):
    phase = record['state']['phase']
    if phase == 'interrupted':
        return 'interrupted'
    if not record['done']:
        return 'waiting_' + record['waiting'] if record['waiting'] else 'running'
    if phase == 'failed':
        return 'failed'
    if phase.endswith('rejected'):
        return 'rejected'
    return 'accepted' if record['state'].get('gate_2_approved') else 'completed'


class History:
    def __init__(self, path=None):
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path) if path else ':memory:', check_same_thread=False)
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, created TEXT NOT NULL, updated TEXT NOT NULL,
            title TEXT NOT NULL, status TEXT NOT NULL, document TEXT NOT NULL)''')
        self.db.commit()
        self.warnings = []
        # Only unfinished records become interrupted. Never replay an approval.
        with self.lock:
            rows = self.db.execute("SELECT document FROM tasks WHERE status IN ('running','waiting_plan','waiting_preview')").fetchall()
            for (raw,) in rows:
                record = json.loads(raw)
                record.update(done=True, waiting=None)
                record['state'].update(phase='interrupted', preview_url=None, preview_ready=False)
                record['state']['errors'].append('服务已停止，任务中断；历史记录保留，执行不会自动恢复。')
                record['updated_at'] = now_iso()
                self.save(record)

    def save(self, record):
        record = redact(record)
        state = record['state']
        title = (state.get('product_spec') or {}).get('project_name') or state['idea'].splitlines()[0]
        with self.lock, self.db:
            self.db.execute('''INSERT INTO tasks VALUES (?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET updated=excluded.updated,
                title=excluded.title, status=excluded.status, document=excluded.document''', (
                    record['id'], record['created_at'], record['updated_at'], title[:100],
                    status_of(record), json.dumps(record, ensure_ascii=False)))

    def get(self, ident):
        with self.lock:
            row = self.db.execute('SELECT document FROM tasks WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise KeyError('任务不存在')
        return redact(json.loads(row[0]))

    def listing(self, offset=0, limit=30):
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError('分页参数无效')
        with self.lock:
            rows = self.db.execute('SELECT id,created,updated,title,status FROM tasks ORDER BY created DESC,id DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
            total = self.db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        return dict(tasks=[dict(zip(('id','created_at','updated_at','title','status'), row)) for row in rows],
                    total=total, offset=offset, limit=limit, warnings=list(self.warnings))

    def import_reports(self, directory):
        """Best-effort import of pre-history reports; malformed files stay untouched."""
        for report in sorted(Path(directory).glob('*/report.json')):
            try:
                if report.is_symlink() or not report.resolve().is_relative_to(Path(directory).resolve()):
                    continue
                if report.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError('报告过大')
                state = ProjectState.model_validate_json(report.read_text(encoding='utf-8'))
                try:
                    self.get(state.project_id)
                    continue
                except KeyError:
                    pass
                if state.phase.value not in {'failed', 'plan_rejected', 'gate_2_rejected', 'gate_2_approved', 'build_done', 'build_verified'}:
                    state.phase = ProjectPhase.INTERRUPTED
                    state.errors.append('从旧报告导入：无法恢复原执行，标记为已中断。')
                state.preview_url = None
                state.preview_ready = False
                stamp = datetime.fromtimestamp(report.stat().st_mtime, timezone.utc).isoformat()
                self.save(dict(id=state.project_id, created_at=stamp, updated_at=stamp,
                               done=True, waiting=None, logs=['从旧运行报告导入；日期为报告修改时间，早期日志可能缺失。'],
                               decisions=[], source='legacy_report', state=state.model_dump(mode='json')))
            except (ValueError, OSError) as exc:
                self.warnings.append(f'有旧报告无法导入（{report.parent.name}）：{type(exc).__name__}')

    def close(self):
        self.db.close()


class HistoryPreview:
    """One on-demand archived preview, with explicit stop and a 30-minute expiry."""
    def __init__(self, generated_root, factory=None):
        from .preview import dev_server
        self.root = Path(generated_root).resolve()
        self.factory = factory or dev_server
        self.lock = threading.RLock()
        self.current = None

    def start(self, record):
        state = record['state']
        if not record['done']:
            raise ValueError('任务仍在执行，请使用当前任务的预览审批入口')
        if not state.get('build_dir'):
            raise ValueError('此任务尚未生成应用代码')
        target = Path(state['build_dir']).resolve()
        if target == self.root or not target.is_relative_to(self.root):
            raise ValueError('应用目录不在项目 generated 目录内，禁止启动')
        if not target.is_dir():
            raise ValueError('生成目录已移动或删除，无法重新预览')
        if not state.get('build_passed') or not (state.get('security_report') or {}).get('passed'):
            raise ValueError('此任务尚未通过构建或安全检查，不能重新预览')
        manifest = target / 'package.json'
        if manifest.is_symlink():
            raise ValueError('应用配置不能是符号链接')
        try:
            scripts = json.loads(manifest.read_text(encoding='utf-8')).get('scripts', {})
        except (OSError, ValueError) as exc:
            raise ValueError('应用 package.json 缺失或无效') from exc
        if scripts.get('dev') != 'next dev' or 'predev' in scripts or 'postdev' in scripts:
            raise ValueError('应用启动脚本已改变，请在本地审查后运行')
        if not (target / 'node_modules' / 'next').is_dir():
            raise ValueError('应用依赖缺失，请在生成目录安装依赖后重试')
        with self.lock:
            if self.current and self.current['status'] in {'starting','ready','stopping'}:
                if self.current['id'] == record['id']:
                    return self.snapshot(record['id'])
                raise ValueError('另一个历史预览正在运行，请先停止它')
            item = dict(id=record['id'], status='starting', url=None, error=None, stop=threading.Event())
            self.current = item
            threading.Thread(target=self._run, args=(item, target), daemon=True).start()
        return self.snapshot(record['id'])

    def _run(self, item, target):
        try:
            with self.factory(target, ready_timeout=30) as (url, ready):
                if not ready:
                    raise ValueError('预览 30 秒内未就绪；请检查本地端口、依赖及生成应用的启动错误')
                with self.lock:
                    if not item['stop'].is_set():
                        item.update(status='ready', url=url)
                item['stop'].wait(1800)
            with self.lock:
                item.update(status='stopped', url=None)
        except Exception as exc:
            with self.lock:
                item.update(status='failed', url=None, error=redact(str(exc)))

    def snapshot(self, ident):
        with self.lock:
            if not self.current or self.current['id'] != ident:
                return dict(id=ident, status='stopped', url=None, error=None)
            return {key: value for key, value in self.current.items() if key != 'stop'}

    def stop(self, ident=None):
        with self.lock:
            if self.current and (ident is None or ident == self.current['id']):
                if self.current['status'] in {'starting','ready'}:
                    self.current.update(status='stopping', url=None)
                    self.current['stop'].set()
        return self.snapshot(ident)
