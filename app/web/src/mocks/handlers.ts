import { delay, http, HttpResponse } from 'msw';
import type { Schemas } from '../api/client';
import { parseGaps, gapContext } from '../lib/gaps';
import { isLevel } from '../lib/levels';
import { expectedCalibrationError } from '../lib/reliability';
import { sampleByInscription } from '../samples';
import { SAMPLES } from '../samples/data';
import { readHandlers } from './read';
import { ASSESSMENT, LESSONS, REVIEWED_ELSEWHERE, SEED_QUEUE, templateContext, type MockItem } from './fixtures';

/** In-memory backend state for the mock API. `resetMockState()` gives tests a clean slate. */
interface SessionState {
  level: Schemas['Level'];
  attempts: Record<string, number>;
  lastAnswerAt: number | null;
  letterSeconds: number[];
  correctByLevel: Record<string, number>;
  phases: Partial<Record<'pre' | 'post', { items: string[]; correct: Set<string> }>>;
  activePhase: 'pre' | 'post' | null;
  /** The tutor team's explanation, delivered once as context_update on the next /api/answer. */
  pendingExplanation?: { explain_ta: string; explain_en: string } | null;
}
const state = {
  sessions: new Map<string, SessionState>(),
  queue: [] as Schemas['QueueItem'][],
  seq: 0,
};
export function resetMockState() {
  state.sessions.clear();
  state.queue = SEED_QUEUE.map((q) => ({ ...q }));
  state.seq = 0;
}

// In the browser the handlers live in the page, so a full reload would wipe the mock backend.
// Persist it per tab so deep links (/progress after /learn) behave like a real server.
const PERSIST_KEY = 'ezhuthu.mock-state';
const canPersist = typeof window !== 'undefined' && import.meta.env.MODE !== 'test';
function persist() {
  if (!canPersist) return;
  try {
    const sessions = [...state.sessions].map(([id, s]) => [
      id,
      { ...s, phases: Object.fromEntries(Object.entries(s.phases).map(([k, v]) => [k, { items: v.items, correct: [...v.correct] }])) },
    ]);
    window.sessionStorage.setItem(PERSIST_KEY, JSON.stringify({ sessions, queue: state.queue, seq: state.seq }));
  } catch {
    /* storage blocked: mock state lasts for this page load */
  }
}
function restorePersisted() {
  if (!canPersist) return;
  try {
    const raw = window.sessionStorage.getItem(PERSIST_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw) as {
      sessions: [string, Omit<SessionState, 'phases'> & { phases: Record<string, { items: string[]; correct: string[] }> }][];
      queue: Schemas['QueueItem'][];
      seq: number;
    };
    for (const [id, s] of saved.sessions)
      state.sessions.set(id, {
        ...s,
        phases: Object.fromEntries(Object.entries(s.phases).map(([k, v]) => [k, { items: v.items, correct: new Set(v.correct) }])),
      });
    state.queue = saved.queue;
    state.seq = saved.seq;
  } catch {
    /* corrupt or blocked storage: start fresh */
  }
}
resetMockState();
restorePersisted();

const ALL_ITEMS: Map<string, MockItem> = new Map(
  [...Object.values(LESSONS).flatMap((l) => l.items), ...ASSESSMENT].map((i) => [i.item_id, i]),
);

const err = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status });
const publicItem = ({ answers: _a, hint_ta: _h, hint_en: _e, ...rest }: MockItem): Schemas['PracticeItem'] => rest;
const norm = (s: string) => s.normalize('NFC').trim().toLowerCase();
const MOCK_DECIDER = 'mock-decider';
const latency = () => delay(import.meta.env.MODE === 'test' ? 0 : 250);

function requireUser(request: Request, expert = false): Response | null {
  const auth = request.headers.get('Authorization');
  if (!auth?.startsWith('Bearer ')) return err(401, 'unauthorized', 'sign in required');
  if (expert && auth !== 'Bearer mock-access-token') return err(403, 'forbidden', 'experts group required');
  return null;
}

