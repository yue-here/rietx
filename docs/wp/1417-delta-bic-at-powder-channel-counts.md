# WP-1417 — ΔBIC at powder channel counts

Milestone: unscheduled · Status: ✅ 2026-09-27 — all five tasks landed: 3-5 and the `suggest()` half of 2 in PR #431, 1 and the layer-2 half of 2 in PR #488
Depends on: — (1339 soft: the same family, where the improvement lives)

## Goal

The package's ΔBIC no longer blesses a parameter its own esd puts within one
sigma of zero. The skill rule that sends an agent to ΔBIC instead of
Hamilton's R-ratio is rewritten to say what is true today, the refuting
evidence (the t-ratio, `esd_inflation`) sits beside the verdict where the
verdict is made, and whether an effective observation count enters the
penalty is decided on a measured estimator.

## Context

Issue #270 (2026-09-05).

**The function.** `report/layer2.py::delta_bic` is

```
ΔBIC = N·ln(χ²_r/χ²_f) − n_added·ln(N)
```

with N the raw channel count. *Superseded in part 2026-09-26: since PR #431
both callers in the fit path charge it at N_eff = N/f² (§ Handover log,
2026-09-24); the free functions still default to raw N.* Schwarz 1978 for N independent Gaussian
observations, correctly implemented, and its docstring says so. It feeds
`strategy/suggest.py::_predicted_delta_bic` (with the residual row count as
N) and so `SuggestedAction.delta_bic`, which reaches the agent as "next:
free X, predicted ΔBIC +N". `SKILL.md` § 4 says: *"Adding parameters: use
ΔBIC, not Hamilton's R-ratio. Measured at 7251 channels, Hamilton's test
blesses a 0.13 % χ² improvement that is physically inert; ΔBIC carries the
sample-size penalty powder channel counts need."*

**The measured case.** Four single-histogram synchrotron patterns of one
compound, two specimens × two temperatures, about 49 500 points each. One
added degree of freedom: a mixed-site occupancy with its partner tied by
`occ₀ = 1 − occ₁`. Everything else identical. Le Bail to a fixed point, then
`mccusker_structural` plus one occupancy stage after `biso`.

| dataset | t = value/esd | ΔBIC (raw N) | `hamilton_justified` | `esd_inflation` | Durbin–Watson |
|---|---|---|---|---|---|
| 1 | 0.76σ | +36.2 | yes | 10.16 | 0.43 |
| 2 | 1.89σ | +211.0 | yes | 7.13 | 0.58 |
| 3 | 1.05σ | +71.1 | yes | 7.89 | 0.57 |
| 4 | 1.01σ | +80.9 | yes | 8.59 | 0.61 |

Not one reaches 2σ. All four ΔBIC are decisive. ΔBIC and Hamilton agree with
each other and disagree with the data, the opposite of what the skill rule
promises. The esds are already Bérar–Lelann inflated. The χ² ratios being
blessed are 1.00095–1.0045.

**Why.** The penalty is one ln N ≈ 10.8. The reward is N·ln(χ²_r/χ²_f)
≈ 49 493 × 1e-3 ≈ 50. A 5e-5 Rwp improvement outvotes the penalty by 3–20×,
and does so for any parameter at this channel count. The premise that fails
is independence, and the report refutes it two fields away: Durbin–Watson
0.43–0.61 and `esd_inflation` 7.1–10.2 against about 1.5 for white residuals.
Deflating by the variance ratio, N_eff = N/f² ≈ 480–970, flips every verdict
(−5.7, −2.5, −5.4, −5.3) and all four then agree with the esd and with each
other. The reporter is explicit that N/f² is a heuristic and not the fix; the
robust part is the direction and the order of magnitude.

**The published verdict.** The compound's refinement (*J. Phys.: Condens.
Matter* **25**, 186004, 2013; a joint X-ray + neutron fit) frees the same
occupancy, reaches 7.0(3) mol %, and concludes the disorder is suggested and
not established. The paper states the trap: with one added parameter against
51 295 points, Hamilton's test "makes virtually any improvement in Rwp
statistically significant".

**What the package already holds.** Root CLAUDE.md § Invariants (WP-1071):
the observation count is reflections and not points, and it gates nothing.
`optimize.statistics.effective_observations` (Altomare et al. 1995,
overlap-corrected) is the one authority for an effective N, written so a
diagnostic's *level* could be set from it. `delta_bic` never read it. That
does not make `effective_observations` the estimator: 1071's count is about
resolution, and the failure here is serial correlation, which the residual's
own autocorrelation measures. Two candidate estimators, then, and the choice
is a measurement.

