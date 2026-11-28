# WP-1925 — anomalous scattering above 70 keV

Milestone: unscheduled · Status: 🔄 2026-11-17 — built, PR #1664 in review; the maintainer's ruling is asked on the default above 70 keV, the 200 keV ceiling and `read_recipe`
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

- [x] Measure what the correction is worth above 70 keV, before choosing a
      source: the same pattern predicted with `dispersion = None` against an
      independent f′/f″ (gemmi's `cromer_liberman` for f″ as WP-0504 used it,
      and the Kissel-Pratt (1990) high-energy limit that FPRIME 3F applies) at
      80, 100 and 130 keV, for Si, Fe, Pb and U. At 60 keV Si the maximum
      intensity moves by 0.04 % between the default and `None` (2026-10-08,
      Debye-Scherrer, 5d1f5f67); the heavy elements are the question.
      **Measured 2026-11-17** (macOS arm64, worktree `.venv` `[dev]`,
      Debye-Scherrer, one element per phase, d ≥ 0.45 Å; the same pattern with
      the block on against `dispersion = None`; change of the maximum
      intensity): Si −0.14/−0.19/−0.23 %, Fe +0.03/−0.19/−0.36 %, Pb
      −6.2/−4.2/−2.2 %, U −4.3/−5.7/−4.9 % at 80/100/130 keV. The heavy
      elements move their intensities by 2-6 %, past
      `DISPERSION_NEGLECT_SEVERE`, so declining is not a small approximation
      there. **gemmi's `cromer_liberman` f′ is not usable above the K edge for
      Z ≥ 79**: it has spurious excursions (Pb −32.8 e at 100 keV and +28.4 e
      at 125 keV; U −10.2 e at 130 keV; Au +17.4 e at 92.5 keV), which would
      move Pb's intensities by −71 % at 100 keV. Its f″ is regular, puts the
      edges where they are (Pt 78.5, Au 80.8, Pb 88.1, Bi 90.4, Th 109.8, U
      115.4 keV), and matches McMaster's photoelectric cross section through
      the optical theorem to within 3 % for Mo-U to 119 keV (Fe 12 %, where
      f″ < 0.05 e). gemmi returns (0, 0) for Z = 93-98.
- [x] Decide the source. **Ruled by the maintainer 2026-11-02: extend the
      table past 70 keV from a permissively licensed source**, so declining
      above 70 keV with a better message is no longer an option. The choice
      left is which source, recorded with task 1's numbers and a licence
      checked per file: the optical-theorem f″ from McMaster (to 120 keV)
      plus an analytic f′, xraylib, the Elam tables, or another. xraydb's
      Chantler extract is out unless NIST's terms are cleared (Inherited,
      2026-11-03).
      **Decided 2026-11-17: no new data file.** f″ above 70 keV is gemmi's
      Cromer-Liberman, the calculation the bundled table already holds (they
      agree to 1e-4 e inside it); gemmi is a hard dependency (MPL-2.0), so
      nothing new is redistributed. f′ is computed from that f″ by the
      dispersion (Kramers-Kronig) relation, plus one constant taken from the
      bundled table's own f′ (median over its rows from 35 keV), so the rows
      above 70 keV continue the table. Checks: anchored on 35-55 keV only, the
      computation reproduces the bundled f′ over 55-70 keV to ≤ 0.0073 e for
      every element Z = 3-92 more than 1 keV from an edge (≤ 0.015 e from
      0.3 keV); it agrees with gemmi's f′ wherever that is regular (Si, Fe,
      Mo, W to 200 keV, Pb at 80, U at 80 and 100 keV) to ≤ 0.008 e; and the
      constant is the high-energy limit the table carries (−0.015 e at Si,
      −0.99 at Pb, −1.31 at U). The band now ends at 200 keV
      (`dispersion.CEILING_EV`); f″ is checked against McMaster only to 120
      keV, where that table stops. Rejected: xraylib's f′ (`fi.dat`) is from
      EPDL97 (LLNL), which states no licence; McMaster's f″ alone stops at
      120 keV and carries no f′.
