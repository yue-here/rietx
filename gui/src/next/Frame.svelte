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
  import FileMenu from "../panels/FileMenu.svelte";
  import NewProject from "../panels/NewProject.svelte";
  import Palette from "../panels/Palette.svelte";
  import Recovery from "../panels/Recovery.svelte";
  import type { HelpCorpus } from "../lib/help";
  import { RecoveryWriter, combine, readDraft, type Draft, type InteractiveDraft,
           type PlanDraft } from "../lib/recovery";
  import { isShortcutTarget, type Command } from "../lib/palette";
  import Splitter from "../panels/Splitter.svelte";
  import { modifier, runWords, toggleTitle } from "../lib/statusbar";
  import { consoleLine, follow, type EngineEvent, type RunState } from "../lib/stream";
  import { applyTheme, readChoice, resolveTheme, type ThemeChoice } from "../lib/theme";
  import { WORKFLOWS, menuLabel, workflow, type WorkflowId } from "../lib/workflows";
  import ActionBar from "./ActionBar.svelte";
  import Console from "./Console.svelte";
  import Keys from "./Keys.svelte";
  import Menu, { type MenuAt } from "./Menu.svelte";
  import Params from "./Params.svelte";
  import Pattern from "./Pattern.svelte";
  import { dropsFor, type StatusReadout } from "./readout";
  import Settings from "./Settings.svelte";
  import Start from "./Start.svelte";
  import { BOTTOM_TABS, GRAPH_TABS, MODEL_TABS,
           type BottomTab, type GraphTab, type ModelTab } from "./tabs";

  let project = $state<any>(null);
  let version = $state<any>(null);
  let run = $state<RunState | null>(null);
  let lines = $state<string[]>([]);
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

  let showGraphs = $state(true);
  let showModel = $state(true);
  let showBottom = $state(false);
  let graphTab = $state<GraphTab>("pattern");
  let modelTab = $state<ModelTab>("params");
  let bottomTab = $state<BottomTab>("console");
  let wf = $state<WorkflowId>("refine");
  let step = $state(0);

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
  const runText = $derived(project && busy ? runWords(run) : "");
  const unbuilt = $derived(workflow(wf).steps ?? null);
  const head = $derived(run?.head ?? project?.head ?? null);
  const noPhases = $derived(project ? (project.n_phases ?? 1) === 0 : false);
  const blocked = $derived(noPhases ? "Add a phase before refining" : null);
  const protocol = $derived({
    limits: (project?.doc?.two_theta_limits ?? null) as [number, number] | null,
    regions: (project?.doc?.excluded_regions ?? []) as [number, number][],
  });
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
  /** The kept copy's Interactive and Plan arms, which today's page wrote and
   *  this page has no panel for. The copy is one per project and shared by
   *  both pages, so they ride on every write from here: a Parameters edit on
   *  this page never drops the other page's unapplied edits. */
  const NO_CARRY = { interactive: null, plan: null } as const;
  let carried = $state.raw<{ interactive: InteractiveDraft | null;
                             plan: PlanDraft | null }>(NO_CARRY);
  const carriedCount = $derived(
    (carried.interactive ? Object.keys(carried.interactive.values ?? {}).length : 0)
    + (carried.plan ? 1 : 0));
  $effect(() => {
    const path = project?.path ?? null;
    const extra = carried;
    const draft = combine(pendingTouched + carriedCount, paramsPanel?.draft() ?? null,
                          extra.interactive, extra.plan);
    const at = head;
    untrack(() => recoveryWriter.schedule(path, at, draft));
  });

  function say(line: string) {
    lines = [...lines.slice(-400), line];
  }

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

  async function loadProject() {
    try {
      project = await api.project();
      await loadResult();
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
    project = doc;
    openError = "";
    newOpen = false;
    await loadResult();
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
    carried = draft?.interactive || draft?.plan
      ? { interactive: draft.interactive, plan: draft.plan } : NO_CARRY;
    if (draft?.params) {
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
    recoveryWriter.arm(o.path, o.draft);
    modelTab = "params";
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
    say("# unapplied edits kept; offered again when the project next opens");
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
        say(`project.doc.two_theta_limits = ${limits ? `(${limits.join(", ")})` : "None"}`);
      }
      if ("excluded_regions" in patch)
        say(`project.set_excluded_regions(${JSON.stringify(patch.excluded_regions)})`);
      protocolError = "";
    } catch (error) {
      protocolError = (error as Error).message;
      say(`refused: ${(error as Error).message}`);
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
        say(`project.doc.ui[${JSON.stringify(key)}] = ${JSON.stringify(value)}`);
    } catch (error) {
      say(`# not kept: ${(error as Error).message}`);
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

  /** Apply the pending edits. A refusal is drawn in the Parameters panel,
   *  so a refused apply brings that tab, and the model panel, forward. The
   *  result is not refetched: a `set_values` keeps the last fit (today's
   *  `App.svelte:moved` says why). */
  async function applyPending(): Promise<boolean> {
    const ok = !!(await paramsPanel?.apply());
    if (!ok) {
      modelTab = "params";
      showModel = true;
      return false;
    }
    return true;
  }

  function revertPending() {
    paramsPanel?.revert();
  }

  /** The action bar's primary: apply the pending edits, then refine. `cycle`
   *  is one stage on what is ticked; `plan` is the project's plan. */
  async function refine(mode: "cycle" | "plan" = refineMode) {
    if (refining || busy || noPhases || pendingInvalid || !project) return;
    refining = true;
    try {
      if (pendingTouched && !(await applyPending())) return;
      if (mode === "plan") {
        run = await api.run({ kind: "fit" });
        say("ref.fit(data, plan=…)");
      } else {
        run = await api.run({ kind: "stage", stage: { name: "cycle", turn_on: [] } });
        say('ref.run_stage(Stage("cycle", turn_on=[]))');
      }
    } catch (error) {
      say(`refused: ${(error as Error).message}`);
    } finally {
      refining = false;
    }
  }

  async function open(path: string): Promise<string> {
    // a write still on the timer lands first, for the project it was made in
    await recoveryWriter.flush();
    try {
      await opened(await api.openProject(path));
      say(`p = rx.Project.open(${JSON.stringify(path)})`);
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
      say(`p = rx.Project.open(${JSON.stringify(doc.path)})  # the ${name} example`);
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
      say(`# ${(error as Error).message}`);
    }
  }

  function openWorkflows() {
    if (wfAt) return (wfAt = null);
    const r = wfButton!.getBoundingClientRect();
    wfAt = { x: r.left, y: r.bottom + 4 };
  }

  function chooseWorkflow(id: string) {
    wf = id as WorkflowId;
    step = 0;
  }

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
    { id: "refine", label: pendingTouched ? "Apply the edits and refine" : "Refine",
      echo: "ref.fit(data, plan=…)", key: `${mod}Enter`,
      disabled: !project || busy || noPhases || !!pendingInvalid, run: () => refine() },
    { id: "apply", label: "Apply the edits", echo: "ref.set_values(…)",
      disabled: !pendingTouched || busy || !!pendingInvalid, run: () => applyPending() },
    { id: "revert", label: "Revert the edits", echo: "",
      disabled: !pendingTouched, run: revertPending },
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
    if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return;
    if (event.key === "Enter") {
      if (layered) return;
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
      (event: EngineEvent) => say(consoleLine(event)),
      (frame: RunState) => {
        run = frame;
        // a run just ended, keyed on its outcome rather than on having seen a
        // `running` frame: a stage that starts and ends between two frames
        // sends one idle frame with a new status (today's `App.svelte`)
        const key = `${frame.state}:${frame.run?.status ?? ""}:${frame.run?.node_id ?? ""}`;
        if (seen !== null && key !== seen && frame.state === "idle" && frame.run?.status) {
          void loadResult();
          void api.project().then((doc) => (project = doc)).catch(() => {});
        }
        seen = key;
      },
      { poll: (since) => api.events(since) },
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
    <FileMenu {project} {busy} {say} onnew={() => (newOpen = true)} onopen={open}
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
          {#each GRAPH_TABS as t (t.id)}
            <button class="tab" role="tab" aria-selected={graphTab === t.id} disabled={!project}
              onclick={() => (graphTab = t.id)}>{t.label}</button>
          {/each}
        </div>
        <div class="pane">
          {#if graphTab === "pattern"}
            <Pattern {result} {plotKey} {theme} {protocol} {extent} {wavelengths} {busy}
              {protocolError} onprotocol={setProtocol} onreadout={(r) => (reading = r)}
              projectPath={project?.path ?? null} ui={project?.doc?.ui ?? null} onui={saveUi} />
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
        {#if unbuilt}
          <nav class="tabs steps" aria-label="Steps">
            {#each unbuilt as s, i (s.name)}
              <button class="tab" aria-current={step === i ? "step" : undefined}
                onclick={() => (step = i)}>{s.name}</button>
            {/each}
          </nav>
          <div class="pane wfpane">
            <p class="box">{unbuilt[step].body}</p>
          </div>
        {:else}
          <div class="tabs" role="tablist" aria-label="Model">
            {#each MODEL_TABS as t (t.id)}
              <button class="tab" role="tab" aria-selected={modelTab === t.id} disabled={!project}
                onclick={() => (modelTab = t.id)}>{t.label}</button>
            {/each}
          </div>
        {/if}
        <div class="pane" class:gone={!!unbuilt || modelTab !== "params"}>
          <Params bind:this={paramsPanel} {head} {busy} {corpus} {say} onmoved={structureMoved}
            onpending={(n, why) => { pendingTouched = n; pendingInvalid = why; }} />
        </div>
        {#if !unbuilt}
          {#if modelTab !== "params"}
            <div class="pane"><p class="unbuilt">Not built yet.</p></div>
          {/if}
          <ActionBar bind:mode={refineMode} touched={pendingTouched} invalid={pendingInvalid}
            {busy} {blocked} stats={barStats} onapply={() => applyPending()}
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
            onclick={() => (bottomTab = t.id)}>{t.label}</button>
        {/each}
      </div>
      <div class="pane" class:gone={bottomTab !== "console"}>
        <Console {lines} {dropped} shown={bottomTab === "console"} />
      </div>
      <div class="pane" class:gone={bottomTab !== "history"}></div>
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
  <NewProject {capabilities} {busy} {say} onclose={() => (newOpen = false)} onopened={opened} />
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
    background: var(--panel);
  }

  .model {
    position: relative;
    min-width: 0;
    display: flex;
    flex-direction: column;
    background: var(--panel);
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

  .wfpane {
    padding: 16px;
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
