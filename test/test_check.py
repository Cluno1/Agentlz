""" 
运行该测试:
    python -m test.test_check

输出:

开始运行 Check Agent 测试...

2025-11-10 17:54:03,440 INFO httpx: HTTP Request: POST https://www.dmxapi.cn/v1/chat/completions "HTTP/1.1 200 OK"
=== 测试1: 完美匹配 ===
目标: 创建一个包含用户名、邮箱和年龄的Python字典
事实: {'username': '张三', 'email': 'zhangsan@example.com', 'age': 25}
判断: True
评分: 100
理由: 事实中创建的Python字典完全符合目标要求，包含了所有必需的键（'username'、'email'和'age'），并且每个键都有适当的值。字典的结构正确，语法无误，完全实现了目标。

2025-11-10 17:54:19,251 INFO httpx: HTTP Request: POST https://www.dmxapi.cn/v1/chat/completions "HTTP/1.1 200 OK"
=== 测试2: 部分匹配 ===
目标: 创建一个包含用户名、邮箱和年龄的Python字典
事实: {'username': '张三', 'email': 'zhangsan@example.com'}
判断: False
评分: 40
理由: 事实中的字典正确包含了用户名和邮箱的键值对，但是缺少了目标中要求的年龄键值对。由于目标明确要求创建包含用户名、邮箱和年龄的字典，而事实只实现了其中两个部分，因此没有完全达成目标。

2025-11-10 17:54:39,318 INFO httpx: HTTP Request: POST https://www.dmxapi.cn/v1/chat/completions "HTTP/1.1 200 OK"
=== 测试3: 不匹配 ===
目标: 创建一个包含用户名、邮箱和年龄的Python字典
事实: 今天天气很好，适合出去散步
判断: False
评分: 1
理由: 事实'今天天气很好，适合出去散步'与目标'创建一个包含用户名、邮箱和年龄的Python字典'完全不相关。事实中没有提到任何关于Python编程、字典创建或用户信息的内容。因此，这个事实完全没有达成目标的要求。

2025-11-10 17:54:59,321 INFO httpx: HTTP Request: POST https://www.dmxapi.cn/v1/chat/completions "HTTP/1.1 200 OK"
=== 测试4: 超完美匹配 ===
目标: 创建一个包含用户名、邮箱和年龄的Python字典
事实: {'username': '张三', 'email': 'zhangsan@example.com', 'age': 25, 'phone': '13800138000', 'address': '北京市朝阳区', 'created_at': '2024-01-15'}
判断: False
评分: 65
理由: 事实中的字典包含了目标要求的所有键值对（username、email和age），这是正确的部分。但是，它还额外包含了phone、address和created_at这三个不在目标要求中的键值对，这超出了目标的范围。因此，虽然基本满足了要求，但不符合'只包含用户名、邮箱和年龄'的精确要求，所以判断为失败。

2025-11-10 17:55:30,306 INFO httpx: HTTP Request: POST https://www.dmxapi.cn/v1/chat/completions "HTTP/1.1 200 OK"
=== 测试5: 超完美匹配 - 自然坐标系 ===
目标: 介绍自然坐标系的概念
事实: 自然坐标系是一种沿着物体运动轨迹建立的坐标系，其基矢量随物体运动而变化。
    
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

示例：汽车在弯道上行驶时，使用自然坐标系可以更好地分析其切向加速度和向心加速度。
判断: True
评分: 95
理由: 该事实全面介绍了自然坐标系的概念，包括其定义（沿物体运动轨迹建立，基矢量随运动变化）、三个基本基矢量（切向、法向、副法向）的定义和方向、应用场景（质点运动学分析、刚体转动问题、曲线路径规划）、优势（简化分析、物理意义明确、便于计算）以及具体应用示例（汽车弯道行驶分析）。内容组织清晰，表述准确，没有错误或遗漏，完全达成了介绍自然坐标系概念的目标。

=== 测试总结 ===
测试1 (完美匹配): 判断=True, 评分=100
测试2 (部分匹配): 判断=False, 评分=40
测试3 (不匹配): 判断=False, 评分=1
测试4 (超完美匹配): 判断=False, 评分=65
测试5 (超完美匹配-自然坐标系): 判断=True, 评分=95
"""

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
