"""Peak equations: a term on a reflection's width or position, or a factor on its
intensity, written in its hkl and angle (WP-2107).

Each target is held to a built-in with the same physics (no code shared with
what it certifies), the TCH partials the exact columns chain through to a
complex step, the coefficients to their truth over pinned noise seeds, and the
refusals to the message a user meets.  The derivative columns themselves are
``tests/test_cross_backend.py``'s ``peak_equations`` config.
"""

from __future__ import annotations

from fnmatch import fnmatch
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
    (lambda: _eq("lor_fwhm", "if(wavelength > 1, a, 0)", a=0.1), "frozen for the stage"),
    (lambda: _eq("lor_fwhm", "wavelength/cos(theta)", wavelength=0.1),
     "that name is the reflection's"),
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
    ([_eq("shift", "a*wavelength", a=0.1)], "in hkl or wavelength goes on Phase"),
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


@pytest.mark.parametrize(("equations", "warned"), [
    ({"lor_fwhm": ("y*wavelength/cos(theta)", "y")}, []),
    ({"lor_fwhm": ("x/cos(theta)", "x")}, [0]),
    # a strain term beside it is rightly shared; a size term in degrees there
    # is the known limit, silent too
    ({"lor_fwhm": ("y*wavelength/cos(theta) + w*tan(theta)", "yw")}, []),
    ({"lor_fwhm": ("y*wavelength/cos(theta) + x/cos(theta)", "yx")}, []),
    ({"lor_fwhm": ("y*wavelength/cos(theta)", "y"),
      "gauss_fwhm_squared": ("(x/cos(theta))^2", "x")}, [1]),
])
def test_an_equation_reading_wavelength_is_not_warned(equations, warned):
    """WP-2152, settled under the maintainer's "your call" of 2026-11-22: an
    equation that reads ``wavelength`` states its λ dependence, so it is
    silent, while another target's degree-only equation on the same phase
    still warns."""
    cu = _instrument()
    equations = [_eq(t, e, **dict.fromkeys(names, 0.01))
                 for t, (e, names) in equations.items()]
    found = _shared_across_wavelengths(equations, [cu, _mo(cu)])
    assert [d.where for d in found] == [[f"phases.0.peak_equations.{i}"]
                                        for i in warned]


#: two single-line sources, so each pattern has one λ and the built-in size
#: twin, which takes one number of degrees per pattern, is exact
LAMS = (0.41390, 0.71070)


def _joint_ycalc(phase, moved=None) -> list[np.ndarray]:
    """Each pattern's curve under one joint table at :data:`LAMS`, the
    coefficients shared.  ``moved`` overrides entries of pattern 1's values
    after the decode, on the model compiled at :data:`LAMS`."""
    from rietx.params.multi import MultiParameterTable

    instruments = []
    for lam in LAMS:
        ins = rx.Instrument.debye_scherrer(wavelength=lam)
        ins.source.dispersion = None
        ins.profile.w.value = 2e-3
        instruments.append(ins)
    structure = Structure(phases=[phase])
    mt = MultiParameterTable(structure, instruments)
    values = mt.decode(mt.x0())
    values[1].update(moved or {})
    tt = np.arange(4.0, 60.0, 0.005)
    blank = rx.PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    # each pattern compiles from its own structure, as the joint fit does, so
    # the twin's windows are sized at its converted size
    return [np.asarray(compile_model(s, ins, blank).evaluate(v))
            for s, ins, v in zip(mt.structures, instruments, values, strict=True)]


def test_a_size_term_reading_wavelength_is_lor_size_at_two_wavelengths():
    """WP-2152: ``y*wavelength/cos(theta)`` with one shared ``y`` is the
    built-in ``lor_size`` shared across the two patterns, which the joint
    table converts by λ_h/λ_0 (``params.multi.SIZE_LAMBDA_POWER``).  Written
    in degrees instead, one shared number is the wrong width at the second
    wavelength by the ratio of the two."""
    size = 0.05
    twin = brucite()
    twin.lor_size.value = size
    eq = brucite(peak_equations=[_eq("lor_fwhm", "y*wavelength/cos(theta)",
                                     y=size / LAMS[0])])
    for got, want in zip(_joint_ycalc(eq), _joint_ycalc(twin), strict=True):
        assert _rel(got, want) < 1e-12
    degrees = brucite(peak_equations=[_eq("lor_fwhm", "x/cos(theta)", x=size)])
    assert _rel(_joint_ycalc(degrees)[1], _joint_ycalc(twin)[1]) > 1e-2


