"""
Plain-language explanation layer. Takes the scoring engine's OUTPUT
(already-decided action/score/reasons) and asks AWS Bedrock (Amazon Nova)
to return a structured JSON object — never a raw prose paragraph.

Return shape:
    {
        "headline": "Trader, hold on RELIANCE.",
        "bullets":  ["...", "...", "..."],
        "action_plan": "Hold your 12 shares and review after the next quarterly result."
    }

On parse failure, a minimal well-formed dict is returned so callers
never receive None or crash.
"""

import os
import json
import logging
import boto3

log = logging.getLogger(__name__)

_bedrock_client = None


def _get_client():
    global _bedrock_client
    if _bedrock_client is None:
        region = os.getenv("AWS_REGION", "ap-south-1")
        _bedrock_client = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_client


MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "apac.amazon.nova-micro-v1:0")

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are an AI stock analyzer that explains recommendations to retail investors. "
    "A rules-based system has ALREADY decided the action (buy/sell/hold). Your only "
    "job is to explain WHY using ONLY the facts provided — never invent numbers.\n\n"
    "CRITICAL OUTPUT RULE:\n"
    "Return ONLY valid JSON. No prose before or after. No markdown fences. No "
    "explanation outside the JSON. The response must start with { and end with }.\n\n"
    "The JSON must have EXACTLY these three keys:\n"
    '  "headline"    – one sentence, direct, action-first. Address the user by\n'
    "                  their name (use the caller-supplied name, or \"Trader\" if none).\n"
    '  "bullets"     – JSON array of 3 concise strings, each one fact-grounded.\n'
    "                  If position context is provided (avg_buy_price, pnl_pct, qty),\n"
    "                  at least one bullet MUST reference the actual position numbers.\n"
    "                  If no position, do NOT fabricate position data.\n"
    '  "action_plan" – one sentence: the concrete next step for THIS user.\n\n'
    "Calibrate language to the experience level (beginner: plain English; "
    "intermediate: standard terms; advanced: technical terms welcome). "
    "Do not add financial-advice disclaimers."
)


def _fallback(action: str, symbol: str, reasons: list, name: str) -> dict:
    """Minimal structured object used when Bedrock fails or is unavailable."""
    verb = {"buy": "consider buying", "sell": "consider selling", "hold": "hold"}.get(
        action, "review"
    )
    return {
        "headline": f"{name}, {verb} {symbol} based on current signals.",
        "bullets": reasons[:3] if reasons else ["No detailed signals available."],
        "action_plan": f"Review {symbol} again before your next trading session.",
    }


def explain(
    profile: dict,
    symbol: str,
    action: str,
    score: float,
    reasons: list,
    conviction: int = 50,
    position: dict | None = None,
) -> dict:
    """
    Returns a structured dict with keys: headline, bullets, action_plan.
    Never raises — always returns a valid dict even if Bedrock is unavailable.

    position (optional): pass when the user holds shares of this stock so
        the bullets can reference their actual avg price / P&L %.
        Pass None for Market / Watchlist context (no fabrication).
    """
    name = profile.get("display_name") or "Trader"
    experience = profile.get("experience_level", "beginner")
    symbol = symbol.upper().strip()

    # ── Build user message ────────────────────────────────────────────────────
    pos_lines = ""
    if position:
        pos_lines = (
            f"\nUser's position in {symbol}:\n"
            f"  Shares held:      {position.get('qty', '?')}\n"
            f"  Avg buy price:    ₹{position.get('avg_buy_price', '?')}\n"
            f"  Current P&L:      {position.get('pnl_pct', '?')}%\n"
        )

    user_message = (
        f"Stock: {symbol}\n"
        f"Decision (already made, do NOT change): {action.upper()}\n"
        f"Score: {score}/10  |  Conviction: {conviction}%\n"
        f"Reasons the scoring system used:\n"
        + "\n".join(f"  - {r}" for r in reasons)
        + pos_lines
        + f"\nUser's name: {name}\n"
        f"User's experience level: {experience}\n"
        f"User's stated goal: {profile.get('investment_goal', 'growth')}\n"
        f"User's risk tolerance: {profile.get('risk_tolerance', 'moderate')}\n"
        f"User's time horizon: {profile.get('time_horizon', 'medium_term')}\n"
        f"\nReturn the JSON object now."
    )

    try:
        client = _get_client()

        body = {
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "system": [{"text": _SYSTEM_PROMPT}],
            "inferenceConfig": {
                "maxTokens": 400,
                "temperature": 0.3,
            },
        }

        response = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        raw_body = response["body"].read().decode("utf-8")
        resp_json = json.loads(raw_body)

        # Nova Micro response structure: output.message.content[0].text
        raw = ""
        try:
            raw = resp_json["output"]["message"]["content"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            # Fallback: look for any text field
            raw = str(resp_json)

        # Strip accidental markdown fences if model adds them despite instructions
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")].strip()

        parsed = json.loads(raw)

        # Validate shape — ensure all three keys are present
        headline = str(parsed.get("headline", "")).strip()
        bullets = parsed.get("bullets", [])
        action_plan = str(parsed.get("action_plan", "")).strip()

        if not isinstance(bullets, list):
            bullets = [str(bullets)]

        if not headline or not action_plan or not bullets:
            raise ValueError("Missing required keys in model response")

        return {
            "headline": headline,
            "bullets": [str(b) for b in bullets],
            "action_plan": action_plan,
        }

    except Exception as e:
        # Any failure (Bedrock unavailable, parse error, etc.) — degrade gracefully
        log.warning("Bedrock explain call failed for %s: %s", symbol, e)
        return _fallback(action, symbol, reasons, name)
