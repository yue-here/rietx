"""WP-0404 — cross-backend Jacobian agreement.

DESIGN.md's mitigation for *backend drift* (small op vocabulary + mandatory
cross-backend tests), made executable: every way rietx can produce a Jacobian
is compared against the analytic one on the same compiled state, so a backend
that starts computing a different derivative is caught here rather than in an
esd three milestones later.

The matrix
----------
**Methods** (all compared against the analytic assembly, ``backend="numpy"``
under the default fp64 policy):

* ``fd`` — central differences of the numpy residual, the reference that is
  independent of *both* the analytic chain and autodiff;
* ``jax`` — chunked jacfwd (WP-0402), ``importorskip``-gated;
* ``torch`` — fp64 CPU ``torch.func.jvp`` (WP-0408), ``importorskip``-gated;
* ``numpy+fp32`` / ``jax+fp32`` / ``torch+fp32`` — the WP-0403 mixed-precision
  *policy*, which is not a backend but a layer over whichever one built the
  columns, so it composes with all three and needs no optional dependency.

The Apple-GPU backend (``torch-mps``) is deliberately **not** a row here: its
fp32 is the device's, not a policy's, so it is compared against the *torch fp64*
Jacobian under WP-0403's reduced-precision bars in
``tests/test_backend_torch.py`` rather than against the analytic one under the
fp64 bars used below.

**Configs**: the 18 ``ANALYTIC_FAMILIES`` on the v0.2 lab state, plus the five
WP-0401 golden states — ``toy_lebail`` (Le Bail snapshot + P-spline penalty
rows), ``toy_pawley`` (aux intensity block + overlap-restraint rows),
``toy_rich`` (aniso ADPs + March-Dollase + *nonzero* extinction + displacement/
transparency), and the real-data ``srm660c`` / ``nac`` (marked ``slow``).
Multi-histogram (stacked ``run_multi_least_squares`` layout) and the
stage-boundary recompiles get their own tests below.  Le Bail and Pawley are
single-histogram only — WP-0308 shipped multi-histogram as Rietveld-only,
because per-pattern intensity extractions are not a shared quantity.

Tolerances
----------
The fp32 bars are **imported** from ``backend.linalg64`` (WP-0403 owns them);
restating the numbers here would be the exact drift this file exists to catch.
The fp64 bars are declared here, in the v0.2 style: per-column relative L2
< 5e-3 and cosine > 0.99999.

Two documented exceptions, neither of them drift:

* **The FCJ S/L == H/L kink.**  The quadrature split point ξ_kink = |S/L − H/L|
  sits at its own non-differentiable zero when the two axial ratios are equal
  (``srm660c`` starts exactly there), so the analytic node-FD (right-sided),
  jacfwd (sign(0) = 0 subgradient) and central FD legitimately disagree at the
  few-1e-3 level — measured jax-vs-analytic 6.1e-3 on ``axial_hl``.  Those two
  columns get WP-0402's loose bar, and only when the state actually sits on the
  kink.  ``_lab_state``/``toy_rich`` use unequal ratios on purpose.
* **Axial columns routed to FD** (``DerivativeBases.axial_ok`` False, i.e. an
  axial ratio ≤ 0 with FCJ nodes allocated): autodiff correctness *at* that
  discontinuity was declared out of scope in WP-0401, so those columns are
  excluded explicitly rather than quietly tolerated.  No config here triggers
  it; the check asserts that, so the exclusion cannot go silent.

Why central differences
-----------------------
Forward differences carry O(h) truncation error, and on real data with sharp
peaks that is not small: measured against the analytic column, forward FD sits
6.2e-3 away on ``srm660c``'s ``phases.0.cell.a`` and 4.7e-3 on ``nac``'s — at or
past the 5e-3 bar, for reasons that have nothing to do with any backend.  The
same two columns with central differences (O(h²)) land at 4.3e-5 and 2.2e-5.  A
bar loose enough to accommodate forward FD would be too loose to catch drift, so
the FD *reference* here is central; the forward-difference variant remains
under test where it belongs, as the v0.2 harness
(``test_v02_core.test_analytic_jacobian_matches_fd``).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.backend.linalg64 import (
    COLUMN_COSINE_MIN,
    COLUMN_REL_L2_MAX,
    FP32_JACOBIAN,
    precision_policy,
)
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import (
    _jacobian_for,
    _make_jacobian,
    _make_residual,
    _multi_closures,
    run_least_squares,
)
from rietx.params.vector import VAR_PREFIX, AffineTie, ParameterTable
from rietx.strategy.staged import Stage
from tests.test_backend_shim import STATES
from tests.test_v02_core import ANALYTIC_FAMILIES, _lab_state

#: fp64 agreement bars — declared here (the v0.2 harness's numbers).  The fp32
#: pair is imported above: WP-0403 owns COLUMN_REL_L2_MAX / COLUMN_COSINE_MIN.
REL_L2_MAX = 5e-3
COSINE_MIN = 0.99999

#: the loose bar for a column sitting on a documented kink of the
#: parameterisation (WP-0402's convention, reused verbatim)
KINK_REL_L2_MAX = 2e-2
KINK_COSINE_MIN = 0.9995
KINK_PATHS = frozenset({"instrument.geometry.axial_sl",
                        "instrument.geometry.axial_hl"})

#: a column is "live" when its norm clears this fraction of the largest
#: column's — below it the value is transform-floor noise, not a derivative
DEAD_COL_FRAC = 1e-6

#: FD step, the same rule as the v0.2 harness (applied ±h, centrally)
FD_STEP = 1e-6


# ----------------------------------------------------------------------
# configs: (model, table) at a compiled expansion point
# ----------------------------------------------------------------------
def _families_state(*, shape: str = "tchz_pv"):
    """The 18 analytic column families on the v0.2 lab Bragg-Brentano state.

    ``shape="voigt"`` swaps in WP-0405's true Gaussian⊗Lorentzian peak, which is
    a *different derivative path* for the same parameters: the width columns then
    come from ``voigt_derivs``' ∂V/∂(σ,γ) via the Faddeeva w(z) rather than from
    the TCHZ polynomial forms.  Built here rather than added to
    ``test_backend_shim.STATES`` on purpose — that registry is guarded by
    bit-identity goldens which are WP-0401's artefact, while this file only needs
    a compiled expansion point.
    """
    structure, ins, pattern = _lab_state()
    ins.profile.shape = shape
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ANALYTIC_FAMILIES:
        assert table.set_vary([path], True), path
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    assert model.shape == shape
    return model, table, {}


def _state_families():
    return _families_state()


def _state_families_voigt():
    return _families_state(shape="voigt")


def _state_families_tied():
    """``families`` with user constraints declared (WP-1070).

    A tie is a *new derivative path*, and an asymmetric one.  The traced
    backends get it for free — ``decode`` is a constant matmul and autodiff
    walks straight through C — while the numpy Jacobian has to *choose* a branch
    from the rows C touches, because each analytic branch computes only what it
    was written for.  So this row is where the choice is checked against three
    independent opinions.

    Three shapes, one per outcome of that choice: an identity tie and a general
    affine one (scale ≠ 1 **and** a constant) on the peak-chain branch, which is
    widened to cover them, and a background tie the gate sends to the
    whole-model FD fallback instead — so the one column numpy finite-differences
    is compared against exact ones.
    """
    structure, ins, pattern = _lab_state()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_tie("phases.0.atoms.1.occ",
                  AffineTie.identity("phases.0.atoms.0.occ"))
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=(("phases.0.atoms.0.biso", 2.0),), const=0.1))
    table.set_tie("instrument.background.c1",
                  AffineTie.identity("instrument.background.c0"))
    table.refresh_ties()
    for path in [*ANALYTIC_FAMILIES, "instrument.background.c0"]:
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_families_variable():
    """A **named variable** carrying the columns instead of a model path (WP-1119).

    The row ``families_tied`` is one rank up: there, a model parameter is the
    master and its name is what ``_make_jacobian`` dispatches on.  Here nothing
    in the model is the master — ``vars.B`` is a synthetic entry with no field
    behind it — so the free path's name matches **no** analytic branch, and the
    numpy Jacobian has to decide the branch from what the column *reaches*
    instead (``_column_identities``).  That is a new way to widen C, which is
    what obliges this file to grow a row (root CLAUDE.md § Backends).

    It is also the row that would have caught the defect WP-1119 found by
    measuring instead: un-gated, a variable's column falls to the whole-model FD
    fallback while the same constraint spelled with a model master takes the
    peak chain, and the two disagree by ~1e-6.  The traced backends walk
    straight through C either way and so are the independent opinion.

    Three shapes, one per branch the reach can name: four Biso rows on the peak
    chain (several reached paths, all direct), a phase scale at coefficient 1
    on the closed-form ``_scale_column`` (one reached path, the case that is
    licensed to keep the linear branches), and a Wyckoff DOF, where the reach is
    ``[…x, …dof.0]`` and only the *directly* driven ``dof.0`` may name the
    column — otherwise a coordinate DOF is dispatched as a coordinate and takes
    the wrong branch.
    """
    structure, ins, pattern = _lab_state()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for name, value, lo, hi in (("B", 0.5, 0.0, 25.0),
                                ("S", float(structure.phases[0].scale.value),
                                 0.0, np.inf),
                                ("D", 0.1993, -1.0, 1.0)):
        table.add_parameter(f"{VAR_PREFIX}{name}", value, vary=True,
                            lo=lo, hi=hi, transform="identity")
    table.set_tie("phases.0.atoms.0.biso", AffineTie.identity(f"{VAR_PREFIX}B"))
    table.set_tie("phases.0.atoms.1.biso",
                  AffineTie(terms=((f"{VAR_PREFIX}B", 2.0),), const=0.1))
    table.set_tie("phases.0.scale", AffineTie.identity(f"{VAR_PREFIX}S"))
    table.set_tie("phases.0.atoms.1.dof.0", AffineTie.identity(f"{VAR_PREFIX}D"))
    table.refresh_ties()
    for path in ("phases.0.cell.a", "instrument.background.c0"):
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_capillary_offsets():
    """The eq (4) capillary displacement pair, both free (WP-1073).

    A new derivative path with no row of its own until now: the two offsets
    move the peak *position* through a shape (sin 2θ, cos 2θ) that no other
    state carries, and the numpy Jacobian claims them on the peak-chain branch
    via ``scalar_chain_supported``.  ``instrument.zero_shift`` is freed beside
    them deliberately — {1, sin2θ, cos2θ} is exactly the collinear trio a
    capillary fit has to separate, so this is also the state where three
    backends have to agree about three near-parallel columns rather than one.

    A local config rather than a ninth entry in ``test_backend_shim.STATES``:
    that registry is guarded by bit-identity goldens, and this file needs only
    a compiled expansion point (the ``families_voigt`` precedent above).
    """
    from rietx.schemas.instrument import Instrument
    from rietx.schemas.pattern import PatternData
    from tests.test_backend_shim import _free
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406,
                                    goniometer_radius_mm=200.0)
    ins.source.dispersion = None    # declined, not inherited
    ins.profile.w.value = 8e-3
    ins.zero_shift.value = 0.01
    # off the origin on both axes: at 0 the columns would still be exact, but
    # the *state* would not carry the shift they produce inside the windows
    ins.geometry.capillary_offset_along_beam.value = 0.15
    ins.geometry.capillary_offset_across_beam.value = -0.10

    grid = np.arange(15.0, 90.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, ins, empty, mode="rietveld")
    sim_table = ParameterTable(structure, ins)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 20.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, ins)
    _free(table, ["phases.0.scale", "phases.0.cell.a", "instrument.zero_shift",
                  "instrument.geometry.capillary_offset_along_beam",
                  "instrument.geometry.capillary_offset_across_beam"])
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_extra_components():
    """An additive background peak, all three parameters free.

    A new derivative path with no row of its own: the peak is a term *added* to
    the pattern rather than a factor inside the peak chain, so no analytic
    branch claims it and the numpy reference column is the whole-model FD.  That
    is exactly why it needs a matrix row — an FD column is only "exact because
    it decodes through C like the residual" if the traced backends agree that it
    is, and nothing else here evaluates a parameter the numpy path declines.

    Freed **beside** the background coefficients on purpose: the peak and the
    low-order Chebyshev terms both raise the same region of the curve, so this
    is also the state where the backends have to agree about a nonlinear column
    sitting next to the exact linear ones it is nearly parallel to.
    """
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import (
        HUMP_FWHM_MIN,
        BackgroundChebyshev,
        HumpComponent,
        Instrument,
    )
    from rietx.schemas.pattern import PatternData
    from tests.test_backend_shim import _free
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.source.dispersion = None    # declined, not inherited
    ins.profile.w.value = 8e-3
    ins.background = BackgroundChebyshev.with_terms(3)
    ins.background.coefficients[0].value = 20.0
    # off every identity: a zero height would make the position and width
    # columns identically zero, so the state would carry no information about
    # the two nonlinear paths it exists to cover
    ins.extra_components = [HumpComponent(
        label="hump",
        position=Parameter(value=34.0, unit="deg"),
        height=Parameter(value=120.0, min=0.0, unit="counts",
                         transform="softplus"),
        fwhm=Parameter(value=9.0, min=HUMP_FWHM_MIN, unit="deg",
                       transform="softplus"))]

    grid = np.arange(15.0, 90.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, ins, empty, mode="rietveld")
    sim_table = ParameterTable(structure, ins)
    y = sim.evaluate(sim_table.decode(sim_table.x0()))
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, ins)
    _free(table, ["phases.0.scale", "instrument.background.c0",
                  "instrument.background.c1",
                  "instrument.extra_components.0.position",
                  "instrument.extra_components.0.height",
                  "instrument.extra_components.0.fwhm"])
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}



def _state_extra_peak():
    """A declared sharp peak, the component seam's tick-landing member (1103).

    A separate row from ``extra_components`` rather than a peak added to it,
    because the two members reach the residual by different routes and a shared
    state would let one cover for the other: a hump goes through
    ``CompiledModel.background``, which every backend already differentiates as
    part of the background block, while a peak goes through
    ``extra_peak_curve`` — a *windowed* term, scattered with ``window_add``, and
    the only place in the package where ``xp.arcsin`` sits on the derivative
    path (the emission-line Bragg image).

    Two lines, so the Kα2 image and its Lorentz-polarisation gain are both in
    the columns; ``eta`` freed as well as the other three, since the mixing is a
    logit-transformed parameter and no other row in this matrix has one.

    Off every identity, for the reason the hump row states: a zero area would
    make the centre, width and mixing columns identically zero and the state
    would carry no information about the paths it exists to cover.
    """
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import (
        EXTRA_PEAK_FWHM_MIN,
        BackgroundChebyshev,
        Instrument,
        PeakComponent,
    )
    from rietx.schemas.pattern import PatternData
    from tests.test_backend_shim import _free
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    ins = Instrument.bragg_brentano(radiation="CuKa")
    ins.source.dispersion = None    # declined, not inherited
    ins.profile.w.value = 8e-3
    ins.background = BackgroundChebyshev.with_terms(3)
    ins.background.coefficients[0].value = 20.0
    ins.extra_components = [PeakComponent(
        label="holder",
        center=Parameter(value=41.0, min=40.5, max=41.5, unit="deg"),
        area=Parameter(value=260.0, min=0.0, unit="counts*deg",
                       transform="softplus"),
        fwhm=Parameter(value=0.22, min=EXTRA_PEAK_FWHM_MIN, max=0.5,
                       unit="deg", transform="softplus"),
        eta=Parameter(value=0.45, min=0.0, max=1.0, transform="logit"))]

    grid = np.arange(15.0, 90.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, ins, empty, mode="rietveld")
    sim_table = ParameterTable(structure, ins)
    y = sim.evaluate(sim_table.decode(sim_table.x0()))
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, ins)
    _free(table, ["phases.0.scale", "instrument.background.c0",
                  "instrument.extra_components.0.center",
                  "instrument.extra_components.0.area",
                  "instrument.extra_components.0.fwhm",
                  "instrument.extra_components.0.eta"])
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_magnetic():
    """WP-1327: a moment DOF and the structural columns of a magnetic phase.

    The **only** config here whose model is magnetic, and it exists because
    two derivative paths are new: the moment modulus (no analytic branch
    claims ``…moment.dof*``, so it takes the peak-chain column), and a
    coordinate DOF on a phase carrying a moment, which
    ``CompiledModel.structural_grad_supported`` drops from the analytic
    structural branch because ``d_f2_d_xyz`` carries no magnetic term — a
    column built from that kernel would come back short rather than wrong,
    exactly the failure the matrix is for.

    The autodiff rows **decline** on it rather than agreeing, and they say so
    by name: the traced twin refuses any model carrying a moment (the
    Cholesky behind the Cartesian moment frame is not in the ``xp`` protocol),
    so the comparison this config actually makes is the analytic assembly
    against central differences.  ``test_the_magnetic_config_declines_the_traced_
    backends_by_name`` asserts the decline, so the skip below cannot go silent.
    """
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.pattern import PatternData
    from tests.test_backend_shim import _free
    from tests.test_magnetic import _mnf2

    structure = rx.Structure(phases=[_mnf2(biso=0.4)])
    structure.phases[0].scale.value = 0.05
    ins = rx.Instrument.constant_wavelength_neutron(2.4)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.profile.x.value = 0.04
    ins.background = BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = 20.0

    grid = np.arange(8.0, 140.0, 0.05)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, ins, empty, mode="rietveld")
    sim_table = ParameterTable(structure, ins)
    y = sim.evaluate(sim_table.decode(sim_table.x0()))
    # off the expansion point, so no column is dead by construction
    pattern = PatternData(two_theta=sim.tt.tolist(),
                          intensity=(np.asarray(y) * 1.03 + 2.0).tolist())

    table = ParameterTable(structure, ins)
    _free(table, ["phases.0.scale", "phases.0.lor_size",
                  "phases.0.atoms.0.moment.dof0",
                  "phases.0.atoms.1.dof.*", "phases.0.atoms.1.biso",
                  "instrument.background.c0", "instrument.zero_shift"])
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table, {}


def _state_satellites():
    """WP-1326: coordinate and ADP columns of a phase carrying a propagation vector.

    The new derivative path is the **masked** ``df2`` branch in
    ``CompiledModel``'s analytic structural columns: a satellite row has no
    nuclear structure factor, so its derivative is multiplied by the same
    ``_nuclear_mask`` the forward model applies.  No other config has a mask
    and no moment, and a moment would route the coordinate columns away from
    that branch (``structural_grad_supported``), so this is the only row that
    reaches it — a column that forgot the mask would carry intensity
    derivatives on rows the residual draws at exactly zero.

    One general-position atom (three coordinate DOFs, a free Biso) and one
    anisotropic atom on a special position (its Uᵢⱼ DOFs), under k = (0, 0, ½)
    on ``P m m m``, which puts a satellite between every pair of nuclear
    lines along c*.
    """
    import rietx as rx
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.pattern import PatternData
    from rietx.schemas.structure import AnisoU
    from tests.test_backend_shim import _free

    P = rx.Parameter
    cell = rx.Cell(a=P(value=4.0), b=P(value=5.0), c=P(value=6.0),
                   alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))
    structure = rx.Structure(phases=[rx.Phase(
        name="sat", space_group="P m m m", cell=cell,
        atoms=[rx.Atom(label="Fe", species="Fe", x=P(value=0.13),
                       y=P(value=0.27), z=P(value=0.31), biso=P(value=0.5)),
               rx.Atom(label="O", species="O", x=P(value=0.5),
                       y=P(value=0.5), z=P(value=0.5), biso=P(value=0.6),
                       aniso=AnisoU.isotropic(0.008, cell))],
        scale=P(value=0.05), propagation_vector=(0, 0, "1/2"))])
    ins = rx.Instrument.constant_wavelength_neutron(2.4)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.profile.x.value = 0.04
    ins.background = BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = 20.0

    grid = np.arange(8.0, 140.0, 0.05)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, ins, empty, mode="rietveld")
    assert sim.phases[0].reflections.is_satellite.any()
    sim_table = ParameterTable(structure, ins)
    y = sim.evaluate(sim_table.decode(sim_table.x0()))
    # off the expansion point, so no column is dead by construction
    pattern = PatternData(two_theta=sim.tt.tolist(),
                          intensity=(np.asarray(y) * 1.03 + 2.0).tolist())

    table = ParameterTable(structure, ins)
    _free(table, ["phases.0.scale", "phases.0.atoms.0.dof.*",
                  "phases.0.atoms.0.biso", "phases.0.atoms.1.adp.*",
                  "instrument.background.c0", "instrument.zero_shift"])
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    assert model.structural_grad_supported(0)
    return model, table, {}


CONFIGS = {"families": _state_families,
           "families_voigt": _state_families_voigt,
           "families_tied": _state_families_tied,
           "families_variable": _state_families_variable,
           "capillary_offsets": _state_capillary_offsets,
           "extra_components": _state_extra_components,
           "extra_peak": _state_extra_peak,
           "magnetic": _state_magnetic,
           "satellites": _state_satellites, **STATES}

#: the fast configs run everywhere; the two real-data ones are `slow`.
#: ``families_voigt`` (WP-0405's shape) and ``toy_restraints`` (WP-0406's extra
#: residual rows) are here because a *new derivative path* that no matrix row
#: evaluates is a path no backend agreement covers — both landed in parallel with
#: WP-0408 and were wired in when the branches were reconciled.
#: ``toy_capillary`` (WP-0501) adds no column of its own — µR is not refinable —
#: but it is the only state where the cell/coordinate/ADP/scale columns chain
#: through a θ-dependent intensity factor that is neither Lp nor extinction.
#: Each config is its own xdist group.  ``_STATE_CACHE`` and ``_JACOBIAN_CACHE``
#: are per-process, so under ``-n auto`` they rebuild once per worker: pinning a
#: config to one worker means its state and its six method Jacobians are built
#: once (jax pays a 1-4 s jit compile per state), while the nine configs still
#: spread across nine workers.  No matrix row is cut.
def _config(name: str, *marks):
    return pytest.param(name, marks=[*marks, pytest.mark.xdist_group(f"xb-{name}")])


CONFIG_PARAMS = [
    _config("families"),
    _config("families_voigt"),
    _config("families_tied"),
    _config("families_variable"),
    _config("capillary_offsets"),
    _config("extra_components"),
    _config("extra_peak"),
    _config("magnetic"),
    _config("satellites"),
    _config("toy_lebail"),
    _config("toy_pawley"),
    _config("toy_rich"),
    _config("toy_restraints"),
    _config("toy_capillary"),
    _config("srm660c", pytest.mark.slow),
    _config("nac", pytest.mark.slow),
]

_STATE_CACHE: dict[str, tuple | None] = {}


def _state(name: str):
    """The config's (model, table), built once per session (states are pure)."""
    if name not in _STATE_CACHE:
        _STATE_CACHE[name] = CONFIGS[name]()
    built = _STATE_CACHE[name]
    if built is None:
        pytest.skip(f"dataset for config {name!r} not present")
    model, table, _extras = built
    return model, table


