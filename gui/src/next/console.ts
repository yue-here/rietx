/**
 * The Console's lines, each knowing its kind (WP-2212).
 *
 * The prototype's Console is the session as a script: a call the window ran
 * behind a `>>>` prompt, what came back muted under it, comments faint. A
 * plain string cannot say which it is, so every writer hands `say` its kind
 * and the panel draws by it. Copy and the script export read the call lines.
 *
 * The kinds:
 *
 *   * `call`: Python the window ran, spelled with one receiver per name
 *     (`p` for the project, `ref` for its refinement, as the script's preamble
 *     binds them, `PREAMBLE`);
 *   * `output`: what a call answered;
 *   * `comment`: a GUI action with no call of its own, written `# …`;
 *   * `refusal`: a verb the server refused, with its words;
 *   * `event`: an engine event off the stream (`lib/stream.ts:consoleLine`).
 *
 * A call carries `script` when the line shown cannot run as written. `null`
 * means nothing runnable stands for it, and the script writes it as a
 * comment; a string is the runnable form. Absent, the text is the script.
 */
import { consoleLine, type EngineEvent } from "../lib/stream";

export type LineKind = "call" | "output" | "comment" | "refusal" | "event";

export const LINE_KINDS: readonly LineKind[] = ["call", "output", "comment", "refusal", "event"];

export interface Line {
  kind: LineKind;
  text: string;
  /** when it was written, in seconds since the epoch */
  t: number;
  /** a call's runnable form: absent is the text, `null` is none */
  script?: string | null;
  /** which entry a non-event line belongs to (`entries`), stamped by the writer */
  entry?: number;
  /** a call that started a run, whose events fold under it */
  run?: boolean;
  /** one of the lines that open a session, binding the names; the script
   *  writes its own */
  preamble?: boolean;
  /** an event's kind and the two fields the fold's summary counts */
  ev?: { kind: string; stage?: string; n_eval?: number };
}

/** How a panel writes to the Console. */
export type Say = (kind: LineKind, text: string, script?: string | null) => void;

/** The non-event lines the Console keeps. Engine events have their own cap,
 *  since a fit writes thousands and would push its own call off the top. */
export const LINE_CAP = 400;
export const EVENT_CAP = 4000;

export function makeLine(kind: LineKind, text: string, script?: string | null,
                         t: number = Date.now() / 1000): Line {
  return script === undefined ? { kind, text, t } : { kind, text, t, script };
}

/** An engine event as a Console line, stamped with the event's own time. */
export function eventLine(event: EngineEvent): Line {
  const line = makeLine("event", consoleLine(event), undefined, event.t ?? Date.now() / 1000);
  const data = event.data ?? {};
  line.ev = { kind: event.kind };
  if (typeof data.stage === "string") line.ev.stage = data.stage;
  if (typeof data.n_eval === "number") line.ev.n_eval = data.n_eval;
  return line;
}

/** Append `line`, dropping the oldest of its own class past that class's cap. */
export function pushLine(lines: readonly Line[], line: Line,
                         caps: { lines: number; events: number } = { lines: LINE_CAP, events: EVENT_CAP }): Line[] {
  const next = [...lines, line];
  const isEvent = line.kind === "event";
  const cap = isEvent ? caps.events : caps.lines;
  let count = 0;
  for (const l of next) if ((l.kind === "event") === isEvent) count += 1;
  if (count <= cap) return next;
  const drop = next.findIndex((l) => (l.kind === "event") === isEvent);
  next.splice(drop, 1);
  return next;
}

/**
 * The two panels this page shares with today's GUI (`panels/FileMenu.svelte`,
 * `panels/NewProject.svelte`) write plain strings, and today's page mounts
 * them too. This is the one place a kind is read off a line's spelling, at
 * that boundary only: `refused: …` is a refusal, `# …` a comment, the rest a
 * call. Their calls name receivers the preamble does not bind (`shutil`,
 * `Path`, `Project.create`), so none is repeated by the script.
 */
export function sharedSay(say: Say): (line: string) => void {
  return (line: string) => {
    if (line.startsWith("refused:")) say("refusal", line);
    else if (line.startsWith("#")) say("comment", line);
    else say("call", line, null);
  };
}

/** A stage run's runnable form: the stage exactly as the run route took it
 *  (`StageSpec`, every field), where the echo shows its name and globs. */
export function stageScript(stage: unknown): string {
  const json = JSON.stringify(stage);
  return `p.run_stage(rx.StageSpec.model_validate_json(${JSON.stringify(json)}).to_stage())`;
}

/** A whole-model edit's runnable form: the model the route took, in full.
 *  The echo names the field that changed; the script carries the model. */
export function structureScript(structure: unknown): string {
  return `ref.edit(structure=rx.Structure.model_validate_json(${JSON.stringify(JSON.stringify(structure))}))`;
}

export function instrumentScript(instrument: unknown): string {
  return `ref.edit(instrument=rx.Instrument.model_validate_json(${JSON.stringify(JSON.stringify(instrument))}))`;
}

/** The receivers the script's preamble binds: a call on any other cannot run
 *  in it. */
const BOUND = /^(p|ref|rx)\./;

/**
 * The runnable form of a call the server echoed (the Text tab's applied
 * verbs): `undefined`, the text itself, when it names a bound receiver and
 * elides nothing; `null` otherwise. `session.move_peak(…)` names the GUI's
 * own session, and `rx.PlanSpec(…3 stage(s))` stands for a plan it does not
 * spell out.
 */
export function serverScript(text: string): undefined | null {
  return BOUND.test(text) && !text.includes("…") ? undefined : null;
}

