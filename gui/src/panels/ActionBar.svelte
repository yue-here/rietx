<script lang="ts">
  /**
   * The model panel's one row of actions (WP-2123).
   *
   * The maintainer's ruling of 2026-11-07: the panel ends in Apply and "Apply
   * and refine", and refine offers one cycle or the staged plan; the bar merge
   * approved the same day makes it one row. Left to right: the refine choice,
   * the pending count, Revert, Apply, and the filled primary.
   *
   * Two rules keep the row still, because no click may move the layout unless
   * it asks to (ruled 2026-11-07). The pending count has a slot as wide as its
   * longest text, so its appearing moves nothing. And the primary reserves the
   * width of its longer label, so "Refine" becoming "Apply and refine" on the
   * first edit pushes no neighbour.
   *
   * While the graphs are hidden the bar also carries the fit's statistics,
   * right of Refine (WP-2210, the maintainer's "try B" of 2026-11-09), handed
   * in as `stats`. They come and go with the collapse click, which asks for a
   * layout change, and their slot reserves its widest content, so a fit
   * finishing moves nothing. A third group, so a narrow bar wraps it whole.
   *
   * The bar owns no state of its own beyond the refine choice: the pending
   * edits are the Parameters panel's, and the run is the shell's. It reports
   * presses and lets those owners act, `Splitter.svelte`'s rule.
   */
  let {
    touched = 0,
    invalid = "",
    busy = false,
    blocked = null,
    mode = $bindable("plan"),
    onapply = () => {},
    onrevert = () => {},
    onrefine = () => {},
    stats = null,
  }: {
    /** how many edits the Parameters panel holds */
    touched?: number;
    /** the first invalid edit's reason, or "" while every edit is valid */
    invalid?: string;
    busy?: boolean;
    /** why a run is refused before it starts (a project with no phase) */
    blocked?: string | null;
    /** `cycle`: one stage on the ticked parameters; `plan`: the project's plan */
    mode?: "cycle" | "plan";
    onapply?: () => void;
    onrevert?: () => void;
    onrefine?: () => void;
    /** the fit's statistics, drawn beside Refine while the graphs are hidden */
    stats?: import("svelte").Snippet | null;
  } = $props();

  const CHOICES = [
    { id: "cycle", label: "One cycle" },
    { id: "plan", label: "Staged plan" },
  ] as const;

  const count = $derived(
    touched ? `${touched} pending ${touched === 1 ? "edit" : "edits"}` : "",
  );
  // The slot shows a short message it always has room for, and an invalid
  // edit's reason, which has no length limit, rides in the slot's tooltip and
  // in the invalid cell's own. A cut message was the defect this replaced: a
  // reason clipped at the slot's edge, which no click could widen.
  const note = $derived(invalid ? "invalid edit" : count);
</script>

<!-- Groups that wrap as wholes: the refine choice, then Refine's group held to
     the right, and the fit's statistics after it while the graphs are hidden.
     Every width in it is reserved, so where the row breaks depends on the
     panel's width and the graphs' collapse alone, never on any other click. -->
<div class="actions" role="toolbar" aria-label="actions">
  <div class="segmented" role="group" aria-label="refine">
    {#each CHOICES as choice (choice.id)}
      <button class:on={mode === choice.id} aria-pressed={mode === choice.id}
        onclick={() => (mode = choice.id)}>{choice.label}</button>
    {/each}
  </div>
  <div class="go">
    <span class="pending" class:bad={!!invalid} title={invalid || null}>{note}</span>
    <button class="ghost" disabled={!touched} onclick={onrevert}>Revert</button>
    <button class="ghost" disabled={busy || !touched || !!invalid} onclick={onapply}>Apply</button>
    <button class="refine" disabled={busy || !!invalid || !!blocked} title={blocked}
      onclick={onrefine}>{touched ? "Apply and refine" : "Refine"} <kbd>⌘⏎</kbd></button>
  </div>
  {#if stats}<div class="fit" role="group" aria-label="fit statistics">{@render stats()}</div>{/if}
</div>

<style>
  .actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--s2) var(--s3);
    padding: var(--s2) var(--s3);
    border-top: 1px solid var(--line);
    flex: 0 0 auto;
    font-size: var(--text-sm);
    white-space: nowrap;
  }

  .go {
    display: flex;
    align-items: center;
    gap: var(--s2);
    margin-left: auto;
  }

  /* as wide as the longest message, "99 pending edits", which
     tests/test_gui_layout_browser.py measures in the slot's own font, so no
     message is cut and none grows the row */
  .pending {
    width: 16ch;
    /* one line tall while empty, so the first edit grows nothing */
    min-height: 1lh;
    text-align: right;
    color: var(--muted);
  }

  .pending.bad {
    color: var(--bad);
  }

  /* the longer label's width, so the first edit moves no neighbour */
  .refine {
    min-width: 19ch;
  }
</style>
