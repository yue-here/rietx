"""Sequential (in-situ / parametric) refinement of a series — WP-0505.

Two synthetic series carry these tests, both built from the LaB6 model that
``test_refine_synthetic`` uses:

``thermal_series``
    a clean linear cell expansion — the only place where the *true* trajectory
    is known, so it is where the trajectory machinery is actually validated.
``jump_series``
    a nearly flat series with one step far larger than its own scatter, which
    ``SeriesResult.steps`` ranks first.

The chain's fences (reseed, path dependence) never alter a
fitted value, so every test here asserts on the reported diagnostics and on
values that were fitted independently of them.
"""

import json
from typing import get_args

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.optimize.cancel import CancelToken
from rietx.params.vector import AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import RefinedParameter, Statistics
from rietx.schemas.sequential import SeriesEntry, SeriesResult, SeriesStep
from rietx.schemas.structure import Atom
from rietx.sequential import (
    FIRST_RUNG_FACTOR,
    SequentialRefinement,
    _better,
    _carry_into,
    _collapse,
    _entry_from_result,
    _labels_for,
    _path_dependence_diagnostics,
    _reseed_needed,
    _series_steps,
    _width_growth_diagnostics,
    refine_sequential,
)
from rietx.strategy import staged
from tests.test_schemas import make_lab6

WAVELENGTH = 0.4139
A0 = 4.15660
TRUE_ZERO = 0.008
TRUE_W = 2.5e-4
TRUE_SCALE = 5e-4
TRUE_BKG = [40.0, -6.0, 1.5]

#: fractional cell expansion per step of the thermal series.  0.05 % shifts a
#: 20° peak by ~0.01°, comparable with the ~0.016° FWHM here, so successive
#: patterns are within each other's capture range — a series a warm start can
#: legitimately walk.
RAMP = 5e-4
#: temperatures the ramp is labelled with (the series coordinate)
TEMPERATURES = [300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]


