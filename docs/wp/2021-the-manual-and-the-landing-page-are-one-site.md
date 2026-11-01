# WP-2021 — The manual and the landing page are one site

Milestone: unscheduled · Status: ✅ 2026-10-22 — one token file and one set of faces, header and footer for both pages; contrast measured to AA; menus drop the tab's prefix
Track: The repo's own process
Depends on: 1986 soft (its last two guides land in the same tree; either order works)

## Goal

The manual at `/docs/` and the landing page at `/` read as one site. They share one palette
and one pair of typefaces from one token file, one logo that goes home and one footer. The
manual carries none of pydata-sphinx-theme's chrome that has no job here: the footer credit,
the collapse rail, "Section Navigation", "Show Source", and a breadcrumb that repeats the
title. The landing page's unwritten rules are written down, and both pages are held to them.

## Context

### What there is

- **The manual** is pydata-sphinx-theme 0.23 defaults plus three things of ours:
  `docs/docs/_static/custom.css` (the bibliography label, the numbered-equation grid, the
  brand's two colours, the drawer's wrap), the two header templates
  `docs/docs/_templates/rietx-brand.html` (mark + wordmark → the manual's front page) and
  `rietx-landing.html` (an orange mark → `rietx.org`), and `html_theme_options` in
  `docs/docs/conf.py`. WP-1986 made the split deliberate (c06871a, "teal brand to the front
  page, orange mark to the landing page"); this WP reverses it.
- **The landing page** is `docs/landing/src/shell.html` (tokens, top bar, theme toggle,
  footer) and `index.html` / `why.html`, built by `docs/landing/build.py`;
  `docs/landing/README.md` is its rulebook. Its tokens are a `:root` block, written three
  times (light, dark by system preference, dark pinned): warm neutrals (`--bg #fbfaf8` /
  `#15110d`, `--surface`, `--surface-2`, `--ink`, `--ink-2`, `--muted`, `--faint`, `--rule`,
  `--rule-strong`), one accent (`--accent #c65d0a` / `#ff9d4d`, `--accent-ink #a34c06` /
  `#ffb679`, `--accent-soft`), `--ok`/`--warn`, and `--sans` Instrument Sans, `--mono` IBM
  Plex Mono.
- **There is no style guide document.** Searched 2026-10-22: the repo, its history, and the
  maintainer's artifacts. "rietx" and "rietx landing preview" are builds of the page, with
  tokens byte-identical to `shell.html`. "House Style Plates" is the matplotlib figure style,
  and "Yue Wu Style Guide" is the voice of a blog. The rules exist only as CSS comments:
  - every bordered box is a button or a link (`index.html:4`, `shell.html:133`);
  - a command is drawn as code, flat and tinted with no border, so it never passes for a
    button, and its copy icon is the one control in it;
  - three layers, two type sizes in a disclosure;
  - hover styles only where the device hovers (a touch screen keeps `:hover` on the last
    button tapped);
  - the top bar's `gap` is a minimum, and at phone widths the gaps give way before the words;
  - the theme is the system's until a click pins one, with no third state, and the glyph
    comes from `only-light`/`only-dark` rather than script.

  The de-facto scales are in the CSS and nowhere stated:
  - **Type:** body 16px/1.55; h1 `clamp(1.9rem,4.2vw,2.8rem)`; h2 1.5rem; headings weight 600
    at −.01em; small labels .72–.75rem, uppercase, .05–.06em tracking, `--faint`.
  - **Radii:** 8px for buttons and the command chip, 10px for code boxes and figures, 12px for
    the animation rig, 999px for the theme button.
  - **Layout:** `.wrap` 1080px with a 24px gutter (16px under 360px); controls 40px tall with a
    `--rule-strong` border that turns `--accent` on hover.

### Measured 2026-10-22

Built from `main` 2330afc. Read in headless Chromium at 1440, 900 and 390 px, in both
themes, through computed styles.

| where | what the reader sees | what it is |
|---|---|---|
| everywhere | cool slate ground (`#14181e` dark) against the landing page's warm `#15110d` | pydata's `--pst-color-background` |
| everywhere | four accent hues: teal links and current items (`#3fb1c5`), violet on every link hover (`#9c5ffd`), pink inline code (`#f3c7ee`, magenta in light), and the orange landing mark | `--pst-color-primary`, `-secondary`/`-link-hover`, `-inline-code`, `--rietx-landing` |
| everywhere | body and headings in `system-ui`, code in `ui-monospace`; only the five letters of the wordmark load Instrument Sans (a Google Fonts `text=` subset) | `--pst-font-family-base`, `-monospace`; `conf.py` `html_css_files` |
| header | five controls, three looks: a 42px rounded search box, a 34px bordered "dev" box, a theme dropdown with a caret, then two bare icons | `navbar_end`, `navbar_persistent` |
| header | the theme control has three states (light, dark, auto) where the landing page's has two, and the two pages store the choice under different keys on one origin (`rietx-theme` against pydata's `theme` and `mode`), so a theme pinned on one page is not the other's | pydata `theme-switcher`; `shell.html:341` |
| drawer, < 960 px | the version, theme and two icon controls sit directly under the last tab at mismatched heights; the current tab is not marked; hovering a tab turns it violet | `.sidebar-header-items` |
| left sidebar | 25 % of the width: 368 px at 1440 for five entries. "Collapse Sidebar" is an underlined link-coloured text button; collapsed, it leaves an 80 px rail with a full-height rule for one 20 px icon. The heading "Section Navigation" is 19.2 px weight 600 and adds nothing to the tab already marked | `--pst-sidebar-primary-width`; `sidebar-collapse` and `sidebar-nav-bs` components |
| right sidebar | "On this page" is 14.4 px weight 400 with a list icon, unlike the left heading. The current entry turns weight 600 (re-wrapping its text) and teal, its bar not on the column's rule. "Show Source" is an underlined teal link with a file icon | `page-toc`, `sourcelink` |
| article head | the breadcrumb is 0.8rem with **every** item bold, and its last item is the page's own title, so on a tab's front page it reads "⌂ › Concepts" directly over an H1 "Concepts" | pydata `components/breadcrumbs.html`, `_breadcrumbs.scss` |
| article | tab sets (macOS, Linux, Windows) draw an accent-coloured border round the whole panel, a bordered box that is not a control | sphinx-design `--sd-color-tabs-*` |
| article | Previous/Next titles are 17.6 px bold and underlined | `.prev-next-title` |
| front page | the H1 "rietx" repeats the logo; the right column holds only "Show Source" | `index.md`; `secondary_sidebar_items` |
| footer | "Created using Sphinx 9.1.1." and "Built with the PyData Sphinx Theme 0.23.0.", a 59 px bar with nothing of ours | `footer_start`, `footer_end` |
| dev banner | deep red bar with a pink button, on every dev page and so on every preview | `show_version_warning_banner` |
| figures | the light twins are opaque white (`make_figures.py:82` saves only the dark twin transparent), so on a warm ground each light figure is a white box | `docs/docs/make_figures.py` |
| diagrams | mermaid's stock `default`/`dark` themes, lilac nodes | `sphinx_shared.MERMAID_*_THEME` |

### The title prefixes

Seven Concepts pages are titled "About …" and 24 Guides "How to …". The rule is stated on
each tab's front page (`concepts/index.md:3`, `guides/index.md:3`). It came from WP-1975 F5,
which read Diátaxis as giving explanation an *implicit* "About" and how-to guides a literal
"How to". It was written for a nested tree in which each page would carry its type as a
badge (WP-1975 lines 625-632, "titles doing the labelling for free"). WP-1978 then chose six
tabs, so the tab already says the type. No test enforces the prefix. 173 hand-written link
texts in 61 files quote a title, so renaming a title means editing its link texts too.

### Seams

- **pydata 0.23 options:** `logo`/`logo_link`, `navbar_start`/`navbar_end`/`navbar_persistent`,
  `html_sidebars` (the default `sidebar-collapse, sidebar-nav-bs`), `secondary_sidebar_items`
  (default `page-toc, edit-this-page, sourcelink`; a dict keys it per page),
  `article_header_start` (`breadcrumbs`), `footer_start`/`footer_center`/`footer_end`,
  `show_version_warning_banner`, `pygments_light_style`/`pygments_dark_style`.
- **CSS variables:** `--pst-color-*` and `--pst-font-family-*`, on `html[data-theme]`. pydata
  always resolves `auto` to `light` or `dark` on that attribute, so the landing page's
  `:root[data-theme="dark"]` selectors work unchanged on the manual. Four gotchas, read from
  the theme's v0.23.0 source:
  - The mapping goes on `html[data-theme="light"]` and `html[data-theme="dark"]`, where
    pydata defines its own variables; a bare `:root` rule loses on specificity.
  - The heading colour is `--pst-heading-color`, not `--pst-color-heading`. `_base.scss`
    writes the fallback without `var()`, so overriding the second does nothing.
  - `--pst-sidebar-primary-width` is a registered `@property` with `inherits: false`, set on
    `.bd-sidebar-primary` from the `lg` breakpoint (992 px). Override it there, inside the
    same media query.
  - `--pst-color-link-hover` defaults to `--pst-color-secondary`, which is where the violet
    comes from.
- **The theme switcher** is a three-item dropdown (System, Light, Dark). It writes
  localStorage `mode` (`auto`/`light`/`dark`) and `theme` (the resolved one) and mirrors them
  to `html[data-mode]` and `html[data-theme]`; the first-visit default is
  `html_context["default_mode"]`. It has no two-state option and exposes no `setTheme`, so a
  toggle is our own component writing both keys and both attributes.
- **A component is a template:** one named in `_templates/` shadows the theme's of the same
  name, as `rietx-brand.html` already does for the brand.
- **Sphinx titles:** a toctree entry's explicit title (`Short label <doc>`) relabels the
  sidebar and nothing else. The H1, `<title>`, the breadcrumb and a bare `{doc}` link keep
  the page's own title. Checked on a two-page pydata 0.23 build, 2026-10-22.

### Tests that pin today's choices

These are the tests whose assertions change on purpose:
- `tests/test_manual.py::test_the_new_trees_marks_are_the_favicons` pins `rietx-landing.html`
  and the `--rietx-ink` hexes to the favicon.
- `::test_every_new_tree_page_brands_its_header_and_links_the_landing_page` pins the brand's
  href to the manual's front page, and the orange mark's to `DOCS_URL`.
- The front-page test pins the three card titles and the six tabs, which do not move.

`docs/docs/check_equations.py` measures whether each numbered equation fits its column, so a
change of face or of column width re-runs it.

### The tier of each rule this WP adds

None is a heuristic in the generality sense. The WP changes no diagnostic, threshold, default
or automatic action in the package, so `rietx._audit` gains no row. The contrast bar it adds
is named practice: WCAG 2.2 AA, 4.5:1 for body text and 3:1 for large text and UI parts.

### Decisions

Taken by the maintainer on 2026-10-22, in the session that filed this WP:
1. The logo goes to the landing page, and the orange mark goes.
2. The footer credit goes.
3. The collapsed rail is too big.
4. The title prefixes and the breadcrumb are to be looked at.
5. **A: the manual takes the landing page's warm palette** (the maintainer, 2026-10-22).
6. **B: left to the session** (the maintainer, 2026-10-22), which took a narrower form than
   it had recommended: **both tabs' menus drop the prefix, and every title keeps it.** Each
   Concepts and Guides toctree entry is its page's H1 less "About" or "How to"; the H1,
   `<title>`, prev/next, search and every link keep the full title.  Dropping "About" from
   the H1s too was measured against the 66 places a concept title is quoted in prose, and
   there the word does work: a link reading "About the report" followed by "describes its
   three layers" names a page, where one reading "The report" reads as the `FitReport`
   describing itself.  The menu is where the tab already says the type, which was the
   maintainer's point.

The two as they were put:
- **A. Which way the palette moves.** Recommended: the manual takes the landing page's warm
  grounds and orange accent, because the landing page is the designed one and the manual's
  teal is pydata's default primary at 0.23. The cost is to re-choose the semantic colours
  (note, warning, danger, the dev banner) so that none is the accent. The landing page's own
  `--warn` (`#b5561b` / `#ffa25c`) is within a few degrees of `--accent`.
- **B. The titles.** The sources split three ways:
  - Diátaxis asks for a literal "How to …" on a how-to guide, calling a bare topic "very bad".
    For an explanation, "About" is only a test the title must pass, so writing it out is
    optional.
  - Google's style guide titles a task with a bare infinitive ("Create an instance") and a
    concept with a noun phrase, and uses neither prefix.
  - Microsoft's guide does the same.

  Docusaurus (`sidebar_label`) and Starlight (`sidebar.label`) both keep a page's title apart
  from its nav label. The usual split gives the H1, `<title>` and search results the full
  title, since they are read without the section, and gives the nav a short one, since the
  tab already names the type. Recommended: drop "About" everywhere, and give every Guides
  entry a short label without "How to" while its H1 keeps it. The alternative is Google's
  bare infinitive in both places.

## Non-goals

- The GUI, `rietx watch` and `rietx compare` keep their palette (`viz/theme.py`, WP-1429).
  They are an application, not this site.
- The figure palette (`viz/plots.PALETTES`). Only the light twins' *ground* changes.
- New content, and the guides WP-1986 still owes.
- Replacing pydata-sphinx-theme. Everything above is an option, a CSS variable or a
  one-component template.

## Tasks

- [x] **Write the house style down**, as `docs/landing/README.md` § House style covering both
      pages: the rules now in CSS comments, the scales above, the label style, and which
      colour does which job.
- [x] **One token file.** Move the landing page's `:root` blocks to `docs/landing/src/tokens.css`,
      inlined by `build.py` and copied into the manual's static files by `conf.py`.
      `custom.css` then *maps* `--pst-color-*` onto those names and spells no hex of its own.
      Decide the semantic colours here.
      A test computes the WCAG contrast of every text-on-ground pair in both themes.
- [x] **Two typefaces, self-hosted.** Ship Instrument Sans and IBM Plex Mono as woff2 under the
      manual's `_static/fonts/`, with their OFL licence beside them, for body, headings and
      code; drop the Google Fonts subset link. A versioned tree is read for years, so it must
      not depend on an outside URL. Re-run `check_equations.py`.
- [x] **Header.**
      - The brand links to `rietx_home`, as NN/g's subsite rule asks: the top-left logo goes
        to the main home. `rietx-landing.html` and its CSS are deleted.
      - The theme control becomes the landing page's two-state toggle, as our own component
        writing pydata's `mode` and `theme` keys and both `html` attributes. The landing page
        moves from `rietx-theme` to those keys, so one choice holds across the origin.
      - The version switcher loses its box.
      - In the drawer: spacing above the controls, and the current tab marked.
- [x] **Sidebars.**
      - Set `--pst-sidebar-primary-width` to a fixed width in the 17–19rem band that
        Docusaurus (300 px) and Starlight (18.75rem) sit in. It is 25 % today, up to 22rem.
      - Set `html_sidebars = {"**": ["sidebar-nav-bs"]}` to drop the collapse button. Its
        state is not kept from page to page in 0.23, so it re-expands on every click through.
      - Replace "Section Navigation" with the tab's name, since the `<nav>` label already
        says what the column is.
      - Give both sidebar headings one small label style, with no icons.
      - Mark the current entry by colour and bar only, with the bar on the rule; a weight
        change re-wraps the text.
      - Replace "Show Source" (`secondary_sidebar_items`, `html_show_sourcelink`) with a quiet
        link to the page's markdown twin (WP-1980), or drop it.
- [x] **Breadcrumb.** End the trail at the parent, never the page itself (GOV.UK's form).
      Name its root in a word ("Manual") rather than a house icon, so on a tab's front page
      it reads "Manual ›" above the H1 and repeats nothing. Every page but the front page
      then links the manual's home, which NN/g's subsite rule wants once the logo goes to
      `/`. Set it in regular weight and `--muted`, so the H1 is the only heavy thing at the
      top of the article. This needs our own `breadcrumbs.html`.
- [x] **Footer and banner.**
      - The landing page's line (licence, GitHub, Cite, Sources) and the manual's version, in
        `footer_start`/`footer_end`, with `html_show_sphinx = False`.
      - The dev banner becomes a quiet one-line tag in the manner of GOV.UK's phase banner.
        The warning colour stays for an older release's banner, which pydata draws in the
        same red today.
- [x] **Inside the article.**
      - Inline code is ink on a tint.
      - Links are `--accent-ink` with a tinted underline, and the violet hover goes.
      - Tab sets draw no border round the panel, only a rule under the tabs.
      - Previous/Next lose the underline.
      - The front page gets a real lede and no right column.
      - Mermaid uses `base` with theme variables from the tokens. *Done otherwise*: the
        extension passes one init config for both themes and mermaid's variables are literal
        colours, so `custom.css` colours the diagram from the tokens over `neutral`/`dark`.
      - The light figure twins are saved on a transparent ground; regenerate the 16 figures.
        *Done otherwise*: `make_figures.py`'s reason for an opaque light twin stands, so they
        are saved on the light `--bg`, read from `tokens.css`; all 16 regenerated.
- [x] **Titles** (decision B). As recommended: drop "About" from the seven Concepts H1s and
      their link texts. Give each Guides toctree entry an explicit short title without "How
      to", while the H1 keeps it. Update both front pages' sentence. *Taken narrower*
      (Decision 6): both tabs' menus drop the prefix and every title keeps it.
- [x] **Tests.** Change the two brand tests above. Add:
      - the token-file test, and the contrast test;
      - every built page's breadcrumb omits its own title, and every page but the front
        page links the manual's home;
      - no page names a hex outside the token file;
      - every page is free of the theme credit and of the collapse control.

      Extend `docs/landing/tools/page_shots.js` to shoot the manual's front page, a Concepts
      page and a Theory page at 1440, 900 and 390 px in both themes, beside the landing page.
- [x] Skill: none expected. The skill links `/docs/` and quotes no page title (grep
      2026-10-22: no `[How to` or `[About` link in `docs/skill/`). Re-check at the end.
      Re-checked at the close: none, and no title moved.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_manual.py tests/test_manual_api.py tests/test_landing.py tests/test_docs_versions.py -n auto --dist loadgroup
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
.venv/bin/python docs/docs/check_equations.py
```

Plus a look: the page shots at three widths in both themes, put beside the landing page's,
with no hue in the manual that the token file does not name.

## References

- pydata-sphinx-theme 0.23 user guide: branding, layout, theme variables.
  <https://pydata-sphinx-theme.readthedocs.io/en/stable/user_guide/index.html>
  The claims above about its internals were read from the v0.23.0 tag's source.
- Diátaxis, the how-to and explanation pages. <https://diataxis.fr/how-to-guides/>,
  <https://diataxis.fr/explanation/>
- Google developer documentation style guide, headings.
  <https://developers.google.com/style/headings>; Microsoft Writing Style Guide, headings.
  <https://learn.microsoft.com/en-us/style-guide/scannable-content/headings>
- Docusaurus `sidebar_label`, Starlight `sidebar.label`: a nav label apart from the title.
  <https://docusaurus.io/docs/api/plugins/@docusaurus/plugin-content-docs>,
  <https://starlight.astro.build/reference/frontmatter/>
- Breadcrumbs. NN/g includes the current page, unlinked:
  <https://www.nngroup.com/articles/breadcrumbs/>. GOV.UK ends at the parent:
  <https://design-system.service.gov.uk/components/breadcrumbs/>. WCAG technique G65 accepts
  both: <https://www.w3.org/TR/WCAG20-TECHS/G65.html>.
- NN/g, subsites: the logo goes to the main home, and every subsite page links the subsite's
  home. <https://www.nngroup.com/articles/the-rise-of-the-subsite/>
- GOV.UK phase banner, a quiet "still being built" cue.
  <https://design-system.service.gov.uk/components/phase-banner/>
- Bold without layout shift. <https://css-tricks.com/bold-on-hover-without-the-layout-shift/>
- WCAG 2.2, success criteria 1.4.3 and 1.4.11. <https://www.w3.org/TR/WCAG22/>
- Instrument Sans and IBM Plex Mono, SIL Open Font License 1.1.

The web sources were read from search extracts on 2026-10-22, since the session's proxy
refused direct fetches; re-read each before quoting it in the manual.

## Handover log

### 2026-10-22 (3rd session) — the guards, the house style and the review; closed

The manual and the landing page now share one set of colours, faces, header and footer,
and the sharing is guarded rather than remembered. A test fails if the manual spells a
colour of its own. Another fails if any text colour falls below WCAG AA on a ground it is
set on, if the two headers' marks drift from the favicon, if a breadcrumb names its own
page, or if a Concepts or Guides menu label stops being its title less the prefix. The
house style, which colour does which job, is written in the landing page's README for the
next change to follow. The review found that the OS could undo a theme a reader had
pinned, which is fixed and checked in a browser. Nothing in the package changed, so no
measured number moved.

*Done*, on top of the second session's work:
- **Tests.** `tests/test_landing.py` § The site's colours: the two dark blocks are one set
  of values, every text colour clears AA on each ground `LEGIBLE` lists, the contrast
  measure itself is checked against WCAG's fixed points, and every landing page inlines
  the token file. `tests/test_manual.py` replaces the two brand tests that pinned the
  retired mark with nine checks:
  - the favicon is the mark for both headers, and its fills are `--accent`;
  - the brand goes to the site's home;
  - the breadcrumb starts at "Manual" and stops at the parent;
  - no page credits its tools or carries the collapse control;
  - the manual spells no colour;
  - the theme button is the landing page's;
  - each menu label is its title less the prefix, once per tab;
  - each page links its markdown twin.

  Each new guard was made to fail once on purpose, with the message expected.
- **Two contrast fixes the test turned up.** The landing page's `$` prompt was `--faint`
  on `--surface-2` (4.25:1) and takes `--muted`. Sphinx's "Hide search matches" link is
  drawn into an empty `#searchbox` above every article and was white on the light accent
  (4.22:1); it is now a plain link, so no page sets words on the accent.
- **One small label**: .75rem, weight 600, .05em, uppercase, on both pages. It was four
  sizes. The animation rig keeps its own smaller scale.
- `docs/landing/README.md` § House style, and its rows for `tokens.css` and the favicon.
  `ATTRIBUTION.md` § Fonts the manual serves. `page_shots.js` takes `SITE=` and shoots the
  landing page with three manual pages at three widths. `default_mode: "auto"`, in
  `html_context`, where pydata reads it.
- `est-cov` (8.5) set on two rows (below).
- WP-1986's `### Inherited` now carries the Guides label rule for its two remaining guides.

*Measured* (Linux x86-64, the worktree's `.venv`, `[dev]`):
- Contrast, light / dark, the tightest pairs: `--faint` on `--bg` 4.59 / 4.99, `--ok` on
  `--surface-2` 4.59 / 8.52, `--accent` on `--surface-2` 3.75 / 7.84 (bar 3).
- `check_equations.py`'s measurement, its own probe, viewports and thresholds driven from
  node, because this sandbox refuses jsdelivr and so MathJax 4.1.3 and its font were
  served from npm. On the branch, est-cov overran its cell by 4-8 px at both widths, and
  after the reflow all 156 numbered equations fit. The base, 2330afc, fails four here,
  est-cov by 47 px. That is likely in part a fallback face, since Google Fonts is out of
  reach in this sandbox too, so the branch's figure is the one in the face readers get.
- Acceptance: the four suites, 140 passed. `sphinx -W -E`, clean.
- Fast suite (`-m "not slow"`, the machine otherwise idle but for one collect-only pass): 11071 passed, 203 skipped, 3 xfailed, 1 failed, in 20:18. The failure was
  `test_every_relative_link_resolves`, reading Decision 6's quoted `(…)` as a link. That
  quote was written in the second session; it is reworded, and the file passes. The branch
  adds 13 cases by collection: `test_landing.py` 33 → 39 and `test_manual.py` 50 → 57,
  the latter net of the two brand tests removed. No new skip.
- The added tests in this run's junit: 0.22 s over 12 names (15 cases). The slowest,
  0.08 s, walks the 123 built pages for the breadcrumb. None joins the slow tail, since
  all of them share the one manual build the suite already makes.
- The full suite was not run. No package code changed, so no measured number can move
  (`tests/CLAUDE.md` § Running, rung 3).

*Review* (`/code-review high --fix`). It made five fixes, all landed:
- a pinned theme snapped back when the system scheme changed, because pydata's `auto`
  listener outlived our pin;
- the version menu kept the old theme's dropdown class;
- the landing page never read its old `rietx-theme` key once the manual had stored `auto`;
- the theme script's header claimed a first visit stores nothing;
- `make_figures.light_ground` split the token file before stripping comments.

The theme fixes were driven in chromium across both pages: a pin survives the system
turning dark and back, the menus follow, a choice on either page holds on the other, the
old key carries over once, and an unpinned page follows the system. *Declined*: moving
`site_tokens` out of `test_landing.py` into a shared module. The suite already imports
across test modules (`test_absent_phase.py`, `test_acceptance_srm676a.py`), so a helper
module would be new structure that fixes no bug.

*Generality*: not owed. `_audit.py` is untouched, and the WP adds no diagnostic,
threshold, default or automatic action (§ The tier of each rule this WP adds). The AA bar
is WCAG's, quoted.

*Gotchas*:
- pydata capitalises "Previous"/"Next" with a four-class selector, so the old label rule
  never reached them. Probe the computed style; a selector that reads right is not
  evidence.
- `default_mode` is a context key. As a theme option it is unsupported, and `-W` fails
  the build.
- `#searchbox` exists, empty, on every page.
- `ps aux | grep -c '[p]ython -m pytest'` counts its own command line when it shares one
  with a pytest launch.

*Not done, deliberately*: the landing page still loads its faces from Google Fonts. It is
one unversioned page, and the manual's copies sit under a per-version path.

Next: the maintainer reviews the PR, judging the page shots beside the landing page. On
merge nothing follows from this WP. WP-1986's two guides inherit the label rule.

- **2026-10-22** (second session, paused for a context compaction) — A and B settled (Decisions
  5 and 6). Landed and pushed, checked by eye in headless Chromium at 1440, 900 and 390 px
  in both themes against a local copy of the site:
  - `docs/landing/src/tokens.css`, inlined by `build.py` and loaded by `conf.py`;
    `custom.css` maps `--pst-*` and spells no colour. Semantic colours: `--warn` ochre
    (`#7d5f00` / `#e3c25b`, hue ~45° against the accent's ~26°), `--info` and `--danger`
    new, `--faint` darkened to `#7a7167` / `#8c8277` (it was 2.89:1 on the light page), and
    the two labels drawn on `--surface-2` take `--muted`, since no `--faint` near `--muted`
    passes there.
  - The fonts, the header (brand to `rietx_home`, `rietx-landing.html` deleted, a two-state
    toggle in `_static/rietx-theme.js`), the sidebars (18rem, no collapse, the tab's name),
    the breadcrumb, the footer, the banner (quiet for `dev`, `--warn` for an old release,
    told apart by the footer's `data-docs-version` through `:has()`), and the article.
  - The header measured 72 px against its declared 56 until `.bd-header__inner`'s padding
    and the brand's went; pydata inverts mermaid SVGs under dark (`filter: invert(.82)`),
    which `custom.css` undoes.
  - **Two deviations from the tasks as written.** Mermaid is not `base` with theme
    variables: the extension takes one init config for both themes and mermaid's
    variables are literal colours, so the tokens reach the diagram through `custom.css`
    over `neutral`/`dark`. The light figures are not transparent: `make_figures.py`'s
    reason for an opaque light twin (dark type unreadable in a dark viewer) stands, so
    they are saved on the light `--bg`, read from `tokens.css`.
  - The front page's H1 is "The rietx manual"; every page's answer sentence is styled as
    its lede.
  - Menus per decision 6. An incremental build left old labels in the sidebar of unchanged
    pages; `-E` showed them right, so judge a toctree change on a fresh build.

  **Not yet done**, in order: the tests (the two brand tests still pin the old templates
  and will fail; add the token, contrast, breadcrumb, credit/collapse and toctree-label
  tests); `docs/landing/README.md` § House style plus its rows for `tokens.css` and the
  favicon, and its "orange" non-converged line, now ochre; ATTRIBUTION.md rows for the
  two faces; `page_shots.js`; `check_equations.py`; the acceptance commands; then
  `/wp-handover`. Scratch tooling for the look (`shots.mjs`, `probe.mjs`, `assemble.sh`,
  `rebuild.sh`, a local mermaid 11.12.1 routed in place of the CDN) is in the session
  scratchpad, not the repo.
- **2026-10-22** — filed from the maintainer's review of the manual's look. No open WP owns
  it: WP-1986 is the guides and the old tree's retirement; WP-1443 is prose read by a
  newcomer; WP-1812 is the manual for rigid bodies. The measurements above are from that
  session's screenshots of `main` 2330afc. The breadcrumb, title, sidebar, logo and banner
  tasks follow the sources under References, which disagree on two points, both recorded:
  whether a breadcrumb ends at the page or its parent, and whether a task title says "How
  to". Next: settle decisions A and B with the maintainer, then start at the house-style
  task, since every later task cites it.
