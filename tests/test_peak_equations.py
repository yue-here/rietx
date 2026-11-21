"""Peak equations: a term on a reflection's width or position, or a factor on its
intensity, written in its hkl and angle (WP-2107).

Each target is held to a built-in with the same physics (no code shared with
what it certifies), the TCH partials the exact columns chain through to a
complex step, the coefficients to their truth over pinned noise seeds, and the
refusals to the message a user meets.  The derivative columns themselves are
``tests/test_cross_backend.py``'s ``peak_equations`` config.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.model.forward import compile_model
from rietx.model.profiles.pseudovoigt import tch_gamma_eta, tch_gamma_eta_partials
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import check_peak_width_positive
from tests.test_stephens import brucite

OUT = Path(__file__).parent / "output"
TT = np.arange(10.0, 120.0, 0.01)


def _eq(target, expression, **coefficients) -> rx.PeakEquation:
    return rx.PeakEquation(target=target, expression=expression,
                           coefficients={k: Parameter(value=v)
                                         for k, v in coefficients.items()})


def _instrument() -> rx.Instrument:
    ins = rx.Instrument.bragg_brentano()
    ins.source.dispersion = None
    ins.profile.w.value = 2e-3
    return ins


def _compiled(phases, ins, tt=TT, mode="rietveld"):
    s = Structure(phases=list(phases))
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(s, ins, blank, mode=mode)
    table = ParameterTable(s, ins)
    return model, table


def _ycalc(phase, ins) -> np.ndarray:
    model, table = _compiled([phase], ins)
    return np.asarray(model.evaluate(table.decode(table.x0())))


def _rel(a, b) -> float:
    return float(np.max(np.abs(a - b)) / np.max(np.abs(b)))


def _rocksalt(**kw) -> Phase:
    p = Parameter
    return Phase(name="NaCl", space_group="F m -3 m",
                 cell=Cell(a=p(value=5.64), b=p(value=5.64), c=p(value=5.64),
                           alpha=p(value=90.0), beta=p(value=90.0), gamma=p(value=90.0)),
                 atoms=[Atom(label="Na", species="Na", x=p(value=0.0), y=p(value=0.0),
                             z=p(value=0.0)),
                        Atom(label="Cl", species="Cl", x=p(value=0.5), y=p(value=0.5),
                             z=p(value=0.5))], **kw)


# --- the surface's refusals ----------------------------------------------------


@pytest.mark.parametrize("build, fragment", [
    (lambda: _eq("lor_fwhm", "w*tan(theta)"), "neither a coefficient nor a reflection"),
    (lambda: _eq("lor_fwhm", "w*tan(theta)", w=0.1, v=0.2), "is not read by the expression"),
    (lambda: _eq("lor_fwhm", "h*tan(theta)", h=0.1), "that name is the reflection's"),
    (lambda: _eq("intensity_factor", "scale", scale=1.0), "phase scale"),
    (lambda: _eq("lor_fwhm", "if(d > 2, a, 0)", a=0.1), "frozen for the stage"),
    (lambda: _eq("lor_fwhm", "if(h == 0, a, 0)*tan(th)", a=0.1), "reflection names are"),
    (lambda: _eq("lor_fwhm", "a*harmonic(3, 0)", a=0.1), "l is even and at least 2"),
    (lambda: _eq("lor_fwhm", "a*orbit_mean(orbit_mean(l^2))", a=0.1),
     "orbit_mean() inside orbit_mean()"),
])
def test_a_malformed_equation_is_refused_at_construction(build, fragment):
    with pytest.raises(ValidationError) as err:
        build()
    assert fragment in str(err.value)


@pytest.mark.parametrize("equations, fragment", [
    ([_eq("lor_fwhm", "a*tan(theta)", a=0.1)], "belongs to a phase"),
    ([_eq("shift", "a*l", a=0.1)], "belong to a phase's reflections"),
    ([_eq("shift", "a*cos(theta)", a=0.1), _eq("shift", "b", b=0.0)], "two equations"),
])
def test_the_instrument_level_takes_a_shift_in_the_angle_alone(equations, fragment):
    data = rx.Instrument.bragg_brentano().model_dump(mode="json")
    data["peak_equations"] = [e.model_dump(mode="json") for e in equations]
    with pytest.raises(ValidationError) as err:
        rx.Instrument.model_validate(data)
    assert fragment in str(err.value)


def test_a_coefficient_named_after_a_phase_field_is_refused():
    """A plan's ``phases.*.lor_size`` would match the coefficient's path too,
    since fnmatch's ``*`` crosses dots."""
    with pytest.raises(ValidationError, match="named after a phase field"):
        brucite(peak_equations=[_eq("lor_fwhm", "lor_size/cos(theta)", lor_size=0.1)])


