# ROADMAP

> 项目任务进度。每次变更后更新。
> AI 在接手任务前先查这个文件，了解当前状态。

---

## 🔄 进行中

| # | 任务 | 分支 | 状态 | 关联 Spec |
|---|------|------|------|-----------|
| 1 | v1 + B系列 + 粒度 + 保真度 + Reviewer(+自愈) + Security | `main` | ✅ 已并入 main，CI 绿 | `wiki/specs/*` |
| 2 | 生成 UI 质量基线（设计令牌 + UI 契约 + 静态审计） | `feat/ui-quality-baseline` | PR #16 草稿；139 测试 + Next build + 桌面/移动视觉复验通过，CI 绿 | `wiki/specs/004-generated-ui-quality-baseline.md` |
| 3 | AI Factory 本地可测试控制台（真实 Agent + MockLLM + HTTP API） | `feat/ui-quality-baseline` | PR #16 草稿；150 测试 + 浏览器交互与布局复验通过，CI 绿 | `wiki/specs/005-testable-web-console.md` |

---

## 📋 待做

| # | 任务 | 优先级 | 预估 | 关联 Issue |
|---|------|--------|------|-----------|
| 5 | 后置 agent：Tester / Ambiguity Resolver / Integration | 低 | v2+ | - |

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
| 8 | Decomposer 粒度约束：prompt 目标 12–18 + check_granularity 软校验 + state.warnings（非阻塞）；49 测试 | 2026-06-15 | - |
| 9 | 保真度：依赖白名单（pdfjs-dist / @supabase/supabase-js，固定版本）+ scaffold 合并 package.json + Supabase env 降级 mock；54 测试 | 2026-06-15 | - |
| 10 | Reviewer agent：Gate 2 前自动代码审查（CodeReview/ReviewIssue + advisory，high 入 warnings + Gate 2 摘要）；60 测试 | 2026-06-15 | - |
| 11 | Reviewer 自愈闭环：否决→Builder.revise→复审（review_and_revise + revise_prompt），≤1 轮后升级 Gate 2；review 先于构建门；66 测试 | 2026-06-15 | - |
| 12 | Security agent：规则扫描（密钥/注入/前端泄露，0 token）+ 高危再 LLM + 一票否决（Gate 2 人工 override）；76 测试 | 2026-06-15 | - |
| 13 | LangGraph 升级：LangGraphRunner（单通道，条件路由短路 + checkpointer 接口）+ make_runner 切换（FACTORY_RUNNER=langgraph）；agent/schema 不变；79 测试 | 2026-06-15 | #10 |
| 14 | AI Code Guard 升级 Node.js 24 actions + `contents: read` 最小权限；81 测试 | 2026-07-20 | #13 |
| 15 | Builder L2 方案模板缓存：确定性匹配 + prompt 注入；91 测试 | 2026-07-20 | #11 |
| 16 | L3 跨项目知识案例缓存：质量门 + 脱敏 + 检索回退；108 测试 | 2026-07-20 | #12 |
| 17 | L2/L3 缓存可观测性：命中率 + context token 估算 + 修复负担趋势；114 测试 | 2026-07-20 | #15 |
| 18 | 生成文件路径安全：阻断目录穿越/绝对路径/符号链接越界，规范 npm 包名；构建门超时与 npm 缺失可诊断 | 2026-07-20 | #14 |
| 19 | 流水线韧性：统一 Runner 异常边界、终止状态，LLM 有限重试/超时，LangGraph 编译复用 | 2026-07-20 | #14 |

---

## 🐛 已知 Bug / 限制

| # | 描述 | 严重程度 | 备注 |
|---|------|---------|------|
| 1 | ~~生成 app 用 `alert()` 阻塞自动化~~ 已解决 | - | Builder prompt 禁 alert/confirm/prompt + preview 截图前注入屏蔽 |
| 2 | v1 Builder mock 数据、无真实 PDF 解析与 Supabase | 中 | 设计内（local-first 证明闭环） |

---

## 💡 想法池

- 架构模板自动优化（Phase 4）

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
python -m orchestration.build_cli "<idea>" --verify --gate2  # 全门通过后沉淀 L3 案例
cd generated/<project> && npm install && npm run dev   # http://localhost:3000

# Provider 切换（默认 Claude；示例 DeepSeek）:
#   ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
#   ANTHROPIC_AUTH_TOKEN=<key>   FACTORY_MODEL=deepseek-chat
```

---

> 格式参考: 在 AI 的帮助下维护。每个 Sprint 结束时更新。
