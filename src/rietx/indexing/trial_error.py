"""Engine B — index-heuristic trial and error: assume the indices, **solve** the
metric, then check the solution against every line.

*Sources*: Werner, P.-E. (1964), *Z. Kristallogr.* **120**, 375-387; Werner,
Eriksson & Westdahl (1985), *J. Appl. Cryst.* **18**, 367-370 (TREOR90); Altomare
*et al.* (2000) **33**, 1180-1186 and (2009) **42**, 768-775 (N-TREOR / N-TREOR09).
**Papers only** — no TREOR or EXPO code was read or ported.

**It is the same linearity as WP-1021, used from the other end.**  Where dichotomy
*bounds* Q over a box of metrics, this engine *assumes* the hkl of n base lines and
solves the n×n system M·θ = Q_base exactly, n being the metric degrees of freedom.
There is no tolerance in the solve at all: the tolerance is spent afterwards,
checking the solution against every usable line.  That makes it seconds where
dichotomy is minutes, and it makes its failure mode completely different — which is
the entire reason both exist (``engines.py``).

**Its failure mode is a bad base line**, and it is not shared with dichotomy: one
impurity among the base lines poisons the exact solve.  So base sets are iterated
(leave-k-out is implicit in ``combinations``) and every solution must survive the
full-list check.  Its *other* failure mode is a dominant zone — one axis long
enough that a low-angle line carries an index outside the table — and this engine
raises that itself, by **measuring** it: if nothing was found, the search is
retried with a table one index wider, and a cell appearing only then is evidence
the table was the binding constraint.  That is the engine's own experience rather
than a proxy statistic, which is what WP-1019 measured a census could not supply.

**The index table is the distinct rows of the design matrix, not the distinct
hkl.**  Q depends on hkl only through ``design_matrix(hkl) @ basis.T``, so in a
cubic cell every reflection with h²+k²+l² = 9 is one trial label, not three.
Deriving the table that way rather than tabulating per system collapses the
enumeration by one to two orders of magnitude and is right in any setting.
"""

from __future__ import annotations

import time
from itertools import combinations

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import PeakList
from .engines import (
    SYSTEM_ORDER,
    Budget,
    EngineCandidate,
    EngineResult,
    SearchSpec,
    assign_lines,
    dedup_candidates,
    effective_shift_allowance,
    incomplete_diagnostic,
    indexes_the_search_lines,
    provisional_payload,
    rank_candidates,
    refine_with_shift,
    reflection_ceiling_ok,
    register_engine,
    search_line_order,
    search_volume_ceiling,
    shift_allowance_diagnostic,
    solution_key,
    trial_hkl,
)
from .qspace import (
    cell_from_af,
    design_matrix,
    metric_basis,
    refine_candidate,
    sigma_effective,
)

