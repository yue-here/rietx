# WP-2105 — a TOPAS parametric input reads in

Milestone: parametric · Status: ⬜
Depends on: 1964 (the grammar an equation lowers onto)
Priority: P2 2026-11-04 — a feature the open milestone was opened for: a user's first act is to bring the input they already have

## Goal

`read_topas_inp` turns a parametric input into a `CoordinateTable`, `variables` and
equations, and refuses by name what it cannot carry.

## Context

`.inp` readers build no `ParametricEquation` today. WP-1325's real-data runs wrote each
protocol by hand, and `read_topas_inp` refused ZrP₂O₇'s `B1` macros outright, so that
run parsed the `str` blocks itself.

The two local inputs show what a real one is made of:

- `prm` at top level holds shared coefficients, some fixed with `!`, some with
  `val_on_continue` for restarts.
- `local` holds a per-pattern value, and an equation on a `local` is a per-pattern
  evaluation.
- `#list Files T_val Range_val` and `#define` generate the per-pattern lines. Macro
  text substitution comes first (TOPAS writes the expansion to `topas.log`). The reader
  either expands them or takes a TOPAS-expanded input.
- Spelling differs from the grammar in known ways: capitalised `Exp` and `Ln`,
  left-associative `^`, and implied multiplication such as `(height) Cos(Th)`.

Two lines in those inputs fall under the milestone's fence. Both need a stated outcome:

- WO₃'s `scale_pks = Exp(-2 b/(2 D_spacing)^2)` is one overall B per pattern. It
  depends on the reflection, but its effect is an added Biso, so the reader can say so.
- ZrP₂O₇'s `th2_offset` is a curve in `Xo`. It has no rietx form, so the reader reports
  it as dropped, with its size.

Rules that apply: `src/rietx/io/CLAUDE.md`, and a reader may repair a file only where it
can say that it did. **Corpus files are private**: a committed fixture carries synthetic
numbers at the file's own column widths, and the Durham inputs stay in the local data
root (root CLAUDE.md § Licensing).

## Non-goals

- GSAS-II `.gpx` sequential results into equations. They hold no equations to read.
- Writing parametric `.inp` out.
- Reflection-level or point-level equations.

## Tasks

- [ ] Inventory the constructs across both inputs, each marked read, reported or
  refused. Bring anything a reader cannot say honestly to the handover.
- [ ] Macro expansion: decide between a small expander for `#list` and `#define` and
  reading a `topas.log`.
- [ ] Lower TOPAS's expression spelling to the grammar, with a table of each rewrite.
  An exact rewrite is silent, and any other is a `Diagnostic`.
- [ ] Build the coordinates, variables and equations, and run the WO₃ input end to end.
- [ ] A synthetic fixture for the committed test.
- [ ] Manual: `switching/topas.md` § Reading an `.inp`.
- [ ] Skill: the foreign-inputs row, or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_topas_whole_input.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1433, WP-1530 (the `.inp` reader's grammar), WP-1118 (the TOPAS boundary).
- Evans, J. S. O. Durham TOPAS tutorials.

## Handover log

- **2026-11-04** — Filed on the opening of the milestone. No open WP owned it: 1455 and
  1973 each read one profile or texture construct. Next: the inventory.
