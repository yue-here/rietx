/**
 * The pattern panel's figure at `/next`: `lib/pattern.ts` (WP-1461), copied
 * because the rebuild draws it to the prototype (WP-2216's polish, 2026-11-11)
 * through its own copy of the chart module, `next/rxplot.mjs`. gui/CLAUDE.md:
 * a shared module the new page must change moves into `gui/src/next/` first,
 * so today's page does not move. The swap deletes `lib/pattern.ts`.
 * WP-2218: a preview draws the last fit in `--plot-last` grey under the preview
 * in the calculated ink, as the prototype does; the original dashes the last fit.
 *
 * The pattern panel's figure (WP-1461).
 *
 * `Plot.svelte` imports this module on its first draw, so uPlot is fetched then
 * and never on a page with no project open. It turns the curves route's payload
 * (D4) into `rxplot.pattern`'s figure and draws what only this panel has on it:
 * the protocol's shading, the candidate's lines, the picked peaks with their
 * fitted profiles and, on the raw view, their residual, and the hover ring.
 * The figure itself (panes, gestures, markers, ticks) is `rxplot.mjs`'s.
 */

import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { pattern, unpack, vlines, type Curves, type Pattern } from "./rxplot.mjs";

import { api } from "../api";
import { channelIndex } from "../lib/interactive";
import { joinCurves, type GroupCurve, type PeakRow } from "../lib/peaks";
import {
  curveColors,
  lens,
  LENS_GAP,
  LENS_HEIGHT,
  LENS_WIDTH,
  maskShapes,
  nearestIndex,
  type CandidateOverlay,
  type Protocol,
  type ResidualKind,
  type Scale,
  type Window,
} from "../lib/plot";

export type { Curves };

/** The project's curves, every channel once (D4). Before a fit, the pattern alone. */
export async function fetchCurves(): Promise<Curves> {
  return unpack(await api.curves());
}

/** Two payloads over the same channels, so a view on one is a view on the other. */
export function sameGrid(a: Curves | null, b: Curves): boolean {
  const x = a?.arrays.two_theta, y = b.arrays.two_theta;
  return !!x && x.length === y.length && x[0] === y[0] && x[x.length - 1] === y[y.length - 1];
}

/**
 * The payload in the shape the readout reads (`lib/plot.ts:readout`).
 *
 * The readout, the curve toggles and the peak markers' heights all read it: the
 * fitted channels on the arrays, and the masked ones on `excluded`, each gathered
 * once into a typed array. The model's arrays are the payload's own views, already
 * one value per fitted channel, so nothing of them is copied.
 */
export function windowOf({ header, arrays }: Curves): Window {
  const tt = arrays.two_theta, y = arrays.y_obs, kept = arrays.kept;
  const pick = (a: ArrayLike<number>, at: ArrayLike<number>) =>
    Float64Array.from({ length: at.length }, (_, q) => a[at[q]]);
  const inKept = new Uint8Array(tt.length);
  for (const i of kept) inKept[i] = 1;
  const out: number[] = [];
  for (let i = 0; i < tt.length; i++) if (!inKept[i]) out.push(i);
  const excluded = { two_theta: pick(tt, out), y_obs: pick(y, out) };
  const common = { weighted: header.weighted, excluded, n_excluded: out.length };
  if (!header.fit) return { raw: true, two_theta: pick(tt, kept), y_obs: pick(y, kept), ...common };
  const empty = new Float64Array(0);
  return {
    ...common,
    two_theta: pick(tt, arrays.fitted), y_obs: pick(y, arrays.fitted),
    y_calc: arrays.y_calc ?? empty, y_background: arrays.y_background ?? empty,
    delta: arrays.delta ?? empty, delta_raw: arrays.delta_raw ?? empty,
    cumulative_chi2: arrays.cumulative_chi2 ?? empty,
    ticks: header.ticks ?? {}, tick_hkl: header.tick_hkl ?? {}, stale: header.stale,
  };
}

