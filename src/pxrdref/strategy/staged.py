"""Minimal staged refinement runner.

Encodes the IUCr-guideline practice of turning parameter groups on
cumulatively in a stable order (McCusker, Von Dreele, Cox, Louër & Scardi,
1999, J. Appl. Cryst. 32, 36): scale + background first, then peak positions
(zero/cell), then profile widths.  Each stage runs the bounded least squares
to convergence before the next group is freed; the reflection list and
evaluation windows are regenerated between stages (the differentiability
invariant — they stay frozen *within* a stage).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: ``phases.i.atoms.j.u11`` … — the stored anisotropic components, grouped by
#: site for the positive-definiteness guard.
_ADP_COMPONENT = re.compile(r"^(phases\.\d+\.atoms\.\d+)\.u(11|22|33|12|13|23)$")
_U_ORDER = {"11": 0, "22": 1, "33": 2, "12": 3, "13": 4, "23": 5}

#: The displacement-parameter stage frees whichever representation each site
#: actually uses.  Both globs are always safe: an isotropic site has no
#: ``adp.k`` entries, and an anisotropic one has its ``biso`` locked, so
#: neither can free a parameter that does not reach the model.
_DISPLACEMENT_GLOBS = ["phases.*.atoms.*.biso", "phases.*.atoms.*.adp.*"]


@dataclass
class Stage:
    name: str
    turn_on: list[str]  # path globs, e.g. "phases.*.cell.*"
    max_iter: int = 100
    lebail_cycles: int = 3  # intensity-partitioning refreshes (lebail mode)
    #: lift any softplus-bounded parameter this stage frees off the exact-zero
    #: floor to this value before solving, so TRF sees a live gradient (the
    #: softplus map's slope at p≈0 is ≈0, so a coefficient starting at 0 would
    #: never move).  0 = no seed.  The extinction stage uses it; unlike the FCJ
    #: AXIAL_SIZING_FLOOR (an identity-transform bound, movable off zero on its
    #: own) a softplus coefficient genuinely needs the value nudge.
    seed: float = 0.0
    #: microstrain (ppm of ΔM/M) to put a freed but still all-zero Stephens
    #: block on before solving.  ``seed`` cannot serve: the S_HKL DOFs are
    #: identity-transform, and their pathology at zero is the *exploding*
    #: gradient of √Σ rather than the softplus's dead one.  0 = no seed.
    strain_seed: float = 0.0


@dataclass
class RefinementPlan:
    stages: list[Stage]
    correlation_guard: float = 0.98

    @classmethod
    def mccusker_default(cls) -> "RefinementPlan":
        """Default staged plan for a Rietveld run (McCusker et al., 1999)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def mccusker_structural(cls) -> "RefinementPlan":
        """The McCusker order continued into the structural parameters:
        atomic coordinates once the profile is stable, then displacement
        parameters.  Coordinates refine as site-symmetry DOFs
        (``phases.*.atoms.*.dof.*`` — WP-0301 constraint block; a special
        position contributes only its allowed directions, a fully fixed one
        contributes none, so the glob is always safe).  The displacement
        stage frees ``biso`` on isotropic sites and the ``adp.*`` patterns on
        anisotropic ones, whichever each site declares.  Kept separate from
        :meth:`mccusker_default` so profile-only workflows never free
        structural parameters by accident."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("coordinates", ["phases.*.atoms.*.dof.*"]),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
            # March-Dollase preferred orientation (WP-0307) turns on *after* the
            # displacement stage: r, occupancies and ADPs all rescale intensity
            # in Q-dependent ways, so letting the structure settle first leaves
            # PO with its own axis-angle signature to fit.  The glob matches only
            # phases that declared a PO block; r ≡ 1 is the identity, so a start
            # from 1.0 perturbs nothing until the data pull it off.
            Stage("preferred_orientation", ["phases.*.preferred_orientation.r"]),
            # secondary extinction (WP-0506) comes *after* the displacement
            # stage on purpose: ext, Biso and the ADPs all attenuate high-Q
            # intensity, so letting the structure/ADPs settle first leaves
            # extinction with only its (different, low-angle-weighted)
            # signature to fit.  The coefficient starts at exactly 0 on the
            # softplus floor, so the stage seeds it to lift TRF off the zero.
            Stage("extinction", ["phases.*.extinction"], seed=1e-3),
        ])

    @classmethod
    def lab_bragg_brentano(cls) -> "RefinementPlan":
        """Lab flat-plate plan: adds sample displacement (with zero), then the
        Kα2/Kα1 intensity ratio and FCJ axial-divergence parameters last —
        the McCusker ordering extended by the v0.2 lab-instrument physics.
        Sample transparency stays fixed (free it explicitly for low-absorbing
        samples)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero_disp", ["instrument.zero_shift",
                                "instrument.geometry.sample_displacement"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("lines_axial", ["instrument.source.lines.*.weight",
                                  "instrument.geometry.axial_sl",
                                  "instrument.geometry.axial_hl"]),
        ])

    @classmethod
    def lab_calibrate(cls) -> "RefinementPlan":
        """Calibrate the instrument on a **certified line-profile standard**
        (NIST SRM 660c LaB6): the certified cell is *held fixed* — that is
        what pins the dispersion axis and decorrelates the otherwise-sloppy
        {zero (const), displacement (cosθ), cell (tanθ)} triple — while zero,
        displacement, the resolution function, the Kα2 ratio and the axial
        ratios refine.  Export the result with ``save_instrument_profile``;
        refine unknowns against it with the ``lab_sample_refine`` plan."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero_disp", ["instrument.zero_shift",
                                "instrument.geometry.sample_displacement"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("lines_axial", ["instrument.source.lines.*.weight",
                                  "instrument.geometry.axial_sl",
                                  "instrument.geometry.axial_hl"]),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
        ])

    @classmethod
    def lab_sample_refine(cls) -> "RefinementPlan":
        """Refine a *sample* against a **calibrated, frozen instrument**
        (the calibrate-on-standard → freeze → refine-sample workflow; see
        ``pxrdref.io.instrument_profile``).

        Only sample-side parameters move: scale/background, specimen
        displacement (a property of the mount, not the instrument), cell,
        the four sample broadening terms (Lorentzian + Gaussian size/strain
        — the instrument U V W X Y stay at their calibrated values), then
        Biso.  Never frees zero, axial ratios or emission-line weights."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("disp", ["instrument.geometry.sample_displacement"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("sample_profile", ["phases.*.lor_size", "phases.*.lor_strain",
                                     "phases.*.gauss_size", "phases.*.gauss_strain"]),
            # Stephens anisotropic strain (WP-0503) comes *after* the isotropic
            # sample-broadening stage: the block's isotropic direction is the
            # lor_strain column itself, so letting the average width settle
            # first leaves the S_HKL patterns with only the hkl-*directional*
            # residual to fit.  The glob matches only phases that declared a
            # microstrain block (which also locks their lor_strain), and the
            # seed puts an all-zero block on the isotropic ray — Λ ∝ √Σ has
            # unbounded slope at Σ = 0.
            Stage("microstrain", ["phases.*.microstrain.dof.*"], strain_seed=1000.0),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
        ])

    @classmethod
    def profile_only(cls) -> "RefinementPlan":
        """Le Bail-style plan: no structural parameters exist to free."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def pawley_default(cls) -> "RefinementPlan":
        """Pawley whole-pattern plan: cell + profile, same order as
        :meth:`profile_only`.  The per-hkl intensities are *not* named globs —
        they are refined as an implicit block every stage (see
        ``model.forward.PawleyBlock``), so no ``turn_on`` frees them."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])


