/**
 * The structure viewer's arithmetic (WP-1015, WP-1462).
 *
 * There is deliberately no crystallography to test here — the orbit, the
 * metric, the eigen-decomposition and the bond rule are all in
 * `src/rietx/gui/structure3d.py` and asserted in `tests/test_structure3d.py`.
 * What *is* here is the part that can silently draw the right numbers wrongly:
 * the matrix convention (the payload's 3×3 has the principal axes as
 * **columns**, so transposing it would rotate every ellipsoid to a plausible
 * but wrong orientation), the view's handedness (a mirrored cell looks
 * right), and the pick, which must solve the same quadric the shader draws.
 */
import { describe, expect, it } from "vitest";

import { faceData, instanceData } from "./gl3d";
import {
  CELL_WIDTH_PX,
  EDGE_WIDTH_PX,
  FLAT_AXIS,
  STICK_FLOOR,
  STICK_RADIUS,
  apply3,
  atomLabel,
  atomTransform,
  axisLabels,
  axisView,
  bondLabel,
  buildScene,
  caption,
  dim,
  invert3,
  legend,
  mul3,
  openingView,
  pickAtom,
  pickFace,
  pickHalf,
  polyhedraLegend,
  polyhedronFormula,
  polyhedronLabel,
  project,
  rgb,
  rotateBy,
  shownPolyhedra,
  stickRadius,
  transform,
  type Geometry,
  type Mat3,
  type Polyhedron,
  type Site,
} from "./structure3d";

function site(extra: Partial<Site> = {}): Site {
  return {
    index: 0, path: "phases.0.atoms.0", label: "La", species: "La",
    element: "La", color: "#aabbcc", radius: 2.0, metal: true, occ: 1,
    biso: 0.5, u_iso: 0.006, aniso: false, multiplicity: 1, special: true,
    npd: false, ...extra,
  };
}

/** Two sites, three drawn atoms, one bond — small enough to count by hand. */
function geometry(extra: Partial<Geometry> = {}): Geometry {
  return {
    phase: 0, phases: ["cubic"], name: "cubic", space_group: "P m -3 m",
    cell: [4, 4, 4, 90, 90, 90], volume: 64,
    lattice: [[4, 0, 0], [0, 4, 0], [0, 0, 4]],
    corners: [[0, 0, 0], [4, 0, 0], [0, 4, 0], [4, 4, 0],
              [0, 0, 4], [4, 0, 4], [0, 4, 4], [4, 4, 4]],
    edges: [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3],
            [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]],
    sites: [site(), site({ index: 1, path: "phases.0.atoms.1", label: "B",
                           species: "B", element: "B", color: "#e0a080",
                           radius: 0.84, metal: false, multiplicity: 2,
                           aniso: true })],
    atoms: [
      { site: 0, frac: [0, 0, 0], pos: [0, 0, 0], boundary: false,
        ellipsoid: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]],
        rms: [0.1, 0.1, 0.1], npd: false },
      { site: 0, frac: [1, 0, 0], pos: [4, 0, 0], boundary: true,
        ellipsoid: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]],
        rms: [0.1, 0.1, 0.1], npd: false },
      { site: 1, frac: [0.5, 0.5, 0.2], pos: [2, 2, 0.8], boundary: false,
        // deliberately not symmetric: a transpose would go unnoticed otherwise
        ellipsoid: [[0.2, 0, 0], [0, 0.1, 0], [0.05, 0, 0.1]],
        rms: [0.1, 0.1, 0.2], npd: false },
    ],
    bonds: [{ i: 0, j: 2, a: [0, 0, 0], b: [2, 2, 0.8], d: 3.0 }],
    polyhedra: [],
    probability: 0.5, probability_levels: { "0.5": 1.5382, "0.9": 2.5003 },
    scale: 1.5382, ball_fraction: 0.40, bond_tolerance: 1.15,
    bond_metals: false, note: "", ...extra,
  };
}

const I3: Mat3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

function expectMatrix(actual: Mat3, expected: Mat3, digits = 12) {
  actual.forEach((v, k) => expect(v).toBeCloseTo(expected[k], digits));
}

function dot(a: number[], b: number[]): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

