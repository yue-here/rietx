"""Anti-divergence guards for the theory manual (WP-0604).

The manual's design rule is that it structurally cannot drift from the code:
constants are injected from the live package at build time (an undefined MyST
substitution is a warning and the build runs -W), every displayed equation
names the source symbol whose docstring it transcribes, and every bibliography
entry is cited.  These tests are what make each of those claims executable.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

from rietx._about import DOCS_URL

pytest.importorskip("sphinx")

MANUAL_DIR = Path(__file__).resolve().parent.parent / "docs" / "manual"
# rglob, not glob: Part 1 lives in docs/manual/using/ (WP-1067).  A doc tree's
# shape should not be set by a test's glob, and the guards below are what a
# future Part 1 page inherits by being collected here.  _build/ is a local
# sphinx output directory, not source — an rglob that walks it collects a stale
# copy of every chapter.
CHAPTERS = sorted(
    p for p in MANUAL_DIR.rglob("*.md") if "_build" not in p.relative_to(MANUAL_DIR).parts
)

#: The new manual (WP-1978), built beside the old one until WP-1986 retires it.
#: Its pages share the old tree's register and trail guards below, and carry the
#: page contract of their own (§ The new tree).
DOCS_TREE = MANUAL_DIR.parent / "docs"
#: Build outputs, never pages.  `_generated/` holds the Reference tab's bodies,
#: which a committed page includes (`docs/reference_pages.py`).
NOT_PAGES = {"_build", "_generated"}
DOCS_PAGES = sorted(
    p for p in DOCS_TREE.rglob("*.md") if not NOT_PAGES & set(p.relative_to(DOCS_TREE).parts)
)
#: Part 2, moved here by WP-1986.
THEORY_DIR = DOCS_TREE / "theory"

# Everything on a built page that is *not* prose: a `$` inside a code block or
# a script is not a rendering failure, and MathJax's own delimiters are `\(…\)`.
MARKUP_WITHOUT_PROSE = re.compile(
    r"<(script|style|pre)\b[^>]*>.*?</\1\s*>|<code\b[^>]*>.*?</code\s*>", re.S | re.I
)

# The landing page is copied into the build verbatim through `html_extra_path`
# (WP-1331), so the output tree holds pages Sphinx never rendered and whose
# markup is nobody's MyST.  They are not this suite's to police, and one of them
# writes a shell prompt as `<span class="ps">$</span>pip install rietx` — prose
# by MARKUP_WITHOUT_PROSE's definition, and a false positive for the TeX guard.
# Derived from the directory conf.py actually copies, so the exclusion is exactly
# what was added and a new manual page stays covered.  Read when the guard runs,
# never at import: `tests/test_landing.py` *creates* `docs/landing/site` during
# the session, so a set frozen at collection time is empty on the checkout that
# had none — and the landing page's `$` is then scanned as the manual's prose.
_LANDING_SITE = MANUAL_DIR.parent / "landing" / "site"


def _copied_in() -> set[str]:
    if not _LANDING_SITE.is_dir():
        return set()
    return {p.relative_to(_LANDING_SITE).as_posix() for p in _LANDING_SITE.rglob("*.html")}

CITE_ROLE = re.compile(r"\{cite\}`([^`]+)`")
#: Each displayed equation's source line, as `{source}` spells it (WP-1408).
#: The role resolves the name to a repository link at build time, so `-W`
#: already fails on one that does not import; these tests keep naming the
#: symbol in the failure and keep the coverage rule that every labelled
#: equation sits beside one.  Leading and trailing whitespace is allowed: a
#: role indented inside a directive, or a line with a stray trailing space, is
#: a source line the reader sees, and anchoring hard would make it invisible to
#: both guards below rather than making it illegal.
SOURCE_LINE = re.compile(r"^[ \t]*\{source\}`([A-Za-z_][\w.]*)`[ \t]*$", re.MULTILINE)
BIB_KEY = re.compile(r"^@\w+\{([^,\s]+)\s*,", re.MULTILINE)


def _cited_keys() -> set[str]:
    """Both trees cite from the one `references.bib` (`docs/sphinx_shared.py`)."""
    keys: set[str] = set()
    for page in CHAPTERS + DOCS_PAGES:
        for role in CITE_ROLE.findall(page.read_text(encoding="utf-8")):
            keys.update(k.strip() for k in role.split(","))
    return keys


@pytest.fixture(scope="session")
def built_manual(tmp_path_factory):
    """One `-W` build, shared by every test that reads its output.

    Session-scoped, and its consumers carry the matching `xdist_group` mark:
    without it a second worker rebuilds the whole tree and the sharing costs
    more than it saved (tests/CLAUDE.md).  Returns the output directory and the
    completed process, so the build's own failure is reported by the test named
    for it rather than as a fixture error.
    """
    return _build(MANUAL_DIR, tmp_path_factory.mktemp("manual") / "html")


@pytest.fixture(scope="session")
def built_docs_tree(tmp_path_factory):
    """The new tree's `-W` build, on the old tree's worker: a few seconds."""
    return _build(DOCS_TREE, tmp_path_factory.mktemp("docs-tree") / "html")


def _build(source: Path, out: Path):
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
         str(source), str(out)],
        capture_output=True, text=True, timeout=300,
    )
    return out, result


#: Each built-HTML guard below reads both trees.
BOTH_BUILDS = pytest.mark.parametrize("build", ["built_manual", "built_docs_tree"])


def _stray_in_prose(build: str, request, pattern: str) -> list[str]:
    """Each match of `pattern` in the rendered prose of a build's own pages.

    The old tree's landing page is copied in and skipped (`_copied_in`); the new
    tree copies nothing in, and its own `index.html` shares the landing page's
    name.  `_static/` is skipped in both, being the theme's assets:
    pydata-sphinx-theme ships a Jinja template there, `webpack-macros.html`,
    that no page renders.
    """
    out, result = request.getfixturevalue(build)
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    copied_in = _copied_in() if build == "built_manual" else set()
    stray: list[str] = []
    for page in sorted(out.rglob("*.html")):
        rel = page.relative_to(out)
        if rel.as_posix() in copied_in or rel.parts[0] == "_static":
            continue
        text = MARKUP_WITHOUT_PROSE.sub("", page.read_text(encoding="utf-8"))
        for match in re.finditer(pattern, text, re.S):
            stray.append(f"{rel.as_posix()}: …{match.group(0).strip()}…")
    return stray


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_manual_builds_warning_free(build, request):
    """sphinx-build -W: warnings (incl. undefined substitutions, missing
    citations, broken eq refs) are errors."""
    _, result = request.getfixturevalue(build)
    assert result.returncode == 0, f"sphinx-build -W failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_no_unrendered_math_survives_the_build(build, request):
    """No `$` reaches the rendered prose.  `-W` cannot see this class of bug:
    the page builds cleanly and prints the TeX.

    Both instances it was written for were live in the shipped HTML.  A
    continuation line beginning `- ` inside inline math is read as a list
    bullet, which dropped the delimiters *and* opened a spurious `<ul>` in
    `forward-model.md`; and five `references.bib` titles carried raw TeX
    (`Al$_2$O$_3$`, `$F_N$`, …) that the bibliography renders verbatim on every
    page that cites them.  Multi-line inline math is otherwise fine — nineteen
    other spans in Part 2 render correctly — so the rule is about the delimiters
    surviving, not about reflowing every equation onto one line.
    """
    stray = _stray_in_prose(build, request, r".{0,60}\$.{0,60}")
    assert not stray, "unrendered TeX in the built prose:\n" + "\n".join(stray[:10])


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_no_unrendered_markup_survives_the_build(build, request):
    """No backtick reaches the rendered prose.  The `$` guard above, one
    delimiter over, and the same blind spot: the page builds clean and prints
    the markup.

    Every backtick in a MyST source opens a code span or a role, and both
    render as an element `MARKUP_WITHOUT_PROSE` strips, so a backtick left in
    the prose is a construct that did not close.  Both instances this was
    written for were live in the shipped HTML (WP-1409).

    `using/indexing.md`'s "Further reading" had lost the ``{doc}`` prefix and
    the opening backtick off a role, so the page printed ``the [agent skill
    <skill>`,`` as text, with `<skill>` swallowed as an HTML tag.  And the
    agent skill's `references/abstention.md` wrote ``scale × |F|² × profile``
    as a code span **inside a Markdown table cell**, where the first `|` ends
    the cell: the span never closed and the backticks rendered literally.  In a
    table the pipes are escaped and the span dropped, which is what the manual's
    own tables already do (`\\|F\\|²`).
    """
    stray = _stray_in_prose(build, request, r".{0,60}`.{0,60}")
    assert not stray, (
        "a code span or role did not close, and its backtick is in the built "
        "prose:\n" + "\n".join(stray[:10])
    )


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_no_unsubstituted_substitution_survives_the_build(build, request):
    """No `{{ NAME }}` reaches the rendered page.  The guard above, one
    delimiter over, and the same blind spot: `-W` sees nothing.

    A MyST substitution is expanded in prose and **not** inside a `{math}`
    directive, so a constant written into an equation reaches MathJax as its
    own name and is typeset as a product of italic letters.  Both instances
    this was written for were live in the shipped HTML — `profiles.md`'s
    strain cap printed `f = STRAINCAPRANGEFRACTION` and its size cap
    `L_min = SIZECAPMINSIZENM nm` (WP-1408) — and neither is a build warning,
    because the substitution is *defined*; it is simply never reached.

    The fix for a new one is never to define the constant somewhere else: keep
    the symbol in the equation and state its value in the prose beside it,
    which is where `conf.py`'s injection works.
    """
    stray = _stray_in_prose(build, request, r".{0,60}\{\{.{0,60}")
    assert not stray, (
        "a MyST substitution reached the page unexpanded (a `{{ NAME }}` inside "
        "a {math} directive is the usual cause):\n" + "\n".join(stray[:10])
    )


#: One `<a class="sidebar-brand" href="…">` on a built page.
SIDEBAR_BRAND = re.compile(r'<a class="sidebar-brand"[^>]*\shref="([^"]*)"')

#: The release line beneath it, which is the way back to the manual's own
#: front page.  The href is relative, so it is `../manual.html` a directory
#: down and `#` on the front page itself, which is sphinx's `pathto` answering
#: for the current document.
SIDEBAR_RELEASE = re.compile(r'<a class="sidebar-release"[^>]*\shref="([^"]*)"')
#: Every drawn shape in an SVG: the `d` of a path, and a rect's four corners.
SVG_SHAPES = re.compile(r'<(?:path\s+d|rect\s+x)="[^"]*"[^>]*>')


@pytest.mark.xdist_group("manual-build")
def test_the_brand_mark_is_the_favicon(built_manual):
    """The inlined mark and `_static/favicon.svg` draw the same thing.

    The mark in `_templates/sidebar/brand.html` is inline SVG, which is a copy
    of the favicon's geometry, and a copy is exactly what this repository does
    not leave unpinned.  It is inline for a measured reason: worn as a CSS
    `mask-image` the same file renders over http and **silently disappears**
    from a local `file://` build, because chromium treats a `file://` mask
    source as cross-origin.  A reviewer opening `_build/html/` would have seen
    no mark at all.

    So the duplicate stays and the file stays its authority.  Compared on the
    drawn shapes rather than on the bytes, because the two documents legitimately
    differ everywhere else: the favicon carries a `<style>` with the two literal
    hexes, which is the one place they have to be literal, and the template
    takes its fill from `--color-rietx-ink`.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    template = (MANUAL_DIR / "_templates" / "sidebar" / "brand.html").read_text(encoding="utf-8")
    favicon = (MANUAL_DIR / "_static" / "favicon.svg").read_text(encoding="utf-8")
    inlined = SVG_SHAPES.findall(template)
    assert inlined, "no drawn shape in the brand template — has the mark moved?"
    assert inlined == SVG_SHAPES.findall(favicon), (
        "the brand's inline mark and _static/favicon.svg have drifted.  The "
        "favicon is the authority: copy its shapes into "
        "docs/manual/_templates/sidebar/brand.html.\n"
        f"  template: {inlined}\n  favicon:  {SVG_SHAPES.findall(favicon)}"
    )
    # and the copy is what the page actually carries
    page = (out / "manual.html").read_text(encoding="utf-8")
    for shape in inlined:
        assert shape in page, f"the built page does not draw {shape}"


@pytest.mark.xdist_group("manual-build")
def test_the_brand_links_to_the_landing_page(built_manual):
    """Every page's brand goes to the site root and its release line to the manual.

    Furo writes `href="{{ pathto(master_doc) }}"` in its own
    `sidebar/brand.html` and offers no theme option that reaches it, so
    `docs/manual/_templates/sidebar/brand.html` is a fork of that file
    (WP-1411).  A fork is exactly the thing that rots quietly: furo reshapes
    its template in some later release, sphinx renders the new one, the build
    is green, and the manual silently becomes a dead end again — which is what
    it was before this, with no page under `docs/manual/` linking to the site
    root at all.

    So the assertion is on the *built* page rather than on the template, and it
    runs over all of them rather than over one: the brand is in the sidebar, so
    a page that lost it lost it alone.  The mark and the wordmark come with it
    because the same upgrade would drop those too, and a link with no brand on
    it is not what this WP shipped.

    The release line underneath is the other half of the same fork: `root_doc`
    is in no toctree, so furo's sidebar never lists the manual's front page and
    that line is the only link to it on any chapter.
    """
    from rietx._about import DIST_NAME, DOCS_URL

    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    copied_in = _copied_in()
    pages = [p for p in sorted(out.rglob("*.html"))
             if p.relative_to(out).as_posix() not in copied_in]
    assert pages, "the build wrote no pages of its own"

    wrong: list[str] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        hrefs = SIDEBAR_BRAND.findall(text)
        if hrefs != [DOCS_URL]:
            wrong.append(f"{page.name}: brand href {hrefs} (want [{DOCS_URL!r}])")
        elif 'class="rietx-mark"' not in text:
            wrong.append(f"{page.name}: the brand carries no mark")
        elif f'<span class="sidebar-brand-text">{DIST_NAME}</span>' not in text:
            wrong.append(f"{page.name}: the brand carries no wordmark")
        else:
            depth = len(page.relative_to(out).parts) - 1
            want = ["#"] if page == out / "manual.html" else ["../" * depth + "manual.html"]
            if SIDEBAR_RELEASE.findall(text) != want:
                wrong.append(
                    f"{page.name}: release line {SIDEBAR_RELEASE.findall(text)} (want {want})")
    assert not wrong, (
        f"{len(wrong)} of {len(pages)} built pages have the wrong brand — has furo's "
        f"sidebar/brand.html moved under the fork in docs/manual/_templates/?\n"
        + "\n".join(wrong[:10])
    )


# The tutorial notebooks (WP-1916).  `conf.py` copies them in at build by
# `build.py`'s own glob, so the set is read from there too: a sixth tutorial
# reaches these tests with no edit, and fails the index test until
# `using/quickstart.md` lists it.
_TUTORIALS = MANUAL_DIR.parent.parent / "examples" / "tutorials"


def _tutorial_notebooks() -> list[Path]:
    spec = importlib.util.spec_from_file_location("_tutorials_build", _TUTORIALS / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return [s.with_suffix(".ipynb") for s in build.sources(_TUTORIALS)]


@pytest.mark.xdist_group("manual-build")
def test_the_build_copies_exactly_the_committed_tutorials(built_manual):
    """`using/tutorials/` holds each committed notebook byte for byte, and nothing else.

    The directory is gitignored and rewritten by every build, so a copy left
    over from a renamed tutorial would render as a page nobody can edit.
    """
    _, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    notebooks = _tutorial_notebooks()
    assert len(notebooks) >= 5, f"found {len(notebooks)} tutorials under {_TUTORIALS}"
    copies = MANUAL_DIR / "using" / "tutorials"
    assert sorted(p.name for p in copies.glob("*.ipynb")) == [nb.name for nb in notebooks]
    for nb in notebooks:
        assert (copies / nb.name).read_bytes() == nb.read_bytes(), f"{nb.name} copy is stale"


@pytest.mark.xdist_group("manual-build")
def test_every_tutorial_renders_with_its_outputs_and_the_quickstart_links_it(built_manual):
    """Each notebook is a page carrying its committed outputs, reached from the quickstart.

    Execution is off at build, so a page shows exactly the outputs the
    notebook was committed with.  myst-nb draws each code cell that has
    outputs as one `cell_output` container, and the count is compared with the
    notebook's own: a build that dropped the outputs would still be green.
    """
    import json

    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    # The page body only: furo's sidebar links every toctree entry on every
    # page, so a link test over the whole file passes with the table row gone.
    index = (out / "using" / "quickstart.html").read_text(encoding="utf-8")
    index = index.split('<article role="main"', 1)[1].split("</article>", 1)[0]
    problems: list[str] = []
    for nb in _tutorial_notebooks():
        page = out / "using" / "tutorials" / f"{nb.stem}.html"
        if not page.is_file():
            problems.append(f"{nb.stem}: no page")
            continue
        cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
        want = sum(1 for c in cells if c["cell_type"] == "code" and c.get("outputs"))
        got = page.read_text(encoding="utf-8").count('class="cell_output')
        if got != want:
            problems.append(f"{nb.stem}: {got} rendered outputs, notebook has {want}")
        if f'href="tutorials/{nb.stem}.html"' not in index:
            problems.append(f"{nb.stem}: the quickstart does not link its page")
        if not re.search(rf'href="\.\./_downloads/[0-9a-f]+/{re.escape(nb.name)}"', index):
            problems.append(f"{nb.stem}: the quickstart offers no download")
    assert not problems, "\n".join(problems)


def test_the_tch_coefficients_in_print_are_the_ones_the_code_runs():
    """(3.6) and (3.7) print seven literals, and they have to be the code's.

    This is the case the manual's usual anti-divergence rule cannot cover. A
    constant is normally injected as a MyST substitution, which is not expanded
    inside a `{math}` directive (WP-1408), so a coefficient that belongs
    *inside* an equation has to be typed — and then nothing holds the two
    copies together. Reading them back out of the chapter is what does.
    """
    from rietx.model.profiles.pseudovoigt import _TCH_ETA, _TCH_GAMMA

    text = (THEORY_DIR / "profiles.md").read_text(encoding="utf-8")
    for label, expected in (("prof-tch-gamma", _TCH_GAMMA), ("prof-tch-eta", _TCH_ETA)):
        block = re.search(rf":label: {label}\n(.*?)^```", text, re.S | re.M)
        assert block, f"{label}: equation not found in profiles.md"
        # The sign is read too: `_TCH_ETA`'s middle coefficient is negative and
        # the chapter prints it as a subtraction, so comparing magnitudes would
        # let a sign flip in either copy through unseen.
        printed = [float(sign.replace("+", "") + digits)
                   for sign, digits in re.findall(r"([-+])?\s*(\d+\.\d{4,})", block.group(1))]
        assert printed == list(expected), (
            f"{label} prints {printed}, the code runs {list(expected)}")


def test_every_bib_entry_is_cited():
    """references.bib carries no dead weight: an uncited entry is either a
    chapter that lost its citation or an entry that should be pruned."""
    bib_keys = set(BIB_KEY.findall((MANUAL_DIR / "references.bib").read_text(encoding="utf-8")))
    assert bib_keys, "no bibliography entries parsed — regex or file moved?"
    uncited = bib_keys - _cited_keys()
    assert not uncited, f"bibliography entries never cited: {sorted(uncited)}"


def test_every_citation_has_a_bib_entry():
    """The -W build also catches this, but a direct diff names the key."""
    bib_keys = set(BIB_KEY.findall((MANUAL_DIR / "references.bib").read_text(encoding="utf-8")))
    missing = _cited_keys() - bib_keys
    assert not missing, f"citations with no bibliography entry: {sorted(missing)}"


#: One entry: `@kind{key,` down to a `}` alone at the start of a line.  The
#: closing brace is anchored with `$` rather than a literal newline, so the
#: last entry is still parsed on a file with no trailing newline — a regex
#: that needs the newline drops it silently, which is a bibliography entry
#: quietly exempt from both guards below.
BIB_ENTRY = re.compile(r"^@(\w+)\{([^,\s]+)\s*,\n(.*?)\n\}\s*$", re.MULTILINE | re.DOTALL)
BIB_FIELD = re.compile(r"^\s*(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$", re.MULTILINE | re.DOTALL)

#: The one article with no DOI, and why (references.bib § rule 2).  A list
#: rather than a count, so adding an entry without one has to say which.
NO_DOI = {"scherrer1918": "Göttinger Nachrichten 1918 predates the DOI register",
          "stark1995": "Computational Statistics 10 (1995) has no Crossref record "
                       "(queried 2026-10-10)"}


def _bib_entries() -> list[tuple[str, str, dict[str, str]]]:
    text = (MANUAL_DIR / "references.bib").read_text(encoding="utf-8")
    out = []
    for kind, key, body in BIB_ENTRY.findall(text):
        out.append((kind, key, dict(BIB_FIELD.findall(body))))
    assert out, "no bibliography entries parsed — regex or file moved?"
    return out


def _title_words(title: str) -> list[tuple[str, bool]]:
    """Every word of a title, each with whether `{...}` protects it.

    Depth is tracked so a word inside `{...}` is exempt, and the depth a word
    *started* at is what counts — reading it at the closing brace would call
    every protected word unprotected.

    A protected word stays **in** the list rather than being filtered out here,
    because the caller exempts the title's *first* word: dropping them would
    shift that exemption onto the second word of every title opening with a
    braced proper noun, and nine entries do (`{Rietveld} refinement …`).
    """
    words: list[tuple[str, bool]] = []
    depth, word, word_depth = 0, "", 0
    for char in title:
        if char.isalnum() or char in "-'’":
            if not word:
                word_depth = depth
            word += char
            continue
        if word:
            words.append((word, word_depth > 0))
            word = ""
        depth += (char == "{") - (char == "}")
    if word:
        words.append((word, word_depth > 0))
    return words


def test_no_bibliography_title_has_an_unbraced_interior_capital():
    """references.bib § rule 1, the one the reader sees when it is broken.

    `bibtex_default_style = "alpha"` sentence-cases a title, so a capital that
    is neither braced nor the first word is lowercased on every page that
    cites the entry. It rendered ten entries as "x-ray" and this package's own
    citation as "Rietx: python-api-first analysis and rietveld refinement"
    (WP-1408). The first word is exempt: the style capitalises it and leaves
    the rest of it alone.
    """
    offenders = []
    for _kind, key, fields in _bib_entries():
        title = fields.get("title")
        if not title:
            continue
        for word, protected in _title_words(title)[1:]:
            if not protected and any(c.isupper() for c in word):
                offenders.append(f"{key}: {word!r} in {title[:60]!r}")
    assert not offenders, (
        "a capital the bibliography style will lowercase — brace the word, or "
        "the whole title if it is a proper name in title case:\n"
        + "\n".join(offenders)
    )


def test_every_article_carries_its_doi_in_the_one_case_the_file_uses():
    """references.bib § rules 2 and 3: an article has a DOI, and it is lower
    case — the form every machine source returns, so the field matches the
    only thing that can check it."""
    entries = _bib_entries()
    missing, miscased = [], []
    for kind, key, fields in entries:
        doi = fields.get("doi")
        if kind == "article" and not doi and key not in NO_DOI:
            missing.append(key)
        if doi and doi != doi.lower():
            miscased.append(f"{key}: {doi}")
    assert not missing, (
        "article entries with no doi field — look it up on Crossref and verify "
        f"title, year, volume and first page, or declare it in NO_DOI: {missing}")
    assert not miscased, f"doi fields that are not lower case: {miscased}"
    stale = sorted(set(NO_DOI) - {key for _k, key, _f in entries})
    assert not stale, f"NO_DOI names entries that are gone: {stale}"


#: A citation label alpha built from one author, longer than the three letters
#: it normally takes.  `srd128`'s author is the braced corporate name `{NIST}`,
#: which pybtex keeps whole because the braces make it non-alphabetic.  A list
#: rather than a bound, so a second one has to say what it is.
LONG_SINGLE_AUTHOR_LABELS = {"srd128": "{NIST}, a braced corporate author"}

LABEL_TAIL = re.compile(r"^(.*?)(\d{2})([a-z]?)$")


def test_every_citation_label_abbreviates_its_authors():
    """references.bib § rule 5, read off the labels themselves.

    `alpha` builds a label by abbreviating each surname, and pybtex abbreviates
    a name part only where `str.isalpha()` holds for it. A LaTeX accent macro
    carries a backslash and braces, so the part is passed through whole and the
    label spells the surname out: nine entries rendered as [LouerLouer72],
    [Humlivcek82], [KvrivyG76] and their like among ninety-six that abbreviate
    (WP-1408). Write the accent in Unicode and the abbreviation works.

    The invariant is what the reader sees, so it is asserted on the rendered
    label: two or more authors give initials, which are upper case, and one
    author gives three letters.
    """
    pytest.importorskip("pybtex")
    from pybtex.database.input import bibtex
    from pybtex.plugin import find_plugin

    data = bibtex.Parser().parse_file(str(MANUAL_DIR / "references.bib"))
    style = find_plugin("pybtex.style.formatting", "alpha")()
    offenders = []
    for formatted in style.format_entries(data.entries.values()):
        entry = data.entries[formatted.key]
        people = entry.persons.get("author") or entry.persons.get("editor") or []
        match = LABEL_TAIL.match(formatted.label)
        if match is None:
            continue  # no year: the label is the entry key, not an abbreviation
        stem = match.group(1).replace("+", "")
        if len(people) > 1:
            if not stem.isupper():
                offenders.append(f"{formatted.key}: [{formatted.label}] is not initials")
        elif len(stem) > 3 and formatted.key not in LONG_SINGLE_AUTHOR_LABELS:
            offenders.append(f"{formatted.key}: [{formatted.label}] spells the surname out")
    assert not offenders, (
        "citation labels that do not abbreviate — an accented surname written "
        "as a LaTeX macro defeats pybtex's abbreviator, so write it in Unicode "
        "(references.bib § rule 5):\n" + "\n".join(offenders)
    )
    stale = sorted(set(LONG_SINGLE_AUTHOR_LABELS) - set(data.entries))
    assert not stale, f"LONG_SINGLE_AUTHOR_LABELS names entries that are gone: {stale}"


#: One rendered citation, tags stripped: `[Bergmann et al., 2004]`.
CITATION_SPAN = re.compile(r'<span class="bibtex-citation".*?</span>', re.S)
#: `et al.` ends in a period, so the character before the comma is not always
#: a letter.
YEAR_IN_CITATION = re.compile(r"[A-Za-z\u00c0-\u024f.]\s*,\s*(?:19|20)\d{2}[a-z]?")

#: The rule in `_static/custom.css` that hides the bibliography's own label.
#: Matched on the selector rather than the whole block, so reformatting the
#: stylesheet does not fail the test.
BIBLIO_LABEL_RULE = 'div.citation[role="doc-biblioentry"] > span.label'


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_every_citation_reads_as_author_and_year(build, request):
    """`conf.py` § bibtex: a citation names its author and year on the page.

    Three settings produce this and any one of them can be lost quietly, so
    the guard reads the built page rather than the config. `alpha` labels —
    [BLBSZ04] for a work cited once among 105 — carry no meaning the reader can
    use, and the bibliography sits on a different page from all but one
    citation, so decoding one costs a navigation (WP-1408 § G3).

    The separator is checked too. `BracketStyle.sep` defaults to a comma, which
    is also what separates an author from its year, so the fourteen citations
    naming more than one work rendered as a flat comma list of six fragments.
    A citation carrying N years must carry N-1 semicolons.
    """
    out, result = request.getfixturevalue(build)
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    not_author_year, bad_separator = [], []
    multi = 0
    for page in sorted(out.rglob("*.html")):
        for match in CITATION_SPAN.finditer(page.read_text(encoding="utf-8")):
            text = re.sub(r"<[^>]+>", "", match.group(0)).strip()
            years = YEAR_IN_CITATION.findall(text)
            if not years:
                not_author_year.append(f"{page.name}: {text}")
                continue
            if len(years) > 1:
                multi += 1
                if text.count("; ") != len(years) - 1:
                    bad_separator.append(f"{page.name}: {text}")
    assert not not_author_year, (
        "citations that do not name an author and a year — check "
        "`bibtex_reference_style` in conf.py:\n" + "\n".join(not_author_year[:10])
    )
    assert multi, "no citation names more than one work — the separator is untested"
    assert not bad_separator, (
        "works in one citation are not separated by a semicolon — check the "
        "registered BracketStyle in conf.py:\n" + "\n".join(bad_separator[:10])
    )


#: A rendered `{eq}` reference: a link into an equation, whose own text is the
#: number in round brackets.
EQUATION_REF = re.compile(r'<a[^>]*href="[^"]*#equation-[^"]*"[^>]*>\((\d+\.\d+)\)</a>')


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_no_reference_is_doubly_bracketed(build, request):
    """A reference brings its own brackets, so the prose must not add a second
    pair.

    `{eq}` renders `(1.4)` and a citation renders `[Rietveld, 1969]`, and
    writing either inside a bracket of the same kind prints `((1.4))` or
    `[[Rietveld, 1969]]`. Twenty-one sites across nine chapters wrapped an
    equation reference in parentheses of their own, reaching the shipped HTML
    as `((1.4))`, `((10.7))` and `((10.8), (10.9))` (WP-1408 § G4). Neither
    `-W` nor a prose read catches it, because the source reads `({eq}`x`)`,
    which looks like ordinary punctuation.

    Brackets of the *other* kind are left alone. `(via Scherrer, (6.3) in …)`
    is ordinary English and reads correctly.
    """
    out, result = request.getfixturevalue(build)
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    doubled, seen = [], 0
    for page in sorted(out.rglob("*.html")):
        if page.name in ("search.html", "genindex.html"):
            continue
        html_text = page.read_text(encoding="utf-8")
        for pattern, left, right in (
            (EQUATION_REF, "(", ")"),
            (CITATION_SPAN, "[", "]"),
        ):
            for match in pattern.finditer(html_text):
                rendered = re.sub(r"<[^>]+>", "", match.group(0)).strip()
                if not (rendered.startswith(left) and rendered.endswith(right)):
                    continue        # a citation style without brackets of its own
                seen += 1
                before = re.sub(r"<[^>]+>", "", html_text[max(0, match.start() - 60):match.start()])
                after = re.sub(r"<[^>]+>", "", html_text[match.end():match.end() + 60])
                if before.rstrip().endswith(left) or after.lstrip().startswith(right):
                    doubled.append(f"{page.name}: …{before.strip()[-45:]}{rendered}{after[:14]}…")
    assert seen, "no bracketed references found in the built manual — the patterns moved"
    assert not doubled, (
        "a reference sits inside a bracket of its own kind, so the page prints a "
        "doubled bracket — drop the prose brackets, the reference carries its "
        "own:\n" + "\n".join(doubled[:12])
    )


@pytest.mark.xdist_group("manual-build")
@BOTH_BUILDS
def test_the_bibliography_label_is_hidden_and_the_rule_reaches_all_of_them(build, request):
    """The other half of § G3, which no build warning can see.

    docutils gives every citation node a label and sphinxcontrib-bibtex
    documents that it cannot remove one, so the list would print [BL91a] beside
    a citation reading [Boultif and Louër, 1991]. `custom.css` hides it. The
    selector is only safe while every label on the site belongs to the
    bibliography, so that is asserted rather than assumed: a label appearing
    anywhere else would be hidden too, silently.
    """
    out, result = request.getfixturevalue(build)
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    css = (out / "_static" / "custom.css").read_text(encoding="utf-8")
    assert BIBLIO_LABEL_RULE in css, (
        f"the rule hiding the bibliography's own label is gone from custom.css: {BIBLIO_LABEL_RULE}"
    )
    labels = biblio_labels = 0
    for page in sorted(out.rglob("*.html")):
        text = page.read_text(encoding="utf-8")
        labels += text.count('<span class="label">')
        for entry in re.findall(r'<div class="citation"[^>]*role="doc-biblioentry".*?</div>', text, re.S):
            biblio_labels += entry.count('<span class="label">')
    assert labels, "no citation labels in the built site — the bibliography moved or vanished"
    assert labels == biblio_labels, (
        f"{labels - biblio_labels} label(s) outside the bibliography would be hidden by "
        f"`{BIBLIO_LABEL_RULE}` — narrow the selector"
    )


#: Part 2 — the theory chapters, the new tree's Theory tab since WP-1986, less
#: its generated bibliography.  The old tree's copies are one-line includes of
#: these.  Derived rather than listed, so a chapter added to Theory inherits
#: the guards below.
def _part_two() -> list[Path]:
    pages = [p for p in DOCS_PAGES if p.parent == THEORY_DIR and p.name != "references.md"]
    assert len(pages) > 5, "Part 2 chapters not found — has the tree moved?"
    return pages


#: Every chapter a person wrote, both parts.  ``_generated/`` is excluded
#: because neither file in it is the manual's prose to hold: the glossary body
#: is written from ``rietx.help`` by ``conf.py`` (and guarded by
#: ``tests/test_help.py``), and the skill body is the agent skill rendered
#: whole, which is a rulebook an agent cites and may compress
#: (``tests/test_skill.py``).
def _authored_chapters() -> list[Path]:
    pages = [p for p in CHAPTERS
             if "_generated" not in p.relative_to(MANUAL_DIR).parts]
    assert len(pages) > 20, "the manual's chapters are not where this expects"
    assert DOCS_PAGES, "the new tree's pages are not where this expects"
    return pages + DOCS_PAGES


#: A directive option (``:class:``, ``:alt:``, ``:language:``) and an ``:::``
#: admonition marker, distinguished from a MyST definition-list body (``: the
#: text``), which is prose and is kept.
_DIRECTIVE_OPTION = re.compile(r"^:(?::+|[a-z][a-z0-9-]*:)")

#: ``:::{admonition} A title`` — the marker is markup and the title after it is
#: prose a reader sees, so the two halves of the line part company here.  Without
#: this the option pattern above swallows the title with the marker.
_DIRECTIVE_MARKER = re.compile(r"^:{3,}\{[a-z][a-z0-9-]*\}\s*(.*)$")

#: The prose of a page: lines outside fenced blocks, with code spans stripped.
#: A token inside ``…`` is a field name or captured output and a fenced block is
#: TeX or a console transcript, so neither is this file's to police.
#:
#: An admonition's **body** is prose and was not covered until WP-1409: the
#: helper skipped a whole ``:::`` block, so Part 1's admonitions carried 17 em
#: dashes and 12 bold marks that the register guard below could not see.  Only
#: the markers and the option lines are dropped now, and a marker's own title
#: is kept, since it renders as the admonition's heading.  An HTML comment goes
#: too: ``<!-- api-doc: no-exec — … -->`` is a directive to `test_manual_api.py`
#: and renders nowhere, and Part 1 carries 66 em dashes inside them.  A comment
#: is tracked to its ``-->`` rather than by its first line alone, or a comment
#: written over two lines puts its second line back into the prose.
def _prose_lines(page: Path) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fence = None
    comment = False
    for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if comment:
            comment = "-->" not in stripped
            continue
        if fence is None and stripped.startswith("```"):
            fence = "```"
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith("<!--"):
            comment = "-->" not in stripped
            continue
        marker = _DIRECTIVE_MARKER.match(stripped)
        if marker:
            stripped = marker.group(1)
            if not stripped:
                continue
        elif _DIRECTIVE_OPTION.match(stripped):
            continue
        lines.append((number, re.sub(r"`[^`]*`", "", stripped)))
    return lines


#: Two marks of the maintainer register, both invisible to `-W` because both are
#: valid Markdown.  Each carries the fix, since a failure is an editing job.
REGISTER_MARKS = (
    ("\u2014", "an em dash: give the aside its own sentence, or use parentheses"),
    ("**", "bold: the heading carries the claim, and backticks cover identifiers"),
)


def test_the_manual_keeps_its_register():
    """The manual is prose someone reads to get work done, and reads as it.

    A rulebook may compress, and `CLAUDE.md` measures ~15 em dashes per 1000
    words with the register working.  A manual's budget is 0, and the failure
    this guard exists for is leakage: the rulebook sits in the same tree, gets
    read first, and its voice arrives in the manual by default. That is how all
    twelve Part 2 chapters came to measure 6-15 per 1000 and to carry 87 bold or
    italic maxims (WP-1408), and Part 1 to carry 363 em dashes and 400 bold
    marks over 73 699 words (WP-1409, `yue-prose`).

    Both parts since WP-1409, and the new tree in docs/docs/ since WP-1978.  Part 2 was already at zero when Part 1 was
    swept, so widening the page list and `_prose_lines`' zones cost Part 2 no
    edit — which is the evidence that the zones were a hole rather than an
    exemption.

    The two marks below are the mechanical half of that register, so they are
    the half a test can hold; the rest is `yue-prose`'s grep pass, run on the
    chapter you edited.  A page that genuinely needs bold (a UI label, a table
    header) changes this test and says why: Part 1 writes its GUI labels in
    backticks instead, which is what the majority of them already did.
    """
    offenders = []
    for page in _authored_chapters():
        for number, line in _prose_lines(page):
            for mark, fix in REGISTER_MARKS:
                if mark in line:
                    rel = page.relative_to(MANUAL_DIR.parent).as_posix()
                    offenders.append(f"{rel}:{number}: {fix}\n    {line.strip()[:70]}")
    assert not offenders, (
        "the manual carries the maintainer register:\n" + "\n".join(offenders)
    )


def test_part_two_sets_a_statistic_as_mathematics():
    """`Rwp` in plain text, four lines under an equation that defines
    $R_{wp}$, was the reader-visible half of this (WP-1408).

    The rule is stated in `manual.md` § How to read this manual and is a
    difference between the two parts, not a global ban: Part 1 writes Rwp and
    χ² as plain text, because that is the word on the GUI header and in a
    console line. So this guard covers Part 2 only, and it exempts code spans
    and fenced blocks, where the token is a field name or captured output.
    """
    offenders = []
    for page in _part_two():
        for number, line in _prose_lines(page):
            if "Rwp" in line:
                offenders.append(f"{page.name}:{number}: {line.strip()[:70]}")
    assert not offenders, (
        "Part 2 writes the statistic as mathematics — $R_{wp}$, "
        "$\\Delta R_{wp}$ — never as plain text:\n" + "\n".join(offenders)
    )


def test_every_source_symbol_imports():
    """Each equation's *Source:* line names a live module or attribute; a
    rename breaks this test rather than the reader's trust."""
    symbols: set[str] = set()
    for page in CHAPTERS + DOCS_PAGES:
        symbols.update(SOURCE_LINE.findall(page.read_text(encoding="utf-8")))
    assert symbols, "no {source} lines found — pattern or chapters moved?"
    for dotted in sorted(symbols):
        parts = dotted.split(".")
        obj = None
        for i in range(len(parts), 0, -1):
            try:
                obj = importlib.import_module(".".join(parts[:i]))
            except ImportError:
                continue
            for attr in parts[i:]:
                obj = getattr(obj, attr, None)
                assert obj is not None, f"{dotted}: no attribute {attr!r}"
            break
        assert obj is not None, f"{dotted}: not importable"


def test_no_chapter_still_writes_a_source_line_by_hand():
    """The old `*Source:* \\`name\\`` spelling is gone and stays gone.

    It is the one thing about the `{source}` role (WP-1408) that no other
    guard sees: a page that writes the line by hand renders it as plain text
    beside a hundred linked ones, the name resolves against nothing, and the
    coverage test above is satisfied by the page's *other* lines. Loud here
    rather than silent on the page.
    """
    offenders = []
    for page in CHAPTERS + DOCS_PAGES:
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("*Source:*"):
                offenders.append(f"{page.relative_to(MANUAL_DIR.parent).as_posix()}:{number}: "
                                 f"{line.strip()[:60]}")
    assert not offenders, (
        "write the source line as the `{source}` role, which resolves the name "
        "to a repository link at build time:\n" + "\n".join(offenders)
    )


def test_source_lines_cover_every_labelled_equation():
    """Every {math} directive with a :label: sits in a section that carries
    at least one `{source}` line — an equation with no named source is a
    transcription with no audit trail.  Every page of the new tree is held to
    it, not only its Theory tab (WP-1978)."""
    for page in CHAPTERS + DOCS_PAGES:
        text = page.read_text(encoding="utf-8")
        n_labels = len(re.findall(r"^:label:", text, re.MULTILINE))
        n_sources = len(SOURCE_LINE.findall(text))
        if n_labels:
            assert n_sources > 0, (f"{page.relative_to(MANUAL_DIR.parent).as_posix()}: "
                                   f"{n_labels} labelled equations, no {{source}} lines")


def test_the_hump_table_agrees_with_the_refinement_that_produced_it():
    """`using/data.md`'s background-peak evidence table, against the fixture.

    That section's headline is a comparison of measured Rwp values — one
    background peak against three more Chebyshev terms, at equal parameter cost
    — and the refinements behind it are `tests/test_acceptance_si640c.py`'s
    `cheb3`/`cheb3_peak`/`cheb6` fixtures, which assert the same numbers by
    running them.  This is the *other* half of that chain: the prose cannot say
    a different number from the one the slow test pins, which is what would
    otherwise happen when a solver change moves the fit and only the test is
    updated.

    It is here rather than in the acceptance module for a scheduling reason —
    this half is a file read and belongs in the fast selection, and the half
    that needs four fits does not.

    **Both prose copies, not one.**  The same table is transcribed twice — the
    Markdown table in `using/data.md` and the reST table in the
    :class:`~rietx.schemas.instrument.HumpComponent` docstring — and the second
    is the one that drifted last time (7dbd27c fixed the manual's claim and left
    the docstring stating the old one).  Both are checked against `MANUAL_RWP`
    here, so neither copy can say a number no refinement produced.
    """
    sys.path.insert(0, str(MANUAL_DIR.parent.parent / "tests"))
    manual_rwp = importlib.import_module("test_acceptance_si640c").MANUAL_RWP
    page = (MANUAL_DIR / "using" / "data.md").read_text(encoding="utf-8")

    # --- the Markdown table in using/data.md, keyed by row label ---
    rows = {
        "cheb3": "| Chebyshev, 3 terms |",
        "cheb3_peak": "| Chebyshev-3 + one hump |",
        "cheb6": "| Chebyshev, 6 terms |",
        "cheb6_peak": "| Chebyshev-6 + one hump |",
    }
    for key, prefix in rows.items():
        line = next((ln for ln in page.splitlines() if ln.startswith(prefix)),
                    None)
        assert line is not None, f"the {key} row is gone from data.md"
        cells = [c.strip() for c in line.strip("|").split("|")]
        # | background | terms | Rwp | GoF | Biso | HIGH_CORRELATION |
        assert float(cells[2]) == manual_rwp[key], (
            f"data.md's {key} row says Rwp {cells[2]}, the fixture that "
            f"produced it says {manual_rwp[key]}")

    # --- the reST table in the HumpComponent docstring, keyed by the `terms`
    # column (its two peak rows share the label "that **+ one peak**", so the
    # label cannot key them; the term count can) ---
    doc = importlib.import_module(
        "rietx.schemas.instrument").HumpComponent.__doc__
    lines = doc.splitlines()
    seps = [i for i, ln in enumerate(lines)
            if ln.strip() and set(ln.strip()) <= {"=", " "}]
    assert len(seps) >= 3, "the HumpComponent docstring table lost its rules"
    terms_to_key = {"3": "cheb3", "3 + 3": "cheb3_peak",
                    "6": "cheb6", "6 + 3": "cheb6_peak"}
    seen: set[str] = set()
    for ln in lines[seps[1] + 1:seps[-1]]:  # body rows, between the inner rules
        cols = re.split(r"\s{2,}", ln.strip())
        # background | terms | Rwp | Biso(Si)/Å² | HIGH_CORRELATION
        key = terms_to_key.get(cols[1]) if len(cols) >= 3 else None
        if key is None:
            continue
        assert float(cols[2]) == manual_rwp[key], (
            f"the HumpComponent docstring's {key} row says Rwp {cols[2]}, the "
            f"fixture that produced it says {manual_rwp[key]}")
        seen.add(key)
    assert seen == set(terms_to_key.values()), (
        f"the HumpComponent docstring table is missing rows: "
        f"{set(terms_to_key.values()) - seen}")


# ----------------------------------------------------------------------
# The new tree (WP-1978)
#
# The page contract holds on `docs/docs/` only.  The old chapters are exempt
# until WP-1986 retires them, since most of them were written before it and
# would fail it.  Each rule is a function of the text, so the tests that hold
# the tree to it are paired with tests that make it fail on purpose.
# ----------------------------------------------------------------------

#: A page longer than this is two pages (WP-1975 § F8).
PAGE_CHAR_CAP = 50_000

#: What a paragraph cannot begin with: a heading, a fence, a directive, a role,
#: an HTML tag, a table, a list, a quote or an image.
_NOT_PROSE = re.compile(r"^(#|```|:::|\{|<|\||[-*+] |\d+[.)] |>|!\[)")

#: A MyST target, `(label)=`, which sits above the heading it names.
_TARGET = re.compile(r"^\([\w.:-]+\)=$")

#: A back-reference: a section that leans on what came before it reads wrong to
#: anyone who arrived at it from a search or a link, which is most readers.
_BACK_REFERENCE = re.compile(
    r"\bas (?:\w+ )?(?:above|earlier|before|previously)\b"
    r"|\b(?:see|shown|described|mentioned|discussed|noted) (?:above|earlier|previously)\b"
    r"|\bthe above\b|\b(?:previous|last|preceding) (?:section|page|chapter)\b"
    r"|^recall\b",
    re.IGNORECASE,
)


def _sections(text: str) -> list[tuple[int, int, str]]:
    """(line, heading level, the paragraph that opens the section) per heading.

    The paragraph is "" when the section opens on something other than prose.
    Headings inside a fenced block are code, not structure.
    """
    lines = text.splitlines()
    sections: list[tuple[int, int, str]] = []
    fence = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if fence is None and stripped.startswith("```"):
            fence = stripped[: len(stripped) - len(stripped.lstrip("`"))]
            continue
        if fence is not None:
            if stripped.startswith(fence):
                fence = None
            continue
        heading = re.match(r"^(#{1,6}) \S", line)
        if not heading:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        paragraph: list[str] = []
        while j < len(lines) and lines[j].strip():
            if not paragraph and (_NOT_PROSE.match(lines[j].strip())
                                  or _TARGET.match(lines[j].strip())):
                break
            paragraph.append(lines[j].strip())
            j += 1
        sections.append((i + 1, len(heading.group(1)), " ".join(paragraph)))
    return sections


def _first_sentence(paragraph: str) -> str:
    return re.split(r"(?<=[.?!])\s", paragraph, maxsplit=1)[0]


def _contract_breaches(text: str) -> list[str]:
    """Every way a page's text breaks the page contract, as messages."""
    breaches = []
    if len(text) > PAGE_CHAR_CAP:
        breaches.append(f"{len(text)} characters, over the {PAGE_CHAR_CAP} cap: split it")
    sections = _sections(text)
    titles = [s for s in sections if s[1] == 1]
    if len(titles) != 1:
        breaches.append(f"{len(titles)} H1 headings: a page has exactly one title")
    else:
        line, _, paragraph = titles[0]
        # A full stop inside a code span (`rx.fit`) or a dotted name is not
        # the end of a sentence.
        if not re.search(r"[.?!](?:\s|$)", re.sub(r"`[^`]*`", "", paragraph)):
            breaches.append(f"line {line}: no answer sentence under the title. "
                            "Say what the page answers before anything else")
    for line, _, paragraph in sections:
        if _BACK_REFERENCE.search(_first_sentence(paragraph)):
            breaches.append(f"line {line}: the section opens on a back-reference "
                            f"({_first_sentence(paragraph)[:60]!r}). A reader may "
                            "arrive here first, so restate what it needs")
    return breaches


#: A committed page's include of a generated body (`docs/reference_pages.py`).
_GENERATED_INCLUDE = re.compile(r"^```\{include\} [./]*_generated/(\S+)\n```$", re.M)


def _reference_pages():
    spec = importlib.util.spec_from_file_location(
        "_reference_pages", MANUAL_DIR.parent / "reference_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _as_rendered(text: str, bodies: dict | None = None) -> str:
    """A page's source with each generated body it includes in place.

    The contract binds what a reader gets, so a page that is one include line
    is held to the size and sections of the body it pulls in.
    """
    if not _GENERATED_INCLUDE.search(text):
        return text
    bodies = _reference_pages().BODIES if bodies is None else bodies
    return _GENERATED_INCLUDE.sub(lambda m: bodies[m.group(1)](), text)


def test_the_contract_reads_a_generated_body_in_place():
    """A one-line include of an over-long body breaks the cap (WP-1981)."""
    page = "# Title\n\nAn answer.\n\n```{include} ../_generated/long.md\n```\n"
    assert _contract_breaches(page) == []
    rendered = _as_rendered(page, {"long.md": lambda: "A sentence. " * 5000})
    assert ["over the 50000 cap" in b for b in _contract_breaches(rendered)] == [True]


def test_every_page_of_the_new_tree_keeps_the_page_contract():
    """An answer sentence under the title, under 50 000 characters, and no
    section opening on "as above" (WP-1975 § F8), generated bodies included."""
    assert len(DOCS_PAGES) >= 7, "the new tree's pages are not where this expects"
    breaches = [f"{page.relative_to(DOCS_TREE).as_posix()}: {message}"
                for page in DOCS_PAGES
                for message in _contract_breaches(
                    _as_rendered(page.read_text(encoding="utf-8")))]
    assert not breaches, "the page contract:\n" + "\n".join(breaches)


@pytest.mark.parametrize("text, expected", [
    ("# Title\n\nThis page answers one question.\n", []),
    ("(target)=\n# Title\n\nThe answer.\n\n## Part\n\nMore.\n", []),
    ("# Title\n\n```{toctree}\na\n```\n", ["no answer sentence"]),
    ("# Title\n\n- a list, not an answer.\n", ["no answer sentence"]),
    ("# Title\n\nSee `rx.fit` on rietx.org\n", ["no answer sentence"]),
    ("# Title\n\nAn answer.\n\n# Second title\n\nAnother.\n", ["2 H1 headings"]),
    ("# Title\n\nAn answer.\n\n## Part\n\nAs described above, the cell moves.\n",
     ["back-reference"]),
    ("# Title\n\nAn answer.\n\n## Part\n\nThe above holds for a plate.\n", ["back-reference"]),
    ("# Title\n\nAn answer.\n\n## Part\n\nRecall that a plate is flat.\n", ["back-reference"]),
    ("# Title\n\nAn answer.\n\n## Part\n\nPeaks above 90° shift. As above, so below.\n", []),
    ("# Title\n\nAn answer.\n\n```text\n# not a heading\n```\n", []),
    ("# Title\n\n" + "A sentence. " * 5000, ["over the 50000 cap"]),
])
def test_the_page_contract_fails_what_it_should(text, expected):
    """Each rule, made to fail once, with the message that names it."""
    breaches = _contract_breaches(text)
    assert len(breaches) == len(expected), breaches
    for breach, fragment in zip(breaches, expected):
        assert fragment in breach, (fragment, breach)


#: A markdown link's target, `[text](target)`, outside an image.
_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")

#: `myst_heading_anchors` in `docs/docs/conf.py`: H1 to H3 get a slug.
HEADING_ANCHOR_DEPTH = 3


def _heading_slugs(source: Path) -> set[str]:
    """The MyST anchor of each heading on a page, as `myst_heading_anchors` makes it.

    A link may name a section by this slug or by its HTML id, and the two
    differ wherever a heading carries punctuation or a non-ASCII letter: MyST
    resolves `#size--strain-µr` to the section whose id is `size-strain-r`.
    Only headings down to the depth `conf.py` sets get one.
    """
    from mdit_py_plugins.anchors.index import slugify

    if not source.is_file():
        return set()
    lines = source.read_text(encoding="utf-8").splitlines()
    return {slugify(lines[line - 1].lstrip("#").strip())
            for line, level, _ in _sections("\n".join(lines))
            if level <= HEADING_ANCHOR_DEPTH}


#: A Part 2 chapter's old address on the site.  Concepts linked these until
#: WP-1986 moved Part 2 into the Theory tab, and the old pages stay up until
#: Part 1 retires, so a link to one would land and go stale in silence.
_OLD_THEORY_LINK = re.compile(re.escape(DOCS_URL) + r"/([\w-]+)\.html(?:#\S*)?$")

#: The tabs whose pages link Theory to back a physics claim (WP-1975 § F8).
LINKING_TABS = {"concepts", "guides", "switching"}


def _theory_link_failures(page: Path, text: str, out: Path) -> list[str]:
    """Each link from `page` into the Theory tab that the build did not write.

    The built page has to exist, and so does the section a fragment names, by
    its HTML id or by the MyST slug that resolves to one.  Read off the HTML,
    because that is what the reader's click lands on.  A link to a moved
    chapter's old address on the site fails too, naming the relative link.
    """
    failures = []
    # The tab's own index is not a moved chapter: `rietx.org/index.html` is the
    # landing page.
    moved = {p.stem for p in _part_two()} - {"index"}
    for target in _MD_LINK.findall(text):
        old = _OLD_THEORY_LINK.match(target)
        if old and old.group(1) in moved:
            failures.append(f"{target}: the chapter is in the Theory tab, so link "
                            f"../theory/{old.group(1)}.md")
            continue
        if "://" in target or target.startswith("#"):
            continue
        path, _, fragment = target.partition("#")
        source = (page.parent / path).resolve()
        try:
            rel = source.relative_to(DOCS_TREE.resolve())
        except ValueError:
            continue
        if not rel.parts or rel.parts[0] != "theory":
            continue
        built = out / rel.with_suffix(".html")
        if not built.is_file():
            failures.append(f"{target}: no page {rel.with_suffix('.html').as_posix()}")
        elif (fragment and f'id="{fragment}"' not in built.read_text(encoding="utf-8")
              and fragment not in _heading_slugs(source.with_suffix(".md"))):
            failures.append(f"{target}: {rel.with_suffix('.html').as_posix()} has no "
                            f"section #{fragment}")
    return failures


@pytest.mark.xdist_group("manual-build")
def test_every_theory_link_from_concepts_guides_and_switching_resolves(built_docs_tree):
    """A physics claim on a Concepts, Guides or Switching page links the Theory
    section that derives it, and the link has to land (WP-1975 § F8)."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    failures = [f"{page.relative_to(DOCS_TREE).as_posix()}: {failure}"
                for page in DOCS_PAGES
                if page.relative_to(DOCS_TREE).parts[0] in LINKING_TABS
                for failure in _theory_link_failures(page, page.read_text(encoding="utf-8"), out)]
    assert not failures, "links into the Theory tab that land nowhere:\n" + "\n".join(failures)


@pytest.mark.xdist_group("manual-build")
def test_the_theory_link_check_fails_what_it_should(built_docs_tree):
    """The check above, made to fail on a missing page, a missing section and
    a moved chapter's old address."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    page = DOCS_TREE / "concepts" / "index.md"
    text = ("[ok](../theory/references.md) [ok](../theory/index.md#theory) "
            "[ok](../theory/background.md#explicit-humps) "
            "[gone](../theory/no-such-page.md) [gone](../theory/index.md#no-such-section) "
            "[gone](../theory/background.md#no-such-hump) "
            "[elsewhere](../reference/index.md) [web](https://example.org/theory/x.md) "
            "[root](../) "
            f"[moved]({DOCS_URL}/background.html#explicit-humps) "
            f"[part one]({DOCS_URL}/using/files.html) "
            f"[landing]({DOCS_URL}/index.html) "
            f"[skill]({DOCS_URL}/skill/rietx/SKILL.md)")
    failures = _theory_link_failures(page, text, out)
    expected = ("no page theory/no-such-page.html", "no section #no-such-section",
                "no section #no-such-hump", "link ../theory/background.md")
    assert len(failures) == len(expected), failures
    for failure, words in zip(failures, expected):
        assert words in failure, failures


def test_a_heading_slug_is_read_the_way_myst_makes_it(tmp_path):
    """A slug and an HTML id part company on punctuation and non-ASCII letters."""
    page = tmp_path / "page.md"
    page.write_text("# Size & strain µR\n\nText.\n\n#### Too deep\n\nMore.\n\n"
                    "```text\n# a comment\n```\n",
                    encoding="utf-8")
    assert _heading_slugs(page) == {"size--strain-µr"}


#: The front page's audience cards, in the order WP-1975 § F8 set.
FRONT_CARDS = ("New to rietx", "Coming from another code", "Supervising an agent")
TABS = ("Start", "Guides", "Concepts", "Reference", "Theory", "Switching")


@pytest.mark.xdist_group("manual-build")
def test_the_front_page_offers_three_audiences_and_six_tabs(built_docs_tree):
    """The cards in their order, and every tab in the header rather than
    folded into a "More" menu."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    html = (out / "index.html").read_text(encoding="utf-8")
    cards = re.findall(r'class="sd-card-title[^"]*"[^>]*>\s*(.*?)\s*<', html, re.S)
    assert tuple(cards) == FRONT_CARDS, cards
    header = html.split('class="bd-header', 1)[1].split("</header>", 1)[0]
    tabs = re.findall(r'class="nav-link nav-internal"[^>]*>\s*(.*?)\s*</a>', header, re.S)
    assert tuple(dict.fromkeys(tabs)) == TABS, tabs


# ----------------------------------------------------------------------
# The markdown twin and llms.txt (WP-1980)
#
# The HTML build writes `page.html.md` beside each page and `llms.txt` and
# `llms-full.txt` at its root (`docs/markdown_twin.py`).  The twin is what an
# agent reads, so the page contract binds it as it binds the source.
# ----------------------------------------------------------------------

#: What MyST leaves in a page that no markdown reader renders: a role, a
#: colon fence, a directive fence and an unexpanded substitution.
_MYST_RESIDUE = re.compile(r"\{[a-z][\w:-]*\}`|^ *:{3,}|^ *`{3,}\{|\{\{", re.M)
#: A fenced block whose info string is a language, which may hold anything.
_CODE_FENCE = re.compile(r"^( *`{3,})(?!\{)[^\n]*\n.*?^\1 *$", re.M | re.S)


def _myst_residue(twin: str) -> list[str]:
    # A code span goes too, but not a role's argument, which is one as well.
    prose = re.sub(r"(?<!\})`[^`\n]+`", "", _CODE_FENCE.sub("", twin))
    return [m.group(0) for m in _MYST_RESIDUE.finditer(prose)]


def _twins(out: Path) -> dict[str, str]:
    return {p.relative_to(out).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted(out.rglob("*.html.md"))}


@pytest.mark.xdist_group("manual-build")
def test_every_page_has_a_twin_that_keeps_the_contract(built_docs_tree):
    """One twin per page, with no MyST left in it, its title and answer
    sentence, and under the 50 000-character cap."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    twins = _twins(out)
    pages = {page.relative_to(DOCS_TREE).with_suffix(".html.md").as_posix() for page in DOCS_PAGES}
    assert set(twins) == pages, set(twins) ^ pages
    breaches = [f"{path}: {message}" for path, twin in twins.items()
                for message in _contract_breaches(twin)
                + [f"MyST left in it: {r!r}" for r in _myst_residue(twin)]]
    assert not breaches, "twins that break the page contract:\n" + "\n".join(breaches)


@pytest.mark.parametrize("twin, expected", [
    ("# T\n\nAn answer.\n\n```python\nf'{{x}}'\n```\n", []),
    ("# T\n\nAn answer with `{{ inline }}` code.\n", []),
    ("# T\n\nSee {eq}`one`.\n", ["{eq}`"]),
    ("# T\n\nAn answer.\n\n:::{note}\nx\n:::\n", [":::", ":::"]),
    ("# T\n\nAn answer.\n\n```{math}\nx\n```\n", ["```{"]),
    ("# T\n\nIt is {{ VALUE }} wide.\n", ["{{"]),
])
def test_the_residue_check_fails_what_it_should(twin, expected):
    assert _myst_residue(twin) == expected


@pytest.mark.xdist_group("manual-build")
def test_llms_txt_links_every_twin_once(built_docs_tree):
    """The llms.txt proposal's shape: the project, the front page's answer
    sentence as the summary, one section per tab, and one line per twin.
    `llms-full.txt` holds every twin."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    text = (out / "llms.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    front = _sections((DOCS_TREE / "index.md").read_text(encoding="utf-8"))[0][2]
    from rietx._about import DIST_NAME
    assert lines[:3] == [f"# {DIST_NAME}", "", f"> {_first_sentence(front)}"]
    assert [line[3:] for line in lines if line.startswith("## ")] == list(TABS)
    twins = _twins(out)
    links = re.findall(r"^- \[[^\]]+\]\(([^)]+)\): \S", text, re.M)
    assert sorted(links) == sorted(set(twins) - {"index.html.md"})
    full = (out / "llms-full.txt").read_text(encoding="utf-8")
    assert [path for path, twin in twins.items() if twin.splitlines()[0] not in full] == []


#: One page holding each node type the old tree uses and the new one does not
#: yet (WP-1986 brings them), so the twin is ready before they arrive.
_COVERAGE_PAGE = """\
# Coverage

The page holds one of each node type.

```{note}
The body of a note.
```

:::{admonition} A Title as Written
A titled admonition.
:::

```{math}
:label: eq-one
y = x^2
```

Equation {eq}`eq-one` cites {cite}`%(key)s`.

```{image} pic-light.png
:class: only-light
:alt: the light figure
```

```{image} pic-dark.png
:class: only-dark
:alt: the dark figure
```

::::{tab-set}
:::{tab-item} First tab
First tab text.
:::
:::{tab-item} Second tab
Second tab text.
:::
::::

:::{dropdown} The folded part
Folded text.
:::

| a | b |
|---|---|
| x \\| y | z |

```{mermaid}
flowchart LR
  A --> B
```

```{bibliography}
```
"""


def test_the_twin_writes_every_node_type_the_old_tree_uses(tmp_path):
    """A note and a titled admonition as labelled quotes, the math, the light
    half of a figure pair, every tab, the dropdown, an escaped table cell, a
    mermaid fence and the bibliography, with `-W` holding no node unknown."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.md").write_text(_COVERAGE_PAGE % {"key": _bib_entries()[0][1]},
                                  encoding="utf-8")
    for name in ("pic-light.png", "pic-dark.png"):
        (src / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    (src / "conf.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(MANUAL_DIR.parent)!r})\n"
        "extensions = ['myst_parser', 'sphinx_design', 'sphinxcontrib.bibtex',\n"
        "              'sphinxcontrib.mermaid', 'markdown_twin']\n"
        "myst_enable_extensions = ['colon_fence', 'dollarmath', 'amsmath']\n"
        f"bibtex_bibfiles = [{str(MANUAL_DIR / 'references.bib')!r}]\n"
        "project = 'coverage'\n",
        encoding="utf-8")
    out = tmp_path / "html"
    result = subprocess.run([sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
                             str(src), str(out)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    twin = (out / "index.html.md").read_text(encoding="utf-8")
    for fragment in ("> **Note**\n> \n> The body of a note.",
                     "> **A Title as Written**\n> \n> A titled admonition.",
                     "$$", "y = x^2",
                     "![the light figure](_images/pic-light.png)",
                     "**First tab**", "Second tab text.",
                     "**The folded part**\n\nFolded text.",
                     "| x \\| y | z |",
                     "```mermaid\nflowchart LR"):
        assert fragment in twin, fragment
    assert "dark figure" not in twin
    assert _myst_residue(twin) == []
    # The citation links its bibliography entry, which carries the label.
    anchor = re.search(r"\]\(#([\w-]+)\)", twin.split("cites", 1)[1])[1]
    entry = twin.split(f'<a id="{anchor}"></a>', 1)[1].lstrip()
    assert re.match(r"\*\*\[\w+\]\*\* \S.*1969", entry), entry
