# WP-1430 — the page is a file

Milestone: unscheduled · Status: 🔄 2026-09-16 — claimed by @yue-here
Depends on: 1423 (the page as it stands)

## Goal

The `rietx watch` page's script and stylesheet are files in the package,
served as files, with the pure functions in an ES module that `node --test`
runs from the suite. The page behaves exactly as it does today and the
browser test passes unchanged. Every later WP on this page edits a file an
editor lints and a test imports.

## Context

Seven WPs (1424–1429, 1431) are queued against one page. Today that page is
`_PAGE_TEMPLATE` in `src/rietx/watch.py`: about 90 lines of CSS and 520 lines
of JavaScript quoted inside a Python string, with three `@TOKEN@`
substitutions and a regex that has to be spelt `\\/` to survive the quoting.
Its only check is `node --check` (`tests/test_watch_app.py`), which sees
syntax and nothing else. WP-1402 and WP-1405 each shipped a page defect no
test could see. Nothing in it is unit-tested: `rangesOf` and the Δ/σ ladder,
`ago`, `num`, `patchList`'s ordering, the panel state.

Two of the queued WPs need this directly. 1425 ports the GUI's `clampSize`
and wants to pin the port to the original on the GUI's own cases. That needs
the port to be importable. 1426 and 1427 both rewrite `drawRun`
and `patchList`; a merge conflict inside a Python string is worse than one in
a `.js` file.

### The precedents

- `src/rietx/gui/static/` is served by `gui/server.py` through `STATIC_DIR`.
  Hatchling takes every non-ignored file under `src/rietx`
  (`pyproject.toml` § wheel), so a static directory ships with no build
  configuration.
- `viz/plotlyjs.py` serves a file out of the installed package on a route.
- `node --test` is in Node since 18 and needs no `npm install`. The suite
  already shells out to `node --check` and skips without it; the same
  fixture runs the tests.
- `compare_app.py` has the same shape (a page in a string, lines 200–560)
  and is not touched here. It has one WP queued against it (1429), which can
  do the move if it wants to and is told so.

### The shape

`watch.py` becomes the package `watch/` with `__init__.py` holding the server
and `static/` holding `index.html`, `watch.css`, `watch.js` and
`watch-core.mjs`. `rietx.watch` stays importable; `cli.py` and the tests do
not change their imports. `watch-core.mjs` holds the functions that touch no
DOM: `rangesOf`, `LADDER`, `ago`, `num`, `esc`, `deltaTitle`, `extent`,
`finiteOf`, the panel-state reducer. `watch.js` imports it as a module
script and owns the DOM. The three substitutions (`@SUFFIX@`, `@DIST@`,
`@HUE@`) become fields on the `api/runs` payload, which the page already
fetches first; the HTML is then a static file and
`test_no_page_token_is_left_unsubstituted` becomes a test that the payload
carries the three.

The `node --check` test becomes `node --test static/*.test.mjs`, skipping the
same way. The browser test is the regression bar: it passes before and after
without an edit, or the move changed behaviour.

## Non-goals

- Any change to what the page does or how it looks. Behaviour is bit-for-bit
  the fence; the browser test is its witness.
- Bundling, TypeScript, or `gui/`'s vitest. The page stays a script the
  browser runs as written. If a later WP wants jsdom for DOM logic, it argues
  for it then.
- Moving `compare_app.py`'s page. Named here for 1429 to pick up.

## Tasks

- [ ] `watch/` package, static files, the three substitutions on the payload,
      routes serving the files with the right content types
- [ ] `watch-core.mjs` with the pure functions, imported by `watch.js`
- [ ] `node --test` over `rangesOf` (the ladder rungs, the 99.9th percentile,
      the data-derived ranges), `ago`, `num` on `"NaN"`, and the panel
      reducer's last-panel rule; run from `tests/test_watch_app.py`, skipping
      without node
- [ ] `tests/test_watch_app.py` adapted (the substitution test, the
      `node --check` test), `tests/test_watch_browser.py` untouched and green
- [ ] Root CLAUDE.md § Conventions: the `node --check` rule becomes "a page
      that is JavaScript is a file, checked by `node --test`", one line, with
      `compare_app.py` named as the remaining string
- [ ] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py tests/test_telemetry.py
.venv/bin/python -m ruff check src tests examples
node --test src/rietx/watch/static/
```

The browser test file has no diff on this branch. `node --test` runs at least
six cases and is invoked by the suite.

## References

- WP-1402 and WP-1405 (the two page defects that motivated `node --check`),
  WP-1423 (the page as it stands), `gui/server.py:STATIC_DIR`.

## Handover log

- **2026-09-16** — created in the revision of 1424–1429, as the WP that
  should have come first.
