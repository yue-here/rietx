"""WP-1806: acridine form IX, the rigid body on real data (#561).

The case is COD 2242872 (CC0): acridine form IX, C₁₃H₉N, P2₁/n, from Stephens,
Schur, Lapidus & Bernstein (2019) *Acta Cryst.* E75, 489,
doi:10.1107/S2056989019003645, with its NSLS X16C capillary pattern
(λ 0.699789 Å, 6 601 points) deposited in the same file.  The body is the 14
deposited heavy atoms (``body_from_atoms``) plus 9 riding H, and only its origin and orientation refine.

This file asserts what the body machinery owns, and nothing about the
published esds:

* **the free-atom control** (part 2, Yue's bar of 2026-11-05) — the same
  model with the 14 heavy atoms free and unrestrained, each H riding on its
  carrier, refined under the same data, profile, background and plan, lands
  where the body does: every coordinate and the mean position along each
  axis within ``CONTROL_BOUND`` esds of the difference;
* **the template round trip** — declaring the body moves no atom;
* **start-independence** — the deposited pose and one 10° / 0.3 Å away reach
  one minimum on the real data;
* **the esd rules** — a distance inside the body reports ``None``
  (``VARIANCE_CANCELLATION_FLOOR``) and one to another molecule a full esd;
* **a known answer with a positive arm** — a pattern simulated with the
  forward model from the deposited coordinates, at the profile the real fit
  converged to, plus Gaussian noise at the deposit's own σ, is refitted from
  the perturbed start and returns the deposited coordinates within
  ``KNOWN_ANSWER_BOUND`` of rietx's esds; a regular-hexagon template refitted
  the same way does not.

The deposited coordinates are another model's answer under another protocol
(``docs/DESIGN.md`` Rule 2), so they judge nothing here: the per-atom table
against the deposit (|Δ|, published esd, rietx esd, ratio), with the cell
in rows of its own, is written to ``tests/output/acridine_ix_deposit_table.md``
as a record and asserts nothing.  The bar is the free-atom control in rietx,
and its table goes to ``tests/output/acridine_ix_control_table.md``.

**The protocol** is the authors' profile as the 2026-10-16 measurement read it
from the paper: Debye-Scherrer, a 10-term Chebyshev plus one broad Gaussian
hump, TCHZ U V W X Y, FCJ asymmetry, Stephens 2/m strain seeded at 1000 ppm,
March-Dollase along (100), one Biso for the heavy atoms with the H at 1.5×, a
zero shift and the cell, in four cumulative stages.  **FCJ H/L is held at
0.01**: on this pattern S/L and H/L are one direction (ρ −1.000 on main at
feae4c75, 2026-10-27), and holding H/L moves no heavy-atom coordinate by more
than 0.041 of rietx's own esd (median 0.011, 42 components, deposited start,
Rwp 0.058424 held against 0.058395 freed), so freeing both buys nothing but a
flat direction.
"""

from __future__ import annotations

import math
import re

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import rotation
from rietx.crystallography.bodies import body_from_atoms, place_body_atoms
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.riding import set_riding_lengths
from rietx.model.forward import compile_model
from rietx.params.derived import cartesian_frame
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion, HumpComponent
from rietx.schemas.structure import (
    Phase,
    PreferredOrientation,
    RigidBody,
    StephensStrain,
    Structure,
)
from rietx.strategy.staged import CLOSING_WINDOW_TOL, INTERMEDIATE_FTOL
from tests.test_rigid_body_special import DATA, OUT, _draw

FIXTURE = DATA / "cod_2242872.cif"
HEAVY = ["N1"] + [f"C{i}" for i in range(1, 14)]
HYDROGENS = [f"H{i}" for i in range(1, 10)]
#: the deposit's _diffrn_radiation_wavelength (NSLS X16C)
WAVELENGTH = 0.699789

#: the perturbed start: a 10° turn and a 0.3 Å shift, along fixed, unrelated
#: directions (the 2026-10-16 and 2026-10-27 measurements' own)
TURN_DEG, TURN_AXIS = 10.0, (0.3, 0.8, -0.5)
SHIFT_ANG, SHIFT_DIR = 0.3, (0.6, -0.3, 0.74)

