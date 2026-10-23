"""A rigid body on a special position (WP-1807, #876).

The rotation DOFs are the axial directions the origin's site symmetry fixes,
``wyckoff.axial_basis`` (0, 1 or 3 of them), and the origin keeps its site
basis.  Two refusals keep a body on its sites: ``RIGID_BODY_NOT_INVARIANT``
(an atom on an element its origin is not on, a torsion moving an on-site
atom, a site in rhombohedral axes, a template that does not map onto itself)
and ``RIGID_BODY_IMAGE_OVERLAP`` (a body straddling a symmetry element, the
silent doubled composition of #876).

The cases are the design's (``r6-design-20261015``): diacetylene at 5 K on
the Pnma mirror (COD 1577467, against its Wombat profile), perhydropyrene's
half molecule on the P2₁/n centre (COD 1550439), a constructed body on the
C2/c 2-fold, PbSO₄'s SO₄ on its mirror (``gsas2_pbso4.gpx``, #876's own) and
HKUST-1's BTC linker on .3m (COD 4002052).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography import rotation
from rietx.crystallography.bodies import (
    add_body,
    body_from_atoms,
    place_body_atoms,
)
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.magnetic.operators import allowed_moment_basis
from rietx.crystallography.symmetry import resolve_group, site_orbit
from rietx.crystallography.wyckoff import axial_basis, coordinate_basis
from rietx.io.projects.gsas2 import read_gsas2_gpx, to_structure
from rietx.io.readers import read_pattern
from rietx.model.forward import compile_model
from rietx.optimize.qpa import phase_zmv
from rietx.params.bodies import RigidBodyBlock
from rietx.params.derived import cartesian_frame
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    RIGID_BODY_OVERLAP_FACTOR,
    Atom,
    BodyTorsion,
    Cell,
    Phase,
    Structure,
)
from rietx.strategy.staged import RefinementPlan, Stage

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
LAB = Instrument.debye_scherrer(wavelength=1.5406)
LAB.profile.w.value = 8e-3
BODY = ["phases.*.rigid_bodies.*.origin.dof.*", "phases.*.rigid_bodies.*.rotation.*"]
#: the deposited body origin of COD 1577467 (the molecule's centre, the
#: midpoint of C2 and C3) and GSAS-II's esds on it, from the same 943 points
DIAC_X, DIAC_X_ESD = 0.12673, 0.00105
DIAC_Z, DIAC_Z_ESD = 0.49939, 0.00212


# ------------------------------------------------------------------ helpers
def _fixed(phase: Phase) -> Phase:
    d = phase.model_dump()
    for a in d["atoms"]:
        for c in "xyz":
            a[c]["vary"] = False
    return Phase.model_validate(d)


def _with_body(phase: Phase, *bodies) -> Structure:
    return Structure(phases=[Phase.model_validate(
        {**phase.model_dump(), "rigid_bodies": [b.model_dump() for b in bodies]})])


def _counts(phase: Phase) -> dict[str, float]:
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(),
                    [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
                     for a in phase.atoms])
    return {k: round(v, 9) for k, v in zmv.element_counts.items()}


def _dofs(table: ParameterTable, b: int = 0) -> tuple[int, int]:
    paths = [e.path for e in table.entries]
    return (sum(f".rigid_bodies.{b}.origin.dof." in p for p in paths),
            sum(f".rigid_bodies.{b}.rotation." in p for p in paths))


def _xyz(phase: Phase) -> np.ndarray:
    return np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])


def _decoded_xyz(table: ParameterTable, values, n: int) -> np.ndarray:
    return np.array([[values[f"phases.0.atoms.{j}.{c}"] for c in "xyz"]
                     for j in range(n)])


def _cart(frac: np.ndarray, cell) -> np.ndarray:
    return frac @ np.asarray(cartesian_frame(tuple(cell)), dtype=np.float64).T


def _distances(cart: np.ndarray) -> np.ndarray:
    return np.linalg.norm(cart[:, None] - cart[None], axis=2)


def _quat(deg: float, axis) -> np.ndarray:
    a = np.asarray(axis, dtype=np.float64) / np.linalg.norm(axis)
    return np.asarray(rotation.canonical_quaternion(np.asarray(
        rotation.quaternion_from_vector(math.radians(deg) * a))), dtype=np.float64)


def _angle_deg(qa, qb) -> float:
    ra = np.asarray(rotation.matrix_from_quaternion(np.asarray(qa)))
    rb = np.asarray(rotation.matrix_from_quaternion(np.asarray(qb)))
    return math.degrees(float(np.linalg.norm(
        np.asarray(rotation.vector_from_matrix(ra @ rb.T)))))


def _draw(result, stem: str) -> None:
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}.png"))


def _synthesize(structure: Structure, ins: Instrument, tt, *, peak: float,
                background: float, seed: int) -> PatternData:
    blank = PatternData(two_theta=list(tt), intensity=np.zeros(len(tt)).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = y * (peak / y.max()) + background
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _diacetylene() -> Phase:
    return _fixed(structure_from_cif(str(DATA / "cod_1577467.cif")).phases[0])


def _diacetylene_body(phase: Phase, **kw):
    return body_from_atoms(phase, [a.label for a in phase.atoms], "C4H2", **kw)


def _pbso4() -> Phase:
    return _fixed(to_structure(read_gsas2_gpx(DATA / "gsas2_pbso4.gpx")).phases[0])


def _pbso4_with_o5_image(dy: float = 0.0) -> Phase:
    """#876's five-atom SO₄: S2, O3, O4, O5 and O5's mirror image O5′, all
    moved ``dy`` in y."""
    d = _pbso4().model_dump()
    o5 = next(a for a in d["atoms"] if a["label"] == "O5")
    d["atoms"].append({**o5, "label": "O5p",
                       "y": {**o5["y"], "value": 0.5 - o5["y"]["value"]}})
    for a in d["atoms"]:
        if a["label"] in ("S2", "O3", "O4", "O5", "O5p"):
            a["y"]["value"] += dy
    return Phase.model_validate(d)


SO4_5 = ["S2", "O3", "O4", "O5", "O5p"]


# ----------------------------------------------------- (a) the axial basis
class _Op:
    """The three fields ``allowed_moment_basis`` reads off an operation."""

    def __init__(self, r):
        self.matrix = np.asarray(r, dtype=np.int64)
        self.determinant = int(round(np.linalg.det(r)))
        self.time_reversal = 1


def _point_group_subgroups() -> set[tuple]:
    """Every subgroup of m-3m and of 6/mmm (in their own integer bases).

    Grown one generator at a time from the cyclic groups — the closure of a
    subgroup and one more element, repeated until nothing new appears — so
    every subgroup a pair or a triple of generators closes to is reached; no
    crystallographic point group needs more than three.  Closure runs on a
    multiplication table of operation indices.
    """
    out: set[tuple] = set()
    for symbol in ("P m -3 m", "P 6/m m m"):
        rots = sorted({tuple(map(tuple, (np.array(op.rot) // 24).astype(int)))
                       for op in resolve_group(symbol, None).operations()})
        index = {r: i for i, r in enumerate(rots)}
        table = [[index[tuple(map(tuple, np.array(a) @ np.array(b)))] for b in rots]
                 for a in rots]

        def closure(elems: frozenset) -> frozenset:
            group = set(elems)
            frontier = list(group)
            while frontier:
                new = {table[a][b] for a in frontier for b in group} | {
                    table[b][a] for a in frontier for b in group}
                frontier = list(new - group)
                group |= new
            return frozenset(group)

        found = {closure(frozenset({i})) for i in range(len(rots))}
        layer = set(found)
        while layer:
            layer = {closure(h | {g}) for h in layer for g in range(len(rots))
                     if g not in h} - found
            found |= layer
        out |= {tuple(sorted(rots[i] for i in h)) for h in found}
    return out


def test_the_axial_basis_is_the_moment_law_on_every_point_group_subgroup():
    """``axial_basis`` equals ``allowed_moment_basis`` without time reversal,
    array for array, on all 98 subgroups of m-3m and the 54 of 6/mmm, and its
    dimension is 0, 1 or 3 on every one (the design's D3).  The positive arm
    drops the determinant, the polar law a wrong implementation would carry:
    a mirror then gives the two in-plane directions."""
    groups = _point_group_subgroups()
    # O_h's 98 subgroups and D_6h's 54, sharing the 16 a common basis allows
    assert len(groups) == 136
    orders = sorted({len(g) for g in groups})
    assert orders == [1, 2, 3, 4, 6, 8, 12, 16, 24, 48]
    dims = set()
    for g in groups:
        rots = [np.array(r) for r in g]
        got = axial_basis(rots)
        ref = allowed_moment_basis([_Op(r) for r in rots], use_time_reversal=False)
        assert np.array_equal(got, ref), g
        dims.add(len(got))
    assert dims == {0, 1, 3}
    mirror = [np.eye(3, dtype=int), np.diag([1, -1, 1])]
    assert axial_basis(mirror).tolist() == [[0, 1, 0]]
    polar = allowed_moment_basis([_Op(r) for r in mirror], use_determinant=False,
                                 use_time_reversal=False)
    assert len(polar) == 2 and np.array_equal(polar, coordinate_basis(mirror))


# --------------------------------------- (b) diacetylene builds as a site body
def test_diacetylene_builds_on_the_mirror_with_two_plus_one_dofs():
    """COD 1577467's six atoms, all at y = 3/4 on the 4c mirror, with the body
    origin at their centroid: 2 origin DOFs (x, z) and 1 rotation (about b, a
    linear body in the mirror).  A 3° turn keeps every atom on the mirror and
    every distance the template's; the decode at zero is exact."""
    phase = _diacetylene()
    assert phase.space_group == "P n m a"
    assert phase.cell.lengths_angles() == (9.3478, 5.989, 5.6746, 90.0, 90.0, 90.0)
    assert all(a.y.value == 0.75 for a in phase.atoms)
    s = _with_body(phase, _diacetylene_body(phase, rotation_vary=True))
    table = ParameterTable(s, LAB)
    assert _dofs(table) == (2, 1)
    n = len(phase.atoms)
    theta = table.x0()
    assert np.abs(_decoded_xyz(table, table.decode(theta), n) - _xyz(phase)).max() < 1e-12
    theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.0")] = math.radians(3.0)
    turned = _decoded_xyz(table, table.decode(theta), n)
    assert np.abs(turned[:, 1] - 0.75).max() < 1e-12
    cell = phase.cell.lengths_angles()
    d0 = _distances(_cart(_xyz(phase), cell))
    assert np.abs(_distances(_cart(turned, cell)) - d0).max() < 1e-12
    assert np.abs(turned - _xyz(phase)).max() > 1e-3      # it did turn


def test_the_polar_law_would_take_diacetylene_out_of_its_mirror():
    """The positive arm of the y check: E from the polar law (no det), the
    in-plane direction perpendicular to the molecule, tilts it out of the
    mirror by far more than 1e-3 Å for a 1° turn."""
    phase = _diacetylene()
    table = ParameterTable(_with_body(phase, _diacetylene_body(phase)), LAB)
    block = table._bodies[0][2]
    values = table.decode(table.x0())
    x = np.array([values[q] for q in block.inputs])
    u = block.r0 @ np.cross(block.body_axes[:, 0], block.body_axes[:, 1])
    m = np.asarray(cartesian_frame(phase.cell.lengths_angles()), dtype=np.float64)
    sg = resolve_group(phase.space_group, None)
    stab = site_orbit(sg, np.array(block.evaluate(x)[:3])).stabilizer
    polar = allowed_moment_basis([_Op(r) for r in stab], use_determinant=False,
                                 use_time_reversal=False)
    plane = m @ polar.T.astype(float)
    wrong = plane @ np.linalg.lstsq(plane, np.cross(u, [0.0, 1.0, 0.0]), rcond=None)[0]
    wrong /= np.linalg.norm(wrong)
    assert abs(wrong @ u) < 1e-9 and abs(wrong[1]) < 1e-12   # in the mirror plane
    good = RigidBodyBlock(phase_base="p", body_base="b", atom_bases=["a"] * 6,
                          template=block.template, q0=block.q0,
                          site_axes=wrong.reshape(3, 1))
    x[9] = math.radians(1.0)
    moved = good.evaluate(x).reshape(-1, 3)
    out = float(np.abs(moved[:, 1] - 0.75).max() * phase.cell.b.value)
    assert out >= 1e-3, out


# ---------------------------------------- (c) diacetylene against its profile
def _diacetylene_instrument() -> Instrument:
    ins = Instrument.constant_wavelength_neutron(2.413, fwhm_deg=0.6)
    # GSAS-II's zero on this Wombat run is not in the file; the default
    # ±0.5° box held it at −0.5° and the cell paid 0.2 % for it
    ins.zero_shift.min, ins.zero_shift.max = -3.0, 3.0
    return ins


_PROFILE = ["instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
            "instrument.profile.x"]


def _diacetylene_plan() -> RefinementPlan:
    b = ["phases.*.scale", "instrument.background.*"]
    late = b + ["phases.*.cell.*", "instrument.zero_shift", *_PROFILE,
                "phases.0.atoms.0.biso", *BODY]
    return RefinementPlan(stages=[
        Stage("scale_bkg", b, max_iter=100),
        Stage("cell_zero", b + ["phases.*.cell.*", "instrument.zero_shift"], max_iter=100),
        Stage("profile", b + ["phases.*.cell.*", "instrument.zero_shift", *_PROFILE],
              max_iter=200),
        Stage("body", late, max_iter=200),
        # answers FROZEN_COMPILE_STALE (1.3 % on the stage before): the
        # windows recompiled at the answer
        Stage("final", late, max_iter=200)], intermediate_ftol=1e-6)


def test_diacetylene_origin_matches_the_deposited_model_on_its_wombat_profile():
    """The WP's acceptance line, on the 943 points deposited with COD 1577467
    (Wombat, λ = 2.413 Å, 5 K): scale, a four-term Chebyshev background, zero,
    cell, U V W X, one Biso shared by every atom, the origin and the one
    rotation.  Measured (macOS arm64, 2026-10-16): x = 0.12732(309) against
    0.12673(105), z = 0.49837(757) against 0.49939(212), both inside the
    deposited esd; Rwp 4.00 % against GSAS-II's 3.57 %, which also refined a
    March-Dollase [010] term and the FCJ asymmetry this protocol leaves out.
    The y origin and every atom stay at 3/4 exactly, after the fit and at the
    next build, and the cell holds C 16, H 8."""
    phase = _diacetylene()
    s = _with_body(phase, _diacetylene_body(phase, rotation_vary=True,
                                            origin_vary=True))
    data = read_pattern(DATA / "cod_1577467.cif")
    assert len(data.two_theta) == 943
    ref = Refinement(s, _diacetylene_instrument(), history=False)
    ref.tie_equal(["phases.0.atoms.*.biso"])
    result = ref.fit(data, plan=_diacetylene_plan())
    _draw(result, "diacetylene_5K_site_body")
    assert result.status == "converged"
    assert result.statistics.rwp < 0.05
    fitted = ref.fitted_structure.phases[0]
    origin = fitted.rigid_bodies[0].origin
    assert abs(origin.x.value - DIAC_X) <= DIAC_X_ESD, origin.x.value
    assert abs(origin.z.value - DIAC_Z) <= DIAC_Z_ESD, origin.z.value
    assert origin.y.value == 0.75
    assert all(abs(a.y.value - 0.75) < 1e-12 for a in fitted.atoms)
    table = ParameterTable(ref.fitted_structure, ref.fitted_instrument)
    y = _decoded_xyz(table, table.decode(table.x0()), len(fitted.atoms))[:, 1]
    assert np.abs(y - 0.75).max() < 1e-12
    assert _counts(fitted) == {"C": 16.0, "H": 8.0}


def test_a_displaced_diacetylene_comes_back_on_a_synthetic_profile():
    """The positive arm: a synthetic Wombat-like pattern from the deposited
    model, the fit started 0.3 Å off in x, −0.3 Å in z and 5° in the mirror.
    The origin comes back within 2σ and the orientation within 0.1°."""
    phase = _diacetylene()
    truth = _with_body(phase, _diacetylene_body(phase))
    ins = Instrument.constant_wavelength_neutron(2.413, fwhm_deg=0.6)
    tt = read_pattern(DATA / "cod_1577467.cif").two_theta
    pattern = _synthesize(truth, ins, tt, peak=2e4, background=2e3, seed=7)
    body = truth.phases[0].rigid_bodies[0]
    d = truth.phases[0].model_dump()
    o = d["rigid_bodies"][0]["origin"]
    o["x"]["value"] += 0.3 / phase.cell.a.value
    o["z"]["value"] -= 0.3 / phase.cell.c.value
    d["rigid_bodies"][0]["orientation"] = tuple(float(v) for v in _quat(5.0, (0, 1, 0)))
    d["rigid_bodies"][0]["rotation_vary"] = True
    for c in "xz":
        o[c]["vary"] = True
    start = Structure(phases=[place_body_atoms(Phase.model_validate(d))])
    ref = Refinement(start, ins, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", ["phases.*.scale", "instrument.background.*", *BODY],
              max_iter=200)]))
    assert result.status == "converged"
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0]
    for c, k in (("x", 0), ("z", 1)):
        esd = result.parameter(f"phases.0.rigid_bodies.0.origin.dof.{k}").stderr
        err = getattr(fitted.origin, c).value - getattr(body.origin, c).value
        assert esd is not None and abs(err) < 2 * esd, (c, err, esd)
    assert _angle_deg(fitted.orientation, body.orientation) < 0.1
    assert all(abs(a.y.value - 0.75) < 1e-12 for a in ref.fitted_structure.phases[0].atoms)