describe("the transform", () => {
  it("reads the matrix by rows, so the payload's columns stay the axes", () => {
    // the payload's convention: column k is the k-th principal axis, so the
    // matrix below must send x̂ to (1, 0, 2) — a transposed reading sends it to
    // (1, 0, 0) and every anisotropic ellipsoid is silently mis-oriented
    const m = [[1, 0, 0], [0, 1, 0], [2, 0, 1]];
    expect(transform(m, [1, 0, 0])).toEqual([1, 0, 2]);
    expect(transform(m, [0, 0, 1])).toEqual([0, 0, 1]);
  });

  it("scales the ellipsoid by k(p) and the ball by the covalent radius", () => {
    const geo = geometry();
    const ellipsoid = atomTransform(geo, geo.atoms[2], "ellipsoid");
    expect(ellipsoid[2][0]).toBeCloseTo(0.05 * 1.5382, 12);
    const ball = atomTransform(geo, geo.atoms[2], "ball");
    expect(ball).toEqual([[0.40 * 0.84, 0, 0], [0, 0.40 * 0.84, 0],
                          [0, 0, 0.40 * 0.84]]);
  });

  it("draws an anisotropic site as a ball in ball mode", () => {
    // the two modes answer different questions; a ball-and-stick that quietly
    // showed thermal motion would make the toggle mean nothing
    const geo = geometry();
    const ball = atomTransform(geo, geo.atoms[2], "ball");
    expect(ball[0][0]).toBe(ball[1][1]);
    expect(ball[2][0]).toBe(0);
  });
});

