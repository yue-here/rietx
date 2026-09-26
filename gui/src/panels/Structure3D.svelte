<script lang="ts">
  /**
   * The structure, rotatable, drawn by the viewer's own WebGL2 renderer
   * (WP-1015, WP-1462).
   *
   * Everything hard is server-side: the symmetry orbit with each image's
   * *rotated* displacement tensor, the bonds, the cell frame.  This component
   * fetches Cartesian numbers, turns them into a scene (`lib/structure3d.ts`)
   * and hands that to `lib/gl3d.ts`, which ray-casts every atom and bond as
   * the exact quadric it is.  No library draws it: plotly cost 4.8 MB for a
   * few hundred ellipsoids, and three.js would have cost 139 KB for the same
   * (WP-1462 § The field, measured).
   *
   * **The ellipsoids are the reason this exists**, and they are a diagnostic
   * rather than decoration: their axes are refined quantities, so an
   * over-flexible background — which improves Rwp while inflating ADPs
   * (CLAUDE.md's block projection R²) — arrives here as balloons, and a tensor
   * that is not positive definite arrives as a flat disc with the reason in its
   * readout. Neither is visible in the parameter table, where the same six
   * numbers look like six ordinary rows.
   *
   * Two knobs, and both are *drawing* thresholds rather than facts about the
   * sample, which is why neither is persisted: the probability level rescales
   * client-side from the table the payload carries (no refetch), and the bond
   * tolerance is a server round trip because the server owns the bond rule.
   *
   * **The view is owned here, outright.**  plotly rebuilt its scene from the
   * layout on every redraw, so the view had to be read back from a private
   * object first; a `View` this component holds survives every redraw by
   * construction, and a test says so.
   */
  import { untrack } from "svelte";

  import { ApiError, api } from "../api";
  import { createRenderer, EXPORT_LONG_SIDE, type Renderer } from "../lib/gl3d";
  import {
    atomLabel,
    axisView,
    bondLabel,
    buildScene,
    caption,
    legend,
    openingView,
    pickAtom,
    pickFace,
    pickHalf,
    pixelsPerAngstrom,
    polyhedraLegend,
    polyhedronLabel,
    project,
    rgb,
    rotateBy,
    shownPolyhedra,
    type Geometry,
    type Mode,
    type Scene,
    type View,
  } from "../lib/structure3d";

  import type { Theme } from "../lib/theme";

  let {
    stamp = 0,
    theme = "light",
    say = (_line: string) => {},
  }: {
    /** bumped by the model pane every time it re-reads — see the effect below */
    stamp?: number;
    /** the resolved theme, and a dependency of the scene effect: the cell
     *  frame samples `--accent` and the canvas the panel's background, so a
     *  theme change that does not redraw leaves the old theme on the canvas
     *  (WP-1029 q) */
    theme?: Theme;
    say?: (line: string) => void;
  } = $props();

  let canvas: HTMLCanvasElement | undefined = $state();
  let labelNodes: HTMLSpanElement[] = $state([]);
  let renderer: Renderer | null = null;
  /** jsdom and old browsers: no WebGL2, so say so rather than show a blank box */
  let unsupported = $state(false);
  /** What is drawn and where from.  Neither is `$state`: nothing renders them,
   *  and making them reactive would re-render the panel on every frame of a
   *  drag. */
  let scene: Scene | null = null;
  const EMPTY: Scene = { atoms: [], halves: [], lines: [], faces: [], labels: [],
                         center: [0, 0, 0], radius: 1, depth: 1 };
  let view: View = openingView();
  let frame = 0;
  /** raw: the payload is replaced, never edited, and a deep proxy would sit
   *  under every read `buildScene` and the hover make */
  let geo = $state.raw<Geometry | null>(null);
  let error = $state("");
  /** Has a first load *settled*? — see `load`. */
  let ready = $state(false);
  let seq = 0;
  let mode = $state<Mode>("ball");
  let phase = $state(0);
  let tolerance = $state(1.15);
  /** The chosen ellipsoid level, held here rather than read off the payload:
   *  every reload brings the server's default back, so a level picked once was
   *  silently reset by the next cell edit (found in a browser). */
  let level = $state("0.5");
  let hidden = $state(new Set<string>());
  let showBoundary = $state(true);
  /** The bond threshold the *label* shows, which follows the drag; `tolerance`
   *  is what the fetch uses and only moves on release.  Two facts, two fields —
   *  the bug was precisely that the cheap one was tied to the expensive one. */
  let toleranceShown = $state(1.15);
  /**
   * How much bigger than k(p) the ellipsoids are drawn.
   *
   * **Not a probability, and never labelled as one.**  k(p) = √χ²₃(p) diverges
   * as p → 1 and `probability_scale(1.0)` raises, so there is no "120 %
   * ellipsoid" to ask for: wanting them bigger is a drawing scale, and the
   * caption states it beside the probability rather than folded into it.
   */
  let exaggeration = $state(1);
  /** The drawing knobs, folded away.  Every one of them was on screen at once
   *  under a 300 px plot in a 380 px column; mode and the view buttons stay in
   *  the open because they are the two anyone reaches for. */
  let knobsOpen = $state(false);
  /** Coordination polyhedra on or off, held per mode (WP-1466, P8): on in
   *  ball mode and off in ellipsoid mode, where faces would cover the ADPs
   *  that mode exists to show.  One switch changes the mode it is pressed in. */
  let polyhedraIn = $state<Record<Mode, boolean>>({ ball: true, ellipsoid: false });
  /** The legend's switch per centre species (P5).  A species this does not
   *  name takes the server's default, which draws shells of four to six. */
  let polyFormulas = $state(new Map<string, boolean>());
  /** Export the PNG on a transparent background rather than the panel's. */
  let transparent = $state(false);
  /** What is under the pointer: the readout strip's one line (WP-1213's rule —
   *  a box over the picture covers the thing it describes). */
  let reading = $state("");
  /** Why the last PNG failed.  Its own field, not `error`: that one replaces
   *  the controls, the PNG button among them, until the next load. */
  let exportError = $state("");

  const entries = $derived(geo ? legend(geo) : []);
  const levels = $derived(geo ? Object.keys(geo.probability_levels) : []);
  const shown = $derived(geo ? shownPolyhedra(geo, polyhedraIn[mode], polyFormulas,
                                               hidden, showBoundary) : []);
  const polyEntries = $derived(geo ? polyhedraLegend(geo) : []);

  /** Refetch whenever the model pane re-reads, and whenever a knob the *server*
   *  owns moves.
   *
   *  `stamp` rather than `head` directly, and the difference is not cosmetic: a
   *  head move reaches the shell one SSE frame later, while the pane around this
   *  one re-reads the moment its own Apply returns — so following the head would
   *  leave the picture a frame behind the atom table it sits beside.  The pane's
   *  reload is itself driven by the head (WP-1005: the head *is* the working
   *  state), so this is one signal, not two. */
  $effect(() => {
    void stamp;
    void phase;
    void tolerance;
    load();
  });

  /** One renderer for the canvas's life, given back when the panel closes:
   *  browsers keep about sixteen WebGL contexts a page and drop the oldest
   *  without a word.
   *
   *  The canvas is this effect's only dependency, and that is load-bearing:
   *  `rebuild` reads the geometry, so called bare it would make every new
   *  payload re-run this effect, whose cleanup *loses* the context — and a
   *  canvas keeps the context it first gave, dead, so the next renderer drew
   *  Chrome's sad face (found in a browser; jsdom's stand-in loses nothing). */
  $effect(() => {
    if (!canvas) return;
    renderer = createRenderer(canvas);
    unsupported = renderer === null;
    const observer = typeof ResizeObserver === "undefined"
      ? null : new ResizeObserver(() => schedule());
    observer?.observe(canvas);
    untrack(() => rebuild());
    return () => {
      observer?.disconnect();
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      renderer?.dispose();
      renderer = null;
    };
  });

  /** Rebuild the scene whenever the geometry or a client-side knob moves.  An
   *  `$effect` over the state rather than a call at each site — WP-1013's rule,
   *  learned when a fifth call site was the one that forgot. */
  $effect(() => {
    void geo;
    void mode;
    void hidden;
    void showBoundary;
    void exaggeration;
    void theme;
    void shown;
    rebuild();
  });

  /**
   * Fetch, at the level this component holds.
   *
   * `seq` is WP-1013's rule one panel over: two quick releases of the bond
   * slider put two requests in flight and they can land out of order, which
   * would leave the picture disagreeing with the control that asked for it.
   * The older answer is dropped rather than merged, for the same reason.
   *
   * `ready` separates "not fetched yet" from "fetched, and there is nothing" —
   * one `geo === null` cannot say both.
   */
  async function load() {
    const mine = ++seq;
    try {
      const payload = await api.structure3d(phase, tolerance);
      if (mine !== seq) return;
      geo = at(payload, level);
      error = "";
    } catch (exc) {
      if (mine !== seq) return;
      if (exc instanceof ApiError && exc.empty) geo = null;
      else error = (exc as Error).message;
    } finally {
      if (mine === seq) ready = true;
    }
  }

  /** A payload rescaled to the chosen level — the one place the two meet.
   *
   * No refetch: the payload carries k(p) for every level it offers, so this is a
   * client multiply.  The level lives in this component and the geometry comes
   * from the server, and *this* is where they are combined, so a reload cannot
   * quietly hand the server's default back. */
  function at(payload: Geometry, key: string): Geometry {
    const scale = payload.probability_levels[key];
    return scale === undefined
      ? payload
      : { ...payload, probability: Number(key), scale };
  }

  /**
   * A new scene for the renderer, then a frame.
   *
   * One microtask first: a style sampled synchronously inside an effect races
   * the shell's `applyTheme` effect in the same flush, and the first dark
   * frame would wear light ink (`gui/CLAUDE.md`, Plot.svelte's rule).
   */
  async function rebuild() {
    const geometry = geo;
    await Promise.resolve();
    if (geometry !== geo) return;
    if (!geometry) {
      // nothing to draw is still a frame: an opaque canvas never drawn is
      // black, and one drawn before keeps the structure that is gone
      scene = EMPTY;
      renderer?.setScene(scene);
      paint();
      return;
    }
    const style = getComputedStyle(document.body);
    // the cell frame is the picture's frame, so it gets the accent rather than
    // `--line`: a hairline border colour is invisible against the page in a 3D
    // scene, and the first browser run drew a box nobody could see.  The a/b/c
    // letters take the same colour, so frame and labels read as one object.
    const cell = style.getPropertyValue("--accent").trim() || "#1f5fa8";
    scene = buildScene(geometry, { mode, hidden, showBoundary, exaggeration, cell,
                                   polyhedra: shown });
    renderer?.setScene(scene);
    paint();
  }

  /** One frame per animation frame, however many pointer events asked. */
  function schedule() {
    if (frame || typeof requestAnimationFrame === "undefined") {
      if (!frame) paint();
      return;
    }
    frame = requestAnimationFrame(() => {
      frame = 0;
      paint();
    });
  }

  function paint() {
    if (!renderer || !scene || !canvas) return;
    renderer.draw(view, background());
    placeLabels();
  }

  /**
   * The colour the canvas clears to: the panel's own.
   *
   * The canvas is opaque — alpha-to-coverage writes its edge coverage into the
   * samples, which is right only where alpha is thrown away (`lib/gl3d.ts`) —
   * so it paints the colour that would otherwise show through it.
   */
  function background(): number[] {
    let at: Element | null = canvas?.parentElement ?? null;
    while (at) {
      // only an opaque `rgb()` is the colour behind the canvas: a tint is
      // blended with what is under it, and `color(srgb …)` counts in 0..1
      const colour = getComputedStyle(at).backgroundColor;
      const parts = /^rgba?\(/.test(colour)
        ? colour.match(/[\d.]+/g)?.map(Number) ?? [] : [];
      if (parts.length >= 3 && (parts.length < 4 || parts[3] >= 1)) {
        return parts.slice(0, 3).map((v) => v / 255);
      }
      at = at.parentElement;
    }
    const token = getComputedStyle(document.body).getPropertyValue("--bg").trim();
    return rgb(token || "#fbfbfa");
  }

  /** The a, b, c letters as DOM over the canvas (D3): crisp, and in the
   *  theme's own type. */
  function placeLabels() {
    if (!scene || !canvas) return;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    scene.labels.forEach((label, k) => {
      const node = labelNodes[k];
      if (!node) return;
      const [x, y] = project(scene!, view, width, height, label.pos);
      node.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    });
  }

  // ---------------------------------------------------------------------
  // the pointer: a trackball, a pan and a zoom, and the readout
  // ---------------------------------------------------------------------

  let drag: { x: number; y: number; pan: boolean } | null = null;

  function onDown(event: PointerEvent) {
    drag = { x: event.clientX, y: event.clientY,
             pan: event.button === 2 || event.shiftKey };
    canvas?.setPointerCapture?.(event.pointerId);
    reading = "";
  }

  function onMove(event: PointerEvent) {
    if (!drag) {
      hover(event);
      return;
    }
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    drag.x = event.clientX;
    drag.y = event.clientY;
    if (drag.pan && scene && canvas) {
      const s = pixelsPerAngstrom(scene, view, canvas.clientWidth, canvas.clientHeight);
      view = { ...view, pan: [view.pan[0] - dx / s, view.pan[1] + dy / s] };
    } else {
      view = rotateBy(view, dx, dy);
    }
    schedule();
  }

  function onUp(event: PointerEvent) {
    drag = null;
    canvas?.releasePointerCapture?.(event.pointerId);
  }

  function onWheel(event: WheelEvent) {
    event.preventDefault();
    view = { ...view, zoom: Math.min(40, Math.max(0.1, view.zoom * Math.exp(-event.deltaY * 0.0015))) };
    schedule();
  }

  /** What is under the pointer, solved on the CPU against the same quadrics
   *  the shader draws (D4): 12-61 µs an event at 116-173 atoms. */
  function hover(event: PointerEvent) {
    if (!scene || !canvas || !geo) return;
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left, y = event.clientY - box.top;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    const atom = pickAtom(scene, view, width, height, x, y);
    const half = pickHalf(scene, view, width, height, x, y);
    if (atom && (!half || atom.z >= half.z)) {
      reading = atomLabel(geo, geo.atoms[scene.atoms[atom.atom].index], mode);
    } else if (half) {
      reading = bondLabel(geo, geo.bonds[scene.halves[half.half].bond]);
    } else {
      // a face only where no atom or stick is under the pointer: the faces
      // are translucent, and the centre atom inside them stays readable
      const face = pickFace(scene, view, width, height, x, y);
      reading = face ? polyhedronLabel(geo, geo.polyhedra[scene.faces[face.faces].index]) : "";
    }
  }

  /** Whether the legend shows a formula's polyhedra as on. */
  function polyOn(formula: string, byDefault: boolean): boolean {
    return polyhedraIn[mode] && (polyFormulas.get(formula) ?? byDefault);
  }

  function togglePolyhedra(formula: string, byDefault: boolean) {
    polyFormulas = new Map(polyFormulas).set(formula, !(polyFormulas.get(formula) ?? byDefault));
  }

  function toggleSpecies(species: string) {
    const next = new Set(hidden);
    if (next.has(species)) next.delete(species);
    else next.add(species);
    hidden = next;
  }

  /** Look straight down a lattice vector — the projections a crystallographer
   *  draws, and the cure for the roll that free rotation allows. */
  function look(axis: number) {
    if (!geo) return;
    view = axisView(geo, axis, view);
    paint();
  }

  function home() {
    view = openingView();
    paint();
  }

  function setProbability(key: string) {
    level = key;
    if (!geo) return;
    geo = at(geo, key);
    mode = "ellipsoid";
    say(`# ellipsoids at ${(Number(key) * 100).toFixed(0)} % `
      + `(k = ${geo.scale.toFixed(4)} = √χ²₃(${key}))`);
  }

  /**
   * A PNG of the structure, rendered once more offscreen with its long side at
   * `EXPORT_LONG_SIDE` pixels (D5): the screen is a slide at best, and a figure
   * wants 2000 px at 300 dpi.  The letters are DOM on screen, so the export is
   * handed where they sit and how they look, and draws them itself.
   */
  async function savePng() {
    if (!renderer || !scene || !canvas || !geo) return;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    const labels = scene.labels.map((label, k) => {
      const [x, y] = project(scene!, view, width, height, label.pos);
      const style = labelNodes[k] ? getComputedStyle(labelNodes[k]) : null;
      return { text: label.text, x, y, color: style?.color || "#1f5fa8",
               font: style?.font || "600 12px sans-serif" };
    });
    exportError = "";
    const png = await renderer.exportPng(view, {
      background: transparent ? null : background(), labels,
    });
    if (!png) {
      exportError = "the export could not be rendered at any size this GPU allows";
      return;
    }
    const name = `${(geo.name || "structure").replace(/[^\w.-]+/g, "_")}.png`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(png.blob);
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
    say(`# saved ${name}, ${png.width} × ${png.height} px`
      + (transparent ? " on a transparent background" : ""));
  }
</script>

<section class="viewer">
  <header>
    <h2>View</h2>
    <!-- one choice among two, so it wears the app's segmented register — two
         plain buttons here wore the primary (filled) style and both read as
         pressed, which is a control that answers no question -->
    <div class="segmented" role="group" aria-label="draw mode">
      <button class:on={mode === "ball"}
        onclick={() => (mode = "ball")}
        title="spheres at a fraction of the covalent radius — the shape of the
               structure, not of its displacement">balls</button>
      <button class:on={mode === "ellipsoid"}
        onclick={() => (mode = "ellipsoid")}
        title="displacement ellipsoids: refined quantities, so an inflated ADP
               is visible here and nowhere else">ellipsoids</button>
    </div>
    <span class="spacer"></span>
    {#if geo && geo.phases.length > 1}
      <select bind:value={phase}>
        {#each geo.phases as name, i (i)}<option value={i}>{name}</option>{/each}
      </select>
    {/if}
  </header>

  <div class="plot">
    <!-- drag rotates, shift- or right-drag pans, the wheel zooms -->
    <canvas bind:this={canvas}
      onpointerdown={onDown} onpointermove={onMove} onpointerup={onUp}
      onpointercancel={onUp} onpointerleave={() => { if (!drag) reading = ""; }}
      onwheel={onWheel} oncontextmenu={(e) => e.preventDefault()}></canvas>
    <div class="letters" aria-hidden="true">
      {#each ["a", "b", "c"] as text, k (text)}
        <span bind:this={labelNodes[k]} hidden={!geo}>{text}</span>
      {/each}
    </div>
  </div>
  <p class="reading mono">{reading || " "}</p>

  {#if unsupported}
    <p class="bad">this browser has no WebGL2, which the structure viewer draws with</p>
  {:else if error}
    <p class="bad">{error}</p>
  {:else if !geo}
    <p class="muted">{ready ? "no structure yet" : "loading the structure…"}</p>
  {:else}
    <div class="legend">
      {#each entries as entry (entry.species)}
        <button class="ghost" class:off={hidden.has(entry.species)}
          onclick={() => toggleSpecies(entry.species)}
          title={entry.sites.map((s) => `${s.label} ×${s.multiplicity}`
            + (s.special ? " (special)" : "")).join(", ")}>
          <span class="dot" style="background:{entry.color}"></span>{entry.species}
        </button>
      {/each}
    </div>
    {#if polyEntries.length}
      <!-- one switch for the mode it is pressed in, then one per formula:
           shells of four to six start on, larger ones off (P5) -->
      <div class="legend">
        <button class="ghost" class:on={polyhedraIn[mode]}
          onclick={() => (polyhedraIn[mode] = !polyhedraIn[mode])}
          title="coordination polyhedra: on in ball mode and off in ellipsoid mode
                 until switched, since faces would cover the ellipsoids">polyhedra</button>
        {#each polyEntries as entry (entry.formula)}
          <button class="ghost" class:off={!polyOn(entry.formula, entry.byDefault)}
            disabled={!polyhedraIn[mode]}
            onclick={() => togglePolyhedra(entry.formula, entry.byDefault)}
            title="the {entry.formula} polyhedra: the shell ends at the largest gap
                   in its ligand distances">
            <span class="dot" style="background:{entry.color}"></span>{entry.formula}
          </button>
        {/each}
      </div>
    {/if}

    <div class="knobs">
      <span class="inline" title="look straight down a lattice vector: down a
        puts c up and b right, and so round — the projections a structure is
        normally drawn in">view down
        <button class="ghost" onclick={() => look(0)}>a</button>
        <button class="ghost" onclick={() => look(1)}>b</button>
        <button class="ghost" onclick={() => look(2)}>c</button>
        <button class="ghost" onclick={home}>reset</button>
      </span>
      <span class="spacer"></span>
      <button class="ghost" onclick={savePng}
        title="save the picture as a PNG {EXPORT_LONG_SIDE} px on its long side —
               rendered again, not captured from the screen">PNG</button>
      <button class="ghost" class:on={knobsOpen}
        onclick={() => (knobsOpen = !knobsOpen)}
        title="drawing thresholds — none of them is a fact about the sample, so
               none is stored in the project">{knobsOpen ? "▾" : "▸"} drawing</button>
    </div>

    {#if exportError}<p class="bad">{exportError}</p>{/if}

    {#if knobsOpen}
      <!-- Where each knob lives is settled by *what it changes*, not by taste:
           the server owns anything that changes the payload (the bond threshold
           decides which bonds exist), the client owns anything that only
           changes drawing (a probability rescale, an exaggeration). -->
      <div class="knobs drawer">
        {#if mode === "ellipsoid"}
          <label class="inline">probability
            <select value={String(geo.probability)}
              onchange={(e) => setProbability((e.currentTarget as HTMLSelectElement).value)}>
              {#each levels as key (key)}
                <option value={key}>{(Number(key) * 100).toFixed(0)} %</option>
              {/each}
            </select>
          </label>
          <label class="inline" title="a drawing scale, not a probability: k(p)
            = √χ²₃(p) diverges as p → 1, so there is no ellipsoid above 100 % to
            ask for — this makes them bigger and the caption says so">× size
            <input type="range" min="1" max="4" step="0.25" value={exaggeration}
              oninput={(e) => (exaggeration =
                Number((e.currentTarget as HTMLInputElement).value))} />
            <span class="mono">{exaggeration.toFixed(2)}×</span>
          </label>
        {/if}
        <label class="inline" title="a drawing threshold, not physics: a bond is
          drawn at d ≤ tol·(rᵢ+rⱼ) on covalent radii, and no fixed value is right
          for both a large cation and an organic">bonds ≤
          <!-- the *label* follows the drag and the *fetch* waits for the release:
               one round trip per pixel would be a flood, but showing a number
               is not a fetch -->
          <input type="range" min="0.9" max="1.4" step="0.05" value={tolerance}
            oninput={(e) => (toleranceShown =
              Number((e.currentTarget as HTMLInputElement).value))}
            onchange={(e) => (tolerance =
              Number((e.currentTarget as HTMLInputElement).value))} />
          <span class="mono">{toleranceShown.toFixed(2)}×</span>
        </label>
        <label class="inline" title="the same atom at the opposite face (a corner
          site drawn at all eight corners) and the bonded neighbours just outside —
          off leaves the cell's own contents and sticks that end in mid-air">
          <input type="checkbox" checked={showBoundary}
            onchange={(e) => (showBoundary = (e.currentTarget as HTMLInputElement).checked)} />
          images outside the cell
        </label>
        <label class="inline">
          <input type="checkbox" checked={transparent}
            onchange={(e) => (transparent = (e.currentTarget as HTMLInputElement).checked)} />
          transparent PNG
        </label>
      </div>
    {/if}

    <p class="muted">{caption(geo, mode, exaggeration, shown)}</p>
    {#if geo.note}<p class="warn">{geo.note}</p>{/if}
    <p class="muted mono">{geo.space_group} · V = {geo.volume.toFixed(2)} Å³</p>
  {/if}
</section>

<style>
  section.viewer {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }

  header {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
    margin: 8px 0 4px;
  }

  h2 {
    /* the row centers its items; a margin here would push the title off the
       buttons' centerline (its tops sat above the title once) */
    margin: 0;
  }

  .spacer {
    margin-left: auto;
  }

  .plot {
    position: relative;
    flex: 1 1 auto;
    min-height: 300px;
  }

  canvas {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
    touch-action: none;
    cursor: grab;
  }

  canvas:active {
    cursor: grabbing;
  }

  .letters {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
  }

  .letters span {
    position: absolute;
    left: 0;
    top: 0;
    color: var(--accent);
    font-weight: 600;
    font-size: var(--text-sm);
  }

  .reading {
    /* one line, always there, so a hover does not move the controls below */
    min-height: 1.4em;
    margin: 2px 0 0;
    font-size: var(--text-sm);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin: 4px 0 2px;
  }

  /* the species legend acts, so it is `button.ghost` (WP-1201) — laid out
     here only because each one carries its colour swatch */
  .legend button {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
  }

  .off {
    opacity: 0.4;
    text-decoration: line-through;
  }

  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid var(--line);
  }

  .knobs {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 12px;
    margin: 2px 0;
  }

  .knobs.drawer {
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 4px 6px;
    background: var(--panel);
  }

  /* a row of controls, so it is control-sized */
  .inline {
    display: inline-flex;
    align-items: center;
    gap: var(--s2);
    font-size: var(--text-sm);
  }

  input[type="range"] {
    width: 84px;
  }

  p {
    margin: var(--s1) 0;
  }
</style>
