"""Named variables: a caller's own parameter that others follow (WP-1119).

The WP's claim is that a variable is a **renaming** — the same constraint,
written in terms of a quantity instead of in terms of whichever model
parameter happened to be nominated as its master.  That claim is checked here
where it is exact (the residual and every Jacobian column) rather than only
where it is convenient (a converged Rwp), for the reason the root CLAUDE.md
gives about a phase scale's FD column: agreeing with the wrong oracle certifies
nothing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.optimize import least_squares
from rietx.optimize.least_squares import _jacobian_for, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import AnisoU
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    perturbed_models,
    synthesize,
)
from tests.test_schemas import make_lab6

#: The four Biso coefficients of the WP's own example: 1, 1, 2, and 1 + 0.5.
COEFFS = ((1.0, 0.0), (1.0, 0.0), (2.0, 0.0), (1.0, 0.5))

#: Ceiling the fixture declares on the master, kept as a *tighter* claim than
#: the one the ties imply.  ``Atom.biso`` is [0, 25] and the coefficient-2
#: dependent puts the master's own ceiling at 12.5
#: (:func:`~rietx.params.vector.tie_window`), so 12.0 is the caller's, not a
#: workaround — which is what it used to be, when the solver's box covered only
#: the free column and a dependent at coefficient 2 sailed past its own ceiling
#: to 50.  ``test_the_declared_ceiling_needs_no_workaround`` is the arm that
#: leaves it at the schema's 25.
MASTER_MAX = 12.0

BISOS = [f"phases.0.atoms.{j}.biso" for j in range(4)]

#: Every test refinement writes its obs/calc/diff for visual inspection
#: (`tests/CLAUDE.md`), because Rwp hides a locally bad fit — and here the two
#: arms are meant to be the *same* fit, so the pair being indistinguishable by
#: eye is the claim these tests make numerically.
OUT = Path(__file__).parent / "output"


def _plot(result, tag: str) -> None:
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"vars_{tag}.png"))
    result.plot(path=str(OUT / f"vars_{tag}_lowangle.png"),
                two_theta_range=(3.0, 10.0))


def four_site_models(*, true: bool, master_max: float = 25.0):
    """LaB6 with two extra B sites, so there are four Biso rows to constrain."""
    s = make_lab6()
    a = TRUE_A if true else TRUE_A + 0.004
    for name in ("a", "b", "c"):
        getattr(s.phases[0].cell, name).value = a
    s.phases[0].scale.value = TRUE_SCALE if true else TRUE_SCALE * 1.8
    s.phases[0].atoms.append(rx.Atom(label="B2", species="B",
                                     x=Parameter(value=0.5),
                                     y=Parameter(value=0.1993),
                                     z=Parameter(value=0.5)))
    s.phases[0].atoms.append(rx.Atom(label="B3", species="B",
                                     x=Parameter(value=0.5),
                                     y=Parameter(value=0.5),
                                     z=Parameter(value=0.1993)))
    for j, b in enumerate((0.7, 1.4, 1.2, 0.9)):
        s.phases[0].atoms[j].biso.value = b
    s.phases[0].atoms[0].biso.max = master_max
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO if true else 0.0
    ins.profile.w.value = TRUE_W if true else TRUE_W * 2.0
    ins.background = (
        BackgroundChebyshev(coefficients=[Parameter(value=v) for v in TRUE_BKG])
        if true else BackgroundChebyshev.with_terms(3))
    return s, ins


@pytest.fixture(scope="module")
def four_site_pattern() -> PatternData:
    s, ins = four_site_models(true=True)
    tt = np.arange(3.0, 24.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, blank, mode="rietveld")
    table = ParameterTable(s, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def dot_path_arm(*, master_max: float = 25.0) -> rx.Refinement:
    """The constraint spelled with ``atoms.0.biso`` nominated as the master."""
    ref = rx.Refinement(*four_site_models(true=False, master_max=master_max))
    for j, (scale, offset) in enumerate(COEFFS):
        if j == 0:
            continue
        ref.tie(BISOS[j], BISOS[0], scale=scale, offset=offset)
    return ref


def variable_arm(*, master_max: float = 25.0) -> rx.Refinement:
    """The same constraint spelled with a named variable as the master."""
    structure, ins = four_site_models(true=False, master_max=master_max)
    ref = rx.Refinement(structure, ins)
    master = structure.phases[0].atoms[0].biso
    ref.add_variable("B_metal", master.value, min=master.min, max=master.max)
    for j, (scale, offset) in enumerate(COEFFS):
        ref.tie(BISOS[j], "vars.B_metal", scale=scale, offset=offset)
    return ref


@pytest.fixture
def ref():
    return rx.Refinement(*perturbed_models())


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


# ------------------------------------------------------------------ the object
def test_a_variable_is_a_row_like_any_other(ref):
    assert ref.add_variable("A", 0.7, min=0.0, max=25.0) == "vars.A"
    row = {r.path: r for r in ref.parameters()}["vars.A"]
    assert (row.value, row.lo, row.hi) == (0.7, 0.0, 25.0)
    assert row.tie is None and not row.locked and not row.mode_fixed
    assert row.refinable and not row.vary
    # an ordinary dot-path from there on: the glob frees it, set_values moves it
    assert ref.set_vary("vars.*", True) == ["vars.A"]
    ref.set_values({"vars.A": 1.1})
    assert {r.path: r for r in ref.parameters()}["vars.A"].value == 1.1


def test_the_declaration_is_the_parameter_and_the_table_reads_it(ref):
    """Bounds reach the table, which is what makes it a renaming."""
    ref.add_variable("S", 3.0, min=0.0, unit="arb")
    entry = {e.path: e for e in ref._working_table().entries}["vars.S"]
    assert (entry.lo, entry.hi) == (0.0, np.inf)


def test_add_variable_refuses_a_name_a_glob_could_not_reach(ref):
    for name in ("a.b", "A*", "", "2A"):
        with pytest.raises(ValueError, match="single identifier"):
            ref.add_variable(name, 1.0)
    ref.add_variable("A", 1.0)
    with pytest.raises(ValueError, match="already exists"):
        ref.add_variable("A", 2.0)


def test_remove_variable_refuses_under_a_dependent_and_names_it(ref):
    ref.add_variable("A", 0.7, min=0.0, max=25.0)
    ref.tie("phases.0.atoms.0.biso", "vars.A")
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.0\.biso"):
        ref.remove_variable("A")
    ref.untie("phases.0.atoms.0.biso")
    assert ref.remove_variable("A") == "vars.A"
    assert "vars.A" not in {r.path for r in ref.parameters()}
    with pytest.raises(ValueError, match="no variable named"):
        ref.remove_variable("A")


# ------------------------------------------------------------- multi-term ties
def test_tie_takes_several_sources_and_scale_multiplies_every_term(ref):
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    ref.add_variable("C", 0.3, min=0.0, max=25.0)
    ref.tie("phases.0.atoms.0.biso", {"vars.A": 1.0, "vars.C": 1.0})
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.atoms.0.biso"].tie.terms == [("vars.A", 1.0), ("vars.C", 1.0)]
    assert rows["phases.0.atoms.0.biso"].value == pytest.approx(0.7)

    # the pair-sequence spelling, and scale on every term
    ref.tie("phases.0.atoms.1.biso", [("vars.A", 1.0), ("vars.C", 2.0)], scale=2.0)
    tie = {r.path: r for r in ref.parameters()}["phases.0.atoms.1.biso"].tie
    assert tie.terms == [("vars.A", 2.0), ("vars.C", 4.0)]


def test_a_repeated_source_is_refused_rather_than_summed(ref):
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    with pytest.raises(ValueError, match="appears twice"):
        ref.tie("phases.0.atoms.0.biso", [("vars.A", 1.0), ("vars.A", 2.0)])
    with pytest.raises(ValueError, match="at least one source"):
        ref.tie("phases.0.atoms.0.biso", {})


# ------------------------------------------------------------- the chain rule
def test_a_variable_may_follow_variables_and_a_model_path_may_not(ref):
    """WP-1119's chain decision, both halves.

    The table has always flattened chains exactly, so this is a judgement about
    what a caller meant rather than a limit of the machinery: composing is the
    point between variables, and misleading on a model path, where the tie
    quietly inherits a constant nobody wrote.
    """
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    ref.add_variable("C", 0.3, min=0.0, max=25.0)
    ref.add_variable("B", 0.0, min=0.0, max=25.0)
    ref.tie("vars.B", {"vars.A": 1.0, "vars.C": 1.0})
    ref.tie("phases.0.atoms.0.biso", "vars.B")     # follows a tied variable
    ref.set_vary(["vars.A", "vars.C"], True)

    table = ref._working_table()
    paths = [e.path for e in table.entries]
    C, d = table.constraint_block()
    row = C.toarray()[paths.index("phases.0.atoms.0.biso")]
    columns = dict(zip(table.free_paths, row, strict=True))
    assert columns["vars.A"] == 1.0 and columns["vars.C"] == 1.0
    assert d[paths.index("phases.0.atoms.0.biso")] == 0.0
    assert {e.path: e.value for e in table.entries}["phases.0.atoms.0.biso"] == 0.7

    with pytest.raises(ValueError, match="carries no freedom of its own"):
        ref.tie("phases.0.atoms.1.biso", "phases.0.atoms.0.biso")


def test_a_cycle_between_variables_is_refused(ref):
    ref.add_variable("A", 0.4, min=0.0, max=25.0)
    ref.add_variable("B", 0.4, min=0.0, max=25.0)
    ref.tie("vars.B", "vars.A")
    with pytest.raises(ValueError):
        ref.tie("vars.A", "vars.B")


# ------------------------------------------------- the equivalence bar, exactly
def test_the_residual_and_every_column_match_the_dot_path_spelling(
        four_site_pattern):
    """Where the claim is exact: the model, not the solver's path through it.

    The two arms differ only in *which* free parameter the four Biso rows
    follow, so the residual must agree bit for bit and each Jacobian column
    must agree with the column carrying the same parameter.  Before the
    dispatch fix in ``_column_identities`` the master's own column disagreed by
    8.6e-7 — the variable's name matched no analytic branch, so it silently
    took the whole-model FD fallback while the dot-path arm took the peak
    chain.
    """
    a, b = dot_path_arm(), variable_arm()
    a.set_vary([BISOS[0], "phases.0.scale"], True)
    b.set_vary(["vars.B_metal", "phases.0.scale"], True)
    ta, tb = a._working_table(), b._working_table()

    # the physical state the two tables decode to is identical, path by path
    va = {e.path: e.value for e in ta.entries}
    vb = {e.path: e.value for e in tb.entries}
    assert all(va[p] == vb[p] for p in va if p in vb)

    ma = compile_model(a.structure, a.instrument, four_site_pattern,
                       mode="rietveld")
    mb = compile_model(b.structure, b.instrument, four_site_pattern,
                       mode="rietveld")
    ra = _make_residual(ma, ta)(ta.x0())
    rb = _make_residual(mb, tb)(tb.x0())
    assert np.array_equal(ra, rb), "the two spellings are not the same model"

    ja = np.asarray(_jacobian_for(ma, ta, "numpy")(ta.x0()))
    jb = np.asarray(_jacobian_for(mb, tb, "numpy")(tb.x0()))
    assert ja.shape == jb.shape
    same_column = {BISOS[0]: "vars.B_metal"}
    for i, path in enumerate(ta.free_paths):
        j = tb.free_paths.index(same_column.get(path, path))
        assert np.array_equal(ja[:, i], jb[:, j]), f"column {path} differs"


def test_the_fit_is_bit_identical_where_the_column_order_coincides(
        four_site_pattern):
    """One free column, so both arms put it at the same index of θ.

    This is the control for the tolerance the next test carries: the columns
    are identical either way (above), so anything left is the solver reading θ
    in a different order — and with one column there is no different order to
    read.  Rwp, χ², the iteration count, every dependent's value and the esd
    all come back bit for bit.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=40)])
    a, b = dot_path_arm(master_max=MASTER_MAX), variable_arm(master_max=MASTER_MAX)
    ra = a.fit(four_site_pattern, plan=plan)
    rb = b.fit(four_site_pattern, plan=plan)
    _plot(ra, "onecol_dotpath")
    _plot(rb, "onecol_variable")

    assert a._working_table().free_paths == [BISOS[0]]
    assert b._working_table().free_paths == ["vars.B_metal"]
    assert ra.statistics.rwp == rb.statistics.rwp
    assert ra.statistics.chi2 == rb.statistics.chi2
    assert [s.n_iterations for s in ra.stages] == [s.n_iterations for s in rb.stages]
    for j in range(4):
        assert (a.fitted_structure.phases[0].atoms[j].biso.value
                == b.fitted_structure.phases[0].atoms[j].biso.value)
    esd_a = {p.path: p.stderr for p in ra.parameters}[BISOS[0]]
    esd_b = {p.path: p.stderr for p in rb.parameters}["vars.B_metal"]
    assert esd_a == esd_b


