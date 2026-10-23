"""The tutorial notebooks execute, and each committed one is its source (WP-1545).

A tutorial's authority is its percent-format script in `examples/tutorials/`,
and `build.py` there generates, executes and commits the `.ipynb` beside it.
These tests find the tutorials by glob, so adding one needs no edit here.

**Each notebook executes in a real kernel on every push.**  A plain script run
would exercise none of the display (WP-1544), and per-push execution is the
whole value of an example guard (`test_examples.py`'s docstring).  So each
notebook is sized to fit the fast tier.  The executed notebook is never written:
outputs move with the machine that drew them, and the committed ones are the
builder's to refresh.

**CI executes them on its newest Python leg alone** (WP-1547), with the guide
scripts and the manual builds: `tests/documentation.py` holds the switch and
says what that trades.  The nightly executes them on 3.13, on Linux, Windows
and macOS.
"""

from __future__ import annotations

import html
import importlib.util
import re
import shutil
from pathlib import Path

import pytest

from tests import documentation

nbformat = pytest.importorskip("nbformat")
pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

REPO_ROOT = Path(__file__).resolve().parent.parent
TUTORIALS = REPO_ROOT / "examples" / "tutorials"

_spec = importlib.util.spec_from_file_location("tutorials_build", TUTORIALS / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

SOURCES = build.sources()

#: The tutorial whose first fit `docs/landing/src/index.html` shows, code and output.
LANDING_TUTORIAL = "02_simple_rietveld"
LANDING_PAGE = REPO_ROOT / "docs" / "landing" / "src" / "index.html"


def _landing_box() -> tuple[str, str]:
    """The landing page's code box and output panel, as plain text."""
    section = re.search(r'<section[^>]*id="example".*?</section>',
                        LANDING_PAGE.read_text(encoding="utf-8"), re.S)
    assert section, f"{LANDING_PAGE.name} has no example section"
    pres = re.findall(r"<pre[^>]*>(.*?)</pre>", section.group(0), re.S)
    assert len(pres) == 2, f"the example section holds {len(pres)} <pre> blocks, not code and output"
    code, out = (html.unescape(re.sub(r"<[^>]+>", "", pre)) for pre in pres)
    return code, out


def _flat(text: str) -> str:
    return " ".join(text.split())


def _printed(cells) -> str:
    """Everything the code cells printed, in order."""
    return "".join(o.get("text", "") for c in cells if c.cell_type == "code" for o in c.outputs)


def _committed(path: Path):
    return nbformat.reads(path.with_suffix(".ipynb").read_text(encoding="utf-8"), as_version=4)


def test_there_are_tutorials():
    """The glob below finds something, or every parametrised test is vacuous."""
    assert SOURCES, f"no {build.SOURCES} under {TUTORIALS}"


@documentation.elsewhere
@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_tutorial_executes_clean(path):
    """No error, no stderr, no home path, and a figure where a cell plots.

    A rietx figure shows through its own display hook whatever the backend,
    so the suite's `MPLBACKEND=Agg` (conftest) does not hide one.  What hides
    one is a cell that discards it, such as a trailing `;` (WP-1544)."""
    nb = build.execute(path)
    assert build.problems(nb) == []
    last = [(c, c.source.splitlines()[-1]) for c in nb.cells if c.cell_type == "code"]
    plots = [c for c, line in last if ".plot(" in line]
    assert plots, f"{path.stem} ends no cell on a plot, so this test checks no figure"
    # a structure figure shows through its own display hook too (WP-1957)
    for cell in plots + [c for c, line in last if "render_structure(" in line]:
        kinds = {k for out in cell.outputs for k in out.get("data", {})}
        assert "image/png" in kinds, f"{path.stem}: {cell.source.splitlines()[-1]!r} showed no image"
    if path.stem == LANDING_TUTORIAL:
        printed = _flat(_printed(nb.cells))
        out = _landing_box()[1]
        # a diagnostic prints as `warning[CODE]: message` (WP-1985)
        codes = re.findall(r"\[([A-Z_]+)\]:", out)
        assert codes, "found no diagnostic code in the landing page's output panel"
        quoted = [_flat(out.splitlines()[0]), *codes]  # the status line, then each code
        missing = [code for code in quoted if code not in printed]
        assert missing == [], f"{path.stem} no longer prints {missing}, which the landing page quotes"


def test_the_landing_box_is_the_tutorial():
    """The landing page's code box is the tutorial's first fit, line for line and
    in order, less only import lines.  Every stretch of its output panel between
    cuts (`…`) is in that cell's committed output, in order, and a panel ending
    without a cut ends where the output does.  So the published numbers are the
    ones the builder drew.

    The box names bare files where the tutorial reads the copies in the wheel."""
    code, out = _landing_box()
    nb = _committed(TUTORIALS / f"{LANDING_TUTORIAL}.py")
    cell = next(c for c in nb.cells if c.cell_type == "code" and "ref.fit(" in c.source)
    box = [_flat(ln) for ln in code.splitlines() if ln.strip()]
    source = [_flat(ln.replace("examples_dir() / ", "")) for ln in cell.source.splitlines()
              if ln.strip()]
    kept = [ln for ln in source if ln in box or not ln.startswith(("import ", "from "))]
    assert kept == box, "the landing page's code box is not the tutorial's fit cell"
    printed = _flat(_printed([cell]))
    pieces = [p for p in map(_flat, out.split("…")) if p]
    stale, at = [], 0
    for piece in pieces:
        found = printed.find(piece, at)
        if found < 0:
            stale.append(piece)
        else:
            at = found + len(piece)
    assert stale == [], "the landing page's output panel no longer matches the tutorial"
    if not out.rstrip().endswith("…"):
        assert printed.endswith(pieces[-1]), "the tutorial prints more than the panel shows, uncut"


def test_committed_notebooks_are_their_sources():
    """Cells equal the script's, and the stamp is this package's major.minor."""
    assert build.check() == []


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_committed_outputs_are_fit_to_publish(path):
    assert build.problems(_committed(path)) == []


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.stem)
def test_a_notebook_opens_by_installing_and_never_ran_it(path):
    """A reader's first cell installs rietx; a build must not install anything."""
    code = [c for c in _committed(path).cells if c.cell_type == "code"]
    assert code[0].source.startswith("%pip install "), code[0].source
    assert code[0].execution_count is None and code[0].outputs == []


