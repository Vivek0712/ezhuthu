"""Shared helpers for the Ezhuthu audio v2 pass (narration voice, ambience, mix).

Reads (never writes) media/video/storyboard.json. Binaries go to ezhuthu-video/audio-v2/.
"""
import json, pathlib, re, subprocess
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
V2 = HERE.parent                                   # media/video/audio-v2
VIDEO = V2.parent                                  # media/video
SB = VIDEO / "storyboard.json"
OUT = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2")
SR = 48000
TOTAL = 180.0
MARGIN = 0.30

# IPA lexicon (Tamil values, as anglicised by an Indian-English narrator). Polly honours <phoneme> on
# neural, long-form and generative engines (verified: a nonsense ph string changes the rendered audio).
LEXICON = {
    "Ezhuthu":     "ˈeɭʊt̪ːʊ",     # user pick 2026-11-03 (option 3, pron-options/opt3.mp3)
    "Madurai":     "ˈmʌd̪ʊɾaɪ",
    "Thanjavur":   "t̪ənˈdʒɑːʋuːɾ",
    "Meenakshi":   "miːˈnɑːkʃi",
    "Rajaraja":    "ˈɾɑːdʒəˌɾɑːdʒə",
    "Vatteluttu":  "ˈʋʌʈʈeɻʊt̪t̪ʊ",
    "Keeladi":     "ˈkiːɻəd̪i",
    "Uttiramerur": "ʊt̪t̪ɪɾəˈmeːɾuːɾ",
    "Chola":       "ˈtʃoːɻə",
}
SUBS = {"AgentCore": "Agent Core", "5-gram": "five-gram"}


def scenes():
    return json.loads(SB.read_text())


def plain_text(sc):
    """Spoken text of a scene from its storyboard SSML (keeps '65 percent' etc. as the storyboard voiced it)."""
    s = sc["narration_ssml"]
    s = re.sub(r"<sub alias=\"[^\"]*\">([^<]*)</sub>", r"\1", s)
    s = re.sub(r"<say-as[^>]*>([^<]*)</say-as>", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def build_ssml(sc, rate="90%", breaks=True, body=None):
    """Storyboard SSML (or a v2 spoken body) -> v2 SSML: one prosody rate, IPA phonemes, gentle sentence breaks."""
    s = sc["narration_ssml"] if body is None else f'<speak><prosody rate="95%">{body}</prosody></speak>'
    s = re.sub(r'<sub alias="[^"]*">(Ezhuthu)</sub>', r"\1", s)
    s = re.sub(r'<prosody rate="[^"]*">', f'<prosody rate="{rate}">', s)
    s = s.replace("Chola-period", "Chola period")
    alt = "|".join(LEXICON)
    s = re.sub(rf"\b({alt})('s)?\b",
               lambda m: f'<phoneme alphabet="ipa" ph="{LEXICON[m.group(1)]}{"z" if m.group(2) else ""}">{m.group(0)}</phoneme>', s)
    for word, alias in SUBS.items():
        s = re.sub(rf"(?<![\">]){re.escape(word)}\b(?!</sub>)", f'<sub alias="{alias}">{word}</sub>', s)
    s = s.replace("to read the stone", 'to <phoneme alphabet="ipa" ph="ɹiːd">read</phoneme> the stone')
    s = s.replace("Help read the", 'Help <phoneme alphabet="ipa" ph="ɹiːd">read</phoneme> the')
    if breaks:   # unhurried: a short breath between sentences (not after the final one)
        s = re.sub(r"([.!?])(['\"]?) (?=[A-Z<])", r'\1\2 <break time="350ms"/> ', s)
    return s


def run(*a):
    return subprocess.run([str(x) for x in a], check=True, capture_output=True, text=True)


def dur(f):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f).stdout)


def polly_client():
    import boto3
    return boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")


def synth(polly, ssml, voice, engine, mp3, wav, lufs=-18):
    r = polly.synthesize_speech(Engine=engine, VoiceId=voice, TextType="ssml", Text=ssml,
                                OutputFormat="mp3", SampleRate="24000")
    pathlib.Path(mp3).write_bytes(r["AudioStream"].read())
    af = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,"
          "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse,"
          f"loudnorm=I={lufs}:TP=-1.5:LRA=11")
    run("ffmpeg", "-y", "-v", "error", "-i", mp3, "-af", af, "-ar", SR, "-ac", 1, "-c:a", "pcm_s24le", wav)
    return dur(wav)


def pcm(f, sr=SR, ch=1):
    b = subprocess.run(["ffmpeg", "-v", "error", "-i", str(f), "-f", "f32le", "-ac", str(ch), "-ar", str(sr), "-"],
                       capture_output=True, check=True).stdout
    x = np.frombuffer(b, np.float32)
    return x.reshape(-1, ch) if ch > 1 else x


def loudness(f):
    """Integrated LUFS, true peak, LRA via ebur128."""
    e = subprocess.run(["ffmpeg", "-nostats", "-i", str(f), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    tail = e[e.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+|-inf)", tail).group(1).replace("-inf", "-120"))
    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak")}


def silences(f, noise="-38dB", d=0.12):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(f), "-af", f"silencedetect=noise={noise}:d={d}",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    return list(zip(st, en))


def f0_stats(x, sr=SR):
    """Crude autocorrelation pitch track (voiced frames): median F0 and semitone spread (prosodic liveliness)."""
    hop, win = int(0.01 * sr), int(0.04 * sr)
    f0 = []
    for i in range(0, len(x) - win, hop):
        fr = x[i:i + win] - x[i:i + win].mean()
        if np.sqrt(np.mean(fr ** 2)) < 0.02:
            continue
        ac = np.correlate(fr, fr, "full")[win - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.45 * ac[0]:
            f0.append(sr / k)
    f0 = np.array(f0)
    if len(f0) < 10:
        return 0, 0
    st = 12 * np.log2(f0 / np.median(f0))
    return float(np.median(f0)), float(np.percentile(st, 90) - np.percentile(st, 10))
