# ADR-005：本地控制台使用标准库 HTTP 边界与真实 Agent Mock 流水线

> 日期：2026-08-15  
> 状态：已采纳

## 背景

项目运行时以 Python 编排为核心，仓库没有长期运行的 Web API。为测试界面单独引入 FastAPI、
Flask 或 Node 后端会增加安装与维护成本；只在浏览器中模拟阶段完成，又无法证明现有 Agent 链
确实可运行。

## 决定

采用 Python 标准库 `ThreadingHTTPServer` 提供仅绑定本机的控制台：

- 静态前端由同源服务器提供。
- `POST /api/runs` 创建独立 `ProjectState` 和 `MockLLM`。
- 每个阶段通过现有 `run_step_safely` 调用生产 Agent 类。
- 响应包含结构化 Spec、Architecture、DAG、GeneratedFile 和质量报告。
- 默认监听 `127.0.0.1:3110`，并设置 CSP、`nosniff` 与 `no-store`。

## 结果

### 正面

- 不增加运行时依赖，也不要求 API Key。
- 控制台和测试使用同一编排代码路径，避免“演示成功、实际失败”。
- HTTP 层可以通过标准库客户端执行真实集成测试。

### 代价

- 标准库服务器只面向本地开发，不提供生产认证、任务队列或流式日志。
- Mock 响应是确定性的，不能用于判断真实模型输出质量。

## 后续

需要真实 LLM 的异步运行、历史记录或多人访问时，再单独设计持久化 API 和任务执行服务；不在
本地验证控制台上逐步堆叠生产职责。
