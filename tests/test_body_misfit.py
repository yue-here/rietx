"""The rigid-body misfit check, ``RIGID_BODY_MISFIT`` (a follow-up to WP-1805).

Positive arm: a pattern made with WP-1803's C₆Br body, fitted with the same
body carrying its C–Br bond 0.3 Å too long, must fire and must name that bond
first.  Negative arm: the right body must not fire.  The statistics are the
package's own model-comparison functions, pinned rather than re-derived.
"""

from __future__ import annotations

import numpy as np
import pytest

import tests.test_rigid_body as trb
from rietx import Refinement
from rietx.optimize.statistics import _chi2_absolute
from rietx.report.body_misfit import _element, rigid_body_misfit
from rietx.report.layer2 import delta_bic
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("body-misfit")


def _fitted(stretch: float):
    """The truth pattern, fitted with a body whose C–Br is ``stretch`` Å long."""
    pattern = trb.synthesize(trb.body_structure(trb.Q_TRUE))
    orig = trb.c6br

    def stretched():
        p = orig()
        u = (p[6] - p[0]) / np.linalg.norm(p[6] - p[0])
        p[6] = p[6] + stretch * u
        return p

    trb.c6br = stretched
    try:
        start = trb.body_structure(trb.Q_TRUE)
    finally:
        trb.c6br = orig
    ref = Refinement(start, trb.INS, history=False)
    ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", trb.BODY_GLOBS, max_iter=200)]))
    return ref, pattern


def _png(arms, stem="body_misfit"):
    """An ``on_arm`` hook saving each arm's obs/calc/diff (tests/CLAUDE.md § Running)."""
    def hook(body, arm, result):
        arms.append((arm, result))
        trb._save_fit_png(result, f"{stem}_{body}_{arm}")
    return hook


@pytest.fixture(scope="module")
def right():
    ref, pattern = _fitted(0.0)
    arms: list = []
    out = ref.check_rigid_bodies(pattern, on_arm=_png(arms))
    return out, arms


@pytest.fixture(scope="module")
def wrong():
    ref, pattern = _fitted(0.3)
    arms: list = []
    out = ref.check_rigid_bodies(pattern, on_arm=_png(arms))
    return out, arms


def test_a_wrong_body_fires_and_names_its_bond(wrong):
    wrong, _ = wrong
    (row,) = wrong.rows
    assert row.fires
    assert row.delta_bic > 10.0 and row.p_value < 1e-3
    assert row.chi2_released < row.chi2_body
    label, template, released, dev = row.deviations[0]
    assert label == "C0–Br"
    assert template == pytest.approx(2.20, abs=1e-6)
    # the data pull it most of the way back to the true 1.90 Å
    assert released < 2.0 and dev < -5.0
    (diag,) = wrong.diagnostics
    assert diag.code == "RIGID_BODY_MISFIT" and diag.level == "warning"
    assert "C0–Br" in diag.message and diag.value == pytest.approx(row.delta_bic)
    assert len(diag.where) == 7


def test_the_right_body_does_not_fire(right):
    right, _ = right
    (row,) = right.rows
    assert not row.fires
    assert right.diagnostics == []
    # the released atoms stay within their restraint widths of the template
    assert max(abs(d[3]) for d in row.deviations) < 2.0


def test_the_statistics_are_the_packages_own(wrong):
    wrong, _ = wrong
    (row,) = wrong.rows
    assert row.delta_bic == pytest.approx(delta_bic(
        row.chi2_body, row.chi2_released, row.n_points, row.n_added,
        n_effective=row.n_effective))
    assert row.n_added == 3 * 7 - 6        # seven free atoms against a 6-DOF pose


def test_no_body_no_rows():
    from tests.test_coordinates import make_rutile, synthesize_rutile
    pattern = synthesize_rutile()
    ref = Refinement(make_rutile(), trb.INS, history=False)
    ref.fit(pattern, plan=RefinementPlan(stages=[Stage("s", ["phases.*.scale"])]))
    out = rigid_body_misfit(ref, pattern)
    assert out.rows == [] and out.diagnostics == []


