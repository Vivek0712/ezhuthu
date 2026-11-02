/**
 * A name that must never appear in user-visible copy. It is stored encoded so that the name itself
 * does not appear in this public repository; the tests decode it and match it case-insensitively.
 */
export const BANNED_NAME = atob('YWl2YXI=');

/** True when `text` contains the banned name (any case). */
export const mentionsBannedName = (text: string | null | undefined): boolean =>
  (text ?? '').toLowerCase().includes(BANNED_NAME);