def _simulate(a: float, *, seed: int, biso: float = 0.4,
              scale: float = TRUE_SCALE, tt_max: float = 24.0) -> rx.PatternData:
    """One pattern of the series at cell edge ``a``, with Poisson noise.
    ``scale=0`` is a blank frame: the background and its noise alone.
    ``tt_max`` ends the 0.005° grid begun at 3°: 18.0 gives the 3 000 points a
    synthetic library uses (WP-1325's solver measurements)."""
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = a
    for atom in structure.phases[0].atoms:
        atom.biso.value = biso
    structure.phases[0].scale.value = scale
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])

    tt = np.arange(3.0, tt_max, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _start_models():
    """The starting model: cell 0.1 % off, no zero shift, flat background."""
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = A0 * 1.001
    structure.phases[0].scale.value = TRUE_SCALE * 1.5
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = 0.0
    ins.profile.w.value = TRUE_W * 1.5
    ins.background = BackgroundChebyshev.with_terms(3)
    return structure, ins


@pytest.fixture(scope="module")
def thermal_patterns():
    """A 7-pattern ramp: a expands linearly by RAMP per step."""
    return [_simulate(A0 * (1.0 + RAMP * k), seed=11 + k)
            for k in range(len(TEMPERATURES))]


@pytest.fixture(scope="module")
def thermal_series(thermal_patterns):
    return _thermal_series(thermal_patterns)


@pytest.fixture(scope="module")
def jump_patterns():
    """Six patterns at one cell, then a step 20× the series' own scatter.

    The step (2e-3 Å) is far below the peak capture range, so *both* the warm
    and the cold fit find it easily — the steps are about the trajectory,
    not about whether an individual fit succeeded.
    """
    flat = [_simulate(A0, seed=31 + k) for k in range(3)]
    stepped = [_simulate(A0 + 2e-3, seed=41 + k) for k in range(3)]
    return flat + stepped


# -- the trajectory: recovered against a known truth ----------------------

def test_series_recovers_the_injected_thermal_expansion(thermal_series):
    """The headline: the fitted a(T) reproduces the injected linear ramp.

    Checked as a *slope*, not point by point: the series was generated with a
    constant fractional expansion per step, and recovering that coefficient is
    what an in-situ user takes away.
    """
    assert len(thermal_series) == len(TEMPERATURES)
    assert all(e.status == "converged" for e in thermal_series)

    traj = thermal_series.trajectory("phases.0.cell.a")
    x, value, sd = traj.arrays()
    assert traj.x_label == "T (K)"
    assert np.allclose(x, TEMPERATURES)
    assert np.all(np.isfinite(sd)) and np.all(sd > 0)

    # injected: a(T) = A0·(1 + RAMP·k), one k per 100 K
    truth = A0 * (1.0 + RAMP * np.arange(len(TEMPERATURES)))
    assert np.allclose(value, truth, atol=max(5 * float(sd.max()), 1e-4))

    slope = np.polyfit(x, value, 1)[0]
    expected = A0 * RAMP / 100.0          # Å per K
    assert slope == pytest.approx(expected, rel=0.05)


def test_tied_cell_edges_travel_with_the_series(thermal_series):
    """Cubic b, c are tied to a, so they must appear in every trajectory."""
    a = thermal_series.trajectory("phases.0.cell.a")
    for name in ("b", "c"):
        other = thermal_series.trajectory(f"phases.0.cell.{name}")
        assert len(other) == len(a)
        assert np.allclose(other.arrays()[1], a.arrays()[1])
    # ... and `paths()` keeps them: tied is not the same as undetermined
    assert "phases.0.cell.b" in thermal_series.paths()
    assert "phases.0.cell.b" not in thermal_series.paths(varied_only=True)


def test_series_axis_defaults_to_the_pattern_index(thermal_patterns):
    """No coordinate given ⇒ the axis is the index, and x_label says so."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:2], structure, ins)
    assert series.x_label == "index"
    assert series.x == [0.0, 1.0]
    assert series.labels == ["p000", "p001"]


def test_the_table_header_has_no_duplicate_column(thermal_series):
    """`x_label` is a label; a header is a set of keys, and they collided.

    `to_table` names the axis column after `x_label`, which defaults to
    `"index"` — the name the first column already has. The default header was
    `['index', 'label', 'index', …]`, so anything keying by name collided
    (pandas silently renames the second to `index.1`) while anything keying by
    position was fine. The axis column now falls back to `x` when its label is
    already taken, and the column count, order and meaning are unchanged
    (WP-1076).
    """
    plain = SeriesResult(entries=list(thermal_series.entries))
    assert plain.x_label == "index"
    header, rows = plain.to_table(paths=["phases.0.cell.a"])
    assert len(set(header)) == len(header), header
    assert header[:7] == ["index", "label", "x", "status", "rung", "rwp", "gof"]
    assert [r[0] for r in rows] == [e.index for e in plain.entries]
    assert [r[2] for r in rows] == plain.x

    # a real coordinate is used verbatim, which is the whole point of the field
    named = SeriesResult(entries=list(thermal_series.entries), x_label="T (K)")
    assert named.to_table(paths=[])[0][2] == "T (K)"


def test_every_entry_carries_per_phase_bragg_agreement(thermal_series):
    """The signal existed per pattern and was dropped at the series boundary.

    This asserts only that: every entry of a Rietveld chain carries a row per
    phase, populated. What the numbers *mean* is deliberately not claimed here —
    a trace phase's R_B is not comparable with the major phase's and a low one
    is consistent with a self-fulfilling partition (``structure_r_factors``,
    WP-1069), so a test asserting a threshold would be asserting an
    interpretation the index does not support.
    """
    for entry in thermal_series.entries:
        assert entry.phase_agreement, f"entry {entry.index} carries none"
        for agreement in entry.phase_agreement:
            assert agreement.n_reflections > 0
            # r_bragg is float | None -- None for a phase with no partitionable
            # scattering power -- so `>= 0.0` would raise TypeError rather than
            # fail readably on the case this test is here to catch.
            assert agreement.r_bragg is not None
            assert agreement.r_bragg >= 0.0


def test_phase_agreement_carries_the_underlying_results_values(thermal_patterns):
    """Value equality with the result's own rows, which is what a consumer reads.

    Not "copies rather than recomputes": an exact recomputation would pass this
    too, and the assertion cannot tell them apart. The claim worth pinning is
    the one it makes — a reader of the entry and a reader of the result see the
    same numbers — plus the *independence* of the copy, which value equality
    alone would miss.
    """
    structure, ins = _start_models()
    result = rx.refine(thermal_patterns[0], structure, ins, plan="mccusker_default")
    entry = _entry_from_result(0, "one", None, result)
    assert [(a.name, a.r_bragg, a.r_f, a.n_reflections) for a in entry.phase_agreement] == \
           [(a.name, a.r_bragg, a.r_f, a.n_reflections) for a in result.phase_agreement]
    # a deep copy, so mutating the result cannot reach an entry already recorded
    assert all(a is not b for a, b in
               zip(entry.phase_agreement, result.phase_agreement, strict=True))


def test_a_lebail_entry_carries_no_agreement(thermal_patterns):
    """Empty outside Rietveld, for the reason it is empty on the result there:
    in Le Bail the partition *is* the fit, so I(obs) would be compared with
    itself."""
    structure, ins = _start_models()
    result = rx.refine(thermal_patterns[0], structure, ins,
                       mode="lebail", plan="profile_only")
    assert _entry_from_result(0, "one", None, result).phase_agreement == []


def test_labels_are_made_unique():
    """Labels become history file names, so duplicates cannot be tolerated."""
    blank = [rx.PatternData(two_theta=[1.0, 2.0], intensity=[1.0, 1.0])
             for _ in range(3)]
    assert _labels_for(blank, ["a", "a", "b"]) == ["a", "a_1", "b"]
    with pytest.raises(ValueError, match="labels has 2 entries"):
        _labels_for(blank, ["a", "b"])


# -- warm-start mechanics -------------------------------------------------

def test_carry_globs_move_only_matching_paths():
    """`carry` is per-parameter, and a narrow glob must not break a tie."""
    start_s, start_i = _start_models()
    fitted_s, fitted_i = _start_models()
    for name in ("a", "b", "c"):
        getattr(fitted_s.phases[0].cell, name).value = A0 * 1.02
    fitted_i.profile.w.value = 9e-4
    fitted_i.zero_shift.value = 0.02

    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["instrument.profile.*"])
    assert start_i.profile.w.value == pytest.approx(9e-4)
    assert start_i.zero_shift.value == pytest.approx(0.0)      # not carried
    assert start_s.phases[0].cell.a.value == pytest.approx(A0 * 1.001)

    # carrying only `cell.a` must still leave b and c equal to it: the cubic
    # tie is re-derived from its source rather than left at the old value
    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["phases.*.cell.a"])
    cell = start_s.phases[0].cell
    assert cell.a.value == pytest.approx(A0 * 1.02)
    assert cell.b.value == pytest.approx(cell.a.value)
    assert cell.c.value == pytest.approx(cell.a.value)


# -- a refined coordinate crosses the boundary (WP-1333) ------------------

B_X = "phases.0.atoms.1.x"
B_DOF = "phases.0.atoms.1.dof.0"


def test_a_refined_coordinate_is_carried_as_its_sites_displacement():
    """Copying a coordinate's DOF carries nothing: every build rederives it to 0.

    The boron sits on 6f (x, ½, ½), one DOF reaching ``x``.  Until WP-1333 a
    fitted 0.2100 came back as the start model's 0.1993 under ``carry=["*"]``,
    while ``cell.a`` beside it carried: the DOF was copied at 0.0 and the
    coordinate re-derived from this model's own anchor.
    """
    fitted_s, fitted_i = _start_models()
    fitted_s.phases[0].atoms[1].x.value = 0.2100
    for name in ("a", "b", "c"):
        getattr(fitted_s.phases[0].cell, name).value = A0 * 1.02

    start_s, start_i = _start_models()
    assert _carry_into(start_s, start_i, (fitted_s, fitted_i), ["*"]) == [B_DOF]
    boron = start_s.phases[0].atoms[1]
    assert boron.x.value == pytest.approx(0.2100, abs=1e-15)
    assert (boron.y.value, boron.z.value) == (0.5, 0.5)
    assert start_s.phases[0].cell.a.value == pytest.approx(A0 * 1.02)

    # the DOF's own path licenses the carry too: it is the name a plan frees
    start_s, start_i = _start_models()
    _carry_into(start_s, start_i, (fitted_s, fitted_i), ["phases.*.atoms.*.dof.*"])
    assert start_s.phases[0].atoms[1].x.value == pytest.approx(0.2100, abs=1e-15)

    # and a glob naming neither leaves the atom where the start model put it
    start_s, start_i = _start_models()
    assert _carry_into(start_s, start_i, (fitted_s, fitted_i),
                       ["phases.*.cell.*"]) == []
    assert start_s.phases[0].atoms[1].x.value == 0.1993


def _with_an_8g_atom(x: float, y: float, z: float):
    structure, instrument = _start_models()
    structure.phases[0].atoms.append(Atom(
        label="O", species="O", x=Parameter(value=x), y=Parameter(value=y),
        z=Parameter(value=z)))
    return structure, instrument


def test_a_site_moves_as_a_site_whatever_the_glob_names():
    """8g (x, x, x) in Pm-3m: one DOF, three rows, and they move together.

    A glob naming ``x`` alone carries the DOF, so ``y`` and ``z`` follow as its
    rows.  Carried row by row instead, the atom would leave the diagonal, and
    the next build would find it on a general position with three DOFs: the
    model changed, and nothing said so.  A fitted target that is off the site
    is projected onto it, not followed off it.
    """
    start_s, start_i = _with_an_8g_atom(0.30, 0.30, 0.30)
    _carry_into(start_s, start_i, _with_an_8g_atom(0.32, 0.32, 0.32),
                ["phases.*.atoms.2.x"])
    oxygen = start_s.phases[0].atoms[2]
    assert [oxygen.x.value, oxygen.y.value, oxygen.z.value] == pytest.approx(
        [0.32] * 3, abs=1e-15)

    start_s, start_i = _with_an_8g_atom(0.30, 0.30, 0.30)
    _carry_into(start_s, start_i, _with_an_8g_atom(0.32, 0.30, 0.34), ["*"])
    oxygen = start_s.phases[0].atoms[2]
    assert [oxygen.x.value, oxygen.y.value, oxygen.z.value] == pytest.approx(
        [0.32] * 3, abs=1e-15)
    dofs = [e.path for e in ParameterTable(start_s, start_i).entries
            if e.path.startswith("phases.0.atoms.2.dof.")]
    assert dofs == ["phases.0.atoms.2.dof.0"]


def test_a_carried_anchor_is_reanchored_once_per_table():
    """``reanchor_dofs`` subtracts from a stored constant, so it is guarded.

    The stored 0.2100 was written while the variable driving the DOF held
    0.0107, and this table declares it at 0.  The anchor moves back by that
    contribution, so the coordinate reads 0.1993 now and 0.2100 once the
    variable is warmed.  A second call would walk it back again, so the table
    refuses it; a source the caller does not name contributed what it holds
    now, which is nothing to correct.
    """
    structure, instrument = _start_models()
    structure.phases[0].atoms[1].x.value = 0.2100
    table = ParameterTable(structure, instrument)
    table.add_parameter("vars.dx", 0.0, lo=-1.0, hi=1.0)
    table.set_tie(B_DOF, AffineTie(terms=(("vars.dx", 1.0),), const=0.0))
    table.rebase_anchored_dofs([B_DOF])
    by_path = {e.path: e for e in table.entries}
    assert by_path[B_X].value == pytest.approx(0.2100, abs=1e-15)

    assert table.reanchor_dofs([B_DOF], {}) == []
    assert table.reanchor_dofs([B_DOF], {"vars.dx": 0.0107}) == [B_DOF]
    assert by_path[B_X].value == pytest.approx(0.1993, abs=1e-15)
    assert table.reanchor_dofs([B_DOF], {"vars.dx": 0.0107}) == []
    assert by_path[B_X].value == pytest.approx(0.1993, abs=1e-15)

    by_path["vars.dx"].value = 0.0107
    table.refresh_ties()
    assert by_path[B_X].value == pytest.approx(0.2100, abs=1e-15)


#: the boron's start, off the patterns' 0.1993 by enough that pattern 1's fit
#: moves it measurably
_B_START = 0.19


def _coordinate_plan(glob: str) -> staged.RefinementPlan:
    return staged.RefinementPlan(stages=[
        *staged.RefinementPlan.mccusker_default().stages,
        staged.Stage("xyz", [glob])])


@pytest.mark.parametrize("tie, carry", [
    (False, ["*"]),
    (True, ["*"]),
    (True, ["phases.*", "instrument.*"]),
], ids=["free", "tied-to-a-variable", "variable-not-carried"])
def test_a_refined_coordinate_starts_the_next_pattern(thermal_patterns, tie, carry):
    """The chain half: pattern 2 starts where pattern 1's fit left the atom.

    Free, the DOF's displacement is carried.  Tied by the hook to a variable,
    the carried coordinate already holds that variable's fitted displacement,
    and the warmed variable must not add it a second time: without
    ``_reanchor_carried`` pattern 2 started the boron at 0.2092, not 0.1996.
    The anchor carries what the fit put there and a tie carries what its
    source says, so a variable the glob excludes restarts at its declaration
    and takes the coordinate back to the start model with it, keeping one
    anchor for the whole trajectory of ``vars.dx``.
    """
    started: list[tuple[float, float | None]] = []

    def constrain(index, ref):
        if tie:
            ref.add_variable("dx", 0.0, min=-0.05, max=0.05)
            ref.tie(B_DOF, "vars.dx")
        inner = ref.fit

        def fit(*args, **kwargs):     # after the carry, which runs on return
            started.append((ref.structure.phases[0].atoms[1].x.value,
                            ref._variables["dx"].value if tie else None))
            return inner(*args, **kwargs)

        ref.fit = fit

    structure, instrument = _start_models()
    structure.phases[0].atoms[1].x.value = _B_START
    series = refine_sequential(
        thermal_patterns[:2], structure, instrument, carry=carry,
        plan=_coordinate_plan("vars.*" if tie else "phases.*.atoms.*.dof.*"),
        constrain=constrain)
    fitted = {p.path: p.value for p in series[0].parameters}
    assert abs(fitted[B_X] - _B_START) > 5e-3     # the fit moved it

    if carry == ["*"]:
        assert started[1][0] == pytest.approx(fitted[B_X], abs=1e-12)
        if tie:
            assert started[1][1] == fitted["vars.dx"]
    else:
        assert started[1] == pytest.approx((_B_START, 0.0), abs=1e-12)


# -- user constraints across the chain (WP-1441, issue #376) --------------

#: the default plan plus the displacement parameters the constraint tests tie
#: together and the variable driving them.  ``_CHEAP`` cannot serve — a
#: constraint nothing refines is one no assertion can see — and the
#: displacement stage alone cannot either: on this series it leaves Rwp at
#: 0.985 against 0.041 here, and a tie measured on a fit that did not converge
#: says nothing about ties.
_TIED = staged.RefinementPlan(stages=[
    *staged.RefinementPlan.mccusker_default().stages,
    staged.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"])])


def _tie_the_two_biso(index, ref):
    """The issue's own constraint: both sites' Biso are one parameter."""
    ref.add_variable("B_all", 0.4, min=0.0, max=5.0)
    ref.tie_equal(["phases.0.atoms.*.biso"], source="vars.B_all")


def test_a_tie_declared_in_constrain_holds_on_every_pattern(thermal_patterns):
    """Issue #376: the tie that held pattern 1 together holds pattern 2.

    Before the ``constrain`` hook there was no object to declare it on — a
    tie lives on ``Refinement._ties`` and in no model, so ``carry`` could not
    reach it and ``prepare`` ran one line before the ``Refinement`` existed.
    Asserted as *equality of the tied pair*, not as the presence of a tie: the
    pair coming back equal on every pattern is the whole content of the ask.
    """
    from pathlib import Path

    from rietx.viz.plots import plot_result

    runner = SequentialRefinement(*_start_models())
    series = runner.fit(thermal_patterns[:3], plan=_TIED,
                        constrain=_tie_the_two_biso)
    assert len(series) == 3
    for entry in series.entries:
        values = {p.path: p.value for p in entry.parameters}
        assert values["phases.0.atoms.0.biso"] == values["phases.0.atoms.1.biso"]
        # and both are the variable driving them, not merely each other
        assert values["vars.B_all"] == values["phases.0.atoms.0.biso"]

    # obs/calc/diff PNGs to tests/output/ (gitignored), full range and a
    # low-angle zoom — house convention, and a tied fit is exactly the kind
    # whose Rwp can stay respectable while a region goes wrong
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    for k, result in enumerate(runner.results_):
        plot_result(result, path=str(out / f"sequential_tied_biso_p{k}.png"))
        plot_result(result, path=str(out / f"sequential_tied_biso_p{k}_zoom.png"),
                    two_theta_range=(3.0, 10.0))


def test_a_hold_declared_in_constrain_reaches_every_pattern(thermal_patterns):
    """The third fact that lives in no model (WP-1435), through #376's hook.

    A hold is neither a value nor a relation, so ``carry`` cannot move it and
    ``prepare`` runs before the ``Refinement`` exists — the same absence a
    tie had, and it inherits the same answer rather than a new channel.

    Asserted on the trajectory as well as the values, because that is what a
    series consumer reads: a held path is not a measurement of any pattern,
    so it has no trajectory to plot.
    """
    from pathlib import Path

    from rietx.viz.plots import plot_result

    def hold_the_cell(index, ref):
        ref.hold("phases.0.cell.*")

    runner = SequentialRefinement(*_start_models())
    declared = runner.structure.phases[0].cell.a.value
    series = runner.fit(thermal_patterns[:3], plan=_TIED,
                        constrain=hold_the_cell)

    assert len(series) == 3
    for entry in series.entries:
        paths = {p.path for p in entry.parameters}
        assert "phases.0.cell.a" not in paths, "a held value is not a measurement"
        assert any(d.code == "HOLD_BLOCKED_PLAN" for d in entry.diagnostics)
    assert series.trajectory("phases.0.cell.a").value == []

    for structure in runner.fitted_structures:
        assert structure.phases[0].cell.a.value == declared

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    for k, result in enumerate(runner.results_):
        plot_result(result, path=str(out / f"sequential_held_cell_p{k}.png"))
        plot_result(result, path=str(out / f"sequential_held_cell_p{k}_zoom.png"),
                    two_theta_range=(3.0, 10.0))


def test_an_untied_series_leaves_the_same_pair_free_and_unequal(thermal_patterns):
    """The control the test above needs: without the hook they diverge.

    Same patterns, same plan, no ``constrain`` — so an equality that the tied
    run reports is the tie's doing and not the data's.
    """
    series = refine_sequential(thermal_patterns[:3], *_start_models(),
                               plan=_TIED)
    for entry in series.entries:
        values = {p.path: p.value for p in entry.parameters}
        assert values["phases.0.atoms.0.biso"] != values["phases.0.atoms.1.biso"]
        assert "vars.B_all" not in values


def test_a_named_variable_warm_starts_under_the_carry_globs(thermal_patterns):
    """``vars.<name>`` is an ordinary dot-path, so ``carry`` governs it.

    A variable lives on the register and in no model, so ``_carry_into`` — which
    reads a ``ParameterTable`` built from the previous fitted pair — cannot see
    one, and ``carry=["*"]`` would be a claim nothing kept (WP-1076's shape).
    Observed at the *start* of each fit rather than at its end, because what
    the carry moves is a starting point; the answers agree either way.
    """
    started: dict[str, list[float]] = {}

    def declare(index, ref, key):
        _tie_the_two_biso(index, ref)
        inner = ref.fit

        def fit(*args, **kwargs):     # after the carry, which runs on return
            started.setdefault(key, []).append(ref._variables["B_all"].value)
            return inner(*args, **kwargs)

        ref.fit = fit

    wide = refine_sequential(
        thermal_patterns[:3], *_start_models(), plan=_TIED,
        constrain=lambda i, r: declare(i, r, "wide"))
    refine_sequential(
        thermal_patterns[:3], *_start_models(), plan=_TIED,
        carry=["phases.*", "instrument.*"],
        constrain=lambda i, r: declare(i, r, "narrow"))

    fitted = [{p.path: p.value for p in e.parameters}["vars.B_all"]
              for e in wide.entries]
    # pattern 1 has nothing to warm from; 2 and 3 start where their
    # predecessor finished
    assert started["wide"] == [0.4] + fitted[:2]
    # a glob that does not match ``vars.*`` leaves every pattern at the
    # declaration, which is what "restarts from the initial models" means here
    assert started["narrow"] == [0.4, 0.4, 0.4]


def test_a_variable_tied_to_others_is_carried_by_its_sources(thermal_patterns):
    """The multi-source form the manual documents, driven from a chain.

    ``set_values`` refuses a tied path — setting its sources is what the caller
    meant — so a variable the hook ties to others must not be offered to the
    carry: pattern 1 fitted and pattern 2 raised. It follows its sources, and
    those are carried, so dropping it moves no starting point.
    """
    started: list[tuple[float, float]] = []

    def constrain(index, ref):
        ref.add_variable("B_base", 0.4, min=0.0, max=5.0)
        ref.add_variable("B_extra", 0.1, min=0.0, max=5.0)
        ref.add_variable("B_total", 0.5, min=0.0, max=10.0)
        ref.tie("vars.B_total", {"vars.B_base": 1.0, "vars.B_extra": 1.0})
        ref.tie_equal(["phases.0.atoms.*.biso"], source="vars.B_total")
        inner = ref.fit

        def fit(*args, **kwargs):     # after the carry, which runs on return
            started.append((ref._variables["B_base"].value,
                            ref._variables["B_total"].value))
            return inner(*args, **kwargs)

        ref.fit = fit

    series = refine_sequential(thermal_patterns[:2], *_start_models(),
                               plan=_TIED, constrain=constrain)
    assert len(series) == 2
    fitted = {p.path: p.value for p in series[0].parameters}
    # the sources crossed the boundary, and the tied variable followed them
    # there rather than being offered to ``set_values`` and refused
    assert started[1][0] == fitted["vars.B_base"]
    assert started[1][1] == pytest.approx(started[1][0] + fitted["vars.B_extra"])


def test_a_quarantined_pattern_seeds_no_variable_either(thermal_patterns):
    """The warm start of a variable is the chain's rule, not the caller's.

    A caller could warm-start a variable by hand inside ``constrain`` — they
    hold the previous result — but only the chain knows which pattern was
    *accepted*: a diverged one is stepped over (WP-1051), and a hand-rolled
    warm start would seed the next pattern from the fit that failed. So the
    carry reads the same ``previous`` the models do, and this pins it: p001 is
    dictated to diverge on every rung, and p002 starts where p000 finished.
    """
    started: list[tuple[int, float]] = []

    def declare(index, ref):
        _tie_the_two_biso(index, ref)
        inner = ref.fit

        def fit(*args, **kwargs):     # after the carry, which runs on return
            started.append((index, ref._variables["B_all"].value))
            return inner(*args, **kwargs)

        ref.fit = fit

    runner = _dictate(SequentialRefinement(*_start_models()),
                      {"p000": [("converged", 0.10)],
                       "p001": [("diverged", 0.001)],
                       "p002": [("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:3], plan=_TIED, reseed_factor=1.0,
                        constrain=declare)
    assert series[1].status == "diverged"

    p000 = {p.path: p.value for p in series[0].parameters}["vars.B_all"]
    assert p000 != 0.4                      # it moved, or this asserts nothing
    # p000 declares; p001 climbs the whole ladder from p000, its cold rung
    # warming from nothing at all; p002 warms from p000 and not from p001
    assert started == [(0, 0.4), (1, p000), (1, p000), (1, 0.4), (2, p000)]


def test_symmetry_outranks_a_constrain_tie_on_every_pattern(thermal_patterns):
    """Issue #376's open question: a user tie naming a symmetry-tied path.

    The hook runs against the pattern's *own* table, and every table rederives
    the symmetry ties from the space group, so the refusal is the one a single
    ``Refinement`` gives and it happens before the first fit. There is no
    pattern on which the same declaration would quietly take.
    """
    def tie_onto_symmetry(index, ref):
        ref.tie("phases.0.cell.b", "phases.0.cell.c")   # cubic: b already ← a

    with pytest.raises(ValueError, match="symmetry outranks a user tie"):
        refine_sequential(thermal_patterns[:2], *_start_models(),
                          plan=_CHEAP, constrain=tie_onto_symmetry)


def test_a_raise_in_constrain_is_the_callers_error(thermal_patterns):
    """The hook is the caller's code and runs outside every guard.

    ``prepare``'s rule, and for its reason: a constraint that did not happen is
    not a series to report on, so it ends the run rather than being folded into
    a diagnostic.
    """
    def boom(index, ref):
        raise KeyError("the caller's own mistake")

    with pytest.raises(KeyError, match="the caller's own mistake"):
        refine_sequential(thermal_patterns[:2], *_start_models(),
                          plan=_CHEAP, constrain=boom)


def test_collapse_unions_the_plans_turn_on_globs():
    plan = rx.RefinementPlan.mccusker_structural()
    single = _collapse(plan)
    assert len(single.stages) == 1
    for stage in plan.stages:
        for glob in stage.turn_on:
            assert glob in single.stages[0].turn_on


def test_collapse_keeps_every_plan_level_setting():
    """The collapsed warm refit is the plan compressed, not another protocol,
    so every plan-level field crosses it: one dropped here runs a series at
    its default, as the absent-phase hold's threshold would (WP-2002, B1)."""
    import dataclasses

    plan = dataclasses.replace(
        rx.RefinementPlan.mccusker_structural(), correlation_guard=0.9,
        intermediate_ftol=1e-4, lebail_passes=3, phase_support_sigma=None)
    single = _collapse(plan)
    for f in dataclasses.fields(plan):
        if f.name != "stages":
            assert getattr(single, f.name) == getattr(plan, f.name), f.name


def test_a_warm_refit_lifts_no_carried_floor_value():
    """WP-1938: the collapsed warm refit carries no ``Stage.seed``.

    ``seed_floored`` lifts every freed row sitting exactly on its floor, and
    on a warm start those rows are the neighbour's converged zeros.  Carrying
    the plan's 0.3 lifted pattern 1's converged ``profile.y`` and
    ``extinction`` to 0.3 on the LaB₆ ramp and ended at χ²_red 1.05828
    against 1.05145.  ``strain_seed`` still carries, since an all-zero
    Stephens block cannot move without it and ``seed_stephens`` touches no
    other."""
    plan = rx.RefinementPlan.mccusker_structural()
    assert max(s.seed for s in plan.stages) > 0.0     # the plan does seed
    assert _collapse(plan).stages[0].seed == 0.0
    stephens = rx.RefinementPlan.lab_sample_refine()
    assert max(s.strain_seed for s in stephens.stages) > 0.0
    assert _collapse(stephens).stages[0].strain_seed == max(
        s.strain_seed for s in stephens.stages)

    # and the table: a converged zero stays where the neighbour left it,
    # where the plan's own largest seed would have lifted it
    structure, ins = _start_models()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    freed = table.set_vary(_collapse(plan).stages[0].turn_on, True)
    assert table.seed_floored(freed, _collapse(plan).stages[0].seed) == []
    assert "phases.0.extinction" in table.seed_floored(
        freed, max(s.seed for s in plan.stages))


def test_refit_single_agrees_with_refit_stages(thermal_patterns):
    """The compressed refit reaches the same cell — it is a speed knob, not a
    different protocol.  The iteration counts are reported, never asserted:
    which one is cheaper is a measurement (see the WP acceptance)."""
    patterns = thermal_patterns[:4]
    staged = refine_sequential(*(patterns, *_start_models()), refit="stages")
    single = refine_sequential(*(patterns, *_start_models()), refit="single")

    a_staged = np.asarray(staged.trajectory("phases.0.cell.a").value)
    a_single = np.asarray(single.trajectory("phases.0.cell.a").value)
    sd = np.nanmax(staged.trajectory("phases.0.cell.a").arrays()[2])
    assert np.allclose(a_staged, a_single, atol=5 * sd)
    print(f"\niterations: stages={staged.n_iterations} single={single.n_iterations}")


# -- the reseed fence -----------------------------------------------------

def test_reseed_decision_uses_the_median_not_the_previous():
    """One bad pattern must not ratchet the threshold and let its successors
    through, which is exactly what comparing against the previous Rwp would do."""
    good = _fake_result(0.10)
    assert not _reseed_needed(good, [], 1.25)
    assert not _reseed_needed(good, [0.09, 0.10, 0.11], 1.25)
    assert _reseed_needed(_fake_result(0.30), [0.09, 0.10, 0.11], 1.25)
    # a single outlier already accepted does not move a median
    assert _reseed_needed(_fake_result(0.30), [0.09, 0.10, 0.11, 0.90], 1.25)
    # divergence always reseeds, whatever the Rwp
    assert _reseed_needed(_fake_result(0.01, status="diverged"), [0.10], 1.25)


def test_better_prefers_convergence_then_rwp():
    assert _better(_fake_result(0.10), _fake_result(0.20))
    assert not _better(_fake_result(0.20), _fake_result(0.10))
    # a converged fit beats a diverged one even at a worse Rwp
    assert _better(_fake_result(0.30), _fake_result(0.05, status="diverged"))


def test_reseed_records_both_fits_and_emits_a_diagnostic(thermal_patterns):
    """End-to-end through the reseed branch, forced by a threshold no fit can
    clear (any Rwp above the running median triggers it).  What is asserted is
    the *bookkeeping*: the kept fit is the better one, the rejected warm Rwp is
    still reported, and the iterations of both count against the series."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins).fit(
        thermal_patterns[:3], reseed_factor=1.0)
    assert len(series) == 3
    for entry in series:
        if entry.reseeded:
            assert entry.rwp_warm is not None
            assert entry.statistics.rwp <= entry.rwp_warm
    reseeded = [e for e in series if e.reseeded]
    codes = [d.code for d in series.diagnostics]
    assert codes.count("SEQUENTIAL_RESEED") == len(reseeded)
    if reseeded:
        assert all("was refitted from the initial model" in d.message
                   for d in series.diagnostics if d.code == "SEQUENTIAL_RESEED")


def test_a_well_behaved_series_reseeds_nothing(thermal_series):
    assert not any(e.reseeded for e in thermal_series)
    codes = [d.code for d in thermal_series.diagnostics]
    assert "SEQUENTIAL_RESEED" not in codes
    # WP-1469's new half fires nothing on it: every fence recorded, none left
    # a pattern above it, and the steps are written, none re-measured cold
    assert "SEQUENTIAL_RWP_OUTLIER" not in codes
    assert thermal_series[0].rwp_fence is None
    assert all(e.rwp_fence is not None and not e.above_fence
               for e in thermal_series.entries[1:])
    assert thermal_series.steps
    assert all(s.cold_ratio is None for s in thermal_series.steps)
    # ... and no pattern climbed past its first rung: the first is cold because
    # it has no predecessor, every other one is the collapsed warm refit
    assert [e.rung for e in thermal_series] == ["cold"] + ["warm"] * 6
    assert all(len(e.rungs_tried) == 1 for e in thermal_series)


# -- the escalation ladder (WP-1051) --------------------------------------

def test_the_ladder_is_the_rungs_in_order_and_never_repeats_one():
    """Three rungs from a collapsed warm refit, **two** from a staged one.

    Under ``refit="stages"`` the first rung already *is* the staged plan from
    the warm state, so the middle rung would re-run an identical plan from an
    identical starting point — a deterministic repeat the series would pay a
    whole fit for.
    """
    from rietx.sequential import RUNGS, _ladder

    base = rx.RefinementPlan.mccusker_default()
    collapsed = _collapse(base)

    single = _ladder(base, collapsed, staged=False)
    assert [name for name, _, _ in single] == ["warm", "warm_staged", "cold"]
    assert [plan for _, plan, _ in single] == [collapsed, base, base]
    assert [warm for _, _, warm in single] == [True, True, False]

    stages = _ladder(base, base, staged=True)
    assert [name for name, _, _ in stages] == ["warm_staged", "cold"]
    assert [plan for _, plan, _ in stages] == [base, base]

    # the names are the vocabulary the schema and the panels quote
    assert set(RUNGS) == {name for name, _, _ in single}


def test_a_warm_rung_seeds_nothing_and_the_cold_one_keeps_the_plans_seeds():
    """Every warm rung starts from the neighbour's answer, so it takes no
    ``seed``: the roughness stage's 0.3 would lift a converged b = 0 off its
    floor.  The cold rung is the plan as written, and so is the first pattern.
    ``strain_seed`` survives everywhere (WP-1938 D11)."""
    from rietx.sequential import _ladder, _unseeded

    base = rx.RefinementPlan.mccusker_structural()
    assert any(s.seed for s in base.stages)
    strain = [s.strain_seed for s in base.stages]
    for staged_refit in (False, True):
        warm = _unseeded(base) if staged_refit else _collapse(base)
        for name, plan, is_warm in _ladder(base, warm, staged=staged_refit):
            if not is_warm:
                assert plan is base, name
                continue
            assert not any(s.seed for s in plan.stages), name
            if len(plan.stages) == len(base.stages):
                assert [s.strain_seed for s in plan.stages] == strain, name
            else:
                assert plan.stages[0].strain_seed == max(strain), name
    # a plan with nothing to drop comes back as itself
    unseeded = _unseeded(base)
    assert _unseeded(unseeded) is unseeded


def _dictate(runner, script):
    """Force what each attempt *reports*, leaving the fits themselves real.

    ``script`` maps a pattern label to the ``(status, rwp)`` its successive
    rungs will come back with; the last pair repeats if the ladder climbs
    further.  Every model, tree and node in the series is still the real one —
    what is stubbed is the verdict the chain reasons about, which is the only
    way to make "which rung ran" a deterministic assertion: with real Rwps two
    patterns of the same material differ by Poisson noise, so whether the fence
    fires on the third pattern is a coin flip.
    """
    real = runner._fit_one
    seen: dict[str, int] = {}

    def dictated(*args, **kw):
        ref, result = real(*args, **kw)
        label = args[1]
        if label in script:
            attempts = script[label]
            k = min(seen.get(label, 0), len(attempts) - 1)
            seen[label] = seen.get(label, 0) + 1
            result.status, result.statistics.rwp = attempts[k]
        return ref, result

    runner._fit_one = dictated
    return runner


def test_the_ladder_stops_at_the_first_rung_that_works(thermal_patterns):
    """Warm-staged rescues the pattern, so the cold rung never runs.

    The whole point of the middle rung: the warm start is worth ~1.8× fewer
    iterations than a cold staged refit, and discarding it was never shown to
    be necessary.  The bookkeeping has to say so — ``rung`` names the attempt
    the values came from, ``rungs_tried`` says it was not the only one, and
    ``reseeded`` stays **False** because a staged refit from the warm state is
    still warm-started, so the chain is unbroken here.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0)

    rescued = series[1]
    assert rescued.rungs_tried == ["warm", "warm_staged"]
    assert rescued.rung == "warm_staged"
    assert rescued.reseeded is False
    assert rescued.rwp_warm == pytest.approx(0.30)      # the rejected attempt
    assert rescued.statistics.rwp == pytest.approx(0.10)
    # no fence fires: the chain was never broken, only re-walked
    assert "SEQUENTIAL_RESEED" not in [d.code for d in series.diagnostics]
    # both attempts are charged to the pattern (the n_iterations contract)
    assert rescued.n_iterations > series[0].n_iterations


def test_the_cold_rung_is_reached_only_when_the_warm_ones_fail(thermal_patterns):
    """All three rungs, in order, and the cold one wins — the pre-WP-1051 path.

    ``reseeded`` and ``SEQUENTIAL_RESEED`` mean exactly what they meant before
    the ladder existed: the kept values did not come from the neighbour.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.28),
                                ("converged", 0.05)]})
    series = runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0)

    entry = series[1]
    assert entry.rungs_tried == ["warm", "warm_staged", "cold"]
    assert entry.rung == "cold"
    assert entry.reseeded is True
    assert entry.rwp_warm == pytest.approx(0.30)        # the *first* attempt
    assert [d.code for d in series.diagnostics] == ["SEQUENTIAL_RESEED"]


def test_a_rung_that_came_back_worse_is_not_kept(thermal_patterns):
    """Keep-best across all attempts, and the fence judges the best so far.

    A rung is an attempt, not a commitment: if the escalation lands worse than
    what it was escalating from, the earlier fit stands — and because the fence
    is then asked about *that* fit rather than the last one, the ladder keeps
    climbing instead of stopping on an improvement that never happened.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.90),
                                ("converged", 0.95)]})
    series = runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0)

    entry = series[1]
    assert entry.rungs_tried == ["warm", "warm_staged", "cold"]
    assert entry.rung == "warm"                       # the best of the three
    assert entry.statistics.rwp == pytest.approx(0.30)
    assert entry.reseeded is False and entry.rwp_warm == pytest.approx(0.30)


