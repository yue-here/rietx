/** The history DAG's geometry and labels, as pure functions.
 *
 * The panel is a *view* over `GET /api/history` — no new history semantics, and
 * no graph library: this DAG is thirty nodes of one project, so lane assignment
 * is a dozen lines and drawing it is a handful of straight SVG segments per
 * edge.  Separated from the component for the reason the parameter table's
 * logic is: "which lane does this node sit in" and "what does this node's badge
 * say" are questions with answers that can be asserted without a DOM.
 *
 * Two facts from the server shape everything here.  The node list arrives in
 * `tree.order`, which is **insertion order and therefore topological** — ids are
 * sequential and a parent is always appended before its children — so lanes can
 * be assigned in one forward pass with no sorting.  And a node carries no state:
 * `rwp`/`gof`/`n_free` are its cached metrics and a parameter value is not in the
 * payload at all, which is why the compare view asks `/api/history/diff` instead
 * of subtracting two node states the client does not have.
 */

import { fnmatch } from "./fnmatch";
import { num } from "./table";

export interface HistoryNode {
  id: string;
  parents: string[];
  children: string[];
  label: string;
  created_utc: string;
  kind: string;
  name: string;
  action: Record<string, any>;
  api_call: string;
  status: string | null;
  n_iterations: number | null;
  rwp: number | null;
  gof: number | null;
  n_free: number | null;
  n_diagnostics: number;
  diagnostics: Array<{ level: string; code: string; message: string; where: string[] }>;
  tags: string[];
  scores: Record<string, number>;
  notes: Record<string, string>;
}

export interface Placed {
  node: HistoryNode;
  /** index into the node list, top to bottom */
  row: number;
  /** which vertical rail the node's dot sits on */
  lane: number;
}

export interface Edge {
  from: string;
  to: string;
  fromRow: number;
  toRow: number;
  fromLane: number;
  toLane: number;
  /** the lane this edge's vertical run occupies, held from `fromRow` to `toRow` */
  lane: number;
  /**
   * True where `from` is not `to`'s **first** parent — drawn dashed.
   *
   * Not "`to` is a merge", which dashed both of a merge's edges and, once the
   * runs became long, put three dashed rows in the middle of the trunk.  The
   * first parent is the lineage `Refinement.lineage` follows and the one
   * `rwpDelta` reads against; a second is a rival strategy that was folded in,
   * and that is the edge worth marking.
   */
  merge: boolean;
}

/** One straight piece of an edge, in (lane, row) coordinates.
 *
 * Either a vertical run (`fromLane === toLane`) or a crossing over exactly one
 * row.  Nothing else exists — see {@link edgeSegments}. */
export interface Segment {
  fromLane: number;
  fromRow: number;
  toLane: number;
  toRow: number;
}

/**
 * Assign every node a row and a lane, git-graph style.
 *
 * A lane is a branch being continued, and the thing that holds one is an
 * **arc**: one parent→child edge, which claims a lane at the parent's row and
 * gives it up at the child's.  That reservation is the whole difference from a
 * tip-following pass (WP-1217).  A tip is free the moment its node is drawn, so
 * a lane could be handed to a new branch while an edge was still due to travel
 * down it, and the drawing was then left choosing between a line through other
 * people's nodes and a diagonal across ten rows.  Reserving the lane for the
 * arc's whole span removes the choice: every edge has a clear lane to run in,
 * and {@link edgeSegments} never has to lean sideways over more than one row.
 *
 * A node's own lane is the leftmost arc arriving at it, so a merge lands in the
 * lane of its first parent and frees the rest.  A node's **first** child
 * continues its lane and every later one opens a fresh one — which is exactly
 * where a fork appears in this DAG, there being no moving refs here (only `head`
 * and tags, WP-1008), so a lane is a *drawn* thing rather than a named one.
 * Lanes a merge freed are reused, so a long log does not widen forever; a lane
 * an arc is still travelling down is not free and is not reused.
 */
