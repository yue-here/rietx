<script lang="ts">
  /**
   * The Background graph at `/next` (WP-2218, inventory rows 63-68): today's
   * Background tab (`panels/Background.svelte`, WP-2129), moved here and drawn
   * to the prototype.
   *
   * The band is the server's (`GET /api/background`, `gui/background.py`): the
   * curve's esd at each channel through the whole covariance, so this graph
   * computes no statistic. It draws the band at `BAND_LEVEL` esd times the
   * multiplier chosen on the title line ("Band drawn"), and says both apart in
   * that control's tooltip.
   *
   * The prototype's screen, restated in WP-2218 § Context: the title line
   * holds what the graph shows, Type and "Band drawn"; the data are greyed
   * min-max bars with the band and the curve over them; a 72 px block under
   * the plot holds Terms and "Hold at last fit" for a Chebyshev, or Stiffness
   * for a P-spline.
   *
   * Two kinds of edit, two paths, as on the rest of the page:
   *
   * - **A hold is a pending edit.** A chip is `Refinement.hold`, a parameter
   *   flag, so it joins the Parameters panel's pending set through `onhold`
   *   (one set: the action bar counts it once, Apply sends it once, the
   *   recovery copy carries it). The band is fetched with every pending
   *   hold, globs and other parameters' included (`?hold=`), so it shows
   *   where the curve may move once they apply, and the title says
   *   "Background preview" while the band drawn is one fetched with holds:
   *   the answer's own `pending_holds`, never the request's, so a refused
   *   or late fetch cannot put the word over a band drawn without them.
   * - **Type, Terms and Stiffness change the model's shape**, so each is one
   *   instrument edit committed at once, as a structural edit is
   *   (gui/CLAUDE.md: a background family goes as a whole validated model).
   *   The hold and free registers keep their paths across it, so the server
   *   releases the holds the edit removes or redefines and frees the terms it
   *   adds (`GuiSession.instrument_patch`, WP-2229), and the Parameters panel
   *   drops its pending edits on the paths the answer says it `ended`
   *   (`ondropped`). The head moves and the band refetches.
   *
   * Nothing a click here changes may move the layout (interaction rule 8):
   * the controls keep their rows, and a refusal is the title's state.
   */
  import { ApiError, api } from "../api";
  import {
    BAND_MULTIPLIERS,
    bandTitle,
    coefficientTerms,
    columnExtremes,
    frame,
    halfWidth,
    holdable,
    holdsApply,
    niceTicks,
    termIndex,
    withLambda,
    type BackgroundHeader,
    type Multiplier,
  } from "../lib/background";
  import { registerEcho } from "../lib/model";
  import { curveColors } from "../lib/plot";
  import { LAMBDA_STOPS, TERMS_MAX, TERMS_MIN, heldWith, kindEcho, lambdaStop,
           pendingHolds, switchKind, termsEcho, withTerms } from "./background";

  let {
    head = null,
    busy = false,
    theme = "light",
    protocol = "",
    holds = new Map(),
    say = (_line: string) => {},
    onhold = (_path: string, _held: boolean, _serverHeld: boolean) => {},
    ondropped = (_gone: (path: string) => boolean) => {},
    onmoved = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    theme?: string;
    /** the document's mode, fit range and excluded regions: settings that
     *  change the answer's channels and free set without moving the head */
    protocol?: string;
    /** the Parameters panel's pending holds and releases, path → held */
    holds?: ReadonlyMap<string, boolean>;
    say?: (line: string) => void;
    /** a chip pressed: hold or release one term, pending until Apply */
    onhold?: (path: string, held: boolean, serverHeld: boolean) => void;
    /** an instrument edit removed or redefined these paths: the pending
     *  values, flags, holds and limits on them can no longer apply */
    ondropped?: (gone: (path: string) => boolean) => void;
    /** an instrument edit landed: the head moved under the shell */
    onmoved?: () => void;
  } = $props();

  type Answer = { header: BackgroundHeader; arrays: Record<string, Float64Array> };
  let answer = $state.raw<Answer | null>(null);
  // a verb's refusal and the load's failure are two fields (gui/CLAUDE.md,
  // WP-1014): a reload must not wipe the sentence a press just earned
  let error = $state("");
  let loadError = $state("");
  let loadedKey = "";
  let multiplier = $state<Multiplier>(1);
  let pending = $state(false);
  let seq = 0;

  /** Every pending hold: the band is fetched with them. */
  const sentHolds = $derived(pendingHolds(holds));
  const header = $derived(answer?.header ?? null);
  const esd = $derived(answer?.arrays.band_esd ?? null);
  const terms = $derived(header ? coefficientTerms(header.terms) : []);
  const kind = $derived(header?.kind ?? "");
  /** the holds the band on screen was drawn with, from its answer */
  const drawnHolds = $derived(header?.pending_holds ?? []);
  const previewing = $derived(drawnHolds.length > 0);

  async function load(key: string, hold: string[]) {
    const mine = ++seq;
    try {
      const { unpack } = await import("./rxplot.mjs");
      const next = unpack(await api.background(hold)) as unknown as Answer;
      if (mine !== seq) return;
      answer = next;
      loadedKey = key;
      loadError = "";
    } catch (exc) {
      if (mine === seq) loadError = exc instanceof ApiError ? exc.message : String(exc);
    }
  }

  // the head is the reload signal, the protocol beside it (a mode, range or
  // region change moves the channels and the free set but not the head), and
  // the pending holds the band is drawn for. A run in flight answers 409, so
  // wait for idle.
  $effect(() => {
    if (busy || !head) return;
    const hold = sentHolds;
    const key = JSON.stringify([head, protocol, hold]);
    if (key === loadedKey) return;
    void load(key, hold);
  });

  /** Is this term held, counting a pending hold or release, a glob's too? */
  function isHeld(path: string, serverHeld: boolean): boolean {
    return heldWith(path, serverHeld, holds);
  }

  /** Type, Terms and Stiffness: one instrument edit, committed at once. The
   *  server answers what it asked of the registers. Once it lands, the
   *  pending edits on the paths it ended are dropped, or the band and Apply
   *  would both be refused on a path the table no longer has, or land on the
   *  new model's path of the same name. */
  async function editInstrument(build: (instrument: any) => any, label: string, echo: string) {
    if (pending) return;
    pending = true;
    try {
      const { instrument } = await api.instrument();
      const answer = await api.patchInstrument(build(instrument), label);
      for (const line of registerEcho(answer, echo)) say(line);
      error = "";
      const ended = new Set(answer.ended ?? []);
      ondropped((path) => ended.has(path));
      onmoved();
    } catch (exc) {
      error = (exc as Error).message;
    } finally {
      pending = false;
    }
  }

  function chooseKind(next: "chebyshev" | "pspline") {
    if (!answer || next === kind) return;
    const tt = answer.arrays.two_theta;
    const lo = tt[0], hi = tt[tt.length - 1];
    void editInstrument((ins) => switchKind(ins, next, lo, hi), `background: ${next}`,
      kindEcho(next, lo, hi));
  }

  /** The Terms slider's value while it is dragged; committed on release. */
  let termsDrag = $state<number | null>(null);
  const termCount = $derived(termsDrag ?? terms.length);

  function commitTerms(n: number) {
    termsDrag = null;
    if (n === terms.length) return;
    void editInstrument((ins) => withTerms(ins, n), `background: ${n} terms`,
      termsEcho(terms.length, n));
  }

  let stopDrag = $state<number | null>(null);
  const lambda = $derived(header?.lambda_smooth ?? 1);
  const stop = $derived(stopDrag ?? lambdaStop(lambda));
  const lambdaShown = $derived(stopDrag !== null ? LAMBDA_STOPS[stopDrag] : lambda);
  const intensityUnits = $derived(header?.lambda_units === "intensity");

  function commitStop(k: number) {
    stopDrag = null;
    const next = LAMBDA_STOPS[k];
    if (next === lambda) return;
    void editInstrument((ins) => withLambda(ins, next), `background λ = ${next}`,
      `instrument.background.lambda_smooth = ${next}`);
  }

  const titleTip = $derived(
    (previewing ? `Background preview: the band once ${drawnHolds.length} pending hold`
      + `${drawnHolds.length === 1 ? "" : "s"} apply` : "Background at the current values")
    + (error ? `. Edit refused: ${error}` : "")
    + (loadError ? `. Band refused: ${loadError}` : ""));

  let canvas = $state<HTMLCanvasElement | null>(null);
  let width = $state(0);
  let height = $state(0);

  $effect(() => {
    void theme;
    void width;
    void height;
    void multiplier;
    const a = answer;
    if (!a || !canvas) return;
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
    const tt = a.arrays.two_theta, obs = a.arrays.y_obs, bg = a.arrays.y_background;
    if (!tt.length) return;
    const L = 52, R = 10, T = 8, B = 22;
    const pw = W - L - R, ph = H - T - B;
    const x0 = tt[0], x1 = tt[tt.length - 1];
    const [lo, hi] = frame(bg);
    const px = (x: number) => L + ((x - x0) / (x1 - x0)) * pw;
    const py = (y: number) => T + ((hi - y) / (hi - lo)) * ph;

    // tick labels and no gridlines (`gui/STYLE.md` § Plots)
    ctx.font = `11px ${style.fontFamily}`;
    ctx.fillStyle = muted;
    ctx.textAlign = "right";
    for (const v of niceTicks(lo, hi, Math.max(2, Math.floor(ph / 48)))) {
      ctx.fillText(String(v), L - 6, Math.round(py(v)) + 4);
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
    ctx.lineWidth = 1;
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
      ctx.globalAlpha = 0.3;
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

<div class="bggraph">
  <div class="ghead">
    <!-- the whole line as its tooltip, since the title is what gives way (B1) -->
    <div class="gtitle" title={titleTip}>
      {#if previewing}<b class="pv">Background preview</b>{:else}<b>Background at the current values</b>{/if}
      {#if loadError}<span class="bad">Band refused</span>
      {:else if error}<span class="bad">Edit refused</span>
      {:else if busy}<span>waiting for the run</span>{/if}
    </div>
    <div class="gctl">
      {#if kind === "chebyshev" || kind === "pspline"}
        <span class="vg">Type
          <span class="segmented" role="group" aria-label="Type">
            <button class:on={kind === "chebyshev"} aria-pressed={kind === "chebyshev"}
              disabled={busy || pending} title="A Chebyshev polynomial, its terms refined"
              onclick={() => chooseKind("chebyshev")}>Chebyshev</button>
            <button class:on={kind === "pspline"} aria-pressed={kind === "pspline"}
              disabled={busy || pending} title="A smooth spline co-refined under a stiffness penalty"
              onclick={() => chooseKind("pspline")}>P-spline</button>
          </span>
        </span>
      {/if}
      <span class="vg" title={header ? bandTitle(header, esd) : null}>Band drawn
        <span class="segmented" role="group" aria-label="Band drawn">
          {#each BAND_MULTIPLIERS as m (m)}
            <button class:on={multiplier === m} aria-pressed={multiplier === m} disabled={!esd}
              onclick={() => (multiplier = m)}>×{m}</button>
          {/each}
        </span>
      </span>
    </div>
  </div>

  <div class="view">
    <div class="plot" bind:clientWidth={width} bind:clientHeight={height}>
      <canvas bind:this={canvas} aria-label="The background curve and its band over the observed pattern"></canvas>
    </div>
    <!-- one block of fixed height, whichever type is drawn, so a type
         choice moves nothing under it (principle 4) -->
    <div class="bgctls">
      {#if kind === "chebyshev"}
        <div class="bgctl">
          <span class="lab">Terms</span>
          <input type="range" min={TERMS_MIN} max={TERMS_MAX} step="1" aria-label="Terms"
            value={termCount} disabled={busy || pending}
            oninput={(e) => (termsDrag = Number((e.currentTarget as HTMLInputElement).value))}
            onchange={(e) => commitTerms(Number((e.currentTarget as HTMLInputElement).value))} />
          <span class="num">{String(termCount).padStart(2, " ")}</span>
        </div>
      {/if}
      {#if holdsApply(kind)}
        <div class="bgctl">
          <span class="lab">Hold at last fit</span>
          <span class="chips" role="group" aria-label="Hold at last fit">
            {#each terms as term (term.path)}
              {@const k = termIndex(term.path)}
              {@const on = isHeld(term.path, term.held)}
              <button class="term" aria-pressed={on} aria-label={`Hold term ${k}`}
                disabled={!holdable(term) || busy || pending}
                title={holdable(term) ? `${on ? "Release" : "Hold"} term ${k}` : term.held_because}
                onclick={() => onhold(term.path, !on, term.held)}>{k}</button>
            {/each}
          </span>
        </div>
      {:else if kind === "pspline"}
        <div class="bgctl">
          <span class="lab">Stiffness</span>
          <!-- the stops are dimensionless: on a λ kept in intensity units
               (`BackgroundPSpline.lambda_units`) one would move the
               stiffness by orders of magnitude, so the slider is shown, not offered -->
          <input type="range" min="0" max={LAMBDA_STOPS.length - 1} step="1" aria-label="Stiffness"
            value={stop} disabled={busy || pending || intensityUnits}
            title={intensityUnits ? "λ is in intensity units here, and the stops are dimensionless" : undefined}
            oninput={(e) => (stopDrag = Number((e.currentTarget as HTMLInputElement).value))}
            onchange={(e) => commitStop(Number((e.currentTarget as HTMLInputElement).value))} />
          <span class="num">λ {lambdaShown}{#if intensityUnits} intensity⁻²{/if}</span>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .bggraph {
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
  }

  .bgctls {
    flex: none;
    height: 72px;
    margin-top: 8px;
  }

  .bgctl {
    display: flex;
    align-items: center;
    gap: 6px 14px;
    min-height: 32px;
    font-size: var(--text-sm);
    color: var(--muted);
  }

  .lab {
    flex: none;
    width: 8.5em;
  }

  .bgctl input[type="range"] {
    flex: 1 1 auto;
    min-width: 110px;
    max-width: 420px;
    accent-color: var(--accent);
  }

  .num {
    font-family: var(--mono-family);
    color: var(--fg);
    white-space: pre;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 3px;
  }

  /* a term's hold: a toggle, pressed while held, as the prototype draws it */
  .chips .term {
    min-width: 24px;
    height: 24px;
    padding: 0 4px;
    border: 1px solid var(--line-strong);
    border-radius: 5px;
    background: none;
    font-family: var(--mono-family);
    font-size: var(--text-sm);
    font-weight: 400;
    color: var(--muted);
  }

  .chips .term[aria-pressed="true"] {
    border-color: var(--fg);
    background: var(--hover);
    color: var(--fg);
  }

  .chips .term:disabled {
    opacity: 0.45;
  }
</style>
