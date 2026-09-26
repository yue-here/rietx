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

import math
from dataclasses import dataclass, field

import numpy as np

from ..backend import get_backend
from ..background.models import (
    bspline_design_matrix,
    chebyshev_design_matrix,
    hump_curve,
    interpolate_fixed,
    pspline_penalty_scale,
    second_difference_matrix,
)
from ..crystallography.adp import U_NAMES, reciprocal_axis_lengths
from ..crystallography.cif import species_spelling_hint
from ..crystallography.dispersion import (
    dispersion,
    normalize_element,
)
from ..crystallography.dispersion import (
    resolve as resolve_dispersion,
)
from ..crystallography.lattice import (
    cell_volume,
    d_spacings,
    reciprocal_metric_tensor,
    two_theta_deg,
)
from ..crystallography.magnetic.scattering import (
    MAGNETIC_SOURCE_KINDS,
    NON_MAGNETIC_SOURCE_KINDS,
    MagneticSites,
    compile_magnetic_sites,
    magnetic_f2,
    magnetic_reflections,
    merge_magnetic,
)
from ..crystallography.neutron import b_coh as neutron_b_coh
from ..crystallography.neutron import (
    normalize_species as neutron_normalize_species,
)
from ..crystallography.satellites import merge_satellites, satellite_reflections
from ..crystallography.scattering import normalize_species
from ..crystallography.stephens import S_NAMES, monomial_matrix, strain_width_deg
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
    resolve_group,
)
from ..schemas.common import Mode
from ..schemas.instrument import (
    CAPILLARY_OFFSETS,
    HUMP_FIELDS,
    PEAK_FIELDS,
    BackgroundChebyshev,
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    Instrument,
)
from ..schemas.pattern import PatternData
from ..schemas.structure import Structure
from . import compiled
from .absorption import (
    cylinder_absorption,
    flat_plate_reflection_absorption,
    flat_plate_transmission_absorption,
)
from .components import COMPONENT_AGGREGATE, EXTRA_TICK_KEY
from .corrections import (
    capillary_displacement_shift_deg,
    displacement_shift_deg,
    lorentz_polarization,
    surface_roughness_pitschke,
    surface_roughness_suortti,
    transparency_shift_deg,
)
from .extinction import sabine_extinction, sabine_extinction_and_dx
from .preferred_orientation import (
    march_dollase_and_dr,
    march_dollase_factors,
    orbit_layout,
)
from .profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from .profiles.fcj import (
    fcj_extent_deg,
    fcj_node_count,
    fcj_offsets_weights,
    fcj_offsets_weights_batch,
)
from .profiles.pseudovoigt import (
    pseudo_voigt,
    pseudo_voigt_basis,
    pseudo_voigt_derivs,
    tch_gamma_eta,
)
from .profiles.voigt import (
    GAUSS_FWHM_TO_SIGMA,
    fwhm_to_voigt_params,
    voigt,
    voigt_basis,
    voigt_derivs,
)
from .restraints import (
    CompiledRestraints,
    resolve_phase_restraints,
    restraint_residual,
)

#: Evaluation windows extend ±(k(η)·Γ_est + WINDOW_MIN_DEG + FCJ extent),
#: where k(η) is the smallest half-width in FWHM units at which the
#: **discarded area** of the unit-area pseudo-Voigt stays at or below this
#: tolerance (WP-1112; :func:`window_fwhm_mult` has the closed forms).  Area,
#: not height, is the criterion because reflection intensities are areas: a
#: pseudo-Voigt cut at ±k·FWHM discards ≈ η/(π·k) of its integral — the
#: two-sided Lorentzian CDF tail — so the pre-1112 fixed ±30 FWHM carried an
#: η-dependent intensity bias it never stated (≈ 0.64 % at η = 0.6, ≈ 1.1 %
#: at η = 1) while spending ~70× FWHM on near-Gaussian lab peaks whose tail
#: dies at ±2.  The tolerance was **chosen by measurement**, not principle
#: (WP-1112's task-4 record has the sweep): the Lorentzian tail makes small
#: tolerances expensive — 1e-3 grows every lab window (k(0.6) ≈ 190) and
#: even 5e-3 reproduces the old widths (k(0.5) ≈ 32) — while on the IUCr
#: QPA round-robin the *answers* are flat in the tolerance: from 5e-3 to
#: 5e-2 the weighed-truth deviations moved < 0.3 wt % (the fits' own
#: systematics dominate at ~0.6/2.9 wt %, bands ±2/±6) as the protocol
#: fits ran 1.9-2.4× faster.  2e-2 is the knee: k(0.6) ≈ 9.5, k(1) ≈ 16,
#: k(0) ≈ 1.05, cpd-1a/cpd-2 1.9×/1.8× faster than the shipped ±30 FWHM at
#: fractions within 0.25 wt % of it, and the discarded area is a stated
#: bound instead of an accident of the margin (the old default's own bias
#: was ≈ 0.64 % at η = 0.6, unstated).  Rwp rises in the third digit as the
#: truncated tail residue becomes visible — Rwp is an identity check here,
#: not the metric.
WINDOW_AREA_TOL = 2e-2
#: Absolute slack added to every half-width: windows are frozen per stage,
#: so a peak must stay inside its window while zero-shift, displacement and
#: the cell move it during the stage — this is movement headroom, not tail
#: coverage (a cold fit's zero error is instrument-scale, ~0.1°).
WINDOW_MIN_DEG = 0.3

#: 2·√(ln 2) — the Gaussian tail argument: a unit-area Gaussian of FWHM Γ
#: has σ = Γ/(2√(2 ln 2)), so the area outside ±k·Γ is erfc(2√(ln 2)·k)
_GAUSS_TAIL_C = 2.0 * np.sqrt(np.log(2.0))


def window_fwhm_mult(eta: np.ndarray) -> np.ndarray:
    """k(η): FWHM multiples holding all but ``WINDOW_AREA_TOL`` of the area.

    The two-sided discarded area of the unit pseudo-Voigt outside ±k·Γ is

        D(k) = η·(2/π)·arctan(1/(2k)) + (1−η)·erfc(2√(ln 2)·k)

    (Lorentzian CDF tail + Gaussian tail; both components share the FWHM Γ
    by the TCHZ construction).  D is monotone in k, so k is solved by
    vectorised bisection to machine-level precision; the Lorentzian term
    dominates for any η ≳ tol, giving k ≈ η/(π·tol) — the fat tail is the
    price of a Lorentzian mix and is why the criterion must know η.
    """
    from scipy.special import erfc

    eta = np.clip(np.asarray(eta, dtype=np.float64), 0.0, 1.0)
    tol = WINDOW_AREA_TOL

    def discard(k):
        with np.errstate(divide="ignore"):
            lor = np.where(k > 0.0, np.arctan(1.0 / np.maximum(2.0 * k, 1e-300)),
                           np.pi / 2.0)
        return eta * (2.0 / np.pi) * lor + (1.0 - eta) * erfc(_GAUSS_TAIL_C * k)

    lo = np.zeros_like(eta)
    hi = np.full_like(eta, 1.0 / (np.pi * tol) + 3.0)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        too_wide = discard(mid) <= tol
        hi = np.where(too_wide, mid, hi)
        lo = np.where(too_wide, lo, mid)
    return hi
#: when the axial S/L, H/L parameters are about to be *refined* from zero,
#: quadrature nodes are sized as if they were at least this large, so the
#: finite-difference Jacobian sees a live parameter instead of a frozen
#: zero-node profile
AXIAL_SIZING_FLOOR = 0.02

#: Distinct keys :meth:`CompiledModel._memo` holds per slot.  Two, because a
#: Jacobian column alternates between the expansion point and one perturbed
#: state; see that method for the measurement and for why this is capped.
_MEMO_DEPTH = 2


def _freeze(value) -> None:
    """Mark every ndarray inside a memoised block read-only, in place.

    Walks lists and tuples because the blocks are per-emission-line sequences,
    and ignores anything else — a block may legitimately be a plain float (an
    absorption factor of exactly 1.0, a zero anisotropic-strain width), and a
    float cannot be written through anyway.  A view is frozen without touching
    its base, which is what is wanted: the base may be a caller's own array.
    """
    if isinstance(value, np.ndarray):
        value.setflags(write=False)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _freeze(item)


def _cached_fcj_nodes(cp: "CompiledPhase", il: int, k: int, variant: int,
                      two_theta_deg, sl, hl, n_nodes: int):
    """``fcj_offsets_weights`` memoised per (line, reflection, call variant) on
    exact input equality (WP-0605 task 0).

    Each slot remembers the last ``(2θ, S/L, H/L)`` it was evaluated at and the
    nodes that came back; it is reused iff all three compare bit-equal, else
    recomputed and replaced.  Equal inputs give bit-equal outputs (the function
    is deterministic), so a hit can never be stale and a reused value is not a
    reordered accumulation — the six backend goldens stay bit-identical by
    construction.  This is *not* a hash of θ: three float compares against the
    node generation they guard (~15 numpy dispatches, ~27 µs measured).

    Why input equality rather than the stage-scoped dirty flag first proposed:
    the shipped plans free parameters *cumulatively* (strategy/staged.py), so
    once a position mover is freed every later stage carries it and a
    per-stage flag almost never clears (measured: 5 % of calls on the SRM 660c
    protocol, none on corundum).  The redundancy is really *within-iteration*
    — the residual and the Jacobian evaluate at the same θ, and FD
    perturbations of non-position parameters leave the nodes untouched — which
    input equality captures wherever it occurs, static stage or not.

    ``variant`` separates evaluation points so they occupy distinct slots.
    Since WP-1112 only the forward evaluation reads this memo (variant 0):
    ``derivative_bases`` generates its nodes batched per frozen count
    (``fcj_offsets_weights_batch``), where regenerating is cheaper than the
    per-row cache reads ever were.  The numpy-name gate
    keeps traced (jax/torch) evaluations honest: they run this same code under
    ``backend.traced.active`` with tracer arguments, and a tracer deposited
    here would leak into later numpy calls (while a cached numpy array would
    silently constant-fold the node positions out of a trace).
    """
    cache = cp.fcj_cache
    if cache is None or get_backend().name != "numpy":
        return fcj_offsets_weights(two_theta_deg, sl, hl, n_nodes)
    tt, s, h = float(two_theta_deg), float(sl), float(hl)
    key = (il, k, variant)
    hit = cache.get(key)
    if hit is not None and hit[0] == tt and hit[1] == s and hit[2] == h:
        return hit[3], hit[4]
    phi, omega = fcj_offsets_weights(two_theta_deg, sl, hl, n_nodes)
    cache[key] = (tt, s, h, phi, omega)
    return phi, omega


#: A phase whose strongest modelled point sits below this many σ of the
#: observation noise is one the data cannot distinguish from absent.  One σ,
#: not a tuned fraction: the comparison is against the counting statistics the
#: phase competes with, the same footing ``indexing.workflow.ABSENT_SIGMA``
#: puts a missing line on.  Below it every parameter of the phase has a
#: Jacobian column under the noise floor, which is the definition of
#: unconstrained rather than an opinion about it.  Lives here, beside
#: :meth:`CompiledModel.phase_support`, because the bound and the diagnostic
#: must read one number.
PHASE_SUPPORT_SIGMA = 1.0

@dataclass
class BatchLayout:
    """Compile-frozen index planes for the batched derivative bases (WP-1112).

    One row per non-empty (emission line, reflection) window, in the
    (il, k)-major order the pre-batch loop iterated — which is what lets a
    row-ordered scatter reproduce its accumulation order.  Everything here is
    an index or a gather of the frozen fit grid, so none of it violates
    frozen-per-stage discreteness: the planes are compile-time constants,
    never θ-dependent.  Rows whose window is padded past their own width
    read a clipped in-window index; the consumer slices ``[:width[j]]`` (the
    ragged view) or masks (the batched accumulators).
    """

    il: np.ndarray            # (R,) emission-line index per row
    k: np.ndarray             # (R,) reflection index per row
    i0: np.ndarray            # (R,) window start (point index)
    i1: np.ndarray            # (R,) window stop
    width: np.ndarray         # (R,) = i1 - i0
    w_max: int                # padded window axis
    idx: np.ndarray           # (R, w_max) point indices, clipped into window
    x: np.ndarray             # (R, w_max) = tt[idx], the frozen 2θ gather
    mask: np.ndarray          # (R, w_max) 1.0 in-window, 0.0 on the pad tail
    fcj: np.ndarray           # (R,) frozen node count per row (0 = symmetric)
    #: frozen node count → row indices; the key 0 is the symmetric block, and
    #: each nonzero key is one batched-quadrature bucket (no node-axis padding
    #: — the pad layout measured 0.8× on the gate's trigger case)
    buckets: dict[int, np.ndarray]
    #: (n_lines + 1,) prefix pointers into the rows per emission line — rows
    #: are il-major, so line il occupies rows line_ptr[il]:line_ptr[il + 1]
    line_ptr: np.ndarray

    def gather(self, peaks: list[tuple], slot: int) -> np.ndarray:
        """(R,) gather of ``peaks[il][slot][k]`` onto the rows.

        ``peaks`` is a ``phase_peaks`` result (one (pos, w₁, w₂, intensity)
        tuple per emission line); ``slot`` picks the quantity.
        """
        out = np.empty(len(self.i0))
        for il in range(len(self.line_ptr) - 1):
            a, b = int(self.line_ptr[il]), int(self.line_ptr[il + 1])
            out[a:b] = np.asarray(peaks[il][slot])[self.k[a:b]]
        return out


#: rows per chunk of the batched FCJ kernel stage in ``derivative_bases``:
#: bounds the transient (chunk, nodes, w_max) planes (~7 live at once) to
#: tens of MB at a 64-node, 400-point worst case, and measured at parity
#: with unchunked evaluation on the WP-1112 gate cases
_BASES_CHUNK_ROWS = 128


def _node_mix(w: np.ndarray, planes: np.ndarray) -> np.ndarray:
    """Node-weighted sum: (B, M) weights against (B, M, W) planes → (B, W)."""
    return np.matmul(w[:, None, :], planes)[:, 0, :]


def accumulate_planes(n_points: int, parts) -> np.ndarray:
    """One ``bincount`` over every (row, term, point) contribution (WP-1112).

    ``parts`` is ``[(layout, [(coef, plane), ...]), ...]`` in the caller's
    phase order.  Contributions are laid out row-major as (row, term, point)
    per part, then concatenated, and ``np.bincount`` accumulates its input
    sequentially from zero — so for any output point the additions arrive in
    exactly the order the pre-batch loop's per-row ``window_add`` sequence
    produced them (phase-major, row-major, terms in call order), and the
    result is **bit-identical** to that loop.  A term whose coefficient
    vector is all-zero must be omitted by the caller (the loop never added
    it); a zero coefficient *within* a live term contributes ±0.0, which is
    neutral under addition.  Planes arrive pad- and NaN-row-zeroed
    (``PhasePlanes``), which is what licenses scattering whole planes
    through ``layout.idx`` — a pad slot aliases a real in-window index.

    Since WP-1115 a compiled kernel does the same walk without materialising
    ``contrib`` or the index array, and does it **bit-identically**: no library
    function enters the sum, so the two produce the same doubles rather than
    close ones (``model/compiled.py``).  It declines on anything it was not
    written for and the numpy expression below is what runs then.
    """
    parts = list(parts)
    if compiled.enabled():
        got = compiled.accumulate(n_points, parts)
        if got is not None:
            return got
    flats_i: list[np.ndarray] = []
    flats_w: list[np.ndarray] = []
    for lay, terms in parts:
        if not terms or not len(lay.i0):
            continue
        contrib = np.empty((len(lay.i0), len(terms), lay.w_max))
        for j, (coef, plane) in enumerate(terms):
            np.multiply(coef[:, None], plane, out=contrib[:, j])
        flats_i.append(
            np.broadcast_to(lay.idx[:, None, :], contrib.shape).ravel())
        flats_w.append(contrib.ravel())
    if not flats_w:
        return np.zeros(n_points)
    idx = flats_i[0] if len(flats_i) == 1 else np.concatenate(flats_i)
    w = flats_w[0] if len(flats_w) == 1 else np.concatenate(flats_w)
    return np.bincount(idx, weights=w, minlength=n_points)


def _batch_layout(win: np.ndarray, fcj_n: np.ndarray, tt: np.ndarray
                  ) -> BatchLayout:
    """Build the frozen planes off the just-computed windows (compile time)."""
    il, k = np.nonzero(win[..., 1] > win[..., 0])  # row-major = (il, k) order
    i0 = win[il, k, 0]
    i1 = win[il, k, 1]
    width = i1 - i0
    w_max = int(width.max()) if len(width) else 0
    ar = np.arange(w_max, dtype=np.int64)[None, :]
    idx = np.minimum(i0[:, None] + ar, np.maximum(i1 - 1, 0)[:, None])
    x = tt[idx] if len(width) else np.zeros((0, 0), dtype=np.float64)
    mask = (ar < width[:, None]).astype(np.float64)
    nf = fcj_n[il, k]
    buckets = {int(v): np.nonzero(nf == v)[0] for v in np.unique(nf)}
    line_ptr = np.searchsorted(il, np.arange(win.shape[0] + 1))
    return BatchLayout(il=il, k=k, i0=i0, i1=i1, width=width, w_max=w_max,
                       idx=idx, x=x, mask=mask, fcj=nf, buckets=buckets,
                       line_ptr=line_ptr)


#: two reflections are treated as "strongly overlapped" for Pawley conditioning
#: when their primary-line centres sit within this fraction of their mean FWHM
PAWLEY_OVERLAP_FWHM_FRAC = 0.5
#: soft equal-split restraint weight for overlapped Pawley groups.  With the
#: per-group intensity scaling in ``build_pawley_restraint`` this makes the
#: split-direction esd ≈ (group intensity)/√λ, i.e. an unresolved split is
#: reported with an esd of order its own value (≈100 % at λ=1) rather than the
#: spuriously tight one a bare pseudo-inverse of a singular JᵀJ would give.
PAWLEY_OVERLAP_LAMBDA = 1.0



def _line_image_deg(tt_primary, lam_ratio: float, xp):
    """2θ of an emission line, given the **primary** line's 2θ — Bragg's law.

    sin θ_l = (λ_l/λ_0)·sin θ_0, which is the same ghost transform
    ``background.diagnostics`` uses and the same one
    ``indexing.peakfit._line_pos`` applies to a fitted position.  Written in
    ``xp`` ops because ``tt_primary`` is θ-derived: this is on the traced path
    for every backend.

    ``lam_ratio`` is 1.0 for the primary line and the identity is exact there,
    so a single-line source reproduces the pre-1103 arithmetic bit for bit.
    """
    if lam_ratio == 1.0:
        return tt_primary
    s = lam_ratio * xp.sin(xp.radians(0.5 * tt_primary))
    return 2.0 * xp.degrees(xp.arcsin(s))


