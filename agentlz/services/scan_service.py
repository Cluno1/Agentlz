from __future__ import annotations
"""
安全扫描服务（病毒扫描 + 完整性校验 + 隔离区转正）。

核心目标：
1) 所有新上传对象先落到 COS 的 quarantine/ 前缀（隔离区）。
2) 通过 ClamAV INSTREAM 对 COS 对象做流式病毒扫描（不落盘）。
3) 同时计算对象的整文件 MD5（作为 file_hash），用于完整性与秒传指纹落库。
4) 扫描通过后，将对象从 quarantine/ copy 到可解析前缀（document/ 或 video/），再删除隔离区对象。
5) 最终触发解析任务（RabbitMQ doc_parse_tasks），并更新 upload_task / document / file_fingerprint 的状态。

阶段说明（大文件链路，>=10MB）：
- 上传：前端直传分片到 quarantine/{tenant}/{user}/{date}/...，后端仅负责签名与编排
- 合并：/v1/uploads/{task_id}/complete 完成 multipart 合并，任务状态 completed，scan_status=pending
- 扫描：RabbitMQ doc_scan_tasks 消费后调用 scan_upload_task
- 转正：scan_status=passed 后 copy 到 document/{tenant}/... 并 delete quarantine/...
- 解析：转正成功后才允许进入 doc_parse_tasks 解析（process_document_from_cos_https 有 gating）

阶段说明（小文件链路，<10MB）：
- 上传：后端接收文件并上传到 quarantine/
- 扫描：同步调用 scan_document_and_publish
- 转正 + 解析：同上，passed 才 publish 解析任务
"""
import hashlib
import logging
import socket
import logging
from typing import Any, Dict, Optional, Tuple
from agentlz.config.settings import get_settings
from agentlz.core.external_services import get_cos_client, publish_to_rabbitmq
from agentlz.repositories import document_repository as doc_repo
from agentlz.repositories import upload_repository as upload_repo
from agentlz.repositories import evaluation_repository as eva_repo
from agentlz.services.cos_service import copy_object, delete_object
from agentlz.services.rag import document_service
from agentlz.core.logger import setup_logging

logger = setup_logging()


def _clamav_scan_stream(stream, timeout: int) -> bool:
    """将文件内容以 INSTREAM 协议流式发送给 ClamAV，并返回是否安全。

    参数：
    - stream: 具备 read(n) -> bytes 的流对象（例如 COS Body 包装）
    - timeout: 连接/读写超时时间（秒）

    返回：
    - True：未发现病毒（ClamAV 响应不含 FOUND）
    - False：发现病毒（ClamAV 响应包含 FOUND）

    异常：
    - socket 连接失败、IO 超时等，会抛出异常，由上层决定重试/标记失败
    """
    s = get_settings()
    host = s.clamav_host
    port = int(s.clamav_port)
    conn = socket.create_connection((host, port), timeout=timeout)
    conn.settimeout(timeout)
    try:
        conn.sendall(b"nINSTREAM\n")
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            conn.sendall(struct.pack(">I", len(chunk)))
            conn.sendall(chunk)
        conn.sendall(struct.pack(">I", 0))
        resp = b""
        while not resp.endswith(b"\n"):
            data = conn.recv(4096)
            if not data:
                break
            resp += data
        text = resp.decode("utf-8", errors="ignore")
        return "FOUND" not in text
    finally:
        try:
            conn.close()
        except Exception:
            pass


def scan_cos_object(cos_key: str) -> Tuple[bool, str, int]:
    """对 COS 对象执行「病毒扫描 + MD5 计算」。

    阶段说明：
    1) 从 COS 获取对象流（Body）
    2) 一边读取流，一边累计 size + 计算 MD5
    3) 将同一份流数据按 ClamAV INSTREAM 协议发送到 ClamAV

    参数：
    - cos_key: COS 对象 Key（建议在 quarantine/ 前缀）

    返回：
    - (is_safe, md5_hex, size_bytes)

    异常：
    - COS 配置缺失 / get_object 失败 / ClamAV 连接失败，均会抛出异常
    """
    s = get_settings()
    logger.info(
        "COS config for scan: bucket=%r region=%r base_url=%r",
        s.cos_bucket,
        s.cos_region,
        s.cos_base_url,
    )
    client = get_cos_client()
    bucket = s.cos_bucket
    if not bucket:
        raise RuntimeError("COS存储桶配置缺失")
    resp = client.get_object(Bucket=bucket, Key=cos_key)
    body = resp.get("Body")
    if body is None:
        raise RuntimeError("COS对象内容为空")
    md5 = hashlib.md5()
    size = 0
    logger.debug(f"扫描COS对象 开始 key={cos_key}")

    def reader():
        nonlocal size
        while True:
            chunk = body.read(8192)
            if not chunk:
                break
            size += len(chunk)
            md5.update(chunk)
            yield chunk

    class StreamProxy:
        """把生成器包装成 ClamAV 需要的 stream.read(n) 形式。"""

        def __init__(self, gen):
            self._gen = gen
            self._buffer = b""

        def read(self, n=8192):
            if self._buffer:
                data = self._buffer[:n]
                self._buffer = self._buffer[n:]
                return data
            try:
                return next(self._gen)
            except StopIteration:
                return b""

    proxy = StreamProxy(reader())
    if s.clamav_disabled:
        while proxy.read(8192):
            pass
        ok = True
    else:
        ok = _clamav_scan_stream(proxy, timeout=int(s.clamav_timeout))
    try:
        body.close()
    except Exception:
        pass
    logger.debug(f"扫描COS对象 完成 key={cos_key} 安全={ok} md5={md5.hexdigest()} size={size}")
    return ok, md5.hexdigest(), size


