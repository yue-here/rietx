"""WP-1327 acceptance, second dataset: the LaMnO₃ moment at 50 K, k = 0.

One BT-1 pattern (NIST reactor, Cu(311) monochromator, λ = 1.5403 Å) from the
GSAS-II tutorial *Magnetic-I*, vendored verbatim with the tutorial's structure
file (``tests/data/README.md``).  Every line indexes on the nuclear P n m a
cell, so the propagation vector is zero and the moment model is a magnetic
space group on that cell.  The tutorial's k-SUBGROUPSMAG step finds two
groups that index every line and let Mn carry a moment: Pn′ma′ (BNS 62.448)
and Pnma (BNS 62.441).  The protocol is the tutorial's where rietx can state
it:

1. nuclear only, from the tutorial's CIF, over its Step 2 Limits of
   6-156° 2θ, with the contaminant line at 15.69° excluded as its Step 7
   suggests: scale + 6 Chebyshev → zero → cell → u, v, w, x → coordinate
   DOFs → B_iso, cumulative.  This is the negative control;
2. Mn³⁺ carrying a moment under each group in turn, warm-started from (1):
   moment + scale + background, then everything.

The tutorial holds My at zero because the strong first line, (010), is
magnetic, and seeds Mx and Mz at 1.  Here the moment is seeded at
(1, 0, 1) μ_B and refines through its modulus and polar angle with the
azimuth held, which is the same hold: the azimuth is what moves a moment out
of the a-c plane.  The tutorial picks Pn′ma′ because it fits the pair of
lines at 33.3° and 34.4° 2θ and Pnma does not.  It quotes no moment, and no
other reference is to hand, so the suite asserts the *shape* of the answer:
a supported moment along **a**, below Mn³⁺'s spin-only ceiling, that removes
half the nuclear-only misfit, and a Pn′ma′ fit that beats the Pnma one at
that pair.

**The instrument** is read from ``gsas2_bt1_cu311.inst`` record by record.
``read_gsas_prm`` refuses the file, since its bank's first profile is GSAS
type 1, so λ comes from the ``ICONS`` line and the Gaussian widths and axial
terms from the type-3 profile, the widths converted by the measured convention
``io.recipe.GAUSS_CENTIDEG2_TO_DEG2`` (a GSAS variance in centideg² to a
Caglioti FWHM² in deg²).  The file's Lorentzian terms are zero, which a
softplus width cannot start from, so ``x`` keeps the builder's seed.

**Dispersion** is not a choice here: a neutron source has no ``dispersion``
channel (``NeutronSource`` carries one wavelength and no f′/f″).  The
convergence schedule is declared explicitly, ``intermediate_ftol=1e-6``, the
shipped value and the Cr₂WO₆ suite's.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.recipe import GAUSS_CENTIDEG2_TO_DEG2
from rietx.schemas.common import Parameter
from tests.test_acceptance_magnetic import draw

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("magnetic-lamno3")]

DATA = Path(__file__).parent / "data"


def _inst_record(key: str) -> list[float]:
    """The numbers on bank 1's ``key`` line of ``gsas2_bt1_cu311.inst``."""
    text = (DATA / "gsas2_bt1_cu311.inst").read_text(encoding="ascii")
    (line,) = [ln for ln in text.splitlines() if ln[6:12].strip() == key]
    return [float(f) for f in line[12:].split()]


#: λ from ``ICONS``; GU, GV, GW from the type-3 profile (``PRCF31``), in
#: GSAS's centideg²; S/L and H/L from its next record (``PRCF32``)
LAMBDA = _inst_record("ICONS")[0]
GU_GV_GW = tuple(_inst_record("PRCF31")[:3])
AXIAL_SL_HL = tuple(_inst_record("PRCF32")[2:4])
#: the tutorial's Step 2 Limits, and the contaminant line at 15.69° that its
#: Step 7 says neither model gives intensity to, at the width the counts show
LIMITS = (6.0, 156.0)
CONTAMINANT = (15.25, 16.05)
N_BKG = 6
#: the pair of lines the tutorial tells the two groups apart by
PAIR = (32.8, 35.0)
#: the plots' zoom: the tutorial's two regions, 10-30° and 30-55°
LOW_ANGLE = (6.0, 55.0)

