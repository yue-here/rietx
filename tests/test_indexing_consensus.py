"""WP-1024 — consensus, the confidence gate, and the shape of the answer.

Four kinds of claim, and they are not interchangeable:

* **the API shape** — that a confident wrong singleton is *unspellable*.  This is
  the milestone's founding rule and it is tested against the type rather than
  against a message: no ``.cell``, no ``.best``, and ``best_or_none()`` returning
  ``None`` under every gate failure.  A docstring asking for the rule would not be
  a test of it;
* **the gate** — each caveat's effect on the verdict, exercised on hand-built
  candidates so every branch is covered without a search;
* **the detectors** — that the whole-profile Le Bail fit separates a correct cell
  from an oversized one, with the measured numbers pinned, because the module's
  reasoning rests on them;
* **the restriction** — that a search over three systems cannot be read as a
  statement about the specimen.  Measured on this repo's own data, a restricted
  engine's coverage bands overlap between single-phase low-symmetry patterns and a
  genuine mixture, and a multiphase claim built on that ambiguity was withdrawn;
  this test is that retraction made permanent.

Every search here declares ``shift_allowance_deg`` explicitly.  The peak lists carry
*exact* positions, so the systematic allowance the engines assume for real data
(``DEFAULT_UNKNOWN_SHIFT_DEG``) is pure looseness — and it would also change what
is being measured, since it caps confidence on its own.  Declaring the physics
rather than inheriting a default is the rule (DESIGN.md §Testing & validation
policy).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import IndexingResult, index_pattern
from rietx.crystallography.symmetry import generate_reflections
from rietx.indexing.consensus import (
    CONSENSUS_CHECK_TOP,
    above_supported_parents,
    below_refuting_parents,
    caveats_for,
    checked_indices,
    consensus,
    grade,
    supercell_checks,
)
from rietx.indexing.engines import (
    SearchSpec,
    agreement,
    corroborated,
    engine_names,
    rank_candidates,
)
from rietx.indexing.workflow import (
    _restrict_to_supported,
    absent_reflections,
    structure_from_candidate,
    validate_by_lebail,
)
from rietx.schemas.indexing import (
    INDEX_REFUTING_CAVEATS,
    PEAK_MIN_USABLE_LINES,
    AmbiguityPartner,
    BravaisOpinion,
    CellCandidate,
    FigureOfMerit,
    IndexCaveat,
    LeBailValidation,
    PeakList,
    SupercellCheck,
)

pytestmark = pytest.mark.xdist_group("indexing-consensus")

LAM = 1.5405929
TRUE_A = 4.1566
#: 2θ range of the synthetic pattern every measured number here is quoted at.
#: 145° rather than 100° for a reason the data-quality gate enforces: a cubic cell
#: shows 15 lines to 100° and 23 to 145°, and below
#: ``PEAK_MIN_USABLE_LINES = 20`` the list cannot be *scored* — the classical
#: figures leave the panel and the ``fom_panel_reduced`` caveat caps confidence
#: (WP-1043) — so a shorter pattern tests the reduced-panel path rather than
#: the scored one this module's numbers are quoted on.
TT_MAX = 145.0


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
def _peak_list(cell, group="P m -3 m", *, esd_deg=0.005, two_theta_max=TT_MAX):
    refl = generate_reflections(group, cell, LAM, two_theta_max)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    return PeakList.from_positions(np.sort(tt), LAM, two_theta_esd=esd_deg)


@pytest.fixture(scope="module")
def cubic_peaks():
    return _peak_list((TRUE_A,) * 3 + (90.0,) * 3)


@pytest.fixture(scope="module")
def lab6_pattern():
    """A noisy LaB₆ powder pattern from the true model — the shared protocol.

    Module-scoped and pinned to one xdist worker (see ``pytestmark``) because the
    Le Bail validations below each cost a refinement: a second worker rebuilding
    this would cost more than the sharing saved (CLAUDE.md, the ``--durations``
    rule).
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.pattern import PatternData

    structure, instrument = _true_models()
    tt = np.arange(15.0, TT_MAX, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(11).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _true_models():
    from rietx.schemas.instrument import BackgroundChebyshev, Instrument
    from rietx.schemas.structure import (
        Atom,
        Cell,
        Parameter,
        Phase,
        Structure,
    )

    structure = Structure(phases=[Phase(
        name="LaB6", space_group="P m -3 m", cell=Cell.cubic(TRUE_A),
        scale=Parameter(value=5e-4, min=0.0, transform="softplus"),
        atoms=[
            Atom(label="La", species="La", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="B", species="B", x=Parameter(value=0.1993),
                 y=Parameter(value=0.5), z=Parameter(value=0.5))])])
    instrument = Instrument.debye_scherrer(wavelength=LAM)
    instrument.profile.w.value = 5e-3
    instrument.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (30.0, -4.0, 1.0)])
    return structure, instrument


def _instrument():
    return _true_models()[1]


def _candidate(a: float, **over) -> CellCandidate:
    """A hand-built candidate that passes the gate unless ``over`` breaks it."""
    fields = dict(
        cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(1e-5,) * 6, system="cubic",
        centring="P", lattice_group="P m -3 m", volume=a ** 3,
        n_indexed=23, n_lines=23,
        fom=[FigureOfMerit(name="indexed_fraction", value=1.0, n_lines=23,
                           n_possible=28, k_sigma=3.0)],
        found_by=sorted(engine_names()),
        bravais=BravaisOpinion(system="cubic", system_loosest="cubic",
                               system_gemmi="cubic", system_spglib="cubic"),
        lebail=LeBailValidation(rwp=0.2, gof=1.3, space_group="P m -3 m",
                                n_reflections=28))
    fields.update(over)
    return CellCandidate(**fields)


def _gate(cand, **over):
    kw = dict(engines_run=sorted(engine_names()), panel_disagrees=False,
              validated=True, search_complete={"cubic": True},
              shift_allowance_assumed=False, checked=True)
    kw.update(over)
    caveats = caveats_for(cand, **kw)
    return caveats, grade(caveats, cand.found_by, kw["engines_run"])


# ----------------------------------------------------------------------
# the API shape — the milestone's founding rule
# ----------------------------------------------------------------------
def test_the_result_type_has_no_singleton_accessor():
    """No ``.cell``, no ``.best``, no ``.solution`` — on the *class*.

    Asserted against the type because that is where the rule lives: the same
    species of guard as ``Geometry.mu_r`` being a plain float so refining it is
    unspellable.  A caller's discipline is not what holds here.
    """
    for forbidden in ("cell", "best", "solution", "unit_cell"):
        assert forbidden not in IndexingResult.model_fields
        assert not hasattr(IndexingResult, forbidden)
    assert "candidates" in IndexingResult.model_fields
    assert callable(IndexingResult.best_or_none)


