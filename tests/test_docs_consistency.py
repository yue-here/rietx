"""The planning docs' mechanical contract (WP-1031).

The session protocol (docs/ROADMAP.md § Session protocol) asks every session
for the same bookkeeping: a controlled WP header, a WP index generated from
the headers (WP-1507; it was a hand-copied ROADMAP row until then), `###
Inherited` as a mailbox that closed WPs no longer carry, and links that
resolve.  Prose asked for it for four milestones; this file asserts
it, in the same spirit as test_manual.py (the manual cannot drift from the
code) and test_compare_ui.py (the compare registry cannot drift from the
acceptance protocols).

Everything here reads documentation files only — no data, and no rietx import
except in the agent-protocol coverage tests (WP-1105), which import the closed
vocabularies on purpose: quoting the live registry instead of restating it is
the point (the ``capabilities()`` idiom).

Size limits: every always-loaded document has a byte budget and ceiling in
`tests/rulebook_limits.py` (WP-2233).  The ceiling is checked here, on every
tree; the budget is compared against the base's table by CI's lint job.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WP_DIR = ROOT / "docs" / "wp"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
TEMPLATE = WP_DIR / "TEMPLATE.md"

# The WP header's vocabulary and its parser are the index generator's
# (WP-1507), so the tests and the index cannot read one header two ways.  The
# hook is stdlib-only and lives outside the package, so it is loaded by path.
_spec = importlib.util.spec_from_file_location(
    "wp_index", ROOT / ".claude" / "hooks" / "wp_index.py"
)
wp_index = importlib.util.module_from_spec(_spec)
# A dataclass resolves its string annotations through sys.modules.
sys.modules["wp_index"] = wp_index
_spec.loader.exec_module(wp_index)

GLYPHS = set(wp_index.GLYPHS)
# The prune rule lands with WP-1031; WPs closed after this date must have
# consumed (deleted) their ### Inherited mailbox on the way out.
_INHERITED_PRUNE_EPOCH = "2026-07-31"
# The priority rubric is TEMPLATE.md's: every ⬜ WP carries a `Priority:`
# line, a closed one carries none (its priority is moot, and the index reads
# `—`), and a 🔄 one may keep the line it had.  Backfilled 2026-09-23.
PRIORITIES = wp_index.PRIORITIES

CURRENT_FOCUS_CAP: int | None = 60  # lines within ROADMAP's Current focus (WP-1031 landed at 33; the 1060 rewrite at 44)
# Words, because a line cap alone was met by nine 1000-character paragraphs
# (measured 2026-09-01: 9 lines, ~1300 words).  The reorder landed at 210.
CURRENT_FOCUS_WORD_CAP: int | None = 300


def _wp_files() -> list[Path]:
    return wp_index.wp_files(ROOT)


def _header(path: Path):
    try:
        return wp_index.read_header(path)
    except ValueError as exc:
        pytest.fail(str(exc))


def _status_of(path: Path) -> tuple[str, str | None]:
    header = _header(path)
    return header.glyph, header.date


def test_template_declares_the_vocabulary_this_file_enforces():
    """TEMPLATE.md and this test must name the same glyphs — neither may drift."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for glyph in GLYPHS:
        assert glyph in text, f"TEMPLATE.md does not declare {glyph}"
    assert "🔶" not in text, "TEMPLATE.md declares 🔶, which practice replaced with 🔄"


def test_every_wp_status_line_is_controlled():
    for path in _wp_files():
        glyph, date = _status_of(path)
        assert glyph in GLYPHS, f"{path.name}: glyph {glyph!r} not in {GLYPHS}"
        if glyph != "⬜":
            assert date, f"{path.name}: {glyph} requires a YYYY-MM-DD date"


def test_no_two_wp_files_share_a_number():
    """Keyed by number, a second file of one number vanishes from the index
    (two sessions both took 1469 on 2026-09-27)."""
    numbers = [p.name[:4] for p in _wp_files()]
    shared = sorted({n for n in numbers if numbers.count(n) > 1})
    assert not shared, f"WP numbers used by more than one file: {shared}"


def _groups() -> list:
    return wp_index.roadmap_groups(ROADMAP.read_text(encoding="utf-8"))


def _rows(groups: list) -> dict:
    try:
        return wp_index.rows_from_headers([_header(p) for p in _wp_files()], groups)
    except ValueError as exc:
        pytest.fail(str(exc))


def test_every_wp_names_a_heading_the_roadmap_has():
    """The WP file's `Milestone:` line is the authority on where a WP stands,
    and its `Track:` line on which `####` of that section it sits under.  The
    number cannot carry this (1101-1103 opened for v1.1 and are queued for
    v1.4), which is why it is a line and a test rather than a naming rule.
    A heading the ROADMAP lacks would drop the row from the index, so the
    generator raises, naming the file and the tracks that section has.
    """
    assert _rows(_groups())


def test_the_wp_index_is_the_generators_output():
    """docs/wp/README.md is output, not a hand-maintained table (WP-1507).

    The rows used to be copied into ROADMAP by hand at every start, close and
    re-rating, and 7 of 17 conflicted ROADMAP merges in six weeks were two
    branches editing adjacent rows.  The same freshness rule as
    docs/VALIDATION.md's (test_validation_matrix.py).
    """
    index = ROOT / wp_index.INDEX
    assert index.read_text(encoding="utf-8") == wp_index.generate(ROOT), (
        f"{wp_index.INDEX} is stale: run {wp_index.COMMAND}"
    )


def test_the_index_parses_back_to_the_rows_that_wrote_it():
    """The merge driver's premise: `parse` inverts `render`.

    Git runs the driver while the tree still holds the pre-merge WP files, so
    the driver merges the three index texts row by row and renders the result
    (wp_index.py's docstring).  A cell the parser reads differently from the
    renderer would merge into a row no WP file says.
    """
    groups = _groups()
    rows = _rows(groups)
    text = wp_index.render(groups, rows)
    parsed_groups, parsed_rows = wp_index.parse(text)
    assert parsed_rows == rows
    assert wp_index.render(parsed_groups, parsed_rows) == text


