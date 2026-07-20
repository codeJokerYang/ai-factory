# Builder 模板缓存维护手册

## 适用范围

用于新增或调整 `orchestration/template_cache.py` 中的 L2 内置方案模板。

## 新增模板

1. 先确认场景会在多个项目重复出现，且约束可脱离具体业务复用。
2. 为模板分配稳定、小写的 `id`，标题和 guidance 不包含客户数据、密钥或历史项目代码。
3. 关键词优先选择明确意图；避免单独使用“管理”“系统”“数据”等宽泛词。
4. guidance 保持短小、可执行，并与 Builder 的依赖白名单和系统硬约束一致。
5. 在 `tests/test_template_cache.py` 增加正向、误命中和数量上限测试。
6. 在 `tests/test_builder.py` 覆盖 prompt 注入；运行全量测试。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_template_cache.py tests/test_builder.py
.\.venv\Scripts\python.exe -m pytest -q
```

## Review 检查

- 英文关键词是否按完整词/短语命中，近似词是否会误命中。
- 中文关键词是否足够具体。
- 明确排除的 `mvp_out_of_scope` 不应触发任何模板。
- 新模板是否可能把注入数量挤过默认上限 2。
- guidance 是否要求了白名单外依赖、真实凭据或不安全客户端逻辑。
- 模板是否仍是方案约束，而不是未经验证的整段生成代码。

## 回退

删除或收窄有问题的模板/关键词即可；匹配不到模板时 Builder 自动回到原始 prompt 路径，无需数据迁移。
