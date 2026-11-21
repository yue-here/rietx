"""How many comment blocks in ``src/rietx`` narrate history, at any revision (WP-2233).

    python -m tests.narration_count             # the working tree's HEAD
    python -m tests.narration_count REV [REV…]  # one table per revision

A block narrates when it says what the code was before a WP: ``until WP-1234``,
``since WP-1234``, ``before WP-1234``, or ``was … until``.  Narration is
tracked, not gated (the maintainer's ruling 1 on WP-2233), so nothing runs this
in CI.  It reads each revision with ``git cat-file``, so a later session can
run it over history to measure the trend before anyone decides on a gate.

A block is one comment run or one string statement, as
`tests/code_references.py` reads them.  The table counts blocks, not matches,
per top-level module or package, and a block matching several patterns counts
once in *any*.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter

from tests.code_references import ROOT, source_blocks

PATTERNS = {
    "until WP": re.compile(r"\buntil WP-\d{4}"),
    "since WP": re.compile(r"\bsince WP-\d{4}"),
    "before WP": re.compile(r"\bbefore WP-\d{4}"),
    "was … until": re.compile(r"\b(?:was|were)\b[^\n]{0,60}?\buntil\b"),
}


def _files_at(rev: str) -> dict[str, str]:
    """Every ``src/rietx`` python file at ``rev``, by path."""
    names = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", rev, "--", "src/rietx"],
        capture_output=True, encoding="utf-8", check=True).stdout.split()
    names = [n for n in names if n.endswith(".py")]
    batch = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "--batch"],
        input="".join(f"{rev}:{n}\n" for n in names).encode(),
        capture_output=True, check=True).stdout
    out, pos = {}, 0
    for name in names:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        out[name] = batch[header_end + 1:header_end + 1 + size].decode("utf-8")
        pos = header_end + 1 + size + 1
    return out


def package_of(rel: str) -> str:
    """``refine`` for ``src/rietx/refine.py``, ``io`` for ``src/rietx/io/x.py``."""
    first = rel.removeprefix("src/rietx/").split("/")[0]
    return first.removesuffix(".py")


def count(rev: str) -> dict[str, Counter]:
    """Blocks matching each pattern, and *any*, per top-level package."""
    table: dict[str, Counter] = {}
    for rel, source in _files_at(rev).items():
        row = table.setdefault(package_of(rel), Counter())
        try:
            found = list(source_blocks(rel, source))
        except (SyntaxError, ValueError):
            row["unparsed files"] += 1
            continue
        for block in found:
            hits = [k for k, pat in PATTERNS.items() if pat.search(block.text)]
            row.update(hits)
            if hits:
                row["any"] += 1
    return table


def render(rev: str, table: dict[str, Counter]) -> str:
    cols = [*PATTERNS, "any"]
    lines = [f"narration in src/rietx at {rev}", "",
             "| package | " + " | ".join(cols) + " |",
             "|---|" + "---:|" * len(cols)]
    total = Counter()
    for pkg in sorted(table, key=lambda p: (-table[p]["any"], p)):
        if table[pkg]["any"]:
            lines.append(f"| {pkg} | " + " | ".join(str(table[pkg][c]) for c in cols) + " |")
        total.update(table[pkg])
    lines.append("| **all** | " + " | ".join(str(total[c]) for c in cols) + " |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    for rev in argv or ["HEAD"]:
        print(render(rev, count(rev)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
