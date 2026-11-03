"""Original 180.0 s score for the Ezhuthu film, synthesized from scratch (numpy additive synthesis, no samples).

Cue sheet (storyboard.json music_cue):
  M1 'stone'      0-14    tanpura-like drone on C#, room tone; soft rising pad from 8.6
  M2 'memory'    14-40    sparse plucked motif (72 bpm), cello-like swell 20-29, single held note 29-36,
                          held breath 36-39.8, reverse swell into 40.0
  M3 'apprentice' 40-90   main theme (Mohanam: C# D# E# G# A#), plucked + pad, soft pulse 84 bpm,
                          hand drum from 60, strings only from 80.5
  M4 'pipeline'  90-145   96 bpm build: synth pulse + mridangam-like percussion; layer 2 at 99.5, gate hit 110.4,
                          theme motif 117.5, shimmer 123, peak 130-139 with fill into 139, downbeat at 145.0,
                          silence 145.0-145.3
  M5 'people'   145.3-172 theme returns fuller and rising; low boom 160.6; highest chord 165 then back to drone
  M6 'resolve'   172-180  final phrase, lift, open drone note at 179.0, 1.0 s tail
SFX stem (separate file): chisel tap 2.4, four chimes 47.8-52.0, stone settles 74.5.

Writes (never into git): ezhuthu-video/audio/music.wav, sfx.wav, mix_preview.wav, mix_preview.mp3
"""
import pathlib, subprocess
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt
import scipy.io.wavfile as wf

SR = 48000
T = 180.0
N = int(T * SR)
OUT = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/audio")
rng = np.random.default_rng(1010)  # Thanjavur, 1010 CE

C3 = 49  # MIDI C#3 = Sa


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def buf():
    return np.zeros((N, 2), np.float32)


def place(dst, t0, sig, gain=1.0, pan=0.0):
    """Add mono or stereo sig at t0 seconds, constant-power pan in [-1, 1]."""
    i0 = int(round(t0 * SR))
    if i0 >= N:
        return
    if sig.ndim == 1:
        a = (pan + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], 1)
    j = min(N, i0 + len(sig))
    s0 = max(0, -i0)
    dst[max(i0, 0):j] += (gain * sig[s0:j - i0]).astype(np.float32)


def tt(d):
    return np.arange(int(d * SR)) / SR


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x, axis=0)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x, axis=0)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x, axis=0)


# ---------------------------------------------------------------- voices
def tanpura(f0, d=7.0):
    """Plucked drone string with jawari: higher partials bloom later, giving the sweeping buzz."""
    t = tt(d)
    s = np.zeros_like(t)
    nmax = int(min(40, 7000 / f0))
    for n in range(1, nmax + 1):
        tp = 0.12 + 0.045 * n
        bloom = (t / tp) * np.exp(1 - t / tp)
        env = np.exp(-t / (4.5 / (1 + 0.05 * n))) * (0.25 + 0.75 * bloom)
        f = n * f0 * (1 + 0.0004 * n) * (1 + 0.0015 * np.sin(2 * np.pi * 0.3 * t))
        s += (1 / n ** 0.85) * env * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    s *= 1 - np.exp(-t / 0.006)
    s[-int(0.3 * SR):] *= np.linspace(1, 0, int(0.3 * SR))
    return s / np.max(np.abs(s))


def pluck(f0, d=2.5, bright=0.6, glide=0.0, decay=1.4):
    """Veena-like pluck; glide = start offset in semitones that slides to pitch (a small gamaka)."""
    t = tt(d)
    bend = 2 ** ((glide * np.exp(-t / 0.07)) / 12)
    ph = 2 * np.pi * np.cumsum(f0 * bend) / SR
    s = np.zeros_like(t)
    for n in range(1, 16):
        if n * f0 > 9000:
            break
        a = (1 / n) * np.exp(-(n - 1) * (1.1 - bright))
        s += a * np.exp(-t * n ** 0.6 / decay) * np.sin(n * ph * (1 + 0.0007 * n))
    s *= 1 - np.exp(-t / 0.003)
    s[-int(0.05 * SR):] *= np.linspace(1, 0, int(0.05 * SR))
    return s


