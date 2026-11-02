"""Synthesize the 30 s social narration (teaser + reel share one VO) with Amazon Polly, and time every word.

Usage:  python3 vo.py [--voice V --engine E --rate R --lang L] [--ezhuthu-ph IPA]
Default voice/engine/rate/phoneme: read from the sound team's choice
(ezhuthu-video/audio-v2/README.md + media/video/audio-v2/narration-v2.json) when present, else the CLI values.

Writes (binaries, never git):  ezhuthu-video/social/vo/line-<n>.wav  (48 kHz mono, -18 LUFS, raw Polly timing kept)
Writes (source, small):        media/social/vo.json  (voice, ssml per line, placement, per-word times on the 30 s clock)

Word timing: Polly speech marks when the engine supports them (neural, long-form); for the generative engine
(no word marks) Amazon Transcribe streaming word timestamps on the rendered audio; if that is unavailable, words
are spread over the detected speech runs by syllable weight (marked "approx" in vo.json).
"""
import argparse, json, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
SOCIAL = HERE.parent
OUT = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/social/vo")
SR = 48000
CUT = json.loads((SOCIAL / "social.json").read_text())

V2_TOOLS = SOCIAL.parent / "video" / "audio-v2" / "tools"
V2_DIR = SOCIAL.parent / "video" / "audio-v2"
V2_BIN = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2")


def run(*a, **k):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True, **k)


def dur(f):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f).stdout)


def sound_team_choice():
    """Voice settings the audio-v2 pass settled on, if it has finished (narration-v2.json)."""
    for f in (V2_DIR / "narration-v2.json", V2_BIN / "narration-v2.json"):
        if f.exists():
            d = json.loads(f.read_text())
            if isinstance(d, dict) and isinstance(d.get("tts"), dict):   # narration-v2.json layout (2026-11-03)
                tt = d["tts"]
                return {"voice": tt.get("voice_id"), "engine": tt.get("engine"), "lang": tt.get("language"),
                        "ezhuthu_ph": (d.get("lexicon_ipa") or {}).get("Ezhuthu")}
            meta = d.get("voice") if isinstance(d, dict) else None
            if isinstance(d, dict) and isinstance(meta, dict):
                return meta
            if isinstance(d, dict):
                return {k: d.get(k) for k in ("voice", "engine", "lang", "rate", "ezhuthu_ph") if k in d}
    return None


def ssml_line(text, rate, ph):
    lex = {
        "Ezhuthu": ph,
    }
    s = text
    for w, ipa in lex.items():
        s = re.sub(rf"\b{w}\b", f'<phoneme alphabet="ipa" ph="{ipa}">{w}</phoneme>', s)
    s = s.replace("read the stone", '<phoneme alphabet="ipa" ph="ɹiːd">read</phoneme> the stone')
    s = s.replace("2021", '<say-as interpret-as="date" format="y">2021</say-as>')
    return f'<speak><prosody rate="{rate}">{s}</prosody></speak>'


def polly():
    import boto3
    return boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")


def speech_marks(P, ssml, voice, engine):
    try:
        r = P.synthesize_speech(Engine=engine, VoiceId=voice, TextType="ssml", Text=ssml, OutputFormat="json",
                                SpeechMarkTypes=["word"])
    except Exception as e:  # generative: no word marks
        return None
    return [json.loads(l) for l in r["AudioStream"].read().decode().splitlines() if l.strip()]


def leading_silence(wav, thr_db=-45):
    e = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af",
                        f"silencedetect=noise={thr_db}dB:d=0.02", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"silence_start: (-?[\d.]+)\s.*?silence_end: ([\d.]+)", e, re.S)
    if m and float(m.group(1)) <= 0.01:
        return float(m.group(2))
    return 0.0


def speech_runs(wav, thr_db=-38, d=0.09):
    total = dur(wav)
    e = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav), "-af", f"silencedetect=noise={thr_db}dB:d={d}",
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    sil = list(zip(st, en + [total] * (len(st) - len(en))))
    runs, t = [], 0.0
    for a, b in sil:
        if a > t + 0.02:
            runs.append((t, a))
        t = max(t, b)
    if t < total - 0.02:
        runs.append((t, total))
    return runs


def syl(w):
    w = re.sub(r"[^a-z0-9]", "", w.lower())
    if w.isdigit():
        return {"2021": 5, "23": 3, "2000": 3}.get(w, len(w) + 1)
    return max(1, len(re.findall(r"[aeiouy]+", w)) - (1 if w.endswith("e") and len(w) > 3 else 0))


def approx_words(text, wav):
    words = text.split()
    runs = speech_runs(wav)
    tot = sum(b - a for a, b in runs)
    weights = [syl(w) for w in words]
    W = sum(weights)
    out, acc = [], 0.0
    # map cumulative weight onto cumulative speech time
    def at(x):
        x = x * tot
        for a, b in runs:
            if x <= (b - a):
                return a + x
            x -= (b - a)
        return runs[-1][1]
    for w, k in zip(words, weights):
        out.append({"w": w, "s": round(at(acc / W), 3), "e": round(at((acc + k) / W), 3)})
        acc += k
    return out


