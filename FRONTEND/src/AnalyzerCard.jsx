/**
 * AnalyzerCard — reusable per-stock analyzer card.
 *
 * Props:
 *   symbol   {string}  — NSE ticker, e.g. "RELIANCE"
 *   userId   {number}  — logged-in user ID
 *   context  {string}  — "dashboard"|"market"|"watchlist"|"portfolio"|"predict"
 *   holding  {object?} — { totalquantity, averagebuyprice, ltp, profitorloss, percentage }
 *                         Pass only from Portfolio context; omit elsewhere.
 *
 * Action buttons are NOT rendered here — each consuming page owns its own buttons.
 * This card fetches independently and never blocks surrounding page content.
 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import { Bot, AlertCircle } from "lucide-react";
import { fetchAnalyzerRecommendation } from "./api";
import "./AnalyzerCard.css";

// Label text varies by context to match each page's screenshot
const CONTEXT_LABEL = {
  dashboard:  "YOUR PERSONAL ANALYZER",
  market:     "ANALYZER",
  watchlist:  "ANALYZER",
  portfolio:  "ANALYZER",
  predict:    "ANALYZER",
};

function badgeClass(action) {
  if (!action) return "az-badge az-badge--hold";
  return `az-badge az-badge--${action.toLowerCase()}`;
}

function SkeletonLoader() {
  return (
    <div className="az-skeleton" aria-label="Loading analyzer…">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="az-skel-line az-skel-line--short" style={{ height: 14 }} />
        <div className="az-skel-line" style={{ width: 50, height: 18 }} />
      </div>
      <div className="az-skel-line az-skel-line--medium" style={{ height: 13 }} />
      <div className="az-skel-line az-skel-line--full"   style={{ height: 11 }} />
      <div className="az-skel-line az-skel-line--full"   style={{ height: 11 }} />
      <div className="az-skel-line" style={{ width: "80%", height: 11 }} />
      <div className="az-skel-line az-skel-line--full"   style={{ height: 36, borderRadius: 10 }} />
    </div>
  );
}

export default function AnalyzerCard({ symbol, userId, context = "market", holding }) {
  const [rec, setRec]       = useState(null);
  const [loading, setLoad]  = useState(false);
  const [error, setError]   = useState(null);

  // Keep track of latest fetch to avoid stale-closure race
  const fetchKey = useRef(0);

  const load = useCallback(async () => {
    if (!symbol || !userId) return;

    const key = ++fetchKey.current;
    setLoad(true);
    setError(null);
    setRec(null);

    try {
      const data = await fetchAnalyzerRecommendation(userId, symbol);
      if (fetchKey.current !== key) return; // stale — another fetch started

      if (data?.error === "no_profile") {
        setError("no_profile");
      } else if (data?.error) {
        setError("fetch_failed");
      } else {
        setRec(data);
      }
    } catch {
      if (fetchKey.current !== key) return;
      setError("fetch_failed");
    } finally {
      if (fetchKey.current === key) setLoad(false);
    }
  }, [symbol, userId]);

  useEffect(() => { load(); }, [load]);

  const label = (context === "dashboard")
    ? CONTEXT_LABEL.dashboard
    : `${CONTEXT_LABEL[context] || "ANALYZER"} · ${symbol || ""}`;

  // ── Loading ──────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="az-card">
        <div className="az-card__header">
          <div className="az-card__label-row">
            <div className="az-card__icon">
              <Bot size={14} color="#54c5ff" />
            </div>
            <span className="az-card__label">{label}</span>
          </div>
        </div>
        <SkeletonLoader />
      </div>
    );
  }

  // ── Error states ─────────────────────────────────────────────────────────
  if (error === "no_profile") {
    return (
      <div className="az-card">
        <div className="az-card__header">
          <div className="az-card__label-row">
            <div className="az-card__icon">
              <Bot size={14} color="#54c5ff" />
            </div>
            <span className="az-card__label">{label}</span>
          </div>
        </div>
        <p className="az-notice">
          <AlertCircle size={13} />
          Set up your profile to get a personal read on {symbol}.
        </p>
      </div>
    );
  }

  if (error || !rec) {
    // Soft fail — don't show a broken UI element, just nothing or a minimal hint
    if (!symbol || !userId) return null;
    return (
      <div className="az-card">
        <div className="az-card__header">
          <div className="az-card__label-row">
            <div className="az-card__icon">
              <Bot size={14} color="#54c5ff" />
            </div>
            <span className="az-card__label">{label}</span>
          </div>
        </div>
        <p className="az-notice">
          <AlertCircle size={13} />
          Analyzer unavailable right now. Try again shortly.
        </p>
      </div>
    );
  }

  // ── Data ─────────────────────────────────────────────────────────────────
  const action    = rec.action  || "hold";
  const conv      = rec.conviction ?? 0;
  const headline  = rec.headline  || "";
  const bullets   = Array.isArray(rec.bullets) ? rec.bullets : [];
  const actionPlan = rec.action_plan || "";

  return (
    <div className="az-card" data-testid={`az-card-${symbol}`}>
      {/* Header */}
      <div className="az-card__header">
        <div className="az-card__label-row">
          <div className="az-card__icon">
            <Bot size={14} color="#54c5ff" />
          </div>
          <span className="az-card__label">{label}</span>
        </div>
        <div className="az-card__right">
          <span className={badgeClass(action)}>{action.toUpperCase()}</span>
          <span className="az-conviction">↗ <span>{conv}%</span> conviction</span>
        </div>
      </div>

      {/* Headline */}
      {headline && <p className="az-headline">{headline}</p>}

      {/* Bullets */}
      {bullets.length > 0 && (
        <ul className="az-bullets">
          {bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}

      {/* Action plan */}
      {actionPlan && (
        <div className="az-action-plan">
          <div className="az-action-plan__label">Action plan</div>
          <div className="az-action-plan__text">{actionPlan}</div>
        </div>
      )}
    </div>
  );
}