def test_an_equation_on_l_is_refused_where_the_orbit_mixes_l():
    """In a cubic group an image of (2, 0, 0) is (0, 0, 2), so ``l == 0`` is not
    one value on that orbit.  The refusal names the reflection, and
    ``orbit_mean`` is the exit."""
    branch = _eq("lor_fwhm", "if(l == 0, a, b)*tan(theta)", a=0.05, b=0.05)
    with pytest.raises(ValueError, match=r"not single-valued over the orbit") as err:
        _compiled([_rocksalt(peak_equations=[branch])], _instrument())
    # a equal to b agrees at the start; the trial coefficients split it
    assert "trial coefficients" in str(err.value)
    mean = _eq("lor_fwhm", "orbit_mean(if(l == 0, a, b))*tan(theta)", a=0.05, b=0.03)
    _compiled([_rocksalt(peak_equations=[mean])], _instrument())
    # a symmetric spelling of the 0kl family passes as written
    family = _eq("lor_fwhm", "if(h*k*l == 0, a, b)*tan(theta)", a=0.05, b=0.03)
    _compiled([_rocksalt(peak_equations=[family])], _instrument())
    # so does a symmetrised harmonic, invariant by construction
    harm = _eq("lor_fwhm", "(a + b*harmonic(4, 1))*tan(theta)", a=0.05, b=0.01)
    _compiled([_rocksalt(peak_equations=[harm])], _instrument())
    # one the Laue class does not allow is named with the one it does
    off = _eq("lor_fwhm", "(a + b*harmonic(4, 0))*tan(theta)", a=0.05, b=0.01)
    with pytest.raises(ValueError, match=r"allows harmonic\(4, 1\)"):
        _compiled([_rocksalt(peak_equations=[off])], _instrument())


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_an_intensity_factor_is_refused_where_intensities_are_extracted(mode):
    phase = brucite(peak_equations=[_eq("intensity_factor", "if(l == 0, 1, p)", p=0.7)])
    with pytest.raises(ValueError, match="extracted intensities would absorb it"):
        _compiled([phase], _instrument(), mode=mode)


# --- each target against its built-in twin -------------------------------------


def test_a_tan_theta_lorentzian_term_is_lor_strain():
    twin = brucite()
    twin.lor_strain.value = 0.05
    eq = brucite(peak_equations=[_eq("lor_fwhm", "y*tan(theta)", y=0.05)])
    assert _rel(_ycalc(eq, _instrument()), _ycalc(twin, _instrument())) < 1e-12


def test_a_variance_term_in_tan_squared_is_caglioti_u():
    ins = _instrument()
    ins.profile.u.value = 0.01
    eq = brucite(peak_equations=[_eq("gauss_fwhm_squared", "u0*tan(theta)^2", u0=0.01)])
    assert _rel(_ycalc(eq, _instrument()), _ycalc(brucite(), ins)) < 1e-12