#: Largest |h|, |k| or |l| a **base line** may be given.  Two, and the bound is a
#: statement rather than a limit: the base lines are the lowest-Q ones, and a
#: low-angle line needing an index of 3 or more is a dominant-zone case, which this
#: engine *reports* (see :data:`DOMINANT_ZONE_PROBE_STEP`) rather than
#: brute-forcing.  The enumeration goes as (table size)ⁿ, so raising this by one is
#: not a small change.
BASE_INDEX_MAX = 2
#: Index ceilings the dominant-zone probe tries, in order, stopping at the first
#: that finds a cell.  A **ladder**, not one step, and that was measured: on a
#: tetragonal cell with c = 26 Å whose lowest *observed* lines are 105, 106 and 009,
#: a table one index wider still cannot label them, so a single-step probe reported
#: nothing and the engine's silence stayed unexplained.  A dominant row makes the
#: needed index large, not slightly larger.
DOMINANT_ZONE_PROBE_LADDER: tuple[int, ...] = (3, 5, 9)
#: Seconds one rung of that ladder may take, capped further by the caller's own
#: ``budget_seconds``.  A **runaway guard on a diagnostic**, not a timer: the probe
#: runs only after the search has already found nothing, so its whole job is to
#: explain a silence without costing more than the search did.
#:
#: Raised from a hard-coded 10.0 in WP-1026, and the reason is CLAUDE.md's rule
#: about budgets in tests reaching one rank down into the library.  The three rungs
#: on the construction this exists for cost **4.3 s serially**, so 10 s was a ~3×
#: margin on the widest rung — and under ``-n auto`` on a 10-core machine that is a
#: race, which is how it was found: ``test_a_dominant_row_is_raised_from_the_engines
#: _own_experience`` failed in the full suite and passed on its own, asserting the
#: absence of a *diagnostic* for a reason that had nothing to do with the index
#: table.  A diagnostic that appears only on an idle machine is worse than one that
#: costs a few seconds more.
DOMINANT_ZONE_PROBE_SECONDS = 30.0
#: Metric degrees of freedom above which the probe is not attempted.  The
#: enumeration is (labels)ⁿ and the probe deliberately uses a *large* table, so it
#: is affordable exactly where the condition it looks for lives: a dominant zone or
#: row is a statement about one axis, and one long axis is what the high-symmetry
#: systems have room to express.
DOMINANT_ZONE_MAX_DOF = 2
#: Base lines the combinations are drawn from, as ``max(n + 4, this)``.  Spare
#: lines beyond the metric degrees of freedom buy two different things, and the
#: second one is why the pool is this long:
#:
#: * **leave-k-out** over the base set — with an impurity among the lowest lines,
#:   some combination of size n still misses it;
#: * **a line that determines the cross terms at all.**  Measured on a monoclinic
#:   cell (8.875, 16.408, 7.137, β = 93.84°): its six lowest reflections are 010,
#:   100, 020, 110, 001, 011 — every one of them has h·l = 0, so *no* 4-subset of
#:   them determines E and the exact solve is singular for every base set in the
#:   pool.  The first reflection with a non-zero cross term is the eighth line
#:   (10-1).  A pool of six therefore cannot index a monoclinic cell at all, and it
#:   fails by finding partial cells with the right b axis rather than by finding
#:   nothing, which is the worse failure of the two.
BASE_POOL_MIN = 8
#: Assignments enumerated per base set.  The table is **shrunk** (smallest ‖m‖
#: first) until ``len(table)ⁿ`` fits, and a shrunk table sets
#: ``search_complete = False``: a truncated enumeration has not covered its space,
#: and "found nothing" must not be able to mean "did not look".
MAX_ASSIGN_PER_BASE = 4_000_000
#: Rows solved per batched ``np.linalg.solve`` call.  Memory, not speed: the batch
#: is (chunk, n, n) float64 plus the same again for the solution.
SOLVE_CHUNK = 200_000


def index_table(basis: np.ndarray, centring: str, max_index: int, *,
                max_rows: int | None = None
                ) -> tuple[np.ndarray, np.ndarray, bool]:
    """Distinct trial labels: ``(m rows, a representative hkl each, truncated)``.

    A *label* is a distinct row of ``design_matrix(hkl) @ basis.T`` — the only
    thing Q sees.  Two reflections with the same row are the same trial, so
    enumerating hkl instead would multiply the search by the Laue multiplicity for
    nothing (cubic: 3 reflections share h²+k²+l² = 9).

    Rows are ordered by ‖m‖, so a truncated table keeps the labels a *low-angle*
    line can plausibly carry — which is the only sensible truncation, and the one
    the dominant-zone probe then tests.
    """
    hkl = trial_hkl(max_index, centring)
    rows = design_matrix(hkl) @ basis.T
    keys = np.round(rows, 9)
    _uniq, first = np.unique(keys, axis=0, return_index=True)
    order = first[np.argsort(np.linalg.norm(rows[first], axis=1))]
    truncated = False
    if max_rows is not None and len(order) > max_rows:
        order, truncated = order[:max_rows], True
    return rows[order], hkl[order], truncated


def _table_rows_allowed(n_dof: int, table_size: int) -> int:
    """Largest table that keeps ``table**n_dof`` inside the enumeration budget."""
    if n_dof <= 0:
        return table_size
    limit = int(MAX_ASSIGN_PER_BASE ** (1.0 / n_dof))
    return max(min(table_size, limit), n_dof + 1)