def _theta(model, table) -> np.ndarray:
    """The full free vector: table θ, plus the Pawley intensity block."""
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    return theta


def _labels(model, table) -> list[str]:
    labels = list(table.free_paths)
    if model.pawley is not None:
        labels += [f"pawley.I{k}" for k in range(model.pawley.n)]
    return labels


def _kink_paths(model, table) -> frozenset[str]:
    """The axial columns, when this state sits exactly on the FCJ S/L == H/L
    kink; empty otherwise (see the module docstring)."""
    values = table.decode(table.x0())
    on_kink = (values["instrument.geometry.axial_sl"]
               == values["instrument.geometry.axial_hl"])
    return KINK_PATHS if on_kink else frozenset()


# ----------------------------------------------------------------------
# methods
# ----------------------------------------------------------------------
#: one built Jacobian callable per (config, backend): jax pays a 1-4 s jit
#: compile per state, and the fp32 row is the *same* callable under a policy
#: read per call — so it must not trigger a second compile.  Keyed by config
#: name, whose state ``_STATE_CACHE`` keeps alive for the session.
_JACOBIAN_CACHE: dict[tuple[str, str], object] = {}


def _for_backend(config: str, model, table, name: str):
    key = (config, name)
    if key not in _JACOBIAN_CACHE:
        _JACOBIAN_CACHE[key] = _jacobian_for(model, table, name)
    return _JACOBIAN_CACHE[key]


