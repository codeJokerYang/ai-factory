"""脚本化 preview：启动 dev server、等待就绪、（可选）截图。

dev_server 是上下文管理器，进出即起停 `npm run dev`。screenshot 用 playwright（懒加载）；
未安装时优雅跳过并返回 False（不强制 100MB 浏览器依赖）。截图前注入 alert/confirm/prompt 屏蔽，
双保险应对生成 app 里残留的阻塞弹窗（源头已在 Builder prompt 禁止）。
"""
from __future__ import annotations

import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Tuple

from .verify import _npm_args


def wait_until_ready(url: str, timeout: int = 120, interval: float = 1.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


@contextmanager
def dev_server(app_dir, port: int = 3000, ready_timeout: int = 120) -> Iterator[Tuple[str, bool]]:
    """启动 `npm run dev -- -p <port>`，yield (url, ready)，退出时停服。"""
    app_dir = Path(app_dir)
    url = f"http://localhost:{port}"
    proc = subprocess.Popen(
        _npm_args(["run", "dev", "--", "-p", str(port)]),
        cwd=str(app_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = wait_until_ready(url, ready_timeout)
        yield url, ready
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


def screenshot(url: str, out_path, width: int = 1280, height: int = 900) -> bool:
    """用 playwright 截图，未安装则返回 False。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        # 双保险：屏蔽阻塞弹窗
        page.add_init_script(
            "window.alert=()=>{};window.confirm=()=>true;window.prompt=()=>null;"
        )
        page.goto(url, wait_until="networkidle")
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()
    return True
