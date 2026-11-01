# WP-2027 — A meaning beside each field of a model

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 2024 soft (its register and gate are the pattern; fields render by `py:fields`, not `:param:`)
Priority: P4 2026-10-23 — a scoping decision with ~1 270 fields behind it, nobody blocked; P3 once WP-2024 has set the register

## Goal

Decide where a pydantic model's or a dataclass's **field** says what it means, and how the
manual's API pages show it; then write it for the models on the everyday page (34 models,
335 fields). The other ~110 models get a follow-up WP filed at close, sized by what this one
measured.

## Context

- Fourth of four WPs (2024-2027) splitting the maintainer's 2026-10-23 ask: a description per
  argument on the API pages. A model's fields are its arguments, and the larger half of the
  surface: counted 2026-10-23 on `main` 96078e25, 145 models and dataclasses on the three pages
  carry ~1 270 fields (everyday 34 / 335, techniques 8 / 110, everything-else 103 / 826), and
  29 fields carry a `Field(description=…)`. The rest are explained, if at all, in the class
  docstring's prose (`RefinedParameter`'s `at_bound`, in `schemas/results.py`).
- **Today's rendering.** WP-2022 drew a model's fields as one `py:fields` directive
  (`docs/py_fields.py`), one `name: annotation = default` signature line per field, anchored
  and indexed, with no body. One `py:attribute` per field was measured and refused: it took
  `api-types.md` from 38 163 to 79 932 characters, over `tests/test_manual.py`'s
  `PAGE_CHAR_CAP` = 50 000. A description per field costs more again, so **the rendering and
  the page split are this WP's first decision**, measured, not assumed: a description under
  each `py:fields` line, a collapsed block, or the types page split by module.
- **Where the text lives — the three candidates, each with a cost to weigh:**
  - `Field(description=…)`: travels into `model_json_schema()` and so into every JSON-schema
    consumer, which is a benefit and an observable change. Check whether it moves anything a
    test pins or `SCHEMA_VERSION` (`schemas/common.py`, "0.59") versions; the root CLAUDE.md
    § `capabilities()` lists the schema as a versioned contract.
  - An attribute docstring (`#:` before the field, or a string after it): Sphinx-native, free
    at runtime, invisible to the schema and to `help()`.
  - A numpy `Attributes` section in the class docstring: one place per class, the same parser
    as WP-2024's Parameters, but a field renamed in the class and not in the section drifts
    unless the gate covers it.
  Whichever is chosen gets the same both-ways gate as WP-2024's (every described name is a
  field; every field is described or in a shrink-only baseline).
- **help.py already describes some fields.** `StageSpec`'s fields are help.py's *stage fields*,
  and instrument presets are help.py's too (root CLAUDE.md § Conventions: what a name *is* is
  written in `help.py` and nowhere else). Those models are **generated from help.py** or link
  to it; restating them is a second authority.
- **A declared field is a claim** (root CLAUDE.md § Invariants, WP-1076): writing what a field
  means is where an empty default that reads as an answer, or a member nothing writes, shows
  up; all nine of WP-1076's surfaced while writing a manual chapter. Such a finding goes to
  the owning WP or a new one, not fixed here.
- **The skill's index** (`docs/skill/make_api_index.py`) prints field lists too; descriptions
  stay out of it (WP-2024's reasoning, and WP-2008 slims the skill).
- Tier: documentation only.

## Non-goals

- Fields on the techniques and everything-else pages, beyond what the decision needs to be
  measured on: a follow-up WP, filed at close.
- Call parameters (WP-2024 to 2026).

## Tasks

- [ ] Decide where field text lives (above), measured: a schema-dump diff, the `help()` and
  IDE view, the parser cost; written down beside WP-2024's section in `CONTRIBUTING.md`
- [ ] Decide the rendering and the types page's split under `PAGE_CHAR_CAP`, measured on a
  built page
- [ ] Renderer and the both-ways gate with a shrink-only baseline
- [ ] The everyday page's 34 models written (335 fields), help.py-owned ones generated or linked
- [ ] File the follow-up WP for the other ~110 models, sized from this one's rate
- [ ] Skill: none expected; re-check at close

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_reference_pages.py tests/test_manual.py tests/test_manual_api.py tests/test_help.py tests/test_schemas.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/skill/make_api_index.py --check
.venv/bin/python -m ruff check src tests examples
```

## References

- numpydoc, *Style guide* § Attributes, numpydoc.readthedocs.io/en/latest/format.html.
- pydantic, *Fields* (`Field(description=...)`) and *JSON Schema*, docs.pydantic.dev.
- Sphinx, *autodoc* § attribute documentation comments (`#:`), sphinx-doc.org.

## Handover log

- **2026-10-23** — created with 2024, 2025 and 2026, one split of one ask; no open WP owns
  field descriptions (WP-2022 fenced them out; WP-2024's creation entry says why).
