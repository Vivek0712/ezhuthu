"""Run Ezhuthu's own Reader and Restorer on the home-hero photograph and record what they really said.

The home hero (app/web/src/components/StoneHero.tsx) animates a real stone: it highlights letters, sends them
through the Reader -> Restorer -> Strands Decider pipeline, and shows the text that comes out. This script makes
that output real instead of invented:

  read     POST /api/read code path (``EzhuthuService.reader.read``, router "routed": Sonnet 4.6 first) on the
           hero crop; writes the raw response to app/web/src/hero/runs/read.json
  restore  POST /api/restore code path (``EzhuthuService.restore``) on the reading's gapped lines, if any;
           writes app/web/src/hero/runs/restore.json

Live Bedrock calls need EZHUTHU_LIVE=1 and are capped by --max-live-calls (cached replies under .cache/llm/ do not
count). Models come only from config/models.yaml. Assembling hero-reading.json (boxes, edition, CER) is
scripts/hero_build.py.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERO = ROOT / "app" / "web" / "src" / "hero"
RUNS = HERO / "runs"
SRC_IMAGE = ROOT / "design" / "hero" / "thanjavur-crop.jpg"


def _service(max_live: int):
    from ezhuthu.agent.llm import BedrockLLM, BudgetedLLM
    from ezhuthu.api.service import EzhuthuService

    llm = BudgetedLLM(BedrockLLM(), max_live)
    return EzhuthuService(llm=llm, admin_token=None), llm  # type: ignore[arg-type]


def cmd_read(args: argparse.Namespace) -> None:
    svc, llm = _service(args.max_live_calls)
    b64 = base64.b64encode(Path(args.image).read_bytes()).decode()
    out = svc.reader.read(image_base64=b64, router=args.router)
    first = dict(out)
    if args.reread and out.get("reread_token"):
        # The app's "Read again with the larger model" button: the same photo, router "opus", the one-time token.
        out = svc.reader.read(image_base64=b64, router="opus", reread_token=out["reread_token"])
        out["reread_of"] = {k: first[k] for k in ("confidence", "models_used", "escalation_skipped", "text")
                            if k in first}
    out.pop("trace_id", None)
    out.pop("reread_token", None)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "read.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"lines": [ln["text"] for ln in out["lines"]], "confidence": out.get("confidence"),
                      "models": out.get("models_used"), "ledger": llm.ledger.to_dict()}, ensure_ascii=False,
                     indent=2))


def cmd_restore(args: argparse.Namespace) -> None:
    svc, llm = _service(args.max_live_calls)
    read = json.loads((RUNS / "read.json").read_text(encoding="utf-8"))
    lines = [ln["text"] for ln in read["lines"]]
    if args.text:
        text = args.text
    else:
        text = "\n".join(lines)
    if "[?" not in text:
        print("the reading has no gaps; nothing to restore (pass --text with an explicit gap to demonstrate)")
        sys.exit(2)
    out = svc.restore(text, script="iso15919", max_candidates=5)
    out.pop("trace_id", None)
    payload = {"input": text, "response": out}
    (RUNS / "restore.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gaps": out.get("gaps"), "ledger": llm.ledger.to_dict()}, ensure_ascii=False, indent=2)[:4000])


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("--image", default=str(SRC_IMAGE))
    r.add_argument("--router", default="routed", choices=("routed", "sonnet"))
    r.add_argument("--reread", action="store_true",
                   help="if escalation was skipped for time, read again with router opus and the reread token")
    r.add_argument("--max-live-calls", type=int, default=2)
    r.set_defaults(fn=cmd_read)
    s = sub.add_parser("restore")
    s.add_argument("--text", help="ISO-15919 text with [?N] gaps (default: the reading itself)")
    s.add_argument("--max-live-calls", type=int, default=4)
    s.set_defaults(fn=cmd_restore)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
