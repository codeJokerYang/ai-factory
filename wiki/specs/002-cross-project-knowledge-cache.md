# SPEC-002: L3 跨项目知识案例缓存

- **状态**: 已完成
- **创建日期**: 2026-07-20
- **负责人**: Codex

---

## 概述

流水线把通过全部质量门的项目沉淀为脱敏、版本化的知识案例。新项目在没有命中 L2 内置模板时，
可检索一个最相关的历史案例并把精简架构摘要注入 Builder prompt。

## 用户故事

> 作为独立开发者，我希望已成功项目的架构经验能安全复用到相似新项目，以便减少重复推理，同时避免复制历史代码或敏感数据。

**验收标准**:

- [x] 只有 build、Reviewer、Security 和 Gate 2 全部通过且无流水线错误时才允许写入。
- [x] 案例仅保存项目摘要、核心功能与架构摘要；不保存代码、用户故事或目标用户。
- [x] 邮箱、手机号、私钥、Bearer token、密钥赋值和长 token 在写入与读取两侧脱敏。
- [x] 使用版本化 JSON、项目名哈希文件名和同目录原子替换。
- [x] 读取时跳过损坏、超限、版本不兼容和符号链接案例。
- [x] 当前项目自身不参与匹配；结果稳定，单次最多返回一个案例。
- [x] L2 命中时不检索 L3；L2 未命中时才注入 L3。
- [x] L3 context 不超过 4000 字符，并明确标记为不可信参考数据。

## 接口定义

内部 Python 接口，无新增 HTTP API：

```python
path = save_knowledge_case(state)
matches = match_knowledge_cases(product_spec, limit=1)
context = render_knowledge_context(matches)
```

默认存储目录：`wiki/knowledge/projects/`。每个文件符合 `KnowledgeCase.schema_version = 1`。

## 质量门

满足以下全部条件才可保存：

- `product_spec`、`architecture` 和 `generated_files` 存在。
- `build_passed is True`。
- `code_review.passed is True`。
- `security_report.passed is True`。
- `phase == GATE_2_APPROVED` 且 `gate_2_approved is True`。
- `errors` 为空。

因此，CLI 需要同时使用 `--verify --gate2`，且 Reviewer/Security 不依赖人工 override，才会生成可信案例。

## 匹配规则

- 输入只使用当前项目名、一句话摘要、核心功能和 MVP in-scope。
- 英文按规范化词匹配；中文生成二元和三元片段。
- 过滤常见的泛化词，至少共享两个有效 term。
- 使用二值 term 余弦相似度排序，同分时按共享数量和项目名稳定排序。
- 强制最多返回一个案例，防止 prompt 膨胀和上下文污染。

## 边界条件

- `ProductSpec` 为 `None`、limit 为 0、缓存目录不存在：返回空结果。
- 案例损坏、超过 64 KiB 或 schema 版本不兼容：跳过；人工编辑的合法案例会在读取时再次脱敏。
- 当前项目名与案例相同：跳过，保持“跨项目”语义。
- 缓存写入失败或项目不满足质量门：不影响已通过 Gate 2 的产品结果，只输出说明。
- 没有 L2/L3 命中：保持原始 Builder prompt 路径。

## 非目标

- 不保存或复用历史生成代码。
- 不使用 embedding、向量数据库或额外 LLM 调用。
- 不自动修改 L2 内置模板。
- 不实现跨仓库、云端或多租户知识共享。

## 测试要点

- [x] 单元测试：质量门、脱敏、原子文件格式、容错读取、匹配排序和预算上限。
- [x] 集成测试：Builder 的 L2→L3 回退和 L2 优先级。
- [x] 全链路测试：Planner→Architect→Decomposer→Gate 1→Builder 注入历史案例。
- [x] 边界测试：null、空目录、零 limit、损坏/超限/旧版本文件和当前项目排除。

## 依赖

- 依赖 SPEC-001 的 L2 模板匹配和 Builder prompt 注入接口。
- 无新增第三方依赖或环境变量。

## 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-07-20 | 首次实现只读检索 + 质量门写入的 L3 案例缓存 | Codex |
