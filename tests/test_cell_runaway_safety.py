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
next stage's own ``_freeze_cell_windows`` ever ran.  That walk needed the
scales refined through softplus: since WP-1938 they are refined in their own
units and the construction no longer walks, so the firing path is reached by
an injected escape (:func:`_fit_with_injected_escape`).

The fix (``refine.reset_cell_runaway``) is a **post-solve** correction, not a
second live bound: it inspects the committed cell values after a stage solves,
and a phase with a free cell parameter outside
``CELL_SAFETY_FRACTION``/``CELL_SAFETY_ANGLE_DEG`` of the value the stage
*started* from gets its whole free cell put back at those starting values,
held, and the stage solved once more without it (WP-2002, B8).  It is
unconditional — no phase_support test gates it, which is
the whole point, since the escaping phase here is exactly the one
phase_support calls fine.  Until WP-2002 the parameter was pulled back to the
window's edge instead.  Doing this on the outcome rather than as a bound
scipy's TRF sees is what keeps every other test in this suite bit-identical:
a live bound changes TRF's own trust-region step scaling even where it is
never hit (WP-1110's own measurement, on an honestly-converging phase), and
this project's suite has thousands of cell-refining fits that must not move a
digit.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx import Instrument, Refinement
from rietx.params.vector import (
    CELL_SAFETY_ANGLE_DEG,
    CELL_SAFETY_FRACTION,
    CELL_WINDOW_ANGLE_DEG,
    CELL_WINDOW_FRACTION,
    cell_window,
)
from rietx.refine import CellReset, _build_result, _cell_runaway_diagnostic, reset_cell_runaway
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, Phase, Structure
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
# reset_cell_runaway as a unit
# ----------------------------------------------------------------------
def test_a_cell_inside_the_window_is_left_alone():
    """The bit-identity property: nothing escaped is nothing changed."""
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)
    start_values = table.decode(table.x0())
    # nudge phase 0's cell by far less than CELL_SAFETY_FRACTION
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 1.001
    found = reset_cell_runaway(table, start_values)
    assert found == []
    assert entry.value == TRUE_A * 1.001


def test_a_cell_outside_the_window_goes_back_to_its_start_and_is_reported():
    """WP-2002, B8: the stage-start value, never the window edge the
    parameter used to be pulled to, and only the phase that escaped."""
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.cell.a"], True)
    start_values = table.decode(table.x0())
    escaped = TRUE_A * 50.0  # far outside +/-15%
    # ``reset_cell_runaway`` reads and writes ``table.entries`` — the table's
    # own committed state, exactly what a real stage leaves it in after
    # ``table.commit(outcome.theta)`` — not the pydantic ``structure`` a
    # caller happens to also hold a reference to.
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = escaped
    other = table.entries[table._paths["phases.1.cell.a"]]
    other.value = TRUE_A * 1.001            # moved, inside its window
    found = reset_cell_runaway(table, start_values)
    assert found == [("phases.0.cell.a", escaped, start_values["phases.0.cell.a"])]
    assert found[0].escaped and found[0].held
    assert entry.value == start_values["phases.0.cell.a"]
    # the cubic b and c follow the restored a
    for n in "bc":
        assert table.entries[table._paths[f"phases.0.cell.{n}"]].value == entry.value
    # the other phase's cell did not escape, and keeps its solved value
    assert other.value == TRUE_A * 1.001
    # never as a bound: the table's free set is the caller's to change
    assert "phases.0.cell.a" in table.free_paths


