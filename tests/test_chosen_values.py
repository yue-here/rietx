"""WP-1448 — a value somebody chose says so, and says where the argument is.

A value in the package is one of three kinds: taken from a paper (cited in its
docstring), measured here (naming the WP whose handover holds the run), or
**chosen** by a person.  The third kind carries a tag at the value, in the
skill's ``*(Kind: pointer — text)*`` shape::

    *(Chosen: WP-1447, 2026-09-22 — a fixed bar over a control run per pattern)*
    *(Chosen: docs/DESIGN.md § Locked decisions, 2026-07-24 — torch before jax-metal)*

The pointer names the record where the choice was made and the alternatives
are written: a WP, which holds it under that date (normally its handover
entry of the day), or a ``docs/`` file and one of its headings.  The rule and the reasons are in
``docs/wp/1448-a-number-somebody-chose.md``.

**What this checks**, as ``tests/test_skill.py`` checks a ``Measured`` tag
(issue #241: a tag that names nothing passed): every ``*(Chosen`` in
``src/rietx`` parses whole; its date is a real date and not in the future;
its WP file exists, or its ``docs/`` file has that heading; and the record
mentions the date, in the WP file or inside the named section.

**What it cannot check**: that the record really holds the alternatives (it
checks only that the date appears in the record: for a WP pointer the date may
appear anywhere in the WP file, a Filed or Status line included, so a tag
dated the day the WP was filed passes whatever the handover log says), and
that an untagged value was not chosen.  The second is why the tag is a convention in
root ``CLAUDE.md`` § Conventions and not a gate on every number; the audit
table (``rietx._audit``) is what gates walked numbers.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "rietx"

#: Where a tag starts.  Anything matching this must parse as :data:`_TAG`,
#: so a misspelt tag fails instead of passing unread: any case, spaces after
#: the parenthesis, and a tag whose asterisks were dropped but which still
#: names a record.  Code such as ``f(chosen, x)`` or ``def f(chosen: str)``
#: has neither the ``*`` nor a record after the colon, so it is not read.
_TAG_START = re.compile(r"\*\(\s*chosen\b|\(\s*chosen\s*:\s*(?:WP-|docs/)", re.I)
#: The whole tag, matched at a :data:`_TAG_START` on flattened text.
_TAG = re.compile(
    r"\*\(Chosen: "
    r"(?P<where>WP-\d{4}|docs/[\w./-]+\.md § .+?), "
    r"(?P<date>\d{4}-\d{2}-\d{2}) — "
    r"(?P<what>\S.*?)\)\*"
)
_COMMENT_LEAD = re.compile(r"^\s*(?:#:?\s?)?")
_HEADING = re.compile(r"^(#+) (.+?)\s*$", re.M)


def _flatten(text: str) -> str:
    """One line per file, with comment markers and indentation gone, so a
    tag wrapped across ``#:`` lines or docstring lines reads as one string."""
    return " ".join(_COMMENT_LEAD.sub("", line) for line in text.splitlines())


def _tags(text: str) -> list[str]:
    """Every tag in *text*, each cut from its start to its closing ``)*``
    (or to the end of the next 300 characters, when it never closes)."""
    flat = _flatten(text)
    out = []
    for m in _TAG_START.finditer(flat):
        end = flat.find(")*", m.start())
        out.append(flat[m.start():end + 2] if end != -1 else flat[m.start():m.start() + 300])
    return out


def _section(text: str, heading: str) -> str | None:
    """The markdown heading *heading* and its body, to the next heading of
    the same or a higher level (a heading may carry the date itself);
    ``None`` when the file has no such heading."""
    heads = list(_HEADING.finditer(text))
    for i, h in enumerate(heads):
        if h.group(2) != heading:
            continue
        level = len(h.group(1))
        end = next((n.start() for n in heads[i + 1:] if len(n.group(1)) <= level), len(text))
        return text[h.start():end]
    return None


def _tag_problems(tag: str, root: Path, today: datetime.date) -> list[str]:
    """Every way *tag* fails to name a record, as messages; ``[]`` when it
    resolves."""
    m = _TAG.fullmatch(tag)
    if m is None:
        return [f"{tag[:80]!r} is not a whole tag: write "
                "*(Chosen: WP-NNNN, YYYY-MM-DD — what was chosen over what)*, or "
                "*(Chosen: docs/<file>.md § <heading>, YYYY-MM-DD — …)*"]
    where, date = m["where"], m["date"]
    try:
        day = datetime.date.fromisoformat(date)
    except ValueError:
        return [f"{tag[:80]!r}: {date} is not a date"]
    if day > today:
        return [f"{tag[:80]!r}: {date} is in the future"]
    if where.startswith("WP-"):
        files = sorted((root / "docs" / "wp").glob(f"{where[3:]}-*.md"))
        if len(files) != 1:
            return [f"{tag[:80]!r}: {where} has {len(files)} WP files, not one"]
        record, name = files[0].read_text(encoding="utf-8"), files[0].name
    else:
        rel, heading = where.split(" § ", 1)
        path = root / rel
        if not path.is_file():
            return [f"{tag[:80]!r}: {rel} does not exist"]
        record, name = _section(path.read_text(encoding="utf-8"), heading), where
        if record is None:
            return [f"{tag[:80]!r}: {rel} has no heading {heading!r}"]
    if date not in record:
        return [f"{tag[:80]!r}: {name} never mentions {date}, so it holds no "
                "record of that day's choice"]
    return []


