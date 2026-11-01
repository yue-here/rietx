"""Assemble the landing page and the pages beside it.

  python build.py            -> dist/<page>.html  everything inlined (one file a page; what the artifact shows)
  python build.py --site     -> site/             every page + img/ + data/demo.json + notebooks/, for a web server
  python build.py --ref HEAD                      the notebooks at a ref other than the newest release tag

`src/shell.html` is what every page shares: the stylesheet, the top bar, the theme control
and the footer.  Its colours and faces are `src/tokens.css`, the manual's too, inlined at
`%%TOKENS%%`.  Each page in PAGES is a `<main>` (and any script of its own) in `src/`,
dropped into the shell at `%%MAIN%%`; the table gives its title, its description and the
footer's line saying who wrote it.  `%%IMG:name%%` becomes a data URI (inline) or
`img/<name>.png` (site); `%%DEMO%%` is data/demo.json inline, or empty for the site build,
where the page fetches data/demo.json at load; `%%TRANSCRIPT%%` is data/transcript.json
when it exists, else empty and the page draws its placeholder.  `%%NOTEBOOKS%%` is the
Jupyter quickstart's rows, one per tutorial notebook at the release (see `release_tag`).
"""
import base64
import functools
import html as _html
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHELL = HERE / "src" / "shell.html"
#: The site's colours and faces, shared with the manual (WP-2021): inlined at `%%TOKENS%%`.
TOKENS = HERE / "src" / "tokens.css"


def _by_path(name: str, path: Path):
    """A module imported by path: the page builds from a checkout without rietx installed."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ABOUT = _by_path("_landing_about", REPO / "src" / "rietx" / "_about.py")
TUTORIALS = "examples/tutorials"
#: The tutorials' own glob, so a sixth notebook gets a row with no edit here.
SOURCES = _by_path("_landing_tutorials", REPO / TUTORIALS / "build.py").SOURCES
COLAB = "https://colab.research.google.com/github/"
# The JupyterLite site `pages.yml` builds to /lite/ (WP-1966), opened at the URL `smoke.mjs`
# runs.  Its notebooks sit at the site root under their file names, and they are the Pages
# commit's rather than the tag's, paired with a rietx wheel from that commit.
LITE = f"{ABOUT.DOCS_URL}/lite/notebooks/index.html?path="


# The Jupyter quickstart's notebooks come from the newest release tag, never from `main`
# (WP-1917).  `main`'s notebooks are built against the next `.dev0` and may call API that
# PyPI does not have, while a tagged notebook's `%pip install rietx` installs the release it
# was built with.  The tag is read from git, not from `pyproject.version`, which names a
# release before it is tagged (the note above `sphinx_shared.SOURCE_REF`).  With no tag the build
# refuses: falling back to `main` is the failure this exists to avoid.  The Pages workflow
# fetches tags for this; a test passes `HEAD`, since CI's shallow checkouts carry none.
def release_tag(repo: Path = REPO) -> str:
    """The newest `vX.Y.Z` tag in `repo`, by version order."""
    tags = subprocess.run(["git", "-C", str(repo), "tag", "--list", "v*"],
                          capture_output=True, text=True, check=True).stdout.split()
    versions = [(tuple(map(int, m.groups())), t) for t in tags
                if (m := re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", t))]
    if not versions:
        raise SystemExit(f"no vX.Y.Z tag in {repo}: the Jupyter quickstart links the notebooks "
                         f"at the newest release (fetch tags, or pass --ref)")
    return max(versions)[1]


@dataclass(frozen=True)
class Notebook:
    path: str       # repository-relative, e.g. examples/tutorials/01_quickstart.ipynb
    title: str      # the first markdown cell's `# ` heading
    data: bytes     # the file at the ref, byte for byte, for the site's download copy

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[1]


@functools.cache
def notebooks(ref: str, repo: Path = REPO) -> tuple[Notebook, ...]:
    """Every tutorial notebook at `ref`, in file order, read from git rather than the tree.
    Cached: the site build reads it for the downloads and again for the page's rows."""
    def git(*args: str) -> bytes:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout
    found = []
    for path in sorted(git("ls-tree", "--name-only", f"{ref}:{TUTORIALS}").decode().split()):
        if not (path.endswith(".ipynb") and fnmatch(path.removesuffix(".ipynb") + ".py", SOURCES)):
            continue
        data = git("show", f"{ref}:{TUTORIALS}/{path}")
        cell = next(c for c in json.loads(data)["cells"] if c["cell_type"] == "markdown")
        title = next(line for line in "".join(cell["source"]).splitlines() if line.startswith("# "))
        found.append(Notebook(f"{TUTORIALS}/{path}", title[2:].strip(), data))
    if not found:
        raise SystemExit(f"no tutorial notebook in {TUTORIALS} at {ref}")
    return tuple(found)