PN_MA = "62.448"   # Pn′ma′, the tutorial's answer
PNMA = "62.441"    # Pnma, its rival
SPIN_ONLY_MN3 = 4.0   # gS for S = 2, μ_B

SCALE = "phases.0.scale"
BKG = [f"instrument.background.c{i}" for i in range(N_BKG)]
ZERO = "instrument.zero_shift"
CELL = "phases.0.cell.*"
WIDTHS = [f"instrument.profile.{k}" for k in "uvwx"]
COORD = "phases.0.atoms.*.dof.*"
BISO = "phases.0.atoms.*.biso"
#: modulus and polar angle of Mn2's moment; the azimuth (dof2) is held
MOMENT = ["phases.0.atoms.1.moment.dof0", "phases.0.atoms.1.moment.dof1"]
POLAR = "phases.0.atoms.1.moment.dof1"

_B = [SCALE, *BKG]
NUCLEAR_STAGES = [
    ("scale_bkg", _B),
    ("zero", _B + [ZERO]),
    ("cell", _B + [ZERO, CELL]),
    ("widths", _B + [ZERO, CELL, *WIDTHS]),
    ("coords", _B + [ZERO, CELL, *WIDTHS, COORD]),
    ("biso", _B + [ZERO, CELL, *WIDTHS, COORD, BISO]),
]
MAGNETIC_STAGES = [
    ("moment_scale_bkg", _B + MOMENT),
    ("final", _B + MOMENT + [ZERO, CELL, *WIDTHS, COORD, BISO]),
]


def _plan(stages) -> rx.RefinementPlan:
    return rx.RefinementPlan(
        stages=[rx.Stage(name=n, turn_on=list(t), max_iter=200) for n, t in stages],
        intermediate_ftol=1e-6,
        closing_window_tol=1e-3)   # WP-2002: the shipped closing stage, named rather than inherited


def _instrument() -> rx.Instrument:
    inst = rx.Instrument.constant_wavelength_neutron(LAMBDA)
    for name, g in zip("uvw", GU_GV_GW):
        getattr(inst.profile, name).value = g * GAUSS_CENTIDEG2_TO_DEG2
    inst.geometry.axial_sl.value, inst.geometry.axial_hl.value = AXIAL_SL_HL
    inst.background.coefficients = [Parameter(value=0.0) for _ in range(N_BKG)]
    return inst


def _with_moment(structure: rx.Structure, bns: str) -> rx.Structure:
    s = structure.model_copy(deep=True)
    s.phases[0].magnetic_symmetry = bns
    mn = s.phases[0].atoms[1]
    assert mn.label == "Mn2"
    mn.moment = rx.Moment.from_values((1.0, 0.0, 1.0), "Mn3+", vary=True)
    return rx.Structure.model_validate(s.model_dump())


def _fit(structure, instrument, data, stages):
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(data, plan=_plan(stages), two_theta_limits=LIMITS)
    return ref, result


def _chi2(result, window) -> float:
    """Σ(Δ/σ)² over the fitted channels inside ``window``."""
    tt = np.asarray(result.two_theta)
    keep = (tt >= window[0]) & (tt <= window[1])
    delta = (np.asarray(result.y_obs) - np.asarray(result.y_calc)) / result.sig()
    return float(np.sum(delta[keep] ** 2))


@pytest.fixture(scope="module")
def lamno3(lamno3_nuclear):
    data, ref_nuc, nuc = (lamno3_nuclear[k] for k in ("data", "ref", "nuc"))
    draw(nuc, "lamno3_50K_nuclear", LOW_ANGLE)
    fits = {}
    for bns in (PN_MA, PNMA):
        ref, res = _fit(_with_moment(ref_nuc.structure, bns),
                        ref_nuc.instrument.model_copy(deep=True), data,
                        MAGNETIC_STAGES)
        (row,) = ref.report().magnetic
        polar = next(p for p in ref.parameters() if p.path == POLAR)
        fits[bns] = (res, row, polar)
        draw(res, f"lamno3_50K_bns{bns}", LOW_ANGLE)
    return {"nuc": nuc, **fits}


