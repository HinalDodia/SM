from flask import Blueprint, jsonify
from flask_cors import cross_origin
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
from nselib import capital_market


stock_short_interest_bp = Blueprint("stock_short_interest_bp", __name__)

def _derive_signal(oi_change_pct: float, price_change_pct: float) -> str:
    oi_up    = oi_change_pct >= 0
    price_up = price_change_pct >= 0
    if oi_up and not price_up:   return "Short Build-up"
    if not oi_up and price_up:   return "Short Covering"
    if oi_up and price_up:       return "Long Build-up"
    return "Long Unwinding"

def _compute_score(oi_chg: float, mwpl: float, pcr: float, vol_ratio: float, signal: str) -> int:
    s1 = min(abs(oi_chg) / 20 * 25, 25)
    s2 = min(mwpl / 100 * 25, 25)
    s3 = min(pcr / 2.0 * 25, 25)
    s4 = max(min((vol_ratio - 1) / 2 * 25, 25), 0)
    raw = s1 + s2 + s3 + s4
    mult = {"Short Build-up": 1.0, "Short Covering": 0.5, "Long Build-up": 0.3, "Long Unwinding": 0.6}.get(signal, 1.0)
    return round(min(raw * mult, 100))

def _fetch_oi_mwpl_pcr(symbol: str) -> dict:
    result = {
        "oi_change_pct":       None,
        "mwpl_pct":            None,
        "pcr":                 None,
        "short_qty":           None,
        "short_qty_change":    None,
        "delivery_pct":        None,
        "delivery_pct_5d_avg": None,
        "no_of_trades":        None,
    }

    from datetime import datetime, timedelta
    to_date   = datetime.now()
    from_date = to_date - timedelta(days=20)  # wider window = more stable baseline
    to_str    = to_date.strftime("%d-%m-%Y")
    from_str  = from_date.strftime("%d-%m-%Y")

    # ── 1. Short Selling Data ────────────────────────────────────────────────
    try:
        ss_df = capital_market.short_selling_data(
            from_date=from_str,
            to_date=to_str
        )
        ss_df = ss_df[ss_df["Symbol"].str.upper() == symbol.upper()].copy()

        if not ss_df.empty:
            ss_df["Quantity"] = (
                ss_df["Quantity"]
                .astype(str)
                .str.replace(",", "")
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0)
            )
            ss_df = ss_df.sort_values("Date", ascending=False).reset_index(drop=True)

            today_qty = float(ss_df.iloc[0]["Quantity"])
            result["short_qty"] = int(today_qty)

            if len(ss_df) >= 2:
                prev_qty = float(ss_df.iloc[1]["Quantity"])
                result["short_qty_change"] = int(today_qty - prev_qty)

                if prev_qty > 0:
                    raw_chg = ((today_qty - prev_qty) / prev_qty) * 100
                    # Cap at ±50% — beyond that it's data sparsity not real change
                    result["oi_change_pct"] = round(max(-50.0, min(50.0, raw_chg)), 2)
                else:
                    result["oi_change_pct"] = 0.0

    except Exception as e:
        print(f"[nselib] short_selling_data failed for {symbol}: {e}")

    # ── 2. Deliverable Position Data ─────────────────────────────────────────
    try:
        del_df = capital_market.deliverable_position_data(
            symbol=symbol,
            from_date=from_str,
            to_date=to_str
        )

        if not del_df.empty:
            del_df["%DlyQttoTradedQty"] = (
                del_df["%DlyQttoTradedQty"]
                .astype(str)
                .str.replace(",", "")
                .pipe(pd.to_numeric, errors="coerce")
                .fillna(0)
            )
            del_df = del_df.sort_values("Date", ascending=False).reset_index(drop=True)

            result["delivery_pct"]        = float(del_df.iloc[0]["%DlyQttoTradedQty"])
            result["delivery_pct_5d_avg"] = round(float(del_df.head(5)["%DlyQttoTradedQty"].mean()), 2)

            # delivery_pct as mwpl equivalent — invert it:
            # LOW delivery = more speculative/short activity = higher "pressure"
            result["mwpl_pct"] = round(100 - result["delivery_pct"], 2)

    except Exception as e:
        print(f"[nselib] deliverable_position_data failed for {symbol}: {e}")

    # ── 3. Price Volume → PCR proxy + trade count ────────────────────────────
    try:
        pv_df = capital_market.price_volume_data(
            symbol=symbol,
            from_date=from_str,
            to_date=to_str
        )

        if not pv_df.empty:
            pv_df = pv_df.sort_values("Date", ascending=False).reset_index(drop=True)

            for col in ["TotalTradedQuantity", "No.ofTrades"]:
                pv_df[col] = (
                    pv_df[col]
                    .astype(str)
                    .str.replace(",", "")
                    .pipe(pd.to_numeric, errors="coerce")
                    .fillna(0)
                )

            result["no_of_trades"] = int(pv_df.iloc[0]["No.ofTrades"])

            vol    = float(pv_df.iloc[0]["TotalTradedQuantity"])
            trades = float(pv_df.iloc[0]["No.ofTrades"])
            if vol > 0 and trades > 0:
                avg_trade_size   = vol / trades
                result["pcr"]    = round(max(0.5, min(2.0, 20 / avg_trade_size)), 2)

    except Exception as e:
        print(f"[nselib] price_volume_data failed for {symbol}: {e}")

    return result