def test_the_first_rung_budget_comes_only_from_rungs_that_worked():
    """WP-1127's rule, in the one function that decides it.

    The sample is the accepted first rungs and nothing else, so a chain bounds
    nothing until one has worked — the cold fit is **not** evidence about a
    collapsed warm rung, which `_first_rung_budget`'s docstring measures.
    """
    from rietx.sequential import FIRST_RUNG_SAMPLES, _first_rung_budget

    # switched off: no factor, no bound, whatever the history says
    assert _first_rung_budget([50, 60, 70], None) is None
    # nothing has worked yet — the first warm pattern of a chain
    assert _first_rung_budget([], 3.0) is None
    # ... and a short sample is no better: its maximum is set by whichever
    # pattern happened to be cheapest, which is the one-evaluation margin that
    # took the thermal ramp's third pattern down on Linux
    assert FIRST_RUNG_SAMPLES == 3
    assert _first_rung_budget([8], 3.0) is None
    assert _first_rung_budget([8, 9], 3.0) is None
    # the bound is headroom over the most expensive converged rung, not the last
    assert _first_rung_budget([8, 9, 17], 3.0) == 51
    assert _first_rung_budget([17, 9, 8], 3.0) == 51
    assert _first_rung_budget([64, 35, 53], 3.0) == 192


def test_the_bound_caps_evaluations_and_never_raises_a_stage():
    """``Stage.max_iter`` is iterations and the budget is evaluations.

    The solver caps evaluations at ``max_iter × NFEV_PER_ITERATION``, so the
    budget divides before it is applied — and a stage already tighter than the
    bound is left alone, as the *same object*.
    """
    from rietx.optimize.least_squares import NFEV_PER_ITERATION
    from rietx.sequential import _bounded_plan

    plan = staged.RefinementPlan(stages=[
        staged.Stage("wide", ["phases.*.scale"], max_iter=100)])

    assert _bounded_plan(plan, None) is plan
    bounded = _bounded_plan(plan, 128)
    assert bounded is not plan
    assert bounded.stages[0].max_iter == 128 // NFEV_PER_ITERATION == 32
    assert plan.stages[0].max_iter == 100, "the caller's plan is not mutated"
    # a budget wider than the stage's own declaration changes nothing
    assert _bounded_plan(plan, 100 * NFEV_PER_ITERATION * 2) is plan
    # never zero: a bound tighter than one iteration still buys one
    assert _bounded_plan(plan, 1).stages[0].max_iter == 1


def test_a_bounded_first_rung_that_spends_its_bound_escalates(thermal_patterns):
    """The clause the bound makes necessary, and the default that does not.

    A rung that hits its evaluation cap comes back ``"max_iter"``, which
    :func:`_better` reads as merely not-diverged and :func:`_reseed_needed`
    does not test at all — so the fence, asked about a *good* Rwp, would keep
    it. Without forcing the escalation the bound would not make a failing rung
    cheap, it would make a **truncated fit acceptable**, which is the one way
    this could reach an answer.

    The second half is what pins the escalation to the bound rather than to a
    change of policy on ``max_iter``: the identical script with the bound
    switched off keeps the truncated rung, because a rung that spends the
    *plan's* own budget is not this WP's business and the ladder's behaviour
    there is what it always was.  ``first_rung_factor=None`` is that way back,
    and what a test pinning a pre-WP-1127 number declares.

    Five patterns, because the bound needs `FIRST_RUNG_SAMPLES` converged first
    rungs before it exists at all: p001-p003 supply them and p004 is the one
    that hits it.
    """
    script = {"p000": [("converged", 0.10)],
              "p001": [("converged", 0.10)],
              "p002": [("converged", 0.10)],
              "p003": [("converged", 0.10)],
              "p004": [("max_iter", 0.10), ("converged", 0.10)]}

    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins), dict(script))
    bounded = runner.fit(thermal_patterns[:5], plan=_CHEAP,
                         first_rung_factor=FIRST_RUNG_FACTOR)
    assert bounded[4].rungs_tried == ["warm", "warm_staged"]
    assert bounded[4].status == "converged"

    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins), dict(script))
    unbounded = runner.fit(thermal_patterns[:5], plan=_CHEAP,
                           first_rung_factor=None)
    assert unbounded[4].rungs_tried == ["warm"]
    assert unbounded[4].status == "max_iter"


def test_a_truncated_attempt_loses_to_one_that_ran_to_completion():
    """``_prefer``'s four cases, and the one that made it necessary.

    Equal Rwp is not a corner: it is what a dictated ladder produces and what
    two rungs of the same warm state can genuinely reach. ``_better`` alone
    keeps the earlier attempt there, which for a bounded first rung means
    keeping the fit *this ladder* cut short over one that finished.
    """
    from rietx.sequential import _prefer

    finished = _fake_result(0.10)
    cut = _fake_result(0.10, status="max_iter")
    # nothing to compare against yet
    assert _prefer(cut, True, None, False) is True
    # the whole point: at equal Rwp the untruncated attempt wins
    assert _prefer(finished, False, cut, True) is True
    assert _prefer(cut, True, finished, False) is False
    # neither truncated — _better's ordinary Rwp rule, unchanged
    assert _prefer(_fake_result(0.09), False, finished, False) is True
    assert _prefer(_fake_result(0.11), False, finished, False) is False


