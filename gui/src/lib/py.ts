/**
 * A JSON value written as the Python literal it stands for, spaced as
 * Python's `repr` spaces it: `{"instrument.zero_shift": 0.01}`, `[10, 12]`.
 *
 * Every Console echo that holds a dict or a list goes through this (the
 * maintainer's look of 2026-11-22, WP-2212): an echo is a line of a Python
 * script, so it reads as one. `JSON.stringify` alone writes `{"a":1}`, and
 * `true`, `false` and `null`, which Python cannot run.
 *
 * Strings keep JSON's double quotes. Every escape JSON writes (`\"`, `\\`,
 * `\n`, `\uXXXX`) means the same in a Python string. A non-finite number,
 * which JSON cannot carry, is written as the `float(...)` call Python needs.
 */
export function py(value: unknown): string {
  if (value === null || value === undefined) return "None";
  if (value === true) return "True";
  if (value === false) return "False";
  if (typeof value === "number") {
    if (Number.isFinite(value)) return String(value);
    return Number.isNaN(value) ? 'float("nan")' : value > 0 ? 'float("inf")' : 'float("-inf")';
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(py).join(", ")}]`;
  // a key holding undefined is dropped, as JSON.stringify drops it from the
  // request body the echo stands for
  if (typeof value === "object")
    return `{${Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${JSON.stringify(k)}: ${py(v)}`).join(", ")}}`;
  return String(value);
}
