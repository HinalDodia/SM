"""
agent.py
Handles all logic for the ARIA AI agent:
  - Fetching user context from MySQL (Users + Portfolio models)
  - Fetching live stock data from yfinance
  - Calling AWS Bedrock (Nova Micro)
  - Returning the reply

Place this file inside: BACKEND/invest/
"""

import os
import boto3
import yfinance as yf
from .models import Users, Portfolio
from .System_prompt import build_system_prompt, get_level_label

# ── Bedrock client (singleton, initialised once on import) ───────────────────
_bedrock_client = None

def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "ap-south-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    return _bedrock_client


# ── 1. Fetch user context ────────────────────────────────────────────────────
def fetch_user_context(userid: int) -> dict:
    """
    Pulls user data from Users + Portfolio tables.
    Fetches current price for each holding via yfinance.
    Returns a dict ready for build_system_prompt().
    """
    user = Users.query.get(userid)
    if not user:
        return {
            "name": "User", "wallet": 0, "pnl_abs": 0,
            "pnl_pct": 0, "progress": 0, "level_label": "Beginner",
            "holdings": []
        }

    # ── Level label ──────────────────────────────────────────────────────────
    level_label = get_level_label(user.level)

    # ── P/L percent — use profitpercent or losspercent whichever is set ──────
    pnl_pct = float(user.profitpercent or 0) - float(user.losspercent or 0)

    # ── Holdings from Portfolio table ────────────────────────────────────────
    holdings_raw = Portfolio.query.filter_by(userid=userid).all()
    holdings = []

    for h in holdings_raw:
        if not h.totalquantity or h.totalquantity == 0:
            continue  # skip zero-qty rows

        # Fetch live price — same pattern used throughout your routes.py
        try:
            ticker = yf.Ticker(f"{h.stockname}.NS")
            current_price = round(
                ticker.fast_info.get("lastPrice") or
                ticker.info.get("currentPrice") or
                float(h.averagebuyprice),
                2
            )
        except Exception:
            current_price = float(h.averagebuyprice)  # fallback to avg price

        avg = float(h.averagebuyprice)
        qty = int(h.totalquantity)
        pl_abs = round((current_price - avg) * qty, 2)

        holdings.append({
            "symbol":      h.stockname,
            "companyname": h.companyname or h.stockname,
            "qty":         qty,
            "avg_price":   round(avg, 2),
            "current_price": current_price,
            "pl_abs":      pl_abs,
        })

    return {
        "name":        user.name,
        "wallet":      float(user.money),
        "pnl_abs":     float(user.profitorloss or 0),
        "pnl_pct":     round(pnl_pct, 2),
        "progress":    int(user.progress or 0),
        "level_label": level_label,
        "holdings":    holdings,
    }


# ── 2. Fetch stock context ───────────────────────────────────────────────────
def fetch_stock_context(symbol: str) -> dict | None:
    """
    Pulls live stock data from yfinance for the stock on screen.
    Returns None if symbol is empty or fetch fails.
    """
    if not symbol or not symbol.strip():
        return None

    symbol = symbol.upper().strip()
    yf_symbol = f"{symbol}.NS"

    try:
        ticker = yf.Ticker(yf_symbol)
        info   = ticker.info

        # If yfinance returns an empty dict (invalid symbol), return None
        if not info or not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return None

        def safe(key, default="N/A"):
            val = info.get(key)
            return val if val is not None else default

        def safe_round(key, digits=2, default="N/A"):
            val = info.get(key)
            try:
                return round(float(val), digits)
            except (TypeError, ValueError):
                return default

        def fmt_crore(val):
            """Converts raw market cap to ₹ Crore string."""
            try:
                crore = float(val) / 1e7
                if crore >= 1_00_000:
                    return f"₹{round(crore/1_00_000, 2)} Lakh Cr"
                return f"₹{round(crore, 0):,.0f} Cr"
            except (TypeError, ValueError):
                return "N/A"

        return {
            "symbol":          symbol,
            "name":            safe("longName") or safe("shortName"),
            "price":           safe_round("currentPrice") or safe_round("regularMarketPrice"),
            "day_high":        safe_round("dayHigh"),
            "day_low":         safe_round("dayLow"),
            "week_high_52":    safe_round("fiftyTwoWeekHigh"),
            "week_low_52":     safe_round("fiftyTwoWeekLow"),
            "market_cap":      fmt_crore(info.get("marketCap")),
            "pe_ratio":        safe_round("trailingPE"),
            "eps":             safe_round("trailingEps"),
            "sector":          safe("sector"),
            "analyst_rating":  safe("recommendationKey", "N/A").upper(),
            "dividend_yield":  safe_round("dividendYield", 4),
            "description":     safe("longBusinessSummary", ""),
        }

    except Exception as e:
        print(f"[ARIA] fetch_stock_context failed for {symbol}: {e}")
        return None


# ── 3. Call Bedrock ──────────────────────────────────────────────────────────
def call_bedrock(system_prompt: str, history: list, message: str) -> str:
    """
    Calls AWS Bedrock Nova Micro via the Converse API.

    Parameters
    ----------
    system_prompt : str   — built by build_system_prompt()
    history       : list  — previous turns [{"role": "user"/"assistant", "content": "..."}]
                            frontend sends last 3 turns max (keeps cost low)
    message       : str   — current user message

    Returns
    -------
    str — ARIA's reply text
    """
    client = get_bedrock_client()

    # ── Build messages list ──────────────────────────────────────────────────
    # Bedrock Converse expects: [{"role": "user"/"assistant", "content": [{"text": "..."}]}]
    messages = []

    # Add conversation history (last 3 turns = 6 messages max)
    for turn in history[-6:]:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({
                "role": role,
                "content": [{"text": str(content)}]
            })

    # Add current message
    messages.append({
        "role": "user",
        "content": [{"text": message}]
    })

    # ── Bedrock Converse call ────────────────────────────────────────────────
    response = client.converse(
        modelId=os.getenv("BEDROCK_MODEL_ID", "apac.amazon.nova-micro-v1:0"),
        system=[{"text": system_prompt}],
        messages=messages,
        inferenceConfig={
            "maxTokens": 600,      # enough for structured buy/sell answer
            "temperature": 0.3,    # lower = more factual, less creative
            "topP": 0.9,
        }
    )

    reply = response["output"]["message"]["content"][0]["text"]
    return reply.strip()


# ── 4. Main entry point called by the Flask route ────────────────────────────
def get_aria_response(userid: int, message: str,
                      current_symbol: str, history: list) -> str:
    """
    Full pipeline:
      fetch user → fetch stock → build prompt → call Bedrock → return reply

    Called directly from the /agent/chat Flask route.
    """
    # Step 1 — User context
    user_ctx  = fetch_user_context(userid)

    # Step 2 — Stock context (None if not on stock page)
    stock_ctx = fetch_stock_context(current_symbol)

    # Step 3 — Build system prompt
    system_prompt = build_system_prompt(user_ctx, stock_ctx)

    # Step 4 — Call Bedrock
    reply = call_bedrock(system_prompt, history, message)

    return reply