PLAN_PRESETS = {
    "mccusker_default": RefinementPlan.mccusker_default,
    "mccusker_structural": RefinementPlan.mccusker_structural,
    "lab_bragg_brentano": RefinementPlan.lab_bragg_brentano,
    "lab_calibrate": RefinementPlan.lab_calibrate,
    "lab_sample_refine": RefinementPlan.lab_sample_refine,
    "profile_only": RefinementPlan.profile_only,
    "pawley_default": RefinementPlan.pawley_default,
}


@dataclass
class GuardReport:
    high_correlations: list[str] = field(default_factory=list)
    at_bounds: list[str] = field(default_factory=list)
    # structural parameters the background block could largely reproduce —
    # the background-eats-the-structure failure mode, measured as a multiple
    # correlation R² rather than a pairwise ρ (see check_guards)
    background_correlations: list[str] = field(default_factory=list)
    # anisotropic displacement tensors that are no longer ellipsoids
    nonpositive_adps: list[str] = field(default_factory=list)
    # phases whose Stephens strain coefficients have left the physical cone
    nonpositive_strain: list[str] = field(default_factory=list)


#: R² beyond which the background block is reported as able to imitate a
#: structural parameter (see ``optimize.statistics.background_absorption``).
#: Measured separation: sane backgrounds (Chebyshev-6, the default 8°-knot
#: penalized spline) sit at 0.01-0.03 even against broad peaks, while a
#: 1°-knot unpenalized spline reaches 0.46.
BACKGROUND_ABSORPTION_GUARD = 0.25