def pad(notes, d, att=1.5, rel=1.5, bright=0.35, voices=3, vib=0.15):
    """Warm detuned additive pad (string/choir-like), stereo."""
    t = tt(d)
    L = np.zeros_like(t); R = np.zeros_like(t)
    for m in notes:
        f0 = hz(m)
        for v in range(voices):
            det = (v - (voices - 1) / 2) * 0.006
            pan = (v / max(1, voices - 1)) * 2 - 1
            lfo = 1 + 0.002 * np.sin(2 * np.pi * (vib + 0.07 * v) * t + v)
            s = np.zeros_like(t)
            for n in range(1, 13):
                if n * f0 > 8000:
                    break
                s += (1 / n) * np.exp(-(n - 1) * (1 - bright) * 0.9) * np.sin(
                    2 * np.pi * n * f0 * (1 + det) * lfo * t + rng.uniform(0, 6.28))
            a = (pan * 0.6 + 1) * np.pi / 4
            L += s * np.cos(a); R += s * np.sin(a)
    env = np.minimum(1, t / att) * np.minimum(1, (d - t) / rel)
    env = np.clip(env, 0, 1) ** 1.5
    out = np.stack([L * env, R * env], 1)
    return out / (len(notes) * voices * 1.6)


def thom(gain=1.0):
    t = tt(0.9)
    f = 75 + 70 * np.exp(-t / 0.045)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.22)
    s += 0.3 * lp(rng.standard_normal(len(t)), 300) * np.exp(-t / 0.02)
    return gain * s


def nam(f0=hz(C3 + 12), gain=1.0, ring=0.45):
    """Right-head ringing stroke: near-harmonic partials of a loaded drum head."""
    t = tt(1.2)
    s = sum(a * np.exp(-t / (ring * dd)) * np.sin(2 * np.pi * f0 * k * t)
            for k, a, dd in [(1, 1, 1), (2, .55, .8), (3, .38, .6), (4, .22, .5), (5, .14, .4)])
    s += 0.5 * hp(rng.standard_normal(len(t)), 2500) * np.exp(-t / 0.004)
    return gain * s * 0.6


def kita(gain=1.0, f0=hz(C3 + 12)):
    t = tt(0.25)
    s = np.sin(2 * np.pi * f0 * 1.5 * t) * np.exp(-t / 0.035)
    s += 0.8 * bp(rng.standard_normal(len(t)), 1500, 6000) * np.exp(-t / 0.012)
    return gain * s * 0.45


def boom(f=42, d=2.2):
    t = tt(d)
    fr = f + 30 * np.exp(-t / 0.08)
    s = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.7)
    s += 0.4 * lp(rng.standard_normal(len(t)), 900) * np.exp(-t / 0.05)
    return s


