import boto3, json
p = boto3.Session(profile_name="heisenberg", region_name="us-east-1").client("polly")
LEX={"Ezhuthu":"ˈeɻʊt̪t̪ʊ","Madurai":"ˈmʌd̪ʊɾaɪ","Thanjavur":"t̪ənˈdʒɑːʋuːɾ","Meenakshi":"miːˈnɑːkʃi","Rajaraja":"ˈɾɑːdʒəˌɾɑːdʒə","Vatteluttu":"ˈʋʌʈʈeɻʊt̪t̪ʊ"}
t="<speak>"+" . ".join(f'<phoneme alphabet="ipa" ph="{v}">{k}</phoneme>' for k,v in LEX.items())+"</speak>"
r=p.synthesize_speech(Engine="neural",VoiceId="Kajal",TextType="ssml",Text=t,OutputFormat="json",SpeechMarkTypes=["viseme","word"])
print(" ".join(("|"+x["value"]+":") if x["type"]=="word" else x["value"] for x in map(json.loads,r["AudioStream"].read().decode().splitlines())))
for st in (["word"],["sentence"]):
  try:
    r=p.synthesize_speech(Engine="generative",VoiceId="Arjun",TextType="ssml",Text='<speak><prosody rate="95%">These temple walls are written in Tamil. The letters are fading.</prosody></speak>',OutputFormat="json",SpeechMarkTypes=st)
    print(st, r["AudioStream"].read().decode()[:400])
  except Exception as ex: print(st,"FAIL",str(ex)[:150])
