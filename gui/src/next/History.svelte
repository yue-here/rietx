<script lang="ts">
  /**
   * The bottom panel's History tab (WP-2211): every node of the project's
   * history, oldest first and the newest at the bottom, as a graph of lanes
   * or as a table (the maintainer's ruling of 2026-11-21 on question 1, Graph
   * by default). Both views share the row actions and the node's menu.
   *
   * - **Compare** overlays a node's fit on the Pattern graph, through
   *   `GET /api/history/curves`, which replays the node. One node at a time;
   *   a second press clears it. It changes nothing, so it echoes nothing.
   * - **Restore** loads a node's values into the action bar as pending edits
   *   (`./history.ts:restorePlan`). Nothing is written until Apply. A node
   *   whose model differs from the working one cannot be loaded that way, and
   *   the refusal offers Make current instead.
   * - **The node's menu** (right-click, or the context-menu key on a focused
   *   row) holds the verbs that act at once, in plain words (question 5):
   *   Make current, Name…, Note… and Branch from here. Each tooltip says what
   *   the click does with the Python call on its second line, and the Console
   *   echoes the call.
   */
  import { api } from "../api";
  import type { LineKind } from "./console";
  import { normalize, type ParamRow } from "../lib/table";
  import Ask, { type AskField } from "./Ask.svelte";
  import Menu, { type MenuAt, type MenuEntry } from "./Menu.svelte";
  import {
    freeText, gofText, lanes, restoreCount, restorePlan, rwpText, stepName, whenText,
    type HistoryNode, type HistoryPayload, type RestorePlan, ROW_PX,
  } from "./history";
  import { laneColor } from "../lib/history";

  let {
    head,
    busy = false,
    view = "graph",
    compared = null,
    say,
    oncount = () => {},
    oncompare,
    onrestore,
    onmoved,
  }: {
    /** the working state's node: the list re-reads when it moves */
    head: string | null;
    busy?: boolean;
    view?: "graph" | "table";
    /** the node whose fit is overlaid on the pattern */
    compared?: string | null;
    say: (kind: LineKind, text: string, script?: string | null) => void;
    /** the node count, for the tab's label */
    oncount?: (n: number) => void;
    /** overlay a node's curve, or clear it with null */
    oncompare: (compare: { id: string; label: string; tt: Float64Array; y: Float64Array } | null) => void;
    /** put a node's values into the pending edits */
    onrestore: (plan: RestorePlan) => void;
    /** the head moved: the window re-reads the project */
    onmoved: () => void;
  } = $props();

  let payload = $state.raw<HistoryPayload | null>(null);
  let error = $state("");
  let note = $state("");
  let menu = $state<{ at: MenuAt; node: HistoryNode } | null>(null);
  let ask = $state<{ at: { x: number; y: number }; node: HistoryNode; verb: "name" | "note" | "branch" } | null>(null);
  let loading = 0;

  const nodes = $derived(payload?.nodes ?? []);
  const current = $derived(payload?.head ?? null);
  const drawn = $derived(lanes(nodes));

  async function load() {
    const seq = ++loading;
    try {
      const answer = (await api.history()) as HistoryPayload;
      if (seq !== loading) return;
      payload = answer;
      error = "";
      oncount(answer.n_nodes);
    } catch (exc) {
      if (seq !== loading) return;
      payload = null;
      error = (exc as Error).message;
      oncount(0);
    }
  }

  $effect(() => {
    void head;
    load();
  });

  // a compared node the history no longer holds, after another project opened
  $effect(() => {
    if (compared && payload && !payload.nodes.some((n) => n.id === compared)) oncompare(null);
  });

  /** The last Compare pressed: an earlier press's answer arriving after it
   *  is dropped, or it would draw a node the buttons do not show pressed. */
  let comparing = 0;

  async function compare(node: HistoryNode) {
    note = "";
    const seq = ++comparing;
    if (compared === node.id) {
      oncompare(null);
      return;
    }
    try {
      const { unpack } = await import("./rxplot.mjs");
      const packed = unpack(await api.historyCurves(node.id));
      if (seq !== comparing) return;
      oncompare({ id: node.id, label: stepName(node),
                  tt: Float64Array.from(packed.arrays.two_theta),
                  y: Float64Array.from(packed.arrays.y_calc) });
    } catch (exc) {
      if (seq !== comparing) return;
      note = `Compare refused:${(exc as Error).message}`;
    }
  }

  async function restore(node: HistoryNode) {
    note = "";
    if (!current || node.id === current) return;
    let plan: RestorePlan;
    try {
      const [diff, params] = await Promise.all([api.historyDiff(node.id, current), api.params()]);
      plan = restorePlan(diff.diff, normalize(params.parameters) as ParamRow[]);
    } catch (exc) {
      note = `Restore refused: ${(exc as Error).message}`;
      return;
    }
    if (plan.missing.length) {
      const n = plan.missing.length;
      note = `${node.id} has a different model: ${n} parameter${n === 1 ? "" : "s"} exist in only one of the two`
        + ` (${plan.missing.slice(0, 3).join(", ")}${n > 3 ? ", …" : ""}). Make current loads it whole.`;
      offer = node.id;
      return;
    }
    const count = restoreCount(plan);
    if (!count) {
      note = `${node.id} has the working values already.`;
      return;
    }
    onrestore(plan);
    say("comment", `# ${node.id}'s values loaded as ${count} pending edit${count === 1 ? "" : "s"}; Apply sets them`);
  }

  /** The node a refused Restore offers to make current, in the note's button. */
  let offer = $state<string | null>(null);
  $effect(() => {
    if (!note) offer = null;
  });

  async function makeCurrent(id: string) {
    note = "";
    try {
      await api.checkout(id);
      say("call", `ref.checkout(${JSON.stringify(id)})`);
      onmoved();
    } catch (exc) {
      note = (exc as Error).message;
    }
  }

  function openMenu(event: MouseEvent | KeyboardEvent, node: HistoryNode) {
    event.preventDefault();
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const at = event instanceof MouseEvent && event.clientX
      ? { x: event.clientX, y: event.clientY } : { x: box.left + 24, y: box.bottom };
    menu = { at, node };
  }

  function rowKey(event: KeyboardEvent, node: HistoryNode) {
    if (event.key === "ContextMenu" || (event.key === "F10" && event.shiftKey)) openMenu(event, node);
  }

  const call = (id: string) => JSON.stringify(id);

  function menuItems(node: HistoryNode): MenuEntry[] {
    const isHead = node.id === current;
    return [
      { id: "current", label: "Make current", disabled: busy || isHead,
        title: isHead ? "This is the current state"
          : `Make this the working state now\nref.checkout(${call(node.id)})` },
      { id: "branch", label: "Branch from here…", disabled: busy,
        title: `Make this current and name it: the next run starts a branch here\nref.checkout(${call(node.id)})` },
      "-",
      { id: "name", label: "Name…", disabled: busy,
        title: `Give this node a name\np.history.tag(${call(node.id)}, "…")` },
      { id: "note", label: "Note…", disabled: busy,
        title: `Write a note on this node\np.history.annotate(${call(node.id)}, label="…")` },
    ];
  }

  function choose(id: string) {
    const target = menu;
    if (!target) return;
    if (id === "current") void makeCurrent(target.node.id);
    else ask = { at: target.at, node: target.node, verb: id as "name" | "note" | "branch" };
  }

  const askFields = (a: NonNullable<typeof ask>): AskField[] =>
    a.verb === "note"
      ? [{ id: "text", label: "Note", value: a.node.label ?? "" }]
      : [{ id: "text", label: "Name", value: "", mono: true }];

  async function submitAsk(values: Record<string, string>): Promise<string> {
    const a = ask;
    if (!a) return "";
    const text = (values.text ?? "").trim();
    const id = a.node.id;
    try {
      if (a.verb === "note") {
        await api.annotate(id, { label: text });
        say("call", `p.history.annotate(${call(id)}, label=${JSON.stringify(text)})`);
        await load();
      } else if (a.verb === "name") {
        if (!text) return "A name is needed";
        await api.tag(id, text);
        say("call", `p.history.tag(${call(id)}, ${JSON.stringify(text)})`);
        await load();
      } else {
        await api.branch(id, text);
        if (text) say("call", `p.history.tag(${call(id)}, ${JSON.stringify(text)})`);
        say("call", `ref.checkout(${call(id)})`);
        onmoved();
      }
      return "";
    } catch (exc) {
      return (exc as Error).message;
    }
  }