def bass_pulse(f0, bright, d=0.5):
    t = tt(d)
    s = np.zeros_like(t)
    nh = 2 + int(bright * 14)
    for n in range(1, nh + 1):
        s += (1 / n) * np.sin(2 * np.pi * n * f0 * t) * np.exp(-t * (6 + 1.5 * n * (1 - bright)))
    s *= 1 - np.exp(-t / 0.004)
    s[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
    return s


def ramp(t, pts):
    xs, ys = zip(*pts)
    return float(np.interp(t, xs, ys))


# ---------------------------------------------------------------- score
SCALE_OK = {0, 2, 4, 7, 9}  # Mohanam degrees (C# D# E# G# A#)
CH = {  # chord voicings (MIDI)
    "I": [C3 - 12, C3, C3 + 4, C3 + 7, C3 + 14],
    "vi": [C3 - 3, C3 + 4, C3 + 9, C3 + 12, C3 + 16],
    "Vsus": [C3 - 5, C3 + 2, C3 + 7, C3 + 12],
    "I6": [C3 - 12, C3 + 4, C3 + 9, C3 + 12, C3 + 16],
    "Ihi": [C3, C3 + 7, C3 + 12, C3 + 16, C3 + 19, C3 + 24],
    "open": [C3 - 24, C3 - 12, C3 - 5, C3],
}
THEME_A = [(4, 1), (7, 1), (9, 2), (7, 1), (4, 1), (2, 2), (4, 1), (7, 1), (9, 1), (12, 1), (9, 2), (7, 2)]
THEME_B = [(12, 1), (14, 1), (12, 1), (9, 1), (7, 2), (4, 2), (2, 1), (4, 1), (7, 1), (4, 1), (2, 2), (0, 2)]
FINAL = [(7, 1), (9, 1), (12, 2), (9, 1), (7, 1), (4, 1), (2, 1)]


def melody(dst, t0, bpm, phrase, octave=12, gain=0.5, bright=0.6, pan=0.15, stacc=False):
    beat = 60 / bpm
    t = t0
    for i, (deg, b) in enumerate(phrase):
        f = hz(C3 + octave + deg)
        d = b * beat * (0.6 if stacc else 1.0) + 1.2
        g = 0.9 if i == 0 else 1.0
        place(dst, t + rng.normal(0, 0.004), pluck(f, d, bright, glide=(-1.0 if b >= 2 and i % 3 == 0 else 0.0)),
              gain * g, pan)
        t += b * beat
    return t


def score():
    mus = buf()

    # --- tanpura cycle (Pa, Sa', Sa', Sa) across the whole film, level follows the acts
    strings = {"Pa": tanpura(hz(C3 - 5)), "Sa1": tanpura(hz(C3)), "Sa1b": tanpura(hz(C3) * 1.0008),
               "Sa": tanpura(hz(C3 - 12))}
    lvl = [(0, .0), (0.4, .55), (14, .5), (20, .4), (40, .3), (90, .2), (130, .14), (144.7, .14), (144.71, 0),
           (145.3, 0), (145.31, .22), (165, .25), (168.5, .55), (172, .5), (178.8, .45), (180, .4)]
    t = 0.05
    while t < 179.0:
        for k, off, p in [("Pa", 0.0, -0.4), ("Sa1", 1.15, 0.3), ("Sa1b", 2.3, -0.1), ("Sa", 3.45, 0.1)]:
            tk = t + off + rng.normal(0, 0.01)
            if tk < 179.0 and not (144.6 < tk < 145.3):
                place(mus, tk, strings[k], 0.22 * ramp(tk, lvl), p)
        t += 5.2
    place(mus, 179.0, strings["Sa"], 0.24, 0)      # open drone note at 179.0
    place(mus, 179.02, strings["Pa"], 0.12, -0.3)

    # --- room tone (M1), very low filtered noise
    rt = lp(rng.standard_normal((int(16 * SR), 2)), 400) * 0.012
    rt *= np.clip(np.minimum(tt(16) / 1.0, (16 - tt(16)) / 3), 0, 1)[:, None]
    place(mus, 0, rt)

    # --- M1 rising pad from 8.6
    place(mus, 8.6, pad([C3, C3 + 7, C3 + 12], 7.5, att=4.0, rel=2.5, bright=0.25), 0.55)

    # --- M2 'memory' 14-40: sparse plucked motif at 72 bpm
    beat = 60 / 72
    motif = [[(0, 12), (1, 7), (1.5, 9), (2, 7), (3, 4)], [(0, 7), (1, 4), (2, 2), (2.5, 4), (3, 0)]]
    for bar in range(5):  # 14.0 .. 30.6
        for b, deg in motif[bar % 2]:
            tb = 14.0 + (bar * 4 + b) * beat
            if tb < 29.0:
                place(mus, tb, pluck(hz(C3 + deg), 2.2, 0.45, decay=1.2), 0.32, 0.25 - 0.1 * (bar % 2))
    place(mus, 14.0, pad(CH["I"], 8.0, att=2.0, rel=2.5, bright=0.2), 0.35)
    # cello-like swell under the 65% ring
    cello = pad([C3 - 24, C3 - 17, C3 - 12], 9.5, att=4.0, rel=4.0, bright=0.55, voices=2, vib=0.25)
    place(mus, 20.0, cello, 0.9)
    # thin to one sustained note, then the held breath
    place(mus, 28.5, pad([C3 + 7], 8.2, att=1.5, rel=3.0, bright=0.2, voices=2), 0.45)
    place(mus, 35.5, pad([C3 - 12, C3], 4.6, att=1.5, rel=1.2, bright=0.1, voices=2), 0.3)
    # reverse swell into M3 at 40.0
    sw_d = 1.7
    tsw = tt(sw_d)
    sw = bp(rng.standard_normal((len(tsw), 2)), 300, 5000) * 0.08
    sw += pad(CH["I"], sw_d, att=0.01, rel=0.01, bright=0.6)[:, :] * 0.8
    sw *= ((tsw / sw_d) ** 3)[:, None]
    place(mus, 40.0 - sw_d, sw, 0.9)

    # --- M3 'apprentice' 40-90 at 84 bpm
    bpm3 = 84; b3 = 60 / bpm3; bar3 = 4 * b3
    prog = ["I", "vi", "Vsus", "I"]
    t = 40.0; k = 0
    while t < 80.5:
        d = min(2 * bar3, 80.5 - t) + 1.5
        place(mus, t, pad(CH[prog[k % 4]], d, att=1.0, rel=1.5, bright=0.3), 0.55)
        t += 2 * bar3; k += 1
    tm = melody(mus, 40.0 + 0.5 * b3, bpm3, THEME_A, gain=0.30)
    tm = melody(mus, tm, bpm3, THEME_B, gain=0.32)
    tm = melody(mus, tm, bpm3, THEME_A, octave=24, gain=0.24, bright=0.7)
    melody(mus, tm, bpm3, THEME_B[:6], gain=0.26)
    # soft pulse (heartbeat sub) on beats 1 and 3
    tb = 40.0
    while tb < 80.5:
        place(mus, tb, bass_pulse(hz(C3 - 24), 0.1, 0.6), 0.35)
        tb += 2 * b3
    # hand drum from 60: light nam/kita on off-beats
    tb = 60.0; i = 0
    while tb < 80.3:
        st = "n.k.n.kt"[i % 8]
        if st == "n":
            place(mus, tb, nam(gain=0.5, ring=0.3), 0.35, 0.2)
        elif st in "kt":
            place(mus, tb, kita(0.6), 0.3, -0.2)
        tb += b3 / 2; i += 1
    # 80.5-90: strings only, held chord into Act 3
    place(mus, 80.5, pad(CH["vi"], 4.6, att=1.2, rel=1.2, bright=0.25, vib=0.2), 0.6)
    place(mus, 84.5, pad(CH["Vsus"], 3.2, att=1.0, rel=1.2, bright=0.25, vib=0.2), 0.6)
    place(mus, 87.0, pad(CH["I"], 4.0, att=1.0, rel=1.4, bright=0.3, vib=0.2), 0.6)

    # --- M4 'pipeline' 90-145 at 96 bpm (88 beats: 145.0 is a downbeat)
    bpm4 = 96; b4 = 60 / bpm4; e4 = b4 / 2
    bass_notes = [C3 - 24, C3 - 24, C3 - 12, C3 - 24, C3 - 17, C3 - 24, C3 - 12, C3 - 17]
    bright_curve = [(90, .15), (110.4, .45), (130, .85), (139, 1.0), (145, .9)]
    amp_curve = [(90, .25), (99.5, .32), (110.4, .38), (130, .48), (139, .5), (145, .45)]
    t = 90.0; i = 0
    while t < 144.99:
        place(mus, t + rng.normal(0, 0.002), bass_pulse(hz(bass_notes[i % 8]), ramp(t, bright_curve)),
              ramp(t, amp_curve), 0.0)
        t += e4; i += 1
    pats = [(90.0, "T...T..."), (99.5, "T.ktn.kt"), (110.4, "D.ktn.kt"), (130.0, "D.ktnTkt"),
            (137.5, "FILL"), (139.0, "D.ktn.kt"), (142.5, "D...n.kt")]

    def stroke(ch, tb, vel):
        p = rng.normal(0, 0.005)
        if ch in "TD":
            place(mus, tb + p, thom(vel), 0.55, -0.05)
        if ch in "nD":
            place(mus, tb + p, nam(gain=vel), 0.5, 0.15)
        if ch in "kt":
            place(mus, tb + p, kita(vel * (0.8 if ch == "k" else 1.0)), 0.45, 0.25 if ch == "k" else -0.2)

    t = 90.0; i = 0
    while t < 144.99:
        name = [p for s0, p in pats if s0 <= t + 1e-6][-1]
        vel = 0.7 + 0.3 * ramp(t, [(90, 0), (139, 1)])
        if name == "FILL":
            # 16ths, crescendo into 139.0
            for j in range(2):
                tb = t + j * e4 / 2
                stroke("kt"[j] if t < 138.4 else "n", tb, vel * (0.6 + 0.4 * (tb - 137.5) / 1.5))
        else:
            ch = name[i % 8]
            if ch != ".":
                stroke(ch, t, vel * (1.1 if i % 8 == 0 else 1.0))
            if t >= 110.4 and i % 2 == 1:  # ghost 16th
                stroke("k", t + e4 / 2, vel * 0.35)
        t += e4; i += 1
    # pad for M4, darker, brighter towards the peak
    t = 90.0; k = 0
    prog4 = ["I", "vi", "Vsus", "I"]
    while t < 144.9:
        d = min(4 * 4 * b4, 145.0 - t)
        place(mus, t, pad(CH[prog4[k % 4]], d + 0.3, att=1.5, rel=0.4, bright=ramp(t, [(90, .15), (139, .5)])),
              ramp(t, [(90, .3), (139, .5)]))
        t += 4 * 4 * b4; k += 1
    # layer 2 swell at 99.5, gate hit at 110.4
    place(mus, 110.4, thom(1.4), 0.8); place(mus, 110.4, boom(48, 1.6), 0.5)
    place(mus, 110.4, hp(rng.standard_normal(int(0.6 * SR)), 1500) * np.exp(-tt(0.6) / 0.15) * 0.2, 0.6)
    # theme motif re-enters at 117.5 (technical: staccato, high)
    tm = melody(mus, 117.5, bpm4, THEME_A, octave=24, gain=0.2, bright=0.85, pan=-0.2, stacc=True)
    melody(mus, tm, bpm4, THEME_B, octave=24, gain=0.22, bright=0.85, pan=0.2, stacc=True)
    # shimmering high pad from 123
    sh = pad([C3 + 24, C3 + 31, C3 + 28, C3 + 36], 22.0, att=4.0, rel=0.3, bright=0.8, voices=3, vib=0.5)
    trem = 0.75 + 0.25 * np.sin(2 * np.pi * 6.0 * tt(22.0))
    place(mus, 123.0, sh * trem[:, None], 0.35)
    # downbeat stab at 145.0, gated so 145.0-145.3 is silent
    stab = pad(CH["I"], 0.24, att=0.005, rel=0.12, bright=0.8)
    place(mus, 145.0, stab, 0.9); place(mus, 145.0, thom(1.3)[: int(0.24 * SR)] * np.linspace(1, 0, int(0.24 * SR)), 0.6)

    # --- M5 'people' 145.3-172 at 84 bpm: theme returns fuller, rising
    t = 145.3; k = 0
    lv5 = [(145.3, .5), (160, .7), (165, .85), (167.5, .6), (169.5, 0)]
    prog5 = ["I", "vi", "Vsus", "I6"]
    while t < 165.0:
        d = min(2 * bar3, 165.0 - t) + 1.4
        place(mus, t, pad(CH[prog5[k % 4]], d, att=0.8 if k else 0.05, rel=1.4, bright=0.4 + 0.02 * k),
              ramp(t, lv5))
        t += 2 * bar3; k += 1
    place(mus, 165.0, pad(CH["Ihi"], 4.5, att=0.6, rel=3.0, bright=0.55, vib=0.2), 0.8)  # highest chord
    tm = melody(mus, 145.3, bpm3, THEME_A, gain=0.32, bright=0.7)
    melody(mus, tm, bpm3, THEME_B[:10], octave=24, gain=0.28, bright=0.75)
    tb = 145.3; i = 0
    while tb < 164.9:
        g = ramp(tb, [(145.3, .3), (164.9, .45)])
        place(mus, tb, bass_pulse(hz(C3 - 24 if i % 4 != 2 else C3 - 17), 0.3, 0.6), g)
        if i % 2 == 1:
            place(mus, tb, nam(gain=0.5, ring=0.35), 0.3 * g / 0.3, 0.2)
        tb += b3; i += 1
    place(mus, 160.6, boom(40, 2.5), 0.75)

    # --- M6 'resolve' 172-180: final phrase, lift, open drone at 179.0
    place(mus, 172.0, pad(CH["vi"], 2.9, att=1.0, rel=0.8, bright=0.4), 0.55)
    place(mus, 174.3, pad(CH["Vsus"], 2.3, att=0.6, rel=0.8, bright=0.5), 0.6)
    place(mus, 176.0, pad(CH["Ihi"], 3.6, att=0.8, rel=1.6, bright=0.6, vib=0.25), 0.7)   # the lift
    melody(mus, 172.6, 84, FINAL, octave=12, gain=0.32, bright=0.7)
    place(mus, 179.0, pad(CH["open"], 1.0, att=0.02, rel=0.95, bright=0.3), 0.6)

    return mus


def reverb(x, d=3.2, wet=0.28):
    t = tt(d)
    ir = rng.standard_normal((len(t), 2)) * np.exp(-t / (d / 6.5))[:, None]
    ir = lp(ir, 6000)
    ir[: int(0.012 * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2, 0))
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[:N] for c in range(2)], 1)
    return (1 - wet) * x + wet * y * 0.9


