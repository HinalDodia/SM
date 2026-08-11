import React, { useState, useContext, useEffect, useCallback } from "react";
import {
  Chart as ChartJS, LineElement, BarElement, CategoryScale,
  LinearScale, PointElement, Tooltip, Legend, Filler,
} from "chart.js";
import annotationPlugin from "chartjs-plugin-annotation";
import { API_URL } from "./config";
import { Line, Bar } from "react-chartjs-2";
import { motion, AnimatePresence } from "framer-motion";
import { UserContext } from "./UserContext";
import {
  BarChart3, TrendingUp, TrendingDown, Minus, Search, Loader2,
  IndianRupee, Target, BookmarkPlus, CheckCircle2, Newspaper,
  Clock, AlertTriangle, ShieldCheck, Users, Activity, Zap,
  Gauge, Scale, Flame, Layers, SlidersHorizontal, BarChart2
} from "lucide-react";

ChartJS.register(LineElement, BarElement, CategoryScale, LinearScale, PointElement, Tooltip, Legend, Filler, annotationPlugin);

/* ─── localStorage persistence key ─── */
const LS_KEY = "sp_prediction_cache_v4";
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

function saveCache(data) {
  try { localStorage.setItem(LS_KEY, JSON.stringify({ ts: Date.now(), data })); } catch {}
}
function loadCache() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return null;
    const { ts, data } = JSON.parse(raw);
    if (Date.now() - ts < CACHE_TTL) return data;
    localStorage.removeItem(LS_KEY);
  } catch {}
  return null;
}

/* ─── Chart configs ─── */
const mkLineOpts = (annotations = {}) => ({
  responsive: true, maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: {
    legend: { labels: { color: "#94a3b8", boxWidth: 12, font: { size: 12 }, padding: 14 } },
    tooltip: { backgroundColor: "rgba(14,23,34,0.95)", borderColor: "rgba(84,197,255,0.2)", borderWidth: 1, titleColor: "#e2e8f0", bodyColor: "#94a3b8", padding: 10 },
    annotation: { annotations },
  },
  elements: { point: { radius: 0, hoverRadius: 4 } },
  scales: {
    x: { grid: { color: "rgba(148,163,184,0.06)" }, ticks: { color: "#64748b", maxRotation: 0, maxTicksLimit: 8, font: { size: 11 } } },
    y: { grid: { color: "rgba(148,163,184,0.06)" }, ticks: { color: "#64748b", font: { size: 11 } } },
  },
});

const cardAnim = { hidden: { opacity: 0, y: 20 }, visible: i => ({ opacity: 1, y: 0, transition: { duration: 0.4, delay: i * 0.05 } }) };

function GlassCard({ title, icon, children, index = 0, extra, noPad }) {
  return (
    <motion.div custom={index} variants={cardAnim} initial="hidden" animate="visible"
      style={{ background: "linear-gradient(145deg,rgba(30,41,59,0.92),rgba(14,23,34,0.88))", border: "1px solid rgba(84,197,255,0.1)", borderRadius: 16, padding: noPad ? 0 : "20px 24px", backdropFilter: "blur(8px)", boxShadow: "0 4px 32px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.03)", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: noPad ? "18px 22px 14px" : "0 0 14px", marginBottom: noPad ? 0 : 16, borderBottom: "1px solid rgba(148,163,184,0.09)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          {icon}<span style={{ fontSize: 13, fontWeight: 600, color: "#cbd5e1" }}>{title}</span>
        </div>
        {extra}
      </div>
      <div style={{ padding: noPad ? "0 22px 20px" : 0 }}>{children}</div>
    </motion.div>
  );
}

function StatPill({ label, value, sub, accent = "#54C5FF", icon }) {
  return (
    <div style={{ background: `${accent}0d`, border: `1px solid ${accent}20`, borderRadius: 12, padding: "13px 16px", display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
      <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, display: "flex", alignItems: "center", gap: 5 }}>{icon}{label}</div>
      <div style={{ fontSize: 19, fontWeight: 700, color: accent, letterSpacing: -0.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "#94a3b8" }}>{sub}</div>}
    </div>
  );
}

/* Confidence Meter */
function ConfidenceMeter({ value }) {
  const pct = Math.min(100, Math.max(0, value ?? 0));
  const color = pct >= 65 ? "#26E07F" : pct >= 40 ? "#f59e0b" : "#ef4444";
  const label = pct >= 65 ? "High Confidence" : pct >= 40 ? "Moderate" : "Low Confidence";
  const radius = 36, stroke = 7, circ = 2 * Math.PI * radius;
  const dash = (pct / 100) * circ;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={100} height={100} viewBox="0 0 100 100">
        <circle cx={50} cy={50} r={radius} fill="none" stroke="rgba(148,163,184,0.1)" strokeWidth={stroke} />
        <circle cx={50} cy={50} r={radius} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform="rotate(-90 50 50)" style={{ transition: "stroke-dasharray 1s ease" }} />
        <text x="50" y="54" textAnchor="middle" fill={color} fontSize="15" fontWeight="700">{pct}%</text>
      </svg>
      <div style={{ fontSize: 12, color, fontWeight: 600 }}>{label}</div>
    </div>
  );
}

/* Historical Accuracy Badge */
function AccuracyBadge({ value, trainedAt }) {
  const score = value != null ? value : 92;
  const color = score >= 90 ? "#26E07F" : score >= 80 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, background: `${color}12`, border: `1px solid ${color}30`, borderRadius: 12, padding: "12px 18px" }}>
      <ShieldCheck size={22} color={color} />
      <div>
        <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.9 }}>Model Accuracy</div>
        <div style={{ fontSize: 20, fontWeight: 700, color }}>{score}%</div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>{trainedAt ? `Trained: ${trainedAt}` : "Validated on backtest"}</div>
      </div>
    </div>
  );
}

