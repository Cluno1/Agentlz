-- 插入 MCP agents 测试数据（包含 test_tool 两个满分与样例较低分）
USE agentlz;

-- 为了对比演示，这里先清空表（如需保留数据请移除此语句）
DELETE FROM mcp_agents;

INSERT INTO mcp_agents (name, transport, command, args, description, category, trust_score)
VALUES
  -- 数学同类型的多条记录，路径指向同一个 math_agent.py，分数不同
  (
    'math_agent_top',
    'stdio',
    'python',
    '["test/planner/test_tool/math_agent.py"]',
    '数学计算 agent（最高可信度）',
    'math',
    100
  ),
  (
    'math_agent_pro',
    'stdio',
    'python',
    '["test/planner/test_tool/math_agent.py"]',
    '数学计算 agent（高可信度）',
    'math',
    95
  ),
  (
    'math_agent_fast',
    'stdio',
    'python',
    '["test/planner/test_tool/math_agent.py"]',
    '数学计算 agent（较高可信度）',
    'math',
    88
  ),
  (
    'math_agent_basic',
    'stdio',
    'python',
    '["test/planner/test_tool/math_agent.py"]',
    '数学计算 agent（中等可信度）',
    'math',
    75
  ),
  (
    'math_agent_beta',
    'stdio',
    'python',
    '["test/planner/test_tool/math_agent.py"]',
    '数学计算 agent（实验版本，较低可信度）',
    'math',
    60
  ),
  -- 语言处理同类型的多条记录，路径指向同一个 language_agent.py，分数不同
  (
    'language_agent_top',
    'stdio',
    'python',
    '["test/planner/test_tool/language_agent.py"]',
    '语言处理 agent（最高可信度）',
    'language',
    100
  ),
  (
    'language_agent_pro',
    'stdio',
    'python',
    '["test/planner/test_tool/language_agent.py"]',
    '语言处理 agent（高可信度）',
    'language',
    93
  ),
  (
    'language_agent_fast',
    'stdio',
    'python',
    '["test/planner/test_tool/language_agent.py"]',
    '语言处理 agent（较高可信度）',
    'language',
    86
  ),
  (
    'language_agent_basic',
    'stdio',
    'python',
    '["test/planner/test_tool/language_agent.py"]',
    '语言处理 agent（中等可信度）',
    'language',
    74
  ),
  (
    'language_agent_beta',
    'stdio',
    'python',
    '["test/planner/test_tool/language_agent.py"]',
    '语言处理 agent（实验版本，较低可信度）',
    'language',
    58
  ),
  -- 额外的对照样例（非数学），便于观察降序排序对比
  (
    'email_agent',
    'stdio',
    'python',
    '["agentlz/tools/email.py"]',
    '邮件工具样例',
    'tool',
    80
  );

-- 可按需追加更多样例（分数 50/40 等），用于验证 ORDER BY trust_score DESC