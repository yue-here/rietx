/** The structure viewer's geometry, as pure functions (WP-1015, WP-1462).
 *
 * **No crystallography crosses the wire.**  `GET /api/structure3d` returns
 * Cartesian points in Å, 3×3 matrices and index pairs; everything here is the
 * arithmetic that turns those into a `Scene` the renderer draws and a `View`
 * it draws it from.  The symmetry expansion, the metric, the
 * eigen-decomposition and the bond rule are all server-side, which is the same
 * refusal WP-1010 made about decimation: two answers to "where is this atom"
 * is one more than a viewer may have.
 *
 * The one design fact worth stating here is why a ball and an ellipsoid are
 * one code path.  Every atom is `pos + M·v` over the unit sphere `v`, and the
 * renderer ray-casts that quadric exactly (`lib/gl3d.ts`), so the only
 * difference between the modes is which `M` is used: a ball is `f·r·I`, an
 * ellipsoid is `k(p)·T` from the payload.  Everything is in Å, so a ball can be
 * compared with the cell around it, which is what plotly's pixel-sized markers
 * could not do and why WP-1015 drew meshes.
 *
 * The same equation the shader solves is solved here for the pointer
 * (`pickAtom`, `pickHalf`), since the browser already holds every position and
 * matrix — so hover needs no id buffer and no pixel read-back (WP-1462 D4).
 */

export interface Site {
  index: number;
  path: string;
  label: string;
  species: string;
  element: string;
  color: string;
  radius: number;
  metal: boolean;
  occ: number;
  biso: number;
  u_iso: number;
  aniso: boolean;
  multiplicity: number;
  special: boolean;
  npd: boolean;
  /** the CIF's disorder assembly and group, `null` for an ordered site */
  disorder_assembly?: string | null;
  disorder_group?: string | null;
  /** the site's colour on a dark ground, where the server chose one
   *  (`structure3d.dark_ground_colours`: C at #666666, WP-1468) */
  dark_color?: string;
}

export interface DrawnAtom {
  site: number;
  frac: number[];
  pos: number[];
  boundary: boolean;
  /** in the payload only as a polyhedron's vertex, so drawn only while one of
   *  its polyhedra is (WP-1466); absent reads as false */
  vertex_only?: boolean;
  /** outside the cell, on a site that centres a polyhedron and as no
   *  polyhedron's vertex, so drawn only while its site's polyhedra are hidden
   *  (WP-1529); absent reads as false */
  outside_centre?: boolean;
  /** columns are the principal axes at one RMS displacement (Å) */
  ellipsoid: number[][];
  rms: number[];
  npd: boolean;
}

export interface Bond {
  i: number;
  j: number;
  a: number[];
  b: number[];
  d: number;
  /** its far end `b` is an `outside_centre` atom, so the bond is drawn only
   *  while that atom is (WP-1529); absent reads as false */
  outside_centre?: boolean;
}

/** One coordination polyhedron (WP-1466): chemistry and geometry both
 *  server-side, so a client only draws it. */
export interface Polyhedron {
  /** the centre, an index into `atoms` */
  center: number;
  site: number;
  /** indices into `atoms`, every one of them drawn */
  vertices: number[];
  /** outward-wound triangles and the edges between faces that are not
   *  coplanar, both as indices into `vertices` */
  faces: number[][];
  edges: number[][];
  /** the centre's sticks to its own vertices, indices into `bonds` */
  bonds: number[];
  coordination: number;
  mean_distance: number;
  gap: number;
  /** a second gap that would close a polyhedron too, `[ligands, ratio]`
   *  (WP-1468); absent or null when there is none */
  rival?: [number, number] | null;
  drawn_by_default: boolean;
}

/** A filled ring or named face (WP-1548): atoms the server chose, wound into
 *  triangles there (`rietx.viz.figure3d.rings`), so a client only draws it. */
export interface Fill {
  kind: "ring" | "face";
  /** indices into `atoms` */
  vertices: number[];
  /** triangles as indices into `vertices` */
  faces: number[][];
  /** `#rrggbb`, or null for `FILL_COLOR` */
  color: string | null;
}

/** A polyhedron the server found and could not draw: its ligands would have
 *  taken the payload past its atom cap. */
export interface DroppedPolyhedron {
  site: number;
  ligands: string[];
  drawn_by_default: boolean;
}

export interface Geometry {
  phase: number;
  phases: string[];
  name: string;
  space_group: string;
  cell: number[];
  volume: number;
  lattice: number[][];
  corners: number[][];
  edges: number[][];
  sites: Site[];
  atoms: DrawnAtom[];
  bonds: Bond[];
  polyhedra: Polyhedron[];
  /** the drawing's planar rings (WP-1548), filled while the drawer asks;
   *  absent reads as none */
  rings?: Fill[];
  /** the polyhedra the atom cap turned away, by centre site and ligand
   *  elements (WP-1468); absent reads as none */
  polyhedra_dropped?: DroppedPolyhedron[];
  probability: number;
  probability_levels: Record<string, number>;
  scale: number;
  ball_fraction: number;
  bond_tolerance: number;
  bond_metals: boolean;
  /** which alternatives of a disordered structure are drawn (WP-1468) */
  disorder?: Disorder;
  /** the sites `"major"` draws no image of, listed in either view */
  minor_sites?: number[];
  /** Mercury's two lists as asked for, `null` for the chemistry's (WP-1468) */
  centres?: string[] | null;
  ligands?: string[] | null;
  /** the elements a polyhedron is drawn round, and at its corners, either way */
  centre_elements?: string[];
  ligand_elements?: string[];
  note: string;
}

/** Every alternative of a disordered structure, or each assembly's most
 *  occupied group alone. */
export type Disorder = "all" | "major";

export type Mode = "ball" | "ellipsoid";

/** A 3×3 matrix, **row-major**, nine numbers. */
export type Mat3 = number[];

/**
 * A colour scaled toward black — the second depth cue, for images outside the
 * cell.
 *
 * Not decoration and not only a depth cue: a boundary atom is the *same* atom
 * seen at the opposite face (or a bonded neighbour just outside), so drawing it
 * dimmer says what it is. It also separates the case the complaint was really
 * about — two same-coloured spheres overlapping at a cell face, one of which is
 * an image of the other.
 */
