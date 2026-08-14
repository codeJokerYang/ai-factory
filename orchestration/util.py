"""Small helpers shared across agents."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


_WINDOWS_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def extract_json(text: str) -> dict[str, Any]:
    """从 LLM 响应里抽出第一个 JSON 对象，容忍 ```json 代码块和前后噪音。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def normalize_relative_path(value: str) -> str:
    """Validate an untrusted repository-relative path and return POSIX form.

    Builder output comes from an LLM, so paths are data rather than trusted code.
    Absolute paths, drive-qualified paths and parent traversal are rejected before
    any file is written.
    """
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("file path must be a non-empty string")
    raw = value.strip().replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"absolute file path is not allowed: {value}")
    if any(part == ".." for part in raw.split("/")):
        raise ValueError(f"parent traversal is not allowed: {value}")
    normalized = PurePosixPath(raw).as_posix()
    if normalized in ("", "."):
        raise ValueError("file path must identify a file")
    return normalized


def resolve_within(root: Path, relative: str) -> Path:
    """Resolve *relative* below *root*, including protection from symlink escape."""
    normalized = normalize_relative_path(relative)
    root = Path(root).resolve()
    resolved = (root / Path(normalized)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"file path escapes output root: {relative}") from exc
    return resolved


def safe_path_component(value: str, *, fallback: str = "project", max_length: int = 80) -> str:
    """Convert an untrusted display name into a portable single path component."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text).strip(" .-")
    text = text[:max_length].rstrip(" .-")
    if not text or text.casefold() in _WINDOWS_RESERVED:
        text = fallback
    return text


def npm_package_name(value: str) -> str:
    """Return a deterministic npm-compatible package name for a display name."""
    ascii_name = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    package = re.sub(r"[^a-z0-9._-]+", "-", ascii_name.lower()).strip("._-")
    package = re.sub(r"-+", "-", package)[:214].rstrip("._-")
    if not package or package in {"node_modules", "favicon.ico"}:
        return "ai-generated-app"
    return package
