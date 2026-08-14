# 生成 UI 质量运行手册

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_ui_quality.py tests/test_pipeline_mock.py tests/test_gate2.py
.\.venv\Scripts\python.exe -m pytest -q
```

真实 UI 复验继续使用完整构建门：

```powershell
python -m orchestration.build_cli "<idea>" --verify --gate2
```

Gate 2 前会显示 `UI Quality` 摘要，并在 dev server 就绪后生成截图（Playwright 可用时）。

## 基础类

- 布局：`ui-shell`、`ui-panel`
- 文字：`ui-kicker`、`ui-title`、`ui-copy`
- 操作：`ui-button-primary`、`ui-button-secondary`
- 表单/反馈：`ui-field`、`ui-status`

这些类提供视觉下限，不限制 Builder 使用额外 Tailwind class 做产品化组合。

## 处理审计发现

- `missing-main` / `missing-h1`：补语义结构与唯一主要标题。
- `missing-responsive`：先保证手机单列，再在 `sm/md/lg` 扩展。
- `clickable-static`：换成 `button` 或语义 link。
- `image-alt`：内容图写清用途；装饰图使用 `alt=""`。
- `form-label`：优先真实 `<label htmlFor>`，无可见标签时使用 `aria-label`。
- `focus-visible`：不要裸删 outline；使用基础控件类或补 `focus-visible:ring-*`。

## 人工视觉检查

静态审计通过不等于视觉完成。桌面与移动尺寸至少检查：

1. 首屏是否能看懂产品、主要任务和首要操作。
2. 内容密度与留白是否平衡，是否出现横向滚动或被遮挡控件。
3. 空、加载、成功、失败和 disabled 状态是否清晰。
4. 键盘 Tab 顺序、焦点可见性、表单 label 和错误反馈是否可用。
5. 是否存在模板化卡片堆叠、无意义渐变、emoji 图标或含糊占位文案。

## 回退

如视觉基线影响特定项目，可在该项目 `app/globals.css` 中覆盖语义变量；不要删除全局 focus 与
reduced-motion 回退。若静态规则误报，优先收窄 `orchestration/ui_quality.py` 的规则并增加回归测试。