def sfx():
    s = buf()
    # chisel tap at 2.4 s: metallic ring + stone click
    t = tt(0.9)
    tap = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / dd) for f, a, dd in
              [(2380, .5, .12), (3910, .35, .07), (5620, .25, .05), (1210, .3, .2)])
    tap += 1.2 * bp(rng.standard_normal(len(t)), 800, 7000) * np.exp(-t / 0.006)
    place(s, 2.4, tap * 0.5, 1.0, 0.1)
    # four soft chimes on letter call-outs
    for tc, m in [(47.8, C3 + 36), (49.2, C3 + 40), (50.6, C3 + 43), (52.0, C3 + 45)]:
        tch = tt(2.0); f = hz(m)
        ch = sum(a * np.sin(2 * np.pi * f * r * tch) * np.exp(-tch / dd) for r, a, dd in
                 [(1, 1, .8), (2.76, .35, .3), (5.4, .15, .12)])
        place(s, tc, ch * (1 - np.exp(-tch / 0.002)) * 0.12, 1.0, 0.3)
    # stone settles at 74.5: low thud + grit
    t = tt(1.2)
    st = np.sin(2 * np.pi * np.cumsum(60 + 40 * np.exp(-t / 0.05)) / SR) * np.exp(-t / 0.18)
    st += 0.5 * bp(rng.standard_normal(len(t)), 200, 3000) * np.exp(-t / 0.08) * (1 + 0.5 * rng.standard_normal(len(t)))
    place(s, 74.5, st * 0.45)
    return reverb(s, 1.6, 0.25)


