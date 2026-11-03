# part-3: form fields

Title (105 chars):
Fine-Tuning a 2B Strands Decision Model for Tamil Epigraphy for USD 2.26, and Keeping Every Number Honest

Description (456 chars):
How I taught a Strands decision model to choose the way the editors of Tamil temple inscriptions chose, and how I evaluated it. Training rows from the train split only, cross-fitted by stone, near-duplicates scrubbed, eight variants compared on validation under a pre-registered rule, and the test set scored once. The fine-tuned 2B model is tested on held-out inscriptions and not yet live: 92.0% of the fills it commits to match the editors' restoration.

Tags: ["strands-agents", "fine-tuning", "evaluation", "machine-learning", "amazon-bedrock"]
Series: Ezhuthu: an apprenticeship in Tamil epigraphy, part 3
Cover image: blog/img/p3-00-cover.png [1200x675 PNG, 277 KB] (1200x675 png/jpg/webp, <= 2 MB, no text)

Figures, in body order. Each < FIGURE n of N > marker in the body is replaced by the upload; the
Alt text line under it goes into the image's alt field; the italic line after it is the caption.
  1. blog/img/p3-01-decider-effort.png  [1600x1010 PNG, 219 KB]  (under "(top)")
  2. blog/img/p3-02-splits.png  [1600x980 PNG, 231 KB]  (under "The benchmark: expert restorations, split by inscription")
  3. blog/img/p3-03-leaderboard.png  [1600x740 PNG, 117 KB]  (under "Choosing the deployed pipeline on validation, then scoring test once")
  4. blog/img/p3-04-reliability.png  [1600x1010 PNG, 161 KB]  (under "Calibration and abstention")
  5. blog/img/p3-05-finetuned-decider.png  [1600x980 PNG, 217 KB]  (under "What the fine-tuned model does on held-out test")
