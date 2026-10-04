# WP-1542 — a Le Bail background left at its seed

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-03 — a background too low reads as a good Le Bail fit and feeds every structure fit after it; a path few fits run

## Goal

A Le Bail fit whose background sits at a seed that is too low says so, and
the Le Bail call has a stated background protocol that does not need the
person to spot a flat line in a plot.

## Context

**The failure, from a real run** (2026-09-28, the review of `solution case 1`,
private corpus map § 5; WP-1510 has the source). The agent followed SKILL.md
§2 rule 5 and seeded every coefficient of an `auto_background` P-spline at a
low percentile. The pattern carried a broad diffuse hump over several degrees.
The free per-reflection intensities absorbed it, the background stayed at its
seed, and the Lorentzian width term grew to carry the hump's tails (it fell 4×
once the background was corrected). The cell was unaffected, so nothing looked
wrong. Every structure fit after it inherited a background that was too low,
with light-atom Biso at bounds and strong peaks under-predicted, for about two
hours, until the person saw the flat line in a plot.

**What worked** was a SNIP estimate held fixed under a 4-term Chebyshev: Le
Bail Rwp fell to 0.74× its first value. A fully free background went the other
way (`BACKGROUND_ABSORPTION`, R² 0.70 against the scale). The agent wrote its
own SNIP although `rietx.background.snip` ships, and the skill names neither it
nor this failure.

**Why nothing fired.** Root CLAUDE.md § Background flexibility: a background
able to imitate the peaks is measured (`background_absorption`), and the
too-stiff side has no guard. Under Le Bail the intensities are free, so a hump
the background cannot reach goes into them rather than into the residual. The
tell named in WP-1323's review is a width term that grows while the background
sits at its seed.

**Why it is not WP-1323's.** That WP's stop rule watches Rwp across passes, and
this failure lowers Rwp. WP-1323 shipped in 1.6.0 and closed with this filed
here (2026-10-03, at the maintainer's request).

## Non-goals

- The alternation's stop rule and keep-best (WP-1323, shipped).
- A too-flexible background, which `BACKGROUND_ABSORPTION` already measures.

## Tasks

- [ ] Reproduce on a fixture the tree can hold: a synthetic pattern with a
      broad hump under the peaks, Le Bail from a low-percentile seed. Record
      the background's movement from its seed and the width terms per pass.
- [ ] Name the test for "the background never left its seed while a width
      grew", with where its threshold comes from (measured here or quoted).
- [ ] A finding that names it, on the Le Bail path at least.
- [ ] The protocol: whether the Le Bail call should start from a SNIP estimate
      held under a low-order Chebyshev, as a default or as the skill's rule.
      Measure both on the fixture before choosing.
- [ ] Skill: SKILL.md §2 rule 5 and `references/judging.md` name
      `rietx.background.snip` and this failure.
- [ ] Tests, with obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_lebail_alternation.py tests/test_background_auto.py tests/test_skill.py
.venv/bin/python -m ruff check src tests examples
```

On the hump fixture, the low-seed Le Bail fit reports the finding, and the
protocol's fit leaves the hump in the background, with the width terms
within their no-hump values.

## References

- WP-1323 (the alternation; this was its Inherited entry), WP-1055
  (`FitReport.background`), WP-1454 (λ against the data).
- Ryan, C. G. et al. (1988). *Nucl. Instrum. Meth.* B34, 396 — SNIP, as
  `rietx.background.estimators` cites it.

## Handover log

- **2026-10-03** — filed from WP-1323's Inherited entry when 1323 closed. No
  open WP owns a too-stiff background: the open rows of the index carry no
  Le Bail or background protocol, and 1530's held background is a TOPAS
  reader's. *Next:* task 1.