def test_a_held_cell_is_never_visited():
    """Only ``table.free_paths`` is inspected — a fixed cell (or one held by
    WP-1301, which is the same ``set_vary(..., False)`` under the hood) cannot
    have "escaped" anything, since nothing moved it.

    Review of #385 finding 3.  The escape is staged on the table's own
    ``Entry`` — what a real stage's ``table.commit(outcome.theta)`` writes,
    and what ``reset_cell_runaway`` actually reads — never on the pydantic
    ``structure``: ``ParameterTable._add`` snapshots ``Entry.value`` from the
    model at construction and does not track it afterwards, so a write to
    ``structure.phases[0].cell.a.value`` after the table is built lands
    nowhere the function looks.  ``make_lab6`` frees the cell by default
    (``Cell.cubic(..., vary=True)``), so this test held ``cell.a`` explicitly
    is what makes the fixture's comment true — the previous
    ``# cell.a not freed`` was false: the fixture frees it, and the old
    test's escape silently missed the entries this function reads on two
    counts, not one.

    A cubic cell held at ``a`` has no other free cell parameter, so the
    reset could not move anything even with the filter gone.  The monoclinic
    half is the one the filter carries: ``a`` held and staged far outside its
    window, ``beta`` free beside it, and a reset reading the held entry would
    put ``beta`` back from its solved value.  Made to fail on purpose once
    (``tests/CLAUDE.md``): commenting out ``_escaped_cell_paths``' ``if e.path
    not in free: continue`` line turned that half red, the reset returning
    ``phases.0.cell.beta`` at its solved 99.3° instead of nothing.
    """
    from rietx.params.vector import ParameterTable

    structure, ins = _degenerate_pair(5e-4)
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.0.cell.a"], False)  # explicitly held/fixed
    assert "phases.0.cell.a" not in table.free_paths
    start_values = table.decode(table.x0())
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 50.0  # staged on the Entry itself, not the pydantic model
    found = reset_cell_runaway(table, start_values)
    assert found == []

    table = ParameterTable(_monoclinic_phase(98.3),
                           Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["phases.0.cell.beta"], True)
    table.set_vary(["phases.0.cell.a"], False)
    start_values = table.decode(table.x0())
    table.entries[table._paths["phases.0.cell.a"]].value = 5.0 * 50.0
    beta = table.entries[table._paths["phases.0.cell.beta"]]
    beta.value = 99.3                       # solved, inside its window
    assert reset_cell_runaway(table, start_values) == []
    assert beta.value == 99.3


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): a cell driven by a free ``vars.X`` is
# invisible to ``reset_cell_runaway``, which tests a free path's own name
# -- and it must stay invisible to the reset (a shared driver has no single
# start to go back to), but it must never pass through silently.
# ----------------------------------------------------------------------
def test_a_vars_driven_cell_escape_is_never_reset_but_is_named():
    """``phases.0.cell.a`` tied to a free ``vars.A`` (Yue's own reproduction,
    review of #385 finding 1): ``reset_cell_runaway`` still does not touch
    it -- that is correct, per its own docstring, since putting the driver
    back would move every other value it reaches -- but
    ``_vars_driven_cell_escapes`` must find it, and the ``CELL_RUNAWAY``
    diagnostic built from both must name ``vars.A`` and ``phases.0.cell.a``
    together, saying it was not put back."""
    from rietx import Refinement
    from rietx.refine import _cell_runaway_diagnostic, _vars_driven_cell_escapes

    structure, ins = _degenerate_pair(5e-4)
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("A", TRUE_A, min=1.0, max=1000.0)
    ref.tie("phases.0.cell.a", "vars.A")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.A", "phases.1.cell.a"], True)
    start_values = table.decode(table.x0())

    # the construction the review names: free (cells+vars) is ['phases.1.cell.a',
    # 'vars.A'], moving (cells+vars) additionally carries 'phases.0.cell.a'
    assert "phases.0.cell.a" not in table.free_paths
    assert "phases.0.cell.a" in table.moving_paths
    assert "vars.A" in table.free_paths

    # the escape happens through the driver -- exactly as it would after a
    # runaway TRF step + table.commit(outcome.theta) -- and the tie carries
    # it to the dependent cell
    driver = table.entries[table._paths["vars.A"]]
    driver.value = TRUE_A * 50.0  # far outside +/-15%, same escape as above
    table.refresh_ties()
    dependent = table.entries[table._paths["phases.0.cell.a"]]
    assert dependent.value == pytest.approx(TRUE_A * 50.0)

    # reset_cell_runaway does not, and must not, touch it
    found = reset_cell_runaway(table, start_values)
    assert found == []
    assert dependent.value == pytest.approx(TRUE_A * 50.0)  # still escaped

    # LaB6 is cubic, so ``vars.A`` reaches ``b``/``c`` too, transitively
    # through ``a``'s own symmetry tie -- column_reach's whole point (it
    # answers what a column moves, not what it is named) is that this is
    # not a special case to test around
    unresolved = _vars_driven_cell_escapes(table, start_values)
    assert unresolved == [("vars.A", ["phases.0.cell.a", "phases.0.cell.b",
                                     "phases.0.cell.c"])]

    # nothing is silently passed through: the diagnostic names the driver
    # and every escaped dependent
    diag = _cell_runaway_diagnostic(found, unresolved)
    assert diag is not None
    assert set(diag.where) == {"vars.A", "phases.0.cell.a",
                               "phases.0.cell.b", "phases.0.cell.c"}
    assert "vars.A" in diag.message
    assert "phases.0.cell.a" in diag.message
    assert "not put back" in diag.message
    assert "restored" not in diag.message


def test_a_vars_driver_with_no_escaped_dependent_is_not_reported():
    """The bit-identity companion: a free ``vars.X`` driving a cell that
    never leaves the window is not reported at all."""
    from rietx import Refinement
    from rietx.refine import _vars_driven_cell_escapes

    structure, ins = _degenerate_pair(5e-4)
    ref = Refinement(structure, ins, history=False)
    ref.add_variable("A", TRUE_A, min=1.0, max=1000.0)
    ref.tie("phases.0.cell.a", "vars.A")
    table = ref._prepare_table(restore=False)
    table.set_vary(["vars.A", "phases.1.cell.a"], True)
    start_values = table.decode(table.x0())

    assert _vars_driven_cell_escapes(table, start_values) == []


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


def test_the_trigger_construction_no_longer_walks_in_physical_units(
        degenerate_pair_fit):
    """The walk was a softplus artefact, and the reset has nothing to do now.

    Measured on this fixture (macOS arm64, ``[dev]``): with the scales
    refined through softplus, TRF drove the decoy's scale to 2.7e-25 and
    ``CELL_RUNAWAY`` fired.  Refined in their own units (WP-1938) the decoy's
    scale stops at 1.2e-6 with a live cell column, and its cell moves 1.1 %
    under either driver.  The firing path is pinned by the injected escapes
    below (``test_the_rietveld_trigger_reports_the_esd_its_last_stage_measured``,
    ``lebail_pair_fits``), which reach it on every platform.
    """
    ref, result = degenerate_pair_fit
    assert not any(d.code == "CELL_RUNAWAY" for d in result.diagnostics)
    for phase in ref.structure.phases:
        a = phase.cell.a.value
        assert abs(a / TRUE_A - 1.0) < CELL_SAFETY_FRACTION, f"{phase.name}: a = {a}"


#: the plan shape of the second instance on issue #374 (Le Bail, two phases
#: of one structure type): background, then cell, then widths, then an axial
#: term.  Staging is cumulative, so the cell stays free in every later stage.
_LEBAIL_WIDTHS = ["instrument.profile.u", "instrument.profile.v",
                  "instrument.profile.w"]
_LEBAIL_STAGES = [
    Stage("bkg", ["instrument.background.*"]),
    Stage("cell", ["phases.*.cell.*"]),
    Stage("widths", _LEBAIL_WIDTHS),
    Stage("axial", ["instrument.geometry.axial_sl"]),
]

#: the second phase of :func:`_cubic_pair`, 1.2 % larger: both phases are in
#: the data, and no peak of one sits on a peak of the other at this resolution
CUBIC_TWIN = 1.012
#: how far the injected answer puts the escaping cell, outside the ±15 % window
ESCAPE = 1.30
ESCAPED = "phases.1.cell.a"


