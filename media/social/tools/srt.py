"""captions.srt for the 30 s social cuts (same text as the burned-in captions; upload as a sidecar where the
platform supports it). One cue per narration sentence/clause, timed from vo.json."""
import json, pathlib, re

SOCIAL = pathlib.Path(__file__).resolve().parent.parent
vo = json.loads((SOCIAL / "vo.json").read_text())


def ts(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


cues = []
for ln in vo["lines"]:
    toks = ln["text"].split()
    words = ln["words"]
    if len(toks) == len(words):
        for w, t in zip(words, toks):
            w["w"] = t
    cur = []
    for w in words:
        cur.append(w)
        if re.search(r"[.,:;]$", w["w"]) and len(" ".join(x["w"] for x in cur)) > 18 or w is words[-1]:
            cues.append((cur[0]["s"], cur[-1]["e"] + 0.2, " ".join(x["w"] for x in cur)))
            cur = []
out = []
for i, (s, e, txt) in enumerate(cues):
    if i + 1 < len(cues):
        e = min(e, cues[i + 1][0] - 0.02)
    out.append(f"{i + 1}\n{ts(s)} --> {ts(e)}\n{txt}\n")
(SOCIAL / "captions.srt").write_text("\n".join(out))
print("\n".join(out))