#: two starts are one minimum when no heavy atom differs by more than this
#: (Å).  Measured 1.6e-6 Å (2026-11-05, on 0f4da1b5) and 0.0001 Å (on
#: feae4c75, 2026-10-27); the bar sits ≥ 10× above both and 2× below the
#: smallest rietx esd on a coordinate here (0.0020 Å).
START_TOL_ANG = 1e-3

#: the known-answer bar: every heavy-atom coordinate within this many of its
#: own rietx esd of the deposited value.  With white Gaussian noise at the σ
#: the fit weights by, a correct model leaves |Δ|/esd ≈ |N(0, 1)| per
#: component, and P(|z| > 4) = 6.3e-5, so the union over 42 components fails a
#: correct fit with probability ≤ 0.3 %.
KNOWN_ANSWER_BOUND = 4.0
NOISE_SEED = 1806

#: each H's carrier, by the deposit's own numbering (Hi on Ci; the nearest
#: heavy atom to every H in the deposit, checked 2026-11-12)
RIDES_ON = {f"H{i}": f"C{i}" for i in range(1, 10)}

#: the free-atom control's bar (Yue's 2026-11-05 ruling, read off the
#: control's own esds): every heavy-atom coordinate of the body, and the
#: molecule's mean position along each axis, within this many esds of the
#: control's.  The esd is that of the *difference* of two nested fits of one
#: pattern, √(σ²_control − σ²_body) (Hausman 1978, *Econometrica* 46, 1251),
#: with the body's σ put on the control's GoF and Bérar-Lelann scale so the
#: two share one σ²: where the body is right, both estimate the same
#: coordinates and the body, the restricted fit, is the efficient one.  The
#: nesting is not exact: the body turns each H with the molecule, while the
#: control's H takes only its carrier's shift, a difference of at most
#: 0.0015 Å on an atom of one electron (WP-1806, 2026-11-12).  The bar can
#: fail: the regular-hexagon body on this pattern breaks it at 8.7 esds.
#: So |Δ|/esd ≈ |N(0, 1)| per statistic, and the same 4 as the known
#: answer's bar fails a correct body over 45 statistics with probability
#: ≤ 0.3 %.  The control's two starts (the deposit, the body's answer) land
#: 0.0002 Å apart, 0.02 of the difference's esd, so the bar senses no solver
#: termination.
CONTROL_BOUND = 4.0

_SU = re.compile(r"([-+]?\d*\.?(\d*))\((\d+)\)")
#: the deposit's refined cell items, and the rietx cell field each one is
CELL = {"length_a": "a", "length_b": "b", "length_c": "c", "angle_beta": "beta"}


# ------------------------------------------------------------------ helpers
def _published_cell_esds() -> dict[str, float]:
    """The deposit's cell esds, as typed (``11.28453(11)`` → 1.1e-4)."""
    block = gemmi.cif.read(str(FIXTURE)).sole_block()
    out = {}
    for key in CELL:
        m = _SU.fullmatch(block.find_value("_cell_" + key))
        out[key] = float(f"{m[3]}e-{len(m[2])}")
    return out


def _published() -> tuple[dict, dict]:
    """The deposit's heavy-atom coordinates and esds, and its cell, as typed."""
    block = gemmi.cif.read(str(FIXTURE)).sole_block()
    atoms = {}
    for row in block.find("_atom_site_", ["label", "fract_x", "fract_y", "fract_z"]):
        vals, esds = [], []
        for k in (1, 2, 3):
            m = _SU.fullmatch(row[k])
            vals.append(float(m[1]) if m else float(row[k]))
            esds.append(float(f"{m[3]}e-{len(m[2])}") if m else None)
        atoms[row[0]] = (vals, esds)
    cell = {}
    for key in CELL:
        m = _SU.fullmatch(block.find_value("_cell_" + key))
        cell[key] = float(m[1])
    return atoms, cell


def _deposited_phase() -> Phase:
    return structure_from_cif(str(FIXTURE)).phases[0]


def _deposited_body(phase: Phase) -> RigidBody:
    body = body_from_atoms(phase, HEAVY + HYDROGENS, "acridine")
    return set_riding_lengths(body, {h: "aromatic_CH" for h in HYDROGENS}, "xray")


