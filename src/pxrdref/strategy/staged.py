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


def check_guards(table, outcome, threshold: float,
                 background_threshold: float = BACKGROUND_ABSORPTION_GUARD
                 ) -> GuardReport:
    """Correlation, bound, background-absorption and ADP-shape guards."""
    import numpy as np

    from ..optimize.statistics import background_absorption

    report = GuardReport()
    report.nonpositive_adps = check_adp_positive_definite(table)
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
