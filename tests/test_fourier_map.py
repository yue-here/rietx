"""The observed and difference Fourier maps of a Rietveld fit (WP-1901).

Two tiers, each with a positive and a negative arm.

* **Synthetic, fast.**  A noiseless NAC pattern computed by the model itself
  partitions back to I_obs = I_calc, so the complete model's difference map is
  zero to roundoff and its observed map is the model's own density.  The same
  pattern read by the model **minus Na1**, nothing refitted, puts Na1 at the
  top of the difference map: no refinement has had a chance to absorb it.
* **Real data, slow.**  The 11-BM NAC protocol of
  ``test_acceptance_nac.py`` refitted with one atom removed.  Here the scale
  and the displacement parameters do absorb part of the missing density, so
  the arm asserts what survives that: the top difference peak is the removed
  site's, above the complete model's highest peak.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import PatternData
from rietx.crystallography.lattice import direct_metric_tensor
from rietx.crystallography.symmetry import expand_positions, get_spacegroup
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.solve.fourier import (
    _fft_size,
    _min_distance,
    fourier_maps,
    fourier_maps_from_model,
)

DATA = Path(__file__).parent / "data"
NAC_CIF = DATA / "cod_1000236.cif"
WAVELENGTH = 0.4139090
NAC_SITES = {"Ca1", "Al1", "Na1", "F1", "F2", "F3"}


def _nac_model(structure, pattern=None, *, mode="rietveld", wavelength=WAVELENGTH,
               dispersion=False, tt_max=24.0):
    instrument = rx.Instrument.debye_scherrer(wavelength=wavelength)
    if not dispersion:
        instrument.source.dispersion = None
    if pattern is None:
        tt = np.linspace(2.0, tt_max, 6000)
        pattern = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, instrument, pattern, mode=mode)
    values = ParameterTable(structure, instrument).decode(
        ParameterTable(structure, instrument).x0())
    return model, values


def _nac_structure():
    s = rx.Structure.from_cif(str(NAC_CIF))
    s.phases[0].scale.value = 1e-6
    return s


@pytest.fixture(scope="module")
def nac_noiseless():
    """The complete NAC model's own pattern, evaluated exactly."""
    structure = _nac_structure()
    model, values = _nac_model(structure)
    y = model.evaluate(values)
    return PatternData(two_theta=model.tt.tolist(), intensity=np.asarray(y).tolist())


def _distance_to_site(maps, xyz, label_xyz):
    metric = direct_metric_tensor(*maps.cell)
    images = np.array(expand_positions(get_spacegroup(maps.space_group),
                                       np.asarray(label_xyz, dtype=np.float64)))
    return _min_distance(np.asarray(xyz), images, metric)


def _site(structure, label):
    atom = next(a for a in structure.phases[0].atoms if a.label == label)
    return (atom.x.value, atom.y.value, atom.z.value)


def test_fft_size_has_no_prime_factor_above_five():
    assert [_fft_size(n) for n in (1, 7, 31, 32, 33, 49, 121)] == [
        1, 8, 32, 32, 36, 50, 125]


def test_a_model_partitioning_its_own_pattern_leaves_no_difference_density(
        nac_noiseless):
    """Negative arm, exact: I_obs = I_calc, so every ΔF coefficient is zero.

    The observed map is then the model's own density, and its six highest
    peaks are NAC's six sites, one each.
    """
    structure = _nac_structure()
    model, values = _nac_model(structure, nac_noiseless)
    maps = fourier_maps_from_model(model, values, structure)
    assert maps.units == "e/Å³" and maps.phase_convention.endswith("exact")
    assert maps.n_reflections > 100
    assert np.abs(maps.difference.grid).max() < 1e-9 * maps.observed.sigma
    top = maps.observed.peaks[:6]
    assert {p.nearest_atom for p in top} == NAC_SITES
    assert max(p.nearest_distance for p in top) < 0.10


def test_the_atom_a_model_lacks_is_the_top_difference_peak(nac_noiseless):
    """Positive arm, no refit: the complete pattern read by NAC minus Na1."""
    full = _nac_structure()
    na1 = _site(full, "Na1")
    partial = _nac_structure()
    partial.phases[0].atoms = [a for a in partial.phases[0].atoms if a.label != "Na1"]
    model, values = _nac_model(partial, nac_noiseless)
    maps = fourier_maps_from_model(model, values, partial)
    top = maps.difference.peaks[0]
    assert _distance_to_site(maps, top.xyz, na1) < 0.10
    assert top.significance > 3.0
    # nothing is placed there, so the nearest *model* atom is far away
    assert top.nearest_distance > 1.5


def _self_partition(cif, **kw):
    """A structure's maps from its own noiseless pattern."""
    structure = rx.Structure.from_cif(str(DATA / cif))
    structure.phases[0].scale.value = 1e-6
    model, values = _nac_model(structure, **kw)
    pattern = PatternData(two_theta=model.tt.tolist(),
                          intensity=np.asarray(model.evaluate(values)).tolist())
    model, values = _nac_model(structure, pattern, **kw)
    return structure, model, values