def _hexagons(cc: float = 1.39, cn: float = 1.34) -> dict[str, np.ndarray]:
    """Acridine as three regular hexagons (C–C ``cc``), the two C–N bonds
    shortened to ``cn`` by moving N1 along the mirror: an idealised template,
    planar and C2v, 0.064 Å RMS from the deposited atoms at best superposition
    (the 2026-10-15 groundwork's template T2)."""
    h, s3 = cc, math.sqrt(3.0)
    pts = {"C13": (s3 / 2 * h, h / 2), "C12": (s3 / 2 * h, -h / 2), "C5": (0.0, -h),
           "C11": (-s3 / 2 * h, -h / 2), "C10": (-s3 / 2 * h, h / 2)}
    left = np.array([-s3 * h, 0.0])
    for k, name in enumerate(["C10", "C1", "C2", "C3", "C4", "C11"]):
        a = math.radians(30.0 + 60.0 * k)
        pts.setdefault(name, tuple(left + h * np.array([math.cos(a), math.sin(a)])))
    for l1, l2 in (("C1", "C9"), ("C2", "C8"), ("C3", "C7"), ("C4", "C6")):
        pts[l2] = (-pts[l1][0], pts[l1][1])
    pts["N1"] = (0.0, h / 2 + math.sqrt(cn ** 2 - (s3 / 2 * h) ** 2))
    return {k: np.array([v[0], v[1], 0.0]) for k, v in pts.items()}


