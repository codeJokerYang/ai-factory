"""Builder Agent — Spec + Architecture → 可运行 Next.js app 的特性文件（Week 3 v1）。

whole-project 一次性生成；mock 数据，无外部服务。脚手架由 scaffold.py 负责。
"""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..cache_metrics import make_cache_lookup
from ..config import ALLOWED_EXTRA_DEPS, BUILDER_MAX_TOKENS, BUILDER_MODEL
from ..knowledge_cache import match_knowledge_cases, render_knowledge_context
from ..prompts.builder import SYSTEM, build_prompt, repair_prompt, revise_prompt
from ..schemas import GeneratedFile
from ..state import ProjectPhase, ProjectState
from ..template_cache import match_templates, render_template_context
from ..ui_quality import audit_ui_quality
from ..util import extract_json
from .base import Agent


def _parse_output(raw: str):
    """解析 LLM 响应 → (files, deps, dropped)。

    缺 app/page.tsx 视为错误；dependencies 按白名单过滤并固定版本，白名单外的记入 dropped。
    """
    data = extract_json(raw)
    files = [GeneratedFile(**f) for f in data.get("files", [])]
    if not any(f.path.replace("\\", "/") == "app/page.tsx" for f in files):
        raise ValueError("未生成 app/page.tsx")
    deps, dropped = {}, []
    for name in data.get("dependencies") or {}:
        if name in ALLOWED_EXTRA_DEPS:
            deps[name] = ALLOWED_EXTRA_DEPS[name]  # 固定版本，忽略 LLM 给的
        else:
            dropped.append(name)
    return files, deps, dropped


def _record_ui_quality(state: ProjectState, files) -> None:
    """刷新 UI 审计与对应 warning，避免 repair/revise 后保留过期发现。"""
    state.warnings = [warning for warning in state.warnings if not warning.startswith("ui-quality[")]
    state.ui_quality = audit_ui_quality(files)
    for finding in state.ui_quality.findings:
        state.warnings.append(
            f"ui-quality[{finding.severity}] {finding.file}: {finding.code} — {finding.message}"
        )


class Builder(Agent):
    name = "builder"
    model = BUILDER_MODEL

    def __init__(self, llm, *, knowledge_dir: Path | None = None):
        super().__init__(llm)
        self.knowledge_dir = knowledge_dir or config.KNOWLEDGE_CACHE_DIR

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
        template_matches = match_templates(state.product_spec)
        template_context = render_template_context(template_matches)
        knowledge_matches = []
        knowledge_context = ""
        if not template_context:  # COST_OPTIMIZATION §7.2：L2 未命中才回退到 L3。
            knowledge_matches = match_knowledge_cases(state.product_spec, self.knowledge_dir)
            knowledge_context = render_knowledge_context(knowledge_matches)
        state.cache_lookup = make_cache_lookup(
            template_matches=template_matches,
            knowledge_matches=knowledge_matches,
            context=template_context or knowledge_context,
        )
        raw = self.llm.complete(
            model=self.model,
            system=SYSTEM,
            prompt=build_prompt(spec_json, arch_json, template_context, knowledge_context),
            max_tokens=BUILDER_MAX_TOKENS,
        )
        try:
            files, deps, dropped = _parse_output(raw)
            state.generated_files = files
            state.extra_dependencies = deps
            _record_ui_quality(state, files)
            for name in dropped:
                state.warnings.append(f"builder: 依赖 {name} 不在白名单，已忽略")
            state.phase = ProjectPhase.BUILD_DONE
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"builder: {exc}")
            state.phase = ProjectPhase.FAILED
        return state

    def repair(self, state: ProjectState, error_log: str) -> ProjectState:
        """构建门失败后自愈：把编译器报错 + 当前文件回灌，生成修正后的完整文件集。"""
        current = [{"path": f.path, "content": f.content} for f in state.generated_files]
        raw = self.llm.complete(
            model=self.model,
            system=SYSTEM,
            prompt=repair_prompt(error_log, current),
            max_tokens=BUILDER_MAX_TOKENS,
        )
        try:
            files, deps, dropped = _parse_output(raw)
            state.generated_files = files
            state.extra_dependencies = {**state.extra_dependencies, **deps}  # 保留原有依赖
            _record_ui_quality(state, files)
            for name in dropped:
                state.warnings.append(f"builder.repair: 依赖 {name} 不在白名单，已忽略")
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"builder.repair: {exc}")
            state.phase = ProjectPhase.FAILED
        return state

    def revise(self, state: ProjectState, review_feedback: str) -> ProjectState:
        """按 Reviewer 审查意见修订代码（FR-2.5 veto → fix）。"""
        current = [{"path": f.path, "content": f.content} for f in state.generated_files]
        raw = self.llm.complete(
            model=self.model,
            system=SYSTEM,
            prompt=revise_prompt(review_feedback, current),
            max_tokens=BUILDER_MAX_TOKENS,
        )
        try:
            files, deps, dropped = _parse_output(raw)
            state.generated_files = files
            state.extra_dependencies = {**state.extra_dependencies, **deps}
            _record_ui_quality(state, files)
            for name in dropped:
                state.warnings.append(f"builder.revise: 依赖 {name} 不在白名单，已忽略")
        except Exception as exc:  # noqa: BLE001
            state.errors.append(f"builder.revise: {exc}")
            state.phase = ProjectPhase.FAILED
        return state
