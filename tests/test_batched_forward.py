"""The batched numpy forward against the per-reflection scalar loop.

WP-1120 moved ``CompiledModel.phase_component`` onto the WP-1112 batched
planes for the numpy backend and kept the loop as ``_phase_component_scalar``.
The equivalence bars are WP-1112's, one rank up — they now govern the
*residual*, not only the derivative bases, so what they cost is visible in
every refined number rather than in a Jacobian column:

* **symmetric rows are exactly bit-equal** to the loop — same elementwise
  expressions, broadcast — so the assertion is on the raw bit pattern and not
  a tolerance;
* **FCJ rows agree to rounding, never to the bit**: the node-weighted sum is
  a batched matmul where the loop ran one dgemv per reflection.  The bar is
  the same ~1e-13 relative as the bases', and the measured deviation on the
  WP-1114 trigger case was 1.7e-16 (~1 ulp);
* a fit on FCJ data therefore lands on the **same parameters and the same
  esds** to well inside their own precision, which is the statement a user
  reads.  It need not take the same *number* of evaluations, and on the
  trigger case it does not (363 vs 364) — that is what an ulp reaching a
  trust-region decision looks like, and pinning it would pin noise.

The dispatch is also pinned here, because it is a claim about a backend this
venv need not have installed: anything that is not numpy takes the loop.

**Every test here runs on the numpy path**, declared by the fixture below and
not inherited (tests/CLAUDE.md).  The bars above are statements about two numpy
implementations — the batched builder and the loop — and WP-1115's compiled
tier is a third, with its own bar, held to it in
``tests/test_compiled_kernels.py``.  Letting these inherit the default made
them pass here and fail on Linux CI, which is the measurement that produced
the rule: the C library's ``exp``, which the kernels call, matches numpy's bit
for bit on darwin/arm64 and misses it by ~3e-17 on Linux.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement, RefinementPlan, Stage
from rietx.model import compiled
from rietx.model.compiled import SPELL_FORWARD
from rietx.model.forward import CompiledModel, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure


def _toy_structure() -> Structure:
    """Two phases, so the per-phase accumulation grouping is exercised."""
    def phase(name: str, a: float, scale: float) -> Phase:
        return Phase(
            name=name,
            space_group="P21/c",
            cell=Cell(
                a=Parameter(value=a), b=Parameter(value=6.4),
                c=Parameter(value=7.8), alpha=Parameter(value=90.0),
                beta=Parameter(value=105.0), gamma=Parameter(value=90.0),
            ),
            atoms=[
                Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                     y=Parameter(value=0.0), z=Parameter(value=0.0)),
                Atom(label="C", species="C", x=Parameter(value=0.23),
                     y=Parameter(value=0.31), z=Parameter(value=0.42)),
            ],
            scale=Parameter(value=scale),
        )
    return Structure(phases=[phase("toy", 5.2, 1e-3),
                             phase("toy2", 5.6, 4e-4)])


def _instrument(*, axial: bool) -> Instrument:
    if axial:
        ins = Instrument.bragg_brentano(radiation="CuKa",
                                        goniometer_radius_mm=173.0)
        ins.geometry.axial_sl.value = 0.025
        ins.geometry.axial_hl.value = 0.030
    else:
        ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    return ins


def _compiled(*, axial: bool, mode: str = "rietveld"):
    structure, ins = _toy_structure(), _instrument(axial=axial)
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    model = compile_model(structure, ins, pattern, mode=mode)
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def _bits_equal(a: np.ndarray, b: np.ndarray) -> bool:
    """Raw bit patterns, so a signed zero or a NaN is not quietly forgiven."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return a.shape == b.shape and np.array_equal(a.view(np.int64),
                                                 b.view(np.int64))


def _rel(a: np.ndarray, b: np.ndarray) -> float:
    scale = float(np.abs(b).max()) or 1.0
    return float(np.abs(np.asarray(a) - np.asarray(b)).max()) / scale


def _has_fcj(model) -> bool:
    return any(np.any(cp.batch.fcj > 0) for cp in model.phases)


@pytest.fixture(autouse=True)
def _numpy_path():
    """This module's subject is the numpy builder — see the docstring."""
    was = compiled.set_enabled(False)
    yield
    compiled.set_enabled(was)


# -- the two bars -------------------------------------------------------------

def test_symmetric_rows_are_bit_equal_to_the_loop():
    model, values = _compiled(axial=False)
    assert not _has_fcj(model), "fixture stopped being the symmetric case"
    for ip in range(len(model.phases)):
        assert _bits_equal(model._phase_component_batched(ip, values),
                           model._phase_component_scalar(ip, values)), \
            f"phase {ip} moved off the loop's bits"


def test_symmetric_evaluate_is_bit_equal_end_to_end():
    """Through ``bragg_component``'s per-phase grouping and the background."""
    model, values = _compiled(axial=False)
    bragg = np.zeros_like(np.asarray(model.tt))
    for ip in range(len(model.phases)):
        bragg = bragg + model._phase_component_scalar(ip, values)
    assert _bits_equal(model.evaluate(values), model.background(values) + bragg)


