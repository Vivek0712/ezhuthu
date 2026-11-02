> **TEST split, scored once** (issue #26). Every strategy, threshold and calibration was chosen on VAL first
> ([`2026-11-02-val-selection.md`](2026-11-02-val-selection.md)); nothing below was tuned on these items. "Matches the
> expert restoration" means the fill equals the DHARMA editor's supplied text after ISO normalisation; it does not
> mean "correct". Gap lengths are counted in Tamil letters throughout (the issue #26 fix); every earlier TEST number
> in `eval/reports/` is superseded by this report.
>
> **Re-scored once more after QA on PR #31** (same settings, same items, 0 Bedrock calls): the character 5-gram's fills
> had depended on `PYTHONHASHSEED`. With the fix every VAL and TEST row was replayed from the reply cache; the 5-gram
> baseline moved from 0.5714 to 0.5666, every VAL choice stayed the same, and of the other configurations only the
> retrieval-only `choice-all` decider row changed (2 gaps; details below). Latencies in this run are higher because
> the local decider was slower under load.
> **What was measured** is the local `strands-decider-2B` with VAL calibration. The deployed cloud runtime (hosted v19
> decider, or the self-report fallback without a decider) is not measured: it has no calibration entry, so it fills or
> abstains at the raw 0.5 threshold, and the 0.6 escalation threshold was chosen on the 2B decider's scale.

## Headline

- **The measured pipeline** (VAL-chosen config: routed Sonnet 4.6 -> Opus 4.6, local 2B decider `noul-topk:3`,
  ontology on): top-1 matches
  the expert on **205 of 413** test gaps (**0.4964**, 95% CI 0.4479-0.5448). The copy-from-best-parallel baseline
  scores 0.4722; the difference is not significant (38 vs 28 discordant gaps, p = 0.27).
- **The character 5-gram baseline is the best restorer on TEST**: 0.5666 (0.5182-0.6150), above copy (84 vs 45,
  p = 0.0008) and above the measured pipeline (77 vs 48 discordant gaps, p = 0.012). 68% of TEST gaps are a single
  letter (VAL: 46%), where the 5-gram is strongest (0.6797); on gaps of 4+ letters (n = 51) every system is at
  0.10-0.33.
- **Abstention:** at its VAL-fitted thresholds the measured pipeline fills 46.5% of gaps and 63.5% of those fills
  match the expert (122 of 192); ECE 0.113.
- **Opus helps, Sonnet alone does not:** routed beats Sonnet-only (0.4165 -> 0.4964; 43 vs 10, p < 0.0001); Sonnet
  alone is below copy (p = 0.006). Opus 4.6 alone on a seeded 100-gap sample: 0.50 (routed on the same 100: 0.49).
- **The 2B decider does not beat prerank for restoration ranking on TEST:** on the same LLM candidates, decider vs
  prerank is 27 vs 28 discordant gaps for Sonnet (p = 1.0) and 25 vs 29 for routed (p = 0.68); on retrieval-only
  candidates the best VAL decider variant (`choice-all`) is below prerank (46 vs 71, p = 0.026). The hosted v19
  decider (decider-cloud) was **not part of this evaluation**; its only restoration numbers are the 60-gap
  [decider benchmark](2026-11-02-decider-benchmark.md), measured before the letter-count fix.
- **Ontology ablation:** no measurable effect. 88 of 413 gaps get an ontology hint; with it on vs off, Sonnet's top-1
  matches on 3 gaps only with it and 3 only without (p = 1.0).
- **Cost and latency (measured routed pipeline):** 122 Sonnet + 300 Opus calls for 413 gaps, about $2.50 at list
  prices ($0.006 per gap); 299 of 413 gaps use Opus (291 by pre-escalation). Latency p50 10.4 s per gap, p90 15.5 s
  in the re-score (first pass: 8.2 s / 12.2 s; the LLM part is the original calls' latency, the rest is the local
  decider, which was slower under this run's load).

## How this run went (read before re-using the rows)

- Live Bedrock calls for the whole issue: 1,080 (626 Sonnet, 454 Opus; 1,075 distinct cached replies, VAL 240, TEST
  835), within the 1,200 budget. The split by process, with the ledger behind each number, is in "Live Bedrock calls
  by ledger" at the end. Account quotas are Sonnet 4.6 10 and Opus 4.6 5 requests a minute; the TEST run warmed the
  reply cache per model in parallel lanes (a cached reply is byte-identical to a live one for the restorer). The
  Sonnet warm-up was a separate process pacing at the full quota while the scored run's Sonnet lane did the same,
  so Sonnet ran above its quota; that, not the per-process pacing, caused the throttling below.
- A first TEST attempt was stopped after its retrieval-only rows (a lane made no progress); it was restarted from the
  same commit. Retrieval-only rows are deterministic and came out identical; its 31 Sonnet and 1 Opus replies were
  replayed.
- Throttling lost 7 of 413 Sonnet gaps and 2 of 88 ablation gaps in the first pass (8 retries each). They were
  replayed from the cache with no setting changed (`repair`, 0 live calls): the other 406 Sonnet rows were unchanged,
  1 of the other 86 ablation rows changed its top-1 (the local decider is not bit-exact between runs; the same
  happened on VAL, e.g. `choice-topk:3` 0.2370 vs 0.2393 on two full-VAL runs). The first-pass rows' meta (commit
  `64edf1c`) records the lost ids.
- The two "prerank instead of the decider" rows were added after the main pass to answer the decider question
  above (8 more live Opus calls). They change no configured setting.
- **Determinism re-score (QA on PR #31).** `CharNgram.fill` broke log-prob ties in set-iteration order, so its fills
  depended on `PYTHONHASHSEED`: 30 of the 856 VAL+TEST gaps got different restorer 5-gram proposals, and 143 different
  5-gram baseline fills, from one process to the next. After the fix (sorted alphabet, ties broken on the string)
  every row was replayed from the cache with no setting re-chosen and 0 Bedrock calls: the full-VAL retrieval report,
  the VAL runs and `decide` (identical choices; the four decider retrieval calibration entries moved slightly, e.g.
  `choice-all` threshold 0.4143 -> 0.4121), then TEST. On TEST the 5-gram baseline changed on 3 gaps (236 -> 234
  matches); `choice-all` on retrieval candidates changed on 2 gaps (175 -> 176) and its calibrated confidences moved
  with the refitted entry; every other configuration has the same top-1 and fill/abstain on every gap. The first
  pass's rows are in git history (commit `64edf1c`).
- Not run: the E4B decider (70 s per gap p50 locally in the decider benchmark; the 2B at ~1 s per `noul` was
  already this run's bottleneck) and the hosted v19 decider (see above).
