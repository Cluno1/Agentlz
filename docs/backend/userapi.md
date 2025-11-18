# 用户管理 API 文档（/v1）

本页提供用户管理相关接口的请求/响应示例，涵盖：
- GET 用户列表：`GET /v1/users`
- GET 用户详情：`GET /v1/users/{id}`
- 创建用户：`POST /v1/users`
- 更新用户：`PUT /v1/users/{id}`
- 删除用户：`DELETE /v1/users/{id}`

通用约定：
- 多租户：所有接口必须在请求头携带租户标识 `X-Tenant-ID`（或 `.env` 中的 `TENANT_ID_HEADER`）。
- 认证：所有接口必须在请求头携带 `Authorization: Bearer <token>`（登录与注册接口除外）。
- 响应模型：统一返回 `UserItem` 或 `ListResponse`（`data + total`）。
- 字段：与数据库列对齐（`id`、`username`、`email`、`password_hash`、`full_name`、`avatar`、`role`、`disabled`、`created_at`、`created_by_id`、`tenant_id`）。
- 密码：当前按照你的数据示例，`password` 明文写入 `password_hash` 列；上线前建议替换为哈希（bcrypt）。

---

## 1) GET /v1/users （列表查询）
查询用户列表，支持分页/排序/搜索，并严格按照租户隔离。

- 查询参数：
  - `_page`（默认 1）、`_perPage`（默认 10，最大 100）
  - `_sort`（字段白名单：`id`、`username`、`email`、`fullName`、`role`、`disabled`、`createdAt`）
  - `_order`（`ASC` 或 `DESC`）
  - `q`（模糊搜索，匹配 `username/email/full_name`）
- 头部：
  - `X-Tenant-ID: default`

示例请求：
```
curl -s \
  -H "X-Tenant-ID: default" \
  -H "Authorization: Bearer <token>" \
  "http://localhost:8000/v1/users?_page=1&_perPage=10&_sort=id&_order=ASC&q=user"
```

示例响应（200）：
```
{
  "data": [
    {
      "id": 2,
      "username": "user_001",
      "email": "user001@",
      "full_name": "小娟",
      "avatar": "https://i.p",
      "role": "user",
      "disabled": false,
      "created_at": "2025-02-24 00:00:00",
      "created_by_id": null,
      "tenant_id": "default"
    }
  ],
  "total": 50
}
```

错误示例（缺少租户头 400）：
```
{
  "detail": "Missing tenant header: X-Tenant-ID"
}
```

---

## 2) GET /v1/users/{id} （用户详情）
按 `id` 获取单个用户详情，需携带租户头。

示例请求：
```
curl -s \
  -H "X-Tenant-ID: default" \
  -H "Authorization: Bearer <token>" \
  "http://localhost:8000/v1/users/1"
```

示例响应（200）：
```
{
  "id": 1,
  "username": "admin",
  "email": "admin@e",
  "full_name": "系统管理员",
  "avatar": "https://i.p",
  "role": "admin",
  "disabled": false,
  "created_at": "2025-11-14 00:00:00",
  "created_by_id": null,
  "tenant_id": "default"
}
```

未找到（404）：
```
{
  "detail": "User not found"
}
```

---

## 3) POST /v1/users （创建用户）
创建用户。当前实现会将请求体中的 `password` 写入数据库列 `password_hash`。

- 体字段（`UserCreate`）：
  - `username`（必填）
  - `email`（选填）
  - `password`（选填；暂映射到 `password_hash`）
  - `full_name`、`avatar`、`role`（默认 `user`）、`disabled`（默认 `false`）、`created_by_id`

示例请求：
```
curl -s -X POST \
  -H "X-Tenant-ID: default" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
        "username": "user_051",
        "email": "user051@",
        "password": "123456",
        "full_name": "赵六",
        "role": "user"
      }' \
  http://localhost:8000/v1/users
```

示例响应（201）：
```
{
  "id": 51,
  "username": "user_051",
  "email": "user051@",
  "full_name": "赵六",
  "avatar": null,
  "role": "user",
  "disabled": false,
  "created_at": "2025-11-16 00:00:00",
  "created_by_id": null,
  "tenant_id": "default"
}
```

---

## 4) PUT /v1/users/{id} （更新用户）
部分更新用户信息；任意字段可选。若提供 `password`，同样映射到 `password_hash`。

示例请求：
```
curl -s -X PUT \
  -H "X-Tenant-ID: default" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
        "full_name": "张三(更新)",
        "disabled": true
      }' \
  http://localhost:8000/v1/users/3
```

示例响应（200）：
```
{
  "id": 3,
  "username": "user_002",
  "email": "user002@",
  "full_name": "张三(更新)",
  "avatar": "https://i.p",
  "role": "user",
  "disabled": true,
  "created_at": "2025-07-13 00:00:00",
  "created_by_id": null,
  "tenant_id": "default"
}
```

未找到（404）：
```
{
  "detail": "User not found"
}
```

---

## 5) DELETE /v1/users/{id} （删除用户）
删除指定用户。成功返回 `204` 无正文。

示例请求：
```
curl -s -X DELETE -H "X-Tenant-ID: default" -H "Authorization: Bearer <token>" http://localhost:8000/v1/users/4 -i
```

成功响应（204）：
```
HTTP/1.1 204 No Content
```

未找到（404）：
```
{
  "detail": "User not found"
}
```

---

## 附录：字段说明（UserItem）
- `id`：主键
- `username`：用户名
- `email`：邮箱
- `full_name`：姓名
- `avatar`：头像 URL
- `role`：`admin` / `user` 等
- `disabled`：是否禁用
- `created_at`：创建时间（字符串化）
- `created_by_id`：创建人 ID（可空）
- `tenant_id`：租户标识

## 附录：排序字段白名单
- `_sort` 可取：`id`、`username`、`email`、`fullName`、`role`、`disabled`、`createdAt`
- `_order`：`ASC` 或 `DESC`

备注：列表响应中提供 `total` 字段用于总数统计；如需兼容前端从响应头读取 `x-total-count` 的模式，可在路由中额外设置该响应头。