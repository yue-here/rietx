"""#1374 — under a declared ceiling, each (engine × system) unit gets a share.

The rule (ruled 2026-11-17): a unit runs for at most
``min(budget_seconds, search_seconds / n_engines)``, where ``search_seconds``
is the ceiling, less the validation reserve when validation runs
(:func:`rietx.indexing.engines.unit_share_seconds`).  With no ceiling,
``budget_seconds`` alone bounds a unit, as before.

The fast rows are deterministic: stub engines advance a fake clock by their
own budget, so "a unit runs to its budget" is a logic device here and nothing
is a load sensor (tests/CLAUDE.md).  The two ``slow`` rows are #1374's table
on the real engines, counted in CPU seconds as the issue measured them.
"""

from __future__ import annotations

import types

import pytest

from rietx.indexing import engines as engines_mod
from rietx.indexing import index_pattern
from rietx.indexing.engines import (
    DEFAULT_BUDGET_SECONDS,
    QUICK_TOTAL_BUDGET_SECONDS,
    SYSTEM_ORDER,
    VALIDATION_RESERVE_FRACTION,
    EngineResult,
    SearchSpec,
    budget_exhausted_diagnostic,
    incomplete_diagnostic,
    unit_share_seconds,
)
from tests.test_indexing_engines import synthetic_peaks

pytestmark = pytest.mark.xdist_group("indexing-scheduler")


@pytest.fixture(scope="module")
def cubic_peaks():
    peaks, _cell = synthetic_peaks("cubic", two_theta_max=150.0)
    return peaks


class _Clock:
    """``engines``' clock, advanced only by the stubs."""

    def __init__(self):
        self.now = 0.0

    def module(self):
        import time

        clock = self

        class _Time(types.ModuleType):
            def monotonic(self):
                return clock.now

            def __getattr__(self, name):
                return getattr(time, name)

        return _Time("time")


def _stub(name, log, clock, *, incomplete=False):
    """An engine that runs its unit to its budget (or to the run's ceiling,
    whichever comes first) and records the budget it was handed."""
    def run(peaks, *, spec, quality=None, cancel=None, progress=None):
        system = spec.systems[0]
        log.append((name, system, spec.budget_seconds))
        step = spec.budget_seconds
        remaining = getattr(cancel, "remaining", None)
        if remaining is not None:
            step = min(step, remaining)
        clock.now += step
        result = EngineResult(engine=name)
        result.systems_searched = (system,)
        result.search_complete[system] = not incomplete
        result.stats[f"{system}.seconds"] = step
        if incomplete:
            result.diagnostics.append(incomplete_diagnostic(
                name, [system], spec.budget_seconds))
        return result
    return run


@pytest.fixture
def stubs(monkeypatch):
    """Three stub engines on a fake clock; returns (log, clock, install)."""
    clock = _Clock()
    monkeypatch.setattr(engines_mod, "time", clock.module())
    log: list = []

    def install(names=("e1", "e2", "e3"), **kw):
        reg = {n: _stub(n, log, clock, **kw) for n in names}
        monkeypatch.setattr(engines_mod, "_REGISTRY", reg)
        monkeypatch.setattr(engines_mod, "_DESCRIPTIONS",
                            {n: "stub" for n in names})
    return log, clock, install


# ----------------------------------------------------------------------
# the share
# ----------------------------------------------------------------------
def test_a_ceiling_shares_the_search_among_the_engines(cubic_peaks, stubs):
    """#780's shape: ``budget_seconds`` raised to ten times the ceiling.
    Without the share the first unit held all 90 s and e2 and e3 never ran;
    with it each engine runs its 30 s on the first system."""
    log, _clock, install = stubs
    install()
    res = index_pattern(cubic_peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal"), budget_seconds=900.0,
        total_budget_seconds=90.0), validate=False)
    assert log == [("e1", "cubic", 30.0), ("e2", "cubic", 30.0),
                   ("e3", "cubic", 30.0)]
    assert res.engines_run == ["e1", "e2", "e3"]
    exhausted = next(d for d in res.diagnostics
                     if d.code == "INDEX_BUDGET_EXHAUSTED")
    assert "not reached: tetragonal" in exhausted.where
    assert ("ran at most 30 s, the search's part of the ceiling shared over "
            "3 engines" in exhausted.suggestion)


