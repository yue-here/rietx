<script lang="ts">
  /**
   * The rebuilt GUI's frame (WP-2215, piece R1 of WP-2214's plan), served at
   * `/next` beside today's page.
   *
   * The prototype's shape, restated in WP-2215 § Context: a top bar holding the
   * graphs toggle, the workflow menu, the project name (the File menu), a gap,
   * Settings and the model toggle; the graphs on the left and the model on the
   * right, split by a sash; the bottom panel (Console, History) under both,
   * hidden at first; a status bar along the foot with the console toggle at its
   * left. The bars never change shape, so no toggle in them moves
   * (`gui/STYLE.md` § Layout and panels). Both bars are drawn without a project
   * too, their project controls disabled, so opening one moves nothing.
   *
   * Later pieces fill the panes; this one owns where they are and how they
   * show and hide.
   */
  import { onMount, untrack } from "svelte";

  import { ApiError, api } from "../api";
  import { py } from "../lib/py";
  import FileMenu from "../panels/FileMenu.svelte";
  import NewProject from "../panels/NewProject.svelte";
  import Palette from "../panels/Palette.svelte";
  import Interactive from "./Interactive.svelte";
  import Background from "./Background.svelte";
  import Peaks from "./Peaks.svelte";
  import Structure from "./Structure.svelte";
  import Recovery from "../panels/Recovery.svelte";
  import { projectStem } from "../lib/filemenu";
  import type { HelpCorpus } from "../lib/help";
  import { RecoveryWriter, combine, readDraft, restoredText, type Draft,
           type ModelDraft } from "../lib/recovery";
  import { FALLBACK_FWHM_DEG, type PreviewAnswer, type RangeContext } from "../lib/interactive";
  import { isShortcutTarget, type Command } from "../lib/palette";
  import { peakWindows, widestFwhm } from "../lib/peakwin";
  import Splitter from "../panels/Splitter.svelte";
  import { modifier, runWords, toggleTitle } from "../lib/statusbar";
  import { follow, type EngineEvent, type RunState } from "../lib/stream";
  import { applyTheme, readChoice, resolveTheme, type ThemeChoice } from "../lib/theme";
  import type { PeakRow, PeaksPayload } from "../lib/peaks";
  import { WORKFLOWS, isNotBuilt, menuLabel, stepGraph, workflow,
           type WorkflowId } from "../lib/workflows";
  import ActionBar from "./ActionBar.svelte";
  import Console from "./Console.svelte";
  import { eventLine, makeLine, pushLine, sessionScript, sharedSay, stageScript, type Line,
           type LineKind } from "./console";
  import HelpBox from "./HelpBox.svelte";
  import Indexing from "./Indexing.svelte";
  import History from "./History.svelte";
  import { howComment, howWords } from "./howran";
  import { GRAPH_HELP, HISTORY_HELP, MODEL_HELP, WORKFLOW_HELP } from "./helpbox";
  import Keys from "./Keys.svelte";
  import Menu, { type MenuAt } from "./Menu.svelte";
  import Params from "./Params.svelte";
  import Plan from "./Plan.svelte";
  import Text from "./Text.svelte";
  import Pattern from "./Pattern.svelte";
  import { dropsFor, type StatusReadout } from "./readout";
  import Settings from "./Settings.svelte";
  import Start from "./Start.svelte";
  import { BOTTOM_TABS, GRAPH_TABS, MODEL_TABS,
           type BottomTab, type GraphTab, type ModelTab } from "./tabs";

  let project = $state<any>(null);
  let version = $state<any>(null);
  let run = $state<RunState | null>(null);
  let lines = $state.raw<Line[]>([]);
  /** Every call since the page loaded, uncapped: the script export reads it. */
  let calls = $state.raw<Line[]>([]);
  let dropped = $state(0);
  let capabilities = $state<any>(null);
  let docsUrl = $state<string | null>(null);
  let recent = $state<any[]>([]);
  let examples = $state<any[]>([]);
  let openError = $state("");
  let newOpen = $state(false);
  let corpus = $state<HelpCorpus | null>(null);

  /** The last fit (`/api/result`), and a key bumped whenever its curves moved. */
  let result = $state.raw<any>(null);
  let plotKey = $state(0);
  let protocolError = $state("");
  /** The hover readout the Pattern graph hands up, or null off the plot. */
  let reading = $state.raw<StatusReadout | null>(null);
  /** The readout's items a narrow window drops, and the room they are
   *  measured against: the status bar's right half. */
  let readoutDrops = $state.raw<ReadonlySet<string>>(new Set());
  let readoutEl: HTMLSpanElement | undefined = $state();
  let readoutRoom = $state(0);
  /** The action bar's refine choice and the Parameters panel's pending edits. */
  let refineMode = $state<"cycle" | "plan">("plan");
  let pendingTouched = $state(0);
  let pendingInvalid = $state("");
  let paramsPanel = $state<any>(null);
  let refining = false;
  /** The Interactive tab's pending slider values and the preview they drew
   *  (WP-2128, mounted here by WP-2218). The action bar counts both panels'
   *  edits as one set, as today's page does. */
  let interactivePanel = $state<any>(null);
  let sliderTouched = $state(0);
  /** The slider values not yet applied, which the Structure graph draws. */
  let sliderValues = $state.raw<Record<string, number> | null>(null);
  /** The pattern at the sliders' values and at the Text tab's typed values,
   *  each its own panel's answer (WP-2231, the maintainer's look of
   *  2026-11-21, item 8). The graphs draw the panel that answered last, so
   *  the plot follows what the person touched last, and fall back to the
   *  other's when that one is taken down. One panel's pair at a time: a
   *  refusal is never said over the other panel's curves. */
  let sliderPreview = $state.raw<PreviewAnswer | null>(null);
  let sliderPreviewError = $state("");
  let textPreview = $state.raw<PreviewAnswer | null>(null);
  let textPreviewError = $state("");
  let previewFrom = $state<"slider" | "text">("slider");
  const textUp = $derived(!!textPreview || !!textPreviewError);
  const sliderUp = $derived(!!sliderPreview || !!sliderPreviewError);
  const fromText = $derived(textUp && (previewFrom === "text" || !sliderUp));
  const previewAnswer = $derived(fromText ? textPreview : sliderPreview);
  const previewError = $derived(fromText ? textPreviewError : sliderPreviewError);
  /** The Parameters panel's pending holds, shared with the Background
   *  graph's term chips (WP-2218): one pending set for both. */
  let pendingHolds = $state.raw<ReadonlyMap<string, boolean>>(new Map());
  /** The Plan tab (WP-2231): an edited plan is one pending edit in the bar. */
  let planPanel = $state<any>(null);
  let planEdited = $state(false);
  /** The Text tab (WP-2231): an edited buffer is one pending edit in the bar,
   *  and why it cannot be applied when it cannot. */
  let textPanel = $state<any>(null);
  let textEdited = $state(false);
  let textWhy = $state("");
  /** What the recovery copy counts as waiting at Apply: its words name the
   *  Text document apart (`lib/recovery.ts:keptParts`). */
  const counted = $derived(pendingTouched + sliderTouched + (planEdited ? 1 : 0));
  const touched = $derived(counted + (textEdited ? 1 : 0));
  /** Why Apply and Refine are refused: the Parameters panel's reason first. */
  const invalid = $derived(pendingInvalid || textWhy);
  /** The curves the Pattern graph last fetched: the sliders' ranges are
   *  measured from its widest peak and its highest angle. */
  let baseCurves = $state.raw<any>(null);
  const rangeContext = $derived.by((): RangeContext => {
    const tt = baseCurves?.arrays?.two_theta;
    const fwhm = baseCurves ? widestFwhm(peakWindows(baseCurves)) : 0;
    return { fwhm: fwhm > 0 ? fwhm : FALLBACK_FWHM_DEG,
             thetaMaxDeg: tt?.length ? tt[tt.length - 1] / 2 : 45 };
  });
  /** One name per phase, in order, read off the tick rows: a magnetic
   *  phase's row and the declared peaks' row are not phases (today's
   *  `App.svelte:phaseNames`). */
  const phaseNames = $derived.by(() => {
    const out: string[] = [];
    for (const key of Object.keys(baseCurves?.header?.ticks ?? {})) {
      if (key === "(extra)" || (out.length && key === `${out[out.length - 1]} (magnetic)`)) continue;
      out.push(key);
    }
    return out;
  });

  let showGraphs = $state(true);
  let showModel = $state(true);
  let showBottom = $state(false);
  let graphTab = $state<GraphTab>("pattern");
  let modelTab = $state<ModelTab>("params");
  let bottomTab = $state<BottomTab>("console");
  /** The History tab (WP-2211): its view, a view choice kept for the session
   *  like the panels' layout; its node count, for the tab's label; and the
   *  node whose fit is overlaid on the pattern. */
  let historyView = $state<"graph" | "table">("graph");
  let historyCount = $state<number | null>(null);
  let compared = $state.raw<{ id: string; label: string; tt: Float64Array; y: Float64Array } | null>(null);
  let wf = $state<WorkflowId>("refine");
  let step = $state(0);
  /** The peaks-and-indexing workflow's peak list, as its last answer gave it,
   *  the row chosen in its table, and a request to frame a line (WP-2240):
   *  the Pattern graph draws them while the workflow is up. */
  let peaksPayload = $state.raw<PeaksPayload | null>(null);
  let selectedPeak = $state<number | null>(null);
  /** the workflow panel, whose verbs the plot's peak gestures call */
  let indexingPanel: ReturnType<typeof Indexing> | undefined = $state();
  let frameAt = $state.raw<{ two_theta: number; seq: number } | null>(null);

  /** The model panel's width and the bottom panel's height, session-local
   *  until a later piece keeps them with the project (inventory row 251). */
  const MODEL_DEFAULT = 785;
  const BOTTOM_DEFAULT = 200;
  let modelWidth = $state(MODEL_DEFAULT);
  let bottomHeight = $state(BOTTOM_DEFAULT);
  let appEl: HTMLDivElement | undefined = $state();
  let mainEl: HTMLDivElement | undefined = $state();

  let wfAt = $state<MenuAt | null>(null);
  let wfButton: HTMLButtonElement | undefined = $state();
  let settingsOpen = $state(false);
  let paletteOpen = $state(false);
  let keysOpen = $state(false);
  let themeChoice = $state<ThemeChoice>("system");
  let systemDark = $state(false);

  const mod = modifier(typeof navigator === "undefined" ? "" : navigator.platform ?? "");
  const busy = $derived(run?.state === "running" || run?.state === "cancelling");
  /** A re-fit's one stage is said in the title line's words, never by the
   *  stage's internal name (WP-2227, the maintainer's consent of 2026-11-22). */
  const runText = $derived(project && busy ? howWords(run?.run?.how, corpus) || runWords(run) : "");
  /** The workflow's steps across the model panel, or null for Refinement,
   *  which shows the model's tabs. */
  const wfSteps = $derived(workflow(wf).steps ?? null);
  /** The graph tabs the workflow shows (the prototype's: peaks and indexing
   *  draws the pattern and the peak fits). */
  const graphTabs = $derived(GRAPH_TABS.filter((t) => !workflow(wf).graphs
    || workflow(wf).graphs!.includes(t.id)));
  const head = $derived(run?.head ?? project?.head ?? null);
  const noPhases = $derived(project ? (project.n_phases ?? 1) === 0 : false);
  const blocked = $derived(noPhases ? "Add a phase before refining" : null);
  const protocol = $derived({
    limits: (project?.doc?.two_theta_limits ?? null) as [number, number] | null,
    regions: (project?.doc?.excluded_regions ?? []) as [number, number][],
  });
  /** What changes the background's channels and free set without moving the
   *  head: the mode, the fit range and the excluded regions (WP-2129). */
  const protocolKey = $derived(JSON.stringify([project?.doc?.mode ?? null, protocol.limits, protocol.regions]));
  const extent = $derived((project?.data?.two_theta_range ?? null) as [number, number] | null);
  const wavelengths = $derived((project?.data?.wavelengths ?? null) as number[] | null);
  const theme = $derived(resolveTheme(themeChoice, systemDark));
  /** The report's count of findings: the result's errors and warnings, which
   *  the status bar's right half shows at rest (the maintainer's ruling of
   *  2026-11-11, question 3). */
  const findings = $derived(result
    ? (result.diagnostics ?? []).filter((d: any) => d.level === "error" || d.level === "warning").length
    : null);
  const findingsText = $derived(findings === null ? ""
    : findings === 0 ? "No findings" : findings === 1 ? "1 finding" : `${findings} findings`);
  // A narrow window drops the readout's items from the right, the reflections
  // first and Background next ("try b"). Measured as ink against room: each
  // item's box, laid out even while dropped, against the half's own width,
  // never `scrollWidth`, which equals `clientWidth` wherever overflow shows.
  $effect(() => {
    const r = reading, room = readoutRoom, el = readoutEl;
    if (!r || !el) return;
    untrack(() => {
      const widths = new Map<string, number>();
      for (const item of el.querySelectorAll<HTMLElement>(".ro")) {
        widths.set(item.dataset.id ?? "", item.getBoundingClientRect().width);
      }
      const gap = parseFloat(getComputedStyle(el).columnGap) || 0;
      const next = dropsFor(r.items.map((i) => i.id), widths, gap, room, r.dropOrder);
      if ([...next].join() !== [...readoutDrops].join()) readoutDrops = next;
    });
  });

  /** Rwp and GoF ride on the action bar only while the graphs are hidden ("try B"). */
  const barStats = $derived(!showGraphs && result
    ? { rwp: result.statistics?.rwp ?? null, gof: result.statistics?.gof ?? null,
        immature: Boolean(result.maturity?.immature) }
    : null);

  /** The recovery copy of the pending edits (WP-2209), as today's page keeps
   *  it: armed once the kept copy has been offered and answered, and handed
   *  every change of the Parameters panel's pending map. */
  const recoveryWriter = new RecoveryWriter(
    (path, at, draft) => api.putRecovery(path, at, draft));
  let offer = $state.raw<{ path: string; draft: Draft; savedUtc: string | null;
                           moved: boolean } | null>(null);
  /** The kept copy's Model arm, which today's page wrote and this page has
   *  no panel for. The copy is one per project and shared by both pages, so
   *  it rides on every write from here: an edit on this page never drops the
   *  other page's unapplied edits. The Interactive arm (WP-2218), and the
   *  Plan and Text arms (WP-2231), are this page's own. */
  const NO_CARRY = { model: null } as const;
  let carried = $state.raw<{ model: ModelDraft | null }>(NO_CARRY);
  $effect(() => {
    const path = project?.path ?? null;
    const extra = carried;
    const draft = combine(counted,
                          { ...extra, params: paramsPanel?.draft(),
                            interactive: interactivePanel?.draft(), plan: planPanel?.draft() ?? null,
                            text: textPanel?.draft() ?? null });
    const at = head;
    untrack(() => recoveryWriter.schedule(path, at, draft));
  });

  function say(kind: LineKind, text: string, script?: string | null) {
    write(makeLine(kind, text, script));
  }

  /**
   * Start a run behind its call: the run's events fold under it. The call is
   * written before the request, since the stream can deliver the run's first
   * events before the route answers; a refused run takes it back, so neither
   * the Console nor the script holds a call that never ran.
   */
  async function startRun(body: any, text: string, script?: string) {
    const line = write({ ...makeLine("call", text, script), run: true });
    try {
      run = await api.run(body);
    } catch (error) {
      lines = lines.filter((l) => l !== line);
      calls = calls.filter((l) => l !== line);
      throw error;
    }
  }

  /** The entry the lines written in this turn of the event loop share: one
   *  action's echoes land together, so they draw under one timestamp. */
  let entry = 0;
  let entryOpen = false;

  function write(line: Line): Line {
    if (line.kind !== "event") {
      if (!entryOpen) {
        entry += 1;
        entryOpen = true;
        queueMicrotask(() => (entryOpen = false));
      }
      line = { ...line, entry };
    }
    lines = pushLine(lines, line);
    if (line.kind === "call") calls = [...calls, line];
    return line;
  }

  /** What the two shared panels write through (`console.ts:sharedSay`). */
  const sayShared = sharedSay(say);

  $effect(() => {
    applyTheme(theme, document.documentElement);
  });

  async function chooseTheme(next: ThemeChoice) {
    themeChoice = next;
    try {
      await api.patchSettings({ theme: next });
    } catch {
      // the choice still holds for this page; the store answers next time
    }
  }

  async function loadResult() {
    try {
      result = (await api.result()).result;
    } catch {
      // no fit yet is an empty state; the graph says what it can draw
      result = null;
    }
    plotKey += 1;
  }

  /**
   * The session's first entry, as the prototype opens it: the lines that bind
   * the names every later call uses, and where the project stands. The script
   * writes its own preamble, so these lines are marked and it skips them.
   * The output line reads as the prototype's: Rwp, the free count and the
   * history nodes. The free count is `GET /api/params`' `n_free`, the rows
   * whose vary flag is set, as the Parameters panel counts them; a plan's
   * stages replace those flags, so it is not what a Refine frees. An
   * unreadable table leaves it out. The count is read beside the result
   * (`freeCount`), so the open waits for neither in turn, and the lines are
   * written in one turn, so they share an entry.
   */
  async function freeCount(): Promise<number | null> {
    try {
      const n = (await api.params())?.n_free;
      return typeof n === "number" ? n : null;
    } catch {
      return null;
    }
  }

  function sayPreamble(free: number | null) {
    if (!project?.path) return;
    const path = project.path;
    const bind = (text: string) => write({ ...makeLine("call", text), preamble: true });
    bind("import rietx as rx");
    bind(`p = rx.Project.open(${JSON.stringify(path)})`);
    bind("ref = p.refinement");
    const rwp = result?.statistics?.rwp;
    const nodes = project.n_nodes ?? 0;
    say("output", [typeof rwp === "number" ? `Rwp ${(rwp * 100).toFixed(2)} %` : null,
                   free === null ? null : `${free} free`,
                   `${nodes} history node${nodes === 1 ? "" : "s"}`]
      .filter(Boolean).join(", "));
  }

  async function loadProject() {
    try {
      project = await api.project();
      const [, free] = await Promise.all([loadResult(), freeCount()]);
      sayPreamble(free);
      await offerRecovery();
    } catch (error) {
      project = null;
      if (!(error instanceof ApiError && error.code === "NO_PROJECT"))
        openError = (error as Error).message;
      await loadLists();
    }
  }

  /** The start screen's two lists; an unreadable one is empty, not an error. */
  async function loadLists() {
    try {
      recent = (await api.recent()).recent ?? [];
    } catch {
      recent = [];
    }
    try {
      examples = (await api.examples()).examples ?? [];
    } catch {
      examples = [];
    }
  }

  async function opened(doc: any) {
    await leaveEdits();
    // the script is this project's session: another project's calls are not
    calls = [];
    // the peak list is the project's (`peaks.json`): another project's rows,
    // their chosen line and a frame request are not this one's
    peaksPayload = null;
    selectedPeak = null;
    frameAt = null;
    project = doc;
    openError = "";
    newOpen = false;
    const [, free] = await Promise.all([loadResult(), freeCount()]);
    sayPreamble(free);
    await offerRecovery();
  }

  /** Leave the open project's pending edits behind as its recovery copy, and
   *  clear them from the panel, which stays mounted across an open. */
  async function leaveEdits() {
    await recoveryWriter.flush();
    recoveryWriter.disarm();
    offer = null;
    carried = NO_CARRY;
    paramsPanel?.revert();
    interactivePanel?.revert();
    planPanel?.leave();
    textPanel?.forget();
    // node ids repeat across projects (n0000, n0001, …), so a compared node
    // is cleared here, never by looking for its id in the next history
    compared = null;
    historyCount = null;
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
      // an unreadable copy is no copy
    }
    if (project?.path !== path) return;
    const draft = readDraft(kept?.draft);
    carried = draft?.model ? { model: draft.model } : NO_CARRY;
    if (draft?.params || draft?.interactive || draft?.plan || draft?.text) {
      offer = { path, draft, savedUtc: kept.saved_utc ?? null,
                moved: !!kept.head && kept.head !== kept.head_now };
      return;
    }
    // the server holds `draft`, which this page only carries
    recoveryWriter.arm(path, draft);
  }

  function restoreKept() {
    const o = offer;
    if (!o) return;
    offer = null;
    if (o.draft.params) paramsPanel?.restoreDraft(o.draft.params);
    if (o.draft.interactive) interactivePanel?.restoreDraft(o.draft.interactive);
    if (o.draft.plan) planPanel?.restoreDraft(o.draft.plan);
    if (o.draft.text) textPanel?.restoreDraft(o.draft.text);
    recoveryWriter.arm(o.path, o.draft);
    modelTab = o.draft.params ? "params" : o.draft.interactive ? "interactive"
      : o.draft.plan ? "plan" : "text";
    say("comment", restoredText(o.draft));
  }

  async function discardKept() {
    const o = offer;
    if (!o) return;
    offer = null;
    try {
      await api.putRecovery(o.path, null, null);
    } catch (error) {
      say("refusal", `refused: ${(error as Error).message}`);
      if (project?.path === o.path) {
        recoveryWriter.arm(o.path, o.draft);
        recoveryWriter.schedule(o.path, head, null);
      }
      return;
    }
    if (project?.path === o.path) {
      carried = NO_CARRY;
      recoveryWriter.arm(o.path, null);
    }
  }

  /** Escape on the offer: kept on the server, offered at the next open. */
  function setAsideKept() {
    if (!offer) return;
    offer = null;
    say("comment", "# unapplied edits kept; offered again when the project next opens");
  }

  function pageHidden() {
    const unsent = recoveryWriter.takeUnsent();
    if (unsent) api.putRecoveryOnHide(unsent.project, unsent.head, unsent.draft);
  }

  /** A range or a region from the Pattern graph, persisted on the verb (WP-1033). */
  async function setProtocol(patch: Record<string, unknown>) {
    if (!project || busy) return;
    try {
      project = await api.patchProject(patch);
      if ("two_theta_limits" in patch) {
        const limits = patch.two_theta_limits as number[] | null;
        say("call", `p.doc.two_theta_limits = ${limits ? `(${limits.join(", ")})` : "None"}`);
      }
      if ("excluded_regions" in patch)
        say("call", `p.set_excluded_regions(${py(patch.excluded_regions)})`);
      protocolError = "";
    } catch (error) {
      protocolError = (error as Error).message;
      say("refusal", `refused: ${(error as Error).message}`);
    }
  }

  /** Keep a view choice with the project, in `ProjectDoc.ui` (WP-1044: a
   *  `ui` key belongs to what it is about). A refusal, such as the 409 while a
   *  run is in flight, leaves the choice on screen and unkept. */
  async function saveUi(patch: Record<string, unknown>) {
    if (!project) return;
    const path = project.path;
    try {
      const doc = await api.patchProject({ ui: patch });
      if (project?.path === path) project = doc;
      for (const [key, value] of Object.entries(patch))
        say("comment", `# view kept: ui[${py(key)}] = ${py(value)}`);
    } catch (error) {
      say("comment", `# not kept: ${(error as Error).message}`);
    }
  }

  /** A structural edit landed (a menu on a phase or an atom): the head moved,
   *  so the document (`n_phases`) and the curves are read again, as today's
   *  `App.svelte:moved` does. */
  async function structureMoved() {
    try {
      project = await api.project();
    } catch {
      // the panel reloads itself; the document answers next time
    }
    await loadResult();
  }

  /** Apply the pending edits. A refusal is drawn in the panel that made
   *  the edit, so a refused apply brings that tab, and the model panel,
   *  forward. The result is not refetched: a `set_values` keeps the last fit
   *  (today's `App.svelte:moved` says why). */
  async function applyPending(): Promise<boolean> {
    // a second Apply or ⌘⏎ while one is in flight would find each panel
    // mid-apply, read that as a refusal and pull its tab forward
    if (applying) return false;
    applying = true;
    try {
      return await applyAll();
    } finally {
      applying = false;
    }
  }
  let applying = false;

  async function applyAll(): Promise<boolean> {
    if (!(await applyText())) return false;
    const ok = !!(await paramsPanel?.apply());
    if (!ok) {
      modelTab = "params";
      showModel = true;
      return false;
    }
    // the slider values second, so a slider wins a path both panels touched;
    // each panel's apply is its own node, as on today's page
    const slid = !!(await interactivePanel?.apply());
    if (!slid) {
      modelTab = "interactive";
      showModel = true;
      return false;
    }
    // the plan last: it moves no head, and a refused plan is drawn in its tab
    const planned = planPanel ? !!(await planPanel.save()) : true;
    if (!planned) {
      modelTab = "plan";
      showModel = true;
      return false;
    }
    return true;
  }

  /** The Text buffer first: it carries the revision it was typed against,
   *  and any other apply moves the head under it, which would leave it stale
   *  (WP-1013: no merge). A path both the text and Parameters change takes
   *  the Parameters value, applied after it. */
  async function applyText(): Promise<boolean> {
    if (!textPanel || !textEdited) return true;
    if (await textPanel.apply()) return true;
    modelTab = "text";
    showModel = true;
    return false;
  }

  /** ⌘⏎ inside the Text editor: the bar's Apply, under the bar's own rule. */
  function applyFromText() {
    if (touched && !busy && !invalid) void applyPending();
  }

  function revertPending() {
    textPanel?.revert();
    paramsPanel?.revert();
    interactivePanel?.revert();
    planPanel?.revert();
  }

  /** The Plan tab stored a plan: the document is read again, so the action
   *  bar's stage count names the plan the project now holds. */
  async function planSaved() {
    try {
      project = await api.project();
    } catch {
      // the bar's count catches up on the next read
    }
  }

  /** The Plan tab's Run this stage and the `.` key: the stage as it stands on
   *  screen, from where the model stands. The Text, Parameters and slider
   *  edits waiting in the bar are applied first, as Refine applies them; the plan's
   *  own edit is not, since the stage runs as drawn either way. */
  async function runStage(stage: any, echo: string) {
    if (refining || busy || noPhases || invalid || !project) return;
    refining = true;
    try {
      if (!(await applyText())) return;
      if (pendingTouched + sliderTouched) {
        if (!(await paramsPanel?.apply())) {
          modelTab = "params";
          showModel = true;
          return;
        }
        if (!(await interactivePanel?.apply())) {
          modelTab = "interactive";
          showModel = true;
          return;
        }
      }
      await startRun({ kind: "stage", stage }, echo, stageScript(stage));
    } catch (error) {
      say("refusal", `refused: ${(error as Error).message}`);
    } finally {
      refining = false;
    }
  }

  /** The action bar's primary: apply the pending edits, then refine. `cycle`
   *  is one stage on what is ticked; `plan` is the project's plan. */
  async function refine(mode: "cycle" | "plan" = refineMode) {
    if (refining || busy || noPhases || invalid || !project) return;
    refining = true;
    try {
      if (touched && !(await applyPending())) return;
      if (mode === "plan") {
        await startRun({ kind: "fit" }, "p.fit()");
      } else {
        await startRun({ kind: "stage", stage: { name: "cycle", turn_on: [] } },
                       'p.run_stage(rx.Stage("cycle", turn_on=[]))');
      }
    } catch (error) {
      say("refusal", `refused: ${(error as Error).message}`);
    } finally {
      refining = false;
    }
  }

  async function open(path: string): Promise<string> {
    // a write still on the timer lands first, for the project it was made in
    await recoveryWriter.flush();
    try {
      // opened() writes the session's first entry, the open among it
      await opened(await api.openProject(path));
      return "";
    } catch (error) {
      openError = (error as Error).message;
      return openError;
    }
  }

  async function openExample(name: string, reset = false): Promise<string> {
    // a write still on the timer lands first: after a reset it would otherwise
    // re-create the copy the server has just discarded (WP-2209)
    await recoveryWriter.flush();
    try {
      const doc = reset ? await api.resetExample(name) : await api.openExample(name);
      await opened(doc);
      return "";
    } catch (error) {
      openError = (error as Error).message;
      return openError;
    }
  }

  async function removeRecent(path: string) {
    try {
      recent = (await api.removeRecent(path)).recent ?? [];
    } catch (error) {
      openError = (error as Error).message;
    }
  }

  async function closed() {
    await leaveEdits();
    project = null;
    result = null;
    showBottom = false;
    await loadLists();
  }

  /** Graphs and model cannot both be hidden (`gui/STYLE.md` § Layout). */
  function toggleGraphs() {
    if (!project || !showModel) return;
    showGraphs = !showGraphs;
  }

  function toggleModel() {
    if (!project || !showGraphs) return;
    showModel = !showModel;
  }

  function toggleBottom() {
    if (!project) return;
    showBottom = !showBottom;
  }

  async function stop() {
    if (!busy) return;
    try {
      run = await api.cancel();
    } catch (error) {
      say("refusal", `refused: ${(error as Error).message}`);
    }
  }

  function openWorkflows() {
    if (wfAt) return (wfAt = null);
    const r = wfButton!.getBoundingClientRect();
    wfAt = { x: r.left, y: r.bottom + 4 };
  }

  function chooseWorkflow(id: string) {
    wf = id as WorkflowId;
    chooseStep(0);
    const shown = workflow(wf).graphs;
    if (shown && !shown.includes(graphTab)) graphTab = shown[0];
  }

  /** A step opens on its graph: the peak fits for Fit peaks, the pattern for
   *  the others (the prototype's, round 11). */
  function chooseStep(i: number) {
    step = i;
    const g = stepGraph(wf, i);
    if (g) graphTab = g;
  }

  /** The chosen row itself arrives through `bind:selected`. */
  function framePeak(row: PeakRow) {
    frameAt = { two_theta: row.two_theta, seq: (frameAt?.seq ?? 0) + 1 };
  }

  /** The stage `.` runs, for the palette's label. */
  const planStageName = $derived(planPanel?.selectedName() ?? "");

  /** Every command the frame has, each with its key and the Python it runs
   *  where it runs any (WP-2214 rows 241-242). Later pieces add theirs. */
  const commands = $derived<Command[]>([
    { id: "graphs", label: showGraphs ? "Hide the graphs" : "Show the graphs", echo: "",
      key: `${mod}1`, disabled: !project || !showModel, run: toggleGraphs },
    { id: "model", label: showModel ? "Hide the model" : "Show the model", echo: "",
      key: `${mod}2`, disabled: !project || !showGraphs, run: toggleModel },
    { id: "console", label: showBottom ? "Hide the console" : "Show the console", echo: "",
      key: `${mod}J`, disabled: !project, run: toggleBottom },
    { id: "stop", label: "Stop the run", echo: "token.cancel()", key: `${mod}.`,
      disabled: !busy, run: stop },
    { id: "refine", label: touched ? "Apply the edits and refine" : "Refine",
      echo: "ref.fit(data, plan=…)", key: `${mod}Enter`,
      disabled: !project || busy || noPhases || !!invalid, run: () => refine() },
    { id: "apply", label: "Apply the edits", echo: "ref.set_values(…)",
      disabled: !touched || busy || !!invalid, run: () => applyPending() },
    { id: "revert", label: "Revert the edits", echo: "",
      disabled: !touched, run: revertPending },
    { id: "stage", label: planStageName ? `Run the stage “${planStageName}”` : "Run this stage",
      echo: "ref.run_stage(Stage(…))", key: ".",
      disabled: !project || busy || noPhases || !!invalid || !planStageName,
      run: () => planPanel?.runStage() },
    { id: "plan-undo", label: "Undo the plan edit", echo: "",
      disabled: !planPanel?.canUndo(), run: () => planPanel?.undo() },
    { id: "plan-redo", label: "Redo the plan edit", echo: "",
      disabled: !planPanel?.canRedo(), run: () => planPanel?.redo() },
    { id: "peaks-undo", label: "Undo the peak edit", echo: "",
      disabled: wf !== "index" || !indexingPanel?.canUndo(), run: () => void indexingPanel?.undo() },
    { id: "peaks-redo", label: "Redo the peak edit", echo: "",
      disabled: wf !== "index" || !indexingPanel?.canRedo(), run: () => void indexingPanel?.redo() },
    { id: "new", label: "New project…", echo: "rx.Project.create(…)", disabled: busy,
      run: () => (newOpen = true) },
    ...WORKFLOWS.map((w): Command => ({
      id: `wf:${w.id}`, label: `Workflow: ${menuLabel(w)}`, echo: "", disabled: !project,
      run: () => chooseWorkflow(w.id) })),
    { id: "settings", label: "Settings…", echo: "", key: `${mod},`,
      run: () => (settingsOpen = true) },
    ...(["system", "light", "dark"] as const).map((t): Command => ({
      id: `theme:${t}`, label: `Theme: ${t === "system" ? "Match system" : t[0].toUpperCase() + t.slice(1)}`,
      echo: "", run: () => chooseTheme(t) })),
    { id: "palette", label: "Show all commands", echo: "", key: `${mod}K`,
      run: () => (paletteOpen = true) },
    { id: "keys", label: "Keyboard shortcuts", echo: "", key: "?", run: () => (keysOpen = true) },
  ]);

  /** Whether a modal layer is up. A key never opens a second one over it:
   *  each layer takes Esc on the window, so two open at once close together. */
  const layered = $derived(settingsOpen || paletteOpen || keysOpen || newOpen || !!wfAt || !!offer);

  /** The frame's keys (WP-2214 rows 12, 228, 239, 240): ⌘1 and ⌘2 the side
   *  panels, ⌘J the bottom panel, ⌘, Settings, ⌘K the palette, ⌘. stops a
   *  run, and `?` lists them. Ctrl elsewhere. Esc is each layer's own. */
  function keydown(event: KeyboardEvent) {
    if (event.key === "?" && isShortcutTarget(event)) {
      if (layered) return;
      event.preventDefault();
      keysOpen = true;
      return;
    }
    // `.` runs the Plan tab's selected stage (WP-2214 row 232)
    if (event.key === "." && !event.metaKey && !event.ctrlKey && !event.altKey
        && isShortcutTarget(event)) {
      if (layered || !project || busy || noPhases) return;
      event.preventDefault();
      planPanel?.runStage();
      return;
    }
    if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return;
    if (event.key === "Enter") {
      // the Text editor's ⌘⏎ is its Apply (`lib/editor.ts`), never a Refine
      if (layered || (event.target as Element | null)?.closest?.(".cm-editor")) return;
      event.preventDefault();
      void refine();
      return;
    }
    const act: Record<string, () => void> = {
      "1": toggleGraphs,
      "2": toggleModel,
      j: toggleBottom,
      k: () => (paletteOpen || !layered) && (paletteOpen = !paletteOpen),
      ",": () => (settingsOpen || !layered) && (settingsOpen = !settingsOpen),
      ".": stop,
    };
    const fn = act[event.key.toLowerCase()];
    if (!fn) return;
    event.preventDefault();
    fn();
  }

  onMount(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    systemDark = !!query?.matches;
    const listen = () => (systemDark = !!query?.matches);
    query?.addEventListener?.("change", listen);
    (async () => {
      try {
        themeChoice = readChoice((await api.settings()).ui?.theme);
      } catch {
        // an unreadable store is the default choice, not a boot failure
      }
      // neither is a reason to skip loading the project: a failure leaves the
      // About line empty and New project without its vocabularies
      try {
        version = await api.version();
      } catch {
        version = null;
      }
      try {
        capabilities = await api.capabilities();
      } catch {
        capabilities = null;
      }
      try {
        corpus = await api.help();
        docsUrl = (corpus as any)?.docs_url ?? null;
      } catch {
        docsUrl = null;
      }
      await loadProject();
      run = await api.runState();
    })();
    /** The run outcome this page has already reacted to; null until the first
     *  frame, so a reload does not reload for a run that ended before it. */
    let seen: string | null = null;
    const unfollow = follow(
      (event: EngineEvent) => write(eventLine(event)),
      (frame: RunState) => {
        run = frame;
        // a run just ended, keyed on its outcome rather than on having seen a
        // `running` frame: a stage that starts and ends between two frames
        // sends one idle frame with a new status (today's `App.svelte`)
        const key = `${frame.state}:${frame.run?.status ?? ""}:${frame.run?.node_id ?? ""}`;
        if (seen !== null && key !== seen && frame.state === "idle" && frame.run?.status) {
          // how the fit ran, as `Refinement.summary()` prints it (WP-2227)
          const comment = howComment(frame);
          if (comment) say("comment", comment);
          void loadResult();
          void api.project().then((doc) => (project = doc)).catch(() => {});
        }
        seen = key;
      },
      { poll: (since) => api.events(since), onDropped: (n) => (dropped = n) },
    );
    return () => {
      unfollow();
      query?.removeEventListener?.("change", listen);
    };
  });
