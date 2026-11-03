"""Build the v2 soundtrack stems and the pre-loudness premix (called by ../mix-v2.sh).

Layers (all 48 kHz stereo, exactly 180.000 s):
  vo      narration-v2.wav (Amazon Polly, synth_v2.py), centre
  amb     dawn birds (Tamil Nadu, CC BY 4.0), stream water as the Vaigai (CC0), distant Sama Veda chant (CC0),
          brass ghanta dings (CC0, single mallet strikes, tuned to C#6), a synthesized distant big temple bell
  music   original, synthesized here: tanpura-like drone on C# (additive, jawari bloom) + a soft Mohanam pad
  sfx     v1 film SFX stem (chisel tap 2.4 s, chimes 47.8-52 s, stone settles 74.5 s; synthesized, read-only)
          + four synthesized chisel taps at 156.05-157.2 s (TAPS: the build into the result)
Ducking: a speech-activity envelope from the VO (attack 60 ms, release 450 ms, hold 150 ms) pulls the bed down
13.5 dB under speech (dings and SFX 10 dB so they stay audible as punctuation).
No conch anywhere (user correction 2026-11-03).

Writes ezhuthu-video/audio-v2/stems/{vo,amb,music,sfx,bed,premix}.wav and check/levels.json.
"""
import json, sys
import numpy as np
from scipy.signal import butter, sosfiltfilt, sosfilt, fftconvolve, resample_poly, lfilter
import scipy.io.wavfile as wf
import v2lib as L

SR, T = L.SR, L.TOTAL
N = int(round(T * SR))                      # 8,640,000 samples
RAW, ST, CK = L.OUT / "raw", L.OUT / "stems", L.OUT / "check"
rng = np.random.default_rng(1010)
t_axis = np.arange(N) / SR
SA = 138.59  # C#3


def db(x):
    return 10 ** (x / 20)


def stereo(x):
    return np.stack([x, x], 1) if x.ndim == 1 else x


def bp(x, lo=None, hi=None, order=4):
    if lo:
        x = sosfiltfilt(butter(order, lo, "hp", fs=SR, output="sos"), x, axis=0)
    if hi:
        x = sosfiltfilt(butter(order, hi, "lp", fs=SR, output="sos"), x, axis=0)
    return x


def k_loud(x):
    """BS.1770 K-weighted loudness (ungated) of a stereo or mono block, LUFS."""
    x = stereo(x)
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1, -2, 1], [1, -1.99004745483398, 0.99007225036621]
    z = lfilter(b2, a2, lfilter(b1, a1, x, axis=0), axis=0)
    p = np.sum(np.mean(z ** 2, axis=0))
    return -0.691 + 10 * np.log10(p + 1e-20)


def norm_to(x, lufs):
    return x * db(lufs - k_loud(x))


def env(points):
    """Piecewise-linear dB envelope over the 180 s timeline: [(t, dB), ...] -> linear gain."""
    ts, ds = zip(*points)
    return db(np.interp(t_axis, ts, ds))[:, None]


def reverb_ir(sec=2.6, hf_damp=3.0, seed=7):
    r = np.random.default_rng(seed)
    n = int(sec * SR); tt = np.arange(n) / SR
    ir = np.zeros((n, 2))
    for c in range(2):
        noise = r.standard_normal(n)
        lo = sosfilt(butter(2, 1800, "lp", fs=SR, output="sos"), noise)
        ir[:, c] = (lo * np.exp(-tt * 6.9 / sec) + (noise - lo) * np.exp(-tt * 6.9 * hf_damp / sec))
    ir[: int(0.012 * SR)] = 0  # pre-delay
    return ir / np.sqrt(np.sum(ir ** 2, 0))


IR = reverb_ir()


def wet(x, mix=0.5):
    x = stereo(x)
    y = np.stack([fftconvolve(x[:, c], IR[:, c])[: len(x)] for c in range(2)], 1)
    return (1 - mix) * x + mix * y * (np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(y ** 2)) + 1e-12))


