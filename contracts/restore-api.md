# Restore and evaluate API (shared by agent, app, eval)

Text uses **ISO-15919** internally; Tamil script is derived (Aksharamukha). Gap markers in input text:
`[?]` gap of unknown length, `[?N]` gap of about N characters.

## POST /api/restore
Request: `{"text": "...[?6]...", "script": "iso15919" | "tamil", "max_candidates": 5, "allow_escalation": true}`

Response:
```json
{
  "restored_text": "...", "restored_text_tamil": "...",
  "gaps": [{
    "index": 0, "gap_chars": 6, "decision": "fill" | "abstain",
    "chosen": 0,
    "candidates": [{
      "text": "...", "text_tamil": "...", "confidence": 0.0,
      "model": "sonnet|opus|retrieval", "decider_model": "...",
      "parallels": [{"inscription_id": "...", "line_n": "...", "snippet": "...", "url": "..."}],
      "ontology_hints": [{"id": "...", "kind": "ruler|title|place|grant|measure|formula", "label": "..."}]
    }]
  }],
  "models_used": ["..."], "trace_id": "...", "latency_ms": 0
}
```

## POST /api/evaluate
Request: JSONL of `benchmark-item` records (upload) or `{"benchmark": "test-hard", "limit": 200, "router": "sonnet|opus|routed"}`.
Response: `{"n": 0, "top1": 0.0, "top20": 0.0, "cer": 0.0, "ece": 0.0, "coverage": [{"threshold": 0.9, "coverage": 0.0, "accuracy": 0.0}], "by_router": {...}, "items": [...]}`

## Corrections and review queue
`POST /api/corrections` `{gap_ref, accepted_candidate | corrected_text, user}` ; `GET /api/queue` ; `POST /api/queue/{id}` `{action: approve|edit|reject, text?}`.
Queue ids are `q-<uuid4>` (Python service and cloud proxy alike). An item is reviewed once: reviewing an item that is not
`pending` returns 409. Approve and edit set `final_text` (approve keeps the proposer's reading).

## Tutor (Education track)
Levels: `L1` modern Tamil, `L2` Chola Tamil, `L3` Pallava Tamil, `L4` Vatteluttu, `L5` Tamil-Brahmi.

- `POST /api/lesson` `{"inscription_id"?: "...", "text"?: "...", "level": "L1".."L5", "lang": "ta"|"en"}` returns
  `{"session_id", "inscription": {"id", "title", "dynasty", "approx_date", "source_url", "restored_text", "restored_text_tamil"},
    "items": [{"item_id", "type": "letter"|"word"|"line", "prompt_ta", "prompt_en", "glyph_svg"|"glyph_text", "script_level", "answer_hidden": true}],
    "context": {"ruler"?, "temple"?, "grant"?, "explain_ta", "explain_en"}}`
- `POST /api/answer` `{"session_id", "item_id", "answer"}` returns
  `{"correct": bool, "feedback_ta", "feedback_en", "next_action": "advance"|"repeat"|"hint", "decider_confidence": 0.0, "hint_ta"?}`
- `POST /api/assessment` `{"session_id", "phase": "pre"|"post"}` returns 10 era-letter items; grading uses `/api/answer`.
- `GET /api/progress/{session_id}` returns `{"pre_score", "post_score", "gain", "letters_correct_by_level", "median_seconds_per_letter"}`

Glyphs: render era scripts with web fonts (Noto Sans Brahmi, Noto Sans Grantha, Noto Sans Tamil). Vatteluttu has no Unicode, so the app ships SVG glyphs for it, plus the ISO-15919 value.
