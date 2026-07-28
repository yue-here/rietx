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
18.55 % to 17.90 %, and that improvement passes *both* statistical tests for
the added parameters — Hamilton's R-ratio test at α = 0.05 and ΔBIC = +488.
It is nonetheless **physically inadmissible**: the refinement drives σ²(M)
negative on 12 of the 43 fitted reflections, and the fit stops at max_iter
rather than converging.  σ² is a variance; a negative one is not a large
anisotropy but coefficients outside the cone, and the reflections it touches
silently get no strain broadening at all.  ``STEPHENS_STRAIN_NOT_POSITIVE``
fires, which is the whole point of having it.

That is the acceptance: a statistically justified improvement that the physics
guard rejects.  It is the same shape as the WP-0305 treatment of round-robin
sample 4 — assert the *characterisation*, including the fence firing, not an
accuracy band the data cannot support.  Anyone tempted to quote brucite S_HKL
from this package should meet this test first.

The corundum control shows the guard is not brucite-specific: an unconstrained
least squares leaves the cone whenever the anisotropic directions are poorly
determined, which on a nearly-isotropic specimen is *always*.  So
``STEPHENS_STRAIN_NOT_POSITIVE`` reads as "do not quote these coefficients" —
correct in both cases — and never as evidence *of* anisotropy.  Keeping a
refinement inside the cone needs an inequality-constrained solve, which this
package does not have (the constraint is linear in the DOFs: σ²(M) = T·θ ≥ 0
on the frozen reflection list, so a bounded/constrained minimiser could carry
it directly).

Corundum is the control the brucite result needs to be readable: on the same
instrument and protocol the Layer-1 diagnostic reports ``detected=False`` with
a 1.6× fitted spread and R² = 0 against the isotropic baseline, so the machine
is not simply calling everything anisotropic.

