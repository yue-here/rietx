"""Acceptance: the SRM 1976a corundum plate against its TOPAS texture (#131).

``srm1976a_corundum_xpert.xy`` is a flat, sintered NIST SRM 1976a alumina
plate on a Philips/PANalytical X'Pert with an X'Celerator, Cu Kα, 20-118.5°
2θ fitted.  A sintered disc is genuinely textured, and its solved TOPAS
refinement, ``srm1976a_corundum_xpert_pvii.inp`` (committed beside it, trimmed
as ``tests/data/README.md`` records), carries ``PO_Spherical_Harmonics(sh, 4)``
with y20 2.08901, y40 0.87393 and y43m 0.00178.  This suite compares
``Phase.texture`` (WP-1960) with those coefficients **term by term**, never
through Rwp (#131 § Acceptance).

**The conversion is measured, not assumed.**  The TOPAS Technical Reference
names Järvinen (1993) and states no normalisation.  rietx's P for one
reflection on a reflection plate (ψ = 0) is

    P_h = 1 + Σ √(4π/(2l+1)) · C_l^n · K_l^n(h)

with K orthonormal (``model/preferred_orientation``).  For n = 0 that term is
C_l^0 · P_l(cos φ).  Three readings of TOPAS's y_l0 give three ratios
C_rietx / c_TOPAS:

* Von Dreele (1997), or Järvinen's harmonics normalised to max |Y| = 1: both
  make the n = 0 term c·P_l(cos φ), so the ratio is **1** at every l;
* an orthonormal Y with no 4π/(2l+1) and y00 = 1: √((2l+1)/4π), 0.631 at
  l = 2 and 0.846 at l = 4;
* an orthonormal Y including y00 = 1/√(4π), whose constant the scale absorbs:
  √(2l+1), 2.24 and 3.00.

The fit lands on the first at both orders (``test_the_measured_ratio_
excludes_the_other_normalisations``).  It cannot tell Von Dreele from
Järvinen's max-normalised harmonics, because those agree for every n = 0 term
and differ only at n ≠ 0, by 0.679 for the n = 3 term here.  The one n ≠ 0
term, y43m, is zero within error in both codes, so neither its factor nor its
sign or azimuth convention is measured.  That waits for a forward TOPAS run
(known coefficients in, ``sh`` per reflection out; WP-1973).

Protocol, mirrored from the ``.inp`` as closely as main allows.  Every
departure is stated.

* ``start_X 20``, to the end of the scan; 11 793 channels, Poisson weights.
* The cell is **held** at a = 4.758877, c = 12.992880 Å, as the ``.inp`` holds
  it; Al z and O x held at its values.  Biso refined for both sites (TOPAS
  ``beq``).  Dispersion declared on (Cromer-Liberman), the shipped default.
* ``LP_Factor(90)``: TOPAS's ``scale_pks`` is (1 + cos²(90°)·cos²2θ) /
  (sin²θ cos θ), so **no** polarisation dependence.  rietx's K = 1 is the same
  factor.  It matters: the unpolarised K = 0.5 gives Biso −0.14 and −0.45 Å²,
  moves C2,0 by +0.017 (0.7 esd) and C4,0 by +0.052 (1.8 esd), and leaves
  C4,0 2.0 esd from TOPAS's.  Matching the protocol is what makes the
  comparison a comparison.
* ``CuKa5(0.001)``, five emission lines, against rietx's Kα1/Kα2 doublet at
  the 0.5 ratio.
* ``PVII_Peak_Type`` (six shape parameters) against TCHZ pseudo-Voigt
  (U, V, W, X, Y).  rietx has no PVII.
* ``Simple_Axial_Model`` (one parameter) against Finger-Cox-Jephcoat with
  S/L and H/L tied equal, so it is one parameter too.
* ``Absorption``, the flat-plate transparency convolution, against
  ``sample_transparency``, which is the sin 2θ position shift alone (no
  broadening); ``Specimen_Displacement`` against ``sample_displacement``.  Zero held, as the ``.inp`` holds it.
* ``bkg`` with 17 Chebyshev terms plus ``One_on_X`` against 13 Chebyshev terms.
  Declaring TOPAS's refined 1/x as a fixed curve moves C2,0 by 0.0012 and
  C4,0 by 0.0005, a twentieth of their esds.

The fit runs in about a second, so the suite is not marked slow.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion

DATA = Path(__file__).parent / "data"
PATTERN = DATA / "srm1976a_corundum_xpert.xy"
TOPAS_INP = DATA / "srm1976a_corundum_xpert_pvii.inp"

LIMITS = (20.0, 118.6)          # start_X 20; the scan ends at 118.531
A, C = 4.758877, 12.992880      # held in the .inp (no @ on a or c)
N_CHEBYSHEV = 13

#: Candidate ratios C_rietx / c_TOPAS for an n = 0 term (module docstring).
CANDIDATES = {
    "von_dreele_or_max_normalised": lambda degree: 1.0,
    "orthonormal_no_prefactor": lambda degree: math.sqrt((2 * degree + 1) / (4 * math.pi)),
    "orthonormal_with_y00": lambda degree: math.sqrt(2 * degree + 1),
}

pytestmark = pytest.mark.xdist_group("srm1976a_texture")


def _topas() -> dict[str, float]:
    """The converged values, read from the committed ``.inp``'s own record."""
    text = TOPAS_INP.read_text(encoding="ascii")
    out = {}
    for name in ("sh_c20", "sh_c40", "sh_c43m"):
        out[name] = float(re.search(rf"\b{name}\s+(-?[0-9.]+)`", text).group(1))
    out["rwp"] = float(re.search(r"\br_wp\s+([0-9.]+)", text).group(1)) / 100.0
    out["rexp"] = float(re.search(r"\br_exp\s+([0-9.]+)", text).group(1)) / 100.0
    return out


