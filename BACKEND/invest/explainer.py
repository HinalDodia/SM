"""
Plain-language explanation layer. Takes the scoring engine's OUTPUT
(already-decided action/score/reasons) and asks Claude to explain it in
plain English calibrated to the user's experience level.

This is the one genuinely new piece of infra for this feature — there is
no existing Anthropic API usage anywhere else in the codebase yet.

Setup needed (not yet done anywhere in this repo):
  pip install anthropic
  Add ANTHROPIC_API_KEY to .env
  Add ANTHROPIC_API_KEY to the required-env-vars line in PROJECT_SUMMARY.md
"""

import os
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

_client = None


def _get_client():
    global _client
    if Anthropic is None:
        raise RuntimeError(
            "anthropic package is not installed. Please run `pip install anthropic`."
        )
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is missing from environment variables (.env) "
                "— cannot generate explanations."
            )
        _client = Anthropic(api_key=api_key)
    return _client


_SYSTEM_PROMPT = """You explain a stock recommendation in plain, jargon-free \
English for a retail investor. You are given a decision that has ALREADY \
been made by a separate rules-based system — your only job is to explain \
WHY, using only the facts provided to you.

Strict rules:
- Do not introduce any numbers, prices, ratios, or facts that are not in \
the input you were given. If you don't have a number, don't invent one.
- Do not change or second-guess the action (buy/sell/hold) — explain it \
as given, even if you would have picked differently.
- Calibrate language to the stated experience level: avoid financial \
jargon for 'beginner', it's fine to use standard terms for 'advanced'.
- 3-4 sentences. End with exactly one line reminding the user this is \
not professional financial advice.
"""


def explain(profile: dict, symbol: str, action: str, score: float, reasons: list[str]) -> str:
    experience = profile.get("experience_level", "beginner")

    user_message = (
        f"Stock: {symbol}\n"
        f"Decision (already made, do not change): {action.upper()}\n"
        f"Score: {score}/10\n"
        f"Reasons the scoring system used:\n"
        + "\n".join(f"- {r}" for r in reasons)
        + f"\n\nUser's experience level: {experience}\n"
        f"User's stated goal: {profile.get('investment_goal')}\n"
        f"User's risk tolerance: {profile.get('risk_tolerance')}\n\n"
        "Explain this recommendation in plain English."
    )

    client = _get_client()
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
