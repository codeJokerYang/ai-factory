import builtins

from orchestration import preview
from orchestration.preview import screenshot, wait_until_ready


class _Resp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_wait_until_ready_ok(monkeypatch):
    monkeypatch.setattr(preview.urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert wait_until_ready("http://x", timeout=2) is True


def test_wait_until_ready_timeout(monkeypatch):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(preview.urllib.request, "urlopen", boom)
    monkeypatch.setattr(preview.time, "sleep", lambda *_: None)  # 不真等
    assert wait_until_ready("http://x", timeout=0.2, interval=0.01) is False


def test_screenshot_without_playwright(monkeypatch, tmp_path):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # 未安装 playwright 时应优雅返回 False，不抛异常
    assert screenshot("http://x", tmp_path / "s.png") is False
