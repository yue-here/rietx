"""WP-2052 — a fit keeps each site's multiplicity from start to answer (#1088).

The toy is the issue's: Pnma, CW neutrons at 1.5 Å, 10-150° 2θ, noise-free.
The truth has O1 on the mirror at y = 1/4 (4c, 4 positions).  The model writes
it as a split pair, a general atom (8 positions) at occupancy 1/2, the same
density.  The data cannot resolve the split, so the cost is even in the
distance off the mirror and the solver stops on it, far inside the site
tolerance.  Before WP-2052 the next compile counted the site at 4 positions
with the occupancy unchanged: 10 O per cell in place of 12, χ²_red 23 and
O1 Biso -1.6 on noise-free data.
"""
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model, orbit_split_of
from rietx.refine import _multiplicity_kept_diagnostics
from rietx.viz.plots import plot_result

P = rx.Parameter
O1 = 2                                    # O1's index in the toy's atom list


def _toy(o1_y: float, occ: float = 1.0, free: bool = False) -> rx.Phase:
    def atom(lab, sp, x, y, z, b, o=1.0, v=False):
        return rx.Atom(label=lab, species=sp, x=P(value=x, vary=v),
                       y=P(value=y, vary=v), z=P(value=z, vary=v),
                       occ=P(value=o), biso=P(value=b))
    return rx.Phase(
        name="toy", space_group="P n m a", scale=P(value=0.016023),
        cell=rx.Cell(a=P(value=5.74), b=P(value=7.69), c=P(value=5.54),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=90.0)),
        atoms=[atom("A", "La", 0.05, 0.25, 0.99, 0.4),
               atom("Bs", "Mn", 0.0, 0.0, 0.5, 0.3),
               atom("O1", "O", 0.49, o1_y, 0.07, 0.6, occ, free),
               atom("O2", "O", 0.28, 0.04, 0.72, 0.6)])


def _instrument() -> rx.Instrument:
    instr = rx.Instrument.constant_wavelength_neutron(1.5, fwhm_deg=0.3)
    return instr.model_copy(update={"background": rx.BackgroundChebyshev(
        coefficients=[P(value=200.0)] + [P(value=0.0)] * 3)})


GRID = np.arange(10.0, 150.0, 0.05)
ALL = rx.Stage("all", ["phases.*.scale", "phases.*.atoms.*.dof.*",
                       "phases.*.atoms.*.biso"])


@pytest.fixture(scope="module")
def truth() -> rx.PatternData:
    y = rx.Refinement(rx.Structure(phases=[_toy(0.25)]), _instrument(),
                      history=False).predict(GRID)
    return rx.PatternData(two_theta=GRID.tolist(),
                          intensity=np.asarray(y).tolist())


def _fitted_oxygen(ref: rx.Refinement) -> float:
    """O per cell as the fit's own model counts it: occupancy × images."""
    split = orbit_split_of(ref._model)[0]
    return sum(a.occ.value * len(split[j][0])
               for j, a in enumerate(ref.structure.phases[0].atoms)
               if a.species == "O")


def _split_pair_fit(data, stages):
    ref = rx.Refinement(rx.Structure(phases=[_toy(0.27, occ=0.5, free=True)]),
                        _instrument(), history=False)
    res = ref.fit(data, plan=rx.RefinementPlan(stages=stages), telemetry=False)
    return ref, res


