"""
/headlines/<symbol>

Fetches news from multiple sources (Google RSS, GNews, NewsAPI),
deduplicates, runs HuggingFace sentiment batch analysis,
and returns a structured news feed with sentiment aggregates.
"""

import re
import time
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from bs4 import BeautifulSoup
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

from ..routes_utils import get_yf_symbol, HF_BASE_URL, HF_HEADERS
import yfinance as yf

stock_headlines_bp = Blueprint("stock_headlines_bp", __name__)

# ── Simple LRU-style cache ─────────────────────────────────────────────────────

HEADLINES_CACHE: dict = {}
HEADLINES_CACHE_TTL = 900   # 15 minutes
MAX_CACHE_SIZE = 100

SENTIMENT_SCORE = {"bullish": 1.35, "neutral": 1.00, "bearish": 0.65}

TRUSTED_SOURCES = {
    "Reuters", "Bloomberg", "CNBC", "Moneycontrol",
    "The Economic Times", "Economic Times", "LiveMint", "Mint",
    "Business Standard", "Financial Express", "The Hindu BusinessLine",
    "BusinessLine", "NDTV Profit", "CNBC TV18", "ETMarkets",
    "Zee Business", "India Today", "Yahoo Finance", "MarketScreener",
    "Seeking Alpha", "Benzinga", "The Motley Fool", "Simply Wall St",
    "simplywall.st", "Tata Consultancy Services",
}


def _cache_get(key: str):
    """Return cached value if still fresh, else None."""
    entry = HEADLINES_CACHE.get(key)
    if entry and (time.time() - entry[1]) < HEADLINES_CACHE_TTL:
        return entry[0]
    return None


def _cache_set(key: str, value: dict) -> None:
    """Store value; evict the oldest entry when the cache is full."""
    if len(HEADLINES_CACHE) >= MAX_CACHE_SIZE:
        oldest = min(HEADLINES_CACHE, key=lambda k: HEADLINES_CACHE[k][1])
        del HEADLINES_CACHE[oldest]
    HEADLINES_CACHE[key] = (value, time.time())


# ── HuggingFace batch call ─────────────────────────────────────────────────────

def _fetch_hf_batch(symbol: str, company_name: str, articles: list[dict]) -> list[dict]:
    """
    Send all articles to HF in a single POST request.
    Returns a list of analysis dicts in the same order as the input.
    Falls back to empty dicts on any error so the route never crashes.
    """
    if not articles:
        return []

    payload = {
        "symbol":       symbol,
        "company_name": company_name,
        "articles":     articles,
    }

    for attempt in range(3):
        try:
            resp = requests.post(
                f"{HF_BASE_URL}/analyze-news-batch",
                headers=HF_HEADERS,
                json=payload,
                timeout=60,
            )

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                # Pad if HF returned fewer items than we sent
                while len(results) < len(articles):
                    results.append({})
                return results

            if resp.status_code == 503:
                print(f"[HF BATCH] 503 cold-start, waiting… (attempt {attempt + 1})")
                time.sleep(12)
                continue

            print(f"[HF BATCH] HTTP {resp.status_code}")
            break

        except requests.Timeout:
            print(f"[HF BATCH] Timeout attempt {attempt + 1}")
            if attempt < 2:
                time.sleep(5)

        except Exception as exc:
            print(f"[HF BATCH] Unexpected error: {exc}")
            break

    return [{} for _ in articles]


# ── News fetching ──────────────────────────────────────────────────────────────

def clean_html(text: str) -> str:
    """Remove HTML tags and common entities from RSS summaries."""
    if not text:
        return ""
    text = re.sub(r"<.*?>", "", text)
    text = (
        text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
    )
    return re.sub(r"\s+", " ", text).strip()


def fetch_google_rss_news(company_name: str, limit: int = 15):
    """Fetch trusted company news via Google News RSS, optimised for Indian equities."""
    query = urllib.parse.quote(f'"{company_name}" stock OR share OR NSE OR earnings')
    url   = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        feed = feedparser.parse(url)
        articles = []
        seen_titles = set()

        for entry in feed.entries:
            source_name = "Google News"
            if isinstance(entry.get("source"), dict):
                source_name = entry.get("source", {}).get("title", "Google News")
            elif isinstance(entry.get("source"), str):
                source_name = entry.get("source")
            source_name = (source_name or "").strip()

            is_trusted = any(t.lower() in source_name.lower() for t in TRUSTED_SOURCES)
            if not is_trusted:
                continue

            title = clean_html(entry.get("title", ""))
            if not title:
                continue

            title_key = title.lower().strip()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            raw_summary = entry.get("summary", "")
            summary     = clean_html(raw_summary)

            img_url = None
            try:
                soup    = BeautifulSoup(raw_summary, "html.parser")
                img_tag = soup.find("img")
                if img_tag and img_tag.get("src"):
                    img_url = img_tag.get("src")
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
            except Exception:
                pass

            if not summary:
                summary = title

            published_ts = None
            try:
                if entry.get("published_parsed"):
                    published_ts = int(
                        datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp()
                    )
                elif entry.get("published"):
                    from email.utils import parsedate_to_datetime
                    published_ts = int(parsedate_to_datetime(entry.published).timestamp())
            except Exception as e:
                print(f"[RSS DEBUG] timestamp parse error: {e}")

            articles.append({
                "title":               title,
                "summary":             summary,
                "publisher":           source_name,
                "link":                entry.get("link", ""),
                "providerPublishTime": published_ts,
                "thumbnail": {
                    "resolutions": [{"url": img_url}] if img_url else []
                },
            })

            if len(articles) >= limit:
                break

        print(f"[Google RSS] Retrieved {len(articles)} trusted articles")
        return articles

    except Exception as e:
        print(f"[Google RSS] Error: {e}")
        return []


