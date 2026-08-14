"""Orchestration 替换点（the swap seam）。

`Step` 是每个流水线阶段满足的契约：吃一个 ProjectState，吐一个更新后的 ProjectState。
Agent 和 Gate 都满足它。SequentialRunner 是**唯一**知道执行顺序的地方 —— 将来换成
LangGraphRunner 时，agent 与 schema 完全不动。

    v1:  SequentialRunner([planner.run, architect.run, decomposer.run, gate_1]).run(state)
    v2:  LangGraphRunner(graph).run(state)        # agents 原样复用
"""
from __future__ import annotations

import os
from typing import Callable, List, Optional

from .state import ProjectPhase, ProjectState

Step = Callable[[ProjectState], ProjectState]

# 这些 phase 一旦出现就停止后续步骤（失败/被拒绝）。
_TERMINAL = {
    ProjectPhase.FAILED,
    ProjectPhase.PLAN_REJECTED,
    ProjectPhase.GATE_2_REJECTED,
}


def run_step_safely(step: Step, state: ProjectState) -> ProjectState:
    """Run one pipeline step without allowing provider or plugin failures to crash the CLI."""
    name = getattr(step, "__qualname__", getattr(step, "__name__", step.__class__.__name__))
    try:
        result = step(state)
    except Exception as exc:  # provider/network/plugin boundary; KeyboardInterrupt still propagates
        state.errors.append(f"runner[{name}]: {type(exc).__name__}: {exc}")
        state.phase = ProjectPhase.FAILED
        return state
    if not isinstance(result, ProjectState):
        state.errors.append(
            f"runner[{name}]: invalid result {type(result).__name__}; expected ProjectState"
        )
        state.phase = ProjectPhase.FAILED
        return state
    return result


class SequentialRunner:
    def __init__(self, steps: List[Step]):
        self.steps = steps

    def run(self, state: ProjectState) -> ProjectState:
        for step in self.steps:
            state = run_step_safely(step, state)
            if state.phase in _TERMINAL:
                break
        return state


def make_runner(steps: List[Step], runner: Optional[str] = None):
    """选择编排引擎（默认 sequential）；FACTORY_RUNNER=langgraph 切到状态机。

    这是 v1 设计的**唯一切换点** —— agent / schema 完全不变。
    """
    name = (runner or os.environ.get("FACTORY_RUNNER", "sequential")).lower()
    if name == "langgraph":
        from .lang_runner import LangGraphRunner

        return LangGraphRunner(steps)
    return SequentialRunner(steps)
