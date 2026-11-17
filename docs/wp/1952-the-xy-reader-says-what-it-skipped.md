# WP-1952 — the xy reader says what it skipped

Milestone: unscheduled · Status: 🔄 2026-11-17 — counts warning and the TEMP decision in PR #1659; the pdCIF naming remains, once PR #1471 merges
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

- [x] Report non-numeric lines after the first data row, by line number:
      `PATTERN_ROWS_DROPPED` widened, or a sibling code (record which).
      Decide whether a `nan` or `inf` value is such a row.
- [x] Refuse a decimal-comma file by name. Detect it where a comma sits
      between digits with no space, and every row has the same comma count.
      Test on the 1° and 0.02° steps.
- [x] The "no numeric data found" refusal names what it saw: an inline
      comment after the numbers, a `;` separator, quoted fields.
- [x] Decide, and record as `Decided YYYY-MM-DD:`, whether an inline
      trailing comment is stripped (a report) or refused, and whether `;`
      and quoted CSV are refused by name or read by a separate format
      entry.
      Decided 2026-11-09 (settled by Claude, see the handover entry): a
      trailing `#` or `!` comment is stripped silently; `;` is read as a
      separator; quoted fields are refused by name; no CSV format entry.
- [x] Tests in `tests/test_readers_robust.py`; every existing xy fixture
      reads unchanged with no new diagnostic.
- [x] Skill: the diagnostics reference row for any new code. Nothing else
      expected.
- [x] The σ ≤ 0 rule (Inherited, WP-2002 B5, ruled 2026-10-19), for every
      format: a channel whose σ ≤ 0 takes no weight by default
      (`PatternData.nonpositive_sigma = "exclude"`, read by
      `in_range_mask`), `read_pattern` warns with the count and the 2θ
      (`PATTERN_SIGMA_NONPOSITIVE`), and the `nonpositive_sigma="poisson"`
      reader option keeps such channels at √max(y, 1). The floor
      (`_floor_sigma`, `SIGMA_FLOOR_RELATIVE`) goes, and so does `gsas`'s
      silent drop of such channels.
- [x] The σ-rule record field (Inherited, WP-2002 B14):
      `RefinementResult.sigma_rule` and `HistogramResult.sigma_rule`, a
      `SigmaRule` of three counts, built by `PatternData.sigma_rule` at
      compile.
- [x] The counts warning (Inherited, WP-2002 B5.2): a file with no σ column
      whose intensities do not look like counts. Built 2026-11-17 as
      `PATTERN_INTENSITY_NOT_COUNTS` on `read_pattern`'s hook, for every
      format: an intensity between 0 and 1 or below 0, with no threshold.
