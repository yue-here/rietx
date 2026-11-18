<script lang="ts">
  /**
   * The Peaks graph at `/next` (WP-2218, inventory rows 59-62): today's
   * Single peaks graph (`panels/PeakWindows.svelte`, WP-2128), moved here and
   * drawn to the prototype.
   *
   * The maintainer's rulings of 2026-11-07: the single-peak comparison plots
   * are liked (third review), and the comparison scale is fixed at the last
   * fit while a preview changes, "the logical expectation of someone trying to
   * compare something" (fourth review). So the windows and their y ranges come
   * from the last fit's curves alone (`lib/peakwin.ts`), and a preview that
   * grows a peak runs off the top of its window.
   *
   * The prototype's screen, restated in WP-2218 § Context: a title line saying
   * what the graph shows, with "Show" and its two choices; up to three windows
   * in a grid of 240 px columns, each titled ‹, the 2θ in mono, the hkl and
   * phase muted, ›. "Data and model" draws the crosses, the last fit and any
   * preview over a 44 px residual strip with its ±3 esd band. "Peak shape
   * alone" draws the model over its background, the last fit and the preview.
   * Under a preview the last fit is the grey `--plot-last`, solid (the
   * maintainer, 2026-11-18: "not dashed").
   *
   * The graph fetches the last fit's curves itself, keyed on the frame's
   * `plotKey`, because the Pattern graph is unmounted while this tab shows; it
   * hands each payload up, so the sliders' ranges follow a fit landed here.
   */
  import type { Curves } from "rxplot";

  import type { PreviewAnswer } from "../lib/interactive";
  import { formatHkl } from "../lib/peaks";
  import { firstPicks, netCurve, peakWindows, shapeRange, windowRange,
           type PeakWindow } from "../lib/peakwin";
  import { curveColors } from "../lib/plot";

  let {
    plotKey = 0,
    preview = null,
    previewError = "",
    rwp = null,
    theme = "light",
    oncurves = () => {},
  }: {
    /** bumped by the frame whenever the last fit's curves moved */
    plotKey?: number;
    preview?: PreviewAnswer | null;
    previewError?: string;
    /** the last fit's Rwp, a fraction */
    rwp?: number | null;
    theme?: string;
    oncurves?: (curves: Curves | null) => void;
  } = $props();

  type Show = "data" | "shape";
  const SHOWS: { id: Show; label: string; title: string }[] = [
    { id: "data", label: "Data and model", title: "Draw the data, the model and the difference" },
    { id: "shape", label: "Peak shape alone", title: "Draw the model over its background, without the data" },
  ];
  /** A view choice, session-local like the Pattern graph's knobs. */
  let show = $state<Show>("data");

  let curves = $state.raw<Curves | null>(null);
  let loadError = $state("");
  let loaded = $state(false);
  let seq = 0;

  async function load() {
    const mine = ++seq;
    try {
      const { fetchCurves } = await import("./pattern");
      const c = await fetchCurves();
      if (mine !== seq) return;
      curves = c;
      loadError = "";
      oncurves(c);
    } catch (exc) {
      if (mine !== seq) return;
      curves = null;
      // an empty project is the empty state below, not a failure
      loadError = (exc as { empty?: boolean }).empty ? "" : (exc as Error).message;
      oncurves(null);
    } finally {
      if (mine === seq) loaded = true;
    }
  }

  $effect(() => {
    void plotKey;
    void load();
  });

  const windows = $derived(curves ? peakWindows(curves) : []);
  // a new set of windows (a fit landed) starts again from the first picks; a
  // payload framing the same reflections keeps the windows the person stepped
  // to. Derived rather than reset in an effect, so a render never indexes a
  // shorter set with the last set's picks
  const windowsKey = $derived(windows.map((w) => w.center).join(","));
  let stepped = $state<{ key: string; picks: number[] } | null>(null);
  const picks = $derived(stepped?.key === windowsKey ? stepped.picks : firstPicks(windows.length));

  /** The last fit's model on the pattern's channels, its channels' 2θ, and
   *  the model over its background there. */
  const lastFit = $derived.by(() => {
    if (!curves) return null;
    const { two_theta: tt, fitted, y_calc: calc, y_background: bkg } = curves.arrays;
    const on: (number | null)[] = new Array(tt.length).fill(null);
    if (fitted && calc) for (let q = 0; q < fitted.length; q++) on[fitted[q]] = calc[q];
    return { on, tt: fitted ? Float64Array.from(fitted, (i) => tt[i]) : null,
             net: calc ? netCurve(calc, bkg) : null };
  });

  const previewing = $derived(!!preview && windows.length > 0);
  const pct = (x: number | null | undefined) => (x == null ? "" : `${(x * 100).toFixed(2)} %`);
  const titleTip = $derived(previewing ? "Preview, not refined"
    : previewError ? `Last fit. Preview refused: ${previewError}` : windows.length ? "Last fit" : "");

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
    void show;
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
    const band = style.getPropertyValue("--hover").trim() || "#eee";
    const { arrays } = curves, tt = arrays.two_theta, obs = arrays.y_obs;
    const calc = arrays.y_calc, delta = arrays.delta;
    const data = show === "data";
    const STRIP = data ? 44 : 0;
    const L = 8, R = 8, T = 8, B = 18 + STRIP;
    const ph = H - T - B, pw = W - L - R;
    const px = (x: number) => L + ((x - w.lo) / (w.hi - w.lo)) * pw;
    const fitTT = lastFit.tt;
    const pv = preview?.curves.arrays;
    // the y range is the last fit's alone, so a preview never rescales it
    const [y0, y1] = data
      ? windowRange(tt, obs, lastFit.on, w.lo, w.hi)
      : fitTT && lastFit.net ? shapeRange(fitTT, lastFit.net, w.lo, w.hi) : [0, 1];
    const py = (y: number) => T + ((y1 - y) / (y1 - y0)) * ph;
    ctx.save();
    ctx.beginPath();
    ctx.rect(L, T, pw, ph);
    ctx.clip();
    if (data) {
      // observed points: crosses, as every rietx pattern draws them
      ctx.strokeStyle = c.obs;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < tt.length; i++) {
        if (tt[i] < w.lo || tt[i] > w.hi) continue;
        const x = px(tt[i]), y = py(obs[i]), r = 2.6;
        ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r);
        ctx.moveTo(x - r, y + r); ctx.lineTo(x + r, y - r);
      }
      ctx.stroke();
    }
    const line = (xs: ArrayLike<number>, ys: ArrayLike<number>, ink: string, lw: number) => {
      ctx.strokeStyle = ink;
      ctx.lineWidth = lw;
      ctx.beginPath();
      let pen = false;
      for (let q = 0; q < xs.length; q++) {
        if (xs[q] < w.lo || xs[q] > w.hi) { pen = false; continue; }
        const x = px(xs[q]), y = py(ys[q]);
        if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y);
        pen = true;
      }
      ctx.stroke();
    };
    // under a preview the last fit turns grey, and stays solid (the
    // maintainer, 2026-11-18); the preview takes the model's ink
    const fitY = data ? calc : lastFit.net;
    if (fitTT && fitY) line(fitTT, fitY, pv ? c.last : c.calc, pv ? 1.2 : 1.3);
    if (pv) line(pv.two_theta, data ? pv.y_calc : netCurve(pv.y_calc, pv.y_background), c.calc, 1.5);
    ctx.restore();
    if (data) {
      // the residual strip: the preview's when there is one, else the last fit's
      const rx = pv ? pv.two_theta : fitTT, ry = pv ? pv.delta : delta;
      const top = T + ph + 6, h = STRIP - 12;
      // the strip's scale is the last fit's too, as the pattern graph's
      // residual pane keeps its y range under a preview (WP-2128 call 10); a
      // preview residual past it is clipped to the strip
      let m = 5;
      if (fitTT && delta)
        for (let q = 0; q < fitTT.length; q++)
          if (fitTT[q] >= w.lo && fitTT[q] <= w.hi && Number.isFinite(delta[q])) m = Math.max(m, Math.abs(delta[q]));
      const qy = (r: number) => top + h / 2 - (r / m) * (h / 2);
      // the ±3 esd band, in the pattern graph's band ink
      ctx.fillStyle = band;
      ctx.fillRect(L, qy(3), pw, qy(-3) - qy(3));
      if (rx && ry) {
        ctx.save();
        ctx.beginPath();
        ctx.rect(L, top, pw, h);
        ctx.clip();
        ctx.strokeStyle = c.diff;
        ctx.lineWidth = 0.9;
        ctx.beginPath();
        let pen = false;
        for (let q = 0; q < rx.length; q++) {
          if (rx[q] < w.lo || rx[q] > w.hi) { pen = false; continue; }
          const x = px(rx[q]), y = qy(ry[q]);
          if (pen) ctx.lineTo(x, y); else ctx.moveTo(x, y);
          pen = true;
        }
        ctx.stroke();
        ctx.restore();
      }
    }
    ctx.fillStyle = muted;
    ctx.font = `11px ${style.fontFamily}`;
    ctx.textAlign = "center";
    for (const f of [0.25, 0.75]) {
      const t = w.lo + f * (w.hi - w.lo);
      ctx.fillText(`${t.toFixed(2)}°`, px(t), H - 5);
    }
  }
