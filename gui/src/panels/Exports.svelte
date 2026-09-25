<script lang="ts">
  /**
   * A figure's four exports (WP-1461, D6): a PNG and an SVG file, the picture
   * on the clipboard, and what is in view as tab-separated columns. The chart
   * module does the work (`png`, `svg`, `copyImage`, `tsv`), each on the
   * figure as drawn now, at the reader's zoom. This is its place in a control
   * row, and the line beside it says what happened, a refusal included, since
   * a clipboard can refuse.
   *
   * Nothing here is imported at boot. The chart module is a chunk the first
   * draw fetches, and a static import here put it on the boot path, so
   * `download` comes from it on a press, when a figure has already loaded it.
   * svgcanvas is imported on the first SVG, a chunk that a session which never
   * exports never fetches.
   */
  import type { Group } from "rxplot";

  async function download(blob: Blob, file: string): Promise<void> {
    (await import("rxplot")).download(blob, file);
  }

  let { figure, name }: {
    /** the figure on screen, or null before one is drawn */
    figure: () => Group | null;
    /** the file name, without its extension */
    name: () => string;
  } = $props();

  let said = $state("");

  async function act(label: string, run: (fig: Group) => Promise<string>): Promise<void> {
    const fig = figure();
    if (!fig) {
      said = "nothing is drawn yet";
      return;
    }
    try {
      said = await run(fig);
    } catch (e) {
      said = `${label} failed: ${(e as Error).message}`;
    }
  }

  const png = () => act("PNG", async (fig) => {
    await download(await fig.png(), `${name()}.png`);
    return "saved a PNG";
  });
  const svg = () => act("SVG", async (fig) => {
    const text = await fig.svg(() => import("svgcanvas"));
    await download(new Blob([text], { type: "image/svg+xml" }), `${name()}.svg`);
    return "saved an SVG";
  });
  const image = () => act("copy image", async (fig) => {
    await fig.copyImage();
    return "copied the figure";
  });
  const data = () => act("copy data", async (fig) => {
    const text = fig.tsv();
    await navigator.clipboard.writeText(text);
    return `copied ${text.split("\n").length - 1} rows`;
  });
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
