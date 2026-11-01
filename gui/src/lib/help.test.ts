/**
 * The help corpus resolved and placed (WP-1203).
 *
 * Two halves that fail differently.  **Resolution** is a vocabulary question,
 * so it is held to `tests/data/gui/help_keys.json` — the committed key set
 * written from the live registry by `tests/test_gui_help.py`, the same device
 * `fnmatch.test.ts` uses — and every quoted `<Help for=…>` in the app is
 * crossed against it: a key naming nothing renders "not yet described" under a
 * real control while nothing goes red.  An *interpolated* key is crossed by its
 * literal prefix and the five sites are named, because the brace-excluding
 * pattern this started as matched none of them and said nothing about it.
 * **Placement** is arithmetic, and it is
 * asserted on numbers because jsdom has no layout: every
 * `getBoundingClientRect` there is zeros, so a popover positioned in a
 * component test would be "correct" wherever it went.
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  ARMS,
  labelFor,
  HELP_GAP,
  HELP_MARGIN,
  manualUrl,
  paramKey,
  place,
  resolve,
  splitKey,
  type HelpCorpus,
} from "./help";

const SRC = fileURLToPath(new URL("../", import.meta.url));
const FIXTURE = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../../tests/data/gui/help_keys.json",
                                    import.meta.url)), "utf-8"),
) as { docs_url: string; arms: string[]; keys: string[] };

/** A corpus of the shape the route serves, small enough to read. */
function corpus(): HelpCorpus {
  const entry = (title: string, extra: Record<string, unknown> = {}) => ({
    title, description: `what ${title} is`, unit: null, default: null,
    typical: null, anchor: null, ...extra,
  });
  return {
    parameters: [
      { paths: ["phases.*.cell.a", "phases.*.cell.b", "phases.*.cell.c"],
        ...entry("Cell edge", { unit: "Å", anchor: "theory/peak-positions.html#lattice" }) },
      { paths: ["instrument.zero_shift"], ...entry("Zero-point shift") },
    ],
    peak_flags: { excluded: entry("Excluded") },
    diagnostics: { PEAK_LIST_TOO_SHORT: entry("Too few lines") },
    peak_origins: { manual: entry("Placed by a person", { label: "manual" }) },
    stage_fields: { seed: entry("Stage seed"), max_iter: entry("Iteration cap") },
    reader_options: { block: entry("Data block") },
    instrument_fields: { radiation: entry("Anode") },
    search_fields: { seed: entry("Random seed"), preset: entry("Search preset") },
    plans: { profile_only: entry("Profile only", { modes: ["rietveld"] }) },
    result_fields: { "RefinementResult.status": entry("Solver exit") },
    docs_url: "https://rietx.org/docs/dev",
  };
}

describe("what a chip says (WP-1209)", () => {
  it("is the entry's label, else the name, and never nothing", () => {
    const c = corpus();
    expect(labelFor(c, "peak_origins:manual")).toBe("manual");
    // an entry without a label is its own label
    expect(labelFor(c, "peak_flags:excluded")).toBe("excluded");
    // a member the corpus does not describe still draws its name…
    expect(labelFor(c, "peak_flags:some_future_flag")).toBe("some_future_flag");
    // …and so does a corpus that has not landed, or a key naming no arm
    expect(labelFor(null, "peak_flags:position_at_bound")).toBe("position_at_bound");
    expect(labelFor(c, "bare")).toBe("bare");
  });
});