def _analytic_jacobian(config, model, table):
    """The reference: the mixed analytic/FD assembly on the numpy backend."""
    return _for_backend(config, model, table, "numpy")


def _central_fd_jacobian(config, model, table):
    """Central differences of the (augmented) numpy residual — the reference
    independent of both the analytic chain and autodiff."""
    residual = _make_residual(model, table)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        cols = []
        for c in range(len(theta)):
            h = FD_STEP * max(1.0, abs(theta[c]))
            tp, tm = theta.copy(), theta.copy()
            tp[c] += h
            tm[c] -= h
            cols.append((residual(tp) - residual(tm)) / (2.0 * h))
        return np.column_stack(cols)

    return jacobian


def _backend_jacobian(name: str):
    """A row for an optional backend: skipped when it is not installed, so the
    same command is green on a numpy-only checkout."""

    def build(config, model, table):
        pytest.importorskip(name)
        if any(getattr(cp, "magnetic", None) is not None
               for cp in model.phases):
            # WP-1327's twin refuses a moment by name, so there is no traced
            # Jacobian to compare; the decline itself is asserted below
            pytest.skip("the magnetic structure factor has no traced twin")
        return _for_backend(config, model, table, name)

    return build


def _fp32_over(name: str):
    """The WP-0403 policy layered over backend ``name`` — not a backend of its
    own, so it composes with every row above and needs no optional install."""
    inner = _backend_jacobian(name) if name != "numpy" else _analytic_jacobian

    def build(config, model, table):
        jac = inner(config, model, table)

        def jacobian(theta: np.ndarray) -> np.ndarray:
            with precision_policy(FP32_JACOBIAN):
                return jac(theta)

        return jacobian

    return build


