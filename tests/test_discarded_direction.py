"""WP-1535 — a direction the covariance discards must not read as measured.

``pinv`` drops an eigenvalue under ``PINV_RCOND × λmax`` and the direction comes
back at zero variance, so a combination of columns the data cannot move reports
the variance of what it *could* move.  A pair of such columns is already a
``FLAT_DIRECTION``; a combination of three has no pairwise ρ to show for it.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Refinement
from rietx.multi import MultiHistogramRefinement
from rietx.optimize.statistics import discarded_directions
from rietx.refine import _REVISABLE_CODES, _guard_diagnostics
from rietx.strategy.staged import (
    GuardFinding,
    GuardReport,
    RefinementPlan,
    Stage,
    check_discarded_directions,
)
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("discarded-direction")


def _jac(n=400, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, 5))


def test_independent_columns_discard_nothing():
    n, touched = discarded_directions(_jac())
    assert n == 0 and len(touched) == 0


def test_a_sum_of_two_columns_is_a_combination_no_pair_shows():
    """c = a + b exactly: pairwise |ρ| is 0.71, the direction is not measured."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    jj = j.T @ j
    rho = jj / np.sqrt(np.outer(np.diag(jj), np.diag(jj)))
    assert np.abs(rho[np.triu_indices(5, 1)]).max() < 0.9  # no FLAT_DIRECTION
    n, touched = discarded_directions(j)
    assert n == 1
    assert list(touched) == [0, 1, 4]