# ------------------------------------ (d) perhydropyrene, half a molecule on −1
def _perhydropyrene() -> Phase:
    return _fixed(structure_from_cif(str(DATA / "cod_1550439.cif")).phases[0])


def _shortest_cross_centre_contact(phase: Phase) -> float:
    """The shortest distance from an atom to an inverted image of another
    (through the origin's centre): the bond the half molecules share."""
    frac = _xyz(phase)
    d = frac[:, None, :] + frac[None, :, :]           # x_i − (−x_j)
    d -= np.round(d)
    cart = d @ np.asarray(cartesian_frame(phase.cell.lengths_angles())).T
    return float(np.linalg.norm(cart, axis=2).min())


@pytest.mark.parametrize("off_deg", [3.0, 10.0])
def test_perhydropyrene_half_molecule_on_the_centre_recovers_its_orientation(off_deg):
    """P2₁/n with Z = 2: the asymmetric unit is half of C₁₆H₂₆ about the 2a
    centre, so the body's origin is fixed (0 DOFs) and its rotation free (3:
    −1 fixes every axial direction).  ``RIGID_BODY_IMAGE_OVERLAP`` stays
    silent, the shortest cross-centre contact being C1–C1′, 1.505 Å against
    a 1.02 Å threshold.  A synthetic Cu Kα₁ pattern from the COD model, the
    fit started 3° and 10° off: the orientation comes back within 0.1° and
    each increment's esd covers the truth."""
    phase = _perhydropyrene()
    assert phase.space_group == "P 1 21/n 1" and len(phase.atoms) == 21
    assert _counts(phase) == {"C": 32.0, "H": 52.0}
    body = body_from_atoms(phase, [a.label for a in phase.atoms], "C16H26",
                           origin=(0.0, 0.0, 0.0), rotation_vary=True)
    truth = _with_body(phase, body)
    assert _dofs(ParameterTable(truth, LAB)) == (0, 3)
    contact = _shortest_cross_centre_contact(phase)
    assert contact == pytest.approx(1.505, abs=1e-3)
    assert contact > RIGID_BODY_OVERLAP_FACTOR * 2 * 0.76 - 1e-6
    tt = np.arange(8.0, 60.0, 0.02)
    # 1e5 counts at the strongest line: at 2e4 the noise alone put the answer
    # 0.05-0.08° off over five seeds, against the 0.1° bar; here 0.013-0.039°
    pattern = _synthesize(truth, LAB, tt, peak=1e5, background=50.0, seed=11)
    d = truth.phases[0].model_dump()
    d["rigid_bodies"][0]["orientation"] = tuple(
        float(v) for v in _quat(off_deg, (0.3, 0.8, -0.5)))
    start = Structure(phases=[place_body_atoms(Phase.model_validate(d))])
    ref = Refinement(start, LAB, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", ["phases.*.scale", "instrument.background.*", *BODY],
              max_iter=200)]))
    if off_deg == 10.0:
        _draw(result, "perhydropyrene_site_body")
    assert result.status == "converged"
    fitted = ref.fitted_structure.phases[0].rigid_bodies[0]
    assert _angle_deg(fitted.orientation, body.orientation) < 0.1
    rf = np.asarray(rotation.matrix_from_quaternion(np.asarray(fitted.orientation)))
    rt = np.asarray(rotation.matrix_from_quaternion(np.asarray(body.orientation)))
    w_true = np.asarray(rotation.vector_from_matrix(rt @ rf.T))
    for k in range(3):
        par = result.parameter(f"phases.0.rigid_bodies.0.rotation.{k}")
        assert par.stderr is not None and abs(w_true[k]) < 3 * par.stderr


