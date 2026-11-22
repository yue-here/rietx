/**
 * The History tab's rows, lanes and Restore, as pure functions (WP-2211).
 *
 * The payload is `GET /api/history` (`session.tree_payload`), whose nodes come
 * in the tree's insertion order, which is topological: a parent is always
 * listed before its children. The tab draws them in that order, oldest first
 * and the newest at the bottom, in both its views. The Graph view's lanes are
 * `lib/history.ts`'s `layout`, the same assignment today's panel draws, with
 * each step into another lane drawn as a rounded corner (the maintainer's
 * ruling of 2026-11-21 on question 1).
 */
import { edgeSegments, layout, nodeLabel, type Edge, type HistoryNode } from "../lib/history";
import type { ParamRow } from "../lib/table";

export type { HistoryNode };

export interface HistoryPayload {
  head: string | null;
  n_nodes: number;
  nodes: HistoryNode[];
}

/** What the Step column says: "Start" for the root, else what the node did,
 *  with a stage under the name the Plan tab gives it. */
export function stepName(node: HistoryNode): string {
  return node.kind === "root" ? "Start" : nodeLabel(node);
}

/** Rwp in per cent at two decimals, or a dash where the node ran no fit. */
export function rwpText(rwp: number | null | undefined): string {
  return rwp == null || !Number.isFinite(rwp) ? "—" : `${(100 * rwp).toFixed(2)} %`;
}

export function gofText(gof: number | null | undefined): string {
  return gof == null || !Number.isFinite(gof) ? "—" : gof.toFixed(2);
}

export function freeText(n: number | null | undefined): string {
  return n == null ? "—" : String(n);
}

/** The time of day a node was made, `HH:MM:SS` on this computer's clock. */
export function whenText(utc: string): string {
  const t = new Date(utc);
  if (Number.isNaN(t.getTime())) return "—";
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(t.getHours())}:${two(t.getMinutes())}:${two(t.getSeconds())}`;
}

// -- the Graph view's lanes ---------------------------------------------------

/** The Graph view's grid: a row is a table row's height, a lane a fixed step. */
export const ROW_PX = 30;
export const LANE_PX = 14;
/** The radius a branch turns with, never past half a row or a lane. */
export const TURN_PX = 6;

const laneX = (lane: number) => LANE_PX / 2 + lane * LANE_PX;
const rowY = (row: number) => ROW_PX / 2 + row * ROW_PX;

/**
 * An edge as one SVG path: down its lane, and a rounded corner wherever it
 * changes lane.
 *
 * `edgeSegments` gives an edge at most two crossings, each spanning one row.
 * A crossing out of the parent leaves sideways at the parent's row and turns
 * down into its lane; any other crossing runs down and turns sideways into
 * the child at the child's row. So every crossing is a horizontal and a
 * vertical piece meeting at one corner, and the corner is rounded with radius
 * `TURN_PX`, never cut as a diagonal.
 */
export function edgePath(edge: Edge): string {
  const points: Array<[number, number]> = [];
  const push = (x: number, y: number) => {
    const last = points[points.length - 1];
    if (!last || last[0] !== x || last[1] !== y) points.push([x, y]);
  };
  for (const s of edgeSegments(edge)) {
    const x0 = laneX(s.fromLane), y0 = rowY(s.fromRow);
    const x1 = laneX(s.toLane), y1 = rowY(s.toRow);
    push(x0, y0);
    if (x0 !== x1) {
      const leaving = s.fromRow === edge.fromRow && s.fromLane === edge.fromLane;
      if (leaving) push(x1, y0);
      else push(x0, y1);
    }
    push(x1, y1);
  }
  return roundedPolyline(points, TURN_PX);
}

/** A polyline whose every interior vertex is a quadratic turn of radius `r`,
 *  shortened where a piece is shorter than two radii. */
export function roundedPolyline(points: ReadonlyArray<[number, number]>, r: number): string {
  if (!points.length) return "";
  const f = (n: number) => String(Math.round(n * 100) / 100);
  let d = `M${f(points[0][0])} ${f(points[0][1])}`;
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = points[i - 1], [x, y] = points[i], [nx, ny] = points[i + 1];
    const inLen = Math.hypot(x - px, y - py), outLen = Math.hypot(nx - x, ny - y);
    const k = Math.min(r, inLen / 2, outLen / 2);
    const ax = x - ((x - px) / inLen) * k, ay = y - ((y - py) / inLen) * k;
    const bx = x + ((nx - x) / outLen) * k, by = y + ((ny - y) / outLen) * k;
    d += ` L${f(ax)} ${f(ay)} Q${f(x)} ${f(y)} ${f(bx)} ${f(by)}`;
  }
  const end = points[points.length - 1];
  return points.length > 1 ? `${d} L${f(end[0])} ${f(end[1])}` : d;
}

export interface Lanes {
  /** each node's dot, by id */
  dots: Map<string, { x: number; y: number; lane: number }>;
  paths: Array<{ d: string; lane: number; merge: boolean; key: string }>;
  width: number;
}

/** The Graph view's drawing for `nodes`, in their order. */
export function lanes(nodes: readonly HistoryNode[]): Lanes {
  const { placed, edges, lanes: n } = layout(nodes);
  const dots = new Map(placed.map((p) => [p.node.id, { x: laneX(p.lane), y: rowY(p.row), lane: p.lane }]));
  const paths = edges.map((e) => ({
    d: edgePath(e), lane: e.lane, merge: e.merge, key: `${e.from}-${e.to}`,
  }));
  return { dots, paths, width: n * LANE_PX };
}

// -- Restore --------------------------------------------------------------------

const COORDINATE = /^(phases\.\d+\.atoms\.\d+)\.([xyz])$/;

export interface RestorePlan {
  /** path → the node's value, as the text a typed edit holds */
  values: Record<string, string>;
  /** atom path → the axes that differ, as typed position edits */
  positions: Record<string, Record<string, string>>;
  /** paths the working state lacks or the node lacks: why the node's values
   *  cannot be loaded as pending edits */
  missing: string[];
}

/**
 * What Restore puts in the pending edits, from `GET /api/history/diff` of the
 * node against the head and the working state's parameter rows.
 *
 * Every differing value goes in, as WP-2211 § Measured decided: a free or
 * fixed row as a value edit, a coordinate as its atom's position edit, since
 * a coordinate reaches the table through its site's directions. A tied or
 * locked row is left out, since it follows what is restored. The free set,
 * ties and holds stay as the working state has them. A path one side lacks
 * means the model itself differs, so nothing can be loaded and `missing`
 * names those paths.
 */
export function restorePlan(diff: Record<string, Array<number | null>>,
                            rows: readonly ParamRow[]): RestorePlan {
  const byPath = new Map(rows.map((r) => [r.path, r]));
  const out: RestorePlan = { values: {}, positions: {}, missing: [] };
  for (const [path, pair] of Object.entries(diff)) {
    const [node, here] = pair;
    const row = byPath.get(path);
    if (node == null || here == null || !row) {
      out.missing.push(path);
      continue;
    }
    const coordinate = COORDINATE.exec(path);
    if (coordinate) {
      (out.positions[coordinate[1]] ??= {})[coordinate[2]] = String(node);
      continue;
    }
    if (row.tie || row.locked || path.includes(".dof.")) continue;
    out.values[path] = String(node);
  }
  out.missing.sort();
  return out;
}

/** How many pending edits a plan makes: one per value and one per atom. */
export function restoreCount(plan: RestorePlan): number {
  return Object.keys(plan.values).length + Object.keys(plan.positions).length;
}
