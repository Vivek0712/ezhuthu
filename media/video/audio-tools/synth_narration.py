"""Synthesize per-scene narration with Amazon Polly (heisenberg, us-east-1), fit-check each scene
against its VO window, and write narration.json + captions.srt + a 180 s narration stem.

Usage: python3 synth_narration.py [--only ID ...] [--no-synth]
Binaries go to /Users/vivekrajaps/tamil-script/ezhuthu-video/audio/ (never git).
"""
import argparse, json, pathlib, re, subprocess, sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
VIDEO = HERE.parent                                   # media/video
SB = VIDEO / "storyboard.json"
AUD = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/audio")
VO = AUD / "vo"
SR = 48000
TOTAL = 180.0
MARGIN = 0.30          # required headroom inside each scene's VO window (s)

VOICE = {"voice_id": "Arjun", "engine": "generative", "language": "en-IN", "rate": "95%"}

# Pronunciation lexicon (IPA, Tamil values). Validated on Polly's en-IN front end via viseme marks:
# Ezhuthu -> e r u t t u, Madurai -> m E t u t a, Thanjavur -> t @ t t S a f u t, Vatteluttu -> f E t t e r u t t u.
# zh (ழ) is the retroflex approximant ɻ; th in these words is the dental t̪ (not English "th").
LEXICON = {
    "Ezhuthu":    "ˈeɻʊt̪t̪ʊ",
    "Madurai":    "ˈmʌd̪ʊɾaɪ",
    "Thanjavur":  "t̪ənˈdʒɑːʋuːɾ",
    "Meenakshi":  "miːˈnɑːkʃi",
    "Rajaraja":   "ˈɾɑːdʒəˌɾɑːdʒə",
    "Vatteluttu": "ˈʋʌʈʈeɻʊt̪t̪ʊ",
}
SUBS = {"AgentCore": "Agent Core"}


def build_ssml(scene):
    """Start from the storyboard SSML, swap the old respellings for IPA phonemes."""
    s = scene["narration_ssml"]
    s = re.sub(r'<sub alias="[^"]*">(Ezhuthu)</sub>', r"\1", s)
    s = re.sub(r'<prosody rate="[^"]*">', f'<prosody rate="{VOICE["rate"]}">', s)
    for word, ipa in LEXICON.items():
        # possessive: Thanjavur's -> phoneme + z
        s = re.sub(rf"\b{word}'s\b", f'<phoneme alphabet="ipa" ph="{ipa}z">{word}\'s</phoneme>', s)
        s = re.sub(rf"(?<![\w\"]){word}\b(?!'|</phoneme>)", f'<phoneme alphabet="ipa" ph="{ipa}">{word}</phoneme>', s)
    for word, alias in SUBS.items():
        s = re.sub(rf"\b{word}\b", f'<sub alias="{alias}">{word}</sub>', s)
    # present-tense "read" in the tagline
    s = s.replace("to read the stone", 'to <phoneme alphabet="ipa" ph="ɹiːd">read</phoneme> the stone')
    s = s.replace("Help read the", 'Help <phoneme alphabet="ipa" ph="ɹiːd">read</phoneme> the')
    return s


def run(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True)


def dur(f):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)).stdout)


def synth(polly, scene, ssml):
    raw = VO / f"{scene['id']}.polly.mp3"
    wav = VO / f"{scene['id']}.wav"
    r = polly.synthesize_speech(Engine=VOICE["engine"], VoiceId=VOICE["voice_id"], TextType="ssml",
                                Text=ssml, OutputFormat="mp3", SampleRate="24000")
    raw.write_bytes(r["AudioStream"].read())
    # trim lead/tail silence (keep 40 ms), loudness-normalise to -18 LUFS / -1.5 dBTP, 48 kHz mono
    trim = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,"
            "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse,"
            "loudnorm=I=-18:TP=-1.5:LRA=11")
    run("ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", trim, "-ar", str(SR), "-ac", "1",
        "-c:a", "pcm_s24le", str(wav))
    return wav


def silences(wav, noise="-38dB", d=0.12):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=noise={noise}:d={d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(st, en))


def chunks(text, maxlen=84):
    """Caption chunks: sentences; a long sentence is split into balanced pieces at : ; , (else a space)."""
    import math
    sents = [x.strip() for x in re.split(r"(?<=[.!?])['\"]?\s+", text) if x.strip()]
    merged = []
    for x in sents:   # fold a very short sentence ("Ezhuthu.") into the next one
        if merged and len(merged[-1]) < 12 and len(merged[-1]) + len(x) < maxlen:
            merged[-1] = merged[-1] + " " + x
        else:
            merged.append(x)
    sents = merged
    out = []
    for s in sents:
        k = math.ceil(len(s) / maxlen)
        if k <= 1:
            out.append(s); continue
        cuts, prev = [], 0
        for i in range(1, k):
            tgt = len(s) * i / k
            punct = [m.end() for m in re.finditer(r"[:;,] ", s) if prev + 15 < m.end() < len(s) - 15]
            spaces = [m.end() for m in re.finditer(r" ", s) if prev + 15 < m.end() < len(s) - 15]
            near = [c for c in punct if abs(c - tgt) <= 22]
            c = min(near or spaces, key=lambda c: abs(c - tgt))
            cuts.append(c); prev = c
        edges = [0] + cuts + [len(s)]
        out += [s[a:b].strip() for a, b in zip(edges[:-1], edges[1:])]
    return out


