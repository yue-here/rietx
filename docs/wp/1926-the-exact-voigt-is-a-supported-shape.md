# WP-1926 — the exact Voigt is a supported shape: its cost, its width, its exports and its bound

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #790).
  Checked against the tree at 5d1f5f67: the Voigt has a cross-backend row, a
  compare variant and three writers that decide; it has no compiled kernel
  (8-16× the pV kernel, measured above), no exact FWHM, no TOPAS statement
  and no pattern-level bound in the manual. No open WP owns it: WP-1521 is
  the compiled tier's reporting, WP-1911 the writers' setting, scale and
  free set, and WP-1122 (🛑) the peaks buffer. Decided 2026-10-08: TCH stays the
  default, TOPAS refuses by name, the kernel pair waits. *Next:* the manual's
  pattern-level bound on a committed synthetic case.
