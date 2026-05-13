# Agent Workbench Web

这是前后端分离版本的前端目录，使用 Vite + React 启动。

## 启动后端

在 `claude/` 目录运行：

```powershell
python .\python\CursorAgent.py
```

默认 API：

```text
http://127.0.0.1:8765
```

## 启动前端

在当前目录运行：

```powershell
npm install
npm run dev
```

默认前端地址：

```text
http://127.0.0.1:5173
```

## 配置后端地址

复制 `.env.example` 为 `.env`，然后修改：

```text
VITE_AGENT_API_BASE=http://127.0.0.1:8765
```