@pytest.mark.parametrize("level", ["instrument", "phase"])
def test_a_cos_theta_shift_is_sample_displacement(level):
    twin = _instrument()
    twin.geometry.sample_displacement.value = 0.1
    radius = twin.geometry.goniometer_radius_mm
    eq = _eq("shift", f"-2*s*cos(theta)/{radius}*180/pi", s=0.1)
    ins, phase = _instrument(), brucite()
    if level == "instrument":
        ins.peak_equations = [eq]
    else:
        phase = brucite(peak_equations=[eq])
    assert _rel(_ycalc(phase, ins), _ycalc(brucite(), twin)) < 1e-12


def test_an_exponential_in_s_squared_is_biso():
    twin = brucite()
    for atom in twin.atoms:
        atom.biso.value += 0.7
    eq = brucite(peak_equations=[_eq("intensity_factor", "exp(-2*b*(1/(2*d))^2)", b=0.7)])
    assert _rel(_ycalc(eq, _instrument()), _ycalc(twin, _instrument())) < 1e-12


def test_the_tch_partials_match_a_complex_step():
    """The exact width columns chain through these; a complex step has no
    truncation error at h = 1e-30."""
    gg = np.array([0.02, 0.05, 0.1, 0.3])
    gl = np.array([0.0, 0.01, 0.1, 0.5])
    got = tch_gamma_eta_partials(gg, gl)
    h = 1e-30
    g_g, e_g = (np.imag(v) / h for v in _tch_complex(gg + 1j * h, gl + 0j))
    g_l, e_l = (np.imag(v) / h for v in _tch_complex(gg + 0j, gl + 1j * h))
    for a, b in zip(got, (g_g, g_l, e_g, e_l), strict=True):
        np.testing.assert_allclose(a, b, rtol=1e-13, atol=1e-15)
    gamma, eta = tch_gamma_eta(gg, gl)
    assert np.all(np.isfinite(gamma)) and np.all(np.isfinite(eta))


def _tch_complex(gg, gl):
    from rietx.model.profiles.pseudovoigt import _TCH_ETA, _TCH_GAMMA
    c1, c2, c3, c4 = _TCH_GAMMA
    gamma = (gg**5 + c1 * gg**4 * gl + c2 * gg**3 * gl**2 + c3 * gg**2 * gl**3
             + c4 * gg * gl**4 + gl**5) ** 0.2
    q = gl / gamma
    e1, e2, e3 = _TCH_ETA
    return gamma, e1 * q + e2 * q**2 + e3 * q**3


# --- the guard and the QPA finding ---------------------------------------------


def test_a_width_driven_below_zero_is_a_guard_finding():
    """A signed variance term is legal; the total going negative is not."""
    phase = brucite(peak_equations=[
        _eq("gauss_fwhm_squared", "q/cos(theta)^2", q=-0.01),
        _eq("lor_fwhm", "y*tan(theta)", y=0.02)])
    model, table = _compiled([phase], _instrument())
    (finding,) = check_peak_width_positive(table, model)
    assert finding.code == "PEAK_WIDTH_NOT_POSITIVE"
    assert finding.paths == ("phases.0.peak_equations.0",)
    assert "Γ_G² below zero" in str(finding) and finding.value < 0.0
    # a term that leaves the total positive is silent
    ok = brucite(peak_equations=[_eq("gauss_fwhm_squared", "q/cos(theta)^2", q=-2e-4)])
    model, table = _compiled([ok], _instrument())
    assert check_peak_width_positive(table, model) == []


def test_a_fraction_beside_an_intensity_factor_says_it_reads_the_scale_alone():
    from rietx.refine import _qpa_intensity_factor_diagnostics

    phases = [brucite(peak_equations=[_eq("intensity_factor", "if(l == 0, 1, p)",
                                          p=0.7)]),
              _rocksalt()]
    phases[1].scale.value = 1e-3
    model, table = _compiled(phases, _instrument())
    values = table.decode(table.x0())
    structure = Structure(phases=phases)
    (diag,) = _qpa_intensity_factor_diagnostics(structure, values, model, [],
                                                lambda p: p)
    assert diag.code == "QPA_INTENSITY_FACTOR"
    assert diag.where == ["phases.0.peak_equations.0"]
    assert "by 0.7 to 1 (mean 0.74)" in diag.message and 0.7 < diag.value < 1.0
    # intensity = scale × factor, so the scale absorbs 1/mean: too high
    assert "too high by about 1/0.74 = 1.4×" in diag.message
    assert "multiply this phase's scale by 0.74" in diag.suggestion
    # one phase in the analysis has a fraction of 1 whatever its factor
    assert _qpa_intensity_factor_diagnostics(structure, values, model, [1],
                                             lambda p: p) == []


