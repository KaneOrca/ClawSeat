/**
 * Coerce a value to a string, defaulting to '' if null/undefined.
 * Use at API data boundaries to prevent .toUpperCase() / .split() / etc crashes.
 */
export function safeStr(val: unknown): string {
  if (val == null) return '';
  return String(val);
}