export function dim(color: string, factor = 0.62): string {
  if (!/^#[0-9a-f]{6}$/i.test(color)) return color;
  const channel = (at: number) =>
    Math.round(parseInt(color.slice(at, at + 2), 16) * factor)
      .toString(16).padStart(2, "0");
  return `#${channel(1)}${channel(3)}${channel(5)}`;
}

/**
 * The geometry as the dark theme draws it: each site the server gave a
 * `dark_color` wears it.  Which sites qualify is the server's question, since
 * it needs the phase palette's OKLab distance, so this only reads the answer.
 * The same object back when no site has one.
 */
export function onDarkGround(geometry: Geometry): Geometry {
  if (!geometry.sites.some((site) => site.dark_color)) return geometry;
  return { ...geometry,
           sites: geometry.sites.map((site) =>
             site.dark_color ? { ...site, color: site.dark_color } : site) };
}

/** `#rrggbb` as three channels in 0..1; anything else is mid-grey. */
export function rgb(color: string): number[] {
  if (!/^#[0-9a-f]{6}$/i.test(color)) return [0.5, 0.5, 0.5];
  return [1, 3, 5].map((at) => parseInt(color.slice(at, at + 2), 16) / 255);
}

/** `T·v` for a 3×3 whose **columns** are the axes — the payload's convention. */
export function transform(matrix: number[][], v: number[]): number[] {
  return [
    matrix[0][0] * v[0] + matrix[0][1] * v[1] + matrix[0][2] * v[2],
    matrix[1][0] * v[0] + matrix[1][1] * v[1] + matrix[1][2] * v[2],
    matrix[2][0] * v[0] + matrix[2][1] * v[1] + matrix[2][2] * v[2],
  ];
}

/** The matrix one atom's sphere is drawn through, in the given mode.
 *
 * `ball` is deliberately isotropic even for an anisotropic site: the two modes
 * answer different questions, and a ball-and-stick that quietly showed thermal
 * motion would make the ellipsoid toggle mean nothing.
 */
export function atomTransform(geometry: Geometry, atom: DrawnAtom,
                              mode: Mode, exaggeration = 1): number[][] {
  if (mode === "ellipsoid") {
    // k(p) and the exaggeration multiply here and are *named* separately
    // everywhere they are shown: k is a probability, the other is not one
    const k = geometry.scale * exaggeration;
    return atom.ellipsoid.map((row) => row.map((value) => value * k));
  }
  const r = geometry.ball_fraction * geometry.sites[atom.site].radius;
  return [[r, 0, 0], [0, r, 0], [0, 0, r]];
}

/** One hover line per atom: what it is, where it is, and how it is displaced. */
export function atomLabel(geometry: Geometry, atom: DrawnAtom, mode: Mode): string {
  const site = geometry.sites[atom.site];
  const frac = atom.frac.map((v) => v.toFixed(4)).join(", ");
  const parts = [`${site.label} (${site.species})`, `(${frac})`];
  if (site.occ !== 1) parts.push(`occ ${site.occ.toFixed(3)}`);
  if (mode === "ellipsoid") {
    const rms = atom.rms.map((v) => v.toFixed(3)).join(" / ");
    parts.push(atom.npd ? `RMS ${rms} Å — not positive definite`
                        : `RMS ${rms} Å`);
  }
  if (atom.boundary) parts.push("image outside the cell");
  return parts.join("  ·  ");
}

/** One hover line per bond: the two sites and the length. */
export function bondLabel(geometry: Geometry, bond: Bond): string {
  const name = (index: number) => geometry.sites[geometry.atoms[index].site].label;
  return `${name(bond.i)}–${name(bond.j)}  ${bond.d.toFixed(3)} Å`;
}

const SUBSCRIPT = "₀₁₂₃₄₅₆₇₈₉";

/** A formula as a chemist writes it: the centre, then its ligands by count,
 *  most first — `AlF₆`, `CaO₆F`. */
export function formula(centre: string, ligands: readonly string[]): string {
  const counts = new Map<string, number>();
  for (const element of ligands) counts.set(element, (counts.get(element) ?? 0) + 1);
  const written = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([element, n]) => element + (n > 1 ? [...String(n)].map((d) => SUBSCRIPT[+d]).join("") : ""));
  return centre + written.join("");
}

/** A polyhedron's `formula`, read off its drawn vertices. */
export function polyhedronFormula(geometry: Geometry, polyhedron: Polyhedron): string {
  return formula(geometry.sites[polyhedron.site].element,
                 polyhedron.vertices.map((v) => geometry.sites[geometry.atoms[v].site].element));
}

/** One hover line per filled ring or face (WP-1548): its kind, size and
 *  composition, most common element first.  "Planar" is the whole claim: the
 *  package cannot tell an aromatic ring from coordinates. */
export function fillLabel(geometry: Geometry, fill: Fill): string {
  const what = fill.kind === "ring" ? `planar ${fill.vertices.length}-ring` : "face";
  return `${what}  ${formula("", fill.vertices.map((v) =>
    geometry.sites[geometry.atoms[v].site].element))}`;
}

/** One hover line per polyhedron: what it is, around which site, and its
 *  shell, with a rival gap beside it when one would close a shell too. */
export function polyhedronLabel(geometry: Geometry, polyhedron: Polyhedron): string {
  const site = geometry.sites[polyhedron.site];
  const parts = [`${polyhedronFormula(geometry, polyhedron)} around ${site.label}`,
                 `${polyhedron.coordination} ligands`,
                 `mean ${polyhedron.mean_distance.toFixed(3)} Å`,
                 `gap ×${polyhedron.gap.toFixed(2)}`];
  if (polyhedron.rival) {
    parts.push(`next gap ×${polyhedron.rival[1].toFixed(2)} after ${polyhedron.rival[0]}`);
  }
  return parts.join("  ·  ");
}

/**
 * Which polyhedra are drawn, as indices into `geometry.polyhedra`.
 *
 * `on` is the one switch, and its default is the mode's (WP-1466, P8): on in
 * ball mode, off in ellipsoid mode, where faces would cover the ADPs that mode
 * exists to show.  `formulas` holds the legend's switches, one per formula; a
 * formula it does not name takes the server's default (P5), which draws
 * shells of four to six.  A polyhedron goes with its centre's species when
 * the atom legend hides that, and with its centre when the images outside the
 * cell are hidden.
 */
export function shownPolyhedra(geometry: Geometry, on: boolean,
                               formulas: ReadonlyMap<string, boolean>,
                               hidden: ReadonlySet<string> = new Set(),
                               showBoundary = true): number[] {
  if (!on) return [];
  return geometry.polyhedra.flatMap((p, i) => {
    if (hidden.has(geometry.sites[p.site].species)) return [];
    if (!showBoundary && geometry.atoms[p.center].boundary) return [];
    return (formulas.get(polyhedronFormula(geometry, p)) ?? p.drawn_by_default) ? [i] : [];
  });
}

/**
 * The polyhedron round one atom, as indices into `geometry.polyhedra`: one
 * atom's environment, drawn alone (WP-1468).  `focus` is the atom by its
 * site and position, never by its index: a refetch appends a different set
 * of partners and corners, so an index held across one names another atom
 * or none.  Only an atom of the cell is a centre, so an image outside it
 * takes the polyhedron of its site's atom nearest to it, the same
 * environment one lattice step away; an atom of the cell is nearest its own.
 * Empty when the site closes none.
 */
export function focusedPolyhedra(geometry: Geometry,
                                 atom: Pick<DrawnAtom, "site" | "pos">): number[] {
  let best = -1, nearest = Infinity;
  geometry.polyhedra.forEach((p, i) => {
    const centre = geometry.atoms[p.center];
    if (centre.site !== atom.site) return;
    const d = Math.hypot(...[0, 1, 2].map((k) => centre.pos[k] - atom.pos[k]));
    if (d < nearest) { nearest = d; best = i; }
  });
  return best < 0 ? [] : [best];
}

/**
 * One legend switch per formula, in the order the server lists the
 * polyhedra, coloured by the centre.
 *
 * Per formula rather than per species, because the default is per shell
 * size (P5) and a formula fixes the size, so every polyhedron under one
 * switch shares its default.  One switch for a species with a CaO₆ drawn and
 * a CaO₈ hidden would read as on, and off then on would draw both, with no
 * way back to the default.  A two-state switch per formula also reaches the
 * one a three-state species switch cannot: the CaO₈ alone.
 *
 * A formula the atom cap turned away in every instance comes last, marked
 * unavailable, so the legend still names it (WP-1468).  Left out, it had
 * vanished with only the note under the picture to say so.
 */
export function polyhedraLegend(geometry: Geometry): Array<{
  formula: string; color: string; byDefault: boolean; available: boolean }> {
  const out: Array<{ formula: string; color: string; byDefault: boolean;
                     available: boolean }> = [];
  const add = (site: number, ligands: string[], byDefault: boolean, available: boolean) => {
    const written = formula(geometry.sites[site].element, ligands);
    if (!out.some((e) => e.formula === written)) {
      out.push({ formula: written, color: geometry.sites[site].color, byDefault, available });
    }
  };
  for (const p of geometry.polyhedra) {
    add(p.site, p.vertices.map((v) => geometry.sites[geometry.atoms[v].site].element),
        p.drawn_by_default, true);
  }
  for (const p of geometry.polyhedra_dropped ?? []) add(p.site, p.ligands, p.drawn_by_default, false);
  return out;
}

/** The phase's elements, once each, in the order the sites declare them: the
 *  buttons Mercury's two lists are chosen with. */
export function elements(geometry: Geometry): string[] {
  return [...new Set(geometry.sites.map((s) => s.element))];
}

/** `list` with `element` switched: in if it was out, out if it was in, sorted
 *  as the server echoes it. */
export function toggled(list: readonly string[], element: string): string[] {
  return (list.includes(element) ? list.filter((e) => e !== element) : [...list, element])
    .sort();
}

/** Species → its legend entry, in the order the sites are declared. */
export function legend(geometry: Geometry): Array<{ species: string; color: string;
                                                    sites: Site[] }> {
  const out: Array<{ species: string; color: string; sites: Site[] }> = [];
  const seen = new Map<string, number>();
  for (const site of geometry.sites) {
    const at = seen.get(site.species);
    if (at === undefined) {
      seen.set(site.species, out.length);
      out.push({ species: site.species, color: site.color, sites: [site] });
    } else {
      out[at].sites.push(site);
    }
  }
  return out;
}

/** Half a bond is 0.08 Å thick.
 *
 * These are *covalent* radii, which is what makes the number smaller than it
 * looks beside VESTA's: at `ball_fraction` even hydrogen (r = 0.31 Å) keeps a
 * ball wider than its own stick, so no species is drawn as a lump on a rod.
 */
export const STICK_RADIUS = 0.08;

/** How much of the smallest drawn semi-axis a stick may take in ellipsoid mode. */
export const STICK_OF_SEMI_AXIS = 0.5;

/** Below this a stick is a hairline at any zoom, so it stops shrinking. */
export const STICK_FLOOR = 0.02;

/**
 * How thick a half-bond is drawn, in Å, **for the mode it is drawn in**.
 *
 * In ball mode this is `STICK_RADIUS`, pinned by test below `BALL_FRACTION` on
 * the smallest covalent radius there is, so every ball is wider than its own
 * stick.  In ellipsoid mode an atom's size is `√U·k(p)·e` and has nothing to do
 * with a covalent radius, so the same fixed number made the sticks nearly as
 * thick as the atoms — measured on NAC, the smallest semi-axis at the default
 * 50 % is 0.130 Å against a 0.08 Å stick, and the *shipped* 10 % level put the
 * atom inside the stick at 0.065 Å.
 *
 * So in ellipsoid mode the radius is half the smallest semi-axis actually
 * drawn, which makes the burial a proof rather than a hope: a rim of radius
 * `r ≤ ½·min semi-axis` lies inside the ellipsoid's inscribed sphere, hence
 * inside the ellipsoid in every direction. It never *grows* past
 * `STICK_RADIUS`, because a fat stick is a fat stick whatever it is buried in.
 *
 * `stick` multiplies the mode's rule, and the floor stays a hairline (WP-1533).
 * At `stick ≤ 1` both promises above hold; a larger one may poke through.
 */
export function stickRadius(geometry: Geometry, mode: Mode, exaggeration = 1,
                            stick = 1): number {
  if (mode !== "ellipsoid") return STICK_RADIUS * stick;
  const semi = geometry.atoms.flatMap((atom) => atom.rms).filter((v) => v > 0);
  if (!semi.length) return STICK_RADIUS * stick;
  const smallest = Math.min(...semi) * geometry.scale * exaggeration;
  return Math.max(STICK_FLOOR,
                  Math.min(STICK_RADIUS * stick, STICK_OF_SEMI_AXIS * stick * smallest));
}

/**
 * A drawn semi-axis below this is drawn at this, in Å.
 *
 * A tensor that is not positive definite arrives with its non-positive axes at
 * **zero** (the server's rule: visibly flat, never a NaN).  The ray-caster
 * solves through `M⁻¹`, which a zero column does not have, so the column is
 * kept at a thousandth of an Å: still a disc at any zoom a person uses.
 */
export const FLAT_AXIS = 1e-3;

/** The cell frame's width, in CSS pixels (WP-1462 D9) — plotly's `line.width`
 *  was 2, and a WebGL line is one *device* pixel, half that at DPR 2. */
export const CELL_WIDTH_PX = 2;

/** One atom as the renderer draws it. */
export interface SceneAtom {
  /** index into `geometry.atoms`, for the hover text */
  index: number;
  pos: number[];
  /** `pos + M·v` over the unit sphere, row-major */
  shape: Mat3;
  inverse: Mat3;
  color: number[];
  /** draw the three principal ellipses: an anisotropic site, in ellipsoid mode */
  rings: boolean;
}

/** One half of a bond: a cylinder from its atom to the midpoint. */
export interface SceneHalf {
  bond: number;
  from: number[];
  to: number[];
  radius: number;
  color: number[];
}

/** A segment drawn at a width in CSS pixels. */
export interface SceneLine {
  a: number[];
  b: number[];
  color: number[];
  width: number;
}

export interface SceneLabel {
  text: string;
  pos: number[];
}

/** A polyhedron's faces are drawn at this opacity in the centre's colour
 *  (WP-1466, P6: VESTA's look). */
export const POLY_ALPHA = 0.55;

/** A filled ring or face with no colour of its own (WP-1548 D5): a neutral
 *  grey, a ring having no centre to take a colour from. */
export const FILL_COLOR = "#8c8c8c";

/**
 * How every solid is lit and inked; `gl3d.ts`'s shaders read it, and the
 * Python renderer's copy (`rietx.viz.figure3d.scene.LOOK`) is held equal to it
 * by the scene corpus (WP-1470).
 *
 * One key light fixed to the camera, in view space (x right, y up, z toward
 * the viewer), so the lit side follows every rotation.  An atom or a stick is
 * `base·(ambient + diffuse·d) + specular·s^shininess`; a polyhedron face is
 * `base·(ambient + face_diffuse·d)`, lit from the side it shows.  A principal
 * ring is where the smallest unit-frame coordinate is under `ring_width`,
 * inked `ring_lighten` of the way to white on an atom whose luminance is under
 * `ring_dark` and at `ring_darken` of its colour on the rest, or a violet atom
 * hides its rings.  Depth cueing (WP-1548, off unless asked) fades a surface
 * toward the background linearly in depth, from nothing at `fog_start` of the
 * drawn atoms' depth span to `fog_max` at `fog_end` (`fogSpan`).  The keys are
 * Python's, because Python owns the corpus.
 */
export const LOOK = {
  light: [-0.40, 0.55, 0.73],
  ambient: 0.45,
  diffuse: 0.60,
  specular: 0.16,
  shininess: 40,
  face_diffuse: 0.55,
  ring_width: 0.035,
  ring_dark: 0.33,
  ring_lighten: 0.6,
  ring_darken: 0.3,
  luma: [0.2126, 0.7152, 0.0722],
  fog_start: 0.5,
  fog_end: 1.0,
  fog_max: 0.7,
} as const;

/**
 * Where depth cueing starts and ends, as view-space depths about the scene's
 * centre (`rotation·(p − center)`'s z, toward the viewer): `fog_start` and
 * `fog_end` of the way back through the drawn atoms' centres, front to back,
 * in this view, so the ramp turns with the picture (WP-1548 D1).  `null` where
 * the atoms span no depth.  Python's `scene.fog_span` is the twin.
 */
export function fogSpan(scene: Scene, rotation: Mat3): [number, number] | null {
  const [r0, r1, r2] = [rotation[6], rotation[7], rotation[8]];
  const c = scene.center;
  const depths = scene.atoms.map((a) =>
    r0 * (a.pos[0] - c[0]) + r1 * (a.pos[1] - c[1]) + r2 * (a.pos[2] - c[2]));
  if (depths.length === 0) return null;
  const front = Math.max(...depths), back = Math.min(...depths);
  if (!(front > back)) return null;
  const span = front - back;
  return [front - LOOK.fog_start * span, front - LOOK.fog_end * span];
}

/** A polyhedron's edges, in CSS pixels, drawn as the cell frame's quads (D9). */
export const EDGE_WIDTH_PX = 1.25;

/** One polyhedron as the renderer draws it: flat triangles, wound outward. */
export interface SceneFaces {
  /** which list `index` reads: `geometry.polyhedra`, or the fills drawn */
  kind: "polyhedron" | "ring" | "face";
  /** index into that list, for the hover text */
  index: number;
  /** three points a triangle, nine numbers, in Å */
  triangles: number[];
  /** one outward normal a triangle, three numbers */
  normals: number[];
  color: number[];
  /** the vertices' mean, which orders translucent polyhedra back to front */
  centroid: number[];
}

/** Everything the renderer draws, in Å — and nothing it has to derive. */
export interface Scene {
  atoms: SceneAtom[];
  halves: SceneHalf[];
  lines: SceneLine[];
  faces: SceneFaces[];
  labels: SceneLabel[];
  /** the centre of the cell and its atoms, and the radius the view fits */
  center: number[];
  radius: number;
  /** how far from the centre anything drawn reaches, Å: the depth range */
  depth: number;
}

export interface SceneOptions {
  mode: Mode;
  hidden?: ReadonlySet<string>;
  showBoundary?: boolean;
  exaggeration?: number;
  /** a multiple of the mode's stick radius (`stickRadius`), 1 by default */
  stick?: number;
  /** the cell frame's colour, `#rrggbb` */
  cell?: string;
  /** the polyhedra drawn, indices into `geometry.polyhedra` (`shownPolyhedra`) */
  polyhedra?: readonly number[];
  /** filled rings and faces (WP-1548), each drawn only while all its atoms are */
  fills?: readonly Fill[];
}

function toRowMajor(m: number[][]): Mat3 {
  return [m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2],
          m[2][0], m[2][1], m[2][2]];
}

