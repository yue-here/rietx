# WP-1917 — a Jupyter quickstart on the landing page, opened in Colab at the release

Milestone: unscheduled · Status: 🔄 2026-10-09 — live; the Colab restart is fixed on main and reaches Colab with the next release
Track: Render what the fit already knows
Depends on: 1916 (the manual pages it links; ✅ 2026-10-08, PR #826)
Priority: P3 2026-10-09 — what remains waits on the next release

## Goal

The landing page's hero carries a "Jupyter quickstart" button beside "Agent
quickstart". It opens to the five tutorial notebooks. Each row reads it in the
manual, opens it in Colab, or downloads the `.ipynb`. Every Colab link opens
the notebook as tagged at the latest release, so its `%pip install rietx`
installs the version it was built with.

## Context

**Why it waited** (superseded 2026-10-09: v1.7.0 is tagged at a9eaebb4 and
on PyPI, so the gate is open). Every notebook needs rietx 1.7 or later (WP-1545). PyPI
served 1.6.0 on 2026-10-07. `pages.yml` deploys on every push to `main`, so a
Colab link merged before the 1.7 release would install 1.6 in its first cell
and fail on the next one. Read and download links work today. The button ships
whole, so this WP waits for 1.7 rather than shipping a button with a dead
column.

**Why a tag and not `main`.** `main`'s notebooks are built against the next
`.dev0` and may call API that PyPI does not have yet. The tagged tree's
notebooks are rebuilt by the release itself (`docs/RELEASING.md` step 1, last
sentence), so `blob/vX.Y.Z/examples/tutorials/NN_slug.ipynb` and
`pip install rietx` at that release agree. The URL form is
`https://colab.research.google.com/github/<owner>/<repo>/blob/<tag>/<path>`,
with `<owner>/<repo>` read from `_about.REPO_URL`, never spelled.

The manual's own source links chose `main` over a tag (`docs/manual/conf.py`,
the note above `_SOURCE_REF`). That choice derived the tag from
`pyproject.version`, which named an untagged release on 2026-09-14 and would
have 404'd. This WP reads the newest `v*` tag from git itself, so that failure
does not apply. Two consequences:
- `pages.yml`'s `actions/checkout` must fetch tags (`fetch-tags: true`, or
  `fetch-depth: 0`). The default shallow checkout has none.
- `docs/landing/build.py` refuses to build when it finds no tag. A silent
  fallback to `main` is the failure this WP exists to avoid.

**The rows are derived.** `examples/tutorials/README.md` already holds a
hand-written table of the five. A third copy on the landing page would drift.
So `build.py` reads each notebook's title off its first markdown cell's `# `
heading and finds the notebooks by `examples/tutorials/build.py`'s `SOURCES`
glob. A sixth tutorial then appears with no edit here. Keep the row to its
title and three links; the landing register is few words (memory:
landing-page-register).

**The hero.** It holds one `<details class="qs" id="quickstart">` today, with
its JS in `src/index.html` (any `#quickstart` link opens it; the copy button
serialises the prompt). The second disclosure gets its own id. Give both the
same `name` attribute so opening one closes the other (exclusive `<details>`,
Chrome 120, Safari 17.2, Firefox 130). Check the pair at 320 px, the narrowest
width the top bar is designed for.

**What other parts of the page already say.**
- The Python API section's "Get started here" links `using/quickstart.html`.
  After WP-1916 that URL is the tutorials index, so it needs no edit.
