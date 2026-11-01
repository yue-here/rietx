"""What a reader of a standard fit receives, before and after a change.

    python -m tests.reader_output         # the diff against this change's base
    python -m tests.reader_output --show  # this tree's text alone

**Why.**  rietx hands its reader, a person or an agent, text it reads as an
answer: ``str(result)``, ``str(report)`` and each diagnostic.  A change can make
that text longer or emptier with every test green, because no test pins what
a fit *prints*.  WP-2010 added a 930-character sentence to every Rietveld
report, the same for every fit with the same free parameters, and it reached
the maintainer only because its author flagged the length.  The maintainer
ruled on 2026-11-01 that every change to what a reader receives comes to them
before merge, since the package should pass no junk back to a reader.  So
`/pr-review` and `/wp-handover` run this and show the diff.

**What it runs**: `examples/srm660c_lab.py`'s model and plan on the NIST LaB6
pattern, about 5 s, then prints the result, the report and every diagnostic.
Two runs of one tree print identical text on one machine, so any line in the
diff is the change's.  It is one fit.  A field added to another result type
shows in the generated `docs/skill/rietx/references/api*.md` instead.

**The base tree** is `git archive` of :func:`tests.skill_caps.base` (the
merge-base with `origin/main`, or ``RIETX_CAPS_BASE``) into a temporary
directory.  This file's probe runs against that tree's ``src`` in a child
process, so a base that predates this file is still read.  It exits 1 when the
texts differ, and 2 when there is no base to compare with.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def probe(root: Path) -> str:
    """The text a reader of the standard fit receives, built from ``root``."""
    sys.path[:0] = [str(root / "src"), str(root / "examples")]
    import srm660c_lab as example

    import rietx as rx

    data = rx.read_pdcif(example.DATA / "nist_srm660c_100a.cif", block="_meas")
    structure, instrument = example.build_model()
    instrument.background = example.auto_background(data, kind="chebyshev").background
    refinement = rx.Refinement(structure, instrument)
    result = refinement.fit(data, plan=example.nist_protocol_plan())
    report = refinement.report(plan=example.nist_protocol_plan())
    lines = [str(result), str(report)] + [str(d) for d in result.diagnostics]
    return "\n".join(lines) + "\n"


def text_of(root: Path) -> str:
    """:func:`probe` on ``root``, in a child process so two trees never share imports."""
    run = subprocess.run(
        [sys.executable, "-W", "ignore", __file__, "--probe", str(root)],
        capture_output=True, encoding="utf-8",
        env={**os.environ, "RIETX_TELEMETRY": "0"})
    if run.returncode != 0:
        raise SystemExit(f"the probe failed on {root}:\n{run.stderr}")
    return run.stdout


def main(argv: list[str]) -> int:
    if argv[:1] == ["--probe"]:
        sys.stdout.write(probe(Path(argv[1])))
        return 0
    if argv[:1] == ["--show"]:
        sys.stdout.write(text_of(ROOT))
        return 0
    from tests.skill_caps import base

    rev, how = base()
    if rev is None:
        print(f"reader output: {how}")
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        archive = subprocess.run(["git", "-C", str(ROOT), "archive", rev],
                                 capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", tmp], input=archive.stdout, check=True)
        before = text_of(Path(tmp))
    after = text_of(ROOT)
    if before == after:
        print(f"reader output: unchanged against {how} ({rev[:9]})")
        return 0
    print(f"reader output: CHANGED against {how} ({rev[:9]})")
    sys.stdout.writelines(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"base {rev[:9]}", tofile="this tree"))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
