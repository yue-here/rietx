<script lang="ts">
  /**
   * The model panel's one row of actions in the rebuild (WP-2216, rows 18-24
   * of WP-2214's inventory), drawn as the prototype draws it: the word
   * Refine and the choice of one cycle or the staged plan on the left; the
   * pending count, Revert, Apply and the one filled button on the right.
   *
   * It is today's `panels/ActionBar.svelte` with one addition, which is why
   * it is a copy (WP-2214 § Two front ends: a shared panel is not edited for
   * the new page's sake). While the graphs are hidden the bar carries Rwp and
   * GoF before the pending count (the maintainer's ruling of 2026-11-09, "try
   * B"), each in a slot as wide as its widest value, and "Not a fit yet" in the
   * danger colour where the report's gate says so (#1518's slot device).
   *
   * Every slot is reserved, so a first edit, a run landing or the graphs
   * hiding moves no neighbour (`gui/STYLE.md` principle 4).
   */
  let {
    touched = 0,
    invalid = "",
    busy = false,
    blocked = null,
    stats = null,
    stages = null,
    mode = $bindable("plan"),
    onapply = () => {},
    onrevert = () => {},
    onrefine = () => {},
  }: {
    touched?: number;
    invalid?: string;
    busy?: boolean;
    blocked?: string | null;
    /** the fit's statistics, shown only while the graphs are hidden; null otherwise */
    stats?: { rwp: number | null; gof: number | null; immature: boolean } | null;
    /** how many stages the project's plan declares; null where it declares none */
    stages?: number | null;
    mode?: "cycle" | "plan";
    onapply?: () => void;
    onrevert?: () => void;
    onrefine?: () => void;
  } = $props();

  // the plan's choice names its length, as the prototype's does
  const CHOICES = $derived([
    { id: "cycle", label: "One cycle", title: "One least-squares cycle on what is ticked" },
    { id: "plan", label: stages ? `Staged plan, ${stages} stage${stages === 1 ? "" : "s"}` : "Staged plan",
      title: "The project's staged plan" },
  ] as const);

  const count = $derived(touched ? `${touched} pending` : "");
  const note = $derived(invalid ? "invalid edit" : count);
  const key = typeof navigator !== "undefined" && /Mac|iP/.test(navigator.platform ?? "")
    ? "⌘Enter" : "Ctrl+Enter";
</script>

<div class="actions" role="toolbar" aria-label="Actions">
  <span class="vg">Refine
    <span class="segmented" role="group" aria-label="Refine">
      {#each CHOICES as choice (choice.id)}
        <button class:on={mode === choice.id} aria-pressed={mode === choice.id}
          title={choice.title} onclick={() => (mode = choice.id)}>{choice.label}</button>
      {/each}
    </span>
  </span>
  <span class="go">
    {#if stats}
      <span class="stat">Rwp <span class="num rwp">{stats.rwp == null ? "" : `${(stats.rwp * 100).toFixed(2)} %`}</span></span>
      <span class="stat">GoF <span class="num gof">{stats.gof == null ? "" : stats.gof.toFixed(2)}</span></span>
      <span class="judge">{stats.immature ? "Not a fit yet" : ""}</span>
    {/if}
    <span class="pending" class:bad={!!invalid} title={invalid || null}>{note}</span>
    <button class="ghost" disabled={!touched} onclick={onrevert}>Revert</button>
    <button class="ghost" disabled={busy || !touched || !!invalid} onclick={onapply}>Apply</button>
    <button class="refine" disabled={busy || !!invalid || !!blocked}
      title={blocked ?? key} onclick={onrefine}>{touched ? "Apply and refine" : "Refine"}</button>
  </span>
</div>

<style>
  .actions {
    flex: none;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 12px;
    min-height: 44px;
    padding: 6px 12px;
    border-top: 1px solid var(--line);
    white-space: nowrap;
  }

  .vg {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--muted);
    font-size: var(--text-sm);
  }

  .go {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }

  .stat {
    color: var(--muted);
    font-size: var(--text-sm);
  }

  /* each number's slot as wide as its widest value, so a run landing moves nothing */
  .num {
    display: inline-block;
    font-family: var(--mono-family);
    color: var(--fg);
    text-align: right;
  }

  .rwp {
    width: 8ch;
  }

  .gof {
    width: 5ch;
  }

  .judge {
    width: 11ch;
    color: var(--bad);
    font-size: var(--text-sm);
  }

  /* as wide as "99 pending", so the first edit grows nothing */
  .pending {
    width: 11ch;
    min-height: 1lh;
    text-align: right;
    color: var(--muted);
    font-size: var(--text-sm);
  }

  .pending.bad {
    color: var(--bad);
  }

  /* the longer label's width, so the first edit moves no neighbour */
  .refine {
    min-width: 16ch;
  }
</style>
