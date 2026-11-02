"""Render all 22 scenes with a v2 voice, choosing per scene the calmest pacing that fits its VO window.

Pacing ladder per scene (first that leaves >= 0.30 s margin wins):
  rate 90% + 350 ms sentence breaks -> 95% + breaks -> 95% plain -> 100% plain -> 105% plain.
Usage: python3 synth_v2.py VOICE ENGINE [--tag NAME] [--final]
  --final also writes narration-v2.json, captions-v2.srt (media/video/audio-v2/) and the 180 s stem.
Binaries: ezhuthu-video/audio-v2/vo/<tag>/  (never git).
"""
import argparse, json, re, sys
import numpy as np
import scipy.io.wavfile as wf
import v2lib as L

LADDER = [("90%", True), ("95%", True), ("95%", False), ("100%", False), ("105%", False)]
# en-IN voices pronounce these place names natively and better than our IPA (Transcribe en-IN check,
# check/pron and check/thanjavur: plain Thanjavur heard as 'Thanjavur' 3/4, IPA 0/4); IPA only for zh words.
NATIVE_EN_IN = {"Madurai", "Thanjavur", "Meenakshi", "Rajaraja", "Keeladi", "Uttiramerur", "Chola"}

Y2021 = '<say-as interpret-as="date" format="y">2021</say-as>'
# v2 script (user direction 2026-11-03): Tamil's significance early in Act 1, a more urgent Act 1, and the solution
# framed as recovery in Act 2 + the close. Each scene: variants, longest first, as (caption text, spoken body);
# the first variant that fits (at any rate on the ladder) wins. Numbers are never changed. Scenes not listed keep
# the storyboard narration verbatim. External facts: see ../README.md "External facts".
TEXT_V2 = {
    "a1-02-place": [
        ("Tamil is one of the oldest living classical languages, written in stone for over 2,000 years, "
         "from Madurai to Thanjavur.",
         "Tamil is one of the oldest living classical languages, written in stone for over two thousand years, "
         "from Madurai to Thanjavur."),
        ("Tamil is one of the oldest living classical languages, written in stone for over 2,000 years.",
         "Tamil is one of the oldest living classical languages, written in stone for over two thousand years."),
        ("Tamil is one of the oldest living classical languages, in stone for over 2,000 years.",
         "Tamil is one of the oldest living classical languages, in stone for over two thousand years."),
    ],
    "a1-03-madurai-in-stone": [
        ("Sangam poets sang of Madurai. Its name is carved in these stones too.",
         "Sangam poets sang of Madurai. Its name is carved in these stones too."),
        ("Sangam poets sang of Madurai. Its name is carved in stone.",
         "Sangam poets sang of Madurai. Its name is carved in stone."),
    ],
    "a1-04-damage": [
        ("Sun, rain and time wear the letters away. 65% of the 1,320 inscriptions we studied are damaged.",
         "Sun, rain and time wear the letters away. 65 percent of the 1,320 inscriptions we studied are damaged."),
        ("Sun and rain wear the letters away. 65% of the 1,320 inscriptions we studied are damaged.",
         "Sun and rain wear the letters away. 65 percent of the 1,320 inscriptions we studied are damaged."),
    ],
    "a1-05-few-readers": [
        ("In 2021, India had only about 23 epigraphists for nearly one lakh inscriptions.",
         f"In {Y2021}, India had only about 23 epigraphists for nearly one lakh inscriptions."),
        ("In 2021, India had about 23 epigraphists for nearly one lakh inscriptions.",
         f"In {Y2021}, India had about 23 epigraphists for nearly one lakh inscriptions."),
    ],
    "a1-06-slow": [
        ("And every year, more of the story is lost.", "And every year, more of the story is lost."),
        ("Every year, more is lost.", "Every year, more is lost."),
    ],
    "a2-08-hero-read": [
        ("On a real Chola-period stone from Thanjavur, it reads the letters, then the words, then the meaning, "
         "in Tamil and English. Stones like it record gifts to temples, lamps to burn forever, land and water.",
         "On a real Chola-period stone from Thanjavur, it reads the letters, then the words, then the meaning, "
         "in Tamil and English. Stones like it record gifts to temples, lamps to burn forever, land and water."),
        ("On a Chola-period stone from Thanjavur, it reads the letters, the words, then the meaning. "
         "Stones like it record gifts to temples, lamps to burn forever, land and water.",
         "On a Chola-period stone from Thanjavur, it reads the letters, the words, then the meaning. "
         "Stones like it record gifts to temples, lamps to burn forever, land and water."),
    ],
    "c-22-close": [
        ("Ezhuthu. Let the stones speak again. Learn to read the stone. Help read the backlog.",
         "Ezhuthu. Let the stones speak again. Learn to read the stone. Help read the backlog."),
        ("Ezhuthu. Let the stones speak again. Help read the backlog.",
         "Ezhuthu. Let the stones speak again. Help read the backlog."),
    ],
}


