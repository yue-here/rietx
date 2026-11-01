# WP-2044 — The Sabine Laue factor is continuous at x = 1

Milestone: unscheduled · Status: ✅ 2026-10-24 — E_L = e^(−x)·[I₀ + I₁] on every backend; the QPA guide's esd agrees on macOS and Linux
Track: What fires, and what stays silent
Depends on: —

## Goal

The Laue half of the Sabine extinction factor is one continuous function of
x, so no fit can park on a step at x = 1. The extinction column agrees with a
central difference at any step on the QPA guide's fit, and that fit's esds
agree between Linux and GitHub's macOS runner. The other programs' choices and
the paper are on record first, in `docs/practice.md`.

## Context

**The model.** `src/rietx/model/extinction.py` implements Sabine's
polycrystalline extinction, E = E_B·sin²θ + E_L·cos²θ, with
x = ext·|F|²·(λ/V)²·Xpol per reflection. It copies GSAS-II's `GetPwdrExt`
for E_L: the six-term series 1 + Σ cᵢxⁱ on 0 < x ≤ 1, and the two-term
asymptote √(2/πx)·(1 − 1/8x) above. Checked in GSAS-II 5.8.4 source
(`GSASII/GSASIIstrMath.py`, `GetPwdrExt`) on 2026-10-24. The two meet with
a step: E_L(1⁻) = 0.67420 and E_L(1⁺) = 0.69815, 3.6 %. The module docstring
keeps the step for the cross-code golden in `tests/test_extinction.py`, and
says real powder data keep x ≪ 1. GSAS-II differentiates its two branches
analytically (`GetPwdrExtDerv`). rietx takes the extinction column by a
forward difference in `optimize/least_squares._peak_chain_column`, at
h = 1e-6 relative.

**What WP-2043 measured, 2026-10-24.** The fit is `examples/guides/qpa.py`'s
first: 11-BM NAC with a CaF₂ impurity, plan `mccusker_structural`, 2-24°.
- At the answer CaF₂'s 11 reflections reach x = 6.49, five have x > 1, and the
  one at 2θ 19.004° has x = 1.0000. The solver parks extinction where a
  reflection touches the step: 1361.11 µm² in 1.9.0, 1361.15 on `main`.
- At the answer the column agrees with a central difference at 1e-6 (norm
  0.1957, cosine 1.0). A central difference at 1e-4 straddles the step: norm
  22.47, cosine −0.19. Earlier closing-stage iterates handed the solver a
  column of norm 4503.
- On GitHub's `macos-26-arm64` runner the last Jacobian straddled. CaF₂ came
  out 3.08 ± 0.21 wt% and extinction 1361 ± 0.007, against 3.08 ± 2.24 and
  1361 ± 2116 on Linux and on a local arm64 Mac. 1.9.0 gave 3.09 ± 2.32 on
  both. Run 40083266263 on branch `tmp/wp2043-macos-qpa`, whose workflow
  `.github/workflows/tmp-wp2043-qpa.yml` and probe re-run the check.

**The candidate.** e^(−x)·[I₀(x) + I₁(x)], with I₀ and I₁ the modified Bessel
functions, expands to Sabine's c₁…c₄, to c₅ = −7/640, and to his four-term
asymptote 1 − 1/8x − 3/128x² − 15/1024x³. That is WP-2043's own expansion, not
read from a paper. In code it is `i0e(x) + i1e(x)`, with
dE_L/dx = −i1e(x)/x, which is −1/2 at x = 0. Against GSAS-II's branches it
differs by 4e-8 at x = 0.25, 5.6e-6 at 0.5, 7.9e-4 at 1⁻, 3.6e-2 at 1⁺,
9.8e-3 at 2 and 1.1e-3 at 5. Patched into the QPA fit on numpy alone, it gave
extinction 1919 ± 4066 µm², CaF₂ 3.58 ± 3.53 wt% and Rwp 0.08163 against
0.08156. `HIGH_CORRELATION` scale ~ extinction at ρ = +0.998 fired where it had
not. The held fit stayed at 1.37 ± 0.07 wt%.