/** What this panel lays over the figure, read at every draw. */
export interface Overlay {
  protocol: Protocol;
  extent: [number, number] | null;
  peaks: readonly PeakRow[] | null;
  groups: readonly GroupCurve[] | null;
  /** the Peaks tab is up: only there are the markers, their fit and the candidate drawn */
  peaksActive: boolean;
  candidate: CandidateOverlay | null;
  /** the peak row a person chose in the Pick step's table (WP-2240): its mark
   *  is drawn larger with a ring, or, for a line left out, a thin line
   *  stands where it is (interaction rule 5) */
  selected?: number | null;
  /** the line a drag is moving: the canvas leaves its mark out, and the page
   *  draws it under the pointer as a DOM mark, so a drag repaints no pane */
  dragging?: number | null;
  hidden: readonly string[];
  /** the payload in the readout's shape (`windowOf`), for a marker's height */
  held: Window | null;
}

export interface ChartOptions {
  scale: Scale;
  kind: ResidualKind;
  labels: { y: () => string; resid: () => string };
  /** whether the y axes keep a strip for their titles: only while exporting */
  titled?: () => boolean;
}

const Y: Record<Scale, "lin" | "sqrt" | "log"> = { linear: "lin", sqrt: "sqrt", log: "log" };

/** The pattern figure with this panel's layers on it. */
export class PatternChart {
  readonly fig: Pattern;
  private colors: ReturnType<typeof curveColors>;
  /** the chrome inks the peak layer borrows: a lens's halo, the chosen
   *  line's ring and a candidate cell's lines; read with `colors`, at build
   *  and on `retheme`, never on a draw */
  private chrome: Chrome;
  private overlay: Overlay;
  private curves: Curves;
  /** What the raw view's residual was last built from, so a repaint rebuilds it only when that moved. */
  private residualKey: unknown[] = [];
  private ringAt: number | null = null;
  /** The preview drawn over the last fit (WP-2128): its model on the last
   *  fit's channels, and those channels' 2θ, or null while there is none. */
  private previewOn: { tt: Float64Array; last: ArrayLike<number>; calc: Float64Array } | null = null;
  private preview: Curves | null = null;
  /** A history node's curve the History tab compares (WP-2211), on the
   *  node's own channels, or null while none is. */
  private compared: { tt: Float64Array; y: Float64Array } | null = null;
  private readonly ringEl: HTMLDivElement;
  /** Each lens the last draw placed, in CSS px from the main pane's plot
   *  area, for the gestures' hit test (`markAt`) and the bar's place. */
  private marks: Array<{ index: number; x: number; y: number; h: number }> = [];
  /** Whether the main pane keeps `HEADROOM` clear above the data. */
  private roomy = false;

  constructor(host: HTMLElement, curves: Curves, overlay: Overlay, opts: ChartOptions) {
    this.overlay = overlay;
    this.curves = curves;
    this.residualKey = this.residualInputs();
    this.colors = readColors();
    this.chrome = readChrome();
    this.ringEl = document.createElement("div");
    this.ringEl.className = "rx-ring";
    this.roomy = PatternChart.wantsRoom(overlay);
    const shade = (u: any) => this.shade(u);
    this.fig = pattern(uPlot, host, curves, {
      // before a fit the lower pane is the peak groups' own residual, in the
      // difference curve's ink, as their fit takes the calculated curve's
      // (the maintainer, 2026-11-23); while a preview is drawn over a fit the model's own series keeps its
      // place in the y range and paints nothing: the layer draws the last fit
      // in `--plot-last` and the preview in the calculated ink, so the scale
      // stays the last fit's
      colors: () => ({ ...this.colors, masked: this.colors.edge,
                       calc: this.previewOn ? "rgba(0, 0, 0, 0)" : this.colors.calc,
                       diff: this.colors.diff }),
      y: Y[opts.scale],
      residual: opts.kind,
      hidden: overlay.hidden,
      labels: opts.labels,
      titled: opts.titled,
      rawResidual: () => this.groupResidual(),
      ranges: { main: (u: any, min: number, max: number) => this.mainRange(u, min, max) },
      layers: {
        main: { under: [shade, (u) => this.candidateLines(u)],
                over: [(u) => this.previewLines(u), (u) => this.compareLine(u), (u) => this.peakFit(u), (u) => this.peakMarkers(u), (u) => this.placeRing(u)] },
        ticks: { under: [shade] },
        resid: { under: [shade] },
      },
    });
  }

