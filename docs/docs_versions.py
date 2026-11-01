# The hosted manual's versions, assembled under the site's /docs/ (WP-1979).
#
# GitHub Pages deploys one fresh site per run, so nothing from an earlier
# deploy survives.  Each release therefore stores its own built tree as an
# asset on its GitHub release: release.yml builds `docs/docs/` at the tag,
# after PyPI has the package, and attaches `<dist>-docs-X.Y.Z.tar.gz`.
# pages.yml builds `main`'s tree into <site>/docs/dev/ and then runs this
# script, which
#
# - keeps the newest release of each of the last KEEP_MINORS minors, each at
#   docs/X.Y/, and copies the newest of them to docs/stable/;
# - writes docs/switcher.json, which every version's menu reads, and
#   docs/index.html, which sends /docs/ to stable/ (to dev/ before any
#   release carries a tree);
# - copies that tree's llms.txt to the site root;
# - writes a redirect stub at each page the retired old tree (`docs/manual/`)
#   published, from RETIRED, so its URLs keep working.
#
# Pruning is the same step: a minor outside the newest KEEP_MINORS is simply
# not fetched.  One version of the new tree measured 7.4 MB on 2026-10-16, and
# the full manual is projected at about 21 MB, so eight trees stay far inside
# Pages' 1 GB.
#
#     python docs/docs_versions.py site

import json as _json
import os as _os
import re as _re
import shutil as _shutil
import sys as _sys
import tarfile as _tarfile
import tempfile as _tempfile
import urllib.request as _request
from html import escape as _escape
from pathlib import Path as _Path

# `docs_version`, the version -> directory mapping, is the package's (WP-1986),
# because the GUI builds the manual's address from it too; `sphinx_shared` and
# the tests read it through here.
from rietx._about import DIST_NAME, DOCS_URL, REPO_URL, docs_version  # noqa: F401

#: How many minor releases stay reachable beside dev (WP-1979).
KEEP_MINORS = 6

#: Every page the old tree (`docs/manual/`, retired by WP-1986) published on
#: 2026-10-16, as a path from the site root, and the one it gained after
#: (`02b_steering_a_refinement`, 2026-10-19), which the landing page links.
#: Each has a row in RETIRED, so none of those URLs 404s
#: (tests/test_docs_versions.py).
OLD_PAGES = """
background corrections engines estimation forward-model indexing intensities
manual method microstructure parameterisation peak-positions profiles
representation-analysis superspace
using/agents using/cli using/compatibility using/concepts using/constraints
using/data using/exports using/files using/first-refinement using/glossary
using/gui-guide using/gui-power using/gui-quickstart using/history
using/indexing using/install using/model using/qpa using/quickstart
using/recipe using/refining using/report using/results using/series
using/skill
using/tutorials/01_quickstart using/tutorials/02_simple_rietveld
using/tutorials/02b_steering_a_refinement
using/tutorials/03_peaks_indexing_lebail
using/tutorials/04_peak_shape_and_microstructure
using/tutorials/05_sequential_fits using/tutorials/06_your_own_data
""".split()

