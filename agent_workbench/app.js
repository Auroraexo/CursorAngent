const { useEffect, useMemo, useRef, useState } = React;
const API_BASE = (window.AGENT_API_BASE || "http://127.0.0.1:8765").replace(/\/$/, "");

const NAV_TO_PANE = {
  dashboard: "overview",
  agents: "chat",
  workflows: "workflow",
  knowledge: "knowledge",
  tools: "tools",
  memory: "monitor",
  logs: "tools",
  settings: "monitor",
};

const I18N = {
  zh: {
    nav: {
      dashboard: "Dashboard",
      agents: "Agents",
      workflows: "Workflows",
      knowledge: "Knowledge",
      tools: "Tools",
      memory: "Memory",
      logs: "Logs",
      settings: "Settings",
    },
    brandSub: "Lobster Shell Console",
    workspaceRoot: "工作区根目录",
    backendHint: "后端由 CursorAgent.py 驱动，前端是本地 React 工作台。",
    currentAgent: "当前 Agent",
    model: "模型",
    runtime: "运行状态",
    standby: "待命",
    running: "运行中",
    search: "搜索 agents、workflows、memory...",
    reset: "重置",
    execute: "执行",
    executing: "执行中...",
    newSession: "新建会话",
    language: "语言",
    heroEyebrow: "Enterprise Agent Operations",
    heroTitle: "智能体中控台，不只是聊天框。",
    heroDesc: "深黑科技底盘叠加少量“龙虾外壳”式层叠结构，用工作台视角承载 Prompt、Workflow、Knowledge、Tool Logs 与遥测指标。",
    promptTokens: "输入 Tokens",
    completionTokens: "输出 Tokens",
    estimatedCost: "估算成本",
    latency: "延迟",
    dialoguePlane: "对话平面",
    conversation: "会话",
    ready: "就绪",
    streaming: "流式输出",
    promptForge: "提示词锻炉",
    promptEditor: "Prompt 编辑器",
    allowActions: "允许写入 / 命令执行",
    promptPlaceholder: "在这里下达任务，工作台会把它送到 CursorAgent 后端，并把工具调用记录同步到监控面板。",
    workflowMesh: "工作流网格",
    orchestration: "编排",
    dragTip: "拖拽卡片可调整流程顺序",
    knowledgeRetrieval: "知识检索",
    contextHits: "上下文命中",
    toolTrace: "工具链追踪",
    toolRecords: "工具调用记录",
    runtimeTelemetry: "运行遥测",
    monitor: "监控",
    contextWindow: "上下文窗口",
    memoryNodes: "记忆节点",
    errorState: "错误状态",
    adminMode: "管理员模式",
    enabled: "已开启",
    no: "否",
    nominal: "正常",
    context: "上下文",
    contextDesc: "Session Prompt + Tool Outputs + Workspace Root",
    contextBody: "重点展示当前目录、启用模型、上下文窗口和风险策略。",
    memory: "记忆",
    memoryDesc: "短期执行记忆",
    memoryBody: "后续可扩展为结构化长期记忆、本地向量索引和偏好配置。",
    errors: "错误",
    errorsOk: "无严重告警",
    errorsWatch: "监控中...",
    errorsBody: "当前工作台默认将破坏性动作放在受控模式，需要显式开启。",
    starterPrompts: [
      "帮我梳理当前项目结构，并标出最关键的入口文件。",
      "定位一下这个项目里和 Agent 编排相关的代码。",
      "给我一个重构计划，先分析再执行。",
      "搜索项目里所有和 memory、knowledge 相关的实现。"
    ],
    boot: "Agent Workbench 已准备就绪。这里像一台真正的 Agent Operating System，而不是普通聊天页。",
    resetDone: "上下文已经重置，工作台进入新的空白态。",
    requestFailed: "请求失败：",
    sessionPrefix: "会话",
    tabs: {
      overview: "总览",
      chat: "对话",
      prompt: "Prompt",
      workflow: "工作流",
      knowledge: "知识",
      tools: "工具",
      monitor: "监控",
    },
  },
  en: {
    nav: {
      dashboard: "Dashboard",
      agents: "Agents",
      workflows: "Workflows",
      knowledge: "Knowledge",
      tools: "Tools",
      memory: "Memory",
      logs: "Logs",
      settings: "Settings",
    },
    brandSub: "Lobster Shell Console",
    workspaceRoot: "Workspace Root",
    backendHint: "Powered by CursorAgent.py with a local React workbench frontend.",
    currentAgent: "Current Agent",
    model: "Model",
    runtime: "Runtime",
    standby: "Standby",
    running: "Running",
    search: "Search agents, workflows, memory...",
    reset: "Reset",
    execute: "Execute",
    executing: "Executing...",
    newSession: "New Session",
    language: "Language",
    heroEyebrow: "Enterprise Agent Operations",
    heroTitle: "An agent control room, not just a chat page.",
    heroDesc: "A dark, premium AI operating console with lobster-shell inspired layered forms for prompts, workflows, knowledge, tool traces, and telemetry.",
    promptTokens: "Prompt Tokens",
    completionTokens: "Completion Tokens",
    estimatedCost: "Estimated Cost",
    latency: "Latency",
    dialoguePlane: "Dialogue Plane",
    conversation: "Conversation",
    ready: "Ready",
    streaming: "Streaming",
    promptForge: "Prompt Forge",
    promptEditor: "Prompt Editor",
    allowActions: "Allow write / command actions",
    promptPlaceholder: "Describe the task here. The workbench will send it to the CursorAgent backend and mirror tool activity into the monitor panel.",
    workflowMesh: "Workflow Mesh",
    orchestration: "Orchestration",
    dragTip: "Drag cards to reorder the pipeline",
    knowledgeRetrieval: "Knowledge Retrieval",
    contextHits: "Context Hits",
    toolTrace: "Toolchain Trace",
    toolRecords: "Tool Call Records",
    runtimeTelemetry: "Runtime Telemetry",
    monitor: "Monitor",
    contextWindow: "Context Window",
    memoryNodes: "Memory Nodes",
    errorState: "Error State",
    adminMode: "Admin Mode",
    enabled: "Enabled",
    no: "No",
    nominal: "Nominal",
    context: "Context",
    contextDesc: "Session Prompt + Tool Outputs + Workspace Root",
    contextBody: "Shows current directory, active model, context window, and safety policy at a glance.",
    memory: "Memory",
    memoryDesc: "Short-term execution memory",
    memoryBody: "This can grow into structured long-term memory, local vector search, and preference profiles.",
    errors: "Errors",
    errorsOk: "No critical alerts",
    errorsWatch: "Monitoring...",
    errorsBody: "Destructive actions stay guarded until explicitly enabled in the workbench.",
    starterPrompts: [
      "Map the current project structure and highlight the key entry files.",
      "Locate code related to agent orchestration in this project.",
      "Give me a refactor plan, analyze first and then execute.",
      "Search all implementations related to memory and knowledge."
    ],
    boot: "Agent Workbench is ready. This feels like a real Agent Operating System instead of a plain chat page.",
    resetDone: "Context has been reset. The workbench is now back to a clean state.",
    requestFailed: "Request failed: ",
    sessionPrefix: "Session",
    tabs: {
      overview: "Overview",
      chat: "Chat",
      prompt: "Prompt",
      workflow: "Workflow",
      knowledge: "Knowledge",
      tools: "Tools",
      monitor: "Monitor",
    },
  }
};

