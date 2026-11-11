/**
 * A figure's four exports (WP-1461, D6): a PNG and an SVG file, the picture on
 * the clipboard, and what is in view as tab-separated columns. The chart module
 * does the work, on the figure as drawn now, at the reader's zoom. Each answers
 * with the line a panel shows, a refusal included, since a clipboard can refuse.
 *
 * The rebuilt Pattern graph's menus call it. It is `panels/Exports.svelte`'s
 * logic, lifted out of that shared panel rather than edited in it (`gui/CLAUDE.md`
 * § Build: a shared panel is not edited for the new page's sake); the panel
 * can call it at the swap.
 *
 * Nothing here is imported at boot: the chart module is a chunk the first draw
 * fetches, and svgcanvas one the first SVG fetches.
 */
import type { Group } from "rxplot";

export type ExportKind = "png" | "svg" | "image" | "data";

const LABELS: Record<ExportKind, string> = {
  png: "PNG", svg: "SVG", image: "copy image", data: "copy data",
};

async function download(blob: Blob, file: string): Promise<void> {
  (await import("rxplot")).download(blob, file);
}

async function run(kind: ExportKind, fig: Group, name: string): Promise<string> {
  if (kind === "png") {
    await download(await fig.png(), `${name}.png`);
    return "saved a PNG";
  }
  if (kind === "svg") {
    const text = await fig.svg(() => import("svgcanvas"));
    await download(new Blob([text], { type: "image/svg+xml" }), `${name}.svg`);
    return "saved an SVG";
  }
  if (kind === "image") {
    await fig.copyImage();
    return "copied the figure";
  }
  const text = fig.tsv();
  await navigator.clipboard.writeText(text);
  return `copied ${text.split("\n").length - 1} rows`;
}

/** Run one export on `fig` and say what happened. */
export async function exportFigure(kind: ExportKind, fig: Group | null,
                                   name: string): Promise<string> {
  if (!fig) return "nothing is drawn yet";
  try {
    return await run(kind, fig, name);
  } catch (e) {
    return `${LABELS[kind]} failed: ${(e as Error).message}`;
  }
}
