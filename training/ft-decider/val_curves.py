# ruff: noqa: SIM115
"""Coverage / selective accuracy of the top fill at confidence thresholds (decider_bench semantics) on VAL choice3,
for score files (name=path[:T]) and for Sonnet self-confidence read from the data rows themselves."""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from val_metrics import temper

TS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.7)


def curve(items):  # items: list of (conf, ok)
    n = len(items)
    out = []
    for t in TS:
        f = [ok for c, ok in items if c >= t]
        out.append((len(f) / n, (sum(f) / len(f)) if f else None))
    return out


def main():
    data = [json.loads(x) for x in open(sys.argv[1])]
    meta = {r["id"]: r for r in data}
    rows = {}
    sc = []
    for r in data:
        s = [(-1 if v is None else v) for v in (r.get("self_report") or [])[:3]]
        b = max(range(len(s)), key=lambda i: s[i])
        sc.append((max(s[b], 0), r["option_keys"][b] == r["label"]))
    rows["sonnet-self-conf"] = sc
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        path, _, t = rest.partition(":")
        t = float(t or 1.0)
        items = []
        for x in open(path):
            s = json.loads(x)
            if s.get("shape") != "choice3":
                continue
            m = meta[s["id"]]
            keys = m["option_keys"]
            if "probs" not in s:
                items.append((0.0, False))  # an error counts as an abstained, wrong item
                continue
            p = temper([s["probs"][k] for k in keys], t)
            b = max(range(3), key=lambda i: p[i])
            items.append((p[b], keys[b] == m["label"]))
        rows[name] = items
    print("| decider | N | " + " | ".join(f"t={t}" for t in TS) + " |")
    print("|---|---|" + "---|" * len(TS))
    for name, items in rows.items():
        cells = [f"{c:.3f} / {'-' if a is None else f'{a:.3f}'}" for c, a in curve(items)]
        print(f"| {name} | {len(items)} | " + " | ".join(cells) + " |")


main()
