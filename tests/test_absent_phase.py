"""WP-1110 item 13 — a phase the data cannot see, and what it does to a fit.

Two mechanisms for one failure, and neither substitutes for the other:

* ``params.vector.cell_window`` bounds the **symptom**.  A phase at zero scale
  contributes a flat direction, the trust region wanders along it, and the cell
  leaves the physical range entirely — silently, because a parameter that does
  not affect the calculated pattern does not affect Rwp either.
* ``refine._phase_support_diagnostics`` names the **cause**.  A windowed cell
  re-anchors at every stage, so it walks quietly rather than loudly and
  ``BOUND_HIT`` need never fire; without this the caller is left inferring an
  absent phase from a ρ≈1 correlation between its cell and its scale.

The episode behind both: two agents independently drove a real phase's cell to
a ≈ 39 293 Å and a ≈ 40 000 Å on a 68-pattern in-situ series, and the run died
hundreds of stages later inside ``generate_reflections``.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, Refinement
from rietx.params.vector import (
    CELL_MIN_LENGTH_A,
    CELL_WINDOW_ANGLE_DEG,
    CELL_WINDOW_FRACTION,
    CELL_WINDOW_PAD_A,
    ParameterTable,
    cell_window,
)
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Structure
from tests.test_refine_synthetic import TRUE_A, synthesize
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("absent-phase")

OUT = __import__("pathlib").Path(__file__).parent / "output"


# ----------------------------------------------------------------------
# the window itself
# ----------------------------------------------------------------------
def test_the_window_is_relative_to_the_value_it_is_anchored_on():
    """±5 % + 0.05 Å either side of where the stage starts."""
    lo, hi = cell_window("a", 10.0, -np.inf, np.inf)
    assert (lo, hi) == pytest.approx((10.0 * 0.95 - 0.05, 10.0 * 1.05 + 0.05))
    # the fractional part scales with the cell; the pad does not, which is what
    # keeps a short cell from being held tighter than a long one in absolute Å
    lo2, hi2 = cell_window("a", 20.0, -np.inf, np.inf)
    assert (hi - lo) == pytest.approx(2 * (CELL_WINDOW_FRACTION * 10.0
                                           + CELL_WINDOW_PAD_A))
    assert (hi2 - lo2) == pytest.approx(2 * (CELL_WINDOW_FRACTION * 20.0
                                             + CELL_WINDOW_PAD_A))


def test_a_finite_stored_bound_is_the_callers_claim_and_is_kept_per_side():
    """TOPAS's rule: user limits override the defaults.

    Per **side**, because the two sides are separate claims — the failure this
    exists for is unbounded-above, and a caller who set only a floor has said
    nothing about a ceiling.
    """
    lo, hi = cell_window("a", 10.0, 0.1, np.inf)
    assert lo == 0.1                      # kept: the caller said so
    assert hi == pytest.approx(10.55)     # filled: nobody said anything

    lo, hi = cell_window("a", 10.0, -np.inf, 12.0)
    assert lo == pytest.approx(9.45)
    assert hi == 12.0

    # both claimed → wholly untouched
    assert cell_window("a", 10.0, 1.0, 99.0) == (1.0, 99.0)


def test_the_floor_is_absolute_and_never_excludes_where_the_cell_already_is():
    """A short cell gets the floor; an impossibly short one is not raised on.

    ``ParameterTable`` has no diagnostics channel, so a cell below the floor is
    a model to refuse where a message can be attached — not a bound to raise on
    here.  Proposing ``lo > value`` would make ``least_squares`` reject x0.
    """
    # 0.95·2.0 − 0.05 = 1.85 clears the floor, so the fraction still governs
    assert cell_window("a", 2.0, -np.inf, np.inf)[0] == pytest.approx(1.85)
    # 0.95·1.6 − 0.05 = 1.47 does not, so the floor takes over
    lo, _ = cell_window("a", 1.6, -np.inf, np.inf)
    assert lo == CELL_MIN_LENGTH_A
    lo, hi = cell_window("a", 0.8, -np.inf, np.inf)
    assert lo <= 0.8 <= hi, "the window must always contain the current value"


def test_angles_get_a_degree_window_clipped_inside_the_degenerate_ends():
    lo, hi = cell_window("beta", 93.2, -np.inf, np.inf)
    assert (lo, hi) == pytest.approx((93.2 - CELL_WINDOW_ANGLE_DEG,
                                      93.2 + CELL_WINDOW_ANGLE_DEG))
    # the metric tensor is singular at 0° and 180°, so the window stops short
    lo, hi = cell_window("gamma", 179.5, -np.inf, np.inf)
    assert hi < 180.0 and lo <= 179.5 <= hi


def test_a_value_no_cell_can_take_is_refused_by_name():
    """Not a short cell — not a cell.  WP-1130's bug.

    The clamp above keeps a *positive* short length (it is a model to refuse
    where there is a diagnostics channel).  At ``value <= -pad/f`` it instead
    snaps both ends of the window onto ``value``, and the degenerate pair goes
    to ``least_squares``, which raises "Each lower bound must be strictly less
    than each upper bound" — naming no parameter and nothing about cells.  A
    trigonal ``a`` reached −42.7 Å that way.
    """
    for name, value in [("a", -5.0), ("b", -42.7), ("c", 0.0)]:
        with pytest.raises(ValueError, match=r"phases\.1\.cell\." + name):
            cell_window(name, value, -np.inf, np.inf,
                        path=f"phases.1.cell.{name}")
    for name, value in [("alpha", 0.0), ("beta", 180.0), ("gamma", -1.0)]:
        with pytest.raises(ValueError, match="not a cell angle"):
            cell_window(name, value, -np.inf, np.inf,
                        path=f"phases.1.cell.{name}")

    # without a path it still says which parameter, since that is all it has
    with pytest.raises(ValueError, match="cell parameter 'a'"):
        cell_window("a", -5.0, -np.inf, np.inf)


def test_the_window_is_never_degenerate():
    """The postcondition, over every value the function accepts.

    ``lo == hi`` is the shape the caller cannot handle: it is passed straight
    to the solver's ``bounds``.  Sweeping both branches is cheap and is what
    would have caught this, since the failing value was outside the range
    anyone thought to write a case for.
    """
    for value in [1e-12, 1e-6, 0.8, 1.5, 2.0, 5.4312, 10.0, 42.7, 1e3, 1e6]:
        lo, hi = cell_window("a", value, -np.inf, np.inf)
        assert lo < hi and lo <= value <= hi
    for value in [1e-9, 0.5, 1.0, 60.0, 90.0, 120.0, 179.0, 179.999]:
        lo, hi = cell_window("beta", value, -np.inf, np.inf)
        assert lo < hi and lo <= value <= hi


def _lab6_table():
    s = make_lab6()
    s.phases[0].cell.a.vary = True
    return s, ParameterTable(s, Instrument.debye_scherrer(wavelength=1.5406))


def test_the_window_reaches_the_solver_and_not_the_parameter_surface():
    """The distinction the placement rests on.

    A window is a bound for the stage about to run, not a fact about the stored
    parameter — ``ParameterRow`` and the ``.rxt`` document both tell a reader
    that bounds come from the schema, so a window surfaced there would read as
    a claim the caller never made.
    """
    _, table = _lab6_table()
    table.freeze_cell_windows({0})

    entry = next(e for e in table.entries if e.path == "phases.0.cell.a")
    assert (entry.lo, entry.hi) == (-np.inf, np.inf), "the entry keeps the schema's bounds"

    lo, hi = table.bounds()
    i = table.free_paths.index("phases.0.cell.a")
    v = entry.value
    assert lo[i] == pytest.approx(v * (1 - CELL_WINDOW_FRACTION) - CELL_WINDOW_PAD_A)
    assert hi[i] == pytest.approx(v * (1 + CELL_WINDOW_FRACTION) + CELL_WINDOW_PAD_A)


def test_a_table_that_was_asked_nothing_windows_nothing():
    """``None`` is *no claim made*, and an empty set is the claim that no phase
    needs one — the ``moving_paths`` convention, one rank over."""
    _, table = _lab6_table()
    i = table.free_paths.index("phases.0.cell.a")

    for claim in (None, set()):
        table.freeze_cell_windows(claim)
        lo, hi = table.bounds()
        assert (lo[i], hi[i]) == (-np.inf, np.inf), f"claim={claim!r}"


def test_the_window_is_spent_only_on_the_phases_named():
    """Not free, so not universal.

    TRF derives its per-coordinate trust-region scale from the distance to the
    bounds, so a window changes the *step* taken in a cell even where the bound
    is never reached. Measured on the chained IUCr ``cpd-1c``, whose cell
    finishes 0.24 Å inside a ±5 % window and never touches it: windowing every
    phase took the collapsed warm refit from 82 iterations to its 400-iteration
    budget and left it at Rwp 0.1501 against 0.1079 — just inside the reseed
    fence, so the pattern was accepted rather than rescued. That is why the
    window is restricted rather than applied to everything.
    """
    s = make_lab6()
    s2 = make_lab6()
    s2.phases[0].name = "second"
    for n in "abc":
        getattr(s2.phases[0].cell, n).value = 5.2
    both = Structure(phases=[s.phases[0], s2.phases[0]])
    for ph in both.phases:
        ph.cell.a.vary = True
    table = ParameterTable(both, Instrument.debye_scherrer(wavelength=1.5406))
    table.freeze_cell_windows({1})

    lo, hi = table.bounds()
    healthy = table.free_paths.index("phases.0.cell.a")
    absent = table.free_paths.index("phases.1.cell.a")
    assert (lo[healthy], hi[healthy]) == (-np.inf, np.inf)
    assert np.isfinite(lo[absent]) and np.isfinite(hi[absent])


def test_the_bound_and_the_diagnostic_read_one_measurement():
    """One authority projected twice, never two opinions (WP-1076's rule).

    A second measurement here would pass its own test and still let the solver
    bound a phase the report calls visible.
    """
    from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
    from rietx.optimize.least_squares import _freeze_cell_windows

    structure, ins = _absent_phase_inputs()
    pattern = synthesize()
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)

    support = model.phase_support(table.decode(table.x0()))
    _freeze_cell_windows(model, table)
    assert table._cell_window_phases == {
        ip for ip, v in enumerate(support) if v < PHASE_SUPPORT_SIGMA}
    assert table._cell_window_phases == {1}, "only the absent phase"


# ----------------------------------------------------------------------
# the failure it exists for
# ----------------------------------------------------------------------
def _absent_phase_inputs():
    """LaB₆ that is really there, plus a copy of it that is not."""
    s1 = make_lab6()
    for n in "abc":
        getattr(s1.phases[0].cell, n).value = 4.1606
    s1.phases[0].scale.value = 5e-4 * 1.8

    s2 = make_lab6()
    absent = s2.phases[0]
    absent.name = "absent"
    for n in "abc":
        getattr(absent.cell, n).value = 5.2
    absent.scale.value = 1e-9

    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    return Structure(phases=[s1.phases[0], absent]), ins


@pytest.fixture(scope="module")
def absent_phase_fit():
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    return ref, ref.fit(synthesize(), plan="mccusker_default")


def test_the_absent_phases_cell_stays_in_the_physical_range(absent_phase_fit):
    """Unbounded this walked 5.2 → 25.6 Å and still reported ``converged``.

    The bar is deliberately far looser than the measured result: the assertion
    is "did not leave the physical range", not a pin on the trajectory, which
    is a flat direction and therefore not reproducible to many figures.
    """
    ref, _ = absent_phase_fit
    a = ref.structure.phases[1].cell.a.value
    assert 4.0 < a < 7.0, f"absent phase cell ran to a = {a:.4g} Å"


def test_the_phase_that_is_really_there_is_untouched_by_the_window(absent_phase_fit):
    """The window must cost an honest phase nothing.

    Measured across 51 stage transitions of the 11-BM NAC and SRM 660c
    protocols the widest honest single-stage cell move was 2.8e-4 relative —
    two orders inside the window — so it is never reached by a fit that is
    working.
    """
    ref, result = absent_phase_fit
    assert result.statistics.rwp < 0.05
    a = ref.structure.phases[0].cell.a.value
    assert a == pytest.approx(TRUE_A, abs=2e-4), f"LaB6 a = {a}"


def test_the_diagnostic_names_the_cause_not_the_correlation(absent_phase_fit):
    """``HIGH_CORRELATION`` reports ρ≈1 between the cell and the scale.

    That is the symptom.  ``PHASE_UNCONSTRAINED`` says which phase the data
    cannot see and which of its parameters were refined against it anyway.
    """
    _, result = absent_phase_fit
    fired = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    finding = fired[0]
    assert finding.value < 1.0
    assert "absent" in finding.message
    # it carries the paths whose values are not measurements
    assert all(p.startswith("phases.1.") for p in finding.where)
    assert "phases.1.scale" not in finding.where, \
        "the scale is how a phase legitimately climbs out of the noise"
    assert any(".cell." in p for p in finding.where)


def test_a_trace_phase_that_is_really_there_does_not_fire_it(absent_phase_fit):
    """The false-positive side, on the same fit.

    Measured on the 11-BM NAC protocol, whose CaF₂ impurity is a genuine minor
    phase: 185σ of support there against a *noise-level* absent phase here.
    The claim is that ordering, and it is asserted as one — against this run's
    own ``support[0]``, never against a remembered figure.

    **The absent phase's support is the landing point of a flat direction and
    cannot be pinned to a number** (WP-1129); the cell assertion above already
    says so about the same fit's other coordinate. The phase reaches the
    pattern only through ``scale × |F|² × profile``, and its scale converges to
    *a* zero, not to *the* zero: measured 1.6e-14 under the shipped schedule
    and 7.1e-09 under ``intermediate_ftol=None``, one macOS box, one commit.
    The support that follows spans **six orders** across settings and
    platforms — 9.1e-07 and 0.548 here, 0.088 on WP-1110's machine, 1.64 on a
    Windows CI worker, which is what a fixed ``< 1.0`` bound turned into a red
    nightly. Every one of those is noise beside the ~386σ the real phase
    carries, which is the only thing the fit actually determines.
    """
    ref, _ = absent_phase_fit
    from rietx.model.forward import compile_model

    model = compile_model(ref.structure, ref.instrument, synthesize(),
                          mode="rietveld")
    table = ParameterTable(ref.structure, ref.instrument)
    values = table.decode(table.x0())
    support = [float(np.max(np.asarray(model.phase_component(ip, values))
                            / model.sigma))
               for ip in range(len(ref.structure.phases))]
    assert support[0] > 10.0, \
        f"the real phase is far above the noise: {support[0]:.3g}σ"
    assert support[1] < support[0] / 20.0, (
        f"the absent one is not far below it: {support[1]:.3g}σ against the "
        f"real phase's {support[0]:.3g}σ — a ratio of "
        f"{support[0] / max(support[1], 1e-300):.3g}, and the bar is 20")


@pytest.mark.slow
def test_the_absent_phase_fit_is_drawn_for_inspection(absent_phase_fit):
    """Rwp hides locally-bad fits; the picture is the check that does not."""
    from rietx.viz.plots import plot_result

    _, result = absent_phase_fit
    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "absent_phase.png"))
    import matplotlib.pyplot as plt

    plt.close("all")
    assert (OUT / "absent_phase.png").exists()


# ----------------------------------------------------------------------
# the same finding, read across a series (item 8)
# ----------------------------------------------------------------------
def _series_with(n: int, fired_in: int, *, code: str = "BOUND_HIT",
                 path: str = "phases.3.cell.c", level: str = "warning"):
    """``fired_in`` of ``n`` patterns carry ``code`` on ``path``."""
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult

    return SeriesResult(entries=[
        SeriesEntry(index=i, label=f"p{i}", diagnostics=(
            [Diagnostic(level=level, code=code, where=[path], message="…")]
            if i < fired_in else []))
        for i in range(n)])


def test_a_finding_in_most_of_a_series_is_stated_once_with_its_count():
    """The sentence no per-pattern diagnostic can produce.

    The trigger episode's own numbers: ``phases.3.cell.c`` pinned in 42 of 68
    patterns, said 425 times per-pattern and never once as "42 of 68".
    """
    from rietx.sequential import _persistent_diagnostics

    out = _persistent_diagnostics(_series_with(68, 42))
    assert len(out) == 1
    finding = out[0]
    assert finding.code == "SEQUENTIAL_PERSISTENT_FINDING"
    assert "42 of 68" in finding.message and "BOUND_HIT" in finding.message
    assert finding.where == ["phases.3.cell.c"]
    assert finding.value == pytest.approx(42 / 68)


def test_the_threshold_is_a_change_of_subject_at_half_the_patterns():
    """Below half, the per-entry diagnostics are the whole story.

    Not a tuned sensitivity: above half a finding describes the series rather
    than some of its members, and a summary that repeated a minority finding
    would be a second authority on the same fact.
    """
    from rietx.sequential import _persistent_diagnostics

    assert _persistent_diagnostics(_series_with(68, 34)) == []   # exactly half
    assert len(_persistent_diagnostics(_series_with(68, 35))) == 1


def test_a_short_series_gets_no_summary_at_all():
    """A summary of three things is not a summary."""
    from rietx.sequential import MIN_POINTS_FOR_PERSISTENCE, _persistent_diagnostics

    short = MIN_POINTS_FOR_PERSISTENCE - 1
    assert _persistent_diagnostics(_series_with(short, short)) == []


def test_it_aggregates_whatever_fired_rather_than_a_list_of_codes():
    """Diagnostic codes are an open vocabulary (root CLAUDE.md).

    A new code must be summarised on the day it lands, with no edit here — so
    this asserts the *mechanism* is code-agnostic, using one that did not exist
    when the aggregation was written.
    """
    from rietx.sequential import _persistent_diagnostics

    out = _persistent_diagnostics(
        _series_with(10, 9, code="PHASE_UNCONSTRAINED", path="phases.3.cell.a"))
    assert len(out) == 1 and "PHASE_UNCONSTRAINED" in out[0].message


def test_the_summary_carries_the_worst_level_and_promotes_nothing():
    """It travels in both directions.

    Up, because a summary must not report an error as a warning. Down, because
    a deliberate `dispersion=None` fires an **info** `DISPERSION_NEGLECTED` on
    every pattern of a series — "68 of 68" is worth saying, and calling a
    declared choice a warning is not.
    """
    from rietx.sequential import _persistent_diagnostics

    assert _persistent_diagnostics(_series_with(10, 9, level="error"))[0].level \
        == "error"
    assert _persistent_diagnostics(
        _series_with(10, 10, code="DISPERSION_NEGLECTED",
                     level="info"))[0].level == "info"


def test_a_finding_about_how_a_pattern_was_measured_is_never_aggregated():
    """``FROZEN_COMPILE_STALE`` (#272) on every pattern is a chain whose every
    last stage re-sized its windows, not a model that is wrong, so it gains no
    series finding — while a model-level code beside it still does."""
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult
    from rietx.sequential import NOT_A_SERIES_FINDING, _persistent_diagnostics

    assert "FROZEN_COMPILE_STALE" in NOT_A_SERIES_FINDING
    assert _persistent_diagnostics(
        _series_with(10, 10, code="FROZEN_COMPILE_STALE", path="",
                     level="info")) == []
    entries = [SeriesEntry(index=i, label=f"p{i}", diagnostics=[
        Diagnostic(level="info", code="FROZEN_COMPILE_STALE", message="…",
                   value=2e-3),
        Diagnostic(level="warning", code="BOUND_HIT",
                   where=["phases.0.cell.a"], message="…")])
        for i in range(10)]
    out = _persistent_diagnostics(SeriesResult(entries=entries))
    assert [d.message.split()[0] for d in out] == ["BOUND_HIT"]


def test_one_error_among_warnings_sets_the_summary_level():
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult
    from rietx.sequential import _persistent_diagnostics

    entries = []
    for i in range(10):
        level = "error" if i == 3 else "warning"
        entries.append(SeriesEntry(index=i, label=f"p{i}", diagnostics=[
            Diagnostic(level=level, code="BOUND_HIT",
                       where=["phases.0.cell.a"], message="…")]))
    out = _persistent_diagnostics(SeriesResult(entries=entries))
    assert out[0].level == "error"


def test_one_pattern_counts_once_however_many_stages_fired_it():
    """Otherwise the count measures stages, not patterns."""
    from rietx.schemas.common import Diagnostic
    from rietx.schemas.sequential import SeriesEntry, SeriesResult
    from rietx.sequential import _persistent_diagnostics

    repeated = [Diagnostic(level="warning", code="BOUND_HIT",
                           where=["phases.0.cell.a"], message=f"stage {s}")
                for s in range(6)]
    series = SeriesResult(entries=[
        SeriesEntry(index=i, label=f"p{i}", diagnostics=list(repeated))
        for i in range(8)])
    out = _persistent_diagnostics(series)
    assert len(out) == 1
    assert "8 of 8" in out[0].message, out[0].message


# ----------------------------------------------------------------------
# a scale on its floor, and the esds it keeps (WP-1463, WP-1938)
# ----------------------------------------------------------------------
# Every entry is refined in its own units since WP-1938, so the absent scale's
# column is the phase's own pattern at any value of the scale, 0.0 included.
# Under softplus its slope underflowed and the esds went (WP-1463).  The
# fixture lets the driver finish and then moves the scale to a chosen physical
# value, re-evaluating the residual and Jacobian there; every post-fit step
# then runs as in production.  A real 48-pattern series stopped its absent
# scale at 1e-179 and at 0.0.

def _scale_only_plan():
    from rietx.schemas.plan import PlanSpec, StageSpec

    return PlanSpec(stages=[
        StageSpec(name="scales",
                  turn_on=["phases.*.scale", "instrument.background.*"]),
        StageSpec(name="profile",
                  turn_on=["phases.0.cell.*", "instrument.zero_shift",
                           "instrument.profile.w", "phases.0.atoms.*.biso"]),
    ])


@pytest.fixture
def fit_absent_at(monkeypatch):
    """``fit(s)`` fits the absent-phase fixture with its scale moved to ``s``.

    Both drivers are wrapped, so the move happens whichever one the stage
    runs; ``s=None`` leaves the fit where the driver stopped it.
    """
    import importlib

    lsq = importlib.import_module("rietx.optimize.least_squares")
    refine_module = importlib.import_module("rietx.refine")
    trf, lm, run = (lsq.least_squares, lsq._lm_outcome,
                    refine_module.run_least_squares)
    where = {"k": None, "s": None}

    def run_recording_the_column(model, table, **kw):
        free = table.free_paths
        where["k"] = free.index("phases.1.scale") if "phases.1.scale" in free else None
        return run(model, table, **kw)

    def move(res, fun, jac):
        if where["k"] is not None and where["s"] is not None:
            x = res.x.copy()
            x[where["k"]] = where["s"]
            res.x, res.fun, res.jac = x, fun(x), jac(x)
            res.cost = 0.5 * float(res.fun @ res.fun)
        return res

    def trf_then_move(fun, x0, jac=None, **kw):
        return move(trf(fun, x0, jac=jac, **kw), fun, jac)

    def lm_then_move(fun, jac, x0, lo, hi, **kw):
        return move(lm(fun, jac, x0, lo, hi, **kw), fun, jac)

    monkeypatch.setattr(lsq, "least_squares", trf_then_move)
    monkeypatch.setattr(lsq, "_lm_outcome", lm_then_move)
    monkeypatch.setattr(refine_module, "run_least_squares", run_recording_the_column)

    def fit(s, plan="mccusker_default"):
        where["s"] = s
        structure, ins = _absent_phase_inputs()
        return Refinement(structure, ins, history=False).fit(synthesize(), plan=plan)

    fit.where = where
    return fit


def _empty_phase_inputs():
    """The absent-phase fixture with every site of the absent phase empty.

    Its pattern is zero at any scale, so its scale has no gradient anywhere.
    That is the one blind scale physical coordinates leave (WP-1938).
    """
    structure, ins = _absent_phase_inputs()
    for atom in structure.phases[1].atoms:
        atom.occ.value = 0.0
    return structure, ins


def _row(result, path):
    return next(p for p in result.parameters if p.path == path)


def _fraction_esds(result):
    return [q.weight_fraction_stderr for q in result.qpa.phases]


@pytest.mark.parametrize("s", [1e-135, 1e-166, 1e-304])
def test_where_on_its_floor_the_scale_stopped_moves_no_esd(fit_absent_at, s):
    """The answer does not depend on how far down the floor the driver went.

    The model is linear in a scale, so its column is the same at 1e-304 as at
    0.0.  Under softplus the internal variance overflowed at S ≈ 1e-166 and
    every weight-fraction esd went with it (WP-1463).  The reference is the
    fit as the driver left it, which on this fixture is exactly 0.0.
    """
    reference = fit_absent_at(None)
    moved = fit_absent_at(s)
    s_ref, s_moved = _row(reference, "phases.1.scale"), _row(moved, "phases.1.scale")
    assert s_moved.value == s
    assert s_ref.stderr is not None and s_ref.stderr > 0.0
    assert s_moved.stderr == pytest.approx(s_ref.stderr, rel=1e-9)
    assert _fraction_esds(moved) == pytest.approx(_fraction_esds(reference),
                                                  rel=1e-9)
    assert all(e is not None for e in _fraction_esds(moved))
    assert "QPA_ESD_UNAVAILABLE" not in {d.code for d in moved.diagnostics}


@pytest.mark.parametrize("plan", ["mccusker_default", "scale_only"])
def test_a_scale_at_zero_keeps_its_esd_and_every_fraction_esd(fit_absent_at, plan):
    """At exactly 0.0 the column is the phase's pattern, so nothing is withheld.

    Under softplus dS/du underflowed there and every fraction lost its esd
    (WP-1463).  The scale's marginal esd is WP-1929's decided rule for a row
    on its bound; it holds under a plan that frees the absent phase's cell
    and under one that frees only its scale.
    """
    result = fit_absent_at(0.0, plan=_scale_only_plan()
                           if plan == "scale_only" else plan)
    row = _row(result, "phases.1.scale")
    assert row.value == 0.0
    assert row.stderr is not None and np.isfinite(row.stderr) and row.stderr > 0.0
    assert all(e is not None and np.isfinite(e) for e in _fraction_esds(result))
    assert "QPA_ESD_UNAVAILABLE" not in {d.code for d in result.diagnostics}


@pytest.mark.parametrize("plan", ["mccusker_default", "scale_only"])
def test_a_scale_with_no_gradient_names_the_phase_that_withheld_every_esd(plan):
    """A phase whose pattern is zero at every scale still withholds the block.

    Every W_i divides by a sum that includes it, so one unmeasured scale
    leaves no fraction quotable (WP-1110 item 14).  The loss says which phase
    caused it, under a plan that frees the phase's cell and under one that
    frees only its scale.
    """
    structure, ins = _empty_phase_inputs()
    result = Refinement(structure, ins, history=False).fit(
        synthesize(),
        plan=_scale_only_plan() if plan == "scale_only" else plan)
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / f"absent_phase_empty_{plan}.png")
    assert _row(result, "phases.1.scale").stderr is None
    assert _fraction_esds(result) == [None, None]
    fired = [d for d in result.diagnostics if d.code == "QPA_ESD_UNAVAILABLE"]
    assert len(fired) == 1
    assert fired[0].where == ["phases.1.scale"]
    assert fired[0].level == "warning"
    assert "phase 1 (absent)" in fired[0].message
    assert "profile_fraction(data, 1)" in fired[0].suggestion


def test_a_scale_only_plan_leaves_phase_unconstrained_nothing_to_say(fit_absent_at):
    """Why the QPA block's comment was wrong on 15 of the 16.

    ``PHASE_UNCONSTRAINED`` is about a phase's *other* free parameters, and a
    plan freeing only the scale gives it none.  What names the phase there is
    the floor its scale stopped on, ``FLOOR_HIT`` since WP-1929.
    """
    result = fit_absent_at(0.0, plan=_scale_only_plan())
    codes = {d.code for d in result.diagnostics}
    assert "PHASE_UNCONSTRAINED" not in codes
    assert [d.where for d in result.diagnostics
            if d.code == "FLOOR_HIT" and "phases.1.scale" in d.where] \
        == [["phases.1.scale"]]


@pytest.mark.parametrize("s", [None, 0.0, 1e-166])
def test_a_scale_on_its_floor_is_at_its_bound_and_is_not_told_to_widen_it(
        fit_absent_at, s):
    """A floor of 0 is an ordinary bound (WP-1938), so the row says ``True``.

    The residual cosine is +0.030 there and pushes the scale outward, so the
    limit carried load.  ``FLOOR_HIT`` names it (WP-1929), with advice for a
    quantity that cannot go negative instead of ``BOUND_HIT``'s "widen the
    bound".  The phase that is there sits far from its floor, and stays a
    tested ``False``.
    """
    from rietx.refine import _ZERO_FLOOR_SUGGESTION

    result = fit_absent_at(s)
    assert _row(result, "phases.1.scale").at_bound is True
    assert _row(result, "phases.0.scale").at_bound is False
    assert not [d for d in result.diagnostics
                if d.code == "BOUND_HIT" and "phases.1.scale" in d.where]
    (hit,) = [d for d in result.diagnostics
              if d.code == "FLOOR_HIT" and "phases.1.scale" in d.where]
    assert hit.message.startswith("phases.1.scale refined to its floor (ρ=+")
    assert hit.value > 0.0
    assert hit.suggestion == _ZERO_FLOOR_SUGGESTION
    assert "widen" not in hit.suggestion


def _joint_inputs(*, empty: bool, seed: int = 1):
    """``seed`` draws histogram 0's noise; histogram 1 keeps seed 2."""
    from tests import test_multi_histogram as tmh

    structure, instruments = tmh.perturbed_inputs()
    absent = make_lab6().phases[0]
    absent.name = "absent"
    for n in "abc":
        getattr(absent.cell, n).value = 5.2
    absent.scale.value = 1e-9
    if empty:
        for atom in absent.atoms:
            atom.occ.value = 0.0
    structure = Structure(phases=[structure.phases[0], absent])
    patterns = [
        tmh.synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                       bkg=[40.0, -6.0, 1.5], seed=seed),
        tmh.synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                       bkg=[70.0, 5.0, -2.0], seed=2),
    ]
    return structure, instruments, patterns


