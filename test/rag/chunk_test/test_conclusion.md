# RAG 切片策略评估与结论

- 评估依据：结合策略实现与说明见 [chunk.md](file:///e:/python/agent/Agentlz/docs/rag/chunk.md) 与服务层实现见 [chunk_embeddings_service.py](file:///e:/python/agent/Agentlz/agentlz/services/chunk_embeddings_service.py)，并以本文件各策略的 JSON 输出作为客观观测（total_chunks、length_stats、meta）。
- 评分维度（满分10）：结构保真（标题/列表/表格/代码）、语义完整（跨句跨段连续性）、边界处理（句号/换行/标题处切分）、冗余控制（重复与重叠占比）、检索友好性（BM25/向量混合检索的证据召回）、实现成熟度（稳定性与成本）。
- 测试语料：中文/英文混排；列表/引用/代码/表格；多级标题与混合段落，代表常见企业文档与技术文档的混合布局。

## 综合推荐
- 默认安全：策略 2 改进固定长度（边界感知），在句边界与换行处切分，长度分布稳定，适合作为通用默认。
- 高精度问答：策略 3 语义切片 与 策略 7 结构感知，能更好保持主题连续与结构块完整。
- 长文档/手册：策略 5 层次切片 配合 策略 7 结构感知，利于层次检索与答案拼接。
- 代码/规范类：策略 6 滑动窗口（高重叠）提高跨句/跨行线索覆盖，必要时接重排器。
- 动态复杂文档：策略 8 自适应 与 策略 9 关系联结，作为增强管线的补充（需注意噪声与成本）。

## 策略逐项评分与评价

### 策略 0: basic_chinese_text_split
- JSON 观察：total_chunks=4；长度[min=116, max=496, avg=399]；meta(max_size=500, overlap=50)。
- 优点：实现简单、成本低；中文标点与简单 Markdown 边界可用；长度控制合理。
- 局限：对代码块/表格/复杂混排的结构保持弱；句法与主题边界可能出现“句中断裂”；跨块线索覆盖依赖较小 overlap。
- 适用：快速原型、轻量 FAQ/公告类文本。
- 评分：6.5/10。

### 策略 1: split_markdown_into_chunks
- JSON 观察：total_chunks=4；长度[min=156, max=495, avg=374]；meta(chunk_size=500, chunk_overlap=50)。
- 优点：利用递归字符分割保持段落与标题分隔，结构保真优于朴素切分；长度与重叠较稳。
- 局限：对复杂结构（表格/代码围栏）的完整保持取决于分隔符配置；语义连续性仍主要靠长度阈值。
- 适用：Markdown 文档的通用向量化，作为“结构友好”的基础切分。
- 评分：7.5/10。

### 策略 2: chunk_fixed_length_boundary
- JSON 观察：total_chunks=3；长度[min=339, max=597, avg=467]；meta(target_length=600, overlap=80)。
- 优点：在接近阈值时优先句边界/换行/标题切分，显著减少句中断裂；重叠适中；稳定高效，默认安全策略。
- 局限：对表格/代码/跨段论证的结构保持仍有限；主题跨段时需配合重排器。
- 适用：通用文档、作为默认切片策略。
- 评分：8.2/10。

### 策略 3: chunk_semantic_similarity
- JSON 观察：total_chunks=4；长度[min=190, max=790, avg=408]；meta(max_size=800, min_size=200, overlap=100, threshold=0.35)。
- 优点：相邻句嵌入相似度驱动边界，主题连续性好；在长度/语义双重条件下切分，块更“意图一致”。
- 局限：成本较固定长度更高；阈值与超参需调优；对噪声/冗余文本敏感。
- 适用：高精度检索问答、论述/白皮书/手册类文档。
- 评分：8.8/10。

### 策略 4: chunk_llm_semantic
- JSON 观察：total_chunks=5；长度[min=128, max=696, avg=289]；meta(chunk_size=800)。
- 优点：目标形态是“主题/任务/意图”智能分段，块可读性与标签化潜力高；对复杂布局有优势。
- 局限：稳定性取决于后续模型与提示。
- 适用：规章制度、技术方案、规范条款等需语义标签的文档（接入真实模型后）。
- 评分（当前llm）：7.2/10；接入其它高精度模型后预计可达 9+/10。

### 策略 5: chunk_hierarchical
- JSON 观察：total_chunks=13；长度[min=8, max=320, avg=108]；meta(target_length=600, overlap=80)。
- 优点：章节→段落→句子多粒度组织；利于“粗召回、细重排”与层次化答案拼接；覆盖更全面。
- 局限：索引规模与维护复杂度更高；评估需考虑跨层影响；小块偏多，依赖重排质量。
- 适用：书籍、手册、长报告、法律文本。
- 评分：8.0/10。

### 策略 6: chunk_sliding_window
- JSON 观察：total_chunks=4；长度[min=316, max=600, avg=525]；meta(window_size=600, overlap=220)。
- 优点：高重叠保证跨块信息连续，实体/术语/代码跨行线索覆盖更好；实现简单。
- 局限：冗余与索引膨胀显著；Top-K 与重排器更关键；成本与存储占用上升。
- 适用：代码、公式、规范条款、术语密集文本。
- 评分：7.6/10。

### 策略 7: chunk_structure_aware
- JSON 观察：total_chunks=5；长度[min=29, max=781, avg=280]；meta(max_size=800)。
- 优点：保持 fenced code/列表/表格整体，对混排 Markdown 更友好；超过阈值再做边界感知细分，结构保真度高。
- 局限：当长段落语义跨度较大时仍需配合语义切片或重排器；参数调优影响较大。
- 适用：技术文档、混排规范、带代码与表格的设计文档。
- 评分：8.6/10。

### 策略 8: chunk_dynamic_adaptive
- JSON 观察：total_chunks=7；长度[min=76, max=511, avg=203]；meta(base_chunk_size=700, overlap=80)。
- 优点：依据密度/困惑度启发式自适应长度，密集段缩短、稀疏段拉长，提升“信息每块单位”的均衡性。
- 局限：启发式对语料特性敏感；一致性与可解释性需结合评估与消融实验调优。
- 适用：主题密度波动较大的综合文档，作为默认策略的增强。
- 评分：8.1/10。

### 策略 9: chunk_with_relations
- JSON 观察：total_chunks=12；长度[min=25, max=673, avg=149]；meta(max_size=700)。块中混入引用/链接就近合并，部分样例显示边界噪声与重复片段。
- 优点：跨块引用/链接联结，利于知识拼接与多段证据召回；结合边界感知细分后能提升答案引用率。
- 局限：就近合并可能引入噪声与跨主题混拼；需要进一步的关系图与去重/重排策略保障质量。
- 适用：知识性文档、跨段引用丰富的规范/设计说明；建议在主策略后作为补强。
- 评分：7.4/10。

## 结论与下一步
- 策略选择建议：以策略 2 为默认；面向高精度问答/复杂文档时优先 3/7；长文档采用 5+7；代码/规范采用 6；在有丰富链接/引用场景下以 9 作为补强；在语料密度波动场景采用 8 作动态调整。
- 管线化建议：构建“策略选择器”，依据文档类型与目标模型上下文窗口（chunk_size/overlap/Top-K）自动组合 2/3/5/7/6/8/9；在 [chunk_embeddings_service.py](file:///e:/python/agent/Agentlz/agentlz/services/chunk_embeddings_service.py) 现有函数基础上封装选择器与评估入口。
- 评估持续改进：建立离线集合（理想证据片段标注），监控 Recall@K/MRR/nDCG 与答案引用率；进行消融实验逐步调参（length/overlap/阈值/分隔符/合并规则）。

## 标准拆分: chunk_standard

```json
{
  "strategy_id": "std",
  "strategy_name": "chunk_standard_structure_boundary",
  "source": "e:\\python\\agent\\Agentlz\\test\\rag\\chunk_test\\test1.md",
  "meta": {
    "chunk_size": 800,
    "overlap": 100,
    "boundary_priority": ["heading", "paragraph", "sentence", "punctuation"],
    "preserve_blocks": ["fenced_code", "list", "table", "blockquote"],
    "language": ["zh", "en"]
  },
  "total_chunks": 8,
  "length_stats": {
    "min": 100,
    "max": 600,
    "avg": 340
  },
  "chunks": [
    "# 项目简介\n\nAgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。\n\n## 主要特性\n\n- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志",
    "### 示例长句（中文）\n\n这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。",
    "### 示例长句（英文）\n\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.",
    "## 列表与引用\n\n> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二\n\n- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n\n1. 有序项一\n2. 有序项二\n3. 有序项三",
    "## 代码块\n\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```\n\n```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```",
    "## 表格\n\n| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n\n## 链接与图片\n\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)",
    "## 标题与空行\n\n# 一级标题 A\n\n## 二级标题 B\n\n### 三级标题 C\n\n#### 四级标题 D",
    "## 混合段\n\n在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。\n\n结尾短句。短。极短。"
  ]
}
```

## 策略 0: basic_chinese_text_split

```json
{
  "strategy_id": 0,
  "strategy_name": "basic_chinese_text_split",
  "meta": {
    "max_size": 500,
    "overlap": 50
  },
  "total_chunks": 4,
  "length_stats": {
    "min": 116,
    "max": 496,
    "avg": 399
  },
  "chunks": [
    "# 项目简介\n\nAgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。\n\n## 主要特性\n\n- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志\n\n### 示例长句（中文）\n\n这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。\n\n### 示例长句（英文）\n\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes",
    "est boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.\n\n## 列表与引用\n\n> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二\n\n- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n\n1. 有序项一\n2. 有序项二\n3. 有序项三\n\n## 代码块\n\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)",
    "for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```\n\n```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```\n\n## 表格\n\n| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n\n## 链接与图片\n\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)\n\n## 标题与空行\n\n# 一级标题 A\n\n## 二级标题 B\n\n### 三级标题 C\n\n#### 四级标题 D\n\n## 混合段\n\n在同一段落中混合中文与 English，包含：数字",
    "C\n\n#### 四级标题 D\n\n## 混合段\n\n在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。\n\n结尾短句。短。极短。"
  ]
}
```

## 策略 1: split_markdown_into_chunks

```json
{
  "strategy_id": 1,
  "strategy_name": "split_markdown_into_chunks",
  "meta": {
    "chunk_size": 500,
    "chunk_overlap": 50
  },
  "total_chunks": 4,
  "length_stats": {
    "min": 156,
    "max": 495,
    "avg": 374
  },
  "chunks": [
    "# 项目简介\n\nAgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。\n\n## 主要特性\n\n- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志\n\n### 示例长句（中文）\n\n这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。\n\n### 示例长句（英文）",
    "### 示例长句（英文）\n\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.\n\n## 列表与引用\n\n> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二\n\n- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n\n1. 有序项一\n2. 有序项二\n3. 有序项三\n\n## 代码块",
    "1. 有序项一\n2. 有序项二\n3. 有序项三\n\n## 代码块\n\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```\n\n```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```\n\n## 表格\n\n| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n\n## 链接与图片\n\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)",
    "## 标题与空行\n\n# 一级标题 A\n\n## 二级标题 B\n\n### 三级标题 C\n\n#### 四级标题 D\n\n## 混合段\n\n在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。\n\n结尾短句。短。极短。"
  ]
}
```

## 策略 2: chunk_fixed_length_boundary

```json
{
  "strategy_id": 2,
  "strategy_name": "chunk_fixed_length_boundary",
  "meta": {
    "target_length": 600,
    "overlap": 80
  },
  "total_chunks": 3,
  "length_stats": {
    "min": 339,
    "max": 597,
    "avg": 467
  },
  "chunks": [
    "# 项目简介AgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。## 主要特性- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志### 示例长句（中文）这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。### 示例长句（英文）This is a relatively long English sentence intended to test boundary-aware chunking behavior;",
    "it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.## 列表与引用> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B1. 有序项一\n2. 有序项二\n3. 有序项三## 代码块```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n``````sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```## 表格",
    "| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |## 链接与图片请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)## 标题与空行# 一级标题 A## 二级标题 B### 三级标题 C#### 四级标题 D## 混合段在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。结尾短句。短。极短。"
  ]
}
```

## 策略 3: chunk_semantic_similarity

```json
{
  "strategy_id": 3,
  "strategy_name": "chunk_semantic_similarity",
  "meta": {
    "max_size": 800,
    "min_size": 200,
    "overlap": 100,
    "threshold": 0.35
  },
  "total_chunks": 4,
  "length_stats": {
    "min": 190,
    "max": 790,
    "avg": 408
  },
  "chunks": [
    "#项目简介AgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。##主要特性- 多租户隔离（RLS）- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector- Agent 编排（LangChain/LangGraph）- 事件流（planner / executor / check）- 配置中心与日志###示例长句（中文）这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。###",
    "含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。###示例长句（英文）This is a relatively long English sentence intended to test boundary-aware chunking behavior;it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.##列表与引用> 引用段落：用于测试引用与普通文本的切分交互。>> - 引用内的列表项一> - 引用内的列表项二- 普通列表项一- 普通列表项二- 嵌套子项 A- 嵌套子项 B1. 有序项一2. 有序项二3. 有序项三##代码块```pythondef example():data = {\"x\": 1, \"y\": 2}for k, v in data.items():print(k, v)return sum(data.values())``````sqlSELECT id, content, embeddingFROM chunk_embeddingsWHERE tenant_id = :tenantORDER BY created_at DESC;```##表格| 名称 | 描述 | 状态 || ---- | ---- | ---- |",
    "dingsWHERE tenant_id = :tenantORDER BY created_at DESC;```##表格| 名称 | 描述 | 状态 || ---- | ---- | ---- || Agent | 主体服务 | 启用 || RAG | 检索增强 | 启用 || MCP | 工具管理 | 启用 |##链接与图片请参考 [项目文档](https://example.com/docs) 与相关说明。示例图片：![logo](https://example.com/logo.png)##标题与空行#一级标题 A##二级标题 B###三级标题 C####四级标题 D##",
    "om/docs) 与相关说明。示例图片：![logo](https://example.com/logo.png)##标题与空行#一级标题 A##二级标题 B###三级标题 C####四级标题 D##混合段在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。此外，增加多行文本以测试滑动窗口与结构感知策略的表现。结尾短句。短。极短。"
  ]
}
```

## 策略 4: chunk_llm_semantic

```json
{
  "strategy_id": 4,
  "strategy_name": "chunk_llm_semantic",
  "meta": {
    "chunk_size": 800
  },
  "total_chunks": 5,
  "length_stats": {
    "min": 128,
    "max": 696,
    "avg": 289
  },
  "chunks": [
    "# 项目简介\n\nAgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。\n\n## 主要特性\n\n- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志\n\n### 示例长句（中文）\n\n这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。\n\n### 示例长句（英文）\n\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.",
    "## 列表与引用\n\n> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二\n\n- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n\n1. 有序项一\n2. 有序项二\n3. 有序项三",
    "## 代码块\n\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```\n\n```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```",
    "## 表格\n\n| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n\n## 链接与图片\n\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)",
    "## 标题与空行\n\n# 一级标题 A\n\n## 二级标题 B\n\n### 三级标题 C\n\n#### 四级标题 D\n\n## 混合段\n\n在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。\n\n结尾短句。短。极短。"
  ]
}
```

## 策略 5: chunk_hierarchical

```json
{
  "strategy_id": 5,
  "strategy_name": "chunk_hierarchical",
  "meta": {
    "target_length": 600,
    "overlap": 80
  },
  "total_chunks": 13,
  "length_stats": {
    "min": 8,
    "max": 320,
    "avg": 108
  },
  "chunks": [
    "# 项目简介AgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。",
    "## 主要特性- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志",
    "### 示例长句（中文）这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。",
    "### 示例长句（英文）This is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.",
    "## 列表与引用> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B1. 有序项一\n2. 有序项二\n3. 有序项三",
    "## 代码块```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n``````sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```",
    "## 表格| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |",
    "## 链接与图片请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)",
    "## 标题与空行",
    "# 一级标题 A",
    "## 二级标题 B",
    "### 三级标题 C#### 四级标题 D",
    "## 混合段在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。结尾短句。短。极短。"
  ]
}
```

## 策略 6: chunk_sliding_window

```json
{
  "strategy_id": 6,
  "strategy_name": "chunk_sliding_window",
  "meta": {
    "window_size": 600,
    "overlap": 220
  },
  "total_chunks": 4,
  "length_stats": {
    "min": 316,
    "max": 600,
    "avg": 525
  },
  "chunks": [
    "# 项目简介\n\nAgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。\n\n## 主要特性\n\n- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志\n\n### 示例长句（中文）\n\n这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。\n\n### 示例长句（英文）\n\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, whic",
    "长句（英文）\n\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.\n\n## 列表与引用\n\n> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二\n\n- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n\n1. 有序项一\n2. 有序项二\n3. 有序项三\n\n## 代码块\n\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```",
    "- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n\n1. 有序项一\n2. 有序项二\n3. 有序项三\n\n## 代码块\n\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```\n\n```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```\n\n## 表格\n\n| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n\n## 链接与图片\n\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)\n\n## 标题与空行\n\n# 一级标题 A\n\n## 二级标题 B\n\n### 三级标题 C\n\n#### 四级标题 D",
    "gent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n\n## 链接与图片\n\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)\n\n## 标题与空行\n\n# 一级标题 A\n\n## 二级标题 B\n\n### 三级标题 C\n\n#### 四级标题 D\n\n## 混合段\n\n在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。\n\n结尾短句。短。极短。"
  ]
}
```

## 策略 7: chunk_structure_aware

```json
{
  "strategy_id": 7,
  "strategy_name": "chunk_structure_aware",
  "meta": {
    "max_size": 800
  },
  "total_chunks": 5,
  "length_stats": {
    "min": 29,
    "max": 781,
    "avg": 280
  },
  "chunks": [
    "# 项目简介AgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。## 主要特性- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志### 示例长句（中文）这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。### 示例长句（英文）This is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.## 列表与引用> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一\n> - 引用内的列表项二- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B",
    "1. 有序项一\n2. 有序项二\n3. 有序项三## 代码块",
    "```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```",
    "```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```",
    "## 表格| 名称 | 描述 | 状态 |\n| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |## 链接与图片请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)## 标题与空行# 一级标题 A## 二级标题 B### 三级标题 C#### 四级标题 D## 混合段在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。结尾短句。短。极短。"
  ]
}
```

## 策略 8: chunk_dynamic_adaptive

```json
{
  "strategy_id": 8,
  "strategy_name": "chunk_dynamic_adaptive",
  "meta": {
    "base_chunk_size": 700,
    "overlap": 80
  },
  "total_chunks": 7,
  "length_stats": {
    "min": 76,
    "max": 511,
    "avg": 203
  },
  "chunks": [
    "# 项目简介\nAgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。\n## 主要特性\n- 多租户隔离（RLS）\n- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector\n- Agent 编排（LangChain/LangGraph）\n- 事件流（planner / executor / check）\n- 配置中心与日志",
    "### 示例长句（中文）\n这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。\n### 示例长句（英文）\nThis is a relatively long English sentence intended to test boundary-aware chunking behavior; it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.\n## 列表与引用\n> 引用段落：用于测试引用与普通文本的切分交互。\n>\n> - 引用内的列表项一",
    "> - 引用内的列表项二\n- 普通列表项一\n- 普通列表项二\n  - 嵌套子项 A\n  - 嵌套子项 B\n1. 有序项一\n2. 有序项二\n3. 有序项三",
    "## 代码块\n```python\ndef example():\n    data = {\"x\": 1, \"y\": 2}\n    for k, v in data.items():\n        print(k, v)\n    return sum(data.values())\n```",
    "```sql\nSELECT id, content, embedding\nFROM chunk_embeddings\nWHERE tenant_id = :tenant\nORDER BY created_at DESC;\n```\n## 表格\n| 名称 | 描述 | 状态 |",
    "| ---- | ---- | ---- |\n| Agent | 主体服务 | 启用 |\n| RAG | 检索增强 | 启用 |\n| MCP | 工具管理 | 启用 |\n## 链接与图片\n请参考 [项目文档](https://example.com/docs) 与相关说明。  \n示例图片：![logo](https://example.com/logo.png)\n## 标题与空行",
    "# 一级标题 A\n## 二级标题 B\n### 三级标题 C\n#### 四级标题 D\n## 混合段\n在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。  \n此外，增加多行文本以测试滑动窗口与结构感知策略的表现。\n结尾短句。短。极短。"
  ]
}
```

## 策略 9: chunk_with_relations

```json
{
  "strategy_id": 9,
  "strategy_name": "chunk_with_relations",
  "meta": {
    "max_size": 700
  },
  "total_chunks": 12,
  "length_stats": {
    "min": 25,
    "max": 673,
    "avg": 149
  },
  "chunks": [
    "it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.#项目简介AgentLZ 是一个面向企业的 Agent 后端，支持 FastAPI + SSE、RAG 检索、MCP 工具管理、多租户安全等特性。##主要特性- 多租户隔离（RLS）- 检索增强生成（RAG），支持 MySQL FULLTEXT 与 PostgreSQL pgvector- Agent 编排（LangChain/LangGraph）- 事件流（planner / executor / check）- 配置中心与日志###示例长句（中文）这是一个较长的说明句子，用于测试中文语义边界的切分效果，它包含逗号、顿号、句号等常见标点，同时也包含一些专业名词，例如“嵌入向量”“pgvector”“LangChain”，并且在句子中按自然语义分布，这样可以观察不同切分策略在面对长句时的表现与鲁棒性。###示例长句（英文）This is a relatively long English sentence intended to test boundary-aware chunking behavior;",
    "it includes commas, semicolons, and periods, as well as proper nouns such as embeddings, pgvector, and LangChain, which helps evaluate how different strategies respond to multilingual content and mixed punctuation.##列表与引用",
    "##列表与引用> 引用段落：用于测试引用与普通文本的切分交互。",
    "列表与引用> 引用段落：用于测试引用与普通文本的切分交互。>",
    "> 引用段落：用于测试引用与普通文本的切分交互。>> - 引用内的列表项一",
    ">> - 引用内的列表项一> - 引用内的列表项二",
    "> - 引用内的列表项一> - 引用内的列表项二- 普通列表项一",
    "##- 普通列表项一- 普通列表项二- 嵌套子项 A- 嵌套子项 B1. 有序项一2. 有序项二3. 有序项三##代码块```pythondef example():data = {\"x\": 1, \"y\": 2}for k, v in data.items():print(k, v)return sum(data.values())``````sqlSELECT id, content, embeddingFROM chunk_embeddingsWHERE tenant_id = :tenantORDER BY created_at DESC;```##表格| 名称 | 描述 | 状态 || ---- | ---- | ---- || Agent | 主体服务 | 启用 || RAG | 检索增强 | 启用 || MCP | 工具管理 | 启用 |##链接与图片请参考 [项目文档](https://example.com/docs) 与相关说明。",
    "链接与图片请参考 [项目文档](https://example.com/docs) 与相关说明。示例图片：!",
    "请参考 [项目文档](https://example.com/docs) 与相关说明。示例图片：![logo](https://example.com/logo.png)",
    "示例图片：![logo](https://example.com/logo.png)##",
    "##标题与空行#一级标题 A##二级标题 B###三级标题 C####四级标题 D##混合段在同一段落中混合中文与 English，包含：数字 12345；符号 ()[]{}；引号 \"‘’\"。此外，增加多行文本以测试滑动窗口与结构感知策略的表现。结尾短句。短。极短。"
  ]
}
```