@pytest.mark.parametrize("break_it,expect", [
    ({}, "high"),
    ({"found_by": ["dichotomy"]}, "low"),
    ({"lebail": None}, "medium"),
    # capping since thresholds 1.12 (C3): a count a truth's undetected weak
    # lines can raise keeps ``high`` out of reach; the pairwise check refutes
    ({"lebail": LeBailValidation(rwp=0.4, gof=2.4, space_group="P m -3 m",
                                 n_reflections=153, predicted_but_absent=117)},
     "medium"),
    ({"lebail": LeBailValidation(rwp=float("inf"), gof=float("inf"),
                                 space_group="P m -3 m", n_reflections=0,
                                 status="failed")}, "low"),
    ({"fom": [FigureOfMerit(name="indexed_fraction", value=0.5, n_lines=23,
                            n_possible=28, k_sigma=3.0)]}, "low"),
    ({"volume": 1.0}, "low"),
    ({"bravais": BravaisOpinion(system="tetragonal", system_loosest="cubic",
                                system_gemmi="tetragonal",
                                system_spglib="tetragonal", ambiguous=True)},
     "medium"),
])
def test_best_or_none_is_none_under_every_gate_failure(break_it, expect):
    """One candidate, one broken precondition, and the singleton disappears.

    The parametrisation is the gate's specification read as a table: ``high``
    needs *everything*, a refuting caveat means ``low``, a capping one means
    ``medium`` — and only ``high`` reaches ``best_or_none()``.
    """
    cand = _candidate(TRUE_A, **break_it)
    caveats, verdict = _gate(cand)
    assert verdict == expect, caveats
    cand.confidence, cand.confidence_caveats = verdict, caveats
    result = _result([cand])
    assert (result.best_or_none() is not None) is (expect == "high")


def _fractions(by_line: float, by_intensity: float) -> list[FigureOfMerit]:
    return [FigureOfMerit(name="indexed_fraction", value=by_line, n_lines=53,
                          n_possible=40, k_sigma=3.0),
            FigureOfMerit(name="indexed_intensity_fraction", value=by_intensity,
                          n_lines=53, n_possible=40, k_sigma=3.0)]


@pytest.mark.parametrize("by_line,by_intensity,caveat,grade", [
    # #933's shape: weak foreign lines take the line count under the bar and
    # leave the intensity the cell explains above it — not refuted, but the
    # count under the bar caps the grade (yue-here's ruling on #1042)
    (0.68, 0.95, "indexed_lines_low", "medium"),
    # the reverse: every line but a strong one indexed — refuted, where the
    # line count alone would have passed it
    (0.95, 0.80, "indexed_fraction_low", "low"),
    (0.95, 0.95, None, "high"),
    # both under the bar: the refuting caveat says it, the cap is not stacked
    (0.68, 0.80, "indexed_fraction_low", "low"),
])
def test_indexed_fraction_low_reads_the_intensity_the_cell_explains(
        by_line, by_intensity, caveat, grade):
    """``indexed_fraction_low`` is read on the intensity-weighted fraction
    (WP-1969, issue #933), so a cell's own impurities do not refute it by
    their count, and a missed strong line refutes it whatever the count.  A
    line count under the same bar caps the grade at ``medium`` through
    ``indexed_lines_low``, which names the shortfall the panel holds."""
    caveats, verdict = _gate(_candidate(TRUE_A,
                                        fom=_fractions(by_line, by_intensity)))
    assert [c for c in caveats if c.startswith("indexed_")] == (
        [caveat] if caveat else []), caveats
    assert verdict == grade, caveats


def test_indexed_lines_low_caps_and_does_not_refute():
    from typing import get_args

    from rietx.schemas.indexing import INDEX_REFUTING_CAVEATS, IndexCaveat

    assert "indexed_lines_low" in get_args(IndexCaveat)
    assert "indexed_lines_low" not in INDEX_REFUTING_CAVEATS


def test_indexed_fraction_low_falls_back_to_the_line_fraction():
    """A panel without the weighted member (a hand-built candidate) is read on
    the line fraction, and a candidate with no panel at all is still refuted:
    the reflection ceiling it hit is what the caveat reports."""
    one = [FigureOfMerit(name="indexed_fraction", value=0.85, n_lines=23,
                         n_possible=28, k_sigma=3.0)]
    assert "indexed_fraction_low" in _gate(_candidate(TRUE_A, fom=one))[0]
    assert "indexed_fraction_low" in _gate(_candidate(TRUE_A, fom=[]))[0]


def _result(candidates) -> IndexingResult:
    from rietx.schemas.common import Provenance

    return IndexingResult(candidates=candidates, engines_run=sorted(engine_names()),
                          systems_searched=["cubic"], search_complete={"cubic": True},
                          validated=True, provenance=Provenance(package_version="t"))


def test_two_high_candidates_are_not_a_singleton():
    """Two cells that both pass everything is exactly when a lesser API would
    return the first one."""
    a, b = _candidate(TRUE_A), _candidate(2 * TRUE_A)
    for cand in (a, b):
        cand.confidence = "high"
    result = _result([a, b])
    assert result.best_or_none() is None
    from rietx.indexing.diagnostics import index_diagnostics

    codes = {d.code for d in index_diagnostics(result)}
    assert "INDEX_MULTIPLE_SOLUTIONS" in codes
    assert "INDEX_ABSTAINED" in codes


def test_the_abstention_names_the_refuting_caveats_the_gate_uses():
    """The suggestion's list of caveats to act on first is read off the gate's
    own set, so it cannot keep naming one the gate moved to a cap (C3 moved
    ``predicted_but_absent``)."""
    from rietx.indexing.diagnostics import index_diagnostics
    from rietx.schemas.indexing import INDEX_REFUTING_CAVEATS

    a, b = _candidate(TRUE_A), _candidate(2 * TRUE_A)
    for cand in (a, b):
        cand.confidence = "high"
    text = next(d.suggestion for d in index_diagnostics(_result([a, b]))
                if d.code == "INDEX_ABSTAINED")
    refuting_part = text.split("(")[1].split(")")[0]
    named = {w.strip() for w in refuting_part.split(",")}
    assert named == INDEX_REFUTING_CAVEATS
    assert "predicted_but_absent" not in refuting_part


def test_an_ambiguous_winner_is_not_a_singleton():
    """``best_or_none`` re-checks the ambiguity the gate already checked.

    Deliberate redundancy: this method is the single place the rule is
    *guaranteed*, so it does not delegate the guarantee to whoever filled the
    field.
    """
    from rietx.schemas.indexing import AmbiguityPartner

    cand = _candidate(TRUE_A)
    cand.confidence = "high"
    assert _result([cand]).best_or_none() is not None
    cand.ambiguity = [AmbiguityPartner(
        cell=(2 * TRUE_A,) * 3 + (90.0,) * 3,
        transformation=[[2, 0, 0], [0, 1, 0], [0, 0, 1]], index=2,
        system="triclinic", volume=8 * TRUE_A ** 3)]
    assert _result([cand]).best_or_none() is None


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
def test_the_caveat_vocabulary_is_closed_and_the_split_is_a_subset():
    """``INDEX_REFUTING_CAVEATS`` must name only real caveats.

    A refuting set that drifted from the vocabulary would silently stop refuting:
    a typo'd member is never in a candidate's caveat list, so nothing would ever
    be demoted by it and no test of the *gate* would notice.
    """
    from typing import get_args

    members = set(get_args(IndexCaveat))
    assert INDEX_REFUTING_CAVEATS <= members
    assert members - INDEX_REFUTING_CAVEATS, "some caveats must merely cap"


def test_an_assumed_tolerance_caps_confidence_on_its_own():
    """The measured reason: a cell found inside a widened window absorbs the
    shift (+1400 ppm on a certified pattern), so an *assumed* allowance is not a
    neutral setting — and the way to clear it is evidence, not a constant."""
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, shift_allowance_assumed=True)
    assert caveats == ["shift_allowance_assumed"]
    assert verdict == "medium"
    assert _gate(cand)[1] == "high"


def test_a_reduced_panel_caps_confidence_on_its_own():
    """WP-1043: below the scoring bar the ranking stands and ``high`` does not —
    the same reachability the old abstention gave unattended use, kept without
    refusing the search.  Capping rather than refuting, because a short list is
    not evidence *against* a cell."""
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, panel_reduced=True)
    assert caveats == ["fom_panel_reduced"]
    assert verdict == "medium"
    assert "fom_panel_reduced" not in INDEX_REFUTING_CAVEATS