def test_parse_uncomments_a_pip_magic(tmp_path):
    src = tmp_path / "00_pip.py"
    src.write_text("# %%\n# %pip install rietx\n", encoding="utf-8", newline="\n")
    assert build.parse(src) == [("code", "%pip install rietx")]


def test_the_readme_lists_every_tutorial():
    readme = (TUTORIALS / "README.md").read_text(encoding="utf-8")
    missing = [p.with_suffix(".ipynb").name for p in SOURCES
               if p.with_suffix(".ipynb").name not in readme]
    assert missing == [], f"examples/tutorials/README.md does not list {missing}"


#: A link into the published manual, its build and its page path apart.
MANUAL_LINK = re.compile(r"https://rietx\.org/docs/([^/\s]+)/([^\s#)>\]\"'`]*)")
MANUAL_SOURCE = REPO_ROOT / "docs" / "docs"


def _bad_manual_links(text: str) -> list[str]:
    """The manual links in `text` that name no page, or name the dev build."""
    bad = []
    for build_name, page in MANUAL_LINK.findall(text):
        if build_name != "stable":
            bad.append(f"{build_name}/{page}: links the {build_name} build; link docs/stable/")
        elif not page.endswith(".html") or not (MANUAL_SOURCE / page).with_suffix(".md").is_file():
            bad.append(f"stable/{page}: no docs/docs/{page.removesuffix('.html')}.md")
    return bad


def test_a_tutorial_links_only_pages_the_manual_has():
    """Every `https://rietx.org/docs/stable/<path>.html` a tutorial's source
    links names an existing `docs/docs/<path>.md`, anchor aside.  A link to
    `docs/dev/` is refused: the dev build moves under a reader."""
    linked = {p.stem: p.read_text(encoding="utf-8") for p in SOURCES}
    assert any(MANUAL_LINK.search(text) for text in linked.values()), \
        "no tutorial links the manual, so this test checks no link"
    bad = [f"{stem}: {b}" for stem, text in linked.items() for b in _bad_manual_links(text)]
    assert bad == []


def test_the_link_check_sees_a_missing_page_and_the_dev_build():
    text = ("[ok](https://rietx.org/docs/stable/guides/check.html#read-the-pattern-diagnostics) "
            "[gone](https://rietx.org/docs/stable/guides/nowhere.html) "
            "[dev](https://rietx.org/docs/dev/guides/check.html)")
    assert _bad_manual_links(text) == [
        "stable/guides/nowhere.html: no docs/docs/guides/nowhere.md",
        "dev/guides/check.html: links the dev build; link docs/stable/"]