TOPAS = _topas()


def _structure(texture: bool) -> rx.Structure:
    P = rx.Parameter
    cell = rx.Cell(a=P(value=A), b=P(value=A), c=P(value=C), alpha=P(value=90.0),
                   beta=P(value=90.0), gamma=P(value=120.0))
    kw = {}
    if texture:
        kw["texture"] = rx.SphericalHarmonicTexture(order=4, coefficients={
            "c2_0": P(value=0.5), "c4_0": P(value=0.1), "c4_3": P(value=0.0)})
    return rx.Structure(phases=[rx.Phase(
        name="Al2O3", space_group="R -3 c:H", cell=cell,
        atoms=[rx.Atom(label="Al1", species="Al3+", x=P(value=0.0), y=P(value=0.0),
                       z=P(value=0.35301), biso=P(value=0.4)),
               rx.Atom(label="O1", species="O2-", x=P(value=0.30263), y=P(value=0.0),
                       z=P(value=0.25), biso=P(value=0.4))],
        **kw)])


def _instrument() -> rx.Instrument:
    P = rx.Parameter
    inst = rx.Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=240.0,
                                        ka2_ratio=0.5)
    inst.source.polarization = P(value=1.0, min=0.0, max=1.0)   # LP_Factor(90)
    # Declared, not inherited (tests/test_validation_matrix.py).  Al and O
    # sit far from any absorption edge at Cu Kα, so f' and f'' are small here.
    inst.source.dispersion = Dispersion()
    inst.background = BackgroundChebyshev(
        coefficients=[P(value=160.0)] + [P(value=0.0) for _ in range(N_CHEBYSHEV - 1)])
    inst.profile.w = P(value=0.002, min=0.0)
    inst.profile.x = P(value=0.02, min=0.0)
    return inst


def _refine(texture: bool):
    """The staged protocol: scale and background, displacement, widths, Biso,
    texture, the two aberrations, then Biso and texture together."""
    data = rx.read_pattern(PATTERN)
    ref = rx.Refinement(_structure(texture), _instrument())
    ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])
    tex = ["phases.0.texture.*"] if texture else []
    stages = [
        rx.Stage("scale_bkg", ["phases.0.scale", "instrument.background.*"]),
        rx.Stage("displacement", ["instrument.geometry.sample_displacement"]),
        rx.Stage("w", ["instrument.profile.w"]),
        rx.Stage("widths", ["instrument.profile.u", "instrument.profile.v",
                            "instrument.profile.x", "instrument.profile.y"]),
        rx.Stage("biso", ["phases.0.atoms.*.biso"]),
        *([rx.Stage("texture", tex)] if texture else []),
        rx.Stage("aberrations", ["instrument.geometry.sample_transparency",
                                 "instrument.geometry.axial_sl"]),
        rx.Stage("final", ["phases.0.atoms.*.biso", *tex]),
    ]
    # The shipped schedule, named rather than inherited (validation matrix).
    plan = rx.RefinementPlan(stages=stages, intermediate_ftol=1e-6)
    return ref.fit(data, plan=plan, two_theta_limits=LIMITS)


