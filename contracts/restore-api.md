# Restore and evaluate API (shared by agent, app, eval)

Text uses **ISO-15919** internally; Tamil script is derived (Aksharamukha). Gap markers in input text:
`[?]` gap of unknown length, `[?N]` gap of about N **Tamil letters** (aksharas: one uyir, mey or uyirmey letter
each, so `[?3]` covers `kōvi` / கோவி; not ISO-15919 or Unicode characters). `gap_chars` in responses and records
is that same letter count (the field keeps its name).

> **Contract change (2026-11-02, issue #26 / deployed-config PR):** `[?N]` and `gap_chars` were documented as
> characters; the restorer, the benchmark (`gap_chars` from DHARMA's `<gap quantity unit="character">`, which counts
> letters) and the length checks have counted Tamil letters since issue #26. Clients that convert a damaged span to
> `[?N]` must count letters, not ISO characters (ISO spells most letters with 2-3 characters).

> **Additive response change (2026-11-02, deployed-config PR):** with the deployed restorer settings
> (`strategy_llm: prerank`, `ngram_prerank: true`), each candidate's `decider_model` is `"prerank-ngram"` (no decider
> ranks the candidates; before, it named the ranking decider or a fallback) and its untyped `features` object gains
> `ngram_probability`: the character 5-gram's share for that fill (0-1, 4 decimals), or `null` when the 5-gram options
> are off. `features` is not in the example below nor in `app/web/api/openapi.yaml`; clients may ignore it.

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

