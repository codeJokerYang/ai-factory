"""Decomposer Agent — Spec + Architecture → DAG (FR-1.5)，输出后做 DAG 校验。"""
from __future__ import annotations

from ..config import DECOMPOSER_MODEL
from ..dag_validator import DagValidationError, validate_dag
from ..prompts.decomposer import SYSTEM, build_prompt
from ..schemas import Dag
from ..state import ProjectPhase, ProjectState
from ..util import extract_json
from .base import Agent


class Decomposer(Agent):
    name = "decomposer"
    model = DECOMPOSER_MODEL

    def run(self, state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        if state.product_spec is None or state.architecture is None:
            state.errors.append("decomposer: 缺少 product_spec 或 architecture")
            state.phase = ProjectPhase.FAILED
            return state

        state.phase = ProjectPhase.DECOMPOSING
        spec_json = state.product_spec.model_dump_json(indent=2)
        arch_json = state.architecture.model_dump_json(indent=2)
        raw = self.llm.complete(
            model=self.model, system=SYSTEM, prompt=build_prompt(spec_json, arch_json)
        )
        try:
            dag = Dag(**extract_json(raw))
            validate_dag(dag)
            state.dag = dag
        except DagValidationError as exc:
            state.errors.append(f"decomposer: DAG 不合法: {exc}")
            state.phase = ProjectPhase.FAILED
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"decomposer: {exc}")
            state.phase = ProjectPhase.FAILED
        return state
