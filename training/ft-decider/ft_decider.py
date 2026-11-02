"""Continue-fine-tune a released Strands Decider on the restorer's decision rows, and score it.

Built on strands-decider 0.2.0's own code (the package `strands-decider serve` runs): the checkpoint is
loaded with `StrandsDeciderModel.load`, its LoRA adapter and pointer head are made trainable (a
continue-from fine-tune: nothing is re-initialised), and every training row is turned into tensors by the
serving engine's own `render_question` / `render_state` / `_fit` / `_option_idx`, so the model trains on
exactly the token sequence and option positions it is served with. Loss: cross-entropy over the row's
options at temperature 1 (as the released recipe trains), weighted per shape.

Why not `strands-decider train`: the 0.2.0 wheel ships no trainer, and the trainers on this machine
(3e94e9d, sd-next) predate the v1-2610 export format (r48 seed-soup LoRA, pointer_dim 768) and render
prompts from an older prompting module. See the report for the details.

Subcommands
  tokstats  token lengths of rows as the engine fits them
  train     fine-tune (writes <out>/checkpoint-*/ and <out>/train.log.jsonl)
  score     score rows in-process with SystemOneEngine.evaluate (the serve code path), write per-row probs
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import random
import time

import torch
from strands_decider.infer import EngineConfig, SystemOneEngine, _option_token_index
from strands_decider.modeling import StrandsDeciderModel, checkpoint_dir
from strands_decider.prompting import render_question, render_state
from strands_decider.schema import SystemOneRequest

BASE = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"


def read_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def payload(row: dict) -> dict:
    req = row["request"]
    if isinstance(req, str):
        try:
            req = json.loads(req)
        except json.JSONDecodeError:
            req = ast.literal_eval(req)
    return req


def label_slot(row: dict, rq) -> int:
    """Index of the gold option in the rendered slot order."""
    if rq.kind == "noul":
        lab = row["label"]
        yes = lab in (1, True, "true", "yes") or (isinstance(lab, str) and lab.lower() in ("true", "yes"))
        return rq.slot_labels.index("true" if yes else "false")
    return rq.slot_labels.index(row["label"])


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Encoder:
    """Rows -> (ids, opt_idx, n_slots, label), through the serving engine's own fitting code."""

    def __init__(self, engine: SystemOneEngine):
        self.engine = engine

    def encode(self, row: dict) -> dict:
        req = SystemOneRequest(**payload(row))
        (_name, q), = req.questions.items()
        rq = render_question(q)
        state_text = render_state(req.state)
        s, qids, offs = self.engine._fit(state_text, [rq.text])
        ids = s + qids[0]
        opt = [len(s) + i for i in _option_token_index(offs[0], rq.option_spans, 0)]
        return {"ids": ids, "opt_idx": opt, "n_slots": rq.n_slots, "label": label_slot(row, rq),
                "kind": rq.kind, "slot_labels": list(rq.slot_labels)}


def load(ckpt: str, device: str) -> tuple[StrandsDeciderModel, SystemOneEngine]:
    model = StrandsDeciderModel.load(ckpt)
    engine = SystemOneEngine(model, EngineConfig(device=device, model_name=os.path.basename(ckpt.rstrip("/"))))
    return model, engine


def cmd_tokstats(a):
    _model, engine = load(checkpoint_dir(a.ckpt), a.device)
    enc = Encoder(engine)
    for f in a.files:
        rows = read_rows(f)
        L = sorted(len(enc.encode(r)["ids"]) for r in rows)
        n = len(L)
        print(f"{os.path.basename(f)}: n={n} p50={L[n // 2]} p90={L[int(n * .9)]} max={L[-1]} sum={sum(L)}")


def forward_one(model, ex: dict, device: str):
    ids = torch.tensor([ex["ids"]], device=device)
    mask = torch.ones_like(ids)
    out = model(input_ids=ids, attention_mask=mask, n_slots=torch.tensor([ex["n_slots"]], device=device),
                labels=torch.tensor([ex["label"]], device=device),
                temperature=torch.ones(1, device=device), opt_idx=torch.tensor([ex["opt_idx"]], device=device))
    return out


