"""Parallel tempering over a :class:`~rietx.solve.moves.SearchSpace` (#562 S2a; WP number pending).

**The energy** of a replica is J = (χ²_data + w·E_clash)/χ²_floor, with χ²_data
:meth:`~rietx.solve.cost.SolveCost.chi2` at the closed-form scale, E_clash the
clash term of :class:`~rietx.solve.moves.Clash` at its weight, and χ²_floor the
cost's own Pawley floor.  Temperatures are in the same units, so a ladder
means the same thing on any pattern.  The data term and the prior are kept
apart in every record (:class:`Visit`), never summed into one number that
cannot be taken apart again (WP-1997's rule).

**The ladder** (:class:`Ladder`) is planned, geometric and frozen: there is no
burn-in and no feedback, as #562's 2026-09-30 measurement chose over an
adaptive one (a paired run on a synthetic P2₁/c set: 36/50 against 30/50
adaptive and 20/50 fixed at 18–48 DOF).  Its top temperature is the spread
(standard deviation) of J over uniform random structures on the same search
space, measured per run (:func:`random_spread`), so the hottest replica moves
between basins of the depth random structures differ by.  The span from top
to bottom is the caller's ``span`` and each rung's move size the caller's
``step`` pair interpolated geometrically.  **The engine chooses none of its
search settings** (#1224: a machinery change adds no tier-3 number): the
span, the move sizes, the exchange probability, the swap cadence and the
random-structure count are required arguments, the values the S2a acceptance
ran and their measurements are ``tests/test_solve_engine.py``'s, and the
defaults land with the solve entry point.  :meth:`Ladder.predicted_swap`
gives Earl & Deem's (2005, *Phys. Chem. Chem. Phys.* 7, 3910, eq. 3, Kofke's)
Gaussian estimate ⟨A⟩ = erfc[½·C_v^½·(1 − ρ)/(1 + ρ²)^½], ρ = T_i/T_{i+1}, at
the harmonic C_v = n_par/2, beside the measured rate: #562 found the measured
rate 10³–10⁶ times further from the harmonic one than the target assumes, so
it is reported and never gated.

**A sweep** proposes one move per replica, on one unit chosen uniformly among
those that move (a free site's move is a site exchange with probability
``exchange`` where it has a partner), and evaluates every replica in one
batched call: a one-atom move through
:meth:`~rietx.solve.moves.Scattering.orbit_sums_one`, a fragment or an
exchange through :meth:`~rietx.solve.moves.Scattering.orbit_sums` on the atoms
it moved, both updating the running amplitudes F_new = F_old + a_j·(S_j,new −
S_j,old).  The clash change of a one-atom move is the per-site energy at
w_same = ½ (:func:`~rietx.solve.chemistry.site_clash`'s identity); any other
move recomputes the total.  Metropolis acceptance is min(1, exp(−ΔJ/T)) (Metropolis et al. 1953,
J. Chem. Phys. 21, 1087).  Every
``swap_every`` sweeps, neighbours exchange with min(1, exp[(β_i − β_j)(J_i −
J_j)]) (Earl & Deem 2005, eq. 2), pairs alternating even and odd, which keeps
detailed balance with the moves between them; attempts and acceptances are
recorded **per neighbour pair**.  Every ``refresh_every`` sweeps the running
sums are rebuilt from the coordinates, so rounding cannot accumulate, and the
largest difference a rebuild found is recorded (:attr:`SeedRun.drift`).

**A seed** (:func:`temper`) is one ``numpy`` generator seed: the starts, the
moves and the swaps are all drawn from it, so a seed reruns bit for bit on one
machine and one path (compiled or numpy).  The move budget is
``sweeps × replicas``; ``wall_seconds`` is a runaway guard, never a timer, and
a run it stops says so (:attr:`SeedRun.stopped`).  Each rung keeps the lowest-J
state it held, and :func:`polish` takes each to its local minimum of J
(L-BFGS-B), so a candidate's coordinates are a minimum, not a thermal sample.

**Stopping and resuming** (#998, as accepted on the issue 2026-10-16).  The
loop reads ``cancel`` (an :class:`~rietx.optimize.cancel.CancelToken`, or
anything answering ``is_set()``) after every sweep, cooperatively, as a fit
reads it between evaluations; a stopped seed says so (``stopped =
"cancelled"``) and keeps its best-so-far.  Its **natural boundary** is a
rebuild of the running sums (every ``refresh_every`` sweeps): there the whole
state is the coordinates, the generator's state and the counters, since every
running sum is recomputed from u, so :class:`TemperState` taken there and
handed back as ``resume`` continues bit for bit — the same moves, the same
swaps, the same rebuilds — and a resumed seed returns the uninterrupted
seed's record.  ``on_boundary`` receives each such state; a sweep between two
boundaries is never saved, so a resume replays at most ``refresh_every``
sweeps.  ``heartbeat`` receives the leader and the ladder's acceptance every
``heartbeat_sweeps`` sweeps.

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.special import erfc

from .moves import Clash, Scattering, SearchSpace

#: Sweeps between full rebuilds of the running orbit sums.
REFRESH_EVERY = 1000


class TemperingRefused(ValueError):
    """The cost cannot carry a temperature: its floor is not positive."""


# ----------------------------------------------------------------------
# the problem: a space, its |F|², the cost and the clash term
# ----------------------------------------------------------------------
@dataclass
class SearchProblem:
    """Everything one energy evaluation reads."""

    space: SearchSpace
    scattering: Scattering
    cost: object                  # SolveCost
    clash: Clash

    def __post_init__(self):
        if not self.cost.chi2_floor > 0.0:
            raise TemperingRefused(
                f"the cost's floor is {self.cost.chi2_floor:g}, not positive: J = χ²/χ²_floor "
                "has no scale to put a temperature on")
        if len(self.scattering.d) != len(self.cost.b):
            raise ValueError(f"the scattering has {len(self.scattering.d)} reflections and "
                             f"the cost {len(self.cost.b)}: build both on one reflection list")

    @property
    def floor(self) -> float:
        return float(self.cost.chi2_floor)

    def evaluate(self, u: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(J, χ²_data, E_clash raw) per row of u (R, n_par), from scratch."""
        u = np.atleast_2d(u)
        xyz = self.space.xyz(u)
        chi2 = self.cost.chi2_batch(self.scattering.f2(xyz))
        e = self.clash.total(xyz) if self.clash.active else np.zeros(len(u))
        return (chi2 + self.clash.weight * e) / self.floor, chi2, e


