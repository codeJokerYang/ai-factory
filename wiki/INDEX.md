# Wiki 索引

> 自动维护。AI 每次操作前先查这个文件确定文档位置。
> 最后更新: 2026-08-14

---

## 架构决策 (decisions/)

| # | 标题 | 日期 | 状态 |
|---|------|------|------|
| [001](decisions/001-built-in-builder-template-cache.md) | L2 先采用内置只读模板注册表 | 2026-07-20 | 已采纳 |
| [002](decisions/002-versioned-validated-knowledge-cases.md) | L3 使用版本化、质量门控制的案例 JSON | 2026-07-20 | 已采纳 |
| [003](decisions/003-local-cache-metrics-jsonl.md) | 缓存指标使用本地版本化 JSONL | 2026-07-20 | 已采纳 |
| [004](decisions/004-deterministic-ui-baseline.md) | 生成 UI 使用确定性视觉基线与 advisory 静态审计 | 2026-08-14 | 已采纳 |

## 功能规格 (specs/)

| # | 标题 | 日期 | 状态 |
|---|------|------|------|
| [001](specs/001-builder-template-cache.md) | Builder L2 方案模板缓存 | 2026-07-20 | 已完成 |
| [002](specs/002-cross-project-knowledge-cache.md) | L3 跨项目知识案例缓存 | 2026-07-20 | 已完成 |
| [003](specs/003-cache-observability.md) | L2/L3 缓存可观测性 | 2026-07-20 | 已完成 |
| [004](specs/004-generated-ui-quality-baseline.md) | 生成 UI 质量基线 | 2026-08-14 | 已完成 |

## 编码规范 (conventions/)

- [coding-style.md](conventions/coding-style.md)

## 运维手册 (runbooks/)

- [deploy.md](runbooks/deploy.md)
- [builder-template-cache.md](runbooks/builder-template-cache.md)
- [knowledge-cache.md](runbooks/knowledge-cache.md)
- [cache-observability.md](runbooks/cache-observability.md)
- [ui-quality.md](runbooks/ui-quality.md)
- [pr-checklist.md](runbooks/pr-checklist.md)

## 跨项目知识 (knowledge/)

- [README.md](knowledge/README.md)

---

> 这个文件在每次 wiki 内容变更后由 CI 自动更新。