  /** Re-read the theme's colours and repaint. One microtask first: the shell
   *  stamps the theme in an effect of the same flush (gui/CLAUDE.md). */
  async retheme(): Promise<void> {
    await Promise.resolve();
    this.colors = readColors();
    this.chrome = readChrome();
    this.fig.redraw();
  }

  /** A new payload. `keep` holds the reader's view, as a run landing should. */
  setCurves(curves: Curves, keep: boolean): void {
    this.curves = curves;
    if (this.preview) this.setPreview(this.preview, keep);
    else this.fig.setCurves(curves, keep);
  }

  /**
   * Draw `preview`, the curves at values nobody has applied, over the last fit,
   * or take it off with null (WP-2128). The view and every y range are kept, so
   * the comparison is at the last fit's scale (ruled 2026-11-07).
   *
   * The preview answers every channel the next fit would fit; it is drawn on
   * the channels this payload carries, found by their 2θ (`channelIndex`), so
   * past `CURVES_CEILING` it is decimated onto the curves route's own choice.
   * The residual pane shows the preview's residuals and the tick band its
   * ticks, both the route's. Before any fit there is no last fit to compare
   * with, and the preview is drawn as the model.
   */
  setPreview(preview: Curves | null, keep = true): void {
    this.preview = preview;
    const base = this.curves;
    if (!preview) {
      this.previewOn = null;
      this.fig.setCurves(base, keep);
      return;
    }
    const tt = base.arrays.two_theta, pv = preview.arrays;
    const header = { ...base.header, ticks: preview.header.ticks ?? {},
                     tick_hkl: preview.header.tick_hkl ?? {} };
    if (!base.header.fit) {
      const at = channelIndex(tt, pv.two_theta), hit: number[] = [];
      at.forEach((i, q) => { if (i >= 0) hit.push(q); });
      const pick = (a: ArrayLike<number>) => Float64Array.from(hit, (q) => a[q]);
      this.previewOn = null;
      this.fig.setCurves({ header: { ...header, fit: true }, arrays: {
        ...base.arrays, fitted: Int32Array.from(hit, (q) => at[q]),
        y_calc: pick(pv.y_calc), y_background: pick(pv.y_background), delta: pick(pv.delta),
        delta_raw: pick(pv.delta_raw), cumulative_chi2: pick(pv.cumulative_chi2) } }, keep);
      return;
    }
    const fitTT = Float64Array.from(base.arrays.fitted, (i) => tt[i]);
    const at = channelIndex(pv.two_theta, fitTT);
    const pick = (a: ArrayLike<number>) => Float64Array.from(at, (j) => (j < 0 ? NaN : a[j]));
    // a running sum has a value at a channel the preview does not fit: the sum
    // so far. A NaN there would make every zoom's re-based Σχ² past it NaN
    let sum = 0;
    const cum = Float64Array.from(at, (j) => (sum = j < 0 ? sum : pv.cumulative_chi2[j]));
    this.previewOn = { tt: fitTT, last: base.arrays.y_calc, calc: pick(pv.y_calc) };
    this.fig.setCurves({ header, arrays: {
      ...base.arrays, delta: pick(pv.delta), delta_raw: pick(pv.delta_raw),
      cumulative_chi2: cum } }, keep);
  }

  /**
   * Draw a history node's curve over the pattern, or take it off with null
   * (WP-2211). A repaint: the view and every y range are kept. The curve is on
   * the node's own channels, placed by their 2θ, since a node can have been
   * fitted over another range than the head.
   */
  setCompared(compared: { tt: Float64Array; y: Float64Array } | null): void {
    this.compared = compared;
    this.fig.redraw();
  }

  /** New layer inputs; a repaint, never a refetch. */
  update(overlay: Overlay): void {
    this.overlay = overlay;
    const key = this.residualInputs();
    if (key.some((v, i) => v !== this.residualKey[i])) {
      this.residualKey = key;
      // with a fit the pane is the model's residual, which a peak edit leaves alone
      if (!this.curves.header.fit) this.fig.refreshResidual();
    }
    const roomy = PatternChart.wantsRoom(overlay);
    if (roomy !== this.roomy) {
      this.roomy = roomy;
      // setting x at itself re-ranges y through `mainRange` (rxplot's `setData`)
      const u = this.fig.panes.main;
      u.setScale("x", { min: u.scales.x.min, max: u.scales.x.max });
    }
    this.fig.redraw();
  }