def test_an_unchecked_candidate_cannot_reach_high():
    """Not enumerating the ambiguity is not the same as finding none.

    The expensive checks run on a subset, so a candidate outside it has an
    unasked question, and an unasked question must not read as a clean answer.
    """
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, checked=False)
    assert "geometric_ambiguity" in caveats
    assert verdict == "low"


def test_an_incomplete_search_caps_the_systems_it_did_not_finish():
    cand = _candidate(TRUE_A)
    caveats, verdict = _gate(cand, search_complete={"cubic": False})
    assert caveats == ["search_incomplete"] and verdict == "medium"


def test_a_single_engine_is_never_agreement():
    """Even with nothing to qualify: one search is one opinion."""
    cand = _candidate(TRUE_A, found_by=["dichotomy"])
    caveats, verdict = _gate(cand)
    assert caveats == ["engines_disagree"] and verdict == "low"


def _cubic_search(peaks, **overrides):
    """One dichotomy pass over the synthetic cubic list — several lattices, one
    engine, cheap enough to run inside a fast test."""
    from rietx.indexing.dichotomy import search_dichotomy

    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, shift_allowance_deg=1e-9,
                      budget_seconds=120.0, **overrides)
    return spec, search_dichotomy(peaks, spec=spec)


def test_agreement_outranks_the_panel_and_is_inert_until_the_merge(cubic_peaks):
    """WP-1046 — the first ranking key is whether two engines found the lattice.

    The package's own doctrine, applied to the order rather than only to the
    verdict: ``grade`` floors a candidate with fewer than two finders at
    ``low`` before any caveat is read, so a list ranked on the panel alone puts
    candidates the gate refuses to promote above the one it could (measured, on
    fluorapatite over seven systems the six above the truth were one engine's
    and the truth was all three's).  Asserted as a *promotion*: whatever the
    panel ranks second overtakes the panel's own winner on agreement alone, and
    with the finder counts equal the panel's order comes back untouched — which
    is why nothing changes inside an engine, where ``found_by`` is empty.
    """
    _spec, result = _cubic_search(cubic_peaks)
    cands = result.candidates
    assert len(cands) >= 2
    # inside a search nothing is merged, so every candidate stands on one engine
    assert {agreement(c) for c in cands} == {1}
    order = rank_candidates(cands, cubic_peaks)
    winner, runner_up = order[0], order[1]

    winner.found_by = ["dichotomy"]
    runner_up.found_by = ["dichotomy", "svd"]
    assert rank_candidates(cands, cubic_peaks)[0] is runner_up

    # equal agreement returns the panel's own order, unchanged
    winner.found_by = ["dichotomy", "svd"]
    assert rank_candidates(cands, cubic_peaks)[:2] == [winner, runner_up]

    # and a THIRD finder buys nothing: the key is the gate's boundary, not a
    # count.  Measured, this is what a count costs (WP-1046): the engines'
    # reach differs by system, so three of them meet in a cheap orthorhombic
    # domain while only two reach an expensive monoclinic one, and on
    # bethanechol's default mode a count sent four published truths from rank 1
    # to ranks 5, 3, 9 and 8 behind orthorhombic cells all three engines found.
    runner_up.found_by = ["dichotomy", "svd", "trial_error"]
    assert agreement(runner_up) == 3 and corroborated(runner_up)
    assert rank_candidates(cands, cubic_peaks)[:2] == [winner, runner_up]


def test_a_prior_is_not_a_finder_for_the_ranking_key():
    """WP-1045's "a wrong prior changes no rank", kept structural under
    WP-1046's key: a stated cell an engine also found must not outrank a
    lattice two engines reached, so :func:`agreement` counts **engines**."""
    from types import SimpleNamespace

    from rietx.indexing.priors import PRIOR_FINDER

    assert agreement(SimpleNamespace(found_by=["svd", PRIOR_FINDER])) == 1
    assert agreement(SimpleNamespace(found_by=["svd", "trial_error"])) == 2
    # and a prior-only candidate is still a candidate, never a zero
    assert agreement(SimpleNamespace(found_by=[PRIOR_FINDER])) == 1
    assert agreement(SimpleNamespace(found_by=[])) == 1


def test_the_reported_cap_is_applied_after_the_merge_and_says_what_it_dropped(
        cubic_peaks):
    """WP-1046 — ``max_candidates`` bounds the **reported** list, and the units
    hand the merge five times as many.

    Both halves in one search.  The unit keeps up to ``engine_pool()`` rather
    than the reported cap, so consensus ranks more than it reports; and the
    truncation is stated (``INDEX_CANDIDATES_TRUNCATED``) rather than silent,
    because a cap that says nothing reads as "everything was considered".
    """
    spec, result = _cubic_search(cubic_peaks, max_candidates=2)
    assert spec.engine_pool() == 10
    assert len(result.candidates) > spec.max_candidates

    outcome = consensus([result], cubic_peaks, spec=spec, ambiguity=False)
    assert len(outcome.candidates) == spec.max_candidates
    truncated = [d for d in outcome.diagnostics
                 if d.code == "INDEX_CANDIDATES_TRUNCATED"]
    assert len(truncated) == 1
    assert "ranked below it" in truncated[0].message
    assert truncated[0].level == "info"


def test_the_expensive_checks_cover_every_promotable_candidate():
    """The cap on cost must not become a cap on the answer.

    ``checked_indices`` is the top few *plus* every candidate the engines agree
    on — because that second set is the only kind the gate can promote, so
    skipping one would quietly make ``high`` unreachable for it.
    """
    cands = [_candidate(4.0 + 0.1 * i, found_by=["dichotomy"])
             for i in range(8)]
    cands[6].found_by = sorted(engine_names())
    idx = checked_indices(cands, sorted(engine_names()), top=CONSENSUS_CHECK_TOP)
    assert idx[:CONSENSUS_CHECK_TOP] == list(range(CONSENSUS_CHECK_TOP))
    assert 6 in idx, "a candidate both engines found must always be checked"
    assert 7 not in idx


# ----------------------------------------------------------------------
# a stop inside one candidate's ambiguity sweep (#895, WP-1924)
# ----------------------------------------------------------------------
class _StopsAfter:
    """A cancel token that reads unset ``n`` times and set from then on."""

    def __init__(self, n: int):
        self.n, self.reads = n, 0

    def __bool__(self) -> bool:
        self.reads += 1
        return self.reads > self.n


def _sweep_args(peaks, a=TRUE_A):
    return ((a,) * 3 + (90.0,) * 3, "cubic", "P", peaks.q(), peaks.q_esd(),
            LAM, float(peaks.two_theta_max))


def test_a_stop_inside_an_ambiguity_sweep_waits_one_child_and_answers_nothing(
        cubic_peaks, monkeypatch):
    """The token is read before each derivative cell, so a stop waits one
    child's work, and a stopped sweep returns ``None`` rather than the
    partners found so far, which would read as a complete answer.  One
    monoclinic sweep takes 0.9 s of CPU on #780's cell, its slowest child 47 ms.
    """
    from rietx.indexing import ambiguity

    calls: list[int] = []
    real = ambiguity.predicted_lines

    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(ambiguity, "predicted_lines", counted)
    whole = ambiguity.ambiguity_partners(*_sweep_args(cubic_peaks))
    n_children = len(calls) - 1
    assert n_children > 3
    calls.clear()
    never = _StopsAfter(10 ** 9)
    assert ambiguity.ambiguity_partners(*_sweep_args(cubic_peaks),
                                        cancel=never) == whole
    assert never.reads == n_children
    calls.clear()
    assert ambiguity.ambiguity_partners(*_sweep_args(cubic_peaks),
                                        cancel=_StopsAfter(2)) is None
    assert len(calls) == 1 + 2, "the parent's lines and the two children begun"


