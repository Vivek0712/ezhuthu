"""TEST row-level metrics for decider score files (http_score.py / hosted_val.py output). Nothing is fitted here.

Every decider's probabilities are used as served (the fine-tuned model's temperatures were fitted on VAL). Metrics
are those of val_metrics.py at the served temperature: choice3 top-1 (the highest-probability FILL among c0..c2,
'none' is never the pick, decider_bench semantics), top-1 when the target is among c0..c2, 4-way accuracy and NLL,
ECE of the top fill's probability, coverage / accuracy at the restorer's raw 0.5 threshold; noul AUC / ECE / Brier
/ NLL and the top-1 of ranking the three by P(yes). Paired: exact McNemar on top-1 and a bootstrap 95 % interval of
the difference (resampling items, seed 0, 2,000 draws).

References from the rows themselves (identical requests): first candidate (c0) and Sonnet self-confidence (the
highest Sonnet self-reported probability among c0..c2, as in val_metrics.py).

    python3 heldout_metrics.py --choice-data test.choice3.jsonl --noul-data test.noul.jsonl \\
        --json-out out.json ft2b=ft2b.test.jsonl base2b=base2b.test.jsonl hosted_v19=hosted.test.choice3.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random

from val_metrics import auc, ece, read  # same helpers as the VAL numbers


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def choice_ok(scores: list[dict], data: dict[str, dict]) -> dict[str, dict]:
    out = {}
    for s in scores:
        if s.get("shape") != "choice3" or s["id"] not in data or "probs" not in s:
            continue
        m = data[s["id"]]
        keys = m["option_keys"]
        p = [float(s["probs"].get(k, 0.0)) for k in keys]
        best = max(range(len(keys) - 1), key=lambda i: p[i])
        y = keys.index(m["label"])
        out[s["id"]] = {"ok": keys[best] == m["label"], "conf": p[best], "acc4": max(range(len(keys)),
                        key=lambda i: p[i]) == y, "nll4": -math.log(max(p[y], 1e-12)),
                        "oracle": m["label"] != "none", "hard": bool(m.get("hard"))}
    return out


def reference_ok(data: dict[str, dict]) -> dict[str, dict[str, dict]]:
    c0, sc = {}, {}
    for i, m in data.items():
        c0[i] = {"ok": m["label"] == "c0", "oracle": m["label"] != "none", "hard": bool(m.get("hard"))}
        s = [(-1 if v is None else v) for v in (m.get("self_report") or [])[:3]]
        b = max(range(len(s)), key=lambda j: s[j]) if s else None
        sc[i] = {"ok": b is not None and m["option_keys"][b] == m["label"], "conf": max(0.0, s[b]) if s else 0.0,
                 "oracle": m["label"] != "none", "hard": bool(m.get("hard"))}
    return {"first_candidate_c0": c0, "sonnet_self_confidence": sc}


def summarize(rows: dict[str, dict], ids: list[str]) -> dict:
    xs = [rows[i] for i in ids]
    n = len(xs)
    out = {"n": n, "top1": round(sum(x["ok"] for x in xs) / n, 4), "matches": sum(x["ok"] for x in xs)}
    orc = [x for x in xs if x["oracle"]]
    out["top1_when_target_in_top3"] = round(sum(x["ok"] for x in orc) / max(1, len(orc)), 4)
    if all("conf" in x for x in xs):
        conf, ok = [x["conf"] for x in xs], [x["ok"] for x in xs]
        out["ece_top_fill"] = round(ece(conf, ok), 4)
        fill = [x for x in xs if x["conf"] >= 0.5]
        out["coverage_at_0.5"] = round(len(fill) / n, 4)
        out["accuracy_at_0.5"] = round(sum(x["ok"] for x in fill) / len(fill), 4) if fill else None
    if all("acc4" in x for x in xs):
        out["acc4"] = round(sum(x["acc4"] for x in xs) / n, 4)
        out["nll4"] = round(sum(x["nll4"] for x in xs) / n, 4)
    return out


def paired(a: dict[str, dict], b: dict[str, dict], ids: list[str], B: int = 2000, seed: int = 0) -> dict:
    oa = [a[i]["ok"] for i in ids]
    ob = [b[i]["ok"] for i in ids]
    only_a = sum(1 for x, y in zip(oa, ob) if x and not y)
    only_b = sum(1 for x, y in zip(oa, ob) if y and not x)
    d = [int(x) - int(y) for x, y in zip(oa, ob)]
    rng = random.Random(seed)
    n = len(d)
    boots = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(B))
    return {"delta": round(sum(d) / n, 4), "ci95": [round(boots[int(0.025 * B)], 4), round(boots[int(0.975 * B) - 1], 4)],
            "only_a": only_a, "only_b": only_b, "p_mcnemar": round(mcnemar(only_a, only_b), 8)}


def noul_metrics(scores: list[dict], data: dict[str, dict]) -> dict | None:
    xs = [(float(s["p_true"]), bool(data[s["id"]]["label"] in (True, "yes", "true", 1)))
          for s in scores if s.get("shape") == "noul" and s["id"] in data and "p_true" in s]
    if not xs:
        return None
    p, y = [a for a, _ in xs], [b for _, b in xs]
    return {"n": len(xs), "yes_rate": round(sum(y) / len(y), 4), "auc": round(auc(p, y), 4),
            "ece": round(ece(p, [float(v) for v in y]), 4),
            "brier": round(sum((a - b) ** 2 for a, b in zip(p, y)) / len(p), 4),
            "nll": round(-sum(math.log(max(a if b else 1 - a, 1e-12)) for a, b in zip(p, y)) / len(p), 4)}


def noul_top1(scores: list[dict], noul: dict[str, dict], choice: dict[str, dict]) -> dict | None:
    by_item: dict[str, list[tuple[int, float, bool]]] = {}
    for s in scores:
        if s.get("shape") != "noul" or s["id"] not in noul or "p_true" not in s:
            continue
        m = noul[s["id"]]
        by_item.setdefault(m["item_id"], []).append((m.get("option_index", 0), float(s["p_true"]),
                                                     m["label"] in (True, "yes", "true", 1)))
    if not by_item:
        return None
    ok = [max(v, key=lambda t: t[1])[2] for v in by_item.values()]
    return {"items": len(ok), "top1": round(sum(ok) / len(ok), 4)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--choice-data", required=True)
    ap.add_argument("--noul-data", default=None)
    ap.add_argument("--json-out", default="")
    ap.add_argument("--primary", default="ft2b")
    ap.add_argument("scores", nargs="+", help="name=path")
    a = ap.parse_args()
    # A score file may hold several data files (http_score.py writes test and test-bench60 rows, which share
    # ids): keep only the rows scored from these data files.
    names = {os.path.basename(a.choice_data), os.path.basename(a.noul_data or "")}
    cdata = {r["id"]: r for r in read(a.choice_data)}
    ndata = {r["id"]: r for r in read(a.noul_data)} if a.noul_data else {}
    rows = reference_ok(cdata)
    files = {}
    for spec in a.scores:
        name, path = spec.split("=", 1)
        files[name] = [r for r in read(path) if r.get("file") in names]
        rows[name] = choice_ok(files[name], cdata)
    ids = sorted(cdata)
    missing = {k: len(set(ids) - set(v)) for k, v in rows.items()}
    full = [i for i in ids if all(i in v for v in rows.values())]
    hard = [i for i in full if cdata[i].get("hard")]
    res = {"n_rows": len(ids), "n_scored_by_all": len(full), "missing": missing, "choice3": {}, "choice3_hard": {},
           "paired": {}, "paired_hard": {}, "noul": {}}
    for k, v in rows.items():
        res["choice3"][k] = summarize(v, full)
        res["choice3_hard"][k] = summarize(v, hard) if hard else None
        if k != a.primary and a.primary in rows:
            res["paired"][f"{a.primary} - {k}"] = paired(rows[a.primary], v, full)
            if hard:
                res["paired_hard"][f"{a.primary} - {k}"] = paired(rows[a.primary], v, hard)
    res["target_in_top3"] = round(sum(cdata[i]["label"] != "none" for i in full) / len(full), 4)
    for k, f in files.items():
        nm = noul_metrics(f, ndata) if ndata else None
        if nm:
            res["noul"][k] = {**nm, "ranking": noul_top1(f, ndata, cdata)}
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(res, fh, indent=1)
    print(json.dumps({"n": len(full), "top1": {k: v["top1"] for k, v in res["choice3"].items()},
                      "paired": {k: (v["delta"], v["ci95"], v["only_a"], v["only_b"], v["p_mcnemar"])
                                 for k, v in res["paired"].items()},
                      "noul": {k: (v["auc"], v["ece"]) for k, v in res["noul"].items()}}, indent=1))


if __name__ == "__main__":
    main()
