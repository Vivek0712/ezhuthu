# Expert validation kit

This kit lets real epigraphists check Ezhuthu's restorations quickly and blind. Agents cannot stand in for
them.

| file | what it is |
|---|---|
| [PROTOCOL.md](PROTOCOL.md) | the study design. Study A: blind 1 to 4 plausibility rating of AI proposals for blank passages and masked restorations, with Fleiss' and Cohen's kappa. Study B: a with/without-AI reading study after Ithaca. It also covers consent, leakage rules, and how the app's Review queue connects to the protocol |
| [OUTREACH.md](OUTREACH.md) | invitation email in Tamil and English (a template; nothing is sent) |
| `pilot/` | a ready pilot packet built with seed 2026 (see below) |
| `src/ezhuthu/expert/` | `python -m ezhuthu.expert sample / propose / generate / synth / analyze` |
| `tests/expert/` | kappa checks against published worked examples, blinding checks, and analysis checks on synthetic ratings |

## Quick start

```bash
python -m ezhuthu.expert sample   --out kit/sample.jsonl
EZHUTHU_LIVE=1 python -m ezhuthu.expert propose --sample kit/sample.jsonl --out kit/proposals.jsonl --router sonnet
python -m ezhuthu.expert generate --sample kit/sample.jsonl --proposals kit/proposals.jsonl \
    --raters R1,R2,R3,R4 --out kit/packet --pdf
# ... experts fill kit/packet/raters/<code>/*.csv ...
python -m ezhuthu.expert analyze  --key kit/packet/coordinator/key.json --out results returned/
```

Without `EZHUTHU_LIVE=1`, use `propose --router none`. The proposals then come from train-only retrieval and
the character n-gram model, with no LLM. `generate --pdf` prints the HTML sheets with headless Chrome, which
shapes Tamil correctly. Without Chrome, print the HTML from any browser.

## Pilot packet (`pilot/`)

- `sample.jsonl` (+ `.meta.json`): seed 2026, the `sample` defaults. It holds 12 blank passages (test and val
  inscriptions), 12 masked test restorations and 12 reading-study passages (also masked test items, from
  inscriptions no rating passage uses), plus 2 spares each for blank and masked: 40 passages. 30% of the
  masked and reading passages come from the age set.
- `proposals.jsonl` (+ `.meta.json`): the production restorer run live on 2026-11-02 with
  `us.anthropic.claude-sonnet-4-6` (router `sonnet`, 2,048-token output budget). Ontology OFF, train-only
  retrieval, decider refused, so the ranking is the flagged fallback. The kit v1 sample took 40 Bedrock
  calls. Kit v2 made the reading passages inscription-disjoint from the rating passages, which replaced 5
  reading passages; only those 5 were proposed again (5 calls), and the 5 dropped passages' proposals were
  removed. In total: 45 calls, 0 errors, estimated USD 0.53 (both runs are in the meta file). The spares were
  not needed; they account for 4 of the calls.
- `packet/coordinator/key.json` (kit v2): 24 rating items (12 masked, 12 blank), 3 options each, AI options
  within +/-1 akshara of the gap preferred. AI options by source tag: sonnet 57, parallel 12, ngram 1; an
  option can carry several tags. Lengths: the edition fill matches the gap in 12 of 12 masked items; of the 24
  AI options on masked items 4 match exactly, 14 are 1 akshara off and 6 are further off (P03, P11, P17: the
  AI had no proposal of the right length); 9 of 12 masked items have every option within +/-1. In 5 masked
  items the edition fill was also among the AI proposals and is shown once (the analysis counts these as
  ties). Each rater's option labels are in `label_maps`. Also 12 reading items with the top 3 AI suggestions
  each.
- `packet/raters/R1/`: R1's sheets as an example (CSV and printable HTML). Regenerate any rater's sheets
  exactly with the `generate` command above, using `--out` and the same sample and proposals.
- `synthetic-dry-run.md`: the analysis run on **synthetic** ratings (raters `SYN-R1` to `SYN-R4`), to show the
  report's shape. It says nothing about restoration quality.

**Before a real round.** The pilot's key is in git, so anyone with repository access can unblind it. For a
round with real raters, generate a new packet with a fresh seed, keep it outside the repository
(`data/expert-validation/`, gitignored) and give each rater only their own folder.
