# WP-1931 — the background order scan runs to its cap

Milestone: unscheduled · Status: 🔄 2026-11-03 — tasks 1, 7 and 8 done (PRs #871, #1368); the REML selector (tasks 2-6) is parked by the 2026-10-11 ruling
Track: What fires, and what stays silent
Depends on: — (1542 soft: the same `auto_background` call and its seed default)
Priority: P3 2026-10-08 — the selector returns its cap on both shipped 11-BM standards and says nothing; measured harmless there (bias ≤ 0.7 % of a background ≤ 0.4 % of the peak), so the cost is a choice that reads as made and was not

## Goal

`select_chebyshev_order` says when its scan ran to `max_order` instead of
stopping, and the co-refined P-spline's stiffness λ is chosen from the data
by a stated criterion (REML proposed), with the effective degrees of freedom
reported beside it.

## Context

Issue #833 (mustachefeeling, 2026-10-08).

**The selector** (`background/select.py:96`; line numbers re-read 2026-11-03). It fits Chebyshev orders 2 to
`max_order` on peak-masked channels (`peak_mask`, net ≤ 3σ over an arPLS
baseline) and keeps the BIC minimum, stopping early once the Durbin-Watson d
reaches `dw_stop` = 1.8. `auto_background(kind="chebyshev")` calls it with the
default `max_order` = 16 (`background/auto.py:155`). The P-spline branch never
calls a selector: it builds `BackgroundPSpline.for_range(…, lambda_smooth=1.0)`
(`auto.py:179`), λ weighed against the data at compile (root CLAUDE.md, the
background clause; WP-1454).

**What was measured** (#833, `main` at `a3f9140a`, macOS arm64):

| file | range | masked channels | `max_order` | selected | stopped by DW | d over the scan |
|---|---|---|---|---|---|---|
| `11BM_Si640c.xy` | 8-30° | 20 540 | 16 | 16 | no | 0.43-0.86 |
| `11BM_Si640c.xy` | 8-30° | 20 540 | 32 | 32 | no | 0.43-1.02 |
| `11BM_LaB6_660a.fxye` | 4-30° | 47 062 | 16 | 16 | no | 0.75-0.93 |
| `11BM_LaB6_660a.fxye` | 4-30° | 47 062 | 32 | 31 | no | 0.75-0.98 |

Two causes: the BIC gain per term (50-800) dwarfs the penalty ln m ≈ 10 at
20 000-47 000 channels, and the masked residual's serial correlation comes
from profile misfit, so d stays under 1.8 at any order. On these two
standards the choice is harmless: synthetic replicates from each converged
fit (4 per arm, Gaussian noise at the file's σ) give a background bias at the
12 strongest peaks of at most 0.7 % of a background that is itself at most
0.4 % of the peak, and |z| on scale, Biso, zero and cell of 0.4-1.1 at both
orders (Bérar-Lelann factor divided out). Where the choice does matter is
WP-1055's over-flexible fixture: Biso 0.958 / 0.000 against a true 0.5 while
every agreement index improved.

**Checked against the tree at `a3f9140a`** (this worktree's `[dev]` venv,
macOS arm64): the Si640c rows reproduce, `selected` 16 and 32 at
`max_order` 16 and 32, `stopped_by_whiteness` False both times, on 20 542
masked channels (the issue's 20 540; the probe's 8-30° crop was inclusive at
both ends). The LaB₆ rows were not re-run.

**The proposal** (#833):

1. `select_pspline_lambda(data, …)`: λ by REML on the penalised linear
   problem at the Le Bail stage, where the background competes only with free
   intensities. The second-difference penalty is the random-effects
   precision, so in the Gaussian linear case the criterion is exact and needs
   one eigendecomposition of the penalty in the data metric.
   `FitReport.background` carries tr(H), the effective degrees of freedom.
2. `select_chebyshev_order` emits `BACKGROUND_ORDER_AT_CAP` when it returns
   `max_order`.
3. `auto_background(seed=True)` as the default. That is #725's proposal, and
   WP-1542 owns it (its Inherited, 2026-10-05 and this triage's entry).

**Prior art.** Inside the field, GSAS, GSAS-II, TOPAS and FullProf all leave
the background order to the user. Outside it, a smooth nuisance curve is a
penalised spline with its smoothing parameter chosen by REML or marginal
likelihood (Wood 2011); Reiss & Ogden (2009) show REML under-smooths less
often than GCV (Craven & Wahba 1979, the classical fallback); the penalised
fit's Bayesian covariance has whole-curve coverage (Marra & Wood 2012).
**Licensing:** mgcv, the reference implementation of Wood's method, is
GPL, so this is built from the papers only.

**What a session must square first.** WP-1454 made λ a number weighed
against the data (√(λ·m)/σ̄, frozen at compile), and WP-1055 measures the
too-flexible side as `BACKGROUND_ABSORPTION`. A data-chosen λ changes what
every P-spline fit frees by default, so `FitReport.background`'s absorption
table on the acceptance suites is read before and after. Choosing λ at the Le
Bail stage and then holding it through the Rietveld stages is a protocol
claim the proposal makes and has not measured.

### The REML selector, parked (pruned from Inherited 2026-11-03)

The three entries below arrived as `### Inherited` and all still hold. The
second records the maintainer's ruling of 2026-10-11 (commit `24850ea95`):
tasks 2-6 wait for a criterion that does not read profile misfit as
background. Tasks 7 and 8 are outside that ruling.


- **2026-10-11, from the issue triage (#833): task 1 is in PR #871, and the
  reporter measured task 2, which undercuts the selector and this WP's
  acceptance.** PR #871 (open, 2026-10-10) adds `BACKGROUND_ORDER_AT_CAP`
  with its manual and skill rows. The reporter's comment of 2026-10-10 is a
  spike on `33fe516e`, no code proposed. They ran exact Gaussian REML (Wood
  2011 § 2 eq. 4) on the Le Bail stage's linear problem, checked against a
  dense evaluation on a 300-point synthetic. λ is `lambda_smooth` (default 1).
  - **Standards: interior, and reading misfit as background.** Si 640c and
    LaB₆ 660a at auto and 1° knots: REML λ 1.8e-5 to 1.3e-3, tr(H) at the
    coefficient count, φ̂ 1.3 and 3.1-3.3. Misfit-free replicates of the same
    problem give φ̂ 1.0 and λ 1.9e-3 to 2.1e-2: 6-350× above REML on the
    real data, and still 50-540× below the default.
  - **WP-1055's fixture: the right answer is the edge.** Its true background
    is flat, which is in the penalty's null space. At the generating profile
    REML runs to λ ≥ 2.6e12 and Biso lands at 0.688(194) and 0.685(964)
    against 0.5. With the profile fitted beside a 1° spline the Le Bail stage
    degenerates first (Rwp 0.21, five `BOUND_HIT`), and REML follows it to
    1.9e-4, where Biso B goes to −0.185 with `BACKGROUND_ABSORPTION`.
  - **This WP's acceptance cannot tell the arms apart.** "Interior" fails on
    the fixture exactly where REML is right. "Biso within 2 esd of 0.5" is met
    by λ = 0 too, since B's esd is 1.15. `worst_absorption` separates them,
    0.46 against 0.08.
  - Not measured: a Le Bail-stage λ carried through the Rietveld stages.

  Whether tasks 3-4 go ahead, and on which criterion, is the maintainer's
  call. Not reproduced here. Checked against the tree at 7d9be3cb:
  `select_pspline_lambda` does not exist under `src/`, and
  `BACKGROUND_ORDER_AT_CAP` exists only on PR #871's branch.

- **Decided 2026-10-11 (#833): the REML selector is parked.** Task 1
  (`BACKGROUND_ORDER_AT_CAP`, PR #871) goes ahead on its own. Tasks 3-4
  (`select_pspline_lambda` and its default) wait until a criterion exists that
  does not read profile misfit as background. The reporter's measurement above
  is the reason: on both standards REML makes the background more flexible
  than the default, which is the harm `BACKGROUND_ABSORPTION` guards. When the
  work resumes, the acceptance is rewritten around `worst_absorption`, the one
  measure that separated the arms (0.46 against 0.08). The maintainer also
  noted that λ is the package's wavelength symbol. So any new name, message or
  document for the smoothing strength must not be readable as a wavelength.
  `lambda_smooth` (WP-1454) is the existing case.

- 2026-10-31, from the issue triage (issue #833): a case for the parked
  selector's acceptance, with no profile misfit at all (reporter, 2026-10-29,
  synthetic, no code proposed). Two families come from rietx's own forward
  model, with the truth's profile equal to the model's. One is a cubic
  perovskite on a capillary with a 4-term Chebyshev background. The other is
  rutile in Bragg-Brentano with Kα1+Kα2. Each has 20 seeds.
  `auto_background(data, seed=True)` leaves an edge error of a few tenths of a
  percent of the background. It alternates in sign within the first 15° and
  returns at the top end. A truth-form Chebyshev control shows none. A
  coherent-residual scan (#1215) fires on 17/20 and 20/20 with the auto
  P-spline, and on 0/20 with the control. `AIR_SCATTER_UNDECLARED` fires on
  clean rutile on 20/20 with the P-spline and 0/20 with the control. The
  error's significance grows with counts (9.0σ to 25.5σ at 10× counts), while
  its size stays near +0.8 %. The reporter suggests that the selector's
  acceptance include the error in the first and last ~15° against a truth-form
  control, read with `worst_absorption`. No threshold is proposed. Checked
  against the tree at d87c8cc91: `auto_background` exists
  (`background/auto.py:92`) and the REML tasks are unticked. The figures were
  not re-run. They come from one source, the same forward model.

## Non-goals

- The seed default (#725, #833 item 3): WP-1542.
- A too-low background left at its seed under Le Bail: WP-1542.
- Changing the arPLS mask or `select_arpls_lambda`.

## Tasks

- [x] `BACKGROUND_ORDER_AT_CAP` from `select_chebyshev_order` (and through
      `auto_background(kind="chebyshev")`), naming the cap and the last d.
      Independently landable.
- [ ] *(Parked, ruling of 2026-10-11, tasks 2-6.)* Measure REML's λ on Si640c, LaB₆ 660a and WP-1055's fixture before
      building the selector: interior or not, tr(H), and Biso on the fixture.
- [ ] `select_pspline_lambda`, with its reference in the docstring, and the
      decision whether `auto_background` calls it by default (the
      maintainer's).
- [ ] tr(H) on `FitReport.background`.
- [ ] Tests, and the acceptance suites' `BACKGROUND_ABSORPTION` table before
      and after, with obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the new code's `references/judging.md` row; a SKILL.md line only
      if the default changes.
- [x] Score the order scan's BIC at the effective sample size of the masked
      residual, as `report.body_misfit` does for its ΔBIC, and measure where
      FAP.XRA and Si 640c then stop. *Measured 2026-11-03 and declined; the
      selector is unchanged (settled by Claude under the measurement below).*
      N_eff = m/f², with f the Bérar-Lelann factor of the masked weighted
      residual (`optimize.statistics.effective_sample_size`). Picked orders,
      at caps 16 / 32:

      | f taken from | FAP.XRA | Si 640c 8-30° | LaB₆ 660a 4-30° |
      |---|---|---|---|
      | raw m (today) | 16 / 32 | 16 / 32 | 16 / 31 |
      | the cap's residual, one N_eff for the scan | 15 / 15 | 15 / 32 | 14 / 17 |
      | each order's own residual | 2 / 2 | 4 / 4 | 14 / 17 |
      | the order-2 residual | 6 / 6 | 11 / 11 | 14 / 17 |
      | pairwise, order n's f, stop at the first loss | 6 / 6 | 2 / 2 | 5 / 5 |

      The principled reading is the second row: one N_eff for every candidate,
      as BIC needs, from the residual least shaped by the background. It moves
      16 to 15 and still returns the cap on Si 640c at 32 (m 20 542, f 3.60,
      N_eff 1589). Each term's gain at that N_eff alternates in sign (FAP:
      +158, +359, +39, +172, −5.6, +24, +5.9, −1.0, …), so the scan has no
      turning point to find. The other rows stop early for reasons that are
      not the noise. A low order's f carries the background shape the next
      terms remove (FAP's order-2 f is 19.5, N_eff 8), and the first-loss
      stop ends Si 640c at 2 because its 3rd term costs 4.5. So ESS scoring
      does not answer the cap, and `BACKGROUND_ORDER_AT_CAP` stays the
      honest report. Probe: `select_chebyshev_order`'s own masking and
      design, this branch's `[dev]` venv, macOS arm64.
- [x] `select_arpls_lambda` says when it falls back to the flexible end of its
      grid (no smoothing strength reached `dw_floor`), the cap code's sibling,
      unless PR #871 carries it. *Landed 2026-11-03 as
      `BACKGROUND_SMOOTHING_AT_FLEXIBLE_END` (info, on
      `BackgroundSelection.diagnostics` only); none of the 20 patterns under
      `tests/data` falls back.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_background_auto.py tests/test_auto_background_seed.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

The selected λ is interior on both standards and on WP-1055's fixture, whose
Biso lands within 2 esd of 0.5 at that λ. Replicate coverage on the two
standards does not move. `select_chebyshev_order` at its default on Si640c
emits `BACKGROUND_ORDER_AT_CAP`.

## References

- Issue #833; #725 (WP-1542).
- WP-1055 (`FitReport.background`, the over-flexible fixture), WP-1454 (λ
  against the data), WP-1309.
- Wood, S. N. (2011). *J. R. Statist. Soc.* B 73, 3-36,
  doi:10.1111/j.1467-9868.2010.00749.x.
- Reiss, P. T. & Ogden, R. T. (2009). *J. R. Statist. Soc.* B 71, 505-523,
  doi:10.1111/j.1467-9868.2008.00695.x.
- Marra, G. & Wood, S. N. (2012). *Scand. J. Statist.* 39, 53-74,
  doi:10.1111/j.1467-9469.2011.00760.x.
- Craven, P. & Wahba, G. (1979). *Numer. Math.* 31, 377-403.

## Handover log

- **2026-11-03** — PR #1368 (ghostshift runner). The order scan's
  remaining idea is now measured and refuted. Charging its BIC at the
  effective sample size, the way the package's other model comparisons do,
  still runs the Chebyshev scan to its cap on Si 640c at `max_order` 32, and
  moves FAP.XRA and Si 640c only from 16 to 15 at the default cap. The gain
  per added term alternates in sign, so there is no turning point for any
  penalty to find, and `BACKGROUND_ORDER_AT_CAP` stays the honest report.
  The arPLS baseline scan now says when it fell back to its grid's flexible
  end, the cap code's sibling. No shipped pattern falls back, and nothing a
  fit prints or returns changes. The REML selector stays parked under the
  2026-10-11 ruling.
  - *Done.* Task 7, measured and declined (table under the task; settled by
    Claude on the measurement, the selector unchanged). Task 8:
    `BACKGROUND_SMOOTHING_AT_FLEXIBLE_END` (info) on
    `BackgroundSelection.diagnostics` from `select_arpls_lambda`, naming the
    strength returned, with the largest d reached as `value`. Audit rows
    (code tier 1, response info, scope all; suggestion tier 1), help entry,
    skill row in `references/abstention.md` (all three copies), manual
    reference and theory lines, a 1.11.0 release note. The new code pushed the
    generated Refinement diagnostics page past the page contract's 50 000
    characters (50 609), so codes raised under `rietx/background/` now file on
    a new "Background selection" page (`reference/diagnostics-background.md`).
  - *Pruned.* The three `### Inherited` entries all still hold; they now sit
    in Context under "The REML selector, parked", and tasks 2-6 are marked
    parked. The triage brief that started this session said the REML selector
    remained; the WP's ruling of 2026-10-11 (commit `24850ea95`) parks it, so
    it was not built. Context's line numbers were re-read.
  - *Measured.* arPLS over the 20 patterns under `tests/data` (FAP.XRA, the
    three 11-BM files, the 16 `qarr` patterns): every scan meets its floor;
    FAP.XRA only at the last candidate, 1e4, d = 1.26. Task 7's table is
    under the task. Both probes: this branch's `[dev]` venv, macOS arm64,
    scripts outside the tree.
  - *Gates.* Fast selection on the final code tree (`2e6c63ff5`), this
    branch's `[dev]` venv, macOS arm64: 13616 passed, 319 skipped, 34
    xfailed, 0 failed, in 8.4 min of wall clock. The earlier run on
    `c6117b672` gave the same counts. The branch adds one test, and it
    passes: `test_an_arpls_scan_that_falls_back_says_so`, 0.16 s in that
    run's junit, nowhere near the slow tail. The full selection did not run,
    because nothing here moves a measured number. `tests.reader_output`
    exit 0, `test_docs_consistency.py` 25 passed, ruff clean. Main had moved
    42 commits and was not merged in; a trial merge is clean and main adds
    no diagnostic code.
  - *Review.* `/code-review high --fix` found no correctness bug. Three fixes
    taken in `0c5412472`: the floor's audit evidence now says it decides when the
    new code fires; `PatternDiagnostics.baseline_lambda`'s docstring says a
    fallback value is the grid's end and the code is not carried there; the test
    pins the default answer at 1e7. Three declined: the code row's tier (the
    judge's call, and it held); `BACKGROUND_ORDER_AT_CAP`'s anchor moving to the
    new page (the site's redirect stubs are per page and cannot carry an anchor);
    the `stopped`/`selected` redundancy in `select_arpls_lambda` (predates the
    branch, no behaviour change).
  - *Generality* (the `generality-review` judge on the branch at `c6117b672`, pasted unedited; the author's answer under the `fails`).

    #### `BACKGROUND_SMOOTHING_AT_FLEXIBLE_END` (code)

    **holds.** The case for the code is stronger. It reports which of the scan's two return lines produced the answer, and it changes nothing. The case against it is "none found".

    | Question | Author's answer (where) | What I found | Verdict |
    |---|---|---|---|
    | 1. What it decides | Row `evidence`, `_audit.py:558`: "fires exactly when no candidate of select_arpls_lambda's grid reached its Durbin-Watson floor … decides nothing" | Confirmed at `select.py:243-256`. The code is added only inside the existing `if selected is None:` branch. The returned value is unchanged, and the test pins `selected == 1e9`. What does decide is the fallback `selected = min(candidates)`, which predates this change. A fallback is one of the things the module docstring says the table cannot see, so it has no row of its own. The code makes that fallback visible. It adds no decision. | holds |
    | 2. Kind of ambiguity | `ambiguity=1` | Whether the fallback line ran is a fact about the code path. That is kind 1: no refiner can read it differently. | agrees |
    | 3. Case against acting | none given | none found. The code takes no action, and reporting a fallback is not something a refiner would do differently. One limit belongs to the threshold, not to this row. The message's "not looking white" means "d < 1.2". That floor `ARPLS_DW_FLOOR` is tier 3 with "no source for 1.2, no measurement recorded" (`_audit.py:1710-1718`, approved 2026-10-19). So the "not a choice" verdict is only as sound as 1.2. | n/a |
    | 4. Case for acting | Docstring, `select.py:211-217`: "a fallback, not a choice"; release note: "Nothing else moves" | Without the code, a caller holding `BackgroundSelection` cannot tell the grid's end from a choice except by reading `scores` and redoing the comparison. The cost of leaving it out is one extra reading step. No measurement is given, and none is needed for a report. The stakes are small. The only default path is `diagnose()` (`diagnostics.py:1592`), which keeps only `.selected` for `PatternDiagnostics.baseline_lambda`, and nothing in `src` reads that field (my grep agrees with the floor row's evidence). So no default path surfaces the code. The skill row says this ("on `select_arpls_lambda(...).diagnostics` only"). | holds |
    | 5. Tier and source | `tier=1`; grounds: "Arithmetic: the scan says which of its two return lines produced the answer" | Tier 1 fits a report of a code path. The statistic d is cited in the module docstring (Durbin & Watson 1950; Hill & Flack 1987), so it is tier 2. The floor is tier 3, tabled separately and approved. No program default applies: as far as I know none of the seven programs ships an arPLS strength scan, but that is recall and not checked in `docs/practice.md`, which has no background-estimator survey. | holds |
    | 6. Dataset families | Docstring and theory page: "None of the 20 patterns under `tests/data` (FAP.XRA, the three 11-BM files and the 16 `qarr` round-robin patterns) falls back; FAP.XRA comes nearest … 1e4, with d = 1.26" | By laboratory and instrument that is three families: a lab FAP scan, 11-BM synchrotron, and the qarr round robin. All three are development data. The table needs no threshold support for a tier-1 report. Silence is measured on real data. Firing is shown only on a synthetic hump with the grid cut to two candidates (`test_an_arpls_scan_that_falls_back_says_so`). No real pattern on disk makes it fire. FAP.XRA passes the floor at 1e4, which is the same strength the fallback would return. There, firing or silence turns on d = 1.26 against 1.2 while the returned value stays the same. That is the report working as intended. No probe environment or commit is recorded for the 20-pattern sweep: **none given** (task 7 states its probe; task 8 does not). | holds, with a gap |
    | 7. Record field | `response="info"`, `scope=("all",)` | `BackgroundSelection.diagnostics` carries it with `value` = the largest d. The raise site passes `level="info"` and no `where`, so `scope` is required and present. | holds |

    Evidence that would change the verdict: a default path that turns `select_arpls_lambda`'s strength into a held baseline while dropping `.diagnostics`. The report would then be silent exactly where it matters.

    #### `BACKGROUND_SMOOTHING_AT_FLEXIBLE_END.suggestion` (suggestion)

    **fails.** The case against the tier is stronger. The suggestion prescribes one of the package's two approved background forms over the other, so it is a judgement. The row tiers it as arithmetic. The rule it cites approves both forms, and the package's own skill names a situation where the other form is the advice.

    | Question | Author's answer (where) | What I found | Verdict |
    |---|---|---|---|
    | 1. What it decides | The text: "Co-refine the background rather than holding this baseline fixed (auto_background builds one)." | It steers the caller to a co-refined background, which by default means `auto_background`'s P-spline. It steers them away from holding an arPLS estimate additively. The package itself never builds a held baseline from this scan's result (grep: no caller turns `.selected` into `BackgroundFixedPlusChebyshev`), so the advice reaches only a caller who built one by hand. | — |
    | 2. Kind of ambiguity | `ambiguity=1` | Which response is right depends on the pattern. Is there a broad amorphous hump? Is there a measured blank? Is it a dense pattern whose peak tails sit under the 3σ mask cut and keep d low at every strength? Those are facts outside this scan, which makes it kind 3, or at best kind 2. | disagrees |
    | 3. Case against acting | Row `evidence`: "a baseline the data did not choose is no measured curve to hold fixed, which leaves the package's other form … (root CLAUDE.md, the weights clause)" | A named dissent exists inside the package. `docs/skill/rietx/references/judging.md:75` reads: "**Under a broad hump, hold SNIP.** … a co-refined one stops short and the reflections keep the rest" (measured on one synthetic fixture, WP-1542). That refiner holds an estimated baseline fixed on purpose. Other responses a competent refiner might make: pass a stiffer strength explicitly, since none is white and a stiffer one eats less peak; switch estimator; or hold a measured blank. The cited clause does not support the row. It reads: "Never subtract an estimated background — hold it additively (`BackgroundFixedPlusChebyshev`) or co-refine it under a smoothness penalty". It allows both forms. The argument "the data did not choose it" also fits an interior-chosen arPLS strength, which is no measured curve either. Practice (recall, not checked): GSAS-II and FullProf both let a user fix background points. | strong |
    | 4. Case for acting | `help.py` entry: "A baseline estimated this way and held fixed carries that misfit into the fit. Co-refine the background instead." | Plausible. The grid's most flexible end (1e4) is the strength most likely to follow peak tails, and a fixed curve cannot correct itself during the fit. But nothing is measured: **none given** for the claimed harm of holding it, and none for co-refining doing better. | weak |
    | 5. Tier and source | `tier=1`, no `grounds` | The table's own tier-1 suggestions name an override argument, defer the pick, or list remedies and pick none. Examples: `RESTRAINT_PAIRS_STALE` ("names the two remedies … and picks neither") and `PATTERN_NET_HAS_BACKGROUND` ("prescribes neither branch, so no dissenter is left"). A suggestion that names one remedy where the choice is the caller's is tiered 3 with grounds and approval, as `CELL_RUNAWAY.suggestion` is. This one picks one remedy and has no tier-2 source. As written it is tier 3 and needs `grounds` and `approved`. Rewording it to list the responses without ranking them would earn tier 1. | fails |
    | 6. Dataset families | none given | No pattern was shown on which holding the fallback baseline did harm, or on which co-refining did better. No real pattern on disk makes the code fire at all. | none given |
    | 7. Record field | — | `Diagnostic.suggestion` on the code above, on `BackgroundSelection.diagnostics` only. No default path shows it. | holds |

    Evidence that would change the verdict: either of two things. (a) The suggestion reworded to list the responses without ranking them: co-refine (`auto_background`), pass a stiffer strength, hold SNIP under a broad hump, or hold a measured blank. That earns tier 1, as `PATTERN_NET_HAS_BACKGROUND` does. (b) A measurement showing that a held fallback baseline biases a refined number where a co-refined background does not, with the SNIP-under-a-hump case shown not to arise. That would support the current wording at tier 3.

    *Author's answer:* taken as (a) in `243b7b86c`. The suggestion now reads "Pass a strength of your own, co-refine the background (auto_background), or hold a measured blank.", ranks none, and the row's evidence names the held-SNIP dissent; the help entry and skill row say the same. The 20-pattern sweep's probe is now stated under *Measured*.
  - *Gotchas.* The Refinement diagnostics page now renders at about 49 350
    characters of its 50 000 cap, so the next code raised in `refine.py`
    will fail `test_every_page_has_a_twin_that_keeps_the_contract` again.
    That page needs a split by something other than the raising file, since
    66 of its 74 codes come from `refine.py`.
  - *Next:* tasks 2-6 wait for a criterion that does not read profile misfit
    as background (the 2026-10-11 ruling). Nothing else remains here, so the
    WP is open only for that.

- **2026-10-12** — PR #871 merged from outside as `6010b3fa`. When the
  Chebyshev order scan stops only because it reached `max_order`, it now says
  so. `select_chebyshev_order` puts `BACKGROUND_ORDER_AT_CAP` on
  `BackgroundSelection.diagnostics`, naming the cap and the last
  Durbin-Watson d, and `auto_background(kind="chebyshev")` passes it on as a
  `UserWarning`. The agent who follows the skill's worked default meets it,
  since FAP.XRA returns 16 of 16. Issue #833 stays open for the P-spline
  selector.
  - *Done.* Task 1. `SCHEMA_VERSION` is 0.47, for the new
    `BackgroundSelection.diagnostics` field. `docs/manual/background.md` §
    "Choosing the flexibility" now states both scans' rules, calls their knob
    the smoothing strength (never λ), and says `auto_background` fixes the
    P-spline's at 1.0.
  - *Gated* on the same four-PR stack as WP-1322's entry of today (stack
    `0e4b7e25` on main `f22e9a7c`; main `f47c728e` content-identical after the
    merges).
  - *Gotchas.* The code's skill row is in `references/abstention.md`, as the
    review decided on 2026-10-11. Task 6 names `judging.md`, and still owes
    the REML selector's row. The row says to read `BACKGROUND_ABSORPTION` first,
    and to switch to `kind="pspline"` only if that fires. Three open PRs (#888,
    #903, #911) also claimed 0.47 and now take the next numbers.
  - *Next:* task 2, measuring REML's smoothing strength on Si640c, LaB₆ 660a
    and WP-1055's fixture.

- **2026-10-11** — PR #871 (task 1, `mustachefeeling`) reviewed and held for
  three items: a `SCHEMA_VERSION` bump for `BackgroundSelection.diagnostics`, a
  skill line for the worked default, and the stopping rule stated in the
  manual's "Choosing the flexibility" section. The worked default's FAP.XRA
  reaches the cap: 16 of 16, d = 0.721. The review keeps § 10 as it is and
  asks for a line in the abstention row. Measured on FAP.XRA in review (3179
  masked channels, ln m = 8.1): every term but the 7th earns 15 to 3166 against
  that penalty while d stays at 0.20-0.72. Scaled by m_eff/m, with d read as a
  lag-1 correlation, the 10th, 14th and 16th terms earn 7.3, 10.0 and 3.3.
  That is the case for the effective-sample-size task added above. The
  `select_arpls_lambda` task is the sibling the review found.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #833).
  Checked against the tree at `a3f9140a`: the Si640c rows reproduce (16 and
  32 selected at caps 16 and 32, never stopped by DW). No open WP owns the
  order or λ choice: 1454 and 1055 are closed, 1460 is about a declared air
  term beside the P-spline, 1542 owns the seed half (item 3, folded there).