/**
 * What the Console draws: the lines grouped into entries, as the prototype
 * draws them. An entry is one action's lines (a timestamp, its calls, what
 * came back), written in one turn of the page's event loop: `Line.entry`
 * says which, stamped by the writer. A run's engine events fold under the
 * call that started it (the maintainer's ruling of 2026-11-21): they join
 * the newest entry holding a `run` call, whatever was written since. Events
 * from before any run on this page (a stream replayed at load) open the list
 * in an entry of their own, with no call.
 */
export interface Entry {
  id: number;
  t: number;
  lines: Line[];
  events: Line[];
}

export function entries(lines: readonly Line[]): Entry[] {
  const out: Entry[] = [];
  let runEntry: Entry | null = null;
  let earlier: Entry | null = null;
  for (const line of lines) {
    if (line.kind === "event") {
      if (!runEntry && !earlier) {
        earlier = { id: -1, t: line.t, lines: [], events: [] };
        out.unshift(earlier);
      }
      (runEntry ?? earlier)!.events.push(line);
      continue;
    }
    let last: Entry | undefined = out[out.length - 1];
    if (!last || last === earlier || line.entry === undefined || last.id !== line.entry) {
      last = { id: line.entry ?? -2, t: line.t, lines: [], events: [] };
      out.push(last);
    }
    last.lines.push(line);
    if (line.run) runEntry = last;
  }
  return out;
}

/** The fold's one line: how many events, and the stages and evaluations
 *  they report. A stage's evaluations are its largest `n_eval`, which counts
 *  every measured trial even where the ring dropped some of the events. */
export function foldSummary(events: readonly Line[]): string {
  const n = events.length;
  const parts = [`${n} engine event${n === 1 ? "" : "s"}`];
  let stages = 0;
  const evals = new Map<string, number>();
  for (const { ev } of events) {
    if (!ev) continue;
    if (ev.kind === "stage_start") stages += 1;
    if (ev.kind === "eval" && ev.n_eval !== undefined) {
      const key = `${stages}:${ev.stage ?? ""}`;
      evals.set(key, Math.max(evals.get(key) ?? 0, ev.n_eval));
    }
  }
  if (stages) parts.push(`${stages} stage${stages === 1 ? "" : "s"}`);
  const total = [...evals.values()].reduce((a, b) => a + b, 0);
  if (total) parts.push(`${total} evaluation${total === 1 ? "" : "s"}`);
  return parts.join(", ");
}

/** A time of day as the prototype prints it, `HH:MM:SS`. */
export function clock(t: number): string {
  const d = new Date(t * 1000);
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map((v) => String(v).padStart(2, "0")).join(":");
}

/** A call cut into plain runs, string literals and a trailing comment: the
 *  two syntax classes the Console colours. */
export type Piece = { text: string; cls: "" | "str" | "cm" };

export function pieces(text: string): Piece[] {
  const out: Piece[] = [];
  const re = /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|(#.*$)/g;
  let at = 0;
  for (const m of text.matchAll(re)) {
    const start = m.index ?? 0;
    if (start > at) out.push({ text: text.slice(at, start), cls: "" });
    out.push({ text: m[0], cls: m[1] ? "str" : "cm" });
    at = start + m[0].length;
  }
  if (at < text.length) out.push({ text: text.slice(at), cls: "" });
  return out;
}

/** What Copy takes: the calls alone, one per line, without prompts,
 *  timestamps or output (the prototype's Copy). */
export function copyText(lines: readonly Line[]): string {
  const calls = lines.filter((l) => l.kind === "call").map((l) => l.text);
  return calls.length ? calls.join("\n") + "\n" : "";
}

/**
 * The session as a Python script: File › Export › Console as a Python script.
 *
 * Built from the page's uncapped store of calls, so a long session's start
 * is never lost to the Console's cap. The preamble binds the names the calls
 * use (`rx`, `p`, `ref`, the prototype's spelling) and opens the project
 * named on the command line, because the script changes the project it
 * opens and is meant for a copy: running it on the original would repeat
 * every step on top of the session's own. The lines the Console opens a
 * session with (`Line.preamble`) are the script's own preamble, written
 * here for the copy. A call with no runnable form is written as a comment, and
 * the head says how many there are, so a reader knows the script may not
 * reach the session's state. The project's settings are saved at the end,
 * as the GUI saves them on each verb.
 */
export function sessionScript(calls: readonly Line[], projectPath: string,
                              when: Date = new Date()): string {
  const name = projectPath.replace(/[\\/]+$/, "").split(/[\\/]/).pop()!.replace(/\.rex$/, "");
  const body: string[] = [];
  let skipped = 0;
  for (const line of calls) {
    if (line.kind !== "call" || line.preamble) continue;
    if (line.script === null) {
      skipped += 1;
      body.push(`# not repeated: ${line.text}`);
    } else {
      body.push(line.script ?? line.text);
    }
  }
  const day = [when.getFullYear(), when.getMonth() + 1, when.getDate()]
    .map((v) => String(v).padStart(2, "0")).join("-");
  const head = [
    `# ${name}: the rietx GUI session of ${day}, as a script.`,
    `# The session ran on ${projectPath}.`,
    "# The script changes the project it opens, so run it on a copy:",
    `#   python ${name}.py path/to/copy.rex`,
  ];
  if (skipped) {
    head.push(`# ${skipped} of its ${body.length} steps are comments: the window ran them,`,
              "# and this script does not repeat them, so it may not reach the same state.");
  }
  return [...head, "import sys", "", "import rietx as rx", "",
          "p = rx.Project.open(sys.argv[1])", "ref = p.refinement", "",
          ...body, ...(body.length ? [""] : []), "p.save()", ""].join("\n");
}
