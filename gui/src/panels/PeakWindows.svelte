<script lang="ts">
  /**
   * The Single peaks graph (WP-2128): three windows on the strongest
   * reflections, each at the last fit's scale.
   *
   * The maintainer's rulings of 2026-11-07: the single-peak comparison plots
   * are liked (third review), and the comparison scale is fixed at the last
   * fit while a preview changes, "the logical expectation of someone trying to
   * compare something" (fourth review). So the windows and their y ranges come
   * from the last fit's curves alone (`lib/peakwin.ts`), and a preview that
   * grows a peak runs off the top of its window.
   *
   * Drawn on a 2D canvas per window: observed points as crosses, the last fit,
   * the preview over it, and the normalised residual in a strip below. The
   * colours are the pattern's own tokens, read at every draw.
   */
  import type { Curves } from "rxplot";

  import { curveColors } from "../lib/plot";
  import type { PreviewAnswer } from "../lib/interactive";
  import { firstPicks, peakWindows, windowRange, type PeakWindow } from "../lib/peakwin";
  import { formatHkl } from "../lib/peaks";

  let {
    curves = null,
    preview = null,
    theme = "light",
    active = false,
  }: {
    curves?: Curves | null;
    preview?: PreviewAnswer | null;
    theme?: string;
    /** the tab is showing; a hidden canvas has no width to draw at */
    active?: boolean;
  } = $props();

  const windows = $derived(curves ? peakWindows(curves) : []);
  // a new set of windows (a fit landed) starts again from the first picks; a
  // payload framing the same reflections keeps the windows the person stepped
  // to. Derived rather than reset in an effect, so a render never indexes a
  // shorter set with the last set's picks
  const windowsKey = $derived(windows.map((w) => w.center).join(","));
  let stepped = $state<{ key: string; picks: number[] } | null>(null);
  const picks = $derived(stepped?.key === windowsKey ? stepped.picks : firstPicks(windows.length));

  /** The last fit's model on the pattern's channels, and its channels' 2θ. */
  const lastFit = $derived.by(() => {
    if (!curves) return null;
    const { two_theta: tt, fitted, y_calc: calc } = curves.arrays;
    const on: (number | null)[] = new Array(tt.length).fill(null);
    if (fitted && calc) for (let q = 0; q < fitted.length; q++) on[fitted[q]] = calc[q];
    return { on, tt: fitted ? Float64Array.from(fitted, (i) => tt[i]) : null };
  });

  let canvases: HTMLCanvasElement[] = $state([]);
  let width = $state(0);

  function step(slot: number, by: number) {
    const next = [...picks];
    next[slot] = Math.min(windows.length - 1, Math.max(0, next[slot] + by));
    stepped = { key: windowsKey, picks: next };
  }

  $effect(() => {
    void theme;
    void width;
    void picks;
    void preview;
    void windows;
    if (!active) return;
    // one microtask: the shell stamps the theme in an effect of the same flush
    void Promise.resolve().then(() => canvases.forEach((cv, i) => cv && draw(cv, windows[picks[i]])));
  });

  function draw(cv: HTMLCanvasElement, w: PeakWindow | undefined) {
    const ctx = cv.getContext?.("2d");
    if (!ctx || !curves || !lastFit || !w) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = devicePixelRatio || 1;
    if (!W || !H) return;
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const style = getComputedStyle(document.body);
    const c = curveColors((n) => style.getPropertyValue(n));
    const muted = style.getPropertyValue("--muted").trim() || "#888";
    const { arrays } = curves, tt = arrays.two_theta, obs = arrays.y_obs;
    const calc = arrays.y_calc, delta = arrays.delta;
    const L = 6, R = 6, T = 6, STRIP = 40, AXIS = 16, B = STRIP + AXIS;
    const ph = H - T - B, pw = W - L - R;
    const px = (x: number) => L + ((x - w.lo) / (w.hi - w.lo)) * pw;
    // the last fit's model on the pattern's channels, for the shared y range
    const [y0, y1] = windowRange(tt, obs, lastFit.on, w.lo, w.hi);
    const py = (y: number) => T + ((y1 - y) / (y1 - y0)) * ph;
    ctx.save();
    ctx.beginPath();
    ctx.rect(L, T, pw, ph);
    ctx.clip();
    // observed points: crosses, as every rietx pattern draws them
    ctx.strokeStyle = c.obs;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < tt.length; i++) {
      if (tt[i] < w.lo || tt[i] > w.hi) continue;
      const x = px(tt[i]), y = py(obs[i]), r = 2.4;
      ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r);
      ctx.moveTo(x - r, y + r); ctx.lineTo(x + r, y - r);
    }
    ctx.stroke();
    const line = (xs: ArrayLike<number>, ys: ArrayLike<number>, dash: number[], lw: number) => {
      ctx.strokeStyle = c.calc;
      ctx.lineWidth = lw;
      ctx.setLineDash(dash);
      ctx.beginPath();
      let pen = false;
      for (let q = 0; q < xs.length; q++) {
        if (xs[q] < w.lo || xs[q] > w.hi) { pen = false; continue; }
        const x = px(xs[q]), y = py(ys[q]);
        if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        pen = true;
      }
      ctx.stroke();
      ctx.setLineDash([]);
    };
    const fitTT = lastFit.tt;
    const pv = preview?.curves.arrays;
    // the last fit dashed once a preview is drawn over it: state rides on the
    // mark, never on a second colour (gui/CLAUDE.md, WP-1210)
    if (fitTT && calc) line(fitTT, calc, pv ? [4, 3] : [], pv ? 1 : 1.3);
    if (pv) line(pv.two_theta, pv.y_calc, [], 1.5);
    ctx.restore();
    // the residual strip: the preview's when there is one, else the last fit's
    const rx = pv ? pv.two_theta : fitTT, ry = pv ? pv.delta : delta;
    const top = T + ph + 4, mid = top + STRIP / 2;
    ctx.strokeStyle = c.zero;
    ctx.beginPath();
    ctx.moveTo(L, Math.round(mid) + 0.5);
    ctx.lineTo(W - R, Math.round(mid) + 0.5);
    ctx.stroke();
    if (rx && ry) {
      // the strip's scale is the last fit's too, as the pattern graph's
      // residual pane keeps its y range under a preview (WP-2128 call 10); a
      // preview residual past it is clipped to the strip
      let m = 5;
      if (fitTT && delta)
        for (let q = 0; q < fitTT.length; q++)
          if (fitTT[q] >= w.lo && fitTT[q] <= w.hi && Number.isFinite(delta[q])) m = Math.max(m, Math.abs(delta[q]));
      ctx.save();
      ctx.beginPath();
      ctx.rect(L, top, pw, STRIP);
      ctx.clip();
      ctx.strokeStyle = c.diff;
      ctx.lineWidth = 1;
      ctx.beginPath();
      let pen = false;
      for (let q = 0; q < rx.length; q++) {
        if (rx[q] < w.lo || rx[q] > w.hi) { pen = false; continue; }
        const x = px(rx[q]), y = mid - (ry[q] / m) * (STRIP / 2 - 2);
        if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        pen = true;
      }
      ctx.stroke();
      ctx.restore();
    }
    ctx.fillStyle = muted;
    ctx.font = `11px ${style.fontFamily}`;
    ctx.textAlign = "center";
    for (const f of [0.25, 0.75]) {
      const t = w.lo + f * (w.hi - w.lo);
      ctx.fillText(`${t.toFixed(2)}°`, px(t), H - 4);
    }
  }
