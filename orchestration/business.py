"""Run declarative acceptance scenarios in a real isolated browser context."""
import json
import os
import subprocess
import hashlib
import re
from pathlib import Path
from urllib.parse import urlsplit


def run_business_tests(url, cases, output):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port:
        raise ValueError('业务测试只允许明确的本地预览地址')
    if not cases or any(not any(s.action in ('text', 'value') for s in c.steps) for c in cases):
        return dict(passed=False, error='没有包含结果断言的业务测试', cases=[])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    spec = output / 'business-input.json'
    spec.write_text(json.dumps(dict(url=url, cases=[c.model_dump() for c in cases]), ensure_ascii=False), encoding='utf-8')
    script = Path(__file__).with_name('business-runner.cjs')
    command = [os.environ.get('FACTORY_NODE', 'node'), str(script), str(spec.resolve()), str(output.resolve())]
    proc = None
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                start_new_session=os.name != 'nt')
        stdout, stderr = proc.communicate(timeout=150)
        report = output / 'business-report.json'
        if not report.exists():
            return dict(passed=False, error='浏览器测试未生成报告：'+stderr.decode('utf-8', errors='replace')[-1500:], cases=[])
        data = json.loads(report.read_text(encoding='utf-8'))
        data['passed'] = bool(proc.returncode == 0 and data.get('passed') and len(data.get('cases', [])) == 2 * len(cases))
        for case in data.get('cases', []):
            name=case.get('screenshot')
            if name:
                if not re.fullmatch(r'case-\d+-(1440|390)\.png', name):
                    raise ValueError('业务截图路径无效')
                shot=output/name
                if shot.stat().st_size>8*1024*1024:
                    raise ValueError('业务截图超过 8 MiB')
                case['screenshot_sha256']=hashlib.sha256(shot.read_bytes()).hexdigest()
        return data
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return dict(passed=False, error='业务测试无法完成：'+str(exc), cases=[])
    finally:
        if proc is not None and proc.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=10)
            else:
                import signal
                os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate(timeout=10)


def business_passed(state):
    report = state.business_report if hasattr(state, 'business_report') else state.get('business_report')
    cases = state.business_cases if hasattr(state, 'business_cases') else state.get('business_cases', [])
    specs = [c.model_dump() if hasattr(c, 'model_dump') else c for c in cases]
    expected = sorted((c['name'], width, len(c['steps'])) for c in specs for width in (1440,390))
    actual = sorted((c.get('name',''), c.get('width',0), c.get('steps',0)) for c in (report or {}).get('cases',[]))
    return bool(expected and report and report.get('passed') and expected == actual and all(c.get('passed') for c in report['cases']))
