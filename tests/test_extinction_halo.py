"""The extinction screen and a declared container halo.

A capillary's amorphous halo is ~1° wide and routinely sits on a forbidden
position (Kapton at d ≈ 4.7 Å; a pyrochlore's d-glide-forbidden (200) at
d = a/2 ≈ 5 Å).  The remedy the manual documents is to declare it as a
:class:`~rietx.schemas.instrument.HumpComponent`.  The screen used to hold a
declared hump at whatever the caller's pre-fit left it at, and that pre-fit runs
in the absence-free lattice group, where the forbidden position is a reflection
that takes the halo's centre — so the hump came back too low and too wide, and
the true class was refuted by the halo it had been handed.

Synthetic data only: a pyrochlore-type A₂B₂O₇ (F d -3 m, origin 2) forward-
modelled at λ = 0.41388 Å with a flat background, plus a Gaussian halo of
0.1 % of the strongest line and 1° FWHM centred on (200).
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from rietx import (
    Instrument,
    PatternData,
    Refinement,
    auto_background,
    determine_extinction_symbol,
    pick_peaks,
)
from rietx.indexing.workflow import seed_widths, structure_from_candidate
from rietx.schemas.common import Parameter
from rietx.schemas.indexing import CellCandidate
from rietx.schemas.instrument import HUMP_FWHM_MIN, HumpComponent
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import Stage, resolve_plan

pytestmark = pytest.mark.xdist_group("extinction-halo")

A = 10.10
LAM = 0.41388
RANGE = (2.5, 14.0)
TOP = 9.0e4                 # counts in the strongest line
FLAT = 75.0                 # counts of flat background
D200 = A / 2.0
TT200 = float(np.degrees(2.0 * np.arcsin(LAM / (2.0 * D200))))


def _pyrochlore() -> Structure:
    def p(v):
        return Parameter(value=v)

    return Structure(phases=[Phase(
        name="pyrochlore", space_group="F d -3 m:2",
        cell=Cell(a=Parameter(value=A, min=0.1), b=Parameter(value=A, min=0.1),
                  c=Parameter(value=A, min=0.1), alpha=p(90.0), beta=p(90.0),
                  gamma=p(90.0)),
        atoms=[Atom(label="A", species="Y", x=p(0.5), y=p(0.5), z=p(0.5),
                    biso=p(0.4)),
               Atom(label="B", species="Ti", x=p(0.0), y=p(0.0), z=p(0.0),
                    biso=p(0.3)),
               Atom(label="O1", species="O", x=p(0.33), y=p(0.125),
                    z=p(0.125), biso=p(0.6)),
               Atom(label="O2", species="O", x=p(0.375), y=p(0.375),
                    z=p(0.375), biso=p(0.6))])])


def _reflections_near(ins, tt, centre, tol):
    """The pyrochlore's reflections carrying intensity within ``tol`` of
    ``centre``, every emission line, as the forward model compiles them."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure = _pyrochlore()
    grid = PatternData(two_theta=list(tt), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    out = []
    for pos, _w1, _w2, intensity in model.phase_peaks(0, table.decode(table.x0())):
        pos, intensity = np.asarray(pos), np.asarray(intensity)
        out += pos[(np.abs(pos - centre) < tol) & (intensity > 0.0)].tolist()
    return out


def _gauss(tt, centre, fwhm, height):
    sig = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return height * np.exp(-0.5 * ((tt - centre) / sig) ** 2)


@pytest.fixture(scope="module")
def bragg():
    """The forward-modelled pyrochlore, scaled to TOP, at two resolutions."""
    tt = np.round(np.arange(RANGE[0], RANGE[1] + 1e-9, 0.002), 4)
    out = {}
    for name, w in (("sync", None), ("lab", 0.1 ** 2)):
        ins = Instrument.debye_scherrer(wavelength=LAM)
        if w is not None:
            ins.profile.w.value = w
        y = np.asarray(Refinement(_pyrochlore(), ins, history=False)
                       .predict(two_theta=tt), dtype=float)
        y = y / y.max() * TOP
        # the d-glide is a statement about the reflection list, so it is asked
        # there.  The pattern at (200) is the neighbours' tails: a prediction
        # draws them at the closing windows, 1.4e-6 (sync) and 4.2e-6 (lab) of
        # TOP there with no reflection within 0.5° (WP-2002)
        assert not _reflections_near(ins, tt, TT200, 0.02), \
            "the model puts intensity on (200): the d-glide is not in force"
        out[name] = y
    return tt, out


def _data(tt, y, seed):
    obs = np.random.default_rng(seed).poisson(y + FLAT).astype(float)
    return PatternData(two_theta=list(tt), intensity=list(obs),
                       sigma=list(np.sqrt(np.maximum(obs, 1.0))))


def _candidate() -> CellCandidate:
    a = A * 0.99994                 # an index cell, a few 10⁻⁵ off
    return CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                         system="cubic", centring="F", volume=a ** 3)


