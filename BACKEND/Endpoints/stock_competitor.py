import os
from flask import Blueprint, request, jsonify, g
from flask_cors import cross_origin
import pandas as pd
import yfinance as yf
import re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from .stock_common import get_yf_symbol
from decimal import Decimal, ROUND_HALF_UP
stock_competitor_bp = Blueprint("stock_competitor_bp", __name__)
from Endpoints.stock_headlines import _merge_chart_data, _fetch_hf_sentiment

COMPETITORS_CACHE = {}

@stock_competitor_bp.route("/competitors/<symbol>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def competitors_page(symbol):
    try:
        if request.method == "OPTIONS":
            return jsonify({"status": "ok"}), 200
    except RuntimeError:
        pass
        
    global COMPETITORS_CACHE
    now = time.time()
    if symbol in COMPETITORS_CACHE:
        cached_data, ts = COMPETITORS_CACHE[symbol]
        if now - ts < 600:
            return jsonify(cached_data)

    try:
        ticker = yf.Ticker(get_yf_symbol(symbol))
        info   = ticker.info or {}
        company_name = info.get("longName") or symbol
        sector = info.get("sector")

        if not sector:
            return jsonify({"error": "Sector not found for this symbol"})

        # ── Find competitors (unchanged from original) ────────────────────────
        

        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        CSV_PATH = os.path.join(BASE_DIR, "invest", "stock_list.csv")
        stocks_df   = pd.read_csv(CSV_PATH)
        all_symbols = [s for s in stocks_df["SYMBOL"].tolist() if s != symbol]
        sample_syms = all_symbols[:min(40, len(all_symbols))]

        competitor_list  = []
        competitor_infos = {}

        def check_competitor(s):
            try:
                t   = yf.Ticker(get_yf_symbol(s))
                inf = t.info or {}
                if inf.get("sector") == sector:
                    return {"symbol": s, "name": inf.get("longName", s), "info": inf}
            except:
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            for res in executor.map(check_competitor, sample_syms):
                if res:
                    competitor_list.append({"symbol": res["symbol"], "name": res["name"]})
                    competitor_infos[res["symbol"]] = res["info"]
                    if len(competitor_list) >= 5:
                        break

        # ── Analysis table (unchanged) ────────────────────────────────────────
        analysis = sorted([
            {
                "symbol":       c["symbol"],
                "marketCap":    competitor_infos[c["symbol"]].get("marketCap"),
                "pe":           competitor_infos[c["symbol"]].get("trailingPE"),
                "profitMargin": competitor_infos[c["symbol"]].get("profitMargins"),
            }
            for c in competitor_list
        ], key=lambda x: x["marketCap"] or 0, reverse=True)

        # ── NEW: Sentiment via HF deployment ──────────────────────────────────
        all_sentiment_symbols = [symbol] + [c["symbol"] for c in competitor_list]

        hf_payloads = {}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(_fetch_hf_sentiment, sym): sym for sym in all_sentiment_symbols}
            for future, sym in futures.items():
                hf_payloads[sym] = future.result()

        # News cards for the main stock only (from HF payload)
        media_sentiment = hf_payloads.get(symbol, {}).get("news", [])
        # Normalize field names
        for a in media_sentiment:
            a["symbol"] = symbol.upper()
            if "learn" in a and "action" not in a:
                a["action"] = a["learn"]
            if "link" in a and "url" not in a:
                a["url"] = a["link"]

        # Build merged chart from all HF chart_data
        sentiment_chart = _merge_chart_data(hf_payloads)

        # Build summary from HF summary field
        sentiment_summary = {
            sym: hf_payloads[sym].get("summary", "neutral")
            for sym in all_sentiment_symbols
        }

        # ── chart_history (unchanged) ─────────────────────────────────────────
        chart_history = []
        try:
            main_yf_sym  = get_yf_symbol(symbol)
            comp_yf_syms = [get_yf_symbol(c["symbol"]) for c in competitor_list]
            dl_symbols   = [main_yf_sym] + comp_yf_syms

            df = yf.download(dl_symbols, period="2y", interval="1d",
                             auto_adjust=True, progress=False)

            if not df.empty:
                close_df = (df["Close"] if isinstance(df.columns, pd.MultiIndex)
                            else df[["Close"]].rename(columns={"Close": main_yf_sym}))
                vol_df   = (df["Volume"] if isinstance(df.columns, pd.MultiIndex)
                            else df[["Volume"]].rename(columns={"Volume": main_yf_sym}))

                if isinstance(close_df, pd.Series):
                    close_df = close_df.to_frame(name=main_yf_sym)
                if isinstance(vol_df, pd.Series):
                    vol_df = vol_df.to_frame(name=main_yf_sym)

                if main_yf_sym in close_df.columns:
                    s50  = close_df[main_yf_sym].rolling(50).mean()
                    s200 = close_df[main_yf_sym].rolling(200).mean()

                    for idx, d in enumerate(df.index):
                        c_main = close_df[main_yf_sym].iloc[idx]
                        if pd.isna(c_main):
                            continue
                        row = {"date": str(d.date()), symbol: float(Decimal(str(float(c_main))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))}
                        if main_yf_sym in vol_df.columns:
                            v = vol_df[main_yf_sym].iloc[idx]
                            row["Volume"] = int(v) if not pd.isna(v) else 0
                        v50, v200 = s50.iloc[idx], s200.iloc[idx]
                        if not pd.isna(v50):  row["50mda"]  = float(Decimal(str(float(v50))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                        if not pd.isna(v200): row["200mda"] = float(Decimal(str(float(v200))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                        for c_obj in competitor_list:
                            cs_yf = get_yf_symbol(c_obj["symbol"])
                            if cs_yf in close_df.columns:
                                cv = close_df[cs_yf].iloc[idx]
                                if not pd.isna(cv):
                                    row[c_obj["symbol"]] = float(Decimal(str(float(cv))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
                        chart_history.append(row)
        except Exception as chart_err:
            print(f"Chart Error: {chart_err}")

        # ── comparison (unchanged) ────────────────────────────────────────────
        comparison = [{"symbol": symbol, "marketCap": info.get("marketCap"),
                       "pe": info.get("trailingPE"), "profitMargin": info.get("profitMargins")}]
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

    # except Exception as e:
    #     return jsonify({"error": str(e)})
    except Exception:
        import traceback
        traceback.print_exc()
        raise

