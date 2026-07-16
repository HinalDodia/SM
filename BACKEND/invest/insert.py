"""
insert_data.py
==============
Standalone script — replicates the exact fetch + calculation logic from routes.py
and stores the resulting JSON into DynamoDB.

Routes.py is NOT touched. This script runs independently.

Usage
-----
    # Insert all 12 endpoints for all 40 stocks
    python insert_data.py

    # Insert specific symbols only
    python insert_data.py --symbols INFY TCS

    # Insert specific endpoints only
    python insert_data.py --endpoints stock-page stock-chart

    # Insert with custom chart period/interval
    python insert_data.py --symbols INFY --period 1y --interval 1d

    # Dry run — fetch data but do NOT write to DynamoDB (just print what would be stored)
    python insert_data.py --dry-run

    # Skip endpoints that already have a fresh item in DynamoDB today
    python insert_data.py --skip-existing

Requirements
------------
    pip install boto3 yfinance pandas numpy requests feedparser beautifulsoup4 nselib

Environment variables
---------------------
    AWS_REGION      : DynamoDB region (default: ap-south-1)
    HF_SPACE_URL    : Hugging Face space base URL
    GNEWS_API_KEY   : GNews API key
    NEWSAPI_KEY     : NewsAPI key
"""

from options_service import OptionsService
import os
import re 
import csv
import time
import json
import pandas as pd
import argparse
import traceback
import urllib.parse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone, date as date_type
from collections import defaultdict
from nselib import capital_market
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests 
import boto3
import numpy as np
import pandas as pd
import yfinance as yf
yf.set_tz_cache_location("/tmp")
import feedparser
from boto3.dynamodb.conditions import Key
from bs4 import BeautifulSoup
import hashlib
from botocore.exceptions import ClientError

CSV_PATH = os.path.join(os.path.dirname(__file__), "stock_list.csv")

stock_df = pd.read_csv(CSV_PATH,dtype=str,keep_default_na=False)
from dotenv import load_dotenv

load_dotenv()
s3 = boto3.client("s3")
# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

AWS_REGION   = os.environ.get("AWS_REGION", "ap-south-1")
HF_BASE_URL  = os.environ.get("HF_SPACE_URL")
HF_HEADERS   = {"Authorization": "Bearer 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"}
GNEWS_API_KEY = os.environ.get("GNEWS_API_KEY")
NEWSAPI_KEY   = os.environ.get("NEWSAPI_KEY")
S3_BUCKET = os.environ.get("S3_BUCKET", "sm-bse-filings")
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
STOCK_CSV    = os.path.join(SCRIPT_DIR, "stock_list.csv")

# ---------------------------------------------------------------------------
# DynamoDB table names (must match what you created in AWS console)
# ---------------------------------------------------------------------------

TABLES = {
    "stock-page":             "stock-page",
    "stock-chart":            "stock-chart",
    "stock-financials":       "stock-financials",
    "stock-earnings":         "stock-earnings",
    "stock-dividend-summary": "stock-dividend-summary",
    "stock-headlines":        "stock-headlines",
    # "stock-sentiment":        "stock-sentiment",
    "stock-competitors":      "stock-competitors",
    "stock-options":          "stock-options",
    "stock-short-interest":   "stock-short-interest",
    "stock-meta":             "stock-meta",
    "bse-filings":            "bse-filings",
}

ALL_ENDPOINTS = list(TABLES.keys())

# ---------------------------------------------------------------------------
# BSE scrip code map (copied from routes.py)
# ---------------------------------------------------------------------------

BSE_SCRIP_MAP = {
    "RELIANCE": "500325", "TCS": "532540", "INFY": "500209",
    "HDFCBANK": "500180", "ICICIBANK": "532174", "SBIN": "500112",
    "AXISBANK": "532215", "KOTAKBANK": "500247", "BAJFINANCE": "500034",
    "BAJAJFINSV": "532978", "LT": "500510", "ITC": "500875",
    "HINDUNILVR": "500696", "NESTLEIND": "500790", "BRITANNIA": "500825",
    "TITAN": "500114", "MARUTI": "532500", "EICHERMOT": "505200",
    "HEROMOTOCO": "500182", "TATASTEEL": "500470", "JSWSTEEL": "500228",
    "ULTRACEMCO": "532538", "POWERGRID": "532898", "NTPC": "532555",
    "ONGC": "500312", "SUNPHARMA": "524715", "DRREDDY": "500124",
    "CIPLA": "500087", "DIVISLAB": "532488", "APOLLOHOSP": "508869",
    "HCLTECH": "532281", "TECHM": "532755", "WIPRO": "507685",
    "ADANIENT": "512599", "ADANIPORTS": "532921", "COALINDIA": "533278",
    "INDUSINDBK": "532187", "PIDILITIND": "500331", "ASIANPAINT": "500820",
    "GRASIM": "500300",
}

BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Referer": "https://www.bseindia.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORY_MAP = {
    "financial result": "Results", "result": "Results",
    "quarterly result": "Results", "earnings call transcript": "Results",
    "board meeting": "Board", "outcome of board": "Board", "board": "Board",
    "dividend": "Dividend", "date of payment of dividend": "Dividend", "record date": "Dividend",
    "agm": "AGM", "egm": "AGM", "annual general meeting": "AGM", "extraordinary general": "AGM",
    "insider": "Insider", "sast": "Insider", "shareholding": "Insider",
    "beneficial ownership": "Insider", "trading window": "Insider", "pit regulation": "Insider",
    "acquisition": "Acquisition", "merger": "Acquisition", "buyback": "Acquisition",
    "subsidiary": "Acquisition", "amalgamation": "Acquisition",
    "press release": "Press Release", "media release": "Press Release",
    "analyst": "Analyst / Investor Meet", "investor meet": "Analyst / Investor Meet",
    "secretarial compliance": "Compliance", "lodr": "Compliance", "regulation 30": "Compliance",
}

SENTIMENT_SCORE = {"bullish": 1.35, "neutral": 1.00, "bearish": 0.65}

TRUSTED_SOURCES = {
    "Reuters",
    "Bloomberg",
    "CNBC",
    "Moneycontrol",
    "The Economic Times",
    "Economic Times",
    "LiveMint",
    "Mint",
    "Business Standard",
    "Financial Express",
    "The Hindu BusinessLine",
    "BusinessLine",
    "NDTV Profit",
    "CNBC TV18",
    "ETMarkets",
    "Zee Business",
    "India Today",
    "Yahoo Finance",
    "MarketScreener",
    "Seeking Alpha",
    "Benzinga",
    "The Motley Fool",
    "Simply Wall St",
    "simplywall.st",
}

# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------

_dynamo = None

def get_dynamo():
    global _dynamo
    if _dynamo is None:
        _dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)
    return _dynamo


def _to_dynamo(obj):
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return None
        try:
            # Use Decimal.from_float for exact binary→decimal conversion, not str(round(...))
            return Decimal(repr(obj))  # repr gives full precision, no rounding
        except InvalidOperation:
            return None
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, dict):
        return {k: _to_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamo(i) for i in obj]
    return obj