def test_perhydropyrene_listed_whole_is_refused_as_an_image_overlap():
    """The positive arm of the overlap check: both halves listed put each
    atom on its own inverted image (0 Å), and the cell would hold twice the
    formula — the refusal says so."""
    phase = _perhydropyrene()
    d = phase.model_dump()
    d["atoms"] += [{**a, "label": a["label"] + "i",
                    **{c: {**a[c], "value": -a[c]["value"]} for c in "xyz"}}
                   for a in phase.model_dump()["atoms"]]
    whole = Phase.model_validate(d)
    assert _counts(whole) == {"C": 64.0, "H": 104.0}
    body = body_from_atoms(whole, [a.label for a in whole.atoms], "C16H26",
                           origin=(0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_IMAGE_OVERLAP: rigid body 'C16H26' has the image of its "
            r"atom 'C1' under -x,-y,-z 0 Å from its atom 'C1i' .* "
            r"C 64, H 104 per cell")):
        ParameterTable(_with_body(whole, body), LAB)


# --------------------------------------------- (e) a body on the C2/c 2-fold
def _c2c(space_group: str = "C 1 2/c 1") -> Phase:
    P = Parameter
    cell = Cell(a=P(value=10.2), b=P(value=8.1), c=P(value=9.3),
                alpha=P(value=90.0), beta=P(value=104.0), gamma=P(value=90.0))
    seed = Atom(label="Na", species="Na", x=P(value=0.0), y=P(value=0.0), z=P(value=0.0))
    return Phase(name="c2c", space_group=space_group, cell=cell, atoms=[seed])


