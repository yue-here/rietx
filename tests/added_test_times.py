"""Per-test seconds for the tests a branch adds, read from a pytest junit file.

The fast tier grows by its tail: on 2026-09-27 its 50 slowest tests took 52 %
of its worker-seconds (WP-1506).  A wall-clock assertion would be a load sensor
(tests/CLAUDE.md § Budgets in tests), so the guard is this report, which
``/wp-handover`` reads.

    python -m tests.added_test_times JUNIT [BASE]

JUNIT comes from a run with ``--junitxml=JUNIT -o junit_duration_report=total``:
a CI leg's ``junit-*`` artifacts when the branch has them, else the handover's
own fast run, whose seconds understate a CI leg's by 3-4× (WP-1547).  A leg
runs as several shards, so JUNIT may be the directory holding them.  BASE defaults
to ``origin/main``.  A test counts as added when the working tree adds its
``def`` line since the fork from BASE and removes none of that name in that
module, so a renamed test is listed and one whose signature changed is not.  An
untracked test file counts whole.  Each row sums setup, call and teardown over
the test's parameter cases that ran.  A skipped case is left out, so a test
skipped throughout reads as absent.  A shared fixture's setup lands on
whichever test used it first, on that worker.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

_FILE = re.compile(r"^diff --git a/\S+ b/(tests/\S+)\.py$")
_DEF = re.compile(r"^([+-])\s*(?:async\s+)?def (test_\w+)\(")
#: A junit case name is the function, then ``[params]`` for a parametrised
#: case, then ``@group`` when xdist's loadgroup appended the ``xdist_group``.
_CASE_SUFFIX = re.compile(r"[\[@]")


def added_tests(diff: str) -> set[tuple[str, str]]:
    """``(module, name)`` for each test function whose ``def`` line a diff adds."""
    added: set[tuple[str, str]] = set()
    removed: set[tuple[str, str]] = set()
    module = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            m = _FILE.match(line)
            module = m.group(1).replace("/", ".") if m else None
        elif module and (m := _DEF.match(line)):
            (added if m.group(1) == "+" else removed).add((module, m.group(2)))
    return added - removed


def times(junit: str, added: set[tuple[str, str]]) -> dict[tuple[str, str], list[float]]:
    """Each added test's per-case seconds in a junit file, keyed as ``added`` is.

    ``junit`` may be a directory, and then every ``.xml`` under it is read.  A
    CI leg runs as several shards, each with its own file (WP-1547)."""
    modules_of: dict[str, list[str]] = defaultdict(list)
    for module, test in added:
        modules_of[test].append(module)
    path = Path(junit)
    files = sorted(path.rglob("*.xml")) if path.is_dir() else [path]
    rows: dict[tuple[str, str], list[float]] = defaultdict(list)
    for case in (c for f in files for c in ET.parse(f).iter("testcase")):
        if case.find("skipped") is not None:
            continue        # a skip's seconds say nothing of what the test costs
        name = _CASE_SUFFIX.split(case.get("name", ""), maxsplit=1)[0]
        classname = case.get("classname", "")
        for module in modules_of.get(name, ()):
            if classname == module or classname.startswith(module + "."):
                rows[(module, name)].append(float(case.get("time", "0")))
    return dict(rows)


def per_file(rows: dict[tuple[str, str], list[float]]) -> dict[str, tuple[float, int]]:
    """Each module's total seconds over its added tests, and how many there are.

    Twelve Le Bail tests of one to two minutes each were never seen as one
    five-minute file, because every row was judged alone (WP-1547)."""
    files: dict[str, tuple[float, int]] = {}
    for (module, _), ts in rows.items():
        total, n = files.get(module, (0.0, 0))
        files[module] = (total + sum(ts), n + 1)
    return files


def _untracked_as_diff() -> str:
    """Untracked test files as a diff adding every line, which ``git diff`` omits."""
    paths = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "tests/"],
        capture_output=True, encoding="utf-8", check=True).stdout.split()
    return "".join(
        f"diff --git a/{p} b/{p}\n"
        + "".join(f"+{line}\n" for line in Path(p).read_text(encoding="utf-8").splitlines())
        for p in paths if p.endswith(".py"))


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    base = argv[1] if len(argv) == 2 else "origin/main"
    fork = subprocess.run(["git", "merge-base", base, "HEAD"],
                          capture_output=True, encoding="utf-8", check=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "--no-renames", "-U0", fork, "--", "tests/"],
                          capture_output=True, encoding="utf-8", check=True).stdout
    added = added_tests(diff + _untracked_as_diff())
    rows = times(argv[0], added)
    for (module, test), ts in sorted(rows.items(), key=lambda kv: -sum(kv[1])):
        where = f"{module.replace('.', '/')}.py::{test}"
        print(f"{sum(ts):8.2f} s  {where}  ({len(ts)} case{'' if len(ts) == 1 else 's'})")
    for module, test in sorted(added - rows.keys()):
        print(f"{'absent':>10}  {module.replace('.', '/')}.py::{test}  (not run here)")
    print(f"{sum(map(sum, rows.values())):8.2f} s  over {len(rows)} added tests")
    print("per file:")
    for module, (total, n) in sorted(per_file(rows).items(), key=lambda kv: -kv[1][0]):
        print(f"{total:8.2f} s  {module.replace('.', '/')}.py  ({n} added test{'' if n == 1 else 's'})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
