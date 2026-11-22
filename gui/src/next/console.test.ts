// The Console's lines by kind (WP-2212): the kinds, the two caps, the shared
// panels' boundary, the runnable forms, every writer's spelling, the entries
// the panel draws and the script the File menu exports.
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  EVENT_CAP, LINE_CAP, LINE_KINDS, clock, copyText, entries, eventLine, foldSummary, makeLine,
  pieces, pushLine, serverScript, sessionScript, sharedSay, stageScript, structureScript, type Line,
  type LineKind,
} from "./console";

const HERE = fileURLToPath(new URL("./", import.meta.url));

describe("a line", () => {
  it("keeps its kind, its text and a script only when given one", () => {
    expect(makeLine("call", "p.fit()", undefined, 5)).toEqual({ kind: "call", text: "p.fit()", t: 5 });
    expect(makeLine("call", "x", null, 5)).toEqual({ kind: "call", text: "x", t: 5, script: null });
  });

  it("stamps an engine event with the event's own time", () => {
    const line = eventLine({ seq: 3, kind: "stage_start", t: 12.5, data: { stage: "scale" } } as any);
    expect(line.kind).toBe("event");
    expect(line.t).toBe(12.5);
    expect(line.text).toContain("stage_start");
    expect(line.ev).toEqual({ kind: "stage_start", stage: "scale" });
  });
});

describe("pushLine", () => {
  const caps = { lines: 3, events: 2 };
  const of = (kind: LineKind, text: string): Line => makeLine(kind, text, undefined, 0);

  it("drops the oldest of its own class past that class's cap", () => {
    let lines: Line[] = [];
    for (const text of ["a", "b", "c"]) lines = pushLine(lines, of("call", text), caps);
    for (const text of ["e1", "e2", "e3"]) lines = pushLine(lines, of("event", text), caps);
    // three events against a cap of two drop the first event, never a call
    expect(lines.map((l) => l.text)).toEqual(["a", "b", "c", "e2", "e3"]);
    lines = pushLine(lines, of("output", "d"), caps);
    expect(lines.map((l) => l.text)).toEqual(["b", "c", "e2", "e3", "d"]);
  });

  it("holds a fit's events under a separate, larger cap", () => {
    expect(EVENT_CAP).toBeGreaterThan(LINE_CAP);
  });
});

describe("the shared panels' plain strings", () => {
  it("read a refusal, a comment and a call off the spelling, at that boundary only", () => {
    const said: [LineKind, string, unknown][] = [];
    const say = sharedSay((kind, text, script) => said.push([kind, text, script]));
    say("refused: no such folder");
    say("# copied");
    say('shutil.copytree("a", "b")');
    expect(said).toEqual([
      ["refusal", "refused: no such folder", undefined],
      ["comment", "# copied", undefined],
      ["call", 'shutil.copytree("a", "b")', null],
    ]);
  });
});

