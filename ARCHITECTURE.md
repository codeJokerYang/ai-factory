# One-Person Company AI Factory — 需求分析与架构设计

> 版本: v1.0
> 日期: 2026-06-15
>
> 本文档描述系统的**完整需求、功能架构、模块划分、数据流和落地路线**。
> 宪法 (`AGENT_CONSTITUTION.md`) 定义权力边界，本文档定义系统设计。
> 两份文档共同构成系统的完整蓝图。

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 系统目标](#2-系统目标)
- [3. 功能需求](#3-功能需求)
- [4. 非功能需求](#4-非功能需求)
- [5. 系统架构](#5-系统架构)
- [6. 模块详细设计](#6-模块详细设计)
- [7. 数据流](#7-数据流)
- [8. 项目目录结构](#8-项目目录结构)
- [9. 技术选型](#9-技术选型)
- [10. 实现路线图](#10-实现路线图)

---

## 1. 项目概述

### 1.1 一句话定义

> **"一句话 → 自动 Spec → 自动拆任务 → 自动编码 → 自动测试 → 自动审计 → 自动 PR → Human Gate → 自动部署"**
>
> 一个为一人公司服务的 AI 软件工厂操作系统。

### 1.2 核心问题

一人公司的瓶颈不是"写代码"，而是：

| 痛点 | 系统如何解决 |
|------|-------------|
| 从模糊想法到可执行 Spec 的鸿沟 | Planner Agent 自动生成 Product Spec |
| 技术选型耗时且容易选错 | Architect Agent 根据项目类型自动路由架构模板 |
| 任务拆解不系统，遗漏关键模块 | Decomposer Agent 产出结构化 DAG |
| 编码和测试来回切换上下文 | Builder Agents 并行执行，各司其职 |
| 手动 code review 累且容易漏 | Reviewer Agent 自动审查所有变更 |
| 安全意识靠自觉 | Security Agent + Filesystem Sandbox 强制执行 |
| 部署流程手动，容易出错 | CI/CD Pipeline + Preview Deploy 自动化 |

### 1.3 目标用户

- 独立开发者 / Solo Founder
- 小型创业团队（1-5 人）
- 想用 AI 放大产出的技术人员

### 1.4 非目标

- ❌ 不是替代人类产品经理的系统
- ❌ 不是面向非技术人员的无代码平台
- ❌ 不是大型团队的协作工具
- ❌ 不支持非 Git 的工作流

---

## 2. 系统目标

### 2.1 量化目标

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| Idea → Preview 时间 | < 4 小时 | 从 Gate 1 通过到 Preview URL 可用 |
| 人工介入次数 | ≤ 3 次/项目 | Gate 1 + Gate 2 + Gate 3 |
| 自动化率 | > 80% | 自动完成的 task / 总 task |
| 测试覆盖率 | > 80% | 由 Tester Agent 保证 |
| 安全漏洞拦截率 | 100% of high/critical | Security Agent + CI |
| 一次通过率 | > 60% | PR 不需要返修的比率 |

### 2.2 定性目标

- **方向可控**: 你只在 3 个 Gate 做决策，不迷失在细节中
- **质量可审计**: 每个 Agent 的输入/输出/决策留痕
- **失败可恢复**: 任何单个 task 失败不影响其他并行 task
- **知识可积累**: 每个项目的 spec/decision/code 沉淀为后续项目的参考

---

## 3. 功能需求

### 3.1 Phase 1 — PLAN（规划阶段）

#### FR-1.1: Idea 输入

```
输入: 自然语言一句话或一段描述
示例: "做一个帮大学生改简历的网站，支持 PDF 上传，按 JD 打分"
```

- 系统接收任意长度的自然语言输入
- 不做格式或模板要求

#### FR-1.2: Product Spec 自动生成 (Planner Agent)

```
输入: 用户的一句话 idea
输出: wiki/specs/{project-name}.md
```

生成的 Spec 必须包含：
- 用户画像（谁在用）
- 核心功能列表
- MVP 边界（做什么 + 不做什么）
- 用户故事（至少 3 个）
- 成功指标
- 风险分析（冷启动、法律、增长）

**约束**: Planner 不得讨论技术实现。

#### FR-1.3: 歧义检测和追问 (Ambiguity Resolver)

```
输入: Planner 输出的 Spec
输出: 置信度评分 + 缺失信息列表
```

置信度分级：
- `> 80%` → 自动继续
- `60-80%` → 使用默认假设 + 通知用户
- `< 60%` → 生成追问列表，等待 Gate 1 审批

追问示例：
```
需要确认 3 个问题：
1. 面向中国市场还是海外？
2. 是否收费？（免费 / 订阅 / 一次性）
3. 用户是否需要登录？（默认假设：需要邮箱注册）
```

#### FR-1.4: 架构方案自动生成 (Architect Agent)

```
输入: Product Spec + 用户偏好
输出: wiki/decisions/ 下的 ADR + architecture.md
```

Architect 必须：
- 根据项目类型自动匹配技术栈模板（SaaS / AI 产品 / 内容站 / App）
- 产出数据模型（ER 图或 Prisma/SQLAlchemy schema）
- 定义 API 设计原则和路径结构
- 定义部署目标
- 对 Planner 的不合理需求提出挑战（成本、可行性）

**技术栈路由规则：**

| 项目类型 | 前端 | 后端 | 数据库 | 部署 |
|---------|------|------|--------|------|
| SaaS | Next.js | Next.js API / Supabase | PostgreSQL | Vercel |
| AI 产品 | Next.js | FastAPI | PostgreSQL + Vector | Railway |
| 内容站点 | Astro / Next.js | — | — | Cloudflare |
| App | Expo | Supabase | PostgreSQL | — |
| CLI 工具 | — | Node.js / Python | — | npm / PyPI |

#### FR-1.5: 任务 DAG 自动生成 (Decomposer Agent)

```
输入: Spec + Architecture Blueprint
输出: tasks.json (结构化 DAG)
```

生成的 DAG 必须：
- 每个节点有唯一 ID 和明确的完成标准
- 声明节点之间的依赖关系
- 标注每个节点的优先级和风险等级
- 每个节点预估 30-90 分钟工作量

**DAG 示例：**

```json
{
  "project": "resume-optimizer",
  "nodes": [
    { "id": "001-db-schema",      "depends": [],                       "owner": "claude", "risk": "low" },
    { "id": "002-auth-login",     "depends": ["001-db-schema"],        "owner": "claude", "risk": "medium" },
    { "id": "003-auth-register",  "depends": ["001-db-schema"],        "owner": "codex",  "risk": "low" },
    { "id": "004-pdf-upload",     "depends": ["001-db-schema"],        "owner": "claude", "risk": "medium" },
    { "id": "005-jd-matching",    "depends": ["004-pdf-upload"],       "owner": "claude", "risk": "high" },
    { "id": "006-dashboard",      "depends": ["002-auth-login"],       "owner": "codex",  "risk": "low" },
    { "id": "007-integration",    "depends": ["005-jd-matching", "006-dashboard"], "owner": "claude", "risk": "high" }
  ]
}
```

#### FR-1.6: Reviewer 审查 DAG

```
输入: DAG
输出: 通过 / 驳回（带原因）
```

检查项：
- 依赖关系是否正确（无循环依赖）
- 是否遗漏关键模块
- 是否拆分过细或过粗
- 是否与 Architecture Blueprint 一致

#### FR-1.7: Gate 1 — Human Approval

```
触发: Phase 1 完成
展示: Product Spec + Architecture 摘要 + DAG 概览 + 追问列表（如有）
操作: Approve → 进入 Phase 2 / Reject → 带回修改意见
```

---

### 3.2 Phase 2 — BUILD（构建阶段）

#### FR-2.1: 云沙盒任务执行

```
输入: DAG 节点
执行:
  1. spawn ephemeral container
  2. git clone repo
  3. git checkout -b feat/{node-id}
  4. 注入 task context + coding conventions + relevant files
  5. Builder Agent 实现
  6. git commit
  7. git push
  8. destroy container
```

每个 DAG 节点一个容器。可并行执行的节点同时启动。

#### FR-2.2: Builder Agent 编码

- **Claude Builder**: 负责复杂逻辑、系统设计、agent 流程、debug（DAG 中标记 `owner: "claude"` 的节点）
- **Codex Builder**: 负责 CRUD、测试生成、Mock、重构、样板代码（DAG 中标记 `owner: "codex"` 的节点）
- **Specialist Agents**:
  - UI Agent: 前端组件生成
  - DB Agent: 数据库 migration 和 seed

**约束**: Builder 只能看当前 task + coding conventions + 相关文件。不能看全仓库。

#### FR-2.3: Tester Agent 自动测试

```
输入: 代码变更 + Spec 中的边界条件
输出: 测试文件 + 测试结果
```

- 单元测试（核心逻辑）
- 集成测试（API 端点）
- 边界条件测试（null、空数组、超时、异常）
- 目标覆盖率 > 80%

#### FR-2.4: Security Agent 自动安全扫描

- 硬编码密钥/密码检测
- SQL Injection / XSS / SSRF 检测
- 认证/授权漏洞检查
- 依赖 CVE 扫描
- 环境变量泄露检测

发现 high/critical 问题 → 直接阻塞，通知用户。

#### FR-2.5: Reviewer Agent 代码审查

```
输入: 所有 Builder 输出
输出: 通过 / 需要修改（带具体原因）
```

审查维度：
- 架构一致性（是否偏离 Blueprint）
- 代码质量（可维护性、重复代码）
- 命名规范
- 错误处理
- 性能问题

#### FR-2.6: Integration Agent 分支合并

当所有 DAG 节点完成后：
- 逐个合并 feature branch
- 检测和解决冲突
- 确保合并后测试通过
- 自动更新 wiki/ 文档

#### FR-2.7: CI/CD Pipeline

```
触发: PR 创建
自动执行:
  - Lint check
  - Type check
  - Unit test
  - Integration test
  - Security scan
  - Wiki sync check
  - Preview deploy
```

#### FR-2.8: Gate 2 — Human Approval

```
触发: CI 全部通过 + Preview URL 可用
展示: Preview 链接 + 功能演示 + Test 报告 + Security 报告
操作: Approve → 合并到 main / Reject → 带回修改意见
```

---

### 3.3 Phase 3 — RELEASE（发布阶段）

#### FR-3.1: Staging 部署

- 合并到 main 后自动部署到 staging
- 跑 smoke test
- 自动生成 changelog

#### FR-3.2: Gate 3 — Human Approval

```
触发: Staging 通过
展示: Staging URL + Changelog
操作: 部署到生产 / 回退
```

#### FR-3.3: 生产部署与回滚

- 自动部署到生产环境
- 健康检查
- 失败自动回滚
- 部署日志持久化

---

## 4. 非功能需求

### 4.1 安全

| 需求 | 实现方式 |
|------|---------|
| Agent 不能访问系统目录 | Filesystem Sandbox（MCP filesystem 限定项目目录） |
| Agent 不能泄露密钥 | Secrets Firewall（.env 只读，CI 扫描硬编码密钥） |
| Agent 不能直接写 main | Git Boundary（强制 branch + PR 流程） |
| Agent 不能自繁殖 | 宪法红线：Agent 不得创建新 Agent |
| 所有操作可审计 | 每次 container 执行日志持久化到仓库外 |

### 4.2 可靠性

| 需求 | 实现方式 |
|------|---------|
| 单个 task 失败不影响整体 | DAG 节点级容器隔离 + 失败只影响依赖该节点的后续节点 |
| 失败 task 可恢复 | 每个 task 的 checkout/commit/push 独立，可重新 spawn |
| 系统状态可恢复 | LangGraph checkpoint 持久化 |
| 超时处理 | 每个 task 设置 2 小时超时，超时自动标记 blocked |

### 4.3 性能

| 需求 | 指标 |
|------|------|
| 并行 task 数 | 最多 10 个同时运行 |
| 单个 task 耗时 | 目标 30-90 分钟 |
| Gate 审批耗时 | < 5 分钟/次 |
| Idea → Preview | < 4 小时（中小型项目） |

### 4.4 可维护性

| 需求 | 实现方式 |
|------|---------|
| 宪法和代码分离 | AGENT_CONSTITUTION.md 是独立文件，修改不触及系统代码 |
| Agent 可独立升级 | 每个 Agent 的 system prompt 和工具集独立定义 |
| 知识可累积 | 每个项目的 wiki/ 沉淀为后续项目的参考 |
| 日志可追溯 | 每次执行的 agent_id + task_id + timestamp 全程记录 |

---

## 5. 系统架构

### 5.1 架构全景

```
                            ┌─────────────────────┐
                            │      HUMAN (CEO)     │
                            └──────────┬──────────┘
                                       │
                    Gate 1 ────────────┼──────────── Gate 2 ──────────── Gate 3
                      │                │               │                   │
                      ▼                │               ▼                   ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                         ORCHESTRATION LAYER                                  ║
║                         (LangGraph State Machine)                            ║
║                                                                              ║
║  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌───────────┐                ║
║  │ Planner  │  │Architect │  │Decomposer  │  │Ambiguity  │                ║
║  │          │  │          │  │            │  │Resolver   │                ║
║  └────┬─────┘  └────┬─────┘  └─────┬──────┘  └─────┬─────┘                ║
║       │              │              │               │                       ║
║       └──────────────┼──────────────┼───────────────┘                       ║
║                      │              │                                        ║
║                      ▼              ▼                                        ║
║               ┌──────────────────────────┐                                  ║
║               │       REVIEWER           │  ← Agent 间仲裁者                 ║
║               └──────────────────────────┘                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                       │
                                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                         EXECUTION LAYER                                      ║
║                         (Cloud Sandbox Cluster)                              ║
║                                                                              ║
║  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       ║
║  │ Container #1 │ │ Container #2 │ │ Container #3 │ │ Container #N │       ║
║  │ feat/001     │ │ feat/002     │ │ feat/003     │ │ feat/00N     │       ║
║  │              │ │              │ │              │ │              │       ║
║  │ Claude       │ │ Codex        │ │ Claude       │ │ Codex        │       ║
║  │ Builder      │ │ Builder      │ │ Builder      │ │ Tester       │       ║
║  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘       ║
║         │                │                │                │               ║
║         └────────────────┼────────────────┼────────────────┘               ║
║                          │                │                                 ║
║                          ▼                ▼                                 ║
║                   ┌──────────────────────────┐                            ║
║                   │   Integration Container  │                            ║
║                   │   合并 → 测试 → PR       │                            ║
║                   └──────────────────────────┘                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                       │
                                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                         SECURITY LAYER                                       ║
║                                                                              ║
║  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            ║
║  │Filesystem Sandbox│ │ Git Boundary     │ │Secrets Firewall  │            ║
║  │(限定项目目录)     │ │(强制 branch+commit)│ │(.env只读+扫描)  │            ║
║  └──────────────────┘ └──────────────────┘ └──────────────────┘            ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                       │
                                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                         CI/CD LAYER                                          ║
║                         (GitHub Actions)                                     ║
║                                                                              ║
║  Lint → Type Check → Unit Test → Integration Test → Security Scan → Deploy  ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 5.2 架构分层说明

| 层 | 职责 | 核心组件 | 运行位置 |
|----|------|---------|---------|
| **Orchestration** | 决策、规划、协调 | LangGraph State Machine + 6 个 Planning Agent | 本地或轻量云 VM |
| **Execution** | 编码、测试、审计 | Docker Containers + Builder Agents | 云端 Ephemeral Sandbox |
| **Security** | 访问控制、边界约束 | Filesystem Sandbox + Git Boundary + Secrets Firewall | 所有层嵌入 |
| **CI/CD** | 质量门、部署 | GitHub Actions | GitHub Runners |

---

## 6. 模块详细设计

### 6.1 Orchestration Layer（编排层）

#### 6.1.1 LangGraph 状态机

**状态定义：**

```python
from typing import TypedDict, List, Optional
from enum import Enum

class ProjectPhase(Enum):
    INIT = "init"
    PLANNING = "planning"
    AMBIGUITY_CHECK = "ambiguity_check"
    ARCHITECTING = "architecting"
    DECOMPOSING = "decomposing"
    DAG_REVIEW = "dag_review"
    WAITING_GATE_1 = "waiting_gate_1"
    BUILDING = "building"
    TESTING = "testing"
    SECURITY_SCAN = "security_scan"
    REVIEWING = "reviewing"
    INTEGRATING = "integrating"
    CI_RUNNING = "ci_running"
    WAITING_GATE_2 = "waiting_gate_2"
    DEPLOYING_STAGING = "deploying_staging"
    WAITING_GATE_3 = "waiting_gate_3"
    DEPLOYING_PROD = "deploying_prod"
    COMPLETED = "completed"
    FAILED = "failed"

class ProjectState(TypedDict):
    project_id: str
    phase: ProjectPhase
    idea: str                              # 用户原始输入
    product_spec: Optional[str]            # Planner 输出
    ambiguity_report: Optional[dict]       # Ambiguity Resolver 输出
    architecture: Optional[dict]           # Architect 输出
    dag: Optional[dict]                    # Decomposer 输出
    dag_review: Optional[dict]             # Reviewer 对 DAG 的审查
    gate_1_approved: bool
    gate_2_approved: bool
    gate_3_approved: bool
    tasks_status: dict                     # {task_id: "pending"|"running"|"done"|"failed"}
    errors: List[dict]                     # 错误日志
```

**状态转换图：**

```
INIT
  │
  ▼
PLANNING ──→ AMBIGUITY_CHECK ──→ (追问用户 / 自动通过)
  │                                      │
  ▼                                      ▼
ARCHITECTING ←────────────────────────────
  │
  ▼
DECOMPOSING ──→ DAG_REVIEW ──→ (通过 / 驳回重拆)
  │
  ▼
WAITING_GATE_1 ──→ (approve / reject)
  │
  ▼
BUILDING (并行 N 个 Builder Container)
  │
  ▼
TESTING (并行 N 个 Tester Container)
  │
  ├── (任一失败 → 对应 Builder 重试)
  │
  ▼
SECURITY_SCAN ──→ (high/critical → 阻塞)
  │
  ▼
REVIEWING ──→ (通过 / 驳回 Builder)
  │
  ▼
INTEGRATING (合并分支)
  │
  ▼
CI_RUNNING (Lint + Test + Security)
  │
  ▼
WAITING_GATE_2 ──→ (approve / reject)
  │
  ▼
DEPLOYING_STAGING
  │
  ▼
WAITING_GATE_3 ──→ (approve / reject)
  │
  ▼
DEPLOYING_PROD
  │
  ▼
COMPLETED
```

#### 6.1.2 Agent 定义

每个 Agent 是一个独立的 LangGraph node，有独立的 system prompt、工具集、和上下文窗口。

**Planner Agent：**
```
模型: Claude
输入: idea (str)
输出: product_spec (str, markdown)
工具: 无（纯推理）
上下文: 用户偏好（wiki/）、同类型项目历史 Spec
约束: 不得讨论技术实现
```

**Ambiguity Resolver Agent：**
```
模型: Claude
输入: product_spec
输出: ambiguity_report {confidence, missing_items[], assumptions[], questions[]}
工具: 无（纯推理）
上下文: 用户偏好、行业常识
```

**Architect Agent：**
```
模型: Claude
输入: product_spec + ambiguity_report
输出: architecture {stack, db_schema, api_design, deploy_target, adrs[]}
工具: 无（纯推理 + 模板匹配）
上下文: 技术偏好、现有架构模板
约束: 不得修改产品需求
```

**Decomposer Agent：**
```
模型: Claude
输入: product_spec + architecture
输出: dag (JSON, 结构化 DAG)
工具: 无
上下文: 历史 DAG 模板、编码规范
```

**Reviewer Agent（Plan 阶段）：**
```
模型: Claude
输入: dag + architecture
输出: dag_review {passed, issues[]}
检查: 循环依赖、遗漏模块、拆分粒度、架构一致性
```

**Builder Agents（Execution 阶段）：**

三级 Builder 架构（详见 `COST_OPTIMIZATION.md`）：

```
Level 1 — Cheap Builder (Haiku)
  占比: ~70% 任务
  处理: CRUD、样板代码、UI 组件、Mock 数据
  升级: 失败 > 1 次 → Level 2

Level 2 — Smart Builder (Sonnet)
  占比: ~25% 任务
  处理: 业务逻辑、状态管理、性能优化、API 设计
  升级: 失败 > 1 次 → Level 3

Level 3 — Expert Builder (Opus)
  占比: ~5% 任务
  处理: 支付、认证、DB migration、Infra
  升级: 失败 > 1 次 → Human Gate 2
```

```
输入: task_context + coding_conventions + relevant_files（由 Context Retriever 精准选取）
输出: committed code on feature branch
工具: MCP filesystem + MCP github + MCP database
上下文: 限定的（L1: 5k tokens/3文件, L2: 10k tokens/5文件, L3: 20k tokens/10文件）
```

**Tester Agent（规则引擎先行）：**
```
流程: pytest/Jest 先跑 → 失败再用 LLM → Builder 修 → 重跑
模型: Haiku（仅在测试失败或无测试时启用 LLM）
输入: code_diff + spec边界条件 + 测试失败报告
输出: test_files + test_results
目标: 覆盖率 > 80%
零 token 路径: 已有测试全部通过 → LLM 完全不介入
```

**Security Agent（规则引擎先行）：**
```
流程: Semgrep/Dependabot 先扫 → 高风险 diff → LLM 再审
模型: Sonnet（仅在 Semgrep 标记 high/critical 时启用 LLM）
输入: code_diff + dependency_tree + Semgrep 报告
输出: security_report {vulnerabilities[], risk_level}
检查: secrets, SQLi, XSS, SSRF, auth_bypass, CVE
权限: 一票否决权（不可被 Reviewer override）
零 token 路径: Semgrep 无 high/critical 发现 → LLM 完全不介入
```

**Integration Agent：**
```
模型: Claude
输入: all_feature_branches + dag
输出: merged_main (或冲突报告)
操作: 逐分支 merge → 冲突检测 → 回归测试 → wiki 更新
```

### 6.2 Execution Layer（执行层）

#### 6.2.1 容器生命周期

```
┌─────────────────────────────────────────────┐
│            Container Lifecycle               │
│                                              │
│  1. SPAWN                                    │
│     docker run --rm -v /tmp/repo:/repo \     │
│       --network=none \         ← 无网络      │
│       --memory=4g \                          │
│       builder-image                          │
│                                              │
│  2. SETUP                                    │
│     git clone <repo> /repo                   │
│     git checkout -b feat/{task-id}           │
│                                              │
│  3. INJECT                                   │
│     → task context (当前节点的需求)           │
│     → coding conventions (规范文件)          │
│     → relevant files (相关源码，非全仓库)    │
│     → CLAUDE.md / AGENT_CONSTITUTION.md      │
│                                              │
│  4. EXECUTE                                  │
│     Builder Agent 编码                       │
│     或 Tester Agent 写测试                   │
│     或 Security Agent 扫描                   │
│                                              │
│  5. COMMIT                                   │
│     git add .                                │
│     git commit -m "{task-id}: {description}" │
│     git push origin feat/{task-id}           │
│                                              │
│  6. DESTROY                                  │
│     docker rm -f <container>                 │
│     清除所有临时文件                          │
│     日志已持久化到仓库外                      │
└─────────────────────────────────────────────┘
```

#### 6.2.2 并行调度

```
DAG 示例:
  001 ──┬── 003 ── 006 ──┐
        │                 │
        └── 004 ── 005 ───┼── 007
                          │
  002 ────────────────────┘

调度时序:
  t=0:  启动 001, 002 (无依赖，并行)
  t=1:  001 完成 → 启动 003, 004 (依赖 001 已满足)
  t=2:  002 完成 → 无新启动 (003/004 已启动，不依赖 002)
  t=3:  003 完成 → 启动 006
  t=4:  004 完成 → 启动 005
  t=5:  006 完成 → 等待 005
  t=6:  005 完成 → 001/002/005/006 全部完成 → 启动 007
  t=7:  007 完成 → BUILDING 阶段结束
```

调度器：
- 监听 DAG 节点状态变化
- 当节点所有依赖完成时，自动 spawn 对应容器
- 最大并发数可配置（默认 10）
- 失败节点自动重试 2 次

### 6.3 Security Layer（安全层）

#### 6.3.1 Filesystem Sandbox

通过 MCP filesystem 实现：
- 所有路径操作被拦截
- 只允许在项目 Git 仓库路径内的读写
- `.env`、`.git/config`、`~/.ssh` 标记为禁止访问
- 任何越权操作记录日志并终止容器

#### 6.3.2 Git Boundary

- 禁止 push 到 main/master（GitHub branch protection）
- 禁止 force push
- 所有 commit 必须包含 task-id（可追溯到 DAG 节点）
- 所有 commit 由 GitHub Actions 验证合规性

#### 6.3.3 Secrets Firewall

- 容器启动时注入 `.env` 为只读文件
- CI 中扫描所有 diff 的硬编码密钥模式
- `.env` 文件加入 `.gitignore` 强制项
- Security Agent 在每次 commit 后扫描

### 6.4 CI/CD Layer（CI/CD 层）

参见 `.github/workflows/ai-code-guard.yml`，包含：
- Lint check
- Type check
- Unit + Integration test
- Security scan
- Wiki sync check
- Preview deploy
- 全通过后触发 Gate 2 通知

---

## 7. 数据流

### 7.1 主数据流

```
用户输入 (idea)
     │
     ▼
┌─────────────┐
│   Planner   │ ──→ wiki/specs/{project}.md
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│Ambiguity Resolver│ ──→ ambiguity_report (JSON)
└────────┬─────────┘
         │
         ▼
┌──────────────┐
│  Architect   │ ──→ wiki/decisions/{project}-*.md
└──────┬───────┘     architecture.md
       │
       ▼
┌──────────────┐
│ Decomposer   │ ──→ tasks.json (DAG)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Reviewer   │ ──→ dag_review (通过/驳回)
└──────┬───────┘
       │
       ▼
  ╔══════════╗
  ║ Gate 1   ║  ← 你审批 Spec + DAG
  ╚══════════╝
       │
       ▼
┌──────────────────────────────────────────┐
│           Parallel Builders              │
│                                          │
│  Container-001 ──→ feat/001 (commit)     │
│  Container-002 ──→ feat/002 (commit)     │
│  Container-003 ──→ feat/003 (commit)     │
│  ...                                     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│           Parallel Testers               │
│  Tester-001 ──→ test files + report      │
│  Tester-002 ──→ test files + report      │
│  ...                                     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────┐
│   Security   │ ──→ security_report
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Reviewer   │ ──→ code_review (通过/驳回)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Integration  │ ──→ 合并到 main
└──────┬───────┘
       │
       ▼
┌──────────────┐
│     CI       │ ──→ Lint + Test + Security + Preview Deploy
└──────┬───────┘
       │
       ▼
  ╔══════════╗
  ║ Gate 2   ║  ← 你审批 Preview
  ╚══════════╝
       │
       ▼
┌──────────────┐
│   Staging    │ ──→ smoke test
└──────┬───────┘
       │
       ▼
  ╔══════════╗
  ║ Gate 3   ║  ← 你审批部署
  ╚══════════╝
       │
       ▼
┌──────────────┐
│  Production  │
└──────────────┘
```

### 7.2 失败处理流

```
Builder 失败
  → 自动重试（最多 2 次）
    → 仍失败 → 标记为 blocked
      → 如果该节点被其他节点依赖 → 受影响节点进入 waiting
      → 通知用户（不阻塞其他并行节点）

Tester 失败
  → 报告给对应 Builder → Builder 修复 → 重新提交

Security 发现 high/critical
  → 立即阻塞 → 通知用户 → 等待 Gate 2 决策

Reviewer 驳回
  → Builder 修复 → 重新提交 Reviewer
    → 连续 2 次驳回 → 升级到 Gate 2
```

---

## 8. 项目目录结构

```
project-root/
│
├── orchestration/                    # 编排层（核心系统）
│   ├── graph.py                      # LangGraph 主状态机
│   ├── state.py                      # 状态定义
│   ├── gates.py                      # Human Approval Gate 逻辑
│   │
│   ├── agents/                       # Agent 定义
│   │   ├── planner.py                # Layer 1: 产品脑
│   │   ├── ambiguity_resolver.py     # 歧义检测
│   │   ├── architect.py              # Layer 2: 架构师
│   │   ├── decomposer.py             # Layer 3: 任务拆解
│   │   ├── builder_claude.py         # Claude Builder
│   │   ├── builder_codex.py          # Codex Builder
│   │   ├── tester.py                 # 测试生成
│   │   ├── security.py               # 安全审计
│   │   └── reviewer.py               # 审查 + 仲裁
│   │
│   ├── sandbox/                      # 云沙盒管理
│   │   ├── manager.py                # 容器生命周期管理
│   │   ├── spawn.sh                  # 启动容器
│   │   ├── inject.py                 # 上下文注入
│   │   └── destroy.sh                # 销毁容器
│   │
│   └── scheduler/                    # DAG 调度器
│       ├── scheduler.py              # 并行调度逻辑
│       └── dag_validator.py          # DAG 合法性检查
│
├── wiki/                             # LLM Wiki（项目记忆）
│   ├── INDEX.md
│   ├── decisions/                    # ADR 架构决策
│   ├── specs/                        # Product Spec
│   ├── conventions/                  # 编码规范
│   └── runbooks/                     # 运维手册
│
├── templates/                        # 架构模板（Architect 使用）
│   ├── saas.json                     # SaaS 模板
│   ├── ai-product.json               # AI 产品模板
│   ├── content-site.json             # 内容站模板
│   └── mobile-app.json               # App 模板
│
├── .claude/
│   └── mcp.json                      # MCP 配置
│
├── .github/workflows/
│   └── ai-code-guard.yml             # CI/CD
│
├── scripts/
│   ├── guard.sh                      # Git 安全守卫
│   └── setup.sh                      # 一键初始化
│
├── AGENT_CONSTITUTION.md             # AI 组织宪法
├── ARCHITECTURE.md                   # 本文档
├── CLAUDE.md                         # AI 入职文档
├── README.md                         # 工作流总览
└── ROADMAP.md                        # 任务进度
```

---

## 9. 技术选型

### 9.1 核心技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| **编排框架** | LangGraph | 状态机原生支持、checkpoint 持久化、人类审批节点 |
| **模型 - 决策层** | Claude Opus | Planner / Architect / Reviewer（贵但调用极少） |
| **模型 - Builder L1** | Claude Haiku | 70% 任务（极便宜，占大头） |
| **模型 - Builder L2** | Claude Sonnet | 25% 任务（中档） |
| **模型 - Builder L3** | Claude Opus | 5% 任务（高风险，调用极少） |
| **模型 - 执行** | Codex (OpenAI) | Tester 辅助、CRUD 加速 |
| **Context Retriever** | tree-sitter + embedding | 精准注入相关文件，省 90% token |
| **规则引擎** | Semgrep / ESLint / pytest | 能不用 LLM 的绝不用 LLM |
| **容器运行时** | Docker | 标准化、隔离性好、CI 原生支持 |
| **代码托管** | GitHub | MCP 集成、Actions、Branch Protection |
| **CI/CD** | GitHub Actions | 托管、免费额度够用 |
| **数据库** | PostgreSQL | 项目主力 DB，Architect 可替换 |
| **部署 - 前端** | Vercel | 零配置、Preview Deploy |
| **部署 - 后端** | Railway / Fly.io | 简单、Docker 支持 |
| **MCP 协议** | Model Context Protocol | 工具接入标准、Filesystem/GitHub/DB 服务器 |
| **成本优化** | 三级路由 + 缓存 + 规则优先 | 详见 `COST_OPTIMIZATION.md` |

### 9.2 为什么不用

| 被排除的 | 原因 |
|---------|------|
| LangChain (基础) | 只适合聊天链，不适合长期多 Agent 状态机 |
| AutoGPT / BabyAGI | 没有制衡机制，Agent drift 严重 |
| 本地 Claude Code 直接编码 | 安全隔离差，无法并行，上下文污染 |
| Kubernetes | MVP 阶段过重，Docker + GH Actions 够用 |
| 微服务架构 | 项目初期拆太细是过度工程 |

---

## 10. 实现路线图

### 10.1 阶段划分

```
Phase 0: Foundation（当前）
Phase 1: Single Agent Pipeline（单项目手动跑通）
Phase 2: DAG Parallel Execution（并行执行）
Phase 3: Autonomous Mode（自动模式）
Phase 4: Self-Improving System（自进化）
```

### 10.2 Phase 0 — Foundation ✅

**状态: 已完成**

- [x] 项目目录结构
- [x] CLAUDE.md 模板
- [x] Wiki 模板（specs/decisions/conventions/runbooks）
- [x] MCP 配置
- [x] Git 安全守卫脚本
- [x] CI/CD 防线
- [x] Agent Constitution
- [x] Architecture Design（本文档）

### 10.3 Phase 1 — Single Agent Pipeline

**目标**: 手动在本地跑通一次 "idea → spec → architecture → DAG → 编码 → 测试 → PR" 的完整流程。

**产出**:
- [ ] `orchestration/graph.py` — LangGraph 主状态机
- [ ] `orchestration/state.py` — 状态定义
- [ ] `orchestration/gates.py` — Human Approval Gate
- [ ] `orchestration/agents/planner.py`
- [ ] `orchestration/agents/architect.py`
- [ ] `orchestration/agents/decomposer.py`
- [ ] `orchestration/agents/ambiguity_resolver.py`
- [ ] `orchestration/agents/reviewer.py`

**验收标准**: 给定一句话 idea，输出 Spec + Architecture + DAG，经过 Gate 1 人工确认后，产出代码 + 测试。

### 10.4 Phase 2 — DAG Parallel Execution

**目标**: 引入云沙盒 + 并行 Builder 执行。

**产出**:
- [ ] `orchestration/sandbox/` — 容器管理
- [ ] `orchestration/scheduler/` — DAG 并行调度
- [ ] `orchestration/agents/builder_claude.py`
- [ ] `orchestration/agents/builder_codex.py`
- [ ] `orchestration/agents/tester.py`
- [ ] `orchestration/agents/security.py`
- [ ] `orchestration/agents/integration.py` (Integration Agent)

**验收标准**: 多个 DAG 节点并行执行，容器隔离，失败节点自动重试。

### 10.5 Phase 3 — Autonomous Mode

**目标**: 减少人工介入，系统自动处理大部分决策。

**产出**:
- [ ] 用户偏好学习模块
- [ ] 置信度自动路由（高置信自动过）
- [ ] 自动重试和降级策略
- [ ] 通知系统（低置信/non-blocking 事件通知）

**验收标准**: 对于中低风险项目，用户仅在 3 个 Gate 做审批。80% 以上的决策由系统自动完成。

### 10.6 Phase 4 — Self-Improving System

**目标**: 系统从历史项目中学习，持续优化决策质量。

**产出**:
- [ ] 项目知识库（跨项目 spec/decision 复用）
- [ ] 架构模板自动优化
- [ ] DAG 拆解质量反馈循环
- [ ] 代码质量趋势追踪

---

## 附录：文档索引

| 文档 | 用途 | 读者 |
|------|------|------|
| `README.md` | 工作流总览，角色分工，快速开始 | 你 |
| `CLAUDE.md` | AI 入职文档，项目规范，强制规则 | AI Agent |
| `AGENT_CONSTITUTION.md` | 权力架构，批准拓扑，记忆边界，红线 | 所有 Agent（最高约束） |
| `ARCHITECTURE.md` (本文档) | 需求分析，系统架构，模块设计，路线图 | 你 + 开发者 |
| `ROADMAP.md` | 当前任务进度 | 你 + AI |
| `wiki/*.md` | 项目知识库（specs/decisions/conventions/runbooks） | AI Agent |
