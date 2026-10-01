"""The time-of-flight forward model: the physics, and both arms of each claim.

Every fixture here is **synthetic and written in this file**.  No line of any
real instrument file is in the repository, and where a public standard (SNS
NOMAD, ISIS GEM) set a number below, the docstring says so.

The residual is driven by ``scipy.optimize.least_squares`` directly rather than
through ``Refinement``: this rung proves the forward model, and a refinement
harness between the two would make a failure ambiguous.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.optimize import least_squares

from rietx.model.forward_tof import (
    INCIDENT_SPECTRUM_HOOK,
    CompiledTOFModel,
    compile_tof_model,
)
from rietx.model.profiles.tof import tof_from_d
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    BackgroundChebyshev,
    BackgroundPSpline,
    Instrument,
    ProfileTOF,
    TOFSource,
)
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

# --- the synthetic bank ------------------------------------------------
# A 90 degree bank of a LANSCE/POWGEN-shaped instrument, with round numbers so
# a reader can check the arithmetic by hand.  DIFC 12000 us/A over 8000-45000
# us covers d = 0.67-3.75 A, which holds Si (111) at 3.1357 A.
DIFC = 12000.0
DIFA = 0.0
TZERO = -5.0
TWO_THETA_BANK = 90.0
SI_A = 5.4311946          # NIST SRM 640c certified, the number arm A aims at
PROFILE = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)
#: The generating scale and background.  Sized so the counting statistics sit
#: *below* the model errors the negative controls introduce: with w = 1/y the
#: Rwp floor is ~sqrt(N / sum(y)), which is 0.075 at a background of 107 and a
#: strongest peak of 2145, larger than every effect measured here, and 0.0075
#: at 100x that -- a perfectly ordinary standard measurement.
SCALE = 100.0
BKG_COEFFS = [12000.0, -2000.0, 800.0, 0.0]
TOF_LO, TOF_HI = 8000.0, 45000.0
P = "instrument.source.profile_tof."
CAL = ("difc", "difa", "tzero", "difb")
PROF_NAMES = ("alpha0", "alpha1", "beta0", "beta1", "sig0", "sig1", "sig2",
              "gam0", "gam1", "gam2")


def silicon(a: float = SI_A, biso: float = 0.5, scale: float = SCALE) -> Structure:
    """Si, Fd-3m origin choice 1, the one atom at the origin."""
    return Structure(phases=[Phase(
        name="Si", space_group="Fd-3m:1",
        cell=Cell(a=Parameter(value=a), b=Parameter(value=a),
                  c=Parameter(value=a), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Si1", species="Si", x=Parameter(value=0.0), y=Parameter(value=0.0),
                    z=Parameter(value=0.0), occ=Parameter(value=1.0),
                    biso=Parameter(value=biso))],
        scale=Parameter(value=scale))])


def bank(*, difc: float = DIFC, difa: float = DIFA, tzero: float = TZERO,
         difb: float = 0.0, two_theta: float = TWO_THETA_BANK,
         profile: dict | None = None, n_cheb: int = 4,
         background=None) -> Instrument:
    prof = dict(PROFILE if profile is None else profile)
    src = TOFSource(difc=difc, difa=difa, tzero=tzero, difb=difb,
                    two_theta_bank_deg=two_theta,
                    profile_tof=ProfileTOF(**{
                        k: v if isinstance(v, Parameter) else Parameter(value=float(v))
                        for k, v in prof.items()}))
    if background is None:
        background = BackgroundChebyshev(
            coefficients=[Parameter(value=c)
                          for c in BKG_COEFFS[:n_cheb]])
    return Instrument(source=src, background=background)


def grid(n: int = 3701) -> np.ndarray:
    return np.linspace(TOF_LO, TOF_HI, n)


def blank_pattern(x: np.ndarray | None = None) -> PatternData:
    x = grid() if x is None else x
    return PatternData(tof=x.tolist(), intensity=[1.0] * len(x))


def values_of(structure: Structure, instrument: Instrument) -> dict:
    """The decoded-θ dictionary the compiled model reads.

    Hand-built rather than taken from ``ParameterTable``, so a failure here is
    the forward model's and never the table's.
    """
    v: dict[str, float] = {}
    src = instrument.source
    for name in CAL:
        v[f"instrument.source.{name}"] = getattr(src, name).value
    for name in PROF_NAMES:
        v[P + name] = getattr(src.profile_tof, name).value
    for i, c in enumerate(instrument.background.coefficients):
        v[f"instrument.background.c{i}"] = c.value
    for ip, ph in enumerate(structure.phases):
        for k in ("a", "b", "c", "alpha", "beta", "gamma"):
            v[f"phases.{ip}.cell.{k}"] = getattr(ph.cell, k).value
        v[f"phases.{ip}.scale"] = ph.scale.value
        for j, at in enumerate(ph.atoms):
            b = f"phases.{ip}.atoms.{j}."
            v[b + "x"], v[b + "y"], v[b + "z"] = at.x.value, at.y.value, at.z.value
            v[b + "occ"], v[b + "biso"] = at.occ.value, at.biso.value
    return v


def rwp(model, values) -> float:
    w = 1.0 / model.sigma
    r = w * (model.y_obs - model.evaluate(values))
    return float(np.sqrt(np.sum(r ** 2) / np.sum((w * model.y_obs) ** 2)))


#: The cubic constraint, spelled by hand because this harness has no
#: ``ParameterTable``.  Without it ``a`` moves while ``b`` and ``c`` stay: the
#: cell goes tetragonal and the minimiser finds the ``a`` that best fits a wrong
#: ``b`` and ``c``.  ``ParameterTable`` applies exactly this tie from the space
#: group on the constant-wavelength side, which is why nothing on that side has
#: ever had to think about it.
#:
#: Measured twice, and the two look nothing alike.  On the synthetic round trip
#: it is loud: ``test_the_cubic_tie_is_what_makes_this_fit_converge`` prints the
#: numbers.  On real data, where a longer background and a five-coefficient
#: profile can absorb the mismatch, it is silent -- on a real Si bank, refined
#: both ways under one protocol, the cell moved by about a part in a thousand
#: while Rwp moved in the fourth decimal, and the *untied* value is the one that
#: looks right against the certificate.  **That** is the shape to remember: a
#: missing constraint is not a bad fit, it is a good fit to the wrong model, and
#: it can flatter the answer as easily as spoil it.
CUBIC_TIE = {"phases.0.cell.a": ("phases.0.cell.b", "phases.0.cell.c")}


def run_fit(model, values0, free, *, bounds=None, max_nfev=400,
            ties=CUBIC_TIE):
    """Weighted least squares on ``free``; returns (values, rwp, chi2, esds)."""
    x0 = np.array([values0[p] for p in free], dtype=float)
    w = 1.0 / model.sigma

    def unpack(x):
        v = dict(values0)
        v.update({p: float(xv) for p, xv in zip(free, x)})
        for src, dests in (ties or {}).items():
            for dest in dests:
                v[dest] = v[src]
        return v

    def resid(x):
        return w * (model.y_obs - model.evaluate(unpack(x)))

    lo = np.full(len(free), -np.inf)
    hi = np.full(len(free), np.inf)
    for i, p in enumerate(free):
        if bounds and p in bounds:
            lo[i], hi[i] = bounds[p]
    x0 = np.clip(x0, lo, hi)
    sol = least_squares(resid, x0, bounds=(lo, hi), x_scale="jac",
                        max_nfev=max_nfev)
    v = unpack(sol.x)
    chi2 = float(np.sum(sol.fun ** 2) / max(len(sol.fun) - len(free), 1))
    # Covariance through the SVD of J, not inv(J'J).  With three Chebyshev
    # terms beside three broad-peak shape coefficients the normal matrix is
    # conditioned badly enough that ``inv`` returns garbage **without raising**
    # -- measured while writing this file: an esd of 0.19 A on a cubic cell at
    # chi2 = 0.96 with the peaks plainly fitted, where the SVD form gives
    # 3.6e-04.  An esd that is silently too large makes every "within 3 esd"
    # assertion pass, which is the one failure mode a tolerance test has.
    _u, sv, vt = np.linalg.svd(sol.jac, full_matrices=False)
    keep = sv > sv.max() * 1e-10
    cov = (vt[keep].T * (1.0 / sv[keep] ** 2)) @ vt[keep] * chi2
    esd = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return v, rwp(model, v), chi2, dict(zip(free, esd))


def synthetic_pattern(seed: int = 20260906, *, structure=None, instrument=None):
    """A Si time-of-flight histogram with Poisson noise, from this model itself.

    The one honest thing a round trip can be: the *same* forward model
    generates and refines, so what is measured is that the parameters are
    identifiable and recoverable, not that two implementations agree.  The
    agreement claims are the closed-form arms in ``test_profile_tof.py`` and
    the TOPAS fixture in ``test_tof_topas_synthetic.py``.

    The count level is set by :data:`SCALE` and :data:`BKG_COEFFS`; see there
    for why it is what it is.
    """
    structure = silicon() if structure is None else structure
    instrument = bank() if instrument is None else instrument
    x = grid()
    model = compile_tof_model(structure, instrument, blank_pattern(x))
    y_true = np.maximum(
        np.asarray(model.evaluate(values_of(structure, instrument))), 0.0)
    rng = np.random.default_rng(seed)
    y = rng.poisson(y_true).astype(float)
    return PatternData(tof=x.tolist(), intensity=y.tolist(),
                       sigma=np.sqrt(np.maximum(y, 1.0)).tolist()), y_true


# ----------------------------------------------------------------------
# the four-term position relation
# ----------------------------------------------------------------------
def test_difb_costs_nothing_at_zero_and_moves_peaks_away_from_it():
    """``tof_from_d`` gained a fourth term; at 0 it must change no bit."""
    d = np.linspace(0.4, 4.0, 61)
    three = DIFC * d + DIFA * d * d + TZERO
    assert np.array_equal(np.asarray(tof_from_d(d, DIFC, DIFA, TZERO)), three)
    assert np.array_equal(
        np.asarray(tof_from_d(d, DIFC, DIFA, TZERO, 0.0)), three)
    # and the negative arm: a non-zero DIFB is not silently ignored
    four = np.asarray(tof_from_d(d, DIFC, DIFA, TZERO, -24.5))
    assert np.min(np.abs(four - three)) > 6.0  # us, at the longest d


def test_positions_are_the_four_term_relation_and_the_apex_is_not():
    """Peaks land at T(d), and the *apex* deliberately does not.

    Both halves matter.  The model must put the position parameter exactly
    where the relation says; and the observable maximum of a back-to-back
    exponential sits at longer flight time than that parameter whenever
    beta < alpha, which is why a peak-picking check of a TOF calibration reads
    a systematic offset that is not a calibration error.  Seen on a real
    high-resolution bank, where the lines are resolved and the pick is clean:
    every parabolic apex sits later than T(d) at the certified cell, all the
    same sign.  (On a low-resolution bank the same check scatters both ways,
    which is the peak picker meeting overlapped multiplets rather than a
    bigger asymmetry.)
    """
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    d = np.asarray(m.phases[0].reflections.d)
    pos = np.asarray(m.positions(d, v))
    assert np.allclose(pos, DIFC * d + DIFA * d ** 2 + TZERO, rtol=0, atol=1e-9)

    y = np.asarray(m.evaluate(v)) - np.asarray(m.background(v))
    k = int(np.argmax(d))                      # Si (111), the strongest line
    lo = int(np.searchsorted(m.tof, pos[k] - 400.0))
    hi = int(np.searchsorted(m.tof, pos[k] + 400.0))
    apex = float(m.tof[lo:hi][np.argmax(y[lo:hi])])
    assert apex > pos[k], "beta < alpha must put the apex at longer flight time"
    assert apex - pos[k] < 200.0


def test_the_bank_angle_enters_the_lorentz_factor_and_not_the_positions():
    """L = d^4 sin(theta_bank), with theta_bank fixed and *not* per reflection."""
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    d = np.asarray(m.phases[0].reflections.d)
    assert np.allclose(np.asarray(m.lorentz(d)),
                       d ** 4 * math.sin(math.radians(TWO_THETA_BANK / 2.0)))
    assert m.sin_theta_bank == pytest.approx(math.sin(math.radians(45.0)))
    # the whole Bragg pattern scales linearly with sin(theta_bank): on one bank
    # it is exactly degenerate with the phase scale, which is why the report
    # says so rather than claiming the angle is measured here
    other = compile_tof_model(st, bank(two_theta=120.0), blank_pattern())
    v = values_of(st, ins)
    r = (np.asarray(other.bragg_component(v))
         / np.maximum(np.asarray(m.bragg_component(v)), 1e-300))
    lit = r[np.asarray(m.bragg_component(v)) > 1e-6]
    assert np.allclose(lit, math.sin(math.radians(60.0)) / m.sin_theta_bank,
                       rtol=1e-10)
    # and the positions do not move with it
    assert np.allclose(np.asarray(other.positions(d, v)),
                       np.asarray(m.positions(d, v)))


def test_wavelength_of_a_reflection_is_2_d_sin_theta_bank():
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    d = np.asarray(m.phases[0].reflections.d)
    assert np.allclose(np.asarray(m.wavelength_of(d)),
                       2.0 * d * m.sin_theta_bank)


def test_a_bank_declaring_no_spectrum_multiplies_by_nothing_at_all():
    """``ITYP 0`` is ``None``, not an array of ones — the bit-identity claim.

    Every reduction that already divided by a vanadium measurement writes
    ``ITYP 0`` (ISIS GEM does, on all six banks), and that is the default of
    :class:`~rietx.schemas.instrument.IncidentSpectrum`.  Returning ``None``
    rather than ``ones_like(tof)`` is what makes such a bank the same arithmetic
    it was before T-3 rather than the same arithmetic times one.
    """
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    assert m.spectrum_itype == 0 and m.spectrum_paths == ()
    assert m.incident_spectrum(values_of(st, ins)) is None
    assert INCIDENT_SPECTRUM_HOOK.endswith("CompiledTOFModel.incident_spectrum")
    # the seam is still a seam: overriding it multiplies the Bragg sum and
    # nothing else, which is the property that says the background is fitted
    # in the observed space and takes no spectrum factor
    v = values_of(st, ins)
    base_bragg = np.asarray(m.bragg_component(v))
    base_bkg = np.asarray(m.background(v))
    m.incident_spectrum = lambda values: 3.0
    assert np.allclose(np.asarray(m.bragg_component(v)), 3.0 * base_bragg)
    assert np.allclose(np.asarray(m.background(v)), base_bkg)


def test_the_profile_kind_is_structural_and_switches_on_gamma():
    st = silicon()
    assert compile_tof_model(st, bank(), blank_pattern()).profile_kind == "gaussian"
    with_gamma = bank(profile=dict(PROFILE, gam1=4.0))
    assert compile_tof_model(st, with_gamma,
                             blank_pattern()).profile_kind == "pseudovoigt"
    # a gamma that is still zero but which the coming stage can move off zero
    # compiles the type-3 shape too: a structural decision taken once, from
    # what can change, never re-asked from a decoded value
    assert compile_tof_model(st, bank(), blank_pattern(),
                             moving_paths={P + "gam1"}).profile_kind == "pseudovoigt"


def test_gamma_zero_makes_type_three_equal_type_one_to_one_ulp():
    """The reduction ``test_profile_tof`` pins, seen through the whole pattern.

    ``test_profile_tof`` asserts ``np.array_equal`` for the two shape functions
    at gamma = 0, and that holds on its grid.  It is **not** universal, and the
    difference is one ulp of sigma, not of the shape: ``tof_pseudovoigt_widths``
    returns ``sigma_eff = Gamma / 2.3548...`` after building ``Gamma =
    2.3548... * sigma``, and that round trip is inexact for 11.7 % of sigma
    values (measured over 200 000 draws in [1, 500] us, worst 1 ulp).  Through
    the whole synthetic pattern that shows up as **8 of 3701** evaluated
    channels differing, by at most 3.6e-12 absolute and 2.2e-16 relative -- 56
    channels of the Bragg sum differ before the background is added to it, and
    the background then absorbs most of them back into equality.  Pinned at
    that size rather than at zero, because a bar written tighter than the
    arithmetic is a bar that fails on somebody else's data.
    """
    st = silicon()
    g = compile_tof_model(st, bank(), blank_pattern())
    pv = compile_tof_model(st, bank(), blank_pattern(),
                           moving_paths={P + "gam1"})
    assert (g.profile_kind, pv.profile_kind) == ("gaussian", "pseudovoigt")
    assert np.array_equal(g.phases[0].win, pv.phases[0].win)
    v = values_of(st, bank())
    a, b = np.asarray(g.evaluate(v)), np.asarray(pv.evaluate(v))
    assert np.max(np.abs(a - b) / np.abs(a)) < 1e-14


def test_the_batched_scatter_equals_the_reflection_loop_bit_for_bit():
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    assert np.array_equal(np.asarray(m._phase_component_batched(0, v)),
                          np.asarray(m._phase_component_scalar(0, v)))
    idx, seg = m.flat_windows[0]
    assert len(idx) == len(seg) > 0
    assert int((m.phases[0].win[0, :, 1] - m.phases[0].win[0, :, 0]).sum()) == len(idx)


# ----------------------------------------------------------------------
# D. the synthetic round trip -- the positive arm
# ----------------------------------------------------------------------
RECOVER_FREE = ["phases.0.scale", "phases.0.cell.a", "phases.0.atoms.0.biso",
                "instrument.source.tzero", P + "alpha1", P + "beta0",
                P + "sig1", "instrument.background.c0",
                "instrument.background.c1", "instrument.background.c2"]
RECOVER_BOUNDS = {"phases.0.scale": (0.0, np.inf),
                  "phases.0.atoms.0.biso": (0.0, 5.0),
                  P + "alpha1": (1e-9, 10.0), P + "beta0": (1e-4, 1.0),
                  P + "sig1": (0.0, 1e5),
                  "instrument.source.tzero": (-400.0, 400.0),
                  # the cell window ``params.vector.cell_window`` applies on
                  # the constant-wavelength side, for the same reason: a cold
                  # cell is the one parameter that can walk to a wrong minimum
                  # where a different reflection sits under each peak.
                  "phases.0.cell.a": (SI_A * 0.97, SI_A * 1.03)}
BKG_FREE = ["instrument.background.c0", "instrument.background.c1",
            "instrument.background.c2"]


def _recover(pattern, *, a0, tzero0, scale0, lorentz_power=4.0, rounds=3,
             ties=CUBIC_TIE, window_slack_us=None):
    """Refine from a perturbed start, recompiling between rounds.

    Recompiling is the one thing here that is not optional.  The evaluation
    windows are frozen at compile, and a start 0.5 % out in the cell puts the
    longest peak 225 us from where it belongs at T = 45 000 us -- more than the
    default movement headroom there (3 us + 2e-3*T = 93 us).  Rounds two and
    three re-freeze them around the peaks as they now are, which is what
    ``Refinement`` does between stages.

    What is *not* needed, measured rather than assumed: neither a wide
    ``window_slack_us`` in the first round nor a stage schedule changes the
    answer by more than 5e-9 A.  Both were in this function while the cubic tie
    below was missing, and both looked essential -- see ``CUBIC_TIE``.  They are
    gone because a fixture that carries machinery nothing measures is a fixture
    that hides the next bug the same way.
    """
    v = None
    for _ in range(rounds):
        st = silicon(a=(v["phases.0.cell.a"] if v else a0),
                     biso=(v["phases.0.atoms.0.biso"] if v else 0.5),
                     scale=(v["phases.0.scale"] if v else scale0))
        ins = bank(profile=(dict(PROFILE) if v is None
                            else {n: v[P + n] for n in PROF_NAMES}),
                   tzero=(v["instrument.source.tzero"] if v else tzero0))
        for i, c in enumerate(ins.background.coefficients):
            c.value = v[f"instrument.background.c{i}"] if v else c.value
        m = compile_tof_model(st, ins, pattern, window_slack_us=window_slack_us)
        if lorentz_power != 4.0:
            m.lorentz = (lambda d, _p=lorentz_power, _s=m.sin_theta_bank:
                         np.asarray(d, dtype=float) ** _p * _s)
        v0 = values_of(st, ins)
        if v is not None:
            v0.update({k: v[k] for k in v0 if k in v})
        v, r_wp, chi2, esd = run_fit(m, v0, RECOVER_FREE,
                                     bounds=RECOVER_BOUNDS, ties=ties)
    return v, r_wp, chi2, esd


@pytest.mark.slow
def test_the_cubic_tie_is_what_makes_this_fit_converge():
    """The bug this file was written around, kept as a control.

    A hand-built values dictionary has no ``ParameterTable``, and therefore no
    symmetry ties.  Refining ``a`` on a cubic phase without copying it to ``b``
    and ``c`` lets the cell go tetragonal; the minimiser then finds the ``a``
    that best fits a wrong ``b`` and ``c``.  Rwp and chi2 stay healthy while it
    happens, which is why it survived three real data sets before the synthetic
    round trip -- the one arm with a known answer -- caught it.
    """
    pattern, _ = synthetic_pattern()
    good, r_good, c_good, esd = _recover(pattern, a0=SI_A * 1.005,
                                         tzero0=TZERO + 20.0, scale0=2.0 * SCALE)
    bad, r_bad, c_bad, esd_bad = _recover(pattern, a0=SI_A * 1.005,
                                          tzero0=TZERO + 20.0,
                                          scale0=2.0 * SCALE, ties=None)
    dev = abs(bad["phases.0.cell.a"] - SI_A) / max(esd_bad["phases.0.cell.a"], 1e-300)
    print(f"\n  cubic tie: a = {good['phases.0.cell.a']:.7f} tied against "
          f"{bad['phases.0.cell.a']:.7f} untied ({dev:.0f} esd from the "
          f"generating value), at Rwp {r_good:.5f} against {r_bad:.5f} and "
          f"chi2 {c_good:.3f} against {c_bad:.3f}")
    assert dev > 3.0, "the untied fit must be wrong, or this control is inert"
    assert abs(good["phases.0.cell.a"] - SI_A) / esd["phases.0.cell.a"] < 3.0


@pytest.mark.slow
def test_a_perturbed_start_recovers_the_generating_parameters():
    """Arm D: a off by 0.5 %, TZERO off by 20 us, scale off by 2x.

    The bar the brief set: every recovered value within 3 esd of the one that
    generated the data.  Reported by the test so a reader sees the margin.
    """
    pattern, _ = synthetic_pattern()
    v, r, chi2, esd = _recover(pattern, a0=SI_A * 1.005, tzero0=TZERO + 20.0,
                               scale0=2.0 * SCALE)
    truth = {"phases.0.cell.a": SI_A, "phases.0.scale": SCALE,
             "phases.0.atoms.0.biso": 0.5,
             "instrument.source.tzero": TZERO,
             P + "alpha1": PROFILE["alpha1"], P + "beta0": PROFILE["beta0"],
             P + "sig1": PROFILE["sig1"]}
    worst = ("", 0.0)
    for path, want in truth.items():
        dev = abs(v[path] - want) / max(esd[path], 1e-300)
        if dev > worst[1]:
            worst = (path, dev)
        assert dev < 3.0, (
            f"{path}: recovered {v[path]:.8g} against {want:.8g}, "
            f"esd {esd[path]:.3g}, {dev:.2f} esd")
    print(f"\n  arm D: Rwp = {r:.4f}, chi2 = {chi2:.3f}, "
          f"a = {v['phases.0.cell.a']:.7f} +- {esd['phases.0.cell.a']:.1e} A "
          f"(generated {SI_A}); worst deviation {worst[1]:.2f} esd on {worst[0]}")
    assert chi2 < 1.3          # Poisson noise and nothing else
    assert r < 0.05


# ----------------------------------------------------------------------
# E. the negative controls
# ----------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("power", [3.0, 0.0])
def test_a_wrong_lorentz_exponent_is_visible_in_the_fit(power):
    """E(i): d^3, or none, in place of d^4 must show up as Rwp or as a.

    The control that can fail: with the exponent free, TOPAS's own
    refinements of real banks land close to 4, and TOPAS inputs for other
    banks write ``scale_pks = D_spacing^4`` outright -- so 4 is what an
    independent program measures on real data, and
    a neighbouring integer has to be distinguishable here.
    """
    pattern, _ = synthetic_pattern()
    good, r_good, _c, esd = _recover(pattern, a0=SI_A * 1.005,
                                     tzero0=TZERO + 20.0, scale0=2.0 * SCALE)
    bad, r_bad, _c2, esd_bad = _recover(pattern, a0=SI_A * 1.005,
                                        tzero0=TZERO + 20.0, scale0=2.0 * SCALE,
                                        lorentz_power=power)
    dev = abs(bad["phases.0.cell.a"] - SI_A) / max(esd_bad["phases.0.cell.a"], 1e-300)
    print(f"\n  arm E(i) d^{power:g}: Rwp {r_good:.4f} -> {r_bad:.4f}, "
          f"a {good['phases.0.cell.a']:.7f} -> {bad['phases.0.cell.a']:.7f} "
          f"+- {esd_bad['phases.0.cell.a']:.1e} ({dev:.1f} esd from the "
          f"generating value), Biso {good['phases.0.atoms.0.biso']:.3f} -> "
          f"{bad['phases.0.atoms.0.biso']:.3f}")
    assert r_bad > 1.5 * r_good or dev > 3.0


@pytest.mark.slow
def test_alpha_and_beta_exchanged_and_held_fit_measurably_worse():
    """E(ii): the pulse asymmetry has a sign, and the data can see it.

    The rates are **held** here, not refined: with alpha and beta free the
    solver simply walks back to the generating shape from either side, which
    measures the optimiser and not the model.  What the control has to show is
    that a peak whose tail is put on the wrong side of the position cannot be
    absorbed by the scale, the cell, Biso or an eight-term background -- so
    everything else is free and only the two rates are wrong.
    """
    pattern, _ = synthetic_pattern()
    free = [p for p in RECOVER_FREE if p not in (P + "alpha1", P + "beta0")]
    out = {}
    for name, prof in (("as generated", dict(PROFILE)),
                       ("exchanged", dict(alpha0=PROFILE["beta0"], alpha1=1e-9,
                                          beta0=PROFILE["alpha1"] / 1.5,
                                          beta1=0.0, sig1=PROFILE["sig1"]))):
        st, ins = silicon(), bank(profile=prof)
        m = compile_tof_model(st, ins, pattern, window_slack_us=400.0)
        v, r, chi2, _e = run_fit(m, values_of(st, ins), free,
                                 bounds=RECOVER_BOUNDS)
        out[name] = (r, chi2, v["phases.0.cell.a"])
    r_good, c_good, a_good = out["as generated"]
    r_bad, c_bad, a_bad = out["exchanged"]
    print(f"\n  arm E(ii): Rwp {r_good:.5f} (chi2 {c_good:.2f}, a {a_good:.7f}) "
          f"with the shape as generated against {r_bad:.5f} "
          f"(chi2 {c_bad:.2f}, a {a_bad:.7f}) with the rates exchanged "
          f"-- {r_bad / r_good:.1f}x")
    assert r_bad > 2.5 * r_good   # measured 2.9x on this seed


def test_the_mismatched_pairs_are_refused_and_the_matched_one_is_not():
    """E(iii): a 2theta pattern with a TOF bank, and the converse."""
    st = silicon()
    two_theta = PatternData(two_theta=np.linspace(10.0, 140.0, 500).tolist(),
                            intensity=[1.0] * 500)
    with pytest.raises(ValueError, match="abscissa is 2. in degrees"):
        compile_tof_model(st, bank(), two_theta)

    from rietx.model.forward import compile_model
    cw = Instrument.constant_wavelength_neutron(1.54)
    with pytest.raises(ValueError, match="time of flight"):
        compile_tof_model(st, cw, blank_pattern())
    with pytest.raises(ValueError, match="time of flight"):
        compile_model(st, bank(), blank_pattern())
    with pytest.raises(ValueError, match="time of flight"):
        compile_model(st, cw, blank_pattern())
    # the positive arm of the same gate
    assert compile_tof_model(st, bank(), blank_pattern()).n_points > 10
    assert compile_model(st, cw, two_theta).mode == "rietveld"


def test_the_corrections_t1b_refused_are_applied_now_and_the_rest_still_refuse():
    """E(iv): which corrections compile on a bank and which are refused.

    Three corrections were refused on a bank at first; two of them — absorption
    and extinction — are now applied, and the third never was.  What this pins is the *pair* —
    that the two which landed compile, and that the two which did not still
    refuse by name — because a list of refusals nobody re-reads is how a
    correction gets applied by accident later.
    """
    from rietx.schemas.structure import PreferredOrientation

    # applied: a declared extinction and a declared capillary radius compile
    st = silicon()
    st.phases[0].extinction = 1e-4
    assert compile_tof_model(st, bank(), blank_pattern()).n_points > 10
    ins = bank()
    ins.geometry.capillary_radius_mm = 3.0
    assert compile_tof_model(silicon(), ins,
                             blank_pattern()).absorption_terms is not None

    # still refused: a *scalar* µR (a claim at one wavelength), and texture
    with pytest.raises(ValueError, match="at one wavelength"):
        bad = bank()
        bad.geometry.mu_r = 0.8
        compile_tof_model(silicon(), bad, blank_pattern())
    st2 = silicon()
    st2.phases[0].preferred_orientation = PreferredOrientation(
        axis=(1, 1, 1), r=Parameter(value=1.0))
    with pytest.raises(ValueError, match="preferred orientation") as exc:
        compile_tof_model(st2, bank(), blank_pattern())
    assert "#193" in str(exc.value) and "T-3" not in str(exc.value)


def test_a_flat_specimen_mu_t_is_refused_and_names_the_open_issue_not_a_rung():
    """The other half of the absorption gate, on the geometry that admits it.

    Its refusal moved from "T-3 has not written this" to "this arm's specimen
    model is the cylinder", which is a statement about what exists rather than
    about a schedule — so the message names issue #193 and not a rung that is
    now done.
    """
    from rietx.schemas.instrument import Geometry

    st, ins = silicon(), bank()
    ins.geometry = Geometry(kind="flat_plate_transmission", mu_t=0.3)
    with pytest.raises(ValueError, match="flat-specimen absorption") as exc:
        compile_tof_model(st, ins, blank_pattern())
    assert "#193" in str(exc.value) and "T-3" not in str(exc.value)


def test_preferred_orientation_and_stephens_strain_are_refused_naming_the_issue():
    """Each names the open issue, not a rung: the texture sentence once said
    "Texture is T-3", and T-3 is the cut that refuses it."""
    from rietx.schemas.structure import PreferredOrientation, StephensStrain

    st, ins = silicon(), bank()
    st.phases[0].preferred_orientation = PreferredOrientation(
        axis=(1, 1, 1), r=Parameter(value=1.0))
    with pytest.raises(ValueError, match="preferred orientation") as exc:
        compile_tof_model(st, ins, blank_pattern())
    assert "#193" in str(exc.value) and "T-3" not in str(exc.value)

    st = silicon()
    st.phases[0].microstrain = StephensStrain(s400=Parameter(value=1e-4))
    with pytest.raises(ValueError, match="Stephens"):
        compile_tof_model(st, ins, blank_pattern())


def test_a_texture_and_a_moment_are_refused_on_a_bank_by_name():
    """Two phase blocks the constant-wavelength model draws and this arm does
    not.  A spherical-harmonic texture is refused here.  A magnetic moment is
    refused by ``forward.magnetic_wanted``, the one dispatch authority, rather
    than compiled as the nuclear part alone."""
    from rietx.schemas.structure import (
        MagneticSymmetry,
        Moment,
        SphericalHarmonicTexture,
    )

    st = silicon()
    st.phases[0].texture = SphericalHarmonicTexture(order=4)
    with pytest.raises(ValueError, match="spherical-harmonic texture") as exc:
        compile_tof_model(st, bank(), blank_pattern())
    assert "#193" in str(exc.value)

    a = 4.4
    magnetic = Structure(phases=[Phase(
        name="M", space_group="P 1",
        cell=Cell(a=Parameter(value=a), b=Parameter(value=a),
                  c=Parameter(value=a), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="Mn", species="Mn", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    occ=Parameter(value=1.0), biso=Parameter(value=0.3),
                    moment=Moment.from_values((2.0, 0.0, 0.0), "Mn2+"))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]),
        scale=Parameter(value=SCALE))])
    with pytest.raises(ValueError, match="carries a magnetic moment") as exc:
        compile_tof_model(magnetic, bank(), blank_pattern())
    assert "'neutron_tof'" in str(exc.value)
    magnetic.phases[0].atoms[0].moment = None
    assert compile_tof_model(magnetic, bank(), blank_pattern()).n_points > 10


def test_an_all_zero_profile_is_refused_by_name():
    """What a declined GSAS ``PRCF`` block leaves behind
    (``GSAS_IPARM_PROFILE_DECLINED``)."""
    st = silicon()
    with pytest.raises(ValueError, match="non-positive"):
        compile_tof_model(st, bank(profile={}), blank_pattern())


def test_a_negative_variance_law_is_refused_and_says_the_terms_are_variances():
    """The schema floors every ``sig-*`` at zero, and an omitted ``min``
    inherits the floor, so the compiler's check is reached by a caller who
    states a negative bound on purpose (an explicit bound always wins, issue
    #204)."""
    st = silicon()
    with pytest.raises(ValueError, match="variances"):
        compile_tof_model(
            st, bank(profile=dict(PROFILE, sig0=Parameter(value=-1e6, min=-1e7))),
            blank_pattern())


def test_the_pspline_air_term_is_refused_on_a_flight_time():
    """The 1/x air row is a statement about 2θ, so a P-spline declaring one is
    refused; the spline without it (``air_scatter=None``, the default since
    WP-1454) is axis-blind and compiles."""
    st = silicon()
    breaks = list(np.linspace(TOF_LO, TOF_HI, 6))
    coeffs = [Parameter(value=0.0) for _ in range(len(breaks) + 2)]
    with_air = BackgroundPSpline(coefficients=coeffs, breakpoints=breaks,
                                 air_scatter=Parameter(value=0.0))
    with pytest.raises(ValueError, match="air"):
        compile_tof_model(st, bank(background=with_air), blank_pattern())
    without = BackgroundPSpline(coefficients=coeffs, breakpoints=breaks)
    assert without.air_scatter is None
    model = compile_tof_model(st, bank(background=without), blank_pattern())
    assert "instrument.background.air" not in model.bkg_paths


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_intensity_extraction_modes_are_refused_by_name(mode):
    st = silicon()
    with pytest.raises(ValueError, match="issue #193"):
        compile_tof_model(st, bank(), blank_pattern(), mode=mode)


def test_the_angle_accessors_refuse_rather_than_returning_microseconds():
    """The mirror of ``PatternData.tt()``, one rank up."""
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    for name in ("tt", "tt_min", "tt_max"):
        with pytest.raises(ValueError, match="2. -only accessor|microseconds"):
            getattr(m, name)
    with pytest.raises(ValueError, match="no primary wavelength"):
        m.wavelength
    assert m.line_lambdas(values_of(st, ins)) == []
    assert m.line_wavelengths == ()
    # and the axis-blind names answer
    assert m.axis == "tof"
    assert len(m.grid) == m.n_points == len(m.tof)
    assert (m.x_min, m.x_max) == (m.tof_min, m.tof_max)


def test_the_geometry_kind_is_not_a_two_theta_key():
    """It is read as a dict key, not as a description, so it must not resolve.

    ``report.layer1.POSITION_TEMPLATES`` indexes ``geometry_kind`` to pick the
    2theta regression shapes a misfit is attributed against.  The natural value
    for a TOF diffractometer -- a can of powder in a beam is Debye-Scherrer --
    is a key that resolves, and would hand a flight-time fit the sample-
    displacement and transparency templates of a goniometer and report the
    answer.  This pins the refusal instead.
    """
    from rietx.report.layer1 import POSITION_TEMPLATES

    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    assert m.geometry_kind not in POSITION_TEMPLATES
    # the positive arm: the three keys that *are* there still are
    assert set(POSITION_TEMPLATES) >= {"bragg_brentano", "debye_scherrer",
                                       "flat_plate_transmission"}


def test_analytic_jacobian_support_is_declared_off_and_refuses_loudly():
    """A missing analytic column must not come back short (WP-1070)."""
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    assert CompiledTOFModel.analytic_jacobian is False
    assert m.scalar_chain_supported("phases.0.cell.a") is False
    with pytest.raises(ValueError, match="analytic derivative bases"):
        m.derivative_bases(values_of(st, ins))


def test_the_windows_are_asymmetric_the_way_the_pulse_is():
    """beta < alpha puts the tail at long flight time; the window follows."""
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    d = np.asarray(m.phases[0].reflections.d)
    pos = np.asarray(m.positions(d, v))
    win = m.phases[0].win[0]
    k = int(np.argmax(d))
    left = pos[k] - m.tof[int(win[k, 0])]
    right = m.tof[int(win[k, 1]) - 1] - pos[k]
    assert right > left, "the long-flight-time wing must get the wider half"


def test_phase_support_and_line_counts_answer_on_a_tof_bank():
    st, ins = silicon(), bank()
    pattern, _ = synthetic_pattern()
    m = compile_tof_model(st, ins, pattern)
    v = values_of(st, ins)
    assert m.phase_support(v)[0] > 1.0
    assert m.phase_line_counts()[0] > 5
    # the limit case is a different statement from a small one
    empty = compile_tof_model(st, ins, pattern, tof_limits=(43000.0, 45000.0))
    assert empty.phase_line_counts()[0] == 0
    assert empty.phase_support(v)[0] == 0.0
