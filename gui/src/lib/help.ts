/** WP-1203 — the help corpus, resolved and placed.
 *
 * `rietx.help` is the one authority for what a name in this package means
 * (root CLAUDE.md), served whole by `GET /api/help`.  This module is the
 * client half: it turns a key into an entry, and an anchor rectangle into a
 * position.  Both are pure functions, deliberately — a popover positioned from
 * `getBoundingClientRect` measures zero under jsdom, so the arithmetic is
 * asserted on numbers here rather than on a layout no test environment has.
 *
 * **A key is `arm:name` and never a bare name.**  The arms have overlapping
 * vocabularies — `seed` is a stage field *and* a search control, `preset` is a
 * search control *and* a plan's own word — so a bare key would resolve by
 * declaration order, which is exactly the property `help_key_for`'s
 * exactly-one-family test exists to avoid one rank down.  `parameters` is the
 * one arm whose name is a glob (`phases.*.cell.a`), which is what
 * `ParameterRow.help_key` carries, so a row's key is
 * `parameters:${row.help_key}`.
 *
 * `help.test.ts` replays the committed corpus `tests/data/gui/help_keys.json`,
 * written from the live registry by `tests/test_gui_help.py` — the fnmatch
 * mechanism (python owns the vocabulary, TypeScript proves it can state it) —
 * and every `<Help for=…>` in the app is crossed against it there.
 */

export interface HelpEntry {
  title: string;
  description: string;
  unit: string | null;
  default: string | null;
  typical: string | null;
  anchor: string | null;
  /** the short words a chip carries where the name itself would not read —
   *  `at bound` for `position_at_bound` (WP-1209); null where the name is
   *  the label */
  label?: string | null;
  /** plans only: the intensity modes the preset is meaningful in */
  modes?: string[];
}

/** One grouped parameter family: an entry plus every glob that reaches it. */
export interface ParameterEntry extends HelpEntry {
  paths: string[];
}

export interface HelpCorpus {
  parameters: ParameterEntry[];
  peak_flags: Record<string, HelpEntry>;
  diagnostics: Record<string, HelpEntry>;
  peak_origins: Record<string, HelpEntry>;
  stage_fields: Record<string, HelpEntry>;
  reader_options: Record<string, HelpEntry>;
  instrument_fields: Record<string, HelpEntry>;
  search_fields: Record<string, HelpEntry>;
  plans: Record<string, HelpEntry>;
  /** keyed `Type.field`, e.g. `RefinementResult.status` (WP-2037) */
  result_fields: Record<string, HelpEntry>;
  /** where the manual lives, so an `anchor` can become a link */
  docs_url: string;
}

/** The arms a key may name, in the order the glossary shows them. */
export const ARMS = [
  "parameters",
  "stage_fields",
  "plans",
  "peak_flags",
  "diagnostics",
  "peak_origins",
  "reader_options",
  "instrument_fields",
  "search_fields",
  "result_fields",
] as const;

export type Arm = (typeof ARMS)[number];

/** `parameters:phases.*.cell.a` for a row that carries the glob alone. */
export function paramKey(helpKey: string | null | undefined): string | null {
  return helpKey ? `parameters:${helpKey}` : null;
}

/** Split a key into its arm and its name, or `null` if it names no arm. */
export function splitKey(key: string): { arm: Arm; name: string } | null {
  const cut = key.indexOf(":");
  if (cut < 1) return null;
  const arm = key.slice(0, cut) as Arm;
  if (!ARMS.includes(arm)) return null;
  return { arm, name: key.slice(cut + 1) };
}

/**
 * The entry a key names, or `null`.
 *
 * `null` covers both "no such arm" and "no such name in it", and the popover
 * renders the same thing for either: the key, and a line saying it is not
 * described yet.  That is WP-1202's failure to report, not this layer's — a
 * client cannot know whether a name is new or misspelled, and guessing between
 * them would put a wrong sentence under a real name.
 */
export function resolve(corpus: HelpCorpus | null, key: string): HelpEntry | null {
  if (!corpus) return null;
  const split = splitKey(key);
  if (!split) return null;
  if (split.arm === "parameters") {
    return corpus.parameters.find((e) => e.paths.includes(split.name)) ?? null;
  }
  return (corpus[split.arm] as Record<string, HelpEntry>)?.[split.name] ?? null;
}

/**
 * The words a chip carries for a corpus key: the entry's `label`, else the
 * name itself (WP-1209).
 *
 * A chip is read at a glance, and `position_at_bound` is not read at a glance;
 * `at bound` is. The fallback is the name rather than nothing, so a corpus that
 * has not landed — or a member it does not describe yet — still draws a chip
 * that says *something true*, and the popover behind it is where "not
 * described yet" belongs. What a label is, is `rietx.help`'s to say.
 */
export function labelFor(corpus: HelpCorpus | null, key: string): string {
  return resolve(corpus, key)?.label ?? splitKey(key)?.name ?? key;
}

/**
 * The manual link for an entry, or `null` where the entry names no chapter.
 *
 * The anchor is `page.html#heading-id` relative to the manual root and the
 * base comes from the same payload (WP-1203), so nothing here knows the site's
 * address — that is `rietx._about.docs_base`'s job and no other file's: the
 * manual of the running version, `<DOCS_URL>/docs/<dev or X.Y>` (WP-1986).
 */
export function manualUrl(corpus: HelpCorpus | null,
                          entry: HelpEntry | null): string | null {
  if (!corpus?.docs_url || !entry?.anchor) return null;
  return `${corpus.docs_url.replace(/\/+$/, "")}/${entry.anchor}`;
}

export interface Rect {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface Placement {
  left: number;
  top: number;
  /** true when the popover sits above its anchor because below did not fit */
  flipped: boolean;
}

/** The gap between the anchor and the popover, and the viewport margin, in px. */
export const HELP_GAP = 6;
export const HELP_MARGIN = 8;

/**
 * Where the popover goes: below the anchor, flipped above when below would
 * leave the viewport, clamped horizontally.
 *
 * Two rules worth stating because neither is obvious from the happy path.
 * **Flipping is decided on fit, not on which half of the screen the anchor is
 * in** — a term near the bottom of a tall panel has room below it in a tall
 * window, and a rule about halves would flip it for nothing.  And **a popover
 * taller than the viewport does not flip**: neither side fits, so it stays
 * below and clamps to the top margin, where its first line is the one visible.
 * Flipping it there would show its last line instead.
 *
 * All coordinates are viewport coordinates, which is what
 * `getBoundingClientRect` returns and what `position: fixed` consumes, so the
 * caller never adds a scroll offset.
 */
export function place(anchor: Rect, viewport: Size, size: Size): Placement {
  const below = anchor.bottom + HELP_GAP;
  const above = anchor.top - HELP_GAP - size.height;
  const fitsBelow = below + size.height <= viewport.height - HELP_MARGIN;
  const fitsAbove = above >= HELP_MARGIN;
  const flipped = !fitsBelow && fitsAbove;

  let top = flipped ? above : below;
  const floor = HELP_MARGIN;
  const ceiling = Math.max(floor, viewport.height - size.height - HELP_MARGIN);
  top = Math.min(Math.max(top, floor), ceiling);

  const rightmost = Math.max(HELP_MARGIN,
                             viewport.width - size.width - HELP_MARGIN);
  const left = Math.min(Math.max(anchor.left, HELP_MARGIN), rightmost);

  return { left, top, flipped };
}
