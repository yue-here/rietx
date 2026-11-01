"""WP-0503 acceptance: Stephens anisotropic strain on real lab patterns.

Two IUCr CPD round-robin pure-phase patterns, same Philips Bragg-Brentano
instrument and protocol as ``test_acceptance_qpa_roundrobin`` (provenance in
``tests/data/README.md``):

* **brucite**, Mg(OH)₂, P-3m1 — a layered platy hydroxide, the round robin's
  own preferred-orientation specimen, and the obvious candidate for
  directional broadening;
* **corundum**, α-Al₂O₃, R-3c — the SRM 676a specimen, a well-crystallised
  isotropic control.

**What the data actually says** (measured 2026-07-27; do not read the brucite
case as a success story):

Adding the three anisotropic Stephens patterns to brucite improves Rwp from
18.62 % to 17.84 %, and that improvement passes *both* statistical tests for
the added parameters — Hamilton's R-ratio test at α = 0.05 and ΔBIC, +22.4 at
N/f² on the 1.7.0 tree (+592 at raw N).  In physical units (WP-1938) the same
TRF fit stops at max_iter at 18.09 %, and ΔBIC reads +9.2 (+392 at raw N).
Since WP-1953 the axial stage refines S/L with H/L held at 0, and on 1.9.0 the
TRF fit converges at 17.88 % from 18.64 %, ΔBIC +21.0 (+578 at raw N).  On
1.10.0, after WP-2002's width twin hold and floor removal, it converges at
18.04 %, ΔBIC +12.5 (+448 at raw N).
It is nonetheless **physically inadmissible**: the refinement drives σ²(M)
negative on 12 of the 43 fitted reflections, and the v0.5 fit stopped at
max_iter rather than converging.  σ² is a variance; a negative one is not a large
anisotropy but coefficients outside the cone, and the reflections it touches
silently get no strain broadening at all.  ``STEPHENS_STRAIN_NOT_POSITIVE``
fires, which is the whole point of having it.

That is the acceptance: a statistically justified improvement that the physics
guard rejects.  It is the same shape as the WP-0305 treatment of round-robin
sample 4 — assert the *characterisation*, including the fence firing, not an
accuracy band the data cannot support.  Anyone tempted to quote brucite S_HKL
from this package should meet this test first.

**Two corrections landed 2026-07-28 (WP-0601); the paragraph above is the
v0.5 record and the brucite half of it still stands.**

*The corundum control does not leave the cone.*  This file used to say it did,
and read that as "an unconstrained least squares leaves the cone whenever the
anisotropic directions are poorly determined, which on a nearly-isotropic
specimen is always".  That was the guard's own test misfiring, not a
measurement: it read σ² ≤ 0, and the all-zero block these runs start from gives
σ² ≡ 0 on *every* reflection, so the guard fired in each stage before the one
that frees the patterns.  Zero is on the cone, not outside it; with the
one-sided test corundum's σ²(M) is strictly positive at every stage (minimum
+4.8e3 against a maximum 1.97e6).  So the guard *does* discriminate: it fires
on brucite and stays silent on corundum.  It still is not evidence *of*
anisotropy — brucite's firing means "these coefficients are not quotable", not
"this specimen is anisotropic" — but the earlier, stronger claim that it fires
on everything was wrong.

*The cone can now be enforced, and doing so does not make the coefficients
quotable.*  ``solver="lm"`` (WP-0601) carries σ²(M) = T·θ ≥ 0 as a linear
inequality on the frozen reflection list.  A four-seed sweep of
``Stage.strain_seed`` on brucite says exactly what it buys and what it does
not:

======  ===================  ==================  ===================  ==============
seed    LM Rwp               LM σ² < 0           TRF Rwp              TRF σ² < 0
======  ===================  ==================  ===================  ==============
400     0.18619              0 of 43             0.17807              15 of 43
800     0.18417              0 of 43             0.17899              12 of 43
1600    0.18068              0 of 43             0.17820              0 of 43
3000    0.17819              0 of 43             0.17819              0 of 43
======  ===================  ==================  ===================  ==============

Measured before 1.6.0. Re-run on the 1.7.0 tree, the TRF column reads 14, 7,
0 and 0 of 43, and seed 800 gives LM 0.17946 against TRF 0.17844.  In physical
units (WP-1938) it reads 13, 7, 26 and 24, seeds 400 and 1600 stop at
max_iter, and seed 800 gives LM 0.17942 against TRF 0.18092.  On 1.9.0, after
WP-1953, it reads 15, 7, 19 and 24, every fit converges, LM holds the cone at
all four, and seed 800 gives LM 0.17995 against TRF 0.17877.  On 1.10.0 it
reads 19, 19, 19 and 17, every fit converges, and seed 800 gives LM 0.18147
against TRF 0.18042.

So: the constraint holds from **every** start, which is what it promised, and
the unconstrained driver leaves the cone from the low seeds only.  But the
objective has several local minima, and the coefficients that come back span
~100 % relative spread across these four starts under *both* drivers — the two
runs that reach Rwp 0.1782 agree with each other to 1.3 %, and the rest do not
agree with anything.  ``docs/solver-survey.md`` §E6 set the kill criterion for
exactly this case, and it is met: **enforcing the cone stops the fit being
inadmissible; it does not make brucite's S_HKL measured.**  What it does buy is
that a bad start now degrades into a worse Rwp instead of a confident
unphysical answer — which is the "never a confident wrong singleton" rule
applied to the solver.

Corundum is the control the brucite result needs to be readable: on the same
instrument and protocol the Layer-1 diagnostic reports ``detected=False`` with
a 1.5× fitted spread and R² = 0.11 against the isotropic baseline (1.9.0), so
the machine is not simply calling everything anisotropic.

It also pins which statistic to believe, and the answer moved with issue #270
(WP-1417).  At the raw channel count Hamilton's F test blesses corundum's inert
0.25 % χ² improvement just as it blesses brucite's 8.0 % one, and raw-N ΔBIC
separates them (+578 against −8.8; +592 against −15 on 1.7.0).  That read as
ΔBIC being the statistic to trust until #270 showed raw-N ΔBIC blessing a 1σ
occupancy the same way.  Both are now read at N/f², f the restricted fit's
``esd_inflation``.  There Hamilton refuses corundum too, and ΔBIC reads +21.0
for brucite against −18.0 on 1.9.0 (+12.5 against −18.1 on 1.10.0).  Brucite's block still pays for its three
parameters jointly, while three of its four S_HKL coefficients lie within 1.3σ
of zero (value/esd 0.37, −1.22, 0.40, 2.29): the ~100 % spread across starts
above, seen in one fit's esds.


Dispersion is **declined**, inherited from ``qarr_instrument`` in
``test_acceptance_qpa_roundrobin``: every number here is a differential
statement about a strain block on round-robin patterns, and it stays
comparable to the v0.3/v0.5 records that were measured without the (now
default) dispersion block.
"""

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.optimize.statistics import _chi2_absolute, effective_sample_size
from rietx.report.layer2 import delta_bic, hamilton_justified
from rietx.schemas.structure import StephensStrain
from tests.test_acceptance_qpa_roundrobin import (
    DATA,
    brucite_phase,
    corundum_phase,
    qarr_instrument,
    seed_scales,
)

