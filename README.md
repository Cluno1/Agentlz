# Agentlz

- a multi agent creation system

## 环境搭建

```bash
 创建环境：python -m venv .venv

 激活环境（Linux/Mac）：source .venv/bin/activate
 激活环境（Windows）：.\.venv\Scripts\activate

 安装依赖：pip install -r requirements.txt

 设置.env 环境变量

 启动:  uvicorn agentlz.app.http_langserve:app --port 8000
```

```bash
固定版本 pip freeze > requirements.txt
```

## 简单 Agent Demo（企业级文件架构）

项目结构：

```md

agentlz/
  app/cli.py            # CLI 入口
  agents/simple_agent.py # Agent 构建与调用
  tools/weather.py       # 示例工具（天气）
  core/logger.py         # 日志封装
  core/model_factory.py  # 模型工厂
  config/settings.py     # 配置（.env 支持）
tests/
  test_settings.py
  test_tools.py
.env.example             # 环境变量示例
```

使用步骤：

1. 复制环境变量模板并填写 `OPENAI_API_KEY`

```bash
cp .env.example .env
# 或手动创建 .env 并设置 OPENAI_API_KEY
```

2.运行 CLI 示例

```bash
python -m agentlz.app.cli query "bing: 中国 AI 新闻"
```

说明：

- 该 Demo 使用 LangChain(1.0.2) 最新 API 形式创建 Agent，并通过 `@tool` 暴露基础工具。
- 配置集中管理，便于在企业环境中扩展模型、日志、鉴权等。

## 开发规范

### 规范文档路径:
- [开发规范](/docs/dev.md)

## MCP 邮件工具（供本地 Agent 调用）

该模块将 `agentlz/agents/mail_agent.py` 注册为 MCP 工具，名称为 `mail.send`，可被支持 MCP 的宿主或其他本地 Agent 调用。

### 安装依赖

```bash
pip install -r requirements.txt
# 确认 .env 中已配置：EMAIL_ADDRESS、EMAIL_PASSWORD、SMTP_HOST/PORT、IMAP_HOST
# 模型相关（任选其一）：
# - CHATOPENAI_API_KEY + CHATOPENAI_BASE_URL（自定义模型服务）
# - OPENAI_API_KEY（OpenAI 官方）
```

### 启动 MCP 服务端（STDIO）

```bash
python -m agentlz.app.mcp_mail_server
```

注意：STDIO 传输下不要在服务端使用 `print`，日志请用 `logging`（已内置）。

### 工具说明

- 工具名：`mail.send`
- 入参：
  - `content: str` 邮件内容或提示；若包含 `direct` 指令，则直接原文发送
  - `to_email: str` 收件人邮箱
- 返回：`'ok'` 或 `"error: ..."`

### 在支持 MCP 的客户端中调用示例（Python）

```python
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    exit_stack = AsyncExitStack()
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "agentlz.app.mcp_mail_server"],
        env=None,
    )
    stdio = await exit_stack.enter_async_context(stdio_client(server_params))
    stdio_in, stdio_write = stdio
    session = await exit_stack.enter_async_context(ClientSession(stdio_in, stdio_write))
    await session.initialize()

    # 调用工具
    result = await session.call_tool("mail.send", {"content": "你好，这是一封测试邮件", "to_email": "someone@example.com"})
    print(result.content)  # ['ok'] 或 ['error: ...']

    await exit_stack.aclose()

asyncio.run(main())
```

### 在 Claude Desktop 中安装（可选）

- 参考 MCP 官方文档，将此服务器脚本通过 MCP 管理器安装，选择 STDIO 方式启动。

## MarkItDown 转换 Agent

该 Agent 接收任意输入（文本、文件路径、URL），并通过 MarkItDown 转换为 Markdown：

- 文件到 Markdown：PDF、Images、Audio（转录）、DOCX、XLSX、PPTX
- 网页到 Markdown：普通网页、YouTube 视频字幕、搜索结果（Bing 或 DuckDuckGo）
- 当输入为 `http/https` 链接时，会自动联网抓取并转换

### 安装依赖

```bash
pip install -r requirements.txt
# 可选：设置 Bing API，用于更好的搜索结果
echo "BING_API_KEY=your_key" >> .env
```

### 使用示例

```bash
# 1) 本地文件转换
python -m agentlz.app.cli query "/path/to/doc.pdf"
python -m agentlz.app.cli query "/path/to/report.docx"
python -m agentlz.app.cli query "/path/to/slides.pptx"
python -m agentlz.app.cli query "/path/to/sheet.xlsx"
python -m agentlz.app.cli query "/path/to/audio.mp3"   # 自动转录为 Markdown
python -m agentlz.app.cli query "/path/to/image.png"

# 2) 网页/视频转换（自动抓取）
python -m agentlz.app.cli query "https://example.com/article"
python -m agentlz.app.cli query "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # 需要安装 youtube-transcription 扩展（已在 requirements）

# 3) 搜索结果转 Markdown
python -m agentlz.app.cli query "bing: 中国 AI 新闻"
python -m agentlz.app.cli query "AI agent 最佳实践"   # 无前缀时将尝试 Bing，失败回退到 DuckDuckGo
```

### 设计说明

- 工具：`agentlz/tools/markdown.py` 暴露 `convert_to_markdown(input_value: str)`
  - URL：交给 MarkItDown 直接抓取与转换
  - 文件：交给 MarkItDown 识别并转换（音频自动转录）
  - 查询：优先使用 Bing API（`BING_API_KEY`），未配置则回退至 DuckDuckGo
- Agent：`agentlz/agents/markdown_agent.py` 将用户输入交给工具处理，只输出 Markdown
- CLI：`agentlz/app/cli.py` 绑定到 `query` 命令，直接打印 Markdown 输出
