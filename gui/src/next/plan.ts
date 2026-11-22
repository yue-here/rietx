/**
 * The rebuilt Plan tab's words (WP-2231): what a stage's glob is called on its
 * chip, and what the `+ Add` picker offers.
 *
 * A plan stores globs (`StageSpec.turn_on`, `turn_off`), and a person reads
 * names. So a chip carries a name where the glob has one and the glob itself
 * where it has none, with the glob in its tooltip either way. The names come
 * from two places. A family `rietx.help` describes (`phases.*.atoms.*.biso`)
 * takes that entry's title, since what a name means is written there and
 * nowhere else (gui/CLAUDE.md, WP-1203). A glob reaching several families at
 * once (`phases.*.cell.*`) has no entry, so `GROUPS` names it, from the
 * prototype's picker ("Cell", "Background", "Peak shape").
 *
 * What a stage frees is never decided here. The picker's counts and its Fix
 * offer read `lib/fnmatch.ts` over the refinable rows as a preview, as the
 * Parameters filter does (WP-1011); what a stage does is the resolve route's
 * answer (WP-1208), drawn only once the plan is applied.
 */

import type { HelpCorpus } from "../lib/help";
import { resolve } from "../lib/help";
import { fnmatch } from "../lib/fnmatch";
import type { Stage } from "../lib/plan";

/** A glob reaching several families, and its name. Every other name is a
 *  `rietx.help` title. */
export const GROUPS: readonly { glob: string; name: string }[] = [
  { glob: "phases.*.cell.*", name: "Cell" },
  { glob: "phases.*.atoms.*.adp.*", name: "Anisotropic ADPs" },
  { glob: "phases.*.atoms.*.moment.dof*", name: "Magnetic moments" },
  { glob: "phases.*.microstrain.dof.*", name: "Anisotropic strain" },
  { glob: "phases.*.texture.*", name: "Texture" },
  { glob: "phases.*.distortion_modes.modes.*.amplitude", name: "Distortion modes" },
  { glob: "instrument.background.*", name: "Background" },
  { glob: "instrument.background.c*", name: "Background" },
  { glob: "instrument.profile.*", name: "Peak shape" },
  { glob: "instrument.geometry.axial_*", name: "Axial divergence" },
  { glob: "instrument.geometry.surface_roughness.*", name: "Surface roughness" },
  { glob: "instrument.extra_components.*", name: "Extra components" },
];

/** One refinable row as `GET /api/params` serves it, the fields used here. */
export interface PlanRow {
  path: string;
  help_key?: string | null;
  refinable: boolean;
}

/** `phases.2.cell.*` → `phases.*.cell.*` and the phase index, or the glob
 *  and `null` when it names no one phase. */
function onePhase(glob: string): { general: string; phase: number | null } {
  const m = /^phases\.(\d+)\.(.+)$/.exec(glob);
  return m ? { general: `phases.*.${m[2]}`, phase: Number(m[1]) } : { general: glob, phase: null };
}

function generalName(glob: string, corpus: HelpCorpus | null): string | null {
  const group = GROUPS.find((g) => g.glob === glob);
  if (group) return group.name;
  return resolve(corpus, `parameters:${glob}`)?.title ?? null;
}

/**
 * The words a chip carries for one glob, or `null` where the glob has no name
 * and the chip shows the glob itself. A glob naming one phase of several is
 * prefixed with the phase's name, as the prototype's picker does.
 */
export function globName(glob: string, corpus: HelpCorpus | null,
                         phaseNames: readonly string[] = []): string | null {
  const { general, phase } = onePhase(glob);
  const name = generalName(general, corpus);
  if (name === null) return null;
  if (phase === null) return name;
  const title = phaseNames[phase];
  if (phaseNames.length < 2) return name;
  return title ? `${title}: ${name}` : null;
}

/** One entry of the picker: a glob, the words it shows, how many refinable
 *  rows it reaches today, and the stages that already name it. */
export interface PickOption {
  glob: string;
  name: string;
  /** a second line of the option: the path, for a single parameter */
  detail: string;
  count: number;
}