export function layout(nodes: readonly HistoryNode[]) {
  const rowOf = new Map(nodes.map((node, row) => [node.id, row]));

  // parent → its children, in row order: `nodes` is topological, so the first
  // child appended is the nearest one below, and it is the one that keeps the lane
  const kids = new Map<string, string[]>();
  for (const child of nodes) {
    for (const parent of child.parents) {
      if (!rowOf.has(parent)) continue;   // a parent outside this payload: invent nothing
      const list = kids.get(parent);
      if (list) list.push(child.id);
      else kids.set(parent, [child.id]);
    }
  }

  const held: Array<Edge | null> = [];    // lane → the arc travelling down it
  const placed: Placed[] = [];
  const edges: Edge[] = [];
  const free = () => {
    const at = held.indexOf(null);
    return at === -1 ? held.length : at;
  };

  nodes.forEach((node, row) => {
    const arriving: number[] = [];
    held.forEach((arc, at) => { if (arc && arc.to === node.id) arriving.push(at); });
    const lane = arriving.length ? arriving[0] : free();
    for (const at of arriving) held[at] = null;
    held[lane] = null;
    placed.push({ node, row, lane });

    (kids.get(node.id) ?? []).forEach((id, k) => {
      const own = k === 0 ? lane : free();  // the first child continues the lane
      const arc: Edge = {
        from: node.id, to: id,
        fromRow: row, toRow: rowOf.get(id) as number,
        fromLane: lane, toLane: -1,       // the child's lane is known once it is placed
        lane: own, merge: false,
      };
      held[own] = arc;
      edges.push(arc);
    });
  });

  const laneOf = new Map(placed.map((p) => [p.node.id, p.lane]));
  const parents = new Map(nodes.map((n) => [n.id, n.parents]));
  for (const edge of edges) {
    edge.toLane = laneOf.get(edge.to) as number;
    edge.merge = (parents.get(edge.to) as string[]).indexOf(edge.from) > 0;
  }
  return { placed, edges, lanes: Math.max(1, held.length) };
}

/**
 * An edge as straight pieces: at most one crossing, and it spans one row.
 *
 * The complaint this answers is that a child ten rows below its parent in
 * another lane was drawn as a single curve across the whole gap — a shallow
 * diagonal that is hard to follow and reads as a slope rather than a relation.
 * A git graph does not do that: a line runs down its lane and steps sideways
 * once.  *Which* end it steps at follows from {@link layout}'s reservation and
 * needs no second rule — the edge steps out of the lane it does not hold and
 * runs down the one it does, so a fork crosses in the row below its parent (the
 * parent's lane belongs to an earlier child) and a merge crosses in the row
 * above its child (the child's lane belongs to its first parent).
 *
 * Adjacent rows are the one shape with no vertical run: the crossing *is* the
 * edge, and it still spans one row.
 */
export function edgeSegments(edge: Edge): Segment[] {
  const { fromLane, fromRow, toLane, toRow, lane } = edge;
  if (toRow - fromRow <= 1 || (lane === fromLane && lane === toLane)) {
    return [{ fromLane, fromRow, toLane, toRow }];
  }
  const out: Segment[] = [];
  let top = fromRow;
  if (lane !== fromLane) {
    out.push({ fromLane, fromRow, toLane: lane, toRow: fromRow + 1 });
    top = fromRow + 1;
  }
  const bottom = lane === toLane ? toRow : toRow - 1;
  if (bottom > top) out.push({ fromLane: lane, fromRow: top, toLane: lane, toRow: bottom });
  if (lane !== toLane) out.push({ fromLane: lane, fromRow: toRow - 1, toLane, toRow });
  return out;
}

/**
 * The hues a lane's ink rotates through, in degrees of OKLCh.
 *
 * Five, 72° apart from `--accent`'s blue, and the count *is* the separation:
 * rotating hue at constant lightness and chroma (WP-1029's rule — sRGB has no
 * distance, so the rotation happens where one is approximately perceptual) puts
 * two lanes 2·C·sin(Δh/2) apart, which at `app.css`'s `--lane-c` clears the
 * phase palette's 0.13 floor at 72° and misses it at 60°.  Six lanes would have
 * been six colours a reader cannot tell apart; a sixth lane repeats the first
 * instead, which is a collision the reader can see is one.
 * `tests/test_gui_palette.py` holds the arithmetic, in Python because
 * `structure3d._oklab_distance` is the one distance this package has.
 *
 * The lightness and chroma are `app.css`'s, per theme, so nothing here learns a
 * colour: this module owns the rotation and not the ink.
 */
