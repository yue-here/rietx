<script lang="ts">
  /**
   * The history worktree: every move this refinement made, and the four verbs
   * that move around in it.
   *
   * A *view*, with no history semantics of its own — the DAG, the checkout, the
   * tag and the annotation are all WP-1008 routes over the v0.2 tree. Three of its
   * rules come from that tree rather than from taste. **A branch is not created,
   * it appears**: there are no moving refs here, only `head` and tags, so
   * "branch" is checkout + tag and the lanes drawn are where the tree actually
   * divided (`lib/history.ts`). **A node carries no parameter values** — ~10 kB of
   * state per node is deliberately absent from the payload — so comparing two
   * nodes asks `/api/history/diff` instead of subtracting two states the client
   * does not have. And **a checkout discards the fitted curves**, which is not a
   * failure: the result described the values the checkout just replaced, so the
   * shell is told to refetch and the plot says so.
   *
   * A node's Rwp is its *cached* metric, measured on the model the stage started
   * from; `replay` recomputes at the values it ended on and can differ marginally.
   * That gap is a staleness signal, not a regression, so the badge shows the
   * difference against the parent and claims nothing about significance.
   */
  import { ApiError, api } from "../api";
  import {
    DIFF_CAP, PATH_CHARS, PERCENT_CHARS, VALUE_CHARS, diffRows, edgeSegments,
    formatDelta, formatPercent, formatSide, laneColor, layout, nodeLabel,
    passChips, passVerdict, isDiscarded, rwpDelta, type Edge, type HistoryNode,
  } from "../lib/history";

  let {
    head = null,
    busy = false,
    say = (_line: string) => {},
    onmoved = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    say?: (line: string) => void;
    onmoved?: () => void;
  } = $props();

  const ROW = 26;
  const LANE = 14;

  let nodes = $state<HistoryNode[]>([]);
  let error = $state("");
  let selected = $state<string>("");
  let against = $state<string>("");
  let diff = $state<Record<string, Array<number | string | null>> | null>(null);
  let metrics = $state<any[]>([]);
  let query = $state("");
  let name = $state("");
  /** true once the user has picked a row, which stops the selection following HEAD */
  let pinned = $state(false);

  const graph = $derived(layout(nodes));
  const byId = $derived(new Map(nodes.map((n) => [n.id, n])));
  const rail = $derived(graph.lanes * LANE + 6);
  const node = $derived(byId.get(selected) ?? null);
  const rows = $derived(diff === null ? [] : diffRows(diff, query));

  async function load() {
    try {
      const payload = await api.history();
      nodes = payload.nodes;
      // follow HEAD until the user picks a row, then stay put: a run must not
      // move a deliberate selection, and before there is one the interesting
      // node is the one the working state stands at
      if (!pinned || !byId.has(selected)) selected = payload.head ?? selected;
      error = "";
    } catch (exc) {
      nodes = [];
      error = exc instanceof ApiError && exc.empty ? "" : (exc as Error).message;
    }
  }

  // the head is the working state, so it is the one signal that covers a run, a
  // checkout and an edit made in another panel (WP-1005)
  $effect(() => {
    void head;
    load();
  });

  function refused(exc: unknown): string {
    return exc instanceof ApiError && exc.busy
      ? "a run is in flight — the history is read-only until it ends"
      : (exc as Error).message;
  }

  async function checkout(id: string) {
    try {
      say(`ref.checkout(${JSON.stringify(id)})`);
      await api.checkout(id);
      error = "";
      onmoved();
    } catch (exc) {
      error = refused(exc);
    }
  }

  async function tag(id: string) {
    const label = name.trim();
    if (!label) return;
    try {
      say(`tree.tag(${JSON.stringify(id)}, ${JSON.stringify(label)})`);
      await api.tag(id, label);
      name = "";
      error = "";
      await load();
    } catch (exc) {
      error = refused(exc);
    }
  }

  /** Checkout **and** name: what "branch" means in a DAG with no moving refs. */
  async function branch(id: string) {
    const label = name.trim() || `from-${id}`;
    try {
      say(`ref.checkout(${JSON.stringify(id)}); tree.tag(${JSON.stringify(id)}, ${JSON.stringify(label)})`);
      await api.branch(id, label);
      name = "";
      error = "";
      onmoved();
      await load();
    } catch (exc) {
      error = refused(exc);
    }
  }

  async function annotate(id: string, label: string) {
    try {
      say(`tree.annotate(${JSON.stringify(id)}, label=${JSON.stringify(label)})`);
      await api.annotate(id, { label });
      error = "";
      await load();
    } catch (exc) {
      error = refused(exc);
    }
  }

  async function compare(a: string, b: string) {
    try {
      say(`tree.diff(${JSON.stringify(a)}, ${JSON.stringify(b)})`);
      const [d, c] = await Promise.all([api.historyDiff(a, b), api.historyCompare([a, b])]);
      diff = d.diff;
      metrics = c.rows;
      error = "";
    } catch (exc) {
      diff = null;
      error = refused(exc);
    }
  }

  /** Select a node, keeping any open comparison pointed at the new pair. */
  function select(id: string) {
    selected = id;
    pinned = true;
    if (against && against !== id) compare(id, against);
    else diff = null;
  }

  function pickAgainst(id: string) {
    if (id === selected) return;   // a node compared with itself is an empty diff
    against = against === id ? "" : id;
    if (against) compare(selected, against);
    else diff = null;
  }

  function laneX(lane: number): number {
    return 8 + lane * LANE;
  }

  function rowY(row: number): number {
    return row * ROW + ROW / 2;
  }

  /** An edge as one polyline: `edgeSegments` in pixels (WP-1217).
   *
   * Straight pieces and no curve at all.  The Bézier this replaced spanned the
   * whole gap between two rows, so a child ten rows below its parent got a
   * shallow diagonal nobody can follow — the user's report, and the reason the
   * lane algorithm now reserves a lane for the arc's whole span. */
  function edgePath(edge: Edge): string {
    const parts = edgeSegments(edge);
    let d = `M ${laneX(parts[0].fromLane)} ${rowY(parts[0].fromRow)}`;
    for (const part of parts) d += ` L ${laneX(part.toLane)} ${rowY(part.toRow)}`;
    return d;
  }

  function pct(value: number | null): string {
    return value === null || value === undefined ? "—" : `${(value * 100).toFixed(2)}%`;
  }
