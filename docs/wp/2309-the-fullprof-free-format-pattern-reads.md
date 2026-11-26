# WP-2309 — FullProf's free-format pattern reads, and a misread names its cause

Milestone: unscheduled · Status: ⬜
Track: The formats a lab still has
Depends on: — (2304 soft: its routing carries a reader's notes into the fit)
Priority: P3 2026-11-25 — a reader nobody else is waiting for; the reporter converts the file by hand, and the two refusals name the wrong cause rather than passing a wrong pattern

## Goal

`read_pattern` reads a FullProf `Ins = 0` pattern (WinPLOTR's "INSTRM_0"): `!` comment lines,
one line of 2θ start, step and end, then counts ten to a line. A file the readers cannot read
is refused with a message that names what was found, never a binary format list or a
concatenated-range story.

## Context

**The report (issue #1834, 2026-11-24, from Mike).** Two public NPD files in this format,
`NPD/200 K/MAB_200K.dat` and `NPD/1.6 K/MAB_1p6K.dat` in the Mendeley Data deposit
doi:10.17632/btb6s33sxp.1 (Potashnikov et al., *J. Magn. Magn. Mater.* 2019,
doi:10.1016/j.jmmm.2018.09.078), are refused, and the refusal names the wrong cause either
way. Three asks: (a) the xy format should not claim a block whose rows hold ten numbers; (b) a
NUL inside a `!` comment line of an otherwise text file is not "binary", so name the bytes and
the line; (c) whether this format is in scope as a reader.

**Reproduced at `21c574dc6`** on a synthetic file of the same layout (a `!` title, a
`! Initial format:` line, `10.000 0.050 29.950`, 400 counts ten to a line):

- With a NUL in the `! Initial format:` comment, which WinPLOTR leaves there:
  `ValueError: … is not a powder pattern this build can read (it looks binary). Supported:
  Bruker/Siemens DIFFRAC binary …`. The cause is `base.looks_binary` (`io/formats/base.py:758`):
  any NUL in the first 4 kB, unless behind a BOM.
- Without it, `xy` claims the file. Its column-count rule (`formats/xy.py`, `read_xy`'s
  docstring) takes the most common count as the file's, so the ten-number rows become the
  data and their first two numbers read as (2θ, y). `base.ascending` then refuses: "2θ does
  not run in one direction — it goes 1000° → 996° at point 0. Concatenating, sorting or
  separating such ranges are three different measurements …". No range was concatenated.

**Scope (c). Decided 2026-11-25** (settled by Claude under WP-1047's purpose, "read the files
labs actually have", and practice): in scope. GSAS-II 5.8.4 ships an importer for it,
`imports/G2pwd_FP.py`, "FullProf 1-10 column .dat powder data file", which skips `!`, `#`
and `'` comment lines and expects a start, step, stop card. FullProf is closed, so the format's
facts come from Rodríguez-Carvajal's manual (*An Introduction to the Program FullProf 2000*,
LLB, July 2001), the same source `ATTRIBUTION.md` already cites for `XYDATA` (`Ins = 10`), and
from the real files. `src/rietx/io/CLAUDE.md` § Adding a format is the procedure: a fixture
licence checked per file first (the Mendeley deposit's licence is not checked here), spec
facts into a table, one module, a `PATTERN_FORMATS` position argued above `xy`.

**Facts to settle against the manual and the files before writing the parser.** Whether the
count line can hold fewer than ten values at its end, and what a short last line means; whether
the format allows an esd block (the issue says counts and no esd, so σ is the Poisson fallback
and the reader says the values are counts); whether a temperature or a monitor sits in the
header; and the NUL. GSAS-II's validator treats a non-ASCII or NUL line as an error only past
the third line.

**The two refusals.** The new reader removes both symptoms for this format and neither for the
next one, so each refusal is fixed in its own right:
- (a) `xy` reading a row of more than three numbers as (x, y[, σ]) is reading a layout it does
  not know. Refuse, naming the column count found and the line.
- (b) `looks_binary`'s NUL test is the guard that keeps a Bruker binary from becoming a
  `UnicodeDecodeError` (its docstring). A NUL on a `!` line of a file whose other bytes decode
  as text is a different case. At the least the refusal names the byte offset and the line it
  sits on. Whether such a file reads on with the byte reported is § What a reader may repair's
  question: a report, not a contradiction, so reading on with a diagnostic is the likely answer.

**Sibling WPs.** WP-1952 (🔄) owns `read_xy`'s report of what it skipped. Item (a) touches the
same function, so whichever lands second rebases. WP-2304 (open PR #1842) routes a reader's
diagnostics into the fit, so a note this reader emits reaches `RefinementResult.diagnostics`
once that lands.

Tier of what this WP adds: physics and the format's own statement, tier 1; the refusals record
what was found.

## Non-goals

- `fullprof.magnetic_reading(model, 1)` raising `AttributeError: 'int' object has no
  attribute 'isy'` (the same issue's smaller report). **Decided 2026-11-25** (settled by Claude
  under Python practice): the signature types `phase` as `FullProfPhase`, and the package does
  not check argument types beyond its choice arguments (WP-2302 owns those).
- Other FullProf `Ins` values. `Ins = 10` (`XYDATA`) is read by `xy` already.

## Tasks

- [ ] The fixture licence of the two Mendeley files, per file; vendor or record in
      `tests/data/README.md` per § Adding a format step 1.
- [ ] The spec table: the manual's `Ins = 0` description against the two files.
- [ ] `formats/fullprof_ins0.py` (or the name the table suggests), placed above `xy` with the
      reason; `capabilities()` and `READER_OPTIONS` follow by their meta-tests.
- [ ] (a) `xy` refuses a block of more than three numbers a row, naming the count and the line.
- [ ] (b) The NUL refusal names the offset and the line; read on and report where the rest
      of the file is text, if the table supports it.
- [ ] Tests: `test_readers.py` cases for the format, (a) and (b); the fixture in
      `test_readers_robust.py`; `tests.reader_output` reviewed, since reader output changes.
- [ ] Manual: the formats table in the readers reference page; `ATTRIBUTION.md` § Format
      specifications row.
- [ ] Skill: none expected. A refusal names its own cause, and the format list is generated.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_readers.py tests/test_readers_robust.py -q
.venv/bin/python -m tests.reader_output
.venv/bin/python -m ruff check src tests examples
```

Both deposit files read with the 2θ range their count line states, and the two synthetic
refusal cases name the column count and the NUL's line.

## References

- J. Rodríguez-Carvajal, *An Introduction to the Program FullProf 2000*, Laboratoire Léon
  Brillouin, version July 2001 (the `Ins` values).
- Potashnikov et al., *J. Magn. Magn. Mater.* (2019), doi:10.1016/j.jmmm.2018.09.078; data
  doi:10.17632/btb6s33sxp.1.
- GSAS-II 5.8.4, `GSASII/imports/G2pwd_FP.py` (practice; spec facts only).

## Handover log

- **2026-11-25** — created, from the 2026-11-25 issue triage (issue #1834). Checked against the
  tree at `21c574dc6`: both refusals reproduced on a synthetic file of the layout; no reader in
  `PATTERN_FORMATS` claims the format. No open WP owns it: WP-1952 owns `read_xy`'s skip
  report and no new format; WP-2146 owns the ISIS iparm files; the formats track holds no
  FullProf pattern reader. Next: the fixture licence, then the spec table.
