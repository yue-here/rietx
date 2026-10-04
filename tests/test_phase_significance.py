"""WP-1523 — a phase is seen when its scale is 3σ from zero against counting noise.

Issue #481's blank frame is background and Poisson noise alone, yet a fit to it
used to report LaB6's cell with an esd and no ``PHASE_UNCONSTRAINED``, or hold
it, depending only on where the fit started.  The old test read one point's
height at 1σ, and a scale fitted to noise lifts that point past it.  The new
one has two halves:

* ``CompiledModel.phase_support`` is the screen, ‖y_p/σ‖₂ over the fitted
  range.  It is the scale's conditional z, so it bounds the full test from
  above, and a phase under ``PHASE_SUPPORT_SIGMA`` there is unseen.
* ``refine._answer_significance`` takes scale / esd(scale) where the screen
  passes: the esd from (JᵀWJ)⁻¹ with no χ²_red or Bérar-Lelann factor,
  marginal over every column that moves the peaks (displacements and
  occupancies left out), with a held phase's columns freed for the
  measurement.

The frame is rebuilt here from the issue script's RNG stream (seed 11,
patterns 0-7 drawn in order), and both starts are the issue's: pattern 0's
fitted models, and the unfitted models the script began from.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.indexing.workflow import ABSENT_SIGMA
from rietx.model.forward import PHASE_SUPPORT_SIGMA, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import Dispersion

pytestmark = pytest.mark.xdist_group("phase-significance")

_refine = __import__("sys").modules["rietx.refine"]
OUT = Path(__file__).parent / "output"

WAVELENGTH, A0, RAMP = 0.4139, 4.15660, 6.4e-5
BLANK = 7
TT = np.arange(3.0, 24.0, 0.005)


def _lab6(a: float, scale: float | None = None) -> rx.Phase:
    phase = rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(a, vary=True),
        atoms=[rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                       y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0)),
               rx.Atom(label="B", species="B", x=rx.Parameter(value=0.1993),
                       y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5))])
    if scale is not None:
        phase.scale.value = scale
        for atom in phase.atoms:
            atom.biso.value = 0.4
    return phase


def _instrument(zero: float, w: float, background) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    # declared, not inherited: the records below were measured with it on
    ins.source.dispersion = Dispersion()
    ins.zero_shift.value, ins.profile.w.value = zero, w
    for c, v in zip(ins.background.coefficients, background, strict=False):
        c.value = v
    return ins


def _draw(phase: rx.Phase, rng) -> rx.PatternData:
    y = rx.Refinement(rx.Structure(phases=[phase]),
                      _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))).predict(TT)
    return rx.PatternData(two_theta=TT.tolist(),
                          intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def _unfitted() -> tuple[rx.Structure, rx.Instrument]:
    return (rx.Structure(phases=[_lab6(A0 * 1.001, 7.5e-4)]),
            _instrument(0.0, 3.75e-4, (0.0, 0.0, 0.0)))


@pytest.fixture(scope="module")
def issue_481():
    """Patterns 0 and 7 of the issue's ramp, and pattern 0's fitted models."""
    rng = np.random.default_rng(11)
    patterns = [_draw(_lab6(A0 * (1 + RAMP * k), 0.0 if k == BLANK else 5e-4), rng)
                for k in range(BLANK + 1)]
    first = rx.Refinement(*_unfitted(), history=False)
    first.fit(patterns[0], plan="mccusker_default")
    starts = {"fitted": lambda: (first.fitted_structure, first.fitted_instrument),
              "unfitted": _unfitted}
    return patterns, starts


def _fit(structure, instrument, pattern, monkeypatch, plan="mccusker_default"):
    """Fit, recording ``(screen, significance)`` at every stage's answer.

    A stage that releases or collapses a phase solves twice and records twice.
    The fit's obs/calc/diff plot goes to ``tests/output/``, named for the
    calling test.
    """
    from rietx.viz.plots import plot_result
    record: list[tuple[float, float]] = []
    inner = _refine._answer_significance

    def spy(model, table, outcome, held, reach, backend):
        out = inner(model, table, outcome, held, reach, backend)
        screen = model.phase_support(table.decode(outcome.theta))
        record.append((round(float(screen[0]), 2), round(float(out[0]), 2)))
        return out

    monkeypatch.setattr(_refine, "_answer_significance", spy)
    result = rx.Refinement(structure, instrument, history=False).fit(
        pattern, plan=plan)
    OUT.mkdir(exist_ok=True)
    name = (os.environ["PYTEST_CURRENT_TEST"].split("::")[-1]
            .split(" ")[0].split("@")[0])
    plot_result(result, path=str(OUT / f"phase_significance_{name}.png"))
    return result, record


def _assert_unseen(result, record):
    assert "phases.0.cell.a" not in {p.path for p in result.parameters}
    (finding,) = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert finding.value < PHASE_SUPPORT_SIGMA
    assert any("phases.0.cell.a" in st.held for st in result.stages)
    assert record and all(z < PHASE_SUPPORT_SIGMA for _, z in record), record


def _assert_seen(result):
    a = {p.path: p for p in result.parameters}.get("phases.0.cell.a")
    assert a is not None and a.stderr is not None
    assert abs(a.value - A0) < 1e-3
    assert "PHASE_UNCONSTRAINED" not in {d.code for d in result.diagnostics}


@pytest.mark.parametrize("start", ["fitted", "unfitted"])
def test_the_blank_frame_holds_its_cell_from_either_start(issue_481, start,
                                                         monkeypatch):
    """Both rows of the WP's table, which used to disagree.

    Before WP-1523 the fitted start released the cell at ``profile_w`` and
    reported 4.14990 ± 0.0016 Å with no finding, while the unfitted start held
    it.  Each stage's answer, as ``(screen, significance)``, measured
    2026-10-04 (macOS arm64, ``[dev]``):

    * fitted: (1.04, 1.04), (1.06, 1.06), (2.33, 2.33), (2.40, 2.40),
      (2.62, 2.62)
    * unfitted: (0.17, 0.17), (0.16, 0.16), (1.49, 1.49), (1.50, 1.50),
      (1.97, 1.97)

    The screen stays under 3σ at every stage of this frame, so the full test
    is never needed; the next test is a frame where it is.
    """
    patterns, starts = issue_481
    _assert_unseen(*_fit(*starts[start](), patterns[BLANK], monkeypatch))


def test_a_blank_frame_past_the_screen_is_judged_by_its_marginal_z(
        issue_481, monkeypatch):
    """Seed 107 of the WP's sweep: noise alone lifts the screen past 3σ.

    Each stage's answer, as ``(screen, significance)``, measured 2026-10-04
    (macOS arm64, ``[dev]``): (2.24, 2.24), (2.50, 2.50), (2.50, 2.50),
    (3.25, 2.61), (3.64, 1.51), (3.64, 1.72).

    Two paths run here.  At the ``profile_w`` answer the cell is held and the
    screen passes, so the held cell is freed for the measurement (2.61).  The
    screen passed at the ``profile`` start, so the cell refined there; at the
    answer its scale reads 1.51σ, so the cell is put back where the stage
    found it and held, and the stage solves again.  The finding quotes 1.51,
    the reading the hold was decided on; the second solve's own, with the
    cell held, is the 1.72.
    """
    _, starts = issue_481
    pattern = _draw(_lab6(A0, 0.0), np.random.default_rng(107))
    result, record = _fit(*starts["unfitted"](), pattern, monkeypatch)
    assert any(s >= PHASE_SUPPORT_SIGMA for s, _ in record), record
    _assert_unseen(result, record)


@pytest.mark.parametrize("start", ["fitted", "unfitted"])
def test_a_weak_real_phase_is_still_refined(issue_481, start, monkeypatch):
    """A planted scale of 2.5e-7, 1/2000 of the ramp's, is seen from both starts.

    It is never held, and its cell lands 1.37e-4 Å from the planted one from
    either start.  Each stage's answer, as ``(screen, significance)``,
    measured 2026-10-04 (macOS arm64, ``[dev]``):

    * fitted: (19.63, 19.53), (19.63, 19.53), (19.64, 19.53), (19.74, 17.75),
      (19.79, 10.17)
    * unfitted: (2.53, 2.53), (4.09, 4.05), (19.04, 18.91), (19.74, 17.74),
      (19.79, 12.29)
    """
    _, starts = issue_481
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    result, record = _fit(*starts[start](), pattern, monkeypatch)
    _assert_seen(result)
    assert record[-1][1] >= PHASE_SUPPORT_SIGMA


def test_a_held_phase_that_appears_is_released(issue_481, monkeypatch):
    """The release path: held at the stage start, freed for the measurement.

    One stage frees scale, background and cell from a scale of 1e-10, so the
    cell is held at the start.  At the answer the held cell is freed to take
    the scale's esd, the phase passes, and the stage solves again.
    Each answer, as ``(screen, significance)``, measured 2026-10-04 (macOS
    arm64, ``[dev]``): (19.63, 19.53) with the held cell freed for the
    measurement, then (19.63, 19.53) after the second solve.
    """
    from rietx.schemas.plan import PlanSpec, StageSpec

    structure = rx.Structure(phases=[_lab6(A0, 1e-10)])
    instrument = _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    plan = PlanSpec(stages=[StageSpec(
        name="all", turn_on=["phases.*.scale", "instrument.background.*",
                             "phases.*.cell.*"])])
    result, record = _fit(structure, instrument, pattern, monkeypatch, plan=plan)
    (stage,) = result.stages
    assert stage.released == ["phases.0.cell.a"] and not stage.held
    assert record[0][1] >= PHASE_SUPPORT_SIGMA
    _assert_seen(result)


def test_the_threshold_is_the_indexing_presence_test():
    """One number means one thing: a phase and a line are present at 3σ."""
    assert PHASE_SUPPORT_SIGMA == ABSENT_SIGMA


@pytest.fixture(scope="module")
def lab6_model():
    """A compiled LaB6 phase at the ramp's own scale, and its values."""
    structure = rx.Structure(phases=[_lab6(A0, 5e-4)])
    ins = _instrument(0.008, 2.5e-4, (40.0, -6.0, 1.5))
    pattern = _draw(structure.phases[0], np.random.default_rng(3))
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def test_phase_support_is_the_integrated_norm(lab6_model):
    """The screen is ‖y_p/σ‖₂ over the fitted range, the scale's conditional z."""
    model, values = lab6_model
    sigma = np.asarray(model.sigma, dtype=np.float64)
    y = np.asarray(model.phase_component(0, values), dtype=np.float64)
    assert model.phase_support(values)[0] == pytest.approx(
        float(np.linalg.norm(y / sigma)), rel=1e-12)


def test_each_reflection_reads_its_own_window_norm(lab6_model):
    """The batched planes against one profile per window, and the phase above
    every one of its reflections, since every contribution is non-negative."""
    model, values = lab6_model
    cp = model.phases[0]
    sigma = np.asarray(model.sigma, dtype=np.float64)
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    rows = model.reflection_support(0, values)
    for il, (pos, gamma, eta, intensity) in enumerate(model.phase_peaks(0, values)):
        for k in range(len(pos)):
            prof = model._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k],
                                             sl, hl)
            if prof is None:
                assert rows[il][k] == 0.0
                continue
            i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
            want = np.linalg.norm(intensity[k] * np.asarray(prof) / sigma[i0:i1])
            assert rows[il][k] == pytest.approx(float(want), rel=1e-9, abs=1e-12)
    best = max(float(np.max(r)) for r in rows)
    assert 0.0 < best <= model.phase_support(values)[0]
