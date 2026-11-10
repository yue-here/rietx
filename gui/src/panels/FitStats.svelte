<script lang="ts">
  /**
   * The fit's statistics: Rwp, GoF and the report's judgement (WP-2210).
   *
   * One component for the two homes the maintainer's layout gives them. While
   * the graphs show they sit on the graph title line (WP-2123); while the
   * graphs are hidden they sit in the action bar beside Refine (the ruling of
   * 2026-11-09, "try B"). Drawn once, so the same fact reads the same way in
   * both (`gui/STYLE.md` principle 3).
   *
   * The judgement is the report's `maturity`, quoted and never re-derived
   * (WP-1029 item c). It is a fact, so it is words in the state colour with no
   * border (`gui/STYLE.md` § Components), and no number is coloured by it
   * (§ Colour). Its message is one click away through `<Help>` (WP-1203).
   *
   * With `reserve` (the bar), every number has a slot as wide as its widest
   * value, a dash fills it before a fit, and the judgement's words keep their
   * room while the fit is mature, invisibly, so a fit finishing moves nothing
   * in the bar (principle 4).
   */
  import Help from "../Help.svelte";

  let {
    rwp = null,
    gof = null,
    immature = false,
    message = "",
    reserve = false,
  }: {
    /** Rwp as a fraction, or null before any fit */
    rwp?: number | null;
    gof?: number | null;
    /** the report's maturity gate (`result.maturity.immature`) */
    immature?: boolean;
    /** the report's own sentence about it */
    message?: string;
    /** keep every slot's room while it is empty, so nothing that fills it moves */
    reserve?: boolean;
  } = $props();
</script>

<span class="fitstats">
  <span class="stat">Rwp <strong class="num pct mono tabular" class:slot={reserve}>{rwp === null ? "—"
    : `${(rwp * 100).toFixed(3)}%`}</strong></span>
  {#if gof !== null || reserve}
    <span class="stat muted">GoF <span class="num mono tabular" class:slot={reserve}>{gof === null ? "—"
      : gof.toFixed(3)}</span></span>
  {/if}
  {#if immature}
    <span class="fact bad"><Help text={message} title="Not a fit yet">not a fit yet</Help></span>
  {:else if reserve}
    <span class="fact reserved" aria-hidden="true">not a fit yet</span>
  {/if}
</span>

<style>
  .fitstats {
    display: inline-flex;
    align-items: baseline;
    gap: var(--s3);
    white-space: nowrap;
  }

  /* With `reserve`, each slot holds the widest plain number `gui/STYLE.md`
     writes: "9999.999" for GoF, and "9999.999%" for Rwp, which passes 1000 % on
     a model that has not met its data (measured 1067 % before a synthetic
     project's first scale). The title line reserves nothing: its statistics
     are held right, so a slot there would add a gap and hold nothing still. */
  .slot {
    display: inline-block;
    min-width: 8ch;
  }

  .slot.pct {
    min-width: 9ch;
  }

  .reserved {
    visibility: hidden;
  }
</style>
