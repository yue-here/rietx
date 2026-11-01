"""The satellite arm's note names peaks on centring-forbidden positions (#795).

A residual peak on an integer (h k l) that the lattice's centring forbids —
(1 0 0) on an F lattice — is in neither of the arm's first two lists, since
``lattice_two_theta`` applies the centring.  It stays among the unexplained
peaks and is scored like any other, and the note now says how many sit on
such positions, from how many in range, and names the strongest with its
(h k l) and Δ/σ.  Found on the GSAS-II *Magnetic-IV* (Pr,Sr)MnO₃ pattern
(F m m m), whose strongest residual peak sits on the forbidden (1 0 0) while
the note said nothing about it; the cases here are synthetic, at a cell of
that shape.

Positive arm: peaks on F's (1 0 0) and (0 1 0) are named, the strongest by
its height.  Negative arms: the same F lattice with an unexplained peak away
from every forbidden position, and a primitive lattice, add nothing.  The
sentence changes no count and no ranking.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.lattice import d_spacings, two_theta_deg
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.satellites import analyse_satellites

LAMBDA = 2.4067
TT_MAX = 110.0
#: an orthorhombic cell with three different edges, so (1 0 0), (0 1 0) and
#: (0 0 1) sit at three different angles
CELL = (7.5, 7.8, 7.7, 90.0, 90.0, 90.0)
SENTENCE = "centring forbids"


def _phase(symbol: str, cell=CELL):
    P = rx.Parameter
    a, b, c, al, be, ga = cell
    return rx.Phase(
        name="M", space_group=symbol,
        cell=rx.Cell(a=P(value=a), b=P(value=b), c=P(value=c),
                     alpha=P(value=al), beta=P(value=be), gamma=P(value=ga)),
        atoms=[rx.Atom(label="Mn", species="Mn", x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.4))],
        scale=P(value=1.0))


def _grid() -> np.ndarray:
    return np.arange(10.0, TT_MAX, 0.02)


def _pattern(y=None) -> rx.PatternData:
    tt = _grid()
    if y is None:
        y = np.ones_like(tt)
    return rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.asarray(y).tolist())


def _setup(symbol: str, instrument=None, cell=CELL):
    instrument = instrument or rx.Instrument.constant_wavelength_neutron(
        LAMBDA, fwhm_deg=0.35)
    structure = rx.Structure(phases=[_phase(symbol, cell)])
    model = compile_model(structure, instrument, _pattern())
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    lam = float(model.line_lambdas(values)[0])
    ticks = np.asarray(model.phases[0].reflections.two_theta(cell, lam),
                       dtype=np.float64)
    return model, values, lam, ticks[np.isfinite(ticks)]


def _tt(hkl, lam: float) -> np.ndarray:
    return np.asarray(two_theta_deg(
        d_spacings(np.asarray(hkl, dtype=np.float64), *CELL), lam),
        dtype=np.float64)


def test_a_peak_on_a_centring_forbidden_position_is_named_with_its_hkl():
    """Positive arm: F's (1 0 0) and (0 1 0), the higher-angle one stronger."""
    model, values, lam, ticks = _setup("F m m m")
    tt = _tt([[1, 0, 0], [0, 1, 0]], lam)
    # neither is a tick: F's reflections are all-odd or all-even
    assert np.min(np.abs(ticks[:, None] - tt[None, :])) > 1.0
    arm = analyse_satellites(model, values, residual_two_theta=tt,
                             ticks=ticks,
                             residual_height_over_sigma=[35.0, 12.0])[0]
    assert arm.n_unexplained == 2
    assert arm.excess_on_absent_lattice_lines == 0
    assert "2 of them sit within the validity radius" in arm.note, arm.note
    assert "the F centring forbids" in arm.note
    # the strongest by Δ/σ, which here is not the lowest-angle peak
    assert tt[0] > tt[1]
    assert f"the strongest, 35.0σ at {tt[0]:.3f}°, is at (1 0 0)" in arm.note
    # the causes, magnetism among them on neutrons; (2 0 0) is an F lattice
    # vector, so λ/2 can put a line there
    assert "less centred than F" in arm.note
    assert "λ/2 contamination from the (2 0 0) line" in arm.note
    assert "impurity" in arm.note
    assert "such as (1 0 0) itself" in arm.note
    assert "four causes" in arm.note


def test_lambda_half_is_not_offered_where_the_group_extinguishes_2hkl():
    """λ/2 contamination needs a nuclear (2h 2k 2l) that exists.

    On F the centring alone passes 2·hkl always, but ``F d -3 m`` extinguishes
    (2 0 0) by its d glide, so a peak on the forbidden (1 0 0) has no line to
    be contaminated by; ``F m -3 m`` (no glide) keeps the cause, as does the
    ``F m m m`` case above.
    """
    cell = (8.5, 8.5, 8.5, 90.0, 90.0, 90.0)
    notes = {}
    for symbol in ("F d -3 m", "F m -3 m"):
        model, values, lam, ticks = _setup(symbol, cell=cell)
        tt = np.asarray(two_theta_deg(
            d_spacings(np.asarray([[1, 0, 0]], dtype=np.float64), *cell), lam),
            dtype=np.float64)
        arm = analyse_satellites(model, values, residual_two_theta=tt,
                                 ticks=ticks,
                                 residual_height_over_sigma=[30.0])[0]
        assert "the F centring forbids" in arm.note, arm.note
        notes[symbol] = arm.note
    assert "λ/2" not in notes["F d -3 m"]
    assert "three causes" in notes["F d -3 m"]
    assert "four causes" in notes["F m -3 m"]
    assert "λ/2 contamination from the (2 0 0) line" in notes["F m -3 m"]


