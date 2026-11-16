# WP-1340 — QPA on a molar basis, and the basis travels with the number

Milestone: unscheduled · Status: 🔄 2026-11-16 — every task landed, in review as PR #1598; the schema additions and the new code wait on the maintainer
Track: Render what the fit already knows
Depends on: — (1320 soft: both touch `PhaseQuantity` and add a diagnostic row)
Priority: P3 2026-09-23 — a second basis for a number QPA already reports

## Goal

A quantitative phase analysis reports a mole fraction as well as a weight
fraction, on a basis stated beside the number — and abstains, by name, where
the formula-unit basis is not established for every phase in the analysis.

## Context

From issue #235. `PhaseQuantity` reports `weight_fraction` and nothing molar,
while most of the chemistry a user brings is molar: reaction stoichiometry,
conversion and extent of reaction, phase-diagram tie lines, solid-solution
site balance. Getting to one today means redoing the arithmetic outside rietx.

Everything needed is already computed. `ZMV` carries `cell_mass`,
`cell_volume`, `zmv`, `z` and `molar_mass` (`optimize/qpa.py:86`), and
`PhaseQuantity` surfaces all five (`schemas/results.py:434`; line numbers
re-read 2026-11-16 at `bc77a934e`).

**Why this is not a one-line derivation, which is the whole content of the
WP.** The obvious form is `x_p ∝ W_p / M_p` using the reported `molar_mass`.
That is **silently wrong for exactly the systems where mol % matters most**.
`_formula_units` (`optimize/qpa.py:115`) returns `z = 1` whenever any
occupancy-weighted element count is not within 2 % of a positive integer, and
`molar_mass` then becomes `cell_mass` — the whole cell as one formula unit.
The docstrings say so plainly. Measured on realistic compositions:

```
  4  z   <- CuO, Z=4 (stoichiometric)
  2  z   <- Cu2O, Z=2
  4  z   <- LaFeO3, Z=4
  1  z   <- La0.6Sr0.4FeO3, Z=4 (solid solution)
  1  z   <- ZnCr2O4 with 2% Zn vacancy
```

So a solid solution or a lightly non-stoichiometric phase lands on a
**per-unit-cell** basis while its stoichiometric neighbours are on a
**per-formula-unit** basis, in the same table. For a 50/50 wt %
LaFeO₃ + La₀.₆Sr₀.₄FeO₃ mixture:

| | LaFeO₃ | La₀.₆Sr₀.₄FeO₃ |
|---|---|---|
| `cell_mass` | 970.993 | 888.937 |
| `z` reported | 4 | **1** |
| `molar_mass` reported | 242.748 | **888.937** |
| `molar_mass` true (Z = 4) | 242.748 | 222.234 |

- true mol %, per formula unit: **47.8 / 52.2**
- naive from reported `molar_mass`: **78.5 / 21.5**
- **error: +30.8 pp**, with nothing raised

Same class as a wt % basis mismatch — one side normalised over a different set
than the other — and **harder to catch**, because unlike a wt % column that
visibly fails to sum to 100 %, a mixed-basis mol % column sums to 100 %
perfectly.

**The escape is that the unit-cell basis is always well defined.** Since
`W_p ∝ S_p · cell_mass_p · V_p`, we have `W_p / cell_mass_p ∝ S_p · V_p` — no
masses at all, just the refined scale and the cell volume, and `cell_mass` /
`cell_volume` are the two quantities the docstring calls unambiguous. So the
proposed shape:

1. **`mole_fraction`**, always populated, on the **unit-cell** basis:
   `n_p ∝ S_p · V_p`, renormalised. Robust for every phase, partial occupancy
   included.
2. **`mole_fraction_formula_unit`**, populated **only when every phase in the
   QPA has a resolved `z`** — no fallback anywhere — because the comparison is
   *between* phases, so one unresolved phase spoils the whole column and not
   just its own row.
3. **`mole_fraction_basis`**, so the basis travels with the number rather than
   being inferred. This is the `weight_fraction` / `weight_fraction_corrected`
   pattern: report alongside, never silently substitute.
4. A **diagnostic** where (2) is withheld, naming the phase that forced it and
   why (refined partial occupancy, solid solution), so a user is told rather
   than left to notice a `None`. `FULLPROF_OCCUPANCY_UNCHECKED` is the closest
   precedent in tone — it says which site could not discriminate rather than
   quietly passing.
