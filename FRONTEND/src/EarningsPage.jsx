import React, { useEffect, useState } from "react";
import { useParams, NavLink } from "react-router-dom";
import { fetchEarnings, fetchStockPage, fetchStockPrice } from "./api";
import {
  ComposedChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid
} from "recharts";
import "./StockDetailPage.css";
import "./EarningsPage.css";

const formatLargeNumber = (val, curr = "USD") => {
  if (val == null) return "-";
  const cs = curr === "INR" ? "₹" : "$";
  if (val >= 1e12) return `${cs}${(val / 1e12).toFixed(2)}T`;
  if (val >= 1e9) return `${cs}${(val / 1e9).toFixed(2)}B`;
  return `${cs}${val.toLocaleString()}`;
};

const EarningsHistoryTable = ({ tableData, companyName, symbol, currency }) => {
  const [rangeMode, setRangeMode] = useState("2 Years");
  
  const today = new Date();
  const twoYearsAgo = new Date(today);
  twoYearsAgo.setFullYear(today.getFullYear() - 2);
  
  const [startDate, setStartDate] = useState(twoYearsAgo.toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(today.toISOString().slice(0, 10));
  
  useEffect(() => {
    const t = new Date(); const s = new Date(t);
    if (rangeMode === "1 Year") s.setFullYear(t.getFullYear() - 1);
    else if (rangeMode === "2 Years") s.setFullYear(t.getFullYear() - 2);
    else if (rangeMode === "5 Years") s.setFullYear(t.getFullYear() - 5);
    else return;
    setStartDate(s.toISOString().slice(0, 10));
    setEndDate(t.toISOString().slice(0, 10));
  }, [rangeMode]);

  const filtered = tableData ? tableData.filter((r) => r.date >= startDate && r.date <= endDate) : [];

  const handleExport = () => {
    const header = ["DATE", "QUARTER", "CONSENSUS ESTIMATE", "REPORTED EPS", "BEAT/MISS", "GAAP EPS", "REVENUE ESTIMATE", "ACTUAL REVENUE"];
    const rows = filtered.map((r) => [
      r.date, r.quarter, r.consensus_eps ?? "", r.reported_eps ?? "", r.beat ?? "", r.reported_eps ?? "", "", r.actual_revenue ?? ""
    ]);
    const csv = [header, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${symbol}_earnings_history.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const [y, m, d] = dateStr.split('-');
      return `${parseInt(m)}/${parseInt(d)}/${y}`;
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="chart-section" style={{ padding: 24, overflow: 'hidden' }}>
      <h2 className="chart-title" style={{ marginBottom: 16 }}>{companyName} Earnings History by Quarter</h2>

      <div className="sc-history-controls" style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap', alignItems: 'flex-end', paddingBottom: 16, borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 140 }}>
          <label style={{ fontSize: 10, fontWeight: 600, color: '#94a3b8', letterSpacing: '0.05em' }}>TIME FRAME</label>
          <select value={rangeMode} onChange={(e) => setRangeMode(e.target.value)} style={{ padding: '9px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', borderRadius: 6, outline: 'none', fontSize: 13 }}>
            <option>Custom Range</option>
            <option>1 Year</option>
            <option>2 Years</option>
            <option>5 Years</option>
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 140 }}>
          <label style={{ fontSize: 10, fontWeight: 600, color: '#94a3b8', letterSpacing: '0.05em' }}>START DATE</label>
          <input type="date" value={startDate} onChange={(e) => { setStartDate(e.target.value); setRangeMode("Custom Range"); }} style={{ padding: '8px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', borderRadius: 6, outline: 'none', fontSize: 13 }} />
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1, minWidth: 140 }}>
          <label style={{ fontSize: 10, fontWeight: 600, color: '#94a3b8', letterSpacing: '0.05em' }}>END DATE</label>
          <input type="date" value={endDate} onChange={(e) => { setEndDate(e.target.value); setRangeMode("Custom Range"); }} style={{ padding: '8px 12px', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', borderRadius: 6, outline: 'none', fontSize: 13 }} />
        </div>

        <button onClick={handleExport} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 18px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', color: '#60a5fa', borderRadius: 6, fontWeight: 600, fontSize: 12, cursor: 'pointer', transition: 'all 0.2s', height: 36 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          EXPORT
        </button>
      </div>

      <div style={{ overflowX: 'auto', paddingBottom: 10 }}>
        <table className="analysis-table" style={{ width: '100%', minWidth: 900, fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>DATE</th>
              <th style={{ textAlign: 'left', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>QUARTER</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>CONSENSUS<br/>ESTIMATE</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>REPORTED<br/>EPS</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>BEAT/MISS</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>GAAP EPS</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>REVENUE<br/>ESTIMATE</th>
              <th style={{ textAlign: 'right', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>ACTUAL<br/>REVENUE</th>
              <th style={{ textAlign: 'center', padding: '12px 16px', color: '#64748b', fontSize: 11, letterSpacing: '0.05em' }}>DETAILS</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan="9" style={{ textAlign: 'center', padding: 24, color: '#64748b' }}>No data for selected range</td></tr>
            ) : filtered.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td style={{ fontWeight: 600, color: '#f8fafc', padding: '14px 16px' }}>{formatDate(row.date)}</td>
                <td style={{ fontWeight: 500, color: '#94a3b8', padding: '14px 16px' }}>{row.quarter}</td>
                <td style={{ textAlign: 'right', padding: '14px 16px', fontWeight: 500 }}>{row.consensus_eps != null ? `₹${row.consensus_eps.toFixed(2)}` : '—'}</td>
                <td style={{ textAlign: 'right', padding: '14px 16px', fontWeight: 500 }}>{row.reported_eps != null ? `₹${row.reported_eps.toFixed(2)}` : '—'}</td>
                <td style={{ textAlign: 'right', padding: '14px 16px', fontWeight: 600, color: row.beat >= 0 ? '#34d399' : '#f87171' }}>
                  {row.beat != null ? `${row.beat >= 0 ? '+' : ''}₹${row.beat.toFixed(2)}` : '—'}
                </td>
                <td style={{ textAlign: 'right', padding: '14px 16px', fontWeight: 500 }}>{row.reported_eps != null ? `₹${row.reported_eps.toFixed(2)}` : '—'}</td>
                <td style={{ textAlign: 'right', padding: '14px 16px', color: '#64748b' }}>—</td>
                <td style={{ textAlign: 'right', padding: '14px 16px', fontWeight: 500 }}>{row.actual_revenue ? formatLargeNumber(row.actual_revenue, currency) : '—'}</td>
                <td style={{ textAlign: 'center', padding: '14px 16px' }}>
                  <button style={{ background: 'transparent', border: '1px solid rgba(59, 130, 246, 0.4)', borderRadius: 4, width: 26, height: 26, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#60a5fa', transition: 'all 0.2s' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="9" x2="15" y2="9"></line><line x1="9" y1="13" x2="15" y2="13"></line><line x1="9" y1="17" x2="15" y2="17"></line></svg>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const EarningsPage = () => {
  const { symbol } = useParams();
  const [data, setData] = useState(null);
  const [stockInfo, setStockInfo] = useState(null);
  const [priceData, setPriceData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const [earnings, stock, priceInfo] = await Promise.all([
        fetchEarnings(symbol),
        fetchStockPage(symbol),
        fetchStockPrice(symbol).catch(() => null)
      ]);
      setData(earnings);
      setStockInfo(stock);
      setPriceData(priceInfo);
      setLoading(false);
    };
    load();
  }, [symbol]);

  if (loading || !data) return <div className="loading">Loading...</div>;

  const { summary, eps_estimate_vs_actual_chart, revenue_chart, earnings_history_table, analyst_estimates_table } = data;

  const companyName = stockInfo?.company_overview?.name || symbol;
  const currentPrice = priceData?.price || 0;
  const priceChange = priceData?.change || 0;
  const percentChange = priceData?.change_percent || 0;

  return (
    <div className="page">

      {/* HEADER - Consistent with StockDetailPage */}
      <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0 }}>
          {companyName}{" "}
          <span style={{ fontWeight: 400, fontSize: "0.65em", color: "#64748b" }}>{symbol}</span>
        </h1>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>
            ₹{currentPrice.toLocaleString("en-IN", {minimumFractionDigits: 2, maximumFractionDigits: 2})}
          </span>
          {priceChange != null && priceData?.price != null && (
            <span
              className={priceChange >= 0 ? "pos" : "neg"}
              style={{ fontSize: 17, fontWeight: 600, color: priceChange >= 0 ? "#34d399" : "#f87171" }}
            >
              {priceChange >= 0 ? "+" : ""}
              {priceChange.toFixed(2)}{" "}
              ({priceChange >= 0 ? "+" : ""}{percentChange.toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      {/* LAYOUT WITH SIDE NAV */}
      <div className="layout">
        <div className="stock-sidenav">
          <NavLink to={`/stock/${symbol}`} className="nav-item">STOCK-PAGE</NavLink>
          <NavLink to={`/chart/${symbol}`} className="nav-item">CHART</NavLink>
          <NavLink to={`/stock/${symbol}/competitors`} className="nav-item">COMPETITOR</NavLink>
          <NavLink to={`/dividend/${symbol}`} className="nav-item">DIVIDEND</NavLink>
          <NavLink to={`/earnings/${symbol}`} className="nav-item active">EARNINGS</NavLink>
          <NavLink to={`/financials/${symbol}`} className="nav-item">FINANCIALS</NavLink>
          <NavLink to={`/news/${symbol}`} className="nav-item">HEADLINES</NavLink>
          <NavLink to={`/options/${symbol}`} className="nav-item">OPTION CHAIN</NavLink>
          <NavLink to={`/sec/${symbol}`} className="nav-item">SEC FILINGS</NavLink>
          <NavLink to={`/shortinterest/${symbol}`} className="nav-item">SHORT INTEREST</NavLink>
          <NavLink to={`/stock/${symbol}`} className="nav-item buy-item">BUY STOCK</NavLink>
        </div>

        {/* BODY */}
        <div className="earnings-content">

          {/* SUMMARY HEADING */}
          <h2 className="section-title" style={{border: 'none', marginBottom: '10px'}}>{companyName} Earnings Summary</h2>

          {/* SUMMARY BOX */}
          <div className="summary-box">
            {summary.summary_text || `Earnings data for ${companyName}.`}
          </div>

          {/* 4 METRIC CARDS */}
          <div className="metric-grid">
            <div className="metric-card">
              <div className="m-label">Latest {summary.quarter}<br/>Earnings Date</div>
              <div className="m-value" style={{fontSize: '18px', letterSpacing: '-0.5px'}}>{summary.latest_earnings_date}</div>
              <div className="m-sub" style={{color: '#94a3b8'}}>REPORTED</div>
            </div>
            <div className="metric-card">
              <div className="m-label">Consensus EPS<br/>({summary.latest_earnings_date})</div>
              <div className="m-value">{summary.consensus_eps}</div>
            </div>
            <div className="metric-card">
              <div className="m-label">Actual EPS<br/>({summary.latest_earnings_date})</div>
              <div className={`m-value ${summary.beat >= 0 ? 'beat-pos' : 'beat-neg'}`}>{summary.actual_eps}</div>
              <div className={`m-sub ${summary.beat >= 0 ? 'beat-pos' : 'beat-neg'}`}>
                {summary.beat >= 0 ? `BEAT BY ${summary.beat}` : `MISSED BY ${Math.abs(summary.beat)}`}
              </div>
            </div>
            <div className="metric-card">
              <div className="m-label">Actual Revenue<br/>({summary.latest_earnings_date})</div>
              <div className="m-value" style={{fontSize: '18px'}}>{formatLargeNumber(summary.actual_revenue, summary.currency)}</div>
            </div>
          </div>

          {/* RESOURCES */}
          <div className="resources-row">
            <button className="res-btn">📄 {summary.quarter || "Latest"} Earnings Report</button>
            <button className="res-btn">💬 {summary.quarter || "Latest"} Conference Call</button>
            <button className="res-btn">📋 Press Release (8-K)</button>
            <button className="res-btn">📅 Quarterly Report (10-Q)</button>
          </div>

          {/* EPS ESTIMATE VS ACTUAL CHART */}
          <div className="chart-section">
            <div className="chart-title">{companyName} EPS Estimates &amp; Actuals by Quarter</div>
            <div className="legend">
              <span className="legend-item"><span className="legend-dot" style={{background: '#60a5fa'}}></span>Actual EPS</span>
              <span className="legend-item"><span className="legend-dot" style={{background: '#94a3b8', border: '1px dashed #64748b'}}></span>Estimated EPS</span>
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={eps_estimate_vs_actual_chart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="quarter" tick={{fill: '#94a3b8', fontSize: 11}} axisLine={false} tickLine={false} />
                  <YAxis tick={{fill: '#94a3b8', fontSize: 11}} tickFormatter={v => `₹${v}`} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "rgba(255,255,255,0.1)", borderRadius: '8px', fontSize: '12px', color: '#f8fafc' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Line type="monotone" dataKey="estimate_eps" name="Estimated EPS" stroke="#94a3b8" strokeWidth={2} strokeDasharray="5 4" dot={{r: 3, fill: '#94a3b8'}} connectNulls={true} />
                  <Area type="monotone" dataKey="actual_eps" name="Actual EPS" stroke="#60a5fa" strokeWidth={2.5} fill="rgba(59,130,246,0.15)" dot={{r: 4, fill: '#60a5fa'}} connectNulls={true} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* REVENUE CHART */}
          <div className="chart-section">
            <div className="chart-title">{companyName} Estimated and Actual Revenue by Quarter</div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={revenue_chart} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="quarter" tick={{fill: '#94a3b8', fontSize: 11}} axisLine={false} tickLine={false} />
                  <YAxis tick={{fill: '#94a3b8', fontSize: 11}} tickFormatter={v => formatLargeNumber(v, summary.currency)} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", borderColor: "rgba(255,255,255,0.1)", borderRadius: '8px', fontSize: '12px', color: '#f8fafc' }}
                    itemStyle={{ color: '#e2e8f0' }}
                    formatter={(v) => formatLargeNumber(v, summary.currency)}
                  />
                  <Area type="monotone" dataKey="revenue" name="Revenue" stroke="#60a5fa" strokeWidth={2.5} fill="rgba(59,130,246,0.15)" dot={{r: 5, fill: '#60a5fa'}} connectNulls={true} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ANALYST EPS ESTIMATES TABLE */}
          <div className="chart-section">
            <div className="chart-title">{companyName} Analyst EPS Estimates</div>
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th># Analysts</th>
                  <th>Low Estimate</th>
                  <th>High Estimate</th>
                  <th>Average Estimate</th>
                </tr>
              </thead>
              <tbody>
                {analyst_estimates_table && analyst_estimates_table.map((row, i) => (
                  <tr key={i} style={{fontWeight: row.quarter.includes('FY') ? '600' : 'normal', color: row.quarter.includes('FY') ? '#93c5fd' : 'inherit'}}>
                    <td>{row.quarter}</td>
                    <td>{row.num_analysts}</td>
                    <td>{row.low_eps != null ? `₹${row.low_eps}` : '-'}</td>
                    <td>{row.high_eps != null ? `₹${row.high_eps}` : '-'}</td>
                    <td>{row.avg_eps != null ? `₹${row.avg_eps}` : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* EARNINGS HISTORY TABLE */}
          <EarningsHistoryTable 
            tableData={earnings_history_table} 
            companyName={companyName} 
            symbol={symbol} 
            currency={summary.currency} 
          />

        </div>
      </div>
    </div>
  );
};

export default EarningsPage;