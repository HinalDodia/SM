import React, { useEffect, useState } from "react";
import { useParams, NavLink } from "react-router-dom";
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
  const [visibleSentimentComps, setVisibleSentimentComps] = useState({});
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

      // also initialize sentiment visibility
      setVisibleSentimentComps(initVisible);
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

        <div className="stock-sidenav">
          <NavLink to={`/stock/${symbol}`} className="nav-item">STOCK-PAGE</NavLink>
          <NavLink to={`/chart/${symbol}`} className="nav-item">CHART</NavLink>
          <NavLink to={`/stock/${symbol}/competitors`} className="nav-item active">COMPETITOR</NavLink>
          <NavLink to={`/dividend/${symbol}`} className="nav-item">DIVIDEND</NavLink>
          <NavLink to={`/earnings/${symbol}`} className="nav-item">EARNINGS</NavLink>
          <NavLink to={`/financials/${symbol}`} className="nav-item">FINANCIALS</NavLink>
          <NavLink to={`/news/${symbol}`} className="nav-item">HEADLINES</NavLink>
          <NavLink to={`/options/${symbol}`} className="nav-item">OPTION CHAIN</NavLink>
          <NavLink to={`/sec/${symbol}`} className="nav-item">SEC FILINGS</NavLink>
          <NavLink to={`/shortinterest/${symbol}`} className="nav-item">SHORT INTEREST</NavLink>
          <NavLink to={`/stock/${symbol}`} className="nav-item buy-item">BUY STOCK</NavLink>
        </div>




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

          {/* 3. MEDIA SENTIMENT OVER TIME */}
          <div className="card full-width">
            <h3>Media Sentiment Over Time</h3>

            {/* Sentiment Trend Chart (Matching Reference) */}
            {data.sentiment_chart && data.sentiment_chart.length > 0 ? (
              <div style={{ height: "350px", marginBottom: "40px", background: "rgba(255,255,255,0.02)", borderRadius: "12px", padding: "20px", border: "1px solid rgba(255,255,255,0.05)" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.sentiment_chart} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      stroke="#006affff"
                      tick={{ fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                      padding={{ left: 10, right: 10 }}
                    />
                    <YAxis
                      stroke="#ff0000ff"
                      tick={{ fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                      domain={[0.5, 1.5]}
                      ticks={[0.65, 1.0, 1.35]}
                      tickFormatter={(v) =>
                        v >= 1.3 ? "Bullish" : v <= 0.7 ? "Bearish" : "Neutral"
                      }
                    />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#1e293b", borderColor: "#334155", borderRadius: "8px" }}
                      itemStyle={{ fontSize: "14px" }}
                      labelFormatter={(label) => `Week of ${label}`}
                      formatter={(value, name) => {
                        const label = value >= 1.15 ? "Bullish" : value <= 0.85 ? "Bearish" : "Neutral";
                        return [`${label} (${value})`, name];
                      }}
                    />
                    <Legend
                      layout="vertical"
                      align="right"
                      verticalAlign="middle"
                      iconType="square"
                      wrapperStyle={{ paddingLeft: "20px" }}
                    />
                    {/* Neutral baseline */}
                    <ReferenceLine y={1.0} stroke="rgba(255,255,255,0.15)" strokeWidth={1} strokeDasharray="4 4" label={{ value: "Neutral", position: "insideLeft", fill: "#64748b", fontSize: 11 }} />
                    {/* Bullish threshold */}
                    <ReferenceLine y={1.15} stroke="rgba(16,185,129,0.15)" strokeWidth={1} strokeDasharray="3 3" />
                    {/* Bearish threshold */}
                    <ReferenceLine y={0.85} stroke="rgba(239,68,68,0.15)" strokeWidth={1} strokeDasharray="3 3" />

                    {/* Main Stock Line */}
                    <Line
                      type="monotone"
                      dataKey={symbol}
                      name={symbol}
                      stroke="#00fb11ff"
                      strokeWidth={3}
                      dot={{ r: 4 }}
                      activeDot={{ r: 6 }}
                      connectNulls={true}
                    />

                    {/* Competitor Lines */}
                    {(Array.isArray(data.competitor_list) ? data.competitor_list : []).filter(c => visibleSentimentComps[c.symbol] !== false).map((c, i) => (
                      <Line
                        key={c.symbol}
                        type="monotone"
                        dataKey={c.symbol}
                        name={c.symbol}
                        stroke={competitorColors[i % competitorColors.length]}
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        connectNulls={true}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: "30px", color: "#64748b", background: "rgba(255,255,255,0.02)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.05)", marginBottom: "40px" }}>
                Sentiment chart data is currently unavailable. The AI analysis service may be warming up — try refreshing in a moment.
              </div>
            )}

            <div className="news-list-container" style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {!data.media_sentiment || data.media_sentiment.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px", color: "#94a3b8" }}>
                  No recent news articles found for this company.
                </div>
              ) : (
                data.media_sentiment.map((n, i) => {
                  // HF uses "link" and "learn"; local pipeline uses "url" and "action"
                  const articleUrl = n.url || n.link || "#";
                  const articleAction = n.action || n.learn || "";
                  const sentColor = n.sentiment === "bullish" ? "#10b981"
                    : n.sentiment === "bearish" ? "#ef4444"
                      : "#94a3b8";
                  const sentBg = n.sentiment === "bullish" ? "rgba(16,185,129,0.2)"
                    : n.sentiment === "bearish" ? "rgba(239,68,68,0.2)"
                      : "rgba(100,116,139,0.2)";
                  const confidencePct = n.confidence != null
                    ? ` · ${(n.confidence * 100).toFixed(0)}% confidence`
                    : "";

                  return (
                    <div key={i} className="news-item-hover-trigger" style={{ position: 'relative', padding: '15px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '8px', cursor: 'pointer' }}>

                      {/* Top row: thumbnail + title + badge */}
                      <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                        {n.image && (
                          <img
                            src={n.image}
                            alt=""
                            style={{ width: '80px', height: '52px', objectFit: 'cover', borderRadius: '6px', flexShrink: 0 }}
                            onError={e => { e.target.style.display = 'none'; }}
                          />
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                            <a href={articleUrl} target="_blank" rel="noreferrer"
                              style={{ color: '#e2e8f0', textDecoration: 'none', fontWeight: '500', fontSize: '15px', flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {n.title}
                            </a>
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexShrink: 0 }}>
                              <span style={{ padding: "2px 8px", borderRadius: "4px", fontSize: "10px", fontWeight: "bold", background: sentBg, color: sentColor, textTransform: "uppercase" }}>
                                {n.sentiment || "neutral"}
                              </span>
                              <span style={{ fontSize: '12px', color: '#64748b', whiteSpace: 'nowrap' }}>{formatTime(n.time)}</span>
                            </div>
                          </div>

                          {/* Publisher + sentiment source */}
                          {(n.publisher || n.sentiment_source) && (
                            <div style={{ marginTop: '4px', fontSize: '11px', color: '#475569' }}>
                              {n.publisher && <span>{n.publisher}</span>}
                              {n.sentiment_source && <span style={{ marginLeft: '8px', color: '#334155' }}>via {n.sentiment_source}</span>}
                              {confidencePct && <span style={{ marginLeft: '8px', color: sentColor }}>{confidencePct}</span>}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Expandable details */}
                      <div className="news-details-hover" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(255,255,255,0.05)', fontSize: '13px', color: '#cbd5e1' }}>
                        {n.summary && (
                          <div style={{ marginBottom: '8px' }}><strong style={{ color: '#94a3b8' }}>Summary:</strong> {n.summary}</div>
                        )}
                        <div style={{ marginBottom: '8px', color: sentColor }}>
                          <strong style={{ color: '#94a3b8' }}>Sentiment:</strong> {n.sentiment?.toUpperCase()}
                          {n.confidence != null && <span style={{ marginLeft: '8px', fontSize: '12px', opacity: 0.8 }}>({(n.confidence * 100).toFixed(1)}% confidence)</span>}
                        </div>
                        {n.impact && (
                          <div style={{ marginBottom: '8px' }}><strong style={{ color: '#94a3b8' }}>Impact:</strong> {n.impact}</div>
                        )}
                        {articleAction && (
                          <div style={{ color: '#60a5fa' }}><strong style={{ color: '#94a3b8' }}>Learnings:</strong> {articleAction}</div>
                        )}
                      </div>

                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* 4. COMPARISON WITH COMPETITOR CHART */}
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