import React, { useEffect, useState, useCallback, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { API_URL } from "./config";
import { motion, AnimatePresence } from "framer-motion";
import { TrendingUp, TrendingDown, RefreshCw, BarChart2, Activity, X, ExternalLink } from "lucide-react";
import { UserContext } from "./UserContext";
import AnalyzerCard from "./AnalyzerCard";
import "./Markets.css";

/* ─── Tiny inline SVG sparkline ─────────────────────────────────────────── */
function Sparkline({ data, isPositive, width = 120, height = 44 }) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const color = isPositive ? "#22c55e" : "#ef4444";
  const polyline = pts.join(" ");

  // Fill polygon: close down to baseline
  const fill = `${pts.join(" ")} ${width},${height} 0,${height}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      <defs>
        <linearGradient id={`sg-${isPositive ? "g" : "r"}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={fill}
        fill={`url(#sg-${isPositive ? "g" : "r"})`}
      />
      <polyline
        points={polyline}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* ─── Sector badge colours ───────────────────────────────────────────────── */
const SECTOR_COLORS = {
  "Information Technology": "#3b82f6",
  "Financials": "#8b5cf6",
  "Energy": "#f59e0b",
  "Healthcare": "#10b981",
  "Consumer Discretionary": "#f97316",
  "default": "#64748b",
};

function sectorColor(sector) {
  return SECTOR_COLORS[sector] || SECTOR_COLORS["default"];
}

/* ─── Stock Card ─────────────────────────────────────────────────────────── */
function StockCard({ stock, index, onClick, isSelected }) {
  const pos = stock.is_positive;
  const color = pos ? "#22c55e" : "#ef4444";
  const bgGlow = pos ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.06)";

  return (
    <motion.div
      className={`mkt-card${isSelected ? " mkt-card--selected" : ""}`}
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.4 }}
      onClick={onClick}
      whileHover={{ scale: 1.015, transition: { duration: 0.15 } }}
      style={{ "--card-glow": bgGlow, "--card-accent": color, cursor: "pointer" }}
    >
      {/* Header row */}
      <div className="mkt-card__head">
        <div>
          <div className="mkt-card__symbol">{stock.symbol}</div>
          <div className="mkt-card__name">{stock.name}</div>
        </div>
        <span
          className="mkt-card__sector"
          style={{ background: `${sectorColor(stock.sector)}22`, color: sectorColor(stock.sector) }}
        >
          {stock.sector || "—"}
        </span>
      </div>

      {/* Sparkline */}
      <div className="mkt-card__spark">
        <Sparkline data={stock.sparkline} isPositive={pos} width={220} height={52} />
      </div>

      {/* Footer */}
      <div className="mkt-card__foot">
        <div>
          <div className="mkt-card__price">
            ₹{Number(stock.price).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="mkt-card__cap">{stock.market_cap}</div>
        </div>
        <div className={`mkt-card__change ${pos ? "pos" : "neg"}`}>
          {pos ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          <span>{pos ? "+" : ""}{stock.change_pct?.toFixed(2)}%</span>
        </div>
      </div>
    </motion.div>
  );
}

/* ─── Module-level cache: persists across navigation, survives re-mounts ── */
const _cache = {
  data:        null,   // array of stocks
  fetchedAt:   null,   // Date
  TTL_MS:      5 * 60 * 1000,  // 5 minutes
  isFresh()  { return this.data && this.fetchedAt && (Date.now() - this.fetchedAt < this.TTL_MS); },
};

