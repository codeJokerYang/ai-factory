# 一人公司 × AI 编程助手 工作流

> **核心理念**: 你不是在写代码，你是在**指挥一个免费工程团队**。
> 你是架构师 + 决策者 + 质量把关人。AI 是你的团队。

---

## 目录

- [1. 角色分工](#1-角色分工)
- [2. 项目结构](#2-项目结构)
- [3. 工作流全景](#3-工作流全景)
- [4. AI 工具职责划分](#4-ai-工具职责划分)
- [5. MCP 协议层](#5-mcp-协议层)
- [6. LLM Wiki：项目集体记忆](#6-llm-wiki项目集体记忆)
- [7. LangChain 编排层](#7-langchain-编排层)
- [8. Git 栅栏：多层安全防线](#8-git-栅栏多层安全防线)
- [9. 快速开始](#9-快速开始)
- [10. 避坑指南](#10-避坑指南)

---

## 1. 角色分工

| 角色 | 工具 | 职责 |
|------|------|------|
| 🧠 **架构设计** | Claude Code | 技术方案、系统设计、架构审查 |
| 🔨 **快速执行** | Codex (OpenAI) | 写模板代码、批量重构、搬砖式 feature |
| 🔍 **Review / Debug** | Claude Code | 查 bug、代码审查、理解复杂逻辑 |
| ✅ **测试** | Codex | 生成测试用例、边界覆盖、Mock 编写 |
| 🔗 **编排** | LangChain | 多模型流水线、自动 Issue→PR、条件路由 |
| 🧩 **知识检索** | MCP + LLM Wiki | 结构化知识 + 代码索引 |

### 黄金法则

> **Claude Code 负责"想"，Codex 负责"做"。**
> Claude Code 理清需求和方案，Codex 或 Claude Code 子 agent 落地。

---

## 2. 项目结构

```
project/
├── .claude/
│   ├── mcp.json                     # MCP 服务配置
│   └── settings.json                # Claude Code 设置
├── .github/workflows/
│   └── ai-code-guard.yml            # CI 防线
├── scripts/
│   ├── guard.sh                     # Git 安全守卫
│   └── setup.sh                     # 一键初始化
├── wiki/                            # LLM Wiki（项目知识库）
│   ├── INDEX.md                     # 自动维护的索引
│   ├── decisions/                   # 架构决策记录 (ADR)
│   │   └── template.md
│   ├── specs/                       # 功能规格
│   │   └── template.md
│   ├── conventions/                 # 编码规范
│   │   └── coding-style.md
│   └── runbooks/                    # 运维手册
│       ├── deploy.md
│       └── pr-checklist.md
├── .gitignore
├── CLAUDE.md                        # 项目说明书（给 AI 看）
├── ROADMAP.md                       # 任务进度
└── README.md                        # 本文件
```

---

## 3. 工作流全景

```
你有一个想法
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 1: 需求 → Spec                    │
│  工具: Claude Code                       │
│  产物: wiki/specs/xxx.md                 │
│  动作: git commit                        │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 2: Spec → 任务分解                │
│  工具: Claude Code                       │
│  产物: ROADMAP.md + GitHub Issues        │
│  MCP: GitHub 自动创建 Issue              │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 3: 创建 Feature Branch             │
│  命令: git checkout -b feat/xxx          │
│  防线: scripts/guard.sh 检查             │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 4: 编码                            │
│  Claude Code: 核心逻辑 + 架构代码        │
│  Codex: 测试代码（同步进行）              │
│  两者都在 Git 栅栏内运行                  │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 5: Review + 修复                  │
│  Claude Code: /code-review              │
│  LangChain: 多模型审查流水线              │
│  动作: 修复 → commit → push              │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 6: 提 PR + 自动防线               │
│  GitHub Actions: 测试 + Lint + Wiki同步  │
│  Git Hooks: pre-push 防线               │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Step 7: 你合并（人在环上）               │
│  你是最后的决策者，不自动合并             │
└─────────────────────────────────────────┘
```

---

## 4. AI 工具职责划分

### Claude Code（架构师）

```
擅长:
  ✅ 长上下文理解 → 看完整个项目再动手
  ✅ 架构设计 → 追问、提替代方案、指出风险
  ✅ Debug → 给 bug + 相关代码，定位准确
  ✅ 代码质量 → 可维护的命名/结构/注释
  ✅ 技术方案 → spec、架构决策、系统设计

典型用法:
  @claude "基于这个 spec，设计 API 接口和数据模型"
  @claude /code-review
  @claude "这个 bug 的根因是什么？"
```

### Codex / GPT-4o（执行者）

```
擅长:
  ✅ 速度 → 秒出代码
  ✅ 测试 → 边界枚举、Mock、框架适配
  ✅ 模板代码 → CRUD、样板、批量重构
  ✅ 前端组件 → 快速出 UI

典型用法:
  "给这个函数写 20 个测试用例"
  "把这个组件改成 TypeScript"
  "生成 Prisma schema 对应的 CRUD API"
```

### LangChain（编排层）

```
定位: 不做 Claude/Codex 做的事，做它们做不到的事

场景一: 多模型流水线
  Claude 写 → GPT 审 → 汇总报告

场景二: 自动 Issue → PR
  读 Issue → 理解代码 → 实现 → 测试 → 自审 → 提 PR

场景三: RAG 增强
  项目大了之后，用 LlamaIndex 对代码库建向量索引
  AI 先查 Wiki（规则）→ 再查 RAG（参考）→ 开始写
```

---

## 5. MCP 协议层

MCP（Model Context Protocol）让 AI 不只是聊天，而是能**操作外部系统**。

### 配置示例 (`.claude/mcp.json`)

| MCP Server | 用途 |
|-----------|------|
| `server-postgres` | AI 直接读写数据库验证功能 |
| `server-github` | AI 自动管理 Issue/PR/Branch |
| `server-filesystem` | 限制 AI 只能在项目目录内操作 |
| `context7` | 项目知识库 + 轻量 RAG |

### AI 的实际调用链

```
你说："加一个用户登录功能"

Claude → MCP:GitHub → 读取 Issue #42 的 spec
Claude → MCP:Wiki    → 查知识库，了解现有认证架构
Claude → MCP:FS      → 在项目目录内创建 feature branch
Claude → 写代码
Codex  → 写测试
Claude → MCP:DB      → 跑 migration，验证表结构
Claude → MCP:GitHub  → 提 PR
```

---

## 6. LLM Wiki：项目集体记忆

### Wiki vs RAG

| | LLM Wiki | RAG |
|---|----------|-----|
| **知识来源** | 主动编写的结构化文档 | 自动索引代码/文档 |
| **质量** | 精炼、有观点、有决策背景 | 原始、可能有噪音 |
| **成本** | 需要写（AI 可帮你写） | 几乎为零 |
| **适用** | "为什么这样做"、"应该怎么做" | "这段代码在哪"、"类似功能有哪些" |

> **Wiki 是骨架，RAG 是肌肉。先建 Wiki，项目大了再补 RAG。**

### Wiki 五层结构

```
wiki/
├── decisions/       # 架构决策 → AI 知道"为什么"
│   └── 每个决策一个文件，记录背景、选项、决定、后果
├── specs/           # 功能规格 → AI 知道"做什么"
│   └── 每个功能一个文件，记录用户故事、接口、边界条件
├── conventions/     # 编码规范 → AI 知道"怎么写"
│   └── 命名、目录、API 风格、错误处理
├── runbooks/        # 运维手册 → AI 知道"怎么跑"
│   └── 部署、回滚、故障处理、PR 检查清单
└── knowledge/       # L3 已验证跨项目案例 → AI 知道"哪里做成过"
    └── projects/    # 全质量门通过后写入的脱敏、版本化 JSON
```

**所有 Wiki 文件随代码一起更新、一起 commit、一起版本控制。**

L3 案例只在 `build_cli "<idea>" --verify --gate2` 的 build、Reviewer、Security 和 Gate 2
全部通过后生成；Builder 仅在 L2 模板未命中时检索一个最相关案例。

---

## 7. LangChain 编排层

LangChain 的定位是**粘合剂**：编排、判断、串联多个工具。

### 使用场景

**场景一：多模型审查流水线**
```
Git Diff → Claude（架构审查）→ GPT-4o（测试覆盖分析）→ 汇总报告
```

**场景二：自动化 Issue → PR**
```
Issue → 读代码库(Wiki+RAG) → Claude 实现 → Codex 测试 → Claude 自审 → 提 PR
```

**注意**: LangChain 不替代 Claude Code/Codex。日常开发你在 Claude Code 里交互操作，LangChain 跑自动化批处理。

---

## 8. Git 栅栏：多层安全防线

### 第一层：项目入口检查 (`scripts/guard.sh`)
- 必须在项目目录内
- 必须在一个 Git 仓库内
- 外部路径访问全部拒绝

### 第二层：CLAUDE.md 强制规则
- 所有文件操作仅限于本仓库
- 变更必须关联 commit → PR
- 测试不可跳过
- 文档必须同步

### 第三层：Git Hooks
- `pre-push`: 测试 + Lint 必须通过
- `pre-commit`: 敏感文件检查（.env、credentials）

### 第四层：GitHub Actions（远程）
- 测试 + Lint 自动运行
- 敏感文件泄露检测
- Wiki 同步检查

---

## 9. 快速开始

### 1. 初始化项目

```bash
# 克隆或创建你的项目
git init my-project
cd my-project

# 复制此模板
cp -r /path/to/one-person-company-workflow/* .

# 运行初始化脚本
bash scripts/setup.sh
```

### 2. 配置 MCP

编辑 `.claude/mcp.json`，填入你的服务配置。

### 3. 安装 Git Hooks

```bash
cp scripts/guard.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### 4. 写第一个 Spec

```bash
# 用 Claude Code 写规格
@claude "帮我根据 wiki/specs/template.md 模板，写一个用户认证功能的 spec"
# 产物保存到 wiki/specs/user-auth.md
git add wiki/specs/user-auth.md && git commit -m "spec: add user auth spec"
```

### 5. 开始开发

```bash
git checkout -b feat/user-auth
# 让 Claude Code 实现
# 让 Codex 写测试
# Claude Code review
# git commit && git push && 提 PR
```

---

## 10. 避坑指南

| 坑 | 对策 |
|---|------|
| AI 写了代码你不理解 | 要求 AI 解释关键逻辑，至少理解数据流 |
| 过度依赖 AI 做决策 | 技术选型、架构你自己定，AI 只给建议 |
| 没有测试就上线 | 自动化测试是底线——一人公司没别人帮你背锅 |
| 同时开太多任务 | 一次一个 feature：做完→测试→合并→部署→下一个 |
| 文档过期 | AI 边写代码边更新 Wiki，CI 自动检查同步 |
| AI 的代码越来越乱 | 每次变更必须过 Claude Code review |
| 对外部服务直接操作 | MCP filesystem 限制在项目目录；API key 用环境变量不硬编码 |

---

## 许可

MIT — 拿去用，改，分发。

---

> 🤖 本项目工作流由 Claude Code 设计，旨在一人公司用 AI 实现"团队规模"的产出。
> 核心公式：**你的决策 × AI 的执行力 × 自动化系统 = 一人公司杠杆**
