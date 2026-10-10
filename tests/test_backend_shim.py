"""WP-0401 backend-shim bit-identity goldens.

The op-shim routing and purity refactors (WP-0401) must not change a single
computed number on the numpy path.  This file freezes that claim: each state
below is compiled, evaluated and differentiated exactly as the solver does,
and compared **bit-for-bit** (``np.array_equal``) against golden arrays
captured from the pre-shim tree.

States (chosen to cover every refactored code path):

* ``srm660c`` — real lab data, Bragg-Brentano + Kα doublet + FCJ + Chebyshev
  background; displacement/transparency/extinction free *at their 0 off-values*
  (gates the unconditional-evaluation refactor's exact identities).
* ``nac`` — real synchrotron data, two phases, coordinate DOF columns.
* ``toy_lebail`` — Le Bail partitioning (3 cycles) + P-spline penalty rows.
* ``toy_pawley`` — Pawley intensity block: aux Jacobian columns + overlap
  restraint rows.
* ``toy_rich`` — aniso ADPs + March-Dollase + extinction + displacement/
  transparency/zero all *on* (nonzero), unequal axial S/L ≠ H/L.
* ``toy_capillary`` — Debye-Scherrer with cylindrical absorption on (WP-0501):
  the only state whose cell/coordinate/ADP/scale columns chain through a
  θ-dependent intensity factor that is neither Lp nor extinction.
* ``toy_restraints`` — Rietveld rutile with bond, angle and value soft-restraint
  rows (WP-0406): the nonlinear penalty stripe below the data rows, its residual
  and analytic Jacobian columns locked for the cross-backend CI (WP-0404).
* ``toy_stephens`` — Rietveld rutile with a Stephens anisotropic-strain block
  (WP-0503): an hkl-dependent width reached through a √ of a frozen monomial
  matmul, which no other state exercises.
* ``toy_roughness`` — Bragg-Brentano rutile with Suortti surface roughness on
  (WP-0502): an exp of a reciprocal sin, folded into all three intensity
  assemblies (phase_peaks plus both analytic column builders).
* ``toy_anomalous`` — Rietveld zincite with f′, f″ on (WP-0504): the only
  **non-centrosymmetric** state, so it is the only one where the
  Friedel-averaged |A|² + |B|² differs from |F|² at the orbit representative.

Golden bit patterns are environment-pinned (they depend on the numpy/BLAS
build); they live in ``tests/data/backend_goldens/`` and are documented in
``tests/data/README.md``.  If the environment shifts, re-baseline **from a
tree that passes the full suite**, never from a mid-refactor tree:

    .venv/bin/python -m tests.test_backend_shim STATE [STATE ...]

naming only the states that genuinely changed — re-capturing an untouched state
rebases a baseline that was meant to be a fixed point.

**Which environments they hold on** stopped being a hypothesis in WP-1002, when
the CI matrix measured it (see ``GOLDEN_PLATFORM`` below).  A *Python* or
*numpy* change does not move them — 3.11/2.4.6, 3.12/2.5.1, 3.13/2.5.1 and
3.14/2.5.1 all reproduce them bit-for-bit on macOS/arm64.  A *platform* change
does: on Linux x86-64 all eight toy states diverge, by 1 ulp on the quantities
that are a single arithmetic chain (``theta``, ``lebail_intensity``,
``pawley_x0``) and by up to ~1100 ulp (1.7e-13 relative) on ``y_calc``, which
accumulates ~130 windows of transcendental evaluations.  That gradient *with
chain length* is the signature of a different libm and a different summation
order, not of different code — and 1.7e-13 relative sits ten orders of
magnitude below the tightest physical bar in the tree.  So the gate is asserted
where it was captured and skipped, loudly, everywhere else: relaxing
``array_equal`` to a tolerance instead would delete the only check that says no
refactor changed a single computed number.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import (
    BackgroundChebyshev,
    BackgroundPSpline,
    Instrument,
    RoughnessSuortti,
)
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import PreferredOrientation

DATA = Path(__file__).parent / "data"
GOLDEN_DIR = DATA / "backend_goldens"


# ----------------------------------------------------------------------
# state builders — deterministic (model, table, extras) triples
# ----------------------------------------------------------------------
def _free(table: ParameterTable, patterns: list[str]) -> None:
    table.set_vary(["*"], False)
    for pat in patterns:
        assert table.set_vary([pat], True), f"nothing freed by {pat!r}"


def _state_srm660c():
    path = DATA / "nist_srm660c_100a.cif"
    if not path.exists():
        return None
    data = rx.read_pdcif(path, block="_meas")
    structure = rx.Structure(phases=[rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.1568),
        atoms=[
            rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.355, min=0.0, max=25.0)),
            rx.Atom(label="B", species="B", x=rx.Parameter(value=0.198),
                    y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5),
                    biso=rx.Parameter(value=0.276, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=1e-4, min=0.0, transform="softplus"),
    )])
    instrument = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.source.dispersion = None   # declined, not inherited — see _toy_base
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    instrument.background = BackgroundChebyshev.with_terms(6)

    table = ParameterTable(structure, instrument)
    # displacement, transparency and extinction free at their 0.0 off-values:
    # the FD Jacobian steps them on, so the exact-identity claim is exercised
    _free(table, [
        "phases.0.scale", "instrument.background.*",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.zero_shift", "phases.0.cell.a",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        "instrument.source.lines.1.weight",
        "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
        "phases.0.atoms.*.biso", "phases.0.extinction",
    ])
    model = compile_model(structure, instrument, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


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


def _state_nac():
    if not (DATA / "11BM_NAC.fxye").exists():
        return None
    data = rx.read_pattern(DATA / "11BM_NAC.fxye")
    structure = rx.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    structure.phases[0].scale.value = 1e-6
    structure.phases.append(_caf2_phase())
    instrument = Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.source.dispersion = None   # declined, not inherited — see _toy_base
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = BackgroundChebyshev.with_terms(6)

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.*.scale", "instrument.background.*",
        "phases.0.cell.a", "phases.1.cell.a", "instrument.zero_shift",
        "instrument.profile.w", "instrument.profile.x",
        "phases.0.atoms.*.dof.*",
        "phases.0.atoms.0.biso", "phases.1.atoms.0.biso",
    ])
    model = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=(2.0, 24.0),
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _toy_base(*, c_near_a: bool = False) -> tuple[rx.Structure, Instrument, PatternData]:
    """Deterministic rutile toy: y_obs from a perturbed copy of the model.

    ``c_near_a`` squeezes the tetragonal cell pseudo-cubic so (hkl)/(lkh)
    partners nearly coincide — that is what puts overlapped groups (and hence
    restraint rows) into the Pawley state.
    """
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    if c_near_a:
        structure.phases[0].cell.c.value = 4.5910
    instrument = Instrument.debye_scherrer(wavelength=1.5406)
    instrument.profile.w.value = 8e-3
    # Dispersion DECLINED (WP-1001 made it the package default).  These
    # goldens exist to prove the *op shim* changes no number, so they must not
    # move when the physics defaults do; ``toy_anomalous`` is the dedicated
    # golden covering the dispersion derivative path, and it turns the block
    # on explicitly.  Declining here keeps every committed npz bit-identical
    # across the default flip, which is itself the evidence that the flip
    # touched physics and not plumbing.
    instrument.source.dispersion = None
    grid = np.arange(15.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value += 0.005
    sim_structure.phases[0].cell.c.value -= 0.004
    sim_structure.phases[0].scale.value = 9.2e-3
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 30.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())
    return structure, instrument, pattern


_TOY_WHOLE_PATTERN_FREE = [
    "phases.0.cell.a", "phases.0.cell.c", "instrument.zero_shift",
    "instrument.profile.w", "instrument.background.*",
]


def _state_toy_lebail():
    structure, instrument, pattern = _toy_base()
    instrument.background = BackgroundPSpline.for_range(15.0, 80.0)
    # The pre-WP-1454 defaults, declared rather than inherited, for the reason
    # dispersion is declined in ``_toy_base``: the npz was captured with an air
    # column and with λ in intensity units, and a golden that moves when a
    # default moves proves nothing about the op shim.
    instrument.background.air_scatter = rx.Parameter(value=0.0, min=0.0,
                                                     transform="softplus")
    instrument.background.lambda_units = "intensity"
    table = ParameterTable(structure, instrument)
    _free(table, _TOY_WHOLE_PATTERN_FREE)
    model = compile_model(structure, instrument, pattern, mode="lebail",
                          moving_paths=set(table.moving_paths))
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    intens = np.concatenate([cp.hkl_intensity for cp in model.phases])
    return model, table, {"lebail_intensity": intens}


def _state_toy_pawley():
    structure, instrument, pattern = _toy_base(c_near_a=True)
    instrument.background = BackgroundChebyshev.with_terms(4)
    table = ParameterTable(structure, instrument)
    _free(table, _TOY_WHOLE_PATTERN_FREE)
    model = compile_model(structure, instrument, pattern, mode="pawley",
                          moving_paths=set(table.moving_paths))
    # mirror the staged runner's seeding: one Le Bail partition, then the
    # equal-split restraint on the seeded scale
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    model.build_pawley_restraint()
    return model, table, {"pawley_x0": model.pawley_x0()}


def _state_toy_rich():
    """Every optional intensity physics ON and nonzero at the expansion point."""
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    phase = structure.phases[0]
    phase.scale.value = 8.0e-3
    phase.extinction.value = 3e-4
    phase.preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
    phase.preferred_orientation.r.value = 0.85
    instrument = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.source.dispersion = None   # declined, not inherited — see _toy_base
    instrument.profile.w.value = 8e-3
    instrument.profile.x.value = 5e-3
    instrument.zero_shift.value = 0.01
    instrument.geometry.sample_displacement.value = -0.08
    instrument.geometry.sample_transparency.value = 0.005
    instrument.geometry.axial_sl.value = 0.03
    instrument.geometry.axial_hl.value = 0.02

    grid = np.arange(15.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value = 4.5987
    sim_structure.phases[0].preferred_orientation.r.value = 0.9
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 20.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.scale", "phases.0.cell.a", "phases.0.cell.c",
        "phases.0.atoms.*.dof.*", "phases.0.atoms.*.adp.*",
        "phases.0.preferred_orientation.r", "phases.0.extinction",
        "instrument.zero_shift",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
        "instrument.source.lines.1.weight", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_toy_restraints():
    """Rietveld rutile carrying bond, angle and value soft-restraint rows.

    Locks the WP-0406 restraint stripe under the bit-identity gate: the rows are
    nonlinear in the coordinates and cell, so their residual and analytic
    Jacobian columns are the new surface a backend could drift on.  The angle
    names explicit orbit ops so the two O neighbours of Ti form a non-degenerate
    angle (auto min-image would pick the same image for both).
    """
    from rietx.schemas.structure import (
        AngleRestraint,
        BondRestraint,
        ValueRestraint,
    )

    structure, instrument, pattern = _toy_base()
    structure.phases[0].atoms[1].x.vary = True  # free the O coordinate DOF
    structure.phases[0].restraints = [
        BondRestraint(atom_i=0, atom_j=1, target=1.95, sigma=0.01),
        AngleRestraint(atom_i=1, atom_j=0, atom_k=1, target_deg=90.0, sigma=1.5,
                       op_index_i=0, op_index_k=1),
        ValueRestraint(path="phases.0.atoms.1.occ", target=0.95, sigma=0.03),
    ]
    instrument.background = BackgroundChebyshev.with_terms(4)
    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale",
        "phases.0.atoms.1.dof.0", "phases.0.atoms.1.occ",
        "instrument.zero_shift", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_toy_capillary():
    """Debye-Scherrer rutile with cylindrical absorption ON (WP-0501).

    µR = 0.8 sits inside the Rouse et al. (1970) fit's stated µR ≤ 1 range and
    is strong enough that A runs ~0.24-0.31 across the pattern.

    There is no new *column* here — µR is not refinable, deliberately (it is
    exactly a linear combination of the scale and Biso directions).  What is
    new is that A depends on 2θ_Bragg, so the cell, coordinate, ADP and scale
    columns now chain through a θ-dependent factor that no other state
    exercises: every existing Rietveld state is either bragg_brentano (where
    the correction is off by geometry) or sits at µR = 0.
    """
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    phase = structure.phases[0]
    phase.scale.value = 8.0e-3
    instrument = Instrument.debye_scherrer(wavelength=1.5406, mu_r=0.8)
    instrument.source.dispersion = None   # declined, not inherited — see _toy_base
    instrument.profile.w.value = 8e-3
    instrument.profile.x.value = 5e-3
    instrument.zero_shift.value = 0.01

    grid = np.arange(15.0, 90.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value = 4.5987
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 20.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.scale", "phases.0.cell.a", "phases.0.cell.c",
        "phases.0.atoms.*.dof.*", "phases.0.atoms.*.adp.*",
        "instrument.zero_shift", "instrument.profile.w", "instrument.profile.x",
        "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    assert model.mu_r == 0.8, "absorption must actually be live in this state"
    return model, table, {}


def _state_toy_stephens():
    """Rietveld rutile with a Stephens anisotropic-strain block (WP-0503).

    Locks the hkl-dependent width path: rutile is Laue 4/mmm, so the block has
    four DOFs, and the tetragonal cell makes the (h00)/(00l) contrast real.  The
    strain enters through a √ of a frozen monomial matmul — a shape no other
    golden exercises, and one an autodiff backend has to trace through.  The
    start is deliberately *off* the isotropic ray so the anisotropic patterns
    carry a nonzero derivative.
    """
    from rietx.crystallography.stephens import stephens_basis
    from rietx.schemas.structure import StephensStrain

    structure, instrument, pattern = _toy_base()
    phase = structure.phases[0]
    basis = stephens_basis(phase.space_group).astype(np.float64)
    coef, *_ = np.linalg.lstsq(
        basis.T,
        np.array(StephensStrain.isotropic(900.0, phase.cell).values()), rcond=None)
    coef[0] *= 1.7  # break the isotropic degeneracy
    phase.microstrain = StephensStrain.from_values(basis.T @ coef, vary=True)
    instrument.background = BackgroundChebyshev.with_terms(4)
    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale",
        "phases.0.microstrain.dof.*", "phases.0.lor_size",
        "instrument.zero_shift", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_toy_anomalous():
    """Rietveld zincite with anomalous scattering on (WP-0504).

    Deliberately **non-centrosymmetric** (ZnO, ``P 63 m c``), which is the only
    setting where the Friedel-averaged |A|² + |B|² differs from |F|² at the
    orbit representative — a centrosymmetric golden would lock the code while
    leaving the one term that motivates it untested.  Zn sits just below its K
    edge at Cu Kα, so f′ = −1.55 is large, and an anisotropic Zn site plus a
    free polar-axis z run the correction through *both* structural derivative
    kernels.

    The observed pattern is **read, not simulated** (WP-1928).  It was once
    evaluated here at a perturbed copy of the model (``cell.a + 0.004``,
    ``atoms[1].z + 0.003``, +25 flat), and that evaluation goes through libm,
    so it moved with the macOS major: 26 → 27 shifted ``residual`` and
    ``jacobian`` while ``y_calc`` stayed bit-identical (#760).  The pattern is
    input data, not code under test, so it is frozen in
    ``backend_goldens/toy_anomalous_y_obs.npy`` (provenance in
    ``tests/data/README.md``) and the gate now tests only the shim path.
    """
    from rietx.schemas.instrument import Dispersion
    from rietx.schemas.structure import AnisoU, Structure
    from tests.test_dispersion import zincite

    phase = zincite()
    phase.scale.value = 6.0e-3
    phase.atoms[0].biso.vary = False
    phase.atoms[0].aniso = AnisoU.from_values(
        (0.0072, 0.0072, 0.0081, 0.0036, 0.0, 0.0), vary=True)
    structure = Structure(phases=[phase])
    instrument = Instrument.bragg_brentano(radiation="CuKa")
    instrument.source.dispersion = Dispersion()
    instrument.profile.w.value = 1.2e-2
    instrument.background = BackgroundChebyshev.with_terms(4)
    grid = np.arange(28.0, 95.0, 0.02)
    y = np.load(GOLDEN_DIR / "toy_anomalous_y_obs.npy")
    assert y.shape == grid.shape, f"frozen y_obs {y.shape} != grid {grid.shape}"
    pattern = PatternData(two_theta=grid.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale",
        "phases.0.atoms.*.dof.*", "phases.0.atoms.0.adp.*",
        "phases.0.atoms.1.biso", "instrument.zero_shift",
        "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_toy_roughness():
    """Rietveld rutile on a Bragg-Brentano mount carrying Suortti roughness.

    Locks the WP-0502 stripe: the correction is an ``xp.exp`` of a reciprocal
    of ``xp.sin``, evaluated per (line, reflection) and folded into three
    separate intensity assemblies (phase_peaks and the two analytic column
    builders).  A backend that got any of them subtly wrong would show up here
    before it showed up in a fit.  Bragg-Brentano because the schema refuses a
    roughness block on a capillary, so this state cannot reuse ``_toy_base`` —
    and it is the flat-plate counterpart to ``toy_capillary``, which locks the
    other geometry's intensity factor.
    """
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    structure.phases[0].atoms[1].x.vary = True
    instrument = Instrument.bragg_brentano()
    instrument.source.dispersion = None   # declined, not inherited — see _toy_base
    instrument.profile.w.value = 8e-3
    instrument.background = BackgroundChebyshev.with_terms(4)
    instrument.geometry.surface_roughness = RoughnessSuortti(
        a=rx.Parameter(value=0.45, min=0.0, max=1.0),
        b=rx.Parameter(value=0.32, min=0.0, max=5.0, transform="softplus"))
    grid = np.arange(12.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 30.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale",
        "phases.0.atoms.1.dof.0", "phases.0.atoms.0.biso",
        "instrument.geometry.surface_roughness.*",
        "instrument.zero_shift", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


STATES = {
    "srm660c": _state_srm660c,
    "nac": _state_nac,
    "toy_lebail": _state_toy_lebail,
    "toy_pawley": _state_toy_pawley,
    "toy_rich": _state_toy_rich,
    "toy_restraints": _state_toy_restraints,
    "toy_stephens": _state_toy_stephens,
    "toy_capillary": _state_toy_capillary,
    "toy_roughness": _state_toy_roughness,
    "toy_anomalous": _state_toy_anomalous,
}


def _capture(name: str, *, compiled_path: bool = False
             ) -> dict[str, np.ndarray] | None:
    """Evaluate + residual + Jacobian arrays at the state's expansion point.

    **The path is declared, never inherited** (CLAUDE.md's rule for a test that
    pins a number, first written for the dispersion default).  These goldens are
    pre-shim bit patterns of the *numpy* expressions, so the default here
    switches the WP-1115 compiled tier off; ``compiled_path=True`` captures the
    same state through the kernels, which is what
    :func:`test_the_compiled_path_holds_the_goldens_to_its_own_bar` compares.
    """
    was = compiled.set_enabled(bool(compiled_path))
    try:
        return _capture_now(name)
    finally:
        compiled.set_enabled(was)


def _capture_now(name: str) -> dict[str, np.ndarray] | None:
    built = STATES[name]()
    if built is None:
        return None
    model, table, extras = built
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    values = table.decode(theta[:len(table.free_paths)])
    out = dict(extras)
    out["free_paths"] = np.array(table.free_paths, dtype="U")
    out["theta"] = theta
    out["y_calc"] = model.evaluate(values)
    out["residual"] = _make_residual(model, table)(theta)
    out["jacobian"] = _make_jacobian(model, table)(theta)
    return out


# ----------------------------------------------------------------------
# shim primitives
# ----------------------------------------------------------------------
def test_numpy_backend_attributes_are_numpy_functions():
    """Zero-overhead claim: the numpy backend's ops ARE the numpy callables
    (plain-function attributes must not have bound as methods)."""
    from rietx.backend import NumpyBackend, get_backend

    xp = get_backend()
    assert isinstance(xp, NumpyBackend)
    assert xp.exp is np.exp
    assert xp.clip is np.clip
    assert xp.einsum is np.einsum
    assert xp.linalg is np.linalg
    assert xp.pi == np.pi


def test_window_add_functional_contract():
    from rietx.backend import get_backend

    xp = get_backend()
    y = np.zeros(6)
    out = xp.window_add(y, 2, 5, np.array([1.0, 2.0, 3.0]))
    # callers thread the return value; the numpy impl mutates in place
    assert out is y
    assert np.array_equal(out, [0.0, 0.0, 1.0, 2.0, 3.0, 0.0])
    out = xp.window_add(out, 0, 0, np.zeros(0))  # empty frozen window is legal
    assert np.array_equal(out, [0.0, 0.0, 1.0, 2.0, 3.0, 0.0])


def test_segment_sum_matches_bincount():
    from rietx.backend import get_backend

    xp = get_backend()
    vals = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    seg = np.array([0, 2, 2, 0, 3])
    got = xp.segment_sum(vals, seg, 5)
    assert np.array_equal(got, np.bincount(seg, weights=vals, minlength=5))
    assert got.shape == (5,)  # n buckets even when the tail is empty


def test_set_backend_roundtrip():
    from rietx.backend import NumpyBackend, get_backend, set_backend

    original = get_backend()

    class _Marker(NumpyBackend):
        name = "marker"

    try:
        set_backend(_Marker())
        assert get_backend().name == "marker"
    finally:
        set_backend(original)
    assert get_backend() is original


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
#: The platform every committed golden was captured on.  It is a *property of
#: the files*, not a preference: they are bit patterns, and WP-1002 measured
#: that they do not survive a libm/BLAS change (module docstring).  Keeping the
#: whole baseline set on one platform is what makes "only re-capture the states
#: that changed" a coherent rule — a set captured half here and half elsewhere
#: could never be green anywhere.
GOLDEN_PLATFORM = ("darwin", "arm64")


def _platform_now() -> tuple[str, str]:
    return (sys.platform, platform.machine())


@pytest.mark.parametrize("name", [
    pytest.param("srm660c", marks=pytest.mark.slow),
    pytest.param("nac", marks=pytest.mark.slow),
    "toy_lebail",
    "toy_pawley",
    "toy_rich",
    "toy_restraints",
    "toy_stephens",
    "toy_capillary",
    "toy_roughness",
    "toy_anomalous",
])
def test_numpy_path_bit_identical_to_golden(name):
    here = _platform_now()
    if here != GOLDEN_PLATFORM:
        pytest.skip(
            f"bit-identity goldens are pinned to {'/'.join(GOLDEN_PLATFORM)}, running on "
            f"{'/'.join(here)} — measured divergence there is 1 to ~1100 ulp (≤1.7e-13 "
            "relative), i.e. a different libm and summation order, not different code. "
            "See the module docstring and tests/data/README.md."
        )
    path = GOLDEN_DIR / f"{name}.npz"
    if not path.exists():
        pytest.skip(f"golden {path.name} not present")
    got = _capture(name)
    if got is None:
        pytest.skip(f"dataset for state {name!r} not present")
    with np.load(path) as ref:
        assert set(ref.files) == set(got), (
            f"{name}: golden keys {sorted(ref.files)} != captured {sorted(got)}")
        for key in ref.files:
            a, b = ref[key], got[key]
            assert a.shape == b.shape, f"{name}:{key} shape {a.shape} != {b.shape}"
            assert np.array_equal(a, b), (
                f"{name}:{key} diverged from the pre-shim golden "
                f"(max |Δ| = {np.max(np.abs(a - b)) if a.dtype.kind == 'f' else '?'})")


@pytest.mark.parametrize("name", ["toy_rich", "toy_capillary", "toy_stephens"])
def test_the_compiled_path_holds_the_goldens_to_its_own_bar(name):
    """What the WP-1115 compiled tier moves, measured against the same files.

    The tier is the default install's residual, so "the numpy path still
    reproduces the goldens" is the *weaker* half of the statement and this is
    the other one.  Two bars, and which applies is a property of the row rather
    than of the state:

    * a **symmetric** row is bit-identical — the kernel is a transcription of
      the same expressions and ``math.exp`` was measured to agree with numpy's
      ``exp`` bit for bit here;
    * an **FCJ** row agrees to rounding only, because the node sum runs
      sequentially in the kernel where ``_node_mix`` runs a matmul.  That is
      WP-1112's bar one rank on, and 1e-13 relative is the number it set.

    So this asserts the rounding bar for every array and does *not* assert the
    bit, which would pass or fail on whether the parametrised state happens to
    carry axial divergence.  ``toy_rich`` does; the guard is that the two paths
    are compared at all, on states carrying the corrections most likely to
    amplify a last-digit difference through a Jacobian column.
    """
    here = _platform_now()
    if here != GOLDEN_PLATFORM:
        pytest.skip(f"goldens are pinned to {'/'.join(GOLDEN_PLATFORM)}")
    path = GOLDEN_DIR / f"{name}.npz"
    if not path.exists():
        pytest.skip(f"golden {path.name} not present")
    if not compiled.available():
        pytest.skip("the rietx-kernels wheel did not load here: "
                    f"{compiled.unavailable()}")
    got = _capture(name, compiled_path=True)
    if got is None:
        pytest.skip(f"dataset for state {name!r} not present")
    with np.load(path) as ref:
        for key in ref.files:
            a, b = ref[key], got[key]
            if a.dtype.kind != "f":
                assert np.array_equal(a, b), f"{name}:{key} is not a float array"
                continue
            scale = float(np.abs(a).max()) or 1.0
            rel = float(np.abs(a - b).max()) / scale
            assert rel < 1e-13, f"{name}:{key} past the rounding bar at {rel:.2e}"


def test_every_committed_golden_is_gated():
    """A golden file no parameter names is a file nothing checks.

    The gate above skips on two conditions — wrong platform, missing file —
    and a skip is indistinguishable from a pass in a summary line.  This test
    runs everywhere and is what stops a golden from being quietly deleted or
    added without a case: it compares the directory against ``STATES``, which
    is also what the capture entry point writes from.
    """
    on_disk = {p.stem for p in GOLDEN_DIR.glob("*.npz")}
    assert on_disk == set(STATES), (
        f"backend_goldens/ and STATES disagree: only on disk {sorted(on_disk - set(STATES))}, "
        f"only in STATES {sorted(set(STATES) - on_disk)}")


def test_on_the_golden_platform_the_gate_actually_runs():
    """On ``GOLDEN_PLATFORM``, prove the gate above asserts rather than skips.

    The monthly macOS CI job is dispatch-only (WP-1060): the hosted runner is
    measurably not the capture machine — one ulp off on ``toy_rich`` — so its
    goldens step only ever warned.  That leaves ``GOLDEN_PLATFORM``, in
    practice the dev machine, as the only place the bit patterns are checked.
    This guard fails *here* if the gate's skip conditions would fire where
    they must not: every golden present and loadable on the platform the pin
    names.  Known pre-existing limitation, made visible rather than fixed: if
    the dev machine stops being darwin/arm64 the goldens run nowhere, and
    this guard's own skip — named below, counted in every local run — is what
    says so.
    """
    if _platform_now() != GOLDEN_PLATFORM:
        pytest.skip(
            f"not on {'/'.join(GOLDEN_PLATFORM)} — the goldens assert nowhere but "
            "there; if this is the dev machine, the WP-1060 known limitation is "
            "live: re-capture the set and move GOLDEN_PLATFORM")
    for name in STATES:
        path = GOLDEN_DIR / f"{name}.npz"
        assert path.exists(), (
            f"golden {path.name} missing on {'/'.join(GOLDEN_PLATFORM)} — the gate "
            "above would skip, and nowhere else checks these bits")
        with np.load(path) as ref:
            assert ref.files, f"golden {path.name} loads but holds no arrays"


if __name__ == "__main__":
    # Capture goldens.  Named states only by default is deliberate: these files
    # are environment-pinned bit patterns, and re-capturing a state that did not
    # change silently rebases a baseline that was meant to be a fixed point.
    # Pass state names to add or refresh exactly those; pass nothing to see the
    # list rather than to overwrite all of them.
    if _platform_now() != GOLDEN_PLATFORM:
        raise SystemExit(
            f"refusing to capture on {'/'.join(_platform_now())}: the committed baseline set is "
            f"pinned to {'/'.join(GOLDEN_PLATFORM)}.  Capturing one state here would produce a "
            "set no platform can be green on, since these files differ between libm/BLAS builds "
            "(see the module docstring).  Re-capture the whole set, and move GOLDEN_PLATFORM, "
            "only as a deliberate change of capture platform."
        )

    wanted = sys.argv[1:]
    if not wanted:
        print("usage: python -m tests.test_backend_shim STATE [STATE ...]")
        print(f"states: {', '.join(STATES)}")
        raise SystemExit(2)
    unknown = [n for n in wanted if n not in STATES]
    if unknown:
        raise SystemExit(f"unknown state(s): {', '.join(unknown)}")
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in wanted:
        got = _capture(name)
        if got is None:
            print(f"{name}: dataset missing, skipped")
            continue
        out = GOLDEN_DIR / f"{name}.npz"
        np.savez_compressed(out, **got)
        sizes = {k: v.shape for k, v in got.items()}
        print(f"{name}: wrote {out} ({out.stat().st_size / 1e6:.2f} MB) {sizes}")