_INDEX_LINK_RE = re.compile(r"\]\(wp/README\.md#([^)\s]+)\)")


def test_every_roadmap_heading_with_rows_links_them():
    """Each ROADMAP section or track with WPs links its table in the index,
    and every such link names an anchor the index has.

    The prose stayed in ROADMAP and the rows left, so the link is the only
    way from a heading's paragraph to what it describes.  A new track is a
    `####` heading, its prose, and this link.
    """
    text = ROADMAP.read_text(encoding="utf-8")
    groups = _groups()
    rows = _rows(groups)
    anchors = {g.anchor for g in wp_index.parse(wp_index.render(groups, rows))[0]}
    body = text.split("\n## Work packages", 1)[1]
    body = re.split(r"^## ", body, maxsplit=1, flags=re.M)[0]
    blocks = re.split(r"^#{3,4} ", body, flags=re.M)[1:]
    assert len(blocks) == len(groups), "ROADMAP headings and the parsed groups disagree"
    occupied = {(r.token, r.track) for r in rows.values()}
    for group, block in zip(groups, blocks):
        if (group.token, group.track) in occupied:
            assert f"](wp/README.md#{group.anchor})" in block, (
                f"ROADMAP § {group.track or group.heading} has WPs but no link to "
                f"wp/README.md#{group.anchor}"
            )
    dangling = sorted(set(_INDEX_LINK_RE.findall(text)) - anchors)
    assert not dangling, f"ROADMAP links index anchors that do not exist: {dangling}"