const knowledgeResults = {
  zh: [
    { title: "Architecture Snapshot", tag: "Design", body: "建议把 CursorAgent 抽象为 Engine、Session、Transport 三层，便于持续扩展。" },
    { title: "Safety Policy", tag: "Ops", body: "写入和命令执行默认关闭，由工作台显式开启，企业环境中更可控。" },
    { title: "Memory Shape", tag: "Context", body: "会话 Memory、工具日志、成本指标并列呈现，避免只看到聊天文本。" },
  ],
  en: [
    { title: "Architecture Snapshot", tag: "Design", body: "Consider splitting CursorAgent into Engine, Session, and Transport layers for easier expansion." },
    { title: "Safety Policy", tag: "Ops", body: "Write and command execution stay disabled by default and require explicit operator opt-in." },
    { title: "Memory Shape", tag: "Context", body: "Conversation memory, tool logs, and cost metrics should stay side by side, not hidden behind chat." },
  ],
};

const workflowSeed = {
  zh: [
    { id: "intent", title: "Intent Parse", desc: "识别用户目标、风险等级与所需工具", status: "Ready" },
    { id: "context", title: "Context Weave", desc: "融合 Memory、Knowledge、当前工作目录", status: "Warm" },
    { id: "tools", title: "Tool Mesh", desc: "执行代码检索、命令、文件读写与审计", status: "Guarded" },
    { id: "response", title: "Response Forge", desc: "整理输出、记录日志并生成回执", status: "Streaming" },
  ],
  en: [
    { id: "intent", title: "Intent Parse", desc: "Detect user intent, risk level, and required tools", status: "Ready" },
    { id: "context", title: "Context Weave", desc: "Blend memory, knowledge, and workspace context", status: "Warm" },
    { id: "tools", title: "Tool Mesh", desc: "Run code search, commands, file writes, and audits", status: "Guarded" },
    { id: "response", title: "Response Forge", desc: "Assemble the answer, trace logs, and final receipt", status: "Streaming" },
  ],
};