@dataclass
class CompiledExtraPeak:
    """One declared :class:`~rietx.schemas.instrument.PeakComponent`, frozen.

    The peak-landing half of the component seam
    (:data:`rietx.model.components.COMPONENT_AGGREGATE`).  What is frozen here
    is exactly what the frozen-per-stage invariant asks for and no more: how
    many peaks there are, which emission lines each one images onto, and the
    **index range** of each (line, peak) window.  Where the peak sits, how wide
    it is and how much of it there is are smooth, so they are read from the
    θ-decoded values on every call.

    **The windows are sized from the parameter's bounds, never from its value.**
    That is the whole reason
    :class:`~rietx.schemas.instrument.PeakComponent` requires finite bounds on
    ``center`` and ``fwhm``: the half-width is ``k(η_max)·fwhm_max + slack``
    and the span is the Bragg image of ``[center.min, center.max]``, so a centre
    free to move anywhere its bounds allow is inside its frozen window *by
    construction*.  The alternative — sizing from the compile-time value and
    widening for the free ones — would need ``free_paths`` plumbed into
    ``compile_model`` and would still be a claim about how far a solver step can
    go.
    """

    #: index in ``Instrument.extra_components``, so a diagnostic can name the
    #: dot-path a user declared
    index: int
    label: str | None
    #: field name → dot-path, from the one field list the table registers
    paths: dict[str, str]
    #: ``(n_lines, 2)`` frozen [i0, i1) index ranges into ``tt``; a line this
    #: peak does not image onto carries ``[0, 0)``
    win: np.ndarray
    #: λ_l/λ_0 per line — the Bragg-image ratio, frozen at compile with the
    #: window it sizes.  A wavelength *is* a table row since WP-1134, so the
    #: freeze is a declaration and not a fact about θ: a stage that frees λ
    #: moves every Bragg peak and leaves this ratio where the stage found it.
    #: Legitimate at the scale a calibration moves λ (ppm, against a ratio the
    #: window's slack covers many times over) and required by the
    #: frozen-per-stage contract the window rests on — the ``f_anom`` argument
    #: in ``scalar_chain_supported``, one member over.
    lam_ratio: np.ndarray
    #: dot-path of each line's weight; line 0 is structurally locked at 1
    weight_paths: tuple[str, ...]
    #: ``False`` restricts the peak to the primary line: something that does not
    #: diffract has no Kα2 image, and placing one would be a claim about physics
    #: that is not happening
    all_lines: bool



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
    # True where no emission line's compile-time centre lies on the fitted
    # data (``PawleyBlock.off_data``; None outside pawley mode)
    off_data: np.ndarray | None = None  # (N,) bool
    # March-Dollase preferred orientation: the frozen symmetry orbit of every
    # reflection (flattened; see preferred_orientation.orbit_layout) plus the
    # fixed integer axis.  None unless the phase carries a PO block in Rietveld
    # mode.  The angles the correction needs move with the cell at evaluation;
    # only these integer members are frozen for the stage.
    po_axis: np.ndarray | None = None       # (3,) int
    po_members: np.ndarray | None = None    # (M_total, 3) int
    po_seg: np.ndarray | None = None        # (M_total,) int → reflection index
    po_counts: np.ndarray | None = None     # (N,) int orbit sizes
    # Stephens anisotropic strain: the frozen (N, 15) matrix of quartic
    # monomials h^H k^K l^L.  None unless the phase carries a microstrain
    # block.  σ²(M) = monomials @ S is the only hkl-dependent piece; the
    # d-spacings that turn it into a width move with the cell at evaluation.
    strain_monomials: np.ndarray | None = None
    # Secondary extinction, frozen *out* of this stage: True when the phase's
    # ``extinction`` is exactly 0 — where Sabine's E is identically 1 — and no
    # path this stage can move reaches it.  Then E is a multiply by ones, and
    # the six-term Laue series that builds it is pure cost: measured 1.2 s of
    # ``sabine_extinction`` plus 0.79 s of ``_laue_and_deriv`` in a 17.5 s fit
    # where extinction was never freed (WP-1109).
    #
    # This is the frozen-per-stage invariant, not a branch on θ: the decision
    # is taken at compile from a value that provably cannot change before the
    # next compile, so the residual it produces is exactly the one the
    # ungated path produces and stays as smooth.  False is the honest default
    # — "no gate was established" — so a CompiledPhase built without the
    # analysis simply evaluates the chain as before.
    skip_extinction: bool = False
    # FCJ node memo (WP-0605 task 0): {(il, k, variant) → (2θ, S/L, H/L,
    # 2φ_q, ω_q)}, each slot reused iff the three inputs compare bit-equal —
    # see ``_cached_fcj_nodes`` for why this is input equality rather than a
    # stage-scoped dirty flag, and why a hit can never be stale.  None (no FCJ
    # nodes this stage) keeps the hot loop exactly as before; numpy path only.
    fcj_cache: dict[tuple[int, int, int], tuple] | None = None
    # Compile-frozen index planes for the batched derivative bases (WP-1112).
    # Always built at compile — the layout is a few index arrays plus one
    # (R, w_max) gather of the frozen grid, and the batched build is the only
    # ``derivative_bases`` there is.
    batch: BatchLayout | None = None
    # Scalar-chain memo (WP-1109): {slot → (key, value)}, one slot per block of
    # ``phase_peaks`` that depends on a small set of decoded scalars, reused iff
    # the key compares bit-equal.  Same contract as ``fcj_cache`` one rank up —
    # input equality, never a dirty flag, so a hit cannot be stale and a reuse
    # is not a reordered accumulation — and it exists for the same reason:
    # ``_peak_chain_column`` re-runs the whole of ``phase_peaks`` once per
    # Jacobian column, at a θ where most of those blocks did not move.  A
    # column perturbing a Biso leaves the cell block alone; one perturbing the
    # profile width leaves both the cell block and |F|² alone.  ``None`` keeps
    # the hot loop exactly as it was; numpy path only, for the reason the FCJ
    # memo is numpy-only.
    scalar_cache: dict[str, tuple] | None = None
    # WP-1326.  ``satellites`` is the second ReflectionSet, frozen at stage
    # compile beside the nuclear one, kept whole so a caller can ask what was
    # generated and from which k; ``reflections`` above is the **merge** of the
    # two, because every consumer downstream — the frozen windows, the FCJ node
    # counts, the Le Bail partition, the Pawley block, the tick list, the
    # observation count — is written over "the phase's reflections" and a
    # satellite is one of those.  ``nuclear_mask`` is (N,) 1.0/0.0 over the
    # merged list and is what makes a Rietveld stage contribute exactly zero at
    # a satellite (``_nuclear_f2``).  Both ``None`` for a phase with no
    # propagation vector, which is what keeps that phase bit-identical.
    satellites: ReflectionSet | None = None
    nuclear_mask: np.ndarray | None = None
    # WP-1327.  ``magnetic`` is the frozen per-atom magnetic data — the axial
    # matrices ε·det(R)·R on the *nuclear* operation subset, the form-factor
    # ion and g, the moment frame — and ``None`` for every phase without a
    # moment, which is what keeps that phase bit-identical.  The three
    # ``mag_*`` arrays are the frozen Laue orbit of every reflection
    # (``preferred_orientation.orbit_layout``, the same flattened shape the
    # March-Dollase correction averages over): |F_⊥|² is *not* constant over
    # that orbit, because the moment direction breaks the Laue symmetry, so
    # the magnetic intensity is its **average** and not one representative's
    # value times a multiplicity.
    #
    # ``nuclear_mask`` above is also set for a magnetic phase, and for a
    # different reason than a satellite: a k = 0 magnetic space group puts
    # intensity on the reciprocal-lattice points the parent's glide and screw
    # operations forbid, those rows are added to the reflection list
    # (``magnetic_reflections``), and the nuclear structure factor there is
    # identically zero by the absence condition — so the mask is exact
    # arithmetic rather than a tolerance.
    magnetic: MagneticSites | None = None
    mag_members: np.ndarray | None = None   # (M_total, 3) int
    mag_seg: np.ndarray | None = None       # (M_total,) int → reflection index
    mag_counts: np.ndarray | None = None    # (N,) int orbit sizes