def test_a_column_the_direction_barely_loads_on_is_not_touched():
    """The bar is the reported variance: a 1e-9 loading adds ~1e-18/cut, far
    under what the kept directions say, so column 3 is not named."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1] + 1e-9 * j[:, 3]
    n, touched = discarded_directions(j)
    assert n == 1
    assert list(touched) == [0, 1, 4]


def test_the_touched_set_does_not_depend_on_a_columns_units():
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    k = j * np.array([1.0, 1e6, 1.0, 1e-4, 1.0])
    assert list(discarded_directions(k)[1]) == [0, 1, 4]


def test_a_dead_column_is_not_this_findings_business():
    j = _jac()
    j[:, 2] = 0.0
    assert discarded_directions(j)[0] == 0


def test_a_pair_flat_direction_already_reported_adds_no_row():
    j = _jac()
    j[:, 4] = j[:, 0]
    free = [f"p{i}" for i in range(5)]
    flat = [GuardFinding.flat_direction("p0", "p4", 1.0)]
    assert check_discarded_directions(j, free, flat) == []
    (row,) = check_discarded_directions(j, free, [])
    assert row.code == "COVARIANCE_DIRECTION_DISCARDED"
    assert set(row.paths) == {"p0", "p4"}


def test_the_row_names_its_paths_and_the_diagnostic_carries_them():
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    free = [f"phases.0.q{i}" for i in range(5)]
    findings = check_discarded_directions(j, free, [])
    assert [f.paths for f in findings] == [("phases.0.q0", "phases.0.q1",
                                            "phases.0.q4")]
    diags = _guard_diagnostics(GuardReport(discarded_directions=findings))
    (d,) = [d for d in diags if d.code == "COVARIANCE_DIRECTION_DISCARDED"]
    assert d.where == ["phases.0.q0", "phases.0.q1", "phases.0.q4"]
    assert d.level == "warning"


def test_the_code_is_retaken_on_the_answer_stage_not_accumulated():
    """An earlier stage's cut is not the matrix the result's esds came from, and
    an unkeyed code is appended once per stage."""
    assert "COVARIANCE_DIRECTION_DISCARDED" in _REVISABLE_CODES


# ------------------------------------------------------------ WP-2219 -----
# A parameter a discarded direction touches reports no esd, in every runner.

def _three_way_zero(mode: str, *, split: bool = True):
    """``zero_shift = za + zb + zc``, all three free: two exact directions, and
    pairwise |ρ| = 0.5, so no ``FLAT_DIRECTION`` covers them.  ``split=False``
    frees the zero shift itself instead, the fit on the combination alone."""
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    if split:
        for name in ("za", "zb", "zc"):
            ref.add_variable(name, 0.0, vary=True)
        ref.tie("instrument.zero_shift",
                {"vars.za": 1.0, "vars.zb": 1.0, "vars.zc": 1.0})
    plan = RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*",
                                         "vars.*" if split else "instrument.zero_shift"]),
        Stage(name="cell", turn_on=["phases.*.cell.*", "instrument.profile.w"]),
    ])
    return ref.fit(synthesize(), plan=plan, mode=mode)


@pytest.mark.parametrize("mode", ["rietveld", "pawley"])
def test_a_combination_the_data_cannot_see_has_no_esd(mode):
    """The three variables report no esd; the cell beside them keeps its own.
    A Pawley solve's intensity block is in the matrix the guard reads, so its
    finding is named too."""
    result = _three_way_zero(mode)
    rows = {p.path: p for p in result.parameters}
    for path in ("vars.za", "vars.zb", "vars.zc"):
        assert rows[path].stderr is None, path
    assert rows["phases.0.cell.a"].stderr > 0.0
    (d,) = [d for d in result.diagnostics if d.code == "COVARIANCE_DIRECTION_DISCARDED"]
    assert set(d.where) == {"vars.za", "vars.zb", "vars.zc"}
    assert "no esd" in d.message


@pytest.mark.parametrize("mode", ["rietveld", "pawley"])
def test_the_sum_the_data_determine_keeps_its_esd(mode):
    """WP-2230: ``zero_shift = za + zb + zc`` is estimable although no term
    is (Searle 1971, p. 169), so the tie reports the sum's esd, and it is the
    esd a fit freeing the zero shift alone gives (measured 1.0002×, both modes,
    macOS arm64; the acceptance bar is 10 %)."""
    split = {p.path: p for p in _three_way_zero(mode).parameters}
    alone = {p.path: p for p in _three_way_zero(mode, split=False).parameters}
    esd = split["instrument.zero_shift"].stderr
    assert esd is not None
    assert esd == pytest.approx(alone["instrument.zero_shift"].stderr, rel=0.1)
    assert split["instrument.zero_shift"].value == pytest.approx(
        alone["instrument.zero_shift"].value, abs=esd)


def test_the_estimability_test_is_the_touched_test_on_a_unit_vector():
    """For c = eᵢ the function test and the column test are one test, so no
    column the solve marked comes back, and a sum of the degenerate columns
    is estimable where one of them is not."""
    from rietx.optimize.least_squares import _guarded_covariance
    from rietx.optimize.statistics import estimable

    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    r = np.random.default_rng(1).standard_normal(400)
    stderr, corr, _, _, (_, touched), sub = _guarded_covariance(j, r, 5, 400)
    assert list(touched) == [0, 1, 4]
    assert np.isinf(stderr[touched]).all() and np.isfinite(sub.stderr).all()
    cov = corr * np.outer(sub.stderr, sub.stderr)
    assert list(np.flatnonzero(~estimable(np.eye(5), cov, sub.lost))) == [0, 1, 4]
    # J·(1, 1, 0, 0, −1) = 0: that direction is not estimable, and a
    # function orthogonal to it is, a touched column among its terms or not
    combos = np.array([[1.0, 1.0, 0.0, 0.0, -1.0],
                       [1.0, 0.0, 0.0, 0.0, 1.0],
                       [1.0, -1.0, 0.0, 2.0, 0.0],
                       [1.0, 1.0, 0.0, 0.0, 1.0]])
    assert list(estimable(combos, cov, sub.lost)) == [False, True, True, False]


def test_the_basis_does_not_depend_on_a_columns_units():
    """‖Bᵀc‖² is a variance, so a column rescaled by k scales its row of B by
    1/k and leaves every function's lost variance where it was."""
    j = _jac()
    j[:, 4] = j[:, 0] + j[:, 1]
    k = np.array([1.0, 1e6, 1.0, 1e-4, 1.0])
    c = np.array([1.0, 1.0, 0.3, 0.0, -1.0])
    _, _, b = discarded_directions(j, basis=True)
    _, _, bk = discarded_directions(j * k, basis=True)
    # θ' = θ/k, so the same function has the gradient c·k in the new units
    assert np.linalg.norm(c @ b) == pytest.approx(np.linalg.norm((c * k) @ bk),
                                                  rel=1e-6)


def test_a_joint_fits_basis_is_the_dense_one():
    """The blocked Schur form discards the dense subspace, so the same
    function loses the same variance."""
    from rietx.optimize.blocked import BlockJacobian

    rng = np.random.default_rng(3)
    a, b = rng.standard_normal((300, 3)), rng.standard_normal((300, 3))
    a[:, 2] = a[:, 0] + a[:, 1]
    bj = BlockJacobian([a, b], [np.array([0, 1, 2]), np.array([0, 3, 4])],
                       [300, 300], [0, 0], 5)
    n_b, t_b, basis_b = discarded_directions(bj, basis=True)
    n_d, t_d, basis_d = discarded_directions(bj.toarray(), basis=True)
    assert (n_b, list(t_b)) == (n_d, list(t_d))
    assert np.allclose(basis_b @ basis_b.T, basis_d @ basis_d.T, atol=1e-6 * np.abs(
        basis_d @ basis_d.T).max())


