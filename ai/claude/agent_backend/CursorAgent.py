import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from html import unescape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from openai import OpenAI

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


# File lives at ai/claude/python/CursorAgent.py
# BASE_DIR = ai/claude  (where .env, agent_workbench, etc. live)
PYTHON_DIR = Path(__file__).resolve().parent  # ai/claude/python
BASE_DIR = PYTHON_DIR.parent                  # ai/claude
PROJECT_ROOT = BASE_DIR.parents[1]           # OpenAi (workspace root)
WEB_DIR = BASE_DIR / "agent_workbench"
SESSIONS_FILE = WEB_DIR / "sessions.json"
KNOWLEDGE_DIR = PROJECT_ROOT / "glm" / "knowledge_db"
API_ALLOWED_ORIGIN = os.getenv("AGENT_API_ALLOWED_ORIGIN", "*")

client = None
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
ACTIVE_SESSION_ID = None
ACTIVE_RUNS = {}
RUNS_LOCK = threading.Lock()
RUN_TERMINAL_STATUSES = {"idle", "error", "cancelled"}


class RunCancelledError(Exception):
    pass


TEXTS = {
    "zh": {
        "missing_key": "未检测到 OPENAI_API_KEY。请在项目根目录 .env 或 ai/claude/.env 中配置 OPENAI_API_KEY。",
        "tool_blocked_write": "❌ 写入动作被安全策略拦截，请先开启前端里的写入权限。",
        "tool_blocked_command": "❌ 命令执行被安全策略拦截，请先开启前端里的命令权限。",
        "search_code_none": "❌ 未找到包含关键字 '{keyword}' 的代码片段。",
        "search_code_title": "🔍 搜索结果:\n{content}",
        "search_file_none": "❌ 未找到包含关键字 '{filename}' 的文件。",
        "search_file_title": "🔍 文件查找结果:\n{content}",
        "read_title": "📄 {target} (带行号):\n{content}",
        "read_fail": "❌ 读取失败: {error}",
        "replace_ok": "✅ 精确修改成功: {target} [{start_line}-{end_line}]",
        "replace_bad_range": "❌ 无效的行号范围: 1~{total}",
        "replace_fail": "❌ 修改代码失败: {error}",
        "command_ok": "✅ (exit 0)\n{output}",
        "command_empty": "✅ 成功 (无输出)",
        "command_fail": "❌ 报错 (exit {code}):\n{err}\n{out}",
        "command_error": "❌ 终端异常: {error}",
        "cd_ok": "✅ 已切换工作目录至: {cwd}",
        "cd_fail": "❌ 目录不存在: {target}",
        "create_ok": "✅ 已创建文件: {target}",
        "create_fail": "❌ 创建失败: {error}",
        "delete_ok": "✅ 已删除: {target}",
        "delete_fail": "❌ 删除失败: {error}",
        "delete_missing": "❌ 路径不存在: {target}",
        "unknown_tool": "❌ 未知工具",
        "reply_empty": "本轮没有文本回复，但工具已经执行完毕。",
        "tool_limit": "已达到工具调用上限。",
        "message_required": "message is required",
        "system_prompt": "你是 CursorAgent，一个本地开发助手。\n你可以检索代码、读取文件、修改文件、执行命令以及进行网络搜索。\n修改文件必须先 read_file_with_lines，再 replace_lines。\n不要写会卡死终端的 input() 或 while True 交互菜单。\n除非用户另有要求，否则默认使用简体中文回复。\n当前工作目录: {cwd}\n",
        "tool_request": "[工具请求] {name}({args})",
        "tool_result": "[工具结果] {result}",
        "search_web_title": "🌐 网络搜索结果 ({query}):\n{content}",
        "search_web_none": "❌ 未找到关于 '{query}' 的搜索结果。",
    },
    "en": {
        "missing_key": "OPENAI_API_KEY was not found. Please configure it in the project root .env or ai/claude/.env.",
        "tool_blocked_write": "Action blocked by safety policy. Enable write actions in the workbench first.",
        "tool_blocked_command": "Action blocked by safety policy. Enable command actions in the workbench first.",
        "search_code_none": "No code snippets containing '{keyword}' were found.",
        "search_code_title": "Search Results:\n{content}",
        "search_file_none": "No files containing '{filename}' were found.",
        "search_file_title": "File Search Results:\n{content}",
        "read_title": "File with line numbers: {target}\n{content}",
        "read_fail": "Read failed: {error}",
        "replace_ok": "Updated successfully: {target} [{start_line}-{end_line}]",
        "replace_bad_range": "Invalid line range: 1~{total}",
        "replace_fail": "Code update failed: {error}",
        "command_ok": "Success (exit 0)\n{output}",
        "command_empty": "Success (no output)",
        "command_fail": "Command failed (exit {code}):\n{err}\n{out}",
        "command_error": "Terminal error: {error}",
        "cd_ok": "Working directory changed to: {cwd}",
        "cd_fail": "Directory does not exist: {target}",
        "create_ok": "Created file: {target}",
        "create_fail": "Create failed: {error}",
        "delete_ok": "Deleted: {target}",
        "delete_fail": "Delete failed: {error}",
        "delete_missing": "Path does not exist: {target}",
        "unknown_tool": "Unknown tool",
        "reply_empty": "No text reply was returned, but tool execution completed.",
        "tool_limit": "Tool call limit reached.",
        "message_required": "message is required",
        "system_prompt": "You are CursorAgent, a local development assistant.\nYou can search code, read files, modify files, execute commands and search the web.\nWhen changing a file, always call read_file_with_lines before replace_lines.\nDo not write scripts that block on input() or infinite interactive loops.\nUnless the user asks otherwise, reply in English.\nCurrent working directory: {cwd}\n",
        "tool_request": "[Tool Request] {name}({args})",
        "tool_result": "[Tool Result] {result}",
        "search_web_title": "🌐 Web Search Results ({query}):\n{content}",
        "search_web_none": "No search results found for '{query}'.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    bundle = TEXTS["en"] if lang == "en" else TEXTS["zh"]
    return bundle[key].format(**kwargs)


def configure_console_encoding():
    if os.name != "nt":
        return
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def load_env_file(path: Path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def initialize_environment():
    configure_console_encoding()
    for candidate in (PROJECT_ROOT / ".env", BASE_DIR / ".env", PYTHON_DIR / ".env"):
        load_env_file(candidate)
    config = {
        "base_url": os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "http://107.173.156.235:8000/v1",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("CHAT_MODEL", "claude-sonnet-4-5"),
        "trust_env": os.getenv("OPENAI_TRUST_ENV", "false").strip().lower() in ("1", "true", "yes", "on"),
        "verify": os.getenv("OPENAI_SSL_VERIFY", "true").strip().lower() in ("1", "true", "yes", "on"),
        "timeout": float(os.getenv("OPENAI_TIMEOUT_SECONDS", "120")),
    }
    if not config["api_key"]:
        raise RuntimeError(t("zh", "missing_key"))
    return config


CONFIG = initialize_environment()


def get_client():
    global client
    if client is None:
        http_client = httpx.Client(
            timeout=CONFIG["timeout"],
            trust_env=CONFIG["trust_env"],
            verify=CONFIG["verify"],
        )
        client = OpenAI(
            base_url=CONFIG["base_url"],
            api_key=CONFIG["api_key"],
            http_client=http_client,
        )
    return client


def get_http_client():
    return httpx.Client(
        timeout=CONFIG["timeout"],
        trust_env=CONFIG["trust_env"],
        verify=CONFIG["verify"],
        follow_redirects=True,
        headers={
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            )
        },
    )


def truncate_text(text: str, max_len: int = 5000) -> str:
    return text if len(text) <= max_len else text[:max_len] + f"\n... ({len(text) - max_len} chars truncated)"


def assistant_message_to_history(msg):
    history_item = {
        "role": "assistant",
        "content": getattr(msg, "content", "") or "",
    }
    tool_calls = []
    for tc in getattr(msg, "tool_calls", []) or []:
        tool_calls.append(
            {
                "id": tc.id,
                "type": getattr(tc, "type", "function"),
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
        )
    if tool_calls:
        history_item["tool_calls"] = tool_calls
    return history_item


def build_stream_tool_calls(tool_call_map):
    ordered = []
    for index in sorted(tool_call_map):
        entry = tool_call_map[index]
        ordered.append(
            {
                "id": entry.get("id") or f"call_{index}",
                "type": entry.get("type") or "function",
                "function": {
                    "name": entry.get("function", {}).get("name", ""),
                    "arguments": entry.get("function", {}).get("arguments", ""),
                },
            }
        )
    return ordered


class ToolRuntime:
    def __init__(self, lang="zh", allow_write=False, allow_command=False, on_event=None, cwd=None):
        self.lang = lang
        self.allow_write = allow_write
        self.allow_command = allow_command
        self.cwd = cwd or str(PROJECT_ROOT)
        self.logs = []
        self.on_event = on_event or (lambda payload: None)

    def emit(self, event_type: str, payload):
        self.on_event({"type": event_type, **payload})

    def log(self, text: str):
        self.logs.append(text)
        self.emit("tool_log", {"message": text})

    def confirm_write(self) -> bool:
        return self.allow_write

    def confirm_command(self) -> bool:
        return self.allow_command


def search_code(keyword: str, path: str = ".", lang="zh", cwd=None) -> str:
    base_cwd = os.path.abspath(cwd or str(PROJECT_ROOT))
    target = os.path.abspath(os.path.join(base_cwd, path))
    results = []
    valid_exts = (".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md", ".txt")
    for root, _, files in os.walk(target):
        if any(exclude in root for exclude in (".git", "__pycache__", "node_modules", "venv", ".idea")):
            continue
        for file in files:
            if not file.endswith(valid_exts):
                continue
            filepath = os.path.join(root, file)
            try:
                lines = Path(filepath).read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, start=1):
                if keyword.lower() in line.lower():
                    results.append(f"{os.path.relpath(filepath, base_cwd)}:{i} -> {line.strip()}")
                    if len(results) >= 50:
                        results.append("...")
                        return t(lang, "search_code_title", content="\n".join(results))
    return t(lang, "search_code_title", content="\n".join(results)) if results else t(lang, "search_code_none", keyword=keyword)


def search_file(filename: str, path: str = ".", lang="zh", cwd=None) -> str:
    base_cwd = os.path.abspath(cwd or str(PROJECT_ROOT))
    target = os.path.abspath(os.path.join(base_cwd, path))
    results = []
    for root, _, files in os.walk(target):
        if any(exclude in root for exclude in (".git", "__pycache__", "node_modules", "venv", ".idea")):
            continue
        for file in files:
            if filename.lower() in file.lower():
                results.append(os.path.abspath(os.path.join(root, file)))
                if len(results) >= 20:
                    results.append("...")
                    return t(lang, "search_file_title", content="\n".join(results))
    return t(lang, "search_file_title", content="\n".join(results)) if results else t(lang, "search_file_none", filename=filename)


def read_file_with_lines(path: str, lang="zh", cwd=None) -> str:
    target = os.path.abspath(os.path.join(os.path.abspath(cwd or str(PROJECT_ROOT)), path))
    try:
        lines = Path(target).read_text(encoding="utf-8").splitlines()
        output = [f"{i:4d} | {line}" for i, line in enumerate(lines, start=1)]
        return t(lang, "read_title", target=target, content=truncate_text("\n".join(output), 6000))
    except Exception as e:
        return t(lang, "read_fail", error=e)


def replace_lines(runtime: ToolRuntime, path: str, start_line: int, end_line: int, new_content: str) -> str:
    if not runtime.confirm_write():
        return t(runtime.lang, "tool_blocked_write")
    target = os.path.abspath(os.path.join(runtime.cwd, path))
    try:
        lines = Path(target).read_text(encoding="utf-8").splitlines(keepends=True)
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return t(runtime.lang, "replace_bad_range", total=len(lines))
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        new_lines = lines[: start_line - 1] + [new_content] + lines[end_line:]
        Path(target).write_text("".join(new_lines), encoding="utf-8")
        return t(runtime.lang, "replace_ok", target=target, start_line=start_line, end_line=end_line)
    except Exception as e:
        return t(runtime.lang, "replace_fail", error=e)


def execute_command(runtime: ToolRuntime, command: str) -> str:
    if not runtime.confirm_command():
        return t(runtime.lang, "tool_blocked_command")
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
            cwd=runtime.cwd,
        )
        out = truncate_text(result.stdout.strip())
        err = truncate_text(result.stderr.strip())
        if result.returncode == 0:
            return t(runtime.lang, "command_ok", output=out) if out else t(runtime.lang, "command_empty")
        return t(runtime.lang, "command_fail", code=result.returncode, err=err, out=out)
    except Exception as e:
        return t(runtime.lang, "command_error", error=e)


def change_directory(path: str, lang="zh", cwd=None):
    base_cwd = os.path.abspath(cwd or str(PROJECT_ROOT))
    target = os.path.abspath(os.path.join(base_cwd, path))
    if os.path.isdir(target):
        return target, t(lang, "cd_ok", cwd=target)
    return base_cwd, t(lang, "cd_fail", target=target)


def create_file(runtime: ToolRuntime, path: str, content: str = "") -> str:
    if not runtime.confirm_write():
        return t(runtime.lang, "tool_blocked_write")
    target = os.path.abspath(os.path.join(runtime.cwd, path))
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        Path(target).write_text(content, encoding="utf-8")
        return t(runtime.lang, "create_ok", target=target)
    except Exception as e:
        return t(runtime.lang, "create_fail", error=e)


def delete_path(runtime: ToolRuntime, path: str) -> str:
    if not runtime.confirm_write():
        return t(runtime.lang, "tool_blocked_write")
    target = os.path.abspath(os.path.join(runtime.cwd, path))
    try:
        if not os.path.exists(target):
            return t(runtime.lang, "delete_missing", target=target)
        shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)
        return t(runtime.lang, "delete_ok", target=target)
    except Exception as e:
        return t(runtime.lang, "delete_fail", error=e)


