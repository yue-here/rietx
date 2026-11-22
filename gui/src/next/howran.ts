/**
 * How the last Refine ran, in words (WP-2227, the maintainer's rulings of
 * 2026-11-22).
 *
 * A second Refine on a model the last fit converged runs the plan in one
 * stage (WP-2224). It runs in stages when the plan frees something the last
 * fit held, and when the one stage is rejected. The person sees which, and
 * why, beside Rwp on the Pattern graph's title line and in the status bar
 * while the one stage runs; the Console carries the plan line
 * `Refinement.summary()` prints.
 *
 * The server says what happened (`how` on the run frame and on
 * `GET /api/result`, read off the refinement's own record); this only words
 * it. A released family is named by its `rietx.help` title, as its chip in
 * the Plan tab is (`./plan.ts:globName`).
 */
import type { HelpCorpus } from "../lib/help";
import type { HowRan, RunState } from "../lib/stream";
import { globName } from "./plan";

/** The Console's comment after a fit ends: the plan line `summary()` prints,
 *  or `null` for a run that was not a fit or carries none. */
export function howComment(frame: RunState | null): string | null {
  const plan = frame?.run?.how?.plan_line;
  return frame?.run?.kind === "fit" && plan ? `# ${plan}` : null;
}

/** A list of names as a sentence says it: `A`, `A and B`, `A, B and 3 more`. */
function nameList(names: readonly string[]): string {
  if (names.length <= 2) return names.join(" and ");
  return `${names.slice(0, 2).join(", ")} and ${names.length - 2} more`;
}

/** The words for how a fit ran, or `""` when there is nothing to say. */
export function howWords(how: HowRan | null | undefined, corpus: HelpCorpus | null): string {
  if (!how) return "";
  if (how.ran === "one_stage") return "One stage: the model had converged";
  if (how.reason === "fallback") {
    return how.diverged ? "In stages: the one-stage re-fit diverged"
      : "In stages: the one-stage re-fit was discarded";
  }
  if (how.reason === "released") {
    const names: string[] = [];
    for (const key of how.families ?? []) {
      const name = globName(key, corpus) ?? key;
      if (!names.includes(name)) names.push(name);
    }
    if (names.length) return `In stages: ${nameList(names)} ${names.length > 1 ? "were" : "was"} held`;
  }
  return "In stages";
}