def test_the_converged_fit_agrees_when_the_variable_sits_elsewhere_in_theta(
        four_site_pattern):
    """A variable is appended, so in a multi-stage plan it is θ's *last* column.

    The columns are identical (above) and a one-free-column fit is bit-identical
    (above), so all that is left here is scipy's TRF reading the same columns in
    a different order.  Measured on this fixture (Rwp 0.0419, GoF 1.03, nine
    free), that costs **nothing**: Rwp, the per-stage iteration counts and every
    refined value come back bit for bit, and the master's esd within one ulp
    (4.2e-16 relative).

    The bar on the refined values is `rel=1e-9` rather than an equality, and it
    carries its margin both ways rather than being picked.  Above: the
    agreement it must pass is 4.2e-16 on macOS, six orders under it, and under
    the bar again on Linux.  Below: with `_column_identities` disabled — the
    variable's column back on the whole-model FD fallback — the same comparison
    returns **1.14e-8** on the refined Biso, eleven times over, and the last
    stage stops at **4 iterations instead of 9** because the approximate column
    convinces the solver it has converged.  An equality is the wrong shape here
    for the reason `tests/CLAUDE.md` gives: a tolerance between two
    independently-converged fits is a cross-platform claim, and this
    measurement is one platform.

    **The esd is not one of the discriminating arms** and its bar is 1e-6; the
    comment beside it has the measurement that settled that, and the two arms
    that do carry the claim are the values above and the integer iteration
    counts.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=30),
        rx.Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"],
                 max_iter=30),
        # The fixture perturbs the profile width 2x, so a plan that never frees
        # it converges at Rwp ~0.57 and every esd it quotes is inflated by the
        # misfit — which would make "the two arms agree far inside the esd" a
        # weaker statement than it reads as (tests/CLAUDE.md: look at the plot).
        # `w` and `x` only, not `profile.*`: this pattern does not determine
        # `u`, `v` or `y`, and `y` in particular sits on its softplus floor, so
        # the whole glob leaves a near-flat direction in the free set. That
        # costs nothing in the fitted *values* — they agree between the two arms
        # to 3e-9 of an esd either way — but it makes the **esds** themselves
        # order-sensitive at 1e-4, since `normal_covariance` equilibrates and
        # then cuts eigenvalues at `rcond·|λ|max`, and a near-threshold
        # eigenvalue is decided differently under a different column order.
        rx.Stage("profile", ["instrument.profile.w", "instrument.profile.x"],
                 max_iter=30),
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=30),
    ])
    a, b = dot_path_arm(), variable_arm()
    ra = a.fit(four_site_pattern, plan=plan)
    rb = b.fit(four_site_pattern, plan=plan)
    _plot(ra, "converged_dotpath")
    _plot(rb, "converged_variable")

    assert (ra.statistics.n_free_parameters
            == rb.statistics.n_free_parameters), "a renaming changed the count"
    assert [s.n_iterations for s in ra.stages] == [s.n_iterations for s in rb.stages]
    assert rb.statistics.rwp == pytest.approx(ra.statistics.rwp, rel=1e-9)
    for j in range(4):
        x = a.fitted_structure.phases[0].atoms[j].biso.value
        y = b.fitted_structure.phases[0].atoms[j].biso.value
        assert y == pytest.approx(x, rel=1e-9)
    # The esd is the **weak** arm here and its bar says so: 1e-6, not the 1e-9
    # the values carry.  It is the one quantity in this comparison that goes
    # through `normal_covariance`, which equilibrates and then cuts eigenvalues
    # at `rcond·|λ|max`, so a near-threshold eigenvalue is decided differently
    # under a different column order — the effect the plan above already
    # narrowed from 1e-4 to nothing measurable on macOS (4.2e-16) and which
    # comes back at **2.5e-9 on Linux py3.12/3.14**.  That is within 2x of the
    # 4.1e-9 the broken column returns, so no bar on the esd separates good
    # from broken across platforms, and pretending otherwise is what made this
    # red.  The discrimination lives in the two arms that do hold: the refined
    # values at `rel=1e-9` against the broken column's 1.14e-8, and the
    # per-stage iteration counts above, which are integers — 9 against 4.
    esd_a = {p.path: p.stderr for p in ra.parameters}[BISOS[0]]
    esd_b = {p.path: p.stderr for p in rb.parameters}["vars.B_metal"]
    assert esd_b == pytest.approx(esd_a, rel=1e-6)


def test_the_parameter_count_drops_by_the_number_of_dependents(ref, pattern):
    before = len(ref._working_table().free_paths)
    ref.set_vary(["phases.0.atoms.*.biso"], True)
    freed = len(ref._working_table().free_paths)
    assert freed == before + 2

    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    for path in ("phases.0.atoms.0.biso", "phases.0.atoms.1.biso"):
        ref.tie(path, "vars.B_all")
    after = ref._working_table().free_paths
    assert len(after) == freed - 2 + 1
    assert "vars.B_all" in after
    assert not any(p.endswith(".biso") for p in after)


# ------------------------------------------------------------------ persistence
def test_a_fit_moves_the_variable_and_the_next_build_starts_from_there(
        four_site_pattern):
    """``apply_to_models`` has nothing to write a variable to, so ``_write_back``
    is the only thing that carries its refined value forward.  Without it the
    next table build re-declares the variable at its *declared* value and every
    dependent silently reverts."""
    plan = rx.RefinementPlan(stages=[
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=40)])
    ref = variable_arm(master_max=MASTER_MAX)
    declared = ref._variables["B_metal"].value
    _plot(ref.fit(four_site_pattern, plan=plan), "write_back")

    refined = ref._variables["B_metal"].value
    assert refined != declared
    rebuilt = {e.path: e.value for e in ref._working_table().entries}
    assert rebuilt["vars.B_metal"] == refined
    assert rebuilt[BISOS[2]] == pytest.approx(2.0 * refined)
    # and the models agree with the register, which is the whole point
    assert ref.fitted_structure.phases[0].atoms[0].biso.value == refined


def test_a_variable_survives_a_history_checkout_with_its_parameter_count(
        ref, pattern):
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=20)])
    ref.fit(pattern, plan=plan)
    before = ref.history.head

    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    ref.tie("phases.0.atoms.0.biso", "vars.B_all")
    ref.tie("phases.0.atoms.1.biso", "vars.B_all", scale=2.0)
    declared = ref.history.head
    n_with = len(ref._working_table().free_paths)

    ref.checkout(before)
    assert ref._variables == {}
    assert "vars.B_all" not in {r.path for r in ref.parameters()}

    ref.checkout(declared)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["vars.B_all"].vary
    assert rows["phases.0.atoms.1.biso"].tie.terms == [("vars.B_all", 2.0)]
    assert len(ref._working_table().free_paths) == n_with


def test_a_set_variable_node_renders_an_api_call_that_runs(ref, pattern):
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=5)])
    ref.fit(pattern, plan=plan)
    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    ref.add_variable("B_extra", 0.1, min=0.0, max=25.0)
    # a one-entry dict *is* a one-source tie, and renders as the spelling that
    # says so; only a genuinely multi-source tie takes the mapping form, which
    # is the call WP-1119 gave the verb and the comment it replaced
    ref.tie("phases.0.atoms.0.biso", {"vars.B_all": 1.0})
    ref.tie("phases.0.atoms.1.biso", {"vars.B_all": 1.0, "vars.B_extra": 2.0})
    calls = [n.action.api_call() for n in ref.history.nodes.values()
             if n.action.kind in ("set_variable", "set_tie")]
    assert calls == [
        "ref.add_variable('B_all', 0.7, vary=True, min=0.0, max=25.0)",
        "ref.add_variable('B_extra', 0.1, min=0.0, max=25.0)",
        "ref.tie('phases.0.atoms.0.biso', 'vars.B_all')",
        "ref.tie('phases.0.atoms.1.biso', "
        "{'vars.B_all': 1.0, 'vars.B_extra': 2.0})",
    ]
    # the rendered calls run, and reproduce the state they describe
    replay = rx.Refinement(*perturbed_models())
    for call in calls:
        eval(compile(call, "<api_call>", "eval"), {"ref": replay, "rx": rx})
    assert ({r.path: r for r in replay.parameters()}["phases.0.atoms.0.biso"]
            .tie.terms == [("vars.B_all", 1.0)])


def test_a_variable_survives_a_history_file_round_trip(ref, pattern, tmp_path):
    path = tmp_path / "vars.jsonl"
    ref = rx.Refinement(*perturbed_models(), history=str(path))
    ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=5)]))
    ref.add_variable("B_all", 0.7, min=0.0, max=25.0, vary=True)
    ref.tie("phases.0.atoms.0.biso", "vars.B_all")
    head = ref.history.head

    reloaded = rx.RefinementTree.load(path)
    state = reloaded[head].state
    assert state.variables["B_all"].value == 0.7
    assert state.variables["B_all"].max == 25.0
    assert state.ties["phases.0.atoms.0.biso"].terms == [("vars.B_all", 1.0)]


def test_a_dependent_that_becomes_symmetry_tied_is_reported_and_dropped(ref):
    """Symmetry outranks a user tie, and a variable's dependents inherit that."""
    ref.add_variable("L", 4.16, min=1.5, max=10.0)
    structure = ref.structure.model_copy(deep=True)
    structure.phases[0].space_group = "P 1"   # b is nobody's dependent here
    ref.edit(structure=structure)
    ref.tie("phases.0.cell.b", "vars.L")
    assert {r.path: r for r in ref.parameters()}["phases.0.cell.b"].tie.user

    structure = ref.structure.model_copy(deep=True)
    structure.phases[0].space_group = "P m -3 m"   # now b follows a
    with pytest.warns(UserWarning, match="no longer apply"):
        ref.edit(structure=structure)
    rows = {r.path: r for r in ref.parameters()}
    assert rows["phases.0.cell.b"].tie.sources == ["phases.0.cell.a"]
    assert not rows["phases.0.cell.b"].tie.user
    # the register was pruned against the model that was accepted
    assert "phases.0.cell.b" not in ref._ties
    # and the variable itself is untouched: nothing followed it any more
    assert ref.remove_variable("L") == "vars.L"


