"""Score, gate, group and rank held parameters from one Jacobian (WP-1050).

The score is the Rao / Gauss-Newton one-parameter gain
(:func:`~rietx.optimize.statistics.one_parameter_gains`); both gates run
through :func:`~rietx.optimize.statistics.block_projection_r2` — absorption
of a candidate by the currently-free block directly, candidate-vs-candidate
ties on the free-block-projected columns.  This module sees only matrices,
paths and constants: enumerating candidates, seeding floored roughness and
Stephens rows and compiling the probe model are
:meth:`rietx.refine.Refinement.suggest`'s job, and the Layer-2
cross-reference arrives as already-built *objects*,
because ``strategy`` builds no ``report`` object and imports none at module
scope.

The single exception is a *number*: ΔBIC (WP-1305) is
:func:`rietx.report.layer2.delta_bic`, imported inside the call the way
``indexing/extinction.py`` reaches the same function, so the package keeps one
BIC formula instead of a second copy pinned to the first by a test.  Writing
``gain − n·ln(N)`` here would have been that copy *and* a weaker statement: it
is the exact form only where the probe's χ²/N is 1, and the noise floor one
gate over already refuses that assumption (``max(chi2_red, 1)``).
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ..optimize.statistics import (
    _off_span,
    _span_basis,
    block_projection_r2,
    column_rescale,
    effective_sample_size,
    one_parameter_gains,
)
from ..schemas.suggest import (
    SUGGEST_ABSORPTION_MAX,
    SUGGEST_GROUP_R2,
    SUGGEST_MIN_GAIN,
    CandidateGroup,
    ParameterCandidate,
    SuggestionResult,
)
from .staged import ROUGHNESS_SEED, STRAIN_SEED_PPM

#: Probe seeds, per family.  Two kinds of floor candidate are scored at the
#: seed the corresponding stage would start its solve from (the
#: ``strategy/staged.py`` constants: :data:`~.staged.ROUGHNESS_SEED` and
#: :data:`~.staged.STRAIN_SEED_PPM`), and report ``seeded=True``.  A Stephens block at
#: S ≡ 0 sits on √Σ's unbounded slope (an FD there returns an h-dependent
#: value, not a derivative).  Suortti roughness at b = 0 is the *identity*,
#: and 0.3 is ``_ROUGHNESS_STAGE``'s measured start.
#:
#: **A width on its floor is scored where it is, from its physical column.**
#: Until WP-1938 a width at 0 was probed from 1e-3, because its softplus
#: column there came out of the FD chain as rounding noise.  Kept after the
#: physical coordinates arrived, that seed manufactured suggestions.  On BT-1
#: X-ray it put ``phases.0.lor_size`` (predicted gain 18 910),
#: ``lor_strain`` (15 040), ``gauss_size`` (11 000) and ``gauss_strain``
#: (7 348) at the top.  On Si 640c it put ``instrument.profile.x`` (1 465)
#: and ``profile.y`` (1 228) there.  Freed and refitted, every one of them
#: stayed on its floor and χ² did not move (Δχ² = 0.000).  Unseeded, the top
#: suggestion on BT-1 X-ray is ``phases.0.atoms.2.occ`` (predicted gain
#: 946.6, refitted Δχ² −945.5) and on Si 640c ``phases.0.extinction``
#: (predicted 757.9, refitted −2478.9).
#:
#: The seeds live in a **second** probe build whose only contribution is
#: those columns — never in the shared residual: measured on the layers
#: suite's truth fixture, seeding the shared state instead broadens every
#: peak, moves probe χ²_red from 1.01 to 7.1, and hands every width
#: parameter a spurious gain ≈ 3×10⁴ at a *converged* fit
#: (``Refinement.suggest`` implements the split and tells the same story).
SUGGEST_SEED_ROUGHNESS = ROUGHNESS_SEED
SUGGEST_SEED_STEPHENS = STRAIN_SEED_PPM


@dataclass(frozen=True)
class Candidate:
    """One held-but-refinable parameter as the caller enumerated it.

    ``index`` is the parameter's column in the probe Jacobian, in the
    parameter's own units (WP-1938), and ``value``/``lo``/``hi`` where on that
    axis it sits and what the solver would let it reach.  A roughness or Stephens candidate on
    its floor is scored at its seed and arrives here with ``seeded=True`` and
    its ``seed_value``.  Every other candidate, a width on 0 included, is
    scored at its stored value.
    """

    path: str
    index: int
    seeded: bool = False
    seed_value: float | None = None
    #: the point the column was measured at and the solver's box around it,
    #: all in the column's own units (WP-1998): ``ParameterTable.x0()`` and
    #: ``.bounds()`` after seeding, so a seeded row's box is measured from its
    #: seed.  ``value=None`` (or both sides infinite) means no box: the gain is
    #: the unbounded one, bit for bit.
    value: float | None = None
    lo: float = -np.inf
    hi: float = np.inf


def _union_find_groups(n: int, linked: list[tuple[int, int]]) -> list[list[int]]:
    """Connected components over ``n`` items from pairwise links."""
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b in linked:
        parent[find(a)] = find(b)
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    return list(comps.values())


def _box_offsets(c: Candidate) -> tuple[float, float] | None:
    """The step room ``(lo − v, hi − v)`` a candidate's box leaves, or ``None``.

    ``None`` is "no box": no point given, or both sides infinite.  A value
    outside its own box (a tie window narrower than the stored value) gives a
    side of the wrong sign, which the callers read as no room that way.
    """
    if c.value is None or not (np.isfinite(c.lo) or np.isfinite(c.hi)):
        return None
    return float(c.lo) - float(c.value), float(c.hi) - float(c.value)


def _scaled(col: np.ndarray) -> tuple[np.ndarray, float]:
    """A column brought into range by :func:`column_rescale`, and its factor."""
    s = column_rescale(col[:, None])
    f = 1.0 if s is None else float(s[0])
    return (col if s is None else col * f), f


def _bounded_single(jac: np.ndarray, q: np.ndarray | None, rt: np.ndarray,
                    c: Candidate, gain: float) -> float:
    """The one-parameter gain reachable inside ``c``'s box (WP-1998).

    With the free block ``F`` projected out of the column and the residual
    (:func:`one_parameter_gains`), the linearised Σr² along the candidate is
    the exact quadratic ``‖r̃ + j̃ δ‖²`` in its step δ: the free block is
    re-solved at every δ, so nothing else is approximated.  It falls by
    ``gain`` at the unconstrained step δ* = −j̃ᵀr̃ / j̃ᵀj̃ and by
    ``gain·α(2 − α)`` at the step α·δ*, so with ``d`` the room the box leaves
    in δ*'s direction the reachable gain is that at α = min(1, d/|δ*|) — zero
    on a bound with δ* pointing out of the box, ``gain`` to the bit when the
    bound is farther than the step (α = 1).
    """
    room = _box_offsets(c)
    if room is None or gain <= 0.0:
        return gain
    j, f = _scaled(np.asarray(jac[:, c.index], dtype=np.float64))
    jt = _off_span(q, j) if q is not None else j
    denom = float(jt @ jt)
    if denom <= 0.0:
        return gain
    step = -float(jt @ rt) / denom * f          # δ*, back in the column's units
    if step == 0.0:
        return gain
    d = room[1] if step > 0.0 else -room[0]
    if d <= 0.0:                    # on the bound (or past it), facing out
        return 0.0
    alpha = min(1.0, d / abs(step))
    return gain if alpha == 1.0 else gain * alpha * (2.0 - alpha)


def _bounded_group(jac: np.ndarray, q: np.ndarray | None, rt: np.ndarray,
                   members: Sequence[Candidate], gain: float) -> float:
    """A group's joint gain reachable inside its members' boxes (WP-1998).

    The group's own linearised problem is min ‖r̃ + J̃_G u‖² over the box.  When
    the unconstrained least-squares step already lies inside it the joint gain
    is returned unchanged; otherwise the bounded problem is solved exactly
    (Lawson & Hanson's bounded-variable least squares, Stark & Parker 1995,
    *Comput. Stat.* 10, 129, as ``scipy.optimize.lsq_linear(method="bvls")``)
    on unit-norm columns, and the gain is what that answer reaches, never more
    than the unbounded joint gain.
    """
    rooms = [_box_offsets(c) for c in members]
    if all(r is None for r in rooms) or gain <= 0.0:
        return gain
    cols, scales = zip(*(_scaled(np.asarray(jac[:, c.index], dtype=np.float64))
                         for c in members))
    b = np.column_stack(cols)
    if q is not None:
        b = _off_span(q, b)
    norms = np.linalg.norm(b, axis=0)
    if not np.all(norms > 0.0):
        return gain
    b = b / norms
    # u_i (column units) = w_i · scale_i / norm_i
    to_w = norms / np.asarray(scales)
    # a value outside its own box leaves a side of the wrong sign: no room
    # that way, as in :func:`_bounded_single`
    lo = np.minimum([-np.inf if r is None else r[0] for r in rooms], 0.0) * to_w
    hi = np.maximum([np.inf if r is None else r[1] for r in rooms], 0.0) * to_w
    w, *_ = np.linalg.lstsq(b, -rt, rcond=None)
    if np.all((w >= lo) & (w <= hi)):
        return gain
    from scipy.optimize import lsq_linear

    hi = np.where(hi > lo, hi, np.nextafter(lo, np.inf))   # BVLS wants lo < hi
    sol = lsq_linear(b, -rt, bounds=(lo, hi), method="bvls")
    after = rt + b @ sol.x
    return min(gain, max(float(rt @ rt) - float(after @ after), 0.0))


def _matched_action_kind(path: str, actions: Sequence) -> str | None:
    """First (highest-confidence) action whose paths match this candidate.

    The two-way fnmatch mirrors :func:`rietx.report.apply_strategy_veto`:
    either side of the comparison may be the glob.
    """
    for action in actions:
        for glob in getattr(action, "parameter_paths", []):
            if fnmatch.fnmatchcase(glob, path) or fnmatch.fnmatchcase(path, glob):
                return str(action.kind)
    return None


def build_suggestion(jac: np.ndarray, resid: np.ndarray, free: list[int],
                     candidates: Sequence[Candidate], *, chi2_red: float,
                     top_n: int = 5, actions: Sequence = (),
                     esd_inflation: float | None = None,
                     ) -> SuggestionResult:
    """Rank ``candidates`` by predicted Δχ², gated so a tie is never a winner.

    ``jac``/``resid`` are the solver's weighted rows for the **combined**
    table (free ∪ candidates — penalty and restraint rows included, or
    absorption is overstated); ``free`` indexes the currently-free columns.
    ``actions`` are FitReport Layer-2 ``SuggestedAction``s (duck-typed:
    ``.kind`` and ``.parameter_paths``), already confidence-sorted, used only
    to annotate agreement between the two methods.

    Every gain is the one **reachable inside the candidate's box** (WP-1998;
    :func:`_bounded_single`, :func:`_bounded_group`): a parameter on its
    floor whose gradient points through it scores zero, and the unbounded
    figure rides beside it as ``gain_unbounded``.  A candidate whose
    unbounded gain clears the noise floor and whose reachable one does not
    is listed in ``bound_limited`` rather than dropped.

    ``esd_inflation`` is the Bérar-Lelann factor of the state's data rows;
    ΔBIC is charged at ``effective_sample_size`` of it (#270), and at the raw
    row count when it is ``None``.
    """
    jac = np.asarray(jac)
    resid = np.asarray(resid, dtype=np.float64)
    targets = [(c.index, c.path) for c in candidates]
    gains = one_parameter_gains(jac, resid, free, targets)
    absorption = block_projection_r2(jac, free, targets) if free else {}
    skipped = [c.path for c in candidates if c.path not in gains]
    # the free-block projection every bounded gain is measured in, the one
    # ``one_parameter_gains`` built its own from
    q = _span_basis(jac, free) if free else None
    rt = _off_span(q, resid) if q is not None else resid

    scored: list[tuple[Candidate, ParameterCandidate]] = []
    for c in candidates:
        if c.path not in gains:
            continue
        gradient = 2.0 * float(jac[:, c.index] @ resid)
        scored.append((c, ParameterCandidate(
            path=c.path, gain=_bounded_single(jac, q, rt, c, gains[c.path]),
            gain_unbounded=gains[c.path], gradient=gradient,
            absorption=absorption.get(c.path, 0.0), seeded=c.seeded,
            seed_value=c.seed_value,
            action_kind=_matched_action_kind(c.path, actions))))

    non_separable = [pc for _, pc in scored
                     if pc.absorption > SUGGEST_ABSORPTION_MAX]
    floor = SUGGEST_MIN_GAIN * max(chi2_red, 1.0)
    survivors = [(c, pc) for c, pc in scored
                 if pc.absorption <= SUGGEST_ABSORPTION_MAX and pc.gain > floor]
    # what the box, not the data, kept off the list: leverage above the floor
    # that no step inside the bounds can reach
    bound_limited = [pc for _, pc in scored
                     if pc.absorption <= SUGGEST_ABSORPTION_MAX
                     and pc.gain <= floor < pc.gain_unbounded]

    # candidate-vs-candidate ties, measured on the free-block-projected
    # columns (one shared projection, then ρ² per pair through the same
    # block_projection_r2 every other collinearity statistic uses)
    proj = _off_span(q, jac) if q is not None else jac
    links: list[tuple[int, int]] = []
    for a in range(len(survivors)):
        ca = survivors[a][0]
        others = [(survivors[b][0].index, str(b)) for b in range(a + 1, len(survivors))]
        if not others:
            continue
        rho2 = block_projection_r2(proj, [ca.index], others)
        links += [(a, int(key)) for key, r2 in rho2.items()
                  if r2 > SUGGEST_GROUP_R2]

    # the restricted model's own weighted SSR and row count: what ΔBIC below
    # compares the predicted freed model against (the residual carries every
    # block — penalty and restraint rows included — because the gain does)
    chi2_state = float(resid @ resid)
    n_rows = len(resid)
    n_eff = (None if esd_inflation is None
             else effective_sample_size(n_rows, esd_inflation))

    groups: list[CandidateGroup] = []
    for comp in _union_find_groups(len(survivors), links):
        members = sorted((survivors[i][1] for i in comp),
                         key=lambda pc: (-pc.gain, pc.path))
        if len(members) == 1:
            gain = members[0].gain
        else:
            cols = [survivors[i][0].index for i in comp]
            gain = one_parameter_gains(jac, resid, free, [(cols, "g")])["g"]
            gain = _bounded_group(jac, q, rt, [survivors[i][0] for i in comp],
                                  gain)
        groups.append(CandidateGroup(
            members=members, gain=gain, resolved=len(members) == 1,
            delta_bic=_predicted_delta_bic(gain, len(members),
                                           chi2_state, n_rows, n_eff),
            delta_bic_raw_n=_predicted_delta_bic(gain, len(members),
                                                 chi2_state, n_rows)))
    groups.sort(key=lambda g: (-g.gain, g.members[0].path))
    groups = groups[:top_n]

    return SuggestionResult(
        groups=groups, non_separable=non_separable,
        bound_limited=bound_limited,
        skipped=skipped, n_evaluated=len(scored), chi2_red=chi2_red,
        noise_floor=floor, n_effective=n_eff,
        summary=_summary(groups, floor, len(scored), len(non_separable),
                         len(skipped), n_rows, n_eff,
                         n_bound_limited=len(bound_limited)))


def _predicted_delta_bic(gain: float, n_added: int, chi2_state: float,
                         n_rows: int, n_effective: float | None = None) -> float:
    """Schwarz's ΔBIC for freeing ``n_added`` parameters, predicted not fitted.

    The package's one BIC form (:func:`rietx.report.layer2.delta_bic`,
    positive favouring the fuller model) evaluated at the Gauss-Newton answer:
    the freed model is predicted to reach ``chi2_state - gain``.  Imported
    inside the call — see this module's docstring on the one edge to
    ``report``.
    """
    from ..report.layer2 import delta_bic

    return delta_bic(chi2_state, chi2_state - gain, n_rows, n_added,
                     n_effective=n_effective)


def _summary(groups: list[CandidateGroup], floor: float, n_evaluated: int,
             n_non_separable: int, n_skipped: int, n_rows: int,
             n_eff: float | None = None, *, n_bound_limited: int = 0) -> str:
    """One deterministic sentence a human or agent can quote.

    The sentence carries both numbers because they answer different questions
    and can disagree: ``Δχ²`` is the leverage that ranks, ΔBIC is whether the
    leverage pays for the parameter at this ``N`` (WP-1305).

    Both are printed no finer than a rerun reproduces them (WP-2002): three
    significant figures of Δχ² and one decimal of ΔBIC, as ``Refinement``'s
    next-step line prints it.  Both move with where the fit stopped.  On the
    fluorapatite guide, starts 1e-14 apart put Δχ² at 96.109 to 96.114 and
    ΔBIC at −1.29940 to −1.29971, and four figures printed that ΔBIC as
    −1.299 or −1.3 by the start.  The noise floor is the data's and did not
    move, so it keeps four.

    The candidates a bound kept below the floor (WP-1998) are counted in the
    tail only when there are any, so a box that changed nothing changes no
    text.
    """
    tail = (f"{n_evaluated} candidate(s) evaluated, {n_non_separable} "
            f"non-separable from the free set, {n_skipped} without leverage"
            + (f", {n_bound_limited} held back by a bound"
               if n_bound_limited else "")
            + f"; noise floor {floor:.4g}")
    if not groups:
        return ("nothing clears the noise floor — the fit is converged for "
                f"every separable held parameter ({tail})")
    top = groups[0]
    if top.resolved:
        head = (f"free {top.members[0].path} next: predicted "
                f"Δχ² {top.gain:.3g}, ΔBIC {top.delta_bic:+.1f}")
        if top.members[0].action_kind:
            head += f" (Layer 2 agrees: {top.members[0].action_kind})"
    else:
        paths = ", ".join(pc.path for pc in top.members)
        head = (f"the data cannot separate {paths}: joint predicted "
                f"Δχ² {top.gain:.3g}, ΔBIC {top.delta_bic:+.1f} — free one, "
                "not on this evidence alone")
    if top.delta_bic <= 0.0:
        head += (f"; ΔBIC refuses it — the predicted gain does not pay for "
                 f"{len(top.members)} parameter(s) at "
                 + (f"N={n_rows}" if n_eff is None else
                    f"N_eff={n_eff:.0f} ({n_rows} rows over the squared "
                    f"esd inflation)"))
    return f"{head} ({tail})"