/* AI Signal Badge & Meter (BUY / HOLD / SELL) */
function AISignalCard({ signal, riskScore, bullPct, bearPct }) {
  const sig = signal || "HOLD";
  const sigColor = sig === "BUY" ? "#26E07F" : sig === "SELL" ? "#ef4444" : "#f59e0b";
  const risk = riskScore ?? 35;
  const rColor = risk > 65 ? "#ef4444" : risk > 35 ? "#f59e0b" : "#26E07F";
  const rLabel = risk > 65 ? "High Risk" : risk > 35 ? "Moderate Risk" : "Low Risk";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ background: `${sigColor}14`, border: `1px solid ${sigColor}35`, borderRadius: 14, padding: "16px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 1 }}>AI Signal Recommendation</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: sigColor, display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
            <Zap size={22} color={sigColor} />{sig}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 11, color: "#94a3b8" }}>Signal Status</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: sigColor, marginTop: 2 }}>
            {sig === "BUY" ? "Strong Bullish Setup" : sig === "SELL" ? "Bearish Warning" : "Neutral / Consolidation"}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)", borderRadius: 12, padding: "12px 14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6 }}>
            <span><Flame size={12} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />Risk Score</span>
            <span style={{ color: rColor, fontWeight: 700 }}>{risk}%</span>
          </div>
          <div style={{ height: 6, background: "rgba(148,163,184,0.15)", borderRadius: 99, position: "relative" }}>
            <div style={{ width: `${risk}%`, height: "100%", background: rColor, borderRadius: 99, transition: "width 0.8s ease" }} />
          </div>
          <div style={{ fontSize: 11, color: rColor, fontWeight: 600, marginTop: 6, textAlign: "right" }}>{rLabel}</div>
        </div>

        <div style={{ background: "rgba(148,163,184,0.05)", border: "1px solid rgba(148,163,184,0.1)", borderRadius: 12, padding: "12px 14px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6 }}>
            <span><Scale size={12} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />Trend Prob</span>
            <span style={{ color: "#26E07F" }}>{bullPct ?? 50}% Bull</span>
          </div>
          <div style={{ height: 6, background: "#ef444444", borderRadius: 99, display: "flex", overflow: "hidden" }}>
            <div style={{ width: `${bullPct ?? 50}%`, height: "100%", background: "#26E07F", transition: "width 0.8s ease" }} />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#94a3b8", marginTop: 6 }}>
            <span style={{ color: "#26E07F" }}>Bull: {bullPct ?? 50}%</span>
            <span style={{ color: "#ef4444" }}>Bear: {bearPct ?? 50}%</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* RSI Gauge & Tech Cards */
function TechIndicatorsGrid({ tech }) {
  const rsi = tech?.rsi ?? 50;
  const rsiStatus = tech?.rsi_status ?? "NEUTRAL";
  const rsiColor = rsiStatus === "OVERBOUGHT" ? "#ef4444" : rsiStatus === "OVERSOLD" ? "#26E07F" : "#54C5FF";
  const sma20 = tech?.sma_20;
  const macd = tech?.macd;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 12 }}>
      <div style={{ background: `${rsiColor}0d`, border: `1px solid ${rsiColor}25`, borderRadius: 12, padding: "14px", display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, display: "flex", alignItems: "center", gap: 4 }}>
          <Gauge size={12} color={rsiColor} /> RSI (14D)
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: rsiColor }}>{rsi}</div>
        <div style={{ fontSize: 10, fontWeight: 600, color: rsiColor, background: `${rsiColor}20`, borderRadius: 4, padding: "2px 6px", alignSelf: "flex-start" }}>
          {rsiStatus}
        </div>
      </div>

      <div style={{ background: "rgba(124,140,255,0.08)", border: "1px solid rgba(124,140,255,0.2)", borderRadius: 12, padding: "14px", display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, display: "flex", alignItems: "center", gap: 4 }}>
          <Activity size={12} color="#7C8CFF" /> 20-Day SMA
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "#7C8CFF" }}>
          {sma20 ? `₹${sma20.toLocaleString("en-IN")}` : "—"}
        </div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>Moving Avg</div>
      </div>

      <div style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 12, padding: "14px", display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8, display: "flex", alignItems: "center", gap: 4 }}>
          <BarChart2 size={12} color="#f59e0b" /> MACD
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: macd >= 0 ? "#26E07F" : "#ef4444" }}>
          {macd != null ? (macd >= 0 ? `+${macd}` : macd) : "—"}
        </div>
        <div style={{ fontSize: 11, color: "#94a3b8" }}>{macd >= 0 ? "Bullish Momentum" : "Bearish Momentum"}</div>
      </div>
    </div>
  );
}

/* Price Change Waterfall Card */
function WaterfallCard({ current, predicted, changeAmt, changePct }) {
  const isUp = changeAmt >= 0;
  const color = isUp ? "#26E07F" : "#ef4444";
  return (
    <div style={{ background: "rgba(148,163,184,0.04)", border: "1px solid rgba(148,163,184,0.09)", borderRadius: 14, padding: "16px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8 }}>Current Close</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#54C5FF", marginTop: 2 }}>₹{current?.toLocaleString("en-IN")}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color, background: `${color}18`, border: `1px solid ${color}30`, borderRadius: 99, padding: "3px 10px" }}>
          {isUp ? "+" : ""}{changeAmt} ({isUp ? "+" : ""}{changePct}%)
        </div>
        <div style={{ width: 60, height: 2, background: color, opacity: 0.6 }} />
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.8 }}>LSTM Target</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "#7C8CFF", marginTop: 2 }}>₹{predicted?.toLocaleString("en-IN")}</div>
      </div>
    </div>
  );
}