#: a C₂-symmetric template about Cartesian y (b): N and O on the axis, a C pair
C2_TEMPLATE = np.array([[0.0, 1.1, 0.0], [0.0, -1.3, 0.0], [1.0, -0.4, 0.8],
                        [-1.0, -0.4, -0.8]])


def test_a_body_on_the_c2c_two_fold_stays_on_its_axis_as_the_cell_moves():
    """The 4e site (0, y, 1/4) of C2/c: 1 origin DOF (y) and 1 rotation (about
    b).  ``add_body`` keeps one atom per image, warning about the one it drops.
    With β moved ±2° and the body turned, N stays on the 2-fold to 1e-12: E
    is b in every monoclinic unique-b cell."""
    with pytest.warns(UserWarning, match=r"places \['Cp'\] as images"):
        phase = add_body(_c2c(), "c2", ["N", "O", "C", "Cp"], ["N", "O", "C", "C"],
                         C2_TEMPLATE, (0.0, 0.31, 0.25), centre=False,
                         rotation_vary=True, origin_vary=True)
    assert [a.label for a in phase.atoms] == ["Na", "N", "O", "C"]
    s = Structure(phases=[phase])
    s.phases[0].cell.beta.vary = True
    table = ParameterTable(s, LAB)
    assert _dofs(table) == (1, 1)
    for dbeta in (2.0, -2.0):
        theta = table.x0()
        theta[table.free_paths.index("phases.0.cell.beta")] += dbeta
        theta[table.free_paths.index("phases.0.rigid_bodies.0.rotation.0")] = 0.2
        values = table.decode(theta)
        assert values["phases.0.cell.beta"] == pytest.approx(104.0 + dbeta)
        for j in (1, 2):                                     # N and O
            n = [values[f"phases.0.atoms.{j}.{c}"] for c in "xyz"]
            assert abs(n[0]) < 1e-12 and abs(n[2] - 0.25) < 1e-12
        c = [values[f"phases.0.atoms.3.{k}"] for k in "xyz"]
        assert abs(c[0] - phase.atoms[3].x.value) > 1e-3       # C did turn


