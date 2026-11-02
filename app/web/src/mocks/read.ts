import { http, HttpResponse, delay } from 'msw';
import type { Schemas } from '../api/client';

/**
 * Mock POST /api/read (contracts/restore-api.md). The mock cannot read photos: every image gets the real reading of the
 * "Weathered stone" sample plate (DHARMA TEST lines, CC BY-SA 4.0), labelled experimental like the real reader.
 * Text files are split into lines; EpiDoc files are reduced to their <lb/> lines with <supplied> shown as [?N].
 */
export const MOCK_PHOTO_LINES: Schemas['ReadLine'][] = [
  // Sonnet 4.6's real reading of public/samples/read/stone-weathered.jpg (DHARMA_INSPallava00526, TEST split),
  // eval/reports/2026-11-02-ocr-eval-synth.jsonl id p00-tamil-weathered.
  { n: '1', text: 'svasti śrī kō [?3] ya', text_tamil: 'ஸ்வஸ்தி ஶ்ரீ கோ [?3] ய', confidence: 0.55, gaps: 1 },
  { n: '2', text: 'tantiparumaṟku yāṇṭu [?2]', text_tamil: 'தந்திபருமற்கு யாண்டு [?2]', confidence: 0.45, gaps: 1 },
  { n: '3', text: '[?2] tiṉ āṟāvatu viṭēl', text_tamil: '[?2] தின் ஆறாவது விடேல்', confidence: 0.4, gaps: 1 },
];

const errBody = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status });
const TAMIL = /[஀-௿]/;

function lineOf(n: number, raw: string): Schemas['ReadLine'] {
  const text = raw.replace(/\.{3,}|…/g, '[?]').replace(/\s+/g, ' ').trim();
  return { n: String(n), text, text_tamil: text, confidence: null, gaps: (text.match(/\[\?\d*\]/g) ?? []).length };
}

function epidocLines(xml: string): Schemas['ReadLine'][] {
  const edition = /<div[^>]*type="edition"[^>]*>([\s\S]*?)<\/div>\s*<div[^>]*type="(?:apparatus|translation|commentary|bibliography)"/.exec(xml)?.[1] ?? xml;
  const body = edition
    .replace(/<note[\s\S]*?<\/note>/g, '')
    .replace(/<supplied[^>]*>([\s\S]*?)<\/supplied>/g, (_m, s: string) => `[?${Math.max(1, s.replace(/<[^>]+>/g, '').replace(/\s/g, '').length >> 1)}]`)
    .replace(/<gap[^>]*\/>/g, '[?]');
  return body
    .split(/<lb\b[^>]*\/>/)
    .slice(1)
    .map((s) => s.replace(/<[^>]+>/g, ''))
    .filter((s) => s.trim())
    .map((s, i) => lineOf(i + 1, s));
}

function envelope(source: Schemas['ReadResponse']['source'], lines: Schemas['ReadLine'][], extra: Partial<Schemas['ReadResponse']> = {}): Schemas['ReadResponse'] {
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
    warnings: [],
    trace_id: `mock-read-${Date.now().toString(36)}`,
    latency_ms: 12,
    ...extra,
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
      const bytes = Math.floor((body.image_base64.length * 3) / 4);
      return HttpResponse.json(
        envelope('image', MOCK_PHOTO_LINES, {
          script_guess: { script: 'modern-tamil', label_en: 'Modern Tamil', label_ta: 'தற்காலத் தமிழ்', era: 'modern reproduction or label', confidence: 0.95, level: 'L1' },
          confidence: 0.4,
          kind: 'inscription',
          models_used: ['sonnet', 'opus'],
          model: 'opus',
          escalated: true,
          image: { width: 1280, height: 530, bytes, format: 'jpeg', source_format: 'jpeg', source_bytes: bytes, resized: false, metadata_removed: [] },
        }),
      );
    }
    const text = body.text ?? '';
    const isXml = /\.xml$/i.test(body.filename ?? '') || body.format === 'epidoc' || text.trimStart().startsWith('<');
    if (isXml) {
      if (!/<TEI[\s>]/.test(text)) return errBody(422, 'not_epidoc', 'XML is not a TEI/EpiDoc document');
      const lines = epidocLines(text);
      const title = /<title[^>]*>([\s\S]*?)<\/title>/.exec(text)?.[1]?.replace(/<[^>]+>/g, '').trim() ?? null;
      return HttpResponse.json(envelope('epidoc', lines, { title, licence: 'CC BY-SA 4.0', masked_supplied: (text.match(/<supplied/g) ?? []).length }));
    }
    const lines = text
      .split(/\r?\n/)
      .map((s) => s.replace(/^\s*\(?\d{1,3}[.)]\s+/, ''))
      .filter((s) => s.trim() && (TAMIL.test(s) || /[a-zāīūēōṭṇṉṟḷḻ]/i.test(s)))
      .map((s, i) => lineOf(i + 1, s));
    if (!lines.length) return errBody(422, 'no_text', 'no Tamil or ISO-15919 text found in the file');
    return HttpResponse.json(envelope('text', lines));
  }),
];
