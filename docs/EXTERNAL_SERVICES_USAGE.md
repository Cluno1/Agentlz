# 外部服务连接管理重构说明

## 概述
已将COS、RabbitMQ、Redis的连接管理统一迁移到`agentlz/core/external_services.py`中，实现了连接复用和统一管理。

## 主要改进

### 1. 连接管理统一化
- **文件**: `agentlz/core/external_services.py`
- **功能**: 统一管理COS、RabbitMQ、Redis连接
- **模式**: 单例模式，支持连接复用

### 2. COS服务重构
- **原文件**: `agentlz/services/cos_service.py`
- **改进**: 从每次都创建新客户端改为使用全局客户端实例
- **性能**: 减少连接建立开销

### 3. RabbitMQ重构
- **原文件**: `agentlz/services/document_service.py`
- **改进**: 从临时创建连接改为使用连接池
- **位置**: 文档解析任务发布（约590-620行）

### 4. 新增Redis缓存服务
- **文件**: `agentlz/services/cache_service.py`
- **功能**: 提供统一的缓存操作接口
- **特性**: 异常安全，不影响主业务流程

## 使用方法

### COS文件上传
```python
from agentlz.core.external_services import upload_to_cos

# 上传文档
url = upload_to_cos(document_bytes, filename)
```

### RabbitMQ消息发布
```python
from agentlz.core.external_services import publish_to_rabbitmq

# 发布消息
message = {"key": "value"}
publish_to_rabbitmq("queue_name", message, durable=True)
```

### Redis缓存操作
```python
from agentlz.services.cache_service import cache_set, cache_get

# 设置缓存
cache_set("key", "value", expire=3600)

# 获取缓存
value = cache_get("key")
```

### 获取客户端实例
```python
from agentlz.core.external_services import get_cos_client, get_rabbitmq_channel, get_redis_client

# 获取COS客户端
cos_client = get_cos_client()

# 获取RabbitMQ通道
channel = get_rabbitmq_channel()

# 获取Redis客户端
redis_client = get_redis_client()
```

## 配置要求

### 环境变量
```bash
# COS配置
COS_SECRET_ID=your_secret_id
COS_SECRET_KEY=your_secret_key
COS_BUCKET=your_bucket
COS_REGION=your_region
COS_BASE_URL=your_base_url  # 可选

# RabbitMQ配置
RABBITMQ_URL=amqp://user:pass@host:port/vhost  # 优先使用
# 或者使用单独配置
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/

# Redis配置
REDIS_URL=redis://user:pass@host:port/db  # 优先使用
# 或者使用单独配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  # 可选
```

## 错误处理

- 所有外部服务连接都包含异常处理
- 连接失败时会记录日志并抛出RuntimeError
- Redis缓存操作异常安全，不影响主业务流程

## 资源清理

应用关闭时会自动清理所有外部服务连接：

```python
from agentlz.core.cleanup import cleanup_all, setup_cleanup_at_exit

# 注册退出清理函数
setup_cleanup_at_exit()

# 手动清理（可选）
cleanup_all()
```

## 性能优化

1. **连接复用**: 避免频繁创建连接
2. **连接池**: 支持连接池配置
3. **健康检查**: 定期检测连接状态
4. **异常恢复**: 连接断开时自动重连

## 监控和日志

- 所有连接操作都有详细的日志记录
- 支持日志级别配置
- 连接状态变化会记录到日志中

## 向后兼容性

- 保持原有API接口不变
- `upload_document_to_cos`函数仍然可用
- 内部实现改为使用统一连接管理