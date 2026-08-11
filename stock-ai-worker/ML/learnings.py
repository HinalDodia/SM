from invest.summarizermodel import summarize_news
from invest.ragbased import impacttosentiment, getimpact, sentiment_to_market_action

from datetime import datetime
import os
import json
import requests

# -------------------------
# Load API key from ENV
# -------------------------
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")


def getheadlines():
    if not GNEWS_API_KEY:
        raise ValueError("❌ GNEWS_API_KEY not set in environment variables")

    url = (
        "https://gnews.io/api/v4/search"
        "?q=stock%20market"
        "&lang=en"
        "&country=in"
        f"&token={GNEWS_API_KEY}"
    )

    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])[:5]

        cleaned_articles = []
        for article in articles:
            cleaned_articles.append({
                "title": article.get("title", "").strip(),
                "description": article.get("description", "").strip()
            })

        return cleaned_articles

    else:
        print("❗ GNews API error:", response.status_code, response.text)
        return []


def get_news():
    try:
        cache_path = "cache_news.json"

        # -------------------------
        # Use cached data if fresh
        # -------------------------
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as file:
                    json_data = json.load(file)
                    last_updated = datetime.fromisoformat(
                        json_data.get("last_updated", "1970-01-01")
                    ).date()

                    if last_updated == datetime.now().date():
                        return json_data
            except Exception as e:
                print("❗ Cache read failed:", e)

        # -------------------------
        # Fetch fresh news
        # -------------------------
        latest = getheadlines()
        if not latest:
            return {"error": "No news from API"}

        newsdata = []

        for article in latest:
            try:
                desc = article.get("description") or ""
                summary = desc if len(desc) < 20 else summarize_news(desc)

                impacts = getimpact(article["title"], summary)
                sentiment = impacttosentiment(impacts)
                reaction, action = sentiment_to_market_action(sentiment)

                newsdata.append({
                    "headline": article["title"],
                    "summary": summary,
                    "sentiment": sentiment,
                    "market_reaction": reaction,
                    "investor_reaction": action
                })

            except Exception as e:
                print("❗ Error processing article:", e)

        json_data = {
            "last_updated": datetime.now().isoformat(),
            "news": newsdata
        }

        with open(cache_path, "w") as file:
            json.dump(json_data, file, indent=2)

        return json_data

    except Exception as e:
        print("❗ Fatal error in get_news:", e)
        return {"error": str(e)}
