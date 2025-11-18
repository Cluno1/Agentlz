# 认证 API 文档（/v1）

本文档提供登录与注册相关接口的请求/响应示例。

- 路由前缀：`/v1`
- 多租户：所有接口必须在请求头携带租户标识 `X-Tenant-ID`（或 `.env` 中的 `TENANT_ID_HEADER`，默认 `X-Tenant-ID`）
- 内容类型：`Content-Type: application/json`
- 认证约定：
  - 登录成功返回 `token`（JWT），有效期 8 小时
  - 调用受保护接口时在请求头携带 `Authorization: Bearer <token>`

---

## 1) POST /v1/login （登录）

- 说明：校验用户名与密码，成功返回 JWT
- 头部：
  - `X-Tenant-ID: default`
  - `Content-Type: application/json`
- 请求体：
  - `username`（必填）
  - `password`（必填）

示例请求：
```
curl -s -X POST \
  -H "X-Tenant-ID: default" \
  -H "Content-Type: application/json" \
  -d '{
        "username": "admin",
        "password": "admin"
      }' \
  http://localhost:8000/v1/login
```

示例响应（200）：
```
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInRlbmFudF9pZCI6ImRlZmF1bHQiLCJpc3MiOiJhZ2VudGx6IiwiaWF0IjoxNzYzMzY5NjAxLCJleHAiOjE3NjMzOTg0MDF9.JgM_80R0c6U3HtIHmV4Y8a9xnw7_kfhwGqXyQ2FzIoE"
}
```

错误示例：
- 缺少租户头（400）
```
{
  "detail": "Missing tenant header: X-Tenant-ID"
}
```
- 凭证错误（401）
```
{
  "detail": "Invalid credentials"
}
```

使用说明：
- 客户端需将响应中的 `token` 保存（如 `localStorage.access_token`），并在后续受保护接口请求头设置：
  - `Authorization: Bearer <token>`

---

## 2) POST /v1/register （注册）

- 说明：创建新用户。当前实现会将请求体中的 `password` 写入数据库列 `password_hash`（上线前建议替换为哈希：如 `bcrypt`）
- 头部：
  - `X-Tenant-ID: default`
  - `Content-Type: application/json`
- 请求体：
  - `username`（必填）
  - `email`（可选）
  - `password`（必填）
  - `confirm`（必填；需与 `password` 一致）

示例请求：
```
curl -s -X POST \
  -H "X-Tenant-ID: default" \
  -H "Content-Type: application/json" \
  -d '{
        "username": "newuser",
        "email": "a@b.com",
        "password": "pass1234",
        "confirm": "pass1234"
      }' \
  http://localhost:8000/v1/register
```

示例响应（201）：
```
{
  "id": 66,
  "username": "newuser",
  "email": "a@b.com",
  "full_name": null,
  "avatar": null,
  "role": "user",
  "disabled": false,
  "created_at": "2025-11-17 09:07:46",
  "created_by_id": null,
  "tenant_id": "default"
}
```

错误示例：
- 缺少租户头（400）
```
{
  "detail": "Missing tenant header: X-Tenant-ID"
}
```
- 密码不一致（422）
```
{
  "detail": "Password mismatch"
}
```
- 用户已存在（409）
```
{
  "detail": "User already exists"
}
```

---

## 附录

### TokenResponse（登录成功）
- 字段：
  - `token`：JWT 字符串
- 认证使用：
  - 受保护接口需设置 `Authorization: Bearer <token>`
- 有效期：
  - `exp` = 登录时刻 + 8 小时；过期后需重新登录获取新 token
- 常见声明：
  - `sub`（用户 ID）、`username`、`tenant_id`、`iss`（发行者）、`iat`（签发时间）、`exp`（过期时间）

### UserItem（注册成功）
- 字段：
  - `id`、`username`、`email`、`full_name`、`avatar`、`role`、`disabled`、`created_at`、`created_by_id`、`tenant_id`

### 多租户与安全
- 所有接口必须携带正确的 `X-Tenant-ID`
- 不要在日志中打印或泄露 `token` 内容
- 建议前端在登录后统一设置 `Authorization` 头，并在 `token` 过期时自动跳转登录或刷新