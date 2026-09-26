"""What every search engine shares: the registry, the option surface, the
budget, the crash guard, and the shape of an answer.

Three engines search for a cell (WP-1021 dichotomy, WP-1022 trial and error,
WP-1023 Monte Carlo) and their **agreement** is the confidence WP-1024 reports —
the same device as ``sequential.py``'s ``direction="both"`` and the cross-backend
Jacobian matrix.  That only works if they are genuinely independent *searches*
that answer in one vocabulary, so everything shared but non-searching lives here:

* :class:`SearchSpec` — one option object, so a caller sets ``max_volume`` once
  and every engine means the same thing by it;
* :class:`EngineCandidate` / :class:`EngineResult` — the answer shape, carrying
  the ``CandidateFit`` (hence ``cov_af``, hence WP-1020's χ² dedup) rather than
  only the schema object, because consensus needs the covariance;
* :func:`register_engine` / :func:`engine_names` — the **live registry**
  WP-1024's agent schema quotes, so a fourth engine cannot be absent from the
  exported tool definition (the WP-0602 meta-test pattern);
* :class:`Budget` and ``search_complete`` — an engine that ran out of time must
  say so per system, because *silence is only evidence when the search finished*;
* :func:`reflection_ceiling_ok` — the crash guard.

**The crash guard is not a quality guard, and it is the most load-bearing
function here.**  Measured in this repo's own prior art (tag ``guillemot-study``,
``audit_tools.py`` check B): a runaway cell on a 1.7 wt % phase made the
reflection generator ask for **1.6 PiB**.  ``generate_reflections`` enumerates a
box ``hmax = floor(a/d_min) + 1`` per axis, so the count goes as the volume, and a
search that *proposes* cells — all three of these do — will eventually propose one
big enough to exhaust memory.  Every path that reaches ``generate_reflections``
from a trial cell goes through :func:`reflection_ceiling_ok` first.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    METRIC_DOF,
    TRUSTED_SHIFT_SOURCES,
    CellCandidate,
    PeakList,
)
from .fom import MATCH_SIGMA, fom_panel, lattice_group, match_lines
from .qspace import CandidateFit, design_matrix, metric_basis, refine_candidate, trial_hkl

#: Systems in decreasing lattice-point-group order — the order every engine
#: searches in.  Highest symmetry first is not a preference, it is a cost
#: statement: the metric has 1 degree of freedom in cubic and 6 in triclinic, so
#: a cubic answer costs seconds while a triclinic search costs minutes, and a
#: caller who gets the cubic answer first can stop.
SYSTEM_ORDER: tuple[str, ...] = ("cubic", "hexagonal", "trigonal", "tetragonal",
                                 "orthorhombic", "monoclinic", "triclinic")

#: Bravais centrings each system admits, in the conventional setting.  A search
#: over metrics alone would miss every centred lattice whose *primitive* cell is
#: not in the same system — a body-centred cubic lattice has a rhombohedral
#: primitive cell, so a cubic-subspace search that assumed P would never see it.
#: Centring costs nothing to carry: it is a filter on the trial hkl set, and a
#: filtered set is *harder* to satisfy, so it prunes rather than adds work.
CENTRINGS: dict[str, tuple[str, ...]] = {
    "cubic": ("P", "I", "F"),
    "hexagonal": ("P",),
    "trigonal": ("P", "R"),
    "tetragonal": ("P", "I"),
    "orthorhombic": ("P", "C", "I", "F"),
    "monoclinic": ("P", "C"),
    "triclinic": ("P",),
}

#: Predicted reflections above which a trial cell is refused rather than
#: enumerated.  Two million integer triples is ~48 MB of hkl plus the d-spacing
#: pass — large enough that no legitimate cell in a bounded search reaches it
#: (SRM 660c to 90° 2θ predicts 24) and small enough to be an instant, survivable
#: refusal.  See the module docstring for the 1.6 PiB that motivated it.
MAX_PREDICTED_REFLECTIONS = 2_000_000
#: Relative agreement in reduced-cell volume below which two candidates are worth
#: comparing properly.  A gate, not a test: two lattices whose volumes differ by
#: more than this cannot pass the χ² metric equality, so the gate only skips
#: comparisons whose answer is already known — which is what keeps a dedup pass
#: over thousands of raw candidates from being O(N²) pinv solves.
DEDUP_VOLUME_RTOL = 0.01

#: Default shortest principal d-spacing (Å) a search will consider.  A bound on
#: *d(100)*, not on *a*: for an oblique cell d(100) = a·sin β < a, so this is
#: slightly the stronger statement, and it is the one the Q-space box actually
#: constrains (A = 1/d(100)²).
DEFAULT_MIN_D_AXIS = 2.0
#: Default longest principal d-spacing (Å).  25 Å covers small-molecule organics
#: (the bethanechol benchmark's longest axis is 15.9 Å); a caller with a protein
#: or a layered phase raises it and pays for it in search volume.
DEFAULT_MAX_D_AXIS = 25.0
#: Smallest unit-cell volume (Å³) a search will report.  Below this the "cell" is
#: smaller than a single atom's exclusion volume, so it is a numerical artefact
#: of the metric cone rather than a lattice.
DEFAULT_MIN_VOLUME = 15.0
#: Observed lines a search is *driven* by — **the strongest N**, in Q order once
#: chosen (:func:`search_line_order`, which is where the ranking rule and its
#: measured grounds live).  Scoring afterwards uses **every** usable line, so a
#: candidate that explains these N and nothing else is ranked down rather than
#: hidden.
#:
#: **Enumerate liberally, sort conservatively** (Oishi-Tomiyasu 2014, *J. Appl.
#: Cryst.* **47**, 593, §3): a *false* line costs only computation — "the success
#: rate in obtaining the correct solution remains the same if Λ^obs is replaced
#: with Λ^obs ∪ {q^obs}" — while a *missing* line costs success, and the figures
#: of merit, unlike the enumeration, are "severely affected" by both.
#:
#: **That asymmetry is asserted there, not proved, and the difference is worth
#: keeping** (WP-1039 read the paper rather than the summary of it): §3 is running
#: prose with no proposition or proof, the statement is made for a *single* added
#: element, and the superset argument that would justify it is never written down.
#: Conograph's own numbers are likewise softer than they are usually quoted —
#: ``N_peak`` is **AUTO** with 48 an *upper threshold* (Table 1), the enumeration
#: cost ∝ N_zone² ∝ N_peak⁴ is hedged twice and defers to supporting information
#: absent from our corpus, and the celebrated 18-250× zone-sorting speedup is
#: 1/rate² computed from measured *selection rates* under that assumed cost model,
#: never a timed A/B.  Read as this package's own rule would have it: a cost model
#: reasoned from an algorithm's structure is not a profile.
#:
#: Twenty, then, is measured here rather than deferred to (WP-1039).  Swept over
#: the known-cell corpus, raising N bought **nothing** at any price — every
#: dataset that indexes at 20 indexes at 20 — and on ``11BM_NAC.fxye``, the
#: pattern that motivated the whole question, N = 48 still spends 16 of its 48
#: lines on background components.  What fixed NAC was the *rank*, not the count.
#: Note also that the split here is not Conograph's shape: it enumerates on ≤ 48
#: and *sorts* on 20-30, where this package searches on these N and scores on
#: **every** usable line, which is the more conservative half of the two.
DEFAULT_SEARCH_LINES = 20
#: Multiple of ``n_search_lines`` forming the low-Q pool the strongest N are drawn
#: from (:func:`search_line_order`).  **A cost bound, and the reason it exists is
#: measured** (WP-1039): ranking by intensity over the *whole* list lets the driven
#: set reach the pattern's high-angle end — on the qarr corundum list, 25.5-150.1°
#: where the low-Q rule gives 5.2-76.8° — and dichotomy sizes its recursion trial
#: set by the driven lines' largest Q, so every box test then carries a far larger
#: set.  Measured on that pattern's trigonal search: 72 s unbounded against 26 s at
#: this bound and 6 s for the old low-Q-only rule, all three ranking the certified
#: cell first.
#:
#: **Two is the smallest pool that gives the rank any freedom at all** — at one the
#: selection *is* the lowest N and intensity cannot act — which is the argument for
#: it, rather than a tuned optimum.  It is also enough to preserve what the rule was
#: for: a list of 2N lines or fewer (SRM 660c's 30) is selected exactly as the
#: unbounded rule would select it, which is why the caveat that rule cleared stays
#: cleared.
#:
#: **What it costs is a little selection quality, and that is the honest trade.**
#: NAC goes from 20 of 20 unbounded to 18, corundum 19 to 17, zircon 18 to 17 — all
#: still far above the 6 of 20 the low-Q rule gives NAC, and every acceptance row
#: passes either way.  What it buys is the whole indexing acceptance file at
#: **~12 min against ~25** (against ~6 before this WP): the rule is a correctness
#: change that is not free, and half its price was avoidable.
SEARCH_POOL_MULTIPLE = 2
#: Lines a search may leave unindexed and still accept a cell.  DICVOL06's own
#: reported gain, and the single most valuable option here: without it one
#: impurity line prunes the true box and the engine returns nothing, confidently.
#: **Raising it manufactures cells** — every extra tolerated line is one more
#: coincidence a wrong metric is allowed to have, so 2 is a default and 4 is a
#: statement about the specimen, not a knob to turn when nothing is found.
DEFAULT_N_UNINDEXED = 2
#: Systematic 2θ allowance (degrees) added in quadrature to every line's fitted σ
#: when **no shift has been measured** — which is the normal state at index time,
#: because a shift is only identifiable against a reference and there is no cell
#: yet (``quality.py``).
#:
#: **Why it exists is measured; its value is a policy, and the gap between the two
#: is recorded rather than hidden.**  Fitted per-line σ on the bundled qarr corundum
#: pattern has a median of 0.0056° 2θ, while the pattern's lines sit a median
#: **0.060°** from the certified cell's positions — a cos θ specimen displacement of
#: −0.065°, i.e. an **11σ** systematic.  At σ_eff = fitted σ the certified cell
#: therefore indexes *zero* lines and both engines return nothing, measured on a
#: pattern whose answer is known.  That is the whole reason a global "position
#: tolerance" of ~0.03° 2θ is the literature's default, and 0.05 is that number with
#: margin.
#:
#: **Widening it was never what that pattern needed, and the correction matters
#: more than the constant.**  WP-1023 measured that at 0.05 the trial-and-error
#: engine still found nothing and dichotomy ranked a wrong 618 Å³ cell first, and
#: that at 0.08 trial-and-error recovered a = 4.7659 Å against the certified
#: 4.7593 (+1400 ppm, the shift absorbed into the cell).  Those numbers stand.
#: The *attribution* did not: WP-1026 found the obstruction was the **peak list**,
#: not the tolerance.  ``pick_peaks`` was reporting one phantom line per strong
#: peak — a re-seeded component ~1 FWHM below it at ~10 % of its area, bought by a
#: ΔBIC gate judging a profile the group model cannot fit — so 19 % of the lines
#: offered to the search were not lines at all.  With those flagged
#: ``not_separable`` (:data:`~rietx.schemas.indexing.PEAK_REFUTED_SIGMA`) **both
#: engines index the certified pattern and rank it first**, at this allowance and
#: without widening it.  The lesson is worth more than either number: a search
#: that finds nothing indicts its input before its tolerance.
#:
#: What the allowance is still for is unchanged, and so is what it cannot do: it
#: opens the window wide enough for a systematic to fit through, and a cell found
#: inside a widened window has absorbed it.  Fixing that is
#: :func:`refine_with_shift`, *after* a candidate survives — a shift is only
#: identifiable against reference positions and a candidate cell is what supplies
#: them.  Every result records which allowance it used and says so with
#: ``INDEX_SHIFT_ALLOWANCE``.
DEFAULT_UNKNOWN_SHIFT_DEG = 0.05
#: Wall-clock seconds a single system may consume before the engine gives up on
#: it and reports ``search_complete[system] = False``.
DEFAULT_BUDGET_SECONDS = 30.0
#: Candidates the **reported** list holds — the cap
#: :func:`~rietx.indexing.consensus.consensus` applies to the merged, ranked
#: answer, and the bound :func:`estimate_ceiling` prices validation by
#: (:func:`~rietx.indexing.consensus.checked_indices` never exceeds it).
#:
#: **It used to be applied one layer down as well, and there it was a ranking**
#: (WP-1046).  Each (engine × system) unit ran the panel and Borda over its own
#: harvest and truncated *there*, before consensus ever saw the candidates —
#: and Borda is a rank-sum over the pool being ranked, so a unit's ordering is a
#: function of what else that unit happened to find.  Measured on bethanechol
#: set F in the paper's manual mode: the published lattice is found by both
#: ``svd`` and ``trial_error``, the consensus panel ranks it **3rd** — and at
#: this constant it was **absent from the result entirely**, because a longer
#: search enlarged each unit's pool until the truth fell below twelfth in both
#: of them.  The score was therefore non-monotonic in the search budget: rank 1
#: at 5 s and 15 s, gone at 30 s and 60 s, repeats agreeing exactly.  What a
#: unit hands to the merge is :data:`ENGINE_POOL_MULTIPLE` times this now, and
#: this number caps only the layer whose ordering the design says is
#: authoritative.
DEFAULT_MAX_CANDIDATES = 12
#: How much larger a unit's hand-off pool is than the reported cap.
#:
#: The two numbers are separate because they buy different things.  The pool
#: bounds the **panel cost** — ``rank_candidates`` scores
#: ``shortlist × pool`` candidates, ~1 ms each — while the reported cap bounds
#: the **validated** list, where a Le Bail fit is 0.6-8.5 s apiece.  Measured on
#: set F (WP-1026's sweep): a pool of 200 cost 91.6 s against 90.7 s at 12, so
#: the pool is nearly free and the cap is not, which is exactly why one number
#: could not serve both.  Five because it is the multiple that makes the default
#: pool the **measured** 60: that is the value WP-1026's sweep raised the cap to,
#: and at it the set-F truth returns, ranked 3rd of the merged list.  Smaller
#: multiples were not measured, so this is a value with evidence rather than a
#: minimum with none.  A caller who raises ``max_candidates`` raises the pool
#: with it, so there is still one knob.
ENGINE_POOL_MULTIPLE = 5
#: Engines that must stand behind a lattice for it to count as corroborated —
#: :func:`~rietx.indexing.consensus.grade`'s own floor, and since WP-1046 also
#: the boundary :func:`rank_candidates` sorts on.  One constant, two readers, so
#: "the reported order mirrors the gate" is structural rather than a
#: coincidence that could drift.
MIN_AGREEMENT = 2
#: ``found_by`` entry for a checked analogue prior (WP-1045).  It lives here
#: rather than in ``priors`` because :func:`agreement` — the ranking's first key
#: — has to know which finders are *engines*, and ``priors`` imports this module.
#: This is the one public spelling; the ``priors.PRIOR_FINDER`` re-export was
#: deleted pre-freeze (WP-1003).
PRIOR_FINDER = "prior"


@dataclass(frozen=True)
class SearchSpec:
    """Everything a search needs that is not the peak list itself.

    One object rather than a dozen keyword arguments per engine, because the
    three engines must mean the *same* thing by ``max_volume`` and
    ``n_unindexed`` for their agreement to be evidence of anything.

    ``max_volume`` is a **per-system** dict when it comes from
    :func:`~rietx.indexing.quality.assess_peak_list` (Smith's envelope differs
    by up to 96× across systems), a float when a caller declares one, and ``None``
    to take the envelope from the data-quality report.
    """

    systems: tuple[str, ...] = SYSTEM_ORDER
    centrings: dict[str, tuple[str, ...]] | None = None
    min_d_axis: float = DEFAULT_MIN_D_AXIS
    max_d_axis: float = DEFAULT_MAX_D_AXIS
    min_volume: float = DEFAULT_MIN_VOLUME
    max_volume: float | dict[str, float] | None = None
    n_unindexed: int = DEFAULT_N_UNINDEXED
    n_search_lines: int = DEFAULT_SEARCH_LINES
    k_sigma: float = MATCH_SIGMA
    #: systematic 2θ **allowance** the matching window must span (°), the
    #: quantity :class:`~rietx.schemas.indexing.ShiftScreen` calls
    #: ``allowance_deg`` — **never** its ``sigma_sys_deg``, the residual scatter
    #: the winning template leaves.  This field was named ``sigma_sys_deg`` too
    #: until WP-1045, and the collision made the obvious calibration protocol
    #: (measure the screen on a standard, declare its number here) fail
    #: *silently*: matching happens against **uncorrected** positions, so
    #: declaring the 4.3×-smaller scatter finds nothing at all (SRM 660c,
    #: 0.0078° vs 0.037° — the story in :func:`effective_shift_allowance`).
    shift_allowance_deg: float = 0.0
    shift_template: str | None = None
    budget_seconds: float = DEFAULT_BUDGET_SECONDS
    #: whole-run wall-clock ceiling (WP-1037), or ``None`` to let the preset
    #: decide — since WP-1042 ``index_pattern`` fills the ``quick`` default's
    #: ceiling in when this is ``None`` (``preset="full"`` declines one).
    #: ``budget_seconds`` is **per (engine × system)** — an unbounded run is
    #: 3 × 7 × 30 s of search before the probe and the validation fits, and
    #: nothing used to state that.  This is the bound a caller actually means:
    #: ``index_pattern`` wraps it in a :class:`Deadline` that every existing
    #: cooperative check reads, the run returns a complete
    #: :class:`~rietx.schemas.indexing.IndexingResult` over whatever was
    #: reached, and ``INDEX_BUDGET_EXHAUSTED`` names what was not.
    total_budget_seconds: float | None = None
    max_candidates: int = DEFAULT_MAX_CANDIDATES
    #: seeded RNG for the stochastic engine; recorded in every result so a run
    #: is reproducible from what it reports
    seed: int = 0
    #: analogue priors (WP-1045, ``indexing/priors.py``): cells and space-group
    #: symbols an isostructural compound suggests.  A prior *steers* — its
    #: system jumps the queue, its metric seeds ``search_svd``'s starting
    #: basin, and the cell itself is checked against the peak list, entering
    #: consensus as finder ``"prior"`` — and never *gates*: no system dropped,
    #: no range changed, prior-only candidates appended after the ranked list
    #: so a wrong prior costs time, never truth.  ``INDEX_PRIOR_USED`` records
    #: what was supplied and what it changed.
    prior_cells: tuple[tuple[float, float, float, float, float, float], ...] = ()
    prior_spacegroups: tuple[str, ...] = ()

    def engine_pool(self) -> int:
        """Candidates one (engine × system) unit hands to the merge.

        :data:`ENGINE_POOL_MULTIPLE` × :attr:`max_candidates`, and the one
        authority for it — every engine asks this rather than reading the
        reported cap, so "what a unit may keep" and "what the answer reports"
        cannot drift apart again (WP-1046).
        """
        return max(int(self.max_candidates), 1) * ENGINE_POOL_MULTIPLE

    def centrings_for(self, system: str) -> tuple[str, ...]:
        if self.centrings is not None and system in self.centrings:
            return self.centrings[system]
        return CENTRINGS.get(system, ("P",))

    def volume_limit(self, system: str, fallback: float) -> float:
        if self.max_volume is None:
            return fallback
        if isinstance(self.max_volume, dict):
            return float(self.max_volume.get(system, fallback))
        return float(self.max_volume)


@dataclass
class EngineCandidate:
    """One cell an engine proposes, with the fit and the assignment behind it.

    Carries the :class:`~rietx.indexing.qspace.CandidateFit` rather than only
    the schema object because everything downstream needs what the schema drops:
    ``cov_af`` is what makes dedup a χ² test rather than a percentage
    (``reduce.same_lattice``), and the assignment is what a Le Bail validation
    (WP-1024) starts from.
    """

    fit: CandidateFit
    system: str
    centring: str
    engine: str
    #: hkl assigned to the indexed lines, and which usable lines those were
    hkl: np.ndarray
    line_index: np.ndarray
    #: usable lines the engine was offered — the denominator of ``n_indexed``
    n_lines: int
    #: the FoM panel, filled by :func:`rank_candidates` (which is what ranks) so
    #: ``to_cell_candidate`` does not enumerate the same reflections twice
    fom: list = field(default_factory=list)
    #: hkl the engine *assumed* for its base lines, where it assumed any
    #: (WP-1022).  Kept because it is the evidence a dominant zone is reported
    #: from: a solution whose base indices sit at the table's edge is one the table
    #: nearly excluded.
    base_hkl: np.ndarray | None = None
    #: every engine that produced **this lattice**, filled by WP-1024's consensus
    #: merge from :func:`dedup_groups`.  Empty means "not merged yet", and
    #: :func:`to_cell_candidate` then reports ``[engine]`` — so a single-engine run
    #: needs no merge step and the field can never disagree with ``engine``.
    found_by: list[str] = field(default_factory=list)

    @property
    def n_indexed(self) -> int:
        return int(len(self.line_index))

    @property
    def cell(self) -> tuple[float, float, float, float, float, float]:
        return self.fit.cell

    @property
    def volume(self) -> float:
        return self.fit.volume


@dataclass
class EngineResult:
    """One engine's answer: candidates, what it covered, and what it did not.

    ``search_complete`` is the half that makes a *negative* result meaningful.
    An exhaustive engine that finishes a system and finds nothing has said
    something ("no cell of that symmetry and volume fits these lines"); the same
    engine stopped by its budget has said nothing at all, and the difference must
    survive into the report rather than being inferred from an empty list.
    """

    engine: str
    candidates: list[EngineCandidate] = field(default_factory=list)
    systems_searched: tuple[str, ...] = ()
    search_complete: dict[str, bool] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all(self.search_complete.values())


# ----------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------
#: name → callable.  Populated by each engine module at import; read by
#: ``index_pattern`` and by ``capabilities()``, which must quote it **live**
#: so a new engine cannot be missing from what a client is told exists.
_REGISTRY: dict[str, Callable[..., EngineResult]] = {}
#: name → one line of what the engine is for, quoted into ``capabilities()``
#: and the CLI help.  Kept beside the callable so an engine cannot register
#: without saying what it does.
_DESCRIPTIONS: dict[str, str] = {}


def register_engine(name: str, fn: Callable[..., EngineResult], description: str,
                    ) -> Callable[..., EngineResult]:
    """Register a search engine under ``name`` (idempotent per name).

    The callable's contract is
    ``fn(peaks, *, spec, quality, cancel, progress) -> EngineResult`` —
    ``progress`` (WP-1037) is a :class:`Progress` the engine feeds one unit per
    system it searches, or ``None`` from a direct call.  An engine claims a
    system in ``systems_searched`` only when it *starts* it, so a run stopped
    by its token reports the un-entered systems as not reached rather than as
    zero-second searches.
    """
    if name in _REGISTRY and _REGISTRY[name] is not fn:
        raise ValueError(f"engine {name!r} is already registered")
    _REGISTRY[name] = fn
    _DESCRIPTIONS[name] = description
    return fn


def engine_names() -> tuple[str, ...]:
    """Registered engines, in registration order."""
    return tuple(_REGISTRY)


def engine_descriptions() -> dict[str, str]:
    return dict(_DESCRIPTIONS)


def get_engine(name: str) -> Callable[..., EngineResult]:
    if name not in _REGISTRY:
        raise ValueError(f"unknown indexing engine {name!r}; registered: "
                         f"{sorted(_REGISTRY)}")
    return _REGISTRY[name]


# ----------------------------------------------------------------------
# Budget
# ----------------------------------------------------------------------
class Budget:
    """A wall-clock deadline, read cooperatively between units of search work.

    Deliberately the same posture as ``optimize.cancel.CancelToken`` (which it
    also carries): nothing is interrupted, the loop is simply not asked for more.
    ``expired()`` is cheap enough to call per box.
    """

    __slots__ = ("seconds", "_start", "_cancel")

    def __init__(self, seconds: float, cancel=None) -> None:
        self.seconds = float(seconds)
        self._start = time.monotonic()
        self._cancel = cancel

    def restart(self) -> "Budget":
        self._start = time.monotonic()
        return self

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def expired(self) -> bool:
        if self._cancel is not None and bool(self._cancel):
            return True
        return self.seconds > 0.0 and self.elapsed >= self.seconds


class Deadline(Budget):
    """The whole-run wall clock, shaped as a cancel token (WP-1037).

    A :class:`Budget` that also answers ``bool()`` and ``is_set()`` the way
    :class:`~rietx.optimize.cancel.CancelToken` does — which is the entire
    design: every cooperative check in the indexing package reads
    ``bool(cancel)``, every per-system ``Budget`` the engines construct takes
    that same object as its ``cancel``, and ``least_squares`` reads
    ``.is_set()`` — so a deadline passed *as the token* nests under all of them
    with no engine changes, and cancellation stays cooperative by construction
    (the deadline is read between units of work, never an interrupt).

    It composes with the caller's own token the way ``Budget`` always has:
    ``Deadline(seconds, cancel=user_token)`` is true when *either* the clock
    has run out or the user cancelled — the any-of token, written once.

    **The consumers that must tell the two apart** — a ceiling is a statement
    about the budget, a user cancellation is not, and :meth:`cancelled_by_user`
    is the question each of them asks:

    * ``index_pattern``'s engine loop — ``INDEX_BUDGET_EXHAUSTED`` is written
      only when the *clock* stopped the run;
    * ``index_pattern``'s validation loop — same rule; either way the un-run
      candidates keep ``lebail = None`` and read as ``not_validated``;
    * :func:`~rietx.indexing.workflow.validate_by_lebail` re-raises
      ``RefinementCancelled`` whoever triggered it — classification is its
      caller's job, and swallowing it into ``status="failed"`` would refute a
      cell the run merely ran out of time on.

    Sites that need no distinction, deliberately: ``Budget.expired()`` (an
    expired per-system budget and an expired ceiling both just stop the
    system), and every caller *outside* ``index_pattern`` — the deadline is
    constructed inside the run from ``SearchSpec.total_budget_seconds``, never
    handed in, so a GUI's own token keeps its meaning.
    """

    __slots__ = ()

    def __bool__(self) -> bool:
        return self.expired()

    def is_set(self) -> bool:
        return self.expired()

    @property
    def remaining(self) -> float:
        """Seconds left on the clock (0.0 once expired; ``inf`` if unbounded)."""
        if self.seconds <= 0.0:
            return float("inf")
        return max(self.seconds - self.elapsed, 0.0)

    def cancelled_by_user(self) -> bool:
        """Did the *caller's* token fire — as opposed to the clock?"""
        return self._cancel is not None and bool(self._cancel)


