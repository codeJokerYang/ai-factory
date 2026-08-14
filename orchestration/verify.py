"""自动构建门（Tester-for-output 雏形）。

在生成的 Next.js app 目录里跑 `npm install` + `npm run build`，捕获通过/失败 + 编译错误尾部。
这是确定性的规则引擎检查（能不用 LLM 就不用）——能逮住编译/类型错误，
例如脚手架 tsconfig 漏配 target 导致的 `[...new Set()]` 类型报错。
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class VerifyResult:
    passed: bool
    step: str  # "install" | "build" | "ok"
    log: str  # 失败时为错误尾部；通过时为简短摘要


def _npm_args(sub: List[str]) -> List[str]:
    # Windows 上 npm 是 npm.cmd（批处理），需经 cmd /c 执行；其他平台直接调用。
    if os.name == "nt":
        return ["cmd", "/c", "npm", *sub]
    return ["npm", *sub]


def _tail(text: str, n: int) -> str:
    lines = (text or "").strip().splitlines()
    return "\n".join(lines[-n:])


def _run(sub: List[str], cwd: Path, timeout: int):
    try:
        proc = subprocess.run(
            _npm_args(sub),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        output = _exception_output(exc)
        return 124, f"命令执行超时（{timeout} 秒）\n{output}".rstrip()
    except OSError as exc:
        return 127, f"无法启动 npm 命令: {exc}"


def _exception_output(exc: subprocess.TimeoutExpired) -> str:
    chunks = []
    for value in (exc.stdout, exc.stderr):
        if isinstance(value, bytes):
            chunks.append(value.decode(errors="replace"))
        elif value:
            chunks.append(value)
    return "".join(chunks)


def verify_app(
    app_dir,
    *,
    install: bool = True,
    tail_lines: int = 40,
    timeout: int = 600,
) -> VerifyResult:
    """在 app_dir 跑 install + build。任何一步失败即 passed=False，log 为错误尾部。"""
    app_dir = Path(app_dir)
    if not (app_dir / "package.json").exists():
        return VerifyResult(False, "install", f"package.json 不存在: {app_dir}")

    if install:
        code, out = _run(["install", "--no-audit", "--no-fund"], app_dir, timeout)
        if code != 0:
            return VerifyResult(False, "install", _tail(out, tail_lines))

    code, out = _run(["run", "build"], app_dir, timeout)
    if code != 0:
        return VerifyResult(False, "build", _tail(out, tail_lines))

    return VerifyResult(True, "ok", _tail(out, 10))
