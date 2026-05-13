from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
import os
import time
from typing import Any, Dict, List, Optional

app = FastAPI(title="OpenAI-to-Claude Proxy")

PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
UPSTREAM_URL = os.getenv("UPSTREAM_URL", "http://localhost:8000/v1")
UPSTREAM_AUTH_TOKEN = os.getenv("UPSTREAM_AUTH_TOKEN", "")

MODEL_MAP = {
    "claude-sonnet-4.5": "claude-sonnet-4.5",
    "claude-sonnet-4": "claude-sonnet-4",
    "claude-3.7-sonnet": "claude-3.7-sonnet",
    "claude-haiku-4.5": "claude-haiku-4.5",
}

UPSTREAM_MESSAGES_API = f"{UPSTREAM_URL}/messages"


def check_auth(auth_header: Optional[str]) -> None:
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = auth_header[len("Bearer "):].strip()
    if token != PROXY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


def map_model(model_name: str) -> str:
    print(f"[DEBUG] Received model name: {model_name}")
    if model_name not in MODEL_MAP:
        print(f"[DEBUG] Model not found in MAP. Available models: {list(MODEL_MAP.keys())}")
        raise HTTPException(status_code=400, detail=f"Invalid model: {model_name}")
    return MODEL_MAP[model_name]


def extract_system_and_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    system_parts: List[str] = []
    out_messages: List[Dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            if isinstance(content, str):
                system_parts.append(content)
        elif role in ("user", "assistant"):
            if isinstance(content, str):
                out_messages.append({
                    "role": role,
                    "content": [{"type": "text", "text": content}]
                })

    result: Dict[str, Any] = {"messages": out_messages}
    if system_parts:
        result["system"] = "\n".join(system_parts)
    return result


def openai_to_claude(body: Dict[str, Any]) -> Dict[str, Any]:
    model = map_model(body.get("model", ""))
    converted = extract_system_and_messages(body.get("messages", []))

    payload: Dict[str, Any] = {
        "model": model,
        "messages": converted["messages"],
        "max_tokens": body.get("max_tokens", 1024),
        "temperature": body.get("temperature", 0.7),
        "stream": body.get("stream", False),
    }

    if "system" in converted:
        payload["system"] = converted["system"]

    return payload


def claude_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def claude_to_openai(resp: Dict[str, Any]) -> Dict[str, Any]:
    content_text = claude_text_from_content(resp.get("content", []))
    usage = resp.get("usage", {})
    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)

    return {
        "id": resp.get("id", f"chatcmpl-{int(time.time())}"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": resp.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content_text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def call_upstream(payload: Dict[str, Any]) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {UPSTREAM_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(UPSTREAM_MESSAGES_API, headers=headers, json=payload)

    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)

    return r.json()


@app.get("/v1/models")
async def list_models(authorization: Optional[str] = Header(default=None)):
    check_auth(authorization)

    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": public_name,
                "object": "model",
                "created": now,
                "owned_by": "anthropic",
                "description": "Claude model via proxy",
            }
            for public_name in MODEL_MAP.keys()
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    check_auth(authorization)

    body = await request.json()
    print(f"[DEBUG] Received request body: {body}")
    
    # 强制禁用流式传输
    body["stream"] = False
    
    payload = openai_to_claude(body)

    upstream_resp = await call_upstream(payload)
    return JSONResponse(content=claude_to_openai(upstream_resp))