def allowed_labels(rows: np.ndarray, q_line: float, theta_lo: np.ndarray,
                   theta_hi: np.ndarray) -> np.ndarray:
    """Which labels a line at this Q could carry, given the metric domain.

    **The same corner-exact bound WP-1021 prunes boxes with, used per line.**  Over
    the θ domain the reachable Q of a label is [Σ min(m·θ), Σ max(m·θ)] with the
    extremes at corners, so a label whose whole reachable range misses this line's Q
    cannot be its index — for any metric in the domain.  That is not a heuristic and
    it is worth a great deal: the enumeration is (labels)ⁿ, and the *lowest* line
    can only carry small-‖m‖ labels, because a large one would need an axis longer
    than ``max_d_axis``.  Measured on a monoclinic list, the per-line filter takes
    the enumeration from 31 million assignments to under two.
    """
    pos = rows > 0.0
    q_min = np.where(pos, rows * theta_lo, rows * theta_hi).sum(axis=1)
    q_max = np.where(pos, rows * theta_hi, rows * theta_lo).sum(axis=1)
    return np.flatnonzero((q_min <= q_line) & (q_max >= q_line))


def _combos(per_line: list[np.ndarray]) -> np.ndarray:
    """The Cartesian product of each base line's own allowed labels."""
    if any(len(a) == 0 for a in per_line):
        return np.zeros((0, len(per_line)), dtype=np.int64)
    grids = np.meshgrid(*per_line, indexing="ij")
    return np.column_stack([g.ravel() for g in grids])


def _solve_assignments(rows: np.ndarray, combos: np.ndarray, q_base: np.ndarray,
                       basis: np.ndarray, spec: SearchSpec, vol_max: float,
                       ) -> tuple[np.ndarray, np.ndarray]:
    """Solve every assignment exactly, then apply the three cheap kills.

    Returns ``(af of survivors, the combos that produced them)``.  The kills are in
    cost order and that order is the point — it is what makes a combinatorial
    enumeration tractable:

    1. **a singular system** never reaches the solver (``|det|`` against the matrix
       norm, so the test scales);
    2. **positive-definiteness of G\\*** by Sylvester's criterion on the batch —
       three vectorised comparisons, no eigenvalues;
    3. **axis and volume bounds**, from the diagonal of the metric and its
       determinant, which the previous step already computed.

    Niggli validity is *not* here: it costs a reduction per candidate, and by this
    point the survivors are few enough for the refinement to be the cheaper filter.
    """
    n = combos.shape[1]
    keep_af: list[np.ndarray] = []
    keep_combo: list[np.ndarray] = []
    a_lo = 1.0 / spec.max_d_axis ** 2
    a_hi = 1.0 / spec.min_d_axis ** 2
    for start in range(0, len(combos), SOLVE_CHUNK):
        chunk = combos[start:start + SOLVE_CHUNK]
        m = rows[chunk]                                   # (c, n, n_dof)
        det = np.linalg.det(m)
        scale = np.maximum(np.linalg.norm(m, axis=(1, 2)) ** n, 1e-300)
        good = np.abs(det) > 1e-9 * scale
        if not good.any():
            continue
        m, chunk = m[good], chunk[good]
        # (c, n, 1) right-hand sides, not (c, n): numpy's solve signature is
        # (m,m),(m,n)->(m,n), so a 2-D b is read as a *matrix* of right-hand sides
        # and a 1-D metric (cubic) fails outright rather than broadcasting
        rhs = np.repeat(q_base[None, :, None], len(m), axis=0)
        theta = np.linalg.solve(m, rhs)[:, :, 0]
        af = theta @ basis                                # (c, 6)
        ok = _admissible(af, a_lo, a_hi, spec.min_volume, vol_max)
        if ok.any():
            keep_af.append(af[ok])
            keep_combo.append(chunk[ok])
    if not keep_af:
        return np.zeros((0, 6)), np.zeros((0, n), dtype=np.int64)
    return np.vstack(keep_af), np.vstack(keep_combo)


