"""What a fit on mode amplitudes reports, as quantities (WP-1419 C4a).

A child stated on its parent's modes (``displacive_statement``) reports one
``DistortionTotal`` per irrep block at fit close, and
``Refinement.distortion_block_tests`` refits with any blocks held at 0.
Everything here is a known answer, an invariance or a measured agreement, and
each check has a positive arm that a wrong implementation fails.  No test
reads a verdict, a ΔBIC against a bar, or a rate of either.

Data:

* **The shipped BT-1 LaMnO₃ 50 K pattern** (``tests/data/README.md``),
  fitted as Pm-3m plus the seven Pnma modes with the Pn′ma′ moment, on
  ``test_acceptance_magnetic_lamno3``'s protocol and then one stage freeing
  scale, background, zero, cell, profile u, v, w, x, Biso tied per parent site
  and every amplitude.
* **Synthetic children of the BT-1 nuclear fit** (that protocol's six nuclear
  stages, Pnma as the parent): the five-mode Γ block of a P2₁/c child (rietx's
  S6 at Γ) and the ten-mode zone-boundary block of a doubled P2₁/c child (S1 at
  k = (½, 0, ½)), drawn with rietx's own forward model on the BT-1 grid and
  file σ, plus white noise of that σ.  Native path: the same one stage.

**The interpretation table** (written 2026-10-30 14:08, before the first run
of the real-data, restart and scatter tests):

==============================================  ===========================================
outcome                                         reading / action
==============================================  ===========================================
T² or esd off the hand form beyond 1e-10 rel    the code computes another form; fix it
a quantity moves under the basis rotation       a basis-dependent step; fix it
A_τ outside Table 13's bar                      unit, basis or 300 K/50 K; stop and report
no restricted-below-full seed in 20             extend to 50, then stop and report
A_det off the bisection beyond its bound        exponent or bisection; stop and report
esd ratio outside [0.75, 1.33]                  esd misdescribes the scatter; stop and report
==============================================  ===========================================
"""

from __future__ import annotations

import functools
import importlib
import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
import rietx.report.distortion as RD
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.magnetic.isotropy import distortion_candidates
from rietx.crystallography.representation import distortion as D
from rietx.schemas.structure import Structure

#: the module, not the ``rietx.refine`` function the package exports under that name
refine_module = importlib.import_module("rietx.refine")

DATA = Path(__file__).parent / "data"
AMPS = "phases.0.distortion_modes.modes.*.amplitude"
BISO = "phases.0.atoms.*.biso"
#: the two synthetic children: (k, rietx's irrep label at that k)
GAMMA = (("0", "0", "0"), "S6")
ZONE = (("1/2", "0", "1/2"), "S1")
#: random streams of the synthetic arms, so no two arms share draws
STREAM = {"gamma_null": 1, "zone_null": 2, "gamma_plant": 10, "zone_plant": 20}


# --------------------------------------------------------------------------
# helpers (the verdict's tests reuse them)
# --------------------------------------------------------------------------

def _protocol():
    from tests.test_acceptance_magnetic_lamno3 import (
        _B,
        CELL,
        CONTAMINANT,
        LIMITS,
        WIDTHS,
        ZERO,
    )
    data = rx.read_pattern(DATA / "gsas2_bt1_lamno3_50K.gsas").model_copy(
        update={"excluded_regions": [CONTAMINANT]})
    return data, LIMITS, [*_B, ZERO, CELL, *WIDTHS, BISO, AMPS]


@functools.cache
def bt1_nuclear():
    """The BT-1 nuclear fit's phase and instrument, and its fitted grid and σ."""
    from tests.test_acceptance_magnetic_lamno3 import NUCLEAR_STAGES, _fit, _instrument

    data, _, _ = _protocol()
    ref, result = _fit(structure_from_cif(DATA / "gsas2_bt1_lamno3.cif"), _instrument(), data,
                       NUCLEAR_STAGES)
    return (ref.structure.phases[0], ref.instrument, np.asarray(result.two_theta),
            np.asarray(result.sigma))


@functools.cache
def child(which):
    """(the child stated at its parent unseeded, the seeded statement) for GAMMA or ZONE."""
    parent, _, _, _ = bt1_nuclear()
    k, irrep = which
    (cand,) = [c for c in distortion_candidates(parent, k)
               if c.irrep == irrep and c.child is not None]
    # a phase scale is per cell, so the child of |det P| parent cells takes 1/|det P|² of it
    det = abs(float(np.linalg.det(np.asarray(cand.transform[0], dtype=float))))
    kid = cand.child.model_copy(update={"scale": parent.scale.model_copy(
        update={"value": parent.scale.value / det ** 2})})
    return (D.displacive_statement(parent, kid, cand.transform, seed=0.0),
            D.displacive_statement(parent, kid, cand.transform))


def block_key(phase, irrep):
    (key,) = [k for k in RD.distortion_blocks(phase) if k[0] == irrep]
    return key


def predict(phase, instrument, tt):
    return np.asarray(rx.Refinement(Structure(phases=[phase]), instrument, history=False)
                      .predict(tt))


def with_amplitudes(phase, amps):
    """``phase`` with its amplitudes set to ``amps`` and its coordinates rewritten."""
    record = phase.distortion_modes.model_copy(deep=True)
    for m, a in zip(record.modes, amps, strict=True):
        m.amplitude.value = float(a)
    vectors = np.array([m.vectors for m in record.modes])
    pos = np.array(record.base) + np.tensordot(np.asarray(amps, dtype=float), vectors, axes=1)
    atoms = [a.model_copy(update={c: getattr(a, c).model_copy(update={"value": float(pos[j, i])})
                                  for i, c in enumerate("xyz")})
             for j, a in enumerate(phase.atoms)]
    return phase.model_copy(update={"atoms": atoms, "distortion_modes": record})


