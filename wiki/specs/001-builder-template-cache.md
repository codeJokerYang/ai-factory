# SPEC-001: Builder L2 方案模板缓存

- **状态**: 已完成
- **创建日期**: 2026-07-20
- **负责人**: Codex

---

## 概述

Builder 在生成代码前，根据 Product Spec 确定性匹配常见方案模板，并把受控的工程约束注入
prompt。匹配不调用 LLM；未命中时沿用原始生成路径。

## 用户故事

> 作为独立开发者，我希望常见的认证、支付、CRUD 和 Dashboard 需求能自动带上经过审查的实现约束，以便减少重复推理和常见错误。

**验收标准**:

- [x] 内置 `auth`、`payment`、`crud`、`dashboard` 四类模板。
- [x] 匹配只读取 Product Spec，按命中关键词数排序，同分时结果稳定。
- [x] 单次最多注入两个模板，控制 prompt 体积。
- [x] 英文关键词按完整词或短语匹配，避免 `auth` 误命中 `authoring`。
- [x] `mvp_out_of_scope` 不参与匹配，避免为明确排除的功能注入模板。
- [x] 空值、无关需求或零限制返回空结果，不改变 Builder 原始 prompt 路径。
- [x] 模板内容来自受控注册表，不回显用户输入或历史项目代码。

## 接口定义

内部 Python 接口，无新增 HTTP API：

```python
matches = match_templates(product_spec, limit=2)
context = render_template_context(matches)
prompt = build_prompt(spec_json, arch_json, context)
```

`TemplateMatch.score` 等于该模板命中的不同关键词数量。结果先按分数降序，再按模板注册顺序排序。

## 边界条件

- `ProductSpec` 为 `None`：不匹配模板。
- `limit <= 0`：不匹配模板；更大的调用方参数也不能突破两个模板的安全上限。
- 英文大小写或全角字符：NFKC + casefold 后匹配。
- 同时命中多类模板：只注入得分最高的两个。
- 仅在 `mvp_out_of_scope` 出现的能力：不触发模板。
- 未命中：不向 prompt 添加 L2 段落。

## 非目标

- 不缓存 Planner 输出。
- 不自动保存生成代码为模板。
- 不读取其他项目的 wiki、代码或凭据。
- 不实现 L3 跨项目知识库；该能力需另行设计数据来源、脱敏、质量门和失效策略。

## 测试要点

- [x] 单元测试：排序、Unicode 规范化、词边界、数量限制和渲染。
- [x] 集成测试：Builder 命中时注入模板，未命中时保持原路径。
- [x] 边界测试：`None`、空字段、零限制和近似英文词。

## 依赖

- 现有 `ProductSpec` 和 Builder prompt 接口。
- 无新增第三方依赖、环境变量或持久化存储。

## 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-07-20 | 首次实现内置只读 L2 模板缓存 | Codex |
