from __future__ import annotations
import os
from sqlalchemy import create_engine
from agentlz.config.settings import get_settings


"""
数据库连接辅助模块

提供统一的 MySQL, PostgreSQL 引擎构造和复用，避免在路由/服务层中散落连接创建逻辑。
"""

# 缓存的数据库引擎实例
_MYSQL_ENGINE = None
_PG_ENGINE = None



def get_pg_conn():
    """获取 PostgreSQL 连接（psycopg2 驱动）"""
    engine = get_pg_engine()
    return engine.raw_connection()


def build_mysql_url() -> str:
    """构建 MySQL 连接 URL（pymysql 驱动）"""
    s = get_settings()
    user = s.db_user or "root"
    pwd = s.db_password or ""
    host = s.db_host or "127.0.0.1"
    port = s.db_port or 3306
    name = s.db_name or "agentlz"
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}?charset=utf8mb4"


def get_mysql_engine():
    """初始化并缓存 SQLAlchemy MySQL Engine"""
    global _MYSQL_ENGINE
    if _MYSQL_ENGINE is None:
        _MYSQL_ENGINE = create_engine(build_mysql_url(), pool_pre_ping=True)
    return _MYSQL_ENGINE


def build_postgres_url() -> str:
    s = get_settings()
    user = s.pgvector_user or os.getenv("PGVECTOR_USER") or "agentlz"
    password = s.pgvector_password or os.getenv("PGVECTOR_PASSWORD") or "change-me"
    host = s.pgvector_host or os.getenv("PGVECTOR_HOST") or "127.0.0.1"
    port = int(s.pgvector_port or os.getenv("PGVECTOR_PORT") or 5432)
    db = s.pgvector_db or os.getenv("PGVECTOR_DB") or "agentlz"
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"



def get_pg_engine():
    """初始化并缓存 SQLAlchemy PostgreSQL Engine"""
    global _PG_ENGINE
    if _PG_ENGINE is None:
        _PG_ENGINE = create_engine(build_postgres_url(), pool_pre_ping=True)
    return _PG_ENGINE

