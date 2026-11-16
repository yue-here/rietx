# WP-2024 — A Parameters list under each call: the format, the gate, and the Refinement calls

Milestone: unscheduled · Status: 🔄 2026-11-16 — PR #1622 open; left: the look in chromium at 390 px, both themes
Track: The repo's own process
Depends on: — (2023 soft: either order works; both edit the same pages' rendering)
Priority: P3 2026-10-23 — a reference that names every argument and explains a fifth of them; reading the source is the workaround

## Goal

A call on the manual's API pages can carry a numpy-style **Parameters** section, and the
generator renders it under the signature as a list, one entry per argument. The format, the
parser, the rendering, the drift gate and the page split are settled here, and proved on one
section: **Refinement**, the calls a fit is made of (18 functions and methods, 71 parameters).
WP-2025 and WP-2026 then write the rest without deciding anything.

## Context

- The maintainer, 2026-10-23, after WP-2022: the best API references carry a description per
  argument, and rietx's carry none. Asked for the work broken into WPs; this is the first.
- **What the pages show today.** `docs/reference_pages.py:_api_entry` writes each name as a
  `py:function`/`py:method`/`py:class` directive whose body is `make_api_index._doc_line(obj)`:
  the docstring's **first sentence**, nothing more. WP-1981 chose a generator over autodoc on
  purpose, because the docstrings are written in the rulebook's register (WP numbers, the
  measurement behind a default); that decision stands. This WP adds one more *section* of the
  docstring to what the generator renders, never the whole docstring.
- **What the docstrings hold** (counted 2026-10-23 on `main` 96078e25, deduplicated across
  tiers): 95 functions and methods on the three pages with 412 parameters; 90 already have a
  paragraph of their own opening on the name (` ``events`` — optional per-iteration telemetry…`,
  `Refinement.fit`); about half more are named somewhere in the prose; the rest are named
  nowhere. Per page: everyday 63 calls / 269 parameters / 56 with a paragraph; techniques
  30 / 142 / 34; everything-else 2 / 1 / 0. Classes drawn with a signature (`Refinement(...)`)
  add their constructors' parameters on top. In `src/rietx` three docstrings carry a
  `Parameters` heading today (`structure_factor.py:321`, `report/__init__.py:293`,
  `sequential.py:1041`).
- **The format: numpy style** (numpydoc), the scientific-Python convention a rietx user reads
  every day in numpy and scipy. An entry is the name and one to three plain sentences: what the
  argument does and what each special value means. The **type and default are already in the
  signature**, so the entry's type line may be bare (`events`, not `events : str | None`);
  decide whether numpydoc's validator accepts that or whether the type is restated, and write
  the decision into `CONTRIBUTING.md`.
