# WP-2117 — a recipe ties the axial pair instead of holding H/L

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2012 (PR #1422 lands the hold this replaces)
Priority: P4 2026-11-05 — was P3: nothing can start, because no committed recipe flags axial divergence, and the evidence below needs one; it lifts when such a file is found

## Goal

A PowderLine (GSAS-II) recipe that flags `SH/L` for refinement frees one number, as GSAS-II does: `axial_hl`
tied to `axial_sl`, so a refined combined value compares directly with the one GSAS-II refines.

## Context

**Source.** Issue #1426. A recipe states axial divergence as one combined `SH/L` with one refine flag. rietx
models it as two ratios, `axial_sl` and `axial_hl`, and the FCJ profile is exactly symmetric under their swap.
So freeing both lets a fit report either assignment.

**What PR #1422 does.** `read_recipe` splits `SH/L` evenly, and where the recipe flags it, frees only
`axial_sl`, holding `axial_hl` at its half. `RECIPE_CONVENTION_ASSUMED` says which ratio was freed. No committed
recipe flags `axial_divergence`, so no fixture's fit moved. On main at `541f0daf7`, `io/recipe.py` lines 647-662
still set both ratios and apply the flag to both. The tie is the follow-up that PR files.

**Why the tie is the more proper model.** It is GSAS-II's own model: one combined number moving as a whole. The
generality judge rated the hold "weak" against the tie on WP-2012 for that reason. `io/CLAUDE.md` § Project writers
prefers freeing over holding where a flag is narrower than the model. Under the hold the refined combined value is
`axial_sl + SH/L / 2`, part refined and part frozen at the recipe's start. Under the tie it is `2 · axial_sl`.

**What it needs.**
- **A tie channel on `Recipe`.** `Recipe` carries `plan`, `limits` and `diagnostics`, and `RefinementPlan` has no tie
  field, so the reader cannot hand a tie to the caller. `Refinement.tie_equal` exists. The missing piece is a field
  the reader can fill and `Recipe`'s documented call sequence applies, or a plan-level tie.
- **The FCJ corner.** A tied pair stays on s = h for the whole fit, where the FCJ quadrature is non-differentiable
  across the diagonal (`docs/docs/theory/method.md` § The FCJ corner at s = h). Along the diagonal the profile depends
  on one variable. Check the tied direction's analytic column against a finite difference there first. An exact
  check is needed, so read the root CLAUDE.md on a branch's oracle.
- **Evidence between the two models.** Fit one recipe with the flag set under the hold and under the tie, and compare
  each with GSAS-II's own refined `SH/L` for that recipe. That needs a recipe file that flags axial divergence, and
  none is committed.

**What changes when it lands:** the `RECIPE_CONVENTION_ASSUMED` text, its `help.py` entry, the recipe reference chapter,
the convention row in `tests/data/README.md`, and WP-2012's four tests in `tests/test_recipe.py`. The skill row in
`docs/skill/rietx/references/diagnostics-projects.md` and `help.py` do not contradict each other today (the issue checks
this). When the tie lands, the row's second sentence should say what the flag frees.

**Tier.** Adopting the program's own model is named practice: tier 2, GSAS-II, checked against its output.

## Non-goals

- The lab presets, which free S/L alone at a declared slit height (the 2026-11-01 ruling).

## Tasks

- [ ] Find or write a recipe that flags axial divergence, with GSAS-II's own refined `SH/L` for it.
- [ ] Check the tied direction's column at s = h.
- [ ] The tie channel on `Recipe`, applied by its documented call sequence.
- [ ] `read_recipe` ties the pair, and the texts above follow.
- [ ] Tests: the four WP-2012 tests, and the comparison with GSAS-II.
- [ ] Skill: the `RECIPE_CONVENTION_ASSUMED` row's second sentence.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_recipe.py tests/test_cross_backend.py
```

## References

- Issue #1426; WP-2012; PR #1422.
- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.* 27, 892-900.

## Handover log

- **2026-11-05** — created, from the 2026-11-05 issue triage (issue #1426). Checked against the tree at `541f0daf7` and PR #1422's WP file: `Recipe` has no tie field, and no committed recipe was found to flag axial divergence, as the issue says; no open WP owns it: WP-2012 closes in #1422. Next: a recipe file; nothing else can start.