def wrap2(s, width=42):
    if len(s) <= width:
        return s
    words, best = s.split(), None
    keep = {("Strands", "Agents"), ("Strands", "Graph"), ("Strands", "decision"), ("Amazon", "Bedrock"),
            ("held-out", "test"), ("Tamil", "ontology")}
    for i in range(1, len(words)):
        if (words[i - 1].strip(",:;."), words[i].strip(",:;.")) in keep:
            continue
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = max(len(a), len(b))
        if best is None or score < best[0]:
            best = (score, a + "\n" + b)
    return best[1]


def time_chunks(cs, wav, d):
    """Place chunk boundaries at the detected pauses nearest to the character-proportional estimate."""
    sil = [((a + b) / 2, b - a) for a, b in silences(wav) if 0.05 < a and b < d - 0.05]
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


def srt_ts(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--no-synth", action="store_true")
    a = ap.parse_args()
    VO.mkdir(parents=True, exist_ok=True)
    scenes = json.loads(SB.read_text())
    polly = None
    if not a.no_synth:
        import boto3
        polly = boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")

    rows, srt, n, ok = [], [], 1, True
    srt_prev_end = [0.0]
    stem = np.zeros(int(TOTAL * SR), dtype=np.float32)
    for sc in scenes:
        ssml = build_ssml(sc)
        wav = VO / f"{sc['id']}.wav"
        if polly and (not a.only or sc["id"] in a.only):
            synth(polly, sc, ssml)
        d = dur(wav)
        vo_in, win = sc["vo_in_s"], sc["vo_window_s"]
        margin = round(win - d, 3)
        fits = margin >= MARGIN
        ok &= fits
        print(f"{sc['id']:26s} dur {d:5.2f}  window {win:5.2f}  margin {margin:+.2f}  {'OK' if fits else 'OVER'}")
        # place on the 180 s stem
        pcm = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1",
                                            "-ar", str(SR), "-"], capture_output=True, check=True).stdout, np.float32)
        i0 = int(round(vo_in * SR)); stem[i0:i0 + len(pcm)] += pcm[: len(stem) - i0]
        cs = chunks(sc["narration"])
        cap = []
        spans = time_chunks(cs, wav, d)
        for j, (c, (t0, t1)) in enumerate(zip(cs, spans)):
            s0 = vo_in + t0
            s1 = vo_in + t1 + (0.3 if j == len(cs) - 1 else 0.0)   # contiguous inside a scene, short hold at the end
            s1 = min(s1, sc["end_s"] - 0.05)
            if srt_prev_end[0] > s0:
                s0 = srt_prev_end[0]
            srt_prev_end[0] = s1
            srt.append(f"{n}\n{srt_ts(s0)} --> {srt_ts(s1)}\n{wrap2(c)}\n"); n += 1
            cap.append({"text": c, "start_s": round(s0, 3), "end_s": round(s1, 3)})
        rows.append({
            "id": sc["id"], "act": sc["act"], "scene_start_s": sc["start_s"], "scene_end_s": sc["end_s"],
            "vo_in_s": vo_in, "vo_window_s": win, "vo_out_s": round(vo_in + d, 3), "duration_s": round(d, 3),
            "margin_s": margin, "fits": fits, "narration": sc["narration"], "ssml": ssml,
            "file": str(wav), "polly_mp3": str(VO / f"{sc['id']}.polly.mp3"), "captions": cap,
        })
    # captions must not overlap
    stem_path = AUD / "narration_full.wav"
    pk = float(np.max(np.abs(stem))) or 1.0
    import scipy.io.wavfile as wf
    wf.write(stem_path, SR, (np.clip(stem, -1, 1) * 32767).astype(np.int16))
    (VIDEO / "captions.srt").write_text("\n".join(srt))
    meta = {
        "generated": "2026-11-03",
        "tts": {"service": "Amazon Polly", "aws_profile": "heisenberg", "region": "us-east-1", **VOICE,
                "format": "Polly mp3 24 kHz -> trimmed, loudnorm -18 LUFS / -1.5 dBTP, WAV 48 kHz mono 24-bit"},
        "audition": AUDITION,
        "lexicon_ipa": LEXICON, "subs": SUBS,
        "fit_rule": f"duration <= vo_window_s - {MARGIN} s; vo_window_s ends 0.25 s before the scene cut",
        "all_fit": ok,
        "total_words": sum(len(r["narration"].split()) for r in rows),
        "stem": str(stem_path), "music": str(AUD / "music.wav"),
        "scenes": rows,
    }
    (VIDEO / "narration.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print("ALL FIT" if ok else "SOME SCENES OVER")
    return 0 if ok else 1


AUDITION = {
    "line": "These temple walls are written in Tamil. The letters are fading.",
    "files_dir": "/Users/vivekrajaps/tamil-script/ezhuthu-video/audio/audition",
    "candidates": [
        {"voice": "Kajal", "engine": "neural", "lang": "en-IN", "dur_s": 4.39,
         "note": "storyboard's original suggestion; clean but flatter read; female voice on a first-person 'So I built' line"},
        {"voice": "Arjun", "engine": "generative", "lang": "en-IN", "dur_s": 4.03,
         "note": "CHOSEN: warm, expressive generative read; Indian English carries Tamil place names natively; "
                 "male voice matches VOICE.md's first-person builder turn ('So I built an apprentice')"},
        {"voice": "Kiara", "engine": "generative", "lang": "en-IN", "dur_s": 4.06,
         "note": "expressive, brighter; good alternate for a female-voiced cut"},
    ],
    "also_probed": ["Kajal generative (4.10 s)", "Brian generative en-GB (4.25 s): loses the place grounding"],
    "pronunciation_check": "IPA phonemes verified via Polly viseme marks on the en-IN front end (generative "
                           "returns no speech marks). A Tamil speaker should still spot-check before final mix.",
}

if __name__ == "__main__":
    sys.exit(main())
