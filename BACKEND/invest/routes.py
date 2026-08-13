from .portfolio import backfill_sectors
from flask_cors import cross_origin
from flask_caching import Cache
from bs4 import BeautifulSoup
from flask import Blueprint, request, jsonify, Response, current_app, g, redirect, session
from .models import Users, Stock, Transactionhistory
from . import watchlist, portfolio as portfolio_module
from .portfolio import get_dashboard_data, _get_live_price_for_symbol, fetch_ltp_parallel
from .auth import require_user as auth_required
from .options_service import OptionsService
import yfinance as yf
from datetime import datetime, timedelta,timezone, date as date_type
import requests 
from .Agent import get_aria_response
import csv
import io
import json
import boto3
from decimal import Decimal
from invest.cache import cache
import numpy as np
import pandas as pd
import time
import base64
import os
from Endpoints.stock_common import get_yf_symbol
from Endpoints.stock_page import stock_page as stock_page_fallback
from Endpoints.stock_chart import stock_chart as stock_chart_fallback
from Endpoints.stock_headlines import headlines_page as headlines_page_fallback
from Endpoints.stock_competitor import competitors_page as competitors_page_fallback
from Endpoints.stock_dividend import dividend_summary as dividend_summary_fallback
from Endpoints.stock_earnings import earnings_page as stock_earnings_fallback
from Endpoints.stock_financials import financials_page as financials_page_fallback
from Endpoints.stock_options import options_chain as options_chain_fallback
from Endpoints.bse_filings import bse_filings as bse_filings_fallback
from Endpoints.bse_filings import bse_company as bse_company_fallback
from Endpoints.bse_filings import download_filing_pdf as download_filing_pdf_fallback
from Endpoints.stock_Short_interest import short_interest as short_interest_fallback

routes_bp = Blueprint("routes_bp", __name__)

# Recommendations only consider this many stocks right now, matching the
# actual scope of the project (data pipeline, dashboards, etc). Raise this
# when more stocks are added — nothing else needs to change.
NUM_SUPPORTED_STOCKS = 10

HF_BASE_URL=os.getenv("HF_SPACE_URL")
HF_TOKEN      = os.getenv("HF_TOKEN")
HF_HEADERS    = {"Authorization": f"Bearer {HF_TOKEN}"}

# These two routes were originally placed before the Blueprint was defined — moved here.



@routes_bp.route("/refresh-sectors")
def refresh_sectors():
    result = backfill_sectors()
    return result

