/**
 * Local practice progress, on this device only. Every storage access is wrapped: in a private window, with storage
 * blocked or full, practice still works and progress lasts for the visit (kept in memory).
 */
import { betterTrial, type Answer } from './engine';
import type { Level, SessionKind } from './types';

export const PROGRESS_KEY = 'ezhuthu.practice.v1';
const RECENT_MAX = 60;

export interface KindStats {
  answered: number;
  right: number;
  sessions: number;
  /** best session ratio, 0..1 */
  best: number | null;
  byLevel: Partial<Record<Level, { answered: number; right: number }>>;
  last: string | null;
}

export interface Progress {
  v: 1;
  kinds: Partial<Record<SessionKind, KindStats>>;
  trial: { runs: number; best: { right: number; total: number; ms: number } | null };
  recent: string[];
}

export function emptyProgress(): Progress {
  return { v: 1, kinds: {}, trial: { runs: 0, best: null }, recent: [] };
}

let memory: Progress | null = null;
let storageOk: boolean | null = null;
const listeners = new Set<() => void>();

function parse(raw: string | null): Progress | null {
  if (!raw) return null;
  try {
    const p = JSON.parse(raw) as Progress;
    return p && p.v === 1 && typeof p.kinds === 'object' ? { ...emptyProgress(), ...p } : null;
  } catch {
    return null;
  }
}

export function loadProgress(): Progress {
  try {
    const p = parse(window.localStorage.getItem(PROGRESS_KEY));
    storageOk = true;
    if (p) memory = p;
  } catch {
    storageOk = false;
  }
  return memory ?? emptyProgress();
}

export function storageAvailable(): boolean {
  if (storageOk === null) loadProgress();
  return storageOk === true;
}

function save(p: Progress) {
  memory = p;
  try {
    window.localStorage.setItem(PROGRESS_KEY, JSON.stringify(p));
    storageOk = true;
  } catch {
    storageOk = false; // blocked or full: keep it in memory for this visit
  }
  listeners.forEach((f) => f());
}

export function onProgress(f: () => void): () => void {
  listeners.add(f);
  return () => listeners.delete(f);
}

function stats(p: Progress, kind: SessionKind): KindStats {
  return p.kinds[kind] ?? { answered: 0, right: 0, sessions: 0, best: null, byLevel: {}, last: null };
}

/** One answered question (counted at once, so leaving mid-session keeps what was done). */
export function recordAnswer(kind: SessionKind, a: Pick<Answer, 'id' | 'level' | 'right'>, now = new Date()): Progress {
  const p = loadProgress();
  const s = stats(p, kind);
  const lv = s.byLevel[a.level] ?? { answered: 0, right: 0 };
  const next: Progress = {
    ...p,
    kinds: {
      ...p.kinds,
      [kind]: {
        ...s,
        answered: s.answered + 1,
        right: s.right + (a.right ? 1 : 0),
        byLevel: { ...s.byLevel, [a.level]: { answered: lv.answered + 1, right: lv.right + (a.right ? 1 : 0) } },
        last: now.toISOString(),
      },
    },
    recent: [a.id, ...p.recent.filter((x) => x !== a.id)].slice(0, RECENT_MAX),
  };
  save(next);
  return next;
}

/** A finished session of `kind`: counts it and keeps the best ratio. */
export function recordSession(kind: SessionKind, right: number, total: number): Progress {
  const p = loadProgress();
  const s = stats(p, kind);
  const ratio = total ? right / total : 0;
  const next: Progress = {
    ...p,
    kinds: { ...p.kinds, [kind]: { ...s, sessions: s.sessions + 1, best: s.best === null ? ratio : Math.max(s.best, ratio) } },
  };
  save(next);
  return next;
}

/** A finished timed trial. Returns whether it is a new best. */
export function recordTrial(right: number, total: number, ms: number): { progress: Progress; newBest: boolean } {
  const p = loadProgress();
  // A run with nothing right is never celebrated as a best.
  const newBest = right > 0 && betterTrial({ right, ms }, p.trial.best);
  const next: Progress = {
    ...p,
    trial: { runs: p.trial.runs + 1, best: newBest ? { right, total, ms } : p.trial.best },
  };
  save(next);
  return { progress: next, newBest };
}

export function clearProgress(): Progress {
  const p = emptyProgress();
  save(p);
  return p;
}

/** Test hook: forget the in-memory copy. */
export function _resetProgressMemory() {
  memory = null;
  storageOk = null;
}
