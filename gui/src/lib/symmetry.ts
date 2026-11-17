/**
 * Rendering the symmetry the server serves (WP-1035).
 *
 * Every function here is a **formatter**.  Nothing computes a tie, a Laue class,
 * a site symmetry or a compatibility verdict: those come off `GET /api/structure`'s
 * `symmetry`/`causes` arms, `GET /api/structure/symmetry`, and the preview verb,
 * all of which read the same `cell_constraints` / `stabilizer_rotations` /
 * `ParameterTable` the refinement itself reads.  A second copy of the crystal
 * systems in TypeScript is exactly the thing WP-1014's split exists to prevent,
 * and WP-1036's measurement is why: 79 of gemmi's 564 settings were served wrong
 * under a *correct* free-parameter count, so a client that "knew" the rule would
 * be wrong in a way no count could catch.
 *
 * They live here rather than in `Model.svelte` so they can be asserted without a
 * DOM, which is the same reason `table.ts` and `fnmatch.ts` do.
 */

/** One phase's arm of `GET /api/structure`'s `symmetry`. */
export interface PhaseSymmetry {
  phase: number;
  space_group: string;
  /** absent when the symbol does not resolve — `error` is present instead */
  xhm?: string;
  number?: number;
  crystal_system?: string;
  laue_class?: string;
  point_group?: string;
  centring?: string;
  ext?: string;
  unique_axis?: string;
  centrosymmetric?: boolean;
  reference_setting?: boolean;
  setting?: string;
  ties?: Record<string, string>;
  fixed_angles?: Record<string, number>;
  constraints?: string;
  error?: string;
}

/** One row of `GET /api/structure/symmetry`'s `letters`. */
export interface SiteLetter {
  path: string;
  atom: number;
  label: string;
  wyckoff?: string;
  site_symmetry?: string;
  multiplicity?: number;
  error?: string;
}

export type Tone = "bad" | "warn" | "info";

/**
 * The line under the space-group field: what the symbol *is*.
 *
 * The **setting** is named wherever it is not the reference one — a `:H`/`:R`
 * extension or a monoclinic unique axis decides which cell edges are tied, and a
 * summary showing "trigonal" alone does not determine what the reader is looking
 * at (WP-1036).  Everything here is a served field; the order is chosen so the
 * first two items fit a 340 px column.
 */
export function symmetryLine(facts: PhaseSymmetry | null | undefined): string {
  if (!facts) return "";
  if (facts.error) return facts.error;
  const parts = [`No. ${facts.number}`, facts.crystal_system ?? ""];
  if (facts.unique_axis) parts.push(`unique axis ${facts.unique_axis}`);
  if (facts.ext) parts.push(facts.ext === "R" ? "rhombohedral axes" : "hexagonal axes");
  parts.push(`Laue ${facts.laue_class}`);
  if (facts.centring) parts.push(`${facts.centring} lattice`);
  parts.push(facts.centrosymmetric ? "centrosymmetric" : "non-centrosymmetric");
  return parts.filter(Boolean).join(" · ");
}

/** How loudly a preview note reads.  The kinds are the server's vocabulary. */
export function noteTone(kind: string): Tone {
  if (kind === "orbit_collision") return "bad";
  if (kind === "setting_change" || kind === "centring_change"
      || kind === "multiplicity_change" || kind.startsWith("free_paths_")) return "warn";
  return "info";
}

/**
 * The structural diff as sentences — what the parameter table would gain or lose.
 *
 * Counts, then the first few paths: at 340 px a list of nineteen dot-paths is a
 * wall, and the count is the part a reader acts on.  An empty diff says so out
 * loud rather than rendering nothing, because "the table does not move" is a
 * real answer to "what would this change" and an empty panel is not.
 */
export function entryLines(entries: Record<string, string[]> | undefined,
                           limit = 4): string[] {
  const say: [string, string][] = [
    ["added", "parameter(s) appear"],
    ["removed", "parameter(s) disappear"],
    ["tied", "become tied to another row"],
    ["untied", "stop being tied and refine on their own"],
    ["locked", "become locked by symmetry"],
    ["unlocked", "stop being locked"],
  ];
  const out: string[] = [];
  for (const [key, phrase] of say) {
    const paths = entries?.[key] ?? [];
    if (!paths.length) continue;
    const shown = paths.slice(0, limit).map(shortPath).join(", ");
    out.push(`${paths.length} ${phrase}: ${shown}`
      + (paths.length > limit ? ` … +${paths.length - limit}` : ""));
  }
  return out;
}

