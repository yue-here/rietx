# WP-2022 — The API reference renders as Python objects

Milestone: unscheduled · Status: ✅ 2026-10-23 — every API name a Python-domain object, a model's fields one `py:fields`; the skill's index byte-identical
Track: The repo's own process
Depends on: —

## Goal

The three API reference pages (`reference/api.md`, `api-techniques.md`, `api-types.md`) render
each name as a Sphinx Python-domain object: a highlighted signature broken one parameter a
line, a permalink, an "On this page" entry and a search-index entry, with a model's fields as
attributes carrying their type and default. The selection, the tiers and the signature text
stay exactly what the skill's `api.md` prints.

## Context

- The maintainer, 2026-10-22: rietx.org/docs/dev/reference/api.html "is very hard to read as it
  doesn't have syntax highlighting or structuring".
- Why: `docs/reference_pages.py:_api_entry` writes each name as a MyST definition list whose
  term is the whole signature in one inline code span, and a model's fields as one
  comma-joined run of code spans. To Sphinx that is text, so the theme has nothing to style.
- The fix is the standard one: the `py:function` / `py:method` / `py:class` /
  `py:exception` / `py:data` / `py:attribute` directives, which is what autodoc emits
  underneath. Sphinx parses the signature string into name, parameters, annotations and
  defaults (each its own CSS class, which pydata-sphinx-theme styles), and
  `python_maximum_signature_line_length` breaks a long one a parameter per line.
- **Not autodoc.** WP-1981 chose a generator over autodoc because autodoc renders whole
  docstrings, written in the rulebook register; writing the directives ourselves keeps that.
  **One source of signature text**: `docs/skill/make_api_index.py`'s `_signature`,
  `_doc_line` and its field builders, so the skill's index and the manual cannot differ.
- `-W` constraints: a name described twice is "duplicate object description", so a repeat
  carries `:no-index:`; nitpicky is off, so an annotation naming a type the domain does not
  describe stays plain text, while one it does describe becomes a link.
- **A model's fields are one `py:fields` directive, never a `py:attribute` each**
  (`docs/py_fields.py`). One attribute per field cost ~60 characters of fence and options and
  took `api-types.md` (102 models, 826 fields) from 38 163 to 79 932 characters, over the page
  contract's 50 000 cap (`tests/test_manual.py` `PAGE_CHAR_CAP`, which reads a generated body in
  place). `py:fields` reads one `name: annotation = default` a body line, MyST handing a
  directive only its first line as an argument, and renders them as one object's signatures:
  stacked, each anchored, the annotation linked, indexed as an `attribute` so `{py:attr}`
  resolves, and kept out of the page contents.
- The markdown twin (`docs/markdown_twin.py`, WP-1980) translates the same doctree.
  sphinx-markdown-builder knows the `desc` nodes, but not the `abbreviation` Sphinx wraps a
  bare `*` in (an unknown node, so `-W` fails), and it writes every signature as a heading,
  so `_normalise` writes the `*` as text and a `py:fields` block as a list of code spans.
- Tier: no rule, threshold or automatic action is added; presentation only.

## Non-goals

- Per-parameter descriptions (a numpy-style "Parameters" field list). The docstrings are prose
  and stay so; this WP changes how the existing text renders, not what it says.
- The old tree under `docs/manual/` (WP-1986 retires it).

## Tasks

- [x] Generator emits Python-domain directives; signature and field text from
  `make_api_index`'s own builders; repeats `:no-index:`; conf sets the signature line length
- [x] Tests: the generated body parses as directives and every signature equals the skill's;
  the manual builds `-W`; the twin reads cleanly
