"""WP-1111: the v1.1 refinement benchmark harness.

Run: ``.venv/bin/python examples/bench_refinement.py``

One command prints the table the **v1.1 milestone is judged by** — named
cases, wall-clock ranges, evaluation counts, per-stage iterations — so every
later speed WP quotes *this* harness for its before/after instead of inventing
its own measurement.  Nothing here changes production code, and that is a
requirement rather than an accident: a harness that lands in the same commit as
an optimisation can no longer measure it.

Read these four rules before quoting any number this script prints.

1. **Wall clock is a range, never a figure** (CLAUDE.md § Commands).  Each case
   is run ``--repeats`` times (default 3) and the *min and max* are printed.  A
   single number would invite comparison against a remembered one, and machine
   state moves these further than most changes do: a concurrent ``pytest -n
   auto`` inflated a 1.24 s fit to 4.78 s — 3.9× — during WP-1109.  **Run this
   on an idle machine, alone.**
2. **A comparison between arms is interleaved, never blocked**, and reports the
   minimum of N beside the median.  Blocked, each arm owns a contiguous slice of
   wall clock and any drift lands on one of them entire: WP-1404's matrix timed
   a telemetry path as *faster* than no telemetry at all, under control spreads
   of 11.4 and 13.2 %, and interleaving took those to 1.1-5.9 % and the
   impossibility away.  Two estimators of one quantity that disagree are still
   measuring the box.  ``main`` interleaves; a one-off script has to be told.
3. **Never compare across machines**, and never against a figure whose venv and
   platform are not stamped beside it.  This script stamps its own header with
   both, plus the package version and the numpy build, so a pasted table
   carries its own provenance.
4. **Rwp is an identity check, not the metric.**  It is printed so that two
   runs of the same case can be seen to be the *same fit*, and the repeats are
   compared for it; a speed change that moves Rwp is not a speed change.  The
   metric is wall clock, and the diagnostics are the evaluation counts.
5. **Every number carries its configuration.**  Since WP-1403 a fit records
   itself by default, so "the wall clock of ``cpd-2``" is no longer a complete
   statement — ``--configs`` says which fit was timed, every row prints its
   key, and a number quoted without one is ambiguous rather than merely
   imprecise.
6. **The counts come from scipy, the wall clock from this process.**  ``nfev``
   and ``njev`` are read off the ``OptimizeResult`` that
   ``rietx.optimize.least_squares`` gets back, by wrapping the module-level
   ``least_squares`` name for the duration of a run (see ``_counting``).  This
   is a measurement scaffold, not an API: the package records ``nfev`` per
   stage as ``StageResult.n_iterations`` and records ``njev`` nowhere, which is
   WP-1113's ground.  The wrapper costs one attribute read per solve and does
   not perturb the timing.

Cases
-----
The first three are the baselines WP-1109 ranked its candidates on, rebuilt
from the acceptance suites' own fixtures rather than from restated protocols —
so that when a number here disagrees with one there, the protocol is not among
the candidate explanations.

``nac-lebail`` 11-BM NAC, 1 phase, ``profile_only``, Le Bail mode, 22 003
             points.
``nac``      The Rietveld leg built on it: 2 phases, 6 stages, same points.  No
             FCJ (Debye-Scherrer at 0.414 Å), so windows are symmetric and the
             peak loop is dispatch-bound rather than node-bound.  Its Le Bail
             seed is built **once**, at setup, and is not timed.
             **WP-1109's 1.5-1.8 s NAC row is the two legs together** — split
             here because timing only the Rietveld leg against that row shows a
             2.4× discrepancy that is not a speed change.
``cpd-1a``   IUCr CPD round-robin sample 1a, 3 phases, Cu Kα doublet,
             ``qpa_plan`` (8 stages), 7 251 points.  **FCJ physics is off at
             every stage**, despite the lab optics: ``qarr_instrument``
             leaves both axial ratios at 0.0 and the plan frees only
             ``axial_sl``, and the aberration needs both positive.  Stages
             before ``lines_axial`` compile no quadrature node; from it on,
             cumulative freeing plus ``AXIAL_SIZING_FLOOR`` allocate nodes
             that evaluate as one-hot symmetric fallbacks — overhead, not
             asymmetry (measured by WP-1112's gate, which corrected this
             blurb).  The small-cell lab case; the FCJ case is ``trigger``.
``cpd-2``    The same instrument on sample 2 under the **QPA acceptance
             protocol** — 4 phases, 9 stages with texture — i.e.
             ``test_sample2_brucite_march_dollase``'s own fit.  This is the
             case WP-1109 profiled at 534 residual + 425 Jacobian evaluations,
             and it is *not* the same fit as the 4-phase ``mccusker_default``
             row in that WP's opening table.  Quote them separately.

The last two are the shape none of the shipped baselines covers, and they are
**simulated**: see the block comment above ``_TRIGGER_TT`` for exactly which
parts are literature and which are invented, and why nothing they print is a
structural claim.

``trigger``  4 phases with large low-symmetry cells, Cu Kα doublet + FCJ,
             4 165 points, 1 188 (line, reflection) pairs — an order of
             magnitude more peaks than the baselines above, fitted cold.
``trigger-series`` and ``trigger-series-stages``
             Ten copies of it with a 100 ppm/step cell ramp through
             ``refine_sequential``: one cold fit then nine warm starts, which
             is the workflow the milestone's ~1 s/pattern target names.  Both
             ``refit`` rungs are measured — see ``_trigger_series`` for why
             the saving one of them is quoted for was never measured at this
             width.

Runtime: the whole harness at the default three repeats is ~35 minutes, nearly
all of it the last three cases.  ``--cases`` selects; ``--list`` shows the
keys.

Configurations
--------------
WP-1404 added a second axis, and it exists because WP-1403 made **recording the
default**: every ``fit()`` in the wild now writes a run directory unless it is
declined, so an unconfigured bench run measures a *recorded* fit and would
silently re-baseline every number this harness has ever printed.  ``--configs``
is therefore explicit and defaults to ``off``, which is what the rows above
were measured under.

``off``          ``telemetry=False`` — no recorder, no events.  **The control**,
                 and the row every ratio is against.
``no-eval``      the recorder with its ``eval`` stream suppressed.  **A harness
                 scaffold, not a knob the package has**: it drops the line *and*
                 stubs out the decode that builds it, so what it prices is the
                 ceiling of WP-1403's mitigations 2 and 3 — the most a sink-side
                 thrift could ever buy.  Never quote it as a thing rietx does.
``record``       the shipping default: recorder attached at ``telemetry=<dir>``,
                 ``eval`` lines buffered, cancel token attached.  WP-1404's
                 original configurations 2 and 3 are this one row, WP-1405
                 having made the token unconditional; it priced the token itself
                 at 1.0036× by interleaving arms of one fit, which is a finer
                 instrument than this matrix.
``events-path``  ``events=<path>``, no recorder — WP-1401 measured this at
                 1.01-1.03×, so it is the bridge that says whether two sittings
                 are comparable at all.
``live``         ``events=LiveSession(dir)``, no recorder — what a user pays
                 today when they *do* ask for a live view.

Selecting more than one prints a comparison block per case: ratio of medians
against the control, the control's own repeat spread, and per configuration the
log lines, bytes, flush count and run-directory size.  ``nfev`` and ``Rwp`` are
checked against the control on every row, because the claim being tested is
that telemetry changed no number — a configuration that moved either is not a
slower fit but a different one, and its ratio means nothing.

A series case takes the axis only through ``telemetry=``: its ``events=`` is
already spent on the collector that reads per-pattern wall clock off the
ladder, so ``events-path`` and ``live`` are refused there by name.

Columns
-------
``pairs`` is the (emission line, reflection) pair count summed over phases —
the quantity peak-loop cost scales with, and the reason the shipped baselines
under-weight the trigger case: they carry a few hundred where it carries
~1000+.  ``win`` is the mean window width in points.  ``free`` is the union of
what the plan's stages actually freed, read off the result rather than
re-derived from the globs.  ``nfev``/``njev`` are whole-fit totals across every
stage; the per-stage ``n_iterations`` breakdown (scipy's nfev per stage) prints
under each case.

``--profile`` re-runs each selected case **once** under cProfile and prints the
top 10 by tottime.  Profiled wall clock is inflated and is never quoted as a
timing; the ranking is what it is for.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import platform
import pstats
import shutil
import statistics
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Callable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import rietx as rx  # noqa: E402
from rietx import _about, runs  # noqa: E402
from rietx.model.forward import compile_model  # noqa: E402
from rietx.sequential import FIRST_RUNG_FACTOR  # noqa: E402

# -- the counting scaffold -------------------------------------------------

class _Counts:
    """Whole-fit ``nfev``/``njev``, accumulated across a run's stages."""

    def __init__(self) -> None:
        self.nfev = 0
        self.njev = 0