def test_the_declared_ceiling_needs_no_workaround(four_site_pattern):
    """The whole fixture at ``Atom.biso``'s own [0, 25], and it converges.

    The coefficient-2 dependent implies a ceiling of 12.5 on the master and the
    ``+ 0.5`` one a floor of −0.5; intersected with the master's own [0, 25]
    that is [0, 12.5], which is inside where this pattern's answer lies.  So
    both arms reach the same fit the ``MASTER_MAX`` arms do — the workaround
    was never load-bearing once the window exists, and this is the assertion
    that says so rather than the comment.

    Run on the **four-stage** plan, not a Biso-only one: an earlier draft froze
    the scale and the width the fixture perturbs and converged at Rwp 2.64, so
    the two arms agreed about a fit that was nothing like the data.  Two
    spellings of one constraint agree on a bad fit too; the claim here is that
    they agree on a *good* one, which is why the Rwp bar is asserted.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                 max_iter=30),
        rx.Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"], max_iter=30),
        rx.Stage("profile", ["instrument.profile.w", "instrument.profile.x"],
                 max_iter=30),
        rx.Stage("biso", ["phases.*.atoms.*.biso", "vars.*"], max_iter=30)])
    a = dot_path_arm()          # master_max=25.0, the schema's own
    b = variable_arm()
    ra, rb = a.fit(four_site_pattern, plan=plan), b.fit(four_site_pattern, plan=plan)
    _plot(ra, "schema_ceiling_dotpath")
    _plot(rb, "schema_ceiling_variable")
    # `rel=1e-9`, not an equality, for the reason the sibling equivalence test
    # states: two *independently converged* fits agreeing bit for bit is a
    # cross-platform claim, and any one run measures one platform.  These two
    # arms are bit-identical on macOS and **1 ulp apart** (1.7e-16 relative) on
    # Linux py3.12/3.14 — the same nine columns read in a different order by a
    # different BLAS.  The bar keeps the claim (the same fit, seven orders of
    # margin) and the line below is what makes it a *good* fit rather than a
    # shared failure.
    assert ra.statistics.rwp == pytest.approx(rb.statistics.rwp, rel=1e-9)
    assert ra.statistics.rwp < 0.05          # the same fit, not the same failure
    rows = {r.path: r.value for r in a.parameters()}
    for j in range(len(COEFFS)):
        assert 0.0 <= rows[BISOS[j]] <= 25.0


def test_a_tie_holds_its_source_where_the_dependents_ceiling_is(four_site_pattern,
                                                                monkeypatch):
    """A runaway that used to end in a bare pydantic error now ends at a bound.

    The dependent declares a ceiling of 0.33 and follows the master at
    coefficient 0.5, which puts the master's own ceiling at 0.66 — just under
    the 0.6697 this pattern's answer wants.  So the fit converges properly (this
    is the same four-stage plan the equivalence bar uses, and the plot is a good
    one), *and* runs into the derived limit, which is the pair of things the
    check needs.  The master stops at 0.66, the dependent at its declared 0.33,
    and the stop is **reported** — ``bound_findings`` reads the same
    ``bounds()`` the window is applied in, so a source held somewhere it never
    declared comes back as ``BOUND_HIT`` like any other bound a stage imposed.

    Without the window the dependent's own row holds it, inside the LM step
    (WP-1325, ``least_squares.tied_bound_inequalities``, which builds it only
    where the box does not already hold it), and the fit lands in the same
    place.  Without either, the master reaches 0.6697, the dependent 0.3348,
    and the first thing to notice is pydantic inside ``apply_to_models`` —
    measured below, by disabling both on a copy of the same fit.
    """
    def run(*, window: bool, rows: bool = True) -> tuple[object, dict[str, float]]:
        structure, instrument = four_site_models(true=False)
        structure.phases[0].atoms[0].biso.value = 0.3    # starts well inside 0.66
        structure.phases[0].atoms[1].biso.value = 0.15   # value first: max validates it
        structure.phases[0].atoms[1].biso.max = 0.33
        ref = rx.Refinement(structure, instrument)
        ref.tie(BISOS[1], BISOS[0], scale=0.5)
        if not window:
            # setattr, never `del` after assigning: the real method lives on the
            # class, so overwriting it and deleting the overwrite removes the
            # method itself — which passed alone and took 21 unrelated tests
            # down under ``-n auto``, in whichever worker ran this one first.
            monkeypatch.setattr(ParameterTable, "_derive_tie_windows",
                                lambda self, tied, d: {})
        if not rows:
            monkeypatch.setattr(least_squares, "tied_bound_inequalities",
                                lambda table, x0, lo, hi: [])
        result = ref.fit(four_site_pattern, plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                     max_iter=30),
            rx.Stage("cell", ["phases.*.cell.*", "instrument.zero_shift"],
                     max_iter=30),
            rx.Stage("profile", ["instrument.profile.w", "instrument.profile.x"],
                     max_iter=30),
            rx.Stage("biso", [BISOS[0]], max_iter=30)]))
        return result, {r.path: r.value for r in ref.parameters()}

    result, rows = run(window=True)
    _plot(result, "tie_window_bound")
    assert result.statistics.rwp < 0.06                 # a converged fit, not a stuck one
    assert rows[BISOS[0]] == pytest.approx(0.66, rel=1e-9)
    assert rows[BISOS[1]] == pytest.approx(0.33, rel=1e-9)
    assert rows[BISOS[1]] <= 0.33                       # inside its declared ceiling
    assert any(d.code == "BOUND_HIT" and BISOS[0] in d.where
               for d in result.diagnostics)

    result, rows = run(window=False)
    # the row's face sits TIED_BOUND_MARGIN of its scale inside the ceiling
    assert rows[BISOS[1]] == pytest.approx(0.33, rel=1e-8)
    assert rows[BISOS[1]] <= 0.33
    assert any(d.code == "CONSTRAINT_ACTIVE"
               and f"{BISOS[1]} bounds" in d.message for d in result.diagnostics)
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.1\.biso=0\.33.*"
                                         r"0\.5\u00b7phases\.0\.atoms\.0\.biso"):
        run(window=False, rows=False)


# ------------------------------------------ a tie onto a coordinate DOF (1432)
#: LaB6's B site is 6f — one site-symmetry-allowed direction, so one DOF — and
#: ``perturbed_models`` stores its x there.  The anchor is what every assertion
#: below is written against: the coordinate the tie was declared over.
B_X = "phases.0.atoms.1.x"
B_DOF = "phases.0.atoms.1.dof.0"
B_X0 = 0.1993

#: Ten write-throughs, which is WP-1432's acceptance.  The defect added the
#: source's whole value at each one, so ten of them moved a coordinate by ten
#: times what the caller declared.
WRITE_THROUGHS = 10


@pytest.fixture
def ref_aniso():
    """The same refinement with an anisotropic B site, for the ADP control."""
    structure, ins = perturbed_models()
    atom = structure.phases[0].atoms[1]
    atom.biso.vary = False
    atom.aniso = AnisoU.from_values([0.01, 0.01, 0.01, 0.0, 0.0, 0.0])
    return rx.Refinement(structure, ins)


#: Where the second B site is stored, so a displacement off it is readable.
B2_X0 = 0.30


def two_site_refinement() -> rx.Refinement:
    """A second 6f B site, so one coordinate DOF can follow another."""
    structure, ins = perturbed_models()
    structure.phases[0].atoms.append(
        rx.Atom(label="B2", species="B", x=Parameter(value=B2_X0),
                y=Parameter(value=0.5), z=Parameter(value=0.5)))
    return rx.Refinement(structure, ins)


@pytest.fixture
def ref_two_sites():
    return two_site_refinement()


def values(ref) -> dict[str, float]:
    return {r.path: r.value for r in ref.parameters()}


def write_through(ref) -> None:
    """A verb that rebuilds the table and writes the models back.

    Unrelated to the tie on purpose: ``phases.0.scale`` shares nothing with a
    coordinate, so anything that moves is the rebuild and not the write.
    """
    ref.set_values({"phases.0.scale": 0.02})


def test_a_variable_driving_a_coordinate_dof_survives_ten_write_throughs(ref):
    """The defect WP-1432 names, and the one a caller cannot see happening.

    A coordinate DOF is a *displacement from the stored coordinate*, so every
    table build anchors ``x`` at what the model holds and rederives the DOF to
    zero.  A variable is the opposite — re-declared from the register at the
    value it holds — so the two together made each rebuild add the variable's
    whole value to a coordinate that had already absorbed it.  The tie means
    one displacement, not one per verb.
    """
    ref.add_variable("A", 0.01, min=-0.5, max=0.5)
    ref.tie(B_DOF, "vars.A")
    # the tie takes its implied value immediately, which is the one application
    assert values(ref)[B_X] == pytest.approx(B_X0 + 0.01)

    for _ in range(WRITE_THROUGHS):
        write_through(ref)
        rows = values(ref)
        assert rows["vars.A"] == 0.01                  # the source never moved
        assert rows[B_DOF] == pytest.approx(0.01)      # the DOF *is* the variable
        assert rows[B_X] == pytest.approx(B_X0 + 0.01)


def test_an_adp_dof_under_the_same_tie_is_the_control(ref_aniso):
    """The first control, and it is what bounds the class.

    An ADP DOF is **absolute** — ``adp_basis`` spans the whole allowed
    subspace, so the entry carries U itself rather than a displacement, and its
    dependents' ``AffineTie`` has no ``const`` to accumulate into.  Tied to the
    same kind of source it held its value before the repair, which is what says
    the defect is the coordinate anchor and not the tie machinery.
    """
    adp = next(r.path for r in ref_aniso.parameters() if ".adp." in r.path)
    ref_aniso.add_variable("A", 0.02, min=0.0, max=0.5)
    ref_aniso.tie(adp, "vars.A")

    for _ in range(WRITE_THROUGHS):
        write_through(ref_aniso)
        assert values(ref_aniso)[adp] == pytest.approx(0.02)


def test_a_coordinate_dof_following_another_is_the_control(ref_two_sites):
    """The second control: both ends reset together, so nothing accumulates.

    The source is rederived to zero on every build exactly as the target is, so
    the implied displacement is zero at each one and both coordinates keep the
    values the model stores.  This is the arm that stays bit-identical through
    the repair — the fix is about a source that does *not* reset.
    """
    ref_two_sites.tie("phases.0.atoms.2.dof.0", B_DOF)
    before = values(ref_two_sites)

    for _ in range(WRITE_THROUGHS):
        write_through(ref_two_sites)
        rows = values(ref_two_sites)
        for path in (B_X, B_DOF, "phases.0.atoms.2.x", "phases.0.atoms.2.dof.0"):
            assert rows[path] == before[path]


def test_a_second_fit_reports_what_the_first_one_did(ref, pattern):
    """The quiet half of WP-1432, and the one a caller reads as a number.

    Fitting twice rebuilds the table between the two solves, so the defect ran
    once in the middle: the refined displacement had migrated into the base
    coordinate, the second fit found it already there, and the variable that
    named it came back at zero at an identical Rwp. The quantity a caller asked
    for was still in the structure and no longer in the answer.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("displacement", ["vars.*"], max_iter=40)])
    ref.add_variable("A", 0.01, min=-0.5, max=0.5)
    ref.tie(B_DOF, "vars.A")

    first = ref.fit(pattern, plan=plan)
    _plot(first, "dof_first_fit")
    a1 = ref._variables["A"].value
    x1 = ref.fitted_structure.phases[0].atoms[1].x.value

    second = ref.fit(pattern, plan=plan)
    _plot(second, "dof_second_fit")
    a2 = ref._variables["A"].value
    x2 = ref.fitted_structure.phases[0].atoms[1].x.value

    # the same answer, and the structure still standing where the first fit
    # left it — the two are one claim, since the defect moved them apart
    assert a2 == pytest.approx(a1, abs=1e-6)
    assert x2 == pytest.approx(x1, abs=1e-6)
    assert x2 == pytest.approx(B_X0 + a2, abs=1e-9)
    assert second.statistics.rwp == pytest.approx(first.statistics.rwp, rel=1e-3)


