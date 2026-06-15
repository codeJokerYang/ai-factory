"""Gate 2 — Preview → Merge 的人工关卡（AGENT_CONSTITUTION 第二条 / ARCHITECTURE FR-2.8）。

工厂作为 Step（state -> state）。审批前展示构建摘要（生成清单 + 构建门结果 + preview/截图）。
审批函数可注入，方便测试（默认走 CLI input()）。
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from .runner import Step
from .state import ProjectPhase, ProjectState

Approver = Callable[[ProjectState], Tuple[bool, Optional[str]]]


def summarize_build(state: ProjectState) -> str:
    lines = ["", "=" * 60, "GATE 2 — Preview 审核", "=" * 60]
    if state.product_spec:
        lines.append(f"项目: {state.product_spec.project_name}")
    if state.build_passed is None:
        lines.append("构建门: 未运行")
    else:
        lines.append("构建门: ✅ 通过" if state.build_passed else "构建门: ❌ 未通过")
    if state.preview_url:
        lines.append(f"Preview: {state.preview_url}")
    if state.screenshot_path:
        lines.append(f"截图: {state.screenshot_path}")
    lines.append(f"生成清单（特性文件 {len(state.generated_files)}）:")
    for f in state.generated_files:
        n = len(f.content.splitlines())
        lines.append(f"  + {f.path} ({n} 行)")
    cr = state.code_review
    if cr is not None:
        lines.append(f"Reviewer: {'✅ 通过' if cr.passed else '❌ 有阻塞问题'} — {cr.summary}")
        for issue in cr.issues:
            lines.append(f"  [{issue.severity}] {issue.file}: {issue.message}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _cli_approver(state: ProjectState) -> Tuple[bool, Optional[str]]:
    print(summarize_build(state))
    answer = input("\nPreview 能不能合并？approve/reject [a/r]: ").strip().lower()
    if answer in ("a", "approve", "y", "yes"):
        return True, None
    feedback = input("反馈（可选，回车跳过）: ").strip()
    return False, feedback or None


def make_gate_2(approver: Optional[Approver] = None) -> Step:
    approver = approver or _cli_approver

    def gate_2(state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        state.phase = ProjectPhase.WAITING_GATE_2
        approved, feedback = approver(state)
        if approved:
            state.gate_2_approved = True
            state.phase = ProjectPhase.GATE_2_APPROVED
        else:
            state.gate_2_feedback = feedback
            state.phase = ProjectPhase.GATE_2_REJECTED
        return state

    return gate_2