def test_a_candidate_whose_sweep_is_stopped_stays_unasked(cubic_peaks):
    """``enumerate_ambiguity`` leaves a stopped candidate out of
    ``ambiguity_checked`` with its ``ambiguity`` untouched, and a candidate
    finished before the stop keeps its whole answer."""
    from rietx.indexing.ambiguity import derivative_cells
    from rietx.indexing.consensus import ConsensusOutcome, enumerate_ambiguity

    n_children = len(derivative_cells(_sweep_args(cubic_peaks)[0]))

    def outcome():
        cands = [_candidate(TRUE_A), _candidate(TRUE_A * 1.5)]
        return ConsensusOutcome(candidates=cands,
                                engines_run=sorted(engine_names()))

    full = outcome()
    enumerate_ambiguity(full, cubic_peaks)
    assert full.ambiguity_checked == [0, 1]

    # stopped inside the first candidate's sweep: its loop read, two children
    first = outcome()
    sentinel = [AmbiguityPartner(cell=(1.0,) * 3 + (90.0,) * 3,
                                 transformation=[[1, 0, 0], [0, 1, 0], [0, 0, 2]],
                                 index=2, system="triclinic", volume=1.0)]
    first.candidates[0].ambiguity = sentinel
    enumerate_ambiguity(first, cubic_peaks, cancel=_StopsAfter(1 + 2))
    assert first.ambiguity_checked == []
    assert first.candidates[0].ambiguity == sentinel

    # stopped inside the second: the first is answered whole
    second = outcome()
    second.candidates[1].ambiguity = sentinel
    enumerate_ambiguity(second, cubic_peaks,
                        cancel=_StopsAfter(1 + n_children + 1 + 2))
    assert second.ambiguity_checked == [0]
    assert second.candidates[0].ambiguity == full.candidates[0].ambiguity
    assert second.candidates[1].ambiguity == sentinel


def test_a_candidate_whose_sweep_refuses_stays_unasked(cubic_peaks,
                                                       monkeypatch):
    """A sweep that raises has not asked the question, so its candidate stays
    out of ``ambiguity_checked`` and the gate caps it.  Before WP-1924 the
    refusal came back as ``[]``, which reads as "asked, no partners", and the
    next candidate is still asked."""
    from rietx.indexing import ambiguity
    from rietx.indexing.consensus import ConsensusOutcome, enumerate_ambiguity

    real = ambiguity.predicted_lines

    def refusing(cell, system, *args, **kwargs):
        if system == "cubic" and cell[0] == TRUE_A:
            raise ValueError("the parent's lines cannot be predicted")
        return real(cell, system, *args, **kwargs)

    monkeypatch.setattr(ambiguity, "predicted_lines", refusing)
    outcome = ConsensusOutcome(
        candidates=[_candidate(TRUE_A), _candidate(TRUE_A * 1.5)],
        engines_run=sorted(engine_names()))
    enumerate_ambiguity(outcome, cubic_peaks)
    assert outcome.ambiguity_checked == [1]
    caveats, grade_ = _gate(outcome.candidates[0],
                            checked=0 in outcome.ambiguity_checked)
    assert "geometric_ambiguity" in caveats and grade_ != "high"


# ----------------------------------------------------------------------
# the supercell re-rank (WP-1449)
# ----------------------------------------------------------------------
def _check(parent: CellCandidate, verdict: str) -> SupercellCheck:
    return SupercellCheck(parent_cell=parent.cell, parent_system=parent.system,
                          parent_centring=parent.centring, index=2, n_extra=10,
                          n_seen=0, p0=0.1, p_value=1.0, verdict=verdict)


def test_a_refuted_supercell_sits_directly_below_its_parent_and_nothing_else_moves():
    """The whole ordering rule, on hand-built checks.

    A refuted child waits for every parent that refutes it, so it lands below
    the lowest-ranked of them; candidates between the two keep their places
    above it; a child already below its parent stays put; and a supported or
    undecided check moves nothing here.  An undecided one is no evidence at
    all, and a supported one is :func:`above_supported_parents`'s to act on.
    """
    a, b, c, d, e, f = (_candidate(4.0 + 0.1 * i) for i in range(6))
    a.supercell_checks = [_check(c, "refuted"), _check(e, "refuted")]
    b.supercell_checks = [_check(f, "supported")]
    d.supercell_checks = [_check(c, "refuted")]
    f.supercell_checks = []
    e.supercell_checks = [_check(f, "undecided")]
    assert below_refuting_parents([a, b, c, d, e, f]) == [b, c, d, e, a, f]
    assert below_refuting_parents([b, c, d, e, f]) == [b, c, d, e, f]


def test_a_supported_supercell_sits_directly_above_its_parent_and_a_refuted_one_never_rises():
    """The mirror rule (WP-1510), on hand-built checks.

    A supported child moves up to directly above the highest-ranked parent
    supporting it, and the candidates between keep their order below it.  Two
    children of one parent keep their own order above it.  A child already
    above its parent stays put.  A child refuted against any parent is never
    moved up, even where another check supports it, so the two halves never
    pull one candidate both ways.  An undecided check moves nothing.
    """
    a, b, c, d, e, f, g = (_candidate(4.0 + 0.1 * i) for i in range(7))
    a.supercell_checks = [_check(c, "supported")]      # already above c
    d.supercell_checks = [_check(b, "supported")]
    f.supercell_checks = [_check(b, "supported"), _check(c, "supported")]
    e.supercell_checks = [_check(b, "supported"), _check(c, "refuted")]
    g.supercell_checks = [_check(b, "undecided")]
    ranked = [a, b, c, d, e, f, g]
    assert above_supported_parents(ranked) == [a, d, f, b, c, e, g]
    # composed as consensus composes them, e stays under the c that refutes it
    both = above_supported_parents(below_refuting_parents(ranked))
    assert both == [a, d, f, b, c, e, g]
    assert both.index(e) > both.index(c)


def test_a_supercell_the_pattern_shows_rises_above_its_parent_and_a_phantom_does_not(
        cubic_peaks):
    """The pair through the check, both ways, on synthetic lists.

    The same two cells, the cubic truth and a c × 2 cell, ranked parent first
    as corroboration would put a cell more engines found.  When the pattern
    carries the doubled cell's lines, its extras are seen on lines the cubic
    cell cannot index, the check reads supported, and the larger cell moves
    above.  When only the cubic cell's lines exist, the same pair reads refuted
    and the larger cell stays below.
    """
    double = (TRUE_A, TRUE_A, 2 * TRUE_A, 90.0, 90.0, 90.0)

    def pair():
        parent = _candidate(TRUE_A)
        child = _candidate(TRUE_A, cell=double, system="tetragonal",
                           lattice_group="P 4/m m m", volume=2 * TRUE_A ** 3)
        return parent, child

    for peaks, verdict, first in (
            (_peak_list(double, "P 4/m m m"), "supported", "child"),
            (cubic_peaks, "refuted", "parent")):
        parent, child = pair()
        ranked = [parent, child]
        supercell_checks(ranked, peaks, q_match=peaks.q_esd(), k_sigma=3.0)
        (check,) = child.supercell_checks
        assert check.verdict == verdict
        if verdict == "supported":
            assert check.n_seen_unexplained == check.n_seen == check.n_extra
        else:
            assert check.n_seen_unexplained == check.n_seen == 0
        ordered = above_supported_parents(below_refuting_parents(ranked))
        assert ordered[0] is (child if first == "child" else parent)