class _counting:
    """Wrap ``optimize.least_squares``'s scipy entry point for one run.

    Reads ``nfev``/``njev`` off each returned ``OptimizeResult``.  Restores the
    original name on exit, including on an exception, so a failed case cannot
    leave the package patched for the next one.  ``solver="lm"`` does not route
    through this name (it has its own driver), which is why the printed count
    says ``-`` rather than 0 when nothing was seen.
    """

    def __init__(self, counts: _Counts) -> None:
        self.counts = counts

    def __enter__(self) -> _Counts:
        from rietx.optimize import least_squares as mod

        self._mod = mod
        self._orig = mod.least_squares

        def wrapper(*args, **kwargs):
            res = self._orig(*args, **kwargs)
            self.counts.nfev += int(getattr(res, "nfev", 0) or 0)
            self.counts.njev += int(getattr(res, "njev", 0) or 0)
            return res

        mod.least_squares = wrapper
        return self.counts

    def __exit__(self, *exc) -> None:
        self._mod.least_squares = self._orig


# -- the configuration axis (WP-1404) --------------------------------------

@dataclass
class _Account:
    """What one run wrote, counted at the handle rather than guessed.

    ``lines``/``bytes``/``flushes`` are read off the handle the event log goes
    through, so they are the log's own traffic and not the directory's total;
    ``dir_bytes`` and ``snapshot_bytes`` are the directory afterwards, which is
    what a person asking "how big does this get" means.  All zero is a
    configuration that wrote nothing, which is the control's honest answer and
    not a missing measurement.
    """

    lines: int = 0
    evals: int = 0
    dropped: int = 0
    flushes: int = 0
    bytes: int = 0
    dir_bytes: int = 0
    snapshot_bytes: int = 0


class _CountingHandle:
    """A text handle that counts what goes through it.

    The recorder writes its event log through one handle and flushes it on a
    cadence, so wrapping the handle is how both numbers are read without
    re-implementing either.  Delegation is by ``__getattr__`` deliberately:
    this stands in for a real file inside the package's own code, and a method
    it forgot to forward would be a harness bug wearing a package bug's
    clothes.
    """

    def __init__(self, fh, account: _Account):
        self._fh = fh
        self._account = account

    def write(self, text: str) -> int:
        self._account.bytes += len(text)
        self._account.lines += 1
        return self._fh.write(text)

    def flush(self) -> None:
        self._account.flushes += 1
        self._fh.flush()

    def __getattr__(self, name):
        return getattr(self._fh, name)


def _counted_recorder(account: _Account, *, drop_eval: bool):
    """A ``RunRecorder`` subclass that counts, and optionally drops ``eval``.

    Patched over ``runs.RunRecorder`` for one run, the way ``_counting``
    patches the solver entry point: ``runs.attach`` reaches the name through
    the module, so the package builds the counting one without knowing it.

    ``drop_eval`` is the ``no-eval`` configuration and it is **a scaffold, not
    a knob the package has**.  It is paired with a stub over ``_free_values``,
    because the decode that builds an ``eval`` payload runs *before* any sink
    is consulted: dropping the line alone would price the serialisation and
    charge the row for the decode anyway.  What the two together price is the
    ceiling of WP-1403's mitigations 2 and 3 — the most a sink-side thrift
    could ever buy — and not any behaviour that ships.
    """
    base = runs.RunRecorder

    class _Counted(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if getattr(self, "_fh", None) is not None:
                self._fh = _CountingHandle(self._fh, account)

        def _write(self, event: dict) -> None:
            if event.get("kind") == "eval":
                if drop_eval:
                    account.dropped += 1
                    return
                account.evals += 1
            super()._write(event)

    return _Counted


@dataclass(frozen=True)
class Config:
    """One row of WP-1404's matrix: what the fit is asked to record.

    ``key`` is stamped on every row this produces, because a wall-clock number
    without its configuration is now ambiguous in a way it was not before
    WP-1403 made recording the default.
    """

    key: str
    blurb: str
    #: attach the package's own recorder, at ``telemetry=<scratch dir>``
    records: bool = False
    #: the harness scaffold described in :func:`_counted_recorder`
    drop_eval: bool = False
    #: what goes to ``events=``: nothing, ``"path"``, or ``"live"``
    stream: str = ""


CONFIGS: tuple[Config, ...] = (
    Config("off", "recording declined — the control", records=False),
    Config("no-eval", "recorder on, eval stream suppressed — a scaffold",
           records=True, drop_eval=True),
    Config("record", "the shipping default: recorder + cancel token",
           records=True),
    Config("events-path", "events=<path>, no recorder — WP-1401's bridge row",
           stream="path"),
    Config("live", "events=LiveSession(dir) — what a user pays when they ask",
           stream="live"),
)


def _tree_bytes(root: Path) -> int:
    return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())


