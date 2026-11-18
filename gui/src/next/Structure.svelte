<script lang="ts">
  /**
   * The Structure graph at `/next` (WP-2218, inventory rows 69-82): today's 3D
   * viewer (`panels/Structure3D.svelte`, WP-1015, WP-1462), written here for the
   * rebuild and drawn to the prototype, with PR #1519's fetch key and its empty
   * state for a project with no phase.
   *
   * The prototype's screen, restated in WP-2218 § Context: a title line saying
   * what is drawn, "Look down" a b c, the draw mode and the colour key; the
   * canvas fills the graph; drag rotates and the wheel zooms. The inventory
   * adds the rest, each row placed by a written rule:
   *
   * - the draw mode is a segmented Balls | Ellipsoids, and polyhedra are
   *   entries in the colour key, each a switch (rows 70, 76, 77);
   * - a phase menu shows only with two or more phases (row 71);
   * - a click selects an atom and opens its bar, which holds Show coordination;
   *   a double-click resets the view (row 73, interaction rules 3 and 6);
   * - the name of the atom or bond under the pointer goes to the status bar
   *   (row 74), handed up through `onreadout`;
   * - the image is saved or copied from the canvas's context menu and the view
   *   menu, and the drawing thresholds sit in a Drawing… popover (rows 79, 80);
   * - while ellipsoids show, the title says their probability and any
   *   exaggeration, separately (row 81, WP-1029); the old caption is gone;
   * - no WebGL2, loading and a load error are each one line (row 82).
   *
   * Unapplied slider values are drawn through `POST /api/structure3d`, so a cell
   * dragged in the Interactive tab moves the frame, and the title then reads
   * "Preview, not refined" as the Pattern graph's does (`gui/STYLE.md` § Layout:
   * a preview never reads as a changed fit).
   */
  import { onDestroy, untrack } from "svelte";

  import { ApiError, api } from "../api";
  import { PreviewQueue } from "../lib/interactive";
  import { createRenderer, EXPORT_LONG_SIDE, type Renderer } from "../lib/gl3d";
  import {
    atomLabel,
    axisView,
    bondLabel,
    buildScene,
    elements,
    fillLabel,
    focusedPolyhedra,
    legend,
    onDarkGround,
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
    toggled,
    type Disorder,
    type Geometry,
    type Mode,
    type Scene,
    type View,
  } from "../lib/structure3d";
  import Menu, { type MenuAt, type MenuEntry } from "./Menu.svelte";
  import type { StatusReadout } from "./readout";
  import { structureReadout, structureValues } from "./structure";

  let {
    head = null,
    projectPath = null,
    busy = false,
    theme = "light",
    values = null,
    say = (_line: string) => {},
    onreadout = () => {},
  }: {
    /** the working state's node: a run, a checkout or an edit moves it */
    head?: string | null;
    /** the open project's path, because two fresh projects share a head */
    projectPath?: string | null;
    busy?: boolean;
    /** the resolved theme: the cell frame samples `--accent` and the canvas
     *  the pane's ground, so a theme change redraws (WP-1029) */
    theme?: string;
    /** the Interactive tab's unapplied slider values, or null */
    values?: Record<string, number> | null;
    say?: (line: string) => void;
    onreadout?: (reading: StatusReadout | null) => void;
  } = $props();

  let canvas: HTMLCanvasElement | undefined = $state();
  let labelNodes: HTMLSpanElement[] = $state([]);
  let ringEl: HTMLDivElement | undefined = $state();
  let renderer: Renderer | null = null;
  let unsupported = $state(false);
  /** What is drawn. Not `$state`: nothing renders it, and a deep proxy would
   *  re-render the graph on every frame of a drag. */
  let scene: Scene | null = null;
  const EMPTY: Scene = { atoms: [], halves: [], lines: [], faces: [], labels: [],
                         center: [0, 0, 0], radius: 1, depth: 1 };
  let view: View = openingView();
  let frame = 0;
  let geo = $state.raw<Geometry | null>(null);
  let error = $state("");
  /** The server's sentence for a model with nothing to draw (no phase yet),
   *  an empty state rather than an error (PR #1519). */
  let absent = $state("");
  /** Why the preview was refused: its own field, beside the load error. */
  let previewError = $state("");
  /** Whether the drawing on screen is at unapplied values. */
  let previewShown = $state(false);
  let ready = $state(false);
  let mode = $state<Mode>("ball");
  let phase = $state(0);
  let tolerance = $state(1.15);
  let toleranceShown = $state(1.15);
  let disorder = $state<Disorder>("all");
  let centres = $state<string[] | null>(null);
  let ligands = $state<string[] | null>(null);
  /** One atom's environment (WP-1468), by its site and position, which a
   *  refetch keeps while an index may move. */
  let focus = $state<{ site: number; pos: number[] } | null>(null);
  /** The selected atom, by the same identity. */
  let selected = $state<{ site: number; pos: number[] } | null>(null);
  let level = $state("0.5");
  let hidden = $state(new Set<string>());
  let showBoundary = $state(true);
  let exaggeration = $state(1);
  let polyhedraIn = $state<Record<Mode, boolean>>({ ball: true, ellipsoid: false });
  let polyFormulas = $state(new Map<string, boolean>());
  let depthCue = $state(false);
  let planarRings = $state(false);
  let transparent = $state(false);

  /** The pending values that move the structure: an instrument value moves
   *  the pattern and leaves the drawing as it is. */
  const moving = $derived(structureValues(values));
  const painted = $derived(geo && theme === "dark" ? onDarkGround(geo) : geo);
  const entries = $derived(painted ? legend(painted) : []);
  const levels = $derived(geo ? Object.keys(geo.probability_levels) : []);
  const shown = $derived(!geo ? [] : focus !== null ? focusedPolyhedra(geo, focus)
    : shownPolyhedra(geo, polyhedraIn[mode], polyFormulas, hidden, showBoundary));
  const polyEntries = $derived(painted ? polyhedraLegend(painted) : []);
  const selIndex = $derived(!geo || !selected ? -1 : geo.atoms.findIndex(
    (a) => a.site === selected!.site && a.pos.every((v, k) => Math.abs(v - selected!.pos[k]) < 1e-6)));
  const selName = $derived(geo && selIndex >= 0 ? siteName(geo, geo.atoms[selIndex].site) : "");
  const focusedHere = $derived(!!focus && !!selected && focus.site === selected.site
    && focus.pos.every((v, k) => Math.abs(v - selected!.pos[k]) < 1e-6));

  function siteName(g: Geometry, site: number): string {
    const s = g.sites[site];
    return s.label === s.species ? s.label : `${s.label} (${s.species})`;
  }

  // -- fetching ---------------------------------------------------------------
  /** The values of the request in flight. The queue sends one at a time, so a
   *  failure is this request's, and only one that carried values is a refused
   *  preview. */
  let sent: Record<string, number> = {};
  /** One request in flight, the newest waiting: a slider drag asks on every
   *  move, and the drawing follows the last values it can (the Pattern graph's
   *  queue, `lib/interactive.ts`). An empty map is the working state. */
  const queue = new PreviewQueue<Geometry>(
    (vals) => {
      sent = vals;
      return api.structure3d(phase, tolerance, disorder, centres, ligands,
                             Object.keys(vals).length ? vals : null);
    },
    (payload, vals) => {
      geo = at(payload, level);
      error = absent = "";
      previewShown = Object.keys(vals).length > 0;
      // a refusal stands while the values that were refused do; a run asks for
      // no preview, so it ends one (a 409 that raced the run's start)
      if (previewShown || !untrack(() => moving) || untrack(() => busy)) previewError = "";
      ready = true;
    },
    (exc) => {
      ready = true;
      if (exc instanceof ApiError && (exc.empty || exc.code === "NOT_FOUND")) {
        geo = null;
        error = previewError = "";
        previewShown = false;
        absent = exc.empty ? "" : exc.message;
      } else if (Object.keys(sent).length) {
        // a refused preview keeps the drawing it had, or draws the working
        // state when it had none, and says so on the title; that request
        // carries no values, so its own failure is a load error and never loops
        previewError = (exc as Error).message;
        if (!geo) queue.push({});
      } else {
        error = (exc as Error).message;
      }
    },
  );

  let fetchedFor = "";
  let chosenIn: string | null | undefined = undefined;
  $effect(() => {
    if (projectPath !== chosenIn) {
      if (chosenIn !== undefined) untrack(() => { phase = 0; clearChemistry(); selected = null; });
      chosenIn = projectPath;
    }
    // a run refuses a preview (409), so the working state is drawn meanwhile
    const vals = busy ? null : moving;
    const key = JSON.stringify([projectPath, head, phase, tolerance, disorder, centres,
                                ligands, vals]);
    if (key === fetchedFor) return;
    fetchedFor = key;
    untrack(() => queue.push(vals ?? {}));
  });

  /** A payload at the chosen ellipsoid level: the payload carries k(p) for
   *  every level, so this is a client multiply and a reload keeps the level. */
  function at(payload: Geometry, key: string): Geometry {
    const scale = payload.probability_levels[key];
    return scale === undefined ? payload : { ...payload, probability: Number(key), scale };
  }

  // -- drawing ------------------------------------------------------------------
  /** One renderer for the canvas's life. The canvas is this effect's only
   *  dependency (gui/CLAUDE.md, WP-1462), or each payload loses the context. */
  $effect(() => {
    if (!canvas) return;
    renderer = createRenderer(canvas);
    unsupported = renderer === null;
    renderer?.setDepthCue(untrack(() => depthCue));
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

  $effect(() => {
    void geo;
    void mode;
    void hidden;
    void showBoundary;
    void planarRings;
    void exaggeration;
    void theme;
    void shown;
    void rebuild();
  });

  $effect(() => {
    void selIndex;
    placeLabels();
  });

  onDestroy(() => onreadout(null));

  /** A new scene, then a frame, one microtask late: a style sampled in an
   *  effect races the shell's theme stamp (gui/CLAUDE.md, WP-1027). */
  async function rebuild() {
    const geometry = geo;
    await Promise.resolve();
    if (geometry !== geo) return;
    if (!geometry) {
      scene = EMPTY;
      renderer?.setScene(scene);
      paint();
      return;
    }
    const style = getComputedStyle(document.body);
    const cell = style.getPropertyValue("--accent").trim() || "#c65d0a";
    scene = buildScene(theme === "dark" ? onDarkGround(geometry) : geometry,
                       { mode, hidden, showBoundary, exaggeration, cell, polyhedra: shown,
                         fills: planarRings ? geometry.rings ?? [] : [] });
    renderer?.setScene(scene);
    paint();
  }

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

  /** The colour the opaque canvas clears to: the first opaque ground above it. */
  function background(): number[] {
    let el: Element | null = canvas?.parentElement ?? null;
    while (el) {
      const colour = getComputedStyle(el).backgroundColor;
      const parts = /^rgba?\(/.test(colour) ? colour.match(/[\d.]+/g)?.map(Number) ?? [] : [];
      if (parts.length >= 3 && (parts.length < 4 || parts[3] >= 1)) {
        return parts.slice(0, 3).map((v) => v / 255);
      }
      el = el.parentElement;
    }
    const token = getComputedStyle(document.body).getPropertyValue("--bg").trim();
    return rgb(token || "#fbfaf8");
  }

  /** The a, b, c letters and the selection ring, as DOM over the canvas. */
  function placeLabels() {
    if (!scene || !canvas) return;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    scene.labels.forEach((label, k) => {
      const node = labelNodes[k];
      if (!node) return;
      const [x, y] = project(scene!, view, width, height, label.pos);
      node.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    });
    placeRing(width, height);
  }

  /** The ring round the selected atom: a DOM mark, so selecting repaints no
   *  scene (`gui/STYLE.md` § Plots: a selected mark carries a ring in `--fg`). */
  function placeRing(width: number, height: number) {
    if (!ringEl || !scene) return;
    const atom = selIndex < 0 ? undefined : scene.atoms.find((a) => a.index === selIndex);
    if (!atom) {
      ringEl.style.display = "none";
      return;
    }
    const [x, y] = project(scene, view, width, height, atom.pos);
    const m = atom.shape;
    const semi = Math.max(...[0, 1, 2].map((c) => Math.hypot(m[c], m[3 + c], m[6 + c])));
    const r = semi * pixelsPerAngstrom(scene, view, width, height) + 4;
    ringEl.style.display = "block";
    ringEl.style.width = ringEl.style.height = `${2 * r}px`;
    ringEl.style.transform = `translate(${x - r}px, ${y - r}px)`;
  }

  // -- the pointer --------------------------------------------------------------
  let drag: { x: number; y: number; x0: number; y0: number; pan: boolean } | null = null;

  function onDown(event: PointerEvent) {
    drag = { x: event.clientX, y: event.clientY, x0: event.clientX, y0: event.clientY,
             pan: event.button === 2 || event.shiftKey };
    canvas?.setPointerCapture?.(event.pointerId);
    onreadout(null);
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
    const was = drag;
    drag = null;
    canvas?.releasePointerCapture?.(event.pointerId);
    // a press that did not move is a click: it selects what is under it
    if (was && event.button === 0 && Math.hypot(event.clientX - was.x0, event.clientY - was.y0) < 4) {
      select(atomAt(event));
    }
  }

  /** The atom under the pointer, by its site and position, or null. */
  function atomAt(event: MouseEvent): { site: number; pos: number[] } | null {
    if (!scene || !canvas || !geo) return null;
    const box = canvas.getBoundingClientRect();
    const hit = pickAtom(scene, view, canvas.clientWidth, canvas.clientHeight,
                         event.clientX - box.left, event.clientY - box.top);
    if (!hit) return null;
    const { site, pos } = geo.atoms[scene.atoms[hit.atom].index];
    return { site, pos };
  }

  function select(atom: { site: number; pos: number[] } | null) {
    selected = atom;
  }

  /** Show the selected atom's environment alone, or end it (WP-1468). */
  function coordination() {
    if (!geo || !selected) return;
    if (focusedHere) {
      clearChemistry();
      return;
    }
    focus = { ...selected };
    centres = [geo.sites[selected.site].element];
    ligands = elements(geo);
  }

  function clearChemistry() {
    focus = null;
    centres = null;
    ligands = null;
  }

  function onWheel(event: WheelEvent) {
    event.preventDefault();
    view = { ...view, zoom: Math.min(40, Math.max(0.1, view.zoom * Math.exp(-event.deltaY * 0.0015))) };
    schedule();
  }

  /** What is under the pointer, solved on the CPU against the quadrics the
   *  shader draws, named in the status bar. */
  function hover(event: PointerEvent) {
    if (!scene || !canvas || !geo) return;
    const box = canvas.getBoundingClientRect();
    const x = event.clientX - box.left, y = event.clientY - box.top;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    const atom = pickAtom(scene, view, width, height, x, y);
    const half = pickHalf(scene, view, width, height, x, y);
    let text = "";
    if (atom && (!half || atom.z >= half.z)) {
      text = atomLabel(geo, geo.atoms[scene.atoms[atom.atom].index], mode);
    } else if (half) {
      text = bondLabel(geo, geo.bonds[scene.halves[half.half].bond]);
    } else {
      const face = pickFace(scene, view, width, height, x, y);
      const hit = face ? scene.faces[face.faces] : null;
      text = !hit ? ""
        : hit.kind === "polyhedron" ? polyhedronLabel(geo, geo.polyhedra[hit.index])
        : fillLabel(geo, (geo.rings ?? [])[hit.index]);
    }
    onreadout(structureReadout(text));
  }

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
    say(`# ellipsoids at ${(Number(key) * 100).toFixed(0)} % `
      + `(k = ${geo.scale.toFixed(4)} = √χ²₃(${key}))`);
  }

  // -- the image ------------------------------------------------------------------
  /** A PNG rendered again offscreen at `EXPORT_LONG_SIDE` (WP-1462 D5), with
   *  the a, b, c letters drawn in where they sit on screen. */
  async function render(onClear: boolean) {
    if (!renderer || !scene || !canvas || !geo) return null;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    const labels = scene.labels.map((label, k) => {
      const [x, y] = project(scene!, view, width, height, label.pos);
      const style = labelNodes[k] ? getComputedStyle(labelNodes[k]) : null;
      return { text: label.text, x, y, color: style?.color || "#a34c06",
               font: style?.font || "600 12px sans-serif" };
    });
    const png = await renderer.exportPng(view, { background: onClear ? null : background(), labels });
    if (!png) say("# the image could not be rendered at any size this GPU allows");
    return png;
  }

  async function saveImage() {
    pop = null;
    const png = await render(transparent);
    if (!png || !geo) return;
    const name = `${(geo.name || "structure").replace(/[^\w.-]+/g, "_")}.png`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(png.blob);
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
    say(`# saved ${name}, ${png.width} × ${png.height} px`
      + (transparent ? " on a transparent background" : "")
      + (transparent && depthCue ? ", without the depth cue" : ""));
  }

  async function copyImage() {
    const png = await render(false);
    if (!png) return;
    try {
      await navigator.clipboard.write([new ClipboardItem({ "image/png": png.blob })]);
      say(`# copied the structure, ${png.width} × ${png.height} px`);
    } catch (exc) {
      say(`# the image could not be copied: ${(exc as Error).message}`);
    }
  }

  // -- menus and popovers ---------------------------------------------------------
  let viewButton: HTMLButtonElement | undefined = $state();
  let viewAt = $state<MenuAt | null>(null);
  let ctxAt = $state<MenuAt | null>(null);
  /** The open popover: the drawing thresholds or the image's choices. */
  let pop = $state<{ kind: "drawing" | "save"; x: number; y: number } | null>(null);

  function openView() {
    // the menu opens where an open popover sits, so the popover gives way
    pop = null;
    const r = viewButton!.getBoundingClientRect();
    viewAt = { x: r.right, y: r.bottom + 4, align: "right" };
  }

  const viewItems = $derived<MenuEntry[]>([
    { id: "home", label: "Reset view", disabled: !geo },
    { id: "drawing", label: "Drawing…", disabled: !geo },
    "-",
    { id: "save", label: "Save image…", disabled: !geo || unsupported },
    { id: "copy", label: "Copy image", disabled: !geo || unsupported },
  ]);

  const ctxItems = $derived<MenuEntry[]>([
    ...(selected ? [{ id: "coord", label: focusedHere ? "Show every atom" : "Show coordination" },
                    "-" as const] : []),
    { id: "save", label: "Save image…", disabled: !geo || unsupported },
    { id: "copy", label: "Copy image", disabled: !geo || unsupported },
  ]);

  function choose(id: string) {
    const r = viewButton?.getBoundingClientRect();
    const x = r ? r.right : 0, y = r ? r.bottom + 4 : 0;
    if (id === "home") home();
    else if (id === "drawing") pop = { kind: "drawing", x, y };
    else if (id === "save") pop = { kind: "save", x, y };
    else if (id === "copy") void copyImage();
    else if (id === "coord") coordination();
  }

  function context(event: MouseEvent) {
    event.preventDefault();
    const atom = atomAt(event);
    if (atom) select(atom);
    ctxAt = { x: event.clientX, y: event.clientY };
  }

  function windowDown(event: PointerEvent) {
    const t = event.target as Element;
    if (pop && !t.closest(".structpop") && !t.closest("[data-structview]")) pop = null;
  }

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    if (pop) pop = null;
    else if (selected) selected = null;
  }

  const pctText = (p: number) => `${(p * 100).toFixed(0)} %`;
</script>

<svelte:window onpointerdown={windowDown} onkeydown={keydown} />

<div class="structgraph">
  <div class="ghead">
    <div class="gtitle" title={[previewShown ? "Preview, not refined" : "Structure at the current values",
      previewError ? `Preview refused: ${previewError}` : "",
      geo && mode === "ellipsoid" ? `ellipsoids at ${pctText(geo.probability)}` : "",
      geo?.note ?? ""].filter(Boolean).join(". ")}>
      {#if previewShown}
        <b class="pv">Preview, not refined</b>
      {:else if geo}
        <b>Structure at the current values</b>
      {/if}
      {#if previewError}<span class="bad">Preview refused</span>{/if}
      {#if geo && mode === "ellipsoid"}
        <!-- the probability and the exaggeration are two facts (WP-1029) -->
        <span>Ellipsoids at <span class="num">{pctText(geo.probability)}</span>{#if exaggeration !== 1},
          drawn <span class="num">×{exaggeration.toFixed(2)}</span>{/if}</span>
      {/if}
      {#if geo?.note}<span>{geo.note}</span>{/if}
    </div>
    <div class="gctl">
      {#if geo && geo.phases.length > 1}
        <select class="phase" aria-label="Phase" bind:value={phase}
          onchange={() => { clearChemistry(); selected = null; }}>
          {#each geo.phases as name, i (i)}<option value={i}>{name}</option>{/each}
        </select>
      {/if}
      <span class="vg">Look down
        {#each ["a", "b", "c"] as axis, k (axis)}
          <button class="ghost axis" disabled={!geo} onclick={() => look(k)}
            title="Look straight down {axis}">{axis}</button>
        {/each}
      </span>
      <span class="segmented" role="group" aria-label="Draw atoms as">
        <button class:on={mode === "ball"} aria-pressed={mode === "ball"} disabled={!geo}
          onclick={() => (mode = "ball")} title="Draw each atom as a ball">Balls</button>
        <button class:on={mode === "ellipsoid"} aria-pressed={mode === "ellipsoid"} disabled={!geo}
          onclick={() => (mode = "ellipsoid")}
          title="Draw each atom's displacement ellipsoid">Ellipsoids</button>
      </span>
      <button class="ib" bind:this={viewButton} data-structview aria-label="View" aria-haspopup="menu"
        aria-expanded={!!viewAt} disabled={!geo} onclick={openView}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="3.5" cy="8" r="1" /><circle cx="8" cy="8" r="1" /><circle cx="12.5" cy="8" r="1" /></svg>
      </button>
    </div>
  </div>
  {#if geo}
    <!-- the colour key: each entry a switch (row 76), polyhedra among them (row 77) -->
    <div class="key" role="group" aria-label="Colour key">
      {#each entries as entry (entry.species)}
        <button class="entry" aria-pressed={!hidden.has(entry.species)}
          onclick={() => toggleSpecies(entry.species)}
          title={`${hidden.has(entry.species) ? "Show" : "Hide"} ${entry.species}: `
            + entry.sites.map((s) => `${s.label} ×${s.multiplicity}`).join(", ")}>
          <i style:background={entry.color}></i>{entry.species}</button>
      {/each}
      {#if polyEntries.length}
        <button class="entry" aria-pressed={polyhedraIn[mode]}
          onclick={() => (polyhedraIn[mode] = !polyhedraIn[mode])}
          title={polyhedraIn[mode] ? "Hide the coordination polyhedra" : "Show the coordination polyhedra"}
          >Polyhedra</button>
        {#each polyEntries as entry (entry.formula)}
          <button class="entry" aria-pressed={entry.available && polyOn(entry.formula, entry.byDefault)}
            disabled={!entry.available || !polyhedraIn[mode]}
            onclick={() => togglePolyhedra(entry.formula, entry.byDefault)}
            title={entry.available ? `Show or hide the ${entry.formula} polyhedra`
              : `The ${entry.formula} polyhedra reach past the atoms drawn`}>
            <i class="poly" style:background={entry.color}></i>{entry.formula}</button>
        {/each}
      {/if}
    </div>
  {/if}

  <div class="view">
    <canvas bind:this={canvas} aria-label="Crystal structure, drag to rotate"
      onpointerdown={onDown} onpointermove={onMove} onpointerup={onUp} ondblclick={home}
      onpointercancel={() => (drag = null)}
      onpointerleave={() => { if (!drag) onreadout(null); }}
      onwheel={onWheel} oncontextmenu={context}></canvas>
    <div class="letters" aria-hidden="true">
      {#each ["a", "b", "c"] as text, k (text)}
        <span bind:this={labelNodes[k]} hidden={!geo}>{text}</span>
      {/each}
      <div class="ring" bind:this={ringEl}></div>
    </div>
    {#if selected && selName}
      <div class="selbar" role="toolbar" aria-label="Selected atom">
        <span>{selName}</span>
        <button class="ghost" aria-pressed={focusedHere} onclick={coordination}
          title={focusedHere ? "Show every atom again" : "Show this atom's coordination alone"}
          >{focusedHere ? "Show every atom" : "Show coordination"}</button>
        <button class="ib" aria-label="Close" title="Close" onclick={() => (selected = null)}>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" /></svg>
        </button>
      </div>
    {/if}
    {#if unsupported}
      <p class="empty bad">This browser has no WebGL2, which the structure is drawn with.</p>
    {:else if error}
      <p class="empty bad">{error}</p>
    {:else if !geo}
      <p class="empty">{absent || (ready ? "No structure to draw." : "Loading the structure…")}</p>
    {/if}
  </div>
</div>

{#if viewAt}
  <Menu at={viewAt} label="View" anchor={viewButton} items={viewItems}
    onchoose={choose} onclose={() => (viewAt = null)} />
{/if}
{#if ctxAt}
  <Menu at={ctxAt} label="Structure" items={ctxItems} onchoose={choose} onclose={() => (ctxAt = null)} />
{/if}

{#if pop && geo}
  <div class="structpop" role="dialog" style:right="{innerWidth - pop.x}px" style:top="{pop.y}px"
    aria-label={pop.kind === "drawing" ? "Drawing" : "Save image"}>
    {#if pop.kind === "drawing"}
      {#if mode === "ellipsoid"}
        <label class="row">Probability
          <select value={String(geo.probability)}
            onchange={(e) => setProbability((e.currentTarget as HTMLSelectElement).value)}>
            {#each levels as key (key)}<option value={key}>{pctText(Number(key))}</option>{/each}
          </select>
        </label>
        <label class="row">Size
          <input type="range" min="1" max="4" step="0.25" value={exaggeration}
            oninput={(e) => (exaggeration = Number((e.currentTarget as HTMLInputElement).value))} />
          <span class="num">×{exaggeration.toFixed(2)}</span>
        </label>
      {/if}
      <label class="row">Bonds up to
        <input type="range" min="0.9" max="1.4" step="0.05" value={tolerance}
          oninput={(e) => (toleranceShown = Number((e.currentTarget as HTMLInputElement).value))}
          onchange={(e) => (tolerance = Number((e.currentTarget as HTMLInputElement).value))} />
        <span class="num">×{toleranceShown.toFixed(2)}</span>
      </label>
      {#if geo.centre_elements && geo.ligand_elements}
        <div class="row">Centres
          <span class="els">{#each elements(geo) as el (el)}
            <button class="entry" aria-pressed={geo.centre_elements.includes(el)}
              onclick={() => { focus = null; centres = toggled(centres ?? geo!.centre_elements ?? [], el); }}
              title="Draw polyhedra round each {el}">{el}</button>
          {/each}</span>
        </div>
        <div class="row">Corners
          <span class="els">{#each elements(geo) as el (el)}
            <button class="entry" aria-pressed={geo.ligand_elements.includes(el)}
              onclick={() => { focus = null; ligands = toggled(ligands ?? geo!.ligand_elements ?? [], el); }}
              title="Put each {el} at a polyhedron's corners">{el}</button>
          {/each}</span>
        </div>
      {/if}
      {#if geo.minor_sites?.length}
        <label class="check"><input type="checkbox" checked={disorder === "major"}
          onchange={(e) => (disorder = (e.currentTarget as HTMLInputElement).checked ? "major" : "all")} />
          Major alternative only</label>
      {/if}
      <label class="check"><input type="checkbox" checked={showBoundary}
        onchange={(e) => (showBoundary = (e.currentTarget as HTMLInputElement).checked)} />
        Images outside the cell</label>
      <label class="check"><input type="checkbox" checked={depthCue}
        onchange={(e) => {
          depthCue = (e.currentTarget as HTMLInputElement).checked;
          renderer?.setDepthCue(depthCue);
          schedule();
        }} />
        Depth cue</label>
      <label class="check"><input type="checkbox" checked={planarRings}
        onchange={(e) => (planarRings = (e.currentTarget as HTMLInputElement).checked)} />
        Fill planar rings</label>
      <div class="popactions">
        <button class="ghost" disabled={centres === null && ligands === null}
          onclick={clearChemistry}>Default</button>
        <button class="ghost" onclick={() => (pop = null)}>Done</button>
      </div>
    {:else}
      <label class="check"><input type="checkbox" checked={transparent}
        onchange={(e) => (transparent = (e.currentTarget as HTMLInputElement).checked)} />
        Transparent background</label>
      <div class="popactions">
        <button class="ghost" onclick={() => (pop = null)}>Cancel</button>
        <button onclick={saveImage}
          title="Save a PNG {EXPORT_LONG_SIDE} px on its long side">Save</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .structgraph {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  .vg {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  /* the axis letters are crystallography's, so italic serif as on the cell */
  .axis {
    font-family: var(--serif-family, "STIX Two Text", serif);
    font-style: italic;
  }

  .phase {
    font: inherit;
    color: var(--fg);
  }

  .key {
    flex: none;
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
    padding: 0 16px 4px;
    font-size: var(--text-sm);
  }

  .entry {
    all: unset;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    cursor: pointer;
    color: var(--fg);
    border-radius: 3px;
  }

  .entry[aria-pressed="false"] {
    color: var(--muted);
    text-decoration: line-through;
  }

  .entry:disabled {
    cursor: default;
    color: var(--muted);
  }

  .entry:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .entry i {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--fg) 25%, transparent);
  }

  .entry i.poly {
    border-radius: 2px;
  }

  .entry[aria-pressed="false"] i {
    opacity: 0.4;
  }

  .view {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
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
    color: var(--accent-ink);
    font-weight: 600;
    font-size: var(--text-sm);
  }

  .ring {
    display: none;
    position: absolute;
    left: 0;
    top: 0;
    box-sizing: border-box;
    border: 1.5px solid var(--fg);
    border-radius: 50%;
  }

  .selbar {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 4px 4px 12px;
    border: 1px solid var(--line-strong);
    border-radius: 8px;
    background: var(--panel);
    box-shadow: 0 4px 16px color-mix(in srgb, var(--fg) 12%, transparent);
    font-size: var(--text-sm);
    white-space: nowrap;
  }

  .empty {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
    color: var(--muted);
    pointer-events: none;
  }

  .empty.bad {
    color: var(--bad);
  }

  .num {
    font-family: var(--mono-family);
  }

  .structpop {
    position: fixed;
    z-index: 30;
    width: 300px;
    box-sizing: border-box;
    padding: 12px;
    border: 1px solid var(--line-strong);
    border-radius: 10px;
    background: var(--panel);
    box-shadow: 0 8px 28px color-mix(in srgb, var(--fg) 14%, transparent);
    font-size: var(--text-sm);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .structpop .row {
    display: grid;
    grid-template-columns: 7em 1fr auto;
    align-items: center;
    gap: 8px;
  }

  .structpop .els {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 10px;
    grid-column: 2 / 4;
  }

  .structpop .check {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .structpop input[type="range"] {
    width: 100%;
    accent-color: var(--accent);
  }

  .popactions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
