import boto3, json, sys
p = boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")
def marks(v,e,t,types=("viseme","word")):
    r=p.synthesize_speech(Engine=e,VoiceId=v,TextType="ssml",Text=t,OutputFormat="json",SpeechMarkTypes=list(types))
    return [json.loads(l) for l in r["AudioStream"].read().decode().splitlines() if l.strip()]
W={"ipa_std":'<speak><phoneme alphabet="ipa" ph="ˈɛ.ɹʊ.θʊ">Ezhuthu</phoneme> . <phoneme alphabet="ipa" ph="ˈmʌ.ðʊ.ɹaɪ">Madurai</phoneme> . <phoneme alphabet="ipa" ph="ˈθʌn.dʒɑː.vuːɹ">Thanjavur</phoneme></speak>',
   "ipa_tam":'<speak><phoneme alphabet="ipa" ph="ˈeɻʊt̪ʊ">Ezhuthu</phoneme> . <phoneme alphabet="ipa" ph="t̪ənˈdʒɑːʋuːɾ">Thanjavur</phoneme></speak>',
   "plain":'<speak>Ezhuthu . Madurai . Thanjavur . Meenakshi . Rajaraja . Vatteluttu</speak>'}
for v,e in [("Arjun","generative"),("Kajal","neural")]:
  for k,t in W.items():
    try:
      m=marks(v,e,t); s=[]
      for x in m:
        s.append(("|"+x["value"]+":") if x["type"]=="word" else x["value"])
      print(v,e,k," ".join(s))
    except Exception as ex: print(v,e,k,"FAIL",str(ex)[:150])
import subprocess
def d(f): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]))
for rate in ["100%","90%"]:
  t=f'<speak><prosody rate="{rate}">These temple walls are written in Tamil. The letters are fading.</prosody></speak>'
  r=p.synthesize_speech(Engine="generative",VoiceId="Arjun",TextType="ssml",Text=t,OutputFormat="mp3"); open("/tmp/x.mp3","wb").write(r["AudioStream"].read()); print("Arjun gen rate",rate,d("/tmp/x.mp3"))