def random_spread(problem: SearchProblem, rng: np.random.Generator, *,
                  n: int) -> tuple[float, float]:
    """(std, median) of J over ``n`` uniform random structures."""
    if not n >= 2:
        raise ValueError(f"a spread needs at least two random structures, not {n}")
    j, _, _ = problem.evaluate(problem.space.random(rng, n))
    return float(np.std(j)), float(np.median(j))


# ----------------------------------------------------------------------
# the ladder
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Ladder:
    """Temperatures (ascending, J units) and move sizes (Å) per rung."""

    temperatures: np.ndarray
    steps: np.ndarray
    n_par: int
    record: dict = field(default_factory=dict)

    @classmethod
    def planned(cls, t_top: float, n_par: int, n_replicas: int, *,
                span: float, step: tuple[float, float],
                record: dict | None = None) -> Ladder:
        """The geometric ladder from t_top/span to t_top over ``n_replicas``."""
        if n_replicas < 2:
            raise ValueError("a ladder needs at least two replicas")
        if not (t_top > 0.0 and span > 1.0):
            raise ValueError(f"t_top {t_top} must be positive and span {span} above 1")
        if not (step[0] > 0.0 and step[1] > 0.0):
            raise ValueError(f"step {tuple(step)} must be two positive move sizes (Å)")
        x = np.linspace(0.0, 1.0, n_replicas)
        temps = t_top / span * span ** x
        steps = step[0] * (step[1] / step[0]) ** x
        rec = {"t_top": float(t_top), "span": float(span), "step_ang": tuple(step)}
        rec.update(record or {})
        return cls(temps, steps, int(n_par), rec)

    def predicted_swap(self) -> np.ndarray:
        """Earl & Deem (2005) eq. 3 per neighbour pair at C_v = n_par/2."""
        rho = self.temperatures[:-1] / self.temperatures[1:]
        cv = self.n_par / 2.0
        return erfc(0.5 * math.sqrt(cv) * (1.0 - rho) / np.sqrt(1.0 + rho * rho))


# ----------------------------------------------------------------------
# one seed
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Visit:
    """A state with its terms apart: J, χ²_data, raw clash, and u."""

    u: np.ndarray
    j: float
    chi2: float
    clash: float


