import { describe, expect, it } from 'vitest';
import { api, ApiError, setTokenGetter } from '../api/client';
import { ASSESSMENT, LESSONS, SAMPLE_RESTORE_ISO, SAMPLE_RESTORE_TAMIL } from './fixtures';

// The mocks stand in for the backend, so they must honour contracts/restore-api.md exactly.
describe('mock API honours the restore contract', () => {
  it('fills a confident gap and abstains on an unknowable one', async () => {
    const r = await api.restore({ text: SAMPLE_RESTORE_ISO, script: 'iso15919', max_candidates: 5, allow_escalation: true });
    expect(r.gaps).toHaveLength(2);
    const [g0, g1] = r.gaps;
    expect(g0).toMatchObject({ index: 0, gap_chars: 4, decision: 'fill', chosen: 0 });
    expect(g0!.candidates[0]).toMatchObject({ text: 'para', text_tamil: 'பர', model: 'sonnet' });
    expect(g0!.candidates[0]!.confidence).toBeGreaterThanOrEqual(0.5);
    expect(g0!.candidates[0]!.parallels[0]!.url).toMatch(/^https:/);
    expect(g1).toMatchObject({ index: 1, gap_chars: null, decision: 'abstain', chosen: null });
    expect(r.restored_text).toContain('kōppara');
    expect(r.restored_text).toContain('[?]');
    expect(r.trace_id).toBeTruthy();
  });
  it('restores Tamil-script input and respects max_candidates', async () => {
    const r = await api.restore({ text: SAMPLE_RESTORE_TAMIL, script: 'tamil', max_candidates: 1 });
    expect(r.restored_text).toContain('கோப்பர');
    expect(r.gaps.every((g) => g.candidates.length <= 1)).toBe(true);
  });
  it('rejects text without gaps with a contract error body', async () => {
    await expect(api.restore({ text: 'no gaps' })).rejects.toMatchObject({ status: 422, code: 'no_gaps' });
  });
});

describe('mock API honours the tutor contract', () => {
  it('runs lesson -> answer (hint, repeat, advance) -> assessment -> progress', async () => {
    const lesson = await api.lesson({ level: 'L5', lang: 'ta' });
    expect(lesson.items.length).toBe(LESSONS.L5.items.length);
    expect(lesson.items[0]).not.toHaveProperty('answers');
    expect(lesson.items.every((i) => i.answer_hidden)).toBe(true);
    const sid = lesson.session_id;
    const first = lesson.items[0]!.item_id;

    const wrong1 = await api.answer({ session_id: sid, item_id: first, answer: 'ம' });
    expect(wrong1).toMatchObject({ correct: false, next_action: 'hint' });
    expect(wrong1.hint_ta).toBeTruthy();
    expect((await api.answer({ session_id: sid, item_id: first, answer: 'ம' })).next_action).toBe('repeat');
    const right = await api.answer({ session_id: sid, item_id: first, answer: ' KA ' });
    expect(right).toMatchObject({ correct: true, next_action: 'advance' });

    const pre = await api.assessment({ session_id: sid, phase: 'pre' });
    expect(pre.items).toHaveLength(10);
    for (const [i, item] of pre.items.entries()) {
      const answer = i < 3 ? ASSESSMENT[i]!.answers[0]! : 'x';
      await api.answer({ session_id: sid, item_id: item.item_id, answer });
    }
    const post = await api.assessment({ session_id: sid, phase: 'post' });
    for (const [i, item] of post.items.entries()) await api.answer({ session_id: sid, item_id: item.item_id, answer: ASSESSMENT[i]!.answers[0]! });

    const p = await api.progress(sid);
    expect(p.pre_score).toBeCloseTo(0.3);
    expect(p.post_score).toBeCloseTo(1);
    expect(p.gain).toBeCloseTo(0.7);
    expect(Object.keys(p.letters_correct_by_level).sort()).toEqual(['L1', 'L2', 'L3', 'L4', 'L5']);
    expect(p.median_seconds_per_letter).not.toBeNull();
  });
  it('404s an unknown session', async () => {
    await expect(api.progress('nope')).rejects.toBeInstanceOf(ApiError);
  });
});