def _item_exists_today(table_name: str, pk: str, sk_prefix: str) -> bool:
    """Return True if there's already an item with today's date in the SK."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        table = get_dynamo().Table(table_name)
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(pk) & Key("SK").begins_with(f"{sk_prefix}#{today}"),
            Limit=1,
        )
        return len(resp.get("Items", [])) > 0
    except Exception:
        return False



# ---------------------------------------------------------------------------
# Stock list loader
# ---------------------------------------------------------------------------
def load_symbol():
    try:
        CSV_PATH = os.path.join(os.path.dirname(__file__), "stock_list.csv")
        stock_df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
        return stock_df.to_dict("records")

    except (FileNotFoundError, pd.errors.EmptyDataError):
        stock_df = pd.DataFrame(columns=["SYMBOL", "NAME OF COMPANY"])

# ---------------------------------------------------------------------------
# Shared helpers (copied from routes.py)
# ---------------------------------------------------------------------------

def get_yf_symbol(symbol: str) -> str:
    symbol = str(symbol).upper().strip()
    special = {"M&M": "M&M.NS", "BAJAJ-AUTO": "BAJAJ-AUTO.NS", "UNITDSPR": "MCDOWELL-N.NS"}
    if symbol in special:
        return special[symbol]
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def safe_float(val):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return float(val)
    except Exception:
        return None


def safe_div(a, b):
    try:
        return round(a / b, 2) if b else None
    except Exception:
        return None


def format_cr(value):
    val = safe_float(value)
    return round(val / 10_000_000, 2) if val is not None else None


def format_currency_cr(value):
    val = format_cr(value)
    return f"₹{val:,.0f} Cr" if val is not None else None

# ---------------------------------------------------------------------------
# 1. stock-page  (copied from routes.py L899–L1250)
# ---------------------------------------------------------------------------


def stock_page(symbol):

    try:
        yf_sym = get_yf_symbol(symbol)
        print(f"[DEBUG] Fetching stock page for symbol: {symbol} -> {yf_sym}")
        ticker = yf.Ticker(yf_sym)
        info = ticker.info or {}
        
        # Debug: log what we got from yfinance
        print(f"[DEBUG] yfinance info keys: {list(info.keys())[:10]}...")
        print(f"[DEBUG] longName: {info.get('longName')}")
        print(f"[DEBUG] currentPrice: {info.get('currentPrice')}")


        # ---------------- PRICE DATA ----------------

        hist = ticker.history(period="6mo")

        today_low = None
        today_high = None

        if not hist.empty:
            today_low = float(hist["Low"].iloc[-1])
            today_high = float(hist["High"].iloc[-1])

        range50 = ticker.history(period="50d")
        range52 = ticker.history(period="1y")

        # ---------------- DIVIDENDS ----------------

        dividends = ticker.dividends

        record_date_1 = None
        record_date_2 = None
        ex_div_1 = None
        ex_div_2 = None
        div_payable_1 = None
        div_payable_2 = None
        div_amt_1 = None
        div_amt_2 = None

        if dividends is not None and not dividends.empty:
            last_div = dividends.tail(2)
            if len(last_div) >= 1:
                ex_div_1 = str(last_div.index[-1].date())
                record_date_1 = ex_div_1
                div_payable_1 = ex_div_1
                div_amt_1 = float(last_div.iloc[-1])

            if len(last_div) >= 2:
                ex_div_2 = str(last_div.index[-2].date())
                record_date_2 = ex_div_2
                div_payable_2 = ex_div_2
                div_amt_2 = float(last_div.iloc[-2])


        # ---------------- CALCULATIONS ----------------

        current_price = info.get("currentPrice")

        target_mean = info.get("targetMeanPrice")

        upside = None

        if current_price and target_mean:
            upside = round(((target_mean-current_price)/current_price)*100,2)


        peg = info.get("pegRatio")


        # Rating Score (0-4 scale)
        rec = info.get("recommendationKey","")

        rating_score_map = {
            "strong_buy":4,
            "buy":3,
            "hold":2,
            "sell":1,
            "strong_sell":0
        }

        rating_score = rating_score_map.get(rec,2)


        # ---------------- ADVANCED FINANCIAL SCRAPING FOR MISSING DATA ----------------
        
        debt_eq = info.get("debtToEquity")
        curr_ratio = info.get("currentRatio")
        quick_ratio = info.get("quickRatio")
        book_val = info.get("bookValue")
        cash_flow = info.get("operatingCashflow")

        try:
            # If we're missing basic debt numbers, scrape the balance sheet
            if debt_eq is None or curr_ratio is None or book_val is None:
                bs = ticker.balance_sheet
                
                if bs is not None and not bs.empty:
                    bs_col = bs.columns[0]
                    
                    if debt_eq is None:
                        td = bs.loc["Total Debt", bs_col] if "Total Debt" in bs.index else None
                        te = bs.loc["Stockholders Equity", bs_col] if "Stockholders Equity" in bs.index else None
                        if td and te:
                            debt_eq = round((td / te) * 100, 2)
                        elif te:
                            # if total debt is missing but Equity exists, debt equity is probably near 0
                            pass
                    
                    if curr_ratio is None:
                        tca = bs.loc["Total Current Assets", bs_col] if "Total Current Assets" in bs.index else None
                        tcl = bs.loc["Current Liabilities", bs_col] if "Current Liabilities" in bs.index else None
                        if tca and tcl:
                            curr_ratio = round(tca / tcl, 2)
                            
                        # Quick Ratio
                        if quick_ratio is None and tca and tcl:
                            inv = bs.loc["Inventory", bs_col] if "Inventory" in bs.index else 0
                            quick_ratio = round((tca - inv) / tcl, 2)

                    if book_val is None:
                        te = bs.loc["Stockholders Equity", bs_col] if "Stockholders Equity" in bs.index else None
                        shares = info.get("sharesOutstanding") or 1
                        if te and shares > 1:
                            book_val = round(te / shares, 2)
                            
            if cash_flow is None:
                cfs = ticker.cashflow
                if cfs is not None and not cfs.empty:
                    cf_col = cfs.columns[0]
                    op_cf = cfs.loc["Operating Cash Flow", cf_col] if "Operating Cash Flow" in cfs.index else None
                    if op_cf:
                        cash_flow = float(op_cf)

        except Exception as metric_err:
            pass
            
        def safe_div(a, b):
            try:
                return round(a/b, 2) if b else None
            except:
                return None
                
        price_sales = info.get("priceToSalesTrailing12Months")
        price_cashflow = info.get("priceToCashflow")
        price_book = info.get("priceToBook")
        annual_sales = info.get("totalRevenue")

        # Fallbacks using calculated book values
        curr_price = info.get("currentPrice") or info.get("previousClose")
        if price_book is None and book_val and curr_price:
            price_book = safe_div(curr_price, book_val)
            
        if price_sales is None and annual_sales and curr_price:
            shares = info.get("sharesOutstanding") or 0
            if shares: price_sales = safe_div(curr_price, (annual_sales/shares))
            
        if price_cashflow is None and cash_flow and curr_price:
            shares = info.get("sharesOutstanding") or 0
            if shares: price_cashflow = safe_div(curr_price, (cash_flow/shares))

        # ---------------- FINAL JSON ----------------

        return ({

            "company_overview": {
                "name": info.get("longName") or "Stock Data Unavailable",
                "symbol": symbol,
                "description": info.get("longBusinessSummary") or (f"Fetched {len(info)} fields from yfinance" if info else "No data from yfinance"),
                "website": info.get("website")
            },

            "key_stats": {

                "today_range": [today_low,today_high],

                "50day_range":[
                    float(range50["Low"].min()) if not range50.empty else None,
                    float(range50["High"].max()) if not range50.empty else None
                ],

                "52week_range":[
                    float(range52["Low"].min()) if not range52.empty else None,
                    float(range52["High"].max()) if not range52.empty else None
                ],

                "volume": info.get("volume"),
                "avg_volume": info.get("averageVolume"),

                "market_cap": info.get("marketCap"),

                "pe_ratio": info.get("trailingPE"),

                "dividend_yield": info.get("dividendYield"),

                "price_target": info.get("targetMeanPrice"),

                "consensus_rating": info.get("recommendationKey")
            },


            "company_calendar":{

                "today": str(date_type.today()),

                "last_earnings":str(info.get("lastFiscalYearEnd")),

                "ex_dividend": str(info.get("exDividendDate")) if info.get("exDividendDate") else ex_div_1,

                "record_date_1":record_date_1,

                "record_date_2":record_date_2,

                "ex_dividend_2":ex_div_2,

                "dividend_payable":div_payable_1,

                "dividend_payable_2":div_payable_2,
                
                "div_amt_1": div_amt_1,
                
                "div_amt_2": div_amt_2,

                "fiscal_year_end":info.get("lastFiscalYearEnd")

            },


            "industry_profile":{

                "exchange":info.get("exchange"),

                "sector":info.get("sector"),

                "industry":info.get("industry"),

                "sub_industry":info.get("industry"),

                "symbol":symbol,

                "previous_symbol":info.get("priorSymbol", "N/A"),

                "cik":info.get("cik"),

                "website":info.get("website"),

                "phone":info.get("phone"),

                "fax":info.get("fax", "N/A"),

                "employees":info.get("fullTimeEmployees"),

                "year_founded":info.get("founded", "N/A")

            },


            "price_target_rating":{

                "avg_target":info.get("targetMeanPrice"),

                "high_target":info.get("targetHighPrice"),

                "low_target":info.get("targetLowPrice"),

                "potential_upside_percent":upside,

                "consensus_rating":info.get("recommendationKey"),

                "rating_score":rating_score,

                "research_coverage":info.get("numberOfAnalystOpinions")

            },


            "profitability":{

                "eps":info.get("trailingEps"),

                "trailing_pe":info.get("trailingPE"),

                "forward_pe":info.get("forwardPE"),

                "peg_ratio":peg,

                "net_income":info.get("netIncomeToCommon"),

                "net_margin":info.get("profitMargins"),

                "pretax_margin":info.get("profitMargins"),

                "roe":info.get("returnOnEquity"),

                "roa":info.get("returnOnAssets")

            },


            "debt":{

                "debt_equity": debt_eq,

                "current_ratio": curr_ratio,

                "quick_ratio": quick_ratio

            },


            "sales_book":{

                "annual_sales": annual_sales,

                "price_sales": price_sales,

                "cashflow": cash_flow,

                "price_cashflow": price_cashflow,

                "book_value": book_val,

                "price_book": price_book

            },


            "misc":{

                "shares_outstanding":info.get("sharesOutstanding"),

                "float_shares":info.get("floatShares"),

                "marketcap":info.get("marketCap"),

                "optionable":True,

                "beta":info.get("beta")

            }

        })


    except Exception as e:
        print(f"[ERROR] stock_page error: {str(e)}")
        import traceback
        traceback.print_exc()
        return ({"error":str(e)})


def insert_stock_page(symbol: str, dry_run: bool, skip_existing: bool):

    pk = f"SYMBOL#{symbol}"
    sk = f"SNAPSHOT#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-page"], pk, "SNAPSHOT"):
        print(f"    [SKIP] stock-page for {symbol} already exists today")
        return

    print(f"  Fetching stock-page for {symbol}...")

    data = stock_page(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-page"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "SNAPSHOT#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-page for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()

def stock_page_live_snapshot(symbol: str) -> dict:
    """Lightweight 5-min fetch — only fields that genuinely move intraday.
    Uses fast_info instead of the full stock_page() pipeline (which makes
    7 slow calls including 3 history() pulls, dividends, balance sheet,
    and cashflow — all static/rarely-changing data not needed here)."""
    yf_sym = get_yf_symbol(symbol)
    ticker = yf.Ticker(yf_sym)
    fi = ticker.fast_info

    price = getattr(fi, "last_price", None)
    prev_close = getattr(fi, "previous_close", None)
    change = round(price - prev_close, 2) if price and prev_close else None
    change_pct = round((change / prev_close) * 100, 2) if change and prev_close else None

    return {
        "current_price":    price,
        "previous_close":   prev_close,
        "price_change":     change,
        "price_change_pct": change_pct,
        "day_low":          getattr(fi, "day_low", None),
        "day_high":         getattr(fi, "day_high", None),
        "volume":           getattr(fi, "last_volume", None),
        "market_cap":       getattr(fi, "market_cap", None),
    }


def save_price_snapshot(symbol: str):
    pk = f"SYMBOL#{symbol}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ttl_value = int(time.time()) + (30 * 24 * 60 * 60)  # 30 days

    data = stock_page_live_snapshot(symbol)
    if not data.get("current_price"):
        print(f"    [SKIP] No live price for {symbol}")
        return

    table = get_dynamo().Table(TABLES["stock-page"])

    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "SNAPSHOT#<date>": "LATEST",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
    })
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "SNAPSHOT#<date>": f"SNAPSHOT#{now_iso}",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
        "ttl": ttl_value,
    })
    print(f"    [OK] Price snapshot stored for {symbol}: ₹{data['current_price']}")

def stock_chart(symbol, period="1y", interval="1d"):
    """
    Enhanced stock chart endpoint returning OHLC + DMA50/200 data.

    Query params:
      - period:   1d | 5d | 1mo | 3mo | 6mo | ytd | 1y | 5y  (default: 1y)
      - interval: 1m | 5m | 15m | 30m | 1h | 1d | 1wk | 1mo  (default: 1d)

     shape (backwards-compatible — 'price' still present as alias for 'close'):
      [{ date, open, high, low, close, price, volume, dma50, dma200 }, ...]
    """
    try:
        # ---- Read & validate query params ----
        VALID_PERIODS   = {"1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "5y"}
        VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "1h", "1d", "1wk", "1mo"}

        period   = period.lower()
        interval = interval.lower()

        if period   not in VALID_PERIODS:   period   = "1y"
        if interval not in VALID_INTERVALS: interval = "1d"

        # ---- Fetch OHLCV history ----
        ticker = yf.Ticker(get_yf_symbol(symbol))
        df = ticker.history(period=period, interval=interval)

        if df.empty:
            return ([])

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
        return ({"error": str(e)}), 500

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

    return result

def insert_stock_chart(symbol: str, period: str, interval: str, dry_run: bool, skip_existing: bool):
    pk = f"SYMBOL#{symbol}"
    sk = f"CHART#{period}#{interval}"

    if skip_existing and _item_exists_today(TABLES["stock-chart"], pk, "CHART"):
        print(f"    [SKIP] stock-chart for {symbol} already exists today")
        return

    print(f"  Fetching stock-chart for {symbol}...")

    data = stock_chart(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-chart"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "CHART#<period>#<interval>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-chart for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()

def financials_page(symbol):

    try:
        def safe_float(val):

            try:

                if val is None:
                    return None

                if pd.isna(val):
                    return None

                return float(val)

            except:
                return None

        def safe_get(df, row, col):

            try:

                if row in df.index:
                    return safe_float(df.loc[row, col])

                return None

            except:
                return None

        # ---------------------------------------------------
        # FORMATTERS
        # ---------------------------------------------------

        def format_cr(value):

            val = safe_float(value)

            if val is None:
                return None

            return round(val / 10000000, 2)

        def format_currency_cr(value):

            val = format_cr(value)

            if val is None:
                return None

            return f"₹{val:,.0f} Cr"

        def format_large_currency(value):

            val = safe_float(value)

            if val is None:
                return None

            if val >= 1_000_000_000_000:
                return f"₹{round(val / 1_000_000_000_000, 2)}T"

            if val >= 1_000_000_000:
                return f"₹{round(val / 1_000_000_000, 2)}B"

            return f"₹{round(val / 1_000_000, 2)}M"

        # ---------------------------------------------------
        # GROWTH
        # ---------------------------------------------------

        def calculate_growth(curr, prev):

            try:

                if curr is None or prev is None:
                    return None

                if prev == 0:
                    return None

                return round(
                    ((curr - prev) / abs(prev)) * 100,
                    2
                )

            except:
                return None

        # ---------------------------------------------------
        # QUARTER LABEL
        # ---------------------------------------------------

        def quarter_label(date):

            try:

                dt = pd.to_datetime(date)

                q = (dt.month - 1) // 3 + 1

                return f"Q{q} {dt.year}"

            except:
                return None

        # ---------------------------------------------------
        # SYMBOL NORMALIZATION
        # ---------------------------------------------------

        symbol = symbol.upper().strip()

        special_map = {
            "M&M": "M&M.NS",
            "BAJAJ-AUTO": "BAJAJ-AUTO.NS"
        }

        if symbol in special_map:
            yf_symbol = special_map[symbol]

        elif not symbol.endswith(".NS"):
            yf_symbol = f"{symbol}.NS"

        else:
            yf_symbol = symbol

        # ---------------------------------------------------
        # INIT
        # ---------------------------------------------------

        ticker = yf.Ticker(yf_symbol)

        info = ticker.info or {}

        # ---------------------------------------------------
        # STATEMENTS
        # ---------------------------------------------------

        income = ticker.income_stmt
        quarterly_income = ticker.quarterly_income_stmt

        cashflow = ticker.cashflow
        quarterly_cashflow = ticker.quarterly_cashflow

        balance = ticker.balance_sheet
        quarterly_balance = ticker.quarterly_balance_sheet

        # ---------------------------------------------------
        # COMPANY
        # ---------------------------------------------------

        company_name = (
            info.get("longName")
            or info.get("shortName")
            or symbol
        )

        # ---------------------------------------------------
        # BUILD INCOME STATEMENT
        # ---------------------------------------------------

        def build_income_statement(df, quarterly=False):

            result = []

            if df is None or df.empty:
                return result

            cols = list(reversed(df.columns[:8]))

            prev_revenue = None
            prev_net_income = None

            for col in cols:

                revenue = safe_get(
                    df,
                    "Total Revenue",
                    col
                )

                gross_profit = safe_get(
                    df,
                    "Gross Profit",
                    col
                )

                operating_income = safe_get(
                    df,
                    "Operating Income",
                    col
                )

                pretax_income = safe_get(
                    df,
                    "Pretax Income",
                    col
                )

                net_income = safe_get(
                    df,
                    "Net Income",
                    col
                )

                diluted_eps = safe_get(
                    df,
                    "Diluted EPS",
                    col
                )

                row = {

                    "year":
                        str(col.year),

                    "period_end":
                        str(col.date()),

                    "quarter":
                        quarter_label(col)
                        if quarterly
                        else None,

                    "revenue":
                        format_cr(revenue),

                    "revenue_display":
                        format_currency_cr(revenue),

                    "gross_profit":
                        format_cr(gross_profit),

                    "gross_profit_display":
                        format_currency_cr(gross_profit),

                    "operating_income":
                        format_cr(operating_income),

                    "operating_income_display":
                        format_currency_cr(
                            operating_income
                        ),

                    "pretax_income":
                        format_cr(pretax_income),

                    "pretax_income_display":
                        format_currency_cr(
                            pretax_income
                        ),

                    "net_income":
                        format_cr(net_income),

                    "net_income_display":
                        format_currency_cr(net_income),

                    "eps":
                        diluted_eps,

                    # Sequential QoQ / YoY growth
                    "revenue_growth":
                        calculate_growth(
                            revenue,
                            prev_revenue
                        ),

                    "net_income_growth":
                        calculate_growth(
                            net_income,
                            prev_net_income
                        ),

                    "growth_type":
                        (
                            "qoq"
                            if quarterly
                            else "yoy"
                        )
                }

                result.append(row)

                prev_revenue = revenue
                prev_net_income = net_income

            result = [
                x for x in result
                if x["revenue"] is not None
            ]

            return result

        # ---------------------------------------------------
        # BUILD CASHFLOW
        # ---------------------------------------------------

        def build_cashflow_statement(df, quarterly=False):

            result = []

            if df is None or df.empty:
                return result

            cols = list(reversed(df.columns[:8]))

            for col in cols:

                operating_cf = safe_get(
                    df,
                    "Operating Cash Flow",
                    col
                )

                free_cf = safe_get(
                    df,
                    "Free Cash Flow",
                    col
                )

                capex = safe_get(
                    df,
                    "Capital Expenditure",
                    col
                )

                investing_cf = safe_get(
                    df,
                    "Investing Cash Flow",
                    col
                )

                financing_cf = safe_get(
                    df,
                    "Financing Cash Flow",
                    col
                )

                row = {

                    "year":
                        str(col.year),

                    "period_end":
                        str(col.date()),

                    "quarter":
                        quarter_label(col)
                        if quarterly
                        else None,

                    "operating_cashflow":
                        format_cr(operating_cf),

                    "operating_cashflow_display":
                        format_currency_cr(
                            operating_cf
                        ),

                    "free_cashflow":
                        format_cr(free_cf),

                    "free_cashflow_display":
                        format_currency_cr(
                            free_cf
                        ),

                    "capital_expenditure":
                        format_cr(capex),

                    "capital_expenditure_display":
                        format_currency_cr(capex),

                    "investing_cashflow":
                        format_cr(investing_cf),

                    "financing_cashflow":
                        format_cr(financing_cf)
                }

                result.append(row)

            result = [
                x for x in result
                if x["operating_cashflow"] is not None
            ]

            return result

        # ---------------------------------------------------
        # BUILD BALANCE SHEET
        # ---------------------------------------------------

        def build_balance_sheet(df, quarterly=False):

            result = []

            if df is None or df.empty:
                return result

            cols = list(reversed(df.columns[:8]))

            for col in cols:

                assets = safe_get(
                    df,
                    "Total Assets",
                    col
                )

                liabilities = safe_get(
                    df,
                    "Total Liabilities Net Minority Interest",
                    col
                )

                equity = safe_get(
                    df,
                    "Stockholders Equity",
                    col
                )

                debt = safe_get(
                    df,
                    "Total Debt",
                    col
                )

                cash = safe_get(
                    df,
                    "Cash And Cash Equivalents",
                    col
                )

                current_assets = safe_get(
                    df,
                    "Current Assets",
                    col
                )

                current_liabilities = safe_get(
                    df,
                    "Current Liabilities",
                    col
                )

                row = {

                    "year":
                        str(col.year),

                    "period_end":
                        str(col.date()),

                    "quarter":
                        quarter_label(col)
                        if quarterly
                        else None,

                    "total_assets":
                        format_cr(assets),

                    "total_assets_display":
                        format_currency_cr(assets),

                    "total_liabilities":
                        format_cr(liabilities),

                    "total_liabilities_display":
                        format_currency_cr(
                            liabilities
                        ),

                    "total_equity":
                        format_cr(equity),

                    "total_equity_display":
                        format_currency_cr(equity),

                    "total_debt":
                        format_cr(debt),

                    "total_debt_display":
                        format_currency_cr(debt),

                    "cash":
                        format_cr(cash),

                    "cash_display":
                        format_currency_cr(cash),

                    "current_assets":
                        format_cr(current_assets),

                    "current_liabilities":
                        format_cr(current_liabilities)
                }

                result.append(row)

            result = [
                x for x in result
                if x["total_assets"] is not None
            ]

            return result

        # ---------------------------------------------------
        # ANNUAL
        # ---------------------------------------------------

        income_statement = build_income_statement(
            income,
            quarterly=False
        )

        cashflow_statement = build_cashflow_statement(
            cashflow,
            quarterly=False
        )

        balance_sheet = build_balance_sheet(
            balance,
            quarterly=False
        )

        # ---------------------------------------------------
        # QUARTERLY
        # ---------------------------------------------------

        quarterly_income_statement = (
            build_income_statement(
                quarterly_income,
                quarterly=True
            )
        )

        quarterly_cashflow_statement = (
            build_cashflow_statement(
                quarterly_cashflow,
                quarterly=True
            )
        )

        quarterly_balance_sheet = (
            build_balance_sheet(
                quarterly_balance,
                quarterly=True
            )
        )

        # ---------------------------------------------------
        # RATIOS
        # ---------------------------------------------------

        dividend_yield = safe_float(
            info.get("dividendYield")
        )

        dividend_yield_percent = None

        if dividend_yield is not None:

            # Yahoo sometimes returns:
            # 0.0509 OR 5.09

            if dividend_yield <= 1:
                dividend_yield_percent = round(
                    dividend_yield * 100,
                    2
                )
            else:
                dividend_yield_percent = round(
                    dividend_yield,
                    2
                )

        ratios = {

            "market_cap":
                format_large_currency(
                    info.get("marketCap")
                ),

            "pe_ratio":
                safe_float(
                    info.get("trailingPE")
                ),

            "forward_pe":
                safe_float(
                    info.get("forwardPE")
                ),

            "price_to_sales":
                safe_float(
                    info.get(
                        "priceToSalesTrailing12Months"
                    )
                ),

            "price_to_book":
                safe_float(
                    info.get("priceToBook")
                ),

            "gross_margin":
                round(
                    (info.get("grossMargins") or 0) * 100,
                    2
                ),

            "operating_margin":
                round(
                    (info.get("operatingMargins") or 0) * 100,
                    2
                ),

            "profit_margin":
                round(
                    (info.get("profitMargins") or 0) * 100,
                    2
                ),

            "roe":
                round(
                    (info.get("returnOnEquity") or 0) * 100,
                    2
                ),

            "roa":
                round(
                    (info.get("returnOnAssets") or 0) * 100,
                    2
                ),

            "current_ratio":
                safe_float(
                    info.get("currentRatio")
                ),

            "debt_to_equity":
                safe_float(
                    info.get("debtToEquity")
                ),

            "dividend_yield":
                dividend_yield,

            "dividend_yield_percent":
                dividend_yield_percent,

            "dividend_yield_display":
                (
                    f"{dividend_yield_percent}%"
                    if dividend_yield_percent is not None
                    else None
                ),

            "beta":
                safe_float(
                    info.get("beta")
                )
        }

        # ---------------------------------------------------
        # CHARTS
        # ---------------------------------------------------

        revenue_chart = []

        income_chart = []

        for row in income_statement:

            revenue_chart.append({

                "year":
                    row["year"],

                "revenue":
                    row["revenue"],

                "net_income":
                    row["net_income"]
            })

            income_chart.append({

                "year":
                    row["year"],

                "gross_profit":
                    row["gross_profit"],

                "operating_income":
                    row["operating_income"],

                "net_income":
                    row["net_income"]
            })

        # ---------------------------------------------------
        # AI SUMMARY
        # ---------------------------------------------------

        latest = (
            income_statement[-1]
            if income_statement
            else {}
        )

        ai_summary = [

            f"{company_name} generated revenue of {latest.get('revenue_display')} in the latest fiscal year.",

            f"Net income stood at {latest.get('net_income_display')} with operating income of {latest.get('operating_income_display')}.",

            f"Operating margin is currently {ratios.get('operating_margin')}% while ROE stands at {ratios.get('roe')}%.",

            f"The company maintains a current ratio of {ratios.get('current_ratio')} and debt-to-equity ratio of {ratios.get('debt_to_equity')}."
        ]

        # ---------------------------------------------------
        # FAQS
        # ---------------------------------------------------

        faqs = [

            {
                "question":
                    f"What was {company_name}'s latest annual revenue?",

                "answer":
                    f"{company_name} reported annual revenue of {latest.get('revenue_display')} in the latest fiscal year."
            },

            {
                "question":
                    f"What is {company_name}'s operating margin?",

                "answer":
                    f"{company_name} currently has an operating margin of {ratios.get('operating_margin')}%."
            },

            {
                "question":
                    f"How profitable is {company_name}?",

                "answer":
                    f"The company reported net income of {latest.get('net_income_display')} with ROE of {ratios.get('roe')}%."
            }
        ]

        # ---------------------------------------------------
        # TABLE CONFIG
        # ---------------------------------------------------

        table_config = {

            "currency": "INR",

            "unit": "Cr",

            "annual_periods":
                len(income_statement),

            "quarterly_periods":
                len(quarterly_income_statement)
        }

        # ---------------------------------------------------
        # FINAL 
        # ---------------------------------------------------

        return ({

            "success": True,

            "symbol":
                symbol.replace(".NS", ""),

            "company_name":
                company_name,

            "table_config":
                table_config,

            # annual
            "income_statement":
                income_statement,

            "cashflow_statement":
                cashflow_statement,

            "balance_sheet":
                balance_sheet,

            # quarterly
            "quarterly_income_statement":
                quarterly_income_statement,

            "quarterly_cashflow_statement":
                quarterly_cashflow_statement,

            "quarterly_balance_sheet":
                quarterly_balance_sheet,

            # ratios
            "ratios":
                ratios,

            # charts
            "revenue_chart":
                revenue_chart,

            "income_chart":
                income_chart,

            # insights
            "ai_summary":
                ai_summary,

            "faqs":
                faqs
        })

    except Exception as e:

        import traceback

        traceback.print_exc()

        return ({
            "success": False,
            "error": str(e)
        }), 500

def insert_stock_financials(symbol: str,dry_run: bool = False, skip_existing: bool = False) -> None:
    pk = f"SYMBOL#{symbol}"
    print("read pk")
    sk1= f"FINANCIALS#annual"
    print("read sk1")
    sk2=f"FINANCIALS#quarterly"
    print("read sk2")
    if skip_existing and _item_exists_today(TABLES["stock-financials"], pk, "FINANCIALS"):
        print(f"    [SKIP] stock-financials for {symbol} already exists today")
        return
    print(f"  Fetching stock-financials for {symbol}...")

    data = financials_page(symbol)
    print("read data")

    if not data or data.get("success") is False:
        print(f"    [SKIP] Empty or error data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert FINANCIALS#annual + FINANCIALS#quarterly for {pk}")
        return

    table = get_dynamo().Table(TABLES["stock-financials"])
    print("read table")
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "FINANCIALS#<period_type>": sk1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data": _to_dynamo({
            "success":            data.get("success"),
            "symbol":             data.get("symbol"),
            "company_name":       data.get("company_name"),
            "table_config":       data.get("table_config"),
            "income_statement":   data.get("income_statement"),
            "cashflow_statement": data.get("cashflow_statement"),
            "balance_sheet":      data.get("balance_sheet"),
            "ratios":             data.get("ratios"),
            "revenue_chart":      data.get("revenue_chart"),
            "income_chart":       data.get("income_chart"),
            "ai_summary":         data.get("ai_summary"),
            "faqs":               data.get("faqs"),
        }),
    })
    print(f"    [OK] Stored annual financials for {symbol}")

    # --- Store QUARTERLY ---
    # Keep: quarterly statements, ratios, company_name, symbol
    # No revenue_chart / income_chart / ai_summary / faqs — those are annual only
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "FINANCIALS#<period_type>": sk2,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data": _to_dynamo({
            "success":                        data.get("success"),
            "symbol":                         data.get("symbol"),
            "company_name":                   data.get("company_name"),
            "table_config":                   data.get("table_config"),
            "quarterly_income_statement":     data.get("quarterly_income_statement"),
            "quarterly_cashflow_statement":   data.get("quarterly_cashflow_statement"),
            "quarterly_balance_sheet":        data.get("quarterly_balance_sheet"),
            "ratios":                         data.get("ratios"),
        }),
    })
    print(f"    [OK] Stored quarterly financials for {symbol}")

def dividend_summary(symbol):

    try:

        ticker = yf.Ticker(get_yf_symbol(symbol))
        info = ticker.info or {}

        dividends = ticker.dividends

        if dividends is None or dividends.empty:
            return  ({
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

        # ---------- FINAL  ----------
        return  ({

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
        return  ({"error": str(e)})

def insert_stock_dividend_summary(symbol: str, dry_run: bool, skip_existing: bool):

    pk = f"SYMBOL#{symbol}"
    sk = f"DIVIDEND_SUMMARY#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-dividend-summary"], pk, "DIVIDEND_SUMMARY"):
        print(f"    [SKIP] stock-dividend-summary for {symbol} already exists today")
        return

    print(f"  Fetching stock-dividend-summary for {symbol}...")

    data = dividend_summary(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-dividend-summary"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "DIVIDEND_SUMMARY#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-dividend-summary for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()


def earnings_page(symbol):
    try:
       

        # ---------------------------------------------------
        # SYMBOL NORMALIZATION
        # ---------------------------------------------------

        def get_yf_symbol(sym):

            sym = str(sym).upper().strip()

            special_map = {
                "M&M": "M&M.NS",
                "BAJAJ-AUTO": "BAJAJ-AUTO.NS",
                "UNITDSPR": "MCDOWELL-N.NS"
            }

            if sym in special_map:
                return special_map[sym]

            if not sym.endswith(".NS"):
                return f"{sym}.NS"

            return sym

        # ---------------------------------------------------
        # INIT
        # ---------------------------------------------------

        ticker = yf.Ticker(get_yf_symbol(symbol))

        info = ticker.info or {}

        earnings_dates = getattr(
            ticker,
            "earnings_dates",
            None
        )

        q_income = getattr(
            ticker,
            "quarterly_income_stmt",
            None
        )

        # ---------------------------------------------------
        # HELPERS
        # ---------------------------------------------------

        def safe_float(val):

            try:

                if val is None:
                    return None

                if pd.isna(val):
                    return None

                return float(val)

            except:
                return None

        def get_quarter_label(date_val):

            try:

                date_val = pd.to_datetime(date_val)

                q = (date_val.month - 1) // 3 + 1

                return f"Q{q} {date_val.year}"

            except:
                return None

        def map_analyst_quarter_label(label):

            mapping = {
                "0q": "Current Quarter",
                "+1q": "Next Quarter",
                "0y": "Current Year",
                "+1y": "Next Year"
            }

            return mapping.get(
                str(label).strip().lower(),
                str(label)
            )

        def get_currency_symbol(curr):

            return {
                "USD": "$",
                "INR": "₹",
                "EUR": "€",
                "GBP": "£"
            }.get(
                str(curr).upper(),
                "₹"
            )

        # ---------------------------------------------------
        # FORMATTERS
        # ---------------------------------------------------

        def format_cr(value):

            val = safe_float(value)

            if val is None:
                return None

            return round(val / 10000000, 2)

        def format_currency_cr(value):

            val = format_cr(value)

            if val is None:
                return None

            return f"₹{val:,.0f} Cr"

        def format_market_cap(value):

            val = safe_float(value)

            if val is None:
                return None

            if val >= 1_000_000_000_000:
                return f"₹{round(val/1_000_000_000_000,2)}T"

            if val >= 1_000_000_000:
                return f"₹{round(val/1_000_000_000,2)}B"

            return f"₹{round(val/1_000_000,2)}M"

        def clean_company_name(name):

            if not name:
                return None

            replacements = {
                "SERV": "Services",
                "SVCS": "Services",
                "TECH": "Technology",
                "INFOTECH": "Infotech",
                "LT": "Ltd",
                "LTD": "Ltd"
            }

            words = name.title().split()

            cleaned = []

            for w in words:

                cleaned.append(
                    replacements.get(
                        w.upper(),
                        w
                    )
                )

            return " ".join(cleaned)

        # ---------------------------------------------------
        # REVENUE EXTRACTION
        # ---------------------------------------------------

        def extract_revenue(df, col):

            if df is None or df.empty:
                return None

            priority = [
                "Total Revenue",
                "Revenue",
                "Revenue From Operations",
                "Operating Revenue",
                "OperatingRevenue",
                "Net Sales",
                "Sales"
            ]

            # exact matches
            for key in priority:

                if key in df.index:

                    val = safe_float(
                        df.loc[key, col]
                    )

                    if val is not None:
                        return val

            # fuzzy revenue
            for idx in df.index:

                idx_lower = str(idx).lower()

                if "revenue" in idx_lower:

                    val = safe_float(
                        df.loc[idx, col]
                    )

                    if val is not None:
                        return val

            # fuzzy sales
            for idx in df.index:

                idx_lower = str(idx).lower()

                if "sales" in idx_lower:

                    val = safe_float(
                        df.loc[idx, col]
                    )

                    if val is not None:
                        return val

            return None

        # ---------------------------------------------------
        # CLOSEST REVENUE
        # ---------------------------------------------------

        def get_closest_revenue(
            earnings_date,
            q_income
        ):

            if q_income is None or q_income.empty:
                return None

            try:

                ed = pd.to_datetime(
                    earnings_date
                ).tz_localize(None)

                cols = []

                for col in q_income.columns:

                    try:

                        col_dt = pd.to_datetime(
                            col
                        ).tz_localize(None)

                        cols.append((col_dt, col))

                    except:
                        continue

                cols.sort()

                selected_col = None

                for dt, col in cols:

                    if dt <= ed:
                        selected_col = col
                    else:
                        break

                if selected_col is None:
                    return None

                return extract_revenue(
                    q_income,
                    selected_col
                )

            except:
                return None

        # ---------------------------------------------------
        # FILL MISSING QUARTERS
        # ---------------------------------------------------

        def fill_missing_quarters(data):

            if not data:
                return data

            filled = []

            for i in range(len(data) - 1):

                current = data[i]
                nxt = data[i + 1]

                filled.append(current)

                try:

                    cq = int(current["quarter"][1])
                    cy = int(current["quarter"][-4:])

                    nq = int(nxt["quarter"][1])
                    ny = int(nxt["quarter"][-4:])

                    diff = (ny - cy) * 4 + (nq - cq)

                    if diff > 1:

                        for j in range(1, diff):

                            q = cq + j
                            y = cy

                            if q > 4:
                                q -= 4
                                y += 1

                            filled.append({
                                "quarter": f"Q{q} {y}",
                                "date": None,
                                "revenue": None,
                                "revenue_display": None
                            })

                except:
                    pass

            filled.append(data[-1])

            return filled

        # ---------------------------------------------------
        # LATEST EARNINGS
        # ---------------------------------------------------

        latest = None

        if (
            earnings_dates is not None
            and not earnings_dates.empty
        ):

            reported = earnings_dates[
                earnings_dates["Reported EPS"].notna()
            ]

            latest = (
                reported.iloc[0]
                if not reported.empty
                else earnings_dates.iloc[0]
            )

        # ---------------------------------------------------
        # EPS
        # ---------------------------------------------------

        actual_eps = (
            safe_float(
                latest.get("Reported EPS")
            )
            if latest is not None
            else None
        )

        est_eps = (
            safe_float(
                latest.get("EPS Estimate")
            )
            if latest is not None
            else None
        )

        beat = None
        beat_percent = None

        if (
            actual_eps is not None
            and est_eps is not None
            and est_eps != 0
        ):

            beat = round(
                actual_eps - est_eps,
                2
            )

            beat_percent = round(
                (beat / abs(est_eps)) * 100,
                2
            )

        # ---------------------------------------------------
        # LATEST REVENUE
        # ---------------------------------------------------

        latest_revenue = None

        if (
            q_income is not None
            and not q_income.empty
        ):

            sorted_cols = sorted(
                list(q_income.columns),
                key=lambda x: pd.to_datetime(x),
                reverse=True
            )

            for col in sorted_cols:

                latest_revenue = extract_revenue(
                    q_income,
                    col
                )

                if latest_revenue:
                    break

        # ---------------------------------------------------
        # PRICE
        # ---------------------------------------------------

        current_price = safe_float(
            info.get("currentPrice")
        )

        previous_close = safe_float(
            info.get("previousClose")
        )

        change = None
        change_percent = None

        if (
            current_price is not None
            and previous_close is not None
        ):

            change = round(
                current_price - previous_close,
                2
            )

            if previous_close != 0:

                change_percent = round(
                    (change / previous_close) * 100,
                    2
                )

        # ---------------------------------------------------
        # SUMMARY
        # ---------------------------------------------------

        company_name = clean_company_name(
            info.get("shortName")
        )

        summary = {

            "company_name": company_name,

            "symbol": symbol.upper(),

            "exchange": "NSE",

            "currency": info.get(
                "currency",
                "INR"
            ),

            "current_price": current_price,

            "current_price_display":
                f"₹{current_price:,.2f}"
                if current_price is not None
                else None,

            "price_change": change,

            "price_change_percent":
                change_percent,

            "price_direction":
                "up"
                if change is not None and change >= 0
                else "down",

            "latest_earnings_date":
                str(
                    pd.to_datetime(
                        latest.name
                    ).date()
                )
                if latest is not None
                else None,

            "quarter":
                get_quarter_label(
                    latest.name
                )
                if latest is not None
                else None,

            "consensus_eps":
                est_eps,

            "actual_eps":
                actual_eps,

            "beat":
                beat,

            "beat_percent":
                beat_percent,

            "beat_direction":
                (
                    "beat"
                    if beat is not None and beat >= 0
                    else "miss"
                ),

            "actual_revenue":
                format_cr(
                    latest_revenue
                ),

            "actual_revenue_display":
                format_currency_cr(
                    latest_revenue
                ),

            "market_cap":
                safe_float(
                    info.get("marketCap")
                ),

            "market_cap_display":
                format_market_cap(
                    info.get("marketCap")
                ),

            "sector":
                info.get("sector"),

            "industry":
                info.get("industry"),

            "website":
                info.get("website"),

            "logo_url":
                info.get("logo_url")
        }

        # ---------------------------------------------------
        # SUMMARY TEXT
        # ---------------------------------------------------

        cs = get_currency_symbol(
            summary["currency"]
        )

        if (
            actual_eps is not None
            and est_eps is not None
        ):

            direction = (
                "beating"
                if beat >= 0
                else "missing"
            )

            summary["summary_text"] = (
                f"{company_name} reported EPS "
                f"of {cs}{actual_eps}, "
                f"{direction} analyst estimates "
                f"by {cs}{abs(beat)} "
                f"({round(beat_percent,2)}%) "
                f"for {summary['quarter']}."
            )

        # ---------------------------------------------------
        # EPS CHART
        # ---------------------------------------------------

        eps_chart = []

        if (
            earnings_dates is not None
            and not earnings_dates.empty
        ):

            df = earnings_dates.head(8)

            for idx, row in reversed(
                list(df.iterrows())
            ):

                idx_dt = pd.to_datetime(idx)

                eps_chart.append({

                    "date":
                        str(idx_dt.date()),

                    "quarter":
                        get_quarter_label(idx_dt),

                    "estimate_eps":
                        safe_float(
                            row.get(
                                "EPS Estimate"
                            )
                        ),

                    "actual_eps":
                        safe_float(
                            row.get(
                                "Reported EPS"
                            )
                        )
                })

        # ---------------------------------------------------
        # REVENUE CHART
        # ---------------------------------------------------

        revenue_chart = []

        if (
            q_income is not None
            and not q_income.empty
        ):

            sorted_cols = sorted(
                list(q_income.columns),
                key=lambda x: pd.to_datetime(x)
            )[-8:]

            for col in sorted_cols:

                col_dt = pd.to_datetime(col)

                revenue_val = extract_revenue(
                    q_income,
                    col
                )

                revenue_chart.append({

                    "date":
                        str(col_dt.date()),

                    "quarter":
                        get_quarter_label(col_dt),

                    "revenue":
                        format_cr(revenue_val),

                    "revenue_display":
                        format_currency_cr(
                            revenue_val
                        )
                })

            revenue_chart = fill_missing_quarters(
                revenue_chart
            )

        # ---------------------------------------------------
        # EARNINGS HISTORY TABLE
        # ---------------------------------------------------

        earnings_history_table = []

        if (
            earnings_dates is not None
            and not earnings_dates.empty
        ):

            df = earnings_dates.head(12)

            for idx, row in df.iterrows():

                idx_dt = pd.to_datetime(idx)

                est = safe_float(
                    row.get("EPS Estimate")
                )

                act = safe_float(
                    row.get("Reported EPS")
                )

                beat_val = None

                if (
                    est is not None
                    and act is not None
                ):

                    beat_val = round(
                        act - est,
                        2
                    )

                revenue = safe_float(
                    row.get(
                        "Reported Revenue"
                    )
                )

                if revenue is None:

                    revenue = get_closest_revenue(
                        idx_dt,
                        q_income
                    )

                earnings_history_table.append({

                    "date":
                        str(idx_dt.date()),

                    "quarter":
                        get_quarter_label(idx_dt),

                    "consensus_eps":
                        est,

                    "reported_eps":
                        act,

                    "beat":
                        beat_val,

                    "beat_direction":
                        (
                            "beat"
                            if beat_val is not None and beat_val >= 0
                            else "miss"
                        ),

                    "surprise_percent":
                        safe_float(
                            row.get(
                                "Surprise(%)"
                            )
                        ),

                    "actual_revenue":
                        format_cr(revenue),

                    "actual_revenue_display":
                        format_currency_cr(
                            revenue
                        )
                })

        # ---------------------------------------------------
        # ANALYST ESTIMATES
        # ---------------------------------------------------

        analyst_estimates_table = []

        earnings_forecasts = None

        try:

            if hasattr(
                ticker,
                "earnings_estimate"
            ):

                earnings_forecasts = (
                    ticker.earnings_estimate
                )

            elif hasattr(
                ticker,
                "earnings_forecasts"
            ):

                earnings_forecasts = (
                    ticker.earnings_forecasts
                )

        except:
            pass

        if (
            earnings_forecasts is not None
            and not earnings_forecasts.empty
        ):

            for idx, row in earnings_forecasts.iterrows():

                def get_field(r, keys):

                    for k in keys:

                        if k in r:
                            return safe_float(
                                r.get(k)
                            )

                    return None

                num_analysts = get_field(
                    row,
                    [
                        "No. of Analysts",
                        "numberOfAnalysts",
                        "No. of analysts"
                    ]
                )

                analyst_estimates_table.append({

                    "quarter":
                        map_analyst_quarter_label(
                            idx
                        ),

                    "low_eps":
                        get_field(
                            row,
                            [
                                "Low Estimate",
                                "low"
                            ]
                        ),

                    "high_eps":
                        get_field(
                            row,
                            [
                                "High Estimate",
                                "high"
                            ]
                        ),

                    "avg_eps":
                        get_field(
                            row,
                            [
                                "Avg Estimate",
                                "avg"
                            ]
                        ),

                    "num_analysts":
                        int(num_analysts)
                        if num_analysts is not None
                        else None
                })

        # ---------------------------------------------------
        # RESOURCES
        # ---------------------------------------------------

        resources = [
            {
                "type": "report",
                "label": "Quarterly Report",
                "url": None
            },
            {
                "type": "transcript",
                "label": "Conference Call",
                "url": None
            },
            {
                "type": "press",
                "label": "Press Release",
                "url": None
            },
            {
                "type": "filing",
                "label": "Exchange Filing",
                "url": None
            }
        ]

        # ---------------------------------------------------
        # FINAL 
        # ---------------------------------------------------

        return ({

            "success": True,

            "summary":
                summary,

            "resources":
                resources,

            "eps_estimate_vs_actual_chart":
                eps_chart,

            "revenue_chart":
                revenue_chart,

            "earnings_history_table":
                earnings_history_table,

            "analyst_estimates_table":
                analyst_estimates_table
        })

    except Exception as e:

        import traceback

        traceback.print_exc()

        return({
            "success": False,
            "error": str(e)
        }), 500

def insert_stock_earnings(symbol: str, dry_run: bool, skip_existing: bool):

    pk = f"SYMBOL#{symbol}"
    sk = f"EARNINGS#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-earnings"], pk, "EARNINGS"):
        print(f"    [SKIP] stock-earnings for {symbol} already exists today")
        return

    print(f"  Fetching stock-earnings for {symbol}...")

    data = earnings_page(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-earnings"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "EARNINGS#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-earnings for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()
HEADLINES_CACHE: dict = {}
CACHE_TTL       = 900   # 15 minutes
MAX_CACHE_SIZE  = 100


def _cache_set(key: str, value: dict) -> None:
    """Store value; evict oldest entry when cache is full."""
    if len(HEADLINES_CACHE) >= MAX_CACHE_SIZE:
        oldest = min(HEADLINES_CACHE, key=lambda k: HEADLINES_CACHE[k][1])
        del HEADLINES_CACHE[oldest]
    HEADLINES_CACHE[key] = (value, time.time())


def _cache_get(key: str):
    """Return cached value if still fresh, else None."""
    entry = HEADLINES_CACHE.get(key)
    if entry and (time.time() - entry[1]) < CACHE_TTL:
        return entry[0]
    return None


# ─────────────────────────────────────────────
# HF BATCH CALL  (single round-trip for all articles)
# ─────────────────────────────────────────────
def _fetch_hf_batch(symbol: str, company_name: str, articles: list[dict]) -> list[dict]:
    """
    Send ALL articles in one POST.
    Returns a list of analysis dicts in the same order.
    Falls back to empty dicts on any error so the route never crashes.
    """
    if not articles:
        return []

    payload = {
        "symbol":       symbol,
        "company_name": company_name,
        "articles":     articles,   # list of {title, summary}
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f"{HF_BASE_URL}/analyze-news-batch",
                headers=HF_HEADERS,
                json=payload,
                timeout=60,          # HF cold-start can be ~30 s
            )

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                # Pad with empty dicts if HF returned fewer items
                while len(results) < len(articles):
                    results.append({})
                return results

            if resp.status_code == 503:
                print(f"[HF BATCH] 503 cold-start, waiting… (attempt {attempt+1})")
                time.sleep(12)
                continue

            print(f"[HF BATCH] HTTP {resp.status_code}")
            break

        except requests.Timeout:
            print(f"[HF BATCH] Timeout attempt {attempt+1}")
            if attempt < 2:
                time.sleep(5)

        except Exception as exc:
            print(f"[HF BATCH] Unexpected error: {exc}")
            break

    return [{} for _ in articles]   # safe fallback


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def _normalize_sentiment(label: str) -> str:
    label = str(label or "").lower()
    if label in {"bullish", "positive", "buy"}:
        return "bullish"
    if label in {"bearish", "negative", "sell"}:
        return "bearish"
    return "neutral"


def _parse_image(item: dict) -> str | None:
    resolutions = item.get("thumbnail", {}).get("resolutions", [])
    return resolutions[0].get("url") if resolutions else None


def _parse_published_at(item: dict) -> str | None:
    ts = item.get("providerPublishTime")
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return None


def _filter_relevant_news(raw_news: list, company_name: str) -> list:
    """
    Keep articles that mention at least one keyword from the company name.
    Falls back to all articles if the filter would remove everything.
    """
    keywords = [w.lower() for w in company_name.split() if len(w) > 2]
    if not keywords:
        return raw_news

    filtered = [
        n for n in raw_news
        if any(kw in (n.get("title", "") + n.get("summary", "")).lower() for kw in keywords)
    ]
    return filtered if filtered else raw_news


def _deduplicate(news: list) -> list:
    seen, out = set(), []
    for item in news:
        key = (item.get("title") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _overall_sentiment(bullish: int, bearish: int, neutral: int):
    """
    Score: 0 = fully bearish, 50 = neutral, 100 = fully bullish
    """
    total = bullish + bearish + neutral
    if total == 0:
        return "Neutral", 50

    score = round(((bullish - bearish) / total) * 50 + 50, 2)

    if bullish > bearish:
        label = "Bullish"
    elif bearish > bullish:
        label = "Bearish"
    else:
        label = "Neutral"

    return label, score


# ─────────────────────────────────────────────
# ROUTE
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# GOOGLE RSS NEWS FETCHER
# ─────────────────────────────────────────────

TRUSTED_SOURCES = {
    "Reuters",
    "Bloomberg",
    "CNBC",
    "Moneycontrol",
    "The Economic Times",
    "Economic Times",
    "LiveMint",
    "Mint",
    "Business Standard",
    "Financial Express",
    "The Hindu BusinessLine",
    "BusinessLine",
    "NDTV Profit",
    "CNBC TV18",
    "ETMarkets",
    "Zee Business",
    "India Today",
    "Yahoo Finance",
    "MarketScreener",
    "Seeking Alpha",
    "Benzinga",
    "The Motley Fool",
    "Simply Wall St",
    "simplywall.st",
    "Tata Consultancy Services",
}


def clean_html(text: str) -> str:
    """
    Remove HTML tags/entities from RSS summaries.
    """

    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r"<.*?>", "", text)

    # Common HTML entities
    text = (
        text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
    )

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def fetch_google_rss_news(company_name: str, limit: int = 15):
    """
    Fetch company news using Google News RSS.
    Optimized for NSE / Indian equities.
    """

    query = urllib.parse.quote(
        f'"{company_name}" stock OR share OR NSE OR earnings'
    )

    url = (
        f"https://news.google.com/rss/search?"
        f"q={query}"
        f"&hl=en-IN&gl=IN&ceid=IN:en"
    )

    try:
        feed = feedparser.parse(url)

        if getattr(feed, "bozo", 0):
            print(f"[Google RSS] Parsing warning: {feed.bozo}")

        articles = []
        seen_titles = set()

        for entry in feed.entries:

            # ─────────────────────────────────
            # Publisher
            # ─────────────────────────────────
            source_name = "Google News"

            if isinstance(entry.get("source"), dict):
                source_name = entry.get("source", {}).get("title", "Google News")

            elif isinstance(entry.get("source"), str):
                source_name = entry.get("source")

            source_name = (source_name or "").strip()

            # ─────────────────────────────────
            # Trusted-source filtering
            # ─────────────────────────────────
            # Trusted-source fuzzy matching
            print(f"[RSS SOURCE] {source_name}")
            source_lower = source_name.lower()

            is_trusted = any(
                trusted.lower() in source_lower
                for trusted in TRUSTED_SOURCES
            )

            if not is_trusted:
                continue

            # ─────────────────────────────────
            # Title cleanup
            # ─────────────────────────────────
            title = clean_html(entry.get("title", ""))

            if not title:
                continue

            title_key = title.lower().strip()

            if title_key in seen_titles:
                continue

            seen_titles.add(title_key)

            # ─────────────────────────────────
            # Summary & Image extraction
            # ─────────────────────────────────
            raw_summary = entry.get("summary", "")
            summary     = clean_html(raw_summary)
            
            # Try to extract image from raw summary HTML
            img_url = None
            try:
                soup = BeautifulSoup(raw_summary, "html.parser")
                img_tag = soup.find("img")
                if img_tag and img_tag.get("src"):
                    img_url = img_tag.get("src")
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
            except:
                pass

            # Fallback summary
            if not summary:
                summary = title

            # ─────────────────────────────────
            # Published timestamp
            # ─────────────────────────────────
            published_ts = None
            try:
                if entry.get("published_parsed"):
                    published_ts = int(
                        datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp()
                    )
                    
                elif entry.get("published"):
                    # fallback: parse the raw string
                    from email.utils import parsedate_to_datetime
                    published_ts = int(parsedate_to_datetime(entry.published).timestamp())
                    
            except Exception as e:
                print(f"[RSS DEBUG] timestamp parse error: {e}")
                published_ts = None

            # ─────────────────────────────────
            # Final article
            # ─────────────────────────────────
            articles.append({
                "title": title,
                "summary": summary,
                "publisher": source_name,
                "link": entry.get("link", ""),
                "providerPublishTime": published_ts,
                "thumbnail": {
                    "resolutions": [{"url": img_url}] if img_url else []
                }
            })

            # Limit
            if len(articles) >= limit:
                break

        print(f"[Google RSS] Retrieved {len(articles)} trusted articles")

        return articles

    except Exception as e:
        print(f"[Google RSS] Error: {e}")
        return []

def fetch_gnews_news(company_name: str, limit: int = 10):
    """
    Fetch news from GNews API.
    Good coverage for Indian equities.
    """

    query = urllib.parse.quote(company_name)

    url = (
        f"https://gnews.io/api/v4/search?"
        f"q={query}"
        f"&lang=en"
        f"&country=in"
        f"&max={limit}"
        f"&apikey={GNEWS_API_KEY}"
    )

    try:
        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            print(f"[GNews] HTTP {resp.status_code}")
            return []

        data = resp.json()

        articles = []

        for item in data.get("articles", []):

            source_name = (
                item.get("source", {})
                .get("name", "GNews")
            )
            published_ts = None
            try:
                pub = item.get("publishedAt") # e.g. "2026-05-29T11:13:31Z"
                
                if pub:
                    published_ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                    
            except Exception:
                print(f"[GNEWS DEBUG] parse error: {e}")

            articles.append({
                "title": item.get("title", ""),
                "summary": item.get("description", ""),
                "publisher": source_name,
                "link": item.get("url", ""),
                "providerPublishTime": published_ts,
                "thumbnail": {
                    "resolutions": (
                        [{"url": item.get("image")}]
                        if item.get("image")
                        else []
                    )
                }
            })

        print(f"[GNews] Retrieved {len(articles)} articles")

        return articles

    except Exception as e:
        print(f"[GNews] Error: {e}")
        return []

def fetch_newsapi_news(company_name: str, limit: int = 10):
    """
    Fetch news using NewsAPI.
    """

    query = urllib.parse.quote(company_name)

    url = (
        f"https://newsapi.org/v2/everything?"
        f"q={query}"
        f"&language=en"
        f"&pageSize={limit}"
        f"&sortBy=publishedAt"
        f"&apiKey={NEWSAPI_KEY}"
    )

    try:
        resp = requests.get(url, timeout=15)

        if resp.status_code != 200:
            print(f"[NewsAPI] HTTP {resp.status_code}")
            return []

        data = resp.json()

        articles = []

        for item in data.get("articles", []):
            published_ts = None
            try:
                pub = item.get("publishedAt")  # e.g. "2026-05-29T11:13:31Z"
                if pub:
                    published_ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
            except Exception:
                print(f"[NewsAPI DEBUG] parse error: {e}")

            articles.append({
                "title": item.get("title", ""),
                "summary": item.get("description", ""),
                "publisher": (
                    item.get("source", {})
                    .get("name", "NewsAPI")
                ),
                "link": item.get("url", ""),
                "providerPublishTime": published_ts,
                "thumbnail": {
                    "resolutions": (
                        [{"url": item.get("urlToImage")}]
                        if item.get("urlToImage")
                        else []
                    )
                }
            })

        print(f"[NewsAPI] Retrieved {len(articles)} articles")

        return articles

    except Exception as e:
        print(f"[NewsAPI] Error: {e}")
        return []


def headlines_page(symbol: str):

    symbol = symbol.upper().strip()

    # ── Cache hit ──────────────────────────────
    cached = _cache_get(symbol)
    if cached:
        return (cached)

    try:
        # ── Stock info ─────────────────────────
               # your existing helper
        ticker = yf.Ticker(get_yf_symbol(symbol))
        info   = ticker.info or {}

        company_name = info.get("longName") or info.get("shortName") or symbol

        # ── Logo Fallback ───────────────────────
        logo_url = info.get("logo_url")
        if not logo_url and info.get("website"):
            domain = info.get("website").replace("https://", "").replace("http://", "").split("/")[0]
            if domain:
                logo_url = f"https://logo.clearbit.com/{domain}"

        company_meta = {
            "sector":               info.get("sector"),
            "industry":             info.get("industry"),
            "logo_url":             logo_url,
            "market_cap":           info.get("marketCap"),
            "current_price":        info.get("currentPrice") or info.get("regularMarketPrice"),
            "price_change":         info.get("regularMarketChange"),
            "price_change_percent": info.get("regularMarketChangePercent"),
        }

        # ── Fetch raw news ─────────────────────
        # ── Multi-source news fetch ─────────────────

        rss_news     = fetch_google_rss_news(company_name, limit=15)
        gnews_news   = fetch_gnews_news(company_name, limit=10)
        newsapi_news = fetch_newsapi_news(company_name, limit=10)

        raw_news = (
            rss_news +
            gnews_news +
            newsapi_news
        )

        print(
            f"[News Sources] "
            f"RSS={len(rss_news)} | "
            f"GNews={len(gnews_news)} | "
            f"NewsAPI={len(newsapi_news)}"
        )

        # Emergency fallback
        if not raw_news:
            print(f"[News] All APIs empty for {symbol}, trying yfinance")
            raw_news = ticker.news or []

        if not raw_news:
            result = {
                "success":      True,
                "symbol":       symbol,
                "company_name": company_name,
                "company_meta": company_meta,
                "news_count":   0,
                "overall_sentiment":      {"label": "Neutral", "score": 50},
                "sentiment_distribution": {"bullish": 0, "neutral": 0, "bearish": 0},
                "top_topics":             [],
                "ai_market_insights":     [],
                "news":                   [],
            }
            _cache_set(symbol, result)
            return (result)

        # ── Clean & filter ─────────────────────
        clean_news = _deduplicate(raw_news)
        clean_news = _filter_relevant_news(clean_news, company_name)

        # ── Build article payloads ─────────────
        article_payloads = [
            {
                "title":   (item.get("title") or "").strip(),
                "summary": (item.get("summary") or "").strip(),
            }
            for item in clean_news
        ]

        # ── ONE batch call to HF ───────────────
        hf_results = _fetch_hf_batch(symbol, company_name, article_payloads)

        # ── Build news cards ───────────────────
        news_cards    = []
        bullish_count = bearish_count = neutral_count = 0
        topic_counter: dict[str, int] = defaultdict(int)

        for idx, (item, hf) in enumerate(zip(clean_news, hf_results)):

            sentiment_label = _normalize_sentiment(hf.get("sentiment", "neutral"))

            if sentiment_label == "bullish":
                bullish_count += 1
            elif sentiment_label == "bearish":
                bearish_count += 1
            else:
                neutral_count += 1

            topics = hf.get("topics") or []
            for t in topics:
                topic_counter[t] += 1

            news_cards.append({
                "id":           f"{symbol}_{idx}",
                "title":        item.get("title"),
                "summary":      hf.get("summary") or item.get("summary") or item.get("title"),
                "source":       item.get("publisher") or "Unknown",
                "published_at": _parse_published_at(item),
                "url":          item.get("link"),
                "image":        _parse_image(item),
                "sentiment": {
                    "label":      sentiment_label,
                    "confidence": hf.get("confidence"),
                },
                "impact":    hf.get("impact", "Medium"),
                "action":    hf.get("action", "Watch"),
                "learnings": hf.get("learnings") or [],
                "topics":    topics,
            })

        # ── Aggregates ─────────────────────────
        overall_label, overall_score = _overall_sentiment(
            bullish_count, bearish_count, neutral_count
        )

        top_topics = [
            {"topic": k, "count": v}
            for k, v in sorted(topic_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        ai_market_insights = []
        if overall_label == "Bullish":
            ai_market_insights.append(f"News sentiment around {company_name} is currently bullish.")
        elif overall_label == "Bearish":
            ai_market_insights.append(f"Recent headlines indicate bearish sentiment around {company_name}.")
        else:
            ai_market_insights.append(f"Market sentiment around {company_name} remains neutral.")

        if top_topics:
            ai_market_insights.append(f"Most discussed topic: {top_topics[0]['topic']}.")

        # ── Final  ─────────────────────
        result = {
            "success":      True,
            "symbol":       symbol,
            "company_name": company_name,
            "company_meta": company_meta,
            "news_count":   len(news_cards),
            "overall_sentiment": {
                "label": overall_label,
                "score": overall_score,
            },
            "sentiment_distribution": {
                "bullish": bullish_count,
                "neutral": neutral_count,
                "bearish": bearish_count,
            },
            "top_topics":         top_topics,
            "ai_market_insights": ai_market_insights,
            "news":               news_cards,
        }

        _cache_set(symbol, result)
        return (result)

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return ({"success": False, "error": str(exc)}), 500    

def insert_stock_headlines(symbol: str, dry_run: bool, skip_existing: bool):

    pk = f"SYMBOL#{symbol}"
    sk = f"HEADLINES#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-headlines"], pk, "HEADLINES"):
        print(f"    [SKIP] stock-headlines for {symbol} already exists today")
        return

    print(f"  Fetching stock-headlines for {symbol}...")

    data = headlines_page(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-headlines"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "HEADLINES#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-headlines for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()


def _article_key(article: dict) -> str:
    """Same article always produces the same key — makes the archive
    write idempotent (safe to insert repeatedly)."""
    url = article.get("url") or article.get("link") or ""
    published = article.get("published_at") or ""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    return f"ARTICLE#{published}#{url_hash}"


def save_headlines_snapshot(symbol: str):
    pk = f"SYMBOL#{symbol}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = headlines_page(symbol)
    if not data or not data.get("news"):
        print(f"    [SKIP] No headlines data for {symbol}")
        return

    table = get_dynamo().Table(TABLES["stock-headlines"])

    # 1. LATEST — the current full page (overwritten every run — this is
    #    what your live endpoint will read to show users right now)
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "HEADLINES#<date>": "LATEST",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
    })

    # 2. One permanent row PER unique article — insert only if new
    new_count = 0
    for article in data.get("news", []):
        key = _article_key(article)
        try:
            table.put_item(
                Item={
                    "SYMBOL#<sym>": pk,
                    "HEADLINES#<date>": key,
                    "first_seen_at": now_iso,
                    "data": _to_dynamo(article),
                    # no ttl — these are permanent, for ML/AI use
                },
                ConditionExpression="attribute_not_exists(#pk)",
                ExpressionAttributeNames={"#pk": "SYMBOL#<sym>"},
            )
            new_count += 1
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                pass  # already archived — expected, not an error
            else:
                raise

    print(f"    [OK] Headlines LATEST updated, {new_count} new article(s) archived for {symbol}")

COMPETITORS_CACHE = {}


def _fetch_hf_sentiment(symbol: str) -> dict:
    """Returns the full HF payload for a symbol: {news, chart_data, competitors, summary}"""
    try:
        url = f"{HF_BASE_URL}/sentiment/{symbol.upper()}"
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
    Each hf_payload["chart_data"] looks like:
      { "TCS": [{date, score}, ...], "INFY": [{date, score}, ...], ... }

    Merges everything into flat rows:
      [{date: "2026-03-30", TCS: 1.0, INFY: 1.35, ...}, ...]
    """
    date_row = {}  # date → {sym: score}

    for sym, payload in all_payloads.items():
        chart_data = payload.get("chart_data", {})
        # Use this ticker's own chart_data entry
        entries = chart_data.get(sym, [])
        for entry in entries:
            d = entry.get("date")
            s = entry.get("score", 1.0)
            if d:
                if d not in date_row:
                    date_row[d] = {"date": d}
                date_row[d][sym] = s

    return sorted(date_row.values(), key=lambda r: r["date"])

