"""The batched ``derivative_bases`` against the per-row scalar arithmetic.

WP-1112 batched the derivative-bases build (one kernel per symmetric block,
one per frozen FCJ node count) and kept the ragged ``entries`` contract as a
derived view.  The equivalence bars are the WP's, pinned here per scope:

* **symmetric rows are exactly bit-equal** to the per-row kernel — same
  elementwise expressions, broadcast, so ``np.array_equal`` and not a
  tolerance (the 0605 precedent);
* **FCJ rows agree to rounding, never to the bit**: the node-weighted sums
  are matmuls where the loop ran one dgemv per reflection, so the bar is
  ~1e-13 relative against the scalar arithmetic reproduced row by row;
* the batched node generation itself matches ``fcj_offsets_weights`` per
  row, one-hot fallback included — that pins
  ``fcj_offsets_weights_batch`` against its scalar authority.

The scalar reference below **is** the pre-WP-1112 loop body, kept verbatim
as the meaning of the planes; if the batch and this reference ever disagree
past the bars, the batch is wrong, not the reference.

**Every test here runs on the numpy path**, declared by the fixture below and
not inherited (tests/CLAUDE.md).  The subject is the batched *numpy* builder
against the scalar arithmetic, and the bit-equality bar above is a statement
about two numpy expressions.  WP-1115's compiled tier is the default and is a
third implementation with its own stated bar — held to it in
``tests/test_compiled_kernels.py``, which is also where the measurement that
forced this declaration lives: the C library's ``exp``, which the kernels
call, matches numpy's bit for bit on darwin/arm64 and does not on Linux, by
~3e-17.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.model.profiles.fcj import (
    fcj_offsets_weights,
    fcj_offsets_weights_batch,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure

H_POS, H_AX = 1e-5, 1e-7  # the shipped FD steps (derivative_bases)


@pytest.fixture(autouse=True)
def _numpy_path():
    """This module's subject is the numpy builder — see the docstring."""
    was = compiled.set_enabled(False)
    yield
    compiled.set_enabled(was)


def _toy_structure() -> Structure:
    return Structure(phases=[Phase(
        name="toy",
        space_group="P21/c",
        cell=Cell(
            a=Parameter(value=5.2), b=Parameter(value=6.4),
            c=Parameter(value=7.8), alpha=Parameter(value=90.0),
            beta=Parameter(value=105.0), gamma=Parameter(value=90.0),
        ),
        atoms=[
            Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="C", species="C", x=Parameter(value=0.23),
                 y=Parameter(value=0.31), z=Parameter(value=0.42)),
        ],
    )])


def _compiled(*, axial: bool, shape: str = "tchz_pv"):
    structure = _toy_structure()
    structure.phases[0].scale.value = 1e-3
    if axial:
        ins = Instrument.bragg_brentano(radiation="CuKa",
                                        goniometer_radius_mm=173.0)
        ins.geometry.axial_sl.value = 0.025
        ins.geometry.axial_hl.value = 0.030
    else:
        ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    ins.profile.shape = shape
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def _scalar_reference(model, values, *, axial_derivs=True):
    """The pre-WP-1112 loop body, row by row — the meaning of the planes."""
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    entries = []
    for ip, cp in enumerate(model.phases):
        peaks = model.phase_peaks(ip, values)
        rows = []
        for il, (pos, gamma, eta, _intensity) in enumerate(peaks):
            for k in range(len(pos)):
                i0, i1 = cp.win[il, k]
                if i1 <= i0 or not np.isfinite(pos[k]):
                    continue
                x = model.tt[i0:i1]
                n_fcj = int(cp.fcj_n[il, k])
                if n_fcj == 0:
                    pv, d_dx, d_dg, d_de = model._profile_derivs(
                        x - pos[k], float(gamma[k]), float(eta[k]))
                    rows.append((il, k, int(i0), int(i1),
                                 pv, -d_dx, d_dg, d_de, None, None))
                    continue
                phi, om = fcj_offsets_weights(float(pos[k]), sl, hl, n_fcj)
                pv, d_dx, d_dg, d_de = model._profile_derivs(
                    x[None, :] - phi[:, None], float(gamma[k]), float(eta[k]))
                phi1, om1 = fcj_offsets_weights(float(pos[k]) + H_POS,
                                                sl, hl, n_fcj)
                dphi, dom = (phi1 - phi) / H_POS, (om1 - om) / H_POS
                d_pos = (dom @ pv) - ((om * dphi) @ d_dx)
                d_sl = d_hl = None
                if axial_derivs and sl > 0.0 and hl > 0.0:
                    phi2, om2 = fcj_offsets_weights(float(pos[k]),
                                                    sl + H_AX, hl, n_fcj)
                    dphi, dom = (phi2 - phi) / H_AX, (om2 - om) / H_AX
                    d_sl = (dom @ pv) - ((om * dphi) @ d_dx)
                    phi3, om3 = fcj_offsets_weights(float(pos[k]),
                                                    sl, hl + H_AX, n_fcj)
                    dphi, dom = (phi3 - phi) / H_AX, (om3 - om) / H_AX
                    d_hl = (dom @ pv) - ((om * dphi) @ d_dx)
                rows.append((il, k, int(i0), int(i1),
                             om @ pv, d_pos, om @ d_dg, om @ d_de, d_sl, d_hl))
        entries.append(rows)
    return entries