def test_a_split_pair_that_lands_on_its_mirror_keeps_its_atoms(truth):
    """The default plan (one stage, then the closing stage) returns 12 O.

    Reverting the freeze returns 10 O at χ²_red 23 and Biso -1.6 here, so this
    is the test that fails on a revert.
    """
    ref, res = _split_pair_fit(truth, [ALL])
    o1 = ref.structure.phases[0].atoms[O1]
    # the premise: the solver stopped on the mirror, inside the site tolerance
    assert abs(o1.y.value - 0.25) < 5e-5
    assert res.statistics.chi2 < 1e-6
    assert o1.biso.value == pytest.approx(0.6, abs=1e-4)
    assert _fitted_oxygen(ref) == pytest.approx(12.0)
    kept = [d for d in res.diagnostics if d.code == "SITE_MULTIPLICITY_KEPT"]
    assert [d.where for d in kept] == [[f"phases.0.atoms.{O1}"]]
    assert kept[0].value == pytest.approx(2.0)      # 0.5 × (8 - 4) atoms
    assert "8 × 0.5 = 4 atoms per cell" in kept[0].message
    assert "4 × 0.5 = 2 atoms per cell" in kept[0].message
    assert "occupancy 1," in kept[0].suggestion

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(res, path=str(out / "site_multiplicity_kept_fit.png"))
    plot_result(res, path=str(out / "site_multiplicity_kept_low.png"),
                two_theta_range=(10.0, 40.0))


def test_stage_boundaries_keep_the_split_too(truth):
    """Three declared stages and an occupancy stage: every compile keeps it.

    Before WP-2052 the occupancy stage walked O1's y to -818.75, a coordinate
    whose column the snapped compile had zeroed, and the result read 10 O at
    χ²_red 44.5.
    """
    stages = [rx.Stage("scale", ["phases.*.scale"]),
              rx.Stage("xyz", ["phases.*.scale", "phases.*.atoms.*.dof.*"]),
              ALL,
              rx.Stage("occ", [*ALL.turn_on, f"phases.*.atoms.{O1}.occ"])]
    ref, res = _split_pair_fit(truth, stages)
    o1 = ref.structure.phases[0].atoms[O1]
    assert abs(o1.y.value - 0.25) < 1e-3          # no walk
    assert o1.occ.value == pytest.approx(0.5, abs=1e-4)
    assert res.statistics.chi2 < 1e-6
    assert _fitted_oxygen(ref) == pytest.approx(12.0, abs=1e-3)
    # each stage starts at the cost the previous one ended at: no compile
    # between them changed the model
    for before, after in zip(res.stages, res.stages[1:]):
        assert after.cost_initial == pytest.approx(before.cost_final,
                                                   rel=1e-3, abs=1.0)


def test_a_joint_fit_keeps_the_split_too(truth):
    """The joint runner decides the split once per histogram, as ``fit`` does."""
    from rietx import MultiHistogramRefinement

    multi = MultiHistogramRefinement(
        rx.Structure(phases=[_toy(0.27, occ=0.5, free=True)]),
        [_instrument(), _instrument()])
    res = multi.fit([truth, truth], plan=rx.RefinementPlan(stages=[ALL]),
                    telemetry=False)
    o1 = multi.fitted_structures[0].phases[0].atoms[O1]
    assert abs(o1.y.value - 0.25) < 5e-5
    assert res.statistics.chi2 < 1e-6
    kept = [d for d in res.diagnostics if d.code == "SITE_MULTIPLICITY_KEPT"]
    assert [d.where for d in kept] == [[f"phases.0.atoms.{O1}"]]


@pytest.mark.parametrize(("occ", "delta", "o_per_cell"), [
    (0.5, 4e-5, 10), (0.5, 6e-5, 12), (1.0, 4e-5, 12), (1.0, 6e-5, 12)])
def test_a_fresh_compile_decides_from_the_coordinates(truth, occ, delta,
                                                      o_per_cell):
    """``predict()`` outside a fit: the split follows y across the tolerance.

    On a mirror the image moves 2δ, so the effective radius is 5e-5.  At
    occupancy 1/2 the general split is the truth's density, and the split
    jumps there: this is the discontinuity a fit no longer crosses.  At
    occupancy 1 the site would put two atoms at one place, so ``Refinement``
    construction merges it onto the mirror (WP-1991, ``SITE_TWINS_MERGED``,
    within 5e-4) and both offsets read the truth.  Before WP-1991 the 6e-5
    offset counted 16 O.
    """
    ref = rx.Refinement(rx.Structure(phases=[_toy(0.25 + delta, occ=occ)]),
                        _instrument(), history=False)
    y = np.asarray(ref.predict(GRID))
    obs = np.asarray(truth.intensity)
    rwp = float(np.sqrt(np.sum((obs - y) ** 2 / obs) / np.sum(obs)))
    assert (rwp < 1e-4) == (o_per_cell == 12)
    model = compile_model(ref.structure, ref.instrument, truth)
    split = orbit_split_of(model)[0]
    assert sum(a.occ.value * len(split[j][0])
               for j, a in enumerate(ref.structure.phases[0].atoms)
               if a.species == "O") == pytest.approx(o_per_cell)


