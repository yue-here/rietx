# WP-1998 — A suggestion whose gain lies past its bound

Milestone: unscheduled · Status: 🔄 2026-11-03 — claimed by @mustachefeeling
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-17 — the top suggestion, and `summary()`'s `next:` line, name a parameter that freeing cannot move; a refit shows it, at the cost of a wasted stage

## Goal

`Refinement.suggest` scores a candidate on its bound by the gain it can reach
inside its box, so a parameter whose gradient points through its floor is
never the top suggestion. And `SuggestionResult.best_or_none` agrees with the
ΔBIC its own groups carry, or says plainly that it does not consult it.

## Context

Found 2026-10-17 by WP-1986 while writing `docs/docs/guides/next.md`, on the
shipped fluorapatite tutorial (`FAP.XRA` and `fluorapatite.cif` in
`rietx.examples`). `examples/guides/next.py` builds the state: six-term
Chebyshev, stages `scale_bkg` → `cell` → `profile` run by hand over 15-130°,
then one empty stage on a branch (`rx.Stage("again", [])`) to reach the
minimum (see WP-1421's Inherited entry of the same date for why that moves the
fit). `[dev]`, darwin/arm64, the same on `RIETX_COMPILED=0`.

**1. A candidate on its floor is scored as if it were free in both
directions.** At that state `phases.0.extinction` sits at its stored 0.0,
which is its lower bound. `suggest` gives it gradient ∂χ²/∂p = +42.6 (χ²
falls as it decreases, through the floor), gain 104.1 and ΔBIC +1.2; narrowed
with `include="phases.*", exclude=["*.occ"]` it is the only group, ΔBIC
+1.4, and the summary reads "free phases.0.extinction next". Freed on a
branch, it stays at 0.0, `FLOOR_HIT` fires, and `report.compare_freed` gives
t = 0 and ΔBIC −7. The gain is the exact one-parameter Gauss-Newton
prediction (`strategy/suggest.py`), which knows nothing of the box. The
exact bounded one-dimensional answer is cheap: with the unconstrained step
δ = −g/(JᵀJ) and distance d to the bound in δ's direction, the reachable gain
is gain × (2α − α²) at α = min(1, d/|δ|), which is 0 on the bound with δ
pointing out. Siblings to check: an upper bound (`max`), a candidate near
rather than on a bound, and the seeded candidates (roughness, Stephens) whose
probe point is not the stored value.

**2. `best_or_none` ignores ΔBIC.** Its docstring gates on the noise floor and
an unresolved tie only. At the state before the empty stage, the narrowed
query returns `phases.0.extinction` from `best_or_none()` while its group's
ΔBIC is −1.799 and the summary says "ΔBIC refuses it". The old manual's
`using/report.md` snippet (`best = s.best_or_none(); ref.set_vary([best.path],
True)`) therefore frees a parameter the same result refuses. Either gate on
ΔBIC where it was measured, or keep the gate and rename or document it so a
reader does not take it as the answer. The new guide says it does not check
ΔBIC; a change updates that sentence.

The tier of each rule this WP adds (written 2026-11-03, the WP predating the
template line):
- **Bounded gain** — tier 1, arithmetic. The linearised Σr² along one
  candidate, with the free block re-solved, is an exact quadratic in its step,
  so the reachable drop at a clipped step is `gain·α(2 − α)`; a group's is the
  bounded least-squares optimum of the same linearisation (BVLS, Stark &
  Parker 1995). No threshold, no default: the box is the solver's own
  (`ParameterTable.bounds()`).
- **`best_or_none` abstains when the leader's ΔBIC ≤ 0** — statistic tier 2
  (Schwarz 1978, the package's one BIC form), threshold 0 tier 1 (the sign
  the criterion defines), action: *abstain*, the conservative direction —
  `None` names nothing, and the groups stay for a caller who reads them.

### Inherited

## Non-goals

- The frozen-window gap that moves the minimum (WP-1421 owns it).
- Ranking by leverage at all: Toby (2024) is why suggestions stay advisory.

## Tasks

- [x] Bounded gain for a candidate on or near a bound, both sides, seeded
      candidates included; a test on the fluorapatite state above where
      extinction drops below the noise floor.
- [x] `best_or_none` and ΔBIC: decide the gate, then make the summary, the
      method and its docstring say one thing.
- [x] Update `examples/guides/next.py`'s assertions and
      `docs/docs/guides/next.md`'s sentence on `best_or_none` if either moves.
- [ ] Skill: the row on reading `suggest`, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest.py tests/test_examples.py -n auto --dist loadgroup
```

## Handover log

- **2026-10-17** — filed from WP-1986's guide work. No open WP owns
  `suggest`: WP-1050 built it and is closed, and WP-1434's bound test is about
  results, not candidates.
