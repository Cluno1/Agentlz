from __future__ import annotations
import json
import logging
from typing import Optional, Any, Dict
from agentlz.config.settings import get_settings
import pika  # type: ignore
logger = logging.getLogger(__name__)

# 全局连接实例缓存
_COS_CLIENT = None
_RABBITMQ_CONNECTION = None
_RABBITMQ_CHANNEL = None
_REDIS_CLIENT = None


def get_cos_client():
    """获取COS客户端实例（单例模式）"""
    global _COS_CLIENT
    if _COS_CLIENT is None:
        try:
            from qcloud_cos import CosConfig, CosS3Client  # type: ignore
            s = get_settings()
            secret_id = s.cos_secret_id
            secret_key = s.cos_secret_key
            region = s.cos_region

            if not secret_id or not secret_key or not region:
                raise RuntimeError(
                    "COS配置缺失：需要COS_SECRET_ID, COS_SECRET_KEY, COS_REGION")

            config = CosConfig(
                Region=region, SecretId=secret_id, SecretKey=secret_key)
            _COS_CLIENT = CosS3Client(config)
            logger.info("COS客户端初始化成功")
        except Exception as e:
            logger.error(f"COS客户端初始化失败: {e}")
            raise RuntimeError(f"COS客户端初始化失败: {e}") from e

    return _COS_CLIENT


def get_rabbitmq_connection():
    """获取RabbitMQ连接（单例模式）"""
    global _RABBITMQ_CONNECTION
    if _RABBITMQ_CONNECTION is None or _RABBITMQ_CONNECTION.is_closed:
        try:
            s = get_settings()

            # 优先使用URL连接
            url = getattr(s, "rabbitmq_url", None)
            if url:
                params = pika.URLParameters(url)
            else:
                # 使用单独参数连接
                host = getattr(s, "rabbitmq_host", "127.0.0.1")
                port = getattr(s, "rabbitmq_port", 5672)
                user = getattr(s, "rabbitmq_user", "guest")
                password = getattr(s, "rabbitmq_password", "guest")
                vhost = getattr(s, "rabbitmq_vhost", "/")

                params = pika.ConnectionParameters(
                    host=host,
                    port=port,
                    virtual_host=vhost,
                    credentials=pika.PlainCredentials(user, password),
                    heartbeat=600,  # 10分钟心跳
                    blocked_connection_timeout=300,  # 5分钟阻塞超时
                )

            _RABBITMQ_CONNECTION = pika.BlockingConnection(params)
            logger.info("RabbitMQ连接初始化成功")
        except Exception as e:
            logger.error(f"RabbitMQ连接初始化失败: {e}")
            raise RuntimeError(f"RabbitMQ连接初始化失败: {e}") from e

    return _RABBITMQ_CONNECTION


def get_rabbitmq_channel():
    """获取RabbitMQ通道（单例模式）"""
    global _RABBITMQ_CHANNEL
    if _RABBITMQ_CHANNEL is None or _RABBITMQ_CHANNEL.is_closed:
        try:
            connection = get_rabbitmq_connection()
            _RABBITMQ_CHANNEL = connection.channel()
            logger.info("RabbitMQ通道初始化成功")
        except Exception as e:
            logger.error(f"RabbitMQ通道初始化失败: {e}")
            raise RuntimeError(f"RabbitMQ通道初始化失败: {e}") from e

    return _RABBITMQ_CHANNEL


def get_redis_client():
    """获取Redis客户端实例（单例模式）"""
    global _REDIS_CLIENT
    if _REDIS_CLIENT is None:
        try:
            import redis  # type: ignore
            s = get_settings()

            # 优先使用URL连接
            redis_url = getattr(s, "redis_url", None)
            if redis_url:
                _REDIS_CLIENT = redis.from_url(
                    redis_url, decode_responses=True)
            else:
                # 使用单独参数连接
                host = getattr(s, "redis_host", "127.0.0.1")
                port = getattr(s, "redis_port", 6379)
                db = getattr(s, "redis_db", 0)
                password = getattr(s, "redis_password", None)

                _REDIS_CLIENT = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30,  # 30秒健康检查
                )

            # 测试连接
            _REDIS_CLIENT.ping()
            logger.info("Redis客户端初始化成功")
        except Exception as e:
            logger.error(f"Redis客户端初始化失败: {e}")
            raise RuntimeError(f"Redis客户端初始化失败: {e}") from e

    return _REDIS_CLIENT