def _build_sentiment_chart(all_articles: list, symbols: list) -> list:
    """
    Aggregate article scores by calendar week → list of
    {date: 'YYYY-MM-DD', SYM1: score, SYM2: score, ...}
    Pads the last 5 weeks so the chart always has a baseline.
    """
    weekly: dict = defaultdict(lambda: defaultdict(list))

    # Pre-fill last 5 weeks so X-axis is always populated
    today = datetime.now()
    this_monday = today - timedelta(days=today.weekday())
    for i in range(4, -1, -1):
        wk_key = (this_monday - timedelta(weeks=i)).strftime("%Y-%m-%d")
        weekly[wk_key]  # touch it so it exists

    for art in all_articles:
        sym  = art.get("symbol", "").upper()
        sent = art.get("sentiment", "neutral")
        score = SENTIMENT_SCORE.get(sent, 1.0)

        # Parse date from "time" field (ISO string like "2026-04-17T03:50:00Z")
        raw_time = art.get("time") or art.get("date") or ""
        try:
            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            week_start = dt - timedelta(days=dt.weekday())
            wk_key = week_start.strftime("%Y-%m-%d")
        except Exception:
            continue

        weekly[wk_key][sym].append(score)

    last_score = {s: 1.0 for s in symbols}
    chart = []
    for wk_key in sorted(weekly.keys()):
        row = {"date": wk_key}
        for sym in symbols:
            scores = weekly[wk_key].get(sym, [])
            if scores:
                avg = round(sum(scores) / len(scores), 3)
                last_score[sym] = avg
            row[sym] = last_score[sym]
        chart.append(row)

    return chart