- [x] If a table is added: bundle it with an ATTRIBUTION.md entry and a header
      stating its status (the wheel rule in root CLAUDE.md § Licensing), extend
      the band, keep the 3-70 keV rows bit-identical, and keep the edge guard.
      No table is added (task 2); the band is extended at runtime, the bundled
      rows are served as read (`test_the_bundled_rows_are_served_as_read`), the
      edge guard holds above 70 keV, and ATTRIBUTION.md's Cromer-Liberman entry
      says what is computed and from what.
- [x] Either way: `_dispersion_diagnostics` says "off, and not sizeable at
      this wavelength" for an element outside the table, instead of skipping
      it. If declining, the `ValueError` also names `Source.dispersion = None`,
      so the person who hits it at 130 keV is not sent to the source.
      Done: an element it cannot size is named in `DISPERSION_NEGLECTED`
      (info, "cannot size it for …"); the out-of-band `ValueError` (now above
      200 keV, or above 70 keV for Np-Cf) names `Dispersion.overrides` and
      `Source.dispersion = None`.
- [x] Tests (unit/property; the 70 keV boundary both sides; an edge inside the
      new range is refused) + obs/calc/diff PNGs to `tests/output/` if a
      fixture is fitted. In `tests/test_dispersion.py` § above the bundled
      70 keV; no fixture is fitted, so no PNGs.
- [x] Skill: the routing or reference row an agent driving rietx needs from
      this WP, or "none" and why (1532 owns the workaround wording).
      The `RECIPE_DISPERSION_DECLINED` row in `references/diagnostics-projects.md`
      said 74.5 keV was outside the table and f = f₀ the correct limit there;
      it now says the lookup reaches 200 keV, the reader still declines above
      the bundled rows, and how to apply the correction. No new row: a
      hand-built model above 70 keV now just works.

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

