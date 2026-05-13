"""
Agent Workbench HTTP API 集成测试。

前置：后端已启动（默认 http://127.0.0.1:8765），且已配置 OPENAI_API_KEY
（聊天类测试需可访问模型服务）。

运行：
  py -3 test_workbench_api.py
  py -3 test_workbench_api.py --base-url http://127.0.0.1:9999
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


def _json_request(method: str, url: str, body: dict | None = None, timeout: float = 30.0) -> tuple[int, Any]:
    data = None
    headers = {}
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        data = raw
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {"_raw": raw}
        return e.code, payload


def _get(url: str, timeout: float = 30.0) -> tuple[int, Any]:
    return _json_request("GET", url, None, timeout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8765", help="CursorAgent 根地址")
    parser.add_argument("--skip-llm", action="store_true", help="跳过需调用模型的聊天测试")
    parser.add_argument("--chat-timeout", type=float, default=120.0, help="聊天请求超时（秒）")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    results: list[tuple[str, str, str]] = []  # name, outcome pass|fail|skip, detail

    def ok(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, "pass" if cond else "fail", detail))

    def skip(name: str, detail: str = "") -> None:
        results.append((name, "skip", detail))

    # 0) 连通性
    try:
        code, data = _get(f"{base}/api/health")
        ok("GET /api/health", code == 200 and data.get("ok") is True, f"code={code}")
    except OSError as e:
        print(f"无法连接 {base}: {e}\n请先启动: py -3 CursorAgent.py", file=sys.stderr)
        return 1

    # 1) 根路径与 health 等价信息
    for path in ("/", "/api"):
        code, data = _get(f"{base}{path}")
        ok(f"GET {path}", code == 200 and data.get("service") == "CursorAgent API", f"code={code}")

    # 2) OPTIONS CORS
    req = urllib.request.Request(f"{base}/api/chat", method="OPTIONS")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.status
            cors = resp.headers.get("Access-Control-Allow-Origin")
        ok("OPTIONS /api/chat", code in (200, 204) and cors is not None, f"code={code} ACAO={cors}")
    except urllib.error.HTTPError as e:
        ok("OPTIONS /api/chat", e.code in (200, 204), f"code={e.code}")

    # 3) status & session
    code, data = _get(f"{base}/api/status?lang=zh")
    sess_list = data.get("sessions") if isinstance(data, dict) else None
    ok("GET /api/status", code == 200 and isinstance(sess_list, list), f"code={code}")
    active = data.get("activeSessionId") if isinstance(data, dict) else None

    if not active and isinstance(sess_list, list) and sess_list:
        active = sess_list[0].get("id")
    code, data = _get(f"{base}/api/session?sessionId={active}&lang=zh")
    ok("GET /api/session", code == 200 and "session" in data, f"code={code}")

    # 4) 新建会话
    code, data = _json_request("POST", f"{base}/api/sessions", {"name": "API Test Session", "lang": "zh"})
    ok("POST /api/sessions", code == 200 and "session" in data and "activeSessionId" in data, f"code={code}")
    new_id = data.get("activeSessionId") if isinstance(data, dict) else None

    # 4.1) workflows
    code, data = _get(f"{base}/api/workflows?sessionId={new_id}&lang=zh")
    ok(
        "GET /api/workflows",
        code == 200 and isinstance(data, dict) and isinstance(data.get("stages"), list) and isinstance(data.get("recentMessages"), list),
        f"code={code}",
    )

    # 4.2) knowledge
    code, data = _get(f"{base}/api/knowledge?q=")
    ok(
        "GET /api/knowledge",
        code == 200 and isinstance(data, dict) and isinstance(data.get("stats"), dict) and isinstance(data.get("items"), list),
        f"code={code}",
    )

    # 4.3) runs status invalid id
    code, data = _get(f"{base}/api/runs/status?runId=nope")
    ok("GET /api/runs/status 无效 runId 返回 404", code == 404, f"code={code}")

    # 4.4) runs stream invalid id
    code, data = _get(f"{base}/api/runs/stream?runId=nope")
    ok("GET /api/runs/stream 无效 runId 返回 404", code == 404, f"code={code}")

    # 5) create run
    code, data = _json_request(
        "POST",
        f"{base}/api/runs",
        {
            "message": "run api test",
            "sessionId": new_id,
            "lang": "zh",
            "allowWrite": False,
            "allowCommand": False,
        },
    )
    ok(
        "POST /api/runs",
        code == 200 and isinstance(data, dict) and isinstance(data.get("runId"), str) and data.get("sessionId") == new_id,
        f"code={code}",
    )
    run_id = data.get("runId") if isinstance(data, dict) else None

    # 5.1) run status
    code, data = _get(f"{base}/api/runs/status?runId={run_id}")
    ok(
        "GET /api/runs/status",
        code == 200 and isinstance(data, dict) and data.get("runId") == run_id and data.get("sessionId") == new_id,
        f"code={code}",
    )

    # 5.2) cancel run
    code, data = _json_request("POST", f"{base}/api/runs/cancel", {"runId": run_id, "sessionId": new_id, "lang": "zh"})
    ok(
        "POST /api/runs/cancel",
        code == 200 and isinstance(data, dict) and data.get("runId") == run_id,
        f"code={code}",
    )

    # 6) reset
    code, data = _json_request("POST", f"{base}/api/reset", {"sessionId": new_id, "lang": "zh"})
    ok("POST /api/reset", code == 200 and data.get("ok") is True, f"code={code}")

    # 7) chat 空消息
    code, data = _json_request("POST", f"{base}/api/chat", {"message": "", "sessionId": new_id, "lang": "zh"})
    ok("POST /api/chat 空 message 返回 400", code == 400, f"code={code} body={data}")

    # 8) stream 空消息
    code, data = _get(f"{base}/api/chat/stream?message=&sessionId={new_id}&lang=zh")
    ok("GET /api/chat/stream 空 message 返回 400", code == 400, f"code={code}")

    # 9) 404
    code, _ = _get(f"{base}/api/nope")
    ok("GET 未知路径 404", code == 404, f"code={code}")

    def _is_api_key_error(text: str) -> bool:
        t = text.lower()
        return "api key" in t or "401" in t or ("invalid" in t and "key" in t)

    # 9) 需 LLM：POST /api/chat
    if not args.skip_llm:
        if httpx is None:
            skip("POST /api/chat 简单对话", "httpx 未安装，请: pip install httpx")
        else:
            try:
                with httpx.Client(timeout=args.chat_timeout) as client:
                    r = client.post(
                        f"{base}/api/chat",
                        json={
                            "message": "请只回复一个词：测试通过",
                            "sessionId": new_id,
                            "lang": "zh",
                            "allowWrite": False,
                            "allowCommand": False,
                        },
                    )
                    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    err_text = str(body.get("error", ""))
                    if r.status_code == 200 and "reply" in body and "error" not in body:
                        ok("POST /api/chat 简单对话", True, f"status={r.status_code}")
                    elif r.status_code == 500 and _is_api_key_error(err_text):
                        skip("POST /api/chat 简单对话", f"模型服务拒绝（检查 OPENAI_API_KEY）: {err_text[:120]}")
                    else:
                        ok(
                            "POST /api/chat 简单对话",
                            False,
                            f"status={r.status_code} keys={list(body.keys())} err={err_text[:200]}",
                        )
            except Exception as e:
                ok("POST /api/chat 简单对话", False, str(e)[:300])

        # 10) SSE stream
        sse_name = "GET /api/chat/stream SSE"
        if httpx is None:
            skip(sse_name, "httpx 未安装")
        else:
            try:
                q = urlencode(
                    {
                        "message": "只回复：流式OK",
                        "sessionId": new_id,
                        "lang": "zh",
                        "allowWrite": "false",
                        "allowCommand": "false",
                    }
                )
                url = f"{base}/api/chat/stream?{q}"
                text = ""
                stream_timeout = httpx.Timeout(min(args.chat_timeout, 90.0), connect=10.0)
                with httpx.Client(timeout=stream_timeout) as client:
                    with client.stream("GET", url) as r:
                        if r.status_code != 200:
                            ok(sse_name, False, f"status={r.status_code}")
                        else:
                            for raw in r.iter_bytes():
                                text += raw.decode("utf-8", errors="replace")
                                if "event: error" in text:
                                    if _is_api_key_error(text):
                                        skip(sse_name, "SSE error 事件（API Key / 上游 401）")
                                    else:
                                        ok(sse_name, False, text[:240])
                                    break
                                if "event: done" in text:
                                    ok(sse_name, True, f"len={len(text)}")
                                    break
                                if len(text) > 512 * 1024:
                                    ok(sse_name, "event:" in text, f"truncated len={len(text)}")
                                    break
                            else:
                                if _is_api_key_error(text):
                                    skip(sse_name, "流结束但含 API 相关错误")
                                elif "event:" in text:
                                    ok(sse_name, "event: done" in text, f"len={len(text)}")
                                else:
                                    ok(sse_name, False, f"unexpected body len={len(text)}")
            except Exception as e:
                el = str(e).lower()
                if "timed out" in el or "timeout" in el:
                    skip(sse_name, f"超时（检查密钥与模型服务）: {str(e)[:100]}")
                else:
                    ok(sse_name, False, str(e)[:300])
    else:
        skip("POST /api/chat 简单对话", "--skip-llm")
        skip("GET /api/chat/stream SSE", "--skip-llm")

    # 汇总
    failed = [r for r in results if r[1] == "fail"]
    skipped = [r for r in results if r[1] == "skip"]
    passed_n = sum(1 for r in results if r[1] == "pass")
    print(f"\n共 {len(results)} 项：通过 {passed_n}，跳过 {len(skipped)}，失败 {len(failed)}\n")
    for name, outcome, detail in results:
        label = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}[outcome]
        print(f"  [{label}] {name}")
        if detail:
            print(f"         {detail}")
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
