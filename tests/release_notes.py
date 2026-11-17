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
heading of any level, in the order of its ``<id>`` (numbers first, by value).
A section whose bullets sit on consecutive lines gets its fragments the same
way; any other gets a blank line before each.  The joined file is then edited
as a reader's document, like any other step-2 draft.

``tests/test_docs_consistency.py`` checks that every fragment names a section
of the staged notes, and that a join leaves no fragment unplaced.
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
HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
BULLET = re.compile(r"^[-*] ")

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


def headings(lines: list[str]) -> list[tuple[int, int, str]]:
    """(line index, level, slug) of every heading of level 2 or more, outside code fences."""
    found, fenced = [], False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            fenced = not fenced
            continue
        m = None if fenced else HEADING.match(line)
        if m and len(m["hashes"]) >= 2:
            found.append((i, len(m["hashes"]), slug(m["text"])))
    return found


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
        if headings(text.splitlines()) or any(
                HEADING.match(line) for line in text.splitlines() if line.startswith("# ")):
            problems.append(f"{path.name}: holds a heading; a fragment is the text under one")
            continue
        frags.append(Fragment(path, m["id"], m["section"], text))
    return frags, problems


def check(head_text: str, frags: list[Fragment]) -> list[str]:
    """A problem line for every fragment whose section the staged notes do not have."""
    known = set(sections(head_text))
    return [f"{f.path.name}: no heading in the staged notes is section {f.section!r}; "
            f"known: {', '.join(sorted(known))}"
            for f in frags if f.section not in known]


def _tight(body: list[str]) -> bool:
    """True when the section's bullets sit on consecutive lines, with no blank between them."""
    starts = [i for i, line in enumerate(body) if BULLET.match(line)]
    return len(starts) >= 2 and all(body[i - 1].strip() for i in starts[1:])


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
        tight = _tight(body)
        out.append(lines[start])
        out.extend(body)
        for f in by_section.get(name, []):
            flines = f.text.splitlines()
            joined_on = (tight and body and BULLET.match(flines[0])
                         and (body[-1].startswith(" ") or BULLET.match(body[-1])))
            if not joined_on:
                out.append("")
            out.extend(flines)
            body = body + flines
        if k + 1 < len(marks):
            out.append("")
    text = "\n".join(out).rstrip("\n") + "\n"
    unplaced = [f.path.name for f in frags if f.text not in text]
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
    problems += check(head_text, frags)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if args.check:
        print(f"{len(frags)} fragment(s), every one names a section of "
              f"{head.relative_to(ROOT)}")
        return 0
    joined = join(head_text, frags)
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