def _trigonal_body(space_group: str, cell, origin, on_axis, general) -> Structure:
    P = Parameter
    phase = Phase(name="r3m", space_group=space_group, cell=Cell(**{
        k: P(value=v) for k, v in zip(("a", "b", "c", "alpha", "beta", "gamma"),
                                      cell, strict=True)}), atoms=[
        Atom(label="X", species="N", x=P(value=on_axis[0]), y=P(value=on_axis[1]),
             z=P(value=on_axis[2])),
        Atom(label="A", species="C", x=P(value=general[0]), y=P(value=general[1]),
             z=P(value=general[2]))])
    return _with_body(phase, body_from_atoms(phase, ["X", "A"], "r3", origin=origin))


#: the obverse rhombohedral axes in hexagonal components (columns a_R, b_R, c_R;
#: International Tables A, Table 5.1.3.1)
HEX_FROM_RHOMB = np.array([[2.0, -1.0, -1.0], [1.0, 1.0, -2.0], [1.0, 1.0, 1.0]]) / 3.0


def test_a_site_body_in_rhombohedral_axes_is_refused_and_builds_in_hexagonal():
    """The 3m axis of R-3m.  Its mirrors contain the axis, so no turn is
    allowed at all, but the axis itself is the site: in rhombohedral axes it
    is M·(1, 1, 1), which turns with the refined α while the template is fixed
    in Å, so the atom on it would leave it inside a stage (D8).  Refused there,
    pointing to :H; the same body in hexagonal axes, the axis along c, builds
    with 1 origin DOF (z) and no rotation."""
    hexa_cell = (6.0, 6.0, 15.0, 90.0, 90.0, 120.0)
    points = [np.array(p) for p in ((0.0, 0.0, 0.2), (0.0, 0.0, 0.28), (0.35, 0.07, 0.23))]
    hexa = _trigonal_body("R -3 m:H", hexa_cell, *points)
    assert _dofs(ParameterTable(hexa, LAB)) == (1, 0)
    g = np.asarray(cartesian_frame(hexa_cell))
    basis = g @ HEX_FROM_RHOMB
    a_r = float(np.linalg.norm(basis[:, 0]))
    alpha = math.degrees(math.acos(basis[:, 0] @ basis[:, 1] / a_r ** 2))
    to_r = np.linalg.inv(HEX_FROM_RHOMB)
    rhom = _trigonal_body("R -3 m:R", (a_r, a_r, a_r, alpha, alpha, alpha),
                          *(tuple(float(v) for v in to_r @ p) for p in points))
    assert rhom.phases[0].atoms[0].x.value == pytest.approx(0.28)   # on (x, x, x)
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_NOT_INVARIANT: rigid body 'r3' has its origin .* "
            r"rhombohedral axes.*hexagonal axes \(:H\)")):
        ParameterTable(rhom, LAB)


# -------------------------------------------- (f) PbSO₄'s SO₄ on its mirror
def test_876s_body_off_the_mirror_is_refused_as_an_image_overlap():
    """#876's route: the five-atom SO₄ moved 0.03 off the mirror in y built in
    silence with Pb 4, S 8, O 32 per cell.  Now the S sits 2·0.03·b = 0.32 Å
    from its own mirror image, and the refusal names the pair, the operation
    and the doubled counts."""
    phase = _pbso4_with_o5_image(0.03)
    assert _counts(phase) == {"Pb": 4.0, "S": 8.0, "O": 32.0}
    body = body_from_atoms(phase, SO4_5, "SO4")
    with pytest.raises(ValueError) as err:
        ParameterTable(_with_body(phase, body), LAB)
    msg = str(err.value)
    m = re.match(r"RIGID_BODY_IMAGE_OVERLAP: rigid body 'SO4' has the image of its "
                 r"atom 'S2' under x,-y\+1/2,z ([0-9.]+) Å from its atom 'S2'", msg)
    assert m, msg
    assert float(m.group(1)) == pytest.approx(2 * 0.03 * phase.cell.b.value, abs=1e-3)
    assert "O 32, S 8 per cell" in msg


