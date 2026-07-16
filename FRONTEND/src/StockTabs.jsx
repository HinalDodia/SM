import React, { useEffect, useState } from "react";
import {
  fetchDividendSummary,
  fetchEarnings,
  fetchFinancials,
  fetchOptions,
  fetchSecFilings,
  fetchShortInterest,
} from "./api";

import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  CartesianGrid, ResponsiveContainer,
} from "recharts";
import OptionsChain from "./OptionsChain";

// ─── Shared helpers ───────────────────────────────────────────────────────────

function LoadingCard({ label }) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <p style={{ color: "#9ca3af", marginTop: 10 }}>Loading…</p>
    </div>
  );
}

function ErrorCard({ label, message }) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <p style={{ color: "#ef4444", marginTop: 10 }}>{message || "Failed to load data."}</p>
    </div>
  );
}

function EmptyCard({ label, message }) {
  return (
    <div className="card">
      <h3>{label}</h3>
      <p style={{ color: "#9ca3af", marginTop: 10 }}>{message || "No data available."}</p>
    </div>
  );
}

// ─── useTabData hook ──────────────────────────────────────────────────────────

function useTabData(fetcher, symbol) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    setLoading(true);

    fetcher(symbol)
      .then((res) => { if (!cancelled) { setData(res); setLoading(false); } })
      .catch((err) => { if (!cancelled) { setError(err.message || "Error"); setLoading(false); } });

    return () => { cancelled = true; };
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error };
}

// ─── DividendView ─────────────────────────────────────────────────────────────

export const DividendView = ({ symbol }) => {
  const { data, loading, error } = useTabData(fetchDividendSummary, symbol);

  if (loading) return <LoadingCard label="Dividend Summary" />;
  if (error)   return <ErrorCard   label="Dividend Summary" message={error} />;
  if (!data || data.message)
    return <EmptyCard label="Dividend Summary" message="No dividend data available for this stock." />;

  const fmt = (v, pct = false) =>
    v == null ? "N/A" : pct ? (v * 100).toFixed(2) + "%" : v;

  return (
    <>
      <div className="card">
        <h3>Dividend Summary</h3>
        <div className="row"><span>Dividend Yield</span><b>{fmt(data.summary?.dividend_yield, true)}</b></div>
        <div className="row"><span>Annual Dividend</span><b>₹{fmt(data.summary?.annual_dividend)}</b></div>
        <div className="row"><span>Payout Ratio</span><b>{fmt(data.summary?.payout_ratio, true)}</b></div>
        <div className="row"><span>Next Payment</span><b>{data.summary?.next_dividend_payment || "N/A"}</b></div>
        <div className="row"><span>5-Year Growth</span><b>{fmt(data.summary?.five_year_growth, true)}</b></div>
        <div className="row">
          <span>Increase Track Record</span>
          <b>{data.summary?.dividend_increase_track_record ?? "N/A"} yrs</b>
        </div>
      </div>

      {data.dividend_history?.length > 0 && (
        <div className="card full-width">
          <h3>Dividend History</h3>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data.dividend_history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`₹${v.toFixed(4)}`, "Dividend"]} />
                <Bar dataKey="dividend" fill="#4CAF50" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </>
  );
};

// ─── EarningsView ─────────────────────────────────────────────────────────────

