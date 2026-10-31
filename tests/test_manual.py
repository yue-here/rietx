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
from tests import documentation

pytest.importorskip("sphinx")

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The manual (WP-1978), the one tree since WP-1986 retired the old one in
#: `docs/manual/`.  rglob, not glob: a doc tree's shape should not be set by a
#: test's glob, and the guards below are what a new page inherits by being
#: collected here.
DOCS_TREE = REPO_ROOT / "docs" / "docs"
#: The bibliography every page cites from (`docs/sphinx_shared.py`'s `BIBFILE`).
BIBFILE = DOCS_TREE / "references.bib"
#: Build outputs, never pages.  `_build/` is a local sphinx output directory,
#: and an rglob that walks it collects a stale copy of every page.
#: `_generated/` holds the Reference tab's bodies, which a committed page
#: includes (`docs/reference_pages.py`).
NOT_PAGES = {"_build", "_generated"}
#: Markdown only, so the tutorial notebooks under `start/tutorials/` are not
#: here, though each is a page of the tree.  A build copies them in from
#: `examples/tutorials/`, so a source checkout may have none, and each guard
#: reading these files reads markdown, where a notebook is JSON.  Their
#: markdown cells are the tutorial scripts' (WP-1545): their code runs in
#: `tests/test_tutorials.py`, and their names and register go unchecked here,
#: as `start/tutorials.md`'s guard note says.  Their built twins are held to
#: the page contract with every other page's
#: (`test_every_page_has_a_twin_that_keeps_the_contract`).
DOCS_PAGES = sorted(
    p for p in DOCS_TREE.rglob("*.md") if not NOT_PAGES & set(p.relative_to(DOCS_TREE).parts)
)
#: Part 2, the Theory tab since WP-1986.
THEORY_DIR = DOCS_TREE / "theory"

# Everything on a built page that is *not* prose: a `$` inside a code block or
# a script is not a rendering failure, and MathJax's own delimiters are `\(…\)`.
MARKUP_WITHOUT_PROSE = re.compile(
    r"<(script|style|pre)\b[^>]*>.*?</\1\s*>|<code\b[^>]*>.*?</code\s*>", re.S | re.I
)

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
    """Every key a page cites from `references.bib` (`docs/sphinx_shared.py`)."""
    keys: set[str] = set()
    for page in DOCS_PAGES:
        for role in CITE_ROLE.findall(page.read_text(encoding="utf-8")):
            keys.update(k.strip() for k in role.split(","))
    return keys


@pytest.fixture(scope="session")
def built_docs_tree(tmp_path_factory):
    """One `-W` build of the manual, shared by every test that reads its output.

    Session-scoped, and its consumers carry the matching `xdist_group` mark:
    without it a second worker rebuilds the whole tree and the sharing costs
    more than it saved (tests/CLAUDE.md).  Returns the output directory and the
    completed process, so the build's own failure is reported by the test named
    for it rather than as a fixture error.  It skips where
    `tests/documentation.py` says the documentation does not execute.
    """
    documentation.skip_here()
    return _build(DOCS_TREE, tmp_path_factory.mktemp("docs-tree") / "html")


def _build(source: Path, out: Path):
    result = subprocess.run(
        [sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
         str(source), str(out)],
        capture_output=True, text=True, timeout=300,
    )
    return out, result


def _stray_in_prose(built, pattern: str) -> list[str]:
    """Each match of `pattern` in the rendered prose of the build's pages.

    The build copies no page in from elsewhere, so every page is Sphinx's.
    `_static/` is skipped, being the theme's assets: pydata-sphinx-theme ships
    a Jinja template there, `webpack-macros.html`, that no page renders.
    """
    out, result = built
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    stray: list[str] = []
    for page in sorted(out.rglob("*.html")):
        rel = page.relative_to(out)
        if rel.parts[0] == "_static":
            continue
        text = MARKUP_WITHOUT_PROSE.sub("", page.read_text(encoding="utf-8"))
        for match in re.finditer(pattern, text, re.S):
            stray.append(f"{rel.as_posix()}: …{match.group(0).strip()}…")
    return stray


@pytest.mark.xdist_group("manual-build")
def test_manual_builds_warning_free(built_docs_tree):
    """sphinx-build -W: warnings (incl. undefined substitutions, missing
    citations, broken eq refs) are errors."""
    _, result = built_docs_tree
    assert result.returncode == 0, f"sphinx-build -W failed:\n{result.stdout}\n{result.stderr}"


@pytest.mark.xdist_group("manual-build")
def test_no_unrendered_math_survives_the_build(built_docs_tree):
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
    stray = _stray_in_prose(built_docs_tree, r".{0,60}\$.{0,60}")
    assert not stray, "unrendered TeX in the built prose:\n" + "\n".join(stray[:10])


@pytest.mark.xdist_group("manual-build")
def test_no_unrendered_markup_survives_the_build(built_docs_tree):
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
    stray = _stray_in_prose(built_docs_tree, r".{0,60}`.{0,60}")
    assert not stray, (
        "a code span or role did not close, and its backtick is in the built "
        "prose:\n" + "\n".join(stray[:10])
    )


