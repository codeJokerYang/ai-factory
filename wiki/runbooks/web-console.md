# 本地 Web 控制台运行手册

## 启动

```bash
python -m orchestration.web_console
```

默认地址：`http://127.0.0.1:3110`。

指定端口：

```bash
python -m orchestration.web_console --port 3111
```

## 验证流程

1. 页面顶部应显示“本地编排器在线 · 无需 API Key”。
2. 点击一个示例或输入不超过 500 字符的产品想法。
3. 点击“运行完整流水线”。
4. 确认 Planner 到 Security 共七个阶段完成。
5. 依次查看产品规格、任务 DAG、生成文件和质量报告。
6. 使用键盘 Tab 检查示例、提交、结果标签和复制按钮。

## API 快速检查

```bash
curl http://127.0.0.1:3110/api/health
```

预期返回：

```json
{"status":"ok","mode":"mock","api_key_required":false}
```

## 常见问题

### 地址已被占用

使用 `--port` 换一个端口；不要终止无法确认归属的进程。

### 页面显示编排器未连接

确认启动命令仍在运行，并直接访问 `/api/health`。控制台静态文件和 API 必须来自同一个端口。

### Mock 结果与真实模型不同

这是预期行为。控制台验证编排契约、错误边界和展示流程；真实模型运行继续使用：

```bash
python -m orchestration.build_cli "<一句话想法>" --verify --gate2
```
