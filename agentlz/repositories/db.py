from __future__ import annotations

"""
数据库连接辅助模块

提供统一的 MySQL 引擎构造和复用，避免在路由/服务层中散落连接创建逻辑。
"""

from sqlalchemy import create_engine

from agentlz.config.settings import get_settings


_ENGINE = None


def build_mysql_url() -> str:
    """构建 MySQL 连接 URL（pymysql 驱动）"""
    s = get_settings()
    user = s.db_user or "root"
    pwd = s.db_password or ""
    host = s.db_host or "127.0.0.1"
    port = s.db_port or 3306
    name = s.db_name or "agentlz"
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{name}?charset=utf8mb4"


def get_engine():
    """初始化并缓存 SQLAlchemy Engine"""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(build_mysql_url(), pool_pre_ping=True)
    return _ENGINE