OUT = Path(__file__).parent / "output"

#: brucite is strongly platy, so March-Dollase on (001) has to be in the model
#: before any width question can be asked — without it Rwp is 54 % and the
#: residual is one enormous 001 peak.
def _plan(*, texture: bool, stephens: bool) -> rx.RefinementPlan:
    stages = [
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("zero_disp", ["instrument.zero_shift",
                               "instrument.geometry.sample_displacement"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
        rx.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
    ]
    if texture:
        stages.append(rx.Stage("po", ["phases.*.preferred_orientation.r"]))
    # the Stephens patterns are freed *in* the sample-broadening stage, since a
    # block locks lor_strain and would otherwise leave the isotropic width
    # unrefined until the moment four correlated patterns turn on at once
    # (`RefinementPlan.lab_sample_refine` does the same)
    broadening = ["phases.*.lor_size", "phases.*.lor_strain",
                  "phases.*.gauss_size", "phases.*.gauss_strain"]
    if stephens:
        broadening.append("phases.*.microstrain.dof.*")
    stages.append(rx.Stage("sample_broadening", broadening,
                           seed=1e-4, strain_seed=800.0))
    stages += [
        rx.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl"]),
        rx.Stage("biso", ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]),
    ]
    plan = rx.RefinementPlan(stages=stages)
    # WP-1123: the shipped convergence schedule, named rather than inherited.
    # Every stage but the last stops at 1e-6 and the last at the solver's own
    # 1e-9, which is what a user's own run does — so these numbers are the
    # ones the package actually produces.  None here would converge every
    # stage; measured cost of the schedule on this protocol is <= 0.02 esd.
    plan.intermediate_ftol = 1e-6
    # No closing stage here (WP-2002), declared rather than inherited.  The
    # suite pins TRF's unconstrained answer, and under TRF the closing stage
    # stops brucite where one S_HKL's esd collapses (t = -268 against -1.22),
    # while LM is unaffected; the iso/aniso comparison needs both fits on one
    # window setting, so the whole module declines it.
    plan.closing_window_tol = None
    return plan


def _fit(name: str, phase: rx.Phase, plan: rx.RefinementPlan, tag: str,
         *, solver: str | None = None):
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / f"{name}.prn")
    structure = rx.Structure(phases=[phase])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)
    ref = (rx.Refinement(structure, ins) if solver is None
           else rx.Refinement(structure, ins, solver=solver))
    result = ref.fit(data, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"stephens_{tag}.png"))
    result.plot(path=str(OUT / f"stephens_{tag}_lowangle.png"),
                two_theta_range=(15.0, 60.0))
    import matplotlib.pyplot as plt

    plt.close("all")
    return ref, result