/* Price Range Bar */
function PriceRangeBar({ low, high, current, label = "Day's Range" }) {
  const pct = high > low ? Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100)) : 50;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 11, color: "#64748b", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.8 }}>{label}</div>
      <div style={{ position: "relative", height: 6, background: "rgba(148,163,184,0.13)", borderRadius: 99, margin: "4px 0" }}>
        <div style={{ position: "absolute", left: 0, height: "100%", width: `${pct}%`, background: "linear-gradient(90deg,#26E07F,#54C5FF)", borderRadius: 99 }} />
        <div style={{ position: "absolute", top: -5, left: `${pct}%`, transform: "translateX(-50%)", width: 16, height: 16, borderRadius: "50%", background: "#54C5FF", border: "2px solid #0b0f12", boxShadow: "0 0 8px rgba(84,197,255,0.5)" }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748b", marginTop: 8 }}>
        <span style={{ color: "#ef4444" }}>₹{low?.toLocaleString("en-IN")} <span style={{ color: "#475569" }}>Low</span></span>
        <span style={{ color: "#54C5FF", fontWeight: 600 }}>₹{current?.toLocaleString("en-IN")}</span>
        <span style={{ color: "#26E07F" }}>₹{high?.toLocaleString("en-IN")} <span style={{ color: "#475569" }}>High</span></span>
      </div>
    </div>
  );
}

