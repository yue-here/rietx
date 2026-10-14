# WP-1931 — the background order scan runs to its cap

Milestone: unscheduled · Status: 🔄 2026-10-12 — task 1 landed from outside (PR #871); the REML selector and the rest remain
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

**The selector** (`background/select.py:75`). It fits Chebyshev orders 2 to
`max_order` on peak-masked channels (`peak_mask`, net ≤ 3σ over an arPLS
baseline) and keeps the BIC minimum, stopping early once the Durbin-Watson d
reaches `dw_stop` = 1.8. `auto_background(kind="chebyshev")` calls it with the
default `max_order` = 16 (`background/auto.py:87`). The P-spline branch never
calls a selector: it builds `BackgroundPSpline.for_range(…, lambda_smooth=1.0)`
(`auto.py:106`), λ weighed against the data at compile (root CLAUDE.md, the
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

### Inherited

- **2026-10-14, from WP-1963's filing: a candidate for the criterion the
  selector waits on.** The resume condition below asks for a criterion that
  does not read profile misfit as background. WP-1963 scopes one taken from the
  instrument instead of the data (`docs/solver-survey.md` §C10): place the
  knots a fixed number of peak FWHMs apart, or uniformly in Q, so that the
  background's stiffness follows the peak width. It judges by this WP's
  `worst_absorption` measure. It is not a fold, because it changes where the
  knots go, not how the smoothing strength is chosen. One fact from the
  filing that bears on this WP: at the default strength, the P-spline's
  equivalent kernel is about three knot spacings wide (23.5° at 8° knots,
  tr(H) 3.61; 9.1° at 3° knots, tr(H) 6.88; 2-50° at 0.001°, uniform σ).

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

## Non-goals

- The seed default (#725, #833 item 3): WP-1542.
- A too-low background left at its seed under Le Bail: WP-1542.
- Changing the arPLS mask or `select_arpls_lambda`.

## Tasks

- [x] `BACKGROUND_ORDER_AT_CAP` from `select_chebyshev_order` (and through
      `auto_background(kind="chebyshev")`), naming the cap and the last d.
      Independently landable.
- [ ] Measure REML's λ on Si640c, LaB₆ 660a and WP-1055's fixture before
      building the selector: interior or not, tr(H), and Biso on the fixture.
- [ ] `select_pspline_lambda`, with its reference in the docstring, and the
      decision whether `auto_background` calls it by default (the
      maintainer's).
- [ ] tr(H) on `FitReport.background`.
- [ ] Tests, and the acceptance suites' `BACKGROUND_ABSORPTION` table before
      and after, with obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the new code's `references/judging.md` row; a SKILL.md line only
      if the default changes.
- [ ] Score the order scan's BIC at the effective sample size of the masked
      residual, as `report.body_misfit` does for its ΔBIC, and measure where
      FAP.XRA and Si 640c then stop.
- [ ] `select_arpls_lambda` says when it falls back to the flexible end of its
      grid (no smoothing strength reached `dw_floor`), the cap code's sibling,
      unless PR #871 carries it.

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
