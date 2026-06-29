# Provenance Guard

An AI-generated text detection API. Submit a piece of writing and get back an attribution result, a calibrated confidence score, and a plain-language transparency label. Every decision is logged to a structured audit trail, and creators can file an appeal if they believe the classification is wrong.

---

## Running the Server

```powershell
# Install dependencies
pip install -r requirements.txt

# Start the Flask server
python app.py
```

Server runs at `http://localhost:5000`. Open `index.html` in a browser to use the frontend (Flask must be running).

---

## API Reference

See `commands.md` for full curl examples.

### `POST /submit`

Analyze text and return an attribution result.

**Request:**

```json
{ "text": "your text here", "creator_id": "optional-user-id" }
```

**Response:**

```json
{
  "content_id": "3ff577df-4031-4023-93f8-d8386762b2ba",
  "attribution": "likely_ai",
  "confidence": 0.69,
  "label": "This text is likely heavily AI generated, with a 69% confidence of AI generation.",
  "llm_score": 0.8,
  "style_score": 0.53
}
```

### `POST /appeal`

Flag a submission for human review.

**Request:**

```json
{ "content_id": "3ff577df-...", "creator_reasoning": "I wrote this myself." }
```

### `GET /log`

Return all audit log entries as JSON, newest first.

---

## Architecture

```
Client (HTTP request)
|
v
+------------------------------------------------+
| API LAYER                                      |
| Flask · POST /submit · POST /appeal · GET /log |
| Flask-Limiter rate limiting                    |
+------------------------------------------------+
                        |
                        v
+------------------------------------------------+
| DETECTION PIPELINE                             |
|                                                |
| +---------------------+ +------------------+  |
| | Signal 1: LLM       | | Signal 2:        |  |
| | classifier          | | stylometrics     |  |
| | Groq · semantic +   | | top-k length, sent.       |  |
| | stylistic           | | variance, punct. |  |
| +---------------------+ +------------------+  |
|           |                     |             |
|           +----------+----------+             |
+------------------------------------------------+
                        |
                        v
+------------------------------------------------+
| CONFIDENCE SCORING + TRANSPARENCY LABEL        |
| weighted avg → score → label variant:          |
| high AI / uncertain / high human               |
+------------------------------------------------+
                        |
          +-------------+-------------+
          |                           |
          v                           v
+----------------+         +---------------------+
| JSON response  |         | AUDIT LOG           |
| to client      |         | (SQLite)            |
| result ·       |         | all decisions +     |
| confidence ·   |         | appeals logged here |
| label_text ·   |         +---------------------+
| content_id     |                   ^
+----------------+                   |
                                      |
                          +---------------------+
                          | APPEALS WORKFLOW    |
                          | POST /appeal ·      |
                          | capture reason ·    |
                          | set under_review    |
                          +---------------------+
```

## Detection Pipeline

Provenance Guard runs two independent signals on every submission and combines them into a single confidence score.

### Signal 1 — LLM Classifier (Groq)

Sends the raw text to `llama-3.3-70b-versatile` with a prompt asking it to score the text from 0.0 (clearly human) to 1.0 (clearly AI). The model evaluates semantic coherence, stylistic uniformity, sentence rhythm, and hedging patterns holistically.

**What it captures:** High-level narrative quality, formulaic phrasing, and the kind of structural polish that AI consistently produces regardless of topic.

**What it misses:** Text that has been substantially rewritten by a human after AI generation. If a person edits the output enough to break the AI's characteristic flow, the LLM signal may score it low even though AI was involved in drafting.

### Signal 2 — Stylometrics (Pure Python)

Computes three structural metrics without calling any external API:

- **Average top-3 word length per sentence** — AI writing skews toward longer, more complex vocabulary ("transformative," "stakeholders," "paradigm"). Averaged across the longest words in each sentence, this captures vocabulary complexity without being thrown off by common short words.
- **Sentence length variance** — AI produces sentences with strikingly uniform rhythm. Low variance means the sentences are all roughly the same length, which is a reliable structural marker.
- **Punctuation density** — AI text tends to overuse commas and semicolons relative to total character count.

**What it captures:** Surface-level structural uniformity that persists even when AI text is lightly edited for content.