def test_876s_body_on_the_mirror_is_an_image_overlap_not_an_origin_refusal():
    """With its centroid on the mirror the old table refused on the origin
    and advised a move off it.  Now the origin is fine and the overlap check
    names what is wrong: O5′ is O5's mirror image, 0 Å away."""
    phase = _pbso4_with_o5_image()
    body = body_from_atoms(phase, SO4_5, "SO4")
    assert body.origin.y.value == pytest.approx(0.25)
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_IMAGE_OVERLAP: rigid body 'SO4' has the image of its "
            r"atom 'O5' under x,-y\+1/2,z 0 Å from its atom 'O5p'")):
        ParameterTable(_with_body(phase, body), LAB)


def _pbso4_pattern() -> tuple[Structure, PatternData]:
    phase = _pbso4()
    truth = _with_body(phase, body_from_atoms(phase, ["S2", "O3", "O4", "O5"], "SO4",
                                              origin="S2"))
    tt = np.arange(10.0, 90.0, 0.02)
    return truth, _synthesize(truth, LAB, tt, peak=2e4, background=50.0, seed=3)


def _two_stage_fit(truth: Structure, pattern: PatternData):
    d = truth.phases[0].model_dump()
    d["rigid_bodies"][0]["orientation"] = tuple(float(v) for v in _quat(0.5, (0, 1, 0)))
    d["rigid_bodies"][0]["rotation_vary"] = True
    start = Structure(phases=[place_body_atoms(Phase.model_validate(d))])
    globs = ["phases.*.scale", "instrument.background.*", "phases.*.atoms.*.dof.*",
             *BODY]
    ref = Refinement(start, LAB, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("s1", globs, max_iter=100), Stage("s2", globs, max_iter=100)],
        closing_window_tol=None))
    return ref, result


def test_the_sulfate_with_its_origin_on_s_refines_across_a_stage_boundary():
    """The four-atom body ``body_from_atoms(..., origin="S2")``: S2, O3, O4 on
    the mirror, O5 general.  It builds 2 + 1 with the cell at Pb 4, S 4, O 16,
    and a two-stage fit's second stage starts where the first ended, to 1e-9
    relative: nothing is counted twice at the boundary (#840 measured the
    start ×119 worse)."""
    truth, pattern = _pbso4_pattern()
    assert _dofs(ParameterTable(truth, LAB)) == (2, 1)
    assert _counts(truth.phases[0]) == {"Pb": 4.0, "S": 4.0, "O": 16.0}
    ref, result = _two_stage_fit(truth, pattern)
    s1, s2 = result.stages
    assert s2.cost_initial == pytest.approx(s1.cost_final, rel=1e-9)
    fitted = ref.fitted_structure.phases[0]
    assert _counts(fitted) == {"Pb": 4.0, "S": 4.0, "O": 16.0}
    assert _angle_deg(fitted.rigid_bodies[0].orientation,
                      truth.phases[0].rigid_bodies[0].orientation) < 0.1


def test_an_unrestricted_turn_on_the_mirror_breaks_the_stage_boundary(monkeypatch):
    """The revert arm: E = I, today's general-position basis, patched in.  The
    body turns off the mirror in stage 1, and stage 2 either refuses or starts
    far from where stage 1 ended."""
    monkeypatch.setattr(RigidBodyBlock, "_increment_basis",
                        lambda self, r0: np.eye(3))
    truth, pattern = _pbso4_pattern()
    try:
        _, result = _two_stage_fit(truth, pattern)
    except ValueError as exc:
        assert "RIGID_BODY_" in str(exc)
        return
    s1, s2 = result.stages
    assert s2.cost_initial > 1.5 * s1.cost_final


# ----------------------------------------------- (g) HKUST-1's BTC on .3m
def test_the_hkust1_linker_on_its_3m_site_has_no_rotation_at_all():
    """The BTC ring centred on the .3m site at (0.156915, 0.343085, 0.156915)
    of Fm-3m: the origin moves along [1, −1, 1] and the 3-fold and its mirrors
    leave no turn (k = 0).  The cell keeps C 288, H 96, O 192, Cu 48."""
    phase = _fixed(structure_from_cif(str(DATA / "cod_4002052.cif")).phases[0])
    body = body_from_atoms(phase, ["C1", "C2", "C3", "O1", "H3"], "BTC",
                           origin=(0.156915, 0.343085, 0.156915))
    s = _with_body(phase, body)
    table = ParameterTable(s, LAB)
    assert _dofs(table) == (1, 0)
    values = table.decode(table.x0())
    assert np.abs(_decoded_xyz(table, values, len(phase.atoms)) - _xyz(phase)).max() < 1e-12
    assert _counts(phase) == {"Cu": 48.0, "O": 192.0, "C": 288.0, "H": 96.0}


# ------------------------------------------------- (h) refusals and rewrites
def test_an_atom_on_an_element_its_origin_is_not_on_is_refused_naming_both():
    """A body on the C2/c 2-fold with a member atom on an inversion centre:
    the centre is not in the origin's site symmetry, so a turn would move the
    atom off it.  The refusal names the atom and the operation."""
    P = Parameter
    phase = _c2c().model_copy(update={"atoms": [
        Atom(label="Na", species="Na", x=P(value=0.0), y=P(value=0.0), z=P(value=0.0)),
        Atom(label="O", species="O", x=P(value=0.0), y=P(value=0.12), z=P(value=0.25))]})
    phase = Phase.model_validate(phase.model_dump())
    body = body_from_atoms(phase, ["Na", "O"], "NaO", origin="O")
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_NOT_INVARIANT: rigid body 'NaO' has its atom 'Na' at "
            r"\(0.0, 0.0, 0.0\) .* \(site symmetry of order 2\), on the element of "
            r"operation -x,-y,-z that the body's origin \(0.0, 0.12, 0.25\)")):
        ParameterTable(_with_body(phase, body), LAB)