def _named_bytes(root: Path, name: str) -> int:
    return sum(f.stat().st_size for f in root.rglob(name) if f.is_file())


def _log_traffic(root: Path) -> tuple[int, int]:
    """(lines, bytes) of every ``events.jsonl`` under ``root``.

    The counting handle only sees the *recorder's* writes, so a configuration
    that wrote through a plain ``EventStream`` — ``events-path``, ``live`` —
    is measured off the file it left behind instead.
    """
    lines = size = 0
    for f in root.rglob(runs.EVENTS_FILE):
        if not f.is_file():
            continue
        size += f.stat().st_size
        with f.open("r", encoding="utf-8") as fh:
            lines += sum(1 for _ in fh)
    return lines, size


def _refuse_stream_on_series(setup: Setup, configs: list[Config]) -> None:
    """Refuse a configuration that wants ``events=`` on a series case.

    Asked twice on purpose: ``main`` asks it once per case *before* spending a
    repeat, and ``_run_series`` asks it again for anyone calling that function
    directly.  Asked only in the second place, the refusal arrives after the
    control arm of a 10-pattern series has already run and takes every case
    after this one down with it.
    """
    if setup.patterns is None:
        return
    blocked = [c.key for c in configs if c.stream]
    if blocked:
        raise SystemExit(
            f"configuration(s) {', '.join(repr(k) for k in blocked)} need "
            f"events=, which a series case spends on its own per-pattern "
            f"collector — measure them on a single-fit case")


@contextmanager
def _configured(config: Config, account: _Account):
    """Put the package into one configuration and hand back ``fit``'s kwargs.

    Everything this touches is put back on the way out, including on an
    exception, for ``_counting``'s reason: a leaked patch would silently apply
    to the next configuration and the table would compare two things that are
    not what their keys say.

    The scratch directory is a fresh temp dir per repeat and is measured before
    it is removed.  Never the working directory: ``run_root`` prunes and
    ``.gitignore``s the root *it* chose, and a harness that quietly filled
    somebody's repository with a run per repeat would be a second thing to
    explain.
    """
    scratch = Path(tempfile.mkdtemp(prefix="rietx-bench-"))
    from rietx.optimize import least_squares as ls_mod

    orig_recorder = runs.RunRecorder
    orig_free_values = ls_mod._free_values
    kwargs: dict = {}
    try:
        if config.records:
            runs.RunRecorder = _counted_recorder(account,
                                                 drop_eval=config.drop_eval)
            kwargs["telemetry"] = scratch
        else:
            kwargs["telemetry"] = False
        if config.drop_eval:
            ls_mod._free_values = lambda table, theta: []
        if config.stream == "path":
            kwargs["events"] = scratch / runs.EVENTS_FILE
        elif config.stream == "live":
            from rietx.viz.live import LiveSession
            kwargs["events"] = LiveSession(scratch / "live")
        yield kwargs
    finally:
        runs.RunRecorder = orig_recorder
        ls_mod._free_values = orig_free_values
        # ``fit`` closes the stream only ``if stream is not events``, so an
        # ``EventStream`` the caller built is the caller's to close — and here
        # the caller is this harness.  Left open, every ``live`` repeat leaks a
        # descriptor onto a file ``rmtree`` has just removed.
        stream = kwargs.get("events")
        if hasattr(stream, "close"):
            stream.close()
        try:
            account.dir_bytes = _tree_bytes(scratch)
            account.snapshot_bytes = _named_bytes(scratch, runs.SNAPSHOT_FILE)
            if not config.records:
                account.lines, account.bytes = _log_traffic(scratch)
        except OSError:
            pass
        shutil.rmtree(scratch, ignore_errors=True)


# -- cases -----------------------------------------------------------------

@dataclass
class Setup:
    """One case, built once: pristine templates plus the plan that fits them.

    ``structure``/``instrument`` are deep-copied per repeat, because a fit
    mutates them and a warm second repeat would not be the same measurement.
    """

    title: str
    data: rx.PatternData
    structure: rx.Structure
    instrument: rx.Instrument
    plan: rx.RefinementPlan
    limits: tuple[float, float] | None = None
    mode: str = "rietveld"
    notes: str = ""
    #: a **series** case: N patterns through ``refine_sequential`` instead of
    #: one ``fit``.  ``data`` is then patterns[0], which is what the shape
    #: columns are measured on.  None for every ordinary case.
    patterns: list[rx.PatternData] | None = None
    #: series cases only — ``refine_sequential``'s first ladder rung.
    refit: str = "single"
    #: series cases only — WP-1127's first-rung bound, **declared** rather than
    #: inherited so a row says which ladder produced its number (the dispersion
    #: rule, root CLAUDE.md).  ``None`` is the pre-WP-1127 ladder; the default
    #: here is the shipped one.
    first_rung_factor: float | None = FIRST_RUNG_FACTOR


@dataclass
class Case:
    key: str
    build: Callable[[], Setup]
    blurb: str


def _nac_inputs():
    from test_acceptance_nac import DATA, build_nac_inputs

    if not (DATA / "11BM_NAC.fxye").exists():
        raise FileNotFoundError("11-BM NAC dataset not present")
    return build_nac_inputs()


def _nac_lebail() -> Setup:
    """The single-phase Le Bail leg the acceptance module opens with.

    A case in its own right because WP-1109's 1.5-1.8 s NAC row is **this leg
    plus the next one**, and a reader comparing against that row while timing
    only the Rietveld leg finds a 2.4× discrepancy that is not a speed change.
    Measured here 2026-08-20, the two legs are ~0.66 s and ~0.64 s.
    """
    from test_acceptance_nac import LIMITS

    data, structure, instrument = _nac_inputs()
    return Setup("11-BM NAC Le Bail leg, 1 phase, profile_only (5 stages)",
                 data, structure, instrument,
                 rx.RefinementPlan.profile_only(), limits=LIMITS, mode="lebail")


def _nac() -> Setup:
    """11-BM NAC: the acceptance module's Rietveld leg, on its Le Bail seed.

    Only the Rietveld leg is timed.  The Le Bail pass is a warm start, not part
    of this case; it is timed separately as ``nac-lebail``, and running it
    inside the timed region would measure a *third* thing again.
    """
    from test_acceptance_nac import LIMITS, _caf2_phase

    data, structure, instrument = _nac_inputs()
    ref_lb = rx.Refinement(structure, instrument, history=False)
    ref_lb.fit(data, mode="lebail", two_theta_limits=LIMITS)

    structure2 = ref_lb.fitted_structure.model_copy(deep=True)
    instrument2 = ref_lb.fitted_instrument.model_copy(deep=True)
    structure2.phases[0].scale.value = 1e-6
    structure2.phases.append(_caf2_phase())

    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    return Setup("11-BM NAC Rietveld leg, 2 phases, synchrotron (no FCJ)",
                 data, structure2, instrument2, plan, limits=LIMITS,
                 notes="Le Bail warm start built once at setup, not timed; "
                       "WP-1109's 1.5-1.8 s row is this leg PLUS nac-lebail")