describe("the scene", () => {
  it("draws each atom through its own matrix, kept row-major with its inverse", () => {
    const geo = geometry();
    const scene = buildScene(geo, { mode: "ellipsoid" });
    expect(scene.atoms.map((a) => a.index)).toEqual([0, 1, 2]);
    const b = scene.atoms[2];
    // the payload's (row 2, column 0) is 0.05: row-major keeps it at [6]
    expect(b.shape[6]).toBeCloseTo(0.05 * 1.5382, 12);
    expect(b.shape[2]).toBe(0);
    expectMatrix(mul3(b.shape, b.inverse), I3);
  });

  it("dims an image outside the cell rather than drawing it identically", () => {
    expect(dim("#ffffff", 0.5)).toBe("#808080");
    expect(dim("#48d860")).toBe("#2d863c");   // 0.62 of each channel, rounded
    expect(dim("not a colour")).toBe("not a colour");
    const scene = buildScene(geometry(), { mode: "ball" });
    expect(scene.atoms[1].color).toEqual(rgb(dim("#aabbcc")));
    expect(scene.atoms[0].color).toEqual(rgb("#aabbcc"));
  });

  it("rings only an anisotropic site, and only in ellipsoid mode", () => {
    // an isotropic site's T is √U·I, whose axes are x, y and z: rings there
    // would claim an orientation the site does not have
    expect(buildScene(geometry(), { mode: "ellipsoid" }).atoms.map((a) => a.rings))
      .toEqual([false, false, true]);
    expect(buildScene(geometry(), { mode: "ball" }).atoms.some((a) => a.rings))
      .toBe(false);
  });

  it("draws a flat axis thin rather than losing the atom", () => {
    // the server draws a non-positive axis at zero; the ray-caster needs M⁻¹
    const geo = geometry();
    geo.atoms[2].ellipsoid = [[0.2, 0, 0], [0, 0.1, 0], [0, 0, 0]];
    const shape = buildScene(geo, { mode: "ellipsoid" }).atoms[2];
    expect(Math.hypot(shape.shape[2], shape.shape[5], shape.shape[8])).toBeCloseTo(FLAT_AXIS, 12);
    expect(shape.inverse.every(Number.isFinite)).toBe(true);
    expect(invert3([1, 0, 0, 0, 1, 0, 0, 0, 0])).toBeNull();
  });

  it("keeps two flat axes perpendicular to the one that is left", () => {
    // eigh sorts ascending, so two non-positive axes are columns 0 and 1; with
    // the survivor along x a fixed fallback of x̂ made M singular
    const geo = geometry();
    geo.atoms[2].ellipsoid = [[0, 0, 0.2], [0, 0, 0], [0, 0, 0]];
    const atom = buildScene(geo, { mode: "ellipsoid" }).atoms[2];
    expect(atom.inverse).not.toBeNull();
    expectMatrix(mul3(atom.shape, atom.inverse), I3, 9);
  });

  it("hides the species the legend switched off, and the images when asked", () => {
    const geo = geometry();
    const noLa = buildScene(geo, { mode: "ball", hidden: new Set(["La"]) });
    expect(noLa.atoms.map((a) => a.index)).toEqual([2]);
    // a half belongs to its atom: hiding La and leaving its stub would be a
    // coloured spike ending in mid-air
    expect(noLa.halves.map((h) => h.color)).toEqual([rgb("#e0a080")]);
    // the images go and their bonds stay, ending in mid-air — which is what
    // the checkbox says it does
    const inner = buildScene(geo, { mode: "ball", showBoundary: false });
    expect(inner.atoms.map((a) => a.index)).toEqual([0, 2]);
    expect(inner.halves.length).toBe(2);
  });

  it("splits a bond at its midpoint and colours each half by its own atom", () => {
    const scene = buildScene(geometry(), { mode: "ball" });
    expect(scene.halves.map((h) => h.color)).toEqual([rgb("#aabbcc"), rgb("#e0a080")]);
    expect(scene.halves[0].from).toEqual([0, 0, 0]);
    expect(scene.halves[0].to).toEqual([1, 1, 0.4]);
    expect(scene.halves[1].from).toEqual([2, 2, 0.8]);
    expect(scene.halves[1].to).toEqual([1, 1, 0.4]);
    expect(bondLabel(geometry(), geometry().bonds[0])).toBe("La–B  3.000 Å");
  });

  it("sizes the stick for the mode it is drawn in", () => {
    const geo = geometry();
    // ball mode: the fixed radius, pinned below BALL_FRACTION on the smallest
    // covalent radius there is, so no species is a lump on a rod
    expect(stickRadius(geo, "ball")).toBe(STICK_RADIUS);
    // ellipsoid mode: half the smallest drawn semi-axis, so the open end of a
    // stick lies inside the ellipsoid's inscribed sphere in every direction
    const thin = stickRadius(geo, "ellipsoid");
    expect(thin).toBeCloseTo(0.5 * 0.1 * 1.5382, 12);
    expect(thin).toBeLessThan(STICK_RADIUS);
    expect(stickRadius(geo, "ellipsoid", 8)).toBe(STICK_RADIUS);
    expect(stickRadius(geo, "ellipsoid", 0.001)).toBe(STICK_FLOOR);
    expect(buildScene(geo, { mode: "ellipsoid" }).halves[0].radius).toBe(thin);
  });

  it("frames the cell with twelve edges at a width in CSS pixels", () => {
    // a WebGL line is one *device* pixel, half a CSS pixel at DPR 2 and a
    // hairline in a 3000 px export, so the frame is quads with a width (D9)
    const scene = buildScene(geometry(), { mode: "ball", cell: "#1f5fa8" });
    expect(scene.lines.length).toBe(12);
    for (const line of scene.lines) {
      expect(line.width).toBe(CELL_WIDTH_PX);
      expect(line.color).toEqual(rgb("#1f5fa8"));
    }
  });

  it("labels the cell's own axes, clear of the corner atoms", () => {
    // The frame of reference is a, b, c — nothing here happens in x, y, z.  The
    // clearance is in Å and set by the largest ball, because a corner site is
    // drawn at all eight corners: a percentage of the edge put every letter
    // inside an atom on the first structure it was tried on.
    const labels = axisLabels(geometry());
    expect(labels.map((l) => l.text)).toEqual(["a", "b", "c"]);
    const clear = 0.35 + 0.4 * 2.0;               // the fixture's largest radius
    expect(labels[0].pos).toEqual([4 + clear, 0, 0]);
    expect(labels[1].pos).toEqual([0, 4 + clear, 0]);
    expect(labels[2].pos).toEqual([0, 0, 4 + clear]);
    const small = axisLabels(geometry({ lattice: [[1, 0, 0], [0, 1, 0], [0, 0, 1]] }));
    expect(small[0].pos[0] - 1).toBeGreaterThan(0.4 * 2.0);
  });

  it("fits a view that neither a mode nor a legend click moves", () => {
    const geo = geometry();
    const ball = buildScene(geo, { mode: "ball" });
    const big = buildScene(geo, { mode: "ellipsoid", exaggeration: 4,
                                  hidden: new Set(["B"]) });
    expect(big.radius).toBe(ball.radius);
    expect(big.center).toEqual(ball.center);
    // …while the depth range holds whatever is drawn
    expect(ball.depth).toBeGreaterThan(ball.radius - 1);
  });

  it("packs each atom as 25 floats with the matrices as columns", () => {
    const scene = buildScene(geometry(), { mode: "ellipsoid" });
    const { atoms, halves, lines } = instanceData(scene);
    expect(atoms.length).toBe(3 * 25);
    expect(halves.length).toBe(2 * 10);
    expect(lines.length).toBe(12 * 10);
    // GLSL's mat3(c0, c1, c2) takes columns: the B atom's column 0 is the
    // payload's first principal axis, (0.2, 0, 0.05)·k
    const b = atoms.subarray(50, 75);
    expect(b[3]).toBeCloseTo(0.2 * 1.5382, 5);
    expect(b[5]).toBeCloseTo(0.05 * 1.5382, 5);
    expect(b[24]).toBe(1);                   // rings on
  });
});