/** The inverse of a row-major 3×3; `null` when it is singular. */
export function invert3(m: Mat3): Mat3 | null {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (!Number.isFinite(det) || Math.abs(det) < 1e-300) return null;
  return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det,
          B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
          C / det, -(a * h - b * g) / det, (a * e - b * d) / det];
}

/** `a·b` for row-major 3×3s. */
export function mul3(a: Mat3, b: Mat3): Mat3 {
  const o = new Array(9);
  for (let r = 0; r < 3; r += 1) {
    for (let c = 0; c < 3; c += 1) {
      o[3 * r + c] = a[3 * r] * b[c] + a[3 * r + 1] * b[3 + c] + a[3 * r + 2] * b[6 + c];
    }
  }
  return o;
}

/** `m·v` for a row-major 3×3. */
export function apply3(m: Mat3, v: number[]): number[] {
  return [m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
          m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
          m[6] * v[0] + m[7] * v[1] + m[8] * v[2]];
}

export function transpose3(m: Mat3): Mat3 {
  return [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]];
}

/** An atom's drawn shape with every column at least `FLAT_AXIS` long. */
function drawable(m: number[][]): Mat3 {
  const out = toRowMajor(m);
  for (let c = 0; c < 3; c += 1) {
    const length = Math.hypot(out[c], out[3 + c], out[6 + c]);
    if (length >= FLAT_AXIS) continue;
    // a zero column has no direction left, so a flat axis takes the one the
    // other two leave free
    const u = [out[(c + 1) % 3], out[3 + (c + 1) % 3], out[6 + (c + 1) % 3]];
    const v = [out[(c + 2) % 3], out[3 + (c + 2) % 3], out[6 + (c + 2) % 3]];
    let n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    let nn = Math.hypot(n[0], n[1], n[2]);
    if (!(nn > 0)) {
      // a neighbour is zero too, so the cross product says nothing: take the
      // Cartesian axis least along the column that is left, made perpendicular
      // to it — a fixed axis could be that column, and M would be singular
      const w = Math.hypot(u[0], u[1], u[2]) > 0 ? u : v;
      const wn = Math.hypot(w[0], w[1], w[2]);
      const k = [0, 1, 2].reduce((best, j) => (Math.abs(w[j]) < Math.abs(w[best]) ? j : best), 0);
      n = [0, 1, 2].map((j) => (j === k ? 1 : 0) - (wn > 0 ? (w[k] * w[j]) / (wn * wn) : 0));
      nn = Math.hypot(n[0], n[1], n[2]);
    }
    n = n.map((x) => x / nn);
    out[c] = FLAT_AXIS * n[0];
    out[3 + c] = FLAT_AXIS * n[1];
    out[6 + c] = FLAT_AXIS * n[2];
  }
  return out;
}

