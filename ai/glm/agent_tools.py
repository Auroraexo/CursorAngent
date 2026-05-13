"""
开发型 Agent 工具：代码搜索、文件读写、行级修改、目录切换、命令执行。
所有路径限制在 workspace_root 内；高危操作可通过 confirm_action 与环境变量控制。
"""

import os
import shutil
import subprocess
from pathlib import Path

from langchain_core.tools import tool

# 由 chatagent 在 build_agent 前注入
AGENT_STATE: dict = {}


def _workspace_root() -> Path:
    root = AGENT_STATE.get("workspace_root")
    if root is None:
        return Path.cwd()
    return Path(root).resolve()


def _agent_cwd() -> Path:
    cwd = AGENT_STATE.get("agent_cwd")
    if not cwd:
        return _workspace_root()
    p = Path(cwd).resolve()
    root = _workspace_root()
    try:
        p.relative_to(root)
    except ValueError:
        return root
    return p


def _set_agent_cwd(path: Path) -> None:
    AGENT_STATE["agent_cwd"] = str(path.resolve())


def _resolve_path(rel_path: str) -> Path:
    """解析相对路径，限制在 workspace 内，否则抛出 ValueError。"""
    root = _workspace_root()
    cwd = _agent_cwd()
    if not cwd.is_relative_to(root) and cwd != root:
        cwd = root
    target = (cwd / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"路径不允许超出工作区根目录: {root}")
    return target


def _truncate(text: str, max_len: int = 5000) -> str:
    if len(text) > max_len:
        return text[:max_len] + f"\n... (已截断 {len(text) - max_len} 字)"
    return text


_confirmed_actions: set = set()


def confirm_action(description: str) -> bool:
    """高危操作前请求用户确认；若环境变量关闭确认则直接返回 True。
    同一描述在同一会话内只确认一次，避免 Agent 重试时反复弹窗。"""
    is_write = any(kw in description for kw in ("修改", "创建", "删除"))
    is_cmd = any(kw in description for kw in ("命令", "终端"))

    if is_cmd and not AGENT_STATE.get("require_confirm_on_command", True):
        return True
    if is_write and not AGENT_STATE.get("require_confirm_on_write", True):
        return True

    if description in _confirmed_actions:
        return True

    print(f"\n[安全确认] AI 请求执行: {description}")
    while True:
        ans = input("允许执行吗？(y/n) [默认 y]: ").strip().lower()
        if ans in ("y", "yes", ""):
            _confirmed_actions.add(description)
            return True
        if ans in ("n", "no"):
            return False


VALID_CODE_EXTENSIONS = (
    ".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt",
    ".java", ".c", ".cpp", ".h", ".yml", ".yaml", ".xml",
)
EXCLUDE_DIRS = (".git", "__pycache__", "node_modules", "venv", ".idea", "env", "ENV")


@tool
def search_code(keyword: str, path: str = ".") -> str:
    """在指定目录中按关键字搜索代码文件内容，返回 文件路径:行号 -> 内容。用于查找函数定义、变量引用等。"""
    try:
        target = _resolve_path(path)
        if not target.is_dir():
            target = target.parent
    except ValueError as e:
        return str(e)
    results = []
    try:
        for root, _, files in os.walk(target):
            if any(ex in root for ex in EXCLUDE_DIRS):
                continue
            for f in files:
                if not f.endswith(VALID_CODE_EXTENSIONS):
                    continue
                filepath = Path(root) / f
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.splitlines(), start=1):
                        if keyword.lower() in line.lower():
                            rel = filepath.relative_to(_agent_cwd())
                            results.append(f"{rel}:{i} -> {line.strip()}")
                            if len(results) >= 50:
                                results.append("... (已截断)")
                                return "\n".join(results)
                except Exception:
                    pass
        if not results:
            return f"未找到包含 '{keyword}' 的代码。"
        return "搜索结果:\n" + "\n".join(results)
    except Exception as e:
        return f"搜索失败: {e}"