def cmd_train(a):
    random.seed(a.seed)
    torch.manual_seed(a.seed)
    ckpt = checkpoint_dir(a.ckpt)
    model, engine = load(ckpt, a.device)
    enc = Encoder(engine)
    os.makedirs(a.out, exist_ok=True)
    # trainable: the checkpoint's own LoRA adapter (continue) + its pointer head
    n_lora = 0
    for n, p in model.torso.named_parameters():
        if "lora_" in n:
            p.requires_grad_(True)
            if p.dtype != torch.float32:
                p.data = p.data.float()
            n_lora += p.numel()
        else:
            p.requires_grad_(False)
    for p in model.head.parameters():
        p.requires_grad_(True)
    n_head = sum(p.numel() for p in model.head.parameters())
    inner = model.torso.base_model.model if hasattr(model.torso, "base_model") else model.torso
    if a.grad_ckpt:
        inner.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    inner.config.use_cache = False
    model.train()

    rows = []
    for spec in a.train:
        path, _, w = spec.partition(":")
        rs = read_rows(path)
        frac = float(a.noul_frac) if "noul" in os.path.basename(path) else 1.0
        if frac < 1.0:
            rng = random.Random(a.seed)
            rs = [r for r in rs if rng.random() < frac]
        for r in rs:
            rows.append((r, float(w or 1.0)))
    t0 = time.time()
    data = []
    for r, w in rows:
        ex = enc.encode(r)
        ex["w"] = w
        ex["id"] = r["id"]
        data.append(ex)
    print(f"[ft] encoded {len(data)} rows in {time.time() - t0:.0f}s; lora params {n_lora:,}, head {n_head:,}",
          flush=True)
    meta = {"base": a.ckpt, "base_dir": ckpt, "train": a.train, "train_sha256": {s.partition(':')[0]:
            sha256(s.partition(':')[0]) for s in a.train}, "rows": len(data), "args": {k: v for k, v in vars(a).items() if k != "fn"}}
    with open(os.path.join(a.out, "train_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)

    lora_params = [p for n, p in model.torso.named_parameters() if p.requires_grad]
    opt = torch.optim.AdamW([{"params": lora_params, "lr": a.lr}, {"params": list(model.head.parameters()),
                             "lr": a.head_lr}], weight_decay=0.01)
    steps_per_epoch = math.ceil(len(data) / a.accum)
    total = a.max_steps or int(steps_per_epoch * a.epochs)
    warm = max(1, int(0.05 * total))
    base_lrs = [g["lr"] for g in opt.param_groups]
    log = open(os.path.join(a.out, "train.log.jsonl"), "a")  # noqa: SIM115 (closed after the loop)
    order: list[int] = []
    step, t_start, run_loss, run_n = 0, time.time(), 0.0, 0
    save_at = {int(x) for x in a.save_at.split(",")} if a.save_at else set()
    while step < total:
        if not order:
            order = list(range(len(data)))
            random.shuffle(order)
        for g, b in zip(opt.param_groups, base_lrs):
            frac = (step + 1) / warm if step < warm else 0.5 * (1 + math.cos(math.pi * (step - warm) / max(1, total - warm)))
            g["lr"] = b * frac
        wsum = 0.0
        batch = [order.pop() for _ in range(min(a.accum, len(order)))]
        wsum = sum(data[i]["w"] for i in batch)
        for i in batch:
            ex = data[i]
            out = forward_one(model, ex, a.device)
            loss = out["loss"] * ex["w"] / wsum
            loss.backward()
            run_loss += float(out["loss"]) * ex["w"]
            run_n += ex["w"]
        torch.nn.utils.clip_grad_norm_([p for g in opt.param_groups for p in g["params"]], 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        step += 1
        if step % a.log_every == 0 or step == total:
            el = time.time() - t_start
            rec = {"step": step, "total": total, "loss": round(run_loss / max(run_n, 1e-9), 4),
                   "lr": opt.param_groups[0]["lr"], "elapsed_s": round(el), "s_per_step": round(el / step, 2)}
            print("[ft]", json.dumps(rec), flush=True)
            log.write(json.dumps(rec) + "\n")
            log.flush()
            run_loss, run_n = 0.0, 0
        if step in save_at or step == total:
            save(model, ckpt, os.path.join(a.out, f"checkpoint-{step}"), meta, step)
    log.close()


def save(model, base_dir: str, out: str, meta: dict, step: int):
    """A checkpoint `strands-decider serve` loads: config + slot_head.pt + lora/ + tokenizer."""
    was = model.training
    model.eval()
    os.makedirs(out, exist_ok=True)
    model.save_pretrained(out)
    # PEFT saves the adapter in fp32 after our upcast; keep it so (bf16 base, fp32 adapter loads fine)
    for f in ("provenance.json",):
        src = os.path.join(base_dir, f)
        if os.path.exists(src):
            with open(src) as fh:
                prov = json.load(fh)
            with open(os.path.join(out, "base_provenance.json"), "w") as fh:
                json.dump(prov, fh, indent=1)
    with open(os.path.join(out, "finetune.json"), "w") as fh:
        json.dump({**meta, "step": step}, fh, indent=1)
    print(f"[ft] saved {out}", flush=True)
    if was:
        model.train()


@torch.inference_mode()
def cmd_score(a):
    ckpt = checkpoint_dir(a.ckpt)
    model, engine = load(ckpt, a.device)
    if a.temps:
        model.config.temperature_by_kind = json.loads(a.temps)
    out = open(a.out, "w")  # noqa: SIM115 (closed after the loop)
    for f in a.files:
        rows = read_rows(f)
        if a.limit:
            rows = rows[: a.limit]
        t0 = time.time()
        for r in rows:
            res = engine.evaluate(SystemOneRequest(**payload(r)))
            (_name, ans), = res.answers.items()
            rec = {"id": r["id"], "file": os.path.basename(f), "shape": r.get("shape"), "label": r["label"]}
            d = ans.model_dump()
            if "noul" in d and d.get("noul") is not None:
                rec["p_true"] = d["noul"]
            if d.get("probabilities"):
                rec["probs"] = d["probabilities"]
            out.write(json.dumps(rec) + "\n")
        print(f"[score] {f}: {len(rows)} rows in {time.time() - t0:.0f}s", flush=True)
    out.close()
    with open(a.out + ".meta.json", "w") as fh:
        json.dump({"ckpt": a.ckpt, "ckpt_dir": ckpt, "files": {f: sha256(f) for f in a.files},
                   "temperature": model.config.temperature,
                   "temperature_by_kind": model.config.temperature_by_kind, "device": a.device}, fh, indent=1)


def main(argv=None):
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("tokstats")
    t.add_argument("--ckpt", default=BASE)
    t.add_argument("--device", default="mps")
    t.add_argument("files", nargs="+")
    t.set_defaults(fn=cmd_tokstats)
    t = sp.add_parser("train")
    t.add_argument("--ckpt", default=BASE)
    t.add_argument("--device", default="mps")
    t.add_argument("--train", nargs="+", required=True, help="path[:weight]")
    t.add_argument("--noul-frac", default="1.0")
    t.add_argument("--out", required=True)
    t.add_argument("--lr", type=float, default=5e-5)
    t.add_argument("--head-lr", type=float, default=5e-4)
    t.add_argument("--accum", type=int, default=16)
    t.add_argument("--epochs", type=float, default=1.0)
    t.add_argument("--max-steps", type=int, default=0)
    t.add_argument("--save-at", default="")
    t.add_argument("--log-every", type=int, default=5)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--grad-ckpt", action="store_true")
    t.set_defaults(fn=cmd_train)
    t = sp.add_parser("score")
    t.add_argument("--ckpt", default=BASE)
    t.add_argument("--device", default="mps")
    t.add_argument("--out", required=True)
    t.add_argument("--limit", type=int, default=0)
    t.add_argument("--temps", default="", help="JSON temperature_by_kind override")
    t.add_argument("files", nargs="+")
    t.set_defaults(fn=cmd_score)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
