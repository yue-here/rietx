/** The `.rxt` highlighter — a per-line scanner, and deliberately not a parser.
 *
 * WP-1009 put the parser on the server and said why: one grammar, one
 * implementation, no drift. So this module colours text and has **no notion of
 * validity**. There is no `error` token in {@link TOKENS} and no way to add one
 * without changing that list, which is what stops the pane from telling a user
 * their document is wrong when only `PUT /api/textdoc` can know that.
 *
 * What it does share with the parser is a *vocabulary* — the keywords, the flag
 * words, the annotation words. That is a real duplication, so it is held to
 * Python by `tests/test_textdoc.py::test_the_highlighter_quotes_the_parsers_words`,
 * which reads the four arrays below out of this file and compares them to
 * `textdoc._KEYWORDS` and friends. A divergence there is a word rendered in the
 * wrong colour, never a wrong edit — the same "preview only" bargain
 * `lib/fnmatch.ts` makes with `fnmatch.fnmatchcase`.
 */

/** Every token this scanner can emit. No `error`, on purpose — see the module docstring. */
export const TOKENS = ["keyword", "vary", "number", "string", "comment",
                       "annotation", "flag", "operator", "path"] as const;

export type Token = (typeof TOKENS)[number];

/** Line-opening words. Mirrors `textdoc._KEYWORDS` (reserved blocks included). */
export const KEYWORDS = ["rxt", "project", "pattern", "mode", "limits", "excluded",
                         "plan", "guard", "tolerance", "stage", "phase",
                         "instrument", "peaks"];

/** Words that describe a parameter rather than annotate it. `textdoc._FLAG_WORDS`. */
export const FLAGS = ["locked", "mode-fixed", "softplus", "logit"];

/** The peaks block's flag column (WP-1027). Mirrors `textdoc._PEAK_FLAG_WORDS`,
 * which quotes the schema's closed `PeakFlag` vocabulary — a new flag word is a
 * failing parity test until it is restated here, by design. */
export const PEAK_FLAGS = ["ghost_kbeta", "ghost_tungsten", "excluded",
                           "fit_failed", "sigma_assumed", "unresolved_shoulder",
                           "position_at_bound", "asymmetry_unmodelled",
                           "not_separable", "background_extrapolated",
                           "axial_tail", "kalpha2_residual", "no_intensity",
                           "unnamed_neighbour"];

/** `name value` annotations on a parameter row. `textdoc._PAIR_WORDS`. */
export const PAIRS = ["min", "max", "esd"];

/** The words a `stage` line carries: `free`, then `textdoc.STAGE_KEYS` — which
 * is derived from `StageSpec`, so a new field lands here and nowhere else. */
export const STAGE_WORDS = ["free", "max_iter", "ftol", "lebail_cycles", "seed",
  "strain_seed", "restraint_weight_scale", "window_slack_deg"];

/** Of those, the ones `StageSpec` types as `int`. `textdoc.STAGE_INT_KEYS`. */
export const STAGE_INT_WORDS = ["max_iter", "lebail_cycles"];

/** Of those, the ones `StageSpec` lets be `None`. An emptied box is `null` for
 * these and a refusal for the rest, which is what lets the plan editor offer
 * every stage field the `.rxt` document already carries (WP-1208). All three
 * arrays are pinned to `StageSpec` from python by `tests/test_textdoc.py`. */
export const STAGE_NULLABLE_WORDS = ["ftol", "window_slack_deg"];

export interface Span {
  /** column offsets into the line, `from` inclusive and `to` exclusive */
  from: number;
  to: number;
  token: Token;
}

// `inf`/`nan` are values, not names: `_fmt_bound` renders an infinite bound as
// the bare word, so it has to read as a number or every unbounded row looks
// like it names a parameter called `inf`.
const NON_FINITE = /^[-+]?(?:inf|nan)(?![A-Za-z0-9_])/i;
const NUMBER = /^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?/;
// dot-paths and globs are one word: `phases.*.atoms.0.dof.1` must not colour as
// six things, and `mode-fixed` is hyphenated
const WORD = /^[A-Za-z_][A-Za-z0-9_.*?-]*/;
const OPERATORS = "=+·,";

/**
 * The coloured spans of one line, left to right, with gaps where nothing is claimed.
 *
 * A keyword only counts as one when it opens the line, so the `mode` in
 * `instrument.mode` and the `plan` in a comment stay plain. Everything the
 * scanner does not recognise simply gets no span rather than an error token.
 */
export function spans(line: string): Span[] {
  const out: Span[] = [];
  let i = 0;
  // Indentation is the parser's own dispatch: `textdoc.parse` sends any line
  // starting with whitespace to `_parse_row` without looking at its first word,
  // so an indented `plan` is a parameter called `plan`, not a keyword.  Getting
  // this wrong would colour rows as settings inside every block.
  let opening = !/^\s/.test(line);
  while (i < line.length) {
    const ch = line[i];
    if (ch === " " || ch === "\t") {
      i++;
      continue;
    }
    if (ch === "#") {
      // to end of line: a comment is the last thing on a line by construction
      out.push({ from: i, to: line.length, token: "comment" });
      break;
    }
    if (ch === '"') {
      let j = i + 1;
      while (j < line.length && line[j] !== '"') j++;
      const to = Math.min(j + 1, line.length);
      out.push({ from: i, to, token: "string" });
      i = to;
      opening = false;
      continue;
    }
    if (ch === "@") {
      out.push({ from: i, to: i + 1, token: "vary" });
      i += 1;
      opening = false;
      continue;
    }
    if (OPERATORS.includes(ch)) {
      out.push({ from: i, to: i + 1, token: "operator" });
      i += 1;
      opening = false;
      continue;
    }
    const rest = line.slice(i);
    const numeric = NON_FINITE.exec(rest) ?? NUMBER.exec(rest);
    if (numeric) {
      out.push({ from: i, to: i + numeric[0].length, token: "number" });
      i += numeric[0].length;
      opening = false;
      continue;
    }
    const word = WORD.exec(rest);
    if (word) {
      out.push({ from: i, to: i + word[0].length, token: classify(word[0], opening) });
      i += word[0].length;
      opening = false;
      continue;
    }
    i += 1; // an unrecognised byte: no span, no opinion
  }
  return out;
}

function classify(word: string, opening: boolean): Token {
  if (opening && KEYWORDS.includes(word)) return "keyword";
  // `excluded` is both a top-level keyword and a peak flag; `opening` has
  // already separated them by the parser's own dispatch (indentation)
  if (FLAGS.includes(word) || PEAK_FLAGS.includes(word)) return "flag";
  if (PAIRS.includes(word) || STAGE_WORDS.includes(word)) return "annotation";
  return "path";
}

/** How many lines carry a `#` comment — the count the pane warns about.
 *
 * A re-render discards the user's own comments (WP-1009 refused to store them:
 * that would be a second authority for something regenerated from state), so the
 * pane has to say so *before* it replaces the buffer. Counting whole lines
 * rather than `#` characters keeps a `#` inside a quoted project name out of it.
 */
export function commentLines(text: string): number {
  let n = 0;
  for (const line of text.split("\n")) {
    if (spans(line).some((span) => span.token === "comment")) n += 1;
  }
  return n;
}
