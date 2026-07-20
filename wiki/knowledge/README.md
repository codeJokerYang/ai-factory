# 跨项目知识案例

`projects/` 由完整构建流水线写入脱敏、版本化的 L3 案例 JSON。案例必须通过 build、Reviewer、
Security 与 Gate 2；它们随代码一起 review 和版本控制。

维护与故障处理见 [L3 知识缓存运行手册](../runbooks/knowledge-cache.md)。

缓存命中事件和案例质量计数保存在本地 `.factory/cache-metrics.jsonl`，不与案例 JSON 混放、
不进入版本控制。统计口径和排障见
[缓存可观测性运行手册](../runbooks/cache-observability.md)。
