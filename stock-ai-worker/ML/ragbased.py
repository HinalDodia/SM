import string
import os
import json
from transformers import pipeline

BASE_DIR = os.path.dirname(__file__)
KB_PATH = os.path.join(BASE_DIR, "kb.json")

with open(KB_PATH, "r") as f:
    KB = json.load(f)

# ── FinBERT for real financial sentiment ──────────────────────────────────────
_finbert = None

def get_finbert():
    global _finbert
    if _finbert is None:
        _finbert = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            framework="pt"
        )
    return _finbert

# ── Keyword fallback (your existing logic, kept as backup) ────────────────────
def normalize(text: str) -> str:
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    return text.strip()

impact_to_sentiment = {
    "bullish": "bullish",
    "positive": "bullish",
    "possible undervaluation": "bullish",
    "may attract investors": "bullish",
    "bearish": "bearish",
    "fear": "bearish",
    "risk of correction": "bearish",
    "overbought risk": "bearish",
    "neutral": "neutral"
}

def getimpact(headline, summary, kb=KB):
    combined = (headline + " " + summary).lower()
    results = [impact for k, impact in kb.items() if k in combined]
    return results if results else ["no clear impact detected"]

def impacttosentiment(impacts):
    score = {"bullish": 0, "bearish": 0, "neutral": 0}
    for i in impacts:
        ilower = i.lower()
        for k, s in impact_to_sentiment.items():
            if k in ilower:
                score[s] += 1
    return max(score, key=score.get)

# ── Primary: FinBERT-based sentiment ─────────────────────────────────────────
def get_finbert_sentiment(headline: str, summary: str):
    """
    Returns (sentiment, confidence) using FinBERT.
    FinBERT labels: positive → bullish, negative → bearish, neutral → neutral
    """
    try:
        finbert = get_finbert()
        text = f"{headline}. {summary}"[:512]  # BERT token limit
        result = finbert(text)[0]

        label_map = {
            "positive": "bullish",
            "negative": "bearish",
            "neutral":  "neutral"
        }

        sentiment = label_map.get(result["label"].lower(), "neutral")
        confidence = round(result["score"], 4)
        return sentiment, confidence

    except Exception as e:
        print(f"⚠️ FinBERT error: {e}")
        return None, 0.0

# ── Hybrid: FinBERT + keyword confirmation ────────────────────────────────────
def get_hybrid_sentiment(headline: str, summary: str):
    """
    Primary: FinBERT
    If FinBERT confidence < 0.65, fallback to keyword matching.
    Returns dict with sentiment, confidence, source.
    """
    sentiment, confidence = get_finbert_sentiment(headline, summary)

    if sentiment and confidence >= 0.65:
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "source": "finbert"
        }

    # Fallback to keyword matching
    impacts = getimpact(headline, summary)
    keyword_sentiment = impacttosentiment(impacts)
    return {
        "sentiment": keyword_sentiment,
        "confidence": 0.5,
        "source": "keyword_fallback"
    }

# ── Market action mapping ─────────────────────────────────────────────────────
sentiment_to_reaction = {
    "bullish": "Buying pressure",
    "bearish": "Selling pressure",
    "neutral": "Hold or sideways"
}

reaction_to_action = {
    "Buying pressure":              "Consider increasing positions",
    "Selling pressure":             "Consider reducing positions or hedging",
    "Hold or sideways":             "Hold positions, monitor closely"
}

def sentiment_to_market_action(sentiment):
    reaction = sentiment_to_reaction.get(sentiment, "Hold or sideways")
    action = reaction_to_action.get(reaction, "Hold positions, monitor closely")
    return reaction, action