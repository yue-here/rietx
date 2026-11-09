"""Acceptance: the IUCr CPD Rietveld round robin on PbSO₄ (Hill 1992), WP-1943.

Hill, R. J. (1992), *J. Appl. Cryst.* **25**, 589–610, publishes the
inter-laboratory spread of Rietveld *parameters* on one dataset: one PbSO₄
specimen, one D1A neutron pattern and one Cu Kα Bragg–Brentano pattern, which
23 participants refined 18 times (X-ray) and 20 times (neutron) with 11
programs; the weighted means use 16 and 17 of those values (Table 7).  That
table gives, for the cell, every coordinate and every B, the participants'
**range** and their **weighted mean** with σ_ext, the esd of that mean from
the agreement among them (eq. 2, p. 603).
The two patterns are the two histograms of ``tests/data/gsas2_pbso4.gpx``,
read through the ``gsas2_gpx`` pattern reader (whose σ = 1/√w is checked against
GSAS-II's stored Rwp in ``tests/test_projects_gsas2.py``); the published values
are ``tests/data/hill1992_pbso4_round_robin.json``, each row citing its page.

**The gate is the envelope the participants bracket, and the spread is
reported** (root ``CLAUDE.md``, WP-1306).  Three bars, every number in them
the paper's:

1. **Every Table 7 value lies inside the participants' range** for its
   radiation — 19 of 19, X-ray and neutron.
2. **|value − weighted mean| < 3 spreads**, where a spread is σ_ext·√n, Hill's
   esd of the mean scaled back to one refinement (n = 16 X-ray, 17 neutron;
   Table 7's footnote).  Why 3: σ_ext·√n is the standard deviation of the
   participants' own values, so a fit drawn from their distribution would land
   beyond 3 SD on any one of 19 parameters with probability
   1 − (1 − 0.0027)¹⁹ ≈ 5 %.  A tighter bar would fail a typical participant;
   a looser one would pass a value no participant reported.
3. **Rwp and GoF lie inside Table 5's participant ranges** (p. 595,
   background included; GoF is Rwp/Rexp, unsquared, as Hill standardises it on
   p. 598 and as ``Statistics.gof`` computes it).  A ceiling, not a validation.

**What is not claimed.**  Esd calibration: Hill's √ℜ is one dataset refined
many ways, not replicate measurements (his footnote, p. 606), so no esd here
is compared with σ_ext.  Nor is the single-crystal value a gate: Hill uses it
as "true" (Table 7's second footnote) but notes the single-crystal cell is
only accurate enough to set a diffractometer (p. 600), and the neutron cell is
off it by the wavelength error below.

**The protocol, frozen here and declared rather than inherited.**  Start: the
single-crystal model Hill tabulates (Miyake, Minato, Morikawa & Iwai 1978,
Table 7's single-crystal column; B as given, the equivalent isotropic value).
``mccusker_structural`` with the shipped convergence schedule, a 6-term
Chebyshev background (Hill traces bad X-ray B's to fewer than 3 or more
than 6 terms, p. 607), the TCH pseudo-Voigt, isotropic B, the zero refined and no
displacement.

* **Neutron**: λ = 1.909 Å, the wavelength the participants were given
  (p. 603); the full 10–155.85° range (Hill traces bad B's to an upper
  limit of 125° or 132°, p. 607); σ² = y/N from the file, the N/Y weighting Hill calls
  correct (p. 595); no axial asymmetry term in the gated arm, the nearer
  rietx counterpart of the round robin's majority practice (Rietveld's
  empirical function shifts a peak's base and leaves its maximum, p. 600),
  and the physical model as the separate arm 4 below.
* **X-ray**: Cu Kα1/Kα2 at the package's anode preset with the Kα2 ratio held
  at its ideal 0.5 and the graphite diffracted-beam monochromator at
  2θ_m = 26.6°, whose polarization cos²2θ_m = 0.7995 sits within 0.0003 of
  the ideal 0.7998 Hill names (p. 595); 18–159.975°, because below 18° a 1° slit over a 20 mm
  specimen does not intercept the whole beam (p. 594).  Anomalous dispersion
  is applied (declared below): Pb's L edges sit near 0.95 Å, well short of
  Cu Kα, so the tabulated f′/f″ answer.

Two of Hill's qualitative findings are asserted on top, each as he states it:

4. **A physical axial-divergence model raises the neutron cell towards the
   X-ray cell** (p. 605: the four participants using Simpson's-rule detector-
   height asymmetry, Howard 1982, reported larger neutron cells).  rietx's
   counterpart is the FCJ axial model, freed here as GSAS-II's single SH/L is
   (S/L tied to H/L).
5. **The joint fit measures a neutron wavelength above the nominal 1.909 Å**
   (p. 605: "closer to 1.912 Å" by back-calculation).  The band is Hill's own
   arithmetic, not ours: λ = 1.909 · (X-ray mean cell) / (neutron cell), taken
   over every neutron cell edge the participants reported (Table 7's neutron
   range), which spans 1.9108–1.9129 Å.

**Measured on this tree (2026-11-09, darwin/arm64, ``[dev]``)** — neutron:
Rwp 4.27 %, GoF 2.20, 19/19 inside, worst 1.52 spreads (O3 x); X-ray: Rwp
9.36 %, GoF 1.94, 19/19 inside, worst 1.26 spreads (B of O1); axial arm: each
edge up 0.08 %, still 19/19 inside (b and c 5.5 spreads above the mean, as
Hill's Simpson's-rule participants were); joint λ_N 1.91252(5) Å in the band
1.91083–1.91290 Å.  Each fit is ``usable`` with no error-level code; the
codes, verbatim, and what was done about each:

* ``BACKGROUND_ABSORPTION`` (warning), every fit: six Chebyshev terms can
  mimic part of the scale (R² 0.29, neutron) and of Pb's B (0.27 neutron,
  0.54 X-ray).  Accepted: it is the trade Hill's 3–6-term finding describes,
  and the B values it touches stay inside the participants' range, which is
  all that is claimed of them.
* ``RESOLUTION_UNCONSTRAINED`` (warning), X-ray: U, V, W refined on a
  pattern whose Lorentzian part dominates — Hill finds these X-ray peaks about
  80 % Lorentzian (p. 599).  Accepted: no width is claimed.
* ``CAPILLARY_OFFSET_UNAVAILABLE`` (info), neutron: the D1A can's goniometer
  radius is not stated, so the capillary offsets stay at zero.  Accepted: the
  zero is refined, and no offset is claimed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import PLAN_PRESETS, Stage

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
GPX = DATA / "gsas2_pbso4.gpx"
HILL = json.loads((DATA / "hill1992_pbso4_round_robin.json").read_text(encoding="utf-8"))
TABLE7 = {row["key"]: row for row in HILL["table7"]}
N_DETERMINATIONS = HILL["determinations"]          # 16 X-ray, 17 neutron

#: The neutron wavelength the participants were given (Hill 1992, p. 603).
LAMBDA_NEUTRON = 1.909
NEUTRON_LIMITS = (10.0, 155.85)                     # the whole pattern
XRAY_LIMITS = (18.0, 159.975)                       # Hill p. 594: full beam from 18°
#: Graphite (002) at Cu Kα; cos²2θ_m = 0.7995, against Hill's ideal 0.7998 (p. 595).
MONOCHROMATOR_TWO_THETA = 26.6
BACKGROUND_TERMS = 6                                # Hill p. 607: 3 to 6 terms
SPREAD_BAR = 3.0                                    # module docstring, bar 2

ATOMS = ("Pb", "S", "O1", "O2", "O3")
SPECIES = {"Pb": "Pb", "S": "S", "O1": "O", "O2": "O", "O3": "O"}

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("pbso4-round-robin")]


def _single_crystal_structure() -> Structure:
    """Hill's Table 7 single-crystal column, in P n m a: Pb, S, O1 and O2 on
    the mirror at y = ¼, O3 general."""
    sc = {key: row["single_crystal"]["value"] for key, row in TABLE7.items()}
    return Structure(phases=[Phase(
        name="PbSO4", space_group="P n m a",
        cell=Cell(a=P(value=sc["cell.a"]), b=P(value=sc["cell.b"]),
                  c=P(value=sc["cell.c"]), alpha=P(value=90.0),
                  beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[Atom(label=a, species=SPECIES[a], x=P(value=sc[f"{a}.x"]),
                    y=P(value=sc.get(f"{a}.y", 0.25)), z=P(value=sc[f"{a}.z"]),
                    biso=P(value=sc[f"{a}.biso"])) for a in ATOMS])])


def _seed_widths(instrument: rx.Instrument, data) -> None:
    """The skill's width seed (§1): W ≈ (0.6·H)², X ≈ 0.6·H from the median
    FWHM of the twelve strongest picked peaks."""
    import numpy as np

    strong = sorted(rx.pick_peaks(data, instrument).peaks,
                    key=lambda p: -p.intensity)[:12]
    h = float(np.median([p.fwhm for p in strong]))
    instrument.profile.w.value, instrument.profile.x.value = (0.6 * h) ** 2, 0.6 * h


def _neutron(data, *, axial: bool = False) -> rx.Instrument:
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA_NEUTRON)
    ins.background = BackgroundChebyshev.with_terms(BACKGROUND_TERMS)
    # ``NeutronSource.dispersion`` is structurally None (f'/f" is an X-ray
    # core-level effect): nothing to declare on this arm
    assert ins.source.dispersion is None
    if axial:
        ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = 0.01
    _seed_widths(ins, data)
    return ins


def _xray(data) -> rx.Instrument:
    ins = rx.Instrument.bragg_brentano(
        radiation="CuKa", monochromator_two_theta=MONOCHROMATOR_TWO_THETA,
        ka2_ratio=0.5)
    # Declared rather than inherited (tests/test_validation_matrix.py): f'/f" at
    # Cu Kα are applied, the package default, since no edge of Pb, S or O lies
    # near 1.54 Å
    ins.source.dispersion = Dispersion()
    ins.background = BackgroundChebyshev.with_terms(BACKGROUND_TERMS)
    _seed_widths(ins, data)
    return ins


def _plan(extra: list[Stage] | None = None) -> rx.RefinementPlan:
    plan = PLAN_PRESETS["mccusker_structural"]()
    plan.stages.extend(extra or [])
    # the shipped schedule, named rather than inherited: these numbers are what
    # a user's own run produces
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3
    return plan


def _fit(which: str, *, axial: bool = False):
    data = rx.read_pattern(GPX, scan=0 if which == "neutron" else 1)
    ins = _neutron(data, axial=axial) if which == "neutron" else _xray(data)
    ref = rx.Refinement(_single_crystal_structure(), ins, history=False)
    extra = None
    if axial:
        # one SH/L, as GSAS-II refines it: S/L and H/L alone are a flat pair
        ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])
        extra = [Stage("axial", ["instrument.geometry.axial_sl"])]
    limits = NEUTRON_LIMITS if which == "neutron" else XRAY_LIMITS
    return ref.fit(data, plan=_plan(extra), two_theta_limits=limits)


@pytest.fixture(scope="module")
def neutron():
    return _fit("neutron")


@pytest.fixture(scope="module")
def xray():
    return _fit("xray")


@pytest.fixture(scope="module")
def neutron_axial():
    return _fit("neutron", axial=True)


@pytest.fixture(scope="module")
def joint():
    """Both histograms, one structure, the X-ray λ held and the neutron one
    freed in a final stage with the cell and coordinates it trades against
    (the protocol of ``test_acceptance_wavelength.py``)."""
    data = [rx.read_pattern(GPX, scan=0), rx.read_pattern(GPX, scan=1)]
    plan = _plan([Stage("wavelength", [
        "hist.0.instrument.source.lines.0.wavelength",
        "phases.*.cell.*", "phases.*.atoms.*.dof.*"])])
    return rx.refine_multi(data, _single_crystal_structure(),
                           [_neutron(data[0]), _xray(data[1])], plan=plan,
                           two_theta_limits=[NEUTRON_LIMITS, XRAY_LIMITS])


def _path(key: str) -> str:
    if key.startswith("cell."):
        return f"phases.0.{key}"
    atom, field = key.split(".")
    return f"phases.0.atoms.{ATOMS.index(atom)}.{field}"


def _value(result, key: str) -> float:
    return result.parameter(_path(key)).value


def _against_table7(result, arm: str) -> list[tuple[str, float, float, bool]]:
    """(key, value, |Δ| in spreads, inside the range) for all 19 rows."""
    n = N_DETERMINATIONS[arm]
    rows = []
    for key, row in TABLE7.items():
        ref = row[arm]
        value = _value(result, key)
        spread = ref["sigma_ext"] * math.sqrt(n)
        lo, hi = ref["range"]
        rows.append((key, value, abs(value - ref["mean"]) / spread, lo <= value <= hi))
    return rows


def _report(name: str, rows) -> str:
    return "\n".join(f"{name} {k:8s} {v:10.5f} {d:5.2f} spread "
                     f"{'in' if ok else 'OUT'}" for k, v, d, ok in rows)


def _plot(result, stem: str) -> None:
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}.png"))


def _no_error_codes(result) -> None:
    assert result.usable
    errors = [d.code for d in result.diagnostics if d.level == "error"]
    assert errors == [], errors


@pytest.mark.parametrize("arm", ["neutron", "xray"])
def test_every_table7_value_lies_inside_the_participants_envelope(
        arm, neutron, xray):
    """Bars 1 and 2 of the module docstring, on each radiation alone."""
    result = neutron if arm == "neutron" else xray
    _no_error_codes(result)
    _plot(result, f"pbso4_round_robin_{arm}")
    rows = _against_table7(result, arm)
    print(_report(arm, rows))
    outside = [k for k, _v, _d, ok in rows if not ok]
    assert outside == [], f"outside the {arm} participants' range: {outside}"
    far = [(k, round(d, 2)) for k, _v, d, _ok in rows if d >= SPREAD_BAR]
    assert far == [], f"further than {SPREAD_BAR} spreads from the {arm} mean: {far}"


@pytest.mark.parametrize("arm", ["neutron", "xray"])
def test_the_agreement_indices_are_a_participants(arm, neutron, xray):
    """Bar 3, a ceiling: Rwp and GoF inside Table 5's ranges (p. 595)."""
    result = neutron if arm == "neutron" else xray
    ranges = HILL["agreement_indices"][arm]
    lo, hi = ranges["rwp_percent"]
    assert lo <= 100.0 * result.statistics.rwp <= hi
    lo, hi = ranges["gof"]
    assert lo <= result.statistics.gof <= hi


