"""Expert-validation kit CLI (docs/expert-validation/PROTOCOL.md).

    python -m ezhuthu.expert sample   --out kit/sample.jsonl [--seed 2026 --n-blank 12 --n-masked 12 --n-reading 12 --spares 2]
    python -m ezhuthu.expert propose  --sample kit/sample.jsonl --out kit/proposals.jsonl --router none|sonnet
    python -m ezhuthu.expert generate --sample kit/sample.jsonl --proposals kit/proposals.jsonl \\
                                      --raters R1,R2,R3,R4 --out kit/packet [--pdf]
    python -m ezhuthu.expert synth    --key kit/packet/coordinator/key.json --raters 4 --out kit/synthetic
    python -m ezhuthu.expert analyze  --key kit/packet/coordinator/key.json --out results kit/returned/*.csv

``propose --router sonnet`` calls Bedrock (one call per passage, plus retries) and needs ``EZHUTHU_LIVE=1``.
``--max-llm-calls`` (default 40) caps actual calls, retries and failed calls included: a sample with more
passages is refused up front, and the run stops calling once the cap is reached. The ``sample`` defaults give
12 + 2 + 12 + 2 + 12 = 40 passages, so the quick start fits the cap.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .packet import SampleSpec, build_packet, read_jsonl, sample_items, sha12, write_jsonl, write_packet


def _bench_dir(arg: str | None) -> Path:
    from ..agent.data import data_source

    return Path(arg) if arg else data_source().path


def cmd_sample(a: argparse.Namespace) -> int:
    bdir = _bench_dir(a.benchmark_dir)
    spec = SampleSpec(seed=a.seed, n_blank=a.n_blank, n_masked=a.n_masked, n_reading=a.n_reading,
                      min_gap=a.min_gap, max_gap=a.max_gap, spares=a.spares, blank_splits=tuple(a.blank_splits.split(",")))
    rows = sample_items(bdir, spec)
    out = Path(a.out)
    write_jsonl(out, rows)
    meta = {"seed": a.seed, "spec": spec.__dict__, "benchmark_dir": bdir.name,
            "blank_sha12": sha12(bdir / "blank.jsonl"), "test_sha12": sha12(bdir / "items.test.jsonl"),
            "counts": {r: sum(1 for x in rows if x["role"] == r) for r in ("rating-blank", "rating-masked", "reading")}}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1, default=list), encoding="utf-8")
    print(json.dumps(meta["counts"]))
    return 0


def cmd_propose(a: argparse.Namespace) -> int:
    from .packet import propose

    sample = read_jsonl(Path(a.sample))
    try:
        rows, meta = propose(sample, router=a.router, max_llm_calls=a.max_llm_calls, k=a.k)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out = Path(a.out)
    write_jsonl(out, rows)
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps({k: meta[k] for k in ("router", "errors", "llm_call_attempts", "cap_reached", "usage")}))
    return 0


def cmd_generate(a: argparse.Namespace) -> int:
    sample = read_jsonl(Path(a.sample))
    proposals = read_jsonl(Path(a.proposals))
    pmeta_path = Path(str(a.proposals) + ".meta.json")
    pmeta = json.loads(pmeta_path.read_text()) if pmeta_path.exists() else {}
    smeta_path = Path(str(a.sample) + ".meta.json")
    smeta = json.loads(smeta_path.read_text()) if smeta_path.exists() else {}
    prov = {"router": pmeta.get("router"), "llm": pmeta.get("llm"), "ranking": pmeta.get("ranking"),
            "use_ontology": pmeta.get("use_ontology"), "sample_seed": smeta.get("seed"),
            "blank_sha12": smeta.get("blank_sha12"), "test_sha12": smeta.get("test_sha12")}
    raters = [r.strip() for r in a.raters.split(",") if r.strip()]
    key = build_packet(sample, proposals, seed=a.seed, options_per_item=a.options, provenance=prov,
                       length_tolerance=None if a.length_tolerance < 0 else a.length_tolerance)
    out = Path(a.out)
    written = write_packet(key, raters, out)
    if a.pdf:
        from .render import html_to_pdf

        for p in [p for ps in written.values() for p in ps if p.suffix == ".html"]:
            html_to_pdf(p, p.with_suffix(".pdf"))
    print(json.dumps({"rating_items": key["meta"]["n_rating"], "reading_items": key["meta"]["n_reading"],
                      "dropped": key["dropped"], "raters": raters, "out": str(out)}, ensure_ascii=False))
    return 0


def cmd_synth(a: argparse.Namespace) -> int:
    from .synth import write_synthetic

    key = json.loads(Path(a.key).read_text(encoding="utf-8"))
    paths = write_synthetic(key, a.raters, Path(a.out), seed=a.seed, rater_sd=a.rater_sd)
    print(json.dumps([str(p) for p in paths]))
    return 0


def cmd_analyze(a: argparse.Namespace) -> int:
    from .analyze import SheetError, analyze, to_markdown

    key = json.loads(Path(a.key).read_text(encoding="utf-8"))
    try:
        res = analyze([Path(p) for p in a.sheets], key, n_boot=a.n_boot, seed=a.seed)
    except SheetError as exc:
        print(f"sheet error: {exc}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "expert-validation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "expert-validation.md").write_text(to_markdown(res), encoding="utf-8")
    print(to_markdown(res))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m ezhuthu.expert", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="seeded sample of blank, masked and reading-study passages")
    s.add_argument("--out", required=True)
    s.add_argument("--benchmark-dir", default=None)
    s.add_argument("--seed", type=int, default=2026)
    s.add_argument("--n-blank", type=int, default=12)
    s.add_argument("--n-masked", type=int, default=12)
    s.add_argument("--n-reading", type=int, default=12)
    s.add_argument("--min-gap", type=int, default=2)
    s.add_argument("--max-gap", type=int, default=12)
    s.add_argument("--spares", type=int, default=2, help="extra rating items per role, used if one drops out")
    s.add_argument("--blank-splits", default="test,val", help="splits to draw blank passages from")
    s.set_defaults(fn=cmd_sample)
    p = sub.add_parser("propose", help="run the restorer on the sample (ontology off, train-only retrieval)")
    p.add_argument("--sample", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--router", default="none", choices=["none", "sonnet", "opus", "routed"])
    p.add_argument("--max-llm-calls", type=int, default=40)
    p.add_argument("--k", type=int, default=8, help="proposals kept per passage")
    p.set_defaults(fn=cmd_propose)
    g = sub.add_parser("generate", help="blinded per-rater sheets (CSV + printable HTML, optional PDF)")
    g.add_argument("--sample", required=True)
    g.add_argument("--proposals", required=True)
    g.add_argument("--raters", required=True, help="comma-separated rater codes (no names), e.g. R1,R2,R3")
    g.add_argument("--out", required=True)
    g.add_argument("--seed", type=int, default=2026)
    g.add_argument("--options", type=int, default=3, help="options per rating item (same for every item)")
    g.add_argument("--length-tolerance", type=int, default=1,
                   help="prefer AI options within this many aksharas of the gap (-1: no preference)")
    g.add_argument("--pdf", action="store_true", help="also print every HTML sheet to PDF with headless Chrome")
    g.set_defaults(fn=cmd_generate)
    y = sub.add_parser("synth", help="synthetic filled sheets (SYN- raters) to test the analysis")
    y.add_argument("--key", required=True)
    y.add_argument("--out", required=True)
    y.add_argument("--raters", type=int, default=4)
    y.add_argument("--seed", type=int, default=0)
    y.add_argument("--rater-sd", type=float, default=0.5)
    y.set_defaults(fn=cmd_synth)
    z = sub.add_parser("analyze", help="agreement, plausibility and reading-study metrics from filled sheets")
    z.add_argument("--key", required=True)
    z.add_argument("--out", required=True)
    z.add_argument("--n-boot", type=int, default=2000)
    z.add_argument("--seed", type=int, default=0)
    z.add_argument("sheets", nargs="+", help="filled CSV files or directories")
    z.set_defaults(fn=cmd_analyze)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