#: method → (Jacobian builder, rel-L2 bar, cosine bar)
METHODS = {
    "fd": (_central_fd_jacobian, REL_L2_MAX, COSINE_MIN),
    "jax": (_backend_jacobian("jax"), REL_L2_MAX, COSINE_MIN),
    "torch": (_backend_jacobian("torch"), REL_L2_MAX, COSINE_MIN),
    "numpy+fp32": (_fp32_over("numpy"), COLUMN_REL_L2_MAX, COLUMN_COSINE_MIN),
    "jax+fp32": (_fp32_over("jax"), COLUMN_REL_L2_MAX, COLUMN_COSINE_MIN),
    "torch+fp32": (_fp32_over("torch"), COLUMN_REL_L2_MAX, COLUMN_COSINE_MIN),
}


def _assert_columns(J_ref, J_test, labels, *, rel_max, cos_min,
                    kink=frozenset(), what=""):
    """Per-column rel-L2 + cosine agreement, skipping transform-floor columns."""
    assert J_ref.shape == J_test.shape, f"{what}: {J_ref.shape} vs {J_test.shape}"
    scale = np.linalg.norm(J_ref, axis=0).max()
    n_live = 0
    for c in range(J_ref.shape[1]):
        a, b = J_ref[:, c], J_test[:, c]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if max(na, nb) < DEAD_COL_FRAC * scale:
            continue
        n_live += 1
        bar, cbar = ((KINK_REL_L2_MAX, KINK_COSINE_MIN) if labels[c] in kink
                     else (rel_max, cos_min))
        err = np.linalg.norm(a - b) / max(na, nb)
        assert err < bar, f"{what}{labels[c]}: rel-L2 {err:.3e} (bar {bar:g})"
        cos = float(a @ b) / (na * nb)
        assert cos > cbar, f"{what}{labels[c]}: cosine {cos:.8f} (bar {cbar:g})"
    assert n_live > 0, f"{what}every column was dead — the comparison proved nothing"


