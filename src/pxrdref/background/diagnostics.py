"""Model-free pattern diagnostics — the structured object an agent (or the
background auto-selection) reasons over before any refinement is attempted.

Everything is computed from the raw pattern alone; nothing here linearises or
assumes a structural model.  Baseline *shape* questions (amorphous hump, air
scatter) are answered from a **rolling low-quantile envelope** rather than an
arPLS baseline: the answers must not depend on a smoothing λ that is itself
being chosen (arPLS stiff enough to be safe under peaks is too stiff to
follow a genuine hump — measured, which is why the envelope is used here).
Wavelength-dependent contamination checks (Kβ ghosts, W Lα from an aging
tube) run only when the primary wavelength is supplied.
"""

from __future__ import annotations

import numpy as np
from pydantic import Field
from scipy.signal import find_peaks

from ..schemas.common import Base
from ..schemas.pattern import PatternData
from .models import chebyshev_design_matrix

#: Kβ1,3 wavelengths (Å) per anode, for contamination checks only — Kβ is never
#: a modelled emission line (see ``schemas.instrument._RADIATIONS``).  Same
#: source and column as the Kα table it is keyed against: the NIST X-ray
#: Transition Energies Database (SRD 128) direct-experimental KM3.  For the 3d
#: metals that column reports the KM2,3 *blend*, which is what a check wants;
#: for Mo and Ag it resolves Kβ1 (KM3) from Kβ3 (KM2, half the weight), and we
#: take Kβ1 — the 3e-4 relative gap between them is ~0.01° 2θ, an order inside
#: the matching window below.
_KBETA: dict[str, float] = {
    "CrKa": 2.0848810,
    "FeKa": 1.7566040,
    "CoKa": 1.6208260,
    "CuKa": 1.3922340,
    "MoKa": 0.632303,
    "AgKa": 0.4970817,
}

#: W Lα1 (Bearden 1967, Rev. Mod. Phys. 39, 78).  Tungsten reaches the target
#: by subliming off the *filament*, so unlike Kβ this line is a property of the
#: tube's age rather than of the anode material, and is checked for every anode.
_W_LA1 = 1.4763800

#: How close the pattern's wavelength must be to an anode's Kα1 to be treated
#: as that anode.  The closest pair in the table is Fe/Co, 0.147 Å apart, so
#: this is unambiguous by two orders.
_ANODE_MATCH_TOL = 0.01


class ContaminationFlag(Base):
    """A weak peak consistent with a known contamination line of a strong one."""

    kind: str                  # "kbeta" | "tungsten_la"
    two_theta: float           # where the ghost sits
    parent_two_theta: float    # the strong Kα parent reflection
    intensity_ratio: float     # ghost/parent net height


class PatternDiagnostics(Base):
    """Agent-readable observations about a raw pattern (no model involved).

    * ``peak_fraction`` — fraction of channels more than 3σ above the
      envelope: how much of the pattern is peak rather than background.
    * ``peak_density_per_deg`` — resolved-peak count per degree 2θ; dense
      patterns (≳2/deg) favour stiff baselines and low background order.
    * ``signal_to_background`` — near-maximum net signal (99.9th percentile)
      over the median background level.
    * ``air_scatter_gain`` — fraction of the cubic-fit residual variance of
      the background envelope explained by adding a 1/(2θ) column, i.e. a
      nested-model test for the low-angle air-scatter rise.  ≳0.3 triggers
      the 1/x background term.
    * ``amorphous_hump_score`` — RMS residual of the envelope *after* the
      cubic **and** the 1/x term, relative to the median level: what is left
      is genuinely broad non-polynomial structure (amorphous content,
      capillary glass).  ≳0.05 calls for a more flexible background.
    * ``contamination`` — Kβ / W Lα ghost candidates.  Needs ``wavelength``,
      and an *empty list means nothing was flagged or nothing was checked*:
      the Kβ position is anode-specific, so a wavelength that matches no
      tabulated Kα1 (:func:`identify_anode`) is silently skipped.
    * ``baseline_lambda`` — the arPLS stiffness the whiteness rule selects
      for this pattern (:func:`pxrdref.background.select_arpls_lambda`).
    """

    n_points: int
    two_theta_min: float
    two_theta_max: float
    baseline_lambda: float
    noise_sigma_median: float
    peak_fraction: float
    n_peaks: int
    peak_density_per_deg: float
    signal_to_background: float
    amorphous_hump_score: float
    air_scatter_gain: float
    contamination: list[ContaminationFlag] = Field(default_factory=list)