describe("the view", () => {
  it("opens down the body diagonal with c up, as a right-handed rotation", () => {
    const r = openingView().rotation;
    const [x, y, z] = [r.slice(0, 3), r.slice(3, 6), r.slice(6, 9)];
    for (const row of [x, y, z]) expect(Math.hypot(...row)).toBeCloseTo(1, 12);
    expect(dot(x, y)).toBeCloseTo(0, 12);
    // right-handed: x × y = z, or the whole cell is drawn mirrored
    expect(x[1] * y[2] - x[2] * y[1]).toBeCloseTo(z[0], 12);
    expect(z[0]).toBeGreaterThan(0);
    expect(z[1]).toBeGreaterThan(0);
    expect(y[2]).toBeGreaterThan(0);          // Cartesian z up the screen
  });

  it("looks down a lattice vector with the next one but one up", () => {
    // down a puts c up and b right, and so round: the three projections a
    // structure is normally drawn in
    const geo = geometry();
    const down = axisView(geo, 2).rotation;
    expectMatrix(down, [1, 0, 0, 0, 1, 0, 0, 0, 1]);           // a right, b up
    expectMatrix(axisView(geo, 0).rotation, [0, 1, 0, 0, 0, 1, 1, 0, 0]);
    // monoclinic, β = 110°: up is c with its part along a taken out
    const beta = (110 * Math.PI) / 180;
    const mono = geometry({ lattice: [[5, 0, 0], [0, 9, 0],
                                      [7 * Math.cos(beta), 0, 7 * Math.sin(beta)]] });
    const r = axisView(mono, 0).rotation;
    expect(r.slice(6, 9)).toEqual([1, 0, 0]);
    expect(dot(r.slice(3, 6), [1, 0, 0])).toBeCloseTo(0, 12);
    expect(r[5]).toBeGreaterThan(0);          // c's own side of the plane
  });

  it("keeps the zoom the user had and drops the pan", () => {
    const view = { ...openingView(), zoom: 2.5, pan: [1, -2] };
    const down = axisView(geometry(), 1, view);
    expect(down.zoom).toBe(2.5);
    expect(down.pan).toEqual([0, 0]);
  });

  it("turns the front of the scene the way the pointer drags", () => {
    const view = { rotation: I3, zoom: 1, pan: [0, 0] };
    // the point nearest the viewer is +z in view space; a drag to the right
    // moves it right, a drag down moves it down (screen y is down, view y up)
    const right = apply3(rotateBy(view, 20, 0).rotation, [0, 0, 1]);
    expect(right[0]).toBeGreaterThan(0);
    expect(right[1]).toBeCloseTo(0, 12);
    const down = apply3(rotateBy(view, 0, 20).rotation, [0, 0, 1]);
    expect(down[1]).toBeLessThan(0);
    expect(rotateBy(view, 0, 0)).toBe(view);
  });

  it("stays a rotation over a long drag", () => {
    let view = openingView();
    for (let i = 0; i < 2000; i += 1) view = rotateBy(view, 7 * Math.sin(i), 5 * Math.cos(i));
    const r = view.rotation;
    expectMatrix(mul3(r, [r[0], r[3], r[6], r[1], r[4], r[7], r[2], r[5], r[8]]), I3, 9);
  });

  it("puts the scene's centre at the canvas centre, and pans in Å", () => {
    const scene = buildScene(geometry(), { mode: "ball" });
    const view = openingView();
    const [x, y] = project(scene, view, 400, 300, scene.center);
    expect(x).toBeCloseTo(200, 9);
    expect(y).toBeCloseTo(150, 9);
    const panned = project(scene, { ...view, pan: [1, 0] }, 400, 300, scene.center);
    const s = 300 / (2 * scene.radius);
    expect(panned[0]).toBeCloseTo(200 - s, 9);
  });
});

