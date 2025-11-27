#!/usr/bin/env python3
"""
RabbitMQ消息清空工具

功能：
- 清空指定队列的消息
- 清空所有队列的消息
- 列出所有队列及其消息数量
- 支持交互式操作

使用方法：
    #  首先确保在test/rabbitmq目录下运行
    cd ./test/rabbitmq


    # 可选
    python purge_queues.py --help
    python purge_queues.py --list                    # 列出所有队列
    python purge_queues.py --queue my_queue          # 清空指定队列
    python purge_queues.py --all                     # 清空所有队列
    python purge_queues.py --interactive             # 交互式模式
"""

from __future__ import annotations
import argparse
import sys
import os
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from agentlz.core.external_services import get_rabbitmq_connection, get_rabbitmq_channel
from agentlz.core.logger import setup_logging

logger = setup_logging()


def get_all_queues() -> List[Dict[str, Any]]:
    """获取所有队列信息"""
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # 使用RabbitMQ管理API获取队列信息
        # 这里我们通过basic_get来检查队列状态
        queues = []
        
        # 获取队列列表（通过声明一个临时队列来获取信息）
        try:
            # 尝试获取默认交换机上的队列
            result = channel.queue_declare(queue='', passive=True)
            
            # 获取队列统计信息
            queue_info = {
                'name': result.method.queue,
                'messages': result.method.message_count,
                'consumers': result.method.consumer_count,
                'durable': False,  # 临时队列
                'auto_delete': True
            }
            queues.append(queue_info)
            
        except Exception as e:
            logger.warning(f"获取队列信息时出错: {e}")
            
        return queues
        
    except Exception as e:
        logger.error(f"获取队列列表失败: {e}")
        raise RuntimeError(f"获取队列列表失败: {e}") from e


def purge_queue(queue_name: str) -> bool:
    """清空指定队列的消息"""
    try:
        connection = get_rabbitmq_connection()
        channel = connection.channel()
        
        # 声明队列（如果存在则获取信息，不存在则创建）
        try:
            result = channel.queue_declare(queue=queue_name, passive=True)
            message_count = result.method.message_count
            
            if message_count == 0:
                logger.info(f"队列 '{queue_name}' 已经是空的")
                return True
                
            logger.info(f"队列 '{queue_name}' 有 {message_count} 条消息，准备清空...")
            
        except Exception:
            logger.warning(f"队列 '{queue_name}' 不存在")
            return False
        
        # 清空队列
        channel.queue_purge(queue=queue_name)
        logger.info(f"队列 '{queue_name}' 已清空")
        
        return True
        
    except Exception as e:
        logger.error(f"清空队列 '{queue_name}' 失败: {e}")
        return False


def purge_all_queues() -> Dict[str, Any]:
    """清空所有队列的消息"""
    try:
        # 注意：这里我们需要列出所有队列
        # 由于RabbitMQ的Python客户端没有直接列出所有队列的方法，
        # 我们需要知道队列名称或使用管理API
        
        logger.info("开始清空所有队列...")
        
        # 常见队列名称列表（你可以根据实际情况修改）
        common_queues = [
            'document_processing',
            'email_queue',
            'notification_queue',
            'task_queue',
            'default',
            'celery',
            'celery_default'
        ]
        
        results = {
            'success': [],
            'failed': [],
            'not_found': []
        }
        
        for queue_name in common_queues:
            try:
                if purge_queue(queue_name):
                    results['success'].append(queue_name)
                else:
                    results['not_found'].append(queue_name)
            except Exception as e:
                logger.error(f"清空队列 '{queue_name}' 失败: {e}")
                results['failed'].append(queue_name)
        
        logger.info(f"清空完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}, 未找到 {len(results['not_found'])}")
        
        return results
        
    except Exception as e:
        logger.error(f"清空所有队列失败: {e}")
        raise RuntimeError(f"清空所有队列失败: {e}") from e


def interactive_mode():
    """交互式模式"""
    print("\n=== RabbitMQ 消息清空工具 ===")
    print("1. 列出所有队列")
    print("2. 清空指定队列")
    print("3. 清空所有队列")
    print("4. 退出")
    
    while True:
        try:
            choice = input("\n请选择操作 (1-4): ").strip()
            
            if choice == '1':
                queues = get_all_queues()
                if queues:
                    print("\n队列列表:")
                    for queue in queues:
                        print(f"  - {queue['name']}: {queue['messages']} 条消息")
                else:
                    print("没有找到队列")
                    
            elif choice == '2':
                queue_name = input("请输入队列名称: ").strip()
                if queue_name:
                    if purge_queue(queue_name):
                        print(f"队列 '{queue_name}' 清空成功")
                    else:
                        print(f"队列 '{queue_name}' 清空失败或不存在")
                else:
                    print("队列名称不能为空")
                    
            elif choice == '3':
                confirm = input("确定要清空所有队列吗? (yes/no): ").strip().lower()
                if confirm in ['yes', 'y']:
                    results = purge_all_queues()
                    print(f"\n清空结果:")
                    print(f"  成功: {len(results['success'])} 个队列")
                    print(f"  失败: {len(results['failed'])} 个队列")
                    print(f"  未找到: {len(results['not_found'])} 个队列")
                else:
                    print("操作已取消")
                    
            elif choice == '4':
                print("退出程序")
                break
                
            else:
                print("无效的选择，请重新输入")
                
        except KeyboardInterrupt:
            print("\n程序被中断")
            break
        except Exception as e:
            logger.error(f"交互式操作出错: {e}")
            print(f"操作出错: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="RabbitMQ消息清空工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
    python purge_queues.py --list                    # 列出所有队列
    python purge_queues.py --queue my_queue          # 清空指定队列
    python purge_queues.py --all                     # 清空所有队列
    python purge_queues.py --interactive           # 交互式模式
        """
    )
    
    parser.add_argument('--list', '-l', action='store_true', 
                       help='列出所有队列及其消息数量')
    parser.add_argument('--queue', '-q', type=str, 
                       help='清空指定的队列')
    parser.add_argument('--all', '-a', action='store_true', 
                       help='清空所有队列（谨慎使用）')
    parser.add_argument('--interactive', '-i', action='store_true', 
                       help='交互式模式')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='显示详细日志')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logger.setLevel('DEBUG')
    
    try:
        # 检查参数
        if not any([args.list, args.queue, args.all, args.interactive]):
            parser.print_help()
            return
        
        if args.interactive:
            interactive_mode()
        elif args.list:
            queues = get_all_queues()
            if queues:
                print("\n队列列表:")
                for queue in queues:
                    print(f"  - {queue['name']}: {queue['messages']} 条消息")
            else:
                print("没有找到队列或无法获取队列信息")
                
        elif args.queue:
            if purge_queue(args.queue):
                print(f"队列 '{args.queue}' 清空成功")
            else:
                print(f"队列 '{args.queue}' 清空失败或不存在")
                sys.exit(1)
                
        elif args.all:
            confirm = input("确定要清空所有队列吗? 此操作不可恢复 (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                results = purge_all_queues()
                print(f"\n清空结果:")
                print(f"  成功: {len(results['success'])} 个队列")
                print(f"  失败: {len(results['failed'])} 个队列")
                print(f"  未找到: {len(results['not_found'])} 个队列")
            else:
                print("操作已取消")
                
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()