def test_the_scatter_is_per_phase_because_regrouping_is_observable():
    """Why ``bragg_component`` scatters once *per phase* and not once overall.

    Addition is commutative but not associative, so a single bincount across
    every phase's rows — the obvious simplification — sums each shared point
    as one long chain instead of one chain per phase, and lands a different
    double.  Pinned by building that variant here: the fixture's two phases
    share most of their points, and the regrouping is worth ~1e-13 relative on
    them, which is a real difference in where a least-squares run stops.

    A weaker guard would be to reverse the phase order, and it would pass
    whatever the code did: with two phases ``P0 + P1`` and ``P1 + P0`` are the
    same double by commutativity.
    """
    model, values = _compiled(axial=False)
    idx_all, w_all = [], []
    for ip in range(len(model.phases)):
        lay = model.phases[ip].batch
        peaks = model.phase_peaks(ip, values)
        pos = lay.gather(peaks, 0)
        omega = model._omega_batch(
            lay, pos, lay.gather(peaks, 1), lay.gather(peaks, 2),
            np.isfinite(pos), values["instrument.geometry.axial_sl"],
            values["instrument.geometry.axial_hl"], SPELL_FORWARD)
        idx_all.append(lay.idx.ravel())
        w_all.append((lay.gather(peaks, 3)[:, None] * omega).ravel())
    regrouped = np.bincount(np.concatenate(idx_all),
                            weights=np.concatenate(w_all),
                            minlength=len(model.tt))

    shared = np.ones(len(model.tt), dtype=bool)
    for cp in model.phases:
        touched = np.zeros(len(model.tt), dtype=bool)
        touched[np.unique(cp.batch.idx)] = True
        shared &= touched
    assert shared.sum() > 100, "fixture's phases stopped overlapping"

    per_phase = np.asarray(model.evaluate(values)) - model.background(values)
    assert not _bits_equal(per_phase, regrouped), \
        "regrouping stopped being observable — this guard now proves nothing"
    assert _rel(per_phase, regrouped) < 1e-12


def test_fcj_rows_agree_with_the_loop_to_rounding():
    model, values = _compiled(axial=True)
    assert _has_fcj(model), "fixture stopped carrying FCJ nodes"
    for ip in range(len(model.phases)):
        got = model._phase_component_batched(ip, values)
        want = model._phase_component_scalar(ip, values)
        assert _rel(got, want) < 1e-13, f"phase {ip} past the rounding bar"


def test_a_fit_on_fcj_data_lands_on_the_same_parameters_and_esds():
    """The bar a user reads, on the case that is *not* bit-equal.

    Both fits see identical data; only the forward differs.  Values and esds
    must agree far inside the esds themselves — the ulp is allowed to move the
    solver's path, never its answer.
    """
    structure, ins = _toy_structure(), _instrument(axial=True)
    grid = np.arange(10.0, 90.0, 0.02)
    blank = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)
    assert _has_fcj(model) and y.max() > 0.0
    rng = np.random.default_rng(1120)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=(y + rng.normal(0.0, 0.02 * y.max(),
                                                    y.shape)).tolist())
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
              max_iter=30),
        Stage("cell", ["phases.*.scale", "instrument.background.*",
                       "phases.*.cell.*"], max_iter=30),
    ])

    def _fit():
        return Refinement(structure.model_copy(deep=True),
                          ins.model_copy(deep=True),
                          history=False).fit(pattern, plan=plan)

    batched = _fit()
    scalar_impl = CompiledModel._phase_component_scalar
    saved = CompiledModel.phase_component
    try:
        CompiledModel.phase_component = scalar_impl
        scalar = _fit()
    finally:
        CompiledModel.phase_component = saved

    rows_b = {p.path: p for p in batched.parameters}
    rows_s = {p.path: p for p in scalar.parameters}
    assert rows_b.keys() == rows_s.keys() and rows_b
    for path, b in rows_b.items():
        s = rows_s[path]
        esd = b.stderr or s.stderr
        if esd:
            assert abs(b.value - s.value) < 1e-3 * esd, f"{path} moved"
        assert (b.stderr is None) == (s.stderr is None)
        if b.stderr:
            assert abs(b.stderr - s.stderr) < 1e-6 * b.stderr, f"{path} esd moved"
    assert abs(batched.statistics.rwp - scalar.statistics.rwp) < 1e-9


# -- the claims the bars rest on ---------------------------------------------

def test_numpy_dispatch_takes_the_batched_path():
    model, values = _compiled(axial=True)
    assert _bits_equal(model.phase_component(0, values),
                       model._phase_component_batched(0, values))


def test_a_non_numpy_backend_is_sent_to_the_loop():
    """The loop is what a traced backend can express.

    Asserted through the dispatch rather than by installing jax or torch,
    which this venv need not have: the numpy namespace answering to another
    name must still reach ``_phase_component_scalar``.
    """
    from rietx.model import forward as fwd

    model, values = _compiled(axial=True)
    real = fwd.get_backend()

    class _Renamed:
        name = "not-numpy"

        def __getattr__(self, item):
            return getattr(real, item)

    saved = fwd.get_backend
    try:
        fwd.get_backend = lambda: _Renamed()
        got = model.phase_component(0, values)
    finally:
        fwd.get_backend = saved
    assert _bits_equal(got, model._phase_component_scalar(0, values))


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_explicit_intensities_reach_the_batched_forward(mode):
    """The hot loop passes ``intensities=`` rather than reading the buffers."""
    model, values = _compiled(axial=True, mode=mode)
    rng = np.random.default_rng(7)
    intens = [rng.uniform(1.0, 5.0, len(cp.hkl_intensity))
              for cp in model.phases]
    for ip in range(len(model.phases)):
        got = model._phase_component_batched(ip, values, intens[ip])
        want = model._phase_component_scalar(ip, values, intens[ip])
        assert _rel(got, want) < 1e-13
    assert _rel(model.evaluate(values, intens),
                model.background(values)
                + sum(model._phase_component_scalar(ip, values, intens[ip])
                      for ip in range(len(model.phases)))) < 1e-13
