import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Sidenav from "./Sidenav";
import { fetchBseCompany, fetchBseFilings, fetchStockPrice } from "./api";
import { API_BASE_URL } from "./config";
import "./StockDetailPage.css";
import "./SecFilingsPage.css";

// Helper: returns "YYYY-MM-DD" string for a given Date object
const toISODate = (date) => date.toISOString().split("T")[0];

// Quarter badge colours
const QUARTER_COLORS = {
  Q1: { bg: "#1e3a5f", color: "#60a5fa" },
  Q2: { bg: "#1a3d2b", color: "#34d399" },
  Q3: { bg: "#3b2a1a", color: "#fb923c" },
  Q4: { bg: "#2d1a3d", color: "#c084fc" },
};

const QuarterBadge = ({ quarter }) => {
  if (!quarter) return null;
  const style = QUARTER_COLORS[quarter] || { bg: "#1e293b", color: "#94a3b8" };
  return (
    <span
      style={{
        display: "inline-block",
        marginLeft: 8,
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.05em",
        background: style.bg,
        color: style.color,
        verticalAlign: "middle",
      }}
    >
      {quarter}
    </span>
  );
};

// Use the central config so this works in both dev and production
const BACKEND = API_BASE_URL;

const SecFilingsPage = () => {
  const { symbol } = useParams();
  const [companyInfo, setCompanyInfo] = useState(null);
  const [filingsData, setFilingsData] = useState(null);
  const [priceData, setPriceData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // No inline viewer — PDFs open in a new tab

  const [category, setCategory] = useState("");
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return toISODate(d);
  });
  const [toDate, setToDate] = useState(() => toISODate(new Date()));

  const categories = [
    "Results", "Board", "Dividend", "AGM", "Insider",
    "Acquisition", "Press Release", "Analyst / Investor Meet",
    "Compliance", "General",
  ];

  // -------------------------------------------------------------------------
  // Fetch filings whenever filters change
  // -------------------------------------------------------------------------
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        const params = {
          // For "Results" category: use results_only=true (strict quarterly filter)
          // For all other categories: pass category directly for backend filtering
          category: category === "Results" ? "" : category,
          from_date: fromDate,
          to_date: toDate,
          results_only: category === "Results" ? "true" : "false",
        };

        const [company, filings, price] = await Promise.all([
          fetchBseCompany(symbol).catch(() => null),
          fetchBseFilings(symbol, params).catch(() => null),
          fetchStockPrice(symbol).catch(() => null),
        ]);

        setCompanyInfo(company);
        setFilingsData(filings);
        setPriceData(price);
      } catch (err) {
        setError(err.message || "Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [symbol, category, fromDate, toDate]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    if (name === "category") setCategory(value);
    if (name === "fromDate") setFromDate(value);
    if (name === "toDate") setToDate(value);
  };

  // -------------------------------------------------------------------------
  // PDF open — opens in a new browser tab via backend proxy
  // (avoids BSE CORS block and the broken inline iframe)
  // -------------------------------------------------------------------------
  const openPdf = (filing) => {
    if (!filing.download_url) return;
    window.open(`${BACKEND}${filing.download_url}`, "_blank", "noopener,noreferrer");
  };

  // Download: fetch the PDF blob from our proxy, then trigger save-as.
  // This avoids the browser blocking the `download` attribute on cross-origin URLs.
  const downloadPdf = async (filing) => {
    if (!filing.download_url) return;
    try {
      const proxyUrl = `${BACKEND}${filing.download_url}&disposition=attachment`;
      const res = await fetch(proxyUrl);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objUrl;
      const filename = filing.download_url.split("file=")[1] || "filing.pdf";
      link.download = filename.endsWith(".pdf") ? filename : filename + ".pdf";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objUrl);
    } catch (err) {
      // Fallback: open in new tab
      window.open(`${BACKEND}${filing.download_url}`, "_blank", "noopener,noreferrer");
    }
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (loading) return <div className="loading">Loading...</div>;
  if (error) return <div className="loading" style={{ color: "#ef4444" }}>Error: {error}</div>;

  const companyName = companyInfo?.name || symbol;
  const currentPrice = priceData?.price || 0;
  const priceChange = priceData?.change || 0;
  const percentChange = priceData?.change_percent || 0;

  return (
    <div className="page">

      {/* HEADER */}
      <div className="header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>
          {companyName}{" "}
          <span style={{ fontWeight: 400, fontSize: "0.65em", color: "#64748b" }}>{symbol}</span>
        </h1>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: "#fff" }}>
            ₹{currentPrice.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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

      {/* LAYOUT */}
      <div className="layout">
        <Sidenav symbol={symbol} />
        {/* BODY */}
        <div className="filings-content">

          {/* COMPANY INFO */}
          <div className="summary-box">
            <h3 style={{ margin: "0 0 10px 0", color: "#f8fafc" }}>Company Information</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px", fontSize: "14px" }}>
              <div><span style={{ color: "#94a3b8" }}>Sector:</span>     <b style={{ color: "#e2e8f0" }}>{companyInfo?.sector || "N/A"}</b></div>
              <div><span style={{ color: "#94a3b8" }}>Industry:</span>   <b style={{ color: "#e2e8f0" }}>{companyInfo?.industry || "N/A"}</b></div>
              <div><span style={{ color: "#94a3b8" }}>Scrip Code:</span> <b style={{ color: "#e2e8f0" }}>{companyInfo?.scrip_code || "N/A"}</b></div>
              <div><span style={{ color: "#94a3b8" }}>ISIN:</span>       <b style={{ color: "#e2e8f0" }}>{companyInfo?.isin || "N/A"}</b></div>
            </div>
          </div>

          {/* FILTERS + TABLE */}
          <div className="chart-section" style={{ padding: 24, overflow: "hidden" }}>
            <h2 className="chart-title" style={{ marginBottom: 16 }}>BSE Corporate Filings</h2>

            {/* Controls */}
            <div
              className="sc-history-controls"
              style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap", alignItems: "flex-end", paddingBottom: 16, borderBottom: "1px solid rgba(255,255,255,0.08)" }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 140 }}>
                <label style={{ fontSize: 10, fontWeight: 600, color: "#94a3b8", letterSpacing: "0.05em" }}>CATEGORY</label>
                <select
                  name="category"
                  value={category}
                  onChange={handleFilterChange}
                  style={{ padding: "9px 12px", background: "rgba(15,23,42,0.6)", border: "1px solid rgba(255,255,255,0.1)", color: "#e2e8f0", borderRadius: 6, outline: "none", fontSize: 13 }}
                >
                  <option value="">All Categories</option>
                  {categories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
                </select>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 140 }}>
                <label style={{ fontSize: 10, fontWeight: 600, color: "#94a3b8", letterSpacing: "0.05em" }}>FROM DATE</label>
                <input
                  type="date" name="fromDate" value={fromDate} max={toDate}
                  onChange={handleFilterChange}
                  style={{ padding: "8px 12px", background: "rgba(15,23,42,0.6)", border: "1px solid rgba(255,255,255,0.1)", color: "#e2e8f0", borderRadius: 6, outline: "none", fontSize: 13 }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1, minWidth: 140 }}>
                <label style={{ fontSize: 10, fontWeight: 600, color: "#94a3b8", letterSpacing: "0.05em" }}>TO DATE</label>
                <input
                  type="date" name="toDate" value={toDate} min={fromDate}
                  onChange={handleFilterChange}
                  style={{ padding: "8px 12px", background: "rgba(15,23,42,0.6)", border: "1px solid rgba(255,255,255,0.1)", color: "#e2e8f0", borderRadius: 6, outline: "none", fontSize: 13 }}
                />
              </div>
            </div>

            {/* Count */}
            {filingsData && (
              <p style={{ fontSize: 12, color: "#64748b", marginBottom: 12 }}>
                Showing {filingsData.filings?.length ?? 0} filing(s) from {fromDate} to {toDate}
                {category ? ` · ${category}` : ""}
                {category === "Results" && (
                  <span style={{ marginLeft: 6, color: "#34d399" }}>· Quarterly results only</span>
                )}
              </p>
            )}

            {/* Table */}
            <div style={{ overflowX: "auto", paddingBottom: 10 }}>
              <table className="analysis-table" style={{ width: "100%", minWidth: 900, fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "12px 16px", color: "#64748b", fontSize: 11, letterSpacing: "0.05em" }}>DATE</th>
                    <th style={{ textAlign: "left", padding: "12px 16px", color: "#64748b", fontSize: 11, letterSpacing: "0.05em" }}>CATEGORY</th>
                    <th style={{ textAlign: "left", padding: "12px 16px", color: "#64748b", fontSize: 11, letterSpacing: "0.05em" }}>DESCRIPTION</th>
                    <th style={{ textAlign: "center", padding: "12px 16px", color: "#64748b", fontSize: 11, letterSpacing: "0.05em" }}>PDF</th>
                  </tr>
                </thead>
                <tbody>
                  {(!filingsData || !filingsData.filings || filingsData.filings.length === 0) ? (
                    <tr>
                      <td colSpan="4" style={{ textAlign: "center", padding: 24, color: "#64748b" }}>
                        No filings found
                      </td>
                    </tr>
                  ) : filingsData.filings.map((filing, i) => (
                    <tr
                      key={i}
                      style={{
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                        background: "transparent",
                      }}
                    >
                      <td style={{ fontWeight: 600, color: "#f8fafc", padding: "14px 16px", whiteSpace: "nowrap" }}>
                        {filing.date ? filing.date.substring(0, 10) : "N/A"}
                      </td>
                      <td style={{ fontWeight: 500, color: "#94a3b8", padding: "14px 16px" }}>
                        {filing.category}
                      </td>
                      <td style={{ color: "#e2e8f0", padding: "14px 16px" }}>
                        {filing.description}
                        {/* Quarter badge — shows Q1/Q2/Q3/Q4 next to description */}
                        <QuarterBadge quarter={filing.quarter} />
                      </td>
                      <td style={{ textAlign: "center", padding: "14px 16px" }}>
                        {filing.download_url ? (
                          <div style={{ display: "flex", gap: 8, justifyContent: "center", alignItems: "center" }}>
                            {/* View — opens PDF in new tab via backend proxy */}
                            <button
                              onClick={() => openPdf(filing)}
                              style={{
                                background: "none", border: "none", cursor: "pointer",
                                color: "#60a5fa", fontSize: 13, padding: 0, textDecoration: "underline",
                              }}
                            >
                              View
                            </button>
                            {/* Download — fetches blob from proxy to bypass cross-origin download block */}
                            <button
                              onClick={() => downloadPdf(filing)}
                              style={{
                                background: "none", border: "none", cursor: "pointer",
                                color: "#94a3b8", fontSize: 15, padding: 0,
                              }}
                              title="Download PDF"
                            >
                              ↓
                            </button>
                          </div>
                        ) : (
                          <span style={{ color: "#64748b" }}>N/A</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>



        </div>
      </div>
    </div>
  );
};

export default SecFilingsPage;