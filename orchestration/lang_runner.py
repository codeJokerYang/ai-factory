"""LangGraphRunner — 把同一组 Step 编排成 LangGraph 状态机（drop-in 替换 SequentialRunner）。

兑现 v1 的"替换点"承诺：**agent 与 schema 完全不动**。单通道设计——图状态仅含一个
ProjectState，每个节点整体替换它，于是任意 `Step` 无需改写即可作为节点。
终止 phase 经**条件边**短路到 END（条件路由）；可选 checkpointer 支持**断点续跑**（thread_id）。
并行 DAG 执行（Builder 层）由此解锁，留待执行层接入。
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from .runner import Step
from .state import ProjectPhase, ProjectState

_TERMINAL = {
    ProjectPhase.FAILED,
    ProjectPhase.PLAN_REJECTED,
    ProjectPhase.GATE_2_REJECTED,
}


class _GraphState(TypedDict):
    state: ProjectState


class LangGraphRunner:
    def __init__(self, steps: List[Step], checkpointer=None):
        self.steps = steps
        self.checkpointer = checkpointer

    def _compile(self):
        from langgraph.graph import END, START, StateGraph

        g = StateGraph(_GraphState)
        names = [f"step_{i}" for i in range(len(self.steps))]

        def make_node(step: Step):
            def node(gs: _GraphState) -> dict:
                return {"state": step(gs["state"])}

            return node

        for name, step in zip(names, self.steps):
            g.add_node(name, make_node(step))

        g.add_edge(START, names[0])
        for i, name in enumerate(names):
            if i + 1 >= len(names):
                g.add_edge(name, END)
                continue
            nxt = names[i + 1]

            def router(gs: _GraphState, _nxt=nxt):
                return END if gs["state"].phase in _TERMINAL else _nxt

            g.add_conditional_edges(name, router, {nxt: nxt, END: END})
        return g.compile(checkpointer=self.checkpointer)

    def run(self, state: ProjectState, thread_id: str = "default") -> ProjectState:
        graph = self._compile()
        config = {"configurable": {"thread_id": thread_id}} if self.checkpointer else {}
        out = graph.invoke({"state": state}, config=config)
        result = out["state"]
        if isinstance(result, dict):  # checkpointer 可能把 pydantic 存成 dict
            result = ProjectState(**result)
        return result