</script>

{#snippet actions(node: HistoryNode)}
  {#if node.kind !== "root"}
    <!-- a curve is a replay, refused while a run is in flight; taking one off is not -->
    <button class="ib act" aria-pressed={compared === node.id} disabled={busy && compared !== node.id}
      title="Overlay this fit on the pattern" onclick={() => compare(node)}>Compare</button>
    <button class="ib act" disabled={busy || node.id === current} title={node.id === current
      ? "This is the current state" : "Load this fit's values as pending edits"}
      onclick={() => restore(node)}>Restore</button>
  {/if}
{/snippet}

{#snippet step(node: HistoryNode)}
  {stepName(node)}{#each node.tags as tag (tag)}<span class="tag">{tag}</span>{/each}{#if node.label}<span
    class="note-text muted">{node.label}</span>{/if}{#if node.id === current}<span class="cur-mark">current</span>{/if}
{/snippet}

<div class="hwrap">
<div class="history">
  {#if error}
    <p class="empty muted">{error}</p>
  {:else if view === "table"}
    <table class="hist">
      <thead>
        <tr><th>Node</th><th>Step</th><th class="num">Rwp</th><th class="num">GoF</th>
          <th class="num">Free</th><th>When</th><th><span class="sr">Actions</span></th></tr>
      </thead>
      <tbody>
        {#each nodes as node (node.id)}
          <tr class:cur={node.id === current} class:cmp={node.id === compared && node.id !== current}
            title={node.api_call} tabindex="0" data-node={node.id}
            oncontextmenu={(e) => openMenu(e, node)} onkeydown={(e) => rowKey(e, node)}>
            <td class="mono">{node.id}</td>
            <td class="what">{@render step(node)}</td>
            <td class="num mono">{rwpText(node.rwp)}</td>
            <td class="num mono">{gofText(node.gof)}</td>
            <td class="num mono">{freeText(node.n_free)}</td>
            <td class="when mono">{whenText(node.created_utc)}</td>
            <td class="acts">{@render actions(node)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <div class="graph" style:--lanes="{drawn.width}px">
      <svg class="rails" width={drawn.width} height={nodes.length * ROW_PX} aria-hidden="true">
        {#each drawn.paths as p (p.key)}
          <path d={p.d} stroke={laneColor(p.lane)} class:merge={p.merge} />
        {/each}
        {#each nodes as node (node.id)}
          {@const dot = drawn.dots.get(node.id)}
          {#if dot}
            <circle cx={dot.x} cy={dot.y} r={node.id === current ? 4.5 : 3.5}
              fill={node.id === current ? laneColor(dot.lane) : "var(--panel)"} stroke={laneColor(dot.lane)} />
          {/if}
        {/each}
      </svg>
      {#each nodes as node (node.id)}
        <div class="grow" class:cur={node.id === current} class:cmp={node.id === compared && node.id !== current}
          title={node.api_call} tabindex="0" role="row" data-node={node.id}
          oncontextmenu={(e) => openMenu(e, node)} onkeydown={(e) => rowKey(e, node)}>
          <span class="mono id">{node.id}</span>
          <span class="what">{@render step(node)}</span>
          <span class="num mono">{rwpText(node.rwp)}</span>
          <span class="acts">{@render actions(node)}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if note}
  <!-- floats over the list, so a refusal appearing moves no row -->
  <div class="hnote" role="status">
    <span>{note}</span>
    {#if offer}
      <button class="ghost" disabled={busy} onclick={() => offer && makeCurrent(offer)}
        title={`Make this the working state now\nref.checkout(${call(offer)})`}>Make current</button>
    {/if}
    <button class="ib" aria-label="Dismiss" onclick={() => (note = "")}>×</button>
  </div>
{/if}
</div>

{#if menu}
  <Menu at={menu.at} items={menuItems(menu.node)} label="Node {menu.node.id}"
    onchoose={choose} onclose={() => (menu = null)} />
{/if}

{#if ask}
  <Ask at={ask.at} label={ask.verb === "note" ? "Note" : ask.verb === "name" ? "Name" : "Branch from here"}
    fields={askFields(ask)} submit={ask.verb === "branch" ? "Branch" : "Save"}
    onsubmit={submitAsk} onclose={() => (ask = null)} />
{/if}

<style>
  .hwrap {
    position: relative;
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  .history {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .empty {
    margin: 0;
    padding: 8px 12px;
  }

  table.hist {
    width: 100%;
    border-collapse: collapse;
  }

  .hist th {
    position: sticky;
    top: 0;
    z-index: 1;
    height: 30px;
    padding: 0 12px 0 0;
    background: var(--bg);
    font-weight: 500;
    color: var(--muted);
    text-align: left;
    white-space: nowrap;
    border-bottom: 1px solid var(--line);
  }

  .hist td {
    height: 30px;
    padding: 0 12px 0 0;
    border-top: 1px solid var(--line);
    white-space: nowrap;
  }

  .hist td:first-child,
  .hist th:first-child {
    padding-left: 12px;
  }

  .hist .num {
    text-align: right;
  }

  .hist tr.cur td,
  .graph .grow.cur {
    background: color-mix(in srgb, var(--accent) 12%, var(--panel));
  }

  .hist tr.cmp td,
  .graph .grow.cmp {
    background: color-mix(in srgb, var(--hover) 60%, transparent);
  }

  .what {
    white-space: normal;
    min-width: 14em;
  }

  .when {
    color: var(--muted);
  }

  .acts {
    text-align: right;
  }


  .act[aria-pressed="true"] {
    border-color: var(--line-strong);
    background: var(--hover);
  }

  .cur-mark,
  .tag,
  .note-text {
    margin-left: 8px;
  }

  .cur-mark {
    color: var(--accent-ink);
  }

  .tag {
    font-family: var(--mono-family);
  }

  tr:focus-visible,
  .grow:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .graph {
    position: relative;
    padding-left: 12px;
  }

  .rails {
    position: absolute;
    top: 0;
    left: 12px;
    overflow: visible;
  }

  .rails path {
    fill: none;
    stroke-width: 1.5;
  }

  .rails path.merge {
    stroke-dasharray: 3 3;
  }

  .rails circle {
    stroke-width: 1.5;
  }

  .grow {
    display: grid;
    grid-template-columns: var(--lanes) 6ch minmax(14em, 1fr) 9ch auto;
    align-items: center;
    column-gap: 12px;
    height: 30px;
    padding-right: 12px;
  }

  .grow > .id {
    grid-column: 2;
  }

  .grow > .num {
    text-align: right;
  }

  .hnote {
    position: absolute;
    right: 12px;
    bottom: 8px;
    left: 12px;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 4px 4px 12px;
    border: 1px solid var(--line);
    border-radius: var(--r-control);
    background: var(--panel);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--fg) 14%, transparent);
  }

  .hnote > span {
    flex: 1;
  }
</style>