class Progress:
    """A flat unit counter over everything an indexing run does (WP-1037).

    One ladder, not two: search units — one per (engine × system) — plus the
    dominant-zone probe's per-system rungs and the per-candidate validation
    fits, all emitted on the *existing* ``stage_start``/``stage_end`` kinds
    (``history/events.py``: adding fields is not a schema bump; a nested
    second ladder on the same kind is what made the GUI's progress bar jump,
    so the per-engine pair this replaces must not come back beside it).

    ``total`` is **revisable mid-run** by :meth:`add` — the probe runs only
    when an engine found nothing and the validation count is known only after
    consensus — so a consumer treats ``n_stages`` as the current best claim,
    not a constant (the same reading ``watch`` and the GUI already apply).

    ``stream=None`` is a working no-op, so a direct engine call in a unit test
    neither needs a stream nor emits anything.

    Every emission also carries the run's **progress facts** (WP-1042):
    ``elapsed_seconds`` since the ladder was built, and ``remaining_seconds``
    when a whole-run :class:`Deadline` was declared — added fields on the
    existing kinds, not a new kind, so ``EVENT_SCHEMA_VERSION`` holds.
    """

    __slots__ = ("stream", "total", "done", "deadline", "_t0")

    def __init__(self, stream=None, total: int = 0, deadline=None) -> None:
        self.stream = stream
        self.total = int(total)
        self.done = 0
        self.deadline = deadline
        self._t0 = time.monotonic()

    def add(self, n: int) -> None:
        """Revise the total: ``n`` more units now known to be coming."""
        self.total += int(n)

    def _facts(self) -> dict:
        facts = {"elapsed_seconds": round(time.monotonic() - self._t0, 2)}
        if self.deadline is not None:
            remaining = self.deadline.remaining
            if remaining != float("inf"):
                facts["remaining_seconds"] = round(remaining, 2)
        return facts

    def start(self, stage: str, **data) -> None:
        if self.stream is not None:
            self.stream.emit("stage_start", stage=stage, index=self.done + 1,
                             n_stages=self.total, **self._facts(), **data)

    def end(self, stage: str, **data) -> None:
        self.done += 1
        if self.stream is not None:
            self.stream.emit("stage_end", stage=stage, index=self.done,
                             n_stages=self.total, **self._facts(), **data)