def _kabsch(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    """``t`` turned and shifted onto ``x`` by least squares (Kabsch 1976)."""
    tc, xc = t.mean(0), x.mean(0)
    u, _, vt = np.linalg.svd((t - tc).T @ (x - xc))
    d = np.diag([1.0, 1.0, np.sign(np.linalg.det(vt.T @ u.T))])
    return (t - tc) @ (vt.T @ d @ u.T).T + xc


def _hexagon_body(phase: Phase) -> RigidBody:
    """The deposited body with its heavy atoms replaced by the hexagons,
    superposed onto them in the body frame, and the riding H re-placed."""
    body = body_from_atoms(phase, HEAVY + HYDROGENS, "acridine_hexagons")
    tpl = np.asarray(body.template, dtype=np.float64)
    ideal = np.array([_hexagons()[lab] for lab in HEAVY])
    tpl[: len(HEAVY)] = _kabsch(ideal, tpl[: len(HEAVY)])
    body = RigidBody.model_validate({**body.model_dump(),
                                     "template": [tuple(map(float, t)) for t in tpl]})
    return set_riding_lengths(body, {h: "aromatic_CH" for h in HYDROGENS}, "xray")


def _with(phase: Phase, body: RigidBody, *, perturb: bool) -> Phase:
    """``phase`` carrying ``body``, its atoms placed by it, at the deposited
    pose or at the perturbed one."""
    placed = place_body_atoms(phase.model_copy(update={"rigid_bodies": [body]}))
    if not perturb:
        return placed
    m = np.asarray(cartesian_frame(placed.cell.lengths_angles()))
    axis = np.asarray(TURN_AXIS) / np.linalg.norm(TURN_AXIS)
    r = np.asarray(rotation.matrix_from_vector(math.radians(TURN_DEG) * axis))
    q = rotation.canonical_quaternion(rotation.quaternion_from_matrix(r))
    shift = np.linalg.solve(m, SHIFT_ANG * np.asarray(SHIFT_DIR) / np.linalg.norm(SHIFT_DIR))
    origin = body.origin.model_copy(deep=True)
    for k, c in enumerate("xyz"):
        getattr(origin, c).value += float(shift[k])
    return place_body_atoms(placed.model_copy(update={"rigid_bodies": [
        body.model_copy(update={"orientation": tuple(float(v) for v in np.asarray(q)),
                                "origin": origin})]}))


def _start(phase: Phase) -> Structure:
    """The fit's starting structure: March-Dollase (100) from 1 and a
    Stephens 2/m block from zero (``strain_seed`` lifts it)."""
    return Structure(phases=[phase.model_copy(update={
        "preferred_orientation": PreferredOrientation(
            axis=(1, 0, 0), r=Parameter(value=1.0, min=0.15, max=6.0)),
        "microstrain": StephensStrain.from_values([0.0] * 15)})])


def _instrument() -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    # dispersion declared on, the package default, so these numbers do not
    # move if the default does
    ins.source.dispersion = Dispersion()
    ins.background = BackgroundChebyshev.with_terms(10)
    ins.extra_components = [HumpComponent(
        position=Parameter(value=11.5, unit="deg"), height=Parameter(value=200.0, min=0.0),
        fwhm=Parameter(value=6.0, min=2.0, unit="deg"))]
    p = ins.profile
    p.u.value, p.v.value, p.w.value, p.x.value, p.y.value = 0.0, 0.0, 4e-4, 5e-3, 5e-3
    ins.geometry.axial_sl.value = 0.01
    ins.geometry.axial_hl.value = 0.01      # held: see the module docstring
    return ins


_BKG = ["phases.*.scale", "instrument.background.*", "instrument.extra_components.*"]
_PROFILE = ["phases.*.cell.*", "instrument.zero_shift", "instrument.profile.u",
            "instrument.profile.v", "instrument.profile.w", "instrument.profile.x",
            "instrument.profile.y", "phases.*.preferred_orientation.r",
            "instrument.geometry.axial_sl", "phases.*.microstrain.dof.*"]
_POSE = ["phases.*.rigid_bodies.*.origin.dof.*", "phases.*.rigid_bodies.*.rotation.*"]


def _fit(structure: Structure, pattern: rx.PatternData):
    """The authors' profile in four cumulative stages.  A phase carrying the
    body refines its pose; one without a body is the free-atom control and
    refines the heavy atoms' coordinates, each H riding on its carrier."""
    ref = rx.Refinement(structure, _instrument(), history=False)
    atoms = structure.phases[0].atoms
    idx = {a.label: i for i, a in enumerate(atoms)}
    heavy = [f"phases.0.atoms.{idx[lab]}.biso" for lab in HEAVY]
    # named: tie_equal's default source is the first match in *table* order,
    # and the H ties and the biso stage below both lean on heavy[0] being it
    ref.tie_equal(heavy, source=heavy[0])
    for h in HYDROGENS:
        ref.tie(f"phases.0.atoms.{idx[h]}.biso", heavy[0], scale=1.5)
    if structure.phases[0].rigid_bodies:
        moving, stage = _POSE, "pose"
    else:
        # riding in SHELX's sense: the H takes its carrier's coordinate shift,
        # so it starts where the body put it and keeps the C-H vector
        for h in HYDROGENS:
            for k in range(3):
                ref.tie(f"phases.0.atoms.{idx[h]}.dof.{k}",
                        f"phases.0.atoms.{idx[RIDES_ON[h]]}.dof.{k}")
        moving, stage = [f"phases.0.atoms.{idx[lab]}.dof.*" for lab in HEAVY], "atoms"
    stages = [rx.Stage("scale_bkg", _BKG, max_iter=200),
              rx.Stage("profile_cell", _BKG + _PROFILE, max_iter=300, strain_seed=1000.0),
              rx.Stage(stage, _BKG + _PROFILE + moving, max_iter=2000),
              rx.Stage("biso", _BKG + _PROFILE + moving + [heavy[0]], max_iter=2000)]
    # the shipped schedule and closing stage, declared: these numbers are what
    # a user's own run of this plan produces
    plan = rx.RefinementPlan(stages=stages, intermediate_ftol=INTERMEDIATE_FTOL,
                             closing_window_tol=CLOSING_WINDOW_TOL)
    result = ref.fit(pattern, plan=plan)
    return ref, result


def _heavy(phase: Phase) -> dict[str, tuple[np.ndarray, list]]:
    """{label: (fractional xyz, [rietx esd x, y, z])} over the heavy atoms."""
    return {a.label: (np.array([a.x.value, a.y.value, a.z.value]),
                      [a.x.stderr, a.y.stderr, a.z.stderr])
            for a in phase.atoms if a.label in HEAVY}


def _ratios(phase: Phase) -> dict[str, list[float]]:
    """|Δ_k| / rietx esd_k against the deposited coordinates (inf: no esd)."""
    pub, _ = _published()
    out = {}
    for lab, (xyz, esd) in _heavy(phase).items():
        d = np.abs(xyz - np.asarray(pub[lab][0]))
        out[lab] = [float(d[k] / esd[k]) if esd[k] else math.inf for k in range(3)]
    return out


def _deposit_table(phase: Phase, rwp: float) -> str:
    """The per-atom table against the deposit: a record, not a bar."""
    pub, cell = _published()
    lines = ["# Acridine form IX, deposited start: the deposit record (not asserted)",
             "", f"Rwp {rwp:.5f}.  ratio = |Δ| / max(published esd, rietx esd), "
             "per component.  A record: it asserts nothing, and the bar is the "
             "free-atom control in rietx (acridine_ix_control_table.md).", "",
             "| atom | axis | |Δ| frac | published esd | rietx esd | ratio |",
             "|---|---|---|---|---|---|"]
    for lab, (xyz, esd) in _heavy(phase).items():
        for k, c in enumerate("xyz"):
            d = abs(float(xyz[k]) - pub[lab][0][k])
            p = pub[lab][1][k]
            r = d / max(p or 0.0, esd[k] or 0.0)
            lines.append(f"| {lab} | {c} | {d:.5f} | {'None' if p is None else f'{p:g}'} | "
                         f"{'None' if esd[k] is None else f'{esd[k]:.5f}'} | {r:.2f} |")
    # the cell joins the record and asserts nothing either (Yue, 2026-11-07):
    # the published cell is the authors' answer under their own protocol
    cell_esd = _published_cell_esds()
    lines += ["", "| cell | unit | |Δ| | published esd | rietx esd | ratio |",
              "|---|---|---|---|---|---|"]
    for key, name in CELL.items():
        par = getattr(phase.cell, name)
        d = abs(float(par.value) - cell[key])
        r = d / max(cell_esd[key], par.stderr or 0.0)
        unit = "deg" if name == "beta" else "Å"
        lines.append(f"| {name} | {unit} | {d:.5f} | {cell_esd[key]:g} | "
                     f"{'None' if par.stderr is None else f'{par.stderr:.5f}'} | {r:.2f} |")
    return "\n".join(lines) + "\n"


def _mean_position(ref, result) -> list[tuple[float, float]]:
    """The heavy atoms' mean fractional coordinate along x, y and z, each
    with its variance through the fit's whole covariance (J·Cov·Jᵀ)."""
    kept = ref._answer_covariance
    # the covariance of *this* answer, correlated: a diagonal-only one would
    # pass for the whole covariance silently (magnetic._moment_correlations)
    assert kept is not None and kept[0] is result, "no covariance kept for this result"
    _, table, theta, stderr_internal, correlation = kept
    assert stderr_internal is not None and correlation is not None
    row = {e.path: i for i, e in enumerate(table.entries)}
    heavy = [(i, a) for i, a in enumerate(ref.fitted_structure.phases[0].atoms)
             if a.label in HEAVY]
    w = np.full(len(heavy), 1.0 / len(heavy))
    out = []
    for c in "xyz":
        paths = [f"phases.0.atoms.{i}.{c}" for i, _ in heavy]
        # a column that measured nothing is zeroed in the covariance, which
        # would understate the variance rather than make it absent
        assert not table.unmeasured_rows(theta, stderr_internal,
                                         np.array([row[p] for p in paths])).any(), c
        cov = table.physical_covariance(theta, stderr_internal, correlation, paths)
        out.append((float(np.mean([getattr(a, c).value for _, a in heavy])),
                    float(w @ cov @ w)))
    return out


def _esd_scale(result) -> float:
    """The factor a fit's esds carry over √((JᵀJ)⁻¹): GoF × Bérar-Lelann."""
    return result.statistics.gof * (result.statistics.esd_inflation or 1.0)


def _against_control(body, control) -> tuple[list[tuple], list[tuple]]:
    """Per heavy-atom component and per mean axis: (label, axis, Δ in Å,
    control esd in Å, esd of the difference in Å, |Δ| / that esd).  ``body``
    and ``control`` are each a fit's (ref, result)."""
    body_ref, control_ref = body[0], control[0]
    pb = body_ref.fitted_structure.phases[0]
    pc = control_ref.fitted_structure.phases[0]
    lengths = [pc.cell.a.value, pc.cell.b.value, pc.cell.c.value]
    hb, hc = _heavy(pb), _heavy(pc)
    # Hausman's subtraction needs one σ² for both covariances, and each fit
    # scales its esds by its own GoF and Bérar-Lelann factor: put the body's
    # on the control's scale (a worse body has the larger GoF, and on its own
    # scale its esd can exceed the control's)
    scale = (_esd_scale(control[1]) / _esd_scale(body[1])) ** 2
    atoms = []
    for lab in HEAVY:
        for k, c in enumerate("xyz"):
            eb, ec = hb[lab][1][k], hc[lab][1][k]
            var = ec * ec - scale * eb * eb
            assert var > 0.0, (lab, c, eb, ec, scale)
            diff = math.sqrt(var)
            d = float(hb[lab][0][k] - hc[lab][0][k])
            atoms.append((lab, c, d * lengths[k], ec * lengths[k], diff * lengths[k],
                          abs(d) / diff))
    means = []
    for k, ((mb, vb), (mc, vc)) in enumerate(zip(_mean_position(*body),
                                                 _mean_position(*control))):
        # the nested-fit premise, as the test asserts it per atom: without it
        # the difference has no esd, and sqrt would raise a bare ValueError
        assert vc > scale * vb, ("mean", "xyz"[k], vb, vc, scale)
        diff = math.sqrt(vc - scale * vb)
        means.append(("mean", "xyz"[k], (mb - mc) * lengths[k], math.sqrt(vc) * lengths[k],
                      diff * lengths[k], abs(mb - mc) / diff))
    return atoms, means


def _control_table(atoms, means, rwp_body: float, rwp_control: float) -> str:
    """The body against the free-atom control, the bar's own numbers."""
    lines = ["# Acridine form IX: the rigid body against the free-atom control", "",
             f"Rwp {rwp_body:.5f} (body) and {rwp_control:.5f} (control, unrestrained, "
             f"H riding).  Δ = body − control in fractional units times the cell "
             f"edge (a, b or c), in Å.  ratio = |Δ| / √(σ²_control − σ²_body), the "
             f"body's σ on the control's scale; the bar is {CONTROL_BOUND:g}.", "",
             "| atom | axis | Δ·edge (Å) | control esd (Å) | esd of Δ (Å) | ratio |",
             "|---|---|---|---|---|---|"]
    for lab, c, d, ec, ed, r in atoms + means:
        lines.append(f"| {lab} | {c} | {d:+.5f} | {ec:.5f} | {ed:.5f} | {r:.2f} |")
    return "\n".join(lines) + "\n"


def _draw_zoom(result, stem: str) -> None:
    """The strong low-angle peaks, 6.5-12.5°, where the residual sits."""
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}_zoom.png"), two_theta_range=(6.5, 12.5))


