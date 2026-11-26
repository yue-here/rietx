"""WP-1042 — the system-major scheduler.

Deterministic throughout: stub engines drive the unit order and the mid-run
stop, and the deferred-probe rows empty the search domain with a volume window
— a *logic* device — so nothing here is a load sensor (tests/CLAUDE.md).  The
wall-clock behaviour of a binding ceiling stays where WP-1037 put it, in
``test_indexing_ceiling.py``.
"""

from __future__ import annotations

import pytest

from rietx.indexing import engines as engines_mod
from rietx.indexing import index_pattern
from rietx.indexing.engines import (
    EngineResult,
    SearchSpec,
    merge_engine_units,
)
from rietx.optimize.cancel import CancelToken
from rietx.schemas.common import Diagnostic
from tests.test_indexing_engines import synthetic_peaks

pytestmark = pytest.mark.xdist_group("indexing-scheduler")


@pytest.fixture(scope="module")
def cubic_peaks():
    """Exact cubic positions, 150° range — the same 30-line list the ceiling
    tests use, enough for the quality gate."""
    peaks, cell = synthetic_peaks("cubic", two_theta_max=150.0)
    assert len(peaks.usable()) >= 20
    return peaks, cell


def _stub(name, log, *, cancel_on=None, token=None):
    """A registered-contract engine that records (engine, system) and claims
    what it entered — the scheduler restricts ``spec.systems`` to one system
    per unit, and the stub asserts that contract by reading ``systems[0]``."""
    def run(peaks, *, spec, quality=None, cancel=None, progress=None):
        assert len(spec.systems) == 1
        system = spec.systems[0]
        log.append((name, system))
        if cancel_on == (name, system) and token is not None:
            token.cancel()
        result = EngineResult(engine=name)
        result.systems_searched = (system,)
        result.search_complete[system] = True
        result.stats[f"{system}.seconds"] = 0.0
        return result
    return run


def _patch_registry(monkeypatch, stubs):
    monkeypatch.setattr(engines_mod, "_REGISTRY", dict(stubs))
    monkeypatch.setattr(engines_mod, "_DESCRIPTIONS",
                        {name: "stub" for name in stubs})


# ----------------------------------------------------------------------
# the schedule
# ----------------------------------------------------------------------
def test_units_run_system_major(cubic_peaks, monkeypatch):
    """Every engine finishes one system before any engine starts the next —
    the whole WP in one list equality."""
    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log),
                                  "e2": _stub("e2", log)})
    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal", "monoclinic")))
    assert log == [("e1", "cubic"), ("e2", "cubic"),
                   ("e1", "tetragonal"), ("e2", "tetragonal"),
                   ("e1", "monoclinic"), ("e2", "monoclinic")]
    assert res.engines_run == ["e1", "e2"]
    assert res.search_complete == {"cubic": True, "tetragonal": True,
                                   "monoclinic": True}


def test_a_mid_system_stop_reads_truncated_not_complete(cubic_peaks,
                                                        monkeypatch):
    """The strict completeness rule: a system one engine never entered while
    the others finished it reads incomplete.  Before WP-1042 it read "searched
    to completion" — the engines that entered it had finished — and nothing in
    the result named the engine whose silence there was not evidence."""
    peaks, _cell = cubic_peaks
    log: list = []
    token = CancelToken()
    _patch_registry(monkeypatch, {
        "e1": _stub("e1", log),
        "e2": _stub("e2", log, cancel_on=("e2", "tetragonal"), token=token),
        "e3": _stub("e3", log)})
    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal", "monoclinic")), cancel=token)
    # e3 never entered tetragonal, and monoclinic was never reached at all
    assert log == [("e1", "cubic"), ("e2", "cubic"), ("e3", "cubic"),
                   ("e1", "tetragonal"), ("e2", "tetragonal")]
    assert res.systems_searched == ["cubic", "tetragonal"]
    assert res.search_complete == {"cubic": True, "tetragonal": False}
    # a user cancellation is never a budget statement (WP-1037's rule holds)
    assert "INDEX_BUDGET_EXHAUSTED" not in {d.code for d in res.diagnostics}


