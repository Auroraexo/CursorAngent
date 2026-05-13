import React, { useEffect, useMemo, useRef, useState } from "react";
import "./styles.css";

const API_BASE = (import.meta.env.VITE_AGENT_API_BASE || "http://127.0.0.1:8765").replace(/\/$/, "");

// --- Generic UI Components (Design System) ---

const Button = ({ children, variant = "primary", className = "", loading, ...props }) => (
  <button 
    className={`btn btn-${variant} ${className}`} 
    disabled={loading || props.disabled}
    {...props}
  >
    {loading ? <span className="skeleton" style={{width: "20px", height: "20px", borderRadius: "50%"}}></span> : children}
  </button>
);

const Card = ({ children, className = "", ...props }) => (
  <div className={`card ${className}`} {...props}>{children}</div>
);

const MetricTile = ({ label, value }) => (
  <div className="metric-tile">
    <span>{label}</span>
    <strong>{value}</strong>
  </div>
);

const Skeleton = ({ className = "", style }) => (
  <div className={`skeleton ${className}`} style={{ minHeight: "1em", width: "100%", ...style }}></div>
);

// --- I18n Dictionary ---
const I18N = {
  en: {
    title: "Agent OS",
    subtitle: "Enterprise Console",
    nav: { dashboard: "Dashboard", workflows: "Workflows", knowledge: "Knowledge", settings: "Settings" },
    status: { running: "Running", standby: "Standby", model: "Model", status: "Status" },
    theme: { light: "☀️ Light", dark: "🌙 Dark" },
    reset: "Reset",
    dialoguePlane: "Dialogue Plane",
    emptyChat: "No messages yet. Start a conversation.",
    inputPlaceholder: "Enter command or prompt...",
    execute: "Execute",
    telemetry: "Runtime Telemetry",
    metrics: { latency: "Latency", tokens: "Tokens", cost: "Cost", memory: "Memory" },
    contextWindow: "Context Window",
    contextDesc: "Workspace root bounded. Destructive actions guarded.",
    contextLogs: [
      "[SYSTEM] Context loaded.",
      "[INFO] Tools meshed.",
      "[READY] Awaiting input."
    ],
    placeholder: "Content for this section is under construction.",
    workflowDesc: "Orchestrate agent task pipelines.",
    knowledgeDesc: "Manage local vectors and documents.",
    settingsDesc: "System preferences and access control.",
    workflows: {
      loading: "Loading workflow telemetry...",
      error: "Failed to load workflows.",
      empty: "No workflow data yet.",
      session: "Session",
      stages: "Stages",
      recentMessages: "Recent Messages",
      toolLogs: "Tool Logs",
      retry: "Retry",
    },
    knowledge: {
      searchPlaceholder: "Search documents or snippets...",
      search: "Search",
      loading: "Loading knowledge base...",
      error: "Failed to load knowledge results.",
      empty: "No matching knowledge documents.",
      stats: "Stats",
      documents: "Documents",
      matches: "Matches",
      bytes: "Bytes",
      updated: "Updated",
    },
    permissions: {
      write: "Write Access",
      command: "Command Access",
      writeHint: "Allow file create/update/delete tools.",
      commandHint: "Allow terminal command execution.",
    },
  },
  zh: {
    title: "智能体系统",
    subtitle: "企业控制台",
    nav: { dashboard: "仪表盘", workflows: "工作流", knowledge: "知识库", settings: "设置" },
    status: { running: "运行中", standby: "待命", model: "模型", status: "状态" },
    theme: { light: "☀️ 亮色", dark: "🌙 暗色" },
    reset: "重置",
    dialoguePlane: "对话平面",
    emptyChat: "暂无消息，请开始对话。",
    inputPlaceholder: "输入命令或提示词...",
    execute: "执行",
    telemetry: "运行时遥测",
    metrics: { latency: "延迟", tokens: "消耗", cost: "成本", memory: "内存" },
    contextWindow: "上下文窗口",
    contextDesc: "已绑定工作区根目录。危险操作已受控。",
    contextLogs: [
      "[系统] 上下文已加载。",
      "[信息] 工具已就绪。",
      "[就绪] 等待输入。"
    ],
    placeholder: "此部分内容正在建设中。",
    workflowDesc: "编排智能体任务流水线。",
    knowledgeDesc: "管理本地向量与文档库。",
    settingsDesc: "系统偏好设置与访问控制。",
    workflows: {
      loading: "正在加载工作流数据...",
      error: "加载工作流失败。",
      empty: "暂无工作流数据。",
      session: "会话",
      stages: "阶段",
      recentMessages: "最近消息",
      toolLogs: "工具日志",
      retry: "重试",
    },
    knowledge: {
      searchPlaceholder: "搜索文档或片段...",
      search: "查询",
      loading: "正在加载知识库...",
      error: "加载知识库结果失败。",
      empty: "没有匹配的知识库文档。",
      stats: "统计",
      documents: "文档数",
      matches: "匹配数",
      bytes: "字节数",
      updated: "更新时间",
    },
    permissions: {
      write: "写入权限",
      command: "命令权限",
      writeHint: "允许创建、修改、删除文件工具。",
      commandHint: "允许执行终端命令。",
    },
  }
};

