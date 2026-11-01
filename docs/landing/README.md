# rietx.org landing page

The page served at `https://rietx.org/`, beside the manual at `/docs/`.
Written 2026-09-02 with Claude Code; entered the repository in WP-1331.
`python build.py` writes `dist/index.html`, the whole page in one file, which is
also what the mockup artifact shows. Since 2026-10-03 a second page sits beside
it: `why.html`, the maintainer's essay, linked from a hero button and the footer
rather than the top bar, which has no room for a fourth item at 320 px.

## What is here

| path | what |
|---|---|
| `src/shell.html` | what every page shares: the stylesheet, the top bar, the theme control, the footer. Placeholders `%%TOKENS%%` (`src/tokens.css`), `%%TITLE%%`, `%%DESCRIPTION%%`, `%%NOTE%%` (from `build.PAGES`), `%%MAIN%%` (the page), `%%FAVICON%%` |
| `src/tokens.css` | the site's colours and faces, the manual's too: § House style |
| `src/index.html` | the landing page's `<main>` and its scripts: the hero's copy buttons and quickstart disclosure, the animation. Placeholders `%%IMG:…%%`, `%%DEMO%%`, `%%TRANSCRIPT%%`. The hero draws a command to copy flat and tinted, like code, and every bordered box as a button or a link. The two quickstarts are a row of toggle buttons over one panel at a time. Opening one closes the other, a click on the pressed one closes it, and any `#quickstart` link opens the agent panel. The panel has no border, since every bordered box in the hero is a button or a link. Without script both panels show and the buttons do not. The agent prompt is written once, as markup, and `tests/test_landing.py` runs its install and skill commands. The Jupyter quickstart's rows are `%%NOTEBOOKS%%` |
| `src/why.html` | the essay's `<main>`. The words are the maintainer's, verbatim; only the links were added |
| `src/favicon.svg` | the site's one favicon, the manual's too, and the mark's authority: both headers copy its shapes inline. Its two fills are `--accent` light and dark, spelled because an icon reads no CSS (`tests/test_manual.py` holds all three equal) |
| `build.py` | `python build.py` → `dist/<page>.html` (everything inlined); `python build.py --site` → `site/` with every page, `img/`, `data/`, `notebooks/`, `favicon.svg`. The Jupyter quickstart's rows, Colab links and `notebooks/` downloads are the tutorial notebooks at the newest `vX.Y.Z` tag, read from git; with no tag it refuses, and `--ref HEAD` builds from another ref (§ How it is built). Each row's JupyterLite link opens the same notebook, by file name, in the JupyterLite site `pages.yml` builds to `/lite/` (`docs/lite/`). That site's copies are the Pages commit's, not the tag's. `PAGES` lists the pages, each with its title, description and footer line; a new page is a row there and a file in `src/` |
| `build_demo.py` | `python build_demo.py <bundle dir> data/demo.json 2` — the animation payload from the contributor's `curves.npz` + `metadata.csv`, decimated by the third argument (**always 2** for the committed file; see § The payload below). Refuses to write if any filename, scan index or specimen token from the bundle reaches the output |
| `data/transcript.json` | what the pane shows around the log: `prompt` (the run's prompt, cut to a few lines), `head` (the stdout before the series), `marks` (lines that land on a given frame: the chunk boundaries, the finalise summary), `report` (the agent's closing words, cut) and `note`. Cuts are marked `[…]`, file names and paths are bracketed stand-ins. `python tools/check_transcript.py <bundle dir> data/transcript.json` refuses any pattern filename, scan index, specimen tag, machine path or person from the bundle |
| `data/demo.json` | the built payload, **committed**, 0.99 MB: 275 × 649 obs and calc as base64 Int16, weight fractions, the gas/temperature programme. Each frame carries `t` (the file's clock, s) and `tm` (the plotted clock, min: the six pauses of 18–58 min between scans count as one 74 s interval; `pauses` lists them). Phases carry `name`, `html` and `support`; the three support phases are named `support 1`–`3` rather than by formula: `build_demo.phase_columns` takes their columns from the bundle's own header, in header order, so their names are in neither the payload nor the builder — and deliberately not in `build.LEAK` either, since a denylist publishes what it denies. Segments carry the atmosphere text and a colour `key` (`n2`, `h2`, `air`). `decimation` and `steps_per_fwhm` record the redaction. No filenames |
| `img/` | `fap-light/dark.png` from the first fit in `examples/tutorials/02_simple_rietveld.py` (drawn when it was `examples/fap_lab.py`, before WP-1545); `gui-history-light/dark.png`, the GUI at 1440×900 @2x with 24 nodes in 3 lanes |
| `tools/gui_shots.js` | builds the three-lane history in a running GUI (`rietx gui --port 8799 --no-open --state-dir …`, then `POST /api/examples/open {"name":"fap"}`) and screenshots it. Needs `playwright-core` and the cached Chromium; run from any directory with `PWC=<node_modules/playwright-core> OUT=<dir> node gui_shots.js` |
| `tools/page_shots.js` | screenshots in both themes at 1440, 900 and 390 px (`W=` to choose). `PAGE=<file>` shoots the built page whole. `SITE=<url>` shoots the site served with the manual at `docs/dev/`: the landing page whole, and the manual's front page, a Concepts page and a Theory page as a reader first sees them, which is the check after a change to anything the two share (§ House style) |
| `tools/check_transcript.py` | the leak check for the transcript; `build.py` runs the same token list over the whole page |
| `tools/rig_shots.js` | screenshots of the animation rig alone, both themes, at chosen frames (`FRAMES=120,274`) — the quickest check after a change to the panels |

## The agent pane

Nothing is outstanding here; both items below are in.

1. **The agent's run** (`data/transcript.json`, from the 2026-09-03 bundle's `agent_transcripts/`, the run that built the animation bundle: Claude Sonnet 5 under Claude Code, 2026-09-01, 2 h 7 min, 289 assistant messages, 154 tool calls). The pane pins the prompt at the top and streams the run log underneath, one line per pattern, in step with the panels: the page formats those lines from `demo.json` (index, temperature, atmosphere, status, Rwp — the run's own record of each fit), and `transcript.json` supplies everything around them. A gas or temperature step opens a marker; a non-converged fit is ochre (`--warn`); the closing report arrives with the last pattern, and the loop holds ~6 s there before restarting. To re-cut it: pick messages by index from the JSONL, keep the text verbatim, mark cuts `[…]`, replace file names with `[pattern n]` (n = `series_index` from `metadata.csv`), paths with `[raw-data directory]` and people with a role, then run `tools/check_transcript.py`.

2. **The model name** in the rig header comes from `transcript.json`'s `model` field, today `Claude Sonnet 5`. With the file absent the header reads "model to confirm" instead, which is what a checkout without the payload shows.

## How it is built and served

`.github/workflows/pages.yml` runs `python docs/landing/build.py --site` and
copies `site/` into the site root, so the landing page lands at `/`. The manual
builds under `/docs/` (`docs/docs_versions.py`), and no sphinx build writes
outside it, which is what keeps `/` this page (`tests/test_landing.py`).
Everything the page needs is in the repository, so a fork builds the whole
thing with no secret. The one fetch is the release tags, which the Jupyter
quickstart reads (below).

- A link meaning "the manual" is `https://rietx.org/docs/`, which sends the
  reader to the newest release's tree, or to `dev/` before a release carries
  one. A chapter link uses the retired old tree's address (`/using/<x>.html`,
  `/<theory>.html`), whose redirect stub (`docs_versions.RETIRED`) resolves the
  same way per page, so the page needs no edit at a release. A stub carries a
  `#fragment` over by script, but a chapter's sections took new heading ids on
  their new pages, so a stub link carries none. A page the old tree never had
  links `/docs/<version>/` directly.