def loop_to(x, n, xfade=2.0):
    """Loop a stereo clip to n samples with equal-power crossfades."""
    x = stereo(x); f = int(xfade * SR)
    out = x.copy()
    while len(out) < n:
        a = np.sqrt(np.linspace(1, 0, f))[:, None]; b = np.sqrt(np.linspace(0, 1, f))[:, None]
        out = np.concatenate([out[:-f], out[-f:] * a + x[:f] * b, x[f:]])
    return out[:n]


def place(dst, t0, sig, gain=1.0):
    i0 = int(round(t0 * SR)); sig = stereo(sig)
    n = min(len(sig), len(dst) - i0)
    if n <= 0:
        return
    dst[i0:i0 + n] += sig[:n] * gain


def fade(x, fin=0.0, fout=0.0):
    x = x.copy()
    if fin:
        k = int(fin * SR); x[:k] *= np.linspace(0, 1, k)[:, None] if x.ndim == 2 else np.linspace(0, 1, k)
    if fout:
        k = int(fout * SR); x[-k:] *= np.linspace(1, 0, k)[:, None] ** 2 if x.ndim == 2 else np.linspace(1, 0, k) ** 2
    return x


# ---------------------------------------------------------------- ambience sources (licensed, see SOUND-CREDITS)
def src_birds():
    x = L.pcm(RAW / "birds.wav", ch=2).astype(np.float64)
    x = bp(x, 450, 5200, order=6)          # drop rumble and the 6-8 kHz insect band
    return norm_to(loop_to(x, N), -23)


def src_river():
    x = L.pcm(RAW / "river.wav", ch=2).astype(np.float64)
    x = bp(x, 120, 3500, order=4)          # up-close stream -> softer, more distant water
    return norm_to(loop_to(x, N, 3.0), -23)


def src_chant():
    x = L.pcm(RAW / "chant.ogg", ch=2).astype(np.float64)[int(60 * SR):int(60 * SR) + N]
    x = bp(x, 220, 2400, order=4)
    x = wet(x, 0.75)                      # far side of a stone courtyard
    return norm_to(x, -23)


def ghanta_hits():
    x = L.pcm(RAW / "ghanta.wav", ch=2).astype(np.float64)
    x = bp(x, 300, None, order=4)          # 50 Hz hum and mallet thump out
    hits = []
    for t0, t1 in [(1.72, 7.8), (7.82, 11.85), (24.82, 33.2), (33.22, 42.0)]:
        h = x[int(t0 * SR):int(t1 * SR)]
        h = resample_poly(h, 1000, 1093, axis=0)      # 1014 Hz -> ~1109 Hz (C#6), in tune with the drone
        h = fade(h, 0.004, min(2.5, len(h) / SR * 0.5))
        hits.append(h / np.max(np.abs(h)))
    return hits


def big_bell(dur=9.0, f=69.3 * 2):
    """Synthesized distant big temple bell on C#3: inharmonic bronze partials, slow beating, long hum."""
    tt = np.arange(int(dur * SR)) / SR
    parts = [(0.5, 1.0, 7.0), (1.0, 0.8, 5.0), (1.19, 0.55, 3.2), (1.5, 0.45, 2.6), (2.0, 0.35, 2.2),
             (2.52, 0.22, 1.5), (2.66, 0.18, 1.3), (3.01, 0.12, 1.0), (4.1, 0.07, 0.7)]
    y = np.zeros((len(tt), 2))
    for r, a, tau in parts:
        for c, det in enumerate((0.9993, 1.0007)):
            ph = rng.uniform(0, 2 * np.pi)
            y[:, c] += a * np.exp(-tt / tau) * np.sin(2 * np.pi * f * r * det * tt + ph) * (1 + 0.15 * np.sin(2 * np.pi * 0.7 * tt))
    y *= np.minimum(1, tt / 0.012)[:, None]
    y = bp(y, 50, 1800, order=2)          # distance: highs gone
    y = wet(y, 0.7)
    return y / np.max(np.abs(y))


