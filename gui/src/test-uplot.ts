/**
 * uPlot as jsdom can run it (WP-1461, the module's finding 9).
 *
 * jsdom has no canvas: `getContext` returns null, and uPlot's constructor uses
 * the context at once. `test-setup.ts` puts this class in its place, so the
 * chart module (`rxplot.mjs`) and `lib/pattern.ts` run unchanged over it and a
 * test reads what each pane was asked to show.
 *
 * It keeps uPlot's state (data, scales, series, cursor, select), fires the
 * hooks the chart module registers, and runs the draw hooks on every paint
 * against a context that **records** each stroke and fill with the style it
 * was made in, and the clip it was made under. It draws no series itself; a paint records one `series` entry
 * per shown series with its resolved stroke instead. The plot area is 1000 by
 * 300 CSS px at every size, so a test can aim a pointer at a 2θ.
 *
 * What uPlot paints from all this is a browser's question:
 * `tests/test_rxplot_browser.py` and `tests/test_gui_browser.py` answer it.
 */

/** One call on the recording context, or one series a paint showed. */
export interface Mark {
  op: "stroke" | "fill" | "fillRect" | "series";
  style: string;
  dash?: boolean;
  /** canvas-px points: `moveTo`/`lineTo`/`rect` origins as `[x, y]`, an `arc`'s
   *  centre as `[x, y, r]`, or a `fillRect`'s two corners */
  points?: number[][];
  /** the series' index, for a `series` entry */
  index?: number;
  /** the clip in force as `[x, y, width, height]` in canvas px, or null for
   *  none: the last `rect` before a `clip`, until the `restore` that undoes it */
  clip?: number[] | null;
}

const W = 1000;
const H = 300;

type Hook = (u: StubPlot, ...args: any[]) => void;

function recorder(marks: () => Mark[]) {
  let path: number[][] = [];
  let dash: number[] = [];
  let lastRect: number[] | null = null;
  let clip: number[] | null = null;
  const stack: any[] = [];
  const ctx: any = {
    strokeStyle: "#000000", fillStyle: "#000000", lineWidth: 1, globalAlpha: 1,
    save() { stack.push({ s: ctx.strokeStyle, f: ctx.fillStyle, w: ctx.lineWidth, d: dash, c: clip }); },
    restore() {
      const top = stack.pop();
      if (top) { ctx.strokeStyle = top.s; ctx.fillStyle = top.f; ctx.lineWidth = top.w; dash = top.d; clip = top.c; }
    },
    setLineDash(d: number[]) { dash = [...d]; },
    getLineDash() { return [...dash]; },
    beginPath() { path = []; },
    closePath() {},
    clip() { clip = lastRect; path = []; },
    moveTo(x: number, y: number) { path.push([x, y]); },
    lineTo(x: number, y: number) { path.push([x, y]); },
    arc(x: number, y: number, r: number) { path.push([x, y, r]); },
    rect(x: number, y: number, w: number, h: number) { path.push([x, y]); lastRect = [x, y, w, h]; },
    stroke() { marks().push({ op: "stroke", style: ctx.strokeStyle, dash: dash.length > 0, points: path, clip }); },
    fill() { marks().push({ op: "fill", style: ctx.fillStyle, points: path, clip }); },
    fillRect(x: number, y: number, w: number, h: number) {
      marks().push({ op: "fillRect", style: ctx.fillStyle, points: [[x, y], [x + w, y + h]], clip });
    },
    clearRect() {},
  };
  return ctx;
}

export class StubPlot {
  /** Every live instance, in the order they were built. */
  static instances: StubPlot[] = [];

  static rangeNum(min: number, max: number, pad: number): [number, number] {
    const span = max - min || Math.abs(max) || 1;
    return [min - pad * span, max + pad * span];
  }

  static rangeLog(min: number, max: number): [number, number] {
    return [min, max];
  }

  opts: any;
  data: any[];
  series: any[];
  scales: Record<string, { min: number | null; max: number | null; distr: number }>;
  cursor: any;
  select = { left: 0, top: 0, width: 0, height: 0 };
  root: HTMLDivElement;
  over: HTMLDivElement;
  width: number;
  height: number;
  bbox: { left: number; top: number; width: number; height: number };
  ctx: any;
  /** What the last paint drew, and how many paints there have been. */
  marks: Mark[] = [];
  paints = 0;
  destroyed = false;
  private hooks: Record<string, Hook[]>;

