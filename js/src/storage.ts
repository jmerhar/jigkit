/**
 * The browser's storage, read and written so that a refusal never breaks the page.
 *
 * Storage can be missing or refuse every access (a private window, blocked site data), so each
 * read falls back to nothing and each write is allowed to fail: the page keeps working, and simply
 * forgets the choice when it is reloaded.
 */

/** The browser's local storage, or undefined where reading it is refused. */
export function browserStorage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

/** The value kept under `key`, or null when there is none or storage refuses. */
export function readStored(key: string, storage: Storage | undefined = browserStorage()): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

/**
 * Keep `value` under `key`, or forget the key when `value` is null. Returns whether storage took
 * the change; a refusal is not an error.
 */
export function keepStored(
  key: string,
  value: string | null,
  storage: Storage | undefined = browserStorage(),
): boolean {
  if (!storage) return false;
  try {
    if (value === null) storage.removeItem(key);
    else storage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

/** The value kept under `key` if it is one of `allowed`, else null. */
export function readChoice<T extends string>(
  key: string,
  allowed: readonly T[],
  storage: Storage | undefined = browserStorage(),
): T | null {
  const value = readStored(key, storage);
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : null;
}