**What it misses:** Academic or legal human writing, which also uses long words and formal sentence structure. A PhD thesis could score higher than expected on this signal even if written entirely by a human.

### Confidence Scoring

The two signals are combined using a weighted average:

```
confidence = (0.60 × llm_score) + (0.40 × style_score)
```

The LLM signal carries more weight because it captures semantic patterns that stylometrics cannot. The 40% stylometric weight is enough to shift borderline cases without overriding a strong LLM signal.

**Thresholds:**

| Score range | Attribution    | Rationale                     |
| ----------- | -------------- | ----------------------------- |
| < 0.35      | `likely_human` | High confidence human         |
| 0.35 – 0.65 | `uncertain`    | Insufficient signal to commit |
| > 0.65      | `likely_ai`    | High confidence AI            |

The thresholds are asymmetric by design: the uncertain band skews toward human. **False positives (labeling human writing as AI) are worse than false negatives** — a creator wrongly flagged as using AI faces reputational harm, while a missed AI submission is less severe. The wide uncertain band reflects this.

**Validation:** The pipeline was tested against four deliberately chosen inputs spanning the full confidence range — clearly AI prose, casual human writing, formal academic text, and lightly edited AI output. Results:

| Input                | LLM   | Style | Combined | Attribution    |
| -------------------- | ----- | ----- | -------- | -------------- |
| Dense AI prose       | 0.800 | 0.526 | 0.690    | `likely_ai`    |
| Casual human writing | 0.200 | 0.314 | 0.246    | `likely_human` |
| Formal academic text | 0.800 | 0.459 | 0.664    | `likely_ai`    |
| Lightly edited AI    | 0.400 | 0.569 | 0.468    | `uncertain`    |

Dense AI prose example:
"Artificial intelligence represents a transformative paradigm shift in modern society. "
"It is important to note that while the benefits of AI are numerous, it is equally "
"essential to consider the ethical implications. Furthermore, stakeholders across "
"various sectors must collaborate to ensure responsible deployment."

Casual human writing example:
"ok so i finally tried that new ramen place downtown and honestly? "
"underwhelming. the broth was fine but they put WAY too much sodium in it and "
"i was thirsty for like three hours after. my friend got the spicy version and "
"said it was better. probably won't go back unless someone drags me there"

The signals disagreed meaningfully on the lightly-edited AI input (LLM saw it as borderline, stylometrics leaned AI), which is the weighted average working as intended — neither signal alone would have produced the right uncertainty.

---

## Transparency Label

Every submission response includes a plain-language label. The label text changes based on the confidence score:

**High-confidence AI** (`confidence > 0.65`):

> "This text is likely heavily AI generated, with a [X]% confidence of AI generation."

**Uncertain** (`0.35 ≤ confidence ≤ 0.65`):

> "It is somewhat uncertain if this text is AI or human created, with a [X]% confidence of AI generation."

**High-confidence human** (`confidence < 0.35`):

> "This text is likely human created, with a [X]% confidence of AI generation."

The percentage shown is the combined confidence score expressed as a whole number. The label is written for a non-technical reader — no references to classifiers, model outputs, or scoring functions.

---

## Appeals Workflow

Creators who believe a submission was misclassified can file an appeal via `POST /appeal`. The endpoint:

1. Validates that the `content_id` exists in the audit log
2. Records the creator's reasoning
3. Updates the entry's status to `"under_review"`
4. Returns confirmation

No automated re-classification occurs, though next steps will likely continue this. Appeals are surfaced in `GET /log` with the `appeal_reason` and `appealed_at` fields populated.

---

## Rate Limiting

`POST /submit` is rate-limited to **10 requests per minute and 100 requests per day per IP address.**

**Reasoning:** A writer submitting their own work for review would rarely need more than a few submissions per minute — 10/min is generous for manual, legitimate use. The 100/day cap prevents sustained scripted abuse across a full session without blocking any realistic human workflow. Exceeding either limit returns a `429 Too Many Requests` response.

---

## Audit Log

Every call to `POST /submit` writes a structured entry to a SQLite database (`audit_log.db`). Fields:

