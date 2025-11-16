from __future__ import annotations

"""
HTTP 接口入口（FastAPI）

提供用户管理页面所需的用户列表查询接口：
- 路由：GET /v1/users
- 支持分页：_page, _perPage
- 支持排序：_sort（字段白名单）, _order（ASC/DESC）
- 支持搜索：q（匹配 username/email/full_name）
- 支持多租户：从请求头读取 TENANT_ID_HEADER（默认 X-Tenant-ID），按 tenant_id 过滤

读取配置来自 agentlz.config.settings.Settings（.env 环境变量）
"""

from typing import Dict

from fastapi import FastAPI

from agentlz.app.routers.users import router as users_router


app = FastAPI()

# 挂载用户路由（CRUD + 列表）
app.include_router(users_router)


@app.get("/v1/health")
def health() -> Dict[str, str]:
    """健康检查：返回 OK"""
    return {"status": "ok"}