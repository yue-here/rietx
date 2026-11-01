# WP-2032 — the TOF readers' T-1 follow-ups: a time map read as data, and names with no writer

Milestone: unscheduled · Status: ✅ 2026-10-23 — a `TIME_MAP` after a bank's rows ends the bank, every refusal names its file, a project records the bank it opened, and `FPATH1` and `SPECTRUM_TYPES` each have a writer and a reader (PR #1122)
Track: The specimen is not an angle, and the neutron follow-through
Depends on: — (1927 soft, closed: the T-1 cut these come from)

## Goal

The T-1 time-of-flight readers have no known defect left: a `TIME_MAP`
record is never read as data, every refusal names its file, the bank a
project opened is recorded, and every declared TOF name has a writer and a
reader or is removed.

## Context

T-1 (WP-1927, PR #911 through #961, 2026-10-13) added the TOF axis and its
readers. Its two review rounds left seven follow-ups, none blocking. At the
time, all seven were parked for the T-2 cut, which ROADMAP § v2+ holds
behind the magnetic milestone. A chain audit on 2026-10-23 found that five of
them are defects in code that has already shipped, and they need no T-2
model. They are this WP. The other two, `TOFSource` exposing `lines`,
`primary_wavelength` and `wavelength_parameters` as properties that refuse by
name, and the hand-written `capabilities()` note for `neutron_tof`, stay in
1927's Context § What T-1 leaves for T-2.

1. **A `TIME_MAP` record placed after a bank's data is read as that bank's
   rows.** `io/gsas.py:550-565` stops a bank's data only at the next `BANK`
   line. This is a silent wrong read. The fix stops at any record header, or
   refuses the file by name.
2. **`load_instrument_profile`'s refusal names the function, not the file**
   (`io/instrument_profile.py:190`). The root rule is that a reader raises
   naming the file (CLAUDE.md § Invariants, WP-1047).
3. **`Project.open` does not record the bank it chose** in the `DataRef`.
   The reader call is part of the reference (CLAUDE.md § Project), so a
   multi-bank file reopened can read a different bank with nothing saying so.
4. **`TOFSource.l1_m` has no writer** (`schemas/instrument.py:710`), though an
   `.iparm` states `FPATH1`. That is a declared name with no writer, WP-1076's
   rule: write it from the reader, or remove the field.
5. **`SPECTRUM_TYPES` is read by nothing** (`model/tof_spectrum.py:42`). Read
   it where the spectrum type is validated, or remove it.

**Tier.** Nothing here is a heuristic. Item 1 is a file-format rule, items 2
and 3 are bookkeeping, and items 4 and 5 remove or wire declared names. No
`_audit` row is expected, unless removing a name takes its row with it.
WP-2006 (the dead surface) tiers such names, so tell it if 4 or 5 removes one.

## Non-goals

- The TOF profile, spectrum and forward model (T-2/T-3) and multi-bank
  (T-5): ROADMAP § v2+.
- The two T-2 follow-ups named above, which stay in 1927's Context.

## Tasks

- [x] `TIME_MAP` after data: a fixture with the record after a bank's rows,
      then the reader stops at it or refuses by name.
- [x] `load_instrument_profile`'s refusal names the file. Test the message.
- [x] `Project.open` writes the chosen bank into `DataRef`, and a reopen reads
      the same bank. Test with a two-bank file.
- [x] `TOFSource.l1_m`: written from `FPATH1` by the `.iparm` reader, or
      removed (a schema bump if removed).
- [x] `SPECTRUM_TYPES`: read where the type is validated, or removed.
- [x] Skill: none expected, since nothing here changes what an agent calls.
      Say why at handover.

## Acceptance

- Each item has a test that fails on `main` and passes here.

```sh
.venv/bin/python -m pytest tests/test_tof*.py tests/test_project*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1927 (T-1) and its 2026-10-13 handover entry's *Not done*; PR #911, #961.
- #1120: taken by @mustachefeeling, with the plan this WP's handover follows.
- Larson & Von Dreele (2004), *GSAS Technical Manual*, LAUR 86-748, p. 217
  (comment records precede a `BANK` or `TIME_MAP` header) and p. 219 (the
  header-and-records sets "may be repeated in any order").

## Handover log

- **2026-10-30** (`/pr-review`, after the close) — the two follow-ups asked on #1122 merged from outside as PR #1138 (`a25650ed`), docs only. `src/rietx/io/CLAUDE.md` now names `FPATH1`'s token reading as a deviation, in the records bullet, as `BNKPAR`'s is named. The `gsas` row's `TIME_MAP` sentence keeps its rule and drops the bug's history, which this log holds. The file stays at its 561-line cap after #1202 (WP-2059) edited it too. Still unowned: real SNS `.prm` files whose `ICONS` records write explicit zeros do not read end to end.

- **2026-10-23 (closed)** — PR #1122 by @mustachefeeling merged as
  `e6e97630`, after one review round (`/pr-review`, at `049d1097`). It lands
  all five tasks, so this WP closes. The review read every source hunk.
  Refusals now name their file, including the `.iparm` reader's wrap of
  `_coefficient_count`. `Project.open` writes the fallback bank into
  `DataRef.options` in memory, only after the fingerprint check passes, so
  opening still writes nothing a save did not. `SPECTRUM_TYPES` is checked
  before `COEFFICIENT_COUNTS` is indexed, so an unknown type cannot raise
  `KeyError`. No `_audit` row was needed.
  *Gate*: the branch already contained main `12f459e5`, so the merged tree
  was the PR's head tree, and CI's fast jobs ran it green. The full suite
  with `-m slow` on that tree (darwin/arm64, `[dev,jax]`, nothing else
  running) gave 404 passed, 12 skipped, 14 xfailed and 4 failed in 18-19
  min. All 4 fail the same way on main `12f459e5` alone on that machine:
  three in `test_staged_start_invariance.py` (cpd1a, LaB6) and
  `test_acceptance_magnetic.py::test_the_150k_null_finds_no_moment`. The
  Linux nightly's full job passed on `d01ae735` (2026-10-22) and was
  cancelled on `3e0dc6f7`, so whether they fail on Linux is not known. The
  maintainer merged on "no new failures".
  *Follow-ups asked on the PR, not blocking*: name `FPATH1`'s token read
  as a deviation in `src/rietx/io/CLAUDE.md` § `instrument_tof.py`, the way
  `BNKPAR`'s is named; and trim the bug's history from the `gsas` row's
  `TIME_MAP` sentence. The real SNS `.prm` files whose `ICONS` records
  write explicit zeros still do not read end to end, and no WP owns that
  yet.

- **2026-10-23** — built all five, as planned on #1120 (taken by
  @mustachefeeling). Each item has a test that fails on `main` `12f459e5` and
  passes here, all in `tests/test_tof_axis.py` § WP-2032; 12 of the 15 new
  items fail on `main`, and the other three are controls that pass on both.
  *Done*: (1) a `TIME_MAP` header ends a bank's rows as a `BANK` record does
  (`formats/gsas.py`, the body loop). The manual allows it: the sets "may be
  repeated in any order" and a map is only "usually" at the head (p. 219).
  *Measured on `main`* it was not silent but refused with the wrong cause
  ("characters 1-8 of data record 3 of the ESD bank hold 'TIME_MAP'"), in
  ESD and STD alike; the Priority line's "silently" overstates it. The
  fixture is `time_map_bank`'s own file with the map moved after the rows;
  here it reads channel for channel as the map-first file does, and a map
  between two banks belongs to neither. A line that is no header still
  refuses by name (the control). (2) `load_instrument_profile`'s bank refusal
  now starts with the path. (3) `Project.open` writes the bank its
  old-project fallback read into `DataRef.options`, after the fingerprint
  vouches for it, so the next save records it. The test swaps the two banks'
  order after the save and the reopen still reads bank 1; with the record
  removed, the same swap is refused by the fingerprint (the control).
  `Project.create` still records no `bank` for a one-bank file, as before:
  the open backfills it. (4) `FPATH1` is read as `TOFSource.l1_m` on every
  bank (`instrument_tof._primary_flight_path`): one number after the key,
  since the manual lists no such record and real files place it in columns
  13-22 (NOMAD) or 13-26 (POWGEN). That it is L₁ rests on SNS NOMAD's data
  header: "Primary flight path 19.5m" beside `FPATH1 19.50`, and per bank a
  "Total flight path" equal to 19.5 m plus `BNKPAR` DIST (five of six banks
  to the written digit, the sixth 0.02 m off). Wired, not removed, so no
  schema bump and nothing for WP-2006. (5) `model.tof_spectrum._coefficient_count`
  validates an ITYP against `SPECTRUM_TYPES` and only then reads
  `COEFFICIENT_COUNTS`; the schema validator and the `.iparm` reader both
  call it, the refusal lists the defined types from the table, and the count
  refusal names the function. A test removes a type from the table and
  watches both refuse it; another holds the two tables' keys equal. Nothing
  was removed, so nothing for WP-2006.
  *Skill*: one reference row corrected, nothing added. The
  `GSAS_IPARM_FIELD_DROPPED` row in `references/diagnostics-gsas.md` said
  "L₁ stays unset", which item 4 made false; it now lists `FPATH1` (L₁)
  among what the banks carry, shorter than before. No new name an agent
  calls. The manual's `.iparm` table has the `FPATH1` row, and the 1.10.0
  staging file has four notes under `## Changed`.
  *Generality*: no `_audit` row. Nothing here adds a diagnostic code, a
  default, a module-level number or a record field.
  *Gate* (Mac, worktree `.venv`, Python 3.12, `-n 4`; pearl offline): the
  acceptance selection `tests/test_tof*.py tests/test_project*.py -m "not
  slow"` 1167 passed; `ruff check src tests examples` clean; the fast
  selection on the final tree 11 261 passed, 265 skipped, 27 xfailed, 0
  failed (`--junitxml`: 11 553 tests, 292 skipped, 0 failures, 0 errors).
  *Not done*: real SNS `.prm` files still do not read end to end. Their
  `ICONS` records write `0.000    0     0.000` in the POLA/IPOLA/KRATIO
  columns, which the reader refuses as non-blank. With those columns blanked
  in a scratch copy, two NOMAD files read L₁ 19.5 m and a POWGEN 2013B file
  60.0 m on every bank. Whether explicit zeros there are "absent" is a
  separate decision, left to a WP of its own.
  Next: review on the PR; closing moves this narrative to the release record.

- **2026-10-23** — created by the chain audit of WP-1927's close. 1927's close
  had left all seven review follow-ups for the T-2 cut. Five of them are
  defects in shipped T-1 code, and no open WP owns them. WP-2006 tiers
  declared names and does not fix readers, and no TOF WP is open.
