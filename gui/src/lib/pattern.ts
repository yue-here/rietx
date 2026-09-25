/**
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
import { pattern, unpack, vlines, type Curves, type Pattern } from "rxplot";

import { api } from "../api";
import { joinCurves, type GroupCurve, type PeakRow } from "./peaks";
import {
  curveColors,
  maskShapes,
  nearestIndex,
  type CandidateOverlay,
  type Protocol,
  type ResidualKind,
  type Scale,
  type Window,
} from "./plot";

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
  hidden: readonly string[];
  /** the payload in the readout's shape (`windowOf`), for a marker's height */
  held: Window | null;
}

export interface ChartOptions {
  scale: Scale;
  kind: ResidualKind;
  labels: { y: () => string; resid: () => string };
}

const Y: Record<Scale, "lin" | "sqrt" | "log"> = { linear: "lin", sqrt: "sqrt", log: "log" };

/** The pattern figure with this panel's layers on it. */
export class PatternChart {
  readonly fig: Pattern;
  private colors: ReturnType<typeof curveColors>;
  private overlay: Overlay;
  private curves: Curves;
  /** What the raw view's residual was last built from, so a repaint rebuilds it only when that moved. */
  private residualKey: unknown[] = [];
  private ringAt: number | null = null;
  private readonly ringEl: HTMLDivElement;

  constructor(host: HTMLElement, curves: Curves, overlay: Overlay, opts: ChartOptions) {
    this.overlay = overlay;
    this.curves = curves;
    this.residualKey = this.residualInputs();
    this.colors = readColors();
    this.ringEl = document.createElement("div");
    this.ringEl.className = "rx-ring";
    const shade = (u: any) => this.shade(u);
    this.fig = pattern(uPlot, host, curves, {
      // before a fit the lower pane is the peak groups' own residual, which
      // wears the peak layer's ink (WP-1210), as its row in the strip does
      colors: () => ({ ...this.colors, masked: this.colors.edge,
                       diff: this.curves.header.fit ? this.colors.diff : this.colors.peakfit }),
      y: Y[opts.scale],
      residual: opts.kind,
      hidden: overlay.hidden,
      labels: opts.labels,
      rawResidual: () => this.groupResidual(),
      layers: {
        main: { under: [shade, (u) => this.candidateLines(u)],
                over: [(u) => this.peakFit(u), (u) => this.peakMarkers(u), (u) => this.placeRing(u)] },
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
    this.fig.redraw();
  }

  /** A new payload. `keep` holds the reader's view, as a run landing should. */
  setCurves(curves: Curves, keep: boolean): void {
    this.curves = curves;
    this.fig.setCurves(curves, keep);
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
    this.fig.redraw();
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

  private candidateLines(u: any): void {
    const lines = this.overlay.candidate?.two_theta;
    if (lines?.length) vlines(u, lines, u.bbox.top, u.bbox.height, this.colors.candidate);
  }

  /** Each group's fitted profile, dashed, on its own channels (D8). */
  private peakFit(u: any): void {
    const { groups, peaksActive, hidden } = this.overlay;
    if (!peaksActive || !groups?.length || hidden.includes("peakfit")) return;
    const { ctx } = u, dpr = devicePixelRatio, fit = joinCurves(groups, (g) => g.y_fit);
    ctx.save();
    ctx.strokeStyle = this.colors.peakfit;
    ctx.lineWidth = 1.4 * dpr;
    ctx.setLineDash([4 * dpr, 3 * dpr]);
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
   * The picked lines, at the measured intensity nearest each: a circle where
   * the picker fitted it and a diamond where a person placed it, hollow where
   * it is not used. The whisker is capped at 3×FWHM (WP-1027).
   */
  private peakMarkers(u: any): void {
    const { peaks, peaksActive, hidden } = this.overlay;
    if (!peaksActive || !peaks?.length || hidden.includes("peaks")) return;
    const { ctx } = u, dpr = devicePixelRatio, r = 4.5 * dpr, cap = 3 * dpr;
    const { min, max } = u.scales.x;
    ctx.save();
    ctx.strokeStyle = ctx.fillStyle = this.colors.peak;
    ctx.lineWidth = 1.2 * dpr;
    // uPlot leaves the last series' dash on the context (the background's)
    ctx.setLineDash([]);
    for (const p of peaks) {
      if (p.two_theta < min || p.two_theta > max) continue;
      const h = this.height(p.two_theta);
      if (h == null) continue;
      const X = u.valToPos(p.two_theta, "x", true), Y = u.valToPos(h, "y", true);
      const w = Math.min(p.two_theta_esd, 3 * p.fwhm);
      if (w > 0) {
        const a = u.valToPos(p.two_theta - w, "x", true), b = u.valToPos(p.two_theta + w, "x", true);
        ctx.beginPath();
        ctx.moveTo(a, Y); ctx.lineTo(b, Y);
        ctx.moveTo(a, Y - cap); ctx.lineTo(a, Y + cap);
        ctx.moveTo(b, Y - cap); ctx.lineTo(b, Y + cap);
        ctx.stroke();
      }
      ctx.beginPath();
      if (p.origin === "fitted") ctx.arc(X, Y, r, 0, 2 * Math.PI);
      else { ctx.moveTo(X, Y - r); ctx.lineTo(X + r, Y); ctx.lineTo(X, Y + r); ctx.lineTo(X - r, Y); ctx.closePath(); }
      if (p.usable) ctx.fill(); else ctx.stroke();
    }
    ctx.restore();
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

function readColors(): ReturnType<typeof curveColors> {
  const style = getComputedStyle(document.body);
  return curveColors((name) => style.getPropertyValue(name));
}
