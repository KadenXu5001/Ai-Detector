The system has five logical layers: the API surface (endpoints + rate limiting), the detection pipeline (multi-signal), the scoring and labeling logic, the appeals workflow, and the persistence layer (SQLite audit log). They interact in a clean one-way flow with the audit log as a cross-cutting concern that receives writes from every layer.

## Signals

- Signal 1 — LLM classifier (Groq): asks the model to score text as human or AI-generated. Captures semantic coherence, stylistic patterns, and narrative quality holistically. It can't capture if a text has been human modifided though
- Signal 2 — Stylometrics (pure Python): computes type-token ratio (vocabulary diversity), sentence length variance, and punctuation density. AI text is statistically more uniform while human writing is noisier. It won't be able to detect common ai words (ie delve).

## Confidence scoring approach

Weighted average of both signals (e.g. 60% LLM, 40% stylometric). 1 = high confidence AI. Thresholds: < 0.35 → high-confidence human, 0.35–0.65 → uncertain, > 0.65 → high-confidence AI.

Asymmetric thresholds intentional: false positives (labeling human as AI) are worse, so the "safe" uncertain band skews toward human.

## Transparency label design

Ai: "This text is likey heavily AI generated, with a [percentage]% confidence of AI generation"

Human: "This text is likey Human created, with a [percentage]% confidence of AI generation"

Uncertin: "It is somewhat uncertain if this text is Ai or Human created, with a [percentage]% confidence of AI generation"

What exact text will the label show for a high-confidence AI result? A high-confidence human result? An uncertain result? Write out the three label variants now, before you build the UI.

## Appeals workflow

POST /appeal accepts content_id + creator_reason. Writes to audit log. Updates content status to "under_review". No automated re-classification.

## Anticipated edge cases

Academic writing or human edited ai will likely become edge cases.

## Rate limiting

The rate limit should be
[your chosen limits + reasoning]

## Audit log schema

fields:

id,
Timestamp
content_id
llm_score
stylometric_score
final_score
label
status (ie appeal / no appeal)

The asymmetric thresholds in the confidence section are worth highlighting in your README — the spec hints at this (false positives are worse) and it'll show graders you read carefully. Want help drafting the label variants or the stylometric heuristics code next?

## Architecture

Here's the previous overview diagram converted to ASCII for your planning.md:
PROVENANCE GUARD — SYSTEM OVERVIEW
===================================

Client (HTTP request)
|
v
+------------------------------------------------+
| API LAYER |
| Flask · POST /submit · POST /appeal · GET /log|
| Flask-Limiter rate limiting |
+------------------------------------------------+
|
v
+------------------------------------------------+
| DETECTION PIPELINE |
| |
| +---------------------+ +------------------+|
| | Signal 1: LLM | | Signal 2: ||
| | classifier | | stylometrics ||
| | Groq · semantic + | | TTR, sent. ||
| | stylistic | | variance, punct. ||
| +---------------------+ +------------------+|
| | | |
| +----------+------------+ |
+------------------------------------------------+
|
v
+------------------------------------------------+
| CONFIDENCE SCORING + TRANSPARENCY LABEL |
| weighted avg → score → label variant: |
| high AI / uncertain / high human |
+------------------------------------------------+
|
+-------------+-------------+
| |
v v
+----------------+ +---------------------+
| JSON response | | AUDIT LOG |
| to client | | (SQLite) |
| result · | | all decisions + |
| confidence · | | appeals logged here |
| label_text · | +---------------------+
| content_id | ^
+----------------+ |
|
+---------------------+
| APPEALS WORKFLOW |
| POST /appeal · |
| capture reason · |
| set under_review |
+---------------------+

## Information state transfer

The text will first traverse through the api endpoint before passing into an LLM classifier to determine whether it is AI or not and then to a stylometric classifier that will check punctuation density, length varience, and vocabulary diversity. finally, it will apply the weighted score and then pass it back to the user. If there is an appeal, it will be announced in an appeals log.

## Information state diagram

# SUBMISSION FLOW

