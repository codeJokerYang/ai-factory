# ROADMAP

> 项目任务进度。每次变更后更新。
> AI 在接手任务前先查这个文件，了解当前状态。

---

## 🔄 进行中

| # | 任务 | 分支 | 状态 | 关联 Spec |
|---|------|------|------|-----------|
| 1 | v1 + B1 + B2 | `main` | ✅ 已并入 main，GitHub Actions CI 绿 | `wiki/specs/*` |
| 2 | Builder 自愈 B3（构建门失败→自动修复一次→复验） | `feat/builder-self-repair` | 已实现+测试，待 push/PR | - |

---

## 📋 待做

| # | 任务 | 优先级 | 预估 | 关联 Issue |
|---|------|--------|------|-----------|
| 2 | Builder 增强：PDF 解析（pdfjs）、真 Supabase 接入、生成更多文件 | 中 | - | - |
| 4 | 升级 `SequentialRunner` → LangGraph（并行 DAG / 断点续跑 / 条件路由） | 中 | - | - |
| 5 | 后置 agent：Reviewer / Security / Tester / Ambiguity Resolver / Integration | 低 | v2+ | - |

---

## ✅ 已完成

| # | 任务 | 完成日期 | PR |
|---|------|---------|-----|
| 0 | Phase 0 Foundation（文档 / CI / 宪法 / 架构 / 成本模型） | 2026-06-15 | - |
| 1 | v1 Plan pipeline（Planner→Architect→Decomposer→Gate 1）+ 离线测试 12 passed | 2026-06-15 | - |
| 2 | Provider 兼容（ANTHROPIC_BASE_URL/AUTH_TOKEN + FACTORY_MODEL）；DeepSeek 实跑验证 | 2026-06-15 | - |
| 3 | 稳定性验证 3/3（固定栈/DAG 合法 100%；DAG 粒度 8–20 波动） | 2026-06-15 | - |
| 4 | Week 3 Builder：whole-project 生成 + 脚手架 + 本地 preview（next build 通过，dev 可跑，截图确认） | 2026-06-15 | - |
| 5 | 自动构建门 verify.py（npm build 门，逮编译/类型错误）+ build_cli --verify；31 测试，集成验证逮住 tsconfig 回退 | 2026-06-15 | - |
| 6 | Gate 2 自动化：gate2.py（摘要+审批）+ preview.py（dev server+playwright 截图）+ --gate2；禁 alert；38 测试 | 2026-06-15 | - |
| 7 | Builder 自愈 B3：构建门失败→编译错误回灌 Builder 修复→复验（build_and_verify + Builder.repair）；44 测试 | 2026-06-15 | - |

---

## 🐛 已知 Bug / 限制

| # | 描述 | 严重程度 | 备注 |
|---|------|---------|------|
| 1 | ~~生成 app 用 `alert()` 阻塞自动化~~ 已解决 | - | Builder prompt 禁 alert/confirm/prompt + preview 截图前注入屏蔽 |
| 2 | v1 Builder mock 数据、无真实 PDF 解析与 Supabase | 中 | 设计内（local-first 证明闭环） |

---

## 💡 想法池

- L2/L3 方案模板缓存（COST_OPTIMIZATION.md §7）
- 跨项目知识库复用（Phase 4）
- Decomposer 粒度约束（目标 12–18 节点）

---

## v1 运行方式

```bash
# 离线测试（无需 API key）
.venv/Scripts/python.exe -m pytest -q

# Plan only（idea → spec/architecture/tasks.json + Gate 1）
python -m orchestration.cli "<idea>"

# Build（idea → Plan → Builder → generated/<project>/ 可跑 Next.js app）
python -m orchestration.build_cli "<idea>"
python -m orchestration.build_cli "<idea>" --verify   # 生成后自动跑 npm build 门
python -m orchestration.build_cli "<idea>" --gate2    # + 启 dev server / 截图 / Gate 2 审批
cd generated/<project> && npm install && npm run dev   # http://localhost:3000

# Provider 切换（默认 Claude；示例 DeepSeek）:
#   ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
#   ANTHROPIC_AUTH_TOKEN=<key>   FACTORY_MODEL=deepseek-chat
```

---

> 格式参考: 在 AI 的帮助下维护。每个 Sprint 结束时更新。
