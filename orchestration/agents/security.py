"""Security Agent — 规则先行 + 高危再 LLM（FR-2.4 / 宪法 5.2，一票否决）。

零 token 路径：规则扫描无 high/critical → LLM 完全不介入。
"""
from __future__ import annotations

from ..config import SECURITY_MODEL
from ..prompts.security import SYSTEM, build_prompt
from ..schemas import SecurityReport
from ..security import is_blocking, max_severity, scan_files
from ..state import ProjectPhase, ProjectState
from .base import Agent


class SecurityAgent(Agent):
    name = "security"
    model = SECURITY_MODEL

    def run(self, state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        if not state.generated_files:
            return state

        files = [(f.path, f.content) for f in state.generated_files]
        findings = scan_files(files)
        blocking = is_blocking(findings)

        summary = ""
        if blocking:  # 仅高危时调 LLM（零 token 路径：无高危不调）
            high = [f for f in findings if f.severity in ("high", "critical")]
            try:
                summary = self.llm.complete(
                    model=self.model, system=SYSTEM, prompt=build_prompt(high, files)
                ).strip()
            except Exception:  # noqa: BLE001 - LLM 失败不影响规则判定（veto 仍生效）
                summary = ""

        state.security_report = SecurityReport(
            passed=not blocking,
            risk_level=max_severity(findings),
            findings=findings,
            summary=summary,
        )
        return state
