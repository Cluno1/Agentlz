from fastapi import FastAPI
from langserve import add_routes
from langchain_core.runnables import RunnableLambda

from agentlz.agents.mail_agent import send as mail_send
from agentlz.agents.schedule.schedule_1_agent import query as schedule_query

app = FastAPI(title="Agentlz via LangServe")


# 对返回字符串的函数用 RunnableLambda 包一层
add_routes(app, RunnableLambda(lambda x: schedule_query(x["input"] if isinstance(x, dict) else x)), path="/agents/schedule_1")

# 邮件发送可同时提供两种接口：
# 1) 直接工具式（输入是 {\"content\": ..., \"to_email\": ...}）
add_routes(app, RunnableLambda(lambda x: mail_send(x["content"], x["to_email"])), path="/tools/mail/send")