- `dist/`, `site/` and `preview.html` are gitignored — one page built three ways.
  `data/` is **not**, and § The payload says why.
- The fluorapatite example is the first fit in
  `examples/tutorials/02_simple_rietveld.py` (WP-1545), shown with bare file
  names where the tutorial reads the copies shipped in the wheel.
  `tests/test_tutorials.py` executes it on every push. It also holds the code
  box to that cell line for line, less only import lines. It holds every
  stretch of the output panel between `…` cuts to the cell's committed output,
  in order. So rebuilding the notebook with new numbers fails the test until
  the panel is refreshed.
- The Jupyter quickstart links the notebooks at the **newest release tag**, never
  at `main` (WP-1917). `main`'s notebooks are built against the next `.dev0`, so
  a Colab link to them could call API that `%pip install rietx` does not
  install. The workflow fetches the `v*` tags for this, and `build.py` refuses
  when it finds none rather than falling back to `main`. The test suite builds
  at `HEAD`, because CI's shallow checkouts carry no tags. The JupyterLite links are
  the one exception: `/lite/` serves the Pages commit's notebooks with a wheel
  from that commit (WP-1966), and a link matches its row by file name only.
- `rietx._about.DOCS_URL` stays `https://rietx.org`, the site root. `help.py`'s
  anchors are `page.html#id` under `_about.docs_base`, the installed version's
  tree, so they do not pass through this page or the stubs.