export const LANE_HUES = [250, 322, 34, 106, 178] as const;

/** A lane's ink — {@link LANE_HUES} composed against the theme's L and C. */
export function laneColor(lane: number): string {
  const n = LANE_HUES.length;
  return `oklch(var(--lane-l) var(--lane-c) ${LANE_HUES[((lane % n) + n) % n]})`;
}

/** What a node's row says it is — the action, not the id.
 *
 * `set_vary` prints how many paths it moved rather than the paths themselves: a
 * bulk free is one node carrying a glob's worth of hits (WP-1011), and the glob
 * is on the node's `api_call` for anyone who wants it. */
export function nodeLabel(node: HistoryNode): string {
  const action = node.action ?? {};
  const on = (action.turn_on ?? []).length;
  const off = (action.turn_off ?? []).length;
  switch (node.kind) {
    case "root":
      return "root";
    case "stage":
      return node.name || "stage";
    case "set_vary":
      return on ? `free ${on} path${on === 1 ? "" : "s"}`
                : `fix ${off} path${off === 1 ? "" : "s"}`;
    case "set_value": {
      const n = Object.keys(action.values ?? {}).length;
      return `set ${n} value${n === 1 ? "" : "s"}`;
    }
    case "edit_model":
      return node.name || node.label || "model edited";
    default:
      return node.kind;
  }
}

/** A chip's tone, from the app's one vocabulary (`app.css`). */
export type Tone = "note" | "ok" | "warn" | "bad" | "accent";

/**
 * The Le Bail alternation's mark on a node (WP-1323), as a chip.
 *
 * `Refinement.fit` writes it into the node's own `notes`: `lebail_pass` on
 * every node a pass created, then `lebail_kept` (`"k of N"`) or
 * `lebail_discarded` once the passes have stopped.  So this reads a fact the
 * tree already carries and invents no history semantics.  One chip, its
 * **tone** saying what became of the pass (`ok` kept, `warn` discarded, `note`
 * while the run is still going): a second chip for the verdict took the
 * name column's room on every node of a six-stage pass, and the words are in
 * the chip's `title` and {@link passVerdict}.  The text is plain rather than a
 * `help.py` entry because it names a *note key* on a node, which is no
 * parameter, flag or field vocabulary, and nothing else reads it.  A node with
 * no such note answers an empty list, which is every node of every fit that
 * was not an alternation.
 */
export function passChips(node: HistoryNode): Array<{ text: string; tone: Tone; title: string }> {
  const notes = node.notes ?? {};
  if (!notes.lebail_pass) return [];
  const tone: Tone = notes.lebail_kept ? "ok" : notes.lebail_discarded ? "warn" : "note";
  return [{ text: `pass ${notes.lebail_pass}`, tone, title: passVerdict(node) }];
}

/** What became of the node's pass, in words, or `""` for a node no pass made. */
export function passVerdict(node: HistoryNode): string {
  const notes = node.notes ?? {};
  if (!notes.lebail_pass) return "";
  if (notes.lebail_kept) {
    return `pass ${notes.lebail_pass} of the Le Bail alternation, kept (${notes.lebail_kept}); the head stands in it`;
  }
  if (notes.lebail_discarded) {
    return `pass ${notes.lebail_pass} of the Le Bail alternation, not kept; its nodes stay in the tree`;
  }
  return `pass ${notes.lebail_pass} of the Le Bail alternation`;
}

/** True for a node of a pass the alternation did not keep. */
export function isDiscarded(node: HistoryNode): boolean {
  return Boolean(node.notes?.lebail_discarded);
}

/**
 * Rwp change against the node's first parent, or `null` when either lacks one.
 *
 * Against the *first* parent because that is the lineage `Refinement.lineage`
 * follows, and because a merge's second parent is a rival strategy rather than a
 * predecessor — reading "improved by 0.03" against a branch nobody was on would
 * be a comparison of two different things.
 *
 * A node's metrics are **as-optimised**: measured on the model the stage *started*
 * from (CLAUDE.md), so a small disagreement with a replay is a staleness signal
 * and not a regression — which is why this returns the difference and nothing
 * about whether it is significant.
 */