  /** The headroom is kept while the peak layer has lines to mark. */
  private static wantsRoom(o: Overlay): boolean {
    return o.peaksActive && !!o.peaks?.length;
  }

  /**
   * The main pane's y range: the chart module's own, with `HEADROOM` CSS px
   * kept clear above the data while the peak layer is up, for the lenses and
   * a selected line's bar (interaction rule 7, round 11c call 28). The room
   * is made in the scale's own space (√ or log), so it is the same number of
   * pixels on every scale. A y the reader zoomed to is pinned and never
   * reaches here.
   */
  private mainRange(u: any, min: number, max: number): [number, number] {
    const distr = u.scales?.y?.distr;
    const [lo, hi] = distr === 3 ? uPlot.rangeLog(min, max, 10, true) as [number, number]
      : uPlot.rangeNum(min, max, 0.1, true) as [number, number];
    const height = (u.bbox?.height ?? 0) / devicePixelRatio;
    if (!this.roomy || !(height > 2 * HEADROOM) || !(hi > lo)) return [lo, hi];
    const fwd = distr === 3 ? Math.log10 : distr === 100
      ? (v: number) => Math.sign(v) * Math.sqrt(Math.abs(v)) : (v: number) => v;
    const bwd = distr === 3 ? (v: number) => 10 ** v : distr === 100
      ? (v: number) => Math.sign(v) * v * v : (v: number) => v;
    const a = fwd(lo), b = fwd(hi);
    return [lo, bwd(a + (b - a) * height / (height - HEADROOM))];
  }

  /** The line whose lens is under a pointer at (`clientX`, `clientY`), or
   *  null. A lens is 4.5 px wide, so the target is wider than the ink. */
  markAt(clientX: number, clientY: number): number | null {
    const box = this.fig.panes.main.over.getBoundingClientRect();
    const x = clientX - box.left, y = clientY - box.top;
    let best: number | null = null, gap = Infinity;
    for (const m of this.marks) {
      const dx = Math.abs(m.x - x);
      if (dx <= MARK_REACH && Math.abs(m.y - y) <= m.h / 2 + 4 && dx < gap) {
        best = m.index;
        gap = dx;
      }
    }
    return best;
  }

  /** Where the last draw put a line's lens, in CSS px from the plot area's
   *  top left, with its height; null for a line with no lens in view. */
  markOf(index: number): { x: number; y: number; h: number } | null {
    return this.marks.find((m) => m.index === index) ?? null;
  }

  /** Where a new line's lens would stand at 2θ, in CSS px from the plot
   *  area's top left: the hover's dashed mark and a dragged mark use it. */
  lensAt(tt: number): { x: number; y: number } | null {
    const u = this.fig.panes.main, { min, max } = u.scales.x;
    if (tt < min || tt > max) return null;
    const h = this.crest(tt);
    if (h == null) return null;
    const y = u.valToPos(h, "y") - LENS_GAP - LENS_HEIGHT / 2;
    return { x: u.valToPos(tt, "x"), y: Math.max(LENS_HEIGHT / 2 + 2, y) };
  }

  /** A 2θ's place across the plot area, in CSS px, or null out of view. */
  xOf(tt: number): number | null {
    const u = this.fig.panes.main, { min, max } = u.scales.x;
    return tt < min || tt > max ? null : u.valToPos(tt, "x");
  }

  /** The 2θ under a pointer at `clientX`, or null off the plot area. */
  thetaOf(clientX: number): number | null {
    const u = this.fig.panes.main, box = u.over.getBoundingClientRect();
    const px = clientX - box.left;
    return px < 0 || px > box.width ? null : u.posToVal(px, "x");
  }

  /** Degrees of 2θ per CSS pixel at the current zoom. The readout asks on
   *  every pointer move, so the width is the one uPlot last laid out, not
   *  `over.clientWidth`, which can force a layout per move. */
  degPerPx(): number {
    const u = this.fig.panes.main, { min, max } = u.scales.x, width = u.bbox.width / devicePixelRatio;
    return width ? Math.abs(max - min) / width : 0.01;
  }

  /** Put the hover ring on the line at 2θ `at`, or take it off. A DOM move,
   *  never a repaint of the pattern (WP-1032's rule, a step cheaper than
   *  plotly's `restyle`). */
  ring(at: number | null): void {
    this.ringAt = at;
    this.placeRing(this.fig.panes.main);
  }

