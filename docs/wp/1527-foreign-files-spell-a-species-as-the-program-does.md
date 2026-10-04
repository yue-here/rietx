# WP-1527 — foreign files spell a species as the other program does

Milestone: unscheduled · Status: 🔄 2026-10-04 — the rule is in all four writers and the lookup reads one-charge ions; the `.pcr` other-program test and Y³⁺ past 2 Å⁻¹ remain
Track: Coming from another code
Depends on: — (WP-1118 closed 2026-09-16; its writers and readers are what this corrects)
Priority: P2 2026-09-30 — a silent wrong structure in another program's refinement (GSAS-II turns `7Li` into H), on a path few fits run; the fix PRs are open

## Goal

A species written to a FullProf `.pcr`, a GSAS `.EXP` or a GSAS-II phase CIF is
spelled the way that program reads it, or refused by name. A species read back
from a GSAS `.EXP` or a GSAS-II `.gpx` carries the isotope the file chose. No
foreign writer makes a site into another element without saying so.

## Context

rietx's own round trip passes on every case below, because each reader accepts
the spelling its own writer used. That is why no test saw them. Every outcome
was measured by the reporter against the real program: FullProf.2k 8.20
(Feb 2025, macOS), GSAS-II 5.6.3. GSAS (EXPEDT/GENLES) was not run.

Five issues, one mechanism, each with a fix PR from the same contributor:

- **#553, PR #569 — GSAS-II phase CIF.** `write_gsas2_phase_cif` copies
  `Atom.species` into `_atom_site_type_symbol`. GSAS-II turns `7Li`, `2H` and
  `60Ni` into H (b −3.74 fm), and the digitless ion `Cu+` into C. Charges are
  fine (`Zr4+` → `Zr+4`). An isotope is a per-type choice in the phase's
  `General["Isotope"]`, with no CIF tag.
- **#554, PR #570 — GSAS-II `.gpx` reader.** `gsas2.to_structure` never reads
  `General["Isotope"]`, so a deuterated project reads back as natural H
  (b +6.68 → −3.74 fm).
- **#555, PR #572 — GSAS `.EXP`.** The reader turns `NI+2_58` into `Ni258+`
  (natural Ni, a +258 ion) because `fullprof.normalize_species` strips the
  underscore. The writer's `ZR4+`/`7Li` spellings do not match the manual's
  `aasv_nnn` grammar (Larson & Von Dreele, LAUR 86-748).
