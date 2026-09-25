"""The `examples/` walkthroughs are executed, not just linted (WP-1067).

`examples/` is the **one authority** for a worked walkthrough: the manual
`{literalinclude}`s these scripts rather than retyping them, so what a reader
of `using/quickstart.md` sees is this file, and this test is what makes it a
script that runs.  Before WP-1067 nothing in `tests/` executed either script —
ruff linted them and that was all, while README carried a second, unguarded
copy of the same walkthrough.

**Where the outputs go.** Each script writes its plots beside itself
(`examples/nac_fit.png`, `examples/srm660c_fit.png`, `…_vlm.png`,
`…_fit.html`, `examples/fap_fit.png`), from a path built off its own
`__file__`, so running it from a
temporary cwd would not redirect anything.  This runner therefore accepts the
write; those names are gitignored.  Its own data paths are `__file__`-relative
too, so the scripts are run in place.

**Why these are not marked `slow`.**  The cost model that put them here
assumed a chapter running a real fit would turn the docs guard into an
acceptance suite.  Measured on this tree ([dev] venv, darwin/arm64), it does
not: 3.5 s for `nac_11bm.py` and 3.3 s for `srm660c_lab.py`, against a fast
selection that runs 1–3 minutes.  Per-push execution is the whole value of
the guard — a broken walkthrough should fail on the push that broke it, not
in the weekly full job — so they run in the fast suite, and the `slow` mark
is one line away if either grows.  These are cheap because their protocols
are short, not because they are toys; they refine the same real data as the
acceptance suites, which is where the *numbers* are pinned (this test asserts
that the script ran, never what it found — one authority per fact).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"


def _run(script: str) -> subprocess.CompletedProcess[str]:
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
        env={**os.environ, "PYTHONUTF8": "1"},
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


@pytest.fixture(scope="module")
def fap_run():
    before = _timestamps("fap_fit.png")
    return _run("fap_lab.py").stdout, before


@pytest.mark.xdist_group("example-nac")
def test_nac_11bm_example_runs(nac_run):
    """The quickstart walkthrough: read, Le Bail, add the impurity the report
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


@pytest.mark.xdist_group("example-fap")
def test_fap_lab_example_runs(fap_run):
    """The landing page's walkthrough (WP-1331): a seven-site structural
    refinement of lab Cu Kα data, and the two warnings it earns. The page
    quotes this script's output, so a rename that breaks it must fail here
    rather than on the published page."""
    out, _ = fap_run
    for marker in ("converged", "Rwp=", "PATTERN_UNDERSAMPLED", "wrote"):
        assert marker in out, f"fap_lab.py printed no {marker!r} line:\n{out}"


@pytest.mark.xdist_group("example-nac")
def test_nac_example_writes_its_plot(nac_run):
    """`nac_11bm.py` swallows an ImportError around plotting so it still runs
    without the `viz` extra.  With matplotlib installed that except-branch must
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


@pytest.mark.xdist_group("example-fap")
def test_fap_example_writes_its_plot(fap_run):
    """Same reason as the NAC one above: the script swallows an ImportError
    around plotting, so with matplotlib installed that branch must not be the
    one taken. The figure is what the landing page shows."""
    pytest.importorskip("matplotlib")
    _, before = fap_run
    for name, stamp in before.items():
        path = EXAMPLES / name
        assert path.exists(), f"fap_lab.py wrote no {name}"
        assert path.stat().st_mtime_ns != stamp, f"fap_lab.py left a stale {name}"
