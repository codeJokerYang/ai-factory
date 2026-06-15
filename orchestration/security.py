"""规则引擎安全扫描（0 token）—— 硬编码密钥 / 危险用法 / 前端密钥泄露。

能确定性发现的绝不用 LLM（COST_OPTIMIZATION §5）。LLM 仅在出现 high/critical 时由
SecurityAgent 再审（见 agents/security.py）。
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .schemas import SecurityFinding

_SEVERITY_ORDER = ["none", "low", "medium", "high", "critical"]

# (compiled pattern, kind, severity)
_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private-key", "critical"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-access-key", "high"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"), "jwt-token", "high"),
    (
        re.compile(
            r"""(?i)(api[_-]?key|secret|passwd|password|access[_-]?token|auth[_-]?token)\s*[:=]\s*['"][A-Za-z0-9_\-]{12,}['"]"""
        ),
        "hardcoded-secret",
        "high",
    ),
    (re.compile(r"child_process"), "child-process", "high"),
    (re.compile(r"dangerouslySetInnerHTML"), "xss-risk", "medium"),
    (re.compile(r"\beval\s*\("), "eval", "medium"),
    (re.compile(r"new\s+Function\s*\("), "dynamic-fn", "medium"),
]
_NEXT_PUBLIC_SECRET = re.compile(r"(?i)NEXT_PUBLIC_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE_KEY)")


def scan_files(files: List[Tuple[str, str]]) -> List[SecurityFinding]:
    """files = [(path, content), ...] → 规则命中的 findings。"""
    findings: List[SecurityFinding] = []
    for path, content in files:
        for pat, kind, sev in _PATTERNS:
            if pat.search(content):
                findings.append(
                    SecurityFinding(severity=sev, file=path, kind=kind, message=f"检测到 {kind}")
                )
        if _NEXT_PUBLIC_SECRET.search(content):
            findings.append(
                SecurityFinding(
                    severity="high",
                    file=path,
                    kind="client-secret-leak",
                    message="疑似密钥经 NEXT_PUBLIC_ 泄露到前端",
                )
            )
    return findings


def max_severity(findings: List[SecurityFinding]) -> str:
    level = "none"
    for f in findings:
        if _SEVERITY_ORDER.index(f.severity) > _SEVERITY_ORDER.index(level):
            level = f.severity
    return level


def is_blocking(findings: List[SecurityFinding]) -> bool:
    """high/critical 即触发一票否决。"""
    return any(f.severity in ("high", "critical") for f in findings)
