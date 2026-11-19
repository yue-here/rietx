"""Join the release-note fragments into the next release's notes (WP-1941).

A change that a user upgrading needs to hear about stages its note as a file
of its own in ``docs/releases/unreleased/``, named
``<id>.<section>.md``.  ``<id>`` is the pull request's number (or, before the
PR exists, any name no other note uses, such as ``wp1941``); ``<section>`` is
the slug of a heading in the next release's staged notes,
``docs/releases/X.Y.Z.md``: ``### Numbers that move`` is ``numbers-that-move``.
Two PRs that each add a note then add two files, and never conflict on one.

**Why the head file, not a template.**  The staged notes carry hand-written
prose between their headings (``## Upgrading``'s opening line, the paragraphs
under ``### Files that change``), and the section set is open: 1.7.0 had
``## Foreign files`` and ``## Indexing``, 1.12.0 has ``## Magnetic
structures``.  towncrier and scriv both render their fragments through a
template into one place in the changelog (towncrier after its
``start_string``, scriv at its insert marker), from a configured list of
types.  Neither puts a note under a heading of a file a person wrote.  Here
the head file *is* the configuration: every heading in it is a section, and a
new section is a new heading.

At the cut (``docs/RELEASING.md`` step 2)::

    python -m tests.release_notes            # print the joined notes
    python -m tests.release_notes --write    # write them, delete the fragments

Each fragment goes at the end of its section's own text, before the next
heading of level 2 or more, in the order of its ``<id>`` (numbers first, by value).
A bullet goes straight under the bullet before it, with no blank line, while
the section's bullets so far sit on consecutive lines, which a section that
starts empty does: notes from separate PRs then make one tight list.  In a
section whose bullets are already blank-separated, each fragment gets a blank
line before it.  The joined file is then edited as a reader's document, like
any other step-2 draft.

``--check``, which ``tests/test_docs_consistency.py`` also runs, checks that
every fragment names a section of the staged notes, and joins them to check
that the join leaves no fragment unplaced.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "docs" / "releases"
FRAGMENT_DIR = RELEASES / "unreleased"

FRAGMENT_NAME = re.compile(
    r"^(?P<id>[0-9A-Za-z][0-9A-Za-z_-]*)\.(?P<section>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
# An ATX heading as CommonMark reads one: up to three spaces of indent, and a
# closing run of #s only after a space, so `## C#` keeps its `#`.
HEADING = re.compile(r"^ {0,3}(?P<hashes>#{1,6})(?:\s+(?P<text>.*?))?(?:\s+#+)?\s*$")
FENCE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
BULLET = re.compile(r"^[-*] ")
# A line of only `-` or only `=`: under a line of text it makes that text a
# setext heading, and on its own it draws a rule.  Neither belongs in a note.
UNDERLINE = re.compile(r"^\s*(?:-+|=+)\s*$")

# Files in the fragment directory that are not fragments.
NOT_FRAGMENTS = frozenset({"README.md"})


@dataclass(frozen=True)
class Fragment:
    path: Path
    id: str
    section: str
    text: str

    @property
    def order(self) -> tuple:
        return (0, int(self.id), self.path.name) if self.id.isdigit() else (1, self.id,
                                                                             self.path.name)


def next_version(root: Path = ROOT) -> str:
    """``pyproject.version`` without its ``.devN``: ``1.12.0.dev0`` → ``1.12.0``."""
    with open(root / "pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]
    return re.sub(r"\.dev\d+$", "", version)


def head_path(version: str | None = None, root: Path = ROOT) -> Path:
    return root / "docs" / "releases" / f"{version or next_version(root)}.md"


def slug(text: str) -> str:
    """A heading's section name: lower case, every run of other characters a hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _scan(lines: list[str]) -> tuple[list[tuple[int, int, str]], bool, list[int]]:
    """Every ATX heading outside a code fence as (line index, level, slug),
    whether every fence closed, and the index of every line of only `-` or `=`
    outside a fence.  A fence closes only on its own character, at least as long
    as its opener."""
    found, fence, underlines = [], "", []
    for i, line in enumerate(lines):
        f = FENCE.match(line)
        if f and not fence:
            fence = f["fence"]
            continue
        if f and fence and f["fence"][0] == fence[0] and len(f["fence"]) >= len(fence) \
                and not line.strip().strip(fence[0]):
            fence = ""
            continue
        if fence:
            continue
        m = HEADING.match(line)
        if m:
            found.append((i, len(m["hashes"]), slug(m["text"] or "")))
        elif UNDERLINE.match(line):
            underlines.append(i)
    return found, not fence, underlines


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, slug) of every heading of level 2 or more, outside code fences.

    The level-1 heading is the file's title and bounds no section."""
    return [h for h in _scan(lines)[0] if h[1] >= 2]


def sections(head_text: str) -> list[str]:
    """The section names of a staged-notes file, in order.  Two headings with one name raise."""
    names = [name for _, _, name in headings(head_text.splitlines())]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            raise ValueError(f"two headings are both section {name!r}; a fragment could not "
                             "say which it means, so rename one")
        seen.add(name)
    return names