Client
|
| POST /submit {content: "raw text"}
v
+------------------+
| Rate limiter | (Flask-Limiter)
+------------------+
|
| raw text
v
+------------------+
| Signal 1: LLM | Groq llama-3.3-70b
| classifier | "is this human or AI?"
+------------------+
|
| llm_score: 0.0–1.0
v
+------------------+
| Signal 2: | pure Python
| stylometrics | TTR, sent. variance,
| | punct. density
+------------------+
|
| style_score: 0.0–1.0
v
+---------------------------+
| Confidence scorer |
| weighted avg of signals |
| → final score + verdict |
+---------------------------+
|
| combined_score: 0.0–1.0
v
+---------------------------+
| Transparency label |
| score → label variant: |
| <0.35 → "high human" |
| 0.35–0.65 → "uncertain" |
| >0.65 → "high AI" |
+---------------------------+
|  
 |-----> audit log (SQLite)
| writes: content_id, timestamp,
| llm_score, style_score,
| combined_score, label, status
|
| {result, confidence, label_text, content_id}
v
Client ◀── JSON response

# APPEAL FLOW

Creator
|
| POST /appeal {content_id, reason: "..."}
v
+---------------------------+
| Appeals handler |
| validates content_id |
| captures creator reason |
+---------------------------+
|
| content_id + reason
v
+---------------------------+
| Status updater |
| sets status = |
| "under_review" |
+---------------------------+
|
|-----> audit log (SQLite)
| appends: appeal_reason,
| appealed_at, new status
|
| {content_id, status: "under_review", message}
v
Creator ◀── JSON response

## AI Tool Plan

### M3 — Submission endpoint + first signal

**Spec sections to provide:**

- Detection signals section (Signal 1: LLM classifier description)
- System overview ASCII diagram
- Submission flow ASCII diagram (POST /submit → signal 1 → audit log → response)

**What to ask the AI tool to generate:**

- Flask app skeleton: app.py with POST /submit route, request parsing,
  and a placeholder response structure
- First signal function: call_llm_signal(text) that sends the raw text
  to Groq (llama-3.3-70b-versatile) and returns a float 0.0–1.0

**How to verify output:**

- Run call_llm_signal() directly in a Python shell on 3 test inputs:
  (1) a paragraph of dense GPT-style prose
  (2) a casual, typo-filled human blog post
  (3) an ambiguous poem
- Confirm the function returns a float, not a dict or string
- Confirm scores are not all identical (signal is doing something)
- Only wire into the /submit endpoint once all three pass

---

### M4 — Second signal + confidence scoring

**Spec sections to provide:**

- Detection signals section (Signal 2: stylometrics description)
- Confidence scoring + uncertainty section from planning.md
- Both ASCII diagrams (overview + submission flow)

**What to ask the AI tool to generate:**

- Second signal function: call_style_signal(text) computing TTR,
  sentence length variance, and punctuation density; returns float 0.0–1.0
- Scoring logic: combine_scores(llm_score, style_score) applying
  weighted average (60% LLM, 40% style) and returning final_score

**What to check:**

- Run both signals on the same 3 test inputs from M3
- Confirm llm_score and style_score differ from each other on the same
  input (they should — one is semantic, one is structural)
- Confirm combine_scores(0.9, 0.9) ≠ combine_scores(0.2, 0.2) and
  that the spread across inputs feels meaningful, not compressed
- Flag it if all final scores cluster between 0.45–0.55 — that means
  the signals are canceling each other out and thresholds need revisiting

---

### M5 — Production layer

**Spec sections to provide:**

- Transparency label variants (all three verbatim from README)
- Appeals workflow description
- Both ASCII diagrams (overview + appeal flow)

**What to ask the AI tool to generate:**

- Label generation logic: get_label(score) that maps the final score
  to one of the three label variant strings based on thresholds
  (<0.35 → high human, 0.35–0.65 → uncertain, >0.65 → high AI)
- POST /appeal endpoint: accepts content_id + reason, updates status
  to "under_review" in SQLite, appends to audit log, returns JSON

**How to verify:**

- Call get_label() with scores 0.10, 0.50, and 0.90 — confirm all
  three distinct label strings are returned (no variant unreachable)
- POST a test appeal via curl or Postman; confirm response includes
  status: "under_review"
- Query the audit log (GET /log) and confirm the appeal entry appears
  with appeal_reason and appealed_at fields populated
- Confirm a second appeal on the same content_id does not duplicate
  the log row — it should update or append cleanly
