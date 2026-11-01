"""v0.3 acceptance: lab corundum against the NIST SRM 676a certified cell.

The certificate (04 Nov 2015 issue; lattice values 23 Apr 2012) is the
**absolute anchor**: a = 4.759355 ± 0.000080 Å, c = 12.99231 ± 0.00015 Å at
22.5 °C (k = 2), on the Hölzer (1997) Cu Kα1 wavelength scale — the same
scale the ``CuKa`` instrument preset ships.  Two honesty caveats, both from
the WP-0310 brief:

* NIST publishes **no raw 676a pattern**, so the fit runs on the IUCr
  round-robin's pure-corundum lab pattern (``qarr/corundum.prn``), whose
  provenance is *not* documented as SRM 676a.  It stands in as a lab corundum
  *specimen*; the certified cell anchors the comparison, not the specimen's
  identity.
* On an ordinary Bragg-Brentano pattern the {zero, displacement, cell} triple
  is decorrelated only by *holding* a certified cell (the ``lab_calibrate``
  lesson), which is exactly what a cell-accuracy test cannot do.  The
  practical absolute tolerance is therefore lab-realistic (6×10⁻⁴ relative),
  nowhere near the certificate's ~17 ppm, and the sharp certificate-grade
  assertion is the **axial ratio c/a** — uniform d-scale systematics (zero,
  displacement, wavelength convention) cancel in it, so it survives lab data
  unharmed.  The same shape-vs-magnitude reasoning as the v0.2 FAP test.

The certificate's other value — crystalline mass fraction 99.02 ± 1.11 %
(k = 2) — is an *amorphous* quantity, certified against an external silicon
series.  Amorphous/internal-standard quantification is a v2 fence and a
WP-0310 non-goal: ``RefinementResult.qpa`` reports fractions of the modelled
crystalline content (≡ 1 for a single phase, asserted below), and this suite
does not claim to test the 99.02 %.

**Measured result** (2026-07-24, recorded in docs/milestones/v0.3.md):
Rwp = 14.4 %, GoF = 1.61; a = 4.757866 Å (−313 ppm), c = 12.988632 Å
(−283 ppm), the two axes offset by the same relative amount (Δ within
3×10⁻⁵) ⇒ a uniform d-scale systematic of this uncalibrated instrument —
while **c/a = 2.729928 lands +30 ppm** from the certificate's 2.729846.
Refined Kα2/Kα1 = 0.43 (the graphite passband clips the 0.5 emission ratio),
Biso(Al) = 0.23, Biso(O) = 0.22 Å² — both physical.


Dispersion is **declined**, inherited from ``qarr_instrument`` in
``test_acceptance_qpa_roundrobin``.  WP-1001 measured what the (now default)
block does to this suite's certificate-grade assertion and it is safe either
way — c/a moves +29.8 → +30.2 ppm against a 100 ppm bar — but Rwp rises
14.374 → 14.531 % and Biso(Al) 0.232 → 0.314 Å², so the recorded numbers below
are dispersion-off ones and say so.
"""

import math
from pathlib import Path

import pytest

import rietx as rx

from .test_acceptance_qpa_roundrobin import (
    DATA,
    corundum_phase,
    qarr_instrument,
    qpa_plan,
    seed_scales,
)

pytestmark = pytest.mark.slow

A_CERT, A_CERT_U = 4.759355, 0.000080   # k = 2, 22.5 °C
C_CERT, C_CERT_U = 12.99231, 0.00015


