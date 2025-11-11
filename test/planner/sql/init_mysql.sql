-- 初始化 MySQL 数据库与表结构（手动执行）
-- 目标库：agentlz

CREATE DATABASE IF NOT EXISTS agentlz
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE agentlz;

CREATE TABLE IF NOT EXISTS mcp_agents (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  transport VARCHAR(32) NOT NULL DEFAULT 'stdio',
  command VARCHAR(255) NOT NULL DEFAULT 'python',
  args TEXT NOT NULL, -- 以 JSON 文本存储，例如 ["d:/PyCharm/AgentCode/Agentlz/test/planner/test_tool/math_agent.py"]
  description TEXT NOT NULL,
  category VARCHAR(64) NULL,
  trust_score DOUBLE NOT NULL DEFAULT 0.0,
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 索引：若存在则先删除再创建（MySQL 8+ 支持 IF EXISTS）
DROP INDEX IF EXISTS idx_mcp_score ON mcp_agents;
CREATE INDEX idx_mcp_score ON mcp_agents (trust_score);