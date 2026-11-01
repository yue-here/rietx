"""Quantitative phase analysis (Hill & Howard ZMV weight fractions).

Reference masses (IUPAC standard atomic weights, via gemmi):
La 138.905, B 10.811, Ca 40.078, F 18.998 g/mol.
"""

import math
from pathlib import Path

import numpy as np
import pytest

from rietx import (
    Atom,
    Cell,
    Instrument,
    Parameter,
    PatternData,
    Phase,
    Refinement,
    Structure,
)
from rietx.crystallography.attenuation import (
    linear_attenuation,
    mass_attenuation,
    total_cross_section,
)
from rietx.model.forward import compile_model
from rietx.optimize.qpa import (
    atomic_weight,
    brindley_correction,
    brindley_tau,
    phase_zmv,
    weight_fractions,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Provenance
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.results import (
    PhaseQuantity,
    QuantitativePhaseAnalysis,
    RefinementResult,
    Statistics,
)

from .test_schemas import make_lab6


def _caf2_phase() -> Phase:
    return Phase(
        name="CaF2", space_group="F m -3 m", cell=Cell.cubic(5.4631),
        atoms=[
            Atom(label="Ca", species="Ca2+", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="F", species="F1-", x=Parameter(value=0.25),
                 y=Parameter(value=0.25), z=Parameter(value=0.25)),
        ],
    )


def _atoms(phase: Phase):
    return [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
            for a in phase.atoms]


def test_atomic_weight_strips_charge():
    assert math.isclose(atomic_weight("La"), 138.905, abs_tol=0.1)
    assert math.isclose(atomic_weight("Ca2+"), 40.078, abs_tol=0.1)
    assert math.isclose(atomic_weight("F1-"), 18.998, abs_tol=0.1)
    with pytest.raises(ValueError):
        atomic_weight("Zz")


def test_atomic_weight_valence_species():
    # Waasmaier-Kirfel valence keys: a greedy 2-letter parse would read "Cval"
    # as the non-element "Cv"; the fallback must resolve C and Si.
    assert math.isclose(atomic_weight("Cval"), 12.011, abs_tol=0.1)
    assert math.isclose(atomic_weight("Siva"), 28.085, abs_tol=0.1)


def test_the_species_parser_is_crystallographys_and_qpa_re_exports_it():
    """One parser, in a module that needs nothing of rietx (#590 review).

    The structure viewer and the geometry read a species with it; living in
    ``optimize.qpa`` it pulled qpa's schemas and attenuation tables across
    WP-1505's split.  ``optimize.qpa.element_symbol`` still answers, as the
    same function.
    """
    import ast
    import inspect

    from rietx.crystallography import species
    from rietx.optimize import qpa

    assert qpa.element_symbol is species.element_symbol
    assert qpa._parse_species is species._parse_species
    tree = ast.parse(inspect.getsource(species))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom) and n.module and not n.level}
    relative = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]
    assert imported <= {"__future__", "re", "gemmi"} and not relative


def test_zmv_lab6():
    phase = make_lab6().phases[0]
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    # LaB6: La on 1a (mult 1) + B on 6f (mult 6); one formula unit per cell.
    assert zmv.z == 1
    assert math.isclose(zmv.cell_mass, 138.905 + 6 * 10.811, abs_tol=0.5)
    assert math.isclose(zmv.molar_mass, zmv.cell_mass, rel_tol=1e-12)
    assert math.isclose(zmv.cell_volume, 4.1566 ** 3, rel_tol=1e-6)
    assert math.isclose(zmv.zmv, zmv.cell_mass * zmv.cell_volume, rel_tol=1e-12)


def test_zmv_caf2():
    phase = _caf2_phase()
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    # CaF2: Ca on 4a (mult 4) + F on 8c (mult 8); four formula units per cell.
    assert zmv.z == 4
    assert math.isclose(zmv.cell_mass, 4 * 40.078 + 8 * 18.998, abs_tol=0.5)
    assert math.isclose(zmv.molar_mass, 40.078 + 2 * 18.998, abs_tol=0.5)
    assert math.isclose(zmv.cell_volume, 5.4631 ** 3, rel_tol=1e-6)