def test_the_50k_moment_is_supported_and_lies_along_a(lamno3):
    """Under Pn′ma′ the moment is measured: ~3.6 μ_B along a, far above its esd.

    Tolerances, not digits, and no reference magnitude: the tutorial quotes
    none.  |m| is held below Mn³⁺'s spin-only 4 μ_B by more than three esds
    and above 3.3 μ_B, a floor under every protocol variant measured
    (3.54-3.56 μ_B with the axial or Lorentzian widths freed or held).  The
    support ratio is held above 10, where the rule's own bar is 3.  "Along
    a" is two statements: My is exactly zero, the tutorial's hold, and the
    tutorial's "Mz is close to zero".  Since WP-1929 the fit asks the second
    itself.  The polar angle ends 0.091 rad from 90°, and moving it there, the
    rest refitted, changes χ² by 0.57 × χ²_red·f² against the one-angle cut of
    2.71 (macOS arm64).  So the angle sits at the direction the symmetry fixes,
    its column leaves the covariance, and it has no esd.  Before, it read
    0.0608 rad, and 90° was within 1.5 of it.  The moment removes about half
    of the nuclear-only misfit.
    """
    nuc = lamno3["nuc"]
    result, row, polar = lamno3[PN_MA]
    assert nuc.status == "converged" and result.status == "converged"
    assert row.ion == "Mn3+"
    assert row.supported is True, row.note
    assert row.magnitude_esd is not None
    assert row.magnitude / row.magnitude_esd > 10.0
    assert 3.3 <= row.magnitude < SPIN_ONLY_MN3 - 3.0 * row.magnitude_esd, (
        row.magnitude, row.magnitude_esd)
    mx, my, mz = row.crystalaxis
    assert abs(my) < 1e-9, row.crystalaxis
    assert abs(mx) / row.magnitude > 0.98, row.crystalaxis
    from_c = np.arccos(abs(mz) / row.magnitude)
    (passed,) = [t for t in result.stages[-1].moment_angle_tests if t.zeroed]
    assert passed.paths == [POLAR] and passed.statistic <= passed.cut
    assert polar.esd is None
    # on the profile's own scale: 90° is inside one half-width of the angle
    assert np.pi / 2 - from_c < passed.half_widths[POLAR], (
        from_c, passed.half_widths)
    assert result.statistics.rwp < 0.6 * nuc.statistics.rwp, (
        result.statistics.rwp, nuc.statistics.rwp)


def test_pn_ma_beats_pnma_at_the_tutorials_pair(lamno3):
    """Both groups carry a supported moment, and Pn′ma′ fits the data better.

    The tutorial's discrimination, on the same protocol.  Both fits give the
    magnetic (010) line its intensity, and they differ in the moment's
    direction: along a under Pn′ma′, along c under Pnma.  The direction
    changes which part of each moment is perpendicular to the scattering
    vector, and the pair at 33.3° and 34.4° 2θ is where that shows.  Both
    moments are held supported, so the comparison is between two moments and
    not between a moment and none.
    Pn′ma′ is held to under 0.85 of Pnma's Rwp (0.75 measured) and under a
    tenth of its χ² over the pair (a fortieth measured).
    """
    res_a, row_a, _ = lamno3[PN_MA]
    res_c, row_c, _ = lamno3[PNMA]
    assert res_a.status == "converged" and res_c.status == "converged"
    assert row_a.supported is True and row_c.supported is True
    assert abs(row_c.crystalaxis[2]) / row_c.magnitude > 0.98, row_c.crystalaxis
    assert res_a.statistics.rwp < 0.85 * res_c.statistics.rwp, (
        res_a.statistics.rwp, res_c.statistics.rwp)
    pair_a, pair_c = _chi2(res_a, PAIR), _chi2(res_c, PAIR)
    assert pair_a < 0.1 * pair_c, (pair_a, pair_c)