def _cpd_1a() -> Setup:
    from test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
    )

    if not DATA.exists():
        raise FileNotFoundError("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / "cpd-1a.prn")
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                     fluorite_phase()])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, data)
    return Setup("IUCr cpd-1a, 3 phases, Cu Kα doublet (no FCJ), qpa_plan (8 stages)",
                 data, structure, instrument, qpa_plan())


def _cpd_2() -> Setup:
    """``test_sample2_brucite_march_dollase``'s protocol, stage for stage."""
    from test_acceptance_qpa_roundrobin import (
        DATA,
        brucite_phase,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
    )

    if not DATA.exists():
        raise FileNotFoundError("IUCr QPA round-robin dataset not present")
    data = rx.read_pattern(DATA / "cpd-2.prn")
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                     fluorite_phase(),
                                     brucite_phase(textured=True)])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, data)
    biso = ("phases.0.atoms.*.biso", "phases.1.atoms.*.biso",
            "phases.2.atoms.*.biso", "phases.3.atoms.0.biso",
            "phases.3.atoms.1.biso")
    return Setup(
        "qarr cpd-2, 4 phases, QPA acceptance protocol (9 stages, texture)",
        data, structure, instrument,
        qpa_plan(biso_globs=biso, texture=True))


def _cpd_series(refit: str = "single") -> Setup:
    """The IUCr round-robin sample-1 chain: eight real mixtures, one goniometer.

    **The counterexample family, and the reason it is a case** (WP-1127).  The
    ladder's first rung is set by ``refit=``, and which rung is cheaper is a
    property of the model rather than a constant: WP-0505 measured this very
    series at 838-904 iterations warm-collapsed against 1623 warm-staged, and
    WP-1110's agent round then hit the opposite side of the trade on a real
    trigger-shaped model — which ``trigger-series`` reproduces, 1253 nfev
    staged against 1603 collapsed.  A rule chosen on either case alone is
    tuned to it, so the harness carries both.

    Deliberately the same chain ``tests/test_acceptance_sequential.py``'s
    ``chained_all`` fixture runs — the same eight patterns, phases, instrument,
    ``seed_scales`` and ``qpa_plan()``, and the same default ``carry=("*",)``
    — so the protocol is the acceptance suite's and what varies here is only
    ``refit``.  It is a **hostile** series on purpose: the composition swings
    from 1 to 94 wt % across the set, which is where a naive carry was expected
    to hurt and measured not to.

    Small cells, three phases, no FCJ: the per-pattern shape ``cpd-1a`` already
    reports one row up, chained.
    """
    from test_acceptance_qpa_roundrobin import (
        DATA,
        SAMPLE1,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
        zincite_phase,
    )

    if not DATA.exists():
        raise FileNotFoundError("IUCr QPA round-robin dataset not present")
    patterns = [rx.read_pattern(DATA / f"{s}.prn") for s in SAMPLE1]
    structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                     fluorite_phase()])
    instrument = qarr_instrument()
    seed_scales(structure, instrument, patterns[0])
    return Setup(
        f"IUCr round-robin sample-1 series (real): 8 mixtures, 1 to 94 wt % "
        f"swing, refit={refit!r}",
        patterns[0], structure, instrument, qpa_plan(), patterns=patterns,
        refit=refit,
        notes="per-pattern wall printed below; cpd-1a is the cold fit and "
              "1b-1h are warm starts")


def _cpd_series_stages() -> Setup:
    return _cpd_series(refit="stages")


def _cpd_series_unbounded() -> Setup:
    setup = _cpd_series()
    setup.first_rung_factor = None
    setup.title += ", first rung unbounded (pre-WP-1127)"
    return setup


# -- the trigger-shaped case, simulated ------------------------------------
#
# WP-1109's trigger was a 68-pattern in-situ series: 4 phases of ZrMo₂O₈,
# 4 165 points, ~41 free, Cu Kα, 105-600 s per pattern.  None of the three
# baselines above is within an order of magnitude of its peak count, and
# peak-loop cost scales with peaks × window width, so a ranking measured only
# on them under-weights exactly the term the trigger is dominated by.  No real
# ZrMo₂O₈ data ships with this repo, so the case below is **simulated** to that
# shape.
#
# WHAT IS REAL AND WHAT IS NOT.  The four **cells** are the literature ones for
# a plausible ZrMo₂O₈ decomposition series — cubic ZrMo₂O₈ (Pa-3, Lind et al.
# 1998, Chem. Mater. 10, 2335), trigonal α-ZrMo₂O₈ (P-31c, Auray, Quarton &
# Tarte 1986, Acta Cryst. C42, 257), baddeleyite ZrO₂ (P2₁/c, Smith & Newkirk
# 1965, Acta Cryst. 18, 983) and MoO₃ (Pbnm, Kihlborg 1963, Ark. Kemi 21, 357)
# — quoted to the precision a *peak count* needs and no further.  Every **atom
# coordinate is invented**: species and rough site counts are chemically
# sensible, the positions are not refined values and are not read from any CIF.
# The phase names carry a ``sim-`` prefix for that reason, and nothing this
# case prints — Rwp, weight fractions, cell esds — is a structural or
# quantitative claim about any of these materials.  The WP licenses exactly
# this: for a *performance* benchmark the truth of the answer is irrelevant,
# and what must be realistic is peak count, overlap and window structure.
#
# HOW IT IS BUILT.  The truth model is evaluated on the 2θ grid, Poisson noise
# is added at a fixed seed (so the pattern is byte-identical between runs and
# machines), and the fit starts **cold**: cells 500 ppm high, widths at generic
# starting values, axial parameters low, background at zero, scales seeded by
# ``seed_scales``.  Rwp lands near 0.02 because the model that made the data is
# the model being fitted — the residual is pure counting noise.  That is a
# property of a simulation and it is why Rwp is only ever an identity check
# here; it does not make the *timing* less real, because the peak loop does the
# same work whatever the residual.

_TRIGGER_TT = np.arange(5.0, 88.281, 0.02)       # 4 165 points, 0.02° steps
_TRIGGER_BKG = (900.0, -260.0, 90.0, -30.0, 12.0, -5.0)


def _p(v, **kw):
    return rx.Parameter(value=v, **kw)