def _mo(ins: rx.Instrument) -> rx.Instrument:
    """``ins`` at Mo Kα's wavelengths, everything else unchanged."""
    out = ins.model_copy(deep=True)
    for line in out.source.lines:
        line.wavelength.value *= 0.7093 / 1.5406
    return out


def _shared_across_wavelengths(equations, instruments, **kw) -> list:
    from rietx.multi import _peak_equation_sharing_diagnostics
    from rietx.params.multi import MultiParameterTable

    mt = MultiParameterTable(Structure(phases=[brucite(peak_equations=equations)]),
                             instruments, **kw)
    return _peak_equation_sharing_diagnostics(mt)


def test_a_coefficient_shared_across_wavelengths_is_a_warning():
    """The maintainer's ruling of 2026-11-20 (option a): a coefficient in
    degrees shared by patterns at two wavelengths fires, naming the equation
    and the coefficient; one wavelength, an unshared coefficient or an
    intensity factor stays quiet."""
    from rietx.params.multi import SharingMap

    cu = _instrument()
    width = [_eq("lor_fwhm", "w*tan(theta) + x/cos(theta)", w=0.02, x=0.01)]
    (diag,) = _shared_across_wavelengths(width, [cu, _mo(cu)])
    assert diag.code == "PEAK_EQUATION_SHARED_ACROSS_WAVELENGTHS"
    assert diag.level == "warning"
    assert diag.where == ["phases.0.peak_equations.0"]
    assert "shares its coefficients w, x in degrees" in diag.message
    assert "a size-like term scales with λ" in diag.message
    assert ('SharingMap(per_histogram=["phases.0.peak_equations.0.w", '
            '"phases.0.peak_equations.0.x"])') in diag.suggestion
    assert diag.value == pytest.approx(cu.source.lines[0].wavelength.value
                                       / _mo(cu).source.lines[0].wavelength.value)
    # one wavelength
    assert _shared_across_wavelengths(width, [cu, cu.model_copy(deep=True)]) == []
    # each pattern its own coefficients
    assert _shared_across_wavelengths(
        width, [cu, _mo(cu)],
        sharing=SharingMap(per_histogram=["phases.*.peak_equations.*"])) == []
    # a pure number reads no wavelength
    assert _shared_across_wavelengths(
        [_eq("intensity_factor", "if(l == 0, 1, p)", p=0.7)], [cu, _mo(cu)]) == []


@pytest.mark.parametrize("build", [
    lambda text: __import__("rietx.params.expression", fromlist=["Expression"])
    .Expression(text),
    lambda text: __import__("rietx.schemas.parametric", fromlist=["ParametricEquation"])
    .ParametricEquation(name="a", target="phases.0.cell.a", basis="expression",
                        expression=text),
    lambda text: rx.Refinement(Structure(phases=[brucite()]), _instrument())
    .tie("phases.0.cell.a", expression=text),
], ids=["expression", "parametric", "tie"])
@pytest.mark.parametrize("text, func", [("a0*(1 + k*orbit_mean(l^2))", "orbit_mean"),
                                        ("a0 + k*harmonic(2, 0)", "harmonic")])
def test_a_reflection_function_outside_a_peak_equation_is_refused(build, text, func):
    """The lead's call of 2026-11-20: ``orbit_mean`` and ``harmonic`` read a
    reflection, so any other expression refuses them where it is parsed,
    rather than when something first evaluates them."""
    with pytest.raises((ValueError, ValidationError),
                       match=rf"{func}\(\) reads a reflection's hkl"):
        build(text)


