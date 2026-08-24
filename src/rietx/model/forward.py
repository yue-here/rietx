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
    interpolate_fixed,
    second_difference_matrix,
)
from ..crystallography.adp import U_NAMES, reciprocal_axis_lengths
from ..crystallography.dispersion import resolve as resolve_dispersion
from ..crystallography.lattice import (
    cell_volume,
    d_spacings,
    reciprocal_metric_tensor,
    two_theta_deg,
)
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
)
from ..schemas.common import Mode
from ..schemas.instrument import (
    CAPILLARY_OFFSETS,
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
    #: since WP-1128, so :meth:`line_lambdas` reads the decoded values and
    #: falls back to this tuple.  A free λ therefore moves peaks inside a stage
    #: while the windows stay put, which is the same bargain the cell already
    #: strikes — legitimate while the motion is small against the window slack,
    #: and it is (215 ppm of λ is 0.09° at 2θ = 150° with a 0.30° FWHM).
    line_wavelengths: tuple[float, ...]
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
    # P-spline smoothness penalty: extra residual rows √λ·D₂·c, already scaled
    # (columns aligned with bkg_paths); None for penalty-free backgrounds
    bkg_penalty: np.ndarray | None
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
        # stacked, not np.array-ed: the coefficients come from θ (traced)
        xp = get_backend()
        coeffs = xp.stack([values[p] for p in self.bkg_paths])
        y = xp.matmul(coeffs, self.bkg_design)
        if self.fixed_background is not None:
            y = y + xp.asarray(self.fixed_background, dtype=np.float64)
        return y

    def penalty_residual(self, values: dict[str, float]) -> np.ndarray | None:
        """√λ·D₂·c rows appended to the residual (P-spline smoothness)."""
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

        The wavelength became a table entry in WP-1128 (a joint fit may free all
        but one of them), so the residual must not read the compile-time tuple.
        ``.get`` rather than ``[]`` because ``phase_peaks`` is public and is
        called with hand-built value dicts by plots, exporters and replay; a
        dict that does not mention λ means "the instrument's λ", which is the
        frozen value.
        """
        return [values.get(f"instrument.source.lines.{il}.wavelength", lam)
                for il, lam in enumerate(self.line_wavelengths)]

    def _cell_block(self, cp: "CompiledPhase", cell: tuple, lams: list):
        """(d, [2θ_Bragg per emission line]) — the cell and λ together.

        One block rather than two memo slots because they share their input and
        every caller wants both: the line positions are ``two_theta_deg(d, λ)``
        and nothing else enters them.  ``d`` depends on the cell alone; the
        per-line angles are where λ enters the model at all, which is why a free
        λ moves every peak of its histogram and nothing else does.
        """
        d = d_spacings(cp.reflections.hkl, *cell)
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
            # column perturbing a width or the background reuses it
            f2 = self._memo(
                cp, "f2", lambda: (cell_key(), self._atom_key(ip, values)),
                lambda: structure_factors_squared(
                    cp.reflections.hkl, d, cp.sites,
                    *self._site_values(ip, values, cell)))
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
        return self.background(values) + self.bragg_component(values, intensities)

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
        # factor G = E + x·dE/dx (see model/extinction.py) — at ext=0, x=0
        # makes G exactly 1 (purity (b)), so the stage that cannot move ext off
        # zero skips it exactly as ``phase_peaks`` does, and every other stage
        # applies it unconditionally.  Only these pure-analytic columns need it
        # explicitly; the scale/occ/biso/cell/extinction columns pick it up
        # from the FD-of-phase_peaks chain.
        ext = values[f"phases.{ip}.extinction"]
        f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                       xyz, occ, biso, uaniso, astar)
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
        d = d_spacings(cp.reflections.hkl, *cell)
        xyz, occ, biso, uaniso, astar = self._site_values(ip, values, cell)
        f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                       xyz, occ, biso, uaniso, astar)
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
            net = xp.maximum(self.y_obs - bkg, 0.0)

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
        net = np.maximum(np.asarray(self.y_obs, dtype=np.float64) - bkg, 0.0)

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
            d = d_spacings(cp.reflections.hkl, *cell)
            f2 = np.asarray(structure_factors_squared(
                cp.reflections.hkl, d, cp.sites,
                *self._site_values(ip, values, cell)), dtype=np.float64)
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
    lam_gen = min(lams)  # smallest λ → smallest 2θ → largest d-sphere needed
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
        refl = generate_reflections(phase.space_group, cell, lam_gen,
                                    two_theta_max=hi_eff, two_theta_min=gen_min)
        f_anom = None
        if disp is not None:
            f_anom = resolve_dispersion([a.species for a in phase.atoms], lams,
                                        disp.overrides)
        # The source decides the radiation, exactly as it decides f_anom: a
        # neutron source resolves bound coherent scattering lengths instead of
        # X-ray form factors, and the two are mutually exclusive.
        sites = compile_phase_sites(
            phase, f_anom,
            neutron=(instrument.source.kind == "neutron_cw"))

        n = len(refl)
        n_lines = len(lams)
        win = np.zeros((n_lines, n, 2), dtype=np.int64)
        fcj_n = np.zeros((n_lines, n), dtype=np.int64)
        tt_primary = fwhm_primary = None
        # Stephens anisotropic strain: freeze the quartic monomials and take
        # the width estimate *with* Λ, so a direction that is three times
        # broader than the isotropic average still gets a wide enough window.
        # No sizing floor (cf. AXIAL_SIZING_FLOOR): Λ cannot start at zero —
        # freeing an all-zero block is rejected in ``params.vector`` — and the
        # 30·FWHM margin absorbs the growth a stage can produce from there.
        strain_monomials = aniso_est = None
        if phase.microstrain is not None:
            strain_monomials = monomial_matrix(refl.hkl)
            aniso_est = strain_width_deg(
                strain_monomials, np.array(phase.microstrain.values()),
                d_spacings(refl.hkl, *cell))
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
                           strain_monomials=strain_monomials)
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
        # March-Dollase preferred orientation acts on *calculated* structure-
        # factor intensities, so it is a Rietveld-mode correction only — Le Bail
        # and Pawley intensities are empirical and would absorb it.  Freeze the
        # symmetry orbit of each reflection here; the angles follow the cell.
        if mode == "rietveld" and phase.preferred_orientation is not None and n:
            orbits = reflection_orbits(phase.space_group, refl.hkl)
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
    restraints = CompiledRestraints(restraint_items) if restraint_items else None

    return CompiledModel(
        tt=tt, y_obs=y_obs, sigma=sigma, tt_min=tt_min, tt_max=tt_max,
        wavelength=instrument.source.primary_wavelength,
        line_wavelengths=lams,
        geometry_kind=geom.kind, radius_mm=geom.goniometer_radius_mm,
        # frozen for the stage; None (nothing asked for) and 0.0 (asked for
        # and negligible) both mean the correction is the exact identity
        mu_r=float(geom.mu_r or 0.0),
        # None and 0.0 are *different* here — see the field comment
        mu_t=None if geom.mu_t is None else float(geom.mu_t),
        mode=mode, phases=phases,
        fixed_background=fixed,
        bkg_paths=bkg_paths, bkg_design=design, bkg_penalty=penalty,
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
    offset = 0
    for cp in phases:
        n = len(cp.reflections)
        phase_slices.append((offset, offset + n))
        if cp.tt_primary is not None and n:
            for g in _overlap_groups(cp.tt_primary, cp.fwhm_primary):
                groups.append([offset + k for k in g])
        offset += n
    return PawleyBlock(n=offset, phase_slices=phase_slices, groups=groups)
