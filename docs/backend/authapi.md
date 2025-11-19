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

- 说明：校验用户名与密码，成功返回 JWT（统一使用 `Result` 包裹，token 在 `data.token`）
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
  "success": true,
  "code": 0,
  "message": "ok",
  "data": {
    "token": "<JWT>"
  }
}
```

错误示例：
- 缺少租户头（400）
```
{
  "success": false,
  "code": 400,
  "message": "Missing tenant header: X-Tenant-ID",
  "data": {}
}
```
- 凭证错误（401）
```
{
  "success": false,
  "code": 401,
  "message": "用户名或密码错误",
  "data": {}
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
- 请求体（统一使用 `Result` 包裹返回）：
  - `username`（必填）
  - `email`（必填，邮箱格式校验，`EmailStr`）
  - `password`（必填）

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
  "success": true,
  "code": 0,
  "message": "ok",
  "data": {
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
}
```

错误示例：
- 缺少租户头（400）
```
{
  "success": false,
  "code": 400,
  "message": "Missing tenant header: X-Tenant-ID",
  "data": {}
}
```
- 邮箱格式错误（422）
```
{
  "success": false,
  "code": 422,
  "message": "参数校验错误",
  "data": { "errors": [/* pydantic 错误 */], "path": "/v1/register" }
}
```
- 用户已存在（409）
```
{
  "success": false,
  "code": 409,
  "message": "用户名已存在",
  "data": {}
}
```
- 邮箱已存在（409）
```
{
  "success": false,
  "code": 409,
  "message": "邮箱已存在",
  "data": {}
}
```

---

## 附录

### 登录成功返回（Result 包裹）
- `data.token`：JWT 字符串
- 有效期：`exp = 登录时刻 + 8 小时`
- 常见声明：`sub`（用户 ID）、`username`、`tenant_id`、`iss`、`iat`、`exp`

### 注册成功返回（Result 包裹 UserItem）
- `data` 为用户实体：`id`、`username`、`email`、`full_name`、`avatar`、`role`、`disabled`、`created_at`、`created_by_id`、`tenant_id`

### 多租户与安全
- 所有接口必须携带正确的 `X-Tenant-ID`
- 错误统一由 `http_langserve` 处理为 `Result.error`（`agentlz/app/http_langserve.py:25-31`）
- 不要在日志中打印或泄露 `token` 内容
- 建议前端在登录后统一设置 `Authorization` 头，并在 `token` 过期时自动跳转登录或刷新