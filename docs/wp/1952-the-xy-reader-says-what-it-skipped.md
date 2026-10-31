# WP-1952 — the xy reader says what it skipped

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-10-11 — a decimal-comma file reads as a different pattern with no word, and a dropped mid-file row goes unreported; a fine step usually trips the duplicate-2θ refusal, and the reporter keeps their own reader

## Goal

`read_xy` reports every line it did not read as data after the first data
row, names the cause when it finds no data at all, and refuses a
decimal-comma file instead of reading it as a different pattern.

## Context

**The report (issue #897).** An application reads instrument formats
through rietx but keeps its own two-column reader, because "real `.xy`
files often have header lines, comment lines or comma separators that
rietx's reader rejects". It asks the reader to skip non-numeric headers and
comments, accept commas and an optional esd column, and say what it
skipped.

**Most of the ask is already there, checked at `d80ca5f4`.** `read_xy`
(`io/formats/xy.py`), the last entry in `PATTERN_FORMATS`:
- skips lines starting `#`, `!`, `'` or `/` (`:44`);
- reads commas as whitespace (`:46`);
- skips any line that does not parse as numbers (`:47-50`);
- adopts a third column as σ when any value is positive (`:79`), with
  `PATTERN_SIGMA_CONSTANT` for a constant one;
- reports numeric rows of another column count as `PATTERN_ROWS_DROPPED`.

On 24 test files a text header, a `2theta intensity` header, metadata
lines, `#` and `!` comments, commas, tabs, a trailing comma, UTF-16 with a
BOM, and an esd column space- or comma-separated all read correctly.

**What is missing, ran at `d80ca5f4`:**
1. **A decimal comma reads as another pattern, silently.** Rows
   `10,0<TAB>100` with a 1° step read as 2θ = 10, 11, 12…, intensity 0
   throughout, σ = 100, 110…, and no diagnostic. At a 0.02° step the
   duplicate-2θ refusal catches it by luck.
2. **A dropped mid-file row is silent.** `10.2 n/a` between data rows is
   skipped and the pattern has three points of four, no diagnostic.
   (`10.1 nan` reads as `y = nan`, also silently.)
3. **An inline trailing comment loses the file.** `10.0 100 # c` on every
   row raises "no numeric data found". The reader parses the first three
   tokens, and the third is the `#`.
4. **`;` separators and quoted CSV** (`"10.0","100"`) raise the same bare
   "no numeric data found", naming neither cause.

**Census.** Of the 55 repository files `identify_format` sends to `xy`, 22
have non-numeric lines before the first data row and none after it (some
of the 55 are not patterns, so the counts are approximate). A report for
lines *above* the first data row would fire on those 22 and break
`tests/test_readers_robust.py::test_a_numeric_header_row_is_dropped_and_reported_by_line`,
which pins `PATTERN_ROWS_DROPPED` alone. A report for lines *after* it
fires on none of them. A header above the data is normal. A text line
inside the data is a lost measurement.

**Rules this meets.** A reader may repair a file only where it can say that
it did (`src/rietx/io/CLAUDE.md` § What a reader may repair, WP-1047). A
reader raises naming the file, never its parser's exception. WP-1332 (✅)
fenced "teaching `read_xy` any format": a file with a known header gets
its own reader. So reading `;` or quoted CSV in `xy` against refusing it by
name is a decision, and the fence leans towards refusing.

**Prior art.** GSAS-II keeps `G2pwd_xye` (two or three columns, comments
and headers) apart from a separate CSV importer for comma, tab and
semicolon data (GSAS-II documentation, *Importers*). Read from its
documentation only.

### Inherited

- **From WP-2002 (2026-10-23, 8th session, PR #1113): the σ rule's record field.** WP-2002's B14 (option 3, ruled 2026-10-20) asked for a `RefinementResult` field naming which σ rule fired, with the channel counts: the file's esd column, the Poisson fallback √max(y, 1) (`schemas.pattern.POISSON_FLOOR_COUNTS`) or the floor at 10⁻³ of the median esd (`SIGMA_FLOOR_RELATIVE`). It was not built there, because this WP replaces the floor it would report; build it with the σ ≤ 0 rule, so the field reports the rule that ships.

- **2026-10-13, from the issue triage (#897, JulesOpp's two files of
  2026-10-12, checked at c3d0367).** Both rebuilt byte for byte and read with
  `rx.read_pattern(path, diagnostics=[])`. (1) One `10.06 150.3  # …` row
  among clean rows is dropped in silence (9 of 10 points), its third token
  being `#`; their reader keeps the point. It is a test case for tasks 1 and
  4. (2) A third column with one `0` is adopted as σ, and
  `schemas.pattern._floor_sigma` raises it to a thousandth of the column's
  median positive esd (0.003 there), so that point weighs about 10⁶× its
  neighbours, with no diagnostic. That case is in no task: report a
  non-positive esd by line, beside `PATTERN_SIGMA_CONSTANT`, and decide
  between floor, drop and refuse (the pdCIF reader drops a weight column with
  any zero). The reporter checked on 1.5.0; both reproduce on c3d0367.

- **From WP-2002 (2026-10-19, PR #1050), ruled.** The maintainer ruled B5: "fix anything obviously wrong, warn during ingestion, and give the option to correct. Don't spend too much effort on this." Today `schemas.pattern._floor_sigma` (~line 43) raises a σ ≤ 0 to 10⁻³ of the column's median esd, about a million times its neighbours' weight (#897's file). The ruling as read: a channel with σ ≤ 0 takes no weight by default, the reader warns with the count and the lines, and a reader option keeps such channels at σ of one count instead. No per-format classifier. Practice, read 2026-10-19 (`2002-batch/rulings.md` § B5): GSAS-II's fxye reader zero-weights σ ≤ 0 or y ≤ 0; its xye reader zero-weights y ≤ 0, replaces σ = 0 by 1/y, and on a negative σ skips the line after storing its 2θ, so every later point pairs with the wrong angle (`imports/G2pwd_xye.py:170-186`; a defect noted here, never filed upstream). FullProf 8.20 treats σ = 0 as 1 and a negative σ as its absolute value, silently. TOPAS is silent on σ ≤ 0. The `_floor_sigma` row in `src/rietx/_audit.py` names this WP as its replacement.

- **From WP-2002 (2026-10-20, PR #1050), a contributor's second read of its batch (B5.2), agreed by the maintainer.** The Poisson fallback √max(y, 1) gives every channel weight 1 on a file normalised below one count that carries no σ column, which a GSAS-II user meets with a rescaled pattern. The proposal: the reader warns when the intensity column does not look like counts (its maximum about 1 or less, or non-integer values at low counts). It fits beside the warning this WP adds for σ ≤ 0, and B5's "don't spend too much effort" bounds it. B5.1's per-format classifier was the option the maintainer declined.

- 2026-10-26 issue triage: #1064 (mustachefeeling, 2026-10-20), the remainder after PR #1080. Checked against the tree at c0e32ab29: PR #1080 (`4b93ccda6`) reads FullProf's `XYDATA` heading (`io/formats/xy.py:139-185`), carries `TEMP` into `metadata["temperature_k"]`, and refuses an `INTER` multiplier other than 1 or `Interpol = 1` by name; reproduced, a file with `fac_y = 2` raises naming the value. Two parts remain. (1) Apply `fac_x` to x and `fac_y` to y and σ, with an info diagnostic naming the factor, as the FullProf manual (2001, p. 74, `Ins = 10`) defines them; `Interpol = 1` stays refused. The PR deferred this only because a new code needed `help.py` and `_audit.py` rows while #1050 rewrote them, and #1050 merged 2026-10-20. The new code takes an `_audit` row at tier 1 (the format's own definition). (2) An `axis` reader option (`"two_theta"` or `"tof"`) the ASCII reader honours as the caller's declaration, recorded in `metadata` as declared, and refused with both quoted where the file states a contradicting unit. Reproduced: a headerless 2000-18000 µs bank raises "x axis runs 2000° to 18000° … not 2θ", and `axis="tof"` raises "unknown reader option 'axis'" (`READER_OPTIONS` is `bank`, `block`, `scan`, `io/formats/base.py:142`). A new option needs its `help.py` entry and a `PatternFormat.options` row (`io/CLAUDE.md` § Options). The PR's open question: real `XYDATA` files write two values on the `TEMP` line and the manual names one; the reader takes the first.

- 2026-10-31, from the issue triage (issue #1064): the reporter (2026-10-28)
  offers to build this WP's two #1064 parts now, as one PR off `main`, and
  leave the rest of the WP (the σ ≤ 0 rule and its record field, the
  decimal-comma refusal, line-numbered reports) to its own design pass. The
  PR: `fac_x` scales x and `fac_y` scales y and σ, a non-unit factor reported
  by an info diagnostic with its `help.py` entry and a tier-1 `_audit` row,
  unit factors silent, `Interpol = 1` still refused; and an `axis` reader
  option, `"two_theta"` or `"tof"`, recorded in `metadata` as declared and
  refused with both quoted where the file states a contradicting unit, with
  its `help.py` entry and `PatternFormat.options` row. Tests: the `fac_y = 2`
  file and the headerless 2000–18000 µs bank read correctly, and every
  existing xy-dispatched file reads with the same arrays and no new
  diagnostic. Checked against the tree at d87c8cc91: `READER_OPTIONS` is still
  `bank`, `block`, `scan` (`io/formats/base.py:142`); the option's values are
  the existing `schemas.pattern.AxisKind = Literal["two_theta", "tof"]`
  (`schemas/pattern.py:22`), so the name follows a vocabulary the package
  already has. The second `TEMP` value is still undefined by any document
  either side holds.

- 2026-10-31, from the issue triage (issue #1240): `read_pattern` reads a
  G(r), S(Q) or F(Q) file (PDFgetX2, PDFgetX3, a bare `.gr`) as a 2θ pattern
  through the xy fallback, with no diagnostic. Reproduced at d87c8cc91: a
  small `#L r(A) G(r)` file as `.gr` and as `.dat`, and a bare `.gr`, all read
  as two_theta 1.0-4.0° with an empty diagnostics list. The fix is in flight
  as the reporter's PR #1241 (open, one maintainer review round answered at
  6bbbbff2), which refuses such files by name; its suffix-only tier was
  approved at tier 3 on the PR on 2026-10-31. A session here should read what
  #1241 lands before touching the xy reader's skip report, since both edit the
  same fallback.

## Non-goals

- A CSV reader (a new format entry, if the decision below wants one).
- Reporting header lines above the first data row.
- Widening `identify_format`'s dispatch (WP-1332's fence).
- Carrying reader diagnostics into the GUI (WP-1522).

## Tasks

- [ ] Report non-numeric lines after the first data row, by line number:
      `PATTERN_ROWS_DROPPED` widened, or a sibling code (record which).
      Decide whether a `nan` or `inf` value is such a row.
- [ ] Refuse a decimal-comma file by name. Detect it where a comma sits
      between digits with no space, and every row has the same comma count.
      Test on the 1° and 0.02° steps.
- [ ] The "no numeric data found" refusal names what it saw: an inline
      comment after the numbers, a `;` separator, quoted fields.
- [ ] Decide, and record as `Decided YYYY-MM-DD:`, whether an inline
      trailing comment is stripped (a report) or refused, and whether `;`
      and quoted CSV are refused by name or read by a separate format
      entry.
- [ ] Tests in `tests/test_readers_robust.py`; every existing xy fixture
      reads unchanged with no new diagnostic.
- [ ] Skill: the diagnostics reference row for any new code. Nothing else
      expected.

## Acceptance

A decimal-comma file raises naming the separator. A text row inside the
data is reported by line. The 55 existing xy-dispatched files read with the
same arrays and no new diagnostic.

```sh
.venv/bin/python -m pytest tests/test_readers_robust.py tests/test_readers.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #897.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #897).
  Checked against the tree at `d80ca5f4`: headers, comments, commas and an
  esd column already read, and the decimal-comma misread, the silent
  mid-file drop and the bare refusal reproduce. No open WP owns it: WP-1332
  (the arity gate) is closed, WP-1522 carries reader diagnostics to the
  GUI and not their content, and WP-1315 and WP-1316 are containers.
  *Next:* task 1.
