"""
CursorAgent - 类似 Cursor 的高级终端智能体
功能特点:
1. 🔍 全局代码搜索 (Search Code by Keyword)
2. ✂️ 代码行级精准修改 (Replace Lines in File) 
3. 💻 终端完全接管 (Execute Command)
4. 📝 交互式确认保护 (Human-in-the-loop) - 修改和执行命令需人工确认
5. 📂 目录与文件系统操作
"""

import os
import sys
import ctypes
import shutil
import json
import subprocess
from openai import OpenAI

# 终端色彩
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"
C_RESET = "\033[0m"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    print(f"{C_RED}⚠️ 警告：当前不是管理员权限！如果您要求我执行系统级别命令，可能会被系统拒绝（Permission Denied）。建议以管理员身份运行我。{C_RESET}\n")

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="password-123",
)

model = "claude-sonnet-4-5"

agent_cwd = os.path.abspath('.')

def truncate_text(text: str, max_len: int = 5000) -> str:
    if len(text) > max_len:
        return text[:max_len] + f"\n... (已截断尾部的 {len(text)-max_len} 个字符)"
    return text

def ask_user_confirmation(action_desc: str) -> bool:
    """拦截高危操作，等待用户确认"""
    print(f"\n{C_MAGENTA}⚠️ [安全拦截] AI 请求执行以下操作:{C_RESET}")
    print(f"{C_MAGENTA}   {action_desc}{C_RESET}")
    while True:
        ans = input(f"{C_MAGENTA}   允许执行吗？(y/n) [默认y]: {C_RESET}").strip().lower()
        if ans in ('y', 'yes', ''):
            return True
        elif ans in ('n', 'no'):
            return False

# ─────────────────────────────────────────────
#  💡 Cursor 特色高级工具：代码行级替换、全局搜索
# ─────────────────────────────────────────────

def search_code(keyword: str, path: str = ".") -> str:
    """在指定目录中按关键字搜索代码文件内容"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    results = []
    
    # 支持的常见代码格式
    valid_exts = ('.py', '.js', '.ts', '.html', '.css', '.json', '.md', '.txt', '.java', '.c', '.cpp', '.h')
    
    try:
        for root, _, files in os.walk(target):
            # 排除特定目录
            if any(exclude in root for exclude in ('.git', '__pycache__', 'node_modules', 'venv', '.idea')):
                continue
                
            for file in files:
                if not file.endswith(valid_exts):
                    continue
                    
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        
                    for i, line in enumerate(lines):
                        if keyword.lower() in line.lower():
                            rel_path = os.path.relpath(filepath, agent_cwd)
                            results.append(f"{rel_path}:{i+1} -> {line.strip()}")
                            if len(results) > 50: # 最多返回50条
                                results.append("... (搜索结果过多，已截断)")
                                return "\n".join(results)
                except Exception:
                    pass
                    
        if not results:
            return f"❌ 未找到包含关键字 '{keyword}' 的代码片段。"
        
        return "🔍 搜索结果:\n" + "\n".join(results)
    except Exception as e:
        return f"❌ 搜索代码失败: {e}"

def search_file(filename: str, path: str = ".") -> str:
    """在指定目录中按文件名查找文件，返回文件的绝对路径"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    results = []
    
    try:
        raw_name = filename.lower()
        for root, _, files in os.walk(target):
            # 排除特定目录加速搜索
            if any(exclude in root for exclude in ('.git', '__pycache__', 'node_modules', 'venv', '.idea', 'AppData', 'Windows')):
                continue
                
            for file in files:
                if raw_name in file.lower():
                    results.append(os.path.abspath(os.path.join(root, file)))
                    if len(results) > 20:
                        results.append("... (搜索结果过多，已截断 20 条)")
                        return "\n".join(results)
                        
        if not results:
            return f"❌ 未找到包含关键字 '{filename}' 的文件。"
        
        return "🔍 文件查找结果:\n" + "\n".join(results)
    except Exception as e:
        return f"❌ 查找文件失败: {e}"

