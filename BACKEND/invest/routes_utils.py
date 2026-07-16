"""
Shared constants and simple utilities used across multiple route modules.

Keeping these here avoids repeating them in every module and ensures
there is a single place to update API keys or base URLs.
"""

import os

# ── HuggingFace ────────────────────────────────────────────────────────────────

HF_BASE_URL = os.getenv("HF_SPACE_URL")
HF_HEADERS  = {"Authorization": "Bearer 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"}

# ── News API keys ──────────────────────────────────────────────────────────────

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
NEWSAPI_KEY   = os.getenv("NEWSAPI_KEY")


# ── Yahoo Finance symbol normalization ─────────────────────────────────────────

def get_yf_symbol(symbol: str) -> str:
    """
    Convert a bare NSE symbol to a Yahoo Finance symbol.
    Already-suffixed symbols (e.g. 'TCS.NS', 'RELIANCE.BO') are returned unchanged.
    """
    symbol = symbol.upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"