def _sim_phase(name, sg, cell, atoms, scale, drift):
    a, b, c, al, be, ga = cell
    f = 1.0 + drift
    return rx.Phase(
        name=name, space_group=sg,
        cell=rx.Cell(a=_p(a * f, min=1.0), b=_p(b * f, min=1.0),
                     c=_p(c * f, min=1.0),
                     alpha=_p(al), beta=_p(be), gamma=_p(ga)),
        atoms=[rx.Atom(label=lab, species=sp, x=_p(x), y=_p(y), z=_p(z),
                       biso=_p(bi, min=0.0, max=25.0))
               for lab, sp, x, y, z, bi in atoms],
        scale=_p(scale, min=0.0),
        lor_size=_p(0.03, min=0.0),
        lor_strain=_p(0.0, min=0.0))


def _trigger_phases(drift: float = 0.0) -> list[rx.Phase]:
    """The four phases, all cells scaled by ``1 + drift`` (the series ramp)."""
    return [
        _sim_phase("sim-ZrMo2O8-cubic", "P a -3",
                   (9.1304, 9.1304, 9.1304, 90, 90, 90),
                   [("Zr", "Zr", 0.0, 0.0, 0.0, 0.6),
                    ("Mo", "Mo", 0.3479, 0.3479, 0.3479, 0.7),
                    ("O1", "O", 0.2081, 0.2081, 0.2081, 1.0),
                    ("O2", "O", 0.4907, 0.2716, 0.1343, 1.0)], 4e-4, drift),
        _sim_phase("sim-ZrMo2O8-trigonal", "P -3 1 c",
                   (10.1391, 10.1391, 11.7091, 90, 90, 120),
                   [("Zr", "Zr", 1 / 3, 2 / 3, 0.1487, 0.6),
                    ("Mo", "Mo", 0.3312, 0.0071, 0.1123, 0.7),
                    ("O1", "O", 0.1837, 0.0264, 0.0741, 1.0),
                    ("O2", "O", 0.4712, 0.1583, 0.1927, 1.0),
                    ("O3", "O", 0.3096, 0.4471, 0.0619, 1.0)], 3e-4, drift),
        _sim_phase("sim-ZrO2-baddeleyite", "P 1 21/c 1",
                   (5.1505, 5.2116, 5.3173, 90, 99.230, 90),
                   [("Zr", "Zr", 0.2758, 0.0411, 0.2082, 0.4),
                    ("O1", "O", 0.0703, 0.3359, 0.3406, 0.6),
                    ("O2", "O", 0.4423, 0.7549, 0.4789, 0.6)], 2e-4, drift),
        _sim_phase("sim-MoO3", "P b n m",
                   (3.9628, 13.855, 3.6964, 90, 90, 90),
                   [("Mo", "Mo", 0.1016, 0.1026, 0.25, 0.5),
                    ("O1", "O", 0.2214, 0.0434, 0.25, 0.8),
                    ("O2", "O", 0.0862, 0.2214, 0.25, 0.8),
                    ("O3", "O", 0.5000, 0.4353, 0.25, 0.8)], 2e-4, drift),
    ]


def _trigger_instrument(*, truth: bool) -> rx.Instrument:
    """Cu Kα doublet, Bragg-Brentano, FCJ live (axial S/L and H/L nonzero).

    ``truth=False`` is the cold start: generic widths, low axial terms, an
    all-zero background.  Dispersion is DECLINED explicitly for the reason
    every acceptance suite declines it — a benchmark whose numbers move when a
    package default moves is not measuring the package.
    """
    from rietx.schemas.instrument import BackgroundChebyshev

    ins = rx.Instrument.bragg_brentano(radiation="CuKa",
                                       goniometer_radius_mm=250.0,
                                       monochromator_two_theta=26.6)
    ins.background = BackgroundChebyshev.with_terms(6)
    ins.source.dispersion = None
    if truth:
        ins.geometry.axial_sl.value = 0.030
        ins.geometry.axial_hl.value = 0.030
        ins.profile.u.value = 0.008
        ins.profile.v.value = -0.004
        ins.profile.w.value = 0.006
        ins.profile.x.value = 0.020
        for coef, v in zip(ins.background.coefficients, _TRIGGER_BKG):
            coef.value = v
    else:
        ins.geometry.axial_sl.value = 0.020
        ins.geometry.axial_hl.value = 0.020
        ins.profile.u.value = 0.0
        ins.profile.v.value = 0.0
        ins.profile.w.value = 0.010
        ins.profile.x.value = 0.010
    return ins