describe("the pick", () => {
  const W = 400, H = 400;

  it("finds the atom under a pixel, the nearest to the viewer first", () => {
    const geo = geometry();
    const scene = buildScene(geo, { mode: "ball" });
    const view = axisView(geo, 2);                 // down c: a right, b up
    const [x, y] = project(scene, view, W, H, [2, 2, 0.8]);
    expect(scene.atoms[pickAtom(scene, view, W, H, x, y)!.atom].index).toBe(2);
    // La at the origin and its image at (4, 0, 0) do not overlap down c, but
    // straight down a they do: the one at x = 4 is nearer the viewer
    const along = axisView(geo, 0);
    const [ax, ay] = project(scene, along, W, H, [0, 0, 0]);
    expect(scene.atoms[pickAtom(scene, along, W, H, ax, ay)!.atom].index).toBe(1);
    expect(pickAtom(scene, view, W, H, 5, 5)).toBeNull();
  });

  it("solves an ellipsoid, not its bounding ball", () => {
    // B's first axis is 0.2·k long along x and its second 0.1·k along y: a
    // pixel 0.15·k off-centre along x hits, the same distance along y misses
    const geo = geometry();
    geo.bonds = [];
    const scene = buildScene(geo, { mode: "ellipsoid" });
    const view = axisView(geo, 2);
    const s = W * view.zoom / (2 * scene.radius);
    const [x, y] = project(scene, view, W, H, [2, 2, 0.8]);
    const k = 0.15 * 1.5382 * s;
    expect(pickAtom(scene, view, W, H, x + k, y)).not.toBeNull();
    expect(pickAtom(scene, view, W, H, x, y - k)).toBeNull();
  });

  it("finds a bond half, and says which bond it is", () => {
    const geo = geometry();
    const scene = buildScene(geo, { mode: "ball" });
    const view = axisView(geo, 2);
    // three quarters of the way along, on B's half
    const [x, y] = project(scene, view, W, H, [1.5, 1.5, 0.6]);
    const hit = pickHalf(scene, view, W, H, x, y)!;
    expect(scene.halves[hit.half].color).toEqual(rgb("#e0a080"));
    expect(scene.halves[hit.half].bond).toBe(0);
    expect(pickHalf(scene, view, W, H, 5, 5)).toBeNull();
  });
});

describe("the legend", () => {
  it("merges the sites that share a species and keeps declaration order", () => {
    const geo = geometry({
      sites: [site({ index: 0, label: "F1", species: "F1-", element: "F",
                     color: "#48d860" }),
              site({ index: 1, label: "Ca1", species: "Ca2+", element: "Ca",
                     color: "#40c060" }),
              site({ index: 2, label: "F2", species: "F1-", element: "F",
                     color: "#48d860" })],
      atoms: [], bonds: [],
    });
    const entries = legend(geo);
    expect(entries.map((e) => e.species)).toEqual(["F1-", "Ca2+"]);
    expect(entries[0].sites.map((s) => s.label)).toEqual(["F1", "F2"]);
  });
});

