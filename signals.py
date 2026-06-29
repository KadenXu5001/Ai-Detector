"""
signals.py

Detection signal functions. Each returns a float in [0.0, 1.0]
where 1.0 = high confidence AI-generated, 0.0 = high confidence human.

Test each function independently before wiring into app.py.
"""

import json
import math
import os
import re

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


# ── Signal 2: Stylometrics ────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]


def _avg_top_word_lengths(text: str, top_n: int = 3) -> float:
    """Average length of the top-N longest words per sentence, across all sentences."""
    sentences = _split_sentences(text)
    scores = []
    for s in sentences:
        words = re.findall(r'[a-zA-Z]+', s)
        if not words:
            continue
        top = sorted(len(w) for w in words)[-top_n:]
        scores.append(sum(top) / len(top))
    return sum(scores) / len(scores) if scores else 0.0


def _sentence_length_variance(text: str) -> float:
    """Variance of word counts across sentences."""
    sentences = _split_sentences(text)
    lengths = [len(re.findall(r'\S+', s)) for s in sentences if s]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    return sum((l - mean) ** 2 for l in lengths) / len(lengths)


def _punctuation_density(text: str) -> float:
    """Fraction of characters that are punctuation."""
    if not text:
        return 0.0
    punct = sum(1 for c in text if c in '.,;:!?-—…()[]"\'')
    return punct / len(text)


def call_style_signal(text: str) -> float:
    """
    Score text using three stylometric heuristics.

    Metrics:
      - Average top-3 word length per sentence (AI uses longer, more complex words)
      - Sentence length variance (AI is more uniform → low variance → higher AI score)
      - Punctuation density (AI overuses commas/semicolons)

    Returns a float in [0.0, 1.0]: 1.0 = likely AI, 0.0 = likely human.
    """
    # Avg top word length: normalize so 5-char avg = 0.0 (human), 10-char avg = 1.0 (AI)
    word_len_score = max(0.0, min(1.0, (_avg_top_word_lengths(text) - 5.0) / 5.0))

    # Sentence variance: low variance = AI; normalize so variance >= 40 = 0.0 (human)
    variance_score = max(0.0, min(1.0, 1.0 - (_sentence_length_variance(text) / 40.0)))

    # Punctuation density: normalize so >= 5% = 1.0 (AI)
    punct_score = max(0.0, min(1.0, _punctuation_density(text) / 0.05))

    return (word_len_score + variance_score + punct_score) / 3.0


# ── Confidence scoring ────────────────────────────────────────────────────────

def combine_scores(llm_score: float, style_score: float) -> float:
    """
    Weighted average of both signals per planning.md spec: 60% LLM, 40% stylometric.
    Returns a float in [0.0, 1.0].
    """
    return (0.60 * llm_score) + (0.40 * style_score)