def background_envelope(two_theta: np.ndarray, y: np.ndarray, *,
                        window_deg: float = 3.0, quantile: float = 10.0
                        ) -> np.ndarray:
    """Rolling low-quantile envelope of the pattern — a peak-robust,
    λ-free stand-in for the background level.

    Windows are wider than any Bragg FWHM, so the low quantile inside each
    lands on background channels; the per-window values are interpolated back
    onto the grid.  Unlike a Whittaker/arPLS baseline this has no smoothing
    parameter to choose, which is what makes it usable *for* choosing one.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    step = float(np.median(np.diff(tt)))
    w = max(int(window_deg / max(step, 1e-12)), 5)
    xs, ys = [], []
    for s in range(0, len(yy), max(w // 2, 1)):
        seg = yy[s:s + w]
        if len(seg) < 3:
            continue
        xs.append(float(tt[s:s + w].mean()))
        ys.append(float(np.percentile(seg, quantile)))
    if len(xs) < 2:
        return np.full_like(tt, float(np.median(yy)))
    return np.interp(tt, np.asarray(xs), np.asarray(ys))


def diagnose(data: PatternData, *, wavelength: float | None = None,
             baseline_lambda: float | None = None) -> PatternDiagnostics:
    """Compute :class:`PatternDiagnostics` for a raw pattern."""
    from .select import select_arpls_lambda

    mask = data.in_range_mask()
    tt = data.tt()[mask]
    y = data.y()[mask]
    sigma = data.sig()[mask]
    span = float(tt[-1] - tt[0])

    env = background_envelope(tt, y)
    net = y - env
    med_env = float(np.median(env))

    peak_channels = net > 3.0 * sigma
    idx, _ = find_peaks(np.where(net > 0, net, 0.0) / sigma, height=5.0, distance=3)

    # nested envelope fits: cubic, then cubic + 1/(2θ) air-scatter column
    design = chebyshev_design_matrix(tt, 4, float(tt[0]), float(tt[-1]))
    coef, *_ = np.linalg.lstsq(design.T, env, rcond=None)
    r_cubic = env - coef @ design
    design_air = np.vstack([design, 1.0 / np.maximum(tt, 1e-3)])
    coef_air, *_ = np.linalg.lstsq(design_air.T, env, rcond=None)
    r_air = env - coef_air @ design_air
    rss_cubic = float(r_cubic @ r_cubic)
    air_gain = float(1.0 - (r_air @ r_air) / rss_cubic) if rss_cubic > 0 else 0.0
    hump = float(np.sqrt(np.mean(r_air ** 2)) / max(med_env, 1e-12))

    flags: list[ContaminationFlag] = []
    if wavelength is not None and len(idx):
        flags = _contamination_flags(tt, net, sigma, idx, wavelength)

    lam = (select_arpls_lambda(data).selected if baseline_lambda is None
           else baseline_lambda)

    return PatternDiagnostics(
        n_points=len(tt),
        two_theta_min=float(tt[0]), two_theta_max=float(tt[-1]),
        baseline_lambda=float(lam),
        noise_sigma_median=float(np.median(sigma)),
        peak_fraction=float(np.mean(peak_channels)),
        n_peaks=int(len(idx)),
        peak_density_per_deg=float(len(idx) / max(span, 1e-12)),
        signal_to_background=float(np.percentile(net, 99.9) / max(med_env, 1e-12)),
        amorphous_hump_score=hump,
        air_scatter_gain=max(air_gain, 0.0),
        contamination=flags,
    )


def identify_anode(wavelength: float) -> str | None:
    """The anode whose Kα1 this wavelength is, or ``None``.

    ``None`` means "not a tabulated characteristic wavelength" — synchrotron,
    an anode we do not carry, or a Kα2-referenced pattern.  Callers must treat
    it as *not checked*, never as *clean*.
    """
    from ..schemas.instrument import _KA_DOUBLETS

    for name, (ka1, _) in _KA_DOUBLETS.items():
        if abs(wavelength - ka1) <= _ANODE_MATCH_TOL:
            return name
    return None


def _contamination_flags(tt: np.ndarray, net: np.ndarray, sigma: np.ndarray,
                         peak_idx: np.ndarray, wavelength: float,
                         *, tol_deg: float = 0.15) -> list[ContaminationFlag]:
    """Ghost peaks at the Kβ / W Lα positions of the strongest reflections.

    Same d-spacing, different λ:  sinθ_ghost = sinθ_parent · λ_ghost/λ_parent.
    A candidate must be a *weaker* detected peak near the predicted position
    (height ratio < 0.6 — Kβ is ≤ ~0.2 of Kα even unfiltered; W Lα weaker
    still).

    Which ghosts are looked for follows the anode: Kβ is anode-specific, W Lα1
    is filament-derived and so applies to any of them.  An unrecognised
    wavelength yields no flags, which is a *silence*, not a clean bill — the
    caller sees the same empty list either way, and that asymmetry is why
    every anode this package can build a source for has a Kβ entry.
    """
    anode = identify_anode(wavelength)
    if anode is None:
        return []
    heights = net[peak_idx]
    order = np.argsort(heights)[::-1]
    strongest = peak_idx[order[:8]]
    flags: list[ContaminationFlag] = []
    for kind, lam_ghost in (("kbeta", _KBETA[anode]), ("tungsten_la", _W_LA1)):
        ratio = lam_ghost / wavelength
        for ip in strongest:
            s = np.sin(np.radians(tt[ip] / 2.0)) * ratio
            if s >= 1.0:
                continue
            tt_ghost = 2.0 * np.degrees(np.arcsin(s))
            if not (tt[0] <= tt_ghost <= tt[-1]):
                continue
            near = peak_idx[np.abs(tt[peak_idx] - tt_ghost) < tol_deg]
            for ig in near:
                r = float(net[ig] / max(net[ip], 1e-12))
                if 0.005 < r < 0.6 and net[ig] > 5.0 * sigma[ig]:
                    flags.append(ContaminationFlag(
                        kind=kind, two_theta=float(tt[ig]),
                        parent_two_theta=float(tt[ip]), intensity_ratio=r))
    return flags
