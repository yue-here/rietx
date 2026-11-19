# WP-2220 — A nested comparison says which fits it rests on, and which freed columns carried information

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (2076 soft: its extinction-screen nesting finding fences that caller out; 2053 soft: the same stationary-point t)
Priority: P2 2026-11-19 — a ΔBIC of the wrong sign is quoted beside a fit that stopped on its budget, and nothing on the comparison says so; a path few fits run

## Goal

`FreedComparison` (and the outcome of `predict_then_verify` and `rigid_body_misfit`) carries
how each of its two fits ended and whether the fuller fit's χ² sits at or below the restricted
one's. Each `FreedParameter` says whether it ended on a bound and why its t-ratio is absent.
A reader of the comparison alone can then tell a ΔBIC built on an unconverged or singular pair
from one built on two optimised fits.

## Context

Issues #1685 and #1686 (mustachefeeling, 2026-11-18), both on the comparison object WP-1417
built for #270. WP-1417 is closed (✅ 2026-09-27), so this is a new WP rather than a fold.

**What the comparison is.** `report.compare_freed(restricted, full)` takes two fits the caller
ran, a restricted one and one that frees more parameters. It returns ΔBIC charged at N_eff =
N/f² (f the restricted fit's `esd_inflation`), the same at raw N, and each freed parameter's
t = (value − held_at)/esd. There is deliberately no verdict field (`FreedComparison`'s
docstring, on `RivalComparison`'s precedent). Code at 7a4a6cd20:
`src/rietx/report/layer2.py:237` (`compare_freed`), `:277` (`_freed_comparison`; `n_added` at
`:309`, the t-ratios at `:349-352`, ΔBIC at `:358-364`); `src/rietx/report/schemas.py:1250`
(`FreedParameter`), `:1268` (`FreedComparison`), `:1472` (`VerificationOutcome`).

**#1685: neither fit's status is read.** A fuller fit that stopped on `max_iter` gives a ΔBIC
that can have either sign. A fuller nested fit whose χ² lands above the restricted one has not
reached its minimum, and nothing checks that either. Reproduced on 7a4a6cd20 (macOS arm64,
this worktree's venv) with the issue's own script, digit for digit:

| fuller fit | status | χ²_full − χ²_restricted | ΔBIC (N_eff) | La Biso t |
|---|---|---|---|---|
| run to convergence | `converged` | −447.1 | +269.1 | −19.1 |
| `max_iter=1`, Biso started at 4 | `max_iter` | +4374.9 | −1956.0 | +16.4 |

The result knows (`status='max_iter'`, `STAGE_MAX_ITER`), the comparison does not. Status alone
is not the whole test. The LM driver calls a slow-descent stop `converged` (`optimize/lm.py`,
#222), and a budget stop can land on the optimum (the reporter's `max_iter=2` from Biso = 8
stops at the converged χ², 5410.1). So the reporter proposes recording both statuses and a
χ² ordering flag, and flagging without refusing. Precedent for the ordering test:
`report/distortion.py:462-470` restarts when the restricted χ² sits below the full one.

**#1686: a freed column with no information is charged and not named.** A freed block whose
leading parameter ends on its zero bound leaves the others with zero columns: `esd=None`,
`t_ratio=None`, no reason. When the leading parameter ends just off its bound, a position can
end on its own bound with a large t that is no Wald number. Reproduced on 7a4a6cd20 with the
issue's script (a `PeakComponent` declared at area 0 over a pattern with no extra peak, area,
centre and fwhm freed):

| seed | χ²_full vs χ²_restricted | ΔBIC | centre | area | fwhm | full fit's own codes |
|---|---|---|---|---|---|---|
| 1 | equal to the last digit | −25.06 (= −3 ln N_eff) | esd None, t None | t 0.0 | esd None, t None | `EXTRA_PEAK_NO_INTENSITY`, `FLOOR_HIT` |
| 7 | −4.9 | −21.28 | 46.5 on its upper bound, t +8.5 | t 1.6 | t 0.34 | `BOUND_HIT` |

The ΔBIC errs on the safe side (nominal k over-charges), so the verdict is not wrong. What is
missing is what the reader is told.

**Authorities to read, never re-derive.** `RefinedParameter.at_bound` is a projection of
`staged.bound_findings` (CLAUDE.md, WP-1076/1434/1929), so a `FreedParameter.at_bound` reads
the fuller fit's row and stays set-equal to it. A zero column's absence of esd comes from
`statistics.normal_covariance` dropping it (`ParameterTable.unmeasured_rows`); WP-2219 (⬜)
moves which parameters lose their esd, so a `t_reason` here quotes whichever authority marks
the row. A new diagnostic code takes its `_audit` row, its `help.py` entry and its skill row.

**Three other ΔBIC callers compare two refits** (#1685's list, checked at 7a4a6cd20):
`predict_then_verify` (`layer2.py:1136`; accepts on a > 1 % χ² gain at `:1183` and attaches
`_freed_comparison`); `rigid_body_misfit` (`report/body_misfit.py:395-438`; Hamilton and ΔBIC
from both arms, no status read); the extinction screen (`indexing/extinction.py:1520-1528`).
The first two are this WP's. The extinction screen is fenced below.

**This changes what a fit returns.** The new fields and any new code are reader output, so they
go to the maintainer before merge (the maintainer's standing rule). Their names sit on `rietx.report`'s
public surface.

## Non-goals

- **The extinction screen.** WP-2076 measured that its class fit sits below the absence-free
  reference on every certified row (corundum, FAP, PbSO₄, Si: class χ² below reference χ²), so
  an ordering flag copied there would fire on every answer the suite certifies. Its ordering
  question is WP-2076's. A pointer is in that WP's Inherited.
- Refusing a comparison. Both issues propose flagging only, since a budget stop can sit on the
  optimum.
- Charging ΔBIC at the identified count. `n_identified` sits beside `n_added`; `delta_bic` stays
  charged at `n_added`.

## Tasks

- [ ] `FreedComparison` records both fits' `status` and a χ² ordering flag (full ≤ restricted
      within the solver's ftol). Pin both rows of #1685's table.
- [ ] A diagnostic on the comparison when either fit is not `converged` or the ordering fails,
      with its `_audit` row (tier: named practice for the ordering, since a nested optimum
      cannot rise), `help.py` and skill rows.
- [ ] `FreedParameter.at_bound`, projected from the fuller fit's `RefinedParameter.at_bound`
      and pinned set-equal; a reason string where `t_ratio` is `None`. Pin both seeds of
      #1686's table.
- [ ] `n_identified` beside `n_added`: freed columns that are live and off their bounds.
- [ ] `predict_then_verify` and `rigid_body_misfit` take the same fields. A trial that stopped
      on its budget reads as not judged, never as a rejection (#1685 proposal 3).
- [ ] Tests (unit, on the two synthetic scripts from the issues) + obs/calc/diff PNGs to
      `tests/output/`
- [ ] Skill: the `compare_freed` reference row says to read the status and ordering fields
      before quoting a ΔBIC.

## Acceptance

Both issues' scripts print the new fields: the `max_iter` arm says it is unconverged and
unordered, seed 1 says two of three freed columns carry no information, seed 7 marks the centre
at its bound. Every existing `compare_freed` number is unchanged.

```sh
.venv/bin/python -m pytest tests/test_compare_freed.py tests/test_body_misfit.py -q
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Schwarz, G. (1978). Estimating the dimension of a model. *Ann. Stat.* **6**, 461-464.
- Hamilton, W. C. (1965). Significance tests on the crystallographic R factor. *Acta Cryst.*
  **18**, 502-510.
- Issues #1685, #1686; related #270 (WP-1417), #222, #538, #831, #1008, #1010 (WP-2053).

## Handover log

- **2026-11-19** — created, from the 2026-11-19 issue triage (issues #1685, #1686). A reader of
  a ΔBIC comparison cannot yet tell when it rests on a fit that never finished, or when it
  charges parameters that carried no information. Checked against the tree at 7a4a6cd20: both
  issues' scripts reproduce digit for digit on macOS arm64; `_freed_comparison` reads no
  `status`, and `FreedParameter` has no `at_bound` or reason field. No open WP owns it: WP-1417
  built the object and is closed; WP-1998 and WP-2115 own the suggestion score, not the
  comparison; WP-2076 owns the extinction screen's nesting and is fenced out above. Combined
  because both edit the same two schema classes and one builder, with the same fixture style.
  Next: task 1.