def _fit_with_solver(name: str, phase: rx.Phase, plan: rx.RefinementPlan,
                     tag: str, *, solver: str):
    """:func:`_fit` with the driver selectable (WP-0601)."""
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / f"{name}.prn")
    structure = rx.Structure(phases=[phase])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)
    ref = rx.Refinement(structure, ins, solver=solver, history=False)
    result = ref.fit(data, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"stephens_{tag}.png"))
    result.plot(path=str(OUT / f"stephens_{tag}_lowangle.png"),
                two_theta_range=(15.0, 60.0))
    import matplotlib.pyplot as plt

    plt.close("all")
    return ref, result


def _sigma2_of(ref) -> np.ndarray:
    """σ²(M) on the last stage's frozen reflection list."""
    from rietx.crystallography.stephens import S_NAMES, sigma2_m

    block = ref.fitted_structure.phases[0].microstrain
    s = np.array([getattr(block, n).value for n in S_NAMES])
    return np.asarray(sigma2_m(ref._model.phases[0].strain_monomials, s))


def _information(restricted, full):
    """``(n_added, {"raw": (ΔBIC, Hamilton), "eff": (…)})`` for a nested pair.

    Not ``report.compare_freed``: the block locks ``lor_strain`` (its
    isotropic direction), so the path sets are not nested although the models
    are.  ``Statistics.chi2`` is reduced, so each is taken back to Σw·Δ² at its
    own N − P first (``_chi2_absolute``), and "eff" charges N/f² with the
    restricted fit's f (WP-1417).
    """
    rs, fs = restricted.statistics, full.statistics
    n, k = rs.n_points, fs.n_free_parameters - rs.n_free_parameters
    chi2_r, chi2_f = _chi2_absolute(rs), _chi2_absolute(fs)
    counts = {"raw": None, "eff": effective_sample_size(n, rs.esd_inflation)}
    return k, {label: (delta_bic(chi2_r, chi2_f, n, k, n_effective=n_eff),
                       hamilton_justified(chi2_r, chi2_f, n, rs.n_free_parameters,
                                          k, n_effective=n_eff))
               for label, n_eff in counts.items()}


def _with_block(phase: rx.Phase) -> rx.Phase:
    """An all-zero block: legal (it is the exact identity) and seeded by the
    stage, which is the path a user who has not chosen a starting strain takes."""
    phase.microstrain = StephensStrain.from_values([0.0] * 15)
    return phase


