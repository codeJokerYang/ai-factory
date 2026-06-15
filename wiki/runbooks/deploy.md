# 部署手册

---

## 部署架构

```
GitHub (main branch)
    │
    ▼
GitHub Actions (CI) → 测试 → Lint → Build
    │
    ▼
[部署平台: Vercel / Railway / Docker / ...]
```

## 部署流程

### 1. 合并 PR 到 main

```bash
# PR 通过所有检查后，你来合并
# 推荐使用 Squash merge，保持 main 干净
```

### 2. 自动部署触发

合并到 main 后自动触发。监控进度：

```bash
# 查看 GitHub Actions 状态
gh run list --limit 5
gh run watch <run-id>
```

### 3. 验证部署

```bash
# 健康检查
curl -s https://your-app.com/api/health | jq .
# 预期: { "status": "ok" }

# 冒烟测试
curl -s https://your-app.com/api/v1/... | jq .
```

### 4. 验证功能

```bash
# 跑一遍关键用户路径
# 确保核心功能正常
```

---

## 回滚

### 立即回滚

```bash
# 回滚到上一个版本
git revert HEAD --no-edit
git push origin main
```

### 部署指定版本

```bash
git checkout <known-good-commit-sha>
git push origin main --force
```

---

## 环境变量

| 变量 | 用途 | 来源 |
|------|------|------|
| DATABASE_URL | 数据库连接 | Railway / Vercel |
| JWT_SECRET | JWT 签名密钥 | 手动生成 |
| API_KEY_XXX | 第三方服务密钥 | 各服务后台 |

---

## 常见问题

### 部署失败
1. 查看 GitHub Actions 日志
2. 常见原因: 环境变量缺失、数据库迁移失败、依赖安装失败
3. 修复后重新 push 触发

### 数据库迁移失败
1. 检查迁移脚本是否有冲突
2. 必要时手动连接数据库检查和修复

### 性能下降
1. 检查部署平台的资源使用
2. 查看最近的变更是否有性能影响
3. 检查是否有 N+1 查询或无限循环

---

## 部署检查清单

- [ ] CI 全部通过
- [ ] 手动验证 1 个核心功能
- [ ] 健康检查端点正常
- [ ] 日志无异常错误
- [ ] wiki/runbooks 已更新（如部署流程有变化）