def web_search(query: str, lang="zh") -> str:
    try:
        with DDGS() as ddgs:
            results = [f"- {r['title']}: {r['body']} ({r['href']})" for r in ddgs.text(query, max_results=8)]
            if not results:
                return t(lang, "search_web_none", query=query)
            return t(lang, "search_web_title", query=query, content="\n".join(results))
    except Exception as e:
        return f"❌ Search error: {e}"

def _search_with_ddgs(query: str):
    if DDGS is None:
        return []
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=8))


def _clean_html_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _search_with_duckduckgo_html(query: str):
    with get_http_client() as http:
        response = http.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
        )
        response.raise_for_status()
    html = response.text
    matches = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>(?P<rest>.*?)(?:</div>\s*</div>|<a[^>]*class="result__a")',
        html,
        flags=re.S,
    )
    results = []
    for href, title, rest in matches[:8]:
        snippet_match = re.search(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', rest, flags=re.S)
        results.append(
            {
                "title": _clean_html_text(title),
                "body": _clean_html_text(snippet_match.group(1) if snippet_match else ""),
                "href": unescape(href),
            }
        )
    return results


def web_search_live(query: str, lang="zh") -> str:
    try:
        raw_results = _search_with_ddgs(query)
    except Exception as e:
        try:
            raw_results = _search_with_duckduckgo_html(query)
        except Exception as fallback_error:
            return f"Search error: {e}; fallback error: {fallback_error}"
    if not raw_results:
        try:
            raw_results = _search_with_duckduckgo_html(query)
        except Exception:
            raw_results = []
    results = []
    for item in raw_results[:8]:
        title = (item.get("title") or "").strip()
        body = (item.get("body") or "").strip()
        href = (item.get("href") or item.get("url") or "").strip()
        line = f"- {title}"
        if body:
            line += f": {body}"
        if href:
            line += f" ({href})"
        results.append(line)
    if not results:
        return t(lang, "search_web_none", query=query)
    return t(lang, "search_web_title", query=query, content="\n".join(results))


TOOLS = [
    {"type": "function", "function": {"name": "search_code", "description": "Search code snippets.", "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}, "path": {"type": "string"}}, "required": ["keyword"]}}},
    {"type": "function", "function": {"name": "search_file", "description": "Search file paths.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "path": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "read_file_with_lines", "description": "Read a file with line numbers.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "replace_lines", "description": "Update a line range in a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}, "new_content": {"type": "string"}}, "required": ["path", "start_line", "end_line", "new_content"]}}},
    {"type": "function", "function": {"name": "execute_command", "description": "Execute a PowerShell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "change_directory", "description": "Change working directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "create_file", "description": "Create a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "delete_path", "description": "Delete a file or directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "web_search_live", "description": "Search the internet for real-time information such as news, weather, and current events.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]


def build_system_prompt(lang: str, cwd=None) -> str:
    return t(lang, "system_prompt", cwd=os.path.abspath(cwd or str(PROJECT_ROOT)))


def compress_history(history, max_messages=12):
    if len(history) <= max_messages:
        return history
    system_prompt = history[0]
    cut_idx = len(history) - max_messages + 1
    while cut_idx < len(history) and history[cut_idx].get("role") != "user":
        cut_idx += 1
    if cut_idx >= len(history):
        cut_idx = len(history) - 1
    return [system_prompt] + history[cut_idx:]


class AgentSession:
    def __init__(self, name=None, lang="zh"):
        self.id = uuid.uuid4().hex[:8]
        self.name = name or f"Session {self.id[:4]}"
        self.lang = lang
        self.cwd = str(PROJECT_ROOT)
        self.lock = threading.Lock()
        self.metrics = {
            "promptTokens": 0,
            "completionTokens": 0,
            "totalTokens": 0,
            "cost": 0,
            "latencyMs": 0,
            "errors": 0,
        }
        self.last_status = "idle"
        self.last_tool_logs = []
        self.reset()

    def reset(self):
        self.history = [{"role": "system", "content": build_system_prompt(self.lang, self.cwd)}]
        self.last_status = "idle"
        self.last_tool_logs = []

    def set_lang(self, lang: str):
        self.lang = lang if lang in ("zh", "en") else "zh"
        if self.history:
            self.history[0]["content"] = build_system_prompt(self.lang, self.cwd)

    def summary(self):
        return {
            "id": self.id,
            "name": self.name,
            "lang": self.lang,
            "status": self.last_status,
            "metrics": self.metrics,
            "messageCount": len(self.ui_messages()),
        }

    def ui_messages(self):
        visible = []
        for item in self.history:
            if item.get("role") in ("user", "assistant", "system") and item.get("content", ""):
                visible.append({"role": item["role"], "content": item["content"]})
        return visible

    def detail(self):
        active_run = get_session_active_run(self.id)
        return {
            "id": self.id,
            "name": self.name,
            "lang": self.lang,
            "cwd": self.cwd,
            "status": self.last_status,
            "messages": self.ui_messages(),
            "toolLogs": self.last_tool_logs,
            "metrics": self.metrics,
            "activeRun": _run_view(active_run) if active_run else None,
        }

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "lang": self.lang,
            "cwd": self.cwd,
            "history": self.history,
            "metrics": self.metrics,
            "last_status": self.last_status,
            "last_tool_logs": self.last_tool_logs,
        }

    @classmethod
    def from_dict(cls, data):
        session = cls(name=data.get("name"), lang=data.get("lang", "zh"))
        session.id = data.get("id") or session.id
        session.cwd = os.path.abspath(data.get("cwd") or str(PROJECT_ROOT))
        session.history = data.get("history") or [{"role": "system", "content": build_system_prompt(session.lang, session.cwd)}]
        if session.history:
            session.history[0]["content"] = build_system_prompt(session.lang, session.cwd)
        session.metrics = data.get("metrics") or session.metrics
        session.last_status = data.get("last_status", "idle")
        session.last_tool_logs = data.get("last_tool_logs", [])
        return session

    def _append_tool(self, tool_call_id: str, content: str):
        self.history.append({"tool_call_id": tool_call_id, "role": "tool", "content": content})

    def _handle_tools(self, runtime: ToolRuntime, tool_calls):
        for tc in tool_calls:
            if isinstance(tc, dict):
                name = tc["function"]["name"]
                args_raw = tc["function"]["arguments"]
                tool_call_id = tc["id"]
            else:
                name = tc.function.name
                args_raw = tc.function.arguments
                tool_call_id = tc.id
            args = json.loads(args_raw)
            runtime.log(t(self.lang, "tool_request", name=name, args=args_raw[:140]))
            if name == "search_code":
                result = search_code(lang=self.lang, cwd=self.cwd, **args)
            elif name == "search_file":
                result = search_file(lang=self.lang, cwd=self.cwd, **args)
            elif name == "read_file_with_lines":
                result = read_file_with_lines(lang=self.lang, cwd=self.cwd, **args)
            elif name == "replace_lines":
                result = replace_lines(runtime, **args)
            elif name == "execute_command":
                result = execute_command(runtime, **args)
            elif name == "change_directory":
                self.cwd, result = change_directory(lang=self.lang, cwd=self.cwd, **args)
                runtime.cwd = self.cwd
                if self.history:
                    self.history[0]["content"] = build_system_prompt(self.lang, self.cwd)
            elif name == "create_file":
                result = create_file(runtime, **args)
            elif name == "delete_path":
                result = delete_path(runtime, **args)
            elif name == "web_search_live":
                result = web_search_live(lang=self.lang, **args)
            else:
                result = t(self.lang, "unknown_tool")
            runtime.log(t(self.lang, "tool_result", result=truncate_text(result, 320)))
            self._append_tool(tool_call_id, result)

    def chat(self, user_input: str, allow_write: bool = False, allow_command: bool = False, on_event=None):
        runtime = ToolRuntime(lang=self.lang, allow_write=allow_write, allow_command=allow_command, on_event=on_event, cwd=self.cwd)
        with self.lock:
            start = time.perf_counter()
            self.last_status = "running"
            self.history[0]["content"] = build_system_prompt(self.lang, self.cwd)
            self.history.append({"role": "user", "content": user_input})
            runtime.emit("status", {"status": "running"})
            reply = None

            try:
                for _ in range(15):
                    response = get_client().chat.completions.create(
                        model=CONFIG["model"],
                        messages=compress_history(self.history),
                        tools=TOOLS,
                        tool_choice="auto",
                        max_tokens=4096,
                    )
                    msg = response.choices[0].message
                    self.history.append(assistant_message_to_history(msg))
                    if msg.tool_calls:
                        self._handle_tools(runtime, msg.tool_calls)
                        continue
                    reply = (msg.content or "").strip() or t(self.lang, "reply_empty")
                    usage = getattr(response, "usage", None)
                    self.metrics["promptTokens"] = getattr(usage, "prompt_tokens", 0)
                    self.metrics["completionTokens"] = getattr(usage, "completion_tokens", 0)
                    self.metrics["totalTokens"] = getattr(usage, "total_tokens", 0)
                    break
                if reply is None:
                    reply = t(self.lang, "tool_limit")
            except Exception:
                self.metrics["errors"] += 1
                self.last_status = "error"
                runtime.emit("status", {"status": "error"})
                raise

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.metrics["latencyMs"] = elapsed_ms
            self.metrics["cost"] = round(self.metrics["totalTokens"] * 0.000012, 4)
            self.last_tool_logs = runtime.logs[-40:]
            self.last_status = "idle"
            runtime.emit("metrics", {"metrics": self.metrics})
            runtime.emit("status", {"status": "idle"})
            save_sessions()

            return {
                "reply": reply,
                "toolLogs": runtime.logs,
                "cwd": self.cwd,
                "status": self.last_status,
                "metrics": self.metrics,
            }

    def chat_stream(self, user_input: str, allow_write: bool = False, allow_command: bool = False, on_event=None, cancel_event=None):
        runtime = ToolRuntime(lang=self.lang, allow_write=allow_write, allow_command=allow_command, on_event=on_event, cwd=self.cwd)

        def ensure_not_cancelled():
            if cancel_event is not None and cancel_event.is_set():
                self.last_status = "cancelled"
                runtime.emit("status", {"status": "cancelled"})
                save_sessions()
                raise RunCancelledError("run cancelled")

        with self.lock:
            start = time.perf_counter()
            self.last_status = "running"
            self.history[0]["content"] = build_system_prompt(self.lang, self.cwd)
            self.history.append({"role": "user", "content": user_input})
            runtime.emit("status", {"status": "running"})
            reply = ""

            try:
                ensure_not_cancelled()
                for _ in range(15):
                    ensure_not_cancelled()
                    content_parts = []
                    tool_call_map = {}
                    usage = None

                    try:
                        stream = get_client().chat.completions.create(
                            model=CONFIG["model"],
                            messages=compress_history(self.history),
                            tools=TOOLS,
                            tool_choice="auto",
                            max_tokens=4096,
                            stream=True,
                            stream_options={"include_usage": True},
                        )

                        for chunk in stream:
                            ensure_not_cancelled()
                            if getattr(chunk, "usage", None):
                                usage = chunk.usage
                            for choice in getattr(chunk, "choices", []) or []:
                                delta = getattr(choice, "delta", None)
                                if not delta:
                                    continue
                                if getattr(delta, "content", None):
                                    content_parts.append(delta.content)
                                    runtime.emit("delta", {"content": delta.content})
                                for tc in getattr(delta, "tool_calls", []) or []:
                                    entry = tool_call_map.setdefault(
                                        tc.index,
                                        {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                                    )
                                    if getattr(tc, "id", None):
                                        entry["id"] = tc.id
                                    if getattr(tc, "type", None):
                                        entry["type"] = tc.type
                                    if getattr(tc, "function", None):
                                        if getattr(tc.function, "name", None):
                                            entry["function"]["name"] += tc.function.name
                                        if getattr(tc.function, "arguments", None):
                                            entry["function"]["arguments"] += tc.function.arguments
                    except Exception:
                        response = get_client().chat.completions.create(
                            model=CONFIG["model"],
                            messages=compress_history(self.history),
                            tools=TOOLS,
                            tool_choice="auto",
                            max_tokens=4096,
                        )
                        msg = response.choices[0].message
                        content_parts = [getattr(msg, "content", "") or ""]
                        usage = getattr(response, "usage", None)
                        if getattr(msg, "tool_calls", None):
                            tool_call_map = {
                                index: {
                                    "id": tc.id,
                                    "type": getattr(tc, "type", "function"),
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for index, tc in enumerate(msg.tool_calls)
                            }

                    ensure_not_cancelled()
                    content = "".join(content_parts)
                    tool_calls = build_stream_tool_calls(tool_call_map)
                    assistant_message = {"role": "assistant", "content": content}
                    if tool_calls:
                        assistant_message["tool_calls"] = tool_calls
                    self.history.append(assistant_message)

                    if tool_calls:
                        self._handle_tools(runtime, tool_calls)
                        continue

                    reply = content.strip() or t(self.lang, "reply_empty")
                    self.metrics["promptTokens"] = getattr(usage, "prompt_tokens", 0) if usage else 0
                    self.metrics["completionTokens"] = getattr(usage, "completion_tokens", 0) if usage else 0
                    self.metrics["totalTokens"] = getattr(usage, "total_tokens", 0) if usage else 0
                    break

                if not reply:
                    reply = t(self.lang, "tool_limit")
            except RunCancelledError:
                self.last_tool_logs = runtime.logs[-40:]
                raise
            except Exception:
                self.metrics["errors"] += 1
                self.last_status = "error"
                runtime.emit("status", {"status": "error"})
                save_sessions()
                raise

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.metrics["latencyMs"] = elapsed_ms
            self.metrics["cost"] = round(self.metrics["totalTokens"] * 0.000012, 4)
            self.last_tool_logs = runtime.logs[-40:]
            self.last_status = "idle"
            runtime.emit("metrics", {"metrics": self.metrics})
            runtime.emit("status", {"status": "idle"})
            save_sessions()

            return {
                "reply": reply,
                "toolLogs": runtime.logs,
                "cwd": self.cwd,
                "status": self.last_status,
                "metrics": self.metrics,
            }


def _save_sessions_unlocked():
    global ACTIVE_SESSION_ID
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "activeSessionId": ACTIVE_SESSION_ID,
        "sessions": [session.to_dict() for session in SESSIONS.values()],
    }
    SESSIONS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_sessions():
    with SESSIONS_LOCK:
        _save_sessions_unlocked()


def load_sessions():
    global ACTIVE_SESSION_ID
    if not SESSIONS_FILE.exists():
        return
    try:
        payload = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        ACTIVE_SESSION_ID = payload.get("activeSessionId")
        sessions = payload.get("sessions") or []
        for item in sessions:
            session = AgentSession.from_dict(item)
            SESSIONS[session.id] = session
    except Exception:
        pass


def get_or_create_session(session_id=None, lang="zh"):
    global ACTIVE_SESSION_ID
    with SESSIONS_LOCK:
        if session_id and session_id in SESSIONS:
            session = SESSIONS[session_id]
            session.set_lang(lang)
            ACTIVE_SESSION_ID = session.id
            _save_sessions_unlocked()
            return session
        session = AgentSession(lang=lang)
        SESSIONS[session.id] = session
        ACTIVE_SESSION_ID = session.id
        _save_sessions_unlocked()
        return session


def create_session(name=None, lang="zh"):
    global ACTIVE_SESSION_ID
    with SESSIONS_LOCK:
        session = AgentSession(name=name, lang=lang)
        SESSIONS[session.id] = session
        ACTIVE_SESSION_ID = session.id
        _save_sessions_unlocked()
        return session


def _run_view(run):
    return {
        "runId": run["id"],
        "sessionId": run["sessionId"],
        "status": run["status"],
        "startedAt": run["startedAt"],
        "finishedAt": run.get("finishedAt"),
        "lastSeq": run["nextSeq"] - 1,
        "error": run.get("error"),
        "metrics": run.get("metrics") or {},
        "done": run["status"] in RUN_TERMINAL_STATUSES,
        "cancelled": run["status"] == "cancelled",
    }


def _append_run_event_unlocked(run, event_name: str, payload: dict):
    event = {"seq": run["nextSeq"], "type": event_name, **payload}
    run["nextSeq"] += 1
    run["events"].append(event)
    if event_name == "status":
        run["status"] = payload.get("status", run["status"])
    elif event_name == "metrics":
        run["metrics"] = payload.get("metrics") or {}
    elif event_name == "error":
        run["status"] = "error"
        run["error"] = payload.get("error")
        run["finishedAt"] = time.time()
    elif event_name == "done":
        run["status"] = payload.get("status") or "idle"
        run["result"] = payload
        run["finishedAt"] = time.time()
        run["metrics"] = payload.get("metrics") or run.get("metrics") or {}
    return event


def get_run(run_id: str):
    with RUNS_LOCK:
        return ACTIVE_RUNS.get(run_id)


def get_session_active_run(session_id: str):
    with RUNS_LOCK:
        for run in reversed(list(ACTIVE_RUNS.values())):
            if run["sessionId"] == session_id and run["status"] not in RUN_TERMINAL_STATUSES:
                return run
        return None


def create_run(session: AgentSession, message: str, allow_write: bool, allow_command: bool):
    run_id = uuid.uuid4().hex[:12]
    run = {
        "id": run_id,
        "sessionId": session.id,
        "message": message,
        "allowWrite": allow_write,
        "allowCommand": allow_command,
        "status": "queued",
        "events": [],
        "nextSeq": 1,
        "startedAt": time.time(),
        "finishedAt": None,
        "error": None,
        "result": None,
        "metrics": {},
        "cancelEvent": threading.Event(),
        "condition": threading.Condition(),
        "thread": None,
    }

    with RUNS_LOCK:
        ACTIVE_RUNS[run_id] = run
        _append_run_event_unlocked(run, "start", {"runId": run_id, "sessionId": session.id})

    def emit(event_name: str, payload: dict):
        with RUNS_LOCK:
            current = ACTIVE_RUNS.get(run_id)
            if current is None:
                return
            _append_run_event_unlocked(current, event_name, payload)
            condition = current["condition"]
        with condition:
            condition.notify_all()

    def worker():
        try:
            result = session.chat_stream(
                message,
                allow_write=allow_write,
                allow_command=allow_command,
                on_event=lambda evt: emit(evt["type"], evt),
                cancel_event=run["cancelEvent"],
            )
            emit("done", result)
        except RunCancelledError as e:
            emit("error", {"error": str(e), "cancelled": True})
        except Exception as e:
            emit("error", {"error": str(e)})

    thread = threading.Thread(target=worker, daemon=True)
    run["thread"] = thread
    thread.start()
    return run


def cancel_run(run_id: str):
    with RUNS_LOCK:
        run = ACTIVE_RUNS.get(run_id)
        if run is None:
            return None
        if run["status"] in RUN_TERMINAL_STATUSES:
            return run
        run["status"] = "cancelled"
        run["finishedAt"] = time.time()
        run["cancelEvent"].set()
        _append_run_event_unlocked(run, "status", {"status": "cancelled"})
        condition = run["condition"]
    with condition:
        condition.notify_all()
    return run


def stream_run_events(handler, run, cursor: int = 0):
    handler.send_response(HTTPStatus.OK)
    handler._send_cors_headers()
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.end_headers()

    def send_event(event_name: str, payload: dict):
        body = f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        handler.wfile.write(body.encode("utf-8"))
        handler.wfile.flush()

    next_seq = max(int(cursor or 0) + 1, 1)
    condition = run["condition"]
    while True:
        with RUNS_LOCK:
            fresh = ACTIVE_RUNS.get(run["id"])
            if fresh is None:
                return
            pending = [event for event in fresh["events"] if event["seq"] >= next_seq]
            is_done = fresh["status"] in RUN_TERMINAL_STATUSES and not pending
        if pending:
            for event in pending:
                send_event(event["type"], event)
                next_seq = event["seq"] + 1
            continue
        if is_done:
            return
        with condition:
            condition.wait(timeout=1.0)


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _safe_read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _knowledge_documents():
    if not KNOWLEDGE_DIR.exists():
        return []

    docs = []
    for file_path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        try:
            content = _safe_read_text(file_path)
        except Exception:
            continue
        docs.append(
            {
                "id": _relative_to_project(file_path),
                "name": file_path.name,
                "path": _relative_to_project(file_path),
                "updatedAt": int(file_path.stat().st_mtime),
                "size": file_path.stat().st_size,
                "content": content,
            }
        )
    return docs


def build_knowledge_payload(query: str = ""):
    docs = _knowledge_documents()
    normalized = (query or "").strip().lower()
    matched = []

    for item in docs:
        content = item["content"]
        haystack = f'{item["name"]}\n{content}'.lower()
        if normalized and normalized not in haystack:
            continue

        snippet = content.strip().replace("\r\n", "\n").replace("\r", "\n")
        if normalized:
            idx = haystack.find(normalized)
            raw_idx = max(idx - 80, 0)
            raw_end = min(idx + 180, len(content))
            snippet = content[raw_idx:raw_end].strip()
        snippet = truncate_text(" ".join(snippet.split()), 240)
        matched.append(
            {
                "id": item["id"],
                "name": item["name"],
                "path": item["path"],
                "updatedAt": item["updatedAt"],
                "size": item["size"],
                "snippet": snippet,
            }
        )

    matched.sort(key=lambda doc: (0 if normalized and normalized in doc["name"].lower() else 1, -doc["updatedAt"]))
    total_bytes = sum(item["size"] for item in docs)
    return {
        "query": query,
        "stats": {
            "documents": len(docs),
            "matches": len(matched),
            "bytes": total_bytes,
        },
        "items": matched[:50],
    }


def build_workflow_payload(session: AgentSession):
    messages = session.ui_messages()
    user_messages = [item for item in messages if item["role"] == "user"]
    assistant_messages = [item for item in messages if item["role"] == "assistant"]
    latest_user = user_messages[-1]["content"] if user_messages else ""
    latest_reply = assistant_messages[-1]["content"] if assistant_messages else ""
    tool_logs = session.last_tool_logs[-20:]

    stages = [
        {
            "id": "intake",
            "title": "需求接入" if session.lang == "zh" else "Request Intake",
            "status": "running" if session.last_status == "running" else "done" if latest_user else "idle",
            "summary": truncate_text(latest_user or ("等待输入" if session.lang == "zh" else "Waiting for input"), 140),
            "count": len(user_messages),
        },
        {
            "id": "execution",
            "title": "执行编排" if session.lang == "zh" else "Execution",
            "status": session.last_status,
            "summary": truncate_text(tool_logs[-1] if tool_logs else ("尚无工具记录" if session.lang == "zh" else "No tool activity yet"), 140),
            "count": len(tool_logs),
        },
        {
            "id": "delivery",
            "title": "结果输出" if session.lang == "zh" else "Delivery",
            "status": "done" if latest_reply and session.last_status != "running" else session.last_status,
            "summary": truncate_text(latest_reply or ("暂无输出" if session.lang == "zh" else "No response yet"), 140),
            "count": len(assistant_messages),
        },
    ]

    return {
        "sessionId": session.id,
        "sessionName": session.name,
        "status": session.last_status,
        "metrics": session.metrics,
        "stages": stages,
        "toolLogs": tool_logs,
        "recentMessages": messages[-8:],
    }


load_sessions()
DEFAULT_SESSION = SESSIONS.get(ACTIVE_SESSION_ID) or next(iter(SESSIONS.values()), None) or create_session(name="Primary Session", lang="zh")
ACTIVE_SESSION_ID = DEFAULT_SESSION.id


def content_type(path: Path) -> str:
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
    }.get(path.suffix.lower(), "text/plain; charset=utf-8")


class AgentWorkbenchHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_cors_headers(self):
        origin = self.headers.get("Origin")
        allow_origin = API_ALLOWED_ORIGIN
        if API_ALLOWED_ORIGIN == "*" and origin:
            allow_origin = origin
        self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path in ("/", "/api", "/api/health"):
            return self.send_json({
                "ok": True,
                "service": "CursorAgent API",
                "model": CONFIG["model"],
                "cwd": str(PROJECT_ROOT),
                "frontend": str(WEB_DIR),
            })

        if parsed.path == "/api/status":
            session = get_or_create_session(query.get("sessionId", [DEFAULT_SESSION.id])[0], query.get("lang", ["zh"])[0])
            return self.send_json({
                "agent": "CursorAgent",
                "model": CONFIG["model"],
                "cwd": session.cwd,
                "status": session.last_status,
                "admin": bool(is_admin()),
                "sessions": [item.summary() for item in list(SESSIONS.values())],
                "activeSessionId": session.id,
                "metrics": session.metrics,
                "toolLogs": session.last_tool_logs,
            })

        if parsed.path == "/api/session":
            session = get_or_create_session(query.get("sessionId", [DEFAULT_SESSION.id])[0], query.get("lang", ["zh"])[0])
            return self.send_json({"session": session.detail()})

        if parsed.path == "/api/workflows":
            session = get_or_create_session(query.get("sessionId", [DEFAULT_SESSION.id])[0], query.get("lang", ["zh"])[0])
            return self.send_json(build_workflow_payload(session))

        if parsed.path == "/api/knowledge":
            return self.send_json(build_knowledge_payload(query.get("q", [""])[0]))

        if parsed.path == "/api/runs/status":
            run_id = query.get("runId", [""])[0]
            run = get_run(run_id)
            if run is None:
                return self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return self.send_json(_run_view(run))

        if parsed.path == "/api/runs/stream":
            run_id = query.get("runId", [""])[0]
            run = get_run(run_id)
            if run is None:
                return self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            cursor = query.get("cursor", ["0"])[0]
            try:
                cursor_value = int(cursor)
            except ValueError:
                return self.send_json({"error": "invalid cursor"}, HTTPStatus.BAD_REQUEST)
            return stream_run_events(self, run, cursor_value)

        if parsed.path == "/api/chat/stream":
            session = get_or_create_session(query.get("sessionId", [DEFAULT_SESSION.id])[0], query.get("lang", ["zh"])[0])
            message = query.get("message", [""])[0]
            allow_write = query.get("allowWrite", ["false"])[0].lower() == "true"
            allow_command = query.get("allowCommand", ["false"])[0].lower() == "true"
            if not message:
                return self.send_json({"error": t(session.lang, "message_required")}, HTTPStatus.BAD_REQUEST)
            run = create_run(session, message, allow_write, allow_command)
            return stream_run_events(self, run)
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads((self.rfile.read(length) or b"{}").decode("utf-8"))
        lang = payload.get("lang", "zh")
        session = get_or_create_session(payload.get("sessionId") or DEFAULT_SESSION.id, lang)

        if parsed.path == "/api/sessions":
            session = create_session(name=payload.get("name"), lang=lang)
            return self.send_json({"session": session.summary(), "activeSessionId": session.id})
        if parsed.path == "/api/reset":
            session.reset()
            save_sessions()
            return self.send_json({"ok": True, "sessionId": session.id})
        if parsed.path == "/api/runs":
            message = (payload.get("message") or "").strip()
            if not message:
                return self.send_json({"error": t(lang, "message_required")}, HTTPStatus.BAD_REQUEST)
            allow_write = payload.get("allowWrite") is True
            allow_command = payload.get("allowCommand") is True
            run = create_run(session, message, allow_write, allow_command)
            return self.send_json(_run_view(run))
        if parsed.path == "/api/runs/cancel":
            run_id = payload.get("runId") or ""
            run = cancel_run(run_id)
            if run is None:
                return self.send_json({"error": "run not found"}, HTTPStatus.NOT_FOUND)
            return self.send_json(_run_view(run))
        if parsed.path == "/api/chat":
            message = (payload.get("message") or "").strip()
            if not message:
                return self.send_json({"error": t(lang, "message_required")}, HTTPStatus.BAD_REQUEST)
            allow_write = payload.get("allowWrite") is True
            allow_command = payload.get("allowCommand") is True
            try:
                return self.send_json(
                    session.chat(
                        message,
                        allow_write=allow_write,
                        allow_command=allow_command,
                    )
                )
            except Exception as e:
                return self.send_json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def stream_chat(self, session: AgentSession, message: str, allow_write: bool, allow_command: bool):
        run = create_run(session, message, allow_write, allow_command)
        return stream_run_events(self, run)

    def send_json(self, payload, status=HTTPStatus.OK):
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        return


def run_cli():
    session = DEFAULT_SESSION
    print(f"CursorAgent CLI | cwd={session.cwd} | model={CONFIG['model']}")
    if not is_admin():
        print("警告：当前不是管理员权限。")
    while True:
        user_input = input("你 > ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            break
        if user_input.lower() in ("clear", "清空"):
            session.reset()
            print("上下文已清空。")
            continue
        result = session.chat(user_input, allow_write=True, allow_command=True)
        print(f"CursorAgent > {result['reply']}\n")


def run_web(host="127.0.0.1", port=8765):
    print(f"Agent Workbench 已启动: http://{host}:{port}")
    print(f"前端目录: {WEB_DIR}")
    ThreadingHTTPServer((host, port), AgentWorkbenchHandler).serve_forever()


def main():
    if "--cli" in sys.argv:
        run_cli()
        return
    host = "127.0.0.1"
    port = 8765
    if "--host" in sys.argv:
        host = sys.argv[sys.argv.index("--host") + 1]
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    run_web(host, port)


if __name__ == "__main__":
    main()