# ---------------------------------------------------------------- original music (synthesized)
def tanpura():
    """Tanpura-like drone: Pa (G#2), Sa, Sa (C#3), low Sa (C#2); one pluck every 1.15 s, cycle 4.6 s."""
    def pluck(f, dur=7.0):
        tt = np.arange(int(dur * SR)) / SR
        y = np.zeros(len(tt))
        for k in range(1, 36):
            if f * k > 9000:
                break
            bloom = 1 + 2.2 * np.exp(-((tt - (0.25 + 0.06 * k)) / (0.5 + 0.03 * k)) ** 2) * (k > 3)   # jawari
            y += (1 / k ** 1.05) * bloom * np.exp(-tt / (3.2 / (1 + 0.04 * k))) * np.sin(2 * np.pi * f * k * tt + rng.uniform(0, 6.28))
        return y * np.minimum(1, tt / 0.006)
    strings = [SA * 1.5 / 2, SA, SA, SA / 2]   # Pa (G#2), Sa, Sa, low Sa
    pl = [pluck(f * rng.uniform(0.9995, 1.0005)) for f in strings]
    out = np.zeros((N + 8 * SR, 2))
    t, i = 0.0, 0
    while t < T:
        k = i % 4
        pan = [-0.35, 0.15, 0.3, -0.1][k]
        g = rng.uniform(0.85, 1.0)
        place(out, t, np.stack([pl[k] * (1 - pan) / 2 * 2, pl[k] * (1 + pan) / 2 * 2], 1), g)
        t += 1.15 + rng.uniform(-0.03, 0.03); i += 1
    out = bp(out[:N], 60, 6000, order=2)
    return wet(out, 0.35)


def pad():
    """Soft Mohanam pad (C# D# F G# A#): sustained Sa-Pa bed + a slow original line, warm sine stacks."""
    def tone(f, dur, att=1.2, rel=2.0, bright=0.25):
        tt = np.arange(int(dur * SR)) / SR
        vib = 1 + 0.003 * np.sin(2 * np.pi * 4.8 * tt) * np.minimum(1, tt / 1.5)
        y = sum((bright ** (k - 1)) * np.sin(2 * np.pi * f * k * np.cumsum(vib) / SR + rng.uniform(0, 6.28)) for k in range(1, 6))
        e = np.minimum(1, tt / att) * np.minimum(1, (dur - tt) / rel).clip(0)
        y = y * e
        return np.stack([y * 0.9, y], 1) if rng.random() < 0.5 else np.stack([y, y * 0.9], 1)
    out = np.zeros((N, 2))
    # bed chord, re-voiced per act
    for t0, t1, notes in [(36, 92, [SA, SA * 1.5]), (88, 147, [SA, SA * 1.5, SA * 2]),
                          (143, 174, [SA, SA * 1.5, SA * 1.26]), (170, 180, [SA, SA * 1.5, SA * 2])]:
        for f in notes:
            place(out, t0, tone(f, t1 - t0, 3.0, 4.0, 0.2), 0.5)
    # slow melodic line (scale degrees of C# Mohanam, octave 4), entering in Act 2, fuller in Act 3 and the close
    sc = {"S": SA * 2, "R": SA * 2 * 2 ** (2 / 12), "G": SA * 2 * 2 ** (4 / 12), "P": SA * 3, "D": SA * 2 * 2 ** (9 / 12),
          "S'": SA * 4}
    phrases = [(41.0, "G R S . P G R S"), (66.0, "P D S' D P G"), (92.0, "S R G P G R S"), (106.0, "G P D P G R G"),
               (120.0, "P D S' D P G R"), (133.0, "G P D S' D P"), (147.0, "S R G R S"), (172.6, "G P D S'")]
    for t0, ph in phrases:
        t = t0
        for n in ph.split():
            if n != ".":
                place(out, t, tone(sc[n], 3.2, 0.6, 1.8, 0.3), 0.32)
            t += 1.6
    return wet(bp(out, 90, 4000, order=2), 0.5)