@dataclass
class TemperState:
    """One seed at a rebuild boundary: everything :func:`temper` needs to
    continue bit for bit (module docstring).  JSON-able through
    :meth:`to_json`; python floats round-trip exactly through ``repr``."""

    done: int                       # sweeps completed
    u: np.ndarray                   # (R, n_par)
    rng: dict                       # the generator's bit_generator.state
    acc: np.ndarray                 # (R,) accepted moves per rung
    sw_try: np.ndarray              # (R−1,)
    sw_ok: np.ndarray               # (R−1,)
    best: list[Visit]               # (R,)
    drift: float
    improved: int                   # the sweep the lowest J last fell

    def to_json(self) -> dict:
        return {"done": int(self.done), "u": self.u.tolist(), "rng": self.rng,
                "acc": self.acc.tolist(), "sw_try": self.sw_try.tolist(),
                "sw_ok": self.sw_ok.tolist(), "drift": float(self.drift),
                "improved": int(self.improved),
                "best": [{"u": v.u.tolist(), "j": v.j, "chi2": v.chi2, "clash": v.clash}
                         for v in self.best]}

    @classmethod
    def from_json(cls, d: dict) -> TemperState:
        return cls(done=int(d["done"]), u=np.array(d["u"], dtype=np.float64), rng=d["rng"],
                   acc=np.array(d["acc"], dtype=np.float64),
                   sw_try=np.array(d["sw_try"], dtype=np.float64),
                   sw_ok=np.array(d["sw_ok"], dtype=np.float64), drift=float(d["drift"]),
                   improved=int(d["improved"]),
                   best=[Visit(np.array(v["u"], dtype=np.float64), float(v["j"]),
                               float(v["chi2"]), float(v["clash"])) for v in d["best"]])


@dataclass
class SeedRun:
    """What one seed did: the record a reader needs to trust or distrust it."""

    seed: int
    ladder: Ladder
    sweeps: int                     # completed
    moves: int                      # sweeps × replicas
    move_accept: np.ndarray         # (R,) per rung
    swap_attempts: np.ndarray       # (R−1,) per neighbour pair
    swap_accepts: np.ndarray        # (R−1,)
    best: list[Visit]               # (R,) lowest J each rung held
    final: list[Visit]              # (R,) each rung's state at the end
    seconds: float
    stopped: str | None             # "wall_seconds" or "cancelled" when the run did not finish
    compiled: dict                  # this seed's calls that took the compiled kernels
    drift: float                    # max |J_running − J_rebuilt| over the rebuilds, J units

    @property
    def swap_acceptance(self) -> np.ndarray:
        """Accepted/attempted per neighbour pair (NaN where none was tried)."""
        with np.errstate(invalid="ignore", divide="ignore"):
            return self.swap_accepts / self.swap_attempts