/**
 * The picker's two lists for one stage.
 *
 * `groups` are the globs reaching more than one refinable row: the `GROUPS`
 * table, then each `rietx.help` family, one per name. With several phases,
 * each phase's own group follows the one for every phase. `parameters` is
 * each refinable row on its own, by its exact path, named by its family's
 * title.
 *
 * `pool` narrows both to some rows: the Fix side offers only what the stages
 * up to this one free, read off their globs as a preview.
 */
export function pickOptions(rows: readonly PlanRow[], corpus: HelpCorpus | null,
                            phaseNames: readonly string[] = [],
                            pool: ((path: string) => boolean) | null = null):
                            { groups: PickOption[]; parameters: PickOption[] } {
  const live = rows.filter((r) => r.refinable && (!pool || pool(r.path)));
  const reach = (glob: string) => live.filter((r) => fnmatch(r.path, glob)).length;
  const groups: PickOption[] = [];
  const taken = new Set<string>();
  const offer = (glob: string, name: string) => {
    const count = reach(glob);
    if (count < 2 || taken.has(name)) return;
    taken.add(name);
    groups.push({ glob, name, detail: "", count });
  };
  const families = [...new Set(live.map((r) => r.help_key).filter((k): k is string => !!k))];
  const generals = [...GROUPS.map((g) => g.glob), ...families];
  for (const glob of generals) {
    const name = generalName(glob, corpus);
    if (name !== null) offer(glob, name);
  }
  if (phaseNames.length > 1) {
    phaseNames.forEach((title, i) => {
      for (const glob of generals) {
        if (!glob.startsWith("phases.*.")) continue;
        const name = generalName(glob, corpus);
        if (name !== null) offer(`phases.${i}.${glob.slice("phases.*.".length)}`, `${title}: ${name}`);
      }
    });
  }
  const parameters = live.map((r) => ({
    glob: r.path,
    name: (r.help_key ? generalName(r.help_key, corpus) : null) ?? r.path,
    detail: r.path,
    count: 1,
  }));
  return { groups, parameters };
}

/** Whether an option is shown for a search: its words or its glob hold the
 *  typed text, case aside. */
export function matchesQuery(option: PickOption, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return `${option.name} ${option.glob}`.toLowerCase().includes(q);
}

/** Which other stages already free (or fix) a glob, by number from 1; the
 *  picker says "moves from stage 2", and picking it there moves it. */
export function namedIn(stages: readonly Stage[], glob: string, side: "free" | "fix",
                        except: number): number[] {
  const out: number[] = [];
  stages.forEach((s, i) => {
    const globs = side === "free" ? s.turn_on : (s.turn_off ?? []);
    if (i !== except && globs.includes(glob)) out.push(i + 1);
  });
  return out;
}

/**
 * The plan with `glob` added to stage `index` on one side. A glob on the Free
 * side is one stage's: picking it here takes it from every other stage's Free
 * row, as the prototype's picker moves a parameter. A fix is a stage's own,
 * so the Fix side adds and takes nothing elsewhere.
 */
export function withGlob(stages: readonly Stage[], index: number, glob: string,
                         side: "free" | "fix"): Stage[] {
  return stages.map((s, i) => {
    if (side === "fix") {
      const off = s.turn_off ?? [];
      return i === index && !off.includes(glob) ? { ...s, turn_off: [...off, glob] } : s;
    }
    if (i === index) return s.turn_on.includes(glob) ? s : { ...s, turn_on: [...s.turn_on, glob] };
    return s.turn_on.includes(glob) ? { ...s, turn_on: s.turn_on.filter((g) => g !== glob) } : s;
  });
}

/** What the stages up to and including `index` free, read off their globs:
 *  the Fix side's offer, a preview. */
export function freeBy(stages: readonly Stage[], index: number): (path: string) => boolean {
  const globs = stages.slice(0, index + 1).flatMap((s) => s.turn_on);
  return (path: string) => globs.some((g) => fnmatch(path, g));
}

/** A percentage at two places with a thin space, as the graph title prints Rwp. */
export function pct(value: number): string {
  return `${(value * 100).toFixed(2)} %`;
}