- [x] The second `TEMP` value (Inherited, issue #1064). Decided 2026-11-17
      (settled by Claude, see the handover entry): the first value stays
      `temperature_k`, the one the manual names, and the others are not
      surfaced (`io/CLAUDE.md` § Metadata). No code change; the evidence is
      in `io/formats/xy.py`'s docstring and a test on two D1B files.

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
- Issue #1448, fixed by PR #1541.

## Handover log

### 2026-11-17 — the counts warning lands, the TEMP line is decided (PR #1659, ghostshift runner)

A pattern that comes with no usable σ is weighted as if its intensities were counts, √max(y, 1), and until now nothing said when they could not be. An intensity between 0 and 1, or below 0, is no count, and the fallback gives it σ = 1: a pattern normalised below one count was fitted unweighted, in silence. The reader now counts such points and names where they sit, for every format, with no threshold, since one such value is already proof. A column scaled but never below 1 stays silent, because it is weighted right up to one factor, which moves χ² and no parameter or esd. No tracked file fires. Separately, the second (and third) value on an `XYDATA` file's `TEMP` line is settled: the first stays the temperature, and the others are not surfaced.

*Done* (commits `7fc9f070f`, `0833ed45a`, `e9f9c2d7b` on top of the claim `7c5e6671e`, then `origin/main` merged):
- The counts warning (B5.2): `PATTERN_INTENSITY_NOT_COUNTS`, on `read_pattern`'s hook beside the σ ≤ 0 rule (`readers._not_counts_diagnostics`). It fires when the pattern has no σ after that rule (so also when a column with no positive σ was declined) and holds a finite intensity strictly between 0 and 1 or below 0. A zero is not counted: on raw counts one count at a zero count is the floor's purpose. It fires beside `PATTERN_INTENSITY_SCALED` too, since that code gives no count of the points at the floor (the review's change, below). Audit rows: code tier 1 (arithmetic, no threshold), suggestion tier 1, kind 3. `help.py`, the skill's diagnostics row (three copies), the manual's pattern-files page, a silence pair, and five test functions in `tests/test_readers_robust.py` (one parametrized over the real fixtures). Two existing `.raw` tests now expect the new code beside `PATTERN_INTENSITY_SCALED`: the scrambled v4 fixture (a third of its values negative) and the scaled v2 file (0.25 and -2.0).
- The second `TEMP` value: decided, no code change. ILL D1B writes three values on every one of the 26 tracked `XYDATA` files (three are planted copies). The third is a round number on each (300, 100, 120, 1.5); the first lies within 6.5 K of it on every run with a sample, and reads 330 on the empty cryostat at 120 K. That is the shape of a set point and a sample sensor, though no document either side holds says so. The first is what the manual names (`tsamp`) and what the reader already took; `io/CLAUDE.md` § Metadata rules that a reader surfaces only a coordinate the format names, so the others stay unread. Recorded in `io/formats/xy.py`'s docstring and the manual, pinned by a test on two D1B files.
- `### Inherited` is deliberately not pruned, though all three entries are now consumed (B5.2 here; #1064's two parts by PR #1279 and its TEMP question here; #1240 by PR #1241, merged 2026-10-31). Held PR #1471 inserts an entry at the top of that section, and deleting the entries beside it would conflict that PR. The session that takes #1471's entry deletes them.

*Measured*:
- Census of every tracked file `read_pattern` opens (all formats, `.cif` under `tests/data`, `examples`, `data`): 59 read with no σ (47 `xy`, 12 others), and 58 hold no intensity between 0 and 1 or below 0. The 59th, the synthetic `bruker_raw4_scrambled.raw` (2335 such points, 2320 of them below 0), fires beside its `PATTERN_INTENSITY_SCALED`. The three pdCIF patterns all carry σ.
- Fast selection (`-m "not slow"`, `-n 4`), `[dev]` venv, arm64 Mac, under ghostshift's serial lock, on the merged tree `227ce207b` (the branch with `origin/main` merged, before this entry): 14 726 passed, 432 skipped, 32 xfailed, 0 failed, in 12:38 wall. An earlier run on `0833ed45a`, before the review's fixes and the merge, gave 14 713 passed; main moved between the two, so they do not subtract. The 12 added test cases (6 functions) cost 0.19 s in all (`tests.added_test_times` on that run's junit).
- `python -m tests.reader_output`: exit 0, unchanged (it covers one standard fit's printed text, which carries σ). ruff clean. Vale (`rietx_vale.sh`, CI's step): 0 errors at warning level.

*What a reader receives* (for the maintainer, per the 2026-11-01 ruling on reader output): one new warning, `PATTERN_INTENSITY_NOT_COUNTS`, only on a file with no σ that holds such values: "N of M points have an intensity no count can take (k between 0 and 1 and j below 0), at 2θ …, and the fallback gives each of them σ = 1." Its suggestion: "If the intensities were scaled or had a background subtracted, supply σ carried from the raw counts, or quote χ² and esds knowing the weights are assumed." No field, no fit number and no refusal changes.

*Review*: a read-only Opus reviewer inside the worktree (the project's `/code-review` edits the main checkout, so it was not run). No correctness bug. One defect, fixed: the message said "the file gives no σ", false where the hook had declined a column with no positive σ; it now says "no usable σ", in the help and skill rows too. Nits fixed: the zero exemption stated for raw counts only, the TEMP test's "set point" made "a round value", spacing and a reflow. One nit answered rather than coded: on a column scaled above 1 that holds zeros, the zeros are weighted at σ = 1 and nothing fires; the fractional values that reveal such a scale are what fires, and counting zeros would fire on raw counts.

*Generality*: the judge (`.claude/agents/generality-review.md`, run as an Opus agent) ran on `0833ed45a`. Its verdicts, condensed; every finding is kept:

> **`PATTERN_INTENSITY_NOT_COUNTS` (code) — holds.** Kind 1 and tier 1 agree. Weak on two questions: the "non-integer at low counts" half of B5.2 was dropped without a ruling, and a column not proportional to counts and above 1 (an offset background, a slit correction) stays silent with wrong relative weights. `responds` named only χ² and esds, though an all-floor fit moves the parameters too. Every firing case is synthetic; the census was not listed.
>
> **`PATTERN_INTENSITY_NOT_COUNTS.suggestion` — holds.** Minor: a negative value can be a masked channel's placeholder, where the remedy is to exclude the point.
>
> **The suppression after `PATTERN_INTENSITY_SCALED` — weak, the case against stronger.** That code's skill row says the parameters are largely unaffected, false exactly when the floor binds everywhere, and it gives no floor count; nothing recorded that the new code was withheld.
>
> **The `TEMP` decision — holds.** Kind 1 by the format's definition. Partial: the empty can reads 330 K at a 120 K set point with no message, and nothing records that the line held more values. One family (ILL D1B).

Author's answers, in `e9f9c2d7b`:
- Suppression: removed; both codes fire, and a test pins it with a shared list.
- `responds`: now names the parameters where most points sit at the floor.
- The non-integer half: not built, and asked of the maintainer in the PR. Integrality cannot tell a proportional column from an offset one, so it would not catch the judge's case either, and it would fire on 19 tracked patterns that are weighted right up to a constant.
- Census: listed above under *Measured*.
- Masked-channel negatives: declined; no reader here writes one with no σ (recalled by the judge, not found in the tree).
- `TEMP`: the other values stay unrecorded, by `io/CLAUDE.md` § Metadata; the empty can has no sample, so its 330 K describes nothing a series would key on.

*Settled for you* (each could have gone the other way):
- The rule is "an intensity between 0 and 1 or below 0", not B5.2's "maximum about 1 or less, or non-integer at low values". Grounds: it needs no threshold, and it fires exactly where the fallback is wrong. The alternative, any non-integer value, would fire on 19 tracked patterns that say nothing today (the twelve LLB G41 files and seven TOPAS exports), whose weights are right up to a constant.
- It lives on `read_pattern`'s hook for every format, not in `xy` alone. Grounds: the fallback is format-agnostic, as the σ ≤ 0 rule and `PATTERN_SIGMA_CONSTANT` are. The alternative was `xy` and `chi` only.
- It is a warning, not info. Grounds: B5's ruling, "warn during ingestion". The alternative was info for a handful of points.
- The `TEMP` line's first value stays the temperature (above).

*Decision for the maintainer*: whether to add B5.2's second half, a warning on non-integer values at low counts. Built as "any non-integer value with no σ", it fires on 19 tracked patterns that say nothing today (the twelve LLB G41 files, the seven TOPAS exports), all weighted right up to one constant.

*Next*: the pdCIF naming in this reader's "no numeric data found" refusal, once held PR #1471 merges and brings its `### Inherited` entry (with or after WP-1933's sniff). Then delete the three consumed `### Inherited` entries and close the WP.

### 2026-11-13 — Yue's rulings recorded, main merged (PR #1541, ghostshift runner)

Ruled by Yue 2026-11-13, on PR #1541:
- The reader output is approved as built, under the 2026-11-01 ruling on reader output. That covers the two forms of `PATTERN_SIGMA_NONPOSITIVE`, the `nonpositive_sigma=` refusal, the changed "fewer than 10 points" refusal and the three new fields. The lead's wording nit on "states no weight" was not taken, so the text ships as built.
- The default stays "no weight": a point whose σ ≤ 0 is left out of the fit, and the reader warns. Yue's reason: practitioners rarely think about weights, so the package must catch a gross weight error itself. It must not invent a σ, because √y is wrong by an unknown factor on a rescaled file. This answers the 2026-11-12 entry's decision for the maintainer.
- The option name `nonpositive_sigma` is accepted.

The audit row `RefinementResult.sigma_rule` now quotes that reason in its grounds, and its `approved` date moves from 2026-10-19 to 2026-11-13. The generality review had noted that the earlier date quoted no sentence of the maintainer's naming the default.

PR #1541 also fixes issue #1448, as ruled 2026-11-13 under the triage of PR #1471. That issue reports that the `gsas` reader dropped every zero-esd point in silence, and returned no σ in silence when the whole bank had zero esd. Since this WP the reader keeps those points, the fit leaves them out with the warning, and an all-zero column falls back to the Poisson σ with the warning. The PR body carries "Closes #1448".

`origin/main` (about 80 commits) merged into the branch without a conflict.

*Measured* on the merged tree (`ff57cfef5`), `[dev]` venv, arm64 Mac, through ghostshift's serial lock: the fast selection (`-m "not slow"`) ran 14 616 passed, 429 skipped, 32 xfailed, 0 failed, in 28:42 wall. `python -m tests.reader_output` exited 0, unchanged against `origin/main`. ruff is clean. Vale reports 0 errors at warning level on `docs/docs` and the tutorial prose.

*Next*: unchanged from the 2026-11-12 entry.

### 2026-11-12 — the σ ≤ 0 rule and its record field land (PR #1541, ghostshift runner)

A point whose esd in the file is zero or negative now takes no weight. Until now rietx floored such an esd at a thousandth of the column's median, which gave the point about a million times its neighbours' weight, in silence (#897). On a synthetic LaB6 with one σ = 0 at the strongest channel, that floor held the fit at its iteration limit with the cell 1.75e-3 Å from the truth. With the rule the fit converges to within 2e-4 Å. The point stays in the pattern with the file's own number, and the reader warns with `PATTERN_SIGMA_NONPOSITIVE`, naming how many points, how many record an intensity of zero, and where they sit in 2θ. The read option `nonpositive_sigma="poisson"` keeps them instead, at the Poisson σ = √max(y, 1). A column with no positive esd at all is not read, and the Poisson σ applies to the whole pattern. Every fit's result now carries `sigma_rule`, three counts of how many fitted points the file's σ, the Poisson σ and the exclusion covered. The counts warning (B5.2) is not built here.

*Done* (commits `69bb437fc`, `7411431ed`, `cc00ce9f6` on top of the claim):
- Task 1, the σ ≤ 0 rule (WP-2002 B5). It lives once, on `read_pattern`'s post-read hook (`_apply_nonpositive_sigma`), for every format, and the schema enforces it through `PatternData.in_range_mask`. `PatternData.nonpositive_sigma` is the new field, default `"exclude"`. `SIGMA_FLOOR_RELATIVE` and `_floor_sigma` are gone, and `RefinementResult.sig()` follows the same rule. Four readers declined or dropped such a σ themselves and now hand it to the hook: `gsas` dropped every σ ≤ 0 channel in silence, and `xy` and `chi` declined a column with no positive entry in silence.
- Task 2, the record field (B14). `SigmaRule` (`n_file_sigma`, `n_poisson_sigma`, `n_nonpositive_excluded`) is built by `PatternData.sigma_rule` over the fit's own window in `compile_model`, and copied to `RefinementResult.sigma_rule` and `HistogramResult.sigma_rule`. `SCHEMA_VERSION` 0.61 carries an "Also in 0.61" note.
- Siblings fixed. The dead-channel check at read time leaves out the channels the rule excluded, and under `"poisson"` it reads the stand-in σ the fit will use, so it agrees with the fit's own check. `BackgroundFixedPlusChebyshev.from_pattern` follows the rule. `compile_model`'s "fewer than 10 points" refusal names the σ rule when the rule emptied the range. A project made before this WP on a GSAS file with σ ≤ 0 channels still opens (`project._pre_1952_gsas_fingerprint`), because the reader now keeps channels it used to drop.
- Audit table: code row `PATTERN_SIGMA_NONPOSITIVE` (tier 1), its suggestion row, and the action row `RefinementResult.sigma_rule` (tier 2, kind 3, `approved` 2026-10-19). The `SIGMA_FLOOR_RELATIVE` row is deleted. `help.py`, the manual's pattern-files and result pages, the skill's diagnostics row, `docs/practice.md` § A zero or negative esd, `io/CLAUDE.md`'s repair table and the root CLAUDE.md's Weights bullet are updated. The `io/CLAUDE.md` line cap moves 571 → 572, logged.
- Tests: in `tests/test_schemas.py` (the LaB6 fit, plotted to `tests/output/sigma_rule_lab6_fit.png`), `tests/test_readers_robust.py`, `tests/test_data_support.py` and `tests/test_project.py`. The dead-channel and old-project tests were each made to fail once on purpose, and failed with the expected message.

*Outside this WP's files*: `src/rietx/refine.py` and `src/rietx/multi.py` each gained one line, `sigma_rule=model.sigma_rule,`, where they build the result. Another runner works in `refine.py`; this is a keyword argument and nothing else.

*Measured*:
- LaB6 probe (above), against `main`'s tree in a scratch snapshot: `main` stops at max_iter at a = 4.15835 Å (truth 4.1566, start 4.1585); the branch converges at a = 4.15662 Å.
- Census of the tracked pattern files `read_pattern` opens: only the two ILL D1B `.dat` files under `tests/data/d1b_co3o4_quench/` carry σ = 0, at y = 0 on the edge channels 0.79-0.89° and 128.59°. These are unmeasured channels. They were floored before and are now excluded with the warning. No tracked text file has a third column without a positive entry, so the `xy`/`chi` change moves no fixture.
- `python -m tests.reader_output`: exit 0, unchanged. It covers one standard fit's printed text.
- Fast selection (`-m "not slow"`), `[dev]` venv, arm64 Mac, on `503af0aa7` through ghostshift's serial lock, which held other suites off: 14 586 passed, 424 skipped, 32 xfailed, 2 failed, 13:52 wall. Both failures were this branch's own. The new warning code had no silence pair in `tests/silence.py`, and the new `help.py` entries left `tests/data/gui/help_keys.json` stale (the test rewrote it). Both are fixed in the next commit, and those two files then ran 41 passed. The whole selection was not re-run, since the fix touches only those two test inputs. `main` has moved since the 2026-11-09 entry's count, so the two totals do not subtract. The 12 added test functions cost 6.0 s in all (`tests.added_test_times` on a local junit run), 4.2 s of it the LaB6 fit. ruff clean. Vale: 0 errors at warning level on `docs/docs` and the tutorial prose, after one word on a line this branch wrote. The full suite did not run: no acceptance fixture carries σ ≤ 0, so no pinned fit number moves (`tests/CLAUDE.md` § Running, rung 3).

*What a reader receives* (for the maintainer, per the 2026-11-01 ruling on reader output):
- A new warning, `PATTERN_SIGMA_NONPOSITIVE`, in two forms. "N of M points have a σ of zero or below (k zero and j negative), at 2θ …. n of them record an intensity of zero. Such a σ states no weight, so these points are left out of the fit." And "every one of its M σ values is zero or negative (…), so the column states no weight and was not read. The Poisson σ = √max(y, 1) is used instead."
- A new refusal: "reader option nonpositive_sigma= takes one of …".
- New fields: `RefinementResult.sigma_rule`, `HistogramResult.sigma_rule`, `PatternData.nonpositive_sigma`.
- A changed refusal: "fewer than 10 points remain in the fit range" gains a clause naming the σ rule when it is the cause.
- The fit itself moves wherever a file carries σ ≤ 0: those points used to weigh ~10⁶× their neighbours and now carry none.

*Review*: `/code-review high --fix` raised nine findings. It fixed four (a stale `from_pattern` docstring, a duplicated span builder now shared as `formats.base._point_runs`, the XYDATA `INTER` message on a declined column, and NaN in `nonpositive_sigma_mask`). This session fixed three more (old GSAS projects, the read/fit dead-channel disagreement, the too-few-points message). Two are declined. The `where` list of run strings is uncapped, as `PATTERN_ROWS_DROPPED`'s already is, and capping one alone would make them differ. `compile_model` converts σ to an array three times, an O(N) cost per compile that is small beside a fit.

*Generality*:

The judge ran on the branch at `69bb437fc`, before `7411431ed`. Its report is condensed here: every verdict and finding is kept, and the per-question tables are cut. The author's answers follow it.

> **`PATTERN_SIGMA_NONPOSITIVE` (code row) — holds.** It reports an arithmetic fact with no threshold. Two findings. The tier-2 citation (GSAS-II's `fxye` zero weight, checked in 5.8.4's source) backs the action, not the warning, and no surveyed program warns; a threshold-free fact is tier 1. And the "every σ ≤ 0" branch could not fire for `xy` or `chi`, whose readers declined such a column in silence (`xy.py:463`, `chi.py:90`), while the manual's row said it fires.
>
> **`PATTERN_SIGMA_NONPOSITIVE.suggestion` — weak.** Whether the points counted zero is a fact about the writing software, so kind 3, not 1. The message gives only 2θ positions, not the numbers that separate the cases: y at those points, or σ²/y over the rest of the column. On D1B the zeros sit at y = 0, unmeasured, and following the suggestion there weights each ~3000× its neighbours (inferred).
>
> **`RefinementResult.sigma_rule` (action row) — weak.** The default is the stronger case against Poisson, but three things are wrong. Its kind is 1 while its own grounds name dissenters (GSAS-II's `xye` reader, FullProf), so it is kind 3. Its only measurement compares exclusion with the deleted floor, not with Poisson; the D1B case is the one that separates them. And `approved` quotes the batch lead's reading of the ruling, not a sentence of the maintainer's naming the default.
>
> **`SIGMA_FLOOR_RELATIVE` (deleted) — holds.** Nothing supports keeping it.
>
> **A column with no positive σ is not read — holds, with a coverage gap.** Same `xy`/`chi` gap. A hand-built `PatternData` with every σ = 0 fails in `compile_model` with "fewer than 10 points remain", which does not name σ.
>
> **The `"poisson"` value √max(y, 1) — holds** on raw counts. On scaled data one count is not one unit, a limit the declined σ²/y test would have covered. `POISSON_FLOOR_COUNTS`' evidence does not name this consumer.
>
> **GSAS no longer drops σ ≤ 0 channels — holds.** Same χ², now reported. A project made before sees matching bytes and a different fingerprint.
>
> **The dead-channel check skips excluded channels — holds.** No test covers the skip. Under `"poisson"` the stand-in σ reaches `dead_channels`, which its docstring refuses.

Author's answers, landed in `7411431ed` and `cc00ce9f6`:
- `xy`/`chi` gap: both readers now hand the column to the hook, and the "every σ ≤ 0" test is parametrized over `xy`, `chi` and `gsas_esd`. No tracked file changes (census above).
- Kinds and tier: the code row is tier 1. The action and suggestion rows are kind 3, with the grounds saying why a default must still act and how the warning and the option answer that. `POISSON_FLOOR_COUNTS`' evidence names the new consumer.
- Suggestion: the message now says how many flagged points record y = 0. The σ²/y test stays declined under the little-effort ruling.
- Approval: brought to the maintainer below.
- Hand-built all-zero σ: the refusal now names the σ rule. The column is not set aside inside `PatternData`, since that would change what a σ the caller wrote means.
- Old projects: `Project.open` also accepts the pre-WP-1952 `gsas` fingerprint.
- Dead-channel check: under `"poisson"` it now reads the stand-in σ the fit uses, so it agrees with the fit's own check rather than skipping. Tested both ways.

*Settled for you* (each could have gone the other way):
- The `"poisson"` option weights a σ ≤ 0 point at √max(y, 1), not at a literal σ = 1. Grounds: rietx's own no-σ fallback and TOPAS's 1/Max(Yobs, 1). The alternative was FullProf's σ = 1, which agrees at y ≤ 1.
- The `"poisson"` option reports nothing. Grounds: the caller asked by name, and the 2026-11-01 ruling against reports nobody needs. The alternative was an info line.
- A column with no positive esd is not read, rather than excluding every point. Grounds: the `pdcif` reader's precedent (`PATTERN_WEIGHT_UNUSABLE`) and that excluding all leaves nothing to fit. The alternative was refusing the file.
- The rule lives in the schema plus one reader hook, not per reader and not as `excluded_regions`. Grounds: io/CLAUDE.md's rule that a repair is reported where it is made, and the project rule that `excluded_regions` are the caller's settings. The alternative was writing the points into `excluded_regions`, which a project would then save as settings.
- The message counts how many flagged points record y = 0, so the reader can judge the suggestion's "if these counted zero". Grounds: the generality review. The alternative was B5's σ²/y ratio test, declined as more effort than the ruling allows.

*Decision for the maintainer*: the action row's `approved` date quotes your 2026-10-19 words ("fix anything obviously wrong, warn during ingestion, and give the option to correct"). The default itself, no weight rather than Poisson weight, is the batch lead's reading of those words (`docs/wp/2002-batch/rulings.md` lines 76-83). The generality review noted no sentence of yours names the default. If you meant Poisson by default, the change is one literal in `PatternData.nonpositive_sigma`.

*Not built*: the counts warning (B5.2). It is a heuristic of its own with a threshold to audit, and the ruling asked for little effort. It stays in Inherited.

*Next*: the counts warning (B5.2), the second `TEMP` value, and the pdCIF naming in this reader's refusal once PR #1471 merges (with or after WP-1933's sniff).

### 2026-11-09 — the six tasks land (PR #1504, ghostshift runner)

The two- and three-column text reader now says what it skips and refuses what it would misread. A line inside the data that is not a row of numbers, such as `10.2 n/a`, used to vanish. It is now named by line. A header above the data and a footer below it stay silent. A file that writes a comma inside a number used to read as a different pattern with no word. That covers a decimal comma (`10,02`) and a thousands separator (`1,234`), and such a file is now refused by name. A trailing `# note` no longer costs its row, `;` separates columns as `,` already did, and the "no numeric data" refusal now names what it saw. Over all 174 tracked files this reader opens, every array reads identically, and no pattern gains a diagnostic. Still open here: the inherited σ ≤ 0 rule with its record field, the counts warning (B5.2), the second `TEMP` value, and the pdCIF naming that PR #1471 adds to Inherited.

*Done* (commits `d36b5f0a8`, `36958de59`, `b891648f5`, `cc06bc5b3` on top of the claim):
- Task 1. `PATTERN_ROWS_DROPPED` was widened rather than given a sibling code. The new report is a second diagnostic under the same code, and the column-count message stays byte for byte. It covers lines between the first and last row at the file's column count. A `nan` or `inf` is a number and was already reported by its 2θ through the finite-row drop (WP-2079), so it is not such a row.
- Task 2. One rule covers the decimal comma and the thousands separator: a whitespace- or `;`-separated field that is a whole number once its commas count as part of it. One such row refuses the file. The WP's "every row has the same comma count" was too strict, because an exporter that drops trailing zeros writes `10` beside `10,5`. The first draft's half-the-rows threshold missed a 0.5° step with an odd row count, which the generality judge found, and it missed a thousands separator in a decimal-point file (`10.00 1,234` read as y = 1, σ = 234), which the code review found. A decimal comma and a thousands separator cannot be told apart, so the message names both.
- Task 3. The no-data refusal now names one of four causes: quoted fields (only when the line reads as numbers with the quotes removed, since prose with quotes appeared in the census), a file of comments, an XYDATA heading with nothing below it, or the first line that is not a comment. An inline comment no longer causes a no-data refusal, since it is stripped.
- Task 4 is under the task line. It was settled by Claude, because no trigger in the triage rule sends it to the maintainer. The grounds are GSAS-II 5.8.4's importers (both read `;`; a quoted field fails) and WP-1332's fence for quoted CSV. A trailing comment changes no number, so it is stripped without a report, as a comment line is. Only `#` and `!` open one mid-row, because inside a row `'` and `/` begin a quote or a path; with them included, the census moved 101 agent-log files. `;` now also opens a comment line (Bruker's marker), or a `;`-led line would read as a row.
- Tasks 5 and 6. 18 tests in `tests/test_readers_robust.py`, plus one from the review there. The review also added two `.pks`/`.udi` cases inside an existing test in `tests/test_readers.py`. The skill's `PATTERN_ROWS_DROPPED` row, `help.py`, the manual's pattern-files page, `io/CLAUDE.md`'s xy row and a new `docs/practice.md` section are updated. The audit table's `PATTERN_ROWS_DROPPED.suggestion` site count goes from 2 to 3.

*Measured*:
- Census of every tracked file `identify_format` sends to `xy` (scratch script, before against after on this branch): 356 files dispatched, 174 read before and after. Zero array changes. Diagnostics differ on 51 files, all agent trail logs under `docs/wp/1504-eval/`, none of them patterns.
- `python -m tests.reader_output`: exit 0, unchanged. It covers one standard fit's printed text, so it cannot see the new reader messages.
- Gates on this branch (main had not moved, `eee8486d5`), arm64 Mac, `[dev]` venv: fast selection (`-m "not slow"`) 14 359 passed, 417 skipped, 32 xfailed, 0 failed, 8:26 wall through ghostshift's serial lock, nothing else running. The 16 added test functions (19 cases) cost 0.16 s in all (`tests.added_test_times`). ruff clean. The full suite did not run: the change is reader-only and moves no measured number of a fit (`tests/CLAUDE.md` § Running, rung 3).

*What a reader receives* (for the maintainer, per the 2026-11-01 ruling on reader output): one new warning text under an existing code ("N line(s) inside the data (lines A-B) do not read as a row of numbers and were not read as data (line k: '…')"). Also three new refusal texts: the comma inside a number, quoted fields, and the cause added to "no numeric data found in <path>: …". No result or report field changes.

*Review*: `/code-review high --fix` raised eight findings. It fixed four (the `.pks` escape gate, the XYDATA no-data cause, the comma test's cost, "three causes" in the skill row). This session fixed two more (the thousands separator, the footer). Two are declined, with reasons:
- A numeric header row at the data's column count moves "first data row" up, so text below it is reported. That row is already read as a point (the #266 limit), and the report at least points at the region.
- A file quoting only some cells reads its unquoted rows, and the quoted ones are reported by line rather than refused. They are reported, so nothing is silent.

*Generality*:

The judge ran on the branch at `36958de59`, before `cc06bc5b3`. Its report is condensed here: every verdict and finding is kept, and the per-question tables are cut. The author's answers follow it.

> **`PATTERN_ROWS_DROPPED.suggestion` (suggestion row, site count 2 → 3) — holds.** The case for the new suggestion is stronger. It is conditional, prescribes nothing the reader can't tell, and the row is unchanged apart from its count. (1) It decides nothing: one fix, conditional on a fact only the user holds. (2) Kind 3: "A line inside the data is a lost point or a note, and the reader cannot tell which" (`help.py`). (3) Case against: none found. (4) Case for: the one step that recovers a lost point, at the cost of one re-read. (5) Tier: no name was added to `UNAUDITED_BASELINE`, so no reason is owed. Separate finding: the code row `PATTERN_ROWS_DROPPED` (`_audit.py:984`) is also unaudited, with no response level and no `responds` sentence. This change gives that unaudited code a new trigger, which the table shows only as the count's +1. (7) `where=["line N", …]`, `value` = count, present. What would change the verdict: none expected. The open item is auditing the code row itself.
>
> **Decimal-comma refusal — weak.** The case for refusing, rather than reading the split numbers, is much stronger than the case against. But the half-the-rows threshold and the mixed-row rule rest only on synthetic tests. No test covers the case the author gives for replacing the WP's rule.
> - (1) Two decisions. (a) The file is not read. (b) It is refused rather than converted.
> - (2) (a) is kind 1. (b) is kind 2 or 3: converting is a real alternative, and a thousands separator (`1,234`) makes conversion ambiguous.
> - (3) Against refusing at all: none found. GSAS-II 5.8.4 splits the number silently (`G2pwd_xye.py:166`), which is a misread, not a competing judgement. Against the threshold:
>   - (i) At a 0.5° step with integer 2θ and an odd row count, the comma rows are (N−1)/2 of N. The file is not refused, and those rows are dropped under `PATTERN_ROWS_DROPPED` with the wrong cause, so up to half the pattern is lost under a misleading message. Nothing tests it.
>   - (ii) Integer x with thousands separators (`10 1,234`) is refused as a "decimal comma", which names the wrong cause.
>   - (iii) A file with a decimal point and thousands separators (`10.02 1,234`) is not caught. It reads silently as three columns, with σ = 234.
>   - Against converting: the WP's own fence leans towards refusing. FullProf, TOPAS, RIETAN-FP, BGMN and MAUD were not checked.
> - (4) Strong for refusing: the old behaviour gave a different pattern in silence. Unwritten argument for the threshold: at half or more, the comma rows would win or tie the column-count vote.
> - (5) The action is kind 1. The ½ threshold and the field regex are rietx's own (tier 3), and the ½ is an inline literal no tier records.
> - (6) The census is a negative control by file, with no decimal-comma file in it. The positives are synthetic, and both write `f"{…:.2f}"`, so the mixed `10` beside `10,02` case has no test.
> - (7) The message carries "N of the file's M rows".
> - What would change the verdict: a test with `10` beside `10,02`, a test at the 0.5° boundary, or one real decimal-comma export.
>
> **Trailing comments — holds.** The case for cutting silently is stronger. No number changes, and every damaged-data spelling tried still ends in a report. Kind 1. Mild case against: Excel's `#N/A` is cut, but that leaves a row of one number or a different column count, which is still reported. A note such as `# spike` marks a point as suspect, and the note is dropped without a word. GSAS-II reads `10.0 100 # c` but refuses `10.0 100 #c` (`G2pwd_xye.py:166-191`), which is accident, not a dissent. Case for: strong, since a row was silently lost before. Tier 3, low stakes. One real user file is the positive case. What would change the verdict: an exporter writing `#` or `!` inside a value, or a user relying on a trailing note to flag a point for exclusion.
>
> **`;` read as a column separator — holds.** Established practice, checked in source (`G2pwd_xye.py:166`, `G2pwd_csv.py:28,73`). Mild case against: a line opening with `;` (Bruker UXD's comment marker) now parses as a numeric row, and is read silently if its column count matches. Tier 2. What would change the verdict: a real export whose `;`-led comment lines carry numbers at the data's column count.
>
> **Report boundary — holds.** Reporting below the first row and staying quiet above it is the stronger case. Cases against:
> - (i) GSAS-II refuses instead (`G2pwd_xye.py:187-191`).
> - (ii) A footer (`End of data`) gets a warning on every file that has one.
> - (iii) A lost point on the very first data line is silent.
> - (iv) Message defect: `10.06 150.3 spike` is skipped and reported as "do not hold two numbers". It holds two numbers, and the point is lost.
>
> Tier 3. Reading on rather than refusing departs from GSAS-II without a stated reason. What would change the verdict: fixing the message, and writing down why the reader warns and continues where GSAS-II refuses.
>
> **No-data refusal cause selection — holds.** Only a refusal's wording is at stake, and refusing quoted fields matches GSAS-II (tier 2). What would change the verdict: a vendor whose only export is quoted numeric CSV.

Author's answers, landed in `cc06bc5b3`:
- Decimal comma (weak). One row with a comma inside a number now refuses, so there is no threshold. A whole-field match covers the decimal comma and the thousands separator, (ii) and (iii) among them. The message names both forms because they cannot be told apart. Tests added: `10` beside `10,5` at 0.5° with 21 rows (the boundary case), and `10.00 1,234`.
- Report boundary (iv, ii, i). The message now says "do not read as a row of numbers", and `10.3 130 spike` is in the test. The report stops at the last data row, so a footer is silent. The reason for reading on is written in `read_xy`'s docstring and `io/CLAUDE.md`: refusing loses every other point for one line the caller can judge.
- `;` (mild). A `;`-led line is now a comment line, tested.
- Unaudited code row `PATTERN_ROWS_DROPPED`: left for the audit's own pass. It stays on `UNAUDITED_BASELINE` as before.

*Not generalised*: the `chi` reader also reads `,` as whitespace, so a decimal comma would misread there too. `.chi` is written by Fit2D and pyFAI, which do not localise numbers, and its count gate would likely catch a split row. Left alone.

*Next*: the σ ≤ 0 rule and its `RefinementResult` record field (Inherited, WP-2002 B5 and B14), with the counts warning (B5.2) beside it. Then, once PR #1471 merges, the pdCIF naming in this reader's refusal, after or with WP-1933's sniff.

### 2026-11-03 — PR #1279 merged (from outside, @mustachefeeling)

PR #1279 (merge sha: 3f10c88f8) lands the two #1064 parts this WP inherited on 2026-10-26 and 2026-10-31. None of the WP's own six tasks is ticked by it.

- `INTER` multipliers are applied: x × `fac_x`, y and σ × `fac_y`, as the FullProf 2000 manual defines them (PDF p. 74, `Ins = 10`). A non-unit factor raises the info code `XYDATA_INTER_APPLIED`. Unit factors are silent. `Interpol = 1` stays refused, and a non-positive or non-finite factor is refused by name. With no σ column the reader takes σ = √(fac_y·w), w the written intensity, which FullProf 8.20 was measured to compute (black box, synthetic files).
- `read_pattern(path, axis="two_theta" | "tof")`: only `xy` honours it. The declaration is stored as `metadata["declared_axis"]`. A recognised unit that contradicts it is refused with both quoted. Other formats report `READER_OPTION_IGNORED`.
- Audit row `XYDATA_INTER_APPLIED` sits at tier 2, not the tier 1 the 2026-10-26 triage note proposed. The σ fallback rests on one program's measured behaviour, and `_audit.py` tiers each part of a heuristic on its own (settled by Claude under that docstring rule, review round 2).
- Still open here: the second `TEMP` value (#1064 stays open on it), the σ ≤ 0 rule and its record field, the decimal-comma refusal, line-numbered skip reports.

Gate on the merged tree (main 625b33678, arm64 Mac, `[dev,jax]`): fast 13 714 passed, 231 skipped, 34 xfailed, 1 failed (environmental Jupyter kernel spec); `-m slow` 922 passed, 16 skipped, 17 xfailed.

This entry lands in PR #1367.

*Next:* task 1, unchanged by this merge.

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #897).
  Checked against the tree at `d80ca5f4`: headers, comments, commas and an
  esd column already read, and the decimal-comma misread, the silent
  mid-file drop and the bare refusal reproduce. No open WP owns it: WP-1332
  (the arity gate) is closed, WP-1522 carries reader diagnostics to the
  GUI and not their content, and WP-1315 and WP-1316 are containers.
  *Next:* task 1.
