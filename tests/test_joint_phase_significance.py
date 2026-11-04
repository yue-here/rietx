"""WP-2003 C10 — the joint fit judges a phase by the single fit's significance.

``tests/test_phase_significance.py`` holds the single fit to WP-1523's two
statistics.  The screen ``CompiledModel.phase_support`` is the scale's
conditional z.  The full test, ``refine._answer_significance``, is the scale
over its counting-noise esd, marginal over the columns that move the peaks.
Until C10 the joint fit read the screen alone, at the stage start and at the
answer, so under the same 3σ it held and restored less.

The fixture is that file's blank frame (#481's seed 107) twice, once per
histogram: background and Poisson noise, no LaB₆.  Measured 2026-11-03
(macOS arm64, ``[dev]``), each stage answer's ``(screen, significance)`` in
both histograms under ``mccusker_default``:

* screen alone: (2.24, 2.24), (2.50, 2.50), (2.50, 2.50), (3.25, 2.61),
  (3.73, 1.60), (3.73, 1.60).  The ``profile_w`` answer released the shared
  cell on the screen's 3.25σ, the cell chased the noise, and the result
  reported a = 4.1517 ± 0.0168 Å with no ``PHASE_UNCONSTRAINED``.
* aligned: (2.24, 2.24), (2.50, 2.50), (2.24, 2.24), (2.68, 2.68),
  (3.03, 1.68), (2.24, 2.24).  The cell is held from the ``cell`` stage on,
  and ``PHASE_UNCONSTRAINED`` reads 2.24σ.  Every stage's evaluation count
  is the single fit's on one copy: 2, 10, 1, 16, 19, 2.

The assertions read the mechanism rather than the readings, which sit within
1.4σ of the threshold.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import rietx as rx
from rietx import multi
from rietx.model.forward import PHASE_SUPPORT_SIGMA
from rietx.params.multi import SharingMap
from tests.test_phase_significance import A0, _assert_prior_holds, _draw, _lab6, _unfitted

pytestmark = pytest.mark.xdist_group("joint-phase-significance")

OUT = Path(__file__).parent / "output"


def _joint_fit(pattern, monkeypatch, *, sharing=None, plan="mccusker_default",
               events=None, start=_unfitted):
    """Two copies of ``pattern``, recording ``(screen, significance)`` per
    histogram at every stage answer, and the obs/calc/diff plot per pattern."""
    record: list[list[tuple[float, float]]] = []
    inner = multi._joint_answer_significance

    def spy(models, mtable, outcome, held, reach, backend, **kw):
        out = inner(models, mtable, outcome, held, reach, backend, **kw)
        screen = multi._joint_screen(models, mtable)
        record.append([(float(s[0]), float(z[0])) for s, z in zip(screen, out,
                                                                   strict=True)])
        return out

    monkeypatch.setattr(multi, "_joint_answer_significance", spy)
    structure, ins = start()
    ref = rx.MultiHistogramRefinement(structure, [ins, ins.model_copy(deep=True)],
                                      sharing=sharing)
    result = ref.fit([pattern, pattern.model_copy(deep=True)], plan=plan,
                     events=None if events is None else events.append)
    OUT.mkdir(exist_ok=True)
    name = (os.environ["PYTEST_CURRENT_TEST"].split("::")[-1]
            .split(" ")[0].split("@")[0].replace("[", "_").replace("]", ""))
    for h in range(2):
        result.for_histogram(h).plot(OUT / f"joint_significance_{name}_h{h}.png")
    return ref, result, record


@pytest.fixture(scope="module")
def blank():
    return _draw(_lab6(A0, 0.0), np.random.default_rng(107))


@pytest.mark.parametrize("sharing", [None, SharingMap(per_histogram=["phases.*"])],
                         ids=["shared", "per_histogram"])
def test_a_blank_pair_past_the_screen_is_judged_by_its_marginal_z(
        blank, sharing, monkeypatch):
    """The screen passes at an answer the marginal does not, and the cell stays held.

    Shared, the cell is one column of the joint fit, held because neither
    pattern sees the phase.  Per histogram, each pattern holds its own copy.
    """
    events: list[dict] = []
    _, result, record = _joint_fit(blank, monkeypatch, sharing=sharing,
                                   events=events)
    assert any(s >= PHASE_SUPPORT_SIGMA > z for row in record for s, z in row), record
    assert all(z < PHASE_SUPPORT_SIGMA for row in record for _, z in row), record
    cells = ({"phases.0.cell.a"} if sharing is None
             else {"hist.0.phases.0.cell.a", "hist.1.phases.0.cell.a"})
    assert cells <= set(result.stages[-1].held)
    assert not any(cells & set(st.released) for st in result.stages)
    assert not cells & {p.path for p in result.parameters}
    (finding,) = [d for d in result.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert finding.value < PHASE_SUPPORT_SIGMA
    assert "against the counting noise" in finding.message
    assert set(finding.where) == cells
    # each stage after one that ended with the cell held starts with it held
    for cell in cells:
        assert _assert_prior_holds(result, events, path=cell) >= 1


def test_a_weak_real_pair_is_still_refined(monkeypatch):
    """A planted scale of 2.5e-7 in both patterns is seen at every answer past
    the screen, and the shared cell refines with an esd."""
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    _, result, record = _joint_fit(pattern, monkeypatch)
    assert record[-1][0][1] >= PHASE_SUPPORT_SIGMA, record
    a = {p.path: p for p in result.parameters}.get("phases.0.cell.a")
    assert a is not None and a.stderr is not None
    assert abs(a.value - A0) < 1e-3
    assert not any(st.held for st in result.stages[-1:])
    assert "PHASE_UNCONSTRAINED" not in {d.code for d in result.diagnostics}


def test_the_blocked_matrix_reads_the_dense_one(monkeypatch):
    """The significance off a ``BlockJacobian`` agrees with the dense matrix.

    A joint fit past ``DENSE_JACOBIAN_MAX_BYTES`` keeps its Jacobian in
    blocks (WP-1325), and the marginal then zeroes the columns it leaves out
    rather than slicing them.  Read at the weak pair's answer, where every
    column is free and the marginal is below the screen.
    """
    pattern = _draw(_lab6(A0, 2.5e-7), np.random.default_rng(200))
    ref, _, _ = _joint_fit(pattern, monkeypatch)
    models, mtable = ref._models, ref.mtable
    dense, cut = (multi._joint_answer_significance(
        models, mtable, SimpleNamespace(moment_angle_tests=None, jacobian_layout=lay),
        [], {}, "numpy") for lay in ("dense", "blocked"))
    screen = multi._joint_screen(models, mtable)
    assert all(z[0] < s[0] for z, s in zip(dense, screen, strict=True))
    np.testing.assert_allclose(np.concatenate(cut), np.concatenate(dense), rtol=1e-9)
