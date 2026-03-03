from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel


class UploadInitRequest(BaseModel):
    filename: str
    size: int
    content_type: Optional[str] = None
    file_type: str
    file_hash: Optional[str] = None
    type: str = "self"
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    strategy: Optional[List[str]] = None
    document_type: Optional[str] = None


class UploadInitResponse(BaseModel):
    task_id: Optional[int] = None
    cos_key: Optional[str] = None
    upload_id: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_count: Optional[int] = None
    status: str
    document_id: Optional[str] = None
    final_url: Optional[str] = None


class UploadStatusResponse(BaseModel):
    status: str
    scan_status: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_count: Optional[int] = None
    uploaded_parts: List[int] = []
    final_url: Optional[str] = None
    document_id: Optional[str] = None


class UploadPartUrlRequest(BaseModel):
    part_number: int
    part_size: int
    part_hash: Optional[str] = None


class UploadPartUrlResponse(BaseModel):
    url: str
    method: str = "PUT"
    required_headers: dict = {}


class UploadCompletePart(BaseModel):
    part_number: int
    etag: str
    part_hash: Optional[str] = None


class UploadCompleteRequest(BaseModel):
    parts: List[UploadCompletePart]
    file_hash: Optional[str] = None


class UploadCompleteResponse(BaseModel):
    status: str
    document_id: Optional[str] = None
    final_url: Optional[str] = None