**Three options, from the issue.** (1) Docs and skill only: ΔBIC on a powder
pattern inherits Hamilton's channel-count pathology, and the esd and
`esd_inflation` outrank it. (2) An effective N in the penalty, with a stated
estimator. (3) Return the pair: carry the parameter's t-ratio beside its
ΔBIC where the recommendation is made, so the disagreement is visible.

**Triage recommendation (2026-09-15):** (1) now, because the rule points the
wrong way today and costs a paragraph. (3) with one correction: `suggest()`
*predicts* ΔBIC before the parameter is freed, so no esd exists yet at that
point; the pair belongs on the *report* of a fit that freed the parameter
(layer 2, beside `hamilton_justified`), and `suggest()`'s prediction gets a
sentence saying it is a raw-N number. (2) only after both estimators
(`effective_observations`; N over the squared inflation) are compared on the
shipped acceptance fixtures, since the issue's data are withheld.

Not #219 (1339). That one is about *where* Δχ² lives; this is about N in the
penalty. Same family, different mechanism, different fix.

## Non-goals

- Hamilton's test itself, and `hamilton_justified`'s threshold.
- The `suggest()` ranking beyond the sentence it gains.
- Deciding the estimator without the comparison in task 3.

## Tasks

- [x] Skill: rewrite `SKILL.md` § 4's ΔBIC rule and add the
      `references/judging.md` row: at powder channel counts ΔBIC on raw N
      blesses any improvement; the parameter's esd and `esd_inflation`
      outrank both statistics. Paid for by a cut, per root CLAUDE.md § skill.
- [x] Layer 2 carries the t-ratio of a freed parameter beside the ΔBIC of
      adding it; the declared field's writer named at review (1076). (The
      `suggest()` half, the predicted ΔBIC saying which N it is charged at,
      landed in PR #431.)
- [x] Measure both effective-N estimators on every acceptance fixture and on
      the issue's shape (one occupancy DOF, synthetic if need be); the table
      in the handover decides whether `delta_bic` takes an `n_effective`.
- [x] Manual Part 2's model-comparison section states the premise ΔBIC needs
      and where the package measures its violation.
- [x] Tests: a synthetic fit at 50 000 correlated points where the added
      parameter is within 1σ of zero asserts the report shows both numbers.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_suggest.py tests/test_report_apply.py tests/test_fitreport_layers.py tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #270 (2026-09-05).
- Schwarz, G. (1978), *Ann. Statist.* **6**, 461.
- Altomare, A. et al. (1995), *J. Appl. Cryst.* **28**, 738 — the effective
  observation count WP-1071 quotes.
- Hamilton, W. C. (1965), *Acta Cryst.* **18**, 502.
- WP-1071, WP-1305 (`delta_bic`'s absent state), WP-1339.

## Handover log

### 2026-09-27 — closed: a freed parameter's t-ratio rides beside the ΔBIC of adding it

After a fit, rietx can now say whether a parameter you freed paid for itself.
It answers in two numbers kept together: ΔBIC charged at the pattern's effective
observation count, and how far each freed parameter moved in its own esd. For
one parameter the two agree, so issue #270's trap, a raw-count ΔBIC blessing an
occupancy within 1σ of zero, no longer has a route through the package's verbs
or through the skill, whose rule now reads the esd first. The session also found
that the χ² every result reports is the reduced one, which a hand-computed ΔBIC
had been using as the sum. That cost about one unit of raw-count ΔBIC per added
parameter. Re-judged at the effective count, the two Stephens acceptance claims
both hold.

**Done.**

- `report.compare_freed(restricted, full)` → `FreedComparison` (ΔBIC at N/f²
  with f the restricted fit's `esd_inflation`, the raw-N figure, and one
  `FreedParameter` per newly freed path with `held_at`, value, esd and
  `t_ratio`). No fit runs. It refuses a pair that is not nested: channel count,
  intensities, mode, a path the restricted fit frees and the fuller does not,
  nothing added, or a free count that moved by other than the added paths (a
  Pawley block whose reflection list changed). `predict_then_verify` is its
  second writer, on `VerificationOutcome.comparison`, `None` when nothing new
  was freed. `THRESHOLDS_VERSION` 1.7 → 1.8.
- A coordinate DOF's `held_at` is read through its own coordinate row, because
  its value is a step from where its own fit began (WP-1333). Right whichever
  model each fit started from.
- Both χ² go through `optimize.statistics._chi2_absolute`, moved there from
  `indexing/extinction.py` so layer2, extinction and the Stephens helper share
  one inverse of `compute_statistics`' division.
- Task 1: `SKILL.md` § 4's rule reads the t-ratio first, then ΔBIC at N/f²
  (body 1 B smaller). `references/judging.md` § 4 carries #270's table, the
  27-row separation, how to read a disagreement, and the by-hand rule.
- The Layer 2 module docstring and Part 2 said the actions were gated by
  Hamilton's test and ΔBIC. No call made either; both now say what is true.
  Part 1 `using/report.md` § After freeing it documents the new type.
- Siblings: `test_acceptance_stephens.py` passed the reduced χ² and judged at
  raw N. It now judges at N/f², and the corundum test is renamed
  `…_hamilton_blesses_it_only_at_raw_n`. `test_suggest.py`'s hand-built refit
  ΔBIC now goes through `compare_freed`. The validation matrix, VALIDATION.md,
  the skill's surprises row, the `CandidateGroup` docstring and its manual row
  carry the new figures.
- #431 and this session staged in `releases/1.5.1.md` (whose intro had said no
  statistic changed), narrated in the v1.6 record.