@tool
def search_file(filename: str, path: str = ".") -> str:
    """按文件名或部分文件名查找文件，返回匹配的绝对路径列表。"""
    try:
        target = _resolve_path(path)
        if not target.is_dir():
            target = target.parent
    except ValueError as e:
        return str(e)
    results = []
    try:
        raw = filename.lower()
        for root, _, files in os.walk(target):
            if any(ex in root for ex in EXCLUDE_DIRS):
                continue
            for f in files:
                if raw in f.lower():
                    results.append(str((Path(root) / f).resolve()))
                    if len(results) >= 20:
                        results.append("... (已截断)")
                        return "\n".join(results)
        if not results:
            return f"未找到包含 '{filename}' 的文件。"
        return "文件查找结果:\n" + "\n".join(results)
    except Exception as e:
        return f"查找失败: {e}"


@tool
def read_file_with_lines(path: str) -> str:
    """带行号读取文件内容。在调用 replace_lines 修改代码前必须先调用此工具确定行号。"""
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return str(e)
    try:
        if not target.is_file():
            return f"不是文件或不存在: {target}"
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        out = [f"{i:4d} | {line}" for i, line in enumerate(lines, start=1)]
        return f"{target} (带行号):\n" + _truncate("\n".join(out), 6000)
    except Exception as e:
        return f"读取失败: {e}"


@tool
def replace_lines(path: str, start_line: int, end_line: int, new_content: str) -> str:
    """精确替换文件中指定行范围（行号从 1 开始，含首尾）。修改前请先用 read_file_with_lines 确认行号。"""
    if not confirm_action(f"修改文件 {path} 第 {start_line}-{end_line} 行"):
        return "操作已取消。"
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return str(e)
    try:
        if not target.exists():
            return f"文件不存在: {target}"
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return f"无效行号范围，文件共 {len(lines)} 行。"
        prefix = lines[: start_line - 1]
        suffix = lines[end_line:]
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        new_lines = prefix + [new_content] + suffix
        target.write_text("".join(new_lines), encoding="utf-8")
        return f"已修改 {target} 第 {start_line}-{end_line} 行。"
    except Exception as e:
        return f"修改失败: {e}"


@tool
def change_directory(path: str) -> str:
    """切换当前工作目录，后续相对路径均基于此目录。"""
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return str(e)
    try:
        if target.is_dir():
            _set_agent_cwd(target)
            return f"当前目录: {target}"
        return f"目录不存在: {target}"
    except Exception as e:
        return f"切换失败: {e}"


@tool
def execute_command(command: str) -> str:
    """在当前工作目录下执行 PowerShell 命令（如运行脚本、安装包）。执行前需确认。"""
    if not confirm_action(f"执行终端命令: {command}"):
        return "操作已取消。"
    timeout = AGENT_STATE.get("command_timeout_seconds", 30)
    cwd = _agent_cwd()
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )
        out = _truncate(result.stdout.strip())
        err = _truncate(result.stderr.strip())
        if result.returncode == 0:
            return f"成功 (exit 0):\n{out}" if out else "成功 (无输出)"
        return f"退出码 {result.returncode}:\n{err}\n{out}"
    except subprocess.TimeoutExpired:
        return f"命令超时 ({timeout}s)。"
    except Exception as e:
        return f"执行异常: {e}"


@tool
def create_file(path: str, content: str = "") -> str:
    """创建新文件（会覆盖已存在的同名文件）。创建前需确认。"""
    if not confirm_action(f"创建文件: {path}"):
        return "操作已取消。"
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return str(e)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"已创建: {target}"
    except Exception as e:
        return f"创建失败: {e}"


@tool
def delete_path(path: str) -> str:
    """删除文件或目录（不可恢复）。若未开启 ALLOW_DELETE_PATH 则不可用。"""
    if not AGENT_STATE.get("allow_delete_path", False):
        return "删除功能已禁用。如需启用，请设置 ALLOW_DELETE_PATH=1 并重启。"
    if not confirm_action(f"删除 (永久): {path}"):
        return "操作已取消。"
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return str(e)
    try:
        if not target.exists():
            return f"路径不存在: {target}"
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return f"已删除: {target}"
    except Exception as e:
        return f"删除失败: {e}"


DEV_TOOLS = [
    search_code,
    search_file,
    read_file_with_lines,
    replace_lines,
    change_directory,
    execute_command,
    create_file,
    delete_path,
]