def test_a_joint_fit_withholds_a_blind_scale_and_names_it():
    """``multi.py`` had its own QPA builder, and it skipped the blind-scale rule.

    So a joint fit with a blind scale propagated the other fractions as if
    that phase were known, which is the confident wrong number the single fit
    had been refusing since WP-1110.  Both now call one builder.  The row path
    is the joint surface's own: the absent scale is per histogram here, so
    ``hist.h.`` prefixes it.
    """
    from rietx import MultiHistogramRefinement

    structure, instruments, patterns = _joint_inputs(empty=True)
    result = MultiHistogramRefinement(structure, instruments).fit(
        patterns, plan="mccusker_default")

    for h, hist in enumerate(result.histograms):
        assert [q.weight_fraction_stderr for q in hist.qpa.phases] == [None, None]
        fired = [d for d in hist.diagnostics if d.code == "QPA_ESD_UNAVAILABLE"]
        assert [d.where for d in fired] == [[f"hist.{h}.phases.1.scale"]]


def test_a_joint_fit_tests_a_scale_on_its_floor_like_the_single_fit():
    """The joint runner's bound test has no floor exemption either (WP-1938).

    Histogram 0's absent scale stops on 0.0 and reads ``at_bound=True`` with
    its marginal esd, and ``FLOOR_HIT`` names it by its joint row path
    (WP-1929).
    Histogram 1's noise holds its own copy 0.1σ off the floor, so only the
    fractions are asserted there.

    Whether the absent scale lands on its floor is the noise's call, so the
    draw is chosen for it: drawn at the closing stage's windows (WP-2002),
    seed 1 holds histogram 0's copy 0.53σ off the floor, and seed 2 is the
    first that puts it on.
    """
    from rietx import MultiHistogramRefinement
    from rietx.refine import _ZERO_FLOOR_SUGGESTION

    structure, instruments, patterns = _joint_inputs(empty=False, seed=2)
    result = MultiHistogramRefinement(structure, instruments).fit(
        patterns, plan="mccusker_default")
    OUT.mkdir(exist_ok=True)
    for h in range(len(patterns)):
        result.for_histogram(h).plot(OUT / f"absent_phase_joint_floor_h{h}.png")

    row = _row(result, "hist.0.phases.1.scale")
    assert row.value == 0.0 and row.at_bound is True
    assert row.stderr is not None and row.stderr > 0.0
    hits = [d for d in result.diagnostics
            if d.code == "FLOOR_HIT" and "hist.0.phases.1.scale" in d.where]
    assert [d.suggestion for d in hits] == [_ZERO_FLOOR_SUGGESTION]
    for hist in result.histograms:
        assert all(q.weight_fraction_stderr is not None for q in hist.qpa.phases)


def test_a_series_whose_phase_has_no_gradient_says_so_in_every_pattern():
    """Five patterns, the empty phase's scale blind in each.

    Each entry names the phase, and ``SEQUENTIAL_PERSISTENT_FINDING`` counts
    it across the series with no edit of its own, its codes being an open
    vocabulary.
    """
    from rietx.sequential import refine_sequential

    structure, ins = _empty_phase_inputs()
    series = refine_sequential([synthesize(noise_seed=s) for s in range(5)],
                               structure, ins, plan="mccusker_default")
    for entry in series.entries:
        fired = [d for d in entry.diagnostics if d.code == "QPA_ESD_UNAVAILABLE"]
        assert [d.where for d in fired] == [["phases.1.scale"]], entry.label
    persistent = [d for d in series.diagnostics
                  if d.code == "SEQUENTIAL_PERSISTENT_FINDING"
                  and d.message.startswith("QPA_ESD_UNAVAILABLE")]
    assert [d.where for d in persistent] == [["phases.1.scale"]]
    assert "5 of 5" in persistent[0].message
