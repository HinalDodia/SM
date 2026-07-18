from flask import Blueprint, jsonify,g
from flask_cors import cross_origin
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback, time
from .stock_common import get_yf_symbol,stock_df
from decimal import Decimal, ROUND_HALF_UP
stock_dividend_bp = Blueprint("stock_dividend_bp", __name__)

@stock_dividend_bp.route("/dividend-summary/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def dividend_summary(symbol):

    try:

        ticker = yf.Ticker(get_yf_symbol(symbol))
        info = ticker.info or {}

        dividends = ticker.dividends

        if dividends is None or dividends.empty:
            return jsonify({
                "symbol": symbol,
                "message": "No dividend data available"
            })

        # ---------- NORMALIZE DIVIDENDS (always per-share, INR) ----------
        # yfinance returns raw per-share values for NSE; no scaling needed.
        # Keep a clean copy with tz-naive index for groupby operations.
        divs_clean = dividends.copy()
        if divs_clean.index.tz is not None:
            divs_clean.index = divs_clean.index.tz_localize(None)

        # ---------- BASIC INFO ----------
        dividend_yield   = info.get("dividendYield")           # e.g. 0.0257 or 2.57
        if dividend_yield and dividend_yield > 1:
            dividend_yield = dividend_yield / 100.0            # Normalize to decimal

        annual_dividend  = info.get("dividendRate")            # e.g. 63.0
        payout_ratio     = info.get("payoutRatio")             # e.g. 0.4632
        if payout_ratio:
            payout_ratio = round(payout_ratio * 100, 2)        # Convert to % (46.32)

        currency         = info.get("currency", "INR")
        stock_price      = info.get("currentPrice") or info.get("regularMarketPrice")
        price_change     = info.get("regularMarketChange")
        pct_change       = info.get("regularMarketChangePercent")
        last_updated     = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        company_name     = info.get("longName", symbol)
        trailing_eps     = info.get("trailingEps")
        forward_eps      = info.get("forwardEps")
        free_cashflow    = info.get("freeCashflow")

        # ---------- MOST RECENT DIVIDEND ----------
        recent_date  = divs_clean.index[-1]
        recent_value = float(divs_clean.iloc[-1])
        recent_dividend_payment = recent_value
        formatted_date = recent_date.strftime("%b. %d").replace(" 0", " ").upper() # e.g. "JAN. 16"

        # ---------- NEXT DIVIDEND DATE ----------
        next_dividend_raw = None
        try:
            cal = ticker.calendar
            if isinstance(cal, pd.DataFrame) and "Dividend Date" in cal.index:
                next_dividend_raw = str(cal.loc["Dividend Date"].iloc[0])
            elif isinstance(cal, dict) and "Dividend Date" in cal:
                next_dividend_raw = str(cal["Dividend Date"])
        except Exception:
            pass

        # ---------- DIVIDEND HISTORY (last 50, normalised) ----------
        dividend_history_full = []
        for dt, val in divs_clean.tail(50).items():
            dividend_history_full.append({
                "date": str(dt.date()),
                "dividend": round(float(val), 4),
                "year": dt.year,
                "quarter": dt.quarter
            })
        
        # UI history list (keep last 20)
        dividend_history = [{"date": x["date"], "dividend": x["dividend"]} for x in dividend_history_full[-20:]]

        # ---------- DIVIDENDS BY QUARTER (Recomputed from history) ----------
        # Group the history entries by year and quarter to ensure 100% unit parity
        q_map = {}
        for entry in dividend_history_full:
            key = (entry["year"], entry["quarter"])
            q_map[key] = q_map.get(key, 0) + entry["dividend"]
        
        dividends_by_quarter = [
            {"year": k[0], "quarter": k[1], "dividend": round(v, 4)}
            for k, v in sorted(q_map.items())
        ]

        # ---------- DIVIDEND YIELD OVER TIME ----------
        dividend_yield_over_time = []
        try:
            hist_prices = ticker.history(period="10y", interval="1mo")
            if not hist_prices.empty:
                hist_prices.index = hist_prices.index.tz_localize(None) if hist_prices.index.tz else hist_prices.index
                # Rolling 12-month dividend sum per month
                monthly_divs = divs_clean.resample("ME").sum()
                rolling_annual = monthly_divs.rolling(12, min_periods=1).sum()
                for dt, price_row in hist_prices.iterrows():
                    close = price_row["Close"]
                    ann_div = float(rolling_annual.get(dt, rolling_annual.asof(dt) if not rolling_annual.empty else 0) or 0)
                    yld = round((ann_div / float(close)) * 100, 4) if close and float(close) > 0 else None
                    dividend_yield_over_time.append({
                        "date": dt.strftime("%Y-%m-%d"),
                        "yield": yld
                    })
        except Exception:
            pass

        # ---------- 5-YEAR CAGR ----------
        growth_5y = None
        try:
            cutoff = divs_clean.index[-1] - pd.DateOffset(years=5)
            last5  = divs_clean[divs_clean.index >= cutoff]
            yearly = last5.groupby(last5.index.year).sum()
            if len(yearly) >= 2:
                first_val = float(yearly.iloc[0])
                last_val  = float(yearly.iloc[-1])
                n_years   = len(yearly) - 1
                growth_5y = round(((last_val / first_val) ** (1 / n_years) - 1) * 100, 2) if first_val > 0 else None
        except Exception:
            pass

        # ---------- DIVIDEND INCREASE TRACK RECORD ----------
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

        # ---------- PAYOUT RATIO BREAKDOWN ----------
        payout_trailing  = payout_ratio  # Already converted to % above

        # This-year estimate: annual_dividend / forward_eps
        payout_this_year = None
        try:
            if annual_dividend and forward_eps and forward_eps > 0:
                payout_this_year = round((annual_dividend / forward_eps) * 100, 2)
        except Exception:
            pass

        # Next-year estimate: use same ratio as fallback (no yfinance field)
        payout_next_year = payout_this_year  # can be replaced with analyst data if available

        # Free-cashflow payout: annual_div_total / FCF (per-share basis via shares outstanding)
        payout_cashflow = None
        try:
            shares = info.get("sharesOutstanding")
            if free_cashflow and shares and shares > 0 and annual_dividend:
                fcf_per_share = free_cashflow / shares
                payout_cashflow = round((annual_dividend / fcf_per_share) * 100, 2)
        except Exception:
            pass

        payout_ratio_breakdown = {
            "trailing_12_months": payout_trailing,
            "this_year_estimate": payout_this_year,
            "next_year_estimate": payout_next_year,
            "cashflow":           payout_cashflow
        }

        # ---------- DIVIDEND TABLE (full detail per payment) ----------
        dividend_table = []
        try:
            # Build yield per payment using closest price on ex-div date
            hist_full = ticker.history(period="max", interval="1d")
            if hist_full.index.tz is not None:
                hist_full.index = hist_full.index.tz_localize(None)

            prev_div = None
            for i, (dt, val) in enumerate(divs_clean.items()):
                fval = round(float(val), 4)

                # payment change
                if prev_div is not None and prev_div != 0:
                    change = round(((fval - prev_div) / prev_div) * 100, 2)
                else:
                    change = None

                # yield on payment date
                row_yield = None
                try:
                    closest_price = hist_full.asof(dt)["Close"]
                    if closest_price and float(closest_price) > 0:
                        # annualise: multiply by 4 (quarterly assumption)
                        row_yield = round((fval * 4 / float(closest_price)) * 100, 2)
                except Exception:
                    pass

                # Period label e.g. "Q1 2025"
                period = f"Q{dt.quarter} {dt.year}"

                # Announced date is typically ~4 weeks before ex-div; approximate
                announced_dt = dt - timedelta(weeks=4)

                # Record date ≈ ex-div + 1 trading day; payable ≈ ex-div + 15 days
                record_dt  = dt + timedelta(days=1)
                payable_dt = dt + timedelta(days=15)

                dividend_table.append({
                    "announced_date": announced_dt.strftime("%Y-%m-%d"),
                    "period":         period,
                    "payment":        fval,
                    "payment_change": change,
                    "yield":          row_yield,
                    "ex_dividend_date": str(dt.date()),
                    "record_date":    record_dt.strftime("%Y-%m-%d"),
                    "payable_date":   payable_dt.strftime("%Y-%m-%d")
                })

                prev_div = fval

        except Exception:
            pass

       # ---------- COMPARISON DATA ----------
        comparison = {}
        try:
            from concurrent.futures import ThreadPoolExecutor

            _df = stock_df.copy()
            # Normalize ALL column names to lowercase to avoid case issues
            _df.columns = [c.strip().lower() for c in _df.columns]
            # Strip whitespace from all string values (pandas 2.1+ compatible)
            try:
                _df = _df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
            except AttributeError:
                _df = _df.map(lambda x: x.strip() if isinstance(x, str) else x)

            # Now columns are: 'symbol', 'name of company', 'sector', 'industry'
            current_sector = (info.get("sector") or "").strip().lower()
            print(f"[Comparison] yfinance sector='{current_sector}'")
            print(f"[Comparison] CSV sectors={_df['sector'].str.lower().unique().tolist()}")

            # Fuzzy sector match: check if any CSV sector word appears in yfinance sector or vice versa
            # e.g. yfinance="Technology" matches CSV="Information Technology"
            def sectors_match(csv_sector):
                csv_s = csv_sector.strip().lower()
                if not csv_s or not current_sector:
                    return False
                # Direct match
                if csv_s == current_sector:
                    return True
                # Partial match either way
                if current_sector in csv_s or csv_s in current_sector:
                    return True
                # Word overlap (e.g. "Technology" in "Information Technology")
                csv_words = set(csv_s.split())
                yf_words  = set(current_sector.split())
                return bool(csv_words & yf_words)

            same_sector_mask = _df["sector"].apply(sectors_match)
            current_sym_mask = _df["symbol"].str.upper() != symbol.upper()

            same_sector_df = _df[same_sector_mask & current_sym_mask]
            peer_symbols   = same_sector_df["symbol"].dropna().tolist()[:8]

            # Fallback: if no sector peers found, use all other symbols
            if not peer_symbols:
                print(f"[Comparison] No sector peers found, falling back to all symbols")
                peer_symbols = [
                    s for s in _df["symbol"].dropna().tolist()
                    if s.upper() != symbol.upper()
                ][:8]

            market_symbols = [
                s for s in _df["symbol"].dropna().tolist()
                if s.upper() != symbol.upper()
            ][:15]

            print(f"[Comparison] peers={peer_symbols}")
            print(f"[Comparison] market_symbols count={len(market_symbols)}")

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

            # ---- peer (first same-sector symbol) ----
            # ---- peer (first same-sector symbol) ----
            peer_symbol = peer_symbols[0].strip() if peer_symbols else None
            if peer_symbol:
                try:
                    pt    = yf.Ticker(get_yf_symbol(peer_symbol))
                    pinf  = pt.info or {}
                    pdivs = pt.dividends

                    # ── track record ──
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

                    # ── dividend yield: normalize same way as compute_metrics ──
                    # yfinance returns either decimal (0.0411) or percent (4.11) — handle both
                    py = pinf.get("dividendYield")
                    if py:
                        py = float(py)
                        peer_yield = round(py * 100 if py < 1 else py, 2)
                    else:
                        peer_yield = None

                    # ── annual dividend ──
                    peer_annual = pinf.get("dividendRate")
                    if peer_annual:
                        peer_annual = round(float(peer_annual), 2)

                    comparison["peer"] = {
                        "symbol":          peer_symbol,
                        "name":            pinf.get("longName", peer_symbol),
                        "annual_dividend": peer_annual,
                        "dividend_yield":  peer_yield,
                        "track_record":    peer_track if peer_track > 0 else None,
                    }
                    print(f"[peer] {peer_symbol} → yield={peer_yield} annual={peer_annual} track={peer_track}")

                except Exception as pe:
                    print(f"[peer] {peer_symbol} failed: {pe}")
                    comparison["peer"] = None
            else:
                comparison["peer"] = None
            comparison["industry_avg"] = compute_metrics(peer_symbols)
            comparison["market_avg"]   = compute_metrics(market_symbols)

            print(f"[Comparison] done — peer={comparison.get('peer', {}).get('symbol') if comparison.get('peer') else None}")

        except Exception as comp_err:
            print(f"[comparison] block failed: {comp_err}")
            import traceback; traceback.print_exc()
            comparison = {
                "peer":         None,
                "industry_avg": {"annual_dividend": None, "dividend_yield": None, "track_record": None},
                "market_avg":   {"annual_dividend": None, "dividend_yield": None, "track_record": None},
            }
            
                    # ---------- DESCRIPTION ----------
        five_yr_label = f"{growth_5y}%" if growth_5y is not None else "N/A"
        yld_label = f"{round(dividend_yield * 100, 2)}%" if dividend_yield else "N/A"
        description = (
            f"{company_name} ({symbol}) has paid a dividend for {increase_years} consecutive years. "
            f"The most recent dividend of ₹{recent_value:.2f} per share was paid on {recent_date.strftime('%B %d, %Y').replace(' 0', ' ')}. "
            f"The current annualised dividend is ₹{annual_dividend or 'N/A'} per share, "
            f"representing a dividend yield of {yld_label} based on the current stock price. "
            f"The 5-year dividend CAGR stands at {five_yr_label} and the payout ratio is "
            f"{payout_ratio}% of trailing earnings."
            if payout_ratio else
            f"{company_name} ({symbol}) has raised its dividend for {increase_years} consecutive years. "
            f"The current annualised dividend is ₹{annual_dividend or 'N/A'} with a yield of {yld_label}."
        )

        # ---------- FAQ ----------
        faq = [
            {
                "question": f"When is {symbol}'s next dividend payment?",
                "answer": f"The next dividend payment date for {symbol} is {next_dividend_raw or 'not yet announced'}."
            },
            {
                "question": f"What is {symbol}'s dividend yield?",
                "answer": f"{symbol}'s current dividend yield is {yld_label}."
            },
            {
                "question": f"How many years has {symbol} increased its dividend?",
                "answer": f"{symbol} has increased its dividend for {increase_years} consecutive years."
            },
            {
                "question": f"What is {symbol}'s payout ratio?",
                "answer": f"{symbol}'s trailing 12-month payout ratio is {payout_trailing}%." if payout_trailing else "Payout ratio data is not available."
            },
            {
                "question": f"What is {symbol}'s 5-year dividend growth rate?",
                "answer": f"{symbol}'s 5-year dividend CAGR is {five_yr_label}."
            }
        ]

        # ---------- FINAL RESPONSE ----------
        return jsonify({

            "symbol": symbol,

            # ── METADATA ──
            "metadata": {
                "currency":  currency,
                "unit":      "per_share",
                "company_name": company_name
            },

            # ── STOCK HEADER ──
            "stock_header": {
                "stock_price":       round(float(stock_price), 2) if stock_price else None,
                "price_change":      round(float(price_change), 2) if price_change else None,
                "percentage_change": round(float(pct_change) * 100, 2) if pct_change else None,
                "last_updated_time": last_updated
            },

            # ── SUMMARY ──
            "summary": {
                "annual_dividend":               annual_dividend,
                "dividend_yield":                round(dividend_yield * 100, 2) if dividend_yield else None,
                "next_dividend_payment":         next_dividend_raw,
                "recent_dividend_payment":       recent_dividend_payment,
                "formatted_date":                formatted_date,
                "dividend_increase_track_record": increase_years,
                "five_year_growth":              growth_5y,
                "payout_ratio":                  payout_ratio,
                "payout_ratio_breakdown":        payout_ratio_breakdown
            },

            # ── DESCRIPTION ──
            "description": description,

            # ── DIVIDEND HISTORY (last 20, normalised per-share) ──
            "dividend_history": dividend_history,

            # ── DIVIDENDS BY QUARTER ──
            "dividends_by_quarter": dividends_by_quarter,

            # ── CHART: YIELD OVER TIME ──
            "dividend_yield_over_time": dividend_yield_over_time,

            # ── FULL DIVIDEND TABLE ──
            "dividend_table": dividend_table,

            # ── COMPARISON ──
            "comparison": comparison,

            # ── UI LABELS ──
            "ui_labels": {
                "dividend_calculator_label": "Dividend Calculator",
                "yield_calculator_label":    "Yield Calculator"
            },

            # ── FAQ ──
            "faq": faq

        })

    except Exception as e:
        return jsonify({"error": str(e)})


