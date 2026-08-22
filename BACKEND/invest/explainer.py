"""
Structured explanation layer. Takes the scoring engine's output
(already-decided action/score/reasons) and asks Claude to return a
structured JSON object — headline, bullet reasons, and action plan.

Return value is always a dict:
    {
        "headline":    "Trader, hold on RELIANCE.",
        "bullets":     ["You're up 6.35% ...", "Energy sector ...", "Nothing demands action."],
        "action_plan": "Hold your 12 shares and review after the next quarterly result."
    }

If Claude is unreachable or returns unparseable JSON, a minimal structured
fallback is returned — the caller is never handed a bare string or None.
"""

import json
import os

from anthropic import Anthropic

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is missing from environment variables (.env) "
                "— cannot generate explanations."
            )
        _client = Anthropic(api_key=api_key)
    return _client


# ─── System prompt ────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are the personal stock analyzer for a retail investor using a trading app.
A separate rules-based system has ALREADY decided the action (buy / sell / hold)
and scored it — your ONLY job is to explain WHY in the user's language.

OUTPUT FORMAT — you must return ONLY a valid JSON object, nothing else.
No markdown fences, no prose before or after. The exact shape:
{
  "headline":    "<one sentence — see style guide below>",
  "bullets":     ["<fact 1>", "<fact 2>", "<fact 3>"],
  "action_plan": "<one concise sentence on what the user should do next>"
}

HEADLINE STYLE GUIDE (pick the most fitting variant):
- Plain informational hold  → "Trader, hold on {SYMBOL}."
  or with name              → "{name}, hold on {SYMBOL}."
- Low-conviction hold       → "No edge right now, {name}. Watch it, don't chase it."
- Risk-driven sell / avoid  → "Risk outweighs reward for your profile today."
- Strong buy signal         → "{name}, {SYMBOL} looks worth adding at this level."
- General sell              → "Time to trim, {name}. The signal has flipped."

BULLET RULES:
- Exactly 3 bullets. Each is one factual sentence.
- If position data is provided (avg_buy_price, pnl_pct, qty), the FIRST bullet
  MUST reference the user's actual position (e.g. "You're up X% on an average
  price of ₹Y against an LTP of ₹Z."). Never invent position data.
- If no position data, bullets cover: valuation signal, volatility / risk fit,
  and one market-context fact. Do not fabricate prices or P&L figures.
- Do not introduce numbers that weren't in the input.
- Calibrate jargon to experience level: plain language for beginner,
  standard financial terms fine for advanced.

ACTION PLAN RULES:
- One sentence. Concrete. Matches the action (buy / sell / hold).
- If position data is present, reference qty or holding where natural.
- Do not add disclaimers here — they go in bullets if needed.

CRITICAL: Return ONLY the JSON object. Any text outside the JSON will break the parser.\
"""


def _fallback(name: str, symbol: str, action: str, reasons: list[str]) -> dict:
    """Minimal structured response used when Claude is down or returns bad JSON."""
    action_lines = {
        "buy":  f"Consider adding {symbol} in line with your risk budget.",
        "sell": f"Review your position in {symbol} and consider reducing exposure.",
        "hold": f"Hold {symbol} and revisit after the next data update.",
    }
    return {
        "headline": f"{name}, {action} on {symbol}.".capitalize(),
        "bullets":  reasons[:3] if reasons else ["No strong signals in available data."],
        "action_plan": action_lines.get(action, f"Review {symbol} before acting."),
    }


def explain(
    profile: dict,
    symbol: str,
    action: str,
    score: float,
    reasons: list[str],
    position: dict | None = None,
) -> dict:
    """
    Build a structured explanation for a stock recommendation.

    Args:
        profile:  User profile dict (risk_tolerance, investment_goal,
                  time_horizon, experience_level, display_name, ...).
        symbol:   Stock ticker, e.g. "RELIANCE".
        action:   "buy" | "sell" | "hold" — already decided by scoring.py.
        score:    Float 0-10 from the scoring engine.
        reasons:  List of short factual reason strings from scoring.py.
        position: Optional dict with keys avg_buy_price (float), pnl_pct (float),
                  qty (int). Pass None when there is no held position
                  (Market / Watchlist context).

    Returns:
        dict with keys: headline (str), bullets (list[str]), action_plan (str).
        Never raises — falls back to a minimal structured response on any error.
    """
    name = (profile.get("display_name") or "Trader").strip() or "Trader"
    experience = profile.get("experience_level", "beginner")

    # ── Build position block (only when caller has real data) ─────────────────
    position_block = ""
    if position:
        avg = position.get("avg_buy_price")
        pnl = position.get("pnl_pct")
        qty = position.get("qty")
        ltp = position.get("ltp")
        parts = []
        if qty is not None:
            parts.append(f"Quantity held: {qty} shares")
        if avg is not None:
            parts.append(f"Average buy price: ₹{avg:.2f}")
        if ltp is not None:
            parts.append(f"Current LTP: ₹{ltp:.2f}")
        if pnl is not None:
            parts.append(f"Unrealised P&L: {pnl:+.2f}%")
        if parts:
            position_block = "\nUser's current position:\n" + "\n".join(
                f"  {p}" for p in parts
            )

    # ── Build user message ────────────────────────────────────────────────────
    user_message = (
        f"User's name: {name}\n"
        f"Stock: {symbol}\n"
        f"Decision (already made, do NOT change): {action.upper()}\n"
        f"Score: {score}/10\n"
        f"Scoring reasons:\n"
        + "\n".join(f"  - {r}" for r in reasons)
        + f"\n\nUser profile:\n"
        f"  Experience level: {experience}\n"
        f"  Investment goal:  {profile.get('investment_goal', 'not set')}\n"
        f"  Risk tolerance:   {profile.get('risk_tolerance', 'moderate')}\n"
        f"  Time horizon:     {profile.get('time_horizon', 'not set')}\n"
        + (f"  Goal text:        {profile.get('goal_text')}\n"
           if profile.get("goal_text") else "")
        + position_block
        + "\n\nReturn the JSON object now."
    )

    # ── Call Claude ───────────────────────────────────────────────────────────
    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

        # Strip accidental markdown fences if Claude still wraps them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)

        # Validate shape — fall back gracefully on partial or wrong output
        headline    = str(parsed.get("headline", "")).strip()
        bullets_raw = parsed.get("bullets", [])
        action_plan = str(parsed.get("action_plan", "")).strip()

        if not isinstance(bullets_raw, list):
            bullets_raw = [str(bullets_raw)]
        bullets = [str(b).strip() for b in bullets_raw if str(b).strip()]

        if not headline or not bullets or not action_plan:
            raise ValueError("Parsed JSON missing required fields")

        return {"headline": headline, "bullets": bullets, "action_plan": action_plan}

    except RuntimeError:
        # ANTHROPIC_API_KEY not set — return fallback, don't crash
        return _fallback(name, symbol, action, reasons)
    except Exception:
        # JSON parse error, network error, validation error — same fallback
        return _fallback(name, symbol, action, reasons)
