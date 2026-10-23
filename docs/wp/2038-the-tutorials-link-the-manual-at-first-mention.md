# WP-2038 — the tutorials link the manual at each concept's first mention

Milestone: unscheduled · Status: ⬜
Track: The repo's own process
Depends on: 1986 (the Guides tab complete)
Priority: P4 2026-10-23 — links change no number, and the pages they would point at are still moving under WP-1986

## Goal

Every rietx concept a tutorial names links to the manual page that explains it, at its first
mention in that notebook.

## Context

The maintainer's note on notebook 01 (2026-10-23; WP-2037 § Where this came from, note 3):
add more manual links to the notebooks once the manual is more complete. The rule this
applies is `yue-docs-style` rule 3 as WP-2037 proposes to widen it: nothing the reader needs
comes before it is explained or linked.

- Counted on `bc71dec`, the tutorials carry 4 to 7 links each to
  `https://rietx.org/docs/stable/…` (01: 4, 02: 4, 02b: 5, 03: 4, 04: 4, 05: 7, 06: 6).
- `tests/test_tutorials.py::test_a_tutorial_links_only_pages_the_manual_has` fails on a link
  to a page or anchor the manual does not have, so a link added here is checked.
- WP-1986 is still moving Guides pages into the new tree. A link written before it lands may
  point at a page that is about to move, which is why this WP waits for it.
- Edit each `examples/tutorials/NN_*.py` and rebuild with `build.py`. Never edit the
  `.ipynb`.

## Non-goals

- The prose and display fixes: WP-2037.
- New manual pages. A concept with no page is listed in the handover entry and gets no link.

## Tasks

- [ ] For each notebook, list every rietx concept it names (a verb, a type, a plan, a mode,
      a diagnostic code) and whether its first mention links the manual. Record the table in
      the handover entry.
- [ ] Add the missing first-mention links, then rebuild.
- [ ] Skill: none. The links are for a person reading a notebook.

## Acceptance

Every concept in the table either links at its first mention or is named as having no page.

```sh
.venv/bin/python examples/tutorials/build.py --check
.venv/bin/python -m pytest tests/test_tutorials.py -q
```

## References

None.

## Handover log

- **2026-10-23** — Created from the maintainer's note on notebook 01, beside WP-2037. Filed
  apart from it because it waits on WP-1986, and WP-2037 does not. Next: start once WP-1986
  closes.
