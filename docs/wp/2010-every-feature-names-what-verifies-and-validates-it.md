# WP-2010 — Every feature names what verifies it and what validates it

Milestone: generality · Status: 🔄 2026-10-31 — ruled, reworded and read for consistency; the reporter (#1051) builds it
Track: The audits
Depends on: —
Priority: P3 2026-10-18 — outside the gate after 2004, so it waits on nothing; the magnetic report wording moves with it

## Goal

Every feature rietx refines or corrects for names what verifies its code and, where one
exists, the independent measurement that validates its physics, in DESIGN.md § Rules,
2's sense as narrowed on 2026-10-27. A feature no test verifies is verified or fenced. A
feature with no independent measurement is recorded as *not yet validated* in the validation
matrix and its generated page, for the developers, and a result that reports a number
from such a feature says so once in its report, naming each such number. A test holds the feature
list to the help vocabulary and the Theory headings, partitioned both ways, and joins
each feature to its claims, so a new feature cannot land without saying which state it
is in. That test is the tripwire Rule 4's test for a new topic lacks.

## Context

DESIGN.md § Rules, 2. Verification asks whether the code computes its model correctly and
is the package's gate. Validation asks whether the model matches the specimen, and its
reference value is an independent measurement. In `tests/validation_matrix.py`'s
tiers, `identity`, `own_result` and `cross_code` verify; `certificate` and `spread`
validate; `prediction` validates where its reference value is an independent measurement and
verifies where it is the package's own arithmetic or another code; `characterisation` does neither. A topic
without an independent measurement states its equation, source and code plainly and is
recorded not yet validated. That state is separate from *provisional*, which
`tests/api_surface.PROVISIONAL_MODULES` keeps for an API that may change.

**Decided 2026-10-27 (the maintainer, in session):**

- *The record is for the developers.* Which feature to use follows from the sample and
  the data, by the agent's own reasoning; whether the package has validated the feature
  should not move that choice. So no surface an agent reads to choose a feature carries
  a validation verdict, no agent-harness round measures the label, and the GUI help
  field waits until something shows a human reads it. The seat is the matrix and
  `docs/VALIDATION.md`, keyed by the feature registry. `capabilities()` is unchanged: a
  per-feature kind of reference value there would be the verdict in machine form.
- *Rule 2 narrowed to the book's meaning.* Agreement with another code or with a
  published refinement of the same pattern verifies. A validation result reports the
  mismatch in the quantity's units with the measurement's uncertainty and the fit's
  esd, over a stated domain, and says whether the data is development data. A dataset
  is unused, development data or sealed; a sealed family is spent into development data
  at the close. Wording of 2026-10-31: "independent measurement" and "reference value"
  replace "referent". DESIGN.md § Rules, 2 carries the text; `generality.md`
  § Acceptance's two rows follow it.
- *A number with no independent measurement says so in the report.* Chosen over a diagnostic on every
  such fit (a new code on every magnetic fit; the reporter's objection, #1051) and over
  the manual alone. One FitReport sentence, present only when the result reports such a
  quantity, read from the registry: the one place the fact reaches a reader of results.
- *Development-data risk, measured* by a hand reading of the audit table's evidence
  text. Of 1240 audit rows, 66 cite an acceptance dataset. 55 are sensitivity or
  invariance checks where the reference played no part. 11 were selected on
  development data in Rule 2's sense: 6 set a threshold or margin so the seen data's
  known answer passes, 2 were kept because a seen acceptance bar went red (GTOL, XTOL
  against the Stephens suite's characterisation bar), and 3 by whether a number moved
  toward its reference value (`Source:dispersion`, tier 2 on seven programs' practice but
  argued from the round-robin RMS; `width_twins_held`, W never held;
  `REFLECTION_MARGIN_DEG`'s reverted edge rule). All three rest on the CPD QPA round
  robin's weighed compositions. Validating claims under the old tiers: 24 on 7 datasets,
  5 families, 4 instruments (11-BM, BT-1, the NIST and the CPD lab instruments); under
  the narrowed rule about 16 on 4 datasets and 3 families, the retier task settling the
  count. Tier-3 rows (rietx's own unsourced numbers, 139): a physics feature carries at
  most one on its path, the background picker 13, the staged plan 15.

**Measured at filing** (2026-10-18, darwin arm64, `[dev]`). The matrix held 134 claims
over 17 acceptance suites, 24 with a validating tier and 21 more agreeing only with
another code; five suites carried neither: both magnetic suites, Stephens anisotropic
strain, extra peaks and NAC. At feae4c75e (2026-10-27): 143 claims, 24 validating under
the old tiers, 24 `cross_code`. The matrix is keyed by test, and nothing joins a feature
to its claims.

**The reporter's first pass** (#1051, 2026-10-19, on main at 2df48c95): 43 features
grouped by Theory section; 15 validated by the old rule (11 under the narrowed one, by
the reporter's feature count); 28 not yet validated, of which 15 have no acceptance
claim at all, 3 are cross-code only (profile, coordinates, ADPs) and 10 rest on
characterisation or own-result claims (magnetic, Stephens, extra components). Both
partitions close: 94 help keys and 117 Theory headings. The list of 15 is in no file;
only the count is.

**The magnetic case.** Both magnetic datasets are GSAS-II tutorials vendored verbatim
(`cr2wo6_hb2a`, `lamno3_bt1`), and neither quotes a moment, so every magnetic claim is
`characterisation`. A published moment refined from either pattern would verify; an
independently measured moment would validate. The magnetic milestone is open (1327,
1329, 1343, 1418, 1419 and 2034 in flight) and its WPs edit the help entries and manual
chapters this WP touches. Merge main before the registry commit. 1327's `### Inherited`
carries a note from 2001 (2026-10-19) on what the label would say; it now says what the
report says instead.

**The seat.** The reporter proposed `capabilities()` primary with a derived
`HelpEntry.validation` field (8 files, the GUI's TypeScript, vitest table and dist). Under
the 2026-10-27 ruling neither: the help field waits, and `capabilities()` carries no
per-feature state. The feature registry (`rietx.features`, the reporter's key) ships,
because the report sentence reads it.

**The grain.** A feature is what a user switches on or refines, so the key is the help
vocabulary: every `PARAMETER_HELP` family and every correction field in
`INSTRUMENT_FIELD_HELP` belongs to exactly one feature. Output topics with no parameter
family (quantitative phase analysis, indexing and extinction symbols, derived geometry,
microstructure) are keyed on their Theory heading, Rule 4 already sending a new topic's
equation there. Four features have no Theory section (TOF shape, peak picking, extinction
symbols, joint fits) and get one or a declared exception.

### Inherited

- 2026-10-26 issue triage: #1051 is the outside contributor's (mustachefeeling) claim on
  this WP. Their 2026-10-19 comment proposes the seat and the key, with a 43-feature
  first-pass table, and asks five questions. Answers drafted 2026-10-27, posted on the
  maintainer's approval (the handover log).

## Non-goals

- New validation data. Finding an independent measurement for an unvalidated feature is a follow-up per
  feature; this WP records the state and files the follow-ups worth doing. The IUCr
  ceria size-strain round robin (Balzar et al. 2004) is the first, for microstructure.
- Retiering heuristics: 2002 to 2007.
- `PROVISIONAL_MODULES`: an API statement, unchanged.
- A `HelpEntry` field, a `capabilities()` arm or any GUI seat for the state (ruled
  2026-10-27).
- An agent-harness measurement of the label (ruled 2026-10-27).

## Tasks

- [ ] The list of the 15 features with no acceptance claim, in this file, with what
      verifies each today (a unit test by name, a cross-code pin) or `unverified`.
- [ ] Each `unverified` feature verified (a test against a formula or another code) or
      fenced until it is.
- [ ] The feature registry: each feature with its help keys, its Theory section and the
      claims that reference it (a `features` field on `Claim`); the four featureless
      topics given a section or a declared exception.
- [ ] The state per feature, derived: what verifies it, what validates it with the
      mismatch, its domain and the development-data flag, and *not yet validated* where
      the second is empty; `docs/VALIDATION.md` regenerated with the feature table.
- [ ] `prediction` claims retiered by rule: a claim validates only against an
      independent measurement. The reviewer's count at feae4c75e: 9 `prediction` claims,
      of which 6 (two capillary identities, three Nd₂Ru₂O₇ joint-wavelength, one Si 640c
      against XND) are referenced to the package's own arithmetic or another code and a
      7th to the package's own v0.3 table, over four features; the Si 640c held-cell
      claim is an identity. The meta-test enumerates them. `TIERS["prediction"]`'s
      text, which calls the capillary ΔB prediction the strongest evidence in the repo,
      rewritten to say which kind of reference value a prediction checks against.
- [ ] The matrix's own prose uses of *validate* in verification's sense reworded
      (start dependence as "a validation axis", "would validate a configuration", the
      anode wavelength tables, the multi-phase CIF round trip), `docs/VALIDATION.md`
      regenerated.
- [ ] The report sentence: a result that reports a quantity from a feature with no
      independent measurement lists it once, read from the registry; absent otherwise.
- [ ] The meta-test: the feature list partitions the help vocabulary and the Theory
      headings both ways; every claim and test a feature names exists; every
      `prediction` claim names its reference value's kind.
- [ ] Root CLAUDE.md § Invariants: the clause "Every physics function cites its
      reference" names the meta-test.
- [ ] 1327's `### Inherited` note updated: the report sentence's wording for the moment.
- [ ] Follow-ups filed: the ceria round robin as a microstructure measurement; references
      for data already in the tree (a Le Bail cell against the SRM 660c and 676a
      certificates, published space groups for the extinction symbols, LaMnO₃'s Pn′ma′).
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: none. The report sentence is the package's own output (DESIGN.md § Rules, 3).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_validation_matrix.py tests/test_help.py tests/test_manual.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

Plus, by hand once: add a throwaway family to `PARAMETER_HELP` on a scratch branch and
confirm the new test goes red naming it.

## References

- `docs/milestones/generality.md` § Decisions; DESIGN.md § Rules, 2 and 4.
- `tests/validation_matrix.py`, `docs/VALIDATION.md`, `tests/api_surface.py`.
- Roache, P. J. (1998). *Verification and Validation in Computational Science and
  Engineering*. Hermosa. Oberkampf, W. L. & Roy, C. J. (2010). *Verification and
  Validation in Scientific Computing*. Cambridge University Press, chapters 2 and 10 to
  13: pp. 31-32 and 44 (calibration against validation), 375-376 (hidden adjustment),
  393-394 and 416-417 (the two-step recipe, the blind test), 401 and 632 (assessment on
  calibration data), 469 (disclosure), 489-490 and 499 (the metric: a mismatch, no
  adequacy word).
- Balzar, D. et al. (2004). *J. Appl. Cryst.* 37, 911-924. The ceria round robin; the
  patterns are served from the first author's University of Denver page.

## Handover log

- **2026-10-31** — a wording ruling and a consistency read of the rule set, no code.

  The rules now use two plain terms where they used one awkward one. An *independent
  measurement* is what validates: a certificate, a weighed composition, a composition
  from another probe. A *reference value* is anything a check compares against, and
  its kind decides whether the check verifies or validates. Read against each other,
  the rules had fifteen inconsistencies. Thirteen are fixed, one needed no change, and
  one is a conflict between written rules that only the maintainer can settle. Rule 1
  has no outcome for the defaults a fit cannot run without, so that conflict now opens
  WP-2038's brief. Both of Mike's issues have their replies, so the build in #1051 can
  start from the rewritten text once #1190 merges.

  *Done.* 3be0246f6: the maintainer's ruling of 2026-10-31 ("B is good, there is no V&V
  audience") puts "independent measurement" and "reference value" in place of
  "referent". The change runs through DESIGN.md § Rules 2 and 4, `generality.md`, this
  file, WPs 1327 and 2017, the generality-review agent, `tests/validation_matrix.py`
  and its renamed test (`test_every_claiming_row_states_its_reference_value`).
  `docs/VALIDATION.md` was regenerated. Handover logs and older records keep the old
  word as history. 72d74c00d: a reviewer read the whole rule set for consistency, and
  I checked each finding against the files. The fixes: Rule 2 states three dataset
  states (unused, sealed, development data) that cover every case, from Oberkampf & Roy
  p. 32's "seen"; a sealed family's seal survives a run that steers no change; a report
  names each unvalidated number once; the agent surfaces that carry no verdict are
  listed; `characterisation` is named as neither verifying nor validating; the testing
  policy counts seven tiers; superseded decisions in `generality.md` are marked; the
  root CLAUDE.md's answer-by-kind bullet says a ranking picks only in Rule 1's two
  cases. The sealed-family row needed no change, since it already says the close
  measures drift and names HfIn's EDX composition as the one independent measurement.
  cc73330f8: the Rule 1 conflict is recorded in WP-2038's `### Inherited`, and the
  CLAUDE.md cap rises from 994 to 995 lines with a dated row, following the 2026-10-24
  precedent. Posted on the maintainer's approval: the replies on #1051 (the rulings,
  five answers, the wording note) and #1052 (the open commit accepted, the close
  measures drift, a request for HfIn's refined composition against EDX Hf 0.51(2)).

  *Measured.* Fast suite, `[dev]`, darwin arm64, on 72d74c00d plus the WP-2038 edit:
  12665 passed, 288 skipped, 4 failed, 21 errors, in 72 min against the usual 3-5,
  with the machine loaded. The 21 errors were the manual build hitting its 300 s
  timeout. Two failures were timing budgets (`test_examples.py[hold]`,
  `test_site_classes.py::test_an_unplaceable_species_does_not_enumerate_the_others`).
  All 90 of those passed on a rerun alone, 2-3 min. One failure was the CLAUDE.md cap,
  fixed in cc73330f8. One is the machine's stale Jupyter kernel spec
  (`test_display.py`). No tests were added. At 091600955 the audit table held 126
  default rows, 81 of them audited and 4 at ambiguity kind 2 or 3.

  *Review.* `/code-review high --fix` over the branch found three wording faults and
  no code fault, all fixed in 1f05874e3. The B(O) claim row called physical
  plausibility "not a reference value", which the new definition contradicts, and now
  says "not a measured value". The cBN QPA test kept "referent". The matrix docstring's
  edited paragraph is rewrapped. *Generality.* No judge was dispatched: the
  `_audit.py` change is the one-word docstring edit of 2026-10-27, `tests.audit_delta`
  reports no row or declaration changed, and the session added no heuristic. The full
  suite did not run, since the branch is docs, docstrings and one renamed test.

  *Gotchas.* No checklist item moved: they are the build, and #1051's reporter has
  taken it. A new reader of Rule 2 should read "reference value" as the umbrella and
  "independent measurement" as the one kind that validates.

  Next: the maintainer reviews and merges #1190. After that, the reporter builds the
  checklist from the first task (the list of the 15 features). Two proposals wait on
  the maintainer and are not filed: a leave-one-family-out rule for WP-2017 (tune on
  two families, test on the third, with the bar fixed first), and a WP for the ceria
  round robin once #1190 merges.

- **2026-10-27** — a ruling session, no code.

  The word "validated" now means one thing in rietx: a refined number was compared with
  a measurement that did not come from a refinement, such as a certified cell or a
  weighed mixture, and the comparison is reported as a mismatch with its uncertainties,
  saying whether the developers had tuned on that data. Agreement with another program
  or with a published refinement only shows the code computes what it claims. The label
  that says which state a feature is in is for the developers; a user or an agent picks
  a feature from the sample and the data, and the only place the fact reaches them is a
  sentence in the fit report beside a number that has no outside check. The WP's job
  therefore changed from labelling 43 features to establishing that each is verified at
  all, since fifteen have no acceptance test behind them.

  *Done.* DESIGN.md § Rules, 2 rewritten as three paragraphs; its north star and Rule
  4's new-topic test narrowed with it; five loose uses of *validate* in DESIGN.md, one in
  the root CLAUDE.md, the audit table's docstring and the generality-review checklist
  moved to *verify*. `generality.md`: the two acceptance rows, three lines of § The
  rule, the § Decisions pointer, and a dated decision carrying the measurements. WP-2017:
  the Nd₂Ru₂O₇ line and the "for good" line brought to the ruling. This file: the four
  decisions dated into § Context, the tasks reframed.

  *Measured* (darwin arm64, `[dev]`, tree feae4c75e; the script and the full
  classification were in the session's scratchpad and are re-derivable from
  `_audit.ROWS` and `validation_matrix.CLAIMS`): 1240 audit rows, 66 citing an
  acceptance dataset, 55 sensitivity or invariance checks, 11 selected on development
  data, 3 by referent distance (all on `qarr`); 143 claims, 24 validating under the old
  tiers on 7 datasets, 5 families, 4 instruments; 139 tier-3 rows, a physics feature
  carrying at most one, the background picker 13, the staged plan 15. Oberkampf & Roy
  chapters 2 and 10 to 13 read in full by a subagent, page-cited in § References. Fast
  selection on the final tree (darwin arm64, `[dev]`, alone): 11862 passed, 272 skipped,
  32 xfailed, 1 failed, 6:15; no test added. The failure is
  `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`,
  which launches the user's `python3` Jupyter kernel spec, and on this machine that spec
  points at a deleted venv; it fails alone and before this branch, and CI's kernel is its
  own. `/code-review high` found one slip (the acceptance row counted predictions by
  feature) and one sentence declared with no writer, both fixed; it declined the
  `prediction` tier text, which the retier task owns. No audit row changed
  (`tests.audit_delta`), so no generality judge was dispatched.

  *Review.* An adversarial fresh-context read of the drafts found sixteen defects; the
  material ones were that `capabilities()` carrying referent kinds would be the verdict
  in machine form, that "four predictions" counted features where the matrix has six to
  seven claims, that Nd₂Ru₂O₇'s three claims are predictions the ruling retiers, that
  the instrument count was 3 where the datasets span 4, that the development-data
  selection is 11 of 66 by Rule 2's own definition, that the #1052 comparison runs under
  a different protocol and so measures drift rather than verifying, and that "spent"
  reverses the 2026-10-26 "for good" and had to say so. All applied.

  *Gotchas.* The north star sentence changed one phrase ("independent referent" for
  "published reference") and reply 1052 reverses a public statement of the maintainer's;
  both are flagged for the maintainer's read. The replies to #1051 and #1052 are drafted
  and not posted. Left out on purpose: leave-one-family-out machinery for WP-2017
  (domain spread outranks blindness on five families), and making the existing suites
  blind.

  *Next*, in order: the maintainer reads the diff and approves or edits the two replies,
  which then go to #1051 and #1052; the reporter rebuilds the list of the 15 unclaimed
  features as the WP's first commit, which decides how much verification work the WP
  holds; the ceria round robin is filed as the microstructure referent.
- **2026-10-18** — created, from the cascade of DESIGN.md's rules into the generality
  milestone. No open WP owns a feature-level audit against Rule 2: 1918 and 1933 validate
  files on read, and 1464 screens batches. Filed in this milestone and outside its gate
  after 2004, because the gate tests whether rietx's decisions are warranted, and this
  WP's premise is already measured by the counts above.
