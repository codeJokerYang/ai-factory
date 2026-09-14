"""Long-lived projects and immutable completed revisions over the task archive.

All callers hold History.lock and use its transaction. No generated directory is
rewritten by promotion or rollback; those actions change only the selected version.
"""
import json


def accepted(record):
    state = record['state']
    from .business import business_passed
    if state.get('delivery_mode') and not business_passed(state):
        return False
    from .acceptance import AcceptanceReport
    try:
        report = AcceptanceReport.model_validate(state.get('acceptance_report'))
    except ValueError:
        return False
    expected = {f'R{i+1}' for i in range(len(state.get('requirements', [])))}
    files = {f['path']: f['content'] for f in state.get('generated_files', [])}
    if {c.id for c in report.checks} != expected or len(report.checks) != len(expected):
        return False
    if any(not c.evidence.strip() or c.file not in files or c.evidence not in files[c.file] for c in report.checks):
        return False
    return bool(record['done'] and state.get('phase') == 'gate_2_approved'
                and state.get('gate_2_approved') and state.get('build_passed')
                and report.passed and 'app/page.tsx' in files
                and all((state.get(k) or {}).get('passed') for k in ('security_report', 'code_review')))


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, client TEXT NOT NULL,
        current_version TEXT, created TEXT NOT NULL, updated TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS versions (
        id TEXT PRIMARY KEY, project TEXT NOT NULL, parent TEXT,
        ordinal INTEGER NOT NULL, UNIQUE(project, ordinal))''')
    db.execute('''CREATE TABLE IF NOT EXISTS project_events (
        id INTEGER PRIMARY KEY, project TEXT NOT NULL, action TEXT NOT NULL,
        previous TEXT, target TEXT NOT NULL, created TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS versions_project ON versions(project,ordinal)')
    # Additive, idempotent migration; original task documents remain unchanged.
    for (raw,) in db.execute('SELECT t.document FROM tasks t LEFT JOIN versions v ON t.id=v.id WHERE v.id IS NULL ORDER BY t.created,t.id').fetchall():
        sync(db, json.loads(raw), importing=True)


def sync(db, record, importing=False):
    state = record['state']
    project = state.get('workspace_id') or record['id']
    title = (state.get('product_spec') or {}).get('project_name') or state['idea'].splitlines()[0]
    db.execute('INSERT OR IGNORE INTO projects VALUES (?,?,?,?,?,?)',
               (project, title[:100], state.get('client_name', ''), None, record['created_at'], record['updated_at']))
    exists = db.execute('SELECT 1 FROM versions WHERE id=?', (record['id'],)).fetchone()
    if not exists:
        ordinal = db.execute('SELECT COALESCE(MAX(ordinal),0)+1 FROM versions WHERE project=?', (project,)).fetchone()[0]
        db.execute('INSERT INTO versions VALUES (?,?,?,?)', (record['id'], project, state.get('resumed_from') or state.get('base_version'), ordinal))
    db.execute('UPDATE projects SET updated=? WHERE id=?', (record['updated_at'], project))
    if accepted(record):
        # Never re-promote a previously committed version after a user rollback.
        promoted = db.execute("SELECT 1 FROM project_events WHERE target=? AND action='promote'", (record['id'],)).fetchone()
        current = db.execute('SELECT current_version FROM projects WHERE id=?', (project,)).fetchone()[0]
        if not promoted and current == state.get('expected_version'):
            db.execute('UPDATE projects SET current_version=?,title=? WHERE id=?', (record['id'], title[:100], project))
            db.execute('INSERT INTO project_events(project,action,previous,target,created) VALUES (?,?,?,?,?)',
                       (project, 'promote', current, record['id'], record['updated_at']))
