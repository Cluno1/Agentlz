import json

from agentlz.prompts.rag.rag import RAG_QUERY_SYSTEM_PROMPT


def test_rag_query_prompt_mentions_messages_object():
    assert '"messages"' in RAG_QUERY_SYSTEM_PROMPT
    assert "严格返回 JSON 对象" in RAG_QUERY_SYSTEM_PROMPT


def test_rag_query_prompt_example_json_is_valid():
    start = RAG_QUERY_SYSTEM_PROMPT.find("{\n  \"messages\": [")
    end = RAG_QUERY_SYSTEM_PROMPT.find("\n  ]\n}", start)
    assert start != -1 and end != -1
    sample = RAG_QUERY_SYSTEM_PROMPT[start : end + len("\n  ]\n}")]
    json.loads(sample)