def amplitudes(phase) -> np.ndarray:
    return np.array([m.amplitude.value for m in phase.distortion_modes.modes])


def a_need(lam, target: float = 3.84) -> float:
    """The amplitude at which ``lam(A)`` reaches ``target``, by bisection (predict-only).

    ``lam(A)`` is Σ((y(A) − y(0))/σ)² for one mode moved by A from a base; the
    F5 measurement's definition, at 3.84 there.
    """
    lo, hi = 0.0, 0.05
    while lam(hi) < target:
        lo, hi = hi, 2.0 * hi
    while hi - lo > 1e-7 * hi:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if lam(mid) < target else (lo, mid)
    return 0.5 * (lo + hi)


def mode_lambda(phase, instrument, tt, sigma, j):
    """λ_j(A) about ``phase``'s own amplitudes, as a function of A."""
    a0 = amplitudes(phase)
    y0 = predict(phase, instrument, tt)

    def lam(amplitude):
        a = a0.copy()
        a[j] += amplitude
        return float(np.sum(((predict(with_amplitudes(phase, a), instrument, tt) - y0)
                             / sigma) ** 2))
    return lam


@functools.cache
def planted(which, c):
    """The truth with the block's easiest mode planted at c × its A_need (at the parent)."""
    truth, _ = child(which)
    _, inst, tt, sigma = bt1_nuclear()
    modes = RD.distortion_blocks(truth.phase)[block_key(truth.phase, which[1])]
    needs = {j: a_need(mode_lambda(truth.phase, inst, tt, sigma, j)) for j in modes}
    j = min(needs, key=needs.get)
    a = amplitudes(truth.phase)
    a[j] += c * needs[j]
    return with_amplitudes(truth.phase, a), j, needs[j]


def synthetic(phase, seed: int, stream: int) -> rx.PatternData:
    """``phase`` drawn on the BT-1 grid, plus white noise of the file's σ."""
    _, inst, tt, sigma = bt1_nuclear()
    y = predict(phase, inst, tt)
    rng = np.random.default_rng([stream, seed])
    return rx.PatternData(two_theta=tt.tolist(), intensity=(y + rng.normal(0.0, sigma)).tolist(),
                          sigma=sigma.tolist())


def native_fit(statement, data, *, tie: bool = True, start=None, max_iter: int = 1000,
               instrument=None, free=None):
    """The native path: one stage freeing the BT-1 set, Biso tied per parent site."""
    inst = instrument or bt1_nuclear()[1]
    free = free if free is not None else _protocol()[2]
    ref = rx.Refinement(Structure(phases=[start or statement.phase]), inst.model_copy(deep=True),
                        history=False)
    if tie:
        for path, source, coeff, _ in statement.biso_ties:
            ref.tie(path, {source: coeff})
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[rx.Stage(name="all", turn_on=free,
                                                                   max_iter=max_iter)]),
                     telemetry=False)
    return ref, result


class Capture:
    """Records every fit-close ``distortion_totals`` call: its inputs and its answer."""

    def __init__(self):
        self.calls = []

    def __call__(self, table, theta, structure, values, *, stderr_internal=None,
                 correlation=None):
        out = RD.distortion_totals(table, theta, structure, values,
                                   stderr_internal=stderr_internal, correlation=correlation)
        self.calls.append((table, np.array(theta), structure, dict(values), stderr_internal,
                           correlation, out))
        return out

    def matching(self, totals):
        """The call whose answer is ``totals``."""
        hits = [c for c in self.calls if c[-1] is not None
                and [t.a_tau for t in c[-1]] == [t.a_tau for t in totals]]
        return hits[-1]


def no_biso_negative(result):
    assert "BISO_NEGATIVE" not in {d.code for d in result.diagnostics}


# --------------------------------------------------------------------------
# the real BT-1 Pnma fit, with the moment
# --------------------------------------------------------------------------

LAMNO3_T = ([[1, 0, -1], [0, 2, 0], [1, 0, 1]], [0.5, 0.0, 0.5])
MOMENT = ["phases.0.atoms.1.moment.dof0", "phases.0.atoms.1.moment.dof1"]


def _cubic():
    from tests.test_displacive_statement import lamno3_parent
    return lamno3_parent()


def _fit_modes(phase, statement, data, limits, free):
    capture = Capture()
    ref = rx.Refinement(Structure(phases=[phase]), statement[1].model_copy(deep=True),
                        history=False)
    for path, source, coeff, _ in statement[0].biso_ties:
        ref.tie(path, {source: coeff})
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(refine_module, "_distortion_totals", capture)
        result = ref.fit(data, plan=rx.RefinementPlan(stages=[rx.Stage(
            name="all", turn_on=free + MOMENT, max_iter=1000)]), two_theta_limits=limits,
            telemetry=False)
    return ref, result, capture


@pytest.fixture(scope="module")
def bt1_modes():
    """The BT-1 pattern as Pm-3m plus the Pnma modes, Pn′ma′ moment on Mn."""
    from tests.test_acceptance_magnetic_lamno3 import (
        MAGNETIC_STAGES,
        NUCLEAR_STAGES,
        PN_MA,
        _fit,
        _instrument,
        _with_moment,
    )

    data, limits, free = _protocol()
    ref_nuc, _ = _fit(structure_from_cif(DATA / "gsas2_bt1_lamno3.cif"), _instrument(), data,
                      NUCLEAR_STAGES)
    ref_mag, _ = _fit(_with_moment(ref_nuc.structure, PN_MA),
                      ref_nuc.instrument.model_copy(deep=True), data, MAGNETIC_STAGES)
    statement = D.displacive_statement(_cubic(), ref_mag.structure.phases[0], LAMNO3_T)
    assert statement.seed == {}
    ref, result, capture = _fit_modes(statement.phase, (statement, ref_mag.instrument), data,
                                      limits, free)
    return {"statement": statement, "instrument": ref_mag.instrument, "ref": ref,
            "result": result, "capture": capture, "data": data, "limits": limits,
            "free": free}