def test_an_expired_ceiling_names_every_engine_and_system(cubic_peaks,
                                                          monkeypatch):
    """The deterministic end of the budget path: a pre-expired ceiling runs
    nothing, and the diagnostic partitions the request exactly."""
    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log)})
    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal"), total_budget_seconds=1e-9))
    assert log == []
    assert res.engines_run == [] and res.systems_searched == []
    exhausted = next(d for d in res.diagnostics
                     if d.code == "INDEX_BUDGET_EXHAUSTED")
    assert "engines not run: e1" in exhausted.where
    assert "not reached: cubic, tetragonal" in exhausted.where


# ----------------------------------------------------------------------
# the fold
# ----------------------------------------------------------------------
def test_merge_engine_units_folds_disjoint_systems():
    u1 = EngineResult(engine="e", systems_searched=("cubic",),
                      search_complete={"cubic": True},
                      stats={"cubic.seconds": 1.0, "candidates.raw": 3.0,
                             "shift_allowance_deg": 0.05})
    u2 = EngineResult(engine="e", systems_searched=("tetragonal",),
                      search_complete={"tetragonal": False},
                      stats={"tetragonal.seconds": 2.0, "candidates.raw": 4.0,
                             "shift_allowance_deg": 0.05})
    merged = merge_engine_units([u1, u2])
    assert merged.engine == "e"
    assert merged.systems_searched == ("cubic", "tetragonal")
    assert merged.search_complete == {"cubic": True, "tetragonal": False}
    # summed, not last-write-wins: each unit counted its own harvest
    assert merged.stats["candidates.raw"] == 7.0
    assert merged.stats["shift_allowance_deg"] == 0.05
    assert merged.stats["cubic.seconds"] == 1.0


def test_merge_engine_units_dedups_diagnostics_and_refuses_misuse():
    same = dict(level="info", code="X", message="same words")
    u1 = EngineResult(engine="e", diagnostics=[Diagnostic(**same)])
    u2 = EngineResult(engine="e", diagnostics=[Diagnostic(**same)])
    assert len(merge_engine_units([u1, u2]).diagnostics) == 1
    with pytest.raises(ValueError):
        merge_engine_units([])
    with pytest.raises(ValueError):
        merge_engine_units([EngineResult(engine="a"),
                            EngineResult(engine="b")])


# ----------------------------------------------------------------------
# presets: quick is the default, and the registry is held in bijection
# ----------------------------------------------------------------------
def test_preset_registry_and_info_are_in_bijection():
    """The PLAN_PRESETS/PLAN_INFO pattern one registry over: a preset added
    without a row of guidance is a preset nobody can be told when to use."""
    from rietx.indexing.engines import (
        DEFAULT_SEARCH_PRESET,
        QUICK_TOTAL_BUDGET_SECONDS,
        SEARCH_PRESET_INFO,
        SEARCH_PRESETS,
    )

    assert set(SEARCH_PRESETS) == set(SEARCH_PRESET_INFO)
    assert DEFAULT_SEARCH_PRESET in SEARCH_PRESETS
    assert SEARCH_PRESETS["quick"] == QUICK_TOTAL_BUDGET_SECONDS
    assert SEARCH_PRESETS["full"] is None
    for info in SEARCH_PRESET_INFO.values():
        assert info.title and info.description and info.when_to_use
        lo, hi = info.typical_seconds
        assert 0.0 < lo < hi