def test_a_free_wavelength_moves_the_term_it_reads():
    """λ is a table entry (WP-1134), and the equation reads it from the
    values, never from the compile's copy.  Pattern 1's λ moved by 1 % in
    its values widens the equation's term with it: the twin is ``lor_size``
    at the moved λ's share, on the same compiled model."""
    size, lam = 0.05, LAMS[1] * 1.01
    path = "instrument.source.lines.0.wavelength"
    eq = brucite(peak_equations=[_eq("lor_fwhm", "y*wavelength/cos(theta)",
                                     y=size / LAMS[0])])
    got = _joint_ycalc(eq, {path: lam})[1]
    twin = brucite()
    twin.lor_size.value = size
    want = _joint_ycalc(twin, {path: lam, "phases.0.lor_size": size * lam / LAMS[0]})[1]
    assert _rel(got, want) < 1e-12
    # a term frozen at the compile's λ would stay at the old width
    frozen = _joint_ycalc(twin, {path: lam})[1]
    assert _rel(got, frozen) > 1e-3


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
                        two_theta_limits=(55.0, 75.0))
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


# --- a width equation inside LM's width rows (WP-2153) -------------------------

#: the floor test's synthetic LaB₆ (``tests/test_gaussian_width_floor.py``),
#: its Gaussian width carried by a phase TCHZ equation; U, V and W held, W on
#: its floor, so before WP-2153 no row held the width at all
ROW_TCHZ = "1e-3*(u*tan(theta)^2 + v*tan(theta) + w)"
ROW_LOR = "1e-3*(x/cos(theta) + y*tan(theta))"
ROW_TRUE = {"u": 0.9, "v": -0.2, "w": 0.025}
_ROW_B = ["phases.0.scale", "instrument.background.*"]
_ROW_EQ = "phases.0.peak_equations.0."
_ROW_TT = np.arange(3.0, 24.0, 0.005)


def _row_models(gauss: str, coefficients: dict, true: bool, **profile):
    from rietx.model.profiles.caglioti import _MIN_GAMMA_G2
    from tests.test_schemas import make_lab6

    s = make_lab6()
    s.phases[0].scale.value = 5e-4
    s.phases[0].peak_equations = [_eq("gauss_fwhm_squared", gauss, **coefficients)]
    ins = rx.Instrument.debye_scherrer(wavelength=0.4139)
    ins.profile.u.value = ins.profile.v.value = 0.0
    ins.profile.w.value = _MIN_GAMMA_G2
    for name, value in profile.items():
        getattr(ins.profile, name).value = value
    if true:
        ins.profile.x.value = 2e-3
        ins.background = rx.BackgroundChebyshev(coefficients=[Parameter(value=40.0)])
    else:
        ins.background = rx.BackgroundChebyshev.with_terms(1)
    return s, ins


def _row_pattern(gauss, coefficients, **profile) -> rx.PatternData:
    s, ins = _row_models(gauss, coefficients, True, **profile)
    model, table = _compiled(s.phases, ins, tt=_ROW_TT)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _row_fits(stem, pattern, gauss, plan, start, truth):
    """LM from ``start``, and the reference: TRF from ``truth``.

    Each is ``(equation coefficients, instrument profile values)``.  The
    reference starts at the truth because TRF from the bad start is no
    oracle here: nothing holds the total width inside its step either, and
    under rounding-level nudges of w's start (``1 + k·1e-14``) it stalled
    under the floor in 5 of 7 (Rwp 0.191-0.195, every esd ``None``, the case
    Linux CI met), where LM landed in 7 of 7 ([dev] macOS arm64, 2026-11-22).
    """
    from rietx.viz.plots import plot_result

    out = {}
    for solver, (coefficients, profile) in (("lm", start), ("trf", truth)):
        s, ins = _row_models(gauss, coefficients, False, **profile)
        out[solver] = rx.Refinement(s, ins, solver=solver, history=False).fit(
            pattern, plan=plan)
    OUT.mkdir(exist_ok=True)
    plot_result(out["lm"], path=OUT / f"{stem}_lm.png")
    ref = {p.path: p for p in out["trf"].parameters}
    assert all(p.stderr is not None for p in ref.values()), "the reference stalled"
    return {p.path: p for p in out["lm"].parameters}, ref, out["lm"]


