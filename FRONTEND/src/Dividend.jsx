import React, { useEffect, useState } from "react";
import { useParams, NavLink } from "react-router-dom";
import { fetchDividendSummary } from "./api";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, ResponsiveContainer
} from "recharts";
import "./StockDetailPage.css";
import "./Dividend.css";

const DividendPage = () => {
  const { symbol } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openFaq, setOpenFaq] = useState(null);
  const [historyTimeframe, setHistoryTimeframe] = useState("All");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchDividendSummary(symbol)
      .then((res) => {
        if (!cancelled) {
          if (res.error) setError(res.error);
          else setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [symbol]);

  if (loading) return <div className="loading">Loading Dividend Data...</div>;
  if (error) return <div className="loading" style={{ color: "#ef4444" }}>Error: {error}</div>;
  if (!data) return <div className="loading">No Dividend Data Available</div>;

  const {
    summary = {},
    metadata = {},
    stock_header = {},
    description = "",
    dividends_by_quarter = [],
    dividend_yield_over_time = [],
    dividend_table = [],
    comparison = {},
    faq = []
  } = data;

  const quarterlyChartData = dividends_by_quarter.map(d => ({
    ...d,
    label: `Q${d.quarter} ${d.year}`
  }));

  const yieldChartData = dividend_yield_over_time.filter(d => d.yield != null);

  const toggleFaq = (index) => setOpenFaq(openFaq === index ? null : index);

  const filterByDate = (dateStr) => {
    if (!dateStr || dateStr === "N/A" || dateStr === "—") return true;
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return true;
    let isValid = true;
    const now = new Date();
    if (historyTimeframe === "1 Year") {
      const past = new Date(); past.setFullYear(now.getFullYear() - 1);
      if (date < past) isValid = false;
    } else if (historyTimeframe === "2 Years") {
      const past = new Date(); past.setFullYear(now.getFullYear() - 2);
      if (date < past) isValid = false;
    } else if (historyTimeframe === "5 Years") {
      const past = new Date(); past.setFullYear(now.getFullYear() - 5);
      if (date < past) isValid = false;
    }
    if (startDate && date < new Date(startDate)) isValid = false;
    if (endDate && date > new Date(endDate)) isValid = false;
    return isValid;
  };

  const filteredHistory = (dividend_table || []).filter(row =>
    filterByDate(row.ex_dividend_date || row.announced_date)
  );

  const handleExport = () => {
    const headers = ["Announced", "Period", "Payment", "Change", "Yield", "Ex-Date", "Record Date", "Payable"];
    const csvData = filteredHistory.map(row =>
      [row.announced_date, row.period, row.payment, row.payment_change,
      row.yield, row.ex_dividend_date, row.record_date, row.payable_date].join(",")
    );
    const blob = new Blob([[headers.join(","), ...csvData].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `${symbol}_dividend_history.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const pb = summary.payout_ratio_breakdown || {};

  const kpiCards = [
    { label: "DIVIDEND YIELD", value: summary.dividend_yield != null ? `${Number(summary.dividend_yield).toFixed(2)}%` : "N/A", sub: null },
    { label: "ANNUAL DIVIDEND", value: summary.annual_dividend != null ? `₹${summary.annual_dividend}` : "N/A", sub: null },
    { label: "RECENT PAYMENT", value: summary.recent_dividend_payment != null ? `₹${summary.recent_dividend_payment}` : "N/A", sub: summary.formatted_date || null },
    { label: "5-YEAR CAGR", value: summary.five_year_growth != null ? `${Number(summary.five_year_growth).toFixed(2)}%` : "N/A", sub: null },
    { label: "TRACK RECORD", value: summary.dividend_increase_track_record != null ? `${summary.dividend_increase_track_record} yrs` : "N/A", sub: null },
    { label: "PAYOUT RATIO", value: summary.payout_ratio != null ? `${Number(summary.payout_ratio).toFixed(2)}%` : "N/A", sub: null },
  ];

  return (
    <div className="page">

      {/* ── HEADER ── */}
      <div className="header">
        <h1>
          {metadata.company_name || symbol}{" "}
          <span style={{ fontWeight: 400, fontSize: "0.65em", color: "#64748b" }}>{symbol}</span>
        </h1>
        <div style={{ marginTop: 10, display: "flex", alignItems: "baseline", gap: 14 }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>
            ₹{stock_header.stock_price?.toLocaleString("en-IN") ?? "—"}
          </span>
          {stock_header.price_change != null && (
            <span
              className={stock_header.price_change >= 0 ? "pos" : "neg"}
              style={{ fontSize: 17, fontWeight: 600 }}
            >
              {stock_header.price_change >= 0 ? "+" : ""}
              {stock_header.price_change?.toFixed(2)}{" "}
              ({stock_header.percentage_change?.toFixed(2)}%)
            </span>
          )}
        </div>
      </div>

      <div className="layout">

        {/* ── SIDEBAR ── */}
        <div className="stock-sidenav">
          <NavLink to={`/stock/${symbol}`} className="nav-item">STOCK-PAGE</NavLink>
          <NavLink to={`/chart/${symbol}`} className="nav-item">CHART</NavLink>
          <NavLink to={`/stock/${symbol}/competitors`} className="nav-item">COMPETITOR</NavLink>
          <NavLink to={`/dividend/${symbol}`} className="nav-item active">DIVIDEND</NavLink>
          <NavLink to={`/earnings/${symbol}`} className="nav-item">EARNINGS</NavLink>
          <NavLink to={`/financials/${symbol}`} className="nav-item">FINANCIALS</NavLink>
          <NavLink to={`/news/${symbol}`} className="nav-item">HEADLINES</NavLink>
          <NavLink to={`/options/${symbol}`} className="nav-item">OPTION CHAIN</NavLink>
          <NavLink to={`/sec/${symbol}`} className="nav-item">SEC FILINGS</NavLink>
          <NavLink to={`/shortinterest/${symbol}`} className="nav-item">SHORT INTEREST</NavLink>
          <NavLink to={`/stock/${symbol}`} className="nav-item buy-item">BUY STOCK</NavLink>
        </div>

        {/* ── MAIN CONTENT ── */}
        <div className="div-content">

          {/* 1 ── KPI GRID 3 × 2 */}
          <div className="div-kpi-grid">
            {kpiCards.map(({ label, value, sub }) => (
              <div className="div-kpi-card" key={label}>
                <div className="div-kpi-label">{label}</div>
                <div className="div-kpi-value">{value}</div>
                {sub && <div className="div-kpi-sub">{sub}</div>}
              </div>
            ))}
          </div>

          {/* 2 ── DESCRIPTION */}
          <div className="div-card">
            <h3 className="div-card-title">Dividend Summary</h3>
            <p className="div-desc-text">{description || "No description available."}</p>
          </div>

          {/* 3 ── CHARTS */}
          <div className="div-card div-charts-row">
            <div className="div-chart-half">
              <h3 className="div-card-title">Dividends Per Quarter</h3>
              <div className="div-chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={quarterlyChartData} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="label" axisLine={false} tickLine={false}
                      tick={{ fill: "#9aa7b6", fontSize: 11 }} minTickGap={25} />
                    <YAxis axisLine={false} tickLine={false}
                      tick={{ fill: "#9aa7b6", fontSize: 11 }} width={42} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0e1722", borderColor: "rgba(255,255,255,0.1)", color: "#fff" }}
                      itemStyle={{ color: "#26E07F" }}
                      formatter={(v) => [`₹${v}`, "Dividend"]}
                    />
                    <Bar dataKey="dividend" fill="#26E07F" radius={[3, 3, 0, 0]} maxBarSize={22} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="div-chart-divider" />

            <div className="div-chart-half">
              <h3 className="div-card-title">Dividend Yield Over Time</h3>
              <div className="div-chart-box">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={yieldChartData} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="date" axisLine={false} tickLine={false}
                      tick={{ fill: "#9aa7b6", fontSize: 11 }} minTickGap={50} />
                    <YAxis axisLine={false} tickLine={false}
                      tick={{ fill: "#9aa7b6", fontSize: 11 }} domain={["auto", "auto"]} width={42} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0e1722", borderColor: "rgba(255,255,255,0.1)", color: "#fff" }}
                      itemStyle={{ color: "#54C5FF" }}
                      formatter={(v) => [`${v}%`, "Yield"]}
                    />
                    <Line type="monotone" dataKey="yield" stroke="#54C5FF" strokeWidth={2}
                      dot={false} activeDot={{ r: 4, fill: "#54C5FF" }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* 4 ── COMPARISON TABLE */}
          <div className="div-card">
            <h3 className="div-card-title">Dividend Comparison</h3>
            <div className="div-table-wrap">
              <table className="div-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>{symbol}</th>
                    <th>Peer (INFY)</th>
                    <th>Industry Avg (WIPRO)</th>
                    <th>Market Avg</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Annual Dividend</td>
                    <td>₹{summary.annual_dividend ?? "N/A"}</td>
                    <td>{comparison.peer?.annual_dividend != null ? `₹${comparison.peer.annual_dividend}` : "N/A"}</td>
                    <td>{comparison.industry_avg?.annual_dividend != null ? `₹${comparison.industry_avg.annual_dividend}` : "N/A"}</td>
                    <td>{comparison.market_avg?.annual_dividend != null ? `₹${comparison.market_avg.annual_dividend}` : "—"}</td>
                  </tr>
                  <tr>
                    <td>Dividend Yield</td>
                    <td>{summary.dividend_yield != null ? `${Number(summary.dividend_yield).toFixed(2)}%` : "N/A"}</td>
                    <td>{comparison.peer?.dividend_yield != null ? `${comparison.peer.dividend_yield}%` : "—"}</td>
                    <td>{comparison.industry_avg?.dividend_yield != null ? `${comparison.industry_avg.dividend_yield}%` : "—"}</td>
                    <td>{comparison.market_avg?.dividend_yield != null ? `${comparison.market_avg.dividend_yield}%` : "—"}</td>
                  </tr>
                  <tr>
                    <td>Track Record</td>
                    <td>{summary.dividend_increase_track_record ?? "0"} yrs</td>
                    <td>{comparison.peer?.track_record ?? "0"} yrs yrs</td>
                    <td>{comparison.industry_avg?.track_record ?? "0"} yrs</td>
                    <td>{comparison.market_avg?.track_record != null && comparison.market_avg.track_record !== "—" ? `${comparison.market_avg.track_record} yrs` : "—"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* 5 ── PAYOUT BREAKDOWN */}
          <div className="div-card">
            <h3 className="div-card-title">Payout Ratio Breakdown</h3>
            <div className="div-table-wrap">
              <table className="div-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Trailing 12M</th>
                    <th>This Year Est.</th>
                    <th>Next Year Est.</th>
                    <th>Cash Flow</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Payout Ratio</td>
                    <td>{pb.trailing_12_months != null ? `${pb.trailing_12_months}%` : "N/A"}</td>
                    <td>{pb.this_year_estimate != null ? `${pb.this_year_estimate}%` : "N/A"}</td>
                    <td>{pb.next_year_estimate != null ? `${pb.next_year_estimate}%` : "N/A"}</td>
                    <td>{pb.cashflow != null ? `${pb.cashflow}%` : "N/A"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* 6 ── DIVIDEND HISTORY TABLE */}
          <div className="div-card">
            <div className="div-history-header">
              <h3 className="div-card-title" style={{ margin: 0 }}>Dividend History</h3>
              <div className="div-history-controls">
                <div className="div-ctrl-group">
                  <label className="div-ctrl-label">Timeframe</label>
                  <select className="div-select" value={historyTimeframe}
                    onChange={(e) => setHistoryTimeframe(e.target.value)}>
                    <option value="1 Year">1 Year</option>
                    <option value="2 Years">2 Years</option>
                    <option value="5 Years">5 Years</option>
                    <option value="All">All</option>
                  </select>
                </div>
                <div className="div-ctrl-group">
                  <label className="div-ctrl-label">From</label>
                  <input type="date" className="div-date-input"
                    value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </div>
                <div className="div-ctrl-group">
                  <label className="div-ctrl-label">To</label>
                  <input type="date" className="div-date-input"
                    value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </div>
                <button className="div-export-btn" onClick={handleExport}>Export CSV</button>
              </div>
            </div>

            <div className="div-table-scroll">
              <table className="div-table sticky-header">
                <thead>
                  <tr>
                    <th>Announced</th>
                    <th>Period</th>
                    <th>Payment</th>
                    <th>Change</th>
                    <th>Yield</th>
                    <th>Ex-Date</th>
                    <th>Record Date</th>
                    <th>Payable</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHistory.map((row, i) => (
                    <tr key={i}>
                      <td>{row.announced_date}</td>
                      <td>{row.period}</td>
                      <td>₹{row.payment}</td>
                      <td className={row.payment_change == null ? "" : row.payment_change >= 0 ? "pos" : "neg"}>
                        {row.payment_change != null
                          ? `${row.payment_change > 0 ? "+" : ""}${row.payment_change}%`
                          : "—"}
                      </td>
                      <td>{row.yield != null ? `${row.yield}%` : "—"}</td>
                      <td>{row.ex_dividend_date}</td>
                      <td>{row.record_date}</td>
                      <td>{row.payable_date}</td>
                    </tr>
                  ))}
                  {filteredHistory.length === 0 && (
                    <tr>
                      <td colSpan="8" style={{ textAlign: "center", padding: 24, color: "#64748b" }}>
                        No dividend history found for the selected range.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 7 ── FAQ */}
          <div className="div-card">
            <h3 className="div-card-title">Frequently Asked Questions</h3>
            {faq.map((item, i) => (
              <div key={i} className="div-faq-item">
                <div className="div-faq-q" onClick={() => toggleFaq(i)}>
                  <span>{item.question}</span>
                  <span className="div-faq-icon">{openFaq === i ? "−" : "+"}</span>
                </div>
                {openFaq === i && <div className="div-faq-a">{item.answer}</div>}
              </div>
            ))}
          </div>

        </div>
      </div>
    </div>
  );
};

export default DividendPage;