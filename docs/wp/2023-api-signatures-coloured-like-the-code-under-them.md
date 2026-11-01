# WP-2023 — API signatures coloured like the code under them

Milestone: unscheduled · Status: ✅ 2026-10-23 — every API signature in the code blocks' Pygments colours; twins byte-identical, contrast ≥ 6.65:1
Track: The repo's own process
Depends on: —

## Goal

On the three API reference pages (`reference/api.md`, `api-techniques.md`, `api-types.md`) a
signature is coloured the way a Python code block on the same page is: the call's name, each
parameter's name, its annotation, a built-in type, a default string, a number and a constant
(`None`, `True`, `False`) each take the code blocks' own colour for that token, in both themes.
No colour value is added to the site.

## Context

- The maintainer, 2026-10-23, after WP-2022 gave each name a Python-domain signature broken a
  parameter a line: "can we also use syntax colouring?". Today a signature is one ink colour
  with the type links in the accent, bold names and italic parameters.
- **The mechanism is already half there.** Sphinx writes each signature piece as a span whose
  class is a Pygments token name: `n` (a name: both a parameter's name *and* its annotation),
  `o` (`=`, `*`, `**`), `p` (`:`, `[`, `|`), `w`, `k` (`class`, `classmethod`), plus
  `sig-name`, `sig-prename`, `default_value` and `sig-return-typehint`. pydata-sphinx-theme's
  `_static/pygments.css` (its default `a11y-high-contrast-light` / `-dark` styles; `conf.py`
  sets neither `pygments_light_style` nor `pygments_dark_style`) colours those classes only
  under `.highlight`, which is why the signature is monochrome.
- **Prototyped 2026-10-23** on a local build of `reference/api.html` (`Refinement.fit`, both
  themes), by putting `highlight` on each `dt.sig` and relabelling in the browser:
  the name → `nf`; an `n` after the parameter's `:` and before its `=` → `nc`, with a bare
  `str`/`int`/`float`/`bool`/`dict`/`list`/`tuple` inside it → `nb` and `None` → `kc`; the
  return annotation → `nc`; a default → `s` (starts with a quote), `mi` (a number), `kc`
  (`None`/`True`/`False`), else left `n`. It read as intended. Two things it got wrong, both
  owed here:
  - `.highlight` brings the code block's background with it. That overrode the `:target`
    tint (`--pst-color-target`), so a signature reached by its permalink no longer showed it
    was the one linked. Keep the signature's own ground and the target tint; take only the
    token colours.
  - `em.sig-param` sets italics on every token, which fights the colours. Set the parameter
    name upright.
- **Where it is done: in the build, never in page JavaScript.** A Sphinx post-transform (or a
  `doctree-resolved` handler) over `desc_signature` nodes, in `docs/py_fields.py` or a new
  extension beside it, registered in `docs/docs/conf.py`'s `extensions`. The doctree already
  separates the pieces (`desc_name`, `desc_parameter` holding `desc_sig_name` /
  `desc_sig_punctuation` / `desc_sig_operator` / an `inline` with class `default_value`), so
  the relabelling is class lists on existing nodes. Classifying a default is
  `ast.literal_eval` on its text, never a regex over prose.
- **Every colour comes from Pygments' stylesheet, none from `custom.css`.** `tests/test_manual.py`
  fails on a hex in `custom.css` (WP-2021: the site's colours are `docs/landing/src/tokens.css`'s).
  The only CSS this WP writes is selectors: upright names, and whatever keeps the ground.
- **Contrast.** pydata's a11y styles meet WCAG AA on their own grounds (`#fff` / `#2b2b2b`); a
  signature sits on the site's `--bg` (`#fbfaf8` / `#15110d`) and, when targeted, on
  `--accent-soft`. Measure each token colour used on each of those grounds with
  `tests/test_landing.py::contrast`, the site's one contrast measure, and hold it at 4.5:1 in
  a test.
- **The markdown twin** (`docs/markdown_twin.py`, WP-1980) translates the same doctree. Extra
  classes carry no text, so the twins of the three pages must come out byte-identical; a test
  says so.
- **Who else does this.** mkdocstrings-python's `separate_signature` draws a signature as a
  highlighted code block (the pydantic and FastAPI docs). The Python docs and numpy/scipy (the
  same pydata theme) keep signatures one colour. sphinx-immaterial re-wraps signatures with
  Black. So this is ahead of most Sphinx sites, not against them.
- Tier: no rule, threshold, default or automatic action; presentation only.

## Non-goals

- Parameter descriptions (WP-2024 onward).
- Signatures elsewhere in the manual: a guide's inline `{py:func}` role is a link, not a
  signature, and stays as it is.
- Changing the code blocks' Pygments style. If the maintainer wants signatures and code in the
  site's own palette, that is a Pygments style built from `tokens.css`, and a WP of its own.

## Tasks

- [x] The transform: `highlight` token classes on every Python-domain signature on the three
  API pages (name, parameter name, annotation, built-in, return type, default by literal kind),
  the `:target` tint kept, parameter names upright
- [x] Tests: the built HTML of the three pages carries the expected class on each token of a
  few pinned signatures (`Refinement.fit`, a classmethod, a `py:fields` line, a `**kw`); the
  contrast of every token colour on `--bg` and `--accent-soft`, both themes, ≥ 4.5:1; the
  twins unchanged; looked at in chromium at 1400 px and 390 px, light and dark
- [x] Skill: none. The skill's `api.md` is plain text and is untouched (`make_api_index.py --check`)

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_reference_pages.py tests/test_manual.py tests/test_landing.py
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/skill/make_api_index.py --check
.venv/bin/python -m ruff check src tests examples
```

## References

- Sphinx, *The Python domain* and *Sphinx API: nodes* (`desc_signature`, `desc_sig_*`),
  sphinx-doc.org.
- pydata-sphinx-theme, *Code blocks* (the `pygments_light_style` / `pygments_dark_style`
  options and the a11y defaults).
- WCAG 2.2, success criterion 1.4.3 (contrast, minimum).

## Handover log

- **2026-10-23** — closed in one session. The API reference's signatures are now coloured the
  way the Python code blocks on the same pages are. The call's name, a type, a built-in, `None`
  and a default each take the code blocks' own colour, in both themes. A signature reached by
  its permalink keeps its highlight, and parameter names are upright. Nothing else about the pages
  changed: the markdown twins, `llms.txt` and the skill's API index are byte-identical, and the
  site gained no colour value of its own. Every colour clears WCAG AA on the page and on the
  permalink tint by a wide margin. The one judgement left for the maintainer is that a linked
  type now reads in the type colour, with an underline, rather than in the link accent (below).

  *Done.* `docs/py_highlight.py` (new, registered in `conf.py`) runs on `doctree-resolved`
  ahead of the twin (priority 900). It puts `highlight` on every Python-domain `desc_signature`
  and adds Pygments classes. A function's name gets `nf`, a class's `nc`. A type in an
  annotation gets `nc`, a `builtins` class `nb` and `None` `kc`. This holds for a link (class on
  the `<a>`) and for bare text (wrapped in an `inline`). A parameter's default gets
  `ast.literal_eval`'s kind (`s`, `mi`, `mf`, `kc`; bytes `s`), and anything else (`-inf`, a
  factory) stays as it was. A `py:fields` line's `: type` and `= value` go through the same
  two classifiers. `custom.css` gains selectors only: `dt.sig.highlight` transparent, `:target`
  back to `--pst-color-target`, and `em.sig-param` upright.

  *Measured* (Linux x86-64, worktree venv `[dev]` + playwright, the latter installed this
  session for the browser look).
  - Twins: a full `-W` build before and after the change. All 121 twins, `llms.txt` and
    `llms-full.txt` are byte-identical, and the build stays warning-free.
  - Contrast: the lowest is 6.65:1 (light `nf`/`nc` on `--accent-soft`), every token ≥ 4.5:1
    on `--bg` and `--accent-soft` in both themes. pydata's muted `.default_value` colour, which
    a non-literal default keeps, measures 5.33 / 5.51 on the tint.
  - Chromium at 1400 and 390 px, light and dark, plain and `#rx.Refinement.fit`: ground
    transparent, and `rgb(253,240,227)` / `rgb(44,31,18)` when targeted. No horizontal
    overflow at 390 px.
  - Acceptance selection (`test_reference_pages`, `test_manual`, `test_landing`): 127 passed.
  - Three tests added in `tests/test_manual.py`, all in the fast tier. A two-build test pins
    each token's class on a page of signatures and holds its twin equal to the page built
    without the extension. A built-manual test checks the three API pages. A contrast test
    reads the colours through pydata's own `get_pygments_stylesheet`. The class test was made
    to fail once on purpose (`mi`→`m`) and failed on exactly that fragment.
  - Fast suite (`[dev]`, playwright removed again, Linux x86-64, 4-core container, alone):
    11152 passed, 203 skipped, 27 xfailed in 32:38, one run. The three added tests are 2.16 s
    together (two-build test 1.91 s), all passes. No local baseline on `main`: that is CI's job.
    A first run with playwright installed hit the 30-minute background limit unfinished. It was
    slow, not hung: the second run's process list showed the example scripts CPU-bound on four
    cores.

  *Review* (`/code-review high --fix`, 8 findings, 4 fixed in their own commit).
  - Fixed: a parameter list Sphinx cannot parse arrives as one bare `Text` and crashed the
    handler on `.get` (regression case added to the test page). A keyword name inside
    `Annotated[..., Call(kw=…)]` was coloured `nc`. `literal_eval` printed a SyntaxWarning on
    `'\d'`, and bytes were uncoloured. The contrast list missed Sphinx's own `m`/`kt`/`sc`.
  - Declined: the contrast test assumes a token with no rule shows the base colour (exact for
    today's styles). The twin is not compared on the real pages in a test, which would mean two
    full builds; the session's before/after build did it once. Finding 8 was measured (above)
    and passes.
  - Left to the maintainer: a linked type in the type colour rather than the accent. The WP
    asked for the annotation's colour; the underline still marks the link.

  *Generality:* not dispatched. `_audit.py` is untouched, and the change is a docs-build
  presentation rule, not a heuristic deciding on a caller's behalf.

  *Forward:* WP-2024's `### Inherited` gets a note. Its parameter lists are field lists, which
  this transform does not touch; if their types should match, they reuse `_annotation`.

  *Next:* nothing owed here. If the maintainer wants links back in the accent, it is one CSS
  selector (`dt.sig.highlight a.reference { color: var(--pst-color-link) }`, after the
  Pygments rules by specificity). If they want the site's own palette in code and signatures
  alike, that is the separate Pygments-style WP the Non-goals name.

- **2026-10-23** — created. No open WP owns the API pages' rendering: WP-2022, which drew the
  signatures, is closed, and its `Next` named only the parameter descriptions (WP-2024).
