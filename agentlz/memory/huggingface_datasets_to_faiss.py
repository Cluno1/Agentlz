import json
from hashlib import sha256
from typing import Any, Dict, List

from agentlz.config.settings import get_settings
from agentlz.core.logger import setup_logging
from agentlz.core.embedding_model_factory import get_hf_embeddings
from agentlz.services.faiss_service import FAISSVectorService

settings = get_settings()

def _concat_dialog(sample: Dict[str, Any]) -> str:
    """
    将样本中的多轮对话拼接为纯文本。

    针对常见字段结构进行鲁棒处理：
    - conversations/messages/history/dialogue/dialog/utterances
    - 若为 dict，尝试使用 role/speaker/from 与 content/text/utterance/value
    - 若不存在上述结构，则回退拼接 instruction/input/output/response 等字段
    """
    seq_keys = [
        "conversations",
        "messages",
        "history",
        "dialogue",
        "dialog",
        "utterances",
        "human",
    ]
    for k in seq_keys:
        if k in sample and isinstance(sample[k], list):
            lines: List[str] = []
            for turn in sample[k]:
                if isinstance(turn, str):
                    lines.append(turn.strip())
                elif isinstance(turn, dict):
                    role = turn.get("role") or turn.get("speaker") or turn.get("from") or turn.get("author")
                    content = turn.get("content") or turn.get("text") or turn.get("utterance") or turn.get("value")
                    if role and content:
                        lines.append(f"{role}: {str(content).strip()}")
                    elif content:
                        lines.append(str(content).strip())
                    else:
                        lines.append(json.dumps(turn, ensure_ascii=False))
                else:
                    lines.append(str(turn))
            return "\n".join(lines)

    # 回退：拼接可能出现的单字段
    fallback_keys = [
        "instruction",
        "input",
        "question",
        "prompt",
        "output",
        "response",
        "assistant",
        "answer",
        "text",
    ]
    parts: List[str] = []
    for k in fallback_keys:
        v = sample.get(k)
        if isinstance(v, str) and v.strip():
            parts.append(f"{k}: {v.strip()}")
    if parts:
        return "\n".join(parts)

    # 最终兜底：序列化为 JSON 文本
    return json.dumps(sample, ensure_ascii=False)


def persist_huggingface_datasets_to_faiss(
    persist_dir: str,
    dataset_name: str,
    split: str = "train",
    index_name: str = "huggingface_train",
    max_docs: int | None = None,
) -> None:
    """
    将 HuggingFace 数据集 的多轮对话拼接为文本，
    使用本地 HuggingFace 中文句向量模型进行向量化，并持久化到指定目录的 FAISS 向量库。

    要点：
    - 流式迭代样本，批量入库，避免一次性加载至内存（内存安全）。
    - 不写入任何原始样本数据到磁盘，仅持久化向量与元数据（不落盘原始数据）。
    - 通过确定性 ID 跳过已存在记录，保证可重复执行（幂等）。

    参数:
        persist_dir: FAISS 索引持久化目录路径。
        dataset_name: HuggingFace 数据集名称。
        split: 数据集 split，默认 "train"。
        index_name: FAISS 索引名称，默认 "huggingface_train"。
        max_docs: 仅用于测试/调试时限制最大写入文档数（None 表示不限制）。

    返回:
        None
    """
    logger = setup_logging(settings.log_level)

    try:
        from datasets import load_dataset  # 使用 HuggingFace datasets 库
    except Exception as e:
        raise RuntimeError(
            "缺少 datasets 依赖，请先安装: pip install datasets"
        ) from e

    # 1) Embeddings（允许通过环境变量 HF_EMBEDDING_MODEL 指定本地/自定义模型路径）
    embeddings = get_hf_embeddings(
        model_name=settings.hf_embedding_model,
    )

    # 2) 初始化 FAISS 服务（统一 CRUD 封装）
    svc = FAISSVectorService(persist_dir=persist_dir, index_name=index_name)
    vectorstore = svc.load_or_create(embeddings)

    # 3) 流式加载 HuggingFace 数据集
    ds = load_dataset(dataset_name, split=split, streaming=True)

    batch_size = 64
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []
    total = 0
    skipped = 0
    processed = 0

    for sample in ds:  # datasets 是可迭代对象
        text = _concat_dialog(sample)

        # 生成确定性 ID（优先使用样本自带 id/uid/sid，否则使用内容哈希）
        raw_id = sample.get("id") or sample.get("uid") or sample.get("sid")
        if raw_id is None:
            h = sha256(text.encode("utf-8")).hexdigest()[:32]
            doc_id = f"psydt-train-{h}"
        else:
            doc_id = f"psydt-train-{raw_id}"

        # 重复检测（若集合已存在该 ID，则跳过）
        try:
            existing = getattr(vectorstore, "_collection", None)
            if existing is not None:
                got = existing.get(ids=[doc_id])
                if got and got.get("ids"):
                    skipped += 1
                    continue
        except Exception:
            # 容忍私有属性或驱动实现差异
            pass

        meta = {
            "dataset": dataset_name,
            "split": split,
            "source": "HuggingFace",
        }

        texts.append(text)
        metadatas.append(meta)
        ids.append(doc_id)

        if len(texts) >= batch_size:
            # 批量写入与保存
            vectorstore = svc.add_texts(vectorstore, texts=texts, metadatas=metadatas, ids=ids, embeddings=embeddings)
            svc.save(vectorstore)
            total += len(texts)
            processed += len(texts)
            texts.clear()
            metadatas.clear()
            ids.clear()
            # 测试场景限制条数
            if max_docs is not None and processed >= max_docs:
                break

    # 收尾批次
    if texts:
        vectorstore = svc.add_texts(vectorstore, texts=texts, metadatas=metadatas, ids=ids, embeddings=embeddings)
        svc.save(vectorstore)
        total += len(texts)

    logger.info(
        f"PsyDTCorpus({split}) 已写入向量: {total} 条，重复跳过: {skipped} 条，索引保存到: {persist_dir}/{index_name}.faiss"
    )