/* ─── Markets Page ───────────────────────────────────────────────────────── */
export default function Markets() {
  const { user } = useContext(UserContext) || {};
  const uid = user?.userid || null;

  const [stocks, setStocks]           = useState(_cache.data || []);
  const [loading, setLoading]         = useState(!_cache.data);
  const [silentRefresh, setSilent]    = useState(false);
  const [error, setError]             = useState(null);
  const [lastUpdated, setLastUpdated] = useState(_cache.fetchedAt ? new Date(_cache.fetchedAt) : null);
  const [filter, setFilter]           = useState("All");
  const [selectedSymbol, setSelected] = useState(null);   // § 5 — side panel state
  const navigate = useNavigate();

  const load = useCallback(async ({ silent = false } = {}) => {
    try {
      if (silent) setSilent(true);
      else        setLoading(true);
      setError(null);

      const res = await fetch(`${API_URL}/markets`);
      if (!res.ok) throw new Error("Failed to fetch market data");
      const data = await res.json();

      _cache.data      = data;
      _cache.fetchedAt = Date.now();

      setStocks(data);
      setLastUpdated(new Date());
    } catch (err) {
      if (!_cache.data) setError(err.message);
    } finally {
      setLoading(false);
      setSilent(false);
    }
  }, []);

  useEffect(() => {
    if (_cache.isFresh()) return;
    load({ silent: !!_cache.data });
  }, [load]);

  /* Sector filter options */
  const sectors = ["All", ...Array.from(new Set(stocks.map(s => s.sector).filter(Boolean)))];

  const filtered = filter === "All"
    ? stocks
    : stocks.filter(s => s.sector === filter);

  const gainers = stocks.filter(s => s.is_positive).length;
  const losers  = stocks.filter(s => !s.is_positive).length;

  const selectedStock = selectedSymbol
    ? stocks.find(s => s.symbol === selectedSymbol)
    : null;

  return (
    <div className="mkt-page">
      {/* ── Header ── */}
      <div className="mkt-header">
        <div>
          <h1 className="mkt-title">
            <Activity size={28} className="mkt-title-icon" />
            Market Overview
          </h1>
          <p className="mkt-subtitle">
            Live prices &amp; performance — click any stock for an AI read
          </p>
        </div>

        <div className="mkt-header-right">
          {!loading && (
            <div className="mkt-summary">
              <span className="mkt-sum-gain">▲ {gainers} Gainers</span>
              <span className="mkt-sum-loss">▼ {losers} Losers</span>
            </div>
          )}
          <button className="mkt-refresh" onClick={() => load({ silent: false })} disabled={loading || silentRefresh}>
            <RefreshCw size={16} className={(loading || silentRefresh) ? "spin" : ""} />
            {silentRefresh ? "Updating…" : loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </div>

      {/* ── Last updated ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        {lastUpdated && (
          <p className="mkt-updated" style={{ margin: 0 }}>
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
        )}
        {silentRefresh && (
          <span style={{ fontSize: 11, color: "#38bdf8", display: "flex", alignItems: "center", gap: 4 }}>
            <RefreshCw size={11} className="spin" /> Refreshing in background…
          </span>
        )}
      </div>

      {/* ── Sector filter pills ── */}
      {!loading && stocks.length > 0 && (
        <div className="mkt-filters">
          {sectors.map(s => (
            <button
              key={s}
              className={`mkt-pill ${filter === s ? "active" : ""}`}
              onClick={() => setFilter(s)}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* ── Loading / Error states ── */}
      {loading && (
        <div className="mkt-loading">
          <div className="mkt-skeleton-grid">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="mkt-skeleton" />
            ))}
          </div>
          <p className="mkt-loading-text">
            <BarChart2 size={16} /> Fetching live market data…
          </p>
        </div>
      )}

      {error && !loading && (
        <div className="mkt-error">
          <p>⚠️ {error}</p>
          <button onClick={load}>Retry</button>
        </div>
      )}

      {/* ── Main layout: grid + optional side panel ── */}
      {!loading && !error && (
        <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>

          {/* Stock grid — narrows when panel is open */}
          <AnimatePresence>
            <div
              className="mkt-grid"
              style={{
                flex: selectedSymbol ? "1 1 0%" : "1 1 100%",
                minWidth: 0,
                transition: "flex 0.3s ease",
              }}
            >
              {filtered.map((stock, i) => (
                <StockCard
                  key={stock.symbol}
                  stock={stock}
                  index={i}
                  isSelected={stock.symbol === selectedSymbol}
                  onClick={() => setSelected(prev =>
                    prev === stock.symbol ? null : stock.symbol
                  )}
                />
              ))}
            </div>
          </AnimatePresence>

          {/* ── Analyzer side panel ── */}
          <AnimatePresence>
            {selectedSymbol && (
              <motion.div
                key="mkt-panel"
                initial={{ opacity: 0, x: 30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 30 }}
                transition={{ duration: 0.25 }}
                style={{
                  width: 340,
                  flexShrink: 0,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  position: "sticky",
                  top: 20,
                }}
              >
                {/* Panel header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: "#e2e8f0" }}>
                      {selectedSymbol}
                    </div>
                    {selectedStock && (
                      <div style={{ fontSize: 12, color: "#64748b" }}>{selectedStock.name}</div>
                    )}
                  </div>
                  <button
                    onClick={() => setSelected(null)}
                    style={{
                      background: "rgba(148,163,184,0.08)",
                      border: "1px solid rgba(148,163,184,0.15)",
                      borderRadius: 7,
                      padding: "4px 8px",
                      cursor: "pointer",
                      color: "#94a3b8",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <X size={13} /> Close
                  </button>
                </div>

                {/* AnalyzerCard — independent fetch, never blocks the grid */}
                <AnalyzerCard
                  context="market"
                  symbol={selectedSymbol}
                  userId={uid}
                />

                {/* Buy + full details actions */}
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    style={{
                      flex: 1,
                      background: "linear-gradient(135deg,#26e07f,#16a34a)",
                      border: "none",
                      borderRadius: 10,
                      padding: "10px 0",
                      color: "#0a1a0a",
                      fontWeight: 700,
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                    onClick={() => navigate(`/stock-page/${selectedSymbol}`)}
                  >
                    Buy / Trade
                  </button>
                  <button
                    onClick={() => navigate(`/stock-page/${selectedSymbol}`)}
                    style={{
                      background: "rgba(84,197,255,0.08)",
                      border: "1px solid rgba(84,197,255,0.2)",
                      borderRadius: 10,
                      padding: "10px 12px",
                      color: "#54c5ff",
                      fontSize: 12,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 5,
                      fontWeight: 600,
                    }}
                  >
                    <ExternalLink size={13} /> Details
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
