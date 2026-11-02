"""Pre-mix for the Ezhuthu film: narration over the original score, music ducked ~12 dB under the voice.

Reads float WAVs decoded by ffmpeg (compile.sh does the decoding, so any stem bit depth works):
  narration (mono), music (stereo), sfx (stereo), all 48 kHz.
Steps:
  1. Gain-stage each stem to a target integrated loudness measured by compile.sh (passed in as dB gains).
  2. Voice-activity envelope from the narration (20 ms RMS above -45 dBFS, 150 ms look-ahead so the music dips
     before the first syllable), smoothed with 120 ms attack / 600 ms release.
  3. Music gain = 0 dB in the clear, -DUCK dB under the voice.
  4. Sum, write a 32-bit float premix. Loudness normalisation (two-pass loudnorm) is done by compile.sh.

Usage: python3 mix_audio.py NARR.f32.wav MUSIC.f32.wav SFX.f32.wav OUT.wav GAIN_N GAIN_M GAIN_S DUCK_DB [SAMPLES]
"""
import sys

import numpy as np
import scipy.io.wavfile as wf

SR = 48000


def load(p, ch):
    sr, x = wf.read(p)
    assert sr == SR, (p, sr)
    x = x.astype(np.float32)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] != ch:
        x = np.repeat(x[:, :1], ch, axis=1) if ch == 2 else x.mean(axis=1, keepdims=True)
    return x


def fit(x, n):
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros((n - len(x), x.shape[1]), np.float32)])


def main(narr_p, music_p, sfx_p, out_p, gn, gm, gs, duck_db, samples=None):
    gn, gm, gs, duck_db = float(gn), float(gm), float(gs), float(duck_db)
    narr, music, sfx = load(narr_p, 1), load(music_p, 2), load(sfx_p, 2) if sfx_p != "-" else None
    n = int(samples) if samples else len(music)
    narr, music = fit(narr, n), fit(music, n)
    narr *= 10 ** (gn / 20)
    music *= 10 ** (gm / 20)

    # voice activity at 10 ms blocks
    blk = SR // 100
    nb = n // blk + 1
    v = np.zeros(nb * blk, np.float32)
    v[:n] = narr[:, 0]
    rms = np.sqrt((v.reshape(nb, blk) ** 2).mean(axis=1) + 1e-12)
    active = (20 * np.log10(rms) > -45).astype(np.float32)
    # bridge gaps shorter than 350 ms so the music does not pump between words
    idx = np.flatnonzero(active)
    for a, b in zip(idx[:-1], idx[1:]):
        if 1 < b - a <= 35:
            active[a:b] = 1
    # 150 ms look-ahead
    look = 15
    active = np.maximum(active, np.concatenate([active[look:], np.zeros(look, np.float32)]))
    # smooth at block rate: attack 120 ms (12 blocks), release 600 ms (60 blocks)
    a = np.exp(-1.0 / 12.0)
    r = np.exp(-1.0 / 60.0)
    env = np.empty_like(active)
    y = 0.0
    for i, t in enumerate(active):
        c = a if t > y else r
        y = c * y + (1 - c) * t
        env[i] = y
    gain_db = -duck_db * env
    g = np.repeat(10 ** (gain_db / 20), blk)[:n].astype(np.float32)
    # interpolate block steps to avoid zipper noise
    k = np.ones(blk, np.float32) / blk
    g = np.convolve(g, k, mode="same").astype(np.float32)
    music *= g[:, None]

    mix = music + narr  # mono narration to both channels
    if sfx is not None:
        sfx = fit(sfx, n) * 10 ** (gs / 20)
        mix += sfx
    wf.write(out_p, SR, mix.astype(np.float32))
    under = gain_db[active > 0.5]
    print(f"premix {n / SR:.3f} s; voice active {active.mean() * 100:.0f}% of blocks; "
          f"music gain under voice: median {np.median(under):.1f} dB")


if __name__ == "__main__":
    main(*sys.argv[1:])
