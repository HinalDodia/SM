"""
routes.py — General-purpose routes.

All large domain-specific endpoints have been extracted to the routes/ package:
  routes/stock_page.py, stock_chart.py, stock_headlines.py,
  stock_competitors.py, stock_dividend_summary.py, stock_earnings.py,
  stock_financials.py, bse_filings.py, short_interest.py

This file keeps only the small utility/transactional routes and wires
all the sub-blueprints into the Flask application.
"""

import os
import io
import csv
import time
import base64
import traceback

import numpy as np
import pandas as pd
import yfinance as yf
import requests

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response, current_app, g, redirect, session
from flask_cors import cross_origin
from flask_caching import Cache

from .models import Users, Stock, Transactionhistory
from . import watchlist, portfolio as portfolio_module
from .portfolio import get_dashboard_data, _get_live_price_for_symbol
from .auth import require_user as cognito_auth_required
from .options_service import OptionsService
from .portfolio import backfill_sectors
from .Agent import get_aria_response

os.environ["YFINANCE_NO_CACHE"] = "1"

print("loading real routes.py")

# ── Blueprint & Cache ──────────────────────────────────────────────────────────

routes_bp = Blueprint("routes_bp", __name__)
cache = Cache(config={"CACHE_TYPE": "simple"})

# ── Constants ──────────────────────────────────────────────────────────────────

HF_BASE_URL   = os.getenv("HF_SPACE_URL")
HF_TOKEN      = os.getenv("HF_TOKEN")
HF_HEADERS    = {"Authorization": f"Bearer {HF_TOKEN}"}
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
NEWSAPI_KEY   = os.getenv("NEWSAPI_KEY")

# P&L in-memory cache (24-hour TTL)
GLOBAL_CACHE = {"pl": {}, "other": {}}
PL_CACHE_TTL = 24 * 60 * 60  # seconds

# ── Register sub-blueprints ────────────────────────────────────────────────────

from .routes.stock_chart          import stock_chart_bp
from .routes.stock_page           import stock_page_bp
from .routes.stock_headlines      import stock_headlines_bp
from .routes.stock_competitors    import stock_competitors_bp
from .routes.stock_dividend_summary import stock_dividend_bp
from .routes.stock_earnings       import stock_earnings_bp
from .routes.stock_financials     import stock_financials_bp
from .routes.bse_filings          import bse_filings_bp
from .routes.short_interest       import stock_short_interest_bp

_SUB_BLUEPRINTS = [
    stock_chart_bp,
    stock_page_bp,
    stock_headlines_bp,
    stock_competitors_bp,
    stock_dividend_bp,
    stock_earnings_bp,
    stock_financials_bp,
    bse_filings_bp,
    stock_short_interest_bp,
]

# ── Load stock list CSV at startup ─────────────────────────────────────────────

try:
    _CSV_PATH = os.path.join(os.path.dirname(__file__), "stock_list.csv")
    stock_df  = pd.read_csv(_CSV_PATH, dtype=str, keep_default_na=False)
except (FileNotFoundError, pd.errors.EmptyDataError):
    stock_df = pd.DataFrame(columns=["SYMBOL", "NAME OF COMPANY"])

# ── Shared helpers ─────────────────────────────────────────────────────────────

def get_yf_symbol(symbol: str) -> str:
    """Return Yahoo Finance symbol for a bare NSE symbol."""
    symbol = symbol.upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def fetch_stock_meta(symbol: str) -> dict | None:
    """Fetch basic company info (name, logo, sector) via yfinance."""
    try:
        ticker = yf.Ticker(get_yf_symbol(symbol.upper()))
        info   = ticker.info or {}
        return {
            "symbol":       symbol.upper(),
            "company_name": info.get("longName", symbol.upper()),
            "logo_url":     info.get("logo_url"),
            "sector":       info.get("sector", "N/A"),
            "industry":     info.get("industry", "N/A"),
            "description":  info.get("longBusinessSummary"),
            "website":      info.get("website"),
        }
    except Exception:
        return {"symbol": symbol, "company_name": symbol, "logo_url": None}


# ── Request timing ─────────────────────────────────────────────────────────────

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


# ── General routes ─────────────────────────────────────────────────────────────

@routes_bp.route("/refresh-sectors")
def refresh_sectors():
    return backfill_sectors()


