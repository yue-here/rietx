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
# The priority rubric is TEMPLATE.md's: every ⬜ WP carries a `Priority:`
# line, a closed one carries none (its priority is moot, and the cell reads
# `—`), and a 🔄 one may keep the line it had.  Backfilled 2026-09-23.
PRIORITIES = ("P1", "P2", "P3", "P4")
_PRIORITY_RE = re.compile(
    r"^Priority: (?P<tier>P[1-4]) (?P<date>\d{4}-\d{2}-\d{2}) — \S", re.M
)

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
#   2026-09-22  src/rietx/indexing/CLAUDE.md  300 -> 306  for WP-1446
#   2026-09-01  tests/CLAUDE.md               253 -> 275  for the placement pass
#   2026-09-01  docs/ROADMAP.md               589 -> 597  for the roadmap reorder: landed 573, cap landed + 24
#   2026-09-02  docs/ROADMAP.md               597 -> 621  for the magnetic scattering track (1326-1329, out of
#                                                          the v2 fence): a section and four rows, landed 597, cap landed + 24
#   2026-09-02  CLAUDE.md                     722 -> 723  for WP-1131's two rules and the handover-trigger note
#                                                          (PRs #227, #228), which landed at 723 with no bump; repaired in #229
#   2026-09-02  CLAUDE.md                     723 -> 732  for WP-1330's skill bullet: the three destinations
#                                                          and the shape rule, landed at the cap
#   2026-09-16  gui/CLAUDE.md                1028 -> 1036 for WP-1425's one rule: the watch page's
#                                                          port of lib/resize.ts, pinned by a text-compared
#                                                          case table, and the dist digest that hashes tests
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
#   2026-09-16  docs/ROADMAP.md               712 -> 717  for WP-1432, filed by the review of issues #286
#                                                          and #293: one index row and one sentence naming
#                                                          it in § What fires, and what stays silent; landed
#                                                          713, +4 headroom so the next few index rows do
#                                                          not each need a cap commit
#   2026-09-16  docs/ROADMAP.md               717 -> 719  for WP-1434 and WP-1435, the two halves of WP-1310
#                                                          it measured into their own shape: two index rows,
#                                                          nothing else. The sentence naming them in § What
#                                                          fires replaced one 1310 already had, so the
#                                                          narrative paid for itself; landed 719, no headroom
#   2026-09-17  docs/ROADMAP.md               719 -> 722  for WP-1436 and WP-1437, opened by the notation
#                                                          audit a LinkedIn comment started: two index rows
#                                                          under § The repo's own process, no narrative at
#                                                          all, since both WP files carry their own. Landed
#                                                          720, +2 headroom
#   2026-09-18  docs/ROADMAP.md               722 -> 748  for WP-1440, opening § v1.5 over 26 rows that
#                                                          were already in the file. The whole move is
#                                                          structure: one ###, five ####, five table
#                                                          headers, one new row for 1440 itself. Every
#                                                          line of new narrative was paid for by a cut in
#                                                          § Unscheduled, whose prose described the rows
#                                                          that left. Landed 745, +3 headroom
#   2026-09-18  docs/ROADMAP.md               762 -> 784  for the v1.6 open over seven rows already in
#                                                          the file. Structure again — one ###, one table
#                                                          header — plus the two paragraphs that are the
#                                                          open's own rulings: the PR order, and that
#                                                          neutron TOF stays fenced. Both govern work
#                                                          arriving from outside, so neither can live in
#                                                          a WP file the contributor does not read.
#                                                          Paid for in Current focus and § Unscheduled.
#                                                          Landed 778, +6 headroom
#   2026-09-18  CLAUDE.md                     929 -> 938  for WP-1434: the bound test's new question,
#                                                          which no consumer of BOUND_HIT or at_bound
#                                                          can re-derive from the code it reads.
#                                                          Landed 937, +1 headroom
#   2026-09-18  CLAUDE.md                     938 -> 954  for WP-1435: a hold the caller declares,
#                                                          owed to every session that writes a plan
#                                                          or a set_vary call site. Row written
#                                                          2026-09-19, the session having left it
#   2026-09-19  CLAUDE.md                     954 -> 963  for WP-1432: a coordinate DOF is relative,
#                                                          so a rebuild must reproduce the
#                                                          coordinate. Landed 962, +1 headroom
#   2026-09-19  CLAUDE.md                     963 -> 973  for WP-1342: a freeze resting on flatness
#                                                          asks which column moves an entry, never
#                                                          what it is called. Folded into the
#                                                          moving_paths bullet rather than added
#                                                          beside it, being that rule one rank down,
#                                                          and owed to every future freeze: four
#                                                          consumers now read it and a fifth would
#                                                          repeat the defect. Landed 972, +1 headroom
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
    # 833 -> 836 (WP-1118): the WP-1076 clause gains its sibling — a message
    # that names its discriminator makes the same claim a declared field
    # does, so the evidence is checked to separate before it is quoted.  It
    # governs every diagnostic that argues from a computed quantity, not
    # only the one that was measured wrong.  Raised rather than shaved.
    # 836 -> 837 (WP-1430, at the merge): the `node --check` clause became the
    # rule that a javascript page is a file, +2 on a branch cut when the cap
    # was 833 and landing at exactly 833.  Two parents' additions do not sum
    # (tests/CLAUDE.md § Quoting numbers), so the merged tree is one over and
    # the +1 is arithmetic rather than new content.
    # 837 -> 841 (WP-1424): "no file check sees layout" gains its second class.
    # A cut is not a variant of the invisible sheet: that one was a rule
    # outranking another, and this is a measurement being right about the
    # wrong box.  It carries the instrument with it, because `scrollWidth` is
    # the obvious probe and is blind here, and a reader who reaches for it
    # measures zero and believes the page.  Raised rather than shaved.
    # 841 -> 853 (WP-1429): one standing rule for the colour values the three
    # browser surfaces share, which governs `watch/`, `compare_app.py` and
    # `gui/` at once and so belongs to none of their rulebooks. Landed at 852.
    # 853 -> 866 (WP-1427): one standing rule for a polled view — that a pane
    # names its own cap on the route it reads, and that a row carrying a clock
    # can never be told it has not changed. Both govern work outside the WP
    # that measured them: the first any future viewer pane, the second any
    # route that wants an `ETag` or a comparison, the GUI's included. The
    # numbers that *dismissed* a candidate stayed in the WP file, per rule 4.
    # 866 -> 871 (WP-1428): the watcher's "one verb" clause was false once it
    # had two, and the second one's rule is that it opens a *copy* — there
    # being no read-only way to open a project at all. Beside it, the one
    # authority for which project a run sits in: two live layouts, three
    # readers that had open-coded one each, and a GUI command that was `None`
    # for every run a project records. The torn-copy measurement that sized
    # the risk stayed in the WP file, per rule 4.
    # 871 -> 882 (WP-1309, merged beside 1428 rather than after it): two more
    # standing rules, neither of them about measured backgrounds. An absorption
    # screen anchors its targets at `phases.`, because a parameter of the block
    # it screens against is *in* the span and scores R² = 1.00 about itself,
    # which governs any future member of either block. And a parameter family
    # has a second consumer that no pytest sees, the GUI's per-family print
    # format, which governs every parameter anyone adds. Both branches raised
    # this cap from 866 at once, so the number here is the *merged* file's size
    # plus headroom rather than either branch's arithmetic — which is the same
    # rule `tests/CLAUDE.md` states for test counts across a merge.
    # 882 -> 883 (WP-1438): the per-stage charge clause gains its *answer*.
    # WP-1413 measured the number and left the cadence to the maintainer, so
    # the clause named a cost with no decision beside it; the lines added say
    # the decision, why a ratio is the wrong test on a sub-second fit, and what
    # a throttle would be if the number ever moved. The other five answers this
    # WP landed reach no rule outside their own subtree. Measured on the merged
    # file, per the paragraph above: this branch and 1309's both raised the cap
    # from 871 and the two sets of lines do not sum.
    # 883 -> 906 (WP-1438, the maintainer's second round on the same track):
    # three clauses that govern anything added after them rather than
    # recording what this WP did. A pane stacking when it cannot meet its
    # floor beside its neighbour, with the breakpoint living once because
    # spelled twice it is two layouts disagreeing; the theme's writer widened
    # from the GUI alone to every page that shows it, since a page the GUI's
    # user never opens could read the choice and not make it; and a tick's
    # Miller index built where the positions are, which governs any second
    # fact anyone pairs with a tick. The other three answers — the empty cell
    # saying why it is empty, the boot's request waterfall, the header's
    # unbreakable line — are findings and stayed in the WP file.
    # 906 -> 907 on the merge (WP-1438 + 1309): both branches raised this
    # cap and the two sets of lines do not sum — 1309's σ-is-a-function-of-the-
    # declared-scale clause landed while 1438's three were open. Per this
    # file's own rule, the number is the *merged* file's size.
    # 907 -> 914 (WP-1436): one standing rule for the symbol sinθ/λ carries,
    # which is `s` in maths and `stol` in python.  It governs work well outside
    # its own WP, which is protocol rule 4's test: five queued magnetic WPs
    # (1326-1329, 1418) will write `k` for the propagation vector inside the
    # very subpackage where it used to mean this, and a later session reading
    # `scattering.py` beside the DABAX file it parses would otherwise restore
    # the file's spelling as the more authoritative one.  The split itself is
    # the part a reader cannot re-derive: `s` is unavailable as an identifier
    # because `structure_factor.d_f2_d_uaniso` already binds it, so the two
    # halves look arbitrary until the reason is written down.  Raised rather
    # than shaved, per the failure message's own instruction.  Landed at 913;
    # the headroom is +1.
    # 914 -> 923 (WP-1441): one standing rule about the pattern boundary, for
    # the shape issue #376 turned out to be.  `RefinementState` names eight
    # facts and the chain had a channel for six; the two it had none for are
    # the two that live on the `Refinement` rather than in the models, and
    # neither failed a test, because an absent channel raises nothing.  The
    # clause governs the ninth fact rather than recording the two: it says
    # where to look (not in the models → no channel), and it says why the two
    # halves are spelled differently, which is the part a reader cannot
    # re-derive — a tie is a verb call against a live table, so it is
    # re-declared per pattern, while a variable's value is a number and is
    # carried.  The measurements (the iteration counts, the Rwp the plan
    # reaches) stayed in the WP file.
    # 923 -> 929 (the magnetic index split, 2026-09-18): one clause saying a
    # task shape's entry points render to a generated `api-<shape>.md` rather
    # than into the everyday `api.md`.  The existing sentence beside it covered
    # the *authored* half of a shape's documentation and was silent on the
    # generated half, which is the half a contributor adding a verb touches, so
    # a reader following CLAUDE.md alone would put a magnetic verb where every
    # session that will never call it pays for it.  It governs every technique
    # after magnetic (TOF, texture, PDF), which is protocol rule 4's test, and
    # the measurement behind it is the reader's context rather than a byte
    # count.  Landed 925, +4 headroom.
    # 929 -> 938 (WP-1434, 2026-09-18): the bound test asks whether the limit
    # carried load, never whether the value is near one, and it is a
    # conjunction because each half covers what the other cannot.  It governs
    # every consumer of `BOUND_HIT` and `at_bound` and every future bound, so
    # it cannot go down a rank into the WP: a session reading the flag has no
    # way to re-derive the change from a `False` it disagrees with.  The
    # thresholds, their measured windows and the two rejected fixes stayed in
    # the WP and in the two constants' own docstrings.  Landed 937, +1
    # headroom.
    # 938 -> 954 (WP-1435): a caller's hold, and the reason it had to be a
    # mechanism rather than a message — `vary=False` does not survive a plan,
    # so every session that writes a plan, a calibration or a `set_vary` call
    # site needs the rule, not just the one that built it. It also states the
    # two things that bite a caller who does not know it exists: `set_vary`
    # can refuse now, and `_user_holds` is not WP-1301's `_held`.
    # 954 -> 963 (WP-1432): a coordinate DOF is relative, and the invariant
    # that keeps it honest is that a rebuild reproduces the coordinate. It
    # belongs beside the DOF bullet it qualifies rather than a rank down,
    # because the two facts a stranger needs are about *other* code: which
    # entries are anchored is data built where the anchor is, so a new DOF
    # family inherits nothing by spelling its paths the same way; and the tie
    # register's consumers each call the rebase, so a third one written
    # without the rule carries the defect `replay` carried alone. The
    # measurement, the two controls and the rejected fixes stayed in the WP.
    # 973 -> 978 (/issue-review, 2026-09-21): one paragraph saying how an
    # issue reaches the roadmap, beside the contributor paragraph whose
    # PR -> issue -> WP chain it completes from the issue's end. A standing
    # rule for anyone who files or folds a WP: the `#N` citation is the whole
    # triage record, read by the command's table and by wp_claim.py alike.
    # Landed 977, +1 headroom.
    "CLAUDE.md": 978,
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
    # 710 -> 712 (WP-1118): the same race again, and the headroom above was
    # spent by the branch that won it.  The watch-unroll merge filled 710
    # exactly with the 1424-1431 rows and a rewritten focus paragraph, while
    # this branch was measured against the older number; the one line here is
    # Current focus naming #101 as closed, which is what a successor reads to
    # know the writers are all that is left of 1118.  Nothing is demotable, so
    # the cap moves rather than the fact.  Landed at 711, headroom +1.
    # 719 -> 722 (WP-1438 over 1309's rows): one index row for the WP
    # that answered the six questions the watcher track left.  Current focus
    # paid for itself — the list of open questions became the list of answers
    # in the same eight lines — so this branch's whole move is the row, and
    # the number is the merged file's.
    # 722 -> 748 (WP-1440): § v1.5 opened over 26 rows the file already
    # carried, so the move is structure and not content — one `###`, five
    # `####`, five table headers and 1440's own row come to exactly the 23
    # lines the file grew by.  The diary's standing rule is that a cap grows
    # with the row count and with nothing else, a row being no narrative; the
    # narrative this branch added is paid for in § Unscheduled, where the
    # prose describing the departed rows was cut to match.  Landed 745, +3
    # headroom for what the notes audit may still have to cut.
    # 748 -> 762 (WP-1441): § v1.5.x, the road for work landing while no
    # milestone is open.  One `###`, a five-line blurb, a table header and one
    # row, against the diary's standing rule that a cap grows with the row
    # count: the row moved out of § Unscheduled, so the growth is the section
    # itself.  It is structure that outlives this WP — every WP landing before
    # v1.6 opens files here — and the blurb is the part that cannot be demoted,
    # since it says where the notes are staged and what the 1.0.x road's ending
    # was.  Paid for in Current focus, where v1.5's summary was cut to the
    # record that already carries it (496 commits, the cost of opening late).
    # Landed 760, +2 headroom.
    # 762 -> 784 (the v1.6 open, 2026-09-18): § v1.6 over the seven magnetic
    # rows § Unscheduled already carried, so the structure — one `###`, one
    # table header — is the diary's standing rule and costs two lines.  The
    # rest is two paragraphs of ruling made at the open: the PR order inside
    # the milestone, and that neutron TOF stays at the v2+ fence although a
    # contributor's chain carries it merged into the magnetic one.  Neither
    # demotes to a WP file, because the reader they are for is building
    # against this index from outside the repository and reads no WP file
    # until a PR is cut.  Paid for twice — Current focus lost a closed WP's
    # narrative and the triage fold list, § Unscheduled lost the blurb
    # describing the rows that left.  Landed 778, +6 headroom.
    # 784 -> 816 (/issue-review, 2026-09-21): two rows (1443, 1444), the two
    # blurb sentences the rows need, one paragraph placing #374 in its PR
    # under § v1.5.x (no open WP owns it), #362 on the TOF fence, and two
    # v2+ bullets — Estimation (#355) and Navigation (#349) — each naming the
    # gate that would reopen it.  Every finding stays in the WP files and on
    # the threads.  Landed 813, +3 headroom.
    # 818 -> 828 (the priority column, 2026-09-23): one paragraph under
    # § Work packages saying what the `Priority` column is and where its
    # authority lives (the WP file's line, TEMPLATE.md's rubric).  The
    # column itself costs no lines: eleven headers widened and sixty rows
    # given a `—` cell, on the open sections only.  Landed 827, +1 headroom;
    # the 2026-09-23 backfill rated every ⬜ row and landed at 827 again.
    # 828 -> 831 (/issue-review, 2026-09-23): three rows under § The repo's
    # own process, 1450-1452, for issues #417, #419 and #426.  No prose:
    # every finding and fold stays in the WP files.  Landed 830, +1 headroom.
    # 831 -> 835 (2026-09-24): four rows, 1453-1456, filed by the review of an
    # agent session on a private in-situ series, across three existing
    # sections; a fifth finding was folded into 1420's Inherited instead.  No
    # prose: the evidence stays in the WP files.  Landed 834, +1 headroom.
    # 835 -> 840 (/issue-review, 2026-09-24): three rows, 1457-1459, under
    # two existing sections, for issues #441, #436 and #440.  No prose beyond
    # one sentence on #374's second instance and the #193 decision with #442
    # beside it in § v2+: the evidence stays in the WP files.  Landed 839,
    # +1 headroom.
    # 840 -> 846 (2026-09-25): two rows, 1463 and 1464, filed by the review of
    # a second agent session on the same private series, under two existing
    # sections, and one sentence on #374's third instance.  Four more findings
    # went into existing WPs' Inherited.  Landed 845, +1 headroom.
    # 846 -> 851 (/issue-review, 2026-09-25): one row, 1465, under § What
    # fires, and what stays silent, for issue #451, and four lines in § v1.6
    # recording the order #286 asked for (1326, 1328, 1343, 1329).  The
    # evidence stays in the WP files.  Landed 850, +1 headroom.
    # 851 -> 852 (2026-09-25): one row, 1467, under § What fires, and what
    # stays silent, from a review of the same private series' Stephens runs.
    # No prose: the evidence stays in the WP file.  Landed 851, +1 headroom.
    # 852 -> 854 (WP-1466, 2026-09-26): one row, 1468, under § Render what the
    # fit already knows, the further work 1466's automatic polyhedra leave, at
    # the maintainer's request.  No prose: the evidence stays in the WP file.
    # Landed 853, +1 headroom.
    "docs/ROADMAP.md": 854,
    # 1036 -> 1053 (WP-1429): where the GUI's colour values live, now that
    # they are Python and this workspace's `tokens.css` is generated from
    # them. It governs work outside the WP that measured it — an edit to a
    # token here is a rebuild, and an edit in the wrong file is a test
    # failure nobody can act on without the rule. Landed at 1045.
    "gui/CLAUDE.md": 1056,   # +3: the node floor the dist build needs (WP-1442)
    # 275 -> 283 (WP-1426): a third way a guard goes quiet, and the only one of
    # the three that is about the instrument rather than the assertion — a
    # browser's layout-shift entry cannot see inside a plotly div, so a
    # stillness guard over a picture reads 0 while the picture moves. It
    # governs work well outside the WP that measured it: three queued WPs edit
    # that page, and `compare_app.py` and the GUI both draw with plotly too.
    # Landed at 282, headroom +1, per this file's docstring.
    # 283 -> 288 (WP-1438): the mid-suite check was `pgrep -f "[p]ytest"`,
    # and `pgrep -f` was measured exiting 1 against a live `pytest -n 4` that
    # `pgrep python` and `ps` both saw — and behaving differently in two
    # sessions the same day. A check that silently finds nothing returns a
    # false all-clear every time, so the rule names `ps aux | grep` and says
    # why, which is the clause that stops the next reader putting `pgrep`
    # back.
    # 288 -> 296 (WP-1439): one standing rule for reading the CI matrix --
    # that a pass count cannot show a module that never ran, and the total is
    # what does.  It governs work outside the WP that measured it: anyone
    # quoting a count off any platform in this matrix, which is protocol rule
    # 4's test.  Raised rather than shaved, per the failure message's own
    # instruction not to delete facts to fit.  Landed at 295; the +1 is
    # headroom, per this file's docstring.
    "tests/CLAUDE.md": 296,
    # 300 -> 306 (WP-1446): one standing rule, on the bullet that already owns
    # the question.  A space-group absence and an oversized cell are not
    # separable by the reversed members either, measured rather than reasoned,
    # so the next person to reach for that ranking finds the refutation instead
    # of re-running it.  Raised rather than shaved, per the failure message's
    # own instruction not to delete facts to fit; the numbers stayed in the WP.
    "src/rietx/indexing/CLAUDE.md": 306,
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
    # 410 -> 428 (WP-1118): one standing rule for the next project reader —
    # that a format stating its operators has already chosen its setting, so
    # the choice is an equality checked rather than a convention adopted, and
    # a format stating only a symbol reports the assumption at read.  It
    # governs work outside the WP that measured it: `.m50` states operators
    # too (WP-1314).  Raised rather than shaved, per the failure message.
    # 428 -> 465 (WP-1118): a § Project writers, four rules the readers do not
    # need.  It governs work outside the WP that measured them — every later
    # writer this family grows, GSAS-II being next — and one of the four is a
    # class no test in this package can catch, since a Fortran edit descriptor
    # supplies the decimal point a field omits while `float()` here does not,
    # so a round trip stays green about a file that says something else to the
    # program it is for.  Raised rather than shaved, per the failure message.
    # Landed at 464, then 472 after the review pass found the budget rule
    # stated too simply: how much of a field is spendable is the *reader's*
    # question, and a writer that spent all fifteen columns of a `.prm` PRCF
    # field wrote a file this package's own reader refused.  That is the rule
    # the section exists for, so it is corrected in place rather than shaved.
    # The +1 is headroom, per this file's docstring.
    # 473 -> 485 (WP-1118, 2026-09-16): the GSAS-II pair added the one rule a
    # writer cannot derive from the four before it — two programs reading one
    # string opposite ways, so the fact goes in the channel the target reads.
    "src/rietx/io/CLAUDE.md": 485,
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


