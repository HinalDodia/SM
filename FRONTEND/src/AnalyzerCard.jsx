/**
 * AnalyzerCard — reusable per-stock AI analyzer card.
 *
 * Props:
 *   symbol   {string}  - Stock ticker, e.g. "RELIANCE"
 *   userId   {number}  - Authenticated user ID
 *   context  {string}  - "dashboard" | "market" | "watchlist" | "portfolio" | "predict"
 *   holding  {object}  - Optional: { qty, avgPrice } — passed for portfolio context only.
 *                        The backend looks up position data server-side; this prop is
 *                        not sent to the server but can be used for local display hints.
 *
 * Behaviour:
 *   - Fetches independently — never blocks surrounding page content.
 *   - Shows an inline skeleton while loading.
 *   - Shows an inline "Set up your profile" message on 404 (no profile).
 *   - Shows a compact error note on other failures.
 *   - Action buttons are NOT rendered here — each page adds its own below/beside.
 */

import React, { useEffect, useState, useCallback } from "react";
import { fetchAnalyzerRecommendation } from "./api";
import OnboardingModal from "./OnboardingModal";
import "./AnalyzerCard.css";

/* ── Label text by context ───────────────────────────────────── */
function cardLabel(context, symbol) {
  if (context === "dashboard") return "YOUR PERSONAL ANALYZER";
  return `ANALYZER · ${symbol}`;
}

/* ── Action badge ────────────────────────────────────────────── */
const ACTION_META = {
  buy:  { emoji: "↑", cls: "az-badge--buy",  text: "BUY"  },
  sell: { emoji: "↓", cls: "az-badge--sell", text: "SELL" },
  hold: { emoji: "→", cls: "az-badge--hold", text: "HOLD" },
};

function ActionBadge({ action }) {
  const meta = ACTION_META[action] || ACTION_META.hold;
  return (
    <span className={`az-badge ${meta.cls}`}>
      <span>{meta.emoji}</span>
      {meta.text}
    </span>
  );
}

/* ── Loading skeleton ────────────────────────────────────────── */
function Skeleton() {
  return (
    <div className="az-skeleton">
      <div className="az-skel-line az-skel-line--header" />
      <div className="az-skel-line az-skel-line--title"  />
      <div className="az-skel-line az-skel-line--body"   />
      <div className="az-skel-line az-skel-line--body2"  />
      <div className="az-skel-line az-skel-line--body3"  />
      <div className="az-skel-line az-skel-line--box"    />
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────── */
export default function AnalyzerCard({ symbol, userId, context = "market", holding }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);   // { code, message }
  const [showOnboarding, setShowOnboarding] = useState(false);

  const load = useCallback(async () => {
    if (!symbol || !userId) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const rec = await fetchAnalyzerRecommendation(userId, symbol);
      setData(rec);
    } catch (err) {
      setError({ code: err.code || "error", message: err.message || "Failed to load." });
    } finally {
      setLoading(false);
    }
  }, [symbol, userId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="az-card">
      {/* ── Header ── */}
      <div className="az-header">
        <div className="az-label-group">
          <div className="az-icon" role="img" aria-label="AI Analyzer">🤖</div>
          <span className="az-label">{cardLabel(context, symbol)}</span>
        </div>

        {data && (
          <div className="az-conviction">
            <span className="az-conviction-arrow">↗</span>
            {data.conviction}% conviction
          </div>
        )}
      </div>

      {/* ── Body ── */}
      {loading && <Skeleton />}

      {!loading && error && error.code === "no_profile" && (
        <div className="az-empty">
          <span className="az-empty-icon">🔧</span>
          <span>Set up your profile to get a personal read&nbsp;</span>
          <button
            onClick={() => setShowOnboarding(true)}
            style={{
              background: "rgba(84,197,255,0.1)",
              border: "1px solid rgba(84,197,255,0.25)",
              borderRadius: 6,
              color: "#54c5ff",
              fontSize: 12,
              fontWeight: 700,
              padding: "4px 10px",
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Set Up →
          </button>
        </div>
      )}

      {!loading && error && error.code !== "no_profile" && (
        <div className="az-empty">
          <span className="az-empty-icon">⚠️</span>
          {error.message}
        </div>
      )}

      {!loading && data && (
        <>
          {/* Action badge */}
          <div className="az-action-row">
            <ActionBadge action={data.action} />
          </div>

          {/* Headline */}
          <p className="az-headline">{data.headline}</p>

          {/* Bullets */}
          {data.bullets && data.bullets.length > 0 && (
            <ul className="az-bullets">
              {data.bullets.map((b, i) => (
                <li key={i} className="az-bullet">
                  <span className="az-bullet-dot" />
                  {b}
                </li>
              ))}
            </ul>
          )}

          {/* Action plan */}
          {data.action_plan && (
            <div className="az-action-plan">
              <span className="az-action-label">Action plan:</span>
              <span className="az-action-text">{data.action_plan}</span>
            </div>
          )}
        </>
      )}

      {/* Onboarding modal — launched from the no-profile nudge */}
      {showOnboarding && userId && (
        <OnboardingModal
          userId={userId}
          onClose={() => setShowOnboarding(false)}
          onSaved={() => {
            setShowOnboarding(false);
            load();   // re-fetch now that profile exists
          }}
        />
      )}
    </div>
  );
}
