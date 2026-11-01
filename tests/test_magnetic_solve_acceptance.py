"""`solve_magnetic` on real data: Cr₂WO₆ at 4 K and 150 K, LaMnO₃ at 50 K
(WP-1418, M-9).

The GSAS-II Magnetic-II tutorial patterns (HFIR HB-2A, λ 2.4067 Å, P4₂/mnm;
provenance in ``tests/data/README.md``), refined from the ideal trirutile start
by the session fixture ``conftest.cr2wo6_nuclear`` that WP-1326's and WP-1327's
acceptance suites already share, so the nuclear models here are exactly theirs.

Two arms, one per temperature, and each is the other's control:

* **4 K**: intensity sits on reciprocal-lattice points the nuclear structure
  factor forbids, so the k step takes the k = 0 route without consulting the
  candidate-k ranking, and 58.395, the group the tutorial refines and
  ``test_acceptance_magnetic.py`` states by hand, is ranked first with its
  class's powder-inseparable members named.
* **150 K**: above the ordering temperature there is nothing on a forbidden
  point, a handful of unexplained peaks match a zone-boundary k at about
  chance, and no class refined there improves on the nuclear model, so the
  answer is that there is nothing to solve rather than a winner.

LaMnO₃ at 50 K is the GSAS-II Magnetic-I tutorial pattern (NIST BT-1, λ
1.5403 Å, P n m a; provenance in ``tests/data/README.md``), fitted by the
session fixture ``conftest.lamno3_nuclear`` that WP-1327's LaMnO₃ acceptance
seeds its moment fits from.  It is the case where a winner *is* named: every
line indexes on the nuclear cell, and the four Γ classes of P n m a are four
models the powder separates.

obs/calc/diff PNGs of the 4 K winner and of the LaMnO₃ winner go to
``tests/output/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.strategy.magnetic import SOLVE_TIE_DELTA_BIC
from tests.test_acceptance_magnetic_lamno3 import PN_MA, PNMA, SPIN_ONLY_MN3

# Each test carries its own fixture's group: xdist joins every xdist_group
# mark an item has into one name, so a module-level mark beside a test's own
# would put that test in neither group.
pytestmark = pytest.mark.slow
CR2WO6 = pytest.mark.xdist_group("magnetic-cr2wo6")
LAMNO3 = pytest.mark.xdist_group("magnetic-lamno3")

OUT = Path(__file__).parent / "output"


@pytest.fixture(scope="module")
def solved_4k(cr2wo6_nuclear):
    return rx.solve_magnetic(cr2wo6_nuclear["ref4"], cr2wo6_nuclear["d4"],
                             sites=["Cr1"], ion="Cr3+")


@pytest.fixture(scope="module")
def solved_150k(cr2wo6_nuclear):
    return rx.solve_magnetic(cr2wo6_nuclear["ref150"], cr2wo6_nuclear["d150"],
                             sites=["Cr1"], ion="Cr3+")


@pytest.fixture(scope="module")
def solved_lamno3(lamno3_nuclear):
    return rx.solve_magnetic(lamno3_nuclear["ref"], lamno3_nuclear["data"],
                             sites=["Mn2"], ion="Mn3+")


@CR2WO6
def test_the_4k_pattern_takes_the_k_zero_route_and_ranks_58_395_first(solved_4k):
    s = solved_4k
    assert s.k_route == "forbidden lattice points", s.k_reason
    assert tuple(str(c) for c in s.k) == ("0", "0", "0")
    assert s.n_on_forbidden_lattice_points > 0
    assert s.verdict == "solved", s.reason
    assert s.best.bns_number == "58.395"
    assert s.best.supported
    assert s.margin is not None and s.margin > s.tie_width
    # the class names what the powder cannot separate from the published group
    members = {m.split()[0] for m in s.best.members}
    assert {"58.395", "65.483", "10.44"} <= members
    # a moment of the size the tutorial reports, measured well clear of zero
    m = s.best.moments[0]
    assert 1.7 < m.magnitude < 2.4 and m.esd < 0.2

    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(s.best._result, path=str(OUT / "magnetic_solve_cr2wo6_4K.png"))


@CR2WO6
def test_the_150k_pattern_has_nothing_to_solve(solved_150k):
    """No class wins, none improves on the nuclear model, and the verdict says so.

    The few unexplained peaks match k = (0, ½, ½) at about chance, and two
    classes refine there, both converged against a converged nuclear
    reference.  Measured on ``0ba8df81`` (macOS arm64, numpy 2.5.4 with
    Accelerate, three runs bit-identical) and on ``c3d03673`` (Linux x86-64,
    after #918 and #923):

    * class 1 at ΔBIC −45.2, every modulus at zero (2e-4 and 8e-7 μ_B, esds
      685 and 3.5e4 μ_B on macOS, 873 and 2.5e4 on Linux).  That is intended
      since WP-1938: intensity goes as m², so a modulus at zero has no gradient
      to leave by.  No pair is folded.
    * class 3 at ΔBIC −40.8, moduli 0.142 ± 6.4 and 0.498 ± 1.7 μ_B, whose two
      child sites fold into one ``MOMENT_PAIR_DEGENERATE`` pair: quadrature sum
      0.5183 ± 0.2501 μ_B (2.07σ) on macOS, 0.518 ± 0.250 on Linux.

    **What is asserted, and what is not (#820, WP-1418, option (a)).**  The
    verdict, ΔBIC ≤ 0 for every refined class (both sit 40-45 below zero), the
    nuclear reference's convergence, the caveat on any trial stopped short, and
    that class 3 converges and carries the pair, which both platforms show.
    The pair is held to **bands, not to the gate**: sum 0.3-0.8 μ_B, esd
    0.1-0.5 μ_B.  Each edge sits ≥ 0.1 μ_B from every value measured here and
    from the lead pair before #918 and #923 (0.606 ± 0.202, Linux and macOS
    alike), because the pair has already moved 0.09 μ_B across solver changes
    on this one pattern; the 0.5-0.7 sum band WP-1418 first named sits 0.018
    from today's 0.518.  The bands say what the pattern supports at 150 K: a
    sub-μ_B sum, far below the 1.7-2.4 μ_B the 4 K arm measures and far above
    the zero class 1 collapses to, with an esd of a few tenths of a μ_B, unlike
    the flat directions (esds ≥ 1.7 μ_B) on either side of it.

    Not asserted: whether any moment or pair clears ``MOMENT_SUPPORT_SIGMA``.
    The verdict does not depend on it, since ``_eligible_trials`` needs
    ΔBIC > 0, and the ratio has crossed sides with the solver: 2.9994σ on Linux
    and 2.9917σ on macOS before WP-1938, no pair at all on ``edad5b5a``, 2.07σ
    now.  An assertion that close to a threshold, or on a count that ρ = 0.95
    decides, senses the solver and not the data (``tests/CLAUDE.md`` § Budgets
    in tests).  The gate's own logic is pinned in ``test_magnetic_solve.py``
    on constructed pairs well clear of it either side, and the rule behind the
    pair esd (one covariance for ρ and both σ's) there too.
    """
    s = solved_150k
    assert s.n_on_forbidden_lattice_points == 0
    assert s.verdict == "nothing to solve", s.reason
    assert s.best is None and s.margin is None
    refined = [t for t in s.trials if t.status == "refined"]
    assert refined and all(t.delta_bic <= 0.0 for t in refined)
    # the ΔBIC is measured against a converged nuclear reference
    assert all(t.reference_status == "converged" for t in refined), [
        (t.class_index, t.reference_status) for t in refined]
    # a trial stopped short is listed with its caveat and left out of the ranking
    for t in refined:
        if t.fit_status != "converged":
            assert any(c.startswith(f"class {t.class_index}: the trial fit stopped")
                       and "not ranked" in c for c in s.caveats), (t.class_index,
                                                                    s.caveats)
    # class 3 converges and folds its pair; the pair sits inside the bands
    c3 = next(t for t in refined if t.class_index == 3)
    assert c3.fit_status == "converged", c3.fit_status
    c3_pair = [r for r in c3.moments if r.paired_with]
    assert c3_pair, [(r.label, r.magnitude, r.esd) for r in c3.moments]
    for r in c3_pair:
        assert 0.3 < r.paired_magnitude < 0.8, (r.label, r.paired_magnitude)
        assert 0.1 < r.paired_magnitude_esd < 0.5, (r.label,
                                                    r.paired_magnitude_esd)
    # each MOMENT_PAIR_DEGENERATE that is raised names its class, and that
    # class's rows carry the pair (#742): the pair's ``where`` is two paths
    # every class shares (moved here from test_pair_diagnostic_class in
    # WP-1930).  The check holds for every pair raised; which classes other
    # than 3 fold one is the solver's, so no count is asserted (#829).
    # A class index is unique only within one k.  The pairs span every k
    # tried and ``s.trials`` holds the chosen k's classes, so a pair is keyed
    # by its whole label and looked up only when it is the chosen k's (under
    # the LM driver a second k reaches a pair, WP-1938).
    pairs = [d for d in s.diagnostics if d.code == "MOMENT_PAIR_DEGENERATE"]
    chosen = ("" if s.k is None or all(c == "0" for c in s.k)
              else " (k = (" + ", ".join(s.k) + "))")
    labels, classes = set(), set()
    for d in pairs:
        assert d.message.startswith("class "), d.message
        label = d.message.split(":")[0]
        labels.add(label)
        index = int(label.split()[1])
        if label != f"class {index}{chosen}":
            continue
        trial = next(t for t in s.trials if t.class_index == index)
        assert any(r.paired_with for r in trial.moments), (index, d.message)
        classes.add(index)
    assert len(labels) == len(pairs)
    unpaired = {t.class_index for t in s.trials
                if not any(r.paired_with for r in t.moments)}
    assert not classes & unpaired


@LAMNO3
def test_lamno3_at_50k_ranks_a_type_first_of_four(solved_lamno3):
    """Pn′ma′ (62.448, A-type) is named the winner, far outside the tie.

    Measured on ``05ac4bac`` (macOS arm64): k = 0 by the forbidden-point
    route, four singleton classes all converged against a converged nuclear
    reference, ranked 62.448 (ΔBIC +423.9, 3.60 ± 0.045 μ_B), 62.441 (+260.0),
    62.447 (+47.4), 62.446 (−17.0), with ΔBIC charged at the reference's
    N/f² = 287 observations.  The lead over 62.441 is 163.9, 27 tie widths.

    **What is asserted.**  The ranks and a lead floor, never the ΔBIC digits,
    which move with the solver and the observation count (the lead was 1704.2
    while the count was the raw 2984 channels).  The floor is ten tie widths,
    the existing ``SOLVE_TIE_DELTA_BIC``, and today's lead is 2.7 times it,
    and the next gap down (62.441 over 62.447, 212.5) is wider still.  The
    second place is the tutorial's rejected group, as
    ``test_acceptance_magnetic_lamno3`` finds by hand.  The moment is held to
    that file's band, not to a digit.

    **The negative control** is 62.446, in the same call: its symmetry leaves
    the Mn moment nothing the pattern shows, so the modulus goes to zero with
    an esd in the thousands, Rwp stays at the nuclear value, and ΔBIC is
    the moment's parameter penalty alone.
    """
    s = solved_lamno3
    assert s.k_route == "forbidden lattice points", s.k_reason
    assert tuple(str(c) for c in s.k) == ("0", "0", "0")
    assert s.verdict == "solved", s.reason
    assert all(t.status == "refined" and t.fit_status == "converged"
               and t.reference_status == "converged" for t in s.trials), [
        (t.bns_number, t.status, t.fit_status, t.reference_status)
        for t in s.trials]
    # four classes, and the powder separates every one: each lists only itself
    assert len(s.trials) == 4
    assert all(len(t.members) == 1 and t.members[0].split()[0] == t.bns_number
               for t in s.trials), [t.members for t in s.trials]
    # A-type first, the tutorial's rival second, the control last
    assert [t.bns_number for t in s.trials] == [PN_MA, PNMA, "62.447", "62.446"]
    assert s.best.bns_number == PN_MA and s.best.supported
    assert s.tied == (0,)
    assert s.tie_width == SOLVE_TIE_DELTA_BIC
    assert s.margin is not None and s.margin > 10.0 * s.tie_width, (
        s.margin, s.tie_width)
    (m,) = s.best.moments
    assert m.supported and 3.3 <= m.magnitude < SPIN_ONLY_MN3 - 3.0 * m.esd, (
        m.magnitude, m.esd)
    # the negative control: no supported moment, no gain over the nuclear fit
    control = s.trials[-1]
    assert not control.supported, control.moments
    assert control.delta_bic <= 0.0, control.delta_bic
    assert abs(control.rwp - s.nuclear_rwp) < 1e-3 * s.nuclear_rwp, (
        control.rwp, s.nuclear_rwp)

    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(s.best._result, path=str(OUT / "magnetic_solve_lamno3_50K.png"))