def _cubic_pair() -> Structure:
    """Two cubic LaB6-shaped phases at ``TRUE_A`` and ``CUBIC_TWIN·TRUE_A`` —
    each ``b``/``c`` tied to its ``a`` by the symmetry, which is what the tie
    closure of the esd rule needs to be tested on."""
    phases = []
    for name, f in (("p", 1.0), ("twin", CUBIC_TWIN)):
        phase = make_lab6().phases[0]
        phase.name = name
        for n in "abc":
            getattr(phase.cell, n).value = TRUE_A * f
        phase.scale.value = 5e-4
        phases.append(phase)
    return Structure(phases=phases)


def _cubic_pair_pattern(wavelength: float = 0.4139, seed: int = 7):
    """``_cubic_pair`` at its own values, Poisson noise at a fixed seed."""
    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    truth = _cubic_pair()
    ins = Instrument.debye_scherrer(wavelength=wavelength)
    ins.profile.w.value = 2.5e-4
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (200.0, -20.0, 5.0)])
    tt = np.arange(3.0, 24.0, 0.005)
    empty = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, empty, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _fit_with_injected_escape(stages, *, mode, escape_at, restore_at,
                              second_escape=None, log=None):
    """Fit :func:`_cubic_pair` under ``stages`` with the escape **injected**:
    ``escape_at``'s first solve answers ``ESCAPE`` times what it found for
    ``ESCAPED``, and ``restore_at``'s solve (if that stage runs) answers the
    value ``escape_at`` found, so a later stage refines the cell from inside
    its window.  ``second_escape`` names a path the escape stage's *second*
    solve, the one the reset buys, answers ``ESCAPE`` times its own value
    for, which reaches the reset that has no solve after it.  ``log``
    collects ``(stage, free paths)`` per solve.

    WP-1301's hold is patched off (``_unsupported_phase_paths`` reports
    nothing): with it on, a phase measured at the escaped answer could be
    called unseen and held by the collapse instead, and the rule under test
    is the reset's."""
    import dataclasses
    import sys

    refine_module = sys.modules["rietx.refine"]
    real = refine_module.run_least_squares
    found: dict[str, float] = {}
    solves: dict[str, int] = {}

    def solve(model, table, **kwargs):
        stage = kwargs.get("stage")
        if log is not None:
            log.append((stage, list(table.free_paths)))
        outcome = real(model, table, **kwargs)
        solves[stage] = solves.get(stage, 0) + 1
        if stage == escape_at and solves[stage] == 2 and second_escape:
            table.commit(outcome.theta)
            entry = table.entries[table._paths[second_escape]]
            entry.value = ESCAPE * entry.value
            table.refresh_ties()
            return dataclasses.replace(outcome, theta=table.x0())
        if stage not in (escape_at, restore_at) or stage in found:
            return outcome
        table.commit(outcome.theta)
        entry = table.entries[table._paths[ESCAPED]]
        if stage == escape_at:
            found["solved"] = entry.value
            entry.value = ESCAPE * entry.value
        else:
            entry.value = found["solved"]
        found[stage] = entry.value
        table.refresh_ties()
        return dataclasses.replace(outcome, theta=table.x0())

    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(refine_module, "run_least_squares", solve)
        mp.setattr(refine_module, "_unsupported_phase_paths", lambda *a, **k: [])
        ref = Refinement(_cubic_pair(), ins, history=False)
        # the declared stages' reset; the closing stage is tests/test_closing_stage.py's
        result = ref.fit(_cubic_pair_pattern(), mode=mode,
                         plan=RefinementPlan(stages=list(stages), closing_window_tol=None))
    assert escape_at in found, "the injection never ran"
    return result


@pytest.fixture(scope="module")
def lebail_pair_fits():
    """The #374 Le Bail plan on ``_cubic_pair``, run twice, with the escape
    **injected** rather than found: the ``cell`` solve's answer for
    ``phases.1.cell.a`` is replaced by ``ESCAPE`` times itself, so the reset
    fires on that one path in that one stage on every platform.

    "end" cuts the plan after ``cell``, so the reset fires in the stage that
    produces the answer.  "early" runs the whole plan and puts the value the
    ``cell`` solve found back as ``widths``' answer, so ``axial`` refines the
    cell from a value inside its window and its reset has nothing to do.

    Why injected (review of #385 round 4): the fixture this replaces walked a
    free, jointly degenerate pair and recorded one machine's stopping point.
    On the Linux CI jobs the walk crossed WP-1301's hold instead, and the
    row left ``parameters`` through the collapse, which is why the helper
    patches the hold off."""
    out = {}
    for name, stages in (("end", _LEBAIL_STAGES[:2]), ("early", _LEBAIL_STAGES)):
        log: list = []
        out[name] = (_fit_with_injected_escape(
            stages, mode="lebail", escape_at="cell", restore_at="widths",
            log=log), log)
    return out


def _cell_rows(result, phase: int) -> dict[str, object]:
    by_path = {p.path: p for p in result.parameters}
    return {n: by_path.get(f"phases.{phase}.cell.{n}") for n in "abc"}


def test_a_reset_cell_is_held_for_its_stage_and_the_stage_solves_again(
        lebail_pair_fits):
    """WP-2002, B8, ruled 2026-10-19: on a runaway the cell goes back to its
    stage-start value and is held for that stage, with a record entry.

    "end": ``cell`` solved twice, the second time without ``ESCAPED``; the
    record names it in ``cell_reset`` and not in ``freed``; the answer holds
    it at exactly the value the stage started from, never the window edge
    the parameter was pulled to before.  "early": the next stage lifts the
    hold and refines the cell again."""
    end, log = lebail_pair_fits["end"]
    solves = [(s, free) for s, free in log if s == "cell"]
    assert len(solves) == 2, [s for s, _ in log]
    assert ESCAPED in solves[0][1] and ESCAPED not in solves[1][1]
    assert "phases.0.cell.a" in solves[1][1]          # the other phase refines on
    cell = end.stages[-1]
    assert cell.name == "cell"
    assert cell.cell_reset == [ESCAPED]
    assert ESCAPED not in cell.freed and ESCAPED not in cell.held
    [diag] = [d for d in end.diagnostics if d.code == "CELL_RUNAWAY"]
    assert "held while the stage solved again" in diag.message
    assert "window edge" not in diag.message
    start = TRUE_A * CUBIC_TWIN
    for n in "bc":   # the held a has left ``parameters``; its tied b, c report it
        assert _cell_rows(end, 1)[n].value == pytest.approx(start, rel=1e-14)
    # the earlier stage reset nothing, and says so rather than staying silent
    assert end.stages[0].cell_reset == []

    early, log = lebail_pair_fits["early"]
    assert [s.cell_reset for s in early.stages] == [[], [ESCAPED], [], []]
    later = [free for s, free in log if s in ("widths", "axial")]
    assert later and all(ESCAPED in free for free in later)