def test_a_torsion_moving_an_atom_on_the_mirror_is_refused_naming_both():
    phase = _pbso4()
    body = body_from_atoms(phase, ["S2", "O3", "O4", "O5"], "SO4", origin="S2")
    body = body.model_copy(update={"torsions": [
        BodyTorsion(name="t0", axis=("S2", "O5"), moves=["O4"], angle=0.0)]})
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_NOT_INVARIANT: rigid body 'SO4' has its torsion 't0' "
            r"move atom 'O4', which sits on a special position")):
        ParameterTable(_with_body(phase, body), LAB)


def _so4_template() -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    phase = _pbso4_with_o5_image()
    by = {a.label: a for a in phase.atoms}
    frac = np.array([[by[k].x.value, by[k].y.value, by[k].z.value] for k in SO4_5])
    cart = _cart(frac - frac[0], phase.cell.lengths_angles())
    return SO4_5, ["S", "O", "O", "O", "O"], cart, frac[0]


def test_add_body_on_the_mirror_keeps_one_atom_per_image():
    """The whole SO₄ placed on the mirror at S: four atoms appended, O5′
    dropped with a warning, and the table builds 2 + 1 at S 4, O 16."""
    labels, species, template, s_at = _so4_template()
    base = _pbso4()
    base = Phase.model_validate({**base.model_dump(), "atoms": [
        a.model_dump() for a in base.atoms if a.label == "Pb1"]})
    with pytest.warns(UserWarning, match=r"places \['O5p'\] as images"):
        phase = add_body(base, "SO4", labels, species, template, s_at, centre=False)
    assert [a.label for a in phase.atoms] == ["Pb1", "S2", "O3", "O4", "O5"]
    s = Structure(phases=[phase])
    assert _dofs(ParameterTable(s, LAB)) == (2, 1)
    assert _counts(phase) == {"Pb": 4.0, "S": 4.0, "O": 16.0}


@pytest.mark.parametrize("tilt", [5.0, 30.0])
def test_add_body_refuses_a_diacetylene_tilted_out_of_the_mirror(tilt):
    """D6 at any angle: the table's overlap backstop only sees a tilt below
    about 42°, the template check sees every one."""
    ref = _diacetylene()
    cell = ref.cell.lengths_angles()
    frac = _xyz(ref)
    centre = frac.mean(axis=0)
    template = _cart(frac - centre, cell)
    base = Phase.model_validate({**ref.model_dump(), "atoms": [
        {**ref.atoms[0].model_dump(), "label": "Q", "x": {"value": 0.5},
         "y": {"value": 0.25}, "z": {"value": 0.0}}]})
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_NOT_INVARIANT: add_body 'C4H2' has its origin on a "
            r"special position .* its point 'C1' maps under x,-y\+1/2,z")):
        add_body(base, "C4H2", [a.label for a in ref.atoms],
                 [a.species for a in ref.atoms], template, centre,
                 orientation=_quat(tilt, (1, 0, 0)))


def test_a_target_orientation_off_the_site_is_refused_and_one_on_it_reached():
    phase = _diacetylene()
    table = ParameterTable(_with_body(phase, _diacetylene_body(phase,
                                                               rotation_vary=True)), LAB)
    base = "phases.0.rigid_bodies.0"
    with pytest.raises(ValueError, match=(
            r"RIGID_BODY_NOT_INVARIANT: the target orientation of rigid body "
            r"'C4H2' turns it 2° about a direction its origin's site symmetry "
            r"does not allow")):
        table.displace_anchored_dofs({}, lambda p: True,
                                     orientations={base: _quat(2.0, (1, 0, 0))})
    moved = table.displace_anchored_dofs({}, lambda p: True,
                                         orientations={base: _quat(2.0, (0, 1, 0))})
    assert moved == [f"{base}.rotation.0"]
    assert table.decode(table.x0())[f"{base}.rotation.0"] == pytest.approx(
        math.radians(2.0), abs=1e-12)


def _refusal(build) -> str:
    with pytest.raises(ValueError) as err:
        build()
    return str(err.value)


def test_no_rigid_body_message_keeps_a_numpy_repr_or_the_old_advice():
    """#876's two message defects: the origin printed ``np.float64(...)``
    reprs and advised a move off the site that doubles the composition.  The
    source no longer carries the advice, and no refusal of a body on or near a
    site prints a numpy repr or opens with anything but its code."""
    root = Path(__file__).parents[1] / "src" / "rietx"
    for path in (root / "params" / "vector.py", root / "params" / "bodies.py",
                 root / "crystallography" / "bodies.py"):
        assert "move the origin to a general position" not in path.read_text(encoding="utf-8"), path
    off, on = _pbso4_with_o5_image(0.03), _pbso4_with_o5_image()
    pbso4 = _pbso4()
    twisted = body_from_atoms(pbso4, ["S2", "O3", "O4", "O5"], "SO4", origin="S2")
    twisted = twisted.model_copy(update={"torsions": [
        BodyTorsion(name="t0", axis=("S2", "O5"), moves=["O4"], angle=0.0)]})
    hill = body_from_atoms(pbso4, ["S2", "O3", "O4", "O5"], "SO4")
    messages = [
        _refusal(lambda: ParameterTable(_with_body(off, body_from_atoms(off, SO4_5, "SO4")),
                                        LAB)),
        _refusal(lambda: ParameterTable(_with_body(on, body_from_atoms(on, SO4_5, "SO4")),
                                        LAB)),
        _refusal(lambda: ParameterTable(_with_body(pbso4, twisted), LAB)),
        _refusal(lambda: ParameterTable(_with_body(pbso4, hill), LAB)),
    ]
    for msg in messages:
        assert msg.startswith("RIGID_BODY_") and "np.float64(" not in msg, msg