#: Cells a just-finished (engine × system) unit streams as provisional.  Three:
#: enough to show a search is converging on something, few enough that a
#: 21-unit run stays a readable log.
PROVISIONAL_STREAM_TOP = 3


def provisional_payload(cands: Sequence[EngineCandidate]) -> list[dict]:
    """The few cells a just-finished search unit streams (WP-1042).

    Deliberately **without** a confidence field, and each entry labelled
    ``provisional``: rank comes from Borda over the FoM panel *after* the
    cross-engine merge, dedup, the Bravais screen and the gate, and a freshly
    found engine candidate has been through none of those.  A consumer may
    show these; it must not order a shortlist by them.  A **completed**
    system's candidates stream graded instead — the per-system consensus
    snapshot in :func:`~rietx.indexing.workflow.index_pattern`, which uses
    the WP-1043 evidence shape.
    """
    top = sorted(cands, key=lambda c: (-c.n_indexed, c.volume))
    return [{"cell": [round(float(v), 6) for v in c.cell],
             "system": c.system, "centring": c.centring,
             "n_indexed": int(c.n_indexed),
             "volume": round(float(c.volume), 2), "provisional": True}
            for c in top[:PROVISIONAL_STREAM_TOP]]


# ----------------------------------------------------------------------
# The crash guard
# ----------------------------------------------------------------------
def predicted_reflection_count(cell: Sequence[float], wavelength: float,
                               two_theta_max: float) -> int:
    """How many hkl ``generate_reflections`` would enumerate for this cell.

    Not an estimate of the *answer* — an exact count of the integer box that
    function allocates: ``hmax = floor(a/d_min) + 1`` per axis over ±hmax, so
    ``(2h+1)(2k+1)(2l+1)``.  Reproducing the generator's own arithmetic is the
    point: a guard computed a different way would drift from the thing it guards
    (``tests/test_indexing_engines.py`` pins the two together).
    """
    d_min = wavelength / (2.0 * np.sin(np.radians(max(two_theta_max, 1e-6) / 2.0)))
    n = 1.0
    for axis in tuple(cell)[:3]:
        n *= 2.0 * (np.floor(float(axis) / d_min) + 1.0) + 1.0
        if n > 1e18:                      # saturate rather than overflow int64
            return int(1e18)
    return int(n)


def reflection_ceiling_ok(cell: Sequence[float], wavelength: float,
                          two_theta_max: float, *,
                          ceiling: int = MAX_PREDICTED_REFLECTIONS) -> bool:
    """Is this cell safe to hand to ``generate_reflections``?

    Call it **before** every such call that a search reached: the alternative,
    measured, is a 1.6 PiB allocation request from a cell that ran away.
    """
    return predicted_reflection_count(cell, wavelength, two_theta_max) <= ceiling