def _build_sentiment_summary(all_articles: list, symbols: list) -> dict:
    summary = {}
    for sym in symbols:
        arts = [a for a in all_articles if a.get("symbol", "").upper() == sym.upper()]
        if arts:
            avg = sum(SENTIMENT_SCORE.get(a.get("sentiment", "neutral"), 1.0) for a in arts) / len(arts)
            summary[sym] = "bullish" if avg > 1.15 else "bearish" if avg < 0.85 else "neutral"
        else:
            summary[sym] = "neutral"
    return summary


def competitors_page(symbol):

    global COMPETITORS_CACHE
    now = time.time()
    if symbol in COMPETITORS_CACHE:
        cached_data, ts = COMPETITORS_CACHE[symbol]
        if now - ts < 600:
            return (cached_data)

    try:
        ticker = yf.Ticker(get_yf_symbol(symbol))
        info   = ticker.info or {}
        company_name = info.get("longName") or symbol
        sector = info.get("sector")

        if not sector:
            return ({"error": "Sector not found for this symbol"})

        # ── Find competitors (unchanged from original) ────────────────────────
        CSV_PATH    = os.path.join(os.path.dirname(__file__), "stock_list.csv")
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

            # yfinance multi-ticker downloads occasionally return all-zero
            # Volume for one symbol even when actual trade data exists.
            # Retry once to get correct volume figures.
            if not df.empty and "Volume" in df.columns:
                _vol_check = (df["Volume"][main_yf_sym] if isinstance(df.columns, pd.MultiIndex)
                              else df["Volume"])
                if isinstance(_vol_check, pd.Series) and _vol_check.sum() == 0:
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
                        # Skip today's bar when volume is 0 — it is an incomplete
                        # intra-day / pre-open row that will mismatch the live
                        # endpoint once actual trades are recorded.
                        if row.get("Volume", -1) == 0 and str(d.date()) == str(date_type.today()):
                            continue
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
        return (result_dict)

    except Exception as e:
        return ({"error": str(e)})