def test_one_named_engine_gets_the_whole_ceiling(cubic_peaks, stubs):
    """The dissenter's route: a caller who wants one engine's exhaustive
    answer names it, and its share is the whole search time."""
    log, _clock, install = stubs
    install(names=("e1",))
    index_pattern(cubic_peaks, spec=SearchSpec(
        systems=("cubic",), budget_seconds=900.0, total_budget_seconds=90.0),
        validate=False)
    assert log == [("e1", "cubic", 90.0)]


def test_no_ceiling_leaves_budget_seconds_alone(cubic_peaks, stubs):
    """``preset="full"`` with no declared ceiling: every unit gets the
    caller's ``budget_seconds``, as before #1374."""
    log, _clock, install = stubs
    install(incomplete=True)
    res = index_pattern(cubic_peaks, spec=SearchSpec(
        systems=("cubic", "tetragonal"), budget_seconds=900.0),
        preset="full", validate=False)
    assert log and {b for _n, _s, b in log} == {900.0}
    advice = [d.suggestion for d in res.diagnostics
              if d.code == "INDEX_SEARCH_INCOMPLETE"]
    assert advice and all(a.startswith("Raise budget_seconds") for a in advice)
    assert "INDEX_BUDGET_EXHAUSTED" not in {d.code for d in res.diagnostics}


def test_a_budget_under_the_share_is_unchanged(cubic_peaks, stubs):
    """The default slice under a ceiling whose share is larger: the units get
    ``budget_seconds`` itself, and the incomplete advice is today's."""
    log, _clock, install = stubs
    install(incomplete=True)
    res = index_pattern(cubic_peaks, spec=SearchSpec(
        systems=("cubic",), total_budget_seconds=QUICK_TOTAL_BUDGET_SECONDS),
        validate=False)
    assert log and {b for _n, _s, b in log} == {DEFAULT_BUDGET_SECONDS}
    advice = [d.suggestion for d in res.diagnostics
              if d.code == "INDEX_SEARCH_INCOMPLETE"]
    assert advice and all(a.startswith("Raise budget_seconds") for a in advice)


def test_the_quick_share_sits_above_the_default_slice():
    """Why a default run is unchanged: the ``quick`` ceiling less its
    validation reserve, over three engines, is 34 s, above the 30 s slice."""
    search = QUICK_TOTAL_BUDGET_SECONDS * (1.0 - VALIDATION_RESERVE_FRACTION)
    share = unit_share_seconds(search, 3)
    assert share == pytest.approx(34.0)
    assert share > DEFAULT_BUDGET_SECONDS
    assert unit_share_seconds(None, 3) is None


# ----------------------------------------------------------------------
# what the reader is told
# ----------------------------------------------------------------------
def test_a_shared_unit_is_told_to_raise_the_ceiling(cubic_peaks, stubs):
    """A unit stopped by its share: a larger ``budget_seconds`` would change
    nothing there, so the remedy names the ceiling and the engines."""
    _log, _clock, install = stubs
    install(incomplete=True)
    res = index_pattern(cubic_peaks, spec=SearchSpec(
        systems=("cubic",), budget_seconds=900.0, total_budget_seconds=300.0),
        validate=False)
    advice = [d.suggestion for d in res.diagnostics
              if d.code == "INDEX_SEARCH_INCOMPLETE"]
    assert advice
    for a in advice:
        assert "Raise budget_seconds" not in a
        assert a.startswith("Each unit's 100 s is the ceiling's search time "
                            "shared over 3 engines, so raise "
                            "total_budget_seconds or name fewer engines")


def test_the_exhausted_suggestion_is_unchanged_without_a_share():
    base = budget_exhausted_diagnostic(120.0, [], [], ["triclinic"], 0)
    assert base.suggestion == (
        "Read systems_searched and search_complete before you treat an "
        "absence as evidence. Raise total_budget_seconds, or narrow systems= "
        "to where the answer can live.")
    shared = budget_exhausted_diagnostic(120.0, [], [], ["triclinic"], 0,
                                         unit_share=40.0, n_engines=3)
    assert shared.suggestion.startswith(base.suggestion + " ")
    assert shared.message == base.message and shared.where == base.where


