# WP-2020 — Opt-in sets of bounds and defaults for a scenario, tested on the datasets they name

Milestone: generality · Status: 🔄 2026-11-15 — claimed by @yue-here
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

*Superseded in part 2026-11-15.* The survey task replaced this recall with a checked section,
`docs/practice.md` § A named set of starting values, limits and refine flags. The recall
held. The survey adds that GSAS-II's `.instprm` carries values and no refine flags, and that
no program found records in its result which set it loaded.

## Findings: the inventory (2026-11-15)

Read from `rietx._audit.ROWS` on `origin/main` at `0f14ac25d`, and from
`docs/wp/2002-batch/rulings.md`. The table holds 1344 rows, 165 of them at tier 3
(15 actions, 14 codes, 111 constants, 20 defaults, 5 suggestion sites). A set holds what a
caller sets for one kind of measurement: limits, starting values and plan settings (this
WP's Goal). So the inventory asks of each candidate whether a set could hold it, what
evidence it has, and which datasets that evidence came from.

**The four candidates the Context named, checked against the tree.**

| Candidate | In the tree now | Evidence, and the datasets it was measured on | Scenario | Could a set hold it? |
|---|---|---|---|---|
| TCHZ width ceilings, 1 on U, W, X, Y and 0.5 on V | removed 2026-10-21 (sixth round, Q5). `TCHZ_CEILING_DEG` = 180 is left, a tier-3 setting for TRF's step scaling, four orders over any measured line | no measurement chose 1 or 0.5. Removing them moved one fit, CPD brucite with Stephens strain under TRF: Rwp 0.17877 to 0.17891 | weak patterns and series chains, by the ruling's argument | yes, as four limits. No dataset shows they help |
| A backstop for a runaway instrument width (sixth round, Q6 (a)) | never built; declined | an argument from the sample-width backstop; no runaway instrument width has been measured | series chains | yes, as limits. Untested |
| 2 nm crystallite-size floor | removed 2026-10-19 (B8) | one private archive of 606 TOPAS refinements. When it bound, `BOUND_HIT` reported it | nanocrystalline specimens. Below a few nanometres the Bragg-peak model itself fails, and `SIZE_UNUSUALLY_SMALL` now says so | yes, as a lower limit. One archive |
| `strain_cap`, `size_cap` (`params/vector.py:848` and after) | kept, and now tier 1: `STRAIN_CAP_RANGE_FRACTION` = 1.0 and `SIZE_CAP_RANGE_FRACTION` = 1.0, on the arithmetic that a line wider than the scan carries no information | issue #140: a 248-pattern CuO to Cu series, where Cu's `lor_strain` reached 1.1e5 and a real 16 wt % phase fell below 1 wt % | every fit | not as the WP filed it. A tier-1 default stays a package default under the generality rule (consent line in the handover entry) |
| WP-2017's demotions | none yet. WP-2017's log of 2026-11-05 reads "No demotion"; 18 of its groups are open | none | none | nothing to hold yet |

**What else is scenario-specific today, and what already carries it.**

| Setting | Tier | Evidence and datasets | Carried today by |
|---|---|---|---|
| TCHZ starting values u, v, w, x, y (`ProfileTCHZ` defaults) | 3 | start-invariance on LaB6; NAC lost its phase from w = x = 1e-2; FAP's GSAS protocol holds x | an instrument profile file, which stores calibrated values in their place |
| Beam polarisation K = 0.5 (`Source.polarization`) | 3 | a wrong K moved Biso by 12 σ at near-unchanged Rwp (WP-1311); a monochromated lab beam or a synchrotron sits near 0.99 | an instrument profile file; the result records K as assumed |
| Refinement order | 3 for `mccusker_default` | McCusker et al. (1999), the order only | nine plan presets: three lab, two magnetic, the default and its structural continuation, a profile-only plan and a Pawley plan |
| Series settings: `carry`, `carry_hkl_intensities`, `reseed`, `on_error`, the series plan | 3, ruled 2026-11-03 | CPD 1a-1h, the thermal ramp, the planted chain | the series verb's own defaults |

**The rest of the tier-3 rows.** A text match over the rows' evidence finds 37 whose evidence
names one family, synthetic problems only, or a second pass owed. Fifteen are solver
settings (13 in `optimize/`, and the two Le Bail convergence tests). Nine are magnetic: six
inside `solve_magnetic`'s ranking and three moment or width floors. Ten are diagnostics: three
codes, one suggestion site, `BOUND_HIT`'s two tests, `MODEL_FAR_FROM_DATA_RWP` and the three
`phase_support_sigma` rows. The last three are `MAX_SITE_ASSIGNMENTS`, `TCHZ_CEILING_DEG`
(above) and `HARMONIC_WEIGHT_SEED`. That seed is the one starting value among the 37, and it
is answer-invariant behind the closing stage. None is a limit, a starting
value or a plan setting that a caller would change for one kind of measurement. The match is a
regex, so the 37 is a lower bound on rows resting on one family.

**What the inventory adds up to.** No setting in the tree needs a new home today. The
removed and declined limits have no measurement showing they help any dataset. What is
scenario-specific already has a carrier: instrument values in an instrument profile file and
refinement order in a plan preset. Two things no rietx carrier holds: which datasets a profile
or preset was tested on, and, in a result, which profile file was loaded. `Provenance` has no
field for the second (`schemas/common.py:1178-1196`); whether a result names its plan preset
was not checked.

## Non-goals

- Changing a package default. Each default is decided by its own audit row.
- Building before the maintainer rules on the design brief.

## Tasks

- [x] Survey the seven programs (GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD,
      EasyDiffraction): how a user shares or loads a set of starting values, bounds and
      refinement settings, what such a file may contain, and how a result records it.
      Checked from source or manual, as `docs/practice.md` was.
- [x] Inventory the candidate settings from `_audit.ROWS` and the rulings: each with its
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