def test_the_check_screens_each_cell_on_its_own_corrected_lines(cubic_peaks,
                                                                monkeypatch):
    """WP-2030, on #941's containment check: which lines a parent indexes is
    read on the parent's own shift correction, never the child's.

    ``screen_for`` hands each candidate its own ``scored_positions``; a parent
    read on the child's lines indexes none of them and every extra the child
    sees reads unexplained, which is "supported" for the wrong reason.
    """
    from rietx.indexing import screen
    from rietx.indexing.engines import scored_positions

    double = (TRUE_A, TRUE_A, 2 * TRUE_A, 90.0, 90.0, 90.0)
    parent = _candidate(TRUE_A).model_copy(update={
        "shift_template": "constant", "shift_coefficient": 0.03})
    child = _candidate(TRUE_A, cell=double, system="tetragonal",
                       lattice_group="P 4/m m m", volume=2 * TRUE_A ** 3)
    seen = []
    real = screen.screen_candidate

    def spy(pattern, cell, system, centring, **kwargs):
        seen.append((tuple(cell), kwargs["q_obs"]))
        return real(pattern, cell, system, centring, **kwargs)

    monkeypatch.setattr(screen, "screen_candidate", spy)
    supercell_checks([parent, child], cubic_peaks, q_match=cubic_peaks.q_esd(),
                     k_sigma=3.0)
    by_cell = dict(seen)
    assert np.array_equal(by_cell[tuple(float(v) for v in parent.cell)],
                          scored_positions(cubic_peaks, parent)[0])
    assert np.array_equal(by_cell[tuple(float(v) for v in child.cell)],
                          scored_positions(cubic_peaks, child)[0])
    assert not np.array_equal(*by_cell.values())


def test_a_phantom_supercell_is_refuted_graded_down_and_told_where_to_look(
        cubic_peaks):
    """The check on a list, the caveat it raises, and the message that names it.

    The doubled cell indexes every observed line and adds lines nobody saw, so
    it moves below the true cell, is refuted rather than capped, and says which
    parent, how many extras, how many seen, and where the first missing one is.
    The parent is asked too, and has no parent of its own: ``[]``, not ``None``.
    """
    from rietx.indexing.diagnostics import candidate_diagnostics

    truth = _candidate(TRUE_A)
    doubled = _candidate(TRUE_A, cell=(TRUE_A, TRUE_A, 2 * TRUE_A, 90.0, 90.0,
                                       90.0),
                         system="tetragonal", lattice_group="P 4/m m m",
                         volume=2 * TRUE_A ** 3)
    ranked = [doubled, truth]
    supercell_checks(ranked, cubic_peaks, q_match=cubic_peaks.q_esd(),
                     k_sigma=3.0)
    assert truth.supercell_checks == []
    (check,) = doubled.supercell_checks
    assert check.verdict == "refuted" and check.index == 2
    assert check.parent_cell == truth.cell and check.n_seen == 0
    assert check.absent_two_theta == sorted(check.absent_two_theta)
    assert below_refuting_parents(ranked) == [truth, doubled]
    assert above_supported_parents([truth, doubled]) == [truth, doubled]

    caveats, verdict = _gate(doubled)
    assert caveats == ["supercell_refuted"] and verdict == "low"
    assert "supercell_refuted" in INDEX_REFUTING_CAVEATS
    (diag,) = [d for d in candidate_diagnostics(doubled)
               if d.code == "INDEX_SUPERCELL_REFUTED"]
    assert f"{check.n_extra} extra line(s)" in diag.message
    assert f"{check.absent_two_theta[0]:.3f}°" in diag.where[-1]


def test_consensus_asks_every_engine_candidate_and_orders_by_the_answer(
        cubic_peaks):
    """Wired where the order is made, so a streamed list agrees with the final.

    Every engine candidate comes out of consensus asked (``[]`` or a list,
    never ``None``), and no candidate the check refutes sits above a parent
    that refutes it.
    """
    spec, result = _cubic_search(cubic_peaks)
    outcome = consensus([result], cubic_peaks, spec=spec, ambiguity=False)
    assert outcome.candidates
    assert all(c.supercell_checks is not None for c in outcome.candidates)
    keys = [(c.cell, c.system, c.centring) for c in outcome.candidates]
    for rank, cand in enumerate(outcome.candidates):
        for check in cand.supercell_checks:
            if check.verdict == "refuted":
                parent = (check.parent_cell, check.parent_system,
                          check.parent_centring)
                assert keys.index(parent) < rank


# ----------------------------------------------------------------------
# the detectors
# ----------------------------------------------------------------------
def test_structure_from_candidate_carries_a_dummy_atom_and_no_absences():
    """Both footguns, asserted rather than only documented.

    The absence-free default is the load-bearing half: a group with reflection
    conditions would excuse an oversized cell's phantom reflections as
    extinctions, which is precisely how such a cell passes validation.
    """
    structure = structure_from_candidate(_candidate(TRUE_A))
    phase = structure.phases[0]
    assert phase.space_group == "P m -3 m"          # holohedry, no conditions
    assert len(phase.atoms) == 1                    # Phase._nonempty needs one
    assert phase.cell.a.value == pytest.approx(TRUE_A)

    centred = _candidate(TRUE_A, centring="F", lattice_group="")
    assert structure_from_candidate(centred).phases[0].space_group == "F m -3 m"


def test_absent_reflections_reads_the_fitted_background():
    """The detector on hand-made arrays: one position with a peak, one without."""
    tt = np.arange(20.0, 25.0, 0.01)
    bkg = np.full_like(tt, 100.0)
    y = bkg + 500.0 * np.exp(-0.5 * ((tt - 21.0) / 0.05) ** 2)
    sigma = np.sqrt(y)
    absent, ratio = absent_reflections(tt, y, bkg, sigma,
                                       np.array([21.0, 23.0]),
                                       np.array([0.12, 0.12]))
    assert absent == [23.0]
    assert ratio[0] < 3.0
    # a position outside the fitted range is *not* evidence of absence
    assert absent_reflections(tt, y, bkg, sigma, np.array([40.0]),
                              np.array([0.12]))[0] == []


@pytest.mark.parametrize("factor,expect_absent,expect_unmatched", [
    (1.0, 0, 0),                     # the truth
    (2.0, "most", 0),                # doubled cell: the oversized signature
    (1.01, "some", "many"),          # wrong metric: caught from both sides
])
def test_le_bail_validation_separates_the_failure_modes(lab6_pattern, factor,
                                                        expect_absent,
                                                        expect_unmatched):
    """The measurement the module's reasoning rests on, pinned.

    Read it by column rather than by row: Rwp is decisive on a wrong *metric* and
    silent on an *oversized* cell, where only ``predicted_but_absent`` sees it;
    the wrong metric is caught instead by ``unmatched_observed``.  That is why
    all three travel together and why none of them is the score.  Under the
    Pawley fit (WP-2011) the wrong metric's background stays near the truth, so
    the fitted-background count sees its displaced lines too (14 of 28); the Le
    Bail fit's sank, and that count read 0.

    The bars are qualitative on purpose (``most``, ``some``, ``many``) — the
    exact counts are noise-seed-dependent and quoted in the module docstring,
    whereas what must not regress is the *separation*.
    """
    validation = validate_by_lebail(_candidate(TRUE_A * factor), lab6_pattern,
                                   _instrument())
    assert validation.status == "converged"
    assert validation.mode == "pawley"
    if expect_absent == 0:
        assert validation.predicted_but_absent == 0
    elif expect_absent == "some":
        assert validation.predicted_but_absent > 0
    else:
        assert validation.predicted_but_absent > 0.5 * validation.n_reflections
    if expect_unmatched == 0:
        assert validation.unmatched_observed == 0
    else:
        assert validation.unmatched_observed > 20
    assert len(validation.predicted_but_absent_two_theta) == \
        validation.predicted_but_absent


