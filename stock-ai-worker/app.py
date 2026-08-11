from __future__ import annotations
import os
import sys

# MUST run before any Keras/TensorFlow import (including transitively, e.g.
# via `keras.models`) — this tells TensorFlow which Keras backend to
# initialize. Setting it any later has no effect, and mixing two Keras
# backends in one process can crash the whole interpreter (segfault).
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import time
import asyncio
import pickle
from typing import Any
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager


import pandas as pd
import numpy as np
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# IMPORT ORDER MATTERS HERE.
# transformers (PyTorch) must be imported before keras (TensorFlow) at
# module level — importing them in the opposite order (or deferring the
# transformers import to later, e.g. inside an async startup function)
# has been observed to cause a native-level crash (segfault, exit 139)
# when both frameworks end up in the same process. This mirrors the
# import order of the original, confirmed-working version of this file.
from transformers import pipeline as hf_pipeline
sys.path.append(os.path.join(os.getcwd(), "ML", "STOCK-PREDICTION"))
from model_manager import load_all_models
from predictor import predict_price

# ── PATH SETUP ──────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(os.getcwd(), "ML")
sys.path.append(MODEL_DIR)

from recommend import recommend_top_stocks

ml_models = {}

# ---------------- APP STARTUP ---------------- #


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # ── Summarizer ────────────────────────────────────────────────────
        # Loading the model/tokenizer directly (instead of pipeline("summarization", ...))
        # since the installed transformers version's pipeline task registry
        # doesn't recognize "summarization" (or "text2text-generation") as a
        # task name. Calling .generate() ourselves sidesteps that entirely.
        print("📥 Loading Summarizer...")
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        summarizer_model_id = "sshleifer/distilbart-cnn-12-6"
        summarizer_tokenizer = AutoTokenizer.from_pretrained(summarizer_model_id)
        summarizer_model = AutoModelForSeq2SeqLM.from_pretrained(summarizer_model_id)

        def run_summarizer(text, max_length=60, min_length=20):
            """Summarize text with distilbart; falls back to a simple
            sentence-trim if the model call fails for any reason."""
            text = (text or "").strip()
            if not text:
                return ""
            try:
                inputs = summarizer_tokenizer(
                    text, return_tensors="pt", truncation=True, max_length=512
                )
                summary_ids = summarizer_model.generate(
                    inputs["input_ids"],
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False,
                )
                return summarizer_tokenizer.decode(
                    summary_ids[0], skip_special_tokens=True
                ).strip()
            except Exception as e:
                print(f"⚠️ Summarizer error, falling back to trim: {e}")
                sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 15]
                cleaned = ". ".join(sentences[:2])
                return cleaned + "." if cleaned else text[:150]

        ml_models["summarizer"] = run_summarizer
        print("✅ Summarizer loaded")

        # ── FinBERT (for sentiment) ─────────────────────────────────────
        print("📥 Loading FinBERT...")
        finbert = hf_pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            framework="pt",
        )
        ml_models["finbert"] = finbert

        # Inject into ragbased so get_hybrid_sentiment uses it
        import ragbased
        ragbased._finbert = finbert
        print("✅ FinBERT loaded")

        # ── Stock list ────────────────────────────────────────────────────
        stock_csv = os.path.join(os.getcwd(), "stock_list.csv")
        df_stocks = pd.read_csv(stock_csv)

        # Extract clean ticker from "COMPANY NAME (XNSE:TICKER)" format
        df_stocks["SYMBOL"] = (
            df_stocks["SYMBOL"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df_stocks = df_stocks.dropna(subset=["SYMBOL"])

        ml_models["ticker_map"] = df_stocks.set_index("SYMBOL").to_dict("index")
        ml_models["industry_map"] = df_stocks.groupby("INDUSTRY")["SYMBOL"].apply(list).to_dict()
        ml_models["all_tickers"] = set(df_stocks["SYMBOL"].tolist())
        print(f"✅ Stock list loaded — {len(df_stocks)} tickers")

        # ── XGBoost recommendation model ───────────────────────────────────
        with open(os.path.join(MODEL_DIR, "recml_xgb.pkl"), "rb") as f:
            ml_models["xgb"] = pickle.load(f)
        with open(os.path.join(MODEL_DIR, "training_columns.pkl"), "rb") as f:
            ml_models["cols"] = pickle.load(f)

        asyncio.create_task(refresh_news_worker())

        print("📥 Loading stock prediction models...")
        load_all_models()
        print("✅ Stock prediction models loaded")
        print("🚀 Startup Complete.")

    except Exception as e:
        print(f"❌ Startup Error: {e}")
    yield
    ml_models.clear()


app = FastAPI(lifespan=lifespan)

# Import RAG logic after path is set
from ragbased import get_hybrid_sentiment, sentiment_to_market_action

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NEWS LOGIC ---
NEWS_CACHE = {
    "timestamp": 0,
    "date": None,
    "data": []
}

COMPETITOR_CACHE: dict = {}   # symbol → (data, timestamp)
COMPETITOR_TTL = 60 * 60 * 24 * 7
COMPANY_SENTIMENT_CACHE: dict = {}
COMPANY_CACHE_TTL = 60 * 60
REFRESH_INTERVAL = 60 * 30  # refresh every 30 mins


def batch_summarize(text_list):
    summarizer = ml_models.get("summarizer")
    if not text_list or not summarizer:
        return []
    results = []
    for t in text_list:
        try:
            out = summarizer(t)
            print(f"✅ Summary: {out[:80]}")
            results.append(out)
        except Exception as e:
            print(f"❌ Summarizer failed: {e}")
            results.append(t[:100] + "...")
    return results


FINNHUB_API_KEY = os.environ.get("FINNHUBAPIKEY", "")


def fetch_finnhub_articles(ticker: str, weeks_back: int = 16) -> list:
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(weeks=weeks_back)

    url = "https://finnhub.io/api/v1/company-news"
    params = {
        "symbol": ticker,
        "from": from_date.strftime("%Y-%m-%d"),
        "to": to_date.strftime("%Y-%m-%d"),
        "token": FINNHUB_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"[Finnhub] {ticker} HTTP {resp.status_code}")
            return []

        articles = resp.json()   # returns a list directly
        if not isinstance(articles, list):
            print(f"[Finnhub] {ticker} unexpected response: {articles}")
            return []

        normalized = []
        for a in articles[:15]:   # cap at 15 per ticker
            normalized.append({
                "title": a.get("headline", ""),
                "description": a.get("summary", "")[:400],
                "image": a.get("image", ""),
                "url": a.get("url", ""),
                "source": {"name": a.get("source", "")},
                "publishedAt": datetime.fromtimestamp(
                    a.get("datetime", 0), tz=timezone.utc
                ).isoformat(),
            })

        print(f"[Finnhub] {ticker} → {len(normalized)} articles")
        return normalized

    except Exception as e:
        print(f"[Finnhub] {ticker} failed: {e}")
        return []


async def refresh_news_worker():
    await asyncio.sleep(5)
    while True:
        try:
            print("🟡 Refreshing market news…")

            url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
            resp = requests.get(url, timeout=10)
            articles_raw = resp.json()[:10] if resp.status_code == 200 else []

            articles = [{
                "title": a.get("headline", ""),
                "description": a.get("summary", "")[:400],
                "image": a.get("image", ""),
                "url": a.get("url", ""),
                "source": {"name": a.get("source", "")},
                "publishedAt": datetime.fromtimestamp(
                    a.get("datetime", 0), tz=timezone.utc
                ).isoformat(),
            } for a in articles_raw]

            # deduplicate
            seen = set()
            unique = []
            for a in articles:
                if a["title"] not in seen:
                    seen.add(a["title"])
                    unique.append(a)
            articles = unique[:10]

            desc_list = [(article.get("description") or "")[:400] for article in articles]
            print(f"📝 Summarizing {len(desc_list)} articles...")

            summaries = batch_summarize(desc_list)
            print(f"✅ Sample summary: {summaries[0] if summaries else 'EMPTY'}")

            newsdata = []
            for article, summary in zip(articles, summaries):
                title = article.get("title", "")

                result = get_hybrid_sentiment(title, summary)
                sentiment = result["sentiment"]
                confidence = result["confidence"]
                source = result["source"]

                reaction, action = sentiment_to_market_action(sentiment)

                newsdata.append({
                    "title": title,
                    "summary": summary,
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "sentiment_source": source,
                    "impact": reaction,
                    "learn": action,
                    "headline": title,
                    "image": article.get("image"),
                    "link": article.get("url"),
                    "publisher": article.get("source", {}).get("name"),
                    "time": article.get("publishedAt")
                })

            newsdata = newsdata[:5]

            NEWS_CACHE["timestamp"] = time.time()
            NEWS_CACHE["date"] = datetime.now(timezone.utc).date()
            NEWS_CACHE["data"] = newsdata

            print("✅ News auto-updated & cached")

        except Exception as e:
            print("❌ News refresh error:", e)

        await asyncio.sleep(REFRESH_INTERVAL)


@app.get("/news")
async def get_market_news_endpoint():
    if not NEWS_CACHE["data"]:
        return {"news": [], "status": "initializing"}

    return {
        "news": NEWS_CACHE["data"],
        "last_updated": NEWS_CACHE["timestamp"],
        "date": str(NEWS_CACHE["date"])
    }


def get_competitors(symbol: str, max_peers: int = 5) -> list[str]:
    ticker_map = ml_models.get("ticker_map", {})
    industry_map = ml_models.get("industry_map", {})
    if symbol not in ticker_map:
        return []
    industry = ticker_map[symbol]["INDUSTRY"]
    peers = [t for t in industry_map.get(industry, []) if t != symbol]
    return peers[:max_peers]


def get_company_name(symbol: str) -> str:
    ticker_map = ml_models.get("ticker_map", {})
    row = ticker_map.get(symbol, {})
    name = row.get("NAME OF COMPANY", symbol)
    for suffix in [" Inc.", " Corp.", " Ltd.", " Limited", " PLC", " SE"]:
        name = name.replace(suffix, "")
    return name.strip()


@app.get("/sentiment/{symbol}")
async def get_company_sentiment(symbol: str):
    sym = symbol.upper()
    now = time.time()

    if sym not in ml_models.get("all_tickers", set()):
        raise HTTPException(status_code=404, detail=f"{sym} not supported")

    if sym in COMPANY_SENTIMENT_CACHE:
        cached, ts = COMPANY_SENTIMENT_CACHE[sym]
        if now - ts < COMPANY_CACHE_TTL:
            return cached

    finbert = ml_models.get("finbert")
    summarizer = ml_models.get("summarizer")
    if not finbert:
        raise HTTPException(status_code=503, detail="FinBERT not loaded yet")

    competitors = get_competitors(sym)
    all_symbols = [sym] + competitors

    all_newsdata = {}

    for target_sym in all_symbols:

        if target_sym != sym and target_sym in COMPETITOR_CACHE:
            cached_data, ts = COMPETITOR_CACHE[target_sym]
            if now - ts < COMPETITOR_TTL:
                all_newsdata[target_sym] = cached_data
                print(f"[Cache] {target_sym} served from cache")
                continue

        raw_articles = fetch_finnhub_articles(target_sym, weeks_back=16)

        newsdata = []
        for art in raw_articles:
            title = art.get("title", "")
            description = (art.get("description") or "")[:400]
            summary = summarizer(description) if summarizer and description else description[:150]

            text_for_bert = f"{title}. {summary}"[:512]
            try:
                fb_result = finbert(text_for_bert)[0]
                label = fb_result["label"].lower()
                confidence = round(fb_result["score"], 3)
                sentiment = (
                    "bullish" if label == "positive" else
                    "bearish" if label == "negative" else
                    "neutral"
                )
            except Exception:
                sentiment, confidence = "neutral", 0.5

            reaction, action = sentiment_to_market_action(sentiment)

            newsdata.append({
                "symbol": target_sym,
                "title": title,
                "summary": summary,
                "sentiment": sentiment,
                "confidence": confidence,
                "impact": reaction,
                "action": action,
                "learn": action,
                "image": art.get("image"),
                "url": art.get("url"),
                "link": art.get("url"),
                "publisher": art.get("source", {}).get("name", ""),
                "time": art.get("publishedAt", ""),
            })

        all_newsdata[target_sym] = newsdata

        if target_sym != sym:
            COMPETITOR_CACHE[target_sym] = (newsdata, now)

    def build_chart(newsdata):
        SCORE_MAP = {"bullish": 1.35, "neutral": 1.00, "bearish": 0.65}
        from collections import defaultdict
        weekly = defaultdict(list)

        today_dt = datetime.now(timezone.utc)
        this_monday = today_dt - timedelta(days=today_dt.weekday())
        for i in range(4, -1, -1):
            wk = (this_monday - timedelta(weeks=i)).strftime("%Y-%m-%d")
            weekly[wk]

        for art in newsdata:
            score = SCORE_MAP.get(art["sentiment"], 1.0)
            raw_time = art.get("time", "")
            try:
                dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                wk = (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                weekly[wk].append(score)
            except Exception:
                continue

        last_score = 1.0
        chart = []
        for wk in sorted(weekly.keys()):
            scores = weekly[wk]
            if scores:
                last_score = round(sum(scores) / len(scores), 3)
            chart.append({"date": wk, "score": last_score})
        return chart

    SCORE_MAP = {"bullish": 1.35, "neutral": 1.00, "bearish": 0.65}
    main_news = all_newsdata[sym]
    if main_news:
        avg = sum(SCORE_MAP.get(a["sentiment"], 1.0) for a in main_news) / len(main_news)
        overall = "bullish" if avg > 1.15 else "bearish" if avg < 0.85 else "neutral"
    else:
        overall = "neutral"

    result = {
        "symbol": sym,
        "competitors": competitors,
        "news": main_news,
        "chart_data": {t: build_chart(all_newsdata[t]) for t in all_symbols},
        "summary": overall,
    }

    COMPANY_SENTIMENT_CACHE[sym] = (result, now)
    return result


# --- analyze news ---
TOPIC_MAP: dict[str, list[str]] = {
    "AI": ["ai", "artificial intelligence", "genai", "machine learning", "llm"],
    "Cloud": ["cloud", "aws", "azure", "gcp", "saas"],
    "Earnings": ["earnings", "results", "quarter", "revenue", "profit", "loss"],
    "Banking": ["bank", "bfsi", "financial services", "rbi", "nbfc"],
    "Deals": ["deal", "contract", "client", "partnership", "win", "order"],
    "Leadership": ["ceo", "cfo", "cto", "management", "appointed", "resigned"],
    "Layoffs": ["layoffs", "job cuts", "retrenchment", "downsizing"],
    "Regulation": ["sebi", "regulation", "compliance", "penalty", "fine", "notice"],
    "Expansion": ["expansion", "launch", "new market", "acquisition", "merger"],
    "Macro": ["inflation", "gdp", "rbi", "fed", "interest rate", "recession"],
}


def _detect_topics(text: str) -> list[str]:
    t = text.lower()
    return [topic for topic, kws in TOPIC_MAP.items() if any(k in t for k in kws)]


def _sentiment_to_action(sentiment: str) -> tuple[str, str]:
    return {
        "bullish": ("High", "Buy / Watch"),
        "bearish": ("High", "Caution / Review"),
        "neutral": ("Medium", "Watch"),
    }.get(sentiment, ("Medium", "Watch"))


def _finbert_sentiment(text: str) -> tuple[str, float]:
    finbert = ml_models.get("finbert")
    if not finbert:
        return "neutral", 0.5
    try:
        res = finbert(text[:512])[0]
        label = res["label"].lower()
        score = round(float(res["score"]), 3)
        sentiment = (
            "bullish" if label == "positive"
            else "bearish" if label == "negative"
            else "neutral"
        )
        return sentiment, score
    except Exception as e:
        print(f"[FINBERT] {e}")
        return "neutral", 0.5


def _summarize(text: str) -> str:
    summarizer = ml_models.get("summarizer")
    if not summarizer or not text:
        return text
    try:
        return summarizer(text, max_length=80, min_length=20)
    except Exception as e:
        print(f"[SUMMARIZER] {e}")
        return text


def _build_learnings(sentiment: str, impact: str, topics: list[str]) -> list[str]:
    learnings = []
    if sentiment == "bullish":
        learnings.append("Positive momentum detected in the news flow.")
    elif sentiment == "bearish":
        learnings.append("Potential business or market pressure identified.")
    else:
        learnings.append("Market sentiment remains balanced.")

    if impact == "High":
        learnings.append("This news could materially affect investor sentiment.")
    if "Earnings" in topics:
        learnings.append("News relates to company financial performance.")
    if "AI" in topics:
        learnings.append("AI-related developments continue to be a focus area.")
    if "Regulation" in topics:
        learnings.append("Regulatory developments may have compliance implications.")
    if "Deals" in topics:
        learnings.append("Deal flow suggests active business development activity.")

    return learnings


def _analyze_single(symbol: str, company_name: str, title: str, summary: str) -> dict[str, Any]:
    combined = f"{title}. {summary}"
    ai_summary = _summarize(summary) if summary else title
    sentiment, confidence = _finbert_sentiment(combined)
    topics = _detect_topics(combined)
    impact, action = _sentiment_to_action(sentiment)
    learnings = _build_learnings(sentiment, impact, topics)

    return {
        "symbol": symbol,
        "company_name": company_name,
        "summary": ai_summary,
        "sentiment": sentiment,
        "confidence": confidence,
        "impact": impact,
        "action": action,
        "learnings": learnings,
        "topics": topics,
    }


# ─────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────
class ArticleIn(BaseModel):
    title: str = ""
    summary: str = ""


class BatchRequest(BaseModel):
    symbol: str
    company_name: str = ""
    articles: list[ArticleIn]


class SingleRequest(BaseModel):
    symbol: str
    company_name: str = ""
    title: str = ""
    summary: str = ""


# ─────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "finbert": ml_models.get("finbert") is not None,
        "summarizer": ml_models.get("summarizer") is not None,
    }


@app.post("/analyze-news-batch")
def analyze_news_batch(req: BatchRequest):
    """Analyze a batch of articles in one call.
    Returns {"results": [...]} in the same order as input articles."""
    if not ml_models.get("finbert"):
        raise HTTPException(status_code=503, detail="FinBERT not loaded")

    results = []
    for article in req.articles:
        try:
            res = _analyze_single(
                symbol=req.symbol,
                company_name=req.company_name or req.symbol,
                title=article.title,
                summary=article.summary,
            )
        except Exception as e:
            print(f"[BATCH ITEM ERROR] {e}")
            res = {
                "symbol": req.symbol,
                "company_name": req.company_name,
                "summary": article.summary or article.title,
                "sentiment": "neutral",
                "confidence": 0.5,
                "impact": "Medium",
                "action": "Watch",
                "learnings": ["Analysis unavailable."],
                "topics": [],
            }
        results.append(res)

    return {"results": results}


@app.post("/analyze-news")
def analyze_news(req: SingleRequest):
    """Single-article endpoint kept for backwards compatibility."""
    if not ml_models.get("finbert"):
        raise HTTPException(status_code=503, detail="FinBERT not loaded")

    try:
        return _analyze_single(
            symbol=req.symbol,
            company_name=req.company_name or req.symbol,
            title=req.title,
            summary=req.summary,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# --- PREDICTION LOGIC (LSTM) ---
@app.get("/predict/{symbol}")
async def predict(symbol: str):
    """
    Return a next-day price prediction for the given NSE symbol.
    Uses a pre-trained LSTM model loaded at startup — no training happens
    during the request.
    """
    try:
        result = predict_price(symbol)

        if not result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "Prediction failed.")
            )

        return {
            "symbol": symbol.upper(),
            "current_price": result["current_price"],
            "predicted_price": result["predicted_price"],
            "predicted_price_range": result.get("predicted_price_range"),
            "confidence_score": result.get("confidence_score"),
            "predicted_change": result["predicted_change"],
            "predicted_change_percent": result["predicted_change_percent"],
            "verdict": "Upward" if result["trend"] == "UP" else ("Downward" if result["trend"] == "DOWN" else "Sideways"),
            "trend": result["trend"],
            "last_available_date": result["last_available_date"],
            "historical_chart": result.get("historical_chart", []),
            "forecast_chart": result.get("forecast_chart", []),
            "technical_indicators": result.get("technical_indicators", {}),
            "model_accuracy": result.get("model_accuracy"),
            "model_trained_at": result.get("model_trained_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- RECOMMENDATION LOGIC (XGBoost) ---
@app.post("/recommend")
async def recommend(data: dict):
    import traceback

    dbg = {"stage": "start"}
    t0 = time.time()

    try:
        xgb_model = ml_models.get("xgb")
        train_cols = ml_models.get("cols")
        if xgb_model is None or train_cols is None:
            return {"error": "MODEL_NOT_LOADED", "debug": dbg}

        txns_df = pd.DataFrame(data.get("transactions", []))
        stocks_df = pd.DataFrame(data.get("stock_universe", []))

        dbg["tx_count"] = len(txns_df)
        dbg["stock_rows_in"] = len(stocks_df)

        if stocks_df.empty:
            return {"error": "EMPTY_STOCK_UNIVERSE", "debug": dbg}

        # normalize column names (in case caller sends raw CSV-style headers)
        stocks_df = stocks_df.rename(columns={
            "SYMBOL": "stockname",
            "NAME OF COMPANY": "companyname",
        })
        dbg["columns_after_rename"] = list(stocks_df.columns)

        if "stockname" not in stocks_df.columns:
            return {"error": "NO_STOCKNAME_FIELD", "debug": dbg}

        if "price" not in stocks_df.columns:
            stocks_df["price"] = 0.0
            dbg["price_filled"] = True

        top_n = int(data.get("top_n", 6))

        recs_df = recommend_top_stocks(
            transactions_df=txns_df,
            stocks_df=stocks_df,
            model=xgb_model,
            train_cols=train_cols,
            top_n=top_n,
        )

        dbg["rows_returned"] = len(recs_df)

        return {
            "count": len(recs_df),
            "recommendations": recs_df.to_dict(orient="records"),
            "source": "model",
            "latency_ms": round((time.time() - t0) * 1000, 2),
            "debug": dbg
        }

    except Exception as e:
        dbg["exception"] = str(e)
        dbg["trace"] = traceback.format_exc()
        return {"error": str(e), "debug": dbg}


@app.post("/summarize")
async def summarize(data: dict):
    summarizer = ml_models.get("summarizer")
    text = data.get("text", "")
    if not text or not summarizer:
        return {"summary": ""}
    return {"summary": summarizer(text, max_length=40, min_length=10)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)