def test_zmv_partial_occupancy_falls_back_to_one_formula_unit():
    phase = _caf2_phase()
    phase.atoms[1].occ.value = 0.3  # F count 0.3·8 = 2.4 → composition does not reduce
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    assert zmv.z == 1
    assert math.isclose(zmv.molar_mass, zmv.cell_mass, rel_tol=1e-12)
    assert math.isclose(zmv.cell_mass, 4 * 40.078 + 0.3 * 8 * 18.998, abs_tol=0.5)


def test_weight_fractions_no_covariance():
    # Two phases, equal Z·M·V, scales 3:1 → fractions 0.75/0.25.
    w, sc, si = weight_fractions([100.0, 100.0], [3.0, 1.0])
    assert np.allclose(w, [0.75, 0.25])
    assert sc is None and si is None


def test_weight_fractions_zero_covariance_reports_none():
    # An all-zero scale block (no scale was freed) is absence of information,
    # not σ(W) = 0.
    w, sc, si = weight_fractions([100.0, 100.0], [1.0, 1.0], np.zeros((2, 2)))
    assert np.allclose(w, [0.5, 0.5])
    assert sc is None and si is None


def test_weight_fractions_zero_scales_raises():
    with pytest.raises(ValueError):
        weight_fractions([100.0, 100.0], [0.0, 0.0], np.eye(2))


def test_weight_fractions_correlated_differs_from_independent():
    # Strongly (positively) correlated scales: the correlated ratio propagation
    # partly cancels, so σ_corr must differ from the naive independent σ.
    scale_cov = np.array([[4.0, 3.5], [3.5, 4.0]])
    w, sigma_corr, sigma_indep = weight_fractions([100.0, 100.0], [1.0, 1.0], scale_cov)
    assert np.allclose(w, [0.5, 0.5])
    assert not np.allclose(sigma_corr, sigma_indep)
    assert np.all(sigma_corr < sigma_indep)  # positive correlation shrinks σ(W)


def test_physical_covariance_block_diagonal_matches_stderr():
    from rietx import Instrument
    from rietx.params.vector import ParameterTable

    structure = make_lab6()
    structure.phases.append(_caf2_phase())
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["phases.*.scale"], True)
    theta = table.x0()
    free = table.free_paths
    i0, i1 = free.index("phases.0.scale"), free.index("phases.1.scale")
    corr = np.eye(len(theta))
    corr[i0, i1] = corr[i1, i0] = 0.7
    stderr_internal = np.full(len(theta), 0.3)

    esds = table.stderr_physical(theta, stderr_internal, corr)
    cov = table.physical_covariance(theta, stderr_internal, corr,
                                    ["phases.0.scale", "phases.1.scale"])
    # The block's diagonal is exactly the reported per-parameter esds squared,
    # so QPA σ(W) inherits the same conditioning by construction.
    assert math.isclose(math.sqrt(cov[0, 0]), esds["phases.0.scale"], rel_tol=1e-9)
    assert math.isclose(math.sqrt(cov[1, 1]), esds["phases.1.scale"], rel_tol=1e-9)
    assert cov[0, 1] != 0.0  # scales are correlated off the diagonal


def _qpa_fixture() -> QuantitativePhaseAnalysis:
    from rietx.schemas.results import MicroabsorptionCorrection

    return QuantitativePhaseAnalysis(phases=[
        PhaseQuantity(name="LaB6", weight_fraction=0.6, weight_fraction_stderr=0.01,
                      scale=2.0, z=1, molar_mass=203.77, cell_mass=203.77,
                      cell_volume=71.82, zmv=14634.9,
                      weight_fraction_corrected=0.62, brindley_tau=0.97,
                      mu_cm=1136.0, mu_r=0.045, particle_radius_um=0.4),
        PhaseQuantity(name="CaF2", weight_fraction=0.4, weight_fraction_stderr=None,
                      scale=1.0, z=4, molar_mass=78.07, cell_mass=312.30,
                      cell_volume=163.05, zmv=50920.0,
                      weight_fraction_corrected=0.38, brindley_tau=1.02,
                      mu_cm=304.0, mu_r=0.012, particle_radius_um=0.4),
    ], microabsorption=MicroabsorptionCorrection(wavelength=1.5406,
                                                 mu_mean_cm=700.0))


def test_qpa_json_round_trip():
    qpa = _qpa_fixture()
    assert QuantitativePhaseAnalysis.model_validate_json(qpa.model_dump_json()) == qpa


# -- compute_qpa microabsorption wiring -----------------------------------