def test_srm676a_corundum_cell_anchor():
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / "corundum.prn")
    structure = rx.Structure(phases=[corundum_phase()])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)

    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan=qpa_plan())

    assert result.status == "converged"
    assert result.statistics.n_points == 7251
    assert result.statistics.rwp < 0.17
    assert result.statistics.gof < 2.0

    phase = ref.fitted_structure.phases[0]
    a, c = phase.cell.a.value, phase.cell.c.value
    da, dc = a / A_CERT - 1.0, c / C_CERT - 1.0
    # lab-realistic absolute band (uncalibrated zero/displacement — docstring)
    assert abs(da) < 6e-4 and abs(dc) < 6e-4
    # the offset must be a *uniform* d-scale, the same on both axes…
    assert abs(da - dc) < 1.5e-4
    # …which is why c/a carries the certificate-grade comparison: its k = 2
    # relative uncertainty is ~21 ppm, and the fit must land within a small
    # multiple of it (measured +30 ppm)
    assert (c / a) / (C_CERT / A_CERT) - 1.0 == pytest.approx(0.0, abs=1e-4)
    # hexagonal tie: b tracks a; symmetry-fixed angles never moved
    assert phase.cell.b.value == pytest.approx(a, rel=1e-12)
    assert phase.cell.gamma.value == 120.0

    # esds exist and are Bérar-Lelann inflated; the −313 ppm absolute offset
    # is a many-σ *systematic*, which is exactly why the absolute band above
    # is not the certificate's — never let an esd launder a systematic
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None and 0.0 < a_esd < 1e-3
    assert result.statistics.esd_inflation > 1.0

    # physical displacement parameters and a clipped-doublet Kα2 ratio
    assert 0.05 < phase.atoms[0].biso.value < 1.0
    assert 0.05 < phase.atoms[1].biso.value < 1.0
    ka2 = ref.fitted_instrument.source.lines[1].weight.value
    assert 0.35 < ka2 < 0.55

    # single modelled phase ⇒ the QPA convention (fractions of the modelled
    # crystalline content) makes this identically 1; the certificate's
    # 99.02 % amorphous complement is out of scope (docstring)
    assert result.qpa is not None and len(result.qpa.phases) == 1
    assert result.qpa.phases[0].weight_fraction == pytest.approx(1.0, abs=1e-12)

    from rietx.viz.plots import plot_for_vlm, plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "srm676a_fit.png"))
    plot_result(result, path=str(out / "srm676a_fit_lowangle.png"),
                two_theta_range=(24.0, 60.0))
    plot_result(result, path=str(out / "srm676a_fit_highangle.png"),
                two_theta_range=(120.0, 150.0))
    report = ref.report(plan=qpa_plan())
    plot_for_vlm(result, report, path=str(out / "srm676a_vlm.png"))
    import matplotlib.pyplot as plt
    plt.close("all")


# ----------------------------------------------------------------------
# WP-1036: the same lattice on rhombohedral axes
# ----------------------------------------------------------------------
# Corundum is R-3c, so it has two equally valid cell descriptions, and before
# WP-1036 the parameter table could only serve one of them.  On rhombohedral
# axes it tied b←a but left c free — breaking a = b = c — and locked all three
# angles at their stored value, removing the single angular degree of freedom
# the setting has.  The free-parameter count was 2 either way, so nothing
# counting degrees of freedom could see it.
#
# The assertion below is stronger than "the ties are right": the *same physical
# lattice*, started from the same place and fitted with the same plan, must give
# the same answer in both descriptions.


def hexagonal_from_rhombohedral(a_r: float, alpha_deg: float) -> tuple[float, float]:
    """(a_H, c_H) of the hexagonal description of a rhombohedral cell.

    a_H = 2·a_R·sin(α/2), c_H = a_R·√(3 + 6cos α) — International Tables for
    Crystallography Vol. A, the obverse setting relating the two descriptions of
    an R lattice (V_H = 3·V_R, checked in the test).
    """
    a_h = 2.0 * a_r * math.sin(math.radians(alpha_deg) / 2.0)
    c_h = a_r * math.sqrt(3.0 + 6.0 * math.cos(math.radians(alpha_deg)))
    return a_h, c_h


def rhombohedral_from_hexagonal(a_h: float, c_h: float) -> tuple[float, float]:
    """(a_R, α) of the rhombohedral description — the inverse of the above."""
    a_r = math.sqrt(a_h ** 2 / 3.0 + c_h ** 2 / 9.0)
    alpha = 2.0 * math.degrees(math.asin(3.0 / (2.0 * math.sqrt(3.0 + (c_h / a_h) ** 2))))
    return a_r, alpha