def _trigger_pattern(seed: int, drift: float) -> rx.PatternData:
    """Evaluate the truth model on the grid and Poisson-sample it."""
    from rietx.params.vector import ParameterTable

    structure = rx.Structure(phases=_trigger_phases(drift))
    instrument = _trigger_instrument(truth=True)
    blank = rx.PatternData(two_theta=_TRIGGER_TT.tolist(),
                           intensity=np.ones_like(_TRIGGER_TT).tolist())
    model = compile_model(structure, instrument, blank)
    table = ParameterTable(structure, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    counts = np.random.default_rng(seed).poisson(np.clip(y, 1.0, None))
    return rx.PatternData(two_theta=_TRIGGER_TT.tolist(),
                          intensity=counts.astype(float).tolist())


def _trigger_cold(data: rx.PatternData) -> tuple[rx.Structure, rx.Instrument]:
    from test_acceptance_qpa_roundrobin import seed_scales

    structure = rx.Structure(phases=_trigger_phases(5e-4))   # 500 ppm high
    instrument = _trigger_instrument(truth=False)
    seed_scales(structure, instrument, data)
    return structure, instrument


def _trigger() -> Setup:
    from test_acceptance_qpa_roundrobin import qpa_plan

    data = _trigger_pattern(seed=1111, drift=0.0)
    structure, instrument = _trigger_cold(data)
    return Setup(
        "trigger-shaped (simulated): 4 phases, large cells, Cu Kα + FCJ",
        data, structure, instrument, qpa_plan(),
        notes="simulated — see the block comment above _TRIGGER_TT; Rwp near "
              "0.02 is counting noise, not a fit quality claim")


def _trigger_series(refit: str = "single") -> Setup:
    """Ten copies of the trigger case with a 100 ppm/step cell ramp.

    The workflow the milestone's ~1 s/pattern target names: one cold fit, then
    nine warm starts.  ``direction="both"`` is deliberately off — this is a
    timing case, not a science case, and the backward pass would double the
    wall clock to answer a question about path dependence that no speed WP
    asks.  Each pattern gets its own noise seed, so a warm start is fitting a
    genuinely different realisation rather than the same array again.

    **Both ``refit`` rungs are cases**, because the saving they are quoted for
    was never measured at this width.  ``refit="single"`` (the default)
    collapses the plan into one stage freeing the whole set, which WP-0505
    measured at 904 iterations against 1623 for the staged refit — on
    small-cell standards.  WP-1110's agent round hit the other side of that
    trade on a real trigger-shaped model: the collapse ran one TRF call over
    ~30 simultaneous free parameters and went past 150 s without finishing on
    a pattern whose staged neighbour took ~50 s.  Stage count and per-stage
    Jacobian *width* trade against each other, and which way is a property of
    the model, so the harness measures both rather than quoting one.
    """
    from test_acceptance_qpa_roundrobin import qpa_plan

    patterns = [_trigger_pattern(seed=2000 + i, drift=i * 100e-6)
                for i in range(10)]
    structure, instrument = _trigger_cold(patterns[0])
    return Setup(
        f"trigger-shaped series (simulated): 10 patterns, 100 ppm/step ramp, "
        f"refit={refit!r}",
        patterns[0], structure, instrument, qpa_plan(), patterns=patterns,
        refit=refit,
        notes="per-pattern wall printed below; pattern 0 is the cold fit and "
              "1-9 are warm starts")


def _trigger_series_stages() -> Setup:
    return _trigger_series(refit="stages")


def _trigger_series_unbounded() -> Setup:
    setup = _trigger_series()
    setup.first_rung_factor = None
    setup.title += ", first rung unbounded (pre-WP-1127)"
    return setup


CASES: tuple[Case, ...] = (
    Case("nac-lebail", _nac_lebail, "22 003 pts, 1 phase — the Le Bail seed leg"),
    Case("nac", _nac, "22 003 pts, no FCJ — the dispatch-light case"),
    Case("cpd-1a", _cpd_1a, "7 251 pts, no FCJ, 3 phases — the small lab case"),
    Case("cpd-2", _cpd_2, "7 251 pts, no FCJ, 4 phases + texture — WP-1109's profile"),
    Case("cpd-series", _cpd_series,
         "8 × cpd-1, warm-started, refit='single' — WP-0505's counterexample"),
    Case("cpd-series-stages", _cpd_series_stages,
         "the same real chain, refit='stages' — the other side of the trade"),
    Case("cpd-series-unbounded", _cpd_series_unbounded,
         "cpd-series without WP-1127's bound — inert here, so identical"),
    Case("trigger", _trigger,
         "4 165 pts, 1 188 pairs, 4 phases — the trigger-shaped cold fit (~50 s)"),
    Case("trigger-series", _trigger_series,
         "10 × trigger, warm-started, refit='single' (the default collapse)"),
    Case("trigger-series-stages", _trigger_series_stages,
         "the same series, refit='stages' — the width-vs-stage-count trade"),
    Case("trigger-series-unbounded", _trigger_series_unbounded,
         "trigger-series without WP-1127's bound — the pre-1127 'before'"),
)


# -- measurement -----------------------------------------------------------

@dataclass
class PerPattern:
    """One pattern of a series case, with its whole escalation (WP-1124/1127).

    ``wall`` sums every rung the pattern ran and ``rung_walls`` breaks it out in
    ladder order, so a discarded first rung is visible rather than averaged
    away.  ``rwp_warm`` and ``status`` are what say *why* a pattern escalated:
    the ladder climbs when the fit diverged or raised, or when the best attempt
    so far sits above a caller's ``reseed_factor`` × the accepted median, and
    those are different failures with different fixes.  ``rwp_warm`` is ``None`` on a pattern that
    never escalated — the library records it only then.
    """

    index: int
    wall: float
    iterations: int
    rwp: float
    rung: str
    rung_walls: list[float]
    rwp_warm: float | None = None
    status: str = ""


@dataclass
class Run:
    wall: float
    rwp: float
    nfev: int
    njev: int
    free: int
    stages: list[tuple[str, int]] = field(default_factory=list)
    status: str = ""
    #: series cases only: one :class:`PerPattern` per pattern, index 0 being
    #: the cold fit and the rest warm starts
    per_pattern: list[PerPattern] = field(default_factory=list)
    #: which :class:`Config` produced this run, stamped rather than inferred
    config: str = "off"
    #: what it wrote (WP-1404); all zero for a configuration that recorded
    #: nothing
    account: _Account = field(default_factory=_Account)


def _shape(setup: Setup) -> tuple[int, int, float]:
    """(fitted points, (line, reflection) pairs, mean window width in points).

    Compiled at the case's *starting* model with no ``moving_paths`` claim, so
    the pair count is the one the first stage sees.
    """
    model = compile_model(setup.structure, setup.instrument, setup.data,
                          mode=setup.mode, two_theta_limits=setup.limits)
    pairs = 0
    widths: list[np.ndarray] = []
    for ph in model.phases:
        pairs += int(ph.win.shape[0] * ph.win.shape[1])
        widths.append((ph.win[..., 1] - ph.win[..., 0]).ravel())
    width = float(np.mean(np.concatenate(widths))) if widths else 0.0
    return len(model.tt), pairs, width


def _run_once(setup: Setup, config: Config = CONFIGS[0]) -> Run:
    if setup.patterns is not None:
        return _run_series(setup, config)
    counts = _Counts()
    account = _Account()
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True),
                        history=False)
    with _configured(config, account) as kwargs, _counting(counts):
        t0 = time.perf_counter()
        result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                         two_theta_limits=setup.limits, **kwargs)
        wall = time.perf_counter() - t0
    freed: set[str] = set()
    for stage in result.stages:
        freed |= set(stage.freed)
    return Run(wall, result.statistics.rwp, counts.nfev, counts.njev,
               len(freed), [(s.name, s.n_iterations) for s in result.stages],
               result.status, config=config.key, account=account)