/**
 * Whether a payload atom is drawn while the polyhedra `polyhedra` are, as a
 * test on its index into `geometry.atoms`.
 *
 * An atom in the payload only as a polyhedron's vertex (`vertex_only`) is
 * drawn only while one of its polyhedra is: at the default bond tolerance,
 * NAC's hidden NaF₇ and CaF₈ would leave 12 F with no stick and no face.  An
 * atom outside the cell whose site centres a polyhedron (`outside_centre`) is
 * drawn only while no drawn polyhedron is centred on its site, and so is a
 * flagged bond to one, both halves (`.bond`): VESTA adds no centre outside the
 * boundary (its manual, § 8.2.1), and rutile drew 2 Ti with no octahedron
 * (WP-1529).  The one statement of both rules: `buildScene` draws by it, its
 * zoom fit reads it over the default polyhedra, and `caption` counts by it.  A
 * copy of it is how the caption came to count atoms that were not drawn
 * (WP-1468).
 */
export function drawnWith(geometry: Geometry, polyhedra: readonly number[]): Drawn {
  const corners = new Set(polyhedra.flatMap((i) => geometry.polyhedra[i].vertices));
  // a site is the asymmetric-unit atom it was built from, as the Python twin
  // keys it, since `recolour` there points some images of a site at a copy
  const unit = (atom: number) => geometry.sites[geometry.atoms[atom].site].index;
  const centred = new Set(polyhedra.map((i) => unit(geometry.polyhedra[i].center)));
  const atom = (index: number) => {
    const a = geometry.atoms[index];
    return (!a.vertex_only || corners.has(index)) && !(a.outside_centre && centred.has(unit(index)));
  };
  const bond = (index: number) => {
    const b = geometry.bonds[index];
    return !(b.outside_centre && centred.has(unit(b.j)));
  };
  return Object.assign(atom, { bond });
}