def test_a_reset_cells_stderr_is_withheld(lebail_pair_fits):
    """Review of #385 round 3: the esd is withheld only where the reset
    happened in the stage that produced the answer, and on every path tied to
    a withheld one (a tie inherits its source's blindness).

    "end": the answer stage put ``phases.1.cell.a`` back and held it, so the
    row has left ``parameters`` (a held path does, as WP-1301's collapse
    does), and the cubic ``b``/``c`` tied to it report ``stderr=None``, while
    phase 0, never reset, keeps its esd.  "early": the same reset fired in
    ``cell``, and the later stages refined the cell again from its start, so
    the value reported is a fit result and every cell row carries the esd that
    last stage measured.  Before round 3 "early" withheld ``a``'s esd off the
    run's accumulated diagnostics and left ``b``/``c`` theirs."""
    end, early = lebail_pair_fits["end"][0], lebail_pair_fits["early"][0]

    fired = [d for d in end.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1 and fired[0].where == [ESCAPED]
    assert [s.name for s in end.stages][-1] == "cell"
    rows = _cell_rows(end, 1)
    assert rows["a"] is None
    for n in "bc":
        assert rows[n] is not None and rows[n].stderr is None, f"end: phases.1.cell.{n}"
    for n, row in _cell_rows(end, 0).items():
        assert row is not None and row.stderr is not None, f"end: phases.0.cell.{n}"

    fired = [d for d in early.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1 and fired[0].where == [ESCAPED]
    assert [s.name for s in early.stages][-1] == "axial"
    for phase in (0, 1):
        rows = _cell_rows(early, phase)
        for n, row in rows.items():
            assert row is not None and row.stderr is not None, (
                f"early: phases.{phase}.cell.{n} withheld after re-converging")
        # one answer to "is this measured?" across a tie
        assert rows["b"].stderr == pytest.approx(rows["a"].stderr)
        assert rows["c"].stderr == pytest.approx(rows["a"].stderr)


#: the Rietveld trigger's plan shape — scale and cell freed together, then a
#: stage that forces the next compile — with a middle stage the injection
#: uses to put the cell back inside its window before ``zero`` refines it
_RIETVELD_STAGES = [
    Stage("both", ["phases.*.scale", "phases.*.cell.*"], max_iter=20),
    Stage("bkg", ["instrument.background.*"], max_iter=20),
    Stage("zero", ["instrument.zero_shift"], max_iter=20),
]


def test_the_rietveld_trigger_reports_the_esd_its_last_stage_measured():
    """Yue's round-3 probe, the Rietveld arm: the reset fires in ``both``
    and a later stage refines the cell again, so every cell row of both
    phases reports the esd ``zero`` measured, the tied ``b``/``c`` equal to
    their ``a``.

    Why injected (review of #385 round 5): this used to read
    ``degenerate_pair_fit``, whose free, jointly degenerate walk stops
    wherever one machine's solve stops — the fragility round four removed
    from the two tests beside it.  That fixture's other tests assert what
    holds on any branch of the walk, and stay on it."""
    result = _fit_with_injected_escape(
        _RIETVELD_STAGES, mode="rietveld", escape_at="both", restore_at="bkg")
    fired = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1 and fired[0].where == [ESCAPED]
    assert fired[0].level == "warning"
    assert fired[0].value is not None and fired[0].value > 0.0
    assert [s.name for s in result.stages][-1] == "zero"
    assert [s.cell_reset for s in result.stages] == [[ESCAPED], [], []]
    for phase in (0, 1):
        rows = _cell_rows(result, phase)
        for n, row in rows.items():
            assert row is not None and row.stderr is not None, (
                f"phases.{phase}.cell.{n} withheld after re-converging")
        assert rows["b"].stderr == pytest.approx(rows["a"].stderr)
        assert rows["c"].stderr == pytest.approx(rows["a"].stderr)


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
    assert all(s.cell_reset == [] for s in result.stages)
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


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): theta/Entry.value desync after a reset
# ----------------------------------------------------------------------
#
# ``reset_cell_runaway`` mutates ``Entry.value`` directly, but it does not
# touch the ``LSQOutcome.theta`` the stage is carrying — and
# ``_build_result`` decodes *that* ``theta`` (never the table) to build
# ``y_calc``/``statistics``/``ticks``, while ``RefinedParameter.value`` reads
# ``Entry.value`` straight off the table.  A reset that fires desyncs the two
# unless the caller re-derives ``theta``: the reported parameter would be the
# restored one, and the reported fit quality/pattern the escaped one's.  (Found
# on the window-edge clamp this replaced; the contract is the same.)
#
# Since WP-2002 a reset after the stage's first solve always buys a second
# solve, whose ``theta`` is a fresh encoder output and never stale.  The one
# branch that hands its outcome straight to ``_build_result`` is a reset after
# that second solve, which ``second_escape`` reaches below.  The contract
# itself needs no solver: a stage's ``table.commit(outcome.theta)`` is exactly
# ``table.commit(entry-set-by-hand)`` from ``_build_result``'s point of view.
def test_build_result_uses_the_theta_a_firing_reset_left_stale():
    """Demonstrates the *contract* directly: fed a stale (pre-reset) theta,
    ``_build_result`` disagrees with the table it was handed; fed
    ``table.x0()`` re-derived after the reset, it agrees exactly. This is
    unconditionally true of ``_build_result`` and does not by itself prove
    ``_run_stage``/``fit()`` honour it on a live solve (both thetas are
    supplied here by hand) -- see
    ``test_fit_re_derives_theta_after_a_reset_with_no_solve_after_it``
    below for the integration check."""
    structure = make_lab6()
    for n in "abc":
        getattr(structure.phases[0].cell, n).value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)

    from rietx.params.vector import ParameterTable

    data = synthesize()
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.0.cell.a"], True)
    start_values = table.decode(table.x0())

    # what a runaway TRF step + ``table.commit(outcome.theta)`` leaves: an
    # escaped cell, freshly committed.  ``stale_theta`` is exactly what
    # ``outcome.theta`` holds until the caller re-derives it.
    entry = table.entries[table._paths["phases.0.cell.a"]]
    entry.value = TRUE_A * 1.30  # +30%, outside CELL_SAFETY_FRACTION
    stale_theta = table.x0()

    found = reset_cell_runaway(table, start_values)
    assert len(found) == 1, found
    fixed_theta = table.x0()  # the fix: re-derived after the reset

    # entry.value is the ground truth either way — RefinedParameter.value
    # reads it directly and is not the thing under test here
    assert entry.value == start_values["phases.0.cell.a"]  # the reset moved it

    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.optimize.statistics import compute_statistics

    model = compile_model(structure, ins, data)

    def y_calc_and_rwp_at(theta):
        values = table.decode(theta)
        y_calc = model.evaluate(values)
        y_bkg = model.background(values)
        stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                   n_free=0, y_background=y_bkg)
        return y_calc, stats.rwp

    y_calc_stale, rwp_stale = y_calc_and_rwp_at(stale_theta)
    y_calc_fixed, rwp_fixed = y_calc_and_rwp_at(fixed_theta)

    # the reset actually moved the cell, so the two thetas decode to
    # different y_calc/rwp -- otherwise this test would not be exercising
    # anything
    assert not np.allclose(y_calc_stale, y_calc_fixed)
    assert rwp_stale != pytest.approx(rwp_fixed)

    # the postcondition: _build_result called with the RE-DERIVED theta
    # agrees with what the table (== RefinedParameter.value) actually holds;
    # called with the STALE one, it does not.
    result_stale = _build_result(
        model, table, stale_theta, mode="rietveld", status="converged",
        stage_results=[], diagnostics=[], structure=structure)
    result_fixed = _build_result(
        model, table, fixed_theta, mode="rietveld", status="converged",
        stage_results=[], diagnostics=[], structure=structure)

    reported_a = {p.path: p.value for p in result_fixed.parameters}["phases.0.cell.a"]
    assert reported_a == pytest.approx(entry.value)  # both results report this

    # stale: y_calc/rwp reflect the escaped cell, not the reported parameter
    assert np.max(np.abs(np.asarray(result_stale.y_calc) - y_calc_fixed)) > 1.0
    assert result_stale.statistics.rwp != pytest.approx(rwp_fixed)

    # fixed: y_calc/rwp agree exactly with a recompute at the reported value
    assert np.asarray(result_fixed.y_calc) == pytest.approx(y_calc_fixed)
    assert result_fixed.statistics.rwp == pytest.approx(rwp_fixed)


