"""A cell can run away *within one stage* even where ``phase_support`` never
falls below its threshold — a gap the WP-1110 window and the WP-1301 hold both
miss, because both key off one phase's own modelled contribution.

Trigger (synthetic, not the private dataset that surfaced it): two free
LaB6-shaped phases sharing the *same* starting cell, one at full scale and one
at a 2 % trace, with scale and cell freed together in one stage.  Neither
phase's own support ever drops — the full-scale phase's least of all — so the
support-based window (``params.vector.cell_window`` as applied by
``optimize.least_squares._freeze_cell_windows``) and the support-based hold
(``refine._hold_unsupported_phases``) both leave the pair unwindowed and
unheld the entire stage.  What actually happens is a **joint** degeneracy: the
two phases trade scale against each other along an axis in which either
phase's cell is free to run, and the phase that ends up walking it can be the
fully-supported one.  Measured on this exact construction before the fix: one
phase's cell.a walked 4.1566 -> 3803 Å in twenty TRF iterations of one "both"
stage (still reporting ``converged``), and the next stage's ``compile_model``
crashed with the WP-1110 ``generate_reflections`` refusal
(``refusing to enumerate reflections for cell a=295.588 ...``) before that
next stage's own ``_freeze_cell_windows`` ever ran.

The fix (``refine.clamp_cell_runaway``) is a **post-solve** correction, not a
second live bound: it inspects the committed cell values after a stage solves
and pulls any free cell parameter back inside
``CELL_SAFETY_FRACTION``/``CELL_SAFETY_ANGLE_DEG`` of the value the stage
*started* from, unconditionally — no phase_support test gates it, which is
the whole point, since the escaping phase here is exactly the one
phase_support calls fine.  Doing this on the outcome rather than as a bound
scipy's TRF sees is what keeps every other test in this suite bit-identical:
a live bound changes TRF's own trust-region step scaling even where it is
never hit (WP-1110's own measurement, on an honestly-converging phase), and
this project's suite has thousands of cell-refining fits that must not move a
digit.
"""

from __future__ import annotations

import math

import pytest

from rietx import Instrument, Refinement
from rietx.params.vector import (
    CELL_SAFETY_ANGLE_DEG,
    CELL_SAFETY_FRACTION,
    CELL_WINDOW_ANGLE_DEG,
    CELL_WINDOW_FRACTION,
    cell_window,
)
from rietx.refine import clamp_cell_runaway
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Structure
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_refine_synthetic import TRUE_A, synthesize
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("cell-runaway-safety")


def _degenerate_pair(decoy_scale: float) -> tuple[Structure, Instrument]:
    """A real LaB6 phase and a second, identically-celled copy at a trace
    scale — the construction WP-1110 item 13's own docstring calls out as
    "the situation this documents", pushed one step further: freeing scale
    and cell of *both* phases together in one stage, which
    ``mccusker_default`` never does (its ``scale_bkg`` and ``cell`` stages
    are separate, so by the time cell frees the trace phase's scale has
    already collapsed and the ordinary window catches it)."""
    real = make_lab6()
    for n in "abc":
        getattr(real.phases[0].cell, n).value = TRUE_A
    real.phases[0].scale.value = 5e-4
    decoy_s = make_lab6()
    decoy = decoy_s.phases[0]
    decoy.name = "decoy"
    for n in "abc":
        getattr(decoy.cell, n).value = TRUE_A
    decoy.scale.value = decoy_scale
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    return Structure(phases=[real.phases[0], decoy]), ins


# ----------------------------------------------------------------------
# cell_window's new fraction/angle_deg parameters: old defaults untouched
# ----------------------------------------------------------------------
def test_cell_window_defaults_are_bit_identical_to_before_the_parameters():
    """Every existing caller of ``cell_window`` passes no ``fraction``/
    ``angle_deg`` and must see exactly the old numbers."""
    lo, hi = cell_window("a", 10.0, -math.inf, math.inf)
    assert (lo, hi) == pytest.approx(
        (10.0 * (1 - CELL_WINDOW_FRACTION) - 0.05,
         10.0 * (1 + CELL_WINDOW_FRACTION) + 0.05))
    lo, hi = cell_window("beta", 93.2, -math.inf, math.inf)
    assert (lo, hi) == pytest.approx(
        (93.2 - CELL_WINDOW_ANGLE_DEG, 93.2 + CELL_WINDOW_ANGLE_DEG))