/* ---------------- restoration rules (deterministic, mock only) ---------------- */
interface Rule {
  test: RegExp;
  candidates: [string, string, number, Schemas['Candidate']['model']][];
  hints?: Schemas['OntologyHint'][];
}
const RULES: Rule[] = [
  {
    // Chola regnal formula: ko-PARA-kesari vs ko-IRAJA-kesari alternate between successive kings.
    test: /(kōp|கோப்)$/,
    candidates: [
      ['para', 'பர', 0.78, 'sonnet'],
      ['irāja', 'இராஜ', 0.17, 'sonnet'],
    ],
    hints: [
      { id: 'ez:title/parakesari', kind: 'title', label: 'Parakēsari (Chola regnal title)' },
      { id: 'ez:ruler/parantaka-i', kind: 'ruler', label: 'Parantaka I' },
    ],
  },
  {
    test: /(svasti|ஸ்வஸ்தி)\s*$/,
    candidates: [['śrī', 'ஸ்ரீ', 0.93, 'retrieval']],
    hints: [{ id: 'ez:formula/svasti-sri', kind: 'formula', label: 'svasti śrī (opening formula)' }],
  },
  {
    test: /(nanti|நந்தி)$/,
    candidates: [
      ['vikkirama', 'விக்கிரம', 0.71, 'opus'],
      ['varma', 'வர்ம', 0.12, 'opus'],
    ],
    hints: [{ id: 'ez:ruler/nandivarman-ii', kind: 'ruler', label: 'Nandivarman II' }],
  },
];

function restore(body: Schemas['RestoreRequest']): Schemas['RestoreResponse'] {
  const tamil = body.script === 'tamil';
  const max = body.max_candidates ?? 5;
  const segs = parseGaps(body.text);
  const gaps: Schemas['Gap'][] = [];
  let restoredIso = '';
  let restoredTa = '';
  let escalated = false;
  for (const s of segs) {
    if (s.kind === 'text') {
      restoredIso += s.text;
      restoredTa += s.text;
      continue;
    }
    const { left } = gapContext(body.text, s.index, 40);
    const rule = RULES.find((r) => r.test.test(left.trimEnd()) || r.test.test(left));
    const candidates: Schemas['Candidate'][] = (rule?.candidates ?? [
      ['ā', 'ஆ', 0.21, 'sonnet'],
      ['iru', 'இரு', 0.14, 'sonnet'],
    ])
      .slice(0, max)
      .filter(([, , , m]) => body.allow_escalation !== false || m !== 'opus')
      .map(([text, text_tamil, confidence, model]) => ({
        text,
        text_tamil,
        confidence,
        model,
        decider_model: MOCK_DECIDER,
        parallels: rule
          ? [
              {
                inscription_id: 'mock:parallel-1',
                line_n: '1',
                snippet: `${left.slice(-16)}${text}…`,
                url: 'https://dharmalekha.info',
              },
            ]
          : [],
        ontology_hints: rule?.hints ?? [],
      }));
    escalated ||= candidates.some((c) => c.model === 'opus');
    const best = candidates[0];
    const fill = !!best && best.confidence >= 0.5; // mirrors routing.abstain_if_confidence_below in config/models.yaml
    gaps.push({ index: s.index, gap_chars: s.chars, decision: fill ? 'fill' : 'abstain', chosen: fill ? 0 : null, candidates });
    restoredIso += fill ? best.text : s.raw;
    restoredTa += fill ? best.text_tamil : s.raw;
  }
  state.seq += 1;
  return {
    restored_text: tamil ? restoredTa : restoredIso,
    restored_text_tamil: restoredTa,
    gaps,
    models_used: escalated ? ['sonnet', 'opus', MOCK_DECIDER] : ['sonnet', MOCK_DECIDER],
    trace_id: `mock-trace-${state.seq}`,
    latency_ms: 0,
  };
}

