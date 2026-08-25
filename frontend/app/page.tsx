"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface Message {
  id: string;
  sender: "user" | "ai";
  text: string;
  intent?: string;
  sources?: string[];
  analytics?: any;
  timestamp?: string;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
}

interface QuestionCategory {
  id: string;
  label: string;
  questions: string[];
}

const QUESTION_CATEGORIES: QuestionCategory[] = [
  {
    id: "popular",
    label: "Popular",
    questions: [
      "Who won Monaco 2024?",
      "Compare Norris and Leclerc's race strategies.",
      "Give a data-backed comparison of Norris and Leclerc."
    ]
  },
  {
    id: "pace",
    label: "Pace & Telemetry",
    questions: [
      "Why was Leclerc faster than Norris in qualifying?",
      "Where did Leclerc gain time?",
      "Compare their sector performance."
    ]
  },
  {
    id: "strategy",
    label: "Tyres & Pit Stops",
    questions: [
      "What tyres did Norris use?",
      "What happened during their pit strategies?",
      "Which driver had better tyre degradation?"
    ]
  },
  {
    id: "quotes",
    label: "Team Statements",
    questions: [
      "What did the drivers/teams say about the race?",
      "What were Ferrari's strategy comments?"
    ]
  }
];

const LOADER_STEPS = [
  "Classifying query intent",
  "Traversing Neo4j Context Graph",
  "Searching Qdrant Vector Cloud",
  "Synthesizing LLM response"
];

const WELCOME_MESSAGE: Message = {
  id: "1",
  sender: "ai",
  text: "Welcome to **DRS AI** — your Data Retrieval System for Formula 1.\n\nI provide in-depth analytics for the **2024 Monaco Grand Prix**, comparing **Charles Leclerc (Ferrari)** and **Lando Norris (McLaren)** across Qualifying & Race sessions. Ask me anything.",
  sources: ["FastF1 Telemetry", "PostgreSQL", "Neo4j Context Graph", "Qdrant Vector Cloud"],
};

function createNewSession(): ChatSession {
  return {
    id: Date.now().toString(),
    title: "New Analysis",
    messages: [WELCOME_MESSAGE],
    createdAt: new Date().toISOString(),
  };
}

