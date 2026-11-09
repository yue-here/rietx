"""A tied entry's own bounds, held inside the LM step (WP-1325).

A tied entry is not a column, so the box never holds it.
``tie_window`` closes a one-source tie exactly and a several-source tie
only to an outer box, and a parametric target in each pattern is a sum of
unbounded coefficients.  Before these rows, a fit whose answer put such an
entry past its own bound raised ``ValueError`` at the write-back after the
solve (``ParameterTable.apply_to_models``).  What is checked here:

* the builder (``least_squares.tied_bound_inequalities``): a row only where
  the box does not already imply it, none for a one-source tie, none from a
  default table, none the start violates;
* a single fit with a two-source tie whose data want the dependent below its
  floor: LM holds it on the floor, says so in ``CONSTRAINT_ACTIVE``, and
  reports the held value as ``FLOOR_HIT`` on its path, as a free column on its
  floor is (``staged.tied_bound_findings``);
* a joint fit with a line equation whose free answer dips under the
  target's floor: LM holds every pattern's target in range, the constraint
  diagnostic names the equation once, and ``FLOOR_HIT`` names the pattern
  held there; TRF, which takes no rows, finishes and carries
  ``PARAMETRIC_OUT_OF_RANGE``;
* each face sits a margin inside its bound, so the strict write-back
  never meets a held value a rounding past it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.multi import refine_multi
from rietx.optimize.least_squares import tied_bound_inequalities
from rietx.params.multi import SharingMap
from rietx.params.vector import AffineTie, ParameterTable
from rietx.refine import _constraint_diagnostics
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.parametric import CoordinateTable, ParametricEquation
from tests.test_params import make_bounded_table, make_table
from tests.test_schemas import make_lab6
from tests.test_sequential import A0, TRUE_W, WAVELENGTH, _simulate, _start_models

OUT = Path(__file__).parent / "output"


# -- the builder -------------------------------------------------------------

def _rows(table: ParameterTable):
    lo, hi = table.bounds()
    return tied_bound_inequalities(table, table.x0(), lo, hi)


def test_a_default_table_builds_no_row():
    """Every tie the package derives carries ±inf bounds (``test_params``'s
    ``test_an_unbounded_dependent_claims_nothing``), so an ordinary fit is
    handed exactly the rows it had before."""
    table = make_table()
    table.set_vary(["*"], True)
    assert _rows(table) == []


def test_a_one_source_tie_is_held_by_its_window_and_takes_no_row():
    table = make_bounded_table()                 # biso in [0, 25]
    table.set_vary(["phases.0.atoms.0.biso"], True)
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 2.0),)))
    assert _rows(table) == []                    # [0, 12.5] on the source says it all


def test_a_two_source_tie_takes_the_rows_its_outer_box_cannot_hold():
    table = make_bounded_table()
    table.add_parameter("synthetic.u", 0.0, vary=True)          # unbounded
    table.set_vary(["phases.0.atoms.0.biso"], True)
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 1.0),
                                   ("synthetic.u", 1.0))))
    (block,) = _rows(table)
    assert block.label == "phases.0.atoms.1.biso bounds"
    k = table.free_paths.index("phases.0.atoms.0.biso")
    j = table.free_paths.index("synthetic.u")
    # biso_B = s + u in [0, 25]: s + u ≥ 0 and 25 − s − u ≥ 0
    assert block.T.shape == (2, len(table.free_paths))
    assert block.T[0, k] == block.T[0, j] == 1.0
    assert block.T[1, k] == block.T[1, j] == -1.0
    v = table.entries[table._paths["phases.0.atoms.1.biso"]].value
    np.testing.assert_allclose(block.slack(table.x0()), [v, 25.0 - v])
    # each face a margin inside its bound, never on it: the write-back after
    # the solve checks the bounds exactly (TIED_BOUND_MARGIN)
    assert block.c[0] < 0.0 and block.c[1] < 25.0
    assert -block.c[0] <= 1e-8 and 25.0 - block.c[1] <= 1e-7
    # a bounded co-source whose box already holds both sides adds nothing
    lo, hi = table.bounds()
    lo[j], hi[j] = 0.0, 0.0
    assert tied_bound_inequalities(table, table.x0(), lo, hi) == []


def test_a_row_the_start_breaks_is_left_out():
    table = make_bounded_table()
    table.add_parameter("synthetic.u", -5.0, vary=True)
    table.set_vary(["phases.0.atoms.0.biso"], True)
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 1.0),
                                   ("synthetic.u", 1.0))))
    # biso_B starts at 0.4 − 5 < 0: the floor row is dropped, the ceiling kept
    (block,) = _rows(table)
    assert block.T.shape[0] == 1 and block.c[0] > 0.0


# -- a single fit: a two-source tie pushed past its floor ---------------------

def _pattern_with_b_biso(b_biso: float, seed: int = 3) -> rx.PatternData:
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = A0
    structure.phases[0].atoms[0].biso = Parameter(value=0.4)
    structure.phases[0].atoms[1].biso = Parameter(value=b_biso)
    structure.phases[0].scale.value = 5e-4
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])
    tt = np.arange(3.0, 24.0, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def test_lm_holds_a_two_source_dependent_on_its_floor():
    """B's Biso = La's Biso + d, with d unbounded, so ``tie_window`` gives La
    no window at all, and data simulated at B = −1.5 want B below its floor
    at 0.  LM holds it there and the constraint diagnostic names it."""
    pattern = _pattern_with_b_biso(-1.5)
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = A0
    for atom in structure.phases[0].atoms:
        atom.biso = Parameter(value=0.4, min=0.0, max=25.0)
    structure.phases[0].scale.value = 5e-4
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev.with_terms(3)
    ref = rx.Refinement(structure, ins)
    ref.add_variable("d", 0.0, vary=True)
    ref.tie("phases.0.atoms.1.biso", {"phases.0.atoms.0.biso": 1.0, "vars.d": 1.0})
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("biso", ["phases.0.atoms.0.biso", "vars.d"])])
    result = ref.fit(pattern, plan=plan)       # LM, the default driver
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / "tied_bound_rows_single.png")
    b = ref.structure.phases[0].atoms[1].biso.value
    assert 0.0 <= b < 1e-8, b
    (d,) = [d for d in result.diagnostics if d.code == "CONSTRAINT_ACTIVE"]
    assert "phases.0.atoms.1.biso bounds" in d.message
    # the held value is reported as a free column on its floor is
    (f,) = [d for d in result.diagnostics if d.code == "FLOOR_HIT"]
    assert f.level == "warning" and f.where == ["phases.0.atoms.1.biso"]
    assert "a tied value, held there inside the step" in f.message
    rows = {p.path: p for p in result.parameters}
    assert rows["phases.0.atoms.1.biso"].at_bound is True


def test_a_tied_width_held_on_its_floor_reads_at_zero_in_the_microstructure_block():
    """The microstructure block reads ``FLOOR_HIT`` (WP-1914), and a tied
    width the LM step held on its floor carries one on its own path.  So it
    reads ``at_zero``, as a free width on its floor does.

    ``floored_paths``' closure cannot reach it: ``lor_size = lor_strain + d``
    with ``d`` an unbounded variable is no follower of a floored source.
    Without the finding the held value, a margin above zero, read as a size.
    """
    structure = make_lab6()
    for name in ("a", "b", "c"):
        getattr(structure.phases[0].cell, name).value = A0
    structure.phases[0].scale.value = 5e-4
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.profile.w.value = TRUE_W
    ins.profile.x.value = 0.0
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (40.0, -6.0, 1.5)])
    tt = np.arange(3.0, 24.0, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    y = model.evaluate(ParameterTable(structure, ins).decode(
        ParameterTable(structure, ins).x0()))
    y = np.random.default_rng(5).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    # the instrument's Lorentzian is wider than the data's, so the data want
    # a negative sample width
    ins.profile.x.value = 1e-2
    ins.background = BackgroundChebyshev.with_terms(3)
    structure.phases[0].lor_strain.value = 1e-3
    ref = rx.Refinement(structure, ins)
    ref.add_variable("d", 5e-3, vary=True)
    ref.tie("phases.0.lor_size", {"phases.0.lor_strain": 1.0, "vars.d": 1.0})
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("width", ["phases.0.lor_strain", "vars.d"])])
    result = ref.fit(pattern, plan=plan)       # LM, the default driver
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / "tied_bound_rows_width.png")
    assert 0.0 <= ref.structure.phases[0].lor_size.value < 1e-8
    floors = [d for d in result.diagnostics if d.code == "FLOOR_HIT"
              and d.where == ["phases.0.lor_size"]]
    assert len(floors) == 1 and "a tied value" in floors[0].message
    term = result.microstructure[0].term("lor_size")
    assert term.unavailable == "at_zero", term


# -- a joint fit: a line equation whose free answer dips under the floor -----

#: La's Biso along a five-pattern ramp: flat, then a jump, so the least-squares
#: line through the patterns sits at about −0.14 Å² at 300 K
_BISO = [0.05, 0.05, 0.05, 0.05, 1.2]
_TEMPS = [300.0, 400.0, 500.0, 600.0, 700.0]


def _biso_ramp(solver: str):
    patterns = [_simulate(A0, seed=k, biso=b) for k, b in enumerate(_BISO)]
    structure, ins = _start_models()
    for atom in structure.phases[0].atoms:
        atom.biso.min = 0.0
    return patterns, refine_multi(
        patterns, structure, [ins] * len(_TEMPS), plan="mccusker_structural",
        solver=solver,
        sharing=SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": _TEMPS}, units={"T": "K"}),
        parametric=[ParametricEquation(name="b", target="phases.0.atoms.0.biso",
                                       basis="polynomial", terms=[[], ["T"]])])


@pytest.mark.xdist_group("tied-bound-rows")
def test_lm_holds_a_parametric_target_inside_its_bounds_in_every_pattern():
    _, result = _biso_ramp("lm")
    OUT.mkdir(exist_ok=True)
    for h in (0, len(_TEMPS) - 1):
        result.for_histogram(h).plot(OUT / f"tied_bound_rows_joint_h{h}.png")
    values = []
    for h in range(len(_TEMPS)):
        rows = {p.path: p.value for p in result.for_histogram(h).parameters}
        values.append(rows["phases.0.atoms.0.biso"])
    assert min(values) >= 0.0 and values[0] < 1e-8, values   # held on the floor at 300 K
    assert all(b > a for a, b in zip(values, values[1:])), values
    codes = [d.code for d in result.diagnostics]
    assert "PARAMETRIC_OUT_OF_RANGE" not in codes
    (d,) = [d for d in result.diagnostics if d.code == "CONSTRAINT_ACTIVE"]
    # one block for the equation across its five patterns, never one per pattern
    assert "parametric equation 'b' (phases.0.atoms.0.biso bounds)" in d.message
    assert "hist." not in d.message
    # the pattern held on the floor, by path, as a free column there would be
    floors = [d for d in result.diagnostics if d.code == "FLOOR_HIT"
              and any("atoms.0.biso" in w for w in d.where)]
    assert [d.where for d in floors] == [["hist.0.phases.0.atoms.0.biso"]], floors
    assert floors[0].level == "warning"
    rows = {p.path: p for p in result.parameters}
    assert rows["hist.0.phases.0.atoms.0.biso"].at_bound is True


@pytest.mark.xdist_group("tied-bound-rows")
def test_trf_takes_no_rows_and_finishes_with_the_range_warning():
    """TRF holds no row, so the line takes the target under its floor at 300 K.
    The fit finishes and says so (settled by Claude 2026-11-09, the Stephens
    cone's precedent: a constraint LM cannot hold becomes a warning)."""
    _, result = _biso_ramp("trf")
    OUT.mkdir(exist_ok=True)
    result.for_histogram(0).plot(OUT / "tied_bound_rows_joint_trf_h0.png")
    rows = {p.path: p.value for p in result.for_histogram(0).parameters}
    assert rows["phases.0.atoms.0.biso"] < 0.0        # the equation's value, kept
    (d,) = [d for d in result.diagnostics if d.code == "PARAMETRIC_OUT_OF_RANGE"]
    assert d.level == "warning" and d.where == ["hist.0.phases.0.atoms.0.biso"]
    assert d.value == 1.0 and "histogram 0" in d.message
    assert "FLOOR_HIT" not in {d.code for d in result.diagnostics
                               if "atoms.0.biso" in " ".join(d.where)}


# -- the readers ---------------------------------------------------------------

class _Outcome:
    def __init__(self, by: dict[str, int]):
        self.truncated_by = by
        self.n_constraint_truncations = sum(by.values())


def test_the_gaussian_floor_sentence_reads_past_a_histogram_prefix_and_no_further():
    gaussian = "Gaussian width (the Γ_G² floor"
    (d,) = _constraint_diagnostics("s", _Outcome({"hist.1 instrument.profile (phases.0)": 2}))
    assert gaussian in d.suggestion
    # the Lorentzian floor's rows are not the Gaussian floor's
    (d,) = _constraint_diagnostics(
        "s", _Outcome({"instrument.profile Lorentzian (phases.0)": 2}))
    assert gaussian not in d.suggestion
    (d,) = _constraint_diagnostics("s", _Outcome({"phases.0.atoms.1.biso bounds": 1}))
    assert gaussian not in d.suggestion and "phases.0.atoms.1.biso bounds: 1" in d.message