/** `drawnWith`'s test on an index into `atoms`, and on one into `bonds`. */
export interface Drawn {
  (index: number): boolean;
  bond(index: number): boolean;
}

/**
 * The scene for one payload, in the given mode.
 *
 * `hidden` is the set of species the legend has switched off, and **a half
 * belongs to its atom**: switching a species off takes its own halves with it
 * rather than leaving coloured stubs in mid-air.  `showBoundary` hides the
 * images outside the cell and keeps the bonds to them, which then end in
 * mid-air — what the checkbox says it does.
 *
 * Bonds are split at the midpoint and each half is coloured by the atom it
 * leaves — the convention every other viewer uses, and the thing that makes a
 * bond say which two species it joins without a hover.
 *
 * A drawn polyhedron (WP-1466) brings its faces and its edges, the edges as
 * lines in a darker ink of the centre's colour, and takes away its centre's
 * sticks to its own vertices.  An atom in the payload only as a polyhedron's
 * vertex is drawn only while one of its polyhedra is, and a centre of its site
 * outside the cell only while none is, with its sticks (`drawnWith`).  The gap
 * shell and the bond rule can disagree (NAC's Na: 4 sticks, 7 vertices), and
 * drawing both would show the contradiction rather than the shell.
 */
export function buildScene(geometry: Geometry, options: SceneOptions): Scene {
  const { mode, hidden = new Set<string>(), showBoundary = true,
          exaggeration = 1, stick = 1, cell = "#1f5fa8", polyhedra = [],
          fills = [] } = options;
  // a drawn polyhedron replaces its centre's sticks to its own vertices (P6)
  const replaced = new Set(polyhedra.flatMap((i) => geometry.polyhedra[i].bonds));
  // and brings the atoms only a polyhedron needs, which come with no other
  const drawn = drawnWith(geometry, polyhedra);
  const atoms: SceneAtom[] = [];
  geometry.atoms.forEach((atom, index) => {
    const site = geometry.sites[atom.site];
    if (hidden.has(site.species)) return;
    if (atom.boundary && !showBoundary) return;
    if (!drawn(index)) return;
    const shape = drawable(atomTransform(geometry, atom, mode, exaggeration));
    atoms.push({
      index,
      pos: atom.pos,
      shape,
      inverse: invert3(shape)!,
      color: rgb(atom.boundary ? dim(site.color) : site.color),
      // an isotropic site's T is √U·I, whose axes are x, y and z: rings there
      // would claim an orientation the site does not have
      rings: mode === "ellipsoid" && site.aniso,
    });
  });
  const radius = stickRadius(geometry, mode, exaggeration, stick);
  const halves: SceneHalf[] = [];
  geometry.bonds.forEach((bond, index) => {
    if (replaced.has(index) || !drawn.bond(index)) return;
    const mid = [0, 1, 2].map((k) => (bond.a[k] + bond.b[k]) / 2);
    for (const [from, at] of [[bond.a, bond.i], [bond.b, bond.j]] as const) {
      const site = geometry.sites[geometry.atoms[at].site];
      if (hidden.has(site.species)) continue;
      halves.push({ bond: index, from, to: mid, radius, color: rgb(site.color) });
    }
  });
  const ink = rgb(cell);
  const lines: SceneLine[] = geometry.edges.map(([a, b]) => ({
    a: geometry.corners[a], b: geometry.corners[b], color: ink, width: CELL_WIDTH_PX,
  }));
  const faceEntry = (kind: SceneFaces["kind"], index: number, at: number[][],
                     triangulation: number[][], color: string): SceneFaces => {
    const triangles: number[] = [], normals: number[] = [];
    for (const face of triangulation) {
      const [a, b, c] = face.map((v) => at[v]);
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
      const length = Math.hypot(n[0], n[1], n[2]) || 1;
      triangles.push(...a, ...b, ...c);
      normals.push(n[0] / length, n[1] / length, n[2] / length);
    }
    const centroid = [0, 1, 2].map((k) => at.reduce((sum, q) => sum + q[k], 0) / at.length);
    return { kind, index, triangles, normals, color: rgb(color), centroid };
  };
  const faces: SceneFaces[] = polyhedra.map((index) => {
    const p = geometry.polyhedra[index];
    const site = geometry.sites[p.site];
    // an image's polyhedron is dimmed with its centre, for the same reason
    const color = geometry.atoms[p.center].boundary ? dim(site.color) : site.color;
    const at = p.vertices.map((v) => geometry.atoms[v].pos);
    for (const [i, j] of p.edges) {
      lines.push({ a: at[i], b: at[j], color: rgb(dim(color, 0.5)), width: EDGE_WIDTH_PX });
    }
    return faceEntry("polyhedron", index, at, p.faces, color);
  });
  // a fill comes after the polyhedra, and only while every atom of it is drawn
  const shown = new Set(atoms.map((a) => a.index));
  fills.forEach((fill, index) => {
    if (!fill.vertices.every((v) => shown.has(v))) return;
    const at = fill.vertices.map((v) => geometry.atoms[v].pos);
    faces.push(faceEntry(fill.kind, index, at, fill.faces, fill.color || FILL_COLOR));
  });
  // the fit reads positions and ball sizes only, so neither a mode nor a
  // legend click moves the zoom.  The fit takes the atoms the default picture
  // can draw: a hidden polyhedron's own atoms would halve LaB6's picture at a
  // bond tolerance of 1.00
  const byDefault = drawnWith(geometry, geometry.polyhedra
    .flatMap((p, i) => (p.drawn_by_default ? [i] : [])));
  const points = [...geometry.corners, ...geometry.atoms
    .filter((_a, k) => byDefault(k)).map((a) => a.pos)];
  const lo = [0, 1, 2].map((k) => Math.min(...points.map((p) => p[k])));
  const hi = [0, 1, 2].map((k) => Math.max(...points.map((p) => p[k])));
  const center = [0, 1, 2].map((k) => (lo[k] + hi[k]) / 2);
  // the half-diagonal of the box holds the scene in *every* orientation, so a
  // rotation never pushes an atom off the canvas
  const half = Math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2;
  const ball = geometry.ball_fraction * Math.max(0, ...geometry.sites.map((s) => s.radius));
  const reach = Math.max(ball, ...atoms.map((a) => [0, 1, 2].reduce((m, c) =>
    Math.max(m, Math.hypot(a.shape[c], a.shape[3 + c], a.shape[6 + c])), 0)));
  // the depth range holds every atom the payload can draw, the zoom's
  // excluded ones too: a hidden polyhedron switched on would otherwise put
  // its outer faces and edges past the clip planes
  const far = Math.max(half, ...geometry.atoms.map((a) =>
    Math.hypot(a.pos[0] - center[0], a.pos[1] - center[1], a.pos[2] - center[2])));
  return { atoms, halves, lines, faces, labels: axisLabels(geometry), center,
           radius: Math.max(half + ball, 1), depth: far + reach + 1 };
}

