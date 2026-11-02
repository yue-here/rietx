"""WP-1045 — analogue priors steer the search and never gate it.

The three rules of ``indexing/priors.py``, each pinned: a prior reorders and
seeds (its system jumps the queue, its metric seeds the stochastic engine)
and never injects a candidate past the engines; it narrows *order*, never the
box; and a prior used is recorded (``INDEX_PRIOR_USED``).  The acceptance
sentence is tested literally: a poisoned prior costs time, never truth.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.indexing import index_pattern
from rietx.indexing.engines import SearchSpec
from rietx.indexing.priors import (
    PRIOR_FINDER,
    cell_systems,
    prior_systems,
    spacegroup_prior,
)
from tests.test_indexing_engines import CASES, synthetic_peaks

#: A tetragonal cell that indexes nothing in the cubic fixture — the poisoned
#: analogue.  Inside the declared box on purpose (axes within 2-12 Å, volume
#: under the ceiling), so it reaches the *data* check and is refuted there;
#: a prior outside the box is refused before any check, which is a different
#: rule (never widen) with its own assertion below.  Its system still jumps
#: the queue, which is the whole cost.
WRONG_PRIOR = (5.31, 5.31, 9.40, 90.0, 90.0, 90.0)


# ----------------------------------------------------------------------
# classification
# ----------------------------------------------------------------------
@pytest.mark.parametrize("cell,expected", [
    ((4.16, 4.16, 4.16, 90.0, 90.0, 90.0), ("cubic",)),
    ((3.78, 3.78, 9.51, 90.0, 90.0, 90.0), ("tetragonal",)),
    ((4.76, 4.76, 12.99, 90.0, 90.0, 120.0), ("hexagonal", "trigonal")),
    ((5.4, 5.4, 5.4, 61.0, 61.0, 61.0), ("trigonal",)),
    ((7.0, 8.0, 9.0, 90.0, 90.0, 90.0), ("orthorhombic",)),
    ((8.9, 16.4, 7.1, 90.0, 93.8, 90.0), ("monoclinic",)),
    ((5.2, 6.1, 7.3, 91.2, 95.4, 103.1), ("triclinic",)),
])
def test_cell_shape_classification(cell, expected):
    assert cell_systems(cell) == expected


def test_spacegroup_prior_resolves_system_and_centring():
    assert spacegroup_prior("R -3 c") == ("trigonal", "R")
    assert spacegroup_prior("I a -3 d") == ("cubic", "I")
    with pytest.raises(ValueError, match="unknown space group"):
        spacegroup_prior("Q 5")


def test_prior_systems_jump_but_never_widen():
    spec = SearchSpec(systems=("cubic", "tetragonal"),
                      prior_cells=(WRONG_PRIOR,),
                      prior_spacegroups=("P 21/c",))
    # monoclinic is named by the space-group prior but not requested: a prior
    # never widens the box, so it may not resurrect the system
    assert prior_systems(spec) == ["tetragonal"]


# ----------------------------------------------------------------------
# the acceptance sentence: a poisoned prior costs time, never truth
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("indexing-priors")
def test_a_wrong_prior_changes_no_rank_and_no_grade():
    """Run the same search with and without a deliberately wrong prior: the
    ranked cells and their grades are identical, the *order of search* is
    what changed (the prior's system ran first), and the result records that
    the prior was tried and refuted."""
    peaks, true_cell = synthetic_peaks("cubic")
    base = dict(min_d_axis=2.0, max_d_axis=12.0, max_volume=1500.0,
                shift_allowance_deg=1e-9, budget_seconds=120.0)
    spec_plain = SearchSpec(systems=("cubic", "tetragonal"), **base)
    spec_prior = SearchSpec(systems=("cubic", "tetragonal"),
                            prior_cells=(WRONG_PRIOR,), **base)

    plain = index_pattern(peaks, spec=spec_plain, preset="full",
                          engines=("trial_error",))
    steered = index_pattern(peaks, spec=spec_prior, preset="full",
                            engines=("trial_error",))

    assert plain.candidates, "the synthetic cubic list must index"
    assert [c.cell for c in plain.candidates] == \
        [c.cell for c in steered.candidates]
    assert [c.confidence for c in plain.candidates] == \
        [c.confidence for c in steered.candidates]
    # what did change is when things were searched: the prior's system first
    assert steered.systems_searched[0] == "tetragonal"
    assert plain.systems_searched[0] == "cubic"

    prior_diags = [d for d in steered.diagnostics
                   if d.code == "INDEX_PRIOR_USED"]
    assert len(prior_diags) == 1
    assert "refuted" in prior_diags[0].message
    assert not any(d.code == "INDEX_PRIOR_USED" for d in plain.diagnostics)
    # the steering is in the record: the notes carry the declared prior
    assert "prior_cells" in steered.provenance.notes
    assert "prior_cells" not in plain.provenance.notes


@pytest.mark.xdist_group("indexing-priors")
def test_a_stated_lattice_one_engine_found_does_not_outgrade_the_truth():
    """#1308 (WP-2082): a prior merged into one engine's candidate is still
    one engine.  The planted lattice is F cubic; the stated prior is the
    primitive cell at the same metric, which predicts mixed-parity lines the
    data lack.  Under ``svd`` alone, counting the prior lifted the P lattice
    to ``medium`` while the planted F stayed ``low``.  Stating the prior must
    change no grade, and the truth is never graded below the prior's
    lattice."""
    a = 4.5
    peaks, _ = synthetic_peaks("cubic", sg="F m -3 m",
                               cell=(a, a, a, 90.0, 90.0, 90.0))
    base = dict(systems=("cubic", "tetragonal"), min_d_axis=2.0,
                max_d_axis=12.0, max_volume=1500.0, shift_allowance_deg=1e-9,
                budget_seconds=120.0)
    prior = (a, a, a, 90.0, 90.0, 90.0)

    def grades(spec):
        res = index_pattern(peaks, spec=spec, preset="full", engines=("svd",))
        # the whole cell in the key: two tetragonal candidates sharing ``a``
        # must not overwrite each other's grade
        out = {(c.centring, c.system, tuple(round(x, 3) for x in c.cell)):
               (c.confidence, c.found_by) for c in res.candidates}
        assert len(out) == len(res.candidates)
        return out

    plain = grades(SearchSpec(**base))
    steered = grades(SearchSpec(**base, prior_cells=(prior,)))
    truth, stated = ("F", "cubic", prior), ("P", "cubic", prior)
    assert truth in steered and stated in steered
    assert PRIOR_FINDER in steered[stated][1], (
        "the fixture no longer merges the prior into svd's own P candidate")
    order = ["low", "medium", "high"]
    assert order.index(steered[truth][0]) >= order.index(steered[stated][0])
    assert {k: g for k, (g, _) in plain.items()} == \
        {k: g for k, (g, _) in steered.items() if k in plain}


@pytest.mark.xdist_group("indexing-priors")
def test_a_correct_prior_surfaces_truth_in_the_first_streamed_shortlist():
    """The other half of the acceptance: a correct analogue prior (the true
    cell perturbed by a few hundred ppm) jumps its system to the front, so
    the first ``consensus:<system>`` snapshot on the ladder is the prior's
    system and already carries the truth."""
    peaks, true_cell = synthetic_peaks("tetragonal")
    prior = tuple(v * (1.0003 if i < 3 else 1.0)
                  for i, v in enumerate(true_cell))
    events: list = []
    res = index_pattern(
        peaks, events=events.append, preset="full",
        spec=SearchSpec(systems=("cubic", "tetragonal"),
                        prior_cells=(prior,), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=1500.0, shift_allowance_deg=1e-9,
                        budget_seconds=120.0))
    snaps = [e["data"] for e in events if e["kind"] == "stage_end"
             and e["data"].get("consensus")]
    assert snaps and snaps[0]["system"] == "tetragonal", (
        "the prior's system must stream its shortlist first")
    first = snaps[0]["candidates"]
    assert any(np.allclose(c["cell"][:3], true_cell[:3], rtol=2e-3)
               for c in first), "the truth is not in the first shortlist"
    # and the final answer still carries it, found by engines — the prior
    # merged into the engines' own candidate rather than shadowing it
    top = res.candidates[0]
    assert np.allclose(np.asarray(top.cell), np.asarray(true_cell), rtol=2e-3)
    assert set(top.found_by) & {"dichotomy", "svd", "trial_error"}


def test_a_prior_outside_the_box_is_refused_before_any_check():
    """The never-widen rule: a prior whose axis leaves the declared range is
    refused at declaration — recorded, not smuggled in and not checked."""
    from rietx.indexing.priors import build_prior_candidates

    peaks, _cell = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic", "tetragonal"), min_d_axis=2.0,
                      max_d_axis=12.0,
                      prior_cells=((5.31, 5.31, 13.72, 90.0, 90.0, 90.0),))
    cands, reports = build_prior_candidates(peaks, spec, None)
    assert cands == []
    assert "never widens the box" in reports[0].reason
    assert reports[0].box == {"max_d_axis": 15.0}


def test_a_prior_past_both_edges_names_both():
    """A rerun naming only one edge would be refused at the other."""
    from rietx.indexing.priors import build_prior_candidates

    peaks, _cell = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("tetragonal",), min_d_axis=4.0, max_d_axis=12.0,
                      prior_cells=((3.2, 3.2, 13.72, 90.0, 90.0, 90.0),))
    _cands, reports = build_prior_candidates(peaks, spec, None)
    assert reports[0].box == {"max_d_axis": 15.0, "min_d_axis": 2.0}
    assert "max_d_axis=15, min_d_axis=2" in reports[0].reason


def test_a_prior_refused_at_the_box_is_a_warning_naming_the_value():
    """The caller's knowledge going unused is a warning, and its suggestion is
    the value to pass, not a sentence to decode (WP-1510)."""
    from rietx.indexing.priors import build_prior_candidates, prior_used_diagnostic

    peaks, _cell = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic", "tetragonal"), min_d_axis=2.0,
                      max_d_axis=12.0,
                      prior_cells=((5.31, 5.31, 13.72, 90.0, 90.0, 90.0),
                                   (5.31, 5.31, 5.31, 90.0, 90.0, 90.0)))
    _cands, reports = build_prior_candidates(peaks, spec, None)
    d = prior_used_diagnostic(reports, [], [])
    assert d.level == "warning"
    assert "SearchSpec(max_d_axis=15)" in d.suggestion
    assert d.value == 1.0

    inside = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        prior_cells=((5.31, 5.31, 5.31, 90.0, 90.0, 90.0),))
    _cands, reports = build_prior_candidates(peaks, inside, None)
    assert prior_used_diagnostic(reports, [], []).level == "info"


# ----------------------------------------------------------------------
# a prior-only candidate: appended, provenanced, never confident
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("indexing-priors")
def test_a_prior_only_candidate_is_appended_with_provenance():
    """Engines that found nothing (their budget refuses the search) leave the
    stated cell as the only candidate: it enters *after* the ranked list
    (here: as the whole list), carries ``found_by == ['prior']``, and cannot
    be ``high`` — the ordinary agreement caveat grades it down with no new
    gate vocabulary."""
    peaks, true_cell = synthetic_peaks("cubic")
    res = index_pattern(
        peaks, preset="full", engines=("trial_error",),
        spec=SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=17.0,  # admits no cubic cell of this data
                        shift_allowance_deg=1e-9,
                        prior_cells=(true_cell,), budget_seconds=30.0))
    priors_only = [c for c in res.candidates
                   if c.found_by == [PRIOR_FINDER]]
    # the prior's own volume is held to the caller's box too — max_volume
    # excludes the true cell, so the prior must NOT have entered
    assert not priors_only, (
        "a prior outside the declared box was smuggled in: the box binds "
        "priors exactly as it binds the engines")
    diag = [d for d in res.diagnostics if d.code == "INDEX_PRIOR_USED"]
    assert len(diag) == 1

    res2 = index_pattern(
        peaks, preset="full", engines=("trial_error",),
        spec=SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                        max_volume=1500.0, shift_allowance_deg=1e-9,
                        prior_cells=(true_cell,),
                        n_search_lines=2))
    # n_search_lines=2 keeps the engine's enumeration trivial while the
    # prior check still runs over every usable line; whether the engine also
    # finds the cell, the prior's fate is recorded either way
    diag2 = [d for d in res2.diagnostics if d.code == "INDEX_PRIOR_USED"]
    assert len(diag2) == 1
    tail = [c for c in res2.candidates if PRIOR_FINDER in c.found_by]
    for cand in tail:
        assert cand.confidence != "high"
        if cand.found_by == [PRIOR_FINDER]:
            assert "engines_disagree" in cand.confidence_caveats


# ----------------------------------------------------------------------
# the seed: a stated basin is tried before the random ladder
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("indexing-priors")
def test_the_prior_seeds_svds_starting_basin(monkeypatch):
    """``search_svd`` runs one deliberate trial per prior before its random
    ladder, so the truth is found from the seed alone.

    The ladder is starved **structurally**, by setting this system's Table-2
    control pair to zero random trials, and the budget is a runaway guard at
    30 s.  Before WP-1128 the starvation was a 0.05 s budget, which is the
    shape ``tests/CLAUDE.md`` forbids: it read as a timer, and what it timed
    was the machine.  ``volume_window``'s κ probes ran between the budget's
    start and its first check — 2-3 ms idle here, 63 ms measured on a
    4×-oversubscribed machine — so on a loaded CI worker the budget expired
    with ``calls=0`` and the seed never ran at all (two red Linux nightlies,
    2026-08-21/22).  With ``n1 = 0`` the sentence below is true by
    construction rather than by arithmetic about how long a call takes.
    """
    from rietx.indexing.qspace import af_from_cell
    from rietx.indexing.reduce import same_lattice
    from rietx.indexing.svd import CONTROL, search_svd

    monkeypatch.setitem(CONTROL, "monoclinic", (0, 1))
    peaks, true_cell = synthetic_peaks("monoclinic")
    _sg, _cell, _tt, (min_d, max_d), vol = CASES["monoclinic"]
    spec = SearchSpec(systems=("monoclinic",), min_d_axis=min_d,
                      max_d_axis=max_d, max_volume=vol,
                      shift_allowance_deg=1e-9,
                      prior_cells=(true_cell,), budget_seconds=30.0)
    res = search_svd(peaks, spec=spec)
    # the ladder made no calls, so every call was a prior's: one per centring
    assert res.stats["monoclinic.calls"] == float(
        len(spec.centrings_for("monoclinic"))), (
        "the ladder was not starved — this test would then be measuring the "
        "random search rather than the seed")
    # same_lattice, never cell tuples: a monoclinic answer legitimately comes
    # back in another setting (the WP-1040 trap, hit again writing this test —
    # the seed's first find was (11.01, 16.408, 8.875, β=139.7°), the same
    # lattice as (8.875, 16.408, 7.137, β=93.84°))
    truth_af = af_from_cell(true_cell)
    assert any(same_lattice(af_from_cell(c.cell), truth_af)[0]
               for c in res.candidates), (
        "the seeded start did not reach the stated basin — with the random "
        "ladder starved to zero trials the seed is the only thing that ran")


# ----------------------------------------------------------------------
# two settings of one lattice, and a cell you can read by name (WP-1510)
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("indexing-priors")
def test_two_settings_of_one_prior_lattice_are_one_candidate():
    """Declared with β and with 180° − β, one monoclinic lattice is checked as
    two priors, named twice in ``INDEX_PRIOR_USED``, and reported as one row."""
    peaks, cell = synthetic_peaks("monoclinic")
    a, b, c, al, be, ga = cell
    spec = SearchSpec(systems=("monoclinic",),
                      prior_cells=(tuple(cell), (a, b, c, al, 180.0 - be, ga)))
    res = index_pattern(peaks, spec=spec, engines=())
    assert len(res.candidates) == 1
    assert res.candidates[0].found_by == ["prior"]
    used = next(d for d in res.diagnostics if d.code == "INDEX_PRIOR_USED")
    assert used.message.count("entered unconfirmed") == 2


def test_a_candidate_cell_reads_by_name_and_converts():
    from rietx.schemas.indexing import CellCandidate

    cand = CellCandidate(cell=(8.875, 16.408, 7.137, 90.0, 93.84, 90.0),
                         cell_esd=(0.0,) * 6, system="monoclinic")
    assert (cand.a, cand.b, cand.c) == (8.875, 16.408, 7.137)
    assert (cand.alpha, cand.beta, cand.gamma) == (90.0, 93.84, 90.0)
    assert cand.to_cell().lengths_angles() == cand.cell
    # properties, not fields: the JSON shape is the tuple it always was
    assert "beta" not in cand.model_dump()
