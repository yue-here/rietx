# WP-2020 — Opt-in sets of bounds and defaults for a scenario, tested on the datasets they name

Milestone: generality · Status: ⬜
Track: The registry and the guard
Depends on: —
Priority: P2 2026-10-21 — the maintainer's concept, raised while declining a default backstop in WP-2002; it gives a demoted default somewhere to go other than away

## Goal

A caller can load a named set of bounds, starting values and plan settings written for one
kind of measurement, and the result says which set it ran under. A set is tested on fewer
datasets than a package default needs, and says which ones. The package defaults stay what
every competent refiner would accept; the scenario-specific choices live in sets the caller
opts into.

## Context

**The maintainer's words** (2026-10-21, answering WP-2002's sixth round, Q6 on a backstop
for a runaway instrument width): "No need to bound these values. I would like callers to
set the bounds themselves. Can you consider a new concept: opt-in sets of bounds and
defaults for particular scenarios. Instead of setting overfit defaults by default (ahem),
we load sets of defaults that have been tested on smaller numbers of datasets. This would
be like sharing a topas .inp, but more flexible or usable."

**Why it fits the generality milestone.** A tier-3 default must hold on three unrelated
dataset families, or it is demoted (`docs/milestones/generality.md` § The rule). Many
defaults hold on one family and serve it well: they were built for an in-situ series, a
nanocrystalline specimen or one instrument. Demotion today means removal. A set gives such
a choice a home where it is still one call away, and where its evidence travels with it.

**Candidates already in view** (each to be checked against the tree before it is used):

- The instrument-width backstop the maintainer declined as a default (WP-2002, Q6), and the
  chosen TCHZ width ceilings removed on 2026-10-21 (1 for U, W, X, Y; 0.5 for V).
- The sample-width backstops `params.vector.strain_cap` and `size_cap`, which exist because
  of a 248-pattern CuO→Cu series (issue #140). WP-2002 left them in place; whether they
  belong in a series set is this WP's question.
- The 2 nm crystallite-size floor removed by WP-2002's B8 ruling.
- The tier-3 rows WP-2017's second pass demotes, as it demotes them.

**What exists to build on.** `PLAN_PRESETS` and `PLAN_INFO` (plans only), the instrument
constructors (`Instrument.bragg_brentano` and the others), `save_instrument_profile` and
`load_instrument_profile`, a project directory (`.rex`), and the PowderLine recipe reader
(WP-1306), which reads a whole refinement from one file.

**Practice, recalled and not checked this session.** TOPAS users share `.inp` files and
include files of macros. GSAS-II shares instrument parameter files (`.instprm`) and copies
refinement flags between histograms. FullProf users start from example `.pcr` files.
Profex ships BGMN device files and structure templates. The survey task below checks each
of the seven programs rietx-bench runs, from source or manual.

## Non-goals

- Changing a package default. Each default is decided by its own audit row.
- Building before the maintainer rules on the design brief.

## Tasks

- [ ] Survey the seven programs (GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD,
      EasyDiffraction): how a user shares or loads a set of starting values, bounds and
      refinement settings, what such a file may contain, and how a result records it.
      Checked from source or manual, as `docs/practice.md` was.
- [ ] Inventory the candidate settings from `_audit.ROWS` and the rulings: each with its
      evidence, the scenario it serves, and the datasets it was measured on.
- [ ] A design brief for the maintainer: what a set may contain, where it lives (package
      data, a user directory, a project), how it composes with a caller's own settings and
      which wins, how a result and a history node record it, how its evidence is stated,
      and its name in the field's terms.
- [ ] Build the ruled design, with one set from the inventory and its tests.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

A loaded set changes only what it declares, the result names it, and its file states the
datasets it was tested on.

## References

- `docs/wp/2002-batch/rulings.md` § Sixth round's answers (the maintainer's words).
- `docs/milestones/generality.md` § The rule (tiers and demotion).

## Handover log

- **2026-10-21** — Filed by the WP-2002 session from the maintainer's answer to the sixth round's Q6. Nothing built; the survey is the first task.