/**
 * Per-atom site changes, one sentence each — the shape the atom table shows.
 *
 * The **multiplicity** is in here because it is the one of the three that no
 * parameter reflects: a browser pass on NAC's `I 21 3` → `I 41 3 2` found every
 * stabiliser and every DOF unchanged while every orbit doubled, and the panel
 * read "no parameter gains or loses a tie".
 */
export function siteLines(sites: any[] | undefined): string[] {
  return (sites ?? []).map((site) => {
    const from = site.from ?? {};
    const to = site.to ?? {};
    const parts = [`site symmetry order ${from.order} → ${to.order}`];
    if (from.multiplicity !== to.multiplicity) {
      parts.push(`multiplicity ${from.multiplicity} → ${to.multiplicity}`);
    }
    parts.push(from.dofs === to.dofs
      ? `${to.dofs} coordinate DOF(s)`
      : `${from.dofs} → ${to.dofs} coordinate DOF(s)`);
    return `${site.label}: ${parts.join(", ")}`;
  });
}

/** `"8a · .3."` for the atom table, or `""` when the letters are not loaded. */
export function wyckoffLabel(letters: readonly SiteLetter[] | undefined,
                            base: string): string {
  const row = (letters ?? []).find((l) => l.path === base);
  if (!row || row.error || !row.wyckoff) return "";
  return `${row.wyckoff} · ${row.site_symmetry ?? "?"}`;
}

/** A dot-path with its `phases.N.` prefix dropped — the panel is already in one. */
export function shortPath(path: string): string {
  return path.replace(/^phases\.\d+\./, "").replace(/^instrument\./, "");
}

/**
 * Whether a typed symbol is worth previewing.
 *
 * Only "is it different, and is it non-empty" — **not** whether it resolves.
 * gemmi's table is the authority on that and it is on the other side of the
 * wire; a client-side symbol regex would refuse settings that are perfectly
 * legal (`R -3 c:R`, `P 1 1 21/b`) and is the second-copy trap in miniature.
 */
export function symbolChanged(typed: string, current: string): boolean {
  return typed.trim() !== "" && typed.trim() !== (current ?? "").trim();
}

/** One piece of a typeset Hermann-Mauguin symbol. */
export type SymbolToken =
  | { kind: "letter"; text: string }
  | { kind: "digit"; text: string }
  | { kind: "bar"; text: string }
  | { kind: "screw"; text: string; sub: string }
  | { kind: "slash"; text: "/" };

/**
 * A Hermann-Mauguin symbol as the International Tables print it (WP-2131).
 *
 * The maintainer ruled on 2026-11-08 that a space group is typeset in a serif
 * face: letters italic, a rotoinversion as a digit under a bar, a screw axis
 * as a digit with its subscript. The words of gemmi's spelling are joined
 * without spaces, so `P 21/c` reads P2₁/c. A setting such as the `H` of
 * `R -3 c:H` comes back beside the symbol rather than typeset.
 */
export function symbolTokens(symbol: string): { tokens: SymbolToken[]; ext: string } {
  const [body, ext = ""] = (symbol ?? "").split(":");
  const tokens: SymbolToken[] = [];
  for (const word of body.trim().split(/\s+/).filter(Boolean)) {
    word.split("/").forEach((part, i) => {
      if (i) tokens.push({ kind: "slash", text: "/" });
      if (/^-\d$/.test(part)) tokens.push({ kind: "bar", text: part[1] });
      else if (/^\d\d$/.test(part)) tokens.push({ kind: "screw", text: part[0], sub: part[1] });
      else if (/^\d$/.test(part)) tokens.push({ kind: "digit", text: part });
      else if (part) tokens.push({ kind: "letter", text: part });
    });
  }
  return { tokens, ext: ext.trim() };
}