**The maintainer's ruling, 2026-10-24.** Option 1 of three (the continuous
function, before the 1.10 tag), filed as this stub, which checks the other
programs and the paper first. The two not taken: cut 1.10 now and owe 1.10.1;
or an analytic column on GSAS-II's form, which ends the esd lottery and leaves
the parking. The maintainer's standing rule is accuracy first, with a
program's convention served beside it where someone needs it.

**The paper, read 2026-10-24.** Sabine, Von Dreele & Jørgensen (1988) eqs 3-4
give E_L as the series 1 − x/2 + x²/4 − 5x³/48 + 7x⁴/192 for x ≤ 1 and the
four-term asymptote √(2/πx)·[1 − 1/8x − 3/128x² − 15/1024x³] above, with no
closed form, and defer the derivation to Sabine (1988). ITC Vol C §6.4.5
(Sabine's own chapter, 2006 edition, eqs 6.4.5.3-4) prints the same pair and
says how it was built: the Laue-case diffracted fraction ½[1 − e^(−2σD)] of
eq 6.4.4.3, with a Lorentzian σ(k), integrated over k and divided by the
kinematic intensity. That integral, (1/πx)·∫ ½[1 − e^(−2x/(1+u²))] du, was
evaluated by quadrature here and equals `i0e(x) + i1e(x)` to 3e-16 relative
from x = 0.001 to 100. So e^(−x)·[I₀ + I₁] is the exact function both
expansions truncate. It is derived here, from ITC's stated construction, and
is printed in neither source. The paper's own pair steps too, 0.68229 to
0.66776 (2.2 %) at x = 1. GSAS-II's six-term series and two-term asymptote
step 3.6 %.

**The survey, 2026-10-24** (`docs/practice.md` § Extinction). Only GSAS-II
and MAUD carry Sabine's E_L. Both switch branches at x = 1 and state no reason.
MAUD's step is +7.0 %, because it puts the asymptote's bracket inside the
square root. TOPAS, FullProf, RIETAN-FP, BGMN and cryspy-powder have no Laue
and Bragg split at all. So the checkpoint did not fire. No program uses an
exact form, and none keeps the step for a stated reason. TOPAS's expression
language has no modified Bessel function, which settles the writer's task: it
spells an approximation, measured at write.

**A second copy of the formula.** The TOPAS writer
(`io/projects/topas_input.py`, the extinction builder near line 405) spells
the same two branches into a `scale_pks` expression, from its own
`_SABINE_LAUE` and `_SABINE_XPOL` (audit rows at `_audit.py` 1495-1496). Its
docstring measured TOPAS 6 against rietx at extinction 20 (`case_nacl_xray`,
Y_calc to 2.6e-3). Whether TOPAS's expression language has I₀ and I₁ is
unchecked.

**The neighbour.** WP-1944 (issue #877) owns *which* phases
`mccusker_structural` frees extinction on: every phase today, which is why
CaF₂'s is free to walk here. It does not own the function, and neither fix
replaces the other.

**Tier.** Physics: the function is Sabine's own, written exactly rather than as
two truncated expansions. No threshold or automatic action is added.

## Non-goals

- Secondary extinction, or an extinction model other than Sabine's.
- The 1.10 cut's own work. That is WP-2043, which waits on this one.

## Tasks

- [x] The paper: Sabine, Von Dreele & Jørgensen (1988), *Acta Cryst.* A44,
      374, at `/Users/yue/Zotero yue-here/storage/HXSZ3X8N/Sabine et al. - 1988
      - Extinction in time-of-flight neutron powder diffractometry.pdf`. What
      it gives for E_L: the series, the asymptote, a closed form, a switch
      point. Whether e^(−x)·[I₀ + I₁] is stated or implied. Sabine (1988),
      *Acta Cryst.* A44, 368, eqs 6 and 16, is not in the corpus: ask the
      maintainer for it if the first paper does not settle the form
- [x] The other programs, each marked checked or inferred: TOPAS (the
      technical reference, topas-academic.com/technical_reference), FullProf,
      RIETAN-FP, BGMN, MAUD and EasyDiffraction (sources and manuals under
      `~/Code/rietx-bench/tools/`), GSAS-II (checked above). For each, the
      extinction model, whether E_L is continuous at x = 1, and how its
      derivative is taken. Into `docs/practice.md` as a new § Extinction
- [x] Checkpoint: if the survey changes the case, such as a program using an
      exact form or every program keeping the step for a stated reason, bring
      it to the maintainer before any code
- [x] `model/extinction.py`: E_L = e^(−x)·[I₀ + I₁] and its derivative, on
      numpy, jax and torch. `i0e` and `i1e` join `_OP_NAMES` and every
      backend, or `tests/test_backend_conformance.py` fails. The docstring's
      "out of reach for real powder data" goes, replaced by the QPA fit's
      numbers
- [x] The TOPAS writer follows the model, or states where it cannot: an
      exact form if TOPAS's expression language has the functions, otherwise
      the closest it can spell, with the difference measured and reported at
      write. Its round-trip test re-run
- [x] The column: a test that the extinction column on the QPA guide's fit
      agrees with a central difference at 1e-4 and at 1e-6. Whether an
      analytic column (`sabine_extinction_and_dx` exists) should replace the
      forward difference is decided on that test's numbers. *Decided
      2026-10-24: kept.* At the answer the forward-difference column misses
      a central difference by 6.7e-7 of its norm at every step from 1e-2 to
      1e-8, which is its own truncation error. With GSAS-II's branches
      patched back in, the same test misses by 100 % at 1e-4
- [x] `tests/test_extinction.py`: the GSAS-II transcription becomes a
      comparison within the band above, and a test asserts E_L is continuous
      at x = 1. `tests/test_cross_backend.py` rows for extinction; the
      bit-identity goldens that carry extinction recaptured, with the move
      quoted
- [x] The QPA guide re-pinned (`examples/guides/qpa.py`, its page), and its
      first fit re-run on the macOS runner by re-pushing
      `tmp/wp2043-macos-qpa`. The branch is deleted after. *Done
      2026-10-24 on a branch of its own*, `tmp/wp2044-macos-qpa` (run
      40087721222, deleted after), since 2043's branch belongs to a live
      session: macOS arm64 and Linux x86_64 both give CaF₂ 3.5769 ± 3.5333
      wt%, compiled tier on and off
- [x] Manual: the Theory tab's extinction equation with its `*Source:*` line.
      Notes: a "Numbers that move" entry in `docs/releases/1.10.0.md` naming
      who moves (a fit where some reflection's x passes about 0.5)
- [x] Skill: none expected. The new `HIGH_CORRELATION` firing is the existing
      code's row. *Confirmed*: the page already quoted that firing at
      ρ = +0.996, and no skill file quotes the QPA guide's numbers

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction.py tests/test_cross_backend.py \
  tests/test_backend_conformance.py tests/test_examples.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

And on the macOS runner, the QPA guide's first fit gives the same CaF₂ esd as
Linux to two significant figures.

## References

- Sabine, T. M., Von Dreele, R. B. & Jørgensen, J.-E. (1988). *Acta Cryst.*
  A44, 374-379.
- Sabine, T. M. (1988). *Acta Cryst.* A44, 368-373.
- GSAS-II 5.8.4, `GSASIIstrMath.GetPwdrExt` and `GetPwdrExtDerv`.
- `docs/wp/2043-cut-1-10-0.md` § Context, for the runner measurements.

## Handover log

### 2026-10-24 (2nd session) — closed: the Laue factor is exact, and the QPA esd no longer depends on the platform

Sabine's Laue extinction factor is now one continuous function, the exact
integral his papers' series and asymptote both truncate. Any fit with
extinction on and some reflection past x ≈ 0.5 moves. The QPA guide's free fit
is the visible case: CaF₂ reads 3.58 ± 3.53 wt% on macOS and Linux alike, where
1.10's tree had given ± 0.21 on one and ± 2.24 on the other. No other Rietveld
program surveyed evaluates the factor continuously, so rietx now departs from
GSAS-II and MAUD here, on the strength of the integral rather than a
convention. The TOPAS export cannot spell a Bessel function and carries a
polynomial approximation within 3.6e-8, untested in TOPAS itself.

*Done.* The paper item (eqs 3-4 of Sabine, Von Dreele & Jørgensen 1988; ITC C
§6.4.5's construction), and the survey into `docs/practice.md` § Extinction.
The checkpoint did not fire. `model/extinction.py` uses `i0e + i1e`, and both
ops joined `backend/api.py`'s vocabulary on numpy, jax, torch and torch-mps
(this item was a lane). An argument shift of 2⁻¹²⁶ (`_ARG_SHIFT`) sets the slope
at x = 0 to −1/2. Unshifted, numpy reads 0/0 there and jax and torch +1/2. The
TOPAS writer spells A&S 9.8.1-9.8.4 and says so in the file's head. Also done:
the column test on the QPA fit (slow), the cross-backend row
`extinction_strong` (reflections straddling x = 1), the band and continuity
tests, the two golden recaptures (`tests/data/README.md`), the guide re-pin,
the Theory-tab equation and the 1.10 notes entry. The macOS check ran on a
branch of its own, `tmp/wp2044-macos-qpa`, deleted after.

*Measured* (venv `[dev,jax,torch]`, macOS 26.6.2 arm64, Python 3.12.10, numpy
2.5.4, scipy 1.18.1, unless named):
- The QPA guide's first fit, run 40087721222 on GitHub (`macos-latest` arm64
  and `ubuntu-latest` x86_64, Python 3.13, compiled tier on and off): CaF₂
  3.5769 ± 3.5333 wt%, extinction 1919.38 ± 4065.9 µm² and Rwp 0.081630 in all
  four cells.
- The column at that answer: forward difference against central at relative
  steps 1e-2 to 1e-8, miss 6.7e-7 of the norm from 1e-4 down (5.0e-5 at 1e-2),
  cosine 1.0. With GSAS-II's branches patched in, the same test misses by
  100 % at 1e-4.
- `_laue_and_deriv` on 10⁴ values: 237 µs a call, against 318 µs for the old
  branches.
- The TOPAS spelling's error against `i0e + i1e`: supremum 3.5914e-8 relative,
  at x ≈ 96.6, step 6e-9 at x = 3.75.
- Goldens: `srm660c` moved in its extinction column only, by 9.3e-6 of the
  norm. `toy_rich` moved by 1.2e-5 there, and at most 4e-13 elsewhere. Both are
  rounding of a 1e-9 µm² step at x ≈ 1e-10: there scipy's `i0e` carries about
  1e-6 of slope error against 8e-8 for the old polynomial. The other nine
  states were bit-identical.
- Fast selection, alone on the machine: 11 783 passed, 111 skipped, 27 xfailed,
  1 failed in 8:38. The failure is `test_display`'s kernel test, from the stale
  user kernel spec. It passes under `JUPYTER_PREFER_ENV_PATH=1`. Against the
  lane's run of the same selection earlier today (11 778 + 111 + 27 + 5 failed),
  the total rose by 1, the one fast test added since
  (`test_the_written_laue_factor_is_within_its_stated_bound`). The QPA column
  test is `slow` and absent from the fast run. Added fast tests cost 0.83 s
  together on this machine (`tests.added_test_times`; worst 0.62 s, the two jax
  and torch autodiff cases). None joins the slow tail.
- Full selection, alone on the machine, on this branch with `main` merged
  (`main` had not moved): 12 191 passed, 114 skipped, 43 xfailed, 3 failed in
  58:32. `test_watch_app`'s real-GUI boot passes alone, a flake under load. The
  NAC termination-view golden and the skill placement episode fail identically
  on an `origin/main` snapshot without this branch. They belong to WP-2037's
  landed work, and its Inherited has both. The QPA column test passed in this
  run.
- Lanes: one, `model ~30`, ran 51 requests (1.70× the estimate) and saved $1.69,
  9 % of the session. Re-read 5K, 8 main requests, 20K left in main. Selective
  policy replay (`baseline --u 4561 --mo 8 --d 19602`): lane when main > 150K
  and item ≥ 20 requests, −14 % over 270 sessions.

*Review* (`/code-review high`). Four findings. One was fixed: the innermost
Horner coefficient was written bare after `*` (`*-0.00027682`), which the
replaced writer never did. Two were skipped: the forward-only path computing
a discarded slope (one division next to two Bessel calls), and three tests
each computing a phase's x on different set-ups. One needed no change: the
3.6e-8 bound is the supremum, checked on a 7e-6-wide grid.

*Generality* (the judge on the seven added and two deleted rows):
- `_BESSEL_SWITCH`, `_I0_SMALL`, `_I1_SMALL`, `_I0_LARGE`, `_I1_LARGE`: holds,
  tier 1 resting on the test that evaluates the written line. The comment
  claimed every x > 0 against a tested (0, 10⁴]. The comment now says the
  tested range. The coefficients match A&S as the judge recalls them, and the
  test bounds them whatever the print says.
- `_LAUE_SPELLING_REL`: holds. What TOPAS itself computes from the new
  spelling is inferred. *Author:* no TOPAS is available here, and WP-1911
  inherits the note.
- `_ARG_SHIFT`: holds, with incomplete evidence. The row did not say that it
  also removes numpy's 0/0 slope at x = 0. The evidence now says so. The fp32
  reason (torch-mps) is untested by any CI row. The lane ran it locally.
- `_SABINE_LAUE` (deleted): holds.
- `_PI2` (deleted): holds. No independent reference is given for the guide's
  CaF₂ fraction. *Author:* none exists for this specimen. The GSAS-II tutorial
  publishes no weighed composition. The guide's point is that the fraction is
  undetermined while extinction is free, which a 3.53 wt% esd now says on every
  platform.

*Gotchas.* WP-2043's probe branch `tmp/wp2043-macos-qpa` still exists. It
belongs to that session. The worktree guard refuses heredocs and variables in
paths, so probe scripts went to the scratchpad by the Write tool. A new git
branch on GitHub came from the git-data API (`gh api .../git/refs`), because
this worktree cannot switch branches.

*Forward.* WP-1911 inherits the FullProf fact (its powder extinction is
empirical, so C3 cannot write Sabine) and the untested TOPAS spelling. WP-1944
inherits the QPA guide's new numbers. WP-2037 inherits the two slow tests it
left red on `main`. WP-2043's file exists only on its own
branch, so its notice went to the maintainer instead. This close unblocks the
1.10 cut, and this WP was P1 for a silent wrong answer, so a release is owed at
once. That release is WP-2043.

Next: the maintainer reviews and merges this PR, then WP-2043 cuts 1.10 on top
of it. Nothing in this WP remains.

- **2026-10-24** — created by WP-2043's session at the maintainer's ask: a
  stub for option 1 that checks the other programs and the paper first. No
  open WP owns the function: of the open WPs naming Sabine or the Laue
  factor, 1944 owns which phases a plan frees, 1911 the foreign writers'
  coverage and 1327 the magnetic Laue orbit. Filed against `origin/main`
  at `377c5724`. Next: the paper, then the survey.
