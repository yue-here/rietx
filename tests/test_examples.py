"""The `examples/` walkthroughs are executed, not just linted (WP-1067).

`examples/` is the **one authority** for a worked walkthrough: the manual
`{literalinclude}`s these scripts rather than retyping them, so what a reader
of `start/first-fit.md` sees is this file, and this test is what makes it a
script that runs.  Before WP-1067 nothing in `tests/` executed either script —
ruff linted them and that was all, while README carried a second, unguarded
copy of the same walkthrough.

**Where the outputs go.** Each script writes its plots beside itself
(`examples/nac_fit.png`, `examples/srm660c_fit.png`, `…_vlm.png`,
`…_fit.html`), from a path built off its own `__file__`, so running it
from a temporary cwd would not redirect anything.  This runner therefore accepts the
write; those names are gitignored.  Its own data paths are `__file__`-relative
too, so the scripts are run in place.

**Why these are not marked `slow`.**  Per-push execution is the whole value
of the guard — a broken walkthrough should fail on the push that broke it, not
in the nightly — so they run in the fast suite.  They refine the same real data
as the acceptance suites, which is where the *numbers* are pinned (this test
asserts that the script ran, never what it found — one authority per fact).

**What they cost, and where they run.**  Measured 2026-10-21 (WP-2019; `[dev]`,
Linux x86-64, Python 3.12, this file alone at `-n 4`): the 23 guide scripts
sum to 614 s, median 13.8 s, the slowest `interval` 104 s, `hold` 85 s and
`qpa` 84 s.  The rest of the file sums to about 113 s: `switching.py` 36 s,
`skill_worked_default.py` 35 s, `nac_11bm.py` and `srm660c_lab.py` 11 s each,
the three structure pictures 20 s.  WP-1067's 3.5 s and 3.3 s, on darwin/arm64
before the guides existed, were the two walkthroughs alone.  So the guides
execute on CI's newest per-push leg only, with the tutorials and the manual
builds (`tests/documentation.py` says what that trades), and the walkthroughs
on every leg.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests import documentation

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"


def _run(script: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """As a subprocess, because `python examples/x.py` is what a reader types."""
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / script)],
        capture_output=True,
        text=True,
        # The scripts print χ and Å.  A reader's *interactive* console prints
        # them on every platform (PEP 528 made the Windows console UTF-8);
        # only a captured pipe falls back to the ANSI code page (cp1252) and
        # dies encoding χ — so pin the pipe to what the console already does,
        # on both ends of it.
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", **(env or {})},
        timeout=900,  # a runaway guard, not a timer (tests/CLAUDE.md): ~250x the measured cost
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"{script} exited {result.returncode}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    assert "Traceback" not in result.stderr, f"{script} wrote a traceback:\n{result.stderr}"
    return result


def _timestamps(*artefacts: str) -> dict[str, int | None]:
    return {
        name: (EXAMPLES / name).stat().st_mtime_ns if (EXAMPLES / name).exists() else None
        for name in artefacts
    }


@pytest.fixture(scope="module")
def nac_run():
    """One run, two assertions.  Module-scoped with an `xdist_group` on every
    consumer, or a second worker reruns the whole script (tests/CLAUDE.md)."""
    before = _timestamps("nac_fit.png")
    return _run("nac_11bm.py").stdout, before


@pytest.fixture(scope="module")
def srm660c_run():
    before = _timestamps("srm660c_fit.png", "srm660c_fit.html")
    return _run("srm660c_lab.py").stdout, before


@pytest.mark.xdist_group("example-nac")
def test_nac_11bm_example_runs(nac_run):
    """The first-refinement walkthrough: read, Le Bail, add the impurity the report
    flagged, Rietveld, report, history."""
    out, _ = nac_run
    for marker in ("Le Bail:", "Rietveld:", "FitReport:", "best node by Rwp:"):
        assert marker in out, f"nac_11bm.py printed no {marker!r} line:\n{out}"


@pytest.mark.xdist_group("example-srm660c")
def test_srm660c_lab_example_runs(srm660c_run):
    """The lab-data walkthrough: auto background, displacement, FCJ, all three
    report layers, the VLM montage and the HTML viewer."""
    out, _ = srm660c_run
    for marker in ("Rwp", "wrote"):
        assert marker in out, f"srm660c_lab.py printed no {marker!r} line:\n{out}"


@pytest.fixture(scope="module")
def skill_worked_default_run():
    return _run("skill_worked_default.py").stdout


@pytest.mark.xdist_group("example-skill-worked-default")
def test_skill_worked_default_example_runs(skill_worked_default_run):
    """The skill body's § 10 block (WP-1906), which an agent copies as written:
    it must converge on a real lab pattern and print the summary its checks
    read.  `tests/test_skill.py` holds this script equal to the body."""
    out = skill_worked_default_run
    for marker in ("RefinementResult: converged", "Refinement.summary:",
                   "deliverable: structure"):
        assert marker in out, f"skill_worked_default.py printed no {marker!r} line:\n{out}"


def test_switching_example_reproduces_what_the_pages_quote():
    """The fluorapatite run behind the Switching tab (WP-1984): the script asserts
    each figure `docs/docs/switching/` quotes from a file rietx wrote or read."""
    out = _run("switching.py").stdout
    assert "reproduced" in out, f"switching.py printed no 'reproduced' line:\n{out}"


#: A file whose name starts with `_` makes a guide's data (the synthetic
#: series, the calibration pair), with no page of its own.
GUIDE_SCRIPTS = sorted(p for p in (EXAMPLES / "guides").glob("*.py")
                       if not p.name.startswith("_"))
GUIDE_PAGES = REPO_ROOT / "docs" / "docs" / "guides"
#: What a guide page shows a script printing, marked so a text block that is
#: not output (a file's contents, a shell line) is never compared.
GUIDE_OUTPUT = re.compile(r"^<!-- output of (\S+) -->\n+```text\n(.*?)^```", re.S | re.M)


@pytest.fixture(scope="session")
def fetched_state(tmp_path_factory):
    """A state directory holding every `rietx.examples.fetch` file, copied from
    `tests/data/`, so a guide that fetches one reads it and never the network."""
    import shutil

    from rietx._about import STATE_DIR_ENV
    from rietx.examples import REMOTE_FILES

    state = tmp_path_factory.mktemp("state")
    (state / "data").mkdir()
    for name in REMOTE_FILES:
        shutil.copyfile(REPO_ROOT / "tests" / "data" / name, state / "data" / name)
    return {STATE_DIR_ENV: str(state)}


@documentation.elsewhere
@pytest.mark.parametrize("script", GUIDE_SCRIPTS, ids=lambda path: path.stem)
def test_every_guide_script_prints_what_its_page_quotes(script, fetched_state):
    """One script per Guides page (WP-1986), named after the page.

    The script asserts every number the page quotes; this checks the page's
    output blocks against what the script printed, so neither can be edited
    alone.  A new script joins by being written, with no test of its own.
    """
    page = GUIDE_PAGES / f"{script.stem}.md"
    assert page.exists(), f"{script.name} has no page: write docs/docs/guides/{page.name}"
    text = page.read_text(encoding="utf-8")
    quoted = GUIDE_OUTPUT.findall(text)
    assert quoted, f"{page.name} quotes no output of {script.name}"
    out = _run(f"guides/{script.name}", env=fetched_state).stdout
    for source, block in quoted:
        assert source == f"examples/guides/{script.name}", (
            f"{page.name} marks output of {source}, not of its own script")
        # Anchored at a line start, so a quoted line cannot match the tail
        # of a longer printed one.
        assert "\n" + block in "\n" + out, (
            f"{page.name} quotes output {script.name} did not print:\n"
            f"{block}\n--- printed ---\n{out}")


@pytest.mark.xdist_group("example-nac")
def test_nac_example_writes_its_plot(nac_run):
    """`nac_11bm.py` swallows an ImportError around plotting so it still runs
    on an install that lacks matplotlib.  With it installed that except-branch must
    not be the one taken, or a broken renderer passes as a clean run."""
    pytest.importorskip("matplotlib")
    _, before = nac_run
    for name, stamp in before.items():
        path = EXAMPLES / name
        assert path.exists(), f"nac_11bm.py wrote no {name}"
        assert path.stat().st_mtime_ns != stamp, f"nac_11bm.py left a stale {name}"


@pytest.mark.xdist_group("example-srm660c")
def test_srm660c_example_writes_its_renderings(srm660c_run):
    """The lab script renders through both paths — matplotlib for the PNGs and
    the chart module for the self-contained HTML — so a broken one is a silent
    loss of exactly what the chapter points a reader at."""
    pytest.importorskip("matplotlib")
    _, before = srm660c_run
    for name, stamp in before.items():
        path = EXAMPLES / name
        assert path.exists(), f"srm660c_lab.py wrote no {name}"
        assert path.stat().st_mtime_ns != stamp, f"srm660c_lab.py left a stale {name}"


def test_structure_figure_example_draws_its_pictures():
    """The structure figure walkthrough (WP-1470), which needs no matplotlib:
    three pictures written and the round trip through the rotation holding."""
    pictures = ("nac_structure.png", "nac_ellipsoids.png", "nac_print.png")
    before = _timestamps(*pictures)
    out = _run("structure_figure.py").stdout
    assert "draws the same picture: True" in out, out
    # the report's section: the search is never worse than the opening view
    opening, auto = (float(m) for m in re.findall(r"(\d+)% (?:of atoms )?hidden", out))
    assert auto <= opening and "same view: True" in out, out
    for name, stamp in before.items():
        path = EXAMPLES / name
        assert path.exists(), f"structure_figure.py wrote no {name}"
        assert path.stat().st_mtime_ns != stamp, f"structure_figure.py left a stale {name}"


def test_structure_cut_example_draws_its_pictures():
    """The cut walkthrough (WP-1501): the figure without F2 is the 113 atoms the
    WP measured, and its manual output block is what the script prints."""
    pictures = ("nac_without_f2.png", "nac_without_f2_completed.png", "nac_110_slab.png",
                "nac_one_red.png", "nac_2x2x1.png")
    before = _timestamps(*pictures)
    out = _run("structure_cut.py").stdout
    assert "without F2: 113 atoms drawn" in out, out
    for name, stamp in before.items():
        path = EXAMPLES / name
        assert path.exists(), f"structure_cut.py wrote no {name}"
        assert path.stat().st_mtime_ns != stamp, f"structure_cut.py left a stale {name}"


def test_structure_furniture_example_draws_its_picture():
    """The furniture walkthrough (WP-1533): a legend, a triad and a scale bar
    drawn in matplotlib from what the figure carries."""
    pytest.importorskip("matplotlib")
    before = _timestamps("ybco_furniture.png")
    out = _run("structure_furniture.py").stdout
    assert "legend ['Y', 'Ba', 'Cu', 'O']" in out, out
    for name, stamp in before.items():
        path = EXAMPLES / name
        assert path.exists(), f"structure_furniture.py wrote no {name}"
        assert path.stat().st_mtime_ns != stamp, f"structure_furniture.py left a stale {name}"