# --- recovery: a width, a position and an intensity equation -------------------

TRUE = {"a": 0.15, "b": 0.06, "sq": 2.4e-5, "ln": -1.5e-3, "p": 0.7}
PATHS = {"a": "phases.0.peak_equations.0.a", "b": "phases.0.peak_equations.0.b",
         "p": "phases.0.peak_equations.1.p", "sq": "instrument.peak_equations.0.sq",
         "ln": "instrument.peak_equations.0.ln"}


def _recovery_models(values):
    phase = brucite(peak_equations=[
        rx.PeakEquation(target="lor_fwhm", expression="if(l == 0, a, b)*tan(theta)",
                        coefficients={"a": Parameter(value=values["a"], min=0.0),
                                      "b": Parameter(value=values["b"], min=0.0)}),
        _eq("intensity_factor", "if(l == 0, 1, p)", p=values["p"])])
    phase.scale.value = 2e-2
    ins = _instrument()
    ins.peak_equations = [_eq("shift", "sq*(two_theta - 60)^2 + ln*(two_theta - 60)",
                              sq=values["sq"], ln=values["ln"])]
    ins.background = rx.BackgroundChebyshev(coefficients=[Parameter(value=50.0)])
    return Structure(phases=[phase]), ins


def _simulate(structure, ins, seed, tt=None):
    tt = np.arange(10.0, 120.0, 0.02) if tt is None else tt
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = np.maximum(np.asarray(model.evaluate(table.decode(table.x0()))), 1.0)
    rng = np.random.default_rng(seed)
    return rx.PatternData(two_theta=model.tt.tolist(),
                          intensity=rng.poisson(y).astype(float).tolist(),
                          sigma=np.sqrt(y).tolist())


EQUATIONS = ["phases.*.scale", "instrument.background.*",
             "phases.*.peak_equations.*", "instrument.peak_equations.*"]
RECOVERY_PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("equations", EQUATIONS), rx.Stage("polish", EQUATIONS)])


def test_twelve_seeds_recover_every_coefficient_without_bias():
    """Mean z-score under 0.5 in size for every coefficient, from wrong starts.
    Measured ([dev], macOS arm64, 2026-11-19): mean z from -0.24 to +0.31."""
    from rietx.viz.plots import plot_result

    truth = _recovery_models(TRUE)
    zs = {k: [] for k in TRUE}
    for seed in range(1, 13):
        data = _simulate(*truth, seed)
        start = _recovery_models({"a": 0.08, "b": 0.10, "sq": 0.0, "ln": 0.0, "p": 1.0})
        result = rx.Refinement(*start, history=False).fit(data, plan=RECOVERY_PLAN)
        assert result.status == "converged", seed
        for k, path in PATHS.items():
            row = result.parameter(path)
            zs[k].append((row.value - TRUE[k]) / row.stderr)
        if seed == 1:
            OUT.mkdir(exist_ok=True)
            plot_result(result, path=OUT / "peak_equations_recovery.png")
            plot_result(result, path=OUT / "peak_equations_recovery_zoom.png",
                        two_theta_range=(55.0, 75.0))
    means = {k: float(np.mean(v)) for k, v in zs.items()}
    assert all(abs(m) < 0.5 for m in means.values()), means


