"""Architect Agent — Spec → Architecture (FR-1.4)。v1 使用固定栈。"""
from __future__ import annotations

from ..config import ARCHITECT_MODEL
from ..prompts.architect import SYSTEM, build_prompt
from ..schemas import Architecture
from ..state import ProjectPhase, ProjectState
from ..util import extract_json
from .base import Agent


class Architect(Agent):
    name = "architect"
    model = ARCHITECT_MODEL

    def run(self, state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        if state.product_spec is None:
            state.errors.append("architect: 缺少 product_spec")
            state.phase = ProjectPhase.FAILED
            return state

        state.phase = ProjectPhase.ARCHITECTING
        spec_json = state.product_spec.model_dump_json(indent=2)
        raw = self.llm.complete(model=self.model, system=SYSTEM, prompt=build_prompt(spec_json))
        try:
            state.architecture = Architecture(**extract_json(raw))
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"architect: {exc}")
            state.phase = ProjectPhase.FAILED
        return state
