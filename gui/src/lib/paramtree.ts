/**
 * The Parameters panel as a tree: sections, rows, groups and atom tables (WP-2126).
 *
 * Grouping B, ruled 2026-11-07: a family of parameters for one effect is a
 * group, a single parameter is a row; rows come first, then groups in the
 * order a refinement frees them. One atom is one row (2026-11-06). The cell's
 * rows that cannot be freed fold into one line in the crystallographer's
 * notation, `a = b = c, α = β = γ = 90°`, built from the setting's own ties and
 * fixed angles (`crystallography.symmetry.cell_constraints`, served on `GET
 * /api/structure`'s `symmetry` arm) rather than from the crystal system's name,
 * which cannot tell a rhombohedral setting from a hexagonal one.
 *
 * Nothing here decides what a row *is*: the families are the server's
 * `help_key` globs, the held reasons the server's fields. A path no rule below
 * places still lands somewhere, grouped by its family, so no parameter of the
 * old table becomes unreachable.
 */
import { leafName, type ParamRow } from "./table";

export interface PhaseInfo {
  name: string;
  space_group: string;
  crystal_system?: string;
  /** the setting's cell ties, `{b: "a", c: "a"}` */
  ties?: Record<string, string>;
  /** the setting's fixed angles, `{alpha: 90, beta: 90, gamma: 120}` */
  fixed_angles?: Record<string, number>;
  atoms: Array<{ label: string; species: string }>;
}

export interface SiteInfo {
  path: string;
  dof_paths: string[];
  dof_directions: number[][];
}

export interface LetterInfo {
  path: string;
  wyckoff?: string;
  multiplicity?: number;
  site_symmetry?: string;
}

export interface TreeInfo {
  phases: PhaseInfo[];
  sites: SiteInfo[];
  letters: LetterInfo[];
  /** the corpus title of a family, or null */
  titleOf: (helpKey: string | null) => string | null;
  /** keep only these rows (the filter); everything when absent */
  keep?: (path: string) => boolean;
}

export interface Line {
  kind: "row";
  key: string;
  row: ParamRow;
  label: string;
  /** the slot column this row's number shares */
  column: string;
}

export interface Fold {
  text: string;
  lines: Line[];
}

export interface Group {
  kind: "group";
  key: string;
  title: string;
  lines: Line[];
  /** what the group's toggle frees and fixes: its rows a user may free */
  members: ParamRow[];
  fold?: Fold;
  /** a group drawn without its rows (the background's coefficients) */
  summary?: string;
}

export interface AtomCell {
  row: ParamRow | null;
  /** the DOF whose box sits beside this coordinate, if this is the first
   *  coordinate that DOF moves (a box sits by what it controls, never by a
   *  follower — second review, 2026-11-07) */
  dof: ParamRow | null;
}

export interface AtomRow {
  key: string;
  /** `phases.i.atoms.j` */
  path: string;
  index: number;
  label: string;
  species: string;
  wyckoff: string;
  siteSymmetry: string;
  multiplicity: number | null;
  x: AtomCell;
  y: AtomCell;
  z: AtomCell;
  occ: ParamRow | null;
  biso: ParamRow | null;
  /** every DOF row of the site, for the padlock */
  dofs: ParamRow[];
}

export interface AtomTable {
  kind: "atoms";
  key: string;
  phase: number;
  atoms: AtomRow[];
}

export type Item = Line | Group | AtomTable;

export interface Section {
  key: string;
  kind: "phase" | "instrument" | "variables" | "other";
  title: string;
  spaceGroup: string;
  system: string;
  items: Item[];
}

const GREEK: Record<string, string> = { alpha: "α", beta: "β", gamma: "γ" };
const LENGTHS = ["a", "b", "c"];
const ANGLES = ["alpha", "beta", "gamma"];

/** The folded line for a cell's held rows: `a = b = c, α = β = γ = 90°`.
 *
 * Built from the setting's ties and fixed angles: each source with what is tied
 * to it is one equality (`a = b`, or `α = β = γ` on rhombohedral axes, where
 * α is free); fixed angles group by value, in α β γ order. Empty when the
 * setting holds nothing (triclinic). */