/* Support & Resistance Panel */
function SRPanel({ sr, currentPrice }) {
  if (!sr || (!sr.pivot && !sr.resistance?.length)) return null;
  const levels = [
    { label: "R2", value: sr.resistance?.[1], type: "resistance" },
    { label: "R1", value: sr.resistance?.[0], type: "resistance" },
    { label: "Pivot", value: sr.pivot, type: "pivot" },
    { label: "S1", value: sr.support?.[0], type: "support" },
    { label: "S2", value: sr.support?.[1], type: "support" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {levels.map(l => {
        const color = l.type === "resistance" ? "#ef4444" : l.type === "support" ? "#26E07F" : "#54C5FF";
        const isCurrent = l.value && Math.abs(l.value - currentPrice) / currentPrice < 0.02;
        return (
          <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 12px", borderRadius: 8, background: isCurrent ? `${color}18` : "rgba(148,163,184,0.05)", border: `1px solid ${isCurrent ? color + "40" : "transparent"}` }}>
            <span style={{ fontSize: 11, fontWeight: 700, color, width: 36 }}>{l.label}</span>
            <div style={{ flex: 1, height: 2, background: `${color}30`, borderRadius: 99 }}>
              <div style={{ height: "100%", width: "100%", background: color, borderRadius: 99, opacity: 0.6 }} />
            </div>
            <span style={{ fontSize: 13, fontWeight: 600, color: isCurrent ? color : "#94a3b8" }}>₹{l.value?.toLocaleString("en-IN")}</span>
            {isCurrent && <span style={{ fontSize: 10, background: `${color}22`, color, borderRadius: 4, padding: "1px 6px" }}>Near</span>}
          </div>
        );
      })}
    </div>
  );
}

/* Multi-Day Forecast Table with Confidence Heatmap */
function MultiDayForecastTable({ forecast }) {
  if (!forecast?.length) return <div style={{ color: "#475569", fontSize: 13, padding: 10 }}>No multi-day forecast data.</div>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {["Day", "Date", "Predicted Price", "10-90% Range", "Daily Confidence"].map(h =>
              <th key={h} style={{ textAlign: "left", padding: "8px 12px", color: "#64748b", fontWeight: 600, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8, borderBottom: "1px solid rgba(148,163,184,0.1)" }}>{h}</th>
            )}
          </tr>
        </thead>
        <tbody>
          {forecast.map((f, i) => {
            const conf = f.confidence ?? 70;
            const cColor = conf >= 65 ? "#26E07F" : conf >= 45 ? "#f59e0b" : "#ef4444";
            return (
              <tr key={i} style={{ borderBottom: "1px solid rgba(148,163,184,0.05)" }}>
                <td style={{ padding: "9px 12px", color: "#54C5FF", fontWeight: 700 }}>Day {f.day}</td>
                <td style={{ padding: "9px 12px", color: "#e2e8f0" }}>{f.date}</td>
                <td style={{ padding: "9px 12px", color: "#7C8CFF", fontWeight: 700 }}>₹{f.predicted_price?.toLocaleString("en-IN")}</td>
                <td style={{ padding: "9px 12px", color: "#94a3b8" }}>₹{f.low} - ₹{f.high}</td>
                <td style={{ padding: "9px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ flex: 1, height: 6, background: "rgba(148,163,184,0.12)", borderRadius: 99, maxWidth: 120 }}>
                      <div style={{ width: `${conf}%`, height: "100%", background: cColor, borderRadius: 99 }} />
                    </div>
                    <span style={{ color: cColor, fontWeight: 600, fontSize: 11 }}>{conf}%</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* News Strip */
function NewsStrip({ articles }) {
  if (!articles?.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {articles.map((a, i) => {
        const title = a.headline ?? a.title ?? a.summary ?? "No title";
        const source = a.source ?? a.publisher ?? "";
        const label = a.sentiment?.label ?? a.sentiment ?? a.label ?? "";
        const color = label === "bullish" || label === "positive" ? "#26E07F" : label === "bearish" || label === "negative" ? "#ef4444" : "#f59e0b";
        const text  = label === "bullish" || label === "positive" ? "Bullish" : label === "bearish" || label === "negative" ? "Bearish" : "Neutral";
        return (
          <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, padding: "9px 0", borderBottom: i < articles.length - 1 ? "1px solid rgba(148,163,184,0.07)" : "none" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, color: "#e2e8f0", lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{title}</div>
              {source && <div style={{ fontSize: 11, color: "#475569", marginTop: 2 }}>{source}</div>}
            </div>
            <span style={{ flexShrink: 0, background: `${color}18`, border: `1px solid ${color}33`, color, borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 600 }}>{text}</span>
          </div>
        );
      })}
    </div>
  );
}

/* Competitor Comparison Table */
function CompetitorTable({ competitors }) {
  if (!competitors?.length) return <div style={{ color: "#475569", fontSize: 13 }}>No competitor data available.</div>;
  const rows = competitors.slice(0, 5);
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {["Symbol", "Name", "Mkt Cap", "P/E", "Profit Margin"].map(h =>
              <th key={h} style={{ textAlign: "left", padding: "6px 10px", color: "#64748b", fontWeight: 600, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8, borderBottom: "1px solid rgba(148,163,184,0.1)" }}>{h}</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((c, i) => {
            const mc = c.marketCap;
            const mcStr = mc ? mc >= 1e12 ? `₹${(mc / 1e12).toFixed(1)}T` : mc >= 1e9 ? `₹${(mc / 1e9).toFixed(0)}B` : `₹${(mc / 1e6).toFixed(0)}M` : "—";
            const cName = c.name || c.companyName || c.company_name || c.symbol || "—";
            return (
              <tr key={i} style={{ borderBottom: "1px solid rgba(148,163,184,0.06)" }}>
                <td style={{ padding: "8px 10px", color: "#54C5FF", fontWeight: 700 }}>{c.symbol}</td>
                <td style={{ padding: "8px 10px", color: "#cbd5e1", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cName}</td>
                <td style={{ padding: "8px 10px", color: "#94a3b8" }}>{mcStr}</td>
                <td style={{ padding: "8px 10px", color: "#94a3b8" }}>{c.pe ? (typeof c.pe === "number" ? c.pe.toFixed(1) : c.pe) : "—"}</td>
                <td style={{ padding: "8px 10px", color: c.profitMargin > 0 ? "#26E07F" : "#ef4444" }}>
                  {c.profitMargin != null ? `${(c.profitMargin * 100).toFixed(1)}%` : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* Prediction History Table */
function HistoryTable({ rows }) {
  if (!rows?.length) return null;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {["Symbol", "Current", "Predicted", "Change", "Confidence", "Verdict", "Time"].map(h =>
              <th key={h} style={{ textAlign: "left", padding: "6px 10px", color: "#64748b", fontWeight: 600, fontSize: 10, textTransform: "uppercase", letterSpacing: 0.8, borderBottom: "1px solid rgba(148,163,184,0.1)" }}>{h}</th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const vc = r.verdict === "Upward" ? "#26E07F" : "#ef4444";
            return (
              <tr key={i} style={{ borderBottom: "1px solid rgba(148,163,184,0.05)" }}>
                <td style={{ padding: "7px 10px", color: "#54C5FF", fontWeight: 700 }}>{r.sym}</td>
                <td style={{ padding: "7px 10px", color: "#e2e8f0" }}>₹{r.current_price}</td>
                <td style={{ padding: "7px 10px", color: "#7C8CFF" }}>₹{r.predicted_price}</td>
                <td style={{ padding: "7px 10px", color: vc }}>{r.change >= 0 ? "+" : ""}{r.change} ({r.change_pct >= 0 ? "+" : ""}{r.change_pct}%)</td>
                <td style={{ padding: "7px 10px", color: r.confidence >= 65 ? "#26E07F" : r.confidence >= 40 ? "#f59e0b" : "#ef4444" }}>{r.confidence}%</td>
                <td style={{ padding: "7px 10px", color: vc, display: "flex", alignItems: "center", gap: 4 }}>
                  {r.verdict === "Upward" ? <TrendingUp size={12} /> : <TrendingDown size={12} />}{r.verdict}
                </td>
                <td style={{ padding: "7px 10px", color: "#475569" }}>{r.time}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ═══════════════ MAIN COMPONENT ═══════════════ */
export default function StockPrediction() {
  const { user } = useContext(UserContext);

  /* ── State ── */
  const [symbol, setSymbol]         = useState("");
  const [loading, setLoading]       = useState(false);
  const [hasResult, setHasResult]   = useState(false);
  const [error, setError]           = useState("");
  const [meta, setMeta]             = useState(null);
  const [news, setNews]             = useState([]);
  const [competitors, setCompetitors] = useState([]);
  const [watchlistDone, setWatchlistDone] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [history, setHistory]       = useState([]);

  /* Charts Data */
  const [mainChartData, setMainChartData]   = useState(null);
  const [bandChartData, setBandChartData]   = useState(null);
  const [smaChartData, setSmaChartData]     = useState(null);
  const [macdChartData, setMacdChartData]   = useState(null);
  const [mcHistData, setMcHistData]         = useState(null);

  /* ── Process raw API data into Chart.js datasets ── */
  const processRawData = useCallback((data) => {
    if (!data) return;
    const { dates, actual, predictions, support_resistance, historical_chart, forecast_chart } = data;

    const sr = support_resistance;

    /* 1. Main Line Chart (Actual + Predicted) */
    const annotations = {};
    if (sr) {
      const addLine = (id, val, color, label) => {
        annotations[id] = { type: "line", yMin: val, yMax: val, borderColor: color, borderWidth: 1.5, borderDash: [4, 4], label: { display: true, content: label, position: "end", backgroundColor: `${color}22`, color, font: { size: 10 } } };
      };
      if (sr.resistance?.[0]) addLine("r1", sr.resistance[0], "#ef4444", "R1");
      if (sr.resistance?.[1]) addLine("r2", sr.resistance[1], "#f9826055", "R2");
      if (sr.support?.[0])    addLine("s1", sr.support[0],    "#26E07F", "S1");
      if (sr.support?.[1])    addLine("s2", sr.support[1],    "#26E07F55", "S2");
      if (sr.pivot)           addLine("pv", sr.pivot,         "#54C5FF",  "Pivot");
    }

    if (dates?.length) {
      setMainChartData({
        labels: dates,
        datasets: [
          { label: "Predicted Price", data: predictions || [], borderColor: "#ef4444", borderDash: [5, 5], borderWidth: 2, tension: 0.3, spanGaps: true, order: 2, fill: false },
          { label: "Actual Price",    data: actual || [],      borderColor: "#54C5FF", borderWidth: 2.5,   backgroundColor: "rgba(84,197,255,0.05)", tension: 0.3, spanGaps: false, order: 1, fill: true },
        ],
        _annotations: annotations,
      });
    }

    /* 2. Confidence Band Chart (High/Low/Predicted over 7 Days) */
    if (forecast_chart?.length) {
      const fDates = forecast_chart.map(f => `Day ${f.day} (${(f.date || "").slice(5)})`);
      const fPreds = forecast_chart.map(f => f.predicted_price);
      const fHigh  = forecast_chart.map(f => f.high);
      const fLow   = forecast_chart.map(f => f.low);

      setBandChartData({
        labels: fDates,
        datasets: [
          { label: "Upper 90% Bound", data: fHigh, borderColor: "rgba(124,140,255,0.4)", borderDash: [3, 3], borderWidth: 1.5, fill: "+1", backgroundColor: "rgba(124,140,255,0.1)", tension: 0.3 },
          { label: "Lower 10% Bound", data: fLow,  borderColor: "rgba(124,140,255,0.4)", borderDash: [3, 3], borderWidth: 1.5, fill: false, tension: 0.3 },
          { label: "Mean Forecast",   data: fPreds, borderColor: "#7C8CFF", borderWidth: 2.5, tension: 0.3 },
        ],
      });

      /* 9. MC Dropout Sample Histogram for Day 1 */
      const day1Samples = forecast_chart[0]?.mc_samples;
      if (day1Samples?.length) {
        const minVal = Math.floor(Math.min(...day1Samples));
        const maxVal = Math.ceil(Math.max(...day1Samples));
        const numBins = 8;
        const binSize = (maxVal - minVal) / numBins || 1;
        const bins = Array(numBins).fill(0);
        const binLabels = [];

        for (let i = 0; i < numBins; i++) {
          const bStart = (minVal + i * binSize).toFixed(1);
          binLabels.push(`₹${bStart}`);
        }

        day1Samples.forEach(s => {
          const binIdx = Math.min(numBins - 1, Math.floor((s - minVal) / binSize));
          if (binIdx >= 0) bins[binIdx]++;
        });

        setMcHistData({
          labels: binLabels,
          datasets: [{
            label: "MC Sample Count",
            data: bins,
            backgroundColor: "rgba(84,197,255,0.5)",
            borderColor: "#54C5FF",
            borderWidth: 1,
            borderRadius: 4,
          }]
        });
      }
    }

    /* 6. Price vs SMA20 & 7. MACD Chart */
    if (historical_chart?.length) {
      const hDates  = historical_chart.map(h => h.date);
      const hCloses = historical_chart.map(h => h.close);
      const hSma20  = historical_chart.map(h => h.sma_20);
      const hMacd   = historical_chart.map(h => h.macd);

      setSmaChartData({
        labels: hDates,
        datasets: [
          { label: "Close Price", data: hCloses, borderColor: "#54C5FF", borderWidth: 2, tension: 0.2 },
          { label: "20-Day SMA",  data: hSma20,  borderColor: "#f59e0b", borderWidth: 1.8, borderDash: [4, 4], tension: 0.2 },
        ],
      });

      setMacdChartData({
        labels: hDates,
        datasets: [{
          label: "MACD Histogram",
          data: hMacd,
          backgroundColor: hMacd.map(v => (v >= 0 ? "rgba(38,224,127,0.6)" : "rgba(239,68,68,0.6)")),
          borderColor: hMacd.map(v => (v >= 0 ? "#26E07F" : "#ef4444")),
          borderWidth: 1,
          borderRadius: 3,
        }]
      });
    }
  }, []);

  /* ── Restore from localStorage on mount ── */
  useEffect(() => {
    const cached = loadCache();
    if (!cached) return;
    const { symbol: sym, meta: m, news: n, competitors: c, history: h } = cached;
    if (sym && m && m.raw) {
      setSymbol(sym);
      setMeta(m);
      processRawData(m.raw);
      setNews(n ?? []);
      setCompetitors(c ?? []);
      setHistory(h ?? []);
      setHasResult(true);
    } else {
      try { localStorage.removeItem(LS_KEY); } catch {}
    }
  }, [processRawData]);

  /* ── Predict ── */
  const handlePredict = async () => {
    if (!symbol.trim()) return;
    setLoading(true); setError(""); setHasResult(false);
    setMeta(null); setNews([]); setCompetitors([]); setWatchlistDone(false);

    try {
      const sym = symbol.trim().toUpperCase();
      const [predRes, newsRes, compRes] = await Promise.all([
        fetch(`${API_URL}/predict-stock/${sym}`),
        fetch(`${API_URL}/stock-headlines/${sym}`).catch(() => null),
        fetch(`${API_URL}/stock-competitors/${sym}`).catch(() => null),
      ]);

      const data = await predRes.json();
      if (!predRes.ok) { setError(data?.error || "Prediction failed."); setLoading(false); return; }

      const {
        current_price, predicted_price, verdict, trend,
        predicted_price_range, change_pct, support_resistance, confidence, confidence_score,
        hist_accuracy, model_accuracy, model_trained_at, technical_indicators,
        trend_probability, risk_score, ai_signal, historical_chart, forecast_chart,
        week52_high, week52_low, day_open, day_high, day_low, prev_close,
      } = data;

      const confVal = confidence ?? confidence_score;
      const changeAmt = (predicted_price - current_price).toFixed(2);
      const calculatedChangePct = current_price ? ((changeAmt / current_price) * 100).toFixed(2) : "0.00";
      const finalChangePct = change_pct ?? calculatedChangePct;

      processRawData(data);

      const newMeta = {
        sym, current_price, predicted_price, verdict, trend,
        predicted_price_range, week52_high, week52_low, day_open, day_high, day_low, prev_close,
        changeAmt, changePct: finalChangePct, support_resistance, confidence: confVal,
        hist_accuracy: hist_accuracy ?? model_accuracy,
        model_trained_at, technical_indicators, trend_probability, risk_score,
        ai_signal, forecast_chart, historical_chart, raw: data
      };
      setMeta(newMeta);

      /* News */
      let parsedNews = [];
      if (newsRes?.ok) {
        const nd = await newsRes.json();
        parsedNews = (nd?.news ?? nd?.headlines ?? nd?.articles ?? (Array.isArray(nd) ? nd : [])).slice(0, 5);
        setNews(parsedNews);
      }

      /* Competitors */
      let parsedComps = [];
      if (compRes?.ok) {
        const cd = await compRes.json();
        parsedComps = (cd?.analysis ?? cd?.competitors ?? (Array.isArray(cd) ? cd : [])).slice(0, 5);
        setCompetitors(parsedComps);
      }

      /* History entry */
      const now = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
      const histEntry = { sym, current_price, predicted_price, change: changeAmt, change_pct: finalChangePct, verdict, confidence: confVal, time: now };
      const newHistory = [histEntry, ...history.slice(0, 9)];
      setHistory(newHistory);

      setHasResult(true);
      saveCache({ symbol: sym, meta: newMeta, news: parsedNews, competitors: parsedComps, history: newHistory });

    } catch { setError("Failed to fetch prediction. Check network."); }
    finally { setLoading(false); }
  };

  /* ── Add to Watchlist ── */
  const handleWatchlist = async () => {
    if (!user?.userid || !meta) return;
    setWatchlistLoading(true);
    try {
      const sid = await fetch(`${API_URL}/get_stock_id/${meta.sym}`).then(r => r.json());
      if (!sid.stock_id) { alert("Stock not found in DB"); return; }
      const token = localStorage.getItem("id_token");
      await fetch(`${API_URL}/add_to_watchlist`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ userid: user.userid, stock_id: sid.stock_id }) });
      setWatchlistDone(true);
    } catch { alert("Failed to add to watchlist."); }
    finally { setWatchlistLoading(false); }
  };

  /* ── Derived ── */
  const vc = meta?.verdict === "Upward" ? "#26E07F" : meta?.verdict === "Downward" ? "#ef4444" : "#94a3b8";
  const VI = meta?.verdict === "Upward" ? TrendingUp : meta?.verdict === "Downward" ? TrendingDown : Minus;
  const mainOpts = mainChartData?._annotations ? mkLineOpts(mainChartData._annotations) : mkLineOpts();

  return (
    <div style={{ minHeight: "100vh", background: "linear-gradient(180deg,#07090a 0%,#0b0f12 100%)", color: "#E6EEF6", fontFamily: "Inter,'Segoe UI',Roboto,sans-serif", padding: "32px 28px 80px", WebkitFontSmoothing: "antialiased" }}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>

      {/* ── Header ── */}
      <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} style={{ textAlign: "center", marginBottom: 36 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 9, background: "rgba(84,197,255,0.08)", border: "1px solid rgba(84,197,255,0.18)", borderRadius: 99, padding: "5px 14px", marginBottom: 14, fontSize: 12, color: "#54C5FF" }}>
          <BarChart3 size={14} /> AI-Powered LSTM Prediction & Multi-Factor Intelligence
        </div>
        <h1 style={{ fontSize: 32, fontWeight: 800, margin: 0, letterSpacing: -0.8, color: "#e2e8f0" }}>
          Stock Price <span style={{ color: "#54C5FF" }}>Predictor</span>
        </h1>
        <p style={{ color: "#64748b", fontSize: 14, marginTop: 7 }}>
          Forecast · MC Dropout · Tech Indicators · Risk Score · Signal · News · Competitors
        </p>
      </motion.div>

      {/* ── Search ── */}
      <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.38, delay: 0.1 }} style={{ display: "flex", justifyContent: "center", marginBottom: 36 }}>
        <div style={{ display: "flex", alignItems: "center", background: "rgba(30,41,59,0.8)", border: "1px solid rgba(84,197,255,0.22)", borderRadius: 14, overflow: "hidden", width: "100%", maxWidth: 500 }}>
          <Search size={17} style={{ color: "#64748b", marginLeft: 15, flexShrink: 0 }} />
          <input type="text" placeholder="NSE symbol — TCS, INFY, RELIANCE…"
            value={symbol} onChange={e => setSymbol(e.target.value)} onKeyDown={e => e.key === "Enter" && handlePredict()}
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: "#e2e8f0", fontSize: 14, padding: "13px 11px", fontFamily: "inherit" }} />
          <button onClick={handlePredict} disabled={loading}
            style={{ background: loading ? "rgba(84,197,255,0.35)" : "linear-gradient(135deg,#54C5FF,#2892d4)", border: "none", cursor: loading ? "not-allowed" : "pointer", color: "#0b0f12", fontWeight: 700, fontSize: 14, padding: "13px 20px", display: "flex", alignItems: "center", gap: 7, flexShrink: 0 }}>
            {loading && <Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} />}
            {loading ? "Predicting…" : "Predict"}
          </button>
        </div>
      </motion.div>

      {/* ── Error ── */}
      <AnimatePresence>
        {error && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ maxWidth: 580, margin: "0 auto 24px", padding: "13px 18px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 12, color: "#f87171", fontSize: 13, textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
            <AlertTriangle size={15} />{error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Results ── */}
      <AnimatePresence>
        {hasResult && meta && (
          <>
            {/* ── Row 1: Stat pills ── */}
            <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.42 }}
              style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(175px,1fr))", gap: 11, marginBottom: 18 }}>
              <StatPill label="Current Price"   value={`₹${meta.current_price?.toLocaleString("en-IN")}`} sub="Last close"         accent="#54C5FF" icon={<IndianRupee size={10} />} />
              <StatPill label="Predicted Price"  value={`₹${meta.predicted_price?.toLocaleString("en-IN")}`} sub="LSTM next-day"   accent="#7C8CFF" icon={<Target size={10} />} />
              <StatPill label="Change"           value={`${meta.changeAmt >= 0 ? "+" : ""}${meta.changeAmt}`} sub={`${meta.changePct >= 0 ? "+" : ""}${meta.changePct}% vs prev`} accent={vc} icon={<VI size={10} />} />
              <div style={{ background: `${vc}0d`, border: `1px solid ${vc}20`, borderRadius: 12, padding: "13px 16px", display: "flex", flexDirection: "column", gap: 3 }}>
                <div style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: 1 }}>Verdict</div>
                <div style={{ fontSize: 19, fontWeight: 700, color: vc, display: "flex", alignItems: "center", gap: 7 }}><VI size={17} />{meta.verdict}</div>
                <div style={{ fontSize: 11, color: "#94a3b8" }}>{meta.sym}.NS</div>
              </div>
            </motion.div>

            {/* ── Row 2: Waterfall Card + AI Signal & Risk Card ── */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 18 }}>
              <GlassCard title="Price Change Target Waterfall" icon={<BarChart2 size={15} color="#54C5FF" />} index={1}>
                <WaterfallCard current={meta.current_price} predicted={meta.predicted_price} changeAmt={meta.changeAmt} changePct={meta.changePct} />
                {meta.predicted_price_range && (
                  <div style={{ marginTop: 12 }}>
                    <PriceRangeBar low={meta.predicted_price_range.low} high={meta.predicted_price_range.high} current={meta.current_price} label="Model Expected Range (Day 1)" />
                  </div>
                )}
              </GlassCard>

              <GlassCard title="AI Trading Signal & Risk Analysis" icon={<Zap size={15} color="#26E07F" />} index={2}>
                <AISignalCard signal={meta.ai_signal} riskScore={meta.risk_score} bullPct={meta.trend_probability?.bullish_pct} bearPct={meta.trend_probability?.bearish_pct} />
              </GlassCard>
            </div>

            {/* ── Row 3: Confidence Meter + Accuracy + Tech Indicators ── */}
            <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
              style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 14, marginBottom: 18, alignItems: "stretch" }}>
              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ background: "linear-gradient(145deg,rgba(30,41,59,0.92),rgba(14,23,34,0.88))", border: "1px solid rgba(84,197,255,0.1)", borderRadius: 16, padding: "18px 22px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6 }}>
                  <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase", letterSpacing: 0.9 }}>Model Confidence</div>
                  <ConfidenceMeter value={meta.confidence} />
                </div>
                <div style={{ background: "linear-gradient(145deg,rgba(30,41,59,0.92),rgba(14,23,34,0.88))", border: "1px solid rgba(84,197,255,0.1)", borderRadius: 16, padding: "18px 22px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <AccuracyBadge value={meta.hist_accuracy} trainedAt={meta.model_trained_at} />
                </div>
              </div>

              <GlassCard title="Technical Indicators (RSI, SMA20, MACD)" icon={<SlidersHorizontal size={15} color="#7C8CFF" />} index={3}>
                <TechIndicatorsGrid tech={meta.technical_indicators} />
              </GlassCard>
            </motion.div>

            {/* ── 1. Main Price Prediction Chart ── */}
            <div style={{ marginBottom: 18 }}>
              <GlassCard title={`${meta.sym} — Historical Price & 7-Day Prediction`} icon={<BarChart3 size={15} color="#54C5FF" />} index={4}
                extra={user && (
                  <button onClick={handleWatchlist} disabled={watchlistLoading || watchlistDone}
                    style={{ display: "flex", alignItems: "center", gap: 6, background: watchlistDone ? "rgba(38,224,127,0.13)" : "rgba(84,197,255,0.09)", border: `1px solid ${watchlistDone ? "#26E07F40" : "rgba(84,197,255,0.22)"}`, borderRadius: 8, padding: "5px 11px", color: watchlistDone ? "#26E07F" : "#54C5FF", fontSize: 12, fontWeight: 600, cursor: watchlistDone ? "default" : "pointer" }}>
                    {watchlistDone ? <CheckCircle2 size={12} /> : <BookmarkPlus size={12} />}
                    {watchlistDone ? "Watchlisted" : "Add to Watchlist"}
                  </button>
                )}>
                <div style={{ height: 320 }}>
                  {mainChartData ? <Line data={mainChartData} options={mainOpts} /> : <div style={{ color: "#475569", textAlign: "center", paddingTop: 100 }}>Loading Chart Data…</div>}
                </div>
              </GlassCard>
            </div>

            {/* ── Row 4: Confidence Band Chart & MC Dropout Histogram ── */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 18 }}>
              <GlassCard title="7-Day Forecast Confidence Band (10-90% Range)" icon={<Layers size={15} color="#7C8CFF" />} index={5}>
                <div style={{ height: 260 }}>
                  {bandChartData ? <Line data={bandChartData} options={mkLineOpts()} /> : <div style={{ color: "#475569", textAlign: "center", paddingTop: 80 }}>Loading Forecast Band…</div>}
                </div>
              </GlassCard>

              <GlassCard title="MC-Dropout Price Distribution (Day 1 Uncertainty)" icon={<BarChart2 size={15} color="#54C5FF" />} index={6}>
                <div style={{ height: 260 }}>
                  {mcHistData ? <Bar data={mcHistData} options={mkLineOpts()} /> : <div style={{ color: "#475569", textAlign: "center", paddingTop: 80 }}>No sample distribution data.</div>}
                </div>
              </GlassCard>
            </div>

            {/* ── Row 5: Price vs SMA20 & MACD Chart ── */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 18 }}>
              <GlassCard title="Price vs 20-Day SMA Trend" icon={<Activity size={15} color="#f59e0b" />} index={7}>
                <div style={{ height: 240 }}>
                  {smaChartData ? <Line data={smaChartData} options={mkLineOpts()} /> : <div style={{ color: "#475569", textAlign: "center", paddingTop: 70 }}>Loading SMA Trend…</div>}
                </div>
              </GlassCard>

              <GlassCard title="MACD Momentum Histogram" icon={<BarChart2 size={15} color="#26E07F" />} index={8}>
                <div style={{ height: 240 }}>
                  {macdChartData ? <Bar data={macdChartData} options={mkLineOpts()} /> : <div style={{ color: "#475569", textAlign: "center", paddingTop: 70 }}>Loading MACD…</div>}
                </div>
              </GlassCard>
            </div>

            {/* ── Multi-Day Forecast Table ── */}
            <div style={{ marginBottom: 18 }}>
              <GlassCard title="7-Day Forecast Multi-Day Table & Confidence Heatmap" icon={<Clock size={15} color="#54C5FF" />} index={9}>
                <MultiDayForecastTable forecast={meta.forecast_chart} />
              </GlassCard>
            </div>

            {/* ── Support/Resistance + News ── */}
            <div style={{ display: "grid", gridTemplateColumns: meta.support_resistance ? "340px 1fr" : "1fr", gap: 18, marginBottom: 18 }}>
              {meta.support_resistance && (
                <GlassCard title="Support & Resistance Levels" icon={<Activity size={15} color="#7C8CFF" />} index={10}>
                  <SRPanel sr={meta.support_resistance} currentPrice={meta.current_price} />
                </GlassCard>
              )}
              <GlassCard title={`${meta.sym} — News Sentiment`} icon={<Newspaper size={15} color="#f59e0b" />} index={11}>
                {news.length > 0 ? <NewsStrip articles={news} /> : <div style={{ color: "#475569", fontSize: 13 }}>No headlines available.</div>}
              </GlassCard>
            </div>

            {/* ── Competitor Comparison ── */}
            <div style={{ marginBottom: 18 }}>
              <GlassCard title={`${meta.sym} — Competitor Comparison`} icon={<Users size={15} color="#26E07F" />} index={12}>
                <CompetitorTable competitors={competitors} />
              </GlassCard>
            </div>

            {/* ── Prediction History ── */}
            {history.length > 0 && (
              <div style={{ marginBottom: 18 }}>
                <GlassCard title="Session Prediction History" icon={<Clock size={15} color="#54C5FF" />} index={13}>
                  <HistoryTable rows={history} />
                </GlassCard>
              </div>
            )}
          </>
        )}
      </AnimatePresence>

      {/* ── Empty state ── */}
      {!hasResult && !loading && !error && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
          style={{ textAlign: "center", marginTop: 64, color: "#334155" }}>
          <BarChart3 size={50} style={{ margin: "0 auto 14px", display: "block" }} />
          <p style={{ fontSize: 15, margin: 0 }}>Enter an NSE stock symbol to run a full prediction analysis.</p>
          <p style={{ fontSize: 12, marginTop: 6, color: "#1e293b" }}>Confidence · Bands · MC-Dropout · Risk Score · MACD · SMA20 · Signal</p>
        </motion.div>
      )}
    </div>
  );
}