/**
 * "a", "b", "c" just beyond the far end of the three cell edges leaving the
 * origin.
 *
 * This is the scene's frame of reference, in place of a Cartesian box: nothing
 * in the picture happens in x, y or z.  `lattice`'s rows *are* those three
 * edges (corner `1 << k` is `lattice[k]`).
 *
 * The clearance is **in Å and set by the largest ball**, not a percentage of the
 * cell edge.  A fraction is the wrong shape for the problem: a corner site is
 * drawn at all eight corners, so the letter has to clear a *ball*, and 8 % of
 * LaB6's 4.16 Å edge is 0.33 Å against a lanthanum drawn at 0.83 — every letter
 * was inside an atom, which is what a browser showed and jsdom cannot.
 */
export function axisLabels(geometry: Geometry): SceneLabel[] {
  const largest = Math.max(0, ...geometry.sites.map((site) => site.radius));
  const clear = 0.35 + geometry.ball_fraction * largest;
  const origin = geometry.corners[0] ?? [0, 0, 0];
  return ["a", "b", "c"].map((text, k) => {
    const v = geometry.lattice[k];
    const length = Math.hypot(v[0], v[1], v[2]) || 1;
    return { text, pos: v.map((c, i) => origin[i] + c * (1 + clear / length)) };
  });
}

// ----------------------------------------------------------------------
// the view
// ----------------------------------------------------------------------

/**
 * Where the scene is seen from: a rotation, a zoom and a pan.
 *
 * `rotation`'s rows are the screen's x (right), y (up) and z (toward the
 * viewer) in the scene's Å, so a point's view coordinates are
 * `rotation·(p − center)`.  The projection is **parallel**: perspective
 * converges a cubic cell's far edges, and a picture of a cell is for seeing its
 * shape (every crystallographic figure is a parallel projection).
 * `pan` is in Å along the screen's x and y; `zoom` multiplies the fit.
 */
