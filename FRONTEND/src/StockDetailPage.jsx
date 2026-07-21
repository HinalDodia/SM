import React, { useEffect, useState, useContext, useMemo } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import Sidenav from "./Sidenav";
import { fetchStockPage } from "./api";
import { DividendView, EarningsView, FinancialsView, OptionsView, SecFilingsView } from "./StockTabs";
import ShortInterest from "./ShortInterest";
import HeadlinesView from "./Headlines/HeadlinesView";
import "./StockDetailPage.css";
import "./Watchlist.css";
import { UserContext } from "./UserContext";
import RecommendationModal from "./RecommendationModal";
import axios from "axios";
import { API_URL } from "./config";


const StockDetailPage = ({ tab }) => {

  const { symbol } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useContext(UserContext) || {};
  const uid = user?.userid || null;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showFullDesc, setShowFullDesc] = useState(false);

  const [showBuyModal, setShowBuyModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [showCelebrate, setShowCelebrate] = useState(false);
  const [showErrorModal, setShowErrorModal] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [quantity, setQuantity] = useState("");
  const [currentPrice, setCurrentPrice] = useState(0);
  const [purchasedStock, setPurchasedStock] = useState(null);

  const authConfig = useMemo(() => {
    const token = localStorage.getItem("id_token");
    return {
      headers: {
        "X-User-Id": String(uid),
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      }
    };
  }, [uid]);

  const handleBuyClick = async (e) => {
    e.preventDefault();
    if (!uid) {
      navigate("/Log", { state: { from: location }, replace: true });
      return;
    }

    // Try to get price
    try {
      const res = await axios.get(`${API_URL}/get-price/${symbol}`, authConfig);
      if (res.data && res.data.price) setCurrentPrice(Number(res.data.price));
      else setCurrentPrice(0);
    } catch (err) {
      console.error("Error fetching price:", err);
      setCurrentPrice(data?.key_stats?.price || 0); // fallback if available
    }

    setQuantity("");
    setShowBuyModal(true);
  };

  const executePurchase = async () => {
    if (!quantity) return;
    const numQuantity = Number(quantity);
    if (isNaN(numQuantity) || numQuantity <= 0) {
      setErrorMessage("Enter a valid number of shares.");
      setShowErrorModal(true);
      return;
    }
    if (!uid) {
      navigate("/Log", { state: { from: location }, replace: true });
      return;
    }

    try {
      const costPrice = currentPrice || 0;
      await axios.post(
        `${API_URL}/buy`,
        {
          userid: uid,
          stockname: symbol,
          companyname: data?.company_overview?.name || symbol,
          qty: numQuantity,
          price: costPrice,
        },
        authConfig
      );

      setPurchasedStock({
        symbol: symbol,
        name: data?.company_overview?.name || symbol,
        quantity: numQuantity,
        totalCost: costPrice * numQuantity,
      });

      setShowBuyModal(false);
      setShowSuccessModal(true);
    } catch (err) {
      console.error("Purchase error:", err);
      setErrorMessage(err?.response?.data?.error || err.message || "Purchase failed");
      setShowErrorModal(true);
    }
  };

  useEffect(() => {
    let cancelled = false;
    setData(null); setError(null); setLoading(true);

    fetchStockPage(symbol)
      .then(res => {
        if (!cancelled) {
          if (res.error) setError(res.error);
          else setData(res);
          setLoading(false);
        }
      })
      .catch(err => { if (!cancelled) { setError(err.message); setLoading(false); } });

    return () => { cancelled = true; };
  }, [symbol]);

  if (loading) return <div className="loading">Loading…</div>;
  if (error) return <div className="loading" style={{ color: "#ef4444" }}>Error: {error}</div>;
  if (!data) return <div className="loading">No Data</div>;

  // Safe date formatter for epoch strings or integers
  const formatEpoch = (val) => {
    if (!val || val === "N/A" || val === "None") return "N/A";
    if (typeof val === "string" && val.includes("-")) return val.substring(0, 10);
    let n = Number(val);
    if (!isNaN(n) && n > 1e8) {
      if (n < 1e11) n *= 1000;
      return new Date(n).toISOString().substring(0, 10);
    }
    return String(val);
  };



  const row = (label, val, suffix = "") => {
    let v = val;

    if (v === null || v === undefined || v === "") {
      v = "N/A";
      suffix = ""; // Don't show % or other suffixes if N/A
    } else if (Array.isArray(v)) {
      // If it's an array like today_range, check if elements are null
      if (v[0] === null || v[1] === null) {
        v = "N/A";
      } else {
        v = `${v[0].toLocaleString()} - ${v[1].toLocaleString()}`;
      }
    } else if (typeof v === "number") {
      v = v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    return (
      <div className="row" key={label}>
        <span>{label}</span>
        <b>{v}{suffix}</b>
      </div>
    );
  };


  return (

    <div className="page">

      {/* HEADER */}
      <div className="header">
        <h1>
          {data.company_overview?.name}
          <span>{data.company_overview?.symbol}</span>
        </h1>
      </div>


      {/* MAIN LAYOUT */}
      <div className="layout">

        <Sidenav symbol={symbol} onBuyClick={handleBuyClick} />
        {/* ⭐ CLOSED SIDEBAR */}



        {/* RIGHT CONTENT */}
        <div className="grid">

          {!tab && (
            <>

              {/* HIGHLIGHT METRICS */}
              <div className="highlight-row">
                <div className="metric-box">
                  <div className="metric-label">Market Cap</div>
                  <div className="metric-value">
                    {data.key_stats?.market_cap ? "₹" + (data.key_stats.market_cap / 1e9 > 1 ? (data.key_stats.market_cap / 1e9).toFixed(2) + "B" : (data.key_stats.market_cap / 1e6).toFixed(2) + "M") : "N/A"}
                  </div>
                </div>
                <div className="metric-box">
                  <div className="metric-label">P/E Ratio</div>
                  <div className="metric-value">{data.key_stats?.pe_ratio ? data.key_stats.pe_ratio.toFixed(2) : "N/A"}</div>
                </div>
                <div className="metric-box">
                  <div className="metric-label">Target Price</div>
                  <div className="metric-value">{data.key_stats?.price_target ? "₹" + data.key_stats.price_target : "N/A"}</div>
                </div>
                <div className="metric-box">
                  <div className="metric-label">Analyst Rating</div>
                  <div className="metric-value" style={{ textTransform: 'capitalize', color: data.key_stats?.consensus_rating?.includes('buy') ? '#34d399' : (data.key_stats?.consensus_rating?.includes('sell') ? '#f87171' : '#facc15') }}>
                    {data.key_stats?.consensus_rating ? data.key_stats.consensus_rating.replace("_", " ") : "N/A"}
                  </div>
                </div>
              </div>

              {/* 1. COMPANY OVERVIEW */}
              <div className="card overview">
                <h3>Company Overview</h3>
                <p>
                  {data.company_overview?.description
                    ? (showFullDesc ? data.company_overview.description : data.company_overview.description.slice(0, 250) + "...")
                    : "No description available."}
                  {data.company_overview?.description && data.company_overview.description.length > 250 && (
                    <span
                      style={{ color: "#60a5fa", cursor: "pointer", marginLeft: "10px", fontWeight: "bold" }}
                      onClick={() => setShowFullDesc(!showFullDesc)}
                    >
                      {showFullDesc ? "View Less" : "View More"}
                    </span>
                  )}
                </p>
              </div>

              {/* 2. KEY STATS */}
              <div className="card">
                <h3>Key Stats</h3>
                {row("Today's Range:", data.key_stats?.today_range)}
                {row("50-Day Range:", data.key_stats?.["50day_range"])}
                {row("52-Week Range:", data.key_stats?.["52week_range"])}
                {row("Volume:", data.key_stats?.volume)}
                {row("Average Volume:", data.key_stats?.avg_volume)}
                {row("Market Capitalization:", data.key_stats?.market_cap)}
                {row("P/E Ratio:", data.key_stats?.pe_ratio)}
                {row("Dividend Yield:", typeof data.key_stats?.dividend_yield === "number" ? (data.key_stats.dividend_yield * 100).toFixed(2) : data.key_stats?.dividend_yield, "%")}
                {row("Price Target:", data.key_stats?.price_target)}
                {row("Consensus Rating:", data.key_stats?.consensus_rating ? String(data.key_stats.consensus_rating).replace("_", " ") : null)}
              </div>

              {/* 3. COMPANY CALENDAR */}
              <div className="card">
                <h3>Company Calendar</h3>
                {row("Latest Dividend Amount:", data.company_calendar?.div_amt_1 ? `₹${data.company_calendar.div_amt_1}` : "N/A")}
                {row(data.company_calendar?.div_amt_1 ? `Record Date for ₹${data.company_calendar.div_amt_1} Dividend:` : "Record Date for Latest Dividend:", formatEpoch(data.company_calendar?.record_date_1))}
                {row(data.company_calendar?.div_amt_1 ? `Ex-Dividend for ₹${data.company_calendar.div_amt_1} Dividend:` : "Ex-Dividend for Latest Dividend:", formatEpoch(data.company_calendar?.ex_dividend))}
                {row("Dividend Payable:", formatEpoch(data.company_calendar?.dividend_payable))}
                {row("Last Earnings:", formatEpoch(data.company_calendar?.last_earnings))}
                {row("Today:", data.company_calendar?.today)}
                {row("Previous Dividend Amount:", data.company_calendar?.div_amt_2 ? `₹${data.company_calendar.div_amt_2}` : "N/A")}
                {row(data.company_calendar?.div_amt_2 ? `Record Date for ₹${data.company_calendar.div_amt_2} Dividend:` : "Record Date for Previous Dividend:", formatEpoch(data.company_calendar?.record_date_2))}
                {row(data.company_calendar?.div_amt_2 ? `Ex-Dividend for ₹${data.company_calendar.div_amt_2} Dividend:` : "Ex-Dividend for Previous Dividend:", formatEpoch(data.company_calendar?.ex_dividend_2))}
                {row("Previous Dividend Payable:", formatEpoch(data.company_calendar?.dividend_payable_2))}
                {row("Fiscal Year End:", formatEpoch(data.company_calendar?.fiscal_year_end))}
              </div>

              {/* 4. INDUSTRY, SECTOR AND SYMBOL */}
              <div className="card">
                <h3>Industry, Sector and Symbol</h3>
                {row("Stock Exchange:", data.industry_profile?.exchange)}
                {row("Sector:", data.industry_profile?.sector)}
                {row("Industry:", data.industry_profile?.industry)}
                {row("Sub-Industry:", data.industry_profile?.sub_industry)}
                {row("Current Symbol:", data.industry_profile?.symbol)}
                {row("Previous Symbol:", data.industry_profile?.previous_symbol)}
                {row("CIK:", data.industry_profile?.cik)}
                {row("Web:", data.industry_profile?.website)}
                {row("Phone:", data.industry_profile?.phone)}
                {row("Fax:", data.industry_profile?.fax)}
                {row("Employees:", data.industry_profile?.employees)}
                {row("Year Founded:", data.industry_profile?.year_founded)}
              </div>

              {/* 5. PRICE TARGET AND RATING */}
              <div className="card">
                <h3>Price Target and Rating</h3>
                {row(`Avg Price Target for ${symbol}:`, data.price_target_rating?.avg_target)}
                {row("High Price Target:", data.price_target_rating?.high_target)}
                {row("Low Price Target:", data.price_target_rating?.low_target)}
                {row("Potential Upside/Downside:", data.price_target_rating?.potential_upside_percent, "%")}
                {row("Consensus Rating:", data.price_target_rating?.consensus_rating ? String(data.price_target_rating.consensus_rating).replace("_", " ") : null)}
                {row("Rating Score (0-4):", data.price_target_rating?.rating_score)}
                {row("Research Coverage:", data.price_target_rating?.research_coverage)}
              </div>

              {/* 6. PROFITABILITY */}
              <div className="card">
                <h3>Profitability</h3>
                {row("EPS (Trailing Twelve Months):", data.profitability?.eps)}
                {row("Trailing P/E Ratio:", data.profitability?.trailing_pe)}
                {row("Forward P/E:", data.profitability?.forward_pe)}
                {row("PEG Ratio:", data.profitability?.peg_ratio)}
                {row("Net Income:", data.profitability?.net_income)}
                {row("Net Margins:", data.profitability?.net_margin)}
                {row("Pretax Margins:", data.profitability?.pretax_margin)}
                {row("Return on Equity:", data.profitability?.roe)}
                {row("Return on Assets:", data.profitability?.roa)}
              </div>

              {/* 7. DEBT */}
              <div className="card">
                <h3>Debt</h3>
                {row("Debt-to-Equity Ratio:", data.debt?.debt_equity)}
                {row("Current Ratio:", data.debt?.current_ratio)}
                {row("Quick Ratio:", data.debt?.quick_ratio)}
              </div>

              {/* 8. SALES AND BOOK VALUE */}
              <div className="card">
                <h3>Sales and Book Value</h3>
                {row("Annual Sales:", data.sales_book?.annual_sales)}
                {row("Price/Sales:", data.sales_book?.price_sales)}
                {row("Cash Flow:", data.sales_book?.cashflow)}
                {row("Price/Cash Flow:", data.sales_book?.price_cashflow)}
                {row("Book Value:", data.sales_book?.book_value)}
                {row("Price/Book:", data.sales_book?.price_book)}
              </div>

              {/* 9. MISCELLANEOUS */}
              <div className="card">
                <h3>Miscellaneous</h3>
                {row("Outstanding Shares:", data.misc?.shares_outstanding)}
                {row("Free Float:", data.misc?.float_shares)}
                {row("MarketCap:", data.misc?.marketcap)}
                {row("Optionable:", data.misc?.optionable ? "Yes" : "No")}
                {row("Beta:", data.misc?.beta)}
              </div>
            </>
          )}

          {tab === "dividend" && <DividendView symbol={symbol} />}
          {tab === "earnings" && <EarningsView symbol={symbol} />}
          {tab === "financials" && <FinancialsView symbol={symbol} />}
          {tab === "news" && <div className="full-width"><HeadlinesView symbol={symbol} /></div>}
          {tab === "ownership" && <div className="card full-width"><h3>Ownership</h3><p style={{ color: "#94a3b8" }}>Institutional and insider ownership data for {symbol}.</p></div>}
          {tab === "options" && <OptionsView symbol={symbol} />}
          {tab === "sec" && <SecFilingsView symbol={symbol} />}
          {tab === "shortinterest" && <ShortInterest symbol={symbol} />}

        </div> {/* GRID */}

      </div> {/* LAYOUT */}

      {/* Buy Modal */}
      {showBuyModal && (
        <div className="wl-backdrop" role="dialog" aria-modal="true" style={{ zIndex: 10000 }}>
          <div className="wl-modal">
            <div className="wl-modal-head">
              <div className="tick blue" aria-hidden />
              <div className="wl-modal-title">
                Buy <strong>{symbol}</strong>
              </div>
            </div>

            <div className="wl-modal-sub">{data?.company_overview?.name || symbol}</div>
            <div className="wl-modal-price">
              Price per share: <strong>₹{currentPrice}</strong>
            </div>

            <div className="wl-input">
              <input
                type="number"
                min="1"
                step="1"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="Number of shares"
              />
              <span className="wl-focusring" aria-hidden />
            </div>

            {quantity && (
              <div className="wl-total">
                Total:{" "}
                <strong>
                  ₹{(currentPrice * Number(quantity)).toFixed(2)}
                </strong>
              </div>
            )}

            <div className="wl-modal-actions">
              <button className="btn btn-confirm" onClick={executePurchase}>
                Buy
              </button>
              <button className="btn btn-cancel" onClick={() => setShowBuyModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success Modal */}
      {showSuccessModal && purchasedStock && (
        <div className="wl-backdrop" role="dialog" aria-modal="true" style={{ zIndex: 10000 }}>
          <div className="wl-modal success">
            <div className="wl-modal-head">
              <div className="tick green" aria-hidden />
              <div className="wl-modal-title">Purchase Successful</div>
            </div>

            <div className="wl-modal-sub">
              You bought <strong>{purchasedStock.quantity}</strong> shares of{" "}
              <strong>{purchasedStock.symbol}</strong>
            </div>
            <div className="wl-total">
              Total Spent:{" "}
              <strong>₹{purchasedStock.totalCost.toFixed(2)}</strong>
            </div>

            <div className="wl-modal-actions">
              <button
                className="btn btn-confirm"
                onClick={() => {
                  setShowSuccessModal(false);
                  setShowCelebrate(true);
                }}
              >
                Awesome
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Celebration / Recommendation Modal */}
      {showCelebrate && purchasedStock && (
        <RecommendationModal
          userId={uid}
          stock={purchasedStock}
          type="buy"
          onClose={() => setShowCelebrate(false)}
        />
      )}

      {/* Error Modal */}
      {showErrorModal && (
        <div className="wl-backdrop" role="dialog" aria-modal="true" style={{ zIndex: 10000 }}>
          <div className="wl-modal error">
            <div className="wl-modal-head">
              <div className="tick red" aria-hidden />
              <div className="wl-modal-title">Error</div>
            </div>
            <div className="wl-modal-sub">{errorMessage}</div>
            <div className="wl-modal-actions">
              <button
                className="btn btn-cancel"
                onClick={() => setShowErrorModal(false)}
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}

    </div> /* PAGE */

  );

};

export default StockDetailPage;