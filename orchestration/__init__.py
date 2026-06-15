"""One-Person Company AI Factory — v1 Plan pipeline.

v1 范围: Idea → Planner → Architect → Decomposer → Gate 1 → spec/architecture/tasks.json。
顺序执行（SequentialRunner），但 agent 无状态、schema 共享，未来可无改写换 LangGraph。
"""

__version__ = "0.1.0"
