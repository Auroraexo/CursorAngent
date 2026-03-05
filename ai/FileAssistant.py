"""
AI 终端全能智能体 (Agent) - V2 优化版
新增:
- 工作目录状态保持 (支持真实的 cd 操作)
- 大文本防爆机制 (截断过长输出)
- ANSI 终端色彩高亮
"""
import os
import sys
import ctypes
import shutil
import json
import subprocess
from openai import OpenAI

C_RED = "\033[91m"
C_RESET = "\033[0m"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    print(f"{C_RED}⚠️ 警告：当前未获取管理员权限！涉及系统底层操作可能会失败。建议以管理员身份打开命令行。{C_RESET}\n")

client = OpenAI(
    base_url="https://api.jiekou.ai/openai",
    api_key="sk_qC61Zova4QrK5o6TQeKvPdpMkI2XSTUK2HXxqZlSCNg",
)

model = "claude-sonnet-4-20250514"

# 颜色代码
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_RESET = "\033[0m"

# 全局工作目录状态
agent_cwd = os.path.abspath('.')

def truncate_text(text: str, max_len: int = 3000) -> str:
    """截断过长的文本，防止撑爆大模型上下文"""
    if len(text) > max_len:
        return text[:max_len] + f"\n... (已截断尾部的 {len(text)-max_len} 个字符)"
    return text

# ─────────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────────

def change_directory(path: str) -> str:
    """更改当前工作目录"""
    global agent_cwd
    try:
        target = os.path.abspath(os.path.join(agent_cwd, path))
        if os.path.isdir(target):
            agent_cwd = target
            return f"✅ 已切换工作目录至: {agent_cwd}"
        return f"❌ 目录不存在: {target}"
    except Exception as e:
        return f"❌ 切换失败: {e}"

def execute_command(command: str) -> str:
    """执行终端命令"""
    global agent_cwd
    try:
        # 在独立的 powershell 中执行，指定 cwd 为当前的 agent_cwd
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            errors='replace',
            timeout=30,
            cwd=agent_cwd
        )
        out = truncate_text(result.stdout.strip())
        err = truncate_text(result.stderr.strip())
        
        if result.returncode == 0:
            return f"✅ (exit 0)\n{out}" if out else "✅ 成功 (无输出)"
        else:
            return f"❌ 报错 (exit {result.returncode}):\n{err}\n{out}"
    except subprocess.TimeoutExpired:
        return "❌ 命令超时 (已终止)"
    except Exception as e:
        return f"❌ 异常: {e}"

def read_file(path: str) -> str:
    """读取文件"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        return f"📄 {target} 内容:\n{truncate_text(content, 4000)}"
    except Exception as e:
        return f"❌ 读取失败: {e}"

def write_file(path: str, content: str = "") -> str:
    """写入文件"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ 已重写文件: {target}"
    except Exception as e:
        return f"❌ 写入失败: {e}"

def delete_path(path: str) -> str:
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        return f"✅ 已删除: {target}"
    except Exception as e:
        return f"❌ 删除失败: {e}"

def list_directory(path: str = ".") -> str:
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    try:
        items = []
        for item in sorted(os.listdir(target)):
            full = os.path.join(target, item)
            tag = "📁" if os.path.isdir(full) else "📄"
            items.append(f"{tag} {item}")
        return f"📂 {target}\n" + "\n".join(items) if items else f"📂 {target} (空)"
    except Exception as e:
        return f"❌ 列出失败: {e}"

tools = [
     {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "类似终端的 cd 操作。更改当前所在的控制台目录。",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "执行终端命令。注意：如果你需要 cd 到别的目录执行，请先调用 change_directory 工具！",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "查看文本文件内容",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "覆盖并写入文件",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_path",
            "description": "删除文件或文件夹",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "查看指定目录下的文件列表",
            "parameters": {"type": "object", "properties": {"path": {"type": "string", "description":"默认为 '.'代表当前目录"}}, "required": []}
        }
    }
]

tool_map = {
    "change_directory": change_directory,
    "execute_command": execute_command,
    "read_file": read_file,
    "write_file": write_file,
    "delete_path": delete_path,
    "list_directory": list_directory,
}

def run_tool_calls(tool_calls):
    results = []
    for tc in tool_calls:
        name = tc.function.name
        args = json.loads(tc.function.arguments)
        print(f"  {C_YELLOW}[调用工具] ⚙️ {name}{C_RESET} ({str(args)[:50]}...)")
        
        func = tool_map.get(name)
        if func:
            result = func(**args)
            print(f"  {C_GREEN}-> {result[:80]}{'...' if len(result)>80 else ''}{C_RESET}")
            results.append({"tool_call_id": tc.id, "role": "tool", "content": result})
        else:
            results.append({"tool_call_id": tc.id, "role": "tool", "content": "❌ unknown tool"})
    return results

# ─────────────────────────────────────────────
#  主循环
# ─────────────────────────────────────────────

os.system('cls' if os.name == 'nt' else 'clear')
print(f"{C_CYAN}=" * 60)
print("  💻 AI 全能终端智能体 (Agent V2) - 带有持久化上下文")
print(f"  📂 初始目录: {agent_cwd}")
print(f"{C_CYAN}=" * 60 + C_RESET + "\n")

system_prompt = f"""你是一个高级的系统终端智能体 (Agent)。你的首要职责是帮助用户在当前终端工作区中解决问题。
1. 当你需要执行诸如 'cd foo' 然后再运行命令的操作时，你必须先调用 change_directory 工具切换状态目录，然后再使用 execute_command 运行命令。
2. 由于 execute_command 不能保存 cd 状态，只有 change_directory 工具能更改你的全局工作目录。
3. 遇到代码问题，先用 read_file 查看，然后 write_file 修改，最后 execute_command 测试。如果有报错，请自动继续修复。
"""
history = [{"role": "system", "content": system_prompt}]

while True:
    print(f"\n{C_CYAN}[{os.path.basename(agent_cwd)}] >{C_RESET}", end=" ")
    try:
        user_input = input().strip()
    except (KeyboardInterrupt, EOFError):
        break

    if not user_input:
        continue
    if user_input.lower() in ("exit", "quit", "退出"):
        break
    if user_input.lower() in ("clear", "清空"):
        history = [{"role": "system", "content": system_prompt}]
        os.system('cls' if os.name == 'nt' else 'clear')
        continue

    history.append({"role": "user", "content": user_input})

    try:
        for step in range(10): # 最多自主思考 10 轮
            response = client.chat.completions.create(
                model=model,
                messages=history,
                tools=tools,
                tool_choice="auto",
                max_tokens=4096,
            )

            msg = response.choices[0].message
            history.append(msg)

            if msg.content:
                print(f"{C_CYAN}🤖 思考/回复: {C_RESET}{msg.content}\n")

            if msg.tool_calls:
                tool_results = run_tool_calls(msg.tool_calls)
                history.extend(tool_results)
            else:
                break
                
    except Exception as e:
        print(f"\n{C_RED}[错误] {e}{C_RESET}\n")
        history.pop()