def test_fit_re_derives_theta_after_a_reset_with_no_solve_after_it(monkeypatch):
    """End-to-end regression, through the public ``Refinement.fit()`` surface
    rather than a direct ``_build_result`` call.

    One stage, two injected escapes (:func:`_fit_with_injected_escape`): the
    first solve's ``ESCAPED``, which the reset holds and re-solves, and the
    second solve's ``phases.0.cell.a``, which goes back to its start with no
    solve after it and stays a free column with its esd withheld.  That second
    one is the branch whose outcome reaches ``_build_result`` directly, so
    this spies on the real ``_build_result`` call ``fit()`` makes and checks
    its ``theta`` decodes to exactly what the SAME table's ``Entry.value``\\ s
    hold at that moment, the literal postcondition, with no independent model
    build to disagree about.  Made to fail on purpose once: without the
    second reset's ``dataclasses.replace(second, theta=table.x0())`` in
    ``_run_stage``, ``phases.0.cell.a`` decodes to the escaped 5.4036 Å
    against the restored entry's 4.1566 Å.

    Rather than recompiling a second model to compare ``y_calc`` against (a
    fresh ``compile_model`` call makes its own frozen-window/FCJ-node sizing
    decisions -- WP-1110's own "Frozen-per-stage discreteness" invariant --
    which need not agree with the live fit's compiled model and produced a
    large, unrelated mismatch when tried), the spy reads the theta.
    """
    import sys

    refine_module = sys.modules["rietx.refine"]  # see the other test's note

    captured = {}
    real_build_result = refine_module._build_result

    def spy(model, table, theta, **kwargs):
        captured["theta"] = theta
        captured["entry_values"] = {e.path: e.value for e in table.entries}
        captured["decoded"] = table.decode(theta)
        return real_build_result(model, table, theta, **kwargs)

    monkeypatch.setattr(refine_module, "_build_result", spy)

    late = "phases.0.cell.a"
    result = _fit_with_injected_escape(
        _RIETVELD_STAGES[:1], mode="rietveld", escape_at="both", restore_at=None,
        second_escape=late)
    [diag] = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert diag.where == [ESCAPED, late]
    assert "held while the stage solved again" in diag.message
    assert "after the stage's second solve" in diag.message
    [stage] = result.stages
    assert stage.cell_reset == [ESCAPED, late]
    assert ESCAPED not in stage.freed and late not in stage.freed
    row = result.parameter(late)
    assert row.vary is True and row.stderr is None
    assert row.value == pytest.approx(TRUE_A, rel=1e-14)
    assert captured, "the spy never ran -- fit() must call _build_result by name"

    for path, entry_value in captured["entry_values"].items():
        assert captured["decoded"][path] == pytest.approx(entry_value, abs=1e-9), (
            f"{path}: table.decode(theta)={captured['decoded'][path]!r} but "
            f"Entry.value={entry_value!r} -- the theta _build_result received "
            f"disagrees with the table it came from")