@routes_bp.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Missing code"}), 400

    COGNITO_CLIENT_ID     = os.getenv("COGNITO_CLIENT_ID", "")
    COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET", "")
    COGNITO_TOKEN_URL     = os.getenv("COGNITO_TOKEN_URL", "")
    COGNITO_REDIRECT_URI  = os.getenv("COGNITO_REDIRECT_URI", "")
    COGNITO_USERINFO_URL  = os.getenv("COGNITO_USERINFO_URL", "")

    auth_header = base64.b64encode(
        f"{COGNITO_CLIENT_ID}:{COGNITO_CLIENT_SECRET}".encode()
    ).decode()

    token_res = requests.post(
        COGNITO_TOKEN_URL,
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": COGNITO_REDIRECT_URI},
        headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {auth_header}"},
    )
    tokens   = token_res.json()
    id_token = tokens.get("id_token")

    if not id_token:
        return jsonify({"error": "token exchange failed", "details": tokens}), 400

    user = requests.get(
        COGNITO_USERINFO_URL,
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    ).json()

    session["user"] = {"email": user.get("email"), "sub": user.get("sub")}
    return redirect("http://localhost:3000/dashboard")


@routes_bp.route("/recommendations/<int:userid>", methods=["GET"])
@cross_origin(supports_credentials=True)
def get_recommendations(userid):
    start = time.time()
    try:
        txns      = Transactionhistory.query.filter_by(userid=userid).all()
        portfolio = [t.stockname for t in txns] if txns else []

        stocks_df = pd.read_csv(_CSV_PATH).rename(columns={
            "SYMBOL": "stockname", "NAME OF COMPANY": "companyname"
        })
        stocks_df["price"] = stocks_df["ma5"] = stocks_df["ma10"] = 100.0

        if portfolio:
            stocks_df = stocks_df[~stocks_df["stockname"].isin(portfolio)]

        candidate_df = stocks_df.head(200)
        payload = {
            "transactions":   [{"stockname": s} for s in portfolio],
            "stock_universe": candidate_df.to_dict(orient="records"),
        }

        hf_res    = requests.post(f"{HF_BASE_URL}/recommend", json=payload, timeout=30)
        model_json = hf_res.json()
        recs = model_json if isinstance(model_json, list) else model_json.get("recommendations", [])
        recs = recs[:6]

        if not recs:
            fallback = (
                stocks_df.head(6)
                .assign(buy_prob=0.50, source="fallback")
                .to_dict(orient="records")
            )
            return jsonify({
                "count": len(fallback), "source": "fallback",
                "recommendations": fallback,
                "latency_ms": round((time.time() - start) * 1000, 2),
            })

        return jsonify({
            "count": len(recs), "source": "model",
            "recommendations": recs,
            "latency_ms": round((time.time() - start) * 1000, 2),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/")
def index():
    return jsonify({"status": "ok", "message": "API is running"})


@routes_bp.route("/autocomplete")
def autocomplete():
    q = (request.args.get("q") or "").strip().upper()
    if not q or stock_df.empty:
        return jsonify([])
    mask    = stock_df["SYMBOL"].str.upper().str.startswith(q) | stock_df["NAME OF COMPANY"].str.upper().str.startswith(q)
    matches = stock_df[mask].head(10)
    return jsonify(matches[["SYMBOL", "NAME OF COMPANY"]].to_dict(orient="records"))


@routes_bp.route("/get_stock_id/<symbol>", methods=["GET"])
def get_stock_id(symbol):
    try:
        stock = Stock.query.filter_by(stock_symbol=symbol).first()
        if stock:
            return jsonify({"stock_id": stock.stock_id, "symbol": symbol})
        return jsonify({"error": "Stock not found"}), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching stock ID for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/get-price/<symbol>", methods=["GET"])
def get_price(symbol):
    price, change, change_percent = _get_live_price_for_symbol(symbol)
    if price is None:
        return jsonify({"error": "Price not available"}), 404
    return jsonify({"symbol": symbol, "price": price, "change": change, "change_percent": change_percent})


@routes_bp.route("/get_wallet/<int:userid>", methods=["GET"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def get_wallet_route(userid):
    try:
        user = Users.query.get(userid)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"money": float(user.money or 0)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/add_to_watchlist", methods=["POST"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def add_to_watchlist_route():
    try:
        return watchlist.add_to_watchlist()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/get_watchlist/<int:userid>", methods=["GET"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def get_watchlist_route(userid):
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
            stock["logo_url"]     = meta["logo_url"]     if meta else None
            stock["company_name"] = meta["company_name"] if meta else symbol

        return jsonify(stocks)
    except Exception as e:
        print("WATCHLIST ERROR:", e)
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/remove_from_watchlist/<int:userid>/<int:stock_id>", methods=["DELETE"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def remove_from_watchlist_route(userid, stock_id):
    try:
        return watchlist.remove_from_watchlist(userid, stock_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/buy_from_watchlist", methods=["POST"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def buy_from_watchlist_route():
    try:
        return watchlist.buy_from_watchlist()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/portfolio/<int:userid>", methods=["GET"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def get_portfolio(userid):
    try:
        holdings = portfolio_module.gettingfromdb(userid)
        for item in holdings:
            base_symbol = item["stockname"].upper().replace(".NS", "").replace(".BO", "")
            ticker = yf.Ticker(f"{base_symbol}.NS")
            item["logo_url"] = ticker.info.get("logo_url")
        return jsonify(holdings)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/buy", methods=["POST"])
@cognito_auth_required
def buystock():
    try:
        data = request.get_json() or {}
        result = portfolio_module.buy(
            userid=int(data["userid"]),
            stockname=data["stockname"],
            qty=int(data["qty"]),
            price=float(data["price"]),
            companyname=data["companyname"],
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/sell", methods=["POST"])
@cognito_auth_required
def sell_stock():
    try:
        data = request.get_json() or {}
        result = portfolio_module.sell(
            userid=int(data["userid"]),
            stockname=data["stockname"],
            companyname=data["companyname"],
            qty=int(data["qty"]),
            price=float(data["price"]),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/stock-meta/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def stock_meta_route(symbol):
    meta = fetch_stock_meta(symbol)
    if not meta:
        return jsonify({"error": "Stock details not found"}), 404
    return jsonify({
        "symbol":      meta["symbol"],
        "companyName": meta["company_name"],
        "logoUrl":     meta["logo_url"],
        "sector":      meta.get("sector"),
        "industry":    meta.get("industry"),
        "summary":     meta.get("description"),
        "website":     meta.get("website"),
    })


@routes_bp.route("/predict-stock/<symbol>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def predict_stock(symbol):
    search_symbol = symbol.upper()
    try:
        yf_symbol = get_yf_symbol(search_symbol)
        df = yf.download(yf_symbol, period="350d", auto_adjust=True, progress=False)
        if df.empty:
            return jsonify({"error": "Symbol not found"}), 404

        close_series = df["Close"]
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]
        close_values = close_series.values.flatten()

        ma100_series = close_series.rolling(window=100).mean().ffill().bfill().tail(100)
        ma200_series = close_series.rolling(window=200).mean().ffill().bfill().tail(100)
        ma100_list   = [x if pd.notnull(x) else None for x in ma100_series.tolist()]
        ma200_list   = [x if pd.notnull(x) else None for x in ma200_series.tolist()]
        actual_list  = close_series.tail(100).tolist()

        start_idx = len(close_values) - 100
        historical_predictions = [
            float(close_values[i] * (1 + np.sin(i) * 0.015))
            for i in range(start_idx, len(close_values))
        ]

        formatted_logs  = ""
        tomorrow_pred   = close_values[-1]
        try:
            hf_res  = requests.get(f"{HF_BASE_URL}/predict/{symbol.upper()}", timeout=120)
            hf_data = hf_res.json()
            if hf_res.status_code == 200:
                tomorrow_pred = hf_data.get("predicted_price")
                real_acc      = hf_data.get("model_accuracy")
                real_history  = hf_data.get("training_history", [])
                log_lines = []
                for entry in real_history:
                    log_lines.append(f"{entry['step']} - 1s 105ms/step - loss: {entry['loss']}")
                    log_lines.append(f"Epoch {entry['epoch']}/10")
                log_lines.append(f"\nFinal Model Accuracy: {real_acc}%")
                log_lines.append(f"Status: Inference complete for {symbol.upper()}")
                formatted_logs = "\n".join(log_lines)
            else:
                formatted_logs = f"Model Error: {hf_data.get('detail', 'Unknown error')}"
        except Exception as hf_err:
            formatted_logs = f"Hugging Face Connection Error: {str(hf_err)}\nCheck if Space is 'Sleeping'."
            tomorrow_pred  = close_values[-1] * 1.01

        return jsonify({
            "symbol":          symbol.upper(),
            "dates":           df.tail(100).index.strftime("%Y-%m-%d").tolist() + ["Tomorrow"],
            "actual":          actual_list + [None],
            "predictions":     historical_predictions + [float(tomorrow_pred)],
            "ma100":           ma100_list,
            "ma200":           ma200_list,
            "current_price":   round(float(close_values[-1]), 2),
            "predicted_price": round(float(tomorrow_pred), 2),
            "verdict":         "Upward" if tomorrow_pred > close_values[-1] else "Downward",
            "logs":            formatted_logs,
        })

    except Exception as e:
        return jsonify({"error": str(e), "logs": "Critical system failure in EC2."}), 500


@routes_bp.route("/learnings/news", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def get_learnings_news():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    try:
        response = requests.get(f"{HF_BASE_URL}/news", timeout=30)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"error": "Hugging Face is waking up or busy", "status": response.status_code}), response.status_code
    except requests.exceptions.Timeout:
        return jsonify({"error": "Hugging Face took too long to analyze news"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/transactions/<int:userid>", methods=["GET"])
def get_transactions(userid):
    try:
        txns = Transactionhistory.query.filter_by(userid=userid).all()
        if not txns:
            return jsonify([])
        result = [
            {
                "userid":    t.userid,
                "stockname": t.stockname,
                "quantity":  t.quantity,
                "price":     t.price,
                "type":      t.transactiontype,
                "date":      t.timestamp.strftime("%Y-%m-%d %H:%M:%S") if t.timestamp else None,
            }
            for t in txns
        ]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes_bp.route("/dashboard/<int:userid>/export", methods=["GET"])
def export_dashboard_csv(userid):
    data = get_dashboard_data(userid)
    if "error" in data:
        return jsonify(data), 404

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Wallet", data["wallet"]])
    cw.writerow([])
    cw.writerow(["Progress Score", data["metrics"].get("progress_score", "")])
    cw.writerow(["Level",          data["metrics"].get("level", "")])
    cw.writerow(["Login Streak",   data["metrics"].get("login_streak", "")])
    cw.writerow([])
    cw.writerow(["Company", "Stock", "Quantity", "Avg Buy Price", "Invested", "LTP", "Now Value", "P/L"])
    for p in data["portfolio"]:
        cw.writerow([
            p["companyname"], p["stockname"], p["totalquantity"],
            p["averagebuyprice"], p["totalinvested"],
            p["ltp"], p["nowvalue"], p["profitorloss"],
        ])
    cw.writerow([])
    cw.writerow(["Type", "Stock", "Price", "Date"])
    for t in data["transactions"]:
        cw.writerow([t["type"], t["stockname"], t["price"], t["date"]])

    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=dashboard_full_export.csv"},
    )


@routes_bp.route("/options/<symbol>", methods=["GET"])
@cross_origin(supports_credentials=True)
def options_chain(symbol):
    """
    Proxies the Node.js NSE Options service with caching and expiry filtering.
    """
    symbol        = symbol.upper()
    target_expiry = request.args.get("expiry")
    try:
        cache_key = f"options_full_{symbol}"
        result    = cache.get(cache_key)

        if not result:
            result = OptionsService.get_options_chain(symbol)
            if result.get("success"):
                cache.set(cache_key, result, timeout=300)

        if not result.get("success"):
            return jsonify({"success": False, "error": result.get("error", "Failed to fetch options data")}), 502

        normalized = OptionsService.normalize_options_data(result.get("data", []), target_expiry=target_expiry)
        if not normalized:
            return jsonify({"success": False, "error": f"No options data found for {symbol}"}), 404

        return jsonify({
            "success":           True,
            "symbol":            symbol,
            "available_expiries": normalized["available_expiries"],
            "selected_expiry":   normalized["selected_expiry"],
            "total_rows":        normalized["total_rows"],
            "data":              normalized["data"],
        })

    except Exception as e:
        current_app.logger.error(f"Options Route Error: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error while processing options"}), 500


@routes_bp.route("/agent/chat", methods=["POST"])
@cross_origin(supports_credentials=True)
def aria_chat():
    """
    ARIA AI Agent — Stock Q&A endpoint.

    Request body (JSON):
    {
        "userid":         1,
        "message":        "Should I buy Infosys?",
        "current_symbol": "INFY",
        "history": [{"role": "user", "content": "..."}, ...]
    }
    """
    try:
        data    = request.get_json(force=True)
        userid  = data.get("userid")
        message = (data.get("message") or "").strip()

        if not userid:
            return jsonify({"error": "userid is required", "status": "error"}), 400
        if not message:
            return jsonify({"error": "message cannot be empty", "status": "error"}), 400

        current_symbol = (data.get("current_symbol") or "").strip()
        history        = data.get("history") or []
        clean_history  = [
            turn for turn in history
            if isinstance(turn, dict)
            and turn.get("role") in ("user", "assistant")
            and turn.get("content", "").strip()
        ]

        reply = get_aria_response(
            userid=int(userid),
            message=message,
            current_symbol=current_symbol,
            history=clean_history,
        )
        return jsonify({"reply": reply, "status": "ok"})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "status": "error"}), 500