def publish_to_rabbitmq(queue_name: str, message: Dict[str, Any], durable: bool = True) -> None:
    """
    发布消息到RabbitMQ队列
    
    :param queue_name: 队列名称
    :param message: 要发布的消息字典
    :param durable: 是否持久化消息（默认True）
    """
    try:
        channel = get_rabbitmq_channel()

        # 声明队列（如果已存在则忽略）
        channel.queue_declare(queue=queue_name, durable=durable)

        # 发布消息
        body = json.dumps(message, ensure_ascii=False)
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2 if durable else 1)  # 2=持久化, 1=非持久化
        )

        logger.info(f"消息发布到队列 {queue_name} 成功")
    except Exception as e:
        logger.error(f"消息发布到队列 {queue_name} 失败: {e}")
        raise RuntimeError(f"消息发布到RabbitMQ失败: {e}") from e


def upload_to_cos(document: bytes, filename: str, path: str = "unknown/", bucket: Optional[str] = None) -> str:
    """
    上传文档到COS,返回独有标志的url
    
    参数：
    - `document`: 文档内容（字节流）
    - `filename`: 文档文件名
    - `bucket`: COS存储桶名称（可选，默认从配置中获取）
    - `path`: COS存储路径（可选，默认"unknown/"）
    
    返回：
    - 上传后的COS对象键（唯一标识符）
    """
    try:
        import uuid
        client = get_cos_client()
        s = get_settings()

        # 获取存储桶名称
        if bucket is None:
            bucket = s.cos_bucket
            if not bucket:
                raise RuntimeError("COS存储桶配置缺失")

        # 生成对象键
        key = f"{path.rstrip('/')}/{uuid.uuid4().hex[:16]}_{filename}"

        # 上传文档
        client.put_object(Bucket=bucket, Body=document, Key=key)

        logger.info(f"文档 {filename} 上传到COS成功, 键: {key}")

        
        return key

    except Exception as e:
        logger.error(f"COS文档上传失败: {e}")
        raise RuntimeError(f"COS文档上传失败: {e}") from e


def test_rabbitmq_connection() -> Dict[str, Any]:
    """测试RabbitMQ连接状态"""
    try:
        connection = get_rabbitmq_connection()
        channel = get_rabbitmq_channel()
        
        connection_status = connection is not None and not connection.is_closed
        channel_status = channel is not None and not channel.is_closed
        
        return {
            "connection_status": connection_status,
            "channel_status": channel_status,
            "message": "RabbitMQ连接正常" if connection_status and channel_status else "RabbitMQ连接异常"
        }
    except Exception as e:
        logger.error(f"RabbitMQ连接测试失败: {e}")
        return {
            "connection_status": False,
            "channel_status": False,
            "message": f"RabbitMQ连接测试失败: {str(e)}"
        }


def close_all_connections() -> None:
    """关闭所有外部服务连接（用于应用关闭时）"""
    global _COS_CLIENT, _RABBITMQ_CONNECTION, _RABBITMQ_CHANNEL, _REDIS_CLIENT

    try:
        if _RABBITMQ_CHANNEL and not _RABBITMQ_CHANNEL.is_closed:
            _RABBITMQ_CHANNEL.close()
            logger.info("RabbitMQ通道已关闭")
    except Exception as e:
        logger.warning(f"关闭RabbitMQ通道时出错: {e}")

    try:
        if _RABBITMQ_CONNECTION and not _RABBITMQ_CONNECTION.is_closed:
            _RABBITMQ_CONNECTION.close()
            logger.info("RabbitMQ连接已关闭")
    except Exception as e:
        logger.warning(f"关闭RabbitMQ连接时出错: {e}")

    try:
        if _REDIS_CLIENT:
            _REDIS_CLIENT.close()
            logger.info("Redis连接已关闭")
    except Exception as e:
        logger.warning(f"关闭Redis连接时出错: {e}")

    # 重置全局变量
    _COS_CLIENT = None
    _RABBITMQ_CONNECTION = None
    _RABBITMQ_CHANNEL = None
    _REDIS_CLIENT = None
