"""Build the public results page's numbers (app/web/src/benchmark/summary.json) from the committed reports.

Every number on /benchmark comes from this file, and every number in this file is read from a machine-readable
report output (never typed by hand):

- eval/reports/2026-11-02-deployed-config.json      the deployed configuration on TEST (scored once), PR #31 rows
- eval/reports/2026-11-02-deployed-config/decisions.json   the VAL choice, incl. the hosted v19 decider run
- eval/reports/2026-11-02-deployed-config/rows/test-deployed.jsonl   per-gap rows (the reliability bins)
- eval/reports/2026-11-02-test-eval.json             Sonnet alone and the hard-subset rows of the baselines
- eval/reports/2026-11-02-decider-benchmark.json     Sparrow Decider and tutor-policy numbers
- eval/reports/2026-11-02-ocr-eval.json              the photo reader's character error rates
- benchmark/stats.json                               split counts

The superseded 2026-11-01 baseline reports (baseline-*-test-full) are not used: they counted gap lengths in ISO
characters; their current numbers are the PR #31 rows of the TEST evaluation.

tests/test_benchmark_summary.py checks the committed JSON against a fresh build and against the Markdown reports.

Run: .venv/bin/python scripts/build_benchmark_summary.py          (add --check to verify the committed file)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORTS = REPO / "eval" / "reports"
OUT = REPO / "app" / "web" / "src" / "benchmark" / "summary.json"
GITHUB = "https://github.com/Vivek0712/ezhuthu/blob/main/"

SRC = {
    "deployed": "eval/reports/2026-11-02-deployed-config.md",
    "preregistration": "eval/reports/2026-11-02-deployed-config/preregistration.md",
    "test": "eval/reports/2026-11-02-test-eval.md",
    "val": "eval/reports/2026-11-02-val-selection.md",
    "decider": "eval/reports/2026-11-02-decider-benchmark.md",
    "ocr": "eval/reports/2026-11-02-ocr-eval.md",
    "data_card": "benchmark/DATA_CARD.md",
    "stats": "benchmark/stats.json",
}


def _load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def p_text(p: float) -> str:
    """The reports' p-value style: '<0.0001' below 1e-4, else 4 decimals (0.00017 -> '0.0002')."""
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def matches(top1: float, n: int) -> int:
    k = round(top1 * n)
    assert abs(k / n - top1) < 5e-5, (top1, n)
    return k


def _vs(pair: dict) -> dict:
    return {"only_deployed": pair["only_a"], "only_other": pair["only_b"], "p": pair["p_mcnemar"],
            "p_text": p_text(pair["p_mcnemar"])}


def _row(rid: str, s: dict, vs: dict | None, source: str) -> dict:
    return {"id": rid, "n": s["n"], "top1": s["top1"], "ci": s.get("top1_ci"), "matches": matches(s["top1"], s["n"]),
            "vs_deployed": _vs(vs) if vs else None, "source": source}


def leaderboard(dep: dict, test: dict) -> dict:
    out = {}
    # PR #31 rows: the deployed report carries the full-split rows (test31); the hard-subset rows are in test-eval.
    pr31 = {"ngram": "ngram", "routed2b": "routed", "copy": "copy"}
    for subset in ("full", "hard"):
        rows = [_row("deployed", dep["by_subset"][subset], None, SRC["deployed"])]
        for rid, key in pr31.items():
            s = dep["test31"][key] if subset == "full" else test["configs"][key]["by_subset"][subset]
            if subset == "hard":  # the same PR #31 run: its full row must equal the deployed report's copy
                assert test["configs"][key]["by_subset"]["full"]["top1"] == dep["test31"][key]["top1"], key
            rows.append(_row(rid, s, dep["vs"][key][subset], SRC["deployed"] if subset == "full" else SRC["test"]))
        # Sonnet alone: in the TEST evaluation; no paired test against the deployed system was run.
        rows.append(_row("sonnet", test["configs"]["sonnet"]["by_subset"][subset], None, SRC["test"]))
        rows.sort(key=lambda r: -r["top1"])
        out[subset] = {"n": rows[0]["n"], "rows": rows}
    return out


def abstention(dep: dict) -> dict:
    from ezhuthu.eval.metrics import ece, reliability

    rows_path = REPORTS / "2026-11-02-deployed-config" / "rows" / "test-deployed.jsonl"
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if "_meta" not in r]
    conf = [r["confidence"] for r in rows]
    ok = [bool(r["top1_correct"]) for r in rows]
    full = dep["by_subset"]["full"]
    # The bins are recomputed from the rows with the same function the report used; they must give its ECE and fills.
    assert len(rows) == full["n"] and round(ece(conf, ok), 4) == full["ece"]
    filled = [r for r in rows if not r["abstained"]]
    assert len(filled) == full["filled"] and sum(r["top1_correct"] for r in filled) == full["filled_matching"]
    assert sum(ok) == matches(full["top1"], full["n"])
    bins = [{"lo": b["bin"][0], "hi": b["bin"][1], "n": b["n"], "accuracy": b["accuracy"], "confidence": b["confidence"]}
            for b in reliability(conf, ok)]
    return {"n": full["n"], "coverage": full["coverage"], "coverage_ci": full["coverage_ci"],
            "selective_accuracy": full["selective_accuracy"], "filled": full["filled"],
            "filled_matching": full["filled_matching"], "ece": full["ece"], "reliability": bins,
            "source": SRC["deployed"], "rows": "eval/reports/2026-11-02-deployed-config/rows/test-deployed.jsonl"}