def _rel(a: np.ndarray, b: np.ndarray) -> float:
    scale = float(np.abs(b).max()) or 1.0
    return float(np.abs(a - b).max()) / scale


def _compare(model, values, *, fcj_tol: float | None):
    """Batched entries vs the scalar reference; bit-equality where claimed."""
    bases = model.derivative_bases(values, axial_derivs=True)
    ref = _scalar_reference(model, values)
    assert [len(r) for r in bases.entries] == [len(r) for r in ref]
    n_fcj = 0
    for got_rows, ref_rows, cp in zip(bases.entries, ref, model.phases):
        for got, want in zip(got_rows, ref_rows):
            assert got[:4] == want[:4]
            is_fcj = bool(cp.fcj_n[got[0], got[1]] > 0)
            for g, w in zip(got[4:], want[4:]):
                assert (g is None) == (w is None)
                if g is None:
                    continue
                if not is_fcj:
                    assert np.array_equal(g, w), "symmetric row not bit-equal"
                else:
                    n_fcj += 1
                    assert _rel(g, w) < fcj_tol
    return n_fcj


def test_symmetric_rows_are_bit_equal_to_the_scalar_kernel():
    model, values = _compiled(axial=False)
    assert all(int(cp.fcj_n.sum()) == 0 for cp in model.phases)
    _compare(model, values, fcj_tol=None)


def test_symmetric_rows_are_bit_equal_under_the_voigt_shape():
    model, values = _compiled(axial=False, shape="voigt")
    _compare(model, values, fcj_tol=None)


def test_fcj_rows_agree_with_the_scalar_arithmetic_to_rounding():
    model, values = _compiled(axial=True)
    assert any(int(cp.fcj_n.sum()) > 0 for cp in model.phases)
    n_fcj = _compare(model, values, fcj_tol=1e-13)
    assert n_fcj > 0, "no FCJ comparison ran — the fixture lost its nodes"


def test_batched_node_generation_matches_the_scalar_authority():
    # low angle (deep asymmetry), high angle (mild), and past 90° where the
    # tan cap truncates ξ; 180° exercises the extreme cap (fp tan(π) ≠ 0, so
    # it is a near-degenerate live row, not the fallback)
    tts = np.array([12.0, 88.0, 180.0])
    phi_b, om_b = fcj_offsets_weights_batch(tts, 0.025, 0.030, 12)
    for j, tt in enumerate(tts):
        phi_s, om_s = fcj_offsets_weights(float(tt), 0.025, 0.030, 12)
        assert _rel(phi_b[j], phi_s) < 1e-15
        assert _rel(om_b[j], om_s) < 1e-15
    # the branchless fallback: a zero aperture turns every row one-hot, and
    # the batch must serve the scalar's exact select per row
    phi0, om0 = fcj_offsets_weights_batch(np.array([12.0, 45.0]),
                                          0.025, 0.0, 12)
    for j, tt in enumerate((12.0, 45.0)):
        phi_s, om_s = fcj_offsets_weights(float(tt), 0.025, 0.0, 12)
        assert np.array_equal(phi0[j], phi_s)
        assert np.array_equal(om0[j], om_s)
    assert om0[0, 0] == 1.0 and float(om0[0, 1:].sum()) == 0.0
    assert np.all(phi0[0] == 12.0)


def test_the_ragged_view_keeps_the_none_patterns():
    model, values = _compiled(axial=True)
    full = model.derivative_bases(values, axial_derivs=True)
    lean = model.derivative_bases(values, profile_derivs=False)
    no_ax = model.derivative_bases(values, axial_derivs=False)
    for rows_full, rows_lean, rows_na, cp in zip(
            full.entries, lean.entries, no_ax.entries, model.phases):
        for f, le, na in zip(rows_full, rows_lean, rows_na):
            is_fcj = cp.fcj_n[f[0], f[1]] > 0
            assert (f[8] is not None) == is_fcj  # d_sl rides FCJ rows only
            assert np.array_equal(f[4], le[4])   # Ω survives the lean build
            assert le[5] is le[6] is le[7] is le[8] is le[9] is None
            assert na[5] is not None and na[8] is None and na[9] is None