def norm_peak(x, db=-1.0):
    return x * (10 ** (db / 20) / (np.max(np.abs(x)) + 1e-9))


def write(path, x):
    x = np.clip(x, -1, 1)
    wf.write(path, SR, (x * 2147483647).astype(np.int32))  # 32-bit; ffmpeg converts to 24-bit below
    tmp = path.with_suffix(".tmp.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-c:a", "pcm_s24le", str(tmp)], check=True)
    tmp.replace(path)


def lufs(path):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    import re
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", out)
    p = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", out)
    return (float(i[-1]) if i else None, float(p[-1]) if p else None)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mus = score()
    # section balance: Act 3 (M4) and the M5 return are the loudest; Acts 1-2 sit lower under dense narration
    g = np.interp(np.arange(N) / SR, [0, 13.5, 14.5, 89.0, 90.0, 180.0], [1.35, 1.35, 0.62, 0.62, 1.0, 1.0])
    mus *= g[:, None].astype(np.float32)
    mus = reverb(mus, 3.2, 0.3)
    mus = np.tanh(mus * 1.2) / 1.2                   # gentle glue
    # silence window 145.0+0.24 .. 145.3 (reverb tail cut) and fade-out tail 179.0-180.0
    a, b = int(145.24 * SR), int(145.3 * SR)
    mus[a:b] = 0
    mus[int(145.18 * SR):a] *= np.linspace(1, 0, a - int(145.18 * SR))[:, None]
    tail = int(1.0 * SR); mus[-tail:] *= np.linspace(1, 0, tail)[:, None] ** 1.5
    fade_in = int(0.4 * SR); mus[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    mus = norm_peak(mus, -1.0)
    assert len(mus) == N
    write(OUT / "music.wav", mus)

    fx = norm_peak(sfx(), -3.0) * 0.6
    write(OUT / "sfx.wav", fx)

    # preview mix: narration stem + music ducked under VO + sfx
    sr, vo = wf.read(OUT / "narration_full.wav")
    vo = vo.astype(np.float32) / 32768.0
    vo = np.pad(vo, (0, max(0, N - len(vo))))[:N]
    env = np.abs(vo)
    k = int(0.05 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    active = (env > 0.01).astype(np.float32)
    # attack 150 ms, release 600 ms smoothing of the duck gate
    sm = np.convolve(active, np.ones(int(0.6 * SR)) / int(0.6 * SR), mode="same")
    duck = 1 - 0.68 * np.clip(sm * 1.6, 0, 1)                  # about -10 dB under VO
    mix = mus * 0.5 * duck[:, None] + fx * 0.7 + np.stack([vo, vo], 1) * 0.9
    mix = norm_peak(mix, -1.0)
    write(OUT / "mix_preview.wav", mix)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(OUT / "mix_preview.wav"), "-b:a", "192k",
                    str(OUT / "mix_preview.mp3")], check=True)
    for f in ["music.wav", "sfx.wav", "mix_preview.wav"]:
        print(f, "LUFS/peak", lufs(OUT / f))


if __name__ == "__main__":
    main()
