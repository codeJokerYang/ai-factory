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

采用浅色工作画布、深绿侧栏、独立输入与结果面板，支持窄屏单列布局及四阶段进度提示。侧栏可跳转至工作台、执行和报告；原有审批、下载与错误提示保留。设计参考：https://www.figma.com/design/BmPU7CPHdAVjJDhkiKt70U 。
