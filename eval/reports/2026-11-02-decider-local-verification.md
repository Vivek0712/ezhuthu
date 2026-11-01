# Local Strands Decider verification (2026-11-02)

What was run, on the 24 GB M4 Pro dev machine, and what happened. Inputs are the synthetic fixtures in
`src/ezhuthu/agent/fixtures/`; nothing here measures restoration quality.

## Setup

- `uv pip install --python .venv/bin/python "strands-decider[mps]==0.2.0"` in the agent worktree venv: installed
  cleanly (torch, transformers 5.22.1).
- `HF_HUB_OFFLINE=1 .venv/bin/strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --device mps --port 8765`
  (weights were already in the local Hugging Face cache, so no download).
- `GET /health`:
  `{"model": "strands-decider-2B-qwen3.5-v1-2610", "base_model": "Qwen/Qwen3.5-2B-Base", "num_slots": 24,
  "max_length": 4096, "device": "mps", "prefix_cache": true, "vision": false}`
- Server process RSS: about 250 MB (model weights live in unified GPU memory and are not counted in RSS).

## Client checks

- `tests/agent/test_fixtures_and_decider.py::test_real_decider_*` pass against this server (they skip when no
  server is reachable, so CI stays offline).
- A first raw `choice` call (3 options) took 1.2 s including warm-up; later restoration choices over up to
  9 options plus `none` took 0.51 s median, 0.63 s max (`restore_gap`, router `none`, 8 fixture items).
- A pedagogy `choice` (advance / repeat / hint) took 0.09 s.
- `num_slots` = 24, so the client sends at most 23 candidates plus the `none` option.

## Observations (fixture smoke only)

- On the 8 synthetic items with router `none` (no LLM), the decider filled 3 and abstained on 5 at the 0.5
  abstain threshold from `config/models.yaml`. The top candidate equalled the fixture target on 5 of 8.
  This is a smoke check of the plumbing on hand-written lines, **not** a benchmark number.
- Option format matters: in one probe, giving each option its evidence (`restored_line`,
  `parallel_lines_supporting`) moved probability toward the parallel-supported fill compared with bare strings
  (0.45 to 0.52 on that probe). The engine uses the evidence format. This is one probe, not a measurement.

## Not done in this wave

- `StrandsAgents/strands-decider-E4B-gemma4-v1-2610` (named for the final run) was not served or compared yet.
  It is in the local HF cache, so wave 2 can run it the same way.