@pytest.mark.parametrize("k", [0, -1, 3])
def test_a_free_equation_is_held_above_the_floor_and_lm_lands_on_the_minimum(k):
    """The stall the rows were built for, reached through an equation.

    Without the equation's term (main before WP-2153) w stepped to -0.150,
    Γ_G² sat under the floor at 19 of 19 reflections, and the fit stopped at
    Rwp 0.195 against 0.0416 at the minimum, u, v and w 27-427 esd from it.
    With it LM lands within 0.0025 esd of a fit started at the truth ([dev]
    macOS arm64, 2026-11-22); the bar is the WP's 0.1 esd.  ``k`` nudges the
    start by k·1e-14, two of the starts where TRF stalled (:func:`_row_fits`).
    """
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=_ROW_B),
        rx.Stage(name="eq_w", turn_on=_ROW_B + [_ROW_EQ + "w"]),
        rx.Stage(name="eq", turn_on=_ROW_B + [_ROW_EQ + "*", "instrument.profile.x"])])
    pattern = _row_pattern(ROW_TCHZ, ROW_TRUE)
    lm, ref, result = _row_fits(
        "peak_equation_width_rows", pattern, ROW_TCHZ, plan,
        start=({"u": 0.0, "v": 0.0, "w": 1.0 * (1 + k * 1e-14)}, {}),
        truth=(ROW_TRUE, {"x": 2e-3}))
    for c in "uvw":
        path = _ROW_EQ + c
        assert lm[path].stderr is not None, path
        assert abs(lm[path].value - ref[path].value) < 0.1 * ref[path].stderr, path
    assert result.stages[1].n_constraint_truncations >= 1
    assert not any(d.code == "PEAK_WIDTH_NOT_POSITIVE" for d in result.diagnostics)


def test_a_held_positive_term_lets_the_built_in_width_dip_where_the_total_does_not():
    """Direction 2: the built-in Γ_G² dips to -1.4e-5 deg² at the truth, and a
    held equation term of 3e-5 keeps the total above it.  Without the term in
    the row LM held the built-in sum at ε and ended at Rwp 0.143 against
    TRF's 0.0418, U, V, W and X 5-115 esd from TRF's.  With it LM lands
    within 3e-5 esd ([dev] macOS arm64, 2026-11-22)."""
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=_ROW_B),
        rx.Stage(name="w", turn_on=_ROW_B + ["instrument.profile.w"]),
        rx.Stage(name="profile", turn_on=_ROW_B + [f"instrument.profile.{k}"
                                                    for k in "uvwx"])])
    truth = {"u": 9e-4, "v": -2.4e-4, "w": 2e-6}
    pattern = _row_pattern("s", {"s": 3e-5}, **truth)
    lm, ref, _result = _row_fits("peak_equation_width_rows_held", pattern, "s", plan,
                                 start=({"s": 3e-5}, {"w": 1e-3}),
                                 truth=({"s": 3e-5}, {**truth, "x": 2e-3}))
    for k in "uvwx":
        path = f"instrument.profile.{k}"
        assert abs(lm[path].value - ref[path].value) < 0.1 * ref[path].stderr, path
    assert lm["instrument.profile.v"].value < 0.0


def _row_stage(gauss: str, coefficients: dict, free: list[str], lor=None):
    s, ins = _row_models(gauss, coefficients, False, u=1e-4, w=4e-5)
    if lor is not None:
        s.phases[0].peak_equations.append(_eq("lor_fwhm", ROW_LOR, **lor))
    model, table = _compiled(s.phases, ins, tt=_ROW_TT)
    table.set_vary(free, True)
    free_paths = set(table.free_paths)
    assert all(any(fnmatch(p, g) for p in free_paths) for g in free), free
    return model, table


def _total_widths(model, table, x):
    """Γ_G² before the floor (reflections on the data) and Γ_L (every
    finite reflection), summed from the forward model's own width terms."""
    v = table.decode(x)
    cp = model.phases[0]
    d, (tt,) = model._cell_block(cp, model._phase_cell(0, v), model.line_lambdas(v))
    tt = np.asarray(tt, dtype=np.float64)
    th = np.radians(0.5 * tt)
    t, sec = np.tan(th), 1.0 / np.cos(th)
    g2 = ((v["instrument.profile.u"] + v["phases.0.gauss_strain"]) * t * t
          + v["instrument.profile.v"] * t + v["instrument.profile.w"]
          + v["phases.0.gauss_size"] * sec * sec)
    gl = ((v["instrument.profile.x"] + v["phases.0.lor_size"]) * sec
          + (v["instrument.profile.y"] + v["phases.0.lor_strain"]) * t)
    extra_g2, extra_l = model._width_terms(0, v, tt, d)
    g2 = g2 + (0.0 if extra_g2 is None else np.asarray(extra_g2))
    gl = gl + (0.0 if extra_l is None else np.asarray(extra_l))
    on = (cp.win[0][:, 1] > cp.win[0][:, 0]) & np.isfinite(tt)
    return g2[on], gl[np.isfinite(tt)]


def _assert_rows_read(block, x, values, floor=0.0):
    np.testing.assert_allclose(np.sort(block.slack(x)),
                               np.sort(np.unique(values - floor)), rtol=1e-9, atol=1e-15)


