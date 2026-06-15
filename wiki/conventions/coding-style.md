# 编码规范

---

## 命名

### 文件

```
✅ 正确: user-auth.ts, payment-service.ts, login-form.tsx
❌ 错误: UserAuth.ts, paymentService.ts, loginForm.tsx
```

- 文件名: **kebab-case**
- 组件文件例外: `LoginForm.tsx`（组件本身是 PascalCase，文件名与之保持一致）

### 变量/函数: camelCase

```typescript
✅ getUserById()
✅ isLoading
✅ maxRetryCount
```

### 类/组件: PascalCase

```typescript
✅ UserService
✅ LoginForm
✅ PaymentController
```

### 常量: UPPER_SNAKE

```typescript
✅ MAX_RETRY_COUNT = 3
✅ API_BASE_URL = 'https://...'
```

---

## 目录结构

```
src/
├── components/        # UI 组件（每个组件一个目录）
│   └── button/
│       ├── index.tsx
│       └── button.test.tsx
├── hooks/             # 自定义 React hooks
├── lib/               # 工具函数和库封装
├── pages/             # 页面/路由入口
├── services/          # 外部 API 调用
├── types/             # TypeScript 类型定义
└── utils/             # 纯函数工具集
```

---

## TypeScript

- 所有新代码使用 TypeScript
- 禁止 `any`（除非有明确理由并注释）
- 优先使用 `interface` 而非 `type`（除非需要 union/intersection）

```typescript
// ✅
interface User {
  id: string
  name: string
}

// ❌ 避免（除非有理由）
const data: any = fetchData()
```

---

## 错误处理

```typescript
// ✅ 明确处理每个错误类型
try {
  await doSomething()
} catch (error) {
  if (error instanceof ValidationError) {
    return { ok: false, code: 'VALIDATION_ERROR' }
  }
  if (error instanceof NetworkError) {
    // 重试或降级
    return retry(() => doSomething())
  }
  // 未知错误向上抛
  throw error
}

// ❌ 禁止
try { ... } catch (e) {}
try { ... } catch (e) { console.log(e) }
```

---

## API 设计

### 路径规范

```
GET    /api/v1/users          → 列表
POST   /api/v1/users          → 创建
GET    /api/v1/users/:id      → 详情
PUT    /api/v1/users/:id      → 更新
DELETE /api/v1/users/:id      → 删除
```

### 响应格式

```typescript
// 成功
{ "data": { ... } }

// 错误
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "名称不能为空",
    "details": [{ "field": "name", "issue": "required" }]
  }
}
```

---

## Git Commit 规范

```
feat: 新功能
fix: 修复 bug
docs: 文档更新
style: 代码格式（不影响功能）
refactor: 重构
test: 测试
chore: 构建/工具/依赖

示例:
feat: add user authentication with JWT
fix: resolve race condition in payment callback
docs: update deploy runbook with rollback steps
```

---

## 注释

```typescript
// ✅ 注释 "为什么"，不注释 "是什么"
// 使用队列而非直接写入，防止高并发下连接池耗尽
await queue.enqueue(task)

// ❌ 无意义注释
// 将 task 加入队列
await queue.enqueue(task)
```