export function rwpDelta(node: HistoryNode,
                         by: Map<string, HistoryNode>): number | null {
  if (node.rwp === null || node.rwp === undefined) return null;
  const parent = by.get(node.parents[0] ?? "");
  if (!parent || parent.rwp === null || parent.rwp === undefined) return null;
  return num(node.rwp) - num(parent.rwp);
}

export interface DiffRow {
  path: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  /** |Δ| relative to the larger magnitude — what the rows are ranked by */
  relative: number;
}

/**
 * `GET /api/history/diff`'s payload as ranked rows.
 *
 * The route returns **only** the paths that differ (`RefinementTree.diff` at
 * rtol 1e-12), so there is no changed-only filter to offer here — every row is a
 * change, and the panel says so rather than showing a toggle that does nothing.
 * A path present in one node and absent in the other (a phase added, an ADP block
 * declared) comes back with a `null` on that side and sorts to the top, because
 * a parameter appearing is a bigger event than one moving.
 */
export function diffRows(diff: Record<string, Array<number | string | null>>,
                         query = ""): DiffRow[] {
  const want = query.trim().toLowerCase();
  const rows: DiffRow[] = [];
  for (const [path, pair] of Object.entries(diff ?? {})) {
    if (want && !path.toLowerCase().includes(want)) continue;
    const a = pair?.[0] == null ? null : num(pair[0]);
    const b = pair?.[1] == null ? null : num(pair[1]);
    const delta = a === null || b === null ? null : b - a;
    const scale = Math.max(Math.abs(a ?? 0), Math.abs(b ?? 0), 1e-30);
    rows.push({
      path, a, b, delta,
      relative: delta === null ? Infinity : Math.abs(delta) / scale,
    });
  }
  return rows.sort((x, y) => y.relative - x.relative || x.path.localeCompare(y.path));
}

/** How many rows the compare table draws, however many differ. */
export const DIFF_CAP = 200;

/** How a family's numbers are written: decimal places, or `"exp"`. */
export type Format = number | "exp";

/**
 * The decimal places each parameter family is written to (WP-1217).
 *
 * The complaint was that the numbers do not hold their columns, and the cause
 * is that `toPrecision` chooses fixed or exponential **per value**: two rows of
 * one family came out at two widths, so a decimal point and a mantissa shared a
 * column.  A place count per family fixes the width, and the count is chosen to
 * resolve the smallest move the family actually makes — a cell length shifts
 * 10-1000 ppm on 3-40 Å, so five places show a 2 ppm move and a sixth would show
 * the solver's noise.  The two families whose values span orders of magnitude
 * instead — a phase scale and an extinction coefficient, both of which reach
 * 1e-6 and neither of which has a natural place count — are exponential, which
 * is a fixed width too.  A background term is *not*: measured on the FAP
 * example its six coefficients run 159 to -15, and `-1.5321e+1` is a worse way
 * to write -15.321 than three places are.
 *
 * The keys are `rietx.help.PARAMETER_HELP`'s own family globs, and
 * `history.test.ts` crosses them against `tests/data/gui/help_keys.json` **both
 * ways** — so a new parameter family fails here until it is given a format, and
 * a renamed one cannot leave an entry behind describing a name that is gone.
 * That is the only reason a client matches a path to a family at all: the server
 * owns the match wherever it *decides* something (`help_key_for`, and
 * `ParameterRow.help_key` carries the answer), and the diff payload is paths and
 * numbers.  A wrong match here shows a digit too many, which is why a preview
 * matcher (`lib/fnmatch.ts`, held to Python by its own corpus) is enough.
 */
