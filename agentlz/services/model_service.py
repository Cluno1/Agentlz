from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException
from agentlz.config.settings import get_settings
from agentlz.repositories import model_repository as repo

def _table_name() -> str:
    """获取模型表名（Settings.MODEL_TABLE_NAME，默认 'model'）。"""
    s = get_settings()
    return getattr(s, "model_table_name", "model")

def list_models(
    *,
    page: int,
    per_page: int,
    sort: str,
    order: str,
    q: Optional[str],
) -> Tuple[List[Dict[str, Any]], int]:
    """分页列出模型。

    支持：
    - 名称模糊查询 `q`
    - 排序与分页（按白名单字段）
    """
    table = _table_name()
    return repo.list_models(page=page, per_page=per_page, sort=sort, order=order, q=q, table_name=table)

def get_model_by_id(*, model_id: int) -> Optional[Dict[str, Any]]:
    """按主键查询模型。"""
    table = _table_name()
    return repo.get_model_by_id(model_id=model_id, table_name=table)

def get_model_by_name(*, name: str) -> Optional[Dict[str, Any]]:
    """按名称查询模型。"""
    table = _table_name()
    return repo.get_model_by_name(name=name, table_name=table)

def create_model(*, payload: Dict[str, Any]) -> Dict[str, Any]:
    """创建模型。

    要求：
    - name 必填且唯一；若冲突由数据库唯一约束抛错，上层可捕获并转换为 409。
    """
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    table = _table_name()
    return repo.create_model(payload=payload, table_name=table)

def update_model(*, model_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新模型。"""
    table = _table_name()
    return repo.update_model(model_id=model_id, payload=payload, table_name=table)

def delete_model(*, model_id: int) -> bool:
    """删除模型。"""
    table = _table_name()
    return repo.delete_model(model_id=model_id, table_name=table)