  destroy(): void {
    this.fig.destroy();
  }

  // -- layers -----------------------------------------------------------

  /**
   * The raw view's lower pane: each fitted group's own (y − fit)/σ, on the
   * channels its window covers. There is no model before a fit, so this is the
   * residual a peak list has. It is drawn where the peak layer is (WP-1210),
   * and a group's channels are the pattern's own, so each value lands by index.
   */
  private groupResidual(): (number | null)[] | null {
    const { groups, peaksActive, hidden } = this.overlay;
    if (!peaksActive || !groups?.length || hidden.includes("peakfit")) return null;
    const tt = this.curves.arrays.two_theta, out = new Array(tt.length).fill(null);
    for (const g of groups) {
      for (let j = 0; j < g.two_theta.length; j++) {
        const i = nearestIndex(tt, g.two_theta[j]);
        if (i >= 0) out[i] = g.delta[j];
      }
    }
    return out;
  }

  private residualInputs(): unknown[] {
    const { groups, peaksActive, hidden } = this.overlay;
    return [groups, peaksActive, hidden.includes("peakfit")];
  }

  private shade(u: any): void {
    const { protocol, extent } = this.overlay;
    if (!extent) return;
    const { ctx, bbox } = u, dpr = devicePixelRatio;
    const at = (x: number) => u.valToPos(x, "x", true);
    ctx.save();
    for (const s of maskShapes(protocol, extent, this.colors)) {
      if (s.type === "rect") {
        const l = Math.max(bbox.left, at(s.x0)), r = Math.min(bbox.left + bbox.width, at(s.x1));
        if (r <= l) continue;
        ctx.fillStyle = s.color;
        ctx.fillRect(l, bbox.top, r - l, bbox.height);
      } else {
        const x = Math.round(at(s.x)) + 0.5;
        if (x < bbox.left || x > bbox.left + bbox.width) continue;
        ctx.strokeStyle = s.color;
        ctx.lineWidth = dpr;
        ctx.setLineDash([2 * dpr, 2 * dpr]);
        ctx.beginPath();
        ctx.moveTo(x, bbox.top);
        ctx.lineTo(x, bbox.top + bbox.height);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  /** The last fit in grey and the preview in the model's accent, as the
   *  prototype draws them (`gui/STYLE.md` § Plots: the last fit turns grey
   *  only while a preview exists; WP-2218). Each is its legend label's switch. */
  private previewLines(u: any): void {
    const on = this.previewOn;
    if (!on) return;
    const hidden = this.overlay.hidden;
    const { ctx } = u;
    ctx.save();
    if (!hidden.includes("calc")) trace(u, on.tt, on.last, this.colors.last, 1.2, []);
    if (!hidden.includes("preview")) trace(u, on.tt, on.calc, this.colors.calc, 1.4, []);
    ctx.restore();
  }

  /** The compared node's curve, dashed in its own ink (`--plot-compare`),
   *  as the design drew it. Its legend label is its switch. */
  private compareLine(u: any): void {
    const on = this.compared;
    if (!on || this.overlay.hidden.includes("compare")) return;
    u.ctx.save();
    trace(u, on.tt, on.y, this.colors.compare, 1.2, [4, 3]);
    u.ctx.restore();
  }

  /** A chosen cell's lines, full height and under everything, in the strong
   *  rule's grey (the maintainer, 2026-11-23: "grey lines much better than
   *  green"). Today's Peaks tab keeps `--plot-candidate`. */
  private candidateLines(u: any): void {
    const lines = this.overlay.candidate?.two_theta;
    if (lines?.length) vlines(u, lines, u.bbox.top, u.bbox.height, this.chrome.rule);
  }

  /** Each group's fitted profile on its own channels (D8), drawn as the
   *  calculated curve is: its ink, solid, at its width. The workflow draws no
   *  refinement over it to confuse it with (the maintainer, 2026-11-23). */
  private peakFit(u: any): void {
    const { groups, peaksActive, hidden } = this.overlay;
    if (!peaksActive || !groups?.length || hidden.includes("peakfit")) return;
    const { ctx } = u, dpr = devicePixelRatio, fit = joinCurves(groups, (g) => g.y_fit);
    ctx.save();
    ctx.strokeStyle = this.colors.calc;
    ctx.lineWidth = 1.2 * dpr;
    ctx.setLineDash([]);
    ctx.beginPath();
    let pen = false;
    for (let i = 0; i < fit.x.length; i++) {
      const x = fit.x[i], y = fit.y[i];
      if (x == null || y == null || !(y > 0 || u.scales.y.distr !== 3)) { pen = false; continue; }
      const X = u.valToPos(x, "x", true), Y = u.valToPos(y, "y", true);
      if (pen) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
      pen = true;
    }
    ctx.stroke();
    ctx.restore();
  }

  /**
   * The lines the search uses, each a lens (the shape of a reflection tick)
   * standing just clear of the highest count near it (WP-2240, the
   * maintainer's rounds 11c and 11d, 2026-11-08). A line left out of the
   * search has no mark: its row in the table is its route, and choosing that
   * row draws a thin solid line where it is, in the fit's ink (the
   * maintainer, 2026-11-23: no dotted line). Lines closer than a lens's width
   * stack upward, so a duplicate never hides under its twin. The chosen line's
   * lens is larger, with a ring in the text ink (`gui/STYLE.md` § Plots,
   * 2026-11-09). A halo of the page's background lets a lens read over the
   * crosses.
   */
  private peakMarkers(u: any): void {
    const { peaks, peaksActive, hidden, selected, dragging } = this.overlay;
    this.marks = [];
    if (!peaksActive || !peaks?.length || hidden.includes("peaks")) return;
    const { ctx } = u, dpr = devicePixelRatio;
    const H = LENS_HEIGHT * dpr, W = LENS_WIDTH * dpr, gap = LENS_GAP * dpr;
    const row = (LENS_HEIGHT + 1) * dpr, near = 7 * dpr, top = u.bbox.top + H / 2 + 2 * dpr;
    const { min, max } = u.scales.x;
    const { halo, ink } = this.chrome;
    const marks: Array<{ index: number; x: number; y: number; level: number; chosen: boolean }> = [];
    let leftOut: number | null = null;
    for (const p of [...peaks].sort((a, b) => a.two_theta - b.two_theta)) {
      if (p.two_theta < min || p.two_theta > max) continue;
      const chosen = selected === p.index;
      if (p.index === dragging) continue;
      if (!p.usable) {
        if (chosen) leftOut = u.valToPos(p.two_theta, "x", true);
        continue;
      }
      const h = this.crest(p.two_theta);
      if (h == null) continue;
      const x = u.valToPos(p.two_theta, "x", true);
      let level = 0;
      while (marks.some((m) => m.level === level && Math.abs(m.x - x) < near)) level++;
      // a stacked lens stands a row above the twin it stacks on, never a row
      // above its own crest: zoomed out, the twin's crest can be the higher
      let y = u.valToPos(h, "y", true) - gap - H / 2;
      for (const m of marks) {
        if (m.level === level - 1 && Math.abs(m.x - x) < near) y = Math.min(y, m.y - row);
      }
      // at the plot's top the stack turns downward, so a twin under the
      // strongest line still clears its partner rather than landing on it
      y = Math.max(top + level * row, y);
      marks.push({ index: p.index, x, y, level, chosen });
    }
    this.marks = marks.map((m) => ({
      index: m.index, x: (m.x - u.bbox.left) / dpr, y: (m.y - u.bbox.top) / dpr,
      h: LENS_HEIGHT * (m.chosen ? 1.4 : 1) }));
    ctx.save();
    // uPlot leaves the last series' dash on the context (the background's)
    ctx.setLineDash([]);
    const size = (m: { chosen: boolean }) => (m.chosen ? 1.4 : 1);
    if (halo) {
      ctx.fillStyle = halo;
      for (const m of marks) {
        lens(ctx, m.x, m.y, H * size(m) + 5 * dpr, W * size(m) + 4 * dpr);
        ctx.fill();
      }
    }
    ctx.fillStyle = this.colors.peak;
    for (const m of marks) {
      lens(ctx, m.x, m.y, H * size(m), W * size(m));
      ctx.fill();
    }
    const chosen = marks.find((m) => m.chosen);
    if (chosen && ink) {
      ctx.strokeStyle = ink;
      ctx.lineWidth = 1.2 * dpr;
      lens(ctx, chosen.x, chosen.y, H * 1.4 + 6 * dpr, W * 1.4 + 5 * dpr);
      ctx.stroke();
    }
    if (leftOut != null) {
      ctx.strokeStyle = this.colors.calc;
      ctx.lineWidth = dpr;
      ctx.beginPath();
      ctx.moveTo(leftOut, u.bbox.top);
      ctx.lineTo(leftOut, u.bbox.top + u.bbox.height);
      ctx.stroke();
    }
    ctx.restore();
  }

  /** The highest measured count within three channels of 2θ, or null on a log
   *  axis at or under zero: what a lens stands clear of. */
  private crest(tt: number): number | null {
    const w = this.overlay.held, k = w ? nearestIndex(w.two_theta, tt) : -1;
    let v = k < 0 ? 0 : w!.y_obs[k];
    if (k >= 0) {
      for (let q = Math.max(0, k - 3); q < Math.min(w!.y_obs.length, k + 4); q++) {
        if (w!.y_obs[q] > v) v = w!.y_obs[q];
      }
    }
    return this.fig.panes.main.scales.y.distr === 3 && !(v > 0) ? null : v;
  }

  /** The measured intensity at the channel nearest 2θ, or null on a log axis at or under zero. */
  private height(tt: number): number | null {
    const w = this.overlay.held, k = w ? nearestIndex(w.two_theta, tt) : -1;
    const v = k < 0 ? 0 : w!.y_obs[k];
    return this.fig.panes.main.scales.y.distr === 3 && !(v > 0) ? null : v;
  }

  private placeRing(u: any): void {
    // An SVG export redraws the pane as a copy with these layers on it, and
    // the ring is DOM on the live pane: moved into the copy, it went when the
    // copy did. The fig is unset only while the constructor builds the pane.
    if (this.fig && u !== this.fig.panes.main) return;
    const el = this.ringEl;
    if (el.parentNode !== u.over) u.over.appendChild(el);
    const at = this.ringAt, h = at == null ? null : this.height(at);
    if (at == null || h == null || at < u.scales.x.min || at > u.scales.x.max) {
      el.style.display = "none";
      return;
    }
    el.style.display = "block";
    el.style.left = `${u.valToPos(at, "x")}px`;
    el.style.top = `${u.valToPos(h, "y")}px`;
    el.style.borderColor = this.colors.peak;
  }
}

/** A curve on its own 2θ channels over the main pane, at a width and a dash in
 *  CSS pixels; the pen lifts outside the view and where the log scale cannot
 *  place a value. The preview's two curves and a compared node's share it. */
function trace(u: any, tt: ArrayLike<number>, ys: ArrayLike<number>, colour: string,
               width: number, dash: number[]): void {
  const { ctx } = u, dpr = devicePixelRatio, { min, max } = u.scales.x, log = u.scales.y.distr === 3;
  ctx.strokeStyle = colour;
  ctx.lineWidth = width * dpr;
  ctx.setLineDash(dash.map((d) => d * dpr));
  ctx.beginPath();
  let pen = false;
  for (let q = 0; q < tt.length; q++) {
    const x = tt[q], y = ys[q];
    if (x < min || x > max || !Number.isFinite(y) || (log && !(y > 0))) { pen = false; continue; }
    const X = u.valToPos(x, "x", true), Y = u.valToPos(y, "y", true);
    if (pen) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
    pen = true;
  }
  ctx.stroke();
}

export { LENS_GAP, LENS_HEIGHT, LENS_WIDTH };
/** The room kept clear above the data while the peak layer is up, in CSS px
 *  (round 11c call 28: about an eighth of the plot in a 900 px window). */
export const HEADROOM = 96;
/** How far from a lens's axis a press still takes it, in CSS px. */
export const MARK_REACH = 6;

function readColors(): ReturnType<typeof curveColors> {
  const style = getComputedStyle(document.body);
  return curveColors((name) => style.getPropertyValue(name));
}

interface Chrome { halo: string; ink: string; rule: string }

function readChrome(): Chrome {
  const style = getComputedStyle(document.body);
  const read = (name: string) => style.getPropertyValue(name).trim();
  return { halo: read("--bg"), ink: read("--fg"), rule: read("--line-strong") };
}
