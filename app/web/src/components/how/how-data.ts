// Real data for the /how-it-works explanation. Everything here is read from committed artefacts or copied from a
// committed report, with the source next to it. Nothing is invented for the page.
import slice from './ontology-slice.json';

// ---- Recorded restorations, copied from samples/recorded-restores.json (EzhuthuService.restore, deployed
// configuration, 2026-11-02) so the samples JSON stays out of the main bundle; how.test.tsx checks these against the
// file. The editors' readings are in samples/samples.json -> edition_reading. ----
export interface RecordedGap {
  sample: string;
  decision: 'fill' | 'abstain';
  top: {
    text: string;
    text_tamil: string;
    confidence: number;
    sources: string[];
    ngram_probability: number;
    ontology_hints: { id: string; kind: string; label: string }[];
  };
}
/** "Ūr iṭu vari-[?1]-pāṭum": filled with ப் (p) at 0.9628; editors read "p" (samples.json edition_reading). */
export const VARI: RecordedGap = {
  sample: 'tiruvavaduturai-taxes-paid-in-gold',
  decision: 'fill',
  top: {
    text: 'p',
    text_tamil: 'ப்',
    confidence: 0.9628,
    sources: ['ngram', 'parallel', 'sonnet'],
    ngram_probability: 0.9929,
    ontology_hints: [
      { id: 'ez:tax/vari', kind: 'measure', label: 'vari' },
      { id: 'ez:admin_unit/variyilitucozhacikamani-mandalam', kind: 'place', label: 'Variyiliṭu-cōḻa-cikāmaṇi-maṇṭalam' },
    ],
  },
};
/** "[?1]ṭaiyār": filled with உ (u) at 0.5988, proposed by the ontology among others; editors read "U". */
export const UTAIYAR: RecordedGap = {
  sample: 'tirunallaru-temple-office',
  decision: 'fill',
  top: {
    text: 'u',
    text_tamil: 'உ',
    confidence: 0.5988,
    sources: ['ngram', 'ontology', 'parallel', 'sonnet'],
    ngram_probability: 0.8878,
    ontology_hints: [{ id: 'ez:title/udaiyar', kind: 'title', label: 'uṭaiyār' }],
  },
};
/** The vari gap's best parallel (a train line): parallels[0] of the chosen candidate, cut around "vari-p-pāṭum". */
export const VARI_PARALLEL = { id: 'DHARMA_INSTiruvavatuturai10101', line: 'A.4', iso: 'sābhai y-iṭu vari-p-pāṭum ceṉṉīr-veṭṭiyum tiru-k-koṟṟa-vācalil' };

// ---- Home-hero runs (scripts/hero_read.py on the Thanjavur photo, 2026-11-02), copied here from
// hero/runs/read.json and hero/runs/interpret.json as committed at c33fc26, so a re-recorded hero does not change them. ----
/** read.json: routed Reader, script_guess chola-tamil, overall confidence 0.2, escalated to Opus; line 3. */
export const READER_EX = {
  line: { n: '3', text: 'paṇṇi ceyvā ku [?2]', text_tamil: 'பண்ணி செய்வா கு [?2]' },
  script_en: 'Chola-era Tamil',
  script_ta: 'சோழர் காலத் தமிழ்',
  confidence: 0.2,
  escalated: true,
};
/** interpret.json: the word குளம் (kuḷam) "tank / pond", attested in the train lexicon. */
export const INTERP_EX = { tamil: 'குளம்', iso: 'kuḷam', en: 'tank / pond', attested: true };

/** The hosted Strands Decider (strands-decider-2b-hobson-v19, choice-topk:3) on one VAL gap, from
 * eval/reports/2026-11-02-deployed-config/rows/val-routed-hosted-v19.jsonl, id DHARMA_INSTamilNadu00467:7:0:
 * target "niṉṟa", top1 "niṉṟa", confidence 0.4055, latency 13.3 s; the chosen configuration's row for the same gap
 * (rows/val-hybrid-prerank.jsonl) has top1 "niṉṟa" too. */
export const DECIDER_EX = { id: 'DHARMA_INSTamilNadu00467:7:0', text: 'niṉṟa', text_tamil: 'நின்ற', confidence: 0.4055, seconds: 13.3 };

// ---- Ontology slice (scripts/build_how_ontology_slice.py from ontology/ezhuthu.ttl, train-only build). ----
export interface SliceNode {
  id: string;
  kind: string;
  label_iso: string;
  label_ta: string | null;
  label_en: string | null;
  era: string | null;
  wikidata: string | null;
  inscriptions: number | null;
}
export interface SliceEdge {
  from: string;
  to: string;
  rel: 'memberOfDynasty' | 'praiseOf' | 'locatedAt' | 'sameStone';
  n?: number;
  evidence?: string[];
}
export const SLICE = slice as unknown as {
  center: string;
  nodes: SliceNode[];
  edges: SliceEdge[];
  counts: Record<string, number>;
  wikidata: Record<string, { with_qid: number; total: number }>;
  corpus: { inscriptions: number; lines: number; collections: number };
  owl: { classes: number; object_properties: number; named_individuals: number; triples: number };
};

// ---- Numbers copied from committed reports (each with its source). ----
export const NUMS = {
  // eval/reports/2026-11-02-deployed-config.md, "Calibration entries fitted for it (VAL only)".
  thrSonnet: 0.4111,
  thrOpus: 0.4887,
  // eval/reports/2026-11-02-deployed-config.md, TEST table: coverage 0.4988, selective acc. 0.9078 (187/206).
  testGaps: 413,
  coverage: 0.4988,
  selAcc: 0.9078,
  selK: 187,
  selN: 206,
  // eval/reports/2026-11-02-deployed-config.md, Headline "Cost and latency": 296 of 413 use Opus (291 + 5), $0.0060
  // per gap, latency p50 3.2 s.
  opusGaps: 296,
  opusPre: 291,
  opusAfter: 5,
  usdPerGap: '0.006',
  p50: 3.2,
  // eval/reports/2026-11-02-deployed-config.md, VAL stage 2: hosted v19 39 vs 41 of 120; 13 of 120 over 27 s.
  hostedN: 120,
  hostedMatches: 39,
  chosenMatches: 41,
  hostedSlow: 13,
  proxyLimitS: 27,
  // eval/reports/2026-11-02-deployed-config.md, "5-gram in the runtime": 14,355 train corpus lines; 11 ms per gap (p50).
  trainLines: 14355,
  ngramMs: 11,
  // ontology/README.md "Train split only" and ontology/coverage.json splits: 862 of 1,193 editions used.
  editionsUsed: 862,
  editionsTotal: 1193,
  // ontology/hint_eval.json held_out: test 16/253 (0.0632), val 16/345 (0.0464).
  hintTestHits: 16,
  hintTestN: 253,
  hintValHits: 16,
  hintValN: 345,
} as const;

/** "14,355" in English digits grouping (the app writes numbers with Western digits in both languages). */
export function grouped(n: number): string {
  return n.toLocaleString('en-US');
}