  constructor(opts: any, data: any[], target: HTMLElement) {
    this.opts = opts;
    this.data = data;
    this.width = opts.width;
    this.height = opts.height;
    const dpr = globalThis.devicePixelRatio || 1;
    this.bbox = { left: 0, top: 0, width: W * dpr, height: H * dpr };
    this.hooks = opts.hooks ?? {};
    this.series = opts.series.map((s: any) => ({ show: true, ...s }));
    this.cursor = { ...opts.cursor, drag: { ...(opts.cursor?.drag ?? {}) }, left: -10, top: -10, idx: null };
    this.scales = { x: { min: null, max: null, distr: 1 },
                    y: { min: null, max: null, distr: opts.scales?.y?.distr ?? 1 } };
    this.root = document.createElement("div");
    this.root.className = "uplot";
    this.over = document.createElement("div");
    this.over.className = "u-over";
    const box = { left: 0, top: 0, right: W, bottom: H, width: W, height: H, x: 0, y: 0 };
    this.over.getBoundingClientRect = () => ({ ...box, toJSON: () => box }) as DOMRect;
    Object.defineProperty(this.over, "clientWidth", { value: W });
    Object.defineProperty(this.over, "clientHeight", { value: H });
    this.root.appendChild(this.over);
    target.appendChild(this.root);
    this.ctx = recorder(() => this.marks);
    StubPlot.instances.push(this);
    this.fit(true);
    // uPlot's first paint is a microtask after the constructor, so a caller
    // holding the instance can finish building before a draw hook reads it
    queueMicrotask(() => { if (!this.destroyed && !this.paints) this.paint(); });
  }

  /** The pane key the chart module stamps on each instance. */
  get key(): string {
    return (this as any).__rxKey;
  }

  private fire(name: string, ...args: any[]) {
    for (const fn of this.hooks[name] ?? []) fn(this, ...args);
  }

  /** x over the data, and y through the scale's own range function over what is in view. */
  private fit(x: boolean) {
    const xs = this.data[0] ?? [];
    if (x) {
      let lo = Infinity, hi = -Infinity;
      for (const v of xs) { if (v < lo) lo = v; if (v > hi) hi = v; }
      this.scales.x.min = Number.isFinite(lo) ? lo : null;
      this.scales.x.max = Number.isFinite(hi) ? hi : null;
    }
    let lo = Infinity, hi = -Infinity;
    const { min, max } = this.scales.x;
    for (let s = 1; s < this.data.length; s++) {
      if (!this.series[s]?.show) continue;
      const ys = this.data[s];
      for (let i = 0; i < xs.length; i++) {
        const v = ys[i];
        if (v == null || (min != null && xs[i] < min) || (max != null && xs[i] > max)) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
    }
    const range = this.opts.scales?.y?.range;
    const [a, b] = typeof range === "function"
      ? range(this, Number.isFinite(lo) ? lo : null, Number.isFinite(hi) ? hi : null)
      : [lo, hi];
    this.scales.y.min = a ?? 0;
    this.scales.y.max = b ?? 1;
  }

  private paint() {
    this.paints++;
    this.marks = [];
    this.fire("drawClear");
    this.fire("drawAxes");
    this.series.forEach((s, i) => {
      if (i === 0 || !s.show) return;
      const stroke = typeof s.stroke === "function" ? s.stroke(this, i) : s.stroke;
      this.marks.push({ op: "series", style: String(stroke ?? ""), index: i });
    });
    this.fire("draw");
  }

  setData(data: any[], reset = true) {
    this.data = data;
    this.fit(reset);
    if (reset) this.fire("setScale", "x");
    this.paint();
  }

  setScale(key: string, { min, max }: { min: number; max: number }) {
    this.scales[key] = { ...this.scales[key], min, max };
    if (key === "x") this.fit(false);
    this.fire("setScale", key);
    this.paint();
  }

  setSeries(i: number, { show }: { show: boolean }) {
    this.series[i].show = show;
    this.fire("setSeries", i);
    this.paint();
  }

  setSize({ width, height }: { width: number; height: number }) {
    this.width = width;
    this.height = height;
    this.fire("setSize");
    this.paint();
  }

  /** A drag's box, in plot-area px, as uPlot hands it to a `setSelect` hook. */
  setSelect(select: { left: number; top: number; width: number; height: number }, fire = true) {
    this.select = { ...select };
    if (fire) this.fire("setSelect");
  }

  /** The pointer at `left`, `top` in plot-area px, as uPlot hands it to a `setCursor` hook. */
  setCursor({ left, top }: { left: number; top: number }) {
    this.cursor.left = left;
    this.cursor.top = top;
    const xs = this.data[0] ?? [];
    let idx: number | null = null;
    if (left >= 0 && xs.length) {
      const x = this.posToVal(left, "x");
      let best = Infinity;
      for (let i = 0; i < xs.length; i++) {
        const d = Math.abs(xs[i] - x);
        if (d < best) { best = d; idx = i; }
      }
    }
    this.cursor.idx = idx;
    this.fire("setCursor");
  }

  redraw() {
    this.paint();
  }

  batch(fn: () => void) {
    fn();
  }

  posToVal(pos: number, key: string): number {
    const { min, max } = this.scales[key];
    const lo = min ?? 0, hi = max ?? 1;
    return key === "x" ? lo + (pos / W) * (hi - lo) : hi - (pos / H) * (hi - lo);
  }

  valToPos(val: number, key: string, canvas = false): number {
    const { min, max } = this.scales[key];
    const lo = min ?? 0, hi = max ?? 1, k = canvas ? globalThis.devicePixelRatio || 1 : 1;
    const f = hi === lo ? 0 : (val - lo) / (hi - lo);
    return (key === "x" ? f * W : (1 - f) * H) * k;
  }

  destroy() {
    this.destroyed = true;
    this.root.remove();
    StubPlot.instances = StubPlot.instances.filter((u) => u !== this);
  }
}