def test_a_cell_tied_to_a_sum_keeps_its_volume_and_bonds():
    """WP-2230 in geometry: ``a = ca + cb + cc`` on cubic LaB6 leaves every
    term without an esd and the cell, its volume and the B–B bond with one,
    the propagated esds a fit on ``a`` alone gives; the diagonal-only
    reading, which would sum the terms' unmeasured variances, is absent."""
    def fit(split):
        structure, ins = perturbed_models()
        ref = Refinement(structure, ins)
        a0 = structure.phases[0].cell.a.value
        if split:
            for name in ("ca", "cb", "cc"):
                ref.add_variable(name, a0 / 3, vary=True)
            ref.tie("phases.0.cell.a", {"vars.ca": 1.0, "vars.cb": 1.0, "vars.cc": 1.0})
        return ref.fit(synthesize(), plan=RefinementPlan(stages=[
            Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
            Stage(name="cell", turn_on=["vars.*" if split else "phases.*.cell.*",
                                        "phases.*.atoms.*.dof.*"])]))

    split, alone = fit(True), fit(False)
    rows = {p.path: p for p in split.parameters}
    for path in ("vars.ca", "vars.cb", "vars.cc"):
        assert rows[path].stderr is None, path
    assert rows["phases.0.cell.a"].stderr == pytest.approx(
        alone.parameter("phases.0.cell.a").stderr, rel=0.1)
    (v_split,), (v_alone,) = split.cell_volumes, alone.cell_volumes
    assert v_split.stderr == pytest.approx(v_alone.stderr, rel=0.1)
    assert v_split.stderr_diagonal is None and v_alone.stderr_diagonal is not None
    bonds_split = [b for b in split.geometry.bonds if b.stderr is not None]
    bonds_alone = [b for b in alone.geometry.bonds if b.stderr is not None]
    assert bonds_split and len(bonds_split) == len(bonds_alone)
    for bs, ba in zip(bonds_split, bonds_alone, strict=True):
        assert bs.stderr == pytest.approx(ba.stderr, rel=0.1)
        assert bs.stderr_diagonal is None