def test_chi2_absolute_is_the_unreduced_sum():
    # the helper the check reads its χ² through: reduced × (N − P)
    class S:
        chi2, n_points, n_free_parameters = 2.0, 110, 10
    assert _chi2_absolute(S) == pytest.approx(200.0)


def test_both_arms_leave_their_pngs(wrong):
    _, arms = wrong
    assert [a for a, _ in arms] == ["body", "released"]
    for arm in ("body", "released"):
        assert (trb.OUT / f"body_misfit_c6br_{arm}.png").stat().st_size > 0


def test_the_species_parser_is_the_packages_one():
    assert _element("Br1-") == "Br" and _element("C") == "C"
    with pytest.raises(ValueError):
        _element("Qq")          # the regex took "Q" and let gemmi pick a placeholder


def test_an_unfitted_refinement_is_refused():
    pattern = trb.synthesize(trb.body_structure(trb.Q_TRUE))
    ref = Refinement(trb.body_structure(trb.Q_TRUE), trb.INS, history=False)
    with pytest.raises(ValueError, match="fitted"):
        ref.check_rigid_bodies(pattern)


def test_the_arms_carry_the_callers_declarations():
    """2θ limits reach both arms; a tie on the body is dropped from the released one."""
    ref, pattern = _fitted(0.0)
    n_full = len(pattern.two_theta)
    ref.tie("phases.0.rigid_bodies.0.origin.dof.1", "phases.0.rigid_bodies.0.origin.dof.0")
    ref.fit(pattern, two_theta_limits=(10.0, 40.0), plan=RefinementPlan(stages=[
        Stage("body", trb.BODY_GLOBS, max_iter=200)]))
    arms: list = []
    out = ref.check_rigid_bodies(pattern, on_arm=_png(arms, "body_misfit_limited"))
    arms = [r for _, r in arms]
    assert all(r.statistics.n_points < n_full for r in arms)
    assert all(r.statistics.n_points == arms[0].statistics.n_points for r in arms)
    (row,) = out.rows
    assert row.dropped == ["tie phases.0.rigid_bodies.0.origin.dof.1"]


def _chain_structure(stretch: float):
    """A ring with a bromoethyl-like arm: ring C0 – C6 – Br, the C0–C6 bond
    ``stretch`` Å too long.  An interior bond: both its ends have restrained
    neighbours, unlike the terminal C–Br of the C₆Br body."""
    ring = trb.c6br()[:6]
    u = ring[0] / np.linalg.norm(ring[0])
    c6 = ring[0] + (1.52 + stretch) * u
    br = c6 + 1.95 * (u * 0.5 + np.array([0.0, 0.866, 0.0]))
    pts = np.vstack([ring, c6, br])
    seed = trb.Atom(label="seed", species="C", x=trb.Parameter(value=0.0),
                    y=trb.Parameter(value=0.0), z=trb.Parameter(value=0.0))
    phase = trb.Phase(name="arm", space_group="P-1", cell=trb._cell(), atoms=[seed],
                      scale=trb.Parameter(value=1e-2, min=0.0, transform="softplus"))
    phase = trb.add_body(phase, "arm", [f"C{i}" for i in range(7)] + ["Br"],
                         ["C"] * 7 + ["Br"], pts, (0.31, 0.42, 0.27),
                         orientation=trb.Q_TRUE, biso=2.0)
    phase = trb.Phase.model_validate({**phase.model_dump(),
                                      "atoms": phase.model_dump()["atoms"][1:]})
    return trb.Structure(phases=[phase])


def test_an_interior_bond_error_fires_and_is_named():
    """The acceptance case (#775): a C–C bond 0.3 Å long, in a molecule where
    its neighbours' restraints share the error."""
    pattern = trb.synthesize(_chain_structure(0.0))
    ref = Refinement(_chain_structure(0.3), trb.INS, history=False)
    ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("body", trb.BODY_GLOBS, max_iter=200)]))
    (row,) = ref.check_rigid_bodies(pattern, on_arm=_png([], "body_misfit_chain")).rows
    assert row.fires
    assert "C0–C6" in [d[0] for d in row.deviations[:3]]
