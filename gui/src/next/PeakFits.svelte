<script lang="ts">
  /**
   * The Fit peaks step's graph at `/next` (WP-2240, task 6): one window per
   * overlap group, as the peak picker fitted it, shown in the Peaks graph tab
   * while the peaks-and-indexing workflow is up.
   *
   * Round 11's design (2026-11-08), restated in WP-2240 § The design: six
   * windows from the group chosen in the step's list onward, each with the
   * data, the group's fit, its background envelope, a lens per line and the
   * residual in esd over its ±3 band. Every line's own curve is a tinted fill
   * under the sum, its Kα2 partner included, with a numbered toggle per line;
   * every curve starts shown and a hidden one stays hidden for the session
   * (calls 23, 30). An unused line keeps a hollow lens here, where its curve is
   * part of the fit (call 34). Each window's Refit fits it again through the
   * peak list's verb, one undoable step.
   *
   * The fit is the peak layer's second blue (`--plot-peakfit`), not the
   * prototype's orange, which `gui/STYLE.md` § Plots keeps for the
   * refinement's fit (principle 9). The curves are the server's
   * (`PeakEditor.curves`), which sum to the group's fit less its envelope.
   */
  import { curveColors, lens } from "../lib/plot";
  import type { GroupCurve, PeakRow, PeaksPayload } from "../lib/peaks";

  let {
    peaks = null,
    groups = [],
    total = 0,
    focused = null,
    theme = "light",
    busy = false,
    onrefit = () => {},
  }: {
    peaks?: PeaksPayload | null;
    /** the groups to draw, in order: the step's list from the chosen row */
    groups?: readonly number[];
    /** how many groups the step's list holds, for the title */
    total?: number;
    /** the group chosen in the step's list, outlined here */
    focused?: number | null;
    theme?: string;
    busy?: boolean;
    /** fit this group's window again */
    onrefit?: (group: number) => void;
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

  /** the lines whose own curve is hidden, by 2θ, so a refit that renumbers
   *  the rows keeps the choice; session-local (call 23) */
  let hidden = $state(new Set<string>());
  const key = (p: PeakRow) => p.two_theta.toFixed(4);
  /** the line whose toggle the pointer is on: its curve is drawn darker */
  let lit = $state<number | null>(null);
  function toggle(p: PeakRow) {
    const next = new Set(hidden);
    if (next.has(key(p))) next.delete(key(p));
    else next.add(key(p));
    hidden = next;
  }

  let canvases: HTMLCanvasElement[] = $state([]);
  let width = $state(0);

  $effect(() => {
    void theme; void width; void windows; void hidden; void lit;
    // one microtask: the frame stamps the theme in an effect of the same flush
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
    const style = getComputedStyle(cv);
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
        const row = members.find((p) => p.index === line.index);
        if (!row || hidden.has(key(row))) continue;
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

    // a lens per line above the window, filled when used, hollow when not,
    // with its number when the window holds more than one; numbers closer
    // than 14 px share a label
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

  const range = (g: GroupCurve) =>
    `${g.two_theta[0].toFixed(2)}–${g.two_theta[g.two_theta.length - 1].toFixed(2)}°`;
</script>

<div class="peakfits">
  <div class="ghead">
    <div class="gtitle">
      <b>Peak fits</b>
      {#if windows.length}
        <span class="stat">{focused == null ? `${total} group${total === 1 ? "" : "s"}`
          : `from ${windows[0].g.two_theta[0].toFixed(2)}°`}</span>
      {/if}
    </div>
  </div>
  <div class="wins" bind:clientWidth={width}>
    {#if !peaks?.groups?.length}
      <p class="empty">No group fits yet. Pick peaks first.</p>
    {:else if !windows.length}
      <!-- "To look at" can be empty on a clean pattern: say so, not a blank pane -->
      <p class="empty">No group in the list. Show all groups to see their fits.</p>
    {:else}
      {#each windows as { g, members }, slot (g.group)}
        <figure class:on={focused === g.group}>
          <figcaption>
            <span class="num">{range(g)}</span>
            <span class="sub">{members.length} {members.length === 1 ? "line" : "lines"},
              χ²ᵣ {g.chi2_red.toFixed(1)}</span>
            {#if members.length > 1}
              <span class="toggles" role="group" aria-label="Each line's own curve">
                {#each members as p, k (p.index)}
                  <button class="ib line" aria-pressed={!hidden.has(key(p))}
                    title="Show or hide the curve of line {k + 1}, at {p.two_theta.toFixed(3)}°"
                    onclick={() => toggle(p)}
                    onmouseenter={() => (lit = p.index)}
                    onmouseleave={() => (lit = null)}>{k + 1}</button>
                {/each}
              </span>
            {/if}
            <button class="ib refit" disabled={busy} title="Fit this window again"
              onclick={() => onrefit(g.group)}>Refit</button>
          </figcaption>
          <canvas bind:this={canvases[slot]}
            aria-label={`Group fit from ${g.two_theta[0].toFixed(2)} degrees`}></canvas>
        </figure>
      {/each}
    {/if}
  </div>
</div>

<style>
  .peakfits {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .wins {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    align-content: start;
    gap: 16px;
    padding: 0 16px 12px;
  }

  .empty {
    grid-column: 1 / -1;
    margin: 0;
    color: var(--muted);
  }

  figure {
    margin: 0;
    min-width: 0;
  }

  figcaption {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 26px;
    margin-bottom: 4px;
    white-space: nowrap;
  }

  figcaption .num {
    font-family: var(--mono-family);
    font-weight: 600;
  }

  .sub {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--muted);
    font-size: var(--text-sm);
  }

  .toggles {
    display: inline-flex;
    gap: 2px;
  }

  /* a line's toggle: its number, in the peak layer's blue while its curve
     shows, a faint dashed box while it is hidden (round 11c) */
  .line {
    min-width: 20px;
    height: 20px;
    font-family: var(--mono-family);
    border: 1px solid var(--plot-peak);
    color: var(--plot-peak);
  }

  .line[aria-pressed="false"] {
    border: 1px dashed var(--line-strong);
    color: var(--muted);
  }

  .refit {
    flex: none;
  }

  canvas {
    display: block;
    width: 100%;
    height: 240px;
    border-radius: 6px;
    background: var(--panel);
  }

  /* the window the step's list has chosen: the accent marks a selection */
  figure.on canvas {
    outline: 1px solid var(--accent);
  }
</style>
