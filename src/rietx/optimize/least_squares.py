"""Weighted least squares: the Jacobian, the two drivers and the esds.

The default driver is the bounded Levenberg-Marquardt of :mod:`.lm`; scipy's
Trust Region Reflective is ``solver="trf"`` (:data:`SOLVERS`).

Minimises  S(θ) = Σ_i w_i (y_obs,i − y_calc,i(θ))²,  w_i = 1/σ_i²
(Rietveld 1969; weights per counting statistics — see PatternData.sig).

The Jacobian is assembled column-by-column, preferring exact work over
full-model finite differences:

* **linear columns** — Chebyshev background coefficients (design-matrix rows);
* **peak-chain columns** — every parameter whose effect flows through the
  per-peak scalars (position, Γ, η, intensity): cell constants, zero shift,
  displacement/transparency, Caglioti U V W, size/strain X Y, scales,
  occupancies, Biso, polarization, emission-line weights.  The expensive
  per-point part uses the analytic profile derivatives
  (``CompiledModel.derivative_bases``); the per-reflection scalar derivatives
  are finite-differenced through ``phase_peaks`` (cheap — no per-point work);
* **site-DOF columns** — Wyckoff coordinate and anisotropic-ADP DOFs, whose
  ∂|F|²/∂p is analytic over the frozen op subsets and chains through the
  site's constraint directions;
* **axial columns** — S/L, H/L through the analytic node-weighted bases;
* **plain forward differences** — anything else (fallback only).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import numpy as np
from scipy.optimize import least_squares

from ..backend import get_backend
from ..backend.api import TORCH_DEVICES
from ..backend.linalg64 import get_precision_policy, require_fp64, to_host_fp64
from ..crystallography.adp import U_NAMES
from ..crystallography.lattice import DegenerateCellError
from ..crystallography.magnetic.moments import (
    MOMENT_DIRECTION_SUPPORT,
    MOMENT_DOF_PATH,
)
from ..crystallography.spherical_harmonics import reflection_directions
from ..crystallography.stephens import S_NAMES
from ..model import rows as row_layout
from ..model.forward import PHASE_SUPPORT_SIGMA, CompiledModel, DerivativeBases
from ..model.forward import accumulate_planes as _accumulate
from ..model.origin import origin_partials
from ..model.restraints import restraint_partials
from ..params.vector import (
    FLOOR_SEEDS,
    ParameterTable,
    is_variable_path,
    size_cap,
    strain_cap,
)
from ..schemas.results import MomentAngleTest
from . import blocked, lapack
from .blocked import BlockJacobian
from .cancel import RefinementCancelled
from .lm import FTOL

if TYPE_CHECKING:
    from ..params.multi import MultiParameterTable
    from . import lm as lm_mod

#: Available minimisers.  ``"lm"`` is the bounded Levenberg-Marquardt of
#: :mod:`.lm` (WP-0601): bounds enforced inside the linear solve, an exact
#: step inside them (WP-1937), and linear inequalities on *functionals* of θ
#: (the Stephens strain positivity cone, the Γ_G² floor) that a box cannot
#: express, held inside the same step when one binds (WP-1938 D8).
#: ``"trf"`` is scipy's Trust Region Reflective, the default until WP-1938
#: and the driver every acceptance number before it was measured with.  From
#: a poor start it can end in a basin LM leaves: on issue #900's synthetic
#: PbSO₄ (scale 2400× high, everything free in one stage) TRF stops on
#: ``max_iter`` at χ² 4.5e5 with Pb Biso 133, where LM reaches 7111 and 1.48.
SOLVERS = ("trf", "lm")

#: The driver a fit runs when the caller names none (WP-1938).  Every
#: signature defaulting ``solver=`` reads this one constant.  It moved with the
#: physical coordinates because each half alone was worse than the pair it
#: replaced, TRF over the softplus coordinates before WP-1938: on WP-1937's
#: grid of 14 acceptance fits, physical + LM left one fit's minimum unsettled,
#: softplus + TRF three, physical + TRF four and softplus + LM seven.
DEFAULT_SOLVER = "lm"

#: Wyckoff site DOFs — coordinates (``dof``, tied to x, y, z) and anisotropic
#: ADPs (``adp``, tied to the six U^ij).  Both get analytic columns that chain
#: the structure-factor derivative through the site's constraint directions.
_STRUCTURAL_PATH = re.compile(r"^phases\.(\d+)\.atoms\.(\d+)\.(dof|adp)\.\d+$")
#: March-Dollase coefficient — an analytic intensity-multiplier column
#: (``po_intensity_grad``), not the peak-chain FD path.
_PO_PATH = re.compile(r"^phases\.(\d+)\.preferred_orientation\.r$")
#: Spherical-harmonics texture coefficient (WP-1960): P is affine in it, so
#: its column is analytic (``texture_intensity_grad``) and exact at any step.
_TEXTURE_PATH = re.compile(r"^phases\.(\d+)\.texture\.c\d+_(?:neg)?\d+$")
#: Phase scale — the one parameter the intensity is *exactly linear* in, so
#: its column needs no perturbed ``phase_peaks`` at all (``_scale_column``).
_SCALE_PATH = re.compile(r"^phases\.(\d+)\.scale$")

#: Residual evaluations per accepted iteration that TRF's budget must allow
#: for, so that a run genuinely needing ``max_iter`` iterations is never cut
#: short.  scipy exposes no iteration cap — only ``max_nfev`` — and an
#: iteration costs one evaluation plus one per rejected trial point.
#:
#: **Measured**, not assumed: 28 stages across four real protocols (the QPA
#: round-robin cpd-2 texture protocol, cpd-1a, and 11-BM NAC in both Le Bail
#: and Rietveld) give nfev/njev median 1.11, p90 1.64, worst 3.20.  Rounded up
#: from the worst case.
#:
#: The multiplier this replaced was ``n_params``, which priced a
#: *finite-difference* Jacobian — n_params evaluations per iteration — and no
#: finite-difference column is built for any common parameter family any more
#: (WP-1109 retired-item 1 counted zero across five NAC stages).  At 42 free
#: parameters that made ``max_iter=100`` a ~4200-evaluation budget, roughly 30x
#: what its name says, which is what let a diverging pattern spend ten minutes
#: before giving up.  This is CLAUDE.md's "runaway guard, never a timer": every
#: converging fit measured stays an order of magnitude inside it.
NFEV_PER_ITERATION = 4

#: Convergence tolerances handed to TRF alongside ``ftol``.  Four orders below
#: scipy's own 1e-8 default, and **deliberately not loosened** — named here so
#: the number has one home and the measurement that keeps it has somewhere to
#: live (WP-1109 tried 1e-8 and put it back).
#:
#: It is not the free hygiene it looks like.  It is not even a speed win: 1e-8
#: measured 1.22-1.27x faster on the IUCr cpd-1a protocol but 1.04x *slower* on
#: the QPA-acceptance cpd-2 one, because an earlier stage stops sooner at a
#: worse point and a later stage then takes more iterations to recover. And it
#: is not answer-preserving: it takes ``test_acceptance_stephens``'s isotropic
#: control past a shipped bar — corundum's reported strain anisotropy 3.64
#: against a < 2.0 assertion, on a specimen whose whole role is to come back
#: isotropic so the brucite result beside it means something. The strain still
#: reads undetected with r2 = 0.41, so the conclusion survives; the quotable
#: ratio does not, which is the distinction that matters for a number a
#: reader would cite.
#:
#: Read that as a statement about how well determined a nearly-isotropic
#: strain tensor is, not about TRF. Loosening these is a real change to the
#: answer on the ill-conditioned directions, so it needs its own evidence,
#: not a tidy-up.
XTOL = GTOL = 1e-12

#: Paths whose whole effect on the pattern is a peak's **integrated
#: intensity**: the peak keeps the position, width and mixing it had, so
#: ∂pos/∂p, ∂Γ/∂p and ∂η/∂p are identically zero and the three profile
#: partials they multiply are never read.  A stage that frees only these can
#: ask ``derivative_bases(profile_derivs=False)`` and skip building them.
#:
#: This is a claim about what a parameter *name* reaches, so it is written the
#: safe way round: an **allow**-list of the intensity-only families, with
#: everything unrecognised — a new parameter included — falling through to the
#: full bases.  Getting the inverse list wrong would cost a silently short
#: column; getting this one wrong costs only the work it was meant to save.
#: The claim is verified where it is used, in ``_peak_chain_column``.
_INTENSITY_ONLY = (
    re.compile(r"^phases\.\d+\.(scale|extinction)$"),
    # every atom parameter: x/y/z and their Wyckoff DOFs, occupancy, Biso and
    # the ADP components — all of them enter through |F|² alone
    re.compile(r"^phases\.\d+\.atoms\.\d+\."),
    re.compile(r"^phases\.\d+\.preferred_orientation\.r$"),
    re.compile(r"^phases\.\d+\.texture\."),
    # a line weight and the polarization ratio scale the intensity of a peak
    # that is already placed.  The line's ``wavelength`` beside it is a table
    # entry since WP-1134 and is deliberately **absent** from this list: λ moves
    # every peak of its histogram (2θ = 2·asin(λ/2d)), so it needs the position,
    # width and mixing partials.  Spelled ``\.weight$`` rather than as a
    # ``lines\.\d+\.`` prefix precisely so the wavelength cannot be swept in.
    re.compile(r"^instrument\.source\.lines\.\d+\.weight$"),
    re.compile(r"^instrument\.polarization$"),
)


def _intensity_only(path: str, bkg_cols: dict[str, int]) -> bool:
    """Whether ``path`` can be refined without any peak moving or reshaping.

    Background coefficients qualify trivially — they never touch a peak at all
    — which is what lets a background-plus-scale stage skip the bases outright.
    An additive background peak (``instrument.extra_components.i.…``) qualifies
    the same way and for the same reason: it is a term *added* to the pattern,
    so ∂pos/∂p, ∂Γ/∂p and ∂η/∂p of every Bragg peak are identically zero.  It
    is spelled here rather than left to fall through because the fall-through
    is only *slow*, not wrong — a stage freeing nothing but a hump would build
    two FCJ node generations per (line, reflection) per iteration and multiply
    all three partials by zero.
    """
    return (path in bkg_cols
            or path.startswith("instrument.extra_components.")
            or any(p.match(path) for p in _INTENSITY_ONLY))


#: scipy ``least_squares`` termination codes as tokens (its docs, `status`):
#: which tolerance fired, for :attr:`LSQOutcome.termination`.
_TRF_TERMINATION = {-1: "invalid_input", 0: "max_nfev", 1: "gtol", 2: "ftol",
                    3: "xtol", 4: "ftol+xtol"}


@dataclass
class LSQOutcome:
    theta: np.ndarray            # table free vector only (never the aux block)
    cost_initial: float
    cost_final: float
    n_iterations: int
    status: str  # "converged" | "max_iter" | "diverged"
    #: table columns only (guards read this); a joint fit's data rows, as a
    #: :class:`~.blocked.BlockJacobian` where :attr:`jacobian_layout` is
    #: ``"blocked"``
    jac: np.ndarray | BlockJacobian | None
    stderr_internal: np.ndarray | None
    correlation: np.ndarray | None
    #: length of the appended Pawley intensity block (its esds land on
    #: ``model.pawley.stderr``, its values in the per-phase buffers)
    n_aux: int = 0
    #: which driver produced this — "trf" (scipy, the reference) or "lm"
    solver: str = DEFAULT_SOLVER
    #: steps the bounded-LM driver held on a linear-inequality constraint (the
    #: Stephens strain cone, the Γ_G² floor), each solved over the box and the
    #: rows together (WP-1938 D8).  0 under TRF, which has no such vocabulary —
    #: see ``optimize/lm.py``.
    n_constraint_truncations: int = 0
    #: the same count by the label of each block the box-only step crossed
    #: (:attr:`.lm.LMOutcome.truncated_by`); empty under TRF and in a joint fit
    truncated_by: dict[str, int] = field(default_factory=dict)
    #: McCusker et al. (1999) §7's convergence quantity, measured over the
    #: final accepted step with both sides in external parameter units — see
    #: :func:`_final_shift_over_esd`.  ``None`` when it cannot be measured (no
    #: accepted step, or no esds), never zero.  ``refine`` copies this onto
    #: ``Statistics.max_shift_over_esd``; nothing else derives it (WP-1076).
    max_shift_over_esd: float | None = None
    #: *which* criterion ended the solve (WP-1113) — the ``status`` string
    #: above says only whether it converged, and the evaluation-count work
    #: needs the difference between "the cost stopped moving" (ftol), "the
    #: step stopped moving" (xtol) and "the gradient vanished" (gtol): a
    #: linear-rate tail rides exactly one of them.  TRF: scipy's status code
    #: as a token (``ftol``/``xtol``/``gtol``/``ftol+xtol``/``max_nfev``).
    #: LM: :attr:`~.lm.LMOutcome.termination`.  ``""`` only on the
    #: zero-parameter early return, where no criterion was ever consulted.
    termination: str = ""
    #: trial cells refused as degenerate on *either* evaluation path (see
    #: ``crystallography.lattice.DegenerateCellError``, issue #283) rather
    #: than warning about and returning NaN.  ``Cell``'s six parameters
    #: declare no bounds of their own (deliberately -- a physical bound there
    #: is a design decision for the cell-window machinery, not shipped by
    #: this change), so an underdetermined cell stage can reach a degenerate
    #: metric often, not rarely; a nonzero count is the ordinary outcome on
    #: such data, pushed back out rather than crashing -- see
    #: ``_DegenerateCellGuard`` and ``_DegenerateCellJacobianGuard`` below,
    #: which share this one counter so the field means "every degenerate
    #: probe this stage made", not "every degenerate residual call".  Both
    #: solver entry points wrap both closures, so "either path" is a claim
    #: about the package and not about one of them: a joint refinement reaches
    #: ``d_spacings`` through the same ``_make_residual``/``_jacobian_for``
    #: pairs, stacked (:func:`run_multi_least_squares`).
    #: ``LSQOutcome`` itself
    #: is an internal dataclass, never serialised; ``refine.py`` and
    #: ``multi.py`` copy this onto the (pydantic)
    #: ``StageResult.n_degenerate_cell_probes``, carried by
    #: ``SCHEMA_VERSION`` 0.19 → 0.20 (see ``schemas/common.py``).
    n_degenerate_cell_probes: int = 0
    #: decompositions this solve and its esds repeated with LAPACK's
    #: QR-iteration driver because the divide-and-conquer one did not converge
    #: (:mod:`.lapack`), copied onto ``StageResult.n_lapack_fallbacks``
    n_lapack_fallbacks: int = 0
    #: cos of the angle between the residual and each Jacobian **column**,
    #: ``gₖ / (‖J:,ₖ‖·‖r‖)`` with ``g = Jᵀr`` the gradient of ½‖r‖²; signed,
    #: in [−1, 1], **table columns only**, so it indexes like :attr:`theta`.
    #: The rows are the whole augmented system (data, background penalty and
    #: restraints alike), because the cost the driver minimised is the one
    #: whose stationarity is being read.
    #:
    #: WP-1434 is the consumer, and the quantity is chosen rather than
    #: inherited.  At an *unconstrained* stationary point the normal equations
    #: put ``Jᵀr = 0``, so every free column is orthogonal to the residual and
    #: every entry here is 0.  A column that is **not** orthogonal is being
    #: held by something other than optimality, and for a column sitting at a
    #: declared limit that something is the limit: the sign says which way the
    #: solver would still move it, and the magnitude says how hard.  Distance
    #: to the limit cannot say this, because TRF keeps its iterates strictly
    #: feasible and where a boundary solution lands is a function of when the
    #: solver stopped (issue #273).  Measured on the WP's fixtures: 1.5e−2 to
    #: 2.1e−1 over 32 genuinely-binding cases against 5.0e−10 at a free
    #: optimum, seven orders where the distance gives none.
    #:
    #: Dimensionless by construction, so it is comparable across parameters
    #: whose units are not, and it is the same definition under both drivers
    #: rather than scipy's ``optimality``, which is Coleman-Li-scaled and
    #: which the ``lm`` driver does not produce at all.  Both drivers fill it
    #: from the ``jac``/``fun`` pair they each already return (WP-1076: a
    #: declared field names its writer); ``None`` only where :attr:`jac` is,
    #: at the zero-parameter early return.  See Nocedal & Wright, *Numerical
    #: Optimization* 2nd ed. ch. 12 and 16: an active set is identified by the
    #: multiplier, never by proximity.
    residual_cosine: np.ndarray | None = None
    #: the driver's own active set, **table columns only** (indexes like
    #: :attr:`theta`): −1 held at the lower bound, +1 at the upper, 0 neither,
    #: scipy's ``active_mask`` convention (WP-1937).  The two drivers differ in
    #: how much it can know.  ``lm`` is exact: the variable sits *on* its
    #: bound and the gradient there pushes outward, so its multiplier is
    #: positive (:attr:`.lm.LMOutcome.active_mask`).  That holds up to
    #: ``lm.BVLS_MAX_COLUMNS``; a larger system (a Pawley block) takes the
    #: projected-CG step (WP-1953), whose budgeted solve can stop short of a
    #: bound the exact one would reach.  ``trf`` reports scipy's
    #: mask, set within ``XTOL`` of a bound whatever the gradient, because its
    #: iterates stay strictly inside; a width TRF parks 7.6e-6 above its floor
    #: (WP-1929, brucite) is not in it.  ``None`` only at the zero-parameter
    #: early return.  WP-1929's at-bound flag is the reader it was built for.
    active_bounds: np.ndarray | None = None
    #: ``repr`` of the ``LinAlgError`` the esd computation raised *after* the
    #: solve returned, or ``None`` when it did not (WP-1333, issue #225).  A
    #: failed eigensolve is not a failed fit: :attr:`theta` is the solver's
    #: answer either way, and only :attr:`stderr_internal`/:attr:`correlation`
    #: are absent — the ``float | None`` every esd downstream already is.
    #: Written by :func:`_guarded_covariance`, the one place both solver entry
    #: points reach ``covariance_estimates`` through; ``refine`` turns it into
    #: ``COVARIANCE_UNAVAILABLE`` naming the stage.
    covariance_error: str | None = None
    #: the Bérar-Lelann factor :attr:`stderr_internal` was multiplied by,
    #: measured on this solve's own last residual (WP-2002, B4).  Written by
    #: :func:`_guarded_covariance` beside the esds, so it is ``None`` exactly
    #: where :attr:`stderr_internal` is.  ``refine`` and ``multi`` divide each
    #: row's esd by it for ``RefinedParameter.stderr_uncorrected``.
    esd_inflation: float | None = None
    #: the stationary-angle test's rounds (WP-1929,
    #: :func:`stationary_angle_test`), the record ``StageResult`` copies.  A
    #: round with ``zeroed`` set names the angles whose columns this outcome's
    #: :attr:`stderr_internal` and :attr:`correlation` were computed without;
    #: :attr:`jac` keeps them.  ``None`` where no test ran: no free moment angle
    #: beside its free modulus, or no covariance computed.
    moment_angle_tests: list[MomentAngleTest] | None = None
    #: how the joint solve held its Jacobian (WP-1325): ``"dense"``, the
    #: stacked matrix every joint fit had before, or ``"blocked"``, one
    #: :class:`~.blocked.BlockJacobian` block per histogram, with its
    #: covariance by Schur complement.  :func:`run_multi_least_squares` writes
    #: it on every return, from :func:`.blocked.choose_layout`'s answer.
    #: ``None`` on the single-histogram path, which has one layout and no
    #: choice to report.
    jacobian_layout: str | None = None


def stationary_columns(outcome: LSQOutcome, free_paths: list[str]) -> list[int]:
    """The columns of ``outcome`` its covariance was computed without.

    Read off the record (:attr:`LSQOutcome.moment_angle_tests`) and indexed in
    ``free_paths``, the order ``outcome.jac`` is in.  A reader of the Jacobian
    that has to describe the same matrix the covariance inverted, such as the
    discarded-direction guard or a phase's significance, zeroes these.
    """
    tests = getattr(outcome, "moment_angle_tests", None) or []
    zeroed = [p for t in tests if t.zeroed for p in t.paths]
    index = {p: i for i, p in enumerate(free_paths)}
    return [index[p] for p in zeroed if p in index]


def covariance_jacobian(outcome: LSQOutcome, free_paths: list[str]):
    """``outcome.jac`` as its covariance saw it: :func:`stationary_columns`
    zeroed.  ``None`` where the outcome has no Jacobian."""
    if outcome.jac is None:
        return None
    return _without_columns(outcome.jac, stationary_columns(outcome, free_paths))


def rechart_outcome(outcome: LSQOutcome, theta: np.ndarray,
                    signs: np.ndarray | None,
                    free_paths: list[str] | None = None) -> LSQOutcome:
    """``outcome`` restated in the chart the table committed it in.

    ``theta`` is the committed table's ``x0()``; ``signs`` is what
    ``ParameterTable.commit`` returned.  ``None`` (nothing moved) returns
    ``outcome``.  ``free_paths`` names the columns, so that each
    :attr:`LSQOutcome.moment_angle_tests` round's ``stationary_at`` moves with
    its angle (:func:`_rechart_stationary`).  Two shapes:

    * a vector of ±1 per free column (#604): a moment block moved into its
      principal chart, the same moment in different numbers.  A Jacobian
      column and a residual cosine take the sign, a correlation takes it on
      both sides, and an esd takes none, which is why a canonicalisation can
      move no esd.
    * the square matrix T = ∂θ_old/∂θ_new (WP-1805): a rigid body's rotation
      composed into its anchor, R₀ ← Exp(δω)·R₀ and δω ← 0.  The Jacobian
      follows the chain rule, J_new = J_old·T; the covariance transforms as
      T⁻¹·Cov·T⁻ᵀ, which moves the rotation columns' esds and correlations to
      what a solve started at δω = 0 on the committed values measures; a
      residual cosine is re-read off the new columns (``‖r‖`` cancels, so the
      old cosines and column norms suffice).  Columns T leaves alone keep
      their numbers bit for bit.  A column whose esd is not finite (one that
      measured nothing) cannot be carried through T⁻¹, so the block holding
      it keeps its old esds and correlations.
    """
    if signs is None:
        return outcome
    s = np.asarray(signs, dtype=np.float64)
    tests = _rechart_stationary(outcome, theta,
                                np.diag(s) if s.ndim == 2 else s, free_paths)
    if s.ndim == 2:
        return replace(_rechart_matrix(outcome, theta, s),
                       moment_angle_tests=tests)

    def padded(n: int) -> np.ndarray:
        # a Pawley block rides after the table columns and never moves
        return np.concatenate([s, np.ones(n - len(s))]) if n > len(s) else s[:n]

    jac = outcome.jac
    if isinstance(jac, BlockJacobian):
        jac = jac.scaled_columns(padded(jac.shape[1]))
    elif jac is not None:
        jac = np.asarray(jac) * padded(np.shape(jac)[1])
    corr = outcome.correlation
    if corr is not None:
        p = padded(np.shape(corr)[0])
        corr = np.asarray(corr) * np.outer(p, p)
    cosine = outcome.residual_cosine
    if cosine is not None:
        cosine = np.asarray(cosine) * padded(len(cosine))
    return replace(outcome, theta=np.asarray(theta, dtype=np.float64), jac=jac,
                   correlation=corr, residual_cosine=cosine,
                   moment_angle_tests=tests)


def _rechart_stationary(outcome: LSQOutcome, theta: np.ndarray,
                        slope: np.ndarray, free_paths: list[str] | None
                        ) -> list[MomentAngleTest] | None:
    """``outcome.moment_angle_tests`` with ``stationary_at`` in the new chart.

    A chart move is affine per angle with slope ±1 (a whole turn, or a
    reflection that negates and shifts), so a point ``d`` from the old value
    lands ``slope·d`` from the new one.  Unchanged without ``free_paths``.
    """
    tests = outcome.moment_angle_tests
    if not tests or free_paths is None:
        return tests
    index = {p: i for i, p in enumerate(free_paths)}
    old = np.asarray(outcome.theta, dtype=np.float64)
    new = np.asarray(theta, dtype=np.float64)

    def moved(p: str, v: float) -> float:
        i = index.get(p)
        if i is None or i >= len(slope):
            return v
        return float(new[i] + slope[i] * (v - old[i]))

    return [t.model_copy(update={"stationary_at": {
        p: moved(p, v) for p, v in t.stationary_at.items()}}) for t in tests]


def _rechart_matrix(outcome: LSQOutcome, theta: np.ndarray,
                    t: np.ndarray) -> LSQOutcome:
    """:func:`rechart_outcome` for a square chart matrix ``t`` (its docstring)."""
    def padded(n: int) -> np.ndarray:
        # a Pawley block rides after the table columns and never moves
        if n <= len(t):
            return t[:n, :n]
        out = np.eye(n)
        out[:len(t), :len(t)] = t
        return out

    # a column is touched wherever T differs from a signed identity: an
    # off-diagonal entry, or a diagonal one that is not ±1 (a rotation DOF
    # held beside a turn about its neighbour's axis scales its own column,
    # with nothing off the diagonal; #801)
    off = np.abs(t - np.diag(np.sign(np.diag(t))))
    touched = np.flatnonzero(off.sum(axis=0) + off.sum(axis=1) > 0.0)
    jac_old = outcome.jac
    if isinstance(jac_old, BlockJacobian):
        jac = jac_old.matmul_chart(padded(jac_old.shape[1]))
    else:
        jac = None if jac_old is None else np.asarray(jac_old) @ padded(np.shape(jac_old)[1])
    stderr, corr = outcome.stderr_internal, outcome.correlation
    if stderr is not None:
        se = np.asarray(stderr, dtype=np.float64)
        tm = padded(len(se))
        if np.all(np.isfinite(se[touched])):
            c = np.eye(len(se)) if corr is None else np.asarray(corr, dtype=np.float64)
            cov = c * np.outer(se, se)
            cov = np.where(np.isfinite(cov), cov, 0.0)
            tinv = np.linalg.inv(tm)
            new = tinv @ cov @ tinv.T
            se_new = se.copy()
            se_new[touched] = np.sqrt(np.diag(new)[touched])
            if corr is not None:
                with np.errstate(invalid="ignore", divide="ignore"):
                    c_new = new / np.outer(se_new, se_new)
                # only the touched rows and columns move; every other entry is
                # the old correlation, bit for bit (a diagonal flip is a sign)
                d = np.sign(np.diag(tm))
                keep = np.ones(len(se), dtype=bool)
                keep[touched] = False
                c_flip = c * np.outer(d, d)
                corr = np.where(np.outer(keep, keep), c_flip, c_new)
            stderr = se_new
        elif corr is not None:
            # a correlation takes only the sign of a diagonal scale
            d = np.sign(np.diag(tm))
            corr = np.asarray(corr) * np.outer(d, d)
    cosine = outcome.residual_cosine
    if cosine is not None:
        cos = np.asarray(cosine, dtype=np.float64)
        if jac_old is None:
            cos = cos * np.sign(np.diag(padded(len(cos))))  # a cosine is scale-free
        else:
            tm = padded(len(cos))
            if isinstance(jac_old, BlockJacobian):
                norm_old = np.sqrt(jac_old.column_sumsq())
                norm_new = np.sqrt(jac.column_sumsq())
            else:
                norm_old = np.linalg.norm(np.asarray(jac_old), axis=0)
                norm_new = np.linalg.norm(jac, axis=0)
            g = (cos * norm_old) @ tm          # ∝ J_newᵀ r; ‖r‖ cancels
            with np.errstate(invalid="ignore", divide="ignore"):
                cos = np.where(norm_new > 0.0, g / norm_new, 0.0)
        cosine = cos
    return replace(outcome, theta=np.asarray(theta, dtype=np.float64), jac=jac,
                   stderr_internal=stderr, correlation=corr, residual_cosine=cosine)


def _guarded_covariance(jac, fun, n_free: int, n_data: int
                        ) -> tuple[np.ndarray | None, np.ndarray | None,
                                   float | None, str | None]:
    """:func:`covariance_estimates`, with an eigensolver failure made absent.

    Returns ``(stderr, corr, factor, None)``, ``factor`` the Bérar-Lelann
    factor ``stderr`` carries (:func:`_covariance_and_inflation`), or
    ``(None, None, None, repr(exc))`` when
    ``np.linalg.LinAlgError`` escapes the pseudo-inverse.  Issue #225 met it
    at a converged fit, pattern 78 of a 182-pattern chain, as ``Eigenvalues
    did not converge`` out of ``eigh``, and the raise discarded the answer the
    solver had already returned.  **The mechanism is not asserted here**: the
    reporter could not reduce it to a data-free case, and ill-conditioned
    synthetic Jacobians (columns at 1e-90 to 1e-200) pass through
    :func:`~.statistics.normal_covariance` without raising.  Only
    ``LinAlgError`` is caught, which is the one type an eigensolve reports
    non-convergence with; anything else is a defect and stays loud.
    """
    try:
        stderr, corr, factor = _covariance_and_inflation(jac, fun, n_free,
                                                         n_data=n_data)
    except np.linalg.LinAlgError as exc:
        return None, None, None, repr(exc)
    return stderr, corr, factor, None


def _residual_cosine(jac, fun) -> np.ndarray | None:
    """``gₖ / (‖J:,ₖ‖·‖r‖)`` per column — see :attr:`LSQOutcome.residual_cosine`.

    A zero column, or a residual that has reached exactly zero, leaves its
    entry at 0.0 rather than dividing: there is no angle to report, and 0 is
    the value that reads as "this column is not being held".
    """
    if jac is None:
        return None
    from .statistics import column_norms

    f = np.asarray(fun)
    if isinstance(jac, BlockJacobian):
        # per block, for a joint fit kept in blocks (WP-1325)
        denom = column_norms(jac) * np.linalg.norm(f)
        return np.divide(jac.rmatvec(f), denom, out=np.zeros(jac.shape[1]),
                         where=denom > 0)
    j = np.asarray(jac)
    # a column of 1e-170 squares to zero and would read as "not held" (WP-1463)
    denom = column_norms(j) * np.linalg.norm(f)
    return np.divide(j.T @ f, denom, out=np.zeros(j.shape[1]), where=denom > 0)


#: The confidence level of the stationary-angle test (WP-1929).  A set of
#: moment angles sits at a direction the symmetry fixes when Δχ² to that
#: direction, the other columns refitted, is within this point of the χ̄²
#: mixture for that many one-sided directions
#: (:func:`~.statistics.chi_bar_squared_quantile`).  The pattern is even in
#: each angle there, so "on the direction" is the boundary δ² = 0 of the
#: parameter space.  For one angle the statistic is Self & Liang's
#: ½χ²₀ + ½χ²₁ (Self, S. G. & Liang, K.-Y., 1987, *J. Am. Statist. Assoc.*
#: **82**, 605), and for several it is the χ̄² family (Shapiro, A., 1985,
#: *Biometrika* **72**, 133).  The value is
#: ``schemas.interval.PARAMETER_INTERVAL_LEVEL``'s, the level a profile
#: interval on a bound is cut at.
STATIONARY_ANGLE_LEVEL = 0.95

#: Central-difference step, in radians, for the test's angle columns and their
#: second derivatives.  ``refine._flat_rotation_axis`` takes the same step on
#: the same quantity, an angle of order one.
STATIONARY_ANGLE_STEP = 1e-4

#: Joint Gauss-Newton iterations the test spends on one round at most.  It
#: also stops at the first iteration that does not reduce the largest column.
#: On the two-site Pnma set (macOS arm64) the step reaches the floor in two or
#: three iterations from every stop, and stops improving after one beside a
#: determined angle.
STATIONARY_ANGLE_MAX_ITER = 8


@dataclass
class _StationaryPoint:
    """Where :func:`_joint_newton` drove a set of angles, and what it read."""

    theta: np.ndarray            # the best iterate, the whole of x
    ratios: np.ndarray           # each angle column over its modulus column
    reached: bool                # every ratio at or under the floor
    resid: np.ndarray            # the data residual at ``theta``
    curvature_stop: np.ndarray | None   # ∂²r/∂α_a∂α_b at the stop, (n, k, k)
    curvature_diag: np.ndarray   # ∂²r/∂α_a² at ``theta``, (n, k)


def _column_entries(tables: list[ParameterTable], col_maps: list[np.ndarray],
                   n_cols: int) -> list[dict[tuple[int, str], float]]:
    """Per column of θ, every entry it moves: ``{(table, path): coefficient}``.

    :meth:`~rietx.params.vector.ParameterTable.column_reach` composed over a
    joint fit's tables, keyed by table because two histograms' copies of one
    path are two entries.  ``col_maps[h]`` sends table ``h``'s free columns
    to θ's, as ``MultiParameterTable.col_map`` does; a single fit passes its
    one table and ``arange``.  The pattern is ``column_reach``'s and the
    coefficient is read off C, ``_column_identities``' split (#801), so a
    derived row carries 0.0.  A column no table owns (a Pawley intensity)
    reaches nothing.
    """
    out: list[dict[tuple[int, str], float]] = [{} for _ in range(n_cols)]
    for h, (table, cmap) in enumerate(zip(tables, col_maps, strict=True)):
        coef = table.constraint_block()[0].tocsc()
        for (c, reached), k in zip(enumerate(table.column_reach().values()), cmap,
                                   strict=True):
            for p in reached:
                out[int(k)][h, p] = float(coef[table._paths[p], c])
    return out


def _moment_angle_columns(entries: list[dict[tuple[int, str], float]]
                          ) -> list[tuple[int, list[int], float | None]]:
    """``(angle column, modulus columns, period)`` for every free moment angle.

    Read off what each column **moves** (:func:`_column_entries`), never off its
    name, the flatness rule of WP-1342: a caller's ``vars.X`` driving two
    sites' azimuths is a column whose name matches nothing.  A column is an
    angle when every model path it moves is a moment angle, all and never any,
    since one non-angle path breaks the evenness the test rests on.  A
    variable is dropped before that test (``is_variable_path``).  The modulus
    columns are every column moving the ``dof0`` of a site the angle moves.
    One of those sites without a modulus column leaves the angle without a
    reference for the floor, so it is no candidate and keeps its column.

    ``period`` is 2π over the coefficient C gives the angles, when they share
    one magnitude, so a Newton step landing on another image is read back to
    the nearest one.  ``None`` where they do not, or a derived row carries no
    coefficient, and the distance is then read as it lands.
    """
    def site(path: str) -> str:
        return path.rsplit(".dof", 1)[0]

    moduli: dict[tuple[int, str], list[int]] = {}
    for c, reached in enumerate(entries):
        for h, p in reached:
            if MOMENT_DOF_PATH.match(p) and p.endswith(".dof0"):
                moduli.setdefault((h, site(p)), []).append(c)
    out = []
    for c, reached in enumerate(entries):
        moved = {k: v for k, v in reached.items() if not is_variable_path(k[1])}
        if not moved or not all(MOMENT_DOF_PATH.match(p) and not p.endswith(".dof0")
                                for _, p in moved):
            continue
        sites = {(h, site(p)) for h, p in moved}
        if not all(s in moduli for s in sites):
            continue
        scale = {abs(v) for v in moved.values()}
        period = (2.0 * math.pi / scale.pop()
                  if len(scale) == 1 and 0.0 not in scale else None)
        out.append((c, sorted({j for s in sites for j in moduli[s]}), period))
    return out


def _joint_newton(resid, x: np.ndarray, r_stop: np.ndarray, idx: list[int],
                  modulus_norms: np.ndarray) -> _StationaryPoint:
    """Move the angles ``idx`` together until their columns vanish.

    Gauss-Newton on the stacked columns C(α) = ∂r/∂α, every other entry of
    ``x`` fixed: δα = −lstsq(∂C/∂α, C), central differences at
    :data:`STATIONARY_ANGLE_STEP` for C and for ∂C/∂α = ∂²r/∂α∂α.  Iterated,
    because one step leaves an error of order δ³, and joint, because two
    sites' angle columns are coupled (WP-1929's deferred measurement).  The
    best iterate is kept, by its largest column over its modulus column.  Costs
    2k² + 1 residual evaluations an iteration for k angles, the k columns
    reusing the diagonal second differences' points.
    """
    from .statistics import column_norms

    h = STATIONARY_ANGLE_STEP
    k = len(idx)

    def columns(th: np.ndarray):
        plus, minus = [], []
        for i in idx:
            tp, tm = th.copy(), th.copy()
            tp[i] += h
            tm[i] -= h
            plus.append(resid(tp))
            minus.append(resid(tm))
        c = np.column_stack([(p - m) / (2.0 * h)
                             for p, m in zip(plus, minus, strict=True)])
        return c, plus, minus

    def ratios_of(c: np.ndarray) -> np.ndarray:
        return column_norms(c) / modulus_norms

    th, r0 = x.copy(), r_stop
    c, plus, minus = columns(th)
    ratios = ratios_of(c)
    curvature_stop = None
    for _ in range(STATIONARY_ANGLE_MAX_ITER):
        if not np.all(np.isfinite(ratios)) or ratios.max() <= MOMENT_DIRECTION_SUPPORT:
            break
        m = np.empty((len(r0), k, k))
        for a in range(k):
            m[:, a, a] = (plus[a] - 2.0 * r0 + minus[a]) / h ** 2
            for b in range(a + 1, k):
                corner = {}
                for sa in (1.0, -1.0):
                    for sb in (1.0, -1.0):
                        t = th.copy()
                        t[idx[a]] += sa * h
                        t[idx[b]] += sb * h
                        corner[sa, sb] = resid(t)
                m[:, a, b] = m[:, b, a] = (
                    corner[1.0, 1.0] - corner[1.0, -1.0]
                    - corner[-1.0, 1.0] + corner[-1.0, -1.0]) / (4.0 * h ** 2)
        if curvature_stop is None:
            curvature_stop = m
        # block a of the stacked system is column a's rows: C[:, a] against
        # M[:, a, :], so C.T flattened and M with its first two axes swapped
        step = -lapack.lstsq(m.transpose(1, 0, 2).reshape(k * len(r0), k),
                                c.T.reshape(-1), rcond=None)[0]
        trial = th.copy()
        trial[idx] += step
        c_new, plus_new, minus_new = columns(trial)
        ratios_new = ratios_of(c_new)
        if not np.all(np.isfinite(ratios_new)) or ratios_new.max() >= ratios.max():
            break
        th, c, plus, minus, ratios = trial, c_new, plus_new, minus_new, ratios_new
        r0 = resid(th)
    diag = np.column_stack([(plus[a] - 2.0 * r0 + minus[a]) / h ** 2
                            for a in range(k)])
    return _StationaryPoint(
        theta=th, ratios=ratios,
        reached=bool(np.all(np.isfinite(ratios))
                     and ratios.max() <= MOMENT_DIRECTION_SUPPORT),
        resid=r0, curvature_stop=curvature_stop, curvature_diag=diag)


def _refitted_increase(jac_data: np.ndarray, angles: list[int],
                       r_stop: np.ndarray, r_point: np.ndarray) -> float:
    """Δχ² from the stop to ``r_point``, the other columns refitted linearly.

    min_β ‖r_point + J_o β‖² − min_β ‖r_stop + J_o β‖², J_o the stop's data
    Jacobian without ``angles``.  One linear step stands in for re-solving
    everything else with the angles pinned: on 96 fits it gave the full
    refit's verdict every time, its statistic at most 1.5 away (WP-1929,
    scratchpad ``case_e_linear.py``).  The columns are scaled to unit norm
    first, and one least-squares solve serves both right-hand sides, so a
    direction the cut drops is dropped from both.
    """
    from .statistics import column_norms

    if isinstance(jac_data, BlockJacobian):
        # the same minimum by eliminating each block's own columns (WP-1325)
        return blocked.refitted_increase(jac_data, angles, r_stop, r_point)
    others = np.setdiff1d(np.arange(jac_data.shape[1]), angles)
    rhs = np.column_stack([r_stop, r_point])
    j_o = jac_data[:, others]
    d = column_norms(j_o) if j_o.shape[1] else np.zeros(0)
    live = np.isfinite(d) & (d > 0.0)
    if live.any():
        j_o = j_o[:, live] / d[live]
        rhs = rhs - j_o @ lapack.lstsq(j_o, rhs, rcond=None)[0]
    return float(rhs[:, 1] @ rhs[:, 1] - rhs[:, 0] @ rhs[:, 0])


def _half_widths(curvature_diag: np.ndarray, resid: np.ndarray,
                 scale: float) -> list[float | None]:
    """Each angle's distance either side of the stationary point at which the
    data χ², everything else held, rises by ``scale`` (χ²_red·f²).

    With the column zero there, r(δ) ≈ r* + ½·r″δ², so the rise is
    (r*·r″)δ² + ¼‖r″‖²δ⁴, and δ² is the positive root of that quadratic in δ²,
    in whichever of its two forms does not cancel.  ``None`` where the angle
    has no curvature either.
    """
    out: list[float | None] = []
    for a in range(curvature_diag.shape[1]):
        m = curvature_diag[:, a]
        qa = 0.25 * float(m @ m)
        qb = float(resid @ m)
        if not (np.isfinite(qa) and np.isfinite(qb)) or qa <= 0.0:
            out.append(None)
            continue
        disc = math.sqrt(qb * qb + 4.0 * qa * scale)
        d2 = 2.0 * scale / (qb + disc) if qb >= 0.0 else (disc - qb) / (2.0 * qa)
        out.append(math.sqrt(d2) if d2 > 0.0 and np.isfinite(d2) else None)
    return out


def stationary_angle_test(resid, x: np.ndarray, jac: np.ndarray, n_data: int,
                          free_paths: list[str],
                          entries: list[dict[tuple[int, str], float]],
                          n_free: int
                          ) -> tuple[list[MomentAngleTest] | None, list[int]]:
    """Which free moment angles sit at a direction the symmetry fixes (WP-1929).

    The pattern is even in a moment's polar angle and azimuth about every
    direction the site symmetry fixes, so their columns vanish there while the
    angle is still determined by curvature.  The covariance equilibrates every
    column to unit norm (``statistics.normal_factors``), so beside such a
    direction where the solver stopped decided the other esds: the two-site
    Pnma set's moduli read 0.031 and 0.159 μ_B in full, against 0.00151 and
    0.00111 (ρ −0.24) with the angle columns left out.

    Every column moving only moment angles, beside a column moving each of
    their sites' moduli, is a candidate (:func:`_moment_angle_columns`, read
    off ``entries``, :func:`_column_entries`' answer).  A round drives the set
    to where its columns vanish (:func:`_joint_newton`), reads Δχ² there with
    the other columns refitted (:func:`_refitted_increase`) over χ²_red·f²,
    and passes the set when that is within the χ̄² cut for its size at
    :data:`STATIONARY_ANGLE_LEVEL`.  The set has reached the direction when
    every column is at most ``MOMENT_DIRECTION_SUPPORT`` of the largest of its
    sites' modulus columns.  A failing set of several drops one angle and is
    tested again, at most once per angle: the one with the largest
    ½‖∂²r/∂α²‖·δ², or the largest column where the Newton step did not reach
    the floor.  A moment tilted 0.05 rad fails jointly beside two azimuths that
    pass alone, and this is how they are separated.

    ``resid`` is the solve's residual; only its first ``n_data`` rows are read.
    ``jac`` is the solve's own Jacobian at ``x``, and ``n_free`` is P in
    χ²_red = χ²/(N − P), as :func:`covariance_estimates` counts it.  Returns
    the record, ``None`` where no angle was a candidate or χ²_red·f² is not
    positive, and the columns of ``x`` the covariance leaves out.
    """
    from .statistics import (
        berar_lelann_factor,
        chi_bar_squared_quantile,
        column_norms,
    )

    candidates = _moment_angle_columns(entries)
    if not candidates:
        return None, []
    x = np.asarray(x, dtype=np.float64)
    if isinstance(jac, BlockJacobian):
        jac_data = jac.data_rows()
    else:
        jac_data = to_host_fp64(jac)[:n_data]

    def r(th: np.ndarray) -> np.ndarray:
        return np.asarray(resid(th), dtype=np.float64)[:n_data]

    r_stop = r(x)
    chi2_red = float(r_stop @ r_stop) / max(n_data - n_free, 1)
    f = berar_lelann_factor(r_stop)
    scale = chi2_red * f * f
    if not (np.isfinite(scale) and scale > 0.0):
        return None, []
    reference: dict[int, float] = {}
    period: dict[int, float | None] = {}
    norms = column_norms(jac_data) if isinstance(jac_data, BlockJacobian) else None
    for i, moduli, p in candidates:
        m = norms[moduli] if norms is not None else column_norms(jac_data[:, moduli])
        m = m[np.isfinite(m)]
        if m.size and m.max() > 0.0:
            reference[i], period[i] = float(m.max()), p
    tested = [i for i, _, _ in candidates if i in reference]
    if not tested:
        return None, []

    rounds: list[MomentAngleTest] = []
    while tested:
        k = len(tested)
        paths = [free_paths[i] for i in tested]
        cut = chi_bar_squared_quantile(STATIONARY_ANGLE_LEVEL, k)
        try:
            point = _joint_newton(r, x, r_stop, tested,
                                  np.array([reference[i] for i in tested]))
            statistic = None
            if point.reached:
                statistic = _refitted_increase(jac_data, tested, r_stop,
                                               point.resid) / scale
                if not np.isfinite(statistic):
                    statistic = None
        except np.linalg.LinAlgError:
            # ``_guarded_covariance``'s rule (#225): a least-squares solve that
            # does not converge must not discard the answer the solver already
            # returned.  The columns stay in the covariance, as before WP-1929,
            # and the rounds that completed are the record
            break
        # An angle is 2π-periodic and a Newton step can land on another image
        # of the same direction (87π from a stop at 3.121 on Cr₂WO₆ at 4 K),
        # so every distance from the stop is read to the nearest image, in the
        # column's own period (2π/c for a variable driving angles by c)
        shift = np.array([point.theta[i] - x[i] if period[i] is None
                          else math.remainder(point.theta[i] - x[i], period[i])
                          for i in tested])
        # where the columns vanish, so a reader can see how far the stop was
        stationary_at = ({p: float(x[i] + s)
                          for p, i, s in zip(paths, tested, shift, strict=True)}
                         if point.reached else {})
        if statistic is not None and statistic <= cut:
            half = _half_widths(point.curvature_diag, point.resid, scale)
            rounds.append(MomentAngleTest(
                paths=paths, reached=True, statistic=statistic, cut=cut,
                zeroed=True, stationary_at=stationary_at,
                half_widths={p: w for p, w in zip(
                    paths, half, strict=True) if w is not None}))
            return rounds, list(tested)
        rounds.append(MomentAngleTest(paths=paths, reached=point.reached,
                                      statistic=statistic, cut=cut, zeroed=False,
                                      stationary_at=stationary_at))
        if k == 1:
            break
        if statistic is None or point.curvature_stop is None:
            drop = int(np.argmax(np.where(np.isfinite(point.ratios),
                                          point.ratios, np.inf)))
        else:
            drop = int(np.argmax([
                0.5 * float(np.linalg.norm(point.curvature_stop[:, a, a]))
                * shift[a] ** 2 for a in range(k)]))
        tested = tested[:drop] + tested[drop + 1:]
    return rounds or None, []


def _without_columns(jac, columns: list[int]):
    """``jac`` with ``columns`` zeroed, for the covariance alone.

    A zero column is the covariance's own "measured nothing": infinite
    variance, no correlation with anything, and an absent esd downstream
    (``ParameterTable.unmeasured_rows``).  The solve's Jacobian itself is
    untouched, because the residual cosine, the active set and every guard
    reading ``LSQOutcome.jac`` describe the fit as solved.
    """
    if not columns:
        return jac
    if isinstance(jac, BlockJacobian):
        return jac.without_columns(columns)
    out = np.array(to_host_fp64(jac), dtype=np.float64, copy=True)
    out[:, columns] = 0.0
    return out


def _feasible_start(x0: np.ndarray, lo: np.ndarray, hi: np.ndarray,
                    solver: str) -> np.ndarray:
    """The start each driver is handed.  TRF requires it strictly inside the
    bounds, so it is nudged 1e-12 off any it sits on.  The LM driver is handed
    it on the bound: nudged, a stage restarting from a held value takes a first
    step under the fp64 floor, stops there, and returns the value 1e-12 off
    its bound and out of :attr:`LSQOutcome.active_bounds` (WP-1937)."""
    if not len(x0):
        return x0
    if solver == "lm":
        return np.clip(x0, lo, hi)
    return np.clip(x0, lo + 1e-12, hi - 1e-12)


def _active_bounds(res, n: int) -> np.ndarray:
    """The driver's active set over its first ``n`` columns — see
    :attr:`LSQOutcome.active_bounds`.  Both result shapes carry it as
    ``active_mask``."""
    return np.asarray(res.active_mask, dtype=np.int8)[:n].copy()


def _lebail_snapshot(model: CompiledModel) -> list[np.ndarray] | None:
    """Le Bail intensities frozen for one solve (taken at closure build).

    They are constant during a least-squares run — ``lebail_update`` only runs
    between solves — so snapshotting here is what lets the residual never read
    the mutable per-phase buffers (the purity contract).
    """
    if model.mode != "lebail":
        return None
    return [np.asarray(cp.hkl_intensity, dtype=np.float64) for cp in model.phases]


class _DegenerateCellGuard:
    """Counts and neutralises :class:`DegenerateCellError` from a residual
    closure (issue #283).

    ``Cell``'s six parameters declare no bounds of their own — that half of
    #283's suggested fix is deliberately not shipped here, since the
    cell-window / tie-window machinery in :mod:`rietx.params.vector` reads an
    infinite stored bound as *no claim made* — so an underdetermined cell
    stage is free to reach a degenerate metric directly, and often does, not
    only through some narrow corner case.  scipy's ``trf`` and the
    in-package ``lm`` driver both call the residual as an opaque function and
    have no vocabulary for "this point is inadmissible, try a smaller step"
    — raising through them would crash the whole stage over one trial the
    search itself would have rejected on the next step anyway.  Returning
    ``10x`` the last *evaluated* residual (``self._last`` is overwritten on
    every successful call, including a trial the trust region goes on to
    reject, not only a point it keeps) is always worse than any point the
    driver has actually accepted, which is enough to push the trust region
    back towards the interior without inventing a value that could look like
    a fit.
    """

    def __init__(self, inner):
        self._inner = inner
        self._last: np.ndarray | None = None
        self.n_degenerate = 0

    def __call__(self, theta: np.ndarray) -> np.ndarray:
        try:
            r = self._inner(theta)
        except DegenerateCellError:
            self.n_degenerate += 1
            if self._last is None:
                # No evaluated point to penalise against yet (x0 itself was
                # degenerate) -- nothing to fall back to, so this is a
                # caller error, not a search artefact.
                raise
            return self._last * 10.0
        self._last = r
        return r


class _DegenerateCellJacobianGuard:
    """Counts and neutralises :class:`DegenerateCellError` out of a Jacobian
    closure the way :class:`_DegenerateCellGuard` does for the residual
    (issue #283, second review round).

    The residual guard above covers only its own path.  ``_make_jacobian``'s
    peak-chain columns re-derive ``phase_peaks`` at ``theta + h`` for a
    per-reflection scalar FD (:func:`_peak_chain_column`), and its declared
    fallback perturbs the whole model the same way (the ``fd_cols`` loop);
    both decode through the same ``C`` and reach ``d_spacings`` exactly as
    the residual does.  A cell parameter sits on the peak-chain branch (the
    module docstring lists it there), so an FD step off an accepted point
    close to the degeneracy boundary can cross it during differencing even
    though the point being differentiated around was itself admissible --
    the trust region has no notion of "close to the boundary" and nothing
    keeps an accepted iterate a step size away from it.  Raising
    :class:`DegenerateCellError` out of a Jacobian call crashes the stage on
    exactly the path the residual guard does not cover.

    Neutralisation returns the last successfully evaluated Jacobian rather
    than a residual-style ``10x`` penalty: neither TRF nor the in-package
    ``lm`` driver compares Jacobians to decide acceptance (both read cost
    from the residual for that), so there is no "worse" matrix to invent --
    reusing the last real one is a value the driver has actually seen, and
    the residual guard's own penalty (which trips first: scipy always
    evaluates the residual at a point before asking for its Jacobian there)
    is what does the steering.  The counter is **shared** with the residual
    guard passed in, so ``n_degenerate_cell_probes`` counts every degenerate
    probe the stage made, off either path, as one number.
    """

    def __init__(self, inner, residual_guard: _DegenerateCellGuard):
        self._inner = inner
        self._residual_guard = residual_guard
        self._last: np.ndarray | None = None

    def __call__(self, theta: np.ndarray) -> np.ndarray:
        try:
            j = self._inner(theta)
        except DegenerateCellError:
            self._residual_guard.n_degenerate += 1
            if self._last is None:
                # Mirrors the residual guard: no evaluated Jacobian to fall
                # back to yet means the very first Jacobian call already hit
                # the boundary on an FD step, which is a caller error (an x0
                # so close to degenerate that even a 1e-6-relative step
                # crosses it), not a search artefact to neutralise.
                raise
            return self._last
        self._last = j
        return j


def _make_residual(model: CompiledModel, table: ParameterTable):
    """Weighted residual, optionally augmented with a Pawley intensity block.

    In Pawley mode θ = [table θ | per-hkl intensities]; the intensity tail is
    split into per-phase slices and passed *through* the evaluation (never
    written to the buffers — those are committed once, post-solve), and the
    overlap-restraint rows are appended after the background penalty rows.

    The row *layout* is not written here: ``model.rows`` owns it, and the
    traced residuals every autodiff backend uses call the same assembler, so
    the numpy reference and the traced twins cannot disagree about block order.
    """
    sqrt_w = 1.0 / model.sigma
    n_table = len(table.free_paths)
    xp = get_backend()
    fixed_intens = _lebail_snapshot(model)
    empty_aux = np.zeros(0, dtype=np.float64)

    def residual(theta: np.ndarray) -> np.ndarray:
        if model.pawley is not None:
            aux = theta[n_table:]
            intens = model.split_pawley_intensities(aux)
            values = table.decode(theta[:n_table])
        else:
            aux = empty_aux
            intens = fixed_intens
            values = table.decode(theta)
        return row_layout.assemble(model, row_layout.ResidualInputs(
            values=values, intens=intens, theta_aux=aux,
            sqrt_w=sqrt_w, y_obs=model.y_obs, xp=xp))

    return residual


def _gather_per_line(lay, arrays) -> np.ndarray:
    """(R,) row gather of per-line arrays (``arrays[il][k]``)."""
    return lay.gather([(a,) for a in arrays], 0)


#: The relative forward-difference step every FD column of
#: :func:`_make_jacobian` is taken with, through :func:`fd_step`.
FD_STEP = 1e-6


def fd_step(theta_c: float, typical: float = 1.0) -> float:
    """The forward-difference step for one column of θ.

    ``FD_STEP · max(typical, |θ_c|)``: relative to the coordinate's size, and
    absolute at ``typical`` near zero (Dennis & Schnabel 1996, *Numerical
    Methods for Unconstrained Optimization and Nonlinear Equations*, SIAM,
    § 5.4).  Both FD sites call it, so one rule sizes every column, and
    :func:`_fd_typicals` says what ``typical`` is.
    """
    return FD_STEP * max(typical, abs(theta_c))


def _fd_typicals(table: ParameterTable,
                 identities: list[tuple[str, list[str], bool]] | None = None
                 ) -> np.ndarray:
    """Each free column's typical size, the ``typical`` of :func:`fd_step`.

    A row that is a **width** takes
    :data:`~rietx.params.vector.FLOOR_SEEDS`' size for its unit (WP-1936).
    Every other row takes 1, the step it always had.

    **Why a width needs its own size.**  The peak chain differences the
    reflection widths, and a width is curved on the scale of the peak's own
    variance, not on a scale of 1.  At 1 the step on a Caglioti term is
    absolute: on LaB₆ + cBN (11-BM, Γ² ≈ 1e-4 deg²) it put 1.4e-3 into ``v``'s
    column and 1.5e-2 into ``w``'s once ``w`` was an identity row on its
    floor, against the jax Jacobian.  At ``FLOOR_SEEDS``' sizes every width
    column on that fit and on lab brucite is within 5e-7 of jax at
    ``FD_STEP`` = 1e-6.  At 1e-7 and 1e-8 the worst is 2e-5, and it grows as
    the step shrinks, which is rounding.

    **Which rows are widths.**  A unit cannot say, because a zero shift and a
    peak position are in degrees too.  They are offsets on a 2θ of tens of
    degrees, and position is linear in them, so a small step removes no
    truncation and adds rounding: at 1e-3° the zero-shift column moved from
    2e-9 to 3e-6 against jax on every golden state.  An offset can be
    negative and a width cannot, so a row is sized as a width when its lower
    bound is at least 0.  A deg² row is a Caglioti term of a variance and is
    sized whatever its bound, since ``u`` and ``v`` may go negative.  So is
    the Lorentzian ``y`` (:data:`_SIGNED_WIDTHS`), a deg row with no floor of
    its own since 2026-10-23 (WP-2002): read off its bound it would take the
    offset's step of 1.  The test also admits a position or an angle a caller
    bounded above 0.  Its step is unchanged while |θ| exceeds the size, which
    holds for every such row the package builds.

    The size is in **column units**, which is what a stage's seed is in
    already (:meth:`~rietx.params.vector.ParameterTable.seed_floored`'s
    write), so a value-scaled joint column needs no factor.

    **A named variable with no unit of its own is sized by what it drives.**
    Its name says nothing, so the row read is the one
    :func:`_column_identities` names for the column, and the size is divided
    by that row's coefficient in C.  Read off the name, a ``vars.U`` driving
    ``u`` kept the step of 1, and on the ``sharp_widths`` state of
    ``tests/test_cross_backend.py`` its column kept the old 1.8e-3 error.
    """
    if identities is None:
        identities = _column_identities(table, _column_extras(table))
    coef = table.constraint_block()[0].tocsc()
    out = np.ones(len(table.free_paths), dtype=np.float64)
    for c, path in enumerate(table.free_paths):
        row, unit, k = path, table._units.get(path), 1.0
        if unit is None and is_variable_path(path) and identities[c][0] != path:
            row = identities[c][0]
            unit = table._units.get(row)
            k = abs(float(coef[table._paths[row], c]))
        size = FLOOR_SEEDS.get(unit)
        if (size is not None and k > 0.0
                and (table.entries[table._paths[row]].lo >= 0.0
                     or unit == "deg^2"
                     or any(row == w or row.endswith("." + w)
                            for w in _SIGNED_WIDTHS))):
            out[c] = size / k
    return out


#: Width rows in deg that may go negative, so :func:`_fd_typicals` cannot read
#: them off their lower bound.  Matched on the end of the path, which a joint
#: fit's histogram prefix leaves in place.
_SIGNED_WIDTHS = ("instrument.profile.y",)


def _peak_chain_column(model: CompiledModel, table: ParameterTable,
                       bases: DerivativeBases, theta: np.ndarray,
                       values: dict[str, float], c: int, path: str,
                       intensities: list[np.ndarray] | None = None,
                       affected: "list[int] | range | None" = None,
                       typical: float = 1.0) -> np.ndarray:
    """∂y/∂θ_c via the analytic bases + per-reflection scalar FD.

    Only the phases the column touches are re-derived (``phases.2.…`` leaves
    the others' scalars untouched; instrument paths touch all).  ``affected``
    overrides that reading of the path, and a tie is why it has to: the
    perturbed values come from ``table.decode``, so every dependent moves with
    the source whatever phase it sits in, while the phases whose scalars are
    *re-derived* here are chosen by name.  A user tie across phases would
    otherwise drop the far phase's whole contribution from the column
    (WP-1070); the caller passes the union C actually touches.
    ``intensities`` carries the lebail/pawley per-hkl vectors — the perturbed
    ``phase_peaks`` must see the same intensities as the expansion point.

    Since WP-1112 the scalar FDs are vectorised over the rows and the
    accumulation is one order-preserving scatter (:func:`~rietx.model.forward.accumulate_planes`, bit
    -identical to the per-row loop); the claim verification is unchanged — a
    term whose coefficients are nonzero under a ``profile_derivs=False``
    build still raises through :func:`_require_basis`, naming the path.
    """
    h = fd_step(theta[c], typical)
    tp = theta.copy()
    tp[c] += h
    values_p = table.decode(tp)
    if affected is None:
        affected = ([int(path.split(".")[1])] if path.startswith("phases.")
                    else range(len(model.phases)))

    parts = []
    for ip in affected:
        # WP-1343: one pass per drawn component.  ``components`` hands back
        # one entry for every phase of every fit at the default, so this loop
        # is the single ``bases.planes[ip]`` read it replaces; where a phase
        # draws its magnetic contribution on its own frozen family the second
        # pass carries the **magnetic width columns** — they move w₁ on that
        # component and nothing at all on the nuclear one, which is exactly
        # the separability the term needs to be identifiable.
        for component, pp in enumerate(bases.components(ip)):
            peaks_p = model.phase_peaks(
                ip, values_p, None if intensities is None else intensities[ip],
                component=component)
            lay = pp.layout
            if not len(lay.i0):
                continue
            pos1 = lay.gather(peaks_p, 0)
            w1p = lay.gather(peaks_p, 1)
            w2p = lay.gather(peaks_p, 2)
            int1 = lay.gather(peaks_p, 3)
            pair = pp.finite & np.isfinite(pos1)
            with np.errstate(invalid="ignore"):
                d_i = np.where(pair, (int1 - pp.inten) / h, 0.0)
                c_p = np.where(pair, pp.inten * ((pos1 - pp.pos) / h), 0.0)
                c_g = np.where(pair, pp.inten * ((w1p - pp.w1) / h), 0.0)
                c_e = np.where(pair, pp.inten * ((w2p - pp.w2) / h), 0.0)
            terms = []
            if np.any(d_i != 0.0):
                terms.append((d_i, pp.omega))
            for coef, plane, what in ((c_p, pp.d_pos, "position"),
                                      (c_g, pp.d_gamma, "width"),
                                      (c_e, pp.d_eta, "mixing")):
                if np.any(coef != 0.0):
                    _require_basis(plane, path, what)
                    terms.append((coef, plane))
            parts.append((lay, terms))
    return _accumulate(len(model.tt), parts)


def _require_basis(basis: np.ndarray | None, path: str, what: str) -> None:
    """Check the caller's ``profile_derivs=False`` claim against the scalars.

    The claim is that no free column moves a peak's position, width or mixing,
    and here is where it meets the finite differences that would say otherwise.
    Both sides recompute from the same decoded values, so an intensity-only
    parameter leaves these scalars bit-zero; a non-zero one means ``path``
    belongs to a family ``_INTENSITY_ONLY`` wrongly claims.  Raising names the
    path — the alternative, using the missing basis as zero, is exactly the
    silently-short column the FD fallback exists to prevent.
    """
    if basis is None:
        raise AssertionError(
            f"{path!r} moves a peak's {what}, but the profile-derivative bases "
            f"were skipped as if it could not — see _INTENSITY_ONLY in "
            f"optimize/least_squares.py")


def _structural_column(model: CompiledModel, table: ParameterTable,
                       bases: DerivativeBases, values: dict[str, float],
                       c: int, ip: int, j: int, rows: tuple[str, ...],
                       grad) -> np.ndarray:
    """∂y/∂θ_c for a coordinate or ADP DOF: only the intensity scalar moves.

    The constraint direction ∂p/∂θ_c is read off the affine constraint block
    (the DOF's column of C restricted to the atom's ``rows``), so the analytic
    column follows whatever site-symmetry basis WP-0301 wired — displacement
    directions for x, y, z; U^ij patterns for the six ADP components.
    """
    C, _ = table.constraint_block()
    coeffs = np.array([C[table._paths[f"phases.{ip}.atoms.{j}.{name}"], c]
                       for name in rows], dtype=np.float64)
    dint = grad(ip, j, coeffs, values)
    pp = bases.planes[ip]
    coef = np.where(pp.finite, _gather_per_line(pp.layout, dint), 0.0)
    terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
    return _accumulate(len(model.tt), [(pp.layout, terms)])


def _po_column(model: CompiledModel, bases: DerivativeBases,
               values: dict[str, float], ip: int) -> np.ndarray:
    """∂y/∂r for the March coefficient: only the intensity scalar moves.

    ``po_intensity_grad`` supplies the analytic per-(line, reflection)
    ∂intensity/∂r (P is a pure multiplier, so positions and widths are
    untouched); it is applied to the same frozen profile bases the forward
    model uses.
    """
    dint = model.po_intensity_grad(ip, values)
    if dint is None:
        return np.zeros(len(model.tt))
    # WP-1343: P is a per-(line, reflection) multiplier of the intensity and
    # is applied to **both** components identically (``phase_peaks``), so
    # ∂intensity/∂r is P's derivative times each component's own base.  The
    # analytic branch therefore covers only the split-free case, where
    # ``components`` has one entry; a split phase with texture falls through
    # ``_make_jacobian``'s dispatch to ``_peak_chain_column``, which
    # ``scalar_chain_supported`` claims for every ``phases.*`` path and which
    # finite-differences ``phase_peaks`` over every drawn component.
    pp = bases.planes[ip]
    coef = np.where(pp.finite, _gather_per_line(pp.layout, dint), 0.0)
    terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
    return _accumulate(len(model.tt), [(pp.layout, terms)])


def _texture_column(model: CompiledModel, bases: DerivativeBases,
                    values: dict[str, float], ip: int, path: str) -> np.ndarray:
    """∂y/∂C for one texture coefficient: only the intensity scalar moves.

    The March-Dollase column's construction (:func:`_po_column`), with
    ``texture_intensity_grad`` supplying ∂intensity/∂C, and its reach: a split
    magnetic phase falls through to ``_peak_chain_column`` the same way.
    """
    dint = model.texture_intensity_grad(ip, path, values)
    if dint is None:
        return np.zeros(len(model.tt))
    pp = bases.planes[ip]
    coef = np.where(pp.finite, _gather_per_line(pp.layout, dint), 0.0)
    terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
    return _accumulate(len(model.tt), [(pp.layout, terms)])


def _scale_column(model: CompiledModel, bases: DerivativeBases,
                  values: dict[str, float], ip: int) -> np.ndarray:
    """∂y/∂scale for phase ip: its own contribution, divided by the scale.

    The scale enters ``phase_peaks`` exactly once, in ``base = scale · mult ·
    |F|²``, and every factor applied after it is independent of it — the
    March multiplier, the line weight, Lp, Sabine extinction (which reads the
    *raw* ``|F|²``, never the scaled product), specimen absorption, surface
    roughness, and the mask that zeroes a reflection pushed off the sphere.
    So the intensity is exactly linear in the scale, no position or width
    moves at all, and ∂intensity/∂scale is the intensity over the scale.

    That makes this the cheapest column in the Jacobian and it was the
    **dearest** before WP-1121: the peak-chain FD perturbed the scale and
    rebuilt the phase's whole scalar chain, which on the trigger case was
    1148 columns and 3.3 % of the fit, most of it a structure-factor
    evaluation that the perturbation could not have changed.  It cost that
    much *because* it could not change anything — the memoised blocks all
    hit, so the price was the ones a neighbouring cell column had evicted.

    **Not valid at ``scale == 0``**, where the true derivative is the whole
    unscaled chain and this expression is 0/0.  A scale's lower bound of 0 is
    reachable, so the caller tests the scale and leaves a dead phase to the
    FD path, which stays correct there.
    """
    scale = values[f"phases.{ip}.scale"]
    # WP-1343: the scale enters *each* component's ``base`` exactly once and
    # multiplies both, so both parts are its own contribution over the scale.
    # One part for every phase of every fit at the default.
    parts = []
    for pp in bases.components(ip):
        coef = np.where(pp.finite, pp.inten / scale, 0.0)
        parts.append((pp.layout,
                      [(coef, pp.omega)] if np.any(coef != 0.0) else []))
    return _accumulate(len(model.tt), parts)


def _axial_column(model: CompiledModel, bases: DerivativeBases,
                  which: int) -> np.ndarray:
    """∂y/∂θ_c for S/L (which=8) or H/L (which=9) from the node-FD bases.

    The plane holds zeros at symmetric rows, so one term over all rows is
    the loop over FCJ rows with ±0 additions interleaved — bitwise neutral.
    """
    parts = []
    # WP-1343: the magnetic component's planes join the loop where they exist;
    # ``planes_mag`` is empty of them for every fit at the default, so the
    # iteration is the one over ``bases.planes`` it replaces.
    for pp in [*bases.planes, *(q for q in bases.planes_mag if q is not None)]:
        plane = pp.d_sl if which == 8 else pp.d_hl
        if plane is None:
            continue
        coef = np.where(pp.finite, pp.inten, 0.0)
        parts.append((pp.layout,
                      [(coef, plane)] if np.any(coef != 0.0) else []))
    return _accumulate(len(model.tt), parts)


def _pawley_intensity_columns(model: CompiledModel, bases: DerivativeBases,
                              values: dict[str, float], sqrt_w: np.ndarray,
                              J: np.ndarray, n_table: int, n_below: int) -> None:
    """Exact analytic columns for the Pawley intensity block.

    ``I_k`` enters y linearly and only through its own peak: ∂y/∂I_k =
    Σ_lines w_l·Ω_lk on the reflection's window (the same argument as the
    background coefficients — take the exact column, never FD).  The overlap
    restraint rows are ∂(R·I)/∂I = R, appended below the data (and background
    penalty) rows.
    """
    n_lines = len(model.line_wavelengths)
    w_lines = [values[f"instrument.source.lines.{il}.weight"] for il in range(n_lines)]
    for ip, (a, _b) in enumerate(model.pawley.phase_slices):
        for (il, k, i0, i1, omega, *_rest) in bases.entries[ip]:
            J[i0:i1, n_table + a + k] += -sqrt_w[i0:i1] * (w_lines[il] * omega)
    if model.pawley.restraint is not None:
        # bound the write to exactly the Pawley-restraint stripe: soft-restraint
        # rows (WP-0406) may sit below it, though Pawley + geometry restraints
        # never coexist (restraints are Rietveld-only)
        n_res = model.pawley.restraint.shape[0]
        J[n_below:n_below + n_res, n_table:] = model.pawley.restraint


#: Largest fraction of the Pawley intensity block's entries that may be
#: nonzero for its normal matrix to be formed sparse
#: (:func:`_pawley_normal_equations`); past it the stage keeps the dense
#: build, bit for bit the path before WP-2011.  A sparse product's work grows
#: as the square of this fraction and BLAS's not at all: measured on banded
#: windows (macOS arm64), the two break even at 0.05 both at 5 995 × 343 and
#: at 59 498 × 2 224, and at 0.2 the sparse one is 12-13× slower.  11-BM NAC's
#: candidates sit at 0.022-0.023, where the sparse build took a monoclinic
#: candidate's fit from 47 s to 34 s (one run each) against a probe that built
#: A dense and then preconditioned it.  A lab pattern's Lorentzian windows
#: reach much further: FAP.XRA's closing stage, on windows dropping 1e-3 of
#: each peak, sits at 0.38 where its other stages sit at 0.03, and there the
#: sparse build took 115 ms against 2 ms.  Past the cut the step has the
#: dense free block's exact (shifted) Cholesky factor and a projected search
#: (:func:`.bccg.projected_cg`): on lab pseudo-symmetric candidates there
#: (zircon and corundum as monoclinic, 601 and 576 columns, 0.06) the largest
#: solve took 157 and 128 products against 1204 and 1154, readings unchanged.
#: Below it the incomplete-LU path keeps its weak case: FAP as monoclinic C
#: (944 columns, 0.041) still spends a solve's whole budget, 12 s a fit.
PAWLEY_SPARSE_DENSITY = 0.05


def _pawley_tail_pattern(model: CompiledModel) -> tuple[np.ndarray, np.ndarray]:
    """Where the Pawley intensity columns of :func:`_make_jacobian` can be
    nonzero, as CSC ``(row indices, indptr)`` over the intensity block.

    A column is nonzero on its reflection's windows, one per emission line,
    and on the Pawley-restraint rows that name it.
    :func:`_pawley_intensity_columns` is its one writer, every other branch of
    :func:`_make_jacobian` writing ``[:, :n_table]``.  The windows are frozen
    at stage compile, so this reads every row of ``CompiledPhase.batch``, a
    superset of the finite rows a call writes, and never θ.
    """
    _data, _pen, pawley_blk, _restr, _origin = row_layout.layout(model)
    rows, cols = [], []
    for cp, (a, _b) in zip(model.phases, model.pawley.phase_slices, strict=True):
        lay = cp.batch
        if lay is None or not len(lay.i0):
            continue
        width = lay.width.astype(np.intp)
        first = np.repeat(np.cumsum(width) - width, width)
        rows.append(np.repeat(lay.i0.astype(np.intp), width)
                    + np.arange(int(width.sum()), dtype=np.intp) - first)
        cols.append(np.repeat(a + lay.k.astype(np.intp), width))
    if model.pawley.restraint is not None:
        r_rows, r_cols = np.nonzero(model.pawley.restraint)
        rows.append(pawley_blk.start + r_rows.astype(np.intp))
        cols.append(r_cols.astype(np.intp))
    row = np.concatenate(rows) if rows else np.zeros(0, dtype=np.intp)
    col = np.concatenate(cols) if cols else np.zeros(0, dtype=np.intp)
    # column-major and without repeats: two lines' windows of one reflection
    # overlap, and a repeated entry would be summed into the column twice
    order = np.lexsort((row, col))
    row, col = row[order], col[order]
    keep = np.ones(len(row), dtype=bool)
    keep[1:] = (np.diff(row) != 0) | (np.diff(col) != 0)
    row, col = row[keep], col[keep]
    return row, np.searchsorted(col, np.arange(model.pawley.n + 1, dtype=np.intp))


def _pawley_normal_equations(model: CompiledModel, n_table: int):
    """``(JᵀJ, −Jᵀr)`` with the intensity block sparse, for
    :func:`.lm.minimize`'s ``normal_equations`` above its BVLS cut (WP-2011).

    The pattern is :func:`_pawley_tail_pattern`'s, read once per solve.  Each
    call gathers the tail's values over it from the dense J, which stays
    whole for the covariance.  Scanning the dense J for its nonzeros instead
    cost 0.32 s of a 0.48 s build at 61 000 × 2230.  A is returned CSR, b
    dense.  ``None`` where more than :data:`PAWLEY_SPARSE_DENSITY` of the
    block is in the pattern: the driver then forms A dense, as before.
    """
    from scipy import sparse

    n_rows, n_int = row_layout.n_rows(model), model.pawley.n
    row, indptr = _pawley_tail_pattern(model)
    if len(row) > PAWLEY_SPARSE_DENSITY * n_rows * n_int:
        return None
    tail = n_table + np.repeat(np.arange(n_int, dtype=np.intp), np.diff(indptr))

    def normal_equations(J, r: np.ndarray):
        Jh = to_host_fp64(J)
        Jt = Jh[:, :n_table]
        Jp = sparse.csc_matrix((Jh[row, tail], row, indptr), shape=(n_rows, n_int))
        A_pp = (Jp.T @ Jp).tocsr()
        b = -np.concatenate([Jt.T @ r, Jp.T @ r])
        if not n_table:
            return A_pp, b
        A_pt = sparse.csr_matrix(Jp.T @ Jt)
        A = sparse.bmat([[sparse.csr_matrix(Jt.T @ Jt), A_pt.T], [A_pt, A_pp]],
                        format="csr")
        return A, b

    return normal_equations


def _column_extras(table: ParameterTable) -> list[list[str]]:
    """Per free column, the *other* physical paths it moves through C.

    Empty for a column that stands for itself alone.  Non-empty wherever a tie
    is live — the derived ones (a cubic ``b``←``a``, a Wyckoff coordinate
    behind its DOF) as much as a user's, which is what makes this a dispatch
    input rather than a special case: each analytic branch then declares the
    reach it can account for, and anything further falls to the whole-model FD
    column, which is exact because it decodes through C like the residual does.

    Read off the table's **declared** reach (``reach_block``), which is C
    itself unless a derived block is declared: a body DOF's column then also
    moves every body atom row, though no C row says so (WP-1804).
    """
    C = table.reach_block()
    free = table.free_paths
    csc = C.tocsc()
    paths = [e.path for e in table.entries]
    return [[paths[r] for r in csc.indices[csc.indptr[c]:csc.indptr[c + 1]]
             if paths[r] != free[c]]
            for c in range(len(free))]


def _column_identities(table: ParameterTable, extras: list[list[str]]
                       ) -> list[tuple[str, list[str], bool]]:
    """Per free column, the ``(path, extra, own)`` the dispatch below should read.

    Identity for every model parameter, so an unconstrained or dot-path-tied
    model dispatches exactly as it did before this existed.

    It is not the identity for a **named variable** (WP-1119), and that is the
    whole point.  Dispatch is by the free path's *name*, and a variable has a
    name no analytic branch was written for — so ``vars.B_metal`` driving four
    Biso rows fell straight to the whole-model FD column, while the same
    constraint written with ``phases.0.atoms.0.biso`` as its master took the
    peak-chain branch.  Measured on a four-site LaB6 fit, that is a column
    8.6e-7 from the analytic one and one extra full residual evaluation per
    Jacobian, for a construct whose whole claim is to be a *renaming*.

    A variable moves no residual row of its own — the forward model never reads
    a ``vars.*`` path — so what it is, for dispatch, is exactly what it reaches.
    Two cases, and the second is narrower on purpose:

    * it reaches **one** path at coefficient exactly 1: the column *is* that
      parameter's column, so every branch applies, the closed-form ones
      included.  Their formulae assume ``p = θ_c``, which is what a unit
      coefficient means.
    * it reaches several, or one at any other coefficient: only the branches
      that read their coefficients off C may have it.  Those are
      ``_peak_chain_column`` (it perturbs θ and decodes, so every coefficient
      and constant is carried) and ``_structural_column`` (it reads the atom's
      rows out of C).  The closed-form linear branches exclude themselves,
      since each requires ``own``: true where the column is its named path's
      own (nothing else reached, at coefficient 1), false for one path at any
      other coefficient, whose ``extra`` is empty too.  Testing ``extra``
      alone let a variable at c = 0.5 onto a scale take ``_scale_column``,
      a column 2× the truth (#801, on ``main`` as well as with a body).

    Which of the reached paths *names* the column matters, and it is chosen
    rather than taken.  C's rows are in table order, so the lowest one is an
    accident of where a parameter sits in the model: a variable driving a
    Wyckoff DOF reaches ``[…atoms.1.x, …atoms.1.dof.0]`` and would be named by
    ``.x``, which matches no structural branch, sending a column that *is* a DOF
    to the peak chain — exact, but the slow way round, and it would make the
    paragraph above false.  So the name is taken from the paths whose **own**
    tie lists this column directly, which is the difference between what the
    variable drives (``dof.0``) and what that in turn drives (``.x``, by site
    symmetry).  Where every reached path is direct — the equal-Biso case, four
    rows all following the variable — the rule changes nothing.

    Read off the **declared** reach (``reach_block``), as ``_column_extras``
    is (WP-1805, the #773 follow-up): a variable driving a body's origin also
    moves every body atom row, which no C row says, and the extras returned
    here replace ``_column_extras``' for that column.  The *pattern* comes
    from there and the *coefficient* from C itself: a table with a block
    stores 1.0 at every entry of its reach, so read there every variable
    reaching one row looked like a unit tie (#801).  A derived row has no C
    entry and never stands alone — it arrives with the input it follows.
    """
    csc = table.reach_block().tocsc()
    coef = table.constraint_block()[0].tocsc()
    paths = [e.path for e in table.entries]
    out: list[tuple[str, list[str], bool]] = []
    for c, path in enumerate(table.free_paths):
        if not is_variable_path(path):
            out.append((path, extras[c], not extras[c]))
            continue
        sl = slice(csc.indptr[c], csc.indptr[c + 1])
        reach = [(paths[r], v) for r, v in zip(csc.indices[sl], csc.data[sl],
                                               strict=True) if paths[r] != path]
        # the paths this column drives *directly*, which is what may name it
        direct = [q for q, _ in reach
                  if (tie := table.entries[table._paths[q]].tie) is not None
                  and any(src == path for src, _ in tie.terms)]
        if direct:
            reach = ([pair for pair in reach if pair[0] == direct[0]]
                     + [pair for pair in reach if pair[0] != direct[0]])
        if not reach:
            # a declared variable nothing follows: it moves no row at all, so
            # its column is zero however it is built, and the FD path says that
            # in one residual evaluation without claiming a branch
            out.append((path, extras[c], False))
        else:
            unit = (len(reach) == 1
                    and coef[table._paths[reach[0][0]], c] == 1.0)
            out.append((reach[0][0], [q for q, _ in reach[1:]], unit))
    return out


def _within_atom(extra: list[str], ip: str, j: str) -> bool:
    """Whether every path this column also moves belongs to atom ``j`` of ``ip``.

    The reach ``_structural_column`` accounts for: it reads the coefficients of
    one atom's x/y/z (or six U) rows.  The site-symmetry ties always satisfy
    this — that is the case it was written for — while a user tie between two
    atoms' DOFs does not, and would otherwise contribute only the near atom.
    """
    prefix = f"phases.{ip}.atoms.{j}."
    return all(p.startswith(prefix) for p in extra)


def _affected_phases(model: CompiledModel, path: str, extra: list[str]):
    """The phases whose peak scalars a column moves — its own and its tie's."""
    touched = [path, *extra]
    if any(not p.startswith("phases.") for p in touched):
        return range(len(model.phases))
    return sorted({int(p.split(".")[1]) for p in touched})


def _make_jacobian(model: CompiledModel, table: ParameterTable):
    """Mixed analytic/FD Jacobian of the residual w.r.t. the internal vector.

    In Pawley mode the vector is [table θ | intensities]; the table columns are
    built exactly as for Rietveld/Le Bail, then the intensity block gets its own
    exact linear columns (:func:`_pawley_intensity_columns`).
    """
    sqrt_w = 1.0 / model.sigma
    free = table.free_paths
    n_table = len(free)
    # row extents from the one layout authority — the Jacobian writes into the
    # same blocks the residual stacks, so it must not re-derive them
    data_blk, pen_blk, pawley_blk, restr_blk, origin_blk = row_layout.layout(model)
    n_data, n_bkg_pen, n_restraint = data_blk.n, pen_blk.n, restr_blk.n
    n_rows = row_layout.n_rows(model)

    bkg_cols = {path: n for n, path in enumerate(model.bkg_paths)}
    axial_paths = {"instrument.geometry.axial_sl": 8, "instrument.geometry.axial_hl": 9}

    # Which *other* physical parameters each free column moves, read off the
    # affine block once (C is frozen for the run).  Every analytic branch below
    # is written for one named path and computes the rows *it* knows about, so a
    # column that reaches further than its own branch covers must not take that
    # branch: the missing dependence would silently leave the column short
    # rather than fail (WP-1070).  Empty for every untied column, which is why
    # an unconstrained model dispatches exactly as it did before.
    extras = _column_extras(table)
    # What each column *is*, for dispatch.  Identity except for a named
    # variable, which has no branch of its own and is read as what it reaches.
    identities = _column_identities(table, extras)
    # every physical path some column of this Jacobian can move — the free
    # names plus everything their ties reach.  Any question of the form "can
    # this stage move X?" must be asked here rather than of ``free``, which is
    # the same distinction ``ParameterTable.moving_paths`` draws one rank down.
    # Read off ``identities``, so a variable contributes the physical paths it
    # drives rather than a ``vars.*`` name that answers every predicate "no".
    reach = {q for name, extra, _ in identities for q in (name, *extra)}
    # A column reaching background coefficients only is linear in θ whatever
    # its coefficients, so its closed form is Σₖ C[k, c]·(basis row k), read
    # off C — the one closed form that needs no ``own``.  Without it a
    # variable at c ≠ 1 fell to the FD fallback, which writes no penalty row
    # (#801).  ``None`` for every other column.
    coef_c = table.constraint_block()[0].tocsc()
    bkg_mix = [np.array([[bkg_cols[q], coef_c[table._paths[q], c]]
                         for q in (path, *extra)])
               if all(q in bkg_cols for q in (path, *extra)) else None
               for c, (path, extra, _) in enumerate(identities)]

    typicals = _fd_typicals(table, identities)

    fixed_intens = _lebail_snapshot(model)
    # the origin rows are linear in the coordinates, so their physical
    # partials are a constant of the solve: scattered once, never per call
    o_phys = (None if model.origin is None or not n_table
              else origin_partials(model.origin, table))

    def jacobian(theta: np.ndarray) -> np.ndarray:
        if model.pawley is not None:
            intens = model.split_pawley_intensities(theta[n_table:])
            theta_t = theta[:n_table]
        else:
            intens = fixed_intens
            theta_t = theta
        values = table.decode(theta_t)
        J = np.zeros((n_rows, len(theta)), dtype=np.float64)
        fd_cols = []
        bases: DerivativeBases | None = None
        # the aperture node-FD bases feed only the axial columns, so ask for
        # them only in a stage that will build those columns — two FCJ node
        # generations per (line, reflection) per iteration otherwise wasted
        # (WP-0605 task 0; the FitReport callers keep the full default)
        need_axial = any(p in axial_paths for p in reach)
        # ∂Ω/∂pos, ∂Ω/∂Γ and ∂Ω/∂η are read only through ∂pos/∂p, ∂Γ/∂p and
        # ∂η/∂p, so a stage refining nothing but intensities multiplies all
        # three by zero.  Asked over ``reach``, not ``free``: a tie carries a
        # column onto paths whose names never appear in the free list.
        need_profile = not all(_intensity_only(p, bkg_cols) for p in reach)

        def get_bases() -> DerivativeBases:
            nonlocal bases
            if bases is None:
                bases = model.derivative_bases(values, intens,
                                               axial_derivs=need_axial,
                                               profile_derivs=need_profile)
            return bases

        for c, (path, extra, own) in enumerate(identities):
            if bkg_mix[c] is not None:
                # y is linear in the coefficient: ∂y/∂c_n = basis row; the
                # penalty rows are linear too (√λ·D₂)
                n, w = bkg_mix[c][:, 0].astype(np.intp), bkg_mix[c][:, 1]
                J[:n_data, c] = -sqrt_w * (w @ model.bkg_design[n])
                if n_bkg_pen:
                    J[n_data:n_data + n_bkg_pen, c] = model.bkg_penalty[:, n] @ w
            elif path in axial_paths and own:
                b = get_bases()
                if b.axial_ok:
                    J[:n_data, c] = -sqrt_w * _axial_column(
                        model, b, axial_paths[path])
                else:
                    fd_cols.append(c)
            elif ((dof := _STRUCTURAL_PATH.match(path)) and model.mode == "rietveld"
                    and model.structural_grad_supported(int(dof.group(1)))
                    and _within_atom(extra, dof.group(1), dof.group(2))):
                rows, grad = (("x", "y", "z"), model.coordinate_intensity_grad) \
                    if dof.group(3) == "dof" else (U_NAMES, model.adp_intensity_grad)
                J[:n_data, c] = -sqrt_w * _structural_column(
                    model, table, get_bases(), values, c,
                    int(dof.group(1)), int(dof.group(2)), rows, grad)
            elif ((po := _PO_PATH.match(path)) and model.mode == "rietveld"
                    and own
                    and not model.mag_split(int(po.group(1)))):
                J[:n_data, c] = -sqrt_w * _po_column(
                    model, get_bases(), values, int(po.group(1)))
            elif ((tex := _TEXTURE_PATH.match(path)) and model.mode == "rietveld"
                    and own
                    and not model.mag_split(int(tex.group(1)))):
                J[:n_data, c] = -sqrt_w * _texture_column(
                    model, get_bases(), values, int(tex.group(1)), path)
            elif ((sc := _SCALE_PATH.match(path)) and model.mode == "rietveld"
                    and own and values[path] > 0.0):
                # exactly linear, so no perturbed ``phase_peaks``; the scale
                # test is the 0/0 fence _scale_column's docstring names, and
                # a phase sitting at zero falls through to the FD path below
                J[:n_data, c] = -sqrt_w * _scale_column(
                    model, get_bases(), values, int(sc.group(1)))
            elif model.scalar_chain_supported(path) and all(
                    model.scalar_chain_supported(p) and p not in bkg_cols
                    and p not in axial_paths for p in extra):
                J[:n_data, c] = -sqrt_w * _peak_chain_column(
                    model, table, get_bases(), theta_t, values, c, path, intens,
                    affected=_affected_phases(model, path, extra),
                    typical=typicals[c])
            else:
                fd_cols.append(c)

        if fd_cols:
            # The declared fallback.  A background-peak parameter lands here by
            # design, not by omission: ``scalar_chain_supported`` names the
            # prefix and returns False, so the reach gate knows the path is
            # outside every analytic branch instead of discovering it (the
            # column-comes-back-**short** failure mode of WP-1070).  Writing
            # only ``[:n_data]`` is exact for it — a peak parameter moves no
            # penalty, Pawley or restraint row at all, so the rows left at their
            # zero initialisation are the rows whose true value is zero.  Three
            # parameters per hump means three residual evaluations per Jacobian,
            # which is why analytic columns for them are not worth writing.
            r0 = sqrt_w * (model.y_obs - model.evaluate(values, intens))
            for c in fd_cols:
                h = fd_step(theta_t[c], typicals[c])
                tp = theta_t.copy()
                tp[c] += h
                rp = sqrt_w * (model.y_obs - model.evaluate(table.decode(tp), intens))
                J[:n_data, c] = (rp - r0) / h

        if model.pawley is not None:
            _pawley_intensity_columns(model, get_bases(), values, sqrt_w, J,
                                      n_table, pawley_blk.start)

        # ∂p/∂p_free at θ: C, with each derived row (a body atom's
        # coordinates) the block's local Jacobian chained through C
        # (WP-1804).  C small: dense is fine.  Built once for both blocks
        # below that chain through it
        cmat = (table.local_jacobian(
                    np.asarray(theta_t, dtype=np.float64)).toarray()
                if n_table and (model.restraints is not None
                                or o_phys is not None) else None)

        if model.restraints is not None and n_table:
            # One unconditional matrix block below the data/penalty/Pawley rows:
            # ∂row/∂θ_c = (R_phys @ C)[i,c], since decode gives
            # p = C·θ + d (and the derived rows after it).  Rietveld-only (the Pawley block is then
            # empty, so restr_blk starts right after the penalty rows), and the
            # rows touch table θ only — no Pawley-intensity columns.
            restr0 = restr_blk.start
            r_phys = restraint_partials(model.restraints, values, table)
            if model.restraint_weight_scale != 1.0:
                # eq (7)'s c_w, applied to the assembled block and never inside
                # restraint_partials — model.geometry calls that same function
                # at unit weight for the unweighted partials every reported
                # geometry esd is built from (WP-1074; CompiledModel's field
                # comment).  √ matches restraint_residual: c_w weights S_G, the
                # sum of these rows squared.
                r_phys = r_phys * math.sqrt(model.restraint_weight_scale)
            J[restr0:restr0 + n_restraint, :n_table] = r_phys @ cmat

        if o_phys is not None:
            # The origin restraint (WP-1912, Flack & Schwarzenbach 1988 eq 9):
            # linear in the coordinates, so its physical partials are the
            # frozen aₙ·Δ_p matrix, chained through C (and a body's derived
            # rows) as the soft-restraint block's are.  Never ×√c_w: the
            # origin is not a restraint the caller declared (CompiledModel's
            # field comment), so c_w = 0 must leave it in place.
            J[origin_blk.rows, :n_table] = o_phys @ cmat
        return J

    return jacobian


def _jacobian_for(model, table, backend: str):
    """The Jacobian callable for ``backend`` (lazy import keeps numpy pure).

    Every autodiff callable produces the same fp64 host array in the same
    row/column layout as :func:`_make_jacobian`; the residual used for
    cost/statistics and the TRF solve stay numpy whichever backend built the
    columns (WP-0402 for jax, WP-0408 for torch — ``"torch"`` is fp64 on CPU,
    ``"torch-mps"`` fp32 on the Apple GPU, since no Apple GPU has fp64).

    This is also the assembly's exit point, so it is where the WP-0403
    mixed-precision policy is applied: whichever backend built the columns,
    they cross ``linalg64``'s host boundary here — cast to fp64, then reduced
    per column if (and only if) a policy asked for it.  With the default fp64
    policy the wrapper is a plain ``np.asarray``, so the numpy path is
    unchanged.
    """
    if backend == "jax":
        from ..backend.jax_backend import make_jax_jacobian

        inner = make_jax_jacobian(model, table)
    elif backend in TORCH_DEVICES:
        from ..backend.torch_backend import make_torch_jacobian

        inner = make_torch_jacobian(model, table, device=TORCH_DEVICES[backend])
    elif backend == "numpy":
        inner = _make_jacobian(model, table)
    else:
        raise ValueError(f"unknown backend {backend!r}; "
                         f"available: numpy, jax, {', '.join(TORCH_DEVICES)}")

    def jacobian(theta: np.ndarray) -> np.ndarray:
        # policy read per call, not per closure build: a `with precision_policy`
        # block around a refine must take effect on an already-built solver
        return get_precision_policy().cast_columns(inner(theta))

    return jacobian


def strain_cone_inequalities(model: CompiledModel, table: ParameterTable,
                             x0: np.ndarray) -> list["lm_mod.LinearInequality"]:
    """Stephens positivity rows σ²(M) = T·θ + c ≥ 0, one block per phase.

    σ²(M) is ``strain_monomials @ S`` and S is an *affine* function of the free
    vector (``decode`` gives p = C·θ + d), so the whole thing is linear in
    θ.  That is what makes it expressible to the bounded-LM driver
    and inexpressible to TRF.

    Two cases are skipped rather than enforced, both deliberately:

    * **no strain DOF free in this stage** — T is then identically zero, so the
      rows are a constant that the solver could never satisfy if it were
      already negative, and would silently freeze the step;
    * **an infeasible starting point** — feasibility is *maintained*, not
      restored, by the step (``lm._solve_constrained_step``).  The staged plans start
      from the isotropic limit S = ε²·[M²], which is strictly inside the cone,
      so this is the pathological case and not the normal one; when it does
      happen the existing ``STEPHENS_STRAIN_NOT_POSITIVE`` guard still fires on
      the result, which is the honest outcome.
    """
    from . import lm as lm_mod

    free = table.free_paths
    if not free:
        return []
    C, d = table.constraint_block()
    C = C.toarray()
    out: list[lm_mod.LinearInequality] = []
    for ip, cp in enumerate(model.phases):
        if cp.strain_monomials is None:
            continue
        try:
            rows = [table._paths[f"phases.{ip}.microstrain.{n}"] for n in S_NAMES]
        except KeyError:                      # phase carries no microstrain block
            continue
        mono = np.asarray(cp.strain_monomials, dtype=np.float64)
        T = mono @ C[rows, :]
        c = mono @ d[rows]
        if not np.any(T):                     # nothing free in this direction
            continue
        block = lm_mod.LinearInequality(T=T, c=c, label=f"phases.{ip}.microstrain")
        if block.violated(x0).any():
            continue
        out.append(block)
    return out


def texture_positivity_inequalities(model: CompiledModel, table: ParameterTable,
                                    x0: np.ndarray) -> list["lm_mod.LinearInequality"]:
    """P ≥ 0 at every reflection of the stage, one block per textured phase.

    P = 1 + (K·diag w)·c with c an affine function of θ, so the rows are linear
    in θ (WP-1960 D4).  K is taken at the stage's **starting** cell, because K
    follows the cell and a row must be a constant of the stage: a stage that
    frees the cell beside the coefficients holds P ≥ 0 to first order only,
    and ``TEXTURE_NOT_POSITIVE`` samples the answer.  Skipped as
    :func:`strain_cone_inequalities` skips: nothing free in the direction, or
    a start already outside.  C = 0 starts strictly inside, at P = 1.
    """
    from . import lm as lm_mod

    if not table.free_paths or all(cp.tex_basis is None for cp in model.phases):
        return []
    C, d = table.constraint_block()
    C = C.toarray()
    values = table.decode(x0)
    out: list[lm_mod.LinearInequality] = []
    for ip, cp in enumerate(model.phases):
        if cp.tex_basis is None:
            continue
        rows = [table._paths[p] for p in cp.tex_paths]
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        kw = np.asarray(cp.tex_basis.evaluate(reflection_directions(
            cp.reflections.hkl, cp.tex_basis.rule, cell))) * cp.tex_weights
        T = kw @ C[rows, :]
        if not np.any(T):
            continue
        block = lm_mod.LinearInequality(T=T, c=1.0 + kw @ d[rows],
                                        label=f"phases.{ip}.texture")
        if block.violated(x0).any():
            continue
        out.append(block)
    return out


def gaussian_width_inequalities(model: CompiledModel, table: ParameterTable,
                                x0: np.ndarray) -> list["lm_mod.LinearInequality"]:
    """Γ_G² ≥ ``caglioti._MIN_GAMMA_G2`` at every reflection, one block per phase.

    ``gaussian_fwhm`` takes Γ_G = √max(Γ_G², ε) with ε = 1e-8 deg².  Under it
    every Gaussian width column is exactly zero, so a stage that steps there
    stops in place.  LM's bounded step reaches it (WP-1938 D7).  With W's
    floor at 0 it landed W exactly there, and with U and V near 0 that put
    Γ_G² under ε at every point: on the manual's minimal NAC call (macOS
    arm64, ``[dev]``) the fit ended at Rwp 0.18028 against TRF's 0.13375.  W's
    floor is ε since, which settles that case on its own.  A negative U or V
    still reaches the clamp: the 150 K Cr₂WO₆ fixture ended at Rwp 0.25458
    against TRF's 0.09924, with U −0.0767 and V −0.179 putting Γ_G² under ε
    at 31 of 31 reflections.  These rows hold that.  GSAS-II clamps the same
    way (``GSASIIstrMath.GetReflSigGamCW``, σ ≥ 0.001 centideg²), but its
    Marquardt takes no bounds, so no step lands on a floor there.

    The rows are held inside the step (WP-1938 D8).  Truncating a box-only
    step against them stalled wherever the optimum wanted Γ_G² under ε at
    most reflections: three of WP-1937's fourteen grid fits stopped short
    (``lm.LinearInequality``).

    A row per (emission line, reflection) whose evaluation window holds data,
    the nuclear one or a magnetic component's wider one, at the frozen hkl
    list's Bragg angles for the starting cell and λ:

        Γ_G² = (u + gauss_strain)·tan²θ + v·tanθ + w + gauss_size/cos²θ

    The five values are table rows, every row is refined in its own units, and
    p = C·θ + d, so each row is exactly affine in θ.  A cell or λ the stage
    frees moves the angles a little, and the rows stay where the stage
    started, as the Stephens cone's d-spacings do.  Exact duplicate rows go,
    and so do rows no free column reaches.

    A row the start already violates is dropped, for
    :func:`strain_cone_inequalities`' reason: the step keeps feasibility and
    cannot restore it.  So a stage starting with Γ_G² under ε at a reflection
    is not held there.  U = V = 0 with W on its floor sits exactly on every
    row, and is held.

    A phase whose width rows are derived (``ParameterTable.derived_paths``) is
    skipped, since a derived row is written after C and is not affine in θ.

    Single-histogram only, like the cone: :func:`run_multi_least_squares`
    builds no inequality.  TRF never sees these rows, and
    ``RESOLUTION_NOT_POSITIVE`` stays its guard
    (:func:`~rietx.strategy.staged.check_resolution_positive`).
    """
    from ..model.profiles.caglioti import _MIN_GAMMA_G2
    from . import lm as lm_mod

    if not table.free_paths:
        return []
    C, d = table.constraint_block()
    C = C.toarray()
    derived = table.derived_paths()
    values = table.decode(x0)
    lams = model.line_lambdas(values)
    out: list[lm_mod.LinearInequality] = []
    for ip, cp in enumerate(model.phases):
        names = ("instrument.profile.u", "instrument.profile.v",
                 "instrument.profile.w", f"phases.{ip}.gauss_strain",
                 f"phases.{ip}.gauss_size")
        if any(n in derived for n in names):
            continue
        try:
            rows = [table._paths[n] for n in names]
        except KeyError:                        # defensive: every phase has both
            continue
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        _d, tt_lines = model._cell_block(cp, cell, lams)
        theta = []
        for il, tt in enumerate(tt_lines):
            tt = np.asarray(tt, dtype=np.float64)
            win = cp.win[il]
            used = win[:, 1] > win[:, 0]
            if cp.win_mag is not None:          # a magnetic peak's, drawn wider
                used |= cp.win_mag[il][:, 1] > cp.win_mag[il][:, 0]
            used &= np.isfinite(tt)
            theta.append(np.radians(0.5 * tt[used]))
        th = np.concatenate(theta) if theta else np.empty(0)
        if not th.size:
            continue
        t = np.tan(th)
        # coefficients of u, v, w, gauss_strain, gauss_size in Γ_G²
        basis = np.column_stack([t * t, t, np.ones_like(t), t * t,
                                 1.0 / (np.cos(th) ** 2)])
        T = basis @ C[rows, :]
        c = basis @ d[rows] - _MIN_GAMMA_G2
        Tc = np.unique(np.column_stack([T, c]), axis=0)
        T, c = Tc[:, :-1], Tc[:, -1]
        # violated beyond rounding, so a row a previous stage left on its
        # face is kept (``lm.LinearInequality.violated``)
        keep = (np.any(T != 0.0, axis=1)
                & ~lm_mod.LinearInequality(T=T, c=c).violated(x0))
        if not keep.any():
            continue
        out.append(lm_mod.LinearInequality(
            T=np.ascontiguousarray(T[keep]), c=c[keep],
            label=f"instrument.profile (phases.{ip})"))
    return out


def lorentzian_width_inequalities(model: CompiledModel, table: ParameterTable,
                                  x0: np.ndarray) -> list["lm_mod.LinearInequality"]:
    """Γ_L ≥ 0 at every reflection, one block per phase.

    The Lorentzian twin of :func:`gaussian_width_inequalities`, built the
    same way and for the maintainer's ruling of 2026-10-23 (WP-2002): Y has
    no floor of its own, and the width is what must stay non-negative.  A
    negative Γ_L is not a shape.  The TCH mixing then gives a negative η, and
    nothing in the forward model refuses it.

    The rows are the sum the forward model draws
    (``CompiledModel._width_block``):

        Γ_L = (x + lor_size)/cosθ + (y + lor_strain)·tanθ

    at the nuclear windows, and with ``magnetic_lor_size`` and
    ``magnetic_lor_strain`` added at a magnetic component's windows.  A
    Stephens block adds Λ(hkl)·tanθ, which its own cone holds at or above
    zero (:func:`strain_cone_inequalities`), so it is left out of the row.
    The row is then a sufficient condition, never a necessary one.  The
    phase terms have floors of 0, so a row can bind only through X and Y.

    **A row at every reflection of the frozen list**, where the Gaussian rows
    take only those whose window holds data.  Γ_G² has a clamp under it
    (``gaussian_fwhm``'s ε), so a reflection off the data can sit under it
    harmlessly; Γ_L has none, and a negative one is NaN at the next compile
    that windows that reflection onto data (``tch_gamma_eta``'s fifth root),
    which stops the stage before it starts.  The list carries
    ``REFLECTION_MARGIN_DEG`` beyond the range, and Γ_L changes sign at most
    once in θ, so holding it there keeps it non-negative over the range.

    Everything else is :func:`gaussian_width_inequalities`' rule: at the
    frozen Bragg angles for the starting cell and λ; affine in θ through C and
    d; exact duplicates and rows no free column reaches dropped; a row the
    start violates dropped; a phase with a derived width row skipped.  The
    joint runner asks it of each histogram (:func:`_joint_width_inequalities`).
    ``RESOLUTION_NOT_POSITIVE`` is TRF's guard.
    """
    from . import lm as lm_mod

    if not table.free_paths:
        return []
    C, d = table.constraint_block()
    C = C.toarray()
    derived = table.derived_paths()
    values = table.decode(x0)
    lams = model.line_lambdas(values)
    out: list[lm_mod.LinearInequality] = []
    for ip, cp in enumerate(model.phases):
        # size then strain, pairwise: the basis below relies on the order
        nuclear = ("instrument.profile.x", "instrument.profile.y",
                   f"phases.{ip}.lor_size", f"phases.{ip}.lor_strain")
        magnetic = (f"phases.{ip}.magnetic_lor_size",
                    f"phases.{ip}.magnetic_lor_strain")
        if any(n in derived for n in nuclear + magnetic):
            continue
        try:
            rows = [table._paths[n] for n in nuclear]
        except KeyError:                        # defensive: every phase has both
            continue
        families = [(cp.win, rows)]
        # the magnetic pair is a table row only where a moment block is declared
        if cp.win_mag is not None and all(n in table._paths for n in magnetic):
            families.append((cp.win_mag, rows + [table._paths[n] for n in magnetic]))
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        _d, tt_lines = model._cell_block(cp, cell, lams)
        blocks_T, blocks_c = [], []
        for _windows, idx in families:
            theta = []
            for tt in tt_lines:
                tt = np.asarray(tt, dtype=np.float64)
                theta.append(np.radians(0.5 * tt[np.isfinite(tt)]))
            th = np.concatenate(theta) if theta else np.empty(0)
            if not th.size:
                continue
            # each row's coefficient in Γ_L: the size terms (x, lor_size, and
            # magnetic_lor_size) go as 1/cosθ, the strain terms as tanθ
            inv_cos, t = 1.0 / np.cos(th), np.tan(th)
            basis = np.column_stack([inv_cos, t] * (len(idx) // 2))
            blocks_T.append(basis @ C[idx, :])
            blocks_c.append(basis @ d[idx])
        if not blocks_T:
            continue
        Tc = np.unique(np.column_stack([np.vstack(blocks_T),
                                        np.concatenate(blocks_c)]), axis=0)
        T, c = Tc[:, :-1], Tc[:, -1]
        keep = (np.any(T != 0.0, axis=1)
                & ~lm_mod.LinearInequality(T=T, c=c).violated(x0))
        if not keep.any():
            continue
        out.append(lm_mod.LinearInequality(
            T=np.ascontiguousarray(T[keep]), c=c[keep],
            label=f"instrument.profile Lorentzian (phases.{ip})"))
    return out


def _joint_width_inequalities(models: list[CompiledModel], mtable, x0: np.ndarray
                              ) -> list["lm_mod.LinearInequality"]:
    """The single fit's Γ_G² and Γ_L rows, asked of each histogram and laid on
    the joint columns (``mtable.col_map``).

    Without them a joint fit kept a width non-negative only through the
    per-coefficient floors, and WP-2002 removed the U, V and Y floors: a free
    Y could step to a negative Γ_L and every residual to NaN.  Each builder
    reads its own histogram's table, whose C already carries the λ factor a
    shared size column takes (WP-1131), so a row needs only its columns moved.
    """
    from . import lm as lm_mod

    out: list[lm_mod.LinearInequality] = []
    n = len(x0)
    for h, (model, table, local) in enumerate(
            zip(models, mtable.tables, mtable.split(x0), strict=True)):
        cols = np.asarray(mtable.col_map(h), dtype=np.intp)
        for block in (gaussian_width_inequalities(model, table, local)
                      + lorentzian_width_inequalities(model, table, local)):
            T = np.zeros((block.T.shape[0], n), dtype=np.float64)
            T[:, cols] = block.T
            out.append(lm_mod.LinearInequality(T=T, c=block.c,
                                               label=f"hist.{h} {block.label}"))
    return out


def _pad_inequalities(blocks: list["lm_mod.LinearInequality"], n_aux: int
                      ) -> list["lm_mod.LinearInequality"]:
    """Each block's T widened by ``n_aux`` zero columns for the Pawley tail.

    The builders read the table, whose columns are the leading part of the
    solver's vector.  A Pawley intensity enters none of Γ_G², Γ_L and σ²(M),
    so its columns are zero.  Unpadded, ``T·θ`` raised a shape ``ValueError`` on
    every Pawley stage freeing a Stephens block under LM.
    """
    if not n_aux:
        return blocks
    return [replace(
        b, T=np.hstack([b.T, np.zeros((b.T.shape[0], n_aux))])) for b in blocks]


def _free_values(table, theta: np.ndarray) -> list[float]:
    """Physical values of the table's free paths at ``theta`` — the ``values``
    field of an ``eval`` event, in ``free_paths`` order (which ``stage_start``
    carries as ``free_paths``, so a stream consumer can align them).

    The table answers, because it knows its own layout:
    :meth:`ParameterTable.free_values` drops an appended Pawley tail, and a
    joint fit's :meth:`~rietx.params.multi.MultiParameterTable.free_values`
    reads each combined path from the histogram that owns it (WP-1341).
    """
    return table.free_values(theta)


def _cancellable(residual, cancel, stage: str):
    """``residual`` behind a read of ``cancel`` at each evaluation boundary.

    One wrapper for :func:`run_least_squares` and
    :func:`run_multi_least_squares`.  ``__wrapped__`` lets ``inspect.unwrap``
    reach the closure underneath.
    """
    def checked(theta: np.ndarray):
        if cancel.is_set():
            raise RefinementCancelled(
                f"cancelled during stage {stage!r}" if stage else "cancelled",
                stage=stage)
        return residual(theta)

    checked.__wrapped__ = residual
    return checked


def _tracked(residual, tracker: _StepTracker, events, stage: str, table):
    """``residual`` as the TRF path's accepted-point hook.

    Two jobs in a fixed order per call: emit the ``eval`` event measured
    against the incumbent, then let ``tracker`` accept.  ``table`` is what
    :func:`_free_values` reads the event's ``values`` off.  One wrapper for
    :func:`run_least_squares` and :func:`run_multi_least_squares`, and
    ``__wrapped__`` lets ``inspect.unwrap`` reach the guard underneath.
    """
    counter = {"n": 0}

    def tracked(theta: np.ndarray):
        r = residual(theta)
        cost = 0.5 * float(r @ r)
        if events is not None:
            counter["n"] += 1
            data = {"stage": stage, "n_eval": counter["n"], "cost": cost,
                    "accepted": bool(cost < tracker.best_cost)}
            if tracker.best is not None:
                data["step_norm"] = float(np.linalg.norm(
                    np.asarray(theta, dtype=np.float64) - tracker.best))
            data["values"] = _free_values(table, theta)
            events.emit("eval", **data)
        tracker.accept(theta, cost)
        return r

    tracked.__wrapped__ = residual
    return tracked


def _lm_outcome(residual, jacobian, x0, lo, hi, *, max_nfev, ftol,
                inequalities, events, stage: str, track=None, table=None,
                normal_equations=None):
    """Run the bounded-LM driver, adapted to the scipy result shape.

    The two drivers are kept interchangeable at exactly this point: everything
    downstream (covariance, guards, history) reads ``x``/``fun``/``jac``/
    ``cost``/``nfev``/``status``, and :class:`~.lm.LMOutcome` carries those with
    scipy's meanings.  ``track`` is a :class:`_StepTracker` fed from the
    driver's accepted-point callback — the LM half of the final-step record
    the TRF path reconstructs from its residual closure.  ``events`` gets one
    ``eval`` per *measured trial* via the driver's ``on_trial`` hook
    (WP-1113): a rejected step arrives with ``accepted: false`` and the λ that
    produced it, which is exactly the trajectory the evaluation-count
    mechanism analysis reads.  Trials the driver's linear model discards
    without evaluating the residual emit nothing — ``eval`` means one trial
    evaluation on both drivers.  LM's curvature measurements
    (:func:`.lm._measured_curvature`) evaluate the residual too, but as
    derivative information, like scipy's finite-difference Jacobian calls, so
    they emit nothing and ``nfev`` leaves them out (WP-1953).
    ``normal_equations`` is the driver's own (:func:`.lm.minimize`).
    """
    from . import lm as lm_mod

    counter = {"n": 0}

    def accept_cb(theta: np.ndarray, cost: float) -> None:
        track.accept(theta, cost)

    def trial_cb(theta: np.ndarray, cost: float, accepted: bool,
                 lam: float, step_norm: float) -> None:
        counter["n"] += 1
        data = {"stage": stage, "n_eval": counter["n"], "cost": cost,
                "accepted": accepted, "step_norm": step_norm, "lam": lam}
        if table is not None:
            data["values"] = _free_values(table, theta)
        events.emit("eval", **data)

    return lm_mod.minimize(residual, jacobian, x0, lo=lo, hi=hi,
                           max_nfev=max_nfev, ftol=ftol,
                           inequalities=inequalities,
                           callback=accept_cb if track is not None else None,
                           on_trial=trial_cb if events is not None else None,
                           normal_equations=normal_equations)


class _StepTracker:
    """The last two accepted iterates of one solve, full θ vector each.

    scipy TRF exposes no accepted-point hook, so the TRF path reconstructs
    acceptance from the solver-facing residual closure: TRF accepts a trial
    exactly when its cost is strictly below the incumbent's, so the strictly
    cost-decreasing evaluations *are* the accepted iterates.  The jacobian
    closure never routes through that residual, which is what keeps FD probe
    points out of the record.  The LM driver reports accepted points through
    its callback and feeds :meth:`accept` directly.
    """

    def __init__(self) -> None:
        self.prev: np.ndarray | None = None
        self.best: np.ndarray | None = None
        self.best_cost = np.inf

    def accept(self, x: np.ndarray, cost: float) -> None:
        if cost < self.best_cost:
            self.prev, self.best = self.best, np.asarray(x, dtype=np.float64).copy()
            self.best_cost = cost

    def step(self) -> tuple[np.ndarray, np.ndarray] | None:
        """(previous, final) accepted iterate, or ``None`` before any step."""
        return None if self.prev is None else (self.prev, self.best)


def _final_shift_over_esd(table: ParameterTable,
                          step: tuple[np.ndarray, np.ndarray] | None,
                          stderr_full: np.ndarray | None,
                          correlation: np.ndarray | None,
                          n_table: int) -> float | None:
    """McCusker et al. (1999) §7's convergence quantity, external units.

    max |Δp_i| / esd(p_i) over the solve's final accepted step, with *both*
    sides in external parameter units: Δp decoded through C, and the esd
    that every reported parameter carries.  The appended Pawley
    intensity block refines outside the table in its own units, so its rows
    join directly.  ``None`` when the quantity cannot be measured — no
    accepted step, or no esds — never zero (WP-1076's honest empty state).
    """
    if step is None or stderr_full is None:
        return None
    x_prev, x_final = step
    vals_prev = table.decode(x_prev[:n_table])
    vals_final = table.decode(x_final[:n_table])
    esd = table.stderr_physical(x_final[:n_table], stderr_full[:n_table],
                                correlation)
    ratios = [abs(vals_final[p] - vals_prev[p]) / esd[p]
              for p in table.free_paths
              if np.isfinite(esd.get(p, np.nan)) and esd[p] > 0.0]
    ratios += [abs(float(x_final[i]) - float(x_prev[i])) / float(stderr_full[i])
               for i in range(n_table, len(x_final))
               if np.isfinite(stderr_full[i]) and stderr_full[i] > 0.0]
    return max(ratios) if ratios else None


def _final_shift_over_esd_multi(mtable: "MultiParameterTable",
                                step: tuple[np.ndarray, np.ndarray] | None,
                                stderr: np.ndarray | None,
                                correlation: np.ndarray | None) -> float | None:
    """:func:`_final_shift_over_esd` for the joint solve (WP-1341).

    The definition carries over unchanged.  Every free column of the joint θ
    has one shift, the joint solve's final accepted step, and one esd, read
    off the covariance of the weighted stacked residual.  That esd is the one
    the joint result reports, because each histogram's slice is decoded here
    exactly as ``MultiHistogramRefinement._build_result`` decodes it.  The
    histogram weights enter both the step and the covariance, so they change
    the number and leave its meaning alone.

    A shared column sits in every histogram's table.  Its ratio is the same in
    each, because each table decodes it affinely, and the WP-1131 λ factor
    scales the shift and the esd alike.  So the maximum over histograms is
    the maximum over columns.
    """
    if step is None or stderr is None:
        return None
    x_prev, x_final = step
    ratios = []
    for h, table in enumerate(mtable.tables):
        cm = mtable.col_map(h)
        corr_h = correlation[np.ix_(cm, cm)] if correlation is not None else None
        r = _final_shift_over_esd(table, (x_prev[cm], x_final[cm]), stderr[cm],
                                  corr_h, len(cm))
        if r is not None:
            ratios.append(r)
    return max(ratios) if ratios else None


def _freeze_cell_windows(model: CompiledModel, table: ParameterTable,
                         sigma: float | None = PHASE_SUPPORT_SIGMA) -> None:
    """Declare which phases' cells take the default window for this stage.

    Only the phases the data cannot see (WP-1110).  A window is not free — TRF
    derives its per-coordinate trust-region scale from the distance to the
    bounds, so bounding a cell changes the step taken in it even where the bound
    is never reached — so it is spent only where the alternative is a flat
    direction the fit will wander down.  ``phase_support`` decides it: the
    screen ``refine._answer_significance`` starts from, which bounds the
    scale's significance from above (WP-1523).  So a windowed phase is one the
    ``PHASE_UNCONSTRAINED`` diagnostic would also call unseen.

    Read at the values the stage *starts* from, which is the whole point of
    doing it here: the same place every other per-stage freeze happens.

    ``sigma`` is the plan's ``phase_support_sigma``, the threshold of the hold
    this window backs (WP-2002, B1).  ``None`` judges no phase unseen, so the
    claim made is that no cell needs a window, and nothing is measured.
    """
    if sigma is None:
        table.freeze_cell_windows(set())
        return
    values = table.decode(table.x0())
    support = model.phase_support(values)
    table.freeze_cell_windows({ip for ip, s in enumerate(support) if s < sigma})


def _freeze_strain_cap(model: CompiledModel, table: ParameterTable) -> None:
    """Declare the sample-strain cap for this stage, off the fitted 2θ extent.

    ``model.tt_min``/``tt_max`` are the *in-range* fit grid's ends — excluded
    regions already removed — which is the right authority, because the bound
    says a line cannot be wider than the interval it was measured over and an
    excluded interval was not measured
    (:func:`~rietx.params.vector.strain_cap`).

    Read where every other per-stage freeze happens, and armed inside
    ``bounds()`` only on terms that have *already* reached it, so a fit whose
    strain stays inside what the data can express gets no bound at all and is
    bit-identical to an uncapped build.  That restriction is the same one
    :func:`_freeze_cell_windows` makes and for the same measured reason: a
    bound is never free, since TRF takes its per-coordinate trust-region scale
    from the distance to it.
    """
    table.freeze_strain_cap(strain_cap(model.tt_min, model.tt_max))


def _freeze_strain_cap_multi(models: list[CompiledModel],
                             mtable: "MultiParameterTable") -> None:
    """The freeze above for a joint refinement, where a phase is *shared*.

    ``lor_strain`` is a phase parameter, so in a joint fit its column is
    written once per histogram and the last write wins — harmless only while
    the histograms agree (``MultiParameterTable.refresh_bounds``).  Here they
    disagree by construction, each having its own 2θ extent, so the **widest**
    cap governs: a line only has to be a line in *some* histogram, and a joint
    fit is entitled to whichever one can express it.  Taking the narrowest
    would let a short scan bound a width the long scan measures perfectly well.
    """
    caps = [strain_cap(m.tt_min, m.tt_max) for m in models]
    cap = max(caps) if caps else None
    for table in mtable.tables:
        table.freeze_strain_cap(cap)


def _longest_line_wavelength(model: CompiledModel) -> float | None:
    """The source's **longest** emission line (Å), or ``None`` if it has none.

    The one selector every reading of a size coefficient as a crystallite goes
    through: the ``SIZE_UNUSUALLY_SMALL`` flag in
    :func:`rietx.refine._size_flag_diagnostics`, the microstructure block and
    the joint fit's size sharing, which import it rather than repeating these
    two lines.  **Longest** because the Scherrer size is per wavelength and a
    longer λ implies a *larger* crystallite for the same coefficient: the most
    permissive attribution, and therefore the one that can never trip a
    genuine fit on account of a Kα2 offset.

    ``None`` is "this source states no wavelength", a fact about the model.
    What to do about it is each caller's: the flag has nothing to read a size
    with, so it returns no diagnostic.  The solver's size bound
    (:func:`~rietx.params.vector.size_cap`) needs no wavelength since the 2 nm
    floor went (WP-2002), so it does not call this.
    """
    lams = [lam for lam in getattr(model, "line_wavelengths", ()) or ()
            if lam > 0.0]
    return max(lams) if lams else None


def _freeze_size_cap(model: CompiledModel, table: ParameterTable) -> None:
    """Declare the sample-size cap for this stage — the strain-cap freeze's twin.

    Off the same fitted 2θ extent (:func:`~rietx.params.vector.size_cap`), read
    where every other per-stage freeze happens, and armed inside ``bounds()``
    only on a term that has already made a line wider than the fitted range.
    So a fit whose size stays where the data can express it gets no bound at
    all and is bit-identical to an uncapped build.
    """
    table.freeze_size_cap(size_cap(model.tt_min, model.tt_max))


def _freeze_size_cap_multi(models: list[CompiledModel],
                           mtable: "MultiParameterTable") -> None:
    """The freeze above for a joint refinement, where a phase is *shared*.

    ``lor_size`` is a phase parameter, so the **widest** cap is the one declared
    to every table, for the strain reason one function up: a line only has to
    fit inside *some* histogram's range, and a joint fit is entitled to
    whichever pattern can express it.

    Since WP-1131 the caps do not merely overwrite one another.
    ``MultiParameterTable`` **intersects** each histogram's bounds onto the
    shared column, and each table divides its physical cap by its own value
    scale, so the binding bound is the widest cap expressed in the reference
    histogram's units.  Only a histogram whose copy has reached its cap arms
    it, and the arming asymmetry decides where the intersection lands.
    """
    caps = [size_cap(m.tt_min, m.tt_max) for m in models]
    cap = max(caps) if caps else None
    for table in mtable.tables:
        table.freeze_size_cap(cap)


def _freeze_cell_windows_multi(models: list[CompiledModel],
                               mtable: "MultiParameterTable",
                               sigma: float | None = PHASE_SUPPORT_SIGMA) -> None:
    """The freeze above for a joint refinement, where a cell can be *shared*.

    A phase invisible in one histogram may be plain in another, and if its cell
    is shared then the data — jointly, which is what a joint refinement fits —
    can see it. So a phase is windowed only when it is below support in **every**
    histogram, and the same set is frozen on every sub-table: the combined bound
    vectors write shared columns once per histogram and keep the last, which is
    only harmless while they agree.  ``sigma`` is :func:`_freeze_cell_windows`'
    own, and ``None`` windows nothing.
    """
    if sigma is None:
        windowed: set[int] = set()
    else:
        per_model = [m.phase_support(t.decode(t.x0()))
                     for m, t in zip(models, mtable.tables, strict=True)]
        n_phases = min((len(s) for s in per_model), default=0)
        windowed = {ip for ip in range(n_phases)
                    if all(s[ip] < sigma for s in per_model)}
    for table in mtable.tables:
        table.freeze_cell_windows(windowed)
    mtable.refresh_bounds()


_MAGNETIC_WIDTH_PATH = re.compile(
    r"^phases\.(\d+)\.magnetic_lor_(size|strain)$")


def _check_magnetic_width_compiled(model: CompiledModel,
                                   table: ParameterTable) -> None:
    """Refuse a free magnetic width the compiled model cannot see (WP-1343).

    ``compile_model`` builds a phase's **second frozen family** — the magnetic
    component's own windows and FCJ node counts — only where that component's
    widths can differ from the nuclear ones this stage: either a value is
    already non-zero, or ``moving_paths`` says the stage can move one.  A
    caller who compiled with no claim at all (``moving_paths=None``: the
    public ``compile_model``, a plot, a replay) and then frees a magnetic
    width against that model would get a column that is **identically zero**,
    because the value is not read on the unsplit path — the silent
    short-column failure WP-1070 filed, one correction over.

    So it is refused here, by name, with the fix in the message.  Asked of
    ``moving_paths`` rather than ``free_paths``, for the reason
    ``compile_model`` sizes from it: a tie moves a parameter that is not a
    column of θ.  The alternative — building the family whenever no claim was
    made — would split the draw for every plot and replay of a magnetic phase
    and cost the last two digits of a converged fit, since (a + b)·Ω and
    a·Ω + b·Ω are not the same doubles.
    """
    for path in table.moving_paths:
        m = _MAGNETIC_WIDTH_PATH.match(path)
        if m is None:
            continue
        ip = int(m.group(1))
        if ip < len(model.phases) and not model.mag_split(ip):
            raise ValueError(
                f"{path} can move in this stage, but the model was compiled "
                f"without the magnetic component's own frozen windows, so the "
                f"parameter reaches no residual row and its Jacobian column "
                f"would be identically zero. Recompile with the stage's claim "
                f"— compile_model(..., moving_paths=set(table.moving_paths)) "
                f"— which is what fit() and every staged plan already pass, "
                f"or seed the term off zero before compiling")


def run_least_squares(model: CompiledModel, table: ParameterTable,
                      *, max_iter: int = 100, ftol: float = FTOL,
                      compute_uncertainties: bool = True,
                      events=None, stage: str = "",
                      backend: str = "numpy",
                      solver: str = DEFAULT_SOLVER,
                      cancel=None,
                      phase_support_sigma: float | None = PHASE_SUPPORT_SIGMA
                      ) -> LSQOutcome:
    """Solve one stage.  ``cancel`` — a :class:`~.cancel.CancelToken`, read
    between residual evaluations; a set token raises
    :class:`~.cancel.RefinementCancelled` out of this call, leaving the model
    and table exactly as the last accepted evaluation found them.
    ``phase_support_sigma`` is the plan's, which decides the default cell
    window (:func:`_freeze_cell_windows`); ``None`` windows no cell."""
    if solver not in SOLVERS:
        raise ValueError(f"unknown solver {solver!r}; available: {', '.join(SOLVERS)}")
    lapack_start = lapack.retries()
    # A free λ beside a free cell is an exactly flat direction.  Asked here
    # rather than at table build because a cumulative plan can free the two in
    # different stages, and rather than in ``_rebuild`` because a diagnostic
    # probe frees parameters without intending to fit them.
    table.check_wavelength_against_cell()
    _check_magnetic_width_compiled(model, table)
    _freeze_cell_windows(model, table, phase_support_sigma)
    _freeze_strain_cap(model, table)
    _freeze_size_cap(model, table)
    residual = _make_residual(model, table)
    cell_guard = _DegenerateCellGuard(residual)
    residual = cell_guard
    jacobian = _jacobian_for(model, table, backend)
    jacobian = _DegenerateCellJacobianGuard(jacobian, cell_guard)

    if cancel is not None:
        # Both drivers, and *before* the event wrapper, so the check costs one
        # branch on the path that would otherwise evaluate: the flag is read at
        # an eval boundary, where the compiled state is quiescent — nothing
        # reaches into the frozen discreteness.  This is deliberately not the LM
        # driver's callback, which fires only on *accepted* points: an inner
        # loop that never accepts a step would never see the token.
        residual = _cancellable(residual, cancel, stage)

    # the closure the stationary-angle test probes after the solve: below the
    # TRF event wrapper, so a probe neither emits an ``eval`` nor moves the
    # step tracker ``max_shift_over_esd`` is read from, and above the cancel
    # check, so a stop requested during the test is honoured like any other
    probe = residual
    tracker = _StepTracker()
    if solver == "trf":
        # One wrapper, two jobs in a fixed order per call: emit the eval event
        # *measured against the incumbent*, then let the tracker accept.  scipy
        # TRF exposes no per-iteration callback, so the residual closure is the
        # hook (the emitted dict is plain floats — no pydantic here), and
        # acceptance/step fields are reconstructed exactly as _StepTracker's
        # docstring describes.  TRF's trust radius is scipy-internal: the trial
        # ``step_norm`` sequence is its observable shadow — a trial step never
        # exceeds the radius, and rejections shrink it (WP-1113).  The LM
        # driver reports its trials through a real callback instead
        # (``_lm_outcome``), so it does not wrap the residual.
        residual = _tracked(residual, tracker, events, stage, table)
    n_table = len(table.free_paths)
    x0 = table.x0()
    lo, hi = table.bounds()
    if model.pawley is not None:
        # append the per-hkl intensity block (bounded ≥ 0)
        plo, phi = model.pawley_bounds()
        x0 = np.concatenate([x0, model.pawley_x0()])
        lo = np.concatenate([lo, plo])
        hi = np.concatenate([hi, phi])
    n_aux = len(x0) - n_table
    x0 = _feasible_start(x0, lo, hi, solver)

    r0 = residual(x0)
    # invariant 2: whatever built the columns, the residual is fp64 on host —
    # checked once per solve, not per iteration
    require_fp64(r0, "least-squares residual")
    cost0 = 0.5 * float(r0 @ r0)
    tracker.accept(x0, cost0)  # the LM path's seed; a no-op after the TRF wrapper
    if len(x0) == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None,
                          solver=solver,
                          n_degenerate_cell_probes=cell_guard.n_degenerate)

    n_truncated, truncated_by = 0, {}
    # one budget, in residual evaluations, for both drivers (WP-1937)
    max_nfev = max_iter * NFEV_PER_ITERATION
    if solver == "lm":
        # the strain cone and the Γ_G² and Γ_L floors (WP-1938 D7, WP-2002)
        # are built against the *starting* point, because feasibility is
        # maintained rather than restored (see the builders)
        ineqs = _pad_inequalities(
            strain_cone_inequalities(model, table, x0[:n_table])
            + texture_positivity_inequalities(model, table, x0[:n_table])
            + gaussian_width_inequalities(model, table, x0[:n_table])
            + lorentzian_width_inequalities(model, table, x0[:n_table]), n_aux)
        from . import lm as lm_mod

        # a Pawley block past the BVLS cut takes its normal matrix sparse,
        # where its windows are narrow enough (``PAWLEY_SPARSE_DENSITY``), so
        # the projected CG can precondition (WP-2011).  numpy only: the
        # pattern is read off the writer in ``_make_jacobian``, and the
        # traced backends' columns were never checked against it
        normal_equations = (_pawley_normal_equations(model, n_table)
                            if model.pawley is not None and backend == "numpy"
                            and len(x0) > lm_mod.BVLS_MAX_COLUMNS else None)
        res = _lm_outcome(residual, jacobian, x0, lo, hi, max_nfev=max_nfev,
                          ftol=ftol, inequalities=ineqs, events=events, stage=stage,
                          track=tracker, table=table,
                          normal_equations=normal_equations)
        n_truncated, truncated_by = res.n_truncated, res.truncated_by
    else:
        with lapack.scipy_trf():
            res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                                ftol=ftol, xtol=XTOL, gtol=GTOL, max_nfev=max_nfev)
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")
    termination = (res.termination if solver == "lm"
                   else _TRF_TERMINATION.get(res.status, str(res.status)))

    # esds from the *full* augmented covariance (table ↔ intensity correlation
    # feeds the table esds too), then split: table columns stay in the outcome,
    # the intensity tail lands on the model's Pawley block.
    stderr = corr = stderr_full = None
    covariance_error = esd_inflation = None
    moment_angle_tests = None
    if compute_uncertainties and res.jac is not None and len(res.fun) > len(res.x):
        # a moment angle at a direction the symmetry fixes leaves the
        # covariance, and only the covariance (WP-1929)
        moment_angle_tests, stationary = stationary_angle_test(
            probe, res.x, res.jac, len(model.tt), table.free_paths,
            _column_entries([table], [np.arange(n_table)], len(res.x)),
            len(res.x))
        stderr_full, corr_full, esd_inflation, covariance_error = _guarded_covariance(
            _without_columns(res.jac, stationary), res.fun, len(res.x),
            n_data=len(model.tt))
    if stderr_full is not None:
        stderr, corr = stderr_full[:n_table], corr_full[:n_table, :n_table]
        if model.pawley is not None:
            model.pawley.stderr = stderr_full[n_table:]
    if model.pawley is not None:
        # pin the final refined intensities into the per-phase buffers (the last
        # residual eval is not guaranteed to sit exactly at the solution)
        model.set_pawley_intensities(res.x[n_table:])
    jac_table = np.asarray(res.jac)[:, :n_table] if res.jac is not None else None
    # off the *full* augmented Jacobian, then sliced to the table columns: the
    # aux block's own angles belong with the Pawley intensities, not here
    cos_table = _residual_cosine(res.jac, res.fun)
    if cos_table is not None:
        cos_table = cos_table[:n_table]
    return LSQOutcome(res.x[:n_table], cost0, float(res.cost), int(res.nfev), status,
                      jac_table, stderr, corr, n_aux=n_aux, solver=solver,
                      residual_cosine=cos_table,
                      active_bounds=_active_bounds(res, n_table),
                      n_constraint_truncations=n_truncated,
                      truncated_by=truncated_by,
                      max_shift_over_esd=_final_shift_over_esd(
                          table, tracker.step(), stderr_full, corr, n_table),
                      termination=termination,
                      n_degenerate_cell_probes=cell_guard.n_degenerate,
                      n_lapack_fallbacks=lapack.retries() - lapack_start,
                      covariance_error=covariance_error,
                      esd_inflation=esd_inflation,
                      moment_angle_tests=moment_angle_tests)


def _stacked_rows(models: list[CompiledModel]) -> tuple[int, int]:
    """``(n_data_total, n_rows)`` of the stacked joint residual: every
    histogram's data rows, then every histogram's background-penalty rows."""
    n_data = sum(len(m.tt) for m in models)
    n_pen = sum(0 if m.bkg_penalty is None else m.bkg_penalty.shape[0] for m in models)
    return n_data, n_data + n_pen


def _multi_closures(models: list[CompiledModel], mtable: "MultiParameterTable",
                    *, weights: list[float] | None = None,
                    backend: str = "numpy", layout: str = "dense"):
    """(residual, jacobian, n_data_total) for the stacked multi-histogram solve.

    Split out of :func:`run_multi_least_squares` so the stacked layout is
    reachable without running a solve — WP-0404's cross-backend matrix compares
    this Jacobian across backends exactly as the solver would build it.

    ``layout="blocked"`` returns the same Jacobian as a
    :class:`~.blocked.BlockJacobian`, each histogram's weighted rows against
    its own columns, whose :meth:`~.blocked.BlockJacobian.toarray` is the
    dense matrix entry for entry (WP-1325).
    """
    if layout not in blocked.LAYOUTS:
        raise ValueError(f"unknown Jacobian layout {layout!r}; "
                         f"available: {', '.join(blocked.LAYOUTS)}")
    n_hist = len(models)
    if any(m.restraints is not None for m in models):
        # The stacked layout sizes the below-data slot from the background
        # penalty rows only, and a shared structure's restraints would land
        # once per histogram.  Deferred since WP-0406; owned by WP-1995.
        raise NotImplementedError(
            "soft restraints are not yet supported in a multi-histogram joint "
            "refinement; run each restrained phase in a single-histogram fit")
    weights = [1.0] * n_hist if weights is None else list(weights)
    if len(weights) != n_hist:
        raise ValueError("weights must have one entry per histogram")
    sqrt_w = [float(np.sqrt(w)) for w in weights]

    residuals = [_make_residual(m, t) for m, t in zip(models, mtable.tables, strict=True)]
    jacobians = [_jacobian_for(m, t, backend)
                 for m, t in zip(models, mtable.tables, strict=True)]
    n_data = [len(m.tt) for m in models]
    n_pen = [0 if m.bkg_penalty is None else m.bkg_penalty.shape[0] for m in models]
    data_off = np.concatenate([[0], np.cumsum(n_data)])
    n_data_total = int(data_off[-1])
    pen_off = n_data_total + np.concatenate([[0], np.cumsum(n_pen)])
    n_rows = int(pen_off[-1])
    n_cols = len(mtable.free_paths)

    def residual(theta: np.ndarray) -> np.ndarray:
        thetas = mtable.split(theta)
        data_parts: list[np.ndarray] = []
        pen_parts: list[np.ndarray] = []
        for h in range(n_hist):
            r = residuals[h](thetas[h])
            data_parts.append(sqrt_w[h] * r[:n_data[h]])
            if n_pen[h]:
                pen_parts.append(sqrt_w[h] * r[n_data[h]:])
        return np.concatenate(data_parts + pen_parts) if n_rows else np.zeros(0)

    def jacobian(theta: np.ndarray) -> np.ndarray:
        thetas = mtable.split(theta)
        J = np.zeros((n_rows, n_cols), dtype=np.float64)
        for h in range(n_hist):
            Jh = jacobians[h](thetas[h])
            cm = mtable.col_map(h)
            do = int(data_off[h])
            J[do:do + n_data[h], cm] = sqrt_w[h] * Jh[:n_data[h]]
            if n_pen[h]:
                po = int(pen_off[h])
                J[po:po + n_pen[h], cm] = sqrt_w[h] * Jh[n_data[h]:]
        return J

    def block_jacobian(theta: np.ndarray) -> BlockJacobian:
        # the dense closure's entries, never scattered: each histogram's rows
        # stay against its own columns (WP-1325)
        thetas = mtable.split(theta)
        return BlockJacobian(
            [sqrt_w[h] * jacobians[h](thetas[h]) for h in range(n_hist)],
            [mtable.col_map(h) for h in range(n_hist)], n_data, n_pen, n_cols)

    return (residual, jacobian if layout == "dense" else block_jacobian,
            n_data_total)


def run_multi_least_squares(models: list[CompiledModel],
                            mtable: "MultiParameterTable", *,
                            weights: list[float] | None = None,
                            max_iter: int = 100, ftol: float = FTOL,
                            compute_uncertainties: bool = True,
                            backend: str = "numpy",
                            solver: str = DEFAULT_SOLVER,
                            events=None, stage: str = "",
                            cancel=None,
                            phase_support_sigma: float | None = PHASE_SUPPORT_SIGMA
                            ) -> LSQOutcome:
    """Joint solve of several histograms stacked into one residual (WP-0308).

    Each histogram keeps its own compiled model (⇒ its own frozen hkl list,
    windows, FCJ node counts) and its own :class:`ParameterTable`; the combined
    free vector θ threads through them via ``mtable``'s column map, so a *shared*
    structural column (cell, coordinates, ADPs …) receives Jacobian
    contributions from *every* histogram — that is what refines the shared
    quantity better than any single pattern could.

    Row layout is [all histograms' data rows] then [all histograms' background-
    penalty rows], so :func:`covariance_estimates` (which treats the first
    ``n_data`` rows as data for χ² and the Bérar-Lelann factor) is reused
    verbatim.  The BL run-of-signs statistic is therefore evaluated on the
    *concatenated* data residual: WP-0407 examined this and kept it as-is —
    each histogram join contaminates the statistic with at most one artificial
    run boundary (a point where consecutive residuals are not 2θ-neighbours),
    i.e. ≤ ``n_hist − 1`` boundaries out of ``n_data_total``, negligible for the
    handful of patterns co-refined here.  A per-histogram decomposition was not
    adopted because BL applies as a single scalar to the whole covariance
    diagonal and a *shared* parameter draws from every histogram, so there is
    no clean single per-parameter factor to combine.  A per-histogram scalar
    weight ``w_h`` scales both that
    histogram's data and its penalty rows by ``√w_h`` — keeping the smoothness
    prior's strength relative to the data fixed; default unit weights leave the
    residual identical to N independent solves sharing the structure.

    ``solver`` selects the driver exactly as in :func:`run_least_squares` —
    this is the *second* entry point WP-0308 warned about, and a solver swap
    that reached only the single-histogram one would leave joint refinements
    silently on scipy.  The Stephens cone is not built here: its rows are
    per-model and the stacked column map would have to scatter each phase's T
    into the joint vector.  Deferred rather than half-done — a joint refinement
    with `solver="lm"` gets the bounded driver, not the cone.

    ``events``, ``stage`` and ``cancel`` are :func:`run_least_squares`' own
    (WP-1341).  An ``eval`` is one evaluation of the *stacked* residual, so
    its ``cost`` and its ``values`` are the joint solve's, aligned with
    ``mtable.free_paths``.  ``phase_support_sigma`` is
    :func:`run_least_squares`' own too (WP-2002, B1).

    The stacked Jacobian is held one of two ways (WP-1325), chosen by
    :func:`.blocked.choose_layout` and recorded on
    :attr:`LSQOutcome.jacobian_layout`: dense, as every joint fit was before,
    or as a :class:`~.blocked.BlockJacobian` once the dense matrix would pass
    :data:`.blocked.DENSE_JACOBIAN_MAX_BYTES`.  Blocked, the LM driver forms
    its normal equations block by block and the covariance is the Schur
    complement of the arrow; every reader below takes the blocks.
    """
    if solver not in SOLVERS:
        raise ValueError(f"unknown solver {solver!r}; available: {', '.join(SOLVERS)}")
    lapack_start = lapack.retries()
    # dense below a size, blocked above it (WP-1325, ``blocked.choose_layout``)
    layout = blocked.choose_layout(_stacked_rows(models)[1], len(mtable.free_paths),
                                   solver)
    residual, jacobian, n_data_total = _multi_closures(
        models, mtable, weights=weights, backend=backend, layout=layout)
    # The same two guards :func:`run_least_squares` wires up, for the same
    # reason and on the same closures: ``_multi_closures`` stacks the very
    # ``_make_residual``/``_jacobian_for`` pairs that function wraps, and a
    # shared cell is unbounded here exactly as it is there
    # (``_freeze_cell_windows_multi`` windows only phases below support).  Left
    # unguarded this entry point turned issue #283's survivable
    # ``RuntimeWarning`` into a stage-killing ``DegenerateCellError``, which is
    # the outcome the guards exist to prevent.
    cell_guard = _DegenerateCellGuard(residual)
    residual = cell_guard
    jacobian = _DegenerateCellJacobianGuard(jacobian, cell_guard)
    n_cols = len(mtable.free_paths)

    if cancel is not None:
        # read at an evaluation boundary, below the event wrapper, as in
        # :func:`run_least_squares`
        residual = _cancellable(residual, cancel, stage)

    # the closure the stationary-angle test probes after the solve, taken
    # below the TRF wrapper for :func:`run_least_squares`' reason: a probe
    # must not emit an ``eval`` or move the step tracker
    # ``max_shift_over_esd`` is read from
    probe = residual
    tracker = _StepTracker()
    if solver == "trf":
        # scipy TRF has no accepted-point hook, so the residual closure is
        # the hook, as in :func:`run_least_squares`
        residual = _tracked(residual, tracker, events, stage, mtable)

    # sample caps first: ``_freeze_cell_windows_multi`` ends in
    # ``refresh_bounds``, which is what pushes *all three* freezes into the
    # combined bound vectors
    _freeze_strain_cap_multi(models, mtable)
    _freeze_size_cap_multi(models, mtable)
    _freeze_cell_windows_multi(models, mtable, phase_support_sigma)
    x0 = mtable.x0()
    lo, hi = mtable.bounds()
    x0 = _feasible_start(x0, lo, hi, solver)
    r0 = residual(x0)
    require_fp64(r0, "least-squares residual")
    cost0 = 0.5 * float(r0 @ r0)
    tracker.accept(x0, cost0)  # the LM path's seed; a no-op after the TRF wrapper
    if n_cols == 0:
        return LSQOutcome(x0, cost0, cost0, 0, "converged", None, None, None,
                          solver=solver,
                          n_degenerate_cell_probes=cell_guard.n_degenerate,
                          jacobian_layout=layout)

    max_nfev = max_iter * NFEV_PER_ITERATION
    if solver == "lm":
        res = _lm_outcome(residual, jacobian, x0, lo, hi, max_nfev=max_nfev,
                          ftol=ftol,
                          inequalities=_joint_width_inequalities(models, mtable, x0),
                          events=events, stage=stage, track=tracker, table=mtable)
    else:
        with lapack.scipy_trf():
            res = least_squares(residual, x0, jac=jacobian, bounds=(lo, hi), method="trf",
                                ftol=ftol, xtol=XTOL, gtol=GTOL, max_nfev=max_nfev)
    status = "converged" if res.status > 0 else ("max_iter" if res.status == 0 else "diverged")
    termination = (res.termination if solver == "lm"
                   else _TRF_TERMINATION.get(res.status, str(res.status)))

    stderr = corr = covariance_error = moment_angle_tests = esd_inflation = None
    if compute_uncertainties and res.jac is not None and len(res.fun) > len(res.x):
        # the single-histogram rule (WP-1929) on the stacked residual: a
        # moment angle's column is every histogram's rows of it, and a shared
        # angle is stationary only where the joint χ² says so
        moment_angle_tests, stationary = stationary_angle_test(
            probe, res.x, res.jac, n_data_total, mtable.free_paths,
            _column_entries(mtable.tables,
                           [mtable.col_map(h) for h in range(len(mtable.tables))],
                           len(res.x)),
            len(res.x))
        stderr, corr, esd_inflation, covariance_error = _guarded_covariance(
            _without_columns(res.jac, stationary), res.fun, len(res.x),
            n_data=n_data_total)
    if isinstance(res.jac, BlockJacobian):
        jac_data = res.jac.data_rows()
    else:
        jac_data = np.asarray(res.jac)[:n_data_total] if res.jac is not None else None
    # ``jac_data`` drops the penalty and restraint *rows*; the angle keeps
    # them, being read off the cost the driver actually minimised
    return LSQOutcome(res.x, cost0, float(res.cost), int(res.nfev), status,
                      jac_data, stderr, corr, solver=solver,
                      residual_cosine=_residual_cosine(res.jac, res.fun),
                      active_bounds=_active_bounds(res, len(res.x)),
                      max_shift_over_esd=_final_shift_over_esd_multi(
                          mtable, tracker.step(), stderr, corr),
                      termination=termination,
                      n_degenerate_cell_probes=cell_guard.n_degenerate,
                      n_lapack_fallbacks=lapack.retries() - lapack_start,
                      covariance_error=covariance_error,
                      esd_inflation=esd_inflation,
                      moment_angle_tests=moment_angle_tests,
                      jacobian_layout=layout)


def covariance_estimates(jac: np.ndarray, fun: np.ndarray, n_free: int,
                         n_data: int | None = None
                         ) -> tuple[np.ndarray, np.ndarray]:
    """Esds and correlation matrix from the weighted Jacobian at the solution.

    Cov = χ²_red · (JᵀJ)⁻¹ with χ²_red = Σr²/(N−P); esd_i = √Cov_ii, then
    multiplied by the Bérar-Lelann serial-correlation factor (Bérar & Lelann,
    1991, J. Appl. Cryst. 24, 1, § IV — see ``statistics.berar_lelann_factor``).  The
    returned esds therefore carry the inflation; the correlation matrix does
    **not** — it is the true Pearson matrix (unit diagonal) normalised by the
    *raw* sqrt-diagonal, so a genuinely degenerate pair reports |ρ| ≈ 1 and the
    0.98 high-correlation guard means what it says (WP-0407 fixed a placement
    bug where normalising by the inflated diagonal left corr with a 1/BL²
    diagonal, cancelling BL in the reported physical esds and deflating the
    guard).  A pseudo-inverse guards against singular normal matrices.

    Both esd consumers inherit the inflation: table esds flow through
    ``ParameterTable.stderr_physical`` as ``diag(C·corr·outer(s,s)·Cᵀ)`` with
    ``s`` already ×BL and ``corr`` now unit-diagonal (no cancellation), and the
    Pawley per-hkl tail (``model.pawley.stderr`` in :func:`run_least_squares`)
    is a slice of this ×BL diagonal used directly.

    With P-spline penalty rows appended (rows beyond ``n_data``), JᵀJ keeps
    them — (J_dᵀJ_d + λD₂ᵀD₂)⁻¹ is the regularised covariance — but χ² and
    the serial-correlation factor are evaluated on the *data* rows only
    (run-of-sign statistics on penalty rows would be meaningless).

    The solve is fp64 unconditionally (architecture invariant 2): cond(JᵀJ) =
    cond(J)², so forming and inverting the normal matrix is the step reduced
    precision can never take.  ``to_host_fp64`` is that boundary — a Jacobian
    whose columns were computed at fp32 is upcast here before JᵀJ, while the
    residual is *required* to have been fp64 all along.

    The pinv guarding, the symmetrisation and the fp64 boundary live in
    :func:`statistics.normal_factors`, shared with the per-peak profile fits
    (WP-1018) so the two surfaces cannot disagree about them; the final clip
    below removes the 1-ulp overshoot ``eigh`` can leave, so a reported
    correlation is always a valid one.  Note the clip is *not* the fix —
    clipping a 2.75 to 1.0 would report a degeneracy that the arithmetic, not
    the data, invented.

    :func:`_covariance_and_inflation` returns the same pair with the factor
    beside it.
    """
    stderr, corr, _ = _covariance_and_inflation(jac, fun, n_free, n_data)
    return stderr, corr


def _covariance_and_inflation(jac: np.ndarray, fun: np.ndarray, n_free: int,
                              n_data: int | None = None
                              ) -> tuple[np.ndarray, np.ndarray, float]:
    """:func:`covariance_estimates`' esds and correlation, and the Bérar-Lelann
    factor those esds were multiplied by.

    The factor is returned rather than recomputed by a caller because it is
    measured on the solve's own last residual, and the residual a result's
    ``Statistics.esd_inflation`` is measured on is another one, built at the
    result's own compile.  Measured on 11-BM NAC (2-24°), the two differ by
    0.07 % on a Rietveld fit and 0.75 % on a Le Bail fit; on a joint fit
    weighted 1:4 they differ by 4 %, since the solve's residual carries the
    weights (WP-2002, B4).  ``RefinedParameter.stderr_uncorrected`` divides
    by this one.
    """
    from .statistics import (
        berar_lelann_factor,
        covariance_from_factors,
        normal_factors,
    )

    data = fun if n_data is None else fun[:n_data]
    # ``normal_covariance`` in its two factors, so the esd below can be taken
    # where the product overflows
    k, inv_d, _chi2_red = normal_factors(jac, data, n_free)
    live = inv_d > 0.0
    cov = covariance_from_factors(k, inv_d)
    # Normalise the correlation by the *raw* (un-inflated) sqrt-diagonal so it is
    # a true Pearson matrix with unit diagonal; apply Bérar-Lelann only to the
    # returned esd diagonal.  Normalising by the inflated diagonal instead (the
    # pre-WP-0407 bug) left corr with a 1/BL² diagonal, which then cancelled the
    # BL factor exactly inside ``ParameterTable.stderr_physical`` (making the
    # reported physical esds effectively raw) and deflated every off-diagonal by
    # BL² (killing the 0.98 high-correlation guard).
    sqrt = np.sqrt(np.maximum(np.diag(cov), 0.0))
    # A live column whose variance has no double can still have an esd that
    # does: one at a variance of ~1e+330 has an esd of ~1e+165 (WP-1463 met it
    # on a softplus scale at 1e-166, before WP-1938).  So the
    # root is taken before the product there, and its correlations come from
    # the scale-free K, where the product form would divide inf by inf.
    wide = live & ~np.isfinite(sqrt)
    if wide.any():
        # masked on ``live``: ``pinv`` leaves rounding-level entries in a dead
        # column's row of K (1e-35 measured), which the product form zeroes
        # through 1/d = 0 and a ratio of K entries would read as a correlation
        kd = np.where(live, np.sqrt(np.maximum(np.diag(k), 0.0)), 0.0)
        sqrt[wide] = inv_d[wide] * kd[wide]
    # the outer product is inside the errstate, not before it: with WP-1110's
    # infinite variance on a gradient-free column and an exactly-zero one on a
    # direction the pinv dropped, ``denom`` has a genuine 0 × inf.  The NaN is
    # then *discarded* correctly — ``nan > 0`` is False, so that pair's
    # correlation is 0, which is what it should be — but a RuntimeWarning
    # raised from a covariance path is noise that hides the next real one.
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        denom = np.outer(sqrt, sqrt)
        corr = np.where(denom > 0, cov / denom, 0.0)
        if wide.any():
            kk = np.outer(kd, kd)
            k_corr = np.where(kk > 0, k / kk, 0.0)
            corr[wide, :] = k_corr[wide, :]
            corr[:, wide] = k_corr[:, wide]
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, np.where(sqrt > 0.0, 1.0, 0.0))
    factor = berar_lelann_factor(data)
    return sqrt * factor, corr, factor