def fetch_gnews_news(company_name: str, limit: int = 10, api_key: str = ""):
    """Fetch news from GNews API. Good coverage for Indian equities."""
    query = urllib.parse.quote(company_name)
    url   = (
        f"https://gnews.io/api/v4/search?"
        f"q={query}&lang=en&country=in&max={limit}&apikey={api_key}"
    )

    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"[GNews] HTTP {resp.status_code}")
            return []

        articles = []
        for item in resp.json().get("articles", []):
            source_name  = item.get("source", {}).get("name", "GNews")
            published_ts = None
            try:
                pub = item.get("publishedAt")
                if pub:
                    published_ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
            except Exception:
                pass

            articles.append({
                "title":               item.get("title", ""),
                "summary":             item.get("description", ""),
                "publisher":           source_name,
                "link":                item.get("url", ""),
                "providerPublishTime": published_ts,
                "thumbnail": {
                    "resolutions": [{"url": item.get("image")}] if item.get("image") else []
                },
            })

        print(f"[GNews] Retrieved {len(articles)} articles")
        return articles

    except Exception as e:
        print(f"[GNews] Error: {e}")
        return []


def fetch_newsapi_news(company_name: str, limit: int = 10, api_key: str = ""):
    """Fetch news using NewsAPI."""
    query = urllib.parse.quote(company_name)
    url   = (
        f"https://newsapi.org/v2/everything?"
        f"q={query}&language=en&pageSize={limit}&sortBy=publishedAt&apiKey={api_key}"
    )

    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"[NewsAPI] HTTP {resp.status_code}")
            return []

        articles = []
        for item in resp.json().get("articles", []):
            published_ts = None
            try:
                pub = item.get("publishedAt")
                if pub:
                    published_ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
            except Exception:
                pass

            articles.append({
                "title":               item.get("title", ""),
                "summary":             item.get("description", ""),
                "publisher":           item.get("source", {}).get("name", "NewsAPI"),
                "link":                item.get("url", ""),
                "providerPublishTime": published_ts,
                "thumbnail": {
                    "resolutions": [{"url": item.get("urlToImage")}] if item.get("urlToImage") else []
                },
            })

        print(f"[NewsAPI] Retrieved {len(articles)} articles")
        return articles

    except Exception as e:
        print(f"[NewsAPI] Error: {e}")
        return []


# ── Article processing helpers ─────────────────────────────────────────────────

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
    Score: 0 = fully bearish, 50 = neutral, 100 = fully bullish.
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


def _build_empty_result(symbol, company_name, company_meta):
    return {
        "success":                True,
        "symbol":                 symbol,
        "company_name":           company_name,
        "company_meta":           company_meta,
        "news_count":             0,
        "overall_sentiment":      {"label": "Neutral", "score": 50},
        "sentiment_distribution": {"bullish": 0, "neutral": 0, "bearish": 0},
        "top_topics":             [],
        "ai_market_insights":     [],
        "news":                   [],
    }


# ── Route ──────────────────────────────────────────────────────────────────────

@stock_headlines_bp.route("/headlines/<symbol>", methods=["GET", "OPTIONS"])
@cross_origin(supports_credentials=True)
def headlines_page(symbol: str):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    symbol = symbol.upper().strip()

    cached = _cache_get(symbol)
    if cached:
        return jsonify(cached)

    try:
        from .. import routes_utils
        ticker       = yf.Ticker(get_yf_symbol(symbol))
        info         = ticker.info or {}
        company_name = info.get("longName") or info.get("shortName") or symbol

        logo_url = info.get("logo_url")
        if not logo_url and info.get("website"):
            domain   = info.get("website").replace("https://", "").replace("http://", "").split("/")[0]
            logo_url = f"https://logo.clearbit.com/{domain}" if domain else None

        company_meta = {
            "sector":               info.get("sector"),
            "industry":             info.get("industry"),
            "logo_url":             logo_url,
            "market_cap":           info.get("marketCap"),
            "current_price":        info.get("currentPrice") or info.get("regularMarketPrice"),
            "price_change":         info.get("regularMarketChange"),
            "price_change_percent": info.get("regularMarketChangePercent"),
        }

        # Fetch from all three news sources
        rss_news     = fetch_google_rss_news(company_name, limit=15)
        gnews_news   = fetch_gnews_news(company_name, limit=10, api_key=routes_utils.GNEWS_API_KEY)
        newsapi_news = fetch_newsapi_news(company_name, limit=10, api_key=routes_utils.NEWSAPI_KEY)
        raw_news     = rss_news + gnews_news + newsapi_news

        print(
            f"[News Sources] "
            f"RSS={len(rss_news)} | "
            f"GNews={len(gnews_news)} | "
            f"NewsAPI={len(newsapi_news)}"
        )

        # Emergency fallback to yfinance news
        if not raw_news:
            print(f"[News] All APIs empty for {symbol}, trying yfinance")
            raw_news = ticker.news or []

        if not raw_news:
            result = _build_empty_result(symbol, company_name, company_meta)
            _cache_set(symbol, result)
            return jsonify(result)

        # Clean and deduplicate
        clean_news = _deduplicate(raw_news)
        clean_news = _filter_relevant_news(clean_news, company_name)

        article_payloads = [
            {
                "title":   (item.get("title") or "").strip(),
                "summary": (item.get("summary") or "").strip(),
            }
            for item in clean_news
        ]

        hf_results = _fetch_hf_batch(symbol, company_name, article_payloads)

        # Build news cards and count sentiment
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

        overall_label, overall_score = _overall_sentiment(bullish_count, bearish_count, neutral_count)

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
        return jsonify(result)

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(exc)}), 500