def test_a_refined_value_with_no_esd_writes_an_unknown_su(tmp_path):
    """The CIF states the value with ``?`` in its su item, never a bare value
    a reader would take as fixed, and the file reads back to the same value."""
    import gemmi

    import rietx as rx

    structure, ins = perturbed_models()
    # a site at zero occupancy: its B moves nothing, so the three terms tied
    # onto it are gradient-free columns.  A tie onto a site the data see is a
    # sum they determine (WP-2230), no longer a value without an esd.
    ghost = structure.phases[0].atoms[0].model_copy(deep=True)
    ghost.label = "Gh"
    ghost.occ.value = 0.0
    structure.phases[0].atoms.append(ghost)
    ref = Refinement(structure, ins)
    for name in ("ba", "bb", "bc"):
        ref.add_variable(name, 0.15, vary=True)
    ref.tie("phases.0.atoms.2.biso", {"vars.ba": 1.0, "vars.bb": 1.0, "vars.bc": 1.0})
    result = ref.fit(synthesize(), plan=RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*", "vars.*"])]))
    rows = {p.path: p for p in result.parameters}
    assert rows["phases.0.atoms.2.biso"].stderr is None
    assert rows["phases.0.cell.a"].stderr > 0.0
    ref.write_cif(tmp_path / "r.cif")
    block = gemmi.cif.read(str(tmp_path / "r.cif"))[0]
    labels = list(block.find_values("_atom_site_label"))
    su = dict(zip(labels, block.find_values("_atom_site_U_iso_or_equiv_su"), strict=True))
    assert su["Gh"] == "?"
    # the other sites' B was not refined: inapplicable, not unknown
    assert su[structure.phases[0].atoms[1].label] == "."
    # nothing else in the file lost its su
    assert block.find_value("_cell_length_a_su") is None
    back = rx.Structure.from_cif(str(tmp_path / "r.cif")).phases[0].atoms[2]
    assert back.biso.value == pytest.approx(ref.structure.phases[0].atoms[2].biso.value,
                                            rel=1e-12)


def test_a_joint_fit_gives_an_exact_pair_no_esd():
    """Two identical phases: each pattern's two scales are one quantity."""
    structure, ins = perturbed_models()
    twin = structure.phases[0].model_copy(deep=True)
    twin.name = "LaB6 twin"
    structure.phases.append(twin)
    data = synthesize()
    mr = MultiHistogramRefinement(structure, [ins, ins.model_copy(deep=True)])
    result = mr.fit([data, data], plan=RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"])]))
    rows = {p.path: p for p in result.parameters}
    for h in (0, 1):
        for ip in (0, 1):
            assert rows[f"hist.{h}.phases.{ip}.scale"].stderr is None
        assert rows[f"hist.{h}.instrument.background.c0"].stderr > 0.0


def test_an_overlap_split_with_no_esd_says_so_rather_than_inf_percent():
    """A Pawley intensity on a discarded direction carries ``inf``; the
    overlap report states it has no esd, never "reaches inf%"."""
    from types import SimpleNamespace

    from rietx.refine import _pawley_unresolved_diagnostics

    pb = SimpleNamespace(stderr=np.array([1.0, np.inf, 2.0]), groups=[(0, 1)],
                         phase_slices=[(0, 3)])
    hklm = np.array([[1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 0]])
    model = SimpleNamespace(
        pawley=pb, pawley_x0=lambda: np.array([10.0, 20.0, 30.0]),
        phases=[SimpleNamespace(reflections=SimpleNamespace(hklm=hklm))])
    structure = SimpleNamespace(phases=[SimpleNamespace(name="P")])
    (d,) = _pawley_unresolved_diagnostics(model, structure)
    assert "inf" not in d.message
    assert d.message.endswith("an individual value has no esd.")


_TRIPLE = ["instrument.profile.w", "phases.*.gauss_size", "phases.*.gauss_strain"]
_TRIPLE_PATHS = ("instrument.profile.w", "phases.0.gauss_size", "phases.0.gauss_strain")


def _triple_plan() -> RefinementPlan:
    return RefinementPlan(stages=[
        Stage(name="scale+bkg", turn_on=["phases.*.scale", "instrument.background.*"]),
        Stage(name="cell", turn_on=["phases.*.cell.*", "instrument.zero_shift"]),
        Stage(name="widths", turn_on=_TRIPLE, seed=1e-4),
    ])


@pytest.mark.parametrize("w_start", [5e-4, 1.5e-4])
def test_the_lab6_width_triple_has_no_short_esd_from_either_start(w_start):
    """WP-2028's case: synthetic LaB6 with W, ``gauss_size`` and
    ``gauss_strain`` free.  (δW, δsize, δstrain) = (1, −1, 1) changes no width
    at any angle; two starts landed 140 esd apart in W, each quoting ± 6.3e-7.
    None of the three now quotes a short esd.  The direction's eigenvalue sits
    at rounding level, and so does the cut, so rounding decides whether it is
    discarded (WP-2241).  Measured on an arm64 Mac under 1e-14 nudges to the
    start W: 16 of 20 starts gave no esd, and four gave 3.5-4.1 on a W of
    2.5e-4.  Windows read the second from this start on 2026-11-22."""
    structure, ins = perturbed_models()
    ins.profile.w.value = w_start
    result = Refinement(structure, ins).fit(synthesize(), plan=_triple_plan())
    rows = {p.path: p for p in result.parameters}
    for path in _TRIPLE_PATHS:
        row = rows[path]
        assert row.stderr is None or row.stderr > 1e3 * abs(row.value), (path, row)
    assert rows["phases.0.cell.a"].stderr > 0.0
    assert not result.stages[2].width_twins_held


def test_the_lab6_width_triple_has_no_short_esd_in_a_joint_fit():
    """Three patterns at one wavelength, W shared and each pattern's own
    Gaussian widths: every pattern's triple is the same flat direction.  Its
    eigenvalue lands on either side of the cut as rounding falls, so each
    parameter has no esd or one thousands of times its value, never a short
    one (measured 2026-11-20: W 2.5e-4 ± 1.56)."""
    from rietx.params.multi import SharingMap

    structure, ins = perturbed_models()
    data = [synthesize(noise_seed=s) for s in (7, 8, 9)]
    mr = MultiHistogramRefinement(
        structure, [ins.model_copy(deep=True) for _ in data],
        sharing=SharingMap(shared=["instrument.profile.w"],
                           per_histogram=["phases.*.gauss_*"]))
    result = mr.fit(data, plan=_triple_plan())
    rows = {p.path: p for p in result.parameters}
    paths = ["instrument.profile.w",
             *(f"hist.{h}.phases.0.gauss_{t}" for h in range(3) for t in ("size", "strain"))]
    for path in paths:
        row = rows[path]
        assert row.stderr is None or row.stderr > 1e3 * abs(row.value), (path, row)
