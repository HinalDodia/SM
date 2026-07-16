"""
/stock-chart/<symbol>  and  /test-yfinance/<symbol>

Handles OHLCV chart data with DMA50/200 moving averages.
"""

import pandas as pd
import yfinance as yf
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from ..routes_utils import get_yf_symbol

stock_chart_bp = Blueprint("stock_chart_bp", __name__)


# ── /test-yfinance/<symbol> ────────────────────────────────────────────────────

@stock_chart_bp.route("/test-yfinance/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def test_yfinance(symbol):
    try:
        yf_sym = get_yf_symbol(symbol)
        ticker = yf.Ticker(yf_sym)
        info = ticker.info or {}
        hist = ticker.history(period="1d")

        return jsonify({
            "symbol":           symbol,
            "yf_symbol":        yf_sym,
            "info_keys_count":  len(info),
            "info_sample":      {k: info.get(k) for k in list(info.keys())[:5]},
            "history_empty":    hist.empty,
            "history_rows":     len(hist) if not hist.empty else 0,
            "longName":         info.get("longName"),
            "currentPrice":     info.get("currentPrice"),
        })
    except Exception as e:
        return jsonify({"error": str(e), "symbol": symbol})


# ── /stock-chart/<symbol> ──────────────────────────────────────────────────────

VALID_PERIODS   = {"1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "5y"}
VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "1wk", "1mo"}
INTRADAY_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "1h"}


def _build_chart_row(idx, row, date_fmt, shares_outstanding):
    """Build a single chart data point from a DataFrame row."""
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

    return {
        "date":       date_str,
        "open":       o,
        "high":       h,
        "low":        l,
        "close":      c,
        "price":      c,   # backwards-compatible alias
        "volume":     v,
        "dma50":      d50,
        "dma200":     d200,
        "market_cap": market_cap,
    }


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
        period   = request.args.get("period",   "1y").lower()
        interval = request.args.get("interval", "1d").lower()

        if period   not in VALID_PERIODS:   period   = "1y"
        if interval not in VALID_INTERVALS: interval = "1d"

        ticker = yf.Ticker(get_yf_symbol(symbol))
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return jsonify([])

        # Flatten multi-level columns yfinance sometimes returns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        df["dma50"]  = close.rolling(window=50).mean()
        df["dma200"] = close.rolling(window=200).mean()

        shares_outstanding = None
        try:
            info = ticker.info or {}
            shares_outstanding = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        except Exception:
            pass

        intraday = interval in INTRADAY_INTERVALS
        date_fmt = "%Y-%m-%dT%H:%M:%S" if intraday else "%Y-%m-%d"

        result = [
            _build_chart_row(idx, row, date_fmt, shares_outstanding)
            for idx, row in df.iterrows()
        ]

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
