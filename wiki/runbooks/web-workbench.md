# 本地网页工作台

在项目根目录运行 `.\.venv\Scripts\python.exe -m orchestration.web`，打开 http://127.0.0.1:8765 。端口冲突时使用 `--port 8766`。停止服务使用 Ctrl+C。

模型凭据通过本地 `.env` 或环境变量配置，不从网页上传。可使用 `FACTORY_MODEL` 或 `FACTORY_PLANNER_MODEL` 等设置账户可用模型；这些配置在 Agent 实例化时读取。

运行失败后，在页面下载报告，检查 `errors`、`build_log`、`acceptance_report`。`implemented` 仅表示有代码证据，`missing` 或 `uncertain` 会阻止验收。预览只在等待人工验收期间运行，批准或拒绝后停止。

报告包含用户需求和生成源码，默认只在 `.factory/` 本地保存，不要未经检查公开。浏览器页面刷新可以继续查询当前任务；Python 服务重启后只保留磁盘报告，不会恢复执行。

GitHub 网络不可用不影响本地网页开发；远程发布需在网络恢复后从升级分支创建 PR。

## DeepSeek 本地环境

检测到 `DEEPSEEK_API_KEY` 且没有 Anthropic 凭据时自动使用 DeepSeek。多凭据环境使用 `FACTORY_PROVIDER=deepseek` 明确选择。默认 `deepseek-chat`，可用 `DEEPSEEK_MODEL` 覆盖。凭据只从进程环境或本地 dotenv 读取，不写入报告或代码。切换后需重启网页服务。

## 方案确认界面

默认展示产品摘要、用户要求、核心功能和本次范围。使用场景、成功标准、风险、实施计划与技术方案按需展开。完整 JSON 仍可在“完整运行报告”查看和下载；轮询不会重置已展开的详情。

## 界面设计

采用 Arctic editorial 视觉：冷灰全屏首屏、原创冰质素材、大字叠层，以及无卡片的需求和审批排版。四个缩略图切换同一雕塑的四种视角，支持键盘操作；触摸关闭视差，系统设置“减少动态效果”时关闭动画。仍使用原有 HTML/CSS/JavaScript 和 Python 服务，无新增运行时依赖。素材与生成提示词见 `orchestration/assets/README.md`。先前绿色 Figma 稿是历史版本，不代表当前页面。

静态图片路由需要新版本 Python 服务；仅刷新网页不能更新已加载的后端代码。已有任务时先完成当前审批，或在独立端口启动新版（例如 `--port 8771`），避免影响旧任务。

## 浏览器回归检查

测试需要 Playwright（开发工具，不是工作台运行依赖）及 Chromium/Chrome。启动本地工作台后运行：

```powershell
# Playwright 模块不在标准 node_modules 时指定安装目录
$env:PLAYWRIGHT_MODULE='<Playwright 模块目录>'
# 使用已安装的 Chrome；留空则使用 Playwright Chromium
$env:FACTORY_BROWSER='C:/Program Files/Google/Chrome/Application/chrome.exe'
$env:FACTORY_TEST_URL='http://127.0.0.1:8771'
node tests/web-ui-smoke.cjs
```

脚本在独立浏览器中拦截全部 job API，不会调用模型、提交真实任务或批准已有任务。截图保存于 `.factory/visual-review/`，包含四种尺寸和长方案状态。检查初始页图片与溢出、视角切换、减少动态效果、原始指令、文本安全、审批重试和报告下载。

Windows 沙箱的系统临时目录不可写时，可给 pytest 指定项目内尚未使用的临时目录：

```powershell
.venv/Scripts/python.exe -m pytest -q --basetemp=.factory/pytest-review-new -o cache_dir=.factory/pytest-cache
```