# ----------------------------------------------------------------------
# #1374's rows on the real engines, CPU-clocked
# ----------------------------------------------------------------------
def _cpu_clock(monkeypatch):
    """``tests.repro_780.cpu_clock``, undone after the test."""
    import time

    class _CpuTime(types.ModuleType):
        monotonic = staticmethod(time.process_time)

        def __getattr__(self, name):
            return getattr(time, name)

    monkeypatch.setattr(engines_mod, "time", _CpuTime("time"))


@pytest.mark.slow
def test_1374_cases_monoclinic_all_systems_finds_the_cell(monkeypatch):
    """#1374's row "CASES monoclinic, all, T = 30": with each unit at the
    ceiling, svd's orthorhombic unit held it and the run returned nothing;
    with the share the monoclinic truth is found.  30 s of CPU, one BLAS
    thread, as the issue measured.  On macOS arm64, ``[dev]``, 2026-11-19,
    dichotomy's monoclinic unit found it in 4.8 s of its 10 s share; T = 60
    no longer separates the two rules there, since svd's orthorhombic unit
    took 16 s of CPU, not the issue's 49.

    Sized for a macOS arm64 core (M-series, 2026-11-21) and checked on Linux
    x86_64 (i9-14900K, Python 3.12, one pinned core, 2026-11-23).  The
    monoclinic unit alone, on the same list, under a CPU budget: on the Mac
    dichotomy and svd each found the cell at 2 s; on Linux svd found it at
    1 s and dichotomy between 1 and 2 s.  Against the unit's 10 s share that
    is a margin of 5 or more on both machines.  A core twice as slow still
    has about 2.5.  The whole row took 31.8-33.5 s of wall clock against its
    30 s ceiling on Linux (31.2 s on the Mac): it always spends the ceiling,
    so that figure is not a margin."""
    from tests.test_indexing_engines import CASES, assert_same_lattice, spec_for

    _cpu_clock(monkeypatch)
    peaks, cell = synthetic_peaks("monoclinic")
    spec = spec_for("monoclinic", systems=tuple(SYSTEM_ORDER),
                    budget_seconds=30.0, total_budget_seconds=30.0)
    res = index_pattern(peaks, spec=spec, preset="full", validate=False)
    mono = [c for c in res.candidates if c.system == "monoclinic"]
    assert mono, [(c.system, c.cell) for c in res.candidates]
    assert_same_lattice(mono[0].cell, CASES["monoclinic"][1])


@pytest.mark.slow
def test_1374_780_monoclinic_gains_a_second_finder(monkeypatch):
    """#1374's row "#780, mono": with each unit at the ceiling, dichotomy
    held it and its cell had one finder; with the share svd also finds it,
    and the cell can reach the agreement gate.

    The ceiling is 120 s, not the issue's 60 s (#1700 review, round 2): the
    share is then 40 s over three engines.  The monoclinic unit alone, on this
    list, under a CPU budget: svd found the cell at 2 s, dichotomy not at 6 s
    and at 8 s, on macOS arm64 (M-series, 2026-11-21) and on Linux x86_64
    (i9-14900K, Python 3.12, one pinned core, 2026-11-23) alike.  Against a
    40 s share svd has a margin of 20 or more and dichotomy, the assertion's
    limiting finder, 5 (it found the cell by 8 s); at 60 s the share was 20 s
    and dichotomy's margin 2.5 to 3.3.  A core more than about 5 times slower
    fails this row.  GitHub's ubuntu-latest, which runs the nightly ``slow``
    tier, is not measured: a core 1.5 to 2 times slower leaves a margin of
    2.5 to 3.3.  The row spends its whole ceiling, so its wall clock
    (about 122 s on the Mac) is not a margin.  It still separates the rules:
    without the share dichotomy's unit holds the ceiling and svd finds nothing
    (the revert check of 2026-11-24 is in the WP's handover log)."""
    from tests.repro_780 import CELL, peaks, spec
    from tests.test_indexing_engines import assert_same_lattice

    _cpu_clock(monkeypatch)
    res = index_pattern(peaks(), spec=spec(120.0), preset="full",
                        validate=False)
    assert res.candidates
    top = res.candidates[0]
    assert_same_lattice(top.cell, CELL)
    assert {"dichotomy", "svd"} <= set(top.found_by), top.found_by
