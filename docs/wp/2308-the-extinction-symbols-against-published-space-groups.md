# WP-2308 — The extinction symbols, checked against the published space groups

Milestone: unscheduled · Status: ⬜
Track: The fit has no reference
Depends on: 2010 (the feature registry and the `reference_kind` join, PR #1266); 2076 soft (PR #1738 moves the PbSO₄ row's answer)
Priority: P3 2026-11-25 — a validation-matrix row over data already in the tree; changes no number a user gets

## Goal

The `extinction_symbols` feature carries a validation-matrix claim for each real pattern in
the tree whose screen runs in a test. Each claim states the compound's published space group,
the class the screen names, and whether that class lists the group. It is tiered by
DESIGN-RULES.md § Rules, 2. Today the feature is verified by two unit tests and validated by
nothing (`docs/VALIDATION.md` § `extinction_symbols`).

## Context

WP-2010's last open task asked for this as one of three follow-ups "for data already in the
tree". The other two are owned: the Le Bail and Pawley cell against SRM 660c is WP-2072
(issue #1259), and LaMnO₃'s Pn′ma′ sits in WP-1327's `### Inherited` (issue #1260).

The real patterns whose screen a test runs, at the tree of 2026-11-25:

| Pattern | Test | Answer pinned today |
|---|---|---|
| Corundum, lab Cu | `test_extinction_symbol.py::test_corundum_returns_the_class_its_certificate_names` | `R - c -` |
| NAC, 11-BM | `test_extinction_symbol.py::test_nac_returns_the_centred_class_and_claims_nothing_more` | `I - - -` |
| Fluorapatite | `test_extinction_symbol.py::test_fap_leads_with_the_p63_class_and_abstains_on_one_position` | abstains |
| PbSO₄, lab X-ray | `test_extinction_gate.py::test_pbso4_xray_gets_its_class_only_through_the_seeded_prefit` | `P c - a`, a known wrong answer; PR #1738 makes it `None` |

**The tier is the open question.** A published space group of the compound comes from another
specimen, usually a single-crystal study. Rule 2's examples of an independent measurement
(a certified cell, a weighed composition, a composition from another probe) do not say
whether that counts. WP-1327 carries the same question for Moussa et al.'s LaMnO₃ moment.
Settle both the same way.

**A gotcha.** The corundum test calls its reference "a certificate" and names SRM 676a. WP-2072
found that `qarr/corundum.prn` is documented as a corundum specimen and not as 676a
(`tests/data/README.md`). Check which file `corundum_screen` loads before the row cites a
certificate.

## Non-goals

- Changing the screen. WP-2076 and WP-1910 own its behaviour.
- New data. A pattern not in the tree is a separate follow-up.

## Tasks

- [ ] Settle the tier of a published space group from another specimen, with WP-1327's
      Moussa question. Bring it to the maintainer only if Rule 2's text does not settle it.
- [ ] Per pattern above, the published space group with its source (author, year, journal),
      read through the paper-reader skill. Confirm the corundum file's provenance.
- [ ] The validation-matrix claims, `features=("extinction_symbols",)`, after PR #1738 lands,
      each stating whether the named class lists the published group. A screen that abstains
      is recorded as abstaining, never as agreement.
- [ ] `docs/VALIDATION.md` regenerated (`python -m tests.validation_matrix`).
- [ ] Skill: none expected. The validation record is for the developers (ruled 2026-10-27,
      WP-2010).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_validation_matrix.py tests/test_extinction_symbol.py tests/test_extinction_gate.py -q
```

## References

- DESIGN-RULES.md § Rules, 2; WP-2010 (the registry); WP-2072 and WP-2306 (the same shape for
  a cell and a size).

## Handover log

- **2026-11-25** — filed by WP-2010's closing handover, as the third of its "references for
  data already in the tree". No open WP owns it. WP-2076 owns the screen's real-data rows, but
  its PR #1738 closes it on merge, so a fold there would be lost. WP-1910 owns the screen at a
  small cell error, not the validation record. Checked against the tree at `0e79e455f`. Next:
  the tier question, then the source per pattern.
