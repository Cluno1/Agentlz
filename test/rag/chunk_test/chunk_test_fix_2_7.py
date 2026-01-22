import sys
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from agentlz.services.rag.chunk_embeddings_service import chunk_content_by_strategy

NAME_MAP = {
    2: "chunk_fixed_length_boundary",
    7: "chunk_structure_aware",
}


def load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_result(content: str, sid: int, meta: dict) -> dict:
    chunks = chunk_content_by_strategy(content, strategy=sid, meta=meta)
    lens = [len(c) for c in chunks]
    return {
        "strategy_id": sid,
        "strategy_name": NAME_MAP.get(sid, "unknown"),
        "meta": meta,
        "total_chunks": len(chunks),
        "length_stats": {
            "min": (min(lens) if lens else 0),
            "max": (max(lens) if lens else 0),
            "avg": (sum(lens) // len(lens) if lens else 0),
        },
        "chunks": chunks,
    }


def replace_section(md_text: str, sid: int, json_text: str) -> str:
    title = rf"## 策略 {sid}: {re.escape(NAME_MAP.get(sid, 'unknown'))}"
    pattern = rf"({title}\s*\n\n```json\n)([\s\S]*?)(\n```)"
    repl = rf"\1{json_text}\3"
    new_text, n = re.subn(pattern, repl, md_text, flags=re.MULTILINE)
    if n == 0:
        # 若不存在对应标题，则追加到末尾
        append_part = "\n".join([
            f"## 策略 {sid}: {NAME_MAP.get(sid, 'unknown')}",
            "",
            "```json",
            json_text,
            "```",
            "",
        ])
        new_text = md_text.rstrip() + "\n\n" + append_part
    return new_text


def main():
    md_path = ROOT / "test" / "rag" / "chunk_test" / "test1.md"
    out_path = ROOT / "test" / "rag" / "chunk_test" / "test_conclusion.md"
    if not md_path.exists():
        print(f"测试文档不存在: {md_path}")
        return
    content = load_markdown(md_path)
    res2 = build_result(content, 2, {"target_length": 600, "overlap": 80})
    res7 = build_result(content, 7, {"max_size": 800})
    json2 = json.dumps(res2, ensure_ascii=False, indent=2)
    json7 = json.dumps(res7, ensure_ascii=False, indent=2)
    if out_path.exists():
        buf = out_path.read_text(encoding="utf-8")
    else:
        buf = ""
    buf = replace_section(buf, 2, json2)
    buf = replace_section(buf, 7, json7)
    out_path.write_text(buf, encoding="utf-8")
    print(f"已更新: {out_path}")


if __name__ == "__main__":
    main()