# ----------------------------------------------------------------------
# review of #385 (2026-09-22): the CELL_RUNAWAY message named the wrong
# unit and the wrong window for an angle
# ----------------------------------------------------------------------
def _monoclinic_phase(beta: float) -> Structure:
    cell = Cell(a=Parameter(value=5.0, min=0.1), b=Parameter(value=6.0, min=0.1),
               c=Parameter(value=7.0, min=0.1), alpha=Parameter(value=90.0),
               beta=Parameter(value=beta), gamma=Parameter(value=90.0))
    return Structure(phases=[Phase(
        name="probe", space_group="P 1 2/m 1", cell=cell,
        atoms=[Atom(label="X", species="Si", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))])])


def test_a_free_beta_outside_the_angle_window_is_reset_and_reported_in_degrees():
    """A monoclinic phase's free ``beta`` escaping the ±``CELL_SAFETY_ANGLE_DEG``
    window must be reported in degrees, at the angle window — never in Å at
    the length fraction, which is what every ``a/b/c`` path in this file's
    other tests correctly gets."""
    from rietx.params.vector import ParameterTable

    structure = _monoclinic_phase(98.3)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(structure, ins)
    hits = table.set_vary(["phases.0.cell.beta"], True)
    assert "phases.0.cell.beta" in hits
    start_values = table.decode(table.x0())

    entry = table.entries[table._paths["phases.0.cell.beta"]]
    entry.value = 98.3 + 10.0  # +10 deg, outside the +/-CELL_SAFETY_ANGLE_DEG window
    found = reset_cell_runaway(table, start_values)
    assert len(found) == 1
    path, old, new = found[0]
    assert path == "phases.0.cell.beta"
    assert old == 108.3 and new == 98.3 and entry.value == 98.3

    diag = _cell_runaway_diagnostic(found)
    assert diag is not None
    assert "Å" not in diag.message
    assert "15%" not in diag.message
    assert "°" in diag.message
    assert f"±{CELL_SAFETY_ANGLE_DEG:.0f}°" in diag.message


def test_a_mixed_length_and_angle_reset_names_both_windows():
    """A stage that resets both a length and an angle in the same firing
    must not collapse to either unit alone."""
    diag = _cell_runaway_diagnostic([
        ("phases.0.cell.a", 5.403580000000001, 4.83009),
        ("phases.0.cell.beta", 108.3, 104.3),
    ])
    assert diag is not None
    assert "Å" in diag.message and "°" in diag.message
    assert f"±{CELL_SAFETY_FRACTION:.0%}" in diag.message
    assert f"±{CELL_SAFETY_ANGLE_DEG:.0f}°" in diag.message


# ----------------------------------------------------------------------
# issue #374's second instance: Le Bail, two phases of one structure type,
# cell lengths gone negative with every stage ``converged``
# ----------------------------------------------------------------------
_ORTHO = (4.02, 4.21, 4.43)


def _ortho_phase(name: str, f: float) -> Phase:
    a, b, c = (f * v for v in _ORTHO)
    return Phase(
        name=name, space_group="P m m m",
        cell=Cell(a=Parameter(value=a, vary=True), b=Parameter(value=b, vary=True),
                  c=Parameter(value=c, vary=True), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="La", species="La", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0)),
               Atom(label="B1", species="B", x=Parameter(value=0.2),
                    y=Parameter(value=0.5), z=Parameter(value=0.5))])


