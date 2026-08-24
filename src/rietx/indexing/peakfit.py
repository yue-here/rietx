"""Per-group profile fitting — where a line's σ(2θ) actually comes from.

Each detected group is fitted alone on its frozen window by
``scipy.optimize.least_squares(method="trf")``.  Deliberately **not**
``run_least_squares``: its signature is ``(model: CompiledModel, table:
ParameterTable, …)`` and ``compile_model`` needs a structure with a space group,
a cell and an enumerated reflection list — i.e. the answer indexing is about to
produce.  Peak parameters also have no dot-paths and must never enter a history
node's ``free_paths``.  A hundred-odd solves of 40-400 points and 4-14
parameters do not want the staged runner's per-solve overhead either.

**Parameters: two widths per group, two numbers per component.**

    θ = [Γ_G, Γ_L] + [2θ_j, I_j] for each component j

The widths are *shared across the group* because a group spans a fraction of a
degree, over which the width law is flat to well inside σ(Γ) — and because a
per-component width is exactly the freedom that lets one component swell to
absorb its neighbour.  Γ_G and Γ_L are the same component FWHMs the instrument
law and the phase size/strain terms produce, so the fitted shape is the
*library's own* (:meth:`_GroupModel._widths` maps them to (Γ, η) for the TCHZ
pseudo-Voigt and (σ, γ) for the true Voigt, via the library's own functions) and
a peak list shares one peak shape with the refinement that follows it.

**Emission lines follow Bragg's law, and the doublet is fitted as a constrained
pair — never stripped.**  The free position is the **Kα1** position 2θ₀; every
other line sits at

    sin θ_l = (λ_l/λ₀)·sin θ₀     ⇒     d(2θ_l)/d(2θ₀) = (λ_l/λ₀)·cosθ₀/cosθ_l

so the splitting grows as 2·tanθ·Δλ/λ rather than being a fixed 2θ offset.  The
Kα2/Kα1 amplitude ratio is **never refined per peak**: a free per-peak ratio is
precisely the freedom that lets a doublet fit swallow an unresolved neighbour,
which is the error Rachinger (1948, J. Sci. Instrum. 25, 254) stripping
formalises — and stripping additionally redistributes the counting noise, so what
is left has neither the position nor the σ it appears to have.  Hence: fitted as
a pair, never subtracted.

It is held at ``source.lines[l].weight`` **times the two lines'
Lorentz-polarisation ratio**, which is not a refinement of the same idea but a
correction of it: the second line diffracts at its own Bragg angle, so it
carries its own Lp, exactly as ``CompiledModel._peak_terms`` gives each line.
Holding the bare weight instead biases the fitted Kα1 position — measured, −2e-4°
and −0.26 mean σ pull on lab Cu Kα LaB6 (:meth:`_GroupModel.freeze`).

**Widths are shared across emission lines too**, and the physics is why: the
dominant broadening is common in Δd/d, hence Δ2θ ∝ tanθ, and between Kα1 and
Kα2 (Δλ/λ ≈ 2.5e-3) that ratio differs by <0.3 % at 2θ = 100° — far inside
σ(Γ).  Per-line widths are unidentifiable at laboratory resolution.

**FCJ asymmetry is applied at the instrument's declared apertures and held
fixed.**  Worth recording *why* it is applied at all rather than dismissed as
second order: the lowest-angle lines are what indexing depends on most (d₂₀ sets
the volume estimate), the axial smear below 90° is one-sided toward low angle,
and an unmodelled one-sided aberration biases those centroids systematically in
one direction — a bias σ cannot see, because σ reports scatter.

**Bérar-Lelann is NOT applied here.**  Its derivation is about serial
correlation across a whole pattern's residual; a 40-400-point window is not that
population, and applying a whole-pattern inflation per peak would compound ~150
independent inflations into the tolerance model.  Do not "fix" this.  The
``√max(χ²_red, 1)`` inflation *is* applied (``normal_covariance(chi2_floor=
True)``): the profile model is not exact over a real peak, and a σ that ignores
that is optimistic exactly where indexing is most sensitive.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from ..model.corrections import lorentz_polarization
from ..model.profiles.fcj import fcj_node_count, fcj_offsets_weights
from ..model.profiles.pseudovoigt import pseudo_voigt_derivs, tch_gamma_eta
from ..model.profiles.voigt import fwhm_to_voigt_params, voigt_derivs
from ..optimize.statistics import normal_covariance
from ..report.layer2 import delta_bic
from ..schemas.indexing import (
    PEAK_KEEP_COMPONENT_MIN_DELTA_BIC,
    PEAK_MAX_RESEED_PASSES,
    PEAK_MIN_HEIGHT_SIGMA,
    PEAK_POSITION_BOUND_FWHM,
    PEAK_WIDTH_BOUND_FACTORS,
)
from ..schemas.instrument import Instrument
from .peaks import Detection, PeakGroup

#: Steps for the two cheap scalar finite differences this module takes — the
#: (Γ_G, Γ_L) → (w₁, w₂) width map, and the FCJ node vectors' motion with
#: position.  The same idiom and the same magnitudes as
#: ``CompiledModel.derivative_bases``, which finite-differences per-reflection
#: *scalars* while keeping the expensive per-point part exact.  Doing it this way
#: rather than hand-writing the TCH quintic's derivative also keeps the fitter
#: shape-agnostic: the true-Voigt width map is differenced by the same two lines.
_H_WIDTH = 1e-7
_H_POS = 1e-5

#: Gaussian FWHM as a fraction of the seed combined Γ at the start of a fit.
#: Both components must start nonzero — the width map's derivative is what
#: identifies them, and a component pinned at zero has none — and a
#: Gaussian-dominant seed is the safer of the two, since a Lorentzian-dominant
#: start over-weights the tails where the frozen background error lives.
_SEED_GAUSS_FRACTION = 0.8


@dataclass
class GroupFit:
    """The converged state of one group's fit."""

    group: PeakGroup
    n: int
    two_theta: np.ndarray          # ° 2θ of each component's Kα1 line
    two_theta_esd: np.ndarray
    intensity: np.ndarray          # integrated area of the Kα1 component
    intensity_esd: np.ndarray
    gamma_g: float
    gamma_l: float
    fwhm: float                    # combined Γ (TCH), ° 2θ
    eta: float
    chi2_red: float
    converged: bool
    at_bound: np.ndarray           # bool per component
    asymmetry_t: np.ndarray        # odd-cubic residual projection, in σ
    n_points: int
    #: 2θ where an extra component would go, if the residual asks for one at
    #: all.  A *proposal*: :func:`fit_group`'s ΔBIC test decides.
    reseed_at: float | None = None
    #: bool per component: did a **re-seed pass** put this component here, rather
    #: than detection?  Provenance, not a judgement — a re-seeded component that
    #: is well separated and comparable in area is an ordinary line.  It is one
    #: of the three conditions :func:`~rietx.indexing.pick._not_separable`
    #: needs, and it is tracked here because ``fit_group`` is the only place that
    #: knows: ``_fit_at`` sees positions, not where they came from.
    from_reseed: np.ndarray | None = None

    def reseeded(self) -> np.ndarray:
        """``from_reseed``, or all-False for a fit that never re-seeded."""
        if self.from_reseed is None:
            return np.zeros(self.n, dtype=bool)
        return np.asarray(self.from_reseed, dtype=bool)


