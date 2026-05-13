# Agent Workbench Frontend

这是独立前端目录。`CursorAgent.py` 现在只提供 API，不再负责前端页面托管。

## 后端启动

```powershell
& 'E:\package\python312\python.exe' 'D:\Aurora\Desktop\work\OpenAi\ai\claude\CursorAgent.py'
```

默认 API 地址：

```text
http://127.0.0.1:8765
```

## 前端启动

在当前目录启动任意静态文件服务即可，例如：

```powershell
cd D:\Aurora\Desktop\work\OpenAi\ai\claude\agent_workbench
& 'E:\package\python312\python.exe' -m http.server 5173
```

然后打开：

```text
http://127.0.0.1:5173
```

## 修改后端地址

编辑 `config.js`：

```js
window.AGENT_API_BASE = "http://127.0.0.1:8765";
```

如果前端和后端部署在不同地址，后端已启用基础 CORS 支持。