- Inherited pruned on arrival: its one entry pointed at PR #431's review, and
  #431 merged on 2026-09-24.

**Measured** (2026-09-26/27, macOS arm64, python 3.12, `[dev]`):

- LaB6 fixture with the data's Lorentzian width left out (21 400 channels,
  Durbin-Watson 0.099, f 6.074, N_eff 580): boron Biso t = +1.585, ΔBIC +86.98
  raw and −3.74 at N_eff; `profile.u` t = 7.08, +1980.56 and +47.58. On white
  residuals (f 1.47) the two ΔBIC agree to about 1.
- A coordinate DOF freed from a different starting coordinate: t = −15.037,
  equal to the coordinate row's own (x − x_held)/esd.
- Stephens, qarr, dispersion declined, 7251 channels, 3 added: brucite χ²
  ratio 1.0891, f 4.302, ΔBIC +592.34 raw and +15.53 at N_eff 392, Hamilton
  justified at both counts; its S_HKL value/esd 0.33, −1.14, 0.33, 2.31 (from
  zero, since the isotropic fit has no block). Corundum ratio 1.0016, f 3.826,
  −15.09 raw and −17.83 at N_eff 495, Hamilton justified at raw N only. With
  the reduced χ² the raw figures read +589.33 and −18.10, the −k bias.
- Fast suite on origin/main `612453fa` merged into the branch: 6438 passed,
  151 skipped (6589) in 4:43, no other suite running. Count check: the test
  files that differ from main collect 745 fast cases against main's copies'
  740, `test_compare_freed.py`'s five. Main's CI at `612453fa` totals 6582
  (Linux py3.14 `[dev]`), so the whole-suite gap is +7. The other two are
  platform: the 2026-09-26 nightly at `63e2a8c4` totals 6334 on macOS and 6331
  on Windows.
- Full suite not run: no forward model, solver or fitted value changed. The
  slow tests over changed code ran targeted and pass: `test_report_loop.py`
  and the two Stephens tests.

**Review** (`/code-review high --fix`): seven findings. It fixed five: the DOF
row lookup could follow a user tie of another DOF, two patterns on one grid
passed as one, the χ² un-reduction was a second copy, the module lacked its
xdist group, and a docstring missed a `None` case. Two were left to me. The
Pawley count now refuses rather than choosing a number. The brucite value/esd
figures are measured from zero, so they say no coefficient is quotable and not
that the pair disagrees; commit `74d39c59`'s message claims the latter, and
`611ab192` corrects the prose.

**Gotchas.**

- `compare_freed` refuses a reparameterised block such as Stephens, which
  locks `lor_strain` (its isotropic direction): the models are nested and the
  path sets are not. `test_acceptance_stephens._information` does that pair
  by hand.
- `layer2` reads `ParameterTable._anchored_dofs`, a private field, for the
  DOF's own rows.

**Deliberately not generalised.** `delta_bic` and `hamilton_justified` keep
raw N as their default, since the indexing callers count independent peaks.
`predict_then_verify`'s 1 % χ² rule is unchanged. `build_report` gains no ΔBIC,
because it runs no fits and one fit has no restricted χ².