@pytest.mark.xdist_group("manual-build")
def test_no_unsubstituted_substitution_survives_the_build(built_docs_tree):
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
    stray = _stray_in_prose(built_docs_tree, r".{0,60}\{\{.{0,60}")
    assert not stray, (
        "a MyST substitution reached the page unexpanded (a `{{ NAME }}` inside "
        "a {math} directive is the usual cause):\n" + "\n".join(stray[:10])
    )


#: Every drawn shape in an SVG: the `d` of a path, and a rect's four corners.
SVG_SHAPES = re.compile(r'<(?:path\s+d|rect\s+x)="[^"]*"[^>]*>')


# The tutorial notebooks (WP-1916).  `conf.py` copies them in at build by
# `build.py`'s own glob (`docs/sphinx_shared.py`), so the set is read from
# there too: a new tutorial reaches these tests with no edit, and fails the
# index test until the index page lists it.
_TUTORIALS = REPO_ROOT / "examples" / "tutorials"


def _tutorial_notebooks() -> list[Path]:
    spec = importlib.util.spec_from_file_location("_tutorials_build", _TUTORIALS / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return [s.with_suffix(".ipynb") for s in build.sources(_TUTORIALS)]


#: Where `conf.py` copies the notebooks, which is also their index page.
TUTORIAL_HOME = "start/tutorials"
#: Where the index page's body opens.  The body only, because the theme's
#: navigation links every toctree entry on every page, so a link test over the
#: whole file passes with the table row gone.
ARTICLE_BODY = '<article class="bd-article"'


@pytest.mark.xdist_group("manual-build")
def test_the_build_copies_exactly_the_committed_tutorials(built_docs_tree):
    """The copy directory holds each committed notebook byte for byte, and nothing else.

    The directory is gitignored and rewritten by every build, so a copy left
    over from a renamed tutorial would render as a page nobody can edit.
    """
    _, result = built_docs_tree
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    notebooks = _tutorial_notebooks()
    assert len(notebooks) >= 5, f"found {len(notebooks)} tutorials under {_TUTORIALS}"
    copies = DOCS_TREE / TUTORIAL_HOME
    assert sorted(p.name for p in copies.glob("*.ipynb")) == [nb.name for nb in notebooks]
    for nb in notebooks:
        assert (copies / nb.name).read_bytes() == nb.read_bytes(), f"{nb.name} copy is stale"


@pytest.mark.xdist_group("manual-build")
def test_every_anchor_a_tutorial_links_is_on_its_page(built_docs_tree):
    """A tutorial's `#anchor` into the manual names an id on that page of the build.

    `test_tutorials.py` checks the page against the Markdown sources, and that
    check cannot see an anchor: a heading's slug is generated, so only the
    output says what a link will find.  A renamed heading would otherwise
    leave the reader at the top of the page with every test green (WP-2040).
    """
    out, result = built_docs_tree
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    texts = {nb.with_suffix(".py").name: nb.with_suffix(".py").read_text(encoding="utf-8")
             for nb in _tutorial_notebooks()}
    assert any(_ANCHOR_LINK.search(text) for text in texts.values()), \
        "no tutorial links an anchor, so this test checks nothing"
    broken = _broken_anchors(texts, out)
    assert not broken, ("links whose anchor is no id on that page of the built manual:\n"
                        + "\n".join(broken))


#: A link into the published manual with an anchor, its page and anchor apart.
_ANCHOR_LINK = re.compile(re.escape(DOCS_URL)
                          + r"/docs/stable/([^\s#)>\]\"'`]+)#([^\s)>\]\"'`]+)")


def _broken_anchors(texts: dict[str, str], out: Path) -> list[str]:
    """Each `page#anchor` link in `texts` whose anchor is no id on that page under `out`."""
    ids: dict[str, set[str]] = {}
    broken = []
    for name, text in texts.items():
        for page, anchor in _ANCHOR_LINK.findall(text):
            if page not in ids:
                built = out / page
                ids[page] = (set(re.findall(r'id="([^"]+)"', built.read_text(encoding="utf-8")))
                             if built.is_file() else set())
            if anchor not in ids[page]:
                broken.append(f"{name}: {page}#{anchor}")
    return broken


def test_the_anchor_check_sees_a_missing_id_and_a_missing_page(tmp_path):
    """The guard can fail: a renamed heading and a page the build lacks are both reported."""
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference" / "result.html").write_text(
        '<section id="diagnostics"><h2>Diagnostics</h2></section>', encoding="utf-8")
    stable = f"{DOCS_URL}/docs/stable"
    text = (f"[ok]({stable}/reference/result.html#diagnostics) "
            f"[renamed]({stable}/reference/result.html#printing-a-result) "
            f"[gone]({stable}/reference/nowhere.html#x)")
    assert _broken_anchors({"t.py": text}, tmp_path) == [
        "t.py: reference/result.html#printing-a-result",
        "t.py: reference/nowhere.html#x"]