def _ortho_pattern():
    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    truth = Structure(phases=[_ortho_phase("p", 1.0)])
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.profile.w.value = 0.002
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (200.0, -20.0, 5.0)])
    tt = np.arange(3.0, 24.0, 0.005)
    empty = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, empty, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0())) * 2e4
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def test_a_negative_cell_length_in_lebail_is_caught_by_the_same_reset(monkeypatch):
    """Two orthorhombic phases of one structure type with cells 0.8 % apart,
    Le Bail, the plan freeing background → cell → widths → an axial term.
    The ``cell`` solve's answer is replaced by the issue's shape — a ≈ −1.0e4,
    b ≈ −5.9e4, c ≈ 1.9e5 Å, a *positive* volume, so no degenerate-metric
    refusal can see it — and the stage still reports ``converged``.

    No positivity guard is needed beside the reset: its window is a band
    around the stage's positive starting length (±15 %, and ±6° inside
    (0°, 180°) for an angle), so a length ≤ 0 is outside it by construction
    and goes back like any other escape, in Le Bail mode as in Rietveld.
    Measured without the clamp the reset replaced: the ``widths`` compile
    refuses to enumerate reflections for the escaped cell (``ValueError``); a
    run whose last stage escaped would have returned it.  Injected on the
    stage's first solve alone, since the reset's second solve runs with the
    cell held."""
    import dataclasses
    import sys

    refine_module = sys.modules["rietx.refine"]
    real = refine_module.run_least_squares
    issue_shape = dict(zip("abc", (-1.0e4, -5.9e4, 1.9e5), strict=True))

    injected = []

    def solve(model, table, **kwargs):
        outcome = real(model, table, **kwargs)
        if kwargs.get("stage") != "cell" or injected:
            return outcome
        injected.append(True)
        table.commit(outcome.theta)
        by_path = {e.path: e for e in table.entries}
        for n, v in issue_shape.items():
            by_path[f"phases.1.cell.{n}"].value = v
        return dataclasses.replace(outcome, theta=table.x0())

    monkeypatch.setattr(refine_module, "run_least_squares", solve)
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    ref = Refinement(Structure(phases=[_ortho_phase("p", 1.0),
                                       _ortho_phase("twin", 1.008)]),
                     ins, history=False)
    result = ref.fit(_ortho_pattern(), mode="lebail", plan=RefinementPlan(stages=[
        Stage("bkg", ["instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("widths", ["instrument.profile.u", "instrument.profile.v",
                         "instrument.profile.w"]),
        Stage("axial", ["instrument.geometry.axial_sl"]),
    ]))

    assert all(s.status == "converged" for s in result.stages)
    fired = [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
    assert len(fired) == 1
    assert fired[0].where == [f"phases.1.cell.{n}" for n in "abc"]
    for n, start in zip("abc", _ORTHO, strict=True):
        assert (f"phases.1.cell.{n} {issue_shape[n]:.6g} -> {1.008 * start:.6g} Å"
                in fired[0].message)
    assert result.stages[1].cell_reset == [f"phases.1.cell.{n}" for n in "abc"]
    for phase in ref.structure.phases:
        assert all(v > 1.0 for v in phase.cell.lengths_angles()[:3]), phase.name


@pytest.mark.parametrize("beta", [-3.0, 0.0, 180.0, 185.0])
def test_an_angle_outside_zero_to_180_is_reset(beta):
    """The angle half of the positivity question: a free β the solve left
    at or past 0° or 180° is outside ±6° of a physical start, so the reset
    puts it back at that start — no second test needed."""
    from rietx.params.vector import ParameterTable

    table = ParameterTable(_monoclinic_phase(95.0), Instrument.debye_scherrer(
        wavelength=0.4139))
    table.set_vary(["phases.0.cell.beta"], True)
    start_values = table.decode(table.x0())
    next(e for e in table.entries if e.path == "phases.0.cell.beta").value = beta
    found = reset_cell_runaway(table, start_values)
    assert found == [("phases.0.cell.beta", beta, 95.0)]


# ----------------------------------------------------------------------
# The reset hands back the cell the stage evaluated (#283 / #289, one rank on)
# ----------------------------------------------------------------------
def _p1_table(cell):
    from rietx.params.vector import ParameterTable
    from rietx.schemas.structure import lebail_scaffold

    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.background = BackgroundChebyshev.with_terms(3)
    table = ParameterTable(lebail_scaffold("P 1", cell), ins)
    table.set_vary(["phases.0.cell.*"], True)
    return table


TRICLINIC = [2.733385, 2.361025, 2.548007, 127.8106, 113.4292, 108.7994]
CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


def test_three_escaped_angles_put_the_whole_cell_back_at_its_start():
    """The window-edge clamp this replaced moved each parameter to its own
    window, so three escaped angles landed on the window's corner, ``start +
    6°`` each: α, β, γ = 133.8°, 119.4°, 114.8°, a direct-metric determinant
    of −126, which raised ``DegenerateCellError`` out of a Le Bail fit.  The
    reset puts the cell back at the one the stage started with, whose volume
    the stage's own residual evaluated."""
    from rietx.crystallography.lattice import direct_metric_tensor

    table = _p1_table(TRICLINIC)
    start_values = table.decode(table.x0())
    for name in CELL_NAMES:
        entry = table.entries[table._paths[f"phases.0.cell.{name}"]]
        entry.value = start_values[f"phases.0.cell.{name}"] * (
            1.5 if name in "abc" else 1.4)             # far outside the window
    found = reset_cell_runaway(table, start_values)
    assert len(found) == 6 and all(c.escaped for c in found)
    for path, escaped, restored in found:
        assert restored == start_values[path], path
        assert table.entries[table._paths[path]].value == start_values[path]
        assert escaped != pytest.approx(start_values[path])
    cell = [table.entries[table._paths[f"phases.0.cell.{n}"]].value for n in CELL_NAMES]
    assert float(np.linalg.det(np.asarray(direct_metric_tensor(*cell)))) > 0.0


def test_a_parameter_inside_its_window_goes_back_with_its_cell():
    """Three angles escape while ``a`` drifts inside its window.  The cell
    goes back whole, since ``a`` beside its partners' start values would be
    another cell no fit produced; ``a`` is reported with the solved value it
    went back from, and the message names only the three that left."""
    table = _p1_table(TRICLINIC)
    start_values = table.decode(table.x0())
    by_path = {e.path: e for e in table.entries}
    for name in ("alpha", "beta", "gamma"):
        by_path[f"phases.0.cell.{name}"].value = start_values[
            f"phases.0.cell.{name}"] * 1.4
    drifted = start_values["phases.0.cell.a"] * 1.01        # inside ±15 %
    by_path["phases.0.cell.a"].value = drifted
    found = reset_cell_runaway(table, start_values)
    assert len(found) == 6
    assert {c[0] for c in found if c.escaped} == {
        f"phases.0.cell.{n}" for n in ("alpha", "beta", "gamma")}
    for path in start_values:
        if ".cell." in path:
            assert by_path[path].value == start_values[path], path
    [a_row] = [c for c in found if c[0] == "phases.0.cell.a"]
    assert a_row[1] == drifted and not a_row.escaped
    assert a_row[2] == start_values["phases.0.cell.a"]
    message = _cell_runaway_diagnostic(found).message
    assert message.startswith(
        "3 free cell parameters left ±6° of this stage's starting cell during "
        "solving: phases.0.cell.alpha, phases.0.cell.beta, phases.0.cell.gamma.")
    assert "phases.0.cell.a " in message           # in the restored detail
    assert "held while the stage solved again" in message
    assert "window edge" not in message


def test_a_reset_after_the_last_solve_says_so():
    """A row the stage could not hold, found after its second solve
    (``CellReset.held`` False), is worded apart from a held one."""
    message = _cell_runaway_diagnostic([
        CellReset("phases.1.cell.a", 5.40358, 4.20648, held=False)]).message
    assert "after the stage's second solve, with no solve after it" in message
    assert "held while the stage solved again" not in message


def test_tied_angles_follow_a_restored_alpha():
    """Rhombohedral axes, α free with β, γ ← α: start 100°, solved 140°.  The
    reset puts the phase's free cell (``a`` and α) back at the start, and the
    ties refreshed off it put β and γ back at 100° too, so the cell the table
    holds is the stage's own (review of #736, round 2, on the clamp)."""
    from rietx.params.vector import ParameterTable
    from rietx.schemas.structure import lebail_scaffold

    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.background = BackgroundChebyshev.with_terms(3)
    table = ParameterTable(
        lebail_scaffold("R -3 m:R", [5.0, 5.0, 5.0, 100.0, 100.0, 100.0]), ins)
    table.set_vary(["phases.0.cell.*"], True)
    start_values = table.decode(table.x0())
    by_path = {e.path: e for e in table.entries}
    by_path["phases.0.cell.alpha"].value = 140.0
    for tied in ("beta", "gamma"):
        by_path[f"phases.0.cell.{tied}"].value = 140.0     # what commit leaves
    found = reset_cell_runaway(table, start_values)
    assert [(c[0], c.escaped) for c in found] == [
        ("phases.0.cell.a", False), ("phases.0.cell.alpha", True)]
    for name in ("alpha", "beta", "gamma"):
        assert by_path[f"phases.0.cell.{name}"].value == 100.0


@pytest.mark.slow
def test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error(tmp_path):
    """The public path: a P 1 Le Bail fit of a valid but wrong ~7 Å^3 cell on
    synthetic silicon (``tests/_synthetic_silicon.py``), two
    stages.  The second ended on the window-edge clamp's degenerate corner
    and raised ``DegenerateCellError`` out of ``fit`` from ``phase_support``;
    the reset that replaced the clamp puts the cell back at its stage start.

    ``slow`` since WP-2019: it was the fast tier's longest case, 217 s of two
    TRF plans.  Each part of its claim is asserted per push elsewhere: the
    reset of this very cell by
    ``test_three_escaped_angles_put_the_whole_cell_back_at_its_start``, and
    the reset inside ``fit`` by the injected escape (``lebail_pair_fits``).
    What this row alone shows is a fit walking into the guard unaided, and
    that is kept in the nightly's full suite."""
    import rietx as rx
    from rietx.schemas.structure import lebail_scaffold
    from tests._synthetic_silicon import silicon_pattern

    # through a file, as the report reproduced it: the trajectory of this fit
    # is pattern-dependent and the 4-decimal 2θ column is part of the pattern
    path = tmp_path / "si_flat.xy"
    pattern = silicon_pattern("flat")
    np.savetxt(path, np.c_[pattern.two_theta, pattern.intensity], fmt="%.4f %.0f")
    data = rx.read_pattern(path)
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.background = rx.background.auto_background(data).background
    structure = lebail_scaffold("P 1", TRICLINIC)
    findings = []
    for plan in ("profile_only", "lab_bragg_brentano"):
        # TRF, because its trajectory is the one that reaches the guard, on
        # every start tried.  Under LM, the default since WP-1938, the wrong
        # cell stays within 0.01 Å of its start (Rwp 0.3316 at three starts
        # 1e-14 apart) and the guard is never asked.
        ref = rx.Refinement(structure, ins, history=False, solver="trf")
        result = ref.fit(data, mode="lebail", plan=plan, telemetry=False,
                         two_theta_limits=(8.0, 70.0))
        # a result came back with numbers in it, which is the claim; how good
        # it is is not, since the cell is wrong on purpose.  Under TRF rounding
        # picks where the widths go: three starts 1e-14 apart read Rwp 127.7,
        # 0.33 and 7.8e6 after profile_only (WP-1938, macOS arm64), and Linux
        # CI once read 1.1e9.  All are the same non-fit, so no bar on Rwp can
        # pass.
        assert math.isfinite(float(result.statistics.rwp))
        assert float(result.statistics.rwp) > 0.0
        findings += [d for d in result.diagnostics if d.code == "CELL_RUNAWAY"]
        # fit plot for visual inspection (tests/output/, gitignored)
        from pathlib import Path

        from rietx.viz.plots import plot_result
        out = Path(__file__).parent / "output"
        out.mkdir(exist_ok=True)
        plot_result(result, path=str(out / f"cell_runaway_p1_lebail_{plan}.png"))
        structure, ins = ref.fitted_structure, ref.fitted_instrument
    # pin that the runaway guard was exercised, and that it put the cell back
    assert findings, "no CELL_RUNAWAY fired: the fit no longer reaches the guard"
    assert all("restored to this stage's starting values" in d.message
               for d in findings), [d.message for d in findings]


def test_two_solves_driven_escapes_merge_by_driver_once():
    """A stage that solves twice names each driving coefficient once.

    ``refine._merge_unresolved`` is the one rule both runners call after the
    second solve (WP-2028 task 7): a driver that escapes in both solves is one
    entry, its dependents the sorted union; a driver from one solve alone is
    kept, in first-seen order.  No fit in the suite reaches a second-solve
    escape on either runner, so the rule is pinned here directly.
    """
    import sys

    refine = sys.modules["rietx.refine"]
    multi = sys.modules["rietx.multi"]
    assert multi._merge_unresolved is refine._merge_unresolved
    first = [("vars.a_0", ["phases.0.cell.a"]), ("vars.c_1", ["phases.0.cell.c"])]
    second = [("vars.a_0", ["hist.1.phases.0.cell.a"]),
              ("vars.b_0", ["phases.0.cell.b"])]
    assert refine._merge_unresolved(first, second) == [
        ("vars.a_0", ["hist.1.phases.0.cell.a", "phases.0.cell.a"]),
        ("vars.c_1", ["phases.0.cell.c"]),
        ("vars.b_0", ["phases.0.cell.b"])]
    assert refine._merge_unresolved(first, []) == first
    assert refine._merge_unresolved([], second) == second