def _param(result, path):
    (p,) = [p for p in result.parameters if p.path == path]
    return p


@pytest.fixture(scope="module")
def textured():
    return _refine(texture=True)


@pytest.fixture(scope="module")
def untextured():
    return _refine(texture=False)


def test_the_protocol_matches_before_any_number_is_compared(textured):
    """Same channels, same weights: Rexp depends on nothing else but P."""
    st = textured.statistics
    assert textured.status == "converged"
    assert st.n_points == 11793
    assert min(textured.two_theta) >= 20.0
    assert abs(st.rexp - TOPAS["rexp"]) / TOPAS["rexp"] < 2e-3


def test_c20_and_c40_agree_with_topas_with_no_conversion(textured):
    """Ratio 1 closes both n = 0 terms inside two of rietx's own esds."""
    for path, key in (("phases.0.texture.c2_0", "sh_c20"),
                      ("phases.0.texture.c4_0", "sh_c40")):
        p = _param(textured, path)
        assert p.stderr is not None and p.stderr < 0.05, (path, p.stderr)
        assert abs(p.value - TOPAS[key]) < 2.0 * p.stderr, (path, p.value, TOPAS[key])


def test_the_measured_ratio_excludes_the_other_normalisations(textured):
    """One convention must close both terms.  Ratio 1 closes each inside two
    esds; each other candidate misses both terms by more than two, and one of
    them by more than ten (√((2l+1)/4π) is 4.4 esds off at l = 4 alone, and
    the l = 2 term is what excludes it)."""
    miss: dict[str, dict[int, float]] = {name: {} for name in CANDIDATES}
    for degree, path, key in ((2, "phases.0.texture.c2_0", "sh_c20"),
                              (4, "phases.0.texture.c4_0", "sh_c40")):
        p = _param(textured, path)
        ratio, ratio_esd = p.value / TOPAS[key], p.stderr / TOPAS[key]
        for name, f in CANDIDATES.items():
            miss[name][degree] = abs(ratio - f(degree)) / ratio_esd
    assert max(miss["von_dreele_or_max_normalised"].values()) < 2.0, miss
    for name in ("orthonormal_no_prefactor", "orthonormal_with_y00"):
        assert min(miss[name].values()) > 2.0, (name, miss)
        assert max(miss[name].values()) > 10.0, (name, miss)


def test_c43_is_zero_within_error_in_both_codes(textured):
    """So the n = 3 factor, and its sign, are not measured by this plate."""
    p = _param(textured, "phases.0.texture.c4_3")
    assert p.stderr is not None and p.stderr < 0.05
    assert abs(p.value) < 2.0 * p.stderr
    assert abs(TOPAS["sh_c43m"]) < p.stderr


def test_the_fit_reaches_topas_rwp_with_physical_displacements(textured):
    """A regression bar, not a profile claim: TCHZ against PVII, two lines
    against five."""
    assert textured.statistics.rwp < TOPAS["rwp"]
    for i in (0, 1):
        assert 0.0 < _param(textured, f"phases.0.atoms.{i}.biso").value < 2.0
    codes = {d.code for d in textured.diagnostics}
    assert "BISO_NEGATIVE" not in codes
    assert "TEXTURE_NOT_POSITIVE" not in codes


def test_without_texture_the_plate_fits_measurably_worse(textured, untextured):
    """The positive arm: the same plate and protocol with no texture."""
    t, u = textured.statistics, untextured.statistics
    assert u.rwp - t.rwp > 0.15, (u.rwp, t.rwp)
    assert u.chi2 / t.chi2 > 5.0, (u.chi2, t.chi2)
