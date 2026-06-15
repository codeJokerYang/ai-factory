"""Planner Agent — Idea → Product Spec (FR-1.2)。"""
from __future__ import annotations

from ..config import PLANNER_MODEL
from ..prompts.planner import SYSTEM, build_prompt
from ..schemas import ProductSpec
from ..state import ProjectPhase, ProjectState
from ..util import extract_json
from .base import Agent


class Planner(Agent):
    name = "planner"
    model = PLANNER_MODEL

    def run(self, state: ProjectState) -> ProjectState:
        state.phase = ProjectPhase.PLANNING
        raw = self.llm.complete(model=self.model, system=SYSTEM, prompt=build_prompt(state.idea))
        try:
            state.product_spec = ProductSpec(**extract_json(raw))
        except Exception as exc:  # noqa: BLE001 - 记录并优雅失败
            state.errors.append(f"planner: {exc}")
            state.phase = ProjectPhase.FAILED
        return state
