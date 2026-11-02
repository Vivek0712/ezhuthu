"""Audition Polly voices on the opening two scenes (a1-01, a1-02) and measure them.

Writes ezhuthu-video/audio-v2/auditions/<voice>-<engine>.{s1,s2}.wav, an opening montage
<voice>-<engine>-opening.mp3 (both lines at their storyboard VO-in times), and auditions.json.
"""
import json, sys
import numpy as np
import v2lib as L

CANDS = [  # (voice, engine, rate)
    ("Arjun", "generative", "90%"),    # v1 voice (en-IN male), slowed
    ("Kajal", "generative", "90%"),    # en-IN female, generative
    ("Kiara", "generative", "90%"),    # en-IN female, generative
    ("Gregory", "long-form", "90%"),   # en-US male, long-form (built for narration)
    ("Arthur", "neural", "90%"),       # en-GB male, neural
    ("Matthew", "generative", "90%"),  # en-US male, generative
]
D = L.OUT / "auditions"


def main():
    D.mkdir(parents=True, exist_ok=True)
    polly = L.polly_client()
    sc = L.scenes()[:2]
    rows = []
    for voice, eng, rate in CANDS:
        tag = f"{voice}-{eng}"
        r = {"voice": voice, "engine": eng, "rate": rate, "scenes": []}
        mont = np.zeros(int(14.0 * L.SR), np.float32)
        words = secs = 0
        f0s, spreads = [], []
        for i, s in enumerate(sc, 1):
            ssml = L.build_ssml(s, rate=rate)
            wav, mp3 = D / f"{tag}.s{i}.wav", D / f"{tag}.s{i}.polly.mp3"
            d = L.synth(polly, ssml, voice, eng, mp3, wav)
            raw = L.loudness(mp3)
            x = L.pcm(wav)
            f0, sp = L.f0_stats(x)
            f0s.append(f0); spreads.append(sp)
            n = len(L.plain_text(s).split())
            words += n; secs += d
            pauses = [round(b - a, 2) for a, b in L.silences(wav, "-40dB", 0.15)]
            r["scenes"].append({"id": s["id"], "dur_s": round(d, 3), "window_s": s["vo_window_s"],
                                "margin_s": round(s["vo_window_s"] - d, 3), "words": n,
                                "wpm": round(60 * n / d, 1), "raw_lufs": raw["I"], "pauses_s": pauses,
                                "f0_hz": round(f0, 1), "f0_spread_st": round(sp, 2)})
            i0 = int(s["vo_in_s"] * L.SR); mont[i0:i0 + len(x)] += x[: len(mont) - i0]
        r["wpm"] = round(60 * words / secs, 1)
        r["f0_hz"] = round(float(np.mean(f0s)), 1)
        r["f0_spread_st"] = round(float(np.mean(spreads)), 2)
        r["fits"] = all(x["margin_s"] >= L.MARGIN for x in r["scenes"])
        import scipy.io.wavfile as wf
        tmp = D / f"{tag}-opening.wav"
        wf.write(tmp, L.SR, (np.clip(mont, -1, 1) * 32767).astype(np.int16))
        L.run("ffmpeg", "-y", "-v", "error", "-i", tmp, "-c:a", "libmp3lame", "-q:a", "2", D / f"{tag}-opening.mp3")
        tmp.unlink()
        rows.append(r)
        print(f"{tag:22s} wpm {r['wpm']:5.1f}  f0 {r['f0_hz']:5.1f} Hz  spread {r['f0_spread_st']:4.1f} st  "
              + "  ".join(f"{x['id'][:5]} {x['dur_s']:.2f}/{x['window_s']} pauses {x['pauses_s']}" for x in r["scenes"]))
    (D / "auditions.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    sys.exit(main())
