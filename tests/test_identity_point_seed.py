"""WP-1420 — a subgroup started at its parent's cell is a bet on a sign.

Issue #267's construction, fully synthetic: a cubic parent (Cu, ``F m -3 m``)
and the tetragonal subgroup of the fcc → bct relation (``I 4/m m m``, same
atom), present at 15 % of the parent's scale with c/(a√2) − 1 = +6.0e-3.  The
model starts the subgroup at the group–subgroup identity point
(a_t = a_c/√2, c_t = a_c), where every subgroup line sits under a parent line.

A fit started there must leave it on one side, and on this construction it
leaves on the wrong one: 42 of 42 cold fits, and 42 of 42 again with the
distortion's sign reversed in the data.  What
``docs/docs/guides/series.md`` § Start a subgroup off its parent's cell
tells a reader to do instead is pinned here: fit one pattern where the
subgroup is present twice, once from each side of the identity point, and keep
the lower Rwp.  The recipe's claim is the **ordering**, never a threshold:
the two starts land on opposite sides, and the lower Rwp is the true side.

Measured over seven noise draws at fractions 0.15, 0.25 and 0.40 of the
parent, for each sign of the true distortion (WP-1420's handover entry of
2026-11-04): the lower of the two picked the true sign in 84 of 84 pairs, at a
wrong-basin Rwp 2-3 %, 5-8 % and 14-17 % above the right one.  This file runs
the worst case, 0.15, on one draw, for both signs.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion
from rietx.schemas.structure import Atom, Cell, Phase, Structure

#: the module fixture's two fits stay on one worker (tests/CLAUDE.md § Shared
#: fixtures and xdist groups)
pytestmark = pytest.mark.xdist_group("identity-point-seed")

OUT = Path(__file__).parent / "output"

WAVELENGTH = 0.4139
A_PARENT = 3.6150
GRID = np.arange(4.0, 32.0 + 1e-9, 0.005)
#: the tetragonal strain in the construction's own variable: c/(a√2) − 1 is
#: (1 + t)/(1 − t/2) − 1 ≈ 1.5 t, so 4e-3 here is the issue's +6.0e-3; the
#: fixture runs it with each sign, so the recipe cannot pass by favouring one
TRUE_TET = 4.0e-3
#: the worst case of the three: the smallest Rwp gap between the two basins
SUBGROUP_FRACTION = 0.15
#: how far off the identity point each of the two starts sits, half the truth
OFF_IDENTITY = 2.0e-3
PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["phases.*.cell.*"]),
    rx.Stage("strain", ["phases.*.lor_strain"]),
])


def _cell(a: float, c: float) -> Cell:
    """A plan replaces the vary flags (WP-1208), so only the bounds are declared."""
    return Cell(a=Parameter(value=a, min=0.95 * a, max=1.05 * a),
                b=Parameter(value=a),
                c=Parameter(value=c, min=0.95 * c, max=1.05 * c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _phase(name: str, group: str, a: float, c: float, scale: float) -> Phase:
    return Phase(
        name=name, space_group=group, cell=_cell(a, c),
        atoms=[Atom(label="Cu", species="Cu", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0),
                    biso=Parameter(value=0.5, min=0.0, max=10.0))],
        scale=Parameter(value=scale, min=0.0),
        lor_strain=Parameter(value=2e-3, min=0.0, max=0.5, unit="deg"))


def _subgroup(scale: float, tet: float) -> Phase:
    """The bct cell of the fcc parent, ``tet`` off the identity point."""
    return _phase("subgroup_I4mmm", "I 4/m m m",
                  A_PARENT * (1.0 - tet / 2.0) / math.sqrt(2.0),
                  A_PARENT * (1.0 + tet), scale)


def _parent(scale: float) -> Phase:
    return _phase("parent_Fm-3m", "F m -3 m", A_PARENT, A_PARENT, scale)


def _instrument():
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = Dispersion()  # declared, not inherited (root CLAUDE.md)
    ins.profile.w.value = 2.0e-3
    ins.profile.x.value = 5.0e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (400.0, -60.0, 20.0)])
    return ins


def _tetragonality(result) -> float:
    p = {q.path: q.value for q in result.parameters}
    return p["phases.1.cell.c"] / (p["phases.1.cell.a"] * math.sqrt(2.0)) - 1.0


@pytest.fixture(scope="module", params=[+1, -1], ids=["true+", "true-"])
def two_starts(request):
    """One Poisson draw with the subgroup present, fitted from each side.

    Returns the true distortion and the two fits keyed by the start's sign.
    """
    true_tet = request.param * TRUE_TET
    truth = Structure(phases=[_parent(1.0), _subgroup(0.0, true_tet)])
    y = rx.Refinement(truth, _instrument(), history=False).predict(GRID)
    s_parent = 4.0e4 / float(np.max(y) - np.min(y))
    truth.phases[0].scale.value = s_parent
    truth.phases[1].scale.value = SUBGROUP_FRACTION * s_parent
    y = rx.Refinement(truth, _instrument(), history=False).predict(GRID)
    counts = np.random.default_rng(5).poisson(np.maximum(y, 0.0)).astype(float)
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())
    out = {}
    for sign in (+1, -1):
        start = Structure(phases=[
            _parent(0.9 * s_parent),
            _subgroup(0.02 * s_parent, sign * OFF_IDENTITY)])
        out[sign] = rx.Refinement(start, _instrument(), history=False).fit(
            data, plan=PLAN)
    return true_tet, out


def test_the_two_starts_end_on_opposite_sides(two_starts):
    """Each start keeps its own side: the identity point is between two basins."""
    _, fits = two_starts
    assert _tetragonality(fits[+1]) > 0.0
    assert _tetragonality(fits[-1]) < 0.0


def test_the_lower_rwp_is_the_true_side(two_starts):
    """The recipe's whole claim: Rwp, not the chain, picks the sign."""
    true_tet, fits = two_starts
    best = min(fits, key=lambda s: fits[s].statistics.rwp)
    assert np.sign(_tetragonality(fits[best])) == np.sign(true_tet)


def test_both_starts_are_drawn_for_inspection(two_starts):
    """Rwp hides locally-bad fits; the pair of pictures shows which basin split
    the subgroup's lines the way the data do."""
    import matplotlib.pyplot as plt

    from rietx.viz.plots import plot_result

    true_tet, fits = two_starts
    truth = "true_plus" if true_tet > 0 else "true_minus"
    OUT.mkdir(exist_ok=True)
    for sign, name in ((+1, "plus"), (-1, "minus")):
        path = OUT / f"identity_point_seed_{truth}_start_{name}.png"
        plot_result(fits[sign], path=str(path))
        plt.close("all")
        assert path.exists()