/* ---------------- evaluation (seeded synthetic scores, mock only) ---------------- */
function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function evaluate(ids: string[], targets: string[], router: string): Schemas['EvaluateResponse'] {
  const rnd = mulberry32(ids.length * 7919 + router.length);
  const items: Schemas['EvaluateItem'][] = ids.map((id, i) => {
    const confidence = Math.round((0.2 + rnd() * 0.79) * 100) / 100;
    const abstained = confidence < 0.5;
    const correct = !abstained && rnd() < confidence - 0.06;
    return { id, target: targets[i] ?? '', prediction: abstained ? null : correct ? (targets[i] ?? '') : '…', confidence, correct, abstained, router };
  });
  const answered = items.filter((i) => !i.abstained);
  const top1 = items.length ? items.filter((i) => i.correct).length / items.length : 0;
  const coverage = [0.5, 0.6, 0.7, 0.8, 0.9].map((threshold) => {
    const kept = items.filter((i) => i.confidence >= threshold);
    return {
      threshold,
      coverage: items.length ? kept.length / items.length : 0,
      accuracy: kept.length ? kept.filter((i) => i.correct).length / kept.length : 0,
    };
  });
  const r2 = (x: number) => Math.round(x * 1000) / 1000;
  const ece = r2(expectedCalibrationError(answered));
  return {
    n: items.length,
    top1: r2(top1),
    top20: r2(Math.min(1, top1 + 0.18)),
    cer: r2(0.42 - top1 * 0.3),
    ece,
    coverage,
    by_router: { [router]: { n: items.length, top1: r2(top1), ece } },
    items,
  };
}

/* ---------------- tutor ---------------- */
function grade(sessionId: string, itemId: string, answer: string): Schemas['AnswerResponse'] | null {
  const s = state.sessions.get(sessionId);
  const item = ALL_ITEMS.get(itemId);
  if (!s || !item) return null;
  const now = Date.now();
  if (s.lastAnswerAt && item.type === 'letter') s.letterSeconds.push((now - s.lastAnswerAt) / 1000);
  s.lastAnswerAt = now;
  const correct = item.answers.map(norm).includes(norm(answer));
  const tries = (s.attempts[itemId] = (s.attempts[itemId] ?? 0) + 1);
  const active = s.activePhase ? s.phases[s.activePhase] : undefined;
  if (active?.items.includes(itemId) && correct) active.correct.add(itemId);
  if (correct) {
    if (tries === 1) s.correctByLevel[item.script_level] = (s.correctByLevel[item.script_level] ?? 0) + 1;
    return {
      correct,
      feedback_ta: tries === 1 ? 'சரியாகப் படித்தீர்கள்!' : 'இப்போது சரி. நன்றாக முயன்றீர்கள்.',
      feedback_en: tries === 1 ? 'You read it right!' : 'Right this time. Well done for persisting.',
      next_action: 'advance',
      decider_confidence: tries === 1 ? 0.91 : 0.74,
      decider_source: 'mock',
    };
  }
  if (tries === 1)
    return {
      correct,
      feedback_ta: 'இன்னும் இல்லை. இந்தக் குறிப்பைப் பாருங்கள்.',
      feedback_en: 'Not yet. Here is a hint.',
      next_action: 'hint',
      decider_confidence: 0.68,
      decider_source: 'mock',
      hint_ta: item.hint_ta,
    };
  if (tries === 2)
    return {
      correct,
      feedback_ta: 'மீண்டும் ஒருமுறை கவனமாகப் பாருங்கள்.',
      feedback_en: 'Look closely and try once more.',
      next_action: 'repeat',
      decider_confidence: 0.61,
      decider_source: 'mock',
      hint_ta: item.hint_ta,
    };
  // Third miss: the attempt-limit guardrail decides, not the decider, so there is no confidence (the agent's
  // tutor/policy.py rule override; decider_source "rules").
  return {
    correct,
    feedback_ta: `இதன் வாசிப்பு “${item.answers[0]}”. அடுத்ததுக்குச் செல்வோம்.`,
    feedback_en: `This reads “${item.answers[0]}”. Let us move on.`,
    next_action: 'advance',
    decider_confidence: null,
    decider_source: 'rules',
  };
}

function median(xs: number[]): number | null {
  if (!xs.length) return null;
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
}

