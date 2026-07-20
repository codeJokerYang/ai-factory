# SPEC-003: L2/L3 缓存可观测性

- **状态**: 已完成
- **创建日期**: 2026-07-20
- **负责人**: Codex

---

## 概述

Builder 每次执行时记录一次结构化缓存观测，区分 L2 命中、L3 回退命中和完全未命中。
Build CLI 把不含业务文本的事件追加到本地版本化 JSONL，并提供人类可读与 JSON 汇总。

## 用户故事

> 作为维护者，我希望知道缓存是否真正命中、复用了多少上下文，以及成功案例是否越来越少依赖修复，以便用数据决定模板和案例库的后续优化。

## 验收标准

- [x] `ProjectState` 携带单次 `CacheLookup`，可随流水线序列化和恢复。
- [x] Builder 对 L2、L3 和 miss 三条路径均产生观测，不增加 LLM 调用。
- [x] L3 指标只保存哈希案例 ID，不保存项目名、需求文本、prompt 或生成代码。
- [x] CLI 以 best-effort 方式追加 lookup；指标失败不得阻断产品流水线。
- [x] L3 案例成功写入后，记录 repair、review 和 warning 计数。
- [x] 汇总输出总命中率、L3 回退命中率、复用 context token 估算和修复负担趋势。
- [x] 支持 `python -m orchestration.cache_metrics [path] [--json]`。

## 统计口径

- **总命中率** = `(L2 命中 + L3 命中) / 全部 lookup`。
- **L3 回退命中率** = `L3 命中 / (L3 命中 + miss)`；L2 命中不会触发 L3，因此不进入分母。
- **估算复用 tokens**：非 ASCII 字符按 1 token，ASCII 字符按每 4 个 1 token 向上取整。
  它衡量注入的缓存 context 体积，不是实际账单 token，也不宣称等量成本节省。
- **修复负担** = `repair_attempts + review_rounds + warning_count`。至少有两个成功案例时，
  比较前后两半（每半最多取最近 10 个）的平均负担，输出改善、持平或恶化。

## 数据格式与位置

默认路径为 `.factory/cache-metrics.jsonl`，目录由 `.gitignore` 排除。事件使用
`schema_version = 1`，分为：

- `lookup`: `source`、`match_ids`、`context_chars`、`estimated_reused_tokens`。
- `case_saved`: `repair_attempts`、`review_rounds`、`warning_count`。

两类事件都包含 UTC `recorded_at`。单行最大 16 KiB；读取时跳过损坏、未知版本、超长行和
符号链接。

## 边界条件

- 没有指标文件或文件为空：返回全零汇总。
- L2 命中：不查 L3，match ID 使用受控模板 ID。
- L3 命中：使用案例名 SHA-256 的短哈希，不写原始名称。
- 完全未命中：context 字符数和 token 估算均为 0。
- 指标路径不可写、为符号链接或单条事件异常：CLI 仅提示，不改变构建结果。
- 成功案例未通过既有质量门：拒绝写入 `case_saved` 事件。

## 非目标

- 不采集供应商实际 input/output token 或价格。
- 不上传遥测，不建立远程数据库或 HTTP API。
- 不用指标自动改写模板或删除案例。
- v1 不处理多进程同时追加；CLI 默认是单进程执行。

## 测试要点

- [x] 单元测试：token 估算、事件读写、汇总公式、趋势计算和质量门。
- [x] 集成测试：MockLLM 从 Planner 跑到 Builder 后可观察 L2/L3 来源。
- [x] 边界测试：缺失、空、损坏、未知版本、超长行、符号链接和不合格案例。

## 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-07-20 | 首次实现本地缓存观测与汇总 | Codex |
