import hashlib
import json
import logging
import os
import sqlite3
import sys
import traceback
import warnings
from datetime import datetime
from pathlib import Path

# ── 在任何第三方库 import 之前，全面压制 HuggingFace / safetensors 噪音 ──
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("SAFETENSORS_FAST_GPU", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

import io as _io

def _quiet_imports():
    """在静默环境中完成所有会产生噪音的 import 和模块初始化。"""
    _real_stderr = sys.stderr
    sys.stderr = _io.StringIO()
    _prev_log_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore")
    try:
        import psutil as _psutil
        from langchain.agents import create_agent as _create_agent
        from langchain_core.documents import Document as _Document
        from langchain_core.tools import tool as _tool
        from langchain_openai import ChatOpenAI as _ChatOpenAI
        from langchain_community.tools import DuckDuckGoSearchRun as _DuckDuckGoSearchRun
        from langchain_community.vectorstores import FAISS as _FAISS
        from langchain_experimental.utilities import PythonREPL as _PythonREPL
        from langgraph.checkpoint.sqlite import SqliteSaver as _SqliteSaver
        try:
            from langchain_huggingface import HuggingFaceEmbeddings as _HFE
            _dep = False
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings as _HFE
            _dep = True
        return (
            _psutil, _create_agent, _Document, _tool, _ChatOpenAI,
            _DuckDuckGoSearchRun, _FAISS, _PythonREPL, _SqliteSaver,
            _HFE, _dep,
        )
    finally:
        sys.stderr = _real_stderr
        logging.disable(_prev_log_level)

(
    psutil, create_agent, Document, tool, ChatOpenAI,
    DuckDuckGoSearchRun, FAISS, PythonREPL, SqliteSaver,
    HuggingFaceEmbeddings, USING_DEPRECATED_HF_EMBEDDINGS,
) = _quiet_imports()


if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except OSError:
        pass


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
KNOWLEDGE_DIR = BASE_DIR / "knowledge_db"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"
CHECKPOINT_DB = CHECKPOINT_DIR / "memory.db"
VECTOR_INDEX_DIR = BASE_DIR / "vector_index"
VECTOR_MANIFEST = VECTOR_INDEX_DIR / "manifest.json"

EMBEDDING_MODEL_DEFAULT = "sentence-transformers/all-MiniLM-L6-v2"
CHAT_MODEL_DEFAULT = "GLM-5"
CHAT_TEMPERATURE_DEFAULT = 0.5
CHAT_THREAD_ID_DEFAULT = "global_user_session_v3"
KNOWLEDGE_TOP_K_DEFAULT = 3
ENABLE_PYTHON_REPL_DEFAULT = False
AGENT_WORKSPACE_ROOT_DEFAULT = ""
REQUIRE_CONFIRM_ON_WRITE_DEFAULT = True
REQUIRE_CONFIRM_ON_COMMAND_DEFAULT = True
ALLOW_DELETE_PATH_DEFAULT = False
COMMAND_TIMEOUT_SECONDS_DEFAULT = 30

SEMANTIC_RETRIEVER = None
RAW_KNOWLEDGE_DOCS = []
DUCKDUCKGO = DuckDuckGoSearchRun()
PYTHON_REPL = PythonREPL()


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a simple .env file without extra dependencies."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


for candidate in (PROJECT_ROOT / ".env", BASE_DIR / ".env"):
    load_env_file(candidate)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL") or "https://api.edgefn.net/v1"
EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", EMBEDDING_MODEL_DEFAULT)
CHAT_MODEL = os.getenv("CHAT_MODEL", CHAT_MODEL_DEFAULT)
CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", str(CHAT_TEMPERATURE_DEFAULT)))
CHAT_THREAD_ID = os.getenv("CHAT_THREAD_ID", CHAT_THREAD_ID_DEFAULT)
KNOWLEDGE_TOP_K = int(os.getenv("KNOWLEDGE_TOP_K", str(KNOWLEDGE_TOP_K_DEFAULT)))
ENABLE_PYTHON_REPL = os.getenv("ENABLE_PYTHON_REPL", "1" if ENABLE_PYTHON_REPL_DEFAULT else "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AGENT_WORKSPACE_ROOT = os.getenv("AGENT_WORKSPACE_ROOT", AGENT_WORKSPACE_ROOT_DEFAULT) or str(PROJECT_ROOT)
REQUIRE_CONFIRM_ON_WRITE = os.getenv("REQUIRE_CONFIRM_ON_WRITE", "1" if REQUIRE_CONFIRM_ON_WRITE_DEFAULT else "0").lower() in {"1", "true", "yes", "on"}
REQUIRE_CONFIRM_ON_COMMAND = os.getenv("REQUIRE_CONFIRM_ON_COMMAND", "1" if REQUIRE_CONFIRM_ON_COMMAND_DEFAULT else "0").lower() in {"1", "true", "yes", "on"}
ALLOW_DELETE_PATH = os.getenv("ALLOW_DELETE_PATH", "1" if ALLOW_DELETE_PATH_DEFAULT else "0").lower() in {"1", "true", "yes", "on"}
COMMAND_TIMEOUT_SECONDS = int(os.getenv("COMMAND_TIMEOUT_SECONDS", str(COMMAND_TIMEOUT_SECONDS_DEFAULT)) or str(COMMAND_TIMEOUT_SECONDS_DEFAULT))


def ensure_directories() -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    VECTOR_INDEX_DIR.mkdir(parents=True, exist_ok=True)


def read_text_file(path: Path) -> str:
    """Read a text file with common Windows encodings."""
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Unable to decode {path}")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    """Split text into small overlapping chunks for retrieval."""
    normalized = text.strip()
    if not normalized:
        return []

    chunks = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(normalized):
        chunk = normalized[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def load_knowledge_documents() -> list[Document]:
    """Load knowledge files explicitly so failures are visible."""
    documents = []
    for file_path in sorted(KNOWLEDGE_DIR.glob("*.txt")):
        try:
            content = read_text_file(file_path)
            documents.append(
                Document(
                    page_content=content,
                    metadata={"source": str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")},
                )
            )
        except Exception as exc:
            print(f"Knowledge file load error: {file_path} -> {exc}")
            traceback.print_exc()

    if documents:
        return documents

    return [
        Document(
            page_content="初始引导：这是一个空的知识库，请向 knowledge_db 目录添加 UTF-8 编码的文本文件。",
            metadata={"source": "system/seed"},
        )
    ]


def build_chunked_documents(documents: list[Document]) -> list[Document]:
    chunked = []
    for document in documents:
        for index, chunk in enumerate(chunk_text(document.page_content), start=1):
            chunked.append(
                Document(
                    page_content=chunk,
                    metadata={**document.metadata, "chunk": index},
                )
            )
    return chunked or documents


def build_knowledge_signature(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for file_path in files:
        digest.update(str(file_path.relative_to(PROJECT_ROOT)).encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def build_embeddings():
    _real_stderr = sys.stderr
    sys.stderr = _io.StringIO()
    _prev = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    finally:
        sys.stderr = _real_stderr
        logging.disable(_prev)


def load_or_build_semantic_retriever(documents: list[Document]):
    files = sorted(KNOWLEDGE_DIR.glob("*.txt"))
    if not files:
        return None

    signature = build_knowledge_signature(files)
    manifest = None
    if VECTOR_MANIFEST.exists():
        try:
            manifest = json.loads(VECTOR_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = None

    embeddings = build_embeddings()

    if manifest and manifest.get("signature") == signature and manifest.get("embedding_model") == EMBEDDING_MODEL:
        try:
            vectorstore = FAISS.load_local(
                str(VECTOR_INDEX_DIR),
                embeddings,
                allow_dangerous_deserialization=True,
            )
            print("Knowledge index: loaded cached FAISS index.")
            return vectorstore.as_retriever(search_kwargs={"k": KNOWLEDGE_TOP_K})
        except Exception as exc:
            print(f"Knowledge index cache invalid, rebuilding. Reason: {exc}")

    chunked_documents = build_chunked_documents(documents)
    vectorstore = FAISS.from_documents(chunked_documents, embeddings)
    vectorstore.save_local(str(VECTOR_INDEX_DIR))
    VECTOR_MANIFEST.write_text(
        json.dumps(
            {
                "signature": signature,
                "embedding_model": EMBEDDING_MODEL,
                "file_count": len(files),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Knowledge index: rebuilt and cached locally.")
    return vectorstore.as_retriever(search_kwargs={"k": KNOWLEDGE_TOP_K})


def tokenize_query(query: str) -> list[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in query)
    tokens = [token for token in cleaned.split() if len(token) > 1]
    compact = "".join(ch.lower() for ch in query if ch.isalnum())
    if compact:
        tokens.append(compact)
    if any("\u4e00" <= ch <= "\u9fff" for ch in compact):
        tokens.extend(compact[i : i + 2] for i in range(max(len(compact) - 1, 0)))
    return list(dict.fromkeys(tokens))


def keyword_search(query: str, documents: list[Document], top_k: int = 3) -> list[Document]:
    terms = tokenize_query(query)
    if not terms:
        return documents[:top_k]

    scored = []
    for document in documents:
        content = document.page_content.lower()
        score = sum(content.count(term) for term in terms)
        if query.lower() in content:
            score += 3
        if score > 0:
            scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [document for _, document in scored[:top_k]] or documents[:top_k]


def format_documents(documents: list[Document]) -> str:
    return "\n\n".join(
        f"[{document.metadata.get('source', '本地知识库')}]\n{document.page_content.strip()}"
        for document in documents
    )


def search_local_knowledge(query: str) -> str:
    if SEMANTIC_RETRIEVER is not None:
        try:
            documents = SEMANTIC_RETRIEVER.invoke(query)
            if documents:
                return format_documents(documents)
        except Exception as exc:
            print(f"Semantic retrieval failed, fallback to keyword search: {exc}")

    if not RAW_KNOWLEDGE_DOCS:
        return "知识库当前为空，请先在 knowledge_db 目录中添加文本文件。"

    documents = keyword_search(query, RAW_KNOWLEDGE_DOCS, top_k=KNOWLEDGE_TOP_K)
    return format_documents(documents)


def get_system_drive() -> str:
    system_drive = os.environ.get("SystemDrive", "C:")
    return f"{system_drive}\\"


def normalize_message_content(content) -> str:
    if isinstance(content, str):
        raw = content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        raw = "\n".join(part for part in parts if part)
    else:
        raw = str(content)
    # 去除重复：1) 整段前后两半相同 2) 连续重复行
    lines = raw.splitlines()
    n = len(lines)
    if n >= 4 and n % 2 == 0:
        mid = n // 2
        if lines[:mid] == lines[mid:]:
            lines = lines[:mid]
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return "\n".join(deduped)


def initialize_knowledge_engine() -> None:
    global RAW_KNOWLEDGE_DOCS, SEMANTIC_RETRIEVER

    RAW_KNOWLEDGE_DOCS = load_knowledge_documents()
    try:
        _real_stderr = sys.stderr
        sys.stderr = _io.StringIO()
        _prev = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                SEMANTIC_RETRIEVER = load_or_build_semantic_retriever(RAW_KNOWLEDGE_DOCS)
        finally:
            sys.stderr = _real_stderr
            logging.disable(_prev)
        if SEMANTIC_RETRIEVER is None:
            print("  -> Knowledge engine: keyword fallback mode.")
        else:
            print("  -> Knowledge engine: semantic retrieval ready.")
    except Exception as exc:
        SEMANTIC_RETRIEVER = None
        print(f"  -> Knowledge engine: keyword fallback. ({exc})")


@tool
def vector_search(query: str) -> str:
    """搜索本地知识库，用于公司制度、人员、地址、项目和内部资料问题。"""
    return search_local_knowledge(query)


@tool
def web_search(query: str) -> str:
    """联网搜索公开信息，用于天气、新闻、实时资讯和外部事实查询。"""
    try:
        return DUCKDUCKGO.run(query)
    except Exception as exc:
        return f"联网搜索暂时不可用: {exc}"


@tool
def get_system_info(request: str = "status") -> str:
    """读取当前电脑系统资源状态，例如 CPU、内存和磁盘占用。"""
    cpu = psutil.cpu_percent(interval=0.2)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage(get_system_drive()).percent
    return (
        f"系统资源报告: CPU {cpu}% | 内存 {memory}% | 磁盘 {disk}% | "
        f"时间 {datetime.now().strftime('%H:%M:%S')}"
    )


@tool
def execute_python_code(code: str) -> str:
    """执行受信任的 Python 代码，用于数学计算或一次性数据处理。"""
    if not ENABLE_PYTHON_REPL:
        return "Python 执行工具默认关闭。若确认当前环境可信，可设置 ENABLE_PYTHON_REPL=1 后重启。"
    try:
        return PYTHON_REPL.run(code)
    except Exception as exc:
        return f"代码执行错误: {exc}"


# 保证同目录 agent_tools 可被导入（从项目根或 ai/cn 运行均可）
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
import agent_tools as _agent_tools

ASSISTANT_TOOLS = [vector_search, web_search, get_system_info, execute_python_code]
TOOLS = ASSISTANT_TOOLS + _agent_tools.DEV_TOOLS


def build_agent():
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "未检测到 OPENAI_API_KEY。请在系统环境变量、项目根目录 .env 或 ai/cn/.env 中配置后重试。"
        )

    workspace_root = Path(AGENT_WORKSPACE_ROOT).resolve() if AGENT_WORKSPACE_ROOT else PROJECT_ROOT
    _agent_tools.AGENT_STATE.clear()
    _agent_tools.AGENT_STATE.update({
        "workspace_root": str(workspace_root),
        "agent_cwd": str(workspace_root),
        "require_confirm_on_write": REQUIRE_CONFIRM_ON_WRITE,
        "require_confirm_on_command": REQUIRE_CONFIRM_ON_COMMAND,
        "allow_delete_path": ALLOW_DELETE_PATH,
        "command_timeout_seconds": COMMAND_TIMEOUT_SECONDS,
    })

    connection = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    memory = SqliteSaver(connection)
    llm = ChatOpenAI(
        model=CHAT_MODEL,
        temperature=CHAT_TEMPERATURE,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
    )
    system_prompt = (
        "你是统一数字助理：兼具企业知识问答与开发助手能力。\n\n"
        "【企业/知识类】\n"
        "- 公司制度、人员、办公地址、内部项目、内部资料：优先使用 vector_search。\n"
        "- 天气、新闻、实时资讯、外部事实：使用 web_search。\n"
        "- 查看本机 CPU/内存/磁盘：使用 get_system_info。\n"
        "- 数学计算或一次性数据处理：在可用时使用 execute_python_code。\n\n"
        "【开发/代码类】\n"
        "- 查代码位置、函数与变量引用：使用 search_code。\n"
        "- 按文件名找文件路径：使用 search_file。\n"
        "- 读文件内容并确定行号：使用 read_file_with_lines；修改前必须先读再改。\n"
        "- 精确修改某几行代码：使用 replace_lines，不要整文件覆写。\n"
        "- 切换当前工作目录：使用 change_directory。\n"
        "- 执行 PowerShell 命令：使用 execute_command。\n"
        "- 创建新文件：使用 create_file。\n"
        "- 删除文件或目录：仅在用户明确要求且工具可用时使用 delete_path。\n\n"
        "【通用】\n"
        "- 始终用中文回复，结论简洁、依据必要。\n"
        "- 修改代码前先 read_file_with_lines 再 replace_lines；不要猜行号。\n"
        "- 当前工作区根目录由系统限制，路径均相对于当前工作目录。"
    )
    agent = create_agent(
        model=llm,
        tools=TOOLS,
        checkpointer=memory,
        system_prompt=system_prompt,
    )
    return connection, agent


def print_banner() -> None:
    print("=" * 60)
    print("  Unified Agent [v2026.4]")
    print("  Loading...")


def print_ready_banner() -> None:
    print("=" * 60)
    print("  System Online!")
    print("  知识库 | 联网搜索 | 系统监控 | 代码开发 | 持久记忆")
    print("  写操作需人工确认 | 输入 exit 退出")
    print("-" * 60)
    print("  快捷菜单:")
    print("    1 → 我公司的福利有哪些？")
    print("    2 → 今天北京天气？")
    print("    3 → 看看我电脑状态？")
    print("    4 → 我刚才问了你什么？")
    print("    5 → 搜索项目里包含 def main 的代码")
    print("    6 → 退出")
    print("-" * 60)


def main() -> None:
    ensure_directories()
    print_banner()
    initialize_knowledge_engine()

    connection = None
    try:
        connection, agent = build_agent()
    except Exception as exc:
        print(f"Startup error: {exc}")
        return

    print_ready_banner()

    config = {"configurable": {"thread_id": CHAT_THREAD_ID}}

    menu_shortcuts = {
        "1": "我公司的福利有哪些？",
        "2": "今天北京天气？",
        "3": "看看我电脑状态？",
        "4": "我刚才问了你什么？",
        "5": "搜索项目里包含 def main 的代码",
        "6": "退出",
    }
    try:
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                print("  请输入问题，或输入 1–6 选择上方菜单项。")
                continue
            if user_input.lower() in {"exit", "退出", "quit"}:
                print("Closing system and saving checkpoints... Bye!")
                break
            if user_input in menu_shortcuts:
                shortcut = menu_shortcuts[user_input]
                if shortcut == "退出":
                    print("Closing system and saving checkpoints... Bye!")
                    break
                user_input = shortcut
                print(f"(菜单 {user_input})")

            print("\nAI Thinking...")
            try:
                response = agent.invoke(
                    {"messages": [{"role": "user", "content": user_input}]},
                    config=config,
                )
                messages = response["messages"]
                final_message = messages[-1]
                content = normalize_message_content(getattr(final_message, "content", final_message))
                # 本轮若调用了工具，在回复下方简要列出（只统计这次提问之后的调用）
                tool_names: list[str] = []
                last_human_idx = None
                for idx in range(len(messages) - 1, -1, -1):
                    m = messages[idx]
                    if getattr(m, "type", None) == "human":
                        last_human_idx = idx
                        break
                recent_messages = messages[last_human_idx + 1 :] if last_human_idx is not None else messages
                for m in recent_messages:
                    if getattr(m, "type", None) == "tool" and getattr(m, "name", None):
                        tool_names.append(m.name)
                    elif hasattr(m, "tool_calls") and m.tool_calls:
                        for tc in m.tool_calls:
                            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                            if name:
                                tool_names.append(name)
                print()
                print(content)
                footer_parts = []
                if tool_names:
                    footer_parts.append("工具: " + ", ".join(dict.fromkeys(tool_names)))
                footer_parts.append(datetime.now().strftime("%H:%M:%S"))
                print(f"  [{' | '.join(footer_parts)}]")
                print("─" * 50)
            except Exception as exc:
                print(f"\nExecution error: {exc}")
                message = str(exc).lower()
                if "rate_limit" in message:
                    print("Tip: API rate limit reached. Please wait and retry.")
                elif "parsing" in message:
                    print("Tip: Model output format was unstable. Please retry once.")
    except KeyboardInterrupt:
        print("\n\nExecution interrupted.")
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()