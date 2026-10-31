"""Consensus between engines, and the confidence gate.

**Agreement is the confidence.**  Two engines that share only the tolerance model
and the form of Q are genuinely independent *searches* — ``search_dichotomy``
bounds Q over boxes and its failure mode is a domain too wide,
``search_trial_error`` assumes the indices of a few base lines and solves exactly
and its failure mode is a bad base line — so a lattice both of them reach is
evidence in a way no single figure of merit is.  The device is
``sequential.py``'s ``direction="both"`` and ``tests/test_cross_backend.py``'s
per-column agreement matrix, one rank up.

**Two engines is the ceiling, and that is a result rather than a shortfall.**
WP-1023's whole-profile Monte Carlo is a measured no-go: its tier-2 re-scoring is
affordable (13-15 ms per state) and discriminating (Rwp 1.29 for the certified
cell against 7.25 for one 1 % off), but tier-1 **cannot rank** — on the certified
qarr corundum pattern the true cell scores exactly 0.0000 and ranks 29 053 of
200 001, because the pattern's 0.060° cos θ displacement is 11σ of the fitted
per-line σ; widening the window puts the truth at rank 4 and simultaneously lets
coincidence-rich large cells outscore it.  So a Le Bail *re-scorer* is worth
having as validation (:mod:`rietx.indexing.workflow`, which owns it) and
``found_by`` must never contain one: a re-scorer is not an independent opinion,
it is the same opinion measured again.

**The gate's shape.**  ``high`` requires *no* caveats at all, and
:data:`~rietx.schemas.indexing.INDEX_REFUTING_CAVEATS` splits the rest in two:
a refuting caveat is positive evidence against the cell (or evidence that the
data cannot choose between it and another) and drops it to ``low``; the others cap
it at ``medium``.  Everything else with at least two engines behind it is
``medium``.

One consequence is worth stating rather than discovering: **on real data with no
measured systematic shift, ``high`` is currently unreachable, by design.** Both
engines widen their matching window by an *assumed*
``DEFAULT_UNKNOWN_SHIFT_DEG`` when no shift has been measured, which raises
``shift_allowance_assumed`` — and a cell found inside a widened window absorbs the
shift (measured, +1400 ppm on a certified pattern).  Declaring a calibrated
``shift_allowance_deg``, or handing ``assess_peak_list`` reference positions from an
internal standard, is what makes the caveat go away.  That is the same posture as
Layer 1's abstention: the ceiling moves when the evidence arrives, not when the
constant is raised.  Closing it on real data is WP-1026.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    INDEX_MIN_INDEXED_FRACTION,
    INDEX_REFUTING_CAVEATS,
    BravaisOpinion,
    CellCandidate,
    Confidence,
    DataQualityReport,
    IndexCaveat,
    PeakList,
)
from .engines import (
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_MIN_VOLUME,
    MIN_AGREEMENT,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    absence_window,
    candidates_truncated_diagnostic,
    dedup_groups,
    match_window,
    rank_candidates,
    search_acceptance,
    search_line_order,
    to_cell_candidate,
)
from .fom import fom_panel_disagrees

# Re-exported from its WP-1045 home beside ``volume_envelope`` itself: the
# engines' search ceiling and this module's ``volume_unphysical`` flag apply
# the *same* slack, so a cell the search could reach is never flagged for
# having been reached — the flag fires only when a caller widened
# ``max_volume`` past the slack too.
from .quality import VOLUME_ENVELOPE_SLACK

#: Candidates that get the **expensive** per-candidate checks — geometrical
#: ambiguity (which enumerates 55 derivative lattices and predicts reflections for
#: each) and whole-pattern validation (a refinement, ~0.6 s measured).  Three, plus
#: every candidate an engine consensus could promote, so the cap never removes a
#: candidate the gate might otherwise call ``high``: see :func:`checked_indices`,
#: which is one rule read by both call sites so "which candidates were checked"
#: has exactly one answer.
CONSENSUS_CHECK_TOP = 3


@dataclass
class ConsensusOutcome:
    """Ranked candidates and the result-level facts the gate needs.

    Separate from :class:`~rietx.schemas.indexing.IndexingResult` because this
    is the *pre-validation* answer: :func:`consensus` stops before the validation
    fits so ``index_pattern`` can decide which candidates to spend a refinement
    on, and :func:`apply_gate` runs after.
    """

    candidates: list[CellCandidate] = field(default_factory=list)
    engines_run: list[str] = field(default_factory=list)
    systems_searched: list[str] = field(default_factory=list)
    search_complete: dict[str, bool] = field(default_factory=dict)
    engine_stats: dict[str, float] = field(default_factory=dict)
    #: candidates whose geometrical-ambiguity enumeration actually ran — the
    #: ``checked`` the gate must be given.  Identical to ``checked_indices``
    #: except under a fired token (WP-1037), where the enumeration is the
    #: measured long pole (12 × 3.75 s on the corundum run) and is skipped for
    #: the remaining candidates — which must then read "not enumerated"
    #: (a capping caveat), never "no ambiguity found"
    ambiguity_checked: list[int] = field(default_factory=list)
    fom_panel_disagrees: bool = False
    #: was any engine's tolerance widened by an *assumed* systematic?  Read from
    #: the engines' own ``INDEX_SHIFT_ALLOWANCE`` diagnostic rather than
    #: re-derived, so the gate and the message can never disagree
    shift_allowance_assumed: bool = False
    diagnostics: list[Diagnostic] = field(default_factory=list)


def merge_engine_candidates(results: Sequence[EngineResult],
                            ) -> list[EngineCandidate]:
    """Pool every engine's candidates and merge the ones that are one lattice.

    The kept member of each group carries ``found_by`` — every engine that
    reached that lattice — which is the raw material of the whole gate.  Note
    what is *not* merged: two centrings of the same metric stay separate, because
    they are two lattices predicting different numbers of lines and the panel
    exists to choose between them (``engines.dedup_groups``).
    """
    pool: list[EngineCandidate] = []
    for result in results:
        pool.extend(result.candidates)
    kept: list[EngineCandidate] = []
    for group in dedup_groups(pool):
        best = group[0]
        # sorted, not insertion-ordered: `found_by` is compared against
        # `engines_run` as a set, and a stable order makes the reported list
        # reproducible whatever order the engines happened to run in
        best.found_by = sorted({c.engine for c in group})
        kept.append(best)
    return kept


def bravais_opinion(cell: Sequence[float], centring: str,
                    cell_esd: Sequence[float] | float = 1e-3,
                    ) -> BravaisOpinion | None:
    """Run WP-1020's two-opinion Bravais screen and pack it for reporting.

    ``None`` when the screen raises — a metric so degenerate that gemmi or spglib
    refuses it is not a lattice symmetry statement, and inventing "triclinic"
    would be one.
    """
    from .reduce import bravais_screen

    try:
        screen = bravais_screen(tuple(cell), centring, cell_esd=cell_esd)
    except Exception:                       # noqa: BLE001 — third-party refusal
        return None
    return BravaisOpinion(
        system=screen.system, system_loosest=screen.system_loosest,
        system_gemmi=screen.system_gemmi, system_spglib=screen.system_spglib,
        ambiguous=screen.ambiguous, methods_disagree=screen.methods_disagree,
        reduced_cell=tuple(float(v) for v in screen.reduced.cell))


def supercell_checks(candidates: Sequence[CellCandidate], peaks: PeakList, *,
                     q_match: np.ndarray, k_sigma: float,
                     screen=None) -> None:
    """Ask each candidate as a child of every other, in place (WP-1449; C3).

    Fills ``supercell_checks`` on every candidate, ``[]`` where no other is a
    parent of it, one entry per parent in the parents' rank order otherwise.
    The relation is **containment of the indexed observed set** with the
    denser line set as the child (:func:`~rietx.indexing.screen.contains`),
    which reaches every pair the primitive-volume ratio of 2 to 4 reached and
    the ones it could not: cubic I √2·a₀ over cubic F a₀ (volume ratio 5.66),
    a trigonal description of a cubic truth at equal volume, a resolved
    orthorhombic split of a tetragonal cell.  The extras and the verdict are
    :func:`~rietx.indexing.screen.containment_evidence`'s, asked at the
    resolution rather than in the search window.  ``screen`` is the run's
    :class:`~rietx.indexing.screen.PatternScreen`; built from the peak list
    alone when the caller has none, which is all this check needs.
    """
    from ..schemas.indexing import SupercellCheck
    from .ambiguity import MAX_DISCRIMINATING
    from .quality import shift_template_basis
    from .screen import PatternScreen, containment_evidence, screen_for

    if screen is None:
        screen = PatternScreen.from_peaks(peaks, q_match=q_match, k_sigma=k_sigma)
    screens = []
    for cand in candidates:
        try:
            screens.append(screen_for(screen, cand, peaks, absence=False))
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            screens.append(None)
    for j, child in enumerate(candidates):
        child.supercell_checks = []
        if screens[j] is None:
            continue
        for i, parent in enumerate(candidates):
            if i == j or screens[i] is None:
                continue
            try:
                ev = containment_evidence(screen, screens[j], screens[i])
            except (ValueError, RuntimeError, np.linalg.LinAlgError):
                # an unanswered pair orders nothing, as ``_partners`` declines
                ev = None
            if ev is None:
                continue
            missing = np.array([q for q, seen in zip(ev.extra_q, ev.extra_seen)
                                if not seen][:MAX_DISCRIMINATING])
            tt = np.degrees(2.0 * np.arcsin(np.clip(
                peaks.wavelength * np.sqrt(missing) / 2.0, -1.0, 1.0)))
            # the child was screened on its shift-corrected lines; say where to
            # look on the pattern's own axis by undoing that correction
            template = child.shift_template
            if template is not None and child.shift_coefficient and len(tt):
                basis = shift_template_basis(tt)
                if template in basis:
                    tt = tt + child.shift_coefficient * basis[template]
            child.supercell_checks.append(SupercellCheck(
                parent_cell=tuple(parent.cell), parent_system=parent.system,
                parent_centring=parent.centring, index=ev.index,
                relation=ev.relation,
                n_extra=ev.n_extra, n_seen=ev.n_seen, p0=ev.p0,
                p_value=ev.p_value, verdict=ev.verdict(),
                n_seen_unexplained=ev.n_seen_unexplained,
                absent_two_theta=[float(t) for t in tt]))


def absence_excess(candidates: Sequence[CellCandidate]) -> None:
    """Write ``lebail.predicted_but_absent_excess_in_window`` on every
    candidate the line screen validated, in place (#941's follow-up).

    The windowed uncancellable count read as a **density compared across
    candidates**: A − N_w·d_min, where d_min is the lowest
    ``predicted_but_absent_density_in_window`` among the run's screened
    candidates.  The field's figures of merit are densities read
    comparatively (de Wolff 1968's M₂₀ divides by the lines a cell predicts up
    to the twentieth observed one; Smith & Snyder 1979's F_N by N_poss; EXPO's
    WRIP20, Altomare *et al.* 2009, against the best candidate), and the raw
    count is not: magnetite's and PbSO₄'s true cells read 2, as LaB₆'s wrong
    a√2 I cell does on synthetic data.  Measured at ``RESOLUTION_FWHM`` 1.0
    on the acceptance corpus's real families (SRM 676a corundum with and
    without the cos θ shift declared, zincite, zircon, brucite, magnetite,
    fluorite, fluorapatite, 11-BM NAC, SRM 660c LaB₆ as picked and
    calibrated) and both PbSO₄ histograms (neutron and lab X-ray), every true
    cell reads an excess of 0 to 0.06, magnetite's and PbSO₄ neutron's
    included, and every oversized cell at least 1; two cells within 0.5 % of
    PbSO₄'s metric, with the truth's line set, read what it reads.  The
    excess comes from the line screen, so it is identical under the Le Bail
    and the Pawley validation fit.  **Reported, not gated**: the
    cleanest candidate of a list that missed the truth, and a lone candidate,
    read 0 whatever their count, so it cannot replace the cap.
    """
    screened = [c for c in candidates
                if c.lebail is not None
                and c.lebail.predicted_but_absent_density_in_window is not None]
    if not screened:
        return
    d_min = min(c.lebail.predicted_but_absent_density_in_window for c in screened)
    for c in screened:
        c.lebail.predicted_but_absent_excess_in_window = float(
            c.lebail.predicted_but_absent_uncancellable_in_window
            - c.lebail.n_lines_screened_in_window * d_min)


def _parent_key(check) -> tuple:
    return tuple(check.parent_cell) + (check.parent_system,
                                       check.parent_centring)


def _parents_with(candidates: Sequence[CellCandidate], verdict: str,
                  ) -> list[set[int]]:
    """For each candidate, the positions of the parents its checks give
    ``verdict``, among ``candidates``."""
    cells = [tuple(c.cell) + (c.system, c.centring) for c in candidates]
    out = []
    for child in candidates:
        keys = {_parent_key(k) for k in child.supercell_checks or []
                if k.verdict == verdict}
        out.append({i for i, key in enumerate(cells) if key in keys})
    return out


def _after_waits(waits: Sequence[set[int]]) -> list[int]:
    """Positions in their given order, each held back until its waits are placed.

    A held position lands directly after the last of its waits, and the
    positions between keep their order above it.
    """
    order: list[int] = []
    placed: set[int] = set()
    remaining = list(range(len(waits)))
    while remaining:
        for pos, i in enumerate(remaining):
            if waits[i] <= placed:
                order.append(i)
                placed.add(i)
                del remaining[pos]
                break
        else:                           # unreachable for sublattice pairs
            order.extend(remaining)
            break
    return order


def _checks_in_final_order(ordered: Sequence[CellCandidate]) -> None:
    """Re-sort each candidate's checks into its parents' order in ``ordered``.

    A parent can itself move, so the order a check was asked in is stale once
    the list is re-ranked.  After this, the last refuting check names the
    parent a refuted child sits directly below, which is what its diagnostic
    quotes.
    """
    rank = {tuple(c.cell) + (c.system, c.centring): r
            for r, c in enumerate(ordered)}
    for child in ordered:
        if child.supercell_checks:
            child.supercell_checks = sorted(
                child.supercell_checks,
                key=lambda k: rank.get(_parent_key(k), len(ordered)))


def below_refuting_parents(candidates: Sequence[CellCandidate]
                           ) -> list[CellCandidate]:
    """The ranked list with every refuted supercell directly below its parent.

    A candidate whose :class:`~rietx.schemas.indexing.SupercellCheck` against a
    parent reads ``"refuted"`` waits until every parent refuting it is placed,
    and the list is otherwise taken in its given order.  So a refuted child
    lands directly below the lowest-ranked parent that refutes it, candidates
    between them keep their places above it, and nothing else moves.  A parent
    is strictly smaller than its child, so the waits cannot form a cycle.

    Why an order and not only a caveat (WP-1449): a caller reads
    ``candidates[0]`` first, and on brucite a supercell the data refute stood
    there above the certified cell, which the gate was already declining to
    promote.  Why this and not a score: re-weighting the panel mends one
    dataset and breaks another (WP-1041).  The check is binary, like
    corroboration, and moves only the pairs it refutes.
    :func:`above_supported_parents` is the other half.
    """
    order = _after_waits(_parents_with(candidates, "refuted"))
    out = [candidates[i] for i in order]
    _checks_in_final_order(out)
    return out


def above_supported_parents(candidates: Sequence[CellCandidate]
                            ) -> list[CellCandidate]:
    """The ranked list with every supported supercell directly above its parent.

    The mirror of :func:`below_refuting_parents` (WP-1510).  A candidate whose
    check against a parent reads ``"supported"`` moves up to directly above
    the highest-ranked parent supporting it, and nothing else moves.  A child
    already above its parents stays where it is.  Built as that function's
    waits on the reversed list, so the child is again the one that moves.

    Why: a supported check says the lines this cell adds over the parent, the
    ones no extinction could remove, are seen on lines the parent cannot index
    more often than chance allows at ``SUPERCELL_CHANCE_ALPHA``.  So the
    parent is not the whole lattice.  Before this, a supported check moved
    nothing, so finder count decided.  On SRM 676a, once the duplicate copies
    left the list, only dichotomy found the certified cell while all three
    engines found its c/2 subcell, which leaves 10 of 47 usable lines
    unexplained.  The certified cell's 18 extras over it are seen 8 times, all
    on those lines, at p₀ = 0.150 (p = 0.0027), and corroboration had put the
    subcell first and the certified cell eighth.  Corroboration does not hold
    the child back here, just as it does not protect a refuted child: the
    check is a lattice statement about the pair, not a score.

    **A refuted child is never promoted.**  If any reported cell explains its
    extras, it is oversized, whatever another pair says.  That also keeps the
    two halves from contradicting each other: a refuted child keeps its place
    under its refuting parents, and moving a parent up never moves its refuted
    children above it.
    """
    refuted = _parents_with(candidates, "refuted")
    supported = [set() if refuted[i] else s
                 for i, s in enumerate(_parents_with(candidates, "supported"))]
    n = len(candidates)
    # reversed, "below" reads "above": each supported child waits for its
    # supported parents, so it lands directly past the highest-ranked of them
    flipped = [{n - 1 - j for j in supported[n - 1 - i]} for i in range(n)]
    order = [n - 1 - i for i in reversed(_after_waits(flipped))]
    out = [candidates[i] for i in order]
    _checks_in_final_order(out)
    return out


def checked_indices(candidates: Sequence[CellCandidate],
                    engines_run: Sequence[str], *,
                    top: int = CONSENSUS_CHECK_TOP) -> list[int]:
    """Which candidates get the expensive checks, in rank order.

    The union of two sets, and the second is what makes the cap safe: the top
    ``top`` by Borda rank, **plus every candidate that every engine found**.  A
    candidate the engines agree on is the only kind the gate can promote to
    ``high``, so skipping one would silently convert a cap on cost into a cap on
    the answer — and a candidate that is checked but ranked eleventh is a cheap
    thing to allow, since the pool is already capped at
    ``SearchSpec.max_candidates``.

    One function rather than two similar loops because ambiguity enumeration and
    whole-pattern validation must cover the *same* candidates: a candidate validated but
    not checked for ambiguity could reach ``high`` with an unenumerated partner.

    Since WP-1046 the second set is *mostly* inside the first — agreement is the
    ranking's leading key, so an all-engine candidate cannot sit below one with
    fewer finders — and it is kept because "mostly" is not "always": a run with
    more than ``top`` all-engine candidates still has some outside the head, and
    the guarantee is what this function exists for.
    """
    want = set(range(min(top, len(candidates))))
    engines = set(engines_run)
    for i, cand in enumerate(candidates):
        if engines and set(cand.found_by) >= engines:
            want.add(i)
    return sorted(want)


def consensus(results: Sequence[EngineResult], peaks: PeakList, *,
              spec: SearchSpec | None = None,
              quality: DataQualityReport | None = None,
              top: int = CONSENSUS_CHECK_TOP,
              cancel=None, ambiguity: bool = True,
              priors: Sequence[EngineCandidate] = (),
              screen=None) -> ConsensusOutcome:
    """Merge, rank, classify and enumerate ambiguity — everything but validation.

    Order matters and it is the WP's: reduce and merge (so ``found_by`` is
    complete before anything is ranked), then Borda over the **whole** figure-of-
    merit panel (never a member — measured, ``indexed_fraction`` alone put a
    390-line wrong phase above the truth), then the two-opinion Bravais screen and
    the geometrical-ambiguity enumeration on the checked subset.

    ``cancel`` (WP-1037) is read by the ambiguity enumeration only, between
    candidates and between one candidate's derivative cells (#895) — merging,
    ranking and the Bravais screen always run, because they are what turns raw
    engine output into an answer at all and they are cheap (the enumeration was
    measured at 45 of a 105 s ceiling-bound corundum run; everything else here
    is noise).  A skipped candidate stays out of ``ambiguity_checked``, which
    is what makes the gate read it honestly.

    ``ambiguity=False`` (WP-1042) skips the enumeration entirely — it is what
    makes this callable per **completed system** mid-run, since everything else
    here is the cheap part.  ``ambiguity_checked`` then stays empty and the
    gate reads every candidate as unchecked (a capping caveat), so a streamed
    grade is conservative: it can rise when the full consensus runs, never
    fall.

    ``screen`` is the run's :class:`~rietx.indexing.screen.PatternScreen`
    (C3), handed to :func:`supercell_checks`; built from the peak list when
    ``None``.

    ``priors`` (WP-1045) are checked prior cells (finder ``"prior"``, from
    ``priors.build_prior_candidates``).  They join the *merge* — a prior that
    is an engine candidate's lattice adds a ``found_by`` member and nothing
    else — but a prior-only lattice **never enters the Borda ranking**: it is
    ranked among its own kind and appended after the engine candidates.
    Borda violates independence of irrelevant alternatives, so this is what
    makes "a wrong prior changes no rank" structural rather than an empirical
    hope.  ``"prior"`` is deliberately absent from ``engines_run``, so the
    ordinary agreement caveat grades a prior-only candidate down with no new
    gate vocabulary.
    """
    from .priors import PRIOR_FINDER

    spec = spec or SearchSpec()
    carrier: list[EngineResult] = []
    if priors:
        holder = EngineResult(engine=PRIOR_FINDER)
        holder.candidates = list(priors)
        carrier = [holder]
    merged = merge_engine_candidates([*results, *carrier])
    prior_only = [c for c in merged if c.found_by == [PRIOR_FINDER]]
    merged = [c for c in merged if c.found_by != [PRIOR_FINDER]]
    # the same window the engines assigned with, re-derived from the same two
    # inputs — ranking candidates in a *tighter* one judges them by a criterion
    # they were never selected under (``fom.fom_panel``)
    q_match = match_window(peaks, spec, quality)
    # the panel trims what the search tolerated (``fom.trimmed_mean``): the
    # inlier rule's system-free leftover, or a declared count verbatim
    driven = search_line_order(peaks, spec)
    trim = search_acceptance(peaks, driven, spec)[0]
    reported = spec.max_candidates or DEFAULT_MAX_CANDIDATES
    # ``shortlist=None``: every merged lattice is scored, not the cheap
    # pre-rank's top ``4 × max_candidates`` (WP-1046).  What arrives here is
    # already bounded by each unit's ``engine_pool``, so there is no harvest to
    # protect against — and tying the panel's reach to the number the answer
    # reports is the same defect as truncating in the units.
    ranked = rank_candidates(merged, peaks, k_sigma=spec.k_sigma,
                             n_unindexed=trim,
                             max_candidates=reported,
                             shortlist=None, q_match=q_match)
    out = ConsensusOutcome(
        engines_run=[r.engine for r in results],
        fom_panel_disagrees=fom_panel_disagrees([c.fom for c in ranked
                                                 if c.fom]))
    systems: list[str] = []
    for result in results:
        for system in result.systems_searched:
            if system not in systems:
                systems.append(system)
        for key, value in result.stats.items():
            out.engine_stats[f"{result.engine}.{key}"] = float(value)
        # deduplicated on (code, message): every engine widens its window by the
        # same assumed allowance and says so in the same words, and N identical
        # copies of one statement reads as N problems.  Two engines that say
        # different things about the same code (different systems incomplete, say)
        # keep both messages, which is why the message is part of the key.
        for diag in result.diagnostics:
            if not any(d.code == diag.code and d.message == diag.message
                       for d in out.diagnostics):
                out.diagnostics.append(diag)
        if any(d.code == "INDEX_SHIFT_ALLOWANCE" for d in result.diagnostics):
            out.shift_allowance_assumed = True
    out.systems_searched = systems
    # what the reported list left out, at the one layer that can state it
    # exactly (WP-1046).  ``merged`` is post-dedup, so the difference counts
    # *lattices*, not repeats; the pool clause is a flag read from the stat each
    # unit sets when its own hand-off pool bound.  ``len(ranked)`` rather than
    # the cap, so the count is what was reported and not what was allowed.
    capped = sorted(f"{r.engine}:{key.split('.')[0]}"
                    for r in results for key, value in r.stats.items()
                    if key.endswith(".pool_capped") and value)
    if len(merged) > len(ranked) or capped:
        out.diagnostics.append(candidates_truncated_diagnostic(
            len(merged), len(ranked), capped, spec.engine_pool()))
    # a system is complete only if **every** engine that ran both entered it
    # and exhausted its domain (WP-1042).  The second half is the new one:
    # under the system-major scheduler a deadline can stop the run with a
    # system entered by some engines and never reached by another, and that
    # engine's silence there is not evidence — before this rule such a system
    # read "searched to completion" whenever the engines that did enter it
    # finished, and the budget diagnostic had nothing to name.
    out.search_complete = {
        s: all(bool(r.search_complete.get(s, False)) for r in results)
        for s in systems}

    out.candidates = [
        to_cell_candidate(c, peaks, k_sigma=spec.k_sigma,
                          n_unindexed=trim, q_match=q_match,
                          search=driven)
        for c in ranked]
    # a supercell the data refute sits below its parent (WP-1449), and one the
    # data support sits above it (WP-1510).  Here, on the engines' list, so
    # every streamed per-system list orders the same way as the final one; a
    # prior-only tail is appended after and never asked
    # an absence test reads the assumed bound, never the widths' window: a
    # narrow window gives it power the unmeasured shift does not (#951)
    supercell_checks(out.candidates, peaks,
                     q_match=absence_window(peaks, spec, quality),
                     k_sigma=spec.k_sigma, screen=screen)
    out.candidates = above_supported_parents(
        below_refuting_parents(out.candidates))
    if prior_only:
        # ranked among their own kind only, appended after every engine
        # candidate: a prior may not displace what the engines found
        tail = rank_candidates(prior_only, peaks, k_sigma=spec.k_sigma,
                               n_unindexed=trim,
                               max_candidates=spec.max_candidates
                               or DEFAULT_MAX_CANDIDATES,
                               shortlist=None, q_match=q_match)
        out.candidates += [
            to_cell_candidate(c, peaks, k_sigma=spec.k_sigma,
                              n_unindexed=trim, q_match=q_match,
                              search=driven)
            for c in tail]
    for cand in out.candidates:
        cand.bravais = bravais_opinion(cand.cell, cand.centring,
                                       cell_esd=np.asarray(cand.cell_esd))
    if ambiguity:
        enumerate_ambiguity(out, peaks, top=top, cancel=cancel)
    return out


def enumerate_ambiguity(outcome: ConsensusOutcome, peaks: PeakList, *,
                        top: int = CONSENSUS_CHECK_TOP, cancel=None) -> None:
    """The geometrical-ambiguity pass over the checked candidates, in place.

    Split out of :func:`consensus` in WP-1045 so ``index_pattern`` can run it
    **after** the budgeted validation: whole-profile validation is the
    mandatory check, and this enumeration — measured at 45 s of a
    ceiling-bound corundum run, with one candidate's 55-lattice sweep
    uninterruptible — consumed the whole validation reserve whenever it ran
    first.  ``cancel`` is read between candidates and, since #895, between
    one candidate's derivative cells, so a stop waits one child's work rather
    than a whole sweep.  A candidate the clock stops before or during its
    sweep stays out of ``ambiguity_checked`` with no partners written, which
    the gate reads as an unasked question (capping), never a clean answer.
    A sweep that refuses (the parent's own lines cannot be predicted) is the
    same unasked question, so its candidate stays out too (WP-1924).
    """
    checked = set(checked_indices(outcome.candidates, outcome.engines_run,
                                  top=top))
    for i, cand in enumerate(outcome.candidates):
        if i in checked and i not in outcome.ambiguity_checked \
                and not (cancel is not None and bool(cancel)):
            partners = _partners(cand, peaks, cancel=cancel)
            if partners is None:
                continue
            cand.ambiguity = partners
            outcome.ambiguity_checked.append(i)


def _partners(cand: CellCandidate, peaks: PeakList, *, cancel=None):
    """The candidate's partners, or ``None`` where the sweep refused or was
    stopped: neither has asked the question, and ``[]`` would answer it."""
    from .ambiguity import ambiguity_partners

    try:
        return ambiguity_partners(cand.cell, cand.system, cand.centring,
                                  peaks.q(), peaks.q_esd(), peaks.wavelength,
                                  float(peaks.two_theta_max),
                                  two_theta_min=float(peaks.two_theta_min),
                                  cancel=cancel)
    except (ValueError, RuntimeError, np.linalg.LinAlgError):
        return None


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
def caveats_for(cand: CellCandidate, *, engines_run: Sequence[str],
                panel_disagrees: bool, validated: bool,
                search_complete: dict[str, bool],
                shift_allowance_assumed: bool,
                checked: bool = True,
                panel_reduced: bool = False,
                min_indexed_fraction: float = INDEX_MIN_INDEXED_FRACTION,
                volume_max: float | None = None) -> list[IndexCaveat]:
    """Every reason this candidate is not ``"high"``, from the closed vocabulary.

    Collected in one place and graded in another (:func:`grade`) for the same
    reason ``indexing/diagnostics.py`` is separate from the fitter: the facts and
    what they are worth are different decisions, and a threshold should move
    without touching the code that measures.

    **``unmatched_observed`` is deliberately not read here, and it was measured
    rather than overlooked** (WP-1041).  A caveat is an absolute verdict on one
    candidate, and that count has no absolute scale: across 21 validated
    candidates on six known-cell datasets it runs 10 to 188 *for correct cells*,
    because its level is set by how much of the specimen the candidate's phase is
    not — 11-BM NAC's own truth leaves 188 unmatched against a CaF₂ impurity.
    Within one pattern it does discriminate, and there it is nearly the number
    the fit already reports: Spearman ρ against Rwp is +0.80 to +1.00 on the five
    datasets with enough candidates to rank, against +0.44 pooled across them.
    So it is a comparative instrument, and reading it as a per-candidate verdict
    is the same mistake as scoring the FoM panel absolutely
    (:func:`~rietx.indexing.fom._log_sum_scores`).
    """
    out: list[IndexCaveat] = []
    engines = set(engines_run)
    if engines and not set(cand.found_by) >= engines:
        out.append("engines_disagree")
    if cand.ambiguity:
        out.append("geometric_ambiguity")
    elif not checked:
        # not enumerated is not "none found"; the honest reading is that the
        # question was not asked, and it must not read as a clean answer
        out.append("geometric_ambiguity")
    if panel_disagrees:
        out.append("fom_panel_disagrees")
    if panel_reduced:
        # below the scoring bar (WP-1043): the panel that ranked this candidate
        # lacks the classical figures, so ``high`` stays exactly as unreachable
        # as the old abstention made it — capping, because a short list is not
        # evidence against the cell
        out.append("fom_panel_reduced")
    if not validated or cand.lebail is None:
        out.append("not_validated")
    elif cand.lebail.status in ("failed", "diverged"):
        out.append("validation_failed")
    elif cand.lebail.predicted_but_absent_uncancellable_in_window is not None:
        # the line screen's count (C3): the uncancellable absences inside de
        # Wolff's window, which every truth measured reads at 0-2 and every
        # wrong cell at 7-79; capping, since a true cell's weak general
        # reflections below detection are absent for a reason that is not
        # the lattice's
        if cand.lebail.predicted_but_absent_uncancellable_in_window:
            out.append("predicted_but_absent")
    elif cand.lebail.predicted_but_absent:
        # no peak list was supplied, so the fitted-background detector's count
        out.append("predicted_but_absent")
    # read on the intensity the cell explains (WP-1969, #933): a cell's own
    # weak impurity lines are not evidence against it by their count, and a
    # missed strong line is evidence whatever the count.  The line fraction
    # stays the reading for a panel built without the weighted member
    fraction = cand.fom_value("indexed_intensity_fraction")
    if fraction is None:
        fraction = cand.fom_value("indexed_fraction")
    if fraction is None or fraction < min_indexed_fraction:
        out.append("indexed_fraction_low")
    else:
        # the ruling on the superstructure dissenter (yue-here, #1042): a
        # sub-cell missing a superlattice explains every strong line and leaves
        # weak ones, so it can pass on intensity, and from the line list alone a
        # superlattice line and an impurity line look the same.  A line count
        # under the same bar therefore caps the grade at ``medium`` (GSAS-II
        # scores cells by count only: M20, X20), without refuting the cell
        lines = cand.fom_value("indexed_fraction")
        if lines is not None and lines < min_indexed_fraction:
            out.append("indexed_lines_low")
    if not search_complete.get(cand.system, True):
        out.append("search_incomplete")
    if shift_allowance_assumed:
        out.append("shift_allowance_assumed")
    if cand.bravais is None or cand.bravais.ambiguous or \
            cand.bravais.methods_disagree:
        out.append("bravais_ambiguous")
    if cand.volume < DEFAULT_MIN_VOLUME or (
            volume_max is not None
            and cand.volume > VOLUME_ENVELOPE_SLACK * volume_max):
        out.append("volume_unphysical")
    if any(c.verdict == "refuted" for c in cand.supercell_checks or []):
        out.append("supercell_refuted")
    return out


def grade(caveats: Sequence[str], found_by: Sequence[str],
          engines_run: Sequence[str]) -> Confidence:
    """The three-level verdict, and the whole of it is four lines.

    * ``low`` — fewer than two engines behind it, or **any** refuting caveat.
      One engine is not agreement, and a refuting caveat is evidence against the
      cell rather than a qualification of it.
    * ``high`` — every engine that ran found this lattice and there is *nothing*
      to qualify.
    * ``medium`` — everything else: at least two independent searches agree and
      the only outstanding caveats are ones that cap rather than refute.

    The WP's "≥2 engines, or all with one caveat" is this, read with the first
    clause as the fallback: caveat *count* is not what separates medium from low,
    because two capping caveats (an assumed tolerance and an unvalidated
    candidate) are the ordinary state of a peaks-only run and would otherwise
    make every answer ``low`` — which would empty the vocabulary of meaning.

    **A prior corroborates but does not confirm** (WP-1003, recording 1046
    §4): agreement means independent *searches*, and a stated cell is not
    one.  ``found_by`` currently counts :data:`~.engines.PRIOR_FINDER` toward
    ``MIN_AGREEMENT``, so a prior one engine also found can reach ``medium``
    partly on the strength of its own statement; the ruled fix — count
    engines the way ``engines.corroborated`` does, prior excluded — is
    deferred into the post-1003 indexing work, where the acceptance suite
    runs.  Deferred on the record, not silently frozen.
    """
    # MIN_AGREEMENT rather than a literal 2 since WP-1046: this floor and
    # ``engines.corroborated`` — the ranking's first key — are one boundary, so
    # the reported order mirrors the gate structurally and not by coincidence
    if len(set(found_by)) < MIN_AGREEMENT or any(c in INDEX_REFUTING_CAVEATS
                                                 for c in caveats):
        return "low"
    if not caveats and set(found_by) >= set(engines_run):
        return "high"
    return "medium"


def apply_gate(candidates: Sequence[CellCandidate], *,
               engines_run: Sequence[str], panel_disagrees: bool,
               validated: bool, search_complete: dict[str, bool],
               shift_allowance_assumed: bool,
               checked: Sequence[int] | None = None,
               quality: DataQualityReport | None = None,
               min_indexed_fraction: float = INDEX_MIN_INDEXED_FRACTION,
               ) -> list[CellCandidate]:
    """Write ``confidence`` and ``confidence_caveats`` onto every candidate.

    Mutates in place and returns the same list: the candidates are this
    function's output, and copying them would leave two objects that could
    disagree about a verdict there is only one of.
    """
    was_checked = set(range(len(candidates)) if checked is None else checked)
    panel_reduced = quality is not None and bool(quality.fom_undefined)
    for i, cand in enumerate(candidates):
        volume_max = None
        if quality is not None:
            volume_max = quality.volume_envelope.get(cand.system)
        cand.confidence_caveats = caveats_for(
            cand, engines_run=engines_run, panel_disagrees=panel_disagrees,
            validated=validated, search_complete=search_complete,
            shift_allowance_assumed=shift_allowance_assumed,
            checked=i in was_checked, panel_reduced=panel_reduced,
            min_indexed_fraction=min_indexed_fraction, volume_max=volume_max)
        cand.confidence = grade(cand.confidence_caveats, cand.found_by,
                                engines_run)
    return list(candidates)


__all__ = ["CONSENSUS_CHECK_TOP", "VOLUME_ENVELOPE_SLACK", "ConsensusOutcome",
           "above_supported_parents", "absence_excess", "apply_gate", "below_refuting_parents",
           "bravais_opinion",
           "caveats_for", "checked_indices", "consensus", "grade",
           "merge_engine_candidates", "supercell_checks"]