- **The register is the user's, and the reason moves below.** ` ``telemetry`` — where this run
  records **itself**… because the knob nobody had to switch on… (WP-1322 measured three of
  three…)` becomes a Parameters entry saying where the run is recorded and what `False` and
  `None` do, while the why stays in the docstring's prose (a `Notes` section or the paragraphs
  under the sections), which the manual does not render. Nothing in the rationale is deleted.
- **Parsing.** The generator does not use autodoc or napoleon, so the section is parsed here:
  `numpydoc.docscrape.FunctionDoc` (numpydoc in the `docs` extra), or a small parser of our own
  if numpydoc's cost is not worth it. The rendered form is Sphinx's own doc fields
  (`:param name: text` in the directive body), which the Python domain draws as a
  "Parameters" list with no extension.
- **One authority per meaning: `src/rietx/help.py`** (root CLAUDE.md § Conventions). It owns
  what a parameter dot-path, a stage field, a reader option and an instrument preset field
  *is*. A call whose argument is one of those (`read_pattern(**options)` takes the reader
  options; a `StageSpec` takes stage fields) **links to the help entry or is generated from
  it**, never restated in a docstring. `tests/test_help.py` crosses help.py with its live
  vocabularies both ways and stays the gate for those.
- **The drift gate.** A Parameters entry naming an argument the signature does not have is a
  description of nothing, and an argument added later with no entry is undocumented, and
  nothing fails either way. So a test, in the shape of the repo's both-ways crossings
  (`test_help.py`, `tests/test_audit_table.py`): for every call on the three API pages, every
  documented name is in the signature (always), and every argument is documented except those
  in a **shrink-only baseline** (`UNDOCUMENTED_PARAMETERS`, the `_audit.UNAUDITED_BASELINE`
  pattern), which this WP seeds with every argument still unwritten. WP-2025 and WP-2026 empty
  it. numpydoc's `validate` (codes PR01 "parameter not documented", PR02 "unknown parameter")
  can be the engine; the baseline is ours.
- **The everyday page goes over its size cap.** `tests/test_manual.py` caps a generated page
  at `PAGE_CHAR_CAP` = 50 000 characters. `api.md`'s body was 31 376 after WP-2022; ~270
  entries at ~80 characters is ~22 000 more. So the everyday tier splits before WP-2025 fills
  it, by its seven sections (Reading data, Refinement, Results, Fit report; Series, history,
  projects; Peaks and indexing; Export and plots) into two or three pages, with the contents,
  the redirects (`docs/docs_versions.py`'s `RETIRED`, if a URL changes) and the
  `api_tiers()` reading order kept. This WP decides the split and makes it; whether the pilot
  alone needs it is measured, not assumed.
- **The markdown twin** (`docs/markdown_twin.py`) translates the doctree; a doc-field list must
  come out as a readable list, and `test_manual.py`'s twin test covers it.
- **The skill's `api.md` stays signature-only** unless measured otherwise: it is generated by
  `docs/skill/make_api_index.py` from the same objects, has a size budget
  (`tests/skill_caps.py`), and WP-2008 is slimming the skill. The manual is where descriptions
  go; `help()` and an IDE show the docstring itself.
- **WP-2013** (stale text in the code) edits some of the same docstrings. A Parameters entry
  written here is checked against the code as it stands, and a stale sentence found on the way
  goes to 2013's list rather than being half-fixed here.
- Tier: no rule, threshold, default or automatic action; documentation only.

### Inherited

- **From WP-2023 (2026-10-23).** API signatures are now coloured with the code blocks' Pygments
  tokens by `docs/py_highlight.py`, on `doctree-resolved` ahead of the twin, and it touches only
  `desc_signature` nodes: a `:param:`/`:type:` field list is not one, so its types stay one
  colour. If the list's types should match the signature's, call that module's `_annotation`
  on the field list's type nodes rather than writing a second classifier. Whatever renders the
  list, the twin test (`test_a_signature_is_coloured_token_by_token_and_its_twin_is_unchanged`'s
  two-build shape) is the pattern for proving the classes carry no text.

## Non-goals

- The rest of the everyday page (WP-2025), the techniques page (WP-2026), model and dataclass
  fields (WP-2027).
- Returns / Raises / Examples sections. They may follow the same path later; this WP renders
  Parameters only, so the gate has one thing to hold.
- The skill's index (above), and the rationale prose, which stays where it is.

## Tasks

- [x] Decide and write down the format (numpy style; the type line; register) in
  `CONTRIBUTING.md`, with one worked entry
- [x] Generator: parse a docstring's Parameters section and render it as the directive's
  `:param:` fields; the twin renders it as a list
- [x] The gate: a test that every documented name is in its signature and every argument on the
  API pages is documented or in the shrink-only `UNDOCUMENTED_PARAMETERS` baseline, seeded now
- [x] The split of the everyday page under `PAGE_CHAR_CAP`, if the measurement says it is owed now
  (else the measurement and the split's plan go to WP-2025's `### Inherited`) — not owed: twin
  49 676 of 50 000 after the pilot; measurement and a three-page plan in WP-2025's `### Inherited`
- [x] The Refinement section's 18 calls written (71 parameters), their entries out of the baseline;
  help.py-owned arguments linked or generated, never restated
