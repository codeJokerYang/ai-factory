"""ProjectState — 在每个步骤之间显式传递的状态对象。

镜像 ARCHITECTURE.md §6.1.1，裁剪到 v1 Plan 阶段字段。Agent 无状态：各自从这个对象读取所需、
返回更新后的对象，因此只有 orchestration 引擎知道执行顺序。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .schemas import Architecture, CodeReview, Dag, GeneratedFile, ProductSpec, SecurityReport


class ProjectPhase(str, Enum):
    INIT = "init"
    PLANNING = "planning"
    ARCHITECTING = "architecting"
    DECOMPOSING = "decomposing"
    WAITING_GATE_1 = "waiting_gate_1"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    # Week 3 — BUILD 阶段
    BUILDING = "building"
    BUILD_DONE = "build_done"
    BUILD_VERIFIED = "build_verified"  # npm build 通过（自动构建门）
    WAITING_GATE_2 = "waiting_gate_2"
    GATE_2_APPROVED = "gate_2_approved"
    GATE_2_REJECTED = "gate_2_rejected"
    FAILED = "failed"


class ProjectState(BaseModel):
    project_id: str
    idea: str
    phase: ProjectPhase = ProjectPhase.INIT
    product_spec: Optional[ProductSpec] = None
    architecture: Optional[Architecture] = None
    dag: Optional[Dag] = None
    gate_1_approved: bool = False
    gate_1_feedback: Optional[str] = None
    # Week 3 — BUILD 阶段
    generated_files: List[GeneratedFile] = Field(default_factory=list)
    extra_dependencies: Dict[str, str] = Field(default_factory=dict)  # Builder 声明的白名单依赖
    build_dir: Optional[str] = None
    build_passed: Optional[bool] = None  # 自动构建门结果（None = 未运行）
    build_log: Optional[str] = None  # 失败时的编译器报错尾部
    repair_attempts: int = 0  # 构建门失败后 Builder 自愈次数
    code_review: Optional[CodeReview] = None  # Reviewer 审查结果（Gate 2 前）
    review_rounds: int = 0  # Reviewer 否决后 Builder 修订轮数
    security_report: Optional[SecurityReport] = None  # Security 扫描结果（一票否决）
    # Gate 2 — preview 审核
    preview_url: Optional[str] = None
    screenshot_path: Optional[str] = None
    gate_2_approved: bool = False
    gate_2_feedback: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)  # 非阻塞提醒（如 DAG 粒度越界）