</script>

<svelte:window onkeydown={keydown} onpagehide={pageHidden} />

{#snippet sideIcon(side: "left" | "right" | "bottom", on: boolean)}
  <svg viewBox="0 0 16 16" aria-hidden="true">
    <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" />
    {#if side === "left"}
      <rect class="fill" class:on x="2" y="3" width="4.5" height="10" /><path d="M6.5 2.5v11" />
    {:else if side === "right"}
      <rect class="fill" class:on x="9.5" y="3" width="4.5" height="10" /><path d="M9.5 2.5v11" />
    {:else}
      <rect class="fill" class:on x="2" y="9.5" width="12" height="3.5" /><path d="M1.5 9.5h13" />
    {/if}
  </svg>
{/snippet}

<header class="topbar">
  <button class="ib" aria-pressed={showGraphs} disabled={!project || !showModel}
    onclick={toggleGraphs} aria-label={showGraphs ? "Hide the graphs" : "Show the graphs"}
    title="{showGraphs ? 'Hide' : 'Show'} the graphs&#10;{mod}1"
    >{@render sideIcon("left", showGraphs)}</button>
  <button class="mbtn wf" bind:this={wfButton} aria-haspopup="menu" aria-expanded={!!wfAt}
    disabled={!project} onclick={openWorkflows}>
    {workflow(wf).name}<svg class="chev" viewBox="0 0 16 16" aria-hidden="true"
      ><path d="M4.5 6.5 8 10l3.5-3.5" /></svg></button>
  <span class="proj">
    <FileMenu {project} {busy} say={sayShared} script={() => sessionScript(calls, project?.path ?? "")}
      onnew={() => (newOpen = true)} onopen={open}
      onproject={(doc) => (project = doc)} onclosed={closed} />
  </span>
  <span class="gap"></span>
  <button class="ib" aria-label="Settings" title="Settings&#10;{mod},"
    aria-haspopup="dialog" aria-expanded={settingsOpen}
    onclick={() => (settingsOpen = !settingsOpen)}>
    <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6.61 3.51 6.95 1.89h2.1l.34 1.62.8.33 1.39-.9 1.48 1.48-.9 1.39.33.8 1.62.34v2.1l-1.62.34-.33.8.9 1.39-1.48 1.48-1.39-.9-.8.33-.34 1.62h-2.1l-.34-1.62-.8-.33-1.39.9-1.48-1.48.9-1.39-.33-.8-1.62-.34v-2.1l1.62-.34.33-.8-.9-1.39 1.48-1.48 1.39.9Z" /><circle cx="8" cy="8" r="2.1" /></svg>
  </button>
  <button class="ib" aria-pressed={showModel} disabled={!project || !showGraphs}
    onclick={toggleModel} aria-label={showModel ? "Hide the model" : "Show the model"}
    title="{showModel ? 'Hide' : 'Show'} the model&#10;{mod}2"
    >{@render sideIcon("right", showModel)}</button>
</header>

<div class="main" bind:this={mainEl}>
  {#if !project}
    <!-- with no project the start screen is the window (WP-2131), between the
         bars, which keep their shape so opening a project moves nothing -->
    <Start {recent} {examples} {busy} {docsUrl} error={openError}
      onnew={() => (newOpen = true)} onopen={open} onexample={openExample}
      onremove={removeRecent} />
  {:else}
  <div class="app" bind:this={appEl}>
    {#if showGraphs}
      <section class="graphs" aria-label="Graphs">
        <div class="tabs" role="tablist" aria-label="Graphs">
          {#each graphTabs as t (t.id)}
            <button class="tab" role="tab" aria-selected={graphTab === t.id} disabled={!project}
              onclick={() => (graphTab = t.id)}>{t.label}</button>
          {/each}
          {#if project}
            <HelpBox entry={GRAPH_HELP[graphTab]} {docsUrl}
              label="About the {GRAPH_TABS.find((t) => t.id === graphTab)?.label} graph" />
          {/if}
        </div>
        <div class="pane">
          {#if graphTab === "pattern"}
            <Pattern {result} {plotKey} {theme} {protocol} {extent} {wavelengths} {busy}
              {protocolError} onprotocol={setProtocol} onreadout={(r) => (reading = r)}
              projectPath={project?.path ?? null} ui={project?.doc?.ui ?? null} onui={saveUi}
              preview={previewAnswer} {previewError} oncurves={(c) => (baseCurves = c)}
              {compared} howText={howWords(result?.how, corpus)}
              peaksActive={wf === "index"} peaks={wf === "index" ? peaksPayload?.peaks ?? null : null}
              groups={wf === "index" ? peaksPayload?.groups ?? null : null}
              bind:selectedPeak {frameAt}
              onpeakedit={(e) => indexingPanel?.edit(e) ?? Promise.resolve(false)}
              onpeakundo={() => indexingPanel?.undo() ?? Promise.resolve(false)} />
          {:else if graphTab === "peaks"}
            <Peaks {plotKey} {theme} preview={previewAnswer} {previewError}
              rwp={result?.statistics?.rwp ?? null} oncurves={(c) => (baseCurves = c)} />
          {:else if graphTab === "background"}
            <Background {head} {busy} {theme} {say} protocol={protocolKey} holds={pendingHolds}
              onhold={(path, held, serverHeld) => paramsPanel?.setHold(path, held, serverHeld)}
              ondropped={(gone) => paramsPanel?.dropPending(gone)}
              onmoved={structureMoved} />
          {:else if graphTab === "structure"}
            <Structure {head} {busy} {theme} {say} values={sliderValues}
              projectPath={project?.path ?? null} onreadout={(r) => (reading = r)} />
          {:else}
            <p class="unbuilt">Not built yet.</p>
          {/if}
        </div>
      </section>
    {/if}
    <!-- mounted while hidden, so hiding the model or choosing a workflow not
         built yet keeps the Parameters panel's pending edits (and the recovery
         copy the effect above writes from them) -->
      <section class="model" class:gone={!showModel} aria-label="Model"
        style:flex={showGraphs ? `0 0 ${modelWidth}px` : "1 1 auto"}>
        {#if showGraphs && project}
          <Splitter size={modelWidth} grow="left" min={360} keep={360}
            extent={() => appEl?.clientWidth ?? 0}
            onsize={(size) => (modelWidth = size)} onreset={() => (modelWidth = MODEL_DEFAULT)}
            title="Drag to resize the panels; double-click resets them" />
        {/if}
        {#if wfSteps}
          <!-- the prototype's step strip (round 4, 2026-11-07; round 11): each
               step its number in a ring and its name, the current one raised,
               a › between them -->
          <nav class="steps" aria-label="Steps">
            {#each wfSteps as s, i (s.name)}
              {#if i}<span class="ar" aria-hidden="true">›</span>{/if}
              <button class="step" aria-current={step === i ? "step" : undefined}
                onclick={() => chooseStep(i)}><b>{i + 1}</b><span class="sname">{s.name}</span></button>
            {/each}
            <span class="sright">
              {#if workflow(wf).loop}
                <button class="step loop" onclick={() => chooseStep(0)}
                  title={workflow(wf).loop}>↺ iterate</button>
              {/if}
              {#if WORKFLOW_HELP[wf]}
                <HelpBox entry={WORKFLOW_HELP[wf]!} {docsUrl}
                  label="About the {workflow(wf).name} workflow" />
              {/if}
            </span>
          </nav>
          {#if isNotBuilt(wf)}
            <div class="pane wfpane">
              <p class="box">{wfSteps[step].body}</p>
            </div>
          {/if}
        {:else}
          <div class="tabs" role="tablist" aria-label="Model">
            {#each MODEL_TABS as t (t.id)}
              <button class="tab" role="tab" aria-selected={modelTab === t.id} disabled={!project}
                onclick={() => (modelTab = t.id)}>{t.label}</button>
            {/each}
            {#if project}
              <HelpBox entry={MODEL_HELP[modelTab]} {docsUrl}
                label="About the {MODEL_TABS.find((t) => t.id === modelTab)?.label} tab" />
            {/if}
          </div>
        {/if}
        <!-- mounted for the workflow's life, so a step switch keeps the list's
             filter and the chosen row; keyed on the project, since the list
             is read once on mount and its row numbers are that project's -->
        {#if wf === "index"}
          {#key project.path}
            <div class="pane wfsteps">
              <Indexing bind:this={indexingPanel} {step} steps={wfSteps ?? []} {busy} {corpus} {say}
                bind:selected={selectedPeak}
                onpeaks={(p) => (peaksPayload = p)} onframe={framePeak} />
            </div>
          {/key}
        {/if}
        <div class="pane" class:gone={!!wfSteps || modelTab !== "params"}>
          <Params bind:this={paramsPanel} {head} {busy} {corpus} {say} onmoved={structureMoved}
            anodes={capabilities?.anodes ?? []}
            onpending={(n, why) => { pendingTouched = n; pendingInvalid = why; }}
            onholds={(h) => (pendingHolds = h)} />
        </div>
        <!-- mounted while hidden too: its slider values are pending edits -->
        <div class="pane" class:gone={!!wfSteps || modelTab !== "interactive"}>
          <Interactive bind:this={interactivePanel} {head} {busy} {corpus} {say}
            context={rangeContext} {phaseNames}
            onpending={(n) => (sliderTouched = n)}
            onvalues={(v) => (sliderValues = v)}
            onpreview={(answer, why) => {
              sliderPreview = answer; sliderPreviewError = why;
              if (answer || why) previewFrom = "slider";
            }} />
        </div>
        <!-- mounted while hidden too: an edited plan is a pending edit -->
        <div class="pane" class:gone={!!wfSteps || modelTab !== "plan"}>
          <Plan bind:this={planPanel} mode={project?.doc?.mode ?? "rietveld"} {head} {busy}
            noPhasesReason={blocked} {corpus} {phaseNames} {say} onrun={runStage}
            onpending={(edited) => (planEdited = edited)} onsaved={planSaved} />
        </div>
        <!-- mounted while hidden too: an edited buffer is a pending edit -->
        <div class="pane" class:gone={!!wfSteps || modelTab !== "text"}>
          <Text bind:this={textPanel} {head} {busy} {say} dark={theme === "dark"}
            active={!wfSteps && showModel && modelTab === "text"}
            name={project?.path ? projectStem(project.path) : "project"}
            onmoved={structureMoved} onapply={applyFromText}
            onpreview={(answer, why) => {
              textPreview = answer; textPreviewError = why;
              if (answer || why) previewFrom = "text";
            }}
            onpending={(edited, why) => { textEdited = edited; textWhy = why; }} />
        </div>
        {#if !wfSteps}
          <ActionBar bind:mode={refineMode} {touched} {invalid}
            {busy} {blocked} stats={barStats} stages={project?.doc?.plan?.stages?.length ?? null} onapply={() => applyPending()}
            onrevert={revertPending} onrefine={() => refine()} />
        {/if}
      </section>
  </div>

  {/if}
  {#if project && showBottom}
    <section class="bottom" aria-label="Console and history" style:flex="0 0 {bottomHeight}px">
      <Splitter size={bottomHeight} grow="up" min={90} keep={240}
        extent={() => mainEl?.clientHeight ?? 0}
        onsize={(size) => (bottomHeight = size)} onreset={() => (bottomHeight = BOTTOM_DEFAULT)}
        title="Drag to resize the console; double-click resets it" />
      <div class="tabs" role="tablist" aria-label="Console and history">
        {#each BOTTOM_TABS as t (t.id)}
          <button class="tab" role="tab" aria-selected={bottomTab === t.id}
            onclick={() => (bottomTab = t.id)}>{t.label}{#if t.id === "history" && historyCount != null}<span
              class="count">{historyCount}</span>{/if}</button>
        {/each}
        {#if bottomTab === "history"}
          <span class="hright">
          <span class="segmented hview" role="group" aria-label="History view">
            {#each [["graph", "Graph", "Draw the nodes as lanes"], ["table", "Table", "List the nodes with their numbers"]] as [id, label, tip] (id)}
              <button class:on={historyView === id} aria-pressed={historyView === id} title={tip}
                onclick={() => (historyView = id as "graph" | "table")}>{label}</button>
            {/each}
          </span>
          <HelpBox entry={HISTORY_HELP} {docsUrl} label="About the History tab" />
          </span>
        {/if}
      </div>
      <div class="pane" class:gone={bottomTab !== "console"}>
        <Console {lines} {dropped} shown={bottomTab === "console"} />
      </div>
      <div class="pane" class:gone={bottomTab !== "history"}>
        <!-- keyed on the project: two projects' heads can share an id, and
             History re-reads only when its head changes -->
        {#key project.path}
          <History {head} {busy} {say} view={historyView} compared={compared?.id ?? null}
            oncount={(n) => (historyCount = n)} oncompare={(c) => (compared = c)}
            onrestore={(plan) => paramsPanel?.loadRestore(plan)} onmoved={structureMoved} />
        {/key}
      </div>
    </section>
  {/if}
</div>

<footer class="statusbar">
  <button class="ib console" aria-pressed={project && showBottom} disabled={!project}
    onclick={toggleBottom} aria-label={showBottom ? "Hide the console" : "Show the console"}
    title={toggleTitle(!!project, showBottom, mod)}
    >{@render sideIcon("bottom", !!project && showBottom)}Console</button>
  <span class="run" role="status" title={runText}>{runText}</span>
  <!-- the slot is kept while no run is in flight, so Stop appearing moves nothing -->
  <span class="stopslot">
    <button class="ghost" class:gone={!busy} disabled={!busy} onclick={stop}
      title="Stop the run&#10;{mod}.">Stop</button>
  </span>
  <span class="right" role="status" bind:this={readoutEl} bind:clientWidth={readoutRoom}>
    {#if reading}
      {#each reading.items as it (it.id)}
        <span class="ro" class:dropped={readoutDrops.has(it.id)} data-id={it.id}><span
          class="k">{it.label}</span><span class="v" class:left={it.left}
          style:min-width="{it.slot}ch">{it.value}</span></span>
      {/each}
    {:else}
      {findingsText}
    {/if}
  </span>
</footer>

{#if wfAt}
  <Menu at={wfAt} label="Workflows" anchor={wfButton}
    items={WORKFLOWS.map((w) => ({ id: w.id, label: menuLabel(w), checked: w.id === wf, radio: true }))}
    onchoose={chooseWorkflow} onclose={() => (wfAt = null)} />
{/if}

{#if newOpen}
  <NewProject {capabilities} {busy} say={sayShared} onclose={() => (newOpen = false)} onopened={opened} />
{/if}

{#if paletteOpen}
  <Palette {commands} onclose={() => (paletteOpen = false)} />
{/if}

{#if keysOpen}
  <Keys {commands} onclose={() => (keysOpen = false)} />
{/if}

{#if offer}
  <Recovery draft={offer.draft} savedUtc={offer.savedUtc} moved={offer.moved}
    onrestore={restoreKept} ondiscard={discardKept} onlater={setAsideKept} />
{/if}

{#if settingsOpen}
  <Settings choice={themeChoice} onchoose={chooseTheme}
    version={version?.package_version ?? ""} onclose={() => (settingsOpen = false)} />
{/if}

<style>
  .topbar,
  .statusbar {
    flex: none;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 8px;
    background: var(--bar);
  }

  .topbar {
    height: var(--frame-h);
    border-bottom: 1px solid var(--line);
  }

  .statusbar {
    height: var(--status-h);
    border-top: 1px solid var(--line);
    color: var(--muted);
  }

  .gap {
    flex: 1 1 auto;
  }

  .proj {
    display: inline-flex;
    min-width: 0;
  }

  .main {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .app {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
  }

  .graphs {
    flex: 1 1 0;
    min-width: 0;
    display: flex;
    flex-direction: column;
    /* the page ground, as the prototype's columns: the plot is a panel-ground card on it */
    background: var(--bg);
  }

  .model {
    position: relative;
    min-width: 0;
    display: flex;
    flex-direction: column;
    background: var(--bg);
  }

  .graphs + .model {
    border-left: 1px solid var(--line);
  }

  .bottom {
    position: relative;
    display: flex;
    flex-direction: column;
    min-height: 0;
    max-height: max(90px, calc(100vh - 300px));
    border-top: 1px solid var(--line);
    background: var(--panel);
  }

  .pane {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: auto;
  }

  .gone {
    display: none;
  }

  /* the History tab's node count, in the muted register (the design's
     "History 8") */
  .count {
    margin-left: 6px;
    color: var(--muted);
  }

  /* the History tab's view choice and ? box, at the strip's right */
  .hright {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }

  .wfpane {
    padding: 16px;
  }

  /* the steps hold their own scroll and their foot */
  .wfsteps {
    overflow: hidden;
  }

  .box {
    margin: 0;
    padding: 12px 14px;
    border: 1px dashed var(--line-strong);
    border-radius: 6px;
    color: var(--muted);
  }

  .run {
    flex: 0 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: var(--fg);
  }

  .stopslot button.gone {
    display: inline-block;
    visibility: hidden;
  }

  .unbuilt {
    margin: 16px;
    color: var(--muted);
  }

  /* the right half: the findings count at rest, the hover readout while the
     pointer is over a plot. Every value has a slot in ch, so a sweep moves no
     label (WP-1213's strip rule, one bar down) */
  /* the bar's free room whatever it holds, so the readout replacing the
     findings count resizes no box; set from the right end, and from the left
     (2θ first) when a narrow window cannot hold the whole reading */
  /* the bar's full height whatever it holds, so the readout's mixed faces
     never change the half's box (1 px, measured in the browser) */
  .right {
    position: relative;
    align-self: stretch;
    flex: 1 1 0;
    display: flex;
    justify-content: safe flex-end;
    align-items: center;
    gap: 14px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  /* a label in the text face and the muted colour, its number in the mono
     face and the ink ("try b", 2026-11-11) */
  .ro {
    display: inline-flex;
    align-items: baseline;
    gap: 5px;
    font-size: var(--text-sm);
  }

  .ro .v {
    display: inline-block;
    color: var(--fg);
    font-family: var(--mono-family);
    text-align: right;
  }

  .ro .v.left {
    text-align: left;
  }

  /* dropped from the right when the room is short: still laid out, so its
     width is measured on the next sweep, but it takes no room */
  .ro.dropped {
    position: absolute;
    visibility: hidden;
  }

  .console {
    gap: 6px;
    padding: 0 6px;
    width: auto;
  }
</style>