describe("the caption", () => {
  it("says what is drawn and at which thresholds", () => {
    const text = caption(geometry(), "ellipsoid");
    expect(text).toContain("2 atoms in the cell");
    expect(text).toContain("+ 1 image outside it");
    expect(text).toContain("1 bond segment at 1.15×");
    expect(text).toContain("metal–metal and metal–cation contacts not bonded");
    expect(text).toContain("ellipsoids at 50 %");
    expect(caption(geometry(), "ball")).toContain("0.40× the covalent radius");
  });

  it("marks an image whose tensor is not positive definite", () => {
    const geo = geometry();
    geo.atoms[2].npd = true;
    expect(atomLabel(geo, geo.atoms[2], "ellipsoid"))
      .toContain("not positive definite");
    // …and only in the mode that draws it
    expect(atomLabel(geo, geo.atoms[2], "ball")).not.toContain("positive");
  });
});

/** SiO₄ alone: Si at the origin, four O at 1.6 Å, the four sticks between them
 *  and the tetrahedron, wound outward, the way the server sends it (WP-1466). */
function tetrahedron(extra: Partial<Polyhedron> = {}): Geometry {
  const k = 1.6 / Math.sqrt(3);
  const corners = [[k, k, k], [k, -k, -k], [-k, k, -k], [-k, -k, k]];
  const atom = (s: number, pos: number[]) => ({
    site: s, frac: pos.map((v) => v / 10), pos, boundary: false,
    ellipsoid: [[0.1, 0, 0], [0, 0.1, 0], [0, 0, 0.1]], rms: [0.1, 0.1, 0.1], npd: false,
  });
  return geometry({
    sites: [site({ label: "Si1", species: "Si", element: "Si", color: "#f0c8a0",
                   radius: 1.11, metal: false }),
            site({ index: 1, label: "O1", species: "O", element: "O", color: "#e02020",
                   radius: 0.66, metal: false })],
    atoms: [atom(0, [0, 0, 0]), ...corners.map((c) => atom(1, c))],
    bonds: corners.map((c, j) => ({ i: 0, j: j + 1, a: [0, 0, 0], b: c, d: 1.6 })),
    polyhedra: [{
      center: 0, site: 0, vertices: [1, 2, 3, 4],
      faces: [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]],
      edges: [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]],
      bonds: [0, 1, 2, 3], coordination: 4, mean_distance: 1.6, gap: 2.0,
      drawn_by_default: true, ...extra,
    }],
  });
}

