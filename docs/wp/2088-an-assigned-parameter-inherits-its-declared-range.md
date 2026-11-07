# WP-2088 — An assigned Parameter inherits its declared range

Milestone: unscheduled · Status: 🔄 2026-11-07 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-04 — a silent unbounded parameter on a path few fits run (assignment after construction); construction is already right

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
- [ ] Skill: none. An agent writes models both ways and needs no rule once
  both inherit.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_schemas.py tests/test_extinction.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

Issue #204; PR #206; WP-1321 (`docs/wp/1321-persisted-bounds-repair.md`).

## Handover log

- **2026-11-04** — created by WP-1944's runner from its `/code-review high`
  finding. No open WP owns it: 1321, which built the inheritance, is ✅, and
  a closed WP's uncovered case is a new WP.
