/**
 * ARIABubble.jsx
 *
 * ARIA — AI Stock Research Assistant floating chat bubble.
 * Mounted once in App.jsx inside the Router so useLocation works.
 *
 * - Reads userid from UserContext (falls back to localStorage)
 * - Detects current stock symbol from the URL automatically
 * - Sends last 3 turns of history with every message
 * - Renders **bold** markdown from ARIA's responses
 */

import { useState, useRef, useEffect, useContext } from "react";
import { useLocation } from "react-router-dom";
import { UserContext } from "../UserContext"; // UserContext lives in src/
import { API_URL } from "../config";          // matches the rest of the app

// ── Bold markdown renderer (**text** → <strong>) ──────────────────────────────
function renderMessage(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part.split("\n").map((line, j, arr) => (
      <span key={`${i}-${j}`}>
        {line}
        {j < arr.length - 1 && <br />}
      </span>
    ));
  });
}

// ── Extract stock symbol from current URL ────────────────────────────────────
function useCurrentSymbol() {
  const { pathname } = useLocation();
  const stockRoutes = [
    /^\/stock\/([A-Z0-9^.&-]+)/i,
    /^\/chart\/([A-Z0-9^.&-]+)/i,
    /^\/earnings\/([A-Z0-9^.&-]+)/i,
    /^\/financials\/([A-Z0-9^.&-]+)/i,
    /^\/dividend\/([A-Z0-9^.&-]+)/i,
    /^\/sec\/([A-Z0-9^.&-]+)/i,
    /^\/news\/([A-Z0-9^.&-]+)/i,
    /^\/insiders\/([A-Z0-9^.&-]+)/i,
    /^\/ownership\/([A-Z0-9^.&-]+)/i,
    /^\/trends\/([A-Z0-9^.&-]+)/i,
    /^\/options\/([A-Z0-9^.&-]+)/i,
    /^\/shortinterest\/([A-Z0-9^.&-]+)/i,
  ];
  for (const pattern of stockRoutes) {
    const match = pathname.match(pattern);
    if (match) return match[1].toUpperCase();
  }
  return "";
}