def _simulate(ref, result, pattern: rx.PatternData) -> tuple[rx.PatternData, Phase]:
    """y_calc at the deposited coordinates and the converged profile, plus
    Gaussian noise at the deposit's own σ; and the phase it was drawn from."""
    _, cell = _published()
    fitted = ref.fitted_structure.phases[0]
    body = fitted.rigid_bodies[0]
    deposited = _deposited_body(_deposited_phase())
    c = fitted.cell.model_copy(deep=True)
    c.a.value, c.b.value, c.c.value = (cell["length_a"], cell["length_b"], cell["length_c"])
    c.beta.value = cell["angle_beta"]
    truth = place_body_atoms(fitted.model_copy(update={"cell": c, "rigid_bodies": [
        body.model_copy(update={"orientation": deposited.orientation,
                                "origin": deposited.origin})]}))
    s = Structure(phases=[truth])
    model = compile_model(s, ref.fitted_instrument, pattern, mode="rietveld")
    table = ParameterTable(s, ref.fitted_instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    sigma = np.asarray(pattern.sig())
    assert len(y) == len(sigma) == len(pattern.two_theta)
    noisy = y + np.random.default_rng(NOISE_SEED).normal(0.0, sigma)
    return pattern.model_copy(update={"intensity": noisy.tolist()}), truth


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def pattern():
    return rx.read_pattern(FIXTURE)


@pytest.fixture(scope="module")
def real_deposited(pattern):
    ref, result = _fit(_start(_with(_deposited_phase(), _deposited_body(_deposited_phase()),
                                    perturb=False)), pattern)
    _draw(result, "acridine_ix_real_deposited_start")
    _draw_zoom(result, "acridine_ix_real_deposited_start")
    OUT.mkdir(exist_ok=True)
    (OUT / "acridine_ix_deposit_table.md").write_text(
        _deposit_table(ref.fitted_structure.phases[0], result.statistics.rwp), encoding="utf-8")
    return ref, result


@pytest.fixture(scope="module")
def real_perturbed(pattern):
    ref, result = _fit(_start(_with(_deposited_phase(), _deposited_body(_deposited_phase()),
                                    perturb=True)), pattern)
    _draw(result, "acridine_ix_real_perturbed_start")
    return ref, result


@pytest.fixture(scope="module")
def free_control(pattern):
    """The free-atom control: the body's starting atoms with the body taken
    away, so the 14 heavy atoms refine their own coordinates under the same
    data, profile, background and plan, and no restraint holds them."""
    placed = _with(_deposited_phase(), _deposited_body(_deposited_phase()), perturb=False)
    ref, result = _fit(_start(placed.model_copy(update={"rigid_bodies": []})), pattern)
    _draw(result, "acridine_ix_real_free_atom_control")
    _draw_zoom(result, "acridine_ix_real_free_atom_control")
    return ref, result


@pytest.fixture(scope="module")
def simulated(real_deposited, pattern):
    return _simulate(*real_deposited, pattern)


@pytest.fixture(scope="module")
def known_answer(simulated):
    phase = _deposited_phase()
    ref, result = _fit(_start(_with(phase, _deposited_body(phase), perturb=True)), simulated[0])
    _draw(result, "acridine_ix_simulated_deposited_body")
    return ref, result


@pytest.fixture(scope="module")
def hexagon_arm(simulated):
    phase = _deposited_phase()
    ref, result = _fit(_start(_with(phase, _hexagon_body(phase), perturb=True)), simulated[0])
    _draw(result, "acridine_ix_simulated_hexagon_body")
    return ref, result


# --------------------------------------------------------------------- tests
def test_the_deposited_body_reproduces_the_deposited_atoms():
    """The template round trip: a body built from the 14 deposited heavy
    atoms, placed by its own map, puts each back where the CIF has it, so
    the template floor is zero by construction (the hexagons' is 0.064 Å)."""
    phase = _deposited_phase()
    placed = _with(phase, _deposited_body(phase), perturb=False)
    pub, _ = _published()
    worst = max(float(np.abs(xyz - np.asarray(pub[lab][0])).max())
                for lab, (xyz, _) in _heavy(placed).items())
    assert worst < 1e-9, worst


@pytest.mark.slow
@pytest.mark.xdist_group("acridine-ix")
def test_a_perturbed_start_reaches_the_same_minimum(real_deposited, real_perturbed):
    """On the deposited pattern, a start 10° and 0.3 Å off the deposited pose
    reaches the deposited start's minimum, atom for atom."""
    (ref_d, res_d), (ref_p, res_p) = real_deposited, real_perturbed
    assert res_d.status == "converged" and res_p.status == "converged"
    assert res_d.statistics.rwp < 0.07, res_d.statistics.rwp
    m = np.asarray(cartesian_frame(ref_d.fitted_structure.phases[0].cell.lengths_angles()))
    a, b = _heavy(ref_d.fitted_structure.phases[0]), _heavy(ref_p.fitted_structure.phases[0])
    gap = max(float(np.linalg.norm(m @ (a[lab][0] - b[lab][0]))) for lab in HEAVY)
    assert gap <= START_TOL_ANG, gap
    assert abs(res_d.statistics.rwp - res_p.statistics.rwp) < 1e-5


@pytest.mark.slow
@pytest.mark.xdist_group("acridine-ix")
def test_an_intra_body_distance_has_no_esd_and_an_inter_body_one_has_a_full_esd(
        real_deposited):
    """A distance between two atoms of the one body is the template's, so its
    J·Cov·Jᵀ cancels and ``VARIANCE_CANCELLATION_FLOOR`` reports ``None``; a
    contact to another molecule (a symmetry image of the body) moves with the
    pose and the cell, and carries the full-covariance esd."""
    _, result = real_deposited
    rows = result.geometry.distances
    intra = [d for d in rows if d.symmetry_2 == "."]
    inter = [d for d in rows if d.symmetry_2 != "."]
    assert intra and inter
    assert all(d.stderr is None and d.stderr_diagonal is None for d in intra), \
        [(d.atom_1, d.atom_2, d.stderr) for d in intra if d.stderr is not None][:5]
    assert all(d.stderr is not None and d.stderr > 0.0 for d in inter), \
        [(d.atom_1, d.atom_2, d.symmetry_2) for d in inter if not d.stderr][:5]
    # "full" means the covariance's off-diagonals are in it: a fall-back to the
    # diagonal-only esd would pass every line above (Yue, #1416 review)
    assert any(abs(d.stderr / d.stderr_diagonal - 1.0) > 0.01 for d in inter
               if d.stderr_diagonal), "every inter-body esd equals its diagonal-only one"
    heavy = [d for d in inter if d.atom_1 in HEAVY and d.atom_2 in HEAVY]
    assert heavy and all(math.isfinite(d.stderr) for d in heavy)


@pytest.mark.slow
@pytest.mark.xdist_group("acridine-ix")
def test_the_body_agrees_with_the_free_atom_control(real_deposited, free_control):
    """Yue's bar (2026-11-05): the same model with the heavy atoms free,
    unrestrained, refined under the same data, profile, background and plan,
    lands where the body does.  Every heavy-atom coordinate and the
    molecule's mean position along each axis agree within ``CONTROL_BOUND``
    esds of their difference.  The mean along c is the one the 2026-10-27
    comparison with the deposit read as the body's own shift; the table goes
    to ``tests/output/acridine_ix_control_table.md``."""
    (ref_b, res_b), (ref_c, res_c) = real_deposited, free_control
    assert res_b.status == "converged" and res_c.status == "converged"
    assert res_c.restraints is None or not res_c.restraints.rows, "the control is unrestrained"
    # the control refined every heavy coordinate: each carries an esd larger
    # than the body's, so the difference's esd is real
    hb, hc = _heavy(ref_b.fitted_structure.phases[0]), _heavy(ref_c.fitted_structure.phases[0])
    assert all(hb[lab][1][k] is not None and hc[lab][1][k] is not None
               and hc[lab][1][k] > hb[lab][1][k] for lab in HEAVY for k in range(3))
    atoms, means = _against_control(real_deposited, free_control)
    OUT.mkdir(exist_ok=True)
    (OUT / "acridine_ix_control_table.md").write_text(
        _control_table(atoms, means, res_b.statistics.rwp, res_c.statistics.rwp),
        encoding="utf-8")
    worst = max(atoms + means, key=lambda r: r[-1])
    assert worst[-1] <= CONTROL_BOUND, worst


@pytest.mark.slow
@pytest.mark.xdist_group("acridine-ix")
def test_a_simulated_known_answer_is_recovered_from_the_perturbed_start(
        simulated, known_answer):
    """The pattern the forward model draws from the deposited coordinates at
    the real fit's converged profile, with Gaussian noise at the deposit's σ,
    refitted from the perturbed start with the default profile seeds: every
    heavy-atom coordinate returns within ``KNOWN_ANSWER_BOUND`` of its own
    rietx esd."""
    _, truth = simulated
    pub, _ = _published()
    planted = max(float(np.abs(xyz - np.asarray(pub[lab][0])).max())
                  for lab, (xyz, _) in _heavy(truth).items())
    assert planted < 1e-9, planted          # the truth is the deposit
    ref, result = known_answer
    assert result.status == "converged"
    worst = max(max(r) for r in _ratios(ref.fitted_structure.phases[0]).values())
    assert worst <= KNOWN_ANSWER_BOUND, worst


@pytest.mark.slow
@pytest.mark.xdist_group("acridine-ix")
def test_a_regular_hexagon_template_fails_the_known_answer_bound(hexagon_arm):
    """The positive arm: the same pattern, plan and start with an idealised
    template (regular hexagons, 0.064 Å RMS from the deposit) cannot place
    its atoms within ``KNOWN_ANSWER_BOUND`` esds of the deposited ones, so
    the bound above is tight enough to see a wrong template."""
    ref, result = hexagon_arm
    assert result.status == "converged"
    worst = max(max(r) for r in _ratios(ref.fitted_structure.phases[0]).values())
    assert worst > KNOWN_ANSWER_BOUND, worst