</script>

<section>
  <div class="bar">
    <span class="muted">
      {nodes.length} node{nodes.length === 1 ? "" : "s"}
      {#if graph.lanes > 1}· {graph.lanes} lanes{/if}
    </span>
    <span class="spacer"></span>
    <span class="muted" title="click a node to select it, then ⇄ on another to compare">
      select · ⇄ compare
    </span>
  </div>

  {#if error}<p class="bad">{error}</p>{/if}

  <div class="scroller">
    {#if !nodes.length}
      <p class="muted pad">No history yet — the tree exists from the project's
        first node, so this fills in as soon as one is open.</p>
    {:else}
      <div class="graph" style:padding-left="{rail}px" style:--row="{ROW}px">
        <svg class="rail" width={rail} height={nodes.length * ROW} aria-hidden="true">
          {#each graph.edges as edge (edge.from + edge.to)}
            <path d={edgePath(edge)} class:merge={edge.merge}
              style:--lane={laneColor(edge.lane)} />
          {/each}
          {#each graph.placed as placed (placed.node.id)}
            <circle cx={laneX(placed.lane)} cy={rowY(placed.row)}
              r={placed.node.id === head ? 4.5 : 3}
              class:head={placed.node.id === head}
              class:selected={placed.node.id === selected}
              class:discarded={isDiscarded(placed.node)}
              style:--lane={laneColor(placed.lane)} />
          {/each}
        </svg>

        {#each graph.placed as placed (placed.node.id)}
          {@const n = placed.node}
          {@const delta = rwpDelta(n, byId)}
          <div class="node" class:on={n.id === selected} class:other={n.id === against}
            class:discarded={isDiscarded(n)}>
            <button class="pick" onclick={() => select(n.id)}
              title={n.api_call}>
              <span class="id mono muted">{n.id}</span>
              <span class="what">{nodeLabel(n)}</span>
              {#if n.id === head}<span class="chip accent">HEAD</span>{/if}
              {#each passChips(n) as chip (chip.text)}
                <span class="chip {chip.tone}" title={chip.title}>{chip.text}</span>
              {/each}
              {#each n.tags as label (label)}<span class="chip">{label}</span>{/each}
              {#if n.n_diagnostics}
                <span class="chip warn" title="{n.n_diagnostics} diagnostic(s)">
                  ⚠ {n.n_diagnostics}</span>
              {/if}
              <span class="spacer"></span>
              {#if n.rwp !== null}
                <span class="rwp mono tabular">{pct(n.rwp)}</span>
                {#if delta !== null}
                  <span class="delta mono tabular" class:better={delta < 0}
                    class:worse={delta > 0}
                    title="against its first parent; a node's metrics are as-optimised">
                    {delta < 0 ? "▾" : "▴"}{Math.abs(delta * 100).toFixed(2)}
                  </span>
                {/if}
              {:else}
                <span class="rwp muted">—</span>
              {/if}
            </button>
            <button class="ghost" title="compare with the selected node"
              onclick={() => pickAgainst(n.id)}>⇄</button>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  {#if node}
    <footer>
      <p class="call mono" title="this node's equivalent public-API call">{node.api_call}</p>
      <p class="muted tabular">
        {node.kind}{node.status ? ` · ${node.status}` : ""}
        {#if node.n_iterations}· {node.n_iterations} iter{/if}
        {#if node.n_free !== null}· {node.n_free} free{/if}
        {#if node.gof !== null}· GoF {node.gof.toFixed(3)}{/if}
        · {node.created_utc}
      </p>
      {#if passVerdict(node)}<p class="muted">{passVerdict(node)}.</p>{/if}
      {#each node.diagnostics as d (d.code + d.message)}
        <p class="diag" data-level={d.level}>
          <span class="mono">{d.code}</span>
          {#if d.where?.length}<span class="mono muted">{d.where.join(" ")}</span>{/if}
          {d.message}
        </p>
      {/each}
      <div class="verbs">
        <input class="mono" placeholder="tag or branch name" bind:value={name}
          disabled={busy} />
        <button class="ghost" disabled={busy || node.id === head}
          onclick={() => checkout(node.id)}
          title="restore this node's state as the working state">Checkout</button>
        <button class="ghost" disabled={busy || !name.trim()}
          onclick={() => tag(node.id)}>Tag</button>
        <button class="ghost" disabled={busy}
          onclick={() => branch(node.id)}
          title="checkout and name the fork point — this DAG has no moving refs">
          Branch</button>
        <button class="ghost" disabled={busy || !name.trim()}
          onclick={() => annotate(node.id, name.trim())}
          title="rename this node">Label</button>
      </div>
      {#if node.id !== head}
        <p class="muted">Checking out discards the fitted curves: they described
          the values this would replace. Re-run to get a result back.</p>
      {/if}
    </footer>
  {/if}

  {#if diff !== null}
    <!-- the three column widths are `lib/history.ts`'s, in the unit its
         formatters keep their promise in: one digit of the mono family -->
    <div class="diff" style:--w-val="{VALUE_CHARS}ch" style:--w-pct="{PERCENT_CHARS}ch"
      style:--w-path="{PATH_CHARS}ch">
      <div class="bar">
        <strong class="mono">{selected} → {against}</strong>
        <span class="spacer"></span>
        <input class="mono" placeholder="filter paths" bind:value={query} />
        <button class="ghost" onclick={() => { diff = null; against = ""; }}>×</button>
      </div>
      {#if metrics.length === 2}
        <p class="muted tabular">
          Rwp {pct(metrics[0].rwp)} → {pct(metrics[1].rwp)}
          · free {metrics[0].n_free ?? "—"} → {metrics[1].n_free ?? "—"}
          · {metrics[0].action} → {metrics[1].action}
        </p>
      {/if}
      <p class="muted">
        {rows.length} path{rows.length === 1 ? "" : "s"} differ — the route returns
        only what changed, so there is nothing to filter out. Ranked by |Δ| against
        the larger of the two values, an appearing parameter first{
          rows.length > DIFF_CAP ? `; showing the first ${DIFF_CAP}` : ""}.
      </p>
      <div class="rows">
        <div class="drow heads">
          <span class="path">path</span>
          <span class="val">{selected}</span>
          <span class="val">{against}</span>
          <span class="val">Δ</span>
          <span class="pct">Δ %</span>
        </div>
        {#each rows.slice(0, DIFF_CAP) as row (row.path)}
          <div class="drow">
            <span class="path" title={row.path}>{row.path}</span>
            <span class="val tabular muted">{formatSide(row.path, row.a)}</span>
            <span class="val tabular">{formatSide(row.path, row.b)}</span>
            <span class="val tabular">{formatDelta(row.path, row.delta)}</span>
            <span class="pct tabular muted">{formatPercent(row.a, row.delta)}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
  }

  /* a row of controls, so it is control-sized */
  .bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px 4px;
    font-size: var(--text-sm);
  }

  .spacer {
    flex: 1 1 auto;
  }

  .scroller {
    flex: 1 1 auto;
    overflow: auto;
    border-top: 1px solid var(--line);
    min-height: 90px;
  }

  .pad {
    padding: 10px;
  }

  .graph {
    position: relative;
  }

  svg.rail {
    position: absolute;
    left: 0;
    top: 0;
  }

  /* `--lane` is the ink `lib/history.ts:laneColor` composed for this lane, set
     inline per element — a custom property rather than a `stroke`, so the
     selected and HEAD rules below still win the cascade instead of losing to an
     inline declaration. */
  svg.rail path {
    fill: none;
    stroke: var(--lane, var(--line));
    stroke-width: 1.5;
  }

  svg.rail path.merge {
    stroke-dasharray: 3 2;
  }

  svg.rail circle {
    fill: var(--panel);
    stroke: var(--lane, var(--muted));
    stroke-width: 1.5;
  }

  svg.rail circle.selected {
    stroke: var(--accent);
  }

  svg.rail circle.discarded {
    opacity: 0.45;
  }

  svg.rail circle.head {
    fill: var(--accent);
    stroke: var(--accent);
  }

  .node {
    display: flex;
    align-items: center;
    height: var(--row);
    box-sizing: border-box;
    padding-right: 6px;
  }

  .node.on {
    background: color-mix(in srgb, var(--accent) 12%, transparent);
  }

  /* a pass the alternation did not keep: still there, still selectable, but not
     where the head is */
  .node.discarded .what,
  .node.discarded .rwp,
  .node.discarded .delta {
    opacity: 0.55;
  }

  .node.other {
    background: color-mix(in srgb, var(--warn) 12%, transparent);
  }

  /* the `.pick` register (app.css) laid out for this list */
  .pick {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 var(--s2);
    height: 100%;
  }

  .id {
    flex: 0 0 auto;
    font-size: var(--text-xs);
  }

  .what {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .chip {
    flex: 0 0 auto;
  }

  .rwp {
    font-size: var(--text-sm);
    flex: 0 0 auto;
  }

  .delta {
    font-size: var(--text-xs);
    flex: 0 0 44px;
    text-align: right;
    color: var(--muted);
  }

  /* Green is a *judgement* and only the Rwp badge is entitled to one: a
     parameter difference has no better side, which is what the old
     `class:better={delta !== 0}` on every compare row was claiming. */
  .delta.better {
    color: var(--ok);
  }

  .delta.worse {
    color: var(--warn);
  }

  footer {
    border-top: 1px solid var(--line);
    padding: 5px 8px 7px;
    flex: 0 0 auto;
  }

  footer p {
    margin: 3px 0 0;
  }

  .call {
    margin: 0 0 3px;
    font-size: var(--text-sm);
    overflow: auto;
    white-space: nowrap;
    color: var(--fg);
  }

  .diag {
    margin: 2px 0;
    color: var(--muted);
  }

  .diag[data-level="warning"] {
    color: var(--warn);
  }

  .verbs {
    display: flex;
    gap: 5px;
    align-items: center;
    margin-top: 5px;
  }

  input {
    font: var(--mono);
    flex: 1 1 auto;
    min-width: 0;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
    padding: 2px 5px;
  }

  .diff {
    border-top: 1px solid var(--line);
    flex: 0 0 auto;
    max-height: 45%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .diff .rows {
    overflow: auto;
  }

  .diff p {
    padding: 0 8px;
    margin: 1px 0;
  }

  /* The family is on the *row*, not on each cell, because the columns are
     measured in `ch` and `ch` is the element's own zero: a header cell that was
     not mono made its track 4 px wider than the mono one below it (measured in
     Chrome, 1414 against 1417). A `ch` column is a shared column only while
     every cell in it is one font at one size. */
  .drow {
    --cell-gap: 6px;
    --row-pad: 8px;
    display: flex;
    gap: var(--cell-gap);
    padding: 0 var(--row-pad);
    /* Every row is at least the floor its own columns declare, so when `.rows`
       scrolls sideways each row's box scrolls with it. Without a floor the row
       is exactly the scroller's width and the sticky header's background stops
       at the visible edge, letting the data travel under its last columns; with
       `min-content` instead, a row is as wide as its own longest path, so the
       rows disagree with each other *and* with the header, and the path stops
       ellipsising (both measured in Chrome at a 380 px sidebar: header 421 px
       against a body row's 476, scroll extent set by the longest dot-path).
       Every number here is stated once — the widths in `lib/history.ts`, the
       gap and the padding above — and the counts are the row's own shape. */
    min-width: calc(var(--w-path) + 3 * var(--w-val) + var(--w-pct)
                    + 4 * var(--cell-gap) + 2 * var(--row-pad));
    font-family: var(--mono-family);
    font-size: var(--text-sm);
    line-height: 18px;
  }

  /* The header is inside the scroller, so it has to be opaque or the rows
     travel under it (WP-1032's sticky-header finding, one panel over) — and it
     keeps `--text-sm`, the size of everything on a cell's row, for the reason
     above: at `--text-xs` its tracks came out narrower and the header sat
     inside its own columns by a growing offset (1266/1341/1420 against
     1252/1335/1417). */
  .drow.heads {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--panel);
    color: var(--muted);
  }

  /* the column that gives: below `--w-path` the row stops squeezing and the
     scroller takes over, so the numbers never lose their tracks */
  .drow .path {
    flex: 1 1 auto;
    min-width: var(--w-path);
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    direction: rtl;
    text-align: left;
  }

  /* A column is scanned, so its width is a promise and the formatter keeps it:
     `--w-val` and `--w-pct` are `VALUE_CHARS`/`PERCENT_CHARS` handed down in
     `ch`, and `formatSide` falls back to exponential rather than write anything
     longer.  Before WP-1217 these were one 74 px rule over four cells of
     `toPrecision`, which chooses fixed or exponential per value — so a decimal
     point and a mantissa shared a column. */
  .drow .val {
    flex: 0 0 var(--w-val);
    text-align: right;
  }

  .drow .pct {
    flex: 0 0 var(--w-pct);
    text-align: right;
  }

  .bad {
    padding: 0 8px;
    margin: var(--s1) 0;
  }
</style>
