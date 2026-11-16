# WP-1926 — the exact Voigt is a supported shape: its cost, its width, its exports and its bound

Milestone: unscheduled · Status: ⬜ 2026-11-16 — the Voigt FWHM landed (#1605); next: the manual's pattern-level bias
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (PR #815 soft: the TOPAS whole-input writer the TOPAS task extends)
Priority: P3 2026-10-08 — opt-in and correct today; what it lacks is speed, an exact reported width and one writer's statement, and the default stays TCH either way

## Goal

`shape="voigt"` runs on the compiled tier, reports an exact FWHM, and each
writer states it or refuses it by name. The manual quotes the pattern-level
bias of the TCH pseudo-Voigt beside the shape bounds it already quotes. The
default stays the TCH pseudo-Voigt.

## Context

Issue #790 (mustachefeeling, 2026-10-06) is a design question with
measurements. rietx makes one approximate step in its profile: the
Thompson-Cox-Hastings pseudo-Voigt that turns Γ_G and Γ_L into Γ and η
(`model/profiles/pseudovoigt.py`). The exact Gaussian ⊗ Lorentzian exists as
`shape="voigt"` (WP-0405, Faddeeva `w(z)` in `model/profiles/faddeeva.py`).
Both shapes consume the same component FWHMs, so switching never touches the
parameter table. The issue recommends keeping `tchz_pv` the default and
making `voigt` first-class as an opt-in.

**What the issue measured** (at 7e9489ad, synthetic, not reproduced here):
the pV departs from the Voigt by up to 1.27 % of the peak height near
Γ_L/Γ_G ≈ 0.9. A pattern made with `voigt` and refined with `tchz_pv` lands
`lor_size` within -1.4 % to +0.2 % with the instrument held. With U, V, W, X
and Y free too, Y drops 18 % and U rises 7 % at an Rwp of 0.08 % on
noise-free data. TOPAS's `str`-level `lor_fwhm` (PR #782) sits 2.0e-3 of the
peak from rietx's pV and 4.3e-3 from its Voigt. TOPAS's own convolution onto
a PV peak type is a pseudo-Voigt approximation too (Technical Reference
§ 5.6). Its `more_accurate_Voigt` improves on it about 100×.

**Checked against the tree at 5d1f5f67:**

- *Derivatives and backends: covered.* `tests/test_cross_backend.py` carries
  the `families_voigt` row, and `tests/test_voigt.py` holds the Faddeeva
  accuracy, the limits, the analytic-against-FD Jacobian and the FCJ
  composition.
- *The shape bound: quoted and tested.* `MANUAL_FWHM_ERROR_PCT` = 0.43,
  `MANUAL_SHAPE_ERROR_PCT` = 1.3 and `MANUAL_CENTRE_ERROR_PCT` = 0.25
  (`tests/test_voigt.py:340-342`) hold `docs/manual/profiles.md`'s numbers.
  The pattern-level bias is not in the manual.
- *The compiled tier: declined.* `model/compiled.py` declines a `voigt` model
  and the numpy path runs (its docstring, line 25). Measured with
  `CompiledModel.evaluate` on a cubic Pm-3m cell at a = 14 Å, 10-140° at
  0.02° (6500 points), the lab instrument of `tests/test_lab_instrument.py`,
  macOS arm64, `[dev]`, load average 34-40: pV compiled 0.52-0.66 ms, pV
  numpy 1.3-1.8 ms, Voigt 4.2-10.6 ms. That is 8-16× the pV kernel and 3-6×
  numpy pV, two runs each, min and median. The Voigt answer is
  bit-identical with the tier on and off. The issue's own numbers are 12×
  and 5× on a 5500-point case.
- *The FWHM: the TCH quintic.* `CompiledModel.peak_fwhm` under `voigt`
  inverts (σ, γ) to the component FWHMs exactly and then applies the TCH
  quintic (`model/forward.py:1462`). It is evaluate-only and never in the
  residual. Olivero & Longbothum (1977) is 0.02 % by the issue's account.
  *Superseded in part 2026-11-16:* `peak_fwhm` under `voigt` now applies
  Olivero & Longbothum (`profiles.voigt.voigt_fwhm`, measured 0.024 % worst);
  `peak_gamma_eta` keeps the quintic for window sizing and FCJ node counts.
- *The compare row: present, unread.* `viz/compare.py` registers a `voigt`
  variant ("+ true Voigt peak shape"), and `tests/test_compare_ui.py`
  asserts every variant is reachable. No reading of it on the standards is
  recorded in `docs/milestones/` or the manual.
- *The writers: three of four already decide.* `write_fullprof_pcr` refuses
  a non-`tchz_pv` profile by name (`fullprof.py:3270`). `write_gsas_prm`
  and the `.instprm` writer write the widths and name the shape change in
  their diagnostic (`instrument_profile.py:1018`, `:1759`). On `main`,
  `write_topas_inp` states no profile. PR #815's whole input refuses
  `voigt` by name.

**Where the time goes in a kernel.** A new kernel is serial
`njit(cache=True, nogil=True)` over a row range on the shared pool, never
`prange`. Its equivalence bar is 1e-13 relative where it calls `exp`
(root CLAUDE.md, the compiled tier). The numpy Voigt stays the oracle, and
`RIETX_COMPILED=0` must still exercise it.

**Licensing.** TOPAS is closed: its Technical Reference and black-box runs
only. Weideman (1994) and Olivero & Longbothum (1977) are papers.

**The compiled tier is the `rietx-kernels` Rust crate now** (folded from
`### Inherited` on 2026-11-16; WP-1940, closed). `_kernels_numba.py` is gone
and `kernels/src/` holds one module per kernel family (`fcj.rs`,
`raster.rs`, …), so a Voigt kernel takes a module of its own, ships as a
minor kernel release and raises rietx's pin floor to it (`docs/RELEASING.md`
§ The kernel wheel). Its bar is `compiled.py`'s rule 3: 1e-13 relative where
it calls the C library's transcendental; a ulp bound asserted on every wheel
where it carries its own, as the FCJ `exp` does
(`test_the_fcj_exponential_holds_its_stated_bound`), plus a slow whole-fit
guard comparing the two paths.

**The TOPAS refusal is in code and pinned by no test** (folded from
`### Inherited` on 2026-11-16; the 2026-10-11 issue triage of #790).
`io/projects/topas_input.py:373-379` refuses any `profile.shape` other than
`tchz_pv` by name; checked against the tree at bc77a934, no test in
`test_topas_whole_input.py` or `test_projects_topas.py` passes
`shape="voigt"`, so the TOPAS task reduces to that test.

## Non-goals

- Fundamental parameters, and the transparency *shape* (Cheary & Coelho
  1992). Both sit behind the v2+ FPA fence (DESIGN.md, locked decisions).
- A hybrid with exact sample terms over a TCH instrument (#790 option d).
  The approximation lives in the Gaussian ⊗ Lorentzian seam itself.
- `indexing/peakfit.py`'s single-peak shape. The issue notes a -10 % Γ_L
  bias there; it is indexing's to decide once a kernel exists.

## Tasks

- [x] **Decided 2026-10-08 (maintainer), on #790's three questions.** (1) The
      TCH pseudo-Voigt stays the default. (2) The TOPAS writer refuses a
      `voigt` model by name until a TOPAS run measures `more_accurate_Voigt`.
      (3) The kernel pair is deferred until the compare readings show the
      shape in use.
- [ ] Manual: § Thompson-Cox-Hastings pseudo-Voigt gains the pattern-level
      bias, measured here on a committed synthetic case, with test constants
      beside the three it has
- [ ] Read the `voigt` compare variant on srm660c, srm676a, lab6_cbn and nac,
      and record the cumulative Δχ² panel in the handover
- [x] `peak_fwhm` under `voigt` by Olivero & Longbothum (1977); window sizing
      and `fcj_node_count` keep the quintic. A test against a bisected
      Faddeeva FWHM — `profiles.voigt.voigt_fwhm`, 0.024 % worst
      (`MANUAL_OLIVERO_FWHM_ERROR_PCT`), equation `prof-voigt-fwhm` in the
      manual, audit row `_OLIVERO_FWHM` at tier 2 (2026-11-16)
- [ ] Deferred until the compare readings show the shape in use: the kernel pair (symmetric and FCJ, forward and bases) in
      a `kernels/src/` module of its own, dispatched in `compiled.py`, held
      to rule 3's bar by `tests/test_compiled_kernels.py`'s pattern
- [ ] The TOPAS whole-input writer refuses a `voigt` model by name, after
      #815 — in code; what is left is the test
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for the compare readings
- [ ] Skill: none expected; a `references/` row only if the default moves or
      a writer gains a diagnostic code

## Acceptance

`shape="voigt"` evaluates on the compiled tier within its stated bar of the
numpy Voigt, or the WP records the decision not to build one. Its FWHM
matches a bisected Faddeeva FWHM to the bound the test states. Every writer
states the shape or refuses it by name.

```sh
.venv/bin/python -m pytest tests/test_voigt.py tests/test_compiled_kernels.py tests/test_cross_backend.py tests/test_compare_ui.py tests/test_manual.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Thompson, P., Cox, D. E. & Hastings, J. B. (1987). *J. Appl. Cryst.* **20**, 79-83.
- Olivero, J. J. & Longbothum, R. L. (1977). *J. Quant. Spectrosc. Radiat. Transfer* **17**, 233-236.
- Weideman, J. A. C. (1994). *SIAM J. Numer. Anal.* **31**, 1497-1518.
- Coelho, A. A. TOPAS Technical Reference, § 5.6 (`more_accurate_Voigt`).
- WP-0405 (the Faddeeva Voigt), WP-1115 (the compiled tier), WP-1122 (the
  peaks buffer and the FPA fence).

## Handover log

- **2026-11-16** — ghostshift runner, one task, PR #1605. A peak drawn with
  the exact Voigt now reports its own width: the number the diagnostics, the
  observation count and the magnetic reports read is within 0.024 % of the
  true Voigt FWHM, where it was up to 0.43 % off through the pseudo-Voigt's
  formula. Nothing changes for the default shape, and the windows and FCJ
  sizing a Voigt fit uses are unchanged too, so no fitted value can move.
  *Done:* `profiles.voigt.voigt_fwhm` (Olivero & Longbothum), used by
  `CompiledModel.peak_fwhm` under `"voigt"`; `peak_gamma_eta` keeps the
  quintic. Manual equation `prof-voigt-fwhm` with bib `olivero1977` (Crossref
  and OpenAlex agree; the paper is not held, FETCH row 381). Audit row
  `_OLIVERO_FWHM`, tier 2. `### Inherited` folded into Context and Tasks: the
  kernel task now points at `kernels/src/` (the Rust crate), and the TOPAS
  task is the missing test only (`topas_input.py:373-379` refuses).
  *Measured:* 121 log-spaced Γ_L/Γ_G in 1e-3..1e3 plus both limits against a
  bisected Faddeeva FWHM: Olivero 0.0237 % worst at 0.28, TCH 0.432 % at
  0.45; Gaussian limit exact, Lorentzian +3.1e-6. Fast suite on a Linux workstation (`[dev]` venv, Linux x86_64 under WSL,
  commit 12f6336cc, `-m "not slow" -n 8`, shared with another job at load 15-27):
  14852 passed / 280 skipped / 32 xfailed / 0 failed, 1002 s. The two added tests
  cost 0.21 s together in that run's junit; they are the only tests added, so the
  count should be the merge-base's +2 (not measured on it). Canary (test_voigt, audit_table,
  help, low_angle_region, derivative_bases_batched, `-n 4`): 104 passed. The
  full selection was not run: under `"tchz_pv"` the change is bit-identical
  (pinned), and no slow test reads a Voigt peak width.
  reader_output exit 0 (unchanged against bc77a934e).
  *Review:* a read-only review subagent found no defect; two notes applied
  (the manual's reader list gained the magnetic-only region;
  `instrument_fwhm_deg` says it stays on the quintic, so the width
  diagnostic compares Olivero phase widths with a quintic instrument scale,
  up to 0.43 % apart, which sets a scale and nothing else). Not applied: the
  old "~1 %" comment at `forward.py` `compile_model`'s quintic (0.43 %
  measured), out of this diff.
  *Generality:* two items, both **holds** (judge's sections, unedited):

  #### `rietx.model.profiles.voigt._OLIVERO_FWHM` (constant, tier 2, value (0.5346, 0.2166))

  **Verdict: holds.** The case for it is stronger. It decides nothing. It is a closed-form approximation to a number the package could compute exactly. It applies only under a shape the caller chose. Its error is measured in this repository across the whole mixing range. The case against found nothing.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides that the caller did not ask for | "the reported FWHM of shape='voigt' only, never window sizing" (row `evidence`, `_audit.py`) | It picks no action. `CompiledModel.peak_fwhm` reaches it only when `self.shape == "voigt"`, which is opt-in; the default `tchz_pv` path is unchanged, and `test_peak_fwhm_under_voigt_is_olivero_and_window_sizing_keeps_the_quintic` pins that bit for bit. Under voigt the reported width moves by at most about 0.4 % (from the TCH quintic's 0.43 % error to 0.024 %). That width feeds the existing thresholds in `refine.py:10859` (the low-angle diagnostic), `refine.py:11918` (the width census), `optimize/statistics.py:1364` (the observation count), the satellite and magnetic reports, and `strategy/magnetic.py:749`. Those thresholds have their own rows, and this change only makes their input more accurate. | holds |
  | 2. Rule 1's kind, and the row's `ambiguity` | none given (a constant row needs no `ambiguity` field, per the `Row` docstring) | No ambiguity of any of the three kinds. The exact Voigt FWHM is a definite number; the coefficients only approximate it. | holds |
  | 3. Case against | — | none found. A refiner who wanted the exact width could bisect the Faddeeva function. At 0.024 %, no width-based diagnostic level could plausibly change. | none found |
  | 4. Case for | "measured within 0.024 % of the bisected Faddeeva FWHM over the whole mixing range" (row `evidence`); manual equation `prof-voigt-fwhm` | Confirmed in the diff: `test_olivero_reproduces_the_voigt_fwhm_to_the_bound_the_manual_quotes` sweeps 121 ratios Γ_L/Γ_G (Lorentzian over Gaussian width) from 1e-3 to 1e3, plus both pure limits. It asserts the 0.024 % ceiling, a floor at half of it, and that the worst case falls at a ratio between 0.2 and 0.4. Keeping the TCH quintic instead leaves the reported width off the shape actually evaluated by up to 0.43 %. | holds |
  | 5. Tier and source | Tier 2: Olivero & Longbothum (1977), JQSRT 17, 233 (docstring, `references.bib`) | A tier-2 citation that tested the formula. I did not check what the seven programs report as a Voigt FWHM by default: `docs/practice.md` has no entry on it, and I do not recall it reliably. Arguably this is tier 1 under the numerical-setting clause, since it controls how accurately rietx computes a number, not what it decides, and a test bounds its error over every input it claims. Either tier keeps it. | holds (tier 1 also defensible; maintainer's call) |
  | 6. Unrelated dataset families | none given (none needed) | No dataset is involved. The reference is the exact Faddeeva computation, so the test is verification by arithmetic identity, not validation. | n/a |
  | 7. Record field or code that says it fired | none given | No field is needed for an approximation that takes no action. The shape choice is already on the instrument profile (`profile.shape`). | holds |

  Evidence that would change the verdict: a consumer that sets an action's threshold from `peak_fwhm` in a way that is sensitive at the 0.4 % level, or a program default that reports a different Voigt width and that rietx output is meant to match.

  #### Second trigger: heuristics the table cannot see

  **Verdict: holds.** No unseen heuristic was added. The case against found nothing.

  | Question | Author's answer (where) | What I found | Verdict |
  |---|---|---|---|
  | 1. What it decides that the caller did not ask for | `peak_gamma_eta` keeps the quintic for window sizing and FCJ node counts (the quadrature node counts for the axial-divergence correction), while `peak_fwhm` uses Olivero; "decided 2026-10-08" (`forward.py` docstring; manual; WP checklist) | The `if self.shape == "voigt"` branch in `peak_fwhm` dispatches on a shape the caller named. It is not an ordering or fallback chain the package chooses. Window sizing under voigt is unchanged from before the diff (bit-identical, pinned by test). So no action, threshold or default moved, and nothing new is always-on. The inline literals are `2.0 *` (half-width to full width) and `GAUSS_FWHM_TO_SIGMA`, both arithmetic. No skill prose was added. | holds |
  | 2. Kind of ambiguity | — | None; this is pure arithmetic. | holds |
  | 3. Case against | — | none found | none found |
  | 4. Case for | "one sizing rule keeps a `"voigt"` fit's windows those of the same `"tchz_pv"` fit" (manual, `profiles.md`) | Sound. The sizing is frozen per stage and approximate by design, and it is already governed by existing sizing rows. | holds |
  | 5. Tier or source of the decision | maintainer, 2026-10-08 (dispatch) | Partly on record. The WP's "Decided 2026-10-08 (maintainer)" item names only #790's three questions: TCH stays the default, TOPAS refuses voigt, the kernels wait. The split between the reported width and the sizing width is in the checklist task written when the WP was created that day ("window sizing and `fcj_node_count` keep the quintic"), not in that decided item. | weak provenance, no effect on the verdict |
  | 6. Dataset families | — | n/a | n/a |
  | 7. Record field or code | — | None is needed: nothing fires. | holds |

  Evidence that would change the verdict: a later consumer that reads `peak_gamma_eta`'s Γ as a reported width under voigt, or a sizing rule that diverges between the two shapes.

  Author's answer: no `fails`. On item 5 of the first section, tier 2 is kept as written; tier 1 is the maintainer's call.

  *Next:* the manual's pattern-level bias on a committed synthetic case
  (first, since it is self-contained); then the TOPAS refusal test (one
  `pytest.raises` passing `shape="voigt"` to `write_topas_inp`); then the
  compare readings on srm660c, srm676a, lab6_cbn and nac, which decide
  whether the deferred kernel pair is wanted.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #790).
  Checked against the tree at 5d1f5f67: the Voigt has a cross-backend row, a
  compare variant and three writers that decide; it has no compiled kernel
  (8-16× the pV kernel, measured above), no exact FWHM, no TOPAS statement
  and no pattern-level bound in the manual. No open WP owns it: WP-1521 is
  the compiled tier's reporting, WP-1911 the writers' setting, scale and
  free set, and WP-1122 (🛑) the peaks buffer. Decided 2026-10-08: TCH stays the
  default, TOPAS refuses by name, the kernel pair waits. *Next:* the manual's
  pattern-level bound on a committed synthetic case.
