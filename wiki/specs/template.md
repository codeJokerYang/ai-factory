# SPEC-XXX: [功能名称]

- **状态**: [提议 / 进行中 / 已完成 / 已废弃]
- **创建日期**: YYYY-MM-DD
- **负责人**: [名字]

---

## 概述

[一句话描述这个功能是什么]

## 用户故事

### 故事 1
> 作为 [角色]，我想要 [功能]，以便 [价值/目的]

**验收标准**:
- [ ] [可验证的条件]

### 故事 2
> 作为 [角色]，我想要 [功能]，以便 [价值/目的]

**验收标准**:
- [ ] [可验证的条件]

---

## 接口定义

### API 端点

```
POST /api/v1/resource
Content-Type: application/json
Authorization: Bearer <token>

Request:
{
  "field": "type"
}

Response 200:
{
  "id": "uuid",
  "createdAt": "ISO8601"
}

Response 400:
{
  "error": { "code": "VALIDATION_ERROR", "message": "..." }
}
```

### 数据模型

```typescript
interface Resource {
  id: string          // UUID
  name: string        // 1-100 chars
  status: 'active' | 'inactive'
  createdAt: Date
  updatedAt: Date
}
```

---

## 边界条件

### 正常流
- [描述正常使用路径]

### 异常流
- 输入无效 → 返回 400
- 未认证 → 返回 401
- 无权限 → 返回 403
- 资源不存在 → 返回 404
- 服务不可用 → 返回 503

### 并发/竞态
- [如果两个用户同时操作会怎样？]

### 性能要求
- 响应时间 < [X]ms (P95)
- 并发支持 [X] req/s

---

## 测试要点

- [ ] 单元测试覆盖核心逻辑
- [ ] 集成测试覆盖 API 端点
- [ ] 边界条件测试（null、空字符串、超长输入）
- [ ] 错误处理测试

---

## 依赖

- 需要先完成: [XXX]
- 外部依赖: [数据库表、第三方服务]

---

## 变更记录

| 日期 | 变更 | 作者 |
|------|------|------|
| YYYY-MM-DD | 初始版本 | [名字] |