def _screen(data, *, hump=None, free_hump=True):
    """The documented protocol: a seeded background, a ``profile_only`` Le Bail
    of the lattice group (with the declared hump freed in a last stage), then the
    screen on the fitted instrument and the refined cell."""
    ins = Instrument.debye_scherrer(wavelength=LAM)
    ins.background = auto_background(data, two_theta_limits=RANGE, seed=True).background
    plan = "profile_only"
    if hump is not None:
        position, height, fwhm = hump
        ins.extra_components = [HumpComponent(
            label="capillary halo", position=Parameter(value=position, unit="deg"),
            height=Parameter(value=height, min=0.0, unit="counts"),
            fwhm=Parameter(value=fwhm, min=HUMP_FWHM_MIN, unit="deg"))]
        if free_hump:
            plan = copy.deepcopy(resolve_plan("profile_only", "lebail"))
            plan.stages.append(Stage("extra_components",
                                     ["instrument.extra_components.*"]))
    peaks = pick_peaks(data, ins, two_theta_range=RANGE)
    ins, _seeded = seed_widths(ins, peaks)
    cand = _candidate()
    pre = Refinement(structure_from_candidate(cand), ins, history=False)
    pre.fit(data, mode="lebail", plan=plan, two_theta_limits=RANGE,
            telemetry=False)
    cell = tuple(float(v)
                 for v in pre.fitted_structure.phases[0].cell.lengths_angles())
    return determine_extinction_symbol(
        data, cand.model_copy(update={"cell": cell}), pre.fitted_instrument,
        peaks=peaks, two_theta_limits=RANGE)


def _fd(screen):
    return next(c for c in screen.candidates if c.symbol == "F d - -")


@pytest.mark.parametrize("seed", [1, 2])
def test_a_declared_halo_on_a_forbidden_position_does_not_refute_the_class(
        bragg, seed):
    """The bug: the declared hump was held at the lattice-group fit's values,
    which the (200) Le Bail line had biased, and ``F d - -`` was refuted at
    (200) on every seed.  Freed per class, like the background it joins, the
    hump takes the halo back and the right class is returned."""
    tt, y = bragg
    data = _data(tt, y["sync"] + _gauss(tt, TT200, 1.0, 1e-3 * TOP), seed)
    screen = _screen(data, hump=(round(TT200 + 0.3, 1), 50.0, 1.5))
    best = screen.best_or_none()
    assert best is not None and best.symbol == "F d - -", [
        (c.symbol, c.refuted_reason) for c in screen.candidates]
    assert "F d -3 m:2" in best.space_groups


def test_a_real_violation_under_a_declared_halo_still_refutes(bragg):
    """The positive arm: an instrument-width line at (200), as high as the halo,
    on top of it.  Freeing the hump must not explain it away."""
    tt, y = bragg
    fwhm = 0.035                       # the synthetic line width at (200)
    data = _data(tt, y["sync"] + _gauss(tt, TT200, 1.0, 1e-3 * TOP)
                 + _gauss(tt, TT200, fwhm, 1e-3 * TOP), 1)
    screen = _screen(data, hump=(round(TT200 + 0.3, 1), 50.0, 1.5))
    fd = _fd(screen)
    assert fd.refuted, fd
    assert (2, 0, 0) in [tuple(h) for h in fd.forbidden_hkl]


def test_a_freed_hump_cannot_narrow_onto_a_violation(bragg):
    """At a laboratory resolution (Bragg FWHM ≈ 0.1°, the hump's own schema floor)
    a hump freed per class could shrink onto a forbidden line and absorb it.  The
    screen floors a declared hump at the width ``HUMP_TOO_NARROW`` calls a
    background width, so the violation still refutes."""
    tt, y = bragg
    data = _data(tt, y["lab"] + _gauss(tt, TT200, 0.1, 1e-3 * TOP), 1)
    screen = _screen(data, hump=(4.70, 30.0, 0.3))
    fd = _fd(screen)
    assert fd.refuted, fd
    assert (2, 0, 0) in [tuple(h) for h in fd.forbidden_hkl]


def test_the_class_fit_frees_declared_humps_and_not_declared_peaks():
    from rietx.indexing.extinction import _screen_plan
    from rietx.schemas.instrument import PeakComponent

    ins = Instrument.debye_scherrer(wavelength=LAM)
    assert _screen_plan(ins).stages[0].turn_on == ["instrument.background.*"]
    ins.extra_components = [
        PeakComponent(label="impurity",
                      center=Parameter(value=6.0, min=5.9, max=6.1),
                      area=Parameter(value=10.0, min=0.0)),
        HumpComponent(label="halo", position=Parameter(value=5.0),
                      height=Parameter(value=50.0, min=0.0),
                      fwhm=Parameter(value=1.0, min=HUMP_FWHM_MIN))]
    assert _screen_plan(ins).stages[0].turn_on == [
        "instrument.background.*", "instrument.extra_components.1.*"]
