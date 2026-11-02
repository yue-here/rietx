# WP-1339 — where the improvement lives

Milestone: unscheduled · Status: ✅ 2026-11-02 — closed; the NiO acceptance stays external, the skill row is in numbers.md (PR #1325)
Track: Render what the fit already knows
Depends on: —

## Goal

The localisation statistic `rietx compare` already computes is reachable as a
library function over **two results on the same pattern**, and a symmetry-aware
wrapper asks the question a global statistic cannot: does the improvement land
where the added degree of freedom says it must?

## Context

`viz/compare.py` already contains the statistic that settles whether a
symmetry-lowering is real, and states the principle exactly:

> **A correction that improves Rwp by rising sharply somewhere and falling
> elsewhere is absorbing something, not modelling it.**

It is reachable only through `rietx compare` — a browser UI over **bundled
standards × predefined variants** (`run(standard_key, variant_key)`,
`catalog()`, standards hard-coded in `_build_srm660c` / `_build_fap` /
`_build_nac` / `_build_lab6_capillary`, variants as `_with_*` functions).
And there is less to lift than "the statistic" suggests: per variant the
cumulative is one line inside `run` (`cumulative = np.cumsum(delta ** 2)`,
stored as `RunRecord.cumulative_chi2`), and the **difference against the
reference** — the panel — is computed in the browser, in the JavaScript
embedded in `compare_app.py`. There is no function taking two results on the
same pattern and returning where their Δχ² lives; one has to be written, and
then both the record and the page consume it. So for the case the principle
was written for — a user's own two candidate space groups on their own data —
the analysis has to be rebuilt by hand.

**Issue #219 rebuilt it by hand, and it reversed the answer.** A laboratory
Cu-Kα pattern of commercial NiO, 6495 points. Cubic `F m -3 m` against
rhombohedral `R -3 m:R`, nested (α → 60° recovers cubic), both fits given
identical treatment — same background, same U/V/W/X/Y, same Biso, same
microstrain — differing only in the symmetry and its one extra degree of
freedom:

| | Rwp % | P | χ² |
|---|---|---|---|
| cubic `F m -3 m` | 5.7490 | 18 | 28816.06 |
| rhombohedral `R -3 m:R` | **5.6445** | 19 | 27778.16 |

ΔBIC(rhombo − cubic) = **−1029.1**. Nested F(1, 6476) = **241.97**,
p = **1.35×10⁻⁵³**. On every global statistic the symmetry-lowering is
overwhelming, and the refined value carries a tight esd: α = **59.9504(30)°**.

**It is wrong anyway, for two reasons no global statistic can see.**

1. **Wrong sign.** NiO contracts along cubic ⟨111⟩ below T_N ≈ 523 K
   (Rooksby 1948), so in the primitive rhombohedral setting α must be
   **greater** than 60°. The refinement gives −0.0496° from 60°. Magnitudes
   for reference: Bartel & Morosin (1971) put saturation at ~4.5 arcmin
   (0.075°); Pomjakushin (arXiv:2509.11715) gives δ_R ≈ +1.9×10⁻³ at 2 K. The
   fit found a distortion of plausible size and the **opposite sense**.
2. **Wrong place, and this is the part the package can check.** The predicted
   splitting is resolvable — it grows from ~48 % to ~104 % of the local
   instrument FWHM across the pattern — but the Δχ² improvement is wildly
   non-monotonic in 2θ, and **the single largest-magnitude decile (75–86°) is
   where the *cubic* model fits better**, while containing the two
   largest-multiplicity predicted split families. Windowing the six
   largest-multiplicity split families (6.2 % of points) captures **−28 % of
   the total Δχ²**: net *negative* precisely where a real rhombohedral
   distortion must concentrate its advantage. The plots show a shared,
   near-identical peak-shape defect driving that region in **both** models —
   the extra degree of freedom is absorbing it, not modelling a symmetry break.

Controls, each able to fail: freeing the zero shift alone recovers only **37 %**
of α's χ² improvement, freeing sample displacement alone only **10 %**, so it
is not a positional systematic either. No diagnostic fired on any of it; the
ones that did fire were a deliberate `lor_strain` floor (`BOUND_HIT`) and
generic symmetric TCHZ degeneracies (`HIGH_CORRELATION` on `lor_size`/
`profile.x` and `lor_strain`/`profile.y`).

**How close this came to going the other way** is the argument for the WP: two
independent agents fitted the same file and reached **opposite** conclusions —
"rhombohedral decisively favoured, ΔBIC −5553" and "the data do not
discriminate". Both were wrong. The first had a cubic baseline 1.1 pp worse
than achievable, so its extra symmetry absorbed the difference; the second
computed its information criterion on a quantity that was not a χ². The
localisation test is what settled it, and it settled it **against** the
statistically overwhelming answer.

This is also the package's own standing rule one rank up: **a new correction
ships with a record field or a diagnostic stating what it changed, never an
Rwp comparison as its evidence** (root CLAUDE.md). #219 is that rule applied
to a *user's* model choice rather than to a package correction, and the
machinery for it already exists in one place with the wrong reach.

**Three asks, in increasing novelty.** (1) is close to a refactor and the
contributor has offered a PR for it alone; (2) is the genuinely new part; (3)
is a design call to take rather than accept.

1. `cumulative_delta_chi2(result_a, result_b)` returning the cumulative
   Σ_{2θ′ ≤ 2θ}(δ²_b − δ²_a) against 2θ for two results on the same pattern,
   plus its decile/quantile breakdown. No UI, no bundled standards, no
   predefined variants.
2. A **symmetry-aware wrapper**: given two nested candidate models, enumerate
   the reflection families the lower-symmetry model **splits**, window the
   pattern to them, and report what fraction of the total Δχ² lands there
   against what fraction of the points they cover. The verdict is then
   mechanical — an improvement concentrated on the split families supports the
   distortion; one flat across the pattern, or **negative on the split
   families**, is absorption.
3. A **diagnostic when the two disagree**: the global statistic prefers the
   richer model while the improvement is anti-localised with respect to the
   degree of freedom that model adds. This is a different failure from what is
   covered — `BACKGROUND_ABSORPTION` asks whether the background can reproduce
   a phase's scale, and the identifiability machinery works at a converged
   point in parameter space. This one is about **where in the data** an
   improvement lives relative to where its physics says it must.

**Decided 2026-09-03 by the maintainer**: asks (1) and (2) together, the NiO
case as acceptance (the pattern to be obtained with permission — the task
below), and (3) as **report-only output** — a number the reader judges, not
a `Diagnostic`, because a diagnostic needs a threshold and the package
reports evidence rather than verdicts. The contributor's PR offer for (1)
and (2) is accepted.

**Closed out 2026-10-16** (issue triage, batch approved by the maintainer):
#219 closed with ask (3) done as report-only, citing PR #928's measurement
(the real parent held in 0 of 15 split starts). The two-phase ridge that the
thread raised belongs to WP-1523, which owns the support hold. Its numbers
are in that WP, and this one's localisation does not answer it: coexistence
"is not what this measures", by the docstring of `report/localisation.py`.

## Non-goals

- Deciding the space group. The package's standing rule holds:
  `determine_extinction_symbol` returns ranked classes, never a confident
  singleton, and this WP adds evidence rather than a verdict.
- `rietx compare`'s standards and variants registry, and its UI. Adding a row
  there when a correction lands stays a separate obligation (root CLAUDE.md).
- The NiO physics. The dataset is an acceptance case, not a claim about NiO.

## Tasks

- [x] Write the library function over two results on one pattern (the
      cumulative Σ(δ²_b − δ²_a) and its quantile breakdown); `run` and the
      page's JavaScript both consume it, so there is one authority and the UI
      is a consumer.
- [x] The NiO pattern: obtain it from the contributor with permission to ship
      it under `tests/data/` and a provenance row in `tests/data/README.md`
      (data carries its own fence, per file — root CLAUDE.md § Licensing), or
      build the acceptance on a constructed nested pair and keep NiO as an
      external check quoted from the issue.
- [x] The split-family enumerator and the windowed Δχ² share, for two nested
      models.
- [x] The disagreement case as report-only output (decided 2026-09-03: a
      number the reader judges, never a `Diagnostic` with a threshold); write
      the reason where the number lives.
- [x] Acceptance on the NiO pair: the localisation test must return the
      negative share (~−28 % on 6.2 % of points) that reversed the answer, and
      the check must be able to fail — a genuinely localised improvement on a
      constructed case must score positive.
      *Closed 2026-11-02 by task 2's second branch; settled by Claude under the
      Acceptance's own clause ("the NiO pair, if it ships") and the
      unpublished-data rule (root CLAUDE.md § Licensing).* The pattern never
      reached the thread, #219 closed on 2026-10-16 without it, and a
      contributor's unpublished laboratory pattern has no peer-reviewed
      citation to ship under. The constructed pair in
      `tests/test_localisation.py` scores positive (+68 %) and negative
      (−30 %), so the check can fail both ways; NiO stays an external check
      quoted from #219.
- [x] Tests: `tests/test_compare_ui.py` keeps asserting the UI field by field;
      the new function is tested on results, not on the UI's standards.
- [x] Skill: `references/judging.md` — the routing row for "two candidate
      space groups, which one", pointing at the localisation share and saying
      plainly that ΔBIC and a nested F-test do not settle it.
      *The row stays in `references/numbers.md`; settled by Claude under
      CONTRIBUTING.md § The agent skill.* `judging.md` holds the measurements
      behind the judging rules and is 26 B under its budget. The comparison is
      reached by the body's §5 routing row ("quoting or comparing a number"),
      so a new shape file is not warranted. 2026-11-02 added the nested F-test
      and the pointer to `judging.md` § adding a parameter that WP-1417 asked for.
- [x] The two follow-ups from #904's review (added 2026-11-02 from the
      2026-10-12 entry's *Not done*): `SplitFamily.emission_line` has no
      default, since its one writer always sets it; and a family whose parent
      lies just past an end of the range is reported when a child lies inside,
      its split read off every child.

## Acceptance

A constructed nested pair with a genuinely localised improvement scores
positive and an absorbed one scores negative; the NiO pair, if it ships,
reproduces the measured decile breakdown and the −28 % split-family share.
The pattern is not in the repo today.

```sh
.venv/bin/python -m pytest tests/test_compare_ui.py -q   # plus the new function's own module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #219 (NiO, laboratory Cu-Kα, 6495 points; the contributor offers a PR
  for ask 1, or 1 and 2 with the NiO case as acceptance).
- Rooksby (1948) — the ⟨111⟩ contraction below T_N ≈ 523 K, which fixes the
  sign. Bartel & Morosin (1971), *Phys. Rev. B* — saturation ~4.5 arcmin.
  Pomjakushin, arXiv:2509.11715 — δ_R ≈ +1.9×10⁻³ at 2 K.
- Search the local paper corpus before requesting any of these.

## Handover log

- **2026-11-02** — WP-1339 closes (ghostshift runner, PR #1325). The two
  functions PR #904 added now report the reflections that straddle an end of
  the fitted range, instead of losing the in-range half. An agent comparing
  two candidate space groups is told plainly that ΔBIC and a nested F-test
  say a lowering paid for itself and not where, so neither settles it. The
  NiO acceptance does not ship. The pattern never reached the thread, and a
  contributor's unpublished laboratory pattern cannot enter the public tree,
  so the constructed Cu pair remains the acceptance and NiO an external check.
  - *Done.* Inherited pruned: the 2026-10-16 close of #219 is folded into
    Context; the ridge entries (2026-09-23, 2026-10-04/11/13, WP-1469) belong
    to WP-1523, which owns the hold, and #904 shipped the 2026-09-23 note's
    sentence fix. WP-1417's note is folded into task 7. WP-1461's described a
    page task 1 already rewired. WP-1434's qualified #219's list of codes that
    fired, which nothing here builds on. Task 5 closed by task 2's second branch; task 7's row stays
    in `references/numbers.md`, now naming the F-test and pointing at
    `judging.md` § adding a parameter. Both settlements are marked in the
    task lines. The two #904 review follow-ups: `SplitFamily.emission_line`
    has no default; a parent just past the range is reported when a child is
    inside, `splits` reads every child, and a window anchors on the in-range
    children, else on the parent. The 1.8.0 release-notes gap had already
    closed (`docs/releases/1.8.0.md:307`).
  - *Review.* `/code-review high --fix` found six. Fixed: a parent in range
    with every child past the end was windowed wholly off the data (zero
    channels, still counted split), now anchored on the parent; the window
    and `n_unmatched` wording; the duplicated in-range predicate, now one
    helper. Declined: the borrowed median width of an out-of-range parent is
    a fallback in a line this branch did not change; removing the
    `emission_line` default breaks a constructor call that omits it (a
    model_dump always wrote the field), which the WP-1076 rule asks for.
  - *Measured.* Fast selection on this branch with main merged
    (unchanged, `f8559dee6`), `[dev]` venv, darwin/arm64, another session's
    pytest running beside it: 1 failed, 13 297 passed, 310 skipped,
    32 xfailed in 23:23. The failure is
    `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`,
    environmental: the user-level Jupyter kernel spec points at a deleted
    venv. The three added tests cost 0.01 s together (local junit). The
    test the generality review asked for came after that run and is an
    edit to one of the three, not a new test (localisation, skill and
    skill-copy files: 240 passed). Each new rule was failed on purpose once
    and its test went red.
  - *Generality.* `generality-review` held all four items: the window anchor
    (tier 1, arithmetic), the straddling family and its `splits` (tier 1;
    case against weak: an edge family with one child in range shows a
    shifted peak rather than a visible split, unmeasured on real data),
    `n_unmatched` in range only (tier 1; it asked for a test, added), and
    the skill row (passes Rule 4; it asked that "judging.md §4" name its
    section, since two headings start "§4", done). Its would-change: a real
    pattern with a family at a range end where the label carries a large
    share of `split_share`.
  - *Reader-output change* (for the maintainer): `split_localisation` can
    now return one more family per range end and line, a `splits` verdict
    that changed for a family with a child past the range, and a different
    window there. `SplitFamily(...)` without `emission_line` now raises. No
    printed fit or report changes (`split_localisation` is called by hand).
  - *Next:* none in this WP. Issue #219 is closed.

- **2026-10-12** — PR #904 merged from outside as `9669796d`. Two fits of one
  pattern can now say *where* the richer one gained, which ΔBIC cannot.
  `report.cumulative_delta_chi2` gives the running Σ(δ²_b − δ²_a) and its
  equal-count quantiles. `report.split_localisation(higher, lower)` shares the
  Δχ² among the windows of the reflections a symmetry-lowering splits, those it
  leaves whole, and the rest. A genuine distortion puts its gain on the split
  reflections, and an absorbed one does not. Issue #219 stays open for ask (3).
  - *Done.* Tasks 1, 3, 4 and 6, and task 2 by its second branch. The
    acceptance rests on a constructed nested pair in `tests/test_localisation.py`:
    a tetragonal Cu specimen gives ΔBIC +190 at N/f² and +68 % of the gain on
    3.2 % of the points, and a cubic one with a reflection-dependent shift
    gives ΔBIC +25 and −30 % on 4.9 %. `viz.compare.run` stores
    `report.cumulative_chi2`, so the page and the report share one authority.
    `THRESHOLDS_VERSION` is 1.12.
  - *Gated* on the same four-PR stack as WP-1322's entry of today (stack
    `0e4b7e25` on main `f22e9a7c`; main `f47c728e` content-identical after the
    merges).
  - *Gotchas.*
    - Children match parents **within one emission line**. A tick's line is
      its rank among the ticks sharing its `tick_hkl`, since `ticks` carries no
      line index. A line whose image falls off the axis for one reflection
      shifts that reflection's later ranks, and the docstring says so.
    - Coincident parents (333 and 511) are one `SplitFamily` carrying `hkls`.
    - Both functions refuse two fits whose `sig()` differ, since a measured
      background widens σ at compile (WP-1309).
    - No #219 value is in the tree. The pattern is not cleared to ship, so
      the manual and the skill quote the synthetic pair and cite #219 by
      number.
  - *Not done.*
    - Task 5, the NiO acceptance, waits on the pattern.
    - Task 7's row is in `references/numbers.md`, tagged `(Measured: …)`,
      because `judging.md` sat 41 B under its budget. Whether that placement
      discharges the task is the maintainer's call.
    - Two follow-ups from the review: `SplitFamily.emission_line` defaults to
      0, and a child whose nearest parent lies just outside the fitted range is
      counted nowhere.
    - `docs/releases/1.8.0.md` has no line for the two functions.
  - *Next:* decide task 7's placement. Task 5 waits on the NiO pattern.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #219).
  Re-checked the same day against the tree: there is no function to lift —
  the cumulative is one line in `run` and the difference is browser
  JavaScript; the NiO pattern is not in the repo, so acceptance rests on a
  constructed pair. Decisions recorded the same day: scope is (1) and (2)
  with NiO as acceptance, (3) is report-only.
