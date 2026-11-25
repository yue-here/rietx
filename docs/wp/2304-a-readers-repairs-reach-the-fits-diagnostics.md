# WP-2304 — A reader's repairs reach the fit's diagnostics

Milestone: unscheduled · Status: 🔄 2026-11-25 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-23 — a reader that rescales intensities and withholds σ says so only into a list the caller passed; a fit on it changes weights with no word in `result.diagnostics`

## Goal

What `read_pattern` repaired or noticed in a file reaches `result.diagnostics` of every fit
on that pattern, once per code, whether or not the caller passed `diagnostics=[]`.

## Context

**Today** (`io/readers.py`, `read_pattern` docstring, on `f9adf0e57`): "The refusal runs on
every call; the report ... only when a caller passed the list." So `PATTERN_INTENSITY_SCALED`
(an attenuator applied, σ withheld where the scale cannot be established),
`PATTERN_SIGMA_CONSTANT` and `PATTERN_SIGMA_NONPOSITIVE` reach no one unless the caller asked.
The fit repeats one of them on its own, `PATTERN_DEAD_CHANNELS` (`refine.py`). The rule for
repairs is root CLAUDE.md § Invariants, WP-1047: "A pattern reader may repair a file only
where it can say that it did." `src/rietx/io/CLAUDE.md` holds the dispatch and the repairs.

**The rule.** [DESIGN § Rules](../DESIGN.md#rules), 4, as amended 2026-11-23, and Rule 4's
test for a new output: an agent can write the next call from it without a rerun. An agent
reads `result.diagnostics` on every fit (the skill's rule 9). A python warning is the weak
channel: `Refinement.set_vary`'s docstring says a warning "can scroll past or show once per
call site", so one warning would cover a batch of 200 files.

**The design.** Carry the reader's notes on `PatternData` and have the fit copy them into
`result.diagnostics`, deduplicated by code against what the fit raises itself. The history
fingerprint is the sha256 of the 2θ and intensity bytes only (`schemas/history.py`,
`TreeHeader.data_fingerprint`), so a new field leaves it alone. A project stores the pattern
file's bytes, not a `PatternData`. Check every other place a `PatternData` is serialised
(the GUI's wire, `model_dump` round-trip tests, `SeriesResult`) before adding the field.

**In the review** (2302-batch/plans.md, Plan 2 D), a first draft also warned when no list was
passed. That was dropped for the channel reason above.

Tier: none. The notes are the reader's existing codes, already in `_audit`.

## Non-goals

- `Structure` and `Instrument` carry CIF and instrument-file repairs too
  (`CIF_SPECIES_NORMALISED`, `CIF_CELL_ANGLE_CORRECTED`). Both are stored in history nodes, so
  a field there is a stored-format change. It needs its own decision and its own WP.
- Changing any repair itself.

## Tasks

- [ ] List every place a `PatternData` is serialised or compared, and confirm a new field
  breaks none of them.
- [ ] `PatternData` carries the reader's notes; `read_pattern` fills it whether or not a list
  was passed, and still extends the list when one was.
- [ ] Each fit entry point copies the notes into `result.diagnostics`, one per code;
  `PATTERN_DEAD_CHANNELS` appears once.
- [ ] A series and a joint fit carry each pattern's notes (per pattern in a series, per
  histogram in a joint fit).
- [ ] `src/rietx/io/CLAUDE.md` § the repairs: the notes reach the fit.
- [ ] Tests: one fixture per repair code, read without a list, asserting the code in
  `result.diagnostics`.
- [ ] Skill: none. The codes already have rows; they now arrive where the skill already sends
  the agent.

## Acceptance

A file that triggers `PATTERN_INTENSITY_SCALED`, read with no `diagnostics=` list and fitted,
carries that code in `result.diagnostics` exactly once.

```sh
.venv/bin/python -m pytest tests/test_readers_robust.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Thomson, M. & Schinazi, D. (2023), RFC 9413, "Maintaining Robust Protocols": tolerance needs
  defined, visible handling.

## Handover log

- **2026-11-23** — created from the API review (2302-batch/plans.md). No open WP owns
  where a reader's notes land: WP-1952 is the xy reader's own skips, and WP-2146 the ISIS iparm
  repairs. Next: the serialisation survey.
