"""The GUI style guide names only what exists and restates no value (WP-2142).

`gui/STYLE.md` holds the rules for how the GUI looks and why; the values live in
`src/rietx/viz/theme.py` (generated into `gui/src/tokens.css`) and
`gui/src/app.css`.  The maintainer approved that split on 2026-11-09, and these
checks hold the guide to it.  A guide naming a token that a rename removed would
send the next session looking for a value that is gone, and a hex code copied
into the guide would drift from the code without any test going red.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "gui" / "STYLE.md"
TOKEN_FILES = (ROOT / "gui" / "src" / "tokens.css", ROOT / "gui" / "src" / "app.css")

# A rule's marker says who stated its motive: the maintainer on a date or in a
# WP, Claude by inference, or an item still waiting on the maintainer.
MARKER = re.compile(r"\[(Yue[ ,]|inferred|open B\d+)[^\]]*\]\.?\s*\|?\s*$")


def _guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


def _declared_tokens() -> set[str]:
    declared: set[str] = set()
    for path in TOKEN_FILES:
        # A comment can quote a token that is gone (`app.css` records a
        # removed `--s4` that way), so comments are dropped before the scan.
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        declared |= set(re.findall(r"(--[a-z][a-z0-9-]*)\s*:", css))
    return declared


def test_every_token_the_guide_names_is_declared():
    named = set(re.findall(r"`(--[a-z][a-z0-9-]*)`", _guide()))
    assert named, "the guide names no token; the pattern no longer matches its style"
    missing = sorted(named - _declared_tokens())
    assert not missing, (
        f"gui/STYLE.md names {missing}, which neither gui/src/tokens.css nor "
        "gui/src/app.css declares. Rename them in the guide, or describe the role "
        "in words until the piece that adds the token lands."
    )


def test_every_file_the_guide_names_exists():
    named = set(re.findall(r"`((?:tests|gui|src|docs)/[^`\s]+\.(?:py|ts|mjs|css|md|svelte|json))`", _guide()))
    assert named
    missing = sorted(p for p in named if not (ROOT / p).exists())
    assert not missing, f"gui/STYLE.md names files that do not exist: {missing}"


def _rule_blocks(text: str) -> list[str]:
    """Each bullet, numbered item and table row between Principles and Checks."""
    assert "\n## Principles\n" in text and "\n## Checks\n" in text, (
        "gui/STYLE.md lost its Principles or Checks heading, which bound the rules")
    body = text.split("\n## Principles\n", 1)[1].split("\n## Checks\n", 1)[0]
    blocks: list[str] = []
    for line in body.split("\n"):
        if re.match(r"^(- |\d+\. )", line):
            blocks.append(line)
        elif line.startswith("|") and not re.match(r"^\|[\s|:-]+\|$", line):
            if line.startswith("| Kind |"):
                continue
            blocks.append(line)
        elif line.startswith("  ") and blocks:
            blocks[-1] += " " + line.strip()
    return blocks


def test_every_rule_carries_a_marker():
    blocks = _rule_blocks(_guide())
    assert len(blocks) > 50, "the rule parser found almost nothing; check the guide's headings"
    unmarked = [b[-80:] for b in blocks if not MARKER.search(b)]
    assert not unmarked, (
        "each rule in gui/STYLE.md ends with [Yue <date>], [inferred] or [open Bn] "
        f"(the maintainer's ruling of 2026-11-09); these carry none: {unmarked}"
    )


def test_the_guide_restates_no_colour_or_size_value():
    text = _guide()
    # A short hex needs a letter, or an issue number such as #1511 would match.
    hexes = re.findall(
        r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|(?=[0-9]*[a-fA-F])[0-9a-fA-F]{3,4})\b", text)
    hexes += re.findall(r"\b(?:rgba?|hsla?|oklch|oklab)\(", text)
    sizes = re.findall(r"\b\d+(?:\.\d+)?\s?(?:px|rem|em|pt|ch|vh|vw|ms)\b", text)
    assert not hexes and not sizes, (
        f"gui/STYLE.md restates values {hexes + sizes}; a value lives in "
        "src/rietx/viz/theme.py or gui/src/app.css, and the guide names its token"
    )
