/** The status bar's words, as pure functions (WP-2207).
 *
 * The run state left the header for the status bar because a slot whose words
 * change must sit where nothing depends on its width: in the header it was a
 * content-sized pill in a right-aligned group, so a project's first run, `idle`
 * becoming `converged`, moved `Simple | Advanced`, the theme and `Cancel` 35 px
 * to the left. In the bar it is a slot that takes the room left between the
 * console toggle and `Cancel`, and the words are written here once.
 */
import type { RunState } from "./stream";

/** The run's state in words: the stage and its count while a run is in flight,
 *  the last run's status after one, and `idle` before any. `null` before the
 *  first state frame arrives, which draws nothing rather than a guess. */
export function runWords(run: RunState | null): string {
  if (!run) return "";
  const r = run.run;
  if (run.state === "idle") return r.status ?? "idle";
  let text = r.stage ?? "starting";
  if (r.stage_index) text += ` (${r.stage_index}/${r.n_stages})`;
  if (r.lebail?.pass) {
    text += ` · pass ${r.lebail.pass}`;
    if (r.lebail.of) text += ` of ${r.lebail.of}`;
  }
  return text;
}

/** The modifier a shortcut is written with on this platform. */
export function modifier(platform: string): string {
  return /Mac|iPhone|iPad/.test(platform) ? "⌘" : "Ctrl+";
}

/** What the console toggle's click does, as a verb phrase (`gui/STYLE.md`
 *  § Components: a tooltip is a verb phrase, its shortcut on a second line). */
export function toggleTitle(project: boolean, shown: boolean, mod: string): string {
  if (!project) return "No project is open";
  return `${shown ? "Hide" : "Show"} the console and history\n${mod}J`;
}