#: Three fits, each of which this module used to run twice.  ``brucite_aniso_trf``
#: is the one worth naming: the anisotropic brucite fit and the "unconstrained
#: control" for the LM test below are the same computation under two names.
#: Its fixture names ``solver="trf"``, because both tests assert the point
#: where the unconstrained driver leaves the cone.  The default driver is LM
#: since WP-1938, and it holds the cone.  The LM fit stays unshared, as the one
#: genuinely different run in the file.
@pytest.fixture(scope="module")
def brucite_iso():
    return _fit("brucite", brucite_phase(textured=True),
                _plan(texture=True, stephens=False), "brucite_iso")


@pytest.fixture(scope="module")
def brucite_aniso_trf():
    return _fit("brucite", _with_block(brucite_phase(textured=True)),
                _plan(texture=True, stephens=True), "brucite_aniso",
                solver="trf")


@pytest.fixture(scope="module")
def corundum_plain():
    return _fit("corundum", corundum_phase(),
                _plan(texture=False, stephens=False), "corundum")


@pytest.mark.slow
@pytest.mark.xdist_group("stephens-brucite")
def test_brucite_improvement_is_justified_but_leaves_the_physical_cone(
        brucite_iso, brucite_aniso_trf):
    iso_ref, iso = brucite_iso
    ani_ref, ani = brucite_aniso_trf

    # the March-Dollase habit is the one WP-0310 measured on the same material
    assert iso_ref.fitted_structure.phases[0].preferred_orientation.r.value \
        == pytest.approx(0.65, abs=0.05)

    # 1. the improvement is real and passes both tests for the added
    #    parameters at N/f² (measured ΔBIC +12.5 at N_eff 473, +448 at raw N
    #    on 1.10.0; +21.0 and +578 on 1.9.0; +9.2 and +392 on 1.8.0, before WP-1953's axial limit;
    #    +22.4 and +592 on 1.7.0, before WP-1938's physical units)
    assert iso.statistics.rwp == pytest.approx(0.1855, abs=0.01)
    assert ani.statistics.rwp == pytest.approx(0.1790, abs=0.01)
    assert ani.statistics.rwp < iso.statistics.rwp
    n_added, info = _information(iso, ani)
    assert n_added == 3          # P-3m1 has 4 patterns, one of them isotropic
    bic, hamilton = info["eff"]
    assert bic > 0.0 and hamilton
    # …jointly: at most one of the four S_HKL coefficients lies 2σ from zero
    # (value/esd 0.37, −1.22, 0.40, 2.29 on 1.9.0), so the data measure the block and
    # not its coefficients.  From zero, because the isotropic fit has no block
    t = [p.value / p.stderr for p in ani.parameters
         if ".microstrain.dof." in p.path and p.stderr]
    assert len(t) == 4 and sum(abs(x) >= 2.0 for x in t) <= 1

    # 2. …and is physically inadmissible all the same.  This is the assertion
    #    the WP exists to make: Rwp and the information criteria cannot see the
    #    cone, and the guard can.
    fired = [d for d in ani.diagnostics if d.code == "STEPHENS_STRAIN_NOT_POSITIVE"]
    assert fired, "the out-of-cone refinement was not reported"
    assert fired[-1].where == ["phases.0.microstrain"]
    assert not [d for d in iso.diagnostics if d.code == "STEPHENS_STRAIN_NOT_POSITIVE"]

    # the offending direction: hk0 is pushed to zero strain while 00l broadens
    strain = ani_ref.report().strain[0]
    assert strain.broadest_hkl[:2] == (0, 0)
    assert strain.anisotropy > 3.0