export const PLACES: Readonly<Record<string, Format>> = {
  "instrument.background.air": 3,
  "instrument.background.c*": 3,
  "instrument.background.scale": 4,
  "instrument.extra_components.*.area": 3,
  "instrument.extra_components.*.center": 4,
  "instrument.extra_components.*.eta": 4,
  "instrument.extra_components.*.fwhm": 4,
  "instrument.extra_components.*.height": 3,
  "instrument.extra_components.*.position": 4,
  "instrument.geometry.axial_hl": 5,
  "instrument.geometry.axial_sl": 5,
  "instrument.geometry.capillary_offset_across_beam": 5,
  "instrument.geometry.capillary_offset_along_beam": 5,
  "instrument.geometry.sample_displacement": 5,
  "instrument.geometry.sample_transparency": 5,
  "instrument.geometry.surface_roughness.a": 4,
  "instrument.geometry.surface_roughness.b": 4,
  "instrument.geometry.surface_roughness.c": 4,
  "instrument.geometry.surface_roughness.tau": 5,
  "instrument.polarization": 4,
  "instrument.profile.u": 6,
  "instrument.profile.v": 6,
  "instrument.profile.w": 6,
  "instrument.profile.x": 6,
  "instrument.profile.y": 6,
  "instrument.source.lines.*.wavelength": 6,
  "instrument.source.lines.*.weight": 4,
  "instrument.zero_shift": 5,
  "phases.*.atoms.*.adp.*": 5,
  "phases.*.atoms.*.biso": 3,
  "phases.*.atoms.*.dof.*": 5,
  // WP-1327: crystal-axis components and the modulus in μ_B, whose esd is a
  // few hundredths on real data (2.078 ± 0.066 on Cr₂WO₆ at 4 K), so three
  // places show a move the fit resolves; the angle DOFs are radians, which
  // four places write to 0.006°
  "phases.*.atoms.*.moment.crystalaxis_*": 3,
  "phases.*.atoms.*.moment.dof*": 4,
  "phases.*.atoms.*.occ": 4,
  "phases.*.atoms.*.u11": 5,
  "phases.*.atoms.*.u12": 5,
  "phases.*.atoms.*.u13": 5,
  "phases.*.atoms.*.u22": 5,
  "phases.*.atoms.*.u23": 5,
  "phases.*.atoms.*.u33": 5,
  "phases.*.atoms.*.x": 5,
  "phases.*.atoms.*.y": 5,
  "phases.*.atoms.*.z": 5,
  "phases.*.cell.a": 5,
  "phases.*.cell.alpha": 5,
  "phases.*.cell.b": 5,
  "phases.*.cell.beta": 5,
  "phases.*.cell.c": 5,
  "phases.*.cell.gamma": 5,
  "phases.*.extinction": "exp",
  "phases.*.gauss_size": 6,
  "phases.*.gauss_strain": 6,
  "phases.*.lor_size": 5,
  "phases.*.lor_strain": 5,
  // WP-1343: the magnetic component's own Lorentzian pair, in the same deg 2θ
  // as the nuclear one above, so the same five places
  "phases.*.magnetic_lor_size": 5,
  "phases.*.magnetic_lor_strain": 5,
  "phases.*.microstrain.dof.*": 3,
  "phases.*.microstrain.s*": 3,
  "phases.*.preferred_orientation.r": 4,
  // WP-1805: a rigid body's origin is fractional like an atom's x, y, z, and
  // its rotation increment is radians, which four places write to 0.006°
  "phases.*.rigid_bodies.*.origin.dof.*": 5,
  "phases.*.rigid_bodies.*.origin.x": 5,
  "phases.*.rigid_bodies.*.origin.y": 5,
  "phases.*.rigid_bodies.*.origin.z": 5,
  "phases.*.rigid_bodies.*.rotation.*": 4,
  // WP-1808: a torsion's increment is degrees, like a cell angle
  "phases.*.rigid_bodies.*.torsions.*.twist": 3,
  "phases.*.scale": "exp",
};

/**
 * The column's promise, in characters — and the formatters keep it.
 *
 * The value columns are `VALUE_CHARS` wide in `ch`, which is one digit of the
 * mono family, so a rendering longer than this would push the column rather than
 * sit in it.  A family's fixed form can be longer than its place count suggests
 * (a background term of 1e5 at three places is thirteen characters), so
 * {@link formatSide} falls back to exponential rather than overflowing, and
 * `history.test.ts` checks every family against a spread of magnitudes.  Eleven
 * is what the widest declared rendering needs: a signed exponential
 * (`-1.2345e-7`) or a signed angle at five places (`-123.45678`).
 */