def notebook_rows(ref: str, books: tuple[Notebook, ...]) -> str:
    """The Jupyter quickstart's list: each notebook's title, then Read, JupyterLite, Colab, Download."""
    repo = ABOUT.REPO_URL.removeprefix("https://github.com/")
    rows = []
    for nb in books:
        stem = nb.name.removesuffix(".ipynb")
        rows.append(
            f'<li><span class="nb-title">{_html.escape(nb.title)}</span><span class="nb-links">'
            f'<a href="{ABOUT.DOCS_URL}/using/tutorials/{stem}.html">Read</a>'
            f'<a href="{LITE}{nb.name}">JupyterLite</a>'
            f'<a href="{COLAB}{repo}/blob/{ref}/{nb.path}">Colab</a>'
            f'<a href="notebooks/{nb.name}" download>Download</a></span></li>')
    return "\n".join(rows)


@dataclass(frozen=True)
class Page:
    title: str
    description: str
    note: str          # the footer's line: who wrote the page, Claude named in every one


_YUE = '<a href="https://github.com/yue-here">@yue-here</a>'
#: Every page the site serves at its root, keyed by its file name in `src/` and in the output.
PAGES = {
    "index.html": Page(
        "rietx",
        "rietx: Rietveld refinement of powder diffraction data, driven from Python and by agents.",
        f"Page written by Claude with edits by {_YUE}."),
    "why.html": Page(
        "Why rietx?",
        "Why rietx exists: a note from its author on writing scientific software with AI agents, and for them.",
        f"Essay by {_YUE}. Page built by Claude."),
}
IMAGES = {"fap-light": "img/fap-light.png", "fap-dark": "img/fap-dark.png",
          "gui-light": "img/gui-history-light.png", "gui-dark": "img/gui-history-dark.png"}
DEMO = HERE / "data" / "demo.json"
TRANSCRIPT = HERE / "data" / "transcript.json"
# Nothing from the contributor's bundle that names a file, a specimen, a machine or a person
# may reach the page. Tokens are substrings; the regexes catch the filename grammar itself.
# **Matched case-insensitively**, because half of what this guards is prose cut by hand: a
# filename says `sio2` and `etoh` while a sentence says `SiO2` and `EtOH`.  A token written in
# one case would have passed the other straight through — which is the only failure this file
# has.  The people arm is now empty (WP-1331): the caption credits every one of them by name,
# and a person the page thanks cannot also be a token that fails the build.  What keeps a
# machine path out is `/Users/`, `/Volumes/` and LEAK_RE, none of which ever moved.
LEAK = ("8pptn0", "etoh", "sio2", "0523",                       # specimen code, sample tags, acquisition-date prefix
        "02pct", "solgel", "8reg0", "drypack", "ultrathin",      # sibling specimens' tags
        "splitter",                                              # the reference's own parser
        "/Users/", "/Volumes/")                                  # machine paths
LEAK_RE = (r"_I\d+_", r"\b\d{10}_", r"\b\d{8}_CuO")           # scan token, acquisition timestamp, run-folder date

# The support phases are kept out a rank earlier and are deliberately NOT tokens here: a
# denylist publishes what it denies, and these names would be in the repository either way.
# `build_demo.phase_columns` takes them from the bundle's own header instead and ships
# them as "support n", so no build of this page has ever held one (WP-1331).

# base64 is drawn from [A-Za-z0-9+/], so a four-character token turns up inside a
# 200 kB inlined PNG by chance — measured: `etoh` and `sio2` both do, and `0523`
# would have without the case fold.  A blob carries no name, so it is not scanned.
BLOB = re.compile(r"base64,[A-Za-z0-9+/=]+")

def leaks(text: str) -> list[str]:
    """Every leak token or pattern found in `text`, in list order; empty means clean."""
    text = BLOB.sub("base64,", text)
    lowered = text.lower()
    found = [t for t in LEAK if t.lower() in lowered]
    for pat in LEAK_RE:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            found.append(m.group(0))
    return found

