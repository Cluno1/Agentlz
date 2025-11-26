from __future__ import annotations
# from agentlz.core.external_services import upload_to_cos
from agentlz.core.logger import setup_logging
def upload_document_to_cos(document: bytes, filename: str) -> str:
    """上传文档到COS current是测试阶段, 仅仅返回测试接口"""
    # return upload_to_cos(document, filename)
    logger = setup_logging()
    logger.info(f"上传cos文档 filename: {filename}")
    return 'https://example.com?id=1123'