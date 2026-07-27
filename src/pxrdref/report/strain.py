"""Layer-1 anisotropic-strain (Stephens) width diagnostic.

Per-region shape attribution (:mod:`.layer1`) sees *where* the widths are wrong,
and :func:`.layer1.analyse_trends` sees whether the width error follows 1/cosθ
(size) or tanθ (strain).  Neither can see the case this module is for: a width
error that is not a function of 2θ at all, but of **direction** — (00l) sharp
and (hk0) broad at the same angle.  That is the signature Stephens' model
(:mod:`pxrdref.crystallography.stephens`) exists to fit, and the question here
is the one that has to be answered *before* someone adds fifteen parameters:

    are this specimen's widths directional, and by how much?

Note the subject: the **specimen**, not the residual.  Refining a microstrain
block does not silence this diagnostic, it makes the two agree — which is the
cross-check that makes either believable, since they arrive at the number by
completely different routes.  Not re-suggesting an action whose parameters are
already free is the Layer-2 strategy veto's job.

Method
------
1. **Extract a per-reflection strain coefficient** (:func:`_strain_errors`) by
   damped Gauss-Newton on the residual, with two unknowns per reflection — an
   amplitude factor and Λ itself.  Solved jointly across reflections (peaks
   overlap), with the amplitude free (a peak that is simply too tall otherwise
   reads as a width error), against Λ rather than the combined width (a
   strained peak is broader *and* more Lorentzian), and iterated (Ω is
   strongly nonlinear in the widths, and the errors this looks for are a factor
   of two, not a few per cent).  Each of those three is load-bearing: measured
   on the injection test, dropping any one of them biases the recovered
   broad/narrow ratio by tens of per cent.
2. **Fit the Laue-allowed patterns.**  Λ² is *linear* in the S_HKL, so with
   T_kj = (basis row j)·(monomials of reflection k),

       Λ_k² / (C²·d_k⁴)  ≈  Σ_j θ_j T_kj,     C = (180/π)·10⁻⁶

   is an ordinary weighted least-squares problem — no grid search, unlike the
   nonlinear March-Dollase scan in :mod:`.texture`.

Score
-----
``r2`` is measured against the **isotropic-only** fit (the single M² column,
which is exactly what ``lor_strain`` already models), so it reads as "how much
of the width variation is *directional*, over and above anything an isotropic
strain could do".  A specimen whose widths are fine, or wrong but isotropically
wrong, scores ~0.

``separable`` follows the Layer-1 rule that a collinear basis must be reported
non-separable rather than resolved into a confident singleton: the individual
S_HKL patterns are declared unresolved when the scale-normalised Gram of T over
the *sampled* reflections is ill-conditioned.  The headline ``r2`` and
``anisotropy`` survive that — "the widths are directional by 3×" is robust even
when "which patterns" is not.

Like :mod:`.texture`, this runs independently of the maturity gate: strong
uncorrected anisotropic broadening is a common *cause* of an immature fit, so
the diagnostic must still speak when Layer 1 otherwise abstains.  It reports;
acting on it (declaring a ``microstrain`` block) is the strategy engine's call.

Reference: Stephens (1999) J. Appl. Cryst. 32, 281.
"""

from __future__ import annotations

import numpy as np

from ..crystallography.lattice import d_spacings
from ..crystallography.stephens import monomial_matrix, stephens_basis
from ..model.forward import CompiledModel
from .schemas import (
    STRAIN_MAX_GRAM_CONDITION,
    STRAIN_MIN_ANISOTROPY,
    STRAIN_MIN_R2,
    STRAIN_MIN_REFLECTIONS,
    StrainAnalysis,
)

#: (180/π)·10⁻⁶ — the constant of ``stephens.strain_width_deg``, needed here to
#: undo it and get back to σ²(M)
_C = np.degrees(1.0) * 1e-6

#: leverage share below which a reflection informs the fit but is not allowed
#: to *name* the broadest or narrowest direction (see ``analyse_strain``)
_QUOTABLE_WEIGHT_FRAC = 0.01

#: Gauss-Newton steps in the per-reflection strain extraction.  One step is a
#: plain linearisation and demonstrably biased on the width errors this looks
#: for; four converge on the injection test.  See :func:`_strain_errors`.
_GAUSS_NEWTON_ITERATIONS = 4


