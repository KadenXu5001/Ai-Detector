"""
signals.py

Detection signal functions. Each returns a float in [0.0, 1.0]
where 1.0 = high confidence AI-generated, 0.0 = high confidence human.

Test each function independently before wiring into app.py.
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_LLM_MODEL = "llama-3.3-70b-versatile"


def _get_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Add it to a .env file.")
    return Groq(api_key=api_key)


# ── Signal 1: LLM classifier ──────────────────────────────────────────────────

def call_llm_signal(text: str) -> float:
    """
    Ask an LLM to score the text as human or AI-generated.

    Returns a float in [0.0, 1.0]:
        0.0 = clearly human-written
        1.0 = clearly AI-generated

    Raises ValueError if the response cannot be parsed as a float score.
    """
    client = _get_groq_client()

    prompt = (
        "Score the following text on a scale from 0.0 to 1.0, where:\n"
        "  0.0 = clearly human-written (natural, varied, imperfect)\n"
        "  1.0 = clearly AI-generated (uniform, coherent, formulaic)\n\n"
        "Consider: semantic coherence, stylistic uniformity, sentence rhythm,\n"
        "hedging patterns, and narrative naturalness.\n\n"
        "Respond with ONLY a JSON object — no explanation, no extra text:\n"
        '{"score": <float between 0.0 and 1.0>}\n\n'
        f"Text to score:\n{text}"
    )

    response = client.chat.completions.create(
        model=_LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=20,
    )

    raw = (response.choices[0].message.content or "").strip()

    try:
        payload = json.loads(raw)
        score = float(payload["score"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"call_llm_signal: could not parse score from response: {raw!r}"
        ) from exc

    return max(0.0, min(1.0, score))
