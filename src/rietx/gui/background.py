"""The background curve and the band it may move in (WP-2129).

``GET /api/background`` serves the Background graph tab: the observed pattern
on the fitted channels, the background curve at the working state's values,
and ``band_esd``, the esd of that curve at each channel. The tab draws the band
at a multiple of it. **Nothing is written.**

The band is the esd of a derived quantity, the manual's ``est-derived`` over
``est-cov`` (McCusker et al., 1999, *J. Appl. Cryst.* **32**, 36, § 10: the whole
covariance, never its diagonal). At channel 2θ, with y_b the background curve,

    σ_b(2θ)² = f² · gᵀ Cov g,    g_k = ∂y_b(2θ)/∂θ_k,
    Cov = χ²_red · (JᵀJ)⁻¹,

where J is the full weighted Jacobian at the working state's values, P-spline
penalty rows included (Eilers & Marx, 1996, *Stat. Sci.* **11**, 89), and f is
the Bérar-Lelann factor (Bérar & Lelann, 1991, *J. Appl. Cryst.* **24**, 1) on
the same residual's data rows. Derivation: y_b is linear in its coefficients,
so δy_b = g·δθ to first order, and Cov(δy_b) = g Cov(θ) gᵀ. Cov is the inverse
of the *whole* normal matrix, so its background block is the covariance
marginal over every other free parameter: a scale or Biso that trades against
the background widens the band.

Three choices make it the same number the package's esds are.

- **J and the residual are the solver's own** (``least_squares._make_jacobian``
  and ``_make_residual``), on the compile ``gui.preview`` caches per working
  state, so the columns are the analytic ones a fit takes.
- **The free set is the working one** less what the intensity mode force-fixes
  (``refine.mode_fixed_column``, as ``Refinement.suggest`` builds it): the set a
  one-cycle run refines. A held term has no column and so no variance, which
  is what "a held term keeps its value from the previous cycle" means here.
- **Cov is ``statistics.normal_factors``**, the equilibrated guarded solve every
  esd goes through, with χ²_red and f over the data rows as in
  ``least_squares._covariance_and_inflation``.

g is a central difference of ``CompiledModel.background`` through the table's
decode, taken only on columns whose reach (``ParameterTable.column_reach``)
touches the background; every other column has g = 0. The background is linear
in its coefficients, so the difference is exact there to rounding, and a hump
component's position and width take an ordinary second-order difference.

The answer is absent rather than zero where the chapter's rule says so: with no
free column reaching the background (``band_absent = "no free background
term"``), and where such a column is one the data do not constrain, 1/d = 0
(``"unmeasured"``). The band is linearised at the current values, so before a
fit converges it describes the curvature there and nothing more.

The answer is cached per working state on ``gui.preview``'s key, so a hold, a
vary change or a λ edit, each of which moves the head, recomputes it.
"""

from __future__ import annotations

import threading
import weakref
from typing import Any

import numpy as np

from ..model import rows as row_layout
from ..optimize.least_squares import _make_jacobian, _make_residual, fd_step
from ..optimize.statistics import berar_lelann_factor, normal_factors
from ..viz.packed import Packed
from . import preview

#: one answer per open ``Project``, keyed on ``preview._key``
_CACHE: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_CACHE_LOCK = threading.Lock()


def _free_table(project):
    """The working table with the intensity mode's force-fixed columns dropped."""
    from ..refine import mode_fixed_column

    table = project.refinement._working_table()
    mode = project.doc.mode
    if mode in ("lebail", "pawley"):
        reach = table.column_reach()
        for path in [p for p in table.free_paths
                     if mode_fixed_column(reach.get(p, [p]), mode)]:
            table.set_vary([path], False)
    return table


def _terms(project) -> list[dict[str, Any]]:
    """The background's own rows, as ``GET /api/params`` serves them."""
    out = []
    for row in project.parameters():
        if not row.path.startswith("instrument.background."):
            continue
        out.append({"path": row.path, "value": row.value, "esd": row.esd,
                    "vary": row.vary, "held": row.held,
                    "refinable": row.refinable,
                    "held_because": row.held_because})
    return out


