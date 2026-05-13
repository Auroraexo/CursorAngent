# LangChain 统一 Agent（企业 + 开发）说明

主入口：**`ai/cn/chatagent.py`**。可直接运行的中文命令行 Agent，同时具备企业知识问答与开发助手能力。

## 1. 能力概览

### 企业助手
- **本地知识库 RAG**：`knowledge_db/*.txt`，语义检索 + 关键词兜底
- **联网搜索**：天气、新闻、实时资讯（DuckDuckGo）
- **系统资源**：CPU / 内存 / 磁盘
- **SQLite 持久化记忆**：跨重启会话
- **Python 执行**：可选，默认关闭（`ENABLE_PYTHON_REPL=0`）

### 开发助手
- **search_code**：按关键字搜索代码
- **search_file**：按文件名查找文件路径
- **read_file_with_lines**：带行号读文件（修改前必用）
- **replace_lines**：精确替换指定行范围
- **change_directory**：切换当前工作目录
- **execute_command**：执行 PowerShell 命令（需确认）
- **create_file**：创建文件（需确认）
- **delete_path**：删除文件/目录（默认关闭，需 `ALLOW_DELETE_PATH=1` 且确认）

### 安全
- 文件与命令写操作默认需**人工确认**（`REQUIRE_CONFIRM_ON_WRITE=1`、`REQUIRE_CONFIRM_ON_COMMAND=1`）
- 删除功能默认关闭（`ALLOW_DELETE_PATH=0`）
- 所有路径限制在工作区根目录内（`AGENT_WORKSPACE_ROOT`，默认项目根）

## 2. 目录与入口

| 路径 | 说明 |
|------|------|
| `ai/cn/chatagent.py` | 主程序入口 |
| `ai/cn/agent_tools.py` | 开发型工具（代码/文件/命令） |
| `ai/cn/knowledge_db/` | 本地知识库文本 |
| `ai/cn/checkpoints/memory.db` | SQLite 会话记忆 |
| `ai/cn/vector_index/` | FAISS 索引缓存 |
| `ai/cn/.env.example` | 环境变量示例 |

## 3. 环境变量

最少配置：

```env
OPENAI_API_KEY=your_api_key_here
```

常用与安全相关：

```env
OPENAI_API_BASE=https://api.edgefn.net/v1
CHAT_MODEL=GLM-5
CHAT_TEMPERATURE=0.5
CHAT_THREAD_ID=global_user_session_v3
HF_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
KNOWLEDGE_TOP_K=3
ENABLE_PYTHON_REPL=0

# 工作区与安全
AGENT_WORKSPACE_ROOT=
REQUIRE_CONFIRM_ON_WRITE=1
REQUIRE_CONFIRM_ON_COMMAND=1
ALLOW_DELETE_PATH=0
COMMAND_TIMEOUT_SECONDS=30
```

- `CHAT_MODEL`：可改为 `gpt5.4fast` 等 API 支持的模型名
- `ENABLE_PYTHON_REPL=1`：启用 Python 代码执行（需环境可信）
- `REQUIRE_CONFIRM_ON_WRITE=0` / `REQUIRE_CONFIRM_ON_COMMAND=0`：关闭写文件/执行命令前的确认（不推荐）
- `ALLOW_DELETE_PATH=1`：允许使用删除工具（仍会二次确认）

## 4. 运行方式

在项目根目录执行：

```powershell
.\venv\Scripts\python.exe ai/cn/chatagent.py
```

或在 `ai/cn` 下：

```powershell
python chatagent.py
```

## 5. 推荐测试

1. **知识**：我公司的福利有哪些？
2. **联网**：今天北京天气怎么样？
3. **系统**：看看我电脑状态？
4. **记忆**：我刚才问了你什么？
5. **开发**：搜索项目里包含 `def main` 的代码（会调用 search_code）
6. **开发**：读一下 `ai/cn/chatagent.py` 前 20 行（read_file_with_lines）；再让 AI 做小范围修改时会触发 replace_lines 并出现确认提示

## 6. 安全提示

- 修改文件、执行命令、创建/删除路径前会提示确认，请根据提示输入 `y` 或 `n`。
- 建议先在测试目录或副本上试用；重要文件请提前备份。
- 工作区根目录外的路径会被拒绝，避免误操作系统目录。

---
*文档更新日期: 2026-03-06*