export function cellFoldText(ties: Record<string, string> = {},
                             fixed: Record<string, number> = {}): string {
  const parts: string[] = [];
  const glyph = (name: string) => GREEK[name] ?? name;
  for (const family of [LENGTHS, ANGLES]) {
    for (const source of family) {
      const tied = family.filter((name) => ties[name] === source);
      if (tied.length) parts.push([source, ...tied].map(glyph).join(" = "));
    }
  }
  const byValue = new Map<string, string[]>();
  for (const name of ANGLES) {
    if (!(name in fixed)) continue;
    const value = `${Number(fixed[name].toFixed(4))}`;
    byValue.set(value, [...(byValue.get(value) ?? []), glyph(name)]);
  }
  for (const [value, names] of byValue) parts.push(`${names.join(" = ")} = ${value}°`);
  return parts.join(", ");
}

function leaf(path: string): string {
  return path.slice(path.lastIndexOf(".") + 1);
}

/** Where a phase-relative path lands. */
const PHASE_GROUPS: Array<{ key: string; title: string; test: (rest: string) => boolean }> = [
  { key: "cell", title: "Cell", test: (r) => r.startsWith("cell.") },
  { key: "size", title: "Size and strain",
    test: (r) => /^(lor|gauss)_(size|strain)$/.test(r) },
];

const PHASE_ROWS: Record<string, string> = { scale: "Scale", extinction: "Extinction" };

/** The instrument, in the prototype's order: zero and displacement rows, then
 *  the background, the peak shape, the axial divergence, and the rest of the
 *  source and geometry. */
const INSTRUMENT_ROWS: Record<string, string> = {
  zero_shift: "Zero shift",
  "geometry.sample_displacement": "Sample displacement",
  "geometry.sample_transparency": "Sample transparency",
  "geometry.capillary_offset_along_beam": "Capillary offset, along the beam",
  "geometry.capillary_offset_across_beam": "Capillary offset, across the beam",
};

const INSTRUMENT_GROUPS: Array<{ key: string; title: string; test: (rest: string) => boolean;
                                  rowless?: boolean }> = [
  { key: "background", title: "Background", test: (r) => r.startsWith("background."),
    rowless: true },
  { key: "profile", title: "Peak shape", test: (r) => r.startsWith("profile.") },
  { key: "axial", title: "Axial divergence", test: (r) => r.startsWith("geometry.axial_") },
  { key: "roughness", title: "Surface roughness",
    test: (r) => r.startsWith("geometry.surface_roughness.") },
  { key: "source", title: "Source and geometry",
    test: (r) => r.startsWith("source.") || r.startsWith("geometry.") || r === "polarization" },
];

function line(row: ParamRow, label: string, column: string): Line {
  return { kind: "row", key: row.path, row, label, column };
}

/** A group's lines under their corpus titles. Two members of one family share a
 *  title (each emission line's weight is "Emission line weight"), so a title
 *  that repeats carries the index its path names, counted from 0 as the help
 *  corpus counts them ("line 0 is locked at 1"). */
function titledLines(members: ParamRow[], info: TreeInfo, column: string): Line[] {
  const titles = members.map((r) => info.titleOf(r.help_key) ?? leaf(r.path));
  return members.map((r, k) => {
    const repeated = titles.filter((t) => t === titles[k]).length > 1;
    const index = /\.(\d+)(\.|$)/.exec(r.path);
    return line(r, repeated && index ? `${titles[k]} ${index[1]}` : titles[k], column);
  });
}

function group(key: string, title: string, lines: Line[], rows: ParamRow[]): Group {
  return { kind: "group", key, title, lines, members: rows.filter((r) => r.refinable || r.vary) };
}

/** Rows no fixed rule placed, by family: a family of one is a row, of more a
 *  group (grouping B applied to whatever a later build adds). */
function families(rows: ParamRow[], prefix: string, info: TreeInfo): Item[] {
  const byKey = new Map<string, ParamRow[]>();
  for (const row of rows) {
    const key = row.help_key ?? row.path.slice(0, row.path.lastIndexOf("."));
    const bucket = byKey.get(key);
    if (bucket) bucket.push(row);
    else byKey.set(key, [row]);
  }
  const singles: Item[] = [];
  const groups: Item[] = [];
  for (const [key, members] of byKey) {
    const title = info.titleOf(members[0].help_key) ?? leaf(key.replace(/\.\*$/, ""));
    if (members.length === 1) {
      singles.push(line(members[0], title, `${prefix}${members[0].path}`));
    } else {
      const gkey = `${prefix}${key}`;
      groups.push(group(gkey, title,
        members.map((row) => line(row, leafName(row.path), gkey)), members));
    }
  }
  return [...singles, ...groups];
}