def _admissible(af: np.ndarray, a_lo: float, a_hi: float, vol_min: float,
                vol_max: float) -> np.ndarray:
    """Sylvester positive-definiteness plus the axis and volume bounds, batched."""
    a, b, c = af[:, 0], af[:, 1], af[:, 2]
    g23, g13, g12 = 0.5 * af[:, 3], 0.5 * af[:, 4], 0.5 * af[:, 5]
    ok = (a > 0.0) & (b > 0.0) & (c > 0.0)
    ok &= a * b - g12 ** 2 > 0.0
    det = (a * b * c + 2.0 * g12 * g13 * g23
           - a * g23 ** 2 - b * g13 ** 2 - c * g12 ** 2)
    ok &= det > 0.0
    ok &= (a >= a_lo) & (a <= a_hi) & (b >= a_lo) & (b <= a_hi)
    ok &= (c >= a_lo) & (c <= a_hi)
    with np.errstate(invalid="ignore", divide="ignore"):
        volume = np.where(det > 0.0, det ** -0.5, np.inf)
    return ok & (volume >= vol_min) & (volume <= vol_max)


def search_trial_error(peaks: PeakList, *, spec: SearchSpec | None = None,
                       quality=None, cancel=None,
                       progress=None, probe: bool = True) -> EngineResult:
    """Assign trial indices to base lines, solve exactly, check against all lines.

    Deterministic and seed-free: the base sets come from ``combinations`` over the
    lowest-Q lines and the labels from a table ordered by ‖m‖, so the same peak
    list gives bit-identical results and the *set* of candidates does not depend on
    the order the lines arrived in.

    ``probe=False`` defers the dominant-zone probe to the caller (WP-1042): the
    probe explains a **whole-run** silence, and a call the scheduler has
    restricted to one system cannot know one — left on, every empty system of a
    run that found its cell elsewhere would be probed, which is neither what
    the probe means nor a cost ``estimate_ceiling``'s typicals budgeted.
    :func:`dominant_zone_probe` is the deferred ask, made once, over the
    systems the engine actually entered.
    """
    spec = spec or SearchSpec()
    q_all = peaks.q()
    tt_all = peaks.two_theta()
    allowance, assumed = effective_shift_allowance(spec, quality)
    sigma = sigma_effective(peaks.q_esd(), tt_all, peaks.wavelength, allowance)
    tt_max = float(peaks.two_theta_max)

    systems = [s for s in SYSTEM_ORDER if s in spec.systems]
    result = EngineResult(engine="trial_error")
    if len(q_all) < 2:
        result.diagnostics.append(Diagnostic(
            level="error", code="INDEX_DATA_INSUFFICIENT",
            message="a lattice cannot be constrained by fewer than two lines",
            where=[f"{len(q_all)} usable lines"],
            suggestion="run assess_peak_list before searching"))
        return result

    raw: list[EngineCandidate] = []
    incomplete: list[str] = []
    capped: list[str] = []
    stopped: list[str] = []
    for system in systems:
        # not started ⇒ not claimed — the same rule as ``search_dichotomy``,
        # and what keeps "not reached" distinct from "truncated" (WP-1037)
        if cancel is not None and bool(cancel):
            break
        result.systems_searched += (system,)
        if progress is not None:
            progress.start(f"trial_error:{system}", engine="trial_error",
                           system=system)
        budget = Budget(spec.budget_seconds, cancel)
        basis = metric_basis(system)
        vol_max = search_volume_ceiling(spec, quality, system)
        found, stats, complete = _search_system(
            peaks, system, basis, spec, budget, q_all, sigma, tt_all, tt_max,
            vol_max)
        raw.extend(found)
        result.search_complete[system] = complete
        for key, value in stats.items():
            result.stats[f"{system}.{key}"] = value
        if not complete:
            # the token (the run's ceiling or the caller) outranks the
            # unit's own clock, and a unit neither stopped hit a size cap,
            # where more time changes nothing (``incomplete_diagnostic``)
            if cancel is not None and bool(cancel):
                stopped.append(system)
            elif budget.expired():
                incomplete.append(system)
            else:
                capped.append(system)
        if progress is not None:
            progress.end(f"trial_error:{system}", engine="trial_error",
                         system=system, n_candidates=len(found),
                         complete=complete,
                         provisional=provisional_payload(found))

    # the hand-off pool, not the reported cap — see ``SearchSpec.engine_pool``
    result.candidates = rank_candidates(raw, peaks, k_sigma=spec.k_sigma,
                                        n_unindexed=spec.n_unindexed,
                                        max_candidates=spec.engine_pool(),
                                        q_match=sigma)
    result.stats["candidates.raw"] = float(len(raw))
    if len(result.candidates) >= spec.engine_pool():
        for system in result.systems_searched:
            result.stats[f"{system}.pool_capped"] = 1.0
    result.stats["shift_allowance_deg"] = round(allowance, 5)
    if assumed:
        result.diagnostics.append(shift_allowance_diagnostic(allowance))
    if incomplete or capped or stopped:
        result.diagnostics.append(
            incomplete_diagnostic("trial_error", incomplete, spec.budget_seconds,
                                  capped, stopped))
    if probe and not result.candidates \
            and not (cancel is not None and bool(cancel)):
        # the probe explains a silence, so a cancelled run — whose silence the
        # token explains — skips it.  Probed systems are the *entered* ones:
        # probing a system the search never reached would quietly claim it.
        # ``probe.seconds`` makes its cost visible — WP-1037's task-0 profile
        # found it a third of the worst case and absent from every stat.
        t0 = time.monotonic()
        probe = _dominant_zone_probe(peaks, spec, q_all, sigma, tt_all, tt_max,
                                     list(result.systems_searched), quality,
                                     cancel, progress=progress)
        result.stats["probe.seconds"] = round(time.monotonic() - t0, 3)
        if probe is not None:
            result.diagnostics.append(probe)
    return result


