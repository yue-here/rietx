"""Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67-70.

    R_p   = Σ|y_o − y_c| / Σ y_o
    R_wp  = √[ Σ w (y_o − y_c)² / Σ w y_o² ]
    R_exp = √[ (N − P) / Σ w y_o² ]
    χ²    = Σ w (y_o − y_c)² / (N − P)        (reduced)
    GoF   = √χ² = R_wp / R_exp

``rwp_background_subtracted`` recomputes R_wp with the background removed from
both numerator-model and denominator-observed, the variant Toby recommends
when the background carries much of the raw intensity.  The Durbin-Watson
statistic d = Σ(Δᵢ−Δᵢ₋₁)²/ΣΔᵢ² on weighted residuals (Hill & Flack, 1987,
J. Appl. Cryst. 20, 356) flags serial correlation (d ≈ 2 ⇒ uncorrelated).

When residuals *are* serially correlated the χ²·(JᵀJ)⁻¹ esds are too small:
neighbouring points do not carry independent information.  Bérar & Lelann
(1991, J. Appl. Cryst. 24, 1) sum consecutive same-sign weighted residuals
coherently, χ²' = Σ_runs (Σ_{i∈run} δᵢ)² ≥ χ², and multiply every esd by
√(χ²'/χ²) — the inflation factor reported here and applied to the esds.
"""

from __future__ import annotations

import numpy as np

from ..schemas.results import Statistics


def berar_lelann_factor(delta: np.ndarray) -> float:
    """Esd inflation factor for serial correlation.

    Bérar & Lelann (1991), J. Appl. Cryst. 24, 1: runs of consecutive
    weighted residuals δᵢ = √wᵢ·Δᵢ sharing a sign are summed coherently,

        χ²' = Σ_runs (Σ_{i∈run} δᵢ)²

    and esds are multiplied by √(χ²'/χ²).  Same-sign cross terms are
    positive, so the factor is always ≥ 1.

    Caveat (documented, not hidden): the estimator is *conservative*.  Even
    iid Gaussian residuals form chance runs (geometric length distribution,
    mean 2), giving E[χ²']/χ² = 1 + 4/π, i.e. an expected factor ≈ 1.51 for
    perfectly white residuals — verified against simulation in the tests.
    Treat the factor as an upper bound on the serial-correlation esd damage;
    Andreev (1994, J. Appl. Cryst. 27, 288) develops a figure of merit that
    removes this bias.  The raw published factor is what FullProf applies,
    and it is reported in ``Statistics.esd_inflation`` so it can be divided
    back out.
    """
    d = np.asarray(delta, dtype=np.float64)
    if len(d) < 2:
        return 1.0
    chi2 = float(d @ d)
    if chi2 <= 0.0:
        return 1.0
    sign = np.sign(d)
    change = np.nonzero(sign[1:] != sign[:-1])[0] + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change, [len(d)]])
    cs = np.concatenate([[0.0], np.cumsum(d)])
    run_sums = cs[ends] - cs[starts]
    return max(float(np.sqrt((run_sums @ run_sums) / chi2)), 1.0)


def background_absorption(jac: np.ndarray, free_paths: list[str]) -> dict[str, float]:
    """How much of each structural parameter the background could reproduce.

    For parameter i with Jacobian column jᵢ and the background columns
    spanning B, the multiple correlation

        R²ᵢ = 1 − ‖jᵢ − P_B jᵢ‖² / ‖jᵢ‖²          (P_B = orthogonal projector)

    is the fraction of jᵢ's effect the background can imitate.  R² → 1 means
    the two are degenerate: the background absorbs Bragg intensity, biasing
    ADPs up and scales (hence QPA fractions) down *while Rwp improves* — the
    documented failure mode of over-flexible backgrounds.  Anisotropic ADP
    DOFs (``…adp.k``) are screened alongside Biso: more displacement freedom
    means more of it available to soak up a background error.

    Pairwise ρ is the wrong statistic for this: with ~100 spline coefficients
    each individual |ρ| stays small (~0.2) while the block collectively
    absorbs ~50 % of the parameter (measured).  The projection sees the block.

    ``jac`` must be the **full** Jacobian including any P-spline penalty rows
    — those rows are what makes a stiff background unable to imitate a peak,
    and dropping them overstates the risk by ~5× (measured: R² 0.46 → 0.08 at
    λ = 10⁴).
    """
    bg = [k for k, p in enumerate(free_paths) if p.startswith("instrument.background.")]
    targets = [(k, p) for k, p in enumerate(free_paths)
               if p.endswith((".biso", ".scale", ".occ")) or ".adp." in p]
    return block_projection_r2(jac, bg, targets)


def block_projection_r2(jac: np.ndarray, block: list[int],
                        targets: list[tuple[int, str]],
                        nuisance: list[int] | None = None) -> dict[str, float]:
    """R²ᵢ of each target column on the span of ``block``, keyed by path.

    The shared core of :func:`background_absorption` and
    :func:`roughness_absorption`: a thin QR of the block gives an orthonormal
    basis, and each target column is projected onto it.  Extracted rather than
    copied because the *statistic* is the reusable idea — "can this group of
    parameters, acting together, imitate that one?" — and a second hand-rolled
    copy would be free to drift from this one's clipping and degenerate-column
    handling.

    ``nuisance`` columns, when given, are projected out of the **whole**
    Jacobian first, making the result a *partial* R²: how much of the target
    the block can still explain once those parameters have taken whatever they
    can.  That matters whenever the nuisance directions are free anyway, and it
    is what makes the roughness number mean something (see
    :func:`roughness_absorption`).

    ``block``, ``nuisance`` and the indices in ``targets`` index columns of
    ``jac``.  A zero-norm target column is skipped rather than reported as 0 or
    1: it carries no information either way.
    """
    if not block or not targets:
        return {}
    jac = np.asarray(jac)
    if nuisance:
        qn, _ = np.linalg.qr(jac[:, nuisance])
        jac = jac - qn @ (qn.T @ jac)
    q, _ = np.linalg.qr(jac[:, block])
    out: dict[str, float] = {}
    for k, path in targets:
        j = jac[:, k]
        denom = float(j @ j)
        if denom <= 0.0:
            continue
        resid = j - q @ (q.T @ j)
        out[path] = float(np.clip(1.0 - float(resid @ resid) / denom, 0.0, 1.0))
    return out


