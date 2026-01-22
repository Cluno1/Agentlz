import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from agentlz.services.rag.chunk_embeddings_service import chunk_content_by_strategy


def load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def print_header(title: str):
    print("=" * 80)
    print(title)
    print("=" * 80)


NAME_MAP = {
        0: "basic_chinese_text_split",
        1: "split_markdown_into_chunks",
        2: "chunk_fixed_length_boundary",
        3: "chunk_semantic_similarity",
        4: "chunk_llm_semantic",
        5: "chunk_hierarchical",
        6: "chunk_sliding_window",
        7: "chunk_structure_aware",
        8: "chunk_dynamic_adaptive",
        9: "chunk_with_relations",
    }


def run_one_strategy(content: str, strategy: int, meta: dict):
    title = f"策略 {strategy}: {NAME_MAP.get(strategy, 'unknown')} | meta={meta}"
    print_header(title)
    chunks = chunk_content_by_strategy(content, strategy=strategy, meta=meta)
    print(f"总块数: {len(chunks)}")
    lens = [len(x) for x in chunks]
    if lens:
        print(f"长度统计 | min={min(lens)} max={max(lens)} avg={sum(lens)//len(lens)}")
    for i, c in enumerate(chunks[:10], start=1):
        short = (c[:240] + "…") if len(c) > 240 else c
        print(f"[{i}] len={len(c)}\n{short}\n")
    return {
        "strategy_id": strategy,
        "strategy_name": NAME_MAP.get(strategy, "unknown"),
        "meta": meta,
        "total_chunks": len(chunks),
        "length_stats": {
            "min": (min(lens) if lens else 0),
            "max": (max(lens) if lens else 0),
            "avg": (sum(lens) // len(lens) if lens else 0),
        },
        "chunks": chunks,
    }


def write_conclusion(out_path: Path, results: list[dict]):
    parts = []
    for r in results:
        title = f"## 策略 {r.get('strategy_id')}: {r.get('strategy_name')}"
        data = {
            "strategy_id": r.get("strategy_id"),
            "strategy_name": r.get("strategy_name"),
            "meta": r.get("meta"),
            "total_chunks": r.get("total_chunks"),
            "length_stats": r.get("length_stats"),
            "chunks": r.get("chunks"),
        }
        parts.append(title)
        parts.append("")
        parts.append("```json")
        parts.append(json.dumps(data, ensure_ascii=False, indent=2))
        parts.append("```")
        parts.append("")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def main():
    md_path = ROOT / "test" / "rag" / "chunk_test" / "test1.md"
    if not md_path.exists():
        print(f"测试文档不存在: {md_path}")
        return
    content = load_markdown(md_path)
    strategies = [
        (0, {"max_size": 500, "overlap": 50}),
        (1, {"chunk_size": 500, "chunk_overlap": 50}),
        (2, {"target_length": 600, "overlap": 80}),
        (3, {"max_size": 800, "min_size": 200, "overlap": 100, "threshold": 0.35}),
        (4, {"chunk_size": 800}),
        (5, {"target_length": 600, "overlap": 80}),
        (6, {"window_size": 600, "overlap": 220}),
        (7, {"max_size": 800}),
        (8, {"base_chunk_size": 700, "overlap": 80}),
        (9, {"max_size": 700}),
    ]
    results = []
    for sid, meta in strategies:
        try:
            r = run_one_strategy(content, sid, meta)
            results.append(r)
        except Exception as e:
            print(f"策略 {sid} 运行失败: {e}")
    out_path = ROOT / "test" / "rag" / "chunk_test" / "test_conclusion.md"
    try:
        write_conclusion(out_path, results)
        print(f"已生成结论文件: {out_path}")
    except Exception as e:
        print(f"写入结论文件失败: {e}")


if __name__ == "__main__":
    main()

