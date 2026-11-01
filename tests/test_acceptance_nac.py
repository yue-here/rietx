"""v0.1 acceptance: real 11-BM synchrotron data (NAC + CaF2 impurity).

Marked slow: run with ``pytest -m slow`` (or no marker filter).
Reference values: see tests/data/README.md.  The refined cell is checked
against the literature band with a tolerance that allows for the beamline
wavelength-calibration uncertainty; internal consistency (Le Bail vs
Rietveld) is checked much more tightly.
"""

import re
from pathlib import Path

import pytest

import rietx as rx

DATA = Path(__file__).parent / "data"
WAVELENGTH = 0.4139090
LIMITS = (2.0, 24.0)

#: both tests below run off one Le Bail pass and one Rietveld fit, so the whole
#: module belongs on the worker that built them
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("nac")]


def build_nac_inputs():
    """(data, structure, instrument) for the 11-BM NAC protocol.

    A plain function, not only a fixture, for the same reason
    ``test_acceptance_srm660c.build_srm_inputs`` is one: another suite
    (``test_acceptance_indexing``) needs to rebuild *this* state rather than a
    plausible imitation of it, so that when the two disagree about a number the
    protocol is not one of the candidate explanations.
    """
    if not (DATA / "11BM_NAC.fxye").exists():
        pytest.skip("11-BM NAC dataset not present")
    data = rx.read_pattern(DATA / "11BM_NAC.fxye")
    structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    instrument = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    from rietx.schemas.instrument import BackgroundChebyshev
    instrument.background = BackgroundChebyshev.with_terms(6)
    # Dispersion DECLINED explicitly (WP-1001 made it the package default) so
    # the v0.1 milestone numbers keep meaning what they said.  It is nearly
    # inert here anyway — at 0.4139 Å (30 keV) every species in Na2Ca3Al2F14
    # and CaF2 is far above its K edge — but "nearly inert" is a measurement,
    # not a licence to leave the setting implicit.
    instrument.source.dispersion = None
    return data, structure, instrument


@pytest.fixture(scope="module")
def nac_inputs():
    return build_nac_inputs()


def _caf2_phase() -> rx.Phase:
    return rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(5.4631),
        atoms=[
            rx.Atom(label="Ca", species="Ca2+", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.6, min=0.0, max=25.0)),
            rx.Atom(label="F", species="F1-", x=rx.Parameter(value=0.25),
                    y=rx.Parameter(value=0.25), z=rx.Parameter(value=0.25),
                    biso=rx.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=1e-7, min=0.0, transform="softplus"),
    )


@pytest.fixture(scope="module")
def nac_lebail(nac_inputs):
    """The single-phase Le Bail pass — the Rietveld model's starting point."""
    data, structure, instrument = nac_inputs
    ref_lb = rx.Refinement(structure, instrument)
    return ref_lb, ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS)


@pytest.fixture(scope="module")
def nac_rietveld(nac_inputs, nac_lebail):
    """The two-phase Rietveld fit built on it: the Le Bail cell and instrument,
    the phase scale reset, the CaF₂ impurity appended."""
    data, _structure, _instrument = nac_inputs
    ref_lb, _lebail = nac_lebail

    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(_caf2_phase())

    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    # WP-1123: the shipped convergence schedule, named rather than inherited.
    # Every stage but the last stops at 1e-6 and the last at the solver's own
    # 1e-9, which is what a user's own run does — so these numbers are the
    # ones the package actually produces.  None here would converge every
    # stage; measured cost of the schedule on this protocol is <= 0.02 esd.
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    ref = rx.Refinement(structure2, instrument2)
    return ref, ref.fit(data, plan=plan, two_theta_limits=LIMITS)


def test_nac_lebail_then_rietveld(nac_lebail, nac_rietveld):
    ref_lb, lebail = nac_lebail
    assert lebail.status == "converged"
    assert lebail.statistics.rwp < 0.20
    a_lb = ref_lb.fitted_structure.phases[0].cell.a.value

    ref, result = nac_rietveld
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

    report = rx.build_report(result)
    assert report.n_regions_total > 20
    assert report.summary

    # fit plot for visual inspection (tests/output/, gitignored)
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "nac_fit.png"))


