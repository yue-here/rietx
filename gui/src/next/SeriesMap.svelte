<script lang="ts">
  /**
   * The series' Map graph at `/next` (WP-2243 task 7), a graph tab while the
   * Series workflow is up: every pattern a row, first at the top (call 7).
   *
   * Round 12's design (2026-11-08), restated in WP-2243 § The design. Map
   * colours each row by its counts on a log scale in cividis, or by
   * Difference, the mean Δ/σ under each pixel, red to blue at ±5 esd (calls 8,
   * 24); Waterfall draws each row as a line instead. With Cuts on (the
   * default, call 31) a click sets a cut at that 2θ and selects the row:
   * under the map the selected pattern's profile, beside it each pattern at
   * the cut, averaged over a width. The width is a bar on the profile under
   * the map, drawn, resized by its grips and moved, with a typed width kept in
   * step (calls 35, 36). A drag across zooms 2θ, a drag down shows a window of
   * rows, and a shift-drag picks an area to average (calls 32, 34). Flip puts
   * the first pattern at the bottom (call 37). The colour key sits in the
   * empty corner under the profile beside the map (call 38).
   *
   * The cells come from `GET /api/series/map` (`rietx.gui.series.map_payload`),
   * which serves the staged list before any run: the counts alone are the
   * series' pre-visualisation. A row carries its difference only once a run's
   * record covers it, and the route withholds it while a run is in flight.
   * The arithmetic is `seriesmap.ts`; the hover readout goes to the status
   * bar, never a box (`gui/STYLE.md` § Plots).
   */
  import { untrack } from "svelte";

  import { ApiError, api } from "../api";
  import type { StatusReadout } from "./readout";
  import {
    CUT_WIDTH, DIFF_LIMIT, bandRows, barPart, cividis, columnRanges, countLabel, cutValue, diverging,
    hexRgb, labelStep, logFraction, roundWidth, rowColumns, shownRows, type Rgb,
  } from "./seriesmap";
  import { CURVE_WORDS } from "./words";

  interface MapHeader {
    n_rows: number;
    n_cols: number;
    labels: string[];
    x: (number | null)[];
    axis: string;
    fitted: boolean[];
    rwp: (number | null)[];
    running: boolean;
  }
  interface MapAnswer {
    header: MapHeader;
    arrays: { two_theta: Float64Array; obs: Float64Array; diff?: Float64Array };
  }

  let {
    theme = "light",
    busy = false,
    stamp = 0,
    selected = $bindable(null),
    onreadout = () => {},
  }: {
    theme?: string;
    /** a run in flight: the map asks again when it starts and when it ends */
    busy?: boolean;
    /** moves whenever the staged list does, so the map asks again */
    stamp?: number;
    /** the one selected pattern, by series index (call 2) */
    selected?: number | null;
    onreadout?: (r: StatusReadout | null) => void;
  } = $props();

  let answer = $state.raw<MapAnswer | null>(null);
  let failure = $state("");
  /** nothing is staged yet: the route's NO_SERIES, an empty state, not a failure */
  let empty = $state(false);
  let mode = $state<"map" | "waterfall">("map");
  let show = $state<"obs" | "diff">("obs");
  let cuts = $state(true);
  let flip = $state(false);
  /** the 2θ zoom, and the window of rows a drag down chose (series indices) */
  let zoom = $state.raw<[number, number] | null>(null);
  let rowWindow = $state.raw<[number, number] | null>(null);
  let cut = $state<number | null>(null);
  let width = $state(CUT_WIDTH);
  /** a shift-click's rows, which the profile under the map averages */
  let band = $state.raw<[number, number] | null>(null);
  let hover = $state.raw<{ row: number | null; tt: number | null } | null>(null);
  let canvas = $state<HTMLCanvasElement | null>(null);
  let boxW = $state(0);
  let boxH = $state(0);
  /** a press in progress, and the frame the last draw laid out */
  let drag: Drag | null = null;
  let dragBox = $state.raw<Drag | null>(null);
  let geo: Geometry | null = null;
  /** where the typed width sits, beside the cut's profile, from the last draw */
  let fieldAt = $state.raw<{ x: number; y: number } | null>(null);
  let asked = 0;

  interface Drag {
    zone: "map" | "profile";
    x0: number;
    y0: number;
    x1: number | null;
    y1: number | null;
    row: number | null;
    shift: boolean;
    part?: "left" | "right" | "move" | "new";
    cut0?: number | null;
    width0?: number;
    moved?: boolean;
  }
  interface Geometry {
    Lm: number; R: number; T: number; Hm: number; rh: number; rows: number[];
    pT: number; pB: number; Hp: number; vx0: number; vx1: number;
    t0: number; t1: number;
  }

  const header = $derived(answer?.header ?? null);
  const sel = $derived(selected ?? 0);
  const step = $derived.by(() => {
    const tt = answer?.arrays.two_theta;
    return tt && tt.length > 1 ? (tt[tt.length - 1] - tt[0]) / (tt.length - 1) : 0.001;
  });
  const titleLabel = $derived(header ? header.labels[sel] ?? "" : "");
  const titleX = $derived(header ? coord(header, sel) ?? "" : "");

  // ask again when the staged list moves, and when a run starts or ends
  $effect(() => {
    void stamp;
    void busy;
    untrack(() => void load());
  });

  async function load() {
    const mine = ++asked;
    try {
      const buffer = await api.seriesMap();
      const { unpack } = await import("./rxplot.mjs");
      if (mine !== asked) return;
      const next = unpack(buffer) as unknown as MapAnswer;
      answer = next;
      failure = "";
      empty = false;
      const n = next.header.n_rows;
      if (selected != null && selected >= n) selected = n ? n - 1 : null;
      if (band && Math.max(...band) >= n) band = null;
      if (rowWindow && Math.max(...rowWindow) >= n) rowWindow = null;
    } catch (error) {
      if (mine !== asked) return;
      answer = null;
      empty = error instanceof ApiError && error.code === "NO_SERIES";
      failure = empty ? "" : (error as Error).message;
    }
  }

  function fmtX(x: number): string {
    return String(Number(x.toPrecision(6)));
  }

  /** a row's label at the axis: its coordinate, else its number */
  function rowLabel(h: MapHeader, i: number): string {
    return h.x.every((v) => v != null) ? fmtX(h.x[i]!) : String(i + 1);
  }

  /** "T 300", or null while the series has no coordinate: the server's axis
   *  reads "index" until every pattern has one (`SeriesSetup.axis_label`) */
  function coord(h: MapHeader, i: number): string | null {
    return h.axis !== "index" && h.x[i] != null ? `${h.axis} ${fmtX(h.x[i]!)}` : null;
  }

  // redraw on every input; the theme waits a microtask, as the shell stamps
  // it in an effect of the same flush
  $effect(() => {
    void [theme, boxW, boxH, mode, show, cuts, flip, zoom, rowWindow, cut, width, band, hover,
          dragBox, sel];
    const a = answer, cv = canvas;
    if (!a || !cv) return;
    void Promise.resolve().then(() => draw(cv, a));
  });

  function draw(cv: HTMLCanvasElement, a: MapAnswer) {
    const ctx = cv.getContext?.("2d");
    if (!ctx) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = devicePixelRatio || 1;
    if (!W || !H) return;
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const style = getComputedStyle(document.body);
    const tok = (n: string) => style.getPropertyValue(n).trim();
    const h = a.header, tt = a.arrays.two_theta, m = h.n_cols;
    if (!tt.length || !h.n_rows) return;
    const diff = show === "diff", wf = mode === "waterfall";
    const cells = diff ? a.arrays.diff : a.arrays.obs;
    const rows = shownRows(h.n_rows, rowWindow, flip), nr = rows.length;
    const fit = (i: number) => diff && !!a.arrays.diff && h.fitted[i];

    // the frame, the prototype's: the map, the profile under it, the profile
    // beside it, and the colour key in the corner the two leave empty
    const Lm = 64, Vw = cuts && W >= 520 ? Math.min(170, Math.round(W * 0.2)) : 0, G = Vw ? 14 : 0;
    const R = W - Vw - G - 8, T = 8;
    const Hp = cuts ? Math.max(90, Math.min(150, Math.round(H * 0.2))) : 0, gap = cuts ? 10 : 0;
    const corner = !!(Vw && Hp), B = !wf && !corner ? 46 : 24;
    const Hm = H - T - B - Hp - gap, rh = Hm / nr;
    if (!(Hm > 0) || !(R > Lm)) return;
    const [t0, t1] = zoom ?? [tt[0], tt[tt.length - 1]];
    const px = (t: number) => Lm + ((t - t0) / (t1 - t0)) * (R - Lm);
    const pT = T + Hm + gap, pB = pT + Hp;
    geo = { Lm, R, T, Hm, rh, rows, pT, pB, Hp, vx0: R + G, vx1: R + G + Vw, t0, t1 };
    const at = Vw && cut != null ? { x: R + G, y: pT + 34 } : null;
    if (at?.x !== fieldAt?.x || at?.y !== fieldAt?.y) fieldAt = at;

    const ground = hexRgb(tok("--panel")), unfit = hexRgb(tok("--hover"));
    const font = style.fontFamily;
    ctx.font = `11px ${font}`;

    // the rows, at device pixels: each pixel column's highest count, or its
    // mean difference
    const w = Math.max(1, Math.floor(R - Lm));
    const cssRanges = columnRanges(tt, t0, t1, w);
    let top = 0;
    if (!diff) {
      for (const i of rows) {
        const v = rowColumns(a.arrays.obs, i * m, cssRanges, false);
        for (const x of v) if (x > top) top = x;
      }
    }
    if (!wf && cells) {
      const dw = Math.max(1, Math.round((R - Lm) * dpr)), dh = Math.max(1, Math.round(Hm * dpr));
      const ranges = columnRanges(tt, t0, t1, dw);
      const img = ctx.createImageData(dw, dh), d = img.data;
      rows.forEach((i, r) => {
        const y0 = Math.round(r * rh * dpr), y1 = Math.round((r + 1) * rh * dpr);
        const v = diff && !fit(i) ? null : rowColumns(cells, i * m, ranges, diff);
        for (let c = 0; c < dw; c++) {
          let rgb: Rgb;
          if (!v) rgb = unfit;
          else if (Number.isNaN(v[c])) rgb = ground;
          else rgb = diff ? diverging(v[c], ground) : cividis(logFraction(v[c], top));
          for (let y = y0; y < y1; y++) {
            const o = (y * dw + c) * 4;
            d[o] = rgb[0];
            d[o + 1] = rgb[1];
            d[o + 2] = rgb[2];
            d[o + 3] = 255;
          }
        }
      });
      ctx.putImageData(img, Math.round(Lm * dpr), Math.round(T * dpr));
    } else if (!wf) {
      // Difference before any fit: every row unfitted
      ctx.fillStyle = tok("--hover");
      ctx.fillRect(Lm, T, R - Lm, Hm);
    } else {
      // each pattern a line on its row's baseline, reaching up over the rows
      // above, drawn top row first and filled to its baseline, so a lower row
      // hides what lies behind it
      const amp = Math.min(Hm * 0.4, rh * 2.2), scale = top || 1;
      ctx.save();
      ctx.beginPath();
      ctx.rect(Lm, T, R - Lm, Hm);
      ctx.clip();
      rows.forEach((i, r) => {
        if (diff && !fit(i)) return;
        const base = T + (r + 1) * rh - 2, mid = T + (r + 0.5) * rh;
        const v = rowColumns(cells!, i * m, cssRanges, diff);
        const yv = (c: number) => Number.isNaN(v[c]) ? (diff ? mid : base)
          : diff ? mid - Math.max(-1.4, Math.min(1.4, v[c] / DIFF_LIMIT)) * rh * 0.9
            : base - (v[c] / scale) * amp;
        ctx.beginPath();
        ctx.moveTo(Lm, base);
        for (let c = 0; c < w; c++) ctx.lineTo(Lm + c + 0.5, yv(c));
        ctx.lineTo(R, base);
        ctx.closePath();
        if (!diff) {
          ctx.fillStyle = tok("--panel");
          ctx.fill();
        }
        const on = i === sel;
        ctx.strokeStyle = on ? tok("--accent") : tok(diff ? "--plot-diff" : "--plot-obs");
        ctx.lineWidth = on ? 1.4 : 0.9;
        ctx.beginPath();
        for (let c = 0; c < w; c++) {
          if (c) ctx.lineTo(Lm + c + 0.5, yv(c));
          else ctx.moveTo(Lm + 0.5, yv(c));
        }
        ctx.stroke();
      });
      ctx.restore();
      ctx.strokeStyle = tok("--line");
      ctx.lineWidth = 1;
      ctx.strokeRect(Lm + 0.5, T + 0.5, R - Lm - 1, Hm - 1);
    }

    // row labels, every row where they fit, else every few; the axis title
    ctx.fillStyle = tok("--muted");
    ctx.textAlign = "right";
    const every = Math.max(1, Math.ceil(13 / rh));
    rows.forEach((i, r) => {
      if (r % every === 0 || i === sel) ctx.fillText(rowLabel(h, i), Lm - 6, T + r * rh + rh / 2 + 4);
    });
    ctx.save();
    ctx.translate(14, T + Hm / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText(h.axis === "index" ? "Pattern" : h.axis, 0, 0);
    ctx.restore();

    // the selected row, the hovered row, the averaged rows and the cut
    const rs = rows.indexOf(sel);
    if (rs >= 0 && !wf) {
      ctx.strokeStyle = tok("--accent");
      ctx.lineWidth = 2;
      ctx.strokeRect(Lm - 1, T + rs * rh, R - Lm + 2, rh);
    }
    if (hover?.row != null && hover.row !== sel && !wf) {
      const rr = rows.indexOf(hover.row);
      if (rr >= 0) {
        ctx.strokeStyle = tok("--fg");
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.strokeRect(Lm - 0.5, T + rr * rh + 0.5, R - Lm + 1, rh - 1);
        ctx.setLineDash([]);
      }
    }
    const averaged = bandRows(band, sel);
    const cutIn = cuts && cut != null && cut >= t0 && cut <= t1;
    const cx = cutIn ? px(cut!) : 0, hw = Math.max(1, (width / 2 / (t1 - t0)) * (R - Lm));
    if (cuts && averaged.length > 1 && averaged.some((i) => rows.includes(i))) {
      const at = averaged.map((i) => rows.indexOf(i)).filter((k) => k >= 0);
      const r0 = Math.min(...at), r1 = Math.max(...at);
      ctx.strokeStyle = tok("--accent");
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 3]);
      ctx.strokeRect(Lm - 0.5, T + r0 * rh, R - Lm + 1, (r1 - r0 + 1) * rh);
      ctx.setLineDash([]);
      if (cutIn) {
        ctx.lineWidth = 2;
        ctx.strokeRect(cx - hw, T + r0 * rh, 2 * hw, (r1 - r0 + 1) * rh);
      }
    }
    if (cutIn) {
      ctx.fillStyle = tok("--accent");
      ctx.globalAlpha = 0.16;
      ctx.fillRect(cx - hw, T, 2 * hw, Hm);
      ctx.globalAlpha = 1;
      const x = Math.round(cx) + 0.5;
      ctx.strokeStyle = tok("--panel");
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(x, T);
      ctx.lineTo(x, Hp ? pB : T + Hm);
      ctx.stroke();
      ctx.strokeStyle = tok("--accent");
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // the profile under the map, on its 2θ axis: the selected pattern, or the
    // mean of the averaged rows
    if (Hp) {
      ctx.strokeStyle = tok("--line");
      ctx.lineWidth = 1;
      ctx.strokeRect(Lm + 0.5, pT + 0.5, R - Lm - 1, Hp - 1);
      const these = diff ? averaged.filter(fit) : averaged;
      if (diff && !these.length) {
        ctx.fillStyle = tok("--muted");
        ctx.textAlign = "left";
        ctx.fillText("Not fitted yet", Lm + 8, pT + 18);
      } else if (cells) {
        const per = these.map((i) => rowColumns(cells, i * m, cssRanges, diff));
        const lo = new Float64Array(w).fill(NaN), hi = new Float64Array(w).fill(NaN);
        let low = Infinity, high = -Infinity;
        for (let c = 0; c < w; c++) {
          let s = 0, n = 0;
          for (const v of per) if (!Number.isNaN(v[c])) { s += v[c]; n += 1; }
          if (!n) continue;
          lo[c] = hi[c] = s / n;
          low = Math.min(low, lo[c]);
          high = Math.max(high, hi[c]);
        }
        if (diff) {
          const e = Math.max(DIFF_LIMIT, Math.abs(low), Math.abs(high));
          low = -e;
          high = e;
        } else low = Math.min(0, low);
        const qy = (v: number) => pB - 4 - ((v - low) / ((high - low) || 1)) * (Hp - 28);
        if (diff) {
          ctx.fillStyle = tok("--hover");
          ctx.fillRect(Lm + 1, qy(3), R - Lm - 2, qy(-3) - qy(3));
          ctx.strokeStyle = tok("--line");
          ctx.beginPath();
          ctx.moveTo(Lm, Math.round(qy(0)) + 0.5);
          ctx.lineTo(R, Math.round(qy(0)) + 0.5);
          ctx.stroke();
        }
        ctx.save();
        ctx.beginPath();
        ctx.rect(Lm, pT, R - Lm, Hp);
        ctx.clip();
        ctx.strokeStyle = tok(diff ? "--plot-diff" : "--plot-obs");
        ctx.lineWidth = 1;
        ctx.beginPath();
        let pen = false;
        for (let c = 0; c < w; c++) {
          if (Number.isNaN(lo[c])) { pen = false; continue; }
          if (pen) ctx.lineTo(Lm + c + 0.5, qy(lo[c]));
          else ctx.moveTo(Lm + c + 0.5, qy(lo[c]));
          pen = true;
        }
        ctx.stroke();
        ctx.restore();
        ctx.fillStyle = tok("--muted");
        ctx.textAlign = "right";
        const marks: [number, string][] = diff ? [[3, "+3"], [-3, "−3"]]
          : [[high, countLabel(high)]];
        for (const [v, t] of marks) ctx.fillText(t, Lm - 6, qy(v) + 4);
        ctx.textAlign = "left";
        ctx.fillStyle = tok("--fg");
        ctx.font = `600 11px ${font}`;
        const name = (i: number) => [h.labels[i], coord(h, i)].filter(Boolean).join(", ");
        const what = these.length > 1
          ? `Mean of ${these.length} patterns, ${rowLabel(h, these[0])}–${rowLabel(h, these[these.length - 1])}`
          : name(these[0]);
        ctx.fillText(what + (diff ? " · difference in esd" : ""), Lm + 8, pT + 16);
        ctx.font = `11px ${font}`;
      }
      if (cutIn) {
        // the averaging bar, with a grip on each edge
        const xa = cx - hw, xb = cx + hw;
        ctx.fillStyle = tok("--accent");
        ctx.globalAlpha = 0.13;
        ctx.fillRect(xa, pT + 1, xb - xa, Hp - 2);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = tok("--accent");
        ctx.lineWidth = 1;
        for (const e of [xa, xb]) {
          ctx.beginPath();
          ctx.moveTo(Math.round(e) + 0.5, pT + 1);
          ctx.lineTo(Math.round(e) + 0.5, pB - 1);
          ctx.stroke();
          ctx.beginPath();
          ctx.roundRect(e - 2.5, pT + Hp / 2 - 9, 5, 18, 2.5);
          ctx.fill();
        }
      }
    }

    // 2θ labels under whichever of the map and the profile is lowest
    const st = labelStep(t1 - t0, R - Lm), dg = Math.max(0, -Math.floor(Math.log10(st)));
    ctx.fillStyle = tok("--muted");
    ctx.textAlign = "center";
    for (let t = Math.ceil(t0 / st) * st; t <= t1 + st * 1e-9; t += st) {
      ctx.fillText(`${t.toFixed(dg)}°`, px(t), corner || wf || !Hp ? H - 6 : H - 28);
    }

    // the profile beside the map, on its rows: each pattern at the cut
    if (Vw) {
      const vx0 = R + G;
      ctx.strokeStyle = tok("--line");
      ctx.lineWidth = 1;
      ctx.strokeRect(vx0 + 0.5, T + 0.5, Vw - 1, Hm - 1);
      if (cut == null) {
        ctx.fillStyle = tok("--muted");
        ctx.textAlign = "center";
        ctx.fillText("Click the map", vx0 + Vw / 2, T + Hm / 2 - 4);
        ctx.fillText("to set a cut", vx0 + Vw / 2, T + Hm / 2 + 12);
      } else if (cells) {
        const these = rows.filter((i) => !diff || fit(i));
        const V = these.map((i) => cutValue(cells, i * m, tt, cut!, width));
        const finite = V.filter(Number.isFinite);
        let lo = Math.min(...finite), hi = Math.max(...finite);
        if (diff) {
          const e = Math.max(3, Math.abs(lo), Math.abs(hi));
          lo = -e;
          hi = e;
        } else {
          const pad = (hi - lo) * 0.08 || 1;
          lo -= pad;
          hi += pad;
        }
        const qx = (v: number) => vx0 + 6 + ((v - lo) / ((hi - lo) || 1)) * (Vw - 12);
        if (diff) {
          ctx.strokeStyle = tok("--line");
          ctx.beginPath();
          ctx.moveTo(Math.round(qx(0)) + 0.5, T);
          ctx.lineTo(Math.round(qx(0)) + 0.5, T + Hm);
          ctx.stroke();
        }
        const ink = tok(diff ? "--plot-diff" : "--plot-obs");
        ctx.strokeStyle = ink;
        ctx.fillStyle = ink;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        let pen = false;
        these.forEach((i, k) => {
          if (!Number.isFinite(V[k])) { pen = false; return; }
          const y = T + rows.indexOf(i) * rh + rh / 2;
          if (pen) ctx.lineTo(qx(V[k]), y);
          else ctx.moveTo(qx(V[k]), y);
          pen = true;
        });
        ctx.stroke();
        these.forEach((i, k) => {
          if (!Number.isFinite(V[k])) return;
          ctx.beginPath();
          ctx.arc(qx(V[k]), T + rows.indexOf(i) * rh + rh / 2, i === sel ? 3.6 : 2.4, 0, 7);
          ctx.fill();
        });
        ctx.fillStyle = tok("--muted");
        ctx.textAlign = "center";
        const ticks: [number, string][] = diff ? [[-3, "−3"], [0, "0"], [3, "+3"]]
          : [[lo, countLabel(Math.max(0, lo))], [hi, countLabel(hi)]];
        for (const [v, t] of ticks) if (v >= lo && v <= hi) ctx.fillText(t, qx(v), T + Hm + 16);
        ctx.textAlign = "left";
        ctx.fillStyle = tok("--fg");
        ctx.font = `600 11px ${font}`;
        ctx.fillText(`At ${cut.toFixed(3)}°`, vx0, pT + 28);
        ctx.font = `11px ${font}`;
      }
    }

    // a drag in progress: the zoom box, or with shift the area to average
    const D = dragBox;
    if (D && D.zone === "map" && (D.x1 != null || D.y1 != null)) {
      const xa = Math.min(D.x0, D.x1 ?? D.x0), xb = Math.max(D.x0, D.x1 ?? D.x0);
      const ya = D.y1 != null ? Math.min(D.y0, D.y1) : T, yb = D.y1 != null ? Math.max(D.y0, D.y1) : T + Hm;
      ctx.strokeStyle = tok("--accent");
      ctx.fillStyle = tok("--accent");
      if (D.shift) {
        ctx.lineWidth = 1.5;
        ctx.strokeRect(xa, ya, Math.max(2, xb - xa), yb - ya);
      } else {
        ctx.globalAlpha = 0.18;
        ctx.fillRect(D.x1 != null ? xa : Lm, ya, D.x1 != null ? xb - xa : R - Lm, yb - ya);
        ctx.globalAlpha = 1;
      }
    }

    // the colour key: in the corner the two profiles leave empty, else in a
    // strip under the map
    if (!wf) {
      const kw = corner ? Math.min(Vw - 6, 150) : 130, kx = corner ? R + G : R - kw - 46;
      const ky = corner ? pB - 22 : H - 15;
      for (let k = 0; k < kw; k++) {
        const f = k / kw, rgb = diff ? diverging((f * 2 - 1) * DIFF_LIMIT, ground) : cividis(f);
        ctx.fillStyle = `rgb(${rgb.join(",")})`;
        ctx.fillRect(kx + k, ky, 1.2, 8);
      }
      const lo = diff ? `−${DIFF_LIMIT}` : "0", hi = diff ? `+${DIFF_LIMIT} esd` : countLabel(top);
      ctx.fillStyle = tok("--muted");
      if (corner) {
        ctx.textAlign = "left";
        ctx.fillText(lo, kx, ky + 21);
        ctx.textAlign = "center";
        ctx.fillText(diff ? "0" : "log", kx + kw / 2, ky + 21);
        ctx.textAlign = "right";
        ctx.fillText(hi, kx + kw, ky + 21);
      } else {
        ctx.textAlign = "right";
        ctx.fillText(lo, kx - 6, ky + 8);
        ctx.textAlign = "left";
        ctx.fillText(hi + (diff ? "" : " (log)"), kx + kw + 6, ky + 8);
      }
    }
  }

  // ------------------------------------------------------------ the pointer
  function local(e: PointerEvent | MouseEvent): [number, number] {
    const r = canvas!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top];
  }

  const ix = (g: Geometry, X: number) => g.t0 + ((X - g.Lm) / (g.R - g.Lm)) * (g.t1 - g.t0);
  const pxOf = (g: Geometry, t: number) => g.Lm + ((t - g.t0) / (g.t1 - g.t0)) * (g.R - g.Lm);

  function rowAt(g: Geometry, Y: number): number | null {
    if (Y < g.T || Y >= g.T + g.Hm) return null;
    return g.rows[Math.min(g.rows.length - 1, Math.floor((Y - g.T) / g.rh))] ?? null;
  }

  function hit(X: number, Y: number): { zone: "map" | "profile" | "side"; row: number | null } | null {
    const g = geo;
    if (!g) return null;
    const row = rowAt(g, Y);
    if (X >= g.Lm && X <= g.R && row != null) return { zone: "map", row };
    if (g.Hp && X >= g.Lm && X <= g.R && Y >= g.pT && Y <= g.pB) return { zone: "profile", row: null };
    if (X >= g.vx0 && X <= g.vx1 && row != null) return { zone: "side", row };
    return null;
  }

  function part(X: number): "left" | "right" | "move" | "new" {
    const g = geo!;
    if (cut == null) return "new";
    return barPart(X, pxOf(g, cut - width / 2), pxOf(g, cut + width / 2));
  }

  function choose(row: number) {
    selected = row;
  }

  function down(e: PointerEvent) {
    if (e.button !== 0) return;
    const [X, Y] = local(e), h = hit(X, Y);
    if (!h) return;
    if (h.zone === "side") {
      band = null;
      choose(h.row!);
      return;
    }
    canvas!.setPointerCapture?.(e.pointerId);
    drag = h.zone === "profile"
      ? { zone: "profile", x0: X, y0: Y, x1: null, y1: null, row: null, shift: false,
          part: part(X), cut0: cut, width0: width, moved: false }
      : { zone: "map", x0: X, y0: Y, x1: null, y1: null, row: h.row, shift: e.shiftKey };
  }

  function move(e: PointerEvent) {
    const g = geo;
    if (!g) return;
    const [X0, Y0] = local(e), X = Math.min(g.R, Math.max(g.Lm, X0));
    const d = drag;
    if (d?.zone === "profile") {
      if (Math.abs(X - d.x0) > 3) d.moved = true;
      if (!d.moved) return;
      const t = ix(g, X), t0 = ix(g, d.x0);
      let lo: number, hi: number;
      if (d.part === "new" || d.cut0 == null) {
        lo = Math.min(t0, t);
        hi = Math.max(t0, t);
      } else if (d.part === "move") {
        lo = d.cut0 - d.width0! / 2 + (t - t0);
        hi = lo + d.width0!;
      } else {
        const fixed = d.part === "left" ? d.cut0 + d.width0! / 2 : d.cut0 - d.width0! / 2;
        lo = Math.min(fixed, t);
        hi = Math.max(fixed, t);
      }
      cut = (lo + hi) / 2;
      width = Math.max(step, hi - lo);
      return;
    }
    if (d) {
      const Y = Math.min(g.T + g.Hm - 1, Math.max(g.T, Y0));
      if (Math.abs(X - d.x0) > 4) d.x1 = X;
      if (Math.abs(Y - d.y0) > g.rh * 0.6) d.y1 = Y;
      dragBox = { ...d };
      return;
    }
    const h = hit(X0, Y0);
    canvas!.style.cursor = !h ? "" : h.zone === "side" ? "pointer"
      : h.zone === "profile" ? { left: "ew-resize", right: "ew-resize", move: "grab", new: "crosshair" }[part(X0)]
        : "crosshair";
    const row = h && h.zone !== "profile" ? h.row : null;
    const at = h && h.zone !== "side" ? ix(g, X0) : null;
    hover = { row, tt: at };
    onreadout(readout(row ?? sel, at));
  }

  function up(e: PointerEvent) {
    const d = drag, g = geo;
    drag = null;
    dragBox = null;
    if (!d || !g) return;
    const [X0] = local(e);
    if (d.zone === "profile") {
      if (!d.moved) cut = ix(g, Math.min(g.R, Math.max(g.Lm, X0)));
      cut = Number(cut!.toFixed(4));
      width = roundWidth(width, step);
      return;
    }
    const across = d.x1 != null && Math.abs(d.x1 - d.x0) > 6;
    const endRow = d.y1 != null ? rowAt(g, d.y1) : null;
    const down_ = endRow != null && d.row != null && endRow !== d.row;
    const span = (): [number, number] => {
      const a = ix(g, Math.min(d.x0, d.x1!)), b = ix(g, Math.max(d.x0, d.x1!));
      return [a, b];
    };
    if (d.shift && cuts && (across || down_)) {
      band = down_ ? [d.row!, endRow!] : null;
      if (across) {
        const [a, b] = span();
        cut = Number(((a + b) / 2).toFixed(4));
        width = roundWidth(b - a, step);
      }
      return;
    }
    if (across || down_) {
      if (across) zoom = span();
      if (down_) rowWindow = [d.row!, endRow!];
      return;
    }
    if (d.row == null) return;
    if (!cuts) {
      choose(d.row);
      return;
    }
    cut = Number(ix(g, d.x0).toFixed(4));
    if (d.shift && d.row !== sel) band = [sel, d.row];
    else {
      band = null;
      choose(d.row);
    }
  }

  function leave() {
    hover = null;
    onreadout(null);
  }

  function showAll() {
    zoom = null;
    rowWindow = null;
  }

  function typed(e: Event) {
    const v = Number((e.currentTarget as HTMLInputElement).value);
    if (Number.isFinite(v) && v > 0) width = roundWidth(v, step);
  }

  /** The status bar's line for pattern `row` at 2θ `at` (`gui/STYLE.md` § Plots). */
  function readout(row: number, at: number | null): StatusReadout | null {
    const a = answer, h = header;
    if (!a || !h) return null;
    const items: StatusReadout["items"] = [
      { id: "row", label: "Pattern", value: h.labels[row] ?? "",
        slot: Math.max(...h.labels.map((l) => l.length)) },
    ];
    if (coord(h, row)) items.push({ id: "x", label: h.axis, value: fmtX(h.x[row]!), slot: 8 });
    if (at != null) {
      items.push({ id: "pos", label: "2θ", value: `${at.toFixed(3)}°`, slot: 8 });
      const diff = show === "diff", cells = diff ? a.arrays.diff : a.arrays.obs;
      const v = cells && (!diff || h.fitted[row])
        ? cutValue(cells, row * h.n_cols, a.arrays.two_theta, at, 0) : NaN;
      items.push({ id: "value", label: diff ? CURVE_WORDS.diff : CURVE_WORDS.obs, slot: 7,
                   value: !Number.isFinite(v) ? "—" : diff
                     ? `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}σ` : String(Math.round(v)) });
    }
    const rwp = h.rwp[row];
    if (rwp != null) items.push({ id: "rwp", label: "Rwp", value: `${(rwp * 100).toFixed(2)} %`, slot: 7 });
    return { items, dropOrder: ["rwp", "x"] };
  }
