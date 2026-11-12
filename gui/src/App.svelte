<script lang="ts">
  /**
   * The shell: one header of run controls and statistics, the plot, the panels.
   *
   * State lives in runes here and is passed down; there is no store library
   * because there is one session and one project, and a second source of truth
   * for "is a run in flight" is exactly the bug the server's 409 exists to
   * prevent. The `state` frame from the event stream is that truth — every
   * control's disabled attribute derives from it rather than from what the last
   * click hoped.
   *
   * Two things landed here in WP-1011 rather than in a panel.  The **command
   * palette** is the shell's, because its entries are every verb the app has and
   * each one echoes the Python call it makes — the palette is the API's index,
   * not a menu.  And **Simple/Advanced** is one flag persisted to
   * `ProjectDoc.ui`, whose keys the frontend owns (WP-1005): it is a property of
   * the project a user comes back to, not of this browser tab.
   */
  import { onMount, setContext, untrack } from "svelte";

  import { ApiError, api } from "./api";
  import Help from "./Help.svelte";
  import ActionBar from "./panels/ActionBar.svelte";
  import Checklist from "./panels/Checklist.svelte";
  import Console from "./panels/Console.svelte";
  import History from "./panels/History.svelte";
  import Interactive from "./panels/Interactive.svelte";
  import Model from "./panels/Model.svelte";
  import NewProject from "./panels/NewProject.svelte";
  import Palette from "./panels/Palette.svelte";
  import Params from "./panels/Params.svelte";
  import PeakWindows from "./panels/PeakWindows.svelte";
  import Peaks from "./panels/Peaks.svelte";
  import Plan from "./panels/Plan.svelte";
  import Plot from "./panels/Plot.svelte";
  import Background from "./panels/Background.svelte";
  import { backgroundTitle } from "./lib/background";
  import Report from "./panels/Report.svelte";
  import Series from "./panels/Series.svelte";
  import Splitter from "./panels/Splitter.svelte";
  import Start from "./panels/Start.svelte";
  import FileMenu from "./panels/FileMenu.svelte";
  import Recovery from "./panels/Recovery.svelte";
  import { RecoveryWriter, combine, readDraft, type Draft } from "./lib/recovery";
  import Stubs from "./panels/Stubs.svelte";
  import Text from "./panels/Text.svelte";
  import {
    HELP_CONTEXT,
    type HelpOpener,
    type HelpRequest,
  } from "./lib/helpContext";
  import { manualUrl, place, resolve, splitKey, type HelpCorpus } from "./lib/help";
  import { isShortcutTarget, type Command } from "./lib/palette";
  import { cellText, type PeaksPayload } from "./lib/peaks";
  import { consoleLine, follow, type EngineEvent, type RunState } from "./lib/stream";
  import { SHELL_MIN, shellStacks } from "./lib/resize";
  import { GRAPH_TABS, TABS, type GraphTab, type Tab } from "./lib/tabs";
  import { FALLBACK_FWHM_DEG, type PreviewAnswer, type RangeContext } from "./lib/interactive";
  import { peakWindows, widestFwhm } from "./lib/peakwin";
  import {
    THEME_CHOICES,
    applyTheme,
    readChoice,
    resolveTheme,
    type Theme,
    type ThemeChoice,
  } from "./lib/theme";

  let version = $state<any>(null);
  let capabilities = $state<any>(null);
  let corpus = $state<HelpCorpus | null>(null);
  let project = $state<any>(null);
  let recent = $state<any[]>([]);
  let examples = $state<any[]>([]);
  let openError = $state<string>("");
  /** the start screen over an open project, from the header's Open… (WP-2131);
   *  with no project it is always shown, so this is only the over-a-project case */
  let startOpen = $state(false);
  /** the New project dialog (WP-2131) */
  let newOpen = $state(false);

  let run = $state<RunState | null>(null);
  let result = $state<any>(null);
  let resultError = $state<string>("");
  let lines = $state<string[]>([]);
  let dropped = $state(0);
  let plotKey = $state(0);

  /** The nine panels, and the one that is showing.  The strip itself is
   *  `lib/tabs.ts` — data, because the manual is held to it (WP-1017). */
  let tab = $state<Tab>("params");
  const modelTab = $derived(tab === "model");
  const textTab = $derived(tab === "text");
  const seriesTab = $derived(tab === "series");
  // The checklist's last step, ticked wherever the tab was reached from — the
  // strip, the palette, `?`, or the report's own link from the header
  // (WP-1017). One effect rather than a flag at four call sites.
  $effect(() => {
    if (tab === "report") reportSeen = true;
  });

  /** Which of the window's two panels are hidden (WP-2123).
   *
   * The maintainer's ruling of 2026-11-07: both side panels collapse, each from
   * a button on its own side that never moves. Hiding the graphs is the
   * full-window column WP-1034 shipped as `Split | Full`, so the pair replaces
   * it. One panel always shows, because a window of nothing is no layout.
   * Session-local and unpersisted, as `Split | Full` was: a layout is a view
   * choice, not a setting (WP-1033's line between the two). */
  let hideGraphs = $state(false);
  let hideModel = $state(false);
  /** The graph strip's tab (`lib/tabs.ts`), one today. */
  let graphTab = $state<GraphTab>("pattern");
  /** The window's width, and whether it has dropped to one column. */
  let windowWidth = $state(0);
  const stacked = $derived(shellStacks(windowWidth));
  /** The model panel's height while stacked, or `null` for half the window.
   *  Session-local: `side_width` is the stored setting, and a height chosen in
   *  a narrow window says nothing about the next one. */
  let sideHeight = $state<number | null>(null);
  /** The action bar's refine choice and the Parameters panel's pending edits. */
  let refineMode = $state<"cycle" | "plan">("plan");
  let pendingTouched = $state(0);
  let pendingInvalid = $state("");
  /** The Interactive tab's pending slider values and the preview they drew
   *  (WP-2128). The action bar counts both panels' edits as one set. */
  let sliderTouched = $state(0);
  let previewAnswer = $state.raw<PreviewAnswer | null>(null);
  let previewError = $state("");
  const touched = $derived(pendingTouched + sliderTouched);
  /** The curves the pattern graph last fetched, which the Single peaks graph
   *  frames and the sliders' ranges are measured from. */
  let baseCurves = $state.raw<any>(null);
  const rangeContext = $derived.by((): RangeContext => {
    const tt = baseCurves?.arrays?.two_theta;
    const fwhm = baseCurves ? widestFwhm(peakWindows(baseCurves)) : 0;
    return { fwhm: fwhm > 0 ? fwhm : FALLBACK_FWHM_DEG,
             thetaMaxDeg: tt?.length ? tt[tt.length - 1] / 2 : 45 };
  });
  /** One name per phase, in order. The tick rows are keyed by phase name, but
   *  a magnetic phase adds a `"<name> (magnetic)"` row after its own and the
   *  declared peaks a `"(extra)"` row (`refine._tick_rows`), and either would
   *  shift every later phase's name by one place. */
  const phaseNames = $derived.by(() => {
    const out: string[] = [];
    for (const key of Object.keys(baseCurves?.header?.ticks ?? {})) {
      if (key === "(extra)" || (out.length && key === `${out[out.length - 1]} (magnetic)`)) continue;
      out.push(key);
    }
    return out;
  });
  /** whether the Plan tab holds an edited plan, which the action bar counts as
   *  one pending edit and its Apply stores (WP-2127) */
  let planPending = $state(false);
  const pendingTotal = $derived(touched + (planPending ? 1 : 0));

  /** The recovery copy of the pending edits (WP-2209, the maintainer's
   *  ruling of 2026-11-09).  The writer is armed for the open project once
   *  its kept copy has been offered and answered, and the effect below hands
   *  it every change: the panels' `draft()` read their pending maps, so a
   *  retyped value is a change even where the count stays the same.  A
   *  switch of project disarms it first, so the panels' emptied maps never
   *  overwrite the copy of the project just left. */
  const recoveryWriter = new RecoveryWriter(
    (path, at, draft) => api.putRecovery(path, at, draft));
  let offer = $state.raw<{ path: string; draft: Draft; savedUtc: string | null;
                           moved: boolean } | null>(null);
  $effect(() => {
    const path = project?.path ?? null;
    const draft = combine(pendingTotal, paramsPanel?.draft() ?? null,
                          interactivePanel?.draft() ?? null, planPanel?.draft() ?? null);
    const at = head;
    untrack(() => recoveryWriter.schedule(path, at, draft));
  });
  /** Bumped by every project opened, so the Plan tab starts over: its unsaved
   *  stages and its undo stack belong to the project they were made in, and
   *  `{#if project}` stays true across an open. */
  let opens = $state(0);
  let simple = $state(true);
  /** The first-run checklist's own two pieces of state (WP-1017): whether it
   *  has been dismissed for this project, and whether the Report tab has been
   *  looked at — the one step that is about the person rather than the
   *  project, and therefore session-local rather than persisted. */
  let firstRun = $state(true);
  let reportSeen = $state(false);
  let consoleHeight = $state(150);
  /** The panel column's width in px, or `null` for "nobody has said".
   *
   * `null` is not laziness: while it holds, the CSS `clamp(340px, 38%, 560px)`
   * supplies the width, so a fresh project is responsive rather than frozen at
   * whatever the first window this project was ever opened in happened to be.
   * The first drag replaces it with a number, which is the user having said. */
  let sideWidth = $state<number | null>(null);
  let sideMeasured = $state(0);
  let sideMeasuredHeight = $state(0);
  /** The Model pane's first two column widths; its third takes the rest. */
  let modelColumns = $state<number[] | null>(null);
  let mainEl: HTMLElement | undefined = $state();

  /** The theme *choice* — three-way, because "follow the system" is a decision
   *  and not the absence of one (lib/theme.ts). */
  let themeChoice = $state<ThemeChoice>("system");
  let systemDark = $state(false);
  const theme = $derived<Theme>(resolveTheme(themeChoice, systemDark));
  const GLYPH: Record<ThemeChoice, string> = { system: "◐", light: "☀", dark: "☾" };
  const THEME_TITLE: Record<ThemeChoice, string> = {
    system: "follow the system, and keep following it when it changes",
    light: "light, whatever the system does",
    dark: "dark, whatever the system does",
  };

  // one authority on the resolved theme, stamped where CSS and CodeMirror both
  // read it — no component derives it a second time from `matchMedia`
  $effect(() => applyTheme(theme, document.documentElement));
  let paletteOpen = $state(false);
  let paramsPanel = $state<any>(null);
  let interactivePanel = $state<any>(null);
  let planPanel = $state<any>(null);
  let modelPanel = $state<any>(null);
  let seriesPanel = $state<any>(null);
  /** a 2θ window the report panel asked the plot to show, or null for all of it */
  let zoom = $state<[number, number] | null>(null);
  /** the last applied suggestion, until it is undone — carries the node to check
   *  out and the χ² it was applied at, which is what makes the *observed* Δχ²
   *  measurable beside the predicted one */
  let applied = $state<any>(null);
  /** the stored peak list plus the raw pattern (WP-1027); the plot draws it and
   *  the Peaks tab is its ledger, so the state lives here, once */
  let peaksData = $state<PeaksPayload | null>(null);
  /** the last indexing answer, with the server's per-candidate adopt verdicts */
  let indexAnswer = $state<any>(null);
  /** streamed per-system graded shortlists (WP-1042/1045): every
   *  `consensus:<system>` stage_end of the run in flight, folded by the panel.
   *  Cleared on `index_start`, kept after the run ends — the anytime answer
   *  remains readable beside the final one. */
  let indexSnapshots = $state<Array<Record<string, any>>>([]);
  /** the last extinction screen — cleared whenever the candidates renumber,
   *  which the server enforces too (a new index run 409s the stale GET) */
  let extinction = $state<any>(null);
  /** the peak the pointer is over, wherever it is over it (WP-1032).  One index
   *  here rather than one per panel, because "which line is this" is a question
   *  about the session, and two copies would be two answers. */
  let hoveredPeak = $state<number | null>(null);
  /** Which candidate's predicted lines the plot draws (WP-1211).
   *
   *  Two indices, not one, because a preview and a selection are different
   *  claims: `pickedCandidate` is the row a person opened and `previewCandidate`
   *  the row the pointer happens to be over, which outranks it only while it
   *  lasts.  One collapsed index would make leaving a row un-select the cell
   *  underneath it. */
  let pickedCandidate = $state<number | null>(null);
  let previewCandidate = $state<number | null>(null);
  const shownCandidate = $derived(previewCandidate ?? pickedCandidate);
  /** Predicted positions per candidate index, fetched once each.
   *
   *  A cache and not a fetch-per-render because the preview above fires on
   *  every row the pointer crosses, and the answer is a pure function of a
   *  candidate that cannot change while it holds an index — so the map is
   *  dropped whole whenever a new answer renumbers them. */
  let candidateTicks = $state<Record<number, any>>({});
  const candidateOverlay = $derived.by(() => {
    const i = shownCandidate;
    const answer = i === null ? null : candidateTicks[i];
    if (i === null || !answer) return null;
    const cell = indexAnswer?.result?.candidates?.[i]?.cell;
    return {
      label: cell ? cellText(cell) : `candidate ${i}`,
      two_theta: answer.two_theta ?? [],
      n_total: answer.n_total ?? (answer.two_theta?.length ?? 0),
      // parallel to the positions and drawn by nothing — the readout strip
      // names the line under the pointer with them (WP-1213)
      hkl: answer.hkl ?? [],
      line: answer.line ?? [],
    };
  });
  /** Whether the *selection* has lines to show, which is what licenses clearing
   *  the plot to the data — not `pickedCandidate !== null` on its own.
   *
   *  A selection whose fetch is still in flight, or that the route refused
   *  (`INDEX_CELL_TOO_LARGE`, a lattice group gemmi will not build), would
   *  otherwise take the model curves off and put nothing in their place: the
   *  plot goes blank with no lines and no sentence saying why.  Keyed on the
   *  *picked* index and not on `candidateOverlay`, so a hover preview that
   *  fails cannot strobe the curves back on over a selection that is drawing. */
  const candidatePicked = $derived(
    pickedCandidate !== null && Boolean(candidateTicks[pickedCandidate]));
  /** the last refusal from a settings patch, in the verb's own words — held
   *  beside the boxes that caused it rather than scrolled away in the console */
  let protocolError = $state("");

  /** What is being fitted (WP-1033), rebuilt from the document on every change.
   *  A *derived* object rather than plot state: `project.json` is the authority,
   *  and the plot is drawing it, not holding an opinion about it. */
  const protocol = $derived({
    limits: (project?.doc?.two_theta_limits ?? null) as [number, number] | null,
    regions: (project?.doc?.excluded_regions ?? []) as [number, number][],
  });
  const extent = $derived((project?.data?.two_theta_range ?? null) as [number, number] | null);
  /** the source's emission lines, primary first — what the plot's readout needs
   *  for `d = λ/(2 sin θ)` and for naming which line a candidate tick is
   *  (WP-1213).  Off the settings document, so it is the *instrument's* λ and
   *  not the one the peak picker happened to run at. */
  const wavelengths = $derived((project?.data?.wavelengths ?? null) as number[] | null);
  const channels = $derived(project
    ? ([project.data.n_fitted ?? project.data.n_points,
        project.data.n_points] as [number, number])
    : null);

  const busy = $derived(run?.state !== "idle");
  /** The fit's own statistics, and the run frame's only *while it is running*.
   *
   * The frame is how a live Rwp reaches the header before a result exists — but
   * it outlives the result it described: an edit discards the curves server-side
   * (`refine.set_values`, "the fitted curve and statistics described the *old*
   * values"), and the header went on printing the last run's Rwp beside a plot
   * saying "No fitted curves yet".  Two panels contradicting each other, which
   * is precisely what putting the editor beside the plot makes visible (found in
   * WP-1034's browser pass). */
  const rwp = $derived(result?.statistics?.rwp ?? (busy ? run?.run?.rwp ?? null : null));
  const gof = $derived(result?.statistics?.gof ?? (busy ? run?.run?.gof ?? null : null));
  /** The report's own maturity gate, quoted rather than re-derived — see the
   *  header below and `GuiSession.result`. */
  const immature = $derived(Boolean(result?.maturity?.immature));
  // the head is the working state (WP-1005), so it is the one signal that says
  // "the table moved" whether a run, a checkout or an edit moved it
  const head = $derived(run?.head ?? project?.head ?? null);
  /**
   * A project with no phase cannot be refined (WP-1207), and every control that
   * would start one says so rather than offering a click whose only outcome is
   * a 400 — the wizard's `blocked()` rule, one panel up.
   */
  const noPhases = $derived(!!project && (project.n_phases ?? 1) === 0);
  const NO_PHASES_REASON =
    "This project has no phase yet. Pick peaks and index them, then adopt a cell.";

  function say(line: string) {
    lines = [...lines.slice(-400), line];
  }

  /** The `ui` keys this frontend owns, read back off the document it saved them
   *  to — one place, so a new key cannot be persisted and then never restored.
   *
   *  The theme is **not** among them and that is the point (WP-1044): these are
   *  facts about a project (it has four phases, so the table wants to be wide),
   *  and re-reading a theme per project is what made choosing dark last until
   *  the next `Open…`. It lives in `/api/settings`, loaded once at boot. */
  function readUi() {
    simple = project?.doc?.ui?.simple ?? true;
    // Absent means "not dismissed yet", so a project made before this existed
    // gets the strip once. Only `false` hides it (WP-1017).
    firstRun = project?.doc?.ui?.first_run !== false;
    consoleHeight = project?.doc?.ui?.console_height ?? 150;
    sideWidth = project?.doc?.ui?.side_width ?? null;
    modelColumns = project?.doc?.ui?.model_columns ?? null;
  }

  /** Persist a `ui` key on the verb, not on a later save (WP-1005/1008). */
  async function setUi(patch: Record<string, unknown>) {
    if (!project) return;
    try {
      project = await api.patchProject({ ui: patch });
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** What is fitted, from the plot (WP-1033) — the same route `ui` takes, and
   *  the reason `api.patchProject` stops being a `{ui: …}`-only call site.
   *
   *  It goes through the shell rather than the panel for the reason every peak
   *  verb does: the Plot stays presentation, and the console echo of the Python
   *  call belongs beside every other one.  The refusal is *held* rather than
   *  toasted, because it is about a value still on screen in a box — the user
   *  needs it while they retype. */
  async function setProtocol(patch: Record<string, unknown>) {
    if (!project) return;
    try {
      const doc = await api.patchProject(patch);
      if ("two_theta_limits" in patch) {
        const limits = patch.two_theta_limits as number[] | null;
        say(`project.doc.two_theta_limits = ${limits ? `(${limits.join(", ")})` : "None"}`);
      }
      if ("excluded_regions" in patch) {
        const regions = patch.excluded_regions as number[][];
        say(`project.set_excluded_regions(${JSON.stringify(regions)})`);
      }
      // the peak plot's raw pattern is masked by the same document, so its
      // payload is stale the moment this lands (`GuiSession._peaks_pattern`)
      const peaks = peaksData ? await readPeaks() : undefined;
      // …and both land in one flush, which is what makes an exclude drag one
      // paint instead of two: assigning the document and then awaiting the peak
      // list put the two on either side of a microtask, so the plot redrew once
      // for the shading and again for the markers (WP-1212, measured).
      project = doc;
      if (peaks !== undefined) peaksData = peaks;
      protocolError = "";
    } catch (error) {
      protocolError = (error as Error).message;
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** Leave the open project's pending edits behind as its recovery copy, and
   *  clear them from the panels, which stay mounted across an open: without
   *  this, one project's pending values were the next project's Apply. */
  async function leaveEdits() {
    await recoveryWriter.flush();
    recoveryWriter.disarm();
    offer = null;
    paramsPanel?.revert();
    interactivePanel?.revert();
  }

  /** Offer the open project's kept edits, or start keeping new ones. */
  async function offerRecovery() {
    const path = project?.path;
    if (!path) return;
    recoveryWriter.disarm();
    let kept: any = null;
    try {
      kept = await api.recovery();
    } catch {
      // an unreadable copy is no copy: the open goes on, and the next edit
      // writes a good one
    }
    if (project?.path !== path) return;   // another project opened meanwhile
    const draft = readDraft(kept?.draft);
    if (draft) {
      offer = { path, draft, savedUtc: kept.saved_utc ?? null,
                moved: !!kept.head && kept.head !== kept.head_now };
      return;
    }
    recoveryWriter.arm(path, null);
  }

  function restoreKept() {
    const o = offer;
    if (!o) return;
    offer = null;
    if (o.draft.params) paramsPanel?.restoreDraft(o.draft.params);
    if (o.draft.interactive) interactivePanel?.restoreDraft(o.draft.interactive);
    if (o.draft.plan) planPanel?.restoreDraft(o.draft.plan);
    // the server holds exactly this, so it is not written again until it changes
    recoveryWriter.arm(o.path, o.draft);
    say(`# ${o.draft.count === 1 ? "1 unapplied edit" : `${o.draft.count} unapplied edits`} restored`);
  }

  async function discardKept() {
    const o = offer;
    if (!o) return;
    offer = null;
    try {
      await api.putRecovery(o.path, null, null);
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
      // the server still holds the copy: arm as if it does, and ask again
      if (project?.path === o.path) {
        recoveryWriter.arm(o.path, o.draft);
        recoveryWriter.schedule(o.path, head, null);
      }
      return;
    }
    if (project?.path === o.path) recoveryWriter.arm(o.path, null);
  }

  /** Escape on the offer (the maintainer's ruling of 2026-11-10): neither
   *  restored nor discarded.  The copy stays on the server and is offered at
   *  the project's next open, so the writer stays disarmed until then: an
   *  edit made meanwhile would otherwise overwrite the copy it set aside. */
  function setAsideKept() {
    const o = offer;
    if (!o) return;
    offer = null;
    say("# unapplied edits kept; offered again when the project next opens");
  }

  /** The page is going: send the write the timer was holding, with
   *  `keepalive`, which a timer cannot outlive. */
  function pageHidden() {
    const unsent = recoveryWriter.takeUnsent();
    if (unsent) api.putRecoveryOnHide(unsent.project, unsent.head, unsent.draft);
  }

  async function loadProject() {
    try {
      project = await api.project();
      readUi();
      openError = "";
    } catch (error) {
      project = null;
      if (error instanceof ApiError && error.code === "NO_PROJECT") {
        await loadRecent();
        await loadExamples();
      } else {
        openError = (error as Error).message;
      }
    }
  }

  async function loadResult() {
    try {
      result = (await api.result()).result;
      resultError = "";
      plotKey += 1; // the curves moved: tell the plot to fetch them again
    } catch (error) {
      result = null;
      // NO_RESULT is an empty state, not a failure: a fresh project has no
      // curves, and a `checkout` throws the last fit's away on purpose.
      resultError = error instanceof ApiError && error.empty ? "" : (error as Error).message;
    }
  }

  /** The import wizard created one: adopt it without a reload (WP-1014).
   *
   * `project_new` answers with the same document `GET /api/project` would, so
   * there is nothing to refetch — and the panels below all key off `head`, which
   * the new project's root node supplies.
   */
  async function opened(doc: any) {
    await leaveEdits();
    project = doc;
    opens += 1;
    readUi();
    openError = "";
    startOpen = false;
    newOpen = false;
    // a different project, so the checklist's session-local step starts over
    // (WP-1017) — this belongs with `tab = "params"` rather than in `readUi`,
    // which `moved()` also calls on every head move: reset there, reading the
    // report and then running a stage would un-tick it
    reportSeen = false;
    tab = "params";
    indexAnswer = null;
    forgetCandidates();
    extinction = null;
    say(`# project: ${doc.path}`);
    run = await api.runState();
    await loadResult();
    await loadPeaks();
    await offerRecovery();
  }

  /** Open another project **in place of** this one (WP-1034).
   *
   * There is nothing to warn about and nothing to save: settings persist on the
   * verb and the history log is already on disk (WP-1005), so the session's
   * project is simply replaced — and a run in flight makes `project_open` 409
   * before any of this, which is where that rule belongs.  Returns the refusal
   * rather than only storing it, because the wizard's own list needs it beside
   * the button that was clicked; every `Project.open` refusal names a different
   * remedy, so it travels verbatim.
   */
  async function open(path: string): Promise<string> {
    await recoveryWriter.flush();
    try {
      const doc = await api.openProject(path);
      await leaveEdits();
      project = doc;
      opens += 1;
      readUi();
      openError = "";
      startOpen = false;
      reportSeen = false;   // a different project — see `opened` (WP-1017)
      tab = "params";
      indexAnswer = null;
      forgetCandidates();
      extinction = null;
      await loadResult();
      await loadPeaks();
      say(`project.open(${path})`);
      await offerRecovery();
      return "";
    } catch (error) {
      openError = (error as Error).message;
      return openError;
    }
  }

  /** A rename or a move from the File menu (WP-2133): the same project, at a
   *  new path, its result and panels kept, since the server kept them too. */
  function relocated(doc: any) {
    // the server re-keyed the kept copy; the writer follows it there
    recoveryWriter.follow(doc.path);
    project = doc;
    say(`# project: ${doc.path}`);
  }

  /** Close from the File menu (WP-2133): the start screen is the window. */
  async function closed() {
    await leaveEdits();
    project = null;
    result = null;
    startOpen = false;
    newOpen = false;
    indexAnswer = null;
    forgetCandidates();
    extinction = null;
    run = await api.runState();
    await loadRecent();
    await loadExamples();
  }

  /** The recent list, which the start screen reads (WP-2131). */
  async function loadRecent() {
    try {
      recent = (await api.recent()).recent ?? [];
    } catch {
      recent = [];   // an unreadable state directory is an empty list, not an error
    }
  }

  /** The examples this build ships (WP-1204), fetched beside the recent list.
   *
   * Same shape and the same reason: the shell owns the fetch because opening
   * one is the shell's verb.  A build with no examples is an empty list, not
   * an error — the section simply does not appear. */
  async function loadExamples() {
    try {
      examples = (await api.examples()).examples ?? [];
    } catch {
      examples = [];
    }
  }

  /** Open an example, building it on first use.
   *
   * Ends in the same document `openProject` returns, so it adopts through the
   * same path — an example is a project like any other from the moment it
   * exists.  Returns the refusal for the button that was clicked, as `open`
   * does, and refreshes the list because `built` has just changed. */
  async function openExample(name: string, reset = false): Promise<string> {
    // a write still on the timer lands first: after a reset it would
    // otherwise re-create the copy the server has just discarded (WP-2209)
    await recoveryWriter.flush();
    try {
      const doc = reset ? await api.resetExample(name) : await api.openExample(name);
      await opened(doc);
      await loadExamples();
      say(`project.open("${doc.path}")  # ${name} example`);
      return "";
    } catch (error) {
      openError = (error as Error).message;
      return openError;
    }
  }

  /** Take a project off the recent list; the list comes back whole. */
  async function removeRecent(path: string) {
    try {
      recent = (await api.removeRecent(path)).recent ?? [];
    } catch (error) {
      openError = (error as Error).message;
    }
  }

  async function start() {
    try {
      run = await api.run({ kind: "fit" });
      say("ref.fit(data, plan=…)");
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  async function runStage(stage: any, echo?: string) {
    try {
      run = await api.run({ kind: "stage", stage });
      if (echo) say(echo);
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** Apply the Parameters panel's pending edits from the action bar. A refusal
   *  is drawn in that panel, so a refused apply brings it forward: from another
   *  tab it would otherwise be a press that did nothing visible. */
  async function applyParams(): Promise<boolean> {
    const ok = !!(await paramsPanel?.apply());
    if (!ok) tab = "params";
    if (!ok) return false;
    // the slider values second, so a slider wins a path both panels touched;
    // each panel's apply is its own node, as its own Apply always was
    const slid = !!(await interactivePanel?.apply());
    if (!slid) tab = "interactive";
    return slid;
  }

  /** Apply everything the action bar counts: the Parameters edits and the
   *  Interactive values (WP-2128), then an edited plan (WP-2127).  A refusal
   *  brings forward the tab that drew it. */
  async function applyPending(): Promise<boolean> {
    if (touched && !(await applyParams())) return false;
    if (planPending && !(await planPanel?.save())) {
      tab = "plan";
      return false;
    }
    return true;
  }

  function revertPending() {
    paramsPanel?.revert();
    interactivePanel?.revert();
    planPanel?.revert();
  }

  /** A stage run from the Plan tab applies the Parameters and Interactive
   *  edits first, as the bar's Refine does, so the stage starts from the values
   *  on screen.  The stage itself is sent as it stands, saved or not. */
  async function runPlanStage(stage: any) {
    if (refining || busy || noPhases || pendingInvalid) return;
    refining = true;
    try {
      if (touched && !(await applyParams())) return;
      await runStage(stage);
    } finally {
      refining = false;
    }
  }

  /** The action bar's primary: apply the pending edits, then refine (WP-2123).
   *
   * `cycle` is one stage with an empty `turn_on`, which `Project.run_stage`
   * runs on the working free set — exactly what is ticked, because a stage
   * keeps a hand-freed row where a plan drops it (WP-1208). `plan` is the
   * project's plan, the header's old Run. A refused apply runs nothing: the
   * refusal is in the Parameters panel, in the verb's own words.
   *
   * `refining` covers the apply's round trip, before `busy` can say a run is
   * in flight, so a second press in that window starts nothing twice. */
  let refining = false;
  async function refine(mode: "cycle" | "plan" = refineMode) {
    if (refining || busy || noPhases || pendingInvalid) return;
    refining = true;
    try {
      if (pendingTotal && !(await applyPending())) return;
      if (mode === "plan") await start();
      else await runStage({ name: "cycle", turn_on: [] },
                          'ref.run_stage(Stage("cycle", turn_on=[]))');
    } finally {
      refining = false;
    }
  }

  /** Hide or show one side; the other always stays. */
  function toggleSide(which: "graphs" | "model") {
    if (which === "graphs") {
      if (!hideGraphs && hideModel) return;
      hideGraphs = !hideGraphs;
    } else {
      if (!hideModel && hideGraphs) return;
      hideModel = !hideModel;
    }
  }

  async function cancel() {
    try {
      run = await api.cancel();
      say("token.cancel()");
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** The peak list, refetched whole — cheap, and the payload every peak verb
   *  already answers with, so a verb's caller passes it here instead. */
  async function loadPeaks() {
    peaksData = await readPeaks();
  }

  /** The peak list read but not yet published — the caller says when.
   *
   *  Split out of `loadPeaks` so a verb that changes two things can land both
   *  in one flush: a `$state` assignment before an `await` and another after it
   *  are two flushes, and every effect downstream runs twice (WP-1212). */
  async function readPeaks(): Promise<PeaksPayload | null> {
    try {
      return await api.peaks();
    } catch (error) {
      if (!(error instanceof ApiError && error.empty)) {
        say(`peaks: ${(error as Error).message}`);
      }
      return null;
    }
  }

  /** One plot gesture → one verb → one console echo — the same round trip the
   *  panel's own buttons make, kept here so the Plot stays presentation. */
  async function peakVerb(work: () => Promise<PeaksPayload>) {
    try {
      const payload = await work();
      if (payload.api_call) say(payload.api_call);
      peaksData = payload;
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  const addPeak = (tt: number) => peakVerb(() => api.addPeak(tt));
  const movePeak = (i: number, tt: number) => peakVerb(() => api.movePeak(i, tt));
  const togglePeak = (i: number) => {
    const row = peaksData?.peaks?.find((p) => p.index === i);
    if (row) peakVerb(() => api.flagPeak(i, { use_for_indexing: !row.usable }));
  };
  /** Right-click on a marker removes it (WP-1032).  Refit stays on the Peaks
   *  table's `↻`, and the `window.prompt` for a component count went with it:
   *  a modal on the one pointer gesture with no undo, for a verb another
   *  control already carried. */
  const removePeak = (index: number) => peakVerb(() => api.removePeak(index));

  async function loadIndexAnswer() {
    try {
      indexAnswer = await api.indexResult();
      extinction = null; // new candidates, new numbering — the server 409s too
      forgetCandidates();
    } catch {
      // NO_INDEX_RESULT — nothing has run in this session; an empty state
    }
  }

  /** Which numbering `candidateTicks` is keyed to.  A plain `let`, not `$state`:
   *  nothing renders it, and a reactive one would make every fetch a reason to
   *  re-render the shell. */
  let candidateEra = 0;

  /** Drop everything keyed by candidate index (WP-1211).
   *
   *  Whole-map, never per entry: an index is only a name while one answer
   *  holds, so keeping any of it across a renumbering would draw one cell's
   *  lines under another cell's row.  The same staleness the server enforces on
   *  the extinction screen. */
  function forgetCandidates() {
    candidateEra += 1;
    candidateTicks = {};
    inFlightCandidates.clear();
    pickedCandidate = null;
    previewCandidate = null;
  }

  /** The indices a fetch is already out for.  The cache above only dedupes once
   *  an answer is *back*, and the route is a whole `generate_reflections`
   *  enumeration per emission line — so a pointer crossing a row twice before
   *  the first answer lands would ask for it twice.  A plain `Set`, not
   *  `$state`: nothing renders it. */
  const inFlightCandidates = new Set<number>();

  /**
   * Show one candidate's predicted lines, fetching them the first time.
   *
   * The fetch is by index and the answer is cached under it, because the
   * preview fires on every row the pointer crosses. A failure is *silent* here
   * and that is deliberate: this is a drawing, asked for by a hover, and the
   * one refusal it can meet (`INDEX_CELL_TOO_LARGE`) is already visible as the
   * absence of lines beside a cell whose own volume says why.
   *
   * **An answer that outlived its numbering is dropped**, which is the text
   * pane's stale-`seq` rule one panel over: an indexing run can finish while a
   * hover's fetch is in flight, and index 3 then names a different cell than
   * the one that was asked for. Silence is the right outcome — the row is gone
   * too.
   */
  async function showCandidate(index: number | null) {
    if (index === null || candidateTicks[index]
        || inFlightCandidates.has(index)) return;
    const era = candidateEra;
    inFlightCandidates.add(index);
    try {
      const answer = await api.candidateTicks(index);
      if (era === candidateEra) candidateTicks = { ...candidateTicks, [index]: answer };
    } catch {
      // no lines to draw; the row and the plot simply stay as they are
    } finally {
      if (era === candidateEra) inFlightCandidates.delete(index);
    }
  }

  async function loadExtinction() {
    try {
      extinction = await api.extinctionResult();
    } catch {
      // NO_EXTINCTION_RESULT — none run, or cleared by a new indexing run
      extinction = null;
    }
  }

  /** A panel moved the head without running: refetch the result.
   *
   * Needed because a `checkout` **discards the fitted curves** server-side — they
   * described the values it just replaced — and the shell otherwise keeps showing
   * a plot of a state the project is no longer in.  Not an `$effect` on `head`: a
   * `set_vary` moves the head too and keeps the result, and refetching there would
   * throw away the plot's zoom on every parameter edit.
   */
  async function moved() {
    zoom = null;
    // the document too, not only the curves: a move can add or remove the
    // project's last phase (Adopt, a structure replace, a checkout across
    // either), and `n_phases` is what disables Run (WP-1207)
    await loadProject();
    await loadResult();
  }

  /** `POST /api/report/apply` came back: a stage is running for a suggestion. */
  function absorbApply(payload: any) {
    if (payload === null) {
      applied = null;
      return;
    }
    run = payload;
    applied = {
      kind: payload.applied.kind,
      chi2_before: payload.chi2_before,
      predicted: payload.applied.expected_delta_chi2,
      undo: payload.undo,
    };
    say(payload.api_call);
  }

  async function setSimple(next: boolean) {
    simple = next;
    await setUi({ simple: next });
    say(`project.doc.ui["simple"] = ${next ? "True" : "False"}`);
  }

  /** Dismiss the first-run checklist, for this project (WP-1017). */
  async function dismissFirstRun() {
    firstRun = false;
    await setUi({ first_run: false });
    say('project.doc.ui["first_run"] = False');
  }

  async function setConsoleHeight(next: number) {
    consoleHeight = next;
    await setUi({ console_height: next });
  }

  function nextTheme(): ThemeChoice {
    return THEME_CHOICES[(THEME_CHOICES.indexOf(themeChoice) + 1) % THEME_CHOICES.length];
  }

  /** The app's own `ui` keys — the person's, not a project's (WP-1044).
   *
   *  Applied before it is sent, and a refusal costs the *persistence* rather
   *  than the choice: the state directory may be read-only (the server treats
   *  it the same way, `settings_patch`), and a theme that snapped back because
   *  a home directory is not writable would be a worse answer than a quiet one.
   */
  async function setTheme(next: ThemeChoice) {
    themeChoice = next;
    try {
      await api.patchSettings({ theme: next });
      say(`session.settings_patch({"ui": {"theme": ${JSON.stringify(next)}}})`);
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    }
  }

  /** Every splitter reports live and persists once — `done` is the round trip. */
  function sideSized(next: number, done: boolean) {
    sideWidth = next;
    if (done) setUi({ side_width: next });
  }

  /** The sash's double-click: back to the CSS clamp, as nobody having said. */
  function resetSide() {
    sideWidth = null;
    setUi({ side_width: null });
  }

  function modelSized(next: number[], done: boolean) {
    modelColumns = next;
    if (done) setUi({ model_columns: next });
  }

  /** Show the start screen, from anywhere: the header button, the palette.
   *
   * Over an open project it is a screen of its own with a way back, so the
   * project's panels stay mounted behind it and lose nothing (WP-2131). The
   * lists are refetched, because another window may have moved them. */
  function startImport() {
    startOpen = true;
    loadRecent();
    loadExamples();
  }

  const commands = $derived<Command[]>([
    // the action bar's primary on the staged plan, so pending edits are applied
    // first, as that button applies them (WP-2123)
    { id: "run", label: pendingTotal ? "Apply the edits and run the fit" : "Run the fit",
      echo: "ref.fit(data, plan=…)", key: "r",
      disabled: busy || !project || noPhases || !!pendingInvalid, run: () => refine("plan") },
    { id: "stage", label: `Run one stage${planPanel?.selectedName() ? ` — ${planPanel.selectedName()}` : ""}`,
      echo: "ref.run_stage(stage)", key: ".",
      disabled: busy || !project || noPhases || !!pendingInvalid,
      run: () => { tab = "plan"; planPanel?.runStage(); } },
    { id: "plan-undo", label: "Undo the last plan edit", echo: "# the Plan tab's own undo",
      disabled: !project || !planPanel?.canUndo(),
      run: () => { tab = "plan"; planPanel?.undo(); } },
    { id: "plan-redo", label: "Redo the plan edit", echo: "# the Plan tab's own undo",
      disabled: !project || !planPanel?.canRedo(),
      run: () => { tab = "plan"; planPanel?.redo(); } },
    { id: "cancel", label: "Cancel the run", echo: "token.cancel()", key: "Esc",
      disabled: !busy, run: cancel },
    { id: "free", label: "Free the filtered parameters", echo: 'ref.set_vary(glob, True)',
      key: "f", disabled: busy || !project,
      run: () => { tab = "params"; paramsPanel?.freeSelection(); } },
    { id: "fix", label: "Fix the filtered parameters", echo: 'ref.set_vary(glob, False)',
      key: "x", disabled: busy || !project,
      run: () => { tab = "params"; paramsPanel?.fixSelection(); } },
    { id: "filter", label: "Filter parameters", echo: "ref.parameters()", key: "/",
      disabled: !project, run: () => { tab = "params"; setTimeout(() => paramsPanel?.focusFilter(), 0); } },
    { id: "peaks", label: "Show the peak picker", echo: "session.pick_peaks()", key: "p",
      disabled: !project, run: () => (tab = "peaks") },
    { id: "index", label: "Run indexing", echo: "index_pattern(peaks, data=…, instrument=…)",
      disabled: busy || !project || !peaksData?.peaks?.length,
      run: async () => { tab = "peaks"; try { await api.index(); say("index_pattern(peaks, data=…, instrument=…)"); } catch (e) { say(`refused: ${(e as Error).message}`); } } },
    { id: "series", label: "Refine a series of patterns",
      echo: "refine_sequential(patterns, structure, instrument, x=…)",
      disabled: !project || noPhases, run: () => (tab = "series") },
    { id: "report", label: "Show the fit report", echo: "ref.report()", key: "?",
      disabled: !project, run: () => (tab = "report") },
    { id: "history", label: "Show the history", echo: "ref.history.summary()", key: "h",
      disabled: !project, run: () => (tab = "history") },
    { id: "text", label: "Edit the project as text",
      echo: "print(rietx.gui.textdoc.render(project))", key: "t", disabled: !project,
      run: () => (tab = "text") },
    { id: "model", label: "Edit the structure and instrument",
      echo: "ref.edit(structure=…, instrument=…)", key: "m", disabled: !project,
      run: () => (tab = "model") },
    { id: "graphs", label: hideGraphs ? "Show the graphs" : "Hide the graphs",
      echo: "# a layout choice, not a setting", disabled: !project || hideModel,
      run: () => toggleSide("graphs") },
    { id: "side", label: hideModel ? "Show the model panel" : "Hide the model panel",
      echo: "# a layout choice, not a setting", disabled: !project || hideGraphs,
      run: () => toggleSide("model") },
    { id: "cycle", label: "Refine one cycle on the ticked parameters",
      echo: 'ref.run_stage(Stage("cycle", turn_on=[]))',
      disabled: busy || !project || noPhases || !!pendingInvalid,
      run: () => refine("cycle") },
    { id: "import", label: "Open or create a project", echo: "Project.create(path, …)",
      run: startImport },
    { id: "disclosure", label: simple ? "Show advanced controls" : "Hide advanced controls",
      echo: 'project.doc.ui["simple"]', disabled: !project, run: () => setSimple(!simple) },
    // no `disabled`: the theme is the person's, so it is reachable in the empty
    // state too — which is the one screen a first-time user starts on
    { id: "theme", label: `Theme: ${themeChoice} — switch to ${nextTheme()}`,
      echo: 'session.settings_patch({"ui": {"theme": …}})',
      run: () => setTheme(nextTheme()) },
    { id: "save", label: "Save the project", echo: "project.save()", disabled: !project,
      run: async () => { await api.save(); say("project.save()"); } },
  ]);

  function keydown(event: KeyboardEvent) {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      paletteOpen = !paletteOpen;
      return;
    }
    // while the palette is open it owns the keyboard — Esc closes it there, and
    // `r` would otherwise start a fit from inside a search box
    if (paletteOpen) return;
    // ⌘⏎ is the action bar's primary (WP-2123), except inside the text pane,
    // whose CodeMirror keymap binds the same chord to its own Apply
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      const inText = (event.target as HTMLElement | null)?.closest?.(".cm-editor");
      if (!inText && project) {
        event.preventDefault();
        refine();
      }
      return;
    }
    // help first: Esc means "close the thing that just opened", and cancelling
    // a run because a popover was open is not recoverable by pressing it again
    if (event.key === "Escape" && helpRequest) {
      closeHelp(true);
      return;
    }
    if (event.key === "Escape" && busy) {
      cancel();
      return;
    }
    if (!isShortcutTarget(event)) return;
    const command = commands.find((entry) => entry.key === event.key);
    if (command && !command.disabled) {
      event.preventDefault();
      command.run();
    }
  }

  /* ---- the help popover (WP-1203) -------------------------------------
   *
   * One instance for the whole app, anchored to whichever `<Help>` term was
   * last activated.  One rather than one-per-term because two open
   * explanations is a state nobody asked for, and because the popover has to
   * escape every panel's `overflow: auto` — it is `position: fixed` in
   * viewport coordinates, which is exactly what `getBoundingClientRect`
   * returns and what `lib/help.ts:place` consumes.
   *
   * The size is *measured* rather than declared: the flip decision needs the
   * rendered height, and a max-width in CSS plus a paragraph of prose is not a
   * height anything here could compute.  The effect that measures runs after
   * the DOM update and before the browser paints, so the correction is not a
   * frame the eye can see; under jsdom every measurement is zero, which is why
   * the arithmetic is tested in `lib/help.test.ts` and not here. */
  let helpNode = $state<HTMLElement | null>(null);
  let helpRequest = $state<HelpRequest | null>(null);
  let helpAnchor = $state<DOMRect | null>(null);
  let popoverEl = $state<HTMLElement | null>(null);
  let popoverSize = $state({ width: 0, height: 0 });
  let viewport = $state({ width: 1024, height: 768 });

  const helpEntry = $derived(
    helpRequest?.key ? resolve(corpus, helpRequest.key) : null);
  const helpLink = $derived(manualUrl(corpus, helpEntry));
  const helpTitle = $derived(
    helpEntry?.title ?? helpRequest?.title ?? helpRequest?.key ?? "");
  const helpBody = $derived(helpEntry?.description ?? helpRequest?.text ?? "");
  /** the name behind a labelled term: a chip says `at bound`, and the flag it
   *  stands for is `position_at_bound`, which nothing else on screen shows
   *  (WP-1209) — so the popover carries it, and only where a label hid it:
   *  `excluded` labelled `excluded` hid nothing */
  const helpCode = $derived.by(() => {
    const name = helpRequest?.key ? splitKey(helpRequest.key)?.name ?? null : null;
    return helpEntry?.label && name && helpEntry.label !== name ? name : null;
  });
  const placement = $derived(helpAnchor
    ? place(helpAnchor, viewport, popoverSize)
    : { left: 0, top: 0, flipped: false });

  /** `refocus` is the caller's claim (Esc); holding focus is the popover's own.
   *
   *  A click away must not steal focus back from whatever was clicked, so the
   *  second test is `contains(activeElement)` rather than "was open": the only
   *  time closing owes the term its focus is when the popover had it, which
   *  since the popover takes focus on open is every keyboard route out. */
  function closeHelp(refocus = false) {
    const held = popoverEl?.contains(document.activeElement) === true;
    if (refocus || held) helpNode?.focus({ preventScroll: true });
    helpNode = null;
    helpRequest = null;
    helpAnchor = null;
    popoverSize = { width: 0, height: 0 };
    focusedFor = null;
  }

  setContext<HelpOpener>(HELP_CONTEXT, {
    isOpen: (node) => helpNode === node,
    toggle(node, request) {
      if (helpNode === node) {
        closeHelp();
        return;
      }
      helpNode = node;
      helpRequest = request;
      helpAnchor = node.getBoundingClientRect();
      popoverSize = { width: 0, height: 0 };
    },
  });

  $effect(() => {
    if (!popoverEl || !helpRequest) return;
    // the *rendered* body, not only the request: what `place` flips on is the
    // height, and the height is whatever is drawn.  Today that is the same
    // thing — `onMount` awaits `api.help()` before `loadProject`, so no term
    // exists until the corpus has landed or failed, and holding `/api/help`
    // for 15 s in a browser produced no term to click.  Declared here, that
    // boot order stops being load-bearing: a corpus arriving late would grow
    // the body under a height measured from "Not described yet.", and this
    // effect would re-measure rather than leaving `place` a stale number.
    void [helpTitle, helpBody, helpEntry, helpLink];
    const width = popoverEl.offsetWidth;
    const height = popoverEl.offsetHeight;
    if (width !== popoverSize.width || height !== popoverSize.height) {
      popoverSize = { width, height };
    }
  });

  /* The popover takes focus, because it is a `role="dialog"` and a dialog
   * nobody is in announces nothing: Tab from an activated term went to the next
   * input in the row, leaving the popover open behind the cursor and its
   * `in the manual →` link reachable only by tabbing the whole app.  Esc and a
   * second activation hand focus back to the term (`closeHelp`).
   *
   * `preventScroll` is load-bearing rather than tidy — `onscrollcapture` closes
   * the popover, so a focus that scrolled anything would close what it just
   * opened.  `focusedFor` is a plain `let`, not `$state`: it must not be a
   * dependency of the effect that writes it. */
  let focusedFor: HTMLElement | null = null;
  $effect(() => {
    if (!popoverEl || !helpNode) return;
    if (focusedFor === helpNode) return;
    focusedFor = helpNode;
    popoverEl.focus({ preventScroll: true });
  });

  // A resize or a scroll moves the anchor out from under the popover, and
  // there is nothing useful to do about it: re-measuring would chase a term
  // that may have left the screen entirely.  Closing is honest and costs one
  // click.
  function reanchor() {
    viewport = { width: window.innerWidth, height: window.innerHeight };
    if (helpRequest) closeHelp();
  }

  /** A click outside the popover and its own term closes it. */
  function clickAway(event: MouseEvent) {
    if (!helpRequest) return;
    const target = event.target as Node | null;
    if (target && (popoverEl?.contains(target) || helpNode?.contains(target))) return;
    closeHelp();
  }

  // "system" has to keep meaning system: a machine that switches at dusk must
  // take the app with it, which is only true if the query is *listened* to
  // rather than read once at boot
  onMount(() => {
    viewport = { width: window.innerWidth, height: window.innerHeight };
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return;
    systemDark = query.matches;
    const listen = () => (systemDark = query.matches);
    query.addEventListener?.("change", listen);
    return () => query.removeEventListener?.("change", listen);
  });

  onMount(() => {
    (async () => {
      version = await api.version();
      capabilities = await api.capabilities();
      // the corpus is static for the life of the build and needs no project,
      // so it is fetched once here beside capabilities.  A failure leaves it
      // null and every term says "not described yet": help is not a reason to
      // fail the boot.
      try {
        corpus = await api.help();
      } catch {
        corpus = null;
      }
      // the person's settings, before the project's: the theme is applied on
      // the first paint rather than after one in the wrong one (WP-1044)
      try {
        themeChoice = readChoice((await api.settings()).ui?.theme);
      } catch {
        // an unreadable store is the default choice, not a boot failure
      }
      await loadProject();
      run = await api.runState();
      await loadResult();
      if (project) {
        await loadPeaks();
        // the session outlives this page: a reload must not lose an indexing
        // answer (or its extinction screen) the server still holds — both
        // loaders treat the 409 empty states as "nothing yet".  Order matters:
        // loadIndexAnswer clears the screen it assumes stale.
        await loadIndexAnswer();
        await loadExtinction();
        await offerRecovery();
      }
    })();

    // The run this shell has already reacted to, as (state, outcome, node).  Keyed
    // on the *outcome* rather than on having seen a `running` frame: the state
    // channel only sends a frame when the coarse frame changes, so a stage that
    // starts and finishes between two frames delivers one idle frame carrying a
    // new status — and a transition test would treat it as nothing having happened
    // and leave the previous fit's curves on screen.  `null` until the first frame,
    // so a reload does not announce the outcome of a run that ended before it.
    let seen: string | null = null;
    return follow(
      (event: EngineEvent) => {
        say(consoleLine(event));
        // the streamed shortlist consumer (WP-1045): a completed system's
        // consensus snapshot is data on an existing kind, never a new one
        if (event.kind === "index_start") indexSnapshots = [];
        else if (event.kind === "stage_end" && event.data?.consensus)
          indexSnapshots = [...indexSnapshots, event.data];
      },
      (frame: RunState) => {
        run = frame;
        const key = `${frame.state}:${frame.run.status ?? ""}:${frame.run.node_id ?? ""}`;
        // a run just ended (any way it ended) → the result and the history moved
        if (seen !== null && key !== seen && frame.state === "idle" && frame.run.status) {
          if (frame.run.kind === "index") {
            // an indexing run commits no node and moves no curves; what it
            // leaves is its answer, adopt verdicts included
            loadIndexAnswer();
            tab = "peaks";
          } else if (frame.run.kind === "extinction") {
            // same shape one rank down: the screen is the whole outcome
            loadExtinction();
            tab = "peaks";
          } else if (frame.run.kind === "series") {
            // a series fits N patterns the project does not own: it moves no
            // curve of *this* project's and commits nothing to its tree, so the
            // outcome is the series panel's answer and nothing else here changes
            seriesPanel?.reload();
            tab = "series";
          } else {
            loadResult();
          }
          if (frame.run.status === "failed") say(`FAILED  ${frame.run.error?.message ?? ""}`);
          if (frame.run.status === "cancelled"
              && frame.run.kind !== "index" && frame.run.kind !== "extinction")
            say(`cancelled at stage ${frame.run.stage} — state stands at ${frame.run.node_id}`);
        }
        seen = key;
      },
      { poll: (since) => api.events(since) },
    );
  });
</script>

<!-- The action bar (WP-2123).  It ends the model panel, and moves to the foot
     of the graphs while that panel is hidden, so a fit can always be started
     from a visible button.  Settled by Claude, reversible: a bar across the
     whole window under both sides is the alternative.  Moving it is part of
     the collapse click, which asks for a layout change. -->
{#snippet actions()}
  <ActionBar bind:mode={refineMode} touched={pendingTotal} invalid={pendingInvalid}
    {busy} blocked={noPhases ? NO_PHASES_REASON : null}
    onapply={applyPending} onrevert={revertPending}
    onrefine={() => refine()} />
{/snippet}

<svelte:window onkeydown={keydown} onclick={clickAway} onresize={reanchor}
  onscrollcapture={reanchor} onpagehide={pageHidden} bind:innerWidth={windowWidth} />

{#if offer}
  <Recovery draft={offer.draft} savedUtc={offer.savedUtc} moved={offer.moved}
    onrestore={restoreKept} ondiscard={discardKept} onlater={setAsideKept} />
{/if}

<!-- The top bar (WP-2123).  Each side's collapse button sits at its own end
     and never moves: the middle wraps within itself, so a narrow window adds
     a row there and leaves both buttons where they were (the maintainer's
     ruling of 2026-11-07, after Xcode and VS Code).  Both are drawn without a
     project too, disabled, so opening one moves nothing. -->
<header>
  <button class="ghost toggle" aria-pressed={!hideGraphs}
    disabled={!project || hideModel} onclick={() => toggleSide("graphs")}
    aria-label={hideGraphs ? "Show the graphs" : "Hide the graphs"}
    title={hideModel ? "the graphs cannot hide while the model panel is hidden"
      : hideGraphs ? "show the graphs" : "hide the graphs"}>
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
      {#if stacked}
        <rect class="fill" x="2" y="3" width="12" height="4.5" /><path d="M1.5 8h13" />
      {:else}
        <rect class="fill" x="2" y="3" width="5" height="10" /><path d="M7.5 2.5v11" />
      {/if}
    </svg>
  </button>

  <div class="bar">
    <div class="title">
      <strong>rietx</strong>
      <span class="muted mono">{version?.package_version ?? "…"}</span>
    </div>

    <!-- the project's name opens the File menu (WP-2133), with or without a
         project, so opening one moves nothing in the bar -->
    <div class="project mono" title={project?.path ?? ""}>
      <FileMenu {project} {busy} hasResult={!!result} {say}
        onnew={() => (newOpen = true)} onopen={open} onproject={relocated}
        onclosed={closed} />
      {#if project}
        <span class="muted">· {project.data.filename} · {project.data.n_points} pts</span>
        <span class="muted">· {project.doc.mode}</span>
        <span class="muted">· σ {project.data.has_sigma ? "from file" : "Poisson"}</span>
      {/if}
    </div>

    <div class="controls">
      {#if project}
        <div class="segmented" role="group" aria-label="disclosure">
          <button class:on={simple} onclick={() => setSimple(true)}
            title="hide bounds and stage seeds">Simple</button>
          <button class:on={!simple} onclick={() => setSimple(false)}
            title="show every field a stage and a parameter carry">Advanced</button>
        </div>
      {/if}
      <!-- outside the `{#if project}` above, because a theme is not the
           project's (WP-1044): the empty state is a screen too, and it is the
           one a first-time user starts on -->
      <div class="segmented theme" role="group" aria-label="theme">
        {#each THEME_CHOICES as choice (choice)}
          <button class:on={themeChoice === choice} onclick={() => setTheme(choice)}
            aria-label={choice} title={THEME_TITLE[choice]}>{GLYPH[choice]}</button>
        {/each}
      </div>
      <span class="pill" data-state={run?.state ?? "idle"}>
        {#if busy}
          {run?.run.stage ?? "starting"}
          {#if run?.run.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
          {#if run?.run.lebail?.pass}· pass {run.run.lebail.pass}{#if run.run.lebail.of} of {run.run.lebail.of}{/if}{/if}
        {:else}
          {run?.run.status ?? "idle"}
        {/if}
      </span>
      <button class="ghost" onclick={cancel} disabled={!busy}>Cancel</button>
      <button class="ghost" onclick={() => (paletteOpen = true)} title="every command, with the call it makes">
        <kbd>⌘K</kbd>
      </button>
    </div>
  </div>

  <button class="ghost toggle" aria-pressed={!hideModel}
    disabled={!project || hideGraphs} onclick={() => toggleSide("model")}
    aria-label={hideModel ? "Show the model panel" : "Hide the model panel"}
    title={hideGraphs ? "the model panel cannot hide while the graphs are hidden"
      : hideModel ? "show the model panel" : "hide the model panel"}>
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
      {#if stacked}
        <rect class="fill" x="2" y="9.5" width="12" height="3.5" /><path d="M1.5 9h13" />
      {:else}
        <rect class="fill" x="9" y="3" width="5" height="10" /><path d="M8.5 2.5v11" />
      {/if}
    </svg>
  </button>
</header>

{#if !busy && run?.run.lebail?.stopped}
  <!-- The alternation's verdict (WP-1323).  It lives on the result's
       diagnostics, which no panel shows, and cannot sit on a history node, so
       the run record carries it.  A row of its own under the header, never a
       span in it: the header is full at ordinary widths and the sentence
       pushed the project's name down to "lebail_…". -->
  <div class="lebail-stop" data-level={run.run.lebail.level} role="status">
    <b>Le Bail alternation</b>
    {run.run.lebail.stopped.replace(/^the Le Bail alternation /, "")}.
    {#if run.run.lebail.suggestion}<span class="muted">{run.run.lebail.suggestion}.</span>{/if}
  </div>
{/if}

<main bind:this={mainEl}>
  <!-- With no project the start screen is the window (WP-2131), and the
       header's Open… lays it over an open project, whose panes stay mounted
       behind it so a look at the recent list throws nothing away. `Model` is
       still mounted exactly once (WP-1205): switching from one project to
       another keeps `project` truthy, so no panel is torn down. -->
  {#if !project || startOpen}
    <Start version={version?.package_version ?? ""} {recent} {examples} {busy}
      docsUrl={corpus?.docs_url ?? null} error={openError} hasProject={!!project}
      onnew={() => (newOpen = true)} onopen={open} onexample={openExample}
      onremove={removeRecent} onback={() => (startOpen = false)} />
  {/if}
  {#if project}
  <div class="panes" class:stacked class:hidden={startOpen}>
    <!-- hidden rather than unmounted in the full-window layout, for the same
         reason every panel is: a purge and a refetch on a layout click would
         throw the drawn window away -->
    {#if project}
      <!-- The graph column (WP-2123): a strip of graph tabs, then a title line
           saying what the view shows, so a later preview can never read as a
           changed fit (the maintainer's ruling of 2026-11-07). The fit's
           statistic rides on that line, moved from the header. -->
      <div class="plotcol" class:hidden={hideGraphs}>
        <nav class="tabs" aria-label="graphs">
          {#each GRAPH_TABS as entry (entry.id)}
            <button class="tab" class:on={graphTab === entry.id}
              onclick={() => (graphTab = entry.id)}>{entry.label}</button>
          {/each}
        </nav>
        <!-- A hopeless fit must not be presented in the register of a good one
             (WP-1029 item c).  The judgement is the *report's* — `maturity`
             quotes `MATURITY_MAX_RWP` — so nothing here decides anything. -->
        <div class="gtitle">
          <strong class="what">{graphTab === "background" ? backgroundTitle(busy)
            : previewAnswer ? "Preview, not refined"
            : busy ? "Refining" : result ? "Last fit" : "Observed pattern"}</strong>
          <div class="stats tabular mono" class:immature={immature}>
            {#if previewAnswer}
              Rwp <strong>{(previewAnswer.curves.header.rwp * 100).toFixed(3)}%</strong>
              {#if rwp !== null}<span class="muted">last fit {(rwp * 100).toFixed(3)}%</span>{/if}
            {:else if previewError}
              <span class="muted">preview refused: {previewError}</span>
            {:else if rwp !== null}
              Rwp <strong>{(rwp * 100).toFixed(3)}%</strong>
              {#if gof !== null}<span class="muted">GoF {gof.toFixed(3)}</span>{/if}
              {#if immature}
                <span class="chip bad">
                  <Help text={result.maturity.message} title="Not a fit yet"
                    >⚠ not a fit yet</Help>
                </span>
              {/if}
            {/if}
          </div>
        </div>
        <!-- each graph stays mounted while another is up, as the panels do -->
        <div class="gview" class:hidden={graphTab !== "pattern"}>
        <Plot {result} {plotKey} {zoom} {theme} error={resultError}
          peaks={peaksData} peaksActive={tab === "peaks"} hovered={hoveredPeak}
          candidate={candidateOverlay} {candidatePicked}
          {protocol} {extent} {channels} {wavelengths} {protocolError} {busy}
          onhoverpeak={(i) => (hoveredPeak = i)}
          onaddpeak={addPeak} onmovepeak={movePeak} ontogglepeak={togglePeak}
          onremovepeak={removePeak} onprotocol={setProtocol}
          preview={previewAnswer} oncurves={(c) => (baseCurves = c)} />
        </div>
        <div class="gview" class:hidden={graphTab !== "single"}>
          <PeakWindows curves={baseCurves} preview={previewAnswer} {theme}
            active={graphTab === "single" && !hideGraphs} />
        </div>
        <div class="gview" class:hidden={graphTab !== "background"}>
          <Background {head} {busy} {theme} {say} onmoved={moved}
            protocol={JSON.stringify([project?.doc?.mode ?? null, protocol.limits,
                                      protocol.regions])}
            active={graphTab === "background" && !hideGraphs} />
        </div>
        {#if hideModel}{@render actions()}{/if}
      </div>
    {/if}
    <div class="side" class:wide={hideGraphs || !project} class:hidden={!!project && hideModel}
      bind:clientWidth={sideMeasured} bind:clientHeight={sideMeasuredHeight}
      style:flex={!project || hideGraphs ? null
        : stacked ? (sideHeight === null ? null : `0 0 ${sideHeight}px`)
        : sideWidth === null ? null : `0 0 ${sideWidth}px`}>
      {#if project && !hideGraphs}
        <!-- one sash, turned by the layout: along the column's left edge side by
             side, along its top edge stacked (WP-2123) -->
        <Splitter size={stacked ? sideHeight ?? sideMeasuredHeight : sideWidth ?? sideMeasured}
          grow={stacked ? "up" : "left"} min={stacked ? 160 : SHELL_MIN.side}
          keep={stacked ? 160 : SHELL_MIN.graphs}
          extent={() => (stacked ? mainEl?.clientHeight : mainEl?.clientWidth) ?? 0}
          onsize={(next, done) => (stacked ? (sideHeight = next) : sideSized(next, done))}
          onreset={() => (stacked ? (sideHeight = null) : resetSide())}
          title="drag to resize the panel column; double-click resets it" />
      {/if}
      {#if project}
        <!-- eight wide, and it **wraps** rather than truncating: measured at
             WP-1034 task 1, eight labels need 415 px squeezed and 533 px whole,
             against a column that clamps at 340 px on a narrow window.  A strip
             that hides a tab is worse than the mode buttons it replaced, so no
             label is ever shortened and the strip takes a second row instead. -->
        {#if firstRun}
          <!-- above the strip and inside the column: it is about what to do
               next, so it sits where the next thing is, and it is dismissible
               rather than modal (WP-1017) -->
          <Checklist hasPhase={!noPhases} hasResult={!!result} {reportSeen} {busy}
            ongo={(next) => (tab = next as Tab)} ondismiss={dismissFirstRun} />
        {/if}
        <nav class="tabs">
          {#each TABS as entry (entry.id)}
            <button class="tab" class:on={tab === entry.id} onclick={() => (tab = entry.id)}
              >{entry.label}</button>
          {/each}
        </nav>
      {/if}
      <!-- the model pane and the text pane are tabs (WP-1034) and stay
           mounted like every other one: a typed species, a half-filled wizard
           and a typed `.rxt` buffer all have to survive a look at the plot.
           `active` is what keeps each from refetching on a head move it is
           not showing, and what builds the CodeMirror editor on first entry —
           and without a project, Model *is* the content, so it is always
           active and never hidden. -->
      <div class="panel" class:hidden={!!project && !modelTab}>
        <Model bind:this={modelPanel} {project} {capabilities} {head} {busy} {simple}
          {theme} {say} active={modelTab} columns={modelColumns}
          oncolumns={modelSized} onmoved={moved} />
      </div>
      {#if project}
        <!-- every tab stays mounted: switching must not throw away a filter, a
             pending edit, an unsaved stage list or a two-node comparison -->
        <div class="panel" class:hidden={tab !== "params"}>
          <Params bind:this={paramsPanel} {head} {busy} {corpus} {say}
            onpending={(n, why) => { pendingTouched = n; pendingInvalid = why; }} />
        </div>
        <div class="panel" class:hidden={tab !== "interactive"}>
          <Interactive bind:this={interactivePanel} {head} {busy} {corpus} {say}
            context={rangeContext} {phaseNames}
            onpending={(n) => (sliderTouched = n)}
            onpreview={(answer, why) => { previewAnswer = answer; previewError = why; }} />
        </div>
        <div class="panel" class:hidden={tab !== "plan"}>
          {#key opens}
            <Plan bind:this={planPanel} mode={project.doc.mode} {head} {busy} {simple}
              noPhasesReason={noPhases ? NO_PHASES_REASON : null}
              {say} onrun={runPlanStage} onpending={(edited) => (planPending = edited)} />
          {/key}
        </div>
        <div class="panel" class:hidden={!textTab}>
          <Text {head} {busy} active={textTab} dark={theme === "dark"} {say} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "peaks"}>
          <Peaks peaks={peaksData} {indexAnswer} {extinction} {run} {busy} {say}
            {capabilities} {corpus} doc={project?.doc ?? null}
            snapshots={indexSnapshots} onproject={loadProject}
            hovered={hoveredPeak} onhover={(i) => (hoveredPeak = i)}
            {shownCandidate}
            oncandidate={(i) => { pickedCandidate = i; showCandidate(i); }}
            oncandidatehover={(i) => { previewCandidate = i; showCandidate(i); }}
            onpeaks={(p) => (peaksData = p)}
            onindexed={(a) => { indexAnswer = a; forgetCandidates(); }}
            onzoom={(lo, hi) => (zoom = [lo, hi])} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={!seriesTab}>
          <Series bind:this={seriesPanel} {project} {run} {busy} {simple} {theme}
            {say} active={seriesTab} />
        </div>
        <div class="panel" class:hidden={tab !== "report"}>
          <Report {head} {busy} {simple} {say} {applied}
            chi2={result?.statistics?.chi2 ?? null}
            diagnostics={result?.diagnostics ?? []}
            onzoom={(lo, hi) => (zoom = [lo, hi])}
            onapplied={absorbApply} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "history"}>
          <History {head} {busy} {say} onmoved={moved} />
        </div>
        <div class="panel" class:hidden={tab !== "build"}>
          <Stubs {capabilities} {project} />
        </div>
        {#if !hideModel}{@render actions()}{/if}
        <Console {lines} {dropped} height={consoleHeight} onresize={setConsoleHeight} />
      {/if}
    </div>
  </div>
  {/if}
</main>

{#if newOpen}
  <NewProject {capabilities} {busy} {say} onclose={() => (newOpen = false)}
    onopened={opened} />
{/if}

{#if paletteOpen}
  <Palette {commands} onclose={() => (paletteOpen = false)} />
{/if}

<!-- The app's one help popover (WP-1203).  It lives here, outside every panel,
     because `position: fixed` inside a scrolling column would still be clipped
     by an ancestor that establishes a containing block, and because two open
     explanations is a state nobody asked for. -->
{#if helpRequest}
  <!-- `data-flipped` is the only way to tell a flip from a clamp that landed on
       the same pixel — a popover taller than the viewport is clamped to the top
       margin, which is exactly where flipping it would also put it — so it is
       what a browser pass reads to check the rule (WP-1203). -->
  <div class="popover" bind:this={popoverEl} role="dialog" aria-label={helpTitle}
       tabindex="-1" data-flipped={placement.flipped}
       style="left: {placement.left}px; top: {placement.top}px">
    <h2>{helpTitle}</h2>
    {#if helpBody}
      <p>{helpBody}</p>
    {:else}
      <!-- a key that resolves to nothing.  Saying so is the honest empty
           state: the corpus is where a description is owed, and inventing one
           here would put a wrong sentence under a real name. -->
      <p class="muted">Not described yet.</p>
    {/if}
    {#if helpEntry && (helpEntry.unit || helpEntry.default || helpEntry.typical
                       || helpEntry.modes?.length || helpCode)}
      <dl>
        {#if helpCode}<dt>Name</dt><dd class="mono">{helpCode}</dd>{/if}
        {#if helpEntry.unit}<dt>Unit</dt><dd>{helpEntry.unit}</dd>{/if}
        {#if helpEntry.default}<dt>Default</dt><dd class="mono">{helpEntry.default}</dd>{/if}
        {#if helpEntry.modes?.length}
          <dt>Modes</dt><dd class="mono">{helpEntry.modes.join(", ")}</dd>
        {/if}
        {#if helpEntry.typical}<dt>Typical</dt><dd>{helpEntry.typical}</dd>{/if}
      </dl>
    {/if}
    {#if helpLink}
      <a class="link" href={helpLink} target="_blank" rel="noreferrer noopener"
        >in the manual →</a>
    {/if}
  </div>
{/if}

<style>
  /* wraps rather than pushing a control off the window's edge — the tab strip's
     rule one rank up.  Measured at 860 px with a fitted project on screen:
     `Cancel` and `⌘K` were 118 px past the right edge and unreachable, because
     the row's only shrinkable item is the filename and it had already
     collapsed to nothing (WP-1034's browser pass). */
  /* The two collapse buttons hold the ends and never wrap (WP-2123); the
     middle `.bar` is what wraps, so a narrow window costs a row there. */
  header {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
    flex: 0 0 auto;
  }

  header > .bar {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 14px;
  }

  .toggle {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    color: var(--muted);
  }

  .toggle svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.4;
  }

  .toggle svg .fill {
    fill: currentColor;
    stroke: none;
    opacity: 0;
  }

  .toggle[aria-pressed="true"] svg .fill {
    opacity: 0.55;
  }

  .title {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  /* the one thing in the header that may be shortened: everything else is a
     control, and a clipped `Advanced` is worse than a clipped filename */
  /* `flex-basis: 0`, not `auto`: with a wrapping header the basis is what
     decides whether the row breaks, and a long filename at its natural width
     would push the controls onto a second row while it still had room to
     ellipsise (measured — the header wrapped at 1200 px for nothing) */
  .project {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    flex: 1 1 0;
    min-width: 0;
  }

  /* The graph's title line (WP-2123): what the view shows, then the fit's
     statistic held to the right.  The title gives way first, with an ellipsis,
     so the statistic never wraps under it. */
  .gview {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .gview.hidden {
    display: none;
  }

  .gtitle {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 4px 12px;
    flex: 0 0 auto;
    min-width: 0;
  }

  .gtitle .what {
    flex: 1 1 0;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    font-weight: 600;
  }

  .stats {
    flex: 0 0 auto;
    display: flex;
    align-items: baseline;
    gap: 6px;
    white-space: nowrap;
  }

  .stats.immature strong {
    color: var(--warn);
  }

  .controls {
    margin-left: auto;
    display: flex;
    /* The header wraps and this did not, so it was one unbreakable 604 px
       line: measured at a 420 px window, the document scrolled to 618 px
       whatever the window was under that (WP-1438). `0 1 auto` lets it give
       ground before it overflows, and then it wraps within itself. */
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    flex: 0 1 auto;
  }

  .lebail-stop {
    padding: 4px 12px;
    font-size: var(--text-sm);
    border-bottom: 1px solid var(--line);
    background: color-mix(in srgb, var(--accent) 8%, var(--panel));
  }
  .lebail-stop[data-level="warning"] {
    background: color-mix(in srgb, var(--warn) 14%, var(--panel));
  }
  .pill[data-state="running"] {
    color: var(--ok);
    border-color: var(--ok);
  }

  .pill[data-state="cancelling"] {
    color: var(--warn);
    border-color: var(--warn);
  }

  main {
    flex: 1 1 auto;
    overflow: hidden;
  }

  .panes {
    display: flex;
    height: 100%;
  }

  .plotcol {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .plotcol.hidden {
    display: none;
  }

  /* one graph tab's view (WP-2128): the column's remaining height, so the
     pattern graph's host sizes exactly as it did before there were two */
  .gview {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .gview.hidden {
    display: none;
  }

  /* The panel column is a *surface*, and says so (WP-1032).
     Reported as "transparent headings clash with other text on scroll"; what is
     actually there is a colour mismatch, measured in both themes.  The Peaks
     table's `th` is the app's only `position: sticky`, and it already paints an
     opaque `var(--panel)` backdrop — over a column that set no background at
     all and therefore showed the body's `--bg`.  Two surfaces, one strip:
     #ffffff on #fbfbfa light, #1e1e1e on #151515 dark, so the header row read
     as a band of a different colour rather than as a backdrop.  Naming the
     column `--panel` — which is what the header bar already is — makes the
     sticky backdrop match the surface it sticks to, and is why no rule here
     needs to know that a table above it is sticky. */
  .side {
    flex: 0 0 clamp(340px, 38%, 560px);
    background: var(--panel);
    border-left: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    min-width: 0;
    /* a stored width outliving the window it was chosen in must not hide the
       plot; the drag clamps against the live extent, this clamps against a
       *resize*, which no drag is present for */
    max-width: 72%;
    position: relative;
  }

  /* the full-window layout: the column *is* the window, so neither the stored
     width nor the clamp that keeps a plot visible applies — there is no plot to
     keep visible, and the tab strip travels with it */
  .side.wide {
    flex: 1 1 auto;
    max-width: none;
    border-left: 0;
  }

  .side.hidden {
    display: none;
  }

  /* One column below `shellThreshold()` (WP-2123): the graphs above the model,
     the sash turned to run along the column's top edge.  Half and half until a
     drag says otherwise. */
  .panes.stacked {
    flex-direction: column;
  }

  .panes.stacked > .plotcol {
    flex: 1 1 0;
    min-height: 0;
  }

  /* `min-height: 0` because a column flex item's automatic minimum is its
     content height, which let the panel column take the whole window and the
     graphs none (measured at 700 px: 1094 px against a 860 px pane). */
  .panes.stacked > .side {
    flex: 0 0 50%;
    min-height: 0;
    max-width: none;
    border-left: 0;
    border-top: 1px solid var(--line);
  }

  .panes.stacked > .side.wide {
    flex: 1 1 auto;
    border-top: 0;
  }

  /* The overflow rule is: never shorten a label, wrap instead (WP-1034) —
     which is also why `.tab` does not grow to fill the row: with nine of them
     the strip wraps at a 340 px column, and a lone `Build` stretched across
     the second row read as a banner rather than as a tab. */
  .tabs {
    display: flex;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--line);
    flex: 0 0 auto;
  }

  /* Every panel scrolls inside itself, so a panel taller than its share is
     clipped here rather than painted over the action bar and the console
     below it (found stacked at 700 px, WP-2123). */
  .panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
    overflow: hidden;
  }

  .panel.hidden {
    display: none;
  }

  .panes.hidden {
    display: none;
  }
</style>
