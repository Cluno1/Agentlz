from __future__ import annotations
import json
import threading
import time
from agentlz.config.settings import get_settings
from agentlz.core.external_services import create_rabbitmq_connection
from agentlz.core.logger import setup_logging
import pika

from agentlz.services.document_service import process_document_from_cos_https
from agentlz.services.cache_service import cache_get

logger = setup_logging()
class BizError(Exception):
    """业务异常，不需要重试"""
    pass


def save_to_dead_letter(body: bytes, reason: str):
    """保存死信消息（可以根据需要实现具体逻辑）"""
    logger.error(f"死信消息: {reason}, body: {body.decode('utf-8')}")


class MQService:
    """RabbitMQ消息队列服务"""
    
    def __init__(self):
        self._running = False
        self._thread = None
        self._channel = None
        self._connection = None
        self.settings = get_settings()
        self.logger = setup_logging()
        
    def start(self):
        """启动MQ服务"""
        if self._running:
            logger.warning("MQ服务已经在运行中")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._consume_messages, daemon=True)
        self._thread.start()
        logger.info("MQ服务已启动")
        
    def stop(self):
        """停止MQ服务"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("MQ服务已停止")
        
    def _consume_messages(self):
        """消费消息的线程函数"""
        while self._running:
            try:
                # 线程内创建独立的连接与通道（pika不支持跨线程共享连接/通道）
                # 使用 external_services 的工厂创建独立连接
                self._connection = create_rabbitmq_connection()
                self._channel = self._connection.channel()

                # 声明队列并设置流控
                self._channel.queue_declare(queue='doc_parse_tasks', durable=True)
                self._channel.queue_declare(queue='chat_persist_tasks', durable=True)
                self._channel.basic_qos(prefetch_count=1)

                logger.info("开始监听文档解析任务队列...")
                logger.info("开始监听聊天持久化任务队列...")

                # 设置消费者
                self._channel.basic_consume(
                    queue='doc_parse_tasks',
                    on_message_callback=self._process_message,
                    auto_ack=False
                )
                self._channel.basic_consume(
                    queue='chat_persist_tasks',
                    on_message_callback=self._process_chat_persist_message,
                    auto_ack=False
                )

                # 开始消费
                self._channel.start_consuming()

            except Exception as e:
                logger.error(f"MQ消费线程出错: {e}")
                if self._running:
                    time.sleep(5)
                    logger.info("尝试重新连接RabbitMQ...")
                else:
                    break

        # 清理连接
        try:
            if self._channel and not self._channel.is_closed:
                try:
                    self._channel.stop_consuming()
                except Exception:
                    pass
                self._channel.close()
            if self._connection and not self._connection.is_closed:
                self._connection.close()
        except Exception as e:
            logger.warning(f"清理MQ连接时出错: {e}")
    # 处理rag文档解析任务消息
    def _process_message(self, ch, method, properties, body):
        """处理接收到的消息 文档解析任务"""
        # 获取重试次数
        headers = properties.headers or {}
        retry = int(headers.get("x-retry", 0))
        max_retries = self.settings.rabbitmq_max_retries
        
        try:
            # 1. 解析消息
            message = json.loads(body.decode('utf-8'))
            logger.info(f"收到文档解析任务: {message}")
            
            # 2. 业务校验（可预期异常）
            doc_id = message.get('doc_id')
            save_https = message.get('save_https')
            document_type = message.get('document_type')
            tenant_id = message.get('tenant_id')
            
            if not all([doc_id, save_https, document_type,tenant_id]):
                raise BizError("消息格式不完整，缺少必要字段")
                
            # 3. 真正处理文档
            logger.info(f"开始处理文档 {doc_id}，类型: {document_type}")
            
            
            # 调用文档处理服务
            process_document_from_cos_https(save_https, document_type,doc_id,tenant_id)
            
            
            
            logger.info(f"文档 {doc_id} 处理完成")
            
            # 确认消息处理成功
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except BizError as biz:
            # -------------- 业务异常：直接 ack + 记录 --------------
            logger.error(f"业务异常，丢弃消息: {biz}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            # 可选：写入死信表或发告警
            save_to_dead_letter(body, reason=str(biz))
            
        except Exception as sys_exc:
            # -------------- 系统异常：重试或丢弃 --------------
            if retry >= max_retries:
                logger.error(f"已达最大重试次数[{max_retries}]，丢弃消息")
                ch.basic_ack(delivery_tag=method.delivery_tag)  # 或 nack+requeue=False
                save_to_dead_letter(body, reason=str(sys_exc))
            else:
                # 计数器 +1 再重新投
                headers["x-retry"] = retry + 1
                ch.basic_publish(
                    exchange='', 
                    routing_key=method.routing_key,  # 原队列
                    body=body,
                    properties=pika.BasicProperties(headers=headers)
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)  # 把旧消息 ack 掉，避免重复
    # 处理聊天持久化任务消息
    def _process_chat_persist_message(self, ch, method, properties, body):
        """处理接收到的消息 聊天持久化任务"""
        headers = properties.headers or {}
        retry = int(headers.get("x-retry", 0))
        max_retries = self.settings.rabbitmq_max_retries

        try:
            message = json.loads(body.decode('utf-8'))
            logger.info(f"收到聊天持久化任务: {message}")

            redis_key = message.get('redis_key')
            agent_id = message.get('agent_id')
            record_id = message.get('record_id')
            session_id = message.get('session_id')

            if not all([redis_key, agent_id, record_id, session_id]):
                raise BizError("消息格式不完整，缺少必要字段")

            cached = cache_get(str(redis_key))
            logger.info(f"聊天持久化占位，redis_key={redis_key}，payload存在={bool(cached)}")

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except BizError as biz:
            logger.error(f"业务异常，丢弃消息: {biz}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            save_to_dead_letter(body, reason=str(biz))
        except Exception as sys_exc:
            if retry >= max_retries:
                logger.error(f"已达最大重试次数[{max_retries}]，丢弃消息")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                save_to_dead_letter(body, reason=str(sys_exc))
            else:
                headers["x-retry"] = retry + 1
                ch.basic_publish(
                    exchange='',
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(headers=headers)
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)

# 全局MQ服务实例
_mq_service = None

def get_mq_service() -> MQService:
    """获取MQ服务实例（单例模式）"""
    global _mq_service
    if _mq_service is None:
        _mq_service = MQService()
    return _mq_service

def start_mq_service():
    """启动MQ服务"""
    service = get_mq_service()
    service.start()
    return service

def stop_mq_service():
    """停止MQ服务"""
    global _mq_service
    if _mq_service:
        _mq_service.stop()
        _mq_service = None