**Request budget and gap cap (additive, 2026-11-02, issue #41).** A request's gaps are restored one after another
(each uses the earlier chosen fills as context) inside the proxy's 27 s (API Gateway: 29 s). `config/models.yaml`
`restorer:` sets the bounds; the defaults are in brackets:

- `request_budget_s` [25]: the whole request. Every LLM call's timeout (retries and back-off included) is what is
  left of it.
- `escalate_min_remaining_s` [8]: Opus (pre-escalation for a long gap or a gap with no good parallel, or after an
  unsure Sonnet) starts only with this much left; otherwise the gap keeps Sonnet's answer and says
  `"escalation_skipped": "time_budget"`.
- `llm_min_remaining_s` [6]: with less left, the gap gets retrieval and 5-gram candidates only and says
  `"llm_skipped": "time_budget"`. An LLM call that fails under the budget keeps the other candidates and says
  `"llm_skipped"` (or `"escalation_skipped"`) `"time_budget"` if the time ran out, else `"error"`.
- `gap_min_remaining_s` [1]: with less left, the remaining gaps abstain with no work:
  `"decision": "abstain", "chosen": null, "candidates": [], "abstain_reason": "time_budget"`; their markers stay
  in `restored_text`.
- `max_gaps_per_request` [8]: gaps past this many abstain the same way with `"abstain_reason": "gap_cap"`. The API
  refuses more than `EZHUTHU_MAX_GAPS` (5) markers per request, so the cap bounds other callers (the tutor restores
  whole inscriptions).

The three gap fields are present only when set. Every response gains
`"budget": {"request_budget_s": 25, "max_gaps_per_request": 8, "limited": false, "abstained": {"time_budget": 0,
"gap_cap": 0}, "llm_skipped": 0, "escalation_skipped": 0}` (`limited`: any of those counts is non-zero). Until the
budget runs low, every gap is restored exactly as without it (same candidates, confidences and decisions).

## POST /api/read (upload + OCR; experimental for photos)
Turns what a learner has (a photo, a text file or a DHARMA EpiDoc file) into lines in the restorer's notation, so the
result can go straight to `/api/restore` and then `/api/lesson`. Send **exactly one** of `image_base64` or `text`.

Request (JSON):
```json
{"image_base64": "<base64 JPEG|PNG|WebP|HEIC>", "media_type": "image/jpeg", "filename"?: "IMG_1.jpg", "router": "routed" | "sonnet" | "opus", "reread_token"?: "<from an earlier response>", "hint": "optional, <=200 chars"}
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
  "models_used": ["sonnet", "opus"], "model"?: "sonnet|opus", "escalated": false,
  "escalation_skipped"?: "time_budget" | "budget" | "error", "reread_token"?: "<32 hex, only with time_budget>",
  "image"?: {"width", "height", "bytes", "format": "jpeg", "source_format", "source_bytes", "resized", "metadata_removed": ["exif", "gps", ...]},
  "title"?: "...", "licence"?: "CC BY-SA 4.0", "licence_url"?: "https://...", "masked_supplied"?: 0,
  "inscription_id"?: "DHARMA_INS..." | null, "source_url"?: "https://dharmalekha.info/texts/DHARMA_INS..." | null,
  "warnings": ["<English message>"], "warning_codes": [{"code": "cut_short|dropped_chars|no_text_in_image|low_reliability_script|unsure|lines_capped|masked_supplied", "params": {}}],
  "trace_id": "...", "latency_ms": 0
}
```
- Gaps use the same markers as `/api/restore`: `[?N]` for about N lost letters, `[?]` for unknown length. Illegible
  stretches in a photo are gaps; the model is told never to guess hidden letters. EpiDoc `<supplied>` restorations are
  returned as `[?N]` gaps (`masked_supplied` counts them) so the learner can try restoring them; `<gap>` stays a gap.
- `confidence` is the model's own probability (not calibrated); `null` for text and EpiDoc uploads.
- Photo reading is **experimental**: the app labels it "experimental reading, check against the edition" in Tamil
  and English. Measured accuracy: `eval/reports/2026-11-02-ocr-eval.md`.
- `warnings[i]` and `warning_codes[i]` are the same warning: the app shows `warning_codes` in the learner's language
  (`params`: `chars` for `dropped_chars`, `script` for `low_reliability_script`, `max` for `lines_capped`, `n` for
  `masked_supplied`) and falls back to the English message.
- Routing (`config/models.yaml` `reader`, `routing`): `routed` reads with `llm.default` (Sonnet 4.6) and re-reads with
  `llm.escalate` (Opus 4.6) when `confidence` < `routing.escalate_if_confidence_below`, only while at least
  `reader.escalate_min_remaining_s` (15 s) of the request budget `reader.request_budget_s` (25 s) is left. Every model
  call, its retries and their back-off stay inside that budget. Of the two readings the more confident one is kept
  (a tie keeps the first); `model` names it. If the escalation fails (throttled, timed out, any Bedrock error) the
  first reading is returned with `escalation_skipped: "error"`; `"budget"` means the server's live-call budget is
  spent.
- **Opus on request is not public.** When escalation is skipped for time (`"time_budget"`) the response carries a
  one-time `reread_token`, bound to a hash of that photo's bytes and valid for `reader.reread_token_ttl_s` (15 min).
  `router: "opus"` is accepted only with such a token for the same photo, and only once; otherwise **403**
  `reread_token_invalid`. `router: "sonnet"` is open. (Tokens live in the service store, DynamoDB `READTOKEN#<id>`.)
- Images: the server sniffs the bytes (JPEG, PNG, WebP; HEIC only with the optional `pillow-heif`), refuses more than
  5 MB decoded (413 `too_large`) or 40 MP, other formats (415 `unsupported_format`), auto-rotates, downscales to
  1568 px on the long side and re-encodes JPEG with **no metadata** (EXIF, GPS, XMP, ICC are dropped before the model,
  the cache or any log; `image.metadata_removed` lists what was found). The image is not stored.
- Transport: base64 inside the JSON body, no S3. The cloud proxy caps this route's body at 4.5 MB (Lambda's 6 MB
  synchronous payload limit applies to the whole event), so **the effective limit in the cloud is about 3.3 MB of
  image** (the agent's own 5 MB limit only applies when it is called directly). The app resizes photos to at most
  2048 px and about 1.5 MB, and refuses anything still over 3.3 MB, so a request is typically 0.3 to 2 MB. The agent
  call must finish inside the proxy's 27 s.
- Images with transparency are composited on white before re-encoding (black text on a transparent PNG stays
  readable). EpiDoc uploads also return the edition's `inscription_id` (`<idno type="filename">`), its dharmalekha
  `source_url` and `licence`/`licence_url`, which the app shows with the reading.
- Errors: 403 `reread_token_invalid`, 413 `too_large` (also an image over Pillow's decompression-bomb limit), 415
  `unsupported_format`, 422 (`bad_image`, `bad_base64`, `bad_xml`, `not_epidoc`, `no_text`, `bad_request`), 503
  `reader_unavailable` (no live model on the server; text and EpiDoc still work).
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