#: The antiphase pair: one variable, two sites, opposite signs.
ANTIPHASE = ((B_DOF, 1.0), ("phases.0.atoms.2.dof.0", -1.0))

#: What the pair is seeded at, and therefore what each site's displacement must
#: read the moment both ties are declared.
SEED = 0.005


def antiphase_arm(order, pattern=None):
    """Declare the pair in ``order`` on a *fresh* refinement, optionally fitting.

    Fresh per arm on purpose: reusing one refinement would start the second arm
    wherever the first one finished, and two arms that begin at different
    points can only be compared to a solver tolerance.
    """
    ref = two_site_refinement()
    ref.add_variable("A", SEED, min=-0.2, max=0.2)
    for path, scale in order:
        ref.tie(path, "vars.A", scale=scale)
    result = None if pattern is None else ref.fit(
        pattern, plan=rx.RefinementPlan(stages=[
            rx.Stage("displacement", ["vars.*"], max_iter=40)]))
    atoms = (ref.structure if result is None else ref.fitted_structure
             ).phases[0].atoms
    return result, (atoms[1].x.value - B_X0, atoms[2].x.value - B2_X0)


def test_an_antiphase_pair_ends_symmetric_whichever_was_declared_first(pattern):
    """The regression case, because it is how the defect first showed.

    Two sites tied to one variable with opposite signs are a constraint that
    they move *together*, in antiphase. Declared in order, each target used to
    collect a different number of applications — the first one more than the
    second, since declaring the second rebuilt the table and re-applied the
    first — so the pair came back at +0.02251 and −0.01751 about their anchors.
    A constraint meant to couple two atoms had moved them differently, and the
    order it was written in was the whole reason.
    """
    # the declaration alone, where the arithmetic is exact: one application
    # each, whichever was declared first
    for order in (ANTIPHASE, ANTIPHASE[::-1]):
        _, (up, down) = antiphase_arm(order)
        assert (up, down) == pytest.approx((SEED, -SEED), abs=1e-12)

    # and through a fit, where the pair must still be one quantity
    result, (up, down) = antiphase_arm(ANTIPHASE, pattern)
    _plot(result, "dof_antiphase")
    assert up == pytest.approx(-down, abs=1e-12)

    _, reversed_pair = antiphase_arm(ANTIPHASE[::-1], pattern)
    assert reversed_pair == pytest.approx((up, down), abs=1e-12)


