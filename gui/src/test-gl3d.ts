/**
 * The structure viewer's renderer as jsdom can run it (WP-1462).
 *
 * jsdom has no WebGL, so `lib/gl3d.ts`'s `createRenderer` would return `null`
 * and the viewer would show its "no WebGL2" line instead of a picture.
 * `test-setup.ts` puts this module in its place: a renderer that keeps every
 * scene and view it was handed, in `frames`, so a component test asserts what
 * the viewer asked to have drawn.  Only `createRenderer` is replaced; the rest of the
 * module is the real one.  What a browser then paints is
 * `tests/test_structure3d_browser.py`'s.
 */

import type { ExportOptions, Renderer } from "./lib/gl3d";
import type { Scene, View } from "./lib/structure3d";

export interface Frame {
  scene: Scene;
  view: View;
  background: number[];
  /** whether depth cueing was on when this frame was drawn (WP-1548) */
  depthCue: boolean;
}

/** Every frame any stand-in renderer drew, oldest first, and every export. */
export const frames: Frame[] = [];
export const exports: Array<{ view: View; options: ExportOptions }> = [];
/** How many renderers were made and how many given back — and how many were
 *  made on a canvas whose context had been given back, which a browser answers
 *  with a dead context that draws nothing (its sad face, in Chrome). */
export const lifecycle = { created: 0, disposed: 0, onDeadCanvas: 0 };
const dead = new WeakSet<HTMLCanvasElement>();

export function createRenderer(canvas: HTMLCanvasElement): Renderer | null {
  lifecycle.created += 1;
  if (dead.has(canvas)) lifecycle.onDeadCanvas += 1;
  let scene: Scene | null = null;
  let depthCue = false;
  return {
    setScene(next: Scene) {
      scene = next;
    },
    setDepthCue(on: boolean) {
      depthCue = on;
    },
    draw(view: View, background: number[]) {
      if (scene) frames.push({ scene, view, background, depthCue });
    },
    async exportPng(view: View, options: ExportOptions) {
      exports.push({ view, options });
      return { blob: new Blob([], { type: "image/png" }), width: 3000, height: 2000 };
    },
    dispose() {
      lifecycle.disposed += 1;
      dead.add(canvas);
    },
  };
}
