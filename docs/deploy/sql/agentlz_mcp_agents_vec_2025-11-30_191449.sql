--
-- PostgreSQL database dump
--

\restrict zNbGCF1WnBgVwvUbpJIwgaPoh5NziPZdpLp2Dc3lTOcmb4In5xfSR0nCuUG5w8J

-- Dumped from database version 16.11 (Debian 16.11-1.pgdg12+1)
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: mcp_agents_vec; Type: TABLE; Schema: public; Owner: agentlz
--

CREATE TABLE public.mcp_agents_vec (
    id bigint NOT NULL,
    name text,
    transport text,
    command text,
    description text,
    category text,
    embedding public.vector(512),
    trust_score real DEFAULT 0
);


ALTER TABLE public.mcp_agents_vec OWNER TO agentlz;

--
-- Name: mcp_agents_vec mcp_agents_vec_pkey; Type: CONSTRAINT; Schema: public; Owner: agentlz
--

ALTER TABLE ONLY public.mcp_agents_vec
    ADD CONSTRAINT mcp_agents_vec_pkey PRIMARY KEY (id);


--
-- PostgreSQL database dump complete
--

\unrestrict zNbGCF1WnBgVwvUbpJIwgaPoh5NziPZdpLp2Dc3lTOcmb4In5xfSR0nCuUG5w8J
--
-- Data migration from MySQL table `mcp_agents` into PostgreSQL `public.mcp_agents_vec`
-- Fields mapped: id, name, transport, command, description, category, trust_score
-- Note: `embedding` left NULL; to be populated by offline embedding job
--
INSERT INTO public.mcp_agents_vec (id, name, transport, command, description, category, trust_score) VALUES
  (23, 'math_agent_top', 'stdio', 'python', '数学计算 agent（最高可信度）', 'math', 82),
  (24, 'math_agent_pro', 'stdio', 'python', '数学计算 agent（高可信度）', 'math', 96),
  (25, 'math_agent_fast', 'stdio', 'python', '数学计算 agent（较高可信度）', 'math', 88),
  (26, 'math_agent_basic', 'stdio', 'python', '数学计算 agent（中等可信度）', 'math', 75),
  (27, 'math_agent_beta', 'stdio', 'python', '数学计算 agent（实验版本，较低可信度）', 'math', 60),
  (28, 'language_agent_top', 'stdio', 'python', '语言处理 agent（最高可信度）', 'language', 82),
  (29, 'language_agent_pro', 'stdio', 'python', '语言处理 agent（高可信度）', 'language', 92),
  (30, 'language_agent_fast', 'stdio', 'python', '语言处理 agent（较高可信度）', 'language', 86),
  (31, 'language_agent_basic', 'stdio', 'python', '语言处理 agent（中等可信度）', 'language', 74),
  (32, 'language_agent_beta', 'stdio', 'python', '语言处理 agent（实验版本，较低可信度）', 'language', 58),
  (33, 'email_agent', 'stdio', 'python', '邮件工具样例', 'tool', 80),
  (34, 'exa_remote', 'http', 'npx', 'Exa github代码搜索远端 MCP 服务', 'tool', 75),
  (35, 'markitdown', 'stdio', 'docker', 'Python tool for converting files and office documents to Markdown.', '开发', 83096),
  (36, 'servers', 'stdio', 'docker', 'A collection of reference implementations for Model Context Protocol (MCP) servers.', 'Official', 72865),
  (37, 'context7', 'stdio', 'docker', 'Context7 MCP Server -- Up-to-date code documentation for LLMs and AI code editors', '开发', 37528),
  (38, 'semantic-kernel', 'stdio', 'docker', 'Integrate cutting-edge LLM technology quickly and easily into your apps', '开发', 26701),
  (39, 'github', 'stdio', 'docker', 'GitHub MCP Server connects AI tools to GitHub for code management and automation.', '开发', 24597),
  (40, 'playwright-mcp', 'stdio', 'docker', 'Playwright MCP server', '开发', 23432),
  (41, 'TrendRadar', 'stdio', 'docker', 'TrendRadar: Deploy a news assistant in 30 seconds to filter relevant news.', '社交', 20877),
  (42, 'fastmcp', 'stdio', 'docker', 'FastMCP is a fast, Pythonic framework for building MCP servers and clients.', '开发', 20431),
  (43, 'repomix', 'stdio', 'docker', 'Repomix packages your codebase into AI-friendly formats for seamless integration.', '创作', 20256),
  (44, 'python-sdk', 'stdio', 'docker', 'Python SDK for implementing the Model Context Protocol (MCP).', '开发', 20151),
  (45, 'mastra', 'stdio', 'docker', 'Mastra is a framework for building AI-powered applications and agents.', '开发', 18194),
  (46, 'serena', 'stdio', 'docker', 'Serena is a free, open-source toolkit that enhances LLMs with IDE-like coding tools.', '开发', 16208),
  (47, 'apisix', 'stdio', 'docker', 'Apache APISIX is an open-source API gateway for managing APIs and microservices.', '开发', 15871),
  (48, 'opik', 'stdio', 'docker', 'Debug, evaluate, and monitor your LLM applications, RAG systems, and agentic workflows with comprehensive tracing, automated evaluations, and production-ready dashboards.', '开发', 15838),
  (49, 'chrome-devtools-mcp', 'stdio', 'docker', 'chrome-devtools-mcp enables AI coding agents to control and inspect Chrome for automation and debugging.', '开发', 14945),
  (50, 'blender-mcp', 'stdio', 'docker', 'BlenderMCP integrates Blender with Claude AI for enhanced 3D modeling.', '开发', 14190),
  (51, 'pydantic-ai', 'stdio', 'docker', 'Pydantic AI: A GenAI Agent Framework built with Pydantic.', '开发', 13442),
  (52, 'semgrep', 'stdio', 'docker', 'Semgrep: Fast code scanning tool for security and quality.', '开发', 13378),
  (53, 'mcp-for-beginners', 'stdio', 'docker', 'Open-source curriculum introducing MCP fundamentals with real-world examples.', '开发', 13331),
  (54, 'Figma-Context-MCP', 'stdio', 'docker', 'Framelink MCP for Figma enables seamless design implementation across frameworks.', '开发', 11857),
  (55, 'genai-toolbox', 'stdio', 'docker', 'MCP Toolbox for Databases is an open-source server that simplifies database tool development.', '开发', 11422),
  (56, 'cua', 'stdio', 'docker', 'Cua is a versatile project supporting Python and Swift on macOS.', '开发', 11295),
  (57, 'fastapi_mcp', 'stdio', 'docker', 'FastAPI-MCP exposes FastAPI endpoints as Model Context Protocol tools with authentication.', '开发', 11088),
  (58, 'typescript-sdk', 'stdio', 'docker', 'MCP TypeScript SDK for building and running servers with advanced features.', '官方', 10782),
  (59, 'n8n-mcp', 'stdio', 'docker', 'n8n-mcp is a Model Context Protocol server for n8n automation.', '开发', 10035),
  (60, 'claude-flow', 'stdio', 'docker', 'Agent orchestration platform for Claude with multi-agent swarms and MCP.', '开发', 9956),
  (61, 'bytebot', 'stdio', 'docker', 'Bytebot: An open-source AI desktop agent that automates tasks for you.', '生产', 9693),
  (62, 'zen-mcp-server', 'stdio', 'docker', 'Zen MCP Server integrates multiple AI CLIs for streamlined workflows.', '开发', 9676),
  (63, 'gemini-mcp-server', 'stdio', 'docker', 'Gemini MCP Server', '开发', 9668),
  (64, 'inbox-zero', 'stdio', 'docker', 'Inbox Zero is an AI email assistant that organizes, pre-drafts replies, and tracks follow-ups.', '生产', 9403),
  (65, 'mcp-chrome', 'stdio', 'docker', 'MCP Server transforms your Chrome into an AI-powered assistant.', '社交', 9298),
  (66, 'cognee', 'stdio', 'docker', 'Cognee - An AI memory system for accurate and persistent data retention.', '创作', 8797),
  (67, 'sqlglot', 'stdio', 'docker', 'SQLGlot is a no-dependency SQL parser and transpiler supporting 31 dialects.', '开发', 8592),
  (68, 'mcp-use-official', 'stdio', 'docker', 'mcp-use is a full-stack MCP framework for building servers, clients, and AI agents.', '社交', 8265),
  (69, 'mcp-use-pietrozullo', 'stdio', 'docker', 'MCP-Use connects LLMs to MCP tools via a unified interface.', '开发', 8262),
  (70, 'eino', 'stdio', 'docker', 'Eino is a project for efficient microservices communication.', '开发', 8245),
  (71, 'convex-backend', 'stdio', 'docker', 'Convex is an open-source reactive database for web app developers.', '开发', 8183),
  (72, 'tools', 'stdio', 'docker', 'Go Tools provides static analysis tools and LSP server for Go programs.', '开发', 7825),
  (73, 'Upsonic-gpt-computer-assistant', 'stdio', 'docker', 'The most reliable AI agent framework that supports MCP.', '社交', 7682),
  (74, 'Upsonic-core', 'stdio', 'docker', 'Upsonic is an AI agent framework for fintech and banks, tested against attacks.', '社交', 7682),
  (75, 'mcp-go', 'stdio', 'docker', 'MCP Go is a Go implementation of the Model Context Protocol for LLM integration.', '开发', 7657),
  (76, 'inspector', 'stdio', 'docker', 'MCP Inspector is a developer tool for testing and debugging MCP servers via a web UI.', '开发', 7494),
  (77, 'mcp', 'stdio', 'docker', 'A suite of specialized MCP servers for optimizing AWS usage.', '官方', 7421),
  (78, 'xiaohongshu-mcp', 'stdio', 'docker', 'MCP for xiaohongshu.com, offering deployment solutions and user-friendly tools.', '社交', 7020),
  (79, 'git-mcp', 'stdio', 'docker', 'GitMCP is a tool for managing Git repositories with enhanced features.', '开发', 6987),
  (80, 'higress', 'stdio', 'docker', 'Higress is an AI Native API Gateway designed for efficient API management.', '开发', 6886),
  (81, 'browser-tools-mcp', 'stdio', 'docker', 'A browser monitoring tool enhancing AI applications via MCP for data analysis.', '开发', 6860),
  (82, 'GhidraMCP', 'stdio', 'docker', 'GhidraMCP is a Model Context Protocol server for LLMs.', '开发', 6535),
  (83, 'awesome-llm-apps', 'stdio', 'docker', 'Collection of LLM Applications', '开发', 6440),
  (84, 'valuecell', 'stdio', 'docker', 'Valuecell is a Python-based project licensed under Apache 2.0.', '金融', 6378),
  (85, 'github', 'http', 'http', 'GitHub MCP Server connects AI tools to GitHub for code management and automation.', '开发', 24597),
  (86, 'context7', 'http', 'http', 'Context7 MCP Server -- Up-to-date code documentation for LLMs and AI code editors', '开发', 37528),
  (118, 'notion-mcp-server', 'http', 'http', 'Official Notion MCP Server with OAuth-based remote hosting.', '官方', 3496);

