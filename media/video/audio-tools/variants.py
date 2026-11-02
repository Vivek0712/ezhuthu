import sys, json, pathlib, subprocess, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import synth_narration as S, boto3
p = boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")
V = json.loads(sys.stdin.read())
tmp = pathlib.Path(tempfile.mkdtemp(dir="/Users/vivekrajaps/tamil-script/ezhuthu-video/audio"))
for sid, (win, texts) in V.items():
  for t in texts:
    ssml = S.build_ssml({"narration_ssml": f'<speak><prosody rate="95%">{t}</prosody></speak>'})
    raw = tmp/"v.mp3"; wav = tmp/"v.wav"
    raw.write_bytes(p.synthesize_speech(Engine="generative",VoiceId="Arjun",TextType="ssml",Text=ssml,OutputFormat="mp3",SampleRate="24000")["AudioStream"].read())
    subprocess.run(["ffmpeg","-y","-v","error","-i",str(raw),"-af","silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse",str(wav)],check=True)
    d = S.dur(wav); print(f"{sid} {d:5.2f} need<={win-0.3:5.2f} {'OK ' if d<=win-0.3 else 'NO '} {t}")
import shutil; shutil.rmtree(tmp)