function atomTable(phase: number, rows: ParamRow[], info: TreeInfo): AtomTable | null {
  const byAtom = new Map<number, Map<string, ParamRow>>();
  for (const row of rows) {
    const m = /^phases\.\d+\.atoms\.(\d+)\.(.+)$/.exec(row.path);
    if (!m) continue;
    const j = Number(m[1]);
    if (!byAtom.has(j)) byAtom.set(j, new Map());
    byAtom.get(j)!.set(m[2], row);
  }
  if (!byAtom.size) return null;
  const pinfo = info.phases[phase];
  const atoms: AtomRow[] = [];
  for (const [j, fields] of [...byAtom].sort((a, b) => a[0] - b[0])) {
    const path = `phases.${phase}.atoms.${j}`;
    const site = info.sites.find((s) => s.path === path);
    const letter = info.letters.find((l) => l.path === path);
    const cells: Record<string, AtomCell> = {
      x: { row: fields.get("x") ?? null, dof: null },
      y: { row: fields.get("y") ?? null, dof: null },
      z: { row: fields.get("z") ?? null, dof: null },
    };
    const dofs: ParamRow[] = [];
    const claimed = new Set<string>();
    (site?.dof_paths ?? []).forEach((dofPath, k) => {
      const dof = fields.get(dofPath.slice(path.length + 1));
      if (!dof) return;
      dofs.push(dof);
      const direction = site!.dof_directions[k] ?? [];
      const axis = ["x", "y", "z"].find((a, i) => direction[i] && !claimed.has(a));
      if (axis) {
        claimed.add(axis);
        cells[axis].dof = dof;
      }
    });
    atoms.push({
      key: path, path, index: j,
      label: pinfo?.atoms[j]?.label ?? `atom ${j}`,
      species: pinfo?.atoms[j]?.species ?? "",
      wyckoff: letter?.wyckoff ?? "",
      siteSymmetry: letter?.site_symmetry ?? "",
      multiplicity: letter?.multiplicity ?? null,
      x: cells.x, y: cells.y, z: cells.z,
      occ: fields.get("occ") ?? null,
      biso: fields.get("biso") ?? null,
      dofs,
    });
  }
  return { kind: "atoms", key: `phases.${phase}.atoms`, phase, atoms };
}

/** The atom table's own fields; anything else under an atom (an ADP block)
 *  is placed by family. */
const ATOM_FIELDS = /^phases\.\d+\.atoms\.\d+\.(x|y|z|occ|biso|dof\.\d+)$/;

function phaseSection(i: number, rows: ParamRow[], info: TreeInfo): Section {
  const pinfo = info.phases[i];
  const prefix = `phases.${i}.`;
  const items: Item[] = [];
  const placed = new Set<string>();
  const kept = rows.filter((r) => !info.keep || info.keep(r.path));
  for (const [name, title] of Object.entries(PHASE_ROWS)) {
    const row = kept.find((r) => r.path === `${prefix}${name}`);
    if (row) {
      items.push(line(row, title, row.path));
      placed.add(row.path);
    }
  }
  const groups: Item[] = [];
  for (const spec of PHASE_GROUPS) {
    const members = kept.filter((r) => spec.test(r.path.slice(prefix.length)));
    if (!members.length) continue;
    members.forEach((r) => placed.add(r.path));
    const key = `${prefix}${spec.key}`;
    if (spec.key === "cell") {
      const ties = pinfo?.ties ?? {};
      const fixed = pinfo?.fixed_angles ?? {};
      const folded = (r: ParamRow) => {
        const name = leaf(r.path);
        return !r.refinable && !r.vary && !r.held && (name in ties || name in fixed);
      };
      const label = (r: ParamRow) => GREEK[leaf(r.path)] ?? leaf(r.path);
      const lines = members.filter((r) => !folded(r)).map((r) => line(r, label(r), key));
      const hidden = members.filter(folded).map((r) => line(r, label(r), key));
      const g = group(key, spec.title, lines, members);
      const text = cellFoldText(ties, fixed);
      if (hidden.length && text) g.fold = { text, lines: hidden };
      else g.lines.push(...hidden);
      groups.push(g);
    } else {
      groups.push(group(key, spec.title, titledLines(members, info, key), members));
    }
  }
  const atomRows = kept.filter((r) => ATOM_FIELDS.test(r.path));
  atomRows.forEach((r) => placed.add(r.path));
  const rest = kept.filter((r) => !placed.has(r.path));
  const extra = families(rest, prefix, info);
  items.push(...extra.filter((it) => it.kind === "row"));
  items.push(...groups, ...extra.filter((it) => it.kind !== "row"));
  const table = atomTable(i, atomRows, info);
  if (table) items.push(table);
  return {
    key: `phases.${i}`, kind: "phase", title: pinfo?.name || `Phase ${i + 1}`,
    spaceGroup: pinfo?.space_group ?? "", system: pinfo?.crystal_system ?? "", items,
  };
}