# ----------------------------------------------------------------------
# the matrix
# ----------------------------------------------------------------------
def test_every_config_defined_here_is_actually_parametrised():
    """A config registered and never run is a matrix row that is not there.

    ``CONFIGS`` builds the states and ``CONFIG_PARAMS`` is what the rows
    iterate, and nothing joined them: a state added to the first alone
    collects zero tests, passes, and reports nothing — the "guard that goes
    quiet instead of red" shape (`tests/CLAUDE.md`).  Measured while adding
    ``families_variable`` (WP-1119), which sat inert through a green run and
    was noticed only because its collection count was checked by hand.

    Scoped to the configs **this file defines**, and that scope is deliberate.
    ``CONFIGS`` also merges ``**STATES`` from ``test_backend_shim``, and three
    of those — ``toy_anomalous``, ``toy_roughness``, ``toy_stephens`` — have no
    row *here*.  That is not the same as untested, and asserting them in would
    say it was: all three carry a numpy bit-identity golden in
    ``test_backend_shim``, and two of them (``toy_stephens``, ``toy_anomalous``)
    also get jax ``jacfwd``-against-analytic agreement in ``test_backend_jax``.
    ``toy_roughness`` is the one with no Jacobian second opinion anywhere, which
    is a question for whoever owns surface roughness rather than for this
    assertion.  Asserted both ways, so a deleted local state whose param
    survives fails too.

    **The local set is derived, not listed** (WP-1103).  It was a literal set
    until a config added to ``CONFIGS`` and to neither this list nor
    ``CONFIG_PARAMS`` collected zero tests and passed — which is precisely the
    failure this test exists to catch, one rank up, and is how ``extra_peak``
    first landed.  A hand-kept list of what to check is the same shape of guard
    as the thing it guards, so it is read off the builders this module defines
    (``fn.__module__``), which no edit can forget to update.
    """
    local = {name for name, fn in CONFIGS.items()
             if getattr(fn, "__module__", None) == __name__}
    assert local <= set(CONFIGS), sorted(local - set(CONFIGS))
    parametrised = {p.values[0] for p in CONFIG_PARAMS}
    assert local <= parametrised, (
        "defined here but never run: "
        f"{sorted(local - parametrised)}")
    assert parametrised <= set(CONFIGS), (
        f"parametrised with no state: {sorted(parametrised - set(CONFIGS))}")