def test_each_row_is_the_total_width_exactly_at_a_full_step():
    """The block is exact, not linearised: at a step of 100 % of every free
    coefficient the rows still read the forward model's total, the oracle
    for a map affine in its parameter (root CLAUDE.md, WP-1121)."""
    import rietx.optimize.least_squares as ls
    from rietx.model.profiles.caglioti import _MIN_GAMMA_G2

    model, table = _row_stage(ROW_TCHZ, ROW_TRUE,
                              [_ROW_EQ + "*", "phases.0.peak_equations.1.*"],
                              lor={"x": 2.0, "y": -0.5})
    x0 = table.x0()
    (g_block,) = ls.gaussian_width_inequalities(model, table, x0)
    (l_block,) = ls.lorentzian_width_inequalities(model, table, x0)
    # the coefficients' columns alone: the cell moves the angles, which the
    # rows freeze for the stage as they do for the built-in terms
    step = np.array([".peak_equations." in p for p in table.free_paths])
    assert step.sum() == 5
    for x in (x0, np.where(step, 2.0 * x0, x0)):
        g2, gl = _total_widths(model, table, x)
        _assert_rows_read(g_block, x, g2, _MIN_GAMMA_G2)
        _assert_rows_read(l_block, x, gl)


@pytest.mark.parametrize("expression, coefficients", [
    ("1e-3*u^2*tan(theta)", {"u": 0.5}),
    ("1e-3*abs(w)", {"w": 0.02}),
    ("1e-3*max(w, 0.01)", {"w": 0.02}),
    ("1e-3*w*w/(1 + w)", {"w": 0.02}),
])
def test_a_term_not_affine_in_a_free_coefficient_leaves_the_built_in_row(
        expression, coefficients, monkeypatch):
    """Not exact, so left out: the row is the built-in terms' alone, as it
    was before WP-2153, and ``PEAK_WIDTH_NOT_POSITIVE`` reports the total.
    Held, the same term is a constant at the frozen angles, and is in."""
    import rietx.optimize.least_squares as ls
    from rietx.model.peak_equations import is_affine
    from rietx.model.profiles.caglioti import _MIN_GAMMA_G2

    (name,) = coefficients
    model, table = _row_stage(expression, coefficients,
                              ["instrument.profile.w", _ROW_EQ + name])
    assert not is_affine(model.phases[0].peq.equations["gauss_fwhm_squared"])
    (with_eq,) = ls.gaussian_width_inequalities(model, table, table.x0())
    with monkeypatch.context() as m:
        m.setattr(ls, "_equation_width_rows", lambda *a, **k: None)
        (without,) = ls.gaussian_width_inequalities(model, table, table.x0())
    np.testing.assert_array_equal(with_eq.T, without.T)
    np.testing.assert_array_equal(with_eq.c, without.c)

    model, table = _row_stage(expression, coefficients, ["instrument.profile.w"])
    (held,) = ls.gaussian_width_inequalities(model, table, table.x0())
    g2, _gl = _total_widths(model, table, table.x0())
    _assert_rows_read(held, table.x0(), g2, _MIN_GAMMA_G2)


@pytest.mark.parametrize("expression, affine", [
    (ROW_TCHZ, True),
    (ROW_LOR, True),
    ("-(a - 2*b)/cos(theta)^2", True),
    ("orbit_mean(a*h^2*l^2)/d^2 + b", True),
    ("if(l == 0, a, b)*tan(theta)", True),
    ("a*b*tan(theta)", False),
    ("a^2", False),
    ("1/a", False),
    ("sqrt(a) + b", False),
    ("if(l == 0, a*b, b)", False),
])
def test_affinity_is_read_off_the_tree_and_agrees_with_the_gradient(expression, affine):
    """The structural test against its numeric reading: an affine equation's
    coefficient gradient is the same at the stored and at a far coefficient
    set.  The test is sufficient only, so a False is not checked numerically."""
    from rietx.model.peak_equations import compile_equation, gradient, is_affine
    from rietx.params.expression import Expression, names_in

    names = [n for n in names_in(Expression(expression, reflection=True).tree)
             if n in set("abuvwxy")]
    eq = _eq("lor_fwhm", expression, **{n: 0.3 + 0.1 * i for i, n in enumerate(names)})
    assert is_affine(compile_equation(eq, "phases.0", 0)) is affine
    if not affine:
        return
    model, table = _compiled([brucite(peak_equations=[eq])], _instrument())
    cp = model.phases[0]
    compiled = cp.peq.equations["lor_fwhm"]
    v = table.decode(table.x0())
    d, (tt, *_rest) = model._cell_block(cp, model._phase_cell(0, v),
                                        model.line_lambdas(v))
    far = dict(v)
    far.update({p: 7.0 * float(v[p]) - 3.0 for _n, p in compiled.paths})
    with np.errstate(all="ignore"):
        g0 = gradient(compiled, v, cp.peq.frame, d=d, theta=np.radians(0.5 * tt),
                      two_theta=tt)[1]
        g1 = gradient(compiled, far, cp.peq.frame, d=d, theta=np.radians(0.5 * tt),
                      two_theta=tt)[1]
    for a, b in zip(g0, g1, strict=True):
        np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-15)
