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
  return makeLine("event", consoleLine(event), undefined, event.t ?? Date.now() / 1000);
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
