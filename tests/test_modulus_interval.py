"""WP-2060: the profile interval of a moment modulus on its dead column.

A powder pattern's magnetic intensity goes as m², so a modulus refined to
m = 0 has a vanishing column there.  Its esd is then the inverse of a
curvature that is nearly zero and reads 1e4-1e5 μ_B.  Before WP-2060
``profile_interval`` stepped in units of that esd, overshot the end by six
orders of magnitude, and Brent's tolerance (a thousandth of the step) put the
end on the fitted value: a zero-width interval with ``fit_is_minimum=True``.

**The fixture** is issue #1075's repro 2: the round-number Pnma perovskite of
``tests/test_magnetic_solve.py``, Mn on 4b, A-type group 62.448, neutrons at
2.4 Å, simulated with **no** moment and Poisson noise, and refined with one Mn
moment along **a**, its angles held.  Seeds 3, 4 and 8 all end on the dead
column (macOS arm64, ``[dev]``): m within 1e-7 μ_B of 0, esd 1.5e4-2.4e5 μ_B.
A fit and its profile cost about 7 s, so seed 4 runs in the fast tier and the
other two are ``slow``.

The modulus's sign is a symmetry of this model (one moment block in the
phase), so the profile keeps m ≥ 0, sits on that bound and is one-sided.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase, Structure
from rietx.strategy.parameter_interval import _sign_is_unseen

pytestmark = pytest.mark.xdist_group("modulus-interval")

OUT = __import__("pathlib").Path(__file__).parent / "output"
GRID = np.arange(8.0, 130.0, 0.05)
SITE = (0.0, 0.0, 0.5)
MOD = "phases.0.atoms.1.moment.dof0"
ANGLES = ["phases.0.atoms.1.moment.dof1", "phases.0.atoms.1.moment.dof2"]


def _phase(moment=None, magnetic=None, scale=1.0) -> Phase:
    def at(label, sp, xyz, moment=None):
        return Atom(label=label, species=sp, x=P(value=xyz[0]), y=P(value=xyz[1]),
                    z=P(value=xyz[2]), biso=P(value=0.4), moment=moment)
    cell = Cell(a=P(value=5.74, vary=True), b=P(value=7.70, vary=True),
                c=P(value=5.54, vary=True), alpha=P(value=90.0), beta=P(value=90.0),
                gamma=P(value=90.0))
    return Phase(name="perovskite", space_group="P n m a", cell=cell, scale=P(value=scale),
                 atoms=[at("A1", "La", (0.05, 0.25, 0.99)), at("Mn1", "Mn", SITE, moment),
                        at("O1", "O", (0.48, 0.25, 0.07)), at("O2", "O", (0.31, 0.04, 0.72))],
                 magnetic_symmetry=magnetic)


def _magnetic() -> MagneticSymmetry:
    group = next(c for c in candidates("P n m a", SITE, (0, 0, 0))
                 if c.bns_number == "62.448").group
    ops, cent = group.xyz_strings()
    return MagneticSymmetry(operations=list(ops), centerings=list(cent))


def _instrument() -> rx.Instrument:
    return rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.35)


def _fitted(seed: int):
    """Repro 2 for one seed: the fit, its data and the modulus row."""
    ins = _instrument()
    ins.background.coefficients[0].value = 40.0
    unit = np.asarray(rx.Refinement(Structure(phases=[_phase()]), ins,
                                    history=False).predict(GRID)) - 40.0
    scale = 2.0e4 / unit.max()
    y_true = np.asarray(rx.Refinement(Structure(phases=[_phase(scale=scale)]), ins,
                                      history=False).predict(GRID))
    y = np.random.default_rng(seed).poisson(y_true).astype(float)
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0)).tolist())
    model = _phase(moment=Moment.from_values((0.5, 0.0, 0.0), "Mn3+", vary=True),
                   magnetic=_magnetic(), scale=0.95 * scale)
    ref = rx.Refinement(Structure(phases=[model]), _instrument(), history=False)
    ref.hold(ANGLES)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("cell", ["phases.*.cell.*", "instrument.zero_shift",
                          "instrument.profile.w"]),
        rx.Stage("moment", [MOD])])
    result = ref.fit(data, plan=plan, telemetry=False)
    return ref, data, result


@pytest.mark.parametrize("seed", [
    pytest.param(3, marks=pytest.mark.slow), 4, pytest.param(8, marks=pytest.mark.slow)])
def test_a_modulus_on_its_dead_column_gets_an_interval_that_contains_zero(seed):
    """Non-zero width, m = 0 inside, and the walk found its end by threshold."""
    ref, data, result = _fitted(seed)
    row = next(p for p in result.parameters if p.path == MOD)
    # the dead column, as the issue measured it
    assert abs(row.value) < 1e-5 and row.stderr > 1e3
    interval = ref.profile_interval(data, MOD)
    assert interval.one_sided and interval.at_bound is not True
    assert (interval.lower, interval.lower_stop) == (0.0, "bound")
    assert interval.upper_stop == "threshold"
    # an end near 0.05-0.07 μ_B, against an esd six orders larger
    assert 0.01 < interval.upper < 0.5
    assert interval.fit_is_minimum
    # the end is a measured probe, at the one-sided threshold to the
    # Brent tolerance, and no probe crossed below m = 0
    (end,) = [p for p in interval.points if p.value == interval.upper]
    assert end.delta_chi2 == pytest.approx(interval.delta_chi2_cut, rel=0.02)
    assert all(p.value > 0.0 for p in interval.points)
    if seed == 4:
        import matplotlib.pyplot as plt

        from rietx.viz.plots import plot_result

        OUT.mkdir(exist_ok=True)
        plot_result(result, path=str(OUT / "modulus_dead_column.png"))
        plt.close("all")


def test_the_sign_is_kept_only_where_the_data_cannot_see_it():
    """One moment block, or free angles: kept.  Two blocks, angles held: both signs."""
    one = rx.Refinement(Structure(phases=[_phase(
        moment=Moment.from_values((0.5, 0.0, 0.0), "Mn3+", vary=True),
        magnetic=_magnetic())]), _instrument(), history=False)
    assert _sign_is_unseen(one._working_table(), MOD, set())

    from tests import test_magnetic_solve as T

    two = rx.Refinement(Structure(phases=[T.two_site(
        m1=Moment.from_values((3.5, 0.0, 0.0), "Mn3+", vary=True),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+", vary=True),
        magnetic=_magnetic())]), _instrument(), history=False)
    table = two._working_table()
    mn2 = "phases.0.atoms.1.moment"
    assert not _sign_is_unseen(table, f"{mn2}.dof0", set())
    assert _sign_is_unseen(table, f"{mn2}.dof0", {f"{mn2}.dof1", f"{mn2}.dof2"})
    assert not _sign_is_unseen(table, "phases.0.scale", set())
