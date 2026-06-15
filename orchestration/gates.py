"""Gate 1 — Plan 阶段结束时的人工审批（AGENT_CONSTITUTION 第二条 / ARCHITECTURE FR-1.7）。

工厂作为 Step（state -> state）。审批函数可注入，方便测试（默认走 CLI input()）。
approver(state) -> (approved: bool, feedback: str | None)
"""
from __future__ import annotations

from typing import Callable, Optional, Tuple

from .runner import Step
from .state import ProjectPhase, ProjectState

Approver = Callable[[ProjectState], Tuple[bool, Optional[str]]]


def summarize(state: ProjectState) -> str:
    spec = state.product_spec
    arch = state.architecture
    dag = state.dag
    lines = ["", "=" * 60, "GATE 1 — Plan 审批", "=" * 60]
    if spec:
        lines += [
            f"项目: {spec.project_name}",
            f"一句话: {spec.one_liner}",
            f"MVP 做: {', '.join(spec.mvp_in_scope) or '—'}",
            f"MVP 不做: {', '.join(spec.mvp_out_of_scope) or '—'}",
        ]
    if arch:
        lines.append(f"技术栈: {arch.stack.get('frontend', '?')} / {arch.stack.get('database', '?')} / {arch.stack.get('deploy', '?')}")
    if dag:
        lines.append(f"DAG: {len(dag.nodes)} 个节点")
        for n in dag.nodes:
            dep = f" <- {', '.join(n.depends)}" if n.depends else ""
            lines.append(f"  [{n.risk.value:6}] {n.id} ({n.est_minutes}m){dep}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _cli_approver(state: ProjectState) -> Tuple[bool, Optional[str]]:
    print(summarize(state))
    answer = input("\n方向对不对？approve/reject [a/r]: ").strip().lower()
    if answer in ("a", "approve", "y", "yes"):
        return True, None
    feedback = input("反馈（可选，回车跳过）: ").strip()
    return False, feedback or None


def make_gate_1(approver: Optional[Approver] = None) -> Step:
    approver = approver or _cli_approver

    def gate_1(state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        state.phase = ProjectPhase.WAITING_GATE_1
        approved, feedback = approver(state)
        if approved:
            state.gate_1_approved = True
            state.phase = ProjectPhase.PLAN_APPROVED
        else:
            state.gate_1_feedback = feedback
            state.phase = ProjectPhase.PLAN_REJECTED
        return state

    return gate_1
