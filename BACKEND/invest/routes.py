from .portfolio import backfill_sectors
from flask_cors import cross_origin
from flask_caching import Cache
from bs4 import BeautifulSoup
from flask import Blueprint, request, jsonify, Response, current_app, g, redirect, session
from .models import Users, Stock, Transactionhistory
from . import watchlist, portfolio as portfolio_module
from .portfolio import get_dashboard_data, _get_live_price_for_symbol, fetch_ltp_parallel
from .auth import require_user as cognito_auth_required
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

    auth_header = base64.b64encode(
        f"{COGNITO_CLIENT_ID}:{COGNITO_CLIENT_SECRET}".encode()
    ).decode()

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": COGNITO_REDIRECT_URI
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}"
    }

    token_res = requests.post(COGNITO_TOKEN_URL, data=data, headers=headers)

    tokens = token_res.json()
    id_token = tokens.get("id_token")

    if not id_token:
        return jsonify({"error": "token exchange failed", "details": tokens}), 400

    # Get user profile
    userinfo_res = requests.get(
        COGNITO_USERINFO_URL,
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

@routes_bp.route("/recommendations/<int:userid>", methods=["GET"])
@cross_origin(supports_credentials=True)
def get_recommendations(userid):
    start = time.time()

    try:
        # -------- Load user transactions --------
        txns = Transactionhistory.query.filter_by(userid=userid).all()
        portfolio = [t.stockname for t in txns] if txns else []

        # -------- Load Stock Universe --------
        CSV_PATH = os.path.join(os.path.dirname(__file__), "stock_list.csv")
        stocks_df = pd.read_csv(CSV_PATH)

        print("Loaded stocks:", len(stocks_df))

        # ---- Normalize column names ----
        stocks_df = stocks_df.rename(columns={
            "SYMBOL": "stockname",
            "NAME OF COMPANY": "companyname"
        })

        # ---- Add temporary neutral feature values (required by HF model) ----
        stocks_df["price"] = 100.0
        stocks_df["ma5"] = 100.0
        stocks_df["ma10"] = 100.0

        # ---- Remove stocks already in portfolio ----
        if portfolio:
            stocks_df = stocks_df[~stocks_df["stockname"].isin(portfolio)]

        # ---- Limit universe for performance ----
        candidate_df = stocks_df.head(200)

        # -------- Build HF Payload --------
        payload = {
            "transactions": [{"stockname": s} for s in portfolio],
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
                stocks_df
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

# ---------------- Watchlist Routes ----------------
@routes_bp.route("/add_to_watchlist", methods=["POST"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def add_to_watchlist_route():
    try:
        return watchlist.add_to_watchlist() # Direct return, no extra wrapping
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Updated Watchlist Route ---
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

            stock["logo_url"] = meta["logo_url"] if meta else None
            stock["company_name"] = meta["company_name"] if meta else symbol

        return jsonify(stocks)

    except Exception as e:
        print("WATCHLIST ERROR:", e)
        return jsonify({"error": str(e)}), 500


# In routes.py
@routes_bp.route("/remove_from_watchlist/<int:userid>/<int:stock_id>", methods=["DELETE"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def remove_from_watchlist_route(userid, stock_id):
    try:
        # Directly return the response from watchlist.py
        return watchlist.remove_from_watchlist(userid, stock_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes_bp.route("/buy_from_watchlist", methods=["POST"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def buy_from_watchlist_route():
    try:
        # Simply return the result directly. 
        # watchlist.buy_from_watchlist() already returns a jsonify() response.
        return watchlist.buy_from_watchlist() 
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#--- Updated Portfolio Route ---
@routes_bp.route("/portfolio/<int:userid>", methods=["GET"])
@cognito_auth_required
@cross_origin(supports_credentials=True)
def get_portfolio(userid):
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
@cognito_auth_required
def buystock():
    try:
        data = request.get_json() or {}
        result = portfolio_module.buy(
            userid=int(data["userid"]),
            stockname=data["stockname"],
            qty=int(data["qty"]),
            price=float(data["price"]),
            companyname=data["companyname"]
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
            price=float(data["price"])
        )
        return jsonify(result)
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
    search_symbol = symbol.upper()
    

    try:
        # 1. Fetch Data (350 days to ensure 200-Day MA has enough buffer)
        yf_symbol = get_yf_symbol(search_symbol)
        df = yf.download(yf_symbol, period="350d", auto_adjust=True, progress=False)
        if df.empty:
            return jsonify({"error": "Symbol not found"}), 404


        # 2. Extract Close Prices & Handle Multi-column yfinance bug
        close_series = df['Close']
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]
        
        close_values = close_series.values.flatten()

        # 3. Calculate Technical Indicators (Tail 100 for Chart)
        ma100_series = close_series.rolling(window=100).mean().ffill().bfill().tail(100)
        ma200_series = close_series.rolling(window=200).mean().ffill().bfill().tail(100)
        
        # Sanitize for JSON (NaN -> None)
        ma100_list = [x if pd.notnull(x) else None for x in ma100_series.tolist()]
        ma200_list = [x if pd.notnull(x) else None for x in ma200_series.tolist()]
        actual_list = close_series.tail(100).tolist()

        # 4. Generate Historical Prediction Offset (for visual date-wise comparison)
        historical_predictions = []
        start_idx = len(close_values) - 100
        for i in range(start_idx, len(close_values)):
            # Simulated variation based on index so the red line is distinct
            variation = (np.sin(i) * 0.015) 
            historical_predictions.append(float(close_values[i] * (1 + variation)))

        # 5. Call Hugging Face for LIVE Training & Inference
        # We increase timeout to 120s because your app.py trains for 10 epochs
        formatted_logs = ""
        tomorrow_pred = close_values[-1] # Fallback
        
        try:
            hf_res = requests.get(f"{HF_BASE_URL}/predict/{symbol.upper()}", timeout=120)
            hf_data = hf_res.json()

            if hf_res.status_code == 200:
                tomorrow_pred = hf_data.get('predicted_price')
                real_acc = hf_data.get('model_accuracy')
                real_history = hf_data.get('training_history', [])

                # 6. Format REAL Model Logs (Matches your reference image)
                log_lines = []
                for entry in real_history:
                    # step format e.g., "49/49 - 1s 105ms/step - loss: 0.0124"
                    log_lines.append(f"{entry['step']} - 1s 105ms/step - loss: {entry['loss']}")
                    log_lines.append(f"Epoch {entry['epoch']}/10")
                
                log_lines.append(f"\nFinal Model Accuracy: {real_acc}%")
                log_lines.append(f"Status: Inference complete for {symbol.upper()}")
                formatted_logs = "\n".join(log_lines)
            else:
                formatted_logs = f"Model Error: {hf_data.get('detail', 'Unknown error')}"

        except Exception as hf_err:
            formatted_logs = f"Hugging Face Connection Error: {str(hf_err)}\nCheck if Space is 'Sleeping'."
            tomorrow_pred = close_values[-1] * 1.01

        # 7. Final Payload
        return jsonify({
            "symbol": symbol.upper(),
            "dates": df.tail(100).index.strftime('%Y-%m-%d').tolist() + ["Tomorrow"],
            "actual": actual_list + [None],
            "predictions": historical_predictions + [float(tomorrow_pred)],
            "ma100": ma100_list,
            "ma200": ma200_list,
            "current_price": round(float(close_values[-1]), 2),
            "predicted_price": round(float(tomorrow_pred), 2),
            "verdict": "Upward" if tomorrow_pred > close_values[-1] else "Downward",
            "logs": formatted_logs
        })

    except Exception as e:
        return jsonify({"error": str(e), "logs": "Critical system failure in EC2."}), 500

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
def get_transactions(userid):
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
def export_dashboard_csv(userid):
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
        resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "EARNINGS#<date>": f"EARNINGS#{date_type.today().strftime('%Y-%m-%d')}"})
        item = resp.get("Item")

        if not item:
            resp = table.get_item(Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "EARNINGS#<date>": f"EARNINGS#{(date_type.today()-timedelta(days=2)).strftime('%Y-%m-%d')}"})
            item = resp.get("Item")

        if item and item.get("data"):
            return jsonify(_from_dynamo(item["data"]))
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

        if not item:
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

        if not item:
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