def _search_system(peaks: PeakList, system: str, basis: np.ndarray,
                   spec: SearchSpec, budget: Budget, q_all: np.ndarray,
                   sigma: np.ndarray, tt_all: np.ndarray, tt_max: float,
                   vol_max: float, *,
                   index_max: int = BASE_INDEX_MAX,
                   ) -> tuple[list[EngineCandidate], dict[str, float], bool]:
    n_dof = basis.shape[0]
    search_lines = search_line_order(peaks, spec)
    # The base-line pool is a *prefix of the search lines*, not of the whole list.
    # It has to be: the exact solve assumes small indices, so the pool must be the
    # lowest-Q lines **the search was given** rather than the lowest-Q lines full
    # stop — which on a pattern opening on background are the ones the selection
    # just declined.  This is where WP-1039's rule pays: on SRM 660c the 2θ-order
    # pool poisons every base set and only dichotomy finds the certified cell
    # (``engines_disagree``); on the strongest-N pool both engines find it.
    pool = search_lines[:min(max(n_dof + 4, BASE_POOL_MIN), len(search_lines))]
    if len(pool) < n_dof:
        return [], {"solves": 0.0}, True

    from .dichotomy import _initial_box

    theta_lo, theta_hi = _initial_box(basis, spec)
    found: list[EngineCandidate] = []
    seen: set[tuple[object, ...]] = set()
    n_solved = 0
    complete = True
    for centring in spec.centrings_for(system):
        rows_all, hkl_all_tab, _t = index_table(basis, centring, index_max)
        allowed = _table_rows_allowed(n_dof, len(rows_all))
        rows = rows_all[:allowed]
        hkl_tab = hkl_all_tab[:allowed]
        if allowed < len(rows_all):
            complete = False
        # each line's own allowed labels, once: the filter depends on the line's Q
        # and the metric domain, not on which base set the line ends up in
        per_line = {int(i): allowed_labels(rows, float(q_all[i]), theta_lo,
                                          theta_hi) for i in pool}
        hkl_full = trial_hkl(_scoring_index(spec, q_all, sigma), centring)
        dm_full = design_matrix(hkl_full)
        for base in combinations(range(len(pool)), n_dof):
            if budget.expired():
                # the clock rides the cut return too: a reader telling a clock
                # cut from a cap reads it (WP-1449)
                return found, {"solves": float(n_solved),
                               "seconds": round(budget.elapsed, 3)}, False
            lines = pool[list(base)]
            combos = _combos([per_line[int(i)] for i in lines])
            if not len(combos):
                continue
            af_batch, combo_batch = _solve_assignments(
                rows, combos, q_all[lines], basis, spec, vol_max)
            n_solved += len(combos)
            for af, combo in zip(af_batch, combo_batch):
                # keyed on the centring as well as the metric, because ``seen``
                # spans the centring loop — see ``engines.solution_key`` for the
                # two ways a lazier key silently discards a real hypothesis
                key = solution_key(af, centring)
                if key in seen:
                    continue
                seen.add(key)
                cand = _score(basis, system, centring, spec, af, hkl_full,
                              dm_full, q_all, sigma, peaks.wavelength, tt_max,
                              vol_max, hkl_tab[combo], search_lines, tt_all)
                if cand is not None:
                    found.append(cand)
            if len(found) > 2000:
                found = dedup_candidates(found)
    return (found, {"solves": float(n_solved), "seconds": round(budget.elapsed, 3)},
            complete)


