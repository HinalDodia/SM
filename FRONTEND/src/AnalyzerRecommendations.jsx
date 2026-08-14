import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchRecommendations } from "./api";
import LoginPrompt from "./LoginPrompt";
import { TrendingUp, TrendingDown, Minus, Info } from "lucide-react";

export default function AnalyzerRecommendations() {
  const stored = JSON.parse(localStorage.getItem("user") || "{}");
  const uid = stored?.userid || null;

  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [profileMissing, setProfileMissing] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  useEffect(() => {
    if (!uid) return;

    async function loadRecommendations() {
      setLoading(true);
      setErrorMsg(null);
      setProfileMissing(false);

      try {
        const res = await fetchRecommendations(uid);

        if (res && res.error) {
          if (res.error.toLowerCase().includes("profile")) {
            setProfileMissing(true);
          } else {
            setErrorMsg(res.error);
          }
        } else if (res && Array.isArray(res.recommendations)) {
          setRecommendations(res.recommendations);
        } else {
          setRecommendations([]);
        }
      } catch (err) {
        console.error("Error fetching recommendations:", err);
        setErrorMsg("Failed to load stock recommendations. Please try again later.");
      } finally {
        setLoading(false);
      }
    }

    loadRecommendations();
  }, [uid]);

  if (!uid) {
    return (
      <LoginPrompt
        title="Sign in required"
        message="Please sign in to access personalized AI recommendations."
      />
    );
  }

  const getBadgeStyle = (action) => {
    const act = (action || "").toLowerCase();
    if (act === "buy") {
      return {
        bg: "rgba(34, 197, 94, 0.15)",
        color: "#4ade80",
        border: "rgba(34, 197, 94, 0.3)",
        icon: <TrendingUp size={18} />,
      };
    }
    if (act === "sell") {
      return {
        bg: "rgba(239, 68, 68, 0.15)",
        color: "#f87171",
        border: "rgba(239, 68, 68, 0.3)",
        icon: <TrendingDown size={18} />,
      };
    }
    return {
      bg: "rgba(245, 158, 11, 0.15)",
      color: "#fbbf24",
      border: "rgba(245, 158, 11, 0.3)",
      icon: <Minus size={18} />,
    };
  };

  return (
    <div style={{ padding: "32px 24px", maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ marginBottom: 28 }}>
        <h1 className="dash__title">Personal Stock Analyzer</h1>
        <p className="dash__subtitle">
          AI-driven, data-grounded stock recommendations tailored to your risk profile and investment goals.
        </p>
      </div>

      {loading && (
        <div className="ultra-card" style={{ textAlign: "center", padding: "60px 24px" }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: "#2dd4bf", marginBottom: 8 }}>
            Analyzing Market Data & Generating Explanations...
          </div>
          <p style={{ color: "#9aa", fontSize: 14, maxWidth: 500, margin: "0 auto" }}>
            Evaluating 10 tracked symbols against your risk tolerance and financial metrics. This may take a few seconds.
          </p>
        </div>
      )}

      {!loading && profileMissing && (
        <div className="ultra-card" style={{ textAlign: "center", padding: "48px 24px" }}>
          <div style={{ marginBottom: 16 }}>
            <Info size={48} color="#2dd4bf" style={{ margin: "0 auto" }} />
          </div>
          <h2 style={{ marginBottom: 8 }}>No Investment Profile Found</h2>
          <p style={{ color: "#9aa", marginBottom: 24, maxWidth: 520, margin: "0 auto 24px" }}>
            To generate personalized stock recommendations, you must first set up your risk profile, capital budget, and investment horizon.
          </p>
          <Link to="/analyzer/profile" className="btn-primary" style={{ padding: "10px 20px" }}>
            Set Up Your Profile
          </Link>
        </div>
      )}

      {!loading && !profileMissing && errorMsg && (
        <div
          style={{
            padding: "16px 20px",
            borderRadius: 8,
            backgroundColor: "rgba(239, 68, 68, 0.15)",
            color: "#f87171",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            marginBottom: 24,
          }}
        >
          {errorMsg}
        </div>
      )}

      {!loading && !profileMissing && !errorMsg && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: 20,
          }}
        >
          {recommendations.map((rec) => {
            const badge = getBadgeStyle(rec.action);
            const isBuy = (rec.action || "").toLowerCase() === "buy";
            const amount = parseFloat(rec.suggested_amount || 0);

            return (
              <div
                key={rec.symbol}
                className="ultra-card"
                style={{
                  display: "flex",
                  flexDirection: "column",
                  justify: "space-between",
                  borderRadius: 12,
                  padding: 20,
                }}
              >
                {/* Header: Symbol + Action Badge */}
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      marginBottom: 12,
                    }}
                  >
                    <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: "0.5px" }}>
                      {rec.symbol}
                    </span>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        padding: "4px 12px",
                        borderRadius: 20,
                        fontSize: 13,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        backgroundColor: badge.bg,
                        color: badge.color,
                        border: `1px solid ${badge.border}`,
                      }}
                    >
                      {badge.icon}
                      {rec.action}
                    </span>
                  </div>

                  {/* Score & Suggested Amount */}
                  <div
                    style={{
                      display: "flex",
                      gap: 16,
                      fontSize: 14,
                      color: "#9aa",
                      marginBottom: 16,
                      paddingBottom: 12,
                      borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                    }}
                  >
                    <div>
                      Score: <strong style={{ color: "#fff" }}>{rec.score}/10</strong>
                    </div>
                    {isBuy && amount > 0 && (
                      <div>
                        Suggested Allocation:{" "}
                        <strong style={{ color: "#4ade80" }}>₹{amount.toLocaleString("en-IN")}</strong>
                      </div>
                    )}
                  </div>

                  {/* Explanation text if present */}
                  {rec.explanation ? (
                    <p style={{ fontSize: 14, lineHeight: "1.5", color: "#e2e8f0", marginBottom: 16 }}>
                      {rec.explanation}
                    </p>
                  ) : null}

                  {/* Factual Grounding Reasons */}
                  {Array.isArray(rec.reasons) && rec.reasons.length > 0 && (
                    <div style={{ marginTop: "auto" }}>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 600,
                          color: "#64748b",
                          textTransform: "uppercase",
                          letterSpacing: "0.5px",
                          marginBottom: 6,
                        }}
                      >
                        Signal Factors
                      </div>
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: "#94a3b8" }}>
                        {rec.reasons.map((r, i) => (
                          <li key={i} style={{ marginBottom: 4 }}>
                            {r}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
