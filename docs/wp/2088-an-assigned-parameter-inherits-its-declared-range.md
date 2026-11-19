# WP-2088 — An assigned Parameter inherits its declared range

Milestone: unscheduled · Status: ✅ 2026-11-07 — an assignment inherits the declared range and leaves the other fields' objects in place (PR #1458)
Track: What fires, and what stays silent
Depends on: —

## Goal

`phase.lor_size = Parameter(value=0.01, vary=True)`, and every other
assignment of a `Parameter` (or a dict) to a field that declares a range,
inherits the range and unit it left out, exactly as construction does since
issue #204 and WP-1321.

## Context

- **The defect, measured 2026-11-04** (WP-1944 branch, `.venv` arm64,
  py3.12). On a `Phase` built with defaults, `lor_size` reads `min 0.0,
  unit deg`. Built with `lor_size=Parameter(value=0.01, vary=True)` it still
  reads `0.0, deg`. Assigned the same `Parameter` afterwards it reads
  `min -inf, unit None`. `atom.occ = Parameter(value=0.5, vary=True)` reads
  `(-inf, inf)` against the declared `min 0.0`. Nothing warns. A free
  `lor_size` under `-inf` can walk negative, and an unbounded `occ` can leave
  `[0, 1]`: issue #204's failure (a Biso of −165 Å², an 81-point QPA error at
  unchanged Rwp), reached by the other way of writing a model.
- **Why construction is right and assignment is not.** The fill lives in
  `schemas.common._InheritsDeclaredDefaults._inherit_declared_bounds`, a
  `model_validator(mode="before")`. Its docstring records that
  `validate_assignment=True` re-runs it on assignment with `data` built from
  the model's current field values; pydantic then takes the assigned field
  from its own field validation, so the filled `Parameter` never lands. The
  measurement above is the evidence; read pydantic's assignment path before
  choosing the seam.
- **One field is already fixed, locally.** WP-1944 made `Phase.extinction`
  opt-in (`Parameter | None`) and, after its code review, its field validator
  `Phase._declare_extinction` calls `common.declared_fills` itself, so an
  assigned extinction inherits `min 0, unit µm²`. That is the per-field
  answer. This WP is the class answer: a seam on `_InheritsDeclaredDefaults`
  (a `field_validator("*", mode="before")` using `cls._declared_default`, or a
  `wrap` model validator) that covers every inheriting class in
  `schemas/structure.py`, `schemas/instrument.py` and `schemas/migrate.py`.
  When it lands, the extinction special case can drop its fill.