It also pins which statistic to believe.  Hamilton's F test blesses corundum's
inert 0.13 % χ² improvement just as it blesses brucite's 6.9 % one — on 7251
channels its threshold sits below anything physically meaningful.  ΔBIC
separates the two by two orders of magnitude (+488 vs −17), because its ln(N)
penalty grows with the channel count.  Quote ΔBIC when deciding whether a
Stephens block earns its parameters on a lab pattern.
"""

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.report.layer2 import delta_bic, hamilton_justified
from pxrdref.schemas.structure import StephensStrain
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
def _plan(*, texture: bool, stephens: bool) -> pr.RefinementPlan:
    stages = [
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("zero_disp", ["instrument.zero_shift",
                               "instrument.geometry.sample_displacement"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
    ]
    if texture:
        stages.append(pr.Stage("po", ["phases.*.preferred_orientation.r"]))
    # the Stephens patterns are freed *in* the sample-broadening stage, since a
    # block locks lor_strain and would otherwise leave the isotropic width
    # unrefined until the moment four correlated patterns turn on at once
    # (`RefinementPlan.lab_sample_refine` does the same)
    broadening = ["phases.*.lor_size", "phases.*.lor_strain",
                  "phases.*.gauss_size", "phases.*.gauss_strain"]
    if stephens:
        broadening.append("phases.*.microstrain.dof.*")
    stages.append(pr.Stage("sample_broadening", broadening,
                           seed=1e-4, strain_seed=800.0))
    stages += [
        pr.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl"]),
        pr.Stage("biso", ["phases.0.atoms.0.biso", "phases.0.atoms.1.biso"]),
    ]
    return pr.RefinementPlan(stages=stages)


def _fit(name: str, phase: pr.Phase, plan: pr.RefinementPlan, tag: str):
    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = pr.read_pattern(DATA / f"{name}.prn")
    structure = pr.Structure(phases=[phase])
    ins = qarr_instrument()
    seed_scales(structure, ins, data)
    ref = pr.Refinement(structure, ins)
    result = ref.fit(data, plan=plan)
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"stephens_{tag}.png"))
    result.plot(path=str(OUT / f"stephens_{tag}_lowangle.png"),
                two_theta_range=(15.0, 60.0))
    import matplotlib.pyplot as plt

    plt.close("all")
    return ref, result


def _with_block(phase: pr.Phase) -> pr.Phase:
    """An all-zero block: legal (it is the exact identity) and seeded by the
    stage, which is the path a user who has not chosen a starting strain takes."""
    phase.microstrain = StephensStrain.from_values([0.0] * 15)
    return phase


@pytest.mark.slow
def test_brucite_improvement_is_justified_but_leaves_the_physical_cone():
    iso_ref, iso = _fit("brucite", brucite_phase(textured=True),
                        _plan(texture=True, stephens=False), "brucite_iso")
    ani_ref, ani = _fit("brucite", _with_block(brucite_phase(textured=True)),
                        _plan(texture=True, stephens=True), "brucite_aniso")

    # the March-Dollase habit is the one WP-0310 measured on the same material
    assert iso_ref.fitted_structure.phases[0].preferred_orientation.r.value \
        == pytest.approx(0.65, abs=0.05)

    # 1. the improvement is real and passes both tests for the added parameters
    assert iso.statistics.rwp == pytest.approx(0.1855, abs=0.01)
    assert ani.statistics.rwp == pytest.approx(0.1790, abs=0.01)
    assert ani.statistics.rwp < iso.statistics.rwp
    n_added = ani.statistics.n_free_parameters - iso.statistics.n_free_parameters
    assert n_added == 3          # P-3m1 has 4 patterns, one of them isotropic
    assert hamilton_justified(iso.statistics.chi2, ani.statistics.chi2,
                              iso.statistics.n_points,
                              iso.statistics.n_free_parameters, n_added)
    assert delta_bic(iso.statistics.chi2, ani.statistics.chi2,
                     iso.statistics.n_points, n_added) > 100.0

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
def test_corundum_is_reported_isotropic():
    """The control: a well-crystallised specimen on the same instrument and
    protocol must come back isotropic, or the brucite result means nothing."""
    ref, result = _fit("corundum", corundum_phase(),
                       _plan(texture=False, stephens=False), "corundum")
    assert result.statistics.rwp == pytest.approx(0.144, abs=0.01)
    strain = ref.report().strain[0]
    assert not strain.detected
    assert strain.r2 < 0.5              # nothing directional beyond isotropic
    assert strain.anisotropy < 2.0
    assert strain.n_patterns == 4       # R-3c → Laue -3m
    assert strain.n_reflections_used > 40


@pytest.mark.slow
def test_corundum_block_is_inert_and_bic_says_so_where_hamilton_does_not():
    """Freeing the Stephens patterns on an isotropic specimen must be inert —
    and the *statistic* that says so is ΔBIC, not Hamilton.

    On 7251 channels Hamilton's F test blesses corundum's 0.13 % χ²
    improvement at α = 0.05, exactly as it blesses brucite's 6.9 % one: with N
    that large the F threshold sits at a fractional improvement smaller than
    anything physically meaningful.  ΔBIC separates them by two orders of
    magnitude (+488 vs −17, i.e. BIC *rejects* the corundum patterns), because
    its ln(N) penalty grows with the channel count while Hamilton's does not.
    Read that as a statement about the tests, not about corundum.
    """
    plain_ref, plain = _fit("corundum", corundum_phase(),
                            _plan(texture=False, stephens=False), "corundum")
    block_ref, block = _fit("corundum", _with_block(corundum_phase()),
                            _plan(texture=False, stephens=True), "corundum_aniso")

    def c_over_a(r):
        cell = r.fitted_structure.phases[0].cell
        return cell.c.value / cell.a.value

    # the certificate-grade quantity does not move
    assert c_over_a(block_ref) == pytest.approx(c_over_a(plain_ref), rel=1e-4)
    assert block.statistics.rwp == pytest.approx(plain.statistics.rwp, abs=2e-3)

    n_added = block.statistics.n_free_parameters - plain.statistics.n_free_parameters
    assert n_added == 3
    assert hamilton_justified(plain.statistics.chi2, block.statistics.chi2,
                              plain.statistics.n_points,
                              plain.statistics.n_free_parameters, n_added)
    assert delta_bic(plain.statistics.chi2, block.statistics.chi2,
                     plain.statistics.n_points, n_added) < 0.0

    # The cone guard fires here too — and that is the point of asserting it.
    # An unconstrained least squares walks out of the cone whenever the
    # anisotropic directions are poorly determined, which on a nearly-isotropic
    # specimen is *always*.  So the guard means "do not quote these
    # coefficients", which is right in both cases; it is not evidence of
    # anisotropy, and nothing in this package should read it as such.
    assert [d for d in block.diagnostics
            if d.code == "STEPHENS_STRAIN_NOT_POSITIVE"]
    assert np.isfinite(block.statistics.rwp)
    # …while the diagnostic, which is not fitting free parameters, stays quiet
    assert not block_ref.report().strain[0].detected