def transcribe_words(wav, lang):
    """Amazon Transcribe streaming word timestamps (needs amazon-transcribe; run with the social venv)."""
    try:
        import asyncio
        from amazon_transcribe.client import TranscribeStreamingClient
        from amazon_transcribe.handlers import TranscriptResultStreamHandler
    except ImportError:
        return None
    import os
    os.environ.setdefault("AWS_PROFILE", "heisenberg")
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout + b"\0" * 32000
    items = []

    class H(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, ev):
            for r in ev.transcript.results:
                if not r.is_partial and r.alternatives:
                    for it in r.alternatives[0].items:
                        if it.item_type == "pronunciation":
                            items.append({"w": it.content, "s": it.start_time, "e": it.end_time})

    async def go():
        c = TranscribeStreamingClient(region="us-east-1")
        st = await c.start_stream_transcription(language_code=lang, media_sample_rate_hz=16000, media_encoding="pcm")

        async def feed():
            for i in range(0, len(pcm), 8000):
                await st.input_stream.send_audio_event(audio_chunk=pcm[i:i + 8000])
                await asyncio.sleep(0.005)
            await st.input_stream.end_stream()
        await asyncio.gather(feed(), H(st.output_stream).handle_events())
    asyncio.run(go())
    return items


def align(text, items, wav):
    """Map script words onto ASR items in order (ASR may spell numbers/names differently): anchor by
    normalized match, interpolate the rest."""
    words = text.split()
    if not items:
        return approx_words(text, wav), "approx"
    norm = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())
    ap = approx_words(text, wav)
    anchors, j = {}, 0
    for i, w in enumerate(words):
        for k in range(j, min(j + 4, len(items))):
            if norm(items[k]["w"]) == norm(w) and norm(w):
                anchors[i] = items[k]; j = k + 1; break
    out = []
    for i, w in enumerate(words):
        if i in anchors:
            out.append({"w": w, "s": round(anchors[i]["s"], 3), "e": round(anchors[i]["e"], 3)})
        else:
            out.append(dict(ap[i]))
    # keep monotonic
    for i in range(1, len(out)):
        out[i]["s"] = max(out[i]["s"], out[i - 1]["s"] + 0.02)
        out[i]["e"] = max(out[i]["e"], out[i]["s"] + 0.05)
    return out, f"transcribe ({len(anchors)}/{len(words)} anchored)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice"); ap.add_argument("--engine"); ap.add_argument("--rate"); ap.add_argument("--lang")
    ap.add_argument("--ezhuthu-ph")
    a = ap.parse_args()
    ch = sound_team_choice() or {}
    vo = CUT["vo"]
    voice = a.voice or ch.get("voice") or vo["voice"]
    engine = a.engine or ch.get("engine") or vo["engine"]
    rate = a.rate or ch.get("rate") or vo["rate"]
    lang = a.lang or ch.get("lang") or vo.get("lang", "en-US")
    ph = a.ezhuthu_ph or ch.get("ezhuthu_ph") or vo["ezhuthu_ph"]
    OUT.mkdir(parents=True, exist_ok=True)
    P = polly()
    lines = []
    for i, ln in enumerate(vo["lines"]):
        ssml = ssml_line(ln["text"], rate, ph)
        mp3, wav = OUT / f"line-{i + 1}.polly.mp3", OUT / f"line-{i + 1}.wav"
        r = P.synthesize_speech(Engine=engine, VoiceId=voice, TextType="ssml", Text=ssml, OutputFormat="mp3",
                                SampleRate="24000")
        mp3.write_bytes(r["AudioStream"].read())
        run("ffmpeg", "-y", "-v", "error", "-i", mp3, "-af", "loudnorm=I=-18:TP=-2:LRA=11", "-ar", SR, "-ac", 1,
            "-c:a", "pcm_s24le", wav)
        lead = leading_silence(wav)
        d = dur(wav)
        marks = speech_marks(P, ssml, voice, engine)
        if marks:
            ws = [m for m in marks if m["type"] == "word"]
            words, src = [], "polly speech marks"
            for k, m in enumerate(ws):
                s = m["time"] / 1000
                e = ws[k + 1]["time"] / 1000 if k + 1 < len(ws) else None
                words.append({"w": m["value"], "s": round(s, 3), "e": round(e, 3) if e else None})
            # last word ends at the end of speech
            runs = speech_runs(wav)
            words[-1]["e"] = round(runs[-1][1] if runs else d, 3)
        else:
            words, src = align(ln["text"], transcribe_words(wav, lang), wav)
        runs = speech_runs(wav)
        speech_end = runs[-1][1] if runs else d
        # where the first phoneme lands on the 30 s clock: the cut-list time, pushed later if the previous
        # line would still be speaking (keeps >= 0.22 s breath between lines with any voice)
        at = max(ln["at"], (lines[-1]["end_s"] + 0.22) if lines else 0.0)
        offset = at - lead
        lines.append({"n": i + 1, "text": ln["text"], "ssml": ssml, "file": str(wav), "dur_s": round(d, 3),
                      "lead_s": round(lead, 3), "offset_s": round(offset, 3), "start_s": round(at, 3),
                      "end_s": round(offset + speech_end, 3), "timing": src,
                      "words": [{"w": w["w"], "s": round(offset + max(w["s"], lead), 3),
                                 "e": round(offset + (w["e"] if w["e"] else speech_end), 3)} for w in words]})
        print(f"line {i + 1}: {d:.2f}s lead {lead:.2f} speech {speech_end - lead:.2f}s  "
              f"{at:.2f}->{offset + speech_end:.2f}  [{src}]  {ln['text']}")
    res = {"voice": voice, "engine": engine, "rate": rate, "lang": lang, "ezhuthu_ph": ph,
           "chosen_by": "sound team (audio-v2)" if ch else "social default (audio-v2 not final yet)",
           "lines": lines}
    (SOCIAL / "vo.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    last = lines[-1]["end_s"]
    print(f"VO ends at {last:.2f}s; overlaps:",
          [(l["n"], round(lines[k + 1]["start_s"] - l["end_s"], 2)) for k, l in enumerate(lines[:-1])])


if __name__ == "__main__":
    main()
