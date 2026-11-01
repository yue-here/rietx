"""The landing page (`docs/landing/`, WP-1331): what it may publish, and what it must not.

Three failure modes, none of which any other suite sees.

**The ignore rules, in both directions.** `site/`, `dist/` and `preview.html`
are build products and ignored — `preview.html` in particular was matched by the
`!docs/**/*.html` un-ignore and would have been committed, 3.2 MB with the
payload inlined. The other
direction is the older bug: the repo-wide `*.png` rule has now swallowed four
directories of committed images (Part 1's figures, the GUI chapters'
screenshots, the GUI dist, and this page's four), so `img/` is un-ignored and
asserted here. `git check-ignore` is the only way to ask the question, and
reading `.gitignore` by eye is what failed the first three times
(`tests/test_gui_dist.py` § the `*.html` rule).

**A build product nobody ran.** `build.py --site` is what the Pages workflow
publishes, and until WP-1331 nobody had served its output: the page is authored
as an artifact *fragment*, so without the document skeleton the site build
rendered every `·` and `°C` as mojibake, and the payload fetch its own comments
promised did not exist. Both are asserted on the assembled bytes.

**A link that means the wrong page.** `/` is the landing page and the manual is
`/docs/` (WP-1986), so a `https://rietx.org/` in the page that meant "the manual"
silently points at the page itself, and a link into a chapter lands only if the
page it names is built or stubbed.

Everything here reads `docs/landing/build.py`'s own tables rather than restating
them, so a new image or a new leak token is covered by adding it there.
"""

from __future__ import annotations

import functools
import html as _html
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LANDING = REPO_ROOT / "docs" / "landing"

# One worker for the module: `build.py --site` rmtree's and rewrites
# `docs/landing/site`, so two workers running it at once race over the same
# directory (tests/CLAUDE.md — a shared fixture stays on one worker, and this
# shares a directory rather than a fixture).  The module costs about a second.
#
# The group is the module's own.  It was the manual build's while the old
# tree's `conf.py` put `docs/landing/site` on `html_extra_path`, so a sphinx
# build on another worker copied the very directory this module rmtree's.  No
# build reads that directory since WP-1986 retired the old tree (pages.yml
# copies it into the site itself), so sharing the group would only queue this
# module behind the manual's build.
pytestmark = pytest.mark.xdist_group("landing-site")


