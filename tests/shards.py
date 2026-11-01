"""Which files a CI shard runs: the fast tier split in N by recorded seconds.

A fast leg ran 21-31 min on GitHub's two-core runner, where the worker count is
not a lever (WP-1547).  So each leg runs as N jobs, one ``--shard K/N`` each,
and ``conftest.pytest_collection_modifyitems`` keeps shard K's files.  A shard
takes files whole.  Files that share an ``xdist_group`` go to one shard
together, so a group's shared fixture is still built once, on one runner.  A
whole file also builds each of its module fixtures once.

Units go longest first, each to the least-loaded shard (Graham's LPT rule), by
the seconds in ``shard_times.json``.  The answer depends only on the collected
files, their groups and the record.  It has to: xdist's controller collects
nothing, and every worker selects its shard for itself.  A file the record does
not hold weighs the median recorded file, so a new file lands somewhere sensible
until the record is rewritten.

    python -m tests.shards DIR [SOURCE]

rewrites the record from one CI run's junit files, fetched with ``gh run
download RUN -p 'junit-*' -D DIR``.  Each subdirectory is one job, named
``junit-<leg>`` or ``junit-<leg>-<shard>``, and a leg's shards sum together.  A
file's seconds sum its cases, leaving out skipped ones.  The record holds one
profile, ``numpy``: each file's median seconds over the Python legs that ran
the most of its cases, each leg's put on the median leg's clock, since one
run's legs differ by up to 1.6× on the same tree.  A leg's clock is what it
spent on the files every leg ran alike: the same number of cases, none of them
free.  Over the legs that ran the *most* of a file, because part of one may run
on a leg alone: the documentation executes on the newest
(``tests/documentation.py``), and every file holding it also holds cases that
run everywhere, so "ran it at all" cannot tell the legs apart.  A median over
every leg would weigh the documentation at half there, on the leg that already
runs the most, and the clock would count it as that leg's slowness (WP-2019).
The jax
job is read past.  It held a second profile while it ran the whole tier in
shards, its costs differing file by file (``test_cross_backend.py`` ~390 s there
against ~15 s on numpy), and since WP-2019 it runs ``--jax-cases`` as one job,
which no record places.  SOURCE names the run in the record.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path

RECORD = Path(__file__).with_name("shard_times.json")
_SPEC = re.compile(r"\s*(\d+)\s*/\s*(\d+)\s*")
#: ``junit-py3.11`` is leg ``py3.11``, and so is its shard ``junit-py3.11-2``.
_JOB = re.compile(r"junit-(.+?)(?:-(\d+))?")


def parse(spec: str) -> tuple[int, int]:
    """``(K, N)`` from ``"K/N"``, or ``ValueError`` saying what is wrong."""
    m = _SPEC.fullmatch(spec)
    if not m:
        raise ValueError(f"--shard takes K/N, such as 1/2, not {spec!r}")
    k, n = int(m[1]), int(m[2])
    if not 1 <= k <= n:
        raise ValueError(f"--shard {spec}: K must run from 1 to N")
    return k, n


def recorded_seconds(path: Path = RECORD) -> dict[str, float]:
    """The record's seconds, keyed by repo-relative POSIX file path."""
    return json.loads(path.read_text(encoding="utf-8"))["numpy"]


def units(pairs: Iterable[tuple[str, str | None]]) -> list[frozenset[str]]:
    """The files that must share a shard, from ``(file, group)`` per item.

    Files sharing a group name merge, transitively.  An item in several groups
    gives a pair for each.  The answer is a set of sets, so it cannot depend on
    the order the items came in, though the list's own order does."""
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def root(x: tuple[str, str]) -> tuple[str, str]:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for file, group in pairs:
        f = root(("file", file))
        if group is not None:
            g = root(("group", group))
            if f != g:
                parent[max(f, g)] = min(f, g)
    members: dict[tuple[str, str], set[str]] = defaultdict(set)
    for kind, name in list(parent):
        if kind == "file":
            members[root((kind, name))].add(name)
    return [frozenset(files) for files in members.values()]


