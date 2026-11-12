/**
 * The house style, asserted (WP-1201).
 *
 * A register means one thing and is drawn one way everywhere, which is a
 * property of `app.css` and of nothing else: **size, padding and radius belong
 * to the register, never to the call site**.  Before this WP the app had six
 * button geometries, three chip geometries and eight literal font sizes across
 * 68 `font-size` declarations, and the "different-sized chips" that started the
 * WP were a same-specificity collision between one panel's `.chip` (10 px) and
 * the same panel's `.note` (12 px) — a class of bug that cannot happen once a
 * register is written once.
 *
 * This is a regex over the source, deliberately: a CSS parser would tell us
 * about cascade and specificity, and what is wanted is much cruder — that a
 * panel does not *say* these words at all.  Three consequences to know before
 * adding a rule:
 *
 *   * `.pick` is not on the forbidden list, because its whole content is that
 *     the row supplies the box (`app.css`).  A panel laying one out is the
 *     register working, not a violation.
 *   * a fourth type step is caught by the value check, not by a size list, so
 *     `font-size: 12px` fails wherever it is written and `var(--text-sm)`
 *     passes wherever it is.
 *   * the geometry check covers the `font` shorthand and the long-hand
 *     paddings and corner radii, because `button { font: 9px/1.2 serif }` and
 *     `.chip { padding-left: 30px }` are the same violation spelled around the
 *     property names (all four dodges measured in review, 2026-08-25).
 *
 * What it still does **not** see, stated rather than assumed: CSS nesting.  A
 * nested `& .ghost { padding: … }` is parsed as the selector `& .ghost`, which
 * matches no register name.  Nothing in `gui/` nests today; a panel that
 * starts to needs this parser replaced, not extended.
 *
 * `app.css` itself is exempt: it is where the argument is had.
 */
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL("../", import.meta.url));

/** `App.svelte` and every panel — the files a register can be redeclared in. */
function styledFiles(): string[] {
  return [
    "App.svelte",
    ...readdirSync(`${SRC}panels`)
      .filter((f) => f.endsWith(".svelte"))
      .sort()
      .map((f) => `panels/${f}`),
  ];
}

/** Every file a class name can be *used* in. */
function allSources(): string[] {
  const out: string[] = [];
  const walk = (dir: string, prefix: string) => {
    for (const entry of readdirSync(`${SRC}${dir}`, { withFileTypes: true }).sort(
      (a, b) => a.name.localeCompare(b.name),
    )) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(`${dir}${entry.name}/`, rel);
      else if (/\.(svelte|css|ts)$/.test(entry.name) && entry.name !== "style.test.ts")
        out.push(rel);
    }
  };
  walk("", "");
  return out;
}

const read = (rel: string) => readFileSync(`${SRC}${rel}`, "utf-8");

/**
 * The `<style>` block with its comments stripped, or "" when there is none.
 *
 * `<style[^>]*>`, not `<style>`: an attribute (`<style lang="css">`) made the
 * match fail, and a failed match is a *silently skipped file* — every
 * assertion below passes for a panel this cannot read.  A guard that fails
 * open on one extra character is worse than no guard, so
 * `every_styled_file_yields_a_block` asserts the parse as well.
 */
function styleBlock(source: string): string {
  const block = source.match(/<style[^>]*>([\s\S]*?)<\/style>/);
  return block ? block[1].replace(/\/\*[\s\S]*?\*\//g, "") : "";
}

interface Rule {
  selectors: string[];
  declarations: string[];
}

/** Flat rules — the panels' style blocks carry no at-rules and no nesting. */
function rules(block: string): Rule[] {
  const out: Rule[] = [];
  for (const m of block.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    out.push({
      selectors: m[1].split(",").map((s) => s.trim()).filter(Boolean),
      declarations: m[2].split(";").map((d) => d.trim()).filter(Boolean),
    });
  }
  return out;
}

/** The registers whose geometry is `app.css`'s alone. */
const REGISTERS: Array<[string, RegExp]> = [
  ["button", /\bbutton\b/],
  [".chip", /\.chip(?![\w-])/],
  [".pill", /\.pill(?![\w-])/],
  [".segmented", /\.segmented(?![\w-])/],
  [".tab", /\.tab(?![\w-])/],
  [".link", /\.link(?![\w-])/],
  // the label-as-button: `app.css` draws it, and it is here because it is the
  // one register that *was* written twice at two geometries before WP-1201
  [".file", /\.file(?![\w-])/],
];

// `font` is the shorthand and sets a size; the long-hand paddings and corner
// radii are the same declaration spelled longer.
const GEOMETRY =
  /^(font|font-size|padding(-[\w-]+)?|border(-[\w-]+)?-radius)\s*:/;

describe("the control registers are declared once, in app.css", () => {
  it("reads a style block out of every file it claims to check", () => {
    // The assertions below are all of the form "this list is empty", so a file
    // whose block failed to parse passes every one of them.  Without this, the
    // guard's coverage is a silent property of a regex.
    const empty = styledFiles().filter((rel) => styleBlock(read(rel)).trim() === "");
    expect(empty).toEqual([]);
    expect(styledFiles().length).toBeGreaterThanOrEqual(14);
  });

  it("no panel gives a register its own size, padding or radius", () => {
    const found: string[] = [];
    for (const rel of styledFiles()) {
      for (const rule of rules(styleBlock(read(rel)))) {
        for (const selector of rule.selectors) {
          const hit = REGISTERS.find(([, re]) => re.test(selector));
          if (!hit) continue;
          for (const declaration of rule.declarations) {
            if (GEOMETRY.test(declaration))
              found.push(`${rel}: ${selector} { ${declaration} }  [register ${hit[0]}]`);
          }
        }
      }
    }
    // A register wanting a second geometry is a register wanting to be two
    // registers; that argument belongs in app.css, where both can be seen.
    expect(found).toEqual([]);
  });

  it("every font-size in a panel names a step of the type scale", () => {
    const found: string[] = [];
    for (const rel of styledFiles()) {
      for (const m of styleBlock(read(rel)).matchAll(/font-size\s*:\s*([^;}]+)/g)) {
        const value = m[1].trim();
        if (!value.startsWith("var(--text")) found.push(`${rel}: font-size: ${value}`);
      }
    }
    // Three steps: --text (prose), --text-sm (a control and its row),
    // --text-xs (a chip and a section heading).  A fourth is a decision, and
    // it is taken in app.css or not at all.
    expect(found).toEqual([]);
  });
});