@pytest.mark.slow
@pytest.mark.xdist_group("stephens-corundum")
def test_corundum_is_reported_isotropic(corundum_plain):
    """The control: a well-crystallised specimen on the same instrument and
    protocol must come back isotropic, or the brucite result means nothing."""
    ref, result = corundum_plain
    assert result.statistics.rwp == pytest.approx(0.144, abs=0.01)
    strain = ref.report().strain[0]
    assert not strain.detected
    assert strain.r2 < 0.5              # nothing directional beyond isotropic
    # No bar on ``strain.anisotropy``: the ratio of an *insignificant*
    # diagnostic fit (r² 0.079) is noise, and it rode the instrument/specimen
    # split of the Lorentzian width (~1.9, 2.02 after WP-1112, 4.51 after
    # WP-1930).  WP-2002's width twin hold fixed that split at the instrument's
    # stage-start Y, a reflection's specimen width then clips to zero, and the
    # ratio is infinite (quoted as 1e6, forwarded to WP-2004).  The isotropic
    # verdict is carried by ``detected`` and ``r2`` above.
    assert strain.n_patterns == 4       # R-3c → Laue -3m
    assert strain.n_reflections_used > 40


@pytest.mark.slow
@pytest.mark.xdist_group("stephens-corundum")
def test_corundum_block_is_inert_and_hamilton_blesses_it_only_at_raw_n(
        corundum_plain):
    """Freeing the Stephens patterns on an isotropic specimen must be inert,
    and both tests must say so at N/f².

    On 7251 channels Hamilton's F test at the raw count blesses corundum's
    0.25 % χ² improvement at α = 0.05, exactly as it blesses brucite's 8.0 %
    one (1.9.0).  With N that large its threshold sits below anything
    physically meaningful.  This test used to read that as ΔBIC being the
    statistic to trust, because raw-N ΔBIC refuses corundum (−15 on 1.7.0,
    −8.8 on 1.9.0).  Issue #270 showed raw-N ΔBIC blessing a 1σ occupancy the
    same way, so both tests are read at N/f² now (WP-1417), and there both
    refuse (ΔBIC −18.0).  Read it as a statement about the tests, not about
    corundum.
    """
    plain_ref, plain = corundum_plain
    # The block's last stage stopped on its 100-iteration budget, and the
    # raw-N verdict below then read wherever it stopped: 0.018 % of χ² above
    # Hamilton's line on darwin/arm64, below it on Linux x86-64 once the FCJ
    # kernels' exp moved a last bit there (WP-1940).  Converged, the margin is
    # 0.052 % on darwin/arm64 and 0.057 % on x86-64, 0.005 % apart.
    plan = _plan(texture=False, stephens=True)
    plan.stages[-1].max_iter = 1000
    block_ref, block = _fit("corundum", _with_block(corundum_phase()), plan,
                            "corundum_aniso")
    assert block.status == "converged", "a verdict read off a truncated fit"

    def c_over_a(r):
        cell = r.fitted_structure.phases[0].cell
        return cell.c.value / cell.a.value

    # the certificate-grade quantity does not move
    assert c_over_a(block_ref) == pytest.approx(c_over_a(plain_ref), rel=1e-4)
    assert block.statistics.rwp == pytest.approx(plain.statistics.rwp, abs=2e-3)

    n_added, info = _information(plain, block)
    assert n_added == 3
    assert info["raw"][1]                    # raw N: Hamilton blesses it
    bic, hamilton = info["eff"]
    assert bic < 0.0 and not hamilton

    # **Corrected 2026-07-28 (WP-0601).**  This used to assert that the cone
    # guard fires on corundum too, and read that as "an unconstrained least
    # squares walks out of the cone whenever the anisotropic directions are
    # poorly determined, which on a nearly-isotropic specimen is *always*".
    # That was an artefact of the guard's own test, not a measurement: it read
    # σ² ≤ 0, and the all-zero block every one of these runs starts from gives
    # σ² ≡ 0 on every reflection, so the guard fired in each stage *before* the
    # one that frees the patterns.  Re-measured with the corrected one-sided
    # test (zero is on the cone, not outside it), corundum's σ²(M) is strictly
    # positive at every stage — minimum +4.8e3 against a maximum 1.97e6 — so
    # the isotropic control never leaves the cone at all.
    assert not [d for d in block.diagnostics
                if d.code == "STEPHENS_STRAIN_NOT_POSITIVE"]
    assert np.isfinite(block.statistics.rwp)
    # …while the diagnostic, which is not fitting free parameters, stays quiet
    assert not block_ref.report().strain[0].detected