BT1 = pytest.mark.xdist_group("distortion-totals-bt1")


@BT1
def test_t2_and_the_esd_are_the_hand_quadratic_forms(bt1_modes, monkeypatch):
    """Test 1: every block carries a DistortionTotal; T² and the esd to 1e-10 of the hand forms.

    Both hand forms read ``physical_covariance`` of the fit that returned the
    result, at f ≈ 2.26 (the Bérar–Lelann factor of this fit), so applying f²
    a second time moves every T² by 1/f² ≈ 0.2: the positive arm below
    recomputes the totals that way and must miss.
    """
    result = bt1_modes["result"]
    no_biso_negative(result)
    totals = result.distortion_totals
    phase = bt1_modes["ref"].structure.phases[0]
    assert [(t.irrep, t.k, t.isotropy_group) for t in totals] == list(
        RD.distortion_blocks(phase))
    assert len(totals) == 5
    table, theta, structure, values, stderr, corr, _ = bt1_modes["capture"].matching(totals)
    f = result.statistics.esd_inflation
    assert f > 2.0

    def hand(t):
        paths = [f"phases.0.distortion_modes.modes.{i}.amplitude" for i in t.modes]
        cov = table.physical_covariance(theta, stderr, corr, paths)
        a = np.array([values[p] for p in paths])
        c = a / np.linalg.norm(a)
        return float(a @ np.linalg.inv(cov) @ a), math.sqrt(float(c @ cov @ c))

    rows = {p.path: p for p in result.parameters}
    for t in totals:
        t2, esd = hand(t)
        assert t.t2 == pytest.approx(t2, rel=1e-10), t.irrep
        assert t.esd == pytest.approx(esd, rel=1e-10), t.irrep
        if t.n_modes == 1:
            # an independent arm: one mode's block esd is that amplitude's own esd
            (i,) = t.modes
            row = rows[f"phases.0.distortion_modes.modes.{i}.amplitude"]
            assert t.esd == pytest.approx(row.stderr, rel=1e-10)
            assert t.t2 == pytest.approx((row.value / row.stderr) ** 2, rel=1e-9)
    # positive arm: the covariance multiplied by f² a second time misses the hand form
    original = RD._block_covariance
    monkeypatch.setattr(RD, "_block_covariance", lambda *a: original(*a) * f * f)
    twice = RD.distortion_totals(table, theta, structure, values, stderr_internal=stderr,
                                 correlation=corr)
    for t in twice:
        assert t.t2 != pytest.approx(hand(t)[0], rel=1e-10)
        assert t.t2 == pytest.approx(hand(t)[0] / (f * f), rel=1e-10)


#: Perez-Mato, Orobengoa & Aroyo (2010) Table 13, p. 577, LaMnO₃ at 300 K
#: (Rodríguez-Carvajal et al. 1998): irrep → (isotropy subgroup, modes, Å)
TABLE_13 = {
    "R4+": ("Imma", 1, 1.19),
    "R5+": ("Imma", 2, 0.09),
    "X5+": ("Cmcm", 2, 0.56),
    "M2+": ("P4/mbm", 1, 0.36),
    "M3+": ("P4/mbm", 1, 0.90),
}
#: the bar main holds the shipped CIF's own decomposition to against Table 13
#: (``test_distortion_modes.test_lamno3_reproduces_table_13``); Yue has not
#: ruled #1107 question 3, whose default is that loose bar with the 50 K /
#: 300 K gap stated
TABLE_13_BAR = 0.03


def _table_13_labels(phase):
    """Table 13's label for each block, through the CIF's decomposition's labels."""
    from tests.test_distortion_modes import _label_lamno3

    dec = D.mode_amplitudes(_cubic(), structure_from_cif(DATA / "gsas2_bt1_lamno3.cif")
                            .phases[0], LAMNO3_T)
    by = {(row.irrep, tuple(row.k)): label for label, row in _label_lamno3(dec).items()}
    return {key: by[(key[0], key[1])] for key in RD.distortion_blocks(phase)}


@BT1
def test_bt1_a_tau_against_table_13_and_t2_on_every_irrep(bt1_modes):
    """Test 3: the 50 K pattern's five A_τ against Table 13's 300 K values, and T² on each.

    Measured 2026-10-30 (macOS arm64): R4+ 1.1946(67), R5+ 0.0893(56),
    X5+ 0.5536(48), M2+ 0.3334(69), M3+ 0.8955(65) Å against 1.19 / 0.09 /
    0.56 / 0.36 / 0.90.  Within 0.03 Å on all five; within its esds it is not:
    M2+ is 3.9 esd off, which the temperature gap or the reference's own
    0.024 Å (the CIF's decomposition) can carry.  The comparison rows of the
    five irreps are recorded in the build report, not asserted.  Positive arm:
    the norm read per parent cell rather than per primitive child cell (÷2)
    misses the bar.
    """
    totals = bt1_modes["result"].distortion_totals
    labels = _table_13_labels(bt1_modes["ref"].structure.phases[0])
    assert sorted(labels.values()) == sorted(TABLE_13)
    off_unit = []
    for t in totals:
        group, n_modes, amplitude = TABLE_13[labels[(t.irrep, t.k, t.isotropy_group)]]
        assert t.isotropy_group.split(" ")[0] == group
        assert t.n_modes == n_modes
        assert t.t2 is not None and math.isfinite(t.t2) and t.t2 > 0.0
        assert t.esd_label == RD.ESD_LABEL
        assert t.a_tau == pytest.approx(amplitude, abs=TABLE_13_BAR)
        off_unit.append(abs(t.a_tau / 2.0 - amplitude) > TABLE_13_BAR)
    assert any(off_unit)