- **#557, #558, PR #568 — FullProf `.pcr`.** The writer puts U = V = W = 0 with
  no resolution file, and FullProf stops before it reads a species. Past that,
  `Zr4+`/`O2-` are NOT FOUND (FullProf's key is `ZR+4`), and an isotope has no
  spelling except a LINE-12 user b. The reader refuses `Nsc = 1`.

**The X-ray side is the coupling.** An isotope label had no X-ray f₀ until PR
#556 (#552) made every X-ray lookup take the element. That landed 2026-09-30,
so a reader may now hand back `2H` for a deuterated project that has an X-ray
histogram. Neutron keys on `neutron.normalize_species`, which already reduces
an ion to its isotope.

**Two decisions the fix PRs take and a reviewer should see stated:**

1. An isotope with no place in the file is **refused by name**, not written as
   the element with a warning (the file would refine natural abundance until
   someone acts).
2. A digitless ion (`Cu+`) is refused, because rietx computes the neutral atom
   for it (#202's fallback) and GSAS-II reads carbon. *Superseded 2026-10-03
   by the maintainer's rule below: no writer refuses a species.*

**The maintainer's rule, 2026-10-03.** A writer neither refuses a species
nor writes an atom rietx did not compute. It writes the species rietx
computed, in the other program's spelling. Where rietx substituted the
neutral atom, the writer writes the neutral element and reports the
substitution. The rule holds for every writer. Decision 1 is untouched: an
isotope with no place in the file has no spelling that states what rietx
computed.

**Measured 2026-10-03: most substitutions are rietx's own lookup miss.**
`scattering.normalize_species` (`:117-123`) tries `Cu+` and then `Cu`, never
`Cu1+`. So `Na+`, `K+`, `Li+`, `Ag+`, `Cu+`, `Cl-` and `F-` all compute as
the neutral atom, though the Waasmaier-Kirfel table carries each ion as
`Na1+`, `Cl1-` and so on. A CIF with those labels reads with no diagnostic,
and at fit time `SPECIES_FALLBACK_NEUTRAL` says the ion is not tabulated,
which is false. pymatgen writes this spelling. Of the 111 ions in
*International Tables* Vol. C Table 6.1.1.3, the table lacks exactly one,
Y³⁺, and Table 6.1.1.4 gives its coefficients (4 Gaussians + c, fitted to
sinθ/λ ≤ 2 Å⁻¹). Ions in no table remain (`Fe+`, `S2-`, `Se2-` on this
table), and the writer rule is for those.

## Non-goals

- `Phase.propagation_vector` dropped by the same writers: #567, PR #571, which
  is WP-1328's.
- A `.gpx` writer. This build writes the `.instprm` + phase CIF pair.
- Running GSAS EXPEDT: no install. The writer half of #555 stays
  "unknown whether accepted" until someone does.

## Tasks

- [x] Review and land PRs #568 (.pcr), #569 (GSAS-II CIF), #570 (.gpx reader),
  #572 (.EXP) through `/pr-review`, each against its issue's reproduction
  (all four merged by 2026-10-02; handover log)
- [ ] A test per writer that reads the written species through the *other*
  program's rule (the reporter's table), not through rietx's own reader
  (met for #569 and #572; the `.pcr` writer's is unconfirmed)
- [x] Decide the reader's X-ray arm for an isotope from a foreign file
  (#554's note: land with #552 or refuse on the X-ray histogram) (settled by
  #556: an isotope takes its element's f₀ on an X-ray histogram)
- [x] Skill: a reference row for the refusal codes the PRs add, or "none" and why
  (none: no new code; #570 and #572 extend two messages, three copies agree)
- [x] A digitless one-charge ion reads as the tabulated ion: `normalize_species`
  tries `Na1+` between `Na+` and `Na`. It moves every fit that used the
  spelling, so it states what it changed (a diagnostic or a record field), and
  `SPECIES_FALLBACK_NEUTRAL` stops firing on those labels
- [x] Y³⁺ in the X-ray table, from *International Tables* Vol. C Table 6.1.1.4,
  with its source and its sinθ/λ ≤ 2 Å⁻¹ range beside the row
  (`scattering._ITC_IONS`; the DABAX file stays byte-identical) and in the
  manual Part 2's f₀ section (2026-10-04: checked against Table 6.1.1.3,
  0.0049 e at worst over s ≤ 2 Å⁻¹, and against cctbx `it1992` and GSAS-II
  `atmdata.py`, digit for digit)
- [ ] Decide what Y³⁺ does past s = 2 Å⁻¹, where the fit leaves the free atom
  (−0.11 e at 2.5, −0.57 e at 3.0, negative beyond 3.86) and ITC sends the
  reader to the free-atom curve. Today rietx evaluates the fit everywhere, as
  cctbx and GSAS-II do. A switch at s = 2 would put a step in f₀ that a
  reflection crossing it during a stage would feel.
- [x] The maintainer's rule in every writer (GSAS-II CIF, GSAS `.EXP`, FullProf
  `.pcr`, TOPAS `.inp`): write the species rietx computed; where it
  substituted, write the neutral element and report it. The three
  digitless-ion refusals go (`topas.py:1568`, `fullprof.py:803`,
  `gsas2.py:1827`) (2026-10-04: `scattering.written_species` and
  `written_neutral_diagnostics`; one `*_SPECIES_WRITTEN_NEUTRAL` code per
  format)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_species_fallback.py tests/test_projects_fullprof.py tests/test_projects_gsas.py tests/test_projects_gsas2.py -q
.venv/bin/python -m ruff check src tests examples
```

Plus the four reproductions in issues #553, #554, #555 and #557/#558 giving
the spelling the issue's "fix direction" names.

## References

- Larson & Von Dreele (2004), *GSAS*, LAUR 86-748, `EXPR ATYP`/`AFAC` records.
- Sears (1992), *Neutron News* 3, 26: the b table behind `neutron.b_coh`.
- Issues #553, #554, #555, #557, #558; PRs #568-#570, #572; PR #556 (#552).

## Handover log

- **2026-10-04** — **The rule is in the code.** A structure labelled with
  `Na+` or `Cl-` now scatters as the ions it names, and Y³⁺ is tabulated. A
  file written for GSAS-II, GSAS, FullProf or TOPAS now states the atom rietx
  computed in that program's spelling. No writer refuses an ion label any
  more. Where rietx computes an ion as its neutral atom, the file says neutral
  and the writer reports it. An isotope a file has no place for still refuses.

  *Done*, as two lanes from a cleanup session, each checked and re-run here.
  `e24980d9`: `normalize_species` tries `Na1+` between `Na+` and `Na`, and
  `_ITC_IONS` carries Y³⁺ (a = 17.9268, 9.15310, 1.76795, −33.108; b =
  1.35417, 11.2145, 22.6599, −0.01319; c = 40.2602), checked against Table
  6.1.1.3's own Y³⁺ column (0.0049 e at worst over s ≤ 2 Å⁻¹, f(0) =
  36.00005) and against cctbx `it1992` and GSAS-II `atmdata.py`. The OCR'd
  copy dropped the minus signs on a4 and b4; only the negative values give 36
  electrons at s = 0. The DABAX file is byte-identical. The writers:
  `scattering.written_species` gives each label the species rietx computes,
  the four spelling functions call it, the three digitless-ion refusals are
  gone, and `write_topas_inp`/`write_fullprof_pcr` take `diagnostics=`.
  `Cu+` writes `Cu+1` (TOPAS), `CU+1` (FullProf X-ray, GSAS), `Cu1+` (GSAS-II
  CIF), and reads back as `Cu1+` through all four. Staged in the 1.7.0 notes.

  *Caps raised*, each with its reason beside it: `API_INDEX_MAX_BYTES`
  39 600 → 39 700 (`api.md` is 39 642 B with the two new keywords), and
  `src/rietx/io/CLAUDE.md`'s line cap 498 → 501 for the species exception to
  § Project writers' first rule. PR #690 (WP-1510) also sets
  `API_INDEX_MAX_BYTES` to 39 700, so whichever merges second resolves a
  one-line conflict in `tests/skill_caps.py`.

  *Measured* (`[dev]`, macOS arm64): `test_species_fallback.py` 72 passed
  (48 before); the four writer files 890 (872 before); with the registry,
  manual API, skill, docs and portability files, 1189 passed. Pinned numbers
  that moved: the fallback fixture is now As³⁺ (its value 0.0828 → 0.0996),
  and the skill row reads 11 of 111.

  *Final tree* (after the review's fixes; `[dev]`, macOS arm64, nothing
  else running): the fast selection 8165 passed, 159 skipped, in 2:36; with
  current `main` merged in (WP-1510's PR among it), 8200 passed, 159 skipped,
  in 3:23, the figure this branch merges at. The
  session's 20 added tests cost 0.22 s together (`tests.added_test_times`), so
  none joins the slow tail. The full selection was not run: no acceptance
  fixture carries a digitless ion label or Y³⁺ (a grep of `tests/data/*.cif`),
  and the writers touch no measured number, so none can move.

  *Lane trial* (`session_usage.py lanes 0433c291`; the session's three lanes,
  both of this WP's and WP-1504's round E, are measured here):

  | lane | est | requests | main at dispatch | lane base | re-read | main requests | left in main | main edits after | redo | lane $ | in-session $ | saved $ |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | 1504-option-E | 40 | 51 | 214K | 69K | 0K of 1061K | 15 | 20K | 4 | 0 | 2.42 | 8.65 | +4.55 |
  | 1527-lookup-and-Y3 | 35 | 84 | 411K | 70K | 0K of 3K | 6 | 15K | 0 | 0 | 3.83 | 10.49 | +5.86 |
  | 1527-writers-rule | 35 | 108 | 429K | 69K | 0K of 8K | 10 | 16K | 1 | 0 | 5.36 | 14.12 | +7.56 |

  One item kept: 1902-poor-reads-usable, est 10, 16 requests, at 322K. The
  session: main 243 requests, peak 461K, $21.32; lanes $11.61. Estimates ran
  2.00× short. The 1504 lane's window is not clean: it ran 68 minutes while
  this session worked other WPs, so its 15 main requests and 4 main edits
  include unrelated work (the edits were WP-1504's own file, the 1505 note
  and a docstring the lane suggested, none of them fixes to the lane's runs).
  The selective policy at these figures (`baseline --u 0 --mo 10 --d 16489`):
  −21 % over the 194 replayed sessions, −13 % with the lane assumptions
  doubled, and −29 % in the band above 450K that this session reached. Row
  added to `docs/milestones/process.md` § Lanes within a WP.

  *Review* (`/code-review high --fix`, `8aa52925`). Fixed: the TOPAS writer
  had neutralised a magnetic site's species (`Fe4+` → `Fe`), though TOPAS
  reads the magnetic form factor from it and rietx computes the moment from
  that ion, so a site with a moment keeps its ion (Fe⁴⁺ and Mn⁺ tested); the
  written-neutral warning names the label written (`D`, `57Fe`); the rule in
  `io/CLAUDE.md` names the valence labels GSAS still refuses. Declined: a
  warning for Y³⁺ past s = 2 (a task above, since it needs plumbing in the
  fit); writing the element in the case it was typed (`fe+` → `fe`, the
  writers' existing pattern); resolving each species twice per export
  (negligible).

  *Not done.* The GSAS writer still refuses valence labels (`Cval`, `Siva`,
  `gsas.py:1405`): no GSAS spelling states what rietx computes. No real
  program has read `NA+1` or `Na1+`; only `Cu1+`/`CU+1` were measured. `S2-`
  written as `S` was never run in a target program.

  *Next:* the `.pcr` writer's test through FullProf's own rule (task 2), then
  the Y³⁺ range decision.

- **2026-10-03** — **The open question is decided, and most of it turned out
  to be a lookup bug.** The maintainer's rule: a writer never refuses a
  species and never writes an atom rietx did not compute. While checking it,
  `Na+`, `Cl-`, `Cu+` and the other one-charge spellings turned out to compute
  as neutral atoms, though rietx's table holds each ion. Fixing the lookup
  removes most substitutions before any writer meets them. Y³⁺ is the only
  ion *International Tables* Vol. C carries and rietx's table does not.

  *Done* (a cleanup session over unowned in-flight WPs; docs only). Tasks 1,
  3 and 4 ticked from the earlier entries. The rule and the measurement are
  in Context. Three tasks added. *Measured* by calling
  `normalize_species`/`detect_fallback` on 15 labels, and by reading a
  two-site NaCl CIF labelled `Na+`/`Cl-`: no read diagnostic, both neutral.
  The ITC count compares Table 6.1.1.3's 111 ion headers, from `pdftotext` of
  the maintainer's copy, with the table's `#S` lines.

  *Next:* the lookup fix first, since it shrinks what the writer rule has to
  cover. Then Y³⁺, then the writers.

- **2026-10-02** — The FullProf half is on `main`. A `.pcr` now states what
  FullProf needs to run it: non-zero widths, the radiation, FullProf's own
  species spelling (`ZR+4`), and rietx's own f′/f″ as one LINE-12
  `nam f′ f″ 2` per X-ray `Typ`. *Done:* PR #568 (`a1861ddd`), merged as
  `430d7b52` by `/pr-review` after four rounds, closing #557 and #558. The
  reader reads LINE 12 back into `FullProfModel.dispersion`. It refuses a pair
  more than 0.01 e from plain Cromer-Liberman at the file's primary wavelength,
  because a `Structure` carries no dispersion. One function,
  `_dispersion_disagreement`, is that test for the reader and the writer
  alike, so the writer refuses at write what its reader would refuse
  (`io/CLAUDE.md` § Project writers). *Decision, the maintainer's, 2026-10-01:*
  an X-ray export under `source.dispersion = None` is refused. Nothing can
  state "dispersion declined" in a form the reader accepts, and a file that
  states numbers the fit then ignores would be worse. A carrier for the pair
  on the structure or instrument would lift both refusals. That is a new
  change, not filed yet. The same goes for a measured `Dispersion.overrides`
  pair beyond the tolerance. *Gotchas:* with no instrument the dispersion is
  resolved at the placeholder Cu Kα lines, so Eu and Ho (an edge between
  them) are refused, with a message naming `instrument=`. The `_anomalous`
  docstring has a stray "With" before "A pair the reader would refuse"
  (follow-up in the review). *Next:* the `Y3+` fallback-ion decision, which
  now applies to all four writers.

- **2026-10-01** — Three of the four species fixes are on `main`. A GSAS-II
  phase CIF now spells each species the way GSAS-II's importer reads it, or
  refuses it by name. A `.gpx` keeps the isotope its phase chose. A GSAS `.EXP`
  reads and writes the manual's `aasv_nnn` type. The FullProf half, #568, is
  held on review. *Done:* PR #569 (`6afa5fdb`, merged as `ecd5e96d`, closes
  #553), PR #570 (`cb1f0ca1`, `d8350249`, closes #554) and PR #572
  (`81e15696`, `cec8a8f2`, closes #555). Task 2 is met for these three: the
  tests pin the written spelling to the reporter's measured GSAS-II table
  (#569) and to the manual's grammar (#572), not to rietx's own reader. Task 3
  is settled by #556: an isotope species takes its element's f₀ on an X-ray
  histogram, so #570's `2H` and `58Ni2+` compile for both radiations. Task 4:
  no new diagnostic code; #570 and #572 extend the messages of
  `GSAS2_GPX_SPECIES_NORMALISED` and `GSAS_EXP_SPECIES_NORMALISED`, and the
  three skill copies agree. *Held:* #568 (review of 2026-10-01, three items).
  Its new radiation and width values pass no non-finite guard, a first-line
  weight of 0 raises a bare `ZeroDivisionError`, and a negative ratio
  desynchronises the file. A partly occupied site is written fully occupied
  (older than the PR). The "does not travel" list omits zero shift,
  displacement, absorption and anomalous dispersion. *Open, one decision for
  all four writers:* a species rietx computes as neutral by fallback (`Y3+`,
  per `scattering.detect_fallback`) is written as the ion by the GSAS-II, GSAS
  and FullProf writers, so the other program refines a different atom. That
  is the `Cu+` refusal's reason without its refusal. *Gotchas:* #572's writer
  half is still from the manual only, with no EXPEDT run. It now refuses the
  valence-labelled `Cval` and `Siva`, with a message calling them "not an
  element, an ion or an isotope". *Next:* #568's second round, then the
  `Y3+` decision.

- **2026-09-30** — created, from the 2026-09-30 issue triage (issues #553, #554,
  #555, #557, #558). Checked against the tree at `e3e6486a`: `write_fullprof_pcr`
  still writes `Zr4+`, `O2-`, `7Li` verbatim and the zero-width line;
  `write_gsas2_phase_cif` still writes `7Li`; the #555 reader snippet still
  gives `Ni258+`, `Li17+` and a `KeyError` for `NI_58`. The FullProf and
  GSAS-II outcomes are the reporter's, not reproduced here (neither program is
  installed). No open WP owns it: WP-1118, which wrote these formats, is ✅, and
  WP-1328 is magnetic interchange. The PRs cite the issues and no WP, so this
  file is where `/pr-review` finds the set.
