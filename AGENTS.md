# AGENTS.md — 项目说明书

> 这是给 AI 看的"入职文档"。保持更新，每个新成员（AI）都会先读这个。

---

## 项目概述

- **项目名**: [你的项目名]
- **一句话**: [一句话说清这个项目是什么]
- **目标用户**: [谁在用，为什么用]
- **核心价值**: [解决什么痛点]

---

## 技术栈

- **前端**: [React/Vue/Next.js] + TypeScript + [Tailwind/...]
- **后端**: [Node.js/Python/Go] + [Prisma/SQLAlchemy/...] + [PostgreSQL/...]
- **部署**: [Vercel/Railway/Docker/...]
- **测试**: [Jest/Vitest/pytest/...]

---

## ⚠️ 强制执行规则

这些规则**不可违反**。每次操作前检查。

### 1. Git 边界

```
✅ 允许: 项目目录内所有文件（源码、wiki、配置）
✅ 允许: ~/.Codex/ 配置目录
❌ 禁止: 读写项目目录外的任何路径
❌ 禁止: 直接修改 .git/config
❌ 禁止: 修改 .env 文件内容（只能读取）
```

### 2. 变更可追溯

```
每次修改必须:
  1. 创建 feature branch: git checkout -b feat/xxx
  2. 实现 + 测试
  3. 清晰的 commit message（描述做了什么、为什么）
  4. 提 PR（不直接 push 到 main）
```

### 3. 测试不可跳过

```
任何新功能必须包含:
  - 单元测试（核心逻辑）
  - 集成测试（API 端点）
  - 边界条件测试（null、空、超时、异常）
```

### 4. 文档同步

```
功能变更后，检查并更新:
  - wiki/specs/ 下的功能规格
  - wiki/decisions/ 如果有架构变更
  - wiki/runbooks/ 如果有流程变化
  - ROADMAP.md 任务状态
```

---

## 编码规范

### 命名

- 文件: kebab-case (`user-auth.ts`)
- 函数/变量: camelCase (`getUserById`)
- 类/组件: PascalCase (`UserService`)
- 常量: UPPER_SNAKE (`MAX_RETRY_COUNT`)

### 目录结构

```
src/
├── components/     # UI 组件
├── hooks/          # 自定义 hooks
├── lib/            # 工具函数
├── pages/          # 页面/路由
├── services/       # 外部服务调用
├── types/          # TypeScript 类型
└── utils/          # 纯工具函数
```

### API 规范

- 路径: `/api/v1/resource`
- RESTful: GET/POST/PUT/DELETE
- 错误格式: `{ error: { code: string, message: string } }`
- 认证: Bearer token in Authorization header

### 错误处理

```typescript
// ✅ 推荐: 明确处理每个错误类型
try {
  await doSomething()
} catch (error) {
  if (error instanceof ValidationError) { ... }
  else if (error instanceof NetworkError) { ... }
  else { throw error } // 未知错误向上抛
}

// ❌ 避免: 吞掉错误或笼统 catch
try { ... } catch (e) { console.log(e) }
```

---

## 工作流命令参考

```
# 起步
@Codex "阅读 AGENTS.md，理解项目"
@Codex "查看 wiki/specs/xxx.md，实现这个功能"

# 编码
@Codex "基于 spec 设计 API 和数据模型"
[切换到 Codex] "给这个模块写全套测试"

# Review
@Codex /code-review

# 提交
git add . && git commit -m "feat: xxx" && git push origin feat/xxx
```

---

## 当前状态

维护在 `ROADMAP.md` 中。格式：

```markdown
## 进行中
- [ ] feat/xxx - [功能描述]

## 待做
- [ ] feat/yyy - [功能描述]

## 已完成
- [x] feat/zzz - [功能描述]
```

---

## MCP 配置

见 `.Codex/mcp.json`。当前可用的 MCP 工具：
- `filesystem`: 项目文件操作（限定在项目目录内）
- `github`: Issue/PR/Branch 管理
- `postgres`: 数据库操作
- `context7`: 知识库和代码索引检索

---

> ⚠️ 这个文件是项目的**核心约束文件**。
> 保持更新。AI 每次交互都会先读这里。
