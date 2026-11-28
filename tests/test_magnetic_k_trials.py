"""solve_magnetic carries the top-N k's into the intensity trial, not
only the first testable one, when they are within the satellite step's own
offset margin of each other -- Ba2FeSbSe5's (PRB 103, 054115; pattern not
vendored) k=(1/2,0,1/2) and k=(1/2,1/2,0) both index the same 11 peaks (worst offsets 0.100 deg and 0.181 deg) and only
the moment refinement's intensity separates them.

Two levels: a synthetic-but-real end-to-end run (a genuine tetragonal
structure, a genuine satellite arm forced to report two candidate k's
together by monkeypatching ``analyse_satellites`` -- the arm's own scoring is
not what this rung changes) proving both k's are actually refined and
reported; and direct unit tests of the new ranking/diagnostic helpers proving
``K_VECTOR_UNSEPARATED`` fires at the stated margin and not outside it.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import magnetic_supercell
from rietx.report.schemas import SatelliteCandidate, SatelliteEvidence
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase
from rietx.strategy.magnetic import (
    SOLVE_K_OFFSET_MARGIN_DEG,
    SOLVE_K_TIE_DELTA_BIC,
    SOLVE_TOP_K,
    MagneticTrial,
    MomentRow,
    _best_eligible_delta_bic,
    _score_k_trials,
    _within_k_offset_margin,
)

LAMBDA_CW = 2.4
GRID = np.arange(8.0, 130.0, 0.05)


def _cell(a, b, c):
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _atom(label, species, xyz, biso=0.4, moment=None):
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=biso), moment=moment)


def tetragonal() -> Phase:
    return Phase(
        name="tetragonal", space_group="P 4/m m m", cell=_cell(4.0, 4.0, 4.2),
        atoms=[Atom(label="Mn1", species="Mn", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.4)),
               _atom("O1", "O", (0.5, 0.5, 0.5), biso=0.6)])


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.35)


def simulate(phase, instrument, *, background=40.0, seed=20260909):
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    y = np.asarray(ref.predict(GRID)) + background
    rng = np.random.default_rng(seed)
    y = y + rng.normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


NUCLEAR_PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    rx.Stage("cell", ["phases.*.scale", "instrument.background.c*",
                      "phases.*.cell.*"])])


def nuclear_fit(phase, data, instrument):
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    ref.fit(data, plan=NUCLEAR_PLAN)
    return ref


@pytest.fixture(scope="module")
def true_k_and_data():
    """A genuine k=(0,0,1/2) magnetic tetragonal pattern and its converged
    nuclear fit -- the same shape as test_magnetic_solve.py's own fixtures.
    **Consumers carry** ``@pytest.mark.xdist_group("magnetic-k-trials-true-k")``,
    or each xdist worker rebuilds the simulation and the nuclear fit."""
    instrument = neutron()
    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    statement = magnetic_supercell(tetragonal(), truth, magnetic_species=["Mn1"],
                                   ion={"Mn1": "Mn3+"}, magnitude=3.0)
    data = simulate(statement.phase, instrument)
    ref = nuclear_fit(tetragonal(), data, instrument)
    return ref, data, truth


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-k-trials-true-k")
def test_two_k_within_margin_are_both_refined_and_reported(true_k_and_data, monkeypatch):
    """Force the satellite arm to report two candidate k's tied on matching
    (the mechanism ``k_trials`` changes), and check both get a full trial: the true
    k=(0,0,1/2) and a second, ('1/2','1/2',0), which also enumerates a real
    (if wrong) candidate set on this site -- ``solve_magnetic`` does not know
    or care which is "true"; that is exactly the point of the rung.
    """
    ref, data, truth = true_k_and_data

    fake_evidence = SatelliteEvidence(
        phase_index=0, radiation="neutron",
        n_residual_peaks=20, n_unexplained=20,
        excess_on_nuclear_lines=0, excess_on_absent_lattice_lines=0,
        generator="test_fake",
        candidates=[
            SatelliteCandidate(k=["0", "0", "1/2"], name="k1", vector="(0, 0, 1/2)",
                              n_satellites=11, matched=11, matched_fraction=1.0,
                              worst_offset_deg=0.100),
            SatelliteCandidate(k=["1/2", "1/2", "0"], name="k2",
                              vector="(1/2, 1/2, 0)", n_satellites=11,
                              matched=11, matched_fraction=1.0,
                              worst_offset_deg=0.181),
        ],
        note="fake evidence for the k_trials mechanism test")

    import rietx.report.satellites as satellites_mod
    monkeypatch.setattr(satellites_mod, "analyse_satellites",
                        lambda *a, **k: [fake_evidence])

    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+",
                                 k_trials=2)

    assert solution.k_route == "satellite ranking"
    # both k's were within the offset margin and both got their own full
    # trial -- the mechanism under test -- whatever either one's classes then
    # did with the data
    assert len(solution.k_trials) == 2, solution.k_trials
    reported_ks = {row.k for row in solution.k_trials}
    assert reported_ks == {("0", "0", "1/2"), ("1/2", "1/2", "0")}
    for row in solution.k_trials:
        assert row.matched == 11
    true_row = next(r for r in solution.k_trials if r.k == ("0", "0", "1/2"))
    assert true_row.n_refined >= 1
    assert true_row.best_delta_bic is not None
    # the true k is the one this call actually reports as the answer
    assert solution.k == ("0", "0", "1/2")
    assert solution.verdict == "solved", solution.reason
    assert solution.best.bns_number == truth.bns_number


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-k-trials-true-k")
def test_k_trials_1_keeps_the_single_k_behaviour(true_k_and_data, monkeypatch):
    """``k_trials=1`` is the escape hatch back to the old behaviour: only the
    first testable k is ever fitted, whatever the offset margin says."""
    ref, data, truth = true_k_and_data

    fake_evidence = SatelliteEvidence(
        phase_index=0, radiation="neutron",
        n_residual_peaks=20, n_unexplained=20,
        excess_on_nuclear_lines=0, excess_on_absent_lattice_lines=0,
        generator="test_fake",
        candidates=[
            SatelliteCandidate(k=["0", "0", "1/2"], name="k1", vector="(0, 0, 1/2)",
                              n_satellites=11, matched=11, matched_fraction=1.0,
                              worst_offset_deg=0.100),
            SatelliteCandidate(k=["1/2", "1/2", "0"], name="k2",
                              vector="(1/2, 1/2, 0)", n_satellites=11,
                              matched=11, matched_fraction=1.0,
                              worst_offset_deg=0.181),
        ],
        note="fake evidence for the k_trials mechanism test")

    import rietx.report.satellites as satellites_mod
    monkeypatch.setattr(satellites_mod, "analyse_satellites",
                        lambda *a, **k: [fake_evidence])

    solution = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+",
                                 k_trials=1)
    assert len(solution.k_trials) == 1
    assert solution.k_trials[0].k == ("0", "0", "1/2")
    assert not any(d.code == "K_VECTOR_UNSEPARATED" for d in solution.diagnostics)


@pytest.mark.xdist_group("magnetic-k-trials-true-k")
def test_top_k_cuts_the_reported_candidate_list_and_never_the_pick(true_k_and_data):
    """`SOLVE_TOP_K`'s named synthetic case (WP-2017 group L, ruled 2026-11-18).

    The real satellite arm (nothing monkeypatched) on this k = (0,0,1/2)
    pattern lists five candidate k's: the true one matching 11 satellites and
    four matching none, (0,1/2,0), (0,1/2,1/2), (1/2,1/2,0) and (1/2,1/2,1/2).
    `top_k` cuts that list to what the solution reports in `k_candidates`; a
    candidate that matches nothing is never walked, so the pick and its
    ranking are the same at every cut.  At the shipped 3 the reported list
    stops at (0,1/2,1/2); 2 or 4 shortens or lengthens it, and the pick does
    not move.  Not marked slow: it is the case that reaches an audited
    constant, three solves of about 1 s on macOS arm64.
    """
    ref, data, truth = true_k_and_data
    shipped = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+")
    assert [c[0] for c in shipped.k_candidates] == [
        "(0, 0, 1/2)", "(0, 1/2, 0)", "(0, 1/2, 1/2)"], shipped.k_candidates
    assert len(shipped.k_trials) == 1
    for top_k, length in ((SOLVE_TOP_K - 1, 2), (SOLVE_TOP_K + 1, 4)):
        moved = rx.solve_magnetic(ref, data, sites=["Mn1"], ion="Mn3+",
                                  top_k=top_k)
        assert len(moved.k_candidates) == length, moved.k_candidates
        assert moved.k == shipped.k == ("0", "0", "1/2")
        assert moved.best.bns_number == shipped.best.bns_number == truth.bns_number
        assert ([(t.bns_number, t.delta_bic) for t in moved.trials]
                == [(t.bns_number, t.delta_bic) for t in shipped.trials])


# ================================================== the ranking helpers, direct

def _trial(index, *, delta_bic, r_mag=0.11, free=1, bns="1.1", supported=True):
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"{bns} S{index}(a)",), site="Mn1", irrep=f"S{index}",
        direction="(a)", bns_number=bns, uni_number=None, msg_type=1,
        free_amplitudes=free, determinable_amplitudes=1, status="refined",
        rwp=0.1, gof=1.0, delta_bic=delta_bic, r_magnetic=r_mag,
        n_moment_parameters=free, n_free_parameters=free + 5,
        moments=(MomentRow(label="Mn1", ion="Mn3+", magnitude=3.0,
                           esd=0.1 if supported else 30.0,
                           crystalaxis=(3.0, 0.0, 0.0), supported=supported),))


def _cand(k, matched, worst_offset_deg):
    return SatelliteCandidate(k=[str(c) for c in k], name="k", vector=str(k),
                              matched=matched, worst_offset_deg=worst_offset_deg)


def test_within_margin_requires_equal_matched_and_close_offset():
    k1, k2 = (0, 0), (1, 1)
    score = {k1: _cand(k1, 11, 0.100), k2: _cand(k2, 11, 0.181)}
    assert _within_k_offset_margin(score, k1, k2)          # 0.081 <= 0.5
    assert _within_k_offset_margin(score, k2, k1)          # symmetric

    score_far = {k1: _cand(k1, 11, 0.0), k2: _cand(k2, 11, 0.0 + SOLVE_K_OFFSET_MARGIN_DEG + 0.01)}
    assert not _within_k_offset_margin(score_far, k1, k2)  # just outside

    score_mismatch = {k1: _cand(k1, 11, 0.1), k2: _cand(k2, 9, 0.1)}
    assert not _within_k_offset_margin(score_mismatch, k1, k2)  # matched differs

    assert not _within_k_offset_margin({}, k1, k2)         # neither scored


def test_best_eligible_delta_bic_matches_rank_eligibility():
    refined_supported = _trial(0, delta_bic=50.0, supported=True)
    refined_unsupported = _trial(1, delta_bic=999.0, supported=False)
    refused = MagneticTrial(
        class_index=2, representative="S2(a)", members=("1.1 S2(a)",),
        site="Mn1", irrep="S2", direction="(a)", bns_number="1.1",
        uni_number=None, msg_type=1, free_amplitudes=1,
        determinable_amplitudes=1, status="refused", refusal="synthetic")
    non_positive = _trial(3, delta_bic=-5.0)

    assert _best_eligible_delta_bic([refined_supported]) == 50.0
    # an unsupported moment or a non-positive ΔBIC is not eligible, however
    # large the number -- exactly _rank's own rule
    assert _best_eligible_delta_bic([refined_unsupported]) is None
    assert _best_eligible_delta_bic([non_positive]) is None
    assert _best_eligible_delta_bic([refused]) is None
    assert _best_eligible_delta_bic([]) is None
    assert _best_eligible_delta_bic(
        [refined_supported, refined_unsupported, refused]) == 50.0


def test_score_k_trials_emits_k_vector_unseparated_within_the_margin():
    k1, k2 = (0, 0), (1, 1)
    score = {k1: _cand(k1, 11, 0.100), k2: _cand(k2, 11, 0.181)}
    trials_1 = [_trial(0, delta_bic=150.0)]
    trials_2 = [_trial(0, delta_bic=150.0 - 0.5 * SOLVE_K_TIE_DELTA_BIC, bns="2.2")]

    kk, trials, rows, diagnostics, caveats = _score_k_trials(
        [(k1, trials_1), (k2, trials_2)], score, SOLVE_K_TIE_DELTA_BIC, "phase")

    assert kk == k1                      # the higher ΔBIC wins
    assert trials is trials_1
    assert len(rows) == 2
    assert {r.k for r in rows} == {("0", "0"), ("1", "1")}
    assert any(d.code == "K_VECTOR_UNSEPARATED" for d in diagnostics)
    assert any("won over" in c for c in caveats)


def test_score_k_trials_no_diagnostic_when_the_gap_is_wide():
    k1, k2 = (0, 0), (1, 1)
    score = {k1: _cand(k1, 11, 0.100), k2: _cand(k2, 11, 0.181)}
    trials_1 = [_trial(0, delta_bic=150.0)]
    trials_2 = [_trial(0, delta_bic=150.0 - 2 * SOLVE_K_TIE_DELTA_BIC, bns="2.2")]

    _kk, _trials, rows, diagnostics, caveats = _score_k_trials(
        [(k1, trials_1), (k2, trials_2)], score, SOLVE_K_TIE_DELTA_BIC, "phase")

    assert not diagnostics
    assert any("won over" in c for c in caveats)
    assert rows[0].best_delta_bic == 150.0
    assert rows[1].best_delta_bic == pytest.approx(150.0 - 2 * SOLVE_K_TIE_DELTA_BIC)


def test_score_k_trials_notes_a_k_with_no_eligible_class():
    k1, k2 = (0, 0), (1, 1)
    score = {k1: _cand(k1, 11, 0.100), k2: _cand(k2, 11, 0.181)}
    trials_1 = [_trial(0, delta_bic=150.0)]
    trials_2 = [_trial(0, delta_bic=-5.0, bns="2.2")]  # not eligible: ΔBIC <= 0

    kk, _trials, rows, diagnostics, caveats = _score_k_trials(
        [(k1, trials_1), (k2, trials_2)], score, SOLVE_K_TIE_DELTA_BIC, "phase")

    assert kk == k1
    assert not diagnostics
    assert any("only one" in c for c in caveats)
    assert rows[1].best_delta_bic is None


def _refused(index=0):
    return MagneticTrial(
        class_index=index, representative=f"S{index}(a)",
        members=(f"1.1 S{index}(a)",), site="Mn1", irrep=f"S{index}",
        direction="(a)", bns_number="1.1", uni_number=None, msg_type=1,
        free_amplitudes=1, determinable_amplitudes=None, status="refused",
        refusal="synthetic")


def test_score_k_trials_a_k_whose_every_class_refused_never_speaks_for_a_fitted_k():
    """Review of #592, item 1: neither k reached an eligible class, and the
    stable sort kept walk order, so the k that ran **no fit** supplied
    ``solution.k`` and the verdict ("nothing was tested against the data")
    while a fitted k's trials were dropped."""
    k1, k2 = (0, 0), (1, 1)
    refused_k = [_refused(0), _refused(1)]
    fitted_k = [_trial(0, delta_bic=-5.0, bns="2.2")]    # refined, not eligible

    kk, trials, rows, _d, _c = _score_k_trials(
        [(k1, refused_k), (k2, fitted_k)], {}, SOLVE_K_TIE_DELTA_BIC, "phase")

    assert kk == k2 and trials is fitted_k
    assert [r.n_refined for r in rows] == [1, 0]
    # positive arm: with the fitted k walked first the answer is the same, and
    # an eligible class still outranks the refined count
    kk, _t, _r, _d, _c = _score_k_trials(
        [(k2, fitted_k), (k1, refused_k)], {}, SOLVE_K_TIE_DELTA_BIC, "phase")
    assert kk == k2
    eligible_k = [_trial(0, delta_bic=40.0)]
    kk, _t, _r, _d, _c = _score_k_trials(
        [(k1, refused_k), (k2, eligible_k)], {}, SOLVE_K_TIE_DELTA_BIC, "phase")
    assert kk == k2


def test_a_refused_k_uses_up_no_k_trials_slot():
    """Review of #592, item 1: ``len(k_runs)`` counted a k whose every class
    refused, so with ``k_trials=2`` one refused k plus one fitted k closed the
    walk after a single k had actually been tried."""
    from rietx.strategy.magnetic import _n_k_tried

    k_runs = [((0, 0), [_refused(0)]), ((1, 1), [_trial(0, delta_bic=10.0)])]
    assert len(k_runs) == 2 and _n_k_tried(k_runs) == 1
    assert _n_k_tried([]) == 0
    assert _n_k_tried(k_runs + [((2, 2), [_trial(0, delta_bic=3.0)])]) == 2


def test_score_k_trials_single_k_run_reports_nothing_extra():
    trials_1 = [_trial(0, delta_bic=150.0)]
    kk, trials, rows, diagnostics, caveats = _score_k_trials(
        [((0, 0), trials_1)], {}, SOLVE_K_TIE_DELTA_BIC, "phase")
    assert kk == (0, 0)
    assert trials is trials_1
    assert len(rows) == 1
    assert not diagnostics
    assert not caveats
