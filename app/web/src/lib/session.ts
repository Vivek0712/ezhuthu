const KEY = 'ezhuthu.session_id';

export function getSessionId(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setSessionId(id: string): void {
  try {
    window.localStorage.setItem(KEY, id);
  } catch {
    /* storage blocked: progress is still visible during this visit via state */
  }
}
