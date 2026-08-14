"""
Deterministic rules-based scoring engine. No API calls, no DB access —
pure function of (user profile, market data) -> (action, score, reasons).
This is intentionally the only component allowed to decide buy/sell/hold;
the Claude explainer (explainer.py) only explains this output, never
overrides it.
"""

from dataclasses import dataclass


@dataclass
class ScoreResult:
    action: str          # "buy" | "sell" | "hold"
    score: float
    reasons: list[str]   # short, factual reasons — fed to the explainer


def score_stock(profile: dict, market: dict) -> ScoreResult:
    """
    profile: {"risk_tolerance": "low"|"moderate"|"high", ...}
    market:  output of market_data.get_scoring_inputs() for one symbol
    """
    score = 5.0
    reasons: list[str] = []

    pe = market.get("pe_ratio")
    if pe is not None:
        if pe < 20:
            score += 1
            reasons.append(f"P/E of {pe} is reasonably valued (< 20)")
        elif pe > 35:
            score -= 1
            reasons.append(f"P/E of {pe} is on the expensive side (> 35)")

    revenue_growth = market.get("revenue_growth")
    if revenue_growth is not None and revenue_growth > 10:
        score += 1.5
        reasons.append(f"Revenue growth of {revenue_growth}% is strong (> 10%)")

    volatility = market.get("volatility_6mo")
    risk = profile.get("risk_tolerance")
    if volatility is not None:
        if risk == "low" and volatility > 0.35:
            score -= 2
            reasons.append(
                f"6-month volatility of {volatility} is high for a low-risk profile"
            )
        elif risk == "high" and volatility < 0.15:
            score -= 0.5
            reasons.append(
                f"6-month volatility of {volatility} is low — may not suit a "
                f"high-risk / high-growth-seeking profile"
            )

    score = round(max(0.0, min(10.0, score)), 2)

    if score >= 7:
        action = "buy"
    elif score >= 4.5:
        action = "hold"
    else:
        action = "sell"

    if not reasons:
        reasons.append("No strong signals in either direction based on available data")

    return ScoreResult(action=action, score=score, reasons=reasons)


def suggested_amount(profile: dict, action: str) -> float:
    """Position size as a % of stated capital, not a fixed number —
    per design doc section 4.4. Only meaningful for 'buy'."""
    if action != "buy":
        return 0.0
    capital = float(profile.get("capital_available", 0))
    max_pct = float(profile.get("max_per_trade_pct", 10.0))
    return round(capital * (max_pct / 100.0), 2)