describe('mock API enforces auth like the real HTTP API', () => {
  it('requires a token for evaluate and the experts token for the queue', async () => {
    setTokenGetter(() => null);
    await expect(api.evaluate({ benchmark: 'test-hard', limit: 5 })).rejects.toMatchObject({ status: 401 });
    await expect(api.queue()).rejects.toMatchObject({ status: 401 });
    setTokenGetter(() => 'some-learner-token');
    await expect(api.queue()).rejects.toMatchObject({ status: 403 });
    setTokenGetter(() => 'mock-access-token');
    const q = await api.queue();
    expect(q.items.length).toBeGreaterThan(0);
    const reviewed = await api.review(q.items[0]!.id, { action: 'reject' });
    expect(reviewed.status).toBe('rejected');
    await expect(api.review(q.items[0]!.id, { action: 'approve' })).rejects.toMatchObject({ status: 409 });
    setTokenGetter(() => null);
  });
  it('scores a built-in run and a JSONL upload with a contract-shaped report', async () => {
    setTokenGetter(() => 'mock-access-token');
    const r = await api.evaluate({ benchmark: 'test-hard', limit: 40, router: 'routed' });
    expect(r.n).toBe(40);
    expect(r.items).toHaveLength(40);
    for (const k of ['top1', 'top20', 'cer', 'ece'] as const) expect(r[k]).toBeGreaterThanOrEqual(0);
    expect(r.coverage.map((c) => c.threshold)).toEqual([0.5, 0.6, 0.7, 0.8, 0.9]);
    const up = await api.evaluateUpload('{"id":"a","target":"x"}\n{"id":"b","target":"y"}\n');
    expect(up.n).toBe(2);
    setTokenGetter(() => null);
  });
  it('queues a public correction for review', async () => {
    const c = await api.correction({ gap_ref: { trace_id: 't', gap_index: 0 }, corrected_text: 'para', user: '' });
    expect(c).toMatchObject({ status: 'pending', user: 'anonymous', corrected_text: 'para' });
    await expect(api.correction({ gap_ref: { trace_id: 't', gap_index: 0 }, user: 'x' })).rejects.toMatchObject({ status: 400 });
  });
});

describe('mock API mirrors the agent: async lesson, rules decisions and single review', () => {
  it('returns a pending template explanation and delivers the tutor team one once, as context_update', async () => {
    const lesson = await api.lesson({ level: 'L5', lang: 'en' });
    expect(lesson.context).toMatchObject({ explanation_status: 'pending', explained_by: 'template', ruler: 'Neṭuñceḻiyaṉ (Pandya)' });
    const item = lesson.items[0]!.item_id;
    const a1 = await api.answer({ session_id: lesson.session_id, item_id: item, answer: 'ம' });
    expect(a1.context_update).toEqual({
      explain_ta: LESSONS.L5.context.explain_ta,
      explain_en: LESSONS.L5.context.explain_en,
      explained_by: 'tutor_team',
      explanation_status: 'done',
    });
    const a2 = await api.answer({ session_id: lesson.session_id, item_id: item, answer: 'ம' });
    expect(a2).not.toHaveProperty('context_update');
  });
  it('sends decider_confidence null with decider_source rules when the attempt limit decides', async () => {
    const lesson = await api.lesson({ level: 'L1', lang: 'en' });
    const ask = () => api.answer({ session_id: lesson.session_id, item_id: lesson.items[0]!.item_id, answer: 'x' });
    expect((await ask()).decider_confidence).toBe(0.68);
    expect((await ask()).decider_confidence).toBe(0.61);
    expect(await ask()).toMatchObject({ next_action: 'advance', decider_confidence: null, decider_source: 'rules' });
  });
  it('answers 409 when another expert reviewed the item first', async () => {
    setTokenGetter(() => 'mock-access-token');
    expect((await api.queue()).items.map((q) => q.id)).toContain('q-0004');
    const e = await api.review('q-0004', { action: 'approve' }).catch((x: unknown) => x);
    expect(e).toBeInstanceOf(ApiError);
    expect(e).toMatchObject({ status: 409, code: 'conflict' });
    expect((await api.queue()).items.map((q) => q.id)).not.toContain('q-0004');
    setTokenGetter(() => null);
  });
});