@pytest.mark.xdist_group("manual-build")
def test_every_tutorial_renders_with_its_outputs_and_the_index_links_it(built_docs_tree):
    """Each notebook is a page carrying its committed outputs, reached from its index page.

    Execution is off at build, so a page shows exactly the outputs the
    notebook was committed with.  myst-nb draws each code cell that has
    outputs as one `cell_output` container, and the count is compared with the
    notebook's own: a build that dropped the outputs would still be green.
    """
    import json

    out, result = built_docs_tree
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    index = (out / f"{TUTORIAL_HOME}.html").read_text(encoding="utf-8")
    index = index.split(ARTICLE_BODY, 1)[1].split("</article>", 1)[0]
    problems: list[str] = []
    for nb in _tutorial_notebooks():
        page = out / TUTORIAL_HOME / f"{nb.stem}.html"
        if not page.is_file():
            problems.append(f"{nb.stem}: no page")
            continue
        cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
        want = sum(1 for c in cells if c["cell_type"] == "code" and c.get("outputs"))
        got = page.read_text(encoding="utf-8").count('class="cell_output')
        if got != want:
            problems.append(f"{nb.stem}: {got} rendered outputs, notebook has {want}")
        if f'href="tutorials/{nb.stem}.html"' not in index:
            problems.append(f"{nb.stem}: {TUTORIAL_HOME}.html does not link its page")
        if not re.search(rf'href="\.\./_downloads/[0-9a-f]+/{re.escape(nb.name)}"', index):
            problems.append(f"{nb.stem}: {TUTORIAL_HOME}.html offers no download")
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
    bib_keys = set(BIB_KEY.findall(BIBFILE.read_text(encoding="utf-8")))
    assert bib_keys, "no bibliography entries parsed — regex or file moved?"
    uncited = bib_keys - _cited_keys()
    assert not uncited, f"bibliography entries never cited: {sorted(uncited)}"


def test_every_citation_has_a_bib_entry():
    """The -W build also catches this, but a direct diff names the key."""
    bib_keys = set(BIB_KEY.findall(BIBFILE.read_text(encoding="utf-8")))
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
    text = BIBFILE.read_text(encoding="utf-8")
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
LONG_SINGLE_AUTHOR_LABELS = {"srd128": "{NIST}, a braced corporate author",
                             "bipm2019": "{BIPM}, a braced corporate author"}

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

    data = bibtex.Parser().parse_file(str(BIBFILE))
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
def test_every_citation_reads_as_author_and_year(built_docs_tree):
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
    out, result = built_docs_tree
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
def test_no_reference_is_doubly_bracketed(built_docs_tree):
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
    out, result = built_docs_tree
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
def test_the_bibliography_label_is_hidden_and_the_rule_reaches_all_of_them(built_docs_tree):
    """The other half of § G3, which no build warning can see.

    docutils gives every citation node a label and sphinxcontrib-bibtex
    documents that it cannot remove one, so the list would print [BL91a] beside
    a citation reading [Boultif and Louër, 1991]. `custom.css` hides it. The
    selector is only safe while every label on the site belongs to the
    bibliography, so that is asserted rather than assumed: a label appearing
    anywhere else would be hidden too, silently.
    """
    out, result = built_docs_tree
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


#: Part 2 — the theory chapters, the Theory tab since WP-1986, less its
#: generated bibliography.  Derived rather than listed, so a chapter added to
#: Theory inherits the guards below.
def _part_two() -> list[Path]:
    pages = [p for p in DOCS_PAGES if p.parent == THEORY_DIR and p.name != "references.md"]
    assert len(pages) > 5, "Part 2 chapters not found — has the tree moved?"
    return pages


