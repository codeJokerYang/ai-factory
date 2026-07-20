# L3 知识缓存运行手册

## 生成可信案例

运行完整验证和人工 Gate 2：

```powershell
python -m orchestration.build_cli "<idea>" --verify --gate2
```

只有构建、Reviewer、Security 和 Gate 2 全部通过且流水线无错误时，才会在
`wiki/knowledge/projects/` 写入 `case-<hash>.json`。同一项目再次成功会原子更新同一文件。

## 日常检查

提交案例前检查：

1. JSON 的 `schema_version` 为 `1`。
2. 只含产品摘要、核心功能和架构摘要，没有 `generated_files`、用户故事或目标用户。
3. 没有邮箱、手机号、token、私钥或凭据。
4. 案例确实来自全质量门通过的项目。
5. 运行全量测试和敏感文件检查。

```powershell
Get-ChildItem wiki/knowledge/projects -Filter case-*.json
.\.venv\Scripts\python.exe -m pytest -q tests/test_knowledge_cache.py
.\.venv\Scripts\python.exe -m pytest -q
```

## 故障行为

- 目录不存在：Builder 当作零案例，继续正常生成。
- 单个文件损坏、超限、版本不兼容或为符号链接：跳过该文件；合法文件在读取时仍会再次脱敏。
- 写入失败：CLI 说明未缓存，但 Gate 2 成功结果不回滚。
- 没有足够相似度：不注入 L3，沿用原始 prompt。

## 失效与回滚

发现案例过期或不安全时，通过独立 PR 删除对应 `case-*.json`；不要直接手工改成另一项目的内容。
如果需要整体关闭 L3，可回退 Builder 的 L3 回退调用，缓存文件本身不会参与执行。

## Schema 升级

新增或改变字段时：

1. 提升 `SCHEMA_VERSION`。
2. 明确旧版本是迁移还是跳过，不得静默误读。
3. 同步 SPEC/ADR 和本手册。
4. 增加旧版本、损坏文件和迁移边界测试。
