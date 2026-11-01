"""The maximal-subgroup sweep at index ≤ 9 over all 230 types (WP-1919).

``tests/test_subgroups.py`` runs the acceptance sweep, index ≤ 4, in the fast
suite.  This module runs the wider one the clean-room prototype was validated
at: every maximal subgroup of index ≤ 9 (primes 2, 3, 5, 7 at index p, 2 and 3
at p², 2 at p³), each standardised exactly inside
:func:`~rietx.crystallography.representation.subgroups.maximal` and rebuilt
from its own symbol and (P, p) by
:func:`~rietx.crystallography.representation.subgroups.is_maximal`.  It is a
script and not a ``slow`` row because the maintainer asked for it outside the
suite (#806, 2026-10-26); measured 2026-10-27 on an M-series Mac, one
process: 9291 subgroups, 40-60 CPU-s, 1-2 s at most for one group.

Run it::

    .venv/bin/python -m tests.subgroups_benchmark            # index <= 9, all 230
    .venv/bin/python -m tests.subgroups_benchmark --max-index 4 --groups 1-74

It prints one line per type (number, symbol, count, CPU seconds, all maximal)
and a total, and exits 1 if any subgroup failed to re-derive as maximal.
"""

from __future__ import annotations

import argparse
import sys
import time

import spglib

from rietx.crystallography.representation.subgroups import _standard, is_maximal, maximal


def standard_symbol(number: int) -> str:
    """spglib's default setting of a type, as gemmi spells it."""
    hall = next(h for h in range(1, 531) if spglib.get_spacegroup_type(h).number == number)
    return _standard(hall)[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-index", type=int, default=9)
    parser.add_argument("--groups", default="1-230", help="a range of type numbers, e.g. 1-74")
    args = parser.parse_args(argv)
    lo, hi = (int(x) for x in args.groups.split("-"))
    total, cpu, worst, bad = 0, 0.0, 0.0, []
    for number in range(lo, hi + 1):
        group = standard_symbol(number)
        start = time.process_time()
        result = maximal(group, max_index=args.max_index)
        ok = all(is_maximal(group, s.symbol, s.transform) for s in result)
        spent = time.process_time() - start
        total, cpu, worst = total + len(result), cpu + spent, max(worst, spent)
        if not ok:
            bad.append(number)
        print(f"{number:3d} {group:16s} {len(result):4d} {spent:6.2f} s {'ok' if ok else 'NOT MAXIMAL'}",
              flush=True)
    print(f"total {total} subgroups, {cpu:.1f} CPU-s, {worst:.2f} s at most for one type; "
          f"not maximal: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
