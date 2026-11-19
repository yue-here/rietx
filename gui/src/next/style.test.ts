// The rebuilt page starts in sentence case (WP-2215, carrying WP-2201's guard).
// The maintainer's rulings of 2026-11-06 and 2026-11-09: a heading is set apart
// by weight, never by capitals and tracking. A selected tab keeps its weight
// (`gui/STYLE.md` § Type), since a bolder word is wider and moves what follows.
import { readFileSync, readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";

const DIR = new URL(".", import.meta.url).pathname;

function sheets(): Array<[string, string]> {
  const out: Array<[string, string]> = [];
  // files only: `static/` holds the fonts the second pass copies
  for (const name of readdirSync(DIR).sort()) {
    if (!/\.(css|svelte)$/.test(name)) continue;
    const text = readFileSync(DIR + name, "utf-8");
    if (name.endsWith(".css")) out.push([name, text]);
    else out.push([name, /<style>([\s\S]*?)<\/style>/.exec(text)?.[1] ?? ""]);
  }
  return out.map(([n, t]) => [n, t.replace(/\/\*[\s\S]*?\*\//g, "")]);
}

describe("the rebuilt page's stylesheets", () => {
  it("are read, next.css among them", () => {
    expect(sheets().map(([n]) => n)).toContain("next.css");
  });

  it("uppercase, capitalise, small-cap and track nothing", () => {
    const found: string[] = [];
    for (const [name, text] of sheets()) {
      for (const m of text.matchAll(/text-transform\s*:\s*(uppercase|capitalize)/g)) found.push(`${name}: ${m[0]}`);
      for (const m of text.matchAll(/letter-spacing\s*:\s*([0-9.]+)/g))
        if (Number(m[1]) > 0) found.push(`${name}: ${m[0]}`);
      for (const m of text.matchAll(/font-variant(-caps)?\s*:[^;]*small-caps/g)) found.push(`${name}: ${m[0]}`);
    }
    expect(found).toEqual([]);
  });

  it("turn off the uppercase heading rule today's app.css carries", () => {
    const next = sheets().find(([n]) => n === "next.css")![1];
    expect(next).toMatch(/h2,\s*h3\s*\{[^}]*text-transform:\s*none/);
  });

  it("never change a tab's weight when it is selected", () => {
    const next = sheets().find(([n]) => n === "next.css")![1];
    const selected = /\.tab\[aria-selected="true"\][^{]*\{([^}]*)\}/.exec(next)![1];
    expect(selected).not.toMatch(/font-weight/);
  });
});
