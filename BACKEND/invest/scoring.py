"""
Deterministic rules-based scoring engine. No API calls, no DB access —
pure function of (user profile, market data) -> (action, score, reasons, conviction).
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
    conviction: int      # 0-100: how much data backed this read (separate from score)


def _conviction(market: dict, distance_from_neutral: float) -> int:
    """
    0-100 measure of how much data backed the read.
    Separate from the buy/sell/hold score — a hold near 5.0 with lots of
    data has higher conviction than a hold near 5.0 with missing data.

    Calibrated to produce the 50-71% range shown in the UI screenshots:
      - 4 factors present + strong signal  → ~85 (capped at 95)
      - 0 factors present + neutral signal → 35  (floored at 30)
    """
    factors_present = sum(
        1 for k in ("pe_ratio", "debt_to_equity", "revenue_growth", "volatility_6mo")
        if market.get(k) is not None
    )
    base = 35 + (factors_present * 10)           # more data → more conviction
    base += min(20, distance_from_neutral * 8)    # stronger signal → more conviction
    return max(30, min(95, round(base)))


def score_stock(profile: dict, market: dict) -> ScoreResult:
    """
    profile: {"risk_tolerance": "low"|"moderate"|"high", ...}
    market:  output of market_data.get_scoring_inputs() for one symbol
    """
    score = 5.0
    reasons: list[str] = []

    pe = market.get("pe_ratio")
    if pe is not None:
        if pe < 15:
            score += 1.8
            reasons.append(f"P/E of {pe:.1f} is highly attractive (< 15)")
        elif pe < 20:
            score += 1.0
            reasons.append(f"P/E of {pe:.1f} is reasonably valued (< 20)")
        elif pe > 30:
            score -= 1.2
            reasons.append(f"P/E of {pe:.1f} is on the expensive side (> 30)")

    revenue_growth = market.get("revenue_growth")
    if revenue_growth is not None:
        if revenue_growth > 10:
            score += 1.5
            reasons.append(f"Revenue growth of {revenue_growth:.1f}% is strong (> 10%)")
        elif revenue_growth < 0:
            score -= 1.0
            reasons.append(f"Revenue contracted by {abs(revenue_growth):.1f}%")

    price_change = market.get("price_change_6mo_pct")
    if price_change is not None:
        if price_change > 10:
            score += 1.2
            reasons.append(f"Strong 6-month price momentum (+{price_change:.1f}%)")
        elif price_change < -12:
            score -= 1.0
            reasons.append(f"Negative 6-month price drawdown ({price_change:.1f}%)")

    volatility = market.get("volatility_6mo")
    risk = profile.get("risk_tolerance", "moderate")
    if volatility is not None:
        if risk == "low" and volatility > 0.30:
            score -= 1.5
            reasons.append(
                f"6-month volatility of {volatility:.2f} is elevated for a low-risk profile"
            )
        elif risk == "high" and volatility < 0.20:
            score -= 0.5
            reasons.append(
                f"6-month volatility of {volatility:.2f} is low for a high-risk profile"
            )

    score = round(max(0.0, min(10.0, score)), 2)

    if score >= 6.0:
        action = "buy"
    elif score <= 4.2:
        action = "sell"
    else:
        action = "hold"

    if not reasons:
        reasons.append("No strong signals in either direction based on available data")

    # Conviction: distance from neutral (5.0) drives signal strength component
    distance = abs(score - 5.0)
    conviction = _conviction(market, distance)

    return ScoreResult(action=action, score=score, reasons=reasons, conviction=conviction)


def suggested_amount(profile: dict, action: str) -> float:
    """Position size as a % of stated capital, not a fixed number —
    per design doc section 4.4. Only meaningful for 'buy'."""
    if action != "buy":
        return 0.0
    capital = float(profile.get("capital_available", 0))
    max_pct = float(profile.get("max_per_trade_pct", 10.0))
    return round(capital * (max_pct / 100.0), 2)