def promote_from_quarantine(cos_key: str, file_type: str, tenant_id: str, user_id: int, filename: str) -> str:
    """将隔离区对象转正到可访问/可解析前缀。

    阶段说明：
    - 将 quarantine/xxx copy 到 document/{tenant}/... 或 video/{tenant}/...
    - copy 成功后删除原 quarantine 对象，避免绕过扫描直接被解析

    参数：
    - cos_key: 当前对象 key（通常在 quarantine/ 前缀）
    - file_type: doc|video|other（决定转正后的前缀）
    - tenant_id: 文档所属租户（已按 self/system/tenant 规则映射后的 tenant）
    - user_id: 上传者用户ID（用于路径/审计）
    - filename: 原始文件名（用于目标 key 拼接）

    返回：
    - new_key: 转正后的 COS key
    """
    import uuid
    from datetime import datetime
    import time
    from agentlz.services.cos_service import head_object
    date_str = datetime.now().strftime("%Y-%m-%d")
    if file_type == "video":
        base = f"video/{tenant_id}"
    else:
        base = f"document/{tenant_id}"
    new_key = f"{base}/{date_str}/{uuid.uuid4().hex[:16]}_{filename}"
    logger.debug("进入隔离区转正, 即将转正")
    head_ok = False
    last_head_err: Optional[Exception] = None
    for _ in range(3):
        try:
            head_object(cos_key)
            head_ok = True
            break
        except Exception as e:
            last_head_err = e
            time.sleep(0.2)
    if not head_ok:
        logger.error(f"quarantine_object_not_found: {cos_key} err={last_head_err}")
        raise RuntimeError(f"quarantine_object_not_found: {cos_key} err={last_head_err}")
    copy_object(cos_key, new_key)
    promoted_ok = False
    last_promote_err: Optional[Exception] = None
    for _ in range(5):
        try:
            head_object(new_key)
            promoted_ok = True
            break
        except Exception as e:
            last_promote_err = e
            time.sleep(0.2)
    if not promoted_ok:
        logger.error(f"promote_not_ready: {new_key} err={last_promote_err}")
        raise RuntimeError(f"promote_not_ready: {new_key} err={last_promote_err}")
    try:
        delete_object(cos_key)
    except Exception:
        pass
    logger.debug(f"隔离区转正完成, 已转正, 信息: from={cos_key} to={new_key}")
    return new_key

