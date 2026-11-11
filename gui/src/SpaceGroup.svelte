<script lang="ts">
  /**
   * A space-group symbol, typeset (WP-2131; the maintainer's ruling of
   * 2026-11-08). The pieces are `lib/symmetry.ts:symbolTokens`'s, so the
   * typesetting is tested without a DOM; the face is app.css's `.sg`.
   */
  import { symbolTokens } from "./lib/symmetry";

  let { symbol }: { symbol: string } = $props();
  const parts = $derived(symbolTokens(symbol));
</script>

<span class="sg">{#each parts.tokens as t, i (i)}{#if t.kind === "bar"}<span
  class="bar">{t.text}</span>{:else if t.kind === "screw"}{t.text}<sub>{t.sub}</sub>{:else if t.kind
  === "letter"}<i>{t.text}</i>{:else}{t.text}{/if}{/each}</span>{#if parts.ext}<span
  class="muted"> :{parts.ext}</span>{/if}