describe("a key names its arm", () => {
  it("splits `arm:name` and refuses anything else", () => {
    expect(splitKey("stage_fields:max_iter"))
      .toEqual({ arm: "stage_fields", name: "max_iter" });
    // a parameter name contains dots and stars; only the FIRST colon splits
    expect(splitKey("parameters:phases.*.cell.a"))
      .toEqual({ arm: "parameters", name: "phases.*.cell.a" });
    expect(splitKey("max_iter")).toBeNull();
    expect(splitKey("nonsense:max_iter")).toBeNull();
    expect(splitKey(":max_iter")).toBeNull();
  });

  it("resolves the same bare name differently in two arms", () => {
    // the whole reason a key carries its arm: `seed` is a stage field and a
    // search control, and a bare key would answer by declaration order
    const c = corpus();
    expect(resolve(c, "stage_fields:seed")!.title).toBe("Stage seed");
    expect(resolve(c, "search_fields:seed")!.title).toBe("Random seed");
  });

  it("matches a parameter key against the globs of its family", () => {
    const c = corpus();
    expect(resolve(c, "parameters:phases.*.cell.b")!.title).toBe("Cell edge");
    // a *path* is not a key: the row carries the glob, and matching here would
    // be a second fnmatch implementation for a question the server answered
    expect(resolve(c, "parameters:phases.0.cell.b")).toBeNull();
  });

  it("resolves a result field by its `Type.field` name, dot and all", () => {
    const c = corpus();
    expect(resolve(c, "result_fields:RefinementResult.status")!.title).toBe("Solver exit");
    expect(resolve(c, "result_fields:RefinementResult")).toBeNull();
  });

  it("returns null for an unknown name, an unknown arm and no corpus", () => {
    const c = corpus();
    expect(resolve(c, "stage_fields:no_such_field")).toBeNull();
    expect(resolve(c, "no_such_arm:seed")).toBeNull();
    expect(resolve(null, "stage_fields:seed")).toBeNull();
  });

  it("builds a parameter key from a row's help_key, and nothing from none", () => {
    expect(paramKey("phases.*.cell.a")).toBe("parameters:phases.*.cell.a");
    expect(paramKey(null)).toBeNull();
    expect(paramKey("")).toBeNull();
  });
});

describe("the manual link", () => {
  it("joins the served base to the entry's page and heading", () => {
    const c = corpus();
    expect(manualUrl(c, resolve(c, "parameters:phases.*.cell.a")))
      .toBe("https://rietx.org/docs/dev/theory/peak-positions.html#lattice");
  });

  it("is null where the entry names no chapter", () => {
    const c = corpus();
    expect(manualUrl(c, resolve(c, "stage_fields:seed"))).toBeNull();
    expect(manualUrl(c, null)).toBeNull();
  });

  it("does not double the slash when the base carries one", () => {
    const c = { ...corpus(), docs_url: "https://rietx.org/docs/dev/" };
    expect(manualUrl(c, resolve(c, "parameters:phases.*.cell.a")))
      .toBe("https://rietx.org/docs/dev/theory/peak-positions.html#lattice");
  });
});

describe("where the popover goes", () => {
  const viewport = { width: 1200, height: 800 };
  const size = { width: 320, height: 200 };
  const anchor = (left: number, top: number) =>
    ({ left, top, right: left + 60, bottom: top + 16 });

  it("sits below its anchor, left edges aligned", () => {
    expect(place(anchor(400, 300), viewport, size))
      .toEqual({ left: 400, top: 316 + HELP_GAP, flipped: false });
  });

  it("flips above when below would leave the viewport", () => {
    // bottom 716 + 6 + 200 = 922 > 800 - 8, so above: 700 - 6 - 200
    expect(place(anchor(400, 700), viewport, size))
      .toEqual({ left: 400, top: 494, flipped: true });
  });

  it("does not flip a popover taller than the viewport", () => {
    // neither side fits: staying below and clamping to the top margin shows
    // the first line, where flipping would show the last
    const tall = { width: 320, height: 900 };
    expect(place(anchor(400, 700), viewport, tall))
      .toEqual({ left: 400, top: HELP_MARGIN, flipped: false });
  });

  it("clamps to the right margin rather than overflowing", () => {
    expect(place(anchor(1100, 300), viewport, size).left)
      .toBe(1200 - 320 - HELP_MARGIN);
  });

  it("clamps to the left margin for an anchor at the window edge", () => {
    expect(place(anchor(0, 300), viewport, size).left).toBe(HELP_MARGIN);
  });

  it("keeps a popover wider than the viewport at the left margin", () => {
    const wide = { width: 2000, height: 200 };
    expect(place(anchor(400, 300), viewport, wide).left).toBe(HELP_MARGIN);
  });
});