def test_a_coefficient_follows_a_coordinate_in_a_joint_fit():
    """A Lorentzian coefficient w(T) = w0 + w1·T across four patterns, through
    a ParametricEquation whose target is the coefficient's path (the
    2026-11-19 ruling, consent item 5).  Measured ([dev], macOS arm64): w0
    -0.63 esd and w1 +0.94 esd from the truth."""
    from rietx.multi import MultiHistogramRefinement
    from rietx.params.multi import SharingMap
    from rietx.schemas.parametric import CoordinateTable, ParametricEquation

    temps, w0, w1 = [300.0, 500.0, 700.0, 900.0], 0.05, 1.5e-4

    def models(w):
        phase = brucite(peak_equations=[rx.PeakEquation(
            target="lor_fwhm", expression="w*tan(theta)",
            coefficients={"w": Parameter(value=w, min=0.0)})])
        phase.scale.value = 2e-2
        ins = _instrument()
        ins.background = rx.BackgroundChebyshev(coefficients=[Parameter(value=50.0)])
        return Structure(phases=[phase]), ins

    patterns = [_simulate(*models(w0 + w1 * t), 40 + k) for k, t in enumerate(temps)]
    structure, ins = models(0.08)
    ref = MultiHistogramRefinement(
        structure, [ins] * len(temps),
        sharing=SharingMap(shared=["instrument.profile.*"]),
        coordinates=CoordinateTable(columns={"T": temps}, units={"T": "K"}),
        variables={"w0": rx.Parameter(value=0.08, vary=True),
                   "w1": rx.Parameter(value=0.0, vary=True)},
        parametric=[ParametricEquation(name="w", target="phases.0.peak_equations.0.w",
                                       basis="expression", expression="w0 + w1*T")])
    result = ref.fit(patterns, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("width", ["phases.*.scale", "instrument.background.*", "vars.*"])]))
    assert result.status == "converged"
    rows = {p.path: p for p in result.parameters}
    for path, truth in (("vars.w0", w0), ("vars.w1", w1)):
        row = rows[path]
        assert abs(row.value - truth) < 2 * row.stderr, (path, row.value, row.stderr)
    for h, t in enumerate(temps):
        w = rows[f"hist.{h}.phases.0.peak_equations.0.w"].value
        assert w == pytest.approx(rows["vars.w0"].value + rows["vars.w1"].value * t,
                                  rel=1e-12)


# --- the ZrP2O7 shape: a calibration curve and a per-phase TCHZ, jointly ------
#
# Stinton & Evans (2007) §§ 4.1-4.2 refine a 2θ calibration curve over the
# whole pattern and give each phase its own six TCHZ terms, shared across the
# patterns of a parametric fit.  Here a Si standard (cell held) pins the curve
# and a brucite sample's cell is each pattern's own.

RAMP_TT = np.arange(12.0, 100.0, 0.02)
RAMP_TEMPS = [300.0, 400.0, 500.0, 600.0, 700.0]
CURVE = "1e-3*(sq*(two_theta - 54)^2/1000 + ln*(two_theta - 54))"
TCHZ_GAUSS = "1e-3*(u*tan(theta)^2 + v*tan(theta) + w)"
TCHZ_LOR = "1e-3*(x/cos(theta) + y*tan(theta))"
#: the curve passes 0.0105° at 15°, zero at 54° and 0.0059° at 90°, as the
#: milestone's ZrP2O7 row quotes it; v is negative, as in two of its phases
TRUE_CURVE = {"sq": 5.775, "ln": -0.04401}
TRUE_TCHZ = [{"u": 10.0, "v": -5.0, "w": 3.0, "x": 20.0, "y": 30.0},
             {"u": 6.0, "v": -2.0, "w": 5.0, "x": 40.0, "y": 15.0}]


def _tchz(values):
    return [rx.PeakEquation(target="gauss_fwhm_squared", expression=TCHZ_GAUSS,
                            coefficients={k: Parameter(value=values[k]) for k in "uvw"}),
            rx.PeakEquation(target="lor_fwhm", expression=TCHZ_LOR,
                            coefficients={k: Parameter(value=values[k]) for k in "xy"})]


def _ramp_structure(tchz, a, c):
    p = Parameter
    si = Phase(name="Si", space_group="F d -3 m:2",
               cell=Cell(a=p(value=5.4311), b=p(value=5.4311), c=p(value=5.4311),
                         alpha=p(value=90.0), beta=p(value=90.0), gamma=p(value=90.0)),
               atoms=[Atom(label="Si", species="Si", x=p(value=0.125), y=p(value=0.125),
                           z=p(value=0.125), biso=p(value=0.5))],
               scale=p(value=2e-3), peak_equations=_tchz(tchz[0]))
    sample = brucite(peak_equations=_tchz(tchz[1]))
    sample.cell.a.value = sample.cell.b.value = a
    sample.cell.c.value = c
    sample.scale.value = 1.5e-2
    return Structure(phases=[si, sample])