def _displacement_like(path: str) -> bool:
    """Displacement freedom a low-angle intensity depression can hide in."""
    return path.endswith(".biso") or ".adp." in path


def _roughness_nuisance(path: str) -> bool:
    """Directions that are free anyway and would swamp the comparison.

    Roughness is a *multiplicative* correction, so it is trivially "scale-like":
    projected onto a block containing the phase scale it scores R² ≈ 0.95
    whatever the data (measured), which says nothing except that both rescale
    the pattern.  The scale and the background refine in every plan regardless,
    so the question worth asking is what is left of roughness *after* they have
    taken whatever they can — a partial R².
    """
    return path.endswith(".scale") or path.startswith("instrument.background.")


def roughness_absorption(jac: np.ndarray, free_paths: list[str]
                         ) -> dict[str, float]:
    """Two-way degeneracy between surface roughness and the ADPs (WP-0502).

    Surface roughness depresses low-angle intensity, which is exactly the
    signature an inflated Biso/ADP can reproduce.  Pitschke, Hermann & Mattern
    (1993) Table III is the canonical demonstration of the consequence:
    uncorrected, YBa₂Cu₃O₇ refines to Biso = −1.9 … −2.5 Å², and only the
    correction brings it back to 0.28–0.45 Å².  The degeneracy is real physics,
    so the answer is to *measure* it, not to hide it behind a good-looking Rwp.

    The phase scale and the background are treated as **nuisance** directions
    and projected out of everything first (see :func:`_roughness_nuisance`);
    without that step every number here saturates near 0.96 and the guard is
    blind.  Both remaining directions are reported, because they answer
    different questions:

    * ``instrument.geometry.surface_roughness.*`` keys — how much of the
      roughness column the displacement block can still reproduce.  High ⇒
      *roughness is not identifiable from this data* and whatever it refined to
      is arbitrary.
    * ``…biso`` / ``…adp.k`` keys — how much of that parameter the roughness
      block can reproduce.  High ⇒ *the displacement parameter is hiding in
      roughness*, so its esd understates its true uncertainty.

    Measured on a synthetic large-cell lab pattern with scale, background, both
    Biso and both Suortti parameters free, varying only the low-angle cutoff:

    ======================  =====  =====  =====  =====  =====
    lowest fitted 2θ          7°    15°    20°    30°    45°
    reflections below 40°     20     18     16     10      0
    R²(roughness b)         0.06   0.62   0.91   0.93   0.95
    ======================  =====  =====  =====  =====  =====

    i.e. the statistic tracks the thing that actually determines
    identifiability — how many *reflections* fall in the range where the
    depression has a lever arm — rather than the nominal 2θ limit.

    As for :func:`background_absorption`, pairwise ρ is the wrong statistic (a
    block of many coefficients absorbs collectively while every individual |ρ|
    stays small) and ``jac`` must be the **full** Jacobian including any
    P-spline penalty rows.
    """
    rough = [k for k, p in enumerate(free_paths)
             if p.startswith("instrument.geometry.surface_roughness.")]
    disp = [(k, p) for k, p in enumerate(free_paths) if _displacement_like(p)]
    if not rough or not disp:
        return {}
    nuisance = [k for k, p in enumerate(free_paths) if _roughness_nuisance(p)]
    out = block_projection_r2(jac, [k for k, _ in disp],
                              [(k, free_paths[k]) for k in rough], nuisance)
    out.update(block_projection_r2(jac, rough, disp, nuisance))
    return out


def compute_statistics(y_obs: np.ndarray, y_calc: np.ndarray, sigma: np.ndarray,
                       n_free: int, y_background: np.ndarray | None = None) -> Statistics:
    y_obs = np.asarray(y_obs, dtype=np.float64)
    y_calc = np.asarray(y_calc, dtype=np.float64)
    w = 1.0 / np.asarray(sigma, dtype=np.float64) ** 2
    n = len(y_obs)
    diff = y_obs - y_calc

    swyo2 = float(w @ (y_obs * y_obs))
    swd2 = float(w @ (diff * diff))
    rp = float(np.abs(diff).sum() / np.abs(y_obs).sum())
    rwp = float(np.sqrt(swd2 / swyo2))
    rexp = float(np.sqrt(max(n - n_free, 1) / swyo2))
    chi2 = swd2 / max(n - n_free, 1)

    rwp_bs = None
    if y_background is not None:
        net = y_obs - y_background
        denom = float(w @ (net * net))
        if denom > 0:
            rwp_bs = float(np.sqrt(swd2 / denom))

    delta = np.sqrt(w) * diff
    dw = float(np.sum(np.diff(delta) ** 2) / np.sum(delta ** 2)) if n > 2 else None

    return Statistics(
        rwp=rwp, rp=rp, rexp=rexp, chi2=chi2, gof=rwp / rexp,
        rwp_background_subtracted=rwp_bs, durbin_watson=dw,
        esd_inflation=berar_lelann_factor(delta) if n > 2 else None,
        n_points=n, n_free_parameters=n_free,
    )