def read_fragments(directory: Path = FRAGMENT_DIR) -> tuple[list[Fragment], list[str]]:
    """Every fragment in ``directory``, and a problem line for each file that is not one."""
    frags, problems = [], []
    if not directory.is_dir():
        return frags, problems
    for path in sorted(directory.iterdir()):
        if path.name in NOT_FRAGMENTS or path.name.startswith("."):
            continue
        m = FRAGMENT_NAME.match(path.name)
        if not m or not path.is_file():
            problems.append(f"{path.name}: not <id>.<section>.md (id: letters, digits, - or _; "
                            "section: a heading's slug, such as numbers-that-move)")
            continue
        text = path.read_text(encoding="utf-8").strip("\n")
        if not text.strip():
            problems.append(f"{path.name}: empty")
            continue
        found, closed, underlines = _scan(text.splitlines())
        if found:
            problems.append(f"{path.name}: holds a heading; a fragment is the text under one")
            continue
        if underlines:
            problems.append(f"{path.name}: line {underlines[0] + 1} is only '-' or '=', which "
                            "makes the line above it a heading (or draws a rule); a fragment "
                            "is the text under one")
            continue
        if not closed:
            problems.append(f"{path.name}: a code fence never closes, which would turn every "
                            "heading after it into code")
            continue
        frags.append(Fragment(path, m["id"], m["section"], text))
    return frags, problems


def check(head_text: str, frags: list[Fragment], head_name: str = "the staged notes") -> list[str]:
    """A problem line for every fragment whose section the staged notes do not have.

    After a cut, a branch that forked before it can carry a fragment for a
    section the new staged notes lack; the line says how to mend that."""
    known = set(sections(head_text))
    return [f"{f.path.name}: no heading in {head_name} is section {f.section!r} "
            f"(known: {', '.join(sorted(known))}). Add that heading to {head_name}, or "
            "rename the fragment to a known section; if a release was cut after this "
            "branch forked, rebase onto main first, so the check reads the new staged notes"
            for f in frags if f.section not in known]


def _tight(body: list[str]) -> bool:
    """True when the section's bullets sit on consecutive lines, with no blank
    between them; a section with fewer than two bullets has nothing loose yet."""
    starts = [i for i, line in enumerate(body) if BULLET.match(line)]
    return all(body[i - 1].strip() for i in starts[1:])


def join(head_text: str, frags: list[Fragment]) -> str:
    """The staged notes with every fragment placed at the end of its section."""
    problems = check(head_text, frags)
    if problems:
        raise ValueError("\n".join(problems))
    by_section: dict[str, list[Fragment]] = {}
    for f in sorted(frags, key=lambda f: f.order):
        by_section.setdefault(f.section, []).append(f)

    lines = head_text.splitlines()
    marks = headings(lines)
    out = lines[:marks[0][0]] if marks else list(lines)
    for k, (start, _, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        body = lines[start + 1:end]
        while body and not body[-1].strip():
            body.pop()
        out.append(lines[start])
        out.extend(body)
        for f in by_section.get(name, []):
            flines = f.text.splitlines()
            # Judged on the section as joined so far, so that one-bullet notes
            # from separate PRs in a section that started empty stay one tight list.
            joined_on = (body and BULLET.match(flines[0]) and _tight(body)
                         and (body[-1].startswith(" ") or BULLET.match(body[-1])))
            if not joined_on:
                out.append("")
                body = body + [""]
            out.extend(flines)
            body = body + flines
        if k + 1 < len(marks):
            out.append("")
    text = "\n".join(out).rstrip("\n") + "\n"
    # Each fragment's text appears at least once more than the head alone holds it.
    unplaced = [f.path.name for f in frags if text.count(f.text) <= head_text.count(f.text)]
    if unplaced:  # pragma: no cover - a join that drops text is a bug here, not in a fragment
        raise AssertionError(f"fragments left unplaced: {unplaced}")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.release_notes", description=__doc__
                                     .split("\n\n")[0])
    parser.add_argument("--version", help="the release whose staged notes are the head "
                        "(default: pyproject.version without .devN)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="only check the fragments; exit 1 on a problem")
    mode.add_argument("--write", action="store_true",
                      help="write the joined notes over the head file and delete the fragments")
    args = parser.parse_args(argv)

    head = head_path(args.version)
    if not head.is_file():
        print(f"no staged notes at {head.relative_to(ROOT)}", file=sys.stderr)
        return 1
    head_text = head.read_text(encoding="utf-8")
    frags, problems = read_fragments()
    try:
        problems += check(head_text, frags, str(head.relative_to(ROOT)))
    except ValueError as err:  # two headings with one slug
        problems.append(f"{head.relative_to(ROOT)}: {err}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    joined = join(head_text, frags)
    if args.check:
        print(f"{len(frags)} fragment(s), every one names a section of "
              f"{head.relative_to(ROOT)} and joins")
        return 0
    if not args.write:
        sys.stdout.write(joined)
        return 0
    head.write_text(joined, encoding="utf-8")
    for f in frags:
        f.path.unlink()
    print(f"wrote {head.relative_to(ROOT)} from {len(frags)} fragment(s), and deleted them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
