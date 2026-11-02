"""Audition Polly voices + probe SSML tag support per engine. Output -> ezhuthu-video/audio/audition/."""
import boto3, subprocess, pathlib, sys
OUT = pathlib.Path("/Users/vivekrajaps/tamil-script/ezhuthu-video/audio/audition"); OUT.mkdir(parents=True, exist_ok=True)
p = boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")
TESTS = {
 "t1": '<speak><prosody rate="95%">These temple walls are written in Tamil. The letters are fading.</prosody></speak>',
 "t2": '<speak>Meet <phoneme alphabet="ipa" ph="ˈeɻʊt̪ʊ">Ezhuthu</phoneme>. From <phoneme alphabet="ipa" ph="məd̪ʊˈɾaɪ">Madurai</phoneme> to <phoneme alphabet="ipa" ph="t̪ənˈdʒɑːʋuːɾ">Thanjavur</phoneme>.</speak>',
 "t3": '<speak>Meet <phoneme alphabet="ipa" ph="ˈɛɹʊθʊ">Ezhuthu</phoneme>. From <phoneme alphabet="ipa" ph="məˈdʊɹaɪ">Madurai</phoneme> to <phoneme alphabet="ipa" ph="tʌnˈdʒɑːvʊɹ">Thanjavur</phoneme>. Learn to <phoneme alphabet="ipa" ph="ɹiːd">read</phoneme> the stone.</speak>',
 "t4": '<speak>Meet <sub alias="Eh-roo-thoo">Ezhuthu</sub>. <sub alias="Mee-naak-shee">Meenakshi</sub>, <sub alias="Raa-ja-raa-ja">Rajaraja</sub>, <sub alias="Vat-teh-lut-too">Vatteluttu</sub>.</speak>',
}
VOICES = [("Kajal","neural"),("Kajal","generative"),("Arjun","generative"),("Kiara","generative"),("Brian","generative")]
def dur(f): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(f)]).strip())
for v,e in VOICES:
  for k,t in TESTS.items():
    f = OUT/f"{v}-{e}-{k}.mp3"
    try:
      r = p.synthesize_speech(Engine=e, VoiceId=v, TextType="ssml", Text=t, OutputFormat="mp3", SampleRate="24000")
      f.write_bytes(r["AudioStream"].read()); print(v,e,k,"OK",round(dur(f),2))
    except Exception as ex: print(v,e,k,"FAIL",str(ex)[:160])
