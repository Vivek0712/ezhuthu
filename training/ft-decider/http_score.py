# ruff: noqa: SIM115
"""Score rows through a running `strands-decider serve` (POST /v1/systemone), one request at a time."""
import json
import os
import sys
import time
import urllib.request

url, out = sys.argv[1].rstrip("/"), sys.argv[2]
with open(out, "w") as fh:
    for f in sys.argv[3:]:
        t0 = time.time()
        n = 0
        for line in open(f):
            r = json.loads(line)
            req = urllib.request.Request(url + "/v1/systemone", data=json.dumps(r["request"]).encode(),
                                         headers={"content-type": "application/json"})
            res = json.load(urllib.request.urlopen(req, timeout=300))
            (_, a), = res["answers"].items()
            rec = {"id": r["id"], "file": os.path.basename(f), "shape": r["shape"], "label": r["label"],
                   "model": res["model"]}
            if a.get("type") == "noul":
                rec["p_true"] = a["noul"]
            else:
                rec["probs"] = a["probabilities"]
            fh.write(json.dumps(rec) + "\n")
            n += 1
        print(f"[http] {f}: {n} rows in {time.time() - t0:.0f}s", flush=True)
