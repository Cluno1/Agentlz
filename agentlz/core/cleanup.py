from __future__ import annotations
import logging
import signal
import sys
from typing import Callable, List
from agentlz.core.external_services import close_all_connections

logger = logging.getLogger(__name__)

# 清理函数列表
cleanup_functions: List[Callable[[], None]] = []


def register_cleanup_function(func: Callable[[], None]) -> None:
    """注册清理函数"""
    cleanup_functions.append(func)


def cleanup_all() -> None:
    """执行所有清理函数"""
    logger.info("开始执行应用清理...")
    
    # 关闭外部服务连接
    try:
        close_all_connections()
        logger.info("外部服务连接已关闭")
    except Exception as e:
        logger.error(f"关闭外部服务连接时出错: {e}")
    
    # 执行其他注册的清理函数
    for func in cleanup_functions:
        try:
            func()
        except Exception as e:
            logger.error(f"执行清理函数 {func.__name__} 时出错: {e}")
    
    logger.info("应用清理完成")


def signal_handler(signum: int, frame) -> None:
    """信号处理函数"""
    logger.info(f"接收到信号 {signum}，开始清理...")
    cleanup_all()
    sys.exit(0)


def register_signal_handlers() -> None:
    """注册信号处理函数"""
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill命令
    logger.info("信号处理函数已注册")


def setup_cleanup_at_exit() -> None:
    """设置程序退出时的清理函数"""
    import atexit
    atexit.register(cleanup_all)
    logger.info("退出清理函数已注册")