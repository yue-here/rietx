# WP-2058 — the FullProf `.pcr` reader takes three control flags, `Jbt ±10` and `NPATT`

Milestone: unscheduled · Status: 🔄 2026-11-01 — F1 and F2 merged from outside as PR #1199 (`8326bc3d`); F3 (`NPATT`) remains
Track: Coming from another code
Depends on: — (F3 waits on two maintainer decisions; #193 for TOF patterns, fenced)
Priority: P3 2026-10-26 — a reader with a workaround (rebuild the model by hand); none of FullProf's 94 example `.pcr` files reads today, and a contributor's dataset needs F2 and F3

## Goal

A FullProf `.pcr` with `Nor = 1`, `Dum ≠ 0` or `Nre > 0` reads, a `Jbt = ±10`
nuclear + magnetic phase reads onto the phase's moments, and a constant-wavelength
`NPATT` file reads to `(structure, instruments, sharing, weights)` ready for
`refine_multi`. Every other value still refuses by name.

## Context

**The proposal (issue #1066, mustachefeeling, 2026-10-20).** Three chunks,
each one PR, each mapping the FullProf manual's definition (Rodríguez-Carvajal,
*An Introduction to the Program FullProf 2000*, July 2001; page numbers below
are the PDF's, as the issue quotes them) onto machinery rietx already has.

- **F1, three single-pattern control flags.** `Nor = 1` (p. 70) is the
  modified March function P = G₂ + (1 − G₂)[(G₁ cos α)² + sin²α/G₁]^(−3/2)
  (eq. 3.32, p. 55), where G₂ is the untextured fraction. With G₂ = 0 it is
  March-Dollase with r = G₁; a non-zero G₂ is refused by name (rietx has no
  untextured-fraction term). The reader states G₁'s geometry note (p. 55: the
  reading of G₁ < 1 and > 1 is opposite in Debye-Scherrer and
  Bragg-Brentano) and does not flip it. `Dum` (p. 68) is a convergence
  control that adds no lines: read and recorded. `Nre` (p. 68) is a count of
  parameter-limit lines at the end of the file: read, and mapped as decided.
- **F2, `Jbt = ±10`** (p. 90): one phase with nuclear and magnetic parts,
  negative meaning spherical moment components. LINE 22's `Mag` comment and
  LINE 23a's magnetic matrices (pp. 95-96), LINE 25b atom lines (p. 105),
  built through WP-1328's `magnetic_reading` path that `Jbt ±1` uses. k ≠ 0
  refused by name, pointing at WP-1918 (#757).
- **F3, `NPATT`** (pp. 65-67, 87-92): the multi-pattern grammar, which splits
  lines 2, 3, 4, 5, 7, 9, 19, 19-1, 19-3 and 19-4 per pattern between
  `NPATT_Lines` and `End_NPATT_Lines`; `W_PAT` per pattern; `JCONTR(1:NPATT)`
  on LINE 19-2 saying which patterns a phase contributes to; the phase's
  profile block repeated once per contributing pattern. A sample size or
  strain that differs between patterns becomes `SharingMap.per_histogram` for
  that path, with an info diagnostic, since rietx's default shares it.
  `Job = −1` (TOF) stays refused (#193, v2+ fence); `Cry ≠ 0` stays refused
  (#1068).

**Where the reader stands, at c0e32ab29.** `src/rietx/io/projects/fullprof.py`:
`NPATT` refused at `:1368-1376`; `_MUST_BE_ZERO` (`:268-280`) refuses `Nor`,
`Dum` ("its meaning is not established by any file here") and `Nre`
("restraint blocks follow it and their position is unevidenced"); `Jbt` other
than 0, ±1 refused at `:1556-1570`. The module docstring's decision 2 refuses
every multi-bank file because choosing one bank's resolution is a question
the file does not answer; F3 removes that question by returning all of them.
`multi.py`: `MultiHistogramRefinement` (`:1081`), `refine_multi` (`:2967`),
`weights` one positive number per histogram (`:1264-1266`).

**The census, measured 2026-10-26 at c0e32ab29** (triage script over the 94
`.pcr` files of FullProf's example distribution, held locally under
`rietx-bench/tools/fullprof/files/Examples` and never committed). None reads.
First refusals: `Dum` 23, `Nor` 14, `Nre` 13, TOF `Job` 9, `Nba` 9, `Cry` 8,
`NPATT` 6, `Opt` 4, other 8. Flags across control lines: `Dum = 1` ×40,
`Nor = 1` ×17, `Nre > 0` ×13. `Jbt` across phase lines: 0 ×67, 1 ×13, 2 ×12,
4 ×11, 10 ×8, 6 ×4, 7 ×3, −1 ×3, 5 ×2, −7 ×1. `NPATT` in 7 files. **With
`Dum` and `Nor` lifted, still none reads: the background type `Nba` (anything
but a point list) then blocks 41.** So F1 alone opens no example file. Decide
at the start whether `Nba`'s polynomial forms join F1; they are the format's
definitions too, and the census says they matter more than `Nre`. The example
set is tutorials, skewed to single-crystal, TOF and exotic `Jbt`, so these
counts bound a user's experience from below only.

**Oracle.** A runnable FullProf (`fp2k`) is held locally
(`rietx-bench/tools/fullprof`). It can be a black-box oracle: its calculated
pattern on a synthetic file against `predict()` on the read model. FullProf is
closed: its manual and its outputs only, never its code.

**Practice.** GSAS-II and TOPAS do not read `.pcr`. GSAS-II links phases to
histograms explicitly and weights a histogram by `wtFactor`
(`GSASIIstrMath.py:4782-4803`, read 2026-10-26); TOPAS repeats `xdd` blocks,
each listing its own `str` (TOPAS v6 Technical Reference; recalled). Both keep
per-pattern sample terms beside per-pattern instrument terms, as FullProf
does. rietx's shared-specimen default is the departure, so F3's diagnostic
says when a file breaks it. Add this survey to `docs/practice.md`.

**Tier.** Every mapping is the format's own definition (tier 1). No action or
default is added. Each new info code takes an `_audit` row at tier 1 and a
`help.py` entry; each refused value keeps its by-name message.

**Decisions open (from the issue, for the maintainer).** (1) `JCONTR = 0`: a
per-histogram scale held at 0, or a phase absent from a histogram in
`MultiParameterTable` (GSAS-II's and TOPAS's model). (2) `W_PAT` passed
through or rescaled so a uniform `W_PAT` is `weights=None`; check first what
FullProf's normalised weight multiplies. (3) `Nre` limits as `min`/`max`
bounds, or a report only.

### Inherited

- Decided 2026-10-26 (maintainer, #1068): stand-alone single-crystal refinement stays "not at any version"; an intensity list joined to a powder pattern is fenced to v2+ (ROADMAP § v2+). So `Cry ≠ 0` stays a refusal here.

## Non-goals

- TOF patterns (`Job = −1`, `Job = 3`): #193, fenced v2+.
- Single-crystal or integrated-intensity jobs (`Cry ≠ 0`): #1068.
- `Jbt` values other than 0, ±1, ±10 (Le Bail, form-factor, Fourier-component phases).
- A `.pcr` *writer* for any of these (WP-1911's territory).

## Tasks

- [ ] Decisions (maintainer): `JCONTR = 0`, `W_PAT`, `Nre` (Context).
- [ ] F1: `Nor = 1` (G₂ = 0 → March-Dollase r = G₁; G₂ ≠ 0 refused), `Dum` read and recorded, `Nre` lines read; decide whether `Nba`'s polynomial forms join it.
- [ ] F2: `Jbt = ±10` through `magnetic_reading`; k ≠ 0 refused naming WP-1918.
- [ ] F3: `NPATT` CW layout, `JCONTR`, per-pattern profile blocks, `to_multi()`; per-pattern sample terms → `SharingMap.per_histogram` with an info diagnostic.
- [ ] Tests: per flag, a synthetic file reading to the same `Structure` as its zero-flag twin apart from the stated field, and a wrong `Nre` line count refused; F2's `Jbt 0` + `Jbt 1` pair against one `Jbt 10` and one `Jbt −10` phase, moments equal to 1e-12 in crystal axes, and a flipped moment changing `predict()`; F3's two-pattern file (X-ray CW + neutron CW) whose per-histogram `predict()` equals the two single-pattern files read alone; FullProf black-box comparisons where the oracle runs. Re-run the example census and record the new first-refusal table.
- [ ] `_audit` rows and `help.py` entries for each new code; `io/CLAUDE.md`'s `.pcr` notes; `docs/practice.md` survey.
- [ ] Skill: a reference row for each new diagnostic code in the foreign-files reference, and the `refine_multi` route for a read `NPATT` file; the body needs nothing.

## Acceptance

The synthetic files above read and round-trip as stated, and every value
outside the new scope still refuses by name.

```sh
.venv/bin/python -m pytest tests/test_fullprof_pcr.py tests/test_multi.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Rodríguez-Carvajal, J. *An Introduction to the Program FullProf 2000*, LLB (CEA-CNRS), July 2001.
- Geers, M. et al. (2023). *Chem. Sci.* 14, 3531-3540 (a joint refinement published from FullProf; data doi:10.17639/nott.7259).
- Toby, B. H. & Von Dreele, R. B. (2013). *J. Appl. Cryst.* 46, 544-549.
- Coelho, A. A. (2018). *J. Appl. Cryst.* 51, 210-218.
- Issue #1066; companions #1063 (mCIF), #1068 (single crystal), #193 (TOF).

## Handover log

- **2026-11-01** (`/pr-review`) — F1 and F2 merged from outside as PR #1199 (`8326bc3d`). The `.pcr` reader now takes `Nor`, `Dum`, `Opt`, `Nre`, the analytic background types and `Jbt` ±10. With the analytic backgrounds in, the census's block on `Nba` that the Context describes no longer applies to F1. A new info code, `FULLPROF_LIMITS_NOT_APPLIED` (tier 1, with its `_audit` row, `help.py` entry and skill row), records that a file's `Nre` hard limits are not carried. A limit names a FullProf parameter number that can drive several values, so the caller sets bounds by hand. That settles the third open decision in the Context (`Nre` as a report only). The other two decisions and F3 are untouched. The PR ticked nothing. Its diff covers the F1 and F2 items, their tests and the audit and `help.py` entries, and the boxes stay for the maintainer. What ran: the PR was replayed in a stack of nine with the other round's merges onto `main` `276fe91d` and run at `635d25e3` (Mac arm64, Python 3.12, `[dev,jax]`). Full suite 14 161 passed, 235 skipped, 50 xfailed, 0 failed. The manual `-W` build was green.

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1066). Checked against the tree at c0e32ab29: `NPATT` refused at `io/projects/fullprof.py:1368`, `Nor`/`Dum`/`Nre` in `_MUST_BE_ZERO` (`:268-280`), `Jbt` beyond 0 and ±1 refused at `:1556`; none of FullProf's 94 example `.pcr` files reads, and with `Dum` and `Nor` lifted the background type `Nba` blocks 41. No open WP owns it: WP-1118 and WP-1328 (which read `.pcr` and its `Jbt ±1`) are ✅, WP-1911 (🔄) is the writers, WP-1918 (⬜) is magCIF. Next: the three decisions, then F1.
