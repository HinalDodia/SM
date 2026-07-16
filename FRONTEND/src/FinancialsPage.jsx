import React, { useEffect, useState, useMemo } from "react";
import { useParams, NavLink } from "react-router-dom";
import { fetchFinancials, fetchStockPage, fetchStockPrice } from "./api";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar, Legend
} from "recharts";
import { 
  ChevronDown, ChevronUp, Info, Download, 
  TrendingUp, Activity, ShieldCheck, 
  BarChart3, PieChart
} from "lucide-react";
import "./StockDetailPage.css";
import "./FinancialsPage.css";

const FinancialsPage = () => {
  const { symbol } = useParams();
  const [data, setData] = useState(null);
  const [stockInfo, setStockInfo] = useState(null);
  const [priceData, setPriceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [period, setPeriod] = useState("Annual"); // "Annual" or "Quarterly"
  const [openFaq, setOpenFaq] = useState(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [financials, stock, priceInfo] = await Promise.all([
          fetchFinancials(symbol),
          fetchStockPage(symbol),
          fetchStockPrice(symbol).catch(() => null)
        ]);
        
        if (financials.error) throw new Error(financials.error);
        
        setData(financials);
        setStockInfo(stock);
        setPriceData(priceInfo);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [symbol]);

  // Derived data based on period
  const currentIncome = useMemo(() => {
    if (!data) return [];
    return period === "Annual" ? data.income_statement : data.quarterly_income_statement;
  }, [data, period]);

  const currentBalance = useMemo(() => {
    if (!data) return [];
    return period === "Annual" ? data.balance_sheet : data.quarterly_balance_sheet;
  }, [data, period]);

  const currentCashflow = useMemo(() => {
    if (!data) return [];
    return period === "Annual" ? data.cashflow_statement : data.quarterly_cashflow_statement;
  }, [data, period]);

  if (loading) return <div className="loading">Loading Financial Data...</div>;
  if (error) return <div className="loading" style={{ color: "#ef4444" }}>Error: {error}</div>;
  if (!data) return <div className="loading">No Data Found</div>;

  const { ratios, revenue_chart, income_chart, ai_summary, faqs, table_config } = data;
  const companyName = stockInfo?.company_overview?.name || symbol;
  const currentPrice = priceData?.price || 0;
  const priceChange = priceData?.change || 0;
  const percentChange = priceData?.change_percent || 0;

  const formatVal = (val) => {
    if (val == null) return "—";
    if (typeof val === "string") return val;
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  const FinanceTable = ({ title, statementData, type }) => {
    if (!statementData || statementData.length === 0) return null;

    // Identify rows dynamically from the first period object
    // Excluding "year" or "quarter" which are our column headers
    const rowKeys = Object.keys(statementData[0]).filter(k => k !== "year" && k !== "quarter" && !k.endsWith("_display"));
    
    // Formatting label for row
    const formatLabel = (key) => {
        return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
    };

    return (
      <div className="table-container animate-in fade-in slide-in-from-bottom duration-500">
        <div className="table-header-box">
          <h3 className="chart-title-sm">{title} ({period})</h3>
          <button className="action-btn btn-outline" onClick={() => {}}>
            <Download size={14} /> EXPORT
          </button>
        </div>
        <div className="table-scroll">
          <table className="finance-table">
            <thead>
              <tr>
                <th>Fiscal Period</th>
                {statementData.map((d, i) => (
                  <th key={i}>{d.year || d.quarter}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rowKeys.map((key) => (
                <tr key={key}>
                  <td>{formatLabel(key)}</td>
                  {statementData.map((d, i) => (
                    <td key={i}>{d[`${key}_display`] || formatVal(d[key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="page">
      {/* HEADER */}
      <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0 }}>
            {companyName}{" "}
            <span style={{ fontWeight: 400, fontSize: "0.65em", color: "#64748b" }}>{symbol}</span>
          </h1>
          <div className="header-meta">
             <div className="meta-item">{stockInfo?.industry_profile?.exchange || 'NSE'}</div>
             <div className="meta-dot">•</div>
             <div className="meta-item">{stockInfo?.industry_profile?.sector || 'Sector'}</div>
             <div className="meta-dot">•</div>
             <div className="meta-cap">Market Cap: {ratios.market_cap}</div>
             <div className="health-badges">
                <div className="badge badge-profit">PROFITABLE</div>
                {ratios.debt_to_equity < 100 && <div className="badge badge-debt">LOW DEBT</div>}
                <div className="badge badge-stable">STABLE</div>
             </div>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14, justifyContent: 'flex-end' }}>
            <span style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>
              {currentPrice > 0 
                ? `₹${currentPrice.toLocaleString("en-IN", {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
                : "—"}
            </span>
            {priceChange != null && currentPrice > 0 && (
              <span
                className={priceChange >= 0 ? "pos" : "neg"}
                style={{ fontSize: 17, fontWeight: 600, color: priceChange >= 0 ? "#34d399" : "#f87171" }}
              >
                {priceChange >= 0 ? "+" : ""}
                {priceChange.toFixed(2)}{" "}
                ({percentChange.toFixed(2)}%)
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="layout">
        {/* SIDEBAR */}
        <div className="stock-sidenav">
          <NavLink to={`/stock/${symbol}`} className="nav-item">STOCK-PAGE</NavLink>
          <NavLink to={`/chart/${symbol}`} className="nav-item">CHART</NavLink>
          <NavLink to={`/stock/${symbol}/competitors`} className="nav-item">COMPETITOR</NavLink>
          <NavLink to={`/dividend/${symbol}`} className="nav-item">DIVIDEND</NavLink>
          <NavLink to={`/earnings/${symbol}`} className="nav-item">EARNINGS</NavLink>
          <NavLink to={`/financials/${symbol}`} className="nav-item active">FINANCIALS</NavLink>
          <NavLink to={`/news/${symbol}`} className="nav-item">HEADLINES</NavLink>
          <NavLink to={`/options/${symbol}`} className="nav-item">OPTION CHAIN</NavLink>
          <NavLink to={`/sec/${symbol}`} className="nav-item">SEC FILINGS</NavLink>
          <NavLink to={`/shortinterest/${symbol}`} className="nav-item">SHORT INTEREST</NavLink>
          <NavLink to={`/stock/${symbol}`} className="nav-item buy-item">BUY STOCK</NavLink>
        </div>

        <div className="financials-content">
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
             <h2 className="section-title">Financial Performance</h2>
             <div className="period-toggle">
                <button className={`toggle-btn ${period === 'Annual' ? 'active' : ''}`} onClick={() => setPeriod('Annual')}>Annual</button>
                <button className={`toggle-btn ${period === 'Quarterly' ? 'active' : ''}`} onClick={() => setPeriod('Quarterly')}>Quarterly</button>
             </div>
          </div>

          {/* AI SUMMARY */}
          <div className="ai-card animate-in fade-in duration-700">
             <h3 style={{ fontSize: 14, fontWeight: 800, color: '#93c5fd', textTransform: 'uppercase', marginBottom: 20, letterSpacing: '0.1em' }}>AI Financial Insight</h3>
             {ai_summary.map((text, idx) => (
               <div className="ai-item" key={idx}>
                 <div className="ai-bullet"></div>
                 <div className="ai-text">{text}</div>
               </div>
             ))}
          </div>

          {/* KPI CARDS */}
          <div className="metric-grid">
            <div className="metric-card">
               <div className="m-label">Total Revenue</div>
               <div className="m-value">{currentIncome[currentIncome.length-1]?.revenue_display || '—'}</div>
               <div className="m-trend pos"><ChevronUp size={14}/> 12.4%</div>
               <div className="m-insight">Vs previous period</div>
            </div>
            <div className="metric-card">
               <div className="m-label">Net Income</div>
               <div className="m-value">{currentIncome[currentIncome.length-1]?.net_income_display || '—'}</div>
               <div className="m-trend pos"><ChevronUp size={14}/> 8.2%</div>
               <div className="m-insight">Positive momentum</div>
            </div>
            <div className="metric-card">
               <div className="m-label">Operating Margin</div>
               <div className="m-value">{ratios.operating_margin}%</div>
               <div className="m-trend pos"><Activity size={14}/> Healthy</div>
               <div className="m-insight">Industry leading</div>
            </div>
            <div className="metric-card">
               <div className="m-label">Free Cash Flow</div>
               <div className="m-value">{currentCashflow[currentCashflow.length-1]?.free_cash_flow_display || '—'}</div>
               <div className="m-trend pos"><ShieldCheck size={14}/> Stable</div>
               <div className="m-insight">Strong liquidity</div>
            </div>
          </div>

          {/* CHARTS */}
          <div className="charts-row">
             <div className="chart-card">
                <div className="chart-header">
                   <h3 className="chart-title-sm">Revenue &amp; Net Income Trend</h3>
                   <BarChart3 size={18} color="#94a3b8" />
                </div>
                <div style={{ width: '100%', height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={period === 'Annual' ? revenue_chart : data.quarterly_income_statement}>
                       <defs>
                        <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.2}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey={period === 'Annual' ? 'year' : 'quarter'} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                      <YAxis hide />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
                        itemStyle={{ fontSize: '12px', fontWeight: 600 }}
                      />
                      <Legend iconType="circle" />
                      <Bar dataKey="revenue" name="Revenue" fill="url(#colorRev)" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="net_income" name="Net Income" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
             </div>

             <div className="chart-card">
                <div className="chart-header">
                   <h3 className="chart-title-sm">Profitability Margins</h3>
                   <PieChart size={18} color="#94a3b8" />
                </div>
                <div style={{ width: '100%', height: 300 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={income_chart}>
                      <defs>
                        <linearGradient id="colorInc" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="year" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                      <YAxis hide />
                      <Tooltip 
                         contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px' }}
                      />
                      <Area type="monotone" dataKey="operating_income" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorInc)" />
                      <Area type="monotone" dataKey="gross_profit" stroke="#3b82f6" fill="transparent" strokeDasharray="5 5" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
             </div>
          </div>

          {/* TABLES */}
          <FinanceTable title="Income Statement" statementData={currentIncome} type="income" />
          <FinanceTable title="Balance Sheet" statementData={currentBalance} type="balance" />
          <FinanceTable title="Cash Flow Statement" statementData={currentCashflow} type="cashflow" />

          {/* RATIOS GRID */}
          <h2 className="section-title" style={{ marginTop: 60 }}>Valuation &amp; Operating Ratios</h2>
          <div className="metric-grid">
             <div className="metric-card">
                <div className="m-label">P/E Ratio</div>
                <div className="m-value">{ratios.pe_ratio}</div>
                <div className="m-insight">Trailing 12 Months</div>
             </div>
             <div className="metric-card">
                <div className="m-label">Forward P/E</div>
                <div className="m-value">{ratios.forward_pe}</div>
                <div className="m-insight">Next Fiscal Year</div>
             </div>
             <div className="metric-card">
                <div className="m-label">Price to Book</div>
                <div className="m-value">{ratios.price_to_book}</div>
                <div className="m-insight">Asset Value Multiple</div>
             </div>
             <div className="metric-card">
                <div className="m-label">Price to Sales</div>
                <div className="m-value">{ratios.price_to_sales}</div>
                <div className="m-insight">Revenue Multiple</div>
             </div>
             <div className="metric-card">
                <div className="m-label">Gross Margin</div>
                <div className="m-value">{ratios.gross_margin}%</div>
                <div className="m-insight" style={{ color: ratios.gross_margin > 40 ? '#34d399' : '#f87171' }}>{ratios.gross_margin > 40 ? 'High Efficiency' : 'Standard'}</div>
             </div>
             <div className="metric-card">
                <div className="m-label">ROE</div>
                <div className="m-value">{ratios.roe}%</div>
                <div className="m-insight" style={{ color: '#34d399' }}>Excellent Returns</div>
             </div>
             <div className="metric-card">
                <div className="m-label">Current Ratio</div>
                <div className="m-value">{ratios.current_ratio}</div>
                <div className="m-insight">Liquidity position</div>
             </div>
             <div className="metric-card">
                <div className="m-label">Dividend Yield</div>
                <div className="m-value">{ratios.dividend_yield_display}</div>
                <div className="m-insight">Annual Payout</div>
             </div>
          </div>

          {/* FAQS */}
          <h2 className="section-title" style={{ marginTop: 60 }}>Financial FAQs</h2>
          <div className="faq-grid">
             {faqs.map((faq, idx) => (
               <div className="faq-item" key={idx}>
                  <div className="faq-question" onClick={() => setOpenFaq(openFaq === idx ? null : idx)}>
                     {faq.question}
                     {openFaq === idx ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  </div>
                  {openFaq === idx && (
                    <div className="faq-answer animate-in fade-in duration-300">
                      {faq.answer}
                    </div>
                  )}
               </div>
             ))}
          </div>

          <div style={{ height: 100 }}></div>
        </div>
      </div>
    </div>
  );
};

export default FinancialsPage;