def test_quick_is_the_default_and_never_overrides_a_declared_ceiling(
        cubic_peaks, monkeypatch):
    """The flip (WP-1042): a run that declares nothing gets quick's ceiling
    and records preset='quick'; a declared spec ceiling is never overridden
    and records 'custom'; 'full' bounds nothing and says so by omission."""
    from rietx.indexing.engines import QUICK_TOTAL_BUDGET_SECONDS

    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log)})

    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)))
    assert res.preset == "quick"
    assert res.provenance.notes["preset"] == "quick"
    assert res.provenance.notes["total_budget_seconds"] == (
        f"{QUICK_TOTAL_BUDGET_SECONDS:g}")

    res = index_pattern(peaks, spec=SearchSpec(
        systems=("cubic",), total_budget_seconds=3600.0))
    assert res.preset == "custom"
    assert res.provenance.notes["total_budget_seconds"] == "3600"

    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)),
                        preset="full")
    assert res.preset == "full"
    assert "total_budget_seconds" not in res.provenance.notes

    with pytest.raises(ValueError, match="unknown preset .fastest.; preset takes"):
        index_pattern(peaks, preset="fastest")


def test_the_search_stops_a_validation_reserve_early(cubic_peaks, monkeypatch):
    """WP-1045: when whole-profile validation is going to run under a ceiling,
    the search's deadline ends ``VALIDATION_RESERVE_FRACTION`` early.

    Measured before the reserve existed: on three heavy qarr patterns the
    search consumed the whole 120 s ceiling on every run and validation got
    **zero** fits, while a fit costs 0.3-1.9 s against 11-60 s for a trailing
    search system.  The ceiling itself never moves — this is scheduling
    within it — and when nothing will validate (no pattern, or
    ``validate=False``) the search keeps every second.
    """
    from rietx.indexing.engines import VALIDATION_RESERVE_FRACTION
    from tests.test_refine_synthetic import perturbed_models, synthesize

    peaks, _cell = cubic_peaks
    seen: list[float] = []

    def spy(p, *, spec, quality=None, cancel=None, progress=None):
        seen.append(float("inf") if cancel is None else cancel.remaining)
        result = EngineResult(engine="e1")
        result.systems_searched = tuple(spec.systems)
        result.search_complete[spec.systems[0]] = True
        return result

    _patch_registry(monkeypatch, {"e1": spy})
    data = synthesize()
    _structure, instrument = perturbed_models()
    boundary = 100.0 * (1.0 - VALIDATION_RESERVE_FRACTION)

    index_pattern(peaks, data=data, instrument=instrument,
                  spec=SearchSpec(systems=("cubic",),
                                  total_budget_seconds=100.0))
    assert seen and seen[0] <= boundary + 1.0

    seen.clear()
    index_pattern(peaks, data=data, instrument=instrument, validate=False,
                  spec=SearchSpec(systems=("cubic",),
                                  total_budget_seconds=100.0))
    assert seen and seen[0] > boundary + 1.0


def test_a_single_engine_run_says_what_low_means(cubic_peaks, monkeypatch):
    """INDEX_SINGLE_ENGINE is a diagnostic, not a caveat: the low it explains
    is produced by grade() structurally, before any caveat is consulted."""
    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log),
                                  "e2": _stub("e2", log)})
    res = index_pattern(peaks, engines=("e1",),
                        spec=SearchSpec(systems=("cubic",)))
    assert "INDEX_SINGLE_ENGINE" in {d.code for d in res.diagnostics}
    both = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)))
    assert "INDEX_SINGLE_ENGINE" not in {d.code for d in both.diagnostics}


# ----------------------------------------------------------------------
# the deferred probe
# ----------------------------------------------------------------------
def test_probe_false_skips_the_in_engine_probe(cubic_peaks, monkeypatch):
    """The engine half of the deferral: ``probe=False`` suppresses the
    in-engine ask even on an empty harvest; the default keeps it."""
    import rietx.indexing.trial_error as te

    peaks, _cell = cubic_peaks
    calls: list = []
    monkeypatch.setattr(te, "_dominant_zone_probe",
                        lambda *a, **k: calls.append(1))
    # a volume window that admits no cell: the harvest is empty by logic
    spec = SearchSpec(systems=("cubic",), max_volume=15.5)
    res = te.search_trial_error(peaks, spec=spec, probe=False)
    assert not res.candidates and calls == []
    te.search_trial_error(peaks, spec=spec)
    assert calls == [1]