export interface View {
  rotation: Mat3;
  zoom: number;
  pan: number[];
}

/** The rotation that looks *from* `eye` toward the centre with `up` up. */
export function lookFrom(eye: number[], up: number[]): Mat3 {
  const unit = (v: number[]) => {
    const n = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / n, v[1] / n, v[2] / n];
  };
  const z = unit(eye);
  const along = up[0] * z[0] + up[1] * z[1] + up[2] * z[2];
  const y = unit([up[0] - along * z[0], up[1] - along * z[1], up[2] - along * z[2]]);
  const x = [y[1] * z[2] - y[2] * z[1], y[2] * z[0] - y[0] * z[2], y[0] * z[1] - y[1] * z[0]];
  return [...x, ...y, ...z];
}

/**
 * The opening view — down the body diagonal, so no axis is edge-on, with the
 * Cartesian z (which is c for every orthogonal cell) up.  The eye plotly's
 * viewer opened at, kept so the first picture does not move.
 */
export function openingView(): View {
  return { rotation: lookFrom([1.35, 1.35, 0.95], [0, 0, 1]), zoom: 1, pan: [0, 0] };
}

/**
 * The view looking straight down one lattice vector.
 *
 * The lattice vector points at the viewer and **c** is up, unless the view is
 * down c, and then **b** (WP-1470 D12): down **a** puts **b** right, down
 * **b** puts **a** left, down **c** puts **a** right, since `right = up ×
 * toward` on a right-handed a, b, c.  That is the convention VESTA's standard
 * orientation sets and megane's VESTA-derived axis buttons keep, and
 * `rietx.viz.figure3d.scene.up_axis` states it for the Python renderer.
 * `up` is Gram-Schmidted against the view direction because in a triclinic
 * cell no two lattice vectors are perpendicular.
 *
 * The zoom comes from the view passed in, so choosing a projection keeps the
 * zoom the user had; the pan goes, because a pan is relative to a direction.
 */
export function axisView(geometry: Geometry, axis: number, view: View = openingView()): View {
  return {
    rotation: lookFrom(geometry.lattice[axis], geometry.lattice[axis === 2 ? 1 : 2]),
    zoom: view.zoom,
    pan: [0, 0],
  };
}

/**
 * The view after a drag of `dx`, `dy` CSS pixels: a trackball.
 *
 * The rotation is about the screen axis perpendicular to the drag, applied in
 * the screen's frame, so the front of the scene follows the pointer whatever
 * the current orientation — the free rotation plotly's `orbit` mode gave, with
 * no up vector to pin (turntable would pin +z, and c ∥ z for every orthogonal
 * cell, so "down c" would be a degenerate view).
 */
export function rotateBy(view: View, dx: number, dy: number, radiansPerPx = 0.008): View {
  const angle = Math.hypot(dx, dy) * radiansPerPx;
  if (!(angle > 0)) return view;
  const [x, y] = [dy / Math.hypot(dx, dy), dx / Math.hypot(dx, dy)];
  const c = Math.cos(angle), s = Math.sin(angle), t = 1 - c;
  // Rodrigues about (x, y, 0)
  const turn: Mat3 = [t * x * x + c, t * x * y, s * y,
                      t * x * y, t * y * y + c, -s * x,
                      -s * y, s * x, c];
  return { ...view, rotation: orthonormal(mul3(turn, view.rotation)) };
}

/** Re-orthonormalise a rotation, so a long drag cannot shear the picture. */
function orthonormal(m: Mat3): Mat3 {
  const unit = (v: number[]) => {
    const n = Math.hypot(v[0], v[1], v[2]) || 1;
    return v.map((c) => c / n);
  };
  const x = unit(m.slice(0, 3));
  let y = m.slice(3, 6);
  const along = x[0] * y[0] + x[1] * y[1] + x[2] * y[2];
  y = unit([y[0] - along * x[0], y[1] - along * x[1], y[2] - along * x[2]]);
  const z = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]];
  return [...x, ...y, ...z];
}

/** Pixels per Å for a canvas of `width` × `height` CSS pixels. */
export function pixelsPerAngstrom(scene: Scene, view: View, width: number,
                                  height: number): number {
  return view.zoom * Math.min(width, height) / (2 * scene.radius);
}

/** A scene point in view coordinates, Å: x right, y up, z toward the viewer. */
export function toView(scene: Scene, view: View, p: number[]): number[] {
  const v = apply3(view.rotation, [p[0] - scene.center[0], p[1] - scene.center[1],
                                   p[2] - scene.center[2]]);
  return [v[0] - view.pan[0], v[1] - view.pan[1], v[2]];
}

/** A scene point on the canvas, in CSS pixels from its top-left corner. */
export function project(scene: Scene, view: View, width: number, height: number,
                        p: number[]): number[] {
  const s = pixelsPerAngstrom(scene, view, width, height);
  const v = toView(scene, view, p);
  return [width / 2 + v[0] * s, height / 2 - v[1] * s, v[2]];
}

/** A canvas point, CSS pixels, back to view coordinates in Å (x, y only). */
function unproject(scene: Scene, view: View, width: number, height: number,
                   px: number, py: number): number[] {
  const s = pixelsPerAngstrom(scene, view, width, height);
  return [(px - width / 2) / s, (height / 2 - py) / s];
}

/**
 * The atom under a canvas point, or `null`: the nearest to the viewer of those
 * whose ellipsoid the ray meets.
 *
 * The ray is `(x, y, z)` with `z` free, which in an atom's unit-sphere frame is
 * `u = q + t·e` — the shader's equation, solved once per atom here.
 */
export function pickAtom(scene: Scene, view: View, width: number, height: number,
                         px: number, py: number): { atom: number; z: number } | null {
  const [x, y] = unproject(scene, view, width, height, px, py);
  const back = transpose3(view.rotation);
  let best: { atom: number; z: number } | null = null;
  for (const [i, atom] of scene.atoms.entries()) {
    const c = toView(scene, view, atom.pos);
    const minv = mul3(atom.inverse, back);
    const q = apply3(minv, [x - c[0], y - c[1], 0]);
    const e = [minv[2], minv[5], minv[8]];
    const a = e[0] * e[0] + e[1] * e[1] + e[2] * e[2];
    const b = q[0] * e[0] + q[1] * e[1] + q[2] * e[2];
    const disc = b * b - a * (q[0] * q[0] + q[1] * q[1] + q[2] * q[2] - 1);
    if (disc < 0 || a <= 0) continue;
    const z = c[2] + (-b + Math.sqrt(disc)) / a;
    if (!best || z > best.z) best = { atom: i, z };
  }
  return best;
}