@pytest.fixture(scope="module")
def bt1_tests(bt1_modes):
    """Every non-identity block of the BT-1 fit held alone, with the restricted refits kept."""
    kept = []
    original = RD._test_one

    def spy(*args, **kw):
        row, restricted = original(*args, **kw)
        kept.append(restricted)
        return row, restricted

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(RD, "_test_one", spy)
        tests = bt1_modes["ref"].distortion_block_tests(bt1_modes["data"])
    return tests, kept


@BT1
def test_each_restricted_refit_holds_its_block_at_zero_and_refits_the_rest(bt1_modes, bt1_tests):
    """Test 5 (b): every held amplitude is exactly 0, and everything else was refitted.

    Revert: a restricted refit that leaves the block free reaches the full
    fit's own χ² (Δχ² ≈ 0) with the amplitudes where they were.
    """
    tests, kept = bt1_tests
    full = bt1_modes["result"]
    assert tests.restarts == [] and tests.restarted_result is None
    assert len(tests.tests) == len(kept) == 5
    free_full = {p.path for p in full.parameters if p.vary}
    values_full = {p.path: p.value for p in full.parameters}
    for row, restricted in zip(tests.tests, kept, strict=True):
        assert row.held == [list(row.held[0])] or len(row.held) == 1
        modes = RD.distortion_blocks(restricted.structure.phases[0])[tuple(row.held[0])]
        amps = amplitudes(restricted.structure.phases[0])
        assert all(amps[i] == 0.0 for i in modes)
        held = {f"phases.0.distortion_modes.modes.{i}.amplitude" for i in modes}
        # no BISO_NEGATIVE assertion here: a restricted model is the full one with a
        # published distortion removed, and on the real pattern a Biso absorbs some of
        # that misfit (the build report lists which blocks); the fixture fit is checked
        res = restricted.result_
        assert {p.path for p in res.parameters if p.vary} == free_full - held
        moved = [p.path for p in res.parameters if p.vary and abs(
            p.value - values_full[p.path]) > 1e-9 * max(abs(values_full[p.path]), 1.0)]
        assert len(moved) > len(free_full - held) // 2
        assert row.m == len(modes)
        assert row.chi2_restricted > row.chi2_full
        assert row.chi2_full == pytest.approx(
            full.statistics.chi2 * (full.statistics.n_points - full.statistics.n_free_parameters),
            rel=1e-12)
        assert row.a_det is None
        assert math.isfinite(row.delta_bic) and math.isfinite(row.lambda_)


# --------------------------------------------------------------------------
# the comparison's arithmetic (test 5 a)
# --------------------------------------------------------------------------

def test_the_block_comparison_is_compare_freeds_bic_and_hamiltons_lambda():
    """Test 5 (a): ΔBIC at N/f_restricted², Λ at χ²_red,full·f_full², on stated numbers.

    The stated case is the BT-1 P1 M3+ block of the #286 comment:
    Δχ² = 145.8 against χ²_red 7.735 and f 3.206 of the full fit, Λ = 1.834.
    Revert: swapping which f each statistic reads changes both numbers.
    """
    chi2_f, n, m = 22586.0, 2984, 1
    chi2_r = chi2_f + 145.8
    f_r, f_f, chi2_red = 3.30, 3.206, 7.735
    dbic, lam, p = RD.block_comparison(chi2_r, chi2_f, n, m, esd_inflation_restricted=f_r,
                                       esd_inflation_full=f_f, chi2_red_full=chi2_red)
    n_eff = n / f_r ** 2
    assert dbic == pytest.approx(n_eff * math.log(chi2_r / chi2_f) - m * math.log(n_eff),
                                 rel=1e-12)
    assert lam == pytest.approx(145.8 / (7.735 * 3.206 ** 2), rel=1e-12)
    assert lam == pytest.approx(1.834, abs=5e-4)
    from scipy.stats import chi2 as chi2_dist
    assert p == pytest.approx(float(chi2_dist.sf(lam, m)), rel=1e-12)
    # positive arm: the other f in either place gives another number
    n_swap = n / f_f ** 2
    assert dbic != pytest.approx(n_swap * math.log(chi2_r / chi2_f) - m * math.log(n_swap),
                                 rel=1e-6)
    assert lam != pytest.approx(145.8 / (7.735 * f_r ** 2), rel=1e-6)
    # and the same ΔBIC as compare_freed's own function at that N
    from rietx.report import delta_bic
    assert dbic == delta_bic(chi2_r, chi2_f, n, m, n_effective=n_eff)


def test_a_det_is_the_formula_on_stated_numbers():
    """A_det = min_j A₀·(target/λ_j)^(1/p_j); target χ²_red·f²·(m·ln(N/f²) + bar)."""
    target = RD.detectability_target(1.2, 1.1, 2984, 5, 6.0)
    assert target == pytest.approx(1.2 * 1.21 * (5 * math.log(2984 / 1.21) + 6.0), rel=1e-12)
    a = RD.detectability_amplitude([125.6, 55.9, 0.0], [4, 2, 4], target, probe=0.1)
    assert a == pytest.approx(min(0.1 * (target / 125.6) ** 0.25,
                                  0.1 * (target / 55.9) ** 0.5), rel=1e-12)
    assert RD.detectability_amplitude([0.0, 0.0], [4, 4], target, probe=0.1) is None
    assert RD.detectability_amplitude([1.0], [4], -1.0, probe=0.1) == 0.0


