# 后端开发文档

本目录收录企业后端服务的开发文档，重点为“分层与依赖约束”。完整的总规范与背景说明请参见同级的 `../dev.md`。

- `layers.md`：后端分层模型、职责边界与依赖约束（主要内容）
- `userapi.md`：接口设计与统一响应、鉴权、多租户与审计

后续将补充如下文档（占位）：
- `conventions.md`：编码/命名规范、错误与日志策略、测试与质量保障
- `ops.md`：运行与部署、配置与密钥管理、监控与告警

如需新增文档，请遵循目录与命名规范，避免循环依赖，并在提交前通过本地格式化与 lint。

## 启动服务器

- 开发模式：`uvicorn agentlz.app.http_langserve:app --port 8000 --reload`
- 生产示例：`uvicorn agentlz.app.http_langserve:app --host 0.0.0.0 --port 8000`
- 健康检查：访问 `http://localhost:8000/v1/health` 返回 `{"status": "ok"}`