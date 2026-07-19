# PR 检查清单

---

## 提交前（你自己检查）

- [ ] 代码实现了 spec 中定义的所有验收标准
- [ ] 测试全部通过：`npm test`
- [ ] Lint 全部通过：`npm run lint`
- [ ] 没有遗留的 console.log / debugger
- [ ] 没有硬编码的密钥或敏感信息
- [ ] commit message 清晰描述了变更

## AI Review 后（必需步骤）

- [ ] Claude Code `/code-review` 通过（无严重问题）
- [ ] 所有 review 意见已处理或解释
- [ ] Codex 测试覆盖了新功能的边界条件

## 文档

- [ ] wiki/specs/ 已更新（如有功能变更）
- [ ] wiki/decisions/ 已补充（如有架构决策）
- [ ] ROADMAP.md 已更新任务状态

## 部署前

- [ ] 数据库迁移脚本已准备好且可回滚
- [ ] 环境变量已配置（如有新增）
- [ ] 已知会下一版本需要的手动操作

## CI 基线维护

- `actions/checkout@v6`：Node.js 24 runtime；GitHub-hosted runner 可直接使用。
- `actions/setup-python@v6`：Node.js 24 runtime；自托管 runner 需至少 `v2.327.1`。
- workflow 顶层保持 `permissions: contents: read`；新增写操作时按 job 最小范围单独授权。
- action major 升级后，除本地测试外必须在目标分支实际运行一次 `AI Code Guard`，确认测试和敏感文件检查均通过且无 runtime 弃用提醒。

---

## PR 描述模板

```markdown
## 概述
[一句话描述]

## 变更内容
- [变更点 1]
- [变更点 2]

## 测试
- [ ] 单元测试: [描述]
- [ ] 集成测试: [描述]
- [ ] 手动测试: [操作步骤和结果]

## 相关
- Spec: wiki/specs/xxx.md
- Issue: #42

## 部署注意
[如有数据库迁移、环境变量等，在此说明]

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
