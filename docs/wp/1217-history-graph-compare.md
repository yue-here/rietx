# WP-1217 — History: the graph and the compare table

Milestone: v1.2 · Status: ✅ 2026-08-28 — the graph reads like a git graph and
the compare table's numbers hold their columns; five rules in `gui/CLAUDE.md`
Depends on: WP-1201

## Goal

The history graph reads like a git graph (an edge runs down its lane and
crosses over exactly one row), and the compare table's numbers hold their
columns, with the difference given both absolute and as a percentage.

## Context

The user: "use a git-style graphical tree design rather than straight lines
connecting the nodes; if nodes are very far away, the shallow line is ugly
and hard to read"; "the numerical column positions can be disrupted based on
how many digits are in the number; control this somehow, perhaps with
scientific notation; the difference value should be given as both absolute
and percentage."

Findings (2026-08-25):

- The graph is a CSS row list (`.node`, `height: var(--row)`, 26 px) over an
  absolutely positioned SVG rail (`History.svelte:205-250, 373-377`); lanes
  are assigned by `layout()` in `lib/history.ts:75-108` (one forward pass;
  a node takes a parent's lane, a fork opens a lane, a merge frees one) and
  `LANE = 14`. `edgePath` (`History.svelte:173-179`) draws a straight line
  within a lane and otherwise **one cubic Bézier spanning the whole vertical
  gap** between the two rows, so a child ten rows below its parent in
  another lane gets the shallow curve the user saw. Merge edges are dashed.
- Compare fires `historyDiff` and `historyCompare` together
  (`History.svelte:137-148`); the diff is `RefinementTree.diff`
  (`history/tree.py:257-273`, only paths differing at `rtol=1e-12`, `None`
  where absent). Rows render `a.toPrecision(7)`, `b.toPrecision(7)` and a
  signed absolute `delta.toPrecision(3)` (`History.svelte:315-324`) in
  74 px columns (`:565-568`); JS picks fixed or exponential per cell, so a
  cell edge and a scale sit in one column at different widths. No
  percentage; the list is cut at 200 rows silently; ranking is by
  `|Δ|/max(|a|,|b|)` (`lib/history.ts:178-194`), which is never shown.
- The per-node Rwp delta badge is a percentage-point difference with a
  glyph for sign (`History.svelte:235-241`); `pct()` at `:181-183`.
- `formatValue(value, esd)` (`lib/table.ts:279-311`) formats to the esd's
  place; a node's params rows carry esds after a fit.

Design: `edgePath` runs vertically in the source lane to the row above the
target and crosses in the last row (or crosses in the first row when the
child's lane opens there, whichever the lane algorithm implies), so no
segment spans more than one row diagonally; lanes get colours from the
OKLab rotation. The compare table formats each side by a per-family place
count (cell 5, coordinates 5, Biso 3, scale exponential), right-aligned
tabular numerals so the decimal points line up within a family; `Δ` absolute
in the same format and `Δ %` relative to `a` (`—` when `a` is 0); "showing 200
of N, ranked by relative change" said out loud.

**No esd is reachable here** (checked 2026-08-28, which is why the design line
above lost its `formatValue` half): `RefinementTree.diff` builds a
`ParameterTable` from each node's stored `Structure`/`Instrument` and reads
`entry.value`, and neither schema carries an esd — a node stores *state*, and
the esds a fit produced live on its `RefinementResult`. Merging them in would
be a new arm on `/api/history/diff`, which is this WP's non-goal. Hence the
place count is the whole answer rather than the fallback.

The three widths this table needs are `lib/history.ts`'s `VALUE_CHARS`,
`PERCENT_CHARS` and `PATH_CHARS`, handed to the CSS as `--w-val`/`--w-pct`/
`--w-path` — WP-1216's rule at this table's scale, and the reason there is no
arithmetic to cross: the formatters *keep* the width (a rendering too long for
its family's places falls back to exponential rather than pushing the column),
which is what `history.test.ts` checks over every family against a spread of
magnitudes.

## Non-goals

- New history verbs; the tree payload's shape.

## Tasks

- [x] `lib/history.ts`: `edgeSegments(edge)` returning the vertical run and
      the one-row crossing; lane colours; `history.test.ts` pins that no
      segment is diagonal over more than one row on a fixture with a
      ten-row gap.
- [x] Compare formatting in `lib/history.ts` (`formatSide`, `formatDelta`,
      `formatPercent`, family place counts); the table on aligned columns;
      the cap notice.
- [x] Browser pass on a tree with a branch and a merge; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1012 (the panel), WP-1029 (OKLab rotation).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**A git graph, and a table whose numbers hold their columns** (WP-1217,
`lib/history.ts`, `panels/History.svelte`, `app.css`). Five rules. **An edge
holds a lane for its whole span** — a *lane* rule, not a drawing one. A
tip-following pass frees a lane the moment its node is drawn, so a later fork
could be handed a lane an edge was still travelling down, and the only way to
draw that edge was a diagonal across the whole gap: the shallow line the user
reported. Reserved, `edgeSegments` steps sideways in exactly one row, and which
end it steps at needs no second rule — the edge leaves the lane that goes on
without it, so a fork crosses below its parent and a merge above its child.
Only a **second** parent is dashed: the first is the lineage `rwpDelta` reads
against, and dashing both put three dashed rows in the middle of the trunk.
Lanes are half a palette in each place — the rotation is `LANE_HUES` (five at
72°, a sixth landing inside the phase palette's floor at `--lane-c`), the
lightness and chroma are `app.css`'s per theme, and `test_gui_palette.py` owns
the distance. **A `ch` column is one column only while every cell in it is one
font at one size**: `ch` is the element's own zero, so a `--text-xs` header sat
inside its own tracks by a growing offset and a non-mono `Δ` widened one by
4 px — the family and the size go on the **row**. **A format is declared per
family and the width is a promise the formatter keeps**: `PLACES` is keyed by
`rietx.help.PARAMETER_HELP`'s own globs and crossed against `help_keys.json`
both ways, so a new family fails until it is given one, and `formatSide` writes
exponentially rather than anything longer than `VALUE_CHARS` — which is why the
three widths are stated once in TypeScript and handed down as
`--w-val`/`--w-pct`/`--w-path` with no arithmetic to cross. Below the sidebar's
clamp the row scrolls rather than squeezes, the path being the column that
gives because it is drawn `rtl` and its leaf survives. **A difference is given
twice and the percentage is of |a|** — measured on a Caglioti V refining from
−0.0002 to +0.0024, a signed denominator printed `+0.002601` beside `-1.30e+3%`,
two marks disagreeing about which way a parameter went — at three significant
figures, because 12 ppm on a cell length is a result and `0.00%` is not a way to
say it. And **only the Rwp badge may be green**: `.better` was on every compare
row with a non-zero delta, and a parameter difference has no good direction.

## Handover log

- **2026-08-28** — The history panel now draws a graph a person can follow and
  a table a person can read down. Before this, a branch that forked from a node
  ten rows up was one long shallow curve, which reads as a slope rather than as
  "this came from that"; and the compare table's four numeric cells were each
  formatted independently, so a column could hold a decimal point on one row and
  an exponent on the next. Both are fixed at their causes rather than their
  symptoms — a lane is now reserved for an edge's whole span, which is what makes
  a one-row sideways step drawable at all, and each parameter family declares its
  own number of decimal places, with the formatter guaranteeing the column's
  width rather than the CSS hoping for it. The difference is now given twice,
  absolute and as a percentage, which is what makes a 12 ppm cell shift legible
  next to a background term that doubled. Nothing about the history *model*
  changed: no new verb, no new route, no change to what a node holds.

  **Done.** All three checklist items. `layout` assigns lanes by **arc** (one
  parent→child edge holding a lane from the parent's row to the child's) instead
  of by tip; `edgeSegments` returns the vertical run and the one-row crossing;
  `LANE_HUES` + `laneColor` compose a lane's ink against `app.css`'s new
  `--lane-l`/`--lane-c` (three theme blocks). The compare table gets `PLACES`,
  `formatFor`, `formatSide`, `formatDelta`, `formatPercent`, `DIFF_CAP` and the
  three width constants, a sticky header naming the two nodes, and a notice that
  states the cap and the ranking. `tests/test_gui_palette.py` grew the lane
  arithmetic; its module docstring now says it covers the GUI's colours rather
  than the plot's.

  **Measured** (`[dev]` venv — numpy + numba, no jax/torch — darwin/arm64,
  nothing else mid-suite):

  - vitest 572 → **583 passed, 21 files**, ~9.4-9.8 s. All eleven are in
    `history.test.ts` (9 → 20); the App-level compare test grew assertions
    rather than cases.
  - `tests/test_gui_palette.py` 10 → **15 collected**, +5 (two parametrized ×
    two themes, plus the twice-declared-and-agrees check). Fast selection
    **3206 passed, 122 skipped** in 2:11; no new skip.
  - The full selection did **not** run: GUI-only plus one test file, which is
    `tests/CLAUDE.md`'s rung-3 exemption.
  - Browser (Chrome 1223, a 12-node fixture with a six-row fork, a merge and a
    second fork): rail 34 px, 12 edge paths, every crossing one row. Compare
    columns right-aligned at 1252/1335/1417/1492 on every row including the
    header. At a 1500 px window (sidebar 559) the row does not overflow; at a
    1000 px window (sidebar 380) it overflows by 34 px and scrolls, which is
    the designed give.

  **Gotchas**, all three found in the browser and none reachable from jsdom:

  - `ch` is the **element's own** zero. A `--text-xs` header inside `--w-val`
    tracks sat at 1266/1341/1420 against the body's 1252/1335/1417, and a `Δ`
    cell without `mono` widened its track by a further 4 px. The family and the
    size now sit on `.drow`, not on each cell — the rule is in `gui/CLAUDE.md`.
  - A percentage of a **signed** `a` disagrees with its own Δ: a Caglioti V
    refining −0.0002 → +0.0024 printed `+0.002601` beside `-1.30e+3%`. It is
    of |a| now.
  - Dashing both of a merge's edges was harmless while they were short curves
    and puts three dashed rows down the trunk once the runs are vertical. Only
    a **second** parent is dashed.

  Two design points a successor should not re-litigate. **No esd is reachable
  in a history diff** — `RefinementTree.diff` reads values off a
  `ParameterTable` built from each node's stored schemas, and neither carries
  one — so the `formatValue`-with-esd half of this WP's design line was struck
  rather than implemented. And the client **does** match a path to a family
  here, through `lib/fnmatch.ts`, against `help.py`'s rule that the server owns
  the match: licensed because this is a display choice (a wrong match shows a
  digit too many, it decides nothing), and pinned by crossing `PLACES` against
  `help_keys.json` both ways.

  **The review pass** (`/code-review medium --fix`) raised three and all three
  were real, none declined. The committed dist was stale and `test_gui_dist.py`
  red — the digest covers `.test.ts` files, so a commit that only edits a test
  still needs a rebuild, which is worth carrying: **build after the last source
  edit, test files included.** The sticky compare header was not opaque across a
  horizontal scroll, the exact failure its own comment claimed to prevent; the
  offered `min-width: min-content` removed that and introduced another (a row as
  wide as its own longest path, so rows disagree with each other and with the
  header, and the path stops ellipsising — measured at a 380 px sidebar, header
  421 px against a body row's 476), so the floor is the row's declared columns
  composed in CSS from the same custom properties instead. And the ROADMAP index
  row was `✅` with no date. The pass also fuzzed the new lane assignment over
  3000 random DAGs against segment continuity, the one-row bound and "no vertical
  run crosses a foreign dot" and found nothing, which is the reassurance three
  hand-written fixtures could not give.

  **Next:** [1017](1017-gui-manual-onboarding.md), the GUI manual and the
  in-app help anchors — the last of v1.2, and now unblocked, this having been
  the last of the triage. Nothing here is owed to it beyond the two widths its
  screenshots will be taken at (1256 px is where the model pane stacks; the
  compare row fits a 559 px sidebar and side-scrolls a 380 px one).

- **2026-08-25** — created from the v1.2 triage.
