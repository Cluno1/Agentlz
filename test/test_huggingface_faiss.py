
"""
python -m test.test_huggingface_faiss

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
import os
import pytest


def test_huggingface_datasets_faiss_build_and_load():
    """使用 hongyin/instruct-tuning-sample 构建 FAISS 索引的集成测试（限量）。

    - 若外部依赖缺失（datasets/embedding 模型），测试将被跳过。
    - 写入少量样本以控制耗时（max_docs=5）。
    """
    try:
        from datasets import load_dataset  # noqa: F401
    except Exception:
        pytest.skip("缺少 datasets 依赖，跳过集成测试")

    try:
        from agentlz.memory.huggingface_datasets_to_faiss import persist_huggingface_datasets_to_faiss
        from agentlz.core.embedding_model_factory import get_hf_embeddings
        from agentlz.config.settings import get_settings
    except Exception as e:
        pytest.skip(f"环境不完整，跳过测试: {e}")

    settings = get_settings()
    try:
        embeddings = get_hf_embeddings(model_name=settings.hf_embedding_model)
    except Exception:
        pytest.skip("嵌入模型不可用或缺失，跳过集成测试")
    # 配置测试参数
    persist_dir = ".storage/faiss/test_agent_1"
    index_name = "instruct-tuning-sample"
    dataset_name = "hongyin/instruct-tuning-sample"
    max_docs = 10

    try:
        persist_huggingface_datasets_to_faiss(persist_dir=persist_dir, dataset_name=dataset_name, index_name=index_name, max_docs=max_docs)
    except Exception as e:
        pytest.skip(f"构建过程依赖外部网络或模型失败，跳过：{e}")

    # 校验索引文件存在
    index_file = os.path.join(persist_dir, f"{index_name}.faiss")
    assert os.path.exists(index_file), "FAISS 索引文件未生成"

    # 能够加载索引
    try:
        try:
            from langchain_community.vectorstores import FAISS
        except Exception:
            from langchain.vectorstores import FAISS  # type: ignore
        vs = FAISS.load_local(persist_dir, embeddings=embeddings, index_name=index_name, allow_dangerous_deserialization=True)
        # 验证至少有一条 doc
        doc_count = 0
        try:
            doc_count = len(getattr(vs.docstore, "_dict", {}))
        except Exception:
            pass
        assert doc_count > 0, "FAISS 索引中无文档"
    except Exception as e:
        pytest.fail(f"FAISS 索引加载失败: {e}")

if __name__ == "__main__":
    test_huggingface_datasets_faiss_build_and_load()