describe("every key the app writes down names something", () => {
  /** `App.svelte` and the panels — where a literal `for=` can be written. */
  function markup(): Array<[string, string]> {
    const files = ["App.svelte",
                   ...readdirSync(`${SRC}panels`).filter((f) => f.endsWith(".svelte"))
                     .sort().map((f) => `panels/${f}`)];
    return files.map((rel) => [rel, readFileSync(`${SRC}${rel}`, "utf-8")]);
  }

  it("declares the arms the registry has", () => {
    expect([...ARMS]).toEqual(FIXTURE.arms);
  });

  it("resolves every quoted <Help for=…> against the committed key set", () => {
    const known = new Set(FIXTURE.keys);
    const unknown: string[] = [];
    for (const [rel, source] of markup()) {
      for (const m of source.matchAll(/<Help\b[^>]*?\bfor="([^"]+)"/g)) {
        // An interpolated key — `peak_flags:{f}`, `parameters:phases.*.cell.
        // {edge}` — names its member at runtime, so what is checkable here is
        // the *literal prefix*: it is what a vocabulary rename breaks, and the
        // arm it points into is exactly what a rename leaves behind.  The
        // brace-excluding form of this pattern skipped all five of them.
        const brace = m[1].indexOf("{");
        const key = brace === -1 ? m[1] : m[1].slice(0, brace);
        const hit = brace === -1
          ? known.has(key)
          : [...known].some((k) => k.startsWith(key) && k.length > key.length);
        if (!hit) unknown.push(`${rel}: ${m[1]}`);
      }
    }
    // A key naming nothing is silent at runtime — the popover says "not yet
    // described" under a control that has a perfectly good entry with a
    // slightly different name.
    expect(unknown).toEqual([]);
  });

  it("checks the interpolated keys too, which is where a rename lands", () => {
    // The gate above is only worth its comment if it *sees* these: a regex
    // that stopped matching them would pass by matching nothing, which is how
    // all five went unchecked.  Naming them is also what makes a sixth site
    // arrive with its prefix declared rather than silently.
    const interpolated = markup().flatMap(([rel, source]) =>
      [...source.matchAll(/<Help\b[^>]*?\bfor="([^"]*\{[^"]*)"/g)]
        .map((m) => `${rel}: ${m[1]}`));
    expect(interpolated.sort()).toEqual([
      "panels/Model.svelte: parameters:phases.*.cell.{edge}",
      // the wizard's typed cell (WP-1206) draws only the parameters the setting
      // leaves free, so its loop runs over names rather than all six edges
      "panels/Model.svelte: parameters:phases.*.cell.{name}",
      "panels/Model.svelte: reader_options:{opt.name}",
      "panels/Peaks.svelte: diagnostics:{d.code}",
      "panels/Peaks.svelte: peak_flags:{f}",
      // the origin chip (WP-1209): `ObservedPeak.origin`'s Literal, keyed both
      // ways from python, so the chip's words are the corpus's
      "panels/Peaks.svelte: peak_origins:{p.origin}",
      "panels/Plan.svelte: plans:{chosen.name}",
      // the plan editor's advanced boxes are a loop over `lib/rxt.ts`'s stage
      // words, which are pinned to `StageSpec` from python (WP-1208), so a new
      // schema field arrives in the form already keyed to its corpus entry
      "panels/Plan.svelte: stage_fields:{key}",
      // the fit's own diagnostics (WP-2037): a folded row keeps its code's
      // explanation beside it, so collapsing hides nothing
      "panels/Report.svelte: diagnostics:{d.code}",
    ]);
  });
});

