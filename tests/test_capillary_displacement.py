"""Capillary sample displacement, McCusker et al. (1999) §5 eq (4) — WP-1073.

Three things are checked, and only the first is about the formula.

**The expression, against a ray trace rather than against the paper.** Eq (4)
is printed as (x·sin2θ − y·cos2θ)/R with no figure, and the letters do not
travel: other codes pair the letter x with the *other* term.  So the test that
matters is not "does the code transcribe the paper" but "does the shift equal
the angle a displaced capillary actually produces", and that is answered by
intersecting the diffracted ray with the detector circle exactly and reading
the angle at the goniometer centre.  Nothing is shared between that and the
implementation but the geometry itself — the WP-0501 lesson (a transcribed
constant with two digits swapped survived every comparison against its own
source) applied to a sign convention.

**Recovery, on a pattern that genuinely carries the displacement** — the
offsets go into the specimen the data is simulated from, not into a starting
model, so a refinement has to find them rather than merely stay where it was
put.  Both axes at once, because either alone is a weaker claim than the pair:
{1, sin2θ, cos2θ} is a near-degenerate trio at short range and the point is
that a wide scan separates it.

**Real 11-BM data**, where the WP's own premise did not survive
measurement.  It expected a *null* test — the paper says a crystal analyser
eliminates displacement error, so 11-BM should recover x, y ≈ 0.  It does not.
Over NAC's certified 2-24° range the three positional shapes are degenerate
(unit-column Gram eigenvalue 1.6e-5), so the fit slides along the null
direction to +4.86 and +2.12 mm with esds of 2.5 and 0.9 mm — while Rwp
*improves* and the cell leaves its acceptance band by 5111 ppm, with an esd
of 2544 ppm that says so (1.10.0).  Until WP-2002 (2026-10-20) a ±1 mm default bound
stopped the walk at 1097 ppm, a prior that the mount is aligned which held
here, with the same esd.  What the last two tests assert is therefore the sharper claim: on
this instrument the correction must not be refined, and the package says so
in the channels that can (the cell's esd, HIGH_CORRELATION, FLAT_DIRECTION)
rather than in the one that cannot (Rwp).

Those two are **not** marked ``slow`` even though they read a real dataset.
The mark exists for the acceptance suites, whose fits cost minutes; both NAC
fits here take 2.9 s together, and they skip cleanly where the file is
absent, so the fast gate is where this evidence is worth having.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.corrections import capillary_displacement_shift_deg
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import CAPILLARY_OFFSETS, Geometry, Instrument
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import RefinementPlan, Stage

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"

#: a laboratory capillary diffractometer's circle
RADIUS_MM = 200.0
ALONG_PATH = f"instrument.geometry.{CAPILLARY_OFFSETS[0]}"
ACROSS_PATH = f"instrument.geometry.{CAPILLARY_OFFSETS[1]}"


# ----------------------------------------------------------------------
# the expression
# ----------------------------------------------------------------------
def _ray_traced_shift_deg(two_theta_deg: np.ndarray, along_mm: float,
                          across_mm: float, radius_mm: float) -> np.ndarray:
    """The apparent 2θ of a displaced source point, computed exactly.

    The diffracting volume sits at ``d`` instead of the origin and emits along
    the true Bragg direction ``n̂``; the detector records where that ray meets
    the circle of radius R, and the angle it reports is the angle of *that
    point* seen from the centre.  Solving |d + t·n̂| = R for t > 0 is a
    quadratic with no approximation in it, which is the point: eq (4) is the
    first-order expansion of this, so agreement to O(|d|/R)² is evidence that
    both the shape and the signs are right.
    """
    tt = np.radians(np.asarray(two_theta_deg, dtype=np.float64))
    d = np.array([along_mm, across_mm])
    out = np.empty_like(tt)
    for i, angle in enumerate(tt):
        n = np.array([np.cos(angle), np.sin(angle)])
        # |d + t n|² = R²  ⇒  t² + 2(d·n)t + (|d|² − R²) = 0
        b = float(d @ n)
        t = -b + np.sqrt(b * b - (float(d @ d) - radius_mm ** 2))
        p = d + t * n
        out[i] = np.degrees(np.arctan2(p[1], p[0])) - np.degrees(angle)
    return out


@pytest.mark.parametrize("along,across", [(0.2, 0.0), (0.0, 0.2), (0.15, -0.10)])
def test_eq4_is_the_ray_trace_to_first_order(along, across):
    """The two must agree to second order in |d|/R, and disagree beyond it.

    The second assertion is what makes the first mean something: an expression
    that agreed to machine precision would not be a linearisation at all, and
    a sign error would show up here as a *first*-order gap.
    """
    tt = np.linspace(5.0, 160.0, 311)
    linear = capillary_displacement_shift_deg(tt, along, across, RADIUS_MM)
    exact = _ray_traced_shift_deg(tt, along, across, RADIUS_MM)

    d_over_r = np.hypot(along, across) / RADIUS_MM
    scale = np.degrees(d_over_r)
    err = np.max(np.abs(linear - exact))
    assert err < 3.0 * scale * d_over_r, f"gap {err:.3e}° is not second order"
    assert err > 0.0, "an exact match would mean this is not a linearisation"


def test_the_signatures_are_the_documented_ones():
    """Physics, not letters: which axis carries which shape, and where it dies.

    Read as the docstring's own claims, one assertion each — an along-beam
    offset is invisible in the forward and back directions and largest at 90°;
    an across-beam one is largest at 0 with the value b/R and reverses past
    90°.  This is the assertion that would have caught the paper's letters
    being taken at face value.
    """
    along = capillary_displacement_shift_deg(
        np.array([0.0, 90.0, 180.0]), 0.1, 0.0, RADIUS_MM)
    assert along[0] == pytest.approx(0.0, abs=1e-12)
    assert along[2] == pytest.approx(0.0, abs=1e-12)
    assert abs(along[1]) == pytest.approx(np.degrees(0.1 / RADIUS_MM))

    across = capillary_displacement_shift_deg(
        np.array([0.0, 90.0, 180.0]), 0.0, 0.1, RADIUS_MM)
    assert across[0] == pytest.approx(np.degrees(0.1 / RADIUS_MM))
    assert across[1] == pytest.approx(0.0, abs=1e-12)
    assert across[2] == pytest.approx(-np.degrees(0.1 / RADIUS_MM))


def _trio_min_eigenvalue(two_theta: np.ndarray) -> float:
    """Smallest eigenvalue of the unit-column Gram of {1, sin2θ, cos2θ}.

    The same statistic ``optimize.identifiability.soft_modes`` reads, on the
    three positional columns alone: dimensionless, 1 for orthogonal, 0 for
    exactly degenerate.  Pairwise |cos| is the wrong number here — sin 2θ never
    changes sign over 0-180°, so it sits at |cos| ≈ 0.94 against a constant on
    *any* range while still being separable; what separates the trio is the
    three-way conditioning, not any pair.
    """
    cols = np.vstack([
        np.ones_like(two_theta),
        capillary_displacement_shift_deg(two_theta, 1.0, 0.0, RADIUS_MM),
        capillary_displacement_shift_deg(two_theta, 0.0, 1.0, RADIUS_MM),
    ])
    cols /= np.linalg.norm(cols, axis=1, keepdims=True)
    return float(np.linalg.eigvalsh(cols @ cols.T).min())


def test_the_range_decides_whether_the_three_shapes_separate():
    """A comparison of two measurements, not a threshold.

    The trio is linearly independent at any range — the claim worth making is
    that a wide scan separates it by orders of magnitude more than a short
    low-angle one, which is what §12.3's "refine the 2θ correction first"
    depends on and what the identifiability layer reports when it does not
    hold.  Measured here: 5.2e-2 over 5-160°, 1.1e-5 over 5-25°, a factor of
    ~4600.
    """
    wide = _trio_min_eigenvalue(np.linspace(5.0, 160.0, 311))
    short = _trio_min_eigenvalue(np.linspace(5.0, 25.0, 101))
    assert wide > 1e-2, f"a full range should condition the trio ({wide:.2e})"
    assert short < 1e-4, f"a short low-angle range must not ({short:.2e})"
    assert wide / short > 100.0


# ----------------------------------------------------------------------
# what the schema refuses
# ----------------------------------------------------------------------
def test_an_offset_without_a_radius_is_refused_by_name():
    """eq (4) divides by R, so a value with no R is a model that cannot be
    evaluated — and the message has to name the missing field, not the
    division."""
    with pytest.raises(ValueError, match="goniometer_radius_mm"):
        Geometry(kind="debye_scherrer",
                 capillary_offset_along_beam=Parameter(value=0.1, min=-1, max=1))
    with pytest.raises(ValueError, match="goniometer_radius_mm"):
        Geometry(kind="debye_scherrer",
                 capillary_offset_across_beam=Parameter(value=0.0, min=-1, max=1,
                                                        vary=True))


def test_an_offset_on_a_flat_specimen_is_refused():
    with pytest.raises(ValueError, match="debye_scherrer"):
        Geometry(kind="bragg_brentano", goniometer_radius_mm=RADIUS_MM,
                 capillary_offset_along_beam=Parameter(value=0.1, min=-1, max=1))


def test_freeing_an_offset_after_construction_is_refused_by_the_table():
    """The validator cannot see a ``vary`` set later, and ParameterTable is the
    last gate before a solve.  Refused rather than silently held: an aberration
    held at zero reports as a *measured* zero, which is the opposite claim."""
    ins = Instrument.debye_scherrer(wavelength=1.0)
    getattr(ins.geometry, CAPILLARY_OFFSETS[0]).vary = True
    with pytest.raises(ValueError, match="goniometer_radius_mm"):
        ParameterTable(_rutile(), ins)


def test_the_offsets_are_held_on_a_flat_plate_and_free_on_a_capillary():
    flat = ParameterTable(_rutile(), rx.Instrument.bragg_brentano())
    assert not flat.set_vary([ALONG_PATH], True)
    assert not flat.set_vary([ACROSS_PATH], True)

    cap = ParameterTable(_rutile(), Instrument.debye_scherrer(
        wavelength=1.5406, goniometer_radius_mm=RADIUS_MM))
    assert cap.set_vary([ALONG_PATH], True)
    assert cap.set_vary([ACROSS_PATH], True)


def test_a_default_capillary_instrument_is_unchanged_by_this_correction():
    """The preset's historical meaning: no radius, no offsets, exactly the
    peak positions a pre-WP-1073 fit produced.  An additive correction that
    moved a default would be a silent refit of every stored project."""
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    assert ins.geometry.goniometer_radius_mm is None
    structure = _rutile()
    tt = np.arange(15.0, 90.0, 0.02)
    empty = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, empty, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))

    ins.geometry.goniometer_radius_mm = RADIUS_MM      # declared, still at zero
    model_r = compile_model(structure, ins, empty, mode="rietveld")
    y_r = model_r.evaluate(ParameterTable(structure, ins).decode(table.x0()))
    assert np.array_equal(y, y_r), "a declared radius alone must move nothing"


# ----------------------------------------------------------------------
# recovery on a pattern that carries the displacement
# ----------------------------------------------------------------------
def _rutile() -> Structure:
    return Structure(phases=[Phase(
        name="rutile", space_group="P42/mnm",
        cell=Cell(a=Parameter(value=4.5937, min=0.1),
                  b=Parameter(value=4.5937, min=0.1),
                  c=Parameter(value=2.9587, min=0.1),
                  alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                  gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Ti", species="Ti", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.5, min=0.0, max=25.0)),
               Atom(label="O", species="O", x=Parameter(value=0.3053),
                    y=Parameter(value=0.3053), z=Parameter(value=0.0),
                    biso=Parameter(value=0.6, min=0.0, max=25.0))],
        scale=Parameter(value=8e-3, min=0.0, transform="softplus"))])


def _capillary_instrument(*, radius: float | None = RADIUS_MM,
                          along: float = 0.0, across: float = 0.0
                          ) -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=1.5406,
                                    goniometer_radius_mm=radius)
    ins.source.dispersion = None      # declined, not inherited (CLAUDE.md)
    ins.profile.w.value = 8e-3
    ins.profile.x.value = 4e-3
    getattr(ins.geometry, CAPILLARY_OFFSETS[0]).value = along
    getattr(ins.geometry, CAPILLARY_OFFSETS[1]).value = across
    return ins


def _simulate(along: float, across: float, *, lo=8.0, hi=140.0, seed=7
              ) -> PatternData:
    """A pattern from a specimen that is genuinely off centre."""
    structure = _rutile()
    ins = _capillary_instrument(along=along, across=across)
    tt = np.arange(lo, hi, 0.02)
    empty = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, empty, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 60.0
    rng = np.random.default_rng(seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0)).astype(float)
                                    .tolist())


def _recovery_plan() -> RefinementPlan:
    return RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        # all three positional freedoms in one stage: freeing the zero shift
        # first would let it absorb whatever of the offsets it can imitate and
        # then hold it, which measures the stage order rather than the physics
        Stage("position", ["instrument.zero_shift", ALONG_PATH, ACROSS_PATH]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile", ["instrument.profile.w", "instrument.profile.x"]),
    ])


ALONG_TRUE, ACROSS_TRUE = 0.30, -0.20


def test_an_injected_displacement_is_recovered_on_both_axes():
    """Both offsets back to within 10 µm, over a scan wide enough to separate
    them from the zero shift — and the cell must survive it, since a
    displacement absorbed into the cell instead is the failure that matters."""
    data = _simulate(ALONG_TRUE, ACROSS_TRUE)
    ref = rx.Refinement(_rutile(), _capillary_instrument())
    result = ref.fit(data, plan=_recovery_plan())

    fitted = {p.path: p for p in result.parameters}
    assert fitted[ALONG_PATH].value == pytest.approx(ALONG_TRUE, abs=0.01)
    assert fitted[ACROSS_PATH].value == pytest.approx(ACROSS_TRUE, abs=0.01)
    # the truth cell, undistorted: with the offsets held this fit puts the
    # displacement into `a` instead (asserted in the next test)
    cell = ref.fitted_structure.phases[0].cell
    assert cell.a.value == pytest.approx(4.5937, abs=2e-4)
    assert cell.c.value == pytest.approx(2.9587, abs=2e-4)

    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result
    plot_result(result, path=str(OUT / "capillary_displacement_corrected.png"))
    plot_result(result, path=str(OUT / "capillary_displacement_corrected_zoom.png"),
                two_theta_range=(8.0, 40.0))


def test_neglecting_it_bends_the_cell_and_only_a_rung_names_the_cause():
    """What this correction ships with, and it is not an Rwp comparison.

    Deny the offsets and the damage does not stay where it was made: the zero
    shift and the cell between them imitate most of eq (4)'s shift, so the
    converged fit reports **no position cause at all** — and the cell is
    −290 ppm out.  That is WP-1058's rule measured on a new correction: a plan
    absorbs an error it cannot free into whatever it can and converges
    suggesting nothing, while an earlier stage named it.  Here the ``zero``
    rung names ``refine_capillary_offset_along_beam`` at 0.66 confidence and
    the final report names nothing, so the trajectory is the evidence and the
    last state is the least informative one.

    Read the two halves together: the assertion that the *converged* report
    stays silent is not a defect being pinned — it is why ``stage_reports`` is
    the thing to look at, and it would be a defect if this test only checked
    the end.
    """
    data = _simulate(ALONG_TRUE, ACROSS_TRUE)
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile", ["instrument.profile.w", "instrument.profile.x"]),
    ])
    ref = rx.Refinement(_rutile(), _capillary_instrument())
    result = ref.fit(data, plan=plan, stage_reports=True)
    report = ref.report()

    cell = ref.fitted_structure.phases[0].cell
    bias = abs(cell.a.value - 4.5937) / 4.5937
    assert bias > 2e-4, f"the neglected displacement left the cell alone ({bias:.1e})"

    # the geometry's own vocabulary, whatever the fit went on to conclude
    position = next((t for t in report.trends if t.observable == "position"), None)
    assert position is not None and position.templates
    names = {t.name for t in position.templates}
    assert "cos_theta" not in names, "a flat-plate aberration a capillary lacks"
    assert {"sin_2theta", "cos_2theta"} <= names

    final_kinds = {a.kind for a in report.suggested_actions}
    assert not final_kinds & {"refine_capillary_offset_along_beam",
                              "refine_capillary_offset_across_beam",
                              "refine_zero_shift", "refine_cell"}, (
        "the converged report named a position cause — if this starts passing "
        "for real, the rung-versus-endpoint story below is no longer the "
        "reason to keep stage_reports on")

    rungs = {r.stage: {a.kind for a in r.actions} for r in ref.stage_reports_}
    assert rungs["zero"] & {"refine_capillary_offset_along_beam",
                            "refine_capillary_offset_across_beam"}, rungs
    # …and never the flat-plate pair, on any rung
    for stage, kinds in rungs.items():
        assert not kinds & {"refine_sample_displacement",
                            "refine_sample_transparency"}, stage

    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result
    plot_result(result, path=str(OUT / "capillary_displacement_neglected.png"))
    plot_result(result, path=str(OUT / "capillary_displacement_neglected_zoom.png"),
                two_theta_range=(8.0, 40.0))


# ----------------------------------------------------------------------
# real synchrotron data: what "eliminated by CA geometry" actually licenses
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def nac_pair():
    """The same simplified NAC protocol run with and without the offsets.

    Simplified deliberately — single phase, ``mccusker_default``, no CaF₂ —
    because the claim here is a *difference between two runs*, so the protocol
    only has to be the same on both sides, and the acceptance suite's own
    two-phase fit stays the authority for NAC's absolute numbers.  R = 1000 mm
    is a stated assumption: the ``.prm`` gives no diffraction circle, only x/R
    is observable, so an R off by a factor scales the fitted millimetres by
    that factor and moves no angle.
    """
    from tests.test_acceptance_nac import LIMITS, build_nac_inputs

    data, structure, ins = build_nac_inputs()      # skips if the file is absent
    assert ins.geometry.kind == "debye_scherrer"

    held = rx.Refinement(structure.model_copy(deep=True), ins.model_copy(deep=True))
    r_held = held.fit(data, plan=rx.RefinementPlan.mccusker_default(),
                      two_theta_limits=LIMITS)

    ins_free = ins.model_copy(deep=True)
    ins_free.geometry.goniometer_radius_mm = 1000.0
    plan = rx.RefinementPlan.mccusker_default()
    # with the zero shift, not after it: the three are one block or none
    plan.stages.append(Stage("capillary_displacement",
                             ["instrument.zero_shift", ALONG_PATH, ACROSS_PATH]))
    free = rx.Refinement(structure.model_copy(deep=True), ins_free)
    r_free = free.fit(data, plan=plan, two_theta_limits=LIMITS)

    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result
    plot_result(r_held, path=str(OUT / "capillary_nac_offsets_held.png"))
    plot_result(r_free, path=str(OUT / "capillary_nac_offsets_free.png"))
    return (held, r_held), (free, r_free)


@pytest.mark.xdist_group("capillary-displacement")
def test_11bm_is_where_this_correction_must_not_be_refined(nac_pair):
    """The paper's synchrotron clause is about the *instrument*, not a licence.

    McCusker §5 says sample-displacement error is eliminated by crystal-analyser
    geometry, and the WP that planned this correction read that as "11-BM is the
    null test: recover x, y ≈ 0".  Measured, it is not a null test — it is a
    **degeneracy** test, and the answer is sharper.  11-BM NAC's certified
    protocol runs 2-24° 2θ, where {1, sin2θ, cos2θ} has a unit-column Gram
    eigenvalue of 1.6e-5, so the fit does not return zero: it slides along the
    null direction to a = +4.86 mm and b = +2.12 mm, two and a half esds out,
    numbers that read as measured and are not.

    Asserted here as the *machinery reporting it*, because that is the part a
    consumer relies on, and since WP-2002 removed the ±1 mm default bound
    (2026-10-20) no bound is there to stop the walk or to report it:
    ``FLAT_DIRECTION`` names the cell with an offset, ``HIGH_CORRELATION``
    names an offset, and the cell's esd is wide enough to cover how far it
    walked from the fit that held the offsets.
    """
    (held, r_held), (free, r_free) = nac_pair
    codes = {d.code for d in r_free.diagnostics}
    flat = [set(d.where) for d in r_free.diagnostics if d.code == "FLAT_DIRECTION"]
    assert any("phases.0.cell.a" in w and (ALONG_PATH in w or ACROSS_PATH in w)
               for w in flat), flat
    assert "HIGH_CORRELATION" in codes
    # the cell's own esd carries the degeneracy: the walk from the held fit is
    # inside three of it (measured 2.0 esd, 2026-10-20)
    a_held = held.fitted_structure.phases[0].cell.a.value
    cell = r_free.parameter("phases.0.cell.a")
    assert abs(cell.value - a_held) < 3 * cell.stderr, (cell.value, cell.stderr, a_held)
    pairs = {(c.path_a, c.path_b) for c in r_free.identifiability.top_correlations
             if abs(c.rho) > 0.99}
    assert any(ALONG_PATH in p or ACROSS_PATH in p for p in pairs), pairs


@pytest.mark.xdist_group("capillary-displacement")
def test_on_11bm_rwp_improves_and_the_cell_leaves_its_band(nac_pair):
    """The invariant, on the correction that ships with this WP.

    Freeing eq (4) over 2-24° takes Rwp *down* — 0.14010 → 0.13784, a 1.6 %
    improvement — while the cell walks out of the acceptance band, 10.2512 to
    10.1986 Å, which is 5111 ppm and 26× the ±2e-3 Å the NAC acceptance
    allows (1097 ppm while a ±1 mm default bound stopped the offsets, until
    WP-2002).  A session judging this correction by Δ Rwp would have accepted
    it here and shipped a cell wrong in the third digit.

    So the assertion is *both directions at once*: it is the improvement
    together with the damage that makes the point, and either alone would be
    the wrong lesson.
    """
    (held, r_held), (free, r_free) = nac_pair
    assert r_free.statistics.rwp < r_held.statistics.rwp, (
        "if Rwp stops improving here, the measured trap has changed and the "
        "prose above needs re-measuring, not this bar relaxing")
    a_held = held.fitted_structure.phases[0].cell.a.value
    a_free = free.fitted_structure.phases[0].cell.a.value
    assert abs(a_held - 10.2510) < 2e-3, a_held        # the acceptance band
    assert abs(a_free - 10.2510) > 2e-3, (
        f"the degenerate fit stayed in band ({a_free:.5f}) — then this dataset "
        f"no longer demonstrates the trap")
    assert abs(a_free - a_held) / a_held > 5e-4
