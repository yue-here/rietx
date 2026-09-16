"""The planning docs' mechanical contract (WP-1031).

The session protocol (docs/ROADMAP.md § Session protocol) asks every session
for the same bookkeeping: a controlled Status line, a ROADMAP index row that
mirrors it, `### Inherited` as a mailbox that closed WPs no longer carry, and
links that resolve.  Prose asked for it for four milestones; this file asserts
it, in the same spirit as test_manual.py (the manual cannot drift from the
code) and test_compare_ui.py (the compare registry cannot drift from the
acceptance protocols).

Everything here reads documentation files only — no data, and no rietx import
except in the agent-protocol coverage tests (WP-1105), which import the closed
vocabularies on purpose: quoting the live registry instead of restating it is
the point (the ``capabilities()`` idiom).

Size caps: SIZE_CAPS pins each always-loaded document to its measured size
plus headroom.  A cap of None means "not yet pinned" (the consolidation pass
that measures it also pins it); the failure message names the demotion
destination, because the fix is to move narrative, never to delete facts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WP_DIR = ROOT / "docs" / "wp"
ROADMAP = ROOT / "docs" / "ROADMAP.md"
TEMPLATE = WP_DIR / "TEMPLATE.md"

GLYPHS = {"⬜", "🔄", "✅", "🛑"}
# ⬜ carries no date; every other glyph must say when.
_STATUS_RE = re.compile(
    r"Status: (?P<glyph>⬜|🔄|✅|🛑)"
    r"(?: (?P<date>\d{4}-\d{2}-\d{2}))?"
    r"(?: — |$)",
    re.MULTILINE,
)
# The prune rule lands with WP-1031; WPs closed after this date must have
# consumed (deleted) their ### Inherited mailbox on the way out.
_INHERITED_PRUNE_EPOCH = "2026-07-31"

# Always-loaded documents: measured size + headroom, pinned by the pass that
# achieved it.  Raising a cap is a decision about every future session's fixed
# cost -- make it in a commit that says so, not as a side effect.  Do not
# delete facts to fit a cap: move narrative to the WP file or the milestone
# record (the assertion message says where).  The admission rule the caps
# enforce: a line enters one of these files only as a standing rule a
# stranger needs in six months, evidence compressed to one clause plus a
# pointer (protocol rule 4); an index row is the one line a new WP cannot
# demote (the bijection test), so ROADMAP's cap grows with the WP count and
# with nothing else.
#
# Every bump, one line: date, file, old -> new, what paid for it.  The
# reasoning behind each is docs/milestones/process.md § The caps diary,
# verbatim; a new bump adds a row here and a paragraph there.
#
#     gui/CLAUDE.md                 879 -> 902  for WP-1214
#     gui/CLAUDE.md                 902 -> 938  for WP-1215
#     gui/CLAUDE.md                 938 -> 962  for WP-1216
#     gui/CLAUDE.md                 962 -> 995  for WP-1217
#     gui/CLAUDE.md                 995 -> 1019 for WP-1017
#     src/rietx/io/CLAUDE.md        294 -> 300  for WP-1118
#   2026-08-14  CLAUDE.md                     600 -> 620  for WP-1067
#   2026-08-14  CLAUDE.md                     620 -> 625  for WP-1068
#   2026-08-15  CLAUDE.md                     625 -> 644  for WP-1070
#   2026-08-15  CLAUDE.md                     648 -> 656  for WP-1071
#   2026-08-15  CLAUDE.md                     656 -> 670  for WP-1072
#   2026-08-15  CLAUDE.md                     670 -> 683  for WP-1073
#   2026-08-15  tests/CLAUDE.md               180 -> 198  for WP-1070
#   2026-08-16  CLAUDE.md                     683 -> 700  for WP-1074
#   2026-08-16  tests/CLAUDE.md               198 -> 205  for WP-1003
#   2026-08-18  CLAUDE.md                     700 -> 720  for WP-1076
#   2026-08-18  docs/ROADMAP.md               400 -> 416  for the agentic-report planning session
#   2026-08-20  CLAUDE.md                     720 -> 736  for WP-1109
#   2026-08-20  CLAUDE.md                     736 -> 752  for WP-1110
#   2026-08-20  docs/ROADMAP.md               416 -> 438  for the refinement-speed planning session
#   2026-08-20  docs/ROADMAP.md               438 -> 439  for WP-1116
#   2026-08-20  tests/CLAUDE.md               205 -> 223  for WP-1110
#   2026-08-21  CLAUDE.md                     752 -> 759  for WP-1110
#   2026-08-21  CLAUDE.md                     759 -> 771  for WP-1110 item 14
#   2026-08-21  docs/ROADMAP.md               439 -> 455  for WP-1110
#   2026-08-21  src/rietx/indexing/CLAUDE.md  280 -> 296  for WP-1110 item 14
#   2026-08-22  CLAUDE.md                     771 -> 784  for WP-1120
#   2026-08-22  CLAUDE.md                     784 -> 804  for WP-1115
#   2026-08-22  CLAUDE.md                     804 -> 817  for WP-1121
#   2026-08-22  CLAUDE.md                     817 -> 833  for WP-1123
#   2026-08-22  CLAUDE.md                     833 -> 834  for WP-1122
#   2026-08-22  CLAUDE.md                     834 -> 845  for WP-1125
#   2026-08-22  CLAUDE.md                     845 -> 855  for WP-1127
#   2026-08-22  docs/ROADMAP.md               455 -> 457  the two probe rows the solver-survey
#   2026-08-22  docs/ROADMAP.md               457 -> 458  for WP-1126
#   2026-08-22  docs/ROADMAP.md               458 -> 459  for WP-1127
#   2026-08-22  tests/CLAUDE.md               223 -> 232  for WP-1115
#   2026-08-23  docs/ROADMAP.md               459 -> 473  for WP-1131
#   2026-08-24  docs/ROADMAP.md               473 -> 474  for WP-1132
#   2026-08-25  CLAUDE.md                     855 -> 869  for WP-1204
#   2026-08-25  CLAUDE.md                     869 -> 882  for WP-1202
#   2026-08-25  docs/ROADMAP.md               473 -> 480  for the v1.2 opening
#   2026-08-25  docs/ROADMAP.md               474 -> 475  for WP-1134
#   2026-08-25  docs/ROADMAP.md               480 -> 482  merging PR #108 into the v1.2 opening
#   2026-08-25  gui/CLAUDE.md                 580 -> 612  for WP-1201
#   2026-08-25  gui/CLAUDE.md                 612 -> 628  for WP-1204
#   2026-08-26  gui/CLAUDE.md                 645 -> 663  for WP-1205
#   2026-08-26  gui/CLAUDE.md                 628 -> 645  for WP-1203
#   2026-08-26  gui/CLAUDE.md                 663 -> 687  for WP-1206
#   2026-08-26  gui/CLAUDE.md                 691 -> 710  for WP-1207
#   2026-08-26  tests/CLAUDE.md               232 -> 246  rung 3 is exclusive across the sessions sharing
#   2026-08-27  CLAUDE.md                     882 -> 890  for the one-session-per-tree tooling
#   2026-08-27  gui/CLAUDE.md                 710 -> 733  for WP-1208
#   2026-08-27  gui/CLAUDE.md                 733 -> 753  for WP-1209
#   2026-08-27  gui/CLAUDE.md                 753 -> 774  for WP-1210
#   2026-08-27  gui/CLAUDE.md                 778 -> 808  for WP-1211
#   2026-08-27  gui/CLAUDE.md                 808 -> 838  for WP-1212
#   2026-08-27  gui/CLAUDE.md                 840 -> 874  for WP-1213
#   2026-08-27  src/rietx/io/CLAUDE.md        271 -> 294  for WP-1118
#   2026-08-28  CLAUDE.md                     890 -> 898  for WP-1017
#   2026-08-28  docs/ROADMAP.md               482 -> 503  queuing v1.3, agents and programs
#   2026-08-28  tests/CLAUDE.md               246 -> 253  for WP-1017
#   2026-08-29  CLAUDE.md                     898 -> 906  for WP-1306
#   2026-08-29  src/rietx/io/CLAUDE.md        250 -> 271  for WP-1306
#   2026-09-01  CLAUDE.md                     906 -> 760  for the compression pass, which is the direction
#   2026-09-01  CLAUDE.md                     760 -> 722  for the placement pass, the compression pass's
#   2026-09-01  docs/ROADMAP.md               503 -> 510  for issues #192-198
#   2026-09-01  docs/ROADMAP.md               510 -> 578  for the issue triage
#   2026-09-01  docs/ROADMAP.md               578 -> 589  for the triage's second batch
#   2026-09-01  gui/CLAUDE.md                1019 -> 1028 for the placement pass
#   2026-09-01  src/rietx/indexing/CLAUDE.md  296 -> 300  for the placement pass
#   2026-09-01  tests/CLAUDE.md               253 -> 275  for the placement pass
#   2026-09-01  docs/ROADMAP.md               589 -> 597  for the roadmap reorder: landed 573, cap landed + 24
#   2026-09-02  docs/ROADMAP.md               597 -> 621  for the magnetic scattering track (1326-1329, out of
#                                                          the v2 fence): a section and four rows, landed 597, cap landed + 24
#   2026-09-02  CLAUDE.md                     722 -> 723  for WP-1131's two rules and the handover-trigger note
#                                                          (PRs #227, #228), which landed at 723 with no bump; repaired in #229
#   2026-09-02  CLAUDE.md                     723 -> 732  for WP-1330's skill bullet: the three destinations
#                                                          and the shape rule, landed at the cap
#   2026-09-03  docs/ROADMAP.md               621 -> 645  for the 2026-09-03 issue triage (1332-1341): ten rows
#                                                          across three existing sections and one new one, landed 641
#   2026-09-08  docs/ROADMAP.md               645 -> 648  for WP-1343 (issue #277, the magnetic
#                                                          scattering track's fifth rung): one row, and its
#                                                          section's paragraph one line longer; landed 647
#   2026-09-13  docs/ROADMAP.md               648 -> 672  for the live-watcher track (1401-1406): six
#                                                          rows in one new section, its paragraph cut to the
#                                                          rungs' order and the one surface decision, the rest
#                                                          left in the WP files; landed 670
#   2026-09-13  docs/ROADMAP.md               676 -> 682  for WP-1407: one row in one new Unscheduled
#                                                          group ("The formats a lab still has") plus the
#                                                          two-line blurb every group in that section
#                                                          carries; landed 678, +4 headroom so the next
#                                                          few index rows do not each need a cap commit
#   2026-09-14  docs/ROADMAP.md               682 -> 688  for WP-1409: one index row, the +4 headroom of
#                                                          2026-09-13 having been spent by 1408's row and
#                                                          the v1.4 ship; landed 683
#   2026-09-14  docs/ROADMAP.md               688 -> 694  for WP-1411 and the survey it filed, 1412:
#                                                          two index rows, and the Current focus sentence
#                                                          naming them paid for by two cuts in the same
#                                                          section; landed 690, +4 headroom again
#   2026-09-15  docs/ROADMAP.md               694 -> 707  for the 2026-09-15 issue triage (1413-1420):
#                                                          eight index rows across five existing sections,
#                                                          one sentence per section naming them, the
#                                                          magnetic track's landed layer, and #258 on the
#                                                          fence; the Current focus paragraph was cut to
#                                                          pay for its own sentence; landed 706, +1 headroom
SIZE_CAPS: dict[str, int | None] = {
    # 739 -> 755 (WP-1102): two standing rules for the component seam — that an
    # additive non-Bragg term is a union *member* and not a new field, and that
    # a renamed dot-path is migrated on the document text. Neither is narrative
    # that could be demoted to a WP file: both govern work outside the WP that
    # measured them, which is protocol rule 4's test. Raised rather than shaved,
    # per the failure message's own instruction not to delete facts to fit.
    # 755 -> 766 (WP-1402): two standing rules for the live view — that it is
    # numbers a viewer draws rather than a page the fit builds, and that a page
    # quoted inside python is syntax-checked with `node --check`. Both govern
    # work outside the WP that measured them: the first any future writer of a
    # live view, the second `compare_app.py` as much as `watch.py`, where a
    # stray escape cost a whole page load with every python test green. Raised
    # rather than shaved, per the failure message's own instruction. Landed at
    # 765; the +1 is headroom, per this file's docstring.
    # 766 -> 793 (WP-1403): two standing rules for automatic run recording —
    # that every fit records itself and telemetry never breaks a fit, and that
    # retention deletes by age and size rather than by count.  The first is the
    # larger clause in the file and it earns the room: it governs anyone
    # touching `fit`'s control flow, and its who-asked failure boundary reads as
    # a flat contradiction of `history/events.py`'s stated rule until both
    # halves are written down, which is exactly the reconciliation a later
    # session would otherwise make in the wrong direction.  The second governs
    # the only code in the package that can destroy a user's data.  Neither is
    # demotable narrative: both are protocol rule 4's test, governing work
    # outside the WP that measured them.  Raised rather than shaved, per the
    # failure message's own instruction.  Landed at 795 after the review pass
    # added the fourth clause of the first rule — that an internal trial the
    # package discards passes ``telemetry=False`` — which is the rule one
    # report build writing four run directories cost; the headroom is +2.
    # 797 -> 811 (WP-1405): one standing rule for the cross-process stop, and
    # two lines on the `node --check` clause.  It governs work outside its own
    # WP three ways, which is protocol rule 4's test.  WP-1404 is *queued* and
    # its stage-boundary configuration would silently make the cancel probe fire
    # once a stage unless the evaluation-boundary rule is written where that
    # session will read it.  `_abandon_on_cancel`'s docstring promised an
    # ordinary fit paid nothing and no longer can, so the withdrawal belongs
    # where someone reading `fit`'s control flow meets it.  And "who asked is a
    # fact about the record, never about the exception" is the refusal a later
    # session would otherwise undo by adding a field to `RefinementCancelled`,
    # which looks obviously useful until you see that the fit cannot tell.  The
    # layout half is the second thing `node --check` cannot see, beside the
    # first: it belongs on that clause, not in a clause of its own.  Raised
    # rather than shaved, per the failure message's own instruction.  Landed at
    # 809; the headroom is +2.
    # 811 -> 823 (WP-1422): one standing rule for the WP claim, the peer of the
    # one-session-per-tree clause it sits beside and bumped for the same reason
    # (2026-08-27, 882 -> 890).  It governs every session rather than the WP
    # that measured it, which is protocol rule 4's test, and three of its
    # clauses are ones a later session would otherwise undo: that the answer is
    # *derived* and the store only sharpens it, so nobody adds a ritual claim
    # step; that a claim dies with its worktree, so nobody writes an expiry
    # policy; and that this is the workflow's one refusal, so nobody softens it
    # to a report on the general principle that the rest of the scan reports.
    # Landed at 821; the headroom is +2.
    # 823 -> 833 (WP-1422, same session): the contributor half, which is a
    # different mechanism rather than more of the same one and cannot fold into
    # the clause above.  A local claim and an `origin` branch are both blind to
    # a fork, so the rule that a contributor is reached through the issues a WP
    # cites belongs where a session meets it — and with it the two clauses that
    # stop it being misused: an issue link is evidence and never proof, so
    # nothing refuses on it, and it needs the network, so it stays out of the
    # SessionStart hook that has to survive being offline.  Landed at 831; the
    # headroom is +2.
    "CLAUDE.md": 833,
    # 672 -> 676 (WP-1102): the Current focus rewrite at 1102's close names the
    # milestone's one break and what makes 1103 the seam's proving case.
    # 676 -> 682 (WP-1407): a new Unscheduled group, "The formats a lab still
    # has".  Its two-line blurb is the one part that cannot be demoted to the WP
    # file: every group in this section carries one, so a group without it does
    # not match the document.  Raised for the blurb only; the WP's own findings
    # stayed in the WP file.  Landed at 678: the +4 is headroom, per this file's
    # docstring ("measured size plus headroom"), because an index row is the one
    # line a new WP cannot demote and a zero-headroom cap makes the next row a
    # cap commit of its own.
    # 682 -> 688 (WP-1409): that headroom is spent, on 1408's row and the v1.4
    # ship pass.  One index row again, and the Current focus paragraph it
    # replaces is shorter than the one it names.  Landed at 683.
    # 688 -> 694 (WP-1411): two index rows, because the WP filed a second one
    # (1412, the theme survey) on finding furo was never compared.  A row is the
    # one line a WP cannot demote.  The two lines of Current focus that name
    # them were paid for inside that section, under a word cap the additions had
    # already broken: the v1.4 row's own "seventeen acceptance rows" and a
    # clause restating that no milestone is open.  Landed at 690.
    # 694 -> 707 (the 2026-09-15 triage): eight rows for 1413-1420, landed 706.
    # 707 -> 710: a merge race, not new content.  The triage branch and
    # WP-1404's branch were both measured against 694 and merged within
    # seventeen seconds of each other, so each cap was right and their sum was
    # not: 706 plus 1404's rewritten Current focus paragraph is 708.  Nothing
    # here is demotable — eight index rows, and the focus paragraph that names
    # the one open item of the watcher track.  The same race gave both branches
    # the number 1413; the triage's is renumbered 1421.  The headroom is +2.
    "docs/ROADMAP.md": 710,
    "gui/CLAUDE.md": 1028,
    "tests/CLAUDE.md": 275,
    "src/rietx/indexing/CLAUDE.md": 300,
    # 300 -> 350 (WP-1407): four per-format rows, and three standing rules the
    # Philips √ encoding taught — that a format may encode its counts rather
    # than store them, that the *permissive* description can be the defective
    # one so a description is checked against a file before it is believed, and
    # that a refusal claims only what its evidence allows (three tiers, with a
    # claims-nothing entry sitting below every reader). None is narrative that
    # could be demoted: each governs the next format anyone adds, which is
    # protocol rule 4's test. The WP's own measurements stayed in
    # tests/data/README.md, and the blocks were cut by a third before the cap
    # was touched — per this test's own instruction not to delete facts to fit.
    #
    # 2026-09-13, 350 -> 368 for WP-1118's model-format registry. Three rules,
    # and each governs the next project reader rather than describing this one:
    # what the registry's unit is (so a reader carrying no model is placed
    # before it is written, which is the question read_gsas_prm raised and
    # nothing answered); that the answer is the format's own model rather than a
    # union with blanks; and that where a format reports its repairs is declared
    # and pinned against the signature, a wrong value being silent rather than
    # loud. The section's existing two rules were not cut to fit.
    #
    # 2026-09-15, 368 -> 383 for WP-1118's column rewrite of `read_gsas_prm`.
    # Two rules, each governing the next project reader rather than this one.
    # That staying outside the registry is about *dispatch* and never about
    # parsing is the clause a session adding a second file kind of a format
    # already read — a GSAS-II `.gpx` beside an `.instprm`, Jana's `.m50`/`.m40`
    # trio (WP-1314) — would otherwise have to rediscover, and the way it is
    # rediscovered is a second parser for one record, which is what this WP
    # spent a session undoing. That a refusal's reason can expire is the check
    # nobody runs: a parser's *reads* are tested and its refusals are prose, so
    # "no file establishes this" sat in the doublet refusal after the file
    # establishing it had been committed. Both are protocol rule 4's test.
    # Raised rather than shaved, per the failure message's own instruction.
    # Landed at 381; the headroom is +2.
    #
    # 2026-09-16, 383 -> 410 for WP-1118's GSAS-II `.gpx` reader, the first
    # member of either registry that is **binary and executable**. Three rules,
    # each governing the next reader rather than describing this one: that a
    # reader which runs what it reads resolves an allow-list and refuses a name
    # rather than a record (with the two measurements that shape such a list —
    # a stand-in for the vendor's own classes, and that one archive cannot
    # produce it); that a binary format's sniff cannot be its magic bytes, since
    # a third of a real corpus does not write them; and that a conversion builds
    # every schema object inside one guard, which is the class `read_gsas_prm`'s
    # repair opened and this closes. The section's existing rules were not cut.
    "src/rietx/io/CLAUDE.md": 410,
}
CURRENT_FOCUS_CAP: int | None = 60  # lines within ROADMAP's Current focus (WP-1031 landed at 33; the 1060 rewrite at 44)
# Words, because a line cap alone was met by nine 1000-character paragraphs
# (measured 2026-09-01: 9 lines, ~1300 words).  The reorder landed at 210.
CURRENT_FOCUS_WORD_CAP: int | None = 300


def _wp_files() -> list[Path]:
    return sorted(p for p in WP_DIR.glob("[0-9]*.md"))


def _status_of(path: Path) -> tuple[str, str | None]:
    text = path.read_text(encoding="utf-8")
    m = _STATUS_RE.search(text)
    assert m, f"{path.name}: no Status line matching the TEMPLATE format"
    return m.group("glyph"), m.group("date")


def _index_rows() -> dict[str, tuple[str, str]]:
    """WP id -> (linked filename, status cell) from every ROADMAP index row."""
    rows: dict[str, tuple[str, str]] = {}
    row_re = re.compile(r"^\| \[(\d{4})\]\((wp/[^)]+\.md)\) \|")
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        m = row_re.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.split("|")]
        # cells[0] is '' before the leading pipe; status is the third column
        assert len(cells) >= 5, f"ROADMAP row for {m.group(1)} has too few cells"
        assert m.group(1) not in rows, f"ROADMAP indexes WP {m.group(1)} twice"
        rows[m.group(1)] = (m.group(2), cells[3])
    return rows


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


def test_wp_files_and_roadmap_rows_are_a_bijection():
    rows = _index_rows()
    files = {p.name[:4]: p for p in _wp_files()}
    missing_rows = sorted(set(files) - set(rows))
    missing_files = sorted(set(rows) - set(files))
    assert not missing_rows, f"WP files with no ROADMAP index row: {missing_rows}"
    assert not missing_files, f"ROADMAP rows with no WP file: {missing_files}"
    for wp_id, (link, _cell) in rows.items():
        assert (ROOT / "docs" / link).is_file(), f"row {wp_id} links {link}, not a file"
        assert link == f"wp/{files[wp_id].name}", (
            f"row {wp_id} links {link}, file is wp/{files[wp_id].name}"
        )


def test_roadmap_glyph_mirrors_the_wp_status_line():
    rows = _index_rows()
    for wp_id, path in ((p.name[:4], p) for p in _wp_files()):
        file_glyph, _ = _status_of(path)
        cell = rows[wp_id][1]
        cell_glyphs = [g for g in cell if g in GLYPHS]
        assert cell_glyphs, f"ROADMAP row {wp_id}: status cell {cell!r} has no glyph"
        assert cell_glyphs[0] == file_glyph, (
            f"WP {wp_id}: file says {file_glyph}, ROADMAP row says {cell_glyphs[0]}"
        )


_MILESTONE_LINE_RE = re.compile(r"^Milestone: (\S+) ·", re.M)
_SECTION_RE = re.compile(r"^### (v\d+\.\d+(?:\.x)?|Unscheduled|v2\+)(?=\s|$)", re.M)


def _index_sections() -> dict[str, str]:
    """WP id -> the milestone token of the `###` section its row sits under.

    Sub-headings (`####`) group rows inside a section and carry no token.
    """
    text = ROADMAP.read_text(encoding="utf-8").split("## Work packages", 1)[1]
    row_re = re.compile(r"^\| \[(\d{4})\]\(wp/")
    sections: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("### "):
            m = _SECTION_RE.match(line)
            assert m, (
                f"ROADMAP section {line!r} does not open with a milestone token "
                "(vN.N, vN.N.x, Unscheduled, v2+) — every section under Work "
                "packages is one milestone's, so a row's section can be checked "
                "against its WP file"
            )
            current = m.group(1)
            continue
        m = row_re.match(line)
        if m:
            assert current, f"ROADMAP row {m.group(1)} sits above any section"
            sections[m.group(1)] = current
    return sections


def test_index_section_mirrors_the_wp_milestone_line():
    """The WP file's `Milestone:` line is the authority on where a WP stands;
    the section its ROADMAP row sits under mirrors it.  The number cannot
    carry this (1101-1103 opened for v1.1 and are queued for v1.4), which is
    why it is a line and a test rather than a naming rule.
    """
    sections = _index_sections()
    for path in _wp_files():
        wp_id = path.name[:4]
        m = _MILESTONE_LINE_RE.search(path.read_text(encoding="utf-8"))
        assert m, f"{path.name}: no 'Milestone: <token> ·' line"
        token = m.group(1)
        section = sections[wp_id]
        assert token.lower() == section.lower(), (
            f"WP {wp_id}: file says Milestone: {token}, ROADMAP row sits under "
            f"§ {section} — move the row or fix the line"
        )


_STATUS_CELL_RE = re.compile(r"^(?:⬜|(?:🔄|✅|🛑) \d{4}-\d{2}-\d{2})$")


def test_roadmap_status_cell_is_a_glyph_and_a_date():
    """An index row's status cell is the glyph and the date, nothing else.

    The free text belongs on the WP file's own Status line (TEMPLATE.md);
    ROADMAP's cells had grown six-line close narratives, which is how the
    file reached 8600 words before the 2026-09-01 reorder.
    """
    for wp_id, (_link, cell) in _index_rows().items():
        assert _STATUS_CELL_RE.match(cell), (
            f"ROADMAP row {wp_id}: status cell {cell!r} is not '<glyph> <date>' "
            "— put the summary on the WP file's Status line"
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
    docs += sorted((ROOT / "docs" / "wp").rglob("*.md"))
    docs += sorted((ROOT / "docs" / "milestones").glob("*.md"))
    return docs  # docs/manual/ is excluded: MyST links are sphinx's to check (-W)


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
    the third (`tests/test_gui_manual.py`) names two directories under
    `docs/manual/`, so WP-1412's eighteen sheets under `docs/wp/` went past it:
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
    paths = [str(p) for p in sorted(set(targets))]
    result = subprocess.run(
        # --no-index: check-ignore answers for a *tracked* file out of the index
        # without reading the rules, and the point here is the rules.
        ["git", "check-ignore", "-v", "--no-index", *paths],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    # 0 is "something matched", 1 is "nothing did"; anything else is git
    # declining to answer — no repository, a path outside it, an argument list
    # too long — and it writes to stderr, leaving an empty stdout that reads
    # here as a pass (tests/CLAUDE.md § Guards that go quiet instead of red).
    assert result.returncode in (0, 1), (
        f"git check-ignore exited {result.returncode} and asked nothing: "
        f"{result.stderr.strip()}"
    )
    ignored = [
        line for line in result.stdout.splitlines()
        # A `!` pattern is check-ignore reporting the un-ignore that saved it.
        if line and not line.split("\t")[0].rpartition(":")[2].startswith("!")
    ]
    assert not ignored, (
        "a planning doc links a file .gitignore drops:\n" + "\n".join(ignored)
    )
    # The un-ignore is half the story.  WP-1412's sheets were ignored *and*
    # never added, and a rule committed without the files it frees leaves this
    # guard green while a clone gets nothing — so ask the index too.  Absent
    # this, only CI sees it, through the missing file the link test resolves.
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *paths],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert tracked.returncode == 0, (
        "a planning doc links a file git does not track:\n" + tracked.stderr.strip()
    )


def test_every_shipped_milestone_row_names_its_record():
    """A ✅ milestone row must link a record file; the link test resolves it."""
    text = ROADMAP.read_text(encoding="utf-8")
    section = text.split("## Milestones", 1)[1].split("## Work packages", 1)[0]
    for line in section.splitlines():
        if not line.startswith("|") or "✅" not in line:
            continue
        assert re.search(r"\(milestones/v[\d.]+\.md\)", line), (
            f"shipped milestone row without a record link: {line[:80]}"
        )


@pytest.mark.parametrize("relpath", sorted(SIZE_CAPS))
def test_always_loaded_docs_stay_under_their_pinned_caps(relpath: str):
    cap = SIZE_CAPS[relpath]
    if cap is None:
        pytest.skip("cap pinned by the consolidation pass that measures it (WP-1031)")
    n_lines = len((ROOT / relpath).read_text(encoding="utf-8").splitlines())
    assert n_lines <= cap, (
        f"{relpath} is {n_lines} lines (cap {cap}).  Do not delete facts to fit: "
        "move narrative to the WP file or the in-flight milestone record "
        "(docs/milestones/, § 'How vX.Y is getting here') per protocol rule 4/5."
    )


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
REFERENCES_BIB = ROOT / "docs" / "manual" / "references.bib"

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

    ``gui/`` is excluded on purpose: the GUI server's session codes
    (NOT_FOUND, RUN_IN_FLIGHT, ...) share the shape but are a separate
    namespace with no protocol rows — §7's namespace note (`references/diagnostics.md`) declares the
    split.  The lowercase ``GateFailure`` codes fall out of the shape filter
    and are covered by the vocabulary test instead.
    """
    import ast

    codes: set[str] = set()
    for py in sorted(SRC.rglob("*.py")):
        if "gui" in py.relative_to(SRC).parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (kw.arg == "code" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and re.fullmatch(r"[A-Z][A-Z0-9_]+", kw.value.value)):
                    codes.add(kw.value.value)
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
        "author-year citations resolving neither in docs/manual/references.bib "
        f"nor inline: {sorted(set(unresolved))}"
    )
