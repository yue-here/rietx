"""Parameter-space identifiability evidence off the final Jacobian (WP-1056).

Three measurements screened at fit time onto
:class:`~rietx.schemas.results.Identifiability` (the Jacobian is never
serialized, so anything read off it is measured here or lost):

* :func:`top_correlations` — the worst |ρ| pairs with their paths, from the
  same correlation matrix the ``HIGH_CORRELATION`` guard reads, in the same
  ``check_guards`` call, so a fired guard and the quoted evidence can never
  disagree.
* :func:`soft_modes` — the softest eigenvectors of the unit-column normal
  matrix, the object Watkin (2008, J. Appl. Cryst. 41, 491, §3.8) shows the
  pairwise table cannot see.  The covariance these describe is **undamped**:
  both drivers evaluate the returned Jacobian at the accepted solution, never
  inside a damped step (Watkin's Marquardt-λ caveat; asserted by test against
  a fresh evaluation at ``outcome.theta``).
* :func:`exchangeability_scan` — for each *held* candidate in
  :data:`EXCHANGE_CANDIDATE_GLOBS`, the block projection R² of its column
  onto the fitted span, with the partner loadings that name who absorbs it.
  Prince (*Mathematical Techniques in Crystallography and Materials Science*,
  3rd ed., ch. 8) is the textbook statement of why the fitted state cannot
  show this by itself: omitting a correlated variable leaves no bias, only
  survivor esds whose "apparent precision will be illusory".

**The measured fact that shapes the whole design** (spike, 2026-08-12, WP-1056
handover): projection R² is a property of the design matrix over the sampled
range, *not* of the fit.  On the E2 fixture (planted −0.02 mm displacement,
never freed, absorbed by a compensating zero_shift at 128 σ) and on its clean
reference (zero_shift at 1.6 σ from 0) the held-displacement R² is 0.999945
on **both**.  So this module reports numbers only; the two-condition
discriminator — R² high *and* a partner significantly away from its null —
is applied where the nulls are known, in :mod:`rietx.report`.

The scan's extra cost is one Jacobian evaluation at the converged point
(candidates freed all at once, never one at a time), on the numpy reference
path whatever backend ran the fit — an evaluate-only measurement, and the
conformance matrix pins the backends to per-column agreement anyway.
"""

from __future__ import annotations

import fnmatch

import numpy as np

from ..schemas.results import CorrelationPair, ExchangeRow, SoftMode
from . import lapack
from .statistics import block_projection_r2, column_norms

#: how many worst-|ρ| pairs the carrier keeps — a size cap, not a judgment
#: threshold (the report decides where comment starts)
TOP_CORRELATIONS_K = 5

#: how many of the softest modes the carrier keeps
SOFT_MODES_K = 3

#: eigenvector components below this magnitude are omitted from a mode's
#: ``loadings`` — display floor for a unit vector, not a gate
SOFT_MODE_MIN_LOADING = 0.10

#: partner loadings below this magnitude are omitted from an exchange row
EXCHANGE_MIN_LOADING = 0.05

#: The held-parameter families the scan projects — the aberration and scale
#: families the Layer-2 template map names (zero, displacement, transparency,
#: cell; scale, biso; the instrument-profile terms).  A held path outside
#: these families has no template the report could hand an agent, so a row
#: for it would be a number with no reading.  Locked, tied and
#: ``mode_fixed``-held paths are excluded by the scan itself: a mode-fixed
#: path (Le Bail/Pawley scale, atoms) is held because the mode's own
#: intensity machinery replaces it, and that machinery lives outside θ where
#: the projection cannot see it — its row would read "not exchangeable"
#: about a designed-in degeneracy, the confident wrong singleton this WP
#: exists to prevent.  Pinned by test.
EXCHANGE_CANDIDATE_GLOBS = [
    "instrument.zero_shift",
    "instrument.geometry.sample_displacement",
    "instrument.geometry.sample_transparency",
    "instrument.geometry.capillary_offset_along_beam",
    "instrument.geometry.capillary_offset_across_beam",
    "phases.*.cell.*",
    "phases.*.scale",
    "phases.*.atoms.*.biso",
    "instrument.profile.u",
    "instrument.profile.v",
    "instrument.profile.w",
    "instrument.profile.x",
    "instrument.profile.y",
]

#: Parameters whose *identity value* is a physically meaningful null: the
#: aberration corrections, exactly zero when the instrument is ideal.  The
#: report's exchangeability discriminator needs a null to ask "is the fitted
#: partner significantly away from it" — a partner without one (a cell edge,
#: a scale) supports no significance statement and licenses no exchange
#: sentence.  Kept beside the family list so the two cannot drift apart.
NULL_IDENTITY: dict[str, float] = {
    "instrument.zero_shift": 0.0,
    "instrument.geometry.sample_displacement": 0.0,
    "instrument.geometry.sample_transparency": 0.0,
    # eq (4)'s pair: zero exactly when the capillary is on the 2θ circle's
    # centre, which is the aberration's own null — and the reason they belong
    # here is the trio {1, sin2θ, cos2θ} they form with the zero shift, which
    # is what a capillary fit has to separate and this scan is for
    "instrument.geometry.capillary_offset_along_beam": 0.0,
    "instrument.geometry.capillary_offset_across_beam": 0.0,
}


