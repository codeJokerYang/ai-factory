# 成本优化与模型路由设计

> 版本: v1.0
> 日期: 2026-06-15
>
> 目标: **成本下降 70–90%，质量下降 < 10%**
>
> 核心原则: 把贵模型放在决策层，便宜模型放在执行层，能用规则引擎的绝不用 LLM。

---

## 目录

- [1. North Star KPI](#1-north-star-kpi)
- [2. 模型路由策略](#2-模型路由策略)
- [3. 三级 Builder 架构](#3-三级-builder-架构)
- [4. Context 精准注入](#4-context-精准注入)
- [5. 规则引擎替代 LLM](#5-规则引擎替代-llm)
- [6. Diff-based Prompting](#6-diff-based-prompting)
- [7. 缓存与方案复用](#7-缓存与方案复用)
- [8. 成本预估模型](#8-成本预估模型)
- [9. 集成到 Architecture](#9-集成到-architecture)

---

## 1. North Star KPI

不追求"自动化率 95%"，追求**商业上可持续**：

| KPI | 目标 | 测量方式 |
|-----|------|---------|
| 单次 Preview Deploy 成本 | < $5 | API token 统计 |
| 首次成功率 | > 80% | PR 不需要返修的比率 |
| 人工干预时间 | < 5 分钟/项目 | Gate 1 + Gate 2 + Gate 3 累计 |
| 成本下降幅度 | 70-90% vs 全量强模型 | 对比基线 |
| 质量下降幅度 | < 10% | Reviewer 评分 + 返修率 |

---

## 2. 模型路由策略

### 2.1 路由矩阵

```
                        调用频率          模型等级          单次成本
                       ─────────        ─────────        ─────────
Planner               极低 (1-3次)      最强 (Opus)       可忽略
Architect             极低 (1-5次)      最强 (Opus)       可忽略
Ambiguity Resolver    低   (1-3次)      强   (Sonnet)     低
Decomposer            低   (1-3次)      中强 (Sonnet)     低
Reviewer (Plan)       低   (1-2次)      强   (Sonnet)     低

Builder (default)     高   (70%任务)    中   (Haiku)      极低
Builder (complex)     中   (25%任务)    中强 (Sonnet)     低
Builder (high-risk)   极低 (5%任务)     强   (Opus)       中

Tester                高   (每个task)    小   (Haiku)      极低
Security (LLM pass)   低   (仅高风险diff) 中 (Sonnet)     低
Security (rule)       高   (每个commit)  免费 (Semgrep等)  0

Reviewer (Code)       中   (每个PR)     中强 (Sonnet)     低
Integration           低   (1次/项目)    中强 (Sonnet)     低
```

### 2.2 路由决策逻辑

```
任务进入
    │
    ▼
┌─────────────────────┐
│ 是决策层任务?        │  Planner / Architect / Decomposer
│ (规划/架构/拆解)     │──→ 强模型，不省钱
└────────┬────────────┘
         │ 否
         ▼
┌─────────────────────┐
│ 是执行层任务?        │  Builder / Tester
│ (编码/测试)          │
└────────┬────────────┘
         │ 是
         ▼
┌─────────────────────┐
│ 风险评估             │
│                      │
│ high-risk? ──→ Level 3 Builder (Opus)   5%
│ complex?  ──→ Level 2 Builder (Sonnet) 25%
│ default   ──→ Level 1 Builder (Haiku)  70%
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ 能用规则引擎?        │  Lint / Security / Format
│                      │──→ 0 token
└─────────────────────┘
```

### 2.3 风险等级判定

| 风险 | 判定条件 | Builder 等级 | 模型 |
|------|---------|-------------|------|
| **low** | CRUD、样板代码、UI 组件、mock 数据 | Level 1 | Haiku |
| **medium** | 业务逻辑、状态管理、性能优化、API wiring | Level 2 | Sonnet |
| **high** | 支付、认证、agent 流程、infra、DB migration | Level 3 | Opus |

**自动升级条件:**
- Level 1 失败 > 1 次 → 自动升级到 Level 2
- Level 2 失败 > 1 次 → 自动升级到 Level 3
- Reviewer 连续 2 次驳回同一 task → 强制 Level 3

---

## 3. 三级 Builder 架构

### 3.1 Level 1: Cheap Builder (Haiku)

```
模型: Claude Haiku / GPT-4o-mini
占比: ~70% 任务
成本: 极低
Context: 严格限定 5k-10k tokens

处理:
  ✅ CRUD 接口
  ✅ 样板代码
  ✅ UI 组件
  ✅ 简单路由
  ✅ Mock 数据
  ✅ 配置文件

不处理:
  ❌ 支付逻辑
  ❌ 认证授权
  ❌ 复杂状态机
  ❌ 性能敏感代码
  ❌ 数据库 migration

失败策略:
  重试 1 次 → 仍失败 → 自动升级 Level 2
```

### 3.2 Level 2: Smart Builder (Sonnet)

```
模型: Claude Sonnet / GPT-4o
占比: ~25% 任务
成本: 低
Context: 10k-20k tokens

处理:
  ✅ 业务逻辑
  ✅ 状态管理
  ✅ 性能优化
  ✅ 复杂查询
  ✅ API 设计
  ✅ 从 Level 1 升级上来的任务

失败策略:
  重试 1 次 → 仍失败 → 自动升级 Level 3
```

### 3.3 Level 3: Expert Builder (Opus)

```
模型: Claude Opus / GPT-4.5
占比: ~5% 任务
成本: 中
Context: 20k-50k tokens（全量上下文）

处理:
  ✅ 支付系统
  ✅ 认证授权
  ✅ Agent 编排
  ✅ 数据库 migration
  ✅ Infra 配置
  ✅ 从 Level 2 升级上来的任务
  ✅ DAG 中标记 risk: "high" 的节点

失败策略:
  重试 1 次 → 仍失败 → 升级到 Human (Gate 2)
```

### 3.4 升级流程图

```
Task 进入
    │
    ▼
┌──────────────┐
│ 风险评估      │
└──────┬───────┘
       │
  ┌────┼────┐
  │    │    │
  ▼    ▼    ▼
low  med  high
  │    │    │
  ▼    ▼    ▼
 L1   L2   L3
  │    │    │
  ├────┼────┤
  │    │    │
  ▼    ▼    ▼
成功? 成功? 成功?
  │    │    │
  ├─y  ├─y  ├─y → 进入 Tester
  │    │    │
  ├─n  ├─n  ├─n
  │    │    │
  ▼    ▼    ▼
重试  重试  重试
  │    │    │
  ├─y  ├─y  ├─y → 进入 Tester
  │    │    │
  ├─n  ├─n  ├─n → Human
  │    │
  ▼    ▼
升级  升级
 L2   L3
```

---

## 4. Context 精准注入

### 4.1 问题

全量注入成本对比：

```
全仓库注入:         80k tokens → 贵 + 模型 drift
精准注入:           5-10k tokens → 便宜 + 聚焦
```

省 **90%** token，质量基本不变。

### 4.2 Context Retriever

每个 Builder task 启动前，自动检索最相关文件：

**检索优先级:**

```
1. 依赖图 (dependency graph)
   → import / require 关系
   → 直接依赖的文件优先级最高

2. AST 分析 (tree-sitter)
   → 函数调用关系
   → 类型引用关系

3. 语义相似度 (embedding)
   → 对 task 描述做 embedding
   → 匹配代码库中最相似的文件

4. 历史关联
   → 同一个 spec 下之前改过的文件
   → 同一个 DAG 分支下的兄弟节点改过的文件
```

### 4.3 注入内容模板

每个 Builder task 收到的 context：

```markdown
## 当前任务
{task_description}

## Spec 相关部分
{spec_excerpt}          ← 不是全文，只截取当前 task 相关的段落

## 相关文件
{file_1_content}        ← 由 Context Retriever 选出，最多 5 个文件
{file_2_content}

## 编码规范
{coding_conventions}    ← 来自 wiki/conventions/

## 接口约定
{api_contract}          ← 如果 task 涉及 API

## 数据库相关
{db_schema_relevant}    ← 只取当前 task 涉及的表

## 禁止访问
- 不要自己去找其他文件
- 不要修改架构决策
- 如有疑问，报告 Reviewer，不要擅自决定
```

### 4.4 注入大小控制

| Builder Level | 最大 Context | 最多文件数 |
|---------------|-------------|-----------|
| Level 1 (Haiku) | 5k tokens | 3 个文件 |
| Level 2 (Sonnet) | 10k tokens | 5 个文件 |
| Level 3 (Opus) | 20k tokens | 不限（但建议 ≤ 10 个文件） |

---

## 5. 规则引擎替代 LLM

**核心原则: 能确定性地解决的问题，绝不用 LLM。**

### 5.1 替代矩阵

| 环节 | LLM 方案 (贵) | 规则引擎方案 (免费) | 何时用 LLM |
|------|-------------|-------------------|-----------|
| **Lint** | Claude 审代码风格 | ESLint / Ruff / Prettier | 从不 |
| **Type Check** | Claude 审类型 | TypeScript / mypy / pyright | 从不 |
| **Format** | Claude 格式化 | Prettier / Black / rustfmt | 从不 |
| **Security 初筛** | Claude 审漏洞 | Semgrep / Dependabot / npm audit | 仅 Semgrep 标记的高风险 diff |
| **Test 初跑** | Claude 看测试结果 | pytest / Jest / vitest | 仅测试失败后给 Builder 修 |
| **依赖检查** | Claude 审依赖 | Dependabot / Renovate / pip-audit | 从不 |
| **重复代码** | Claude 查重复 | jscpd / SonarQube | 从不 |
| **文档格式** | Claude 写文档 | markdownlint | LLM 写内容，规则引擎检查格式 |

### 5.2 Security 分层流程

```
每个 commit
    │
    ▼
┌─────────────────┐
│ Semgrep 扫描     │  ← 0 token，秒级
│ (规则引擎)       │
└────────┬────────┘
         │
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
  通过  中危  high/critical
    │    │    │
    │    ▼    ▼
    │  通知  阻塞 + 通知
    │  继续   │
    │        ▼
    │  ┌──────────────┐
    │  │ Security Agent│  ← 仅对 high/critical diff
    │  │ (LLM Sonnet)  │     ~500 tokens/diff
    │  └──────────────┘
    │        │
    └────────┼────────
             ▼
          继续/阻塞
```

### 5.3 Tester 分层流程

```
代码 commit
    │
    ▼
┌─────────────────┐
│ pytest / Jest    │  ← 0 token，先跑
│ (已有测试)       │
└────────┬────────┘
         │
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
  通过  失败  无测试
    │    │    │
    │    ▼    ▼
    │  ┌──────────────┐
    │  │ Builder 修复  │  ← LLM，但只修失败的
    │  └──────────────┘
    │         │
    │         ▼
    │      重新跑
    │
    ▼
  通过
```

---

## 6. Diff-based Prompting

### 6.1 原则

> 不给 Builder 全文，给 git diff + 周边上下文。

### 6.2 注入策略

```
Builder 收到的内容:

1. Git Diff (本次变更)
   git diff HEAD~1 -- {related_files}

2. Surrounding Context
   每个变更文件的前后 50-100 行
   不是整个文件

3. 相关的函数/类签名
   从 AST 中提取的被调用方/调用方

4. 接口契约
   API 的输入输出类型定义
```

### 6.3 对比

```
全文件注入:
  feature 涉及 5 个文件 × 平均 500 行 = 2500 行 ≈ 15k tokens

Diff + Context:
  diff 50 行 + 周边 100 行 × 5 文件 = 550 行 ≈ 3k tokens

省 80%，Builder 更聚焦 diff 本身，质量更高。
```

---

## 7. 缓存与方案复用

### 7.1 三层缓存

```
L1: 结果缓存
  Architect 输出（技术栈、DB schema）→ 同项目内复用
  Planner 输出（Spec）→ 不缓存（每个项目唯一）

L2: 方案模板缓存
  "auth pattern" → 认证方案模板
  "payment pattern" → 支付方案模板
  "crud pattern" → CRUD 方案模板
  "dashboard pattern" → Dashboard 方案模板

L3: 跨项目知识库
  已完成项目的 wiki/ → 新项目参考
  架构决策模式 → 加速 Architect
  DAG 拆解模式 → 加速 Decomposer
```

### 7.2 缓存命中流程

```
Task 进入 Builder
    │
    ▼
┌──────────────────┐
│ 匹配方案模板?     │──→ 命中 → 注入模板 + task context → 编码
│ (L2 cache)       │                    ↓
└────────┬─────────┘              成本: 极低
         │ 未命中
         ▼
┌──────────────────┐
│ 匹配跨项目案例?   │──→ 命中 → 注入案例 + task context → 编码
│ (L3 cache)       │                    ↓
└────────┬─────────┘              成本: 低
         │ 未命中
         ▼
    从头实现
    (正常流程)
```

### 7.3 缓存更新策略

- **成功完成** → 保存方案到 L2 cache
- **成功但有 Review 意见** → 更新方案到 L2 cache（带修正）
- **失败** → 不缓存，分析失败原因

---

## 8. 成本预估模型

### 8.1 小型 MVP（~25 个 DAG 节点）

| Agent | 调用次数 | 模型 | 单次 tokens | 单价 (每1M tokens) | 小计 |
|-------|---------|------|------------|-------------------|------|
| Planner | 2 | Opus | 8k | $15 | ~$0.24 |
| Architect | 3 | Opus | 6k | $15 | ~$0.27 |
| Decomposer | 2 | Sonnet | 5k | $3 | ~$0.03 |
| Reviewer (Plan) | 1 | Sonnet | 8k | $3 | ~$0.02 |
| Builder L1 (70%) | 17 | Haiku | 5k | $0.25 | ~$0.02 |
| Builder L2 (25%) | 6 | Sonnet | 10k | $3 | ~$0.18 |
| Builder L3 (5%) | 2 | Opus | 20k | $15 | ~$0.60 |
| Tester | 25 | Haiku | 3k | $0.25 | ~$0.02 |
| Reviewer (Code) | 1 | Sonnet | 15k | $3 | ~$0.05 |
| Security (LLM) | 1 | Sonnet | 5k | $3 | ~$0.02 |
| Integration | 1 | Sonnet | 10k | $3 | ~$0.03 |
| **总计** | | | | | **~$1.48** |

对比全量 Opus: ~$30-100。下降 **95%**。

### 8.2 中型 SaaS（~60 个 DAG 节点）

| 优化前（全强模型） | 优化后（三级路由） |
|-------------------|-------------------|
| ~$150-300 | ~$5-15 |

下降 **90%+**。

### 8.3 成本控制红线

- 单项目成本上限: $30（超出自动暂停，通知用户）
- 单 task 重试上限: 2 次（超出升级，不计费循环）
- 缓存命中可再降 30-50%

---

## 9. 集成到 Architecture

### 9.1 架构文档更新点

本文档是 `ARCHITECTURE.md` 的补充。以下模块需要根据本文档调整：

| ARCHITECTURE.md 模块 | 更新内容 |
|----------------------|---------|
| §6.1.2 Agent 定义 | Agent 增加 `model_tier` 字段 |
| §6.1.2 Builder Agent | 改为三级 Builder（L1/L2/L3）+ 升级逻辑 |
| §6.1.2 Tester Agent | 增加规则引擎先行 + LLM 仅在失败时介入 |
| §6.1.2 Security Agent | 增加 Semgrep 先行 + LLM 仅审高风险 diff |
| §6.2.1 容器生命周期 | Step 3 INJECT 增加 Context Retriever |
| §6.2.2 并行调度 | 增加缓存命中时的 task 跳过逻辑 |
| §9.1 核心技术栈 | 增加 Haiku/Sonnet/Opus 三级模型 + Semgrep + tree-sitter |

### 9.2 Agent 定义更新示例

```python
# 每个 Agent 定义增加 model_tier 和 context_limit

AGENT_DEFINITIONS = {
    "planner": {
        "model": "claude-opus-4-8",
        "model_tier": "premium",          # 不省钱
        "context_limit": 8000,
        "cache_ttl": None,                # 不缓存
        "max_calls_per_project": 3,
    },
    "architect": {
        "model": "claude-opus-4-8",
        "model_tier": "premium",
        "context_limit": 8000,
        "cache_ttl": "project",           # 同项目内缓存
        "max_calls_per_project": 5,
    },
    "builder_default": {
        "model": "claude-haiku-4-5",
        "model_tier": "cheap",
        "context_limit": 5000,
        "context_retriever": True,        # 启用 Context Retriever
        "max_files": 3,
        "upgrade_on_failure": "builder_complex",
    },
    "builder_complex": {
        "model": "claude-sonnet-4-6",
        "model_tier": "mid",
        "context_limit": 10000,
        "context_retriever": True,
        "max_files": 5,
        "upgrade_on_failure": "builder_expert",
    },
    "builder_expert": {
        "model": "claude-opus-4-8",
        "model_tier": "premium",
        "context_limit": 20000,
        "context_retriever": True,
        "max_files": 10,
        "upgrade_on_failure": "human",     # 升级到 Human
    },
    "tester": {
        "model": "claude-haiku-4-5",
        "model_tier": "cheap",
        "context_limit": 3000,
        "rule_first": True,                # 先跑 pytest，失败再 LLM
    },
    "security": {
        "model": "claude-sonnet-4-6",
        "model_tier": "mid",
        "context_limit": 5000,
        "rule_first": True,                # 先跑 Semgrep，高风险再 LLM
        "veto_power": True,
    },
}
```

---

## 附录：与现有文档的关系

| 文档 | 本文档如何关联 |
|------|--------------|
| `ARCHITECTURE.md` | 本文档是 §6 模块设计的性能/成本维度细化 |
| `AGENT_CONSTITUTION.md` | 宪法定义权力边界，本文档定义资源分配 |
| `CLAUDE.md` | 编码规范在此，Builder 的 context 注入包含它 |
| `wiki/conventions/` | Context Retriever 将此作为 Builder 必注入文件 |

---

> 这套优化方案的核心不是省钱，而是**把省下来的钱花在刀刃上**。
> Planner 和 Architect 用最好的模型，Builder 用最合适的模型，能不用 LLM 的地方绝不用。