def _ramp_instrument(curve):
    ins = _instrument()
    ins.profile.w.value = 1e-6  # each phase carries its own TCHZ
    ins.background = rx.BackgroundChebyshev(coefficients=[Parameter(value=40.0)])
    ins.peak_equations = [_eq("shift", CURVE, **curve)]
    return ins


def _ramp_cell(t):
    return 3.147 * (1 + 1.2e-5 * (t - 300)), 4.769 * (1 + 3.0e-5 * (t - 300))


def test_a_calibration_curve_and_per_phase_tchz_are_recovered_jointly():
    """Each of the twelve coefficients within 2 esd on the pinned ramp (the
    WP's acceptance; worst 1.68 esd, [dev] macOS arm64, 2026-11-20).

    Over twelve ramps (seeds 1-12) every mean z-score was 0.50 or less in
    size, the largest Si's x (-0.50) and y (+0.50).  The worst |z| among the
    twelve went past 2 on two of the twelve ramps, as it can for twelve
    coefficients each scattering with sd 0.5-1.1, so the pin is one ramp and
    the means are the evidence.  The data are drawn at the closing window, so
    the fit closes there too: at the declared stages' windows the cut
    Lorentzian tails took a sample x 1.2 esd low on average.
    """
    from rietx.multi import MultiHistogramRefinement
    from rietx.params.multi import SharingMap
    from rietx.schemas.plan import CLOSING_WINDOW_TOL

    patterns = []
    for k, t in enumerate(RAMP_TEMPS):
        y = rx.Refinement(_ramp_structure(TRUE_TCHZ, *_ramp_cell(t)),
                          _ramp_instrument(TRUE_CURVE)).predict(RAMP_TT)
        y = np.maximum(y, 1.0)
        counts = np.random.default_rng([2107, k]).poisson(y).astype(float)
        patterns.append(rx.PatternData(two_theta=RAMP_TT, intensity=counts,
                                       sigma=np.sqrt(y)))
    start = [{"u": 5.0, "v": 0.0, "w": 5.0, "x": 10.0, "y": 10.0}] * 2
    ref = MultiHistogramRefinement(
        _ramp_structure(start, *_ramp_cell(300.0)),
        [_ramp_instrument({"sq": 0.0, "ln": 0.0}) for _ in RAMP_TEMPS],
        sharing=SharingMap(shared=["instrument.peak_equations.*"],
                           per_histogram=["phases.1.cell.*"]))
    base = ["phases.*.scale", "instrument.background.*", "phases.1.cell.*"]
    widths = [*base, "phases.*.peak_equations.*"]
    result = ref.fit(patterns, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", base[:2]), rx.Stage("cell", base),
        rx.Stage("widths", widths),
        rx.Stage("curve", [*widths, "instrument.peak_equations.*"])],
        closing_window_tol=CLOSING_WINDOW_TOL))
    assert result.status == "converged"
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result
    for h in (0, len(RAMP_TEMPS) - 1):
        plot_result(result.for_histogram(h), path=OUT / f"peak_equations_ramp_h{h}.png")
    rows = {p.path: p for p in result.parameters}
    truths = {f"instrument.peak_equations.0.{k}": v for k, v in TRUE_CURVE.items()}
    for ip, values in enumerate(TRUE_TCHZ):
        truths.update({f"phases.{ip}.peak_equations.0.{k}": values[k] for k in "uvw"})
        truths.update({f"phases.{ip}.peak_equations.1.{k}": values[k] for k in "xy"})
    z = {path: (rows[path].value - truth) / rows[path].stderr
         for path, truth in truths.items()}
    assert all(abs(v) < 2.0 for v in z.values()), z
