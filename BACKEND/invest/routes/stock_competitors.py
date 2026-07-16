"""
/competitors/<symbol>

Finds same-sector competitors, compares sentiment via HuggingFace,
and returns price chart history for all symbols together.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import yfinance as yf
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from ..routes_utils import get_yf_symbol, HF_BASE_URL, HF_HEADERS

import os

stock_competitors_bp = Blueprint("stock_competitors_bp", __name__)

COMPETITORS_CACHE: dict = {}

SENTIMENT_SCORE = {"bullish": 1.35, "neutral": 1.00, "bearish": 0.65}


# ── Sentiment data from HuggingFace ───────────────────────────────────────────

def _fetch_hf_sentiment(symbol: str) -> dict:
    """Returns the full HF payload for a symbol: {news, chart_data, competitors, summary}."""
    try:
        url  = f"{HF_BASE_URL}/sentiment/{symbol.upper()}"
        resp = requests.get(url, headers=HF_HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"[HF] {symbol} → HTTP {resp.status_code}")
            return {"news": [], "chart_data": {}}
        return resp.json()
    except Exception as exc:
        print(f"[HF] {symbol} error: {exc}")
        return {"news": [], "chart_data": {}}


def _merge_chart_data(all_payloads: dict) -> list:
    """
    all_payloads: { "TCS": hf_payload, "INFY": hf_payload, ... }

    Merges each symbol's chart_data into flat rows:
      [{date: "2026-03-30", TCS: 1.0, INFY: 1.35, ...}, ...]
    """
    date_row = {}

    for sym, payload in all_payloads.items():
        for entry in payload.get("chart_data", {}).get(sym, []):
            d = entry.get("date")
            s = entry.get("score", 1.0)
            if d:
                if d not in date_row:
                    date_row[d] = {"date": d}
                date_row[d][sym] = s

    return sorted(date_row.values(), key=lambda r: r["date"])


# ── Chart history building ─────────────────────────────────────────────────────

def _round2(value: float) -> float:
    return float(Decimal(str(float(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_chart_history(symbol: str, competitor_list: list) -> list:
    """
    Download 2 years of daily close prices for the main symbol and all
    competitors, and return a list of dated rows with MDA50/200.
    """
    chart_history = []
    try:
        main_yf_sym  = get_yf_symbol(symbol)
        comp_yf_syms = [get_yf_symbol(c["symbol"]) for c in competitor_list]
        dl_symbols   = [main_yf_sym] + comp_yf_syms

        df = yf.download(dl_symbols, period="2y", interval="1d", auto_adjust=True, progress=False)

        if df.empty:
            return chart_history

        close_df = (
            df["Close"] if isinstance(df.columns, pd.MultiIndex)
            else df[["Close"]].rename(columns={"Close": main_yf_sym})
        )
        vol_df = (
            df["Volume"] if isinstance(df.columns, pd.MultiIndex)
            else df[["Volume"]].rename(columns={"Volume": main_yf_sym})
        )

        if isinstance(close_df, pd.Series):
            close_df = close_df.to_frame(name=main_yf_sym)
        if isinstance(vol_df, pd.Series):
            vol_df = vol_df.to_frame(name=main_yf_sym)

        if main_yf_sym not in close_df.columns:
            return chart_history

        s50  = close_df[main_yf_sym].rolling(50).mean()
        s200 = close_df[main_yf_sym].rolling(200).mean()

        for idx, d in enumerate(df.index):
            c_main = close_df[main_yf_sym].iloc[idx]
            if pd.isna(c_main):
                continue

            row = {"date": str(d.date()), symbol: _round2(c_main)}

            if main_yf_sym in vol_df.columns:
                v = vol_df[main_yf_sym].iloc[idx]
                row["Volume"] = int(v) if not pd.isna(v) else 0

            v50, v200 = s50.iloc[idx], s200.iloc[idx]
            if not pd.isna(v50):
                row["50mda"] = _round2(v50)
            if not pd.isna(v200):
                row["200mda"] = _round2(v200)

            for c_obj in competitor_list:
                cs_yf = get_yf_symbol(c_obj["symbol"])
                if cs_yf in close_df.columns:
                    cv = close_df[cs_yf].iloc[idx]
                    if not pd.isna(cv):
                        row[c_obj["symbol"]] = _round2(cv)

            chart_history.append(row)

    except Exception as chart_err:
        print(f"Chart Error: {chart_err}")

    return chart_history


# ── Route ──────────────────────────────────────────────────────────────────────

@stock_competitors_bp.route("/competitors/<symbol>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def competitors_page(symbol):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    global COMPETITORS_CACHE
    now = time.time()

    if symbol in COMPETITORS_CACHE:
        cached_data, ts = COMPETITORS_CACHE[symbol]
        if now - ts < 600:
            return jsonify(cached_data)

    try:
        ticker       = yf.Ticker(get_yf_symbol(symbol))
        info         = ticker.info or {}
        company_name = info.get("longName") or symbol
        sector       = info.get("sector")

        if not sector:
            return jsonify({"error": "Sector not found for this symbol"})

        # Find competitors in the same sector from the CSV stock list
        csv_path  = os.path.join(os.path.dirname(__file__), "..", "stock_list.csv")
        stocks_df = pd.read_csv(csv_path)
        all_symbols  = [s for s in stocks_df["SYMBOL"].tolist() if s != symbol]
        sample_syms  = all_symbols[:min(40, len(all_symbols))]

        competitor_list  = []
        competitor_infos = {}

        def check_competitor(s):
            try:
                t   = yf.Ticker(get_yf_symbol(s))
                inf = t.info or {}
                if inf.get("sector") == sector:
                    return {"symbol": s, "name": inf.get("longName", s), "info": inf}
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            for res in executor.map(check_competitor, sample_syms):
                if res:
                    competitor_list.append({"symbol": res["symbol"], "name": res["name"]})
                    competitor_infos[res["symbol"]] = res["info"]
                    if len(competitor_list) >= 5:
                        break

        # Comparison table sorted by market cap
        analysis = sorted([
            {
                "symbol":       c["symbol"],
                "marketCap":    competitor_infos[c["symbol"]].get("marketCap"),
                "pe":           competitor_infos[c["symbol"]].get("trailingPE"),
                "profitMargin": competitor_infos[c["symbol"]].get("profitMargins"),
            }
            for c in competitor_list
        ], key=lambda x: x["marketCap"] or 0, reverse=True)

        # Sentiment from HF for main stock and all competitors
        all_sentiment_symbols = [symbol] + [c["symbol"] for c in competitor_list]

        hf_payloads = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_fetch_hf_sentiment, sym): sym for sym in all_sentiment_symbols}
            for future, sym in futures.items():
                hf_payloads[sym] = future.result()

        # Normalize field names in the main stock's sentiment news
        media_sentiment = hf_payloads.get(symbol, {}).get("news", [])
        for a in media_sentiment:
            a["symbol"] = symbol.upper()
            if "learn" in a and "action" not in a:
                a["action"] = a["learn"]
            if "link" in a and "url" not in a:
                a["url"] = a["link"]

        sentiment_chart   = _merge_chart_data(hf_payloads)
        sentiment_summary = {
            sym: hf_payloads[sym].get("summary", "neutral")
            for sym in all_sentiment_symbols
        }

        chart_history = _build_chart_history(symbol, competitor_list)

        comparison = [
            {"symbol": symbol, "marketCap": info.get("marketCap"),
             "pe": info.get("trailingPE"), "profitMargin": info.get("profitMargins")}
        ]
        comparison.extend(analysis)

        result_dict = {
            "competitor_list":    competitor_list,
            "analysis":           analysis,
            "media_sentiment":    media_sentiment,
            "sentiment_chart":    sentiment_chart,
            "sentiment_summary":  sentiment_summary,
            "has_sentiment_data": len(sentiment_chart) > 0,
            "comparison":         comparison,
            "chart_history":      chart_history[-185:],
        }

        COMPETITORS_CACHE[symbol] = (result_dict, now)
        return jsonify(result_dict)

    except Exception as e:
        return jsonify({"error": str(e)})
