"""30 s social soundtrack: temple hand-bell dings + soft tanpura bed (both synthesized from code, no samples, no conch),
the narration lines from vo.json, bed ducked under the voice, two-pass loudnorm to -14 LUFS / TP <= -1.5 dBTP.

Usage: python3 audio.py            -> ezhuthu-video/social/audio/{bed.wav, vo.wav, mix.wav}, prints loudness
If the audio-v2 pass has published stems (ezhuthu-video/audio-v2/stems/{bell,tanpura}*.wav) they are NOT used:
the social bed is generated here so it can be cut to 30.000 s exactly; the timbre follows the same brief.
"""
import json, pathlib, re, subprocess
import numpy as np
import scipy.io.wavfile as wf

HERE = pathlib.Path(__file__).resolve().parent
SOCIAL = HERE.parent
OUT = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/social/audio")
SR = 48000
CUT = json.loads((SOCIAL / "social.json").read_text())
T = CUT["duration_s"]
N = int(round(T * SR))
rng = np.random.default_rng(7)
TONIC = 138.59  # C#3, same key as the film's drone


def bell(f0=1046.5, dur=6.5, amp=1.0):
    """Small brass temple hand-bell: inharmonic partials, fast strike, long shimmering decay, slight beating."""
    t = np.arange(int(dur * SR)) / SR
    parts = [(0.50, 0.55, 2.8), (1.00, 1.00, 2.4), (1.19, 0.35, 1.9), (1.56, 0.32, 1.5), (2.00, 0.45, 1.3),
             (2.51, 0.22, 0.9), (2.66, 0.25, 0.85), (3.36, 0.14, 0.6), (4.1, 0.10, 0.45), (5.4, 0.06, 0.3)]
    y = np.zeros_like(t)
    for r, a, tau in parts:
        f = f0 * r
        beat = 1 + 0.25 * np.sin(2 * np.pi * (0.9 + r * 0.3) * t)   # doublet beating = shimmer
        y += a * beat * np.exp(-t / tau) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    strike = rng.standard_normal(int(0.012 * SR)) * np.exp(-np.arange(int(0.012 * SR)) / (0.002 * SR))
    y[:len(strike)] += 0.35 * strike
    att = np.minimum(1, t / 0.002)
    return amp * y * att / np.max(np.abs(y))


def tanpura(dur):
    """Soft tanpura: Pa-Sa-Sa-Sa plucks every ~1.1 s, rich harmonics with a slowly moving 'jawari' formant."""
    n = int(dur * SR)
    out = np.zeros(n + SR * 8)
    pattern = [TONIC * 1.5 / 2, TONIC, TONIC, TONIC / 2]  # Pa (low), Sa, Sa, Sa (low)
    step = 1.1
    k = 0
    tt = 0.0
    while tt < dur + 1:
        f = pattern[k % 4]
        L = int(7.0 * SR)
        t = np.arange(L) / SR
        y = np.zeros(L)
        for h in range(1, 28):
            # jawari: harmonics bloom then fade at different rates (the buzzing 'life' of the string)
            env = np.exp(-t / (3.2 / (1 + 0.08 * h))) * (1 - np.exp(-t / (0.05 + 0.03 * h)))
            form = np.exp(-((h * f - (900 + 600 * np.sin(2 * np.pi * 0.15 * t + h))) / 700) ** 2)
            y += (0.5 / h + 0.25 * form) * env * np.sin(2 * np.pi * h * f * (1 + 0.0007 * np.sin(2 * np.pi * 0.3 * t)) * t)
        i0 = int(tt * SR)
        out[i0:i0 + L] += y * (0.8 if k % 4 == 0 else 1.0)
        k += 1
        tt += step
    out = out[:n]
    out /= np.max(np.abs(out))
    return out


def lowpass(x, fc):
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(4, fc, fs=SR, output="sos"), x)


def run(*a):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True)


def read(f):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True, check=True).stdout
    return np.frombuffer(b, np.float32).astype(np.float64)