def test_the_finding_is_silent_when_no_split_changed():
    structure = rx.Structure(phases=[_toy(0.27, occ=0.5)])
    model = compile_model(structure, _instrument(),
                          rx.PatternData(two_theta=GRID.tolist(),
                                         intensity=[1.0] * len(GRID)))
    assert _multiplicity_kept_diagnostics(structure, orbit_split_of(model)) == []


def test_a_split_for_another_structure_is_refused():
    structure = rx.Structure(phases=[_toy(0.27)])
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=[1.0] * len(GRID))
    split = orbit_split_of(compile_model(structure, _instrument(), data))
    with pytest.raises(ValueError, match="orbit split for 2 phases"):
        compile_model(structure, _instrument(), data, orbit_split=split * 2)
    with pytest.raises(ValueError, match="orbit split for 3 atoms"):
        compile_model(structure, _instrument(), data,
                      orbit_split=[split[0][:3]])


def test_a_trial_made_inside_a_call_refits_at_its_split():
    """A profile-interval refit is a trial: it inherits the call's split."""
    ref = rx.Refinement(rx.Structure(phases=[_toy(0.27, occ=0.5)]),
                        _instrument(), history=False)
    assert ref._trial(record=False)._orbit_split is None
    assert ref._decide_orbit_split()
    trial = ref._trial(record=False)
    assert [[len(r) for r, _ in p] for p in trial._orbit_split] == \
        [[len(r) for r, _ in p] for p in ref._orbit_split]
    assert not trial._decide_orbit_split()        # it reuses, never re-decides


def test_a_site_that_leaves_its_special_position_gets_its_full_orbit():
    """Kept images are never dropped, and missing ones are never withheld.

    A rigid body's pose can carry an atom off a mirror.  Four images of a
    general position are no structure, so the compile takes the eight the
    coordinates need, as it did before WP-2052, and nothing is reported.
    """
    data = rx.PatternData(two_theta=GRID.tolist(), intensity=[1.0] * len(GRID))
    on = rx.Structure(phases=[_toy(0.25, occ=0.5)])
    off = rx.Structure(phases=[_toy(0.27, occ=0.5)])
    special = orbit_split_of(compile_model(on, _instrument(), data))
    assert len(special[0][O1][0]) == 4
    model = compile_model(off, _instrument(), data, orbit_split=special)
    assert len(orbit_split_of(model)[0][O1][0]) == 8
    assert _multiplicity_kept_diagnostics(off, orbit_split_of(model)) == []


def test_the_one_atom_reading_is_offered_only_where_it_fits():
    """A full general atom stopped on a mirror is 2 atoms at one place.

    Its fitted content is 8 × 1 = 8, and one atom on the 4c position holds 4,
    so the suggestion names that and offers only the split reading.
    """
    split = [[*[(r, t) for r, t in
                orbit_split_of(compile_model(
                    rx.Structure(phases=[_toy(0.27)]), _instrument(),
                    rx.PatternData(two_theta=GRID.tolist(),
                                   intensity=[1.0] * len(GRID))))[0]]]]
    phase = _toy(0.27)
    phase.atoms[O1].y.value = 0.25 + 1e-6      # past the construction gate
    found = _multiplicity_kept_diagnostics(rx.Structure.model_construct(
        phases=[phase]), split)
    assert [d.where for d in found] == [[f"phases.0.atoms.{O1}"]]
    assert "occupancy 2" not in found[0].suggestion
    assert "8 atoms per cell" in found[0].suggestion