def test_the_sentence_changes_no_count_and_no_ranking():
    """The note is the whole change: counts and candidates are untouched."""
    model, values, lam, ticks = _setup("F m m m")
    tt = _tt([[1, 0, 0], [0, 1, 0]], lam)
    with_h = analyse_satellites(model, values, residual_two_theta=tt,
                                ticks=ticks,
                                residual_height_over_sigma=[35.0, 12.0])[0]
    without = analyse_satellites(model, values, residual_two_theta=tt,
                                 ticks=ticks)[0]
    assert with_h.model_dump(exclude={"note"}) == \
        without.model_dump(exclude={"note"})
    # with no heights the note names the lowest-angle one and quotes no σ
    assert (f"the lowest-angle, at {tt[1]:.3f}°, is at (0 1 0)"
            in without.note), without.note
    assert "σ at" not in without.note


def test_on_x_rays_the_sentence_names_no_magnetic_cause():
    instrument = rx.Instrument.debye_scherrer(LAMBDA)
    model, values, lam, ticks = _setup("F m m m", instrument)
    tt = _tt([[1, 0, 0]], lam)
    arm = analyse_satellites(model, values, residual_two_theta=tt,
                             ticks=ticks, residual_height_over_sigma=[20.0])[0]
    assert arm.radiation == "xray"
    assert "the F centring forbids" in arm.note, arm.note
    assert "three causes" in arm.note
    assert "magnetic structure whose propagation vector" not in arm.note


def test_an_unexplained_peak_away_from_every_forbidden_position_adds_nothing():
    """Negative arm on the same F lattice: the sentence keys on the position.

    At 12° the peak's d is longer than any cell edge, so no integer (h k l)
    sits within the radius; it is still unexplained and still scored.
    """
    model, values, lam, ticks = _setup("F m m m")
    assert np.all(_tt([[1, 0, 0], [0, 1, 0], [0, 0, 1]], lam) > 17.0)
    arm = analyse_satellites(model, values, residual_two_theta=[12.0],
                             ticks=ticks,
                             residual_height_over_sigma=[40.0])[0]
    assert arm.n_unexplained == 1
    assert SENTENCE not in arm.note, arm.note


def test_a_primitive_lattice_adds_nothing():
    """Negative arm: on P every integer (h k l) is a lattice vector.

    The peaks sit at satellites of (0, 0, ½) — unexplained, so they reach the
    third list, where on F a forbidden position could have been tested.
    """
    from rietx.crystallography.satellites import satellite_reflections

    model, values, lam, ticks = _setup("P m m m")
    refl = satellite_reflections("P m m m", CELL, lam, TT_MAX, (0, 0, "1/2"),
                                 two_theta_min=10.0)
    tt = np.asarray(two_theta_deg(refl.d, lam), dtype=np.float64)
    tt = np.sort(tt[np.isfinite(tt) & (tt > 12.0) & (tt < TT_MAX - 1.0)])[:6]
    arm = analyse_satellites(model, values, residual_two_theta=tt,
                             ticks=ticks,
                             residual_height_over_sigma=np.full(len(tt), 30.0))[0]
    assert arm.n_unexplained >= 3, arm.note
    assert SENTENCE not in arm.note, arm.note


def test_heights_must_pair_with_the_peaks():
    model, values, lam, ticks = _setup("F m m m")
    with pytest.raises(ValueError, match="one per peak"):
        analyse_satellites(model, values, residual_two_theta=[18.0, 19.0],
                           ticks=ticks, residual_height_over_sigma=[5.0])


def test_the_report_names_the_strongest_forbidden_peak_end_to_end():
    """`Refinement.report()` hands the arm its Δ/σ, so the note quotes it.

    A nuclear F m m m profile plus two Gaussians the model cannot draw, on
    (1 0 0) and the weaker on (0 1 0); fitted on scale and background only.
    """
    instrument = rx.Instrument.constant_wavelength_neutron(LAMBDA,
                                                           fwhm_deg=0.35)
    structure = rx.Structure(phases=[_phase("F m m m")])
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    nuclear = np.asarray(compile_model(structure, instrument, _pattern())
                         .evaluate(values), dtype=np.float64)
    tt = _grid()
    t100, t010 = _tt([[1, 0, 0], [0, 1, 0]], LAMBDA)

    def bump(centre: float, height: float) -> np.ndarray:
        return height * np.exp(-4.0 * np.log(2.0) * ((tt - centre) / 0.35) ** 2)

    y = nuclear + bump(t100, 600.0) + bump(t010, 200.0) + 20.0
    ref = rx.Refinement(structure, instrument)
    ref.fit(_pattern(y), plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    ]))
    arm = ref.report().satellites[0]
    assert "the F centring forbids" in arm.note, arm.note
    assert "the strongest, " in arm.note and "is at (1 0 0)" in arm.note
