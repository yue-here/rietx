# WP-1998 — A suggestion whose gain lies past its bound

Milestone: unscheduled · Status: ✅ 2026-11-03 — suggest scores the gain a candidate's bounds let it reach; best_or_none abstains where ΔBIC refuses (PR #1383; open questions in #1392)
Track: What fires, and what stays silent
Depends on: —

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
  Parker 1995). No threshold, no default. The box is the one a stage would
  solve in: `ParameterTable.bounds()` after the probe freezes the same
  per-stage windows `run_least_squares` does (cell window, strain and size
  caps), so stored bounds, tie windows and the caps all count.
- **`best_or_none` abstains when the leader's ΔBIC ≤ 0** — statistic tier 2
  (Schwarz 1978, the package's one BIC form) charged at N_eff = N/f², which
  is tier 3 and already rietx's (#270), and *predicted* from the linearised
  gain rather than refitted; threshold 0 tier 1 (the sign
  the criterion defines), action: *abstain*, the conservative direction —
  `None` names nothing, and the groups stay for a caller who reads them.

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

- [x] Bounded gain for a candidate on or near a bound, both sides, seeded
      candidates included; a test on the fluorapatite state above where
      extinction drops below the noise floor.
- [x] `best_or_none` and ΔBIC: decide the gate, then make the summary, the
      method and its docstring say one thing.
- [x] Update `examples/guides/next.py`'s assertions and
      `docs/docs/guides/next.md`'s sentence on `best_or_none` if either moves.
- [x] Skill: the row on reading `suggest`, or "none" and why. **None**
      (2026-11-03): the trap this WP found — a bounded candidate scored as if
      free — is fixed in the package, and the one ΔBIC reading a caller needs
      is now in `best_or_none` and the summary itself; a skill row is API
      vocabulary or a trap sourced outside rietx's own runs, and this is
      neither. The API index (`references/api.md`, three copies) is
      regenerated for `SuggestionResult.bound_limited`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest.py tests/test_examples.py -n auto --dist loadgroup
```

## Handover log

- **2026-11-03** — `suggest` no longer recommends a parameter its bounds
  will not let move. A candidate is scored by the drop in χ² it can reach
  inside the box a stage would solve it in, so a parameter on its floor with
  the data pushing it through scores zero and is listed separately as held
  back by a bound. `best_or_none()` now abstains when the same result's ΔBIC
  refuses the top group, and the summary says that parameter *leads* rather
  than that it is next. On the fluorapatite guide the narrowed query no longer
  names extinction, and nothing is named. Four questions the review raised
  are left in #1392, with no wrong answer in any case tested. PR #1383.

  *Done.* `strategy/suggest.py`: `_bounded_single` (exact α(2−α) on the
  projected quadratic), `_bounded_group` (BVLS when the min-norm joint step
  leaves the box, `min(gain, reach)`), `Candidate.value/lo/hi`;
  `refine.py`'s `suggest` reads `x0()`/`bounds()` after seeding and after
  freezing the cell window and strain/size caps as `run_least_squares` does
  (the review's finding 1); `_next_parameter_line` counts the held-back ones.
  New fields `ParameterCandidate.gain_unbounded` (writer `build_suggestion`)
  and `SuggestionResult.bound_limited`. `best_or_none` gates on the leader's
  `delta_bic > 0` and does not promote a lower group. Guide `next.md` and its
  script, `reference/comparison.md`, the theory page (the α(2−α) rule inline, the page being at its
  50 000-character cap), the
  skill's `api.md` (three copies). No skill row (task 4 says why).
  The truth-fixture tests moved where the physics did: with W or X injected
  too broad, every sample width on its floor of 0 is now bound-held, so the
  X ↔ lor_size identity tie is asserted with X injected too *narrow* instead,
  and a new test asserts the too-broad case resolves to X.

  *Measured* (`[dev]`, darwin/arm64, origin/main 99fe3f149 merged in): fast
  selection 13766 passed, 318 skipped, 34 xfailed in 11:39, alone under
  ghostshift's serial lock; the branch adds 13 cases to `test_suggest.py`
  (10 functions, one a rename), 0.54 s together, slowest 0.26 s. Full
  selection not run: the change moves no fitted number, only `suggest`'s
  predictions. `python -m tests.reader_output` exit 0, unchanged against the
  merge-base; the new fields are a reader change all the same (PR body).
  The cap test fails with the strain-cap freeze removed (checked once).

  *Review.* `/code-review high --fix`: 8 findings; 3 taken (stage box on the
  probe, the `next:` line, one shared projection). Declined into #1392: the
  projected-step vs unprojected-`gradient` sign (would change what
  `gradient` means), a bounded group charged k = all members, the group
  shortcut's min-norm columns vs the absorbed ones; not taken: shared QR
  (signature change outside the diff), two dead guards.

  *Generality* (judge, verbatim verdicts): `best_or_none` abstains when the
  leader's ΔBIC ≤ 0 — **holds** ("the case for this abstention is
  stronger"; tier: statistic 2 with N_eff at tier 3, threshold 1 — taken
  into the tier line). Bounded gain and `bound_limited` — **holds, with one
  wording fix** (the box was not the stage's own; fixed in code, not only in
  words). Summary "leads" — **holds**. Families: fluorapatite tutorial plus
  synthetic; no tier-3 number added.

  *Next:* Yue's ruling on the PR, then #1392's four items, of which (2), the
  ΔBIC count of a bound-pinned member, is a ruling rather than a patch.

- **2026-10-17** — filed from WP-1986's guide work. No open WP owns
  `suggest`: WP-1050 built it and is closed, and WP-1434's bound test is about
  results, not candidates.

- **2026-11-06** — Review round (Yue, 2026-11-05). The milestone narrative moved
  from `docs/milestones/v1.11.md` to `v1.12.md`, since 1.11.0 is cut and
  `pyproject.version` is `1.12.0.dev0`. `docs/releases/1.12.0.md` now names the
  `best_or_none()` change under § Code to check, the meaning of
  `ParameterCandidate.gain`, and the two new fields. `schemas/common.py` carries
  an `Also in 0.61 (WP-1998)` note and the pin's comment in
  `tests/test_magnetic.py` lists it; the number stays 0.61. No code changed.