def test_the_bound_is_inert_under_refit_stages(thermal_patterns):
    """Under ``refit="stages"`` the first rung *is* the answer plan.

    Bounding it would truncate the fit rather than a bet, so the budget is
    never computed there — asserted through the escalation that the bound
    would otherwise force on a ``max_iter`` first rung. Five patterns, so the
    sample is complete and the bound would be armed if `refit` did not exclude
    it; the same script under `refit="single"` escalates, one test up.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.10)],
                       "p002": [("converged", 0.10)],
                       "p003": [("converged", 0.10)],
                       "p004": [("max_iter", 0.10), ("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:5], plan=_CHEAP, refit="stages",
                        first_rung_factor=FIRST_RUNG_FACTOR)
    assert series[4].rungs_tried == ["warm_staged"]


def test_only_a_converged_first_rung_becomes_evidence(thermal_patterns):
    """Only *converged* first rungs are evidence about what a working one costs.

    "Worked" means it converged, not that it survived. A first rung kept at the
    *plan's* own cap reports ``"max_iter"``; letting it in at full budget would
    raise the bound to a multiple of the cap and switch the bound off from then
    on.

    Two chains differing in one dictated status is what separates those, and
    the status is on the **third** rung — the one that completes
    `FIRST_RUNG_SAMPLES`, so it is exactly the sample that arms the bound.
    """
    def run(p003_status):
        structure, ins = _start_models()
        runner = _dictate(SequentialRefinement(structure, ins),
                          {"p000": [("converged", 0.10)],
                           "p001": [("converged", 0.10)],
                           "p002": [("converged", 0.10)],
                           "p003": [(p003_status, 0.10), ("converged", 0.10)],
                           "p004": [("max_iter", 0.10), ("converged", 0.10)]})
        return runner.fit(thermal_patterns[:5], plan=_CHEAP,
                          first_rung_factor=FIRST_RUNG_FACTOR)

    # p003 converged on its first rung, so the sample is complete and p004's
    # truncated rung escalates
    evidence = run("converged")
    assert evidence[3].rungs_tried == ["warm"]
    assert evidence[4].rungs_tried == ["warm", "warm_staged"]

    # p003 came back max_iter: kept, because nothing had armed a bound yet, but
    # it is not evidence — so the sample is still two short of
    # FIRST_RUNG_SAMPLES and p004 keeps its own rung exactly as the unbounded
    # ladder would
    none = run("max_iter")
    assert none[3].rungs_tried == ["warm"] and none[3].status == "max_iter"
    assert none[4].rungs_tried == ["warm"] and none[4].status == "max_iter"


def chain_answer(series):
    """Every number a chain reports, and which rung each pattern kept: per
    pattern its values, esds, rungs, fence and codes, then the series' own
    codes and steps.  The tree and node ids a history writes are names, not
    answers, and are left out."""
    entries = [(e.label, e.status, e.rung, tuple(e.rungs_tried), e.reseeded,
                e.rwp_warm, e.rwp_fence, e.statistics.rwp,
                [(p.path, p.value, p.stderr) for p in e.parameters],
                [d.code for d in e.diagnostics])
               for e in series.entries]
    return entries, [d.code for d in series.diagnostics], series.steps


def first_rung_ratios(series):
    """Each kept first rung's cost over the most expensive one before it.

    Replays :func:`~rietx.sequential._first_rung_budget`'s sample from the
    record: a warm pattern that kept its first rung reports that rung's
    evaluations as ``n_iterations``, and only a *converged* one joins the
    sample.  Once the sample holds :data:`~rietx.sequential.FIRST_RUNG_SAMPLES`
    (the point the bound arms) every kept first rung gets a ratio, a
    ``max_iter`` one included: that is the rung a bound would cut.
    """
    from rietx.sequential import FIRST_RUNG_SAMPLES

    sample, ratios = [], []
    for e in series.entries[1:]:
        if e.rungs_tried == ["warm"]:
            if len(sample) >= FIRST_RUNG_SAMPLES:
                ratios.append(e.n_iterations / max(sample))
            if e.status == "converged":
                sample.append(e.n_iterations)
    return ratios


def _thermal_series(patterns, **kw):
    structure, ins = _start_models()
    return refine_sequential(patterns, structure, ins,
                             x=TEMPERATURES, x_label="T (K)",
                             labels=[f"{int(t)}K" for t in TEMPERATURES],
                             plan="mccusker_default", **kw)


@pytest.fixture(scope="module")
def thermal_series_unbounded(thermal_patterns):
    return _thermal_series(thermal_patterns, first_rung_factor=None)


def test_the_first_rung_bound_moves_no_accepted_value(thermal_series,
                                                      thermal_series_unbounded):
    """`FIRST_RUNG_FACTOR` is answer-invariant here, and by how much (WP-2003).

    Invariance is a measured margin, not a construction: a bound that cut a
    *winning* first rung would keep the next rung's answer instead.  So two
    things are asserted on the default plan's chain, the bound on and off:
    every accepted value, esd, rung and code is equal, and every first rung
    the unbounded chain kept cost less than the budget the bound would have
    set at that point.  Measured 2026-10-24: three armed patterns, each at
    1.0× the running maximum (15 evaluations against 15), so the bound sits
    3× above every rung it could have cut.  The CPD chain's twin is in
    `test_acceptance_sequential.py`.
    """
    assert chain_answer(thermal_series) == chain_answer(thermal_series_unbounded)
    ratios = first_rung_ratios(thermal_series_unbounded)
    assert ratios, "the bound armed on no pattern, so nothing was tested"
    assert max(ratios) < FIRST_RUNG_FACTOR


def test_an_unrecovered_pattern_seeds_nothing_and_joins_no_median(
        thermal_patterns, tmp_path):
    """The hygiene criterion: a doubly-failed pattern is stepped over.

    Pattern 1 is dictated to diverge on every rung at an Rwp *far below* the
    series — which is what makes the median half of this testable.  If the
    failure joined ``accepted_rwp`` the median would fall from 0.10 to 0.0505
    and pattern 2, at exactly 0.10, would escalate for no reason; quarantined,
    the median stays 0.10, ``0.10 > 1.0 × 0.10`` is false, and pattern 2 fits
    once.  The seeding half is read off the history note, which names the node
    each pattern's starting values actually came from.
    """
    structure, ins = _start_models()
    runner = _dictate(
        SequentialRefinement(structure, ins, history=tmp_path / "h"),
        {"p000": [("converged", 0.10)],
         "p001": [("diverged", 0.001)],
         "p002": [("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:3], plan=_CHEAP, reseed_factor=1.0)

    failed = series[1]
    assert failed.status == "diverged"
    assert failed.rungs_tried == ["warm", "warm_staged", "cold"]   # all of them
    unrecovered = [d for d in series.diagnostics
                   if d.code == "SEQUENTIAL_UNRECOVERED"]
    assert len(unrecovered) == 1
    assert unrecovered[0].level == "warning"
    assert unrecovered[0].where == ["p001"]
    assert "seeded no successor" in unrecovered[0].message
    # the re-routing is on the record, with history off as with it (WP-2003)
    assert [e.seeded_from for e in series] == [None, 0, 0]
    assert ("Pattern 2 (p002) warm-started from pattern 0 (p000) instead."
            in unrecovered[0].message)

    # the median never saw it: pattern 2 fitted once, against a median of 0.10
    assert series[2].rungs_tried == ["warm"]

    # ... and neither did the warm start: pattern 2 chains from pattern 0
    roots = [t.root for t in runner.trees_]
    assert roots[2].notes["series_warm_start_node"] == series[0].node_id
    assert roots[2].notes["series_warm_start_tree"] == series[0].tree_id
    # the failure is still reported in full — it was measured, and dropping it
    # would make the trajectory look like a shorter series
    assert len(series) == 3 and failed.statistics is not None


# -- a kept rung still above the fence (WP-1469, issue #481) ---------------

def test_a_pattern_every_rung_left_above_the_fence_says_so(thermal_patterns,
                                                           tmp_path):
    """Gap 1: the Rwp leg of the fence was a trigger and never a verdict.

    Pattern 1 is dictated above the fence on every rung, the cold one least
    so, which is issue #481's blank frame: kept cold, reseeded, and until
    WP-1469 reported only by a ``SEQUENTIAL_RESEED`` calling it a good fit.
    """
    structure, ins = _start_models()
    runner = _dictate(
        SequentialRefinement(structure, ins, history=tmp_path / "h"),
        {"p000": [("converged", 0.10)],
         "p001": [("converged", 0.30), ("converged", 0.29), ("converged", 0.28)],
         "p002": [("converged", 0.10)]})
    series = runner.fit(thermal_patterns[:3], plan=_CHEAP)

    kept = series[1]
    assert kept.rungs_tried == ["warm", "warm_staged", "cold"]
    assert kept.rung == "cold" and kept.reseeded
    assert series[0].rwp_fence is None               # no median yet
    assert kept.rwp_fence == pytest.approx(1.25 * 0.10)
    assert kept.above_fence
    (outlier,) = [d for d in series.diagnostics
                  if d.code == "SEQUENTIAL_RWP_OUTLIER"]
    assert outlier.level == "warning" and outlier.where == ["p001"]
    assert outlier.value == pytest.approx(0.28 / 0.125)
    # the evidence that separates the causes, against the pattern before it
    assert "Against p000, the last pattern before it inside the fence: GoF " in \
        outlier.message
    assert "Rexp" in outlier.message
    # …and the reseed text stops calling it a good fit
    (reseed,) = [d for d in series.diagnostics if d.code == "SEQUENTIAL_RESEED"]
    assert "good fit" not in reseed.suggestion
    assert "SEQUENTIAL_RWP_OUTLIER" in reseed.suggestion
    assert "SEQUENTIAL_UNRECOVERED" not in [d.code for d in series.diagnostics]

    # not quarantined: it seeds its successor and joins the median, so a
    # lasting change can become the chain's new normal (the WP's measurement)
    roots = [t.root for t in runner.trees_]
    assert roots[2].notes["series_warm_start_node"] == kept.node_id
    assert series[2].rwp_fence == pytest.approx(1.25 * np.median([0.10, 0.28]))
    assert not series[2].above_fence


@pytest.mark.slow
def test_a_blank_frame_no_longer_reads_as_a_point_or_hides_a_step():
    """Issue #481 as a fixture, all three gaps at once.

    Twenty-four patterns of a ramp growing 6.4e-5 a pattern, pattern 7 blank
    (every scale 0: background and noise), a 2e-3 Å step planted from pattern
    12, the first pattern fitted with ``mccusker_default`` and the chain run
    as the issue ran it.  Before WP-1469 the blank read as a good fit and its
    cell, fitted to noise, took the one flag on a, b and c, verified at 1.00,
    while the planted step went unreported.
    """
    ramp, step, blank, stepped = 6.4e-5, 2e-3, 7, 12
    patterns = [_simulate(A0 * (1 + ramp * k) + (step if k >= stepped else 0.0),
                          seed=500 + k, scale=0.0 if k == blank else TRUE_SCALE)
                for k in range(24)]
    first = rx.Refinement(*_start_models())
    first.fit(patterns[0], plan="mccusker_default")
    series = SequentialRefinement(first.fitted_structure,
                                  first.fitted_instrument).fit(
        patterns, labels=[f"ramp_{k:03d}" for k in range(24)],
        plan="mccusker_default", refit="stages", on_error="carry",
        verify_steps=3)

    # gap 1: the blank carries a warning that does not call it a good fit,
    # and it is the only pattern that does
    outliers = [d for d in series.diagnostics
                if d.code == "SEQUENTIAL_RWP_OUTLIER"]
    assert [d.where for d in outliers] == [["ramp_007"]]
    assert outliers[0].level == "warning"
    assert all("good fit" not in d.suggestion for d in series.diagnostics
               if d.where == ["ramp_007"])
    # gap 2: the planted step is the cell's largest, re-measured cold, and no
    # step touches the blank (WP-2003: a row of SeriesResult.steps, no flag)
    cell = [s for s in series.steps if s.path == "phases.0.cell.a"]
    assert cell[0].labels == ("ramp_011", "ramp_012")
    assert cell[0].cold_ratio == pytest.approx(1.0, abs=0.05)
    # gap 3: …and the pair is read from a field
    assert not [s for s in series.steps if "ramp_007" in s.labels]


def test_the_outlier_verdict_is_read_off_the_entry():
    """Derived, like every fence here, so a reloaded series says the same."""
    from rietx.sequential import _inside_before, _rwp_outlier_diagnostics

    def entry(k, rwp, fence, status="converged"):
        return SeriesEntry(index=k, label=f"p{k}", status=status, rwp_fence=fence,
                           statistics=Statistics(rwp=rwp, rp=rwp, rexp=0.04,
                                                 chi2=1.0, gof=rwp / 0.04,
                                                 n_points=100,
                                                 n_free_parameters=3))

    assert not entry(0, 0.30, None).above_fence          # no fence applied
    assert not entry(0, 0.05, 0.0625).above_fence        # inside it
    assert not entry(0, 0.30, 0.0625, "diverged").above_fence   # UNRECOVERED's
    assert entry(0, 0.30, 0.0625).above_fence
    assert _rwp_outlier_diagnostics(entry(0, 0.05, 0.0625), None) == []

    # "before" is in walk order: a backward chain reached p1 from p2
    chain = [entry(0, 0.04, None), entry(1, 0.30, 0.05), entry(2, 0.04, 0.05)]
    assert _inside_before(chain, "forward")[1].label == "p0"
    assert _inside_before(chain, "backward")[1].label == "p2"
    reloaded = SeriesEntry.model_validate_json(chain[1].model_dump_json())
    assert reloaded.above_fence and reloaded.rwp_fence == 0.05

    # a ladder stopped short of its cold rung (reseed=False, or a cancel)
    # does not claim every start was tried
    climbed = entry(1, 0.30, 0.05)
    climbed.rungs_tried, climbed.rung = ["warm", "warm_staged", "cold"], "cold"
    (d,) = _rwp_outlier_diagnostics(climbed, None)
    assert "every rung the chain tried" in d.message
    assert "No starting point" in d.message
    short = entry(1, 0.30, 0.05)
    short.rungs_tried, short.rung = ["warm"], "warm"
    (d,) = _rwp_outlier_diagnostics(short, None)
    assert "every rung" not in d.message and "cold rung" in d.message
    assert "No starting point" not in d.message
    assert d.value == pytest.approx(6.0) and "6.00× the fence" in d.message


def test_a_diverged_cold_rung_is_not_called_a_good_fit():
    """Every rung diverged and the cold one was the least bad: reseeded, and
    SEQUENTIAL_UNRECOVERED calls it a failed fit, so the reseed text must not
    call it a good one."""
    from rietx.sequential import _reseed_diagnostics

    e = SeriesEntry(index=1, label="p1", status="diverged", reseeded=True,
                    rung="cold", rungs_tried=["warm", "warm_staged", "cold"],
                    rwp_warm=0.5, rwp_fence=0.05,
                    statistics=Statistics(rwp=0.3, rp=0.3, rexp=0.04, chi2=1.0,
                                          gof=7.5, n_points=100,
                                          n_free_parameters=3))
    (d,) = _reseed_diagnostics(e)
    assert "good fit" not in d.suggestion
    assert "SEQUENTIAL_UNRECOVERED" in d.suggestion


def test_every_rung_writes_its_own_history_log(thermal_patterns, tmp_path):
    """One header per file, which the cold restart used to break.

    Three attempts on one pattern are three separate fits of the same data —
    same ``tree_id``, since that is the data fingerprint — and the JSONL format
    is append-only, so sharing a file would interleave two trees' nodes under
    whichever header was written last.  Same reason the backward pass has its
    own suffix.
    """
    structure, ins = _start_models()
    runner = _dictate(
        SequentialRefinement(structure, ins, history=tmp_path / "h"),
        {"a": [("converged", 0.10)],
         "b": [("converged", 0.30), ("converged", 0.28), ("converged", 0.05)]})
    runner.fit(thermal_patterns[:2], plan=_CHEAP, labels=["a", "b"],
               reseed_factor=1.0)

    for name in ("a.jsonl", "b.jsonl", "b.warm_staged.jsonl", "b.cold.jsonl"):
        log = tmp_path / "h" / name
        assert log.exists(), name
        text = log.read_text(encoding="utf-8").replace(" ", "")
        assert text.count('"record":"header"') == 1, name
        assert rx.RefinementTree.load(log).header.tree_id
    # the kept fit is the cold one, and its log is the one the entry names
    assert not (tmp_path / "h" / "a.cold.jsonl").exists()


def test_a_restart_stamps_which_rung_it_is(thermal_patterns):
    """One added ``data`` key, on restarts only — and not one new ``EventKind``.

    ``series_rung`` has to appear on the escalation attempts and *not* on a
    pattern's first one: the first pattern of a chain runs the cold rung without
    being a restart, so stamping it would relabel an ordinary cold start as a
    rescue — and ``series_cold``, which WP-1016 defined as exactly that, would
    change meaning.  A changed meaning is an ``EVENT_SCHEMA_VERSION`` bump; an
    added field is not.
    """
    from rietx.history.events import EVENT_SCHEMA_VERSION, EventKind

    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30), ("converged", 0.28),
                                ("converged", 0.05)]})
    seen = []
    runner.fit(thermal_patterns[:2], plan=_CHEAP, reseed_factor=1.0,
               events=seen.append)

    assert {e["v"] for e in seen} == {EVENT_SCHEMA_VERSION}
    assert {e["kind"] for e in seen} <= set(get_args(EventKind))
    starts = [e["data"] for e in seen if e["kind"] == "fit_start"]
    assert [(d["series_index"], d.get("series_rung")) for d in starts] == [
        (0, None), (1, None), (1, "warm_staged"), (1, "cold")]
    # ``series_cold`` stays what it was: present, and true, on a cold restart
    assert [d.get("series_cold") for d in starts] == [None, None, None, True]


def test_a_cancel_mid_ladder_keeps_the_best_complete_attempt(thermal_patterns):
    """A rung that never finished is not evidence against the one that did.

    WP-1016's rule for the cold restart, one rung generalised: the abandoned
    attempt left no node and no commit, so what stands is the best *complete*
    fit of that pattern, and the walk ends there.
    """
    structure, ins = _start_models()
    runner = _dictate(SequentialRefinement(structure, ins, history=True),
                      {"p000": [("converged", 0.10)],
                       "p001": [("converged", 0.30)]})
    token = CancelToken()

    def watch(event):
        if event["kind"] == "fit_start" and event["data"].get("series_rung"):
            token.cancel()

    series = runner.fit(thermal_patterns[:3], plan=_CHEAP, reseed_factor=1.0,
                        events=watch, cancel=token)

    assert len(series) == 2                      # pattern 2 was never started
    kept = series[1]
    assert kept.rungs_tried == ["warm"] and kept.rung == "warm"
    assert kept.statistics.rwp == pytest.approx(0.30)
    assert kept.node_id is not None              # a complete fit, with a node
    assert "SEQUENTIAL_CANCELLED" in [d.code for d in series.diagnostics]


# -- the steps between patterns (WP-2003) ------------------------------

def test_the_step_ranks_first_and_the_value_is_left_alone(jump_patterns):
    """The planted step is the cell's largest row, no diagnostic names it,
    and no row is re-measured unless the caller asks: ``cold_ratio`` stays
    ``None`` (WP-1003's absent-for-cause rule)."""
    structure, ins = _start_models()
    series = refine_sequential(jump_patterns, structure, ins)
    assert "SEQUENTIAL_DISCONTINUITY" not in [d.code for d in series.diagnostics]
    cell = [s for s in series.steps if s.path == "phases.0.cell.a"]
    assert len(cell) == 5                       # every consecutive pair
    assert cell[0].indices == (2, 3)
    assert cell[0].step == pytest.approx(2e-3, abs=3e-4)
    assert abs(cell[0].size_esd) > 3 * max(abs(s.size_esd) for s in cell[1:])
    assert all(s.cold_ratio is None for s in series.steps)

    # nothing was smoothed: the fitted step is still the injected one
    value = np.asarray(series.trajectory("phases.0.cell.a").value)
    assert value[3] - value[2] == pytest.approx(2e-3, abs=3e-4)


@pytest.mark.slow
def test_verified_step_reproduces_a_real_step(jump_patterns):
    """WP-1305 (c): a step that is in the data survives two fits that never
    saw each other.  The fixture's step is injected into the *specimen*, so
    the honest answer is a ratio of 1."""
    structure, ins = _start_models()
    series = refine_sequential(jump_patterns, structure, ins, verify_steps=3)
    step = next(s for s in series.steps
                if s.path == "phases.0.cell.a" and s.indices == (2, 3))
    assert step.cold_ratio == pytest.approx(1.0, abs=0.1)
    assert sum(s.cold_ratio is not None for s in series.steps) <= 3


@pytest.mark.slow
def test_verified_step_renders_for_inspection(jump_patterns):
    """The trajectory and the two patterns the check refitted, drawn to
    tests/output/ (gitignored) — a ratio of 1.00 is a number, and the curve
    either side of the step is what says it is a step (memory: plot every test
    refinement)."""
    from pathlib import Path

    from rietx.viz.plots import plot_result, plot_trajectory

    structure, ins = _start_models()
    runner = SequentialRefinement(structure, ins)
    series = runner.fit(jump_patterns, labels=[f"p{k}" for k in range(6)],
                        verify_steps=1)
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_trajectory(series, [series.steps[0].path],
                    path=str(out / "sequential_verified_step.png"))
    for k in series.steps[0].indices:      # the pair the verification refitted
        plot_result(runner.results_[k],
                    path=str(out / f"sequential_verified_step_p{k}.png"))
    assert (out / "sequential_verified_step.png").exists()


@pytest.mark.slow
def test_verification_moves_no_fitted_value(jump_patterns):
    """The post-walk guarantee: a check that changed the answer would be a
    ladder rung, and the module docstring says why this cannot be one."""
    structure, ins = _start_models()
    plain = refine_sequential(jump_patterns, structure, ins)
    checked = refine_sequential(jump_patterns, structure, ins, verify_steps=3)
    for a, b in zip(plain.entries, checked.entries, strict=True):
        assert a.rung == b.rung and a.status == b.status
        assert a.n_iterations == b.n_iterations
        assert [(p.path, p.value) for p in a.parameters] == \
               [(p.path, p.value) for p in b.parameters]
    assert [(s.path, s.indices, s.step) for s in plain.steps] == \
           [(s.path, s.indices, s.step) for s in checked.steps]


class _RecordedVerify(SequentialRefinement):
    """A runner that records which rows the walk hands its verification."""

    def _verify_steps(self, steps, *args, **kw):
        self.handed = list(steps)


def test_verify_steps_hands_the_k_largest_rows_to_the_check(thermal_patterns):
    """``verify_steps=k`` is the caller's k over the sorted list, and 0 runs
    no check at all (WP-2003, the ruling's option (ii))."""
    runner = _RecordedVerify(*_start_models())
    series = runner.fit(thermal_patterns[:3], plan=_CHEAP, verify_steps=2)
    assert runner.handed == series.steps[:2]
    assert all(a is b for a, b in zip(runner.handed, series.steps[:2], strict=True))

    runner = _RecordedVerify(*_start_models())
    runner.fit(thermal_patterns[:3], plan=_CHEAP)
    assert not hasattr(runner, "handed")


@pytest.mark.parametrize("bad, error, match", [
    (True, TypeError, "verify_discontinuities"),
    (False, TypeError, "count"),
    (-1, ValueError, "0 or more"),
    (2.0, TypeError, "int count"),
])
def test_verify_steps_refuses_a_flag_or_a_negative_count(thermal_patterns, bad,
                                                         error, match):
    """``True`` meant "the flagged pairs" under the old keyword; read as 1 it
    would refit a pair nobody chose, so a bool is refused by name."""
    runner = SequentialRefinement(*_start_models())
    with pytest.raises(error, match=match):
        runner.fit(thermal_patterns[:2], plan=_CHEAP, verify_steps=bad)
    assert runner.results_ == []


class _StubColdFits(SequentialRefinement):
    """A runner whose verification refits are canned.

    The ratio arithmetic, the one-refit-per-pattern cache and the branch where
    a cold fit determines nothing are all decidable without fitting, and a
    *measured* false step is the one case the ramp can no longer supply: after
    WP-1301 the CaF₂ cell that used to wander is held instead (WP-1305's
    handover has the run).  So the "the chain made it" direction is pinned
    here, on numbers chosen for it.
    """

    def __init__(self, values: dict[str, dict[str, float]]):
        super().__init__(*_start_models())
        self._values = values
        self.refits: list[str] = []
        self.hooks: list[object] = []

    def _fit_one(self, data, label, previous, previous_hkl, plan, mode,
                 two_theta_limits, position, previous_tag, prepare, constrain,
                 index, history_suffix="", *, previous_vars=None, stream=None,
                 stamp=None, cancel=None):
        assert previous is None and previous_hkl == []   # cold, by construction
        assert history_suffix == ".verify"
        self.refits.append(label)
        self.hooks.append(constrain)
        return None, _fake_result(0.1, parameters=[
            RefinedParameter(path=p, value=v)
            for p, v in self._values[label].items()])


def _flagged(path: str, step: float, labels=("p2", "p3")) -> SeriesStep:
    return SeriesStep(path=path, labels=labels, step=step,
                      indices=tuple(int(label[1:]) for label in labels))


def test_verification_reports_a_chain_made_step_as_a_small_ratio():
    """Two patterns that agree when fitted independently, in a chain that
    stepped by 2e-3: the step is the chain's, and the ratio says so."""
    runner = _StubColdFits({"p2": {"phases.0.cell.a": 4.1566},
                            "p3": {"phases.0.cell.a": 4.1567}})
    steps = [_flagged("phases.0.cell.a", 2e-3)]
    runner._verify_steps(steps, [None] * 6, [f"p{i}" for i in range(6)],
                         "rietveld", _CHEAP, None, None, None)
    assert steps[0].cold_ratio == pytest.approx(0.05, rel=1e-6)
    assert runner.refits == ["p2", "p3"]


def test_verification_refits_each_pattern_once_for_all_its_paths():
    """Two paths stepping between the same pair is one pair of refits, and a
    third step sharing one of its patterns adds one refit, not two."""
    runner = _StubColdFits({"p2": {"phases.0.cell.a": 4.0, "phases.0.cell.b": 4.0},
                            "p3": {"phases.0.cell.a": 4.002, "phases.0.cell.b": 4.002}})
    runner._values["p4"] = {"phases.0.cell.a": 4.004}
    steps = [_flagged("phases.0.cell.a", 2e-3), _flagged("phases.0.cell.b", 2e-3),
             _flagged("phases.0.cell.a", 2e-3, labels=("p3", "p4"))]
    runner._verify_steps(steps, [None] * 6, [f"p{i}" for i in range(6)],
                         "rietveld", _CHEAP, None, None, None)
    assert runner.refits == ["p2", "p3", "p4"]
    assert all(s.cold_ratio == pytest.approx(1.0, rel=1e-6) for s in steps)


def test_verification_ratio_is_signed_so_the_other_way_is_not_a_reproduction():
    """A cold pair that steps as far the *other* way is the opposite of a
    reproduction, and dividing two magnitudes would report it as 1.00 — the
    one reading this check exists to rule out."""
    runner = _StubColdFits({"p2": {"phases.0.cell.a": 4.002},
                            "p3": {"phases.0.cell.a": 4.0}})
    steps = [_flagged("phases.0.cell.a", 2e-3)]
    runner._verify_steps(steps, [None] * 6, [f"p{i}" for i in range(6)],
                         "rietveld", _CHEAP, None, None, None)
    assert steps[0].cold_ratio == pytest.approx(-1.0, rel=1e-6)


def test_verification_says_so_when_a_cold_fit_determines_nothing():
    """A ratio needs both ends; a path a cold fit did not measure is not a
    zero, so no ``cold_ratio`` is written at all."""
    runner = _StubColdFits({"p2": {"phases.0.cell.a": 4.0}, "p3": {}})
    steps = [_flagged("phases.0.cell.a", 2e-3)]
    runner._verify_steps(steps, [None] * 6, [f"p{i}" for i in range(6)],
                         "rietveld", _CHEAP, None, None, None)
    assert steps[0].cold_ratio is None


def test_verification_refits_carry_the_callers_constraints():
    """The cold refit gets ``constrain``, as it gets the plan and the models.

    A verification fit that dropped the caller's own ties would be a different
    model, and the ratio it reports would be comparing the step against a fit
    nobody asked for (WP-1441).
    """
    runner = _StubColdFits({"p2": {"phases.0.cell.a": 4.0},
                            "p3": {"phases.0.cell.a": 4.002}})
    steps = [_flagged("phases.0.cell.a", 2e-3)]
    runner._verify_steps(steps, [None] * 6, [f"p{i}" for i in range(6)],
                         "rietveld", _CHEAP, None, None, _tie_the_two_biso)
    assert runner.hooks == [_tie_the_two_biso, _tie_the_two_biso]


def _synthetic_series(path: str, values, stderr) -> SeriesResult:
    return SeriesResult(entries=[
        SeriesEntry(index=k, label=f"p{k}", parameters=[
            RefinedParameter(path=path, value=v, stderr=s)])
        for k, (v, s) in enumerate(zip(values, stderr, strict=True))])


def _series_missing(path: str, values, stderr, absent) -> SeriesResult:
    """``_synthetic_series`` with the path *absent* from the ``absent``
    patterns — not held with a ``None`` esd, but carrying no
    ``RefinedParameter`` row at all, which is what ``trajectory()`` skips and
    what WP-1301 does to a held structural path."""
    return SeriesResult(entries=[
        SeriesEntry(index=k, label=f"p{k}",
                    parameters=([] if k in absent else
                                [RefinedParameter(path=path, value=v, stderr=e)]))
        for k, (v, e) in enumerate(zip(values, stderr, strict=True))])


def test_an_inert_parameter_steps_by_zero_esds():
    """Regression for a measured false positive: a softplus coefficient dying
    on its floor has dp/du → 0, so its esd collapses *with* its value and
    every step is formally astronomically many σ.  ``instrument.profile.y`` on
    the synthetic ramp came back with a median step of 4e-16, one step of
    1.3e-11 and σ ≈ 4e-55; under the noise floor its steps have size 0."""
    inert = _synthetic_series(
        "instrument.profile.y",
        [1e-16, 2e-16, 1.3e-11, 1.4e-11, 1.5e-11, 1.6e-11],
        [4e-55] * 6)
    assert [s.size_esd for s in _series_steps(inert)] == [0.0] * 5

    # the same shape at a physical magnitude is measured
    real = _synthetic_series(
        "phases.0.cell.a",
        [4.1566, 4.15661, 4.15962, 4.15963, 4.15964, 4.15965],
        [1e-5] * 6)
    steps = _series_steps(real)
    # the signed step the verification ratio divides by (WP-1305)
    assert steps[0].step == pytest.approx(4.15962 - 4.15661)
    assert steps[0].size_esd == pytest.approx((4.15962 - 4.15661) / 1e-5)
    # …and the pair it is between, as fields (WP-1469, issue #481)
    assert steps[0].labels == ("p1", "p2")
    assert steps[0].indices == (1, 2)


def test_steps_sort_largest_first_and_an_unmeasured_size_last():
    """Every consecutive pair is a row, sized by the *later* fit's esd, in
    descending magnitude whatever its sign, and a step against no esd has no
    size rather than an infinite one."""
    series = _synthetic_series("phases.0.cell.a",
                               [4.0, 4.001, 4.0, 4.0005, 4.0035],
                               [1e-4, 1e-4, 2e-4, None, 1e-3])
    steps = _series_steps(series)
    assert [s.indices for s in steps] == [(0, 1), (1, 2), (3, 4), (2, 3)]
    assert steps[0].size_esd == pytest.approx(0.001 / 1e-4)
    assert steps[1].size_esd == pytest.approx(-0.001 / 2e-4)
    assert steps[2].size_esd == pytest.approx(0.003 / 1e-3)
    assert steps[3].size_esd is None and steps[3].step == pytest.approx(5e-4)
    # one pattern is no step at all
    assert _series_steps(_synthetic_series("phases.0.cell.a", [4.0], [1e-4])) == []


def _fenced_series(path: str, values, stderr, *, above=(), diverged=()):
    """A hand-built chain whose ``above`` patterns sit over a fence of 0.05
    and whose ``diverged`` ones diverged; every other one is inside it."""
    def stats(rwp):
        return Statistics(rwp=rwp, rp=rwp, rexp=0.04, chi2=1.0, gof=rwp / 0.04,
                          n_points=100, n_free_parameters=3)

    return SeriesResult(entries=[
        SeriesEntry(index=k, label=f"p{k}",
                    status="diverged" if k in diverged else "converged",
                    rwp_fence=None if k == 0 else 0.05,
                    statistics=stats(0.16 if k in above else 0.04),
                    parameters=[RefinedParameter(path=path, value=v, stderr=s)])
        for k, (v, s) in enumerate(zip(values, stderr, strict=True))])


#: issue #481's shape on one path: a ramp of 2.7e-4 a step, pattern 3 a blank
#: frame whose cell was fitted to noise, and a 2e-3 step planted from pattern 6
_RAMP_A = [4.1566 + 2.7e-4 * k + (2e-3 if k >= 6 else 0.0) for k in range(10)]
_RAMP_A[3] = 4.1499
_RAMP_SD = [6.6e-6] * 10
_RAMP_SD[3] = 1.6e-3


def test_a_rejected_frame_has_no_step():
    """Gap 2: the blank's steps were the largest, so the argmax kept them and
    the planted step behind it went unreported.  Above the fence or diverged,
    its two steps are not rows, and the planted one ranks first."""
    path = "phases.0.cell.a"
    # as a measurement (the pre-WP-1469 reading), the blank's steps lead
    assert "p3" in _series_steps(_fenced_series(path, _RAMP_A, _RAMP_SD))[0].labels
    for rejected in ({"above": {3}}, {"diverged": {3}}):
        steps = _series_steps(_fenced_series(path, _RAMP_A, _RAMP_SD, **rejected))
        assert not [s for s in steps if "p3" in s.labels]
        assert len(steps) == 7
        assert steps[0].labels == ("p5", "p6")
        assert steps[0].indices == (5, 6)
        assert steps[0].step == pytest.approx(2.27e-3)


def test_a_non_finite_rejected_value_has_no_step():
    """A diverged pattern whose value is NaN: its steps are dropped, and no
    row carries the NaN."""
    values = list(_RAMP_A)
    values[3] = float("nan")
    steps = _series_steps(_fenced_series("phases.0.cell.a", values, _RAMP_SD,
                                         diverged={3}))
    assert steps[0].labels == ("p5", "p6")
    assert all(np.isfinite(s.step) for s in steps)


def test_a_run_of_rejected_patterns_is_never_bridged():
    """A clean ramp whose counts fell for four patterns: those four sit over
    the fence with good values.  Bridged, the step from p1 to p6 spans five of
    the ramp's steps; dropped, only the pairs either side remain."""
    ramp = [4.1566 + 2.7e-4 * k for k in range(10)]
    steps = _series_steps(_fenced_series(
        "phases.0.cell.a", ramp, [6.6e-6] * 10, above={2, 3, 4, 5}))
    assert sorted(s.indices for s in steps) == [(0, 1), (6, 7), (7, 8), (8, 9)]


@pytest.mark.parametrize("above", [{3}, set()])
def test_a_pattern_the_path_is_absent_from_is_not_bridged(above):
    """A pattern whose phase was held carries no row for its cell, so the
    trajectory skips it; the pair either side of it is two steps apart and is
    not a row, whether the pattern sits above the fence (tutorial 05's 5 %
    jump read 600 K → 800 K before) or inside it (the planted blank frame)."""
    series = _fenced_series("phases.0.cell.a", _RAMP_A, _RAMP_SD, above=above)
    series.entries[3].parameters = []
    steps = _series_steps(series)
    assert sorted(s.indices for s in steps) == [
        (0, 1), (1, 2), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)]