@pytest.mark.parametrize("config", CONFIG_PARAMS)
@pytest.mark.parametrize("method", list(METHODS))
def test_jacobian_matches_analytic(method, config):
    model, table = _state(config)
    build, rel_max, cos_min = METHODS[method]
    theta = _theta(model, table)

    J_ref = _analytic_jacobian(config, model, table)(theta)
    J_test = build(config, model, table)(theta)   # may skip (optional backend)
    _assert_columns(J_ref, J_test, _labels(model, table),
                    rel_max=rel_max, cos_min=cos_min,
                    kink=_kink_paths(model, table),
                    what=f"{config}/{method} ")


def test_the_magnetic_config_declines_the_traced_backends_by_name():
    """The skip in ``_backend_jacobian`` above, made a measured fact.

    WP-1327's config is the only magnetic model in this file, and its autodiff
    rows are skipped rather than compared.  That is only honest if the twin
    really refuses — a twin that silently dropped the magnetic term would
    produce a Jacobian, agree with nothing, and the skip would be hiding it.
    """
    model, table = _state("magnetic")
    assert any(cp.magnetic is not None for cp in model.phases)
    assert not model.structural_grad_supported(0)
    asked = 0
    for name in ("jax", "torch"):
        try:
            __import__(name)
        except ImportError:                  # a numpy-only checkout
            continue
        asked += 1
        with pytest.raises(NotImplementedError, match="magnetic"):
            _jacobian_for(model, table, name)
    if not asked:
        pytest.skip("no autodiff backend installed")


@pytest.mark.parametrize("config", CONFIG_PARAMS)
def test_axial_columns_are_not_silently_fd_routed(config):
    """``axial_ok`` False sends the axial columns to plain FD, and autodiff *at*
    that discontinuity is out of scope (WP-0401).  No config here triggers it —
    asserted, so the exclusion can never become a silent pass."""
    model, table = _state(config)
    values = table.decode(table.x0())
    if not any(p in table.free_paths for p in KINK_PATHS):
        pytest.skip("no axial columns in this config")
    bases = model.derivative_bases(
        values, None if model.mode == "rietveld" else
        [cp.hkl_intensity for cp in model.phases])
    assert bases.axial_ok, (
        f"{config}: axial columns fell back to FD — exclude them explicitly "
        "rather than comparing autodiff at the FCJ discontinuity")


# ----------------------------------------------------------------------
# multi-histogram: the stacked layout
# ----------------------------------------------------------------------
#: the free set for the joint state — one shared structural column (the cubic
#: cell) plus per-histogram scale, background, zero, width and **wavelength**.
#:
#: The wavelength can only live here.  A single-histogram table refuses a free λ
#: by construction (exactly degenerate with the cell —
#: ``params.vector.check_wavelength_freedom``), so the joint state is the only
#: config in this file able to free one, and it has to: λ is a derivative path
#: like any other and this file's rule is that its configs grow whenever one
#: does.  Scoped to histogram 1, because freeing both copies is the degeneracy
#: back again.
MULTI_GLOBS = ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
               "instrument.zero_shift", "instrument.profile.w",
               "hist.1.instrument.source.lines.0.wavelength"]

_MULTI_CACHE: dict[str, tuple] = {}


def _multi_state():
    """Two LaB6 patterns of one crystal at two wavelengths (the WP-0308 state),
    compiled per histogram and wired through a ``MultiParameterTable``."""
    if "state" not in _MULTI_CACHE:
        from rietx.params.multi import MultiParameterTable
        from tests.test_multi_histogram import perturbed_inputs, synthesize

        data = [synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                           bkg=[40.0, -6.0, 1.5], seed=1),
                synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                           bkg=[70.0, 5.0, -2.0], seed=2)]
        structure, instruments = perturbed_inputs()
        mtable = MultiParameterTable(structure, instruments)
        mtable.set_vary(["*"], False)
        assert mtable.set_vary(MULTI_GLOBS, True)
        mtable.apply_to_models()
        models = [compile_model(s, ins, d, mode="rietveld",
                                moving_paths=set(t.moving_paths))
                  for s, ins, d, t in zip(mtable.structures, mtable.instruments,
                                          data, mtable.tables, strict=True)]
        _MULTI_CACHE["state"] = (models, mtable)
    return _MULTI_CACHE["state"]


