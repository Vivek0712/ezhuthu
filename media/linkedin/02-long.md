# LinkedIn: long post (winner D4v2, panel 118/125)

Arc: place -> problem -> apprentice -> pipeline on AWS (with the fine-tuned Strands decision model) -> who it helps
-> results -> honest limits. About 2,700 characters (LinkedIn limit 3,000). Fact IDs are below the post, not in it.

---

The great temple at Thanjavur has stood for over 1,000 years. Its walls, like temple walls across Tamil Nadu, are written in Tamil. Even Madurai is carved into the stones: 25 of the inscription editions I worked with name it, 23 of them in a Chola king's title, "who took Madurai".

But time wears letters away. Of 1,320 inscriptions in my corpus, 858 (65%) carry a gap or an editor's restoration. And in 2021, India had about 23 epigraphists; of nearly 1 lakh inscriptions found since 1886, only 30,000 to 35,000 had been deciphered and published.

So I built Ezhuthu (எழுத்து, "letter"), an apprenticeship tool for Tamil epigraphy.

What it does
- Practice: 1,469 Tamil-first drills from real inscriptions, five levels from modern Tamil back to Tamil-Brahmi letters
- Restore: proposes the worn-away letters, shows how sure it is, and abstains when it is not
- Reader and Interpreter: Tamil-script photo in; letters, words, today's Tamil and a plain meaning out
- Tutor: hints and history in Tamil first. When the AI is unsure, the lesson says so: experts are unsure here too

How it is built
- A Strands Graph runs every lesson; a Strands Swarm of Tutor and Assessor teaches inside it. Six specialist agents
- A custom Tamil-epigraphy ontology, 1,958 named entities (kings, places, temples, formulas), served to the agents over MCP
- Claude Sonnet 4.6 first, Claude Opus 4.6 when it matters, on Amazon Bedrock, with confidence calibrated on validation
- Runs on Amazon Bedrock AgentCore Runtime; 5 CDK stacks for data, auth, agent, API and web
- I also fine-tuned a 2B Strands decision model to pick the fill the editors chose: train split only, cross-fitted, pre-registered. One A100, 74 minutes, USD 2.26. Inside the restorer, on held-out test, it fills 57.6% of gaps and 92.0% of those match. The live app now ranks with it.

What it scores
On 413 held-out test gaps, scored once after every choice was locked on validation:
- 62.7% (259 of 413) match the editors' restoration
- When it commits, 90.8% match (187 of 206); the other half go to an expert review queue
- Copying the best parallel passage gets 47.2% on the same gaps; a classic character 5-gram model, 56.7%
- About $0.0060 per gap at list prices; 3.2 s per gap (p50)

Still hard: gaps of 4+ letters (19.6%), and it does not read Tamil-Brahmi from photos. Next: a learner pilot with AWS UG Madurai student volunteers.

Learn to read the stone. Help read the backlog.

Try it: https://ezhuthu.sparrowdecider.com
Code (public): https://github.com/Vivek0712/ezhuthu
Inscription texts: DHARMA project (ERC grant 809994), CC BY-SA 4.0.

#StrandsAgents #AmazonBedrock #AgentCore #Tamil #Epigraphy #DigitalHumanities #AIforGood

---

Fact trace: E5 (Thanjavur, over 1,000 years); P13 (25 editions with *matirai*, 23 in *matirai koṇṭa*, a Cōḻa
king's title); P6, P7 (1,320; 858, 65%); P1/E7 (The Federal, 3 Aug 2021); S2, P4, L9 (1,469 items, 5 levels;
Tamil-Brahmi level teaches letters from transliterated text); S4, S6, S7 (Reader: Tamil script only), S5, S8; T1, T2;
T4 (1,958 named individuals, MCP); T8, T13 (routing; Platt scaling fitted on VAL); T15, T16 (AgentCore, 5 stacks);
D1-D5, D7, A17 (2B LoRA continue-from, TRAIN only, 5-fold cross-fit, pre-registered, A100 74 min, USD 2.26; 57.6% /
92.0% on held-out TEST; the live app ranks with it, routed config not scored on TEST); A1, A7, A13; A4 (copy 0.4722), A3 (5-gram 0.5666); A11 (list prices, an
estimate); L1 (4+ letters 0.1961), L6; H6 (planned). Credits: FACTS "Credits". Put the hero photo credit (Richard
Mortel, CC BY 2.0) in the image alt text or first comment if the hero image is attached.
