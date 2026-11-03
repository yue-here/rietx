# WP-1925 — anomalous scattering above 70 keV

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: — (1532 soft: it words the `dispersion = None` workaround in the skill, and this WP removes the need for it above 70 keV)
Priority: P3 2026-10-08 — a workaround covers it: `Source.dispersion = None` declines the correction; the refusal is loud and the named user (a high-energy synchrotron beamline) has one line to type. The workaround is itself unflagged above 70 keV (see Context), which is why the first task is a measurement and the row is not P4

## Goal

A refinement at a photon energy above 70 keV (λ below 0.177 Å) gets f′ and f″
from a table that covers it, or the refusal names the workaround, and the
choice between the two is made on a measurement of what the correction is worth
there.

## Context

From issue #792 (AlemSnyder, 2026-10-06): the tabulated anomalous scattering
factors stop at 70 keV and many synchrotrons run above 130 keV.

`src/rietx/data/f1f2_CromerLiberman.dat` is the DABAX Cromer-Liberman file
trimmed to 3-70 keV. The header says 70 keV is the upper limit of the original
tabulation, so the limit is the source's and not a trim we chose.
`dispersion.dispersion` raises `ValueError` outside the band
(`crystallography/dispersion.py:181-193`): "wavelength ... (E = 130.000 keV) is
outside the tabulated 3-70 keV band for Si".

The reason for the source is in WP-0504 § Data source. Cromer-Liberman is the
crystallographic reference (International Tables Vol. C, GSAS-II), so a
disagreement with another code is attributable. DABAX's `f1f2_Chantler.dat`
must not be bundled (licence purchased by ESRF, NIST SRD 66). WP-0504 also
notes that xraydb carries a CC0 data dedication for its Chantler tables and
was left out for its sqlalchemy dependency, not its licence; whether those
tables can be extracted and bundled the way `mu_McMaster.dat` was is the open
question here.

**The workaround is silent above 70 keV.** `_dispersion_diagnostics`
(`refine.py:7010`) sizes the neglected correction with the same
`dispersion()` lookup and skips an element whose lookup raises, so at 130 keV
with `Source.dispersion = None` a fit returns no `DISPERSION_NEGLECTED` at all
(measured 2026-10-08, 5d1f5f67: diagnostics `CAPILLARY_OFFSET_UNAVAILABLE`,
`PATTERN_UNDERSAMPLED`). Whatever the table decision is, this diagnostic has
to say something for a wavelength the table does not cover, or the refusal
that was loud becomes a decline that is quiet.

What a replacement table must also supply: the absorption edges above 70 keV.
`dispersion.resolve` refuses a line pair that straddles an edge, and K edges
of Z >= 74 (W 69.5, Pt 78.4, Au 80.7, Pb 88.0, Bi 90.5, U 115.6 keV) fall in
the new range (edge energies quoted from memory; check them against
`dispersion.edges` or McMaster before relying on them).

`data/mu_McMaster.dat` already covers 2-120 keV with a photoelectric column,
and WP-0504's optical-theorem cross-check ties f″ to it
(σ_photo = 2·r_e·λ·f″, agreeing with Cromer-Liberman to 0.04-5 % at Cu Kα).
That gives f″ to 120 keV from a file already shipped. It gives no f′ and stops
short of 130 keV, so it is a partial answer.

### Inherited

- **2026-11-03, from [2013](2013-stale-text-in-the-code-the-manual-move-found.md) (its owed question 5) and the maintainer's ruling of 2026-11-02.** The ruling is in § Tasks (task 2). The case that raised it is the PowderLine recipe reader at 74.5 keV (λ 0.16642 Å). There the table refuses every element, and `io/recipe.py` (`_decline_dispersion_off_table`) declines dispersion for the whole model with `RECIPE_DISPERSION_DECLINED` at `info`. For W, whose K edge is 69.5 keV, that drops an f″ of about 3 e at 5 keV above the edge. That figure is the lead's estimate from W's photoabsorption cross-section, not a measurement; this tree's table gives W f′ −4.06 e and f″ 0.64 e at 69 keV, below the edge. Many high-energy beamlines run at 60-100 keV, so the band matters well below #792's 130 keV. Two facts measured 2026-11-03 (macOS arm64, worktree venv `[dev]`, tree `27a58e102`), by a probe outside the tree. (1) **`Dispersion.overrides` already carries a fit above the band, but only when every element is overridden.** On LaB6 at 74.5 keV, `compile_model` refuses with no overrides (naming La), refuses with La alone overridden (naming B, whose f′ and f″ are near zero there), and compiles and fits with both. An override skips the lookup per element in `dispersion.resolve`, and one element left to the table refuses the whole model. (2) **Licences, checked 2026-11-03.** NIST's FFAST page states SRD 66 is "© 1995, 1996, 2001 copyright by the U.S. Secretary of Commerce … All rights reserved", so the Chantler tables are not a public-domain US-government work. xraydb's LICENSE places "the database files, data sources, and documentation files" under CC0 "unless otherwise stated", and also says "some of the datasets here do not have clear statements of copyright or license". So xraydb's CC0 does not clear the Chantler data it repackages. Not checked: xraylib (BSD-3) and the provenance of its anomalous factors, and the Elam, Ravel and Sieber (2002) tables. Until this WP lands, the recipe reader's decline and its message stay as they are (the ruling).