**Next.** Nothing is owed here. Forward references went to 1418 (M-9's
ranking), 1419 (its ΔBIC figures do not say which N), 1453 and 1339. None was
blocked, so none is re-rated.

### 2026-09-24 — task 3 and half of task 2 landed from outside; ΔBIC is charged at N/f²

`report.layer2.delta_bic` and `hamilton_justified` now take `n_effective=`,
and `Refinement.suggest` charges its predicted ΔBIC at N_eff = N/f², with f
the Bérar-Lelann `esd_inflation` measured on the probe's rows. This is
issue #270's fix, live since PR #431 merged (`3b5c0519`, closing #270).
It came from an outside contributor with no `WP-NNNN:` prefix and no
touch of this file, so this entry is written at the merge. The WP stays
`⬜`: task 1 and the layer-2 half of task 2 are open, and no session owns
it.

**Task 3, measured before the default was chosen.** Both estimators were run
on every refining acceptance fixture: 27 rows, each the fixture's last-freed
scalar parameter, with the full fit compared against the same fit holding
that path at its seed. They were also run on the issue's shape, synthetically:
one occupancy DOF, 50 000 points, √y·AR(1) with ρ = 0.97, 11 seeds.

- **N/f²** refuses every |t| < 2.3 and admits every |t| ≥ 2.6 (13 of 13).
  Its rule is exactly t² > ln N_eff.
- **Altomare et al. (1995) M_ind**, WP-1071's count, refuses 8 of the 12 real
  effects it has a value for, up to t = 6.8. It admits one 0.81σ
  `lor_strain`, and it has no value on a joint fit.

N/f² is the default. 17 of the 27 rows are in the PR body, and the other ten
rows and the synthetic seeds stayed with the contributor.

**What the merge makes possible.** `CandidateGroup.delta_bic` is charged at
N_eff, with `delta_bic_raw_n` and `SuggestionResult.n_effective` beside it.
`summary()`'s "next:" line reads "predicted ΔBIC +x at N_eff n". Part 2 has
the premise, and where the package measures its violation, as eq
`est-effective-n` in `estimation.md`. `SCHEMA_VERSION` is now 0.27.

**What it deliberately does not do.**

- `n_effective=None` is raw N and bit-identical, so the indexing callers
  (`extinction.py`, `peakfit.py`) are untouched. Their N counts independent
  peaks or reflections.
- No layer-2 record carries the t-ratio of a freed parameter (the larger half
  of task 2). That needs a new FitReport entry, a restricted-χ² source (the
  start-of-stage metrics are not converged under `intermediate_ftol`), a
  schema bump and a manual row.
- `SKILL.md` § 4 is not rewritten and there is no `judging.md` row (task 1).
  The contributor's proposed § 4 sentence is on the PR.

**Gotchas.**

- A refit's ΔBIC is comparable with the prediction only when it is charged at
  the **restricted** fit's `esd_inflation`, since `suggest` measures f on the
  restricted state's residual. Round 2 of the review fixed the pinning test
  that compared them at different counts. `report.md` and `CandidateGroup`'s
  docstring now say so.
- `test_acceptance_stephens.py:251-254` and `:319-322` still judge the
  anisotropic-strain block at raw N, which is the reading #270 says passes
  any χ² gain.
- #433 (WP-1327) also claims `SCHEMA_VERSION` 0.27 and renumbers when it
  lands.

**Measured on the merged tree** (`origin/main` `2d42303a`
plus #430, #432 and #431; Linux x86_64, 4 cores, python 3.12, `[dev,jax]`):

- Fast suite: 1 failed, 5944 passed, 96 skipped. The failure is
  `test_telemetry.py`'s unwritable-directory case, which fails on main alone
  because the bench runs as root.
- Fast collect with #431 alone on main: 6015 → 6021, +6.
- Full `-m slow`: 2 failed, 188 passed, 9 skipped in 1:32:45. Neither failure
  is #431's. The brucite XPASS(strict) is red on main's own nightly (run 51).
  The held-phase ramp tripped its 60 s runaway guard at 147 s under load. Run
  alone it passes, in 21.4 s on this tree against 20.3 s on main.
- `ruff`: clean.

**Next** is task 1, the skill rule, which is the maintainer's file. After it
comes the layer-2 half of task 2.

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #270).
  Checked against the tree: `delta_bic` takes raw N from both callers; the
  skill rule reads as the issue quotes it; `effective_observations` exists
  and is unread here. Recommendation recorded, with the correction that the
  t-ratio can only sit on the report, not on the prediction.