@routes_bp.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing code"}), 400

    oauth_client_id = os.getenv("OAUTH_CLIENT_ID", "")
    oauth_client_secret = os.getenv("OAUTH_CLIENT_SECRET", "")
    oauth_redirect_uri = os.getenv("OAUTH_REDIRECT_URI", "")
    oauth_token_url = os.getenv("OAUTH_TOKEN_URL", "")
    oauth_userinfo_url = os.getenv("OAUTH_USERINFO_URL", "")

    auth_header = base64.b64encode(
        f"{oauth_client_id}:{oauth_client_secret}".encode()
    ).decode()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": oauth_redirect_uri
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }

    token_res = requests.post(oauth_token_url, data=data, headers=headers)

    tokens = token_res.json()
    id_token = tokens.get("id_token")

    if not id_token:
        return jsonify({"error": "token exchange failed", "details": tokens}), 400

    # Get user profile
    userinfo_res = requests.get(
        oauth_userinfo_url,
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    user = userinfo_res.json()

    # Save session
    session["user"] = {
        "email": user.get("email"),
        "sub": user.get("sub")
    }

    return redirect("http://localhost:3000/dashboard")

#-----------------routes--------------------------------------------

def _batch_get_market_cap_buckets(symbols):
    """Fetch market cap for many symbols at once from the stock-page
    DynamoDB table (reusing data our own pipeline already writes there)
    and bucket each into small/mid/large. Falls back to 'Unknown' for
    any symbol with no data available (today or yesterday)."""
    if not symbols:
        return {}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    def _bucket(market_cap):
        try:
            mc = float(market_cap)
        except (TypeError, ValueError):
            return "Unknown"
        if mc >= 50000 * 1e7:   # roughly >= ₹50,000 Cr
            return "large"
        if mc >= 10000 * 1e7:   # roughly ₹10,000-50,000 Cr
            return "mid"
        return "small"

    def _batch_fetch(date_str, syms):
        found = {}
        try:
            dynamo = get_dynamo()
            syms = list(syms)
            for i in range(0, len(syms), 100):  # batch_get_item caps at 100 keys
                chunk = syms[i:i + 100]
                keys = [
                    {"SYMBOL#<sym>": f"SYMBOL#{s}", "SNAPSHOT#<date>": f"SNAPSHOT#{date_str}"}
                    for s in chunk
                ]
                resp = dynamo.batch_get_item(RequestItems={"stock-page": {"Keys": keys}})
                for item in resp.get("Responses", {}).get("stock-page", []):
                    sym_val = item.get("SYMBOL#<sym>", "").replace("SYMBOL#", "")
                    data = item.get("data", {}) or {}
                    mc = (data.get("key_stats") or {}).get("market_cap")
                    if mc is not None:
                        found[sym_val] = mc
        except Exception as e:
            print(f"[DynamoDB] batch market-cap fetch failed for {date_str}: {e}")
        return found

    buckets = {}
    for sym, mc in _batch_fetch(today, symbols).items():
        buckets[sym] = _bucket(mc)

    missing = [s for s in symbols if s not in buckets]
    if missing:
        for sym, mc in _batch_fetch(yesterday, missing).items():
            buckets[sym] = _bucket(mc)

    for s in symbols:
        buckets.setdefault(s, "Unknown")

    return buckets


@routes_bp.route("/recommendations/<int:userid>", methods=["GET"])
@auth_required
@cross_origin(supports_credentials=True)
def get_recommendations(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    start = time.time()

    try:
        # -------- Load user transactions --------
        txns = Transactionhistory.query.filter_by(userid=userid).all()
        portfolio = [t.stockname for t in txns] if txns else []

        # Real transaction data (quantity/price/timestamp) — the model's
        # user/stock aggregate features need these, not just stock names.
        transactions_payload = [
            {
                "userid": userid,
                "stockname": t.stockname,
                "quantity": t.quantity,
                "price": float(t.price),
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            for t in txns
        ] if txns else []

        # -------- Load Stock Universe --------
        CSV_PATH = os.path.join(os.path.dirname(__file__), "stock_list.csv")
        stocks_df = pd.read_csv(CSV_PATH)

        print("Loaded stocks:", len(stocks_df))

        # ---- Normalize column names ----
        stocks_df = stocks_df.rename(columns={
            "SYMBOL": "stockname",
            "NAME OF COMPANY": "companyname",
            "SECTOR": "sector",
        })

        # ---- Remove stocks already in portfolio ----
        if portfolio:
            stocks_df = stocks_df[~stocks_df["stockname"].isin(portfolio)]

        # ---- Limit universe for performance ----
        # Project currently supports this many stocks end-to-end (data
        # pipeline, dashboards, etc). Bump this constant when more stocks
        # are added — nothing else needs to change.
        candidate_df = stocks_df.head(NUM_SUPPORTED_STOCKS).copy()
        candidate_symbols = candidate_df["stockname"].tolist()

        # ---- Real live prices (cached, parallel — same infra as portfolio pages) ----
        price_df = fetch_ltp_parallel(candidate_symbols)
        price_map = dict(zip(price_df["stockname"], price_df["price"]))
        candidate_df["price"] = candidate_df["stockname"].map(price_map)

        # Drop stocks we couldn't get a real price for — a missing/zero
        # price would be worse for the model than just excluding the row.
        candidate_df = candidate_df[candidate_df["price"].notna()]

        # ---- Real market-cap bucket (from our own DynamoDB pipeline) ----
        bucket_map = _batch_get_market_cap_buckets(candidate_df["stockname"].tolist())
        candidate_df["market_cap_bucket"] = candidate_df["stockname"].map(bucket_map).fillna("Unknown")

        # -------- Build HF Payload --------
        payload = {
            "transactions": transactions_payload,
            "stock_universe": candidate_df.to_dict(orient="records")
        }

        # -------- Call HuggingFace Model --------
        hf_res = requests.post(
            f"{HF_BASE_URL}/recommend",
            json=payload,
            timeout=30
        )

        model_json = hf_res.json()

        # HF may return list or wrapped object
        recs = (
            model_json
            if isinstance(model_json, list)
            else model_json.get("recommendations", [])
        )

        # -------- Ensure TOP-6 only --------
        recs = recs[:6]

        # -------- If model returned nothing → fallback top 6 --------
        if not recs:
            fallback = (
                candidate_df
                    .head(6)
                    .assign(
                        buy_prob=0.50,      # neutral confidence
                        source="fallback"
                    )
                    .to_dict(orient="records")
            )

            return jsonify({
                "count": len(fallback),
                "source": "fallback",
                "recommendations": fallback,
                "latency_ms": round((time.time() - start) * 1000, 2)
            })

        # -------- Normal Model Response --------
        return jsonify({
            "count": len(recs),
            "source": "model",
            "recommendations": recs,
            "latency_ms": round((time.time() - start) * 1000, 2)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#---------------Request timing ----------------
@routes_bp.before_request
def start_timer():
    g.start_time = time.perf_counter()

@routes_bp.after_request
def log_request_time(response):
    if hasattr(g, "start_time"):
        elapsed = time.perf_counter() - g.start_time
        print(f"[TIMER] {request.method} {request.path} took {elapsed:.3f}s")
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
    return response

# ---------------- Load stock list ----------------
try:
    CSV_PATH = os.path.join(os.path.dirname(__file__), "stock_list.csv")
    stock_df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
except (FileNotFoundError, pd.errors.EmptyDataError):
    stock_df = pd.DataFrame(columns=["SYMBOL", "NAME OF COMPANY"])

@routes_bp.route("/")
def index():
    return jsonify({"status": "ok", "message": "API is running"})

@routes_bp.route("/autocomplete")
def autocomplete():
    q = (request.args.get("q") or "").strip().upper()
    if not q or stock_df.empty: return jsonify([])

    mask = stock_df["SYMBOL"].str.upper().str.startswith(q) | stock_df["NAME OF COMPANY"].str.upper().str.startswith(q)
    matches = stock_df[mask].head(10)
    results = matches[["SYMBOL", "NAME OF COMPANY"]].to_dict(orient="records")
    return jsonify(results)

# ---------------- Markets Overview (all stocks with sparkline) ----------------
@routes_bp.route("/markets", methods=["GET"])
@cross_origin(supports_credentials=True)
@cache.cached(timeout=300, key_prefix="markets_overview")  # cache 5 minutes
def markets_overview():
    """
    Returns all stocks from stock_list.csv with:
    - live price, change, change_percent
    - 30-day close price sparkline array
    - sector, industry, company name
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    def fetch_stock_data(row):
        symbol   = str(row.get("SYMBOL", "")).strip()
        name     = str(row.get("NAME OF COMPANY", symbol)).strip()
        sector   = str(row.get("SECTOR", "")).strip()
        industry = str(row.get("INDUSTRY", "")).strip()
        yf_sym   = f"{symbol}.NS"
        try:
            ticker = yf.Ticker(yf_sym)
            hist   = ticker.history(period="30d", auto_adjust=True)
            if hist.empty:
                return None
            close = hist["Close"].dropna()
            if len(close) < 2:
                return None
            sparkline     = [round(float(v), 2) for v in close.tolist()]
            current_price = sparkline[-1]
            prev_price    = sparkline[-2]
            change        = round(current_price - prev_price, 2)
            change_pct    = round((change / prev_price) * 100, 2) if prev_price else 0
            info       = ticker.info or {}
            market_cap = info.get("marketCap")
            if market_cap:
                if market_cap >= 1_000_000_000_000:
                    market_cap_display = f"₹{round(market_cap/1_000_000_000_000,2)}T"
                elif market_cap >= 1_000_000_000:
                    market_cap_display = f"₹{round(market_cap/1_000_000_000,2)}B"
                else:
                    market_cap_display = f"₹{round(market_cap/1_000_000,2)}M"
            else:
                market_cap_display = "—"
            return {
                "symbol":        symbol,
                "name":          name,
                "sector":        sector,
                "industry":      industry,
                "price":         current_price,
                "change":        change,
                "change_pct":    change_pct,
                "market_cap":    market_cap_display,
                "sparkline":     sparkline,
                "is_positive":   change_pct >= 0,
            }
        except Exception as exc:
            print(f"[MARKETS] Error fetching {symbol}: {exc}")
            return None
    if stock_df.empty:
        return jsonify([])
    rows = stock_df.to_dict(orient="records")
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_stock_data, r): r for r in rows}
        for future in as_completed(futures):
            data = future.result()
            if data:
                results.append(data)
    # Sort by market cap descending (keep original order for ties)
    results.sort(key=lambda x: x["symbol"])
    return jsonify(results)


@routes_bp.route("/get_stock_id/<symbol>", methods=["GET"])
def get_stock_id(symbol):
    try:
        from .models import Stock  # Changed from Stocks to Stock
        stock = Stock.query.filter_by(stock_symbol=symbol).first()
        if stock:
            return jsonify({"stock_id": stock.stock_id, "symbol": symbol})
        else:
            return jsonify({"error": "Stock not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching stock ID for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/get-price/<symbol>", methods=["GET"])
def get_price(symbol):
    price, change, change_percent = _get_live_price_for_symbol(symbol)
    if price is None: return jsonify({"error": "Price not available"}), 404
    return jsonify({"symbol": symbol, "price": price, "change": change, "change_percent": change_percent})

# ---------------- Wallet ----------------
@routes_bp.route("/get_wallet/<int:userid>", methods=["GET"])
@auth_required
@cross_origin(supports_credentials=True)
def get_wallet_route(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    try:
        user = Users.query.get(userid)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"money": float(user.money or 0)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Watchlist Routes ----------------
@routes_bp.route("/add_to_watchlist", methods=["POST"])
@auth_required
@cross_origin(supports_credentials=True)
def add_to_watchlist_route():
    data = request.get_json() or {}
    body_userid = data.get("userid")
    if body_userid is not None and g.current_userid != int(body_userid):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return watchlist.add_to_watchlist() # Direct return, no extra wrapping
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Updated Watchlist Route ---
@routes_bp.route("/get_watchlist/<int:userid>", methods=["GET"])
@auth_required
@cross_origin(supports_credentials=True)
def get_watchlist_route(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    try:
        response = watchlist.get_watchlist(userid)

        if not response:
            return jsonify([])

        stocks = response.get_json()

        if not stocks or not isinstance(stocks, list):
            return jsonify([])

        for stock in stocks:
            symbol = stock.get("stock_symbol")
            if not symbol:
                continue

            meta = fetch_stock_meta(symbol)

            stock["logo_url"] = meta["logo_url"] if meta else None
            stock["company_name"] = meta["company_name"] if meta else symbol

        return jsonify(stocks)

    except Exception as e:
        print("WATCHLIST ERROR:", e)
        return jsonify({"error": str(e)}), 500


# In routes.py
@routes_bp.route("/remove_from_watchlist/<int:userid>/<int:stock_id>", methods=["DELETE"])
@auth_required
@cross_origin(supports_credentials=True)
def remove_from_watchlist_route(userid, stock_id):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    try:
        return watchlist.remove_from_watchlist(userid, stock_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/buy_from_watchlist", methods=["POST"])
@auth_required
@cross_origin(supports_credentials=True)
def buy_from_watchlist_route():
    data = request.get_json() or {}
    body_userid = data.get("userid")
    if body_userid is not None and g.current_userid != int(body_userid):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return watchlist.buy_from_watchlist()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#--- Updated Portfolio Route ---
@routes_bp.route("/portfolio/<int:userid>", methods=["GET"])
@auth_required
@cross_origin(supports_credentials=True)
def get_portfolio(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    try:
        holdings = portfolio_module.gettingfromdb(userid)

        for item in holdings:
            base_symbol = (
                item["stockname"]
                .upper()
                .replace(".NS", "")
                .replace(".BO", "")
            )
            ticker = yf.Ticker(f"{base_symbol}.NS")
            item["logo_url"] = ticker.info.get("logo_url")

        return jsonify(holdings)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/buy", methods=["POST"])
@auth_required
def buystock():
    data = request.get_json() or {}
    body_userid = data.get("userid")
    if body_userid is not None and g.current_userid != int(body_userid):
        return jsonify({"error": "Forbidden"}), 403
    try:
        result = portfolio_module.buy(
            userid=int(data["userid"]),
            stockname=data["stockname"],
            qty=int(data["qty"]),
            price=float(data["price"]),
            companyname=data["companyname"]
        )
        return jsonify(result)
    except portfolio_module.PriceMismatchError as e:
        return jsonify({"error": str(e)}), 400
    except portfolio_module.ServiceUnavailableError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/sell", methods=["POST"])
@auth_required
def sell_stock():
    data = request.get_json() or {}
    body_userid = data.get("userid")
    if body_userid is not None and g.current_userid != int(body_userid):
        return jsonify({"error": "Forbidden"}), 403
    try:
        result = portfolio_module.sell(
            userid=int(data["userid"]),
            stockname=data["stockname"],
            companyname=data["companyname"],
            qty=int(data["qty"]),
            price=float(data["price"])
        )
        return jsonify(result)
    except portfolio_module.PriceMismatchError as e:
        return jsonify({"error": str(e)}), 400
    except portfolio_module.ServiceUnavailableError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Stock Metadata (Logos & Info) ----------------

@routes_bp.route("/stock-meta/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_meta_route(symbol):
    meta = fetch_stock_meta(symbol)

    if not meta:
        return jsonify({"error": "Stock details not found"}), 404

    return jsonify({
        "symbol": meta["symbol"],
        "companyName": meta["company_name"],
        "logoUrl": meta["logo_url"],
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "summary": meta.get("description"),
        "website": meta.get("website")
    })

# ---------------- Stock Prediction (OFFLOADED TO HUGGING FACE) ---------------
@routes_bp.route("/predict-stock/<symbol>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def predict_stock(symbol):
    """
    Clean proxy to the HF stock-ai-worker's /predict/{symbol} endpoint.
    No calculation happens here — every field in the response (historical_chart,
    forecast_chart, technical_indicators, trend_probability, risk_score,
    ai_signal, model_accuracy, etc.) comes directly from the trained model on HF.
    """
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    search_symbol = symbol.upper()

    try:
        hf_res = requests.get(f"{HF_BASE_URL}/predict/{search_symbol}", timeout=120)
        hf_data = hf_res.json()

        if hf_res.status_code != 200 or hf_data.get("error"):
            return jsonify({
                "error": hf_data.get("error", "Prediction unavailable"),
                "status": hf_res.status_code
            }), hf_res.status_code if hf_res.status_code != 200 else 502

        historical = hf_data.get("historical_chart", [])
        forecast = hf_data.get("forecast_chart", [])

        hist_dates = [h.get("date") for h in historical]
        hist_closes = [h.get("close") for h in historical]
        fore_dates = [f.get("date") for f in forecast]
        fore_preds = [f.get("predicted_price") for f in forecast]

        if historical and forecast:
            dates = hist_dates + fore_dates
            actual = hist_closes + [None] * len(forecast)
            predictions = [None] * (len(historical) - 1) + [hist_closes[-1]] + fore_preds
        else:
            dates, actual, predictions = [], [], []

        hf_data.update({
            "confidence": hf_data.get("confidence_score", 0),
            "change_pct": hf_data.get("predicted_change_percent", 0),
            "dates": dates,
            "actual": actual,
            "predictions": predictions,
        })

        return jsonify(hf_data), 200

    except requests.exceptions.Timeout:
        return jsonify({"error": "Model service took too long to respond"}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Model service connection error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- Learnings (OFFLOADED TO HUGGING FACE) ----------------
# In your EC2 routes.py

@routes_bp.route("/learnings/news", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_learnings_news():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
        
    try:
        # 1. Update this to your ACTUAL Hugging Face Space URL
        # Note: Use the 'Direct' URL (ends in .hf.space) not the UI URL
        HF_SPACE_URL =f"{HF_BASE_URL}/news"
        
        # 2. INCREASE TIMEOUT to 30 seconds
        # Summarizing and RAG takes time on HF's CPU
        response = requests.get(HF_SPACE_URL, timeout=30)
        
        if response.status_code == 200:
            return jsonify(response.json()), 200
        else:
            return jsonify({
                "error": "Hugging Face is waking up or busy", 
                "status": response.status_code
            }), response.status_code

    except requests.exceptions.Timeout:
        return jsonify({"error": "Hugging Face took too long to analyze news"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Transactions ----------------
@routes_bp.route("/transactions/<int:userid>", methods=["GET"])
@auth_required
def get_transactions(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    try:
        txns = Transactionhistory.query.filter_by(userid=userid).all()
        if not txns: return jsonify([])
        result = [
            {
                "userid": t.userid, "stockname": t.stockname,
                "quantity": t.quantity, "price": t.price,
                "type": t.transactiontype,
                "date": t.timestamp.strftime("%Y-%m-%d %H:%M:%S") if t.timestamp else None
            }
            for t in txns
        ]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/dashboard/<int:userid>/export", methods=["GET"])
@auth_required
def export_dashboard_csv(userid):
    if g.current_userid != userid:
        return jsonify({"error": "Forbidden"}), 403
    data = get_dashboard_data(userid)
    if "error" in data: return jsonify(data), 404

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Wallet", data["wallet"]])
    cw.writerow([])
    cw.writerow(["Progress Score", data["metrics"].get("progress_score", "")])
    cw.writerow(["Level", data["metrics"].get("level", "")])
    cw.writerow(["Login Streak", data["metrics"].get("login_streak", "")])
    cw.writerow([])

    cw.writerow(["Company", "Stock", "Quantity", "Avg Buy Price", "Invested", "LTP", "Now Value", "P/L"])
    for p in data["portfolio"]:
        cw.writerow([
            p["companyname"], p["stockname"], p["totalquantity"],
            p["averagebuyprice"], p["totalinvested"],
            p["ltp"], p["nowvalue"], p["profitorloss"]
        ])
    cw.writerow([])
    cw.writerow(["Type", "Stock", "Price", "Date"])
    for t in data["transactions"]:
        cw.writerow([t["type"], t["stockname"], t["price"], t["date"]])

    output = si.getvalue()
    return Response(output, mimetype="text/csv",
       headers={"Content-Disposition": "attachment;filename=dashboard_full_export.csv"})

#------------------------------------------------------------------------------------------------------------
def fetch_stock_meta(symbol):
    try:
        base_symbol = symbol.upper()

        ticker = yf.Ticker(get_yf_symbol(base_symbol))
        info = ticker.info or {}

        return {
            "symbol": base_symbol,
            "company_name": info.get("longName", base_symbol),
            "logo_url": info.get("logo_url"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "description": info.get("longBusinessSummary"),
            "website": info.get("website")
        }

    except Exception as e:
        return {
            "symbol": symbol,
            "company_name": symbol,
            "logo_url": None
        }

@routes_bp.route("/agent/chat", methods=["POST"])
@cross_origin(supports_credentials=True)
def aria_chat():
    """
    ARIA AI Agent — Stock Q&A endpoint.
 
    Request body (JSON):
    {
        "userid":         1,
        "message":        "Should I buy Infosys?",
        "current_symbol": "INFY",    <- stock on screen, "" if not on stock page
        "history": [                 <- last 3 turns, empty list on first message
            {"role": "user",      "content": "What is PE ratio?"},
            {"role": "assistant", "content": "PE ratio is ..."}
        ]
    }
 
    Response (JSON):
    {
        "reply":  "ARIA's answer here",
        "status": "ok"
    }
 
    Error response:
    {
        "error":  "description",
        "status": "error"
    }
    """
    try:
        data = request.get_json(force=True)
 
        # ── Validate required fields ─────────────────────────────────────────
        userid = data.get("userid")
        message = (data.get("message") or "").strip()
 
        if not userid:
            return jsonify({"error": "userid is required", "status": "error"}), 400
 
        if not message:
            return jsonify({"error": "message cannot be empty", "status": "error"}), 400
 
        # ── Optional fields with safe defaults ───────────────────────────────
        current_symbol = (data.get("current_symbol") or "").strip()
        history        = data.get("history") or []
 
        # Sanitise history — only keep valid turns
        clean_history = [
            turn for turn in history
            if isinstance(turn, dict)
            and turn.get("role") in ("user", "assistant")
            and turn.get("content", "").strip()
        ]
 
        # ── Call ARIA pipeline ───────────────────────────────────────────────
        reply = get_aria_response(
            userid=int(userid),
            message=message,
            current_symbol=current_symbol,
            history=clean_history
        )
 
        return jsonify({"reply": reply, "status": "ok"})
 
    except Exception as e:
        import traceback
        traceback.print_exc()   # prints full error in your terminal
        return jsonify({"error": str(e), "status": "error"}), 500
 

_dynamo = None
 
def get_dynamo():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION"))
    return _dynamo
 
 
def _is_fresh(fetched_at):
    """For stock-chart / stock-financials only (fixed key, no date in SK).
    Accept the item if it was fetched today or yesterday (UTC)."""
    if not fetched_at:
        return False
    try:
        fetched_date = fetched_at[:10]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        return fetched_date in (today, yesterday)
    except Exception:
        return False


def _from_dynamo(obj):
    """Boto3 returns numbers from DynamoDB as Decimal. Flask's jsonify()
    can't serialize Decimal natively and silently stringifies it instead,
    which breaks any frontend code expecting a real number (e.g. .toFixed()).
    Convert Decimal back to int/float before returning the response."""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_dynamo(i) for i in obj]
    return obj


@routes_bp.route("/stock-page/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_page(symbol):
    symbol = symbol.upper()
    try:
        table = get_dynamo().Table("stock-page")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        for d in (today, yesterday):
            resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "SNAPSHOT#<date>": f"SNAPSHOT#{d}"})
            item = resp.get("Item")
            if item and item.get("data"):
                return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock-page read failed for {symbol}: {e}")
    return stock_page_fallback(symbol)

@routes_bp.route("/stock-chart/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_chart(symbol):
    symbol = symbol.upper()
    period = request.args.get("period", "1y")  
    interval = request.args.get("interval", "1d")  
    
    try:
        table = get_dynamo().Table("stock-chart")
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "CHART#<period>#<interval>": f"CHART#{period}#{interval}"})
        item = resp.get("Item")
        if item and item.get("data"):
            return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock-chart read failed for {symbol}: {e}")
    return stock_chart_fallback(symbol)

@routes_bp.route("/stock-earnings/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_earnings(symbol):
    symbol = symbol.upper()
  
    try:
        table = get_dynamo().Table("stock-earnings")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        for d in (today, yesterday, "LATEST"):
            sk = f"EARNINGS#{d}" if d != "LATEST" else "LATEST"
            resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "EARNINGS#<date>": sk})
            item = resp.get("Item")
            if item and item.get("data"):
                data = _from_dynamo(item["data"])
                # Skip cached error payloads (stored before fix was applied)
                if isinstance(data, dict) and not data.get("error") and data.get("success") is not False:
                    return jsonify(data)
    except Exception as e:
        print(f"[DynamoDB] stock-earnings read failed for {symbol}: {e}")
    return stock_earnings_fallback(symbol)     

@routes_bp.route("/stock-dividend/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_dividend(symbol):
    symbol = symbol.upper()
  
    try:
        table = get_dynamo().Table("stock-dividend-summary")
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "DIVIDEND_SUMMARY#<date>": f"DIVIDEND_SUMMARY#{date_type.today().strftime('%Y-%m-%d')}"})
        item = resp.get("Item")

        if not item:
            resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "DIVIDEND_SUMMARY#<date>": f"DIVIDEND_SUMMARY#{(date_type.today()-timedelta(days=2)).strftime('%Y-%m-%d')}"})
            item = resp.get("Item")

        if item and item.get("data"):
            return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock-dividend read failed for {symbol}: {e}")
    return dividend_summary_fallback(symbol)



@routes_bp.route("/stock-bse-filings/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_bse_filings(symbol):
    symbol = symbol.upper()
    from_date = request.args.get("from_date", "").strip()
    to_date = request.args.get("to_date", "").strip()
    category_filter = request.args.get("category", "").strip()
    results_only = request.args.get("results_only", "false").lower() == "true"
    limit = request.args.get("limit")

    # Primary Option: Always try DynamoDB first
    try:
        table = get_dynamo().Table("bse-filings")
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "FILINGS#<date>": "LATEST"})
        item = resp.get("Item")
        if item and item.get("data"):
            data = _from_dynamo(item["data"])
            filings = data.get("filings", [])

            # Filter DynamoDB filings in python if date or category filters are provided
            if from_date or to_date or category_filter or results_only:
                filtered = []
                for f in filings:
                    f_date = (f.get("date") or "")[:10]
                    if from_date and f_date and f_date < from_date:
                        continue
                    if to_date and f_date and f_date > to_date:
                        continue
                    if results_only and not (f.get("is_result") or f.get("quarter")):
                        continue
                    if category_filter and (f.get("category") or "").lower() != category_filter.lower():
                        continue
                    filtered.append(f)
                filings = filtered

            if limit:
                try:
                    filings = filings[:int(limit)]
                except ValueError:
                    pass

            data["filings"] = filings
            data["count"] = len(filings)
            return jsonify(data)
    except Exception as e:
        print(f"[DynamoDB] stock-bse-filings read failed for {symbol}: {e}")

    # Fallback Option: Only call live BSE API if DynamoDB is unavailable or missing data
    return bse_filings_fallback(symbol)

@routes_bp.route("/bse-company/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def bse_company(symbol):
    return bse_company_fallback(symbol)



@routes_bp.route("/bse-filings/<symbol>/download", methods=["GET"])
@cross_origin(supports_credentials=True)
def download_filing_pdf(symbol):
    return download_filing_pdf_fallback(symbol)

@routes_bp.route("/stock-competitors/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_competitors(symbol):
    symbol = symbol.upper()
  
    try:
        table = get_dynamo().Table("stock-competitors")
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "COMPETITORS#<date>": f"COMPETITORS#{date_type.today().strftime('%Y-%m-%d')}"})
        item = resp.get("Item")

        if not item:
            resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "COMPETITORS#<date>": f"COMPETITORS#{(date_type.today()-timedelta(days=2)).strftime('%Y-%m-%d')}"})
            item = resp.get("Item")

        if item and item.get("data"):
            return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock-competitors read failed for {symbol}: {e}")
    return competitors_page_fallback(symbol)


@routes_bp.route("/stock-financials/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_financials(symbol):
    symbol = symbol.upper()
    try:
        table = get_dynamo().Table("stock-financials")
        pk = f"SYMBOL#{symbol}"
        annual_resp = table.get_item(Key={"SYMBOL#<sym>": pk, "FINANCIALS#<period_type>": "FINANCIALS#annual"})
        quarterly_resp = table.get_item(Key={"SYMBOL#<sym>": pk, "FINANCIALS#<period_type>": "FINANCIALS#quarterly"})
        annual_item = annual_resp.get("Item")
        quarterly_item = quarterly_resp.get("Item")

        if (annual_item and quarterly_item
                and _is_fresh(annual_item.get("fetched_at"))
                and _is_fresh(quarterly_item.get("fetched_at"))):
            merged = dict(annual_item["data"])
            merged.update(quarterly_item["data"])
            return jsonify(_from_dynamo(merged))
    except Exception as e:
        print(f"[DynamoDB] stock-financials read failed for {symbol}: {e}")
    return financials_page_fallback(symbol)


@routes_bp.route("/stock-headlines/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_headlines(symbol):
    symbol = symbol.upper()
 
    try:
        table = get_dynamo().Table("stock-headlines")
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "HEADLINES#<date>": "LATEST"})
        item = resp.get("Item")

        if item and item.get("data"):
            return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock headlines read failed for {symbol}: {e}")
    return headlines_page_fallback(symbol)

@routes_bp.route("/stock-options/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_options(symbol):
    symbol = symbol.upper()
    try:
        table = get_dynamo().Table("stock-options")
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "OPTIONS#<date>": "LATEST"})
        item = resp.get("Item")  

        if item and item.get("data"):
            return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock-options read failed for {symbol}: {e}")
    return options_chain_fallback(symbol)


@routes_bp.route("/stock-short-interest/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_short_interest(symbol):
    symbol = symbol.upper()

    try:
        table = get_dynamo().Table("stock-short-interest")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        for d in (today, yesterday):
            resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "SI#<date>": f"SI#{d}"})
            item = resp.get("Item")
            if item and item.get("data"):
                return jsonify(_from_dynamo(item["data"]))
    except Exception as e:
        print(f"[DynamoDB] stock-short-interest read failed for {symbol}: {e}")
    return short_interest_fallback(symbol)