- **2026-11-17** — A model at 70-200 keV now gets f′ and f″ instead of a
  refusal, and nothing new is bundled. f″ there is the same Cromer-Liberman
  calculation the table holds, computed by gemmi; f′ is computed from it by
  the dispersion relation and joined to the table's own f′, because gemmi's f′
  is wrong by tens of electrons above the K edge of Au-U. Measured first:
  declining the correction above 70 keV costs heavy elements 2-6 % of their
  intensities, so it was not a small approximation there. Ruled out: xraylib's
  f′ (from EPDL97, which states no licence). Two things wait on the
  maintainer: whether the default should change this way, and the 200 keV
  ceiling's tier-3 approval.

  *Done.* Tasks 1-6 above, each with its numbers.
  `dispersion._continuation` / `_kk_samples` / `_dispersion_integral`,
  `CEILING_EV` (200 keV), `bundled_band()`. The bundled 3-70 keV rows are
  served as read (every pinned number there is unchanged; `tests.reader_output`
  exit 0). Out-of-band refusal (above 200 keV, or above 70 keV for Np-Cf,
  which gemmi does not cover) names `Dispersion.overrides` and
  `Source.dispersion = None`. `_dispersion_diagnostics` names an element it
  cannot size ("cannot size it for …", info) instead of skipping it.
  `read_recipe` still declines above the *bundled* band, so the PowderLine
  recipes (74.5 keV) and their pinned numbers do not move; its docstring says
  why. Skill row `RECIPE_DISPERSION_DECLINED` and a manual paragraph in
  `theory/intensities.md` updated; ATTRIBUTION.md's Cromer-Liberman entry says
  what is computed above 70 keV.

  *Measured* (macOS arm64, worktree `.venv` `[dev]`, Python 3.12): see tasks
  1-2. Fast selection: FASTSUITE. WP acceptance (`test_dispersion.py`,
  `test_acceptance_dispersion.py`, plus `test_recipe.py`): 154 passed on the
  final tree. Lint steps as CI runs them: ruff, format, skill_caps,
  skill_surface, audit_delta all exit 0; Vale 0 errors.

  *Gotchas.* `tests/test_audit_table.py::test_an_audited_row_carries_its_evidence`
  stays red until the maintainer writes `approved` on the `CEILING_EV` row
  (tier 3, grounds written); that red is the waiting state, not a defect.
  Fact-check: none of the three cited works (Cromer & Liberman 1970, 1981;
  Kissel & Pratt 1990) is in our literature base (`papers/MANIFEST.tsv`), so the check stopped at its
  pre-flight gate. The new prose cites no work: every new claim is a
  measurement in this entry or a test.

  *Review* (a read-only review agent over the branch diff; `/code-review`
  is not run by ghostshift runners). Twelve findings; fixed: `read_recipe`
  raised `KeyError` on any H, D or He site (`bundled_band` now gives them
  an unbounded band; test added), `np.trapezoid` needs numpy 2 while
  pyproject admits 1.26 (fallback), an edge-interval decline now a
  `warning`, an unreadable species named rather than skipped, the message
  says "off" once, two tests that could not fail rewritten (the 130 keV model
  now compares predictions; the lookup-failure test sets `dispersion = None`),
  the gemmi-defect assert dropped (a gemmi fix would have failed CI), two
  docstrings corrected (0.005 → 0.01 e; the finite-range closed form).
  Declined: the last row's short final interval (29 eV at U; lookups are
  correct), and computing the continuation only above 70 keV (10-20 ms per
  element, once).

  *Generality* (the `generality-review` judge, run as general-purpose on the
  agent definition; pasted unedited, author's answers under each weak/fails):

  ## rietx.crystallography.dispersion.CEILING_EV (top of the computed f′/f″ band, 200 keV)
  **weak.** The evidence for computing f′/f″ above 70 keV at all is strong. Nothing checks 200 keV over 120 keV for heavy elements.

  | Q | Author (where) | Found | Verdict |
  |---|---|---|---|
  | 1 | "where the computed rows … stop" (row `evidence`) | Sets the band where the default `Dispersion()` gets computed rows, and where compile refuses | stated |
  | 2 | no `ambiguity` | **none given**. A refusal edge is kind 1 | finding |
  | 3 against | "nothing physical changes at 200 keV" (`grounds`) | f″ is checked against McMaster only to 120 keV. f′ is checked against gemmi to 200 keV only for Si, Fe, Mo and W. Pb and U above their K edges get no independent check at 120-200 keV. A refiner could stop at 120 keV | real |
  | 4 for | #792 names 130 keV | Declining moves Pb/U intensities by 2-6 % at 80-130 keV (WP task 1). All seven programs apply f′/f″ by default (`Source:dispersion` row). No edge for Z ≤ 92 lies above U K (115.6 keV), so f″ is smooth past 120 keV. The row does not make that argument | strong for a band |
  | 5 | tier 3, "Ours", unapproved | Right tier: this is a band edge, not a numerical setting. What other programs use as a band top: not checked | holds |
  | 6 | none cited | No measured pattern above 70 keV uses these rows. McMaster and gemmi agreement verifies the numbers and validates nothing, so the topic is *not yet validated* (no independent measurement) above 70 keV | finding |
  | 7 | the `ValueError` names overrides and `None` | No record field says a fit's f′ was computed rather than read | partial |

  Would change: Pb/U f′ or f″ at 150-200 keV pinned against an independent tabulation, or the ceiling lowered to 120 keV.

  > Author: agreed that 120-200 keV for Pb-U rests on CL's own f″ and the integral; whether to keep 200 or stop at 120 keV is question (2) below for the maintainer.

  ## rietx.crystallography.dispersion._KK_SAMPLES (sampling grid for the Kramers-Kronig integral)
  **holds.** It is a numerical setting with a test bar, but the tests cover less than the domain it claims.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | "numerical grid" (`evidence`) | Sets how accurately f′ is computed and decides nothing | holds |
  | 3 against | — | none found | — |
  | 4 for | "residual reaches 0.05 e near a K edge" without the edge bisection | Bar of 0.01 e | holds |
  | 5 | tier 1 | B10 requires a test over every input claimed (Z = 3-92, 70-200 keV). `test_the_dispersion_integral_reproduces_the_bundled_f_prime` covers 8 elements at 55-70 keV. `test_matches_gemmi_where_its_f_prime_is_regular` covers 11 points. "Every element Z = 3-92" was a one-off measurement, not a test. The tail claim ("under 1e-3 e") and the 0.01 eV bisection stop are untested inline literals | gap |
  | 2, 6, 7 | — | No action, so not applicable | — |

  Would change: a convergence test (ratio 1.001 against 1.002) over Z = 3-92 at 70-200 keV.

  > Author: added, `test_the_integral_grid_is_converged` (every seventh Z; the full Z = 3-92 sweep measured 3.6e-4 e at worst).

  ## `_continuation` anchor (median of f′_table − integral over rows ≥ 0.5 × top)
  **holds.** This is computation, not a decision. Its 0.5 is invisible to the table.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | docstring | Picks f′'s constant C | stated |
  | 3 against | — | Alternatives are the Kissel-Pratt limit (WP task 1) or the top row alone. The docstring says C "equals the high-energy limit the table carries" (Pb −0.99, U −1.31), so they agree | none found |
  | 4 for | docstring | The median resists the La-W edge rows inside 35-70 keV | holds |
  | 5 | none (no row) | `test_the_70_kev_boundary_is_continuous` (6 elements, 0.01 e) uses this anchor. The positive control anchors on 35-55 keV instead | partial |

  Would change: the anchor's error at production settings tested over Z = 3-92.

  ## DISPERSION_NEGLECTED, new "cannot size" branch (src/rietx/refine.py)
  **holds** as kind 3 (it reports and stops). The open point is its level.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | docstring: "named … rather than skipped" | With dispersion set to `None`, it names the elements the table cannot size | stated |
  | 2 | code row unaudited (both baselines) | Kind 3 | holds |
  | 3 against | — | A wavelength inside an edge interval is where the neglect is largest, yet the message reads `info`. Zn and O at 250 keV are called "not known", though the recipe reader's own docstring calls f → f₀ correct there. It adds a third branch to a level already set by a threshold (clause 2 asks for two codes) | real |
  | 4 for | WP Context: "the one silence" at 130 keV | The branch closes a silent decline | strong |
  | 7 | the code | The unsized list is in the message only, not in a field | partial |

  Would change: a maintainer ruling that an edge-interval decline owes a `warning`.

  > Author: the edge-interval case is now a `warning` (`test_an_edge_interval_decline_is_a_warning`); an out-of-band one stays `info`.

  ## `_decline_dispersion_off_table` kept above 70 keV (src/rietx/io/recipe.py)
  **fails on its own evidence.** The case for applying dispersion is stronger. The decline is kept only on the 2026-11-03 ruling.

  | Q | Author | Found | Verdict |
  |---|---|---|---|
  | 1 | "a recipe's numbers do not move" (docstring) | It switches off f′/f″ for the whole model on a PowderLine (JSON recipe format) recipe above 70 keV, which the lookup now serves | stated |
  | 2 | **none given** | Kind 1, so the unanimity gate applies | finding |
  | 3 against | — | GSAS-II, PowderLine's own engine, applies f′/f″ with no switch (`Source:dispersion` row, GSASIIstrIO.py:251-273). Declining moves Pb/U by 2-6 %. After declining, DISPERSION_NEGLECTED now sizes these elements and can warn "Restore it with Dispersion()" (from the code, not run) | strong |
  | 4 for | the ruling: "decline stays unchanged until then" (handover 2026-11-03) | BGMN drops dispersion silently with a line file that has no `.ano` table (practice.md:818), a weak precedent. Bit-identity alone is not a ground (§ moved golden) | weak |
  | 6 | — | One case on disk: LaB6 at 74.5 keV. Its distance from a reference: **none given** | finding |
  | 7 | RECIPE_DISPERSION_DECLINED, `info` | — | holds |

  The docstring says the question is "asked in WP-1925's handover", but the WP has no 2026-11-17 entry: **none given**.

  Would change: a ruling that computed rows are not the extension the maintainer ruled for.

  > Author: agreed on the evidence; kept because following the lookup moves the PowderLine acceptance numbers, which is a default/published-number change for the maintainer. It is question (3) below; the handover entry now carries it.


  *Next.* The maintainer rules on the question in PR #1664: (1) keep the
  default applying f′/f″ from 70 to 200 keV; (2) approve or change
  `CEILING_EV`; (3) whether `read_recipe` should follow the lookup above 70
  keV, which would re-pin the PowderLine acceptance numbers in a follow-up on
  this WP. If (1) is no, the table extension is reverted to a refusal that
  names the workaround, which the new message already does.

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