def _kind(instrument) -> dict[str, Any]:
    bkg = instrument.background
    info: dict[str, Any] = {"kind": bkg.kind}
    if bkg.kind == "pspline":
        info["lambda_smooth"] = bkg.lambda_smooth
        info["lambda_units"] = bkg.lambda_units
    return info


def band_esd(model, table) -> tuple[np.ndarray | None, dict[str, Any]]:
    """σ_b at every fitted channel, and the facts the header reports beside it.

    The module docstring has the formula and its derivation. Returns ``None``
    for the band, with ``band_absent`` naming why, where the chapter's
    absent-rather-than-zero rule applies.
    """
    free = list(table.free_paths)
    reach = table.column_reach()
    # the paths ``CompiledModel.background`` reads, never a prefix test: a
    # declared *peak* component is an ``extra_components`` path the curve does
    # not contain, and counting it would draw a zero band as a measured one
    reads = set(model.bkg_paths).union(*map(set, model.component_paths))
    touches = [k for k, p in enumerate(free)
               if any(q in reads for q in reach.get(p, [p]))]
    facts: dict[str, Any] = {"n_free": len(free),
                             "n_background_free": len(touches),
                             "n_other_free": len(free) - len(touches),
                             "chi2_red": None, "esd_inflation": None,
                             "band_absent": None}
    if not touches:
        facts["band_absent"] = "no free background term"
        return None, facts

    theta = np.asarray(table.x0(), dtype=np.float64)
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    n_table = len(free)
    resid = np.asarray(_make_residual(model, table)(theta), dtype=np.float64)
    jac = np.asarray(_make_jacobian(model, table)(theta), dtype=np.float64)
    n_data = row_layout.layout(model)[0].n
    data = resid[:n_data]
    k, inv_d, chi2_red = normal_factors(jac, data, jac.shape[1])
    factor = berar_lelann_factor(data)
    facts["chi2_red"] = chi2_red
    facts["esd_inflation"] = factor

    # g, one column per free parameter reaching the background
    g = np.zeros((n_data, len(touches)), dtype=np.float64)
    for c, col in enumerate(touches):
        h = fd_step(float(theta[col]))
        up, dn = theta[:n_table].copy(), theta[:n_table].copy()
        up[col] += h
        dn[col] -= h
        g[:, c] = (np.asarray(model.background(table.decode(up)), dtype=np.float64)
                   - np.asarray(model.background(table.decode(dn)), dtype=np.float64)
                   ) / (2.0 * h)
    scales = inv_d[touches]
    if np.any((scales == 0.0) & np.any(g != 0.0, axis=0)):
        facts["band_absent"] = "unmeasured"
        return None, facts
    a = g * scales  # g·diag(1/d)
    kb = k[np.ix_(touches, touches)]
    var = np.einsum("ni,ij,nj->n", a, kb, a)
    return factor * np.sqrt(np.maximum(var, 0.0)), facts


def answer(project) -> Packed:
    """The packed answer to ``GET /api/background``; the module docstring has it."""
    key = preview._key(project)
    with _CACHE_LOCK:
        hit = _CACHE.get(project)
        if hit is not None and hit[0] == key:
            return hit[1]
    base = preview._base(project)
    with base.lock:
        model = base.model
        table = _free_table(project)
        esd, facts = band_esd(model, table)
        values = table.decode(table.x0())
        y_bkg = np.asarray(model.background(values), dtype=np.float64)
    arrays = {"two_theta": np.asarray(model.tt, dtype=np.float64),
              "y_obs": np.asarray(model.y_obs, dtype=np.float64),
              "y_background": y_bkg}
    if esd is not None:
        arrays["band_esd"] = esd
    header = {"head": key[0], **_kind(project.refinement.instrument),
              "terms": _terms(project), **facts}
    packed = Packed(header, arrays)
    with _CACHE_LOCK:
        _CACHE[project] = (key, packed)
    return packed
