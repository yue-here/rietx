<script lang="ts">
  /**
   * The Fit peaks step's graph (WP-2202): one window per overlap group, as the
   * peak picker fitted it.
   *
   * The maintainer's design, round 11 (2026-11-08): six group windows, from the
   * group chosen in the side's list onward, each with the data, the group's fit,
   * its background envelope, a mark per line and the residual in esd with the
   * ±3 band. Every line's own curve is drawn under the sum as a tinted fill and
   * a line (round 11c), shown by default and hidden per line for the session
   * (round 11b call 23). The curves are the server's (`PeakEditor.curves`'s
   * `lines`), which sum to the group's fit less its envelope. An unused line
   * keeps a hollow mark here, where its curve is part of the fit (call 34).
   */
  import { curveColors, lens } from "../lib/plot";
  import type { GroupCurve, PeakRow, PeaksPayload } from "../lib/peaks";

  let {
    peaks = null,
    groups = [],
    focused = null,
    theme = "light",
    active = false,
  }: {
    peaks?: PeaksPayload | null;
    /** the groups to draw, in order: the side's list from the chosen row */
    groups?: number[];
    /** the group the side's list has selected, outlined here */
    focused?: number | null;
    theme?: string;
    /** the graph is showing; a hidden canvas has no width to draw at */
    active?: boolean;
  } = $props();

  /** a window per group, its member rows lowest 2θ first */
  const windows = $derived.by(() => {
    const byGroup = new Map((peaks?.groups ?? []).map((g) => [g.group, g]));
    const rows = peaks?.peaks ?? [];
    return groups.flatMap((k) => {
      const g = byGroup.get(k);
      if (!g) return [];
      const members = rows.filter((p) => p.group === k)
        .sort((a, b) => a.two_theta - b.two_theta);
      return [{ g, members }];
    });
  });

  /** the lines whose own curve is hidden, by row; session-local */
  let hidden = $state(new Set<number>());
  /** the line whose toggle the pointer is on: its curve is drawn darker */
  let lit = $state<number | null>(null);
  function toggle(index: number) {
    const next = new Set(hidden);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    hidden = next;
  }

  let canvases: HTMLCanvasElement[] = $state([]);
  let width = $state(0);

  $effect(() => {
    void theme;
    void width;
    void windows;
    void hidden;
    void lit;
    if (!active) return;
    // one microtask: the shell stamps the theme in an effect of the same flush
    void Promise.resolve().then(() =>
      canvases.forEach((cv, i) => cv && windows[i] && draw(cv, windows[i].g, windows[i].members)));
  });

  function draw(cv: HTMLCanvasElement, g: GroupCurve, members: PeakRow[]) {
    const ctx = cv.getContext?.("2d");
    if (!ctx || !peaks) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = devicePixelRatio || 1;
    if (!W || !H || g.two_theta.length < 2) return;
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const style = getComputedStyle(document.body);
    const c = curveColors((n) => style.getPropertyValue(n));
    const muted = style.getPropertyValue("--muted").trim() || "#888";
    const tt = g.two_theta, lo = tt[0], hi = tt[tt.length - 1];
    const L = 8, R = 8, T = 24, STRIP = 44, AXIS = 18, B = STRIP + AXIS;
    const ph = H - T - B, pw = W - L - R;
    const px = (x: number) => L + ((x - lo) / (hi - lo)) * pw;
    // the group's own channels; the payload's pattern is decimated, so it is
    // only the fallback for a server that sends no `y_obs`
    const obsT = g.y_obs ? tt : peaks.pattern.two_theta;
    const obsY = g.y_obs ?? peaks.pattern.y_obs;
    let top = 0;
    for (let i = 0; i < obsT.length; i++)
      if (obsT[i] >= lo && obsT[i] <= hi) top = Math.max(top, obsY[i]);
    for (const v of g.y_fit) top = Math.max(top, v);
    top = top * 1.1 || 1;
    const py = (y: number) => T + ((top - y) / top) * ph;
    const path = (xs: ArrayLike<number>, ys: ArrayLike<number>) => {
      ctx.beginPath();
      for (let q = 0; q < xs.length; q++) {
        const x = px(xs[q]), y = py(ys[q]);
        if (q) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      }
    };

    ctx.save();
    ctx.beginPath();
    ctx.rect(L, T, pw, ph);
    ctx.clip();
    // observed points: crosses, as every rietx pattern draws them
    ctx.strokeStyle = c.obs;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < obsT.length; i++) {
      if (obsT[i] < lo || obsT[i] > hi) continue;
      const x = px(obsT[i]), y = py(obsY[i]), r = 2.4;
      ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r);
      ctx.moveTo(x - r, y + r); ctx.lineTo(x + r, y - r);
    }
    ctx.stroke();
    // the group's background envelope, dashed
    ctx.strokeStyle = c.bkg;
    ctx.setLineDash([5, 4]);
    path(tt, g.y_env);
    ctx.stroke();
    ctx.setLineDash([]);
    // each line's own curve over the envelope: a tinted fill and a line
    if (members.length > 1) {
      for (const line of g.lines ?? []) {
        if (hidden.has(line.index)) continue;
        const on = lit === line.index;
        const ys = line.y.map((v, k) => g.y_env[k] + v);
        path(tt, ys);
        for (let k = tt.length - 1; k >= 0; k--) ctx.lineTo(px(tt[k]), py(g.y_env[k]));
        ctx.closePath();
        ctx.fillStyle = c.peak;
        ctx.globalAlpha = on ? 0.38 : 0.14;
        ctx.fill();
        ctx.globalAlpha = 1;
        path(tt, ys);
        ctx.strokeStyle = c.peak;
        ctx.lineWidth = on ? 2 : 1.1;
        ctx.stroke();
      }
    }
    // the group's fit
    ctx.strokeStyle = c.peakfit;
    ctx.lineWidth = 1.4;
    path(tt, g.y_fit);
    ctx.stroke();
    ctx.restore();

    // a mark per line above the window, filled when used, hollow when not, with
    // its number when the window holds more than one; numbers closer than
    // 14 px share a label
    ctx.font = `11px ${style.fontFamily}`;
    ctx.textAlign = "center";
    const labels: Array<{ x: number; x0: number; t: number[] }> = [];
    members.forEach((p, k) => {
      const x = Math.round(px(p.two_theta));
      lens(ctx, x, T - 6, 10, 3);
      if (p.usable) {
        ctx.fillStyle = c.peak;
        ctx.fill();
      } else {
        ctx.strokeStyle = c.peak;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      const last = labels[labels.length - 1];
      if (last && x - last.x < 14) {
        last.t.push(k + 1);
        last.x = (last.x0 + x) / 2;
      } else labels.push({ x, x0: x, t: [k + 1] });
    });
    if (members.length > 1) {
      ctx.fillStyle = muted;
      for (const l of labels) ctx.fillText(l.t.join(", "), l.x, T - 13);
    }

    // the residual in esd, with the ±3 band, at the window's own scale
    const s0 = H - B + 6, sh = STRIP - 12;
    let m = 5;
    for (const d of g.delta) if (Number.isFinite(d)) m = Math.max(m, Math.abs(d));
    const qy = (r: number) => s0 + sh / 2 - (r / m) * (sh / 2);
    ctx.fillStyle = c.zero;
    ctx.globalAlpha = 0.35;
    ctx.fillRect(L, qy(3), pw, qy(-3) - qy(3));
    ctx.globalAlpha = 1;
    ctx.strokeStyle = c.diff;
    ctx.lineWidth = 0.9;
    ctx.beginPath();
    g.delta.forEach((d, q) => {
      const x = px(tt[q]), y = qy(d);
      if (q) ctx.lineTo(x, y); else ctx.moveTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = muted;
    for (const f of [0.25, 0.75]) {
      const t = lo + f * (hi - lo);
      ctx.fillText(`${t.toFixed(2)}°`, px(t), H - 5);
    }
  }
</script>

<div class="fits" bind:clientWidth={width}>
  {#if !peaks?.groups?.length}
    <p class="muted">No group fits yet. Pick peaks first.</p>
  {:else if !windows.length}
    <!-- "To look at" can be empty on a clean pattern: say so, not a blank pane -->
    <p class="muted">No group in the list. Show all groups to see their fits.</p>
  {:else}
    {#each windows as { g, members }, slot (g.group)}
      <figure class:on={focused === g.group}>
        <figcaption>
          <span class="mono tabular">{g.two_theta[0].toFixed(2)}–{g.two_theta[g.two_theta.length - 1].toFixed(2)}°</span>
          <span class="muted sub">{members.length} {members.length === 1 ? "line" : "lines"},
            χ²ᵣ {g.chi2_red.toFixed(1)}</span>
          {#if members.length > 1}
            <div class="segmented" role="group" aria-label="Each line's own curve">
              {#each members as p, k (p.index)}
                <button class:on={!hidden.has(p.index)} aria-pressed={!hidden.has(p.index)}
                  aria-label="Curve of line {k + 1}, at {p.two_theta.toFixed(3)}°"
                  onclick={() => toggle(p.index)}
                  onmouseenter={() => (lit = p.index)}
                  onmouseleave={() => (lit = null)}>{k + 1}</button>
              {/each}
            </div>
          {/if}
        </figcaption>
        <canvas bind:this={canvases[slot]}
          aria-label={`Group fit from ${g.two_theta[0].toFixed(2)} degrees`}></canvas>
      </figure>
    {/each}
  {/if}
</div>

<style>
  .fits {
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
  canvas {
    display: block;
    width: 100%;
    height: 240px;
    border: 1px solid var(--line);
  }
  /* the window the side's list has chosen */
  figure.on canvas {
    border-color: var(--accent);
  }
</style>