def _components(model: CompiledModel, values: dict[str, float], ip: int
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(d, Γ_G, Γ_L, tanθ, current total strain coefficient) for phase ``ip``.

    The three width arrays are per **(emission line, reflection)**: the Kα2
    satellite of a reflection sits at its own Bragg angle, so it has its own
    Γ_G, Γ_L and tanθ even though the strain coefficient it carries is the same
    number.  That is exactly why the unknown fitted below is the strain
    coefficient and not a width — one unknown, consistently applied to every
    line.  Recomputed here rather than read off ``phase_peaks``, which returns
    only the *combined* pair.
    """
    from ..model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm

    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = np.asarray(d_spacings(cp.reflections.hkl, *cell), dtype=np.float64)
    aniso = np.asarray(model.strain_width(ip, values, d)) \
        if cp.strain_monomials is not None else np.zeros(len(d))
    # the whole tanθ coefficient, isotropic part included: a Stephens block
    # *subsumes* lor_strain (its isotropic direction is the same column, which
    # is why declaring one locks it), so the quantity to fit and to report the
    # anisotropy of is the total, not the anisotropic remainder.  Fitting the
    # remainder alone would call a specimen infinitely anisotropic the moment
    # lor_strain had absorbed the narrow direction entirely.
    strain_total = aniso + values[f"phases.{ip}.lor_strain"]
    gam_g, gam_l, tan_theta = [], [], []
    for lam in model.line_wavelengths:
        with np.errstate(invalid="ignore"):
            theta = np.degrees(np.arcsin(np.clip(lam / (2.0 * d), -1.0, 1.0)))
        gam_g.append(np.asarray(gaussian_fwhm(
            theta, values["instrument.profile.u"], values["instrument.profile.v"],
            values["instrument.profile.w"], values[f"phases.{ip}.gauss_size"],
            values[f"phases.{ip}.gauss_strain"])))
        gam_l.append(np.asarray(lorentzian_fwhm(
            theta, values["instrument.profile.x"] + values[f"phases.{ip}.lor_size"],
            values["instrument.profile.y"] + values[f"phases.{ip}.lor_strain"], aniso)))
        tan_theta.append(np.tan(np.radians(theta)))
    return d, np.array(gam_g), np.array(gam_l), np.array(tan_theta), strain_total


def _degenerate_groups(d: np.ndarray, rtol: float = 1e-9) -> np.ndarray:
    """Group index per reflection: reflections sharing a d-spacing are one.

    In a trigonal Laue class (h,k,l) and (h,k,-l) can be inequivalent yet
    coincide exactly, which makes their profile columns literally identical.
    Their widths are one unknown, not two — solving them separately leaves the
    system singular in a direction the Gauss-Newton iteration then walks along
    (measured: a reflection oscillating between 0.004 and 0.117° per step).
    """
    order = np.argsort(-d)
    group = np.empty(len(d), dtype=np.int64)
    n_group = 0
    last = None
    for i in order:
        if last is not None and abs(d[i] - d[last]) <= rtol * d[last]:
            group[i] = n_group - 1
        else:
            group[i] = n_group
            n_group += 1
            last = i
    return group


def _strain_errors(model: CompiledModel, values: dict[str, float], ip: int,
                   n_iter: int = _GAUSS_NEWTON_ITERATIONS
                   ) -> tuple[np.ndarray, np.ndarray]:
    """(ΔΛ, weight) per reflection of phase ``ip``, by damped Gauss-Newton.

    Each iteration rebuilds the pattern at the current per-group (strain,
    amplitude) corrections and solves the residual jointly against every
    group's own pair of columns — I_k·Ω_k and I_k·∂Ω_k/∂Λ.  Jointly, because
    overlapped peaks share points and a per-reflection dot product would hand
    each of them the other's misfit; and *with* the amplitude columns, because
    a peak that is simply too tall reads as a width error to any basis that
    lacks them (the non-orthogonality argument Layer 1 makes for its five
    regional columns, one level down).

    Two details do the real work:

    * The unknown is **Λ, not Γ.**  Perturbing the combined width alone holds
      the mixing η fixed, but a genuinely more-strained peak is both broader
      *and* more Lorentzian; a fixed-η basis can only match it by overshooting
      the width.  Feeding the perturbation through the model's own
      ``_peak_widths`` moves both slots together, the way the physics does.
    * It **iterates.**  Ω is strongly nonlinear in the widths, and the errors
      this diagnostic exists to find are large — a factor of two, not a few per
      cent.  Reporting a single linear step would be exactly the
      confident-but-wrong number the FitReport is not allowed to produce.

    ``weight`` is the group's width-column squared norm, shared out over its
    members — the leverage that reflection has on the residual, which is what
    the downstream fit should trust in proportion to.
    """
    cp = model.phases[ip]
    sl = values["instrument.geometry.axial_sl"]
    hl = values["instrument.geometry.axial_hl"]
    peaks = model.phase_peaks(ip, values)
    _d, gam_g, gam_l, tan_theta, _tot = _components(model, values, ip)
    n = len(cp.reflections)
    npts = len(model.tt)
    sw = 1.0 / model.sigma
    group = _degenerate_groups(np.asarray(cp.reflections.d, dtype=np.float64))
    n_group = int(group.max()) + 1 if n else 0
    # everything this phase does not own stays fixed: background, other phases
    y_other = model.evaluate(values) - model.phase_component(ip, values)

    d_lambda = np.zeros(n_group)
    amp_factor = np.ones(n_group)   # multiplicative: each step scales the current
    weight = np.zeros(n_group)
    h_lambda = 1e-6
    for _ in range(max(n_iter, 1)):
        y = y_other.copy()
        col_a = np.zeros((npts, n_group))
        col_w = np.zeros((npts, n_group))
        for il, (pos, _g, _e, intensity) in enumerate(peaks):
            for k in range(n):
                i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                if i1 <= i0 or not np.isfinite(pos[k]) or intensity[k] == 0.0:
                    continue
                g = group[k]
                gl = max(gam_l[il, k] + d_lambda[g] * tan_theta[il, k], 0.0)
                amp = float(intensity[k]) * amp_factor[g]
                w1, w2 = model._peak_widths(gam_g[il, k], gl)
                prof = model._reflection_profile(cp, il, k, pos[k], w1, w2, sl, hl)
                # ∂Ω/∂Λ by forward difference of the model's own profile: the
                # FCJ smear, the width combination and the shape dispatch all
                # come along, which a re-derivation here would have to
                # duplicate and could drift from
                w1h, w2h = model._peak_widths(
                    gam_g[il, k], gl + h_lambda * tan_theta[il, k])
                dp = (model._reflection_profile(cp, il, k, pos[k], w1h, w2h, sl, hl)
                      - prof) / h_lambda
                y[i0:i1] += amp * prof
                col_a[i0:i1, g] += (amp * sw[i0:i1]) * prof
                col_w[i0:i1, g] += (amp * sw[i0:i1]) * dp
        weight = (col_w * col_w).sum(axis=0)
        live = weight > 0.0
        if not live.any():
            return np.zeros(n), np.zeros(n)
        delta = (model.y_obs - y) * sw
        design = np.hstack([col_a[:, live], col_w[:, live]])
        # rcond, not the machine-precision default: peaks that merely *overlap*
        # strongly leave near-collinear columns whose split the data does not
        # determine; truncating those singular values spreads the correction
        # over the group instead of letting the iteration walk along them
        step, *_ = np.linalg.lstsq(design, delta, rcond=1e-6)
        n_live = int(live.sum())
        amp_factor[live] *= 1.0 + np.clip(step[:n_live], -0.5, 0.5)
        d_lambda[live] += step[n_live:]
    counts = np.bincount(group, minlength=n_group)
    return d_lambda[group], weight[group] / counts[group]


def _fit(templates: np.ndarray, y: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float]:
    """Weighted least squares of ``y`` on ``templates``; returns (θ, residual SS)."""
    sw = np.sqrt(w)[:, None]
    coef, *_ = np.linalg.lstsq(templates * sw, y * np.sqrt(w), rcond=None)
    resid = (templates @ coef - y) * np.sqrt(w)
    return coef, float(resid @ resid)


def analyse_strain(model: CompiledModel, values: dict[str, float], *,
                   min_weight_frac: float = 1e-3) -> list[StrainAnalysis]:
    """Detect directional (Stephens) width misfit, one result per phase.

    Runs whether or not the phase already carries a ``microstrain`` block: with
    one, the question becomes "is there anisotropy *left*", which is how the
    result gets checked after refining it.  Rietveld mode only — Le Bail and
    Pawley widths are shared with empirical intensities, so a width error there
    is not separable from an intensity one.
    """
    if model.mode != "rietveld":
        return []
    out: list[StrainAnalysis] = []
    for ip, cp in enumerate(model.phases):
        d_lambda, weight = _strain_errors(model, values, ip)
        d, _gam_g, _gam_l, tan_theta, current = _components(model, values, ip)
        live = (weight > min_weight_frac * max(weight.max(initial=0.0), 1e-300)) \
            & np.isfinite(tan_theta[0]) & (tan_theta[0] > 0.0)
        n_used = int(live.sum())
        basis = stephens_basis(cp.reflections.spacegroup).astype(np.float64)
        if n_used < max(STRAIN_MIN_REFLECTIONS, len(basis) + 1):
            out.append(StrainAnalysis(phase_index=ip, n_reflections_used=n_used))
            continue

        # required strain coefficient per reflection.  A negative one is
        # unreachable (Λ ≥ 0) and is clipped — "this peak wants to be narrower
        # than a zero-strain model" is a statement about the *instrument*
        # width, not about anisotropy.
        target = np.maximum(current + d_lambda, 0.0)

        mono = monomial_matrix(cp.reflections.hkl)
        templates = (mono @ basis.T)[live]
        scale = (_C * d[live] ** 2) ** 2          # y = Λ²/scale
        y = target[live] ** 2 / scale
        # Weight in **Λ** space, propagated: the fit is linear in σ²(M), but σ²
        # spans three orders of magnitude across a powder pattern (it carries a
        # 1/d⁴), so least squares on it alone is decided entirely by the
        # high-angle reflections and returns negative — unphysical — variances
        # for the low-index ones.  Dividing by (∂y/∂Λ)² makes the solve a
        # weighted least squares in the width itself, which is the quantity the
        # residual actually measured.
        floor = 1e-3 * max(float(np.median(target[live])), 1e-12)
        w = weight[live] * (scale / (2.0 * np.maximum(target[live], floor))) ** 2

        # the isotropic baseline: one column, the M² = 1/d⁴ ray — exactly what
        # lor_strain already spans.  R² against it is the directional content.
        _, ss_iso = _fit((1.0 / d[live] ** 4)[:, None], y, w)
        coef, ss_full = _fit(templates, y, w)
        r2 = float(1.0 - ss_full / ss_iso) if ss_iso > 0 else 0.0

        # The headline ratio is quoted only over reflections that carry real
        # leverage.  The fit is informed by every live reflection, but naming a
        # direction — and dividing by its width — on the strength of a weak
        # high-angle peak is how a diagnostic ends up overstating: the model
        # extrapolates freely where nothing holds it down.
        fitted = np.sqrt(np.maximum(templates @ coef, 0.0) * scale)
        lev = weight[live]
        strong = lev > _QUOTABLE_WEIGHT_FRAC * lev.max()
        idx = np.nonzero(strong)[0] if strong.any() else np.arange(len(fitted))
        hi_i = idx[int(np.argmax(fitted[idx]))]
        lo_i = idx[int(np.argmin(fitted[idx]))]
        lo, hi = float(fitted[lo_i]), float(fitted[hi_i])
        anisotropy = hi / lo if lo > 0 else float("inf")
        hkl_live = cp.reflections.hkl[live]

        norm = templates / np.maximum(np.linalg.norm(templates, axis=0), 1e-300)
        cond = float(np.linalg.cond(norm.T @ norm)) if len(basis) > 1 else 1.0
        detected = (r2 >= STRAIN_MIN_R2 and anisotropy >= STRAIN_MIN_ANISOTROPY
                    and n_used >= STRAIN_MIN_REFLECTIONS)
        out.append(StrainAnalysis(
            phase_index=ip, n_reflections_used=n_used, r2=max(r2, 0.0),
            anisotropy=min(anisotropy, 1e6),
            broadest_hkl=tuple(int(v) for v in hkl_live[hi_i]),
            narrowest_hkl=tuple(int(v) for v in hkl_live[lo_i]),
            n_patterns=len(basis), gram_condition=cond,
            separable=bool(cond <= STRAIN_MAX_GRAM_CONDITION),
            detected=detected,
        ))
    return out