def _run_series(setup: Setup, config: Config = CONFIGS[0]) -> Run:
    """One pass of a series case through ``refine_sequential``.

    **The configuration axis reaches this only through ``telemetry=``.**  A
    series case already spends ``events=`` on the collector that reads its
    per-pattern wall clock off the ladder, so a configuration wanting that
    channel is refused by name rather than silently given a second stream that
    would change what the row measures.

    Per-pattern wall clock is taken from the **event ladder** rather than by
    timing calls, because ``refine_sequential`` is one call: every event
    carries ``series_index`` (WP-1016), so the ``fit_start``/``fit_end`` pair
    for each index brackets that pattern's own refinement.  A pattern that
    escalated a rung reports the wall of the whole escalation, which is what a
    person waiting on the series experiences.

    **That last sentence was a claim, not a measurement, until WP-1124.**  A
    pattern emits one ``fit_start``/``fit_end`` pair *per rung*, so keeping the
    latest of each reported only the rung that succeeded — and the rung that
    succeeded is by construction the cheap one, the escalation having been
    reached because the first was rejected.  On the ``trigger-series`` case
    that hid 32.8 s of a 57.7 s series in two discarded first rungs: pattern 1
    read 3.21 s and had spent 20.3 s.  The pairs are therefore accumulated in
    arrival order and summed, and ``rungs`` prints the breakdown, because a
    number that omits the expensive half of the expensive patterns is the one
    number a speed milestone must not print.
    """
    from rietx.sequential import refine_sequential

    _refuse_stream_on_series(setup, [config])

    account = _Account()
    marks: dict[int, list[tuple[str, float]]] = {}

    def collect(event):
        index = event.get("data", {}).get("series_index")
        if index is not None and event["kind"] in ("fit_start", "fit_end"):
            marks.setdefault(index, []).append((event["kind"], event["t"]))

    def rung_spans(index: int) -> list[float]:
        spans, start = [], None
        for kind, t in marks.get(index, []):
            if kind == "fit_start":
                start = t
            elif start is not None:
                spans.append(t - start)
                start = None
        return spans

    counts = _Counts()
    with _configured(config, account) as kwargs, _counting(counts):
        t0 = time.perf_counter()
        series = refine_sequential(setup.patterns,
                                   setup.structure.model_copy(deep=True),
                                   setup.instrument.model_copy(deep=True),
                                   plan=setup.plan, refit=setup.refit,
                                   first_rung_factor=setup.first_rung_factor,
                                   events=collect, **kwargs)
        wall = time.perf_counter() - t0

    per: list[PerPattern] = []
    for entry in series.entries:
        spans = rung_spans(entry.index)
        per.append(PerPattern(entry.index, sum(spans), entry.n_iterations,
                              entry.statistics.rwp, entry.rung, spans,
                              entry.rwp_warm, entry.status))
    last = series.entries[-1] if series.entries else None
    statuses = {e.status for e in series.entries}
    status = "converged" if statuses == {"converged"} else "/".join(sorted(statuses))
    # ``free`` is -1, printed "-": a series entry carries no per-stage freed
    # list, and ``SeriesEntry.parameters`` is not the same quantity — a row
    # appears there iff the entry varied *or was tied*.  The count is the
    # ``trigger`` row's, one line up, because the plan is the same one.
    return Run(wall, last.statistics.rwp if last else float("nan"),
               counts.nfev, counts.njev, -1, [], status, per,
               config=config.key, account=account)


def _profile(setup: Setup, config: Config = CONFIGS[0]) -> str:
    prof = cProfile.Profile()
    prof.enable()
    _run_once(setup, config)
    prof.disable()
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("tottime").print_stats(10)
    return buf.getvalue()


def _header(repeats: int, configs: list[Config]) -> str:
    return (f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · "
            f"numpy {np.__version__} · python {platform.python_version()} · "
            f"{platform.system().lower()}/{platform.machine()} · "
            f"venv {Path(sys.prefix)}\n"
            f"best-of-{repeats}, wall clock as a RANGE — run idle, alone; "
            f"never compare across machines\n"
            f"configurations are INTERLEAVED within each repeat, so machine "
            f"drift spreads over all of them instead of landing on one\n"
            f"configurations: {', '.join(c.key for c in configs)} — every row "
            f"carries its own, and a number quoted without one is ambiguous")


HEAD = (f"  {'case':14s} {'config':11s} {'pts':>6s} {'pairs':>6s} {'win':>5s} "
        f"{'free':>5s} {'wall (s)':>15s} {'nfev':>6s} {'njev':>6s} "
        f"{'Rwp':>8s}  status")