_MASK_NUMBER = re.compile(r"[-+]?\d[\d.]*")
GOLDEN_TERMINATION_VIEW = Path(__file__).parent / "data" / "nac_termination_golden.txt"


def _masked(text: str) -> str:
    """Every digit run replaced by ``#`` — the termination view's *shape*,
    stripped of the numbers that carry no structural meaning for this test
    (a platform-libm ulp, a re-measured Rwp) but would otherwise break an
    exact-text comparison the way this codebase's other goldens are pinned to
    a platform (``tests/CLAUDE.md``, ``GOLDEN_PLATFORM``) — this one is not,
    on purpose: it changes only when a *field* does, never when a number
    moves within its own precision.

    The **version** is masked whole, before the digit runs, and that is not a
    tidy-up.  Under the digit mask alone ``1.3.0.dev0`` becomes ``#dev#`` and
    ``1.3.0`` becomes ``#``, so a golden written between releases pins the
    release *phase* into the view's shape and goes red on the one commit that
    ships it — and again when the version moves on to ``1.x.0.dev0``.
    Measured: the only red in v1.3's ship suite, and the six required checks
    cannot see it because acceptance is ``slow``.
    """
    return _MASK_NUMBER.sub("#", text.replace(rx.__version__, "#"))


def test_nac_termination_view_golden_shape(nac_rietveld):
    """``Refinement.summary()``'s shape on 11-BM NAC, masked (WP-1302).

    Every message is checked by substring elsewhere in this suite (never by
    equality with a sentence — the acceptance rule this WP declares); this
    test is the complementary one, checking the view's *structure* — which
    sections appear, in which order, with which labels — survives untouched
    when only a number moves. Regenerate the golden file at
    ``tests/data/nac_termination_golden.txt`` with
    ``_masked(ref.summary(deliverable="qpa"))`` when a field genuinely
    changes, and say why in the commit.
    """
    ref, _result = nac_rietveld
    text = ref.summary(deliverable="qpa")
    golden = GOLDEN_TERMINATION_VIEW.read_text(encoding="utf-8")
    assert _masked(text) == golden.rstrip("\n")


def _min_extinction_factor(structure, instrument, data, ip: int) -> float:
    """Smallest E(hkl) the fitted extinction applies to phase ``ip`` — the
    physical size of the correction, wavelength/cell-independent (unlike the
    raw ``ext`` coefficient)."""
    import numpy as np

    from rietx.crystallography.lattice import (
        cell_volume,
        d_spacings,
        two_theta_deg,
    )
    from rietx.crystallography.structure_factor import structure_factors_squared
    from rietx.model.extinction import sabine_extinction
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

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


def test_nac_extinction_on_the_main_phase_is_bounded_and_unbiasing(
        nac_inputs, nac_rietveld):
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
    default and opt-in *per phase*, and why the guards stay live.

    The extinction stage is *warm-extended* onto the shared Rietveld fit rather
    than re-run from the Le Bail pass: ``run_stage`` restores the cumulative
    free set at the converged values and then frees the new stage's globs, which
    is exactly what an appended stage of the same plan does from the same state.
    Verified on this dataset before landing — Rwp, a, ext and min E all agree to
    the last digit of their float64 repr with the from-scratch protocol."""
    data, _structure, _instrument = nac_inputs
    ref_base, _rietveld = nac_rietveld

    # only the main phase — the recommended usage; not the CaF2 impurity
    ref = ref_base.branch()
    result = ref.run_stage(
        data, rx.Stage("extinction", ["phases.0.extinction"], seed=1e-3))

    assert result.status == "converged"
    assert result.statistics.rwp < 0.12
    a = ref.fitted_structure.phases[0].cell.a.value
    assert abs(a - 10.2510) < 2e-3, f"extinction biased the NAC cell to a={a:.5f}"
    # CaF2 extinction was never freed, so it stays exactly off
    assert ref.fitted_structure.phases[1].extinction.value == 0.0
    # the main-phase correction is physical, not a runaway
    min_e = _min_extinction_factor(ref.fitted_structure, ref.fitted_instrument, data, 0)
    assert min_e > 0.8, f"main-phase extinction attenuates {(1 - min_e) * 100:.0f}% — implausible"
