# WP-1340 — QPA on a molar basis, and the basis travels with the number

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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
- [ ] Decide volume fraction in or out, and say which in the handover.
- [x] Optional: a caller-declared `z` per phase (`Phase.formula_units`).
- [x] Tests: the LaFeO₃ / La₀.₆Sr₀.₄FeO₃ pair asserts 47.8 / 52.2 and that the
      naive route is not what ships; a mixed table withholds the formula-unit
      column and names the phase.
- [ ] Skill: the QPA row in `references/diagnostics.md` and the reading rule
      in the body or `references/judging.md` — that a mol % column summing to
      100 % is no evidence its basis is uniform.

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

- **2026-09-03** — created, from the 2026-09-03 issue triage (issue #235).
  Given its own WP rather than folded into 1320 because it adds a diagnostic
  code and a basis field, and because the two WPs answer different questions
  about the same number.