# --------------------------------------------------------------------------
# basis rotation (test 2)
# --------------------------------------------------------------------------

def _rotated(phase, modes, q):
    """``phase`` with the modes of one block rotated by the orthogonal ``q``."""
    record = phase.distortion_modes.model_copy(deep=True)
    v = np.array([record.modes[i].vectors for i in modes])
    a = np.array([record.modes[i].amplitude.value for i in modes])
    for row, i in enumerate(modes):
        record.modes[i].vectors = [tuple(float(x) for x in r)
                                   for r in np.tensordot(q[row], v, axes=1)]
        record.modes[i].amplitude.value = float(q[row] @ a)
    return phase.model_copy(update={"distortion_modes": record})


#: the bar for "unchanged under the rotation": two converged fits of one model in
#: two parametrisations.  Measured 2026-10-30 (macOS arm64): A_τ 2.0e-8, esd
#: 8.4e-8, T² 1.9e-7, Δχ² 1.3e-13, ΔBIC 1.0e-11, Λ 6.5e-9 relative; a 50×
#: margin on the widest, against a diagonal form that moves by 37 %
ROTATION_REL = 1e-5


@BT1
@pytest.mark.slow
def test_the_block_quantities_do_not_depend_on_the_basis_inside_it(bt1_modes):
    """Test 2: rotate X5+'s two modes (La and O) by an orthogonal matrix and refit.

    A_τ, its esd, T², and the block comparison's Δχ², ΔBIC and Λ agree to
    ROTATION_REL relative.  Positive arm: the per-mode sum Σ A_i²/σ_i² (the
    diagonal covariance) differs between the two bases by far more.
    """
    statement = bt1_modes["statement"]
    phase = statement.phase
    # X5+, at k = (0, 1/2, 0): one mode on La and one on O
    key = next(k for k in RD.distortion_blocks(phase) if k[1] == ("0", "1/2", "0"))
    modes = RD.distortion_blocks(phase)[key]
    theta = 0.7
    q = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
    ref_r, res_r, cap_r = _fit_modes(_rotated(phase, modes, q),
                                     (statement, bt1_modes["instrument"]), bt1_modes["data"],
                                     bt1_modes["limits"], bt1_modes["free"])
    no_biso_negative(res_r)
    res = bt1_modes["result"]
    t0 = next(t for t in res.distortion_totals if (t.irrep, t.k, t.isotropy_group) == key)
    t1 = next(t for t in res_r.distortion_totals if (t.irrep, t.k, t.isotropy_group) == key)
    for name in ("a_tau", "esd", "t2"):
        assert getattr(t1, name) == pytest.approx(getattr(t0, name), rel=ROTATION_REL), name
    b0 = bt1_modes["ref"].distortion_block_tests(bt1_modes["data"], hold=[key]).tests[0]
    b1 = ref_r.distortion_block_tests(bt1_modes["data"], hold=[key]).tests[0]
    assert b1.chi2_restricted - b1.chi2_full == pytest.approx(
        b0.chi2_restricted - b0.chi2_full, rel=ROTATION_REL)
    assert b1.delta_bic == pytest.approx(b0.delta_bic, rel=ROTATION_REL)
    assert b1.lambda_ == pytest.approx(b0.lambda_, rel=ROTATION_REL)

    def diagonal(capture, result):
        table, theta_, _, values, stderr, corr, _ = capture.matching(result.distortion_totals)
        paths = [f"phases.0.distortion_modes.modes.{i}.amplitude" for i in modes]
        cov = table.physical_covariance(theta_, stderr, corr, paths)
        a = np.array([values[p] for p in paths])
        return float(np.sum(a * a / np.diag(cov)))

    d0 = diagonal(bt1_modes["capture"], res)
    d1 = diagonal(cap_r, res_r)
    assert abs(d1 / d0 - 1.0) > 100 * ROTATION_REL


# --------------------------------------------------------------------------
# the synthetic children: Biso ties, shape, A_det
# --------------------------------------------------------------------------

SYN = pytest.mark.xdist_group("distortion-totals-synthetic")


@SYN
def test_the_tied_native_fit_carries_no_negative_biso_and_the_untied_one_does():
    """Test 8: the native path ties Biso per parent site, and that is what keeps BISO_NEGATIVE off.

    Revert (the positive arm): the same pattern and start with per-site Biso
    free raises the code (measured on seed 0 of the Γ null child).
    """
    truth, start = child(GAMMA)
    data = synthetic(truth.phase, 0, STREAM["gamma_null"])
    _, tied = native_fit(start, data)
    no_biso_negative(tied)
    _, untied = native_fit(start, data, tie=False)
    assert "BISO_NEGATIVE" in {d.code for d in untied.diagnostics}


