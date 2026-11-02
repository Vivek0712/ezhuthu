"""VAL metrics for decider score files written by ft_decider.py score (scored at temperature 1).

choice3 (the restorer's decision, top-3 + none):
  top1        the highest-probability FILL among c0..c2 equals the expert target (decider_bench.score_item:
              'none' is never the pick; the forced fill is scored), over all rows
  top1|oracle the same over rows whose target is among c0..c2
  acc4        argmax over all four options (incl. none) equals the label
  ece_fill    ECE (10 bins) of the top fill's probability vs. its correctness (decider_bench's confidence)
  nll4        mean -log p(label) over the four options
  abst@0.5    share of rows whose top fill has p < 0.5 (routing.abstain_if_confidence_below), selective accuracy
noul (one row per top-3 candidate): AUC, ECE (10 bins), Brier, NLL, base rate, and the noul ranking:
  argmax_k P(yes | c_k) equals the target (noul_top1).

Temperatures: 'T1' = raw (temperature 1), 'ckpt' = the checkpoint's own temperature_by_kind, 'cv' = a per-kind
temperature fitted by NLL with 2-fold cross-fitting over VAL inscriptions (each half scored with the
temperature fitted on the other half), 'fit' = fitted on all VAL (what would be written to the served
checkpoint; in-sample, so only 'cv' is an honest calibrated estimate).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict

EPS = 1e-4


def read(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def temper(ps: list[float], t: float) -> list[float]:
    ls = [math.log(max(p, EPS)) / t for p in ps]
    m = max(ls)
    e = [math.exp(x - m) for x in ls]
    s = sum(e)
    return [x / s for x in e]


def ece(conf, ok, bins=10):
    n = len(conf)
    tot = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i in range(n) if (lo < conf[i] <= hi) or (b == 0 and conf[i] == 0)]
        if idx:
            tot += len(idx) / n * abs(sum(conf[i] for i in idx) / len(idx) - sum(ok[i] for i in idx) / len(idx))
    return tot


def auc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return float("nan")
    # rank-based (Mann-Whitney) with ties
    allv = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg])
    i = 0
    r = [0.0] * len(allv)
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        for k in range(i, j + 1):
            r[k] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(r[k] for k in range(len(allv)) if allv[k][1] == 1)
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def nll_choice(rows, t):
    return sum(-math.log(max(temper(r["p"], t)[r["y"]], 1e-12)) for r in rows) / max(1, len(rows))


def fit_t(rows, kind):
    grid = [0.3 + 0.05 * i for i in range(75)]  # 0.30 .. 4.0
    return min(grid, key=lambda t: nll_choice(rows, t))


def choice_rows(scores, data):
    meta = {r["id"]: r for r in data}
    out = []
    for s in scores:
        if s.get("shape") != "choice3":
            continue
        m = meta[s["id"]]
        keys = m["option_keys"]
        out.append({"id": s["id"], "insc": m["inscription_id"], "p": [s["probs"][k] for k in keys], "y": keys.index(m["label"]),
                    "fills_ok": [k == m["label"] for k in keys[:-1]], "oracle": m["label"] != "none", "hard": m.get("hard")})
    return out


def noul_rows(scores, data):
    meta = {r["id"]: r for r in data}
    out = []
    for s in scores:
        if s.get("shape") != "noul":
            continue
        m = meta[s["id"]]
        p1 = s["p_true"]
        out.append({"id": s["id"], "item": m["item_id"], "insc": m["inscription_id"], "p": [1 - p1, p1],
                    "y": 1 if m["label"] in ("yes", 1, True, "true") else 0})
    return out


def choice_metrics(rows, t):
    n = len(rows)
    top1 = acc4 = 0
    conf, ok = [], []
    orc_n = orc_ok = 0
    nll = 0.0
    filled = filled_ok = 0
    for r in rows:
        p = temper(r["p"], t)
        best = max(range(3), key=lambda i: p[i])
        c = r["fills_ok"][best]
        top1 += c
        conf.append(p[best])
        ok.append(1 if c else 0)
        acc4 += max(range(4), key=lambda i: p[i]) == r["y"]
        nll += -math.log(max(p[r["y"]], 1e-12))
        if r["oracle"]:
            orc_n += 1
            orc_ok += c
        if p[best] >= 0.5:
            filled += 1
            filled_ok += c
    return {"n": n, "top1": top1 / n, "top1_oracle": orc_ok / max(orc_n, 1), "acc4": acc4 / n,
            "ece_fill": ece(conf, ok), "nll4": nll / n, "abstain@0.5": 1 - filled / n,
            "sel_acc@0.5": (filled_ok / filled) if filled else None, "filled@0.5": filled}


def noul_metrics(rows, t):
    ps = [temper(r["p"], t)[1] for r in rows]
    ys = [r["y"] for r in rows]
    n = len(rows)
    by = defaultdict(list)
    for r, p in zip(rows, ps):
        by[r["item"]].append((p, r["y"]))
    top = sum(max(v)[1] for v in by.values()) / len(by)
    return {"n": n, "auc": auc(ps, ys), "ece": ece(ps, ys), "brier": sum((p - y) ** 2 for p, y in zip(ps, ys)) / n,
            "nll": sum(-math.log(max(p if y else 1 - p, 1e-12)) for p, y in zip(ps, ys)) / n,
            "base_rate": sum(ys) / n, "mean_p": sum(ps) / n, "noul_top1": top, "items": len(by)}


def cv_t(rows, metric, seed=0):
    """2-fold cross-fitted temperature over inscriptions: each half is scored with the other half's T."""
    ins = sorted({r["insc"] for r in rows})
    rng = random.Random(seed)
    rng.shuffle(ins)
    half = set(ins[: len(ins) // 2])
    a = [r for r in rows if r["insc"] in half]
    b = [r for r in rows if r["insc"] not in half]
    ta, tb = fit_t(a, None), fit_t(b, None)
    return ta, tb, a, b


def merge_cv(rows, fn):
    ta, tb, a, b = cv_t(rows, fn)
    # score a with tb and b with ta, then pool by recomputing on per-row tempered copies
    pooled = [dict(r, p=temper(r["p"], tb)) for r in a] + [dict(r, p=temper(r["p"], ta)) for r in b]
    return fn(pooled, 1.0), (round(ta, 2), round(tb, 2))


def bootstrap_paired(a_rows, b_rows, t_a, t_b, B=2000, seed=0):
    """Paired bootstrap 95% CI of top1(b) - top1(a) over items (choice3)."""
    ia = {r["id"]: r for r in a_rows}
    ib = {r["id"]: r for r in b_rows}
    ids = sorted(set(ia) & set(ib))

    def ok(r, t):
        p = temper(r["p"], t)
        return 1 if r["fills_ok"][max(range(3), key=lambda i: p[i])] else 0

    d = [ok(ib[i], t_b) - ok(ia[i], t_a) for i in ids]
    rng = random.Random(seed)
    stats = sorted(sum(d[rng.randrange(len(d))] for _ in d) / len(d) for _ in range(B))
    only_a = sum(1 for x in d if x < 0)
    only_b = sum(1 for x in d if x > 0)
    # exact two-sided McNemar
    n = only_a + only_b
    k = min(only_a, only_b)
    p = min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / (2 ** n)) if n else 1.0
    return {"delta": sum(d) / len(d), "ci95": (stats[int(0.025 * B)], stats[int(0.975 * B)]),
            "only_base": only_a, "only_ft": only_b, "mcnemar_p": p, "n": len(ids)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--choice-data", required=True)
    ap.add_argument("--noul-data", required=True)
    ap.add_argument("--ckpt-temps", default="{}", help="JSON {name: {choice: T, noul: T}}")
    ap.add_argument("--baseline", default="")
    ap.add_argument("--json-out", default="")
    ap.add_argument("scores", nargs="+", help="name=path")
    a = ap.parse_args()
    cdata, ndata = read(a.choice_data), read(a.noul_data)
    ckt = json.loads(a.ckpt_temps)
    res = {}
    rows_by = {}
    for spec in a.scores:
        name, path = spec.split("=", 1)
        sc = read(path)
        cr, nr = choice_rows(sc, cdata), noul_rows(sc, ndata)
        rows_by[name] = (cr, nr)
        tc = ckt.get(name, {}).get("choice", 1.0)
        tn = ckt.get(name, {}).get("noul", 1.0)
        fc, fn_ = fit_t(cr, "choice"), (fit_t(nr, "noul") if nr else 1.0)
        cv_c, cv_ct = merge_cv(cr, choice_metrics)
        cv_n, cv_nt = merge_cv(nr, noul_metrics) if nr else (None, None)
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        res[name] = {"file_sha256": digest,
                     "choice": {"T1": choice_metrics(cr, 1.0), "ckpt": choice_metrics(cr, tc), "cv": cv_c,
                                "fit": choice_metrics(cr, fc)},
                     "noul": ({"T1": noul_metrics(nr, 1.0), "ckpt": noul_metrics(nr, tn), "cv": cv_n,
                               "fit": noul_metrics(nr, fn_)} if nr else None),
                     "temps": {"ckpt": {"choice": tc, "noul": tn}, "fit_all_val": {"choice": round(fc, 2), "noul": round(fn_, 2)},
                               "cv_folds": {"choice": cv_ct, "noul": cv_nt}}}
    if a.baseline:
        bc = rows_by[a.baseline][0]
        for name, (cr, _) in rows_by.items():
            if name != a.baseline:
                res[name]["vs_" + a.baseline] = bootstrap_paired(bc, cr, 1.0, 1.0)
    # reference rows on identical requests (from the data rows themselves)
    ref = {"c0_alone": sum(1 for r in cdata if r["label"] == "c0") / len(cdata),
           "target_in_top3": sum(1 for r in cdata if r["label"] != "none") / len(cdata)}
    sr_ok = 0
    for r in cdata:
        sr = r.get("self_report") or []
        if sr and any(x is not None for x in sr[:3]):
            b = max(range(len(sr[:3])), key=lambda i: -1 if sr[i] is None else sr[i])
            sr_ok += r["option_keys"][b] == r["label"]
    ref["sonnet_self_confidence_top3"] = sr_ok / len(cdata)
    res["_reference"] = ref
    if a.json_out:
        with open(a.json_out, "w") as fh:
            json.dump(res, fh, indent=1)
    print(json.dumps(ref))
    hdr = f"{'model':<16}{'T':<5}{'top1':>7}{'t1|or':>7}{'acc4':>7}{'eceF':>7}{'nll4':>7}{'abst':>7}{'selA':>7} |{'AUC':>7}{'ECE':>7}{'brier':>7}{'nll':>7}{'nTop1':>7}"
    print(hdr)
    for name, r in res.items():
        if name.startswith("_"):
            continue
        for tk in ("T1", "ckpt", "cv"):
            c = r["choice"][tk]
            sa = "-" if c["sel_acc@0.5"] is None else f"{c['sel_acc@0.5']:.3f}"
            line = (f"{name:<16}{tk:<5}{c['top1']:>7.3f}{c['top1_oracle']:>7.3f}{c['acc4']:>7.3f}{c['ece_fill']:>7.3f}"
                    f"{c['nll4']:>7.3f}{c['abstain@0.5']:>7.3f}{sa:>7} |")
            if r["noul"]:
                n = r["noul"][tk]
                line += f"{n['auc']:>7.3f}{n['ece']:>7.3f}{n['brier']:>7.3f}{n['nll']:>7.3f}{n['noul_top1']:>7.3f}"
            print(line)
        if "vs_" + a.baseline in r:
            print("   ", "vs", a.baseline, json.dumps(r["vs_" + a.baseline]))


if __name__ == "__main__":
    main()