def _two_phase_decoded(radii):
    from rietx.optimize.qpa import compute_qpa

    structure = make_lab6()
    structure.phases.append(_caf2_phase())
    for phase, r in zip(structure.phases, radii, strict=True):
        phase.particle_radius_um = r
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    return structure, table.decode(table.x0()), compute_qpa


def test_compute_qpa_brindley_applied():
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    base = compute_qpa(structure, values, wavelength=None)
    assert qpa.microabsorption is not None and qpa.microabsorption_skipped is None
    rows = {r.name: r for r in qpa.phases}
    la, ca = rows["LaB6"], rows["CaF2"]
    # uncorrected numbers are untouched by the correction...
    assert [r.weight_fraction for r in qpa.phases] == \
           [r.weight_fraction for r in base.phases]
    # ...and the corrected ones move the absorbing phase (LaB6, µ≈1136/cm) up
    assert la.brindley_tau < 1.0 < ca.brindley_tau
    assert la.weight_fraction_corrected > la.weight_fraction
    assert ca.weight_fraction_corrected < ca.weight_fraction
    assert math.isclose(sum(r.weight_fraction_corrected for r in qpa.phases), 1.0,
                        abs_tol=1e-12)
    assert 1080.0 < la.mu_cm < 1180.0 and 290.0 < ca.mu_cm < 315.0
    assert math.isclose(la.mu_r, la.mu_cm * 0.4e-4, rel_tol=1e-12)
    assert ca.mu_cm < qpa.microabsorption.mu_mean_cm < la.mu_cm


def test_compute_qpa_brindley_skipped_partial_radii():
    structure, values, compute_qpa = _two_phase_decoded([0.4, None])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    assert qpa.microabsorption is None
    assert "CaF2" in qpa.microabsorption_skipped
    assert all(r.weight_fraction_corrected is None for r in qpa.phases)


def test_compute_qpa_brindley_skipped_no_wavelength():
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=None)
    assert qpa.microabsorption is None
    assert "wavelength" in qpa.microabsorption_skipped


def test_compute_qpa_brindley_skipped_mu_unavailable():
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=13.0)  # outside 2-120 keV
    assert qpa.microabsorption is None
    assert "attenuation unavailable" in qpa.microabsorption_skipped


def test_compute_qpa_no_radii_stays_silent():
    structure, values, compute_qpa = _two_phase_decoded([None, None])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    assert qpa.microabsorption is None and qpa.microabsorption_skipped is None


# -- a phase with no reflection in the fitted range (WP-1958, #954) ---------

def _three_phase_decoded(radii):
    from rietx.optimize.qpa import compute_qpa

    structure = make_lab6()
    structure.phases.append(_caf2_phase())
    extra = _caf2_phase()
    extra.name = "CaF2_out"
    structure.phases.append(extra)
    for phase, r in zip(structure.phases, radii, strict=True):
        phase.particle_radius_um = r
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    return structure, table.decode(table.x0()), compute_qpa


def test_an_unmeasured_phase_has_no_fraction_and_leaves_the_sum():
    """Absent rather than zero, and the others are fractions of the phases
    seen: exactly the fractions the model without it gives."""
    structure, values, compute_qpa = _three_phase_decoded([None] * 3)
    qpa = compute_qpa(structure, values, unmeasured=[2])
    seen, _, compute = _two_phase_decoded([None, None])
    two = compute(seen, values)
    assert qpa.phases[2].weight_fraction is None
    assert qpa.phases[2].weight_fraction_stderr is None
    assert qpa.phases[2].scale == values["phases.2.scale"]   # the row stays
    assert [r.weight_fraction for r in qpa.phases[:2]] == \
           [r.weight_fraction for r in two.phases]
    assert qpa.unmeasured_phases == ["CaF2_out"]
    # the positive arm: every phase counted, the same call gives three numbers
    full = compute_qpa(structure, values)
    assert all(r.weight_fraction is not None for r in full.phases)
    assert full.unmeasured_phases == []
    assert full.phases[0].weight_fraction < qpa.phases[0].weight_fraction


