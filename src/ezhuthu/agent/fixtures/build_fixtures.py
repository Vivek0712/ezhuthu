"""Regenerate the synthetic fixtures in this directory: python src/ezhuthu/agent/fixtures/build_fixtures.py"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
import json
import unicodedata

N = lambda s: unicodedata.normalize("NFC", s)
URL = "https://example.invalid/ezhuthu-fixture/{}"  # synthetic: not a DHARMA edition
ins = {
 "FIXTURE_CHOLA_001": ("tfa-fixture-chola", "Chola", "Fixture Chola lamp grant A", "c. 11th century (fixture)", [
   "svasti śrī kōvirājakēcaripaṉmaṟku yāṇṭu irupattirāvatu",
   "tirumakaḷ pōlap perunilac celviyum tanakkē yurimai pūṇṭamai manakkoḷa",
   "tiruvaiyāṟṟu mahādēvarkku nantā viḷakku oṉṟukku vaitta āṭu toṇṇūṟu",
   "cantirātittavar celvatāka vaittēn ivai paṉmāhēcurar rakṣai"]),
 "FIXTURE_CHOLA_002": ("tfa-fixture-chola", "Chola", "Fixture Chola lamp grant B", "c. 11th century (fixture)", [
   "svasti śrī kōpparakēcaripaṉmaṟku yāṇṭu nālāvatu",
   "tañcāvūr uṭaiyār śrīrājarājīcuramuṭaiya mahādēvarkku",
   "nantā viḷakku iraṇṭukku vaitta pacu nāṟpatu",
   "cantirātittavar celvatāka ivai paṉmāhēcurar rakṣai"]),
 "FIXTURE_PALLAVA_001": ("tfa-fixture-pallava", "Pallava", "Fixture Pallava assembly resolution", "c. 9th century (fixture)", [
   "svasti śrī kōvicaiya nantivikkiramaparumaṟku yāṇṭu irupattirāṇṭāvatu",
   "uttaramēru caturvētimaṅkalattu sabhaiyōm",
   "ivvāṇṭu mutal ūr vāriyam ceyvārai kuṭavōlai yiṭṭu"]),
 "FIXTURE_PANDYA_001": ("tfa-fixture-pandya", "Pandya", "Fixture Pandya lamp grant", "c. 8th century (fixture)", [
   "svasti śrī kōmāṟañcaṭaiyaṟku yāṇṭu mūṉṟāvatu",
   "tirupparaṅkuṉṟattu mahādēvarkku nantā viḷakku oṉṟu"]),
}
with open("corpus_lines.jsonl","w") as f:
  for iid,(col,dyn,title,date,lines) in ins.items():
    f.writelines(json.dumps({"inscription_id":iid,"collection":col,"dynasty":dyn,"line_n":str(i),"text":N(l),"split":"train","source_url":URL.format(iid)},ensure_ascii=False)+"\n" for i,l in enumerate(lines,1))
test_ins = {
 "FIXTURE_CHOLA_101": ("tfa-fixture-chola","Chola",False,"Fixture Chola test inscription","c. 11th century (fixture)"),
 "FIXTURE_PALLAVA_101": ("tfa-fixture-pallava","Pallava",True,"Fixture Pallava test inscription","c. 9th century (fixture)"),
}
items = [
 ("FIXTURE_CHOLA_101","1","svasti śrī kōvirājakēcari","paṉmaṟku"," yāṇṭu mūṉṟāvatu",False),
 ("FIXTURE_CHOLA_101","2","mahādēvarkku nantā viḷakku ","oṉṟukku"," vaitta āṭu toṇṇūṟu",False),
 ("FIXTURE_CHOLA_101","3","cantirātittavar ","celvatāka"," ivai paṉmāhēcurar rakṣai",False),
 ("FIXTURE_CHOLA_101","4","tirumakaḷ pōlap perunilac celviyum tanakkē yurimai ","pūṇṭamai"," manakkoḷa",False),
 ("FIXTURE_CHOLA_101","5","śrī rājēntiracōḻa ","tēvaṟku"," yāṇṭu",True),
 ("FIXTURE_CHOLA_101","6","ivai paṉmāhēcurar ","rakṣai","",False),
 ("FIXTURE_PALLAVA_101","1","uttaramēru caturvētimaṅkalattu ","sabhaiyōm","",False),
 ("FIXTURE_PALLAVA_101","2","kōvicaiya kampavarmaṟku yāṇṭu ","aiñcāvatu","",True),
]
with open("items.test.jsonl","w") as f:
  for iid,ln,l,t,r,hard in items:
    col,dyn,age,_,_ = test_ins[iid]
    f.write(json.dumps({"id":f"{iid}:{ln}:0","inscription_id":iid,"collection":col,"dynasty":dyn,"age_set":age,"split":"test","line_n":ln,"left":N(l),"right":N(r),"target":N(t),"gap_chars":len(N(t)),"hard":hard,"kind":"supplied","source_url":URL.format(iid)},ensure_ascii=False)+"\n")
with open("inscriptions.jsonl","w") as f:
  for iid,(col,dyn,title,date,lines) in ins.items():
    f.write(json.dumps({"id":iid,"collection":col,"dynasty":dyn,"title":title,"date_text":date,"source_url":URL.format(iid)},ensure_ascii=False)+"\n")
  for iid,(col,dyn,age,title,date) in test_ins.items():
    f.write(json.dumps({"id":iid,"collection":col,"dynasty":dyn,"title":title,"date_text":date,"source_url":URL.format(iid)},ensure_ascii=False)+"\n")
def e(kind, slug, label, ta=None, variants=(), era=None, dyn=None, att=()):
  return {"id":f"ez:{kind}/{slug}","kind":kind,"label_iso":N(label),"label_ta":ta,"variants":[N(v) for v in variants],"era":era,"dynasty":dyn,"broader":None,"wikidata":None,"attested_in":list(att)}
onto = [
 e("title","rajakesari","rājakēcari","இராஜகேசரி",["kōvirājakēcari","rājakēcaripaṉmaṉ"],"Chola","Chola",["FIXTURE_CHOLA_001"]),
 e("title","parakesari","parakēcari","பரகேசரி",["kōpparakēcari"],"Chola","Chola",["FIXTURE_CHOLA_002"]),
 e("ruler","nandivarman-iii","nantivikkiramaparumaṉ","நந்திவிக்கிரமபருமன்",["nantivikkiramaparumaṟku","kōvicaiya nantivikkiramaparumaṉ"],"Pallava","Pallava",["FIXTURE_PALLAVA_001"]),
 e("ruler","rajendra-chola-i","rājēntiracōḻatēvar","இராஜேந்திரசோழதேவர்",["rājēntiracōḻa"],"Chola","Chola",[]),
 e("place","uttaramerur","uttaramēru caturvētimaṅkalam","உத்தரமேரு சதுர்வேதிமங்கலம்",["uttaramēru caturvētimaṅkalattu"],None,"Pallava",["FIXTURE_PALLAVA_001"]),
 e("place","thanjavur","tañcāvūr","தஞ்சாவூர்",[],None,"Chola",["FIXTURE_CHOLA_002"]),
 e("temple","rajarajesvaram","śrīrājarājīcuram","ஸ்ரீராஜராஜீசுரம்",["śrīrājarājīcuramuṭaiya"],None,"Chola",["FIXTURE_CHOLA_002"]),
 e("grant_type","nanda-vilakku","nantā viḷakku","நந்தா விளக்கு",["nantāviḷakku"],None,None,["FIXTURE_CHOLA_001","FIXTURE_CHOLA_002","FIXTURE_PANDYA_001"]),
 e("formula","candradityavar","cantirātittavar celvatāka","சந்திராதித்தவர் செல்வதாக",["cantirātittavar"],None,None,["FIXTURE_CHOLA_001","FIXTURE_CHOLA_002"]),
 e("formula","paṉmahesvara-raksai","paṉmāhēcurar rakṣai","பன்மாஹேசுரர் ரக்ஷை",["paṉmāhēcurar"],None,None,["FIXTURE_CHOLA_001","FIXTURE_CHOLA_002"]),
 e("assembly","sabha","sabhaiyōm","சபையோம்",["sabhai"],None,None,["FIXTURE_PALLAVA_001"]),
 e("formula","tirumakal-pola","tirumakaḷ pōlap perunilac celviyum tanakkē yurimai pūṇṭamai manakkoḷa","திருமகள் போலப் பெருநிலச் செல்வியும் தனக்கே உரிமை பூண்டமை மனக்கொள",["tirumakaḷ pōla"],"Chola","Chola",["FIXTURE_CHOLA_001"]),
]
with open("ontology_stub.json", "w") as f:
    json.dump(onto, f, ensure_ascii=False, indent=1)