- [x] Skill: none — the skill's `api.md` is unchanged byte for byte, and no agent-facing rule moves

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_reference_pages.py tests/test_manual.py tests/test_skill.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/skill/make_api_index.py --check   # the skill's index unchanged
.venv/bin/python -m ruff check src tests examples
```

## References

- Sphinx, *The Python domain* (`py:function`, `python_maximum_signature_line_length`,
  `toc_object_entries`), sphinx-doc.org.

## Handover log

### 2026-10-23 — closed: the API pages read as Python

The three API reference pages now look like a Python library's reference. Each call shows its
signature broken one parameter a line, with names, types and defaults styled apart, a link on
every type the pages describe, and its own anchor, sidebar entry and search entry. A model's
fields are a compact list under it, each anchored. The text is still the skill's own: its index
is unchanged byte for byte, and a test holds every one of the 101 signatures and every model's
fields equal to it. What it ruled out is one `py:attribute` per field. That doubled the
everything-else page past the 50 000-character page cap, so the fields take one directive of our
own, and the pages stay the size they were.

*Done.* `docs/reference_pages.py` writes `py:function`/`method`/`class`/`exception`/`data`
directives, each under `:module:` (`rx`, or the longest importable prefix), so the contents
read `Refinement.summary()` rather than two `summary()`s. A classmethod or staticmethod carries
its marker. A repeat across tiers takes `:no-index:` (none today; the path is tested).
`docs/py_fields.py` is the `py:fields` directive. `make_api_index.py` exports
`model_field_parts`/`dataclass_field_parts`, and its own output is unchanged (`--check`).
`docs/markdown_twin.py` keeps a signature's bare `*` (Sphinx wraps it in an `abbreviation` the
translator does not know, which failed `-W`) and writes a model's fields as a list. Conf:
`python_maximum_signature_line_length = 72`, `python_display_short_literal_types`,
`toc_object_entries_show_parents = "domain"`. CSS: a signature scrolls on its own line where a
phone is narrower than its first unbreakable run (`rx.save_instrument_profile(instrument:`), and
fields stack tight.

*Measured* (`[dev]` venv, Linux x86-64, 4 cores). The six files touching this
(`test_reference_pages`, `test_manual`, `test_manual_api`, `test_skill`, `test_help`,
`test_docs_consistency`): 320 passed, of which four are new (all in `test_reference_pages.py`).
`test_manual.py`'s twin coverage test was extended, not added. The manual builds `-W` clean. Generated bodies: api 31 376,
api-techniques 10 773, api-types 38 493 characters (30 396 / 10 367 / 38 163 before). Twins:
34 107 / 12 156 / 39 201. In chromium at 1400 px and 390 px, no page scrolls sideways and no
signature is cut. The **fast suite was not run to completion locally**: it reached 8-10 % in
about ten minutes on this 4-core container twice, and CI's required matrix runs the same
selection. Each new guard was made to fail once (twin `*`, twin field list).

*Review.* `/code-review high` returned eight findings. Fixed: contents entries ambiguous under
`hide` (now `:module:` + `domain`); classmethods unmarked; `py:fields` patched Sphinx internals
mid-run (now overrides `get_signatures` and `add_target_and_index`); the twin flattened every
`abbreviation` (now only inside a signature); a test that would read `:no-index:` as a field;
a constant's docstring computed for nothing. Answered by a wider test, not a refactor: the
dispatch copied from `make_api_index._entry` (the field test now covers every model and
dataclass on the pages, 100+). Declined, and pre-existing: a technique-only field like
`Phase.rigid_bodies` appears on no page, because the everyday tier drops it as the skill's index
does, and no technique tier lists `Phase`. The old page had the same gap.

*Generality.* Nothing to judge: no row, threshold, default or automatic action. Presentation
only, and the audit table is untouched.

*Next.* Nothing owed here. If the maintainer wants a parameter's meaning beside its type, that
is docstring work (numpy-style sections) and a new WP, which this one fenced out.

- **2026-10-22** — created. No open WP owns the API page's rendering: WP-1981, which wrote the
  generator, is closed, and WP-1986 moves Guides and Theory, not the Reference tab.
