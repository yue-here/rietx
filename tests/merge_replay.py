"""Where merges conflict, and whether WP bookkeeping still touches ROADMAP (WP-1507).

    python -m tests.merge_replay SINCE [UNTIL]

Two reports over a window of history, both read from git alone.

**The replay.**  Every two-parent merge in ``git log --merges --all`` is
recomputed with ``git merge-tree --write-tree``, which exits 1 on a conflict
and names the paths.  It runs twice.  The first run merges the WP index as
plain text, which is what GitHub's web merge does.  The second runs the
``wpindex`` driver, which is what a local sync does: merge-tree runs a
configured driver (measured 2026-09-27 on git 2.39).  The counts are a floor,
since a rebase leaves no merge behind to replay.  WP-1507's baseline is this
replay over 2026-08-15 to 2026-09-27: 25 conflicted merges, 17 of them on
docs/ROADMAP.md.

**Header changes.**  A first-parent commit on origin/main whose diff touches
docs/wp/README.md changed some WP's header: a filing, a claim, a close or a
re-rating.  WP-1507's acceptance is that none of them touches docs/ROADMAP.md
or tests/test_docs_consistency.py.  One that does is listed for a person to
judge, because opening a new ROADMAP track is a legitimate reason.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = "docs/wp/README.md"
WATCHED = ("docs/ROADMAP.md", "tests/test_docs_consistency.py")
#: A driver that is git's own text merge, standing in for "no driver" where
#: the repository's config names one.  It runs myers where git's merge runs
#: pattern, because ``merge-file --diff-algorithm`` is missing from git 2.39
#: and 2.43, and a driver git cannot start reports every merge it reaches as a
#: conflict.  The /pr-review bench sets the same line.
TEXT_MERGE = "git merge-file %A %O %B"
DRIVER = (
    f'"{sys.executable}" "{ROOT / ".claude" / "hooks" / "wp_index.py"}" '
    f"--merge %O %A %B || {TEXT_MERGE}"
)


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=check
    )


def _window(since: str, until: str | None) -> list[str]:
    return [f"--since={since}"] + ([f"--until={until}"] if until else [])


def merges(root: Path, since: str, until: str | None = None) -> list[tuple[str, str, str]]:
    """``(merge, parent1, parent2)`` for every two-parent merge in the window."""
    out = _git(
        root, "log", "--merges", "--exclude=refs/stash", "--all",
        *_window(since, until), "--format=%H %P",
    ).stdout
    return [tuple(line.split()) for line in out.splitlines() if len(line.split()) == 3]


def conflicts(root: Path, p1: str, p2: str, driver: str) -> list[str]:
    """The paths a merge of ``p1`` and ``p2`` conflicts on, under ``driver``."""
    done = _git(
        root, "-c", f"merge.wpindex.driver={driver}",
        "merge-tree", "--write-tree", "--name-only", "--no-messages", p1, p2,
        check=False,
    )
    if done.returncode not in (0, 1):
        raise RuntimeError(f"merge-tree {p1[:8]} {p2[:8]}: {done.stderr.strip()}")
    return done.stdout.splitlines()[1:] if done.returncode == 1 else []


def replay(root: Path, since: str, until: str | None = None,
           driver: str = DRIVER) -> dict[str, tuple[int, Counter]]:
    """Per mode, the number of conflicted merges and the conflicts per path."""
    found = merges(root, since, until)
    result = {"merges": (len(found), Counter())}
    for mode, command in (("text", TEXT_MERGE), ("driver", driver)):
        paths: Counter = Counter()
        conflicted = 0
        for _merge, p1, p2 in found:
            hit = conflicts(root, p1, p2, command)
            conflicted += bool(hit)
            paths.update(hit)
        result[mode] = (conflicted, paths)
    return result


def header_changes(root: Path, since: str, until: str | None = None,
                   ref: str = "origin/main") -> list[tuple[str, str, list[str]]]:
    """``(sha, subject, watched paths it touched)`` per first-parent commit
    whose diff against its first parent touches the index, oldest first."""
    out = _git(
        root, "log", "--first-parent", "--diff-merges=first-parent", "--reverse",
        *_window(since, until), "--name-only", "--format=%x1e%H%x1f%s", ref,
    ).stdout
    rows = []
    for record in out.split("\x1e")[1:]:
        head, _, files = record.partition("\n")
        sha, _, subject = head.partition("\x1f")
        names = files.split()
        if INDEX in names:
            rows.append((sha, subject, [w for w in WATCHED if w in names]))
    return rows


def report(root: Path, since: str, until: str | None = None) -> str:
    window = f"{since} to {until or 'now'}"
    rep = replay(root, since, until)
    total = rep["merges"][0]
    lines = [f"## Merge replay, {window}", "", f"{total} two-parent merges replayed.", ""]
    for mode, label in (("text", "index merged as text (GitHub's web merge)"),
                        ("driver", "index merged by the wpindex driver (a local sync)")):
        conflicted, paths = rep[mode]
        rate = f"{conflicted / total:.1%}" if total else "n/a"
        lines.append(f"- {label}: {conflicted} conflicted ({rate})")
        for path, n in paths.most_common():
            lines.append(f"  - {n} × `{path}`")
    changes = header_changes(root, since, until)
    offenders = [c for c in changes if c[2]]
    lines += ["", f"## Header changes on origin/main, {window}", "",
              f"{len(changes)} commits changed a WP header; "
              f"{len(offenders)} of them also touched ROADMAP or the cap test."]
    for sha, subject, touched in changes[:3]:
        verdict = "touched " + ", ".join(f"`{t}`" for t in touched) if touched else "clean"
        lines.append(f"- first three: {sha[:8]} {subject}: {verdict}")
    for sha, subject, touched in (c for c in offenders if c not in changes[:3]):
        lines.append(f"- also: {sha[:8]} {subject}: " + ", ".join(f"`{t}`" for t in touched))
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    print(report(ROOT, *argv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
