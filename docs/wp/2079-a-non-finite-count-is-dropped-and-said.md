# WP-2079 — a non-finite count or σ in a pattern file is dropped, and the reader says so

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-02 — a real file's dead channels reach the fit with no word from the reader; what a fit then does with them is not measured, and task 1 measures it

## Goal

Every pattern reader drops a row whose count, σ or 2θ is NaN or ±inf, and
says which rows it dropped by their 2θ range. No non-finite value reaches a
`PatternData`.

## Context

**The report (issue #1187).** `read_pattern` passes non-finite counts and σ
through, and no diagnostic names them. The reporter's file is
`PLANTED_nan_block_from_1023q_1p5K.dat` from #1162: a real ILL D1B `XYDATA`
file with counts and σ written `NaN` on 60 channels (2θ 30.79-36.69°). On
`main` at `1612e5ae`, `rx.read_pattern(path, diagnostics=d)` returned 1280
points, 60 NaN intensities and 60 NaN σ. Its only diagnostic was
`PATTERN_DEAD_CHANNELS`, for two other channels at 128.6°. Neither the
readers (`src/rietx/io/`) nor `PatternData` tests a value for being finite
(the issue's read, not re-checked here). NaN is how a normalisation by a zero
monitor or efficiency comes out, so a real file can carry it.

**The rule this meets.** A reader may repair a file only where it can say
that it did, and only where the deviation is a report rather than a
contradiction (root CLAUDE.md; `src/rietx/io/CLAUDE.md` § What a reader may
repair). A NaN states "no value here", so dropping its row invents nothing.
`PATTERN_ROWS_DROPPED` already reports dropped rows in the xy reader
(`io/formats/xy.py`). `base.pattern_data()` is the boundary every reader
crosses (`io/CLAUDE.md` § Refusals), so one check there covers every format.

**Decided.** Settled 2026-11-01 by Claude under the io rulebook's
reader-repair rule: drop the non-finite rows with a warning naming the 2θ
range, through the existing `PATTERN_ROWS_DROPPED` path, and check ±inf and
every reader format. The alternative was to refuse the whole file. That
would block a real ILL D1B file over 60 dead channels. The new message
changes what a read prints, so it goes to the maintainer before merge (the
reader-output rule; `python -m tests.reader_output`).

**Practice.** GSAS-II 5.8.4 zeroes such a point's weight, silently
(`imports/G2pwd_xye.py:200-201`; read 2026-11-01, not run). FullProf and
TOPAS were not checked.

**Owner check.** No open WP owns a finite-value check across readers.
WP-1952 (the xy reader's skip report) asks in its task 1 whether a `nan` or
`inf` value is a dropped row, for xy alone. Its file is being edited by an
open PR (#1279), so this was filed apart rather than folded. A session on
either WP reads the other's state first: the two share `PATTERN_ROWS_DROPPED`
and `tests/test_readers_robust.py`.

### Inherited

## Non-goals

- The xy reader's other silent drops (a text row inside the data, a decimal
  comma, an inline comment): WP-1952.
- σ ≤ 0 and its floor (`schemas.pattern._floor_sigma`): WP-1952 § Inherited.
- Carrying reader diagnostics into the GUI: WP-1522.

## Tasks

- [ ] Measure what a fit does today with the reporter's file: does it raise,
      return NaN, or return a number? Record it here. It sets how loud the
      new message must be.
- [ ] Drop every row with a non-finite 2θ, count or σ in `base.pattern_data()`,
      reported by `PATTERN_ROWS_DROPPED` with the count and the 2θ range of
      the dropped rows. A wholly non-finite file raises, naming the file.
- [ ] Tests in `tests/test_readers_robust.py`: NaN and ±inf in each column,
      through every entry of `io.readers.PATTERN_FORMATS` that can carry a
      float (a synthetic writer per format where one exists), and #1162's
      planted file. Every existing fixture reads with the same arrays and no
      new diagnostic.
- [ ] The reader-output approval for the new message text, before merge.
- [ ] Skill: the diagnostics reference row for `PATTERN_ROWS_DROPPED`, if its
      meaning widens. Nothing else expected.

## Acceptance

The planted D1B file reads 1220 points with one `PATTERN_ROWS_DROPPED`
naming 30.79-36.69°. No reader returns a non-finite value.

```sh
.venv/bin/python -m pytest tests/test_readers_robust.py tests/test_readers.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issues #1187 (the report) and #1162 (the planted file).

## Handover log

- **2026-11-02** — created by a ghostshift runner from the 2026-11-01
  decision briefs (§C item 1), to give #1187 an owner. No WP cited it. The
  closest owner, WP-1952, covers the xy reader alone and is being edited by
  PR #1279. Filed in PR #1317. Nothing was run; every number above is the
  issue's. *Next:* task 1.