- That section's code box is notebook 02's first cell, held equal to the
  committed notebook by a test (WP-1545's second review round). Its bar may
  gain an "Open in Colab" link to 02. Leave the code itself alone.

**Unmeasured, and only the maintainer can measure it.** Whether Colab's
preinstalled numpy or matplotlib makes `%pip install rietx` ask for a runtime
restart. It needs a Google sign-in, so the maintainer runs each notebook once
from its tagged Colab URL. If a restart is needed, the notebook's opening
markdown says so in one line.

**The "until 1.7" lines.** Each notebook's opening cell and
`examples/tutorials/README.md` say "Until rietx 1.7 is on PyPI, install it from
GitHub instead". They were meant to go before the 1.7 cut. Superseded in part
2026-10-09: the cut came first, so the v1.7.0 notebooks carry the line into
Colab until the next release's tag. The line is stale but harmless there,
since its condition is now false and `%pip install rietx` installs 1.7.0.
`main` drops it now.

**The manual's tutorials index** (from WP-1916, PR #826).
`using/quickstart.html` is a table of the five notebooks with a `{download}`
link each (`docs/manual/using/quickstart.md`). A Colab column in that table is
the manual's place for Colab links.
`tests/test_manual.py::test_every_tutorial_renders_with_its_outputs_and_the_quickstart_links_it`
reads that page's article body, and needs widening if the column becomes
required. The manual copies notebooks from `examples/tutorials/` on every build,
so dropping the "until 1.7" lines needs no manual edit.

### Inherited

- **2026-10-10, from WP-1940 (4th session, PR #864).** rietx no longer depends on
  numba. It depends on `rietx-kernels`, one abi3 wheel per platform with no
  sdist. So the next release's `%pip install rietx` on Colab touches numba
  not at all, and adds a ~200 KB manylinux wheel. JupyterLite stays out of
  reach for a new reason: Pyodide has no `rietx-kernels` wheel, so pip refuses
  rietx there.

## Non-goals

- The manual's tutorial chapter and the quickstart rename (WP-1916).
- Binder (minutes to start) and JupyterLite (no numba in Pyodide).
- A Colab badge inside the notebooks themselves.

## Tasks

- [x] Drop the "until 1.7" lines from the five `.py`
  sources and the README, then rebuild the notebooks.
- [x] `build.py`: the newest `v*` tag, a refusal when there is none, and the
  rows derived from the notebooks; `pages.yml` fetches tags.
- [x] The "Jupyter quickstart" disclosure in the hero, exclusive with the agent
  one; checked at 320 px in light and dark.
- [x] Tests in `tests/test_landing.py`: the built page has one row per notebook
  by glob; every Colab URL names the tag `build.py` found; every Read link
  resolves to a page the manual builds.
- [x] The maintainer's Colab run of each notebook at the tag, its result
  recorded in the handover. It asked for a restart (2026-10-09 entry).
- [x] The matplotlib floor at Colab's preinstalled 3.10.0 below Python 3.14,
  so the install needs no restart.
- [x] The two quickstarts as a row of toggle buttons over one panel.
- [ ] After the next release: one notebook re-run in Colab with no restart
  prompt and no "until 1.7" line.
- [x] Skill: none. The page is for people, and the agent quickstart is unchanged.

## Acceptance

After 1.7 is on PyPI, every Colab link on the deployed page opens a notebook
that runs top to bottom on a fresh Colab runtime.

```sh
.venv/bin/python docs/landing/build.py --site
.venv/bin/python -m pytest tests/test_landing.py tests/test_tutorials.py -q
.venv/bin/python -m ruff check src tests examples docs/landing
```

## References

- Colab's GitHub URL form: https://colab.research.google.com/github/
- `docs/landing/README.md`, the landing page's rulebook.

## Handover log

- **2026-10-09** — (second session) the maintainer's Colab run answered the
  open question. `%pip install rietx` does ask for a runtime restart, naming
  `matplotlib` and `mpl_toolkits`. Colab preinstalls matplotlib 3.10.0 and
  imports it at startup, and 1.7.0's floor of 3.10.5 makes pip upgrade it.
  The floor is now 3.10 on Python 3.11 to 3.13 and stays 3.10.5 on 3.14
  (`pyproject.toml`, an environment marker). That reaches Colab only with the
  next PyPI release, as does dropping the "Until rietx 1.7" line, since both
  live in the tagged tree and on PyPI. So no notebook gains a restart line.
  The hero's two quickstarts are now a row of toggle buttons over one panel
  at a time. The buttons never move, switching is one click, and the pressed
  button carries the state. A first version had the open panel grow over its
  neighbour; the maintainer saw it flicker on close, and the toggles replaced
  it. The Jupyter lead is the maintainer's copy.

  *Measured.* Colab's set (googlecolab/backend-info, 2026-10-09): Python
  3.13.16, matplotlib 3.10.0, numba 0.61.2, numpy 2.1.3. A Python 3.13 venv
  holding those three, dry-run: `rietx==1.7.0` upgrades matplotlib to 3.11.2,
  this tree leaves it at 3.10.0. Both upgrade numba, which Colab does not
  import at startup and the warning did not name. On matplotlib 3.10.0 the
  viz, figure, indexing-plot, structure-render, tutorial and example tests
  gave 228 passed, 1 skipped (`[dev]` venv, macOS). The toggles in chromium
  (playwright): no horizontal scroll at 1280, 375 or 320 px in either theme;
  both buttons at identical positions over 25 frames of a switch; copy takes
  the chosen install line; a `#quickstart` link from the footer opens the
  agent panel, scrolls the row under the top bar and focuses its button;
  without script both panels show and the buttons hide. The grow-over version
  had scrolled the page for 2 to 8 frames on close between 421 and about
  880 px, and its three discrete flips at 0.2 s were the flicker. The fast
  suite, on the grow-over tree, gave 8875 passed, 172 skipped,
  1 xfailed (`[dev]` venv, macOS, beside another session's pytest), no tests
  added. The full suite did not run: a lower floor installs nothing new here.

  *Review.* `/code-review high --fix` read the grow-over version. Its fixes to
  that CSS went with it; the one finding that outlives it is declined: no CI
  job pins matplotlib 3.10.0, so nothing yet holds the lowered floor true. The
  toggle commit had its own `/code-review medium --fix` pass. Fixed: a
  `#quickstart` link focused the first button by position, now the one that
  controls the agent panel; and closed panels were plain `hidden`, which
  find-in-page cannot reach where a closed `<details>` could. They are now
  `hidden="until-found"`, and a `beforematch` opens the matched panel through
  the toggle state (chromium: a text-fragment URL for "Sequential fits"
  opened the Jupyter panel and pressed its button; the closed row stays
  40 px). Declined: a browser test that opening one closes the other (none
  of this page's tests drives a browser, and `test_watch_browser.py`'s is
  local-only); the instant hide of the panel being switched away from.

  *Gotchas.* The test that pinned the exclusive `<details>` now pins one
  toggle per panel, every panel hidden and no button pressed at load; that
  opening one closes the other is the script's and was checked in a browser
  only. A playwright click on a quickstart radio's label times out, since the
  input sits over it by design: click the input.

  Next: a release carries both fixes to Colab; then the maintainer re-runs one
  notebook there to confirm no restart prompt.
- **2026-10-09** — the landing page now has a "Jupyter quickstart" beside the
  agent one. Opening either closes the other. It lists the five tutorial
  notebooks, and each can be read in the manual, opened in Colab or downloaded.
  The Colab links and the downloads are the notebooks as tagged at v1.7.0,
  which is what `pip install rietx` installs today. The page goes live with the
  next Pages deploy after this merges. One thing only the maintainer can do
  remains: run each notebook once in Colab. The v1.7.0 notebooks still carry the
  "Until rietx 1.7 is on PyPI" line, because the cut came before this WP. `main`
  has dropped it, and the next tag's notebooks will not carry it.

  *Done.* (1) The "until 1.7" lines are out of the five `.py` sources and
  `examples/tutorials/README.md`. The rebuilt notebooks changed in that cell
  only, with every output byte-identical. (2) `docs/landing/build.py`:
  `release_tag()` is the newest `vX.Y.Z` tag by version order, and with none it
  refuses. `notebooks(ref)` lists the tutorials at that ref via `git ls-tree`,
  filtered by the tutorials' own `SOURCES` glob, and takes each title from the
  first markdown cell's `# ` line. `--site` writes `site/notebooks/*.ipynb`
  byte-for-byte from the ref. `--ref HEAD` builds from another ref. `pages.yml`
  fetches the `v*` tags at depth 1. (3) The hero has a second `<details
  id="notebooks">`, sharing `name="quickstart"` with the agent disclosure.
  (4) `tests/test_landing.py` gains five tests. Every build in the module is at
  `REF = "HEAD"`, because CI's shallow checkouts carry no tags. The tag lookup
  and its refusal are tested in a throwaway repository. The landing README says
  all of this.

  *Review* (`/code-review high --fix`). It found one real defect: an
  inline-build test still called `assemble` with no ref, and so would have
  failed on every CI leg. It also added a cache on `notebooks()` and corrected
  the README's "no fetch" sentence. Six findings were declined. (a) The inline
  `dist/` build's Download link 404s; that build is only the artifact preview.
  (b) Read links come from `main`'s manual while rows come from the tag, so a
  tutorial renamed after a release would 404 there; this follows the WP's
  design, and a guard would need tags in CI. (c) The row-count test reads `HEAD`
  against the working tree, so it misfires only while a new tutorial is
  uncommitted. (d) The `--ref` argument is parsed with no check. (e) A notebook
  with no `# ` heading raises a bare `StopIteration`. (f) No JS reveal for a
  `#notebooks` link, since no such link exists yet.

  *Measured.* The fast suite gave 8875 passed, 172 skipped, 1 xfailed, `[dev]`
  venv, macOS, alone on the machine. `main`'s count was not measured. The +5 is
  the test-function count (19 → 24 in `test_landing.py`, one case each). The
  added tests cost 0.61 s in total, the dearest the tag test at 0.38 s, one
  run. `test_landing.py` passes 30 of 30 in a depth-1 clone with no tags, the CI
  condition. A depth-1 clone grew from 47 MB to 70 MB with the nine `v*` tags
  fetched. At 320 px and 1280 px, in both themes, nothing overflows and no row's
  links spill. Opening one disclosure closes the other (chromium, playwright).
  The full suite did not run: nothing here can move a measured number.

  *Not done, on purpose.* There is no Colab column in the manual's tutorials
  table. The manual links `main` throughout, and a column there would need the
  tag in `conf.py`. There is no "Open in Colab" link on the Python API code box;
  the WP said it "may" have one.

  *Gotchas.* The worktree guard refuses heredocs and loops that mention git or
  `github`. Put such commands in a scratchpad script and run it in one plain
  call.

  Next: the maintainer opens each Colab URL at v1.7.0 (the five in the built
  page, for example
  `https://colab.research.google.com/github/yue-here/rietx/blob/v1.7.0/examples/tutorials/01_quickstart.ipynb`)
  and runs it top to bottom on a fresh runtime. Record whether `%pip install
  rietx` asked for a runtime restart. If one did, add a line saying so to each
  notebook's opening cell, and the WP closes at the next tag. If none did, the
  WP closes on that record.
- **2026-10-07** — created. No open WP owns this: WP-1545 (🔄, in review)
  covers the notebooks and not their exposure, and WP-1331 and 1411, which
  built the landing page and its links home, are closed. Split from WP-1916
  because its gate is the 1.7 release and 1916's is none. Next: the "until 1.7"
  task, before the cut.