def assign(parts: Iterable[frozenset[str]], seconds: Mapping[str, float],
           n: int) -> list[tuple[frozenset[str], float]]:
    """Each shard's files and estimated seconds, units placed longest first.

    Ties break on the unit's sorted file names and then on the lowest shard
    index, so every process given the same units gets the same shards.  The
    largest shard exceeds an even split by at most the largest unit."""
    default = statistics.median(seconds.values()) if seconds else 1.0

    def weight(unit: frozenset[str]) -> float:
        return math.fsum(seconds.get(f, default) for f in sorted(unit))

    order = sorted(((weight(u), sorted(u)) for u in parts), key=lambda wu: (-wu[0], wu[1]))
    files: list[set[str]] = [set() for _ in range(n)]
    loads = [0.0] * n
    for w, unit in order:
        i = min(range(n), key=lambda j: (loads[j], j))
        files[i].update(unit)
        loads[i] += w
    return [(frozenset(f), load) for f, load in zip(files, loads, strict=True)]


def _file_of(classname: str) -> str | None:
    """``tests/test_x.py`` from ``tests.test_x`` or ``tests.test_x.TestK``."""
    parts = classname.split(".") if classname else []
    while parts and parts[-1][:1].isupper():
        parts.pop()                 # a test class, which pytest names Test*
    return "/".join(parts) + ".py" if parts else None


def leg_seconds(directory: Path) -> dict[str, dict[str, float]]:
    """Each leg's seconds per file, a leg's shards summed.

    A file whose every case skipped is kept at zero, which is what it cost.  A
    module skipped at import has no classname and no items, and is left out.
    A leg missing a shard that another leg has is refused: a shard that timed
    out uploads no file, and its files would read as costing nothing."""
    return _legs(directory)[0]


def _legs(directory: Path) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, int]]]:
    """``leg_seconds``, and beside it how many of each file's cases each leg ran."""
    legs: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    ran: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    shards_of: dict[str, set[int]] = defaultdict(set)
    for junit in sorted(directory.glob("junit-*/junit.xml")):
        m = _JOB.fullmatch(junit.parent.name)
        if m is None:
            continue
        if m[2] is not None:
            shards_of[m[1]].add(int(m[2]))
        leg, count = legs[m[1]], ran[m[1]]
        for case in ET.parse(junit).iter("testcase"):
            file = _file_of(case.get("classname", ""))
            if file is None:
                continue
            skipped = case.find("skipped") is not None
            leg[file] += 0.0 if skipped else float(case.get("time", "0"))
            count[file] += 0 if skipped else 1
    want = set(range(1, max(map(max, shards_of.values()), default=0) + 1))
    if short := {name: sorted(want - got) for name, got in shards_of.items() if got != want}:
        raise SystemExit(f"shards missing under {directory}: {short}")
    return ({name: dict(files) for name, files in legs.items()},
            {name: dict(files) for name, files in ran.items()})


def record(directory: Path, source: str) -> dict:
    """The record's contents from one run's junit files, its Python legs alone."""
    seconds, ran = _legs(directory)
    python = [name for name in seconds if name.startswith("py")]
    if not python:
        raise SystemExit(f"no junit-py* leg under {directory}")
    every = set().union(*(seconds[name] for name in python))
    common = {f for f in every
              if len({ran[name].get(f, 0) for name in python}) == 1
              and all(seconds[name].get(f, 0.0) > 0.0 for name in python)}
    speed = {name: math.fsum(seconds[name][f] for f in sorted(common)) for name in python}
    median = statistics.median(speed.values())
    factor = {name: (s / median if s and median else 1.0) for name, s in speed.items()}
    numpy = {}
    for f in every:
        most = max(ran[name].get(f, 0) for name in python)
        legs = [seconds[name][f] / factor[name] for name in python
                if most and ran[name].get(f, 0) == most]
        numpy[f] = round(statistics.median(legs), 1) if legs else 0.0
    return {"source": source, "numpy": numpy}


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    directory = Path(argv[0])
    source = argv[1] if len(argv) == 2 else directory.name
    out = record(directory, source)
    RECORD.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"numpy: {len(out['numpy'])} files, {math.fsum(out['numpy'].values()):.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
