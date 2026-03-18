import argparse
import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, List

import requests

try:
    import psutil
except Exception:
    psutil = None


@dataclass
class RequestResult:
    latency: float
    success: bool
    error: Optional[str]
    tokens_in: int
    tokens_out: int


@dataclass
class StressStats:
    total: int = 0
    success: int = 0
    error: int = 0
    latencies: List[float] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    in_flight: int = 0
    start_time: float = field(default_factory=time.perf_counter)
    last_total: int = 0
    last_time: float = field(default_factory=time.perf_counter)
    # 新增：控制总请求数，避免无限循环
    max_requests: int = 0
    completed_requests: int = 0

    def add(self, result: RequestResult) -> None:
        self.total += 1
        self.completed_requests += 1
        if result.success:
            self.success += 1
        else:
            self.error += 1
        self.latencies.append(result.latency)
        self.tokens_in += result.tokens_in
        self.tokens_out += result.tokens_out

    def snapshot(self) -> Dict[str, float]:
        now = time.perf_counter()
        elapsed = max(now - self.start_time, 1e-6)
        interval = max(now - self.last_time, 1e-6)
        total = self.total
        success = self.success
        error = self.error
        latencies = list(self.latencies)
        in_flight = self.in_flight
        tokens_in = self.tokens_in
        tokens_out = self.tokens_out
        interval_total = total - self.last_total
        qps = interval_total / interval
        self.last_time = now
        self.last_total = total
        p95 = 0.0
        if latencies:
            sorted_lats = sorted(latencies)
            idx = int(len(sorted_lats) * 0.95)
            # 修复p95计算边界问题
            idx = max(0, min(idx - 1, len(sorted_lats) - 1))
            p95 = sorted_lats[idx]
        return {
            "elapsed": float(elapsed),
            "total": float(total),
            "success": float(success),
            "error": float(error),
            "qps": float(qps),
            "p95": float(p95),
            "in_flight": float(in_flight),
            "tokens_in": float(tokens_in),
            "tokens_out": float(tokens_out),
        }


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def login_and_get_token(base_url: str, username: str, password: str) -> str:
    url = base_url.rstrip("/") + "/v1/login"
    resp = requests.post(url, json={"username": username, "password": password}, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError("登录返回数据格式错误")
    if not data.get("success"):
        raise RuntimeError(f"登录失败: {data.get('message')}")
    inner = data.get("data") or {}
    if not isinstance(inner, dict):
        raise RuntimeError("登录返回数据中缺少data字段")
    token = inner.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("登录返回数据中缺少token")
    return token


def build_payload(args: argparse.Namespace) -> Dict[str, object]:
    session_id = uuid.uuid4().hex
    base_message = args.message or ""
    message = f"{base_message} [{session_id[:8]}]"
    payload: Dict[str, object] = {
        "type": 0,
        "meta": {"session_id": session_id},
        "message": message,
    }
    if args.api_name and args.api_key:
        payload["api_name"] = args.api_name
        payload["api_key"] = args.api_key
    elif args.agent_id is not None:
        payload["agent_id"] = args.agent_id
    else:
        raise RuntimeError("必须提供 api_name/api_key 或 agent_id 之一")
    return payload


def send_single_request(
    chat_url: str,
    headers: Dict[str, str],
    args: argparse.Namespace,
    stats: StressStats,
    lock: threading.Lock,
    stop_event: threading.Event,
) -> None:
    # 核心修改1：每个线程只发指定数量的请求，而非无限循环
    while not stop_event.is_set():
        with lock:
            # 达到最大请求数则退出
            if stats.completed_requests >= stats.max_requests:
                break
        payload = build_payload(args)
        message = str(payload.get("message") or "")
        tokens_in = estimate_tokens(message)
        start = time.perf_counter()
        with lock:
            stats.in_flight += 1
        error_text: Optional[str] = None
        success = False
        tokens_out = 0
        try:
            resp = requests.post(
                chat_url,
                json=payload,
                headers=headers,
                stream=True,
                timeout=args.request_timeout,
            )
            if resp.status_code != 200:
                error_text = f"HTTP {resp.status_code}"
            else:
                text_acc = ""
                try:
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if stop_event.is_set():
                            break
                        if not raw_line:
                            continue
                        line = str(raw_line)
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            success = True
                            break
                        try:
                            obj = json.loads(data)
                        except Exception:
                            # 修复：流式响应可能直接返回文本，而非JSON
                            text_acc += data
                            continue
                        # 兼容后端返回的JSON格式
                        if isinstance(obj, dict):
                            content = obj.get("content", "")
                            if isinstance(content, str):
                                text_acc += content
                    if not success and not stop_event.is_set():
                        error_text = "流式响应未正常结束"
                except Exception as e:
                    error_text = f"流式读取异常: {e}"
                tokens_out = estimate_tokens(text_acc)
        except Exception as e:
            error_text = f"请求异常: {e}"
        end = time.perf_counter()
        latency = end - start
        result = RequestResult(
            latency=latency,
            success=success and not error_text,
            error=error_text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        with lock:
            stats.in_flight = max(0, stats.in_flight - 1)
            stats.add(result)


def reporter_loop(stats: StressStats, lock: threading.Lock, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        time.sleep(1.0)
        with lock:
            snap = stats.snapshot()
        elapsed = snap["elapsed"]
        total = int(snap["total"])
        success = int(snap["success"])
        error = int(snap["error"])
        qps = snap["qps"]
        p95_ms = snap["p95"] * 1000.0
        in_flight = int(snap["in_flight"])
        tokens_in = int(snap["tokens_in"])
        tokens_out = int(snap["tokens_out"])
        err_rate = 0.0
        if total > 0:
            err_rate = error * 100.0 / float(total)
        sys_load = ""
        if psutil is not None:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                sys_load = f" | CPU {cpu:5.1f}% MEM {mem:5.1f}%"
            except Exception:
                sys_load = ""
        line = (
            f"[{elapsed:6.1f}s] total={total:6d} succ={success:6d} err={error:6d} "
            f"err%={err_rate:5.1f}% qps={qps:6.1f} p95={p95_ms:7.1f}ms "
            f"queue={in_flight:4d} tokens_in={tokens_in:8d} tokens_out={tokens_out:8d}{sys_load}"
        )
        print(line, flush=True)


def run_stress(args: argparse.Namespace) -> None:
    base_url = args.base_url.rstrip("/")
    chat_url = base_url + "/v1/agent/chat"
    headers: Dict[str, str] = {}
    if args.tenant_id:
        headers[args.tenant_header] = args.tenant_id
    token = args.token or ""
    if args.username and args.password and not token:
        print("开始登录获取token...", flush=True)
        token = login_and_get_token(base_url, args.username, args.password)
        print("登录成功", flush=True)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    stats = StressStats()
    # 核心修改2：设置最大请求数 = 并发数 × 压测时长（避免无限请求）
    stats.max_requests = args.concurrency * int(args.duration)
    lock = threading.Lock()
    stop_event = threading.Event()
    workers: List[threading.Thread] = []
    # 核心修改3：并发数建议从10降到5，先验证效果
    concurrency = min(args.concurrency, 5)
    for i in range(concurrency):
        t = threading.Thread(
            target=send_single_request,
            args=(chat_url, headers, args, stats, lock, stop_event),
            daemon=True,
        )
        workers.append(t)
        t.start()
    reporter = threading.Thread(
        target=reporter_loop,
        args=(stats, lock, stop_event),
        daemon=True,
    )
    reporter.start()
    try:
        # 核心修改4：等待请求完成或超时
        while not stop_event.is_set():
            time.sleep(1)
            with lock:
                if stats.completed_requests >= stats.max_requests:
                    break
                if time.perf_counter() - stats.start_time > args.duration:
                    break
    except KeyboardInterrupt:
        print("用户中断, 准备停止...", flush=True)
    stop_event.set()
    # 等待线程结束（延长超时时间）
    for t in workers:
        t.join(timeout=args.request_timeout + 10.0)
    reporter.join(timeout=5.0)
    with lock:
        final_snap = stats.snapshot()
    total = int(final_snap["total"])
    success = int(final_snap["success"])
    error = int(final_snap["error"])
    p95_ms = final_snap["p95"] * 1000.0
    qps = 0.0
    if final_snap["elapsed"] > 0:
        qps = total / final_snap["elapsed"]
    err_rate = 0.0
    if total > 0:
        err_rate = error * 100.0 / float(total)
    tokens_in = int(final_snap["tokens_in"])
    tokens_out = int(final_snap["tokens_out"])
    summary = (
        f"结束: total={total} succ={success} err={error} "
        f"err%={err_rate:.2f}% avg_qps={qps:.2f} p95={p95_ms:.1f}ms "
        f"tokens_in={tokens_in} tokens_out={tokens_out}"
    )
    print(summary, flush=True)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="agent_chat_stress", description="Agent RAG 聊天链路压测工具")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="后端HTTP基础地址, 不含/v1")
    parser.add_argument("--agent-id", type=int, default=None, help="Agent ID, 使用用户token鉴权时必填")
    parser.add_argument("--api-name", type=str, default=None, help="Agent API 名称, 与api_key配合可免登录")
    parser.add_argument("--api-key", type=str, default=None, help="Agent API 密钥, 与api_name配合可免登录")
    parser.add_argument("--username", type=str, default=None, help="登录用户名")
    parser.add_argument("--password", type=str, default=None, help="登录密码")
    parser.add_argument("--token", type=str, default=None, help="已获取的Bearer Token, 若提供则跳过登录")
    parser.add_argument("--tenant-id", type=str, default=None, help="租户ID, 部分接口需要, 如: default")
    parser.add_argument("--tenant-header", type=str, default="X-Tenant-ID", help="租户ID请求头名称")
    parser.add_argument("--concurrency", type=int, default=5, help="并发线程数量（建议先设为5）")
    parser.add_argument("--duration", type=float, default=60.0, help="压测持续时间, 单位秒")
    parser.add_argument("--request-timeout", type=float, default=30.0, help="单次请求超时时间（从60s降到30s）")
    parser.add_argument("--message", type=str, default="请基于RAG知识库回答一个简单问题用于压测", help="对话消息模板")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = parse_args(argv)
    run_stress(args)


if __name__ == "__main__":
    main()