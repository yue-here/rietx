<script lang="ts">
  /**
   * A figure's four exports as a row of buttons, for the Series panel
   * (WP-1461, D6). The work is `lib/exports.ts`, which the Pattern tab's view
   * menu calls too (WP-2213); the line beside the buttons says what happened.
   */
  import type { Group } from "rxplot";
  import { exportFigure, type ExportKind } from "../lib/exports";

  let { figure, name }: {
    /** the figure on screen, or null before one is drawn */
    figure: () => Group | null;
    /** the file name, without its extension */
    name: () => string;
  } = $props();

  let said = $state("");

  const act = (kind: ExportKind) => async () => {
    said = await exportFigure(kind, figure(), name());
  };
  const png = act("png");
  const svg = act("svg");
  const image = act("image");
  const data = act("data");
</script>

<div class="exports" role="group" aria-label="export">
  <button class="ghost" onclick={png} title="save the figure as a PNG, as drawn">PNG</button>
  <button class="ghost" onclick={svg} title="save the figure as an SVG, redrawn as vectors">SVG</button>
  <button class="ghost" onclick={image} title="copy the figure to the clipboard as a PNG">copy image</button>
  <button class="ghost" onclick={data} title="copy what is in view as tab-separated columns">copy data</button>
  {#if said}<span class="said muted">{said}</span>{/if}
</div>

<style>
  .exports {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
  }
</style>