def test_brindley_is_skipped_with_an_unmeasured_phase():
    """τ compares each phase's µ with the mixture's volume-mean µ̄, which
    needs every phase's fraction: with one absent the correction cannot run,
    and says so rather than averaging over the phases seen."""
    structure, values, compute_qpa = _three_phase_decoded([0.4, 0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406, unmeasured=[2])
    assert qpa.microabsorption is None
    assert "CaF2_out" in qpa.microabsorption_skipped
    assert all(r.weight_fraction_corrected is None for r in qpa.phases)
    # the positive arm: every phase measured, the same radii run it
    full = compute_qpa(structure, values, wavelength=1.5406)
    assert full.microabsorption is not None and full.microabsorption_skipped is None


def test_the_skipped_brindley_advice_follows_its_reason():
    """With radii supplied and a phase unmeasured, "supply particle_radius_um"
    points the wrong way: the advice is the range or the phase (#1103).  The
    positive arm, a phase missing its radius, keeps the old advice."""
    from rietx.optimize.qpa import microabsorption_diagnostics

    structure, values, compute_qpa = _three_phase_decoded([0.4, 0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406, unmeasured=[2])
    (diag,) = microabsorption_diagnostics(qpa)
    assert diag.code == "MICROABSORPTION_SKIPPED"
    assert "Widen the fitted range" in diag.suggestion
    assert "CaF2_out" in diag.suggestion
    assert "particle_radius_um" not in diag.suggestion.replace(
        "the radii were supplied", "")
    structure, values, compute_qpa = _three_phase_decoded([0.4, None, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    (diag,) = microabsorption_diagnostics(qpa)
    assert diag.suggestion.startswith("Supply particle_radius_um")


def test_the_skipped_brindley_advice_names_a_phase_still_missing_its_radius():
    """One radius is enough to record the skip, so "the radii were supplied"
    was said of a model with a phase still missing its radius (#1103, round
    2).  The message and the advice name that phase; the positive arm, every
    radius given, still says the radii were supplied."""
    from rietx.optimize.qpa import microabsorption_diagnostics

    structure, values, compute_qpa = _three_phase_decoded([0.4, None, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406, unmeasured=[2])
    (diag,) = microabsorption_diagnostics(qpa, structure)
    assert "radii were supplied" not in diag.suggestion
    assert diag.suggestion.endswith("Supply particle_radius_um on CaF2 too.")
    assert diag.message.endswith("No particle_radius_um on phase(s) CaF2 either.")
    structure, values, compute_qpa = _three_phase_decoded([0.4, 0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406, unmeasured=[2])
    (diag,) = microabsorption_diagnostics(qpa, structure)
    assert diag.suggestion.endswith("The radii were supplied.")
    assert "either" not in diag.message


def test_a_lone_phase_seen_is_whole_by_definition_with_no_esd():
    structure, values, compute_qpa = _three_phase_decoded([None] * 3)
    cov = np.diag([1e-10, 1e-10])
    qpa = compute_qpa(structure, values, cov[:1, :1], unmeasured=[1, 2])
    assert qpa.phases[0].weight_fraction == 1.0
    assert qpa.phases[0].weight_fraction_stderr is None
    assert qpa.unmeasured_phases == ["CaF2", "CaF2_out"]


def test_an_unmeasured_row_round_trips_and_says_so_in_the_table():
    from rietx.io.exporters import qpa_table_csv

    structure, values, compute_qpa = _three_phase_decoded([None] * 3)
    qpa = compute_qpa(structure, values, unmeasured=[2])
    assert QuantitativePhaseAnalysis.model_validate_json(qpa.model_dump_json()) == qpa
    text = qpa_table_csv(qpa)
    assert "relative to the phases measured; CaF2_out not measured" in text
    (row,) = [line for line in text.splitlines() if line.startswith("CaF2_out,")]
    assert row.split(",")[1] == ""


# -- µR fence diagnostics --------------------------------------------------

def test_mu_r_fence_fires_exactly_when_it_should():
    from rietx.optimize.qpa import BRINDLEY_MU_R_FENCE, microabsorption_diagnostics

    # In regime: LaB6 µ≈1136/cm, R=0.4 µm → µR≈0.045 < 0.05 — no diagnostic.
    structure, values, compute_qpa = _two_phase_decoded([0.4, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    assert max(r.mu_r for r in qpa.phases) < BRINDLEY_MU_R_FENCE
    assert microabsorption_diagnostics(qpa) == []

    # Push LaB6 past the fence (R=1 µm → µR≈0.11); CaF2 stays inside.
    structure, values, compute_qpa = _two_phase_decoded([1.0, 0.4])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    diags = microabsorption_diagnostics(qpa)
    assert len(diags) == 1
    d = diags[0]
    assert d.code == "BRINDLEY_OUTSIDE_REGIME" and d.level == "warning"
    assert d.where == ["LaB6"] and "µR" in d.message
    # the correction is still reported (never silently dropped)…
    assert all(r.weight_fraction_corrected is not None for r in qpa.phases)
    # …with the offending µR travelling on the result object
    assert {r.name: r.mu_r for r in qpa.phases}["LaB6"] > BRINDLEY_MU_R_FENCE


def test_skipped_correction_surfaces_as_diagnostic():
    from rietx.optimize.qpa import microabsorption_diagnostics

    structure, values, compute_qpa = _two_phase_decoded([0.4, None])
    qpa = compute_qpa(structure, values, wavelength=1.5406)
    diags = microabsorption_diagnostics(qpa)
    assert len(diags) == 1 and diags[0].code == "MICROABSORPTION_SKIPPED"
    assert "CaF2" in diags[0].message


def test_result_with_qpa_round_trip():
    stats = Statistics(rwp=0.05, rp=0.04, rexp=0.03, chi2=2.0, gof=1.4,
                       n_points=1000, n_free_parameters=8)
    result = RefinementResult(
        status="converged", mode="rietveld", parameters=[], statistics=stats,
        provenance=Provenance(package_version="test"), qpa=_qpa_fixture())
    assert RefinementResult.model_validate_json(result.model_dump_json()) == result


# -- attenuation coefficients (microabsorption input) --------------------

# Published anchors: NIST mass attenuation coefficients of Hubbell & Seltzer
# (1995), NISTIR 5632, at exactly 8.000 keV (tables at
# physics.nist.gov/PhysRefData/XrayMassCoef/ElemTab/zNN.html).  The bundled
# McMaster (1969) tabulation tracks them to ~2.5 % for Z >= 9; light elements
# are worse (B -7 %, O -3.6 % — a known weakness of the McMaster photoelectric
# fits at low Z) but contribute little to any phase's mu.
_NIST_8KEV = {"F": 16.02, "Al": 50.33, "Si": 64.68, "Ca": 172.6,
              "Ni": 49.52, "La": 352.9}
_LAM_8KEV = 12398.4198 / 8000.0


def test_mass_attenuation_matches_nist():
    for el, ref in _NIST_8KEV.items():
        assert math.isclose(mass_attenuation(el, _LAM_8KEV), ref, rel_tol=0.04)
    assert math.isclose(mass_attenuation("B", _LAM_8KEV), 2.346, rel_tol=0.08)
    assert math.isclose(mass_attenuation("O", _LAM_8KEV), 11.63, rel_tol=0.05)


def test_linear_attenuation_common_phases():
    # Cross-check the composition -> mu plumbing against values hand-computed
    # from the NIST elemental mu/rho above: mass-fraction mixing gives
    # mu(LaB6) ≈ 1116-1137 1/cm and mu(CaF2) ≈ 300-307 1/cm at Cu Ka1.
    lam = 1.5405929
    mu_lab6 = linear_attenuation({"La": 1.0, "B": 6.0}, 4.1566 ** 3, lam)
    mu_caf2 = linear_attenuation({"Ca": 4.0, "F": 8.0}, 5.4631 ** 3, lam)
    assert 1080.0 < mu_lab6 < 1180.0
    assert 290.0 < mu_caf2 < 315.0


def test_attenuation_edge_interval_raises():
    # Ni K edge at 8.3328 keV sits inside a ~2 % tabulation interval; asking
    # for mu there must refuse rather than smear the edge, while Cu Ka (well
    # below the edge) stays fine.
    with pytest.raises(ValueError, match="absorption edge of Ni"):
        total_cross_section("Ni", 12398.4198 / 8300.0)
    assert mass_attenuation("Ni", 1.5405929) > 0


def test_attenuation_missing_element_and_band():
    with pytest.raises(KeyError, match="McMaster"):
        total_cross_section("Po", 1.5406)
    with pytest.raises(ValueError, match="outside the tabulated"):
        total_cross_section("Si", 13.0)


def test_zmv_element_counts_and_density():
    phase = _caf2_phase()
    zmv = phase_zmv(phase.space_group, phase.cell.lengths_angles(), _atoms(phase))
    assert zmv.element_counts == {"Ca": 4.0, "F": 8.0}
    # CaF2 X-ray density ~3.18 g/cm3
    assert math.isclose(zmv.density, 3.18, rel_tol=0.01)


# -- Brindley particle-absorption factors ---------------------------------

def test_brindley_tau_reproduces_published_values():
    """tau must match both published representations of Brindley's table.

    Anchors: the quadratic 1 - 1.450x + 1.426x^2 (FullProf QPA formulation,
    Rodriguez-Carvajal's ILL notes; valid |x| <= 0.1) and the exponential fit
    -0.00229 + 2.054*exp(-(x + 0.50356)/0.69525) (MAUD, Lutterotti's QPA
    course notes).  The two published fits themselves differ by ~1 %, which
    sets the reproduction tolerance.
    """
    for x in np.linspace(-0.1, 0.1, 21):
        quad = 1.0 - 1.450 * x + 1.426 * x * x
        assert math.isclose(brindley_tau(x), quad, rel_tol=0.015)
    for x in np.linspace(-0.1, 0.5, 25):
        expfit = -0.00229 + 2.054 * math.exp(-(x + 0.50356) / 0.69525)
        assert math.isclose(brindley_tau(x), expfit, rel_tol=0.02)


def test_brindley_tau_limits():
    assert brindley_tau(0.0) == 1.0
    # continuous across the series/closed-form switch at |2x| = 0.05: the
    # difference over 2e-9 in x is slope-dominated (~3e-9), no visible jump
    assert abs(brindley_tau(0.025 + 1e-9) - brindley_tau(0.025 - 1e-9)) < 1e-8
    xs = np.linspace(-0.3, 1.5, 200)
    taus = np.array([brindley_tau(x) for x in xs])
    assert np.all(np.diff(taus) < 0)          # monotone decreasing
    assert np.all(taus > 0)                   # never a sign flip
    assert brindley_tau(-0.05) > 1.0          # less absorbing than matrix


def test_brindley_correction_direction_and_conservation():
    # Two phases, equal measured fractions; phase 0 strongly more absorbing.
    # The correction must *raise* the absorbing phase (its intensity was
    # suppressed) and lower the other, sum staying 1.
    w, taus, mu_bar = brindley_correction(
        [0.5, 0.5], densities=[4.7, 3.2], mus=[1100.0, 300.0],
        radii_um=[0.4, 0.4])
    assert math.isclose(w.sum(), 1.0, abs_tol=1e-12)
    assert w[0] > 0.5 > w[1]
    assert taus[0] < 1.0 < taus[1]
    assert 300.0 < mu_bar < 1100.0
    # zero contrast -> no correction, whatever the radius
    w2, taus2, _ = brindley_correction([0.3, 0.7], [3.0, 3.0],
                                       [500.0, 500.0], [5.0, 5.0])
    assert np.allclose(w2, [0.3, 0.7])
    assert np.allclose(taus2, 1.0)


def test_phase_particle_radius_field():
    phase = _caf2_phase()
    assert phase.particle_radius_um is None    # default: no correction
    phase.particle_radius_um = 0.75
    from rietx import Structure
    s = Structure(phases=[phase])
    assert Structure.model_validate_json(s.model_dump_json()) == s
    with pytest.raises(Exception):
        phase.particle_radius_um = -1.0


# -- two-phase synthetic acceptance --------------------------------------

_WAVELENGTH = 1.5406


def _two_phase_truth(la_scale: float, caf2_scale: float):
    structure = make_lab6()
    structure.phases[0].scale.value = la_scale
    caf2 = _caf2_phase()
    caf2.scale.value = caf2_scale
    structure.phases.append(caf2)
    ins = Instrument.debye_scherrer(wavelength=_WAVELENGTH)
    ins.profile.w.value = 3e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (30.0, -4.0, 1.0)])
    return structure, ins


def _true_weight_fractions(structure) -> np.ndarray:
    k = np.array([phase_zmv(p.space_group, p.cell.lengths_angles(), _atoms(p)).zmv
                  for p in structure.phases])
    s = np.array([p.scale.value for p in structure.phases])
    a = s * k
    return a / a.sum()


def test_two_phase_synthetic_qpa():
    truth, ins = _two_phase_truth(la_scale=6e-4, caf2_scale=4e-4)
    w_true = _true_weight_fractions(truth)

    tt = np.arange(15.0, 90.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    # refine from perturbed scales (both start equal) and a slightly-off cell
    start, start_ins = _two_phase_truth(la_scale=1e-3, caf2_scale=1e-3)
    start.phases[0].cell.a.value += 0.01
    ref = Refinement(start, start_ins)
    result = ref.fit(data, plan="mccusker_default")

    assert result.status == "converged"
    assert result.qpa is not None and len(result.qpa.phases) == 2
    fractions = {row.name: row for row in result.qpa.phases}
    assert math.isclose(sum(r.weight_fraction for r in result.qpa.phases), 1.0, abs_tol=1e-9)

    for ip, name in enumerate(("LaB6", "CaF2")):
        row = fractions[name]
        assert row.weight_fraction_stderr is not None and row.weight_fraction_stderr > 0
        # recovered fraction within the propagated σ (with a modest multiplier
        # for the single noisy realisation) — and never wildly off
        assert abs(row.weight_fraction - w_true[ip]) < 4 * row.weight_fraction_stderr
        assert abs(row.weight_fraction - w_true[ip]) < 0.03

    # The wired σ(W) must come from the *correlated* scale block, not the naive
    # independent propagation from σ(S) alone — the two scales correlate through
    # the shared intensity/background, so the two must differ here.
    fitted = ref.fitted_structure
    zmv = np.array([phase_zmv(p.space_group, p.cell.lengths_angles(), _atoms(p)).zmv
                    for p in fitted.phases])
    scales = np.array([result.parameter(f"phases.{i}.scale").value for i in range(2)])
    sig_s = np.array([result.parameter(f"phases.{i}.scale").stderr for i in range(2)])
    _, sigma_indep, _ = weight_fractions(zmv, scales, np.diag(sig_s ** 2))
    sigma_wired = np.array([r.weight_fraction_stderr for r in result.qpa.phases])
    assert not np.allclose(sigma_wired, sigma_indep, rtol=1e-3)

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    result.plot(path=str(out / "qpa_two_phase.png"))


def test_two_phase_synthetic_brindley_correction():
    """Microabsorption injected at generation must be undone by the correction.

    The pattern is synthesized with each phase's intensity multiplied by its
    true Brindley factor (that *is* the microabsorption effect at the
    intensity level), so the refined scales absorb tau and the uncorrected
    Hill-Howard fractions are biased away from truth in a known direction:
    LaB6 (µ≈1136/cm at Cu Kα) suppressed, CaF2 (µ≈304/cm) inflated.  The
    corrected fractions must land back on the truth.  Radii differ per phase
    (0.4 / 1.5 µm) and keep both µR inside the 0.05 fence.
    """
    from rietx import Stage
    from rietx.crystallography.attenuation import linear_attenuation
    from rietx.optimize.qpa import BRINDLEY_MU_R_FENCE

    radii = {"LaB6": 0.4, "CaF2": 1.5}
    truth, ins = _two_phase_truth(la_scale=6e-4, caf2_scale=4e-4)
    w_true = _true_weight_fractions(truth)

    # true tau at the true composition (volume-weighted solid mu_bar)
    zmvs = [phase_zmv(p.space_group, p.cell.lengths_angles(), _atoms(p))
            for p in truth.phases]
    mus = np.array([linear_attenuation(z.element_counts, z.cell_volume, _WAVELENGTH)
                    for z in zmvs])
    rho = np.array([z.density for z in zmvs])
    r_cm = np.array([radii[p.name] for p in truth.phases]) * 1e-4
    v = (w_true / rho) / np.sum(w_true / rho)
    mu_bar_true = float(np.dot(v, mus))
    tau_true = np.array([brindley_tau(x) for x in (mus - mu_bar_true) * r_cm])
    assert tau_true[0] < 1.0 < tau_true[1]
    assert np.all(mus * r_cm < BRINDLEY_MU_R_FENCE)

    # synthesize with tau folded into the scales — the refinement sees a
    # pattern whose LaB6 intensity is genuinely suppressed by absorption
    for phase, tau in zip(truth.phases, tau_true, strict=True):
        phase.scale.value *= tau
    tt = np.arange(15.0, 90.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    start, start_ins = _two_phase_truth(la_scale=1e-3, caf2_scale=1e-3)
    for phase in start.phases:
        phase.particle_radius_um = radii[phase.name]
    ref = Refinement(start, start_ins)
    result = ref.fit(data, plan="mccusker_default")
    assert result.status == "converged"

    qpa = result.qpa
    assert qpa.microabsorption is not None and qpa.microabsorption_skipped is None
    assert not any(d.code == "BRINDLEY_OUTSIDE_REGIME" for d in result.diagnostics)
    rows = {r.name: r for r in qpa.phases}
    for ip, name in enumerate(("LaB6", "CaF2")):
        row = rows[name]
        err_uncorr = abs(row.weight_fraction - w_true[ip])
        err_corr = abs(row.weight_fraction_corrected - w_true[ip])
        # the injected bias is ~1.7 % absolute, well above the Poisson noise
        # (~0.3 %); the correction must remove most of it, in the right
        # direction, for both phases
        assert err_uncorr > 0.010
        assert err_corr < 0.5 * err_uncorr
        assert err_corr < 0.010
        assert math.isclose(row.brindley_tau, tau_true[ip], rel_tol=5e-3)
    assert math.isclose(qpa.microabsorption.mu_mean_cm, mu_bar_true, rel_tol=0.02)

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    result.plot(path=str(out / "qpa_brindley.png"))

    # push LaB6 past the fence and refit one stage: the engine itself must
    # surface the regime warning on the rebuilt result
    for phase in ref.structure.phases:
        phase.particle_radius_um = 5.0
    result2 = ref.run_stage(data, Stage("scale", ["phases.*.scale"], max_iter=5))
    fence = [d for d in result2.diagnostics if d.code == "BRINDLEY_OUTSIDE_REGIME"]
    assert fence and "LaB6" in fence[0].where
    assert {r.name: r for r in result2.qpa.phases}["LaB6"].mu_r > BRINDLEY_MU_R_FENCE


# -- the radiation seam of the specimen-absorption estimate (WP-1132) -------
def _vanadium_phase() -> Phase:
    """A synthetic bcc V cell, a = 3.03 Å, one site at 2a (two atoms/cell)."""
    P = Parameter
    return Phase(
        name="V", space_group="I m -3 m",
        cell=Cell(a=P(value=3.03), b=P(value=3.03), c=P(value=3.03),
                  alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[Atom(label="V1", species="V", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=0.4))])


def test_the_estimator_reads_the_neutron_table_on_a_neutron_source():
    """One seam: only µ per phase changes with ``source_kind``.

    By hand, from Sears (V σ_abs 5.08, σ_coh 0.0184, σ_inc 5.08 barn) at
    λ = 2.4067 Å: σ_tot = 5.08 × 2.4067/1.798 + 0.0184 + 5.08 = 11.898198
    barn, µ = 2 × 11.898198 / 3.03³ = 0.855428 cm⁻¹, and with the default
    packing 0.6 and R = 3 mm, µR = 0.6 × 0.855428 × 0.3 = 0.153977.

    The X-ray answer for the same arguments is asserted to be a different
    number by more than an order of magnitude, so a seam that ignored
    ``source_kind`` cannot pass.
    """
    from rietx.optimize.qpa import (
        estimate_capillary_mu_r,
        estimate_flat_plate_mu_t,
    )

    structure = Structure(phases=[_vanadium_phase()])
    inst = Instrument.constant_wavelength_neutron(2.4067)
    table = ParameterTable(structure, inst)
    values = table.decode(table.x0())

    mu_r, note = estimate_capillary_mu_r(structure, values, 2.4067, 3.0, 0.6,
                                         source_kind="neutron_cw")
    assert note is None
    assert mu_r == pytest.approx(0.153977, abs=2e-6)
    # the flat-plate twin shares everything but the length: t = 2R here
    mu_t, note = estimate_flat_plate_mu_t(structure, values, 2.4067, 6.0, 0.6,
                                          source_kind="neutron_cw")
    assert note is None and mu_t == pytest.approx(2.0 * mu_r, rel=1e-12)

    xray, _ = estimate_capillary_mu_r(structure, values, 2.4067, 3.0, 0.6)
    assert xray is not None and xray > 10.0 * mu_r


def test_a_source_with_no_table_declines_by_name():
    """A kind the seam does not know has no table, and says so."""
    from rietx.optimize.qpa import estimate_capillary_mu_r

    structure = Structure(phases=[_vanadium_phase()])
    table = ParameterTable(structure, Instrument.constant_wavelength_neutron(2.4067))
    mu_r, reason = estimate_capillary_mu_r(
        structure, table.decode(table.x0()), 2.4067, 3.0, 0.6,
        source_kind="neutron_tof")
    assert mu_r is None
    assert "attenuation unavailable" in reason and "neutron_tof" in reason