def insert_stock_competitors(symbol:str, dry_run:bool, skip_existing:bool):
    
    pk = f"SYMBOL#{symbol}"
    sk = f"COMPETITORS#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-competitors"], pk, "COMPETITORS"):
        print(f"    [SKIP] stock-competitors for {symbol} already exists today")
        return

    print(f"  Fetching stock-competitors for {symbol}...")

    data = competitors_page(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-competitors"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "COMPETITORS#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-competitors for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()

def options_chain(symbol, expiry=None):
    symbol = symbol.upper()
    target_expiry = expiry

    try:
        result = OptionsService.get_options_chain(symbol)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Failed to fetch options data")
            }

        normalized = OptionsService.normalize_options_data(
            result.get("data", []),
            target_expiry=target_expiry
        )

        if not normalized:
            return {
                "success": False,
                "error": f"No options data found for {symbol}"
            }

        return {
            "success": True,
            "symbol": symbol,
            "available_expiries": normalized["available_expiries"],
            "selected_expiry": normalized["selected_expiry"],
            "total_rows": normalized["total_rows"],
            "data": normalized["data"]
        }

    except Exception as e:
        print(f"Options Route Error: {str(e)}")
        return {
            "success": False,
            "error": "Internal server error while processing options"
        }
def insert_stock_options(symbol: str, expiry: str, dry_run: bool, skip_existing: bool):
    """
    Stores NSE Options chain data in DynamoDB.
    """
    symbol = symbol.upper()
    pk = f"SYMBOL#{symbol}"
    sk = f"OPTIONS#{expiry or datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-options"], pk, "OPTIONS"):
        print(f"    [SKIP] stock-options for {symbol} already exists today")
        return

    print(f"  Fetching stock-options for {symbol}...")

    data = options_chain(symbol,expiry)

    if not data or not data.get("success"):
        print(f"    [SKIP] Options fetch failed: {data.get('error', 'no data') if data else 'empty response'}")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-options"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "OPTIONS#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-options for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()

