<script lang="ts">
  /**
   * The Background graph (WP-2129): the observed pattern greyed, the
   * background curve at the working state's values, and a band where that
   * curve may move when the free parameters refine.
   *
   * The band is the server's (`GET /api/background`, `gui/background.py`): the
   * curve's esd at each channel through the whole covariance, so this panel
   * computes no statistic. It draws the band at `BAND_LEVEL` esd times the
   * multiplier the person picks, and says both apart in the control's tooltip.
   *
   * A Chebyshev background offers a hold on each term, which is
   * `Refinement.hold` through `PATCH /api/params`: the term keeps its value
   * from the previous cycle and no plan frees it (the maintainer's ruling of
   * 2026-11-07). A P-spline offers its smoothness λ, an instrument edit. Both
   * move the head, and the head is the refetch signal, as every panel's is.
   *
   * Drawn on a 2D canvas, as the Single peaks graph is. Nothing that a click
   * here changes may move the layout (interaction rule 8): the controls keep
   * their row, and a refusal is drawn over the plot rather than as a line.
   */
  import Help from "../Help.svelte";
  import { ApiError, api } from "../api";
  import {
    BAND_MULTIPLIERS,
    bandTitle,
    coefficientTerms,
    columnExtremes,
    frame,
    halfWidth,
    holdDelta,
    holdEcho,
    holdable,
    holdsApply,
    niceTicks,
    parseLambda,
    termIndex,
    withLambda,
    type BackgroundHeader,
    type Multiplier,
  } from "../lib/background";
  import { curveColors } from "../lib/plot";

  let {
    head = null,
    busy = false,
    theme = "light",
    active = false,
    protocol = "",
    say = (_line: string) => {},
    onmoved = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    theme?: string;
    /** the tab is showing: a hidden canvas has no size, and a hidden tab
     *  fetches nothing */
    active?: boolean;
    /** the document's mode, fit range and excluded regions: settings that
     *  change the answer's channels and free set without moving the head */
    protocol?: string;
    say?: (line: string) => void;
    onmoved?: () => void;
  } = $props();

  type Answer = { header: BackgroundHeader; arrays: Record<string, Float64Array> };
  let answer = $state.raw<Answer | null>(null);
  // a verb's refusal and the load's failure are two fields (gui/CLAUDE.md,
  // WP-1014): a reload must not wipe the sentence a press just earned
  let error = $state("");
  let loadError = $state("");
  /** the head and protocol the shown answer was fetched for */
  let loadedKey = "";
  let multiplier = $state<Multiplier>(1);
  let pending = $state(false);
  let lambdaText = $state("");
  let seq = 0;

  const HOLD_MEANS = "A held term keeps its value from the previous cycle, and no "
    + "plan frees it. The band then shows where the curve may move with the other "
    + "terms refining.";

  const header = $derived(answer?.header ?? null);
  const esd = $derived(answer?.arrays.band_esd ?? null);
  const terms = $derived(header ? coefficientTerms(header.terms) : []);

  async function load(key: string) {
    const mine = ++seq;
    try {
      const { unpack } = await import("rxplot");
      const next = unpack(await api.background()) as unknown as Answer;
      if (mine !== seq) return;
      answer = next;
      loadedKey = key;
      loadError = "";
      if (next.header.kind === "pspline") lambdaText = String(next.header.lambda_smooth);
    } catch (exc) {
      if (mine === seq) loadError = exc instanceof ApiError ? exc.message : String(exc);
    }
  }

  // the head is the reload signal, and the protocol beside it: a mode, range or
  // region change moves the channels and the free set but not the head. A run
  // in flight answers 409, so wait for idle.
  $effect(() => {
    if (!active || busy || !head) return;
    const key = JSON.stringify([head, protocol]);
    if (key === loadedKey) return;
    void load(key);
  });

  async function hold(path: string, held: boolean, box: HTMLInputElement) {
    pending = true;
    try {
      await api.patchParams(holdDelta(path, held));
      say(holdEcho(path, held));
      error = "";
      onmoved();
    } catch (exc) {
      error = (exc as Error).message;
      // refused: nothing moved, so no reload will put the box back
      box.checked = !held;
    } finally {
      pending = false;
    }
  }

  async function commitLambda() {
    // Enter commits and the blur that follows must not commit it again
    if (pending || !header || header.kind !== "pspline") return;
    const parsed = parseLambda(lambdaText);
    if (typeof parsed === "string") {
      error = parsed;
      return;
    }
    if (parsed === header.lambda_smooth) return;
    pending = true;
    try {
      const { instrument } = await api.instrument();
      await api.patchInstrument(withLambda(instrument, parsed), `background λ = ${parsed}`);
      say(`instrument.background.lambda_smooth = ${parsed}`);
      error = "";
      onmoved();
    } catch (exc) {
      error = (exc as Error).message;
      lambdaText = String(header.lambda_smooth);
    } finally {
      pending = false;
    }
  }

  let canvas = $state<HTMLCanvasElement | null>(null);
  let width = $state(0);
  let height = $state(0);

  $effect(() => {
    void theme;
    void width;
    void height;
    void multiplier;
    const a = answer;
    if (!active || !a || !canvas) return;
    const cv = canvas;
    // one microtask: the shell stamps the theme in an effect of the same flush
    void Promise.resolve().then(() => draw(cv, a));
  });

  function draw(cv: HTMLCanvasElement, a: Answer) {
    const ctx = cv.getContext?.("2d");
    if (!ctx) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = devicePixelRatio || 1;
    if (!W || !H) return;
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const style = getComputedStyle(document.body);
    const ink = curveColors((n) => style.getPropertyValue(n));
    const muted = style.getPropertyValue("--muted").trim() || "#888";
    const line = style.getPropertyValue("--line").trim() || "#ddd";
    const tt = a.arrays.two_theta, obs = a.arrays.y_obs, bg = a.arrays.y_background;
    if (!tt.length) return;
    const L = 52, R = 8, T = 8, B = 22;
    const pw = W - L - R, ph = H - T - B;
    const x0 = tt[0], x1 = tt[tt.length - 1];
    const [lo, hi] = frame(bg);
    const px = (x: number) => L + ((x - x0) / (x1 - x0)) * pw;
    const py = (y: number) => T + ((hi - y) / (hi - lo)) * ph;

    ctx.font = `11px ${style.fontFamily}`;
    ctx.fillStyle = muted;
    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    ctx.textAlign = "right";
    for (const v of niceTicks(lo, hi, Math.max(2, Math.floor(ph / 48)))) {
      const q = Math.round(py(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(L, q);
      ctx.lineTo(W - R, q);
      ctx.stroke();
      ctx.fillText(String(v), L - 6, q + 4);
    }
    ctx.textAlign = "center";
    for (const v of niceTicks(x0, x1, Math.max(2, Math.floor(pw / 80)))) {
      ctx.fillText(`${v}°`, px(v), H - 6);
    }

    ctx.save();
    ctx.beginPath();
    ctx.rect(L, T, pw, ph);
    ctx.clip();
    // the data greyed: each pixel column's extremes, faded under the curve
    const cols = columnExtremes(tt, obs, x0, x1, pw);
    ctx.strokeStyle = ink.obs;
    ctx.globalAlpha = 0.45;
    ctx.beginPath();
    for (let c = 0; c < cols.lo.length; c++) {
      if (Number.isNaN(cols.lo[c])) continue;
      const x = L + c + 0.5;
      ctx.moveTo(x, py(cols.lo[c]) + 0.5);
      ctx.lineTo(x, py(cols.hi[c]) - 0.5);
    }
    ctx.stroke();
    // the band, then the curve over it
    if (a.arrays.band_esd) {
      const half = halfWidth(a.arrays.band_esd, multiplier);
      ctx.fillStyle = ink.bkg;
      ctx.globalAlpha = 0.28;
      ctx.beginPath();
      for (let i = 0; i < tt.length; i++) {
        const x = px(tt[i]), y = py(bg[i] + half[i]);
        if (i) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      }
      for (let i = tt.length - 1; i >= 0; i--) ctx.lineTo(px(tt[i]), py(bg[i] - half[i]));
      ctx.closePath();
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = ink.bkg;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < tt.length; i++) {
      const x = px(tt[i]), y = py(bg[i]);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }
</script>

<section aria-label="background">
  <div class="host" bind:clientWidth={width} bind:clientHeight={height}>
    <canvas bind:this={canvas}></canvas>
    {#if error || loadError}
      <!-- over the plot, never a line of its own: a refusal must not move the
           controls a click just pressed (interaction rule 8) -->
      <p class="refusal" role="alert">{error || loadError}</p>
    {:else if !answer}
      <p class="refusal muted">{busy ? "Waiting for the run to finish" : ""}</p>
    {/if}
  </div>
  <div class="knobs">
    {#if header && holdsApply(header.kind)}
      <div class="terms" role="group" aria-label="hold terms">
        <span class="muted"><Help text={HOLD_MEANS} title="Hold">Hold</Help></span>
        {#each terms as term (term.path)}
          <!-- the title is the value, which the row does not show; why a term
               cannot be held is the server's sentence, so it is a Help term -->
          <label class="term mono" title={`${term.path} = ${term.value.toPrecision(6)}`}>
            <input type="checkbox" checked={term.held}
              disabled={!holdable(term) || busy || pending}
              onchange={(e) => {
                const box = e.currentTarget as HTMLInputElement;
                void hold(term.path, box.checked, box);
              }} />
            {#if holdable(term)}c{termIndex(term.path)}{:else}<Help
              text={term.held_because ?? ""} title={term.path}
              >c{termIndex(term.path)}</Help>{/if}
          </label>
        {/each}
      </div>
    {:else if header?.kind === "pspline"}
      <label class="lambda">
        <span class="muted">Smoothness λ</span>
        <input class="mono" type="text" inputmode="decimal" bind:value={lambdaText}
          disabled={busy || pending} size="9"
          onkeydown={(e) => { if (e.key === "Enter") void commitLambda(); }}
          onblur={() => void commitLambda()} />
        {#if header.lambda_units === "intensity"}<span class="muted">intensity⁻²</span>{/if}
      </label>
    {/if}
    <div class="band">
      <span class="muted"><Help text={header ? bandTitle(header, esd) : ""}
        title="The band">Band ±3 esd</Help></span>
      <div class="segmented" role="group" aria-label="band drawn">
        {#each BAND_MULTIPLIERS as m (m)}
          <button class:on={multiplier === m} disabled={!esd}
            onclick={() => (multiplier = m)}>×{m}</button>
        {/each}
      </div>
    </div>
  </div>
</section>

<style>
  section {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    padding: 8px 10px;
    gap: 6px;
  }

  .host {
    position: relative;
    flex: 1 1 0;
    min-height: 240px;
    overflow: hidden;
  }

  canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .refusal {
    position: absolute;
    top: 8px;
    left: 60px;
    right: 12px;
    margin: 0;
    color: var(--bad);
    pointer-events: none;
  }

  .refusal.muted {
    color: var(--muted);
  }

  .knobs {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .terms,
  .band,
  .lambda {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .term {
    display: inline-flex;
    align-items: center;
    gap: 3px;
  }
</style>
