import time
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import yfinance as yf
import pandas as pd
from .stock_common import get_yf_symbol

GLOBAL_CACHE = {"pl": {}, "other": {}}
CACHE_TTL = {"pl": 86400}

stock_chart_bp = Blueprint("stock_chart_bp", __name__)

@stock_chart_bp.route("/stock-chart/<symbol>")
@cross_origin(supports_credentials=True)
def stock_chart(symbol):
    """
    Enhanced stock chart endpoint returning OHLC + DMA50/200 data.

    Query params:
      - period:   1d | 5d | 1mo | 3mo | 6mo | ytd | 1y | 5y  (default: 1y)
      - interval: 1m | 5m | 15m | 30m | 1h | 1d | 1wk | 1mo  (default: 1d)

    Response shape (backwards-compatible — 'price' still present as alias for 'close'):
      [{ date, open, high, low, close, price, volume, dma50, dma200 }, ...]
    """
    try:
        # ---- Read & validate query params ----
        VALID_PERIODS   = {"1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "5y"}
        VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "1wk", "1mo"}

        period   = request.args.get("period",   "1y").lower()
        interval = request.args.get("interval", "1d").lower()

        if period   not in VALID_PERIODS:   period   = "1y"
        if interval not in VALID_INTERVALS: interval = "1d"

        # ---- Fetch OHLCV history ----
        ticker = yf.Ticker(get_yf_symbol(symbol))
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return jsonify([])

        # ---- Flatten multi-level columns yfinance sometimes returns ----
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # ---- Rolling moving averages (only meaningful on daily+ intervals) ----
        close = df["Close"]
        df["dma50"]  = close.rolling(window=50).mean()
        df["dma200"] = close.rolling(window=200).mean()

        # ---- Shares outstanding for market cap calculation ----
        shares_outstanding = None
        try:
            info = ticker.info or {}
            shares_outstanding = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        except Exception:
            pass

        # ---- Determine date format based on interval ----
        intraday = interval in {"1m", "2m", "5m", "15m", "30m", "60m", "1h"}
        date_fmt = "%Y-%m-%dT%H:%M:%S" if intraday else "%Y-%m-%d"

        # ---- Build result list ----
        result = []
        for idx, row in df.iterrows():
            # Normalise index to tz-naive string
            try:
                date_str = idx.strftime(date_fmt)
            except Exception:
                date_str = str(idx)[:10]

            o = round(float(row["Open"]),  2) if pd.notna(row["Open"])  else None
            h = round(float(row["High"]),  2) if pd.notna(row["High"])  else None
            l = round(float(row["Low"]),   2) if pd.notna(row["Low"])   else None
            c = round(float(row["Close"]), 2) if pd.notna(row["Close"]) else None
            v = int(row["Volume"])             if pd.notna(row["Volume"]) else 0

            d50  = round(float(row["dma50"]),  2) if pd.notna(row["dma50"])  else None
            d200 = round(float(row["dma200"]), 2) if pd.notna(row["dma200"]) else None

            market_cap = round(c * shares_outstanding, 2) if c and shares_outstanding else None

            result.append({
                "date":       date_str,
                # OHLC
                "open":       o,
                "high":       h,
                "low":        l,
                "close":      c,
                "price":      c,          # ← backwards-compatible alias
                # Volume
                "volume":     v,
                # Moving averages
                "dma50":      d50,
                "dma200":     d200,
                # Market cap (close * shares_outstanding)
                "market_cap": market_cap,
            })

        return (result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

#--------------------------------------------------------------------------------------------------------------------
def get_yearly_dividends_per_share(ticker, years):
    """
    Returns dividend per share for each year (aligned with income statement years)
    """
    dividends = ticker.dividends  # pandas Series: date -> dividend per share

    if dividends is None or dividends.empty:
        return [None] * len(years)

    # group dividends by year
    dividends.index = dividends.index.year
    yearly = dividends.groupby(dividends.index).sum()

    result = []
    for y in years:
        result.append(float(yearly.get(int(y), 0)) if int(y) in yearly else None)

    return result


def get_simple_pl_2y(symbol):
    cache = GLOBAL_CACHE["pl"]
    cache_key = f"pl:{symbol.upper()}"

    # ---- Serve from cache
    if cache_key in cache:
        entry = cache[cache_key]
        if time.time() - entry["timestamp"] < CACHE_TTL["pl"]:
            return entry["data"]

    # ---- Fetch from yfinance
    ticker = yf.Ticker(get_yf_symbol(symbol))
    df = ticker.income_stmt

    if df is None or df.empty:
        raise Exception("P&L data not available")

    df = df.iloc[:, :2]
    years = [str(c.year) for c in df.columns]

    def val(field):
        if field in df.index:
            return [float(x) if pd.notna(x) else None for x in df.loc[field]]
        return [None, None]

    # ---------------- RAW VALUES ----------------
    sales = val("Total Revenue")
    expenses = val("Total Expenses")
    operating_profit = val("Operating Income")
    ebitda = val("EBITDA")
    net_profit = val("Net Income")
    pbt = val("Pretax Income")
    eps = val("Basic EPS")

    interest_income = val("Interest Income")
    other_non_op = val("Other Non Operating Income Expense")
    interest_expense = val("Interest Expense")
    depreciation = val("Reconciled Depreciation")

    dividends_per_share = get_yearly_dividends_per_share(ticker, years)

    dividend_payout_percent = []
    for i in range(len(years)):
        if eps[i] and dividends_per_share[i] is not None:
            dividend_payout_percent.append(dividends_per_share[i] / eps[i])
        else:
            dividend_payout_percent.append(None)

    sales_growth = [None, None]
    if sales[1] and sales[0]:
        sales_growth[0] = (sales[0] - sales[1]) / sales[1]

    expense_growth = [None, None]
    if expenses[1] and expenses[0]:
        expense_growth[0] = (expenses[0] - expenses[1]) / expenses[1]

    other_income = [
        (interest_income[i] or 0) + (other_non_op[i] or 0)
        for i in range(2)
    ]

    opm = [(operating_profit[i] / sales[i]) if sales[i] else None for i in range(2)]
    ebitda_margin = [(ebitda[i] / sales[i]) if sales[i] else None for i in range(2)]
    npm = [(net_profit[i] / sales[i]) if sales[i] else None for i in range(2)]

    net_income_common = val("Net Income Common Stockholders")
    diluted_ni_raw = val("Diluted NI Available To Com Stockholders")
    diluted_ni = [
        diluted_ni_raw[i] if diluted_ni_raw[i] is not None else net_income_common[i]
        for i in range(2)
    ]

    result = {
        "years": years,

        "sales": sales,
        "sales_growth": sales_growth,
        "sales_breakup": {
            "total_revenue": sales,
            "operating_revenue": val("Operating Revenue"),
        },

        "expenses": expenses,
        "expense_growth": expense_growth,
        "expenses_breakup": {
            "cost_of_revenue": val("Cost Of Revenue"),
            "operating_expense": val("Operating Expense"),
            "selling_general_and_admin": val("Selling General And Administration"),
            "research_and_development": val("Research And Development"),
        },

        "operating_profit": operating_profit,
        "opm_percent": opm,

        "ebitda": ebitda,
        "ebitda_margin_percent": ebitda_margin,

        "other_income": other_income,
        "other_income_breakup": {
            "interest_income": interest_income,
            "other_non_op_income": other_non_op,
        },

        "interest": interest_expense,
        "depreciation": depreciation,

        "profit_before_tax": pbt,

        "net_profit": net_profit,
        "net_profit_margin_percent": npm,
        "net_profit_breakup": {
            "net_income_common": net_income_common,
            "diluted_ni": diluted_ni,
            "normalized_income": val("Normalized Income"),
        },

        "eps": eps,
        "dividend_payout_percent": dividend_payout_percent,

        "source": "yfinance",
        "period": "annual",
    }

    # ---- Save to cache
    cache[cache_key] = {
        "timestamp": time.time(),
        "data": result
    }

    return result