# ------------------------------------- Yue's round 1 on #1005 (items 1-4)
def _p21c() -> Phase:
    P = Parameter
    cell = Cell(a=P(value=7.1), b=P(value=9.2), c=P(value=8.3), alpha=P(value=90.0),
                beta=P(value=101.0), gamma=P(value=90.0))
    return Phase(name="p21c", space_group="P 1 21/c 1", cell=cell, atoms=[
        Atom(label="Na", species="Na", x=P(value=0.1), y=P(value=0.2), z=P(value=0.3))])


def test_a_body_spanning_two_inversion_centres_is_refused_not_built_with_three_dofs():
    """Item 1: -1 fixes (0,0,0) and (1/2,0,0) alike modulo the lattice, so the
    old test saw one site symmetry for both and let the body build with three
    turns; any turn takes the second atom off its centre, one lattice vector
    from where -1 holds it.  The exact test in unwrapped body coordinates,
    R·(p − o) = p − o, refuses it; the positive arm, the origin's centre with
    a general atom beside it, still builds."""
    P = Parameter
    base = _p21c()
    for second, ok in (((0.5, 0.0, 0.0), False), ((0.2, 0.1, 0.15), True)):
        atoms = [base.atoms[0], Atom(label="A", species="C", x=P(value=0.0),
                                     y=P(value=0.0), z=P(value=0.0)),
                 Atom(label="B", species="O", x=P(value=second[0]),
                      y=P(value=second[1]), z=P(value=second[2]))]
        phase = Phase.model_validate({**base.model_dump(),
                                      "atoms": [a.model_dump() for a in atoms]})
        body = body_from_atoms(phase, ["A", "B"], "pair", origin="A")
        if ok:
            ParameterTable(_with_body(phase, body), LAB)
            continue
        with pytest.raises(ValueError, match=(
                r"RIGID_BODY_NOT_INVARIANT: rigid body 'pair' has its atom 'B' at "
                r"\(0.5, 0.0, 0.0\).*-x,-y,-z.*lattice")):
            ParameterTable(_with_body(phase, body), LAB)


def test_two_fold_axes_a_lattice_vector_apart_are_refused_on_c2c():
    """Item 1's other cases: C2/c's 2-folds at x = 0 and x = 1/2 are the same
    element modulo the lattice and different elements for a turn."""
    P = Parameter
    base = _c2c()
    atoms = [Atom(label="A", species="N", x=P(value=0.0), y=P(value=0.3), z=P(value=0.25)),
             Atom(label="B", species="O", x=P(value=0.5), y=P(value=0.3), z=P(value=0.25))]
    phase = Phase.model_validate({**base.model_dump(),
                                  "atoms": [a.model_dump() for a in atoms]})
    body = body_from_atoms(phase, ["A", "B"], "pair", origin="A")
    with pytest.raises(ValueError, match=r"RIGID_BODY_NOT_INVARIANT.*atom 'B'.*lattice"):
        ParameterTable(_with_body(phase, body), LAB)


def test_a_linear_body_off_its_site_axis_by_cif_precision_is_accepted():
    """Item 2: the site check snaps within SITE_TOL, so a linear body whose
    end is typed 4e-5 (fractional) off the mirror passes it and must not then
    be refused at 89.99° by a 1e-9 axis test; a tilt of 3e-2 still is."""
    ref = _diacetylene()
    for dy, ok in ((4e-5, True), (3e-2, False)):
        d = ref.model_dump()
        d["atoms"][0]["y"]["value"] += dy
        phase = Phase.model_validate(d)
        try:
            body = _diacetylene_body(phase, rotation_vary=True)
            table = ParameterTable(_with_body(phase, body), LAB)
        except ValueError as exc:
            assert not ok, exc
            continue
        assert ok and _dofs(table) == (2, 1)


def test_add_body_refuses_a_torsion_naming_an_atom_it_dropped():
    """Item 3: on the C2/c 2-fold ``add_body`` drops Cp, an image of C.  A
    torsion that moves Cp used to ride through to a later, unrelated error;
    now the call refuses naming the torsion and the dropped atom."""
    torsion = BodyTorsion(name="t0", axis=("N", "O"), moves=["Cp"], angle=0.0)
    with pytest.warns(UserWarning, match=r"places \['Cp'\] as images"):
        with pytest.raises(ValueError, match=(
                r"add_body 'c2': its torsion 't0' names 'Cp', which the space group "
                r"places as an image of an atom kept")):
            add_body(_c2c(), "c2", ["N", "O", "C", "Cp"], ["N", "O", "C", "C"],
                     C2_TEMPLATE, (0.0, 0.31, 0.25), centre=False,
                     torsions=[torsion])


def test_a_disorder_group_exempts_a_body_across_the_mirror_from_the_overlap_refusal():
    """Item 4: the skill's remedy for IMAGE_OVERLAP, tested.  The whole SO₄ on
    the mirror at its centroid is refused (test above); with a disorder_group
    on its atoms the same body builds."""
    d = _pbso4_with_o5_image().model_dump()
    for a in d["atoms"]:
        if a["label"] in SO4_5:
            a["disorder_group"] = "1"
    phase = Phase.model_validate(d)
    body = body_from_atoms(phase, SO4_5, "SO4")
    ParameterTable(_with_body(phase, body), LAB)