def replace_lines(path: str, start_line: int, end_line: int, new_content: str) -> str:
    """
    精确替换文件中的特定行范围（行号从1开始，包含 start_line 和 end_line）。
    用于修复 Bug、修改函数，而不需要覆盖整个文件！
    """
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    
    # 发起拦截确认
    if not ask_user_confirmation(f"修改文件 {path} (第 {start_line} 到 {end_line} 行)"):
        return "❌ 动作被用户拒绝。"

    try:
        if not os.path.exists(target):
            return f"❌ 文件不存在: {target}"
            
        with open(target, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return f"❌ 无效的行号范围: 1~{len(lines)}"
            
        # 截取新旧内容，处理换行符
        prefix = lines[:start_line - 1]
        suffix = lines[end_line:]
        
        # 确保新内容以换行符结尾
        if new_content and not new_content.endswith('\n'):
            new_content += '\n'
            
        new_lines = prefix + [new_content] + suffix
        
        with open(target, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
        return f"✅ 精确修改成功: {target} [{start_line}-{end_line} 行已更新]"
    except Exception as e:
        return f"❌ 修改代码失败: {e}"


# ─────────────────────────────────────────────
#  传统文件与终端工具
# ─────────────────────────────────────────────

def read_file_with_lines(path: str) -> str:
    """带行号读取文件内容，方便接下来使用 replace_lines 进行精准修改"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    try:
        with open(target, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        output = []
        for i, line in enumerate(lines):
            output.append(f"{i+1:4d} | {line.rstrip()}")
            
        content_with_lines = "\n".join(output)
        return f"📄 {target} (带行号):\n{truncate_text(content_with_lines, 6000)}"
    except Exception as e:
        return f"❌ 读取失败: {e}"

def execute_command(command: str) -> str:
    """执行终端命令"""
    global agent_cwd
    if not ask_user_confirmation(f"执行终端命令 > {command}"):
        return "❌ 动作被用户拒绝。"
        
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, errors='replace', timeout=30, cwd=agent_cwd
        )
        out = truncate_text(result.stdout.strip())
        err = truncate_text(result.stderr.strip())
        if result.returncode == 0:
            return f"✅ (exit 0)\n{out}" if out else "✅ 成功 (无输出)"
        else:
            return f"❌ 报错 (exit {result.returncode}):\n{err}\n{out}"
    except Exception as e:
        return f"❌ 终端异常: {e}"

def change_directory(path: str) -> str:
    global agent_cwd
    try:
        target = os.path.abspath(os.path.join(agent_cwd, path))
        if os.path.isdir(target):
            agent_cwd = target
            return f"✅ 已切换工作目录至: {agent_cwd}"
        return f"❌ 目录不存在: {target}"
    except Exception as e:
        return f"❌ 切换失败: {e}"

def create_file(path: str, content: str = "") -> str:
    """全新创建文件（完整覆盖）"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    if not ask_user_confirmation(f"创建全新文件: {path}"):
        return "❌ 动作被用户拒绝。"
    try:
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ 已创建文件: {target}"
    except Exception as e:
        return f"❌ 创建失败: {e}"

def delete_path(path: str) -> str:
    """删除文件或文件夹"""
    global agent_cwd
    target = os.path.abspath(os.path.join(agent_cwd, path))
    if not ask_user_confirmation(f"⚠️ 删除路径 (永久): {target}"):
        return "❌ 动作被用户拒绝。"
    try:
        if not os.path.exists(target):
            return f"❌ 路径不存在: {target}"
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        return f"✅ 已删除: {target}"
    except Exception as e:
        return f"❌ 删除失败: {e}"

# 工具注册表
tools = [
     {"type": "function", "function": {"name": "search_code", "description": "全局代码搜索。用于查找函数定义、变量引用等。返回包含关键字的文件路径和行号。", "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}, "path": {"type": "string", "description":"查找范围，默认."}}, "required": ["keyword"]}}},
     {"type": "function", "function": {"name": "replace_lines", "description": "行级精准代码替换！修复Bug或修改函数时，不要覆写整个文件，只需替换指定范围的行号（包含首尾端点）。必须先用 read_file_with_lines 确定行号！", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}, "new_content": {"type": "string", "description": "要替换进来的新代码"}}, "required": ["path", "start_line", "end_line", "new_content"]}}},
     {"type": "function", "function": {"name": "read_file_with_lines", "description": "读取文件内容，每行都会带有行号标记。在修改代码(replace_lines)前必须调用此工具查看行号。不要瞎猜行号！", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
     {"type": "function", "function": {"name": "execute_command", "description": "执行终端 PowerShell 命令（例如运行脚本、安装 pip 库包）。", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
     {"type": "function", "function": {"name": "change_directory", "description": "cd 命令。切换 AI 所处的当前工作目录。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
     {"type": "function", "function": {"name": "create_file", "description": "创建一个全新的文件。不要用这个工具来修改已有的大文件！", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
     {"type": "function", "function": {"name": "delete_path", "description": "删除文件或文件夹。永远用这个工具删文件，绝对不要去终端用 del。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
     {"type": "function", "function": {"name": "search_file", "description": "通过文件名查找文件的绝对路径，不要去终端用 Get-ChildItem，直接用这个 Python 工具高速查找。", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "path": {"type": "string", "description":"查找范围目录，默认."}}, "required": ["filename"]}}},
]

tool_map = {
    "search_code": search_code,
    "search_file": search_file,
    "replace_lines": replace_lines,
    "read_file_with_lines": read_file_with_lines,
    "execute_command": execute_command,
    "change_directory": change_directory,
    "create_file": create_file,
    "delete_path": delete_path,
}

def run_tool_calls(tool_calls):
    results = []
    for tc in tool_calls:
        name = tc.function.name
        args_str = tc.function.arguments
        
        # 精简参数显示
        display_args = args_str if len(args_str) < 60 else args_str[:60] + "..."
        print(f"  {C_YELLOW}[工具请求] ⚙️ {name}{C_RESET} ({display_args})")
        
        try:
            args = json.loads(args_str)
        except Exception:
            results.append({"tool_call_id": tc.id, "role": "tool", "content": "参数 JSON 解析失败"})
            continue
            
        func = tool_map.get(name)
        if func:
            result = func(**args)
            if not result.startswith("❌ 动作被用户拒绝"):
                print(f"  {C_GREEN}-> {result[:100]}...\n{C_RESET}")
            else:
                print(f"  {C_RED}-> {result}\n{C_RESET}")
            results.append({"tool_call_id": tc.id, "role": "tool", "content": result})
        else:
            results.append({"tool_call_id": tc.id, "role": "tool", "content": "❌ 未知工具"})
    return results

# ─────────────────────────────────────────────
#  程序主入口
# ─────────────────────────────────────────────

os.system('cls' if os.name == 'nt' else 'clear')
print(f"{C_CYAN}=" * 65)
print("  🚀 CursorAgent - 高级版终端智能体")
print("  包含全局检索、代码行级 Diff 修改、交互式安全确认功能。")
print(f"  📂 初始目录: {agent_cwd}")
print(f"{C_CYAN}=" * 65 + C_RESET + "\n")

system_prompt = f"""你是一个顶尖的开发助手 CursorAgent。
你可以在本地终端自由穿梭、修改代码、执行命令和测试。
工作原则：
1. 【修改代码】: 修改现有文件必须先 `read_file_with_lines` 查看最新内容和确定行号，再 `replace_lines` 局部修改。
2. 【排错闭环】: `execute_command` 运行报错时，请分析错误、修改代码，并重新运行直至成功。
3. 【Windows PowerShell 避坑指南⚠️】: 
   - 查找环境变量/命令位置时，必须使用 `where.exe xxx` 或 `Get-Command xxx`，绝对不要用 `where xxx`。
   - 寻找文件时，绝对不要在根目录 (C:\\, D:\\) 直接使用 `Get-ChildItem -Recurse`。
   - **拼接任何路径时，必须添加双引号** (如 `"C:\\Program Files\\xxx"`)，否则含有空格的路径会导致 PowerShell 解析参数失败。
4. 【文件删除强制规则】: 如果要删除文件或文件夹，**绝对不要**用 `execute_command` 里的 `del` 或 `rm`！必须使用提供的 `delete_path` 工具，它能在 Python 底层安全处理各种带有空格的绝对路径。
5. 【⚠️防死锁禁令⚠️】: 如果用户要求你编写爬虫、测试脚本或任何用于终端执行的程序，**写成的脚本代码必须是直接一溜烟跑完并自动 print 输出结果的程序。绝对禁止使用 `input()` 请求用户交互，绝对禁止写出会卡死终端的 `while True` 交互菜单！** 因为你在后台通过 `execute_command` 调用这个程序时你无法打字输入，这会导致你的进程彻底永久死锁卡死！
当前工作目录: {agent_cwd}
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
        for step in range(15): # 强大的自我修复流水线上限15步
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
                print(f"{C_CYAN}🤖 CursorAgent: {C_RESET}{msg.content}\n")

            if msg.tool_calls:
                tool_results = run_tool_calls(msg.tool_calls)
                history.extend(tool_results)
            else:
                break
                
    except Exception as e:
        print(f"\n{C_RED}[系统错误] {e}{C_RESET}\n")
        history.pop()