@SYN
def test_every_record_is_numbers_with_the_esd_label_and_no_verdict():
    """Test 9: the esd label on every DistortionTotal; no t2_p, verdict or correlation field."""
    truth, start = child(GAMMA)
    ref, result = native_fit(start, synthetic(truth.phase, 0, STREAM["gamma_null"]))
    assert result.distortion_totals
    for t in result.distortion_totals:
        assert t.esd_label == RD.ESD_LABEL == (
            "linearised; undefined at A_τ = 0 and Rice-biased below about 2 esd")
        assert t.sign_convention == RD.SIGN_CONVENTION
    from rietx.report import DistortionBlockTest, DistortionBlockTests, DistortionRestart
    from rietx.schemas.results import DistortionTotal
    for model in (DistortionTotal, DistortionBlockTest, DistortionBlockTests, DistortionRestart):
        for name in model.model_fields:
            assert name not in {"t2_p", "verdict", "lambda_p_holm", "delta_bic_raw_n"}, name
            assert "correlation" not in name and "supported" not in name, name
    # a phase with no modes reports none
    plain = rx.Refinement(Structure(phases=[bt1_nuclear()[0]]), bt1_nuclear()[1], history=False)
    out = plain.fit(synthetic(truth.phase, 0, STREAM["gamma_null"]),
                    plan=rx.RefinementPlan(stages=[rx.Stage(name="s", turn_on=["phases.0.scale"])]),
                    telemetry=False)
    assert out.distortion_totals is None


#: the probe amplitude (Å) the A_det tests pass: the caller's argument, no default
PROBE = 0.1


def _restricted_and_row(ref, data, hold, bar):
    kept = []
    original = RD._test_one

    def spy(*args, **kw):
        row, restricted = original(*args, **kw)
        kept.append(restricted)
        return row, restricted

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(RD, "_test_one", spy)
        tests = ref.distortion_block_tests(data, hold=hold, detectability_bar=bar,
                                           detectability_probe=PROBE)
    return tests, kept


#: A_det's agreement with the bisected crossing as F5.2 measured it, by exponent
#: (p = 4 within 1.1 %, p = 2 within 2.7 %), and the margin this test adds
A_DET_MEASURED = {4: 0.011, 2: 0.027}
A_DET_MARGIN = 0.01


@SYN
@pytest.mark.parametrize("which", [
    GAMMA, pytest.param(ZONE, marks=pytest.mark.slow)], ids=["gamma", "zone"])
def test_a_det_meets_the_bisected_crossing(which):
    """Test 6: A_det at the 0.1 Å probe against predict-only bisection, per held mode.

    On the null child (seed 0), the tested block and the identity block are
    each held; at the restricted optimum every mode's A₀·(3.84/λ_j)^(1/p_j) is
    compared with the bisected amplitude at which λ_j = 3.84, within the
    measured 1.1 % (p = 4) and 2.7 % (p = 2) plus A_DET_MARGIN, i.e. the bars
    this test enforces: 2.1 % (p = 4) and 3.7 % (p = 2), at the 0.1 Å probe, on
    two blocks of one material at one noise seed.  The row's
    ``a_det`` is that formula at the call's own target.  Positive arm: the
    other exponent misses by more than 25 %.

    Measured 2026-10-30 (macOS arm64), largest |offset| per held block: Γ
    child S6 1.66 % (p = 4), identity 2.44 % (p = 2); zone-boundary child S1
    0.56 % (p = 4), identity 1.40 % (p = 2).  The other exponent misses the
    block's crossing by a factor 2.4, 5.9, 1.8 and 4.9.
    """
    truth, start = child(which)
    _, inst, tt, sigma = bt1_nuclear()
    data = synthetic(truth.phase, 0, STREAM["gamma_null" if which is GAMMA else "zone_null"])
    ref, result = native_fit(start, data)
    no_biso_negative(result)
    phase = ref.structure.phases[0]
    tested = block_key(phase, which[1])
    identity = next(k for k, v in RD.distortion_blocks(phase).items()
                    if all(phase.distortion_modes.modes[i].parent_invariant for i in v))
    tests, kept = _restricted_and_row(ref, data, [tested, identity], 6.0)
    seen = set()
    for row, restricted in zip(tests.tests, kept, strict=True):
        base = restricted.structure.phases[0]
        inst_r = restricted.instrument
        modes = RD.distortion_blocks(base)[tuple(row.held[0])]
        even = D.amplitude_action(base).even(amplitudes(base))
        lambdas, exps, ratios, bisected = [], [], [], []
        for j in modes:
            lam = mode_lambda(base, inst_r, tt, sigma, j)
            p = RD.EVEN_EXPONENT if even[j] else RD.LINEAR_EXPONENT
            lambdas.append(lam(PROBE))
            exps.append(p)
            bisected.append(a_need(lam))
            ratios.append((p, PROBE * (3.84 / lambdas[-1]) ** (1.0 / p)
                           / bisected[-1] - 1.0))
        for p, r in ratios:
            assert abs(r) <= A_DET_MEASURED[p] + A_DET_MARGIN, (row.held, p, r)
            seen.add(p)
        # positive arm, on the block's A_det at 3.84 (its easiest mode): the other
        # exponent misses the bisected crossing by more than a factor 1.25
        wrong = [6 - p for p in exps]
        miss = RD.detectability_amplitude(lambdas, wrong, 3.84, probe=PROBE) / min(bisected)
        assert max(miss, 1.0 / miss) > 1.25, (row.held, miss)
        target = RD.detectability_target(result.statistics.chi2, row.esd_inflation_restricted,
                                         row.n_points, len(modes), 6.0)
        assert row.a_det == pytest.approx(RD.detectability_amplitude(lambdas, exps, target, probe=PROBE),
                                          rel=1e-6)
    assert seen == {2, 4}


# --------------------------------------------------------------------------
# the restart (test 4)
# --------------------------------------------------------------------------

