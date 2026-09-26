"""Engine C — SVD-Index: propose a metric at random, then let the *assignment*
converge.

*Source*: Coelho, A. A. (2003), *J. Appl. Cryst.* **36**, 86-95, "Indexing of
powder diffraction patterns by iterative use of singular value decomposition".
**Papers only** — TOPAS is closed source and none of it was consulted (CLAUDE.md).

**Where it sits between the other two.**  WP-1021's dichotomy *bounds* Q over
boxes of metrics and is exhaustive; WP-1022's trial and error *assumes* the hkl of
a few base lines and solves the metric exactly.  This one does neither: it starts
from a random metric and alternates two steps that are each trivial —

    assign every observed line to its nearest calculated line;
    re-solve A..F from that assignment by linear least squares

— until the assignment stops changing (Coelho's Table 1, ~3-9 iterations here).
Neither step needs a tolerance, which is the property Coelho advertises over the
dichotomy method: *"it does not require errors in the input d-spacings as input"*.
So its failure mode is a third one again — not a wide domain, not a poisoned base
line, but a **starting metric in the wrong basin** — and that is what makes its
agreement with the other two worth something (``engines.py``).

**WP-1023's Monte Carlo no-go does not fence this, and the distinction is the
whole reason the WP exists.**  That spike scored *raw random cells*.  Both working
Monte Carlo indexers refine every proposal: SVD-Index iterates to a fixed hkl
assignment (this module), and McMaille takes 200-5000 local steps per proposal
(Le Bail 2004 §III).  WP-1023's number stands for what it measured — unrefined
random-cell scoring does not rank — and says nothing about a refined one.

## What was measured before this module was written (WP-1040 task 0)

On the known-cell corpus, one random start per call, calls to Table 1 before the
true lattice is first reached (``reduce.same_lattice``), median of five seeded
runs.  Coelho's own averages are quoted beside them, on simulated 20-line sets:

=================  ==========  =============  ===========
dataset            system      calls to truth  Coelho avg
=================  ==========  =============  ===========
SRM 660c LaB6      cubic        1              1.3
11-BM NAC          cubic        6              1.3
qarr zincite       hexagonal    107            8.3
qarr zircon        tetragonal   150            26.1
GSAS-II FAP        hexagonal    389            8.3
bethanechol F      monoclinic   ~15 000        78
qarr corundum      trigonal     **never**      —
=================  ==========  =============  ===========

Two of those rows are the reason the WP is a go rather than a curiosity.
**bethanechol set F is reached at all**: it is the benchmark the milestone bar is
written on, and ``tests/test_acceptance_indexing.py`` records that an exhaustive
dichotomy over the paper's own domain returns **0 candidates and never finishes**
at 240 s *and* at 900 s.  And the wall clock is a different order: a Table 1 call
is 0.2-3 ms, so the whole ladder is seconds where dichotomy is minutes.

The corpus is also where the four rules below were measured, each of which
contradicts something reasoned from the algorithm's structure.

**1. The N_c/N_o gate is a volume *window*, computable before the search.**
Coelho uses step (ii) as a per-trial abort and step (iv)(a) as a stopping rule
discovered during the sweep.  But N_c — distinct calculated d-spacings inside the
observed sphere — is proportional to the cell volume at fixed Q_max, system and
centring, so one probe measures κ = N_c/V and the gate *is* a bound on V:

    V ∈ [N_o/(3κ), 4·N_o/κ]

a factor-12 window, i.e. 27 rungs of Coelho's ν₁ = 1.1 ladder.  Measured on all
nine corpus datasets, **the window contains the true volume every time**, and
placing the ladder inside it rather than sweeping from an arbitrary floor is what
takes the searches to the seconds above.  See :func:`volume_window`.

**2. N_c counts distinct calculated d-spacings, not hkl** — Table 1's caption says
one and §2's prose the other, and only the prose can be right: LaB6 to 149° 2θ has
~244 Friedel-unique hkl inside its own sphere against 20 driven lines, so an hkl
count puts N_c/N_o at ~12 and the gate refuses the certified cubic cell outright.

**3. The impurity cut belongs in the last pass only, and Coelho says so.**  §2.4
runs Table 1 three times per random start and drops far-lying observed lines only
in the third.  Reasoning from real data says the opposite — our peak lists carry
artifacts that no iteration will index — and the corpus says the reasoning is
wrong: moving the cut into the first pass takes zincite from 5/5 seeded runs to
1/5 and zircon and FAP from 5/5 to **0/5**.  A random starting metric predicts
lines nowhere near the observed ones, so a cut applied there removes nearly
everything and the call dies before it can iterate anywhere.

**4. One line below the lattice's longest d-spacing destroys the eq. (4)
weighting entirely** — and this is the failure simulated data cannot show.  The
qarr corundum list opens at 5.17° 2θ (d = 17 Å) where the pattern itself starts at
5.00°, an edge artifact the acceptance suite already tolerates with
``n_unindexed = 3``.  Corundum's longest real d is 4.33 Å, so that line is 3.9×
beyond anything the lattice can produce; W = d_o⁴·|Δ2θ|·I_o then weights it ~10⁴
above the shortest line, the solve answers with c ≈ 51 Å, and the N_c gate kills
the call.  Measured: **0 convergences in 4000 random starts**, against 3293 with
that one line removed.  Coelho's own impurity test (Table 6) places impurity
d-spacings between the smallest observed d and 1.5× the largest, so it never
reaches this case.  The fallback is :data:`TRIM_RETRY` and it is a *retry*, not a
default, because a budgeted trim rescues corundum and costs every other dataset
(zircon 58 → 1 hits per 3000 starts, zincite 317 → 205, bethanechol F 1 → 0).

## What §2.3's zero-error column turned out to be for (WP-1040 task 3)

**5. It does not make the search converge more often; it makes a converged
answer correct.**  This is the opposite of what the WP expected of it, and both
halves are measured.  On the ten published bethanechol sets the per-trial hit
rate does not move at all under any pass strategy.  Started **at** the truth on a
synthetic monoclinic with a zero error injected, a single pass returns a lattice
**3.5 % from the truth** at Ze = 0.10° — a miss by every equality test in the
package, because a search that cannot model the shift absorbs it into the axes —
and :func:`svd_trial`'s three passes return it to **1e-4** while reporting the
shift to 1 % (0.0989 for 0.100, 0.0497 for 0.050, −0.0807 for −0.080).  With a
realistic 0.005° of scatter on the positions the recovered lattice sits at
0.0044 **independently of the injected shift**, which is the residual of the
scatter and not of the shift.  End to end that bought one dataset and cost none:
qarr corundum goes from **0 candidates to 1** — the truth, ranked first, 3e-4
from the certificate — while zincite and zircon return the same cells at the
same ranks, for up to 2× the wall clock (2.0 → 2.8 s, 4.2 → 4.4 s, 3.5 → 7.2 s).

**6. The zero error it fits is a third independent road to WP-1038's number,
and it agrees to 0.003°.**  Where both speak, on the two datasets whose shift the
reflection-pair screen detects:

===============  ==================  ==================  ==========
dataset          pairs (``constant``)  against reference  SVD Ze
===============  ==================  ==================  ==========
SRM 660c LaB6    +0.0359             +0.0367             **+0.0329**
qarr corundum    −0.0670             −0.0650             **−0.0666**
===============  ==================  ==================  ==========

The three see different things — the pair screen sees only harmonic pairs among
the observed lines, the reference-based fit sees certified positions, and this
column sees only a candidate lattice — so the agreement is evidence about the
*shift*, not about any one method.  It also reaches where the pair screen
declines: a bare 20-line list supplies too few pairs to concentrate (WP-1038),
and this column needs none.

**7. The bethanechol A-D sets are not blocked by their zeroshift.**  Closest
approach to the true lattice over 1500 random starts, in ``equal_reduced``'s own
relative units where 0.005 is a hit: **six of the ten sets never get inside
0.21-0.33** under any pass strategy, so nothing about the shift was ever going to
reach them.  The failure on A-D is not the shift — half of those sets barely have
one, since the paper's blanket −0.100° correction is right for PDF 43-1748 and
wrong for 46-1964 — it is that the *a* entries carry **7 impurity lines in 20**,
past the 33 % Coelho's own N_c/N_o gate says it tolerates (§2) and past anything
his Table 6 tests.  The WP predicted this column would unlock A-D.  It does not,
and a prediction is not a measurement even when the paper is on its side.

Of the four sets that *are* reached, three improve — Bb 0.122 → 0.007, E 0.017 →
0.005, Db 0.011 → 0.007 — and **the fourth gets worse**: set F, the synchrotron
measurement with the most precise positions and essentially no shift, goes 0.0009
→ 0.004, which is what a free column costs when there is nothing for it to
absorb.  It does not survive into the answer, because :func:`_keep` re-fits every
converged metric on 1/σ(Q) before anything is reported — but it is the reason
this module does not claim the strategy is free.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import PeakList
from .engines import (
    SYSTEM_ORDER,
    Budget,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    assign_lines,
    dedup_candidates,
    effective_shift_allowance,
    incomplete_diagnostic,
    indexes_the_search_lines,
    provisional_payload,
    rank_candidates,
    refine_with_shift,
    reflection_ceiling_ok,
    register_engine,
    search_line_order,
    search_volume_ceiling,
    shift_allowance_diagnostic,
    solution_key,
)
from .fom import LINE_COINCIDENCE_RTOL
from .priors import prior_seed_afs
from .qspace import (
    af_from_cell,
    cell_from_af,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
    trial_hkl,
)

#: Iterations of Table 1 step (iv) before a call gives up.  Coelho's N_T1 = 20,
#: and it is generous: the corpus converges in 3-9, and his §2.4 reports ~5 for
#: the first pass and ~1 for the second and third.
MAX_ITERATIONS = 20
#: Table 1 step (ii): the ratio of calculated to observed lines outside which a
#: trial is abandoned.  Coelho's own reading of what it costs — *"this condition
#: may cause failure if more than 75 % of the observed d-spacings are missing or
#: if more than 33 % of the observed d-spacings are impurity lines"*.
NC_NO_LO, NC_NO_HI = 1.0 / 3.0, 4.0
#: ν₁ of Coelho eq. (3) — the factor the volume ladder grows by per rung.
VOLUME_LADDER_RATIO = 1.1
#: Coelho Table 3 (captioned "Table 2" in the scan): (N₁, N₂) per crystal system.
#: N₁ random starts per volume rung, then N₂ − 1 further rounds perturbing the
#: best.  The small values at high symmetry are not a shortcut — a cubic metric
#: has one free parameter and a triclinic one has six.
CONTROL: dict[str, tuple[int, int]] = {
    "cubic": (1, 1),
    "hexagonal": (10, 2),
    "trigonal": (10, 2),
    "tetragonal": (10, 2),
    "orthorhombic": (200, 2),
    "monoclinic": (200, 2),
    "triclinic": (200, 3),
}
#: Exponent m of the weighting function W = d_o^m·|Δ2θ|·I_o (Coelho eq. 4).
#:
#: **Four, fixed, and the paper disagrees with itself about the range it should
#: be randomised over.**  §2.2 says *"randomizing m between 0 and 4 produces
#: better results"*; the experiment that produced that claim, in §3.1, says the m
#: values *"were randomly varied between 0 and 6"*.  Both are quotations, so
#: neither reading of the WP's context section is a misreading — there are two
#: sentences and they do not agree, and only the second is attached to a number.
#: The "4.4 → 8.4 → 11.8 % decomposition" is likewise not one experiment: 4.4 % is
#: §3.1's triclinic Δ = 0.3 single-call perturbation rate, while 8.4 and 11.8 are
#: single-pass Table 2 runs later in the same section.  Measured here on the
#: corpus, randomising m is not free either way — it helps LaB6 at large Δ and
#: hurts NAC (100 % → 51-67 % at every Δ) — so the fixed optimum is kept and the
#: randomisation is recorded as unreproduced rather than adopted on the paper's
#: word.
WEIGHT_EXPONENT = 4.0
#: Lines dropped, at most, when a search that found nothing is retried.  See rule
#: 4 in the module docstring: this rescues one corpus dataset and costs every
#: other, so it runs only after silence, the same posture as ``trial_error``'s
#: dominant-zone probe.
TRIM_RETRY = 1
#: Largest |h| the per-iteration enumeration will build a box for.  A crash guard
#: in the same family as ``engines.reflection_ceiling_ok`` and needed for the same
#: reason: the loop re-enumerates from the *current* trial metric, and a metric
#: that has run away asks for a box that will not fit in memory.
MAX_BOX_INDEX = 40
#: Random starts the κ probe averages over, and the reference volume it uses.
#: Twenty-four is enough for a median that moves the window's endpoints by under a
#: per cent, and the window is a factor of twelve wide.
KAPPA_PROBES, KAPPA_VOLUME = 24, 500.0
#: Angle range random triclinic and monoclinic starts are drawn from — Coelho §3's
#: own test-lattice generation (90-130°).
ANGLE_LO, ANGLE_HI = 90.0, 130.0
#: Coelho §2.4: in the **last** pass only, an observed line whose nearest
#: calculated line is further than this is left unindexed rather than fitted.
#: Read it as a search device and not as a precision — it is the one number in
#: this module that resembles a tolerance, and it is applied only once the metric
#: is already roughly right (module docstring, rule 3, and rule 5 below).
IMPURITY_CUT_DEG = 0.05
#: Largest |Ze| (° 2θ) a pass will carry forward.  Coelho's own reason for
#: running a zero-error-free pass first is that *"the absolute value of Ze as
#: returned by SVD is often too large (>0.1° 2θ)"* on early, wrong assignments;
#: this bounds what survives a *later* pass for the same reason, since the column
#: is one free parameter that will happily absorb a wrong metric.  Set to twice
#: the ±0.05° the paper claims the strategy tolerates, so it can never refuse a
#: shift the method is supposed to handle.  Measured, it does not bind on either
#: bundled dataset that has a shift to find — SRM 660c +0.033°, qarr corundum
#: −0.067° — and the one place it would is the bethanechol `A` sets' +0.108°,
#: which are unreachable for an unrelated reason (module docstring, rule 7).
ZERO_ERROR_LIMIT_DEG = 0.10


@lru_cache(maxsize=32)
def _hkl_box(max_index: int, centring: str) -> np.ndarray:
    """``trial_hkl`` memoised: the loop re-enumerates once per iteration and the
    box usually does not change between them."""
    hkl = trial_hkl(max_index, centring)
    hkl.setflags(write=False)
    return hkl


def _predicted(af: np.ndarray, basis: np.ndarray, centring: str, q_max: float):
    """Distinct calculated ``(Q, hkl)`` inside the observed sphere.

    The box is sized from the *current* metric — ``hmax = floor(a·√Q_max) + 1``
    per axis, the arithmetic ``engines.predicted_reflection_count`` guards — so
    the enumeration tracks the trial cell rather than covering the whole domain.

    Merged to distinct **lines** at :data:`~rietx.indexing.fom.LINE_COINCIDENCE_RTOL`,
    which is what makes ``len(q)`` the N_c the gate wants (module docstring, rule 2).
    """
    try:
        cell = cell_from_af(af)
    except ValueError:
        return np.zeros(0), np.zeros((0, 3), dtype=np.int64)
    hmax = int(np.floor(max(cell[:3]) * np.sqrt(max(q_max, 1e-12)))) + 1
    if hmax > MAX_BOX_INDEX:
        return np.zeros(0), np.zeros((0, 3), dtype=np.int64)
    hkl = _hkl_box(hmax, centring)
    q = design_matrix(hkl) @ np.asarray(af, dtype=np.float64)
    inside = (q > 0.0) & (q <= q_max)
    q, hkl = q[inside], hkl[inside]
    if not len(q):
        return q, hkl
    order = np.argsort(q)
    q, hkl = q[order], hkl[order]
    keep = np.ones(len(q), dtype=bool)
    keep[1:] = np.diff(q) > LINE_COINCIDENCE_RTOL * np.maximum(q[1:], 1e-300)
    return q[keep], hkl[keep]


def _nearest_assignment(q_obs: np.ndarray, intensity: np.ndarray,
                        q_cal: np.ndarray) -> np.ndarray:
    """Table 1 step (iii): each observed line takes its nearest calculated one.

    Returns an index into ``q_cal`` per observed line, ``-1`` where the line is
    left un-indexed.  **There is no tolerance window here at all** — that is the
    whole of Coelho's "does not require errors in the input d-spacings as input",
    and it is why this engine's silence means something different from
    dichotomy's.

    A calculated line claimed by more than one observed keeps the observed with
    the smallest 1/(d_o²·I_o), i.e. the largest I_o/Q_o; the rest are un-indexed,
    which is *"the key factor in determining impurity lines"* (§2).  This is also
    the only place in any of the three engines where an observed **intensity**
    changes what the search does.
    """
    if not len(q_cal):
        return np.full(len(q_obs), -1, dtype=np.int64)
    pos = np.searchsorted(q_cal, q_obs)
    lo = np.clip(pos - 1, 0, len(q_cal) - 1)
    hi = np.clip(pos, 0, len(q_cal) - 1)
    nearest = np.where(np.abs(q_cal[hi] - q_obs) < np.abs(q_cal[lo] - q_obs),
                       hi, lo)
    out = np.full(len(q_obs), -1, dtype=np.int64)
    claimed: set[int] = set()
    for i in np.argsort(-intensity / np.maximum(q_obs, 1e-300)):
        c = int(nearest[i])
        if c not in claimed:
            claimed.add(c)
            out[i] = c
    return out


@dataclass(frozen=True)
class SvdPass:
    """What one call to Coelho's Table 1 returned.

    ``ze`` is the fitted zero error in **degrees 2θ**, signed as eq. (6) signs it:
    the observed angle is the true one *plus* ``ze``, so a correction subtracts
    it.  It is 0.0 exactly whenever the pass carried no zero-error column, which
    is not the same claim as "the zero error was measured to be zero" —
    :func:`svd_trial` records which passes fitted one.
    """

    af: np.ndarray
    converged: bool
    iterations: int
    why: str
    ze: float = 0.0


def zero_error_column(two_theta: np.ndarray, wavelength: float) -> np.ndarray:
    """Coelho eq. (6)'s design column: ∂Q/∂Ze for a **constant** 2θ zero error.

    From ``1/d_o² = sin²(θ + Ze·π/360)·4/λ²`` expanded to first order,

        Q_obs = Q_lattice + Ze·(π/360)·(4/λ²)·sin(2θ)

    so a constant shift in 2θ enters Q *through* ``sin 2θ``.  **This is not the
    package's** ``sin_2theta`` **template** — that one is a shift proportional to
    sin 2θ in 2θ space (specimen transparency), and it is the ``constant``
    template whose Q-space signature this is.  The two get conflated because the
    same three letters appear in both; the discriminator is which space the
    sin 2θ lives in.

    Equivalent, to first order, to differentiating ``q_of_two_theta``: that
    derivative is ``(π/90)·sin(2θ)/λ²`` per degree of 2θ, and ``π/90 = 2·π/180``
    against this column's ``4·π/360 = π/90``.  They are the same number, and the
    check is worth stating because ``refine_candidate`` carries the note about
    π/90 versus π/180 for the same reason.
    """
    return ((np.pi / 360.0) * (4.0 / wavelength ** 2)
            * np.sin(np.radians(np.asarray(two_theta, dtype=np.float64))))


def svd_iterate(af0: np.ndarray, q_obs: np.ndarray, two_theta: np.ndarray,
                intensity: np.ndarray, basis: np.ndarray, centring: str,
                wavelength: float, *, m: float = WEIGHT_EXPONENT,
                sigma: np.ndarray | None = None, trim: int = 0,
                max_iterations: int = MAX_ITERATIONS,
                zero_error: bool = False, ze0: float = 0.0,
                weight: str = "eq4", cut_deg: float | None = None,
                ) -> SvdPass:
    """One call to Coelho's Table 1.

    The weighting is eq. (4), ``W = d_o^m·|Δ2θ|·I_o``, applied to both sides of the
    quadratic form.  Note that it deliberately weights the *worst-fitting* lines
    **up**: §2.2's argument is that a large discrepancy is where the information
    about how to move is, and the paper measures the choice rather than asserting
    it (per-trial success 4.4 → 11.8 % on triclinic simulations).  It is the
    opposite of a least-squares weight, which is why the fitted cell this returns
    is a *starting point* and never the answer — ``search_svd`` re-fits every
    survivor through :func:`~rietx.indexing.qspace.refine_candidate`, on 1/σ(Q),
    to get a cell and a covariance anyone may quote.

    **Convergence is tested against every assignment seen, not only the previous
    one.**  Coelho's step (iv) says "the same as in the previous iteration", which
    a 2-cycle never satisfies — measured on four of the nine corpus datasets,
    where the loop reached the true metric and then burned all twenty iterations
    alternating between two assignments before reporting failure.

    **The three optional arguments are the three ways §2.3 and §2.4's later
    passes differ from this one**, and none of them is on by default because a
    first pass must have all three off (:func:`svd_trial` is the strategy):

    ``zero_error``
        append :func:`zero_error_column` to the design and solve for Ze with the
        metric.  The assignment step then works on ``Q_obs − Ze·col`` — the
        *corrected* observed lines — while the fit stays on the uncorrected ones
        with the column, which is eq. (7) as printed.
    ``weight="d2"``
        Coelho §2.4's ``W = d_o²``, i.e. all lines weighted alike in Q.  Eq. (4)
        deliberately over-weights the worst-fitting lines to *search*; once the
        assignment is right that bias is a bias, and this is the pass that
        removes it.
    ``cut_deg``
        leave unindexed any observed line whose nearest calculated line is
        further than this in 2θ.  Coelho's impurity cut, and the module
        docstring's rule 3 is that it belongs here and nowhere earlier.
    """
    af = np.asarray(af0, dtype=np.float64).copy()
    n_o = len(q_obs)
    n_free = basis.shape[0]
    seen: set[bytes] = set()
    col = (zero_error_column(two_theta, wavelength) if zero_error
           else np.zeros_like(q_obs))
    ze = float(ze0)
    for it in range(1, max_iterations + 1):
        # the assignment always sees the *corrected* observed lines; the fit
        # below always sees the uncorrected ones plus the column
        q_corr = q_obs - ze * col
        q_cal, hkl_cal = _predicted(af, basis, centring, float(q_corr.max()))
        if not (NC_NO_LO <= len(q_cal) / n_o <= NC_NO_HI):
            return SvdPass(af, False, it, "gate", ze)
        assign = _nearest_assignment(q_corr, intensity, q_cal)
        idx = np.flatnonzero(assign >= 0)
        if trim > 0 and len(idx) - trim >= n_free + 1:
            dq = np.abs(q_corr[idx] - q_cal[assign[idx]])
            scale = (np.asarray(sigma)[idx] if sigma is not None
                     else np.maximum(q_corr[idx], 1e-300))
            idx = idx[np.argsort(dq / np.maximum(scale, 1e-300))][:len(idx) - trim]
        if len(idx) < n_free + 1:
            return SvdPass(af, False, it, "too-few-indexed", ze)

        tt_cal = np.degrees(2.0 * np.arcsin(np.clip(
            wavelength * np.sqrt(np.maximum(q_cal[assign[idx]], 0.0)) / 2.0,
            -1.0, 1.0)))
        dtt = np.abs(two_theta[idx] - ze - tt_cal)
        if cut_deg is not None:
            near = dtt <= cut_deg
            if int(np.count_nonzero(near)) >= n_free + 1:
                idx, tt_cal, dtt = idx[near], tt_cal[near], dtt[near]

        hkl = hkl_cal[assign[idx]]
        key = hkl.tobytes() + idx.tobytes()
        if key in seen:
            return SvdPass(af, True, it, "converged", ze)
        seen.add(key)

        q_i = q_obs[idx]
        rows = design_matrix(hkl) @ basis.T
        if zero_error:
            rows = np.column_stack([rows, col[idx]])
        d_o = 1.0 / np.sqrt(np.maximum(q_corr[idx], 1e-300))
        if weight == "d2":
            w = d_o ** 2
        else:
            # |Δ2θ| = 0 would delete the row rather than merely stop it pulling,
            # and deleting a row changes the *rank* of the system, which is a
            # different claim about what the lines determine.  Floored well below
            # the smallest real discrepancy instead.
            floor = (float(dtt[dtt > 0.0].min()) * 1e-3 if np.any(dtt > 0.0)
                     else 1e-9)
            w = d_o ** m * np.maximum(dtt, floor) * intensity[idx]
        w = np.where(np.isfinite(w) & (w > 0.0), w, 0.0)
        if not np.any(w > 0.0):
            return SvdPass(af, False, it, "degenerate-weights", ze)
        try:
            theta, *_ = np.linalg.lstsq(rows * w[:, None], q_i * w, rcond=None)
        except np.linalg.LinAlgError:
            return SvdPass(af, False, it, "lstsq-failed", ze)
        if zero_error:
            ze_new = float(theta[-1])
            # Coelho runs a zero-error-free pass first because SVD returns
            # |Ze| > 0.1° on early wrong assignments.  A later pass can still ask
            # for one, so it is bounded rather than trusted.
            if not np.isfinite(ze_new):
                return SvdPass(af, False, it, "non-finite", ze)
            ze = float(np.clip(ze_new, -ZERO_ERROR_LIMIT_DEG,
                               ZERO_ERROR_LIMIT_DEG))
            theta = theta[:-1]
        af_new = basis.T @ theta
        if not np.all(np.isfinite(af_new)):
            return SvdPass(af, False, it, "non-finite", ze)
        af = af_new
    return SvdPass(af, False, max_iterations, "max-iterations", ze)


def svd_trial(af0: np.ndarray, q_obs: np.ndarray, two_theta: np.ndarray,
              intensity: np.ndarray, basis: np.ndarray, centring: str,
              wavelength: float, *, m: float = WEIGHT_EXPONENT,
              sigma: np.ndarray | None = None, trim: int = 0,
              zero_error: bool = True,
              cut_deg: float | None = IMPURITY_CUT_DEG) -> SvdPass:
    """§2.4's *final* algorithm: Table 1 three times from one random start.

    Coelho: *"The first call is made with the weighting function of equation (4)
    and no zero error, the second is made with the weighting function of equation
    (4) and a zero error included, and the third is made with a zero error
    included but with the weighting function W = d_o²"*, with the impurity cut in
    the third only.  He measures ~5 iterations for the first pass and ~1 for each
    of the others, so the strategy costs well under twice one pass.

    Each pass starts from the previous pass's metric, which is the entire point:
    *"Immediate assignment of this weighting … reduces the chances of getting
    close to the correct solution"* — the same sentence, structurally, as the one
    about Ze being too large on early assignments.  Both later refinements are
    things you may only do **once the assignment is roughly right**, and pass 1
    is what makes it so.

    A pass that dies on the N_c gate ends the trial: its metric is not a starting
    point for anything.  A pass that merely runs out of iterations is carried
    forward, because its metric is still the best estimate available.
    """
    first = svd_iterate(af0, q_obs, two_theta, intensity, basis, centring,
                        wavelength, m=m, sigma=sigma, trim=trim)
    if not (zero_error or cut_deg is not None):
        return first
    if first.why in ("gate", "too-few-indexed", "degenerate-weights",
                     "lstsq-failed", "non-finite"):
        return first
    second = svd_iterate(first.af, q_obs, two_theta, intensity, basis, centring,
                         wavelength, m=m, sigma=sigma, trim=trim,
                         zero_error=zero_error)
    if second.why in ("gate", "too-few-indexed", "degenerate-weights",
                      "lstsq-failed", "non-finite"):
        return SvdPass(first.af, first.converged, first.iterations, first.why,
                       0.0)
    third = svd_iterate(second.af, q_obs, two_theta, intensity, basis, centring,
                        wavelength, sigma=sigma, trim=trim,
                        zero_error=zero_error, ze0=second.ze, weight="d2",
                        cut_deg=cut_deg)
    if third.why in ("gate", "too-few-indexed", "degenerate-weights",
                     "lstsq-failed", "non-finite"):
        return second
    return SvdPass(third.af, third.converged,
                   first.iterations + second.iterations + third.iterations,
                   third.why, third.ze)


# ----------------------------------------------------------------------
# The gate, read as a volume window
# ----------------------------------------------------------------------
def _random_af(system: str, rng, d_lo: float, d_hi: float) -> np.ndarray:
    """(A..F) of a random conventional cell of ``system`` with axes in range."""
    a, b, c = rng.uniform(d_lo, d_hi, size=3)
    if system == "cubic":
        cell = (a, a, a, 90.0, 90.0, 90.0)
    elif system == "tetragonal":
        cell = (a, a, c, 90.0, 90.0, 90.0)
    elif system in ("hexagonal", "trigonal"):
        cell = (a, a, c, 90.0, 90.0, 120.0)
    elif system == "orthorhombic":
        cell = (a, b, c, 90.0, 90.0, 90.0)
    elif system == "monoclinic":
        cell = (a, b, c, 90.0, float(rng.uniform(ANGLE_LO, ANGLE_HI)), 90.0)
    else:
        ang = rng.uniform(ANGLE_LO, ANGLE_HI, size=3)
        cell = (a, b, c, float(ang[0]), float(ang[1]), float(ang[2]))
    return af_from_cell(cell)


def _project(af: np.ndarray, basis: np.ndarray) -> np.ndarray:
    return basis.T @ np.linalg.lstsq(basis.T, af, rcond=None)[0]


def scale_to_volume(af: np.ndarray, volume: float) -> np.ndarray:
    """Scale (A..F) so the real-space cell volume is ``volume`` — Table 2 step (i).

    ``V ∝ det(G*)^(-1/2)`` and det scales as s³ under ``A..F → s·(A..F)``, so
    ``V → V·s^(-3/2)``.
    """
    from ..crystallography.lattice import cell_volume
    try:
        v0 = float(cell_volume(*cell_from_af(af)))
    except ValueError:
        return af
    if not np.isfinite(v0) or v0 <= 0.0 or volume <= 0.0:
        return af
    return af * (v0 / volume) ** (2.0 / 3.0)


def volume_window(n_observed: int, system: str, centring: str, q_max: float,
                  seed: int = 0) -> tuple[float, float]:
    """The volume range Coelho's N_c/N_o gate admits, computed **before** the search.

    N_c is proportional to V at fixed Q_max, system and centring — one reciprocal
    lattice point per reciprocal-cell volume, divided by the multiplicity of the
    coincidences a symmetric lattice has — so a handful of probe cells measure
    κ = N_c/V and the gate becomes a bound on volume rather than a per-trial
    verdict:

        V ∈ [N_o/(3κ), 4·N_o/κ]

    always a factor of twelve, so the value is in *where* it sits, not how wide it
    is.  Measured on all nine of WP-1040's corpus datasets, it contains the true
    volume every time — and a ladder placed inside it rather than swept from an
    arbitrary floor is most of why this engine costs seconds (module docstring).

    Returns ``(0.0, inf)`` when no probe cell produced a usable prediction, so a
    caller's own bounds decide and the window never *excludes*: the one failure a
    search bound may not have is excluding the true cell (WP-1019's envelope).
    """
    basis = metric_basis(system)
    rng = np.random.default_rng(seed)
    kappas = []
    for _ in range(KAPPA_PROBES):
        af = _project(scale_to_volume(_random_af(system, rng, 2.0, 25.0),
                                      KAPPA_VOLUME), basis)
        q_cal, _hkl = _predicted(af, basis, centring, q_max)
        if len(q_cal):
            kappas.append(len(q_cal) / KAPPA_VOLUME)
    if not kappas:
        return 0.0, float("inf")
    kappa = float(np.median(kappas))
    if kappa <= 0.0:
        return 0.0, float("inf")
    return (n_observed * NC_NO_LO / kappa, n_observed * NC_NO_HI / kappa)


# ----------------------------------------------------------------------
# The engine
# ----------------------------------------------------------------------
def search_svd(peaks: PeakList, *, spec: SearchSpec | None = None,
               quality=None, cancel=None, progress=None) -> EngineResult:
    """Propose metrics at random over a volume ladder; iterate each to a fixed
    assignment; keep what explains the driven lines.

    **Stochastic, and the seed is part of the answer.**  ``SearchSpec.seed`` is
    recorded in the result's stats, so a run is reproducible from what it reports
    — the one thing the other two engines, which are deterministic, never had to
    say.  Coelho's own note applies and is worth passing on: *"the Monte Carlo
    nature of Table 2 implies different results every time SVD-Index is run"*, so
    running it again searches more of the space rather than repeating itself.
    """
    spec = spec or SearchSpec()
    q_all = peaks.q()
    tt_all = peaks.two_theta()
    allowance, assumed = effective_shift_allowance(spec, quality)
    sigma = sigma_effective(peaks.q_esd(), tt_all, peaks.wavelength, allowance)
    inten = peaks.intensity()
    tt_max = float(peaks.two_theta_max)

    result = EngineResult(engine="svd")
    if len(q_all) < 2:
        result.diagnostics.append(Diagnostic(
            level="error", code="INDEX_DATA_INSUFFICIENT",
            message="a lattice cannot be constrained by fewer than two lines",
            where=[f"{len(q_all)} usable lines"],
            suggestion="run assess_peak_list before searching"))
        return result

    search_lines = search_line_order(peaks, spec)
    systems = [s for s in SYSTEM_ORDER if s in spec.systems]
    raw: list[EngineCandidate] = []
    incomplete: list[str] = []
    capped: list[str] = []

    for system in systems:
        # not started ⇒ not claimed — the rule both other engines follow, and what
        # keeps "not reached" distinct from "truncated" (WP-1037)
        if cancel is not None and bool(cancel):
            break
        result.systems_searched += (system,)
        if progress is not None:
            progress.start(f"svd:{system}", engine="svd", system=system)
        budget = Budget(spec.budget_seconds, cancel)
        found, stats, complete = _search_system(
            peaks, system, spec, budget, q_all, sigma, tt_all, inten, tt_max,
            search_lines, quality)
        if not found and not budget.expired():
            # The retry that explains a silence, and it pays for itself only when
            # there is a silence to explain (module docstring, rule 4).  It shares
            # the system's **existing** budget rather than taking a fresh one: a
            # second Budget here would make the engine cost 2·budget_seconds per
            # system and quietly falsify ``engines.estimate_ceiling``, whose whole
            # claim is that the per-system budgets are hard ceilings the engines
            # enforce.  So the retry runs on what the search left over, and gets
            # nothing when the search used it all — which is the right answer.
            more, more_stats, _c = _search_system(
                peaks, system, spec, budget, q_all,
                sigma, tt_all, inten, tt_max, search_lines, quality,
                trim=TRIM_RETRY)
            found = more
            for key, value in more_stats.items():
                stats[f"trim.{key}"] = value
        raw.extend(found)
        result.search_complete[system] = complete
        for key, value in stats.items():
            result.stats[f"{system}.{key}"] = value
        if not complete:
            # a unit its budget did not stop hit a size cap, where more
            # time changes nothing (``incomplete_diagnostic``)
            (incomplete if budget.expired() else capped).append(system)
        if progress is not None:
            progress.end(f"svd:{system}", engine="svd", system=system,
                         n_candidates=len(found), complete=complete,
                         provisional=provisional_payload(found))

    # the hand-off pool, not the reported cap — see ``SearchSpec.engine_pool``
    result.candidates = rank_candidates(raw, peaks, k_sigma=spec.k_sigma,
                                        n_unindexed=spec.n_unindexed,
                                        max_candidates=spec.engine_pool(),
                                        q_match=sigma)
    result.stats["candidates.raw"] = float(len(raw))
    if len(result.candidates) >= spec.engine_pool():
        for system in result.systems_searched:
            result.stats[f"{system}.pool_capped"] = 1.0
    result.stats["shift_allowance_deg"] = round(allowance, 5)
    result.stats["seed"] = float(spec.seed)
    if assumed:
        result.diagnostics.append(shift_allowance_diagnostic(allowance))
    if incomplete or capped:
        result.diagnostics.append(
            incomplete_diagnostic("svd", incomplete, spec.budget_seconds,
                                  capped))
    return result


def _search_system(peaks: PeakList, system: str, spec: SearchSpec,
                   budget: Budget, q_all: np.ndarray, sigma: np.ndarray,
                   tt_all: np.ndarray, inten: np.ndarray, tt_max: float,
                   search_lines: np.ndarray, quality, *, trim: int = 0):
    """Coelho's Table 2 over one crystal system: the volume ladder.

    ``search_complete`` is **False whenever the ladder was not walked to its
    end** — by the budget or by the caller's token.  A stochastic engine's
    silence is weaker evidence than an exhaustive one's even when it *did*
    finish, so this flag is the floor of what may be claimed, not the ceiling:
    consensus reads it, and ``EngineResult.complete`` is what stops an absence
    being read as "no such cell".
    """
    basis = metric_basis(system)
    n1, n2 = CONTROL.get(system, (200, 2))
    q_search = q_all[search_lines]
    tt_search = tt_all[search_lines]
    i_search = inten[search_lines]
    sig_search = sigma[search_lines]
    q_max = float(q_search.max())

    # **Not** ``hash(system)``: python salts string hashes per process, so a run
    # seeded from ``SearchSpec.seed`` would still not reproduce — which is the one
    # promise a stochastic engine has to keep.  The system's position in
    # ``SYSTEM_ORDER`` is a stable integer and decorrelates the systems' streams.
    rng = np.random.default_rng(
        (int(spec.seed), SYSTEM_ORDER.index(system), int(trim)))
    vol_ceiling = search_volume_ceiling(spec, quality, system)
    found: list[EngineCandidate] = []
    seen: set[tuple[int, ...]] = set()
    zes: list[float] = []
    calls = 0
    complete = True

    # analogue priors seed the starting basin (WP-1045): each prior metric of
    # this system is one deliberate Table-1 start per centring, run BEFORE the
    # random ladder and outside the N_c/N_o volume gate — that gate is a
    # statistic about random starts, and a stated cell is not a random start.
    # The caller's own box still binds: ``_keep`` holds a seeded candidate to
    # the same ``vol_max`` and the same acceptance bar as every other one, so
    # a prior can spend calls, never widen what is searchable.
    prior_afs = prior_seed_afs(spec, system)

    for centring in spec.centrings_for(system):
        for af_p in prior_afs:
            if budget.expired():
                return found, _stats(calls, budget, zes), False
            out = svd_trial(_project(af_p, basis), q_search, tt_search,
                            i_search, basis, centring, peaks.wavelength,
                            sigma=sig_search, trim=trim)
            calls += 1
            if out.converged and _keep(
                    out.af, basis, system, centring, spec, peaks, q_all,
                    sigma, tt_all, tt_max, search_lines, seen, found,
                    vol_ceiling, ze=out.ze) > -np.inf:
                zes.append(out.ze)
        # The N_c/N_o window gates the **random ladder** and no part of a
        # prior's trial, so it is measured after them.  Its κ probes cost a
        # couple of ms, and ahead of the prior loop they were the one thing
        # that could spend a small budget before the caller's own stated cell
        # got its single deliberate call — 63 ms of them against a 50 ms
        # budget on a 4×-oversubscribed machine (WP-1128).  Pure reordering:
        # ``volume_window`` draws from its own ``default_rng(seed)``, so
        # neither ``rng``'s stream nor any accepted value moves.
        gate_lo, gate_hi = volume_window(len(q_search), system, centring, q_max,
                                         seed=spec.seed)
        v_lo = max(spec.min_volume, gate_lo)
        v_hi = min(vol_ceiling, gate_hi)
        if not (v_lo < v_hi):
            continue
        v1 = v_lo
        best_af, best_score = None, -np.inf
        while v1 <= v_hi:
            if budget.expired():
                return found, _stats(calls, budget, zes), False
            for _ in range(n1):
                af0 = _project(scale_to_volume(
                    _random_af(system, rng, spec.min_d_axis, spec.max_d_axis),
                    v1), basis)
                out = svd_trial(af0, q_search, tt_search, i_search, basis,
                                centring, peaks.wavelength, sigma=sig_search,
                                trim=trim)
                calls += 1
                if not out.converged:
                    continue
                score = _keep(out.af, basis, system, centring, spec, peaks,
                              q_all, sigma, tt_all, tt_max, search_lines, seen,
                              found, v_hi, ze=out.ze)
                if score > -np.inf:
                    zes.append(out.ze)
                if score > best_score:
                    best_af, best_score = out.af, score
            for _ in range(n2 - 1):
                if best_af is None or budget.expired():
                    break
                theta = np.linalg.lstsq(basis.T, best_af, rcond=None)[0]
                for k in range(n1):
                    # Coelho Table 2 step (ii): R uniform on
                    # [0.99 − 0.49·k/N₁, 1.5 + 0.49·k/N₁], widening as the round
                    # goes on.  Drawn **per free metric parameter** rather than
                    # per X_nn: scaling A..F independently leaves the crystal
                    # system's subspace, so a cubic A = B = C would not survive it.
                    lo = 0.99 - 0.49 * k / max(n1, 1)
                    hi = 1.50 + 0.49 * k / max(n1, 1)
                    af0 = basis.T @ (theta * rng.uniform(lo, hi,
                                                         size=theta.shape))
                    out = svd_trial(af0, q_search, tt_search, i_search, basis,
                                    centring, peaks.wavelength,
                                    sigma=sig_search, trim=trim)
                    calls += 1
                    if out.converged and _keep(
                            out.af, basis, system, centring, spec, peaks, q_all,
                            sigma, tt_all, tt_max, search_lines, seen, found,
                            v_hi, ze=out.ze) > -np.inf:
                        zes.append(out.ze)
            v1 *= VOLUME_LADDER_RATIO
        if len(found) > 2000:
            found = dedup_candidates(found)
    return found, _stats(calls, budget, zes), complete


def _stats(calls: int, budget: Budget, zes: list[float]) -> dict[str, float]:
    """What one (engine × system) search reports about itself.

    ``ze_deg`` is the median zero error the accepted candidates were *found*
    under, and it is reported rather than applied (see :func:`_keep`).  It is the
    only number in the package that measures a systematic 2θ shift with no
    reference positions and no harmonic pairs — WP-1038's screen is the other
    road to the same quantity and declines on short lists — so where both speak
    they are worth comparing, and where only this one does it is evidence a
    caller can act on by declaring a template.
    """
    out = {"calls": float(calls), "seconds": round(budget.elapsed, 3)}
    if zes:
        out["ze_deg"] = round(float(np.median(zes)), 5)
    return out


def _keep(af, basis, system, centring, spec, peaks, q_all, sigma, tt_all,
          tt_max, search_lines, seen, found, vol_max, ze: float = 0.0) -> float:
    """Re-fit a converged metric properly, then apply the shared acceptance bar.

    The SVD loop's own cell is fitted under eq. (4)'s deliberately perverse
    weighting, so it is never the cell reported: this re-assigns with the
    package's per-line window and re-fits on 1/σ(Q) through ``refine_candidate``,
    which is also what supplies the ``cov_af`` consensus dedup needs.  The bar
    afterwards is ``indexes_the_search_lines`` — the same absolute budget both
    other engines are held to, so three engines' candidates mean the same thing.

    **``ze`` centres the matching window; it never writes the reported cell.**
    A zero error fitted inside the search is measured, but measured *under an
    assumed attribution* — Coelho's column is the ``constant`` template and
    nothing in the data distinguishes it from ``cos_theta`` over a short range
    (WP-1038, ``template_collinearity``).  The package already has the rule for
    that case and it is ``effective_shift_allowance``'s: **a shift measured without an
    attribution sizes windows; only a template the caller declared corrects a
    cell.**  So the assignment runs in corrected space, where it belongs — the
    question "is this the same line" is asked of positions the shift has been
    taken out of — and the reported fit is on ``q_all``, under
    ``engines.refine_with_shift`` and the caller's own template, exactly as for
    the other two engines.  The measured value is reported instead, in
    ``EngineResult.stats``.
    """
    try:
        cell = cell_from_af(af)
    except ValueError:
        return -np.inf
    if not reflection_ceiling_ok(cell, peaks.wavelength, tt_max):
        return -np.inf
    # keyed on the centring as well as the metric, because ``seen`` spans the
    # whole centring loop — ``engines.solution_key`` carries both measurements
    key = solution_key(af, centring)
    if key in seen:
        return -np.inf
    seen.add(key)

    d_max = spec.max_d_axis
    q_hi = float(q_all.max() + spec.k_sigma * sigma.max())
    max_index = int(np.ceil(d_max * np.sqrt(max(q_hi, 1e-12)))) + 1
    hkl_full = trial_hkl(max_index, centring)
    dm_full = design_matrix(hkl_full)

    q_match = (q_all if ze == 0.0
               else q_all - ze * zero_error_column(tt_all, peaks.wavelength))
    # The loop settles the *assignment*, so it runs on ``q_match`` throughout —
    # refitting on ``q_all`` here would drag ``af`` back onto shift-absorbed axes
    # between iterations and re-ask the matching question against a metric the
    # corrected lines no longer agree with.  One fit on ``q_all`` afterwards is
    # what the caller is told about.
    line_index = assigned = None
    previous: bytes | None = None
    for _pass in range(3):
        line_index, assigned = assign_lines(q_match, sigma, hkl_full, af,
                                            k_sigma=spec.k_sigma, design=dm_full)
        if len(line_index) < basis.shape[0] + 1:
            return -np.inf
        stamp = line_index.tobytes()
        if stamp == previous:
            break
        previous = stamp
        try:
            af = refine_candidate(q_match[line_index], sigma[line_index],
                                  assigned, system=system).af
        except (ValueError, np.linalg.LinAlgError):
            return -np.inf
    try:
        fit = refine_candidate(q_all[line_index], sigma[line_index], assigned,
                               system=system)
    except (ValueError, np.linalg.LinAlgError):
        return -np.inf
    if fit.chi2_red > spec.k_sigma ** 2:
        return -np.inf
    if not indexes_the_search_lines(line_index, search_lines, spec.n_unindexed):
        return -np.inf
    fit = refine_with_shift(fit, spec, system, q_all, sigma, tt_all,
                            peaks.wavelength, line_index, assigned)
    if not (spec.min_volume <= fit.volume <= vol_max):
        return -np.inf
    found.append(EngineCandidate(
        fit=fit, system=system, centring=centring, engine="svd", hkl=assigned,
        line_index=line_index, n_lines=len(q_all)))
    return float(len(line_index)) - float(fit.chi2_red)


register_engine(
    "svd", search_svd,
    "proposes metrics at random over a volume ladder and iterates SVD until the "
    "hkl assignment stops changing; needs no tolerance to search with, and is "
    "stochastic, so its failure mode is a bad starting basin rather than a wide "
    "domain or a bad base line")

__all__ = ["CONTROL", "IMPURITY_CUT_DEG", "MAX_ITERATIONS", "NC_NO_HI",
           "NC_NO_LO", "TRIM_RETRY", "VOLUME_LADDER_RATIO", "WEIGHT_EXPONENT",
           "ZERO_ERROR_LIMIT_DEG", "SvdPass", "scale_to_volume", "search_svd",
           "svd_iterate", "svd_trial", "volume_window", "zero_error_column"]
