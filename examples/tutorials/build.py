"""Build the tutorial notebooks from their percent-format sources (WP-1545).

Each tutorial is a script, ``NN_slug.py``, and its notebook ``NN_slug.ipynb``
is generated from it (a letter after the number, as in ``02b_``, files a
notebook straight after the one it continues), executed, and committed beside it (a template in
``UNEXECUTED`` is executed and committed without its outputs).  The script is the
authority (root CLAUDE.md: a walkthrough has one, and it is ``examples/``), so
an edit goes to the ``.py`` and this file regenerates the notebook.

The source format is the subset of jupytext's percent format that a
notebook needs: ``# %%`` opens a code cell, ``# %% [markdown]`` a markdown
cell whose lines each start ``# ``.  A file opens with a marker.  A code line
``# %pip …`` is a magic kept as a comment so the script stays python; the
notebook carries it uncommented, as jupytext does.  A cell of nothing but
``%pip`` lines is never executed: a build or a test must not install anything.

    python examples/tutorials/build.py              # rebuild every notebook
    python examples/tutorials/build.py 01_quickstart  # rebuild one
    python examples/tutorials/build.py --check      # exit 1 if a notebook's cells or stamp are stale
    python examples/tutorials/build.py --prose      # write the markdown cells to _prose/ for Vale

A rebuild of unchanged code on one machine changes nothing.  Timing is not
recorded, cell ids are positional, and the notebook metadata holds only what
a reader needs.  The figures' bytes still depend on the matplotlib that drew
them, so a rebuild on another machine moves them; ``--check`` therefore
compares cells and the version stamp, never outputs.

A rebuild lists each code cell whose text output changed, with the markdown
cell under it (WP-2039).  That markdown says what the output showed, and no
check can tell whether it still does, so whoever ran the build rereads it.

A build **fails on any stderr output**.  A warning prints the absolute path of
the file that raised it, and a notebook committed with one carries the
builder's home directory.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = "[0-9][0-9]*_*.py"
#: Notebooks committed with their cells and no outputs (WP-1957).  A template
#: is run by its reader on their own data, so an output drawn from the example
#: files would read as theirs.  Its build still executes it and refuses to
#: write one that fails, and the suite executes it like any tutorial.
UNEXECUTED = ("06_your_own_data",)
_MARKER = re.compile(r"^# %%(?P<markdown> \[markdown\])?\s*$")


def sources(directory: Path = HERE) -> list[Path]:
    return sorted(directory.glob(SOURCES))


def parse(path: Path) -> list[tuple[str, str]]:
    """``(cell_type, source)`` per cell, in order."""
    cells: list[tuple[str, list[str]]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = _MARKER.match(line)
        if m:
            cells.append(("markdown" if m["markdown"] else "code", []))
            continue
        if line.lstrip().startswith(("# %%", "#%%")):
            raise ValueError(f"{path.name}:{n}: a cell marker this builder does not read")
        if not cells:
            raise ValueError(f"{path.name}:{n}: text before the first '# %%' marker")
        kind, body = cells[-1]
        if kind == "markdown" and line.strip():
            if not line.startswith("# ") and line != "#":
                raise ValueError(f"{path.name}:{n}: a markdown line must start '# '")
            line = line[2:]
        elif kind == "markdown":
            line = ""
        elif line.startswith("# %pip "):
            line = line[2:]
        body.append(line.rstrip() if kind == "markdown" else line)
    out = []
    for kind, body in cells:
        text = "\n".join(body).strip("\n")
        if not text:
            raise ValueError(f"{path.name}: an empty {kind} cell")
        out.append((kind, text))
    return out


def notebook_cells(nb) -> list[tuple[str, str]]:
    return [(c.cell_type, c.source) for c in nb.cells]


def _version() -> str:
    import rietx

    return rietx.__version__


def _notebook(path: Path):
    import nbformat

    nb = nbformat.v4.new_notebook()
    for i, (kind, text) in enumerate(parse(path)):
        make = nbformat.v4.new_markdown_cell if kind == "markdown" else nbformat.v4.new_code_cell
        nb.cells.append(make(text, id=f"{path.stem[:2]}-{i:02d}"))
    nb.metadata = {
        "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
        "language_info": {"name": "python"},
        "rietx": {"version": _version()},
    }
    return nb


def _installs(cell) -> bool:
    """A code cell that only installs packages."""
    lines = [s for s in cell.source.splitlines() if s.strip()]
    return cell.cell_type == "code" and bool(lines) and all(s.startswith("%pip ") for s in lines)


def problems(nb) -> list[str]:
    """What makes an executed notebook unfit to commit."""
    home = str(Path.home())
    found = []
    for i, cell in enumerate(nb.cells):
        for out in cell.get("outputs", []):
            if out.get("output_type") == "stream" and out.get("name") == "stderr":
                found.append(f"cell {i} wrote to stderr: {out['text'][:300]!r}")
            if out.get("output_type") == "error":
                found.append(f"cell {i} raised {out.get('ename')}: {out.get('evalue')}")
            text = out.get("text", "") + "".join(
                v for k, v in out.get("data", {}).items() if k.startswith("text/"))
            if home in text:
                found.append(f"cell {i} prints the home directory {home!r}")
    return found


def execute(path: Path):
    """The executed notebook, never written: a test calls this too."""
    from jupyter_client.kernelspec import KernelSpecManager
    from jupyter_client.manager import AsyncKernelManager
    from nbclient import NotebookClient

    from rietx._about import TELEMETRY_ENV

    nb = _notebook(path)
    held = {i: c for i, c in enumerate(nb.cells) if _installs(c)}
    nb.cells = [c for i, c in enumerate(nb.cells) if i not in held]
    env = {k: v for k, v in os.environ.items() if k != "MPLBACKEND"}  # the kernel's own, as a reader's
    env[TELEMETRY_ENV] = "0"
    env["PYTHONUTF8"] = "1"
    # The kernel is this interpreter's ipykernel.  A looked-up "python3" spec
    # can be a user-level one naming another environment's python, which then
    # executes the notebook against whatever rietx that environment holds.
    # A client handed its manager shuts the kernel down only when told to.
    km = AsyncKernelManager(kernel_name="python3",
                            kernel_spec_manager=KernelSpecManager(kernel_dirs=[]))
    # A scratch working directory, so a file a notebook writes beside itself
    # (06's results) never lands in the repository (WP-1957).  Its removal
    # must not fail a build: on Windows a kernel that has not quite exited
    # still holds its working directory.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as cwd:
        NotebookClient(nb, km=km, timeout=900, record_timing=False,
                       resources={"metadata": {"path": cwd}}).execute(env=env, cleanup_kc=True)
    nb.metadata.get("language_info", {}).pop("version", None)  # the builder's Python patch release
    for i in sorted(held):
        nb.cells.insert(i, held[i])        # unexecuted: no count, no output
    return nb


def build(path: Path) -> Path:
    import nbformat

    nb = execute(path)
    found = problems(nb)
    if found:
        raise SystemExit(f"{path.name}: not written\n  " + "\n  ".join(found))
    if path.stem in UNEXECUTED:
        nb = _notebook(path)
    out = path.with_suffix(".ipynb")
    out.write_text(nbformat.writes(nb) + "\n", encoding="utf-8", newline="\n")
    return out


def _text_outputs(cell) -> list[str]:
    """The text a code cell printed or returned: what its markdown describes."""
    texts = []
    for out in cell.get("outputs", []):
        if out.get("output_type") == "stream":
            texts.append(out.get("text", ""))
        elif "text/plain" in out.get("data", {}):
            texts.append(out["data"]["text/plain"])
    return texts


def changed_outputs(old, new) -> list[str]:
    """One line per code cell of ``new`` whose text output differs from the
    same code's in ``old``, naming the markdown cell under it.

    A cell is matched by its source, so an inserted cell moves nothing; a cell
    whose code changed counts as changed.  A figure's bytes are not compared,
    for the reason ``--check`` gives.
    """
    before: dict[str, list[list[str]]] = {}
    for cell in old.cells:
        if cell.cell_type == "code":
            before.setdefault(cell.source, []).append(_text_outputs(cell))
    found = []
    for i, cell in enumerate(new.cells):
        if cell.cell_type != "code" or not cell.get("outputs"):
            continue
        seen = before.get(cell.source)
        if seen and seen.pop(0) == _text_outputs(cell):
            continue
        under = next((c for c in new.cells[i + 1:] if c.cell_type == "markdown"), None)
        first = ((under.source.splitlines() or [""])[0] if under is not None
                 else "(no markdown follows)")
        found.append(f"Out[{cell.execution_count}] {(cell.source.splitlines() or [''])[0]!r}: "
                     f"reread {first!r}")
    return found


def prose(directory: Path = HERE, out: Path | None = None) -> list[Path]:
    """Each tutorial's markdown cells as one ``.md`` file in ``out``, for Vale.

    ``out`` defaults to ``_prose/`` beside the sources, which ``.vale.ini``
    names and git ignores.  Vale matches a section against the path it is
    given, so run it on that relative path.  That default directory is this
    builder's own, so a file a renamed tutorial left there is removed first;
    a directory a caller names is left as it was.
    """
    own = out is None
    out = out or directory / "_prose"
    out.mkdir(exist_ok=True)
    if own:
        for stale in out.glob("*.md"):
            stale.unlink()
    written = []
    for path in sources(directory):
        md = [text for kind, text in parse(path) if kind == "markdown"]
        target = out / f"{path.stem}.md"
        target.write_text("\n\n".join(md) + "\n", encoding="utf-8", newline="\n")
        written.append(target)
    return written


def check(directory: Path = HERE) -> list[str]:
    import nbformat

    stale = []
    major_minor = ".".join(_version().split(".")[:2])
    for path in sources(directory):
        nb_path = path.with_suffix(".ipynb")
        if not nb_path.exists():
            stale.append(f"{nb_path.name}: missing")
            continue
        nb = nbformat.reads(nb_path.read_text(encoding="utf-8"), as_version=4)
        if notebook_cells(nb) != parse(path):
            stale.append(f"{nb_path.name}: cells differ from {path.name}")
        if path.stem in UNEXECUTED and any(c.get("outputs") for c in nb.cells):
            stale.append(f"{nb_path.name}: a template is committed without outputs")
        stamped = nb.metadata.get("rietx", {}).get("version", "")
        if ".".join(stamped.split(".")[:2]) != major_minor:
            stale.append(f"{nb_path.name}: built by rietx {stamped or '?'}, package is {major_minor}")
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="stems to rebuild (default: all)")
    parser.add_argument("--check", action="store_true", help="report stale notebooks, build nothing")
    parser.add_argument("--prose", action="store_true",
                        help="write the markdown cells to _prose/ for Vale, build nothing")
    args = parser.parse_args(argv)
    if args.check:
        stale = check()
        for line in stale:
            print(line)
        return 1 if stale else 0
    if args.prose:
        for path in prose():
            print(f"wrote {path.relative_to(HERE.parent.parent)}")
        return 0
    chosen = [p for p in sources() if not args.names or p.stem in args.names]
    unknown = set(args.names) - {p.stem for p in chosen}
    if unknown:
        parser.error(f"no tutorial named {sorted(unknown)}")
    import nbformat

    for path in chosen:
        nb_path = path.with_suffix(".ipynb")
        old = (nbformat.reads(nb_path.read_text(encoding="utf-8"), as_version=4)
               if nb_path.exists() else nbformat.v4.new_notebook())
        out = build(path)
        print(f"wrote {out.name}")
        new = nbformat.reads(out.read_text(encoding="utf-8"), as_version=4)
        for line in changed_outputs(old, new):
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