class _GroupModel:
    """Residual and analytic Jacobian for one frozen group.

    The background is the detection's frozen envelope, held **additively**: the
    residual is (y − env − model)/σ, never (net − model)/σ against a subtracted
    baseline that has silently taken counting noise with it.  That is the
    whole-pattern weights invariant (CLAUDE.md) applied to a window.
    """

    def __init__(self, det: Detection, group: PeakGroup, instrument: Instrument,
                 n_components: int, seed_fwhm: float):
        self.x = det.two_theta[group.i0:group.i1]
        self.y = det.intensity[group.i0:group.i1]
        self.sigma = det.sigma[group.i0:group.i1]
        self.env = det.envelope[group.i0:group.i1]
        self.n = n_components
        self.seed_fwhm = seed_fwhm
        self.shape = instrument.profile.shape
        lines = instrument.source.lines
        self.lam = np.array([ln.wavelength.value for ln in lines], dtype=np.float64)
        self.line_weight = np.array([ln.weight.value for ln in lines],
                                    dtype=np.float64)
        self.line_weight[0] = 1.0   # structurally locked (schemas.instrument)
        self.polarization = instrument.source.polarization.value
        self.sl = instrument.geometry.axial_sl.value
        self.hl = instrument.geometry.axial_hl.value
        self.fcj = self.sl > 0.0 and self.hl > 0.0
        # FCJ quadrature sizes and the per-line amplitude gains, frozen per
        # (component, line) before the fit and never changed inside it: the
        # differentiability invariant one level down from the stage compile that
        # owns it for a refinement.
        self.n_nodes: dict[tuple[int, int], int] = {}
        self.line_gain = np.tile(self.line_weight, (max(n_components, 1), 1))

    # -- parameter packing -----------------------------------------------
    def pack(self, gamma_g: float, gamma_l: float, pos: np.ndarray,
             inten: np.ndarray) -> np.ndarray:
        return np.concatenate([[gamma_g, gamma_l],
                               np.stack([pos, inten], axis=1).ravel()])

    def unpack(self, p: np.ndarray) -> tuple[float, float, np.ndarray, np.ndarray]:
        rest = np.asarray(p[2:]).reshape(self.n, 2)
        return float(p[0]), float(p[1]), rest[:, 0].copy(), rest[:, 1].copy()

    def freeze(self, pos: np.ndarray) -> None:
        """Freeze the FCJ node counts and the per-line amplitude gains.

        The **gain** is ``weight_l · Lp(2θ_l)/Lp(2θ₀)``, not ``weight_l`` alone:
        each emission line diffracts at its own Bragg angle, so it also carries
        its own Lorentz-polarisation factor — which is exactly what
        ``CompiledModel._peak_terms`` does per line.  Small and one-sided: over
        the 0.0775° Cu Kα split of the LaB6 110 line at 30.4° it is a 0.43 %
        deficit in the Kα2 amplitude, which drags the fitted **Kα1** position
        down by ~2e-4°.  That is ~0.6σ on a strong lab line, and it showed up as
        a −0.26 mean σ pull across the ensemble (WP-1018) — a bias, so no amount
        of counting removes it.

        Frozen at the *seed* position rather than recomputed inside the solve,
        which is the same trade the FCJ node counts make: the ratio varies by
        ~5 %/° while the fit moves the position by ~1e-3°, so freezing costs
        ~1e-4 relative and buys an exactly differentiable residual and an
        analytic Jacobian with no extra chain factor.
        """
        self.n_nodes = {}
        for j in range(self.n):
            for il in range(len(self.lam)):
                tt = self._line_pos(float(pos[j]), il)
                if not np.isfinite(tt):
                    continue
                if il > 0:
                    lp = lorentz_polarization(
                        np.array([tt, float(pos[j])]), self.polarization)
                    if np.isfinite(lp[1]) and lp[1] > 0.0:
                        self.line_gain[j, il] = (self.line_weight[il]
                                                 * float(lp[0] / lp[1]))
                if self.fcj:
                    self.n_nodes[(j, il)] = fcj_node_count(
                        float(tt), max(self.seed_fwhm, 1e-6), self.sl, self.hl)

    # -- emission-line chain ----------------------------------------------
    def _line_pos(self, pos0: float, il: int) -> float:
        """2θ of line ``il`` for a Kα1 position ``pos0`` — Bragg's law, which is
        literally the ghost transform in ``background.diagnostics``."""
        if il == 0:
            return pos0
        s = self.lam[il] / self.lam[0] * np.sin(np.radians(0.5 * pos0))
        if not (-1.0 <= s <= 1.0):
            return float("nan")
        return 2.0 * np.degrees(np.arcsin(s))

    def _line_dpos(self, pos0: float, il: int) -> float:
        """d(2θ_l)/d(2θ₀) = (λ_l/λ₀)·cosθ₀/cosθ_l."""
        if il == 0:
            return 1.0
        th0 = np.radians(0.5 * pos0)
        thl = np.radians(0.5 * self._line_pos(pos0, il))
        c = np.cos(thl)
        if not np.isfinite(c) or abs(c) < 1e-12:
            return 1.0
        return float(self.lam[il] / self.lam[0] * np.cos(th0) / c)

    # -- shape -------------------------------------------------------------
    def _widths(self, gamma_g: float, gamma_l: float) -> tuple[float, float]:
        """(w₁, w₂) of the active shape from component FWHMs — the library's own
        map: (Γ, η) for the TCHZ pseudo-Voigt, (σ, γ_HWHM) for the true Voigt."""
        if self.shape == "voigt":
            w1, w2 = fwhm_to_voigt_params(gamma_g, gamma_l)
        else:
            w1, w2 = tch_gamma_eta(gamma_g, gamma_l)
        return float(w1), float(w2)

    def _profile_derivs(self, x: np.ndarray, w1: float, w2: float):
        if self.shape == "voigt":
            return voigt_derivs(x, w1, w2)
        return pseudo_voigt_derivs(x, w1, w2)

    def _shape_terms(self, j: int, il: int, pos0: float, w1: float, w2: float):
        """(Ω, ∂Ω/∂pos₀, ∂Ω/∂w₁, ∂Ω/∂w₂) for component ``j``, line ``il``.

        Under FCJ the images and weights are generated at the *line's* own
        position, and their motion with position is finite-differenced on the
        node vectors themselves (≤64 numbers) exactly as ``derivative_bases``
        does, while the per-point profile partials stay exact.
        """
        tt = self._line_pos(pos0, il)
        if not np.isfinite(tt):
            z = np.zeros_like(self.x)
            return z, z, z, z
        chain = self._line_dpos(pos0, il)
        n_nodes = self.n_nodes.get((j, il), 0)
        if n_nodes == 0:
            pv, d_dx, d_w1, d_w2 = self._profile_derivs(self.x - tt, w1, w2)
            return pv, -d_dx * chain, d_w1, d_w2
        phi, om = fcj_offsets_weights(float(tt), self.sl, self.hl, n_nodes)
        pv, d_dx, d_w1, d_w2 = self._profile_derivs(
            self.x[None, :] - phi[:, None], w1, w2)
        phi1, om1 = fcj_offsets_weights(float(tt) + _H_POS, self.sl, self.hl,
                                        n_nodes)
        if len(phi1) != len(phi):
            d_line = -(om @ d_dx)              # crossed the symmetric fallback
        else:
            dphi, dom = (phi1 - phi) / _H_POS, (om1 - om) / _H_POS
            d_line = (dom @ pv) - ((om * dphi) @ d_dx)
        return om @ pv, d_line * chain, om @ d_w1, om @ d_w2

    # -- residual / jacobian ----------------------------------------------
    def model(self, p: np.ndarray) -> np.ndarray:
        gg, gl, pos, inten = self.unpack(p)
        w1, w2 = self._widths(gg, gl)
        total = np.zeros_like(self.x)
        for j in range(self.n):
            for il in range(len(self.lam)):
                om = self._shape_terms(j, il, float(pos[j]), w1, w2)[0]
                total = total + inten[j] * self.line_gain[j, il] * om
        return total

    def residual(self, p: np.ndarray) -> np.ndarray:
        return (self.y - self.env - self.model(p)) / self.sigma

    def jacobian(self, p: np.ndarray) -> np.ndarray:
        gg, gl, pos, inten = self.unpack(p)
        w1, w2 = self._widths(gg, gl)
        w1_g, w2_g = self._widths(gg + _H_WIDTH, gl)
        w1_l, w2_l = self._widths(gg, gl + _H_WIDTH)
        dw1_dgg, dw2_dgg = (w1_g - w1) / _H_WIDTH, (w2_g - w2) / _H_WIDTH
        dw1_dgl, dw2_dgl = (w1_l - w1) / _H_WIDTH, (w2_l - w2) / _H_WIDTH

        jac = np.zeros((len(self.x), 2 + 2 * self.n))
        for j in range(self.n):
            for il in range(len(self.lam)):
                om, d_pos, d_w1, d_w2 = self._shape_terms(
                    j, il, float(pos[j]), w1, w2)
                a = inten[j] * self.line_gain[j, il]
                jac[:, 0] += a * (d_w1 * dw1_dgg + d_w2 * dw2_dgg)
                jac[:, 1] += a * (d_w1 * dw1_dgl + d_w2 * dw2_dgl)
                jac[:, 2 + 2 * j] += a * d_pos
                jac[:, 3 + 2 * j] += self.line_gain[j, il] * om
        # r = (y − env − model)/σ  ⇒  ∂r/∂p = −(∂model/∂p)/σ
        return -jac / self.sigma[:, None]

    # -- seeds and bounds --------------------------------------------------
    def seed(self, pos: np.ndarray) -> np.ndarray:
        """Seed vector: the calibrated width split Gaussian-dominant, and each
        component's area as net height × FWHM.

        A unit-area profile of width Γ has height ≈ 0.94/Γ (Gaussian) to 0.64/Γ
        (Lorentzian), so height × Γ is the area to within tens of percent — which
        is all a seed for a linear-in-intensity parameter needs.
        """
        gg = _SEED_GAUSS_FRACTION * self.seed_fwhm
        gl = (1.0 - _SEED_GAUSS_FRACTION) * self.seed_fwhm
        net = self.y - self.env
        inten = np.empty(len(pos))
        for j, p0 in enumerate(pos):
            k = int(np.argmin(np.abs(self.x - p0)))
            inten[j] = max(float(net[k]), 1e-3) * self.seed_fwhm
        return self.pack(gg, gl, np.asarray(pos, dtype=np.float64), inten)

    def bounds(self, pos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Native trust-region bounds — no softplus reparameterisation.

        The widths' *lower* bound is what keeps Γ strictly positive (the profile
        is (1/Γ)·f(x/Γ)), which is the only thing a softplus was ever buying
        here, and native bounds keep the analytic Jacobian in physical units
        with no chain factor.  Positions are bounded to
        ``PEAK_POSITION_BOUND_FWHM`` of their seed: a fit that wants to move
        further is reporting a detection failure, so it comes back *at* its
        bound with a flag rather than converging somewhere unrelated.
        """
        f_lo, f_hi = PEAK_WIDTH_BOUND_FACTORS
        r = PEAK_POSITION_BOUND_FWHM * self.seed_fwhm
        lo = [f_lo * self.seed_fwhm, f_lo * self.seed_fwhm]
        hi = [f_hi * self.seed_fwhm, f_hi * self.seed_fwhm]
        for p0 in pos:
            lo += [p0 - r, 0.0]
            hi += [p0 + r, np.inf]
        return np.array(lo), np.array(hi)


def _asymmetry_t(m: _GroupModel, p: np.ndarray) -> np.ndarray:
    """Per-component |t| of the residual's odd-**cubic** projection.

    Odd-cubic and not odd-linear, because a free position already absorbs the
    first odd moment exactly: after the fit, ∂Ω/∂pos is orthogonal to the
    residual by construction, so projecting onto it measures convergence, not
    asymmetry.  The next odd direction is the leading detectable signature of an
    unmodelled one-sided aberration.

        t = Σ (r/σ)·u³·Ω̂ / √(Σ (u³·Ω̂/σ)²),   u = (x − 2θ_j)/Γ

    which is the residual amplitude along that direction in units of σ, so it is
    read against a plain |t| threshold.
    """
    gg, gl, pos, _inten = m.unpack(p)
    w1, w2 = m._widths(gg, gl)
    gamma = float(tch_gamma_eta(gg, gl)[0])
    r = m.residual(p)
    out = np.zeros(m.n)
    for j in range(m.n):
        u = (m.x - pos[j]) / max(gamma, 1e-9)
        shape = m._shape_terms(j, 0, float(pos[j]), w1, w2)[0]
        basis = u ** 3 * shape
        norm = float(np.sqrt(np.sum((basis / m.sigma) ** 2)))
        if norm <= 0.0:
            continue
        out[j] = abs(float(np.sum(r * basis / m.sigma)) / norm)
    return out


def _solve(m: _GroupModel, pos: np.ndarray) -> tuple[np.ndarray, object]:
    m.freeze(pos)
    p0 = m.seed(pos)
    lo, hi = m.bounds(pos)
    p0 = np.clip(p0, lo + 1e-12, hi - 1e-12)
    res = least_squares(m.residual, p0, jac=m.jacobian, bounds=(lo, hi),
                        method="trf", xtol=1e-12, ftol=1e-12, gtol=1e-12)
    return res.x, res


def fit_group_at(det: Detection, group: PeakGroup, instrument: Instrument,
                 positions: np.ndarray) -> GroupFit:
    """One solve with **exactly** these components — the editing entry point.

    :func:`fit_group` owns the judgement calls (shoulder pruning, ΔBIC
    re-seeding); this deliberately makes none of them, because its caller is a
    human who has already said where the components are (WP-1027's
    ``add_peak``/``move_peak``/``refit_group``).  The count is frozen, the
    positions are seeds for the same bounded solve detection's seeds get, and
    ``from_reseed`` stays ``None`` — a component a human placed is not a
    residual's proposal, so :func:`~rietx.indexing.pick._not_separable` never
    fires on it by condition 1 alone.
    """
    pos = np.sort(np.asarray(positions, dtype=np.float64))
    if pos.ndim != 1 or len(pos) == 0:
        raise ValueError("fit_group_at needs at least one component position")
    return _fit_at(det, group, instrument, pos)


def group_profile(det: Detection, group: PeakGroup, instrument: Instrument,
                  fit: GroupFit) -> np.ndarray:
    """The fitted model of one group, evaluated on its own frozen window.

    Drawing, not fitting: WP-1027's panel shows the fitted group profile over
    the data, and the profile is reconstructable from a :class:`GroupFit`'s
    ``(gamma_g, gamma_l, two_theta, intensity)`` without re-solving anything.
    The FCJ node counts and per-line gains are frozen at the *fitted* positions
    here rather than the seeds — a ~1e-4 relative difference (the ratio moves
    ~5 %/° while a fit moves positions ~1e-3°), invisible at plot resolution.

    Returns the peak model only (no background); add ``det.envelope`` over the
    same window to draw it against the measured counts.
    """
    m = _GroupModel(det, group, instrument, fit.n, group.seed_fwhm)
    m.freeze(fit.two_theta)
    return m.model(m.pack(fit.gamma_g, fit.gamma_l, fit.two_theta, fit.intensity))


def fit_group(det: Detection, group: PeakGroup, instrument: Instrument, *,
              max_reseed: int = PEAK_MAX_RESEED_PASSES) -> GroupFit:
    """Fit one group: solve, prune shoulder seeds, then re-seed if asked.

    The component count is frozen before each solve and never changes inside
    it — a fitter that adds or drops a component mid-solve has a discontinuous
    residual, which is the frozen-per-stage invariant restated one level down.
    Adding *and removing* a component is therefore an explicit second solve, and
    either way the decision is
    :data:`~rietx.schemas.indexing.PEAK_KEEP_COMPONENT_MIN_DELTA_BIC` on
    ``report.layer2.delta_bic`` — the same statistic the Stephens acceptance
    quotes, and for the same reason Hamilton's R-ratio is not used: at these
    channel counts an R-ratio blesses an inert improvement.

    **Pruning runs before re-seeding, and it is what closes a gap the ΔBIC gate
    had.**  A shoulder seed that lands far from any maximum forms a group of its
    own, and a *singleton* group faced no test at all: the gate as first written
    only judged components that a re-seed pass had added, so a curvature false
    positive became a reported line with an esd and no evidence.  Every
    shoulder-seeded component now has to earn its two parameters against its own
    absence — for a singleton, against there being no peak there whatsoever.
    """
    pos = np.asarray(group.seed_two_theta, dtype=np.float64)
    shoulder = np.asarray(group.from_shoulder, dtype=bool)
    best = _fit_at(det, group, instrument, pos)
    best, pos, shoulder = _prune_shoulders(det, group, instrument, best, pos,
                                           shoulder)
    if best is None:                            # every component was pruned
        return _empty_fit(det, group, instrument)
    added = np.zeros(best.n, dtype=bool)
    for _ in range(max_reseed):
        if best.reseed_at is None or not best.converged:
            break
        trial_pos = np.sort(np.concatenate([best.two_theta, [best.reseed_at]]))
        trial = _fit_at(det, group, instrument, trial_pos)
        gain = delta_bic(_chi2(best), _chi2(trial),
                         n_points=best.n_points, n_added=2)
        if gain < PEAK_KEEP_COMPONENT_MIN_DELTA_BIC:
            break
        # provenance travels with the *sorted* position vector, so the new
        # component is identified by where it was inserted rather than by index
        k = int(np.searchsorted(best.two_theta, best.reseed_at))
        added = np.insert(added, k, True)
        best = trial
    best.from_reseed = added
    return best


def _prune_shoulders(det: Detection, group: PeakGroup, instrument: Instrument,
                     fit: GroupFit, pos: np.ndarray, shoulder: np.ndarray,
                     ) -> tuple[GroupFit | None, np.ndarray, np.ndarray]:
    """Drop shoulder-seeded components that do not clear ΔBIC.

    Only shoulder seeds are tested, and the asymmetry is deliberate: a
    maximum-detected component already cleared a σ-normalised *height* test on
    the data itself, whereas a curvature seed cleared only a test on the second
    derivative.  Weakest first, so that removing one cannot mask another.
    """
    tested: set[float] = set()
    while shoulder.any():
        # significance recomputed every pass, and candidacy keyed by seed 2θ
        # rather than by index: dropping a component renumbers the rest, and an
        # index list built once before the first drop points at the wrong ones
        esd = np.where(fit.intensity_esd > 0.0, fit.intensity_esd, np.inf)
        weakest_first = np.argsort(np.abs(fit.intensity) / esd)
        cands = [int(j) for j in weakest_first
                 if shoulder[j] and float(pos[j]) not in tested]
        if not cands:
            break
        j = cands[0]
        tested.add(float(pos[j]))
        keep = np.ones(len(pos), dtype=bool)
        keep[j] = False
        if not keep.any():
            gain = delta_bic(_null_chi2(det, group), _chi2(fit),
                             n_points=fit.n_points, n_added=4)
            if gain < PEAK_KEEP_COMPONENT_MIN_DELTA_BIC:
                return None, pos[keep], shoulder[keep]
            continue
        trial = _fit_at(det, group, instrument, pos[keep])
        gain = delta_bic(_chi2(trial), _chi2(fit),
                         n_points=fit.n_points, n_added=2)
        if gain < PEAK_KEEP_COMPONENT_MIN_DELTA_BIC:
            fit, pos, shoulder = trial, pos[keep], shoulder[keep]
    return fit, pos, shoulder


def _null_chi2(det: Detection, group: PeakGroup) -> float:
    """Σ((y − env)/σ)² over the window — the no-peak-at-all model.

    The frozen envelope is the *whole* model in this hypothesis, which is only
    honest because it is held additively rather than subtracted: there is a
    background here either way, and the question is whether a peak is needed
    on top of it.
    """
    s = slice(group.i0, group.i1)
    r = (det.intensity[s] - det.envelope[s]) / det.sigma[s]
    return float(r @ r)


def _empty_fit(det: Detection, group: PeakGroup,
               instrument: Instrument) -> GroupFit:
    """A group that pruned away to nothing: zero components, no lines."""
    n_points = group.i1 - group.i0
    return GroupFit(
        group=group, n=0, two_theta=np.zeros(0), two_theta_esd=np.zeros(0),
        intensity=np.zeros(0), intensity_esd=np.zeros(0),
        gamma_g=float("nan"), gamma_l=float("nan"), fwhm=group.seed_fwhm,
        eta=float("nan"), chi2_red=_null_chi2(det, group) / max(n_points, 1),
        converged=True, at_bound=np.zeros(0, dtype=bool),
        asymmetry_t=np.zeros(0), n_points=n_points, reseed_at=None)


def _chi2(fit: GroupFit) -> float:
    """Σr² from the reported reduced χ², undoing the (N−P) division only.

    ``delta_bic`` wants the two models' *absolute* χ² at a common N, and
    ``normal_covariance`` reports the reduced form; the floor it applies to the
    covariance is not applied to the returned value, so this is the raw sum.
    """
    return fit.chi2_red * max(fit.n_points - (2 + 2 * fit.n), 1)


def _fit_at(det: Detection, group: PeakGroup, instrument: Instrument,
            pos: np.ndarray) -> GroupFit:
    """One frozen-count solve, with esds and the diagnostic projections."""
    m = _GroupModel(det, group, instrument, len(pos), group.seed_fwhm)
    p, res = _solve(m, pos)
    gg, gl, fit_pos, inten = m.unpack(p)
    cov, chi2_red = normal_covariance(
        np.asarray(res.jac), np.asarray(res.fun), len(p), chi2_floor=True,
        what="peak-group residual entering the covariance solve")
    esd = np.sqrt(np.maximum(np.diag(cov), 0.0))
    # the combined TCH Γ and η are the reported width and mixing under *both*
    # shapes: Γ_TCH tracks the true Voigt FWHM to ~1 %, which is what the TCH
    # quintic is fitted to, and one width summary keeps a peak list comparable
    # across instruments that differ only in `profile.shape`
    fwhm, eta = tch_gamma_eta(gg, gl)

    lo, hi = m.bounds(pos)
    tol = 1e-8 * np.maximum(np.abs(pos), 1.0)
    at_bound = np.array([
        bool(abs(fit_pos[j] - lo[2 + 2 * j]) <= tol[j]
             or abs(fit_pos[j] - hi[2 + 2 * j]) <= tol[j])
        for j in range(len(pos))], dtype=bool)

    # a proposal for one more component: the residual's largest positive
    # excursion, held to the same σ-normalised height a detection needed
    k = int(np.argmax(res.fun))
    reseed = float(m.x[k]) if res.fun[k] > PEAK_MIN_HEIGHT_SIGMA else None

    return GroupFit(
        group=group, n=len(pos), two_theta=fit_pos,
        two_theta_esd=esd[2::2], intensity=inten, intensity_esd=esd[3::2],
        gamma_g=gg, gamma_l=gl, fwhm=float(fwhm), eta=float(eta),
        chi2_red=chi2_red, converged=bool(res.status > 0), at_bound=at_bound,
        asymmetry_t=_asymmetry_t(m, p), n_points=len(m.x), reseed_at=reseed)