- Rules that bind the fix (from the class docstring): fill before any
  `Parameter` exists, so the caller's object is never written; the
  replacement is a `Parameter`, never a dict; presence is
  `model_fields_set` (a dict's keys), so an explicit `min=-inf` still wins;
  an out-of-range value raises naming the field.
- Tier: physics (the declared range is the quantity's physical domain). No
  new judgement.

## Non-goals

- The history reader's repair of stored bare attributes
  (`history.tree.declared_range_repairs`): stored documents are not affected,
  since a reload states every attribute.
- Which fields declare a range, and what range. WP-1321 sorted that.

## Tasks

- [x] A test over every inheriting class and every declared field: build
  with defaults, assign `Parameter(value=<in range>, vary=True)`, assert the
  declared `min`/`max`/`unit` hold; and assign one stating `min=-inf`,
  assert it wins. It fails today on `Phase.lor_size` and `Atom.occ`.
  (2026-11-07: `test_an_assigned_parameter_inherits_its_declared_range_on_every_class`
  assigns a `Parameter` and a dict to all 72 declared fields of 21 classes,
  and failed on 70 of them before the seam. It leaves `vary` unset, since
  `Phase.magnetic_lor_size` refuses `vary=True` without a magnetic structure;
  the `min=-inf` case is `test_an_assigned_parameter_keeps_the_bound_it_states`,
  on named fields, since `PeakComponent` refuses an unbounded `fwhm`.)
- [x] The class-level seam; drop `Phase._declare_extinction`'s own fill if
  the seam covers it. (2026-11-07: `_InheritsDeclaredDefaults.__setattr__`
  beside the construction validator, both through `_inherit_declared`. The
  `field_validator("*")` this WP proposed is refused by pydantic on a
  discriminator field, `Source.kind`. The extinction fill is dropped; its
  number-to-declaration branch stays.)
- [x] Skill: none. An agent writes models both ways and needs no rule once
  both inherit. (2026-11-07: nothing added.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_schemas.py tests/test_extinction.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

Issue #204; PR #206; WP-1321 (`docs/wp/1321-persisted-bounds-repair.md`).

## Handover log

- **2026-11-07** — Assigning a `Parameter` to a schema field now inherits
  the field's declared range and unit, as passing it to the constructor
  always did. Before, `phase.lor_size = Parameter(value=0.01, vary=True)`
  left the width unbounded below and unitless. So did 70 of the 72 fields
  that declare a range. The code review then found an older defect on the
  same path: any assignment replaced the model's other declared parameters
  with copies, so an object a script held stopped being the model's. Both
  are fixed at one seam on the shared base class, and no fit prints or
  returns anything new.

  *Done.* `_InheritsDeclaredDefaults.__setattr__` fills an assigned value
  before pydantic validates it. The construction validator and it both call
  `_inherit_declared`. On an assignment's pass the construction validator now
  returns its data untouched, told apart by `info.field_name`, which pydantic
  sets only then. `Phase._declare_extinction` keeps only its
  number-to-declaration branch. Commits `ab1355b24` (seam and tests) and
  `4e864a7a8` (review fixes).

  *Premise check.* WP-1964 removed `Parameter.expr` after this WP was filed.
  It does not bear on the fill, which reads only `min`, `max` and `unit`. The
  Context's suggested `field_validator("*", mode="before")` cannot be built:
  pydantic refuses a before validator on a discriminator field, and
  `Source.kind` is one. So the seam is `__setattr__`.

  *Measured* (worktree `.venv`, `[dev]`, darwin/arm64, py3.12). Before the
  seam, 70 of 72 declared fields across 21 classes lost part of their range
  on assignment; after it, none. The two that held were `Phase.extinction`
  (WP-1944's per-field fill) and `PreferredOrientation.r`. Fast selection on
  the tree merged with `origin/main` at `8116c5a9d`: 14243 passed, 411
  skipped, 36 xfailed, 0 failed. The first run, before the review's identity
  test, read 14242 passed and 411 skipped: the one added test is the
  difference. Main was not re-measured. Four tests added, 0.01 s together
  (`tests.added_test_times` on the local junit). Acceptance: 483 passed,
  2 skipped over `test_schemas`, `test_extinction`, `test_history`,
  `test_tof_axis` and `test_cif_syntax_faults`; ruff clean.
  `python -m tests.reader_output`: unchanged against `96c2e3135`.

  *Code review* (`/code-review high --fix`, seven findings). Fixed: the
  sibling-identity defect above, which predates this WP; a caller's own
  broken `Parameter` now raises its own error rather than one quoting the
  fills; a dict with a non-string key raises a `ValidationError` rather than
  a `TypeError`; the refusal test now pins the field location, which the
  parent commit did not give. Declined: an assigned `Parameter` that leaves
  an attribute unset is copied, so a later change to the caller's object
  does not reach the model. That is construction's rule since PR #206, and a
  test pins it. Declined: an assignment now costs about 23 µs against 15.5,
  and no hot path assigns a schema field.

  *Deliberately not generalised.* `model_copy(update=...)` skips validation
  altogether, by pydantic's design. All 84 package sites were read, and each
  copies an existing `Parameter` that already carries its range. A stored
  document that already holds an assignment's unbounded range keeps it, the
  WP's non-goal.

  *Overlap.* WP-2118's runner edits `schemas/common.py` too, in the
  `SCHEMA_VERSION` comment near line 694. This WP edits lines 1000-1130 of
  that file, so the two do not conflict textually. Neither touches
  `params/` or `refine.py` on the other's behalf.

  *Generality.* No judge dispatched: no row of `_audit.py` moved and nothing
  adds a threshold, flag or automatic action.

  Next: none. The WP closes when PR #1458 merges.

- **2026-11-04** — created by WP-1944's runner from its `/code-review high`
  finding. No open WP owns it: 1321, which built the inheritance, is ✅, and
  a closed WP's uncovered case is a new WP.