def test_the_steps_are_a_field_that_survives_json():
    """Gap 3: the pair is fields, not prose, and survives JSON; a document
    written before WP-2003 carries ``discontinuities`` and still opens."""
    series = _fenced_series("phases.0.cell.a", _RAMP_A, _RAMP_SD, above={3})
    series.steps = _series_steps(series)
    series.steps[0].cold_ratio = 0.98
    reloaded = SeriesResult.model_validate_json(series.model_dump_json())
    assert reloaded.steps == series.steps
    assert reloaded.steps[0].labels == ("p5", "p6")
    # a document written before the record says "not recorded", not "none"
    assert SeriesResult().steps is None

    old = json.loads(series.model_dump_json())
    del old["steps"]
    old["discontinuities"] = [{"path": "phases.0.cell.a", "labels": ["p5", "p6"],
                               "indices": [5, 6], "step": 2.27e-3}]
    opened = SeriesResult.model_validate(old)
    assert opened.steps is None
    assert "discontinuities" not in opened.model_dump()


def test_the_plot_shades_only_a_step_re_measured_cold():
    """No step is called a jump, so an unverified one is not shaded; the one
    ``verify_steps`` re-measured is, between the pair its record names."""
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_trajectory

    path = "phases.0.cell.a"
    series = _fenced_series(path, _RAMP_A, _RAMP_SD, above={3})
    series.steps = _series_steps(series)
    fig = plot_trajectory(series, [path])
    (ax,) = fig.get_axes()
    assert not ax.patches
    plt.close(fig)

    series.steps[0].cold_ratio = 1.0
    fig = plot_trajectory(series, [path])
    (ax,) = fig.get_axes()
    (span,) = ax.patches
    xs = ax.transData.inverted().transform(
        span.get_transform().transform(span.get_path().vertices))[:, 0]
    assert (xs.min(), xs.max()) == pytest.approx((5.0, 6.0))
    # …and the pattern above the fence is boxed, the one mark it carries
    boxed = [line for line in ax.get_lines() if line.get_marker() == "s"]
    assert [tuple(line.get_xdata()) for line in boxed] == [(3.0,)]
    plt.close(fig)


def test_a_relative_dof_is_judged_by_neither_fence_nor_stepped():
    """A coordinate DOF's value is the step its fit took, not a position.

    Since WP-1333 each pattern starts where its predecessor ended, so a DOF's
    trajectory is the first pattern's move from the model and then small steps
    either way: a jump by construction.  The backward chain takes the same
    steps from the other side, so the two differ in sign by construction too.
    Both fences fired on exactly that, on a clean seven-pattern ramp whose
    coordinate agreed between the chains to 1e-9, and its first step leads
    ``SeriesResult.steps`` unless the path is named relative.
    """
    steps = [0.0096, -0.0005, 0.0003, -0.0002, 0.0003, -0.0001]
    forward = _synthetic_series(B_DOF, steps, [4e-4] * 6)
    backward = _synthetic_series(B_DOF, [-s for s in steps], [4e-4] * 6)
    assert _series_steps(forward)[0].indices == (0, 1)
    assert [d.code for d in _path_dependence_diagnostics(forward, backward)] == [
        "SEQUENTIAL_PATH_DEPENDENT"]

    relative = frozenset({B_DOF})
    assert _series_steps(forward, relative) == []
    assert _path_dependence_diagnostics(forward, backward, relative) == []


def test_a_chained_coordinate_is_judged_on_its_coordinate(thermal_patterns):
    """The fences are handed the model's displacement DOFs, and skip them.

    Read off the table built from the models the chain was given
    (``anchored_dof_paths``), since nothing in a ``SeriesEntry`` says a path
    is relative.  The coordinate row stays in the series, and so does the DOF:
    each is what its fits reported.
    """
    structure, instrument = _start_models()
    structure.phases[0].atoms[1].x.value = _B_START
    series = refine_sequential(
        thermal_patterns[:5], structure, instrument, direction="both",
        plan=_coordinate_plan("phases.*.atoms.*.dof.*"))
    assert {B_X, B_DOF} <= set(series.paths(varied_only=False))
    assert [d.where for d in series.diagnostics
            if d.code == "SEQUENTIAL_PATH_DEPENDENT"] == []
    stepped = {s.path for s in series.steps}
    assert B_X in stepped and B_DOF not in stepped
    assert {s.path for s in series.backward.steps} == stepped


def test_path_dependence_ignores_numerically_identical_chains():
    """Two chains agreeing to 1e-60 are agreeing, whatever the σ ratio says."""
    forward = _synthetic_series("instrument.profile.y",
                                [2.2e-74, 1e-60, 1e-60], [1e-70] * 3)
    backward = _synthetic_series("instrument.profile.y",
                                 [2.1e-60, 1e-60, 1e-60], [1e-70] * 3)
    assert _path_dependence_diagnostics(forward, backward) == []

    moved = _synthetic_series("phases.0.cell.a", [4.1566, 4.1570, 4.1574],
                              [1e-5] * 3)
    shifted = _synthetic_series("phases.0.cell.a", [4.1576, 4.1570, 4.1574],
                                [1e-5] * 3)
    assert [d.code for d in _path_dependence_diagnostics(moved, shifted)] == [
        "SEQUENTIAL_PATH_DEPENDENT"]