def _multi_jacobian(backend: str):
    key = f"jac:{backend}"
    if key not in _MULTI_CACHE:
        models, mtable = _multi_state()
        _MULTI_CACHE[key] = _multi_closures(models, mtable, backend=backend)[1]
    return _MULTI_CACHE[key]


@pytest.mark.parametrize("method", list(METHODS))
def test_multi_histogram_stacked_jacobian_matches_analytic(method):
    """The same matrix over the stacked ``run_multi_least_squares`` layout.

    Rietveld only, and that is not an omission: WP-0308 shipped multi-histogram
    without Le Bail/Pawley because per-pattern intensity extractions are not a
    shared quantity, and ``multi.py`` raises ``NotImplementedError`` for them.
    """
    models, mtable = _multi_state()
    theta = mtable.x0()
    J_ref = _multi_jacobian("numpy")(theta)
    _build, rel_max, cos_min = METHODS[method]

    if method == "fd":
        residual = _multi_closures(models, mtable)[0]
        cols = []
        for c in range(len(theta)):
            h = FD_STEP * max(1.0, abs(theta[c]))
            tp, tm = theta.copy(), theta.copy()
            tp[c] += h
            tm[c] -= h
            cols.append((residual(tp) - residual(tm)) / (2.0 * h))
        J_test = np.column_stack(cols)
    else:
        backend = method.split("+")[0]
        if backend != "numpy":
            pytest.importorskip(backend)
        jac = _multi_jacobian(backend)
        if method.endswith("+fp32"):
            with precision_policy(FP32_JACOBIAN):
                J_test = jac(theta)
        else:
            J_test = jac(theta)

    _assert_columns(J_ref, J_test, list(mtable.free_paths),
                    rel_max=rel_max, cos_min=cos_min,
                    what=f"multi/{method} ")


def test_multi_histogram_stacked_layout():
    """The layout the agreement above is measured on: one shared column fed by
    *every* histogram's rows, per-histogram columns confined to their own."""
    models, mtable = _multi_state()
    J = _multi_jacobian("numpy")(mtable.x0())
    n_data = [len(m.tt) for m in models]
    blocks = [slice(0, n_data[0]), slice(n_data[0], n_data[0] + n_data[1])]

    paths = list(mtable.free_paths)
    shared = paths.index("phases.0.cell.a")
    assert all(np.linalg.norm(J[b, shared]) > 0 for b in blocks), (
        "the shared cell column must receive contributions from every "
        "histogram — that is what refines it better than one pattern can")

    own = paths.index("hist.1.phases.0.scale")
    assert np.linalg.norm(J[blocks[0], own]) == 0.0
    assert np.linalg.norm(J[blocks[1], own]) > 0.0


# ----------------------------------------------------------------------
# stage boundaries: the frozen state, regenerated
# ----------------------------------------------------------------------
#: recompile gap at a stage boundary — whole-matrix Frobenius and worst single
#: column, both relative.  Measured at the WP-1112 area-criterion windows:
#: srm660c's cell stage 4.4e-4 / 2.6e-3, the toy Le Bail and Pawley cells
#: 1.3e-4 and 3.6e-4 (at the pre-1112 ±30·FWHM margins the same gaps read
#: 5.9e-6 / 6.9e-5 — window edges then sat in deep tail, so re-freezing them
#: after a stage's parameter move shifted almost no weight; an edge now
#: carries its share of the stated ≤2 % discarded area, and the recompile
#: gap is honestly larger).  The bars sit ~4×/3× above the worst measured
#: gap and ~5×/1.3× below the gross-discreteness scale (a dropped
#: reflection or a stale window at a moved cell changes columns by 1e-2 and
#: up) — narrower headroom than the fat-window era's 15×, which is the
#: price of windows that no longer bury their edges.
BOUNDARY_FROBENIUS_MAX = 2e-3
BOUNDARY_COLUMN_MAX = 8e-3


def _frozen_signature(model) -> list[tuple]:
    """What a stage freezes: the hkl list, the per-(line, reflection) window
    index ranges, the FCJ quadrature node counts and the March-Dollase orbit
    members.  Nothing in here may move during a least-squares run."""
    return [(cp.reflections.hkl.copy(), cp.win.copy(), cp.fcj_n.copy(),
             None if cp.po_members is None else cp.po_members.copy())
            for cp in model.phases]


def _same_signature(a: list[tuple], b: list[tuple]) -> bool:
    if len(a) != len(b):
        return False
    return all(all((x is None and y is None) or
                   (x is not None and y is not None and np.array_equal(x, y))
                   for x, y in zip(pa, pb, strict=True))
               for pa, pb in zip(a, b, strict=True))


