# WP-2025 — Parameters for the everyday calls

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 2024 (the format, the renderer, the gate and the page split)
Priority: P4 2026-10-23 — down a rung from P3 until WP-2024 lands its format and gate; P3 then

## Goal

Every argument of every call on the manual's everyday API page has a numpy-style Parameters
entry, rendered under its signature. WP-2024's shrink-only baseline holds no everyday
argument when this closes.

## Context

- Second of four WPs (2024-2027) splitting the maintainer's 2026-10-23 ask: a description per
  argument on the API pages. WP-2024 settles everything to decide (numpy style, the type line,
  the register, the parser, the `:param:` rendering, the drift gate `UNDOCUMENTED_PARAMETERS`,
  the split of the everyday page under `tests/test_manual.py`'s `PAGE_CHAR_CAP` = 50 000) and
  writes the **Refinement** section. Read its `CONTRIBUTING.md` section before writing an
  entry. This WP is the writing, nothing else.
- **What is left** (counted 2026-10-23 on `main` 96078e25; the Refinement section excluded):
  | Section | Calls | Parameters | Already with a paragraph |
  |---|---|---|---|
  | Reading data | 12 | 43 | 13 |
  | Results | 6 | 8 | 1 |
  | Fit report | 4 | 20 | 2 |
  | Series, history, projects | 11 | 53 | 5 |
  | Peaks and indexing | 4 | 34 | 7 |
  | Export and plots | 8 | 40 | 9 |
  | **Total** | **45** | **198** | **37** |

  Plus the constructors of the classes on the page drawn with a signature. "With a paragraph"
  means the docstring already has one opening on the name (` ``name`` — …`): that one is a
  conversion, and the rest are written from the code.
- **An entry is checked against the code, never inferred from the name.** Read the body and the
  callee it forwards to; where a default's meaning lives in another module (a `None` that
  derives something), say what it derives. A sentence found stale on the way goes to WP-2013's
  list, not fixed in passing.
- **help.py owns parameters, stage fields, reader options and preset fields** (root CLAUDE.md
  § Conventions). `read_pattern`'s `**options`, `load_instrument_profile`, the series calls'
  stage arguments: link the help entry or generate from it, per WP-2024's rule; never restate.
- **The Series calls are a known tangle**: `refine_sequential` forwards most of its keywords
  per pattern, and `events=`/`cancel=` are per pattern (root CLAUDE.md § Data flow, Series).
  Describe what the *series* does with each, which is not always what `fit` does.
- Size: about two sessions; split by section if one runs long. Each section is one commit.
- Tier: documentation only.

## Non-goals

- Model and dataclass fields on this page (`RefinementResult`, `PatternData` and the other 34):
  WP-2027.
- The techniques page: WP-2026.

## Tasks

- [ ] Reading data (12 calls, 43 parameters)
- [ ] Results and Fit report (10 calls, 28 parameters)
- [ ] Series, history, projects (11 calls, 53 parameters)
- [ ] Peaks and indexing (4 calls, 34 parameters)
- [ ] Export and plots (8 calls, 40 parameters)
- [ ] The constructors drawn with a signature on the page
- [ ] `UNDOCUMENTED_PARAMETERS` holds no everyday-page entry; the page(s) under `PAGE_CHAR_CAP`;
  the manual builds `-W`
- [ ] Skill: none expected (the index stays signature-only, WP-2024); re-check at close

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_reference_pages.py tests/test_manual.py tests/test_manual_api.py tests/test_help.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python -m ruff check src tests examples
```

## References

- numpydoc, *Style guide*, numpydoc.readthedocs.io/en/latest/format.html.

## Handover log

- **2026-10-23** — created with 2024, 2026 and 2027, one split of one ask; no open WP owns
  argument descriptions (WP-2024's creation entry says why).
