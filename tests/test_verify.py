"""自动构建门测试：mock subprocess，覆盖通过 / build 失败 / install 失败 / 无 package.json。"""
import subprocess

from orchestration import verify
from orchestration.verify import verify_app


class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _pkg(tmp_path):
    (tmp_path / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    return tmp_path


def test_verify_pass(monkeypatch, tmp_path):
    _pkg(tmp_path)

    def fake_run(args, **kw):
        return _FakeProc(0, "Compiled successfully")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    res = verify_app(tmp_path)
    assert res.passed is True
    assert res.step == "ok"


def test_verify_build_fails(monkeypatch, tmp_path):
    _pkg(tmp_path)

    def fake_run(args, **kw):
        if "install" in args:
            return _FakeProc(0, "added 1 package")
        return _FakeProc(1, "", "Type error: Set spread needs ES2015\nFailed to compile.")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    res = verify_app(tmp_path)
    assert res.passed is False
    assert res.step == "build"
    assert "Failed to compile" in res.log


def test_verify_install_fails(monkeypatch, tmp_path):
    _pkg(tmp_path)

    def fake_run(args, **kw):
        return _FakeProc(1, "", "npm ERR! network timeout")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    res = verify_app(tmp_path)
    assert res.passed is False
    assert res.step == "install"
    assert "npm ERR!" in res.log


def test_verify_no_package_json(tmp_path):
    res = verify_app(tmp_path)  # 空目录
    assert res.passed is False
    assert res.step == "install"
    assert "package.json" in res.log


def test_verify_skip_install(monkeypatch, tmp_path):
    _pkg(tmp_path)
    seen = []

    def fake_run(args, **kw):
        seen.append(args)
        return _FakeProc(0, "ok")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    res = verify_app(tmp_path, install=False)
    assert res.passed is True
    # 只应跑 build，不跑 install
    assert all("install" not in a for a in seen)


def test_verify_reports_timeout_without_crashing(monkeypatch, tmp_path):
    _pkg(tmp_path)

    def fake_run(args, **kw):
        raise subprocess.TimeoutExpired(args, kw["timeout"], output="still building")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    res = verify_app(tmp_path, install=False, timeout=3)
    assert res.passed is False
    assert res.step == "build"
    assert "超时" in res.log
    assert "still building" in res.log


def test_verify_reports_missing_npm_without_crashing(monkeypatch, tmp_path):
    _pkg(tmp_path)

    def fake_run(args, **kw):
        raise FileNotFoundError("npm not found")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    res = verify_app(tmp_path, install=False)
    assert res.passed is False
    assert res.step == "build"
    assert "无法启动 npm" in res.log
