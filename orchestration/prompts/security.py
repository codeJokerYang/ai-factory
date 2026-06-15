"""Security system prompt — 仅在规则引擎扫出 high/critical 时调用（高危复审）。"""
from __future__ import annotations

MARKER = "[agent:security]"

SYSTEM = f"""{MARKER}
你是安全审计 Agent（Security），拥有一票否决权（宪法第五条 5.2，不可被 Reviewer 推翻，只有 Human 可 override）。
规则引擎已扫出下列高危项。请简要确认风险真实性、说明影响与修复方向（中文，3-5 句纯文本，不要 JSON）。"""


def build_prompt(findings: list, files: list) -> str:
    flist = "\n".join(f"- [{f.severity}] {f.file}: {f.kind} — {f.message}" for f in findings)
    blocks = "\n\n".join(f"### {p}\n{c}" for p, c in files)
    return f"高危发现:\n{flist}\n\n相关代码:\n{blocks}\n\n请给出安全评估。"