// ── Main component ────────────────────────────────────────────────────────────
export default function ARIABubble() {
  const { user } = useContext(UserContext) || {};
  const userid =
    user?.userid ??
    JSON.parse(localStorage.getItem("user") || "{}")?.userid ??
    null;

  const currentSymbol = useCurrentSymbol();

  const [open, setOpen]       = useState(false);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]); // { role, content }[]
  const [error, setError]     = useState(null);
  const bottomRef = useRef(null);
  const inputRef  = useRef(null);
  const panelRef  = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 120);
  }, [open]);

  // Reset error when user starts typing
  useEffect(() => { setError(null); }, [input]);

  // ── Send message ────────────────────────────────────────────────────────────
  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setError(null);

    const newHistory = [...history, { role: "user", content: userMessage }];
    setHistory(newHistory);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userid,
          message:        userMessage,
          current_symbol: currentSymbol,
          history:        history.slice(-6), // last 3 turns
        }),
      });

      const data = await res.json();
      if (!res.ok || data.status === "error") {
        throw new Error(data.error || "Something went wrong");
      }

      setHistory(h => [...h, { role: "assistant", content: data.reply }]);
    } catch (err) {
      setError(err.message || "Could not reach ARIA. Try again.");
      setHistory(h => h.slice(0, -1));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const clearChat = () => setHistory([]);

  // ── Context-aware starter questions ─────────────────────────────────────────
  const starters = currentSymbol
    ? [
        `Is ${currentSymbol} fundamentally strong?`,
        `What are risks of ${currentSymbol}?`,
        `${currentSymbol} PE ratio analysis`,
      ]
    : [
        "What is PE ratio?",
        "How to read a balance sheet?",
        "What is diversification?",
      ];

  return (
    <>
      {/* ── Global keyframes & utility classes ──────────────────────────────── */}
      <style>{`
        @keyframes ariaSlideUp {
          from { opacity: 0; transform: translateY(24px) scale(0.94); }
          to   { opacity: 1; transform: translateY(0)   scale(1);    }
        }
        @keyframes ariaDot {
          0%, 80%, 100% { transform: scale(0.55); opacity: 0.35; }
          40%            { transform: scale(1);   opacity: 1;    }
        }
        @keyframes ariaPillPulse {
          0%   { box-shadow: 0 6px 28px rgba(15,52,96,0.7), 0 0 0 0   rgba(99,179,237,0.7); }
          70%  { box-shadow: 0 6px 28px rgba(15,52,96,0.7), 0 0 0 16px rgba(99,179,237,0); }
          100% { box-shadow: 0 6px 28px rgba(15,52,96,0.7), 0 0 0 0   rgba(99,179,237,0); }
        }
        @keyframes ariaFloat {
          0%, 100% { transform: translateY(0px); }
          50%       { transform: translateY(-4px); }
        }
        @keyframes ariaGlow {
          0%, 100% { box-shadow: 0 6px 28px rgba(15,52,96,0.7), 0 0 20px rgba(99,179,237,0.15); }
          50%       { box-shadow: 0 6px 36px rgba(15,52,96,0.9), 0 0 36px rgba(99,179,237,0.35); }
        }
        .aria-pill-btn {
          animation: ariaFloat 3s ease-in-out infinite, ariaGlow 3s ease-in-out infinite;
        }
        .aria-pill-btn:hover {
          transform: translateY(-3px) scale(1.03) !important;
          animation: none !important;
          box-shadow: 0 10px 40px rgba(15,52,96,0.9), 0 0 48px rgba(99,179,237,0.4) !important;
        }
        .aria-pill-btn:active {
          transform: scale(0.97) !important;
        }
        .aria-send:hover:not(:disabled) {
          background: linear-gradient(135deg, #1e4d8c, #2d6bc4) !important;
          transform: scale(1.05);
        }
        .aria-starter {
          padding: 6px 13px;
          border-radius: 20px;
          background: rgba(99,179,237,0.07);
          border: 1px solid rgba(99,179,237,0.22);
          color: #63b3ed;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.15s ease;
          white-space: nowrap;
          font-family: inherit;
          line-height: 1.5;
        }
        .aria-starter:hover {
          background: rgba(99,179,237,0.16);
          border-color: rgba(99,179,237,0.45);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(99,179,237,0.15);
        }
        .aria-messages::-webkit-scrollbar { width: 3px; }
        .aria-messages::-webkit-scrollbar-track { background: transparent; }
        .aria-messages::-webkit-scrollbar-thumb {
          background: rgba(99,179,237,0.2);
          border-radius: 2px;
        }
        .aria-input:focus {
          border-color: rgba(99,179,237,0.5) !important;
          box-shadow: 0 0 0 3px rgba(99,179,237,0.08) !important;
          outline: none;
        }
        .aria-user-bubble strong { color: #93c5fd; }
        .aria-ai-bubble strong   { color: #7dd3fc; }
        .aria-header-glow {
          background: linear-gradient(135deg, #0a1628 0%, #0f2444 50%, #0a1628 100%);
        }
      `}</style>

      {/* ── Pill Launcher Button ─────────────────────────────────────────────── */}
      <button
        className="aria-pill-btn"
        onClick={() => setOpen(o => !o)}
        aria-label={open ? "Close ARIA" : "Open ARIA chat assistant"}
        style={{
          position: "fixed",
          bottom: 30,
          right: 28,
          zIndex: 1200,
          height: 52,
          paddingLeft: open ? 20 : 16,
          paddingRight: 22,
          borderRadius: 999,
          background: open
            ? "linear-gradient(135deg, #0f2a50 0%, #1a3a6e 100%)"
            : "linear-gradient(135deg, #0f3460 0%, #1e4d8c 60%, #2563ae 100%)",
          border: "1.5px solid rgba(99,179,237,0.45)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          gap: 10,
          boxShadow: "0 6px 28px rgba(15,52,96,0.7)",
          transition: "transform 0.2s ease, box-shadow 0.2s ease, background 0.25s ease, padding 0.2s ease",
          outline: "none",
          userSelect: "none",
          whiteSpace: "nowrap",
        }}
      >
        {/* Icon */}
        <span style={{
          display: "flex", alignItems: "center", justifyContent: "center",
          width: 30, height: 30, borderRadius: "50%",
          background: "rgba(99,179,237,0.15)",
          flexShrink: 0,
          transition: "transform 0.3s ease",
          transform: open ? "rotate(90deg)" : "rotate(0deg)",
        }}>
          {open ? (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="#63b3ed" strokeWidth="2.8" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="#93c5fd" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              <circle cx="9"  cy="10" r="1.2" fill="#93c5fd"/>
              <circle cx="12" cy="10" r="1.2" fill="#93c5fd"/>
              <circle cx="15" cy="10" r="1.2" fill="#93c5fd"/>
            </svg>
          )}
        </span>

        {/* Label */}
        <span style={{
          display: "flex", flexDirection: "column",
          alignItems: "flex-start", lineHeight: 1.2,
        }}>
          <span style={{
            color: "#e8f4fd", fontWeight: 700, fontSize: 14,
            letterSpacing: "0.02em",
          }}>
            {open ? "Close" : "Ask ARIA"}
          </span>
          {!open && (
            <span style={{
              color: "rgba(99,179,237,0.7)",
              fontSize: 10.5,
              fontWeight: 400,
              letterSpacing: "0.01em",
            }}>
              AI Stock Research
            </span>
          )}
        </span>

        {/* Sparkle badge — only when closed */}
        {!open && (
          <span style={{
            marginLeft: 2,
            fontSize: 15,
            lineHeight: 1,
          }}>✨</span>
        )}
      </button>

      {/* ── Chat Panel ──────────────────────────────────────────────────────── */}
      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-label="ARIA Chat Assistant"
          style={{
            position: "fixed",
            bottom: 94,
            right: 28,
            zIndex: 1199,
            width: 420,
            height: 600,
            borderRadius: 22,
            background: "#0d1117",
            border: "1px solid rgba(99, 179, 237, 0.18)",
            boxShadow: "0 28px 80px rgba(0,0,0,0.8), 0 0 60px rgba(15,52,96,0.4), inset 0 1px 0 rgba(99,179,237,0.1)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            animation: "ariaSlideUp 0.28s cubic-bezier(0.34, 1.56, 0.64, 1)",
          }}
        >

          {/* ── Header ──────────────────────────────────────────────────────── */}
          <div
            className="aria-header-glow"
            style={{
              padding: "14px 16px 13px",
              borderBottom: "1px solid rgba(99, 179, 237, 0.12)",
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexShrink: 0,
              position: "relative",
            }}
          >
            {/* Avatar */}
            <div style={{
              width: 38, height: 38, borderRadius: "50%",
              background: "linear-gradient(135deg, #0f3460 0%, #1e4d8c 50%, #63b3ed 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
              boxShadow: "0 0 12px rgba(99,179,237,0.3)",
            }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="#e8f4fd" strokeWidth="2" strokeLinecap="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>

            {/* Name + subtitle */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                color: "#e8f4fd", fontWeight: 700, fontSize: 14.5,
                letterSpacing: "0.02em", lineHeight: 1.2,
              }}>
                ARIA
              </div>
              <div style={{ color: "rgba(99,179,237,0.65)", fontSize: 11, marginTop: 1 }}>
                AI Stock Research Assistant
              </div>
            </div>

            {/* Live status dot */}
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{
                width: 7, height: 7, borderRadius: "50%",
                background: "#4ade80",
                boxShadow: "0 0 6px rgba(74,222,128,0.7)",
              }}/>
              <span style={{ fontSize: 10, color: "rgba(74,222,128,0.8)", fontWeight: 500 }}>
                Online
              </span>
            </div>

            {/* Stock context pill */}
            {currentSymbol && (
              <div style={{
                padding: "3px 9px",
                borderRadius: 20,
                background: "rgba(99, 179, 237, 0.1)",
                border: "1px solid rgba(99, 179, 237, 0.28)",
                fontSize: 11,
                color: "#63b3ed",
                fontFamily: "'DM Mono', 'Fira Code', monospace",
                letterSpacing: "0.04em",
                flexShrink: 0,
              }}>
                📊 {currentSymbol}
              </div>
            )}

            {/* Clear button */}
            {history.length > 0 && (
              <button
                onClick={clearChat}
                title="Clear chat"
                style={{
                  background: "none", border: "none",
                  color: "rgba(99,179,237,0.45)", cursor: "pointer",
                  fontSize: 16, padding: "2px 4px", lineHeight: 1,
                  borderRadius: 4, transition: "color 0.15s",
                  flexShrink: 0,
                }}
                onMouseEnter={e => e.target.style.color = "rgba(99,179,237,0.85)"}
                onMouseLeave={e => e.target.style.color = "rgba(99,179,237,0.45)"}
              >
                ↺
              </button>
            )}
          </div>

          {/* ── Messages ────────────────────────────────────────────────────── */}
          <div
            className="aria-messages"
            style={{
              flex: 1, overflowY: "auto",
              padding: "16px 14px 8px",
              display: "flex", flexDirection: "column", gap: 10,
              scrollbarWidth: "thin",
              scrollbarColor: "rgba(99,179,237,0.15) transparent",
            }}
          >

            {/* Empty / welcome state */}
            {history.length === 0 && (
              <div style={{ textAlign: "center", padding: "8px 4px 0" }}>
                <div style={{ fontSize: 34, marginBottom: 10 }}>📈</div>
                <div style={{
                  color: "#8b949e", fontSize: 13, marginBottom: 18,
                  lineHeight: 1.6, padding: "0 8px",
                }}>
                  {currentSymbol
                    ? <>Ask me anything about <strong style={{ color: "#63b3ed" }}>{currentSymbol}</strong> or any Indian stock.</>
                    : "Ask me anything about Indian stocks, markets, or investing concepts."
                  }
                </div>

                {/* Divider */}
                <div style={{
                  fontSize: 10, color: "rgba(99,179,237,0.4)", marginBottom: 10,
                  letterSpacing: "0.1em", textTransform: "uppercase",
                }}>
                  — Try asking —
                </div>

                {/* Starters */}
                <div style={{
                  display: "flex", flexWrap: "wrap",
                  gap: 7, justifyContent: "center",
                }}>
                  {starters.map((q, i) => (
                    <button
                      key={i}
                      className="aria-starter"
                      onClick={() => {
                        setInput(q);
                        setTimeout(() => inputRef.current?.focus(), 50);
                      }}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Conversation bubbles */}
            {history.map((msg, i) => (
              <div
                key={i}
                className={msg.role === "user" ? "aria-user-bubble" : "aria-ai-bubble"}
                style={
                  msg.role === "user"
                    ? {
                        alignSelf: "flex-end",
                        maxWidth: "82%",
                        padding: "9px 13px",
                        borderRadius: "14px 14px 3px 14px",
                        background: "linear-gradient(135deg, #0f3460, #1e4d8c)",
                        color: "#e8f4fd",
                        fontSize: 13.5,
                        lineHeight: 1.6,
                        border: "1px solid rgba(99,179,237,0.2)",
                        boxShadow: "0 2px 8px rgba(15,52,96,0.4)",
                      }
                    : {
                        alignSelf: "flex-start",
                        maxWidth: "89%",
                        padding: "10px 13px",
                        borderRadius: "3px 14px 14px 14px",
                        background: "#161b22",
                        color: "#c9d1d9",
                        fontSize: 13.5,
                        lineHeight: 1.65,
                        border: "1px solid rgba(99,179,237,0.1)",
                        boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
                      }
                }
              >
                {msg.role === "assistant" && (
                  <div style={{
                    fontSize: 10, color: "#63b3ed", fontWeight: 700,
                    letterSpacing: "0.1em", marginBottom: 5,
                    textTransform: "uppercase", opacity: 0.9,
                  }}>
                    ARIA
                  </div>
                )}
                {renderMessage(msg.content)}
              </div>
            ))}

            {/* Typing indicator */}
            {loading && (
              <div style={{
                alignSelf: "flex-start",
                padding: "10px 14px",
                borderRadius: "3px 14px 14px 14px",
                background: "#161b22",
                border: "1px solid rgba(99,179,237,0.1)",
                display: "flex", gap: 5, alignItems: "center",
              }}>
                <span style={{ fontSize: 10, color: "#63b3ed", fontWeight: 700,
                  marginRight: 4, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                  ARIA
                </span>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{
                    width: 6, height: 6, borderRadius: "50%",
                    background: "#63b3ed",
                    animation: `ariaDot 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }}/>
                ))}
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{
                alignSelf: "flex-start",
                padding: "8px 12px",
                borderRadius: "3px 12px 12px 12px",
                background: "rgba(220,53,69,0.08)",
                border: "1px solid rgba(220,53,69,0.25)",
                color: "#f87171", fontSize: 12.5, lineHeight: 1.5,
              }}>
                ⚠ {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* ── Input bar ───────────────────────────────────────────────────── */}
          <div style={{
            padding: "10px 12px 12px",
            borderTop: "1px solid rgba(99,179,237,0.1)",
            display: "flex", gap: 8, flexShrink: 0,
            background: "rgba(13,17,23,0.98)",
          }}>
            <input
              ref={inputRef}
              id="aria-chat-input"
              className="aria-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                currentSymbol
                  ? `Ask about ${currentSymbol}…`
                  : "Ask about any stock…"
              }
              disabled={loading}
              maxLength={500}
              autoComplete="off"
              style={{
                flex: 1,
                padding: "9px 13px",
                borderRadius: 11,
                background: "#161b22",
                border: "1px solid rgba(99,179,237,0.2)",
                color: "#c9d1d9",
                fontSize: 13.5,
                fontFamily: "inherit",
                transition: "border-color 0.15s, box-shadow 0.15s",
              }}
            />
            <button
              className="aria-send"
              id="aria-send-btn"
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              aria-label="Send message"
              style={{
                padding: "9px 16px",
                borderRadius: 11,
                background: loading || !input.trim()
                  ? "rgba(99,179,237,0.07)"
                  : "linear-gradient(135deg, #0f3460, #1e4d8c)",
                border: "1px solid rgba(99,179,237,0.25)",
                color: loading || !input.trim()
                  ? "rgba(99,179,237,0.3)"
                  : "#63b3ed",
                fontSize: 19, cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                transition: "all 0.15s ease", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}
            >
              ↑
            </button>
          </div>

          {/* ── Footer branding ──────────────────────────────────────────────── */}
          <div style={{
            textAlign: "center", fontSize: 10,
            color: "rgba(99,179,237,0.25)", paddingBottom: 8,
            letterSpacing: "0.04em",
          }}>
            Powered by ARIA · AI may make mistakes
          </div>

        </div>
      )}
    </>
  );
}