def test_replaying_a_node_rebases_the_anchor_the_same_way(ref, pattern):
    """The sibling: ``replay`` is the second place a table meets a user tie.

    It builds a table from the node's own structure, re-declares the recorded
    variables and ties on it, and is otherwise ``_prepare_table`` one rank out
    — so it inherited the defect whole. A replayed node came back with the
    displacement applied twice, which is the worst place for it: replay exists
    to say what a recorded state *was*, and nothing else in the answer says the
    model it measured is not the model on file.
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage("displacement", ["vars.*"], max_iter=40)])
    ref.add_variable("A", 0.01, min=-0.5, max=0.5)
    ref.tie(B_DOF, "vars.A")
    result = ref.fit(pattern, plan=plan)

    replayed = rx.replay(ref.history, result.node_id, pattern)
    rows = {p.path: p.value for p in replayed.parameters}
    # the node's own coordinate, not one displacement further on: 0.2084 here,
    # against the 0.2174 the un-rebased build answered with
    assert rows[B_X] == pytest.approx(
        ref.fitted_structure.phases[0].atoms[1].x.value, abs=1e-12)
    assert rows[B_X] == pytest.approx(B_X0 + rows["vars.A"], abs=1e-12)
    # and the statistics stand, which is what replay is asked for.  Marginal
    # differences are expected of it (``NodeMetrics``); a whole displacement
    # is not.
    assert replayed.statistics.rwp == pytest.approx(result.statistics.rwp,
                                                    rel=1e-6)


def test_rebasing_an_anchor_twice_does_nothing_the_second_time(ref):
    """The repair's own mirror, and it would be as silent as the defect.

    The correction subtracts the tie's contribution from a stored constant, so
    a second application walks the coordinate *down* by that contribution
    rather than leaving it alone.  Two callers rebase today and CLAUDE.md's
    coordinate-DOF bullet asks a third to; one whose table came from
    ``_working_table`` — already rebased — would have inverted the fix without
    anything saying so.  The table remembers instead, so a caller may hand the
    whole register over after declaring one more tie.
    """
    ref.add_variable("A", 0.01, min=-0.5, max=0.5)
    ref.tie(B_DOF, "vars.A")
    table = ref._working_table()
    by_path = {e.path: e for e in table.entries}
    assert by_path[B_X].value == pytest.approx(B_X0 + 0.01)

    assert table.rebase_anchored_dofs([B_DOF]) == []
    assert table.rebase_anchored_dofs([B_DOF]) == []
    assert by_path[B_X].value == pytest.approx(B_X0 + 0.01)


# ----------------------------------------------------------------------
# WP-1342 — the Le Bail force-fix asks what a column moves
# ----------------------------------------------------------------------
# The phase freeze's sibling, found by asking which other decision in
# ``refine.py`` reads a free path's name.  Against an intensity model there is
# no |F|² to fit, so a structural parameter is not refinable at all; the drop
# tested the free path's name, and a variable driving one slipped past it.
def _lebail_plan(glob: str) -> rx.RefinementPlan:
    return rx.RefinementPlan(stages=[
        rx.Stage("bkg", ["instrument.background.*"]),
        rx.Stage("displ", ["instrument.background.*", glob]),
    ])


def _lebail_fit(tied: bool):
    ref = rx.Refinement(make_lab6(),
                        rx.Instrument.debye_scherrer(wavelength=WAVELENGTH),
                        history=False)
    glob = "phases.*.atoms.*.biso"
    if tied:
        ref.add_variable("B", 0.7, min=0.0, max=25.0)
        ref.tie("phases.0.atoms.0.biso", "vars.B")
        glob = "vars.*"
    result = ref.fit(synthesize(), mode="lebail", plan=_lebail_plan(glob),
                     telemetry=False)
    return ref, result


def test_a_variable_driving_a_structural_path_is_force_fixed_in_lebail():
    """The arm that failed: ``vars.B`` entered θ where its dependent could not.

    Le Bail extracts the intensities, so an atom's ``biso`` changes nothing in
    the calculated pattern — the column is dead, and before this it came back
    with a value and an esd that read as measurements.
    """
    _, tied = _lebail_fit(tied=True)
    _, plain = _lebail_fit(tied=False)

    freed = {p for s in tied.stages for p in s.freed}
    assert "vars.B" not in freed
    assert freed == {p for s in plain.stages for p in s.freed}
    # and the dead column is gone from the answer, not merely unreported
    assert "vars.B" not in {p.path for p in tied.parameters}


def test_the_force_fixed_column_costs_the_fit_nothing():
    """Bit-identical to the untied fit, which is what "dead column" means."""
    _, tied = _lebail_fit(tied=True)
    _, plain = _lebail_fit(tied=False)
    assert tied.statistics.rwp == plain.statistics.rwp


def test_the_row_and_the_drop_agree_about_a_force_fixed_column():
    """One test projected twice, never two opinions (WP-1076).

    ``parameters()`` reports ``mode_fixed`` and ``_run_stage`` drops the freed
    path; a row calling a column refinable that the next stage silently fixes
    is the disagreement that rule exists to prevent.
    """
    ref, _ = _lebail_fit(tied=True)
    rows = {r.path: r for r in ref.parameters(mode="lebail")}
    assert rows["vars.B"].mode_fixed
    assert not rows["vars.B"].refinable
    # and in rietveld the same variable is an ordinary refinable parameter
    assert not {r.path: r for r in ref.parameters(mode="rietveld")}[
        "vars.B"].mode_fixed


def test_a_column_driving_one_fixed_and_one_live_path_stays_free():
    """All, never any — the flatness argument again.

    A variable driving an atom's ``biso`` *and* the zero shift has gradient
    through the zero shift, so fixing it would freeze a parameter Le Bail
    refines perfectly well.
    """
    ref = rx.Refinement(make_lab6(),
                        rx.Instrument.debye_scherrer(wavelength=WAVELENGTH),
                        history=False)
    ref.add_variable("M", 0.01, min=-1.0, max=1.0)
    ref.tie("phases.0.atoms.0.biso", "vars.M", scale=10.0, offset=0.5)
    ref.tie("instrument.zero_shift", "vars.M")

    result = ref.fit(synthesize(), mode="lebail",
                     plan=_lebail_plan("vars.*"), telemetry=False)
    assert "vars.M" in {p for s in result.stages for p in s.freed}
    assert "vars.M" in {p.path for p in result.parameters}