export const VALUE_CHARS = 11;

/** The same promise for the `Δ %` column: `+1.23e+2%` is nine. */
export const PERCENT_CHARS = 10;

/**
 * How much of the path is kept when the panel is too narrow for all of it.
 *
 * The three widths together are the row's floor, which is why all three are
 * stated here and handed to the CSS rather than written in it (WP-1215's rule,
 * WP-1216's arithmetic): 12 + 3·11 + 10 characters and four gaps is wider than
 * the sidebar's 340 px clamp, so past that the rows scroll sideways instead of
 * squeezing the numbers out of their columns.  The path is the column that
 * gives, because it is the one whose ends are still readable when it does —
 * it is drawn `rtl`, so what survives is the leaf, and the whole path is on the
 * row's `title`.
 */
export const PATH_CHARS = 12;

/** The format the path's family declares, exponential where none does.
 *
 * A path outside `PLACES` cannot arrive from a `ParameterTable` — the corpus
 * test is what makes that true — so the fallback is for a payload from a build
 * this one does not know.  Exponential, because it is the form that states its
 * own precision and cannot silently round a value it has no place count for. */
export function formatFor(path: string): Format {
  const exact = PLACES[path];
  if (exact !== undefined) return exact;
  for (const glob of Object.keys(PLACES)) if (fnmatch(path, glob)) return PLACES[glob];
  return "exp";
}

/** The widest exponential form of `value` that fits `chars`, from `most` down. */
function exponentialAt(value: number, chars: number, most = 4): string {
  for (let digits = most; digits > 0; digits -= 1) {
    const text = value.toExponential(digits);
    if (text.length <= chars) return text;
  }
  return value.toExponential(0);
}

/** One side of a compare row — `—` where the parameter is absent on that side. */
export function formatSide(path: string, value: number | null | undefined,
                           chars = VALUE_CHARS): string {
  if (value === null || value === undefined) return "—";
  if (!Number.isFinite(value)) return String(value);
  const how = formatFor(path);
  if (how !== "exp") {
    const text = value.toFixed(how);
    if (text.length <= chars) return text;
  }
  return exponentialAt(value, chars);
}

/** The absolute difference, signed, in the family's own format.
 *
 * `new` where one side is absent: a parameter that appeared has no difference,
 * and a difference against nothing would be the value wearing a `+`. */
export function formatDelta(path: string, delta: number | null | undefined): string {
  if (delta === null || delta === undefined) return "new";
  const text = formatSide(path, delta, VALUE_CHARS - 1);
  return delta > 0 ? `+${text}` : text;
}

/**
 * The difference as a percentage of the **first** node's value.
 *
 * Of `a` rather than of the larger of the two, because the pair is read left to
 * right and "b is 0.1 % above a" is the sentence: the ranking's own scale
 * (`DiffRow.relative`, the larger magnitude) exists to keep a near-zero `a` from
 * dominating the order, which is a different job.  `—` where there is no such
 * percentage to state: a parameter absent on one side, or an `a` of zero, where
 * every move is an infinite fraction of it.
 *
 * Of |a|, so the sign is the difference's own.  Measured in a browser on a
 * Caglioti V that refined from −0.0002 to +0.0024: against a signed `a` the row
 * read `+0.002601` beside `-1.30e+3%`, two marks disagreeing about which way a
 * parameter went.  The magnitude is the fraction of its own size either way.
 *
 * Three significant figures rather than two decimal places: a cell length
 * moving 12 ppm is a real refinement result and `0.00%` is not a way to say it.
 */
export function formatPercent(a: number | null | undefined,
                              delta: number | null | undefined,
                              chars = PERCENT_CHARS): string {
  if (a === null || a === undefined || !a) return "—";
  if (delta === null || delta === undefined) return "—";
  const percent = (100 * delta) / Math.abs(a);
  if (!Number.isFinite(percent)) return "—";
  const magnitude = Math.abs(percent);
  const body = magnitude >= 1000 || (percent !== 0 && magnitude < 1e-3)
    ? exponentialAt(percent, chars - 2, 2)   // three significant figures here too
    : String(Number(percent.toPrecision(3)));
  return `${percent > 0 ? "+" : ""}${body}%`;
}