</script>

<div class="mapgraph">
  <div class="ghead">
    <div class="gtitle">
      {#if header}
        <b>{titleLabel}</b>{#if titleX}<span>{titleX}</span>{/if}
      {:else if empty}<span>No patterns yet. Add them in the Patterns step.</span>
      {:else if failure}<span class="bad">{failure}</span>{/if}
    </div>
    <div class="gctl">
      <span class="segmented" role="group" aria-label="Draw">
        <button class:on={mode === "map"} aria-pressed={mode === "map"}
          onclick={() => (mode = "map")}>Map</button>
        <button class:on={mode === "waterfall"} aria-pressed={mode === "waterfall"}
          onclick={() => (mode = "waterfall")}>Waterfall</button>
      </span>
      <span class="segmented" role="group" aria-label="Show">
        <button class:on={show === "obs"} aria-pressed={show === "obs"}
          onclick={() => (show = "obs")}>Observed</button>
        <button class:on={show === "diff"} aria-pressed={show === "diff"}
          onclick={() => (show = "diff")}>Difference</button>
      </span>
      <button class="ib" aria-pressed={flip} aria-label="Flip vertically"
        title="Flip vertically: first pattern at the bottom" onclick={() => (flip = !flip)}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><path
          d="M5 2.5v11M2.5 5 5 2.5 7.5 5M11 13.5v-11M8.5 11 11 13.5 13.5 11" /></svg>
      </button>
      <label class="vg"><input type="checkbox" bind:checked={cuts} />Cuts</label>
      <button class="ghost" disabled={!zoom && !rowWindow} onclick={showAll}
        title="Drag across the map to zoom in; double-click it to show it all">Show all</button>
    </div>
  </div>
  <div class="view">
    <div class="plot" bind:clientWidth={boxW} bind:clientHeight={boxH}>
      <canvas bind:this={canvas} aria-label="Every pattern of the series as a row of colour"
        onpointerdown={down} onpointermove={move} onpointerup={up} onpointerleave={leave}
        ondblclick={showAll}></canvas>
      {#if fieldAt && cuts && cut != null}
        <label class="width" style:left="{fieldAt.x}px" style:top="{fieldAt.y}px">mean over
          <input class="num" inputmode="decimal" aria-label="Cut width in degrees 2θ"
            value={String(roundWidth(width, step))} onchange={typed} />°</label>
      {/if}
    </div>
  </div>
</div>

<style>
  .mapgraph {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .view {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    padding: 0 16px 12px;
  }

  /* the plot is a card on the window's ground, as the pattern's is */
  .plot {
    position: relative;
    flex: 1 1 auto;
    min-height: 300px;
    border-radius: 6px;
    background: var(--panel);
    overflow: hidden;
  }

  canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    touch-action: none;
  }

  /* a pressed toggle, the prototype's: the hover ground under the strong rule */
  .ib[aria-pressed="true"] {
    background: var(--hover);
    border-color: var(--line-strong);
    color: var(--fg);
  }

  .vg input[type="checkbox"] {
    margin: 0;
    accent-color: var(--accent);
  }

  .width {
    position: absolute;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--text-sm);
    color: var(--muted);
    white-space: nowrap;
  }

  .width input {
    width: 6ch;
    font-family: var(--mono-family);
    font-size: var(--text-sm);
  }
</style>