# 大文件
def scan_upload_task(task_id: int) -> Optional[Dict[str, Any]]:
    """处理「大文件分片上传任务」的扫描与后续编排。

    阶段说明：
    1) 读取 upload_task，获取 cos_key（隔离区对象）与前端上报的 file_hash（可选）
    2) scan_cos_object：ClamAV 扫描 + 计算整文件 MD5
    3) 完整性校验：若 upload_task.file_hash 存在且与计算值不一致 -> 直接判定失败
    4) 扫描通过：
       - promote_from_quarantine：对象转正
       - 更新 upload_task.scan_status=passed / cos_key=新key / file_hash=计算值
       - 若 upload_task.document_id 已存在：更新 document.save_https 与 status=processing
       - publish_document_chunk_tasks_after_scan：发布解析任务
       - upsert_fingerprint：写入秒传指纹（仅 passed 才可复用）
    5) 扫描失败：
       - 更新 upload_task.scan_status=failed / status=failed
       - 若 document_id 存在：document.status=scan_failed（gating）

    参数：
    - task_id: upload_task 主键

    返回：
    - 更新后的 upload_task 行（dict），不存在则返回 None
    """
    task = upload_repo.get_upload_task(task_id=task_id)
    if not task:
        logger.info(f"扫描上传任务开始：任务不存在 task_id={task_id}")
        return None
    cos_key = str(task.get("cos_key") or "")
    if not cos_key:
        logger.info(f"扫描上传任务开始：缺少 cos_key task_id={task_id}")
        return None
    logger.info(f"扫描上传任务：准备扫描 task_id={task_id} tenant_id={task.get('tenant_id')} user_id={task.get('user_id')} cos_key={cos_key} filename={task.get('filename')}")
    ok, file_hash, _size = scan_cos_object(cos_key)
    if task.get("file_hash") and str(task.get("file_hash")) != file_hash:
        ok = False
    logger.info(f"扫描上传任务：扫描完成 task_id={task_id} 安全={ok} 计算MD5={file_hash} 大小Bytes={_size}")
    doc_id = task.get("document_id")
    is_evaluation = bool(int(task.get("is_evaluation") or 0))
    if ok:
        new_key = promote_from_quarantine(
            cos_key=cos_key,
            file_type=str(task.get("file_type") or "doc"),
            tenant_id=str(task.get("tenant_id") or "default"),
            user_id=int(task.get("user_id") or 0),
            filename=str(task.get("filename") or "document"),
        )
        logger.info(f"扫描上传任务：隔离区转正完成但是数据库未更新save_https task_id={task_id} from={cos_key} to={new_key}")
        
        # 获取到实际的save_https
        save_https = document_service.build_save_https(new_key)
        
        upload_repo.update_upload_task(
            task_id=task_id,
            payload={"scan_status": "passed", "status": "completed", "cos_key": new_key, "file_hash": file_hash},
        )
        logger.info(f"扫描上传任务：更新上传任务状态完成 task_id={task_id} scan_status=passed status=completed cos_key={new_key}")
        if doc_id:
            if is_evaluation:
                eva_repo.update_eva_doc(
                    doc_id=str(doc_id),
                    payload={"save_https": save_https, "status": "processing"},
                    tenant_id=str(task.get("tenant_id") or "default"),
                    table_name="eva_doc",
                )
                publish_to_rabbitmq(
                    "eva_parse_tasks",
                    {"eva_doc_id": str(doc_id), "tenant_id": str(task.get("tenant_id") or "default")},
                    durable=True,
                )
                logger.info(f"扫描上传任务：已发布测评解析任务 eva_doc_id={doc_id}")
            else:
                doc_repo.update_document(
                    doc_id=str(doc_id),
                    payload={"save_https": save_https, "status": "processing"},
                    tenant_id=str(task.get("tenant_id") or "default"),
                    table_name=document_service.get_document_table_name(),
                )
                logger.info(f"扫描上传任务：更新文档完成 doc_id={doc_id} save_https={save_https} status=processing")
                document_service.publish_document_chunk_tasks_after_scan(
                    doc_id=str(doc_id),
                    save_https=save_https,
                    document_type=str(task.get("document_type") or "txt"),
                    tenant_id=str(task.get("tenant_id") or "default"),
                    strategy=document_service.parse_strategy_list(task.get("strategy")),
                )
                logger.info(f"扫描上传任务：已发布文档切割任务 doc_id={doc_id} strategy={document_service.parse_strategy_list(task.get('strategy')) or [0]}")
                
        upload_repo.upsert_fingerprint(
            {
                "tenant_id": str(task.get("tenant_id") or "default"),
                "file_hash": file_hash,
                "size": int(task.get("size") or 0),
                "cos_key": new_key,
                "document_id": str(doc_id) if doc_id else None,
                "scan_status": "passed",
            }
        )
        logger.info(f"扫描上传任务完成：通过 task_id={task_id} new_key={new_key} md5={file_hash}")
    else:
        upload_repo.update_upload_task(
            task_id=task_id,
            payload={"scan_status": "failed", "status": "failed"},
        )
        logger.info(f"扫描上传任务：标记上传任务失败 task_id={task_id}")
        if doc_id:
            if is_evaluation:
                eva_repo.update_eva_doc(
                    doc_id=str(doc_id),
                    payload={"status": "scan_failed"},
                    tenant_id=str(task.get("tenant_id") or "default"),
                    table_name="eva_doc",
                )
            else:
                doc_repo.update_document(
                    doc_id=str(doc_id),
                    payload={"status": "scan_failed"},
                    tenant_id=str(task.get("tenant_id") or "default"),
                    table_name=document_service.get_document_table_name(),
                )
        logger.info(f"扫描上传任务：标记文档失败 doc_id={doc_id} status=scan_failed")
    logger.info(f"扫描上传任务结束：task_id={task_id} 安全={ok}")
    return upload_repo.get_upload_task(task_id=task_id)

