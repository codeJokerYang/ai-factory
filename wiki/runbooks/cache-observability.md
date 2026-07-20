# 缓存可观测性运行手册

## 查看汇总

```powershell
python -m orchestration.cache_metrics
python -m orchestration.cache_metrics --json
```

读取其他导出文件：

```powershell
python -m orchestration.cache_metrics D:\path\cache-metrics.jsonl
```

默认文件为 `.factory/cache-metrics.jsonl`，首次运行 Builder CLI 后自动创建；该目录不进入 Git。

## 指标解释

- 总命中率同时包含 L2 与 L3。
- L3 回退命中率只在 L2 未命中的样本中计算。
- `复用 context tokens` 是字符启发式估算，仅用于相对比较，不是账单或真实成本节省。
- 修复负担趋势比较成功案例前后样本的 repair、review 和 warning 总量，越低越好。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_cache_metrics.py tests/test_pipeline_mock.py
.\.venv\Scripts\python.exe -m pytest -q
```

## 故障处理

- 文件不存在或为空：汇总显示 0，不影响构建。
- 出现损坏/旧版本/超长行：读取器跳过该行，其他事件继续参与统计。
- 指标路径是符号链接：读侧返回空，写侧拒绝，避免写出本地边界。
- Build CLI 提示指标未记录：检查 `.factory/` 写权限；产品输出与质量门结果仍有效。
- 需要清零：确认目标是项目内 `.factory/cache-metrics.jsonl` 后，先备份或移动该文件；下次运行会重建。

## 隐私检查

lookup 事件不得包含 idea、Product Spec、prompt、生成代码或原始 L3 项目名。L2 只使用受控模板 ID，
L3 使用短哈希案例 ID；成功案例事件只含非负计数。

## 未来迁移

如果启用并发 worker，不要继续依赖无锁 JSONL 追加；改用带幂等事件 ID 的 SQLite 或遥测服务，
并保持现有 schema 版本、统计公式和 best-effort 非阻塞语义。