def top_correlations(correlation: np.ndarray, free_paths: list[str],
                     k: int = TOP_CORRELATIONS_K) -> list[CorrelationPair]:
    """The ``k`` worst |ρ| pairs, worst first, keyed by path.

    ``correlation`` is the solver's final matrix (normalised on the raw
    diagonal, so every guard threshold means what it says — see
    ``covariance_estimates``); the values carried here are the same numbers
    the ``HIGH_CORRELATION`` guard thresholds.
    """
    corr = np.asarray(correlation)
    n = len(free_paths)
    if corr.ndim != 2 or corr.shape[0] != n or n < 2:
        return []
    pairs = sorted(((abs(float(corr[i, j])), i, j)
                    for i in range(n) for j in range(i + 1, n)),
                   key=lambda t: -t[0])
    return [CorrelationPair(path_a=free_paths[i], path_b=free_paths[j],
                            rho=float(corr[i, j]))
            for _, i, j in pairs[:k]]


def soft_modes(jac: np.ndarray, free_paths: list[str],
               k: int = SOFT_MODES_K,
               min_loading: float = SOFT_MODE_MIN_LOADING) -> list[SoftMode]:
    """The ``k`` softest modes of the unit-column normal matrix.

    Columns are normalised to unit length before forming ĴᵀĴ, so an
    eigenvalue is dimensionless and independent of every parameter transform:
    for a pair it is 1 − |ρ|, and 0 is exact degeneracy.  Zero-norm columns
    (a parameter with no leverage at this state) are dropped rather than
    carried as spurious null directions.  The eigenvector sign is
    canonicalised (largest component positive) so serialized loadings are
    stable run to run.
    """
    J = np.asarray(jac, dtype=np.float64)
    if J.ndim != 2 or J.shape[1] != len(free_paths):
        return []
    # a tiny column is live, and squaring it would call it zero (WP-1463)
    norms = column_norms(J)
    keep = np.nonzero(norms > 0.0)[0]
    if len(keep) < 2:
        return []
    Jn = J[:, keep] / norms[keep]
    gram = Jn.T @ Jn
    gram = 0.5 * (gram + gram.T)
    eigvals, eigvecs = lapack.eigh(gram)
    out = []
    for m in range(min(k, len(keep))):
        vec = eigvecs[:, m]
        lead = float(vec[np.argmax(np.abs(vec))])
        if lead < 0:
            vec = -vec
        loadings = {free_paths[keep[i]]: float(vec[i])
                    for i in range(len(keep)) if abs(vec[i]) >= min_loading}
        out.append(SoftMode(eigenvalue=float(max(eigvals[m], 0.0)),
                            loadings=loadings))
    return out


def exchangeability_scan(model, table) -> list[ExchangeRow]:
    """Project every held candidate's column onto the fitted span.

    One evaluate-only Jacobian at the converged values with all candidates
    freed at once: vary flags do not enter :func:`compile_model`, so the
    stage's compiled model serves as is, and frozen-per-stage discreteness is
    untouched because nothing is refined (the candidates are freed on the
    live table and restored under ``finally`` — the solve is over and the
    vary set is about to be rebuilt by the next stage anyway, but a scan must
    not be the thing that leaves state behind).  A candidate whose analytic
    column is unsupported falls back per column inside ``_make_jacobian``,
    which is the FD fallback the WP names.

    Skipped entirely (empty list) in Pawley mode: there θ is
    ``[table | per-hkl intensities]`` and the fitted span includes the
    intensity block, which the table-only vector this scan evaluates cannot
    represent — a row measured against the wrong span would be worse than no
    row.
    """
    from ..refine import mode_fixed_path
    from .least_squares import _make_jacobian

    if model.pawley is not None:
        return []
    free_before = list(table.free_paths)
    if not free_before:
        return []
    candidates = [
        e.path for e in table.entries
        if not e.vary and e.tie is None and not e.locked
        and not mode_fixed_path(e.path, model.mode)
        and any(fnmatch.fnmatchcase(e.path, g)
                for g in EXCHANGE_CANDIDATE_GLOBS)
    ]
    if not candidates:
        return []
    try:
        # the paths ``set_vary`` **took**, never the ones it was offered.  It
        # declines a row for reasons this list cannot enumerate and should not
        # try to: a caller's hold (WP-1435), a wavelength the free cell makes
        # degenerate, and whatever is added next.  Asking for the requested
        # set back is an index error on the first one it declines, which is
        # what a held cell produced.
        candidates = table.set_vary(candidates, True)
        if not candidates:
            return []
        paths = list(table.free_paths)
        J = np.asarray(_make_jacobian(model, table)(table.x0()))
        free_idx = [paths.index(p) for p in free_before]
        r2 = block_projection_r2(
            J, free_idx, [(paths.index(c), c) for c in candidates])
        Jf = J[:, free_idx]
        # ``block_projection_r2`` keeps a tiny target column (WP-1463), so its
        # norm must not square to zero here either, or the loading divides by 0
        f_norms = column_norms(Jf)
        rows = []
        for c in candidates:
            if c not in r2:      # zero-norm column: no information either way
                continue
            jc = J[:, paths.index(c)]
            beta, *_ = lapack.lstsq(Jf, jc, rcond=None)
            c_norm = float(column_norms(jc[:, None])[0])
            loading = beta * f_norms / c_norm
            partners = {free_before[i]: float(loading[i])
                        for i in range(len(free_before))
                        if abs(loading[i]) >= EXCHANGE_MIN_LOADING}
            rows.append(ExchangeRow(held=c, r2=r2[c], partners=partners))
        return rows
    finally:
        table.set_vary(candidates, False)
