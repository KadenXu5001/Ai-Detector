"""
app.py

Provenance Guard — Flask API surface.

Routes:
    POST /submit   — run detection pipeline, return result + audit log entry
    POST /appeal   — flag a content_id for human review  [wired in M5]
    GET  /log      — return audit log entries as JSON

Run with:
    python app.py
"""

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from db import (
    fetch_all_entries,
    generate_content_id,
    init_db,
    update_appeal,
    write_log_entry,
)
from signals import call_llm_signal

app = Flask(__name__)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
)

with app.app_context():
    init_db()


# ── POST /submit ───────────────────────────────────────────────────────────────

@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute")
def submit():
    """
    Accepts JSON: {"text": "<text to analyze>", "creator_id": "<optional>"}

    Returns JSON:
        {
          "content_id":  str,
          "attribution": "likely_ai" | "likely_human" | "uncertain",
          "confidence":  float,
          "label":       str,
          "llm_score":   float
        }
    """
    body = request.get_json(silent=True)
    if not body or not body.get("text", "").strip():
        return jsonify({"error": "Request body must include a non-empty 'text' field."}), 400

    text = body["text"].strip()
    creator_id = body.get("creator_id")
    content_id = generate_content_id()

    # Signal 1: LLM classifier
    llm_score = call_llm_signal(text)

    # M4 placeholder: second signal not yet wired; confidence = llm_score for now
    confidence = llm_score

    # Attribution thresholds
    if confidence < 0.35:
        attribution = "likely_human"
        label = (
            f"This text is likely human created, with a "
            f"{confidence * 100:.0f}% confidence of AI generation."
        )
    elif confidence > 0.65:
        attribution = "likely_ai"
        label = (
            f"This text is likely heavily AI generated, with a "
            f"{confidence * 100:.0f}% confidence of AI generation."
        )
    else:
        attribution = "uncertain"
        label = (
            f"It is somewhat uncertain if this text is AI or human created, with a "
            f"{confidence * 100:.0f}% confidence of AI generation."
        )

    write_log_entry(
        content_id=content_id,
        creator_id=creator_id,
        llm_score=llm_score,
        confidence=confidence,
        attribution=attribution,
    )

    return jsonify({
        "content_id":  content_id,
        "attribution": attribution,
        "confidence":  confidence,
        "label":       label,
        "llm_score":   llm_score,
    })


# ── POST /appeal ───────────────────────────────────────────────────────────────

@app.route("/appeal", methods=["POST"])
def appeal():
    """
    Accepts JSON: {"content_id": str, "reason": str}
    Marks the entry under_review in the audit log.
    """
    body = request.get_json(silent=True)
    if not body or not body.get("content_id") or not body.get("reason", "").strip():
        return jsonify({"error": "Request body must include 'content_id' and 'reason'."}), 400

    content_id = body["content_id"]
    reason = body["reason"].strip()

    found = update_appeal(content_id, reason)
    if not found:
        return jsonify({"error": f"content_id '{content_id}' not found in audit log."}), 404

    return jsonify({
        "content_id": content_id,
        "status":     "under_review",
        "message":    "Your appeal has been recorded and will be reviewed.",
    })


# ── GET /log ───────────────────────────────────────────────────────────────────

@app.route("/log", methods=["GET"])
def log():
    """Return all audit log entries as JSON, newest first."""
    return jsonify({"entries": fetch_all_entries()})


# ── run ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