@SYN
def test_a_restricted_fit_below_the_full_one_restarts_the_full_fit():
    """Test 4: the full fit is refitted from the lower restricted optimum, and every set retested.

    No native seed gives the case on its own here: the seed scan over 50
    zone-boundary null seeds (the build report) found no restricted refit
    below its full fit with Biso tied, against 10 of 50 in F5.3 with per-site
    Biso free.  So the full fit is made to stop short, the case the restart
    exists for: the Γ null child (seed 0) from an instrument whose zero is
    0.1° off and whose u and w are three times the nuclear fit's, one
    iteration per stage.  It stops at χ² ≈ 27 400, and the restricted refit
    from there reaches ≈ 2 932 (measured 2026-10-30, macOS arm64).

    Positive arm: the first pass alone, with no restart, leaves the restricted
    χ² below the full χ², which is what removing the restart would report.
    """
    truth, start = child(GAMMA)
    data = synthetic(truth.phase, 0, STREAM["gamma_null"])
    inst = bt1_nuclear()[1].model_copy(deep=True)
    inst.zero_shift.value += 0.1
    inst.profile.u.value *= 3.0
    inst.profile.w.value *= 3.0
    ref, result = native_fit(start, data, max_iter=1, instrument=inst)
    assert result.status == "max_iter"
    no_biso_negative(result)
    key = block_key(ref.structure.phases[0], GAMMA[1])
    first = RD._test_one(ref, data, 0, [key], None)[0]
    assert first.chi2_restricted < first.chi2_full
    out = ref.distortion_block_tests(data, hold=[key])
    assert len(out.restarts) >= 1
    previous = first.chi2_full
    for r in out.restarts:
        assert r.held == [key] and r.lowered
        assert r.chi2_full_before == pytest.approx(previous, rel=1e-12)
        assert r.chi2_full_after < r.chi2_restricted < r.chi2_full_before
        previous = r.chi2_full_after
    assert all(r.chi2_restricted >= r.chi2_full for r in out.tests)
    assert out.restarted_result is not None
    no_biso_negative(out.restarted_result)
    final = out.restarted_result.statistics
    assert out.tests[0].chi2_full == pytest.approx(
        final.chi2 * (final.n_points - final.n_free_parameters), rel=1e-12)
    assert out.tests[0].chi2_full == pytest.approx(previous, rel=1e-12)
    # the caller's refinement is left as it was
    assert ref.result_ is result


# --------------------------------------------------------------------------
# review round 1: what a report field may do to a fit, what hold=None selects,
# what counts as a restart, what A_det needs from the caller
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def gamma_null():
    """The Γ null child (seed 0) fitted natively: (refinement, data, result)."""
    truth, start = child(GAMMA)
    data = synthetic(truth.phase, 0, STREAM["gamma_null"])
    ref, result = native_fit(start, data)
    return ref, data, result


@SYN
def test_a_phase_whose_action_cannot_be_built_still_fits_with_driving_unanswered(monkeypatch):
    """A record whose parent operations miss its reference structure must not abort the fit.

    ``amplitude_action`` raises ``RuntimeError`` there; the fit still returns, every
    quantity but ``driving`` is the same, and ``driving`` is ``None`` rather than a guess.
    Positive arm: unpatched, ``driving`` is a bool on every block.
    """
    truth, start = child(GAMMA)
    data = synthetic(truth.phase, 0, STREAM["gamma_null"])
    _, normal = native_fit(start, data)
    assert all(isinstance(t.driving, bool) for t in normal.distortion_totals)

    def refuse(phase):
        raise RuntimeError("a parent operation did not map the reference structure onto itself")

    monkeypatch.setattr(D, "amplitude_action", refuse)
    _, broken = native_fit(start, data)
    assert [t.driving for t in broken.distortion_totals] == [None] * len(normal.distortion_totals)
    for a, b in zip(normal.distortion_totals, broken.distortion_totals, strict=True):
        assert (a.a_tau, a.esd, a.t2) == (b.a_tau, b.esd, b.t2)


@SYN
def test_hold_none_holds_only_the_blocks_the_fit_freed():
    """``hold=None`` selects blocks whose amplitudes all varied; a freed-only-in-part fit gets rows.

    The Γ null child fitted with only the identity block's amplitudes free:
    ``hold=None`` returns no row for the blocks the fit held (it used to raise
    ``ValueError`` on the first of them).  Freeing the tested block as well gives its row.
    Positive arm: a named block the fit did not free still raises.
    """
    truth, start = child(GAMMA)
    data = synthetic(truth.phase, 0, STREAM["gamma_null"])
    phase = start.phase
    blocks = RD.distortion_blocks(phase)
    tested = block_key(phase, GAMMA[1])
    identity = next(k for k, v in blocks.items()
                    if all(phase.distortion_modes.modes[i].parent_invariant for i in v))
    base = [f for f in _protocol()[2] if f != AMPS]

    def amps(*keys):
        return [f"phases.0.distortion_modes.modes.{i}.amplitude" for k in keys for i in blocks[k]]

    ref, _ = native_fit(start, data, free=base + amps(identity, tested))
    got = ref.distortion_block_tests(data)
    assert tested in [tuple(r.held[0]) for r in got.tests]
    ref, _ = native_fit(start, data, free=base + amps(identity))
    assert ref.distortion_block_tests(data).tests == []
    with pytest.raises(ValueError, match="did not free"):
        ref.distortion_block_tests(data, hold=[tested])