#: A retired old-tree page and the new-tree page that replaces it, both
#: without `.html`; the new one may carry a `#heading`.  WP-1986 retired the
#: whole old tree at once (2026-10-22): its Part 2 pages were already the new
#: tree's Theory chapters, its front page goes to the new one, Part 1 maps
#: chapter by chapter, and the tutorials render under Start.
RETIRED: dict[str, str] = {
    "manual": "index",
    "background": "theory/background",
    "corrections": "theory/corrections",
    "engines": "theory/engines",
    "estimation": "theory/estimation",
    "forward-model": "theory/forward-model",
    "indexing": "theory/indexing",
    "intensities": "theory/intensities",
    "method": "theory/method",
    "microstructure": "theory/microstructure",
    "parameterisation": "theory/parameterisation",
    "peak-positions": "theory/peak-positions",
    "profiles": "theory/profiles",
    "representation-analysis": "theory/representation-analysis",
    "superspace": "theory/superspace",
    "using/agents": "reference/programs",
    "using/cli": "reference/cli",
    "using/compatibility": "reference/compatibility",
    "using/concepts": "concepts/fit",
    "using/constraints": "reference/parameter-table#ties",
    "using/data": "reference/data",
    "using/exports": "reference/exports",
    "using/files": "reference/pattern-files",
    "using/first-refinement": "start/first-fit",
    "using/glossary": "reference/parameters",
    "using/gui-guide": "reference/gui-guide",
    "using/gui-power": "reference/gui-power",
    "using/gui-quickstart": "start/gui-quickstart",
    "using/history": "reference/history",
    "using/indexing": "reference/indexing",
    "using/install": "start/install",
    "using/model": "reference/parameter-table",
    "using/qpa": "reference/qpa",
    "using/quickstart": "start/tutorials",
    "using/recipe": "reference/recipe",
    "using/refining": "reference/refinement",
    "using/report": "reference/report",
    "using/results": "reference/result",
    "using/series": "reference/series",
    "using/skill": "reference/agents",
    # The notebooks are copied in at build (`sphinx_shared.copy_tutorials`).
    "using/tutorials/01_quickstart": "start/tutorials/01_quickstart",
    "using/tutorials/02_simple_rietveld": "start/tutorials/02_simple_rietveld",
    "using/tutorials/02b_steering_a_refinement": "start/tutorials/02b_steering_a_refinement",
    "using/tutorials/03_peaks_indexing_lebail": "start/tutorials/03_peaks_indexing_lebail",
    "using/tutorials/04_peak_shape_and_microstructure":
        "start/tutorials/04_peak_shape_and_microstructure",
    "using/tutorials/05_sequential_fits": "start/tutorials/05_sequential_fits",
    "using/tutorials/06_your_own_data": "start/tutorials/06_your_own_data",
}

_TAG = _re.compile(r"v(\d+)\.(\d+)\.(\d+)")
#: The start of a markdown link target that is relative to its file.
_RELATIVE_LINK = _re.compile(r"\]\((?![a-z][a-z0-9+.-]*:|/|#)")


def asset_name(version: str) -> str:
    """The release asset holding one release's built tree."""
    return f"{DIST_NAME}-docs-{version}.tar.gz"


def kept_releases(releases: list[dict]) -> list[tuple[str, str]]:
    """(minor, version) to host, newest first, from the GitHub releases API.

    Drafts, prereleases and any release without a tree are skipped, so the
    releases cut before WP-1979 drop out by themselves.
    """
    newest: dict[tuple[int, int], tuple[int, str]] = {}
    for release in releases:
        match = _TAG.fullmatch(release["tag_name"])
        if release["draft"] or release["prerelease"] or not match:
            continue
        version = release["tag_name"][1:]
        if asset_name(version) not in {asset["name"] for asset in release["assets"]}:
            continue
        major, minor, patch = (int(part) for part in match.groups())
        if (major, minor) not in newest or patch > newest[major, minor][0]:
            newest[major, minor] = (patch, version)
    minors = sorted(newest, reverse=True)[:KEEP_MINORS]
    return [(f"{major}.{minor}", newest[major, minor][1]) for major, minor in minors]


def switcher_entries(minors: list[str]) -> list[dict]:
    """The version menu: dev, then each kept minor with the newest as stable.

    `version` is what a build's `version_match` names, so the stable entry
    carries its minor and both stable/ and docs/X.Y/ mark it as current.  The
    theme shows its banner on any version that is not the `preferred` one.
    """
    entries = [{"name": "dev", "version": "dev", "url": "/docs/dev/"}]
    for index, minor in enumerate(minors):
        if index == 0:
            entries.append({"name": f"{minor} (stable)", "version": minor,
                            "url": "/docs/stable/", "preferred": True})
        else:
            entries.append({"name": minor, "version": minor, "url": f"/docs/{minor}/"})
    return entries