def test_the_validation_fits_a_supercell_as_well_as_its_parent(lab6_pattern):
    """Why ``rwp`` is silent on an oversized cell, pinned (WP-2011).

    The doubled cell predicts a line at every position the truth does, so a
    converged decomposition gives it the truth's fit and more freedom besides.
    One Le Bail pass read 0.354 against 0.234 here: a gap its stall made, which
    the diagnostics quoted as if the lattice had.
    """
    truth = validate_by_lebail(_candidate(TRUE_A), lab6_pattern, _instrument())
    doubled = validate_by_lebail(_candidate(2.0 * TRUE_A), lab6_pattern,
                                 _instrument())
    assert doubled.rwp == pytest.approx(truth.rwp, rel=0.01), (
        doubled.rwp, truth.rwp)


def test_the_validation_record_names_its_fit_on_every_path(lab6_pattern,
                                                            monkeypatch):
    """``LeBailValidation.mode``'s two writers and its default (WP-2011).

    A record from before schema 0.60 has no key and was a Le Bail fit, so the
    default reads ``"lebail"``; both writers in ``validate_by_lebail`` name
    the fit that ran, the failed path included.
    """
    from rietx.refine import Refinement
    from rietx.schemas.indexing import LeBailValidation

    old = LeBailValidation.model_validate(
        {"rwp": 0.2, "gof": 1.5, "space_group": "P m -3 m", "n_reflections": 28})
    assert old.mode == "lebail"

    def raises(self, *a, **kw):
        raise ValueError("a fit the physics refuses")

    monkeypatch.setattr(Refinement, "fit", raises)
    failed = validate_by_lebail(_candidate(TRUE_A), lab6_pattern, _instrument())
    assert failed.status == "failed" and failed.mode == "pawley"


def test_layer0_unmatched_calc_cannot_serve_as_the_absent_detector(lab6_pattern):
    """The plan's own mechanism, measured false and pinned so it is not retried.

    Le Bail extraction sets each intensity from ``max(y_obs − y_bkg, 0)``, so a
    reflection predicted where there is nothing gets nothing and leaves **no
    negative residual to detect**; what Layer 0 finds instead is 5σ noise
    excursions near a tick.  It fires on the majority of the *certified* cell's
    reflections, which is the whole content of this test.
    """
    from rietx.refine import Refinement
    from rietx.report.layer0 import build_layer0

    cand = _candidate(TRUE_A)
    ref = Refinement(structure_from_candidate(cand), _instrument(), history=False)
    from rietx.indexing.workflow import validation_plan

    result = ref.fit(lab6_pattern, mode="lebail",
                     plan=validation_plan(cand, _instrument(),
                                          two_theta_max=float(
                                              max(lab6_pattern.two_theta))))
    layer0 = build_layer0(result)
    n_calc = len([u for u in layer0.unmatched if u.kind == "unmatched_calc"])
    n_refl = len([r for r in ref.reflection_table() if r.line == 0])
    assert n_calc > 0.4 * n_refl, (
        "if this ever separates a correct cell from an oversized one, "
        "re-measure before reaching for it — it did not in WP-1024")
    assert validate_by_lebail(cand, lab6_pattern,
                              _instrument()).predicted_but_absent == 0


# ----------------------------------------------------------------------
# end to end
# ----------------------------------------------------------------------
def test_index_pattern_recovers_the_cell_and_refutes_its_supercells(lab6_pattern):
    """The closed loop, picking its own peaks: pattern in, gated cell out."""
    result = index_pattern(
        data=lab6_pattern, instrument=_instrument(),
        spec=SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=1500.0, budget_seconds=120.0,
                        shift_allowance_deg=1e-9))
    best = result.best_or_none()
    assert best is not None, [c.confidence_caveats for c in result.candidates]
    assert best.cell[0] == pytest.approx(TRUE_A, abs=2e-4)
    assert best.confidence == "high"
    assert sorted(best.found_by) == sorted(engine_names())
    assert best.lebail is not None and best.lebail.predicted_but_absent == 0
    assert result.validated and result.search_complete == {"cubic": True}
    assert result.provenance.notes["engines"] == ", ".join(engine_names())

    # the supercells that index every observed line are refuted by the
    # pattern, not by the panel — this is the blind spot validation exists to
    # close.  Since C3 (thresholds 1.12) the refutation is the pairwise check
    # (``supercell_refuted``: the lines a superlattice adds over the truth,
    # that no extinction could remove, are seen no more often than chance)
    # and the line screen's absent count **caps**.  Only the checked subset
    # carries a verdict: validation costs a refinement each, so the rest must
    # say **not_validated** rather than look clean, and that half of the
    # claim is the one a widening candidate list can break.
    supercells = [c for c in result.candidates if c.volume > 2 * best.volume]
    assert supercells, "the F/I supercells should be proposed and then refuted"
    tested = [c for c in supercells if c.lebail is not None]
    assert tested, "no supercell reached validation at all"
    for cand in supercells:
        assert cand.confidence != "high"
        if cand.lebail is None:
            assert "not_validated" in cand.confidence_caveats
            continue
        assert cand.lebail.absent_source == "line_screen"
        assert "predicted_but_absent" in cand.confidence_caveats
        assert any(d.code == "INDEX_PREDICTED_BUT_ABSENT"
                   for d in cand.diagnostics)
    # the true superlattices — the 2a cells and the P description of the
    # a√2 I lattice — are refuted against their parents and grade low
    doubled = [c for c in supercells if c.cell[0] == pytest.approx(2 * TRUE_A, rel=1e-3)]
    assert len(doubled) >= 2
    for cand in doubled + [c for c in supercells if c.centring == "P"
                           and c.cell[0] == pytest.approx(np.sqrt(2) * TRUE_A, rel=1e-3)]:
        assert cand.confidence == "low"
        assert any(k.verdict == "refuted" for k in cand.supercell_checks or []), cand.cell
        assert "supercell_refuted" in cand.confidence_caveats
    # the a√2 I cell is no superlattice (primitive volume 2.83× the truth's):
    # it misses the 321 line and predicts three lines P has none at (M = 7,
    # 15, 23), so neither direction of the containment check is asked and
    # the screen's two windowed absences cap it at medium — what a true
    # cell reads on lab data (C3: magnetite 2) and so never a
    # refutation.  It ranks below the truth and cannot reach ``high``.
    (root2,) = [c for c in supercells if c.centring == "I"
                and c.cell[0] == pytest.approx(np.sqrt(2) * TRUE_A, rel=1e-3)]
    assert root2.confidence == "medium"
    assert root2.confidence_caveats == ["predicted_but_absent"]
    assert root2.lebail.predicted_but_absent_uncancellable_in_window >= 1
    assert result.candidates.index(root2) > result.candidates.index(best)
    # the density compared across candidates (#941's follow-up), written by
    # the run: the truth is the cleanest (excess 0), the a√2 I cell carries
    # its windowed absences over and above it, which the raw count shares
    # with magnetite's and PbSO₄'s true cells
    assert best.lebail.predicted_but_absent_excess_in_window == 0.0
    assert root2.lebail.predicted_but_absent_excess_in_window == pytest.approx(
        root2.lebail.predicted_but_absent_uncancellable_in_window)


