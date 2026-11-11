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
  import { onMount } from "svelte";

  import { ApiError, api } from "../api";
  import FileMenu from "../panels/FileMenu.svelte";
  import Splitter from "../panels/Splitter.svelte";
  import { modifier, runWords, toggleTitle } from "../lib/statusbar";
  import { consoleLine, follow, type EngineEvent, type RunState } from "../lib/stream";
  import { applyTheme, readChoice, resolveTheme, type ThemeChoice } from "../lib/theme";
  import { WORKFLOWS, menuLabel, workflow, type WorkflowId } from "../lib/workflows";
  import Console from "./Console.svelte";
  import Menu, { type MenuAt } from "./Menu.svelte";
  import Settings from "./Settings.svelte";
  import { BOTTOM_TABS, GRAPH_TABS, MODEL_TABS,
           type BottomTab, type GraphTab, type ModelTab } from "./tabs";

  let project = $state<any>(null);
  let version = $state<any>(null);
  let run = $state<RunState | null>(null);
  let lines = $state<string[]>([]);
  let dropped = $state(0);

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
  let themeChoice = $state<ThemeChoice>("system");
  let systemDark = $state(false);

  const mod = modifier(typeof navigator === "undefined" ? "" : navigator.platform ?? "");
  const busy = $derived(run?.state === "running" || run?.state === "cancelling");
  const runText = $derived(project && busy ? runWords(run) : "");
  const placeholder = $derived(workflow(wf).steps ?? null);

  function say(line: string) {
    lines = [...lines.slice(-400), line];
  }

  $effect(() => {
    applyTheme(resolveTheme(themeChoice, systemDark), document.documentElement);
  });

  async function chooseTheme(next: ThemeChoice) {
    themeChoice = next;
    try {
      await api.patchSettings({ theme: next });
    } catch {
      // the choice still holds for this page; the store answers next time
    }
  }

  async function loadProject() {
    try {
      project = await api.project();
    } catch (error) {
      project = null;
      if (!(error instanceof ApiError && error.code === "NO_PROJECT"))
        say(`# ${(error as Error).message}`);
    }
  }

  async function open(path: string): Promise<string> {
    try {
      project = await api.openProject(path);
      say(`p = rx.Project.open(${JSON.stringify(path)})`);
      return "";
    } catch (error) {
      return (error as Error).message;
    }
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

  /** The frame's keys (WP-2214 rows 12, 239): ⌘1 and ⌘2 the side panels, ⌘J
   *  the bottom panel, ⌘, Settings, ⌘. stops a run. Ctrl elsewhere. */
  function keydown(event: KeyboardEvent) {
    if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return;
    const act: Record<string, () => void> = {
      "1": toggleGraphs,
      "2": toggleModel,
      j: toggleBottom,
      ",": () => (settingsOpen = !settingsOpen),
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
      version = await api.version();
      await loadProject();
      run = await api.runState();
    })();
    const unfollow = follow(
      (event: EngineEvent) => say(consoleLine(event)),
      (frame: RunState) => (run = frame),
      { poll: (since) => api.events(since) },
    );
    return () => {
      unfollow();
      query?.removeEventListener?.("change", listen);
    };
  });
</script>

<svelte:window onkeydown={keydown} />

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
    <FileMenu {project} {busy} {say} onopen={open} onproject={(doc) => (project = doc)}
      onclosed={() => (project = null)} />
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
  <div class="app" bind:this={appEl}>
    {#if showGraphs || !project}
      <section class="graphs" aria-label="Graphs">
        <div class="tabs" role="tablist" aria-label="Graphs">
          {#each GRAPH_TABS as t (t.id)}
            <button class="tab" role="tab" aria-selected={graphTab === t.id} disabled={!project}
              onclick={() => (graphTab = t.id)}>{t.label}</button>
          {/each}
        </div>
        <div class="pane"></div>
      </section>
    {/if}
    {#if showModel || !project}
      <section class="model" aria-label="Model"
        style:flex={showGraphs || !project ? `0 0 ${modelWidth}px` : "1 1 auto"}>
        {#if showGraphs && project}
          <Splitter size={modelWidth} grow="left" min={360} keep={360}
            extent={() => appEl?.clientWidth ?? 0}
            onsize={(size) => (modelWidth = size)} onreset={() => (modelWidth = MODEL_DEFAULT)}
            title="Drag to resize the panels; double-click resets them" />
        {/if}
        {#if placeholder}
          <nav class="tabs steps" aria-label="Steps">
            {#each placeholder as s, i (s.name)}
              <button class="tab" aria-current={step === i ? "step" : undefined}
                onclick={() => (step = i)}>{s.name}</button>
            {/each}
          </nav>
          <div class="pane wfpane">
            <p class="box">{placeholder[step].body}</p>
          </div>
        {:else}
          <div class="tabs" role="tablist" aria-label="Model">
            {#each MODEL_TABS as t (t.id)}
              <button class="tab" role="tab" aria-selected={modelTab === t.id} disabled={!project}
                onclick={() => (modelTab = t.id)}>{t.label}</button>
            {/each}
          </div>
          <div class="pane"></div>
        {/if}
      </section>
    {/if}
  </div>

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
  <span class="gap"></span>
  <span class="right"></span>
</footer>

{#if wfAt}
  <Menu at={wfAt} label="Workflows" anchor={wfButton}
    items={WORKFLOWS.map((w) => ({ id: w.id, label: menuLabel(w), checked: w.id === wf, radio: true }))}
    onchoose={chooseWorkflow} onclose={() => (wfAt = null)} />
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

  .console {
    gap: 6px;
    padding: 0 6px;
    width: auto;
  }
</style>
