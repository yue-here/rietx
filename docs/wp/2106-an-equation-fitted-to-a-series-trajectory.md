# WP-2106 — an equation fitted to a series trajectory

Milestone: parametric · Status: 🔄 2026-11-09 — claimed by @mustachefeeling
Depends on: 1964 (the grammar and its derivative rules)
Priority: P2 2026-11-04 — a feature the open milestone was opened for: this is how a GSAS-II user works, and nothing else in the milestone serves them

## Goal

After a series, a user fits an equation in the grammar to a parameter's trajectory,
weighted by its esds, and gets the coefficients with esds. A GSAS-II user's stored
sequential equations come across too.

## Context

The milestone's reader includes GSAS-II users, and every other WP in it builds the TOPAS
route: one joint residual. GSAS-II's practice is different. Its equation is a
python-syntax string fitted to the sequential results table after the refinement, never
in a joint residual (`docs/practice.md`), and it stores those equations with the
sequential results (`SeqParFitEqList`, GSAS-II 5.8.4). Evans also recommends a
sequential fit as a first look. Series practice here agrees: the setup is calibrated and
held, and full refits are unusual.

A clean-context review of the milestone found this gap on 2026-11-04. rietx has no such
fit: `SeriesResult` carries trajectories, and neither `schemas/sequential.py` nor
`guides/equation.md` fits anything to them. Today a user exports the table and writes a
scipy script.

The comparison with a joint fit is the content of the page a user needs.
`guides/equation.md` § When to declare an equation instead of fitting a series already
says why a joint fit is the stronger form. A trajectory's esds are each conditional on
their own pattern, and a chain's trajectory is path-dependent (root CLAUDE.md § Series).
So the result must say it is a fit to a trajectory, and which direction of the chain it
read.

The seams are small. The grammar gives the value and its exact derivative, so the fit
is a few lines of weighted least squares over one equation, and a quarantined pattern
stays out as it does from a median.

The tier of each rule this WP adds ([generality § The rule](../milestones/generality.md#the-rule)),
written 2026-11-09 at the start: the fit is arithmetic (tier 1), weighted least squares with
each coefficient's esd propagated from the trajectory's own. A quarantined pattern is left
out by the chain's own test (`_rejected`, ruled 2026-11-03), and a point with no esd has
no weight, so it is left out too (tier 1); both are named in the result. The esd follows
the package's convention for every refined esd, scaled by χ²/ν (named practice), and the
unscaled one rides beside it, since a refiner who trusts each pattern's esd would not
scale (no unanimity), so neither is chosen and no threshold reads them. No new diagnostic. The
reference is a synthetic ramp with a known truth and the joint fit beside it; there is no
published number, so the fit ships not yet validated.

GSAS-II's licence is its own (`ATTRIBUTION.md`), and this package takes concepts only from
its code. Any reader takes the stored format from a file's contents.

## Non-goals

- A second fitter for the joint case. That is `refine_multi`.
- GSAS-II's external functions in an equation.
- A new diagnostic beyond what the fit's own numbers say.

## Tasks

- [x] The fit: a trajectory, an expression and a `variables` dict in, coefficients with
  esds and χ² out. Name it as a consent item for the maintainer, since it joins the top
  level. (`rx.fit_trajectory` → `rx.TrajectoryFit`; the names are the handover's consent
  item.)
- [x] Which trajectory: `direction="both"` gives two, so say which is read, or fit each.
  Skip quarantined patterns and say so. (Forward by default, `chain="backward"` for the
  other; `TrajectoryFit.skipped` names each point left out.)
- [ ] Measure on a synthetic ramp against the joint fit: do the coefficients agree within
  their combined esds, and how much wider are the esds?
- [ ] GSAS-II's stored equations: read `SeqParFitEqList` from a `.gpx` into this fit's
  input, or refuse by name. Lower GSAS-II's spelling onto the grammar, with a table of
  each rewrite.
- [ ] Manual: `guides/equation.md` beside the joint route, and `switching/gsas2.md`.
- [ ] Skill: the series reference's row.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_sequential.py tests/test_parametric_series.py tests/test_manual_api.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544-549 — GSAS-II.
- WP-1964 (the grammar), WP-1325 (the joint fit), WP-1051 (quarantine).

## Handover log

- **2026-11-04** — Filed from the clean-context review of the milestone. No open WP
  owned it: 1325 and 1964 build the joint route, and 2105 fenced the `.gpx` on a claim
  that proved false. Next: the fit's name, then the fit.