def test_a_completed_system_streams_graded_candidates(cubic_peaks):
    """The streaming contract, on real engines: a completed system's snapshot
    rides the ladder as its own ``consensus:<system>`` unit, each candidate in
    the WP-1043 evidence shape and graded conservatively (nothing can stream
    ``high`` — validation and ambiguity are still open questions); raw unit
    candidates ride ``provisional`` with no confidence at all; and every
    ladder emission carries ``elapsed_seconds``.  No new event kind anywhere."""
    peaks, _cell = cubic_peaks
    events: list = []
    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)),
                        events=events.append)
    assert res.candidates, "the synthetic cubic list must index"
    assert {e["kind"] for e in events} <= {"index_start", "stage_start",
                                           "stage_end", "index_end"}
    ends = [e["data"] for e in events if e["kind"] == "stage_end"]
    snaps = [d for d in ends if d.get("consensus")]
    assert [d["system"] for d in snaps] == ["cubic"]
    assert snaps[0]["n_candidates"] >= 1
    for cand in snaps[0]["candidates"]:
        assert cand["confidence"] in ("low", "medium")
        assert {"cell", "system", "caveats", "found_by"} <= set(cand)
    unit_ends = [d for d in ends if d.get("engine") and not d.get("probe")]
    assert unit_ends
    for d in unit_ends:
        for p in d.get("provisional", []):
            assert p["provisional"] and "confidence" not in p
    ladder = [e["data"] for e in events if e["kind"].startswith("stage_")]
    assert ladder and all("elapsed_seconds" in d for d in ladder)


def test_remaining_seconds_streams_only_under_a_ceiling(cubic_peaks,
                                                        monkeypatch):
    """The other progress fact: ``remaining_seconds`` appears exactly when a
    whole-run ceiling was declared.  Stub engines, so the only ladder units
    are the snapshots — which also pins that a snapshot with no candidates is
    still a well-formed emission."""
    peaks, _cell = cubic_peaks
    log: list = []
    _patch_registry(monkeypatch, {"e1": _stub("e1", log)})
    with_ceiling: list = []
    index_pattern(peaks, spec=SearchSpec(systems=("cubic",),
                                         total_budget_seconds=3600.0),
                  events=with_ceiling.append)
    without: list = []
    index_pattern(peaks, spec=SearchSpec(systems=("cubic",)), preset="full",
                  events=without.append)
    lad = [e["data"] for e in with_ceiling if e["kind"].startswith("stage_")]
    assert lad and all("remaining_seconds" in d and "elapsed_seconds" in d
                       for d in lad)
    lad = [e["data"] for e in without if e["kind"].startswith("stage_")]
    assert lad and all("remaining_seconds" not in d for d in lad)
    assert all(d["n_candidates"] == 0 and d["candidates"] == []
               for d in lad if d.get("consensus") and "n_candidates" in d)


def test_the_scheduler_asks_the_probe_once_over_entered_systems(
        cubic_peaks, monkeypatch):
    """The scheduler half: per-system units silence their own probes, and the
    run asks once at the end — over the systems the engine entered, only when
    the merged harvest is empty."""
    import rietx.indexing.trial_error as te

    peaks, _cell = cubic_peaks
    calls: list = []

    def fake_probe(peaks_, spec_, q_all, sigma, tt_all, tt_max, systems,
                   quality, cancel, *, progress=None):
        calls.append(tuple(systems))
        return None

    monkeypatch.setattr(te, "_dominant_zone_probe", fake_probe)
    res = index_pattern(peaks, engines=("trial_error",),
                        spec=SearchSpec(systems=("cubic", "tetragonal"),
                                        max_volume=15.5))
    assert res.candidates == []
    assert calls == [("cubic", "tetragonal")]
    assert "trial_error.probe.seconds" in res.engine_stats