def _lattice_only_plan():
    """Le Bail, so the fit is about the lattice and nothing else.

    A dummy atom carries no structure — exactly the indexing validator's device
    — which is what makes this a clean test of the cell ties: the rhombohedral
    *atomic* coordinates never enter, so they cannot be got wrong and confound
    the comparison.  Stage order follows ``validation_plan``: ``w`` before the
    other width terms, because it is the only one non-zero at 2θ = 0.

    The (profile, cell) round repeats until the descent flattens, and that is
    load-bearing rather than thorough (measured 2026-08-17, darwin/arm64).  With
    one round the two arms of the test below stop at Rwp 0.1499524 having agreed
    to 1.2e-8 in c — but they agree because they are still on a *coincident*
    path, not because the lattice says so.  The next round splits them
    (0.146059 against 0.144896) and they settle 7.4e-5 apart at 0.1419093 and
    0.1419837, flat to ~1e-8 from round six on.  A Linux runner's rhombohedral
    arm splits a little differently, so the one-round coincidence held on darwin
    and broke there, and the bar below was widened twice chasing it before
    anyone plotted the descent (runs 31973603220, 32001934722, 32008985488).
    Twelve rounds costs 3.4 s per arm and puts both arms at a stationary point,
    which is the only place "the same lattice, described twice" is a claim about
    the lattice rather than about where five stages happen to stop.
    """
    from rietx.strategy.staged import RefinementPlan, Stage

    cell = ["phases.*.cell.*", "instrument.zero_shift"]
    widths = ["instrument.profile.u", "instrument.profile.v",
              "instrument.profile.x", "instrument.profile.y",
              "phases.*.lor_size"]
    stages = [
        Stage("bkg", ["instrument.background.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("cell", cell, max_iter=80),
    ]
    for i in range(12):
        stages.append(Stage(f"profile{i + 1}", widths))
        stages.append(Stage(f"cell{i + 1}", cell, max_iter=80))
    plan = RefinementPlan(stages=stages)
    # WP-1123: the shipped convergence schedule, named rather than inherited.
    # Every stage but the last stops at 1e-6 and the last at the solver's own
    # 1e-9, which is what a user's own run does — so these numbers are the
    # ones the package actually produces.  None here would converge every
    # stage; measured cost of the schedule on this protocol is <= 0.02 esd.
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    return plan


def _lebail_corundum(symbol: str, cell: tuple[float, ...], data):
    ins = qarr_instrument()
    # the ProfileTCHZ default W is a synchrotron line (~13x too narrow here);
    # seeding it is what seed_widths does for an indexing validation
    ins.profile.w.value = 0.01
    a, b, c, alpha, beta, gamma = cell
    structure = rx.Structure(phases=[rx.Phase(
        name="corundum", space_group=symbol,
        cell=rx.Cell(a=rx.Parameter(value=a, min=1.0),
                     b=rx.Parameter(value=b, min=1.0),
                     c=rx.Parameter(value=c, min=1.0),
                     alpha=rx.Parameter(value=alpha, min=20.0, max=130.0),
                     beta=rx.Parameter(value=beta, min=20.0, max=130.0),
                     gamma=rx.Parameter(value=gamma, min=20.0, max=130.0)),
        atoms=[rx.Atom(label="X", species="Al", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0))],
        lor_size=rx.Parameter(value=0.02, min=0.0, transform="softplus"))])
    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan=_lattice_only_plan(), mode="lebail")
    return ref, result


