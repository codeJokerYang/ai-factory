"""生成 UI 的确定性静态审计。

它不尝试替代浏览器视觉审查，只捕获可从 TSX 稳定判断的语义、响应式和无障碍回退。
所有发现均为 advisory，不增加 LLM 调用，也不单独阻断构建。
"""
from __future__ import annotations

import re
from typing import Literal, Sequence

from .schemas import GeneratedFile, UIQualityFinding, UIQualityReport

_RESPONSIVE_CLASS = re.compile(r"(?:^|[\s\"'`])(?:sm|md|lg|xl|2xl):")
_INTERACTIVE = re.compile(r"<(?:button|a|input|select|textarea|Link)\b", re.IGNORECASE)
_CLICKABLE_STATIC = re.compile(
    r"<(?:div|span)\b[^>]*\bonClick\s*=", re.IGNORECASE | re.DOTALL
)
_IMAGE = re.compile(r"<(?:img|Image)\b[^>]*>", re.IGNORECASE | re.DOTALL)
_FORM_CONTROL = re.compile(r"<(?:input|select|textarea)\b", re.IGNORECASE)
_FOCUS_STYLE = re.compile(r"focus-visible:|ui-button(?:-primary|-secondary)?|ui-field")


def _finding(
    code: str,
    message: str,
    *,
    file: str = "app/page.tsx",
    severity: Literal["low", "medium"] = "medium",
) -> UIQualityFinding:
    return UIQualityFinding(severity=severity, code=code, file=file, message=message)


def audit_ui_quality(files: Sequence[GeneratedFile] | None) -> UIQualityReport:
    """检查主页面和组件的最小 UI 基线；输入缺失时返回结构化结果而非抛异常。"""
    files = list(files or [])
    page = next((item for item in files if item.path == "app/page.tsx"), None)
    if page is None:
        return UIQualityReport(
            passed=False,
            findings=[_finding("missing-page", "缺少可审计的 app/page.tsx")],
        )

    findings = []
    page_source = page.content
    if not re.search(r"<main\b", page_source, re.IGNORECASE):
        findings.append(_finding("missing-main", "主页面应使用 <main> 表达主要内容区域"))
    if not re.search(r"<h1\b", page_source, re.IGNORECASE):
        findings.append(_finding("missing-h1", "主页面缺少清晰的一级标题层级"))

    combined = "\n".join(item.content for item in files if item.path.endswith((".tsx", ".jsx")))
    if not _RESPONSIVE_CLASS.search(combined):
        findings.append(_finding("missing-responsive", "未发现 sm/md/lg/xl 响应式断点"))
    removes_outline = re.search(r"(?:focus:)?outline-none", combined) is not None
    if _INTERACTIVE.search(combined) and removes_outline and not _FOCUS_STYLE.search(combined):
        findings.append(
            _finding(
                "focus-visible",
                "交互控件缺少可见键盘焦点样式",
                severity="low",
            )
        )
    if _CLICKABLE_STATIC.search(combined):
        findings.append(
            _finding(
                "clickable-static",
                "不要用带 onClick 的 div/span 代替 button 或 link",
            )
        )
    if any("alt=" not in tag and "alt =" not in tag for tag in _IMAGE.findall(combined)):
        findings.append(_finding("image-alt", "图片必须提供 alt 文本，装饰图使用空 alt"))
    if _FORM_CONTROL.search(combined) and not re.search(
        r"<label\b|aria-label\s*=|aria-labelledby\s*=", combined, re.IGNORECASE
    ):
        findings.append(_finding("form-label", "表单控件需要可感知的 label 或 aria-label"))

    return UIQualityReport(passed=not findings, findings=findings)
