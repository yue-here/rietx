"""v0.1 acceptance: real 11-BM synchrotron data (NAC + CaF2 impurity).

Marked slow: run with ``pytest -m slow`` (or no marker filter).
Reference values: see tests/data/README.md.  The refined cell is checked
against the literature band with a tolerance that allows for the beamline
wavelength-calibration uncertainty; internal consistency (Le Bail vs
Rietveld) is checked much more tightly.
"""

from pathlib import Path

import pytest

import pxrdref as pr

DATA = Path(__file__).parent / "data"
WAVELENGTH = 0.4139090
LIMITS = (2.0, 24.0)

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def nac_inputs():
    if not (DATA / "11BM_NAC.fxye").exists():
        pytest.skip("11-BM NAC dataset not present")
    data = pr.read_pattern(DATA / "11BM_NAC.fxye")
    structure = pr.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    instrument = pr.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    from pxrdref.schemas.instrument import BackgroundChebyshev
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument


def _caf2_phase() -> pr.Phase:
    return pr.Phase(
        name="CaF2", space_group="F m -3 m", cell=pr.Cell.cubic(5.4631),
        atoms=[
            pr.Atom(label="Ca", species="Ca2+", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.6, min=0.0, max=25.0)),
            pr.Atom(label="F", species="F1-", x=pr.Parameter(value=0.25),
                    y=pr.Parameter(value=0.25), z=pr.Parameter(value=0.25),
                    biso=pr.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-7, min=0.0, transform="softplus"),
    )


def test_nac_lebail_then_rietveld(nac_inputs):
    data, structure, instrument = nac_inputs

    ref_lb = pr.Refinement(structure, instrument)
    lebail = ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS)
    assert lebail.status == "converged"
    assert lebail.statistics.rwp < 0.20
    a_lb = ref_lb.fitted_structure.phases[0].cell.a.value

    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(_caf2_phase())

    plan = pr.RefinementPlan.mccusker_default()
    plan.stages.append(pr.Stage("biso", ["phases.*.atoms.*.biso"]))
    ref = pr.Refinement(structure2, instrument2)
    result = ref.fit(data, plan=plan, two_theta_limits=LIMITS)

    assert result.status == "converged"
    assert result.statistics.rwp < 0.12
    assert result.statistics.gof < 5.0

    a = ref.fitted_structure.phases[0].cell.a.value
    a_err = result.parameter("phases.0.cell.a").stderr
    assert a_err is not None and a_err < 1e-4
    # literature band ± wavelength-calibration allowance
    assert abs(a - 10.2510) < 2e-3
    # internal consistency with the (single-phase) Le Bail cell
    assert abs(a - a_lb) < 5e-4

    # the CaF2 impurity cell should land on fluorite
    a_caf2 = ref.fitted_structure.phases[1].cell.a.value
    assert abs(a_caf2 - 5.4631) < 5e-3

    report = pr.build_report(result)
    assert report.n_regions_total > 20
    assert report.summary

    # fit plot for visual inspection (tests/output/, gitignored)
    from pxrdref.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "nac_fit.png"))


def _min_extinction_factor(structure, instrument, data, ip: int) -> float:
    """Smallest E(hkl) the fitted extinction applies to phase ``ip`` — the
    physical size of the correction, wavelength/cell-independent (unlike the
    raw ``ext`` coefficient)."""
    import numpy as np

    from pxrdref.crystallography.lattice import (
        cell_volume,
        d_spacings,
        two_theta_deg,
    )
    from pxrdref.crystallography.structure_factor import structure_factors_squared
    from pxrdref.model.extinction import sabine_extinction
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable

    model = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=LIMITS)
    values = ParameterTable(structure, instrument).decode(
        ParameterTable(structure, instrument).x0())
    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.hkl, *cell)
    xyz, occ, biso, ua, astar = model._site_values(ip, values, cell)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites, xyz, occ, biso, ua, astar)
    tt = two_theta_deg(d, model.line_wavelengths[0])
    E = sabine_extinction(f2, model.line_wavelengths[0], cell_volume(*cell),
                          tt, values[f"phases.{ip}.extinction"])
    return float(np.nanmin(E))


def test_nac_extinction_on_the_main_phase_is_bounded_and_unbiasing(nac_inputs):
    """WP-0506 does-no-harm on synchrotron data, done *right* — extinction
    freed only on the well-determined main phase.

    Unlike SRM 660c (single phase, extinction → 0), NAC does *not* drive
    extinction to zero: at λ = 0.414 Å with V ≈ 1077 Å³ the raw ``ext``
    coefficient (≈ 336) is large for a *small* physical correction (x ∝
    (λ/V)²), so the invariant is on the correction's *size*, not on ``ext``.
    The correction stays bounded (min E > 0.8, ≤ ~12% on the strongest line)
    and the cell is not biased.  Freeing extinction on the ill-determined CaF₂
    impurity instead lets it run away (measured min E ≈ 0.31, a spurious 69%
    attenuation on a phase contributing ~1% of the pattern) — the
    over-flexible-correction hazard — which is why extinction is off by
    default and opt-in *per phase*, and why the guards stay live."""
    data, structure, instrument = nac_inputs

    ref_lb = pr.Refinement(structure, instrument)
    ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS)
    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(_caf2_phase())

    plan = pr.RefinementPlan.mccusker_default()
    plan.stages.append(pr.Stage("biso", ["phases.*.atoms.*.biso"]))
    # only the main phase — the recommended usage; not the CaF2 impurity
    plan.stages.append(pr.Stage("extinction", ["phases.0.extinction"], seed=1e-3))

    ref = pr.Refinement(structure2, instrument2)
    result = ref.fit(data, plan=plan, two_theta_limits=LIMITS)

    assert result.status == "converged"
    assert result.statistics.rwp < 0.12
    a = ref.fitted_structure.phases[0].cell.a.value
    assert abs(a - 10.2510) < 2e-3, f"extinction biased the NAC cell to a={a:.5f}"
    # CaF2 extinction was never freed, so it stays exactly off
    assert ref.fitted_structure.phases[1].extinction.value == 0.0
    # the main-phase correction is physical, not a runaway
    min_e = _min_extinction_factor(ref.fitted_structure, ref.fitted_instrument, data, 0)
    assert min_e > 0.8, f"main-phase extinction attenuates {(1 - min_e) * 100:.0f}% — implausible"