def variants(sc):
    return TEXT_V2.get(sc["id"], [(sc["narration"], None)])


def ssml_for(sc, rate, breaks, voice_lang, body=None):
    s = L.build_ssml(sc, rate=rate, breaks=breaks, body=body)
    if voice_lang == "en-IN":
        for w in NATIVE_EN_IN:
            s = re.sub(rf'<phoneme alphabet="ipa" ph="[^"]*">({w}(?:\'s)?)</phoneme>', r"\1", s)
    return s


# reuse v1 caption chunking/wrapping so the captions read the same
sys.path.insert(0, str(L.VIDEO / "audio-tools"))
from synth_narration import chunks, wrap2, srt_ts  # noqa: E402


def time_chunks(cs, wav, d):
    sil = [((a + b) / 2, b - a) for a, b in L.silences(wav) if 0.05 < a and b < d - 0.05]
    total = sum(len(c) for c in cs)
    bounds, acc, used = [], 0, set()
    for c in cs[:-1]:
        acc += len(c)
        est = d * acc / total
        cand = [(abs(m - est), i, m) for i, (m, w) in enumerate(sil) if i not in used and abs(m - est) < 1.2]
        if cand:
            _, i, m = min(cand); used.add(i); bounds.append(m)
        else:
            bounds.append(est)
    edges = [0.0] + sorted(bounds) + [d]
    return list(zip(edges[:-1], edges[1:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("voice"); ap.add_argument("engine")
    ap.add_argument("--lang", default="en-US")
    ap.add_argument("--tag"); ap.add_argument("--final", action="store_true")
    ap.add_argument("--only", nargs="*", help="re-render only these scene ids; reuse the others from fit.json")
    a = ap.parse_args()
    tag = a.tag or f"{a.voice}-{a.engine}"
    D = L.OUT / "vo" / tag
    D.mkdir(parents=True, exist_ok=True)
    polly = L.polly_client()
    rows, ok = [], True
    prev = {r["id"]: r for r in json.loads((D / "fit.json").read_text())} if a.only else {}
    for sc in L.scenes():
        win = sc["vo_window_s"]
        if a.only and sc["id"] not in a.only:
            r = prev[sc["id"]]; rows.append(r); ok &= r["fits"]
            print(f"{sc['id']:26s} kept (dur {r['duration_s']:5.2f} margin {r['margin_s']:+.2f})")
            continue
        # calm first: every text variant at <= 100% before any variant at 105%
        tries = [(vi, tb, rb) for rb in (LADDER[:-1], LADDER[-1:]) for vi, tb in enumerate(variants(sc))]
        done = False
        for vi, (text, body), ladder in tries:
            for rate, br in ladder:
                ssml = ssml_for(sc, rate, br, a.lang, body)
                wav, mp3 = D / f"{sc['id']}.wav", D / f"{sc['id']}.polly.mp3"
                d = L.synth(polly, ssml, a.voice, a.engine, mp3, wav)
                if win - d >= L.MARGIN:
                    done = True; break
            if done:
                break
        fits = win - d >= L.MARGIN
        ok &= fits
        n = len(re.sub(r"<[^>]+>", "", ssml).split())
        rows.append({"id": sc["id"], "act": sc["act"], "scene_start_s": sc["start_s"], "scene_end_s": sc["end_s"],
                     "vo_in_s": sc["vo_in_s"], "vo_window_s": win, "vo_out_s": round(sc["vo_in_s"] + d, 3),
                     "offset_s": sc["vo_in_s"], "duration_s": round(d, 3), "margin_s": round(win - d, 3),
                     "fits": fits, "rate": rate, "sentence_breaks_ms": 350 if br else 0,
                     "wpm": round(60 * n / d, 1), "text": text, "variant": vi, "text_changed": text != sc["narration"],
                     "narration_v1": sc["narration"], "ssml": ssml,
                     "file": str(wav), "polly_mp3": str(mp3)})
        print(f"{sc['id']:26s} {rate:>4s} br={int(br)} dur {d:5.2f} win {win:5.2f} margin {win - d:+.2f} "
              f"{60 * n / d:5.1f} wpm v{vi} {'OK' if fits else 'OVER'}", flush=True)
    (D / "fit.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print("ALL FIT" if ok else "SOME OVER")
    if a.final:
        write_final(rows, a, tag, ok)
    return 0 if ok else 1


def write_final(rows, a, tag, ok):
    stem = np.zeros(int(L.TOTAL * L.SR), np.float32)
    srt, n, prev_end = [], 1, 0.0
    for r, sc in zip(rows, L.scenes()):
        x = L.pcm(r["file"])
        i0 = int(round(r["vo_in_s"] * L.SR)); stem[i0:i0 + len(x)] += x[: len(stem) - i0]
        cs = chunks(r["text"])
        cap = []
        for j, (c, (t0, t1)) in enumerate(zip(cs, time_chunks(cs, r["file"], r["duration_s"]))):
            s0 = r["vo_in_s"] + t0
            s1 = min(r["vo_in_s"] + t1 + (0.3 if j == len(cs) - 1 else 0.0), sc["end_s"] - 0.05)
            s0 = max(s0, prev_end); prev_end = s1
            srt.append(f"{n}\n{srt_ts(s0)} --> {srt_ts(s1)}\n{wrap2(c)}\n"); n += 1
            cap.append({"text": c, "start_s": round(s0, 3), "end_s": round(s1, 3)})
        r["captions"] = cap
    stem_path = L.OUT / "narration-v2.wav"
    # atomic replace: compile.sh may read these while we work
    tmp = stem_path.with_suffix(".tmp.wav")
    wf.write(tmp, L.SR, np.clip(stem, -1, 1).astype(np.float32)); tmp.replace(stem_path)
    cap_path = L.V2 / "captions-v2.srt"
    tmpc = cap_path.with_suffix(".tmp"); tmpc.write_text("\n".join(srt)); tmpc.replace(cap_path)
    aud = json.loads((L.OUT / "auditions" / "auditions.json").read_text())
    meta = {
        "generated": "2026-11-03",
        "tts": {"service": "Amazon Polly", "aws_profile": "heisenberg", "region": "us-east-1",
                "voice_id": a.voice, "engine": a.engine, "language": a.lang,
                "pacing": "per scene: longest text variant at the slowest of 90%+350ms breaks / 95%+breaks / 95% / 100% that "
                           "fits; 105% only if no variant fits at 100%",
                "format": "Polly mp3 24 kHz -> trimmed, loudnorm -18 LUFS / -1.5 dBTP, WAV 48 kHz mono 24-bit"},
        "text_changes": "Act 1 (a1-02..a1-06), a2-08 and c-22 rewritten per user direction 2026-11-03 "
                        "(Tamil significance, urgency, recovery); see scenes[].text vs narration_v1",
        "lexicon_ipa": L.LEXICON, "subs": L.SUBS,
        "fit_rule": f"duration <= vo_window_s - {L.MARGIN} s",
        "all_fit": ok, "stem": str(stem_path), "auditions": aud, "scenes": rows,
    }
    (L.V2 / "narration-v2.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print("wrote", stem_path, L.V2 / "narration-v2.json", L.V2 / "captions-v2.srt")


if __name__ == "__main__":
    sys.exit(main())
