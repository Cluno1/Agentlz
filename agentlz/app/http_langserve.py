from fastapi import FastAPI
from langserve import add_routes
from langchain_core.runnables import RunnableLambda

from agentlz.agents.markdown_agent import build_markdown_agent
from agentlz.agents.weather_agent import build_weather_agent
from agentlz.agents.multi_agent import ask as multi_ask
from agentlz.agents.mail_agent import send as mail_send

app = FastAPI(title="Agentlz via LangServe")

# 直接挂载 runnable Agent（create_agent 返回的通常是 Runnable）
add_routes(app, build_markdown_agent(), path="/agents/markdown")
add_routes(app, build_weather_agent(), path="/agents/weather")

# 对返回字符串的函数用 RunnableLambda 包一层
add_routes(app, RunnableLambda(lambda x: multi_ask(x.get("input", x))), path="/agents/multi")

# 邮件发送可同时提供两种接口：
# 1) 直接工具式（输入是 {\"content\": ..., \"to_email\": ...}）
add_routes(app, RunnableLambda(lambda x: mail_send(x["content"], x["to_email"])), path="/tools/mail/send")