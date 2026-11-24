# WP-2301 — The typical temperature series: one route, a preset, and a Switching page

Milestone: series · Status: ⬜
Depends on: 2300 (the declaration a preset bundles)
Priority: P3 2026-11-22 — a feature the series milestone was opened for (P2), down a rung: waits on WP-2300's declaration and on the maintainer's naming of the preset

## Goal

The skill, the guide and the manual give one route for the typical temperature series: an
instrument calibrated once and held, with each phase's widths left free. A named preset
bundles that route's declarations, and a page in the manual's Switching tab takes a user
from another program's sequential mode to a first series.

## Context

**The rulings.** [`../milestones/series.md`](../milestones/series.md) is the authority.

- § Ruled after the open (2026-11-16, "keep today's default"): a series call with no plan
  keeps refining the zero shift, five profile terms, the background, the scale and the cell
  on every pattern. "The typical temperature series, with a calibrated instrument held, is a
  named preset and a skill recipe that a caller opts into."
- Rule 4 (accepted 2026-11-16): rietx makes no series strategy choices. "A named preset may
  bundle rule 1's declarations for a common experiment, and it does nothing else."
- § The order: "The default is ruled, so a preset for the typical temperature series can be
  written. The documentation for a user arriving from another program's sequential mode is
  written with rule 1."
- § Acceptance, "The documentation agrees with itself": the skill, the guide and the manual
  give one route for the typical temperature series; each skill trap names a source outside
  rietx's own runs; a page in the manual's Switching tab takes a user from another program's
  sequential mode to a first series.
- § Scope: the maintainer's typical experiment is a specimen in a fixed position under fixed
  instrument conditions, with changes from the environment or the sample. The most common
  case is a temperature series on a laboratory or synchrotron instrument.

**Where the documentation disagrees** (read 2026-11-22 on `f590981ab`). The skill's
`references/series.md` opens with `plan="lab_sample_refine"` and says to hold the instrument
after calibrating it once. The guide `examples/guides/series.py` runs
`plan="mccusker_default"`, and the manual's `guides/series.md` includes it. No Switching page
is about series. `switching/gsas2.md` § A sequential refinement is a chain maps GSAS-II's
sequential controls to `refine_sequential`, and `switching/topas.md` mentions a series of
files sharing a `prm`.

**What the route must keep free** (WP-2081 § Context, the real ramp). On the CuCr₂O₄ ramp of
17 APS 11-BM patterns, routes that held every width put the b/c transition near 60 K, near
230 K or nowhere, against about 130 K in the paper. Holding the instrument and freeing the
sample widths (`lab_sample_refine`) closed between 111 and 123 K, as the default did. The
ramp is development data, so it can fail a route and cannot prove one. The milestone record
settled that no skill line states the width trap, since no outside source tests it
(2026-11-21). So the preset frees the sample widths, and the evidence for that stays in
WP-2081.

**Open for the maintainer: the preset's name.** It is on the main user surface and the field
has no standard term for it. A session does not pick it. What it bundles depends on WP-2300's
declaration (rule 4), and where it lives (a `PLAN_PRESETS` entry beside the nine, or a
series-level bundle of declarations) follows from WP-2300's vocabulary ruling. Today's
`lab_sample_refine` is the nearest preset. Its `PLAN_INFO` title says lab, and on a capillary
it frees no setup path because displacement is locked there (WP-2081 § The crux).

**Practice** (`docs/practice.md` § Sequential refinement, "Parameters the setup fixes" and
"How a person works a series"). Every program surveyed keeps a fixed parameter fixed across a
series, and "refine on the first pattern, then freeze" is a manual step in each (inferred).
No program ships a named preset for a temperature series (not checked beyond the survey).

**Tier.** A preset is a caller's opt-in that bundles declarations, so it adds no default.
Its row is `caller` while no default path selects it.

**Related.** WP-2300 (the declaration, hard dependency); WP-2081 (the measurements);
WP-2015 (the declared geometry picks the single-fit plan); WP-1317 (the series view, in
gui-overhaul).

## Non-goals

- Changing the series default (ruled to stay, 2026-11-16).
- Choosing which patterns calibrate: rule 4 leaves it to the caller, and the skill says how.
- A width-trap skill line (settled 2026-11-21, milestone record).

## Tasks

- [ ] The maintainer's name for the preset, recorded here with his words.
- [ ] The preset, bundling WP-2300's declarations: the instrument's setup paths fixed, the
      scale, cell, background and sample widths per pattern. Its `help.py` entry and audit row.
- [ ] One route: the guide `examples/guides/series.py` and the manual's `guides/series.md`
      move to it, and the skill's `references/series.md` names the preset.
- [ ] The Switching page: from GSAS-II's, TOPAS's and FullProf's sequential modes to a first
      series, written with WP-2300's vocabulary; `switching/index.md` links it; the gsas2
      page's sequential section points to it rather than repeating it.
- [ ] Tests (the preset's route on the synthetic LaB₆ ramp; the CuCr₂O₄ ramp's closure
      between 111 and 135 K, the milestone's real-ramp row) + obs/calc/diff PNGs to
      `tests/output/`.
- [ ] Skill: the routing row for the typical temperature series names the preset.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_examples.py tests/test_manual_api.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- [`../milestones/series.md`](../milestones/series.md) § Scope, § The rules (4), § Ruled after
  the open, § Acceptance.
- `docs/wp/2081-batch/measure_real_ramp.py` (`--report` reprints the saved numbers).
- Suchomel, M. R. et al. (2012), the CuCr₂O₄ ramp's reference (`tests/data/README.md`).

## Handover log

- **2026-11-22** — created (a ghostshift runner, in WP-2081's session). The maintainer ruled
  on 2026-11-16 that the typical temperature series is a named preset and a skill recipe, and
  the milestone's acceptance asks one documented route and a Switching page. No open WP owned
  them: WP-2081 was the discussion and WP-2300 owns the declaration a preset bundles. The
  preset, the route and the page share one dependency (WP-2300's vocabulary) and one reader,
  so they are one WP. Facts above checked on `f590981ab`.

  *Next:* the preset's name, put to the maintainer with WP-2300's vocabulary question.