function FormattedAnswer({ text }: { text: string }) {
  const cleaned = text
    .replace(/\*\*(Answer|Evidence|Analysis|Context|Sources):\*\*/gi, "")
    .trim();

  const paragraphs = cleaned.split(/\n\s*\n/);

  return (
    <div className="message-text-wrapper">
      {paragraphs.map((para, pIdx) => {
        const lines = para.split("\n").filter((l) => l.trim().length > 0);
        return (
          <div key={pIdx} className="para-block">
            {lines.map((line, lIdx) => {
              const trimmed = line.trim();
              const isBullet = trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ");
              const content = isBullet ? trimmed.replace(/^[-*•]\s*/, "") : line;

              const parts = content.split(/(\*\*.*?\*\*)/g);
              const formattedContent = parts.map((part, partIdx) => {
                if (part.startsWith("**") && part.endsWith("**")) {
                  return <strong key={partIdx}>{part.slice(2, -2)}</strong>;
                }
                return part;
              });

              if (isBullet) {
                return (
                  <div key={lIdx} className="bullet-row">
                    <span className="bullet-mark">•</span>
                    <span>{formattedContent}</span>
                  </div>
                );
              }

              return <p key={lIdx} className="text-paragraph">{formattedContent}</p>;
            })}
          </div>
        );
      })}
    </div>
  );
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loaderStep, setLoaderStep] = useState(0);
  const [activeCategory, setActiveCategory] = useState("popular");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Load sessions from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("drs-ai-sessions");
    if (saved) {
      try {
        const parsed: ChatSession[] = JSON.parse(saved);
        if (parsed.length > 0) {
          setSessions(parsed);
          setActiveSessionId(parsed[0].id);
          return;
        }
      } catch {}
    }
    const first = createNewSession();
    setSessions([first]);
    setActiveSessionId(first.id);
  }, []);

  // Persist sessions to localStorage
  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem("drs-ai-sessions", JSON.stringify(sessions));
    }
  }, [sessions]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [sessions, loading]);

  useEffect(() => {
    let interval: any;
    if (loading) {
      setLoaderStep(0);
      interval = setInterval(() => {
        setLoaderStep((prev) => (prev < LOADER_STEPS.length - 1 ? prev + 1 : prev));
      }, 1100);
    }
    return () => clearInterval(interval);
  }, [loading]);

  const activeSession = sessions.find(s => s.id === activeSessionId);
  const messages = activeSession?.messages || [];

  const updateActiveMessages = useCallback((updater: (prev: Message[]) => Message[]) => {
    setSessions(prev => prev.map(s =>
      s.id === activeSessionId ? { ...s, messages: updater(s.messages) } : s
    ));
  }, [activeSessionId]);

  const startNewChat = () => {
    const newSession = createNewSession();
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };

  const switchSession = (id: string) => {
    setActiveSessionId(id);
  };

  const deleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== id);
      if (filtered.length === 0) {
        const newSession = createNewSession();
        setActiveSessionId(newSession.id);
        return [newSession];
      }
      if (activeSessionId === id) {
        setActiveSessionId(filtered[0].id);
      }
      return filtered;
    });
  };

  const sendMessage = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text: query,
      timestamp: timeStr
    };

    // Update session title from first user message
    const isFirstUserMsg = messages.filter(m => m.sender === "user").length === 0;
    if (isFirstUserMsg) {
      setSessions(prev => prev.map(s =>
        s.id === activeSessionId
          ? { ...s, title: query.length > 40 ? query.slice(0, 40) + "..." : query, messages: [...s.messages, userMsg] }
          : s
      ));
    } else {
      updateActiveMessages(prev => [...prev, userMsg]);
    }

    if (!textToSend) setInput("");
    setLoading(true);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const res = await fetch(`${backendUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.statusText}`);
      }

      const data = await res.json();
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: "ai",
        text: data.answer,
        intent: data.intent,
        sources: data.sources,
        analytics: data.analytics,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      updateActiveMessages(prev => [...prev, aiMsg]);
    } catch (err: any) {
      updateActiveMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "ai",
          text: `Connection Error: ${err.message}\n\nPlease verify backend server is running via \`python -m uvicorn app.main:app --reload --port 8000\`.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const currentCategoryObj = QUESTION_CATEGORIES.find(c => c.id === activeCategory) || QUESTION_CATEGORIES[0];

  const formatSessionDate = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1) return "Just now";
      if (mins < 60) return `${mins}m ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24) return `${hrs}h ago`;
      return d.toLocaleDateString([], { month: "short", day: "numeric" });
    } catch {
      return "";
    }
  };

  return (
    <div className="app-shell">
      {/* History Sidebar */}
      <aside className={`history-sidebar ${sidebarOpen ? "open" : "collapsed"}`}>
        <div className="sidebar-header">
          <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="2" y="3" width="12" height="1.5" rx="0.75" fill="currentColor"/>
              <rect x="2" y="7.25" width="12" height="1.5" rx="0.75" fill="currentColor"/>
              <rect x="2" y="11.5" width="12" height="1.5" rx="0.75" fill="currentColor"/>
            </svg>
          </button>
          {sidebarOpen && (
            <button className="new-chat-btn" onClick={startNewChat}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              New Analysis
            </button>
          )}
        </div>

        {sidebarOpen && (
          <div className="session-list">
            {sessions.map(session => (
              <div
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? "active" : ""}`}
                onClick={() => switchSession(session.id)}
              >
                <div className="session-item-content">
                  <div className="session-title">{session.title}</div>
                  <div className="session-meta">
                    {session.messages.filter(m => m.sender === "user").length} queries · {formatSessionDate(session.createdAt)}
                  </div>
                </div>
                {sessions.length > 1 && (
                  <button className="session-delete" onClick={(e) => deleteSession(session.id, e)}>
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* Main Content */}
      <div className="main-content">
        <div className="container">
          {/* Header Banner */}
          <header className="header">
            <div className="header-top">
              <div className="brand-wrapper">
                <div className="f1-logo-badge">F1</div>
                <div>
                  <h1 className="title">
                    DRS AI <span className="title-tag">MONACO 2024</span>
                  </h1>
                  <p className="subtitle">
                    FastF1 + OpenF1 // Neo4j + Qdrant + Gemini LLM
                  </p>
                </div>
              </div>

              <div className="system-status-pills">
                <div className="status-pill">
                  <span className="status-dot"></span>
                  FastAPI :8000
                </div>
                <div className="status-pill">
                  <span className="status-dot"></span>
                  Qdrant Cloud
                </div>
                <div className="status-pill">
                  <span className="status-dot"></span>
                  Neo4j Aura
                </div>
              </div>
            </div>

            {/* Driver Spotlight Header */}
            <div className="driver-spotlight-bar">
              <div className="driver-card ferrari">
                <div className="driver-info">
                  <span className="driver-number">16</span>
                  <div>
                    <div className="driver-name">Charles Leclerc</div>
                    <div className="driver-team">Scuderia Ferrari • SF-24</div>
                  </div>
                </div>
                <div className="driver-stats">
                  <div className="stat-winner">RACE WINNER (P1)</div>
                  <div className="stat-time">Quali: 1:10.270</div>
                </div>
              </div>

              <div className="driver-card mclaren">
                <div className="driver-info">
                  <span className="driver-number">4</span>
                  <div>
                    <div className="driver-name">Lando Norris</div>
                    <div className="driver-team">McLaren F1 Team • MCL38</div>
                  </div>
                </div>
                <div className="driver-stats">
                  <div>P4 Finish</div>
                  <div className="stat-time">Quali: 1:10.542</div>
                </div>
              </div>
            </div>
          </header>

          {/* Main Content Layout */}
          <div className="main-layout">
            {/* Chat Panel */}
            <div className="chat-panel">
              <div className="chat-container">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`message-card ${
                      msg.sender === "user" ? "user-message" : "ai-message"
                    }`}
                  >
                    <div className="message-header-row">
                      <div className="message-sender">
                        {msg.sender === "user" ? "USER QUERY" : "DRS AI"}
                      </div>
                      {msg.timestamp && (
                        <span className="message-time">{msg.timestamp}</span>
                      )}
                    </div>

                    <div className="message-body">
                      {msg.sender === "ai" ? (
                        <FormattedAnswer text={msg.text} />
                      ) : (
                        msg.text
                      )}
                    </div>

                    {msg.sender === "ai" && (msg.intent || msg.sources) && (
                      <div className="provenance-bar">
                        {msg.intent && (
                          <span className="badge intent">
                            Intent: {msg.intent}
                          </span>
                        )}
                        {msg.sources?.map((src) => (
                          <span key={src} className="badge source">
                            {src}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {loading && (
                  <div className="telemetry-loader">
                    <div className="loader-header">
                      <div className="loader-status-text">
                        <div className="pulse-spinner"></div>
                        {LOADER_STEPS[loaderStep]}
                      </div>
                      <span style={{ fontSize: "0.68rem", color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                        PIPELINE ACTIVE
                      </span>
                    </div>
                    <div className="loader-progress-track">
                      <div
                        className="loader-progress-bar"
                        style={{ width: `${((loaderStep + 1) / LOADER_STEPS.length) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Categorized Suggested Questions */}
              <div className="suggested-questions-panel">
                <div className="questions-header">
                  <span>SUGGESTED QUESTIONS</span>
                </div>

                <div className="questions-tabs">
                  {QUESTION_CATEGORIES.map((cat) => (
                    <button
                      key={cat.id}
                      className={`tab-btn ${activeCategory === cat.id ? "active" : ""}`}
                      onClick={() => setActiveCategory(cat.id)}
                    >
                      {cat.label}
                    </button>
                  ))}
                </div>

                <div className="demo-questions-grid">
                  {currentCategoryObj.questions.map((q, idx) => (
                    <button
                      key={idx}
                      className="demo-btn"
                      onClick={() => sendMessage(q)}
                      disabled={loading}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Input Form */}
              <form
                className="input-container"
                onSubmit={(e) => {
                  e.preventDefault();
                  sendMessage();
                }}
              >
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask about Monaco 2024 telemetry, tyre stints, sector pace..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={loading}
                />
                <button type="submit" className="send-button" disabled={loading}>
                  Send
                </button>
              </form>
            </div>

            {/* Telemetry Visualizer Side Widget */}
            <aside className="telemetry-widget-card">
              {/* Sector Times Section */}
              <div className="widget-section">
                <div className="widget-title">
                  Qualifying Sector Deltas
                </div>

                <div className="sector-bar-container">
                  <div className="sector-row">
                    <div className="sector-header">
                      <span>S1 — Sainte Dévote</span>
                      <span>LEC −0.112s</span>
                    </div>
                    <div className="sector-progress-track">
                      <div className="sector-bar-lec" style={{ width: "54%" }}></div>
                      <div className="sector-bar-nor" style={{ width: "46%" }}></div>
                    </div>
                  </div>

                  <div className="sector-row">
                    <div className="sector-header">
                      <span>S2 — Casino / Tunnel</span>
                      <span>LEC −0.104s</span>
                    </div>
                    <div className="sector-progress-track">
                      <div className="sector-bar-lec" style={{ width: "53%" }}></div>
                      <div className="sector-bar-nor" style={{ width: "47%" }}></div>
                    </div>
                  </div>

                  <div className="sector-row">
                    <div className="sector-header">
                      <span>S3 — Swimming Pool</span>
                      <span>LEC −0.056s</span>
                    </div>
                    <div className="sector-progress-track">
                      <div className="sector-bar-lec" style={{ width: "51%" }}></div>
                      <div className="sector-bar-nor" style={{ width: "49%" }}></div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Tyre Stint Section */}
              <div className="widget-section">
                <div className="widget-title">
                  Race Tyre Strategy
                </div>

                <div className="stint-card" style={{ borderLeftColor: "var(--ferrari-red)", borderLeftWidth: "2px" }}>
                  <div className="stint-driver" style={{ color: "var(--ferrari-red)" }}>LEC — P1</div>
                  <div className="stint-detail">Medium L1–15 → Hard L16–78</div>
                </div>

                <div className="stint-card" style={{ borderLeftColor: "var(--mclaren-papaya)", borderLeftWidth: "2px" }}>
                  <div className="stint-driver" style={{ color: "var(--mclaren-papaya)" }}>NOR — P4</div>
                  <div className="stint-detail">Medium L1–15 → Hard L16–78</div>
                </div>
              </div>

              {/* Legend */}
              <div className="widget-section" style={{ paddingTop: "8px", paddingBottom: "8px" }}>
                <div style={{ display: "flex", gap: "14px", justifyContent: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "5px", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.58rem", color: "var(--text-muted)" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "2px", background: "var(--ferrari-red)" }}></div>
                    LEC
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "5px", fontFamily: "'JetBrains Mono', monospace", fontSize: "0.58rem", color: "var(--text-muted)" }}>
                    <div style={{ width: "8px", height: "8px", borderRadius: "2px", background: "var(--mclaren-papaya)" }}></div>
                    NOR
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