5. Separable and optional: let a caller **declare** `z` per phase, which is
   the only way `La0.6Sr0.4FeO3` ever gets a formula-unit mol %, its formula
   unit being something the occupancies cannot express.

**Volume fraction is nearly free alongside** and is what a microstructure or
dilatometry comparison wants: `ZMV.density` exists, so `V_p ∝ W_p / ρ_p`.
Named because it shares all the plumbing; in or out of scope is the WP's call.

Two package rules bear directly. **A derived quantity's esd goes through the
whole covariance, and one that cannot be measured is absent rather than zero**
(WP-1072) — a mole fraction is a derived quantity of the same scales the
weight fractions come from, so its esd is the same J·Cov·Jᵀ question and the
same `None` discipline, and QPA's unmeasured-row rule marks the **whole**
block because W normalises by a sum. And **a declared name is a claim**
(WP-1076): each new field needs its writer named at review, and `None` is the
honest empty state where the fact has no computing authority.

**Whether this needed a WP was asked rather than assumed**, and the reporter's
own reasoning is why it got one: item (4) is a new diagnostic code, and root
CLAUDE.md's rule is that a WP adding a code adds its row — which now means a
row in `references/diagnostics.md`, a file that had **86 B of headroom**
until PR #111 split it (see 1338). That is planned here rather than discovered at the cap. Against that, this adds
no new physics and no new dependency.

### Folded in on arrival (2026-11-16, at `bc77a934e`)

The two inherited entries were checked against `main` and folded here; the
`### Inherited` heading is gone.

- **From 1338 (superseded in part).** `references/diagnostics.md` is no longer
  over its budget: it was split further and now sits at 28 861 B against
  `tests/skill_caps.py`'s 34 600 B budget, so a QPA row there costs no cut.
  `references/judging.md` is the tight one, 34 501 B, **99 B under budget**, so
  this WP's reading rule goes in the diagnostics row and the manual's
  `reference/qpa.md`, not in `judging.md`.
- **From 1320 (superseded in part).** `SCHEMA_VERSION` is 0.61, not 0.33, and
  1320's diagnostic `QPA_FRACTION_UNDETERMINED` was replaced by
  `QPA_FRACTION_RANGE` (B12 3(a), ruled 2026-10-19). `FractionProfile`
  (`schemas/fraction.py`) is still weight fractions only. Whether it reports a
  molar range too is still open; if it does, it converts per grid point from
  each refit's own QPA row, never the range afterwards (W is nonlinear in
  every scale).

## Non-goals

- The multi-modal fraction and the profile-likelihood limit — 1320. That WP
  asks *how well fixed* a fraction is; this one asks *in what units*.
- Amorphous content and the crystalline-basis caveat, beyond stating it.
- Changing `_formula_units`' 2 % integrality rule. This WP works with its
  answer and reports when it abstained; retuning it is a separate question.

## Tasks

- [x] `mole_fraction` on the unit-cell basis, from `S_p · V_p`, with its esd
      through the full covariance and `None` where the covariance cannot
      supply one.
- [x] `mole_fraction_formula_unit`, withheld unless **every** phase resolves
      `z`; and `mole_fraction_basis` beside them (landed as
      `PhaseQuantity.z_source`; the handover says why).
