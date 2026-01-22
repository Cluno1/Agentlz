# 项目简介

AgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。

## 主要特性

- 多租户隔离（RLS）
- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector
- Agent 编排（LangChain/LangGraph）
- 事件流（planner / executor / check）
- 配置中心与日志

### 示例长句（中文）

这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。

### 示例长句（英文）

This is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.

## 列表与引用

> 引用段落：用于测试引用与普通文本的切分交互。
>
> - 引用内的列表项一
> - 引用内的列表项二

- 普通列表项一
- 普通列表项二
  - 嵌套子项 A
  - 嵌套子项 B

1. 有序项一
2. 有序项二
3. 有序项三

## 代码块

```python
def example():
    data = {"x": 1, "y": 2}
    for k, v in data.items():
        print(k, v)
    return sum(data.values())
```

```sql
SELECT id, content, embedding
FROM chunk_embeddings
WHERE tenant_id = :tenant
ORDER BY created_at DESC;
```

## 表格

| 名称 | 描述 | 状态 |
| ---- | ---- | ---- |
| Agent | 主体服务 | 启用 |
| RAG | 检索增强 | 启用 |
| MCP | 工具管理 | 启用 |

## 链接与图片

请参考 [项目文档](https://example.com/docs) 与相关说明。  
示例图片：![logo](https://example.com/logo.png)

## 标题与空行

# 一级标题 A

## 二级标题 B

### 三级标题 C

#### 四级标题 D

## 混合段

在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 "‘’"。  
此外，增加多行文本以测试滑动窗口与结构感知策略的表现。

结尾短句。短。极短。

