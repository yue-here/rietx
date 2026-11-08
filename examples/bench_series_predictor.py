"""WP-1124: the warm-series continuation probe — does a predictor seed beat a copy?

Run: ``.venv/bin/python examples/bench_series_predictor.py``

`sequential.py` warm-starts pattern k+1 from pattern k's converged endpoint.
That is a **zeroth-order predictor** of a trajectory that moves smoothly along
the series coordinate.  The solver survey's §2.B8 claims a first-order one
lands closer, and closer matters twice: fewer iterations per warm fit (direct),
and fewer *rung escalations* (amplified — WP-1123 measured the same chain flip
from 1.04× worse to 1.12× better across one unrelated commit, because a bounded
per-fit difference becomes an escalation taken or avoided and the chain
integrates it).

This script measures that claim.  It ships **no** predictor: the two arms are
built out of ``SequentialRefinement.fit(prepare=…)``, a hook that already
exists, and the library is untouched — which is the same discipline WP-1114's
spike ran under, and the reason a negative verdict costs nothing to act on.

Three arms
----------
``copy``     the shipped default: ``prepare=None``, ``carry=("*",)``.  Every
             other arm is judged against this one and nothing else.
``secant``   seed pattern k+1 at ``θ_k + (θ_k − θ_{k−1})`` in **physical**
             values, per entry, shrunk to stay inside the entry's own bounds.
             Costs nothing but two dictionaries.
``tangent``  one Gauss-Newton step against pattern k+1's data from pattern k's
             converged state: solve ``J·δ ≈ −r`` at that state, both already
             weighted, and take θ + δ.  Costs one Jacobian and two residuals a
             pattern, and **the totals below charge it for them** — a predictor
             that buys ten iterations for the price of twelve is not a saving.

Four rules this script is written around
----------------------------------------
1. **The predictor is the first rung only.**  ``prepare`` is called on every
   ladder rung, the cold rescue included, and on the cold rung it would be
   handed the *initial* model rather than a warm one — extrapolating there
   corrupts the rescue.  So each arm acts on the first call per pattern and
   returns immediately on any later one, which leaves ``warm_staged`` and
   ``cold`` **bit-identical to the copy arm's**.  The predictor changes the
   first rung; the ladder stays the rescue it was.
2. **The secant needs two converged points, so it starts at pattern 2.**  At
   pattern 1 the only earlier state is the cold fit's answer and, before it,
   the initial guess — the difference between them is a cold-start correction,
   not a step along the series.  Pattern 1 therefore gets the copy seed in
   every arm.
3. **A quarantined pattern extrapolates to nothing, for free.**  The state
   ``prepare`` is handed is whatever ``_carry_into`` wrote, i.e. the last
   *accepted* endpoint; when the chain steps over a diverged pattern that
   state does not advance, the snapshot difference is identically zero and the
   predictor degenerates to the copy seed.  No special case is needed and none
   is written.
4. **Extrapolation is clamped as a step, never as a value.**  A width sitting
   near zero extrapolates negative, and a refused write would be a probe bug,
   not a finding (the WP says so).  ``_limited`` shrinks the step to keep
   ``keep`` of the gap to the bound, so a parameter already *at* its bound
   moves by exactly zero instead of by a repaired amount.

Read-outs
---------
Per arm: whole-chain wall, whole-chain ``nfev``/``njev`` (the WP-1111 counting
scaffold, imported rather than restated), predictor cost, per-pattern wall /
iterations / rung, escalation and quarantine counts, and **endpoint agreement**
against the copy arm in esd units — because a seed that changes the answer has
not made the same fit faster.  ``--direction both`` adds the path-dependence
read-out: a predictor changes the path, and the largest forward-backward gap
(``SeriesResult.direction_gaps``) must not worsen under it.

Wall clock is a range over ``--repeats``; run it idle and alone
(``bench_refinement``'s four rules apply here unchanged).
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from bench_refinement import _counting, _Counts, _trigger_cold, _trigger_pattern  # noqa: E402

from rietx import _about  # noqa: E402
from rietx.model.forward import compile_model  # noqa: E402
from rietx.params.vector import ParameterTable  # noqa: E402

# -- the two predictors ----------------------------------------------------

def _limited(cur: float, step: float, lo: float, hi: float,
             keep: float = 0.99) -> float:
    """``cur + step``, shrunk to keep ``keep`` of the gap to whichever bound it
    heads for.

    The step is clamped, not the value, which is what makes the degenerate
    cases silent: a parameter already sitting on its bound has zero gap, so it
    moves by zero rather than by a repaired amount, and a non-finite step
    leaves the value alone.  ``keep < 1`` keeps the value strictly inside its
    bounds, which the softplus and logit entries before WP-1938 needed; an
    endpoint is a legal value now that every entry refines in its own units.
    """
    if step == 0.0 or not np.isfinite(step):
        return cur
    if step > 0.0 and np.isfinite(hi):
        step = min(step, keep * max(hi - cur, 0.0))
    if step < 0.0 and np.isfinite(lo):
        step = max(step, keep * min(lo - cur, 0.0))
    return cur + step


class _Predictor:
    """Base: first-call-per-pattern gating and the snapshot bookkeeping.

    Subclasses implement :meth:`_seed`.  Everything above it — rules 1-3 in the
    module docstring — is shared, so the two arms differ only in how they turn
    a warm state into a seed.
    """

    name = "copy"

    def __init__(self) -> None:
        self.applied: list[int] = []
        self.rejected: list[int] = []
        self.wall = 0.0
        self.nfev = 0
        self.njev = 0
        self._last: int | None = None
        self._step: int | None = None

    def prepare(self, index: int, data, structure, instrument) -> None:
        """Gate on the walk, because ``prepare`` sees more calls than patterns.

        Two things have to be read off the index sequence alone, since the hook
        is told neither the rung nor the pass.  A **repeat** of the last index
        is an escalation rung — rule 1, the ladder's business — and a **break in
        the walk's stride** is ``direction="both"`` turning round to start the
        backward chain, whose first pattern is cold and whose snapshot history
        must start empty.  Both are silent no-ops that leave the arm identical
        to ``copy`` for that call.
        """
        if self._last is not None and index == self._last:
            return
        step = None if self._last is None else index - self._last
        fresh = self._last is None or (self._step is not None
                                       and step != self._step)
        self._step = None if fresh else step
        self._last = index
        if fresh:                   # the cold pattern of this pass — never seeded
            self._new_pass()
            return
        t0 = time.perf_counter()
        self._seed(index, data, structure, instrument)
        self.wall += time.perf_counter() - t0

    def _new_pass(self) -> None:
        """Called on the cold pattern of each chain; subclasses drop their state."""

    def _seed(self, index, data, structure, instrument) -> None:
        raise NotImplementedError


class _Secant(_Predictor):
    """θ_k + (θ_k − θ_{k−1}), per entry, in physical values."""

    name = "secant"

    def __init__(self) -> None:
        super().__init__()
        self.previous: dict[str, float] | None = None

    def _new_pass(self) -> None:
        self.previous = None

    def _seed(self, index, data, structure, instrument) -> None:
        table = ParameterTable(structure, instrument)
        current = {e.path: e.value for e in table.entries}
        # rule 2: the first warm pattern stores one point and seeds nothing —
        # its only predecessor is the cold answer, and before that the initial
        # guess, whose difference is a cold-start correction rather than a step
        previous, self.previous = self.previous, current
        if previous is None:
            return
        moved = 0
        for e in table.entries:
            was = previous.get(e.path)
            if was is None:
                continue
            step = e.value - was
            new = _limited(e.value, step, e.lo, e.hi)
            if new != e.value:
                moved += 1
            e.value = new
        if not moved:
            return
        # hold everything and read the affine map back, so ties are re-derived
        # from whatever their sources now hold — `_carry_into`'s own move, for
        # the same reason: a seed must never leave a tie inconsistent
        table.set_vary(["*"], False)
        resolved = table.decode(np.zeros(0))
        for e in table.entries:
            e.value = resolved[e.path]
        table.apply_to_models(structure, instrument)
        self.applied.append(index)


class _Tangent(_Predictor):
    """One Gauss-Newton step against the next pattern's data.

    ``J·δ ≈ −r`` at the warm state, in θ space, where the solver's own bounds
    live: each entry's ``min``/``max`` in its own units since WP-1938.

    The step is **corrector-checked**: the residual is re-evaluated at θ + δ and
    the seed is kept only if the cost actually fell.  An undamped Gauss-Newton
    step on a nonlinear residual can overshoot arbitrarily, and a predictor that
    can leave the pattern worse than the copy seed would be measuring the
    overshoot rather than the extrapolation.  The check costs one residual, and
    every residual and Jacobian this class evaluates is charged to the arm.
    """

    name = "tangent"

    def __init__(self, free_globs: list[str], mode: str = "rietveld",
                 rcond: float = 1e-8) -> None:
        super().__init__()
        self.free_globs = list(free_globs)
        self.mode = mode
        self.rcond = rcond
        self.gains: list[float] = []

    def _seed(self, index, data, structure, instrument) -> None:
        from rietx.optimize.least_squares import _jacobian_for, _make_residual

        table = ParameterTable(structure, instrument)
        table.set_vary(["*"], False)
        table.set_vary(self.free_globs, True)
        if not table.free_paths:
            return
        model = compile_model(structure, instrument, data, mode=self.mode,
                              moving_paths=set(table.moving_paths))
        residual = _make_residual(model, table)
        jacobian = _jacobian_for(model, table, "numpy")
        x0 = table.x0()
        r0 = residual(x0)
        self.nfev += 1
        jac = jacobian(x0)
        self.njev += 1
        delta, *_ = np.linalg.lstsq(jac, -r0, rcond=self.rcond)
        lo, hi = table.bounds()
        x1 = np.array([_limited(float(x), float(d), float(a), float(b))
                       for x, d, a, b in zip(x0, delta, lo, hi)])
        r1 = residual(x1)
        self.nfev += 1
        c0 = float(r0 @ r0)
        c1 = float(r1 @ r1)
        if not np.isfinite(c1) or c1 >= c0:
            self.rejected.append(index)
            return
        self.gains.append(c1 / c0 if c0 else float("nan"))
        table.commit(x1)
        table.apply_to_models(structure, instrument)
        self.applied.append(index)


# -- measurement -----------------------------------------------------------

@dataclass
class ArmRun:
    wall: float
    nfev: int
    njev: int
    pred_wall: float
    pred_nfev: int
    pred_njev: int
    applied: list[int]
    rejected: list[int]
    #: (index, wall, iterations, Rwp, rung, rungs_tried, status, rung_walls)
    #: per pattern — ``wall`` is the sum over every rung the pattern ran, and
    #: ``rung_walls`` breaks it out in ladder order
    per_pattern: list[tuple] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    #: path -> (value, esd) for every pattern, for the agreement read-out
    endpoints: list[dict[str, tuple[float, float | None]]] = field(default_factory=list)
    #: the largest forward-backward gap in combined esds, ``direction="both"``
    gap: float | None = None


def largest_gap(series) -> float | None:
    """The series' largest forward-backward gap in combined esds, or ``None``.

    Read off ``SeriesResult.direction_gaps`` (WP-2003, C5), which replaced the
    ``SEQUENTIAL_PATH_DEPENDENT`` code this read-out once counted.
    """
    sized = [abs(g.gap_esd) for g in series.direction_gaps or []
             if g.gap_esd is not None]
    return max(sized) if sized else None


def _series_setup(refit: str, n: int, ppm: float):
    from test_acceptance_qpa_roundrobin import qpa_plan

    patterns = [_trigger_pattern(seed=2000 + i, drift=i * ppm * 1e-6)
                for i in range(n)]
    structure, instrument = _trigger_cold(patterns[0])
    return patterns, structure, instrument, qpa_plan(), refit


def _collapsed_globs(plan) -> list[str]:
    """The single warm stage's turn-on globs, from the library's own collapse."""
    from rietx.sequential import _collapse

    return list(_collapse(plan).stages[0].turn_on)


def _run_arm(arm: str, setup, direction: str) -> ArmRun:
    from rietx.sequential import refine_sequential

    patterns, structure, instrument, plan, refit = setup
    if arm == "copy":
        pred = _Predictor()
        prepare = None
    elif arm == "secant":
        pred = _Secant()
        prepare = pred.prepare
    elif arm == "tangent":
        pred = _Tangent(_collapsed_globs(plan))
        prepare = pred.prepare
    else:                                     # pragma: no cover - argparse gates
        raise ValueError(f"unknown arm {arm!r}")

    # every rung's bracket, appended rather than overwritten: a pattern that
    # escalated ran the ladder's first rung *and* the one that rescued it, and
    # the failed one is exactly what a predictor is being asked to prevent — so
    # a collector that keeps only the last `fit_start` measures the cheap half
    # of the expensive patterns (see § Findings; `bench_refinement` had this)
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
        series = refine_sequential(patterns,
                                   structure.model_copy(deep=True),
                                   instrument.model_copy(deep=True),
                                   plan=plan, refit=refit, direction=direction,
                                   prepare=prepare, events=collect)
        wall = time.perf_counter() - t0

    per, endpoints = [], []
    for entry in series.entries:
        spans = rung_spans(entry.index)
        per.append((entry.index, sum(spans), entry.n_iterations,
                    entry.statistics.rwp if entry.statistics else float("nan"),
                    entry.rung, list(entry.rungs_tried), entry.status, spans))
        endpoints.append({p.path: (p.value, p.stderr) for p in entry.parameters})
    return ArmRun(wall, counts.nfev, counts.njev,
                  pred.wall, pred.nfev, pred.njev,
                  list(pred.applied), list(pred.rejected), per,
                  [d.code for d in series.diagnostics], endpoints,
                  largest_gap(series))


#: The trigger case's one exactly degenerate family — the instrument Lorentzian
#: term and every phase's, which add to one width.  WP-1123 measured the flip
#: moving ``instrument.profile.x`` by +0.0013165 against each phase's
#: ``lor_size`` by −0.0012897 to −0.0013300, i.e. along the degeneracy, and
#: reported the rest of the model at 0.001 esd.  A seed that changes the split
#: without changing the sum has not changed the answer, so the read-out below
#: says how much of a disagreement lies here before it says how large it is.
_DEGENERATE_WIDTH = ("instrument.profile.x", "phases.*.lor_size")


def _in_family(path: str) -> bool:
    import fnmatch

    return any(fnmatch.fnmatchcase(path, g) for g in _DEGENERATE_WIDTH)


def _agreement(base: ArmRun, other: ArmRun
               ) -> tuple[list[tuple[int, float, str]], list[tuple[str, float]],
                          list[tuple[int, float, str]]]:
    """Per-pattern worst |Δ|/esd against the copy arm, plus who carried it.

    Returns ``(per_pattern, worst_paths, outside_family)`` — the third being
    the same per-pattern measure with :data:`_DEGENERATE_WIDTH` dropped, which
    is the one that says whether the answer moved rather than the split.

    The esd is the **copy** arm's throughout, so every arm is judged in one set
    of units; a row with no esd (an unmeasured direction — WP-1110 makes that
    ``None`` rather than a small number) is skipped rather than scored against
    a zero it would divide by.
    """
    rows, outside = [], []
    by_path: dict[str, float] = {}
    for i, (b, o) in enumerate(zip(base.endpoints, other.endpoints)):
        worst, where = 0.0, ""
        worst_out, where_out = 0.0, ""
        for path, (value, esd) in b.items():
            if esd is None or not np.isfinite(esd) or esd <= 0 or path not in o:
                continue
            ratio = abs(o[path][0] - value) / esd
            by_path[path] = max(by_path.get(path, 0.0), ratio)
            if ratio > worst:
                worst, where = ratio, path
            if not _in_family(path) and ratio > worst_out:
                worst_out, where_out = ratio, path
        rows.append((i, worst, where))
        outside.append((i, worst_out, where_out))
    top = sorted(by_path.items(), key=lambda kv: -kv[1])[:4]
    return rows, top, outside


def _escalations(run: ArmRun) -> int:
    return sum(1 for row in run.per_pattern if len(row[5]) > 1)


def _quarantined(run: ArmRun) -> int:
    return sum(1 for row in run.per_pattern if row[6] == "diverged")


def _wasted(run: ArmRun) -> float:
    """Wall spent in ladder rungs that were **thrown away**.

    Every rung but the last one a pattern ran: the escalation happened because
    the fence rejected what came before, so that wall bought nothing.  This is
    the quantity a predictor is bidding for, and on the ``refit="single"``
    trigger series it is most of the band."""
    return sum(sum(row[7][:-1]) for row in run.per_pattern if len(row[7]) > 1)


def _header(repeats: int) -> str:
    return (f"{_about.DIST_NAME} {version(_about.DIST_NAME)} · "
            f"numpy {np.__version__} · python {platform.python_version()} · "
            f"{platform.system().lower()}/{platform.machine()} · "
            f"venv {Path(sys.prefix)}\n"
            f"best-of-{repeats}, wall clock as a RANGE — run idle, alone; "
            f"never compare across machines")


def _report(arm: str, runs: list[ArmRun], base: ArmRun | None) -> None:
    walls = [r.wall for r in runs]
    last = runs[-1]
    # the counting scaffold wraps scipy's entry point, which the predictor does
    # not go through — so its own evaluations are added here rather than
    # assumed: a seed bought with more work than it saves is not a saving
    nfev = [r.nfev + r.pred_nfev for r in runs]
    print(f"\n  {arm:8s} wall {min(walls):7.2f}-{max(walls):7.2f} s   "
          f"nfev {min(nfev)}-{max(nfev)}   njev {last.njev + last.pred_njev}   "
          f"escalations {_escalations(last)}   quarantined {_quarantined(last)}")
    fits = sum(row[1] for row in last.per_pattern)
    print(f"           of the last repeat's {last.wall:.2f} s: {fits:.2f} s in "
          f"fits, {_wasted(last):.2f} s of that in discarded rungs, "
          f"{last.wall - fits:.2f} s between them")
    if last.pred_nfev or last.pred_njev or last.pred_wall:
        print(f"           predictor cost: {last.pred_wall:.2f} s, "
              f"{last.pred_nfev} residual, {last.pred_njev} Jacobian "
              f"(charged to the totals above; the wall is inside the fits row)")
        print(f"           applied to patterns {last.applied}"
              + (f", rejected on {last.rejected}" if last.rejected else ""))
    codes = sorted(set(last.diagnostics))
    if codes:
        print(f"           diagnostics: {', '.join(codes)}")
    print(f"           {'pat':>3s} {'wall':>7s} {'iter':>6s} {'Rwp':>8s}  "
          f"{'kept rung':14s} rungs run (wall each)")
    for index, wall, iters, rwp, rung, tried, status, spans in last.per_pattern:
        flag = "" if status == "converged" else f"  <{status}>"
        detail = "  ".join(f"{name}={s:.2f}s"
                           for name, s in zip(tried, spans))
        print(f"           {index:3d} {wall:7.2f} {iters:6d} {rwp:8.5f}  "
              f"{rung:14s} {detail}{flag}")
    if base is not None:
        rows, top, outside = _agreement(base, last)
        if rows:
            worst = max(rows, key=lambda r: r[1])
            med = float(np.median([r[1] for r in rows]))
            wout = max(outside, key=lambda r: r[1])
            mout = float(np.median([r[1] for r in outside]))
            print(f"           agreement vs copy: median {med:.3f} esd, "
                  f"max {worst[1]:.3f} esd on pattern {worst[0]} ({worst[2]})")
            print(f"           …outside the degenerate width family: median "
                  f"{mout:.3f} esd, max {wout[1]:.3f} esd on pattern "
                  f"{wout[0]} ({wout[2]})")
            print("           worst paths: " + ", ".join(
                f"{p} {v:.2f}" for p, v in top))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arms", default="copy,secant,tangent",
                    help="comma-separated: copy, secant, tangent")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--refit", default="single", choices=("single", "stages"))
    ap.add_argument("--direction", default="forward",
                    choices=("forward", "backward", "both"))
    ap.add_argument("--patterns", type=int, default=10)
    ap.add_argument("--ppm", type=float, default=100.0,
                    help="cell ramp per step, ppm (harness default 100)")
    args = ap.parse_args(argv)

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    print(_header(args.repeats))
    print(f"trigger-shaped series (simulated): {args.patterns} patterns, "
          f"{args.ppm:g} ppm/step ramp, refit={args.refit!r}, "
          f"direction={args.direction!r}")

    setup = _series_setup(args.refit, args.patterns, args.ppm)
    base: ArmRun | None = None
    for arm in arms:
        runs = [_run_arm(arm, setup, args.direction) for _ in range(args.repeats)]
        _report(arm, runs, None if arm == "copy" else base)
        if arm == "copy":
            base = runs[-1]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