| Field               | Description                                              |
| ------------------- | -------------------------------------------------------- |
| `content_id`        | UUID identifying this submission                         |
| `creator_id`        | Submitter identifier (optional)                          |
| `timestamp`         | ISO 8601 UTC timestamp                                   |
| `llm_score`         | Raw score from the LLM signal (0.0–1.0)                  |
| `stylometric_score` | Raw score from the stylometric signal (0.0–1.0)          |
| `confidence`        | Combined weighted score (0.0–1.0)                        |
| `attribution`       | Final label: `likely_ai`, `likely_human`, or `uncertain` |
| `status`            | `classified` or `under_review`                           |
| `appeal_reason`     | Creator's reasoning (populated after an appeal)          |
| `appealed_at`       | Timestamp of appeal (populated after an appeal)          |

Retrieve entries with `GET /log` — returns structured JSON, not console output.

"entries": [
{
"appeal_reason": "Not ai",
"appealed_at": "2026-06-29T06:26:21.637Z",
"attribution": "likely_ai",
"confidence": 0.6755555555555556,
"content_id": "4e00f54f-5dd4-4dbc-ba26-002ae045425f",
"creator_id": "kaden1",
"id": 11,
"llm_score": 0.8,
"status": "under_review",
"stylometric_score": 0.4888888888888889,
"timestamp": "2026-06-29T05:53:03.597Z"
},
{
"appeal_reason": null,
"appealed_at": null,
"attribution": "uncertain",
"confidence": 0.5686821705426357,
"content_id": "664c05af-b4b3-41af-ae1d-8eb8a61b9a0a",
"creator_id": "kaden1",
"id": 10,
"llm_score": 0.8,
"status": "classified",
"stylometric_score": 0.22170542635658916,
"timestamp": "2026-06-29T05:52:43.550Z"
},
{
"appeal_reason": null,
"appealed_at": null,
"attribution": "likely_human",
"confidence": 0.28888888888888886,
"content_id": "4f3a6708-6e33-4848-a921-83a0feaea03c",
"creator_id": "kaden1",
"id": 9,
"llm_score": 0.2,
"status": "classified",
"stylometric_score": 0.4222222222222222,
"timestamp": "2026-06-29T05:52:21.506Z"
},

---

## Known Limitations

**Formal human writing is the system's most likely misclassification.** Academic papers, legal briefs, and professional reports use long sentences, complex vocabulary, and low stylistic variance — the same surface features the stylometric signal treats as AI markers. A human-written literature review could score 0.6+ on the style signal, pulling the combined score into the uncertain or even `likely_ai` band despite being entirely human-written. The LLM signal partially compensates for this (it can detect natural academic voice), but it is not reliable enough to fully offset the stylometric false positive.

A secondary edge case is **human-edited AI output.** If a person substantially rewrites AI-generated text — fixing the rhythm, varying sentence length, removing hedging phrases — both signals can miss it. The LLM signal is the stronger backstop here, but it too can be fooled by thorough editing.

---

## Spec Reflection

As we created the spec ourselves, I would say the best part of spec writing was conversing with Claude about different types of implementations, which allowed for me to test my knowledge of system design well. I suppose that is how the spec helped me.

The most significant divergence from the original plan was the replacement of type-token ratio (TTR) with average top-word length per sentence as the vocabulary diversity metric in Signal 2. The planning document listed TTR as the diversity measure, but it became clear that TTR is length-dependent: longer texts naturally score lower TTR regardless of authorship, conflating document length with AI probability. Furthermore, some human texts will also reuse the same word (ie, "the"), so TTR may not be the best metric to use. The replacement metric (averaging the lengths of the three longest words per sentence across all sentences) seems to better capture vocabulary complexity without this bias, and is more directly tied to the known pattern of AI text using longer, more formal words.

---

## AI Usage

One thing that I asked the AI to do was to choose between the metrics listed for the detection and choose some important ones (IE TTR, Sentence Length, ETC). It proposed the TTR as a choice, but after digging deeper, I realized that TTR was an inheritenly flawed metic in my opinion, so I switched it out

Another thing that I changed from the AI was the auditing json file format. The ai when given the task created a lot of different fields and didn't correctly label the confidence field correctly, relying on just the LLM score. Thus, I had to redirect it to consider everything.

---

## Running the Tests

```powershell
python test.py
```

Runs all four test inputs through both signals and prints a comparison table of `llm_score`, `style_score`, `combined`, and attribution.