function apiUrl(path, params) {
  const url = new URL(`${API_BASE}${path}`);
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });
  return url.toString();
}

// --- Main Application ---

export default function App() {
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "dark");
  const [lang, setLang] = useState(localStorage.getItem("lang") || "en");
  const [loading, setLoading] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");

  // Real backend state
  const [status, setStatus] = useState({ agent: "CursorAgent", model: "claude-sonnet-4-5", cwd: "loading...", admin: false });
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(localStorage.getItem("activeSessionId") || "");
  const [sessionState, setSessionState] = useState({});
  const [workflowState, setWorkflowState] = useState({ data: null, loading: false, error: "" });
  const [knowledgeState, setKnowledgeState] = useState({ data: null, loading: false, error: "", query: "" });
  const [allowWrite, setAllowWrite] = useState(false);
  const [allowCommand, setAllowCommand] = useState(false);
  const [activeRunId, setActiveRunId] = useState("");
  const [lastEventSeq, setLastEventSeq] = useState(0);
  const [streamingAssistantId, setStreamingAssistantId] = useState("");

  const abortControllerRef = useRef(null);
  const eventSourceRef = useRef(null);
  const activeSessionIdRef = useRef("");
  const activeRunIdRef = useRef("");
  const lastEventSeqRef = useRef(0);
  const streamingAssistantIdRef = useRef("");

  useEffect(() => { activeSessionIdRef.current = activeSessionId; }, [activeSessionId]);
  useEffect(() => { activeRunIdRef.current = activeRunId; }, [activeRunId]);
  useEffect(() => { lastEventSeqRef.current = lastEventSeq; }, [lastEventSeq]);
  useEffect(() => { streamingAssistantIdRef.current = streamingAssistantId; }, [streamingAssistantId]);

  const t = I18N[lang];
  const messages = sessionState[activeSessionId]?.messages || [];
  const toolLogs = sessionState[activeSessionId]?.toolLogs || [];
  const metrics = sessionState[activeSessionId]?.metrics || {};
  const workflowData = workflowState.data;
  const knowledgeData = knowledgeState.data;

  const costText = useMemo(() => `$${Number(metrics.cost || 0).toFixed(4)}`, [metrics.cost]);

  function getStoredRunState(sessionId) {
    try {
      const all = JSON.parse(localStorage.getItem("runStateBySession") || "{}");
      return all[sessionId] || null;
    } catch {
      return null;
    }
  }

  function persistRunState(sessionId, patch) {
    if (!sessionId) return;
    try {
      const all = JSON.parse(localStorage.getItem("runStateBySession") || "{}");
      all[sessionId] = { ...(all[sessionId] || {}), ...patch };
      localStorage.setItem("runStateBySession", JSON.stringify(all));
    } catch {
    }
  }

  function clearRunState(sessionId) {
    if (!sessionId) return;
    try {
      const all = JSON.parse(localStorage.getItem("runStateBySession") || "{}");
      delete all[sessionId];
      localStorage.setItem("runStateBySession", JSON.stringify(all));
    } catch {
    }
  }

  function closeRunStream() {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }

  async function fetchJson(path, params) {
    const res = await fetch(apiUrl(path, params));
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error || `Request failed: ${res.status}`);
    return data;
  }

  function updateSession(sessionId, patch) {
    if (!sessionId) return;
    setSessionState((prev) => ({ ...prev, [sessionId]: { ...(prev[sessionId] || {}), ...patch } }));
  }

  function upsertStreamingAssistant(sessionId, assistantId) {
    setSessionState((prev) => {
      const current = prev[sessionId] || {};
      const existingMessages = current.messages || [];
      const hasAssistant = existingMessages.some((item) => item.id === assistantId);
      return {
        ...prev,
        [sessionId]: {
          ...current,
          messages: hasAssistant ? existingMessages : [...existingMessages, { id: assistantId, role: "assistant", content: "" }],
        },
      };
    });
  }

  async function finalizeRun(sessionId) {
    clearRunState(sessionId);
    setActiveRunId("");
    setLastEventSeq(0);
    setStreamingAssistantId("");
    setLoading(false);
    closeRunStream();
    await fetchSessionDetail(sessionId);
    await refreshStatus(sessionId);
  }

  function applyRunEvent(sessionId, assistantId, eventName, payload) {
    if (payload?.seq) {
      setLastEventSeq(payload.seq);
      persistRunState(sessionId, { runId: activeRunIdRef.current, lastEventSeq: payload.seq, streamingAssistantId: assistantId });
    }

    if (eventName === "tool_log") {
      setSessionState((prev) => ({ ...prev, [sessionId]: { ...(prev[sessionId] || {}), toolLogs: [...((prev[sessionId]?.toolLogs) || []), payload.message] } }));
      return;
    }

    if (eventName === "delta") {
      upsertStreamingAssistant(sessionId, assistantId);
      setSessionState((prev) => ({
        ...prev,
        [sessionId]: {
          ...(prev[sessionId] || {}),
          messages: ((prev[sessionId]?.messages) || []).map((item) => item.id === assistantId ? { ...item, content: `${item.content}${payload.content || ""}` } : item),
        },
      }));
      return;
    }

    if (eventName === "metrics") {
      updateSession(sessionId, { metrics: payload.metrics || {} });
      return;
    }

    if (eventName === "status") {
      updateSession(sessionId, { status: payload.status });
      if (payload.status === "running") setLoading(true);
      if (payload.status === "idle" || payload.status === "cancelled") {
        finalizeRun(sessionId).catch(() => { });
      }
      return;
    }

    if (eventName === "done") {
      finalizeRun(sessionId).catch(() => { });
      return;
    }

    if (eventName === "error") {
      updateSession(sessionId, {
        messages: [...((sessionState[sessionId]?.messages) || []), { role: "system", content: `Error: ${payload.error}` }],
        status: payload.cancelled ? "cancelled" : "error",
      });
      finalizeRun(sessionId).catch(() => { });
    }
  }

  function openRunStream(runId, sessionId, assistantId, cursor = 0) {
    closeRunStream();
    upsertStreamingAssistant(sessionId, assistantId);
    const stream = new EventSource(apiUrl("/api/runs/stream", { runId, cursor: String(cursor) }));
    eventSourceRef.current = stream;
    setLoading(true);

    ["start", "tool_log", "delta", "metrics", "status", "done", "error"].forEach((eventName) => {
      stream.addEventListener(eventName, (event) => {
        const payload = JSON.parse(event.data);
        applyRunEvent(sessionId, assistantId, eventName, payload);
      });
    });

    stream.onerror = () => {
      stream.close();
      if (activeRunIdRef.current === runId) {
        eventSourceRef.current = null;
      }
    };
  }

  async function resumeRun(sessionId, forceFullReplay = false) {
    const stored = getStoredRunState(sessionId);
    if (!stored?.runId) return;
    try {
      const run = await fetchJson("/api/runs/status", { runId: stored.runId });
      if (run.done) {
        await finalizeRun(sessionId);
        return;
      }
      const assistantId = stored.streamingAssistantId || `assistant-${run.runId}`;
      setActiveRunId(run.runId);
      setLastEventSeq(stored.lastEventSeq || 0);
      setStreamingAssistantId(assistantId);
      persistRunState(sessionId, { runId: run.runId, lastEventSeq: stored.lastEventSeq || 0, streamingAssistantId: assistantId });
      const existingMessages = sessionState[sessionId]?.messages || [];
      const hasAssistant = existingMessages.some((item) => item.id === assistantId);
      openRunStream(run.runId, sessionId, assistantId, forceFullReplay || !hasAssistant ? 0 : (stored.lastEventSeq || 0));
    } catch {
      clearRunState(sessionId);
    }
  }

  // Apply theme to document
  useEffect(() => {
    document.documentElement.className = `${theme}-theme`;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem("lang", lang);
  }, [lang]);

  useEffect(() => {
    localStorage.setItem("activeSessionId", activeSessionId);
  }, [activeSessionId]);

  useEffect(() => () => closeRunStream(), []);

  // --- Backend Data Fetching ---
  async function fetchSessionDetail(sessionId) {
    if (!sessionId) return;
    const data = await fetchJson("/api/session", { sessionId, lang });
    setSessionState((prev) => ({ ...prev, [sessionId]: { ...(prev[sessionId] || {}), ...data.session } }));
  }

  async function refreshStatus(sessionId, useLang) {
    const sid = sessionId || activeSessionIdRef.current;
    const lng = useLang || lang;
    try {
      const data = await fetchJson("/api/status", { sessionId: sid, lang: lng });
      setStatus(data);
      setSessions(data.sessions || []);
      if (!activeSessionIdRef.current && data.activeSessionId) setActiveSessionId(data.activeSessionId);

      const target = sid || data.activeSessionId;
      if (target) await fetchSessionDetail(target);
    } catch (e) {
      console.error("Failed to fetch status:", e);
    }
  }

  async function fetchWorkflows(sessionId = activeSessionIdRef.current, force = false) {
    if (!sessionId || (workflowState.loading && !force)) return;
    if (workflowState.data && !force) return;
    setWorkflowState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const data = await fetchJson("/api/workflows", { sessionId, lang });
      setWorkflowState({ data, loading: false, error: "" });
    } catch (error) {
      setWorkflowState((prev) => ({ ...prev, loading: false, error: error.message || t.workflows.error }));
    }
  }

  async function fetchKnowledge(query = knowledgeState.query, force = false) {
    if (knowledgeState.loading && !force) return;
    if (knowledgeState.data && knowledgeState.query === query && !force) return;
    setKnowledgeState((prev) => ({ ...prev, query, loading: true, error: "" }));
    try {
      const data = await fetchJson("/api/knowledge", { q: query });
      setKnowledgeState({ data, query, loading: false, error: "" });
    } catch (error) {
      setKnowledgeState((prev) => ({ ...prev, loading: false, error: error.message || t.knowledge.error }));
    }
  }

  useEffect(() => { refreshStatus().catch(() => { }); }, []);
  useEffect(() => {
    const timer = setInterval(() => {
      const sid = activeSessionIdRef.current;
      if (sid) refreshStatus(sid).catch(() => { });
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (activeTab === "workflows") fetchWorkflows().catch(() => { });
    if (activeTab === "knowledge") fetchKnowledge().catch(() => { });
  }, [activeTab, activeSessionId, lang]);

  useEffect(() => {
    if (!activeSessionId) return;
    const stored = getStoredRunState(activeSessionId);
    setActiveRunId(stored?.runId || "");
    setLastEventSeq(stored?.lastEventSeq || 0);
    setStreamingAssistantId(stored?.streamingAssistantId || "");
    fetchSessionDetail(activeSessionId)
      .then(() => resumeRun(activeSessionId, true))
      .catch(() => { });
  }, [activeSessionId, lang]);

  async function createSession() {
    const res = await fetch(apiUrl("/api/sessions"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: `Session ${sessions.length + 1}`, lang }),
    });
    const data = await res.json();
    setWorkflowState({ data: null, loading: false, error: "" });
    setActiveSessionId(data.session.id);
    await refreshStatus(data.session.id);
  }

  async function resetSession() {
    if (!activeSessionId) return;
    clearRunState(activeSessionId);
    closeRunStream();
    setActiveRunId("");
    setLastEventSeq(0);
    setStreamingAssistantId("");
    await fetch(apiUrl("/api/reset"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: activeSessionId, lang }),
    });
    await fetchSessionDetail(activeSessionId);
  }

  // --- Interaction ---
  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const toggleLang = () => {
    const newLang = lang === "en" ? "zh" : "en";
    setLang(newLang);
    const sid = activeSessionIdRef.current;
    if (sid) refreshStatus(sid, newLang).catch(() => { });
  };

  async function stopExecution() {
    const runId = activeRunIdRef.current;
    closeRunStream();
    if (!runId) {
      setLoading(false);
      return;
    }
    try {
      await fetch(apiUrl("/api/runs/cancel"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ runId, sessionId: activeSessionIdRef.current, lang }),
      });
    } finally {
      setLoading(false);
      refreshStatus(activeSessionIdRef.current).catch(() => { });
    }
  }

  const submitMessage = async () => {
    if (!prompt.trim() || loading || !activeSessionId) return;

    closeRunStream();
    if (abortControllerRef.current) abortControllerRef.current.abort();
    const ctrl = new AbortController();
    abortControllerRef.current = ctrl;

    const sessionId = activeSessionId;
    const message = prompt.trim();
    const placeholderId = `assistant-${Date.now()}`;
    setPrompt("");
    setLoading(true);
    setStreamingAssistantId(placeholderId);
    setLastEventSeq(0);
    updateSession(sessionId, { messages: [...messages, { role: "user", content: message }, { id: placeholderId, role: "assistant", content: "" }], status: "running", toolLogs: toolLogs });

    try {
      const response = await fetch(apiUrl("/api/runs"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sessionId,
          lang,
          allowWrite,
          allowCommand,
          message,
        }),
        signal: ctrl.signal,
      });
      const run = await response.json();
      if (!response.ok) throw new Error(run?.error || "run request failed");
      setActiveRunId(run.runId);
      persistRunState(sessionId, { runId: run.runId, lastEventSeq: 0, streamingAssistantId: placeholderId });
      openRunStream(run.runId, sessionId, placeholderId, 0);
    } catch (error) {
      if (error.name !== "AbortError") {
        updateSession(sessionId, { messages: [...((sessionState[sessionId]?.messages) || []), { role: "system", content: `Error: ${error.message}` }], status: "error" });
      }
      setLoading(false);
    } finally {
      abortControllerRef.current = null;
    }
  };

  // Render the main content based on the active tab
  const renderContent = () => {
    switch (activeTab) {
      case "workflows":
        return (
          <Card className="col-lg-12">
            <h2 className="mb-2">{t.nav.workflows}</h2>
            <p className="mb-4 text-muted">{t.workflowDesc}</p>
            {workflowState.loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                <Skeleton style={{ height: "56px" }} />
                <Skeleton style={{ height: "120px" }} />
                <Skeleton style={{ height: "120px" }} />
              </div>
            ) : workflowState.error ? (
              <Card style={{ background: "var(--bg-app)" }}>
                <p className="mb-4">{workflowState.error || t.workflows.error}</p>
                <Button variant="ghost" onClick={() => fetchWorkflows(activeSessionId, true)}>{t.workflows.retry}</Button>
              </Card>
            ) : !workflowData ? (
              <div className="text-muted" style={{ padding: "var(--space-8) 0", textAlign: "center" }}>{t.workflows.empty}</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                <div className="grid" style={{ "--grid-columns": 4 }}>
                  <MetricTile label={t.workflows.session} value={workflowData.sessionName || "-"} />
                  <MetricTile label={t.status.status} value={workflowData.status || "idle"} />
                  <MetricTile label={t.workflows.stages} value={String((workflowData?.stages || []).length)} />
                  <MetricTile label={t.metrics.tokens} value={String(workflowData.metrics?.totalTokens || 0)} />
                </div>
                <div className="grid" style={{ "--grid-columns": Math.max((workflowData?.stages || []).length || 1, 1) }}>
                  {(workflowData?.stages || []).length > 0 ? (workflowData?.stages || []).map((stage) => (
                    <Card key={stage.id} style={{ background: "var(--bg-app)" }}>
                      <div className="status-chip mb-2">{stage.status}</div>
                      <h3 className="mb-2">{stage.title}</h3>
                      <p className="mb-2">{stage.summary}</p>
                      <small className="text-muted">count: {stage.count}</small>
                    </Card>
                  )) : (
                    <div className="text-muted">{t.workflows.empty}</div>
                  )}
                </div>
                <div className="grid" style={{ "--grid-columns": 2 }}>
                  <Card style={{ background: "var(--bg-app)" }}>
                    <h3 className="mb-2">{t.workflows.recentMessages}</h3>
                    <div className="text-muted text-xs" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {(workflowData?.recentMessages || []).length > 0 ? (workflowData?.recentMessages || []).map((item, index) => (
                        <div key={`${item.role}-${index}`}>
                          <strong>{item.role}</strong>
                          <div>{item.content}</div>
                        </div>
                      )) : t.workflows.empty}
                    </div>
                  </Card>
                  <Card style={{ background: "var(--bg-app)" }}>
                    <h3 className="mb-2">{t.workflows.toolLogs}</h3>
                    <div className="text-muted text-xs" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                      {(workflowData?.toolLogs || []).length > 0 ? (workflowData?.toolLogs || []).map((item, index) => <div key={`${index}-${item}`}>{item}</div>) : t.workflows.empty}
                    </div>
                  </Card>
                </div>
              </div>
            )}
          </Card>
        );
      case "knowledge":
        return (
          <Card className="col-lg-12">
            <h2 className="mb-2">{t.nav.knowledge}</h2>
            <p className="mb-4 text-muted">{t.knowledgeDesc}</p>
            <div style={{ display: "flex", gap: "var(--space-3)", marginBottom: "var(--space-4)" }}>
              <input
                type="text"
                className="input"
                placeholder={t.knowledge.searchPlaceholder}
                value={knowledgeState.query}
                onChange={(e) => setKnowledgeState((prev) => ({ ...prev, query: e.target.value }))}
                onKeyDown={(e) => e.key === "Enter" && fetchKnowledge(knowledgeState.query, true)}
              />
              <Button onClick={() => fetchKnowledge(knowledgeState.query, true)} loading={knowledgeState.loading}>{t.knowledge.search}</Button>
            </div>
            {knowledgeState.loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                <Skeleton style={{ height: "56px" }} />
                <Skeleton style={{ height: "96px" }} />
              </div>
            ) : knowledgeState.error ? (
              <Card style={{ background: "var(--bg-app)" }}>
                <p className="mb-4">{knowledgeState.error || t.knowledge.error}</p>
                <Button variant="ghost" onClick={() => fetchKnowledge(knowledgeState.query, true)}>{t.workflows.retry}</Button>
              </Card>
            ) : !knowledgeData ? (
              <div className="text-muted" style={{ padding: "var(--space-8) 0", textAlign: "center" }}>{t.knowledge.empty}</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
                <div className="grid" style={{ "--grid-columns": 3 }}>
                  <MetricTile label={t.knowledge.documents} value={String(knowledgeData?.stats?.documents || 0)} />
                  <MetricTile label={t.knowledge.matches} value={String(knowledgeData?.stats?.matches || 0)} />
                  <MetricTile label={t.knowledge.bytes} value={String(knowledgeData?.stats?.bytes || 0)} />
                </div>
                {(knowledgeData?.items || []).length > 0 ? (knowledgeData?.items || []).map((item) => (
                  <Card key={item.id} style={{ background: "var(--bg-app)" }}>
                    <h3 className="mb-2">{item.name}</h3>
                    <p className="mb-2 text-xs" style={{ wordBreak: "break-all" }}>{item.path}</p>
                    <p>{item.snippet || t.knowledge.empty}</p>
                    <small className="text-muted">{t.knowledge.updated}: {item.updatedAt ? new Date(item.updatedAt * 1000).toLocaleString() : "-"}</small>
                  </Card>
                )) : (
                  <div className="text-muted" style={{ padding: "var(--space-8) 0", textAlign: "center" }}>{t.knowledge.empty}</div>
                )}
              </div>
            )}
          </Card>
        );
      case "settings":
        return (
          <Card className="col-lg-12">
            <h2 className="mb-2">{t.nav.settings}</h2>
            <p className="mb-4 text-muted">{t.settingsDesc}</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", maxWidth: "400px" }}>
              <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>{t.theme[theme]}</span>
                <Button variant="ghost" onClick={toggleTheme}>Toggle</Button>
              </label>
              <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Language / 语言</span>
                <Button variant="ghost" onClick={toggleLang}>{lang === "en" ? "中" : "EN"}</Button>
              </label>
            </div>
          </Card>
        );
      case "dashboard":
      default:
        return (
          <div className="panel-grid">
            {/* Left Column: Chat / Action Area */}
            <Card className="col-lg-8 col-md-12">
              <h2 className="mb-4">{t.dialoguePlane}</h2>
              <div className="message-list mb-4">
                {messages.length === 0 ? (
                  <div className="text-muted" style={{ textAlign: "center", padding: "var(--space-8) 0" }}>
                    {t.emptyChat}
                  </div>
                ) : (
                  messages.map((msg, i) => (
                    <div key={i} className={`message ${msg.role}`}>
                      <small className="text-brand font-bold" style={{textTransform: 'uppercase'}}>{msg.role}</small>
                      <p style={{marginTop: "var(--space-2)"}}>{msg.content}</p>
                    </div>
                  ))
                )}
                {loading && (
                  <div className="message assistant">
                    <small className="text-brand font-bold">ASSISTANT</small>
                    <div style={{marginTop: "var(--space-2)"}}>
                      <Skeleton style={{width: "80%", marginBottom: "8px"}} />
                      <Skeleton style={{width: "60%"}} />
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", gap: "var(--space-3)" }}>
                <input 
                  type="text" 
                  className="input" 
                  placeholder={t.inputPlaceholder}
                  value={prompt}
                  onChange={e => setPrompt(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && submitMessage()}
                />
                <Button onClick={submitMessage} loading={loading}>{t.execute}</Button>
              </div>
            </Card>

            {/* Right Column: Metrics / Telemetry */}
            <div className="col-lg-4 col-md-12" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
              <Card>
                <h3 className="mb-4">{t.telemetry}</h3>
                <div className="grid" style={{ "--grid-columns": 2 }}>
                  <MetricTile label={t.metrics.latency} value={loading ? "..." : `${metrics.latencyMs || 0}ms`} />
                  <MetricTile label={t.metrics.tokens} value={metrics.promptTokens ? `${metrics.promptTokens}/${metrics.completionTokens}` : "0/0"} />
                  <MetricTile label={t.metrics.cost} value={costText} />
                  <MetricTile label={t.metrics.memory} value={status.cwd ? "Mounted" : "Healthy"} />
                </div>
              </Card>

              <Card>
                <h3 className="mb-2">{t.contextWindow}</h3>
                <p className="mb-4 text-xs text-muted" style={{wordBreak: "break-all"}}>{status.cwd}</p>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px", fontSize: "14px", color: "var(--text-secondary)" }}>
                  <input type="checkbox" checked={allowWrite} onChange={e => setAllowWrite(e.target.checked)} />
                  <span>{t.permissions.write}</span>
                </label>
                <div className="text-muted text-xs" style={{ marginBottom: "16px" }}>{t.permissions.writeHint}</div>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px", fontSize: "14px", color: "var(--text-secondary)" }}>
                  <input type="checkbox" checked={allowCommand} onChange={e => setAllowCommand(e.target.checked)} />
                  <span>{t.permissions.command}</span>
                </label>
                <div className="text-muted text-xs" style={{ marginBottom: "16px" }}>{t.permissions.commandHint}</div>
                {loading ? (
                  <div style={{display: 'flex', flexDirection: 'column', gap: '8px'}}>
                    <Skeleton />
                    <Skeleton />
                    <Skeleton />
                  </div>
                ) : (
                  <div className="text-muted text-xs" style={{fontFamily: "monospace", padding: "var(--space-3)", background: "var(--bg-app)", borderRadius: "var(--radius-md)", maxHeight: "200px", overflowY: "auto"}}>
                    {toolLogs.length > 0 ? (
                      toolLogs.map((log, i) => (
                        <div key={i} style={{marginBottom: "4px", paddingBottom: "4px", borderBottom: "1px solid var(--border-subtle)"}}>{log}</div>
                      ))
                    ) : (
                      t.contextLogs.map((log, i) => (
                        <React.Fragment key={i}>
                          {log}<br/>
                        </React.Fragment>
                      ))
                    )}
                  </div>
                )}
              </Card>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <aside className="sidebar card">
        <div className="brand mb-4">
          <div className="brand-mark"></div>
          <div>
            <h2 className="text-brand">{t.title}</h2>
            <small className="text-muted">{t.subtitle}</small>
          </div>
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          {["dashboard", "workflows", "knowledge", "settings"].map(nav => (
            <div 
              key={nav} 
              className={`nav-item ${activeTab === nav ? "active" : ""}`}
              onClick={() => setActiveTab(nav)}
              role="button"
              tabIndex={0}
            >
              <span>{t.nav[nav]}</span>
            </div>
          ))}
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="topbar card">
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center" }}>
            <span className="status-chip">{t.status.model}: {status.model}</span>
            <span className="status-chip">{t.status.status}: {loading ? t.status.running : t.status.standby}</span>
            <div className="status-chip" style={{ background: "transparent", border: "none" }}>
              <select 
                value={activeSessionId} 
                onChange={(e) => setActiveSessionId(e.target.value)}
                style={{ background: "var(--bg-glass)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "4px 8px" }}
              >
                {sessions.map((session) => {
                  const title = session.title || session.name;
                  return (
                    <option key={session.id} value={session.id}>
                      {title}
                    </option>
                  );
                })}
              </select>
            </div>
          </div>
          <div style={{ display: "flex", gap: "var(--space-3)" }}>
            <Button variant="ghost" onClick={createSession}>+ New</Button>
            <Button variant="ghost" onClick={toggleLang}>
              {lang === "en" ? "中" : "EN"}
            </Button>
            <Button variant="ghost" onClick={toggleTheme}>
              {theme === "dark" ? t.theme.light : t.theme.dark}
            </Button>
            {loading ? (
              <Button variant="danger" onClick={stopExecution}>Stop</Button>
            ) : (
              <Button variant="danger" onClick={resetSession}>{t.reset}</Button>
            )}
          </div>
        </header>

        {renderContent()}
      </main>
    </div>
  );
}