def test_an_axial_model_raises_the_neutron_cell_towards_the_xray_cell(
        neutron, neutron_axial):
    """Hill p. 605: the neutron participants who modelled the detector-height
    asymmetry physically reported larger cells, nearer the X-ray ones.  Each
    edge rises, none passes the X-ray mean (the wavelength error remains), and
    the axial arm stays inside the neutron envelope."""
    _no_error_codes(neutron_axial)
    _plot(neutron_axial, "pbso4_round_robin_neutron_axial")
    for edge in ("cell.a", "cell.b", "cell.c"):
        base, axial = _value(neutron, edge), _value(neutron_axial, edge)
        assert base < axial < TABLE7[edge]["xray"]["mean"], (edge, base, axial)
    rows = _against_table7(neutron_axial, "neutron")
    print(_report("neutron+axial", rows))
    assert [k for k, _v, _d, ok in rows if not ok] == []


def test_the_joint_fit_finds_the_wavelength_hill_back_calculated(joint):
    """Hill p. 605: the neutron wavelength is "closer to 1.912 Å" than to the
    1.909 Å the participants were given.  The band is the λ that maps the
    X-ray mean cell onto each neutron cell edge any participant reported."""
    _no_error_codes(joint)
    implied = [LAMBDA_NEUTRON * TABLE7[e]["xray"]["mean"] / bound
               for e in ("cell.a", "cell.b", "cell.c")
               for bound in TABLE7[e]["neutron"]["range"]]
    lo, hi = min(implied), max(implied)
    assert 1.9105 < lo < hi < 1.9130          # the band the docstring quotes
    row = joint.parameter("hist.0.instrument.source.lines.0.wavelength")
    print(f"joint λ_N {row.value:.5f}({row.stderr:.1e}) against [{lo:.5f}, {hi:.5f}]")
    assert lo <= row.value <= hi
    assert row.value - LAMBDA_NEUTRON > 10.0 * row.stderr
