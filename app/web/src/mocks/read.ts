import { http, HttpResponse, delay } from 'msw';
import type { Schemas } from '../api/client';
import { SAMPLE_IMAGES } from '../samples';

/**
 * Mock POST /api/read (contracts/restore-api.md), mirroring the server's rules (src/ezhuthu/agent/reader.py) so demo
 * screenshots show what the real reader shows, warnings included.
 *
 * The mock cannot read photos. A sample plate (recognised by its file name) gets Sonnet 4.6's real reading of that
 * plate (eval/reports/2026-11-02-ocr-app-samples.jsonl, TRAIN-split DHARMA lines, CC BY-SA 4.0). A sample picture from
 * the home gallery track (src/samples/sample-images.json) gets the edition text it was rendered from, with no
 * confidence (there is no measured reading of it), so the server's "unsure" rule applies. Any other image gets the
 * worn-stone reading. Warnings, escalation and the one-time "read again" token follow the server's rules. The mock
 * has no Opus reading: "read again" returns the first reading with escalation_skipped "error", as the server does when
 * the larger model cannot answer.
 */
type Sample = Pick<Schemas['ReadResponse'], 'lines' | 'confidence' | 'kind' | 'note'> & { script_guess: Schemas['ScriptGuess'] };

const MODERN: Schemas['ScriptGuess'] = { script: 'modern-tamil', label_en: 'Modern Tamil', label_ta: 'தற்காலத் தமிழ்', era: 'modern printed Tamil', confidence: 0.92, level: 'L1' };

export const MOCK_SAMPLE_READINGS: Record<string, Sample> = {
  'stone-tamil': {
    lines: [
      { n: '1', text: 'śrī tirukkaḻukunṟattu peṟumāṉ', text_tamil: 'ஶ்ரீ திருக்கழுகுந்றத்து பெறுமான்', confidence: 0.92, gaps: 0 },
      { n: '2', text: 'naṭikaḷukku kaḷattuārkōṭṭat', text_tamil: 'நடிகளுக்கு களத்துஆர்கோட்டத்', confidence: 0.82, gaps: 0 },
      { n: '3', text: 'tu [?3] tirukkaḻukkuṉṟa', text_tamil: 'து [?3] திருக்கழுக்குன்ற', confidence: 0.8, gaps: 1 },
    ],
    confidence: 0.82,
    kind: 'inscription',
    note: 'Line 3 has a white oval obscuring approximately 3-4 aksharas.',
    script_guess: { ...MODERN, confidence: 0.95 },
  },
  'stone-weathered': {
    lines: [
      { n: '1', text: 'svasti śrī pūmālai miṭaintu poṉamāṉa[?2] ka', text_tamil: 'ஸ்வஸ்தி ஶ்ரீ பூமாலை மிடைந்து பொனமான[?2] க', confidence: 0.72, gaps: 1 },
      { n: '2', text: 'ḻ tarap pāmāṉa[?2]niṉtu parumaṇit tiraḷ puyat', text_tamil: 'ழ் தரப் பாமான[?2]நின்து பருமணித் திரள் புயத்', confidence: 0.68, gaps: 1 },
      { n: '3', text: 't irunilamaṭ[?3]u jayamakaḷ iruppat [?]', text_tamil: 'த் இருநிலமட்[?3]உ ஜயமகள் இருப்பத் [?]', confidence: 0.65, gaps: 2 },
    ],
    confidence: 0.65,
    kind: 'printed',
    note: 'Some letters in the middle sections of lines 2 and 3 are partially obscured or damaged.',
    script_guess: MODERN,
  },
  'stone-brahmi': {
    lines: [
      { n: '1', text: 'āṉ ṟaḷ tēṉ pē tē caṟ āṉ ṉo ḷ ḷy ē', text_tamil: 'ஆன் றள் தேன் பே தே சற் ஆன் னொ ள் ள்ய் ஏ', confidence: 0.15, gaps: 0 },
      { n: '2', text: 'ḷ c tē pē tē pa ṟ āṉ ē ī tē cā cā', text_tamil: 'ள் ச் தே பே தே ப ற் ஆன் ஏ ஈ தே சா சா', confidence: 0.12, gaps: 0 },
      { n: '3', text: 'ṉ [?5] ṟaḷ tēṉ pē tē caṟ', text_tamil: 'ன் [?5] றள் தேன் பே தே சற்', confidence: 0.12, gaps: 1 },
    ],
    confidence: 0.1,
    kind: 'inscription',
    note: 'Transcriptions are highly tentative and likely incorrect in detail.',
    script_guess: { script: 'vatteluttu', label_en: 'Vatteluttu', label_ta: 'வட்டெழுத்து', era: 'early medieval Tamil, possibly 8th-10th century CE reproduction', confidence: 0.45, level: 'L4' },
  },
};