describe("the runnable forms", () => {
  it("carry the stage and the model whole, as JSON the schema reads back", () => {
    const stage = { name: "cell", turn_on: ["phases.*.cell.*"], max_iter: 40 };
    const script = stageScript(stage);
    expect(script).toMatch(/^p\.run_stage\(rx\.StageSpec\.model_validate_json\(/);
    // a JSON string literal is a Python string literal too, holding the stage's JSON
    expect(script).toContain(`model_validate_json(${JSON.stringify(JSON.stringify(stage))})`);
    expect(structureScript({ phases: [] })).toBe(
      'ref.edit(structure=rx.Structure.model_validate_json("{\\"phases\\":[]}"))');
  });

  it("repeat a server's echo only on a bound receiver with nothing elided", () => {
    expect(serverScript("ref.set_values({'a': 1.0})")).toBeUndefined();
    expect(serverScript("p.doc.mode = 'lebail'")).toBeUndefined();
    expect(serverScript("p.doc.plan = rx.PlanSpec(…3 stage(s))")).toBeNull();
    expect(serverScript("session.move_peak(2, 31.4)")).toBeNull();
  });
});

describe("every writer under next/", () => {
  const files = readdirSync(HERE).filter((f) => f.endsWith(".svelte"));
  const calls = files.flatMap((f) => {
    const text = readFileSync(`${HERE}${f}`, "utf-8");
    // the whole statement, which may run over lines: a script argument often does
    return [...text.matchAll(/\bsay\(([\s\S]{0,400}?)\);/g)].map((m) => ({ file: f, args: m[1] }));
  });

  it("passes its kind first", () => {
    expect(calls.length).toBeGreaterThan(20);
    const kindless = calls.filter(({ args }) =>
      !LINE_KINDS.some((k) => args.startsWith(`"${k}"`)) && !args.startsWith("kind:"));
    expect(kindless).toEqual([]);
  });

  it("spells a literal call on the receivers the preamble binds, or says it cannot run", () => {
    const literal = calls.filter(({ args }) => /^"call", [`"']/.test(args));
    const unbound = literal.filter(({ args }) => {
      const text = args.slice('"call", '.length + 1);
      return !/^(p|ref|rx)\.|^p = rx\.Project\.open/.test(text) && !args.includes("null");
    });
    expect(unbound).toEqual([]);
  });
});

describe("the entries the Console draws", () => {
  const at = (kind: LineKind, text: string, entry?: number, extra: Partial<Line> = {}): Line =>
    ({ ...makeLine(kind, text, undefined, 100), ...(entry === undefined ? {} : { entry }), ...extra });
  const ev = (kind: string, data: Record<string, unknown> = {}) =>
    eventLine({ seq: 1, kind, t: 101, data } as any);

  it("group one action's lines, and fold a run's events under its call", () => {
    const drawn = entries([
      at("call", "ref.set_values({})", 1),
      at("call", "ref.set_vary('a', True)", 1),
      at("call", "p.fit()", 2, { run: true }),
      ev("stage_start", { stage: "scale" }),
      at("comment", "# view kept", 3),
      ev("eval", { stage: "scale", n_eval: 4 }),
    ]);
    expect(drawn.map((e) => e.lines.map((l) => l.text))).toEqual([
      ["ref.set_values({})", "ref.set_vary('a', True)"], ["p.fit()"], ["# view kept"]]);
    // the eval that came after the comment still folds under the run's call
    expect(drawn[1].events.map((l) => l.ev?.kind)).toEqual(["stage_start", "eval"]);
    expect(drawn[2].events).toEqual([]);
  });

  it("open with the events from before any run on this page, under no call", () => {
    const drawn = entries([ev("fit_end"), at("call", "p.fit()", 1)]);
    expect(drawn[0].lines).toEqual([]);
    expect(drawn[0].events).toHaveLength(1);
  });

  it("sum a fold as events, stages and evaluations", () => {
    expect(foldSummary([
      ev("fit_start"), ev("stage_start", { stage: "a" }), ev("eval", { stage: "a", n_eval: 1 }),
      ev("eval", { stage: "a", n_eval: 7 }), ev("stage_end", { stage: "a" }),
      ev("stage_start", { stage: "b" }), ev("eval", { stage: "b", n_eval: 5 }),
    ])).toBe("7 engine events, 2 stages, 12 evaluations");
    expect(foldSummary([ev("index_start")])).toBe("1 engine event");
  });
});

describe("a line's drawing", () => {
  it("cuts a call into plain runs, strings and a trailing comment", () => {
    expect(pieces('ref.hold("a.b")  # 2 path(s)')).toEqual([
      { text: "ref.hold(", cls: "" }, { text: '"a.b"', cls: "str" }, { text: ")  ", cls: "" },
      { text: "# 2 path(s)", cls: "cm" }]);
    // a # inside a string is the string's
    expect(pieces("x = '#1'").map((p) => p.cls)).toEqual(["", "str"]);
  });

  it("prints the time of day as the prototype does", () => {
    expect(clock(new Date(2026, 10, 22, 9, 5, 7).getTime() / 1000)).toBe("09:05:07");
  });

  it("copies the calls alone", () => {
    const lines = [makeLine("call", "p.fit()"), makeLine("output", "done"),
                   makeLine("comment", "# x"), makeLine("call", "ref.hold('a')")];
    expect(copyText(lines)).toBe("p.fit()\nref.hold('a')\n");
    expect(copyText([])).toBe("");
  });
});

describe("the session as a script", () => {
  const call = (text: string, script?: string | null): Line => makeLine("call", text, script, 0);

  it("binds the names, opens the copy it is given, and repeats each call's runnable form", () => {
    const text = sessionScript([
      { ...call('p = rx.Project.open("/w/fap.rex")'), preamble: true },
      call("ref.set_values({\"a\": 1})"),
      call("ref.run_stage(...)", "p.run_stage(rx.StageSpec.model_validate_json(\"{}\").to_stage())"),
      makeLine("comment", "# view kept", undefined, 0),
    ], "/w/fap.rex", new Date(2026, 10, 22));
    const lines = text.split("\n");
    expect(lines[0]).toBe("# fap: the rietx GUI session of 2026-11-22, as a script.");
    expect(text).toContain("#   python fap.py path/to/copy.rex\n");
    expect(text).toContain("import rietx as rx\n\np = rx.Project.open(sys.argv[1])\nref = p.refinement\n");
    // the Console's opening lines are the preamble's; a comment line is no call
    expect(text).not.toContain('Project.open("/w/fap.rex")');
    expect(text).not.toContain("view kept");
    expect(text.endsWith('ref.set_values({"a": 1})\n'
      + 'p.run_stage(rx.StageSpec.model_validate_json("{}").to_stage())\n\np.save()\n')).toBe(true);
    expect(text).not.toContain("steps are comments");
  });

  it("writes a call it cannot repeat as a comment, and says so at its head", () => {
    const text = sessionScript([call("ref.edit(structure=…)  # limits", null), call("p.fit()")],
                               "/w/fap.rex");
    expect(text).toContain("# 1 of its 2 steps are comments: the window ran them,");
    expect(text).toContain("# not repeated: ref.edit(structure=…)  # limits\np.fit()\n");
  });
});