def test_the_safety_window_is_three_times_wider_than_the_support_window():
    """The two constants the two mechanisms use, related as documented."""
    assert CELL_SAFETY_FRACTION == pytest.approx(3.0 * CELL_WINDOW_FRACTION)
    assert CELL_SAFETY_ANGLE_DEG == pytest.approx(3.0 * CELL_WINDOW_ANGLE_DEG)
    lo_support, hi_support = cell_window("a", 10.0, -math.inf, math.inf)
    lo_safety, hi_safety = cell_window("a", 10.0, -math.inf, math.inf,
                                       fraction=CELL_SAFETY_FRACTION,
                                       angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert lo_safety < lo_support < 10.0 < hi_support < hi_safety


# ----------------------------------------------------------------------
# clamp_cell_runaway as a unit
# ----------------------------------------------------------------------
def test_a_cell_inside_the_window_is_left_alone():
    """The bit-identity property: nothing to clamp is nothing changed."""
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)
    start_values = table.decode(table.x0())
    # nudge phase 0's cell by far less than CELL_SAFETY_FRACTION
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 1.001
    clamped = clamp_cell_runaway(table, start_values)
    assert clamped == []
    assert entry.value == pytest.approx(TRUE_A * 1.001)


def test_a_cell_outside_the_window_is_pulled_back_and_reported():
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)
    start_values = table.decode(table.x0())
    escaped = TRUE_A * 50.0  # far outside +/-15%
    # ``clamp_cell_runaway`` reads and writes ``table.entries`` — the table's
    # own committed state, exactly what a real stage leaves it in after
    # ``table.commit(outcome.theta)`` — not the pydantic ``structure`` a
    # caller happens to also hold a reference to.
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = escaped
    clamped = clamp_cell_runaway(table, start_values)
    assert len(clamped) == 1
    path, old, new = clamped[0]
    assert path == "phases.0.cell.a"
    assert old == pytest.approx(escaped)
    lo, hi = cell_window("a", start_values[path], -math.inf, math.inf,
                         fraction=CELL_SAFETY_FRACTION,
                         angle_deg=CELL_SAFETY_ANGLE_DEG)
    assert new == pytest.approx(hi)
    assert entry.value == pytest.approx(hi)


def test_a_held_cell_is_never_visited():
    """Only ``table.free_paths`` is inspected — a fixed cell (or one held by
    WP-1301) cannot have "escaped" anything, since nothing moved it."""
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    # cell.a not freed
    start_values = table.decode(table.x0())
    structure.phases[0].cell.a.value = TRUE_A * 50.0  # would-be escape
    clamped = clamp_cell_runaway(table, start_values)
    assert clamped == []


# ----------------------------------------------------------------------
# the failure it exists for: end to end through Refinement.fit
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def degenerate_pair_fit():
    """The construction that crashed on main before this fix: two free
    cells sharing one starting value, scale+cell freed together in a single
    stage, followed by a second stage (forcing the next ``compile_model`` —
    exactly where the pre-fix crash actually fired, one stage after the
    escape, not inside the escaping stage itself)."""
    structure, ins = _degenerate_pair(1e-5)
    ref = Refinement(structure, ins, history=False)
    plan = RefinementPlan(stages=[
        Stage("both", ["phases.*.scale", "phases.*.cell.*"], max_iter=20),
        Stage("zero", ["instrument.zero_shift"], max_iter=20),
    ])
    return ref, ref.fit(synthesize(), plan=plan)


def test_the_trigger_construction_no_longer_crashes(degenerate_pair_fit):
    """Before the fix this raised ``ValueError: refusing to enumerate
    reflections ...`` out of the second stage's compile."""
    ref, result = degenerate_pair_fit
    assert result.status in ("converged", "max_iter")


def test_every_free_cell_ends_in_the_physical_range(degenerate_pair_fit):
    ref, _ = degenerate_pair_fit
    for phase in ref.structure.phases:
        a = phase.cell.a.value
        assert 1.0 < a < 100.0, f"{phase.name}: a = {a:.6g} Å ran away"


def test_cell_runaway_is_reported_when_it_fires(degenerate_pair_fit):
    _, result = degenerate_pair_fit
    fired = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1, [d.code for d in result.diagnostics]
    finding = fired[0]
    assert finding.level == "warning"
    assert all(p.startswith("phases.") and p.endswith(".cell.a")
              for p in finding.where)
    assert finding.value is not None and finding.value > 0.0


def test_a_well_behaved_fit_never_fires_it():
    """The bit-identity claim, on a real fit rather than a unit call: a
    single genuine LaB6 phase, ``mccusker_default``, never comes near the
    safety window (matching ``synthesize()``'s own wavelength/background,
    exactly as ``_absent_phase_inputs()`` does)."""
    structure = make_lab6()
    for n in "abc":
        getattr(structure.phases[0].cell, n).value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize())
    assert not any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    assert result.statistics.rwp < 0.05


def test_absent_phase_fixture_is_unaffected_by_the_new_safety_net():
    """WP-1110's own absent-phase fixture (support-window territory, not the
    joint-degeneracy this fix covers) must land exactly where
    ``test_absent_phase.py`` pins it — this fix must not change that path."""
    from tests.test_absent_phase import _absent_phase_inputs

    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize(), plan="mccusker_default")
    assert not any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    a = ref.structure.phases[0].cell.a.value
    assert a == pytest.approx(TRUE_A, abs=2e-4)