def test_path_dependence_needs_an_esd_from_both_chains():
    """A pattern one chain refined and the other held has an esd on one side
    only, and ``Trajectory.arrays`` reports the missing one as NaN.  Combining
    them through ``np.nan_to_num`` divides the two values' difference by the
    refining chain's esd alone, which is a significance the held side never
    earned — 100σ below, on a series where not one pattern was measured twice.

    A tied dependent path reaches this state routinely: ``_build_result`` emits
    tie rows whether or not their source was refined, so a cubic phase's
    ``cell.b`` is present in every pattern while its ``cell.a`` is absent in
    the held ones (and so is dropped by the length gate).
    """
    esd = 1e-4
    held_late = _synthetic_series(
        "phases.1.cell.b",
        [5.4000, 5.4010, 5.4020, 5.4030, 5.4030, 5.4030, 5.4030, 5.4030],
        [esd, esd, esd, esd, None, None, None, None])
    held_early = _synthetic_series(
        "phases.1.cell.b",
        [5.4100, 5.4100, 5.4100, 5.4100, 5.4100, 5.4110, 5.4120, 5.4130],
        [None, None, None, None, esd, esd, esd, esd])
    # nothing is judged — and since WP-1333 that is said, rather than being
    # the same empty list an agreed path returns (issue #269)
    assert _unjudged(_path_dependence_diagnostics(held_late, held_early)) == [
        ["phases.1.cell.b"]]


def _unjudged(diagnostics) -> list[list[str]]:
    """Every diagnostic must be the #269 finding; return what each names.

    The shape these tests pin is that the comparison judged nothing: no
    ``SEQUENTIAL_PATH_DEPENDENT`` at all, and one ``info``
    ``SEQUENTIAL_PATH_CHECK_INCOMPLETE`` naming the paths it could not reach.
    """
    assert all(d.code == "SEQUENTIAL_PATH_CHECK_INCOMPLETE" and d.level == "info"
               for d in diagnostics), [d.code for d in diagnostics]
    return [d.where for d in diagnostics]


def test_path_dependence_keeps_the_patterns_both_chains_measured():
    """The mask is per pattern, not per path.  Six of these eight patterns
    were measured by both chains and agree well inside their esds; two are
    one-sided.  Dropping the whole path would discard the six, and judging the
    two reports the series as path-dependent at 80σ on the strength of the
    patterns that carry no comparable esd."""
    esd = 1e-4
    forward = _synthetic_series(
        "phases.1.cell.b",
        [5.4000, 5.4010, 5.4020, 5.4030, 5.4040, 5.4050, 5.4060, 5.4060],
        [esd] * 8)
    backward = _synthetic_series(
        "phases.1.cell.b",
        [5.4001, 5.4011, 5.4019, 5.4031, 5.4039, 5.4051, 5.4130, 5.4140],
        [esd] * 6 + [None, None])
    assert _path_dependence_diagnostics(forward, backward) == []

    # …and a real disagreement inside the comparable patterns still fires,
    # with the one-sided pair present and ignored: the two channels are
    # separable, and only one of them is an artefact.
    backward.entries[5].parameters[0].value = 5.4060
    assert [d.code for d in _path_dependence_diagnostics(forward, backward)] == [
        "SEQUENTIAL_PATH_DEPENDENT"]


def test_path_dependence_pairs_the_two_chains_by_pattern():
    """Equal length is not alignment, and the length gate never made it so.

    ``trajectory()`` *skips* patterns where the path is absent, so a path held
    in the forward chain's first pattern and in the backward chain's last
    gives two seven-long trajectories over different patterns.  Compared
    position by position, p1 is subtracted from p0 the whole way down and one
    clean monotonic ramp — the same ramp, in both chains — is reported
    path-dependent at tens of sigma, with every esd two-sided so the
    both-measured mask never sees it.  Reported by @yue-here in review of
    PR #264, reproduced here before the fix at 70.7σ.
    """
    esd = 1e-5
    ramp = [4.1500 + 1e-3 * k for k in range(8)]
    forward = _series_missing("phases.1.cell.a", ramp, [esd] * 8, absent={0})
    backward = _series_missing("phases.1.cell.a", ramp, [esd] * 8, absent={7})

    f = forward.trajectory("phases.1.cell.a")
    b = backward.trajectory("phases.1.cell.a")
    assert len(f) == len(b) == 7          # the length gate lets this through
    assert f.labels != b.labels           # and they are not the same patterns

    assert _path_dependence_diagnostics(forward, backward) == []

    # The positive arm: a real disagreement on a pattern both chains *did*
    # measure still fires, and the label in the message is the pattern the
    # two values actually come from.
    backward.entries[3].parameters[0].value = 4.1600
    fired = _path_dependence_diagnostics(forward, backward)
    assert [d.code for d in fired] == ["SEQUENTIAL_PATH_DEPENDENT"]
    assert "at p3:" in fired[0].message
    assert "4.153 vs 4.16" in fired[0].message


def test_path_dependence_judges_the_overlap_of_unequal_chains():
    """Unequal lengths no longer mean the path goes unexamined.  Before the
    label pairing, ``len(f) != len(b)`` dropped the whole path, so a phase
    absent from one pattern of one chain was never compared on any of the
    others — the follow-up @yue-here raised on PR #264."""
    esd = 1e-5
    ramp = [4.1500 + 1e-3 * k for k in range(8)]
    forward = _series_missing("phases.1.cell.a", ramp, [esd] * 8, absent={0})
    disagreeing = list(ramp)
    disagreeing[4] = 4.1600
    backward = _series_missing("phases.1.cell.a", disagreeing, [esd] * 8,
                               absent=set())

    assert len(forward.trajectory("phases.1.cell.a")) == 7
    assert len(backward.trajectory("phases.1.cell.a")) == 8
    fired = _path_dependence_diagnostics(forward, backward)
    assert [d.code for d in fired] == ["SEQUENTIAL_PATH_DEPENDENT"]
    assert "at p4:" in fired[0].message


def test_the_abstention_row_recipe_counts_the_patterns_actually_judged():
    """The skill row's own remedy, run on the two shapes it exists to catch.

    ``abstention.md``'s ``SEQUENTIAL_PATH_DEPENDENT`` row told an agent to
    compare ``len(series.trajectory(path))`` against the backward chain's
    before reading silence as clearance.  @yue-here measured both states in
    which that returns "fine": two chains whose held stretches sit at opposite
    ends have equal lengths and no shared pattern at all, and two chains with
    identical labels can still have no pattern measured by both.  The quantity
    is neither length — it is the number of patterns where the labels
    intersect **and** both esds are finite — so the row now carries that
    computation, and this test is the computation.
    """
    path = "phases.1.cell.a"
    ramp = [4.1500 + 1e-3 * k for k in range(8)]
    esd = 1e-5

    def patterns_judged(series: SeriesResult, path: str) -> int:
        """``abstention.md``'s recipe, as an agent would run it."""
        f = series.trajectory(path)
        b = series.backward.trajectory(path)
        _, _, sf = f.arrays()
        _, _, sb = b.arrays()
        sb_by = dict(zip(b.labels, sb, strict=True))
        return sum(1 for lab, e in zip(f.labels, sf, strict=True)
                   if np.isfinite(e) and np.isfinite(sb_by.get(lab, np.nan)))

    def both(fwd: SeriesResult, bwd: SeriesResult) -> SeriesResult:
        fwd.direction, fwd.backward = "both", bwd
        return fwd

    # A — the label half.  The two chains held opposite ends of the series, so
    # nothing is ever compared and the lengths match anyway.
    a = both(_series_missing(path, ramp, [esd] * 8, absent={4, 5, 6, 7}),
             _series_missing(path, ramp, [esd] * 8, absent={0, 1, 2, 3}))
    fa, ba = a.trajectory(path), a.backward.trajectory(path)
    assert len(fa) == len(ba) == 4          # the old check: EQUAL -> clearance
    assert set(fa.labels) & set(ba.labels) == set()
    assert _unjudged(_path_dependence_diagnostics(a, a.backward)) == [[path]]
    assert patterns_judged(a, path) == 0

    # B — the esd half.  Identical labels, identical lengths, and the
    # both-measured mask rules out every pattern, so nothing is judged.
    b = both(_series_missing(path, ramp, [None] * 8, absent=set()),
             _series_missing(path, ramp, [esd] * 8, absent=set()))
    fb, bb = b.trajectory(path), b.backward.trajectory(path)
    assert len(fb) == len(bb) == 8          # the old check: EQUAL -> clearance
    assert fb.labels == bb.labels
    # the two chains' values are *identical*, which the comparison's noise
    # floor calls agreement whatever the esds say, so there is nothing an esd
    # could have changed and nothing to name (WP-1333)
    assert _path_dependence_diagnostics(b, b.backward) == []
    assert patterns_judged(b, path) == 0

    # B' — the same esd pattern over values that differ: now the silence
    # would hide something, and the #269 finding names the path
    shifted = [v + 2e-3 for v in ramp]
    b2 = both(_series_missing(path, ramp, [None] * 8, absent=set()),
              _series_missing(path, shifted, [esd] * 8, absent=set()))
    assert _unjudged(_path_dependence_diagnostics(b2, b2.backward)) == [[path]]
    assert patterns_judged(b2, path) == 0

    # The positive arm, because a count that only ever answers 0 is not
    # separable from a broken one: a series both chains measured throughout is
    # judged on every pattern, and a partial overlap is reported as the
    # overlap rather than as either length.
    whole = both(_series_missing(path, ramp, [esd] * 8, absent=set()),
                 _series_missing(path, ramp, [esd] * 8, absent=set()))
    assert patterns_judged(whole, path) == 8

    partial = both(_series_missing(path, ramp, [esd] * 8, absent={0, 1}),
                   _series_missing(path, ramp, [esd] * 8, absent={7}))
    assert len(partial.trajectory(path)) == 6
    assert len(partial.backward.trajectory(path)) == 7
    assert patterns_judged(partial, path) == 5      # p2..p6, neither length


def test_a_uniform_ramp_steps_one_way(thermal_series):
    """A steady trend: every cell step is the same sign, and nothing in the
    series reads any of them as a finding (WP-2003)."""
    assert "SEQUENTIAL_DISCONTINUITY" not in [d.code
                                              for d in thermal_series.diagnostics]
    cell = [s for s in thermal_series.steps if s.path == "phases.0.cell.a"]
    assert len(cell) == len(thermal_series) - 1
    assert all(s.step > 0 and s.size_esd > 0 for s in cell)


# -- the path-dependence fence -------------------------------------------

@pytest.mark.slow
def test_forward_and_backward_chains_agree_on_a_clean_series(thermal_patterns):
    """Each pattern of a well-conditioned series reaches its own minimum
    whichever neighbour it started from, so no parameter is path-dependent."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:5], structure, ins,
                               direction="both")
    assert series.direction == "both"
    assert [d.code for d in series.diagnostics
            if d.code == "SEQUENTIAL_PATH_DEPENDENT"] == []
    # the backward chain is kept, and reported in series order
    assert [e.index for e in series.entries] == [0, 1, 2, 3, 4]

    # …and the one-shot API hands it back, so the trajectory the
    # path-dependence diagnostics are about is reachable (WP-1076).  Before
    # that WP it lived only on `SequentialRefinement.backward_`, which
    # `refine_sequential` never returns.
    assert series.backward is not None
    assert series.backward.direction == "backward"
    assert series.backward.labels == series.labels
    assert series.backward.backward is None, "one extra level, not a cycle"
    # n_iterations counts the reported chain, and the reverse chain cost more
    # than nothing — the number is not the run's total and does not claim to be
    assert series.backward.n_iterations > 0
    assert series.model_dump_json()  # the extra level round-trips


def test_a_one_directional_series_carries_no_backward(thermal_series):
    assert thermal_series.direction != "both"
    assert thermal_series.backward is None


# -- reporting surfaces ---------------------------------------------------

def test_series_result_json_round_trip(thermal_series):
    text = thermal_series.model_dump_json()
    back = SeriesResult.model_validate(json.loads(text))
    assert len(back) == len(thermal_series)
    assert back.x_label == thermal_series.x_label
    assert back.labels == thermal_series.labels
    assert (back.trajectory("phases.0.cell.a").value
            == thermal_series.trajectory("phases.0.cell.a").value)
    # summaries, not curves: a series must never carry N patterns of y_obs
    assert "y_obs" not in text


def test_write_csv(thermal_series, tmp_path):
    out = tmp_path / "series.csv"
    thermal_series.write_csv(out, paths=["phases.0.cell.a"])
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",") == ["index", "label", "T (K)", "status", "rung",
                                   "rwp", "gof", "phases.0.cell.a",
                                   "phases.0.cell.a_esd"]
    assert len(lines) == len(thermal_series) + 1
    assert lines[1].split(",")[1] == "300K"


def test_the_rung_reaches_json_the_table_and_the_plot(tmp_path):
    """The bookkeeping is only useful where a reader will meet it.

    Built by hand rather than fitted: what is under test is that the three
    reporting surfaces carry the ladder's answer, not that the ladder produces
    one (the tests above do that), and a synthetic series can hold the two rows
    that matter — a rescued point and one nothing rescued — side by side.
    """
    import matplotlib.pyplot as plt

    series = SeriesResult(entries=[
        SeriesEntry(index=0, label="p0", rung="cold", rungs_tried=["cold"],
                    statistics=Statistics(rwp=0.1, rp=0.1, rexp=0.05, chi2=1.0,
                                          gof=1.0, n_points=10,
                                          n_free_parameters=1),
                    parameters=[RefinedParameter(path="phases.0.cell.a",
                                                 value=4.0, stderr=1e-4)]),
        SeriesEntry(index=1, label="p1", rung="cold", reseeded=True,
                    rwp_warm=0.4, rungs_tried=["warm", "warm_staged", "cold"],
                    parameters=[RefinedParameter(path="phases.0.cell.a",
                                                 value=4.1, stderr=1e-4)]),
        SeriesEntry(index=2, label="p2", status="diverged", rung="warm",
                    rungs_tried=["warm", "warm_staged", "cold"],
                    parameters=[RefinedParameter(path="phases.0.cell.a",
                                                 value=9.9, stderr=1e-4)]),
    ])

    back = SeriesResult.model_validate(json.loads(series.model_dump_json()))
    assert [e.rung for e in back] == ["cold", "cold", "warm"]
    assert back[2].rungs_tried == ["warm", "warm_staged", "cold"]

    header, rows = back.to_table(paths=["phases.0.cell.a"])
    assert header[3:5] == ["status", "rung"]
    assert [row[4] for row in rows] == ["cold", "cold", "warm"]

    # the diverged point is crossed out, the rescued one ringed: a ring means
    # "good fit, different starting model", a cross means "not a measurement"
    fig = back.plot(["phases.0.cell.a"])
    markers = [line.get_marker() for line in fig.axes[0].lines]
    assert markers.count("x") == 1 and markers.count("o") >= 1
    fig.savefig(tmp_path / "traj.png")
    plt.close("all")
    assert (tmp_path / "traj.png").stat().st_size > 5_000


def test_plot_trajectory_writes_a_png(thermal_series, tmp_path):
    import matplotlib.pyplot as plt

    out = tmp_path / "trajectory.png"
    thermal_series.plot(["phases.0.cell.a", "instrument.profile.w"], path=out)
    plt.close("all")
    assert out.exists() and out.stat().st_size > 5_000


def test_plot_trajectory_titles_the_figure_only_when_asked(thermal_series):
    """WP-1444: ``title=`` names the whole stack, above the panels' own
    parameter titles, and without it no figure title is drawn at all."""
    import matplotlib.pyplot as plt

    paths = ["phases.0.cell.a", "instrument.profile.w"]
    plain = thermal_series.plot(paths)
    assert plain.get_suptitle() == ""
    titled = thermal_series.plot(paths, title="thermal ramp")
    assert titled.get_suptitle() == "thermal ramp"
    assert [ax.get_title(loc="left") for ax in titled.get_axes()] == paths
    plt.close("all")


@pytest.mark.parametrize("style", ["light", "dark"])
def test_plot_trajectory_draws_every_mark_in_its_styles_role(style):
    """WP-1970: ``style=`` reaches the series figure, so every figure call has
    a dark form.  Each mark takes its role from the style's palette, and the
    ground is the style's, so no light-palette ink is left on a dark page."""
    import matplotlib.pyplot as plt

    from rietx.viz.plots import PALETTES

    def entry(i, value, **kw):
        return SeriesEntry(
            index=i, label=f"p{i}", x=float(i),
            statistics=Statistics(rwp=0.1, rp=0.1, rexp=0.05, chi2=1.0, gof=1.0,
                                  n_points=10, n_free_parameters=1),
            parameters=[RefinedParameter(path="phases.0.cell.a", value=value,
                                         stderr=1e-3)], **kw)

    series = SeriesResult(entries=[
        entry(0, 4.00), entry(1, 4.01, reseeded=True, rung="cold"),
        entry(2, 4.02, status="diverged"), entry(3, 4.03, rwp_fence=0.05)])
    hue = PALETTES[style]
    fig = series.plot(["phases.0.cell.a"], style=style)
    lines = fig.axes[0].lines
    by_marker = {line.get_marker(): line for line in lines if line.get_marker() in "xs"}
    rings = [line for line in lines
             if line.get_marker() == "o" and line.get_markerfacecolor() == "none"]
    assert lines[0].get_color() == hue["series"]
    assert [ring.get_markeredgecolor() for ring in rings] == [hue["reseeded"]]
    assert by_marker["x"].get_color() == hue["unrecovered"]
    assert by_marker["s"].get_markeredgecolor() == hue["outlier"]
    from matplotlib.colors import to_hex
    assert to_hex(fig.get_facecolor()) == hue["ground"]
    plt.close("all")
    with pytest.raises(ValueError, match="style must be one of"):
        series.plot(["phases.0.cell.a"], style="sepia")