def save_options_snapshot(symbol: str, expiry: str = None):
    """Options chain is already 100% live data (OI, IV, volume, turnover) —
    nothing static to strip out, so this reuses options_chain() as-is.
    The Node OptionsService already caches for 60s on its own side, so a
    5-minute schedule here never causes a wasted duplicate NSE call."""
    pk = f"SYMBOL#{symbol}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ttl_value = int(time.time()) + (30 * 24 * 60 * 60)

    data = options_chain(symbol, expiry)
    if not data or not data.get("success"):
        print(f"    [SKIP] No live options data for {symbol}")
        return

    table = get_dynamo().Table(TABLES["stock-options"])

    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "OPTIONS#<date>": "LATEST",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
    })
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "OPTIONS#<date>": f"SNAPSHOT#{now_iso}",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
        "ttl": ttl_value,
    })
    print(f"    [OK] Options snapshot stored for {symbol}")

#---------------------------------------------------------------------------
# Load company list from stock_list.csv
# ---------------------------------------------------------------------------

BSE_BASE = "https://api.bseindia.com/BseIndiaAPI/api"
 
BSE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
    "Referer":         "https://www.bseindia.com/",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
 
# ---------------------------------------------------------------------------
# PDF URL patterns — tried in order for every download
# ---------------------------------------------------------------------------
 
BSE_PDF_PATTERNS = [
    "https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}",
    "https://www.bseindia.com/xml-data/corpfiling/AttachHis/{attach}",
    "https://www.bseindia.com/xml-data/corpfiling/Attachhis/{attach}",
]
 
# BSE's EXACT strCat string for financial results (singular, not "Results")
BSE_RESULT_CAT = "Result"
 
# ---------------------------------------------------------------------------
# Company list loader
# ---------------------------------------------------------------------------
 
def load_company_list(csv_path: str = None) -> dict:
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), "stock_list.csv")
    companies = {}
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                symbol = row.get("SYMBOL", "").strip().upper()
                if not symbol:
                    continue
                industry = row.get("INDUSTRY", "").strip()
                if industry == "#FIELD!":
                    industry = ""
                companies[symbol] = {
                    "name":     row.get("NAME OF COMPANY", "").strip(),
                    "sector":   row.get("SECTOR", "").strip(),
                    "industry": industry,
                    "bse_code": None,
                }
    except FileNotFoundError:
        pass
    return companies
 
 
# ---------------------------------------------------------------------------
# NSE symbol → BSE scrip code map
# ---------------------------------------------------------------------------
 
BSE_SCRIP_MAP = {
    "RELIANCE":   "500325",
    "TCS":        "532540",
    "INFY":       "500209",
    "HDFCBANK":   "500180",
    "ICICIBANK":  "532174",
    "SBIN":       "500112",
    "AXISBANK":   "532215",
    "KOTAKBANK":  "500247",
    "BAJFINANCE": "500034",
    "BAJAJFINSV": "532978",
    "LT":         "500510",
    "ITC":        "500875",
    "HINDUNILVR": "500696",
    "NESTLEIND":  "500790",
    "BRITANNIA":  "500825",
    "TITAN":      "500114",
    "MARUTI":     "532500",
    "EICHERMOT":  "505200",
    "HEROMOTOCO": "500182",
    "TATASTEEL":  "500470",
    "JSWSTEEL":   "500228",
    "ULTRACEMCO": "532538",
    "POWERGRID":  "532898",
    "NTPC":       "532555",
    "ONGC":       "500312",
    "SUNPHARMA":  "524715",
    "DRREDDY":    "500124",
    "CIPLA":      "500087",
    "DIVISLAB":   "532488",
    "APOLLOHOSP": "508869",
    "HCLTECH":    "532281",
    "TECHM":      "532755",
    "WIPRO":      "507685",
    "ADANIENT":   "512599",
    "ADANIPORTS": "532921",
    "COALINDIA":  "533278",
    "INDUSINDBK": "532187",
    "PIDILITIND": "500331",
    "ASIANPAINT": "500820",
    "GRASIM":     "500300",
}
 
# Load once at startup and attach BSE codes
COMPANY_LIST = load_company_list()
for _sym, _code in BSE_SCRIP_MAP.items():
    if _sym in COMPANY_LIST:
        COMPANY_LIST[_sym]["bse_code"] = _code
 
 
# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------
 
CATEGORY_MAP = {
    "financial result":              "Results",
    "result":                        "Results",
    "quarterly result":              "Results",
    "earnings call transcript":      "Results",
    "board meeting":                 "Board",
    "outcome of board":              "Board",
    "board":                         "Board",
    "dividend":                      "Dividend",
    "date of payment of dividend":   "Dividend",
    "record date":                   "Dividend",
    "agm":                           "AGM",
    "egm":                           "AGM",
    "annual general meeting":        "AGM",
    "extraordinary general":         "AGM",
    "insider":                       "Insider",
    "sast":                          "Insider",
    "shareholding":                  "Insider",
    "beneficial ownership":          "Insider",
    "trading window":                "Insider",
    "pit regulation":                "Insider",
    "acquisition":                   "Acquisition",
    "merger":                        "Acquisition",
    "buyback":                       "Acquisition",
    "incorporation":                 "Acquisition",
    "subsidiary":                    "Acquisition",
    "amalgamation":                  "Acquisition",
    "press release":                 "Press Release",
    "media release":                 "Press Release",
    "analyst":                       "Analyst / Investor Meet",
    "investor meet":                 "Analyst / Investor Meet",
    "reg.24":                        "Compliance",
    "secretarial compliance":        "Compliance",
    "lodr":                          "Compliance",
    "regulation 30":                 "Compliance",
    "newspaper publication":         "Compliance",
    "newspaper":                     "Compliance",
}
 
 
def map_category(raw: str) -> str:
    if not raw:
        return "General"
    lower = raw.lower()
    for key, val in CATEGORY_MAP.items():
        if key in lower:
            return val
    return raw.strip()[:40]
 
 
# ---------------------------------------------------------------------------
# Result filtering — whitelist approach
# ---------------------------------------------------------------------------
 
# Substrings of BSE's SUBCATNAME that confirm a genuine financial result
_RESULT_SUBCATEGORY_WHITELIST = [
    "financial result",
    "unaudited result",
    "audited result",
    "quarterly result",
    "half yearly result",
    "half-yearly result",
    "annual result",
    "standalone result",
    "consolidated result",
    "outcome of board meeting",
]

_HARD_EXCLUDE_CATEGORIES = [
    "investor presentation",
    "press release",
    "media release",
    "analyst / investor meet",
    "analyst/investor meet",
    "earnings call transcript",
    "agm",
    "postal ballot",
    "closure of trading window",
]

_HARD_EXCLUDE_HEADLINES = [
    "press release",
    "newspaper",
    "investor presentation",
    "earnings call",
    "transcript",
    "concall",
    "audio recording",
    "media release",
    "media statement",
]

_QUARTER_END_RE = re.compile(
    r"ended\s+(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"[^,0-9]{0,4}\d{0,2},?\s*(\d{4})",
    re.IGNORECASE,
)

_MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _quarter_end_key(description: str) -> str | None:
    """Pulls a stable 'YYYY-MM' key from phrases like 'ended June 30, 2025'.
    SEBI-mandated filings almost always spell this out, so it's a far more
    reliable grouping key than guessing a Q1-Q4 label — it ties directly
    to the real quarter-end date in the text, regardless of company."""
    m = _QUARTER_END_RE.search(description or "")
    if not m:
        return None
    month = _MONTH_NUM.get(m.group(1).lower())
    year = m.group(2)
    if not month:
        return None
    return f"{year}-{month:02d}"


# When a quarter has ZERO filings under the strict result categories,
# fall back to the best available substitute — Media Release (closer to
# an official numbers summary) before Investor Presentation (a slide deck).
_FALLBACK_CATEGORY_PRIORITY = [
    "press release / media release",
    "investor presentation",
]


def resolve_quarterly_filings(filings: list[dict]) -> set[str]:
    """Two-pass quarter resolution:
      1. Accept anything passing the strict is_quarterly_result() check.
      2. For any quarter that ended up with ZERO strict acceptances, pick
         the single best fallback candidate so that quarter isn't left
         with no PDF archived at all.
    Returns the set of filing keys that should have their PDF stored.
    """
    accepted = set()
    by_quarter = defaultdict(list)

    for f in filings:
        cat = f.get("category_raw", "")
        desc = f.get("description", "")
        key = _filing_key_for_insert(f)

        if is_quarterly_result(cat, desc):
            accepted.add(key)

        qkey = _quarter_end_key(desc)
        if qkey:
            by_quarter[qkey].append(f)

    for qkey, group in by_quarter.items():
        group_keys = {_filing_key_for_insert(f) for f in group}
        if group_keys & accepted:
            continue  # this quarter already has a real result filing

        best = None
        for wanted_cat in _FALLBACK_CATEGORY_PRIORITY:
            for f in group:
                if wanted_cat in f.get("category_raw", "").lower():
                    best = f
                    break
            if best:
                break

        if best:
            accepted.add(_filing_key_for_insert(best))

    return accepted