@dataclass
class CompiledModel:
    """Everything frozen for one refinement stage + fast evaluation buffers."""

    tt: np.ndarray          # fit grid (in-range points only), deg 2θ
    y_obs: np.ndarray
    sigma: np.ndarray
    tt_min: float
    tt_max: float
    wavelength: float                 # primary line, used for tick positions
    #: λ of each emission line **at stage compile**, in Å.  This is the value
    #: the frozen discreteness was sized from — the reflection list, the point
    #: windows and the FCJ node counts all come from it — and it is what a
    #: caller outside the hot loop (plot, exporter, tick list) reads.  It is
    #: *not* what the residual uses when a wavelength is free: λ is a row of θ
    #: since WP-1134, so :meth:`line_lambdas` reads the decoded values and
    #: falls back to this tuple.  A free λ therefore moves peaks inside a stage
    #: while the windows stay put, which is the same bargain the cell already
    #: strikes — legitimate while the motion is small against the window slack,
    #: and it is (215 ppm of λ is 0.09° at 2θ = 150° with a 0.30° FWHM).
    line_wavelengths: tuple[float, ...]
    # Which emission lines are *declared monochromator harmonics*, line index →
    # order n (schemas.instrument.Harmonic).  Frozen here rather than inferred
    # downstream from λ_i/λ_0 ≈ 1/n, because the declaration is a fact about the
    # beam and a ratio is a coincidence: a genuine second wavelength half the
    # primary would be indistinguishable.  Empty on every source that declares
    # none, which is every source built before harmonics existed — nothing in
    # the forward model reads it (a harmonic *is* an emission line and needs no
    # special case), so it exists only for the post-fit HARMONIC_FRACTION
    # diagnostic, which has to name the order it is reporting.
    harmonic_orders: dict[int, int]
    geometry_kind: str
    radius_mm: float | None
    # dimensionless µ·R of a packed capillary, resolved once at compile from
    # Geometry.mu_r or the composition estimate.  A *frozen scalar*, never a θ
    # entry: the Rouse transmission factor is exactly a constant times
    # exp(c·sin²θ), so a refinable µR would be an exactly singular direction
    # alongside the phase scale and Biso (model/absorption.py).  0.0 means the
    # correction is the exact identity.  A itself is not frozen — it follows
    # 2θ_Bragg, which moves with the cell.
    mu_r: float
    # dimensionless µ·t of a flat specimen, resolved once at compile the same
    # way and for the same reasons (model/absorption.py).  ``None`` means the
    # thick-specimen assumption — ITC case (1a), A = 1/2µ with no θ, exactly
    # degenerate with the phase scale — which is what this package modelled
    # before WP-0508 and what a reflection geometry without a thickness still
    # models.  0.0 is a *legal transmission* specimen (non-absorbing plate,
    # sec θ footprint only) and an illegal reflection one, so the two cases
    # cannot share the "0 means off" convention the rest of the model uses.
    mu_t: float | None
    mode: Mode
    phases: list[CompiledPhase]
    fixed_background: np.ndarray | None  # sampled on tt, or None
    # the background is linear in its parameters: y_bkg = Σ values[path]·row
    # (Chebyshev or B-spline rows + optional 1/x air term — exact Jacobian
    # columns either way)
    bkg_paths: tuple[str, ...]
    bkg_design: np.ndarray  # (len(bkg_paths), n_points)
    # P-spline smoothness penalty: extra residual rows w·D₂·c, the weight w
    # (√λ, times √m/σ̄ under ``lambda_units="dimensionless"``) already folded in
    # (columns aligned with bkg_paths); None for penalty-free backgrounds
    bkg_penalty: np.ndarray | None
    #: Whether :attr:`sigma` came from the file's own esd column, or from the
    #: Poisson fallback ``√max(y,1)``.  The fact travels with the σ it
    #: describes, because by the time anything downstream holds a
    #: ``CompiledModel`` the two are the same array of floats and the branch
    #: cannot be taken again: ``sig()`` already took it.  ``data.sigma is not
    #: None`` is the test at this rank, the ``PatternData``-level peer of
    #: ``DataRef.has_sigma`` (``background/diagnostics.py``).
    #:
    #: It changes no number here.  What it changes is what a renderer may
    #: *call* Δ/σ, which is what the fit minimised either way (WP-1029).
    #: ``None`` is no claim made rather than a claim of no σ — a defaulted
    #: ``False`` would answer a question nothing asked (WP-1076) — and
    #: :func:`compile_model` always states it.
    sigma_measured: bool | None
    # Explicit additive background peaks (schemas.instrument.HumpComponent):
    # one (position, height, fwhm) path triple per declared peak, in list order.
    #
    # **The count is frozen; the positions and widths are not.**  How many peaks
    # there are is discrete, so it is fixed here at stage compile like the hkl
    # list and the window ranges; where a peak sits and how wide it is are
    # smooth, so they are read from the θ-decoded values on every call.  That is
    # the frozen-per-stage discreteness invariant applied to a new object, not
    # an exception to it.
    #
    # Deliberately **not** part of ``bkg_paths``: those name a *linear* block
    # (y = coeffs @ bkg_design), which is what makes their Jacobian columns
    # exact design rows and what the VarPro identity rests on.  A peak is
    # nonlinear in its position and width, and a nonlinear path in ``bkg_paths``
    # would take the "y is linear in this coefficient" branch of
    # ``_make_jacobian`` and get a silently wrong column.  The design matrix is
    # untouched; the peak sum is added after it.  A test asserts the two path
    # sets are disjoint.
    component_paths: tuple[tuple[str, str, str], ...] = ()
    # Declared sharp peaks (schemas.instrument.PeakComponent), the *other* half
    # of the same seam.  They are here and not in ``component_paths`` because
    # the two members land in different places and that difference is the
    # contract's clause 2: a hump joins the reported background, a peak does
    # not.  ``compile_model`` partitions ``Instrument.extra_components`` by
    # ``model.components.COMPONENT_AGGREGATE``, which is read, never inferred.
    #
    # The consequence a caller sees: a peak's curve is **not** in
    # ``background()``, so it is not in ``result.y_background`` and not drawn as
    # background anywhere — and its subtraction from the Le Bail/Pawley net is
    # therefore not free, the way a hump's is.  It is done explicitly at both
    # nets, which is the whole of clause 3 for this member.
    peak_components: tuple["CompiledExtraPeak", ...] = ()
    # peak shape frozen for the stage: "tchz_pv" (default pseudo-Voigt) or
    # "voigt" (true Gaussian⊗Lorentzian via the shared Faddeeva w(z)).  A
    # compile-time structural constant, never a θ entry — the width parameters
    # (U,V,W,X,Y and phase size/strain) are identical for both shapes.
    shape: str = "tchz_pv"
    # Surface-roughness model frozen for the stage: "suortti", "pitschke" or
    # None when the instrument carries no block.  Compile-time structural, like
    # ``shape`` and ``geometry_kind`` — never a θ entry, so the branch on it
    # never sees a decoded value and the residual stays smooth (WP-0502).
    roughness: str | None = None
    # Pawley intensity block (per-hkl intensities as free parameters, appended
    # to θ outside the ParameterTable); None outside pawley mode.
    pawley: "PawleyBlock | None" = None
    # Soft-restraint rows (bond/angle/value), frozen per stage; None when no
    # phase declares any (Rietveld-only — see compile_model).  They sit below
    # the data/penalty/Pawley rows in the residual, in the covariance but out
    # of Rwp/DW/Bérar-Lelann (WP-0406).
    restraints: "CompiledRestraints | None" = None
    # c_w of McCusker eq (7) for this stage: every restraint row is multiplied
    # by √c_w, so S_G as a whole is weighted by c_w against the diffraction
    # data (WP-1074).  A compile-time scalar, like ``shape`` and ``mu_r`` and
    # for the same reason — a schedule changes it *between* stages, never
    # within one.  1.0 is the identity.
    #
    # It is applied where the rows are assembled — ``restraint_residual`` here
    # and the analytic block in ``optimize.least_squares`` — and deliberately
    # NOT on the compiled items or inside ``restraints.restraint_partials``:
    # ``model.geometry`` calls that function with sigma = weight = 1 precisely
    # to get unweighted ∂(distance or angle)/∂p, and every reported geometry
    # esd is built from them.  Scaled there, all of them would come back ×√c_w
    # with no test failing that a reader would connect to the change.
    restraint_weight_scale: float = 1.0
    meta: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    def background(self, values: dict[str, float]) -> np.ndarray:
        """The whole declared background: the linear block plus any peaks.

        One authority, and that is what makes the peaks compose: ``evaluate``,
        the Le Bail/Pawley partition net, ``report.texture``, ``viz.live`` and
        ``result.y_background`` all call this, so a declared peak is subtracted
        from the partition and drawn as background everywhere without any of
        them knowing it exists.  Empty ``component_paths`` leaves the body
        bit-identical to the pre-peak one — the loop does not run.
        """
        # stacked, not np.array-ed: the coefficients come from θ (traced)
        xp = get_backend()
        coeffs = xp.stack([values[p] for p in self.bkg_paths])
        y = xp.matmul(coeffs, self.bkg_design)
        if self.fixed_background is not None:
            y = y + xp.asarray(self.fixed_background, dtype=np.float64)
        if self.component_paths:
            # lifted once, and lifted *here* rather than at compile: the grid is
            # a frozen numpy constant that is about to meet a θ-derived
            # position, and jax's fp64 is scoped to the traced call (CLAUDE.md →
            # Conventions, and backend/traced.py's module docstring)
            tt = xp.asarray(self.tt, dtype=np.float64)
            for pos_path, height_path, fwhm_path in self.component_paths:
                y = y + hump_curve(
                    tt, values[pos_path], values[height_path],
                    values[fwhm_path], xp)
        return y

    def peak_component_prefixes(self) -> frozenset[str]:
        """Dot-path prefixes of the components that are **not** background.

        One spelling, because two consumers must partition the declared
        components the same way: ``background_absorption`` excludes exactly
        these and ``extra_peak_absorption`` takes exactly these, and a set that
        disagreed between them would count a component twice or not at all —
        which is the failure clause 2 of the member contract exists to prevent,
        reaching a statistic instead of a curve.
        """
        return frozenset(f"instrument.extra_components.{pc.index}."
                         for pc in self.peak_components)

    def extra_peak_tick_positions(self, values: dict[str, float]) -> list[float]:
        """Where every declared sharp peak's emission-line images sit, in °2θ.

        The tick half of the member contract's clause 2, written once because
        **two** result builders owe it: ``refine._build_result`` and
        ``multi.MultiHistogramRefinement._ticks``.  A copy in each is how a
        joint fit ends up reporting a declared peak as an unindexed impurity
        while a single-histogram fit does not — the ``ticks`` failure this
        exists to prevent, one surface over.

        **No zero shift**, unlike a phase's ticks: the centre is the *apparent*
        position by declaration and carries its own aberrations
        (:class:`~rietx.schemas.instrument.PeakComponent`), so adding the
        specimen's shift would move a tick off the peak the model drew.

        Sorted, and empty when nothing is declared — so a caller writes the
        reserved key only when there is something to put under it.
        """
        out: list[float] = []
        for pc in self.peak_components:
            centre = values[pc.paths["center"]]
            reach = len(pc.lam_ratio) if pc.all_lines else 1
            for il in range(reach):
                pos_l = _line_image_deg(centre, float(pc.lam_ratio[il]), np)
                if np.isfinite(pos_l):
                    out.append(float(pos_l))
        return sorted(out)

    def extra_peak_curve(self, values: dict[str, float]):
        """Every declared sharp peak, summed on the fit grid.

        Zeros when none is declared, and the empty case is *exactly* off: the
        loop does not run and the array is the additive identity, so a model
        that declares no peak is bit-identical to the pre-1103 one.

            y(2θ) = Σ_peaks Σ_lines A·g_l · pV(2θ − 2θ_l; Γ, η)

        with ``g_l = w_l · Lp(2θ_l)/Lp(2θ_0)`` the line gain and 2θ_l the Bragg
        image of the declared centre.  The gain is the *measured* form, not the
        bare weight: each line diffracts at its own Bragg angle so it carries
        its own Lorentz-polarisation factor, and holding the bare weight instead
        biases the fitted primary position (−2e-4° and −0.26 mean σ pull on lab
        Cu Kα LaB6, WP-1018; :mod:`rietx.indexing.peakfit` states the same
        arithmetic for the same reason).  Line 0's weight is structurally locked
        at 1 and its own ratio is 1, so ``area`` is the primary line's area.

        **No FCJ.**  The axial divergence of whatever is making this peak is not
        the specimen's, so applying the specimen's asymmetry would be worse than
        applying none; the symmetric pseudo-Voigt is the honest simple model and
        the WP says so as a non-goal rather than as an oversight.

        Windowed, with the window frozen at compile — see
        :class:`CompiledExtraPeak` for why sizing it from bounds is what makes
        the frozen-per-stage invariant hold without any free-path analysis.
        """
        xp = get_backend()
        y = xp.zeros_like(xp.asarray(self.tt, dtype=np.float64))
        if not self.peak_components:
            return y
        tt = xp.asarray(self.tt, dtype=np.float64)
        pol = values["instrument.polarization"]
        for peak in self.peak_components:
            center = values[peak.paths["center"]]
            area = values[peak.paths["area"]]
            gamma = values[peak.paths["fwhm"]]
            eta = values[peak.paths["eta"]]
            lp0 = lorentz_polarization(center, pol)
            n_lines = 1 if not peak.all_lines else len(peak.weight_paths)
            for il in range(n_lines):
                i0, i1 = int(peak.win[il, 0]), int(peak.win[il, 1])
                if i1 <= i0:
                    continue
                pos = _line_image_deg(center, float(peak.lam_ratio[il]), xp)
                gain = values[peak.weight_paths[il]]
                if il:
                    gain = gain * (lorentz_polarization(pos, pol) / lp0)
                prof = pseudo_voigt(tt[i0:i1] - pos, gamma, eta)
                # ``window_add`` is THE scatter op (backend/api.py): the index
                # range is a frozen constant but the values are θ-derived, and
                # a traced backend has no in-place write
                y = xp.window_add(y, i0, i1, area * gain * prof)
        return y

    def instrument_fwhm_deg(self, two_theta, values: dict[str, float]):
        """Instrumental resolution FWHM (deg 2θ) at arbitrary 2θ.

        The **instrument** half of the profile only — Caglioti U,V,W and the
        Lorentzian X,Y through the TCH mixing, with no phase size/strain terms —
        because it answers a question about the *goniometer*: "how narrow can a
        real reflection be here?".  That is the scale a background peak's width
        is judged against (``strategy.staged.check_hump_width``), and
        it must not depend on which phase one happens to ask about.

        Evaluate-only and off the hot path: plain floats in, the shared
        ``profiles`` functions through the active backend.
        """
        xp = get_backend()
        theta = xp.asarray(np.asarray(two_theta, dtype=np.float64) * 0.5)
        gamma_g = gaussian_fwhm(theta, values["instrument.profile.u"],
                                values["instrument.profile.v"],
                                values["instrument.profile.w"])
        gamma_l = lorentzian_fwhm(theta, values["instrument.profile.x"],
                                  values["instrument.profile.y"])
        gamma, _eta = tch_gamma_eta(gamma_g, gamma_l)
        return gamma

    def penalty_residual(self, values: dict[str, float]) -> np.ndarray | None:
        """w·D₂·c rows appended to the residual (P-spline smoothness; the
        frozen weight w is ``bkg_penalty``'s, see that field)."""
        if self.bkg_penalty is None:
            return None
        xp = get_backend()
        coeffs = xp.stack([values[p] for p in self.bkg_paths])
        # xp.matmul: the frozen penalty rows are the *left* operand (backend/api.py)
        return xp.matmul(self.bkg_penalty, coeffs)

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
        elif self.geometry_kind == "debye_scherrer" and self.radius_mm:
            # McCusker eq (4).  Unconditional inside the branch for the same
            # reason as the flat-plate pair: a = b = 0 contributes an exact ±0.
            # The radius test *is* structural — a capillary instrument with no
            # declared R cannot carry a non-zero offset (Geometry's validator)
            # and cannot free one (ParameterTable), so both offsets are
            # identically 0 here and skipping the term changes no number.
            shift = shift + capillary_displacement_shift_deg(
                tt_bragg,
                values[f"instrument.geometry.{CAPILLARY_OFFSETS[0]}"],
                values[f"instrument.geometry.{CAPILLARY_OFFSETS[1]}"],
                self.radius_mm)
        return shift

    def _absorption(self, tt_bragg: np.ndarray) -> np.ndarray | float:
        """Specimen absorption transmission A(θ) for this geometry, or exactly 1.0.

        One seam, three geometries (:mod:`rietx.model.absorption`): the Rouse
        cylinder for a capillary, ITC case (2) for a finite-thickness flat
        reflection specimen, ITC case (3a) for symmetric transmission.  The
        branch is on *compile-time structural* state only — the geometry kind
        and a frozen scalar — so no θ-derived value is ever branched on and the
        residual stays smooth for FD/autodiff Jacobians.

        **Every hand-written analytic intensity column must apply this too.**
        A is a plain multiplier on the same product ``phase_peaks`` builds, and
        unlike extinction it does not depend on |F|², r or any refined
        parameter — so a coordinate/ADP/PO move chains through it unchanged and
        the column is simply scaled.  Omit it in one of those builders and that
        column is silently wrong by A (a factor of ~5 at µR = 1, and a factor of
        3 across the pattern at µt = 0.2) while the finite-difference columns
        stay right, which converges happily to the wrong structure.
        ``test_absorption.py`` guards this for every geometry.

        Returns the scalar ``1.0`` when off so the multiply is a no-op the
        backends do not even trace.  "Off" differs by geometry and that is
        deliberate: no capillary µR, or a flat specimen with no declared
        thickness (the thick limit, which has no θ-dependence to correct).
        """
        if self.geometry_kind == "debye_scherrer":
            return cylinder_absorption(tt_bragg, self.mu_r) if self.mu_r else 1.0
        if self.geometry_kind == "flat_plate_transmission":
            # µt is optional here and *not* an on/off switch: the sec θ growth
            # of the illuminated volume is a property of a tilted plate, not of
            # its absorption, so an undeclared thickness means µt = 0 (a
            # transparent plate) rather than no correction.  Choosing this
            # geometry is the opt-in.
            return flat_plate_transmission_absorption(tt_bragg, self.mu_t or 0.0)
        if self.mu_t is None:
            return 1.0
        return flat_plate_reflection_absorption(tt_bragg, self.mu_t)

    def _strain_key(self, ip: int, values: dict[str, float]) -> tuple:
        """The Stephens coefficients of phase ip, or ``()`` when it has none."""
        if self.phases[ip].strain_monomials is None:
            return ()
        return tuple(float(values[f"phases.{ip}.microstrain.{n}"])
                     for n in S_NAMES)

    def _shift_key(self, values: dict[str, float]) -> tuple:
        """Every scalar :meth:`_position_shift_deg` reads, by geometry.

        Mirrors that method's structural branch rather than listing all the
        parameters: a key wider than the shift is merely a missed reuse, but a
        key *narrower* than it would hand back a stale position, so the two
        must be read together whenever either changes.
        """
        key = [float(values["instrument.zero_shift"])]
        if self.geometry_kind == "bragg_brentano":
            key.append(float(values["instrument.geometry.sample_displacement"]))
            key.append(float(values["instrument.geometry.sample_transparency"]))
        elif self.geometry_kind == "debye_scherrer" and self.radius_mm:
            key.extend(float(values[f"instrument.geometry.{name}"])
                       for name in CAPILLARY_OFFSETS)
        return tuple(key)

    def _width_block(self, ip: int, values: dict[str, float],
                     tt_bragg_lines: list, aniso):
        """The (w₁, w₂) pair of every emission line, at the current widths."""
        out = []
        for tt_bragg in tt_bragg_lines:
            theta = 0.5 * tt_bragg  # Bragg angle drives the widths
            gam_g = gaussian_fwhm(theta, values["instrument.profile.u"],
                                  values["instrument.profile.v"],
                                  values["instrument.profile.w"],
                                  values[f"phases.{ip}.gauss_size"],
                                  values[f"phases.{ip}.gauss_strain"])
            gam_l = lorentzian_fwhm(
                theta,
                values["instrument.profile.x"] + values[f"phases.{ip}.lor_size"],
                values["instrument.profile.y"] + values[f"phases.{ip}.lor_strain"],
                aniso)
            out.append(self._peak_widths(gam_g, gam_l))
        return out

    def line_lambdas(self, values: dict[str, float]) -> list:
        """λ per emission line, from θ where it is a row and frozen otherwise.

        The wavelength became a table entry in WP-1134 (a joint fit may free all
        but one of them), so the residual must not read the compile-time tuple.
        ``.get`` rather than ``[]`` because ``phase_peaks`` is public and is
        called with hand-built value dicts by plots, exporters and replay; a
        dict that does not mention λ means "the instrument's λ", which is the
        frozen value.
        """
        out = [values.get(f"instrument.source.lines.{il}.wavelength", lam)
               for il, lam in enumerate(self.line_wavelengths)]
        # A declared harmonic is lambda/n by construction and therefore has NO
        # theta row -- freeing one would be a second name for one number.  So
        # ``.get`` above can only ever hand back its frozen compile-time value,
        # which goes stale the moment the fundamental refines.  Recompute it.
        #
        # Measured before this line existed: with the fundamental moved +0.2 %,
        # the pair read (1.5434808, 0.7702) where tracking gives
        # (1.5434808, 0.7717404).  At the +258 ppm the acceptance suite finds on
        # this instrument that misplaces the lambda/2 peaks by up to 0.11 deg at
        # 2theta = 150 deg, about a third of the assumed 0.30 deg FWHM -- and
        # nothing raised, because the Jacobian column agreed with the residual.
        for il, order in self.harmonic_orders.items():
            out[il] = out[0] / order
        return out

    def _cell_block(self, cp: "CompiledPhase", cell: tuple, lams: list):
        """(d, [2θ_Bragg per emission line]) — the cell and λ together.

        One block rather than two memo slots because they share their input and
        every caller wants both: the line positions are ``two_theta_deg(d, λ)``
        and nothing else enters them.  ``d`` depends on the cell alone; the
        per-line angles are where λ enters the model at all, which is why a free
        λ moves every peak of its histogram and nothing else does.
        """
        d = d_spacings(cp.reflections.index, *cell)
        return d, [two_theta_deg(d, lam) for lam in lams]

    def _memo(self, cp: "CompiledPhase", slot: str, key_fn, build):
        """``build()`` memoised on exact equality of a small scalar key.

        The generalisation of :func:`_cached_fcj_nodes`, and it keeps that
        function's two rules.  *Input equality, never a dirty flag*: equal
        inputs give bit-equal outputs because every block below is
        deterministic, so a hit can never be stale, and the value handed back
        is the same array the miss would have built rather than a re-summed
        one — which is what lets the goldens stay bit-identical.  *Numpy only*:
        under a trace the decoded values are tracers, and one deposited here
        would leak into a later numpy call while a cached numpy array would
        constant-fold the block out of the trace.

        **The key arrives as a thunk, and that is the whole reason this takes a
        callable rather than a tuple.** Every key here is built by calling
        ``float()`` on decoded values, which under a trace are tracers —
        ``float(tracer)`` raises ``ConcretizationTypeError``. Passing the key
        itself would evaluate it at the call site, *before* the numpy test
        below, so the traced path would die building a key it never uses. It
        did: the whole jax matrix failed this way, on a change whose numpy runs
        were green, because a ``[dev]``-only venv skips every jax row. A thunk
        makes the rule structural instead of remembered — the key cannot be
        computed off the numpy path.

        The key must hold plain floats.  A numpy array in it would make the
        ``==`` below elementwise and the truth test ambiguous, which is a
        raise rather than a wrong answer, but the caller should not get there.

        What is memoised is handed back **read-only**.  Before this memo every
        ``phase_peaks`` call allocated its own arrays, so a consumer writing
        into one hurt nobody; now the same array is shared across calls and an
        in-place write would poison every later evaluation of that phase
        silently.  ``phase_peaks`` is public, so that consumer need not be in
        this repository.  Freezing the arrays costs nothing per call and turns
        the corruption into a ``ValueError`` naming the write.

        **Two keys deep, because a Jacobian alternates between exactly two**
        (WP-1121).  A column perturbs one parameter and leaves the rest at the
        expansion point, so a run of columns that do not touch this block all
        want the *same* base key — and one cell column between two of them is
        enough to evict it from a one-deep slot, which then rebuilds a block
        the perturbation could not have changed.  Measured on the trigger cold
        fit: 63.6 % of column-seam lookups hit at depth 1 against 72.9 % with
        an unbounded cache, the gap worth 0.29 s of 8.8 s, and |F|² alone —
        145 µs a build — carrying 0.17 s of it.

        Depth is capped rather than unbounded because the keys are decoded θ:
        an unbounded map grows one entry per distinct parameter vector and a
        fit visits thousands, so it is a leak wearing a cache's clothes.  Two
        is what the *access pattern* asks for, not a tuning constant — the
        alternation has two arms, and **depth 8 was measured to build exactly
        the same 35 596 blocks as depth 2** on the trigger fit, to the call.
        What the remaining 8 pp of the unbounded figure would take is a key
        last seen in an *earlier Jacobian*, thousands of lookups ago; no cache
        that is not a leak reaches it, and reading that gap as headroom is the
        mistake this note exists to stop.
        """
        cache = cp.scalar_cache
        if cache is None or get_backend().name != "numpy":
            return build()
        key = key_fn()
        held = cache.get(slot)
        if held is not None:
            if held[0][0] == key:
                return held[0][1]
            if len(held) > 1 and held[1][0] == key:
                # promote, so an alternation keeps hitting rather than
                # evicting the arm it is about to want again
                held[0], held[1] = held[1], held[0]
                return held[0][1]
        value = build()
        _freeze(value)
        if held is None:
            cache[slot] = [(key, value)]
        else:
            held.insert(0, (key, value))
            del held[_MEMO_DEPTH:]
        return value

    def _atom_key(self, ip: int, values: dict[str, float]) -> tuple:
        """Every decoded scalar |F|² reads for phase ip, in a fixed order.

        Cheaper than the arrays :meth:`_site_values` stacks from them (a few
        dozen dict lookups against a structure-factor evaluation), which is
        what makes it worth building on a call that will then hit the memo.
        """
        cp = self.phases[ip]
        n = cp.sites.n_asym
        out: list[float] = []
        for j in range(n):
            base = f"phases.{ip}.atoms.{j}."
            out.append(float(values[base + "x"]))
            out.append(float(values[base + "y"]))
            out.append(float(values[base + "z"]))
            out.append(float(values[base + "occ"]))
            out.append(float(values[base + "biso"]))
            if cp.sites.any_aniso:
                out.extend(float(values.get(base + u, 0.0)) for u in U_NAMES)
            # The moment DOFs belong in this key, and leaving them out is the
            # silent-short-column failure of WP-1070 rather than a slow path:
            # ``_peak_chain_column`` perturbs one θ and re-runs ``phase_peaks``,
            # so a stale |F|² memo would hand the perturbed call the
            # unperturbed intensity and the moment's Jacobian column would come
            # back identically **zero** — a moment that cannot refine, with no
            # error anywhere.
            if cp.magnetic is not None:
                out.extend(float(values[f"{base}moment.dof{k}"])
                           for k in range(cp.magnetic.n_dofs(j)))
        return tuple(out)

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

    def _nuclear_mask(self, ip: int):
        """(N,) 1.0 on a nuclear row, 0.0 on a satellite or a parent-forbidden
        row — or ``None``.

        ``None`` is the phase with neither a propagation vector nor a moment,
        and it is not the same as an array of ones: the multiply never happens,
        so such a phase reaches the same arithmetic in the same order and every
        number it produces is bit-identical to what it produced before WP-1326
        and WP-1327 existed.

        Lifted onto the backend, never left as a frozen numpy constant beside
        a θ-derived value (root ``CLAUDE.md``: ``ndarray * tensor`` raises on
        torch and ``tensor * ndarray`` goes through a deprecated path), so the
        traced backends see an ``xp`` array exactly as they do for the
        multiplicity.
        """
        cp = self.phases[ip]
        if cp.nuclear_mask is None:
            return None
        return get_backend().asarray(cp.nuclear_mask, dtype=np.float64)

    def _nuclear_f2(self, ip: int, d, values: dict[str, float], cell: tuple):
        """⟨|F|²⟩ with a satellite's or a parent-forbidden row set to exactly zero.

        **A satellite is a position, not a structure factor** (WP-1326).  That
        rung carries no moment, no magnetic form factor and no magnetic
        symmetry, so the nuclear model has nothing to say about the intensity
        at Q = H ± k — and the honest value is zero, not the parent
        reflection's |F|² evaluated at a d it does not have.  A Rietveld stage
        therefore contributes nothing there and the peak is drawn by whatever
        a Le Bail or Pawley stage extracted, which is the whole shape of the
        hypothesis test.  The structure-factor call is made with the
        **parent** integer hkl — the op subsets frozen on ``cp.sites`` are
        indexed by nothing else.

        A k = 0 magnetic space group (WP-1327) drops the parent's glide and
        screw operations, so its reflection list carries rows the nuclear
        structure factor forbids; the nuclear term there is zero by the
        absence condition, and the mask makes it exactly zero rather than
        whatever roundoff the orbit sum leaves.

        The result is masked, rather than the reflection list being split in
        two: one array per quantity is what every consumer downstream was
        written over.
        """
        cp = self.phases[ip]
        f2 = structure_factors_squared(
            cp.reflections.hkl, d, cp.sites,
            *self._site_values(ip, values, cell))
        nuc = self._nuclear_mask(ip)
        return f2 if nuc is None else f2 * nuc

    def _moment_dofs(self, ip: int, values: dict[str, float]) -> list:
        """Each atom's moment DOF vector, decoded — empty where there is none."""
        cp = self.phases[ip]
        return [np.array([values[f"phases.{ip}.atoms.{j}.moment.dof{k}"]
                          for k in range(cp.magnetic.n_dofs(j))],
                         dtype=np.float64)
                for j in range(cp.sites.n_asym)]

    def _magnetic_f2(self, ip: int, d, values: dict[str, float], cell: tuple):
        """p²·⟨|F_⊥|²⟩ in fm², or ``None`` when this phase has no moment.

        Added to ⟨|F_N|²⟩ rather than carried beside it, because both are in
        fm² and the phase's **one** scale multiplies both — a separate magnetic
        scale is the easiest route to a plausible fit and a wrong moment, and
        WP-1327 declines to offer one.  The heavy lifting is in
        ``crystallography.magnetic.scattering``; what belongs here is the
        dispatch and the frozen orbit layout.
        """
        cp = self.phases[ip]
        if cp.magnetic is None:
            return None
        xyz, occ, biso, _u, _a = self._site_values(ip, values, cell)
        stol = 1.0 / (2.0 * np.asarray(d, dtype=np.float64))
        return magnetic_f2(cp.mag_members, cp.mag_seg, cp.mag_counts, stol,
                           cp.magnetic, cell, xyz, occ, biso,
                           self._moment_dofs(ip, values))

    def _total_f2(self, ip: int, d, values: dict[str, float], cell: tuple):
        """⟨|F_N|²⟩ + p²⟨|F_⊥|²⟩ — the nuclear and magnetic terms, one scale.

        The addition happens **only** where a magnetic term exists, so a phase
        with no moment reaches the same arithmetic in the same order and every
        number it produces is bit-identical to what it produced before this WP.
        Secondary extinction reads this total, which is the physical reading:
        the attenuation is of the reflection, and the reflection is whatever
        the crystal actually diffracts.  It changes nothing at the default
        ``extinction = 0``, where Sabine's E is exactly 1.
        """
        f2 = self._nuclear_f2(ip, d, values, cell)
        mag = self._magnetic_f2(ip, d, values, cell)
        return f2 if mag is None else f2 + mag

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

    def strain_width(self, ip: int, values: dict[str, float], d: np.ndarray):
        """Λ(hkl) (N,) — the Stephens tanθ coefficient — or 0.0 when off.

        The ``None`` test is compile-time structural (does this phase carry a
        block), not a branch on θ, so it does not break residual purity; the
        off state contributes an exact ±0 to the Lorentzian strain term.
        """
        cp = self.phases[ip]
        if cp.strain_monomials is None:
            return 0.0
        xp = get_backend()
        s = xp.stack([values[f"phases.{ip}.microstrain.{n}"] for n in S_NAMES])
        return strain_width_deg(cp.strain_monomials, s, d)

    # ------------------------------------------------------------------
    # peak-shape dispatch — the two width scalars, the unit-area profile and
    # its partials all switch on the frozen ``shape`` (default TCHZ).  Both
    # shapes consume the *same* component FWHMs and expose a two-width tuple
    # ``(pos, w₁, w₂, intensity)``, so everything downstream (the peak-chain
    # Jacobian, Le Bail partitioning, FitReport Layer-1) is shape-agnostic.
    # ------------------------------------------------------------------
    def _roughness_factor(self, tt_bragg: np.ndarray, values: dict[str, float]):
        """Surface-roughness intensity multiplier, or ``None`` when off.

        ``None`` rather than an array of ones so the off state costs nothing and
        stays bit-identical; the model choice is a compile-time constant, so
        this branch never inspects a θ-decoded value.

        Evaluated at the *ideal* Bragg 2θ, matching Lp and Sabine extinction —
        the sample aberrations shift where a peak lands on the detector by
        ≤0.1°, which does not change the depth the beam travelled.

        **Every site that folds intensity by hand must call this.** The analytic
        column builders bypass :meth:`phase_peaks`, so a factor applied only
        there would leave the dof/adp/March columns disagreeing with finite
        differences — the hidden-Jacobian bug that WP-0506 and WP-0307 both
        pinned.  Unlike extinction, roughness is independent of |F|², so it is a
        plain multiply everywhere: there is no ``G = E + x·dE/dx`` analogue.
        """
        if self.roughness is None:
            return None
        base = "instrument.geometry.surface_roughness"
        if self.roughness == "suortti":
            return surface_roughness_suortti(tt_bragg, values[f"{base}.a"],
                                             values[f"{base}.b"])
        return surface_roughness_pitschke(tt_bragg, values[f"{base}.c"],
                                          values[f"{base}.tau"])

    def _peak_widths(self, gam_g: np.ndarray, gam_l: np.ndarray
                     ) -> tuple[np.ndarray, np.ndarray]:
        """(w₁, w₂) from component FWHMs: (Γ, η) for TCHZ, (σ, γ_HWHM) for Voigt."""
        if self.shape == "voigt":
            return fwhm_to_voigt_params(gam_g, gam_l)
        return tch_gamma_eta(gam_g, gam_l)

    def peak_fwhm(self, w1: np.ndarray, w2: np.ndarray) -> np.ndarray:
        """Combined FWHM (° 2θ) from a :meth:`phase_peaks` width pair.

        The shape-agnostic reader of the shape-specific pair — a consumer that
        wants "how wide is this peak" rather than "what does the profile
        function need".  Under TCHZ ``w1`` already *is* Γ; under the true Voigt
        the pair is (σ, γ_HWHM), which inverts to the component FWHMs exactly
        (:func:`~rietx.model.profiles.voigt.fwhm_to_voigt_params` is two
        divisions) and then goes through the same TCH quintic.  That last step
        is the ~1 % approximation ``compile_model`` already relies on for
        window sizing and FCJ node counts, and for the same reason: the quintic
        is *fit* to the true Voigt FWHM.

        Evaluate-only, and never in the hot loop — nothing in the residual
        needs a combined width.
        """
        if self.shape == "voigt":
            gam_g = np.asarray(w1, dtype=np.float64) * GAUSS_FWHM_TO_SIGMA
            gam_l = 2.0 * np.asarray(w2, dtype=np.float64)
            return np.asarray(tch_gamma_eta(gam_g, gam_l)[0], dtype=np.float64)
        return np.asarray(w1, dtype=np.float64)

    def _profile(self, x: np.ndarray, w1: np.ndarray, w2: np.ndarray) -> np.ndarray:
        """Unit-area profile of the active shape at offsets ``x``."""
        if self.shape == "voigt":
            return voigt(x, w1, w2)
        return pseudo_voigt(x, w1, w2)

    def profile_at(self, x: np.ndarray, w1: np.ndarray, w2: np.ndarray
                   ) -> np.ndarray:
        """Unit-area profile at offsets ``x`` — the public reader of the
        shape dispatch, for a consumer outside this module that has a
        :meth:`phase_peaks` width pair and wants the curve it describes.

        The peak's **symmetric** shape: the FCJ axial convolution is applied by
        :meth:`evaluate` over the frozen quadrature nodes, not here.  A caller
        integrating one reflection's area is reading the same shape function a
        full-pattern decomposition program reports, which is what
        :func:`~rietx.optimize.statistics.effective_observations` needs.
        """
        return self._profile(x, w1, w2)

    def _profile_derivs(self, x: np.ndarray, w1: float, w2: float
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """(Ω, ∂Ω/∂x, ∂Ω/∂w₁, ∂Ω/∂w₂) of the active shape."""
        if self.shape == "voigt":
            return voigt_derivs(x, w1, w2)
        return pseudo_voigt_derivs(x, w1, w2)

    def _profile_basis(self, x: np.ndarray, w1: float, w2: float) -> np.ndarray:
        """Ω of the active shape, bit-for-bit as :meth:`_profile_derivs` builds
        it — which is *not* bit-for-bit :meth:`_profile` (see
        ``pseudovoigt.pseudo_voigt_basis``).  For ``derivative_bases`` under
        ``profile_derivs=False``, where the bases must not shift under a
        caller's decision about which partials it needs.
        """
        if self.shape == "voigt":
            return voigt_basis(x, w1, w2)
        return pseudo_voigt_basis(x, w1, w2)

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

        **The position and width arrays may be shared between calls** and are
        handed back read-only, because the blocks that build them are memoised
        on the scalars they read (``CompiledPhase.scalar_cache``).  Copy before
        writing; ``intensity`` is built fresh every call and is not frozen.
        """
        xp = get_backend()
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        # the cell block: d, and with it every per-line Bragg angle.  Memoised
        # together because they share one input and are always wanted together
        # — a Jacobian column that perturbs anything but this phase's cell
        # reuses the lot (``CompiledPhase.scalar_cache``).
        # every key below is built inside a thunk, never at the call site: on a
        # traced backend these values are tracers and ``float()`` on one raises
        # (see ``_memo``)
        lams = self.line_lambdas(values)

        # The λs join the cell in *every* key below, not only the "cell" slot.
        # Two reasons, and the second is the load-bearing one.  (a) 2θ_Bragg
        # feeds the widths, Lp, the absorption factor and Sabine extinction, so
        # a stale block under a moved λ would be wrong in five slots rather than
        # one.  (b) ``_peak_chain_column`` builds the analytic λ column by
        # perturbing θ and re-deriving these scalars — a key that ignored λ
        # would hand the perturbed call the *unperturbed* block and the column
        # would come back identically zero, which is the silent-short-column
        # failure the FD fallback exists to prevent.  With λ held the key is a
        # constant-extended tuple, so the hit/miss pattern and every value are
        # bit-identical to before.
        def cell_key():
            return (tuple(float(c) for c in cell)
                    + tuple(float(x) for x in lams))

        d, tt_bragg_lines = self._memo(
            cp, "cell", cell_key, lambda: self._cell_block(cp, cell, lams))

        if self.mode in ("lebail", "pawley"):
            # extracted by partitioning (Le Bail) or refined as θ (Pawley) —
            # identical from here on
            base = cp.hkl_intensity if hkl_intensity is None else hkl_intensity
        else:
            # |F|² samples the form factors at sinθ/λ = 1/2d — line-independent,
            # and a function of the cell and this phase's atoms alone, so a
            # column perturbing a width or the background reuses it.
            #
            # This survives a **λ/n monochromator harmonic**, which is the one
            # case where sharing looks wrong at first glance: that line's λ is
            # half the primary's, so surely its structure factors differ?  They
            # do not.  ``structure_factors_squared`` takes *d*, never λ — the
            # form factors and the Debye-Waller factor are evaluated at
            # sinθ/λ = 1/2d, which is a property of the reflection.  A harmonic
            # diffracts the **same** hkl list with the same |F|²; what differs
            # is only *where* each reflection lands, and that is the per-line
            # ``tt_bragg`` below, with its own Lorentz factor, profile width and
            # window.  The single exception is anomalous dispersion, whose f′/f″
            # are functions of λ alone — which is exactly why a harmonic is
            # refused on a dispersive source rather than sharing one f_anom
            # across a factor-of-two wavelength gap
            # (``schemas.instrument.check_harmonics``).
            f2 = self._memo(
                cp, "f2", lambda: (cell_key(), self._atom_key(ip, values)),
                lambda: self._total_f2(ip, d, values, cell))
            # multiplicity lifted onto the backend: a frozen numpy factor in a
            # product with traced values (backend/api.py)
            mult = xp.asarray(cp.reflections.multiplicity, dtype=np.float64)
            base = values[f"phases.{ip}.scale"] * mult * f2
            # March-Dollase preferred orientation: a line-independent per-hkl
            # intensity multiplier folded into ``base`` (P ≡ 1 when off, so this
            # leaves the intensity bit-identical then).  It rides ahead of the
            # extinction multiply — both commute — and the extinction variable x
            # still uses the raw |F|², not this product.
            if cp.po_axis is not None:
                P = self._memo(
                    cp, "po",
                    lambda: (cell_key(),
                             float(values[f"phases.{ip}.preferred_orientation.r"])),
                    lambda: self._po_factors(ip, values, cell))
                base = base * P
            # secondary extinction (model/extinction.py): a per-(line,
            # reflection) intensity multiplier folded in below.  ext=0 makes E
            # exactly 1 (Sabine's blend is sin²θ·1 + cos²θ·1, which is exactly
            # 1.0 in fp), so where the stage cannot move ext off zero the
            # whole chain is skipped rather than evaluated to ones — a
            # compile-time structural branch (``skip_extinction``), never one
            # on θ.  Otherwise it is evaluated unconditionally, and the off
            # state stays bit-identical anyway (purity (b)).
            # V moves with the cell, hence recomputed here rather than cached.
            ext = values[f"phases.{ip}.extinction"]
            vol = cell_volume(*cell)

        # anisotropic strain is line-independent (it depends on hkl and the
        # cell, not on λ), so Λ is computed once and reused across the lines
        aniso = self._memo(
            cp, "aniso", lambda: (cell_key(), self._strain_key(ip, values)),
            lambda: self.strain_width(ip, values, d))

        # The three per-line blocks below were built inside the loop until
        # WP-1109 and are hoisted only so each can carry its own memo key; the
        # arithmetic and the order it happens in are unchanged.  Each names
        # exactly what it depends on, which is what a Jacobian column's
        # perturbation is compared against.
        positions = self._memo(
            cp, "pos", lambda: (cell_key(), self._shift_key(values)),
            lambda: [tt + self._position_shift_deg(0.5 * tt, tt, values)
                     for tt in tt_bragg_lines])

        def width_key():
            return (cell_key(), self._strain_key(ip, values),
                    float(values["instrument.profile.u"]),
                    float(values["instrument.profile.v"]),
                    float(values["instrument.profile.w"]),
                    float(values["instrument.profile.x"]),
                    float(values["instrument.profile.y"]),
                    float(values[f"phases.{ip}.gauss_size"]),
                    float(values[f"phases.{ip}.gauss_strain"]),
                    float(values[f"phases.{ip}.lor_size"]),
                    float(values[f"phases.{ip}.lor_strain"]))

        widths = self._memo(cp, "widths", width_key,
                            lambda: self._width_block(ip, values, tt_bragg_lines,
                                                      aniso))
        if self.mode in ("lebail", "pawley"):
            lp_lines = absorb_lines = None
        else:
            lp_lines = self._memo(
                cp, "lp",
                lambda: (cell_key(), float(values["instrument.polarization"])),
                lambda: [lorentz_polarization(
                    tt, values["instrument.polarization"])
                    for tt in tt_bragg_lines])
            # µR/µt are frozen at compile, so the cell is the whole key
            absorb_lines = self._memo(
                cp, "abs", cell_key,
                lambda: [self._absorption(tt) for tt in tt_bragg_lines])

        out = []
        for il, lam in enumerate(lams):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = tt_bragg_lines[il]
            pos = positions[il]
            gamma, eta = widths[il]
            if self.mode in ("lebail", "pawley"):
                # extracted/refined intensities already absorb Lp
                intensity = base * w_line
            else:
                intensity = base * w_line * lp_lines[il]
                if not cp.skip_extinction:
                    intensity = intensity * sabine_extinction(
                        f2, lam, vol, tt_bragg, ext)
                # specimen absorption, model/absorption.py: cylinder, finite
                # flat reflection or flat transmission by geometry.  The
                # geometry test is a compile-time structural branch, permitted
                # by the same rule as _position_shift_deg; µR/µt are frozen, so
                # no θ-derived value is branched on.  Off returns the scalar
                # 1.0, which keeps a specimen-shape-free model off the code path
                # entirely rather than merely multiplying by ones.
                intensity = intensity * absorb_lines[il]
                # surface roughness (model/corrections.py): a per-(line,
                # reflection) depression of the low-angle intensity.  Rides
                # after extinction — all these multiplies commute — and, unlike
                # extinction, does not feed back into the extinction variable x.
                # It can now coexist with the absorption factor above (both are
                # flat-specimen quantities, and a thin rough layer is a real
                # specimen), which is why neither is written as an else-branch
                # of the other.
                rough = self._roughness_factor(tt_bragg, values)
                if rough is not None:
                    intensity = intensity * rough
            # a reflection pushed off the sphere (λ/2d > 1 → NaN position)
            # carries exactly zero intensity: Lp of a NaN angle is NaN, and the
            # masked profile (purity (c)) would otherwise multiply NaN·0
            intensity = xp.where(xp.isfinite(pos), intensity, 0.0)
            out.append((pos, gamma, eta, intensity))
        return out

    def _reflection_profile(self, cp: CompiledPhase, il: int, k: int,
                            pos_k: float, gamma_k: float, eta_k: float,
                            sl: float, hl: float,
                            grid: np.ndarray | None = None) -> np.ndarray | None:
        """Unit-area profile of one (line, reflection) on its frozen window.

        Returns ``None`` only for the frozen empty window (``i1 <= i0``, a
        compile-time structural branch).  A non-finite *position* is
        θ-dependent, so it is a where-mask instead (purity (c)): the profile
        is evaluated at a safe position and zeroed element-wise —
        ``phase_peaks`` zeroes the matching intensity, so a dead reflection
        contributes exactly 0 without a python branch.

        ``grid`` is the fit grid already lifted onto the active backend, hoisted
        by the caller: it is subtracted *from the left* of the θ-derived peak
        position, which torch requires be a tensor (backend/api.py), and lifting
        it once per forward call rather than once per reflection is the
        difference between one host→device copy and thousands.  ``None`` keeps
        the numpy buffer, which is what ``asarray`` would hand back anyway.
        """
        i0, i1 = cp.win[il, k]
        if i1 <= i0:
            return None
        xp = get_backend()
        finite = xp.isfinite(pos_k)
        pos_safe = xp.where(finite, pos_k, 0.0)
        x = (self.tt if grid is None else grid)[i0:i1]
        n_fcj = int(cp.fcj_n[il, k])
        if n_fcj == 0:  # frozen node count — structural
            return xp.where(finite, self._profile(x - pos_safe, gamma_k, eta_k), 0.0)
        # FCJ images computed at the apparent position: the ≤0.1° detector
        # shifts change the aberration geometry negligibly (≪ node spacing)
        phi, omega = _cached_fcj_nodes(cp, il, k, 0, pos_safe, sl, hl, n_fcj)
        prof = omega @ self._profile(x[None, :] - phi[:, None], gamma_k, eta_k)
        return xp.where(finite, prof, 0.0)

    def _omega_batch(self, lay: "BatchLayout", pos: np.ndarray,
                     w1: np.ndarray, w2: np.ndarray, finite: np.ndarray,
                     sl: float, hl: float, spell: int) -> np.ndarray:
        """(R, w_max) Ω planes for one phase's frozen rows — the batched twin
        of :meth:`_reflection_profile`, with the profile spelling left to the
        caller.

        ``spell`` is :data:`~rietx.model.compiled.SPELL_FORWARD` for the
        **forward** and :data:`~rietx.model.compiled.SPELL_BASIS` for the
        **derivative bases**.  That is a deliberate parameter, not an
        implementation detail: the two spell the Gaussian exponent differently
        and land 1-2 ulp apart by design (``model/profiles/pseudovoigt``), so a
        caller is declaring *which* Ω it is reproducing.  Handing the forward
        the bases' spelling would move every converged fit in its last digits
        (WP-1120), and it is the same declaration either path takes — the
        compiled kernel carries the flag rather than inferring it.

        Symmetric rows reproduce the per-row loop **bit for bit** — the same
        elementwise expressions, broadcast; an FCJ row's node mix is a batched
        matmul where the loop ran one dgemv, and agrees to rounding rather
        than to the bit (WP-1112's bar, unchanged here).

        Returned pad- and NaN-row-zeroed, which is what makes it safe to
        scatter whole planes through ``lay.idx`` (:func:`accumulate_planes`).
        """
        omega = np.zeros((len(lay.i0), lay.w_max))
        basis = (self._profile if spell == compiled.SPELL_FORWARD
                 else self._profile_basis)
        # the compiled kernels are pseudo-Voigt only; a Voigt model keeps the
        # numpy expression, which is the shape dispatch one rank down
        fast = self.shape != "voigt" and compiled.enabled()
        srows = lay.buckets.get(0, np.zeros(0, dtype=np.int64))
        if len(srows) and not (fast and compiled.omega_symmetric(
                omega, lay.x, srows, pos, w1, w2, lay.width, spell)):
            omega[srows] = basis(lay.x[srows] - pos[srows, None],
                                 w1[srows, None], w2[srows, None])
        for n, rows_b in lay.buckets.items():
            if n == 0:
                continue
            phi_all, om_all = fcj_offsets_weights_batch(pos[rows_b], sl, hl, n)
            if fast and compiled.omega_fcj(omega, lay.x, rows_b, w1, w2,
                                           lay.width, phi_all, om_all, spell):
                continue
            for a in range(0, len(rows_b), _BASES_CHUNK_ROWS):
                rs = rows_b[a:a + _BASES_CHUNK_ROWS]
                s = slice(a, a + _BASES_CHUNK_ROWS)
                phi, om = phi_all[s], om_all[s]
                x3 = lay.x[rs][:, None, :] - phi[:, :, None]
                omega[rs] = _node_mix(
                    om, basis(x3, w1[rs, None, None], w2[rs, None, None]))
        np.multiply(omega, lay.mask, out=omega)
        if not finite.all():
            omega[~finite] = 0.0
        return omega

    def phase_component(self, ip: int, values: dict[str, float],
                        hkl_intensity: np.ndarray | None = None) -> np.ndarray:
        """Bragg contribution of one phase.

        Batched on numpy (WP-1120), the per-reflection loop on every traced
        backend — which is not a choice about speed but about what each path
        can express: ``fcj_offsets_weights_batch`` is numpy-only by intent,
        and ``backend/traced.py`` builds its own residual anyway.  The two
        agree bit for bit on symmetric rows and to rounding on FCJ rows; the
        loop is the oracle that says so (``_phase_component_scalar``).
        """
        if get_backend().name == "numpy":
            return self._phase_component_batched(ip, values, hkl_intensity)
        return self._phase_component_scalar(ip, values, hkl_intensity)

    def _phase_component_batched(self, ip: int, values: dict[str, float],
                                 hkl_intensity: np.ndarray | None = None
                                 ) -> np.ndarray:
        """One phase's Bragg contribution through the WP-1112 batched planes.

        Ω is built with :meth:`_profile` — the loop's own spelling, not the
        derivative bases' — and scattered by :func:`accumulate_planes`, whose
        bincount reproduces the loop's ``window_add`` order.  A non-finite
        position keeps the loop's semantics exactly: Ω is zeroed on that row
        and the intensity is *not*, so a NaN intensity still reaches the
        pattern, in both paths and at the same points.
        """
        lay = self.phases[ip].batch
        peaks = self.phase_peaks(ip, values, hkl_intensity)
        pos = lay.gather(peaks, 0)
        omega = self._omega_batch(
            lay, pos, lay.gather(peaks, 1), lay.gather(peaks, 2),
            np.isfinite(pos), values["instrument.geometry.axial_sl"],
            values["instrument.geometry.axial_hl"], compiled.SPELL_FORWARD)
        return accumulate_planes(
            len(self.tt), [(lay, [(lay.gather(peaks, 3), omega)])])

    def _phase_component_scalar(self, ip: int, values: dict[str, float],
                                hkl_intensity: np.ndarray | None = None
                                ) -> np.ndarray:
        """The per-reflection loop: the traced backends' path, and the
        bit-identity oracle every batched claim is measured against."""
        xp = get_backend()
        y = xp.zeros_like(self.tt)
        grid = xp.asarray(self.tt, dtype=np.float64)  # lifted once, see below
        cp = self.phases[ip]
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        peaks = self.phase_peaks(ip, values, hkl_intensity)
        for il, (pos, gamma, eta, intensity) in enumerate(peaks):
            for k in range(len(pos)):
                prof = self._reflection_profile(cp, il, k, pos[k], gamma[k],
                                                eta[k], sl, hl, grid)
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
        if not self.peak_components:
            # The empty case is off at the *call*, not inside a summed zero
            # array: this is the hot loop, and a model that declares no peak
            # pays neither the allocation nor the add.  Both arms keep the
            # association they had — addition is not associative, so folding
            # these two returns into one would move every converged fit.
            return self.background(values) + self.bragg_component(values, intensities)
        return (self.background(values) + self.extra_peak_curve(values)
                + self.bragg_component(values, intensities))

    def phase_support(self, values: dict[str, float]) -> np.ndarray:
        """Each phase's strongest modelled point, in σ of the observation noise.

        The one authority for "can the data see this phase at all", with two
        consumers that must not disagree: the default cell window
        (``params.vector.cell_window``, applied by ``run_least_squares`` only to
        phases below :data:`PHASE_SUPPORT_SIGMA`) and the
        ``PHASE_UNCONSTRAINED`` diagnostic.  A second opinion here would pass a
        test and still let the solver bound a phase the report calls visible —
        the ``staged.bound_findings`` precedent (WP-1076), one measurement
        projected twice.

        Measured on the **modelled contribution** rather than on ``scale``,
        because scale is degenerate with |F|², the profile widths and the line
        weights: a small scale is not the same statement as a small
        contribution, and only one of them is about what the data can see.
        Against σ rather than a fraction of the pattern, for the reason
        ``refine.ROUGHNESS_MIN_DEPRESSION`` is: the competitor is counting
        statistics.
        """
        sigma = np.asarray(self.sigma, dtype=np.float64)
        out = np.zeros(len(self.phases), dtype=np.float64)
        for ip in range(len(self.phases)):
            y = np.asarray(self.phase_component(ip, values), dtype=np.float64)
            out[ip] = float(np.max(y / sigma)) if len(y) else 0.0
        return out

    def reflection_support(self, ip: int, values: dict[str, float]
                           ) -> list[np.ndarray]:
        """Each reflection's strongest modelled point, in σ of the noise.

        :meth:`phase_support` one rank down — the same quantity, max(y/σ), over
        one (emission line, reflection) window instead of over the whole phase
        — so the two can be read against one threshold,
        :data:`PHASE_SUPPORT_SIGMA` (WP-1458).  One array per emission line
        over the frozen reflection list, the layout :meth:`phase_peaks`
        returns.  A reflection whose frozen window is empty (generated in the
        compiler's margin, outside the fitted range) reads 0: nothing of it is
        on a point the data holds.

        Built from the Ω planes :meth:`phase_component` scatters, taken per row
        before the scatter rather than re-evaluated, and on the loop path
        (every traced backend) from the same per-reflection profile.
        Evaluate-only; never in the hot loop.
        """
        cp = self.phases[ip]
        sigma = np.asarray(self.sigma, dtype=np.float64)
        peaks = self.phase_peaks(ip, values)
        out = [np.zeros(len(np.asarray(p[0]))) for p in peaks]
        if get_backend().name == "numpy":
            lay = cp.batch
            if not len(lay.i0):
                return out
            pos = lay.gather(peaks, 0)
            omega = self._omega_batch(
                lay, pos, lay.gather(peaks, 1), lay.gather(peaks, 2),
                np.isfinite(pos), values["instrument.geometry.axial_sl"],
                values["instrument.geometry.axial_hl"], compiled.SPELL_FORWARD)
            height = lay.gather(peaks, 3)[:, None] * omega / sigma[lay.idx]
            row = np.max(height, axis=1)
            for il in range(len(lay.line_ptr) - 1):
                a, b = int(lay.line_ptr[il]), int(lay.line_ptr[il + 1])
                out[il][lay.k[a:b]] = row[a:b]
            return out
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        for il, (pos, gamma, eta, intensity) in enumerate(peaks):
            for k in range(len(pos)):
                prof = self._reflection_profile(cp, il, k, pos[k], gamma[k],
                                                eta[k], sl, hl)
                if prof is None:
                    continue
                i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                y = np.asarray(intensity[k] * prof, dtype=np.float64)
                out[il][k] = float(np.max(y / sigma[i0:i1]))
        return out

    def extra_peak_support(self, values: dict[str, float]
                           ) -> list[tuple[float, int, float]]:
        """``(position, peak, support)`` of every declared peak's line images.

        The images :meth:`extra_peak_tick_positions` lists — same filter, same
        sort, so the two pair by index — each with the index of the peak it is
        an image of (into :attr:`peak_components`) and its strongest modelled
        point in σ of the noise, :meth:`reflection_support`'s quantity for a
        declared peak.  The curve is :meth:`extra_peak_curve`'s term for that
        (peak, line), rebuilt here on numpy because that method returns the
        sum and this needs the terms.  An image whose frozen window is empty
        reads 0.  Evaluate-only.
        """
        sigma = np.asarray(self.sigma, dtype=np.float64)
        pol = values["instrument.polarization"]
        out: list[tuple[float, int, float]] = []
        for j, peak in enumerate(self.peak_components):
            center = float(values[peak.paths["center"]])
            area = float(values[peak.paths["area"]])
            gamma = float(values[peak.paths["fwhm"]])
            eta = float(values[peak.paths["eta"]])
            lp0 = lorentz_polarization(center, pol)
            reach = len(peak.lam_ratio) if peak.all_lines else 1
            for il in range(reach):
                pos = float(_line_image_deg(center, float(peak.lam_ratio[il]), np))
                if not np.isfinite(pos):
                    continue
                i0, i1 = int(peak.win[il, 0]), int(peak.win[il, 1])
                if i1 <= i0:
                    out.append((pos, j, 0.0))
                    continue
                gain = float(values[peak.weight_paths[il]])
                if il:
                    gain = gain * float(lorentz_polarization(pos, pol) / lp0)
                y = area * gain * pseudo_voigt(self.tt[i0:i1] - pos, gamma, eta)
                out.append((pos, j, float(np.max(np.asarray(y) / sigma[i0:i1]))))
        return sorted(out, key=lambda t: t[0])

    def phase_line_counts(self) -> np.ndarray:
        """How many (emission line, reflection) windows of each phase cover a point.

        Zero is the **limit** of :meth:`phase_support`, and a different
        statement from a small one: no line of the phase lies in the fitted
        range at all, so no value of its scale could make it visible and
        nothing about it is measurable here.  Worth separating because the two
        have different answers — a phase whose scale sits at its floor might
        appear in the next pattern of a series; a phase with no line in the
        window will not, whatever the specimen does.

        Read off the **frozen windows** rather than ``len(reflections)``: a
        reflection generated just outside the fitted ends (the compiler keeps
        a margin) has an empty window and contributes exactly as much as one
        that does not exist.  Frozen at stage compile like everything else the
        windows carry, so this is a fact about the stage, not about θ.
        """
        out = np.zeros(len(self.phases), dtype=np.int64)
        for ip, cp in enumerate(self.phases):
            out[ip] = int(np.count_nonzero(cp.win[:, :, 1] > cp.win[:, :, 0]))
        return out

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

    def structural_grad_supported(self, ip: int) -> bool:
        """Whether the analytic coordinate/ADP columns are exact for this phase.

        **False when the phase carries a moment**, and this is a declared
        exclusion rather than an omission (the WP-1070 rule: an unstated
        exclusion is the column-comes-back-*wrong* class of bug).  A moment
        sits on the same coordinate and takes the same Debye-Waller factor as
        the nucleus, so ∂I/∂x has a magnetic term too, and
        ``structure_factor.d_f2_d_xyz`` computes only the nuclear one.  Rather
        than write a second analytic kernel for it, the dispatch drops such a
        phase to ``_peak_chain_column``, which re-runs ``phase_peaks`` at the
        perturbed θ and is therefore exact for whatever the intensity contains.
        The cost is one extra residual-shaped evaluation per structural column
        of a magnetic phase.
        """
        return self.phases[ip].magnetic is None

    def _structural_intensity_grad(self, ip: int, j: int, coeffs: np.ndarray,
                                   values: dict[str, float], kernel
                                   ) -> list[np.ndarray] | None:
        if self.mode != "rietveld" or not self.structural_grad_supported(ip):
            return None
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.index, *cell)
        xyz, occ, biso, uaniso, astar = self._site_values(ip, values, cell)
        df2 = kernel(cp.reflections.hkl, d, cp.sites, xyz, occ, biso, j, uaniso, astar
                     ) @ np.asarray(coeffs, dtype=np.float64)
        # a satellite or a parent-forbidden row has no nuclear structure
        # factor, so it has no derivative of one either — the same mask
        # ``_nuclear_f2`` applies to the forward model, applied here so the
        # analytic column and the residual cannot disagree about a row the
        # forward model puts at exactly zero
        nuc = self._nuclear_mask(ip)
        if nuc is not None:
            df2 = df2 * nuc
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
        # factor G = E + x·dE/dx (see model/extinction.py) — at ext=0, x=0
        # makes G exactly 1 (purity (b)), so the stage that cannot move ext off
        # zero skips it exactly as ``phase_peaks`` does, and every other stage
        # applies it unconditionally.  Only these pure-analytic columns need it
        # explicitly; the scale/occ/biso/cell/extinction columns pick it up
        # from the FD-of-phase_peaks chain.
        ext = values[f"phases.{ip}.extinction"]
        # the extinction variable x is built from the whole reflection, so the
        # magnetic term belongs in it exactly as it does in ``phase_peaks``
        f2 = self._total_f2(ip, d, values, cell)
        vol = cell_volume(*cell)
        out = []
        # λ read through ``line_lambdas``, never off the frozen tuple: a joint
        # fit may have moved a wavelength since compile, and a column built at
        # the compile-time λ would place this phase's peaks somewhere the
        # residual does not.
        for il, lam in enumerate(self.line_lambdas(values)):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = two_theta_deg(d, lam)
            col = d_base * w_line * lorentz_polarization(
                tt_bragg, values["instrument.polarization"])
            if not cp.skip_extinction:
                E, dEdx, x = sabine_extinction_and_dx(f2, lam, vol, tt_bragg, ext)
                col = col * (E + x * dEdx)
            col = col * self._absorption(tt_bragg)
            # roughness scales the intensity and does not depend on the
            # coordinates/ADPs, so a structural move chains through it
            # unchanged — carry exactly what phase_peaks folded in.
            rough = self._roughness_factor(tt_bragg, values)
            if rough is not None:
                col = col * rough
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
        d = d_spacings(cp.reflections.index, *cell)
        # preferred orientation multiplies the whole reflection's intensity, so
        # the derivative carries the magnetic term with it
        f2 = self._total_f2(ip, d, values, cell)
        gstar = reciprocal_metric_tensor(*cell)
        r = values[f"phases.{ip}.preferred_orientation.r"]
        _P, dP = march_dollase_and_dr(cp.po_members, cp.po_seg, cp.po_counts,
                                      cp.po_axis, gstar, r)
        d_base = values[f"phases.{ip}.scale"] * cp.reflections.multiplicity * f2 * dP
        # gated exactly like phase_peaks, and unconditional otherwise: E ≡ 1
        # exactly at ext=0 either way (purity (b))
        ext = values[f"phases.{ip}.extinction"]
        vol = cell_volume(*cell)
        out = []
        # λ read through ``line_lambdas``, never off the frozen tuple: a joint
        # fit may have moved a wavelength since compile, and a column built at
        # the compile-time λ would place this phase's peaks somewhere the
        # residual does not.
        for il, lam in enumerate(self.line_lambdas(values)):
            w_line = values[f"instrument.source.lines.{il}.weight"]
            tt_bragg = two_theta_deg(d, lam)
            col = d_base * w_line * lorentz_polarization(
                tt_bragg, values["instrument.polarization"])
            if not cp.skip_extinction:
                col = col * sabine_extinction(f2, lam, vol, tt_bragg, ext)
            col = col * self._absorption(tt_bragg)
            rough = self._roughness_factor(tt_bragg, values)
            if rough is not None:
                col = col * rough
            out.append(col)
        return out

    def scalar_chain_supported(self, path: str) -> bool:
        """Paths whose effect on y flows *only* through the per-peak scalars
        (position, Γ, η, intensity) — the analytic-column chain rule applies.

        Excluded: background coefficients (their own exact columns), the FCJ
        axial ratios (they move the quadrature nodes — see
        ``derivative_bases``), and anything unknown (falls back to FD).
        """
        # A background peak is outside **every** analytic branch's reach, and
        # this line is the declaration rather than the accident.  The default
        # for an unrecognised path is already False, so this changes no
        # dispatch; what it changes is that the exclusion is now stated where
        # the reach is claimed, next to the ``surface_roughness`` clause that
        # exists for the mirror-image reason (an unstated *inclusion* costs a
        # slow test, an unstated *exclusion* is the class of bug WP-1070 filed
        # — a column that comes back **short** rather than raising).
        #
        # Short is exactly what does not happen here, and that is checkable
        # rather than hopeful: the whole-model FD writes ``J[:n_data, c]`` only,
        # and a peak parameter's derivative on every row below the data block is
        # *identically* zero — the P-spline penalty rows are w·D₂·c in the
        # background *coefficients*, the Pawley rows are in the intensity block,
        # and a restraint row is a function of coordinates and cell.  So the
        # rows the FD leaves at their zero initialisation are the rows whose
        # true value is zero, and the FD column is exact because it decodes
        # through C like the residual does.
        if path.startswith("instrument.extra_components."):
            return False
        # A *declared sharp peak* widens what two instrument names reach, and
        # the widening is outside every analytic branch: ``extra_peak_curve``
        # scales each non-primary image by ``weight_l · Lp(2θ_l)/Lp(2θ_0)``, so
        # with a peak compiled, ``instrument.polarization`` and a line
        # ``weight`` move counts the per-peak scalar chain never sees.  Left
        # claimed, the column comes back **short** rather than raising — the
        # WP-1070 failure exactly: measured at 0 against a whole-model FD of
        # −1.75 on the Kα2 rows of a 500 counts·deg holder line.  Conditioned
        # on a peak actually being compiled, so a model without one keeps the
        # analytic column it has always had.  ``getattr`` because this
        # predicate is called unbound on ``None`` by a test that asks only
        # about a path.
        if getattr(self, "peak_components", ()) and (
                path == "instrument.polarization"
                or (path.startswith("instrument.source.lines.")
                    and path.endswith(".weight"))):
            return False
        if path.startswith("phases."):
            return True
        if path in ("instrument.zero_shift", "instrument.polarization"):
            return True
        if path.startswith("instrument.geometry.sample_"):
            return True
        # the two eq (4) offsets move the peak *position* and nothing else, so
        # they ride the same chain.  Spelled out rather than folded into a
        # prefix for the surface-roughness reason below.
        if path in tuple(f"instrument.geometry.{n}" for n in CAPILLARY_OFFSETS):
            return True
        # surface roughness scales the per-peak intensity and nothing else, so
        # it rides the same chain.  Spelled out rather than left to the
        # ``sample_`` prefix above: the path does not start with it, and the
        # silent consequence of missing it is a *correct* but whole-model-FD
        # column, i.e. a slow test rather than a failing one.
        if path.startswith("instrument.geometry.surface_roughness."):
            return True
        if path.startswith("instrument.profile."):
            return True
        # Both source-line rows: the ``weight`` scales an already-placed peak,
        # and the ``wavelength`` moves one.  **The reach claim for λ is that
        # everything it touches is a per-peak scalar of this method's four**,
        # and it is checkable by enumeration — λ enters the model in exactly one
        # expression, ``two_theta_deg(d, λ)`` in :meth:`_cell_block`, and every
        # further use is a function of that angle: the widths (Caglioti in θ),
        # Lp, the specimen absorption factor, Sabine extinction, the roughness
        # depression.  All four scalars move, so no ``profile_derivs=False``
        # claim covers a free λ (``_INTENSITY_ONLY`` is an allow-list and does
        # not name it) and ``_require_basis`` would raise rather than shorten a
        # column if one ever did.
        #
        # Two things λ does *not* reach, both by declaration rather than by
        # accident.  f′/f″ are frozen onto ``PhaseSites.f_anom`` at compile, so
        # |F|² does not follow a refining λ — legitimate, because a calibration
        # error is ppm-scale and the dispersion tables are flat over that
        # (a 215 ppm move at 1.2 Å is 0.26 mÅ, far inside
        # ``LINE_DISPERSION_TOL``), and *required*, because a θ-dependent
        # dispersion would break the frozen-per-stage contract.  And the
        # reflection list, point windows and FCJ node counts are compile-time
        # discreteness, sized from ``line_wavelengths``: a free λ moves peaks
        # inside their frozen windows exactly as a free cell does.
        return path.startswith("instrument.source.lines.")

    def derivative_bases(self, values: dict[str, float],
                         intensities: list[np.ndarray] | None = None,
                         axial_derivs: bool = True,
                         profile_derivs: bool = True) -> "DerivativeBases":
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

        ``axial_derivs=False`` skips the two aperture node-FD evaluations and
        leaves every ∂Ω/∂sl, ∂Ω/∂hl entry ``None`` (WP-0605 task 0): they
        exist only to build the axial S/L, H/L Jacobian columns, so a caller
        that will not build them — ``_make_jacobian`` in any stage where
        neither axial parameter is free — should not pay two FCJ node
        generations per (line, reflection) per iteration for them.  The
        default keeps the full contract for the FitReport consumers
        (report/layer1.py reads ∂Ω/∂sl unconditionally).

        ``profile_derivs=False`` is the same bargain one term earlier and it is
        the larger one: it leaves ∂Ω/∂pos, ∂Ω/∂Γ and ∂Ω/∂η ``None`` and takes
        Ω from :meth:`_profile_basis` — the derivative form's own arithmetic
        with the partials dropped, and deliberately *not* the plain
        :meth:`_profile` the forward uses, so the bases cannot shift under a
        caller's decision about which partials it needs — so a stage
        whose free parameters move only *intensities* — scale, Biso, the
        coordinates and ADPs, extinction, the March coefficient, a line weight
        — stops paying for three partials nothing reads.  The three terms are
        multiplied by ∂pos/∂p, ∂Γ/∂p and ∂η/∂p, which are then identically
        zero, so this removes a multiply by zero rather than an approximation.
        It implies ``axial_derivs=False``: ∂Ω/∂(S/L) is built from ∂Ω/∂x.
        The caller owns the claim, and ``_peak_chain_column`` **verifies** it
        against the scalars it finite-differences anyway — a wrong claim raises
        there and names the path, rather than silently leaving the column
        short, which is what the whole-model FD fallback exists to prevent.

        Since WP-1112 the build is **batched** over ``CompiledPhase.batch``:
        one kernel evaluation for a phase's symmetric rows, one per frozen
        node count for its FCJ rows (node generation vectorised, the
        node-weighted sums as matmuls, the kernel stage chunked to bound the
        transient (rows, nodes, w_max) planes).  Symmetric rows reproduce the
        per-row loop **bit for bit** — same elementwise expressions,
        broadcast — while an FCJ row's matmul replaces a per-reflection dgemv
        and agrees to rounding, not to the bit (the WP-1112 gate record has
        the measured bars).  The ragged ``entries`` view and its None
        patterns are unchanged.
        """
        if not profile_derivs:
            axial_derivs = False
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        h_pos, h_ax = 1e-5, 1e-7
        # d_sl/d_hl exist only while the parameterisation is smooth there; at
        # either aperture ≤ 0 the axial columns fall back to FD (``axial_ok``)
        build_axial = axial_derivs and sl > 0.0 and hl > 0.0
        peaks_all: list[list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]] = []
        planes_all: list[PhasePlanes] = []
        axial_ok = True
        for ip, cp in enumerate(self.phases):
            peaks = self.phase_peaks(
                ip, values, None if intensities is None else intensities[ip])
            peaks_all.append(peaks)
            lay = cp.batch
            n_rows, w_max = len(lay.i0), lay.w_max
            pos = lay.gather(peaks, 0)
            w1 = lay.gather(peaks, 1)
            w2 = lay.gather(peaks, 2)
            inten = lay.gather(peaks, 3)
            finite = np.isfinite(pos)
            has_fcj = bool(np.any((lay.fcj > 0) & finite))
            if has_fcj and (sl <= 0.0 or hl <= 0.0):
                axial_ok = False
            d_pos = d_gamma = d_eta = d_sl = d_hl = None
            if not profile_derivs:
                # Ω alone, through the shared batched builder — in the bases'
                # own spelling, which the forward's is deliberately not
                omega = self._omega_batch(lay, pos, w1, w2, finite, sl, hl,
                                          compiled.SPELL_BASIS)
                planes_all.append(PhasePlanes(
                    layout=lay, finite=finite, pos=pos, w1=w1, w2=w2,
                    inten=inten, omega=omega, d_pos=None, d_gamma=None,
                    d_eta=None, d_sl=None, d_hl=None))
                continue
            omega = np.zeros((n_rows, w_max))
            d_pos = np.zeros((n_rows, w_max))
            d_gamma = np.zeros((n_rows, w_max))
            d_eta = np.zeros((n_rows, w_max))
            if build_axial and has_fcj:
                d_sl = np.zeros((n_rows, w_max))
                d_hl = np.zeros((n_rows, w_max))
            # pseudo-Voigt only: a Voigt model keeps the numpy expressions
            fast = self.shape != "voigt" and compiled.enabled()
            srows = lay.buckets.get(0, np.zeros(0, dtype=np.int64))
            if len(srows) and not (fast and compiled.bases_symmetric(
                    omega, d_pos, d_gamma, d_eta, lay.x, srows, pos, w1, w2,
                    lay.width)):
                pv, ddx, ddg, dde = self._profile_derivs(
                    lay.x[srows] - pos[srows, None],
                    w1[srows, None], w2[srows, None])
                omega[srows] = pv
                d_pos[srows] = -ddx
                d_gamma[srows] = ddg
                d_eta[srows] = dde
            for n, rows_b in lay.buckets.items():
                if n == 0:
                    continue
                nodes = fcj_offsets_weights_batch(pos[rows_b], sl, hl, n)
                shift = fcj_offsets_weights_batch(
                    pos[rows_b] + h_pos, sl, hl, n)
                axl = axh = None
                if d_sl is not None:
                    axl = fcj_offsets_weights_batch(
                        pos[rows_b], sl + h_ax, hl, n)
                    axh = fcj_offsets_weights_batch(
                        pos[rows_b], sl, hl + h_ax, n)
                if fast and compiled.bases_fcj(
                        omega, d_pos, d_gamma, d_eta, d_sl, d_hl, lay.x,
                        rows_b, w1, w2, lay.width, nodes[0], nodes[1],
                        (shift[0] - nodes[0]) / h_pos,
                        (shift[1] - nodes[1]) / h_pos,
                        None if axl is None else
                        ((axl[0] - nodes[0]) / h_ax, (axl[1] - nodes[1]) / h_ax,
                         (axh[0] - nodes[0]) / h_ax,
                         (axh[1] - nodes[1]) / h_ax)):
                    continue
                for a in range(0, len(rows_b), _BASES_CHUNK_ROWS):
                    rs = rows_b[a:a + _BASES_CHUNK_ROWS]
                    s = slice(a, a + _BASES_CHUNK_ROWS)
                    phi, om = nodes[0][s], nodes[1][s]
                    x3 = lay.x[rs][:, None, :] - phi[:, :, None]
                    pv, ddx, ddg, dde = self._profile_derivs(
                        x3, w1[rs, None, None], w2[rs, None, None])
                    omega[rs] = _node_mix(om, pv)
                    d_gamma[rs] = _node_mix(om, ddg)
                    d_eta[rs] = _node_mix(om, dde)
                    # node-FD ∂Ω/∂pos: a frozen count keeps both node sets the
                    # same shape, so the scalar loop's length-mismatch fallback
                    # has no batched counterpart
                    dphi = (shift[0][s] - phi) / h_pos
                    dom = (shift[1][s] - om) / h_pos
                    d_pos[rs] = _node_mix(dom, pv) - _node_mix(om * dphi, ddx)
                    for planes, var in ((d_sl, axl), (d_hl, axh)):
                        if planes is None:
                            continue
                        dphi = (var[0][s] - phi) / h_ax
                        dom = (var[1][s] - om) / h_ax
                        planes[rs] = (_node_mix(dom, pv)
                                      - _node_mix(om * dphi, ddx))
            # Make the planes scatter-safe for the batched accumulators
            # (optimize/least_squares): zero the pad tail — its garbage points
            # at a real in-window index through ``lay.idx`` — and the NaN rows
            # of a non-finite position, which the ragged view never serves but
            # a whole-plane term would otherwise multiply into NaN.  In-window
            # finite values are multiplied by 1.0, which preserves their bits,
            # so the ragged view is unchanged.
            for pl in (omega, d_pos, d_gamma, d_eta, d_sl, d_hl):
                if pl is None:
                    continue
                np.multiply(pl, lay.mask, out=pl)
                if not finite.all():
                    pl[~finite] = 0.0
            planes_all.append(PhasePlanes(
                layout=lay, finite=finite, pos=pos, w1=w1, w2=w2, inten=inten,
                omega=omega, d_pos=d_pos, d_gamma=d_gamma, d_eta=d_eta,
                d_sl=d_sl, d_hl=d_hl))
        return DerivativeBases(planes=planes_all, peaks=peaks_all,
                               axial_ok=axial_ok)

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

        **y_bragg spans every phase, and that is what makes the partition a
        partition** (WP-1028 §(g)).  The shares Σ_p Σ_k I_k·Ω_k / y_bragg sum to
        exactly 1 at every channel, so the whole of ``net`` is handed out once.
        Building the denominator per phase — as this did before v1.0 — makes
        *each* phase claim the entire observed excess in its own windows, so
        wherever two phases overlap the same counts are issued twice.  Measured
        on a synthetic LaB₆ + CaF₂ pattern: Σ y_bragg settles at **1.79 ×** the
        observed excess.  Note the shape of that failure, because the WP that
        filed it described a different one — it converges, to a *fixed*
        overcount, rather than inflating without bound; the Rwp table it was
        filed with (742-3334 % at two phases, 2.6e5 % at three) is the
        overcount compounding through the profile stages that follow, not the
        partition running away by itself.

        Runs *between* least-squares solves, so it may commit to the at-rest
        buffers — but it threads the intensity vectors functionally through its
        own cycles and writes each phase's buffer exactly once at the end.
        """
        if self.mode not in ("lebail", "pawley"):
            raise RuntimeError("lebail_update on a Rietveld-mode model")
        xp = get_backend()
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        n_lines = len(self.line_wavelengths)
        intens = [np.asarray(cp.hkl_intensity, dtype=np.float64) for cp in self.phases]
        for _ in range(n_cycles):
            bkg = self.background(values)
            # clause 3, and the one thing a peak-landing member costs that a
            # background-landing one does not: a hump is inside ``background``
            # and so is subtracted for free, a peak has to be subtracted here.
            # Without it the phases are handed shares of counts that belong to
            # a holder.
            net = xp.maximum(self.y_obs - bkg - self.extra_peak_curve(values), 0.0)

            # pass 1 — every phase's profiles, and the *total* Bragg curve they
            # are shares of.  One pass per phase would be cheaper by nothing:
            # the profiles are needed again below either way.
            all_peaks, all_profs = [], []
            y_bragg = xp.zeros_like(self.tt)
            for ip, cp in enumerate(self.phases):
                peaks = self.phase_peaks(ip, values, intens[ip])
                profs: list[list[np.ndarray | None]] = []
                for il, (pos, gamma, eta, intensity) in enumerate(peaks):
                    row: list[np.ndarray | None] = []
                    for k in range(len(cp.reflections)):
                        om = self._reflection_profile(cp, il, k, pos[k], gamma[k], eta[k], sl, hl)
                        row.append(om)
                        if om is not None:
                            i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                            y_bragg = xp.window_add(y_bragg, i0, i1, intensity[k] * om)
                    profs.append(row)
                all_peaks.append(peaks)
                all_profs.append(profs)

            # pass 2 — each reflection takes its share of net out of the total
            for ip, cp in enumerate(self.phases):
                peaks, profs = all_peaks[ip], all_profs[ip]
                new_int = intens[ip].copy()
                for k in range(len(cp.reflections)):
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

    def structure_intensity_partition(
            self, values: dict[str, float]
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Per-phase (I_obs, I_calc) in the units of eq (14), I_hkl = m·|F|².

        The 'observed' integrated intensities of McCusker et al. (1999) §6 and
        §11: the net observed counts are handed to the reflections in
        proportion to their *calculated* profile contributions, which is the
        same partition :meth:`lebail_update` performs — with one difference
        that is the whole point.  Le Bail's shares come from empirical per-hkl
        intensities that the partition itself then rewrites; these come from
        the **structural model** (S·m·|F|²·P·Lp·E·A·R), so the answer says how
        well that model reproduces the pattern rather than converging to it.
        The paper is explicit that this is the intended procedure — "by
        distributing the intensities of the overlapping reflections according
        to the structural model" — and equally explicit about the price: an
        I(obs) built from I(calc) is biased towards the model.

        Evaluate-only.  Nothing is written: no buffer, no θ, no recompile — the
        windows, reflection lists and FCJ node counts are reused exactly as
        compiled, so frozen-per-stage discreteness is untouched.  Runs at fit
        close, outside any traced scope, hence plain numpy throughout (the
        :meth:`lebail_update` convention one method up).

        **Every correction divides out except m and |F|².**  Writing the
        calculated counts of reflection k as W_k = Σ_l Σ_i I_lk·Ω_lk,i and its
        observed share as O_k = Σ_l Σ_i [I_lk·Ω_lk,i / y_bragg,i]·net_i, the
        two differ only by the observed/calculated ratio, so

            I_obs,k = m_k·|F_k|² · O_k / W_k .

        Scale, preferred orientation, Lorentz-polarization, extinction,
        absorption, roughness and the emission-line weights all appear in both
        W and O and cancel — which is what makes the returned pair the paper's
        I_hkl rather than a count.  Computing the ratio instead of
        reconstructing the correction product is not an optimisation: the
        product would have to be divided out per (line, reflection), and a
        systematically absent reflection would divide by |F|² = 0.

        **The sums run over hkl, not over (line, hkl).**  Both W and O
        accumulate every emission line's window contribution into the one
        reflection, so a Kα doublet counts its reflection once, at the summed
        weight — the ``RefinementResult.ticks`` lesson (all lines, never just
        the primary) one rank down.

        A reflection with W_k = 0 — a dead position off the Ewald sphere, an
        empty frozen window, or an exactly absent |F|² — has no ratio, and is
        returned as NaN in *both* arrays rather than as a zero that would enter
        the sums as perfect agreement.
        """
        if self.mode != "rietveld":
            raise RuntimeError(
                "structure_intensity_partition needs calculated structure "
                f"factors; mode is {self.mode!r}")
        sl = values["instrument.geometry.axial_sl"]
        hl = values["instrument.geometry.axial_hl"]
        bkg = np.asarray(self.background(values), dtype=np.float64)
        # clause 3 — see ``lebail_update``; the two nets must agree or Le Bail
        # and Pawley partition the same pattern differently
        extra = np.asarray(self.extra_peak_curve(values), dtype=np.float64)
        net = np.maximum(np.asarray(self.y_obs, dtype=np.float64) - bkg - extra, 0.0)

        # pass 1 — every phase's profiles and the *total* Bragg curve they are
        # shares of.  Per-phase denominators would issue the same counts once
        # per overlapping phase (lebail_update's docstring has the measurement).
        all_peaks, all_profs = [], []
        y_bragg = np.zeros(len(self.tt), dtype=np.float64)
        for ip, cp in enumerate(self.phases):
            peaks = self.phase_peaks(ip, values)
            profs: list[list[np.ndarray | None]] = []
            for il, (pos, gamma, eta, intensity) in enumerate(peaks):
                row: list[np.ndarray | None] = []
                for k in range(len(cp.reflections)):
                    om = self._reflection_profile(cp, il, k, pos[k], gamma[k],
                                                  eta[k], sl, hl)
                    row.append(om)
                    if om is not None:
                        i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                        y_bragg[i0:i1] += intensity[k] * om
                profs.append(row)
            all_peaks.append(peaks)
            all_profs.append(profs)

        out: list[tuple[np.ndarray, np.ndarray]] = []
        for ip, cp in enumerate(self.phases):
            peaks, profs = all_peaks[ip], all_profs[ip]
            n = len(cp.reflections)
            w_calc = np.zeros(n)
            o_obs = np.zeros(n)
            for k in range(n):
                for il in range(len(self.line_wavelengths)):
                    om = profs[il][k]
                    if om is None:
                        continue
                    i0, i1 = int(cp.win[il, k, 0]), int(cp.win[il, k, 1])
                    contrib = float(peaks[il][3][k]) * np.asarray(om)
                    w_calc[k] += float(contrib.sum())
                    denom = y_bragg[i0:i1]
                    good = denom > 1e-12
                    if not np.any(good):
                        continue
                    o_obs[k] += float(
                        (contrib[good] / denom[good] * net[i0:i1][good]).sum())
            # I_calc as the paper defines it: multiplicity × |F|², with the
            # scale and every angle-dependent correction left out (they are in
            # the ratio above, on both sides).  Recomputed rather than unpicked
            # from phase_peaks' product, which folds preferred orientation in.
            cell = tuple(values[f"phases.{ip}.cell.{key}"]
                         for key in ("a", "b", "c", "alpha", "beta", "gamma"))
            d = d_spacings(cp.reflections.index, *cell)
            f2 = np.asarray(self._total_f2(ip, d, values, cell),
                            dtype=np.float64)
            i_calc = np.asarray(cp.reflections.multiplicity,
                                dtype=np.float64) * f2
            live = w_calc > 0.0
            ratio = np.where(live, o_obs / np.where(live, w_calc, 1.0), np.nan)
            out.append((i_calc * ratio, np.where(live, i_calc, np.nan)))
        return out

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
        # xp.matmul: R is a frozen numpy constant on the left (backend/api.py)
        return get_backend().matmul(self.pawley.restraint, vec)

    def restraint_residual(self, values: dict) -> np.ndarray | None:
        """√(c_w·w)·(computed − target)/σ soft-restraint rows appended below the
        data (and background-penalty / Pawley) rows, or None when off (WP-0406).

        Traceable in ``xp``: the bond/angle geometry is one differentiable
        function of the decoded coordinates and cell, so jacfwd differentiates
        these rows automatically alongside the data rows.

        This is one of the **two** places :attr:`restraint_weight_scale` is
        applied — the residual row build; the other is the analytic Jacobian
        block in ``optimize.least_squares``.  Both scale the assembled rows and
        neither touches ``restraints.restraint_partials``, which
        ``model.geometry`` calls at unit weight to get *unweighted* ∂/∂p for the
        reported esds (WP-1074; see the field comment).  √ because eq (7) scales
        the sum of squares S_G, and these rows are what is squared.
        """
        if self.restraints is None:
            return None
        rows = restraint_residual(self.restraints, values)
        if self.restraint_weight_scale == 1.0:
            return rows
        # scalar on the right: a python float, so no backend routing question
        return rows * math.sqrt(self.restraint_weight_scale)

    def build_pawley_restraint(self, lam: float = PAWLEY_OVERLAP_LAMBDA) -> None:
        """Build the equal-split restraint rows for the current intensities.

        One row per member of every overlapped group: √λ/s·(δ_kj − 1/n) over the
        group, where s is the group's current mean intensity.  The rows sum to
        zero, so they penalise deviations of the *split* from an equal partition
        while leaving the group *sum* (the data-determined quantity) free.  Run
        after the intensities are seeded/carried so s reflects a realistic
        scale; constant during the least-squares run, like the background
        penalty.

        Then one row per reflection centred off the data
        (:attr:`PawleyBlock.off_data`): √λ/s·I_k, a ridge toward zero whose
        width s is the phase's largest on-data intensity (WP-1459, issue
        #440).  A reflection that stays off the data meets it only through a
        tail, so its column is all but zero and it is bounded below only: on a
        synthetic fluorapatite pattern ending at 74.99° the (6 0 2) at 75.44°
        refined to 1.45e8 against a median of 81, a warm-started series
        carried it to 1.1e12, and TRF's step test (relative to ‖x‖) then ended
        solves after two iterations at up to 769× the Rwp of the same chain
        re-seeded.  The reflection cannot simply be dropped: the list runs
        0.5° past the data so that one a stage *moves onto* the data is
        modelled, and without that margin a later pattern of the same series,
        fitted cold from a cell 0.1 % short, stalled its cell stage at 24 %
        Rwp against 3.4 %.  With the ridge an undetermined
        intensity stays within s and comes back with an esd of order s — the
        overlap rows' large-but-honest answer — while a reflection the data
        do reach has a column far more precise than a prior as wide as the
        strongest reflection.
        """
        pb = self.pawley
        if pb is None or not (pb.groups or pb.off_data):
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
        off = np.zeros(pb.n, dtype=bool)
        off[pb.off_data] = True
        for a, b in pb.phase_slices:
            on = intens[a:b][~off[a:b]]
            s = max(float(on.max()) if len(on) else 0.0, 1.0)
            for k in np.flatnonzero(off[a:b]):
                row = np.zeros(pb.n, dtype=np.float64)
                row[a + k] = np.sqrt(lam) / s
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
    off_data: list[int] = field(default_factory=list)  # centred off the data (flat idx)
    restraint: np.ndarray | None = None      # (n_rows, n) √λ-scaled restraint rows
    stderr: np.ndarray | None = None         # per-intensity esd, filled post-solve


@dataclass
class PhasePlanes:
    """One phase's derivative bases as padded (R, w_max) planes (WP-1112).

    Rows align with ``CompiledPhase.batch`` (``layout``); each row is padded
    past its own window width.  ``finite`` marks rows whose position was
    finite at the expansion point: the others are zeroed after the build and
    excluded from the ragged view, exactly as the pre-batch loop skipped
    them — and the pad tails are zeroed too, so a batched accumulator may
    scatter whole planes through ``layout.idx`` without masking (a pad slot
    aliases a real in-window index; its zero contribution is bitwise
    neutral).  ``d_sl``/``d_hl`` hold zeros at symmetric rows — a batched
    axial accumulation over all rows is then correct by construction — while
    the ragged view serves ``None`` there.  ``pos``/``w1``/``w2``/``inten``
    are the row-gathered peak scalars at the expansion point, stored so a
    per-column scalar FD gathers only its perturbed state.
    """

    layout: BatchLayout
    finite: np.ndarray
    pos: np.ndarray
    w1: np.ndarray
    w2: np.ndarray
    inten: np.ndarray
    omega: np.ndarray
    d_pos: np.ndarray | None
    d_gamma: np.ndarray | None
    d_eta: np.ndarray | None
    d_sl: np.ndarray | None
    d_hl: np.ndarray | None


@dataclass
class DerivativeBases:
    """Analytic profile-derivative bases (see ``CompiledModel.derivative_bases``).

    Since WP-1112 the storage is batched: ``planes[ip]`` holds one padded
    (R, w_max) plane per quantity (:class:`PhasePlanes`), row-aligned with
    ``CompiledPhase.batch``.  The pre-batch ragged contract survives as a
    **derived view**: ``entries[ip]`` holds tuples ``(il, k, i0, i1, Ω,
    ∂Ω/∂pos, ∂Ω/∂Γ, ∂Ω/∂η, ∂Ω/∂sl, ∂Ω/∂hl)`` per visible peak of phase
    ``ip``, each array a slice of its plane row, built lazily on first read
    and cached.  Ω is always present; every partial after it is optional and
    **every consumer None-checks**.  ∂Ω/∂sl and ∂Ω/∂hl are None for a
    symmetric peak or under ``axial_derivs=False``; the three before them
    are None under ``profile_derivs=False``, which a caller passes only when
    it has claimed that nothing it will build moves a peak's position, width
    or mixing.  ``peaks[ip]`` caches ``phase_peaks(ip, values)`` at the
    expansion point.  These bases also feed the FitReport Layer-1 misfit
    attribution (same expansion, different right-hand side) — which reads
    the partials, so its callers keep the full default.
    """

    planes: list[PhasePlanes]
    peaks: list[list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]]
    axial_ok: bool
    _entries: list[list[tuple]] | None = field(default=None, repr=False)

    @property
    def entries(self) -> list[list[tuple]]:
        if self._entries is None:
            out: list[list[tuple]] = []
            for pp in self.planes:
                lay = pp.layout
                rows: list[tuple] = []
                for j in np.nonzero(pp.finite)[0]:
                    w = int(lay.width[j])
                    is_fcj = lay.fcj[j] > 0
                    rows.append((
                        int(lay.il[j]), int(lay.k[j]),
                        int(lay.i0[j]), int(lay.i1[j]),
                        pp.omega[j, :w],
                        None if pp.d_pos is None else pp.d_pos[j, :w],
                        None if pp.d_gamma is None else pp.d_gamma[j, :w],
                        None if pp.d_eta is None else pp.d_eta[j, :w],
                        pp.d_sl[j, :w] if (is_fcj and pp.d_sl is not None)
                        else None,
                        pp.d_hl[j, :w] if (is_fcj and pp.d_hl is not None)
                        else None,
                    ))
                out.append(rows)
            self._entries = out
        return self._entries


def _reraise_species_fault(phase, disp, lams, exc, *, neutron=False):
    """Name the phase, atom and label behind a species lookup that failed.

    ``species`` is validated when the model *compiles*, not when the object is
    built (``docs/manual/using/data.md`` § Atom): the scattering lookups are the
    authority on what they can read, and duplicating their grammar in a schema
    would put a periodic table in ``pydantic`` and, worse, refuse for one
    radiation's sake a spelling the other reads — a neutron nuclide (``2H``) has
    no X-ray table row, and a sign-first charge (``Cu+1``) the X-ray table
    refuses is one the neutron parser accepts.  The cost of validating at
    compile is that the raise names only the *species* — not the atom, the
    phase, nor that the caller's own structure is at fault.

    So this re-walks the atoms **in whichever table the compile actually
    consulted**, to find the one it choked on, and re-raises naming the index,
    label and species.  That table is decided by the source, exactly as
    ``compile_phase_sites`` decides it: a ``neutron_cw`` source resolves bound
    coherent scattering lengths (``neutron.b_coh``, keyed by nuclide), and every
    other source resolves X-ray form factors (``resolve_dispersion`` then
    ``normalize_species``).  Re-walking the X-ray tables on a neutron compile
    would stop at the first nuclide the X-ray table cannot read — ``2H`` — and
    blame it for a fault in a table this compile never touched, hiding the real
    one; the boundary must ask the same question the compile asked.

    **Both arms re-walk in two passes, in the compile's own order**, because
    both compiles are two passes.  On the X-ray arm ``compile_model`` resolves
    dispersion over *every* atom of the phase first (``resolve_dispersion``,
    which raises on the first species it cannot read) and only if that whole
    pass succeeds calls ``compile_phase_sites``, which walks the atoms again
    calling ``normalize_species`` per atom.  On the neutron arm
    ``compile_phase_sites`` is itself two passes over its own table's parser:
    ``neutron_normalize_species`` per atom in the site loop, then
    ``neutron_b_coh`` per atom for the b vector.  In both cases a single loop
    that checked both lookups per atom would stop at an earlier atom that
    survives pass one but fails pass two, and blame it for a fault the compile
    never reached:

    * X-ray — ``D`` reads as hydrogen for dispersion but the Waasmaier-Kirfel
      table carries no ``D`` row, so an interleaved loop blames ``D`` when the
      real fault was a *later* atom's dispersion;
    * neutron — ``Xx`` parses as a symbol but has no Sears row, so an
      interleaved loop (or a single loop over ``b_coh``, which parses and
      looks up in one call) blames ``Xx`` for a missing scattering length when
      the compile actually choked on a *later* atom's unreadable label
      (``123``) in pass one, a table the lookup pass never reached.

    So on each arm pass one runs to completion before pass two begins, and the
    boundary re-walks the same sequence the compile did.

    Within the X-ray dispersion pass the per-atom check is the *whole* of what
    ``dispersion.resolve`` does per species — the primary line **and** the
    emission-line edge guard over the secondary lines — because a walk that
    checked the primary alone would fall straight through an edge-crossing
    species and pin the source's fault on some later atom that fails for an
    unrelated reason.  The guard is run by calling ``resolve_dispersion``
    itself rather than by copying its drift arithmetic, so there is one
    tolerance in the codebase and not two.

    The sign-first spelling hint (``Cu+1`` → ``Cu1+``) is an X-ray-table
    artifact and is added on the X-ray arm only: the neutron parser accepts the
    sign-first charge, so on that arm the charge is never the fault and naming a
    rewrite of it would be false advice.  A failure that belongs to *no* atom is
    re-raised untouched — the edge guard is about the source's two wavelengths
    and an element's core levels, not about one atom's spelling, and every atom
    of that species shares it, so there is no index to name that would not be
    arbitrary.

    **This function is a hand-maintained mirror** of ``compile_phase_sites``'s
    loops and ``dispersion.resolve``'s per-species checks, tied to them by this
    prose alone.  Anything that changes the *number or order* of lookups on
    either side — a pass added to ``compile_phase_sites``, a check added to
    ``resolve``, a lookup moved between them — has to be mirrored here in the
    same order, or this boundary starts naming the wrong atom and the wrong
    table with full confidence, which is worse than the anonymous ``KeyError``
    it replaced.
    """
    def _name_atom(index, atom, atom_exc):
        # ``str(KeyError(...))`` re-quotes its arg; take the message itself
        reason = atom_exc.args[0] if atom_exc.args else str(atom_exc)
        hint = "" if neutron else species_spelling_hint(atom.species)
        raise ValueError(
            f"phase {phase.name!r} atom {index} ({atom.label!r}): "
            f"{reason}{hint}") from exc

    def _walk(check):
        """One full pass of ``check`` over the atoms, naming the first to fail."""
        for index, atom in enumerate(phase.atoms):
            try:
                check(atom.species)
            except (KeyError, ValueError) as atom_exc:
                _name_atom(index, atom, atom_exc)

    if neutron:
        # The parse pass, then the table pass — compile_phase_sites' own two,
        # in its order.  b_coh does both in one call, which is why the lookup
        # pass alone is not enough: it would refuse a parseable-but-untabulated
        # species before the parse pass had reached a later unreadable label.
        _walk(neutron_normalize_species)
        _walk(neutron_b_coh)
        raise exc

    # X-ray: the dispersion pass first (all atoms), then the form-factor pass
    # (all atoms) — matching compile_model's two passes, so the atom named is
    # the one the compile actually choked on and in the table it choked in.
    overrides = disp.overrides if disp is not None else None

    def _line_guard_fires(species):
        """True when ``resolve``'s edge guard is what refused this species.

        Called only once the primary line has resolved for this species, so the
        guard is the only refusal ``resolve`` has left; running the real
        function keeps the drift tolerance in one place.
        """
        try:
            resolve_dispersion([species], lams, overrides)
        except ValueError:
            return True
        return False

    if disp is not None:
        for index, atom in enumerate(phase.atoms):
            try:
                sym = normalize_element(atom.species)
                if not overrides or sym not in overrides:
                    dispersion(sym, lams[0])
            except (KeyError, ValueError) as atom_exc:
                _name_atom(index, atom, atom_exc)
            if _line_guard_fires(atom.species):
                # Found the species resolve refused, and it is not a spelling:
                # re-raise the compile's own message rather than pin an
                # absorption edge on one atom, and stop — walking on would
                # reach a later atom failing for an unrelated reason and name
                # that one instead.
                raise exc
    _walk(normalize_species)
    raise exc


# ----------------------------------------------------------------------
def magnetic_wanted(phase, source) -> bool:
    """Whether this phase's moment contributes to *this* histogram (WP-1327).

    **The magnetic term enters a neutron histogram and nothing else.**  A
    neutron sees the
    magnetization density through its own moment; an X-ray of a laboratory or
    ordinary synchrotron experiment does not, to many orders of magnitude, so
    on an X-ray histogram of a joint fit the term is identically zero — and it
    is not *computed* and then found to be zero, it is never built, so the
    phase's X-ray arithmetic is untouched.  A moment refined against X-ray data
    alone therefore has no gradient anywhere, which is exactly the state the
    hold rule reports as unobserved rather than fitting.

    Any other radiation is refused **by name** rather than silently treated as
    one of the two.  This function is the one authority on that dispatch, so a
    second forward arm asks it rather than re-testing ``source.kind``.
    """
    if phase.magnetic_symmetry is None or not any(
            a.moment is not None for a in phase.atoms):
        return False
    kind = getattr(source, "kind", None)
    if kind in MAGNETIC_SOURCE_KINDS:
        return True
    if kind in NON_MAGNETIC_SOURCE_KINDS:
        return False
    raise ValueError(
        f"phase {phase.name!r} carries a magnetic moment and the source is "
        f"{kind!r}. The magnetic structure factor is a **neutron** term: it is "
        f"the neutron's own moment coupling to the magnetization density, and "
        f"an X-ray of a laboratory or ordinary synchrotron experiment does not "
        f"see it to many orders of magnitude. This package computes it for "
        f"neutron_cw, returns False for xray_cw, and refuses "
        f"any other source by name rather than guessing which of the two it "
        f"resembles. Refine the moment against a neutron histogram, or drop "
        f"the moment to fit the nuclear structure against this source")



def _compile_extra_peaks(instrument, tt: np.ndarray, lams: list[float]
                         ) -> tuple[CompiledExtraPeak, ...]:
    """Freeze one window per (emission line, declared sharp peak).

    **Sized from bounds, not values.**  The span is the Bragg image of
    ``[center.min, center.max]`` and the half-width is
    ``window_fwhm_mult(eta.max)·fwhm.max + WINDOW_MIN_DEG``, so every state the
    solver can legally reach during this stage is inside the window that was
    frozen for it.  Sizing from the compile-time *value* would need to know
    which paths are free and how far a trust-region step can carry them, which
    is a claim; a bound is a fact the schema already holds, which is why
    :class:`~rietx.schemas.instrument.PeakComponent` insists on finite ones.

    ``k(η)`` is taken at η's **upper** bound because it is steeply increasing
    (k(0) ≈ 1.05, k(1) ≈ 16) and a window must cover the widest tail the peak
    may adopt, not the tail it starts with.  ``WINDOW_MIN_DEG`` is the same
    absolute movement slack every phase window carries.

    A window holding no fitted channel is **refused**, naming the peak: a free
    parameter whose column is identically zero is a dead column, and the honest
    time to say so is now rather than at an esd that never arrives.  It is not
    an expertise gate — a declared peak that *is* in range is never questioned,
    however implausible.
    """
    out: list[CompiledExtraPeak] = []
    for i, comp in enumerate(instrument.extra_components):
        if COMPONENT_AGGREGATE[comp.kind] != "ticks":
            continue
        half = (float(window_fwhm_mult(np.float64(comp.eta.max)))
                * comp.fwhm.max + WINDOW_MIN_DEG)
        n_lines = len(lams)
        win = np.zeros((n_lines, 2), dtype=np.int64)
        ratios = np.array([lam / lams[0] for lam in lams], dtype=np.float64)
        reach = 1 if not comp.all_lines else n_lines
        for il in range(reach):
            lo = _line_image_deg(comp.center.min, float(ratios[il]), np)
            hi = _line_image_deg(comp.center.max, float(ratios[il]), np)
            if not (np.isfinite(lo) and np.isfinite(hi)):
                # the image of this centre is past the Bragg limit for this
                # line: the line simply has no image, which is a fact about the
                # wavelength and not a caller error
                continue
            win[il, 0] = int(np.searchsorted(tt, lo - half, side="left"))
            win[il, 1] = int(np.searchsorted(tt, hi + half, side="right"))
        if int(win[:, 1].sum() - win[:, 0].sum()) <= 0:
            name = comp.label or f"extra_components[{i}]"
            raise ValueError(
                f"declared peak {name!r} covers no fitted channel: its centre "
                f"bounds [{comp.center.min}, {comp.center.max}] deg, widened by "
                f"{half:.3f} deg, fall outside the fitted range "
                f"[{tt[0]:.3f}, {tt[-1]:.3f}] deg (or entirely inside an "
                "excluded region). Move the centre bounds onto the peak you "
                "mean, or drop the component.")
        out.append(CompiledExtraPeak(
            index=i, label=comp.label,
            paths={n: f"instrument.extra_components.{i}.{n}"
                   for n in PEAK_FIELDS},
            win=win, lam_ratio=ratios,
            weight_paths=tuple(f"instrument.source.lines.{il}.weight"
                               for il in range(n_lines)),
            all_lines=bool(comp.all_lines)))
    return tuple(out)


#: The measured-background scale's dot-path, spelled once.  ``compile_model``
#: tests it against ``moving_paths`` and appends its design row under the same
#: name ``params.vector.background_parameters`` registers, so the row and the
#: table entry cannot drift apart.
SCALE_PATH = "instrument.background.scale"


def compile_model(structure: Structure, instrument: Instrument, pattern: PatternData,
                  *, mode: Mode = "rietveld",
                  two_theta_limits: tuple[float, float] | None = None,
                  moving_paths: set[str] | None = None,
                  restraint_weight_scale: float = 1.0,
                  window_slack_deg: float | None = None) -> CompiledModel:
    """Freeze reflection lists, orbits, windows and FCJ nodes for one stage.

    ``moving_paths`` is every parameter the coming stage can move, or ``None``
    for "no claim made", which gates nothing and sizes as if nothing were free.
    When given, it is
    ``ParameterTable.moving_paths``, which is the free set *plus its ties*, not
    ``free_paths``: a tied parameter is not a column of θ and still changes
    while θ does, so freezing anything on "this cannot move" must ask the
    wider question.  It drives two structural decisions and nothing else.
    *Sizing*: when the axial parameters can move, FCJ nodes are allocated even
    if their current values are still zero.  *Gating*: a correction sitting
    exactly at its off state, which nothing this stage can move off it, is
    skipped rather than evaluated to its identity — see
    ``CompiledPhase.skip_extinction``.  Both are compile-time structural in the
    sense the frozen-per-stage invariant means: the decision is taken once, off
    values that cannot change, and never re-asked from a θ-derived quantity.

    ``restraint_weight_scale`` is the coming stage's c_w (McCusker eq 7),
    frozen onto the model like every other discrete choice; 1.0 is the identity
    and is what every caller outside the staged runner passes.

    ``window_slack_deg`` overrides ``WINDOW_MIN_DEG`` as the absolute capture
    slack added to every window half-width (``Stage.window_slack_deg`` has
    the two-jobs story); ``None`` — every ordinary caller — is the default.
    """
    if restraint_weight_scale < 0.0:
        raise ValueError(
            f"restraint_weight_scale must be >= 0 (got {restraint_weight_scale})")
    # Start the kernel compile here, on a background thread: numba releases the
    # GIL while it compiles, so the cost hides behind the reflection generation,
    # symmetry orbits and window sizing below rather than landing on the first
    # residual.  A no-op on every call after the first, and on a build with no
    # numba (``model/compiled.py`` § Startup).
    compiled.warm()
    mask = pattern.in_range_mask()
    tt_all, y_all, s_all = pattern.tt(), pattern.y(), pattern.sig()
    if two_theta_limits is not None:
        lo, hi = two_theta_limits
        mask &= (tt_all >= lo) & (tt_all <= hi)
    tt, y_obs, sigma = tt_all[mask], y_all[mask], s_all[mask]
    if len(tt) < 10:
        raise ValueError("fewer than 10 points remain in the fit range")
    tt_min, tt_max = float(tt[0]), float(tt[-1])

    lams = tuple(line.wavelength.value for line in instrument.source.lines)
    # Which of those lines the source declared as λ/n harmonics.  The list is
    # ordered fundamental-then-harmonics by ``Source.lines``, so the offset is
    # the number of declared lines; read off the source rather than recomputed
    # from the λ ratios (see ``CompiledModel.harmonic_orders``).
    _declared = getattr(instrument.source, "harmonics", ())
    harmonic_orders = {len(lams) - len(_declared) + i: h.order
                       for i, h in enumerate(_declared)}
    # Smallest λ → smallest 2θ for a given d → smallest d_min → the *largest*
    # reflection sphere any line needs.  Load-bearing for a λ/n harmonic and not
    # merely tidy: λ/2 has twice the Ewald radius, so generating with the
    # primary λ would silently drop every reflection only the harmonic reaches.
    # Measured on Nd₂Ru₂O₇ over 5-155° 2θ: 79 reflections at λ = 1.5404 Å
    # against 499 at λ/2, i.e. 6.3× — those 420 are the harmonic's whole
    # high-angle contribution, and dropping them would look like a correction
    # that simply does not help.
    lam_gen = min(lams)
    zero = instrument.zero_shift.value
    geom = instrument.geometry

    # ``None`` is "the caller made no claim", which is not the same as "nothing
    # moves": an empty set gates every off-state correction, so a caller that
    # simply never passed the argument must not silently get that.  Only an
    # explicit set — even an empty one — licenses the gates.
    gate_off_states = moving_paths is not None
    # FCJ sizing values (floored when the axial parameters are about to
    # refine).  The aberration's weight is the overlap trapezoid of height
    # 2·min(S/L, H/L), so it can act this stage only if **both** apertures
    # can be positive — a value already above zero, or a path the stage can
    # move.  One aperture pinned at 0 with only the other freed (the QPA
    # protocol's `lines_axial` stage) previously floored both for sizing and
    # allocated nodes that evaluated as one-hot symmetric fallbacks — full
    # node-generation and (nodes × window) kernel cost for an exact identity,
    # measured 2.5× on the bases build (WP-1112's gate record).
    moving_paths = moving_paths or set()
    axial_free = ("instrument.geometry.axial_sl" in moving_paths
                  or "instrument.geometry.axial_hl" in moving_paths)
    can_sl = geom.axial_sl.value > 0.0 or "instrument.geometry.axial_sl" in moving_paths
    can_hl = geom.axial_hl.value > 0.0 or "instrument.geometry.axial_hl" in moving_paths
    sl_eff = geom.axial_sl.value
    hl_eff = geom.axial_hl.value
    if axial_free and can_sl and can_hl:
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
        elif geom.kind == "debye_scherrer" and geom.goniometer_radius_mm:
            a = getattr(geom, CAPILLARY_OFFSETS[0]).value
            b = getattr(geom, CAPILLARY_OFFSETS[1]).value
            if a != 0.0 or b != 0.0:
                shift = shift + capillary_displacement_shift_deg(
                    tt_bragg, a, b, geom.goniometer_radius_mm)
        return shift

    # Anomalous scattering: f′ + i·f″ per species, frozen for the stage.  The
    # source owns it (it is a property of the wavelength, not the structure),
    # and ``resolve`` refuses rather than averages when an emission line is far
    # enough from the primary for one |F|² not to serve both.
    disp = instrument.source.dispersion

    phases: list[CompiledPhase] = []
    restraint_items: list = []
    for ip, phase in enumerate(structure.phases):
        cell = phase.cell.lengths_angles()
        # The phase's own operation list when it carries one: a child cell
        # whose glide translation is a quarter (a k ≠ 0 superstructure) has no
        # Hermann-Mauguin symbol, and its absences, multiplicities and Laue
        # orbits all have to come from the operations rather than from the
        # label.  ``None`` is exactly the old path, so every other phase
        # enumerates the identical list in the identical order.
        group = resolve_group(phase.space_group, phase.symmetry_operations)
        refl = generate_reflections(group, cell, lam_gen,
                                    two_theta_max=hi_eff, two_theta_min=gen_min)
        # WP-1326: a declared propagation vector adds the satellites at
        # Q = H ± k as a second ReflectionSet, frozen here with the nuclear one
        # and merged into a single list (see ``CompiledPhase.satellites``).
        # The generation runs over the reciprocal *lattice* and applies no
        # glide/screw absence — those are conditions on the nuclear structure
        # factor, which a satellite does not have.  The schema refuses a k
        # beside a moment model, so at most one of the two branches runs.
        satellites = None
        if phase.propagation_vector is not None:
            satellites = satellite_reflections(
                phase.space_group, cell, lam_gen, hi_eff,
                phase.propagation_vector, two_theta_min=gen_min)
            refl = merge_satellites(refl, satellites)
        # WP-1327: a magnetic space group generally drops the parent's glide
        # and screw operations, so a k = 0 magnetic structure puts intensity
        # on reciprocal-lattice points the nuclear structure factor forbids —
        # Cr₂WO₆'s (0 0 1) and (1 0 2), its two strongest 4 K peaks, are both
        # there.  Those rows are not in the nuclear list at all, so they are
        # generated and merged, with a mask that keeps the nuclear term at
        # exactly zero on them (which is the absence condition, not a
        # tolerance).  Only for a phase that declares a moment; every other
        # phase enumerates the list it always did.
        magnetic_mask = None
        if magnetic_wanted(phase, instrument.source):
            extra = magnetic_reflections(
                group, cell, lam_gen, hi_eff, two_theta_min=gen_min,
                magnetic_group=phase.magnetic_symmetry.group())
            refl, magnetic_mask = merge_magnetic(refl, extra)
        f_anom = None
        # The source decides the radiation, exactly as it decides f_anom: a
        # neutron source resolves bound coherent scattering lengths instead of
        # X-ray form factors, and the two are mutually exclusive.
        neutron = instrument.source.kind == "neutron_cw"
        try:
            if disp is not None:
                f_anom = resolve_dispersion([a.species for a in phase.atoms],
                                            lams, disp.overrides)
            sites = compile_phase_sites(phase, f_anom, neutron=neutron)
        except (KeyError, ValueError) as exc:
            _reraise_species_fault(phase, disp, lams, exc, neutron=neutron)

        n = len(refl)
        n_lines = len(lams)
        win = np.zeros((n_lines, n, 2), dtype=np.int64)
        fcj_n = np.zeros((n_lines, n), dtype=np.int64)
        tt_primary = fwhm_primary = None
        on_data = np.zeros(n, dtype=bool)
        # Stephens anisotropic strain: freeze the quartic monomials and take
        # the width estimate *with* Λ, so a direction that is three times
        # broader than the isotropic average still gets a wide enough window.
        # No sizing floor (cf. AXIAL_SIZING_FLOOR): Λ cannot start at zero —
        # freeing an all-zero block is rejected in ``params.vector`` — and the
        # 30·FWHM margin absorbs the growth a stage can produce from there.
        strain_monomials = aniso_est = None
        if phase.microstrain is not None:
            strain_monomials = monomial_matrix(refl.index)
            aniso_est = strain_width_deg(
                strain_monomials, np.array(phase.microstrain.values()),
                d_spacings(refl.index, *cell))
        for il, lam in enumerate(lams):
            tt_bragg = refl.two_theta(cell, lam)
            theta = 0.5 * tt_bragg
            pos = tt_bragg + _shift_est(theta, tt_bragg)
            g_est = gaussian_fwhm(theta, instrument.profile.u.value,
                                  instrument.profile.v.value, instrument.profile.w.value,
                                  phase.gauss_size.value, phase.gauss_strain.value)
            l_est = lorentzian_fwhm(theta,
                                    instrument.profile.x.value + phase.lor_size.value,
                                    instrument.profile.y.value + phase.lor_strain.value,
                                    0.0 if aniso_est is None else aniso_est)
            # TCHZ combined (Γ, η) is a compile-time proxy for window sizing
            # and FCJ node counts under *both* shapes: it tracks the true
            # Voigt FWHM to ~1 % (that is what the TCH quintic is fit to),
            # far inside the area criterion's own resolution.
            gamma_est, eta_est = tch_gamma_eta(g_est, l_est)
            if il == 0:  # primary line drives Pawley overlap grouping
                tt_primary, fwhm_primary = pos.copy(), gamma_est.copy()
            on_data |= (pos >= tt_min) & (pos <= tt_max)
            slack = (WINDOW_MIN_DEG if window_slack_deg is None
                     else window_slack_deg)
            half = window_fwhm_mult(eta_est) * gamma_est + slack
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

        cp = CompiledPhase(reflections=refl, sites=sites, win=win, fcj_n=fcj_n,
                           strain_monomials=strain_monomials,
                           satellites=satellites)
        if satellites is not None:
            cp.nuclear_mask = (~refl.is_satellite).astype(np.float64)
        if magnetic_mask is not None:
            cp.nuclear_mask = magnetic_mask
            cp.magnetic = compile_magnetic_sites(phase, sites.ops)
            # the Laue orbit of every reflection, frozen here: |F_⊥|² varies
            # over it, so the magnetic intensity is the orbit *average*.  The
            # same layout the March-Dollase correction uses, built from the
            # same ``reflection_orbits``.
            cp.mag_members, cp.mag_seg, cp.mag_counts = orbit_layout(
                reflection_orbits(group, refl.hkl))
        cp.batch = _batch_layout(win, fcj_n, tt)
        # the off-state gate (see the field): ext is exactly its identity and
        # nothing this stage moves can take it off there
        cp.skip_extinction = (gate_off_states
                              and phase.extinction.value == 0.0
                              and f"phases.{ip}.extinction" not in moving_paths)
        # WP-0605 task 0: the FCJ node memo needs no free-path analysis —
        # correctness rests on input equality alone — so it is allocated
        # whenever any peak has quadrature nodes at all.
        if fcj_on and fcj_n.any():
            cp.fcj_cache = {}
        # the scalar-chain memo needs no free-path analysis either, for the
        # same reason: correctness rests on input equality alone
        cp.scalar_cache = {}
        if mode in ("lebail", "pawley"):
            cp.hkl_intensity = np.full(n, max(float(np.median(y_obs)), 1.0))
        if mode == "pawley":
            cp.tt_primary, cp.fwhm_primary = tt_primary, fwhm_primary
            cp.off_data = ~on_data
        # March-Dollase preferred orientation acts on *calculated* structure-
        # factor intensities, so it is a Rietveld-mode correction only — Le Bail
        # and Pawley intensities are empirical and would absorb it.  Freeze the
        # symmetry orbit of each reflection here; the angles follow the cell.
        if mode == "rietveld" and phase.preferred_orientation is not None and n:
            orbits = reflection_orbits(group, refl.hkl)
            cp.po_axis = np.array(phase.preferred_orientation.axis, dtype=np.int64)
            cp.po_members, cp.po_seg, cp.po_counts = orbit_layout(orbits)
        # Soft restraints are a structural correction (bond/angle geometry, or a
        # value target), so they are Rietveld-only — Le Bail/Pawley extract
        # intensities and never compute the coordinates a bond would need.  The
        # PBC image is frozen for the stage here, at the compile-time cell/coords.
        if mode == "rietveld" and phase.restraints:
            restraint_items.extend(resolve_phase_restraints(phase, ip, sites, cell))
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
        curve = interpolate_fixed(tt, np.asarray(bkg.fixed_two_theta),
                                   np.asarray(bkg.fixed_intensity))
        # The curve is carried one of two ways, and never both — a double count
        # is absorbed by the refined scale as s_true − 1, leaves Rwp
        # bit-for-bit unchanged, and is wrong only in the number the caller
        # asked for (WP-1309, issue #171 note 1).
        #
        # A scale the stage can move is a *row*: the model is linear in it, so
        # the row is its exact Jacobian column and ``_make_jacobian``'s
        # background branch picks it up by being in ``bkg_paths`` — which is
        # also what keeps a background-only stage from rebuilding the profile
        # derivative bases every iteration.  A scale that cannot move is folded
        # into the frozen curve instead, where 1.0 is exactly the identity and
        # every number a project produced before this field existed is
        # reproduced bit for bit.
        #
        # ``moving_paths`` is the authority for "can this move", never
        # ``free_paths``: a tie can move it without it being a column.  The
        # no-claim case takes the *row* — read here off ``gate_off_states``,
        # since ``moving_paths`` has been an empty set since the normalisation
        # above — because a fold is a freeze, and a freeze taken on an unasked
        # question would hand a caller who had freed the scale a flat column
        # and a parameter that cannot move.  Every other gate in this function
        # falls the other way for the same reason: theirs is a cost, this one
        # would be a wrong number.
        if not gate_off_states or SCALE_PATH in moving_paths:
            bkg_paths = bkg_paths + (SCALE_PATH,)
            design = np.vstack([design, curve[None, :]])
        else:
            fixed = float(bkg.scale.value) * curve
        if bkg.fixed_sigma is not None:
            # The curve's own counting statistics, at the scale the stage
            # compiled at: σ² = σ_y² + s²·σ_f² (schemas.instrument's docstring
            # has the two caveats).  Frozen per stage like every other discrete
            # choice, so a stage that moves s re-weights at the next compile.
            sig_f = interpolate_fixed(tt, np.asarray(bkg.fixed_two_theta),
                                      np.asarray(bkg.fixed_sigma))
            s = float(bkg.scale.value)
            sigma = np.sqrt(sigma * sigma + (s * sig_f) ** 2)
    elif isinstance(bkg, BackgroundPSpline):
        n_coef = len(bkg.coefficients)
        bkg_paths = tuple(f"instrument.background.c{n}" for n in range(n_coef))
        design = bspline_design_matrix(tt, np.asarray(bkg.breakpoints))
        # An air term the model does not declare has no row, so no plan's
        # ``instrument.background.*`` can free it (WP-1454).
        n_air = 0 if bkg.air_scatter is None else 1
        if n_air:
            bkg_paths = bkg_paths + ("instrument.background.air",)
            with np.errstate(divide="ignore"):
                air_row = 1.0 / np.maximum(tt, 1e-3)
            design = np.vstack([design, air_row[None, :]])
        if bkg.lambda_smooth > 0.0 and n_coef > 2:
            d2 = second_difference_matrix(n_coef)
            weight = np.sqrt(bkg.lambda_smooth)
            if bkg.lambda_units == "dimensionless":
                # σ is this compile's, over the fitted channels, so the scale
                # is frozen per stage like every other discrete choice here
                weight *= pspline_penalty_scale(sigma, n_coef)
            penalty = np.hstack([weight * d2,
                                 np.zeros((d2.shape[0], n_air))])  # air term unpenalised
    else:  # pragma: no cover - schema exhausts the union
        raise TypeError(f"unsupported background model {type(bkg).__name__}")

    # the component *count* is frozen here (discrete); every position, width,
    # height and area is read from θ on every call (smooth).  Built from the
    # same field lists the parameter table registers, so a path can never be
    # spelled two ways — see ``params.vector.extra_component_parameters``.
    #
    # **The list is partitioned by declared aggregate, never by class name**
    # (``model.components.COMPONENT_AGGREGATE``, the member contract's clause 2).
    # A hump joins the background block below; a peak is compiled into its own
    # frozen windows and evaluated outside ``background`` entirely.
    component_paths = tuple(
        tuple(f"instrument.extra_components.{i}.{name}"
              for name in HUMP_FIELDS)
        for i, comp in enumerate(instrument.extra_components)
        if COMPONENT_AGGREGATE[comp.kind] == "background")
    peak_components = _compile_extra_peaks(instrument, tt, lams)
    if peak_components:
        # `RefinementResult.ticks` is keyed by name, so a phase actually called
        # "(extra)" and the declared-peak row would be one entry and one of the
        # two would vanish — silently, and in the direction that matters (Layer
        # 0 would stop seeing a whole phase's reflections).  Refused rather than
        # renamed: the name is the caller's and a CIF's phase names are not
        # parenthesised, so this is a collision worth saying out loud.  Only
        # checked when a peak is actually declared, so no existing model can
        # start failing for a name it has always had.
        for phase in structure.phases:
            if phase.name == EXTRA_TICK_KEY:
                raise ValueError(
                    f"phase name {EXTRA_TICK_KEY!r} collides with the reserved "
                    "tick-list key for declared sharp peaks; rename the phase "
                    "(parenthesised names are no CIF's) or drop the "
                    "PeakComponent.")

    pawley = _build_pawley_block(phases) if mode == "pawley" else None
    restraints = CompiledRestraints(restraint_items) if restraint_items else None

    return CompiledModel(
        tt=tt, y_obs=y_obs, sigma=sigma, tt_min=tt_min, tt_max=tt_max,
        sigma_measured=pattern.sigma is not None,
        wavelength=instrument.source.primary_wavelength,
        line_wavelengths=lams,
        harmonic_orders=harmonic_orders,
        geometry_kind=geom.kind, radius_mm=geom.goniometer_radius_mm,
        # frozen for the stage; None (nothing asked for) and 0.0 (asked for
        # and negligible) both mean the correction is the exact identity
        mu_r=float(geom.mu_r or 0.0),
        # None and 0.0 are *different* here — see the field comment
        mu_t=None if geom.mu_t is None else float(geom.mu_t),
        mode=mode, phases=phases,
        fixed_background=fixed,
        bkg_paths=bkg_paths, bkg_design=design, bkg_penalty=penalty,
        component_paths=component_paths,
        peak_components=peak_components,
        shape=instrument.profile.shape,
        # Rietveld-only, for the reason preferred orientation is: Le Bail and
        # Pawley intensities are extracted from the data and would absorb any
        # smooth θ-dependent factor, leaving the parameters unidentifiable.
        roughness=(geom.surface_roughness.kind
                   if geom.surface_roughness is not None and mode == "rietveld"
                   else None),
        pawley=pawley, restraints=restraints,
        restraint_weight_scale=float(restraint_weight_scale),
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
    off_data: list[int] = []
    offset = 0
    for cp in phases:
        n = len(cp.reflections)
        phase_slices.append((offset, offset + n))
        if cp.tt_primary is not None and n:
            for g in _overlap_groups(cp.tt_primary, cp.fwhm_primary):
                groups.append([offset + k for k in g])
        if cp.off_data is not None:
            off_data.extend(offset + int(k) for k in np.flatnonzero(cp.off_data))
        offset += n
    return PawleyBlock(n=offset, phase_slices=phase_slices, groups=groups,
                       off_data=off_data)


def seed_phase_scales(structure: Structure, instrument: Instrument,
                      pattern: PatternData, *,
                      mode: Mode = "rietveld") -> float:
    """Match the summed calculated intensity to the data, split evenly.

    Deterministic, and it keeps a first stage inside the softplus transform's
    live range: a scale orders of magnitude off is the most common reason a
    first stage goes nowhere, and it is what a model assembled from somewhere
    *else* usually arrives with — every code's scale factor carries its own
    normalisation (on one committed pattern GSAS-II's converged scale is
    3.77e-2 and TOPAS's 2.61e-6, for the same specimen), so a scale read out of
    a foreign document is a *start* and not a measurement.

    Mutates ``structure`` in place and returns the ratio applied.  Two callers
    and one authority: :mod:`rietx.viz.compare`, which assembles a standard
    from a phase library, and :func:`rietx.io.recipe.read_recipe`, which
    assembles one from another code's recipe.
    """
    from ..params.vector import ParameterTable

    if not structure.phases:
        return 1.0
    model = compile_model(structure, instrument, pattern, mode=mode)
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    obs = np.asarray(pattern.intensity, dtype=float)
    ratio = float((obs.sum() - obs.min() * len(obs)) / max(float(y.sum()), 1e-9))
    for ph in structure.phases:
        ph.scale.value *= ratio / len(structure.phases)
    return ratio