// Server constants (reader.py, config/models.yaml routing.escalate_if_confidence_below).
export const LOW_RELIABILITY_SCRIPTS = ['tamil-brahmi', 'vatteluttu', 'grantha'];
export const LOW_CONFIDENCE = 0.5;
export const ESCALATE_BELOW = 0.6;

type Warning = Schemas['ReadWarning'] & { message: string };

/** The server's image warnings, in its order. */
export function imageWarnings(s: Sample, cutShort = false): Warning[] {
  const out: Warning[] = [];
  if (cutShort) out.push({ code: 'cut_short', params: {}, message: 'the reading was cut short; later lines may be missing' });
  if (!s.lines.length) out.push({ code: 'no_text_in_image', params: {}, message: 'no readable Tamil-family text was found in the image' });
  else if (LOW_RELIABILITY_SCRIPTS.includes(s.script_guess.script))
    out.push({
      code: 'low_reliability_script',
      params: { script: s.script_guess.script },
      message: `Ezhuthu cannot yet read ${s.script_guess.label_en} reliably from photos (measured error rate above 50%): treat these letters as a guess and compare them with a published edition`,
    });
  else if ((s.confidence ?? 0) < LOW_CONFIDENCE)
    out.push({ code: 'unsure', params: {}, message: 'the reader is unsure about much of this reading; check every line against the stone' });
  return out;
}

const errBody = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status });
const TAMIL = /[஀-௿]/;
const GAP = /\[\?\d*\]/g;
const issued = new Map<string, string>(); // token -> image key (one-time, like the server)

function lineOf(n: number, raw: string): Schemas['ReadLine'] {
  const text = raw.replace(/\.{3,}|…/g, '[?]').replace(/\s+/g, ' ').trim();
  return { n: String(n), text, text_tamil: text, confidence: null, gaps: (text.match(GAP) ?? []).length };
}

/** EpiDoc edition lines with <supplied> as [?N] and <gap/> as [?], counted like ezhuthu.corpus.epidoc. */
export function epidocLines(xml: string): { lines: Schemas['ReadLine'][]; masked: number } {
  const edition = /<div[^>]*type="edition"[^>]*>([\s\S]*?)<\/div>\s*(?:<div[^>]*type="(?:apparatus|translation|commentary|bibliography)"|<\/body>)/.exec(xml)?.[1] ?? '';
  let masked = 0;
  const body = edition
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<(note|app|rdg|lem|foreign)\b[^>]*\/>/g, '')
    .replace(/<note\b[\s\S]*?<\/note>/g, '')
    .replace(/<(orig|sic|surplus)\b[^>]*>[\s\S]*?<\/\1>/g, '')
    .replace(/<supplied\b([^>]*)>([\s\S]*?)<\/supplied>/g, (_m, attrs: string, s: string) => {
      // Like the server: only reason="lost" / undefined are restorations; "omitted" stays text, glosses are dropped.
      const reason = /reason="([^"]+)"/.exec(attrs)?.[1] ?? 'undefined';
      if (reason === 'subaudible' || reason === 'explanation') return '';
      if (reason !== 'lost' && reason !== 'undefined') return s;
      masked += 1;
      const letters = s.replace(/<[^>]+>/g, '').replace(/[\s\-_.·’']/g, '').length;
      return `[?${Math.max(1, letters >> 1)}]`;
    })
    .replace(/<gap\b[^>]*\/>/g, '[?]');
  const lines = body
    .split(/<lb\b[^>]*\/>/)
    .slice(1)
    .map((s) => s.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .map((s, i) => lineOf(i + 1, s));
  return { lines, masked };
}

function envelope(source: Schemas['ReadResponse']['source'], lines: Schemas['ReadLine'][], warnings: Warning[], extra: Partial<Schemas['ReadResponse']> = {}): Schemas['ReadResponse'] {
  return {
    source,
    experimental: source === 'image',
    lines,
    text: lines.map((l) => l.text).join('\n'),
    text_tamil: lines.map((l) => l.text_tamil).join('\n'),
    gaps: lines.reduce((a, l) => a + l.gaps, 0),
    script_guess: null,
    confidence: null,
    models_used: [],
    escalated: false,
    warnings: warnings.map((w) => w.message),
    warning_codes: warnings.map(({ code, params }) => ({ code, params })),
    trace_id: `mock-read-${Date.now().toString(36)}`,
    latency_ms: 12,
    ...extra,
  };
}

function sampleKey(filename: string | undefined): string {
  const base = (filename ?? '').replace(/^.*[\\/]/, '').replace(/\.[a-z]+$/i, '');
  if (base in MOCK_SAMPLE_READINGS || SAMPLE_IMAGES.some((im) => im.id === base)) return base;
  return 'stone-weathered';
}