function MetricTile({ label, value, accent }) {
  return React.createElement("div", { className: `metric-tile accent-${accent}` }, [
    React.createElement("span", { key: "label" }, label),
    React.createElement("strong", { key: "value" }, value),
  ]);
}

function clone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function apiUrl(path, params) {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }
  return url.toString();
}

function App() {
  const [lang, setLang] = useState("zh");
  const [status, setStatus] = useState({ agent: "CursorAgent", model: "claude-sonnet-4-5", cwd: "loading...", admin: false, metrics: {} });
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [sessionState, setSessionState] = useState({});
  const [loading, setLoading] = useState(false);
  const [allowActions, setAllowActions] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [workflowCards, setWorkflowCards] = useState(clone(workflowSeed.zh));
  const [activePane, setActivePane] = useState("overview");
  const [activeNav, setActiveNav] = useState("dashboard");
  const dragRef = useRef(null);
  const activeSessionIdRef = useRef("");

  const dict = I18N[lang];
  const navItems = [
    { id: "dashboard", label: dict.nav.dashboard },
    { id: "agents", label: dict.nav.agents },
    { id: "workflows", label: dict.nav.workflows },
    { id: "knowledge", label: dict.nav.knowledge },
    { id: "tools", label: dict.nav.tools },
    { id: "memory", label: dict.nav.memory },
    { id: "logs", label: dict.nav.logs },
    { id: "settings", label: dict.nav.settings },
  ];
  const paneTabs = [
    { id: "overview", label: dict.tabs.overview },
    { id: "chat", label: dict.tabs.chat },
    { id: "prompt", label: dict.tabs.prompt },
    { id: "workflow", label: dict.tabs.workflow },
    { id: "knowledge", label: dict.tabs.knowledge },
    { id: "tools", label: dict.tabs.tools },
    { id: "monitor", label: dict.tabs.monitor },
  ];
  const activeState = sessionState[activeSessionId] || { messages: [], toolLogs: [], metrics: {}, status: "idle", name: "" };
  const messages = activeState.messages || [];
  const toolLogs = activeState.toolLogs || [];
  const metrics = activeState.metrics || {};

  const costText = useMemo(() => {
    const value = metrics.cost || 0;
    return `$${Number(value).toFixed(4)}`;
  }, [metrics.cost]);

  useEffect(() => {
    setWorkflowCards(clone(workflowSeed[lang]));
  }, [lang]);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  async function refreshStatus(sessionId = activeSessionId) {
    const res = await fetch(apiUrl("/api/status", { sessionId: sessionId || "", lang }));
    const data = await res.json();
    setStatus(data);
    setSessions(data.sessions || []);
    if (data.activeSessionId && !activeSessionId) setActiveSessionId(data.activeSessionId);
    if (data.activeSessionId && !sessionState[data.activeSessionId]) {
      setSessionState((prev) => ({
        ...prev,
        [data.activeSessionId]: {
          name: (data.sessions || []).find((item) => item.id === data.activeSessionId)?.name || dict.sessionPrefix,
          messages: [{ role: "assistant", content: dict.boot }],
          toolLogs: data.toolLogs || ["[boot] workbench shell initialized"],
          metrics: data.metrics || {},
          status: data.status || "idle",
        },
      }));
    }
    const targetSessionId = sessionId || data.activeSessionId;
    if (targetSessionId) {
      await fetchSessionDetail(targetSessionId);
    }
  }

  useEffect(() => {
    refreshStatus().catch(() => {});
  }, [lang]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (activeSessionId) refreshStatus(activeSessionId).catch(() => {});
    }, 4000);
    return () => clearInterval(timer);
  }, [activeSessionId, lang]);

  async function fetchSessionDetail(sessionId) {
    if (!sessionId) return;
    const res = await fetch(apiUrl("/api/session", { sessionId, lang }));
    const data = await res.json();
    const session = data.session;
    setSessionState((prev) => ({
      ...prev,
      [session.id]: {
        name: session.name,
        messages: session.messages || [{ role: "assistant", content: dict.boot }],
        toolLogs: session.toolLogs || [],
        metrics: session.metrics || {},
        status: session.status || "idle",
      },
    }));
  }

  function ensureSessionState(sessionId, fallbackName) {
    setSessionState((prev) => {
      if (prev[sessionId]) return prev;
      return {
        ...prev,
        [sessionId]: {
          name: fallbackName,
          messages: [{ role: "assistant", content: dict.boot }],
          toolLogs: ["[boot] workbench shell initialized"],
          metrics: {},
          status: "idle",
        },
      };
    });
  }

  async function createSession() {
    const name = `${dict.sessionPrefix} ${sessions.length + 1}`;
    const res = await fetch(apiUrl("/api/sessions"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, lang }),
    });
    const data = await res.json();
    const session = data.session;
    ensureSessionState(session.id, session.name);
    setSessions((prev) => [...prev, session]);
    setActiveSessionId(session.id);
    await fetchSessionDetail(session.id);
  }

  async function resetSession() {
    if (!activeSessionId) return;
    await fetch(apiUrl("/api/reset"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: activeSessionId, lang }),
    });
    await fetchSessionDetail(activeSessionId);
  }

  function updateSessionState(sessionId, updater) {
    if (!sessionId) return;
    setSessionState((prev) => {
      const current = prev[sessionId] || {};
      const next = typeof updater === "function" ? updater(current) : { ...current, ...updater };
      return {
        ...prev,
        [sessionId]: next,
      };
    });
  }

  function updateActiveSession(patch) {
    updateSessionState(activeSessionIdRef.current || activeSessionId, patch);
  }

  async function submitMessage(raw) {
    const message = (raw ?? prompt).trim();
    if (!message || loading || !activeSessionId) return;

    const sessionId = activeSessionId;
    const placeholderId = `assistant-${Date.now()}`;
    setPrompt("");
    setLoading(true);
    updateSessionState(sessionId, {
      status: "running",
      messages: [
        ...(messages || []),
        { role: "user", content: message },
        { id: placeholderId, role: "assistant", content: "" },
      ],
    });

    try {
      const response = await fetch(apiUrl("/api/chat/stream", {
        sessionId,
        lang,
        allowActions: String(allowActions),
        message,
      }));
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "stream request failed");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let stopReading = false;

      while (!stopReading) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop();
        for (const block of chunks) {
          const lines = block.split("\n");
          const eventLine = lines.find((line) => line.startsWith("event: "));
          const dataLine = lines.find((line) => line.startsWith("data: "));
          if (!eventLine || !dataLine) continue;
          const eventName = eventLine.replace("event: ", "").trim();
          const payload = JSON.parse(dataLine.replace("data: ", ""));

          if (eventName === "tool_log") {
            updateSessionState(sessionId, (current) => ({
              ...current,
              toolLogs: [...(current.toolLogs || []), payload.message],
            }));
          }

          if (eventName === "delta") {
            updateSessionState(sessionId, (current) => ({
              ...current,
              messages: (current.messages || []).map((item) =>
                item.id === placeholderId ? { ...item, content: `${item.content}${payload.content}` } : item
              ),
            }));
          }

          if (eventName === "metrics") {
            updateSessionState(sessionId, { metrics: payload.metrics || {} });
          }

          if (eventName === "status") {
            updateSessionState(sessionId, { status: payload.status });
          }

          if (eventName === "done") {
            updateSessionState(sessionId, {
              metrics: payload.metrics || {},
              status: payload.status || "idle",
            });
            stopReading = true;
            try {
              await reader.cancel();
            } catch (_) {}
          }

          if (eventName === "error") {
            updateSessionState(sessionId, (current) => ({
              ...current,
              messages: [
                ...(current.messages || []),
                { role: "system", content: `${dict.requestFailed}${payload.error}` },
              ],
              status: "error",
            }));
            stopReading = true;
            try {
              await reader.cancel();
            } catch (_) {}
          }
        }
      }
    } catch (error) {
      updateSessionState(sessionId, (current) => ({
        ...current,
        messages: [
          ...(current.messages || []),
          { role: "system", content: `${dict.requestFailed}${error.message}` },
        ],
        status: "error",
      }));
    } finally {
      setLoading(false);
      refreshStatus(sessionId).catch(() => {});
    }
  }

  function onDragStart(index) {
    dragRef.current = index;
  }

  function onDrop(index) {
    const from = dragRef.current;
    if (from === null || from === index) return;
    const next = [...workflowCards];
    const [moved] = next.splice(from, 1);
    next.splice(index, 0, moved);
    setWorkflowCards(next);
    dragRef.current = null;
  }

  function selectNav(navId) {
    setActiveNav(navId);
    setActivePane(NAV_TO_PANE[navId] || "overview");
  }

  function selectPane(paneId) {
    setActivePane(paneId);
    const matchedNav = Object.entries(NAV_TO_PANE).find(([, targetPane]) => targetPane === paneId)?.[0];
    if (matchedNav) {
      setActiveNav(matchedNav);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar shell-card">
        <div className="brand">
          <div className="brand-mark"></div>
          <div>
            <strong>Agent OS</strong>
            <p>{dict.brandSub}</p>
          </div>
        </div>

        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeNav === item.id ? "active" : ""}`}
              onClick={() => selectNav(item.id)}
            >
              <span className="nav-dot"></span>{item.label}
            </button>
          ))}
        </nav>

        <div className="session-tabs">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`session-tab ${session.id === activeSessionId ? "active" : ""}`}
              onClick={() => {
                setActiveSessionId(session.id);
                ensureSessionState(session.id, session.name);
                fetchSessionDetail(session.id).catch(() => {});
              }}
            >
              <span>{session.name}</span>
              <small>{session.lang.toUpperCase()}</small>
            </button>
          ))}
        </div>

        <div className="sidebar-footer shell-card inset-card">
          <span className="eyebrow">{dict.workspaceRoot}</span>
          <strong>{status.cwd}</strong>
          <p>{dict.backendHint}</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar shell-card">
          <div className="topbar-left">
            <div className="status-chip"><span className="chip-label">{dict.currentAgent}</span><strong>{status.agent}</strong></div>
            <div className="status-chip"><span className="chip-label">{dict.model}</span><strong>{status.model}</strong></div>
            <div className="status-chip"><span className="chip-label">{dict.runtime}</span><strong>{loading ? dict.running : dict.standby}</strong></div>
          </div>
          <div className="topbar-right">
            <label className="search-wrap"><input placeholder={dict.search} /></label>
            <select className="lang-switch" value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
            <button className="ghost-btn" onClick={createSession}>{dict.newSession}</button>
            <button className="ghost-btn" onClick={resetSession}>{dict.reset}</button>
            <button className="primary-btn" onClick={() => submitMessage()}>{loading ? dict.executing : dict.execute}</button>
          </div>
        </header>

        <section className="hero shell-card">
          <div className="hero-copy">
            <span className="eyebrow">{dict.heroEyebrow}</span>
            <h1>{dict.heroTitle}</h1>
            <p>{dict.heroDesc}</p>
          </div>
          <div className="hero-metrics">
            <MetricTile label={dict.promptTokens} value={metrics.promptTokens || "0"} accent="red" />
            <MetricTile label={dict.completionTokens} value={metrics.completionTokens || "0"} accent="orange" />
            <MetricTile label={dict.estimatedCost} value={costText} accent="gold" />
            <MetricTile label={dict.latency} value={`${metrics.latencyMs || 0} ms`} accent="red" />
          </div>
        </section>

        <section className="tabbed-workspace shell-card">
          <div className="pane-tabs">
            {paneTabs.map((tab) => (
              <button
                key={tab.id}
                className={`pane-tab ${activePane === tab.id ? "active" : ""}`}
                onClick={() => selectPane(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="pane-body">
            {(activePane === "overview" || activePane === "chat") && (
              <section className="chat-panel panel-plain">
              <div className="panel-head">
                <div><span className="eyebrow">{dict.dialoguePlane}</span><h2>{dict.conversation}</h2></div>
                <span className="state-pill">{loading ? dict.streaming : dict.ready}</span>
              </div>
              <div className="messages">
                {messages.map((msg, idx) => (
                  <article key={`${msg.role}-${idx}-${msg.id || "x"}`} className={`message ${msg.role}`}>
                    <span className="message-role">{msg.role}</span>
                    <p>{msg.content || (loading && msg.role === "assistant" ? "..." : "")}</p>
                  </article>
                ))}
              </div>
              </section>
            )}

            {(activePane === "overview" || activePane === "prompt") && (
              <section className="editor-panel panel-plain">
              <div className="panel-head">
                <div><span className="eyebrow">{dict.promptForge}</span><h2>{dict.promptEditor}</h2></div>
                <label className="toggle">
                  <input type="checkbox" checked={allowActions} onChange={(e) => setAllowActions(e.target.checked)} />
                  <span>{dict.allowActions}</span>
                </label>
              </div>
              <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder={dict.promptPlaceholder} />
              <div className="starter-row">
                {dict.starterPrompts.map((item) => (
                  <button key={item} className="starter-pill" onClick={() => submitMessage(item)}>{item}</button>
                ))}
              </div>
              </section>
            )}

            {(activePane === "overview" || activePane === "workflow" || activePane === "knowledge") && (
              <section className={`split-panels ${activePane !== "overview" ? "single-pane" : ""}`}>
              {(activePane === "overview" || activePane === "workflow") && (
                <section className="workflow-panel panel-plain">
                <div className="panel-head">
                  <div><span className="eyebrow">{dict.workflowMesh}</span><h2>{dict.orchestration}</h2></div>
                  <span className="state-pill subtle">{dict.dragTip}</span>
                </div>
                <div className="workflow-list">
                  {workflowCards.map((card, index) => (
                    <div
                      className="workflow-card draggable"
                      key={card.id}
                      draggable
                      onDragStart={() => onDragStart(index)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => onDrop(index)}
                    >
                      <div><strong>{card.title}</strong><p>{card.desc}</p></div>
                      <span>{card.status}</span>
                    </div>
                  ))}
                </div>
                </section>
              )}

              {(activePane === "overview" || activePane === "knowledge") && (
                <section className="knowledge-panel panel-plain">
                <div className="panel-head"><div><span className="eyebrow">{dict.knowledgeRetrieval}</span><h2>{dict.contextHits}</h2></div></div>
                <div className="knowledge-list">
                  {knowledgeResults[lang].map((item) => (
                    <article className="knowledge-card" key={item.title}>
                      <div className="knowledge-head"><strong>{item.title}</strong><span>{item.tag}</span></div>
                      <p>{item.body}</p>
                    </article>
                  ))}
                </div>
                </section>
              )}
              </section>
            )}

            {(activePane === "overview" || activePane === "tools") && (
              <section className="log-panel panel-plain">
              <div className="panel-head"><div><span className="eyebrow">{dict.toolTrace}</span><h2>{dict.toolRecords}</h2></div></div>
              <div className="log-stream">
                {toolLogs.map((item, idx) => <div className="log-line" key={`${item}-${idx}`}>{item}</div>)}
              </div>
              </section>
            )}

            {(activePane === "overview" || activePane === "monitor") && (
              <div className={`monitor-stack ${activePane !== "overview" ? "single-monitor" : ""}`}>
            <section className="monitor-card panel-plain">
              <div className="panel-head"><div><span className="eyebrow">{dict.runtimeTelemetry}</span><h2>{dict.monitor}</h2></div></div>
              <div className="monitor-grid">
                <MetricTile label={dict.contextWindow} value="32k" accent="red" />
                <MetricTile label={dict.memoryNodes} value="148" accent="orange" />
                <MetricTile label={dict.errorState} value={(metrics.errors || 0) > 0 ? `${metrics.errors}` : dict.nominal} accent="gold" />
                <MetricTile label={dict.adminMode} value={status.admin ? dict.enabled : dict.no} accent="red" />
              </div>
            </section>

            <section className="side-stack panel-plain">
              <div className="stack-item"><span className="eyebrow">{dict.context}</span><strong>{dict.contextDesc}</strong><p>{dict.contextBody}</p></div>
              <div className="stack-item"><span className="eyebrow">{dict.memory}</span><strong>{dict.memoryDesc}</strong><p>{dict.memoryBody}</p></div>
              <div className="stack-item"><span className="eyebrow">{dict.errors}</span><strong>{loading ? dict.errorsWatch : dict.errorsOk}</strong><p>{dict.errorsBody}</p></div>
            </section>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