def temper(problem: SearchProblem, ladder: Ladder, *, seed: int, sweeps: int,
           swap_every: int, exchange: float, refresh_every: int = REFRESH_EVERY,
           wall_seconds: float | None = None,
           start: np.ndarray | None = None, cancel=None, heartbeat=None,
           heartbeat_sweeps: int | None = None, on_boundary=None,
           resume: TemperState | None = None) -> SeedRun:
    """Run one seed of parallel tempering (module docstring).

    ``resume`` continues from a :class:`TemperState` that ``on_boundary``
    handed out on an earlier call with the same problem, ladder and seed;
    ``start`` is then not read.  ``sweeps`` is the seed's total, not what is
    left."""
    if not (swap_every >= 1 and int(swap_every) == swap_every):
        raise ValueError(f"swap_every {swap_every!r} must be a whole number of sweeps, at least 1")
    if not 0.0 <= exchange <= 1.0:
        raise ValueError(f"exchange {exchange} is a probability, in [0, 1]")
    space, sc, cost, clash = problem.space, problem.scattering, problem.cost, problem.clash
    n_rep = len(ladder.temperatures)
    rng = np.random.default_rng(seed)
    if not len(space.movable):
        raise ValueError("no unit of this search has a free parameter")
    if resume is not None:
        if resume.u.shape != (n_rep, space.n_par):
            raise ValueError(f"the state holds u of shape {resume.u.shape}, this search "
                             f"{(n_rep, space.n_par)}")
        u = resume.u.copy()
        rng.bit_generator.state = resume.rng
    elif start is None:
        u = space.random(rng, n_rep)
    else:
        u = space.wrap(np.array(np.broadcast_to(start, (n_rep, space.n_par)), dtype=np.float64))
        space.check_seed(u)
    floor, w = problem.floor, clash.weight
    beta = 1.0 / ladder.temperatures
    used0 = (dict(sc.compiled_used), clash.compiled_used)
    steps = ladder.steps

    def rebuild(u):
        xyz = space.xyz(u)
        s = sc.sums(xyz)
        a, b = sc.amplitudes(s)
        chi2 = cost.chi2_batch(sc.f2_of(a, b))
        e = clash.total(xyz) if clash.active else np.zeros(n_rep)
        return xyz, s, a, b, chi2, e

    xyz, s, a, b, chi2, e = rebuild(u)
    jj = (chi2 + w * e) / floor
    if resume is None:
        best = [Visit(u[r].copy(), float(jj[r]), float(chi2[r]), float(e[r]))
                for r in range(n_rep)]
        acc = np.zeros(n_rep)
        sw_try = np.zeros(n_rep - 1)
        sw_ok = np.zeros(n_rep - 1)
        done = 0
        drift = 0.0
        improved = 0
    else:
        best = list(resume.best)
        acc, sw_try, sw_ok = resume.acc.copy(), resume.sw_try.copy(), resume.sw_ok.copy()
        done, drift, improved = resume.done, resume.drift, resume.improved
    lead = min(v.j for v in best)
    t0 = time.perf_counter()
    stopped = None
    reps = np.arange(n_rep)
    for sweep in range(done, sweeps):
        units = space.movable[rng.integers(len(space.movable), size=n_rep)]
        u_new, moved = space.propose(u, units, steps, rng, exchange=exchange)
        xyz_new = xyz.copy()
        a_new, b_new = a.copy(), None if b is None else b.copy()
        s_upd: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []   # (reps, atoms, S_new)
        one = np.array([len(m) == 1 for m in moved])
        groups: dict[tuple, list[int]] = {}
        for r in np.flatnonzero(~one):
            groups.setdefault(tuple(moved[r]), []).append(int(r))
        if one.any():
            rr = reps[one]
            atom = np.array([moved[r][0] for r in rr])
            xyz_new[rr, atom] = space.xyz(u_new[rr])[np.arange(len(rr)), atom]
            s_new = sc.orbit_sums_one(xyz_new[rr], atom)                    # (r, N)
            ds = s_new - s[rr, atom]
            a_new[rr] += sc.amp_a[atom] * ds
            if b_new is not None:
                b_new[rr] += sc.amp_b[atom] * ds
            s_upd.append((rr, atom[:, None], s_new[:, None, :]))
        for at_t, rl in groups.items():
            rr = np.array(rl)
            at = np.array(at_t)
            xyz_new[np.ix_(rr, at)] = space.xyz(u_new[rr])[:, at]
            s_new = sc.orbit_sums(xyz_new[rr], at)                           # (r, n_k, N)
            ds = s_new - s[np.ix_(rr, at)]
            a_new[rr] += np.einsum("jn,rjn->rn", sc.amp_a[at], ds)
            if b_new is not None:
                b_new[rr] += np.einsum("jn,rjn->rn", sc.amp_b[at], ds)
            s_upd.append((rr, np.broadcast_to(at, (len(rr), len(at))), s_new))
        chi2_new = cost.chi2_batch(sc.f2_of(a_new, b_new))
        e_new = e
        if clash.active:
            e_new = e.copy()
            if one.any():
                rr = reps[one]
                atom = np.array([moved[r][0] for r in rr])
                e_new[rr] += (clash.site(space.images(xyz_new[rr]), atom, 0.5)
                              - clash.site(space.images(xyz[rr]), atom, 0.5))
            if (~one).any():
                rr = reps[~one]
                e_new[rr] = clash.total(xyz_new[rr])
        j_new = (chi2_new + w * e_new) / floor
        dj = j_new - jj
        ok = (dj <= 0.0) | (rng.random(n_rep) < np.exp(-np.maximum(dj, 0.0) * beta))
        if ok.any():
            u[ok] = u_new[ok]
            xyz[ok] = xyz_new[ok]
            a[ok] = a_new[ok]
            if b is not None:
                b[ok] = b_new[ok]
            for rr, at, s_new in s_upd:
                keep = ok[rr]
                for i in np.flatnonzero(keep):
                    s[rr[i], at[i]] = s_new[i]
            chi2[ok], e[ok], jj[ok] = chi2_new[ok], e_new[ok], j_new[ok]
            acc[ok] += 1
            for r in np.flatnonzero(ok & (jj < np.array([v.j for v in best]))):
                best[r] = Visit(u[r].copy(), float(jj[r]), float(chi2[r]), float(e[r]))
        done = sweep + 1
        now_lead = min(v.j for v in best)
        if now_lead < lead:
            lead, improved = now_lead, done
        if done % swap_every == 0:
            for i in range((done // swap_every) % 2, n_rep - 1, 2):
                sw_try[i] += 1
                delta = (beta[i] - beta[i + 1]) * (jj[i] - jj[i + 1])
                if delta >= 0.0 or rng.random() < math.exp(delta):
                    sw_ok[i] += 1
                    for arr in (u, xyz, s, a, chi2, e, jj) + (() if b is None else (b,)):
                        arr[[i, i + 1]] = arr[[i + 1, i]]
        if done % refresh_every == 0:
            j_running = jj
            xyz, s, a, b, chi2, e = rebuild(u)
            jj = (chi2 + w * e) / floor
            drift = max(drift, float(np.max(np.abs(j_running - jj))))
            if on_boundary is not None:
                on_boundary(TemperState(done, u.copy(), rng.bit_generator.state, acc.copy(),
                                        sw_try.copy(), sw_ok.copy(), list(best), drift,
                                        improved))
        if heartbeat is not None and heartbeat_sweeps and done % heartbeat_sweeps == 0:
            with np.errstate(invalid="ignore", divide="ignore"):
                swaps = sw_ok / sw_try
            heartbeat({"sweep": done, "sweeps": int(sweeps), "moves": done * n_rep,
                       "leader_j": lead, "leader_chi2": min(best, key=lambda v: v.j).chi2,
                       "leader_changed": done - improved < heartbeat_sweeps, "sweeps_since_improvement": done - improved,
                       "replica_acceptance": (acc / done).tolist(),
                       "swap_acceptance": [None if not np.isfinite(x) else float(x)
                                           for x in swaps]})
        if cancel is not None and cancel.is_set():
            stopped = "cancelled"
            break
        if wall_seconds is not None and time.perf_counter() - t0 > wall_seconds:
            stopped = "wall_seconds"
            break
    j_running = jj.copy()
    xyz, s, a, b, chi2, e = rebuild(u)
    jj = (chi2 + w * e) / floor
    drift = max(drift, float(np.max(np.abs(j_running - jj))))
    final = [Visit(u[r].copy(), float(jj[r]), float(chi2[r]), float(e[r])) for r in range(n_rep)]
    return SeedRun(seed=seed, ladder=ladder, sweeps=done, moves=done * n_rep,
                   move_accept=acc / max(done, 1), swap_attempts=sw_try, swap_accepts=sw_ok,
                   best=best, final=final, seconds=time.perf_counter() - t0, stopped=stopped,
                   compiled={k: sc.compiled_used[k] - used0[0][k] for k in used0[0]}
                   | {"clash": clash.compiled_used - used0[1]}, drift=drift)


# ----------------------------------------------------------------------
# the polish
# ----------------------------------------------------------------------
def polish(problem: SearchProblem, visit: Visit, *, maxiter: int) -> Visit:
    """The local minimum of J from ``visit`` (L-BFGS-B, finite-difference
    gradient; Byrd et al. 1995, SIAM J. Sci. Comput. 16, 1190), its terms
    re-measured from scratch.  Never worse than the start.  maxiter is the
    caller's: the engine chooses none of its search settings."""
    def f(x):
        return float(problem.evaluate(x[None])[0][0])

    res = minimize(f, visit.u, method="L-BFGS-B", options={"maxiter": maxiter})
    x = res.x if res.fun <= visit.j else visit.u
    u = problem.space.wrap(np.asarray(x)[None])
    j, chi2, e = problem.evaluate(u)
    return Visit(u[0], float(j[0]), float(chi2[0]), float(e[0]))


__all__ = ["REFRESH_EVERY", "Ladder",
           "SearchProblem", "SeedRun", "TemperState", "TemperingRefused", "Visit", "polish",
           "random_spread", "temper"]