def _build_module():
    """`docs/landing/build.py` imported by path: it is a script beside the page,
    not a package, and this suite reads its tables rather than copying them."""
    spec = importlib.util.spec_from_file_location("landing_build", LANDING / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build():
    return _build_module()


@pytest.fixture(scope="module")
def build_demo():
    """`docs/landing/build_demo.py`, imported by path like `build.py` above."""
    spec = importlib.util.spec_from_file_location("landing_build_demo", LANDING / "build_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: Where every build here reads the notebooks.  The page links the newest release tag,
#: and CI's shallow checkouts carry no tags, so the suite builds at `HEAD` and the tag
#: lookup is asserted on a repository of its own (WP-1917).
REF = "HEAD"


@pytest.fixture(scope="module")
def site_html(build) -> str:
    """The landing page's site build, assembled without writing anything."""
    return build.assemble(True, ref=REF)


#: Every page `build.py` serves, read off its own table so a new page is covered by
#: adding it there.
PAGE_NAMES = list(_build_module().PAGES)


@pytest.fixture(scope="module", params=PAGE_NAMES)
def any_page(request, build) -> tuple[str, str]:
    """(name, site build) for each page in turn."""
    return request.param, build.assemble(True, request.param, REF)


# ----------------------------------------------------------------------
# What may reach the repository
# ----------------------------------------------------------------------

#: path -> must it be ignored?
IGNORE_EXPECTED = {
    "docs/landing/src/shell.html": False,      # what every page shares
    "docs/landing/src/index.html": False,      # the landing page's own body
    "docs/landing/src/why.html": False,
    "docs/landing/src/tokens.css": False,      # the site's colours, the manual's too
    "docs/landing/src/favicon.svg": False,     # the site's one favicon
    "docs/landing/build.py": False,
    "docs/landing/README.md": False,
    "docs/landing/img/fap-light.png": False,   # committed figure, under a repo-wide *.png
    "docs/landing/img/gui-history-dark.png": False,
    "docs/landing/data/demo.json": False,      # committed, and decimated to earn it
    "docs/landing/data/transcript.json": False,
    "docs/landing/preview.html": True,         # built page, payload inlined
    "docs/landing/dist/index.html": True,
    "docs/landing/site/index.html": True,
    "docs/landing/site/why.html": True,
    "docs/landing/dist/why.html": True,
}


def _ignored(paths: list[str]) -> set[str]:
    """The subset of `paths` git ignores.

    ``--no-index`` because check-ignore consults the index first and answers for
    a *tracked* file from there, which would hide exactly the regression this
    asks about (the same reason `tests/test_gui_dist.py` passes it)."""
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *paths],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    # rc 0: some path matched.  rc 1: none did.  Anything else is a real failure.
    assert result.returncode in (0, 1), f"git check-ignore failed: {result.stderr}"
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_the_payload_cannot_be_committed_and_the_figures_cannot_be_dropped():
    """Both directions at once, because the file gets them wrong both ways: a
    rule that publishes the contributor's data, and a rule that hides the
    page's images while every local checkout still has them."""
    ignored = _ignored(list(IGNORE_EXPECTED))
    for path, want in IGNORE_EXPECTED.items():
        got = path in ignored
        assert got == want, (
            f"{path}: git {'ignores' if got else 'tracks'} it, expected "
            f"{'ignored' if want else 'tracked'}.  See .gitignore's landing-page "
            f"block — order decides there, the last matching rule wins."
        )


def test_the_committed_figures_are_actually_committed():
    """The un-ignore above is necessary and not sufficient: it says git *would*
    take the files.  This says it did — a fresh clone gets the pictures."""
    tracked = subprocess.run(
        ["git", "ls-files", "docs/landing/img"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    build = _build_module()
    for rel in build.IMAGES.values():
        assert f"docs/landing/{rel}" in tracked, (
            f"{rel} is referenced by build.py but not tracked — a clone would "
            f"build the page with a broken image"
        )


#: rietx asks for 5-10 steps across a FWHM and raises PATTERN_UNDERSAMPLED below 5
#: (`optimize.statistics`).  The committed payload has to sit clearly under that: it
#: is what makes the file a figure of the contributor's series rather than the series.
MAX_STEPS_PER_FWHM = 3.0


def test_the_committed_payload_is_below_what_can_be_refined():
    """The redaction is asserted, not merely performed.

    `docs/landing/data/demo.json` is in the repository because it keeps every
    second measured channel; at the acquisition's own step it would be a copy of a
    contributor's unpublished in-situ series.  If someone rebuilds it at full
    resolution — `build_demo.py` takes the factor as an argument and defaults to 1 —
    nothing else would notice.

    Decimation, not averaging, for a reason worth keeping: a mean of k channels
    divides the counting noise by sqrt(k), so the observed cloud tightens onto the
    calculated curve and the difference curve flattens, and the panel then shows a
    better fit than the Rwp printed beside it.
    """
    payload = json.loads((LANDING / "data" / "demo.json").read_text(encoding="utf-8"))
    # .get, not [], so a payload built before the field existed fails with the
    # message rather than a KeyError
    assert payload.get("decimation", 1) >= 2, (
        "the committed payload is at full resolution; rebuild it with a decimation "
        "factor (build_demo.py <bundle> <out> 2)"
    )
    assert payload.get("steps_per_fwhm", 99) <= MAX_STEPS_PER_FWHM, (
        f"{payload['steps_per_fwhm']} steps across a peak is refinable data "
        f"(rietx wants 5-10); rebuild with a larger decimation factor"
    )


def test_the_animation_caption_says_what_the_data_is_and_who_it_is_owed_to(site_html):
    """The rig's caption: what the measurement was, then the credit for it.

    It once described the run and named the support phases; both went when the
    phases did, leaving the credit alone.  WP-1411 put the description back, from
    the section head above the rig, which now opens on what the agent was asked to
    do rather than on the specimen.

    Pinned, and the pin is worth more than an exact string usually is, because the
    credit is the one thing on this page that is owed to somebody and the
    description is the one thing that fences what the payload is.  Neither may
    drift silently: an edit that changes either should have to say so here, which
    is what the 2026-09-14 rewrite did.
    """
    captions = re.findall(r'<p class="caption">(.*?)</p>', site_html, re.S)
    text = re.sub(r"<[^>]+>", "", captions[0]).strip()
    assert text == (
        "The dataset is 275 in situ XRD patterns from a supported Cu/CuO redox "
        "experiment collected on a lab diffractometer with ~30 s acquisitions. "
        "The measurements were made at up to 300&nbsp;&deg;C under changing "
        "chemical environments using a bespoke gas cell. "
        "Contributed by Michael W. Gaultois. Work performed with Jamie Capel, "
        "Martin C. Chan, Stuart Scott, Felix Donat, and Prof. Dame Clare Grey at "
        "the Department of Chemistry, University of Cambridge. "
        "Visualisation constructed by Claude."
    )


def test_the_support_phases_ship_unnamed(build_demo):
    """The payload names the reacting phases; the support formulation is not named at all.

    Cu, Cu2O and CuO are the animation's subject.  The support phases would pin the
    contributor's unpublished sample, so they ship positionally as "support n" — and the
    builder does not know their names either: `phase_columns` reads every other `wtpct_`
    column straight off the bundle's own header.  Deliberately not a `build.LEAK` token,
    because a denylist publishes what it denies.
    """
    payload = json.loads((LANDING / "data" / "demo.json").read_text(encoding="utf-8"))
    support = [ph for ph in payload["phases"] if ph["support"]]
    assert support, "no support phases in the payload"
    for i, ph in enumerate(support, start=1):
        assert ph["name"] == ph["html"] == f"support {i}", ph

    named = [name for _, name, _ in build_demo.REACTING]
    assert [ph["name"] for ph in payload["phases"] if not ph["support"]] == named

    # the mechanism, on a header the bundle could have: whatever the extra columns are
    # called, they come back positional
    cols = build_demo.phase_columns(
        ["series_index"] + [f"wtpct_{c}" for c, *_ in build_demo.REACTING]
        + ["wtpct_SomePhase", "wtpct_Another"])
    assert [name for _, name, _, _ in cols] == named + ["support 1", "support 2"]
    assert [sup for *_, sup in cols] == [False] * len(named) + [True, True]


def test_no_leak_token_reaches_a_built_page(any_page, build):
    """`build.py` raises on a leak at build time; this is the same question
    asked of the assembled bytes, so a change to `leaks()` that stopped
    raising would still be caught."""
    name, page = any_page
    assert build.leaks(page) == [], name


def test_every_placeholder_is_filled(any_page):
    name, page = any_page
    assert "%%" not in page, name


def test_every_page_says_claude_wrote_it(any_page):
    """Anything published under the maintainer's name carries a line saying Claude
    wrote it, and the shell's footer is where each page says so.  The line is per
    page because the pages differ: the essay's words are the maintainer's own."""
    name, page = any_page
    notes = re.findall(r'<span class="note">(.*?)</span>', page, re.S)
    assert len(notes) == 1 and "Claude" in notes[0], f"{name}: {notes}"


# ----------------------------------------------------------------------
# What the site build has to be for a web server
# ----------------------------------------------------------------------

def test_the_site_build_is_a_document_not_a_fragment(any_page):
    """The source is authored for the Artifact runtime, which supplies the
    skeleton and refuses a file that brings its own.  A web server supplies
    none of it: without the charset every `·`, `°C` and `θ` on the page is
    mojibake unless the server happens to say utf-8."""
    head = any_page[1][:400].lower()
    assert head.startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in head
    assert "width=device-width" in head


def test_the_inline_build_stays_a_fragment(build):
    """...and the other build must NOT gain one, or the artifact publish gets a
    document inside a document."""
    assert build.DEMO.exists(), "the payload is committed; this should not be conditional"
    for name in build.PAGES:
        assert not build.assemble(False, name, REF).lstrip().lower().startswith("<!doctype"), name


def test_the_page_fetches_the_payload_it_does_not_inline(site_html):
    """The site build leaves the data tag empty on purpose — 1.9 MB inlined is
    1.9 MB before the first paint — so the page has to fetch it.  For a whole
    release the source only *said* it did, and the animation never ran."""
    assert 'id="demo-data"></script>' in site_html.replace("\n", "")
    assert 'fetch(' in site_html, "the site build has nothing to load its payload with"
    for url in ("data/demo.json", "data/transcript.json"):
        assert url in site_html


# ----------------------------------------------------------------------
# Where the page points
# ----------------------------------------------------------------------

def _links(page: str) -> list[str]:
    return re.findall(r'(?:href|src)="([^"]+)"', page)


@functools.cache
def _versions():
    """`docs/docs_versions.py`, imported by path once a session: its `RETIRED`
    table is where an old-tree address is sent."""
    spec = importlib.util.spec_from_file_location(
        "_docs_versions", REPO_ROOT / "docs" / "docs_versions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_no_link_means_the_manual_and_lands_on_this_page(any_page):
    """`/` is the landing page since WP-1331 and the manual is `/docs/` since
    WP-1986.  Three links in the page meant "the manual" and pointed at the site root."""
    name, page = any_page
    roots = [a for a in _links(page) if a.rstrip("/") == "https://rietx.org"]
    assert len(roots) == 1, (
        f"{name}: {len(roots)} links point at the site root; exactly one may (the brand, "
        f"which does mean 'home').  A link meaning the manual is https://rietx.org/docs/."
    )


def test_every_link_into_the_manual_lands_on_a_page(any_page):
    """A chapter link is either a page of the manual under `/docs/<version>/` or an
    old-tree address `docs_versions.RETIRED` stubs, which sends the reader to the
    released tree once one carries the page and to `dev/` until then (WP-1986).  A
    stub link carries no `#fragment`: the stub carries one over, but a chapter's
    sections took new heading ids on their new pages."""
    name, page = any_page
    retired = _versions().RETIRED
    tree = REPO_ROOT / "docs" / "docs"
    for link in _links(page):
        path = link.removeprefix("https://rietx.org/")
        if path == link or not path.partition("#")[0].endswith(".html"):
            continue
        if path.startswith("lite/"):
            continue
        target, _, fragment = path.partition("#")
        target = target.removesuffix(".html")
        version = re.match(r"docs/[^/]+/", target)
        if version:
            rel = target[version.end():]
            source = tree / rel
            # A notebook page is copied in at build from its committed .ipynb
            # (`sphinx_shared.copy_tutorials`), and only into start/tutorials/.
            notebook = (rel.rpartition("/")[0] == "start/tutorials" and (
                REPO_ROOT / "examples" / "tutorials" / f"{source.name}.ipynb").is_file())
            assert source.with_suffix(".md").is_file() or notebook, (
                f"{name}: {link} names no page of docs/docs/")
        else:
            assert target in retired, f"{name}: {link} is neither a manual page nor a stub"
            assert not fragment, (
                f"{name}: {link} carries #{fragment}, which names an old-tree heading")


def test_the_landing_page_alone_is_written_at_the_site_root():
    """The other half of that: sphinx writes its root document to index.html,
    so the landing page keeps `/` only while no sphinx build writes into the
    site's root.  Since WP-1986 the manual builds under `site/docs/`, and
    pages.yml copies the landing page's own build into `site/`."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    builds = re.findall(r"-m sphinx\b[^\n]*", workflow)
    assert builds, "pages.yml builds no manual"
    for build in builds:
        assert build.split()[-1].startswith("site/docs/"), (
            f"a sphinx build writes outside site/docs/, over the landing page: {build}")
    assert "docs/landing/build.py --site" in workflow
    assert "cp -R docs/landing/site/. site/" in workflow, (
        "pages.yml no longer copies the landing page into the site root")


def test_every_relative_link_resolves_to_something_the_build_writes(any_page, build):
    """A root-relative or bare link in a page has to name a file
    `build.py --site` puts beside it, and a fragment has to name an id the page
    it points into carries: the hero's quickstart is reached by `#quickstart`
    from wherever a link to it sits.  Derived from build.py's own tables, so a
    new image or a new page is covered by adding it there."""
    name, page = any_page
    written = {"favicon.svg", "data/demo.json", "data/transcript.json"}
    written |= set(build.IMAGES.values()) | set(build.PAGES)
    written |= {f"notebooks/{nb.name}" for nb in build.notebooks(REF)}
    for link in _links(page):
        if link.startswith("#"):
            assert f'id="{link[1:]}"' in page, f"{name}: {link!r} names an id the page does not carry"
            continue
        if link.startswith(("http://", "https://", "data:", "mailto:")):
            continue
        path, _, fragment = link.partition("#")
        path = path.lstrip("/")
        path = "index.html" if path in ("", ".", "./") else path.removeprefix("./")
        assert path in written, (
            f"{name}: {link!r} is not written by build.py --site (it writes {sorted(written)})"
        )
        if fragment:
            assert f'id="{fragment}"' in build.assemble(True, path, REF), (
                f"{name}: {link!r} names an id {path} does not carry")


# ----------------------------------------------------------------------
# What the page claims about the package
# ----------------------------------------------------------------------

def test_every_rietx_name_the_page_shows_still_exists(site_html):
    """The page prints a complete script and its output.  A rename in the
    package would leave the published page quoting a call that no longer
    exists, and nothing else in the suite reads this file."""
    rietx = pytest.importorskip("rietx")
    text = _html.unescape(re.sub(r"<[^>]+>", "", site_html))
    names = sorted(set(re.findall(r"\brx\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)", text)))
    assert names, "found no rx.* call in the page — has the example section moved?"
    for dotted in names:
        obj = rietx
        for part in dotted.split("."):
            assert hasattr(obj, part), f"the page shows rx.{dotted}, but {part!r} does not resolve"
            obj = getattr(obj, part)


def test_the_example_the_page_quotes_is_a_script_that_runs(site_html):
    """`examples/` is the one authority for a worked walkthrough (root
    CLAUDE.md).  The page presents its own syntax-highlighted copy, so this
    checks the script exists and is the one the suite runs; what it *prints* is
    `tests/test_tutorials.py`'s question (WP-1545)."""
    assert (REPO_ROOT / "examples" / "tutorials" / "02_simple_rietveld.py").is_file()
    assert "02_simple_rietveld.py" in site_html


def test_build_py_site_runs_and_writes_the_files_it_names(build):
    """The `__main__` half — the copying, and the guard that lets an absent
    payload through.  It writes into `docs/landing/site`, which is gitignored,
    exactly as `tests/test_examples.py` accepts the scripts' PNGs."""
    result = subprocess.run(
        [sys.executable, str(LANDING / "build.py"), "--site", "--ref", REF],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"build.py --site failed:\n{result.stdout}\n{result.stderr}"
    site = LANDING / "site"
    for name in build.PAGES:
        assert (site / name).is_file(), f"build.py --site wrote no {name}"
    assert (site / "favicon.svg").is_file()
    for rel in build.IMAGES.values():
        assert (site / rel).is_file(), f"build.py --site wrote no {rel}"
    # A download is the file the Colab link opens: the notebook at the ref, byte for byte.
    for nb in build.notebooks(REF):
        shown = subprocess.run(["git", "-C", str(REPO_ROOT), "show", f"{REF}:{nb.path}"],
                               capture_output=True, check=True).stdout
        assert (site / "notebooks" / nb.name).read_bytes() == shown, nb.name


# ----------------------------------------------------------------------
# The agent quickstart: a prompt somebody pastes, so every command in it runs
# ----------------------------------------------------------------------

def _prompt(site_html: str) -> tuple[str, list[str]]:
    """The quickstart prompt's text, and every `code` span in it."""
    block = re.search(r'<div class="qs-prompt" id="qs-prompt">(.*?)</div>', site_html, re.S)
    assert block, "no quickstart prompt on the landing page"
    codes = [_html.unescape(c) for c in re.findall(r"<code>(.*?)</code>", block.group(1))]
    return _html.unescape(re.sub(r"<[^>]+>", "", block.group(1))), codes


def test_the_quickstart_installs_this_package_from_where_it_lives(site_html):
    """Both install lines name the real package: the PyPI one by the distribution
    name, the GitHub one by the repository `_about` publishes.  The Python floor
    the prompt quotes is pyproject's, which is what pip enforces."""
    about = pytest.importorskip("rietx._about")
    text, codes = _prompt(site_html)
    assert f"pip install {about.DIST_NAME}" in codes
    assert f"pip install git+{about.REPO_URL}" in codes
    floor = re.search(r'requires-python = ">=(\d+\.\d+)"',
                      (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    assert f"Python {floor} or newer" in text, f"the prompt does not quote Python {floor}"


def test_the_quickstart_skill_command_writes_the_file_it_says_to_read(site_html, tmp_path, monkeypatch):
    """`rietx skill --install`, run where the prompt runs it (the data folder),
    has to leave a SKILL.md at the path the prompt then tells the agent to read.
    Run through the CLI rather than `skill.install`, because the command is what
    the agent types."""
    cli = pytest.importorskip("rietx.cli")
    _, codes = _prompt(site_html)
    command = next(c for c in codes if c.startswith("rietx skill"))
    path = next(c for c in codes if c.endswith("SKILL.md"))
    monkeypatch.chdir(tmp_path)
    assert cli.main(command.split()[1:]) == 0
    assert (tmp_path / path).is_file(), f"{command!r} wrote no {path}"


# ----------------------------------------------------------------------
# The Jupyter quickstart (WP-1917): one row a notebook, linked at the release
# ----------------------------------------------------------------------

def _rows(page: str) -> list[str]:
    block = re.search(r'<ul class="nb-list">(.*?)</ul>', page, re.S)
    assert block, "no Jupyter quickstart on the landing page"
    return re.findall(r"<li>(.*?)</li>", block.group(1), re.S)


def test_the_jupyter_quickstart_has_one_row_per_notebook(site_html):
    """The rows follow the tutorials' own glob, so a sixth notebook gets a row with
    no edit to the page, and each row's title is its notebook's heading."""
    spec = importlib.util.spec_from_file_location(
        "_landing_tutorials_test", REPO_ROOT / "examples" / "tutorials" / "build.py")
    tutorials = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tutorials)
    sources = tutorials.sources()
    rows = _rows(site_html)
    assert len(rows) == len(sources), f"{len(rows)} rows for {len(sources)} tutorials"
    for row, source in zip(rows, sources):
        heading = next(line for line in source.read_text(encoding="utf-8").splitlines()
                       if line.startswith("# # "))
        assert f'<span class="nb-title">{_html.escape(heading[4:].strip())}</span>' in row, source.name
        assert row.count(f"{source.stem}.ipynb") == 3 and f"/{source.stem}.html" in row, source.name


def test_every_colab_link_opens_the_notebook_at_the_ref(site_html, build):
    """Colab opens the file at the ref the page was built at, which the Pages build
    takes to be the newest release tag, so the notebook's `%pip install rietx`
    installs the version it was built with."""
    repo = build.ABOUT.REPO_URL.removeprefix("https://github.com/")
    prefix = f"https://colab.research.google.com/github/{repo}/blob/{REF}/"
    links = re.findall(r'href="(https://colab\.research\.google\.com/[^"]+)"', site_html)
    assert len(links) == len(_rows(site_html))
    for link in links:
        assert link.startswith(prefix), link
        found = subprocess.run(["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{REF}:{link[len(prefix):]}"])
        assert found.returncode == 0, f"{link} names no file at {REF}"


def test_every_jupyterlite_link_opens_a_notebook_the_lite_site_serves(site_html, build):
    """A JupyterLite link opens the browser copy (WP-1966).  `pages.yml` builds that site
    to /lite/, and `docs/lite/build.py` puts each notebook at its root under its file name.
    That build reads the notebooks at `HEAD` while the rows read the tag, so this suite,
    which builds both at `HEAD`, cannot see a tutorial renamed since the release.  The URL
    form is the one `smoke.mjs` opens."""
    links = re.findall(r'href="([^"]+)">JupyterLite</a>', site_html)
    assert links == [build.LITE + nb.name for nb in build.notebooks(REF)]
    form = "/notebooks/index.html?path="
    assert build.LITE == f"{build.ABOUT.DOCS_URL}/lite{form}"
    smoke = (REPO_ROOT / "docs" / "lite" / "smoke.mjs").read_text(encoding="utf-8")
    assert f"${{base}}{form}" in smoke, "smoke.mjs opens the notebooks at another URL"
    workflow = (REPO_ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "--out site/lite" in workflow, "pages.yml no longer builds the browser site at /lite/"


def test_every_read_link_is_a_page_the_manual_builds(site_html):
    """A Read link lands on the notebook's manual page, which exists while the
    tutorials index lists it in its toctree (`start/tutorials.md`, WP-1916).

    The link reaches the page either directly, under `/docs/<version>/`, or
    through the redirect stub the retired old tree's address became
    (`docs/docs_versions.py`'s `RETIRED`, WP-1986), which must then send the
    reader to that same page."""
    versions = _versions()
    index = (REPO_ROOT / "docs" / "docs" / "start" / "tutorials.md").read_text(encoding="utf-8")
    toctree = re.search(r"```\{toctree\}(.*?)```", index, re.S).group(1).split()
    reads = re.findall(r'href="https://rietx\.org/([^"]+)\.html">Read</a>', site_html)
    assert len(reads) == len(_rows(site_html))
    for path in reads:
        if not re.match(r"docs/[^/]+/start/tutorials/", path):
            assert path in versions.RETIRED, f"/{path}.html is neither a manual page nor a stub"
            path = versions.RETIRED[path]
        page = "tutorials/" + path.rsplit("/", 1)[-1]
        assert path.endswith(f"start/{page}") and page in toctree, (
            f"/{path}.html is not in the manual's tutorials toctree")


def test_each_quickstart_toggle_controls_a_panel_that_starts_hidden(site_html):
    """One disclosure button per panel, none pressed and every panel hidden at
    load, so the page opens on the row of buttons.  That opening one closes the
    other is the script's, and a browser check's to see."""
    controls = re.findall(r'<button class="btn qs-toggle" type="button" aria-expanded="false" '
                          r'aria-controls="([\w-]+)"', site_html)
    panels = re.findall(r'<div class="qs-panel" id="([\w-]+)" hidden="until-found">', site_html)
    assert sorted(controls) == sorted(panels) == ["notebooks", "quickstart"], (controls, panels)
    assert not re.search(r'<button[^>]*aria-expanded="true"', site_html)


def test_the_release_tag_is_the_newest_and_its_absence_refuses(build, tmp_path):
    """By version order, not by name, and only `vX.Y.Z`: this repository also
    carries tags like `guillemot-study`.  With none the build refuses, since a
    fallback to `main` would link notebooks PyPI cannot run."""
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgSign=false", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        *args], check=True, capture_output=True)
    git("init", "-q")
    git("commit", "-q", "--allow-empty", "-m", "start")
    with pytest.raises(SystemExit, match="no vX.Y.Z tag"):
        build.release_tag(tmp_path)
    for tag in ("v1.9.0", "v1.10.0", "v1.11.0rc1", "guillemot-study", "v2"):
        git("tag", tag)
    assert build.release_tag(tmp_path) == "v1.10.0"


# ----------------------------------------------------------------------
# The site's colours (WP-2021): one file, every text colour legible on its ground
# ----------------------------------------------------------------------

TOKENS = LANDING / "src" / "tokens.css"
_HEX_TOKEN = re.compile(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\b")


def site_tokens() -> dict[str, dict[str, str]]:
    """`tokens.css`'s three blocks, each a name -> hex map of the colours it spells.

    Keyed ``light``, ``dark (system)`` and ``dark (pinned)``, in file order:
    `:root`, the `prefers-color-scheme` block and `:root[data-theme="dark"]`.
    Only six-digit hexes are read; the shadows and the faces are not colours a
    contrast is measured on.  `tests/test_manual.py` reads the accent here too."""
    text = re.sub(r"/\*.*?\*/", "", TOKENS.read_text(encoding="utf-8"), flags=re.S)
    light, rest = text.split("@media", 1)
    system, pinned = rest.split(':root[data-theme="dark"]', 1)
    return {name: dict(_HEX_TOKEN.findall(block)) for name, block in
            (("light", light), ("dark (system)", system), ("dark (pinned)", pinned))}


def _luminance(colour: str) -> float:
    """Relative luminance, WCAG 2.2 § relative luminance."""
    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(int(colour[i:i + 2], 16) / 255) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG 2.2 contrast ratio, from 1 to 21."""
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


#: The grounds text is set on.  `--surface-3` is a hover ground only.
GROUNDS = ("bg", "surface", "surface-2")
#: (colour, the grounds it is drawn on, its bar), as `docs/landing/README.md`
#: § House style assigns them.  Text takes AA's 4.5:1.  `--faint` is the one
#: text colour kept off `--surface-2`, where a label takes `--muted` instead.
#: `--accent` draws marks, bars and underlines, never words, so it takes a UI
#: component's 3:1.  `--on-accent` is absent because no page sets words on the
#: accent: pydata's one use, the search-match link in `#searchbox`, is a plain
#: link in the manual's `custom.css`, since white on the light accent is 4.2:1.
LEGIBLE = (
    *((text, GROUNDS, 4.5) for text in
      ("ink", "ink-2", "muted", "accent-ink", "ok", "warn", "info", "danger")),
    ("faint", ("bg", "surface"), 4.5),
    *((text, ("surface-3",), 4.5) for text in ("ink", "ink-2", "muted", "accent-ink")),
    ("accent", GROUNDS, 3.0),
)


def test_the_two_dark_blocks_are_one_set_of_values():
    """Dark is written twice, for the system's choice and for a pinned theme, and a
    value changed in one block alone is a dark mode that depends on how you got there."""
    tokens = site_tokens()
    system, pinned = tokens["dark (system)"], tokens["dark (pinned)"]
    assert system == pinned, {name: (system.get(name), pinned.get(name))
                              for name in system.keys() | pinned.keys()
                              if system.get(name) != pinned.get(name)}
    assert tokens["light"].keys() == pinned.keys(), tokens["light"].keys() ^ pinned.keys()


@pytest.mark.parametrize("theme", ["light", "dark (pinned)"])
def test_every_text_colour_is_legible_on_every_ground_it_is_set_on(theme):
    """WCAG 2.2 AA, measured on the values rather than judged by eye: the old
    `--faint` read as fine and measured 2.89:1 on the light page."""
    tokens = site_tokens()[theme]
    low = [f"--{text} on --{ground}: {contrast(tokens[text], tokens[ground]):.2f} < {bar}"
           for text, grounds, bar in LEGIBLE for ground in grounds
           if contrast(tokens[text], tokens[ground]) < bar]
    assert not low, f"{theme}:\n" + "\n".join(low)


def test_the_contrast_measure_is_the_standards():
    """Black on white is 21:1, a colour on itself 1:1, and #767676 the lightest grey
    that passes AA on white, so the measure cannot pass by being computed wrong."""
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#777777", "#777777") == pytest.approx(1.0)
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


def test_every_page_wears_the_site_tokens(any_page):
    """`build.py` inlines the token file at the top of each page's stylesheet."""
    name, page = any_page
    assert TOKENS.read_text(encoding="utf-8").strip() in page, name