def _stage_boundaries(data, structure, instrument, stages, *, mode="rietveld"):
    """Run a staged plan, reporting what each recompile did to the Jacobian.

    Mirrors ``Refinement._run_stage`` (free the stage's globs, drop structural
    parameters in the whole-pattern modes, recompile with the new free set,
    carry Le Bail/Pawley intensities) and adds one measurement at each stage
    boundary: the previous stage's *frozen* model and the freshly compiled one,
    both differentiated at the same parameter values with the same table, over
    the columns the two stages share.

    The measurement is taken **before** ``lebail_update``: re-partitioning the
    extracted intensities is a deliberately path-dependent step that changes the
    model itself (measured 8.2e-2 on the toy Le Bail cell boundary, 3.2e-1 for
    Pawley), so including it would swamp the quantity under test — the
    regeneration of the frozen discreteness.
    """
    from rietx.refine import _carry_lebail

    table = ParameterTable(structure, instrument)
    table.set_vary(["*"], False)
    model = None
    prev_free: list[str] = []
    records = []

    for stage in stages:
        table.set_vary(stage.turn_on, True)
        if mode in ("lebail", "pawley"):
            for path in list(table.free_paths):
                if ".atoms." in path or path.endswith(".scale") \
                        or ".source.lines." in path:
                    table.set_vary([path], False)
        table.apply_to_models(structure, instrument)
        fresh = compile_model(structure, instrument, data, mode=mode,
                              moving_paths=set(table.moving_paths))
        carried = False
        if model is not None and mode in ("lebail", "pawley"):
            _carry_lebail(model, fresh)
            carried = True
        if mode == "pawley":
            fresh.build_pawley_restraint()

        if model is not None:
            J_before = _make_jacobian(model, table)(_theta(model, table))
            J_after = _make_jacobian(fresh, table)(_theta(fresh, table))
            idx = [table.free_paths.index(p) for p in prev_free]
            assert J_before.shape[0] == J_after.shape[0], (
                f"{stage.name}: row count changed across the recompile "
                f"({J_before.shape[0]} → {J_after.shape[0]})")
            B, A = J_before[:, idx], J_after[:, idx]
            per_column = [float(np.linalg.norm(A[:, k] - B[:, k])
                                / np.linalg.norm(A[:, k]))
                          for k in range(len(idx))]
            records.append({
                "stage": stage.name,
                "frobenius": float(np.linalg.norm(A - B) / np.linalg.norm(A)),
                "worst_column": max(per_column),
                "worst_path": prev_free[int(np.argmax(per_column))],
                # did the recompile actually produce a different frozen state?
                # if not, "continuity" would be a comparison of identical models
                "frozen_state_moved": not _same_signature(
                    _frozen_signature(model), _frozen_signature(fresh)),
            })

        model = fresh
        if mode == "lebail":
            model.lebail_update(table.decode(table.x0()),
                                n_cycles=stage.lebail_cycles)
        elif mode == "pawley" and not carried:
            model.lebail_update(table.decode(table.x0()),
                                n_cycles=stage.lebail_cycles)
            model.build_pawley_restraint()

        before = _frozen_signature(model)
        outcome = run_least_squares(model, table, max_iter=stage.max_iter)
        assert _same_signature(before, _frozen_signature(model)), (
            f"{stage.name}: the frozen state moved *during* the least-squares "
            "run — the differentiability invariant is broken")
        table.commit(outcome.theta)
        if mode == "lebail":
            model.lebail_update(table.decode(outcome.theta),
                                n_cycles=stage.lebail_cycles)
        prev_free = list(table.free_paths)
        table.apply_to_models(structure, instrument)

    return records


def _assert_boundaries(records, *, what: str):
    for rec in records:
        assert rec["frobenius"] < BOUNDARY_FROBENIUS_MAX, (
            f"{what} → {rec['stage']}: recompile moved the Jacobian by "
            f"{rec['frobenius']:.3e} (Frobenius, relative)")
        assert rec["worst_column"] < BOUNDARY_COLUMN_MAX, (
            f"{what} → {rec['stage']}: {rec['worst_path']} moved "
            f"{rec['worst_column']:.3e} across the recompile")


def test_stage_boundary_continuity_rietveld():
    """The headline case: three stages of the NIST SRM 660c protocol on real
    lab data.  Freeing scale + background cannot move the frozen state at all,
    so that recompile must be bit-identical; the displacement stage moves the
    specimen 0.08 mm, which does shift windows — and the Jacobian follows
    continuously rather than jumping."""
    from tests.test_acceptance_srm660c import build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    records = _stage_boundaries(data, structure, instrument, [
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("disp", ["instrument.geometry.sample_displacement"]),
        Stage("cell", ["phases.*.cell.*"]),
    ])
    assert len(records) == 2
    # scale and background enter neither the reflection list nor the windows:
    # the recompile is the same pure function of the same values
    assert records[0]["frobenius"] == 0.0
    assert not records[0]["frozen_state_moved"]
    # …and the boundary that *did* regenerate the discreteness is the one the
    # bars are about (without this the assertion below would be vacuous)
    assert records[1]["frozen_state_moved"]
    _assert_boundaries(records, what="srm660c/rietveld")


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_stage_boundary_continuity_whole_pattern(mode):
    """Le Bail and Pawley: same claim, with the extracted intensities carried
    across the boundary so what is measured is the frozen-state regeneration
    and not the re-extraction (see :func:`_stage_boundaries`)."""
    from tests.test_backend_shim import _toy_base

    structure, instrument, pattern = _toy_base(c_near_a=(mode == "pawley"))
    records = _stage_boundaries(pattern, structure, instrument, [
        Stage("bkg", ["instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
        Stage("cell", ["phases.*.cell.*"]),
    ], mode=mode)
    assert len(records) == 2
    assert records[0]["frobenius"] == 0.0
    assert records[1]["frozen_state_moved"]
    _assert_boundaries(records, what=f"toy/{mode}")


def test_pawley_intensity_columns_are_exact_across_backends():
    """The Pawley aux block is exactly linear in the intensities (−√w·Σ_l w_l·Ω)
    and never finite-differenced, so every fp64 method must agree to round-off
    there — a loose bar on those columns would be hiding something."""
    model, table = _state("toy_pawley")
    assert model.pawley is not None
    theta = _theta(model, table)
    n_table = len(table.free_paths)
    aux_ref = _analytic_jacobian("toy_pawley", model, table)(theta)[:, n_table:]
    assert np.linalg.norm(aux_ref) > 0

    for method in ("fd", "jax", "torch"):
        build, _rel, _cos = METHODS[method]
        aux = build("toy_pawley", model, table)(theta)[:, n_table:]
        err = np.linalg.norm(aux - aux_ref) / np.linalg.norm(aux_ref)
        # central FD of a linear function is exact to round-off scaled by 1/h
        assert err < (1e-6 if method == "fd" else 1e-9), f"{method}: {err:.3e}"

    # the overlap-restraint rows are the constant matrix R itself, in every row
    n_res = model.pawley.restraint.shape[0]
    np.testing.assert_allclose(aux_ref[-n_res:], model.pawley.restraint,
                               rtol=0, atol=1e-12)