def test_template_declares_the_priority_vocabulary():
    """TEMPLATE.md carries the rubric; every tier this test accepts is in it."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for tier in PRIORITIES:
        assert re.search(rf"^  {tier}  ", text, re.M), (
            f"TEMPLATE.md's rubric has no row for {tier}"
        )


def test_every_not_started_wp_is_rated_and_no_closed_wp_is():
    """A ⬜ WP is rated at the write; a close deletes the line.

    A 🔄 WP may keep the line it had.  Any line present is held to the
    format by the parser, because the index's cell is read off it.
    """
    for path in _wp_files():
        header = _header(path)
        if header.tier:
            assert header.glyph not in {"✅", "🛑"}, (
                f"{path.name}: closed ({header.glyph}) and still rated — delete "
                "the Priority line (protocol step 5)"
            )
        else:
            assert header.glyph != "⬜", (
                f"{path.name}: not started and carries no Priority line (TEMPLATE.md)"
            )


def test_inherited_is_h3_and_closed_wps_have_consumed_theirs():
    """`## Inherited` (H2) is a format drift; a mailbox outliving its WP is a leak.

    The section is a channel to work that has not finished: pruned on every
    session start, deleted (fully consumed) when the WP closes.  WPs closed
    before the rule existed keep theirs as frozen archive.
    """
    for path in _wp_files():
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^## Inherited\b", text, re.M), (
            f"{path.name}: '## Inherited' must be '### Inherited' (H3)"
        )
        glyph, date = _status_of(path)
        if glyph in {"✅", "🛑"} and date and date > _INHERITED_PRUNE_EPOCH:
            # heading-anchored like the H2 check above: a WP that *mentions*
            # the section name in prose (1061 is about the handover protocol)
            # is not carrying a mailbox
            assert not re.search(r"^### Inherited\b", text, re.M), (
                f"{path.name}: closed {date} but still carries '### Inherited' — "
                "fold what was consumed into Context and delete the section "
                "(protocol step 1)"
            )


# The two entry forms TEMPLATE.md sanctions and .claude/hooks/session_start.py
# parses.  Kept as literal source here rather than imported from the hook: the
# point is that the two agree, and a shared constant could not fail.
_ENTRY_BULLET_RE = re.compile(r"^- \*\*\d{4}-\d{2}-\d{2}", re.M)
_ENTRY_HEADING_RE = re.compile(r"^#{3,4} \d{4}-\d{2}-\d{2}", re.M)


def _handover_log(path: Path) -> str | None:
    """The `## Handover log` section, bounded at the next H2 — several WPs put
    `## References` after it."""
    _, sep, log = path.read_text(encoding="utf-8").partition("\n## Handover log")
    if not sep:
        return None
    return re.split(r"^## ", log, maxsplit=1, flags=re.M)[0]


def test_every_handover_entry_is_in_a_form_the_session_hook_can_read():
    """A handover the SessionStart scan cannot see is a handover that did not
    happen — it reports the WP as owing one at the next session, and a false
    alarm teaches the reader to skip the one line that is ever load-bearing.

    Measured 2026-08-20: WP-1109 and WP-1110 had adopted `### YYYY-MM-DD`
    headings, which multi-session days need and a date bullet cannot express,
    and the hook read only bullets — so it flagged both as un-handed-over on
    the morning after three handed-over sessions.
    """
    for path in _wp_files():
        log = _handover_log(path)
        assert log is not None, f"{path.name}: no '## Handover log' section"
        assert _ENTRY_BULLET_RE.search(log) or _ENTRY_HEADING_RE.search(log), (
            f"{path.name}: the handover log has no entry in either sanctioned "
            "form — '- **YYYY-MM-DD** — …' or '### YYYY-MM-DD — …' "
            "(docs/wp/TEMPLATE.md § Handover log)"
        )
        for line in log.splitlines():
            if line.startswith("#") and not re.match(r"^#{3,4} \d{4}-\d{2}-\d{2}", line):
                raise AssertionError(
                    f"{path.name}: heading in the handover log does not open "
                    f"with a date, so the scan cannot see it: {line!r}"
                )


#: Every committed rulebook: each `CLAUDE.md`, `AGENTS.md`, and each skill
#: under `.claude/skills/` (`pr-review` names code).
RULEBOOKS = sorted(subprocess.run(
    ["git", "-C", str(ROOT), "ls-files", "*CLAUDE.md", "AGENTS.md",
     ".claude/skills/*/SKILL.md"],
    capture_output=True, encoding="utf-8", check=True).stdout.split())
# Where a path a rulebook writes may be rooted, beside the rulebook's own
# directory and each parent: `lib/plot.ts` is under gui/src, `gui/session.py`
# under src/rietx.  A path under a runtime directory names something a run
# writes, never a file in the tree.
_RULEBOOK_BASES = ("", "gui", "gui/src", "src/rietx", "src/rietx/gui", "src", "tests",
                   "docs", "docs/docs", "docs/skill/rietx", ".claude")
_RUNTIME_DIRS = ("live/", "state_dir/", "tests/output/", ".rex/", "exports/", "site/",
                 "dev/", "refs/")
# A template rather than a path: `docs/milestones/vX.Y.md`, `refs/pr/N`.
_RULEBOOK_PLACEHOLDER = re.compile(r"X\.Y|NNNN|(?:^|/)[A-Z](?:/|$)|[*<]")
_RULEBOOK_PATH = re.compile(
    r"^((?:[\w.-]+/)+[\w.-]*(?:\{[\w.,-]+\})?[\w.-]*"
    r"\.(?:ts|svelte|py|mjs|cjs|js|json|jsonl|css|md|html|yml|yaml|toml|rs))"
    r"(?:::?([\w.]+))?$"
)
# A directory: written with a trailing slash, or three segments deep with no
# extension (`src/rietx/gui/static`), which no route or prose token is.  A
# leading `/` is a GUI route or a slash command, never a path, and the first
# segment must be a word, so neither form matches.
_RULEBOOK_DIR = re.compile(r"^(?:(?:\.?[\w-]+/)+|(?:\.?[\w-]+/){2,}[\w-]+)$")
# A module and an attribute: `projects/gsas.split_records`, `refine.replay`,
# `rietx.io.read_pattern`.  Checked by `tests/code_references.py`'s resolver
# when the first segment is rietx or one of its modules.
_RULEBOOK_NAME = re.compile(r"^((?:[a-z_]\w*/)*[a-z_]\w*(?:\.[A-Za-z_]\w*)+)(?:\(\))?$")


def _rulebook_bases(rel: str) -> list[str]:
    here = Path(rel).parent
    own = [str(d) for d in (here, *here.parents) if str(d) != "."]
    return [*own, *_RULEBOOK_BASES]


def rulebook_problems(rel: str, text: str | None = None) -> list[str]:
    """Every path, test and module name in one rulebook the tree does not have."""
    from tests import code_references as cr

    if text is None:
        text = (ROOT / rel).read_text(encoding="utf-8")
    bases = _rulebook_bases(rel)
    package = "rietx" if not rel.startswith("src/rietx/") else ".".join(
        Path(rel).parent.parts[1:])
    problems = []
    for token in sorted(set(re.findall(r"`([^`\n]+)`", text))):
        if (token.startswith(_RUNTIME_DIRS) or _RULEBOOK_PLACEHOLDER.search(token)
                or token in cr.ALLOWLIST):
            continue
        if _RULEBOOK_DIR.match(token):
            if (not any(cr.in_tree(ROOT / b / token) == "dir" for b in bases)
                    and not cr.generated(token)):
                problems.append(f"`{token}`: no directory of that name")
            continue
        m = _RULEBOOK_PATH.match(token)
        if not m:
            n = _RULEBOOK_NAME.match(token)
            if n:
                name = n.group(1).replace("/", ".")
                parts = name.split(".")
                if (parts[0] in cr.rietx_top_names() and parts[-1] not in cr.PATH_EXTS
                        and not cr.resolve(name, package)
                        and not (parts[0] not in ("rietx", "rx")
                                 and set(parts[1:]) <= cr.class_attribute_names())):
                    problems.append(f"`{token}`: no such rietx name")
            continue
        path, symbol = m.groups()
        brace = re.search(r"\{([^}]+)\}", path)
        paths = ([path[:brace.start()] + alt + path[brace.end():]
                  for alt in brace.group(1).split(",")] if brace else [path])
        for p in paths:
            hits = [ROOT / b / p for b in bases if cr.in_tree(ROOT / b / p) == "file"]
            if not hits and cr.generated(p):
                continue
            if not hits:
                problems.append(f"`{token}`: no file {p}")
            elif symbol and not any(
                all(re.search(rf"\b{re.escape(part)}\b", h.read_text(encoding="utf-8"))
                    for part in symbol.split("."))
                for h in hits
            ):
                problems.append(f"`{token}`: {symbol} is not in {p}")
    return problems


@pytest.mark.parametrize("rel", RULEBOOKS)
def test_rulebook_paths_and_names_resolve(rel):
    """Every path, test and rietx name a rulebook writes exists (WP-2134, WP-2233).

    A rulebook is rules keyed by the files and names they govern, so a renamed
    file leaves a rule pointing at nothing and nothing goes red.  A bare file
    name is ambiguous and is not checked; `lib/plot.ts` is, and so is a
    directory such as `gui/scripts/`.  A `file:symbol` (or a pytest
    `file::test`) also asks that the symbol is still in that file as a whole
    word, so a comment saying "cloned" does not keep `lib/model.ts:clone`
    alive.  A `module.attr` whose first segment is rietx or one of its modules
    goes through `tests/code_references.py`'s resolver.  A GUI route or a slash
    command starts with `/` and is skipped by form.
    """
    problems = rulebook_problems(rel)
    assert not problems, (
        f"{rel} names what the tree no longer has. Rewrite the rule against the "
        "code it governs now, and put the history in the WP file:\n  "
        + "\n  ".join(problems)
    )


@pytest.mark.parametrize("token, problem", [
    ("`tests/test_deleted_long_ago.py`", "no file tests/test_deleted_long_ago.py"),
    ("`gui/scripts_gone/`", "no directory of that name"),
    ("`refine.no_such_verb`", "no such rietx name"),
    ("`tests/test_bccg.py::test_renamed_away`", "test_renamed_away is not in"),
])
def test_a_planted_rulebook_break_fails(token, problem):
    found = rulebook_problems("src/rietx/io/CLAUDE.md", f"A rule about {token}.")
    assert len(found) == 1 and problem in found[0], found


@pytest.mark.parametrize("token", [
    "`/api/params`", "`/pr-review`", "`docs/milestones/vX.Y.md`", "`refine.replay`",
    "`projects/gsas2.py`", "`report.regions`", "`docs/docs/_generated`",
])
def test_a_rulebook_route_command_or_live_name_passes(token):
    assert rulebook_problems("src/rietx/io/CLAUDE.md", f"A rule about {token}.") == []


def test_a_path_is_judged_by_what_a_commit_holds_never_the_disk(monkeypatch):
    """A build output exists in a working checkout and not in CI's, so a disk
    check passed here and failed there (`docs/docs/_generated`, PR #1757).
    The check reads git: a path ``.gitignore`` covers is generated and passes
    in both, and a file on disk that a commit would not hold fails in both."""
    from tests import code_references as cr

    # a directory-only rule over a directory absent from the disk, as
    # `docs/docs/_generated/` is in CI's clean checkout
    assert not (ROOT / "kernels" / "target").exists()
    assert cr.generated("kernels/target") and rulebook_problems(
        "src/rietx/io/CLAUDE.md", "A rule about `kernels/target`.") == []
    # a file on disk that no commit holds: under an ignored `*.rex/`, in a
    # directory of its own, so no other test sees it
    stray = ROOT / "planted_stray.rex" / "x.md"
    assert cr.generated("planted_stray.rex/x.md")
    monkeypatch.setattr(cr, "generated", lambda rel: False)
    stray.parent.mkdir()
    try:
        stray.write_text("x", encoding="utf-8")
        found = rulebook_problems("src/rietx/io/CLAUDE.md",
                                  "A rule about `planted_stray.rex/x.md`.")
    finally:
        shutil.rmtree(stray.parent)
    assert len(found) == 1 and "no file" in found[0], found


def test_template_declares_both_handover_entry_forms():
    """TEMPLATE.md is where a session learns the format; the hook and this test
    both depend on it saying the same thing."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "- **YYYY-MM-DD**" in text
    assert "### YYYY-MM-DD" in text
    assert "session_start.py" in text, (
        "TEMPLATE.md must name the hook that reads these entries — the format "
        "is a contract with it, not a house style"
    )


_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def _planning_docs() -> list[Path]:
    docs = [ROOT / "CLAUDE.md"]
    for extra in ("gui/CLAUDE.md", "tests/CLAUDE.md", "src/rietx/gui/CLAUDE.md",
                  "src/rietx/io/CLAUDE.md", "src/rietx/indexing/CLAUDE.md"):
        if (ROOT / extra).is_file():
            docs.append(ROOT / extra)
    docs += sorted((ROOT / "docs").glob("*.md"))
    # rglob, so a WP that files evidence in a directory of its own brings that
    # directory's README under the same two checks (WP-1412).
    docs += _kept_by_git(sorted((ROOT / "docs" / "wp").rglob("*.md")))
    docs += sorted((ROOT / "docs" / "milestones").glob("*.md"))
    return docs  # docs/docs/ is excluded: MyST links are sphinx's to check (-W)


def _kept_by_git(paths: list[Path]) -> list[Path]:
    """Drop what .gitignore drops: a file no clone gets is no planning doc.

    A spike's README says `npm install` in its own directory (WP-1461), which
    puts every package's README under `docs/wp/`, with links into files npm
    never shipped.  The index is consulted on purpose: a tracked file stays.
    """
    import subprocess

    # -z: without it git C-quotes a path holding a backslash or a non-ASCII
    # byte, so every Windows path, and any `é`, would never match below.
    result = subprocess.run(
        ["git", "check-ignore", "-z", "--stdin"],
        input="".join(f"{p}\0" for p in paths),
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    # 0 is "something matched", 1 is "nothing did"; anything else is git
    # declining to answer, which must not read as "nothing is ignored".
    assert result.returncode in (0, 1), (
        f"git check-ignore exited {result.returncode} and asked nothing: "
        f"{result.stderr.strip()}"
    )
    ignored = set(result.stdout.split("\0"))
    return [p for p in paths if str(p) not in ignored]


def test_every_relative_link_resolves():
    broken: list[str] = []
    for doc in _planning_docs():
        for target in _LINK_RE.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel = target.split("#", 1)[0]
            if not rel:
                continue
            if not (doc.parent / rel).exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {target}")
    assert not broken, "broken relative links:\n" + "\n".join(broken)


def test_no_planning_doc_links_something_gitignored():
    """A file a planning doc links must survive a fresh clone.

    `.gitignore` carries a blanket `*.png`, un-ignored directory by directory,
    and it has swallowed a committed image five times.  The guard written after
    the third (`tests/test_gui_manual.py`) named two directories under
    the old manual tree, so WP-1412's eighteen sheets under `docs/wp/` went past it:
    the local build was right, the commit took the README alone, and nothing
    was red.

    This asks the question one rank up and without a list.  Whatever a planning
    doc links, in whatever directory, has to be a file a clone gets — so a new
    evidence directory fails here rather than reaching a reader with its
    pictures missing.  Two answers make that true: no ignore rule drops it, and
    the index carries it.  WP-1412's sheets failed both, and an un-ignore
    committed without its files fails only the second.
    """
    import subprocess

    targets: list[Path] = []
    for doc in _planning_docs():
        for target in _LINK_RE.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel = target.split("#", 1)[0]
            if rel and (doc.parent / rel).is_file():
                targets.append(doc.parent / rel)
    assert targets, "no linked files found — the link regex or the corpus moved"
    # Repo-relative and normalised: a link's `..` stays out of what git is asked
    # and of what the index listing below is compared against.
    normalised = {Path(os.path.normpath(p)) for p in targets}
    outside = sorted(str(p) for p in normalised if not p.is_relative_to(ROOT))
    assert not outside, (
        "a planning doc links a file outside the repository:\n" + "\n".join(outside)
    )
    paths = sorted(p.relative_to(ROOT).as_posix() for p in normalised)
    # The paths go on stdin, never argv: the WP files' links outgrew Windows'
    # 32 767-character command line, and argv failed there with WinError 206
    # every night from 2026-09-28 (WP-1541).
    result = subprocess.run(
        # --no-index: check-ignore answers for a *tracked* file out of the index
        # without reading the rules, and the point here is the rules.
        ["git", "check-ignore", "-v", "-z", "--no-index", "--stdin"],
        input="".join(f"{p}\0" for p in paths),
        # git reads and writes paths as UTF-8; the locale is cp1252 on Windows.
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
    )
    # 0 is "something matched", 1 is "nothing did"; anything else is git
    # declining to answer — no repository, a path outside it — and it writes to
    # stderr, leaving an empty stdout that reads here as a pass
    # (tests/CLAUDE.md § Guards that go quiet instead of red).
    assert result.returncode in (0, 1), (
        f"git check-ignore exited {result.returncode} and asked nothing: "
        f"{result.stderr.strip()}"
    )
    # -v -z writes four fields a match: source, line number, pattern, path.
    fields = result.stdout.split("\0")[:-1]
    assert len(fields) % 4 == 0, f"unexpected check-ignore output: {result.stdout!r}"
    ignored = [
        f"{source}:{line}:{pattern}\t{path}"
        for source, line, pattern, path in zip(*[iter(fields)] * 4)
        # A `!` pattern is check-ignore reporting the un-ignore that saved it.
        if not pattern.startswith("!")
    ]
    assert not ignored, (
        "a planning doc links a file .gitignore drops:\n" + "\n".join(ignored)
    )
    # The un-ignore is half the story.  WP-1412's sheets were ignored *and*
    # never added, and a rule committed without the files it frees leaves this
    # guard green while a clone gets nothing — so ask the index too.  Absent
    # this, only CI sees it, through the missing file the link test resolves.
    # The whole index is listed rather than the paths named, for argv's reason.
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    untracked = sorted(set(paths) - set(tracked.stdout.split("\0")))
    assert not untracked, (
        "a planning doc links a file git does not track:\n" + "\n".join(untracked)
    )


def test_every_shipped_milestone_row_names_its_record():
    """A ✅ milestone row must link a record file; the link test resolves it.

    A version's record is `vX.Y.md` and a named milestone's is `<name>.md`
    (WP-1540), so the pattern takes either.
    """
    text = ROADMAP.read_text(encoding="utf-8")
    section = text.split("## Milestones", 1)[1].split("## Work packages", 1)[0]
    for line in section.splitlines():
        if not line.startswith("|") or "✅" not in line:
            continue
        assert re.search(r"\(milestones/(?:v[\d.]+|[a-z][a-z0-9-]*)\.md\)", line), (
            f"shipped milestone row without a record link: {line[:80]}"
        )


def test_always_loaded_docs_stay_under_their_ceilings():
    """Every always-loaded document has a row and sits under its ceiling.

    The limits and the rule that holds the budget against the base are
    `tests/rulebook_limits.py`'s docstring (WP-2233)."""
    from tests import rulebook_limits

    failures = rulebook_limits.ceiling_failures()
    assert not failures, "\n".join(failures)


def test_a_grown_rulebook_fails_its_ceiling_with_where_the_text_goes():
    """The planted break: CLAUDE.md's ceiling lowered under its size."""
    from tests import rulebook_limits as rl

    now = rl.size((ROOT / "CLAUDE.md").read_text(encoding="utf-8"))
    failures = rl.ceiling_failures({**rl.LIMITS, "CLAUDE.md": (now - 200, now - 100)})
    assert len(failures) == 1 and failures[0].startswith("CLAUDE.md is")
    assert "Take at least 200 B back out" in failures[0]
    assert "Cut, or move" in failures[0] and "raise" not in failures[0].lower()


def test_a_rulebook_with_no_row_fails():
    from tests import rulebook_limits as rl

    limits = {k: v for k, v in rl.LIMITS.items() if k != "AGENTS.md"}
    assert [f.split(" ", 1)[0] for f in rl.ceiling_failures(limits)] == ["AGENTS.md"]


def test_the_limits_table_names_every_always_loaded_document():
    from tests import rulebook_limits as rl

    assert set(rl.LIMITS) == set(rl.documents())
    assert rl.limits_in((ROOT / rl.REL).read_text(encoding="utf-8")) == rl.LIMITS
    assert all(budget <= ceiling for budget, ceiling in rl.LIMITS.values())


def test_current_focus_stays_a_focus_not_a_diary():
    if CURRENT_FOCUS_CAP is None:
        pytest.skip("cap pinned by the consolidation pass that measures it (WP-1031)")
    text = ROADMAP.read_text(encoding="utf-8")
    section = text.split("## Current focus", 1)[1]
    for heading in ("\n## ",):
        idx = section.find(heading)
        if idx != -1:
            section = section[:idx]
    n_lines = len(section.splitlines())
    assert n_lines <= CURRENT_FOCUS_CAP, (
        f"Current focus is {n_lines} lines (cap {CURRENT_FOCUS_CAP}).  On WP close "
        "it is rewritten, and the outgoing narrative MOVES to the in-flight "
        "milestone record (protocol rule 5) — it does not accumulate here."
    )
    n_words = len(section.split())
    assert CURRENT_FOCUS_WORD_CAP is None or n_words <= CURRENT_FOCUS_WORD_CAP, (
        f"Current focus is {n_words} words (cap {CURRENT_FOCUS_WORD_CAP}).  A "
        "shipped milestone's summary belongs in its record, not here."
    )


# ----------------------------------------------------------------------
# Release-note fragments (WP-1941)
#
# A change stages its note as docs/releases/unreleased/<id>.<section>.md, and
# the cut joins the fragments into the next release's staged notes
# (tests/release_notes.py; docs/RELEASING.md step 2).  These hold the two
# halves a stranger cannot see from one PR: that a fragment names a heading the
# staged notes have, and that a join drops nothing.
# ----------------------------------------------------------------------

from tests import release_notes  # noqa: E402


def test_every_release_note_fragment_names_a_section_of_the_staged_notes():
    head = release_notes.head_path()
    assert head.is_file(), (
        f"{head.relative_to(ROOT)} is missing; RELEASING.md step 11 opens the "
        "next release's staged notes, and every fragment is placed under them")
    head_text = head.read_text(encoding="utf-8")
    frags, problems = release_notes.read_fragments()
    problems += release_notes.check(head_text, frags, str(head.relative_to(ROOT)))
    assert not problems, "release-note fragments:\n" + "\n".join(problems)
    # The real join, once per PR that adds a note: it raises on a fragment it
    # cannot place, so the cut is not the first time a real fragment is joined.
    release_notes.join(head_text, frags)


_HEAD = """\
# rietx 9.9.0

> Staged.

## Upgrading

Code written against 9.8.0 runs unaltered.

### Code to check

- A loose bullet.
  Its second line.

- Another.

### Numbers that move

## New

- One.
- Two.

## Magnetic structures
"""


def _frag(tmp_path, name, text):
    (tmp_path / name).write_text(text, encoding="utf-8")


def test_a_join_places_each_fragment_under_its_heading(tmp_path):
    _frag(tmp_path, "12.new.md", "- Twelve.\n  Continued.\n")
    _frag(tmp_path, "3.new.md", "- Three.\n")
    _frag(tmp_path, "wp1941.new.md", "- A note filed before its PR.\n")
    _frag(tmp_path, "7.code-to-check.md", "- Seven.\n")
    _frag(tmp_path, "8.numbers-that-move.md", "- Eight.\n")
    _frag(tmp_path, "9.magnetic-structures.md", "- Nine.\n")
    _frag(tmp_path, "README.md", "# Not a fragment\n")
    frags, problems = release_notes.read_fragments(tmp_path)
    assert not problems and len(frags) == 6
    joined = release_notes.join(_HEAD, frags)
    assert joined == """\
# rietx 9.9.0

> Staged.

## Upgrading

Code written against 9.8.0 runs unaltered.

### Code to check

- A loose bullet.
  Its second line.

- Another.

- Seven.

### Numbers that move

- Eight.

## New

- One.
- Two.
- Three.
- Twelve.
  Continued.
- A note filed before its PR.

## Magnetic structures

- Nine.
"""


def test_a_fragment_naming_no_heading_or_holding_one_is_refused(tmp_path):
    """A heading, or a fence left open, would move every heading after it."""
    _frag(tmp_path, "5.fixed.md", "- No such section.\n")
    _frag(tmp_path, "6.new.md", "## New\n\n- A heading inside.\n")
    _frag(tmp_path, "7.new.md", "- An open fence.\n\n  ```\n  code\n")
    _frag(tmp_path, "8.new.md", "- A closed one.\n\n  ```python\n  # a comment\n  ```\n")
    _frag(tmp_path, "notes.md", "- No section in the name.\n")
    frags, problems = release_notes.read_fragments(tmp_path)
    assert [p.split(":")[0] for p in problems] == ["6.new.md", "7.new.md", "notes.md"]
    assert [f.path.name for f in frags] == ["5.fixed.md", "8.new.md"]
    assert release_notes.check(_HEAD, frags)[0].startswith("5.fixed.md: no heading")
    with pytest.raises(ValueError, match="5.fixed.md"):
        release_notes.join(_HEAD, frags)


def test_a_fragment_with_a_setext_underline_or_a_rule_is_refused(tmp_path):
    """`---` or `===` under a line of text makes it a heading the ATX scan does
    not see, and the join would put a new section inside the one named."""
    _frag(tmp_path, "1.new.md", "A paragraph\n---\n\n- X.\n")
    _frag(tmp_path, "2.new.md", "- Y.\n  A title\n  ===\n")
    _frag(tmp_path, "3.new.md", "- Z.\n\n---\n")
    _frag(tmp_path, "4.new.md", "- A fenced one is code.\n\n  ```\n  ---\n  ```\n")
    frags, problems = release_notes.read_fragments(tmp_path)
    assert [p.split(":")[0] for p in problems] == ["1.new.md", "2.new.md", "3.new.md"]
    assert all("heading" in p for p in problems)
    assert [f.path.name for f in frags] == ["4.new.md"]


def test_a_fragment_for_a_section_the_new_staged_notes_lack_says_how_to_mend_it(tmp_path):
    """A branch that forked before a cut can merge a note for a section the
    next staged file does not open; the refusal names the file and the remedy."""
    _frag(tmp_path, "1700.foreign-files.md", "- A note.\n")
    frags, _ = release_notes.read_fragments(tmp_path)
    [problem] = release_notes.check(_HEAD, frags, "docs/releases/9.9.0.md")
    assert "docs/releases/9.9.0.md" in problem and "'foreign-files'" in problem
    assert "rebase onto main" in problem


def test_one_bullet_notes_in_a_section_that_starts_empty_join_as_a_tight_list(tmp_path):
    """Every section of a freshly opened staged file is empty, so this is the
    usual case: separate PRs' notes make one list, not paragraphs."""
    _frag(tmp_path, "1700.magnetic-structures.md", "- A.\n")
    _frag(tmp_path, "1701.magnetic-structures.md", "- B.\n  Continued.\n")
    _frag(tmp_path, "1702.magnetic-structures.md", "- C.\n")
    _frag(tmp_path, "1703.numbers-that-move.md", "- D.\n")
    _frag(tmp_path, "1704.numbers-that-move.md", "- E.\n\n- F, loose.\n")
    _frag(tmp_path, "1705.numbers-that-move.md", "- G.\n")
    frags, _ = release_notes.read_fragments(tmp_path)
    joined = release_notes.join(_HEAD, frags)
    assert joined.endswith("## Magnetic structures\n\n- A.\n- B.\n  Continued.\n- C.\n")
    # Once a note brings a blank-separated pair, the section is loose from there on.
    assert "### Numbers that move\n\n- D.\n- E.\n\n- F, loose.\n\n- G.\n\n## New" in joined


def _blocks(lines):
    """A section's text as its blocks: each bullet with its continuation, each paragraph."""
    blocks, cur = [], []
    for line in lines:
        if not line.strip() or release_notes.BULLET.match(line):
            if cur:
                blocks.append(" ".join(s.strip() for s in cur))
            cur = [line] if line.strip() else []
        else:
            cur.append(line)
    if cur:
        blocks.append(" ".join(s.strip() for s in cur))
    return blocks


def _by_section(text):
    lines = text.splitlines()
    marks = release_notes.headings(lines)
    return {name: sorted(_blocks(lines[i + 1:(marks[k + 1][0] if k + 1 < len(marks)
                                                  else len(lines))]))
            for k, (i, _, name) in enumerate(marks)}


# A released file never changes, so the round trip always has bullets to split;
# the live staged file opens with none (RELEASING.md step 11) and may stay so,
# since notes now go to fragments.
_ROUND_TRIP_HEADS = {"released-1.11.0": ROOT / "docs" / "releases" / "1.11.0.md", "live": None}


@pytest.mark.parametrize("which", list(_ROUND_TRIP_HEADS))
def test_the_staged_notes_split_into_fragments_join_back_section_for_section(which, tmp_path):
    """The acceptance: every bullet of a staged-notes file moved into a
    fragment of its own, joined onto what is left, gives the same sections."""
    head = _ROUND_TRIP_HEADS[which] or release_notes.head_path()
    head_text = head.read_text(encoding="utf-8")
    lines = head_text.splitlines()
    marks = release_notes.headings(lines)
    kept, n = lines[:marks[0][0]], 0
    for k, (start, _, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        kept.append(lines[start])
        item: list[str] = []
        for line in lines[start + 1:end] + [""]:
            if item and (not line.strip() or release_notes.BULLET.match(line)):
                n += 1
                _frag(tmp_path, f"{n}.{name}.md", "\n".join(item) + "\n")
                item = []
            if release_notes.BULLET.match(line) or (item and line.strip()):
                item.append(line)
            elif not item:
                kept.append(line)
    if n < 2 and which == "live":
        pytest.skip(f"{head.relative_to(ROOT)} holds {n} bullet(s); the released file "
                    "carries the round trip")
    assert n >= 2, f"{head.relative_to(ROOT)} holds under two bullets; nothing was split"
    frags, problems = release_notes.read_fragments(tmp_path)
    assert not problems and len(frags) == n
    joined = release_notes.join("\n".join(kept) + "\n", frags)
    assert _by_section(joined) == _by_section(head_text)
    assert release_notes.sections(joined) == release_notes.sections(head_text)


def test_a_freshly_opened_staged_file_skips_the_live_round_trip(tmp_path, monkeypatch):
    """1.12.0.md as step 11 opened it: headings, no bullets.  The live arm must
    skip there, not fail, or every PR goes red from the day after a cut."""
    opened = tmp_path / "9.9.0.md"
    opened.write_text("# rietx 9.9.0\n\n> Staged.\n\n## Upgrading\n\n### Code to check\n\n"
                      "## New\n\n## Changed\n", encoding="utf-8")
    monkeypatch.setattr(release_notes, "head_path", lambda *a, **k: opened)
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    (tmp_path / "frags").mkdir()
    with pytest.raises(pytest.skip.Exception, match="holds 0 bullet"):
        test_the_staged_notes_split_into_fragments_join_back_section_for_section(
            "live", tmp_path / "frags")


# ----------------------------------------------------------------------
# Agent-protocol coverage (WP-1105, re-pointed at the skill tree by WP-1304)
#
# Root CLAUDE.md's rule — "a WP that adds a diagnostic code or a correction
# adds its row there" — was enforced by nothing, and the drift it permits is
# silent: two engine codes shipped without a row and no test went red.  These
# three tests give the rule teeth.  They deliberately import the closed
# vocabularies rather than restating them, so a new member fails coverage the
# day it lands.
#
# The document is now a directory (`docs/skill/rietx/`), so what these read is
# the **concatenation** of every file in it.  That is the right denominator for
# all three: a code's row may sit in any reference file, and a citation's
# journal is given at its first mention *somewhere in the document*, which the
# split moved across files without changing what the reader has available.
# ----------------------------------------------------------------------

SKILL_TREE = ROOT / "docs" / "skill" / "rietx"
SRC = ROOT / "src" / "rietx"
REFERENCES_BIB = ROOT / "docs" / "docs" / "references.bib"

#: Diagnostic codes the AST walk below cannot see statically, each mapped to a
#: comment naming its emitter.  Empty today: every engine code is a
#: ``code="..."`` keyword literal.  A code built dynamically (f-string,
#: constant indirection) goes here — never silently uncovered.
STATIC_INVISIBLE_CODES: dict[str, str] = {}


def _protocol_text() -> str:
    """Every `.md` in the skill tree, concatenated — body and references."""
    paths = sorted(SKILL_TREE.rglob("*.md"))
    assert paths, f"no skill files under {SKILL_TREE}"
    return "\n".join(p.read_text(encoding="utf-8") for p in paths)


def _engine_codes() -> set[str]:
    """Every UPPER_SNAKE ``code="..."`` keyword literal under src/rietx.

    One walk with CI's changed-surface report (``tests.skill_surface``), which
    runs it on a base revision's text; ``is_engine_source`` says why ``gui/``
    is excluded.  The lowercase ``GateFailure`` codes fall out of the shape
    filter and are covered by the vocabulary test instead.
    """
    import ast

    from tests.skill_surface import diagnostic_codes, is_engine_source

    codes: set[str] = set()
    for py in sorted(SRC.rglob("*.py")):
        rel = py.relative_to(ROOT).as_posix()
        if is_engine_source(rel):
            codes |= diagnostic_codes(
                ast.parse(py.read_text(encoding="utf-8"), filename=str(py)))
    return codes


def test_every_vocabulary_member_appears_in_the_protocol():
    """Every ``GateCode`` and ``ActionKind`` member has protocol coverage.

    WP-1003 promoted gate failures to typed codes precisely so a consumer can
    branch on the name; a member the protocol never names is a branch the
    consumer cannot learn.  The §6 gate table and the §5 action table are the
    rows this asserts exist (as backticked mentions, so a passing rename
    cannot hide in prose).
    """
    from typing import get_args

    from rietx.report.schemas import ActionKind, GateCode

    members = (*get_args(GateCode), *get_args(ActionKind))
    assert len(members) >= 22, "vocabulary import broke — Literals moved?"
    text = _protocol_text()
    missing = [m for m in members if f"`{m}`" not in text]
    assert not missing, (
        f"vocabulary members with no mention in the skill tree: {missing} — "
        "add the row to references/abstention.md's gate table or "
        "references/numbers.md's action table"
    )


def test_every_engine_diagnostic_code_has_a_protocol_row():
    """Root CLAUDE.md: a WP that adds a diagnostic code adds its row there.

    Collector liveness was proven the required way round (WP-1105): run
    against the tree before the rows landed, it failed on exactly the two
    codes known to be missing (EXTINCTION_SCREEN_FAILED,
    INDEX_VALIDATION_FAILED) out of 79 collected.
    """
    # the envelope's four ``ERROR_CODES`` were in this union until WP-1303
    # deleted them with the envelope; what remains is every code the engine
    # itself emits, plus the ones no AST walk can see
    codes = _engine_codes() | set(STATIC_INVISIBLE_CODES)
    assert len(codes) >= 60, (
        f"only {len(codes)} codes collected — the AST walk broke, it does not "
        "mean the protocol got shorter"
    )
    text = _protocol_text()
    missing = sorted(c for c in codes if f"`{c}`" not in text)
    assert not missing, (
        f"engine diagnostic codes with no row in the skill tree: {missing} — "
        "add each to the references/ table its family lives in "
        "(root CLAUDE.md's rule)"
    )


_WP_REF = re.compile(r"\bWP-(\d{4})\b")
_CITE_NAME = r"[A-Z][A-Za-zöëüéèçå'-]+"
# an author chain ("Hill", "Hill & Flack", "Madsen et al.", "Dreele, Cox,
# Louër & Scardi") followed by a year that is not part of a date
_CITATION = re.compile(
    rf"({_CITE_NAME}(?:'s)?(?:,? (?:&|and) {_CITE_NAME}|, {_CITE_NAME}"
    rf"|,? et al\.?)*),? \(?((?:18|19|20)\d{{2}})(?![-\d])")


def test_every_wp_and_citation_the_protocol_names_resolves():
    """WP-1104 verified both halves by hand; this is what stops the redrift.

    Every ``WP-NNNN`` named inline exists as a WP file, and every author-year
    citation resolves where the protocol's See-also says it does: in the
    manual's bibliography, or inline (its journal follows the year at first
    mention — ``1992, *J. Appl. Cryst.* ...``).  The chain's *whole* author
    list is consulted against the bib, so a partial regex match ("Scardi,
    1999" out of the five-author McCusker reference) still resolves to the
    right entry.
    """
    text = _protocol_text()

    missing_wps = sorted({n for n in set(_WP_REF.findall(text))
                          if not list(WP_DIR.glob(f"{n}-*.md"))})
    assert not missing_wps, f"WPs named with no docs/wp file: {missing_wps}"

    bib = REFERENCES_BIB.read_text(encoding="utf-8")
    entries = []  # (author field lowercased, year) per entry
    for block in bib.split("\n@"):
        author = re.search(r"author\s*=\s*\{([^}]*)\}", block)
        year = re.search(r"year\s*=\s*\{(\d{4})\}", block)
        if author and year:
            entries.append((author.group(1).lower(), year.group(1)))
    assert len(entries) > 50, "references.bib parse broke"

    unresolved: list[str] = []
    for m in _CITATION.finditer(text):
        chain, year = m.group(1), m.group(2)
        surnames = [s[:-2] if s.endswith("'s") else s
                    for s in re.findall(_CITE_NAME, chain) if s != "Von"]
        in_bib = any(y == year and any(s.lower() in a for s in surnames)
                     for a, y in entries)
        inline = any(
            re.search(rf"{re.escape(s)}[^\n]*?\(?{year}[a-z]?,\s*\*", text)
            for s in surnames)
        if not (in_bib or inline):
            unresolved.append(f"{chain}, {year}")
    assert not unresolved, (
        "author-year citations resolving neither in docs/docs/references.bib "
        f"nor inline: {sorted(set(unresolved))}"
    )
