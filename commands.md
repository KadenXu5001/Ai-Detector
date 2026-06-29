# Provenance Guard — curl Commands

## POST /submit

Analyze text and get an attribution result.

```powershell
curl.exe -s -X POST http://localhost:5000/submit `
  -H "Content-Type: application/json" `
  --data-binary "@body.json"
```

Or inline:

```powershell
curl.exe -s -X POST http://localhost:5000/submit `
  -H "Content-Type: application/json" `
  --data-raw "{\"text\": \"your text here\", \"creator_id\": \"test-user-1\"}"
```

**Request body (`body.json`):**
```json
{
  "text": "your text here",
  "creator_id": "test-user-1"
}
```

**Response:**
```json
{
  "attribution": "likely_ai",
  "confidence": 0.69,
  "content_id": "3ff577df-4031-4023-93f8-d8386762b2ba",
  "label": "This text is likely heavily AI generated, with a 69% confidence of AI generation.",
  "llm_score": 0.8,
  "style_score": 0.526
}
```

`confidence` is the combined score: 60% `llm_score` + 40% `style_score`.

---

## GET /log

Return all audit log entries, newest first.

```powershell
curl.exe -s http://localhost:5000/log
```

Pretty-printed:

```powershell
curl.exe -s http://localhost:5000/log | python -m json.tool
```

**Response:**
```json
{
  "entries": [
    {
      "content_id": "3ff577df-...",
      "creator_id": "test-user-1",
      "timestamp": "2026-06-29T03:56:04.471Z",
      "attribution": "likely_ai",
      "confidence": 0.69,
      "llm_score": 0.8,
      "stylometric_score": 0.526,
      "status": "classified",
      "appeal_reason": null,
      "appealed_at": null
    }
  ]
}
```

---

## POST /appeal

Flag a submission for human review. Use the `content_id` from a `/submit` response.

```powershell
curl.exe -s -X POST http://localhost:5000/appeal `
  -H "Content-Type: application/json" `
  --data-raw "{\"content_id\": \"<content_id here>\", \"creator_reasoning\": \"I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.\"}"
```

Verify the appeal appears in the log:

```powershell
curl.exe -s http://localhost:5000/log
```

The matching entry should show `"status": "under_review"` and `"appeal_reason"` populated.

**Response:**
```json
{
  "content_id": "3ff577df-...",
  "message": "Your appeal has been recorded and will be reviewed.",
  "status": "under_review"
}
```