def redirect_page(url: str, canonical: str) -> str:
    """An HTML stub that sends a reader on, for a host with no redirects.

    A meta refresh drops the `#fragment` the reader arrived with, so where the
    target names no heading of its own a script carries it over first.  That is
    what keeps an installed release's help links landing on their section:
    their anchors are `<theory chapter>.html#<heading>` at the site root, and
    each Theory chapter kept its heading ids when it moved under /docs/.  The
    refresh stays as the fallback for a reader without scripts.
    """
    forward = ""
    if "#" not in url:
        target = _json.dumps(url).replace("<", "\\u003c")
        forward = f"<script>location.replace({target} + location.hash)</script>\n"
    return ('<!doctype html>\n<meta charset="utf-8">\n'
            + forward +
            f'<meta http-equiv="refresh" content="0; url={_escape(url)}">\n'
            f'<link rel="canonical" href="{_escape(canonical)}">\n'
            f'<title>Moved</title>\n<p>This page has moved to <a href="{_escape(url)}">'
            f'{_escape(canonical)}</a>.</p>\n')


def assemble(site: _Path, kept: list[tuple[str, str]], fetch) -> None:
    """Lay out <site>/docs/ around the dev tree already built there.

    `fetch(version)` returns the path of that release's tarball.
    """
    docs = site / "docs"
    if not (docs / "dev" / "index.html").is_file():
        raise SystemExit(f"{docs / 'dev'} holds no built tree; build main's first")
    # A second run over the same site replaces each tree rather than merging into it.
    for name in [minor for minor, _ in kept] + ["stable"]:
        _shutil.rmtree(docs / name, ignore_errors=True)
    for minor, version in kept:
        with _tarfile.open(fetch(version)) as archive:
            archive.extractall(docs / minor, filter="data")
    if kept:
        _shutil.copytree(docs / kept[0][0], docs / "stable")
    minors = [minor for minor, _ in kept]
    (docs / "switcher.json").write_text(
        _json.dumps(switcher_entries(minors), indent=1) + "\n", encoding="utf-8")
    target = "stable" if kept else "dev"
    (docs / "index.html").write_text(
        redirect_page(f"{target}/", f"{DOCS_URL}/docs/{target}/"), encoding="utf-8")
    # The llms.txt proposal puts the file at the site's root.  It is the hosted
    # tree's own with its links rebased onto that tree, and dev's until a
    # release carries one (WP-1980, docs/markdown_twin.py).
    tree = target if (docs / target / "llms.txt").is_file() else "dev"
    if (docs / tree / "llms.txt").is_file():
        text = (docs / tree / "llms.txt").read_text(encoding="utf-8")
        (site / "llms.txt").write_text(
            _RELATIVE_LINK.sub(f"](/docs/{tree}/", text), encoding="utf-8")
    for old, new in RETIRED.items():
        page, _, heading = new.partition("#")
        # A page retired on main is in dev at once and in stable only from the next
        # release, so until then the stub sends the reader to dev.
        tree = target if (docs / target / f"{page}.html").is_file() else "dev"
        path = f"/docs/{tree}/{page}.html" + (f"#{heading}" if heading else "")
        stub = site / f"{old}.html"
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(redirect_page(path, DOCS_URL + path), encoding="utf-8")


def main(site: _Path) -> None:
    # Newest first, so one page of 100 holds every minor worth keeping.  The
    # token only lifts the API's rate limit.  A download goes without it, since
    # it redirects to a storage host that refuses a second credential.
    api = REPO_URL.replace("https://github.com/", "https://api.github.com/repos/")
    headers = {"Accept": "application/vnd.github+json"}
    if _os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {_os.environ['GITHUB_TOKEN']}"
    request = _request.Request(f"{api}/releases?per_page=100", headers=headers)
    with _request.urlopen(request) as response:
        releases = _json.load(response)
    kept = kept_releases(releases)
    with _tempfile.TemporaryDirectory() as scratch:
        def fetch(version: str) -> _Path:
            path = _Path(scratch) / asset_name(version)
            url = f"{REPO_URL}/releases/download/v{version}/{asset_name(version)}"
            with _request.urlopen(url) as response, path.open("wb") as out:
                _shutil.copyfileobj(response, out)
            return path

        assemble(site, kept, fetch)
    print("docs/: dev" + "".join(f", {minor} ({version})" for minor, version in kept))


if __name__ == "__main__":
    main(_Path(_sys.argv[1]))