function readingFor(key: string): Sample {
  const known = MOCK_SAMPLE_READINGS[key];
  if (known) return known;
  const im = SAMPLE_IMAGES.find((x) => x.id === key)!;
  return {
    lines: im.lines.map((l, i) => lineOf(i + 1, l)),
    confidence: null,
    kind: im.style === 'page' ? 'printed' : 'inscription',
    note: 'Mock: the edition text this sample picture was rendered from (no measured reading).',
    script_guess: { ...MODERN, confidence: null },
  };
}

export const readHandlers = [
  http.post('/api/read', async ({ request }) => {
    await delay(import.meta.env.MODE === 'test' ? 0 : 900);
    const body = (await request.json().catch(() => null)) as Schemas['ReadRequest'] | null;
    if (!body || (body.image_base64 == null) === (body.text == null)) return errBody(422, 'bad_request', 'send exactly one of image_base64 or text');
    if (body.image_base64 != null) {
      if (body.image_base64.length > 4_500_000) return errBody(413, 'too_large', 'request body is larger than 4.3 MB');
      if (/hei[cf]/i.test(body.media_type ?? '')) return errBody(415, 'unsupported_format', 'HEIC photos are not supported here; export the photo as JPEG');
      const key = sampleKey(body.filename);
      if (body.router === 'opus') {
        if (!body.reread_token || issued.get(body.reread_token) !== key) return errBody(403, 'reread_token_invalid', "router 'opus' needs this photo's reread_token (it works once)");
        issued.delete(body.reread_token);
      }
      const s = readingFor(key);
      const bytes = Math.floor((body.image_base64.length * 3) / 4);
      const extra: Partial<Schemas['ReadResponse']> = {
        script_guess: s.script_guess,
        confidence: s.confidence,
        kind: s.kind,
        note: s.note,
        models_used: ['sonnet'],
        model: 'sonnet',
        escalated: false,
        image: { width: 1280, height: 530, bytes, format: 'jpeg', source_format: 'jpeg', source_bytes: bytes, resized: false, metadata_removed: [] },
      };
      if (body.router === 'opus') extra.escalation_skipped = 'error';
      else if ((body.router ?? 'routed') === 'routed' && (s.confidence ?? 0) < ESCALATE_BELOW) {
        // The server would ask Opus here; the mock has no Opus reading, so it behaves like a read that ran out of time.
        const token = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('');
        issued.set(token, key);
        extra.escalation_skipped = 'time_budget';
        extra.reread_token = token;
      }
      return HttpResponse.json(envelope('image', s.lines, imageWarnings(s), extra));
    }
    const text = body.text ?? '';
    const isXml = /\.xml$/i.test(body.filename ?? '') || body.format === 'epidoc' || text.trimStart().startsWith('<');
    if (isXml) {
      if (!/<TEI[\s>]/.test(text)) return errBody(422, 'not_epidoc', 'XML is not a TEI/EpiDoc document');
      const { lines, masked } = epidocLines(text);
      const title = /<titleStmt>[\s\S]*?<title[^>]*>([\s\S]*?)<\/title>/.exec(text)?.[1]?.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim() ?? null;
      const id = /<idno type="filename">(DHARMA_[A-Za-z0-9_]+)\.xml<\/idno>/.exec(text)?.[1] ?? null;
      const licence = /<licence\b[^>]*>([\s\S]*?)<\/licence>/.exec(text);
      const warnings: Warning[] = masked ? [{ code: 'masked_supplied', params: { n: masked }, message: `${masked} editorial restoration(s) (<supplied>) are shown as gaps for you to restore` }] : [];
      return HttpResponse.json(
        envelope('epidoc', lines, warnings, {
          title,
          licence: licence?.[1]?.replace(/<[^>]+>/g, '').trim() ?? null,
          licence_url: /target="(https:\/\/[^"]+)"/.exec(licence?.[0] ?? '')?.[1] ?? null,
          masked_supplied: masked,
          inscription_id: id,
          source_url: id ? `https://dharmalekha.info/texts/${id}` : null,
        }),
      );
    }
    const lines = text
      .split(/\r?\n/)
      .map((s) => s.replace(/^\s*\(?\d{1,3}[.)]\s+/, ''))
      .filter((s) => s.trim() && (TAMIL.test(s) || /[a-zāīūēōṭṇṉṟḷḻ]/i.test(s)))
      .map((s, i) => lineOf(i + 1, s));
    if (!lines.length) return errBody(422, 'no_text', 'no Tamil or ISO-15919 text found in the file');
    return HttpResponse.json(envelope('text', lines, []));
  }),
];
