INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('markitdown', 'stdio', 'docker', '{"mcpServers":{"markitdown":{"command":"docker","args":["run","--rm","-i","markitdown-mcp:latest"]}}}', 'Python tool for converting files and office documents to Markdown.', '开发', 83096);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('servers', 'stdio', 'docker', '{"mcpServers":{"servers":{"command":"docker","args":["run","--rm","-i","ghcr.io/modelcontextprotocol/servers:latest"]}}}', 'A collection of reference implementations for Model Context Protocol (MCP) servers.', 'Official', 72865);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('context7', 'stdio', 'docker', '{"mcpServers":{"context7":{"command":"docker","args":["run","--rm","-i","ghcr.io/upstash/context7:latest"]}}}', 'Context7 MCP Server -- Up-to-date code documentation for LLMs and AI code editors', '开发', 37528);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('semantic-kernel', 'stdio', 'docker', '{"mcpServers":{"semantic-kernel":{"command":"docker","args":["run","--rm","-i","ghcr.io/microsoft/semantic-kernel:latest"]}}}', 'Integrate cutting-edge LLM technology quickly and easily into your apps', '开发', 26701);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('github', 'stdio', 'docker', '{"mcpServers":{"github":{"command":"docker","args":["run","--rm","-i","ghcr.io/github/github-mcp-server"]}}}', 'GitHub MCP Server connects AI tools to GitHub for code management and automation.', '开发', 24597);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('playwright-mcp', 'stdio', 'docker', '{"mcpServers":{"playwright-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/microsoft/playwright-mcp:latest"]}}}', 'Playwright MCP server', '开发', 23432);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('TrendRadar', 'stdio', 'docker', '{"mcpServers":{"TrendRadar":{"command":"docker","args":["run","--rm","-i","ghcr.io/sansan0/trendradar:latest"]}}}', 'TrendRadar: Deploy a news assistant in 30 seconds to filter relevant news.', '社交', 20877);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('fastmcp', 'stdio', 'docker', '{"mcpServers":{"fastmcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/jlowin/fastmcp:latest"]}}}', 'FastMCP is a fast, Pythonic framework for building MCP servers and clients.', '开发', 20431);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('repomix', 'stdio', 'docker', '{"mcpServers":{"repomix":{"command":"docker","args":["run","--rm","-i","ghcr.io/yamadashy/repomix:latest"]}}}', 'Repomix packages your codebase into AI-friendly formats for seamless integration.', '创作', 20256);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('python-sdk', 'stdio', 'docker', '{"mcpServers":{"python-sdk":{"command":"docker","args":["run","--rm","-i","ghcr.io/modelcontextprotocol/python-sdk:latest"]}}}', 'Python SDK for implementing the Model Context Protocol (MCP).', '开发', 20151);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mastra', 'stdio', 'docker', '{"mcpServers":{"mastra":{"command":"docker","args":["run","--rm","-i","ghcr.io/mastra-ai/mastra:latest"]}}}', 'Mastra is a framework for building AI-powered applications and agents.', '开发', 18194);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('serena', 'stdio', 'docker', '{"mcpServers":{"serena":{"command":"docker","args":["run","--rm","-i","ghcr.io/oraios/serena:latest"]}}}', 'Serena is a free, open-source toolkit that enhances LLMs with IDE-like coding tools.', '开发', 16208);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('apisix', 'stdio', 'docker', '{"mcpServers":{"apisix":{"command":"docker","args":["run","--rm","-i","ghcr.io/apache/apisix:latest"]}}}', 'Apache APISIX is an open-source API gateway for managing APIs and microservices.', '开发', 15871);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('opik', 'stdio', 'docker', '{"mcpServers":{"opik":{"command":"docker","args":["run","--rm","-i","ghcr.io/comet-ml/opik:latest"]}}}', 'Debug, evaluate, and monitor your LLM applications, RAG systems, and agentic workflows with comprehensive tracing, automated evaluations, and production-ready dashboards.', '开发', 15838);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('chrome-devtools-mcp', 'stdio', 'docker', '{"mcpServers":{"chrome-devtools-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/chromedevtools/chrome-devtools-mcp:latest"]}}}', 'chrome-devtools-mcp enables AI coding agents to control and inspect Chrome for automation and debugging.', '开发', 14945);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('blender-mcp', 'stdio', 'docker', '{"mcpServers":{"blender-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/ahujasid/blender-mcp:latest"]}}}', 'BlenderMCP integrates Blender with Claude AI for enhanced 3D modeling.', '开发', 14190);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('pydantic-ai', 'stdio', 'docker', '{"mcpServers":{"pydantic-ai":{"command":"docker","args":["run","--rm","-i","ghcr.io/pydantic/pydantic-ai:latest"]}}}', 'Pydantic AI: A GenAI Agent Framework built with Pydantic.', '开发', 13442);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('semgrep', 'stdio', 'docker', '{"mcpServers":{"semgrep":{"command":"docker","args":["run","--rm","-i","ghcr.io/semgrep/semgrep:latest"]}}}', 'Semgrep: Fast code scanning tool for security and quality.', '开发', 13378);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-for-beginners', 'stdio', 'docker', '{"mcpServers":{"mcp-for-beginners":{"command":"docker","args":["run","--rm","-i","ghcr.io/microsoft/mcp-for-beginners:latest"]}}}', 'Open-source curriculum introducing MCP fundamentals with real-world examples.', '开发', 13331);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('Figma-Context-MCP', 'stdio', 'docker', '{"mcpServers":{"Figma-Context-MCP":{"command":"docker","args":["run","--rm","-i","ghcr.io/glips/figma-context-mcp:latest"]}}}', 'Framelink MCP for Figma enables seamless design implementation across frameworks.', '开发', 11857);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('genai-toolbox', 'stdio', 'docker', '{"mcpServers":{"genai-toolbox":{"command":"docker","args":["run","--rm","-i","ghcr.io/googleapis/genai-toolbox:latest"]}}}', 'MCP Toolbox for Databases is an open-source server that simplifies database tool development.', '开发', 11422);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('cua', 'stdio', 'docker', '{"mcpServers":{"cua":{"command":"docker","args":["run","--rm","-i","ghcr.io/trycua/cua:latest"]}}}', 'Cua is a versatile project supporting Python and Swift on macOS.', '开发', 11295);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('fastapi_mcp', 'stdio', 'docker', '{"mcpServers":{"fastapi_mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/tadata-org/fastapi_mcp:latest"]}}}', 'FastAPI-MCP exposes FastAPI endpoints as Model Context Protocol tools with authentication.', '开发', 11088);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('typescript-sdk', 'stdio', 'docker', '{"mcpServers":{"typescript-sdk":{"command":"docker","args":["run","--rm","-i","ghcr.io/modelcontextprotocol/typescript-sdk:latest"]}}}', 'MCP TypeScript SDK for building and running servers with advanced features.', '官方', 10782);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('n8n-mcp', 'stdio', 'docker', '{"mcpServers":{"n8n-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/czlonkowski/n8n-mcp:latest"]}}}', 'n8n-mcp is a Model Context Protocol server for n8n automation.', '开发', 10035);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('claude-flow', 'stdio', 'docker', '{"mcpServers":{"claude-flow":{"command":"docker","args":["run","--rm","-i","ghcr.io/ruvnet/claude-flow:latest"]}}}', 'Agent orchestration platform for Claude with multi-agent swarms and MCP.', '开发', 9956);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('bytebot', 'stdio', 'docker', '{"mcpServers":{"bytebot":{"command":"docker","args":["run","--rm","-i","ghcr.io/bytebot-ai/bytebot:latest"]}}}', 'Bytebot: An open-source AI desktop agent that automates tasks for you.', '生产', 9693);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('zen-mcp-server', 'stdio', 'docker', '{"mcpServers":{"zen-mcp-server":{"command":"docker","args":["run","--rm","-i","ghcr.io/beehiveinnovations/zen-mcp-server:latest"]}}}', 'Zen MCP Server integrates multiple AI CLIs for streamlined workflows.', '开发', 9676);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('gemini-mcp-server', 'stdio', 'docker', '{"mcpServers":{"gemini-mcp-server":{"command":"docker","args":["run","--rm","-i","ghcr.io/beehiveinnovations/gemini-mcp-server:latest"]}}}', 'Gemini MCP Server', '开发', 9668);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('inbox-zero', 'stdio', 'docker', '{"mcpServers":{"inbox-zero":{"command":"docker","args":["run","--rm","-i","ghcr.io/elie222/inbox-zero:latest"]}}}', 'Inbox Zero is an AI email assistant that organizes, pre-drafts replies, and tracks follow-ups.', '生产', 9403);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-chrome', 'stdio', 'docker', '{"mcpServers":{"mcp-chrome":{"command":"docker","args":["run","--rm","-i","ghcr.io/hangwin/mcp-chrome:latest"]}}}', 'MCP Server transforms your Chrome into an AI-powered assistant.', '社交', 9298);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('cognee', 'stdio', 'docker', '{"mcpServers":{"cognee":{"command":"docker","args":["run","--rm","-i","ghcr.io/topoteretes/cognee:latest"]}}}', 'Cognee - An AI memory system for accurate and persistent data retention.', '创作', 8797);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('sqlglot', 'stdio', 'docker', '{"mcpServers":{"sqlglot":{"command":"docker","args":["run","--rm","-i","ghcr.io/tobymao/sqlglot:latest"]}}}', 'SQLGlot is a no-dependency SQL parser and transpiler supporting 31 dialects.', '开发', 8592);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-use', 'stdio', 'docker', '{"mcpServers":{"mcp-use":{"command":"docker","args":["run","--rm","-i","ghcr.io/mcp-use/mcp-use:latest"]}}}', 'mcp-use is a full-stack MCP framework for building servers, clients, and AI agents.', '社交', 8265);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-use', 'stdio', 'docker', '{"mcpServers":{"mcp-use":{"command":"docker","args":["run","--rm","-i","ghcr.io/pietrozullo/mcp-use:latest"]}}}', 'MCP-Use connects LLMs to MCP tools via a unified interface.', '开发', 8262);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('eino', 'stdio', 'docker', '{"mcpServers":{"eino":{"command":"docker","args":["run","--rm","-i","ghcr.io/cloudwego/eino:latest"]}}}', 'Eino is a project for efficient microservices communication.', '开发', 8245);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('convex-backend', 'stdio', 'docker', '{"mcpServers":{"convex-backend":{"command":"docker","args":["run","--rm","-i","ghcr.io/get-convex/convex-backend:latest"]}}}', 'Convex is an open-source reactive database for web app developers.', '开发', 8183);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('tools', 'stdio', 'docker', '{"mcpServers":{"tools":{"command":"docker","args":["run","--rm","-i","ghcr.io/golang/tools:latest"]}}}', 'Go Tools provides static analysis tools and LSP server for Go programs.', '开发', 7825);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('Upsonic', 'stdio', 'docker', '{"mcpServers":{"Upsonic":{"command":"docker","args":["run","--rm","-i","ghcr.io/Upsonic/gpt-computer-assistant:latest"]}}}', 'The most reliable AI agent framework that supports MCP.', '社交', 7682);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('Upsonic', 'stdio', 'docker', '{"mcpServers":{"Upsonic":{"command":"docker","args":["run","--rm","-i","ghcr.io/Upsonic/Upsonic:latest"]}}}', 'Upsonic is an AI agent framework for fintech and banks, tested against attacks.', '社交', 7682);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-go', 'stdio', 'docker', '{"mcpServers":{"mcp-go":{"command":"docker","args":["run","--rm","-i","ghcr.io/mark3labs/mcp-go:latest"]}}}', 'MCP Go is a Go implementation of the Model Context Protocol for LLM integration.', '开发', 7657);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('inspector', 'stdio', 'docker', '{"mcpServers":{"inspector":{"command":"docker","args":["run","--rm","-i","ghcr.io/modelcontextprotocol/inspector:latest"]}}}', 'MCP Inspector is a developer tool for testing and debugging MCP servers via a web UI.', '开发', 7494);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp', 'stdio', 'docker', '{"mcpServers":{"mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/awslabs/mcp:latest"]}}}', 'A suite of specialized MCP servers for optimizing AWS usage.', '官方', 7421);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('xiaohongshu-mcp', 'stdio', 'docker', '{"mcpServers":{"xiaohongshu-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/xpzouying/xiaohongshu-mcp:latest"]}}}', 'MCP for xiaohongshu.com, offering deployment solutions and user-friendly tools.', '社交', 7020);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('git-mcp', 'stdio', 'docker', '{"mcpServers":{"git-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/idosal/git-mcp:latest"]}}}', 'GitMCP is a tool for managing Git repositories with enhanced features.', '开发', 6987);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('higress', 'stdio', 'docker', '{"mcpServers":{"higress":{"command":"docker","args":["run","--rm","-i","ghcr.io/alibaba/higress:latest"]}}}', 'Higress is an AI Native API Gateway designed for efficient API management.', '开发', 6886);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('browser-tools-mcp', 'stdio', 'docker', '{"mcpServers":{"browser-tools-mcp":{"command":"docker","args":["run","--rm","-i","ghcr.io/AgentDeskAI/browser-tools-mcp:latest"]}}}', 'A browser monitoring tool enhancing AI applications via MCP for data analysis.', '开发', 6860);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('GhidraMCP', 'stdio', 'docker', '{"mcpServers":{"GhidraMCP":{"command":"docker","args":["run","--rm","-i","ghcr.io/LaurieWired/GhidraMCP:latest"]}}}', 'GhidraMCP is a Model Context Protocol server for LLMs.', '开发', 6535);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('awesome-llm-apps', 'stdio', 'docker', '{"mcpServers":{"awesome-llm-apps":{"command":"docker","args":["run","--rm","-i","ghcr.io/Arindam200/awesome-llm-apps:latest"]}}}', 'Collection of LLM Applications', '开发', 6440);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('valuecell', 'stdio', 'docker', '{"mcpServers":{"valuecell":{"command":"docker","args":["run","--rm","-i","ghcr.io/ValueCell-ai/valuecell:latest"]}}}', 'Valuecell is a Python-based project licensed under Apache 2.0.', '金融', 6378);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('github', 'http', 'http', '{"mcpServers":{"github":{"type":"http","url":"https://api.githubcopilot.com/mcp/"}}}', 'GitHub MCP Server connects AI tools to GitHub for code management and automation.', '开发', 24597);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('context7', 'http', 'http', '{"mcpServers":{"context7":{"type":"http","url":"https://mcp.context7.com/mcp"}}}', 'Context7 MCP Server -- Up-to-date code documentation for LLMs and AI code editors', '开发', 37528);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('firecrawl', 'http', 'http', '{"mcpServers":{"firecrawl":{"type":"http","url":"http://127.0.0.1:3000/mcp"}}}', 'Official Firecrawl MCP Server - Adds powerful web scraping and search.', '数据', 4945);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('lingo.dev', 'http', 'http', '{"mcpServers":{"lingo.dev":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'AI-powered i18n toolkit for instant localization.', '开发', 4972);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('browser-mcp', 'http', 'http', '{"mcpServers":{"browser-mcp":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Automate your browser with AI, ensuring privacy and performance.', '开发', 4965);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('autobrowser-mcp', 'http', 'http', '{"mcpServers":{"autobrowser-mcp":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Allows AI applications to control your browser.', '开发', 4952);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('DesktopCommanderMCP', 'http', 'http', '{"mcpServers":{"DesktopCommanderMCP":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'AI-powered file management and terminal command execution.', '生产', 4928);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('ClaudeDesktopCommander', 'http', 'http', '{"mcpServers":{"ClaudeDesktopCommander":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'MCP server for Claude that gives it terminal control.', '开发', 4927);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('ClaudeComputerCommander', 'http', 'http', '{"mcpServers":{"ClaudeComputerCommander":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Provides terminal control, file system search, and diff editing.', '生产', 4927);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('deepchat', 'http', 'http', '{"mcpServers":{"deepchat":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Open-source AI chat platform supporting multiple models and advanced features.', '社交', 4922);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('5ire', 'http', 'http', '{"mcpServers":{"5ire":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'AI assistant and MCP client offering free tools and prompts.', '社交', 4778);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('cc-switch', 'http', 'http', '{"mcpServers":{"cc-switch":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Provider switcher for Claude Code & Codex.', '开发', 4697);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('hexstrike-ai', 'http', 'http', '{"mcpServers":{"hexstrike-ai":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'AI-powered MCP cybersecurity automation platform.', '数据', 4579);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('claude-context', 'http', 'http', '{"mcpServers":{"claude-context":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Integrates your codebase as context for Claude.', '开发', 4499);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('CodeIndexer', 'http', 'http', '{"mcpServers":{"CodeIndexer":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Semantic code search in VS Code.', '开发', 4495);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('code-context', 'http', 'http', '{"mcpServers":{"code-context":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Adds semantic search capabilities to Claude Code.', '开发', 4495);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('magic', 'http', 'http', '{"mcpServers":{"magic":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Open-source all-in-one AI productivity platform.', '生产', 4347);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('ida-pro-mcp', 'http', 'http', '{"mcpServers":{"ida-pro-mcp":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Reverse engineering assistant bridging IDA Pro with LLMs via MCP.', '开发', 4306);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('poem', 'http', 'http', '{"mcpServers":{"poem":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Rust framework for building web applications.', '开发', 4265);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('Skill_Seekers', 'http', 'http', '{"mcpServers":{"Skill_Seekers":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Python project for skill assessment, integrated with MCP.', '创作', 4234);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('deep-research', 'http', 'http', '{"mcpServers":{"deep-research":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Deep Research with SSE API and MCP server.', '数据', 4232);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('53AIHub', 'http', 'http', '{"mcpServers":{"53AIHub":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Open-source AI portal for building and operating AI agents.', '开发', 4148);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('adk-go', 'http', 'http', '{"mcpServers":{"adk-go":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Open-source Go toolkit for building and deploying AI agents.', '开发', 4126);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('ENScan_GO', 'http', 'http', '{"mcpServers":{"ENScan_GO":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Information collection tool targeting HW/SRC for enterprises.', '数据', 4061);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('sdk-python', 'http', 'http', '{"mcpServers":{"sdk-python":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Strands Agents: Build AI agents with model-driven approach.', '开发', 4045);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('voltagent', 'http', 'http', '{"mcpServers":{"voltagent":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'TypeScript AI Agent Framework with built-in LLM Observability.', '开发', 3995);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('nexent', 'http', 'http', '{"mcpServers":{"nexent":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Agent SDK and platform for multimodal services built on MCP.', '开发', 3951);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('magic-mcp', 'http', 'http', '{"mcpServers":{"magic-mcp":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Instant UI component creation via natural language.', '开发', 3945);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('unity-mcp', 'http', 'http', '{"mcpServers":{"unity-mcp":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'AI assistant for Unity enhancing development workflows.', '开发', 3909);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcpo', 'http', 'http', '{"mcpServers":{"mcpo":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Simple, secure MCP-to-OpenAPI proxy server.', '开发', 3662);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-atlassian', 'http', 'http', '{"mcpServers":{"mcp-atlassian":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Integrates AI with Atlassian products like Confluence and Jira.', '企业', 3624);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('csharp-sdk', 'http', 'http', '{"mcpServers":{"csharp-sdk":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Official C# SDK for MCP to build .NET applications.', '官方', 3583);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('astron-rpa', 'http', 'http', '{"mcpServers":{"astron-rpa":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Agent-ready RPA suite with out-of-the-box automation tools.', '企业', 3560);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('notion-mcp-server', 'http', 'http', '{"mcpServers":{"notion-mcp-server":{"type":"http","url":"https://mcp.notion.com/mcp"}}}', 'Official Notion MCP Server with OAuth-based remote hosting.', '官方', 3496);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('fast-agent', 'http', 'http', '{"mcpServers":{"fast-agent":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Create and interact with sophisticated agents.', '开发', 3459);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('Windows-MCP', 'http', 'http', '{"mcpServers":{"Windows-MCP":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'MCP Server for Computer Use in Windows.', '官方', 3454);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('Everywhere', 'http', 'http', '{"mcpServers":{"Everywhere":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'AI companion for every moment and place.', '社交', 3430);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('koog', 'http', 'http', '{"mcpServers":{"koog":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Kotlin-based framework for agentic applications.', '开发', 3425);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('refact', 'http', 'http', '{"mcpServers":{"refact":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Open-source AI software development agent.', '开发', 3382);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-feedback-enhanced', 'http', 'http', '{"mcpServers":{"mcp-feedback-enhanced":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Feedback-oriented development MCP server.', '开发', 3365);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mcp-ui', 'http', 'http', '{"mcpServers":{"mcp-ui":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'UI SDK for MCP supporting multiple platforms.', '开发', 3285);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('container-use', 'http', 'http', '{"mcpServers":{"container-use":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Container Sandboxing MCP for Agents.', '开发', 3267);
-- Fillers to reach 50
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('opik-http', 'http', 'http', '{"mcpServers":{"opik":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'LLM tracing and evaluations platform.', '开发', 15838);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('apisix-http', 'http', 'http', '{"mcpServers":{"apisix":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Open-source API gateway.', '开发', 15871);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('playwright-http', 'http', 'http', '{"mcpServers":{"playwright":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Playwright MCP over HTTP.', '开发', 23432);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('fastmcp-http', 'http', 'http', '{"mcpServers":{"fastmcp":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'FastMCP HTTP configuration.', '开发', 20431);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('repomix-http', 'http', 'http', '{"mcpServers":{"repomix":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Repomix HTTP configuration.', '开发', 20256);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('mastra-http', 'http', 'http', '{"mcpServers":{"mastra":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Mastra HTTP configuration.', '开发', 18194);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('serena-http', 'http', 'http', '{"mcpServers":{"serena":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Serena HTTP configuration.', '开发', 16208);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('bytebot-http', 'http', 'http', '{"mcpServers":{"bytebot":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Bytebot HTTP configuration.', '生产', 9693);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('zen-http', 'http', 'http', '{"mcpServers":{"zen-mcp-server":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Zen MCP HTTP configuration.', '开发', 9676);
INSERT INTO `mcp_agents` (`name`, `transport`, `command`, `args`, `description`, `category`, `trust_score`) VALUES
('gemini-http', 'http', 'http', '{"mcpServers":{"gemini-mcp-server":{"type":"http","url":"http://127.0.0.1:3001/mcp"}}}', 'Gemini MCP HTTP configuration.', '开发', 9668);