def loud(f):
    e = subprocess.run(["ffmpeg", "-nostats", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    tail = e[e.rfind("Summary:"):]
    I = float(re.search(r"I:\s+(-?[\d.]+)", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+|-inf)", tail).group(1).replace("-inf", "-120"))
    lra = float(re.search(r"LRA:\s+(-?[\d.]+)", tail).group(1))
    return I, tp, lra


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vo = json.loads((SOCIAL / "vo.json").read_text())
    # ---- voice track
    V = np.zeros(N)
    for ln in vo["lines"]:
        x = read(ln["file"])
        i0 = int(round(ln["offset_s"] * SR))
        j0 = max(0, -i0)
        x = x[j0:]
        i0 = max(0, i0)
        m = min(len(x), N - i0)
        V[i0:i0 + m] += x[:m]
    # ---- bed: tanpura (stereo-ish via two detuned renders) + bells
    tp = lowpass(tanpura(T), 3500)
    tpR = np.roll(tp, int(0.013 * SR))
    fade = np.minimum(1, np.arange(N) / (1.2 * SR)) * np.minimum(1, (N - np.arange(N)) / (1.6 * SR))
    bedL = 0.22 * tp * fade
    bedR = 0.22 * tpR * fade
    bells = CUT["audio"]["bell_at_s"]
    for k, at in enumerate(bells):
        b = bell(f0=[1046.5, 1174.7, 1046.5][k % 3], amp=0.55 if k == 0 else 0.42)
        i0 = int(at * SR)
        m = min(len(b), N - i0)
        pan = [0.0, -0.25, 0.15][k % 3]
        bedL[i0:i0 + m] += b[:m] * (1 - pan) * 0.5
        bedR[i0:i0 + m] += b[:m] * (1 + pan) * 0.5
    # ---- duck the bed under the voice (envelope follower, 60 ms attack, 400 ms release)
    env = np.abs(V)
    win = int(0.03 * SR)
    env = np.convolve(env, np.ones(win) / win, mode="same")
    on = (env > 0.01).astype(float)
    g = np.zeros(N)
    a_att, a_rel = np.exp(-1 / (0.06 * SR)), np.exp(-1 / (0.40 * SR))
    s = 0.0
    for i in range(0, N, 48):  # block-wise for speed
        tgt = on[i]
        a = a_att if tgt > s else a_rel
        s = tgt + (s - tgt) * (a ** 48)
        g[i:i + 48] = s
    duck = 10 ** (CUT["audio"]["duck_db"] * g / 20)
    bedL *= duck
    bedR *= duck
    L = V + bedL
    R = V + bedR
    pre = OUT / "premix.wav"
    st = np.stack([L, R], 1)
    st /= max(1e-9, np.max(np.abs(st))) / 0.7
    wf.write(pre, SR, st.astype(np.float32))
    wf.write(OUT / "vo.wav", SR, (V / max(1e-9, np.max(np.abs(V))) * 0.7).astype(np.float32))
    wf.write(OUT / "bed.wav", SR, (np.stack([bedL, bedR], 1) * 0.7).astype(np.float32))
    # ---- two-pass loudnorm (linear) then a true-peak limiter safety
    tgt = CUT["audio"]["target"]
    e = subprocess.run(["ffmpeg", "-nostats", "-i", str(pre), "-af",
                        f"loudnorm=I={tgt['lufs']}:TP={tgt['tp_dbtp']}:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    j = e[e.rfind("{"):]
    m = json.loads(j[:j.find("}") + 1])
    af = (f"loudnorm=I={tgt['lufs']}:TP={tgt['tp_dbtp']}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          f"aresample=48000,atrim=0:{T},apad=whole_len={N}")
    mix = OUT / "mix.wav"
    run("ffmpeg", "-y", "-v", "error", "-i", pre, "-af", af, "-ar", SR, "-c:a", "pcm_s24le", mix)
    I, tpk, lra = loud(mix)
    d = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mix).stdout)
    print(f"mix.wav {d:.3f}s  I={I} LUFS  TP={tpk} dBTP  LRA={lra}")


if __name__ == "__main__":
    main()
