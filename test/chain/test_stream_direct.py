import asyncio
import json
import os
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from agentlz.services.chain.chain_service import stream_chain_generator


def _pretty_print(evt: str, env: dict, raw: bool = False) -> None:
    if raw:
        print(json.dumps({"event": evt, "envelope": env}, ensure_ascii=False), flush=True)
        return
    payload = env.get("payload")
    seq = env.get("seq")
    ts = env.get("ts")
    if evt == "chain.step":
        print(json.dumps({"seq": seq, "ts": ts, "event": evt, "step": payload}, ensure_ascii=False), flush=True)
    elif evt == "planner.plan":
        try:
            ec = payload.get("execution_chain") or []
            mc = payload.get("mcp_config") or []
            print(json.dumps({"seq": seq, "ts": ts, "event": evt, "execution_chain": ec, "mcp_count": len(mc)}, ensure_ascii=False), flush=True)
        except Exception:
            print(json.dumps({"seq": seq, "ts": ts, "event": evt, "payload": payload}, ensure_ascii=False), flush=True)
    elif evt == "call.start":
        print(json.dumps({"seq": seq, "ts": ts, "event": evt, "name": payload.get("name"), "input": payload.get("input")}, ensure_ascii=False), flush=True)
    elif evt == "call.end":
        print(json.dumps({"seq": seq, "ts": ts, "event": evt, "name": payload.get("name"), "status": payload.get("status"), "output": payload.get("output")}, ensure_ascii=False), flush=True)
    elif evt == "check.summary":
        judge = None
        score = None
        try:
            judge = payload.get("judge")
            score = payload.get("score")
        except Exception:
            pass
        print(json.dumps({"seq": seq, "ts": ts, "event": evt, "judge": judge, "score": score}, ensure_ascii=False), flush=True)
    elif evt == "final":
        text = str(payload or "")
        short = (text[:160] + "…") if len(text) > 160 else text
        print(json.dumps({"seq": seq, "ts": ts, "event": evt, "text": short}, ensure_ascii=False), flush=True)
    else:
        print(json.dumps({"seq": seq, "ts": ts, "event": evt, "payload": payload}, ensure_ascii=False), flush=True)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="请根据原始数字进行两次平方和一次与原始数字的相加，运用双关语言输出一段有趣的话，并且根据结果搜索代码来实现一个小程序，初始输入：3")
    parser.add_argument("--tenant", default="default")
    parser.add_argument("--sub", default="1")
    parser.add_argument("--raw", action="store_true")
    args = parser.parse_args()

    gen = stream_chain_generator(user_input=args.prompt, tenant_id=args.tenant, claims={"sub": args.sub})
    async for frame in gen:
        lines = frame.strip().splitlines()
        data_line = next((l for l in lines if l.startswith("data: ")), None)
        evt_line = next((l for l in lines if l.startswith("event: ")), None)
        env = json.loads(data_line[6:]) if data_line else {}
        evt = evt_line[7:] if evt_line else ""
        _pretty_print(evt, env, raw=args.raw)


if __name__ == "__main__":
    asyncio.run(main())
