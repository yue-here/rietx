"""A tick sits where the forward model draws its peak (WP-1908).

``RefinementResult.ticks`` placed each reflection at its Bragg angle plus the
zero shift and nothing else.  The forward model also applies the geometry's own
position shift: sample displacement and transparency on a flat plate, the two
capillary offsets on a capillary.  A fit with a refined displacement therefore
drew its ticks off its own peaks, by 2·s·cosθ/R, while the calculated curve
sat on the data.  Measured on IUCr CPD sample 1c under the acceptance suite's
``qpa_plan``, the fit's displacement refined to -0.81 mm and every tick sat
0.50° from the peak it labelled.

The oracle here is the calculated curve, never the shift formula.  A tick is
right when it lies at the apex of the peak the model drew, so a test that
re-derived the shift from the same expression would certify the shift and not
the tick.  Peaks are noise-free and narrow, so the apex of a three-point
parabola on the 0.01 deg grid is good to well under the 0.01 deg bar.

Three builders owe the same answer and each has a test: the single-histogram
result (``refine._build_result``), the joint runner's
(``multi.MultiHistogramRefinement._build_result``, through
``refine._tick_rows``) and the live view's
(``viz.snapshot.stage_ticks``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.symmetry import reflection_label_row
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import CAPILLARY_OFFSETS, Instrument
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import RefinementPlan, Stage
from rietx.viz.snapshot import TWO_THETA_DECIMALS, stage_ticks

OUT = Path(__file__).parent / "output"

#: the bar the WP states: a tick within a hundredth of a degree of its peak
BAR_DEG = 0.01
DISPLACEMENT_PATH = "instrument.geometry.sample_displacement"
TT_GRID = np.arange(20.0, 120.0, 0.01)


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


def _flat_plate(*, radiation: str = "CuKa1", displacement: float = 0.0,
                transparency: float = 0.0) -> Instrument:
    ins = rx.Instrument.bragg_brentano(radiation=radiation)
    ins.source.dispersion = None      # declined, not inherited (CLAUDE.md)
    ins.profile.w.value = 4e-3
    ins.profile.x.value = 2e-3
    ins.geometry.sample_displacement.value = displacement
    ins.geometry.sample_transparency.value = transparency
    return ins


def _capillary(along: float, across: float) -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=1.5406,
                                    goniometer_radius_mm=200.0)
    ins.source.dispersion = None
    ins.profile.w.value = 4e-3
    ins.profile.x.value = 2e-3
    getattr(ins.geometry, CAPILLARY_OFFSETS[0]).value = along
    getattr(ins.geometry, CAPILLARY_OFFSETS[1]).value = across
    return ins


def _simulate(ins: Instrument, structure: Structure | None = None
              ) -> PatternData:
    """A noise-free pattern drawn by the forward model itself, on a flat floor."""
    structure = structure or _rutile()
    empty = PatternData(two_theta=TT_GRID.tolist(),
                        intensity=np.zeros_like(TT_GRID).tolist())
    model = compile_model(structure, ins, empty, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = np.asarray(model.evaluate(table.decode(table.x0()))) + 50.0
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _apex(tt: np.ndarray, y: np.ndarray, centre: float, half: float):
    """The top of the peak nearest ``centre``, parabola through three points."""
    window = (tt > centre - half) & (tt < centre + half)
    if window.sum() < 5:
        return None
    i = int(np.argmax(np.where(window, y, -np.inf)))
    if i == 0 or i == len(tt) - 1:
        return None
    y0, y1, y2 = y[i - 1], y[i], y[i + 1]
    curvature = y0 - 2.0 * y1 + y2
    step = tt[1] - tt[0]
    return tt[i] + (0.5 * (y0 - y2) / curvature * step if curvature else 0.0)


def _tick_offsets(tt, y_calc, ticks, *, half=0.25, isolation=0.3,
                  lo=None, hi=None, floor=60.0):
    """Apex minus tick, for every tick that sits alone and on a visible peak.

    A tick is judged only when no other tick lies within ``isolation`` of it,
    so a neighbour's apex cannot be mistaken for its own, and only when the
    calculated curve rises ``floor`` above the 50-count floor there, so a
    forbidden-by-intensity reflection with no peak is not asked for one.
    """
    tt, y_calc, ticks = (np.asarray(v, dtype=float) for v in (tt, y_calc, ticks))
    out = []
    for k, c in enumerate(ticks):
        if (lo is not None and c < lo) or (hi is not None and c > hi):
            continue
        # a phase with one tick has no neighbour to be isolated from
        if ticks.size > 1 and np.min(np.abs(np.delete(ticks, k) - c)) < isolation:
            continue
        apex = _apex(tt, y_calc, c, half)
        if apex is None:
            continue
        if y_calc[np.argmin(np.abs(tt - apex))] < 50.0 + floor:
            continue
        out.append((c, apex - c))
    return np.array(out)


def _first_phase_ticks(result) -> list[float]:
    return result.ticks["rutile"]


def _zoom_about(rows: np.ndarray, half: float = 0.7) -> tuple[float, float]:
    """A window on the middle judged tick, wide enough to see peak and tick."""
    centre = float(rows[len(rows) // 2, 0])
    return centre - half, centre + half


def _plot_with_zoom(result, stem: str, zoom: tuple[float, float]) -> None:
    """Save the obs/calc/diff panel and a zoom on one peak with its tick."""
    import matplotlib.pyplot as plt

    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"{stem}.png"))
    result.plot(path=str(OUT / f"{stem}_zoom.png"), two_theta_range=zoom)
    plt.close("all")


# ----------------------------------------------------------------------
# the acceptance case: a fitted 0.5 mm displacement
# ----------------------------------------------------------------------
def _fit_displaced(radiation: str, truth_mm: float = 0.5):
    data = _simulate(_flat_plate(radiation=radiation, displacement=truth_mm))
    ref = rx.Refinement(_rutile(), _flat_plate(radiation=radiation))
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("displacement", [DISPLACEMENT_PATH]),
        Stage("cell", ["phases.*.cell.*"]),
    ])
    return ref.fit(data, plan=plan)


def test_every_tick_lies_on_its_peak_after_a_fitted_displacement():
    """The WP's acceptance, on a pattern whose displacement is 0.5 mm.

    Before the fix every tick sat 0.14° (at 117°) to 0.26° (at 27°) above its
    peak: the displacement shift is -2·s·cosθ/R, and the ticks lacked it.
    """
    result = _fit_displaced("CuKa1")
    fitted = {p.path: p.value for p in result.parameters}
    assert fitted[DISPLACEMENT_PATH] == pytest.approx(0.5, abs=1e-3)

    rows = _tick_offsets(result.two_theta, result.y_calc,
                         _first_phase_ticks(result), half=0.4, isolation=0.9)
    assert len(rows) >= 15, "too few isolated peaks for the claim to mean much"
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, (
        f"a tick sits {worst:.4f} deg from its peak (bar {BAR_DEG}); the "
        f"uncorrected offset on this case is 0.14-0.26 deg")
    # and they cover the whole range, not only where the shift is small
    assert rows[:, 0].min() < 40.0 and rows[:, 0].max() > 100.0

    _plot_with_zoom(result, "tick_positions_displaced",
                    (26.5, 28.0))


def test_a_kalpha2_tick_takes_its_own_lines_shift():
    """Each emission line has its own θ, so each tick has its own shift.

    A doublet resolves above 100° (0.46° apart at 117°), so there each line's
    peak can be found and its tick compared with it.  Two reflections resolve
    on this pattern, so four ticks: both lines of each are judged.
    """
    result = _fit_displaced("CuKa")
    rows = _tick_offsets(result.two_theta, result.y_calc,
                         _first_phase_ticks(result), half=0.25,
                         isolation=0.3, lo=100.0, hi=120.0)
    assert len(rows) >= 4, f"{len(rows)} resolved lines is too few to cover both"
    # the pairs really are Kα1/Kα2 of one reflection, 0.4-0.5° apart
    gaps = np.diff(rows[:, 0])
    assert np.any((gaps > 0.4) & (gaps < 0.5))
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, f"a tick sits {worst:.4f} deg from its line's peak"
    # both doublets of the judged range, each line with its own tick
    _plot_with_zoom(result, "tick_positions_kalpha2", (116.0, 118.4))


# ----------------------------------------------------------------------
# every geometry's own shift, by the live view's builder and the result's
# ----------------------------------------------------------------------
GEOMETRIES = [
    pytest.param(lambda: _flat_plate(displacement=0.5), id="displacement"),
    pytest.param(lambda: _flat_plate(transparency=0.004), id="transparency"),
    pytest.param(lambda: _capillary(0.4, -0.3), id="capillary"),
]


@pytest.mark.parametrize("make_instrument", GEOMETRIES)
def test_the_live_views_ticks_follow_every_geometry(make_instrument):
    """``stage_ticks`` is the third builder, so it is held to the same oracle.

    No fit: the model is evaluated at the values it was built with, which is
    exactly the picture ``plot_pattern(model=...)`` draws before any fit.
    """
    ins = make_instrument()
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    y_calc = np.asarray(model.evaluate(values)) + 50.0
    ticks = stage_ticks(model, values)["phase 0"]["two_theta"]

    rows = _tick_offsets(model.tt, y_calc, ticks, half=0.5, isolation=1.0)
    assert len(rows) >= 10
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, f"a live-view tick sits {worst:.4f} deg from its peak"


@pytest.mark.parametrize("make_instrument", GEOMETRIES)
def test_a_result_places_its_ticks_by_every_geometry(make_instrument, request):
    """The result's builder, on the geometries a plan can leave nonzero.

    The fit frees only the scale and background, so the geometry stays at the
    value it was declared with and the ticks must carry it from there.
    """
    ins = make_instrument()
    data = _simulate(ins)
    plan = RefinementPlan(stages=[Stage(
        "scale_bkg", ["phases.*.scale", "instrument.background.*"])])
    result = rx.Refinement(_rutile(), ins).fit(data, plan=plan)

    rows = _tick_offsets(result.two_theta, result.y_calc,
                         _first_phase_ticks(result), half=0.5, isolation=1.0)
    assert len(rows) >= 10
    worst = float(np.max(np.abs(rows[:, 1])))
    assert worst < BAR_DEG, f"a result tick sits {worst:.4f} deg from its peak"
    _plot_with_zoom(result, f"tick_positions_{request.node.callspec.id}",
                    _zoom_about(rows))


# ----------------------------------------------------------------------
# the joint runner's own builder
# ----------------------------------------------------------------------
def test_the_joint_runners_ticks_follow_each_histograms_displacement():
    """``multi`` keeps its own tick builder, so it owes the same position.

    Two histograms of one specimen carrying different displacements: a tick
    list shared between them, or one that read the wrong histogram's shift,
    would be off by the difference.
    """
    truths = (0.5, -0.3)
    patterns = [_simulate(_flat_plate(displacement=s)) for s in truths]
    instruments = [_flat_plate(displacement=s) for s in truths]
    plan = RefinementPlan(stages=[Stage(
        "scale_bkg", ["phases.*.scale", "instrument.background.*"])])
    result = rx.MultiHistogramRefinement(_rutile(), instruments).fit(
        patterns, plan=plan)

    for h, hist in enumerate(result.histograms):
        rows = _tick_offsets(hist.two_theta, hist.y_calc,
                             hist.ticks["rutile"], half=0.4, isolation=0.9)
        assert len(rows) >= 10, h
        worst = float(np.max(np.abs(rows[:, 1])))
        assert worst < BAR_DEG, (
            f"histogram {h}: a tick sits {worst:.4f} deg from its peak")
        _plot_with_zoom(result.for_histogram(h), f"tick_positions_joint_{h}",
                        _zoom_about(rows))


# ----------------------------------------------------------------------
# what the fix leaves alone
# ----------------------------------------------------------------------
def test_a_zero_displacement_leaves_the_ticks_at_bragg_plus_zero():
    """With no geometry shift the new method must reduce to the old sum.

    An additive correction that moved a default would be a silent change to
    every stored project's ticks.
    """
    ins = _flat_plate()
    ins.zero_shift.value = 0.03
    structure = _rutile()
    data = _simulate(ins)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    bragg = cp.reflections.two_theta(cell, model.line_wavelengths[0])

    # the unrounded walk, against an independent sum
    pos, _ = model.reflection_positions(0, values)
    assert np.allclose(pos, bragg + 0.03, rtol=0.0, atol=1e-12, equal_nan=True)

    # and what the live view prints is that sum rounded to its own decimals,
    # so the expectation carries the same half-unit of rounding the builder does
    ticks = stage_ticks(model, values, max_per_phase=10**9)["phase 0"]["two_theta"]
    expected = np.sort(bragg[np.isfinite(bragg)] + 0.03)
    half_unit = 0.5 * 10.0 ** -TWO_THETA_DECIMALS
    assert len(ticks) == len(expected)
    assert np.allclose(ticks, expected, rtol=0.0, atol=half_unit + 1e-12)


def test_the_three_builders_share_one_walk_and_pair_positions_with_indices():
    """``reflection_positions`` is the walk, and ticks and indices stay paired.

    A doublet puts one reflection list twice, so the Miller indices are that
    list tiled once per line and a Kα2 image carries its Kα1 partner's index.
    The live view's rows are the walk's rows filtered, sorted and rounded
    through one index, and nothing else.
    """
    ins = _flat_plate(radiation="CuKa", displacement=0.5)
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())

    pos, hklm = model.reflection_positions(0, values)
    n_reflections = len(model.phases[0].reflections.hklm)
    assert len(model.line_wavelengths) == 2
    assert len(pos) == len(hklm) == 2 * n_reflections
    assert np.array_equal(hklm[:n_reflections], hklm[n_reflections:])

    keep = np.isfinite(pos)
    order = np.argsort(pos[keep], kind="stable")
    row = stage_ticks(model, values, max_per_phase=10**9)["phase 0"]
    assert row["two_theta"] == [round(float(p), TWO_THETA_DECIMALS)
                                for p in pos[keep][order]]
    assert row["hkl"] == [reflection_label_row(r) for r in hklm[keep][order]]


def test_the_walk_reads_a_refined_wavelength_as_the_peaks_do():
    """A free λ moves every peak, so it moves every tick.

    ``phase_peaks`` reads λ from the values (``line_lambdas``, WP-1134), and a
    walk reading the compile-time tuple instead left the ticks of a λ
    calibration at the old λ: 0.1 deg at 150 deg for +0.1 %.
    """
    ins = _flat_plate(radiation="CuKa")
    structure = _rutile()
    model = compile_model(structure, ins, _simulate(ins, structure),
                          mode="rietveld")
    table = ParameterTable(structure, ins)
    values = dict(table.decode(table.x0()))
    path = "instrument.source.lines.0.wavelength"
    values[path] *= 1.001

    pos, _ = model.reflection_positions(0, values)
    drawn = np.concatenate([p[0] for p in model.phase_peaks(0, values)])
    assert np.allclose(pos, drawn, rtol=0.0, atol=1e-10, equal_nan=True)


def test_the_satellite_arms_lattice_follows_the_ticks_geometry():
    """``report.satellites`` places its own positions and owes the ticks' answer.

    The reciprocal lattice contains every allowed reflection, so each tick must
    lie on a lattice position.  The arm added the zero alone, which left every
    lattice and satellite position 0.14-0.26 deg from the peak a displaced
    specimen drew, and the residual peak it was matched against.
    """
    from rietx.report.satellites import _lattice_positions

    ins = _flat_plate(displacement=0.5)
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    ticks = np.asarray(
        stage_ticks(model, values, max_per_phase=10**9)["phase 0"]["two_theta"])
    lattice = np.sort(_lattice_positions(model, values, 0))
    nearest = np.min(np.abs(ticks[:, None] - lattice[None, :]), axis=1)
    assert nearest.max() < 1e-4, (
        f"a tick sits {nearest.max():.4f} deg from the nearest lattice position")


def test_the_satellite_arm_places_a_propagation_vectors_satellites_by_the_ticks():
    """``_satellite_positions`` is the arm's other placement, held beside the lattice.

    A phase carrying a propagation vector draws its satellites in the model, so
    each of those drawn positions must be one the arm lists for that vector.
    The arm added the zero alone, so with a 0.5 mm displacement every one of
    them sat 0.14-0.26 deg from the satellite the model drew.
    """
    from rietx.report.satellites import _satellite_positions
    from tests.test_satellites import _phase as modulated_phase

    k = (0, 0, "1/2")
    structure = Structure(phases=[modulated_phase(k)])
    ins = _flat_plate(displacement=0.5)
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())

    pos, _ = model.reflection_positions(0, values)
    n_lines = len(model.line_wavelengths)
    is_satellite = np.tile(np.asarray(model.phases[0].reflections.is_satellite),
                           n_lines)
    drawn = pos[is_satellite & np.isfinite(pos)]
    drawn = drawn[(drawn >= model.tt_min) & (drawn <= model.tt_max)]
    assert len(drawn) >= 5, "the case must draw satellites for the claim to mean much"

    listed = _satellite_positions(model, values, 0,
                                  [structure.phases[0].propagation_vector])[0]
    nearest = np.min(np.abs(drawn[:, None] - listed[None, :]), axis=1)
    assert nearest.max() < 1e-4, (
        f"a drawn satellite sits {nearest.max():.4f} deg from the arm's nearest")


# ----------------------------------------------------------------------
# the window a reflection is generated in
# ----------------------------------------------------------------------
def test_a_reflection_the_geometry_pushes_into_the_range_is_still_generated():
    """The generation window follows the geometry's shift, not a fixed margin.

    ``compile_model`` kept reflections whose Bragg angle fell within 0.5 deg of
    the range after the zero.  A transparency of 0.04 pulls a 62 deg peak 2 deg
    down, so rutile (002), at 62.76 deg Bragg, is drawn at 60.72 deg: inside a
    range ending at 61.5, and outside the old window, which ended at 62.0.  The
    oracle is the same model over a range that does not strain the window.
    Without the reflection the live view shows no tick there, Layer 0 calls the
    peak an impurity, and the curve loses the peak.
    """
    ins = _flat_plate(transparency=0.04)
    structure = _rutile()
    data = _simulate(ins, structure)
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    hi = 61.5
    narrow = compile_model(structure, ins, data, mode="rietveld",
                           two_theta_limits=(20.0, hi))
    wide = compile_model(structure, ins, data, mode="rietveld",
                         two_theta_limits=(20.0, 70.0))

    def in_range(model):
        row = stage_ticks(model, values, max_per_phase=10**9)["phase 0"]
        return np.asarray([t for t in row["two_theta"] if 20.0 <= t <= hi])

    ticks_narrow, ticks_wide = in_range(narrow), in_range(wide)
    assert np.any(np.abs(ticks_wide - 60.72) < 0.05), "the case lost its pushed peak"
    assert len(ticks_narrow) == len(ticks_wide)
    assert np.allclose(ticks_narrow, ticks_wide, rtol=0.0, atol=1e-5)

    y_narrow = np.asarray(narrow.evaluate(values))
    y_wide = np.asarray(wide.evaluate(values))[: len(y_narrow)]
    assert np.allclose(narrow.tt, wide.tt[: len(y_narrow)])
    worst = float(np.max(np.abs(y_narrow - y_wide)) / np.max(y_wide))
    assert worst < 1e-3, f"the narrow model's curve is off the wide one's by {worst:.2e}"


# ----------------------------------------------------------------------
# where an intensity correction is judged (WP-1908's review finding 5)
# ----------------------------------------------------------------------
def test_a_correction_summary_is_judged_at_the_bragg_angle():
    """The absorption and roughness summaries read the angle the model used.

    The forward model evaluates both factors at each reflection's Bragg angle
    (``phase_peaks`` passes ``tt_bragg``).  The summaries' helper returned the
    drawn angle until WP-1976, so under a 0.5 mm displacement it
    judged them up to 0.26° away from where any reflection was corrected.
    """
    from rietx.model.absorption import equivalent_delta_biso_from_transmission
    from rietx.refine import _absorption_record, _reflection_bragg_angles

    ins = _flat_plate(displacement=0.5)
    ins.geometry.mu_t = 1.0
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())

    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    bragg = np.asarray(cp.reflections.two_theta(cell, model.line_lambdas(values)[0]))
    drawn = np.asarray(model.apparent_two_theta(bragg, values))
    inside = (drawn >= model.tt_min) & (drawn <= model.tt_max)
    assert np.max(np.abs(drawn - bragg)[inside]) > 0.1, "the case lost its shift"

    judged = _reflection_bragg_angles(model, values)
    assert np.array_equal(judged, bragg[inside])

    lam = model.line_lambdas(values)[0]
    record = _absorption_record(model, "given", None, values)

    def delta_biso(tt):
        return equivalent_delta_biso_from_transmission(
            tt, np.asarray(model._absorption(tt)), lam)[0]

    assert record.equivalent_delta_biso == delta_biso(bragg[inside])
    assert record.equivalent_delta_biso != delta_biso(drawn[inside])


def test_the_roughness_regime_is_judged_at_the_bragg_angle():
    """The second consumer: Pitschke's sinθ ≥ τ fence reads the Bragg angle.

    Rutile's first reflection sits at 27.44° Bragg and is drawn at 27.18°
    under a 0.5 mm displacement.  τ = 0.236 lies between sin θ at the two
    (0.2371 and 0.2350).  The forward model evaluates roughness at the Bragg
    angle, where sin θ > τ, so the model still depresses intensity there and
    only the turnover note may fire.  Judged at the drawn angle, the fence
    warned that the model amplifies.  The message quotes the drawn angle, the
    pattern's own axis.
    """
    from rietx.refine import _roughness_regime_diagnostics
    from rietx.schemas import RoughnessPitschke

    ins = _flat_plate(displacement=0.5)
    ins.geometry.surface_roughness = RoughnessPitschke(
        c=Parameter(value=1.0, min=0.0, max=4.0, transform="softplus"),
        tau=Parameter(value=0.236, min=0.0, max=0.3))
    structure = _rutile()
    data = _simulate(ins, structure)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())

    hits = [d for d in _roughness_regime_diagnostics(model, values)
            if d.code == "ROUGHNESS_OUTSIDE_REGIME"]
    assert [d.level for d in hits] == ["info"], "judged at the drawn angle"
    assert "sin(theta)=0.2371 at 27.18° 2θ" in hits[0].message