- [ ] Tests (above) green; the manual builds `-W`; looked at in chromium, both themes, 390 px
- [x] Skill: none expected, and why (the index stays signature-only); re-check at close —
  none: `make_api_index.py --check` passes, the skill's `api.md` reads signatures and first lines
  only, and its budget (`tests/skill_caps.py`) is untouched

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_reference_pages.py tests/test_manual.py tests/test_manual_api.py tests/test_help.py tests/test_skill.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/skill/make_api_index.py --check
.venv/bin/python -m ruff check src tests examples
```

## References

- numpydoc, *Style guide* (the docstring standard), numpydoc.readthedocs.io/en/latest/format.html;
  rendered examples: `numpy.linspace`, `scipy.optimize.least_squares` in their projects' references.
- Sphinx, *The Python domain*, § Info field lists (`:param:`), sphinx-doc.org.

## Handover log

- **2026-11-16** — (ghostshift runner, PR #1622.) A reader of the manual's API pages now sees,
  under every call of the Refinement section, a list naming each argument and saying what it
  does and what its special values mean, where before there was one sentence per call. The
  format is decided and written down, the generator renders it, and a test now fails when a
  description names an argument that does not exist or an argument has none and is not on a
  shrink-only list, so the remaining 397 arguments are counted rather than forgotten. The
  everyday page is now 324 characters under its size cap, so WP-2025 splits it before writing
  anything else.
  - *Done.* `CONTRIBUTING.md` § A Parameters section under each call (bare name line, register,
    `Notes` for the reasons, the gate). `docs/reference_pages.py`: `parameter_entries` (our own
    parser; numpydoc is not a dependency and would flag every bare name as PR04),
    `_parameter_fields` writing `:param:` fields, `documented_call`, `call_arguments`; MyST's
    `fieldlist` extension on (`docs/sphinx_shared.py`). `docs/undocumented_parameters.py`, seeded
    with 475 lines over 106 calls, now 397. All 19 Refinement-section calls (78 arguments: the
    WP's 18/71 had grown) written in `src/rietx/refine.py`, each old paragraph kept under
    `Notes`; path arguments link `parameters.md`, plans `plans.md`, a stage
    `settings.md#stage-settings`, a formula `expressions.md`. `build_report`'s existing section
    reshaped to numpy's name lines plus a `Notes` heading, since its closing prose was parsed as
    arguments. The twin's residue check (`tests/test_manual.py`) now fails on a raw `:param`
    line.
  - *Measured.* With `fieldlist` on, every built page but `reference/api.html` (and its twin and
    `llms-full.txt`) is byte-identical to the build with it off. Twin of `api.md`: 37 753 before,
    49 676 after (cap 50 000); body 46 904. Without `fieldlist` the twin carried 18 raw `:param`
    lines, with it 0 (the residue check's positive arm). Gate made to fail on purpose by deleting
    one baseline line. Mac arm64, worktree venv `[dev]`, each file alone: test_reference_pages 41
    passed, test_manual 67, test_manual_api 19, test_help 37, test_skill 174; `sphinx -W` exit 0;
    `make_api_index.py --check` 0; ruff clean; `rietx_vale.sh` 0 errors. Fast suite on pearl (Linux x86-64, `rietx-py312`
    venv, `-n 4`, co-tenant, tip 6079db766): 14859 passed, 280 skipped, 32 xfailed, 0 failed
    in 1006 s, 6.6 GB peak; the 7 added tests cost 0.03 s together (`tests.added_test_times`),
    plus two cases on an existing residue test; no main baseline was run, so the delta is the
    added tests, not a measured difference.
    `python -m tests.reader_output`: exit 0, unchanged.
  - *Review.* No `/code-review` (it edits the main checkout); a read-only review agent instead.
    Applied: `cancel=None` can still be stopped from `rietx watch` on a recorded run; `None` for
    mode and limits in `run_stage`/`suggest`/`parameters` is the working state's, which a
    checkout sets; `refine`'s `history` and `telemetry` entries; `unhold`'s floating-origin
    holds; `fit`'s `events`/`cancel` paragraphs restored under Notes; a body opening on a doc
    field is set off from the directive's options (latent: no call has an empty summary today);
    the gate refuses an empty entry. Declined: cross-reference links inside entries (roles
    render as code, as `_doc_line` already does); entry order against the signature.
  - *Not done.* The look in chromium at 390 px in both themes: headless Chrome on this Mac
    returned blank screenshots. The HTML is Sphinx's own field list in the theme's styling.
  - *Gotchas.* Vale does not read inside the directive fences, so entries are not spell-checked
    by CI; the tests and the build are their only gate. An unindented line inside the section
    reads as an argument and fails the gate, which is the intended alarm.
  - *Generality.* None: documentation only, no rule, threshold, default or automatic action.
  - Next: the chromium look (anyone, on the built page); then WP-2025, whose first commit is the
    page split (its `### Inherited` has the measurement and a three-page plan); WP-2026 and
    WP-2027 are re-rated P3.

- **2026-10-23** — created. No open WP owns argument descriptions: WP-2022 fenced them out as
  "docstring work and a new WP"; WP-2013 corrects stale sentences but adds no sections; WP-2008
  slims the skill and does not touch the manual.
