# WP-2120 — Where a rigid body turns about: the origin that decorrelates its pose

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (1805 soft: PR #1388 reshapes the turn chart this reads; 1812 soft, the manual paragraph)
Priority: P3 2026-11-06 — a view over the covariance a fit already has; no atom, χ² or atom esd moves with the origin, and a fractional `origin=` point already moves it by hand

## Goal

A caller who quotes a rigid body's origin esds, or wonders why its origin and
rotation are correlated, can ask where the body's pose decorrelates and what
the origin esds would be there, from the fit they already ran. The manual says
when the default origin is fine and when to move it.

## Context

**Source.** Issue #1417 (2026-11-05), a design proposal from the recurring
contributor, measured on rietx `ba3719f06`.

**What the origin is.** A body's origin is the point it turns about.
`body_from_atoms(phase, labels, name, *, origin=None)` puts it at the atoms'
unit-weight centroid; `origin` may also be an atom label or a fractional point
(`crystallography/bodies.py:65`). `add_body(..., centre=True)` shifts the
template to its unit-weight centroid before placing it at `origin`
(`:108`). Moving the origin by d is an exact reparameterisation of the pose: a
turn about P is a turn about C plus a translation, t′ = t − [d]×ω and ω′ = ω.
So χ², the atoms and their esds are unchanged. What moves is the origin's own
esds, the origin–rotation correlations and the conditioning of the 6×6 pose
block. The pose covariance transforms as Σ′ = TΣTᵀ, so the esds at any other
origin follow from one fit without a refit. *Checked against the tree at
`a84379aac`:* both functions and their centroid defaults are as the issue says.

**What the reporter measured** (not reproduced here). One body fitted from the
same start with the origin at seven points, on three patterns. P_opt, the point
minimising the origin–rotation correlation block, agreed to 0.003 Å whichever of
the seven fits it was computed from.

| origin | acridine IX, measured (COD 2242872) | acridine, synthetic neutron | Br-acridine, synthetic X-ray |
|---|---|---|---|
| unit centroid (today's default) | 0.50 Å from P_opt, max\|C\| 0.25 | 0.23 Å, 0.20 | 3.8 Å, 0.59 (condition number 57) |
| centre of mass | 0.49 Å, 0.25 | 0.17 Å, 0.11 | 2.2 Å, 0.54 |
| Z² (X-ray) or b² (neutron) weighted | 0.49 Å, 0.24 | 0.16 Å, 0.08 | 0.2 Å, 0.24 (cond 10) |
| P_opt | 0, 0.09 | 0, 0.04 | 0, 0.17 |

max|C| is the largest origin–rotation correlation. Across the arms χ² agreed to
0.002, atoms to 2.4e-6 Å, atom esds to 5e-5 relative, rotation esds exactly. No
convergence effect was seen. A point 5 Å off the body raised max|C| to 0.72 and
doubled the origin esd. **What a user would see** with today's default on a
molecule with one heavy atom: origin esds larger than they need be and
origin–rotation correlations near 0.6. Nothing fires: `HIGH_CORRELATION`'s
guard is 0.98 (`schemas/plan.CORRELATION_GUARD`). The weight that matters is an
atom's share of the normal matrix, f² or b², and the Br case bears that out.

**The proposal, three parts, default unchanged.**

1. Report P_opt for each general-position body, fractional and Cartesian, with
   its distance from the current origin. A quantity, no threshold, no warning.
   Closed form: the 3-parameter linear least squares min over d of
   ‖Σ_tω − [d]×Σ_ωω‖_F. The reporter's table used min ‖C‖_F on correlations;
   the two points lay 0.007-0.13 Å apart.
2. `origin_weights=` on `body_from_atoms` and `add_body`, with a helper giving
   Z² or b² for a stated radiation.
3. `origin=` accepting a list of labels, for the centroid of a subset such as a
   ring.

A body on a special position is out of scope: its origin is the site (WP-1807).

**A constraint the issue did not meet: the covariance is never serialized.**
`model/geometry.py`'s docstring: it is read off the final Jacobian at fit close,
so a derived esd is measured then or lost. `Refinement.geometry(request)` is the
precedent for an on-demand reading: answered while the last fit's covariance is
live, every esd `None` after an edit, a checkout or a replay (WP-1815). So
"in `report.bodies`" is not a place that exists. No per-body report section is
on main (`report/body_misfit.py` is a separate call). The choice is between a
field built at fit close, beside `result_.geometry`, and an on-demand verb
beside `Refinement.geometry`.

**Practice.** GSAS-II 5.8.4 places a residue body's origin on a chosen reference
atom (`rbRef[0]`, `GSASIIconstrGUI.py:3728`) or, with "molCent", at the
unit-weight centroid (`:3747-3753`); a placed body's origin is an editable point
(`RBObj['Orig']`, `GSASIIphsGUI.py:9574-9714`) (checked). No weighting and no
decorrelation report was seen there; the search was those two files. TOPAS and
FullProf were not checked. In TLS analysis the analogous choice is
Schomaker & Trueblood's (1968) centre of reaction, the origin that makes the
screw tensor symmetric (recall, not checked against the paper). rietx's two
defaults match GSAS-II's two.

**Tier.** Part 1 is physics (an exact reparameterisation and a linear least
squares), reported as a number with its meaning, kind 3 of DESIGN § Rules,
Rule 1. It is reader output, so its wording goes to the maintainer before
merge. Parts 2 and 3 are caller statements and add no judgement.

### Inherited

## Open question for the maintainer

Which of parts 1-3 to build, and where P_opt sits. Triage recommendation
(2026-11-06, a lean): build part 1 as an on-demand reading beside
`Refinement.geometry`, closed form, returning P_opt and the origin esds at
P_opt through Σ′ = TΣTᵀ, so nobody needs to refit to quote them. Decline parts
2 and 3 as arguments for now: `origin=` already takes a fractional point, so a
weighted or subset centroid is three lines of caller arithmetic, which the
manual paragraph (WP-1812) shows. The crux is audience. Only a caller who
quotes origin esds sees any difference, and the reading tells them where to
put the origin directly. What would flip it: an agent or a user tripping over
the hand arithmetic, or a fit where the origin's conditioning slows
convergence.

## Non-goals

- Changing the default origin.
- A body on a special position (WP-1807).
- The turn chart's re-charted esds (WP-2114).

## Tasks

- [ ] The maintainer's answer to the open question, recorded as `Decided YYYY-MM-DD:`.
- [ ] P_opt: the closed form, on the pose block of the live covariance; the
      origin esds at P_opt by Σ′ = TΣTᵀ. Test: refitting with the origin moved
      to P_opt reproduces the predicted esds and correlations.
- [ ] Whatever of parts 2-3 the decision keeps, with `help.py` rows.
- [ ] Reproduce one row of the issue's table (acridine IX, WP-1806's fixture)
      before quoting any number in the manual.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for the acridine fit.
- [ ] Skill: one reference row naming the reading, keyed on "origin esd" in
      the body reference, or none if the manual paragraph carries it; say which
      at handover.

## Acceptance

On the acridine IX fit and a synthetic Br-acridine, P_opt computed from fits
at three different origins agrees to 0.01 Å, and a refit at P_opt gives the
origin esds the reading predicted, to 1 %.

```sh
.venv/bin/python -m pytest tests/test_rigid_body.py -q
.venv/bin/python -m pytest tests/test_docs_consistency.py tests/test_manual_api.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1417, its table and its proposal.
- Schomaker, V. & Trueblood, K. N. (1968). *Acta Cryst.* B24, 63-76 (TLS, the
  centre of reaction).
- `src/rietx/crystallography/bodies.py`, `src/rietx/model/geometry.py`,
  `src/rietx/refine.py` (`Refinement.geometry`).
- WP-1806 (acridine form IX, the measured case's data and fixture).

## Handover log

- **2026-11-06** — created, from the 2026-11-06 issue triage (issue #1417).
  A rigid body's origin choice changes only its own esds and its
  origin–rotation correlations, and the issue measured a heavy atom pulling the
  best origin 3.8 Å from the default. This WP holds the proposal and the
  maintainer's choice of how much of it to build. Checked against the tree at
  `a84379aac`: `body_from_atoms` and `add_body` default to the unit-weight
  centroid as the issue says; the covariance is never serialized, so the
  reading must be built at fit close or answered while the fit is live; no
  per-body report section exists. No open WP owns it: WP-1805 is closing in
  PR #1388 and owns the body's schema and collector, WP-2114 the turn chart's
  esds, WP-1812 the surfaces and the manual, WP-1806 the acridine case. The
  issue's numbers were not reproduced. *Next:* the open question, then task 2.