# @stock_short_interest_bp.route("/short-interest/<symbol>", methods=["GET"])
# @cross_origin(supports_credentials=True)
def short_interest(symbol):
    """
    NSE equivalent of short interest for a single F&O stock.

    Returns:
        price, price_change_pct, volume, volume_ratio,
        oi_change_pct, mwpl_pct, pcr,
        signal (Short Build-up / Short Covering / Long Build-up / Long Unwinding),
        score (0-100),
        price_history (30 days, for charts)
    """
    symbol = symbol.upper().strip()

    # ── 1. Price + volume from yfinance ─────────────────────────────────────
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        hist   = ticker.history(period="35d").tail(30)

        if hist.empty:
            return ({"error": f"No price data found for {symbol}"}), 404

        latest       = hist.iloc[-1]
        prev         = hist.iloc[-2] if len(hist) > 1 else latest
        price_change = round(((latest["Close"] - prev["Close"]) / prev["Close"]) * 100, 2)
        avg_vol_20   = hist["Volume"].tail(20).mean()
        vol_ratio    = round(latest["Volume"] / avg_vol_20, 2) if avg_vol_20 > 0 else 1.0

        info         = ticker.info
        price_history = [
            {"date": str(row.Index.date()), "close": round(float(row.Close), 2), "volume": int(row.Volume)}
            for row in hist.itertuples()
        ]
    except Exception as e:
        return ({"error": f"Price fetch failed: {str(e)}"}), 502

    # ── 2. OI / MWPL / PCR from NSE ─────────────────────────────────────────
    oi_data = _fetch_oi_mwpl_pcr(symbol)

    oi_change_pct = oi_data["oi_change_pct"] if oi_data["oi_change_pct"] is not None else 0.0
    mwpl_pct      = oi_data["mwpl_pct"]      if oi_data["mwpl_pct"]      is not None else 0.0
    pcr           = oi_data["pcr"]            if oi_data["pcr"]            is not None else 1.0

    # ── 3. Signal + Score ────────────────────────────────────────────────────
    signal = _derive_signal(oi_change_pct, price_change)
    score  = _compute_score(oi_change_pct, mwpl_pct, pcr, vol_ratio, signal)

    return ({
        "symbol":              symbol,
        "name":                info.get("longName", ""),
        "sector":              info.get("sector", ""),
        "price":               round(float(latest["Close"]), 2),
        "price_change":        price_change,
        "volume":              int(latest["Volume"]),
        "avg_volume_20d":      int(avg_vol_20),
        "volume_ratio":        vol_ratio,
        "week52_high":         info.get("fiftyTwoWeekHigh"),
        "week52_low":          info.get("fiftyTwoWeekLow"),
        # core positioning fields
        "oi_change_pct":       oi_change_pct,
        "mwpl_pct":            mwpl_pct,
        "pcr":                 pcr,
        "signal":              signal,
        "score":               score,
        "oi_data_live":        oi_data["oi_change_pct"] is not None,
        # new bonus fields
        "short_qty":           oi_data.get("short_qty"),
        "short_qty_change":    oi_data.get("short_qty_change"),
        "delivery_pct":        oi_data.get("delivery_pct"),
        "delivery_pct_5d_avg": oi_data.get("delivery_pct_5d_avg"),
        "no_of_trades":        oi_data.get("no_of_trades"),
        "price_history":       price_history,
        "as_of":               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