def test_check_sees_a_stale_notebook(tmp_path):
    """The guard can fail: a source edited without a rebuild is reported."""
    source = SOURCES[0]
    shutil.copy(source, tmp_path / source.name)
    shutil.copy(source.with_suffix(".ipynb"), tmp_path / source.with_suffix(".ipynb").name)
    assert build.check(tmp_path) == []
    copy = tmp_path / source.name
    copy.write_text(copy.read_text(encoding="utf-8") + "\n# %%\nprint('new')\n",
                    encoding="utf-8", newline="\n")
    assert build.check(tmp_path) == [f"{source.stem}.ipynb: cells differ from {source.name}"]



@pytest.mark.parametrize("stem", build.UNEXECUTED)
def test_a_template_is_committed_without_outputs(stem):
    """Its reader runs it on their own data, so the committed copy carries no
    output from the example files (WP-1957).  The suite still executes it,
    in test_tutorial_executes_clean."""
    code = [c for c in _committed(TUTORIALS / f"{stem}.py").cells if c.cell_type == "code"]
    assert code and all(c.outputs == [] and c.execution_count is None for c in code)


def test_check_sees_a_template_with_outputs(tmp_path):
    """The guard can fail: a template committed executed is reported."""
    import nbformat
    stem = build.UNEXECUTED[0]
    shutil.copy(TUTORIALS / f"{stem}.py", tmp_path / f"{stem}.py")
    nb = _committed(TUTORIALS / f"{stem}.py")
    assert build.check(tmp_path) == [f"{stem}.ipynb: missing"]
    cell = next(c for c in nb.cells if c.cell_type == "code" and not c.source.startswith("%pip"))
    cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text="from the example\n")]
    (tmp_path / f"{stem}.ipynb").write_text(nbformat.writes(nb), encoding="utf-8")
    assert build.check(tmp_path) == [f"{stem}.ipynb: a template is committed without outputs"]


def test_a_rebuild_names_the_markdown_under_a_changed_output():
    """A cell whose text output moved is listed with the markdown that
    describes it; an inserted cell and an unchanged one are not (WP-2037)."""
    v4 = nbformat.v4

    def nb(*cells):
        return v4.new_notebook(cells=list(cells))

    def code(source, text, n):
        out = v4.new_output("execute_result", data={"text/plain": text}, execution_count=n)
        return v4.new_code_cell(source, outputs=[out], execution_count=n)

    old = nb(code("a", "1", 1), v4.new_markdown_cell("A is one."),
             code("b", "2", 2), v4.new_markdown_cell("B is two.\nMore."))
    new = nb(code("z", "0", 1), v4.new_markdown_cell("Z is new."),
             code("a", "1", 2), v4.new_markdown_cell("A is one."),
             code("b", "3", 3), v4.new_markdown_cell("B is two.\nMore."))
    assert build.changed_outputs(old, new) == [
        "Out[1] 'z': reread 'Z is new.'",
        "Out[3] 'b': reread 'B is two.'"]
    assert build.changed_outputs(new, new) == []


def test_prose_writes_only_the_markdown(tmp_path):
    """``--prose`` hands Vale the markdown cells and none of the code."""
    (tmp_path / "01_x.py").write_text(
        "# %% [markdown]\n# # Title\n#\n# Some words.\n# %%\nx = 1\n# %% [markdown]\n# More.\n",
        encoding="utf-8", newline="\n")
    (written,) = build.prose(tmp_path, tmp_path / "out")
    assert written.read_text(encoding="utf-8") == "# Title\n\nSome words.\n\nMore.\n"


def test_problems_sees_stderr_and_a_home_path():
    v4 = nbformat.v4
    cell = v4.new_code_cell("x", outputs=[
        v4.new_output("stream", name="stderr", text="UserWarning: careful\n"),
        v4.new_output("stream", name="stdout", text=f"read {Path.home() / 'data.xy'}\n"),
    ])
    found = build.problems(v4.new_notebook(cells=[cell]))
    assert len(found) == 2 and "stderr" in found[0] and "home directory" in found[1]


def test_parse_refuses_what_it_cannot_round_trip(tmp_path):
    bad = tmp_path / "00_bad.py"
    bad.write_text("import rietx\n# %%\nx = 1\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="before the first"):
        build.parse(bad)
    bad.write_text("# %% [markdown]\nno hash\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="must start"):
        build.parse(bad)
    bad.write_text("# %% [markdown]\n# text\n# %% A titled cell\nx = 1\n",
                   encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="does not read"):
        build.parse(bad)
