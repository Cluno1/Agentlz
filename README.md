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
