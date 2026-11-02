"""One-off: apply fit-tightened narration (facts unchanged) to storyboard.json + STORYBOARD.md."""
import json, pathlib, re
V = pathlib.Path(__file__).resolve().parent.parent
R = '<speak><prosody rate="95%">{}</prosody></speak>'
NEW = {
 "a1-02-place": ("From Madurai to Thanjavur, kings carved their words in stone. Thanjavur's great temple has stood over a thousand years.", None),
 "a1-04-damage": ("Time wears the letters away. 65% of the 1,320 inscriptions we studied are damaged.",
                  "Time wears the letters away. 65 percent of the 1,320 inscriptions we studied are damaged."),
 "a1-05-few-readers": ("In 2021, India had about 23 epigraphists for nearly one lakh inscriptions.",
                  'In <say-as interpret-as="date" format="y">2021</say-as>, India had about 23 epigraphists for nearly one lakh inscriptions.'),
 "a3-12-under-the-hood": ("Six agents, built with Strands Agents, pass the stone along.", None),
 "a3-13-reader-restorer": ("The Reader turns photos into letters. The Restorer checks parallels and a 5-gram model, then asks Claude on Amazon Bedrock: Sonnet first, Opus when it matters.",
                  'The Reader turns photos into letters. The Restorer checks parallels and a <sub alias="five-gram">5-gram</sub> model, then asks Claude on Amazon Bedrock: Sonnet first, Opus when it matters.'),
 "a3-16-ontology": ("Agents look up kings, temples and formulas in a custom Tamil ontology over MCP.",
                  'Agents look up kings, temples and formulas in a custom Tamil ontology over <say-as interpret-as="characters">MCP</say-as>.'),
 "a3-17-finetuned": ("We fine-tuned Strands decision models for Tamil: train stones only, a pre-registered pick, one held-out test.", None),
 "a3-18-agentcore": ("The live app runs on Amazon Bedrock AgentCore, serverless, as code.", None),
 "a4-20-proof": ("On 413 held-out test gaps, 62.7% match the editors' restoration.",
                  "On 413 held-out test gaps, 62.7 percent match the editors' restoration."),
}
sb = json.loads((V/"storyboard.json").read_text()); md = (V/"STORYBOARD.md").read_text()
for s in sb:
    if s["id"] not in NEW: continue
    text, ssml = NEW[s["id"]]; old = s["narration"]; ow = s["narration_words"]
    s["narration"] = text; s["narration_ssml"] = R.format(ssml or text)
    w = len(text.split()); s["narration_words"] = w
    s["words_per_min"] = round(w / s["duration_s"] * 60); s["vo_wpm"] = round(w / s["vo_window_s"] * 60)
    md = md.replace(f"> {old}", f"> {text}")
    md = re.sub(rf"(### {re.escape(s['id'])} .*?\*\*Narration\*\* \()\d+ words(; VO in at [\d.]+ s, )\d+ wpm",
                lambda m: f"{m.group(1)}{w} words{m.group(2)}{s['vo_wpm']} wpm", md, count=1, flags=re.S)
tot = sum(s["narration_words"] for s in sb)
md = re.sub(r"Narration: \*\*\d+ words over 180 s\*\* \(about \d+ wpm average\)", f"Narration: **{tot} words over 180 s** (about {round(tot/3)} wpm average)", md)
(V/"storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n"); (V/"STORYBOARD.md").write_text(md)
print("total words", tot)