@pytest.mark.slow
def test_constrained_solver_keeps_brucite_inside_the_cone():
    """WP-0601's headline, and it is invisible in Rwp — deliberately so.

    ``solver="lm"`` carries σ²(M) = T·θ ≥ 0 as a linear inequality on the
    frozen reflection list, which is a thing no box bound and therefore no
    ``scipy.optimize.least_squares`` call can express.  The comparison that
    matters is not Δ Rwp but *how many reflections the answer is unphysical
    on*.  On 1.7.0 the constrained fit was the worse of the two by Rwp at this
    seed.  In physical units (WP-1938) TRF stopped at max_iter above it, and
    since WP-1953's axial limit it converges below it again:

    ==================  ===========  ===========  ===========  ===================
    brucite, seed 800   Rwp, 1.7.0   Rwp, 1.8     Rwp, 1.9     reflections σ² < 0
    ==================  ===========  ===========  ===========  ===================
    TRF, unconstrained  17.84        18.09        17.88        7 of 43
    LM, cone enforced   17.95        17.94        18.00        0 of 43
    ==================  ===========  ===========  ===========  ===================

    On 1.10.0 TRF reads 18.04 with 19 of 43 reflections out of the cone, and LM
    18.15 with none.

    On 1.7.0 a fit inadmissible on 7 of its 43 reflections had the lower Rwp,
    and it was still not the better fit: its S_HKL cannot be quoted.  Same
    shape as the v0.5 method result — a correction that is right can move Rwp
    the wrong way — which is why every assertion below is about the cone and
    the guard rather than the residual.

    Do not read this as "the constrained solver measures brucite's strain":
    the module docstring's seed sweep shows the coefficients still span ~100 %
    across starting seeds under both drivers.  What is bought here is that the
    answer cannot come back unphysical, not that it comes back determined.
    """
    ref, result = _fit_with_solver("brucite", _with_block(brucite_phase(textured=True)),
                                   _plan(texture=True, stephens=True),
                                   "brucite_cone_lm", solver="lm")

    from rietx.strategy.staged import STEPHENS_CONE_TOL

    sigma2 = _sigma2_of(ref)
    # on the cone means within the guard's tolerance: since WP-1938 D8 the
    # step lands on the face exactly, so a reflection there reads a rounding
    # either side of zero (measured -6.5e-16 of the largest σ²)
    out = sigma2 < -STEPHENS_CONE_TOL * np.max(np.abs(sigma2))
    assert not out.any(), f"{int(out.sum())} reflections left the cone"
    assert not [d for d in result.diagnostics
                if d.code == "STEPHENS_STRAIN_NOT_POSITIVE"]
    assert result.status == "converged"
    # the constrained optimum is pushed toward the face: the reflections the
    # unconstrained fit drives negative sit far below the block's scale once
    # the physics is enforced.  Before WP-1112 the minimum landed numerically
    # *on* the face (< 1e-4 of max); at the area-criterion windows the same
    # fit stops slightly interior (measured 1.3e-3 of max, with the
    # unconstrained cone count down 10+ → 7 in the same direction), so the
    # bar states the separation without demanding an exact active constraint.
    # Since WP-1938 D8 the step holds the cone exactly and the fit ends on the
    # face again
    assert sigma2.min() < 5e-3 * sigma2.max()
    # …and it costs Rwp, which is the point of not judging this by Rwp
    assert 0.17 < result.statistics.rwp < 0.20


@pytest.mark.slow
@pytest.mark.xdist_group("stephens-brucite")
def test_unconstrained_solver_leaves_the_cone_on_the_same_data(brucite_aniso_trf):
    """The control for the test above: same data, same plan, default driver.

    That default driver *is* TRF, so this is literally the anisotropic brucite
    fit of the first test in this module, and it is shared rather than re-run.
    """
    ref, result = brucite_aniso_trf
    sigma2 = _sigma2_of(ref)
    # ≥ 10 before WP-1112; the area-criterion windows moved the converged
    # block and 7 reflections left the cone on 1.9.0, 19 on 1.10.0 — the claim is that the
    # unconstrained optimum genuinely wants negative σ², and it still does
    assert (sigma2 < 0.0).sum() >= 5
    assert [d for d in result.diagnostics
            if d.code == "STEPHENS_STRAIN_NOT_POSITIVE"]
