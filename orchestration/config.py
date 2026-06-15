"""Central configuration for the v1 Plan pipeline.

所有 model id、路径、v1 固定栈集中在此 —— 一处调参（成本/质量，见 COST_OPTIMIZATION.md §9.2），
不必碰 agent 代码。
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Models (COST_OPTIMIZATION.md §9.2) ----------------------------------
# 决策层用最强模型（调用极少）；Decomposer 用中档。
# 默认 Claude；可用 FACTORY_MODEL（一刀切）或单独的 FACTORY_*_MODEL 覆盖，
# 以便指向任意 Anthropic 兼容网关（如智谱 GLM）做测试。
_MODEL_OVERRIDE = os.environ.get("FACTORY_MODEL")
PLANNER_MODEL = _MODEL_OVERRIDE or os.environ.get("FACTORY_PLANNER_MODEL", "claude-opus-4-8")
ARCHITECT_MODEL = _MODEL_OVERRIDE or os.environ.get("FACTORY_ARCHITECT_MODEL", "claude-opus-4-8")
DECOMPOSER_MODEL = _MODEL_OVERRIDE or os.environ.get("FACTORY_DECOMPOSER_MODEL", "claude-sonnet-4-6")
BUILDER_MODEL = _MODEL_OVERRIDE or os.environ.get("FACTORY_BUILDER_MODEL", "claude-sonnet-4-6")

# --- Paths (ARCHITECTURE.md §7.1 / §8) -----------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIKI_SPECS_DIR = PROJECT_ROOT / "wiki" / "specs"
WIKI_DECISIONS_DIR = PROJECT_ROOT / "wiki" / "decisions"
TASKS_JSON = PROJECT_ROOT / "tasks.json"

# --- v1 固定栈 (Architect 不自动选型，收窄问题空间) ------------------------
FIXED_STACK = {
    "frontend": "Next.js (App Router) + TypeScript",
    "styling": "Tailwind CSS",
    "backend": "Next.js API Routes / Supabase",
    "database": "PostgreSQL (Supabase)",
    "auth": "Supabase Auth",
    "deploy": "Vercel",
}

# --- LLM settings --------------------------------------------------------
MAX_TOKENS = 8000
BUILDER_MAX_TOKENS = 8000  # 整项目生成需要更大输出预算（DeepSeek 上限 ~8192）

# --- DAG 粒度约束 (Decomposer) -------------------------------------------
# 稳定性测显示同一 idea 节点数 8–20 波动；收敛到目标区间，过界给非阻塞 warning。
DAG_MIN_NODES = 12
DAG_MAX_NODES = 18

# --- 保真度：Builder 可声明的额外依赖白名单 ------------------------------
# 防止任意依赖注入：只接受白名单内的包，且固定版本（忽略 LLM 给的版本）。
ALLOWED_EXTRA_DEPS = {
    "pdfjs-dist": "4.7.76",  # 客户端 PDF 文本解析（无需后端/凭据）
    "@supabase/supabase-js": "2.45.0",  # Supabase 客户端（env 配置则真连，否则降级 mock）
}

# --- Builder / generated app (Week 3) ------------------------------------
GENERATED_DIR = PROJECT_ROOT / "generated"
API_KEY_ENV = "ANTHROPIC_API_KEY"
AUTH_TOKEN_ENV = "ANTHROPIC_AUTH_TOKEN"  # Bearer 认证（Anthropic 兼容网关，如 GLM）
BASE_URL_ENV = "ANTHROPIC_BASE_URL"


def get_api_key() -> str | None:
    return os.environ.get(API_KEY_ENV) or os.environ.get(AUTH_TOKEN_ENV)


def get_base_url() -> str | None:
    return os.environ.get(BASE_URL_ENV)