describe("the polyhedra", () => {
  it("are written the way a chemist writes them", () => {
    const geo = tetrahedron();
    expect(polyhedronFormula(geo, geo.polyhedra[0])).toBe("SiO₄");
    expect(polyhedronLabel(geo, geo.polyhedra[0]))
      .toBe("SiO₄ around Si1  ·  4 ligands  ·  mean 1.600 Å  ·  gap ×2.00");
    expect(polyhedraLegend(geo)).toEqual([
      { formula: "SiO₄", color: "#f0c8a0", byDefault: true }]);
  });

  it("show by the server's default, until a switch or a legend says otherwise", () => {
    const shown = tetrahedron();
    const hidden = tetrahedron({ drawn_by_default: false });
    expect(shownPolyhedra(shown, true, new Map())).toEqual([0]);
    expect(shownPolyhedra(hidden, true, new Map())).toEqual([]);
    expect(shownPolyhedra(hidden, true, new Map([["SiO₄", true]]))).toEqual([0]);
    expect(shownPolyhedra(shown, true, new Map([["SiO₄", false]]))).toEqual([]);
    // the one switch, and the atom legend hiding the centre's species
    expect(shownPolyhedra(shown, false, new Map([["SiO₄", true]]))).toEqual([]);
    expect(shownPolyhedra(shown, true, new Map(), new Set(["Si"]))).toEqual([]);
    // an image's polyhedron goes with the images
    shown.atoms[0].boundary = true;
    expect(shownPolyhedra(shown, true, new Map(), new Set(), false)).toEqual([]);
  });

  it("switch per formula, so a species drawn in part can go back to its default", () => {
    // one Si centre drawn as SiO₄ by default, and a second shell of it hidden
    const geo = tetrahedron();
    geo.polyhedra.push({ ...geo.polyhedra[0], vertices: [1, 2, 3], coordination: 3,
                         drawn_by_default: false });
    expect(polyhedraLegend(geo)).toEqual([
      { formula: "SiO₄", color: "#f0c8a0", byDefault: true },
      { formula: "SiO₃", color: "#f0c8a0", byDefault: false }]);
    expect(shownPolyhedra(geo, true, new Map())).toEqual([0]);
    // off and on again is the default, not every shell of the species
    expect(shownPolyhedra(geo, true, new Map([["SiO₄", true]]))).toEqual([0]);
    // and the hidden shell alone is reachable
    expect(shownPolyhedra(geo, true, new Map([["SiO₄", false], ["SiO₃", true]])))
      .toEqual([1]);
  });

  it("bring the atoms only they need, and no hidden one does", () => {
    const geo = tetrahedron();
    // a vertex only a polyhedron needs has no stick of its own
    geo.atoms[4].vertex_only = true;
    geo.bonds = geo.bonds.slice(0, 3);
    geo.polyhedra[0].bonds = [0, 1, 2];
    const atoms = (polyhedra: number[]) =>
      buildScene(geo, { mode: "ball", polyhedra }).atoms.map((a) => a.index);
    expect(atoms([])).toEqual([0, 1, 2, 3]);
    expect(atoms([0])).toEqual([0, 1, 2, 3, 4]);
  });

  it("bring their faces and edges, and take their centre's sticks away", () => {
    const geo = tetrahedron();
    const bare = buildScene(geo, { mode: "ball" });
    expect(bare.faces).toEqual([]);
    expect(bare.halves).toHaveLength(8);
    const scene = buildScene(geo, { mode: "ball", polyhedra: [0] });
    expect(scene.halves).toEqual([]);
    const edges = scene.lines.filter((line) => line.width === EDGE_WIDTH_PX);
    expect(edges).toHaveLength(6);
    // the edge ink is the centre's colour, darker
    expect(edges[0].color).toEqual(rgb(dim("#f0c8a0", 0.5)));
    const [faces] = scene.faces;
    expect(faces.triangles).toHaveLength(4 * 9);
    expect(faces.color).toEqual(rgb("#f0c8a0"));
    expect(faces.centroid.every((v) => Math.abs(v) < 1e-12)).toBe(true);
    // every normal points away from the centre, as the server wound the face
    for (let f = 0; f < 4; f += 1) {
      const n = faces.normals.slice(3 * f, 3 * f + 3);
      const a = faces.triangles.slice(9 * f, 9 * f + 3);
      expect(dot(n, a)).toBeGreaterThan(0);
      expect(Math.hypot(...n)).toBeCloseTo(1, 12);
    }
  });

  it("are one vertex array with a range each, three vertices a triangle", () => {
    const scene = buildScene(tetrahedron(), { mode: "ball", polyhedra: [0] });
    const { vertices, ranges } = faceData(scene);
    expect(vertices).toHaveLength(12 * 9);
    expect(ranges).toEqual([{ first: 0, count: 12, centroid: scene.faces[0].centroid }]);
    // the fifth vertex is the second triangle's: its normal, and the colour
    expect(Array.from(vertices.slice(9 * 4 + 3, 9 * 4 + 9)).map((v) => +v.toFixed(5)))
      .toEqual([...scene.faces[0].normals.slice(3, 6), ...rgb("#f0c8a0")]
        .map((v) => +v.toFixed(5)));
  });

  it("are picked where no atom is, at the face nearer the viewer", () => {
    const scene = buildScene(tetrahedron(), { mode: "ball", polyhedra: [0] });
    const view = { rotation: I3, zoom: 1, pan: [0, 0] };
    const [w, h] = [400, 400];
    // the centroid of the face x − y + z = k, which faces the viewer; the ray
    // through it leaves by another face, farther back
    const k = 1.6 / Math.sqrt(3);
    const [x, y, z] = project(scene, view, w, h, [k / 3, -k / 3, k / 3]);
    const hit = pickFace(scene, view, w, h, x, y);
    expect(hit).not.toBeNull();
    expect(hit!.z).toBeCloseTo(z, 9);
    expect(pickFace(scene, view, w, h, 5, 5)).toBeNull();
  });

  it("are named in the caption, drawn or not", () => {
    const geo = tetrahedron();
    expect(caption(geo, "ball", 1, [0])).toContain("polyhedra SiO₄ ×1");
    expect(caption(geo, "ellipsoid", 1, [])).toContain("polyhedra off (SiO₄)");
    expect(caption(geometry(), "ball")).not.toContain("polyhedr");
  });
});
