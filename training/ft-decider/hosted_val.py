# ruff: noqa: SIM115
"""Score VAL choice3 rows with hosted v19 (decider-cloud) through ezhuthu's own HostedDecider client.

Same requests as the local models (row['request'] verbatim). Resumable: rows already in --out are skipped.
The API key is read by the client from Secrets Manager and never printed.
"""
import json
import os
import sys

from ezhuthu.agent.decider import DeciderUnavailable, hosted_decider

data, out = sys.argv[1], sys.argv[2]
done = set()
if os.path.exists(out):
    done = {json.loads(x)["id"] for x in open(out) if x.strip()}
d = hosted_decider()
if not d.available():
    raise SystemExit("hosted decider not available")
n = err = 0
with open(out, "a") as fh:
    for line in open(data):
        r = json.loads(line)
        if r["id"] in done:
            continue
        (name, q), = r["request"]["questions"].items()
        try:
            c = d.choice(r["request"]["state"], q["instructions"], q["criteria"], name=name)
            rec = {"id": r["id"], "file": os.path.basename(data), "shape": r["shape"], "label": r["label"],
                   "probs": {k: c.probabilities.get(k, 0.0) for k in r["option_keys"]}, "model": c.model,
                   "latency_ms": c.latency_ms, "trimmed": getattr(d, "last_trimmed", None)}
        except DeciderUnavailable as e:
            err += 1
            rec = {"id": r["id"], "file": os.path.basename(data), "shape": r["shape"], "label": r["label"],
                   "error": str(e)[:200]}
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        n += 1
        if n % 25 == 0:
            print(f"[hosted] {n} new rows, {err} errors", flush=True)
print(f"[hosted] done: {n} new rows, {err} errors", flush=True)