def check_adp_positive_definite(table) -> list[str]:
    """Anisotropic sites whose U tensor is not positive definite.

    An unconstrained U can leave the physical cone, and the resulting
    Debye-Waller factor *grows* without bound along the offending direction
    as |h| increases — the fit does not merely become wrong, it diverges at
    high Q.  The test runs on the stored CIF U^ij matrix rather than on
    U_cart: the two are related by a congruence, so by Sylvester's law of
    inertia the eigenvalue *signs* are the same and no cell is needed here
    (magnitudes would need one — see ``crystallography.adp``).
    """
    import numpy as np

    from ..crystallography.adp import min_eigenvalue

    values = {e.path: e.value for e in table.entries}
    sites: dict[str, list[float]] = {}
    for e in table.entries:
        m = _ADP_COMPONENT.match(e.path)
        if m:
            sites.setdefault(m.group(1), [np.nan] * 6)
            sites[m.group(1)][_U_ORDER[m.group(2)]] = values[e.path]
    out = []
    for base, u6 in sorted(sites.items()):
        if not np.isnan(u6).any() and min_eigenvalue(u6) <= 0.0:
            out.append(f"{base} (min eigenvalue {min_eigenvalue(u6):+.2e} Å²)")
    return out


def check_stephens_positive(table, model) -> list[str]:
    """Phases whose Stephens σ²(M) is non-positive on some fitted reflection.

    σ² is a variance, so a negative value is not a large anisotropy but an
    unphysical set of coefficients — the width law's √ has nothing to take and
    the model quietly reports zero broadening for that direction.  The
    constraint is a *cone* coupling all fifteen coefficients (like ADP positive
    definiteness), which is why it cannot be a box bound and has to be a guard.

    Tested on the frozen reflection list rather than over all integer hkl: the
    cone condition off the measured directions is unobservable, and flagging it
    would be a claim the data cannot support.  Needs the compiled model for
    that list, so it returns ``[]`` when none is supplied.
    """
    import numpy as np

    from ..crystallography.stephens import S_NAMES, sigma2_m

    if model is None:
        return []
    values = {e.path: e.value for e in table.entries}
    out: list[str] = []
    for ip, cp in enumerate(model.phases):
        if cp.strain_monomials is None:
            continue
        base = f"phases.{ip}.microstrain"
        s = np.array([values.get(f"{base}.{n}", 0.0) for n in S_NAMES])
        sigma2 = np.asarray(sigma2_m(cp.strain_monomials, s))
        bad = sigma2 <= 0.0
        if bad.any():
            k = int(np.argmin(sigma2))
            hkl = tuple(int(v) for v in cp.reflections.hkl[k])
            out.append(f"{base} ({int(bad.sum())} of {len(sigma2)} reflections, "
                       f"worst σ²(M) {sigma2[k]:+.2e} at {hkl})")
    return out


def check_guards(table, outcome, threshold: float,
                 background_threshold: float = BACKGROUND_ABSORPTION_GUARD,
                 model=None) -> GuardReport:
    """Correlation, bound, background-absorption, ADP- and strain-shape guards."""
    import numpy as np

    from ..optimize.statistics import background_absorption

    report = GuardReport()
    report.nonpositive_adps = check_adp_positive_definite(table)
    report.nonpositive_strain = check_stephens_positive(table, model)
    free = table.free_paths

    if outcome.correlation is not None and len(free) > 1:
        corr = np.asarray(outcome.correlation)
        for i in range(len(free)):
            for j in range(i + 1, len(free)):
                if abs(corr[i, j]) > threshold:
                    report.high_correlations.append(
                        f"{free[i]} ~ {free[j]} (ρ={corr[i, j]:+.3f})")

    if outcome.jac is not None and len(free) > 1:
        for path, r2 in sorted(background_absorption(outcome.jac, free).items(),
                               key=lambda kv: -kv[1]):
            if r2 > background_threshold:
                report.background_correlations.append(f"{path} (R²={r2:.2f})")

    lo, hi = table.bounds()
    for k, path in enumerate(free):
        t = outcome.theta[k]
        span = hi[k] - lo[k]
        tol = 1e-8 * (span if np.isfinite(span) else 1.0)
        if (np.isfinite(lo[k]) and t - lo[k] <= tol) or (np.isfinite(hi[k]) and hi[k] - t <= tol):
            report.at_bounds.append(path)
    return report