def _bytes(n: int) -> str:
    """Bytes at three significant figures, because these span six orders."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} kB"
    return f"{n / 1024 ** 2:.2f} MB"


def _report(case: Case, setup: Setup, runs: list[Run], config: Config,
            shape: tuple[int, int, float], *, detail: bool = True) -> None:
    pts, pairs, width = shape
    walls = [r.wall for r in runs]
    rwps = {round(r.rwp, 6) for r in runs}
    last = runs[-1]
    njev = f"{last.njev}" if last.njev else "-"
    free = f"{last.free}" if last.free >= 0 else "-"
    rng = f"{min(walls):.2f}-{max(walls):.2f}"
    print(f"  {case.key:14s} {config.key:11s} {pts:6d} {pairs:6d} {width:5.0f} "
          f"{free:>5s} {rng:>15s} {last.nfev:6d} {njev:>6s} {last.rwp:8.5f}"
          f"  {last.status}")
    if detail:
        print(f"    {setup.title}")
        if setup.notes:
            print(f"    ({setup.notes})")
    if len(rwps) > 1:
        print(f"    !! Rwp differs between repeats {sorted(rwps)} — these are "
              f"not the same fit, so the wall-clock range is not one either")
    if detail and last.stages:
        print("    per-stage nfev: " +
              "  ".join(f"{n}={i}" for n, i in last.stages))
    if last.per_pattern:
        cold = last.per_pattern[0].wall
        warm = [p.wall for p in last.per_pattern[1:]]
        wasted = sum(sum(p.rung_walls[:-1]) for p in last.per_pattern
                     if len(p.rung_walls) > 1)
        print(f"    cold {cold:.2f} s | warm {min(warm):.2f}-{max(warm):.2f} s "
              f"over {len(warm)} patterns (last repeat)")
        if wasted:
            print(f"    {wasted:.2f} s of that ({100 * wasted / last.wall:.0f} %"
                  f" of the series) is rungs the ladder discarded — rungs= below")
        for p in last.per_pattern:
            rungs = ""
            if len(p.rung_walls) > 1:
                rungs = f"  rungs={'+'.join(f'{s:.2f}' for s in p.rung_walls)}"
                if p.rwp_warm is not None:
                    rungs += f"  warm Rwp {p.rwp_warm:.5f}"
            if p.status and p.status != "converged":
                rungs += f"  [{p.status}]"
            print(f"      pattern {p.index:2d}  {p.wall:7.2f} s  "
                  f"{p.iterations:5d} iter  Rwp {p.rwp:.5f}  kept {p.rung}{rungs}")


def _compare(by_config: dict[str, list[Run]]) -> None:
    """Ratios against the control, with the control's own spread printed first.

    WP-1404's gate on the default-on recorder is 1.05×, **unless the control's
    own repeat spread exceeds 5 %, in which case the gate becomes that
    spread**: a gate tighter than the measurement's resolution is a coin toss
    wearing a check's clothes.  So the spread is printed before any ratio, and
    every ratio is printed beside the number it has to beat.

    The ratio is of medians, which is what WP-1404 asks for; the range stays
    what each row prints.  A median is comparable and a range is honest, and
    neither substitutes for the other.

    ``nfev`` and ``Rwp`` are compared against the control on every row, because
    the whole claim being tested is that telemetry changed no number — a
    configuration that moved either is not a slower fit, it is a different one,
    and its ratio means nothing.
    """
    if len(by_config) < 2:
        return
    control = by_config.get(CONFIGS[0].key)
    if not control:
        # silence here reads as "nothing to compare", which is the one thing
        # it is not: several configurations ran and none of them is a baseline
        print(f"    no comparison: {CONFIGS[0].key!r} was not selected, and "
              f"every ratio in this block is against it")
        return
    walls = [r.wall for r in control]
    base = statistics.median(walls)
    floor = min(walls)
    spread = (max(walls) - min(walls)) / base if base else 0.0
    gate = max(0.05, spread)
    tail = "" if gate == 0.05 else "  (the spread, not the 5 %)"
    print(f"    vs {CONFIGS[0].key}: {len(control)} interleaved repeats · "
          f"control spread {100 * spread:.1f} % · gate {1 + gate:.3f}×{tail}")
    print(f"      {'':12s} {'median':>7s} {'min':>7s}  "
          f"— the min of N is the least contaminated estimate of the same "
          f"quantity, so a pair that disagree are still measuring the machine")
    if len(control) < 3:
        print(f"      !! {len(control)} repeat(s): the spread above is not a "
              f"spread and the gate it implies is not one either")
    ref_nfev = {r.nfev for r in control}
    ref_rwp = {round(r.rwp, 9) for r in control}
    records = {c.key: c.records for c in CONFIGS}
    for key, rs in by_config.items():
        assert all(r.config == key for r in rs), (
            f"a run filed under {key!r} carries a different configuration stamp")
        med = statistics.median([r.wall for r in rs])
        ratio = med / base if base else float("nan")
        floor_ratio = min(r.wall for r in rs) / floor if floor else float("nan")
        acc = rs[-1].account
        flags = []
        if {r.nfev for r in rs} != ref_nfev:
            flags.append("nfev DIFFERS from the control")
        if {round(r.rwp, 9) for r in rs} != ref_rwp:
            flags.append("Rwp DIFFERS from the control")
        if key != CONFIGS[0].key and ratio > 1 + gate:
            flags.append("OVER THE GATE")
        note = "  << " + "; ".join(flags) if flags else ""
        # a flush count is read at the recorder's own handle, so a
        # configuration that wrote through a plain ``EventStream`` has none —
        # "-" rather than 0, which would read as a measurement
        flush = f"{acc.flushes:5d}" if records.get(key) else f"{'-':>5s}"
        evals = f"{acc.evals:5d} eval" if records.get(key) else f"{'-':>5s} eval"
        print(f"      {key:12s} {ratio:6.3f}× {floor_ratio:6.3f}×  "
              f"median {med:8.3f} s  log {acc.lines:6d} ln "
              f"{_bytes(acc.bytes):>9s}  {evals}  flush {flush}  "
              f"dir {_bytes(acc.dir_bytes):>9s}  "
              f"snap {_bytes(acc.snapshot_bytes):>9s}{note}")
        if acc.dropped:
            print(f"        ({acc.dropped} eval events dropped by the "
                  f"scaffold — not a shipped behaviour)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="v1.1 refinement benchmark harness")
    ap.add_argument("--cases", default="", help="comma-separated case keys "
                    f"(default all: {','.join(c.key for c in CASES)})")
    ap.add_argument("--configs", default=CONFIGS[0].key,
                    help="comma-separated telemetry configurations (default "
                    f"{CONFIGS[0].key}; all: {','.join(c.key for c in CONFIGS)})")
    ap.add_argument("--repeats", type=int, default=3,
                    help="timed repeats per case (default 3)")
    ap.add_argument("--profile", action="store_true",
                    help="also cProfile each case once, top 10 by tottime")
    ap.add_argument("--list", action="store_true", help="list the cases and exit")
    args = ap.parse_args(argv)

    if args.list:
        for case in CASES:
            print(f"  {case.key:{max(len(c.key) for c in CASES)}s} {case.blurb}")
        print()
        for config in CONFIGS:
            print(f"  --configs {config.key:12s} {config.blurb}")
        return 0

    wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
    unknown = set(wanted) - {c.key for c in CASES}
    if unknown:
        ap.error(f"unknown case(s): {', '.join(sorted(unknown))}")
    selected = [c for c in CASES if not wanted or c.key in wanted]

    asked = [c.strip() for c in args.configs.split(",") if c.strip()]
    unknown = set(asked) - {c.key for c in CONFIGS}
    if unknown:
        ap.error(f"unknown configuration(s): {', '.join(sorted(unknown))}")
    if not asked:
        # unlike ``--cases``, empty does not mean all: it means a harness that
        # builds every case and times none of them, in silence
        ap.error("--configs selects nothing; name at least one of "
                 f"{', '.join(c.key for c in CONFIGS)}")
    # declaration order, not the order asked in: the control runs first so its
    # own spread is on screen before any ratio is
    configs = [c for c in CONFIGS if c.key in asked]
    # **The environment outranks ``telemetry=``** (``runs.enabled``), so under
    # ``RIETX_TELEMETRY=0`` a recording configuration attaches no recorder and
    # times the control while still printing a ratio against it.  Refused here
    # rather than discovered in the table: the only trace it leaves is an
    # all-zero accounting row, which is also what an honest control prints.
    if any(c.records for c in configs) and not runs.enabled():
        ap.error(f"recording is switched off for this process, so "
                 f"{', '.join(c.key for c in configs if c.records)} would "
                 f"time the control and call it a recorded fit — unset "
                 f"{_about.TELEMETRY_ENV} (or set it to 1) and re-run")

    print(_header(args.repeats, configs))
    print()
    print(HEAD)

    for case in selected:
        try:
            setup = case.build()
        except (FileNotFoundError, OSError) as exc:        # dataset absent
            print(f"  {case.key:10s} skipped ({exc})")
            continue
        _refuse_stream_on_series(setup, configs)
        shape = _shape(setup)
        # **Interleaved, never blocked.**  Running every repeat of one
        # configuration before starting the next makes each configuration a
        # contiguous slice of wall-clock time, so any drift in the machine --
        # thermal, another process, page cache -- lands on one configuration
        # entire and arrives as a difference between configurations.  Measured
        # 2026-09-15, blocked: `events=<path>` came in at 0.816x a bare fit on
        # `nac`, and on `cpd-2` the recorder came in cheaper than the caller's
        # stream it contains.  Both are impossible; both went away on
        # interleaving.  WP-1405 reached the same shape from the other end and
        # its numbers are the finer ones for that reason.
        by_config: dict[str, list[Run]] = {c.key: [] for c in configs}
        for _ in range(args.repeats):
            for config in configs:
                by_config[config.key].append(_run_once(setup, config))
        for n, config in enumerate(configs):
            _report(case, setup, by_config[config.key], config, shape,
                    detail=n == 0)
        _compare(by_config)
        if args.profile:
            print(_profile(setup, configs[0]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