</script>

<div class="peakwins" bind:clientWidth={width}>
  {#if !windows.length}
    <p class="muted">No fitted peaks to frame yet. Refine first.</p>
  {:else}
    {#each picks as k, slot (slot)}
      {@const w = windows[k]}
      <figure>
        <figcaption>
          <button class="pick step" aria-label="Previous peak" disabled={k <= 0}
            onclick={() => step(slot, -1)}>‹</button>
          <span class="mono tabular">{w.center.toFixed(2)}°</span>
          <span class="muted sub">{w.hkl ? formatHkl(w.hkl) : ""} {w.phase}</span>
          <button class="pick step" aria-label="Next peak" disabled={k >= windows.length - 1}
            onclick={() => step(slot, 1)}>›</button>
        </figcaption>
        <canvas bind:this={canvases[slot]}
          aria-label={`Peak window at ${w.center.toFixed(2)} degrees`}></canvas>
      </figure>
    {/each}
  {/if}
</div>

<style>
  .peakwins {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    align-content: start;
    gap: var(--s3);
    padding: var(--s2) var(--s3);
  }
  figure {
    margin: 0;
    min-width: 0;
  }
  figcaption {
    display: flex;
    align-items: center;
    gap: var(--s2);
    font-size: var(--text-sm);
    min-height: 1.8em;
    white-space: nowrap;
  }
  .sub {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .step {
    flex: 0 0 auto;
    width: 1.5em;
    text-align: center;
    cursor: pointer;
  }
  .step:disabled {
    color: var(--muted);
    cursor: default;
  }
  canvas {
    display: block;
    width: 100%;
    height: 260px;
    border: 1px solid var(--line);
  }
</style>