def data_uri(p: Path) -> str:
    mime = "image/svg+xml" if p.suffix == ".svg" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"

# `src/index.html` is authored as an artifact **fragment**: the Artifact runtime wraps it in
# a document and supplies the charset and the viewport, and refuses a file that brings its
# own `<html>`.  A web server supplies neither, so the site build adds the skeleton — the
# same one the runtime does, `<title>` and `<style>` at the top of `<body>` included, which
# the HTML parser hoists.  Measured: without the charset a server that does not say utf-8
# renders every `·`, `θ` and `α` on the page as mojibake, and without the viewport a phone
# lays it out 980 px wide.  The page's own CSS is complete (box-sizing, color-scheme, body
# background and font), so the skeleton carries no reset.
DOCUMENT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body>
{body}</body>
</html>
"""


def assemble(site: bool, name: str = "index.html", ref: str | None = None) -> str:
    """One page; `ref` is where its notebooks are read, the newest release tag when None."""
    page = PAGES[name]
    html = SHELL.read_text(encoding="utf-8")
    html = html.replace("%%TOKENS%%", TOKENS.read_text(encoding="utf-8").strip())
    html = html.replace("%%MAIN%%", (HERE / "src" / name).read_text(encoding="utf-8").strip())
    html = (html.replace("%%TITLE%%", page.title).replace("%%DESCRIPTION%%", page.description)
            .replace("%%NOTE%%", page.note))
    fav = HERE / "src" / "favicon.svg"
    html = html.replace("%%FAVICON%%", "favicon.svg" if site else data_uri(fav))
    for name, rel in IMAGES.items():
        html = html.replace(f"%%IMG:{name}%%", rel if site else data_uri(HERE / rel))
    if not site and "%%DEMO%%" in html and not DEMO.exists():
        # The inline build is the one-file artifact, whose whole point is the payload;
        # absent, say so rather than raising FileNotFoundError from inside a replace.
        # (`--site` is the build where absent is a legitimate state — see __main__.)
        raise SystemExit(f"no payload at {DEMO} — the inline build needs one; "
                         f"`build.py --site` is the build that does not")
    if "%%DEMO%%" in html:
        html = html.replace("%%DEMO%%", "" if site else DEMO.read_text(encoding="utf-8"))
    tr = TRANSCRIPT.read_text(encoding="utf-8").strip() if TRANSCRIPT.exists() else ""
    html = html.replace("%%TRANSCRIPT%%", tr)
    if "%%NOTEBOOKS%%" in html:
        ref = ref or release_tag()
        html = html.replace("%%NOTEBOOKS%%", notebook_rows(ref, notebooks(ref)))
    assert "%%" not in html, f"unfilled placeholder in {name}"
    bad = leaks(html)
    if bad:
        raise SystemExit(f"leak: {bad[:5]} in {name}")
    return DOCUMENT.format(body=html) if site else html

if __name__ == "__main__":
    site = "--site" in sys.argv
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else release_tag()
    if site:
        out = HERE / "site"
        shutil.rmtree(out, ignore_errors=True)
        (out / "img").mkdir(parents=True)
        (out / "data").mkdir()
        for rel in IMAGES.values():
            shutil.copy(HERE / rel, out / rel)
        shutil.copy(HERE / "src" / "favicon.svg", out / "favicon.svg")
        # The payload is committed (README § The payload), so absence means someone
        # removed it.  Still not an error: the page renders without the animation
        # rather than failing the whole site build.
        if DEMO.exists():
            shutil.copy(DEMO, out / "data" / "demo.json")
        if TRANSCRIPT.exists():
            shutil.copy(TRANSCRIPT, out / "data" / "transcript.json")
        # The downloads are the notebooks at the same ref as the Colab links, so the two agree.
        (out / "notebooks").mkdir()
        for nb in notebooks(ref):
            (out / "notebooks" / nb.name).write_bytes(nb.data)
        for name in PAGES:
            (out / name).write_text(assemble(True, name, ref), encoding="utf-8")
    else:
        out = HERE / "dist"
        out.mkdir(exist_ok=True)
        for name in PAGES:
            (out / name).write_text(assemble(False, name, ref), encoding="utf-8")
    print("wrote", out)