def _priority_of(path: Path) -> tuple[str, str] | None:
    """(tier, date) from the WP file's `Priority:` line, or None when unrated."""
    m = _PRIORITY_RE.search(path.read_text(encoding="utf-8"))
    return (m.group("tier"), m.group("date")) if m else None


def _priority_cells() -> dict[str, str | None]:
    """WP id -> the row's Priority cell, or None where its table has no column.

    A header line names its columns, and the rows under it (to the next
    blank line) are read against that header, so the column may sit on the
    open sections' tables only.
    """
    cells: dict[str, str | None] = {}
    columns: list[str] = []
    row_re = re.compile(r"^\| \[(\d{4})\]\(wp/")
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        if line.startswith("| WP |"):
            columns = [c.strip() for c in line.strip("|").split("|")]
            continue
        if not line.startswith("|"):
            columns = []
            continue
        m = row_re.match(line)
        if not m:
            continue
        row = [c.strip() for c in line.strip("|").split("|")]
        if "Priority" in columns:
            assert len(row) == len(columns), (
                f"ROADMAP row {m.group(1)}: {len(row)} cells under a "
                f"{len(columns)}-column header"
            )
            cells[m.group(1)] = row[columns.index("Priority")]
        else:
            cells[m.group(1)] = None
    return cells


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
    format, because the ROADMAP cell is read off it.
    """
    for path in _wp_files():
        text = path.read_text(encoding="utf-8")
        glyph, _ = _status_of(path)
        if "\nPriority:" in text:
            assert _priority_of(path), (
                f"{path.name}: Priority line is not 'Priority: P<n> YYYY-MM-DD — <why>'"
            )
            assert glyph not in {"✅", "🛑"}, (
                f"{path.name}: closed ({glyph}) and still rated — delete the "
                "Priority line and set the ROADMAP cell to '—' (protocol step 5)"
            )
        else:
            assert glyph != "⬜", (
                f"{path.name}: not started and carries no Priority line (TEMPLATE.md)"
            )


def test_roadmap_priority_cell_mirrors_the_wp_priority_line():
    """The WP file's line is the authority; the index cell is its tier.

    A rated WP whose row sits in a table without the column is a rating
    nobody reading the index can see, so that fails too.
    """
    cells = _priority_cells()
    for path in _wp_files():
        wp_id = path.name[:4]
        rated = _priority_of(path)
        cell = cells[wp_id]
        if cell is None:
            assert rated is None, (
                f"WP {wp_id}: file rates it {rated[0]} but its ROADMAP table has "
                "no Priority column — add the column to that section's table"
            )
            continue
        expected = rated[0] if rated else "—"
        assert cell == expected, (
            f"WP {wp_id}: ROADMAP Priority cell is {cell!r}, file says {expected!r}"
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
    docs += _kept_by_git(sorted((ROOT / "docs" / "wp").rglob("*.md")))
    docs += sorted((ROOT / "docs" / "milestones").glob("*.md"))
    return docs  # docs/manual/ is excluded: MyST links are sphinx's to check (-W)


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
        cwd=ROOT, capture_output=True, text=True, check=False,
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