/** The bond half under a canvas point, or `null` — the shader's finite
 *  cylinder, solved for one ray: the ray's origin and direction with their
 *  parts along the axis removed, against a circle of the stick's radius. */
export function pickHalf(scene: Scene, view: View, width: number, height: number,
                         px: number, py: number): { half: number; z: number } | null {
  const [x, y] = unproject(scene, view, width, height, px, py);
  let best: { half: number; z: number } | null = null;
  for (const [i, half] of scene.halves.entries()) {
    const A = toView(scene, view, half.from), B = toView(scene, view, half.to);
    const len = Math.hypot(B[0] - A[0], B[1] - A[1], B[2] - A[2]);
    if (len < 1e-9) continue;
    const w = [(B[0] - A[0]) / len, (B[1] - A[1]) / len, (B[2] - A[2]) / len];
    const o = [x - A[0], y - A[1], -A[2]];
    const ow = o[0] * w[0] + o[1] * w[1] + o[2] * w[2];
    const q = [o[0] - ow * w[0], o[1] - ow * w[1], o[2] - ow * w[2]];
    const e = [-w[2] * w[0], -w[2] * w[1], 1 - w[2] * w[2]];
    const a = e[0] * e[0] + e[1] * e[1] + e[2] * e[2];
    if (a < 1e-9) continue;                     // looking straight down the bond
    const b = q[0] * e[0] + q[1] * e[1] + q[2] * e[2];
    const disc = b * b - a * (q[0] * q[0] + q[1] * q[1] + q[2] * q[2] - half.radius ** 2);
    if (disc < 0) continue;
    const z = (-b + Math.sqrt(disc)) / a;
    const along = ow + z * w[2];
    if (along < 0 || along > len) continue;
    if (!best || z > best.z) best = { half: i, z };
  }
  return best;
}

/** The polyhedron whose face is under a canvas point, or `null`: the ray
 *  `(x, y, z)` with `z` free meets a triangle where the point lies inside the
 *  triangle's projection, at the depth its barycentric weights give. */
export function pickFace(scene: Scene, view: View, width: number, height: number,
                         px: number, py: number): { faces: number; z: number } | null {
  const [x, y] = unproject(scene, view, width, height, px, py);
  let best: { faces: number; z: number } | null = null;
  for (const [i, polyhedron] of scene.faces.entries()) {
    const t = polyhedron.triangles;
    for (let k = 0; k < t.length; k += 9) {
      const [a, b, c] = [0, 3, 6].map((o) => toView(scene, view, t.slice(k + o, k + o + 3)));
      const det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]);
      if (Math.abs(det) < 1e-12) continue;           // seen edge-on
      const l1 = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det;
      const l2 = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det;
      const l3 = 1 - l1 - l2;
      if (l1 < 0 || l2 < 0 || l3 < 0) continue;
      const z = l1 * a[2] + l2 * b[2] + l3 * c[2];
      if (!best || z > best.z) best = { faces: i, z };
    }
  }
  return best;
}

/** The sentence under the plot: what is drawn, at what thresholds. */
export function caption(geometry: Geometry, mode: Mode, exaggeration = 1,
                        shown: readonly number[] = []): string {
  // counted as `buildScene` draws them
  const drawn = drawnWith(geometry, shown);
  const counted = geometry.atoms.filter((_a, k) => drawn(k));
  const real = counted.filter((a) => !a.boundary).length;
  const ghosts = counted.length - real;
  const parts = [
    `${real} atom${real === 1 ? "" : "s"} in the cell`
      + (ghosts ? ` + ${ghosts} image${ghosts === 1 ? "" : "s"} outside it` : ""),
    `${geometry.bonds.length} bond segment${geometry.bonds.length === 1 ? "" : "s"}`
      + ` at ${geometry.bond_tolerance.toFixed(2)}×(rᵢ+rⱼ)`,
  ];
  if (!geometry.bond_metals) parts.push("metal–metal and metal–cation contacts not bonded");
  if (mode === "ellipsoid") {
    // The probability and the exaggeration are stated **separately**, always.
    // A probability cannot exceed 1 — k(p) = √χ²₃(p) diverges as p → 1, and
    // `probability_scale(1.0)` raises — so "bigger so I can see it" is not a
    // higher probability, and a viewer that drew 1.5·k(0.5) under a "50 %"
    // label would be claiming a surface it is not drawing.  An ORTEP figure
    // quotes a probability because the surface *means* something.
    let text = `ellipsoids at ${(geometry.probability * 100).toFixed(0)} %`
      + ` (k = ${geometry.scale.toFixed(3)})`;
    if (exaggeration !== 1) {
      text += ` × ${exaggeration.toFixed(2)} exaggeration — a drawing scale,`
        + " not a probability: no surface encloses more at this size";
    }
    parts.push(text);
  } else {
    parts.push(`balls at ${geometry.ball_fraction.toFixed(2)}× the covalent radius`);
  }
  parts.push(`sticks ${stickRadius(geometry, mode, exaggeration).toFixed(3)} Å`);
  if (geometry.centres != null || geometry.ligands != null) {
    const named = (list?: string[]) => (list?.length ? list.join(", ") : "none");
    parts.push(`polyhedra round ${named(geometry.centre_elements)} with`
      + ` ${named(geometry.ligand_elements)} at the corners, as chosen`);
  }
  const minor = geometry.minor_sites?.length ?? 0;
  if (minor) {
    parts.push(geometry.disorder === "major"
      ? `the major alternative alone: ${minor} site${minor === 1 ? "" : "s"} of the minor not drawn`
      : "every alternative drawn, with no stick between two of them");
  }
  if (geometry.polyhedra.length) {
    const formula = (i: number) => polyhedronFormula(geometry, geometry.polyhedra[i]);
    const all = [...new Set(geometry.polyhedra.map((_p, i) => formula(i)))];
    const drawn = new Map<string, number>();
    for (const i of shown) drawn.set(formula(i), (drawn.get(formula(i)) ?? 0) + 1);
    const off = all.filter((f) => !drawn.has(f));
    parts.push(shown.length
      ? "polyhedra " + [...drawn].map(([f, n]) => `${f} ×${n}`).join(", ")
        + (off.length ? `; ${off.join(", ")} off` : "")
      : `polyhedra off (${all.join(", ")})`);
  }
  return parts.join(" · ");
}