## House style

The landing page and the manual are one site to a reader, and since WP-2021 they
share one set of values. `src/tokens.css` holds every colour and face. `build.py`
inlines it at the top of each page's stylesheet. The manual's `conf.py` copies it
in, and `docs/docs/_static/custom.css` maps pydata-sphinx-theme's names onto it.
Neither stylesheet spells a colour of its own, and `tests/test_manual.py` fails on
one in the manual's. A change of colour is one edit there and reaches both pages.

**Which colour does which job.** A colour is chosen by its job, never by its look.

| token | its job |
|---|---|
| `--bg` | the page's ground. The manual's light figures are saved on it, so they show no edge (`docs/docs/make_figures.py`) |
| `--surface` | a raised panel: a card, the animation rig, a code box, a figure's frame |
| `--surface-2` | a flat block: code, a command, inline code, the dev banner |
| `--surface-3` | a hover ground, and nothing else |
| `--ink` | body text and headings |
| `--ink-2` | secondary text: navigation links, the lede, the footer's links |
| `--muted` | captions and metadata, and any label on `--surface-2` |
| `--faint` | the small label and separators, on `--bg` and `--surface` only |
| `--rule`, `--rule-strong` | hairlines; the strong one borders a control or a card |
| `--accent` | the mark, the current item's bar, the open tab's underline, a focus ring, a link's underline. It marks; it never sets words |
| `--accent-ink` | the accent as text: links, and code keywords on the landing page |
| `--accent-soft` | a tinted ground: a link target |
| `--ok`, `--warn`, `--info`, `--danger` | states, and only states. `--warn` is ochre, so a warning never reads as the brand |
| `--calc`, `--obs`, `--diff`, `--p0`…, `--heat0`…, `--atm-…`, `--support…` | the animation's data, the landing page's alone |

**Every text colour is legible where it is set.** Each clears WCAG 2.2 AA, 4.5:1,
on each ground the table puts it on, and `--accent` clears 3:1 as a mark. This is
measured, not judged by eye: `tests/test_landing.py`'s `LEGIBLE` lists the pairs.
A new text colour, or an old one on a new ground, is a row there first. The old
`--faint` read as fine and measured 2.89:1.

**Light and dark.** The file writes dark twice: once for the system's choice and
once for a pinned theme. The test holds the two blocks equal. Both pages pin a
theme the same way, with one two-state button that writes pydata's own keys,
`mode` and `theme` in `localStorage`. The site is one origin, so a choice made on
one page holds on the other.

**Type.** Instrument Sans for text and headings, IBM Plex Mono for code. The
manual serves both from its own tree (`docs/docs/_static/fonts/`, OFL, in
`ATTRIBUTION.md`), since a versioned manual must outlive a font service. The
landing page loads them from Google Fonts. Headings are weight 600, tracked
−0.01em. The manual's scale is h1 2.25rem, h2 1.5rem, h3 1.2rem and h4 1.05rem,
over a 1rem body.

