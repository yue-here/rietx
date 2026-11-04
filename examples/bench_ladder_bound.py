"""WP-1127: does bounding the ladder's first rung change the answer?

Run: ``.venv/bin/python examples/bench_ladder_bound.py``

`examples/bench_refinement.py` already prices the bound — `trigger-series`
against `trigger-series-bounded`, `cpd-series` against `cpd-series-bounded`.
What it cannot say is whether the two chains **agree**, and that is the half
that decides whether the bound may ship: a cheaper chain that lands somewhere
else is not a faster chain, it is a different one.

So this script is the equivalence read-out, and it runs the WP's pre-registered
kill criterion clauses 2-4:

``escalations`` / ``quarantined`` / ``status``
    a bounded rung comes back ``"max_iter"``, which :func:`_better` reads as
    merely not-diverged and :func:`_reseed_needed` does not test at all — so a
    bound that did not force the next rung would let the ladder **accept** a
    truncated fit.  Clause 2 is the guard against exactly that, and it is
    checked on the entries rather than on the code.
``agreement``
    per-pattern worst ``|Δ|/esd`` against the unbounded arm, reported twice:
    over every path, and again with the trigger case's exactly degenerate width
    family dropped.  A bound that moves the split of one width without moving
    the sum has not moved the answer, which is why WP-1123 and WP-1124 both
    report it this way — and the second number is the one clause 3 is about.
``direction="both"``
    the read-out that retired WP-1124's predictors.  Both of its arms turned
    the removed ``SEQUENTIAL_PATH_DEPENDENT`` from absent to reported (now the
    largest gap in ``SeriesResult.direction_gaps``), because a first-order
    predictor cannot seed the first two patterns of a pass and is therefore
    asymmetric in the series coordinate.  The bound has a weaker version of the
    same shape — the *first* warm pattern of a pass has no accepted first rung
    behind it, and which pattern that is depends on the direction — so the
    check is run rather than argued.

The comparison machinery is imported from ``bench_series_predictor`` (WP-1124)
rather than copied: ``_agreement``, the degenerate-family filter and the
escalation/quarantine/wasted-wall readers are the same measurements on the same
case, and a second copy would be a second authority for what "the answers
agree" means.  ``ArmRun``'s three predictor fields are passed as zeros here,
which is the one price of sharing it.

Wall clock is reported but never compared across runs: the arms of one table
run in one process, and the deterministic read-outs (nfev, njev, iterations)
lead every claim.  `bench_refinement.py` is the authority for the timings.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from importlib.metadata import version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from bench_refinement import (  # noqa: E402
    _counting,
    _Counts,
    _cpd_series,
    _trigger_series,
)
from bench_series_predictor import (  # noqa: E402
    ArmRun,
    _agreement,
    _escalations,
    _quarantined,
    _wasted,
    largest_gap,
)

from rietx import _about  # noqa: E402

#: WP-1127's factor, the package default until WP-2003 C3 made the bound the
#: caller's (``first_rung_factor=None`` by default since); this benchmark
#: measures it by name
FIRST_RUNG_FACTOR = 3.0

#: ``(key, setup builder, refit)`` — the two harness series cases, each in the
#: mode its own baseline won in (WP-1127 § Findings 1), plus the trigger case in
#: the other mode, where the bound must be provably inert because the first rung
#: is the answer plan rather than a bet.
CASES = {
    "trigger": (lambda: _trigger_series(), "single"),
    "trigger-stages": (lambda: _trigger_series(refit="stages"), "stages"),
    "cpd": (lambda: _cpd_series(), "single"),
    "cpd-stages": (lambda: _cpd_series(refit="stages"), "stages"),
}


def _run_arm(setup, factor: float | None, direction: str) -> ArmRun:
    """One chain, with or without the bound, through ``refine_sequential``.

    Per-rung wall comes off the event ladder the way `bench_refinement` takes
    it — one ``fit_start``/``fit_end`` pair per **rung**, accumulated rather
    than overwritten, because the discarded rung is the whole subject here.
    A ``direction="both"`` run emits a backward pass under the same indices, so
    the collector keeps the forward one and the backward pass is read from the
    diagnostics instead.
    """
    from rietx.sequential import refine_sequential

    marks: dict[int, list[tuple[str, float]]] = {}

    def collect(event):
        data = event.get("data", {})
        index = data.get("series_index")
        if (index is not None and data.get("series_pass") == "forward"
                and event["kind"] in ("fit_start", "fit_end")):
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
    with _counting(counts):
        t0 = time.perf_counter()
        series = refine_sequential(setup.patterns,
                                   setup.structure.model_copy(deep=True),
                                   setup.instrument.model_copy(deep=True),
                                   plan=setup.plan, refit=setup.refit,
                                   direction=direction,
                                   first_rung_factor=factor, events=collect)
        wall = time.perf_counter() - t0

    per, endpoints = [], []
    for entry in series.entries:
        spans = rung_spans(entry.index)
        per.append((entry.index, sum(spans), entry.n_iterations,
                    entry.statistics.rwp if entry.statistics else float("nan"),
                    entry.rung, list(entry.rungs_tried), entry.status, spans))
        endpoints.append({p.path: (p.value, p.stderr) for p in entry.parameters})
    return ArmRun(wall, counts.nfev, counts.njev, 0.0, 0, 0, [], [], per,
                  [d.code for d in series.diagnostics], endpoints,
                  largest_gap(series))


def _statuses(run: ArmRun) -> set[str]:
    return {row[6] for row in run.per_pattern}


def _report(case: str, base: ArmRun, arm: ArmRun) -> None:
    print(f"\n  {case}")
    for name, run in (("unbounded", base), ("bounded", arm)):
        print(f"    {name:10s} {run.wall:7.2f} s  {run.nfev:5d} nfev  "
              f"{run.njev:5d} njev  {_escalations(run)} escalations  "
              f"{_quarantined(run)} quarantined  "
              f"{_wasted(run):6.2f} s discarded  "
              f"status {'/'.join(sorted(_statuses(run)))}")
        if run.diagnostics:
            print(f"               diagnostics: {sorted(set(run.diagnostics))}")

    if base.nfev:
        print(f"    evaluations {base.nfev / arm.nfev:.2f}x  "
              f"(clause 1 fires if < 1.00 against the better fixed mode)")
    added = sorted(set(arm.diagnostics) - set(base.diagnostics))
    print(f"    clause 2: diagnostics added {added or 'none'}; "
          f"non-converged accepted entries "
          f"{sorted(_statuses(arm) - {'converged'}) or 'none'}")

    # esd units answer "did the answer move?"; this answers "did any bit move?".
    # The mechanism predicts the stronger claim: the bound only ever truncates a
    # rung whose result is *discarded*, and the rung that replaces it starts
    # from the warm state rather than from the truncated one — so an arm that
    # escalates in both cases should reproduce the kept fit exactly.  A path
    # that differs at all is therefore the interesting event, not a large one.
    moved, worst_abs, worst_path = 0, 0.0, ""
    for b, o in zip(base.endpoints, arm.endpoints, strict=True):
        for path, (value, _) in b.items():
            if path in o and o[path][0] != value:
                moved += 1
                if abs(o[path][0] - value) > worst_abs:
                    worst_abs, worst_path = abs(o[path][0] - value), path
    total = sum(len(b) for b in base.endpoints)
    print(f"    exactness: {moved} of {total} accepted values differ at all"
          + (f", worst |Δ| {worst_abs:.3e} on {worst_path}" if moved else
             " — bit-identical"))

    rows, top, outside = _agreement(base, arm)
    if rows:
        med = float(np.median([r[1] for r in rows]))
        worst = max(rows, key=lambda r: r[1])
        mout = float(np.median([r[1] for r in outside]))
        wout = max(outside, key=lambda r: r[1])
        print(f"    clause 3: all paths median {med:.3f} esd, max "
              f"{worst[1]:.3f} on pattern {worst[0]} ({worst[2]})")
        print(f"              outside the degenerate width family: median "
              f"{mout:.3f} esd, max {wout[1]:.3f} on pattern {wout[0]} "
              f"({wout[2] or '—'})")
        print("              worst paths: "
              + ", ".join(f"{p} {v:.2f}" for p, v in top))


def _report_both(case: str, base: ArmRun, arm: ArmRun) -> None:
    print(f"\n  {case}  direction='both'")
    for name, run in (("unbounded", base), ("bounded", arm)):
        gap = "none sized" if run.gap is None else f"{run.gap:.2f} esd"
        print(f"    {name:10s} {run.wall:7.2f} s  {run.nfev:5d} nfev  "
              f"largest forward-backward gap {gap}")
        if run.diagnostics:
            print(f"               diagnostics: {sorted(set(run.diagnostics))}")
    if base.gap is not None and arm.gap is not None:
        print(f"    clause 4: the bound moves the largest gap "
              f"{base.gap:.2f} -> {arm.gap:.2f} esd")
    else:
        print("    clause 4: no gap sized in one of the arms")


def _header() -> str:
    return (f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · "
            f"numpy {np.__version__} · python {platform.python_version()} · "
            f"{sys.platform}/{platform.machine()} · venv {sys.prefix}\n"
            f"WP-1127 kill-criterion clauses 2-4, factor {FIRST_RUNG_FACTOR}; "
            f"arms compared inside one process, counts lead the wall clock")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WP-1127 first-rung bound: equivalence")
    ap.add_argument("--cases", default="trigger,cpd",
                    help=f"comma-separated (default trigger,cpd; all: "
                         f"{','.join(CASES)})")
    ap.add_argument("--both", action="store_true",
                    help="also run direction='both' — roughly doubles the wall")
    args = ap.parse_args(argv)

    wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
    unknown = set(wanted) - set(CASES)
    if unknown:
        ap.error(f"unknown case(s): {', '.join(sorted(unknown))}")

    print(_header())
    for key in wanted:
        build, _ = CASES[key]
        try:
            setup = build()
        except (FileNotFoundError, OSError) as exc:
            print(f"\n  {key}: skipped — {exc}")
            continue
        base = _run_arm(setup, None, "forward")
        arm = _run_arm(setup, FIRST_RUNG_FACTOR, "forward")
        _report(key, base, arm)
        if args.both:
            _report_both(key,
                         _run_arm(setup, None, "both"),
                         _run_arm(setup, FIRST_RUNG_FACTOR, "both"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
