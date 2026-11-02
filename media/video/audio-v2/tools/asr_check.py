"""Intelligibility proxy: run Amazon Transcribe streaming (en-IN and en-US) on WAV files and print the text.

Needs the `amazon-transcribe` package (run from a venv that has it). Usage: python asr_check.py LANG f1.wav ...
Credentials: AWS_PROFILE=heisenberg, region us-east-1. Nothing is stored server-side (streaming API).
"""
import asyncio, os, subprocess, sys
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler


class H(TranscriptResultStreamHandler):
    def __init__(self, s):
        super().__init__(s); self.parts = []

    async def handle_transcript_event(self, ev):
        for r in ev.transcript.results:
            if not r.is_partial and r.alternatives:
                self.parts.append(r.alternatives[0].transcript)


async def one(lang, f):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout + b"\0" * 32000
    c = TranscribeStreamingClient(region="us-east-1")
    st = await c.start_stream_transcription(language_code=lang, media_sample_rate_hz=16000, media_encoding="pcm")

    async def feed():
        for i in range(0, len(pcm), 8000):
            await st.input_stream.send_audio_event(audio_chunk=pcm[i:i + 8000])
            await asyncio.sleep(0.01)
        await st.input_stream.end_stream()
    h = H(st.output_stream)
    await asyncio.gather(feed(), h.handle_events())
    return " ".join(h.parts)


async def main():
    lang = sys.argv[1]
    for f in sys.argv[2:]:
        print(f"{os.path.basename(f)}\t{await one(lang, f)}", flush=True)

os.environ.setdefault("AWS_PROFILE", "heisenberg")
asyncio.run(main())
