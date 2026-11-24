<script lang="ts">
  /**
   * The mark a held row wears where its vary checkbox would be
   * (`lib/table.ts:heldGlyph`). Text marks (`=`, `≈`, `·`) are typed; the
   * padlock is drawn (`Padlock.svelte`), in the accent's text role for a hold,
   * which `unhold` can lift, and in the surrounding muted ink for a lock,
   * which nothing can.
   */
  import Padlock from "./Padlock.svelte";
  import { PADLOCK, heldGlyph, heldKind, type ParamRow } from "./lib/table";

  let { row }: { row: ParamRow } = $props();
  const glyph = $derived(heldGlyph(row));
  const hold = $derived(heldKind(row) === "hold");
</script>

{#if glyph === PADLOCK}<span class="lock" class:hold
  ><Padlock label={hold ? "held" : "locked"} /></span
>{:else}{glyph}{/if}

<style>
  .lock {
    display: inline-flex;
    align-items: center;
  }

  .hold {
    color: var(--accent-ink);
  }
</style>
