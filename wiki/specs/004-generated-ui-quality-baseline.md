# SPEC-004: 生成 UI 质量基线

- **状态**: 已完成
- **创建日期**: 2026-08-14
- **负责人**: Codex

---

## 概述

为 Builder 生成的 Next.js 应用提供可复用的视觉底座、明确的 UI 质量契约和零 token 静态审计，
减少“能运行但像默认模板”的输出，并在 Gate 2 前暴露响应式、语义和无障碍退化。

## 用户故事

> 作为产品维护者，我希望新生成的应用默认具备清晰层级、响应式布局和可信的交互细节，以便 Gate 2 把精力放在产品判断，而不是反复修基础 UI。

## 验收标准

- [x] Tailwind 脚手架提供 canvas/surface/ink/muted/brand/line 语义色和 soft/lift 阴影。
- [x] 全局样式提供稳定的字体、背景、选区、键盘焦点和 reduced-motion 回退。
- [x] 提供 `ui-shell`、`ui-panel`、标题、正文、按钮、输入框和状态提示基础类。
- [x] RootLayout 使用 `zh-CN`、主题色 viewport 和最小全屏布局。
- [x] Builder UI 契约覆盖视觉方向、移动优先、语义层级、交互状态、表单、图片与真实文案。
- [x] Reviewer 同步审查视觉层级、响应式、无障碍与 loading/empty/error/success 状态。
- [x] Builder 后执行确定性 UI 审计，并写入 typed `ProjectState.ui_quality`。
- [x] CLI 与 Gate 2 展示审计结果；审计不新增 LLM 调用，也不单独阻断构建。

## 静态审计规则

| Code | 级别 | 规则 |
|------|------|------|
| `missing-page` | medium | 缺少 `app/page.tsx`（直接调用审计时的容错） |
| `missing-main` | medium | 主页面没有语义化 `<main>` |
| `missing-h1` | medium | 主页面没有清晰 `<h1>` |
| `missing-responsive` | medium | TSX/JSX 未出现 `sm/md/lg/xl/2xl` 响应式断点 |
| `clickable-static` | medium | `div/span` 直接绑定 `onClick` |
| `image-alt` | medium | `img/Image` 缺少 `alt` |
| `form-label` | medium | 表单控件缺少 label 或 aria label |
| `focus-visible` | low | 主动移除 outline 后未提供 focus-visible 或基础 UI 类 |

## 边界与非目标

- `None`、空文件列表或缺少页面时返回结构化结果，不抛异常。
- repair/revise 后重新审计，并清除上一次的过期 UI warning。
- 静态审计不推断颜色对比度、内容密度、品牌匹配或真实浏览器布局；这些继续由截图和 Gate 2 判断。
- 不引入组件库、图标包、外部字体或额外 LLM 调用。
- 不因 advisory UI finding 把可构建产品改为 FAILED。

## 测试

- [x] 单元测试：设计令牌、基础类、提示词与全部审计规则。
- [x] 集成测试：Planner→Architect→Decomposer→Gate 1→Builder 产出 UIQualityReport。
- [x] 边界测试：`None`、空列表、缺页和常见无障碍退化。
- [x] 真实 Next.js 样例 `npm run build` 与桌面/移动截图复验。

## 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-08-14 | 首次实现生成 UI 质量基线 | Codex |
