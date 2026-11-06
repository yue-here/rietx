# WP-1998 — A suggestion whose gain lies past its bound

Milestone: unscheduled · Status: ⬜
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

### Inherited

- **From WP-2102 (2026-11-05): the report's Layer 2 suggests a parameter the
  mode force-fixes.** A sibling of this WP's defect in the FitReport rather
  than in `suggest`. On a Le Bail fit of a synthetic LaB6 pattern (the
  `two_patterns[0]` fixture of `tests/test_multi_histogram.py`, Rwp 0.042),
  `ref.report()` offers `refine_scale` (`phases.*.scale`) and `refine_biso`
  (`phases.*.atoms.*.biso`) as active actions. Both paths are held "force-fixed
  by the intensity mode", so freeing either moves nothing. Before WP-2102,
  `report(plan="mccusker_default")` hid the scale one by accident: the
  hand-read preset's scale stage vetoed it as "already refined by the staged
  plan". `apply_strategy_veto` (`report/layer2.py`) sees the plan and the free
  paths only, never the mode-fixed ones. Fold it here, or file it as its own WP
  if the mechanism differs from the bounded gain.

## Non-goals

- The frozen-window gap that moves the minimum (WP-1421 owns it).
- Ranking by leverage at all: Toby (2024) is why suggestions stay advisory.

## Tasks

- [ ] Bounded gain for a candidate on or near a bound, both sides, seeded
      candidates included; a test on the fluorapatite state above where
      extinction drops below the noise floor.
- [ ] `best_or_none` and ΔBIC: decide the gate, then make the summary, the
      method and its docstring say one thing.
- [ ] Update `examples/guides/next.py`'s assertions and
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