## Non-goals

- A Chantler table taken from DABAX or NIST (licence, above).
- Resonant scattering near an edge (`Dispersion.overrides` already takes
  measured pairs).
- Changing the 3-70 keV numbers: every pinned number there stays bit-identical.

## Tasks

- [ ] Measure what the correction is worth above 70 keV, before choosing a
      source: the same pattern predicted with `dispersion = None` against an
      independent f′/f″ (gemmi's `cromer_liberman` for f″ as WP-0504 used it,
      and the Kissel-Pratt (1990) high-energy limit that FPRIME 3F applies) at
      80, 100 and 130 keV, for Si, Fe, Pb and U. At 60 keV Si the maximum
      intensity moves by 0.04 % between the default and `None` (2026-10-08,
      Debye-Scherrer, 5d1f5f67); the heavy elements are the question.
- [ ] Decide the source. **Ruled by the maintainer 2026-11-02: extend the
      table past 70 keV from a permissively licensed source**, so declining
      above 70 keV with a better message is no longer an option. The choice
      left is which source, recorded with task 1's numbers and a licence
      checked per file: the optical-theorem f″ from McMaster (to 120 keV)
      plus an analytic f′, xraylib, the Elam tables, or another. xraydb's
      Chantler extract is out unless NIST's terms are cleared (Inherited,
      2026-11-03).
- [ ] If a table is added: bundle it with an ATTRIBUTION.md entry and a header
      stating its status (the wheel rule in root CLAUDE.md § Licensing), extend
      the band, keep the 3-70 keV rows bit-identical, and keep the edge guard.
- [ ] Either way: `_dispersion_diagnostics` says "off, and not sizeable at
      this wavelength" for an element outside the table, instead of skipping
      it. If declining, the `ValueError` also names `Source.dispersion = None`,
      so the person who hits it at 130 keV is not sent to the source.
- [ ] Tests (unit/property; the 70 keV boundary both sides; an edge inside the
      new range is refused) + obs/calc/diff PNGs to `tests/output/` if a
      fixture is fitted.
- [ ] Skill: the routing or reference row an agent driving rietx needs from
      this WP, or "none" and why (1532 owns the workaround wording).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_dispersion.py tests/test_acceptance_dispersion.py
.venv/bin/python -m ruff check src tests examples
```

A model at 130 keV either predicts with a stated f′/f″ or raises a message that
names the workaround, and the 3-70 keV tests are unchanged.

## References

- Cromer, D. T. & Liberman, D. (1970), J. Chem. Phys. 53, 1891; Cromer (1983),
  J. Appl. Cryst. 16, 437.
- Kissel, L. & Pratt, R. H. (1990), Acta Cryst. A46, 170-175.
- Chantler, C. T. (1995), J. Phys. Chem. Ref. Data 24, 71 (read before any
  claim is made about its range).
- WP-0504 (the table decision), WP-0305 (McMaster), WP-1532 (skill wording).

## Handover log

- **2026-11-03** — the maintainer ruled the direction: the table is extended
  past 70 keV from a permissively licensed source, and the recipe reader's
  decline stays unchanged until then. WP-2013 asked for a new WP, and this
  one already owns the work, so the ruling was folded here rather than filed
  twice. Task 2 now carries the ruling. The Inherited note carries the
  74.5 keV recipe case and two findings: `Dispersion.overrides` already gets
  a fit past the band when every element is overridden, and NIST's Chantler
  tables are copyrighted, so xraydb's CC0 does not clear them. Recorded in
  PR #1369, a ghostshift runner's branch carrying the 2026-11-02 rulings.

  *Next.* Task 1 is unchanged and comes first: measure what the correction is
  worth at 80, 100 and 130 keV. Then pick a source among the permissive ones.

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #792).
  Checked against the tree at 5d1f5f67: a Si model at 71 and 130 keV
  (Debye-Scherrer, `repro-792.py`) raises "outside the tabulated 3-70 keV
  band"; at 60 and 69 keV it predicts; with `Source.dispersion = None` all
  four energies predict, with no `DISPERSION_NEGLECTED` at 130 keV (the one
  silence). No open WP owns it: WP-1532 words
  the 70 keV workaround in the skill and does not touch the table, and
  WP-0504 shipped the table with 70 keV as the source's limit.