#: Every page a person wrote.  ``_generated/`` is already out of
#: ``DOCS_PAGES``: its bodies are written from the package by
#: ``docs/reference_pages.py``, so their prose is the package's strings, held
#: by the tests of the code that owns each one (``tests/test_help.py`` for the
#: vocabularies).
def _authored_chapters() -> list[Path]:
    assert len(DOCS_PAGES) > 20, "the manual's pages are not where this expects"
    return DOCS_PAGES


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
                    rel = page.relative_to(DOCS_TREE.parent).as_posix()
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
    for page in DOCS_PAGES:
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
    for page in DOCS_PAGES:
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("*Source:*"):
                offenders.append(f"{page.relative_to(DOCS_TREE.parent).as_posix()}:{number}: "
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
    for page in DOCS_PAGES:
        text = page.read_text(encoding="utf-8")
        n_labels = len(re.findall(r"^:label:", text, re.MULTILINE))
        n_sources = len(SOURCE_LINE.findall(text))
        if n_labels:
            assert n_sources > 0, (f"{page.relative_to(DOCS_TREE.parent).as_posix()}: "
                                   f"{n_labels} labelled equations, no {{source}} lines")


def test_the_hump_table_agrees_with_the_refinement_that_produced_it():
    """`concepts/parameters.md`'s hump evidence table, against the fixture.

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
    Markdown table in `concepts/parameters.md` and the reST table in the
    :class:`~rietx.schemas.instrument.HumpComponent` docstring — and the second
    is the one that drifted last time (7dbd27c fixed the manual's claim and left
    the docstring stating the old one).  Both are checked against `MANUAL_RWP`
    here, so neither copy can say a number no refinement produced.
    """
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    manual_rwp = importlib.import_module("test_acceptance_si640c").MANUAL_RWP
    page = (DOCS_TREE / "concepts" / "parameters.md").read_text(encoding="utf-8")

    # --- the Markdown table in concepts/parameters.md, keyed by row label ---
    rows = {
        "cheb3": "| Chebyshev, 3 terms |",
        "cheb3_peak": "| Chebyshev, 3 terms, and one hump |",
        "cheb6": "| Chebyshev, 6 terms |",
        "cheb6_peak": "| Chebyshev, 6 terms, and one hump |",
    }
    for key, prefix in rows.items():
        line = next((ln for ln in page.splitlines() if ln.startswith(prefix)),
                    None)
        assert line is not None, f"the {key} row is gone from parameters.md"
        cells = [c.strip() for c in line.strip("|").split("|")]
        # | background | free background terms | Rwp | Biso |
        assert float(cells[2]) == manual_rwp[key], (
            f"parameters.md's {key} row says Rwp {cells[2]}, the fixture that "
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
# The page contract (WP-1978)
#
# Every page of `docs/docs/` keeps it.  Each rule is a function of the text,
# so the tests that hold the tree to it are paired with tests that make it
# fail on purpose.
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
        "_reference_pages", DOCS_TREE.parent / "reference_pages.py")
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
    # Its own id: pytest puts the id in PYTEST_CURRENT_TEST, and Windows refuses
    # an environment variable over 32 767 characters (WP-2043).
    pytest.param("# Title\n\n" + "A sentence. " * 5000, ["over the 50000 cap"],
                 id="over-the-cap"),
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
#: WP-1986 moved Part 2 into the Theory tab, and since the old tree retired
#: each is a redirect stub, so a link to one costs the reader a hop.
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


#: The manual's header brand, which goes to the site's home page (WP-2021).
HEADER_BRAND = re.compile(r'<a class="navbar-brand logo rietx-brand" href="([^"]*)"')
#: The site's source: the landing page's shell, its favicon and its colours.
LANDING_SRC = REPO_ROOT / "docs" / "landing" / "src"


#: The pages Sphinx writes for itself rather than from a source.
SPHINX_PAGES = {"genindex.html", "search.html"}


def _built_pages(out: Path) -> list[Path]:
    """Every page the build wrote.  `_static/` holds the theme's assets, one of them
    an HTML macro file no page renders."""
    pages = [p for p in sorted(out.rglob("*.html")) if p.relative_to(out).parts[0] != "_static"]
    assert pages, "the build wrote no pages"
    return pages


def test_the_site_draws_one_mark():
    """The favicon, the manual's header and the landing page's header draw one mark.

    `docs/landing/src/favicon.svg` is the site's one favicon and the mark's
    authority (WP-2021).  The two headers copy its geometry inline, because an
    `<img>` is its own document and cannot follow the theme toggle, so the copies
    are held to it: one mark, never redrawn.  Compared on the drawn shapes rather
    than the bytes, since the favicon carries a `<style>` and the headers take
    their fill from the page.  An SVG loaded as an icon reads no CSS variable, so
    the favicon spells its two fills, and they are `--accent` in `tokens.css`."""
    from tests.test_landing import site_tokens

    favicon = (LANDING_SRC / "favicon.svg").read_text(encoding="utf-8")
    shapes = SVG_SHAPES.findall(favicon)
    assert shapes, "no drawn shape in docs/landing/src/favicon.svg — has the mark moved?"
    # The mark is the 32-unit drawing; the theme button beside it draws on 24.
    def mark(path: Path) -> list[str]:
        drawing = re.search(r'<svg[^>]*viewBox="0 0 32 32".*?</svg>',
                            path.read_text(encoding="utf-8"), re.S)
        return SVG_SHAPES.findall(drawing.group(0)) if drawing else []
    for copy in (DOCS_TREE / "_templates" / "rietx-brand.html", LANDING_SRC / "shell.html"):
        where, inlined = copy.relative_to(REPO_ROOT).as_posix(), mark(copy)
        assert inlined == shapes, (
            f"{where} has drifted from docs/landing/src/favicon.svg, which is the "
            f"authority: copy its shapes.\n  copy:    {inlined}\n  favicon: {shapes}")
    fills = re.findall(r"fill:\s*(#[0-9a-fA-F]{6})", favicon)
    tokens = site_tokens()
    accent = [tokens["light"]["accent"], tokens["dark (pinned)"]["accent"]]
    assert fills == accent, f"the favicon's fills {fills} are not --accent {accent}"


def test_the_manual_spells_no_colour():
    """Only `tokens.css` spells a colour.  `custom.css` maps pydata's names onto the
    tokens, and a hex or an `rgb()` anywhere in the manual's own styles, scripts or
    templates is a second authority the dark theme and the landing page cannot see."""
    literal = re.compile(r"(?<![\w-])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![\w-])"
                         r"|\b(?:rgba?|hsla?)\(|\b(?:white|black)\b")
    files = [DOCS_TREE / "_static" / "custom.css", DOCS_TREE / "_static" / "rietx-theme.js",
             DOCS_TREE / "_static" / "fonts" / "fonts.css",
             *sorted((DOCS_TREE / "_templates").glob("*.html"))]
    found = [f"{f.relative_to(REPO_ROOT).as_posix()}:{n}: {line.strip()}"
             for f in files
             for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
             if literal.search(line)]
    assert not found, "a colour spelled outside docs/landing/src/tokens.css:\n" + "\n".join(found)


def test_the_theme_control_is_the_landing_pages():
    """The manual's theme button draws the landing page's two glyphs, so the control
    a reader learned on one page is the control on the other."""
    def glyphs(text: str) -> list[str]:
        return re.findall(r'<svg class="only-(?:light|dark)".*?</svg>', text, re.S)
    ours = glyphs((DOCS_TREE / "_templates" / "rietx-theme.html").read_text(encoding="utf-8"))
    theirs = glyphs((LANDING_SRC / "shell.html").read_text(encoding="utf-8"))
    assert len(ours) == 2 and ours == theirs, (ours, theirs)


#: Each tab whose page titles share a prefix, and the prefix (WP-2021 decision 6).
TITLE_PREFIXES = {"concepts": "About ", "guides": "How to "}
#: One entry of a toctree with an explicit title: `Label <doc>`.
TOCTREE_ENTRY = re.compile(r"^(?P<label>.+?) <(?P<doc>[^>]+)>$")


@pytest.mark.parametrize("tab", sorted(TITLE_PREFIXES))
def test_a_tabs_menu_names_each_page_without_the_prefix_its_tab_says(tab):
    """In Concepts and Guides the sidebar drops "About" and "How to", which the tab
    already says, and the page keeps them.

    A toctree entry's explicit title changes the menu alone: the H1, the `<title>`,
    the previous and next links and `llms.txt` keep the page's own.  The title keeps
    its prefix because 66 links quote it as prose ("[About the report] describes
    its three layers"), where the bare noun would read as the thing, not the page.
    So the label is derived, never authored: the title less its prefix, capitalised."""
    prefix = TITLE_PREFIXES[tab]
    index = (DOCS_TREE / tab / "index.md").read_text(encoding="utf-8")
    block = re.search(r"```\{toctree\}\n(?::[^\n]*\n)*\n(.*?)\n```", index, re.S)
    assert block, f"{tab}/index.md has no toctree"
    wrong: list[str] = []
    for entry in block.group(1).splitlines():
        match = TOCTREE_ENTRY.match(entry)
        if not match:
            wrong.append(f"{entry!r}: no explicit title, so the menu shows the prefix")
            continue
        page = (DOCS_TREE / tab / f"{match['doc']}.md").read_text(encoding="utf-8")
        title = re.search(r"^# (.+)$", page, re.M).group(1)
        if not title.startswith(prefix):
            wrong.append(f"{match['doc']}: title {title!r} does not begin {prefix!r}")
            continue
        rest = title[len(prefix):]
        if match["label"] != rest[0].upper() + rest[1:]:
            wrong.append(f"{match['doc']}: menu says {match['label']!r} for the title {title!r}")
    assert not wrong, f"{tab}/index.md:\n" + "\n".join(wrong)


@pytest.mark.xdist_group("manual-build")
def test_every_page_brands_its_header_with_the_sites_home(built_docs_tree):
    """The brand goes to the site's home page, the landing page, from every page.

    Asserted on every built page, because the brand is in the header and a pydata
    upgrade renaming `navbar_start`'s slot would drop it with a green build.  The
    wordmark is checked as the word itself, `_about.DIST_NAME`.  The way back to
    this manual's own front page is the breadcrumb's, below."""
    from rietx._about import DIST_NAME

    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    pages = _built_pages(out)
    wrong: list[str] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        name = page.relative_to(out).as_posix()
        if HEADER_BRAND.findall(text) != [DOCS_URL]:
            wrong.append(f"{name}: brand href {HEADER_BRAND.findall(text)} (want {[DOCS_URL]})")
        elif f'rietx-wordmark">{DIST_NAME}</p>' not in text:
            wrong.append(f"{name}: the brand carries no wordmark")
    assert not wrong, f"{len(wrong)} of {len(pages)} pages:\n" + "\n".join(wrong[:10])


@pytest.mark.xdist_group("manual-build")
def test_every_breadcrumb_starts_at_the_manual_and_stops_at_the_parent(built_docs_tree):
    """The trail's first item is "Manual", linking the front page, and its last is the
    page's parent, never the page, whose title is the H1 directly under it.  The front
    page carries none, nor do Sphinx's own index and search pages, which have no
    article header.  Read on the built pages, since the trail is a template."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    pages = [p for p in _built_pages(out) if p.relative_to(out).as_posix() not in SPHINX_PAGES]
    wrong: list[str] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        name = page.relative_to(out).as_posix()
        trail = re.search(r'<nav aria-label="Breadcrumb".*?</nav>', text, re.S)
        if page == out / "index.html":
            if trail:
                wrong.append(f"{name}: the front page carries a trail")
            continue
        if not trail:
            wrong.append(f"{name}: no trail")
            continue
        items = re.findall(r'<li class="breadcrumb-item[^"]*">(.*?)</li>', trail.group(0), re.S)
        links = [re.search(r'<a href="([^"]*)"[^>]*>(.*?)</a>', item, re.S) for item in items]
        if not items or not all(links):
            wrong.append(f"{name}: an item that is not a link, {items}")
            continue
        home = (page.parent / links[0][1]).resolve()
        if (links[0][2], home) != ("Manual", (out / "index.html").resolve()):
            wrong.append(f"{name}: first item {links[0][2]!r} -> {links[0][1]}")
        if any((page.parent / link[1]).resolve() == page.resolve() for link in links):
            wrong.append(f"{name}: the trail names the page itself")
    assert not wrong, f"{len(wrong)} of {len(pages)} pages:\n" + "\n".join(wrong[:10])


@pytest.mark.xdist_group("manual-build")
def test_no_page_credits_its_tools_or_folds_its_sidebar(built_docs_tree):
    """The footer is the site's line, with no credit to Sphinx or the theme, and the
    sidebar has no collapse control: pydata 0.23 keeps no state for it, so every
    click through to another page opened it again."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    pages = _built_pages(out)
    unwanted = ("Created using", "Built with the", "pst-collapse-sidebar-button")
    wrong = [f"{p.relative_to(out).as_posix()}: {word!r}"
             for p in pages for word in unwanted if word in p.read_text(encoding="utf-8")]
    missing = [p.relative_to(out).as_posix() for p in pages
               if 'class="rietx-footer"' not in p.read_text(encoding="utf-8")]
    assert not wrong, "\n".join(wrong[:10])
    assert not missing, f"no site footer on {missing[:10]}"


@pytest.mark.xdist_group("manual-build")
def test_every_page_links_its_markdown_twin(built_docs_tree):
    """The right column's "This page as markdown" link, in place of "Show source",
    names the twin the build wrote beside the page, and every page with a twin has it.
    A page without a right column has nowhere to hold it: the front page (`conf.py`)
    and a wide table's page that removes the column for room."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    wrong: list[str] = []
    for page in _built_pages(out):
        text = page.read_text(encoding="utf-8")
        if 'class="sidebar-secondary-items' not in text:
            continue
        name = page.relative_to(out).as_posix()
        link = re.search(r'class="tocsection rietx-twin">\s*<a href="([^"]*)"', text)
        twin = page.with_name(page.name + ".md")
        if twin.is_file() and not link:
            wrong.append(f"{name}: no link to its twin")
        elif link and (page.parent / link[1]).resolve() != twin.resolve():
            wrong.append(f"{name}: links {link[1]}, not its twin")
        elif link and not twin.is_file():
            wrong.append(f"{name}: links {link[1]}, which the build did not write")
    assert not wrong, "\n".join(wrong[:10])


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


#: A tutorial notebook's twin, in `TUTORIAL_HOME`, where the notebooks are copied.
def _notebook_twins() -> set[str]:
    return {f"{TUTORIAL_HOME}/{nb.stem}.html.md" for nb in _tutorial_notebooks()}


@pytest.mark.xdist_group("manual-build")
def test_every_page_has_a_twin_that_keeps_the_contract(built_docs_tree):
    """One twin per page and per tutorial notebook, with no MyST left in it,
    its title and answer sentence, and under the 50 000-character cap.

    A notebook is held to the same contract as a page: each tutorial's
    authorship note sits below its opening paragraph, so the paragraph under
    the title answers (the waiver that excused this went in WP-1986)."""
    out, result = built_docs_tree
    assert result.returncode == 0, "the new tree did not build"
    twins = _twins(out)
    notebooks = _notebook_twins()
    pages = {page.relative_to(DOCS_TREE).with_suffix(".html.md").as_posix()
             for page in DOCS_PAGES} | notebooks
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


#: One page holding each node type the retired old tree used (WP-1986), so the
#: twin handles each one whether or not a page carries it today.
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

<div><img class="rx-fig-light only-light" alt="the inline figure" src="data:image/png;base64,%(light)s"><img class="rx-fig-dark only-dark" alt="" src="data:image/png;base64,%(dark)s"><style>.rx-fig-dark {display:none}</style></div>

Get {download}`the notes <notes.txt>` to read later.

```{py:function} rx.call(a: int, *, b: str = 'x') -> int
An API entry, whose bare `*` the HTML marks with a tooltip.
```

````{py:class} rx.Model
A model, whose {py:attr}`rx.Model.size` is a field.

```{py:fields}
name: str
size: float = 1.0
```
````

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
    half of a figure pair (a notebook's inline one written out as a file),
    a download, an API signature and a model's fields as a list (the HTML's
    field anchored and found by `{py:attr}`), every tab, the dropdown, an
    escaped table cell, a mermaid fence and the bibliography, with `-W`
    holding no node unknown."""
    import base64

    src = tmp_path / "src"
    src.mkdir()
    light, dark = b"\x89PNG\r\n\x1a\nlight", b"\x89PNG\r\n\x1a\ndark"
    (src / "index.md").write_text(
        _COVERAGE_PAGE % {"key": _bib_entries()[0][1],
                          "light": base64.b64encode(light).decode(),
                          "dark": base64.b64encode(dark).decode()},
        encoding="utf-8")
    for name in ("pic-light.png", "pic-dark.png"):
        (src / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    (src / "notes.txt").write_text("notes\n", encoding="utf-8")
    (src / "conf.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(DOCS_TREE.parent)!r})\n"
        "extensions = ['myst_parser', 'sphinx_design', 'sphinxcontrib.bibtex',\n"
        "              'sphinxcontrib.mermaid', 'markdown_twin', 'py_fields']\n"
        "myst_enable_extensions = ['colon_fence', 'dollarmath', 'amsmath']\n"
        f"bibtex_bibfiles = [{str(BIBFILE)!r}]\n"
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
                     "rx.call(a: int, \\*, b: str = 'x') → int",
                     "* `name: str`\n* `size: float = 1.0`",
                     "**First tab**", "Second tab text.",
                     "**The folded part**\n\nFolded text.",
                     "| x \\| y | z |",
                     "```mermaid\nflowchart LR"):
        assert fragment in twin, fragment
    assert "dark figure" not in twin
    assert _myst_residue(twin) == []
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'id="rx.Model.size"' in html and 'href="#rx.Model.size"' in html
    # The inline pair's light half is a file the twin links; the base64, the
    # dark half and its stylesheet are the browser's.
    inline = re.search(r"!\[the inline figure\]\((_images/twin-[0-9a-f]+\.png)\)", twin)
    assert inline and (out / inline[1]).read_bytes() == light, twin
    assert "data:image" not in twin and "rx-fig-dark" not in twin
    assert re.search(r"\[`?the notes`?\]\(_downloads/[0-9a-f]+/notes\.txt\)", twin), twin
    # The citation links its bibliography entry, which carries the label.
    anchor = re.search(r"\]\(#([\w-]+)\)", twin.split("cites", 1)[1])[1]
    entry = twin.split(f'<a id="{anchor}"></a>', 1)[1].lstrip()
    assert re.match(r"\*\*\[\w+\]\*\* \S.*1969", entry), entry


# ----------------------------------------------------------------------
# A signature in the code blocks' colours (WP-2023, docs/py_highlight.py)
# ----------------------------------------------------------------------

_SIGNATURE_PAGE = """\
# Signatures

```{py:function} rx.call(a: int, *, b: str | None = None, n: float = 1.5, k: int = 3, mode: Mode = 'x', lo=-inf, **kw: Any) -> rx.Model
A call.
```

```{py:function} rx.unparsed(a: dict[str, int], b = (0 × 3))
A list Sphinx can parse neither way, so its one parameter is bare text.
```

````{py:class} rx.Model
A model.

```{py:method} rx.Model.load(path: str) -> rx.Model
:classmethod:
A classmethod.
```

```{py:fields}
name: str
size: float = 1.0
flag: bool = False
```
````
"""

#: `<span class="pre">` is the HTML writer's wrapper round every piece of text in
#: a signature; dropped, a token reads as one span.
_PRE = re.compile(r'<span class="pre">([^<]*)</span>')


def _signature_build(tmp_path: Path, extensions: list[str]) -> tuple[str, str]:
    src = tmp_path / "src"
    src.mkdir(parents=True)
    (src / "index.md").write_text(_SIGNATURE_PAGE, encoding="utf-8")
    (src / "conf.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(DOCS_TREE.parent)!r})\n"
        f"extensions = {['myst_parser', 'markdown_twin', 'py_fields', *extensions]!r}\n"
        "project = 'signatures'\n",
        encoding="utf-8")
    out = tmp_path / "html"
    result = subprocess.run([sys.executable, "-m", "sphinx", "-W", "-q", "-E", "-b", "html",
                             str(src), str(out)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    return (_PRE.sub(r"\1", (out / "index.html").read_text(encoding="utf-8")),
            (out / "index.html.md").read_text(encoding="utf-8"))


def test_a_signature_is_coloured_token_by_token_and_its_twin_is_unchanged(tmp_path):
    """Each piece of a signature carries the Pygments class a code block gives it,
    a default by the kind of literal it is, and the markdown twin is the page built
    without the extension byte for byte: the classes carry no text."""
    html, twin = _signature_build(tmp_path / "with", ["py_highlight"])
    _, plain = _signature_build(tmp_path / "without", [])
    assert twin == plain
    signatures = html.count('<dt class="sig sig-object py')
    assert signatures == 7 and html.count('<dt class="sig sig-object py highlight"') == signatures
    for fragment in (
            '<span class="sig-name descname nf">call</span>',
            '<span class="n">a</span><span class="p">:</span><span class="w"> </span>'
            '<span class="n"><span class="nb">int</span></span>',
            '<span class="nb">str</span><span class="w"> </span><span class="p">|</span>'
            '<span class="w"> </span><span class="kc">None</span>',
            '<span class="default_value kc">None</span>',
            '<span class="default_value mf">1.5</span>',
            '<span class="default_value mi">3</span>',
            '<span class="n"><span class="nc">Mode</span></span>',
            '<span class="default_value s">\'x\'</span>',
            # Not one literal: `ast.literal_eval` reads no `-inf`, and it stays a name.
            '<span class="default_value">-inf</span>',
            '<span class="o">**</span><span class="n">kw</span><span class="p">:</span>'
            '<span class="w"> </span><span class="n"><span class="nc">Any</span></span>',
            '<span class="sig-return-typehint"><a class="nc reference internal" href="#rx.Model"',
            '<span class="sig-name descname nc">Model</span>',
            '<span class="k">classmethod</span>',
            '<span class="sig-name descname nf">load</span>',
            '<span class="sig-name descname">flag</span><span class="property">'
            '<span class="p">:</span><span class="w"> </span><span class="nb">bool</span></span>'
            '<span class="property"><span class="w"> </span><span class="p">=</span>'
            '<span class="w"> </span><span class="default_value kc">False</span></span>',
            '<span class="default_value mf">1.0</span>'):
        assert fragment in html, fragment


@pytest.mark.xdist_group("manual-build")
def test_the_api_pages_signatures_carry_their_token_classes(built_docs_tree):
    """On the built pages: every Python signature is coloured, and four pinned ones
    carry the class each of their tokens takes — an instance method, a classmethod, a
    `py:fields` line and a `**kw`."""
    out, result = built_docs_tree
    assert result.returncode == 0, "manual did not build — see test_manual_builds_warning_free"
    pages = {name: _PRE.sub(r"\1", (out / "reference" / f"{name}.html").read_text(encoding="utf-8"))
             for name in ("api", "api-techniques", "api-types")}
    for name, html in pages.items():
        signatures = html.count('<dt class="sig sig-object py')
        assert signatures > 30, name
        assert html.count('<dt class="sig sig-object py highlight"') == signatures, name

    def signature(ident: str) -> str:
        html = pages["api"]
        start = html.index(f'id="{ident}"')
        return html[start:html.index("</dt>", start)]

    fit = signature("rx.Refinement.fit")
    for fragment in ('<span class="sig-name descname nf">fit</span>',
                     '<a class="nc reference internal" href="#rx.PatternData"',
                     '<span class="default_value s">\'rietveld\'</span>',
                     '<span class="nb">tuple</span><span class="p">[</span><span class="nb">float</span>',
                     '<span class="kc">None</span></span>',
                     '<span class="default_value kc">None</span>'):
        assert fragment in fit, fragment
    from_cif = signature("rx.Structure.from_cif")
    for fragment in ('<span class="k">classmethod</span>',
                     '<span class="sig-name descname nf">from_cif</span>',
                     '<span class="default_value kc">False</span>',
                     '<span class="sig-return-typehint"><a class="nc reference internal" '
                     'href="#rx.Structure"'):
        assert fragment in from_cif, fragment
    vary = signature("rx.Parameter.vary")
    assert '<span class="nb">bool</span>' in vary
    assert '<span class="default_value kc">False</span>' in vary
    read = signature("rx.read_pattern")
    assert ('<span class="o">**</span><span class="n">options</span><span class="p">:</span>'
            '<span class="w"> </span><span class="n"><span class="nc">Any</span>') in read


#: Every token class a coloured signature carries: Sphinx's own (its `desc_sig_*`
#: nodes, `m`/`kt`/`sc` among them for a `Literal[1]`-style annotation), and the
#: ones `docs/py_highlight.py` writes.
SIGNATURE_TOKENS = ("n", "o", "p", "w", "k", "kt", "m", "s", "sc",
                    "nf", "nc", "nb", "kc", "mi", "mf")


def _pygments_styles() -> dict[str, str]:
    """The light and dark Pygments styles the manual's `pygments.css` is built from:
    pydata-sphinx-theme's defaults, since `conf.py` sets neither."""
    import configparser

    import pydata_sphinx_theme

    conf = (DOCS_TREE / "conf.py").read_text(encoding="utf-8")
    assert "pygments_light_style" not in conf and "pygments_dark_style" not in conf, (
        "conf.py now names a Pygments style: read it here rather than the theme's default")
    theme = configparser.ConfigParser()
    theme.read(Path(pydata_sphinx_theme.__file__).parent / "theme" / "pydata_sphinx_theme"
               / "theme.conf")
    return {mode: theme["options"][f"pygments_{mode}_style"] for mode in ("light", "dark")}


def test_every_signature_colour_is_legible_on_its_grounds():
    """WCAG 2.2 AA on the site's own grounds, not the code block's: a signature sits
    on `--bg`, and on `--accent-soft` when reached by its permalink.  The colours
    are read from the stylesheet pydata writes, by its own function."""
    from pydata_sphinx_theme.pygments import get_pygments_stylesheet

    from tests.test_landing import contrast, site_tokens

    styles = _pygments_styles()
    css = get_pygments_stylesheet(styles["light"], styles["dark"])
    tokens = {"light": site_tokens()["light"], "dark": site_tokens()["dark (pinned)"]}
    low, measured = [], 0
    for mode in ("light", "dark"):
        prefix = re.escape(f'html[data-theme="{mode}"] .highlight')
        base = re.search(prefix + r" \{[^}]*?color: (#[0-9a-fA-F]{6})", css)[1]
        for token in SIGNATURE_TOKENS:
            rule = re.search(prefix + rf" \.{token} \{{[^}}]*?color: (#[0-9a-fA-F]{{6}})", css)
            colour = rule[1] if rule else base
            for ground in ("bg", "accent-soft"):
                ratio = contrast(colour, tokens[mode][ground])
                measured += 1
                if ratio < 4.5:
                    low.append(f"{mode} .{token} {colour} on --{ground}: {ratio:.2f}")
    assert measured == 2 * len(SIGNATURE_TOKENS) * 2
    assert not low, "\n".join(low)