def test_a_peak_split_by_a_mirror_between_two_grid_points_is_kept():
    """LaMnO₃'s La1 sits on the mirror at y = ¼, midway between points 13 and
    14 of a 54-point b axis, so the two read the same to the bit; a strict
    26-neighbour test kept neither and lost the heaviest atom (the review)."""
    structure, model, values = _self_partition("gsas2_bt1_lamno3.cif")
    maps = fourier_maps_from_model(model, values, structure, grid_step=0.142373)
    assert maps.observed.grid.shape == (45, 54, 40)
    la = [p for p in maps.observed.peaks if p.nearest_atom == "La1"]
    assert la and la[0].nearest_distance < 0.10
    assert maps.observed.peaks[0] is la[0]


def test_a_dispersive_source_states_its_phase_convention():
    """NAC at Cu Kα with f′ and f″ declared: the convention says so, and the
    observed map still finds the six sites (the f″ path, otherwise untested)."""
    structure, model, values = _self_partition(
        "cod_1000236.cif", wavelength=1.5406, dispersion=True, tt_max=150.0)
    maps = fourier_maps_from_model(model, values, structure)
    assert "f'' is declared" in maps.phase_convention
    top = maps.observed.peaks[:6]
    assert {p.nearest_atom for p in top} == NAC_SITES
    assert max(p.nearest_distance for p in top) < 0.10
    assert np.abs(maps.difference.grid).max() < 1e-9 * maps.observed.sigma


def test_a_le_bail_model_is_refused(nac_noiseless):
    structure = _nac_structure()
    model, values = _nac_model(structure, nac_noiseless, mode="lebail")
    with pytest.raises(ValueError, match="mode is 'lebail'"):
        fourier_maps_from_model(model, values, structure)


def test_an_unfitted_refinement_is_refused():
    structure = _nac_structure()
    ref = rx.Refinement(structure, rx.Instrument.debye_scherrer(wavelength=WAVELENGTH))
    with pytest.raises(RuntimeError, match="fit"):
        fourier_maps(ref)


# ---------------------------------------------------------------- real data
@pytest.fixture(scope="module")
def nac_fits():
    """The NAC protocol, refitted complete and without each of three atoms.

    One Le Bail pass seeds all four Rietveld fits, as in
    ``test_acceptance_nac.nac_rietveld``: the Le Bail cell and instrument,
    the CaF₂ impurity appended, ``mccusker_default`` plus a Biso stage.
    """
    from tests.test_acceptance_nac import LIMITS, _caf2_phase, build_nac_inputs

    data, structure, instrument = build_nac_inputs()
    ref_lb = rx.Refinement(structure, instrument)
    ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS)
    out = {}
    for removed in (None, "Na1", "F3", "Al1"):
        s2 = ref_lb.fitted_structure.model_copy(deep=True)
        i2 = ref_lb.fitted_instrument.model_copy(deep=True)
        s2.phases[0].scale.value = 1e-6
        if removed is not None:
            s2.phases[0].atoms = [a for a in s2.phases[0].atoms if a.label != removed]
        s2.phases.append(_caf2_phase())
        plan = rx.RefinementPlan.mccusker_default()
        plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
        plan.intermediate_ftol = 1e-6
        plan.closing_window_tol = 1e-3
        ref = rx.Refinement(s2, i2)
        result = ref.fit(data, plan=plan, two_theta_limits=LIMITS)
        assert result.status == "converged"
        out[removed] = fourier_maps(ref, 0)
    return structure, out


@pytest.mark.slow
@pytest.mark.xdist_group("nac")
def test_nac_observed_map_has_the_six_sites(nac_fits):
    _structure, maps = nac_fits
    top = maps[None].observed.peaks[:6]
    assert {p.nearest_atom for p in top} == NAC_SITES
    assert max(p.nearest_distance for p in top) < 0.10


@pytest.mark.slow
@pytest.mark.xdist_group("nac")
@pytest.mark.parametrize("removed", ["Na1", "F3", "Al1"])
def test_nac_minus_one_atom_shows_it_as_the_top_difference_peak(nac_fits, removed):
    """Positive arm on real data, each control the complete model's map.

    The top ΔF peak lies nearer the removed site than to any atom the full
    structure has, above 3σ of its map, and higher (e/Å³) than anything the
    complete model's map holds.  Measured distances to the site are in
    WP-1901's handover: the 0.10 Å bar holds for Al1 alone here.
    """
    structure, maps = nac_fits
    m = maps[removed]
    top = m.difference.peaks[0]
    metric = direct_metric_tensor(*m.cell)
    group = get_spacegroup(m.space_group)
    nearest = min(
        (_min_distance(np.asarray(top.xyz),
                       np.array(expand_positions(group, np.array(_site(structure, a.label)))),
                       metric), a.label)
        for a in structure.phases[0].atoms)
    assert nearest[1] == removed
    assert top.significance > 3.0
    assert top.height > maps[None].difference.peaks[0].height
    if removed == "Al1":
        assert nearest[0] < 0.10