describe("`title=` is no longer how this app explains a name", () => {
  /**
   * Every authored `title="…"` that is not on a `<button>`, per file.
   *
   * A `title=` may still carry two things, and neither is authored prose: a
   * **value** the layout truncated (`title={row.path}` on a column showing the
   * leaf) and a **sentence the server wrote** (`held_because`, a refutation).
   * Both are expressions, which is why this only counts string literals.
   *
   * What is left is prose typed into the markup, and it is owed a corpus entry
   * — but the corpus describes *names the package has* (parameters, peak
   * flags, stage fields, reader options, instrument fields, plans, search
   * controls, result fields), and several panels' vocabularies are not among them: a report
   * statistic, a series setting, an indexing result column, a drawing
   * threshold.  Those arrive with the WPs that own those panels.
   *
   * So this is a **budget, not a ban**: an exact count per file, which fails
   * both ways.  A new authored `title=` fails it, and so does deleting the
   * last one in a file without deleting the file's row — which is what stops
   * this list outliving the debt it records.
   */
  const OWED: Record<string, number> = {
    "App.svelte": 1,                 // the splitter's drag gesture
    "panels/Console.svelte": 1,      // the event ring's size
    "panels/History.svelte": 4,      // node vocabulary — WP-1217
    "panels/Model.svelte": 3,        // the space-group box, two splitters
    "panels/Params.svelte": 4,       // the table's own affordances
    // The add-at-2θ box, plus nine on the candidate and extinction tables.
    // **Unowned**, and deliberately not WP-1211's, which this line used to name:
    // 1211 drew a candidate's lines on the plot and added no `title=`, while
    // describing these means a new corpus arm and the arms are crossed against
    // a *live* vocabulary both ways, so the arm has to quote something. The
    // thing to quote exists and is the finding to carry: `ΔBIC`, `testable`,
    // `refuting` and `absent` are `ExtinctionCandidate` and `CellCandidate`
    // field names, so an arm over those two `model_fields` is a real live
    // vocabulary — a `peak_origins`-sized commit (help.py, test_help.py
    // `_arms`, test_gui_help.py `ARMS`, lib/help.ts `ARMS` + `HelpCorpus`,
    // docs/reference_pages.py `_VOCABULARIES`, the regenerated help_keys.json),
    // and a WP of its own.
    "panels/Peaks.svelte": 10,
    "panels/Plan.svelte": 2,         // the reorder grip, correlation_guard
    "panels/Plot.svelte": 3,         // fit-range fields — WP-1212
    "panels/Report.svelte": 4,       // report statistics
    "panels/Series.svelte": 11,      // series settings and status chips
    "panels/Structure3D.svelte": 4,  // drawing thresholds, not physics
  };

  function markupFiles(): Array<[string, string]> {
    const files = ["App.svelte",
                   ...readdirSync(`${SRC}panels`).filter((f) => f.endsWith(".svelte"))
                     .sort().map((f) => `panels/${f}`)];
    return files.map((rel) => [rel, readFileSync(`${SRC}${rel}`, "utf-8")]);
  }

  /** Authored `title="…"` outside a `<button>` and outside `<Help>` itself. */
  function authored(source: string): number {
    let n = 0;
    for (const m of source.matchAll(/\btitle="/g)) {
      const open = source.lastIndexOf("<", m.index!);
      const tag = /^<\s*([A-Za-z0-9_.-]+)/.exec(source.slice(open))?.[1];
      // `<Help title=…>` is the popover's own heading for a supplied sentence,
      // not a tooltip — it is rendered *inside* the popover, never hovered
      if (tag === "button" || tag === "Help") continue;
      n += 1;
    }
    return n;
  }

  it("counts exactly the authored titles each file is still owed", () => {
    const found: Record<string, number> = {};
    for (const [rel, source] of markupFiles()) {
      const n = authored(source);
      if (n) found[rel] = n;
    }
    expect(found).toEqual(OWED);
  });

  it("reads a file it claims to count, so the regex cannot fail open", () => {
    // Every assertion here is "this count is right", which a regex that
    // matched nothing would satisfy for a file full of titles.
    const files = markupFiles();
    expect(files.length).toBeGreaterThanOrEqual(14);
    expect(files.every(([, source]) => source.includes("<"))).toBe(true);
    // …and the counter must actually see a title where one demonstrably is
    expect(authored('<span title="x">y</span>')).toBe(1);
    expect(authored('<button title="run this stage">Run</button>')).toBe(0);
    expect(authored('<Help title="Not a fit yet">chip</Help>')).toBe(0);
    expect(authored("<span title={row.path}>y</span>")).toBe(0);
  });

  it("keeps no authored help prose in the two field inventories", () => {
    // These are the "two hand-written TypeScript corpora" `rietx.help`'s own
    // docstring names: 21 explanations in `controls.ts` and 11 in `wizard.ts`,
    // kept beside the fields they described.  Both now *derive* a corpus key
    // from the field's own name, so the type carries no `title` at all — which
    // is what makes the move irreversible by accident.
    //
    // Asserted on the interface rather than by counting `title:` lines,
    // because `lib/plot.ts` legitimately says `title` about a curve toggle and
    // a plotly axis, and a blanket ban would be a rule about the word.
    for (const [file, iface] of [["controls.ts", "ControlField"],
                                 ["wizard.ts", "PresetField"]] as const) {
      const source = readFileSync(`${SRC}lib/${file}`, "utf-8");
      const block = new RegExp(`export interface ${iface} \\{([^}]*)\\}`).exec(source);
      expect(block, `${file}: ${iface} moved`).toBeTruthy();
      expect(/\btitle\??:/.test(block![1]), `${iface}.title`).toBe(false);
    }
    // …and `lib/model.ts`'s `Field` keeps `title` as a *stated* escape for the
    // handful of model choices the corpus has no vocabulary for, which
    // `wizard.test.ts` holds to a named list.
    const model = readFileSync(`${SRC}lib/model.ts`, "utf-8");
    expect(/export interface Field \{[^}]*\bhelp\?:/.test(model)).toBe(true);
  });
});