</script>

<div class="peaksgraph">
  <div class="ghead">
    <!-- the whole line as its tooltip, since the title is what gives way (B1) -->
    <div class="gtitle" title={titleTip}>
      {#if previewing}
        <b class="pv">Preview, not refined</b>
        <span class="stat">Rwp <span class="num">{pct(preview?.curves?.header?.rwp)}</span>{#if rwp != null},
          last fit <span class="num">{pct(rwp)}</span>{/if}</span>
      {:else if windows.length}
        <b>Last fit</b>
        {#if previewError}<span class="bad">Preview refused</span>{/if}
        {#if rwp != null}<span class="stat">Rwp <span class="num">{pct(rwp)}</span></span>{/if}
      {/if}
    </div>
    <div class="gctl">
      <span class="vg">Show
        <span class="segmented" role="group" aria-label="Show">
          {#each SHOWS as s (s.id)}
            <button class:on={show === s.id} aria-pressed={show === s.id} title={s.title}
              disabled={!windows.length} onclick={() => (show = s.id)}>{s.label}</button>
          {/each}
        </span>
      </span>
    </div>
  </div>

  <div class="wins" bind:clientWidth={width}>
    {#if loadError}
      <p class="empty bad">{loadError}</p>
    {:else if loaded && !windows.length}
      <p class="empty">No fitted peaks to frame yet.</p>
    {:else}
      {#each picks as k, slot (slot)}
        {@const w = windows[k]}
        <figure>
          <figcaption>
            <button class="ib step" aria-label="Previous peak" title="Frame the next peak down in 2θ"
              disabled={k <= 0} onclick={() => step(slot, -1)}>‹</button>
            <span class="num">{w.center.toFixed(2)}°</span>
            <span class="sub">{w.hkl ? formatHkl(w.hkl) : ""} {w.phase}</span>
            <button class="ib step" aria-label="Next peak" title="Frame the next peak up in 2θ"
              disabled={k >= windows.length - 1} onclick={() => step(slot, 1)}>›</button>
          </figcaption>
          <canvas bind:this={canvases[slot]}
            aria-label={`Peak window at ${w.center.toFixed(2)} degrees`}></canvas>
        </figure>
      {/each}
    {/if}
  </div>
</div>

<style>
  .peaksgraph {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .vg {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
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

  .empty.bad {
    color: var(--bad);
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

  /* ‹ and › stay where they are while the hkl and phase give way */
  .step {
    flex: none;
    min-width: 24px;
    height: 24px;
  }

  /* each window is a card on the window's ground, as the pattern's plot is */
  canvas {
    display: block;
    width: 100%;
    height: 240px;
    border-radius: 6px;
    background: var(--panel);
  }
</style>