@SYN
def test_a_restricted_chi2_within_the_solvers_ftol_below_the_full_one_is_not_a_restart(
        gamma_null, monkeypatch):
    """A restricted χ² below the full one by round-off (< ftol) starts no refit.

    The rows are rewritten so the restricted χ² sits half an ftol below the full one
    (what a held true zero lands at): no restart.  Positive arm: ten ftol below,
    where the full fit has demonstrably stopped short, the restart is recorded.
    """
    from rietx.optimize.lm import FTOL

    ref, data, _ = gamma_null
    key = block_key(ref.structure.phases[0], GAMMA[1])
    original = RD._test_one

    def below(fraction):
        def patched(*args, **kw):
            row, restricted = original(*args, **kw)
            return row.model_copy(update={"chi2_restricted": row.chi2_full * (1 - fraction)}), \
                restricted
        return patched

    monkeypatch.setattr(RD, "_test_one", below(0.5 * FTOL))
    assert ref.distortion_block_tests(data, hold=[key]).restarts == []
    monkeypatch.setattr(RD, "_test_one", below(10 * FTOL))
    # the rewritten row is not a real optimum, so the loop ends at the first restart
    assert len(ref.distortion_block_tests(data, hold=[key]).restarts) >= 1


@SYN
def test_a_det_needs_the_callers_probe_and_records_it(gamma_null):
    """A bar without a probe raises before any refit; with both, the record carries both."""
    ref, data, _ = gamma_null
    key = block_key(ref.structure.phases[0], GAMMA[1])
    with pytest.raises(ValueError, match="detectability_probe"):
        ref.distortion_block_tests(data, hold=[key], detectability_bar=6.0)
    out = ref.distortion_block_tests(data, hold=[key], detectability_bar=6.0,
                                     detectability_probe=PROBE)
    assert (out.detectability_bar, out.detectability_probe) == (6.0, PROBE)
    assert out.tests[0].a_det is not None


@SYN
def test_a_block_key_survives_a_json_round_trip_and_a_foreign_total_is_refused(gamma_null):
    """A key read back from ``model_dump(mode="json")`` is a list and still names one block;
    a ``DistortionTotal`` of another refinement's phase raises the intended message."""
    ref, _, result = gamma_null
    total = result.distortion_totals[0]
    key = (total.irrep, tuple(total.k), total.isotropy_group)
    as_json = [total.irrep, list(total.k), total.isotropy_group]
    assert RD.held_sets(ref.structure, [as_json]) == RD.held_sets(ref.structure, [key])
    assert RD.held_sets(ref.structure, [[as_json, as_json]]) == RD.held_sets(
        ref.structure, [[key]])
    with pytest.raises(ValueError, match="another fit"):
        RD.held_sets(ref.structure, [total.model_copy(update={"phase": 7})])


# --------------------------------------------------------------------------
# A_τ's esd against its scatter (test 7)
# --------------------------------------------------------------------------

#: the planted strengths, in A_need of the block's easiest mode (the verdict's planted arms)
PLANT = {"gamma": (GAMMA, 3.0), "zone": (ZONE, 4.0)}
SEEDS = range(40)


def scatter(name, seeds=SEEDS):
    """(A_τ, esd, diagonal-only esd, f, χ²_red, codes) of the planted block per seed."""
    which, c = PLANT[name]
    truth, j, need = planted(which, c)
    _, start = child(which)
    rows = []
    for seed in seeds:
        capture = Capture()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(refine_module, "_distortion_totals", capture)
            ref, result = native_fit(start, synthetic(truth, seed, STREAM[f"{name}_plant"]))
        key = block_key(ref.structure.phases[0], which[1])
        t = next(t for t in result.distortion_totals if (t.irrep, t.k, t.isotropy_group) == key)
        table, theta, _, values, stderr, corr, _ = capture.matching(result.distortion_totals)
        paths = [f"phases.0.distortion_modes.modes.{i}.amplitude" for i in t.modes]
        cov = table.physical_covariance(theta, stderr, corr, paths)
        a = np.array([values[p] for p in paths])
        c_ = a / np.linalg.norm(a)
        rows.append((t.a_tau, t.esd, math.sqrt(float(np.sum(c_ * c_ * np.diag(cov)))),
                     result.statistics.esd_inflation, result.statistics.chi2,
                     sorted({d.code for d in result.diagnostics})))
    return rows


@SYN
@pytest.mark.slow
@pytest.mark.parametrize("name", [
    "gamma",
    pytest.param("zone", marks=pytest.mark.xfail(strict=True, reason=(
        "measured 2026-10-30 (Linux x86-64, 40 seeds): SD 0.00595 A against a median esd of "
        "0.00864 A, ratio 0.689, below the band; 0.778 with the Berar-Lelann factor "
        "(f 1.10-1.14 on white noise) taken out; reported for a ruling, band not moved")))])
def test_the_esd_of_a_tau_describes_its_scatter_over_40_seeds(name):
    """Test 7: seed-to-seed SD of A_τ over the median reported esd lies in [0.75, 1.33].

    The Γ block planted at 3× its A_need and the zone-boundary block at 4×, 40
    white-noise seeds each, native path.  On white noise f is near 1 and 40
    seeds fix the SD to about ±11 %, so the band is about 2.5 of those either
    side of 1.  Both blocks sit well above 2 esd, where the label says the esd
    means something.

    Measured 2026-10-30 (Linux x86-64): Γ 0.926
    (A_τ 0.1312 ± SD 0.0072 for 0.1244 planted), zone-boundary 0.689 (0.2301 ±
    0.0060 for 0.2220), outside the band, so that arm is an expected failure
    until it is ruled on.  The diagonal-only esd (the block's off-diagonal
    covariance dropped) gives 0.909 on Γ, inside the band, so on that block
    the check cannot catch it; 0.176 on the zone-boundary block.
    """
    rows = scatter(name)
    a = np.array([r[0] for r in rows])
    esd = np.array([r[1] for r in rows])
    assert np.all(a > 2.0 * esd)
    ratio = float(np.std(a, ddof=1) / np.median(esd))
    assert 0.75 <= ratio <= 1.33, ratio
    assert not any("BISO_NEGATIVE" in r[5] for r in rows)