def test_the_two_descriptions_of_the_r_lattice_refine_to_the_same_cell():
    """A refinement that WP-1036 would have mis-tied, on real certified data."""
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / "corundum.prn")

    # start both arms at the SAME physical lattice, displaced from the
    # certificate so the fit has to find its way back
    a_r0, alpha0 = rhombohedral_from_hexagonal(A_CERT, C_CERT)
    a_r_start, alpha_start = a_r0 * 1.003, alpha0 - 0.3
    a_h_start, c_h_start = hexagonal_from_rhombohedral(a_r_start, alpha_start)

    ref_r, res_r = _lebail_corundum(
        "R -3 c:R", (a_r_start,) * 3 + (alpha_start,) * 3, data)
    ref_h, res_h = _lebail_corundum(
        "R -3 c:H", (a_h_start, a_h_start, c_h_start, 90.0, 90.0, 120.0), data)

    assert res_r.status == "converged" and res_h.status == "converged"
    assert res_r.statistics.rwp < 0.25 and res_h.statistics.rwp < 0.25

    cell_r = ref_r.fitted_structure.phases[0].cell
    # 1. the ties held through the whole fit, bitwise — a = b = c and α = β = γ.
    #    Before WP-1036 c was free here, so this is the assertion that could not
    #    have been made.
    assert cell_r.a.value == cell_r.b.value == cell_r.c.value
    assert cell_r.alpha.value == cell_r.beta.value == cell_r.gamma.value

    # 2. α is genuinely refinable, and it walked back to the certificate.  The
    #    old table locked all three angles at their stored value, so α could
    #    never have left its start.
    assert abs(cell_r.alpha.value - alpha_start) > 0.2, "alpha did not refine"
    assert cell_r.alpha.value == pytest.approx(alpha0, abs=0.02)

    # 3. the hexagonal image of the rhombohedral answer is the hexagonal
    #    answer — the same lattice, described two ways, fitted independently,
    #    and compared where the comparison means something: the stationary
    #    point the plan now runs to, for the reason its docstring gives.
    #
    #    Measured 2026-08-17 (darwin/arm64) at that point: a agrees to -1.5e-7,
    #    c to +6.9e-7, c/a to 8.3e-7, both arms -326/-339 ppm from the
    #    certificate.  rel=1e-5 is ~14x above the looser of those and ~540x
    #    below the mis-tie this guards: pre-WP-1036 c never left its start,
    #    which is 5.44e-3 away in c and 1.71e-3 in a.
    #
    #    Held on Linux at the first run of this plan (nightly 32017322140,
    #    2026-08-17, [dev,jax], full suite green in 1:51:56).  That is the bar
    #    confirmed on a second platform and not the spread re-measured: a pass
    #    says the disagreement is under 1e-5, not what it is, and nothing here
    #    prints it.  The 1.72e-5 that fired three nightlies before the repair
    #    was mid-descent path divergence and is a different quantity, so it is
    #    not evidence about this one either way.  Do not widen this from a
    #    single failure without plotting the descent first; that is the mistake
    #    this test has now cost twice.
    a_h, c_h = hexagonal_from_rhombohedral(cell_r.a.value, cell_r.alpha.value)
    cell_h = ref_h.fitted_structure.phases[0].cell
    assert a_h == pytest.approx(cell_h.a.value, rel=1e-5)
    assert c_h == pytest.approx(cell_h.c.value, rel=1e-5)
    # Rwp is deliberately not an equality.  The two settings reach *different*
    # Le Bail fixed points — 4.8e-6 apart at stationarity on the 1.7.0 tree
    # (7.44e-5 on 2026-08-17), not shrinking with
    # more rounds, the rhombohedral arm the better of the two — which is a
    # finding about the extraction, not slack to be absorbed.  abs=1e-3 is ~200x
    # above it and still catches what this line is now for: an arm that fails
    # to descend, which the old one-round stopping point would show as 8e-3.
    assert res_r.statistics.rwp == pytest.approx(res_h.statistics.rwp, abs=1e-3)

    # 4. V_H = 3·V_R, the volume relation between the two descriptions
    from rietx.crystallography.lattice import cell_volume
    v_r = cell_volume(*[getattr(cell_r, n).value
                        for n in ("a", "b", "c", "alpha", "beta", "gamma")])
    assert float(cell_volume(a_h, a_h, c_h, 90.0, 90.0, 120.0)) == \
        pytest.approx(3.0 * float(v_r), rel=1e-9)

    # 5. and it is the right lattice: the same uniform d-scale systematic of
    #    this uncalibrated instrument the Rietveld arm above measures
    #    (−312/−282 ppm), here −328/−336 ppm, with c/a within 1e-5
    assert abs(a_h / A_CERT - 1.0) < 1e-3 and abs(c_h / C_CERT - 1.0) < 1e-3
    assert (c_h / a_h) / (C_CERT / A_CERT) - 1.0 == pytest.approx(0.0, abs=5e-4)

    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(res_r, path=str(out / "srm676a_rhombohedral_fit.png"))
    plot_result(res_r, path=str(out / "srm676a_rhombohedral_lowangle.png"),
                two_theta_range=(24.0, 60.0))
    plot_result(res_h, path=str(out / "srm676a_hexagonal_lebail_fit.png"))
    import matplotlib.pyplot as plt
    plt.close("all")