def is_quarterly_result(raw_category: str, headline: str) -> bool:
    h = headline.lower().strip()
    sub = raw_category.lower().strip()

    # Step 1 — exclude by CATEGORY first (most reliable, BSE's own taxonomy)
    if any(kw in sub for kw in _HARD_EXCLUDE_CATEGORIES):
        return False

    # Step 2 — exclude by headline (catches subsidiary media releases filed
    # under the generic "General" category, like the Karkinos/Jio ones above)
    if any(kw in h for kw in _HARD_EXCLUDE_HEADLINES):
        return False

    # Step 3 — accept only if it's actually the results document
    if any(wl in sub for wl in _RESULT_SUBCATEGORY_WHITELIST):
        return True

    return False
 
 
def detect_quarter(headline: str, date_raw: str) -> str | None:
    """
    Detect Q1/Q2/Q3/Q4 from headline, fallback to filing month.
    Indian FY: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
    """
    h = headline.lower()
 
    if "q1" in h or "june" in h or "apr-jun" in h or "april-june" in h or "first quarter" in h:
        return "Q1"
    if "q2" in h or "september" in h or "jul-sep" in h or "july-september" in h or "second quarter" in h:
        return "Q2"
    if "q3" in h or "december" in h or "oct-dec" in h or "october-december" in h or "third quarter" in h:
        return "Q3"
    if "q4" in h or "march" in h or "jan-mar" in h or "january-march" in h or "fourth quarter" in h:
        return "Q4"
    if "annual" in h or "full year" in h or "full-year" in h:
        return "Q4"
 
    # Fallback by filing month
    if date_raw:
        try:
            month = int(date_raw[5:7]) if "-" in date_raw else int(date_raw[4:6])
            if month in (7, 8):   return "Q1"
            if month in (10, 11): return "Q2"
            if month in (1, 2):   return "Q3"
            if month in (4, 5):   return "Q4"
        except (ValueError, IndexError):
            pass
 
    return None
 
 
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
 
def build_pdf_url(attach: str) -> str | None:
    if not attach:
        return None
    return f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}"
 
 
def get_bse_scrip(symbol: str) -> str | None:
    symbol = symbol.upper().strip()
    if symbol.isdigit():
        return symbol
    if symbol in BSE_SCRIP_MAP:
        return BSE_SCRIP_MAP[symbol]
    try:
        resp = requests.get(
            f"{BSE_BASE}/fetchCompanyNameForSymbol/w?Type=E&Scode={symbol}",
            headers=BSE_HEADERS, timeout=6,
        )
        table = resp.json().get("Table", [])
        if table:
            return str(table[0].get("SECURITY_CODE", ""))
    except Exception:
        pass
    return None
 
 
# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
 

def list_companies():
    if not COMPANY_LIST:
        return ({"error": "stock_list.csv not found in backend folder"}), 500
 
    companies = [
        {
            "symbol":   sym,
            "name":     info["name"],
            "sector":   info["sector"],
            "industry": info["industry"],
            "bse_code": info["bse_code"],
        }
        for sym, info in sorted(COMPANY_LIST.items(), key=lambda x: x[1]["name"])
    ]
    return ({"count": len(companies), "companies": companies})
 

def bse_filings(symbol):
    """
    Query params:
        from_date     YYYY-MM-DD  (default: 1 year ago)
        to_date       YYYY-MM-DD  (default: today)
        category      display-name filter, e.g. "Board", "Dividend"
        results_only  true | false  — genuine Q1-Q4 PDFs only
        limit         integer (optional)
    """
    today    = datetime.now()
    year_ago = today - timedelta(days=365)
 
    from_date_str   = year_ago.strftime("%Y-%m-%d")
    to_date_str     = today.strftime("%Y-%m-%d")
    category_filter = ""
    results_only    = False
 
    limit = None
 
    try:
        from_dt = datetime.strptime(from_date_str, "%Y-%m-%d")
        to_dt   = datetime.strptime(to_date_str,   "%Y-%m-%d")
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}
 
    scrip_code = get_bse_scrip(symbol)
    if not scrip_code:
        return {
            "error": f"Unknown symbol '{symbol}'. Add it to BSE_SCRIP_MAP or stock_list.csv."
        }
 
    company_info = COMPANY_LIST.get(symbol.upper(), {})
 
    # ------------------------------------------------------------------
    # strCat for BSE API:
    #   results_only=true  →  "Result"  (BSE's exact singular string)
    #   everything else    →  "-1"      (all categories)
    #
    # IMPORTANT: Do NOT pass our display category names (e.g. "Board") as
    # strCat — BSE uses different internal strings. We filter by mapped
    # category client-side after fetching.
    # ------------------------------------------------------------------
    str_cat = BSE_RESULT_CAT if results_only else "-1"
 
    # Split into 90-day chunks
    chunks = []
    chunk_start = from_dt
    while chunk_start <= to_dt:
        chunk_end = min(chunk_start + timedelta(days=90), to_dt)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
 
    def fetch_chunk(c_start, c_end):
        url = (
            f"{BSE_BASE}/AnnSubCategoryGetData/w"
            f"?strCat={str_cat}"
            f"&strPrevDate={c_start.strftime('%Y%m%d')}"
            f"&strScrip={scrip_code}"
            f"&strSearch=P"
            f"&strToDate={c_end.strftime('%Y%m%d')}"
            f"&strType=C"
            f"&subcategory=-1"
        )
        try:
            resp = requests.get(url, headers=BSE_HEADERS, timeout=12)
            resp.raise_for_status()
            return resp.json().get("Table") or []
        except Exception:
            return []
 
    # Concurrent fetch
    all_rows = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_chunk, s, e) for s, e in chunks]
        for future in as_completed(futures, timeout=30):
            try:
                all_rows.extend(future.result())
            except Exception:
                pass
 
    filings = []
 
    for item in all_rows:
        raw_category = item.get("SUBCATNAME") or item.get("CATEGORYNAME") or ""
        headline     = item.get("HEADLINE") or item.get("NEWSSUB") or "BSE Announcement"
        mapped_cat   = map_category(raw_category)
 
        # results_only: whitelist filter
        if results_only and not is_quarterly_result(raw_category, headline):
            continue
 
        # Optional display-name category filter
        if category_filter and mapped_cat.lower() != category_filter.lower():
            continue
 
        date_raw     = item.get("DissemDT") or item.get("News_submission_dt") or ""
        attach       = (item.get("ATTACHMENTNAME") or "").strip()
        pdf_url_val  = build_pdf_url(attach)
        download_url = (
            f"/bse-filings/{symbol.upper()}/download?file={attach}"
            if attach else None
        )
 
        is_result = is_quarterly_result(raw_category, headline)
        quarter   = detect_quarter(headline, date_raw) if is_result else None
 
        filings.append({
            "date":         date_raw,
            "filer":        item.get("SLONGNAME") or company_info.get("name") or symbol.upper(),
            "scrip_code":   scrip_code,
            "symbol":       symbol.upper(),
            "category":     mapped_cat,
            "category_raw": raw_category,
            "description":  headline,
            "quarter":      quarter,
            "pdf_url":      pdf_url_val,
            "download_url": download_url,
            "has_pdf":      bool(attach),
        })
 
    filings.sort(key=lambda x: (x["date"] or "", x["description"] or "", x["pdf_url"] or ""), reverse=True)
 
    if limit:
        filings = filings[:limit]
 
    return {
        "symbol":       symbol.upper(),
        "name":         company_info.get("name", ""),
        "sector":       company_info.get("sector", ""),
        "industry":     company_info.get("industry", ""),
        "scrip_code":   scrip_code,
        "from_date":    from_date_str,
        "to_date":      to_date_str,
        "category":     category_filter or "all",
        "results_only": results_only,
        "count":        len(filings),
        "filings":      filings,
    }
 

def download_filing_pdf(symbol):
    attach  = ""
    pdf_url = ""
 
    if not attach and not pdf_url:
        return {"error": "Missing 'file' or 'url' query parameter"}
 
    allowed = ("bseindia.com", "nseindia.com")
 
    if attach:
        candidates = [p.format(attach=attach) for p in BSE_PDF_PATTERNS]
    else:
        if not any(d in pdf_url for d in allowed):
            return {"error": "Only BSE/NSE URLs are permitted"}
 
        candidates = [pdf_url]
 
        if "AttachHist" in pdf_url:
            candidates.append(pdf_url.replace("AttachHist", "AttachHis"))
            candidates.append(pdf_url.replace("AttachHist", "Attachhis"))
        elif "AttachLive" in pdf_url:
            fn = pdf_url.split("/")[-1]
            candidates.append(f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{fn}")
            candidates.append(f"https://www.bseindia.com/xml-data/corpfiling/Attachhis/{fn}")
 
    last_error = None
 
    for url in candidates:
        if not any(d in url for d in allowed):
            continue
        try:
            r = requests.get(url, headers=BSE_HEADERS, timeout=20, stream=True)
 
            if r.status_code == 404:
                last_error = f"404 at {url}"
                continue
 
            r.raise_for_status()
 
            content_type = r.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower():
                last_error = f"Non-PDF content '{content_type}' at {url}"
                continue
 
            filename = url.split("/")[-1] or "filing.pdf"
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"
 
            return {
                "content": r.iter_content(chunk_size=8192),
                "headers": {
                    "Content-Type":        "application/pdf",
                    "Content-Disposition": f'inline; filename="{filename}"',
                    "Cache-Control":       "no-cache",
                },
            }
 
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue
 
    if attach:
        return {
            "url": f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}",
        }
 
    return {
        "error": f"PDF not available. BSE error: {last_error}",
    }
 
 

def bse_company(symbol):
    symbol     = symbol.upper().strip()
    scrip_code = get_bse_scrip(symbol)
    if not scrip_code:
        return ({"error": f"Unknown symbol: {symbol}"}), 404
 
    info   = COMPANY_LIST.get(symbol, {})
    result = {
        "symbol":     symbol,
        "scrip_code": scrip_code,
        "name":       info.get("name", ""),
        "sector":     info.get("sector", ""),
        "industry":   info.get("industry", ""),
        "isin":       "",
    }
 
    try:
        resp = requests.get(
            f"{BSE_BASE}/CompanyReach/w?scripcode={scrip_code}",
            headers=BSE_HEADERS, timeout=6,
        )
        row = (resp.json().get("Table") or [{}])[0]
        result["isin"] = row.get("ISIN_CODE", "")
        if not result["name"]:
            result["name"] = row.get("LONGNAME", "")
    except Exception:
        pass
 
    return (result)
#------------------------------------------------------------------------------------------------------------------------
def get_yf_symbol(symbol):
    """
    Convert NSE symbol to Yahoo Finance symbol
    """
    symbol = symbol.upper().strip()

    if "." in symbol:
        return symbol

    return f"{symbol}.NS"


#-------------------------------------------------------------------------------------------------------------------------
# ─────────────────────────────────────────────────────────────────────────────
# SHORT INTEREST (NSE Equivalent) — /short-interest/<symbol>
# ─────────────────────────────────────────────────────────────────────────────

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
        raw_hist = ticker.history(period="35d").tail(30)

        if raw_hist.empty:
            return {"error": f"No price data found for {symbol}"}

        # Drop any incomplete bars (weekend / pre-open rows) that have
        # Volume=0 or NaN Close — they produce null price_change and 0
        # avg_volume when stored, then mismatch the live endpoint later.
        hist = raw_hist[
            (raw_hist["Volume"] > 0) & raw_hist["Close"].notna()
        ]
        if hist.empty:
            hist = raw_hist  # fallback: use all rows if filtering removes everything

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
        return {"error": f"Price fetch failed: {str(e)}"}

    # ── 2. OI / MWPL / PCR from NSE ─────────────────────────────────────────
    oi_data = _fetch_oi_mwpl_pcr(symbol)

    oi_change_pct = oi_data["oi_change_pct"] if oi_data["oi_change_pct"] is not None else 0.0
    mwpl_pct      = oi_data["mwpl_pct"]      if oi_data["mwpl_pct"]      is not None else 0.0
    pcr           = oi_data["pcr"]            if oi_data["pcr"]            is not None else 1.0

    # ── 3. Signal + Score ────────────────────────────────────────────────────
    signal = _derive_signal(oi_change_pct, price_change)
    score  = _compute_score(oi_change_pct, mwpl_pct, pcr, vol_ratio, signal)

    return {
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
    }

def insert_stock_short_interest(symbol: str, dry_run: bool, skip_existing: bool):
    pk = f"SYMBOL#{symbol}"
    sk = f"SI#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["stock-short-interest"], pk, "SI"):
        print(f"    [SKIP] stock-short-interest for {symbol} already exists today")
        return

    print(f"  Fetching stock-short-interest for {symbol}...")

    data = short_interest(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["stock-short-interest"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "SI#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored stock-short-interest for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()

def short_interest_live_snapshot(symbol: str) -> dict:
    """Lightweight 5-min fetch — price/volume only. Deliberately skips
    _fetch_oi_mwpl_pcr(): that data comes from NSE's official daily
    reports (short-selling, delivery %, trade volume), published once a
    day — refetching it every 5 minutes returns the exact same numbers
    until tomorrow, so it's pure waste and unnecessary NSE load."""
    yf_sym = get_yf_symbol(symbol)
    ticker = yf.Ticker(yf_sym)
    fi = ticker.fast_info

    price = getattr(fi, "last_price", None)
    prev_close = getattr(fi, "previous_close", None)

    return {
        "price":        price,
        "price_change": round(price - prev_close, 2) if price and prev_close else None,
        "volume":       getattr(fi,"last_volume",None)
    }


def save_short_interest_snapshot(symbol: str):
    pk = f"SYMBOL#{symbol}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ttl_value = int(time.time()) + (30 * 24 * 60 * 60)

    data = short_interest_live_snapshot(symbol)
    if not data.get("price"):
        print(f"    [SKIP] No live price for {symbol}")
        return

    table = get_dynamo().Table(TABLES["stock-short-interest"])

    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "SI#<date>": "LATEST",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
    })
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "SI#<date>": f"SNAPSHOT#{now_iso}",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
        "ttl": ttl_value,
    })
    print(f"    [OK] Short-interest snapshot stored for {symbol}")

