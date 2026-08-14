"""把 Plan 阶段产物落盘（ARCHITECTURE §7.1 路径约定）。

- spec         → wiki/specs/{project}.md
- architecture → wiki/decisions/{project}-architecture.md  （按项目命名，绝不覆盖仓库自身的 ARCHITECTURE.md）
- dag          → tasks.json
draft=True 时文件名加 .draft 后缀，避免把未审批的内容当成正式产物。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from . import config
from .schemas import Architecture, Dag, ProductSpec
from .state import ProjectState
from .util import safe_path_component


def write_outputs(state: ProjectState, *, draft: bool = False) -> Dict[str, Path]:
    if state.product_spec is None or state.architecture is None or state.dag is None:
        raise ValueError("write_outputs: state 缺少 spec / architecture / dag")

    project = state.product_spec.project_name or state.project_id
    project_file = safe_path_component(project, fallback=state.project_id)
    suffix = ".draft" if draft else ""
    status = "DRAFT（未审批）" if draft else "APPROVED"

    config.WIKI_SPECS_DIR.mkdir(parents=True, exist_ok=True)
    config.WIKI_DECISIONS_DIR.mkdir(parents=True, exist_ok=True)

    spec_path = config.WIKI_SPECS_DIR / f"{project_file}{suffix}.md"
    arch_path = config.WIKI_DECISIONS_DIR / f"{project_file}-architecture{suffix}.md"
    dag_path = (
        config.TASKS_JSON
        if not draft
        else config.PROJECT_ROOT / "tasks.draft.json"
    )

    spec_path.write_text(_render_spec_md(state.product_spec, status), encoding="utf-8")
    arch_path.write_text(_render_arch_md(state.architecture, project, status), encoding="utf-8")
    dag_path.write_text(_render_dag_json(state.dag), encoding="utf-8")

    return {"spec": spec_path, "architecture": arch_path, "dag": dag_path}


def _render_spec_md(spec: ProductSpec, status: str) -> str:
    lines = [
        f"# {spec.project_name} — Product Spec",
        "",
        f"> 一句话: {spec.one_liner}",
        f"> 状态: {status}",
        "",
        "## 目标用户",
        "",
        spec.target_users,
        "",
        "## 核心功能",
        "",
        *[f"- {f}" for f in spec.core_features],
        "",
        "## MVP 边界",
        "",
        "### 做",
        "",
        *[f"- {x}" for x in spec.mvp_in_scope],
        "",
        "### 不做",
        "",
        *[f"- {x}" for x in spec.mvp_out_of_scope],
        "",
        "## 用户故事",
        "",
        *[f"- 作为 {s.as_a}，我想 {s.i_want}，以便 {s.so_that}" for s in spec.user_stories],
        "",
        "## 成功指标",
        "",
        *[f"- {m}" for m in spec.success_metrics],
        "",
        "## 风险",
        "",
        *[f"- {r}" for r in spec.risks],
        "",
    ]
    return "\n".join(lines)


def _render_arch_md(arch: Architecture, project: str, status: str) -> str:
    lines = [
        f"# {project} — Architecture",
        "",
        f"> 状态: {status}",
        "",
        "## 技术栈",
        "",
        *[f"- **{k}**: {v}" for k, v in arch.stack.items()],
        "",
        "## 数据模型",
        "",
        arch.data_model,
        "",
        "## API 设计",
        "",
        *[f"- `{e.method} {e.path}` — {e.purpose}" for e in arch.api_design],
        "",
        f"## 部署目标",
        "",
        arch.deploy_target,
        "",
        "## 架构决策记录 (ADR)",
        "",
    ]
    for adr in arch.adrs:
        lines += [f"### {adr.title}", "", f"- 决定: {adr.decision}", f"- 理由: {adr.rationale}", ""]
    return "\n".join(lines)


def _render_dag_json(dag: Dag) -> str:
    return dag.model_dump_json(indent=2)
