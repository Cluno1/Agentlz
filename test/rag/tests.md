# RAG 测试说明

**目录**：`test/rag`

**目标**
- 测试使用 HuggingFace 数据集构建和加载 FAISS 索引的功能。
- 验证集成流程是否正常，包括依赖检查、索引构建和加载。

**运行命令**
- 在项目根目录：
  - `python -m test.rag.test_huggingface_faiss`

**输出**
- 测试日志：
  - 包括模型加载、索引构建和加载的详细信息。

**示例日志**

"""
示例日志：

(TraeAI-5) ~/code/pythoncode/Agentlz [1] $ python -m test.test_huggingface_faiss
/Users/zhangliandeng/code/pythoncode/Agentlz/.venv/lib/python3.14/site-packages/langchain_core/_api/deprecation.py:26: UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.
  from pydantic.v1.fields import FieldInfo as FieldInfoV1
2025-11-11 15:29:57,097 INFO agentlz: 加载 Embeddings 模型: BAAI/bge-small-zh-v1.5 (device=cpu)
/Users/zhangliandeng/code/pythoncode/Agentlz/agentlz/core/embedding_model_factory.py:56: LangChainDeprecationWarning: The class `HuggingFaceEmbeddings` was deprecated in LangChain 0.2.2 and will be removed in 1.0. An updated version of the class exists in the `langchain-huggingface package and should be used instead. To use it run `pip install -U `langchain-huggingface` and import as `from `langchain_huggingface import HuggingFaceEmbeddings``.
  return HuggingFaceEmbeddings(
2025-11-11 15:29:59,042 INFO sentence_transformers.SentenceTransformer: Load pretrained SentenceTransformer: BAAI/bge-small-zh-v1.5
2025-11-11 15:30:02,373 INFO agentlz: 加载 Embeddings 模型: BAAI/bge-small-zh-v1.5 (device=cpu)
2025-11-11 15:30:02,374 INFO sentence_transformers.SentenceTransformer: Load pretrained SentenceTransformer: BAAI/bge-small-zh-v1.5
2025-11-11 15:30:09,808 INFO faiss.loader: Loading faiss.
2025-11-11 15:30:09,862 INFO faiss.loader: Successfully loaded faiss.
2025-11-11 15:30:09,870 INFO agentlz: PsyDTCorpus(train) 已写入向量: 64 条，重复跳过: 0 条，索引保存到: .storage/faiss/test_agent_1/instruct-tuning-sample.faiss
"""

**常见问题**
- 缺少依赖：确保安装了 `datasets` 和 `faiss`。
- 索引文件未生成：检查数据集和模型是否可用。

**关联文件**
- FAISS 构建工具：`agentlz/memory/huggingface_datasets_to_faiss.py`
- 嵌入模型工厂：`agentlz/core/embedding_model_factory.py`