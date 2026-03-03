from __future__ import annotations
import json
import threading
import time
from typing import List
from agentlz.config.settings import get_settings
from agentlz.core.external_services import create_rabbitmq_connection
from agentlz.core.logger import setup_logging
import pika

from agentlz.services.rag.document_service import process_document_from_cos_https
from agentlz.services import scan_service
from agentlz.services.cache_service import cache_get, acquire_record_zip_lock, release_record_zip_lock
from agentlz.repositories import session_repository as sess_repo
from agentlz.repositories import agent_repository as agent_repo
from agentlz.repositories import record_repository as record_repo
from agentlz.services.cache_service import chat_history_set_item
from langchain_core.prompts import ChatPromptTemplate
from agentlz.prompts.rag.zipper import ZIPPER_SYSTEM_PROMPT, ZIPPER_USER_PROMPT_TEMPLATE, RECORD_SUMMARY_SYSTEM_PROMPT, RECORD_SUMMARY_USER_PROMPT_TEMPLATE
from agentlz.core.model_factory import get_model_by_name, get_model

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
                self._channel.queue_declare(queue='zip_tasks', durable=True)
                self._channel.queue_declare(queue='doc_scan_tasks', durable=True)
                self._channel.queue_declare(queue='zip_record_aggregate_tasks', durable=True)
                self._channel.basic_qos(prefetch_count=1)

                logger.info("开始监听文档解析任务队列...")
                logger.info("开始监听聊天持久化任务队列...")
                logger.info("开始监听zip任务队列...")
                logger.info("开始监听扫描任务队列...")
                logger.info("开始监听记录总压缩任务队列...")

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
                self._channel.basic_consume(
                    queue='zip_tasks',
                    on_message_callback=self._process_zip_task,
                    auto_ack=False
                )
                self._channel.basic_consume(
                    queue='doc_scan_tasks',
                    on_message_callback=self._process_scan_task,
                    auto_ack=False
                )
                self._channel.basic_consume(
                    queue='zip_record_aggregate_tasks',
                    on_message_callback=self._process_record_zip_aggregate_message,
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
            strategy = message.get('strategy', 0)
            
            if not all([doc_id, save_https, document_type,tenant_id]):
                raise BizError("消息格式不完整，缺少必要字段")
                
            # 3. 真正处理文档
            logger.info(f"开始处理文档 {doc_id}，类型: {document_type}，策略: {strategy}")
            
            
            # 调用文档处理服务
            process_document_from_cos_https(save_https, document_type, doc_id, tenant_id, strategy)
            
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
            if not cached:
                raise BizError("redis payload 不存在")
            obj = json.loads(cached)
            inp = obj.get("input")
            outp = obj.get("output")
            if inp is None or outp is None:
                raise BizError("redis payload 缺少 input/output")
            s = get_settings()
            sess_table = getattr(s, "session_table_name", "session")
            sess_repo.create_session_idempotent(
                record_id=int(record_id),
                request_id=str(redis_key),
                meta_input=inp,
                meta_output=outp,
                table_name=sess_table,
            )

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except BizError as biz:
            logger.error(f"业务异常，丢弃消息: {biz}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            save_to_dead_letter(body, reason=str(biz))
        except Exception as sys_exc:
            if retry >= max_retries:
                logger.error(f"已达最大重试次数[{max_retries}]，丢弃消息")
                ch.basic_ack(delivery_tag=method.delivery_tag)

    def _process_zip_task(self, ch, method, properties, body):
        """处理 zip 生成任务（对单条 session 做摘要压缩）。

        目标：
        - 生成 zip 摘要并写入 MySQL（幂等：已有 zip 或 zip_status=done 则跳过）
        - 写入成功后同步补齐 Redis 历史缓存对应条目的 zip/zip_status
        """
        headers = properties.headers or {}
        retry = int(headers.get("x-retry", 0))
        max_retries = self.settings.rabbitmq_max_retries

        try:
            # 阶段1：解析与校验消息体
            message = json.loads(body.decode("utf-8"))
            logger.info(f"收到zip任务: {message}")

            session_id = message.get("session_id")
            record_id = message.get("record_id")
            agent_id = message.get("agent_id")
            request_id = message.get("request_id")
            if not all([session_id, record_id, agent_id, request_id]):
                raise BizError("消息格式不完整，缺少必要字段")

            # 阶段2：读取 session，做幂等判定
            s = get_settings()
            sess_table = getattr(s, "session_table_name", "session")
            row = sess_repo.get_session_by_id(session_id=int(session_id), table_name=sess_table)
            if not row:
                raise BizError("session不存在")

            if str(row.get("zip") or "").strip() != "" or str(row.get("zip_status") or "") == "done":
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # 阶段3：抽取 input/output 文本；短对话直接保留，不走压缩
            mi = row.get("meta_input")
            mo = row.get("meta_output")
            try:
                inp_obj = json.loads(mi) if isinstance(mi, str) else mi
            except Exception:
                inp_obj = mi
            try:
                out_obj = json.loads(mo) if isinstance(mo, str) else mo
            except Exception:
                out_obj = mo
            inp_text = inp_obj.get("text") if isinstance(inp_obj, dict) else inp_obj
            out_text = out_obj.get("text") if isinstance(out_obj, dict) else out_obj
            inp_text = str(inp_text or "")
            out_text = str(out_text or "")

            if len(inp_text) + len(out_text) <= 300:
                zip_text = f"用户输入：{inp_text}\n大模型回答：{out_text}".strip()
            else:
                agent_table = getattr(s, "agent_table_name", "agent")
                arow = None
                try:
                    arow = agent_repo.get_agent_by_id_any_tenant(agent_id=int(agent_id), table_name=agent_table)
                except Exception:
                    arow = None
                meta_conf = None
                if arow:
                    mc = arow.get("meta")
                    if isinstance(mc, str):
                        try:
                            mc = json.loads(mc)
                        except Exception:
                            mc = None
                    if isinstance(mc, dict):
                        meta_conf = mc

                llm = None
                if isinstance(meta_conf, dict):
                    model_name = str(meta_conf.get("zip_model_name") or meta_conf.get("model_name") or "") or None
                    chat_api_key = meta_conf.get("chatopenai_api_key")
                    chat_base_url = meta_conf.get("chatopenai_base_url")
                    openai_key = meta_conf.get("openai_api_key")
                    if model_name or chat_api_key or chat_base_url or openai_key:
                        llm = get_model_by_name(
                            settings=s,
                            model_name=model_name or s.model_name,
                            streaming=False,
                            chatopenai_api_key=chat_api_key,
                            chatopenai_base_url=chat_base_url,
                            openai_api_key=openai_key,
                        )
                if llm is None:
                    llm = get_model(settings=s, streaming=False)

                prompt = ChatPromptTemplate.from_messages(
                    [
                        ("system", ZIPPER_SYSTEM_PROMPT),
                        ("human", ZIPPER_USER_PROMPT_TEMPLATE),
                    ]
                )
                chain = prompt | llm
                try:
                    resp = chain.invoke({"input": inp_text, "output": out_text})
                    zip_text = str(getattr(resp, "content", resp) or "").strip()
                except Exception as e:
                    raise RuntimeError(str(e))

            if zip_text == "":
                raise BizError("zip生成为空")

            # 阶段5：落库（仅 pending/空 zip 才更新），并回写 Redis 缓存
            updated = sess_repo.update_session_zip_if_pending(
                session_id=int(session_id),
                zip_text=str(zip_text),
                zip_status="done",
                table_name=sess_table,
            )
            if updated:
                item = {
                    "session_id": int(session_id),
                    "count": int(row.get("count") or 0),
                    "input": inp_obj,
                    "output": out_obj,
                    "zip": str(zip_text),
                    "zip_status": "done",
                    "created_at": str(row.get("created_at") or ""),
                }
                chat_history_set_item(record_id=int(record_id), session_id=int(session_id), item=item, ttl=3600)

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
                    exchange="",
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(headers=headers),
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)

    def _process_record_zip_aggregate_message(self, ch, method, properties, body):
        """
        处理 record 级总压缩任务，生成并更新 record.summary_zip。

        关键步骤：
        - 使用 Redis 锁串行化同一 record 的总压缩任务；
        - 读取当前 summary_until_session_id，避免重复压缩；
        - 读取指定区间 session（优先用 zip，否则用 input/output）拼接段落；
        - 通过 LLM 生成新的总摘要并落库；
        - 失败时走重试或死信策略，确保可观测。
        """
        headers = properties.headers or {}
        retry = int(headers.get("x-retry", 0))
        max_retries = self.settings.rabbitmq_max_retries
        token = str(int(time.time() * 1000))
        record_id = None
        try:
            message = json.loads(body.decode("utf-8"))
            logger.info(f"收到记录总压缩任务: {message}")
            record_id = message.get("record_id")
            agent_id = message.get("agent_id")
            target_until = message.get("target_until_session_id")
            if not all([record_id, agent_id, target_until]):
                raise BizError("消息格式不完整，缺少必要字段")
            if not acquire_record_zip_lock(record_id=int(record_id), token=token, ttl_ms=30000):
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            s = get_settings()
            rec_table = getattr(s, "record_table_name", "record")
            sess_table = getattr(s, "session_table_name", "session")
            rec_row = record_repo.get_record_summary(record_id=int(record_id), table_name=rec_table)
            summary_until = 0
            summary_zip = ""
            summary_version = 1
            if rec_row:
                try:
                    summary_until = int(rec_row.get("summary_until_session_id") or 0)
                except Exception:
                    summary_until = 0
                summary_zip = str(rec_row.get("summary_zip") or "").strip()
                try:
                    summary_version = int(rec_row.get("summary_version") or 1)
                except Exception:
                    summary_version = 1
            target_until = int(target_until)
            if summary_until >= target_until:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            rows = sess_repo.list_sessions_in_id_range(
                record_id=int(record_id),
                after_session_id=int(summary_until),
                until_session_id=int(target_until),
                table_name=sess_table,
            )
            segments: List[str] = []
            for r in rows:
                mi = r.get("meta_input")
                mo = r.get("meta_output")
                try:
                    inp_obj = json.loads(mi) if isinstance(mi, str) else mi
                except Exception:
                    inp_obj = mi
                try:
                    out_obj = json.loads(mo) if isinstance(mo, str) else mo
                except Exception:
                    out_obj = mo
                inp_text = inp_obj.get("text") if isinstance(inp_obj, dict) else inp_obj
                out_text = out_obj.get("text") if isinstance(out_obj, dict) else out_obj
                inp_text = str(inp_text or "")
                out_text = str(out_text or "")
                z = str(r.get("zip") or "").strip()
                z_status = str(r.get("zip_status") or "").strip()
                count_val = r.get("count")
                label = int(count_val) if isinstance(count_val, (int, float)) else int(r.get("id") or 0)
                if z and z_status == "done":
                    segments.append(f"第{label}轮: {z}")
                else:
                    text = f"用户输入：{inp_text}\n大模型回答：{out_text}".strip()
                    segments.append(f"第{label}轮: {text}")
            merged_summary = summary_zip
            if segments:
                agent_table = getattr(s, "agent_table_name", "agent")
                arow = None
                try:
                    arow = agent_repo.get_agent_by_id_any_tenant(agent_id=int(agent_id), table_name=agent_table)
                except Exception:
                    arow = None
                meta_conf = None
                if arow:
                    mc = arow.get("meta")
                    if isinstance(mc, str):
                        try:
                            mc = json.loads(mc)
                        except Exception:
                            mc = None
                    if isinstance(mc, dict):
                        meta_conf = mc
                llm = None
                if isinstance(meta_conf, dict):
                    model_name = str(meta_conf.get("zip_model_name") or meta_conf.get("model_name") or "") or None
                    chat_api_key = meta_conf.get("chatopenai_api_key")
                    chat_base_url = meta_conf.get("chatopenai_base_url")
                    openai_key = meta_conf.get("openai_api_key")
                    if model_name or chat_api_key or chat_base_url or openai_key:
                        llm = get_model_by_name(
                            settings=s,
                            model_name=model_name or s.model_name,
                            streaming=False,
                            chatopenai_api_key=chat_api_key,
                            chatopenai_base_url=chat_base_url,
                            openai_api_key=openai_key,
                        )
                if llm is None:
                    llm = get_model(settings=s, streaming=False)
                if llm is None:
                    merged_summary = "\n".join([x for x in [summary_zip, "\n".join(segments)] if x])
                else:
                    prompt = ChatPromptTemplate.from_messages(
                        [
                            ("system", RECORD_SUMMARY_SYSTEM_PROMPT),
                            ("human", RECORD_SUMMARY_USER_PROMPT_TEMPLATE),
                        ]
                    )
                    chain = prompt | llm
                    resp = chain.invoke({"summary": summary_zip, "segments": "\n\n".join(segments)})
                    merged_summary = str(getattr(resp, "content", resp) or "").strip()
            record_repo.update_record_summary_if_earlier(
                record_id=int(record_id),
                summary_zip=str(merged_summary or ""),
                summary_until_session_id=int(target_until),
                summary_version=int(summary_version or 1),
                table_name=rec_table,
            )
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
                    exchange="",
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(headers=headers),
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)
        finally:
            if record_id:
                release_record_zip_lock(record_id=int(record_id), token=token)

    def _process_scan_task(self, ch, method, properties, body):
        headers = properties.headers or {}
        retry = int(headers.get("x-retry", 0))
        max_retries = self.settings.rabbitmq_max_retries
        try:
            message = json.loads(body.decode("utf-8"))
            task_id = message.get("task_id")
            if not task_id:
                raise BizError("消息格式不完整，缺少必要字段")
            scan_service.scan_upload_task(task_id=int(task_id))
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
                    exchange="",
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(headers=headers),
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