def insert_bse_filings(symbol: str, dry_run: bool, skip_existing: bool):
    pk = f"SYMBOL#{symbol}"
    sk = f"FILINGS#{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if skip_existing and _item_exists_today(TABLES["bse-filings"], pk, "BSE_FILINGS"):
        print(f"    [SKIP] bse-filings for {symbol} already exists today")
        return

    print(f"  Fetching bse-filings for {symbol}...")

    data = bse_filings(symbol)

    if data is None or data == {} or data == []:
        print(f"    [SKIP] Empty data")
        return

    if dry_run:
        print(f"    [DRY RUN] Would insert PK={pk} SK={sk}")
        return

    try:
        table = get_dynamo().Table(TABLES["bse-filings"])

        table.put_item(
            Item={
                "SYMBOL#<sym>": pk,
                "FILINGS#<date>": sk,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "data": _to_dynamo(data),
            }
        )

        print(f"    [OK] Stored bse-filings for {symbol}")

    except Exception as e:
        print(f"    [ERROR] DynamoDB insert failed: {e}")
        traceback.print_exc()

_ATTACH_ID_RE = re.compile(r'file=([^&]+)$')
def _filing_key_for_insert(filing: dict) -> str:
    """Stable identity for a filing — same filing always produces the
    same key, so re-inserting it is a harmless no-op."""
    url = filing.get("download_url") or filing.get("pdf_url") or ""
    m = _ATTACH_ID_RE.search(url)
    if m:
        return f"FILING#{m.group(1)}"
    return f"FILING#{filing.get('date')}|{filing.get('description')}"


def _download_and_store_pdf(filing: dict, symbol: str) -> str | None:
    """Downloads the filing's PDF and uploads it to S3.
    Tries all known BSE storage paths, verifies it's really a PDF, and
    keys the S3 object by the PDF's own content hash — so if multiple
    BSE announcements attach the same literal file (common for results +
    board outcome + dividend intimation), they all point to ONE shared
    S3 object instead of storing duplicate copies."""
    m = _ATTACH_ID_RE.search(filing.get("download_url", "") or filing.get("pdf_url", ""))
    if not m:
        return None
    attach = m.group(1)

    candidates = [pattern.format(attach=attach) for pattern in BSE_PDF_PATTERNS]

    for url in candidates:
        try:
            resp = requests.get(url, headers=BSE_HEADERS, timeout=20)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()

            if "pdf" not in resp.headers.get("Content-Type", "").lower():
                continue

            content_hash = hashlib.sha256(resp.content).hexdigest()[:16]
            s3_key = f"bse-filings/{symbol}/{content_hash}.pdf"

            # Only upload if we don't already have these exact bytes stored
            try:
                s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
                # already exists — skip re-uploading, just reuse the link
            except ClientError as e:
                if e.response["Error"]["Code"] == "404":
                    s3.put_object(
                        Bucket=S3_BUCKET,
                        Key=s3_key,
                        Body=resp.content,
                        ContentType="application/pdf",
                    )
                else:
                    raise

            return f"https://{S3_BUCKET}.s3.amazonaws.com/{s3_key}"

        except requests.exceptions.RequestException:
            continue

    print(f"    [PDF ERROR] All BSE paths 404'd/failed for {symbol} (attach={attach})")
    return None


def save_bse_filings_snapshot(symbol: str):
    """Runs every 15 min. Writes:
      - one LATEST row (current full filings list — what real users see)
      - one permanent row PER unique filing (never overwritten with loss,
        never deleted) — this is your permanent archive for ML/AI.
      - for quarterly result filings specifically, also downloads the
        actual PDF into S3, so it survives even if BSE's link ever breaks.
    """
    pk = f"SYMBOL#{symbol}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = bse_filings(symbol)
    if not data or not data.get("filings"):
        print(f"    [SKIP] No filings data for {symbol}")
        return

    table = get_dynamo().Table(TABLES["bse-filings"])

    # 1. LATEST — current full filings list (overwritten every run)
    table.put_item(Item={
        "SYMBOL#<sym>": pk,
        "FILINGS#<date>": "LATEST",
        "fetched_at": now_iso,
        "data": _to_dynamo(data),
    })

    # 2. One permanent row PER unique filing — insert only if new
    new_count = 0
    pdf_count = 0
    quarterly_keys = resolve_quarterly_filings(data.get("filings", []))
    for filing in data.get("filings", []):
        key = _filing_key_for_insert(filing)

        # Only download the PDF for genuinely new filings — no point
        # re-downloading ones we already archived on a prior run
        is_quarterly = key in quarterly_keys
        s3_url = None
        if is_quarterly:
            s3_url = _download_and_store_pdf(filing, symbol)
            if s3_url:
                pdf_count += 1

        item_data = dict(filing)
        item_data["pdf_stored_url"] = s3_url  # None if not quarterly / download failed

        try:
            table.put_item(
                Item={
                    "SYMBOL#<sym>": pk,
                    "FILINGS#<date>": key,
                    "first_seen_at": now_iso,
                    "data": _to_dynamo(item_data),
                },
                ConditionExpression="attribute_not_exists(#pk)",
                ExpressionAttributeNames={"#pk": "SYMBOL#<sym>"},
            )
            new_count += 1
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                pass  # already archived — expected, not an error
            else:
                raise

    print(f"    [OK] Filings LATEST updated, {new_count} new filing(s) archived, "
          f"{pdf_count} quarterly PDF(s) stored to S3 for {symbol}")

def run_endpoint(endpoint: str, symbol: str, args, dry_run: bool, skip_existing: bool):
    try:
        if endpoint == "stock-page":
            insert_stock_page(symbol, dry_run, skip_existing)
        elif endpoint == "stock-chart":
            insert_stock_chart(symbol, args.period, args.interval, dry_run, skip_existing)
        elif endpoint == "stock-financials":
            insert_stock_financials(symbol, dry_run, skip_existing)
        elif endpoint == "stock-earnings":
            insert_stock_earnings(symbol, dry_run, skip_existing)
        elif endpoint == "stock-dividend-summary":
            insert_stock_dividend_summary(symbol, dry_run, skip_existing)
        elif endpoint == "stock-headlines":
            insert_stock_headlines(symbol, dry_run, skip_existing)
        elif endpoint == "stock-competitors":
            insert_stock_competitors(symbol, dry_run, skip_existing)
        elif endpoint == "stock-options":
            insert_stock_options(symbol, getattr(args, "expiry", None), dry_run, skip_existing)
        elif endpoint == "stock-short-interest":
            insert_stock_short_interest(symbol, dry_run, skip_existing)
        elif endpoint == "bse-filings":
            insert_bse_filings(symbol, dry_run, skip_existing)
        # elif endpoint == "stock-meta":
        #     insert_stock_meta(symbol, dry_run, skip_existing)
    except Exception as e:
        print(f"    [ERROR] {endpoint} for {symbol}: {e}")
        traceback.print_exc()

def run_live_snapshots(symbols: list[str]):
    """Runs the fast, frequently-changing data pull for every symbol.
    This is the function EventBridge/Lambda will call every 5 minutes —
    for now, run it manually to test."""
    for symbol in symbols:
        symbol = symbol.upper().strip()
        print(f"\n[LIVE SNAPSHOT] {symbol}")
        try:
            save_price_snapshot(symbol)
        except Exception as e:
            print(f"    [ERROR] price snapshot failed: {e}")
        try:
            save_short_interest_snapshot(symbol)
        except Exception as e:
            print(f"    [ERROR] short-interest snapshot failed: {e}")
        try:
            save_options_snapshot(symbol)
        except Exception as e:
            print(f"    [ERROR] options snapshot failed: {e}")

def run_frequent_content(symbols: list[str]):
    for symbol in symbols:
        symbol = symbol.upper().strip()
        print(f"\n[15-MIN REFRESH] {symbol}")
        try:
            save_headlines_snapshot(symbol)
        except Exception as e:
            print(f"    [ERROR] headlines failed: {e}")
        try:
            save_bse_filings_snapshot(symbol)
        except Exception as e:
            print(f"    [ERROR] bse-filings failed: {e}")

def run_daily_full_refresh(symbols: list[str]):
    """Runs once, right after market close (~4:00 PM IST) — covers
    everything that doesn't need to be fresher than daily, plus the
    FULL (slow) versions of stock-page/short-interest/options that
    include the static/rarely-changing data the 5-min jobs skip."""
    for symbol in symbols:
        symbol = symbol.upper().strip()
        print(f"\n[DAILY REFRESH] {symbol}")

        insert_stock_page(symbol, dry_run=False, skip_existing=False)
        insert_stock_chart(symbol, period="1y", interval="1d", dry_run=False, skip_existing=False)
        insert_stock_financials(symbol, dry_run=False, skip_existing=False)
        insert_stock_earnings(symbol, dry_run=False, skip_existing=False)
        insert_stock_dividend_summary(symbol, dry_run=False, skip_existing=False)
        insert_stock_competitors(symbol, dry_run=False, skip_existing=False)
        insert_stock_short_interest(symbol, dry_run=False, skip_existing=False)
        insert_stock_options(symbol, expiry=None, dry_run=False, skip_existing=False)

def lambda_handler(event, context):
    """Single entry point for all three schedules. EventBridge tells us
    which job to run via the 'job' field in its event payload."""
    job = event.get("job")
    # symbols = [s["SYMBOL"] for s in load_symbol()]
    symbols = [s["SYMBOL"] for s in load_symbol()]  # TEMP: just first symbol, remove later

    if job == "live_snapshots":
        run_live_snapshots(symbols)
    elif job == "frequent_content":
        run_frequent_content(symbols)
    elif job == "daily_full_refresh":
        run_daily_full_refresh(symbols)
    else:
        raise ValueError(f"Unknown job type: {job}")

    return {"status": "ok", "job": job, "symbol_count": len(symbols)}
    
# if __name__ == "__main__":
#     # Quick manual test — replace with your real symbol list
#     run_live_snapshots(["TCS", "INFY"])

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Fetch stock data (same logic as routes.py) and store in DynamoDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all endpoints for all 40 stocks
  python insert_data.py

  # Specific symbols
  python insert_data.py --symbols INFY TCS

  # Specific endpoints
  python insert_data.py --endpoints stock-page stock-chart stock-financials

  # Dry run (no DB writes)
  python insert_data.py --symbols INFY --dry-run

  # Skip if already stored today
  python insert_data.py --skip-existing
        """
    )
    p.add_argument("--symbols",    nargs="+", default=None,          help="Symbols to process (default: all 40 from stock_list.csv)")
    p.add_argument("--endpoints",  nargs="+", default=ALL_ENDPOINTS, choices=ALL_ENDPOINTS, help="Endpoints to run (default: all)")
    p.add_argument("--period",     default="1y",  help="Chart period (default: 1y)")
    p.add_argument("--interval",   default="1d",  help="Chart interval (default: 1d)")
    p.add_argument("--expiry",     default=None,  help="Options expiry date (e.g. 2025-05-29)")
    p.add_argument("--dry-run",    action="store_true", help="Fetch data but don't write to DynamoDB")
    p.add_argument("--skip-existing", action="store_true", help="Skip endpoints that already have data for today")
    p.add_argument("--csv",        default=None,  help="Path to stock_list.csv (default: same directory)")
    p.add_argument("--live-snapshots", action="store_true",
                   help="Run live snapshots only (price + short-interest + options). "
                        "Designed for frequent polling (e.g. every 5 min). "
                        "Skips the normal full-endpoint ingestion loop.")

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()

    # Load symbol list
    all_stocks = load_symbol()
    if not all_stocks:
        print("[ERROR] No symbols loaded. Check stock_list.csv path.")
        return

    if args.symbols:
        requested = [s.upper() for s in args.symbols]
        symbols   = [s for s in all_stocks if s["SYMBOL"] in requested]
        if not symbols:
            print(f"[ERROR] None of {requested} found in stock_list.csv")
            return
    else:
        symbols = all_stocks

    # ── Live-snapshot fast path ──────────────────────────────────────────────
    if args.live_snapshots:
        symbol_names = [s["SYMBOL"] if isinstance(s, dict) else s for s in symbols]
        print(f"\n{'='*60}")
        print(f"  LIVE SNAPSHOTS")
        print(f"  Symbols     : {', '.join(symbol_names)}")
        print(f"  Started at  : {datetime.now(timezone.utc).isoformat()} UTC")
        print(f"{'='*60}")
        run_live_snapshots(symbol_names)
        print(f"\n{'='*60}")
        print(f"  DONE — {datetime.now(timezone.utc).isoformat()} UTC")
        print(f"{'='*60}\n")
        return

    endpoints  = args.endpoints
    dry_run    = args.dry_run
    skip_exist = args.skip_existing

    print(f"\n{'='*60}")
    print(f"  insert_data.py")
    print(f"  DRY RUN     : {dry_run}")
    print(f"  SKIP EXISTS : {skip_exist}")
    print(f"  Symbols     : {len(symbols)}")
    print(f"  Endpoints   : {', '.join(endpoints)}")
    print(f"  Started at  : {datetime.now(timezone.utc).isoformat()} UTC")
    print(f"{'='*60}\n")

    total_ok = total_err = 0

    for stock in symbols:
        symbol = stock["SYMBOL"]
        print(f"\n{'-'*50}")
        print(f"  >  {symbol}  ({stock['NAME OF COMPANY']})")
        print(f"{'-'*50}")

        for endpoint in endpoints:
            t0 = time.time()
            try:
                run_endpoint(endpoint, symbol, args, dry_run, skip_exist)
                total_ok += 1
            except Exception as e:
                print(f"    [FAIL] {endpoint}: {e}")
                total_err += 1
            elapsed = time.time() - t0
            print(f"    -> {endpoint} done in {elapsed:.1f}s")

            # Small sleep between endpoints to avoid rate limiting
            time.sleep(0.5)

        # Slightly longer pause between symbols
        time.sleep(1)

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"  Succeeded : {total_ok}")
    print(f"  Failed    : {total_err}")
    print(f"  Finished  : {datetime.now(timezone.utc).isoformat()} UTC")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
    # print("=== FIRST RUN ===")
    # save_headlines_snapshot("TCS")
    # print("\n=== SECOND RUN (should archive 0 new articles) ===")
    # save_headlines_snapshot("TCS")
    # print("=== FIRST RUN ===")
    # save_bse_filings_snapshot("TCS")
    # print("\n=== SECOND RUN (should archive 0 new filings) ===")
    # save_bse_filings_snapshot("TCS")
    fake_event = {"job": "frequent_content"}
    result = lambda_handler(fake_event, None)