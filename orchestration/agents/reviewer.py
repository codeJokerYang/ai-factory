"""Reviewer Agent — Gate 2 前的自动代码审查（FR-2.5）。

v1 是 **advisory（建议性）**：产出 CodeReview 并把 high 问题写入 warnings，由 Gate 2 人工决策
（对应宪法的"连续否决 → 升级到 Human Gate 2"）。审查本身的失败不阻塞构建。
"""
from __future__ import annotations

from ..config import REVIEWER_MODEL
from ..prompts.reviewer import SYSTEM, build_prompt
from ..schemas import CodeReview
from ..state import ProjectPhase, ProjectState
from ..util import extract_json
from .base import Agent


class Reviewer(Agent):
    name = "reviewer"
    model = REVIEWER_MODEL

    def run(self, state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        if not state.generated_files:
            state.warnings.append("reviewer: 没有可审查的代码，跳过")
            return state

        spec_json = state.product_spec.model_dump_json(indent=2) if state.product_spec else "{}"
        arch_json = state.architecture.model_dump_json(indent=2) if state.architecture else "{}"
        files = [{"path": f.path, "content": f.content} for f in state.generated_files]
        raw = self.llm.complete(
            model=self.model, system=SYSTEM, prompt=build_prompt(spec_json, arch_json, files)
        )
        try:
            state.code_review = CodeReview(**extract_json(raw))
        except Exception as exc:  # noqa: BLE001 - advisory：审查解析失败不阻塞
            state.warnings.append(f"reviewer: 审查解析失败，已跳过（{exc}）")
        return state