- [x] The abstention diagnostic, naming the phase and the reason.
- [x] Decide volume fraction in or out, and say which in the handover (out:
      the 2026-11-16 entry, and issue #1600).
- [x] Optional: a caller-declared `z` per phase (`Phase.formula_units`).
- [x] Tests: the LaFeO₃ / La₀.₆Sr₀.₄FeO₃ pair asserts 47.8 / 52.2 and that the
      naive route is not what ships; a mixed table withholds the formula-unit
      column and names the phase.
- [x] Skill: the QPA row in `references/diagnostics.md` and the reading rule
      in the body or `references/judging.md` — that a mol % column summing to
      100 % is no evidence its basis is uniform (the rule went in the row and
      in the manual's `reference/qpa.md` § Mole fractions: `judging.md` is
      99 B under its budget).

## Acceptance

The measured mixture returns the true mol % on both bases where both are
available, and withholds the formula-unit column by name where they are not.

```sh
.venv/bin/python -m pytest tests/test_qpa.py tests/test_skill.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #235. Hill & Howard (1987) / Bish & Howard (1988) for the ZMV
  weight-fraction relation the mole fraction is derived alongside.
- `optimize/qpa.py` docstrings — the `z = 1` fallback and the two quantities
  called unambiguous.

## Handover log

- **2026-11-16** — review fix-ups on PR #1598 (ghostshift runner). The
  per-formula-unit column now also withholds when a phase has a mixed or
  partly occupied site whose counts per cell happen to be whole
  (La0.75Sr0.25FeO3 and La0.5Sr0.5FeO3 in a Z = 4 cell shipped 79.1/20.9 and
  64.1/35.9 for a true 48.6/51.4 and 47.2/52.8). `ZMV.partial_sites` and
  `qpa.partial_occupancy_sites` carry it; two tests pin both rows. The help
  text, suggestion, audit row and manual now say `mole_fraction` counts cells
  and is the mol % only where every cell holds the same number of formula
  units; both mole fractions are on the uncorrected (non-Brindley) basis.
  Left for the maintainer: listed in the PR body.

- **2026-11-16** — all seven tasks landed, in PR #1598 (ghostshift runner).
  A Rietveld fit now reports how many moles of each phase there are, not only
  their weight, and it says which way it counted. Every phase gets a mole
  fraction counted in unit cells, which needs no formula unit and so is always
  a correct count of cells (the chemist's mol % only where every cell holds the
  same number of formula units). A second column counts formula units, the chemist's mol %, and it
  appears only when every phase's formula unit is known. When one phase is a
  solid solution or has a partly empty site, that column is left empty for
  every phase, and an info diagnostic names the phase and its odd counts,
  rather than shipping a column that sums to 100 % on two bases. On the WP's
  50/50 wt % LaFeO₃ + La₀.₆Sr₀.₄FeO₃ mixture, the per-cell column reads the
  true 47.8/52.2, and the naive route (78.5/21.5) is pinned as not what
  ships. A caller can declare a solid solution's formula units to get the
  per-formula-unit column. Volume fraction is out. What a reader receives
  changed: six result fields, one input field and one diagnostic code, all
  waiting on the maintainer's review.

  *Done.*
  - `PhaseQuantity` has new fields:
    - `mole_fraction` and `mole_fraction_stderr`, per unit cell, from S·V;
    - `mole_fraction_formula_unit` and `mole_fraction_formula_unit_stderr`,
      from Z·S·V;
    - `z_source` (`composition`, `declared` or `unresolved`).
  - `QuantitativePhaseAnalysis.formula_unit_withheld` holds the reason the
    second column is absent. `QPA_FORMULA_UNIT_WITHHELD` (info) quotes it, and
    its `where` names the phase.
  - `Phase.formula_units` is the caller's Z. It is read only by QPA, and
    `molar_mass` follows it. It is deliberately not per-pattern-free in a
    joint fit, so starting structures that differ in it are refused.
  - Both esds come from `qpa.mole_fractions`, which is `weight_fractions`
    with V or Z·V in place of Z·M·V. Same J·Cov(S)·Jᵀ, same `None`
    discipline. Each is tested against a finite-difference oracle, the
    per-formula-unit one on LaB₆ + CaF₂ (Z = 1 against Z = 4).
  - `ZMV.z_resolved` and `qpa.unreduced_counts` record when `_formula_units`
    fell back. Its 2 % rule is unchanged (a non-goal).
  - Edge cases:
    - A lone measured phase reads 1.0 on both bases, with no diagnostic.
    - A phase with no mass in its cell (every site empty) gets `None`, not
      0.0. Its cell count rides a blind scale, and it withholds nothing.
    - A negative scale that leaves Σ S·V ≤ 0 makes that basis absent rather
      than raising (WP-1028 §(f)).
  - `help.py` entry, two `_audit` rows (tier 1, ambiguity 1, response info),
    the skill's diagnostics row, `reference/qpa.md` § Mole fractions (with
    the reading rule as a heading), a `Phase.formula_units` row in
    `reference/data.md`, `api.md` regenerated, the GUI help-key fixture, and a
    0.61 schema note.

  *Decisions, with reasons.*
  - **Volume fraction: out.** It is nearly free (V_p ∝ S_p·V_p²). But it
    brings its own basis question: crystalline solid at the X-ray density,
    porosity and amorphous content not modelled. That wants its own reader
    rule, and it is one more field for the maintainer to review. Filed in
    #1600 with the recipe.
  - **`mole_fraction_basis` landed as `z_source`.** The basis of each
    column is fixed by its name (per cell, per formula unit). What varied,
    and what nothing recorded before, is where a row's `z` came from, and so
    whether its z = 1 was a formula unit or the whole cell.
  - **The reading rule** ("a mol % column summing to 100 % is no evidence its
    basis is uniform") went in the skill row and the manual, not in
    `judging.md`, which is 99 B under its budget.
  - **`FractionProfile` molar range:** not built (the 1320 note); filed in
    #1600.

  *Measured* (`[dev]` venv on the workstation, Linux x86_64, `-n 8 --dist loadgroup
  -m "not slow"`; the Mac's runs were single files without `-n`):
  - Canary wp1340c at `0502772e1`: 378 passed in 29 s.
  - Fast wp1340f at `0502772e1`: 14855 passed, 280 skipped, 32 xfailed,
    2 failed. Both failures were mine: a stale `help_keys.json` fixture, and
    bold in the manual's register. Both are fixed in `dd0d73690`.
  - Final-tree fast run: wp1340g at `c01b9221c`: 14860 passed, 280 skipped, 32 xfailed, 0 failed, 435 s, 5.9 GB peak, 728 % on 8 cores. That is +3 over wp1340f (the three review tests) with its two failures fixed, so passed+skipped moved by exactly the tests added. The ten added tests cost 0.08 s together in that junit (`tests.added_test_times`), so none joins the slow tail.
  - `tests/test_qpa.py` went from 39 to 49 tests (+10, none skipped).
  - `python -m tests.reader_output` exits 0: unchanged against the
    merge-base. Its fixtures carry no mixed-basis QPA, so the new code shows
    there nowhere.

  *Review.* Not `/code-review` (a runner may not run it), but a read-only
  review agent over the branch diff. It found five things, and four were
  fixed in `c82c80bbe`:
  - a massless phase took a mole fraction;
  - one negative scale could raise from inside QPA;
  - the withheld text was wrong for several phases;
  - there was no esd test with differing Zs.
  The fifth, that the CIF writer ignores a declared Z, is in #1600.

  *Generality* (the judge's verdicts, condensed from its tables; full text in
  the session):
  - `QPA_FORMULA_UNIT_WITHHELD`, code row: **holds** (tier 1, kind 1).
    It cautioned on attention cost, since the code fires on every multi-phase
    fit with a solid solution. What would change the verdict: a count of how
    often it fires on the suite's multi-phase fits.
  - Suggestion row: **holds**. Minor: "and refit" is the only route to the
    declared-Z column.
  - (a) withholding the whole column: **holds**. It added that composition Z
    is the reduced formula (benzene reads z = 24). Now said in the
    docstring and the manual (`d71e309d3`).
  - (b) lone phase reads 1.0: **holds**. Its esd is `None` on the
    definitional path but 0.0 on a plain single-phase fit, as σ(W) already
    was. Filed in #1600.
  - (c) massless phase: **weak** as first written (0.0). Author's answer:
    changed to `None` in `d71e309d3`, the judge's own remedy, with the test
    asserting `z_source`.
  - (d) declared Z: **weak**, because the CIF export still writes the
    composition's Z. Author's answer: the field is the caller's (`caller`
    class), and the CIF reader and writer question is #1600's item 3. It is a
    file-format decision, not this WP's.
  - (e) the skill reading rule: **holds**.

  *Gotchas.*
  - `tests/test_gui_help.py` rewrites `tests/data/gui/help_keys.json` when
    it is stale. On the workstation that left the job tree dirty, and a
    `git checkout --detach` to the next commit failed silently inside a
    chained command. Check the tree's `git log -1` before starting a job.
  - WP-1532's runner edits the same skill references. This branch adds one
    row to `references/diagnostics.md` and regenerates `api.md` for
    `Phase`'s new field. A conflict there is resolved by regenerating
    (`docs/skill/make_api_index.py`, then `rietx skill --install . --copy`).

  *Next.*
  1. The maintainer rules on the schema additions (six result fields, one
     `Phase` field) and the new code, then merges or asks for changes.
  2. If they want it, WP-2073 picks up the export columns from its new
     Inherited entry.
  3. #1600 holds the rest. Its items 3 (CIF Z) and 5 (the definitional-esd
     convention) are the maintainer's calls.

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #235).
  Given its own WP rather than folded into 1320 because it adds a diagnostic
  code and a basis field, and because the two WPs answer different questions
  about the same number.
