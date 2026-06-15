"""Builder Agent — Spec + Architecture → 可运行 Next.js app 的特性文件（Week 3 v1）。

whole-project 一次性生成；mock 数据，无外部服务。脚手架由 scaffold.py 负责。
"""
from __future__ import annotations

from ..config import BUILDER_MAX_TOKENS, BUILDER_MODEL
from ..prompts.builder import SYSTEM, build_prompt
from ..schemas import GeneratedFile
from ..state import ProjectPhase, ProjectState
from ..util import extract_json
from .base import Agent


class Builder(Agent):
    name = "builder"
    model = BUILDER_MODEL

    def run(self, state: ProjectState) -> ProjectState:
        if state.phase == ProjectPhase.FAILED:
            return state
        if state.product_spec is None or state.architecture is None:
            state.errors.append("builder: 缺少 product_spec 或 architecture")
            state.phase = ProjectPhase.FAILED
            return state

        state.phase = ProjectPhase.BUILDING
        spec_json = state.product_spec.model_dump_json(indent=2)
        arch_json = state.architecture.model_dump_json(indent=2)
        raw = self.llm.complete(
            model=self.model,
            system=SYSTEM,
            prompt=build_prompt(spec_json, arch_json),
            max_tokens=BUILDER_MAX_TOKENS,
        )
        try:
            data = extract_json(raw)
            files = [GeneratedFile(**f) for f in data.get("files", [])]
            if not any(f.path.replace("\\", "/") == "app/page.tsx" for f in files):
                raise ValueError("Builder 未生成 app/page.tsx")
            state.generated_files = files
            state.phase = ProjectPhase.BUILD_DONE
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"builder: {exc}")
            state.phase = ProjectPhase.FAILED
        return state