# ---------------------------------------------------------------- envelopes (dB, relative to each layer's -23 LUFS)
ENV = {
    # Act 1 (0-40) ambience leads; Vaigai sunrise at the title (40-47); fades under product (47-90) and the
    # pipeline (90-145); returns for the people section and the close (165-180).
    "birds": [(0, -60), (0.4, 0), (36, 0), (40, -1), (47, -7), (56, -18), (70, -60), (150, -60), (162, -16),
              (168, -4), (178.5, -4), (180, -60)],
    "river": [(0, -60), (1.0, -8), (36, -8), (40, -4), (46, -4), (52, -14), (64, -60), (166, -60), (171, -9),
              (178.5, -9), (180, -60)],
    "chant": [(0, -60), (2.0, -7), (30, -7), (38, -16), (44, -60), (170, -60), (173, -15), (178, -15), (180, -60)],
    "tanpura": [(0, -60), (1.5, -11), (36, -9), (47, -8), (88, -8), (95, -4), (139, -3), (145, -6),
                (165, -6), (172, -3), (178.5, -3), (180, -60)],
    "pad": [(0, -60), (36, -60), (40, -12), (88, -11), (96, -6), (139, -5), (145, -9), (165, -9), (172, -4),
            (178.5, -4), (180, -60)],
}
DINGS = [(0.0, 0, -14), (40.0, 1, -13), (90.0, 2, -14), (145.0, 3, -14), (172.0, 0, -15)]   # (t, hit, peak dBFS pre-mix)
BIG_BELLS = [(13.45, -16), (178.6, -14)]
SFX_GAIN_DB = -2.0
# chisel taps that turn the 154.8-157.5 s narration gap into a build: the a4-20 dot field lights up on them
TAPS = [(156.05, -13), (156.45, -16), (156.85, -18), (157.2, -20)]   # (t, peak dBFS pre-mix)
DUCK_DB, DUCK_DB_PUNCT = 13.5, 10.0


def chisel_tap(seed=0):
    """Synthesized chisel on stone: a short metallic ring plus a band-limited click (original, no samples)."""
    r = np.random.default_rng(300 + seed)
    tt = np.arange(int(0.6 * SR)) / SR
    ring = sum(a * np.sin(2 * np.pi * f * (1 + 0.01 * seed) * tt) * np.exp(-tt / d) for f, a, d in
               ((2350, 1.0, 0.09), (3710, 0.6, 0.05), (5230, 0.35, 0.03), (1180, 0.4, 0.14)))
    click = bp(r.standard_normal(len(tt)), 900, 7000) * np.exp(-tt / 0.005) * 1.4
    x = ring * 0.6 + click
    x = x / np.abs(x).max()
    return wet(stereo(x), 0.25)