def _live_tags() -> list[tuple[str, str]]:
    return [(str(p.relative_to(ROOT)), t)
            for p in sorted(SRC.rglob("*.py"))
            for t in _tags(p.read_text(encoding="utf-8"))]


def test_every_chosen_tag_names_a_record_of_its_day():
    tags = _live_tags()
    assert tags, "no *(Chosen: …)* tag found under src/rietx: the scan reads nothing"
    today = datetime.datetime.now(datetime.timezone.utc).date()
    problems = [f"{where}: {p}" for where, t in tags for p in _tag_problems(t, ROOT, today)]
    assert not problems, "\n".join(problems)


# --- the check itself, against a fixture tree (tests/CLAUDE.md § Guards that go quiet)

@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "wp").mkdir(parents=True)
    (tmp_path / "docs" / "wp" / "0001-a-wp.md").write_text(
        "# WP-0001 — a wp\n\n## Handover log\n\n### 2026-09-22 — decided\n\nA over B.\n",
        encoding="utf-8")
    (tmp_path / "docs" / "DESIGN.md").write_text(
        "# Design\n\n## Locked decisions\n\n- *Amendment (2026-07-24).* X.\n\n"
        "## Decisions, 2026-10-18\n\nRuled.\n\n"
        "## History\n\n2026-08-01 something else.\n", encoding="utf-8")
    return tmp_path


TODAY = datetime.date(2026, 11, 16)


@pytest.mark.parametrize("tag", [
    "*(Chosen: WP-0001, 2026-09-22 — A over B)*",
    "*(Chosen: docs/DESIGN.md § Locked decisions, 2026-07-24 — X over Y)*",
    "*(Chosen: WP-0001, 2026-09-22 — 2.0 over 1.3 (r = 0.10) and 3.0)*",
    "*(Chosen: docs/DESIGN.md § Decisions, 2026-10-18, 2026-10-18 — a heading with a comma)*",
])
def test_a_tag_naming_a_record_of_its_day_passes(tree, tag):
    assert _tag_problems(tag, tree, TODAY) == []


@pytest.mark.parametrize("tag, says", [
    ("*(Chosen: some conversation)*", "is not a whole tag"),
    ("*(Chosen: WP-0001 — A over B)*", "is not a whole tag"),
    ("*(Chosen: WP-0001, 2026-09-22)*", "is not a whole tag"),
    ("*(Chosen: WP-0001, 2026-02-30 — A over B)*", "is not a date"),
    ("*(Chosen: WP-0001, 2027-01-01 — A over B)*", "in the future"),
    ("*(Chosen: WP-9999, 2026-09-22 — A over B)*", "0 WP files"),
    ("*(Chosen: WP-0001, 2026-09-21 — A over B)*", "never mentions 2026-09-21"),
    ("*(Chosen: docs/NOPE.md § Locked decisions, 2026-07-24 — X)*", "does not exist"),
    ("*(Chosen: docs/DESIGN.md § Locked, 2026-07-24 — X)*", "no heading"),
    # the date is in the file, but under another heading
    ("*(Chosen: docs/DESIGN.md § Locked decisions, 2026-08-01 — X)*", "never mentions"),
])
def test_a_tag_naming_nothing_fails_and_says_why(tree, tag, says):
    problems = _tag_problems(tag, tree, TODAY)
    assert len(problems) == 1 and says in problems[0], problems


def test_a_tag_wrapped_across_comment_and_docstring_lines_is_read_whole():
    source = (
        "#: The bar.  *(Chosen: WP-0001,\n"
        "#: 2026-09-22 — A over B)*\n"
        "X = 5\n"
        "def f():\n"
        "    \"\"\"Kept on argument *(Chosen: WP-0001, 2026-09-22 — parents\n"
        "    over ghosts)*.\"\"\"\n"
        "# *(Chosen WP-0001 2026-09-22)*\n"
    )
    assert _tags(source) == [
        "*(Chosen: WP-0001, 2026-09-22 — A over B)*",
        "*(Chosen: WP-0001, 2026-09-22 — parents over ghosts)*",
        "*(Chosen WP-0001 2026-09-22)*",
    ]


@pytest.mark.parametrize("source", [
    "#: bar *(chosen: WP-0001, 2026-09-22 — A over B)*",
    "#: bar *( Chosen: WP-0001, 2026-09-22 — A over B)*",
    "#: bar (Chosen: WP-0001, 2026-09-22 — A over B)*",
])
def test_a_tag_misspelt_at_its_start_is_found_and_fails(tree, source):
    tags = _tags(source)
    assert len(tags) == 1, tags
    problems = _tag_problems(tags[0], tree, TODAY)
    assert len(problems) == 1 and "is not a whole tag" in problems[0], problems


def test_code_that_says_chosen_is_not_read_as_a_tag():
    source = "x = f(chosen, sets.get(chosen))\ndef g(chosen: str) -> None: ...\n"
    assert _tags(source) == []
