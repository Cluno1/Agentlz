#!/usr/bin/env python3
"""
AgentLZ 服务启动脚本
使用配置文件中的监听地址和端口
"""

import uvicorn
import os
import sys
from pathlib import Path

# 将项目根目录添加到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入设置
from agentlz.config.settings import get_settings

def main():
    """启动FastAPI服务"""
    
    # 从配置文件获取服务配置
    settings = get_settings()
    host = settings.server_host
    port = settings.server_port
    
    print(f"正在启动 AgentLZ 服务...")
    print(f"监听地址: http://{host}:{port}")
    print(f"健康检查: http://{host}:{port}/v1/health")
    print(f"RabbitMQ健康检查: http://{host}:{port}/v1/health/rabbitmq")
    print("=" * 50)
    
    # 使用uvicorn启动FastAPI应用
    uvicorn.run(
        "agentlz.app.http_langserve:app",
        host=host,
        port=port,
        reload=True,  # 开发模式下启用热重载
        log_level="info"
    )

if __name__ == "__main__":
    main()