export const EarningsView = ({ symbol }) => {
  const { data, loading, error } = useTabData(fetchEarnings, symbol);

  if (loading) return <LoadingCard label="Earnings" />;
  if (error)   return <ErrorCard   label="Earnings" message={error} />;
  if (!data)   return <EmptyCard   label="Earnings" />;

  return (
    <>
      <div className="card">
        <h3>Earnings Summary</h3>
        <div className="row"><span>Latest Earnings Date</span><b>{data.summary?.latest_earnings_date || "N/A"}</b></div>
        <div className="row"><span>Consensus EPS</span><b>{data.summary?.consensus_eps ?? "N/A"}</b></div>
        <div className="row"><span>Actual EPS</span><b>{data.summary?.actual_eps ?? "N/A"}</b></div>
        <div className="row">
          <span>Actual Revenue</span>
          <b>{data.summary?.actual_revenue ? "₹" + data.summary.actual_revenue.toLocaleString() : "N/A"}</b>
        </div>
      </div>

      {data.revenue_chart?.length > 0 && (
        <div className="card full-width">
          <h3>Revenue History (Quarterly)</h3>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data.revenue_chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => "₹" + (v / 1e9).toFixed(1) + "B"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => ["₹" + (v / 1e9).toFixed(2) + "B", "Revenue"]} />
                <Bar dataKey="revenue" fill="#3f51b5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {data.eps_estimate_vs_actual_chart?.length > 0 && (
        <div className="card full-width">
          <h3>EPS: Estimate vs Actual</h3>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data.eps_estimate_vs_actual_chart}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="estimate_eps" name="Estimate EPS" fill="#8884d8" radius={[4, 4, 0, 0]} />
                <Bar dataKey="actual_eps"   name="Actual EPS"   fill="#82ca9d" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {data.earnings_history_chart?.length > 0 && (
        <div className="card full-width">
          <h3>Earnings History</h3>
          <div className="chart-box" style={{ overflowX: "auto" }}>
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Date</th><th>Estimate EPS</th><th>Actual EPS</th><th>Surprise %</th>
                </tr>
              </thead>
              <tbody>
                {data.earnings_history_chart.map((r, i) => (
                  <tr key={i}>
                    <td>{r.date}</td>
                    <td>{r.estimate ?? "N/A"}</td>
                    <td>{r.actual ?? "N/A"}</td>
                    <td style={{ color: r.surprise_percent > 0 ? "#4CAF50" : "#ef4444" }}>
                      {r.surprise_percent != null ? r.surprise_percent.toFixed(2) + "%" : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
};

// ─── FinancialsView ──────────────────────────────────────────────────────────

export const FinancialsView = ({ symbol }) => {
  const { data, loading, error } = useTabData(fetchFinancials, symbol);

  if (loading) return <LoadingCard label="Financials" />;
  if (error)   return <ErrorCard   label="Financials" message={error} />;
  if (!data)   return <EmptyCard   label="Financials" />;

  const { ratios = {}, income_statement = [], cashflow_statement = [], balance_sheet = [] } = data;
  const fmt = (v, pct = false) =>
    v == null ? "N/A" : pct ? (v * 100).toFixed(2) + "%" : v;

  return (
    <>
      <div className="card">
        <h3>Key Ratios</h3>
        <div className="row"><span>Gross Margin</span><b>{fmt(ratios.gross_margin, true)}</b></div>
        <div className="row"><span>Operating Margin</span><b>{fmt(ratios.operating_margin, true)}</b></div>
        <div className="row"><span>Profit Margin</span><b>{fmt(ratios.profit_margin, true)}</b></div>
        <div className="row"><span>ROE</span><b>{fmt(ratios.roe, true)}</b></div>
        <div className="row"><span>ROA</span><b>{fmt(ratios.roa, true)}</b></div>
        <div className="row"><span>Debt to Equity</span><b>{fmt(ratios.debt_to_equity)}</b></div>
        <div className="row"><span>Current Ratio</span><b>{fmt(ratios.current_ratio)}</b></div>
      </div>

      {income_statement.length > 0 && (
        <div className="card full-width">
          <h3>Income Statement</h3>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={income_statement}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => "₹" + (v / 1e9).toFixed(1) + "B"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => "₹" + (v / 1e9).toFixed(2) + "B"} />
                <Legend />
                <Line dataKey="revenue"    name="Revenue"    stroke="#8884d8" dot={false} />
                <Line dataKey="gross_profit" name="Gross Profit" stroke="#fbbf24" dot={false} />
                <Line dataKey="net_income" name="Net Income" stroke="#82ca9d" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {cashflow_statement.length > 0 && (
        <div className="card full-width">
          <h3>Cash Flow Statement</h3>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={cashflow_statement}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => "₹" + (v / 1e9).toFixed(1) + "B"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => "₹" + (v / 1e9).toFixed(2) + "B"} />
                <Legend />
                <Bar dataKey="operating_cashflow"  name="Operating CF"  fill="#4CAF50" radius={[4,4,0,0]} />
                <Bar dataKey="free_cashflow"        name="Free CF"       fill="#2196F3" radius={[4,4,0,0]} />
                <Bar dataKey="capital_expenditure"  name="CapEx"         fill="#ef4444" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {balance_sheet.length > 0 && (
        <div className="card full-width">
          <h3>Balance Sheet</h3>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={balance_sheet}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => "₹" + (v / 1e9).toFixed(1) + "B"} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => "₹" + (v / 1e9).toFixed(2) + "B"} />
                <Legend />
                <Bar dataKey="total_assets"      name="Total Assets"      fill="#8884d8" radius={[4,4,0,0]} />
                <Bar dataKey="total_liabilities" name="Total Liabilities" fill="#ef4444" radius={[4,4,0,0]} />
                <Bar dataKey="total_equity"      name="Equity"            fill="#82ca9d" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </>
  );
};

// ─── OptionsView ──────────────────────────────────────────────────────────────

export const OptionsView = ({ symbol }) => {
  return (
    <div className="full-width">
      <OptionsChain symbol={symbol} />
    </div>
  );
};

// ─── SecFilingsView ───────────────────────────────────────────────────────────

export const SecFilingsView = ({ symbol }) => {
  const { data, loading, error } = useTabData(fetchSecFilings, symbol);

  if (loading) return <LoadingCard label="SEC Filings" />;
  if (error)   return <ErrorCard   label="SEC Filings" message={error} />;
  if (!data || data.error || !data.filings?.length)
    return <EmptyCard label="SEC Filings" message={data?.error || "No SEC filings found."} />;

  return (
    <div className="card full-width">
      <h3>Recent SEC Filings</h3>
      <div style={{ overflowX: "auto" }}>
        <table className="analysis-table">
          <thead>
            <tr><th>Date</th><th>Type</th><th>Title</th><th>Link</th></tr>
          </thead>
          <tbody>
            {data.filings.map((f, i) => (
              <tr key={i}>
                <td>{f.date ? String(f.date).substring(0, 10) : "N/A"}</td>
                <td><strong>{f.type}</strong></td>
                <td style={{ textAlign: "left" }}>{f.title || "—"}</td>
                <td>
                  {f.edgar_url
                    ? <a href={f.edgar_url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa" }}>View ↗</a>
                    : "—"
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ─── ShortInterestView ────────────────────────────────────────────────────────

export const ShortInterestView = ({ symbol }) => {
  const { data, loading, error } = useTabData(fetchShortInterest, symbol);

  if (loading) return <LoadingCard label="Short Interest" />;
  if (error)   return <ErrorCard   label="Short Interest" message={error} />;
  if (!data)   return <EmptyCard   label="Short Interest" />;

  const fmtNum = (v) => (v != null ? v.toLocaleString() : "N/A");
  const fmtPct = (v) => (v != null ? (v * 100).toFixed(2) + "%" : "N/A");

  return (
    <div className="card">
      <h3>Short Interest</h3>
      <div className="row"><span>Shares Outstanding</span><b>{fmtNum(data.shares_outstanding)}</b></div>
      <div className="row"><span>Float Shares</span><b>{fmtNum(data.float_shares)}</b></div>
      <div className="row"><span>Short Interest</span><b>{fmtNum(data.short_interest)}</b></div>
      <div className="row"><span>Short Ratio (Days to Cover)</span><b>{data.short_ratio_days_to_cover ?? "N/A"}</b></div>
      <div className="row"><span>Short % of Float</span><b>{fmtPct(data.short_percent_of_float)}</b></div>
    </div>
  );
};