def speech_activity(vo):
    """0..1 envelope: VO frames above -45 dBFS RMS, hold 150 ms, attack 60 ms, release 450 ms."""
    hop = int(0.005 * SR)
    fr = np.sqrt(np.mean(vo[: len(vo) // hop * hop].reshape(-1, hop) ** 2, 1))
    act = (20 * np.log10(fr + 1e-9) > -45).astype(float)
    hold = int(0.15 / 0.005)
    act = np.convolve(act, np.ones(hold), "full")[: len(act)].clip(0, 1)
    a_up, a_dn = 1 - np.exp(-0.005 / 0.06), 1 - np.exp(-0.005 / 0.45)
    out, y = np.zeros_like(act), 0.0
    # look-ahead 40 ms so the bed starts dropping just before the first syllable
    act = np.concatenate([act[8:], np.zeros(8)])
    for i, v in enumerate(act):
        y += (a_up if v > y else a_dn) * (v - y); out[i] = y
    return np.interp(np.arange(N), np.arange(len(out)) * hop + hop / 2, out)


def limit(x, ceiling_db=-3.5, look=0.005, rel=0.08):
    """Transparent look-ahead peak limiter (only touches the rare speech peaks) so loudnorm can stay linear."""
    from scipy.ndimage import maximum_filter1d, minimum_filter1d, uniform_filter1d
    c = db(ceiling_db)
    pk = np.abs(x).max(1)
    w = int(look * SR) * 2 + 1
    req = np.minimum(1.0, c / np.maximum(maximum_filter1d(pk, w), 1e-9))
    req = minimum_filter1d(req, int(rel * SR))
    g = uniform_filter1d(req, w)
    g = np.minimum(g, minimum_filter1d(req, w))
    return x * g[:, None], float(20 * np.log10(g.min()))


def write(path, x):
    wf.write(path, SR, x.astype(np.float32))


def main():
    ST.mkdir(parents=True, exist_ok=True); CK.mkdir(parents=True, exist_ok=True)
    vo1 = L.pcm(L.OUT / "narration-v2.wav")[:N].astype(np.float64)
    vo1 = np.pad(vo1, (0, N - len(vo1)))
    vo1 = bp(vo1, 60, None, order=2)          # Polly output carries sub-60 Hz energy; voice f0 is ~86 Hz
    vo = stereo(vo1)
    layers = {"birds": src_birds(), "river": src_river(), "chant": src_chant(),
              "tanpura": norm_to(tanpura(), -23), "pad": norm_to(pad(), -23)}
    amb = sum(layers[k] * env(ENV[k]) for k in ("birds", "river", "chant"))
    music = sum(layers[k] * env(ENV[k]) for k in ("tanpura", "pad"))
    punct = np.zeros((N, 2))
    hits = ghanta_hits()
    for t, h, pk in DINGS:
        place(punct, t, hits[h], db(pk))
    bb = big_bell()
    for t, pk in BIG_BELLS:
        place(punct, t, fade(bb[: int((180 - t) * SR)], 0, min(1.2, 180 - t - 0.05)) if t > 170 else bb, db(pk))
    sfx = L.pcm("/Users/vivekrajaps/tamil-script/ezhuthu-video/audio/sfx.wav", ch=2).astype(np.float64)[:N]
    sfx = np.pad(sfx, ((0, N - len(sfx)), (0, 0))) * db(SFX_GAIN_DB)
    for i, (t, pk) in enumerate(TAPS):
        tap = chisel_tap(i)
        place(sfx, t, tap / np.abs(tap).max(), db(pk))
    act = speech_activity(vo1)[:, None]
    g_bed, g_punct = db(-DUCK_DB * act), db(-DUCK_DB_PUNCT * act)
    bed = (amb + music) * g_bed + (punct + sfx) * g_punct
    bed = bp(bed, 40, None, order=2)          # no sub-rumble under the voice
    premix, gr = limit(vo + bed)
    print(f"limiter max gain reduction {gr:.2f} dB")
    # fade the last 40 ms so the file ends on silence exactly at 180.000 s
    premix[-int(0.04 * SR):] *= np.linspace(1, 0, int(0.04 * SR))[:, None]
    for name, x in [("vo", vo), ("amb", amb * g_bed), ("music", music * g_bed), ("punct", punct * g_punct),
                    ("sfx", sfx * g_punct), ("bed", bed), ("premix", premix)]:
        write(ST / f"{name}.wav", x)
    # per-scene speech-vs-bed check (K-weighted), during VO only
    nj = json.loads((L.V2 / "narration-v2.json").read_text())
    rows = []
    for s in nj["scenes"]:
        i0, i1 = int(s["vo_in_s"] * SR), int(s["vo_out_s"] * SR)
        rows.append({"id": s["id"], "speech_lufs": round(k_loud(vo[i0:i1]), 2), "bed_lufs": round(k_loud(bed[i0:i1]), 2)})
        rows[-1]["speech_minus_bed_lu"] = round(rows[-1]["speech_lufs"] - rows[-1]["bed_lufs"], 2)
    (CK / "levels.json").write_text(json.dumps(rows, indent=2))
    worst = min(r["speech_minus_bed_lu"] for r in rows)
    print(f"premix peak {20 * np.log10(np.abs(premix).max()):.2f} dBFS; worst scene speech-bed {worst:.1f} LU")
    for r in rows:
        print(f"  {r['id']:26s} speech {r['speech_lufs']:6.1f}  bed {r['bed_lufs']:6.1f}  diff {r['speech_minus_bed_lu']:5.1f} LU")


if __name__ == "__main__":
    sys.exit(main())