def test_qpa_trajectory(thermal_series):
    traj = thermal_series.qpa_trajectory("LaB6")
    assert len(traj) == len(thermal_series)
    # single phase ⇒ 100 wt % at every point
    assert np.allclose(traj.arrays()[1], 100.0)


# -- history --------------------------------------------------------------

def test_one_tree_per_pattern_cross_linked(thermal_patterns, tmp_path):
    """A tree is pinned to one pattern by its data fingerprint, so the series
    is N trees; the chain is recorded as notes on each root node."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins, history=tmp_path / "hist")
    series.fit(thermal_patterns[:3], labels=["t0", "t1", "t2"])

    for name in ("t0", "t1", "t2"):
        assert (tmp_path / "hist" / f"{name}.jsonl").exists()
    trees = series.trees_
    assert len({t.header.tree_id for t in trees}) == 3       # distinct patterns

    roots = [t.root for t in trees]
    assert "series_warm_start_node" not in roots[0].notes    # the cold start
    for k in (1, 2):
        assert roots[k].notes["series_position"] == str(k)
        assert roots[k].notes["series_warm_start_tree"] == trees[k - 1].header.tree_id
        assert roots[k].notes["series_warm_start_node"] is not None

    # each entry points at its own tree, and a reloaded log agrees
    reloaded = rx.RefinementTree.load(tmp_path / "hist" / "t1.jsonl")
    assert reloaded.header.tree_id == series.result_[1].tree_id
    assert reloaded.root.notes["series_label"] == "t1"


def test_the_backward_pass_writes_its_own_logs(thermal_patterns, tmp_path):
    """A verification chain must not append to the reported chain's log.

    The JSONL format is append-only by design, so two headers in one file would
    make the reload ambiguous — ``direction="both"`` writes the backward pass
    to ``<label>.backward.jsonl``."""
    structure, ins = _start_models()
    series = SequentialRefinement(structure, ins, history=tmp_path / "h")
    series.fit(thermal_patterns[:2], labels=["a", "b"], direction="both")

    for name in ("a", "b"):
        forward = tmp_path / "h" / f"{name}.jsonl"
        assert forward.exists()
        assert (tmp_path / "h" / f"{name}.backward.jsonl").exists()
        # exactly one header record, so the log is unambiguously reloadable
        headers = [line for line in forward.read_text(encoding="utf-8").splitlines()
                   if '"record":"header"' in line.replace(" ", "")]
        assert len(headers) == 1
        assert rx.RefinementTree.load(forward).header.tree_id


# -- Le Bail --------------------------------------------------------------

@pytest.mark.slow
def test_lebail_series_carries_extracted_intensities(thermal_patterns):
    """Le Bail intensities are path-dependent state outside θ; a series must
    carry them pattern to pattern rather than re-seeding flat every time."""
    structure, ins = _start_models()
    series = refine_sequential(thermal_patterns[:3], structure, ins,
                               mode="lebail")
    assert series.mode == "lebail"
    assert all(e.status == "converged" for e in series)
    assert all(e.qpa is None for e in series)      # Le Bail scales are degenerate

    a = np.asarray(series.trajectory("phases.0.cell.a").value)
    truth = A0 * (1.0 + RAMP * np.arange(3))
    assert np.allclose(a, truth, atol=2e-4)


# -- argument validation --------------------------------------------------

def test_argument_validation(thermal_patterns):
    structure, ins = _start_models()
    seq = SequentialRefinement(structure, ins)
    with pytest.raises(ValueError, match="at least one pattern"):
        seq.fit([])
    with pytest.raises(ValueError, match="refit must be"):
        seq.fit(thermal_patterns[:1], refit="nope")
    with pytest.raises(ValueError, match="direction must be"):
        seq.fit(thermal_patterns[:1], direction="sideways")
    with pytest.raises(ValueError, match="x has 2 entries"):
        seq.fit(thermal_patterns[:1], x=[1.0, 2.0])
    with pytest.raises(ValueError, match="unknown plan preset"):
        seq.fit(thermal_patterns[:1], plan="does_not_exist")


def _fake_result(rwp: float, *, status: str = "converged", parameters=()):
    """A minimal RefinementResult standing in for a fit, for the guard units."""
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult

    return RefinementResult(
        status=status, mode="rietveld", parameters=list(parameters),
        statistics=Statistics(rwp=rwp, rp=rwp, rexp=0.05, chi2=1.0, gof=1.0,
                              n_points=10, n_free_parameters=1),
        provenance=Provenance(package_version="test"))


def test_series_entry_lookup_helpers():
    entry = SeriesEntry(index=0, parameters=[
        RefinedParameter(path="phases.0.cell.a", value=4.0, stderr=1e-4)])
    assert entry.value("phases.0.cell.a") == 4.0
    assert entry.stderr("phases.0.cell.a") == pytest.approx(1e-4)
    assert entry.value("nope") is None and entry.stderr("nope") is None


# ----------------------------------------------------------------------
# telemetry and cancellation (WP-1016)
# ----------------------------------------------------------------------
#: A one-stage plan freeing the one parameter these tests care about.  The
#: chain's *answers* are the tests above; what is under test here is the stream
#: and the token, so the fits are as cheap as they can be.
_CHEAP = staged.RefinementPlan(stages=[
    staged.Stage("quick", ["phases.*.scale"], max_iter=5)])


def test_unique_labels_disambiguates_by_position():
    """Two files with the same basename is an ordinary series.

    Split out of ``_labels_for`` because a caller that *offers* the labels before
    the run has to show the ones the run will use — a panel displaying the name
    that was typed would be displaying a name that names nothing (WP-1016).
    """
    from rietx.sequential import unique_labels

    assert unique_labels(["a", "b", "a", "a"]) == ["a", "b", "a_2", "a_3"]
    assert unique_labels([]) == []
    # and ``_labels_for`` is that function, not a second copy of the rule
    assert _labels_for([None, None, None], ["x", "x", "y"]) == ["x", "x_1", "y"]


def test_every_patterns_events_carry_its_place_in_the_series():
    """Per-pattern telemetry, and not one new ``EventKind``.

    ``data`` is an open dict on both sides, so five added fields on existing
    kinds is an additive change and ``EVENT_SCHEMA_VERSION`` does not move — the
    rule, and the reason a bump would make the version useless as a
    compatibility signal, are in ``history/events.py``.
    """
    from rietx.history.events import EVENT_SCHEMA_VERSION, EventKind

    patterns = [_simulate(A0 * (1 + RAMP * i), seed=500 + i) for i in range(2)]
    structure, ins = _start_models()
    seen = []
    series = SequentialRefinement(structure, ins).fit(
        patterns, plan=_CHEAP, labels=["lo", "hi"], events=seen.append)

    assert len(series) == 2
    kinds = {e["kind"] for e in seen}
    assert kinds <= set(get_args(EventKind))          # nothing new was invented
    assert {"fit_start", "fit_end", "stage_start", "stage_end"} <= kinds
    assert {e["v"] for e in seen} == {EVENT_SCHEMA_VERSION}

    # every event, not only the fit pair: an ``eval`` from pattern 1 has to be
    # attributable too, or a progress bar cannot tell the two patterns apart
    assert all("series_index" in e["data"] for e in seen)
    starts = [e["data"] for e in seen if e["kind"] == "fit_start"]
    assert [(d["series_index"], d["series_label"]) for d in starts] == [
        (0, "lo"), (1, "hi")]
    assert {d["series_n"] for d in starts} == {2}
    assert {d["series_pass"] for d in starts} == {"forward"}
    # the stamp does not displace the event's own fields
    assert starts[0]["mode"] == "rietveld" and starts[0]["n_points"] == len(
        patterns[0].two_theta)


def test_a_backward_pass_is_the_same_patterns_walked_again():
    """``series_index`` is the pattern's place in the *series*, not in the walk.

    Which is what makes the two chains comparable frame by frame — and
    ``series_pass`` is then the only thing that distinguishes the verification
    pass from a restart, which a counter running 1…N…1 otherwise reads as.
    """
    patterns = [_simulate(A0 * (1 + RAMP * i), seed=600 + i) for i in range(2)]
    structure, ins = _start_models()
    seen = []
    SequentialRefinement(structure, ins).fit(
        patterns, plan=_CHEAP, labels=["lo", "hi"], direction="both",
        events=seen.append)

    walked = [(e["data"]["series_index"], e["data"]["series_pass"])
              for e in seen if e["kind"] == "fit_start"]
    assert walked == [(0, "forward"), (1, "forward"),
                      (1, "backward"), (0, "backward")]


def test_a_cancelled_series_returns_what_it_completed():
    """The rule one level up, not an exception to it.

    ``Refinement.fit`` abandons the stage in flight and raises; a *series* is N
    separate refinements, so the patterns already walked are finished fits with
    committed nodes — raising here would throw them away.  What must not happen
    is silence: a short ``entries`` list is indistinguishable from a shorter
    series that ran to completion, so ``SEQUENTIAL_CANCELLED`` says how far it
    got.
    """
    patterns = [_simulate(A0 * (1 + RAMP * i), seed=700 + i) for i in range(3)]
    structure, ins = _start_models()
    token = CancelToken()

    def watch(event):
        if event["kind"] == "fit_end" and event["data"]["series_index"] == 0:
            token.cancel()

    runner = SequentialRefinement(structure, ins, history=True)
    series = runner.fit(patterns, plan=_CHEAP, events=watch, cancel=token)

    assert len(series) == 1
    assert len(runner.results_) == 1 and len(runner.trees_) == 1
    assert [d.code for d in series.diagnostics] == ["SEQUENTIAL_CANCELLED"]
    assert "after 1 of 3 patterns" in series.diagnostics[0].message
    # the completed pattern is a real fit with a real node
    assert series[0].node_id and series[0].statistics is not None


def test_a_cancelled_chain_does_not_run_the_verification_pass():
    """The comparison is between two *complete* chains; half of one says nothing."""
    patterns = [_simulate(A0 * (1 + RAMP * i), seed=800 + i) for i in range(3)]
    structure, ins = _start_models()
    token = CancelToken()
    passes = []

    def watch(event):
        if event["kind"] == "fit_start":
            passes.append(event["data"]["series_pass"])
        if event["kind"] == "fit_end" and event["data"]["series_index"] == 1:
            token.cancel()

    runner = SequentialRefinement(structure, ins)
    series = runner.fit(patterns, plan=_CHEAP, direction="both", events=watch,
                        cancel=token)

    assert set(passes) == {"forward"}
    assert runner.backward_ is None
    # the comparison that never ran says so (WP-1333): zero
    # SEQUENTIAL_PATH_DEPENDENT findings is what a clean series reports too
    assert [d.code for d in series.diagnostics] == [
        "SEQUENTIAL_CANCELLED", "SEQUENTIAL_PATH_CHECK_INCOMPLETE"]
    not_run = series.diagnostics[1]
    assert not_run.level == "warning"
    assert "did not run" in not_run.message
    assert "forward chain was cancelled" in not_run.message
    assert not any(d.code == "SEQUENTIAL_PATH_DEPENDENT"
                   for d in series.diagnostics)


# ------------------------------------------------ agreement trajectories ---
def test_agreement_trajectory_carries_the_index_across_the_series(thermal_series):
    """``qpa_trajectory``'s shape over the rows PR #99 carried to the boundary.

    The point of the accessor is that a *trend* in R_B is readable where a
    single value is not: WP-1069's warning is about comparing one phase's
    index with another's, not about watching one phase's move with temperature.
    """
    names = thermal_series.agreement_phases()
    assert names, "the fixture carries no agreement rows to trajectory over"
    traj = thermal_series.agreement_trajectory(names[0])
    assert traj.path == f"r_bragg.{names[0]}"
    assert traj.x_label == thermal_series.x_label
    assert len(traj) == len(thermal_series.entries)
    assert traj.x == list(thermal_series.x)
    assert all(v >= 0.0 for v in traj.value)
    # value-for-value the rows themselves, not a recomputation
    assert traj.value == [
        next(r.r_bragg for r in e.phase_agreement if r.name == names[0])
        for e in thermal_series.entries]


def test_the_agreement_esd_column_is_empty_because_a_residual_has_no_esd(
        thermal_series):
    """Not a gap — a fact, and the reason it differs from the other two.

    ``trajectory`` and ``qpa_trajectory`` use ``None`` for "this pattern did
    not estimate one".  Here the whole column is ``None`` for every series,
    because R_Bragg is a residual rather than a fitted parameter and has no
    covariance entry to propagate from.  ``arrays()`` must still work, since a
    plotting caller cannot be asked to special-case one trajectory kind.
    """
    import numpy as np

    name = thermal_series.agreement_phases()[0]
    traj = thermal_series.agreement_trajectory(name)
    assert traj.stderr == [None] * len(traj)
    _x, _v, sd = traj.arrays()
    assert np.isnan(sd).all()


def test_r_f_is_reachable_and_is_a_different_number(thermal_series):
    """Both McCusker indices are offered; a fit quotes at least one of them,
    and which is a reader's convention rather than this method's choice."""
    name = thermal_series.agreement_phases()[0]
    rb = thermal_series.agreement_trajectory(name, metric="r_bragg")
    rf = thermal_series.agreement_trajectory(name, metric="r_f")
    assert rf.path == f"r_f.{name}"
    assert len(rf) == len(rb)
    assert rf.value != rb.value, "r_f and r_bragg returned the same column"
    with pytest.raises(ValueError, match="r_bragg"):
        thermal_series.agreement_trajectory(name, metric="rwp")


def test_resolve_trajectory_is_the_one_dispatch_for_every_kind(thermal_series):
    """The duplicated two-branch conditional ``viz`` and the GUI each carried.

    An unprefixed path must still reach :meth:`trajectory` — that is what makes
    the resolver safe to call unconditionally on a display path.
    """
    name = thermal_series.agreement_phases()[0]
    assert thermal_series.resolve_trajectory(f"r_bragg.{name}").value == \
        thermal_series.agreement_trajectory(name).value
    assert thermal_series.resolve_trajectory(f"r_f.{name}").value == \
        thermal_series.agreement_trajectory(name, metric="r_f").value

    # The arm that already existed is the one a regression would be quietest
    # in: `qpa.` is why the resolver had to keep working at all, since
    # plot_trajectory and gui/series.py were only safe to convert once every
    # kind went through one front door.
    assert thermal_series.is_derived_path("qpa.LaB6")
    assert thermal_series.resolve_trajectory("qpa.LaB6").value == \
        thermal_series.qpa_trajectory("LaB6").value

    param = thermal_series.paths()[0]
    assert not thermal_series.is_derived_path(param)
    assert thermal_series.resolve_trajectory(param).value == \
        thermal_series.trajectory(param).value


def test_a_lebail_series_has_an_empty_agreement_trajectory_not_a_zero_one(
        thermal_series):
    """Absent for cause, one rank up from the entry that is empty for it.

    A zero R_B would read as a perfect fit; an empty trajectory reads as "this
    mode does not produce the number", which is the true statement.
    """
    stripped = SeriesResult(
        entries=[e.model_copy(update={"phase_agreement": []})
                 for e in thermal_series.entries],
        x_label=thermal_series.x_label)
    assert stripped.agreement_phases() == []
    assert len(stripped.agreement_trajectory("anything")) == 0


# -- to_table resolves a path the way everything else does (WP-1310) -------
#
# Issue #162: ``to_table`` called ``SeriesEntry.value``, which scans
# ``parameters`` only, so every derived path came back as a well-formed column
# of ``None`` — the declared-shape-with-a-lying-empty-state class of WP-1076.


def _derived_series() -> SeriesResult:
    """Three patterns; the second has no QPA and the third lacks one phase.

    Hand-built, because what is under test is the *alignment* between a
    trajectory (which skips what it cannot serve) and a table row per entry,
    and a fitted series would carry every phase on every pattern and so could
    not show the skip at all.
    """
    from rietx.schemas.results import (
        PhaseAgreement,
        PhaseQuantity,
        QuantitativePhaseAnalysis,
    )

    def quantity(name, wf, **kw):
        # the scale-and-mass block is required and irrelevant here: the table
        # reads weight_fraction, so these carry one self-consistent set
        return PhaseQuantity(name=name, weight_fraction=wf, scale=1.0,
                             cell_mass=100.0, cell_volume=70.0, zmv=7000.0,
                             **kw)

    def entry(i, *, wf=None, rb=None, extra_phase=False, wf_esd=0.01):
        qpa = None
        if wf is not None:
            rows = [quantity("LaB6", wf, weight_fraction_stderr=wf_esd)]
            if extra_phase:
                rows.append(quantity("CaF2", 1.0 - wf))
            qpa = QuantitativePhaseAnalysis(phases=rows)
        return SeriesEntry(
            index=i, label=f"p{i}", x=float(i),
            statistics=Statistics(rwp=0.1, rp=0.1, rexp=0.05, chi2=1.0,
                                  gof=1.0, n_points=10, n_free_parameters=1),
            parameters=[RefinedParameter(path="phases.0.cell.a",
                                         value=4.0 + 0.01 * i, stderr=1e-4)],
            qpa=qpa,
            phase_agreement=([PhaseAgreement(name="LaB6", r_bragg=rb, r_f=rb)]
                             if rb is not None else []))

    return SeriesResult(entries=[
        entry(0, wf=0.9, rb=0.05, extra_phase=True),
        entry(1, wf=None, rb=0.06),          # no QPA at all on this pattern
        # no agreement index, and a weight fraction whose esd was not estimated
        entry(2, wf=0.8, rb=None, wf_esd=None),
    ])


def test_to_table_exports_a_qpa_path_as_numbers_not_blanks():
    """The issue's headline: a derived path used to yield a column of None."""
    series = _derived_series()
    header, rows = series.to_table(paths=["qpa.LaB6"])

    assert header[7:] == ["qpa.LaB6", "qpa.LaB6_esd"]
    # percentages, and the pattern with no QPA is a hole rather than a zero
    assert [row[7] for row in rows] == [90.0, None, 80.0]
    # the esd column stays, and its two blanks mean different things: pattern 1
    # has no QPA at all, pattern 2 has one whose esd was not estimated
    assert [row[8] for row in rows] == [1.0, None, None]