def _scoring_index(spec: SearchSpec, q_all: np.ndarray,
                   sigma: np.ndarray) -> int:
    """Largest |h| the *scoring* set needs — the whole pattern, not the base lines.

    Bounded the same way WP-1021 bounds it: Q ≥ A_min·h², so h ≤ d_max·√Q_max.
    """
    q_hi = float(q_all.max() + spec.k_sigma * sigma.max())
    return int(np.ceil(spec.max_d_axis * np.sqrt(max(q_hi, 1e-12)))) + 1


def _score(basis: np.ndarray, system: str, centring: str, spec: SearchSpec,
           af: np.ndarray, hkl: np.ndarray, dm: np.ndarray, q_all: np.ndarray,
           sigma: np.ndarray, wavelength: float, tt_max: float, vol_max: float,
           base_hkl: np.ndarray, search_lines: np.ndarray,
           two_theta: np.ndarray) -> EngineCandidate | None:
    """Check one exact solution against **every** usable line, then refine.

    The exact solve used n lines and no tolerance; this is where the tolerance is
    spent, and it is the step that makes a poisoned base set harmless — a metric
    fitted to an impurity explains nothing else, so it fails here rather than being
    reported.
    """
    try:
        cell = cell_from_af(af)
    except ValueError:
        return None
    if not reflection_ceiling_ok(cell, wavelength, tt_max):
        return None

    fit = None
    previous: bytes | None = None
    for _pass in range(3):
        line_index, assigned = assign_lines(q_all, sigma, hkl, af,
                                            k_sigma=spec.k_sigma, design=dm)
        if len(line_index) < basis.shape[0] + 1:
            return None
        key = line_index.tobytes()
        if key == previous:
            break
        previous = key
        try:
            fit = refine_candidate(q_all[line_index], sigma[line_index], assigned,
                                   system=system)
        except (ValueError, np.linalg.LinAlgError):
            return None
        af, cell = fit.af, fit.cell
    if fit is None or fit.chi2_red > spec.k_sigma ** 2:
        return None
    if not indexes_the_search_lines(line_index, search_lines, spec.n_unindexed):
        return None
    fit = refine_with_shift(fit, spec, system, q_all, sigma, two_theta,
                            wavelength, line_index, assigned)
    if not (spec.min_volume <= fit.volume <= vol_max):
        return None
    cand = EngineCandidate(fit=fit, system=system, centring=centring,
                           engine="trial_error", hkl=assigned,
                           line_index=line_index, n_lines=len(q_all))
    cand.base_hkl = np.asarray(base_hkl)
    return cand