def gap_length(dep: dict, test: dict) -> dict:
    names = {"deployed": "deployed", "ngram": "ngram", "routed2b": "routed", "copy": "copy"}
    bins = []
    for label in dep["by_gap_length"]["deployed"]:
        b = {"key": label, "n": dep["by_gap_length"]["deployed"][label]["n"]}
        for rid, key in names.items():
            b[rid] = dep["by_gap_length"][key][label]["top1"]
        # 95% intervals exist for the PR #31 rows only (test-eval); the deployed report gives point values.
        b["ngram_ci"] = test["by_gap_length"]["ngram"][label]["top1_ci"]
        bins.append(b)
    return {"bins": bins, "source": SRC["deployed"]}


def ocr(o: dict) -> dict:
    s = o["synthetic"]
    lv = s["by_level"]
    return {
        "tamil_synthetic": {k: {"n": lv[k]["n"], "cer": lv[k]["cer"]} for k in ("clean", "photo", "weathered")},
        "tamil_synthetic_all": {"n": s["all_tamil_vs_edition"]["n"], "cer": s["all_tamil_vs_edition"]["cer"]},
        "printed_pages": {"n": 3, "cer": o["real"]["printed_mean_cer"]},
        "brahmi_real": {"n": sum(1 for i in o["real"]["images"] if i["script"] == "tamil-brahmi"),
                        "cer": o["real"]["inscriptions_mean_cer"]},
        "brahmi_synthetic": {"n": s["by_script_photo_level"]["tamil-brahmi"]["n"],
                             "cer": s["by_script_photo_level"]["tamil-brahmi"]["cer"]},
        "grantha_synthetic": {"n": s["by_script_photo_level"]["grantha"]["n"],
                              "cer": s["by_script_photo_level"]["grantha"]["cer"]},
        "source": SRC["ocr"],
    }


def decider(dec: dict, bench: dict) -> dict:
    s2 = dec["stage2"]
    hv = dec["variants"]["routed-hosted-v19"]
    notes = " ".join(bench["meta"]["notes"])
    first = float(re.search(r"always pick candidate 1 = ([0-9]+\.[0-9]+)", notes).group(1))
    rnd = float(re.search(r"uniform random pick among the top 3 = ([0-9]+\.[0-9]+)", notes).group(1))
    sparrow = {k: v["top1"] for k, v in bench["restoration"].items() if k.startswith("sparrow-")}
    pol = bench["policy"]
    return {
        "hosted": {"n": s2["n"], "hosted_matching": s2["hosted_matching"], "chosen_matching": s2["stage1_winner_matching"],
                   "only_hosted": s2["paired"]["only_a"], "only_chosen": s2["paired"]["only_b"],
                   "p": s2["paired"]["p_mcnemar"], "p_text": f"{s2['paired']['p_mcnemar']:.2f}",
                   "over_limit": hv["latency"]["over_proxy_limit"], "limit_s": 27,
                   "p90_s": round(hv["latency"]["p90_ms"] / 1000, 1), "source": SRC["deployed"]},
        "sparrow": {"n": bench["restoration"]["sparrow-nano"]["n"], "best_top1": max(sparrow.values()),
                    "random_top3": rnd, "first_candidate": first,
                    "nano_policy_raw": pol["sparrow-nano"]["raw_agree_with_rules"],
                    "nano_policy_final": pol["sparrow-nano"]["final_agree_with_rules"],
                    "policy_n": pol["sparrow-nano"]["n"], "source": SRC["decider"]},
    }


def method(stats: dict, dec: dict) -> dict:
    ps = stats["per_split"]
    return {"splits": {k: {"inscriptions": ps[k]["inscriptions"], "items": ps[k]["items"]} for k in ("train", "val", "test")},
            "test_hard": ps["test"]["hard"], "val_selection_n": dec["n_selection"], "val_hosted_n": dec["n_hosted"],
            "bootstrap_resamples": 2000, "licence": "CC BY-SA 4.0"}


def build() -> dict:
    dep = _load("eval/reports/2026-11-02-deployed-config.json")
    test = _load("eval/reports/2026-11-02-test-eval.json")
    dec = _load("eval/reports/2026-11-02-deployed-config/decisions.json")
    bench = _load("eval/reports/2026-11-02-decider-benchmark.json")
    o = _load("eval/reports/2026-11-02-ocr-eval.json")
    stats = _load("benchmark/stats.json")
    lb = leaderboard(dep, test)
    return {
        "_about": "Generated by scripts/build_benchmark_summary.py from the committed reports. Do not edit by hand.",
        "github": GITHUB,
        "sources": SRC,
        "leaderboard": lb,
        "abstention": abstention(dep),
        "gap_length": gap_length(dep, test),
        "ocr": ocr(o),
        "decider": decider(dec, bench),
        "method": method(stats, dec),
    }


def render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if the committed JSON differs from a fresh build")
    a = ap.parse_args(argv)
    text = render(build())
    if a.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(REPO)} is stale: run scripts/build_benchmark_summary.py", file=sys.stderr)
            return 1
        print("up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
