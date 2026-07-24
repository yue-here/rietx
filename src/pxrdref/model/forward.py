"""The Rietveld forward model.

Assembles

    y_calc(2θ_i) = y_bkg(2θ_i)
                 + Σ_p Σ_l Σ_k I_{pk} · w_l · Ω_lk(2θ_i)

where the sums run over phases p, source emission lines l (Kα1/Kα2 …, each
diffracting at its own Bragg angle so the splitting grows with tanθ) and
reflections k.  For **Rietveld mode** the integrated reflection intensity is

    I_{pk} = S_p · m_{pk} · |F_{pk}|² · Lp(2θ_{lk})            (Rietveld 1969)

(|F|² depends only on sinθ/λ = 1/2d and is shared across lines; Lp is
evaluated per line) and for **Le Bail mode** I_{pk} are empirical per-hkl
values updated between least-squares cycles by observed-intensity
partitioning summed over lines (Le Bail, Duroy & Fourquet, 1988, Mater. Res.
Bull. 23, 447).  Ω_lk is the unit-area TCHZ pseudo-Voigt
(profiles.pseudovoigt), optionally smeared by the Finger-Cox-Jephcoat
axial-divergence aberration (profiles.fcj) into a fixed-node quadrature sum
of images that still integrates to exactly 1.

Peak positions:  2θ_lk = 2θ_Bragg(d_k, λ_l) + zero
                       [+ displacement/transparency shifts, Bragg-Brentano]

Differentiability invariants honoured here (see docs/DESIGN.md):
* the reflection list is frozen in the compiled model (regenerate between
  stages);
* each (line, reflection) pair is evaluated only inside a *frozen*
  point-index window, chosen wide enough at compile time (incl. the FCJ
  smear extent) that the profile is ≈ 0 at the edges;
* FCJ quadrature node counts are frozen per stage; node positions follow
  the refined parameters smoothly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..backend import get_backend
from ..background.models import (
    bspline_design_matrix,
    chebyshev_design_matrix,
    interpolate_fixed,
    second_difference_matrix,
)
from ..crystallography.adp import U_NAMES, reciprocal_axis_lengths
from ..crystallography.lattice import (
    cell_volume,
    d_spacings,
    reciprocal_metric_tensor,
    two_theta_deg,
)
from ..crystallography.structure_factor import (
    PhaseSites,
    compile_phase_sites,
    d_f2_d_uaniso,
    d_f2_d_xyz,
    structure_factors_squared,
)
from ..crystallography.symmetry import (
    ReflectionSet,
    generate_reflections,
    reflection_orbits,
)
from ..schemas.common import Mode
from ..schemas.instrument import (
    BackgroundChebyshev,
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    Instrument,
)
from ..schemas.pattern import PatternData
from ..schemas.structure import Structure
from .corrections import (
    displacement_shift_deg,
    lorentz_polarization,
    transparency_shift_deg,
)
from .extinction import sabine_extinction, sabine_extinction_and_dx
from .preferred_orientation import (
    march_dollase_and_dr,
    march_dollase_factors,
    orbit_layout,
)
from .profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from .profiles.fcj import fcj_extent_deg, fcj_node_count, fcj_offsets_weights
from .profiles.pseudovoigt import pseudo_voigt, pseudo_voigt_derivs, tch_gamma_eta
from .profiles.voigt import fwhm_to_voigt_params, voigt, voigt_derivs

#: windows extend ±(WINDOW_FWHM_MULT · Γ_est + WINDOW_MIN_DEG + FCJ extent)
WINDOW_FWHM_MULT = 30.0
WINDOW_MIN_DEG = 0.3
#: when the axial S/L, H/L parameters are about to be *refined* from zero,
#: quadrature nodes are sized as if they were at least this large, so the
#: finite-difference Jacobian sees a live parameter instead of a frozen
#: zero-node profile
AXIAL_SIZING_FLOOR = 0.02

#: two reflections are treated as "strongly overlapped" for Pawley conditioning
#: when their primary-line centres sit within this fraction of their mean FWHM
PAWLEY_OVERLAP_FWHM_FRAC = 0.5
#: soft equal-split restraint weight for overlapped Pawley groups.  With the
#: per-group intensity scaling in ``build_pawley_restraint`` this makes the
#: split-direction esd ≈ (group intensity)/√λ, i.e. an unresolved split is
#: reported with an esd of order its own value (≈100 % at λ=1) rather than the
#: spuriously tight one a bare pseudo-inverse of a singular JᵀJ would give.
PAWLEY_OVERLAP_LAMBDA = 1.0


@dataclass
class CompiledPhase:
    reflections: ReflectionSet
    sites: PhaseSites
    # frozen evaluation windows, one (start, stop) point-index pair per
    # (emission line, reflection)
    win: np.ndarray  # (n_lines, N, 2) int
    # frozen FCJ quadrature node counts, 0 → symmetric peak
    fcj_n: np.ndarray  # (n_lines, N) int
    # per-hkl integrated intensity buffer, set in lebail *and* pawley mode:
    # storage AT REST (between stages, for history/plots/exporters).  The hot
    # loop never reads it — the residual/Jacobian closures pass the intensity
    # vector explicitly through phase_peaks/evaluate, so nothing mutates
    # mid-solve (the WP-0401 purity contract; what makes Pawley/Le Bail
    # traceable by an autodiff backend).
    hkl_intensity: np.ndarray | None = None  # (N,)
    # primary-line 2θ and estimated FWHM at compile, kept for Pawley overlap
    # grouping (None outside pawley mode)
    tt_primary: np.ndarray | None = None  # (N,)
    fwhm_primary: np.ndarray | None = None  # (N,)
    # March-Dollase preferred orientation: the frozen symmetry orbit of every
    # reflection (flattened; see preferred_orientation.orbit_layout) plus the
    # fixed integer axis.  None unless the phase carries a PO block in Rietveld
    # mode.  The angles the correction needs move with the cell at evaluation;
    # only these integer members are frozen for the stage.
    po_axis: np.ndarray | None = None       # (3,) int
    po_members: np.ndarray | None = None    # (M_total, 3) int
    po_seg: np.ndarray | None = None        # (M_total,) int → reflection index
    po_counts: np.ndarray | None = None     # (N,) int orbit sizes


@dataclass
class CompiledModel:
    """Everything frozen for one refinement stage + fast evaluation buffers."""

    tt: np.ndarray          # fit grid (in-range points only), deg 2θ
    y_obs: np.ndarray
    sigma: np.ndarray
    tt_min: float
    tt_max: float
    wavelength: float                 # primary line, used for tick positions
    line_wavelengths: tuple[float, ...]
    geometry_kind: str
    radius_mm: float | None
    mode: Mode
    phases: list[CompiledPhase]
    fixed_background: np.ndarray | None  # sampled on tt, or None
    # the background is linear in its parameters: y_bkg = Σ values[path]·row
    # (Chebyshev or B-spline rows + optional 1/x air term — exact Jacobian
    # columns either way)
    bkg_paths: tuple[str, ...]
    bkg_design: np.ndarray  # (len(bkg_paths), n_points)
    # P-spline smoothness penalty: extra residual rows √λ·D₂·c, already scaled
    # (columns aligned with bkg_paths); None for penalty-free backgrounds
    bkg_penalty: np.ndarray | None
    # peak shape frozen for the stage: "tchz_pv" (default pseudo-Voigt) or
    # "voigt" (true Gaussian⊗Lorentzian via the shared Faddeeva w(z)).  A
    # compile-time structural constant, never a θ entry — the width parameters
    # (U,V,W,X,Y and phase size/strain) are identical for both shapes.
    shape: str = "tchz_pv"
    # Pawley intensity block (per-hkl intensities as free parameters, appended
    # to θ outside the ParameterTable); None outside pawley mode.
    pawley: "PawleyBlock | None" = None
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    def background(self, values: dict[str, float]) -> np.ndarray:
        # stacked, not np.array-ed: the coefficients come from θ (traced)
        coeffs = get_backend().stack([values[p] for p in self.bkg_paths])
        y = coeffs @ self.bkg_design
        if self.fixed_background is not None:
            y = y + self.fixed_background
        return y

    def penalty_residual(self, values: dict[str, float]) -> np.ndarray | None:
        """√λ·D₂·c rows appended to the residual (P-spline smoothness)."""
        if self.bkg_penalty is None:
            return None
        coeffs = get_backend().stack([values[p] for p in self.bkg_paths])
        return self.bkg_penalty @ coeffs

    def _position_shift_deg(self, theta: np.ndarray, tt_bragg: np.ndarray,
                            values: dict[str, float]) -> np.ndarray | float:
        """Detector-space peak shifts beyond the Bragg angle (zero + geometry).

        Evaluated unconditionally: s = 0 and t = 0 contribute an exact ±0
        shift (purity refactor (b) — no branching on θ-decoded values; the
        geometry check is compile-time structural and may stay).
        """
        shift = values["instrument.zero_shift"]
        if self.geometry_kind == "bragg_brentano":
            s = values["instrument.geometry.sample_displacement"]
            shift = shift + displacement_shift_deg(theta, s, self.radius_mm)
            t = values["instrument.geometry.sample_transparency"]
            shift = shift + transparency_shift_deg(tt_bragg, t)
        return shift

    def _site_values(self, ip: int, values: dict[str, float], cell: tuple
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                np.ndarray | None, np.ndarray | None]:
        """(xyz, occ, biso, U^ij, a*) for the structure-factor call.

        The anisotropic pair is ``None`` unless the phase has at least one
        anisotropic site, so the common isotropic path does no extra work.
        Rows of isotropic atoms are zero-filled and never read (``sites.aniso``
        selects); a* moves with the cell, so it is recomputed per call.
        """
        xp = get_backend()
        sites = self.phases[ip].sites
        n = sites.n_asym
        xyz = xp.stack([xp.stack([values[f"phases.{ip}.atoms.{j}.{c}"]
                                  for c in ("x", "y", "z")]) for j in range(n)])
        occ = xp.stack([values[f"phases.{ip}.atoms.{j}.occ"] for j in range(n)])
        biso = xp.stack([values[f"phases.{ip}.atoms.{j}.biso"] for j in range(n)])
        if not sites.any_aniso:
            return xyz, occ, biso, None, None
        uaniso = xp.stack([xp.stack([values.get(f"phases.{ip}.atoms.{j}.{u}", 0.0)
                                     for u in U_NAMES]) for j in range(n)])
        return xyz, occ, biso, uaniso, reciprocal_axis_lengths(*cell)

    def _po_factors(self, ip: int, values: dict[str, float], cell: tuple
                    ) -> np.ndarray | None:
        """March-Dollase P_hkl (N,) for phase ip, or None when off.

        The frozen orbits live on the compiled phase; the angles are taken with
        the reciprocal metric of the *current* cell, so P follows the cell (and
        r) smoothly through a least-squares run.
        """
        cp = self.phases[ip]
        if cp.po_axis is None:
            return None
        gstar = reciprocal_metric_tensor(*cell)
        r = values[f"phases.{ip}.preferred_orientation.r"]
        return march_dollase_factors(cp.po_members, cp.po_seg, cp.po_counts,
                                     cp.po_axis, gstar, r)

    # ------------------------------------------------------------------
    # peak-shape dispatch — the two width scalars, the unit-area profile and
    # its partials all switch on the frozen ``shape`` (default TCHZ).  Both
    # shapes consume the *same* component FWHMs and expose a two-width tuple
    # ``(pos, w₁, w₂, intensity)``, so everything downstream (the peak-chain
    # Jacobian, Le Bail partitioning, FitReport Layer-1) is shape-agnostic.
    # ------------------------------------------------------------------
    def _peak_widths(self, gam_g: np.ndarray, gam_l: np.ndarray
                     ) -> tuple[np.ndarray, np.ndarray]:
        """(w₁, w₂) from component FWHMs: (Γ, η) for TCHZ, (σ, γ_HWHM) for Voigt."""
        if self.shape == "voigt":
            return fwhm_to_voigt_params(gam_g, gam_l)
        return tch_gamma_eta(gam_g, gam_l)

    def _profile(self, x: np.ndarray, w1: np.ndarray, w2: np.ndarray) -> np.ndarray:
        """Unit-area profile of the active shape at offsets ``x``."""
        if self.shape == "voigt":
            return voigt(x, w1, w2)
        return pseudo_voigt(x, w1, w2)

    def _profile_derivs(self, x: np.ndarray, w1: float, w2: float
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(Ω, ∂Ω/∂x, ∂Ω/∂w₁, ∂Ω/∂w₂) of the active shape."""
        if self.shape == "voigt":
            return voigt_derivs(x, w1, w2)
        return pseudo_voigt_derivs(x, w1, w2)

    def phase_peaks(self, ip: int, values: dict[str, float],
                    hkl_intensity: np.ndarray | None = None
                    ) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """Per-line (positions, w₁, w₂, intensities) for phase ip.

        Returns one (pos, w₁, w₂, intensity) tuple per emission line; arrays run
        over the frozen reflection list.  The two width slots are shape-specific
        (``_peak_widths``): (Γ, η) for the TCHZ pseudo-Voigt, (σ, γ_HWHM) for the
        true Voigt.  ``intensity`` already carries the line weight (and Lp per
        line in Rietveld mode).

        In lebail/pawley mode ``hkl_intensity`` supplies the per-hkl
        intensities explicitly — the residual/Jacobian closures always pass it
        (purity: never read mutable state mid-solve).  ``None`` falls back to
        the phase's at-rest buffer, for callers outside the hot loop (plots,
        exporters, replay).
        """
        xp = get_backend()
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.hkl, *cell)

        if self.mode in ("lebail", "pawley"):
            # extracted by partitioning (Le Bail) or refined as θ (Pawley) —
            # identical from here on
            base = cp.hkl_intensity if hkl_intensity is None else hkl_intensity
        else:
            # |F|² samples the form factors at sinθ/λ = 1/2d — line-independent
            f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                           *self._site_values(ip, values, cell))
            base = values[f"phases.{ip}.scale"] * cp.reflections.multiplicity * f2
            # March-Dollase preferred orientation: a line-independent per-hkl
            # intensity multiplier folded into ``base`` (P ≡ 1 when off, so this
            # leaves the intensity bit-identical then).  It rides ahead of the
            # extinction multiply — both commute — and the extinction variable x
            # still uses the raw |F|², not this product.
            P = self._po_factors(ip, values, cell)
            if P is not None:
                base = base * P
            # secondary extinction (model/extinction.py): a per-(line,
            # reflection) intensity multiplier folded in below, evaluated
            # unconditionally — ext=0 makes E exactly 1 (Sabine's blend is
            # sin²θ·1 + cos²θ·1, which is exactly 1.0 in fp), so the off
            # state stays bit-identical without branching on θ (purity (b)).
            # V moves with the cell, hence recomputed here rather than cached.
            ext = values[f"phases.{ip}.extinction"]
            vol = cell_volume(*cell)

        out = []
        for il, lam in enumerate(self.line_wavelengths):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = two_theta_deg(d, lam)
            theta = 0.5 * tt_bragg  # Bragg angle drives widths and Lp
            pos = tt_bragg + self._position_shift_deg(theta, tt_bragg, values)
            gam_g = gaussian_fwhm(theta, values["instrument.profile.u"],
                                  values["instrument.profile.v"], values["instrument.profile.w"],
                                  values[f"phases.{ip}.gauss_size"],
                                  values[f"phases.{ip}.gauss_strain"])
            gam_l = lorentzian_fwhm(theta,
                                    values["instrument.profile.x"] + values[f"phases.{ip}.lor_size"],
                                    values["instrument.profile.y"] + values[f"phases.{ip}.lor_strain"])
            gamma, eta = self._peak_widths(gam_g, gam_l)
            if self.mode in ("lebail", "pawley"):
                # extracted/refined intensities already absorb Lp
                intensity = base * w_line
            else:
                intensity = base * w_line * lorentz_polarization(tt_bragg, values["instrument.polarization"])
                intensity = intensity * sabine_extinction(f2, lam, vol, tt_bragg, ext)
            # a reflection pushed off the sphere (λ/2d > 1 → NaN position)
            # carries exactly zero intensity: Lp of a NaN angle is NaN, and the
            # masked profile (purity (c)) would otherwise multiply NaN·0
            intensity = xp.where(xp.isfinite(pos), intensity, 0.0)
            out.append((pos, gamma, eta, intensity))
        return out

    def _reflection_profile(self, cp: CompiledPhase, il: int, k: int,
                            pos_k: float, gamma_k: float, eta_k: float,
                            sl: float, hl: float) -> np.ndarray | None:
        """Unit-area profile of one (line, reflection) on its frozen window.

        Returns ``None`` only for the frozen empty window (``i1 <= i0``, a
        compile-time structural branch).  A non-finite *position* is
        θ-dependent, so it is a where-mask instead (purity (c)): the profile
        is evaluated at a safe position and zeroed element-wise —
        ``phase_peaks`` zeroes the matching intensity, so a dead reflection
        contributes exactly 0 without a python branch.
        """
        i0, i1 = cp.win[il, k]
        if i1 <= i0:
            return None
        xp = get_backend()
        finite = xp.isfinite(pos_k)
        pos_safe = xp.where(finite, pos_k, 0.0)
        x = self.tt[i0:i1]
        n_fcj = int(cp.fcj_n[il, k])
        if n_fcj == 0:  # frozen node count — structural
            return xp.where(finite, self._profile(x - pos_safe, gamma_k, eta_k), 0.0)
        # FCJ images computed at the apparent position: the ≤0.1° detector
        # shifts change the aberration geometry negligibly (≪ node spacing)
        phi, omega = fcj_offsets_weights(pos_safe, sl, hl, n_fcj)
        prof = omega @ self._profile(x[None, :] - phi[:, None], gamma_k, eta_k)
        return xp.where(finite, prof, 0.0)

    def phase_component(self, ip: int, values: dict[str, float],
                        hkl_intensity: np.ndarray | None = None) -> np.ndarray:
        """Bragg contribution of one phase (used by the analytic scale Jacobian)."""
        xp = get_backend()
        y = xp.zeros_like(self.tt)
        cp = self.phases[ip]
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        peaks = self.phase_peaks(ip, values, hkl_intensity)
        for il, (pos, gamma, eta, intensity) in enumerate(peaks):
            for k in range(len(pos)):
                prof = self._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k], sl, hl)
                if prof is None:
                    continue
                i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                y = xp.window_add(y, i0, i1, intensity[k] * prof)
        return y

    def bragg_component(self, values: dict[str, float],
                        intensities: list[np.ndarray] | None = None) -> np.ndarray:
        y = get_backend().zeros_like(self.tt)
        for ip in range(len(self.phases)):
            y = y + self.phase_component(
                ip, values, None if intensities is None else intensities[ip])
        return y

    def evaluate(self, values: dict[str, float],
                 intensities: list[np.ndarray] | None = None) -> np.ndarray:
        """y_calc on the fit grid.  ``intensities`` (one per-hkl vector per
        phase) is required semantics for the hot loop in lebail/pawley mode;
        at-rest callers omit it and read the buffers."""
        return self.background(values) + self.bragg_component(values, intensities)

    # ------------------------------------------------------------------
    # analytic Jacobian support
    # ------------------------------------------------------------------
    def coordinate_intensity_grad(self, ip: int, j: int, coeffs: np.ndarray,
                                  values: dict[str, float]
                                  ) -> list[np.ndarray] | None:
        """Per-line ∂intensity/∂u for a coordinate DOF u of atom j, phase ip.

        ``coeffs`` is the displacement direction ∂xyz/∂u — the DOF's column
        of the affine constraint block restricted to this atom's x, y, z
        rows.  Chains the analytic ∂|F|²/∂xyz (frozen op subsets,
        ``structure_factor.d_f2_d_xyz``) through the same scale ·
        multiplicity · line-weight · Lp factors as :meth:`phase_peaks`;
        positions and widths do not depend on coordinates, so the intensity
        scalar is the whole chain.  Le Bail intensities are extracted, not
        computed, so there is nothing to differentiate: returns ``None``.
        """
        return self._structural_intensity_grad(ip, j, coeffs, values, d_f2_d_xyz)

    def adp_intensity_grad(self, ip: int, j: int, coeffs: np.ndarray,
                           values: dict[str, float]) -> list[np.ndarray] | None:
        """Per-line ∂intensity/∂u for an anisotropic-ADP DOF of atom j.

        The exact analogue of :meth:`coordinate_intensity_grad` with
        ``coeffs`` the site-symmetry U^ij *pattern* (the DOF's column of the
        constraint block restricted to the atom's six U rows) — see
        ``structure_factor.d_f2_d_uaniso``.  ADPs, like coordinates, move only
        the intensity scalar, not the peak positions or widths.
        """
        return self._structural_intensity_grad(ip, j, coeffs, values, d_f2_d_uaniso)

    def _structural_intensity_grad(self, ip: int, j: int, coeffs: np.ndarray,
                                   values: dict[str, float], kernel
                                   ) -> list[np.ndarray] | None:
        if self.mode != "rietveld":
            return None
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.hkl, *cell)
        xyz, occ, biso, uaniso, astar = self._site_values(ip, values, cell)
        df2 = kernel(cp.reflections.hkl, d, cp.sites, xyz, occ, biso, j, uaniso, astar
                     ) @ np.asarray(coeffs, dtype=np.float64)
        d_base = values[f"phases.{ip}.scale"] * cp.reflections.multiplicity * df2
        # March-Dollase P multiplies the intensity and does not depend on the
        # coordinates/ADPs, so a structural move chains through it unchanged —
        # the analytic column must carry the same P the forward model folded in
        # (P ≡ None when off).  The r column itself comes from po_intensity_grad.
        P = self._po_factors(ip, values, cell)
        if P is not None:
            d_base = d_base * P
        # extinction couples |F|² into the intensity twice (as the prefactor
        # and through x ∝ |F|²), so a coordinate/ADP move chains through the
        # factor G = E + x·dE/dx (see model/extinction.py), applied
        # unconditionally — at ext=0, x=0 makes G exactly 1 (purity (b)).
        # Only these pure-analytic columns need it explicitly; the scale/occ/
        # biso/cell/extinction columns pick it up from the FD-of-phase_peaks
        # chain.
        ext = values[f"phases.{ip}.extinction"]
        f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                       xyz, occ, biso, uaniso, astar)
        vol = cell_volume(*cell)
        out = []
        for il, lam in enumerate(self.line_wavelengths):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = two_theta_deg(d, lam)
            col = d_base * w_line * lorentz_polarization(
                tt_bragg, values["instrument.polarization"])
            E, dEdx, x = sabine_extinction_and_dx(f2, lam, vol, tt_bragg, ext)
            col = col * (E + x * dEdx)
            out.append(col)
        return out

    def po_intensity_grad(self, ip: int, values: dict[str, float]
                          ) -> list[np.ndarray] | None:
        """Per-line ∂intensity/∂r for the March coefficient of phase ip.

        r enters the intensity only through the multiplier P_hkl(r) (Dollase
        1986), so ∂I/∂r = (∂P/∂r)·(intensity with P divided out) = (∂P/∂r)·base
        ·w·Lp·E — the same chain :meth:`phase_peaks` builds, with P replaced by
        ∂P/∂r.  ∂P/∂r is line-independent (the angles depend only on the cell),
        so it is computed once and reused across the emission lines.  Returns
        ``None`` when the phase has no PO block or outside Rietveld mode.
        """
        if self.mode != "rietveld":
            return None
        cp = self.phases[ip]
        if cp.po_axis is None:
            return None
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.hkl, *cell)
        xyz, occ, biso, uaniso, astar = self._site_values(ip, values, cell)
        f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                       xyz, occ, biso, uaniso, astar)
        gstar = reciprocal_metric_tensor(*cell)
        r = values[f"phases.{ip}.preferred_orientation.r"]
        _P, dP = march_dollase_and_dr(cp.po_members, cp.po_seg, cp.po_counts,
                                      cp.po_axis, gstar, r)
        d_base = values[f"phases.{ip}.scale"] * cp.reflections.multiplicity * f2 * dP
        # unconditional, like phase_peaks: E ≡ 1 exactly at ext=0 (purity (b))
        ext = values[f"phases.{ip}.extinction"]
        vol = cell_volume(*cell)
        out = []
        for il, lam in enumerate(self.line_wavelengths):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = two_theta_deg(d, lam)
            col = d_base * w_line * lorentz_polarization(
                tt_bragg, values["instrument.polarization"])
            col = col * sabine_extinction(f2, lam, vol, tt_bragg, ext)
            out.append(col)
        return out

    def scalar_chain_supported(self, path: str) -> bool:
        """Paths whose effect on y flows *only* through the per-peak scalars
        (position, Γ, η, intensity) — the analytic-column chain rule applies.

        Excluded: background coefficients (their own exact columns), the FCJ
        axial ratios (they move the quadrature nodes — see
        ``derivative_bases``), and anything unknown (falls back to FD).
        """
        if path.startswith("phases."):
            return True
        if path in ("instrument.zero_shift", "instrument.polarization"):
            return True
        if path.startswith("instrument.geometry.sample_"):
            return True
        if path.startswith("instrument.profile."):
            return True
        return path.startswith("instrument.source.lines.")

    def derivative_bases(self, values: dict[str, float],
                         intensities: list[np.ndarray] | None = None
                         ) -> "DerivativeBases":
        """Per-(phase, line, reflection) analytic profile-derivative bases.

        For each peak on its frozen window this computes Ω and the exact
        partials ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η (``pseudo_voigt_derivs``), and — for
        FCJ-smeared peaks — ∂Ω/∂(S/L), ∂Ω/∂(H/L).  A parameter column is then

            ∂y/∂p = Σ_k [ ∂I_k/∂p·Ω_k + I_k·(∂pos_k/∂p·∂Ω/∂pos
                          + ∂Γ_k/∂p·∂Ω/∂Γ + ∂η_k/∂p·∂Ω/∂η) ]

        where the per-reflection scalar derivatives come from cheap finite
        differences of :meth:`phase_peaks` (per-reflection work only; the
        expensive per-point part above is exact).  FCJ node positions/weights
        depend smoothly on (pos, S/L, H/L); their derivatives are finite-
        differenced on the node vectors themselves (≤64 numbers per peak).

        ``axial_ok`` is False when either axial ratio sits at ≤ 0 while FCJ
        nodes exist — the parameterisation is discontinuous there (FCJ's
        overlap trapezoid has zero height) and the axial columns must fall
        back to plain FD.
        """
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        h_pos, h_ax = 1e-5, 1e-7
        peaks_all: list[list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = []
        entries: list[list[tuple]] = []
        axial_ok = True
        for ip, cp in enumerate(self.phases):
            peaks = self.phase_peaks(
                ip, values, None if intensities is None else intensities[ip])
            peaks_all.append(peaks)
            rows: list[tuple] = []
            for il, (pos, gamma, eta, _intensity) in enumerate(peaks):
                for k in range(len(pos)):
                    i0, i1 = cp.win[il, k]
                    if i1 <= i0 or not np.isfinite(pos[k]):
                        continue
                    x = self.tt[i0:i1]
                    n_fcj = int(cp.fcj_n[il, k])
                    if n_fcj == 0:
                        pv, d_dx, d_dg, d_de = self._profile_derivs(
                            x - pos[k], float(gamma[k]), float(eta[k]))
                        rows.append((il, k, int(i0), int(i1),
                                     pv, -d_dx, d_dg, d_de, None, None))
                        continue
                    if sl <= 0.0 or hl <= 0.0:
                        axial_ok = False
                    phi, om = fcj_offsets_weights(float(pos[k]), sl, hl, n_fcj)
                    pv, d_dx, d_dg, d_de = self._profile_derivs(
                        x[None, :] - phi[:, None], float(gamma[k]), float(eta[k]))
                    omega = om @ pv
                    d_gamma = om @ d_dg
                    d_eta = om @ d_de

                    def node_diff(phi1, om1):
                        if len(phi1) != len(phi):
                            return None  # crossed the symmetric fallback
                        return (phi1 - phi), (om1 - om)

                    d = node_diff(*fcj_offsets_weights(float(pos[k]) + h_pos, sl, hl, n_fcj))
                    if d is None:
                        d_pos = -(om @ d_dx)  # pure-translation approximation
                    else:
                        dphi, dom = d[0] / h_pos, d[1] / h_pos
                        d_pos = (dom @ pv) - ((om * dphi) @ d_dx)
                    d_sl = d_hl = None
                    if axial_ok:
                        d = node_diff(*fcj_offsets_weights(float(pos[k]), sl + h_ax, hl, n_fcj))
                        if d is not None:
                            dphi, dom = d[0] / h_ax, d[1] / h_ax
                            d_sl = (dom @ pv) - ((om * dphi) @ d_dx)
                        d = node_diff(*fcj_offsets_weights(float(pos[k]), sl, hl + h_ax, n_fcj))
                        if d is not None:
                            dphi, dom = d[0] / h_ax, d[1] / h_ax
                            d_hl = (dom @ pv) - ((om * dphi) @ d_dx)
                    rows.append((il, k, int(i0), int(i1),
                                 omega, d_pos, d_gamma, d_eta, d_sl, d_hl))
            entries.append(rows)
        return DerivativeBases(entries=entries, peaks=peaks_all, axial_ok=axial_ok)

    # ------------------------------------------------------------------
    def lebail_update(self, values: dict[str, float], n_cycles: int = 1) -> None:
        """Refresh per-hkl intensities by observed-intensity partitioning.

        Per-hkl intensities are shared across emission lines: reflection k
        contributes through every line l with profile mass w_l·Ω_lk, so

            I_k ← Σ_l Σ_i [I_k·w_l·Ω_lk,i / y_bragg,i] · max(y_obs,i − y_bkg,i, 0)
                  / Σ_l w_l·Σ_i Ω_lk,i

        which is a fixed point when y_obs = y_calc (Le Bail et al., 1988).  This
        *is* the Le Bail step; in Pawley mode it is used only once, to seed the
        intensity block before the first least-squares run (never between runs,
        which would overwrite the refined values).

        Runs *between* least-squares solves, so it may commit to the at-rest
        buffers — but it threads the intensity vectors functionally through its
        own cycles and writes each phase's buffer exactly once at the end.
        """
        if self.mode not in ("lebail", "pawley"):
            raise RuntimeError("lebail_update on a Rietveld-mode model")
        xp = get_backend()
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        intens = [np.asarray(cp.hkl_intensity, dtype=np.float64) for cp in self.phases]
        for _ in range(n_cycles):
            bkg = self.background(values)
            net = xp.maximum(self.y_obs - bkg, 0.0)
            for ip, cp in enumerate(self.phases):
                peaks = self.phase_peaks(ip, values, intens[ip])
                n = len(cp.reflections)
                n_lines = len(self.line_wavelengths)
                profs: list[list[np.ndarray | None]] = []
                y_bragg = xp.zeros_like(self.tt)
                for il, (pos, gamma, eta, intensity) in enumerate(peaks):
                    row: list[np.ndarray | None] = []
                    for k in range(n):
                        om = self._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k], sl, hl)
                        row.append(om)
                        if om is not None:
                            i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                            y_bragg = xp.window_add(y_bragg, i0, i1, intensity[k] * om)
                    profs.append(row)
                new_int = intens[ip].copy()
                for k in range(n):
                    num = 0.0
                    den = 0.0
                    for il in range(n_lines):
                        om = profs[il][k]
                        if om is None or om.sum() <= 0:
                            continue
                        i0, i1 = cp.win[il, k]
                        denom = y_bragg[i0:i1]
                        good = denom > 1e-12
                        if not np.any(good):
                            continue
                        intensity = peaks[il][3]
                        share = np.zeros_like(om)
                        share[good] = intensity[k] * om[good] / denom[good]
                        w_line = values[f"instrument.source.lines.{il}.weight"]
                        num += float((share * net[i0:i1]).sum())
                        den += w_line * float(om.sum())
                    if den > 0.0:
                        new_int[k] = num / den
                intens[ip] = np.maximum(new_int, 1e-10)
        for cp, vec in zip(self.phases, intens, strict=True):
            cp.hkl_intensity = vec

    # ------------------------------------------------------------------
    # Pawley intensity block (per-hkl intensities as free parameters)
    # ------------------------------------------------------------------
    def pawley_x0(self) -> np.ndarray:
        """Current per-hkl intensities, flat in phase order — the block's θ₀."""
        return np.concatenate([np.asarray(cp.hkl_intensity, dtype=np.float64)
                               for cp in self.phases]) if self.phases else np.zeros(0)

    def pawley_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Intensities are bounded ≥ 0 (identity transform, TRF-reflected).

        Positivity is a box, not a restraint: a single reflection's intensity
        does not couple to the others, so unlike the ADP positive-definite cone
        it can be enforced component-wise.  Keeping the transform identity is
        what makes the block's Jacobian columns exactly linear.
        """
        n = self.pawley.n if self.pawley is not None else 0
        return np.zeros(n), np.full(n, np.inf)

    def split_pawley_intensities(self, vec: np.ndarray) -> list[np.ndarray]:
        """Per-phase slices of a flat intensity vector (views, no buffer I/O).

        The hot-loop counterpart of the buffers: the residual/Jacobian
        closures split the θ tail with this and pass the slices through
        ``evaluate``/``derivative_bases``, never touching ``hkl_intensity``.
        """
        return [vec[a:b] for (a, b) in self.pawley.phase_slices]

    def set_pawley_intensities(self, vec: np.ndarray) -> None:
        """Commit a flat intensity vector to the at-rest per-phase buffers.

        Called once per solve, after TRF returns — never from inside the
        residual (purity contract).
        """
        for cp, (a, b) in zip(self.phases, self.pawley.phase_slices, strict=True):
            cp.hkl_intensity = np.array(vec[a:b], dtype=np.float64)

    def pawley_restraint_residual(self, vec: np.ndarray) -> np.ndarray | None:
        """√λ·R·I overlap-restraint rows appended to the residual (or None)."""
        if self.pawley is None or self.pawley.restraint is None:
            return None
        return self.pawley.restraint @ vec

    def build_pawley_restraint(self, lam: float = PAWLEY_OVERLAP_LAMBDA) -> None:
        """Build the equal-split restraint rows for the current intensities.

        One row per member of every overlapped group: √λ/s·(δ_kj − 1/n) over the
        group, where s is the group's current mean intensity.  The rows sum to
        zero, so they penalise deviations of the *split* from an equal partition
        while leaving the group *sum* (the data-determined quantity) free.  Run
        after the intensities are seeded/carried so s reflects a realistic
        scale; constant during the least-squares run, like the background
        penalty.
        """
        pb = self.pawley
        if pb is None or not pb.groups:
            return
        intens = self.pawley_x0()
        rows: list[np.ndarray] = []
        for g in pb.groups:
            s = max(float(np.mean(intens[g])), 1e-10)
            n = len(g)
            for k in g:
                row = np.zeros(pb.n, dtype=np.float64)
                for j in g:
                    row[j] = (np.sqrt(lam) / s) * ((1.0 if j == k else 0.0) - 1.0 / n)
                rows.append(row)
        pb.restraint = np.array(rows, dtype=np.float64) if rows else None


@dataclass
class PawleyBlock:
    """Per-hkl intensities refined as free parameters (Pawley, 1981, J. Appl.
    Cryst. 14, 357).

    The intensities themselves live in the per-phase ``hkl_intensity`` buffers,
    not in the ParameterTable (``RefinementState.free_paths`` stays a table of
    named scalars — see ``schemas/history.ReflectionState``); this block is the
    seam that lets ``run_least_squares`` append them to θ.  ``phase_slices`` maps
    each phase to its contiguous slice of the flat intensity vector, concatenated
    in phase order.

    Overlapped reflections make the intensity block of JᵀJ near-singular — at
    exact overlap the split between two intensities is unconstrained by the data
    and the naive pseudo-inverse reports a *spuriously tight* esd for it.
    ``restraint`` (built by :meth:`CompiledModel.build_pawley_restraint`) holds
    the √λ-scaled equal-split rows that regularise the split so the covariance
    reports a large-but-honest esd instead; ``groups`` lists the flat-index
    members of each overlapped group so those splits can be flagged unresolved.
    """

    n: int                                   # total intensities across phases
    phase_slices: list[tuple[int, int]]      # (start, stop) into the flat vector
    groups: list[list[int]]                  # overlapped groups (flat idx), size ≥ 2
    restraint: np.ndarray | None = None      # (n_rows, n) √λ-scaled restraint rows
    stderr: np.ndarray | None = None         # per-intensity esd, filled post-solve


@dataclass
class DerivativeBases:
    """Analytic profile-derivative bases (see ``CompiledModel.derivative_bases``).

    ``entries[ip]`` holds tuples ``(il, k, i0, i1, Ω, ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η,
    ∂Ω/∂sl, ∂Ω/∂hl)`` per visible peak of phase ``ip``; the last two are None
    for symmetric peaks.  ``peaks[ip]`` caches ``phase_peaks(ip, values)`` at
    the expansion point.  These bases also feed the FitReport Layer-1 misfit
    attribution (same expansion, different right-hand side).
    """

    entries: list[list[tuple]]
    peaks: list[list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]]
    axial_ok: bool


def compile_model(structure: Structure, instrument: Instrument, pattern: PatternData,
                  *, mode: Mode = "rietveld",
                  two_theta_limits: tuple[float, float] | None = None,
                  free_paths: set[str] | None = None) -> CompiledModel:
    """Freeze reflection lists, orbits, windows and FCJ nodes for one stage.

    ``free_paths`` (the parameters the coming stage will refine) only affects
    *sizing* decisions: when the axial parameters are free, FCJ nodes are
    allocated even if their current values are still zero.
    """
    mask = pattern.in_range_mask()
    tt_all, y_all, s_all = pattern.tt(), pattern.y(), pattern.sig()
    if two_theta_limits is not None:
        lo, hi = two_theta_limits
        mask &= (tt_all >= lo) & (tt_all <= hi)
    tt, y_obs, sigma = tt_all[mask], y_all[mask], s_all[mask]
    if len(tt) < 10:
        raise ValueError("fewer than 10 points remain in the fit range")
    tt_min, tt_max = float(tt[0]), float(tt[-1])

    lams = tuple(line.wavelength for line in instrument.source.lines)
    lam_gen = min(lams)  # smallest λ → smallest 2θ → largest d-sphere needed
    zero = instrument.zero_shift.value
    geom = instrument.geometry

    # FCJ sizing values (floored when the axial parameters are about to refine)
    free_paths = free_paths or set()
    axial_free = ("instrument.geometry.axial_sl" in free_paths
                  or "instrument.geometry.axial_hl" in free_paths)
    sl_eff = geom.axial_sl.value
    hl_eff = geom.axial_hl.value
    if axial_free:
        sl_eff = max(sl_eff, AXIAL_SIZING_FLOOR)
        hl_eff = max(hl_eff, AXIAL_SIZING_FLOOR)
    fcj_on = sl_eff > 0.0 and hl_eff > 0.0

    # a reflection is kept if *any* line lands in range: the min-λ line sits
    # lowest, so generate with λ_min and translate the low-2θ cutoff from the
    # max-λ line's frame (same d ⇒ sinθ ∝ λ)
    lo_eff = max(tt_min - zero - 0.5, 0.1)
    hi_eff = tt_max - zero + 0.5
    sin_lo = np.sin(np.radians(lo_eff / 2.0)) * lam_gen / max(lams)
    gen_min = max(2.0 * np.degrees(np.arcsin(min(sin_lo, 1.0))), 0.05)

    def _shift_est(theta: np.ndarray, tt_bragg: np.ndarray) -> np.ndarray | float:
        shift = zero
        if geom.kind == "bragg_brentano":
            s = geom.sample_displacement.value
            if s != 0.0:
                shift = shift + displacement_shift_deg(theta, s, geom.goniometer_radius_mm)
            t = geom.sample_transparency.value
            if t != 0.0:
                shift = shift + transparency_shift_deg(tt_bragg, t)
        return shift

    phases: list[CompiledPhase] = []
    for phase in structure.phases:
        cell = phase.cell.lengths_angles()
        refl = generate_reflections(phase.space_group, cell, lam_gen,
                                    two_theta_max=hi_eff, two_theta_min=gen_min)
        sites = compile_phase_sites(phase)

        n = len(refl)
        n_lines = len(lams)
        win = np.zeros((n_lines, n, 2), dtype=np.int64)
        fcj_n = np.zeros((n_lines, n), dtype=np.int64)
        tt_primary = fwhm_primary = None
        for il, lam in enumerate(lams):
            tt_bragg = refl.two_theta(cell, lam)
            theta = 0.5 * tt_bragg
            pos = tt_bragg + _shift_est(theta, tt_bragg)
            g_est = gaussian_fwhm(theta, instrument.profile.u.value,
                                  instrument.profile.v.value, instrument.profile.w.value,
                                  phase.gauss_size.value, phase.gauss_strain.value)
            l_est = lorentzian_fwhm(theta,
                                    instrument.profile.x.value + phase.lor_size.value,
                                    instrument.profile.y.value + phase.lor_strain.value)
            # TCHZ combined Γ is a compile-time width proxy for window sizing
            # and FCJ node counts under *both* shapes: it tracks the true Voigt
            # FWHM to ~1 % (that is what the TCH quintic is fit to), and the
            # 30·FWHM window margin dwarfs any residual difference.
            gamma_est, _ = tch_gamma_eta(g_est, l_est)
            if il == 0:  # primary line drives Pawley overlap grouping
                tt_primary, fwhm_primary = pos.copy(), gamma_est.copy()
            half = WINDOW_FWHM_MULT * gamma_est + WINDOW_MIN_DEG
            if fcj_on:
                half = half + fcj_extent_deg(pos, sl_eff, hl_eff)
            valid = np.isfinite(pos)
            pos_v = np.where(valid, pos, 0.0)
            half_v = np.where(valid, half, 0.0)
            i0 = np.searchsorted(tt, pos_v - half_v, side="left")
            i1 = np.searchsorted(tt, pos_v + half_v, side="right")
            i0[~valid] = 0
            i1[~valid] = 0
            win[il, :, 0], win[il, :, 1] = i0, i1
            if fcj_on:
                for k in range(n):
                    if valid[k] and i1[k] > i0[k]:
                        fcj_n[il, k] = fcj_node_count(float(pos[k]), float(gamma_est[k]),
                                                      sl_eff, hl_eff)

        cp = CompiledPhase(reflections=refl, sites=sites, win=win, fcj_n=fcj_n)
        if mode in ("lebail", "pawley"):
            cp.hkl_intensity = np.full(n, max(float(np.median(y_obs)), 1.0))
        if mode == "pawley":
            cp.tt_primary, cp.fwhm_primary = tt_primary, fwhm_primary
        # March-Dollase preferred orientation acts on *calculated* structure-
        # factor intensities, so it is a Rietveld-mode correction only — Le Bail
        # and Pawley intensities are empirical and would absorb it.  Freeze the
        # symmetry orbit of each reflection here; the angles follow the cell.
        if mode == "rietveld" and phase.preferred_orientation is not None and n:
            orbits = reflection_orbits(phase.space_group, refl.hkl)
            cp.po_axis = np.array(phase.preferred_orientation.axis, dtype=np.int64)
            cp.po_members, cp.po_seg, cp.po_counts = orbit_layout(orbits)
        phases.append(cp)

    # background compilation — always linear: paths + design rows (+ penalty)
    bkg = instrument.background
    fixed = None
    penalty = None
    if isinstance(bkg, BackgroundChebyshev):
        n_cheb = len(bkg.coefficients)
        bkg_paths = tuple(f"instrument.background.c{n}" for n in range(n_cheb))
        design = chebyshev_design_matrix(tt, n_cheb, tt_min, tt_max)
    elif isinstance(bkg, BackgroundFixedPlusChebyshev):
        n_cheb = len(bkg.chebyshev.coefficients)
        bkg_paths = tuple(f"instrument.background.c{n}" for n in range(n_cheb))
        design = chebyshev_design_matrix(tt, n_cheb, tt_min, tt_max)
        fixed = interpolate_fixed(tt, np.asarray(bkg.fixed_two_theta),
                                  np.asarray(bkg.fixed_intensity))
    elif isinstance(bkg, BackgroundPSpline):
        n_coef = len(bkg.coefficients)
        bkg_paths = tuple(f"instrument.background.c{n}" for n in range(n_coef)) \
            + ("instrument.background.air",)
        spline = bspline_design_matrix(tt, np.asarray(bkg.breakpoints))
        with np.errstate(divide="ignore"):
            air_row = 1.0 / np.maximum(tt, 1e-3)
        design = np.vstack([spline, air_row[None, :]])
        if bkg.lambda_smooth > 0.0 and n_coef > 2:
            d2 = second_difference_matrix(n_coef)
            penalty = np.hstack([np.sqrt(bkg.lambda_smooth) * d2,
                                 np.zeros((d2.shape[0], 1))])  # air term unpenalised
    else:  # pragma: no cover - schema exhausts the union
        raise TypeError(f"unsupported background model {type(bkg).__name__}")

    pawley = _build_pawley_block(phases) if mode == "pawley" else None

    return CompiledModel(
        tt=tt, y_obs=y_obs, sigma=sigma, tt_min=tt_min, tt_max=tt_max,
        wavelength=instrument.source.primary_wavelength,
        line_wavelengths=lams,
        geometry_kind=geom.kind, radius_mm=geom.goniometer_radius_mm,
        mode=mode, phases=phases,
        fixed_background=fixed,
        bkg_paths=bkg_paths, bkg_design=design, bkg_penalty=penalty,
        shape=instrument.profile.shape,
        pawley=pawley,
    )


def _overlap_groups(tt: np.ndarray, fwhm: np.ndarray) -> list[list[int]]:
    """Contiguous groups of reflections whose primary-line peaks overlap.

    Reflections arrive sorted by descending d (ascending 2θ).  Adjacent peaks k,
    k+1 join a group when their centre spacing is below
    ``PAWLEY_OVERLAP_FWHM_FRAC`` of their mean FWHM — the point past which the
    least squares cannot cleanly apportion intensity between them.  Non-finite
    positions break the chain.  Returns only groups of size ≥ 2 (singletons need
    no restraint), as lists of indices into the reflection list.
    """
    groups: list[list[int]] = []
    run = [0] if len(tt) else []
    for k in range(1, len(tt)):
        close = (np.isfinite(tt[k]) and np.isfinite(tt[k - 1])
                 and (tt[k] - tt[k - 1])
                 < PAWLEY_OVERLAP_FWHM_FRAC * 0.5 * (fwhm[k] + fwhm[k - 1]))
        if close:
            run.append(k)
        else:
            if len(run) >= 2:
                groups.append(run)
            run = [k]
    if len(run) >= 2:
        groups.append(run)
    return groups


def _build_pawley_block(phases: list[CompiledPhase]) -> PawleyBlock:
    """Assemble the flat intensity layout and overlapped-group list.

    The restraint rows themselves are built later (once the intensities are
    seeded to a realistic scale) by ``CompiledModel.build_pawley_restraint``.
    """
    phase_slices: list[tuple[int, int]] = []
    groups: list[list[int]] = []
    offset = 0
    for cp in phases:
        n = len(cp.reflections)
        phase_slices.append((offset, offset + n))
        if cp.tt_primary is not None and n:
            for g in _overlap_groups(cp.tt_primary, cp.fwhm_primary):
                groups.append([offset + k for k in g])
        offset += n
    return PawleyBlock(n=offset, phase_slices=phase_slices, groups=groups)
