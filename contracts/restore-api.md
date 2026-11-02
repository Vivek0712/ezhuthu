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

## POST /api/read (upload + OCR; experimental for photos)
Turns what a learner has (a photo, a text file or a DHARMA EpiDoc file) into lines in the restorer's notation, so the
result can go straight to `/api/restore` and then `/api/lesson`. Send **exactly one** of `image_base64` or `text`.

Request (JSON):
```json
{"image_base64": "<base64 JPEG|PNG|WebP|HEIC>", "media_type": "image/jpeg", "router": "routed" | "sonnet" | "opus", "hint": "optional, <=200 chars"}
{"text": "<file contents>", "filename": "x.txt" | "x.xml", "format": "auto" | "txt" | "epidoc"}
```

Response:
```json
{
  "source": "image" | "text" | "epidoc", "experimental": true,
  "lines": [{"n": "1", "text": "svasti śrī kō[?4]kēcari", "text_tamil": "ஸ்வஸ்தி ஶ்ரீ கோ[?4]கேசரி", "confidence": 0.0 | null, "gaps": 1}],
  "text": "<lines joined by \n, ISO-15919>", "text_tamil": "...", "gaps": 1,
  "script_guess": {"script": "tamil-brahmi|vatteluttu|grantha|pallava-tamil|chola-tamil|modern-tamil|unknown",
                   "label_en": "...", "label_ta": "...", "era": "..." | null, "confidence": 0.0 | null, "level": "L1".."L5" | null} | null,
  "confidence": 0.0 | null, "kind"?: "inscription|printed|handwritten|other", "note"?: "...",
  "models_used": ["sonnet", "opus"], "model"?: "sonnet|opus", "escalated": false, "escalation_skipped"?: "time_budget" | "budget",
  "image"?: {"width", "height", "bytes", "format": "jpeg", "source_format", "source_bytes", "resized", "metadata_removed": ["exif", "gps", ...]},
  "title"?: "...", "licence"?: "...", "masked_supplied"?: 0,
  "warnings": ["..."], "trace_id": "...", "latency_ms": 0
}
```
- Gaps use the same markers as `/api/restore`: `[?N]` for about N lost letters, `[?]` for unknown length. Illegible
  stretches in a photo are gaps; the model is told never to guess hidden letters. EpiDoc `<supplied>` restorations are
  returned as `[?N]` gaps (`masked_supplied` counts them) so the learner can try restoring them; `<gap>` stays a gap.
- `confidence` is the model's own probability (not calibrated); `null` for text and EpiDoc uploads.
- Photo reading is **experimental**: the app labels it "experimental reading, check against the edition" in Tamil
  and English. Measured accuracy: `eval/reports/2026-11-02-ocr-eval.md`.
- Routing (`config/models.yaml` `reader`, `routing`): `routed` reads with `llm.default` (Sonnet 4.6) and re-reads with
  `llm.escalate` (Opus 4.6) when `confidence` < `routing.escalate_if_confidence_below`, only if the first read took
  less than `reader.escalate_if_elapsed_below_s`; otherwise `escalation_skipped: "time_budget"` and the app offers a
  second request with `router: "opus"`.
- Images: the server sniffs the bytes (JPEG, PNG, WebP; HEIC only with the optional `pillow-heif`), refuses more than
  5 MB decoded (413 `too_large`) or 40 MP, other formats (415 `unsupported_format`), auto-rotates, downscales to
  1568 px on the long side and re-encodes JPEG with **no metadata** (EXIF, GPS, XMP, ICC are dropped before the model,
  the cache or any log; `image.metadata_removed` lists what was found). The image is not stored.
- Transport: base64 inside the JSON body, no S3. The cloud proxy caps this route's body at 4.5 MB (Lambda's 6 MB
  synchronous payload limit applies to the whole event); the app resizes photos to at most 2048 px and about 1.5 MB
  first, so a request is typically 0.3 to 2 MB. The agent call must finish inside the proxy's 27 s.
- Errors: 413 `too_large`, 415 `unsupported_format`, 422 (`bad_image`, `bad_base64`, `bad_xml`, `not_epidoc`,
  `no_text`, `bad_request`), 503 `reader_unavailable` (no live model on the server; text and EpiDoc still work).
  Error bodies are `{"detail", "code"}` from the FastAPI app and `{"error": {"code", "message"}}` through the proxy.

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
  `{"correct": bool, "feedback_ta", "feedback_en", "next_action": "advance"|"repeat"|"hint", "decider_confidence": 0.0 | null, "decider_source"?, "hint_ta"?, "context_update"?}`
  - `decider_confidence` is `null` when the rules decided (`decider_source: "rules"`, or `"assessment"` for pre/post
    items); the app then says "decided by rules", never "confidence 0%".
  - `context_update` `{"explain_ta", "explain_en", "explained_by", "explanation_status": "done"}` appears at most once,
    when the lesson's `context.explanation_status` was `"pending"` and the tutor team's explanation has since finished
    (best effort: it may never arrive). The app replaces the lesson's `explain_ta`/`explain_en` with it.
- `/api/lesson` `context` also carries `explained_by` and `explanation_status`: `"pending"` | `"done"` | `"template"`.
- `POST /api/assessment` `{"session_id", "phase": "pre"|"post"}` returns 10 era-letter items; grading uses `/api/answer`.
- `GET /api/progress/{session_id}` returns `{"pre_score", "post_score", "gain", "letters_correct_by_level", "median_seconds_per_letter"}`

Glyphs: render era scripts with web fonts (Noto Sans Brahmi, Noto Sans Grantha, Noto Sans Tamil). Vatteluttu has no Unicode, so the app ships SVG glyphs for it, plus the ISO-15919 value.
