"""
/dividend-summary/<symbol>

Returns comprehensive dividend data: history, yield over time, quarterly
breakdown, payout ratio analysis, peer comparison, and FAQ.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from flask import Blueprint, jsonify
from flask_cors import cross_origin

from ..routes_utils import get_yf_symbol

import os

stock_dividend_bp = Blueprint("stock_dividend_bp", __name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _normalize_dividend_yield(raw_yield):
    """yfinance sometimes returns 0.0257 and sometimes 2.57 — normalize to decimal."""
    if raw_yield and raw_yield > 1:
        return raw_yield / 100.0
    return raw_yield


def _compute_5yr_cagr(divs_clean):
    """Return 5-year dividend CAGR as a percentage, or None."""
    try:
        cutoff = divs_clean.index[-1] - pd.DateOffset(years=5)
        last5  = divs_clean[divs_clean.index >= cutoff]
        yearly = last5.groupby(last5.index.year).sum()
        if len(yearly) >= 2:
            first_val = float(yearly.iloc[0])
            last_val  = float(yearly.iloc[-1])
            n_years   = len(yearly) - 1
            if first_val > 0:
                return round(((last_val / first_val) ** (1 / n_years) - 1) * 100, 2)
    except Exception:
        pass
    return None


def _count_increase_years(divs_clean):
    """Count consecutive years of dividend increases."""
    increase_years = 0
    try:
        yearly_all = divs_clean.groupby(divs_clean.index.year).sum()
        prev = None
        for val in yearly_all:
            if prev is not None and val > prev:
                increase_years += 1
            prev = val
    except Exception:
        pass
    return increase_years


def _build_dividend_history(divs_clean):
    """Build a raw list of {date, dividend, year, quarter} for the last 50 payments."""
    history = []
    for dt, val in divs_clean.tail(50).items():
        history.append({
            "date":     str(dt.date()),
            "dividend": round(float(val), 4),
            "year":     dt.year,
            "quarter":  dt.quarter,
        })
    return history


def _build_quarterly_breakdown(dividend_history_full):
    """Group payments by year and quarter."""
    q_map = {}
    for entry in dividend_history_full:
        key = (entry["year"], entry["quarter"])
        q_map[key] = q_map.get(key, 0) + entry["dividend"]

    return [
        {"year": k[0], "quarter": k[1], "dividend": round(v, 4)}
        for k, v in sorted(q_map.items())
    ]


def _build_yield_over_time(ticker, divs_clean):
    """Compute rolling 12-month dividend yield over monthly price history."""
    result = []
    try:
        hist_prices = ticker.history(period="10y", interval="1mo")
        if hist_prices.empty:
            return result

        if hist_prices.index.tz:
            hist_prices.index = hist_prices.index.tz_localize(None)

        monthly_divs  = divs_clean.resample("ME").sum()
        rolling_annual = monthly_divs.rolling(12, min_periods=1).sum()

        for dt, price_row in hist_prices.iterrows():
            close   = price_row["Close"]
            ann_div = float(rolling_annual.get(dt, rolling_annual.asof(dt) if not rolling_annual.empty else 0) or 0)
            yld     = round((ann_div / float(close)) * 100, 4) if close and float(close) > 0 else None
            result.append({"date": dt.strftime("%Y-%m-%d"), "yield": yld})
    except Exception:
        pass
    return result


def _build_dividend_table(divs_clean, ticker):
    """Build per-payment rows with yield, change, and approximate dates."""
    table = []
    try:
        hist_full = ticker.history(period="max", interval="1d")
        if hist_full.index.tz is not None:
            hist_full.index = hist_full.index.tz_localize(None)

        prev_div = None
        for dt, val in divs_clean.items():
            fval = round(float(val), 4)

            change = None
            if prev_div is not None and prev_div != 0:
                change = round(((fval - prev_div) / prev_div) * 100, 2)

            row_yield = None
            try:
                closest_price = hist_full.asof(dt)["Close"]
                if closest_price and float(closest_price) > 0:
                    row_yield = round((fval * 4 / float(closest_price)) * 100, 2)
            except Exception:
                pass

            table.append({
                "announced_date":   (dt - timedelta(weeks=4)).strftime("%Y-%m-%d"),
                "period":           f"Q{dt.quarter} {dt.year}",
                "payment":          fval,
                "payment_change":   change,
                "yield":            row_yield,
                "ex_dividend_date": str(dt.date()),
                "record_date":      (dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                "payable_date":     (dt + timedelta(days=15)).strftime("%Y-%m-%d"),
            })

            prev_div = fval
    except Exception:
        pass
    return table


def _build_payout_ratio_breakdown(payout_ratio, annual_dividend, forward_eps, free_cashflow, info):
    """Compute trailing, this-year, next-year, and cashflow payout ratios."""
    payout_this_year = None
    try:
        if annual_dividend and forward_eps and forward_eps > 0:
            payout_this_year = round((annual_dividend / forward_eps) * 100, 2)
    except Exception:
        pass

    payout_cashflow = None
    try:
        shares = info.get("sharesOutstanding")
        if free_cashflow and shares and shares > 0 and annual_dividend:
            fcf_per_share   = free_cashflow / shares
            payout_cashflow = round((annual_dividend / fcf_per_share) * 100, 2)
    except Exception:
        pass

    return {
        "trailing_12_months": payout_ratio,
        "this_year_estimate": payout_this_year,
        "next_year_estimate": payout_this_year,  # best available estimate
        "cashflow":           payout_cashflow,
    }


def _fetch_peer_metrics(symbol, info, stock_df):
    """
    Identify same-sector peers from the CSV stock list, then fetch one
    named peer and compute industry/market average dividend metrics.
    Returns a comparison dict.
    """
    comparison = {}
    try:
        _df = stock_df.copy()
        _df.columns = [c.strip().lower() for c in _df.columns]
        try:
            _df = _df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        except AttributeError:
            _df = _df.map(lambda x: x.strip() if isinstance(x, str) else x)

        current_sector = (info.get("sector") or "").strip().lower()

        def sectors_match(csv_sector):
            csv_s = csv_sector.strip().lower()
            if not csv_s or not current_sector:
                return False
            if csv_s == current_sector:
                return True
            if current_sector in csv_s or csv_s in current_sector:
                return True
            return bool(set(csv_s.split()) & set(current_sector.split()))

        same_sector_mask = _df["sector"].apply(sectors_match)
        current_sym_mask = _df["symbol"].str.upper() != symbol.upper()
        same_sector_df   = _df[same_sector_mask & current_sym_mask]
        peer_symbols     = same_sector_df["symbol"].dropna().tolist()[:8]

        if not peer_symbols:
            peer_symbols = [
                s for s in _df["symbol"].dropna().tolist()
                if s.upper() != symbol.upper()
            ][:8]

        market_symbols = [
            s for s in _df["symbol"].dropna().tolist()
            if s.upper() != symbol.upper()
        ][:15]

        def fetch_one(s):
            try:
                t    = yf.Ticker(get_yf_symbol(s.strip()))
                inf  = t.info or {}
                divs = t.dividends
                return inf, divs
            except Exception as fe:
                print(f"[fetch_one] {s} skipped: {fe}")
                return {}, None

        def compute_metrics(symbols):
            if not symbols:
                return {"annual_dividend": None, "dividend_yield": None, "track_record": None}

            total_div   = 0; count_div   = 0
            total_yield = 0; count_yield = 0
            total_track = 0; count_track = 0

            with ThreadPoolExecutor(max_workers=6) as ex:
                results = list(ex.map(fetch_one, symbols))

            for inf, divs in results:
                d = inf.get("dividendRate")
                if d and float(d) > 0:
                    total_div  += float(d)
                    count_div  += 1

                y = inf.get("dividendYield")
                if y and float(y) > 0:
                    y = float(y) * 100 if float(y) < 1 else float(y)
                    total_yield += y
                    count_yield += 1

                track = 0
                if divs is not None and not divs.empty:
                    _d = divs.copy()
                    if _d.index.tz is not None:
                        _d.index = _d.index.tz_localize(None)
                    yearly = _d.groupby(_d.index.year).sum()
                    prev   = None
                    for v in yearly:
                        if prev is not None and float(v) > float(prev):
                            track += 1
                        prev = v
                    total_track += track
                    count_track += 1

            return {
                "annual_dividend": round(total_div   / count_div,   2) if count_div   else None,
                "dividend_yield":  round(total_yield / count_yield, 2) if count_yield else None,
                "track_record":    round(total_track / count_track)    if count_track else None,
            }

        # Fetch the first named peer individually for a named comparison
        peer_symbol = peer_symbols[0].strip() if peer_symbols else None
        if peer_symbol:
            try:
                pt    = yf.Ticker(get_yf_symbol(peer_symbol))
                pinf  = pt.info or {}
                pdivs = pt.dividends

                peer_track = 0
                if pdivs is not None and not pdivs.empty:
                    _pd = pdivs.copy()
                    if _pd.index.tz is not None:
                        _pd.index = _pd.index.tz_localize(None)
                    yearly = _pd.groupby(_pd.index.year).sum()
                    prev   = None
                    for v in yearly:
                        if prev is not None and float(v) > float(prev):
                            peer_track += 1
                        prev = v

                py = pinf.get("dividendYield")
                peer_yield  = round(float(py) * 100 if py and float(py) < 1 else float(py), 2) if py else None
                peer_annual = round(float(pinf.get("dividendRate")), 2) if pinf.get("dividendRate") else None

                comparison["peer"] = {
                    "symbol":          peer_symbol,
                    "name":            pinf.get("longName", peer_symbol),
                    "annual_dividend": peer_annual,
                    "dividend_yield":  peer_yield,
                    "track_record":    peer_track if peer_track > 0 else None,
                }
            except Exception as pe:
                print(f"[peer] {peer_symbol} failed: {pe}")
                comparison["peer"] = None
        else:
            comparison["peer"] = None

        comparison["industry_avg"] = compute_metrics(peer_symbols)
        comparison["market_avg"]   = compute_metrics(market_symbols)

    except Exception as comp_err:
        import traceback
        traceback.print_exc()
        comparison = {
            "peer":         None,
            "industry_avg": {"annual_dividend": None, "dividend_yield": None, "track_record": None},
            "market_avg":   {"annual_dividend": None, "dividend_yield": None, "track_record": None},
        }

    return comparison


# ── Route ──────────────────────────────────────────────────────────────────────

@stock_dividend_bp.route("/dividend-summary/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def dividend_summary(symbol):
    try:
        ticker = yf.Ticker(get_yf_symbol(symbol))
        info   = ticker.info or {}

        dividends = ticker.dividends
        if dividends is None or dividends.empty:
            return jsonify({"symbol": symbol, "message": "No dividend data available"})

        divs_clean = dividends.copy()
        if divs_clean.index.tz is not None:
            divs_clean.index = divs_clean.index.tz_localize(None)

        # Basic fields
        dividend_yield  = _normalize_dividend_yield(info.get("dividendYield"))
        annual_dividend = info.get("dividendRate")
        payout_ratio    = info.get("payoutRatio")
        if payout_ratio:
            payout_ratio = round(payout_ratio * 100, 2)

        currency      = info.get("currency", "INR")
        stock_price   = info.get("currentPrice") or info.get("regularMarketPrice")
        price_change  = info.get("regularMarketChange")
        pct_change    = info.get("regularMarketChangePercent")
        last_updated  = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        company_name  = info.get("longName", symbol)
        trailing_eps  = info.get("trailingEps")
        forward_eps   = info.get("forwardEps")
        free_cashflow = info.get("freeCashflow")

        # Most recent dividend
        recent_date           = divs_clean.index[-1]
        recent_value          = float(divs_clean.iloc[-1])
        recent_dividend_payment = recent_value
        formatted_date        = recent_date.strftime("%b. %d").replace(" 0", " ").upper()

        # Next dividend date
        next_dividend_raw = None
        try:
            cal = ticker.calendar
            if isinstance(cal, pd.DataFrame) and "Dividend Date" in cal.index:
                next_dividend_raw = str(cal.loc["Dividend Date"].iloc[0])
            elif isinstance(cal, dict) and "Dividend Date" in cal:
                next_dividend_raw = str(cal["Dividend Date"])
        except Exception:
            pass

        # Build data sections
        dividend_history_full = _build_dividend_history(divs_clean)
        dividend_history      = [{"date": x["date"], "dividend": x["dividend"]} for x in dividend_history_full[-20:]]
        dividends_by_quarter  = _build_quarterly_breakdown(dividend_history_full)
        dividend_yield_over_time = _build_yield_over_time(ticker, divs_clean)
        dividend_table        = _build_dividend_table(divs_clean, ticker)
        growth_5y             = _compute_5yr_cagr(divs_clean)
        increase_years        = _count_increase_years(divs_clean)
        payout_ratio_breakdown = _build_payout_ratio_breakdown(
            payout_ratio, annual_dividend, forward_eps, free_cashflow, info
        )

        # Load CSV stock list for peer comparison
        csv_path = os.path.join(os.path.dirname(__file__), "..", "stock_list.csv")
        try:
            stock_df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        except Exception:
            stock_df = pd.DataFrame()

        comparison = _fetch_peer_metrics(symbol, info, stock_df)

        # Human-readable description
        five_yr_label = f"{growth_5y}%" if growth_5y is not None else "N/A"
        yld_label     = f"{round(dividend_yield * 100, 2)}%" if dividend_yield else "N/A"

        if payout_ratio:
            description = (
                f"{company_name} ({symbol}) has paid a dividend for {increase_years} consecutive years. "
                f"The most recent dividend of ₹{recent_value:.2f} per share was paid on "
                f"{recent_date.strftime('%B %d, %Y').replace(' 0', ' ')}. "
                f"The current annualised dividend is ₹{annual_dividend or 'N/A'} per share, "
                f"representing a dividend yield of {yld_label} based on the current stock price. "
                f"The 5-year dividend CAGR stands at {five_yr_label} and the payout ratio is "
                f"{payout_ratio}% of trailing earnings."
            )
        else:
            description = (
                f"{company_name} ({symbol}) has raised its dividend for {increase_years} consecutive years. "
                f"The current annualised dividend is ₹{annual_dividend or 'N/A'} with a yield of {yld_label}."
            )

        faq = [
            {
                "question": f"When is {symbol}'s next dividend payment?",
                "answer":   f"The next dividend payment date for {symbol} is {next_dividend_raw or 'not yet announced'}.",
            },
            {
                "question": f"What is {symbol}'s dividend yield?",
                "answer":   f"{symbol}'s current dividend yield is {yld_label}.",
            },
            {
                "question": f"How many years has {symbol} increased its dividend?",
                "answer":   f"{symbol} has increased its dividend for {increase_years} consecutive years.",
            },
            {
                "question": f"What is {symbol}'s payout ratio?",
                "answer":   (
                    f"{symbol}'s trailing 12-month payout ratio is {payout_ratio}%."
                    if payout_ratio else "Payout ratio data is not available."
                ),
            },
            {
                "question": f"What is {symbol}'s 5-year dividend growth rate?",
                "answer":   f"{symbol}'s 5-year dividend CAGR is {five_yr_label}.",
            },
        ]

        return jsonify({
            "symbol": symbol,

            "metadata": {
                "currency":     currency,
                "unit":         "per_share",
                "company_name": company_name,
            },

            "stock_header": {
                "stock_price":       round(float(stock_price), 2) if stock_price else None,
                "price_change":      round(float(price_change), 2) if price_change else None,
                "percentage_change": round(float(pct_change) * 100, 2) if pct_change else None,
                "last_updated_time": last_updated,
            },

            "summary": {
                "annual_dividend":               annual_dividend,
                "dividend_yield":                round(dividend_yield * 100, 2) if dividend_yield else None,
                "next_dividend_payment":         next_dividend_raw,
                "recent_dividend_payment":       recent_dividend_payment,
                "formatted_date":                formatted_date,
                "dividend_increase_track_record": increase_years,
                "five_year_growth":              growth_5y,
                "payout_ratio":                  payout_ratio,
                "payout_ratio_breakdown":        payout_ratio_breakdown,
            },

            "description":              description,
            "dividend_history":         dividend_history,
            "dividends_by_quarter":     dividends_by_quarter,
            "dividend_yield_over_time": dividend_yield_over_time,
            "dividend_table":           dividend_table,
            "comparison":               comparison,

            "ui_labels": {
                "dividend_calculator_label": "Dividend Calculator",
                "yield_calculator_label":    "Yield Calculator",
            },

            "faq": faq,
        })

    except Exception as e:
        return jsonify({"error": str(e)})