**The small label** is .75rem, weight 600, tracked .05em and uppercase. It is
`--faint`, or `--muted` on `--surface-2`. It heads a table, a code box, the
quickstart's prompt, the manual's two sidebars and its previous and next links.
The animation rig's labels are the one exception: they stay a size down, at the
rig's own scale.

**Chrome.** The bar is 56 px, with the ground showing through it, and is the same
on both pages. It has the mark and the wordmark on the left, which go to `/` from
every page, and quiet controls of one height on the right. The footer is one line
of links over a `--faint` note. The current item in a menu is `--ink` beside a
2 px `--accent` bar, never bold. A block of code is flat: `--surface-2`, no border,
8 px radius. A card is bordered with `--rule-strong`, and its border takes the
accent on hover.

**The page's opening sentence is its lede.** Every manual page answers its title
in the paragraph directly under the H1 (the page contract), and that paragraph is
set at 1.1rem in `--ink-2`.

## The payload

`data/demo.json` is in the repository because it is **decimated to every second
measured channel**. At the acquisition's own 0.0501° step the file would be a
copy of a contributor's unpublished in-situ series; at 0.1002° it sits at 2.38
steps across a peak, against the 5-to-10 rietx itself asks for, so it is a figure
of that series and not the series. `tests/test_landing.py` asserts that rather
than trusting it. The page itself does not say so. Its caption describes the
measurement and credits it (WP-1411 moved the description there from the section
head, which now opens on what the agent was asked to do), and says nothing about
the step, so `decimation` and `steps_per_fwhm` in the payload, and this section,
are where the redaction is on the record.

**Decimated, not averaged, and the difference matters.** A mean of *k* channels
divides the counting noise by √*k*: the observed cloud tightens onto the
calculated curve and the difference curve flattens, so the panel shows a better
fit than the Rwp printed beside it. Measured at k = 2 and k = 3 by rendering
both. Keeping every *k*-th channel keeps each point a real measured channel,
noise and all; what it costs is peak *shape*, the calculated line growing spikier
as apexes fall between retained channels.

Everything else the fence covers is unchanged: no filename, scan index, specimen
token or path from the bundle reaches either file, `build.py`'s `leaks()` and
`tools/check_transcript.py` enforce it case-insensitively, and the bundle's own
files (`curves.npz`, `metadata.csv`, plots, logs, `agent_transcripts/`) stay out
of the repository entirely.

**People are now the one exception, and it is a credit rather than a leak.** The
fence started with a people arm, on the reasoning that a name in a run log is a
name the bundle did not offer to publish. The caption then carried the credit the
contributors asked for, which names all of them — and a person the page thanks
cannot also be a token that fails the build, so the arm is empty. What keeps a
machine path out is `/Users/`, `/Volumes/` and `LEAK_RE`, none of which ever
moved; the transcript's own cut still replaces a name with a role, because a
name *inside the run log* is still not a credit.

## Sources behind the page's numbers

- Fluorapatite: GSAS-II tutorials `LabData` (`tests/data/README.md`); GSAS's converged values from `FAP.EXP`; the CuKa preset wavelengths are Hölzer et al. 1997 (`schemas/instrument.py`, ref 7d). Cell +60 ppm = 1.5405929/1.5405.
- Validation rows: `docs/VALIDATION.md` (generated from `tests/validation_matrix.py`), quoted verbatim from its "Measured" lines.
- Animation: the contributor's bundle README and `metadata.csv`; the atmosphere tokens decode as `1N2atm` = N₂, `2H2mixatm` = 0.2 vol % H₂ in N₂ at 1 L/min, `3airatm` = air (the leading digit is a gas-step counter; the bundle's 2026-09-03 rebuild states this, correcting its first release and the maintainer's own 5 % reading); 272/275 converged; the run reported PHASE_UNCONSTRAINED on the third support phase in every pattern (bundle README caveat 2, and the campaign report).
