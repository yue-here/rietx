# WP-2154 — a holder offset shared across a joint fit

Milestone: parametric · Status: ✅ 2026-11-22 — the series recipe measured, tested and in the guide, with no source change (PR #1782)
Depends on: 2103 soft (its joint `tie`, only if the expression route fails; it did not)

## Goal

A joint fit over several patterns shares a sample holder's cell and its height offset
from the sample, while each pattern keeps its own sample height and its own holder line
areas and widths. The recipe is measured on a synthetic series and written in the manual.

## Context

**What exists.** WP-2108 fits a sample holder beside a sample in one pattern with nothing
new in the package (`docs/docs/guides/holder_cell.md`, `examples/guides/holder_cell.py`,
`tests/test_holder_cell.py`). Each holder reflection is a declared peak (`PeakComponent`
in `Instrument.extra_components`). Its centre is a formula, set by
`Refinement.tie(path, expression=...)`, of four variables: the holder cell `a_holder`,
the height offset `offset`, the zero shift `zero` and the sample height `height`. The
zero shift and the specimen displacement are tied to the last two. The formula is Bragg's
law for Kα1 plus the zero shift, minus (2s/R)·cosθ at the holder's height s = height +
offset, with R the goniometer radius. Over 12 seeds of fluorapatite over a textured
aluminium holder it recovered both cells, the coordinates and the offset (mean z of the
offset +0.25, of the holder cell −0.24). The holder fitted as an aluminium phase missed
its own cell by about 30 esd.

**Why a series.** Stinton & Evans (2007, § 4.1, example 1) share the height offset
across data sets, and the holder is there to give the sample height. The milestone's
row ([parametric.md](../milestones/parametric.md), the 2108 row) asks for a synthetic
series and records "a joint fit sharing the offset was not tried".

**The open question.** `MultiHistogramRefinement` has no `tie`, which WP-2103 would give
it. It takes `variables=` and `ParametricEquation(basis="expression")`, whose target may
be any table path. WP-2101 measured the same shape for WO₃'s overall B: a formula
equation per site with `vars.b` in `SharingMap(per_histogram=[...])` gave one refined B
per pattern (WP-2103's `### Inherited`). So the joint form is likely this, unmeasured:

- `variables=` declares `a_holder`, `offset`, `zero` and `height`.
- `SharingMap(per_histogram=["vars.height", ...])` keeps the sample height per pattern.
  Whether the zero shift is per pattern is the fixture's choice; say which.
- One expression equation per holder line sets its centre, and two more set
  `instrument.zero_shift` and `instrument.geometry.sample_displacement` from the variables.
- Line areas and widths are per pattern.
- The plan edits of the single-fit recipe carry over: no preset frees a `vars.*` column,
  and the holder stage comes before the zero stage (2108's gotchas).

If an equation cannot target a declared peak's centre or the displacement in a joint fit,
say what refused it, and put the case in WP-2103's `### Inherited` as a customer of its
tie.

**Tier.** No rule is added. This is a recipe over existing machinery.

## Non-goals

- A holder as a Pawley phase (2108's other route, struck there).
- Phase fractions for the holder.
- A new verb on a joint fit, which is WP-2103's.

## Tasks

- [x] A synthetic series: the 2108 fixture over five patterns, one holder cell and one
  offset, a sample height per pattern. Fit it jointly by the route above.
- [x] Measure over 12 pinned seeds: the mean z-score of the truth for both cells, the
  sample's coordinates, the offset and each height; their spread; GoF; time per fit as a
  range. Compare the offset's esd with the single-pattern recipe's.
- [x] A slow test beside `tests/test_holder_cell.py`, holding the milestone's bar.
- [x] A section in `docs/docs/guides/holder_cell.md` with its script under
  `examples/guides/`, every quoted number asserted.
- [x] The milestone's 2108 row, rewritten to say what the series measured.
- [x] Skill: none expected, since `holder.md` reaches the guide. Say so, or add the row.
  None added: the skill routes to no single guide, and the manual's `holder.md` links
  `holder_cell.md`, whose new section is the recipe.

## Acceptance

Over 12 pinned seeds of the synthetic series, both cells, the sample's structure and the
shared offset have a mean z-score under 0.5 in size.

```sh
.venv/bin/python -m pytest tests/test_holder_cell.py tests/test_examples.py -k holder
.venv/bin/python -m ruff check src tests examples
```

## References

- Stinton, G. W. & Evans, J. S. O. (2007). *J. Appl. Cryst.* 40, 87-95, § 4.1.
- WP-2108 (the single-pattern recipe), WP-2103 (a joint fit's verbs), WP-2101 (a per-pattern
  variable through a formula equation), WP-1103 (declared peaks).

## Handover log

- **2026-11-22** — Closed by a ghostshift runner, PR #1782. A joint fit over five
  patterns can now share a sample holder's cell and its height offset while each pattern
  keeps its own specimen height, and the manual shows how. Nothing in the package had to
  change: the route the Context guessed works as written. Five patterns measure the offset
  and the holder's cell to about 0.45 of one pattern's esd, close to 1/√5, and every
  value lands near the truth over twelve noise seeds. WP-2103's joint `tie` is not
  needed for this recipe.
  - *Done.* `tests/test_holder_cell.py` gains `_with_lines`, `HEIGHTS`, `_joint` and the
    slow test `test_a_joint_fit_shares_the_holder_cell_and_offset_across_heights` (its
    own `xdist_group("holder-series")`, so it runs apart from the single-pattern fixture).
    `examples/guides/holder_cell.py` gains a `series` block with every printed number
    asserted, and `docs/docs/guides/holder_cell.md` a section "Share the holder across a
    series"; its Limitations line saying a series was not shown is gone. The milestone's
    2108 row says what the series measured. The skill gains no row (task 6 says why).
  - *Fixture.* The 2108 pattern at five specimen heights (0.040, −0.030, 0.090, 0.010,
    −0.060 mm), one holder cell 4.0495 Å, offset −0.120 mm, zero 0.012°. Pattern k of
    seed s uses noise seed 10·s + k, s in 100-111. The zero shift is **shared** (one
    variable read by every pattern's zero-shift equation), as is the instrument profile
    (`shared=["instrument.profile.*"]`). Background, scale, and each line's area, width
    and η are per pattern by default.
  - *Measured* (macOS arm64, `[dev]`, load average about 30 from other runners). Over
    12 seeds, mean z of the truth (standard deviation of z): fluorapatite a −0.25 (0.61),
    c −0.27 (0.62), mean coordinate −0.21 (0.28), holder cell −0.32 (0.63), offset +0.26
    (0.58), zero −0.22 (0.63), each height −0.21 to −0.22 (0.63). Coordinate RMS z 0.85
    on average, 1.06 at most. GoF 0.989-1.010. Every fit converged. Joint esd against
    pattern 0 fitted alone by the 2108 recipe, per seed: offset 0.42-0.49 (0.00099 mm
    against 0.0022 mm on average), height 0.44-0.46, holder cell 0.45 on average.
    Wall clock per fit, under that load: joint 17-23 s, single 3-5 s. A noise-free series
    puts the systematic error at +0.00008 mm on the offset with the Kα doublet, and
    −0.00001 mm with Kα1 alone: 0.08 and 0.01 of the noisy joint esd. The doublet's part is
    the declared line's Kα2 placement the guide's Limitations already name. A first look at
    six seeds gave the offset a mean z of +0.50; at twelve it is +0.26, so that was scatter.
    Gates: the new test passed alone in 207 s; `tests/test_examples.py -k holder` 2 passed;
    the guide script runs clean in 40-95 s under load.
  - *Gotchas.* Declare the four variables `vary=False`. A stage reaching an equation's
    target frees every variable it names, so the holder stage would otherwise free
    `zero` and `height` with the lines. Only `height` is in `per_histogram`. The fit
    reports `FLAT_DIRECTION` for zero against each height and for every pair of heights
    (15 rows on five patterns). The heights' errors are all one common mode with the zero
    (correlation of their z-scores with the zero's 0.9997 over 12 seeds). Each line's η
    lands on its floor of 0 (`FLOOR_HIT`), as the simulated lines are pure Gaussian.
    The joint result carries no `EXTRA_PEAK_ON_REFLECTION`, which the single fit does.
    That is how a joint fit's diagnostics stand today, not a finding of this WP.
  - *Review* (`/code-review high --fix`: no bugs, four nits, none applied). (1) The
    measurements belong in this entry, now here. (2) The 0.42-0.49 esd ratio is a
    one-off measurement, not held by the slow test, which has no single-pattern fit on
    the same seeds; the example asserts the ratio on its own seed (0.4-0.5). (3) The
    example inherits `source.dispersion` where the root rule wants it declared. The 2108
    sections of the same script inherit it too, and declaring it would re-pin every number
    on the page, so the series follows the script's convention. (4) The heights print to
    4 decimals on a flat direction and were pinned on darwin/arm64. The 2108 height is
    pinned the same way and passes Linux CI; if the Linux guide leg splits, quote 3 decimals.
  - *Settled by Claude* (none brought to the maintainer): the zero shift and the profile
    are shared across the series, under the 2026-11-03 ruling that a series holds the
    instrument fixed (alternative: per pattern, the default); the variables are
    `vary=False` and freed by named stages, under 2108's plan edits (alternative:
    `vary=True` and freed by target-reaching stages); the series test is its own xdist
    group, under `tests/CLAUDE.md`'s "a group whose members share no fixture splits for
    free"; no skill row.
  - *Next.* None in this WP. The parametric milestone's 2108 row is now met on single
    patterns and on a series.
- **2026-11-22** — Filed by the session closing WP-2107, from WP-2108's "not tried" and
  its milestone row. Not folded into WP-2103: that WP adds verbs to a joint fit, and this
  recipe likely needs none, since WP-2101 measured the per-pattern-variable shape without
  a tie. It depends on 2103 only if that measurement fails here. Premises checked on main
  f590981ab. Next: the synthetic series.
