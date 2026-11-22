// The Console's lines by kind (WP-2212): the kinds, the two caps, the shared
// panels' boundary, the runnable forms, and every writer's spelling.
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  EVENT_CAP, LINE_CAP, LINE_KINDS, eventLine, makeLine, pushLine, serverScript, sharedSay,
  stageScript, structureScript, type Line, type LineKind,
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