def test_a_peaks_only_run_abstains_by_declaration(cubic_peaks):
    """No pattern ⇒ no whole-profile test ⇒ nothing reaches ``high``.

    The *result* abstains rather than one field being quietly downgraded, which is
    why ``INDEX_NOT_VALIDATED`` is a result-level diagnostic and not a note on a
    candidate.
    """
    result = index_pattern(
        cubic_peaks,
        spec=SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=1500.0, budget_seconds=120.0,
                        shift_allowance_deg=1e-9))
    assert result.candidates and result.best_or_none() is None
    assert not result.validated
    top = result.candidates[0]
    assert top.cell[0] == pytest.approx(TRUE_A, abs=2e-3)
    assert top.confidence == "medium"
    assert top.confidence_caveats == ["not_validated"]
    codes = {d.code for d in result.diagnostics}
    assert {"INDEX_NOT_VALIDATED", "INDEX_ABSTAINED"} <= codes


def test_a_short_clean_list_is_searched_ranked_and_capped():
    """The fluorite defect in miniature (WP-1043): fifteen clean cubic lines
    are fifteen-fold over-determined for a one-parameter metric, and the
    pre-1043 gate refused to search them because twenty is where the classical
    figures are *scored*.  Now the search runs — restricted to the systems
    ``MIN_LINES_PER_DOF`` supports — the reduced panel ranks, each absent
    figure carries its reason, and the ``fom_panel_reduced`` caveat caps the
    grade instead of a refusal standing in front of the answer."""
    peaks = _peak_list((TRUE_A,) * 3 + (90.0,) * 3, two_theta_max=100.0)
    assert len(peaks.usable()) < PEAK_MIN_USABLE_LINES
    result = index_pattern(
        peaks, spec=SearchSpec(systems=("cubic", "monoclinic"), min_d_axis=2.0,
                               max_d_axis=12.0, max_volume=1500.0,
                               budget_seconds=120.0, shift_allowance_deg=1e-9))
    # searched, not abstained — and only where the line count supports it:
    # monoclinic needs 20 lines at 5 per DOF, so the request is narrowed
    assert result.quality.supports_indexing
    assert result.systems_searched == ["cubic"]
    codes = {d.code for d in result.diagnostics}
    assert "INDEX_DATA_INSUFFICIENT" not in codes
    assert "INDEX_PANEL_REDUCED" in codes
    # ranked by the reduced panel, the truth first, reasons on the report
    assert result.candidates
    top = result.candidates[0]
    assert top.cell[0] == pytest.approx(TRUE_A, abs=2e-3)
    names = [f.name for f in top.fom]
    assert "m20" not in names and "f_n" not in names
    assert "indexed_fraction" in names
    assert set(result.quality.fom_undefined) == {"m20", "f_n"}
    # capped, uniformly: the grade is a field on the answer, not a gate in
    # front of it — and ``high`` stays exactly as unreachable as before
    for cand in result.candidates:
        assert "fom_panel_reduced" in cand.confidence_caveats
    assert result.best_or_none() is None

    # the evidence view agrees with the result it projects, by construction
    ev = result.evidence()
    assert ev.fom_undefined == result.quality.fom_undefined
    assert set(ev.fom_ranked) == set(names)
    assert set(ev.candidates[0].fom) == set(ev.fom_ranked)
    assert all(any(c.name == "fom_panel_reduced" and c.kind == "capping"
                   for c in cand.caveats)
               for cand in ev.candidates)


def test_restriction_honors_an_explicit_unsupported_request():
    """Two edges of :func:`_restrict_to_supported`, asserted on the function.

    A caller whose declared systems share *nothing* with the supported set is
    not silently handed an empty search — the same never-overridden rule as
    ``_adopt_measured_shift`` — and at or above the scoring bar the spec is
    untouched even when a declared system is under-determined, because that is
    the measured pre-1043 behaviour every acceptance row was quoted on."""
    from types import SimpleNamespace

    below_bar = SimpleNamespace(fom_undefined={"m20": "…", "f_n": "…"},
                                systems_supported=["cubic", "tetragonal"])
    no_overlap = SearchSpec(systems=("monoclinic",))
    assert _restrict_to_supported(no_overlap, below_bar) is no_overlap

    at_bar = SimpleNamespace(fom_undefined={},
                             systems_supported=["cubic"])
    unrestricted = SearchSpec()
    assert _restrict_to_supported(unrestricted, at_bar) is unrestricted

    overlap = SearchSpec(systems=("cubic", "monoclinic"))
    assert _restrict_to_supported(overlap, below_bar).systems == ("cubic",)


def test_the_evidence_view_is_a_projection_with_caveat_kinds():
    """WP-1043: the gate's inputs, serialized — not a second copy of them.

    The refuting/capping split lived only in ``INDEX_REFUTING_CAVEATS``, a
    package constant no JSON consumer can see, so the serialized answer could
    name ``supercell_refuted`` and ``not_validated`` in the same list
    without saying that one argues against the cell and the other only says a
    question was never asked (``predicted_but_absent`` was the refuting
    example until thresholds 1.12 made it capping).  ``evidence()`` computes the view from the live
    fields on each call, so the two representations cannot disagree."""
    from typing import get_args

    from rietx.refine import _VERSION
    from rietx.schemas.common import Provenance
    from rietx.schemas.indexing import IndexingEvidence

    refuted = _candidate(
        TRUE_A, confidence="medium",
        confidence_caveats=["predicted_but_absent", "not_validated"],
        lebail=LeBailValidation(rwp=0.379, gof=2.1, space_group="P m -3 m",
                                n_reflections=153, predicted_but_absent=117,
                                unmatched_observed=0))
    unreached = _candidate(
        4.9, confidence="medium", confidence_caveats=["fom_panel_reduced"],
        lebail=None, fom=[])
    result = IndexingResult(
        candidates=[refuted, unreached], engines_run=sorted(engine_names()),
        systems_searched=["cubic"], search_complete={"cubic": True},
        validated=True, wavelength=LAM, n_usable_lines=17,
        provenance=Provenance(package_version=_VERSION,
                              created_utc="2026-08-07T00:00:00Z"))

    ev = result.evidence()
    assert [c.index for c in ev.candidates] == [0, 1]
    kinds = {c.name: c.kind for c in ev.candidates[0].caveats}
    assert kinds == {"predicted_but_absent": "capping",     # 1.12: caps (C3)
                     "not_validated": "capping"}
    assert ev.candidates[1].caveats[0].kind == "capping"

    # the three whole-profile figures travel together, and an unreached
    # validation is None — absent for cause, never zero
    first = ev.candidates[0]
    assert (first.validated, first.lebail_rwp, first.predicted_but_absent,
            first.unmatched_observed) == (True, 0.379, 117, 0)
    second = ev.candidates[1]
    assert (second.validated, second.lebail_rwp, second.predicted_but_absent,
            second.unmatched_observed) == (False, None, None, None)

    # panel membership comes from the first candidate that carries one
    assert ev.fom_ranked == [f.name for f in refuted.fom]
    assert ev.candidates[0].fom == {f.name: f.value for f in refuted.fom}
    assert ev.systems_searched == ["cubic"]

    # every member of the closed vocabulary gets a kind, and the partition is
    # exactly the refuting constant — so a new caveat cannot arrive unkinded
    all_caveats = _candidate(TRUE_A,
                             confidence_caveats=sorted(get_args(IndexCaveat)))
    every = {c.name: c.kind
             for c in IndexingResult(
                 candidates=[all_caveats], provenance=result.provenance,
             ).evidence().candidates[0].caveats}
    assert {n for n, k in every.items() if k == "refuting"} \
        == set(INDEX_REFUTING_CAVEATS)

    # the view is a schema: it survives the JSON round trip intact
    assert IndexingEvidence.model_validate_json(ev.model_dump_json()) == ev