function instrumentSection(rows: ParamRow[], info: TreeInfo): Section {
  const prefix = "instrument.";
  const kept = rows.filter((r) => !info.keep || info.keep(r.path));
  const items: Item[] = [];
  const placed = new Set<string>();
  for (const [name, title] of Object.entries(INSTRUMENT_ROWS)) {
    const row = kept.find((r) => r.path === `${prefix}${name}`);
    if (row) {
      items.push(line(row, title, row.path));
      placed.add(row.path);
    }
  }
  const groups: Item[] = [];
  for (const spec of INSTRUMENT_GROUPS) {
    const members = kept.filter((r) => !placed.has(r.path)
      && spec.test(r.path.slice(prefix.length)));
    if (!members.length) continue;
    members.forEach((r) => placed.add(r.path));
    const key = `${prefix}${spec.key}`;
    if (spec.rowless) {
      const g = group(key, spec.title, [], members);
      g.summary = `${members.length} ${members.length === 1 ? "term" : "terms"}`;
      groups.push(g);
    } else {
      groups.push(group(key, spec.title, titledLines(members, info, key), members));
    }
  }
  const extra = families(kept.filter((r) => !placed.has(r.path)), prefix, info);
  items.push(...extra.filter((it) => it.kind === "row"), ...groups,
             ...extra.filter((it) => it.kind !== "row"));
  return { key: "instrument", kind: "instrument", title: "Instrument", spaceGroup: "",
           system: "", items };
}

/** The panel's sections: every phase, the instrument, then user variables and
 *  anything else the table holds, each section only when it has a row. */
export function buildTree(rows: readonly ParamRow[], info: TreeInfo): Section[] {
  const phases = new Map<number, ParamRow[]>();
  const instrument: ParamRow[] = [];
  const variables: ParamRow[] = [];
  const other: ParamRow[] = [];
  for (const row of rows) {
    const m = /^phases\.(\d+)\./.exec(row.path);
    if (m) {
      const i = Number(m[1]);
      const bucket = phases.get(i);
      if (bucket) bucket.push(row);
      else phases.set(i, [row]);
    } else if (row.path.startsWith("instrument.")) instrument.push(row);
    else if (row.path.startsWith("vars.")) variables.push(row);
    else other.push(row);
  }
  const sections: Section[] = [];
  for (const i of [...phases.keys()].sort((a, b) => a - b)) {
    sections.push(phaseSection(i, phases.get(i)!, info));
  }
  if (instrument.length) sections.push(instrumentSection(instrument, info));
  const keep = (r: ParamRow) => !info.keep || info.keep(r.path);
  const vars = variables.filter(keep);
  if (vars.length) {
    sections.push({ key: "vars", kind: "variables", title: "User variables", spaceGroup: "",
                    system: "", items: vars.map((r) => line(r, r.path.slice(5), r.path)) });
  }
  const rest = other.filter(keep);
  if (rest.length) {
    sections.push({ key: "other", kind: "other", title: "Other", spaceGroup: "", system: "",
                    items: families(rest, "", info) });
  }
  return sections.filter((s) => s.items.some((it) =>
    it.kind !== "atoms" || it.atoms.length));
}

/** The tri-state of a set of boxes: all on, none, or mixed (`null`). */
export function triState(flags: readonly boolean[]): boolean | null {
  if (!flags.length) return false;
  const on = flags.filter(Boolean).length;
  return on === 0 ? false : on === flags.length ? true : null;
}
