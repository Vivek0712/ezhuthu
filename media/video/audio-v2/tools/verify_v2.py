"""Verify soundtrack-v2.wav: length, loudness, peaks, speech-over-bed per scene, bell transients, silence gaps.
Writes ezhuthu-video/audio-v2/check/verify.json; exits 1 if any check fails."""
import json, sys
import numpy as np
import scipy.io.wavfile as wf
import v2lib as L
from build_v2 import k_loud, DINGS, BIG_BELLS

O = L.OUT
sr, y = wf.read(O / "soundtrack-v2.wav")
y = y.astype(np.float64) / (2 ** 31 if y.dtype == np.int32 else 1)
pre = wf.read(O / "stems" / "premix.wav")[1].astype(np.float64)
vo = wf.read(O / "stems" / "vo.wav")[1].astype(np.float64)
bed = wf.read(O / "stems" / "bed.wav")[1].astype(np.float64)
punct = wf.read(O / "stems" / "punct.wav")[1].astype(np.float64)
gain = np.sqrt(np.mean(y[: len(pre)] ** 2) / np.mean(pre ** 2))
lo = L.loudness(O / "soundtrack-v2.wav")
res = {"samples": len(y), "sample_rate": sr, "channels": y.shape[1], "duration_s": len(y) / sr,
       "integrated_lufs": lo["I"], "lra_lu": lo["LRA"], "true_peak_dbtp": lo["TP"],
       "sample_peak_dbfs": round(20 * np.log10(np.abs(y).max()), 2), "loudnorm_gain_db": round(20 * np.log10(gain), 2)}
nj = json.loads((L.V2 / "narration-v2.json").read_text())
sc = []
for s in nj["scenes"]:
    i0, i1 = int(s["vo_in_s"] * sr), int(s["vo_out_s"] * sr)
    sp, bd = k_loud(vo[i0:i1] * gain), k_loud(bed[i0:i1] * gain)
    sc.append({"id": s["id"], "speech_lufs": round(sp, 1), "bed_lufs": round(bd, 1), "diff_lu": round(sp - bd, 1)})
res["scenes"] = sc
res["min_speech_over_bed_lu"] = min(r["diff_lu"] for r in sc)
bells = []
for t, *_ in DINGS + [(b[0],) for b in BIG_BELLS]:
    i0 = int(t * sr); seg = punct[i0:i0 + int(3 * sr)] * gain
    full = y[i0:i0 + int(0.5 * sr)]
    bells.append({"t": t, "bell_peak_dbfs": round(20 * np.log10(np.abs(seg).max() + 1e-12), 1),
                  "mix_peak_first_500ms_dbfs": round(20 * np.log10(np.abs(full).max() + 1e-12), 1)})
res["bells"] = bells
gaps = [(round(a, 2), round(b, 2)) for a, b in L.silences(O / "soundtrack-v2.wav", "-50dB", 1.5)]
res["silence_gaps_over_1_5s_at_-50dB"] = gaps
# speech gaps (VO only) longer than 1.5 s, for information: the bed fills them
res["vo_gaps_over_1_5s"] = [(round(a, 2), round(b, 2)) for a, b in L.silences(O / "stems" / "vo.wav", "-50dB", 1.5)]
checks = {
    "exact_180s": len(y) == 8640000 and sr == 48000 and y.shape[1] == 2,
    "lufs_-14_pm_0.5": abs(lo["I"] + 14) <= 0.5,
    "true_peak_below_-1": lo["TP"] < -1.0,
    "speech_12lu_over_bed": res["min_speech_over_bed_lu"] >= 12,
    "bells_below_-6dbfs": all(b["bell_peak_dbfs"] <= -6 for b in bells),
    "no_silence_gap_over_1_5s": not gaps,
}
checks = {k: bool(v) for k, v in checks.items()}
res["checks"] = checks
(O / "check" / "verify.json").write_text(json.dumps(res, indent=2))
print(json.dumps({k: v for k, v in res.items() if k not in ("scenes",)}, indent=1))
print("worst scenes:", sorted(sc, key=lambda r: r["diff_lu"])[:3])
sys.exit(0 if all(checks.values()) else 1)