# 小文件
def scan_document_and_publish(
    *, doc_id: str, save_https: str, document_type: str, tenant_id: str, file_hash: Optional[str], title: str, file_type: str, user_id: int, filename: str, strategy: Optional[list[int]]
) -> Dict[str, Any]:
    """处理「小文件后端上传」的扫描、转正与解析编排。

    阶段说明：
    1) 通过 save_https 解析出 COS key（通常在 quarantine/）
    2) scan_cos_object：ClamAV 扫描 + 计算整文件 MD5
    3) 完整性校验：若 file_hash（上游提供）存在且与计算值不一致 -> 判定失败
    4) 扫描通过：
       - promote_from_quarantine：对象转正
       - 更新 document.save_https=转正后的地址 / status=processing
       - 发布解析任务（doc_parse_tasks）
       - 写入 file_fingerprint（passed），支持后续秒传复用
    5) 扫描失败：
       - document.status=scan_failed（解析 gating）
       - file_fingerprint.scan_status=failed（不会用于秒传复用）

    参数：
    - doc_id: document 表主键
    - save_https: document.save_https（后端内部 URL，含 /v1/cos/ 前缀）
    - document_type: 文档类型（pdf/docx/txt...）
    - tenant_id: 文档 tenant_id
    - file_hash: 可选，上游（前端/其他服务）声明的整文件 MD5
    - title/filename/user_id/file_type/strategy: 用于转正路径与解析任务编排

    返回：
    - {"status": "passed"|"failed", "save_https": ..., "file_hash": ...}
    """
    cos_key = document_service.extract_cos_key(save_https)
    logger.info(f"准备扫描 doc_id={doc_id} tenant_id={tenant_id} user_id={user_id} cos_key={cos_key} filename={filename or title} document_type={document_type}")
    ok, computed_hash, _size = scan_cos_object(cos_key)
    if file_hash and file_hash != computed_hash:
        ok = False
    logger.info(f"扫描完成 doc_id={doc_id} 安全={ok} 计算MD5={computed_hash} 大小Bytes={_size}")
    if ok:
        new_key = promote_from_quarantine(
            cos_key=cos_key,
            file_type=file_type,
            tenant_id=tenant_id,
            user_id=user_id,
            filename=filename or title,
        )
        logger.info(f"文件隔离区转正完成, 但是没落库 doc_id={doc_id} from={cos_key} to={new_key}")
        new_save_https = document_service.build_save_https(new_key)
        logger.debug(f"新的保存路径 doc_id={doc_id} new_save_https={new_save_https}")
        if strategy is not None and strategy:
            doc_repo.update_document(
            doc_id=doc_id,
            payload={"save_https": new_save_https, "status": "processing"},
            tenant_id=tenant_id,
            table_name=document_service.get_document_table_name(),
            )
            logger.info(f"更新文档完成, 等待发布切割信息 doc_id={doc_id} 更新了save_https={new_save_https} status=processing")
        else:
            doc_repo.update_document(
                doc_id=doc_id,
                payload={"save_https": new_save_https, "status": "success"},
                tenant_id=tenant_id,
                table_name=document_service.get_document_table_name(),
            )
            logger.info("更新文档完成,无切割任务")

        document_service.publish_document_chunk_tasks_after_scan(
            doc_id=doc_id,
            save_https=new_save_https,
            document_type=document_type,
            tenant_id=tenant_id,
            strategy=strategy,
        )
        
        upload_repo.upsert_fingerprint(
            {
                "tenant_id": tenant_id,
                "file_hash": computed_hash,
                "size": int(_size),
                "cos_key": new_key,
                "document_id": doc_id,
                "scan_status": "passed",
            }
        )
        return {"status": "passed", "save_https": new_save_https, "file_hash": computed_hash}
    doc_repo.update_document(
        doc_id=doc_id,
        payload={"status": "scan_failed"},
        tenant_id=tenant_id,
        table_name=document_service.get_document_table_name(),
    )
    upload_repo.upsert_fingerprint(
        {
            "tenant_id": tenant_id,
            "file_hash": computed_hash,
            "size": int(_size),
            "cos_key": cos_key,
            "document_id": doc_id,
            "scan_status": "failed",
        }
    )
    logger.info(f"失败 doc_id={doc_id} md5={computed_hash}")
    return {"status": "failed", "save_https": save_https, "file_hash": computed_hash}