def _dominant_zone_probe(peaks: PeakList, spec: SearchSpec, q_all: np.ndarray,
                         sigma: np.ndarray, tt_all: np.ndarray, tt_max: float,
                         systems: list[str], quality, cancel, *,
                         progress=None) -> Diagnostic | None:
    """Was the *index table* the binding constraint?  Measure it, don't infer it.

    WP-1019 established that a dominant zone is not detectable from a census of the
    peak list — the statistic it tried scored a general monoclinic cell (+3.3σ)
    higher than the dominant-zone cells it was meant to find (+0.9σ, +0.8σ).  So
    this engine answers the question with its own experience instead: re-run the
    cheap systems with a **ladder** of wider tables, and if a cell appears only
    then, the table was what stood in the way — which is exactly what a long axis
    does to a low-angle line's index.

    The ladder is the part that had to be measured (:data:`DOMINANT_ZONE_PROBE_LADDER`).
    """
    lowest = float(np.degrees(2.0 * np.arcsin(
        peaks.wavelength * np.sqrt(np.min(q_all)) / 2.0)))
    for system in systems:
        basis = metric_basis(system)
        if basis.shape[0] > DOMINANT_ZONE_MAX_DOF:
            continue
        if cancel is not None and bool(cancel):
            return None
        # the probe was invisible in the progress ladder (WP-1037): a unit per
        # probed system, *added* rather than pre-declared, because whether the
        # probe runs at all is known only after the search came back empty
        if progress is not None:
            progress.add(1)
            progress.start(f"probe:{system}", engine="trial_error",
                           system=system, probe=True)
        vol_max = search_volume_ceiling(spec, quality, system)
        hit: Diagnostic | None = None
        for wider in DOMINANT_ZONE_PROBE_LADDER:
            budget = Budget(min(spec.budget_seconds, DOMINANT_ZONE_PROBE_SECONDS),
                            cancel)
            found, _stats, _complete = _search_system(
                peaks, system, basis, spec, budget, q_all, sigma, tt_all, tt_max,
                vol_max, index_max=wider)
            if found:
                hit = Diagnostic(
                    level="warning", code="INDEX_DOMINANT_ZONE",
                    message=(f"no cell was found with base-line indices up to "
                             f"{BASE_INDEX_MAX}, but {len(found)} appeared at "
                             f"indices up to {wider} in {system}: the lowest "
                             "observed lines carry large indices along one axis, "
                             "which is a dominant zone (one short real axis) or a "
                             "dominant row (one long one)"),
                    where=[f"{system}, lowest line {lowest:.2f}° 2θ"],
                    suggestion=(
                        "the lines that would pin the short direction are below "
                        "the measured range or too weak to detect — extend it "
                        "downward if you can.  Otherwise use the dichotomy "
                        "engine, which bounds the metric instead of assuming "
                        "indices and so is indifferent to how large they are, or "
                        f"raise BASE_INDEX_MAX past {wider} for this pattern"))
                break
        if progress is not None:
            progress.end(f"probe:{system}", engine="trial_error",
                         system=system, probe=True, found=hit is not None)
        if hit is not None:
            return hit
    return None


def dominant_zone_probe(peaks: PeakList, *, systems: list[str] | tuple[str, ...],
                        spec: SearchSpec | None = None, quality=None,
                        cancel=None, progress=None) -> Diagnostic | None:
    """The silence-explaining probe, callable on its own (WP-1042).

    ``search_trial_error`` runs it itself when its whole call came back empty;
    the system-major scheduler slices the engine into per-system units, passes
    ``probe=False`` to each, and asks here **once** — after the run, over the
    ``systems`` the engine actually entered, and only when the merged harvest
    is empty.  Probing a system the search never reached would quietly claim
    it, which is the same not-started-⇒-not-claimed rule the engines follow.
    """
    spec = spec or SearchSpec()
    q_all = peaks.q()
    tt_all = peaks.two_theta()
    allowance, _assumed = effective_shift_allowance(spec, quality)
    sigma = sigma_effective(peaks.q_esd(), tt_all, peaks.wavelength, allowance)
    return _dominant_zone_probe(peaks, spec, q_all, sigma, tt_all,
                                float(peaks.two_theta_max), list(systems),
                                quality, cancel, progress=progress)


register_engine(
    "trial_error", search_trial_error,
    "assumes trial indices for a few base lines and solves the metric exactly, "
    "then checks against every line; seconds rather than minutes, and poisoned "
    "by a bad base line rather than by a wide domain")

__all__ = ["BASE_INDEX_MAX", "BASE_POOL_MIN", "DOMINANT_ZONE_PROBE_SECONDS",
           "MAX_ASSIGN_PER_BASE", "dominant_zone_probe", "index_table",
           "search_trial_error"]
