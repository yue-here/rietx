"""The v1.1 benchmark harness is a script that runs (WP-1111).

`examples/bench_refinement.py` is the **measurement authority** every later
speed WP quotes for its before/after, so a harness that has silently stopped
building one of its cases is worse than no harness: the missing row reads as a
case that was covered.  These tests are the guard against that, and they are
carefully *not* an acceptance suite.

**What is asserted, and what deliberately is not.**  Nothing here asserts a
wall-clock number.  A budget in a test is a runaway guard, never a timer
(CLAUDE.md § Commands), and the harness's whole point is that its numbers are
machine-relative — a CI box asserting one would be pinning the box, not the
package.  What is asserted is *structure*: every case key is distinct, the
registry's builders are reachable, the simulated trigger case still carries the
peak count that is its reason to exist, and the counting scaffold puts back the
name it patched.

WP-1404 added a second axis, configurations, and it is held to the same three
properties one section down — distinct keys, a control that records nothing,
and every patch put back on both exits.  The counted half of WP-1404's
acceptance is not here but in `test_telemetry.py`, where the recorder is: this
module knows about the harness, not about what the harness measures.

**Why only the cheap cases are built.**  Building a case is not free — `nac`
runs a Le Bail fit to make its warm start, and `trigger-series` simulates ten
4 165-point patterns — so this module builds the two that cost about a second
and checks the rest by construction.  Running every case is what running the
harness *is*, and that belongs to a session that means to measure something.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "examples" / "bench_refinement.py"


@pytest.fixture(scope="module")
def bench():
    """The harness imported as a module.

    By path rather than by package, because `examples/` is not one — the same
    reason `test_examples.py` runs its scripts as subprocesses.  The import
    itself is the first assertion: the module inserts `tests/` on `sys.path`
    at import time so its case builders can reach the acceptance fixtures, and
    a broken insert would fail here rather than in a bench run nobody is
    watching.
    """
    spec = importlib.util.spec_from_file_location("bench_refinement", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_refinement"] = module
    spec.loader.exec_module(module)
    return module


def test_case_keys_are_distinct_and_listable(bench):
    keys = [case.key for case in bench.CASES]
    assert len(keys) == len(set(keys)), f"duplicate case key in {keys}"
    assert all(case.blurb for case in bench.CASES)
    # `--list` is the only path a reader takes before committing 20 minutes
    assert bench.main(["--list"]) == 0


def test_an_unknown_case_is_refused_by_name(bench):
    """A typo must not silently select every case — the failure mode is a
    20-minute run the person did not ask for."""
    with pytest.raises(SystemExit):
        bench.main(["--cases", "nac,not-a-case"])


def test_the_trigger_case_carries_the_trigger_peak_count(bench):
    """Case 4's reason to exist is its shape, so its shape is what is pinned.

    WP-1109's trigger was ~4 165 points and roughly an order of magnitude more
    peaks than any shipped baseline; the WP's acceptance is "~1000+ (line,
    reflection) pairs".  Compiled here without fitting, which is cheap — the
    expensive half of building this case is evaluating the truth model to make
    the pattern, and a peak count needs no intensities.
    """
    structure = rx.Structure(phases=bench._trigger_phases())
    instrument = bench._trigger_instrument(truth=True)
    tt = bench._TRIGGER_TT
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.ones_like(tt).tolist())
    model = compile_model(structure, instrument, blank)

    assert len(tt) == 4165, "the trigger grid is 4 165 points by construction"
    pairs = sum(int(ph.win.shape[0] * ph.win.shape[1]) for ph in model.phases)
    assert pairs > 1000, f"trigger case carries only {pairs} (line, reflection) pairs"
    assert len(model.phases) == 4
    # Cu Kα doublet, both lines windowed — a single-line trigger case would
    # halve the pair count without changing the phase list
    assert all(ph.win.shape[0] == 2 for ph in model.phases)


def test_the_trigger_pattern_is_deterministic(bench):
    """Same seed, same counts — otherwise two "repeats" are two datasets and
    the wall-clock range is not a range of anything."""
    a = bench._trigger_pattern(seed=7, drift=0.0)
    b = bench._trigger_pattern(seed=7, drift=0.0)
    assert np.array_equal(np.asarray(a.intensity), np.asarray(b.intensity))
    c = bench._trigger_pattern(seed=8, drift=0.0)
    assert not np.array_equal(np.asarray(a.intensity), np.asarray(c.intensity))


def test_the_bigcell_cases_carry_the_large_cell_shape(bench):
    """WP-2317's cases exist for their shape: a real 12.2 × 36.7 × 3.95 Å
    cell (Nb₁₈W₁₆O₉₃, COD 2107344) with its 43 published sites, and more
    (line, reflection) pairs than ``trigger``.

    The structure is pinned to the vendored file because the maintainer
    asked for a real one in place of probe 1's invented atoms (2026-11-27).
    The structural case's preparation must tie the eight co-sited Nb/W
    pairs: one tie for the fixed pair's Biso, three for each of the seven
    others (two site-symmetry steps and the Biso).  Compiled on a blank
    pattern, so nothing here evaluates the model.
    """
    from test_large_cell_refinement import tie_co_sited

    phase = bench._bigcell_phase(0.0)
    assert phase.space_group.replace(" ", "") == "Pbam"
    assert (phase.cell.a.value, phase.cell.b.value, phase.cell.c.value) == \
        pytest.approx((12.195, 36.73999, 3.951))
    assert len(phase.atoms) == 43
    structure = rx.Structure(phases=[phase])
    tt = np.arange(5.0, 90.0, 0.02)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.ones_like(tt).tolist())
    model = compile_model(structure, bench._bigcell_instrument(truth=True), blank)
    pairs = sum(int(ph.win.shape[0] * ph.win.shape[1]) for ph in model.phases)
    assert pairs > 1500, f"the 90° large cell carries only {pairs} pairs"

    ref = rx.Refinement(rx.Structure(phases=[bench._bigcell_phase(5e-4)]),
                        bench._bigcell_instrument(truth=False), history=False)
    assert tie_co_sited(ref) == 22
    keys = {c.key: c for c in bench.CASES}
    assert {"bigcell-structural", "bigcell-pawley", "bigcell-pawley-120",
            "bigcell-lebail"} <= set(keys)


def test_a_baseline_case_builds_a_compiled_model(bench):
    """`cpd-1a` is the cheapest real-data case to build: a read plus the scale
    seeding.  Compiling its setup is what every timed repeat starts from."""
    try:
        setup = bench._cpd_1a()
    except (FileNotFoundError, OSError) as exc:
        pytest.skip(str(exc))
    pts, pairs, width = bench._shape(setup)
    assert pts == 7251
    assert pairs > 0 and width > 0
    assert setup.patterns is None, "cpd-1a is a single fit, not a series"


def test_the_real_series_case_is_the_acceptance_chain(bench):
    """`cpd-series` is WP-1127's counterexample family, and cheap to *build*.

    Unlike `trigger-series`, which simulates ten 4 165-point patterns, this one
    is eight reads and a scale seeding, so the build is a smoke test rather
    than a measurement.  What is pinned is that it stayed the acceptance
    suite's chain: the eight sample-1 mixtures in `SAMPLE1` order, the same
    7 251-point grid `cpd-1a` reports, and two rows differing in `refit` and
    nothing else — the trade WP-0505 and WP-1110 measured opposite ways is only
    readable if the two rows are otherwise the same fit.
    """
    try:
        single = bench._cpd_series()
        staged = bench._cpd_series_stages()
    except (FileNotFoundError, OSError) as exc:
        pytest.skip(str(exc))

    from test_acceptance_qpa_roundrobin import SAMPLE1

    assert single.patterns is not None and len(single.patterns) == len(SAMPLE1)
    assert len(single.patterns[0].two_theta) == 7251
    assert single.refit == "single" and staged.refit == "stages"
    assert [s.name for s in single.plan.stages] == [s.name for s in staged.plan.stages]
    assert len(single.structure.phases) == 3


def test_the_series_case_is_declared_as_one(bench):
    """A series case is recognised by `Setup.patterns`, which is what routes it
    to `refine_sequential` instead of `fit` — so the flag, not the key name, is
    the thing to pin."""
    series = [c for c in bench.CASES if c.key.endswith("-series")]
    assert series, "no series case in the registry"
    # built lazily: constructing it simulates ten patterns (~50 s), which is a
    # measurement, not a smoke test.  What is checked here is that the runner
    # dispatches on the declared flag.
    src = SCRIPT.read_text(encoding="utf-8")
    assert "if setup.patterns is not None:" in src
    assert "refine_sequential" in src


def test_the_counting_scaffold_restores_the_name_it_patched(bench):
    """The harness wraps `optimize.least_squares`'s scipy entry point to read
    `nfev`/`njev`.  A wrapper left in place after an exception would stack one
    wrapper per failed case and quietly double-count, so the restore is tested
    on both exits.
    """
    from rietx.optimize import least_squares as mod

    original = mod.least_squares
    with bench._counting(bench._Counts()):
        assert mod.least_squares is not original
    assert mod.least_squares is original

    with pytest.raises(RuntimeError):
        with bench._counting(bench._Counts()):
            raise RuntimeError("case blew up")
    assert mod.least_squares is original


# ----------------------------------------------------------------------
# the configuration axis (WP-1404)
# ----------------------------------------------------------------------
#
# The second axis exists because WP-1403 made recording the default, so an
# unconfigured bench run measures a *recorded* fit and would silently
# re-baseline every number this harness has printed.  Nothing here times
# anything either: what is asserted is that the configurations are distinct,
# that the control is the control, and that the scaffold puts back everything
# it patched — the same three properties `_counting` is held to one section up.


def test_configuration_keys_are_distinct_and_the_control_is_first(bench):
    """`_compare` ratios everything against `CONFIGS[0]`, so that row has to be
    the one that records nothing."""
    keys = [c.key for c in bench.CONFIGS]
    assert len(keys) == len(set(keys)), f"duplicate configuration key in {keys}"
    assert all(c.blurb for c in bench.CONFIGS)
    control = bench.CONFIGS[0]
    assert control.key == "off"
    assert not control.records and not control.stream and not control.drop_eval


def test_an_unknown_configuration_is_refused_by_name(bench):
    """A typo must not silently select the default and print a table whose rows
    say something the reader did not ask for."""
    with pytest.raises(SystemExit):
        bench.main(["--cases", "nac", "--configs", "record,not-a-config"])


def test_exactly_one_configuration_drops_events_and_it_is_a_scaffold(bench):
    """`no-eval` is not a knob the package has.

    It drops the `eval` line *and* stubs the decode that builds it, so it
    measures the ceiling of WP-1403's mitigations rather than any shipped
    behaviour.  A second configuration acquiring `drop_eval` would be a second
    scaffold whose row nobody had labelled, so the count is pinned at one.
    """
    scaffolds = [c for c in bench.CONFIGS if c.drop_eval]
    assert [c.key for c in scaffolds] == ["no-eval"]
    assert all(c.records for c in scaffolds), "a dropped eval needs a recorder"
    # the two `events=` rows carry no recorder: they are what a *caller* pays,
    # and a recorder underneath would price both at once
    assert [c.key for c in bench.CONFIGS if c.stream] == ["events-path", "live"]
    assert not any(c.records for c in bench.CONFIGS if c.stream)


def test_the_configuration_scaffold_restores_everything_it_patched(bench):
    """Both exits, for `_counting`'s reason, doubled.

    A leaked `RunRecorder` subclass or a leaked `_free_values` stub would apply
    to the *next* configuration in the same process, and the table would then
    compare two things that are not what their keys say — the one failure this
    harness cannot afford, because its output looks identical either way.
    """
    from rietx import runs
    from rietx.optimize import least_squares as ls_mod

    recorder, free_values = runs.RunRecorder, ls_mod._free_values
    scaffold = next(c for c in bench.CONFIGS if c.drop_eval)

    with bench._configured(scaffold, bench._Account()) as kwargs:
        assert runs.RunRecorder is not recorder
        assert ls_mod._free_values is not free_values
        assert kwargs["telemetry"] not in (None, False)
    assert runs.RunRecorder is recorder
    assert ls_mod._free_values is free_values

    with pytest.raises(RuntimeError):
        with bench._configured(scaffold, bench._Account()):
            raise RuntimeError("the case blew up mid-configuration")
    assert runs.RunRecorder is recorder
    assert ls_mod._free_values is free_values


def test_the_scratch_directory_is_measured_and_then_removed(bench, tmp_path):
    """The account is read before the temp directory goes, and the directory
    goes: a harness that left one behind per repeat would be a slow leak in a
    35-minute run."""
    account = bench._Account()
    control = bench.CONFIGS[0]
    with bench._configured(control, account) as kwargs:
        scratch = Path(kwargs["events"]) if kwargs.get("events") else None
        assert kwargs["telemetry"] is False
        assert scratch is None
    assert account.dir_bytes == 0 and account.lines == 0

    live = next(c for c in bench.CONFIGS if c.stream == "live")
    with bench._configured(live, bench._Account()) as kwargs:
        here = Path(kwargs["events"].dir)
        assert here.is_dir()
    assert not here.exists(), "the scratch directory outlived the run"


def test_the_counting_handle_counts_writes_and_flushes(bench, tmp_path):
    """The handle is what the recorder's log goes through, so it is where the
    bytes and the flush cadence are read rather than re-derived."""
    account = bench._Account()
    target = tmp_path / "events.jsonl"
    # the recorder opens its log this way, and this handle stands in for
    # it: without the pin, text mode makes `st_size` two bytes larger
    # than the count on Windows and the identity below is not the
    # handle's fault (WP-1439)
    with target.open("w", encoding="utf-8", newline="\n") as fh:
        handle = bench._CountingHandle(fh, account)
        handle.write('{"kind": "eval"}\n')
        handle.write('{"kind": "stage_end"}\n')
        handle.flush()
        assert handle.encoding == "utf-8"      # delegation, not reimplementation

    assert account.lines == 2
    assert account.bytes == target.stat().st_size
    assert account.flushes == 1