@pytest.mark.slow
def test_a_restricted_search_is_not_a_verdict_about_the_specimen():
    """A search over three systems says nothing about the other four.

    This is the withdrawn multiphase claim made permanent.  Measured (tag
    ``guillemot-study``, check C): a two-parameter engine scores 47-60 % on
    single-phase orthorhombic/monoclinic patterns, 82-100 % on genuinely
    tetragonal or hexagonal ones and 69 % on a real mixture — **the bands
    overlap**, so a coverage score cannot tell a multiphase pattern from a
    single-phase one of lower symmetry than the engine reaches.  So the report
    names what it did not search, and nothing anywhere claims a second phase.
    """
    peaks = _peak_list((7.0, 8.0, 9.0, 90.0, 90.0, 90.0), "P m m m",
                       two_theta_max=45.0)
    # 900 s is a runaway guard, not a timer, sized the way
    # test_indexing_engines.BUDGET_SECONDS was on 2026-07-30 and for the same
    # reason.  The row below needs the orthorhombic search to *find* the cell,
    # so a budget the machine can miss turns that into an assertion about load:
    # 60 s serial against the old 180 s is a 3x margin, and under -n auto this
    # row was measured at 129-169 s, up to 94 % of its own guard.
    common = dict(min_d_axis=2.0, max_d_axis=12.0, max_volume=1500.0,
                  budget_seconds=900.0, shift_allowance_deg=1e-9)

    restricted = index_pattern(
        peaks, spec=SearchSpec(systems=("cubic", "tetragonal", "hexagonal"),
                               **common))
    assert "orthorhombic" not in restricted.systems_searched
    assert set(restricted.systems_searched) == {"cubic", "tetragonal",
                                               "hexagonal"}
    not_covered = next(d for d in restricted.diagnostics
                       if d.code == "INDEX_SYSTEMS_NOT_COVERED")
    assert "orthorhombic" in not_covered.where

    # **No code means "multiphase", and codes are what an agent branches on.**
    # Asserted on the vocabulary rather than by scanning the prose, because the
    # prose deliberately *contains* the word — INDEX_SYSTEMS_NOT_COVERED's own
    # suggestion warns against exactly this reading, and a text scan cannot tell a
    # warning from a claim.
    codes = ({d.code for d in restricted.diagnostics}
             | {d.code for c in restricted.candidates for d in c.diagnostics})
    assert codes, "a restricted search must say what it did not cover"
    assert not any("PHASE" in code for code in codes), codes
    assert restricted.best_or_none() is None

    # the same list, with the right system in scope: the cell is there all along
    found = index_pattern(peaks, spec=SearchSpec(systems=("orthorhombic",),
                                                 **common))
    assert found.candidates, "the orthorhombic truth must be reachable"
    axes = sorted(found.candidates[0].cell[:3])
    assert axes == pytest.approx([7.0, 8.0, 9.0], abs=2e-3)


def _monoclinic_engine_candidate(engine_cell, centring="P"):
    """A candidate fitted, as an engine would, in the setting it arrived at."""
    from rietx.indexing.engines import EngineCandidate
    from rietx.indexing.qspace import refine_candidate

    group = f"{centring} 1 2/m 1"
    refl = generate_reflections(group, engine_cell, LAM, 100.0)
    order = np.argsort(np.asarray(refl.d))[::-1]
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d)[order])))
    peaks = PeakList.from_positions(tt, LAM, two_theta_esd=0.005)
    hkl = np.asarray(refl.hkl, dtype=np.float64)[order]
    fit = refine_candidate(peaks.q(), peaks.q_esd(), hkl, system="monoclinic")
    cand = EngineCandidate(fit=fit, system="monoclinic", centring=centring,
                           engine="svd", hkl=hkl, line_index=np.arange(len(tt)),
                           n_lines=len(tt))
    return cand, peaks


def test_a_monoclinic_candidate_is_reported_in_its_conventional_setting():
    """WP-1923 (issue #779): the engine's β = 81.78° is reported as the
    conventional 98.22°, af and the esds re-set with it, and the engine's own
    cell and the change of basis kept beside it."""
    from rietx.indexing.engines import provisional_payload, to_cell_candidate
    from rietx.indexing.qspace import cell_esds
    from rietx.indexing.reduce import af_map

    cand, peaks = _monoclinic_engine_candidate(
        (4.541, 4.884, 10.198, 90.0, 81.78, 90.0))
    out = to_cell_candidate(cand, peaks)
    assert out.cell == pytest.approx((4.541, 4.884, 10.198, 90.0, 98.22, 90.0),
                                     abs=1e-6)
    assert out.engine_cell == pytest.approx(tuple(cand.fit.cell), rel=1e-12)
    assert out.change_of_basis == ((-1, 0, 0), (0, -1, 0), (0, 0, 1))
    assert np.allclose(out.af, af_map(out.change_of_basis) @ cand.fit.af,
                       rtol=1e-12)
    # a sign flip of a and b moves no esd
    assert np.allclose(out.cell_esd, cand.fit.cell_esd, rtol=1e-9)
    assert out.lattice_group == "P 1 2/m 1"
    assert out.volume == pytest.approx(cand.fit.volume, rel=1e-12)
    assert provisional_payload([cand])[0]["cell"] == pytest.approx(
        list(out.cell), abs=1e-6)

    # a C cell keeps its centring, and a mixing step re-derives the esds
    cand, peaks = _monoclinic_engine_candidate(
        (9.0, 5.0, 12.0, 90.0, 140.0, 90.0), centring="C")
    out = to_cell_candidate(cand, peaks)
    assert out.centring == "C" and out.lattice_group == "C 1 2/m 1"
    assert out.cell == pytest.approx((9.0, 5.0, 7.7159, 90.0, 91.4298, 90.0),
                                     abs=1e-4)
    assert out.change_of_basis == ((1, 0, 0), (0, 1, 0), (1, 0, 1))
    t = af_map(out.change_of_basis)
    assert np.allclose(out.cell_esd, cell_esds(t @ cand.fit.af,
                                               t @ cand.fit.cov_af @ t.T))

    # already conventional: the identity, recorded rather than left unasked
    cand, peaks = _monoclinic_engine_candidate(
        (4.541, 4.884, 10.198, 90.0, 98.22, 90.0))
    out = to_cell_candidate(cand, peaks)
    assert out.change_of_basis == ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert out.engine_cell == out.cell


def test_the_fallback_panel_is_scored_at_the_resolution_like_the_search_panel(
        monkeypatch):
    """``to_cell_candidate`` builds its own panel when the engine brought none
    (a prior, or a ``_panel_for`` that raised); it must ask the reversed member
    the way ``_panel_for`` does, with the peak list's widths.  Spied, because on
    a clean list the two members' values can coincide."""
    from rietx.indexing import engines

    cand, peaks = _monoclinic_engine_candidate(
        (4.541, 4.884, 10.198, 90.0, 98.22, 90.0))
    assert not cand.fom
    calls = []
    real = engines.fom_panel
    monkeypatch.setattr(engines, "fom_panel",
                        lambda *a, **kw: calls.append(kw.get("fwhm_obs")) or real(*a, **kw))
    engines.to_cell_candidate(cand, peaks)
    engines._panel_for(cand, peaks, 3.0)
    assert len(calls) == 2 and all(w is not None for w in calls)
    assert np.array_equal(calls[0], calls[1])
