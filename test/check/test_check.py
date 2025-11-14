

from agentlz.agents.check.check_agent_1 import get_check_agent
from time import sleep


def test_perfect_match():
    """测试1: 完美匹配 - 事实完全实现了目标"""
    check_agent = get_check_agent()

    objectMsg = "创建一个包含用户名、邮箱和年龄的Python字典"
    factMsg = "{'username': '张三', 'email': 'zhangsan@example.com', 'age': 25}"

    result = check_agent.invoke({"objectMsg": objectMsg, "factMsg": factMsg})
    print("=== 测试1: 完美匹配 ===")
    print(f"目标: {objectMsg}")
    print(f"事实: {factMsg}")
    print(f"判断: {result.judge}")
    print(f"评分: {result.score}")
    print(f"理由: {result.reasoning}")
    print()

    return result


def test_partial_match():
    """测试2: 部分匹配 - 事实缺少一些目标要求的元素"""
    check_agent = get_check_agent()

    objectMsg = "创建一个包含用户名、邮箱和年龄的Python字典"
    factMsg = "{'username': '张三', 'email': 'zhangsan@example.com'}"

    result = check_agent.invoke({"objectMsg": objectMsg, "factMsg": factMsg})
    print("=== 测试2: 部分匹配 ===")
    print(f"目标: {objectMsg}")
    print(f"事实: {factMsg}")
    print(f"判断: {result.judge}")
    print(f"评分: {result.score}")
    print(f"理由: {result.reasoning}")
    print()

    return result


def test_no_match():
    """测试3: 不匹配 - 事实与目标完全无关"""
    check_agent = get_check_agent()

    objectMsg = "创建一个包含用户名、邮箱和年龄的Python字典"
    factMsg = "今天天气很好，适合出去散步"

    result = check_agent.invoke({"objectMsg": objectMsg, "factMsg": factMsg})
    print("=== 测试3: 不匹配 ===")
    print(f"目标: {objectMsg}")
    print(f"事实: {factMsg}")
    print(f"判断: {result.judge}")
    print(f"评分: {result.score}")
    print(f"理由: {result.reasoning}")
    print()

    return result


def test_super_perfect_false_match():
    """测试4: 超完美匹配 - 事实不仅实现了目标，还额外提供了更多有用信息, 但是是错误的"""
    check_agent = get_check_agent()

    objectMsg = "创建一个包含用户名、邮箱和年龄的Python字典"
    factMsg = "{'username': '张三', 'email': 'zhangsan@example.com', 'age': 25, 'phone': '13800138000', 'address': '北京市朝阳区', 'created_at': '2024-01-15'}"

    result = check_agent.invoke({"objectMsg": objectMsg, "factMsg": factMsg})
    print("=== 测试4: 超完美匹配 ===")
    print(f"目标: {objectMsg}")
    print(f"事实: {factMsg}")
    print(f"判断: {result.judge}")
    print(f"评分: {result.score}")
    print(f"理由: {result.reasoning}")
    print()

    return result


def test_super_perfect_true_match():
    """测试5: 超完美匹配 - 事实完全实现了目标, 并且提供了更多有用信息,但是确实是正确的,并且要有高评分"""
    check_agent = get_check_agent()

    objectMsg = "介绍自然坐标系的概念"
    factMsg = """自然坐标系是一种沿着物体运动轨迹建立的坐标系，其基矢量随物体运动而变化。
    
主要特点：
1. 切向单位矢量(t)：沿运动轨迹切线方向
2. 法向单位矢量(n)：垂直于切线，指向曲率中心
3. 副法向单位矢量(b)：t×n得到，垂直于运动平面

应用场景：
- 质点运动学分析
- 刚体转动问题
- 曲线路径规划

优势：
- 简化曲线运动分析
- 物理意义明确
- 便于计算速度和加速度分量

示例：汽车在弯道上行驶时，使用自然坐标系可以更好地分析其切向加速度和向心加速度。"""

    result = check_agent.invoke({"objectMsg": objectMsg, "factMsg": factMsg})
    print("=== 测试5: 超完美匹配 - 自然坐标系 ===")
    print(f"目标: {objectMsg}")
    print(f"事实: {factMsg}")
    print(f"判断: {result.judge}")
    print(f"评分: {result.score}")
    print(f"理由: {result.reasoning}")
    print()

    return result


def run_all_tests():
    """运行所有测试用例"""
    print("开始运行 Check Agent 测试...\n")

    test1_result = test_perfect_match()

    test2_result = test_partial_match()

    test3_result = test_no_match()

    test4_result = test_super_perfect_false_match()

    test5_result = test_super_perfect_true_match()

    print("=== 测试总结 ===")
    print(f"测试1 (完美匹配): 判断={test1_result.judge}, 评分={test1_result.score}")
    print(f"测试2 (部分匹配): 判断={test2_result.judge}, 评分={test2_result.score}")
    print(f"测试3 (不匹配): 判断={test3_result.judge}, 评分={test3_result.score}")
    print(f"测试4 (超完美匹配): 判断={test4_result.judge}, 评分={test4_result.score}")
    print(
        f"测试5 (超完美匹配-自然坐标系): 判断={test5_result.judge}, 评分={test5_result.score}")


if __name__ == "__main__":
    run_all_tests()
