"""Shared typed schemas for the Plan pipeline.

镜像 ARCHITECTURE.md 已定义的契约（§3.1.5 DAG、§6.1.x agent 输出），让实现与设计文档一致。
Agent 在 ProjectState 上读写这些 typed 对象；orchestration 引擎（现在 SequentialRunner，
将来 LangGraph）不需要知道它们的内部结构。
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class UserStory(BaseModel):
    as_a: str
    i_want: str
    so_that: str


class ProductSpec(BaseModel):
    """Planner 输出 (FR-1.2)。不得含技术内容。"""

    project_name: str
    one_liner: str
    target_users: str
    core_features: List[str] = Field(default_factory=list)
    mvp_in_scope: List[str] = Field(default_factory=list)
    mvp_out_of_scope: List[str] = Field(default_factory=list)
    user_stories: List[UserStory] = Field(default_factory=list)
    success_metrics: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class ApiEndpoint(BaseModel):
    method: str
    path: str
    purpose: str


class Adr(BaseModel):
    title: str
    decision: str
    rationale: str


class Architecture(BaseModel):
    """Architect 输出 (FR-1.4)。v1 使用 config.FIXED_STACK。"""

    stack: Dict[str, str] = Field(default_factory=dict)
    data_model: str = ""
    api_design: List[ApiEndpoint] = Field(default_factory=list)
    deploy_target: str = ""
    adrs: List[Adr] = Field(default_factory=list)


class Risk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class DagNode(BaseModel):
    """镜像 ARCHITECTURE.md §3.1.5。每个节点预估 30-90 分钟。"""

    id: str
    depends: List[str] = Field(default_factory=list)
    owner: str = "claude"
    risk: Risk = Risk.low
    done_criteria: str = ""
    est_minutes: int = 60


class Dag(BaseModel):
    project: str
    nodes: List[DagNode] = Field(default_factory=list)


class GeneratedFile(BaseModel):
    """Builder 输出的单个文件（相对生成 app 根目录的路径 + 内容）。"""

    path: str
    content: str


class ReviewIssue(BaseModel):
    severity: str  # "low" | "medium" | "high"
    file: str = ""
    message: str


class CodeReview(BaseModel):
    """Reviewer 输出（FR-2.5）。passed=false 表示存在 high 阻塞问题。"""

    passed: bool
    summary: str = ""
    issues: List[ReviewIssue] = Field(default_factory=list)


class SecurityFinding(BaseModel):
    severity: str  # "low" | "medium" | "high" | "critical"
    file: str = ""
    kind: str = ""
    message: str = ""


class SecurityReport(BaseModel):
    """Security 输出（FR-2.4 / 宪法 5.2）。passed=false = 有 high/critical，触发一票否决。"""

    passed: bool = True
    risk_level: str = "none"  # none|low|medium|high|critical
    findings: List[SecurityFinding] = Field(default_factory=list)
    summary: str = ""  # LLM 对高危项的评估（仅高危时调用）
