import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Sidenav from "./Sidenav";
import { fetchCompetitors } from "./api";

import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, ComposedChart, XAxis, YAxis, Tooltip, Legend, CartesianGrid, ResponsiveContainer, ReferenceLine
} from "recharts";

import "./StockDetailPage.css";
import "./Competitor.css";

const CompetitorsPage = () => {

  const { symbol } = useParams();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [showVolume, setShowVolume] = useState(false);
  const [visibleCompetitors, setVisibleCompetitors] = useState({});
  const [show50mda, setShow50mda] = useState(false);
  const [show200mda, setShow200mda] = useState(false);

  // Initialize all competitors as visible when data loads
  const competitorColors = ["#10b981", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

  useEffect(() => {
    let cancelled = false;
    setData(null); setError(null); setLoading(true);

    fetchCompetitors(symbol)
      .then(res => { if (!cancelled) { setData(res); setLoading(false); } })
      .catch(err => { if (!cancelled) { setError(err.message); setLoading(false); } });

    return () => { cancelled = true; };
  }, [symbol]);

  useEffect(() => {
    if ((data?.competitor_list || []).length > 0) {
      const initVisible = {};
      data.competitor_list.forEach(c => {
        initVisible[c.symbol] = true;
      });
      setVisibleCompetitors(initVisible);
    }
  }, [data]);

  if (loading) return <div className="loading">Loading…</div>;
  if (error) return <div className="loading" style={{ color: "#ef4444" }}>Error: {error}</div>;
  if (!data) return <div className="loading">No Data</div>;
  if (data.error) return <div className="loading" style={{ color: "#ef4444" }}>Error: {data.error}</div>;

  /* Chart Mapping */

  const chartData = (Array.isArray(data.comparison) ? data.comparison : []).map(item => ({
    symbol: item.symbol,
    marketCap: item.marketCap,
    pe: item.pe || 0,
    profitMargin: item.profitMargin || 0
  }));

  /* Normalize chart_history → convert all prices to % change from first value */
  const allStockKeys = [symbol, ...(data.competitor_list || []).map(c => c.symbol)];

  // Initialize visibility for competitors on first render
  const compSymbols = (data.competitor_list || []).map(c => c.symbol);


  const baseValues = {};
  (data.chart_history || []).forEach(row => {
    allStockKeys.forEach(key => {
      if (!(key in baseValues) && row[key] != null) {
        baseValues[key] = row[key];
      }
    });
  });

  const normalizedHistory = (data.chart_history || []).map(row => {
    const r = { date: row.date, Volume: row.Volume };
    allStockKeys.forEach(key => {
      if (row[key] != null && baseValues[key]) {
        r[key] = parseFloat(((row[key] / baseValues[key] - 1) * 100).toFixed(2));
      }
    });
    // Normalize MAs too (relative to main stock base)
    if (row["50mda"] != null && baseValues[symbol]) r["50mda"] = parseFloat(((row["50mda"] / baseValues[symbol] - 1) * 100).toFixed(2));
    if (row["200mda"] != null && baseValues[symbol]) r["200mda"] = parseFloat(((row["200mda"] / baseValues[symbol] - 1) * 100).toFixed(2));
    return r;
  });



  /* Formatters */

  const formatMarketCap = (num) => {

    if (!num) return "N/A";

    if (num > 1e12) return (num / 1e12).toFixed(1) + "T";
    if (num > 1e9) return (num / 1e9).toFixed(1) + "B";
    if (num > 1e6) return (num / 1e6).toFixed(1) + "M";

    return num;

  };


  const formatPercent = (num) => {

    if (num === null || num === undefined) return "N/A";

    return (num * 100).toFixed(2) + "%";

  };

  // Format time: can be a Unix timestamp (int) or an ISO string
  const formatTime = (t) => {
    if (!t) return "N/A";
    if (typeof t === "number") return new Date(t * 1000).toISOString().substring(0, 10);
    return String(t).substring(0, 10);
  };


  return (

    <div className="page">


      {/* HEADER */}

      <div className="header">

        <h1>

          Competitors

          <span>{symbol}</span>

        </h1>

      </div>



      <div className="layout">


        {/* SIDEBAR */}

        <Sidenav symbol={symbol} />
        {/* Right Content Grid */}
        <div className="grid">

          {/* 1. LIST OF COMPETITORS */}
          <div className="card full-width">
            <h3>List of Competitors</h3>
            <div className="competitor-grid">
              {(data.competitor_list || []).map(c => (
                <div key={c.symbol} className="competitor-card">
                  <div className="symbol">{c.symbol}</div>
                  <div className="company">{c.name}</div>
                </div>
              ))}
            </div>
          </div>

          {/* 2. ANALYSIS WITH COMPETITORS */}
          <div className="card full-width">
            <h3>Analysis with Competitors</h3>
            <div style={{ display: "flex", gap: "30px", flexWrap: "wrap", alignItems: "flex-start" }}>

              {/* Table */}
              <div style={{ flex: "1 1 500px" }}>
                <table className="analysis-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Market Cap</th>
                      <th>P/E</th>
                      <th>Profit Margin</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(Array.isArray(data.analysis) ? data.analysis : []).map(s => (
                      <tr key={s.symbol}>
                        <td>{s.symbol}</td>
                        <td>{formatMarketCap(s.marketCap)}</td>
                        <td>{s.pe || "N/A"}</td>
                        <td>{formatPercent(s.profitMargin)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Bar Chart */}
              <div style={{ flex: "1 1 500px", height: "300px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis dataKey="symbol" stroke="#94a3b8" />
                    <YAxis stroke="#94a3b8" />
                    <Tooltip contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155" }} />
                    <Legend />
                    <Bar dataKey="pe" name="P/E Ratio" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

            </div>
          </div>


          {/* 3. COMPARISON WITH COMPETITOR CHART */}
          <div className="card full-width">

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", marginBottom: "20px", borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: "15px" }}>
              <div>
                <h3 style={{ margin: 0, borderBottom: "none" }}>Historical Comparison</h3>
                <span style={{ fontSize: "12px", color: "#64748b" }}>% change from start — all stocks normalized to same baseline</span>
              </div>

              {/* Checkboxes UI */}
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", fontSize: "13px", color: "#e2e8f0", alignItems: "center" }}>
                {(data.competitor_list || []).map((c, i) => (
                  <label key={c.symbol} style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={visibleCompetitors[c.symbol] !== false}
                      onChange={(e) => setVisibleCompetitors(prev => ({ ...prev, [c.symbol]: e.target.checked }))}
                    />
                    <span style={{ color: competitorColors[i % competitorColors.length] }}>{c.symbol}</span>
                  </label>
                ))}
                <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="checkbox" checked={show50mda} onChange={(e) => setShow50mda(e.target.checked)} />
                  50 MA
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="checkbox" checked={show200mda} onChange={(e) => setShow200mda(e.target.checked)} />
                  200 MA
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="checkbox" checked={showVolume} onChange={(e) => setShowVolume(e.target.checked)} />
                  Volume
                </label>
              </div>
            </div>

            <div style={{ width: "100%", height: "450px", display: "block" }}>
              {!data.chart_history || data.chart_history.length === 0 ? (
                <div style={{ textAlign: "center", paddingTop: "150px", color: "#94a3b8" }}>Chart data loading or unavailable.</div>
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <ComposedChart data={normalizedHistory} margin={{ top: 10, right: showVolume ? 50 : 0, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />

                    <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 12 }} minTickGap={30} />
                    <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} tickFormatter={(v) => `${v}%`} />
                    {showVolume && <YAxis yAxisId="vol" orientation="right" stroke="#64748b" tick={{ fontSize: 12 }} tickFormatter={(v) => formatMarketCap(v)} />}

                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", borderRadius: "8px" }}
                      labelStyle={{ color: "#94a3b8", marginBottom: "5px" }}
                      formatter={(value, name) => name === "Volume" ? [formatMarketCap(value), name] : [`${value}%`, name]}
                    />
                    <Legend wrapperStyle={{ paddingTop: "10px" }} />

                    {showVolume && <Bar yAxisId="vol" dataKey="Volume" name="Volume" fill="rgba(100, 116, 139, 0.3)" maxBarSize={15} />}

                    <Line type="monotone" dataKey={symbol} name={`${symbol} Price`} stroke="#3b82f6" strokeWidth={3} dot={false} activeDot={{ r: 6 }} />

                    {show50mda && <Line type="monotone" dataKey="50mda" name="50 MA" stroke="#f59e0b" strokeWidth={2} strokeDasharray="5 5" dot={false} />}
                    {show200mda && <Line type="monotone" dataKey="200mda" name="200 MA" stroke="#ef4444" strokeWidth={2} strokeDasharray="5 5" dot={false} />}

                    {/* Individual competitor lines */}
                    {(data.competitor_list || []).map((c, i) =>
                      visibleCompetitors[c.symbol] !== false ? (
                        <Line key={c.symbol} type="monotone" dataKey={c.symbol} name={c.symbol} stroke={competitorColors[i % competitorColors.length]} strokeWidth={2} dot={false} />
                      ) : null
                    )}

                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>

          </div>

        </div>


      </div> {/* LAYOUT */}

    </div>

  )

}

export default CompetitorsPage;