function newSession(level: Schemas['Level']): string {
  const id = `mock-session-${(state.sessions.size + 1).toString().padStart(4, '0')}-${Date.now().toString(36)}`;
  state.sessions.set(id, { level, attempts: {}, lastAnswerAt: null, letterSeconds: [], correctByLevel: {}, phases: {}, activePhase: null });
  return id;
}

export const handlers = [
  ...readHandlers,
  http.post('/api/restore', async ({ request }) => {
    await latency();
    const body = (await request.json()) as Schemas['RestoreRequest'];
    if (typeof body?.text !== 'string' || !body.text.trim()) return err(400, 'bad_request', 'text is required');
    if (!parseGaps(body.text).some((s) => s.kind === 'gap')) return err(422, 'no_gaps', 'no [?] or [?N] gap in text');
    const out = restore(body);
    persist();
    return HttpResponse.json(out);
  }),

  http.post('/api/lesson', async ({ request }) => {
    await latency();
    const body = (await request.json()) as Schemas['LessonRequest'];
    if (!isLevel(body?.level)) return err(400, 'bad_request', 'level must be L1..L5');
    const lesson = LESSONS[body.level];
    const own = body.text?.trim();
    // inscription_id: the gallery samples are known; any other id is unknown, as on the real API (404).
    const linked = !own && body.inscription_id ? sampleByInscription(SAMPLES, body.inscription_id) : undefined;
    if (!own && body.inscription_id && !linked) return err(404, 'not_found', `inscription ${body.inscription_id} not found`);
    const session_id = newSession(body.level);
    // Like EZHUTHU_LESSON_EXPLAIN=async: the template explanation now, the tutor team's on the next answer.
    state.sessions.get(session_id)!.pendingExplanation = { explain_ta: lesson.context.explain_ta, explain_en: lesson.context.explain_en };
    const res: Schemas['LessonResponse'] = {
      session_id,
      inscription: own
        ? { ...lesson.inscription, id: 'mock:user-text', title: 'Your text', source_url: null, licence: null, restored_text: own, restored_text_tamil: own }
        : linked
          ? {
              id: linked.inscription_id,
              title: linked.edition_title,
              dynasty: linked.dynasty,
              approx_date: null,
              ruler: linked.ruler,
              regnal_year: linked.regnal_year,
              source_url: linked.source_url,
              dharmalekha_url: linked.dharma_url,
              licence: linked.licence,
              restored_text: linked.text_iso,
              restored_text_tamil: linked.text_tamil,
            }
          : lesson.inscription,
      items: lesson.items.map(publicItem),
      context: templateContext(lesson),
    };
    persist();
    return HttpResponse.json(res);
  }),

  http.post('/api/answer', async ({ request }) => {
    await latency();
    const body = (await request.json()) as Schemas['AnswerRequest'];
    const res = grade(body.session_id, body.item_id, body.answer ?? '');
    const s = state.sessions.get(body.session_id);
    if (res && s?.pendingExplanation) {
      res.context_update = { ...s.pendingExplanation, explained_by: 'tutor_team', explanation_status: 'done' };
      s.pendingExplanation = null; // delivered once
    }
    persist();
    return res ? HttpResponse.json(res) : err(404, 'not_found', 'unknown session or item');
  }),

  http.post('/api/assessment', async ({ request }) => {
    await latency();
    const body = (await request.json()) as Schemas['AssessmentRequest'];
    const s = state.sessions.get(body.session_id);
    if (!s) return err(404, 'not_found', 'unknown session');
    if (body.phase !== 'pre' && body.phase !== 'post') return err(400, 'bad_request', 'phase must be pre or post');
    s.phases[body.phase] = { items: ASSESSMENT.map((i) => i.item_id), correct: new Set() };
    s.activePhase = body.phase;
    persist();
    return HttpResponse.json({ session_id: body.session_id, phase: body.phase, items: ASSESSMENT.map(publicItem) });
  }),

  http.get('/api/progress/:sessionId', async ({ params }) => {
    await latency();
    const s = state.sessions.get(String(params.sessionId));
    if (!s) return err(404, 'not_found', 'unknown session');
    const score = (p?: { items: string[]; correct: Set<string> }) => (p ? p.correct.size / p.items.length : null);
    const pre = score(s.phases.pre);
    const post = score(s.phases.post);
    const res: Schemas['ProgressResponse'] = {
      pre_score: pre,
      post_score: post,
      gain: pre !== null && post !== null ? post - pre : null,
      letters_correct_by_level: { L1: 0, L2: 0, L3: 0, L4: 0, L5: 0, ...s.correctByLevel },
      median_seconds_per_letter: median(s.letterSeconds),
    };
    return HttpResponse.json(res);
  }),

  http.post('/api/evaluate', async ({ request }) => {
    const denied = requireUser(request);
    if (denied) return denied;
    await latency();
    const type = request.headers.get('Content-Type') ?? '';
    if (type.includes('ndjson')) {
      const lines = (await request.text()).split(/\r?\n/).filter((l) => l.trim());
      const recs = lines.map((l) => JSON.parse(l) as Schemas['BenchmarkItem']);
      return HttpResponse.json(evaluate(recs.map((r) => r.id), recs.map((r) => r.target), 'routed'));
    }
    const body = (await request.json()) as Schemas['EvaluateBuiltinRequest'];
    const n = Math.min(body.limit ?? 200, 2000);
    const ids = Array.from({ length: n }, (_, i) => `mock:${body.benchmark}:${i}`);
    return HttpResponse.json(evaluate(ids, ids.map(() => 'x'), body.router ?? 'routed'));
  }),

  http.post('/api/corrections', async ({ request }) => {
    await latency();
    const body = (await request.json()) as Schemas['CorrectionRequest'];
    if (!body?.gap_ref?.trace_id || typeof body.gap_ref.gap_index !== 'number')
      return err(400, 'bad_request', 'gap_ref.trace_id and gap_ref.gap_index are required');
    if (!body.accepted_candidate && !body.corrected_text)
      return err(400, 'bad_request', 'accepted_candidate or corrected_text is required');
    const item: Schemas['QueueItem'] = {
      id: `q-${(state.queue.length + 1).toString().padStart(4, '0')}`,
      gap_ref: body.gap_ref,
      ...(body.accepted_candidate ? { accepted_candidate: body.accepted_candidate } : {}),
      ...(body.corrected_text ? { corrected_text: body.corrected_text } : {}),
      user: body.user?.trim() || 'anonymous',
      status: 'pending',
      created_at: new Date().toISOString(),
    };
    state.queue.push(item);
    persist();
    return HttpResponse.json(item, { status: 201 });
  }),

  http.get('/api/queue', async ({ request }) => {
    const denied = requireUser(request, true);
    if (denied) return denied;
    await latency();
    return HttpResponse.json({ items: state.queue.filter((q) => q.status === 'pending') });
  }),

  http.post('/api/queue/:id', async ({ request, params }) => {
    const denied = requireUser(request, true);
    if (denied) return denied;
    await latency();
    const body = (await request.json()) as Schemas['QueueAction'];
    const item = state.queue.find((q) => q.id === params.id);
    if (!item) return err(404, 'not_found', 'unknown queue item');
    if (REVIEWED_ELSEWHERE.has(item.id) && item.status === 'pending') {
      Object.assign(item, { status: 'approved', reviewed_by: 'another-expert', reviewed_at: new Date().toISOString(), final_text: item.accepted_candidate ?? '' });
      persist();
    }
    if (item.status !== 'pending') return err(409, 'conflict', 'item does not exist or was already reviewed');
    if (body.action === 'edit' && !body.text?.trim()) return err(400, 'bad_request', 'text is required for edit');
    item.status = body.action === 'approve' ? 'approved' : body.action === 'edit' ? 'edited' : 'rejected';
    item.reviewed_by = 'demo-expert';
    item.reviewed_at = new Date().toISOString();
    if (body.action !== 'reject') item.final_text = body.text?.trim() || item.corrected_text || item.accepted_candidate || '';
    persist();
    return HttpResponse.json(item);
  }),
];
