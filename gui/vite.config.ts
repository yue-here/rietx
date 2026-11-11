import { fileURLToPath } from "node:url";

import { svelte } from "@sveltejs/vite-plugin-svelte";
// from vitest/config, not vite: it is the one that types the `test` key
import { defineConfig } from "vitest/config";

// The build output is COMMITTED under src/rietx/gui/static, so installing the
// wheel never needs node.  Two consequences shape this config:
//
//   * stable filenames, no content hashes — a dist diff has to be reviewable,
//     and a hashed filename turns every rebuild into a rename;
//   * no sourcemaps and no build timestamp anywhere, so rebuilding unchanged
//     sources produces a byte-identical tree and `git diff --exit-code` means
//     "the dist is stale", not "someone rebuilt".
//
// Two pages since WP-2215: today's GUI (`index.html`) and the rebuild
// (`next.html`, served at /next until the swap). The rebuild is a second pass,
// `vite build --mode next`, writing `next.html`, `assets/next.js` and
// `assets/next.css` beside the first pass's output. One multi-entry pass would
// split the code both pages import into a shared chunk and a shared
// stylesheet, so today's page would load files it never loaded and the
// rebuild's global rules would reach it; two passes leave today's dist as it
// was and give each page its own script and stylesheet.
export default defineConfig(({ mode }) => ({
  plugins: [svelte()],
  // the rebuild's fonts and their licences, copied as they are into the dist's
  // `fonts/` by the second pass alone, so today's page is unchanged
  publicDir: mode === "next" ? "src/next/static" : false,
  build: {
    outDir: "../src/rietx/gui/static",
    emptyOutDir: mode !== "next",
    sourcemap: false,
    target: "es2022",
    // one CSS file: the styles are ~700 lines and splitting them would trade a
    // reviewable dist for a load time nobody can measure on localhost
    cssCodeSplit: false,
    rollupOptions: {
      ...(mode === "next"
        ? { input: fileURLToPath(new URL("next.html", import.meta.url)) } : {}),
      output: {
        entryFileNames: mode === "next" ? "assets/next.js" : "assets/app.js",
        // the second pass writes beside the first with nothing emptied, so its
        // chunks take a prefix: an `assets/vendor-uplot.js` of its own would
        // replace the one `app.js` imports, whose export names it does not share
        chunkFileNames: mode === "next" ? "assets/next-[name].js" : "assets/[name].js",
        // Application code is still one chunk.  CodeMirror — its first real
        // dependency (WP-1013) — is not, and splitting it *serves* the
        // one-chunk decision rather than reversing it: a committed dist has to
        // diff reviewably, and ~350 kB of minified third-party bytes inside
        // `app.js` would sit in the middle of every application diff, while a
        // separate `vendor-cm.js` changes only when the lockfile pin does.
        // `panels/Text.svelte` imports it dynamically, so this is also what
        // keeps the boot path at the size WP-1010 measured — the editor is
        // fetched the first time someone opens the text pane, not before the
        // first paint.
        //
        // uPlot is split for the same reason (WP-1461): 51 kB of third-party
        // bytes that change only when its pin does. svgcanvas too, and it is
        // imported on the first SVG export rather than at boot.
        manualChunks: (id: string) =>
          /node_modules[\\/](@codemirror|@lezer|crelt|style-mod|w3c-keyname)[\\/]/
            .test(id) ? "vendor-cm"
            : /node_modules[\\/]uplot[\\/]/.test(id) ? "vendor-uplot"
            : /node_modules[\\/]svgcanvas[\\/]/.test(id) ? "vendor-svgcanvas" : undefined,
        assetFileNames: (info) =>
          !info.names?.[0]?.endsWith(".css") ? "assets/[name][extname]"
            : mode === "next" ? "assets/next.css" : "assets/app.css",
      },
    },
  },
  // Svelte's own testing guidance: under vitest, resolve the *browser* build of
  // svelte, or `mount()` comes from the server bundle and throws
  // `lifecycle_function_unavailable` — which is how a component test that only
  // ever ran on the server announces itself.
  resolve: {
    // The chart module is javascript in the Python package, because `rietx
    // watch` and `rietx compare` serve it to a page as it is (WP-1461, D3).
    // `src/rxplot.d.ts` declares its types.
    alias: {
      rxplot: fileURLToPath(new URL("../src/rietx/viz/static/rxplot.mjs", import.meta.url)),
    },
    ...(process.env.VITEST ? { conditions: ["browser"] } : {}),
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
    // one file, for the browser APIs jsdom lacks — see its own comment for the
    // rule about which ones may go in it
    setupFiles: ["src/test-setup.ts"],
  },
}));
