"""Q-space: the quadratic form, the symmetry-allowed metric subspaces, and
weighted candidate refinement.

**Q is linear in the metric, and that is load-bearing three times over.**  With
hkl assigned,

    Q = 1/d² = A h² + B k² + C l² + D kl + E hl + F hk,
    (A..F) = (G*₁₁, G*₂₂, G*₃₃, 2G*₂₃, 2G*₁₃, 2G*₁₂)

so fitting a cell to assigned lines is a **weighted linear** least-squares
problem; WP-1022's trial-and-error becomes an exact n×n solve; and WP-1021's
dichotomy bounds are attained at box corners, so it searches A..F rather than
(a, b, c, α, β, γ).  Neither d nor 2θ is linear in the metric — that is *why*
indexing works in Q.  *Source*: Altomare, Cuocci, Moliterni & Rizzi (2019),
International Tables for Crystallography Vol. H ch. 3.4, eq. (3.4.2).

**The symmetry-allowed subspace is derived, never tabulated.**  The allowed G*
patterns span ∩ker(A(R) − I) under A(R)[U] = R·U·Rᵀ, which is exactly
``crystallography.wyckoff.adp_basis`` — already exact-rational.  (Which R goes in
is subtle and the wrong choice is invisible in the dimension: see
:func:`metric_basis`.)  So a cubic search is genuinely one-dimensional and a
monoclinic one
four-dimensional, with no case table and no assumption about the setting: the
same code gives the right subspace for hexagonal axes, rhombohedral axes or a
non-standard monoclinic b-unique cell.  ``tests/test_indexing_core.py`` asserts
the derived subspace against ``crystallography.symmetry.cell_constraints`` — the
derivation must reproduce what the refinement side ties, and it asserts *which*
tie rather than how many, because the dimension agrees even when the subspace
does not (WP-1036, and :func:`metric_basis` one rank up).

Note the asymmetry with the refinement side: ``cell_constraints`` is keyed by
**setting** because a caller can hand it any symbol, while this module is keyed
by crystal *system* because a search has no symbol yet — only a lattice — and an
R lattice reaches indexing in hexagonal axes by construction (see
``indexing.extinction.compatible_groups``).

**esds are analytic, by the delta method.**  A..F comes out of a linear solve
with a covariance, and the cell is a smooth function of it, so ∂cell/∂(A..F) is
written out rather than finite-differenced — the analytic preference the whole
package follows.  The derivative that makes it easy is the matrix-inverse one,
dG = −G·dG*·G, since G = (G*)⁻¹.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from ..crystallography.wyckoff import adp_basis
from ..schemas.indexing import METRIC_DOF, q_of_two_theta

#: Which G* component each of A..F is, and its multiplier: (A..F) =
#: (G*₁₁, G*₂₂, G*₃₃, 2G*₂₃, 2G*₁₃, 2G*₁₂).  ``adp_basis`` speaks Voigt order
#: (11, 22, 33, 12, 13, 23) — see ``wyckoff._VOIGT`` — so the two orders differ by
#: a permutation *and* a factor of two on the off-diagonals, and mixing them up
#: silently halves three columns of every design matrix.
_AF_INDEX: tuple[tuple[int, int], ...] = ((0, 0), (1, 1), (2, 2),
                                          (1, 2), (0, 2), (0, 1))
_AF_FACTOR = np.array([1.0, 1.0, 1.0, 2.0, 2.0, 2.0])
#: Voigt slot of each A..F entry, for converting an ``adp_basis`` row.
_VOIGT_OF_AF = (0, 1, 2, 5, 4, 3)

#: Representative holohedral space group per crystal system.  The *lattice* point
#: group is what constrains a metric, so these are the maximal groups of each
#: system in the conventional setting; trigonal is taken in hexagonal axes, which
#: is gemmi's default for R groups and the setting ``params.vector`` ties cells in.
_HOLOHEDRY: dict[str, str] = {
    "triclinic": "P -1",
    "monoclinic": "P 1 2/m 1",
    "orthorhombic": "P m m m",
    "tetragonal": "P 4/m m m",
    "trigonal": "P -3 m 1",
    "hexagonal": "P 6/m m m",
    "cubic": "P m -3 m",
}


def design_matrix(hkl: np.ndarray) -> np.ndarray:
    """(N, 6) matrix M with ``Q = M @ (A..F)`` — the quadratic form as a solve.

    Columns are h², k², l², kl, hl, hk in that order, matching :data:`_AF_INDEX`.
    """
    h = np.asarray(hkl, dtype=np.float64)
    if h.ndim != 2 or h.shape[1] != 3:
        raise ValueError("hkl must be (N, 3)")
    return np.column_stack([h[:, 0] ** 2, h[:, 1] ** 2, h[:, 2] ** 2,
                            h[:, 1] * h[:, 2], h[:, 0] * h[:, 2],
                            h[:, 0] * h[:, 1]])


def centring_allows(hkl: np.ndarray, centring: str) -> np.ndarray:
    """Which hkl a Bravais centring allows — the *lattice* absences, only.

    Space-group absences are not known until an extinction symbol is determined
    (``indexing.extinction``, which needs a cell first) and must never be assumed
    here: "lattice-possible" is exactly the
    population de Wolff's and Smith & Snyder's denominators count.
    """
    h, k, ll = hkl[:, 0], hkl[:, 1], hkl[:, 2]
    if centring in ("", "P"):
        return np.ones(len(hkl), dtype=bool)
    if centring == "I":
        return (h + k + ll) % 2 == 0
    if centring == "F":
        return ((h + k) % 2 == 0) & ((k + ll) % 2 == 0)
    if centring == "A":
        return (k + ll) % 2 == 0
    if centring == "B":
        return (h + ll) % 2 == 0
    if centring == "C":
        return (h + k) % 2 == 0
    if centring == "R":            # obverse setting on hexagonal axes
        return (-h + k + ll) % 3 == 0
    raise ValueError(f"unknown centring {centring!r}")


def trial_hkl(max_index: int, centring: str = "P") -> np.ndarray:
    """Every centring-allowed hkl up to ``max_index``, one per Friedel pair.

    A powder measures |g|, so h and −h are the same line and only one is kept
    (the first non-zero component positive).  Vectorised on purpose: this is both
    the engines' trial set and — through :func:`~rietx.indexing.fom.predicted_lines`
    — the figures of merit's denominator population, and it is evaluated once per
    candidate cell in a ranking loop.
    """
    rng = np.arange(-int(max_index), int(max_index) + 1)
    h, k, ll = np.meshgrid(rng, rng, rng, indexing="ij")
    hkl = np.column_stack([h.ravel(), k.ravel(), ll.ravel()]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    lead = hkl[np.arange(len(hkl)), np.argmax(hkl != 0, axis=1)]
    hkl = hkl[lead > 0]
    return hkl[centring_allows(hkl, centring)]


def gstar_from_af(af: np.ndarray) -> np.ndarray:
    """The symmetric 3×3 reciprocal metric tensor from (A..F)."""
    a = np.asarray(af, dtype=np.float64)
    g = np.zeros((3, 3))
    for p, (i, j) in enumerate(_AF_INDEX):
        v = a[p] / _AF_FACTOR[p]
        g[i, j] = v
        g[j, i] = v
    return g


def af_from_gstar(gstar: np.ndarray) -> np.ndarray:
    g = np.asarray(gstar, dtype=np.float64)
    return np.array([_AF_FACTOR[p] * g[i, j]
                     for p, (i, j) in enumerate(_AF_INDEX)])


def af_from_cell(cell: tuple[float, ...]) -> np.ndarray:
    """(A..F) of a conventional cell — the inverse of :func:`cell_from_af`."""
    from ..crystallography.lattice import reciprocal_metric_tensor
    return af_from_gstar(np.asarray(reciprocal_metric_tensor(*cell)))


def cell_from_af(af: np.ndarray) -> tuple[float, float, float, float, float, float]:
    """(a, b, c, α, β, γ) in Å and degrees from (A..F).

    Raises when the form is not positive definite: a metric with a non-positive
    eigenvalue is not a lattice, and an engine that has wandered there should be
    told rather than handed a NaN cell.  Same posture as the ADP
    positive-definiteness check one rank down (``crystallography/adp.py``).
    """
    gstar = gstar_from_af(af)
    w = np.linalg.eigvalsh(gstar)
    if not np.all(w > 0.0):
        raise ValueError(
            f"(A..F) = {np.asarray(af).tolist()} is not a positive-definite "
            f"reciprocal metric (eigenvalues {w.tolist()}), so it is not a "
            "lattice")
    g = np.linalg.inv(gstar)
    a, b, c = (float(np.sqrt(g[i, i])) for i in range(3))
    alpha = float(np.degrees(np.arccos(np.clip(g[1, 2] / (b * c), -1.0, 1.0))))
    beta = float(np.degrees(np.arccos(np.clip(g[0, 2] / (a * c), -1.0, 1.0))))
    gamma = float(np.degrees(np.arccos(np.clip(g[0, 1] / (a * b), -1.0, 1.0))))
    return a, b, c, alpha, beta, gamma


def cell_jacobian(af: np.ndarray) -> np.ndarray:
    """(6, 6) ∂(a,b,c,α,β,γ)/∂(A..F), analytic — angles in **degrees**.

    Two chains, both exact:

    * ``dG = −G·dG*·G`` (the derivative of a matrix inverse), which turns each
      A..F direction into a full dG;
    * ``a = √G₁₁`` ⇒ ``∂a = dG₁₁/2a``, and ``cos α = G₂₃/(b·c)`` ⇒
      ``∂α = −∂[G₂₃/(bc)]/sin α``, with the b and c derivatives already in hand.

    Finite-differencing this instead would be defensible numerically and is still
    the wrong choice here: the delta-method covariance is used to *decide* whether
    two candidate cells are the same lattice (WP-1020's χ² equality), so its
    accuracy is part of a decision, not of a report.
    """
    gstar = gstar_from_af(af)
    g = np.linalg.inv(gstar)
    a, b, c, alpha, beta, gamma = cell_from_af(af)
    lengths = np.array([a, b, c])
    cos_ang = np.array([g[1, 2] / (b * c), g[0, 2] / (a * c), g[0, 1] / (a * b)])
    sin_ang = np.sqrt(np.maximum(1.0 - cos_ang ** 2, 1e-300))
    # (angle index) → the two length indices and the G component it uses
    pairs = ((1, 2), (0, 2), (0, 1))

    jac = np.zeros((6, 6))
    for p, (i, j) in enumerate(_AF_INDEX):
        # assignment, not accumulation: for a diagonal component i == j and
        # ``+=`` twice would double it (the first three columns of this Jacobian
        # came out exactly 2× before this line was written this way)
        dgstar = np.zeros((3, 3))
        dgstar[i, j] = 1.0 / _AF_FACTOR[p]
        dgstar[j, i] = 1.0 / _AF_FACTOR[p]
        dg = -g @ dgstar @ g
        dlen = np.array([dg[k, k] / (2.0 * lengths[k]) for k in range(3)])
        jac[0:3, p] = dlen
        for q, (m, n) in enumerate(pairs):
            dcos = (dg[m, n] - g[m, n] * (dlen[m] / lengths[m]
                                          + dlen[n] / lengths[n])
                    ) / (lengths[m] * lengths[n])
            jac[3 + q, p] = np.degrees(-dcos / sin_ang[q])
    return jac


def cell_esds(af: np.ndarray, cov_af: np.ndarray) -> np.ndarray:
    """Cell esds from the (A..F) covariance, by the delta method."""
    j = cell_jacobian(af)
    cov_cell = j @ np.asarray(cov_af, dtype=np.float64) @ j.T
    return np.sqrt(np.maximum(np.diag(cov_cell), 0.0))


@lru_cache(maxsize=None)
def _metric_basis_cached(system: str) -> np.ndarray:
    """The uncached derivation, memoised — see :func:`metric_basis`.

    Memoised because a search calls ``refine_candidate`` once per accepted box
    and each call re-derives the subspace: measured on an orthorhombic search,
    the exact-rational nullspace was 2.5 s of a 15 s run, for seven possible
    answers.  The array is returned read-only so a cached value cannot be mutated
    by a caller.
    """
    import gemmi

    if system not in _HOLOHEDRY:
        raise ValueError(f"unknown crystal system {system!r}; expected one of "
                         f"{sorted(_HOLOHEDRY)}")
    sg = gemmi.find_spacegroup_by_name(_HOLOHEDRY[system])
    rots = [np.array(op.rot, dtype=np.int64) // gemmi.Op.DEN
            for op in sg.operations()]
    basis_voigt = adp_basis(rots)
    out = np.zeros((basis_voigt.shape[0], 6))
    for p in range(6):
        out[:, p] = _AF_FACTOR[p] * basis_voigt[:, _VOIGT_OF_AF[p]]
    out.setflags(write=False)
    return out


def metric_basis(system: str) -> np.ndarray:
    """(m, 6) basis of the A..F directions a ``system`` allows.

    Derived from the holohedry's rotations by exact rational algebra —
    ``adp_basis``, the same integer nullspace the anisotropic-ADP basis uses —
    then converted from Voigt order to A..F order (:data:`_AF_INDEX`).  ``m``
    equals :data:`~rietx.schemas.indexing.METRIC_DOF`, and a test asserts that
    against the cell ties ``params.vector`` has used since v0.1.

    **The rotations go in untransposed, and getting that wrong is invisible in the
    dimension.**  CLAUDE.md's rule that the reciprocal-space symmetry action is
    Rᵀ is about **hkl**: h → Rᵀh.  A tensor that contracts with h *twice* is
    therefore invariant under U → R·U·Rᵀ — the two statements are the same one,
    since (Rᵀh)ᵀ U (Rᵀh) = hᵀ (R U Rᵀ) h — and G\\* is such a tensor, exactly like
    the U\\* form of an ADP.  Passing the transposed operators here instead returns
    the invariants of the **direct** metric G: same dimension in every system (the
    transposed set is a group too), so a degrees-of-freedom test passes happily,
    but the wrong subspace wherever R is not symmetric.  Measured while writing
    this: the hexagonal basis came out with F = −A, which is the direct metric's
    cos γ = −1/2, where the reciprocal one has F = +A.  Only a test asserting that
    the *true* metric lies in the span catches it — ``tests/test_indexing_core.py``
    has one.
    """
    return _metric_basis_cached(system)


@dataclass
class CandidateFit:
    """One weighted solve of A..F against assigned lines.

    ``chi2_red`` is on the **Q** residual in units of σ_eff, so it is directly a
    statement about whether the lattice explains the positions to within their
    own precision: ≈1 means it does, ≫1 means it does not and no figure of merit
    should be believed over it.
    """

    af: np.ndarray
    cov_af: np.ndarray
    cell: tuple[float, float, float, float, float, float]
    cell_esd: np.ndarray
    system: str
    n_lines: int
    chi2_red: float
    residual_q: np.ndarray
    shift_template: str | None = None
    shift_coefficient: float = 0.0
    shift_esd: float = 0.0

    @property
    def volume(self) -> float:
        from ..crystallography.lattice import cell_volume
        return float(cell_volume(*self.cell))


def sigma_effective(q_esd: np.ndarray, two_theta: np.ndarray, wavelength: float,
                    allowance_deg: float = 0.0) -> np.ndarray:
    """Per-line σ(Q) with a systematic floor added **in quadrature**.

    What the engines feed in is the shift **allowance** — the amplitude a
    window must span (``effective_shift_allowance``), never the residual
    scatter a template leaves; the two differ 4.3× on SRM 660c and this
    parameter carried the scatter's name until WP-1045.  It is a degrees-2θ
    quantity, so it is propagated into Q by the same exact derivative σ(Q) uses
    and only then combined.  Combining in 2θ and propagating afterwards would give
    the same answer here; doing it in Q keeps one propagation function in the
    package (``schemas.indexing.q_esd_of_two_theta``) rather than two.
    """
    from ..schemas.indexing import q_esd_of_two_theta
    base = np.asarray(q_esd, dtype=np.float64)
    if allowance_deg <= 0.0:
        return base
    extra = q_esd_of_two_theta(two_theta, np.full_like(base, allowance_deg),
                              wavelength)
    return np.sqrt(base ** 2 + extra ** 2)


def refine_candidate(q: np.ndarray, q_esd: np.ndarray, hkl: np.ndarray, *,
                     system: str = "triclinic",
                     two_theta: np.ndarray | None = None,
                     wavelength: float | None = None,
                     shift_template: str | None = None,
                     max_iter: int = 8) -> CandidateFit:
    """Fit A..F (and optionally one shift coefficient) to assigned lines.

    Without a shift this is **one weighted linear solve** — the inner loop of
    every engine, so it stays a single ``lstsq`` on an (N, m) system with no
    iteration and no scipy call.  With a shift it is Gauss-Newton on the same
    system plus one column, and the only nonlinearity is that the *corrected*
    positions move: 2θ_corr = 2θ_obs − s·t(θ), whose Q-derivative is

        ∂Q/∂s = −(π/90)·sin(2θ_corr)/λ² · t(θ)

    Note the **π/90**, not π/180: differentiating Q = 4sin²θ/λ² with respect to
    2θ in *degrees* picks up the θ = (2θ)/2 chain and the degree conversion, and
    only one of the two is the classic slip (WP-1018 found this WP's plan text
    carrying the π/180 form).
    """
    basis = metric_basis(system)
    m = design_matrix(hkl) @ basis.T
    qv = np.asarray(q, dtype=np.float64)
    sig = np.asarray(q_esd, dtype=np.float64)
    if not (len(qv) == len(sig) == m.shape[0]):
        raise ValueError("q, q_esd and hkl must have the same length")
    if len(qv) < basis.shape[0]:
        raise ValueError(
            f"{len(qv)} lines cannot determine {basis.shape[0]} metric "
            f"parameters for a {system} cell")
    w = 1.0 / np.maximum(sig, 1e-300)

    shift = 0.0
    if shift_template is None:
        jac = m * w[:, None]
        theta, *_ = np.linalg.lstsq(jac, qv * w, rcond=None)
        resid_w = qv * w - jac @ theta
    else:
        if two_theta is None or wavelength is None:
            raise ValueError("a shift template needs two_theta and wavelength")
        from .quality import shift_template_basis
        tt = np.asarray(two_theta, dtype=np.float64)
        tmpl = shift_template_basis(tt)[shift_template]
        theta = np.zeros(basis.shape[0])
        for _ in range(max_iter):
            corrected = tt - shift * tmpl
            resid_w = (q_of_two_theta(corrected, wavelength) - m @ theta) * w
            # Gauss-Newton on r = (Q(2θ − s·t) − Mθ)·w.  ∂r/∂θ = −M·w and
            # ∂r/∂s = −(π/90)·sin(2θ_corr)/λ²·t·w, so the step solves
            # [+M·w, −∂r/∂s]·Δ = r — **both** signs flipped together.  Flipping
            # only the θ block (which looks right, because +M·w·Δθ = r is the
            # correct linear solve on its own) leaves the shift column with the
            # wrong relative sign and s runs away: measured, −11.65 for an
            # injected +0.05.
            dq_dtt = (np.pi / 90.0) * np.sin(np.radians(corrected)) \
                / wavelength ** 2
            jac = np.column_stack([m * w[:, None], dq_dtt * tmpl * w])
            step, *_ = np.linalg.lstsq(jac, resid_w, rcond=None)
            theta = theta + step[:-1]
            shift += float(step[-1])
            if np.max(np.abs(step)) <= 1e-14 * (1.0 + np.max(np.abs(theta))):
                break
        corrected = tt - shift * tmpl
        resid_w = (q_of_two_theta(corrected, wavelength) - m @ theta) * w

    af = basis.T @ theta
    # The metric is checked before the covariance is formed.  A direction no
    # line constrains leaves its A..F term at zero and its variance infinite,
    # and the propagation below meets that infinity as 0·inf, which OpenBLAS
    # reports and Accelerate does not (WP-1545: 15 rejected fits warned on
    # Linux in one search).  Such a metric is no lattice, so it raises here.
    cell = cell_from_af(af)
    cov, chi2_red = _covariance(jac, resid_w)
    n_free = basis.shape[0]
    # "at zero" is not exact: the solve can leave such a term at ±1e-17, and
    # when the sign is + the metric is positive definite and passes the check
    # above (measured on h0l-only assignments of a monoclinic cell).  The
    # infinite variance is the direct test, so it is asked here as well; let
    # through, it gave the candidate NaN esds, which reached spglib as symprec.
    if not np.all(np.isfinite(np.diag(cov)[:n_free])):
        raise ValueError(
            f"no assigned line constrains every metric direction of this "
            f"{system} fit (A..F = {af.tolist()}), so it is not a lattice")
    cov_af = basis.T @ cov[:n_free, :n_free] @ basis
    return CandidateFit(
        af=af, cov_af=cov_af, cell=cell,
        cell_esd=cell_esds(af, cov_af), system=system, n_lines=len(qv),
        chi2_red=chi2_red, residual_q=resid_w / w,
        shift_template=shift_template, shift_coefficient=shift,
        shift_esd=(float(np.sqrt(max(cov[-1, -1], 0.0)))
                   if shift_template is not None else 0.0))


def _covariance(jac_w: np.ndarray, resid_w: np.ndarray):
    """χ²_red·pinv(MᵀWM) — the same estimator the refinement side uses.

    Routed through ``optimize.statistics.normal_covariance`` so the two surfaces
    cannot disagree about pinv guarding or about the χ² floor (which is applied:
    a lattice that does not explain the positions must not report tight esds).
    """
    from ..optimize.statistics import normal_covariance
    cov, chi2_red = normal_covariance(
        jac_w, resid_w, jac_w.shape[1], chi2_floor=True,
        what="candidate-cell Q residual entering the covariance solve")
    return cov, chi2_red


__all__ = ["CandidateFit", "af_from_cell", "af_from_gstar", "cell_esds",
           "cell_from_af", "cell_jacobian", "design_matrix", "gstar_from_af",
           "metric_basis", "refine_candidate", "sigma_effective",
           "METRIC_DOF"]