def test_an_agreement_path_gets_no_esd_column_at_all():
    """An agreement index has ``stderr = None`` by construction, so a column
    of blanks would invite the "zero or absent?" reading WP-1076 removes."""
    series = _derived_series()
    header, rows = series.to_table(paths=["r_bragg.LaB6"])

    assert header[7:] == ["r_bragg.LaB6"]          # no _esd sibling
    assert [row[7] for row in rows] == [0.05, 0.06, None]

    # …while a kind that *has* esds keeps the column even where this series
    # estimated none, because there the blank carries information
    header_p, _ = series.to_table(paths=["phases.0.cell.a"])
    assert header_p[7:] == ["phases.0.cell.a", "phases.0.cell.a_esd"]


def test_the_row_a_trajectory_skipped_stays_aligned():
    """A trajectory is a *subsequence* of the series, so the table cannot zip
    it positionally — the hole has to land on the pattern it belongs to."""
    series = _derived_series()
    traj = series.resolve_trajectory("qpa.LaB6")

    assert len(traj) == 2                      # pattern 1 carries no QPA
    assert traj.positions == [0, 2]            # …and it is *which* two
    _, rows = series.to_table(paths=["qpa.LaB6"])
    assert [row[0] for row in rows] == [0, 1, 2]
    assert rows[1][7] is None and rows[0][7] == 90.0 and rows[2][7] == 80.0


def test_mixed_paths_keep_their_own_column_shapes():
    """Three kinds in one call: the widths differ and must not drift."""
    series = _derived_series()
    header, rows = series.to_table(
        paths=["phases.0.cell.a", "qpa.LaB6", "r_bragg.LaB6"])

    assert header[7:] == ["phases.0.cell.a", "phases.0.cell.a_esd",
                          "qpa.LaB6", "qpa.LaB6_esd", "r_bragg.LaB6"]
    assert all(len(row) == len(header) for row in rows)
    assert rows[0][7] == pytest.approx(4.0)
    assert rows[0][9] == 90.0
    assert rows[0][11] == 0.05


def test_a_path_no_pattern_carries_refuses_by_name():
    """Never a well-formed empty column — and the refusal says what exists."""
    series = _derived_series()

    with pytest.raises(ValueError, match="NotAPhase"):
        series.to_table(paths=["qpa.NotAPhase"])
    with pytest.raises(ValueError, match="agreement index"):
        series.to_table(paths=["r_bragg.NotAPhase"])
    with pytest.raises(ValueError, match="not a refined parameter"):
        series.to_table(paths=["phases.0.cell.nonsense"])

    # the two derived kinds answer with their own vocabulary, which is not the
    # same set: CaF2 has a weight fraction on pattern 0 and never an R_B
    with pytest.raises(ValueError, match="CaF2"):
        series.to_table(paths=["qpa.NotAPhase"])
    with pytest.raises(ValueError, match=r"available: LaB6\)"):
        series.to_table(paths=["r_bragg.NotAPhase"])


def test_write_csv_follows_to_table_through_the_resolver(tmp_path):
    """``write_csv`` is a thin wrapper, so the fix has to reach the file."""
    series = _derived_series()
    out = tmp_path / "derived.csv"
    series.write_csv(out, paths=["r_bragg.LaB6", "qpa.LaB6"])

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",")[7:] == ["r_bragg.LaB6", "qpa.LaB6",
                                       "qpa.LaB6_esd"]
    assert lines[1].split(",")[7:] == ["0.05", "90.0", "1.0"]
    # the skipped pattern writes empty cells, as every other absence does
    assert lines[2].split(",")[7:] == ["0.06", "", ""]


def test_pawley_chain_carried_intensities_refit_as_far_as_cleared():
    """WP-1459 (issue #440): carrying a Pawley pattern's per-hkl intensities to
    the next must not stop the warm refit short.  A reflection centred off the
    data used to grow along the chain (1.45e8 → 2.8e11 → 1.1e12) until TRF's
    step test, relative to ‖x‖, ended pattern 3 after two iterations at 2.81×
    the Rwp of the same chain re-seeded.  ``carry_hkl_intensities=False`` is
    the re-seeded chain; the two must agree to 1e-3 relative on every pattern
    (measured: identical to five digits), and the switch must actually clear
    what the carried chain hands on."""
    from tests.test_pawley import FAP_CIF, _fap_instrument, fap_series

    patterns = fap_series(4)
    seen: dict[bool, list[int]] = {True: [], False: []}
    rwp = {}
    for carry in (True, False):
        def hook(i, ref, carry=carry):
            seen[carry].append(sum(len(r.intensity) for r in ref._pending_reflections))

        sr = SequentialRefinement(rx.Structure.from_cif(str(FAP_CIF)),
                                  _fap_instrument(False),
                                  carry_hkl_intensities=carry)
        series = sr.fit(patterns, mode="pawley", plan="pawley_default",
                        reseed=False, constrain=hook)
        assert all(e.status == "converged" for e in series.entries)
        rwp[carry] = [e.statistics.rwp for e in series.entries]
    assert seen[True][0] == 0 and all(n > 0 for n in seen[True][1:])
    assert seen[False] == [0, 0, 0, 0]
    np.testing.assert_allclose(rwp[True], rwp[False], rtol=1e-3)


# -- a width that grew while the fit got worse (WP-1465, issue #451) -------

def _width_series(path: str, values, stderr, gof, *, diverged=()) -> SeriesResult:
    """A hand-built series carrying one width path and each pattern's GoF.

    Rwp is GoF × 1 %, so the message's Rwp pair is checkable too; only GoF
    enters the test."""
    return SeriesResult(entries=[
        SeriesEntry(index=k, label=f"p{k}",
                    status="diverged" if k in diverged else "converged",
                    statistics=Statistics(rwp=0.01 * g, rp=0.01 * g, rexp=0.01,
                                          chi2=990.0 * g * g, gof=g,
                                          n_points=1000, n_free_parameters=10),
                    parameters=[RefinedParameter(path=path, value=v, stderr=s)])
        for k, (v, s, g) in enumerate(zip(values, stderr, gof, strict=True))])


_GROWING = [0.020, 0.021, 0.070, 0.100, 0.150]
_WORSENING = [1.0, 1.02, 2.0, 3.0, 4.0]


def test_a_width_that_grows_while_the_fit_worsens_is_named_at_its_onset():
    path = "phases.0.lor_strain"
    found = _width_growth_diagnostics(
        _width_series(path, _GROWING, [1e-3] * 5, _WORSENING))
    assert [d.code for d in found] == ["SEQUENTIAL_WIDTH_GROWTH"]
    (d,) = found
    assert d.level == "warning" and d.where == [path]
    # the onset is p2, the first pattern past 3× *and* past 1.5× in GoF
    assert d.value == pytest.approx(0.070 / 0.020)
    assert "from p0 to p2" in d.message and "GoF rose 2.0×" in d.message
    assert "Rwp 1.00% → 2.00%" in d.message
    assert "2 of the 2 patterns after it" in d.message
    assert "reaching 7.5× at p4" in d.message


def test_a_width_that_grows_under_a_flat_fit_is_not_named():
    """The misfit half is what keeps a real broadening silent: the same
    growth, GoF flat."""
    assert _width_growth_diagnostics(_width_series(
        "phases.0.lor_strain", _GROWING, [1e-3] * 5,
        [1.0, 1.1, 1.05, 1.2, 1.1])) == []


def test_the_reference_is_the_first_width_the_series_measured():
    """The round-robin chain's first ``lor_strain`` is 5.85e-5 with an esd of
    3e3, which makes any later width "946×" it.  The reference is the first
    width over WIDTH_GROWTH_SIGMA of its own esds, here p1 at 0.02; against
    that p3 is 2.5×, under the factor, so nothing is named."""
    assert _width_growth_diagnostics(_width_series(
        "phases.0.lor_strain", [5.85e-5, 0.020, 0.030, 0.050],
        [3043.8, 1e-3, 1e-3, 1e-3], [1.0, 1.0, 2.0, 3.0])) == []


def test_a_growth_within_its_esds_is_not_named():
    assert _width_growth_diagnostics(_width_series(
        "phases.0.lor_size", [0.02, 0.03, 0.07, 0.10],
        [6e-3, 0.02, 0.02, 0.03], [1.0, 1.2, 2.0, 3.0])) == []


def test_a_gaussian_width_is_judged_on_its_square_root():
    """``gauss_strain`` is a variance coefficient: 4× in it is 2× in width,
    under the factor, and 16× is 4×, over it."""
    path = "phases.0.gauss_strain"
    assert _width_growth_diagnostics(_width_series(
        path, [0.001, 0.004], [1e-5, 1e-5], [1.0, 2.0])) == []
    (d,) = _width_growth_diagnostics(_width_series(
        path, [0.001, 0.016], [1e-5, 1e-5], [1.0, 2.0]))
    assert d.value == pytest.approx(4.0)
    assert "square root" in d.message


def test_a_quarantined_pattern_neither_references_nor_fires():
    path = "phases.0.lor_strain"
    assert _width_growth_diagnostics(_width_series(
        path, [0.02, 0.5, 0.021], [1e-3] * 3, [1.0, 9.0, 1.0],
        diverged={1})) == []
    # and a diverged *first* pattern is no reference: p1 is, and p3 fires
    (d,) = _width_growth_diagnostics(_width_series(
        path, [0.001, 0.02, 0.03, 0.08], [1e-4, 1e-3, 1e-3, 1e-3],
        [0.5, 1.0, 1.2, 2.0], diverged={0}))
    assert "from p1 to p3" in d.message


def test_a_pattern_above_the_rwp_fence_is_still_read():
    """WP-1465's handover asked for such a pattern to join the quarantine skip.
    Declined, measured: every soaked pattern of the chain below is over the
    fence, since a phase standing in for a missing one is what lifts it there,
    so the skip would leave the finding nothing to fire on (WP-1469)."""
    series = _width_series("phases.0.lor_strain", _GROWING, [1e-3] * 5,
                           _WORSENING)
    for entry in series.entries[1:]:
        entry.rwp_fence = 0.0125
    assert [e.above_fence for e in series.entries][2:] == [True] * 3
    (d,) = _width_growth_diagnostics(series)
    assert "from p0 to p2" in d.message


def test_widths_tied_to_one_column_share_one_finding():
    """``tie_equal("phases.*.lor_strain")`` makes two paths one trajectory; a
    finding each would say one fact twice (the code review's catch)."""
    one = _width_series("phases.0.lor_strain", _GROWING, [1e-3] * 5, _WORSENING)
    for entry in one.entries:
        (row,) = entry.parameters
        entry.parameters.append(row.model_copy(
            update={"path": "phases.1.lor_strain"}))
    (d,) = _width_growth_diagnostics(one)
    assert d.where == ["phases.0.lor_strain", "phases.1.lor_strain"]


def test_a_path_that_is_not_a_phase_width_is_never_judged():
    """The instrument's own widths and a Stephens block are not screened (the
    constant's docstring says why)."""
    for path in ("instrument.profile.y", "phases.0.microstrain.dof.0",
                 "phases.0.cell.a"):
        assert _width_growth_diagnostics(_width_series(
            path, _GROWING, [1e-3] * 5, _WORSENING)) == []


SOAK_WAVELENGTH = 0.4139
SOAK_BKG = [3000.0, -400.0, 100.0]
SOAK_SCALE = 1e-3
#: phase B's fraction along the series: the issue's first five patterns
SOAK_FRACTIONS = [0.0, 0.05, 0.10, 0.15, 0.20]


def _soak_instrument(background):
    ins = rx.Instrument.debye_scherrer(wavelength=SOAK_WAVELENGTH)
    ins.profile.w.value = 4e-3
    ins.background = background
    return ins


def _soak_pattern(fb: float, *, seed: int, strain: float = 0.02) -> rx.PatternData:
    """Issue #451's synthetic: phase B, the LaB6 model with its cell 0.4 %
    larger, at weight fraction ``fb`` beside phase A, both at ``strain``."""
    structure = make_lab6()
    b = structure.phases[0].model_copy(deep=True)
    b.name = "LaB6_expanded"
    for name in "abc":
        getattr(b.cell, name).value = A0 * 1.004
    structure.phases[0].scale.value = SOAK_SCALE * (1 - fb)
    b.scale.value = SOAK_SCALE * fb
    for phase in (structure.phases[0], b):
        phase.lor_strain.value = strain
        for atom in phase.atoms:
            atom.biso.value = 0.4
    structure.phases.append(b)
    ins = _soak_instrument(BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in SOAK_BKG]))
    tt = np.arange(3.0, 30.0, 0.01)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _soak_models(two_phase: bool):
    structure = make_lab6()
    structure.phases[0].scale.value = SOAK_SCALE
    structure.phases[0].lor_strain.value = 0.03
    if two_phase:
        b = structure.phases[0].model_copy(deep=True)
        b.name = "B"
        for name in "abc":
            getattr(b.cell, name).value = A0 * 1.004
        b.scale.value = SOAK_SCALE * 0.3
        structure.phases.append(b)
    ins = _soak_instrument(BackgroundChebyshev.with_terms(13))
    ins.background.coefficients[0].value = 2500.0
    return structure, ins


_SOAK_PLAN = staged.RefinementPlan(stages=[
    staged.Stage("bkg", ["instrument.background.*"]),
    staged.Stage("cell", ["phases.*.cell.*"]),
    staged.Stage("width", ["phases.*.lor_strain"]),
])


def _soak_pngs(runner, stem):
    from pathlib import Path

    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    for k, result in enumerate(runner.results_):
        plot_result(result, path=str(out / f"{stem}_p{k}.png"))
        plot_result(result, path=str(out / f"{stem}_p{k}_zoom.png"),
                    two_theta_range=(20.0, 30.0))


def test_a_phase_standing_in_for_a_missing_one_is_named_from_its_onset():
    """Issue #451's synthetic as a chain: a one-phase model over a specimen
    growing a second phase 0.4 % larger.  The width takes the second phase
    (measured 2.3×, 3.65×, 5.15×, 6.8× the first pattern's over the soaked
    four, GoF 1.9×, 3.1×, 4.2×, 5.1×) and nothing per-pattern says so.  The
    finding names the width at fB = 0.10, the first pattern past both
    thresholds, and the two-phase control names nothing."""
    patterns = [_soak_pattern(fb, seed=100 + k)
                for k, fb in enumerate(SOAK_FRACTIONS)]
    labels = [f"fB={fb:.2f}" for fb in SOAK_FRACTIONS]

    one = SequentialRefinement(*_soak_models(two_phase=False))
    soaked = one.fit(patterns, labels=labels, mode="pawley", plan=_SOAK_PLAN)
    found = [d for d in soaked.diagnostics
             if d.code == "SEQUENTIAL_WIDTH_GROWTH"]
    assert [d.where for d in found] == [["phases.0.lor_strain"]]
    assert "from fB=0.00 to fB=0.10" in found[0].message
    assert found[0].value > 3.0
    # nothing warning-level fires on the soaked patterns themselves
    for entry in soaked.entries:
        assert not [d for d in entry.diagnostics
                    if d.level in ("warning", "error")], entry.label

    two = SequentialRefinement(*_soak_models(two_phase=True))
    control = two.fit(patterns, labels=labels, mode="pawley", plan=_SOAK_PLAN)
    assert not [d for d in control.diagnostics
                if d.code == "SEQUENTIAL_WIDTH_GROWTH"]

    _soak_pngs(one, "wp1465_soak_one_phase")
    _soak_pngs(two, "wp1465_soak_two_phase")


def test_a_width_that_grows_for_real_is_not_named():
    """The clean series the suite had none of: one phase, a correct model,
    and a strain that grows 5× along the series.  The width passes the
    factor and GoF stays flat, so the finding stays silent — the
    "microstrain evolves" rule the skill keeps."""
    strains = [0.02, 0.04, 0.06, 0.08, 0.10]
    patterns = [_soak_pattern(0.0, seed=200 + k, strain=s)
                for k, s in enumerate(strains)]
    runner = SequentialRefinement(*_soak_models(two_phase=False))
    series = runner.fit(patterns, mode="pawley", plan=_SOAK_PLAN)
    _, value, _ = series.trajectory("phases.0.lor_strain").arrays()
    assert value[-1] / value[0] > 4.0          # the width half is met
    gof = [e.statistics.gof for e in series.entries]
    assert max(gof) / gof[0] < 1.2, gof        # the misfit half is not
    assert not [d for d in series.diagnostics
                if d.code == "SEQUENTIAL_WIDTH_GROWTH"]
    _soak_pngs(runner, "wp1465_real_growth")