describe("`.small` and `.tiny` are gone", () => {
  it("names no size class, in a stylesheet or in markup", () => {
    // They were sizes wearing the clothes of registers: `.small` was
    // redeclared in nine panels and `.tiny` in five, at three different values
    // between them, and neither said what the thing it sized *was*.  What
    // replaced them is the register (a control is control-sized) and `.muted`
    // (secondary is said by colour, once).
    const selectors: string[] = [];
    const uses: string[] = [];
    for (const rel of allSources()) {
      const source = read(rel);
      for (const m of source.matchAll(/(?<![\w-])\.(small|tiny)(?![\w-])/g))
        selectors.push(`${rel}: selector .${m[1]}`);
      if (!rel.endsWith(".svelte")) continue;
      for (const m of source.matchAll(/class="([^"]*)"/g))
        if (/(?<![\w-])(small|tiny)(?![\w-])/.test(m[1].replace(/\{[^{}]*\}/g, "")))
          uses.push(`${rel}: class="${m[1].replace(/\s+/g, " ").trim()}"`);
    }
    expect(selectors).toEqual([]);
    expect(uses).toEqual([]);
  });
});


describe("the title bar gives ground before it overflows", () => {
  it("wraps its controls, as the header around them already does", () => {
    // Measured at a 420 px window (WP-1438): the document scrolled to 618 px,
    // and to 618 at every window under that, because `.controls` was one
    // unbreakable 604 px flex line inside a header that wraps. `flex: 0 0
    // auto` on top of that told it never to give ground.
    //
    // A regex over the source, like everything else here: what would catch
    // this properly is a browser measuring the document against the window,
    // and the GUI has no such harness. This is the declaration whose absence
    // was the defect.
    const source = read("App.svelte");
    const start = source.indexOf("\n  .controls {");
    expect(start).toBeGreaterThan(-1);
    const rule = source.slice(start, source.indexOf("}", start));
    expect(rule).toMatch(/flex-wrap:\s*wrap/);
    expect(rule).not.toMatch(/flex:\s*0 0 /);
  });
});

/**
 * Every `<button …>` opening tag in a file, attributes whole.
 *
 * Scanned rather than matched with `<button[^>]*>`, because an attribute such
 * as `onclick={() => go()}` holds a `>` and a regex would end the tag there.
 */
function buttonTags(source: string): string[] {
  const out: string[] = [];
  let from = 0;
  for (;;) {
    const start = source.indexOf("<button", from);
    if (start < 0) return out;
    let depth = 0;
    let quote = "";
    let i = start + 7;
    for (; i < source.length; i++) {
      const c = source[i];
      if (quote) {
        if (c === quote) quote = "";
      } else if (depth === 0 && (c === '"' || c === "'")) quote = c;
      else if (c === "{") depth++;
      else if (c === "}") depth--;
      else if (c === ">" && depth === 0) break;
    }
    out.push(source.slice(start, i + 1));
    from = i + 1;
  }
}

describe("one filled primary per view", () => {
  it("draws every button outlined, a segmented option or a register of its own", () => {
    // The maintainer's ruling of 2026-11-06: one filled primary per view, in
    // the accent, and every other button outlined.  The shell's action bar
    // shows its filled Refine under every panel (WP-2123), so a panel's own
    // filled button is always a second one.  Three are allowed: the start
    // screen's New project…, which is the whole view and has no bar under it
    // (WP-2131), and two dialogs over the window whose own primary is the
    // dialog's, the New project dialog's Create project and the folder
    // browser's Use this directory.  The File menu's Save a copy and Export
    // dialog is a fourth over the window (WP-2133), one primary for both.
    // The offer of kept edits is a fifth (WP-2209), whose primary is Restore.
    const ALLOWED: Record<string, number> = {
      "panels/ActionBar.svelte": 1,
      "panels/Browse.svelte": 1,
      "panels/FileMenu.svelte": 1,
      "panels/NewProject.svelte": 1,
      "panels/Recovery.svelte": 1,
      "panels/Start.svelte": 1,
    };
    // `.ink` is the Parameters panel's number (WP-2126): the value itself,
    // tinted because it can be edited, whose press opens the editor over it.
    // It carries no fill of the accent, so it is no second primary.
    const OTHER = /\bclass="[^"]*\b(ghost|tab|pick|link|help|ink)\b/;
    const filled: Record<string, number> = {};
    const tags: string[] = [];
    for (const rel of styledFiles()) {
      for (const tag of buttonTags(read(rel))) {
        tags.push(tag);
        if (OTHER.test(tag) || /\bclass:(ghost|on)=/.test(tag)) continue;
        filled[rel] = (filled[rel] ?? 0) + 1;
      }
    }
    // the scanner read real tags: one of them holds an arrow function's `>`
    expect(tags.some((tag) => tag.includes("=>"))).toBe(true);
    expect(filled).toEqual(ALLOWED);
  });
});