# ----------------------------------------------------------------------
# Shared scoring / assignment
# ----------------------------------------------------------------------
def assign_lines(q_obs: np.ndarray, sigma: np.ndarray, hkl: np.ndarray,
                 af: np.ndarray, *, k_sigma: float = MATCH_SIGMA,
                 design: np.ndarray | None = None,
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Give each observed line the hkl whose Q is nearest, within k·σ.

    Returns ``(line_index, hkl_assigned)`` over the lines that matched.  The
    window is per line, which is the whole contract ``schemas/indexing.py``
    establishes: a strong sharp line and a weak shoulder are not held to the same
    tolerance.

    ``design`` is ``design_matrix(hkl)`` when the caller already has it — a
    search calls this once per accepted cell over the same trial set, and
    rebuilding the (N, 6) matrix each time is the difference between a matvec and
    a matrix build in the engine's warm path.
    """
    dm = design_matrix(hkl) if design is None else design
    q_pred = dm @ np.asarray(af, dtype=np.float64)
    # Drop predictions outside the observed Q range **before** matching.  The
    # trial set is sized for the whole search domain, so on any one cell most of
    # it is far out of range, and ``match_lines`` costs an (observed × predicted)
    # matrix: measured on an orthorhombic search, filtering first took a rejected
    # leaf from ~30 ms to well under one, and leaf rejection was 90 % of the run.
    window = k_sigma * float(np.max(sigma)) if len(sigma) else 0.0
    inside = ((q_pred >= float(np.min(q_obs)) - window)
              & (q_pred <= float(np.max(q_obs)) + window))
    q_pred, hkl_in = q_pred[inside], np.asarray(hkl)[inside]
    if not len(q_pred):
        return np.zeros(0, dtype=np.int64), np.zeros((0, 3), dtype=np.int64)
    order = np.argsort(q_pred)
    idx, _ = match_lines(q_obs, sigma, q_pred[order], k_sigma=k_sigma)
    hit = idx >= 0
    return np.flatnonzero(hit), hkl_in[order][idx[hit]]


def search_line_order(peaks: PeakList, spec: SearchSpec) -> np.ndarray:
    """Indices of the observed lines a search is **driven** by: the strongest
    ``n_search_lines`` of them, returned in Q order.

    One function rather than the slice each engine used to open-code, because
    "which lines drive the search" has to mean the same thing in both or their
    agreement stops being evidence (the reason :class:`SearchSpec` is one object).
    Scoring is unaffected and stays over the whole usable list — the
    enumerate-liberally / sort-conservatively split :data:`DEFAULT_SEARCH_LINES`
    states.

    **The count was never the defect; the rank was** (WP-1039).  Taking the first
    N lines *in 2θ order* assumes the lowest-angle components are the phase's
    strongest reflections — true of a lab pattern that opens after its first
    Bragg peak, false of anything that opens on background.  Measured on
    ``11BM_NAC.fxye``, which starts at 0.76° 2θ: of the first twenty lines in 2θ
    order the true cell explains **six**, against 268 of the whole 285.  The
    fourteen others are low-angle components at 0.1–0.6 % of the strongest line's
    intensity carrying a fitted σ(2θ) two orders above their real neighbours'.
    Raising N does not reach past them — 32 of 48 at N = 48, and paid for at
    whatever the enumeration actually scales as (Conograph's own N_peak⁴ is
    hedged twice and defers to supporting information; see
    :data:`DEFAULT_SEARCH_LINES`).  Ranking by intensity takes the same twenty
    lines to **18** of 20, and within the :data:`SEARCH_POOL_MULTIPLE` bound that
    keeps the cost sane — unbounded it is 20 of 20, which is not worth what it
    costs; that trade is measured in the constant's own docstring.

    Ties fall back to Q order, and that is not a detail.  A
    :meth:`PeakList.from_positions` list has no measured intensities and every
    line comes back weight 1, so a bare position list — which is the whole
    bethanechol benchmark — selects **exactly** as it did before this rule
    existed.  An assumed intensity may no more reorder a search than an assumed σ
    may refuse one.

    **Do not propagate this rule into** ``fom.py``.  M₂₀'s "first twenty" is de
    Wolff's *definition* — the figure is N_poss counted up to the twentieth
    observed line in Q order — so re-ranking there would not tune a figure of
    merit, it would compute a different one under the same name.
    """
    q = peaks.q()
    n = min(spec.n_search_lines, len(q))
    pool = np.argsort(q)[:min(SEARCH_POOL_MULTIPLE * n, len(q))]
    order = pool[np.lexsort((q[pool], -peaks.intensity()[pool]))[:n]]
    return order[np.argsort(q[order])]


def effective_shift_allowance(spec: SearchSpec,
                              quality=None) -> tuple[float, bool]:
    """The systematic allowance to use, and whether it was **assumed**.

    Three cases, in priority order: the caller declared one; the data-quality
    report measured one, by either of the two roads
    :data:`~rietx.schemas.indexing.TRUSTED_SHIFT_SOURCES` names — against
    supplied references (``"measured"``), or from harmonic reflection pairs with
    no reference at all (``"reflection_pairs"``, WP-1038, which is what made this
    branch reachable on real data); or neither, in which case
    :data:`DEFAULT_UNKNOWN_SHIFT_DEG` is assumed and the second return value says
    so.  An assumed precision must never be reported as a measured one — the same
    rule ``PeakList.from_positions`` follows.

    **What it reads from the screen is ``allowance_deg``, not ``sigma_sys_deg``,
    and that was a bug for as long as this branch was unreachable.**  ``sigma_sys``
    is the scatter the winning template *leaves*; the window has to span the shift
    itself, because matching happens against uncorrected positions.  Measured on
    SRM 660c the two are 0.0078° and 0.037°: declaring the smaller finds
    **nothing**, declaring the larger recovers the certificate.  The
    ``lab6_calibrated`` fixture computed the right quantity by hand for exactly
    this reason; the screen now computes it once.  The same collision lived in
    the *declared* field's name until WP-1045 — ``SearchSpec.sigma_sys_deg``
    invited exactly the wrong number — so both this function and that field now
    say "allowance", and the only ``sigma_sys_deg`` left is the screen's scatter.
    """
    if spec.shift_allowance_deg > 0.0:
        return float(spec.shift_allowance_deg), False
    if (quality is not None and quality.shift is not None
            and quality.shift.source in TRUSTED_SHIFT_SOURCES
            and quality.shift.allowance_deg > 0.0):
        return float(quality.shift.allowance_deg), False
    return DEFAULT_UNKNOWN_SHIFT_DEG, True


#: Search ceiling (Å³) when neither the caller nor a data-quality report
#: supplies one — deliberately generous, because a ceiling with no evidence
#: behind it must only ever exclude the absurd.
DEFAULT_VOLUME_CEILING = 8000.0


def search_volume_ceiling(spec: SearchSpec, quality, system: str) -> float:
    """The volume a *search* prunes at for one system — the one authority.

    A caller's declared ``max_volume`` is returned verbatim: explicit
    narrowing is the caller's own act (the no-silent-caps rule), and it is
    already recorded in ``spec_notes``.  The fallback is the data-quality
    report's Smith envelope **with**
    :data:`~rietx.indexing.quality.VOLUME_ENVELOPE_SLACK`, because the
    envelope is a least-squares *mean line*, not a bound: deviations run 29 %
    low on Smith's own calibration set and low is the ordinary case (missing
    weak lines produce it — with p the fraction of possible lines detected the
    raw line stands at 1.40·p × truth, excluding the true cell below
    p = 0.71).  Until WP-1045 all four engine call sites fed the raw envelope,
    so the slack existed only where consensus *flags* a found candidate — a
    calibrated exclusion of the right answer, invisible to the complete-list
    guard test (blind at p = 1).
    """
    if quality is not None and system in quality.volume_envelope:
        from .quality import VOLUME_ENVELOPE_SLACK

        fallback = VOLUME_ENVELOPE_SLACK * float(quality.volume_envelope[system])
    else:
        fallback = DEFAULT_VOLUME_CEILING
    return spec.volume_limit(system, fallback)


def shift_allowance_diagnostic(allowance_deg: float) -> Diagnostic:
    """``INDEX_SHIFT_ALLOWANCE`` — the search widened its own tolerance, and by how
    much.  Reported because it is the difference between a cell and no cell, and
    because it biases the cell it finds."""
    return Diagnostic(
        level="info", code="INDEX_SHIFT_ALLOWANCE",
        message=(f"no systematic 2θ shift has been measured, so {allowance_deg:.3f}° "
                 "was added in quadrature to every line's fitted σ.  Measured on "
                 "a certified pattern, the fitted σ alone is ~11× too tight: the "
                 "true cell indexed no lines at all and the search returned "
                 "nothing"),
        where=[f"σ_sys = {allowance_deg:.3f}° 2θ (assumed)"],
        suggestion=("the cell a widened search finds absorbs the shift, so refine "
                    "the winner with a shift template "
                    "(refine_candidate(..., shift_template=...), or pass "
                    "shift_template in the SearchSpec) and quote *that* cell; "
                    "supply reference positions to assess_peak_list if you have "
                    "an internal standard"))


def shift_from_pairs_diagnostic(shift) -> Diagnostic:
    """``INDEX_SHIFT_FROM_PAIRS`` — a systematic 2θ shift was **measured** from the
    peak list alone, and this is what it says.

    The counterpart of ``INDEX_SHIFT_ALLOWANCE``: that one fires when the window
    was widened by an assumed number, this one when it was widened by a measured
    one.  Both are reported for the same reason — the window size is the
    difference between a cell and no cell — but the reader's next action differs,
    which is why they are separate codes rather than one code with a flag.
    """
    p = shift.pairs
    named = ("; the cause is not named: "
             + ("no template was refuted" if not p.refuted_templates
                else f"{', '.join(p.refuted_templates)} refuted, "
                     "the rest indistinguishable over this range"))
    return Diagnostic(
        level="info", code="INDEX_SHIFT_FROM_PAIRS",
        message=(f"a systematic shift of {shift.allowance_deg:.4f}° 2θ was "
                 f"measured from {p.n_clustered} harmonic reflection pairs "
                 f"agreeing to {p.scatter_deg:.4f}° (of {p.n_pairs} admitted, "
                 f"z = {p.z:.1f} against {p.null_replicates} structureless "
                 f"replicates, p = {p.p_value:.3f}) — no reference positions "
                 "were needed" + named),
        where=[f"allowance = {shift.allowance_deg:.4f}° 2θ (measured)",
               f"best template = {shift.best}"],
        suggestion=("this is the window the search used; if the cause matters, "
                    "extending the 2θ range is what separates a zero-point error "
                    "from a specimen displacement — they are collinear over a "
                    "short range and no amount of counting can attribute them"))


def refine_with_shift(fit, spec: SearchSpec, system: str, q_all: np.ndarray,
                      sigma: np.ndarray, two_theta: np.ndarray,
                      wavelength: float, line_index: np.ndarray,
                      hkl: np.ndarray):
    """Re-fit an accepted candidate with a shift column, if one was asked for.

    **This is what stops a widened search from reporting a biased cell.**  The
    search has to open its tolerance to cover an unmeasured systematic
    (:data:`DEFAULT_UNKNOWN_SHIFT_DEG`), and a cell fitted inside that window
    absorbs the shift: measured on the qarr corundum pattern, the trial-and-error
    engine returned a = 4.7659 Å against a certified 4.7593 (+1400 ppm) with the
    shift left in.  Fitting the template *after* the candidate survives is the order
    WP-1020 prescribes — a shift is only identifiable against reference positions,
    and a candidate cell is what supplies them.

    **A declared template is the caller's physics, not a hypothesis for a fit
    statistic to adjudicate**, so the only thing that can refuse it is
    identifiability.  Until WP-1026 this kept the shifted fit only when χ²_red
    improved, and that rule is backwards in a way that is easy to state and was
    measured: the correction always costs a degree of freedom, while a cell that has
    *already absorbed* the shift into its axes cannot gain much χ² from it — so the
    test refused the correction precisely on the candidates that needed it and
    accepted it on the ones that needed it least.  Traced on the corundum run,
    ``refine_with_shift`` was called 17 times and declined 9, the ranked-first
    candidate among them (χ²_red 1.5829 → 1.5945).  It is v0.5's method result and
    WP-1026's own ΔBIC lesson one rank up: a declared correction ships with a record
    of what it changed, never with a fit statistic as its gatekeeper —
    ``Geometry.mu_t`` is the precedent.

    So the fit is returned shifted unless there is no shift to be had: no template
    asked for, the solve failed numerically, or the assigned lines cannot support
    one more parameter.  ``shift_coefficient`` and ``shift_esd`` travel on the
    candidate, so a shift consistent with zero is *reported* as such rather than
    being silently declined.
    """
    if spec.shift_template is None:
        return fit
    # one column more than the metric, and one row spare to fit it with: below
    # that the shift is exactly determined by the lines and means nothing
    if len(line_index) < len(metric_basis(system)) + 2:
        return fit
    try:
        shifted = refine_candidate(
            q_all[line_index], sigma[line_index], hkl, system=system,
            two_theta=two_theta[line_index], wavelength=wavelength,
            shift_template=spec.shift_template)
    except (ValueError, np.linalg.LinAlgError):
        return fit
    if not (np.all(np.isfinite(shifted.cell)) and shifted.volume > 0.0
            and np.isfinite(shifted.shift_coefficient)):
        return fit
    return shifted


def indexes_the_search_lines(line_index: np.ndarray, search: np.ndarray,
                             n_unindexed: int) -> bool:
    """Did this candidate index the lines the search was **driven by**?

    The acceptance bar has to be "all but ``n_unindexed`` of the *search* lines",
    not "at least that many lines somewhere in the pattern".  The two are wildly
    different once a pattern has more lines than the search uses: measured on a
    75-line monoclinic list, the second reading kept **17 607** candidates, because
    a 4-parameter metric indexes 18 of 75 lines by coincidence without difficulty.
    The first reading is also the honest one — those are the lines whose failure
    the tolerated-unindexed count was chosen against.
    """
    if not len(search):
        return True
    hit = int(np.count_nonzero(np.isin(search, line_index)))
    return hit >= len(search) - n_unindexed


def match_window(peaks: PeakList, spec=None, quality=None) -> np.ndarray:
    """The σ(Q) the *search* matched with — the one authority, three callers.

    ``q_esd`` is what the measurement resolves and this is what a line was
    allowed to move by, and the two differ by the shift allowance
    (:func:`effective_shift_allowance`).  Ranking, or drawing, in the tighter one
    judges candidates by a criterion they were never selected under — the rule
    ``fom.fom_panel`` states for ``q_match``, now stated once here so
    :mod:`~rietx.indexing.consensus` and :mod:`rietx.viz.indexing` cannot
    derive it two ways.
    """
    from .qspace import sigma_effective

    allowance, _assumed = effective_shift_allowance(spec or SearchSpec(),
                                                    quality)
    return sigma_effective(peaks.q_esd(), peaks.two_theta(), peaks.wavelength,
                           allowance)


def scored_positions(peaks: PeakList, fit) -> tuple[np.ndarray, np.ndarray]:
    """(Q, 2θ) a candidate is **scored against** — corrected by its own shift.

    A candidate that carries a fitted shift template claims that the lines
    *corrected* by s·t(θ) are the ones its lattice explains, so scoring it against
    the raw positions marks it down for the very correction it declared.  Measured
    on the certified corundum pattern: with the shift applied to every candidate
    and the panel left on raw positions, the certified lattice — fitted shift
    −0.0606°, the largest in the list — fell out of the top six while candidates
    whose fitted shift was under 0.03° were untouched, i.e. the panel was ranking
    on *how little a candidate had been corrected*.

    Refining one shift per candidate is the field's practice (DICVOL, ITO and
    TREOR all refine a zero-point per trial cell) and it carries the blind spot
    ``f_n`` already states: a refined shift can manufacture a large F_N.  What it
    must not also do is score two candidates against two different claims.
    """
    tt = peaks.two_theta()
    template = getattr(fit, "shift_template", None)
    coeff = float(getattr(fit, "shift_coefficient", 0.0) or 0.0)
    if template is None or coeff == 0.0:
        return peaks.q(), tt
    from ..schemas.indexing import q_of_two_theta
    from .quality import shift_template_basis
    basis = shift_template_basis(tt)
    if template not in basis:
        return peaks.q(), tt
    corrected = tt - coeff * basis[template]
    if not np.all(np.isfinite(corrected)) or np.any(corrected <= 0.0):
        return peaks.q(), tt
    return q_of_two_theta(corrected, peaks.wavelength), corrected


def to_cell_candidate(cand: EngineCandidate, peaks: PeakList, *,
                      k_sigma: float = MATCH_SIGMA, n_unindexed: int = 0,
                      diagnostics: Sequence[Diagnostic] = (),
                      q_match: np.ndarray | None = None,
                      ) -> CellCandidate:
    """Score a candidate with the whole FoM panel and pack it for reporting.

    The panel — never a member — is what a candidate is ranked on: measured on
    this repo's own data, ``indexed_fraction`` alone put a 390-line wrong phase
    above the truth (``fom.py``'s module docstring).  This function is where an
    engine's internal answer becomes a comparable one, so it is also where the
    reflection ceiling is checked one last time: ``fom_panel`` enumerates.
    """
    fit = cand.fit
    tt_esd = peaks.two_theta_esd()
    q_esd = peaks.q_esd()
    q, tt = scored_positions(peaks, fit)
    inten = peaks.intensity()
    tt_max = float(np.max(tt)) if len(tt) else 90.0
    panel = cand.fom
    if not panel and reflection_ceiling_ok(fit.cell, peaks.wavelength, tt_max):
        panel = fom_panel(q, q_esd, inten, tt, tt_esd, fit.cell, cand.system,
                          cand.centring, peaks.wavelength, k_sigma=k_sigma,
                          n_unindexed=n_unindexed, q_match=q_match)
    esd = np.asarray(fit.cell_esd, dtype=np.float64)
    vol_esd = _volume_esd(fit)
    return CellCandidate(
        cell=tuple(float(v) for v in fit.cell),
        cell_esd=tuple(float(v) for v in esd),
        system=cand.system, centring=cand.centring,
        lattice_group=lattice_group(cand.system, cand.centring),
        volume=float(fit.volume), volume_esd=vol_esd,
        af=tuple(float(v) for v in fit.af),
        n_indexed=cand.n_indexed, n_lines=cand.n_lines,
        chi2_red=float(fit.chi2_red),
        shift_template=fit.shift_template,
        shift_coefficient=float(fit.shift_coefficient),
        shift_esd=float(fit.shift_esd),
        fom=panel, found_by=list(cand.found_by) or [cand.engine],
        diagnostics=list(diagnostics))


def _volume_esd(fit: CandidateFit) -> float:
    """σ(V) by the delta method through ∂V/∂(A..F).

    V = 1/√det G*, so ∂V/∂G* = −(V/2)·(G*)⁻ᵀ by Jacobi's formula — analytic for
    the same reason ``cell_jacobian`` is: the number is used to decide whether two
    candidates are the same lattice, not merely to print.
    """
    from .qspace import gstar_from_af

    gstar = gstar_from_af(fit.af)
    det = float(np.linalg.det(gstar))
    if det <= 0.0:
        return 0.0
    vol = det ** -0.5
    inv = np.linalg.inv(gstar)
    # d(det)/dG*_ij = det·inv_ji; A..F carry a factor 2 on the off-diagonals, so
    # the chain to (A..F) divides by that factor and counts the symmetric pair
    grad = np.array([
        -0.5 * vol * inv[0, 0], -0.5 * vol * inv[1, 1], -0.5 * vol * inv[2, 2],
        -0.5 * vol * inv[1, 2], -0.5 * vol * inv[0, 2], -0.5 * vol * inv[0, 1]])
    return float(np.sqrt(max(grad @ np.asarray(fit.cov_af) @ grad, 0.0)))


#: Relative grid a solved metric is hashed on before it is refined.  A real cell is
#: reached by many different base sets (``trial_error``) and many different random
#: starts (``svd``), and re-fitting each of them is the cost this pre-filter avoids.
SAME_SOLUTION_RTOL = 1e-3


def solution_key(af: np.ndarray, centring: str = "") -> tuple[object, ...]:
    """The **within-engine** dedup key of a solved metric: cheap, and lossless in
    the two ways an engine's ``seen`` set can silently discard a real hypothesis.

    Both are measured defects rather than precautions, and both were found in
    ``svd`` (WP-1040) before being fixed here for ``trial_error`` too (WP-1041) —
    which is why the key lives in this module, the one place engines share.

    *One: it is scale-**dependent**.*  The obvious form ``round(af / (max|af| ·
    rtol))`` is scale invariant, and for a one-dimensional metric that is fatal
    rather than merely lossy: every cubic cell is ``(A, A, A, 0, 0, 0)``, so
    dividing by ``max|af|`` maps all of them to one key and the first candidate
    reached blocks every later one.  Measured on a clean synthetic cubic pattern:
    **0 candidates** from 72 starts that included the truth.  So the quantised
    scale goes into the key too, on a logarithmic grid of the same relative width.

    *Two: it carries the centring.*  A ``seen`` set spanning the centring loop with
    a centring-free key lets the first centring tried claim a metric while every
    later one is silently discarded — and ``P`` is first in ``centrings_for``.
    Measured on 11-BM NAC: the answer came back cubic **P** with 92
    predicted-and-absent reflections in place of the cubic **I** description of
    identical axes, which has none.  It is also what ``dedup_groups`` already says
    one rank up — two centrings of one metric are two lattices, predicting
    different numbers of lines, and the figures of merit exist to choose between
    them.  Passing ``centring=""`` is the deliberate opt-out, for a caller whose
    loop does not span centrings at all.

    This is a *pre-filter*, never the authority on whether two candidates are the
    same lattice: that is ``dedup_groups``' χ² test on the Niggli-reduced metric,
    which knows about settings and covariance and costs accordingly.
    """
    a = np.asarray(af, dtype=np.float64)
    scale = float(np.max(np.abs(a)))
    if not np.isfinite(scale) or scale <= 0.0:
        return (centring, *(0,) * (len(a) + 1))
    decade = int(np.round(np.log(scale) / np.log1p(SAME_SOLUTION_RTOL)))
    return (centring, decade,
            *np.round(a / (scale * SAME_SOLUTION_RTOL)).astype(np.int64))


def merge_engine_units(units: Sequence[EngineResult]) -> EngineResult:
    """Fold one engine's per-system unit results into the single
    :class:`EngineResult` consensus reads (WP-1042's system-major scheduler).

    The scheduler runs (engine × system) units — ``spec.systems`` restricted to
    one system per call — so a binding deadline sacrifices trailing *systems*
    for every engine equally instead of whole engines.  Consensus, and
    everything downstream of it, still wants one answer per engine, and this is
    that fold.  Everything is a union of disjoint per-system facts except the
    engine-level stats: ``candidates.raw`` is **summed** (each unit counted its
    own harvest), while ``shift_allowance_deg`` and ``seed`` are identical across
    units by construction (one spec, one quality report), so last-write-wins is
    exact for them.  Diagnostics dedup on (code, message) — every unit repeats
    the engine-level ones (``INDEX_SHIFT_ALLOWANCE``) in identical words, and N
    copies of one statement would read as N problems (the same rule
    ``consensus`` applies across engines).
    """
    if not units:
        raise ValueError("merge_engine_units needs at least one unit result")
    engines = {u.engine for u in units}
    if len(engines) > 1:
        raise ValueError(
            f"one merge per engine: got units from {sorted(engines)}")
    out = EngineResult(engine=units[0].engine)
    raw = 0.0
    for unit in units:
        out.candidates.extend(unit.candidates)
        out.systems_searched += tuple(s for s in unit.systems_searched
                                      if s not in out.systems_searched)
        out.search_complete.update(unit.search_complete)
        for key, value in unit.stats.items():
            if key == "candidates.raw":
                raw += float(value)
            else:
                out.stats[key] = value
        for diag in unit.diagnostics:
            if not any(d.code == diag.code and d.message == diag.message
                       for d in out.diagnostics):
                out.diagnostics.append(diag)
    out.stats["candidates.raw"] = raw
    return out


def dedup_groups(cands: Sequence[EngineCandidate],
                 ) -> list[list[EngineCandidate]]:
    """Group candidates that are the same lattice, best-fitting member first.

    WP-1020's χ² equality on the **Niggli-reduced** A..F, so a setting change is
    equality rather than an ambiguity — but keyed within a centring, because the
    same metric with two different centrings is two different *lattices* (one
    predicts half the lines of the other) and merging them would silently drop a
    hypothesis the figures of merit are there to choose between.

    The *groups*, not just the survivors, because WP-1024's consensus needs to
    know **which engines** produced one lattice: agreement is the confidence, so
    the membership is the answer and not a by-product.  :func:`dedup_candidates`
    is this function's first column.
    """
    from .reduce import equal_reduced, reduced_af

    #: reduce **once** per candidate, not once per comparison
    prepared: list[tuple[EngineCandidate, np.ndarray, float]] = []
    for cand in sorted(cands, key=lambda c: (-c.n_indexed, c.fit.chi2_red)):
        try:
            red = reduced_af(cand.fit.af)
        except (ValueError, np.linalg.LinAlgError, RuntimeError):
            continue
        prepared.append((cand, red, _reduced_volume(red)))

    kept: list[tuple[list[EngineCandidate], np.ndarray, float]] = []
    for cand, red, volume in prepared:
        for group, other_red, other_volume in kept:
            # volume gate first: two lattices whose reduced volumes differ by more
            # than a per-cent cannot pass a χ² test on their metrics, and this is
            # what keeps the pass from being N² pinv solves as well as N² reductions
            if abs(volume - other_volume) > DEDUP_VOLUME_RTOL * max(volume,
                                                                    other_volume):
                continue
            other = group[0]
            if other.centring != cand.centring or other.system != cand.system:
                continue
            try:
                same, _chi2 = equal_reduced(red, other_red,
                                            cov_a=cand.fit.cov_af,
                                            cov_b=other.fit.cov_af)
            except (ValueError, np.linalg.LinAlgError):
                same = False
            if same:
                group.append(cand)
                break
        else:
            kept.append(([cand], red, volume))
    return [group for group, _red, _vol in kept]


def dedup_candidates(cands: Sequence[EngineCandidate],
                     ) -> list[EngineCandidate]:
    """The best-fitting member of each distinct lattice — :func:`dedup_groups`
    with the membership dropped."""
    return [group[0] for group in dedup_groups(cands)]


def _reduced_volume(red: np.ndarray) -> float:
    from .qspace import gstar_from_af
    det = float(np.linalg.det(gstar_from_af(red)))
    return det ** -0.5 if det > 0.0 else float("inf")


def rank_candidates(cands: Sequence[EngineCandidate], peaks: PeakList, *,
                    k_sigma: float = MATCH_SIGMA,
                    n_unindexed: int = 0,
                    max_candidates: int = DEFAULT_MAX_CANDIDATES,
                    shortlist: int | None = 4,
                    q_match: np.ndarray | None = None,
                    ) -> list[EngineCandidate]:
    """Dedup, score with the FoM panel, and rank by **agreement, then** Borda.

    **Ranking happens here rather than in each engine, and it is not on a
    member.**  ``indexed_fraction`` alone put a 390-line wrong phase above the
    truth on this repo's own data (``fom.py``); on synthetic data the same shape
    appears as supercells, which index every observed line *exactly* and so tie
    the truth on every forward-looking figure — they lose only on
    ``predicted_seen_fraction``, and only a panel sees that.

    **Whether two engines found a lattice outranks every figure of merit**
    (WP-1046, :func:`corroborated`), and this is the package's own doctrine
    applied to the order rather than only to the verdict: ``grade`` floors a
    candidate below :data:`MIN_AGREEMENT` finders at ``low`` before a single
    caveat is consulted, so a list ranked on the panel alone routinely put
    candidates the gate refuses to promote above the one it could.  Measured:
    on the GSAS-II fluorapatite pattern over all seven systems, the six
    candidates above the truth were ``trial_error``-only while the truth was
    found by all three engines; on bethanechol sets F and Db the candidate
    displacing the truth was ``svd``-only.  It is not a panel member and not a
    weighting — WP-1041 measured and refuted the aggregates, and every one of
    those refutations stands.  Two properties earn it the primary position:
    corroboration does not depend on which *other* candidates exist, so unlike
    Borda it cannot be moved by the size of the pool (the whole subject of
    WP-1046); and it is **inert** inside an engine, where every candidate
    carries the same ``found_by`` and the order is the panel's exactly as
    before.  It is deliberately **binary** — a third finder buys nothing, and
    :func:`corroborated` carries the measurement that says why.

    The panel costs a reflection enumeration per candidate, so a cheap pre-rank
    picks the shortlist: **most indexed lines first, then smallest volume**. That
    order is conservative in the direction that matters — a supercell can tie the
    truth on lines indexed but never beat it, and it is larger by construction,
    so the truth cannot be shortlisted out by its own supercell.

    ``shortlist=None`` scores **every** deduped candidate, and that is what
    :func:`~rietx.indexing.consensus.consensus` passes (WP-1046).  The
    pre-rank exists to bound an engine's *unbounded* harvest — a monoclinic
    trial-and-error unit measured 1890 raw candidates — and consensus has no
    such harvest: what reaches it is already bounded by
    :meth:`SearchSpec.engine_pool` per unit.  Leaving the multiplier in place
    there tied the panel's reach to the number the answer *reports*, which is
    the defect this WP is about, one layer up and in a cheaper disguise: at
    ``max_candidates = 12`` only 48 of a 260-lattice merge were scored at all,
    and on bethanechol set F the published lattice was not among them.  Its
    conservatism does not transfer either — the pre-rank is safe against a
    candidate's *own* supercell, not against a hundred unrelated low-symmetry
    cells that index more lines than the truth does.

    ``q_match`` is the σ(Q) the *search* matched with — pass the same array the
    engine assigned lines with, or the panel judges these candidates by a window
    they were never selected under (:func:`~rietx.indexing.fom.fom_panel`).
    """
    kept = dedup_candidates(cands)
    # agreement leads the cheap pre-rank too: a candidate cut here never reaches
    # the panel, so applying the key only to the final sort would leave the same
    # truncation deciding an order it is not entitled to decide
    kept.sort(key=lambda c: (not corroborated(c), -c.n_indexed, c.volume))
    if shortlist is not None:
        kept = kept[:max(shortlist * max_candidates, max_candidates)]
    if not kept:
        return []
    for cand in kept:
        cand.fom = _panel_for(cand, peaks, k_sigma, n_unindexed, q_match)
    scored = [c for c in kept if c.fom]
    unscored = [c for c in kept if not c.fom]
    if scored:
        from .fom import borda_scores
        scores = borda_scores([c.fom for c in scored])
        scored = [c for _a, _s, _i, c in sorted(
            ((not corroborated(c), -float(s), i, c)
             for i, (s, c) in enumerate(zip(scores, scored))))]
    return (scored + unscored)[:max_candidates]


def corroborated(cand: EngineCandidate) -> bool:
    """Do at least :data:`MIN_AGREEMENT` engines stand behind this lattice?

    :func:`rank_candidates`'s first key, and **binary on purpose** (WP-1046).
    The count itself is not a comparable quantity across crystal systems: the
    engines' reach differs by system, so three of them meet in a cheap
    orthorhombic domain while only two ever reach an expensive monoclinic one,
    and ranking on the *count* rewards the easy system rather than the better
    answer.  Measured, and it is not subtle — on bethanechol sets Bb, Db, E and
    F in the paper's default mode, an orthorhombic cell found by all three
    engines led every list while the published monoclinic truth, found by two,
    fell to ranks 5, 3, 9 and 8; sets whose truth had been first.

    The one statement that *is* comparable is the one the gate already makes:
    :func:`~rietx.indexing.consensus.grade` floors a candidate below
    :data:`MIN_AGREEMENT` at ``low`` before any caveat is read, everywhere, in
    every system.  So the ranking mirrors exactly that boundary and no more —
    within a tier the panel decides, as it always did.
    """
    return agreement(cand) >= MIN_AGREEMENT


def agreement(cand: EngineCandidate) -> int:
    """Distinct **engines** behind this lattice.

    ``found_by`` is empty until :func:`~rietx.indexing.consensus.consensus`
    merges, and an unmerged candidate stands on its own engine, so this is 1
    everywhere inside a search: the key is **inert** there by construction
    rather than by a caller remembering to switch it off.

    :data:`PRIOR_FINDER` is **excluded**, and that is WP-1045's rule kept
    structural rather than re-argued: a prior steers and never gates, so a
    stated cell an engine also found must not outrank a lattice two engines
    reached — "a wrong prior changes no rank" has to survive the ranking key
    changing under it.
    """
    return len({f for f in cand.found_by if f != PRIOR_FINDER}) or 1


def _panel_for(cand: EngineCandidate, peaks: PeakList, k_sigma: float,
               n_unindexed: int = 0, q_match: np.ndarray | None = None):
    tt_esd = peaks.two_theta_esd()
    q, tt = scored_positions(peaks, cand.fit)
    tt_max = float(np.max(tt)) if len(tt) else 90.0
    if not reflection_ceiling_ok(cand.cell, peaks.wavelength, tt_max):
        return []
    try:
        return fom_panel(q, peaks.q_esd(), peaks.intensity(), tt, tt_esd,
                         cand.cell, cand.system, cand.centring, peaks.wavelength,
                         k_sigma=k_sigma, n_unindexed=n_unindexed,
                         q_match=q_match)
    except (ValueError, RuntimeError):
        return []


def incomplete_diagnostic(engine: str, systems: Sequence[str],
                          seconds: float,
                          capped: Sequence[str] = ()) -> Diagnostic:
    """``INDEX_SEARCH_INCOMPLETE`` — a searched domain was not exhausted.

    Its whole content is that a *negative* result from these systems is not
    evidence: an exhaustive engine's silence means "no such cell" only when it
    finished.

    **Two causes, and only one of them is time** (WP-1449).  ``systems`` were
    stopped by the clock; ``capped`` outgrew a size cap on the grid or the
    trial set, where a larger ``budget_seconds`` changes nothing.  Measured on
    11-BM NAC, the dichotomy explored 0 boxes in 0.26 s and this message said it
    had not finished within 300 s.  So the engines classify each unit by
    whether its budget had expired when it returned.
    """
    parts = []
    if systems:
        parts.append(f"did not finish {', '.join(systems)} within {seconds:g} s "
                     "per system")
    if capped:
        parts.append(f"outgrew a size cap on {', '.join(capped)}")
    everything = [*systems, *capped]
    dof = ", ".join(f"{s} {METRIC_DOF[s]}" for s in everything if s in METRIC_DOF)
    if systems:
        advice = ("raise budget_seconds, or narrow the search — a smaller "
                  "max_volume or a shorter d-axis range costs exponentially "
                  "less than more time buys.")
    else:
        advice = ("narrow the search — a smaller max_volume, a shorter d-axis "
                  "range or a peak list ending at a lower angle shrinks what "
                  "the cap counts; more time changes nothing.")
    return Diagnostic(
        level="warning", code="INDEX_SEARCH_INCOMPLETE",
        message=(f"the {engine} search {' and '.join(parts)}, so finding no "
                 "cell there is not evidence that none exists"),
        where=everything,
        suggestion=(f"{advice}  Cost grows with the metric degrees of freedom "
                    f"({dof})"))


def candidates_truncated_diagnostic(n_merged: int, n_reported: int,
                                    pool_capped: Sequence[str] = (),
                                    pool: int = 0) -> Diagnostic:
    """``INDEX_CANDIDATES_TRUNCATED`` — what the reported list left out.

    Two clauses, and they are different kinds of statement.  The **merge**
    truncation is exact: consensus ranked ``n_merged`` distinct lattices and
    reports the first ``n_reported``, so the difference is a count.  The
    **pool** clause is a flag, not a count: a unit that returned a full
    :meth:`SearchSpec.engine_pool` may have had more distinct lattices behind
    it, and how many is not known without deduplicating a harvest the search
    already discarded — so it names the (engine, system) units it happened to
    and claims nothing about the size.  Under the system-major scheduler a unit
    *is* one system, so that label is exact on the path ``index_pattern`` takes;
    a direct multi-system engine call truncates one pooled harvest and names
    every system it searched, because attributing the cut to one of them would
    be a guess.

    Info, not a warning.  A bounded reported list is the design (a Le Bail
    validation is priced per candidate), and this exists because a cap that
    says nothing reads as "everything was considered" — the no-silent-caps rule
    one rank up.  Since WP-1046 the layer that truncates is also the layer
    whose ranking the design calls authoritative; before it, the units
    truncated first and that was the defect this code now reports rather than
    hides.
    """
    parts = []
    if n_merged > n_reported:
        parts.append(f"{n_merged} distinct lattices were merged and the "
                     f"reported list holds the top {n_reported}, so "
                     f"{n_merged - n_reported} ranked below it")
    if pool_capped:
        parts.append(f"{', '.join(pool_capped)} returned a full pool of "
                     f"{pool}, so more may have been found there than were "
                     "handed to the merge")
    return Diagnostic(
        level="info", code="INDEX_CANDIDATES_TRUNCATED",
        message="; ".join(parts) if parts else "nothing was truncated",
        where=list(pool_capped),
        suggestion=("raise max_candidates to report more — it also raises the "
                    "per-unit pool, and it is what prices validation "
                    "(estimate_ceiling), so the cost is the Le Bail fits and "
                    "not the search"))


def single_engine_diagnostic(name: str) -> Diagnostic:
    """``INDEX_SINGLE_ENGINE`` — one engine ran, so ``low`` means something else.

    A **diagnostic, not a caveat**, and the distinction is structural (WP-1042):
    ``grade`` returns ``low`` whenever fewer than two engines stand behind a
    candidate, so every candidate of a one-engine run is ``low`` before any
    caveat is consulted — a *capping* caveat could not explain a floor the
    grade produces itself.  This statement is result-level: it tells the reader
    that ``low`` here means "unconfirmed by construction", not "refuted".
    """
    return Diagnostic(
        level="info", code="INDEX_SINGLE_ENGINE",
        message=(f"only the {name} engine ran, and agreement between "
                 "independent searches is what confidence measures here — so "
                 "every candidate grades low structurally (fewer than two "
                 "finders), which means 'unconfirmed', not 'refuted'"),
        where=[f"engines: {name}"],
        suggestion=("run the default engine set for a gradeable answer; a "
                    "single-engine run is a probe, and its ranking is still "
                    "the panel's"))


def budget_exhausted_diagnostic(total_seconds: float,
                                engines_not_run: Sequence[str],
                                systems_truncated: Sequence[str],
                                systems_not_reached: Sequence[str],
                                candidates_not_validated: int,
                                ceiling_hit: bool = True) -> Diagnostic:
    """``INDEX_BUDGET_EXHAUSTED`` — the declared whole-run ceiling bound.

    Written only when the *clock* stopped the run
    (:meth:`Deadline.cancelled_by_user` is false): a user cancellation is not a
    statement about the budget.  Its whole content is the three-state reading of
    ``systems_searched`` — a system searched to completion said something, a
    truncated one said less, and one never reached said nothing at all — plus
    the candidates whose validation never ran (they read ``not_validated``,
    which is the honest cap, never ``validation_failed``).

    ``ceiling_hit=False`` (WP-1042) is the slice-only case: the whole-run clock
    never expired, but one or more validation fits exhausted the equal slice
    of the remaining clock the ceiling's arithmetic gave them — the ceiling
    still bound the answer, and saying "the run hit its ceiling" would be
    false, so the message says which of the two happened.
    """
    where = []
    if engines_not_run:
        where.append("engines not run: " + ", ".join(engines_not_run))
    if systems_truncated:
        where.append("truncated: " + ", ".join(systems_truncated))
    if systems_not_reached:
        where.append("not reached: " + ", ".join(systems_not_reached))
    if candidates_not_validated:
        where.append(f"{candidates_not_validated} candidate(s) not validated")
    return Diagnostic(
        level="warning", code="INDEX_BUDGET_EXHAUSTED",
        message=((f"the run hit its declared ceiling of {total_seconds:g} s, "
                  "so the answer covers what was reached rather than the "
                  "whole requested search") if ceiling_hit else
                 (f"the declared ceiling of {total_seconds:g} s bound the "
                  "shortlist's validation: one or more fits exhausted their "
                  "slice of the remaining clock and their candidates read "
                  "not_validated")),
        where=where,
        suggestion=("what was reached is still ranked and gated honestly — "
                    "read systems_searched and search_complete before treating "
                    "an absence as evidence.  Raise total_budget_seconds, or "
                    "narrow systems= to where the answer can live, which costs "
                    "exponentially less than more time buys"))


# ----------------------------------------------------------------------
# Search presets (WP-1042)
# ----------------------------------------------------------------------
#: Whole-run ceiling (seconds) the ``quick`` preset fills into
#: ``SearchSpec.total_budget_seconds`` when the caller has not declared one.
#: Chosen from the task-0 re-measure under the system-major scheduler
#: (WP-1042 handover, darwin/arm64 M4, ``[dev,jax,torch]`` venv): graded per-system
#: shortlists stream 0.5-35 s in across the known-cell corpus, so the ceiling
#: is not what makes the default responsive — streaming is — and its job is
#: the other end: bounding the newly searchable short lists (a 15-line list
#: used to hang a GUI click for minutes, and quick-fluorite now finishes
#: whole at ~115 s) and the unbudgeted validation tail.  Measured under this
#: value, the six corpus quick runs land at 115-126 s wall (ceiling +
#: cooperative granularity), the truth's own system completes inside the
#: ceiling on every one, and what a binding ceiling cuts is the trailing
#: low-symmetry systems — loudly (``INDEX_BUDGET_EXHAUSTED``), the documented
#: cost of cheapest-first ordering.  The starvation this used to carry — on
#: the heavier patterns the search consumed the whole ceiling and validation
#: got **no** fits — is why :data:`VALIDATION_RESERVE_FRACTION` exists
#: (WP-1045): the search now stops a reserve early whenever validation is
#: going to run, so the first click's shortlist arrives whole-profile-checked.
QUICK_TOTAL_BUDGET_SECONDS = 120.0
#: The preset ``index_pattern`` resolves when the caller names none.
DEFAULT_SEARCH_PRESET = "quick"

#: Fraction of a whole-run ceiling the *search* may not consume when
#: whole-profile validation is going to run — the validation reserve
#: (WP-1045).  Measured before it existed: on three heavy qarr patterns
#: (corundum, zincite, brucite) the search consumed the full 120 s ceiling on
#: every run and validation got **zero** fits, while a validation fit costs
#: 0.3–1.9 s and a trailing search *system* costs 11–60 s.  8 % (9.6 s at the
#: default ceiling) covers the measured worst checked shortlist (3 × 1.9 s)
#: with margin for the equal-slice arithmetic, and costs at most a sixth of
#: one trailing system — and the deferred ambiguity pass runs on whatever the
#: fits leave, because validation is the mandatory check and the enumeration
#: is the one the gate already reads conservatively when unasked.  Scheduling
#: within the ceiling, never a change to it: the run still ends at
#: ``total_budget_seconds``, the search merely stops early enough that
#: "validated by Le Bail" is part of the first click's answer rather than the
#: rerun's.  No reserve when nothing will validate (``validate=False`` or no
#: pattern): the search keeps every second.
VALIDATION_RESERVE_FRACTION = 0.08

#: name → the whole-run ceiling it fills in (``None`` = unbounded, today's
#: pre-WP-1042 behaviour).  Held in bijection with :data:`SEARCH_PRESET_INFO`
#: by a meta-test (the ``PLAN_PRESETS``/``PLAN_INFO`` pattern), and quoted live
#: by ``capabilities()`` and the agent schema — never restated.
SEARCH_PRESETS: dict[str, float | None] = {
    "quick": QUICK_TOTAL_BUDGET_SECONDS,
    "full": None,
}


@dataclass(frozen=True)
class SearchPresetInfo:
    """What a search preset is for, in the words a chooser needs.

    The ``PLAN_INFO`` pattern one registry over: beside the registry rather
    than in a UI or a docs page, because every consumer needs the same facts
    and a preset added without a row here is a preset nobody can be told when
    to use.  ``typical_seconds`` is **measured** (the WP-1042 task-0 corpus
    re-measure; dated history in the v1.0 appendix diary) and must be
    re-measured when the default protocol changes; the worst case is stated in
    ``description`` because it is a different *kind* of number per preset — a
    bounded preset's worst case is its own ceiling plus
    :data:`CEILING_GRANULARITY_SECONDS`, an unbounded one's is
    :func:`estimate_ceiling`'s spec arithmetic.
    """

    title: str
    description: str
    when_to_use: str
    typical_seconds: tuple[float, float]


SEARCH_PRESET_INFO: dict[str, SearchPresetInfo] = {
    "quick": SearchPresetInfo(
        title="Quick (default)",
        description=(
            "All registered engines, all requested systems in SYSTEM_ORDER, "
            "with a whole-run ceiling of "
            f"{QUICK_TOTAL_BUDGET_SECONDS:g} s covering search, probe and "
            "validation — the worst case is that ceiling plus one "
            "cooperative-check granularity.  Nothing is narrowed: no engine "
            "dropped, no system dropped, no search box shrunk.  A run that "
            "hits the ceiling reports what was truncated or not reached "
            "(INDEX_BUDGET_EXHAUSTED) rather than having silently searched "
            "less, and what a binding ceiling cuts is the trailing "
            "low-symmetry systems — the documented cost of cheapest-first "
            "ordering."),
        when_to_use=(
            "the default: a first look at anything, and every interactive "
            "call — the graded shortlist for completed systems streams "
            "seconds in, and the ceiling keeps a short or pathological list "
            "from hanging the run"),
        typical_seconds=(1.0, 126.0),
    ),
    "full": SearchPresetInfo(
        title="Full (no ceiling)",
        description=(
            "The same engines and systems with no whole-run ceiling — only "
            "the per-(engine × system) budget_seconds bounds the search, so "
            "the worst case is estimate_ceiling()'s arithmetic on the spec "
            "and validation runs unbudgeted.  This is the pre-1.0 default "
            "behaviour."),
        when_to_use=(
            "when a quick run reported truncated or not-reached systems (or "
            "validation slices that ran dry) and the answer may live there — "
            "typically low-symmetry searches, which are irreducibly slow"),
        typical_seconds=(4.0, 440.0),
    ),
}


# ----------------------------------------------------------------------
# The ceiling a caller can compute before running (WP-1037)
# ----------------------------------------------------------------------
#: Engines whose worst-case cost :func:`estimate_ceiling` models.  All three take
#: ``budget_seconds`` per system as a hard per-system ceiling, and trial_error
#: adds the dominant-zone probe.  A registered engine that is not in this set
#: comes back in ``CeilingEstimate.unmodelled`` rather than silently costing zero.
#:
#: ``svd`` is in here rather than unmodelled because its ladder reads the budget
#: between volume rungs and its trim retry (WP-1040) shares the **same** Budget
#: object as the search — a second one would have made the engine cost
#: 2·``budget_seconds`` per system and quietly falsified this whole arithmetic.
MODELLED_ENGINES: frozenset[str] = frozenset({"dichotomy", "svd", "trial_error"})

#: Measured seconds per Le Bail validation fit on the eight-dataset known-cell
#: corpus (WP-1037 task 0, darwin/arm64 M4): 0.6–8.5 s on single-phase lab and
#: synchrotron patterns, 44 s on the round-robin three-phase mixture.  A
#: **measurement, not arithmetic** — Le Bail cost scales with the pattern's
#: channel count and the candidate's reflection count, and no budget bounds it
#: unless ``total_budget_seconds`` is declared — which is why the estimate
#: carries it as an explicitly uncertain range instead of folding a guess into
#: the worst case.  It is also why the term matters at all: on the FAP tutorial
#: pattern validation was 74 s of an 84 s run — eight fits, none budgeted.
MEASURED_VALIDATION_SECONDS: tuple[float, float] = (0.6, 44.0)

#: Measured wall clock of a whole **unbounded** (``preset="full"``) run on the
#: acceptance-protocol corpus (re-measured WP-1042 task 0, three engines,
#: system-major scheduler, darwin/arm64 M4 ``[dev,jax,torch]``): runs that actually
#: search land in this band — the top of it is corundum, whose dichotomy units
#: alone now cost 77-200 s per system — and the abstaining runs finish under a
#: second.  Quoted beside the arithmetic worst case because the two differ by
#: ~3-100× and a ceiling ten times the typical gets ignored.  The ``quick``
#: default does not live in this band: its ceiling bounds the whole run at
#: ``QUICK_TOTAL_BUDGET_SECONDS`` plus one cooperative granularity.
MEASURED_TYPICAL_SECONDS: tuple[float, float] = (4.0, 440.0)

#: How far past a declared ceiling a run can land: the longest stretch between
#: cooperative reads of the deadline.  In the searches that is one box or one
#: solve (well under a second); the two long poles are **consensus** — ranking,
#: panel scoring and ambiguity enumeration run after the search loop with no
#: token reads, measured ~3.6 s past a binding ceiling on a 30-line synthetic —
#: and the validation fit, whose token is read between residual evaluations but
#: whose per-stage model compile is not interruptible (seconds on a dense lab
#: pattern).  Verified by the acceptance run: ``--total-budget 60`` must finish
#: within 60 s plus one of these.
CEILING_GRANULARITY_SECONDS = 10.0


@dataclass(frozen=True)
class CeilingEstimate:
    """The pre-run answer to "how long can this take" — and what kind of answer
    each field is.

    ``search_seconds`` and ``probe_seconds`` are **arithmetic on the spec, not a
    timing prediction**: per-system budgets are hard ceilings the engines
    enforce, so their sum is a bound that holds by construction, on any
    machine.  The validation term is the weak one and wears no arithmetic
    clothes: ``validation_seconds_each`` is a measured range
    (:data:`MEASURED_VALIDATION_SECONDS`), because a Le Bail fit has no budget
    of its own and its cost is a property of the data.  ``typical_seconds``
    (:data:`MEASURED_TYPICAL_SECONDS`) is why the worst case should not be read
    as an ETA: searches finish their systems early far more often than not.
    """

    search_seconds: float
    probe_seconds: float
    validation_calls: int
    validation_seconds_each: tuple[float, float]
    granularity_seconds: float
    #: engines whose cost the arithmetic covers, and those it does not — a
    #: registered engine outside :data:`MODELLED_ENGINES` costs an unknown
    #: amount, and saying so beats a worst case that silently omits it
    covers: tuple[str, ...]
    unmodelled: tuple[str, ...]
    typical_seconds: tuple[float, float]

    @property
    def worst_case_seconds(self) -> float:
        """Arithmetic search + probe bound, plus the *measured high end* of the
        validation range — the honest total, with the caveat in the field
        docs."""
        return (self.search_seconds + self.probe_seconds
                + self.validation_calls * self.validation_seconds_each[1])


def estimate_ceiling(spec: SearchSpec | None = None, *,
                     engines: Sequence[str] | None = None,
                     validate: bool = True) -> CeilingEstimate:
    """What a run of :func:`~rietx.indexing.workflow.index_pattern` can cost,
    computable **before** starting it.

    See :class:`CeilingEstimate` for which terms are arithmetic and which are
    measured.  The arithmetic: ``budget_seconds`` is per (engine × system)
    (an unbounded three-engine call is 3 × 7 × 30 s = 10.5 min of search
    ceiling — the ``quick`` default's whole-run ceiling cuts across it), the
    dominant-zone probe adds up to ``len(ladder)`` rungs of
    ``min(budget_seconds, probe_seconds)`` for each low-DOF system, and
    validation runs one Le Bail fit per checked candidate (worst case
    ``max_candidates`` — :func:`~rietx.indexing.consensus.checked_indices`
    is the top few plus every all-engine candidate, which the cap bounds).
    """
    from .trial_error import (
        DOMINANT_ZONE_MAX_DOF,
        DOMINANT_ZONE_PROBE_LADDER,
        DOMINANT_ZONE_PROBE_SECONDS,
    )

    spec = spec or SearchSpec()
    names = tuple(engines) if engines is not None else engine_names()
    covers = tuple(n for n in names if n in MODELLED_ENGINES)
    unmodelled = tuple(n for n in names if n not in MODELLED_ENGINES)
    systems = [s for s in SYSTEM_ORDER if s in spec.systems]

    search = len(covers) * len(systems) * float(spec.budget_seconds)
    probe = 0.0
    if "trial_error" in covers:
        eligible = [s for s in systems
                    if METRIC_DOF.get(s, 6) <= DOMINANT_ZONE_MAX_DOF]
        probe = (len(eligible) * len(DOMINANT_ZONE_PROBE_LADDER)
                 * min(float(spec.budget_seconds), DOMINANT_ZONE_PROBE_SECONDS))
    calls = int(spec.max_candidates) if validate else 0
    return CeilingEstimate(
        search_seconds=search, probe_seconds=probe, validation_calls=calls,
        validation_seconds_each=MEASURED_VALIDATION_SECONDS,
        granularity_seconds=CEILING_GRANULARITY_SECONDS,
        covers=covers, unmodelled=unmodelled,
        typical_seconds=MEASURED_TYPICAL_SECONDS)


__all__ = ["CEILING_GRANULARITY_SECONDS", "CENTRINGS",
           "ENGINE_POOL_MULTIPLE", "MIN_AGREEMENT", "PRIOR_FINDER",
    "agreement", "candidates_truncated_diagnostic", "corroborated",
           "DEFAULT_BUDGET_SECONDS", "DEFAULT_MAX_CANDIDATES",
           "DEFAULT_MAX_D_AXIS", "DEFAULT_MIN_D_AXIS", "DEFAULT_MIN_VOLUME",
           "DEFAULT_N_UNINDEXED", "DEFAULT_SEARCH_LINES",
           "SEARCH_POOL_MULTIPLE",
           "MAX_PREDICTED_REFLECTIONS", "MEASURED_TYPICAL_SECONDS",
           "MEASURED_VALIDATION_SECONDS", "MODELLED_ENGINES",
           "PROVISIONAL_STREAM_TOP", "provisional_payload",
           "SAME_SOLUTION_RTOL", "SYSTEM_ORDER",
           "Budget", "CeilingEstimate", "Deadline", "EngineCandidate",
           "EngineResult", "Progress", "SearchSpec", "assign_lines",
           "DEFAULT_UNKNOWN_SHIFT_DEG", "DEFAULT_VOLUME_CEILING",
           "budget_exhausted_diagnostic",
           "dedup_candidates", "dedup_groups",
           "effective_shift_allowance", "engine_descriptions", "engine_names",
           "estimate_ceiling", "indexes_the_search_lines", "match_window",
           "merge_engine_units", "refine_with_shift",
           "scored_positions", "search_line_order", "search_volume_ceiling",
           "shift_allowance_diagnostic",
           "shift_from_pairs_diagnostic",
           "get_engine", "incomplete_diagnostic", "predicted_reflection_count",
           "reflection_ceiling_ok", "register_engine", "solution_key",
           "to_cell_candidate", "trial_hkl"]
