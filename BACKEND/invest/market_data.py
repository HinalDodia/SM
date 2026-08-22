"""
Reads market data for the scoring engine from the SAME DynamoDB tables
your existing EventBridge jobs (run_live_snapshots / run_daily_full_refresh)
already keep fresh. No new table, no new job — this is a read-only
consumer of data you already collect.

Reused from insert.py: get_dynamo(), TABLES dict, AWS_REGION/boto3 setup.
"""

from .insert import get_dynamo, TABLES  # adjust import path to wherever
                                          # insert.py actually lives relative
                                          # to this new module


def _to_float(v):
    """Safe Decimal→float conversion; returns None if v is None/falsy."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _get_latest_price(symbol: str) -> float | None:
    table = get_dynamo().Table(TABLES["stock-page"])
    item = table.get_item(
        Key={"SYMBOL#<sym>": f"SYMBOL#{symbol}", "SNAPSHOT#<date>": "LATEST"}
    ).get("Item", {})
    return _to_float(item.get("data", {}).get("current_price"))


def _get_ratios(symbol: str) -> dict:
    table = get_dynamo().Table(TABLES["stock-financials"])
    item = table.get_item(
        Key={
            "SYMBOL#<sym>": f"SYMBOL#{symbol}",
            "FINANCIALS#<period_type>": "FINANCIALS#annual",
        }
    ).get("Item", {})
    data = item.get("data", {})
    ratios = data.get("ratios", {})

    # revenue_growth lives per-year inside income_statement, not in `ratios`.
    # ASSUMPTION: income_statement[0] is the most recent year — verify this
    # against how financials_page() actually orders the list before relying
    # on it for scoring.
    revenue_growth = None
    income_statement = data.get("income_statement") or []
    if income_statement:
        revenue_growth = income_statement[0].get("revenue_growth")

    return {
        "pe_ratio":      _to_float(ratios.get("pe_ratio")),
        "debt_to_equity":_to_float(ratios.get("debt_to_equity")),
        "revenue_growth":_to_float(revenue_growth),
    }


def _get_volatility_and_change(symbol: str) -> tuple[float | None, float | None]:
    """Computes 6-month annualized volatility and 6-month price change
    from the daily chart data already stored by insert_stock_chart()."""
    table = get_dynamo().Table(TABLES["stock-chart"])
    item = table.get_item(
        Key={
            "SYMBOL#<sym>": f"SYMBOL#{symbol}",
            "CHART#<period>#<interval>": "CHART#1y#1d",
        }
    ).get("Item", {})
    rows = item.get("data", [])
    if not rows or len(rows) < 2:
        return None, None

    # ~126 trading days ≈ 6 months
    window = rows[-126:] if len(rows) >= 126 else rows
    closes = [float(r["close"]) for r in window if r.get("close") is not None]
    if len(closes) < 2:
        return None, None

    price_change_6mo_pct = round((closes[-1] - closes[0]) / closes[0] * 100, 2)

    import math
    log_returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0
    ]
    if not log_returns:
        return None, price_change_6mo_pct

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
    daily_std = variance ** 0.5
    annualized_vol = round(daily_std * (252 ** 0.5), 4)

    return annualized_vol, price_change_6mo_pct


def get_scoring_inputs(symbol: str) -> dict:
    """Single entry point the scoring engine calls. Returns None for any
    field that couldn't be found — the scoring engine must handle missing
    values gracefully (treat as neutral, not as a crash)."""
    symbol = symbol.upper().strip()

    price = _get_latest_price(symbol)
    ratios = _get_ratios(symbol)
    volatility_6mo, price_change_6mo_pct = _get_volatility_and_change(symbol)

    return {
        "symbol": symbol,
        "price": price,
        "pe_ratio": ratios["pe_ratio"],
        "debt_to_equity": ratios["debt_to_equity"],
        "revenue_growth": ratios["revenue_growth"],
        "volatility_6mo": volatility_6mo,
        "price_change_6mo_pct": price_change_6mo_pct,
    }
