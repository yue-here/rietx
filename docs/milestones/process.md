# The repo's own process — the record

The milestone records hold what the package computes; this one holds how the
repository works on itself: the always-loaded rulebook caps and their diary,
moved here from `tests/test_docs_consistency.py` on 2026-09-01 (every
paragraph verbatim), and the process WPs those caps came from —
[1031](../wp/1031-docs-consolidation.md), [1060](../wp/1060-docs-ci-consolidation.md),
[1061](../wp/1061-workflow-robustness.md), [1116](../wp/1116-session-protocol-hygiene.md),
and the one-tree-per-session tooling of 2026-08-27. The test keeps the rule and
a one-line table per bump; the reasoning is here. Since 2026-09-30 it also
holds [what a session's reading costs](#what-a-sessions-reading-costs), the
measurement behind the delegation rules in `/pr-review`, `/wp-start` and
`/wp-handover`. Since 2026-10-01 it holds [lanes within a
WP](#lanes-within-a-wp), the replay and trial behind `/wp-start` step 6c.

## The rule

Always-loaded documents: measured size + headroom, pinned by the pass that
achieved it.  Raising a cap is a decision about every future session's fixed
cost — make it in a commit that says so, not as a side effect.  Do not
delete facts to fit a cap: move narrative to the WP file or the milestone
record (the assertion message says where).
History: WP-1031 (2026-07-31) landed CLAUDE.md at 601 and ROADMAP at 494;
2026-08-05 raised 700 -> 720 with the written warning that it bought twelve
lines, not a habit, and that the next WP needing room should consolidate.
WP-1060 (2026-08-06) was that consolidation: the indexing dossier moved to
src/rietx/indexing/CLAUDE.md (auto-loads with its subtree), ROADMAP's
closed-WP narratives moved to the milestone record, Current numbers became
a measurement recipe — CLAUDE.md landed at 553, ROADMAP at 337 — and every
always-loaded rulebook is now capped at landed + headroom.  The admission
rule the caps enforce: a line enters one of these files only as a standing
rule a stranger needs in six months, evidence compressed to one clause plus
a pointer (protocol rule 4); a new indexing rule lands in the indexing
rulebook and earns a root clause only if it changes behavior outside
indexing/.  WP-1047 (2026-08-09) is the same move for the readers: root
CLAUDE.md was at exactly 600 with four vendor formats still to land, so the
reader detail went to src/rietx/io/CLAUDE.md (loads under io/) and root
kept only the four consequences a caller outside io/ sees.  Landed at 165,
capped at 200 — the headroom is the remaining formats' per-format rows.
WP-1067 (2026-08-17) is the same move for ROADMAP, and the cap does NOT move:
the file was at exactly 400 with 1076's index row still to add, and the
session before it recorded that a raise was the only fix left because the
narrative had no second copy.  Measured, two paragraphs had one already — the
guillemot-study prior art is in v1.0.md § "Indexing joined v1.0" with the
`git show` recipe, and the vmap sizing note is in v0.4.md twice — so those
were deleted and the five post-2026-08-05 close narratives moved to v1.0.md
§ "The WP-table narratives, second pass", which is what protocol rule 5 asks
for on close and this assertion's own message prescribes.  400 -> 355.
The deletions also exposed what the narrative was hiding: three of the four
tables under "### v1.0 — indexing" are not indexing WPs, and only the prose
between them made the splits look deliberate.  They now carry their own
headings, which is why the saving is 45 lines rather than the 64 removed.

## The caps diary

### `CLAUDE.md`

600 -> 620 for WP-1067 (2026-08-14): the manual became two parts with
two different guards, and the operating detail did go down a rank as
this comment requires — the derivation's three rules live in
tests/api_surface.py's docstring, the chapters' own rules in the WP.
What could not go down a rank is the one clause a session that never
opens docs/manual/ still needs: adding a public method or field fails
the manual's coverage partition until it is documented or deferred.
Net +11 lines after the theory-manual bullet was rewritten to cover both.

620 -> 625 for WP-1068 (2026-08-14): the manual bullet gains the clause a
session that never opens docs/manual/ still needs — a green sphinx build
is not a rendered page, and Part 1's figures are committed artefacts with
a generator, so touching either means regenerating and *looking*.  The
operating detail went down a rank as this comment requires: the figure
recipes are in make_figures.py's docstring, the chapters' own rules in
the WP.

625 -> 644 for WP-1070 (2026-08-15): the constraint verbs, and the rule
underneath them.  The operating detail went down a rank as this comment
requires — the refusal wording, the FAP numbers and the two open freeze
asymmetries are in the WP, the narrative in the v1.0 record.  What cannot
go down a rank is what a session touching the Jacobian never reads:
`_make_jacobian` dispatches on a parameter's *name*, so a branch is a
claim about that name's reach, and a constraint that reaches further
leaves the column short instead of raising.

648 -> 656 for WP-1071 (2026-08-15): the observation count.  The
operating detail went down a rank as this comment requires — the
estimator, its three caveats and the one measured deviation from the
paper are in `optimize.statistics.effective_observations`' docstring, the
sampling floor's evidence in `background.diagnostics`, the acceptance
numbers in the WP.  What cannot go down a rank is the shortcut a session
adding any support statistic will otherwise take: `n_points` is the
algorithm's N and not the number of observations, and the two bands set a
diagnostic's level rather than gating a fit.

656 -> 670 for WP-1072 (2026-08-15): the geometry table, and the two
rules under it.  The operating detail went down a rank as this comment
requires — the listing convention, the cutoffs, the CIF tag check and
the NAC numbers are in `model/geometry.py`'s docstring and the WP, the
narrative in the v1.0 record.  What cannot go down a rank is what a
session adding *any* derived quantity will otherwise get wrong twice:
its esd needs the whole covariance (and the diagonal number beside it is
not the conservative choice, it is wrong in either direction), and an
esd that cannot be measured is absent rather than zero.  The orbit-count
clause rides with it because it is the only check that saw the bug.

670 -> 683 for WP-1073 (2026-08-15): a position correction belongs to a
geometry.  The operating detail went down a rank as this comment
requires — the derivation that fixes eq (4)'s signs is in
`capillary_displacement_shift_deg`'s docstring, the two 11-BM
measurements and the premises they overturned are in the WP, the
narrative in the v1.0 record.  What cannot go down a rank is what a
session adding *any* aberration will otherwise get wrong: the template
and the action are geometry-scoped (a blind map suggests a force-fixed
parameter), a parameter the forward branch skips must be force-fixed
rather than merely unfree, and the evidence for a position correction is
a stage rung rather than the converged report.

683 -> 700 for WP-1074 (2026-08-16): the restraint weight schedule.  The
operating detail went down a rank as this comment requires — the c_w
measurements are in the WP and the manual, the seam's own reasoning in
`CompiledModel.restraint_weight_scale`'s field comment.  What cannot go
down a rank is the constraint on a file a session edits for other
reasons: `model/restraints.py` has a second consumer that is not a
restraint, so anything weighting a restraint row belongs at the row build
and not in the shared partials function — the geometry esds are built
from that function's output at unit weight, and no distance-value test
in the package would notice them all moving by a constant factor.

700 -> 720 for WP-1076 (2026-08-18): a declared name is a claim, and an
absent writer fails no test.  It earns a clause because it governs core
work — adding a schema field or a Literal member — rather than manual
work: 1067's near-miss rule was about mis-attributing a type in prose and
went into a docstring instead, and the cap was what sent it there.

720 -> 736 for WP-1109 (2026-08-20): the structural-freeze question.
The operating detail went down a rank as this comment requires — the
memo's contract is in `CompiledModel._memo`'s docstring, the profile
numbers and the cumulative before/after in the WP, the narrative in the
v1.1 record.  What cannot go down a rank is the clause a session adding
any compile-time freeze never reads: `free_paths` is the narrower
question and a tie defeats it, so a freeze asks `moving_paths` and then
verifies its own claim where the claim is used.

736 -> 752 for WP-1110 (2026-08-20): the default cell window and the two
diagnostics beside it.  The operating detail went down a rank as this
comment requires — TOPAS's Table 2-1, the per-stage-vs-per-iteration
translation and the 51-stage-transition measurement are all in
`params.vector.cell_window`'s docstring, the episode and the equivalence
numbers in the WP.  What cannot go down a rank is the clause a session
that never opens params/ still needs: a construction site passes no cell
floor rather than a nonsense one, or it silently suppresses the default.

752 -> 759 for WP-1110 (2026-08-21): the plan mirror is crossed at the two
authorities that own it.  The operating detail went down a rank as this
comment requires — which validator, which converter and why the crossing
is by isinstance are in `PlanSpec._accept_the_dataclass` and
`resolve_plan`, the friction it closes in the WP.  What cannot go down a
rank is the clause a session adding *any* mirror needs before it writes
one: two types sharing every field name make a structural test certify an
accident, so the crossing tests the class.

759 -> 771 for WP-1110 item 14 (2026-08-21): the covariance is
equilibrated, and a direction the data cannot see reports no esd.  The
operating detail went down a rank as this comment requires — the cutoff
arithmetic, the van der Sluis result and the 0 × inf propagation are in
`normal_covariance` and `ParameterTable._cov_free`, the measurements in
the WP.  What cannot go down a rank is the pair a session touching *any*
statistic will otherwise get wrong: a badly-scaled column silently zeroes
a variance rather than raising, and the honest empty state for an
unmeasured direction is absence, which every consumer must mark rather
than clamp.

771 -> 784 for WP-1120 (2026-08-22): the numpy forward moved onto the
batched planes, and three facts about it cannot go down a rank because a
session touching *any* profile or accumulation code will otherwise get
them wrong — Ω has two spellings that differ by design, the scalar loop
is an oracle rather than dead code, and the phase scatter's grouping is
observable.  The operating detail did go down: the ratios and the
equivalence measurements are in the WP's § Findings, the method notes in
the v1.1 record, and the bars are executable in tests/test_batched_forward.py.

784 -> 804 for WP-1115 (2026-08-22): the numpy path now has a compiled
tier and it is what a default install runs, which no other line in this
file implies and which a session touching any residual, Jacobian or
packaging code will get wrong without it — that the tier is not a
backend, that its numpy fallback is mandatory *and* must stay exercised
(numba is required because an extra cannot subtract a dependency, so the
way out is a runtime switch), what shape a new kernel takes, and what bar
it is held to.  The measurements, the `prange` comparison and the three
traps stayed down a rank: § The decision in the WP, the v1.1 record's
narrative, and the bars executable in tests/test_compiled_kernels.py.

804 -> 817 for WP-1121 (2026-08-22): how to *verify* an analytic Jacobian
branch, which the clause above it only says how to *scope*.  It earns a
clause because the trap is silent and points the wrong way: the
whole-model FD is the branch's own fallback, so a session reaches for it
as the oracle, and on a transformed parameter it certifies the column
being replaced while condemning the exact one that replaces it (measured
at 2e-11 agreement with a column 4.6e-6 from the truth).  The operating
detail went down a rank as this comment requires — the step sweep, the
per-state golden diff and the seam decomposition are in the WP, the
column's own reasoning in `_scale_column`'s docstring.

817 -> 833 for WP-1123 (2026-08-22): a staged plan stops its intermediate
stages early by default, which changes what every fit in the package
returns and is not implied by any other line here.  A session that never
opens strategy/ still needs three of its clauses: the schedule is the
plan's and is applied by one authority (a runner reading Stage.ftol
reintroduces the second opinion), cumulative staging is what bounds the
cost so the bound is a property of the runner rather than of the presets,
and a record must say what a stage RAN at or a cherry-pick replays what
never happened.  The measurements went down a rank as this comment
requires: the harness table and the esd shifts are in the WP's handover
and the v1.1 record, the trade in docs/manual/using/refining.md, the
decision beside the numbers it produced in tests/validation_matrix.py.

833 -> 834 for WP-1122 (2026-08-22): one line, extending a fence that is
already here.  The peaks buffer is now behind FPA rather than merely
unbuilt, and the clause carries the measured reason a session cannot
re-derive cheaply — shape reuse needs more FCJ images a window point than
any symmetric family has, so a re-attempt without FPA repeats 1114's and
1122's no-go.  The measurements went down a rank as rule 4 requires: the
break-even table, the Amdahl share and the two ways to mis-measure it are
in the WP's § Findings and the v1.1 record's narrative.

834 -> 845 for WP-1125 (2026-08-22): a fence, like 1122's, and for the
same reason — the idea behind it is attractive enough to be re-proposed
by anyone who notices that the background is linear.  What cannot go
down a rank is the one sentence that settles it without re-deriving
anything: the profiled Gauss-Newton step IS the joint one, so variable
projection asks this solver for the step it already takes.  The
measurements went down a rank as rule 4 requires: the 70-stage table,
the trust-radius mechanism and the two gates that failed for reasons
unrelated to their names are in the WP's § Findings, the survey's §2.A1
and E5 notes, and the v1.1 record's narrative.

845 -> 855 for WP-1127 (2026-08-22): the ladder's first-rung bound, and
like the two fences above it is here because the *wrong* version of it is
the attractive one.  Two clauses cannot go down a rank without being
re-derived by whoever proposes the next bound: what a bound may be
derived from (only a rung that did the same job and converged — the cold
fit reads as free evidence and is false), and the two places a bound
would otherwise reach the answer, neither of which is where it is
applied.  The measurements went down a rank as rule 4 requires: the
cold-9-warm-14 refutation, the per-case tables and the pre-registered
clause that fired are in the WP's § Findings and the v1.1 record.  The
last two lines are the third such trap and the one that cost a CI round:
a threshold set for effect rather than for margin, which two of four
python versions on the other platform caught and a green local full suite
did not.

855 -> 869 for WP-1204 (2026-08-25): developer mode and the shipped
example projects.  Two clauses cannot go down a rank.  The first is a
property of the *project format*, not of the GUI: there is no read-only
way to open one, because every verb writes into the directory as it runs
and `Project.open` appends a head annotation before any verb is called —
a session that never opens gui/ still has to know that opening a checked-
in project dirties it, and what to reach for instead.  The second is
where an example's protocol comes from: an example IS a `compare.py`
standard, so a WP tempted to write a project builder has to know the
registry is the authority.  The third is the data licence fence, which
belongs in the Licensing invariant beside the code one because the two
are asked at the same moment and only one of them existed.  The operating
detail went down a rank as rule 4 requires: the routes, the state-dir
placement and the traversal refusal are in gui/CLAUDE.md, the per-file
licence table is `tests/test_example_projects.py`'s, and the measured
wheel sizes are in the WP's handover.

869 -> 882 for WP-1202 (2026-08-25): the help corpus.  The operating
detail went down a rank as this comment requires — the registry's own
rules are in `help.py`'s docstring, the entries are the corpus, the
measurements are in the WP.  What cannot go down a rank is the one clause
a session adding a parameter, a flag or a stage field will otherwise miss:
the description goes in `rietx.help`, not in a `title=` beside a control
or a second `Field(description=)`, and the row carries the family key
rather than the entry.

882 -> 890 for the one-session-per-tree tooling (2026-08-27): the rule a
session must read before its first edit, and nothing else — the gate's
own rationale is its docstring, the ritual is /wp-start.

890 -> 898 for WP-1017 (2026-08-28): the GUI is documented and no longer
beta, and the manual gained a third guard for a subject that is routes
and panels rather than importable names.  What cannot go down a rank is
the clause a session that never opens `docs/manual/` still needs — adding
or renaming a GUI route or a tab now fails a test until a chapter covers
it, which is the manual bullet's existing shape one vocabulary over.

898 -> 906 for WP-1306 (2026-08-29): the PowderLine recipe reader, folded
into the existing cross-code bullet rather than given one of its own.  The
operating detail went down a rank as this comment requires — the whole
convention table with how each row was measured is `tests/data/README.md`
§ v1.3, the format's own rules are `src/rietx/io/CLAUDE.md`, and the
consumer-facing chapter is `docs/manual/using/recipe.md`.  What cannot go
down a rank is what a session comparing against *any* other code needs
before it sets a tolerance: two references that disagree by more than the
bar make agreement with both impossible, and a unit a format states two
ways is refused rather than picked.

906 -> 760 for the compression pass (2026-09-01), which is the direction
this comment block has never gone before and so states its method: no
rule, identifier, dot-path, diagnostic code or measured number left the
file (checked mechanically against the pre-pass copy — 50 WP numbers, 57
SHOUTING constants, 96 file paths and 477 inline code spans, all still
present).  What left is connective prose and the mechanism a pointer
already covers: a derivation the linked survey section carries, a
private helper named only to explain why a rule holds, the sentence
after the one that states the rule.  Landed at 736 lines and 8612 words
(from 906 and 9529, i.e. -9.6 % of the words a session pays for on every
request).  The cap is landed + 24 because the admission rule is
unchanged: a line enters as a standing rule, evidence compressed to one
clause plus a pointer.  A future session finding a clause too thin
should restore it from the WP file it names rather than reasoning from
what is left here.

760 -> 722 for the placement pass (2026-09-01), the compression pass's
other half: that one shortened prose, this one moves whole clauses to the
rulebook that already owns them.  Three sections went down a rank — the
GUI section to gui/CLAUDE.md, the indexing bullets to
src/rietx/indexing/CLAUDE.md, the key-test-data table to tests/CLAUDE.md
— and each destination's cap moved by what it received, so the fact count
across the four files is unchanged (checked mechanically against the
pre-pass copies: every WP number, SHOUTING constant, measured number and
file path still present in the union).  What stayed here is what a
session that never opens the subtree still needs: the run state is not an
event, a project has no read-only open, and indexing's three clauses that
reach outside indexing/ (no confident singleton, `quick` is the default,
run the indexing acceptance suite before closing an engine change).
Landed at 698, cap landed + 24 as above.

723 -> 732 for WP-1330 (2026-09-02): the skill bullet grew from three
lines to twelve, because a session that measures a rule an agent
*driving* rietx needs had nowhere told where it goes — protocol rule 4
routed findings to the handover log and named no third destination.
What enters here is the routing (skill / CLAUDE.md / handover), the
shape rule (one `references/` file per task shape, numbered under the
body section it specialises), the evidence tag and the cap-is-paid-for
rule; the row form and the sync commands are CONTRIBUTING.md § The
agent skill's.  Landed at the cap.

732 -> 739 for WP-1331 (2026-09-03): a landing page joined the repository
at docs/landing/ and took the site root.  The subsystem detail went down a
rank as this rule requires — docs/landing/README.md is the file map, the
build's two shapes and the fence on the contributor's data, and the
gitignore reasoning is in .gitignore's own block and tests/test_landing.py's
docstring.  What could not go down a rank is what a session that never opens
docs/landing/ still meets: the manual is now /manual.html so a link meaning
"the manual" is never the site root, and conf.py's conditional
html_extra_path puts pages Sphinx never rendered into the build output, which
a guard walking that output must exclude rather than widen itself around
(one already had to).  Landed at the cap.

923 -> 929 for the magnetic index split (2026-09-18): one clause saying a task
shape's **entry points** render to a generated `api-<shape>.md` rather than
into the everyday `api.md`.  The sentence beside it already sent a shape's
authored rules to `references/<shape>.md` and said nothing about the generated
names, which is the half a contributor adding a verb actually touches — so a
reader following CLAUDE.md alone would put a magnetic verb into the file every
session about to call rietx loads whole, and every session that will never
refine a magnetic structure would pay for it.  The reason is the reader's
context and the byte cap follows from it, which is why this is stated where
the admission rule is and not only in the test.  It governs every technique
after magnetic — TOF, texture, PDF — which is protocol rule 4's test.  The
mechanism went down a rank as this rule requires: the gate is a glob over
`api*.md` in `tests/test_skill.py`, and why an authored reference and a
generated index are different objects is `make_api_index.py`'s docstring.
Landed 925, +4 headroom.

929 -> 938 for WP-1434 (2026-09-18): the bound test asks whether the limit
carried load, never whether the value stopped near one.  The clause runs to
eight lines because the shape is the content: it is a conjunction, and each half
covers exactly what the other cannot, so a reader given one half alone would
weaken it back to the test that went silent on nine of 32 binding cases.  It
governs every consumer of `BOUND_HIT` and `at_bound`, and every bound anyone
adds after it, which is protocol rule 4's test — and a session reading a
`False` it disagrees with has no way to re-derive the change from the code in
front of it.  The operating detail went down a rank as this rule requires: the
two thresholds carry the windows they were measured into in their own
docstrings, the sweep and the two fixes the issue proposed and measurement
ruled out are in the WP, and the user-facing sentence is the 1.5.1 release
note.  Landed 937, +1 headroom.

938 -> 954 for WP-1435 (2026-09-18, recorded 2026-09-19): a hold the caller
declares, and why it had to be a mechanism rather than a message.  `vary=False`
does not survive a plan, so the rule is owed to every session that writes a
plan, a calibration or a `set_vary` call site, not only to the one that built
the verb.  The clause also states the two facts that bite a caller who does not
know the verb exists: `set_vary` can refuse now, so read its return rather than
the list you offered it, and `_user_holds` is not WP-1301's stage-scoped
`_held`.  The precedence order, the blocked-glob report and the measured LaB6
counts stayed in the WP.  The session landed the clause and its cap and left
this paragraph and the ledger row unwritten; both are reconstructed here from
the cap note it did write.

954 -> 963 for WP-1432 (2026-09-19): a coordinate DOF is relative, and the
invariant that keeps it honest is that a rebuild reproduces the coordinate.  It
sits beside the DOF bullet it qualifies because the two facts a stranger needs
are about *other* code.  Which entries are anchored is data built where the
anchor is, so a new DOF family inherits nothing by spelling its paths the same
way — ADP and Stephens DOFs already spell them identically and are absolute.
And each consumer of the tie register calls the rebase, so a third one written
without the rule carries the defect `replay` carried alone.  The measurement,
the two controls that bound the class and the two rejected fixes stayed in the
WP.  Landed 962, +1 headroom.

### `docs/ROADMAP.md`

400 -> 416 for the agentic-report planning session (2026-08-18): four
v1.1 WP rows (1104-1107) plus their focus bullet.  Index rows cannot go
down a rank — the WP-file/row bijection test in this file requires one
per WP — so the cap grows with the WP count and with nothing else; the
sets' narratives live in the WP files.

416 -> 438 for the refinement-speed planning session (2026-08-20): the
v1.1 speed set (1109 moved + five new rows and its intro) and the v1.1
Milestones row.  Same rule as the bump above: rows cannot go down a
rank, so the cap grows with the WP count and with nothing else.

438 -> 439 for WP-1116 (2026-08-20): its own index row, and only that.
The same WP also rewrote § Session protocol's rule 3, which is two lines
longer — prose, so by the rule above it earns no bump and was paid for
by compressing Current focus instead.  That is the rule working: the
cap is a budget on narrative, and a row is not narrative.

439 -> 455 for WP-1110 (2026-08-21): one section and two rows for the work
the agent round found and no milestone owns yet — 1118 (foreign model
files) and 1119 (the named variable a foreign equation refers to).  The
rows are not narrative and the prose is eight lines for both, because the
fences, the measured behaviour and the acceptance live in the WP files.
Current focus was rewritten in the same pass and paid part of it back.

455 -> 457 (2026-08-22): the two probe rows the solver-survey
re-assessment opened — 1124 (warm-series continuation, survey B8) and
1125 (variable-projection probe, survey A1/E5).  Rows only: the
motivation and disposition live in solver-survey.md §5 and the WP
files, and the Current focus mention replaced text inside an existing
line.  Same rule as the bumps above: a row is not narrative.

457 -> 458 for WP-1126 (2026-08-22): its own index row, and only that.
The manual style pass touches no always-loaded file: the review's rules
went into the yue-docs-style skill and the chapters, and the WP file
carries the measurements.

458 -> 459 for WP-1127 (2026-08-22): its own index row, and only that.
The row is required rather than chosen — test_wp_files_and_roadmap_rows_
are_a_bijection makes an index row the one line a new WP cannot demote —
and Current focus was not touched at the opening, because the front it
takes over is already named there in WP-1124's closing sentence.

459 -> 473 for WP-1131 (2026-08-23): its index row, and the section that
had to come with it — the bumps above buy a row inside an existing table,
and there was no table for this one.  The five prose lines are the part a
row cannot carry: that the defect is *size* and not strain, that the two
are distinguished by the wavelength and nothing else, and the measured
size of it.  Without them the row reads as a reporting feature, which is
the half of the WP that is not a correctness bug.

473 -> 480 for the v1.2 opening (2026-08-25): a milestone section with
eighteen index rows (1201-1217 and 1017 moved in), which the bijection
test requires one line each, net +7 after Current focus was rewritten
from 30 lines to 12 and the peaks section was retitled v1.3 in place.
The per-note assessment went down a rank into milestones/v1.2.md.

473 -> 474 for WP-1132 (2026-08-24): its own index row, and only that.
The row is required rather than chosen (the bijection test again), and
every line of the WP's reasoning stays in its own file — unlike 1131 it
needs no section here, because nothing about it has to be read before
someone opens it.

474 -> 475 for WP-1134 (2026-08-25): its own index row, and only that.
The row is required rather than chosen (the bijection test).  This WP
exists because the number did not: the neutron/harmonics/wavelength work
was committed under WP-1128, which is the shipped v1.1 indexing WP cited
from indexing/svd.py -- two meanings of one number costs more than a
renumber, so the in-code citations moved to 1134 and this file names it.

480 -> 482 merging PR #108 into the v1.2 opening (2026-08-25):
the two caps above were measured against different parents, so
neither survives the merge; 482 is the merged file, both index
rows on top of the v1.2 section.

482 -> 503 queuing v1.3, agents and programs (2026-08-28): one milestone
row, and a section of seven index rows under eight intro lines.  Rows
are required by the bijection test, not chosen; the intro carries what a
row cannot and no WP file repeats: that the only agents observed are
shell-equipped sessions using the notebook API, and the three numbers
(90 API calls, 14.6 M cache-read tokens, 34.7 min for 34 s of fitting)
every 13xx acceptance is measured against.  Nothing else in the file
moved; the free-standing peaks section changed only its title.

503 -> 510 for issues #192-198 (2026-09-01): Z-matrices named beside
rigid bodies in the v2+ list, and a new "Added" paragraph for the six
other maintainer-requested features (PDF/total-scattering, charge
flipping, Rietica/XND readers, RMCProfile export, VESTA I/O) fenced the
same way the McCusker and low-symmetry-corpus additions were.

510 -> 578 for the 2026-09-01 issue triage: the 28 open issues arranged
into eleven unscheduled WPs (1309-1319) — eleven index rows across three
existing Unscheduled sections and four new ones, each new section opened
by the measured evidence its issues carry, per the section pattern this
file already uses.  The remainder of the triage cost no lines here: four
issues folded into WP-1118's own file, and the fenced items were already
named by the #192-198 bump above.

578 -> 589 for the triage's second batch (2026-09-01): the five issues
newer than PR #205 (#202-204, #207, #209) arranged into three
unscheduled WPs — three index rows and their evidence sentences across
the two existing sections whose subjects they extend; #202 and #204's
construction half cost no lines, being in-flight PRs (#208, #206).

589 -> 597 for the roadmap reorder (2026-09-01): the file was rewritten in
milestone order — one section per milestone, status cells reduced to glyph
and date, seven Unscheduled sections merged into one, Current focus cut from
nine ~1000-character paragraphs to 210 words — and landed at 573 lines and
6791 words (from 589 and 8613).  The line count barely moved because the
old file's prose ran to 1000-character lines and the new one wraps; the word
count is the honest measure, and the new word cap on Current focus exists
because a line cap was met by exactly that.  Three WP rows were added (1323,
1324, 1325) and every close narrative a cell carried went to the WP file's
own Status line, checked number by number.  Cap landed + 24, as CLAUDE.md's
compression pass set the convention; the admission rule is unchanged, and
two new tests keep the shape — a row's section mirrors its WP's Milestone
line, and a status cell is a glyph and a date.

597 -> 621 for the magnetic scattering track (2026-09-02): a section and four
rows (1326-1329), landed 597, cap landed + 24.  Recorded here after the fact,
in the 2026-09-03 bump below; the diary had missed it.

621 -> 645 for the 2026-09-03 issue triage: the 22 issues newer than the
2026-09-01 rounds arranged into ten unscheduled WPs (1332-1341) — ten index
rows across the three existing Unscheduled sections whose subjects they extend,
plus one new section for the costs a multi-hundred-pattern campaign paid and a
single fit never sees.  Landed 639, then 641 after the same-day re-check.
Same rule as every bump above: rows cannot go down a rank, so the cap grows
with the WP count and with nothing else, and the evidence lives in the WP
files.  The three remaining issues cost no lines
here, being folded into WP-1118, WP-1310 and WP-1322's own files; Current focus
paid for its new sentence by cutting four closed WPs' narratives back to their
numbers, which their own files already carry (protocol rule 5).

645 -> 762 in six bumps between 2026-09-13 and 2026-09-18, each one a row or
a section and each recorded in `tests/test_docs_consistency.py`'s own ledger
above `SIZE_CAPS`, which is the complete one; they were not copied here, and
this paragraph is the note saying so rather than a reconstruction.

762 -> 784 for the v1.6 open (2026-09-18): § v1.6 over the seven magnetic rows
§ Unscheduled already carried.  The structure — one `###` and one table header
— is the standing rule and costs two lines.  The rest is two paragraphs of
ruling taken at the open, and they are the first entry in this diary that is
not narrative *about* rows: the PR order inside the milestone, and that neutron
TOF stays at the v2+ fence although a contributor's integration branch carries
it merged into the magnetic chain.  Neither demotes to a WP file, because the
reader they are written for is building against this index from outside the
repository and reads no WP file until a PR is cut.  Paid for twice, in Current
focus (a closed WP's narrative and the triage fold list) and in § Unscheduled
(the blurb describing the rows that left).  Landed 778, +6 headroom.

784 -> 818 in two bumps on 2026-09-21 and -22, both recorded in the test's
ledger: the issue triage's two rows and its placements, then WP-1442's four
siblings.

818 -> 828 for the priority column (2026-09-23).  One paragraph under § Work
packages says what the `Priority` cell is, that the WP file's line is its
authority and that `—` means unrated.  The column itself costs no lines:
eleven table headers on the open sections widened and sixty rows given a `—`
cell.  The rubric lives in `docs/wp/TEMPLATE.md`, which is not capped, and
the re-rating duty is one clause in protocol step 3.  Rows filed before the
rubric stay unrated on purpose; the index says which tier a new WP is and
never claims one for a row nobody rated.  Landed 827, +1 headroom.

828 -> 831 for the 2026-09-23 issue triage: three rows under § The repo's own
process, 1450-1452.  No prose.  Landed 830, +1 headroom.  (Recorded
2026-09-24; that session wrote only the test's ledger line.)

831 -> 835 for the 2026-09-24 review of an agent session on a private in-situ
series: four rows, 1453-1456, in three existing sections.  A fifth finding
went into WP-1420's `### Inherited` rather than a row of its own.  No prose,
because each WP file carries its own evidence.  Landed 834, +1 headroom.

835 -> 840 for the 2026-09-24 issue triage: three rows, 1457-1459, under two
existing sections, and one sentence on #374's second instance.  Landed 839,
+1 headroom.  (Recorded 2026-09-25; that session wrote only the test's ledger
line.)

840 -> 846 for the 2026-09-25 review of a second agent session on the same
private series: two rows, 1463 and 1464, in two existing sections, and one
sentence on #374's third instance.  Four more findings went into the
`### Inherited` of 1322, 1420, 1455 and 1456.  Landed 845, +1 headroom.

846 -> 851 for the 2026-09-25 issue triage: one row, 1465, under § What
fires, and what stays silent, and four lines in § v1.6 recording the order
#286 asked for.  Landed 850, +1 headroom.

851 -> 852 for the 2026-09-25 review of the same private series' Stephens
runs: one row, 1467, under § What fires, and what stays silent.  No prose.
Landed 851, +1 headroom.

880 -> 571 for WP-1507 (2026-09-27): the cap goes down, and its rule
changes.  The 34 WP tables left for `docs/wp/README.md`, which
`.claude/hooks/wp_index.py` generates from the WP files' headers, and Current
focus kept milestone prose, its WP-level paragraphs moved to the v1.6 record.
The rule above, that a row is not narrative and the cap grows with the WP
count, has no rows left to apply to.  Filing, starting or closing a WP no
longer touches ROADMAP, so the cap now moves only when prose does.  Landed
570, +1 headroom.

571 -> 579 for the structure track (2026-09-28, WPs 1510-1517): prose, so
the new rule applies.  One new § Unscheduled group with the three-line blurb
the other groups carry, and the fence paragraph rewritten to say what left
it and when.  The blurb was cut from five lines to three before the cap was
touched; the evidence behind it is DESIGN.md's *Structure fence revised* and
the WP files.  Landed 578, +1 headroom.

579 -> 588 for v1.8 and v1.9 (2026-09-30, WPs 1801-1803 and 1901-1902): two
milestone table rows and two headings the WP index needs, each with a
one-line blurb, prose as the rule counts it.  The first draft's sections
(31 lines) were cut to these before the cap was touched; the sequencing
constraint lives in WP-1803 and WP-1514's `### Inherited`.  Landed 588, no
headroom.

### `gui/CLAUDE.md`

580 -> 612 for WP-1201 (2026-08-25): the house style — one token layer
and the nine control registers, as a table of one rule each.  This file
grows for a rule nothing else in it carried, same as the bumps above: a
panel's `<style>` block was the authority on its own controls, so six
button geometries and three chip geometries were all locally correct.
The vocabulary has to be here because every later v1.2 panel WP writes
markup against it, and a table is the compressed form — the inventory,
the measurements and the three misuses it exposed are in the WP.

612 -> 628 for WP-1204 (2026-08-25): the examples surface.  Here rather
than in root because it is the *empty state's* second list and its rules
are the GUI's own — where a built example lives and why, that the open
verb ends in `project_open` so nothing downstream can tell an example
from a project, and that `name` is checked against the list rather than
sanitised.  The last of the five is a house-style consequence the WP-1201
table above could not have carried: `.pick` gives up its box because the
row is the target, so a list that gives the row no hover reads as prose.
The operating detail went down a rank as rule 4 requires — the licence
table is `tests/test_example_projects.py`'s, the protocol-quoting rule is
root's, and the browser session that found the missing hover is the WP's.

645 -> 663 for WP-1205 (2026-08-26): the filesystem browser. A stranger
touching `App.svelte`'s layout needs the invariant this WP's own bug
was found under — `Model` is mounted exactly once, never one instance
per branch of `{#if project}` — because the failure mode (a stale
`wizardOpen` painting the wizard over a freshly-opened project) is
invisible until the *next* session recreates the split and re-derives
the same bug from nothing. `GET /api/fs`'s containment shape and the
settle-on-open convention (`openPath()`) are the other two facts no
test alone would tell a reader to preserve.

628 -> 645 for WP-1203 (2026-08-26): the help popover, replacing the
`title=` paragraph WP-1201 wrote as a placeholder.  It belongs here for
the reason the register table does: every later v1.2 panel WP writes
markup against it, and there are five rules a stranger cannot read off
the code — why a key carries its arm, when a field inventory derives its
key and when it carries one, what `<Help text=>` is for, what may still
be a `title=`, and why a term is a span with a role.  Compressed to one
clause each: the 151-attribute inventory, the two decisions taken against
this WP's own written design, and the flex-minimum defect the browser
pass measured are in `docs/wp/1203-help-popover.md`.  One rule *left*
this file in the same pass — WP-1032's "`title=` is these forms' only
help mechanism" is no longer true, and its no-mute-fields half stayed.

663 -> 687 for WP-1206 (2026-08-26): a project without a CIF.  Four rules
a later panel WP cannot read off the code — that `structure` now has four
forms told apart by disjoint keys, that a constrained cell is *offered*
rather than validated (which is where the free/determined split has to be
decided, and it is a crystallography call, not a form's), that a mode is
refused rather than overridden here while Adopt does override, and the two
form-drawing facts a browser found: a register's width belongs to the call
site, and a numeric placeholder reads as a filled value.  The measured
detail — the fit, the four browser defects, TOPAS's macro shape — is in
`docs/wp/1206-typed-cell-project.md`.  687 -> 691 in the same WP's review
round: the mode clause had to name **both** routes `_as_structure` serves,
because a new form added at that one boundary reaches every verb crossing
it — the typed cell was accepted by `PATCH /api/structure` too, where it
would leave a rietveld project refining a dummy carbon.  That is the
generalisable half, and it is what a later WP adding a third form needs.

691 -> 710 for WP-1207 (2026-08-26): the third answer to step 2, whose
four rules a later panel WP cannot read off the code.  Two of them are
the earlier clause's own shape one turn further — the `structure` forms
are told apart at one boundary, so the fifth (`null`) had to be decided
*ahead* of the inline branch it used to fall through; and null is an
answer where an absent key is not, which `dict.get` cannot express.  The
other two are where the refusal lives (the verb, never the model — so
peak picking and indexing keep working) and why `n_phases` rides on the
project document, which is what lets a client disable Run rather than
offer a click whose only outcome is a 400.

710 -> 733 for WP-1208 (2026-08-27): the plan resolved against the live
table.  The operating detail went down a rank as this comment requires —
the three-bucket partition, how the dynamic held-reason is reached
without spelling its sentence twice, and the node-to-rung alignment are
in `GuiSession.plan_resolve`'s docstring, the panel's own rules in
`Plan.svelte`'s header comment, the measurements in the WP.  What cannot
go down a rank is the one a later panel WP will otherwise get wrong: a
plan does not continue the vary flags a person set, it replaces them, so
`Run all` and `Run this stage` start from different tables — and the
per-stage Rwp already exists on the history node, which is why the run
verb did not have to grow a trajectory to show it.

733 -> 753 for WP-1209 (2026-08-27): the peak table's numbers and chips.
Two of its four rules reach past the panel — an esd that has swallowed
its value is not a precision (every caller of formatValue), and a chip's
words are the corpus's label — and the fourth is a browser-only trap: a
`td` that is not `display: table-cell` merges with its flex neighbour
into one anonymous cell, which jsdom cannot see and a shared class name
triggered.

753 -> 774 for WP-1210 (2026-08-27): the peak layer.  Its four rules all
reach past the panel — where a layer may be drawn at all (and that the
tab is therefore a drawing input, not a fact about the payload), that an
undrawable curve is listed with its reason rather than dropped, that
chrome tokens are not a palette (`--accent` *is* `--plot-diff` on the
light theme, which is the reported defect), and that a mark's state is
carried by its shape rather than by spending a colour.  The hex values,
the hue search and the two grandfathered pairs are a rank down, in
`app.css`'s own comment and `tests/test_gui_palette.py`.  774 -> 778 in
the same WP's review: the state-on-the-mark rule needed its corollary,
because that is where it was broken — a mark that is not the data may not
borrow the recessive ink of the data it sits on.

778 -> 808 for WP-1211 (2026-08-27): the candidate overlay, whose five
rules are each about a *different* thing a later panel will meet — which
of two shifts belongs on a drawn position, how a cap admits it capped, why
a layer selected from a row gets no toggle, why a preview and a selection
have to be two props, and what "full height" costs in plotly.  None of
them generalises from another, and the two the drawing depends on are
browser findings.  The operating detail went a rank down as this comment
requires: the shift algebra and the enumeration counts are in
`GuiSession.index_ticks`'s docstring, the drawing order and the axis in
`Plot.svelte`'s, and the measured numbers in the WP's handover.

808 -> 838 for WP-1212 (2026-08-27): a redraw never moves the axes.  Six
rules, four of them browser findings that no reading of the code reaches
and none derivable from another — what `autorange === false` stopped
meaning, which field carries the range plotly is *drawing* with, that a
layout key is a relayout rather than a repaint, that a `$derived` off the
project arrives new-but-equal on every settings PATCH, that two `$state`
assignments either side of an `await` are two flushes, and that an empty
`scattergl` trace has no index in the scene its peers share.  The first
two rewrite what the WP-1044 section above claims, so they cannot live
only in a WP file.  Operating detail went a rank down as this comment
requires: the pin's mechanics are `pinPatch`'s and `drawnRange`'s
docstrings, the gesture's ink is the `.select-outline` rule's comment,
and every measured number is in the WP's handover table.  840 after the
review pass added the seventh: an axis with nothing on it is not pinned.

840 -> 874 for WP-1213 (2026-08-27): the hover readout.  Seven rules, and
the first of them rewrites what a stranger would otherwise try — the
unified box has no positioning, so it is deleted and `hoverinfo: "none"`
is what keeps the spike; a WP file cannot hold that, because the next
session's instinct is to move the box.  Three are browser findings no
reading of the code reaches (the strip must not reflow, the spike's ink
collided with the mask edge, two spellings of minus in one row), one is a
svelte trap the whole app can hit (`$state.raw` for a payload that is
replaced whole), and none derives from another.  Operating detail went a
rank down as this comment requires: the field list and the resting state
are `readout`'s docstring, the strip's widths are the `.readout` rule's
comment, and every measured number is in the WP's handover.  879 after
the peaks-tab pass added the eighth: a curve is read at the nearest drawn
channel and a nearby thing is hit-tested against the pointer, because the
drawn pattern is decimated and the two are not the same position.

879 -> 902 for WP-1214: the refine flag in the model editor, and with it
the fourth held reason (`needs_held_cell`) that WP-1011's three-mark
sentence had been wrong about since it arrived.  Four rules and one width
trap; the measurements are in the WP's handover.

902 -> 938 for WP-1215: the atom table becomes one row per atom, and the
coordinate becomes a cell in it.  Four rules, and the third and fourth are
the ones no reading of this subtree reaches — a memoised answer changes
*who may ask* without changing which route it is on (with the three client
rules that come with fetching it beside another fetch rather than after
it), and a width written in three places had a test on one of them.  The
operating detail went a rank down as this comment requires: the refusal
wording is `position_values`' docstring, the per-state pixel measurements
are `MODEL_MIN`'s and the WP's handover.

938 -> 962 for WP-1216: the instrument form becomes one grid of three
columns.  Four rules, and two of them are about *who decides a width* —
a form's column count is a promise no wrap point or container may take,
and a declared column count is a declared minimum, which is what moved
`MODEL_MIN.form` and put WP-1215's stale-width lesson under a test rather
than a comment.  The nine measured configurations are in the WP.

962 -> 995 for WP-1217: the history graph becomes a git graph and the
compare table's numbers hold their columns.  Five rules, and the two that
earn the lines are browser findings no jsdom test could make — an edge has
to *hold* a lane for its whole span before a one-row crossing is drawable
at all, and a `ch` width is a shared column only while every cell in it is
one font at one size.  The measured offsets are in the WP.

995 -> 1019 for WP-1017: the GUI has a manual, and two of the
vocabularies it is *about* are held to the app by test rather than by
care.  The lines go on the four rules a session working here has to know
before it renames anything — routes and panels partitioned both ways, the
authorities swapped where no python object knows the fact, a screenshot
generated by one script and judged by looking, and a first-run aid whose
steps are derived.  The operating detail went down a rank as this comment
requires: how each picture is taken is `make_screenshots.py`'s docstring,
the partition's shape is `test_gui_manual.py`'s, and the counts are in
the WP.

1019 -> 1028 for the placement pass (2026-09-01): the two clauses root was
carrying about this app that nothing here restated — a project has no
read-only way to open it (`--scratch`, `--state-dir`, `*.rex/` in
.gitignore) and an example project *is* a `compare.py` standard, so the
examples route restates no protocol.  Root kept the half that governs
`Project.open` itself; the flags are here because they are flags on this
command.  The other two root GUI rules needed no lines: the 409 and the
theme's scope were already stated here in full.

### `tests/CLAUDE.md`

180 -> 198 for WP-1070 (2026-08-15): the running ladder.  It is a rule
about *cadence*, which nothing else in this file carried — the sections
below all say how to run or read one suite, none said how often the
expensive one should fire.  Measured occasion: one session's ~80 min of
test time against ~43 min earned, the whole difference being a full run
launched mid-edit and therefore repeated.

198 -> 205 for WP-1003 (2026-08-16): the budget section's numeric twin —
a cross-fit agreement tolerance needs the measured cross-platform
spread.  The section covered wall-clock budgets only, and the weekly CI
failure that taught the rule was numeric.

205 -> 223 for WP-1110 (2026-08-20): a second eval protocol exists
(tests/eval_agent_surface/), and a session under tests/ that does not
know it will either miss it or pool its cells with the first one's.  The
clause is a rule about comparability and about what a shim owes its
subject, not a record of the round — that lives in the WP and the
protocol.  Same rule as the bumps above: this file grows for a rule that
nothing else in it carried.

223 -> 232 for WP-1115 (2026-08-22): a test that pins a number must
declare its *path*, not only its settings.  Nothing else in this file
carried it — the dispersion clause one rank up is about a schema default,
and this is about which implementation computed the double — and the
failure has a signature worth naming, because it is otherwise read as
flakiness: green alone, red under `-n auto`.  The tier itself, its bars
and its measurements are all a rank down (root CLAUDE.md, the WP).

232 -> 246 (2026-08-26): rung 3 is exclusive across the sessions sharing
this machine.  Nothing here carried it — the budget rules below say load
breaks an assertion, not that a second session is what supplies the load —
and it could not go down a rank, being about *running* the suite, which no
other always-loaded file governs.  It is a look (`pgrep`) and not a lock
on purpose, which is what kept the raise to fourteen lines: reserving
would have needed a script, a release to forget and a staleness rule,
while observing needs one command and can state its own evidence.

246 -> 253 for WP-1017 (2026-08-28): the worktree-venv rule gains the
direction it did not cover.  `uv pip install` prefers an inherited
VIRTUAL_ENV over the cwd's `.venv`, so the documented build command, run
inside a fresh worktree, installed that worktree's source into the *main*
checkout's venv — pointing a concurrent session's tests at this session's
tree.  A rule about which venv a count came from is worth nothing if the
command that builds it can silently retarget the other one.

253 -> 275 for the placement pass (2026-09-01): the key-test-data table
came down from root, where it was a third copy of a subset.  It is not
provenance — that is tests/data/README.md, which this file already
pointed at — but the rule a session needs before it picks a fixture:
which dataset is an absolute anchor, which is a cross-code consistency
check and not truth, and which carries a weighed composition.  A claim
referenced to the wrong one is green and worth nothing, and nothing in
this file said so.

### `src/rietx/indexing/CLAUDE.md`

250 at the WP-1060 split; raised once, for WP-1046's two standing rules
(which layer may apply a cap, and that agreement outranks the panel) —
both measured, and every number behind them is in the v1.0 appendix

280 -> 296 for WP-1110 item 14 (2026-08-21): a component at its zero
intensity bound is not a line.  The operating detail went down a rank as
this comment requires — the flag's semantics are on `PeakFlag` and
`PEAK_UNUSABLE_FLAGS`, the mechanism in `peaks_of_group`, the numbers in
the WP.  What cannot go down a rank is that this class of phantom was
*invisible* until the covariance was equilibrated, so a session reading
the peak list's history will otherwise assume the not_separable fix
cleared it.

296 -> 300 for the placement pass (2026-09-01): the search-tolerance
paragraph stops deferring to root for its rule and states it whole,
absorbing the two facts that lived only there — the diagnostic code the
allowance is reported under (an assumed precision must never look like a
measured one) and the +1400 ppm bias a cell that was never shift-refined
carries.  Root's clause is gone, so the cross-reference had to go too.

### `src/rietx/io/CLAUDE.md`

200 at the .ras/.uxd consolidation; raised once with three container
formats still to land, each of which is a row in its per-format table

250 -> 271 for WP-1306 (2026-08-29): `recipe.py`, whose first job is to
say it is **not** a pattern format, so none of the dispatch, options and
sigma rules above govern it.  The operating detail went down a rank as
this comment requires — the measured convention table is
`tests/data/README.md` § v1.3, the consumer chapter is
`docs/manual/using/recipe.md`, and every refusal's wording is the module
docstring.  What cannot go down a rank is the five rules the *next*
foreign format read in this subtree will need before it is written.

271 -> 294 for WP-1118 (2026-08-27): `io/projects/` is a second kind of
reader in this subtree and needs its two rules stated where a session
working here loads them — derive obligations from the specification and
corroborate with files (three of the round's six corrections are
invisible to any archive sweep), and refuse where a pattern reader would
repair.  The operating detail went down a rank as this comment requires:
the derived format model is `projects/topas.py`'s own docstring, the
per-construct decisions and every incidence are the audit table in the
WP, the measured counts are `tests/data/README.md`.

294 -> 300 for WP-1118: the coverage registry is the "classify every name"
rule of the section above acquiring an implementation, so the clause names
where the table lives rather than restating what it decides.

300 -> 350 for WP-1407 (2026-09-13): two readers and two refusals, so four
rows in the per-format table, plus three rules the Philips √ encoding
taught and a fourth axis case.  The rules are what a cap is for: a format
may **encode** its counts rather than store them, and only a real file says
so; the *permissive* description can be the defective one, so a description
is checked against a file before it is believed; and a format's own
redundancy is the gate to reach for, refused on disagreement rather than
repaired.  Each governs the next format anyone adds here, which is protocol
rule 4's test, so none could go down a rank.  What did go down: every
measurement — the 28-file offset table, the four confirmations of the √
rule, the 19-key `.udf` vocabulary — is `tests/data/README.md` § Philips,
and which source each fact came from is `ATTRIBUTION.md`.  The blocks were
cut by roughly a third before the cap was touched, per this comment's own
instruction; 344 landed against the 350.

## What a session's reading costs

Measured 2026-09-30 for `/pr-review`
([#548](https://github.com/yue-here/rietx/pull/548)) and carried to the WP
commands the same day. The rules are `/pr-review` step 6, `/wp-start` steps 2,
5 and 6b, and `/wp-handover`'s opening note and steps 5, 7 and 8. The numbers behind
them are here.

**The mechanism.** A token that enters the main session is paid for twice.
It is written to the cache once, at the 1-hour TTL (2× base input: $8/MTok on
Opus 5.5). It is then read again by every later request at $0.20/MTok, the
same price on Opus 5.5 and Sonnet 5.5. At a 400K context, a request costs
$0.08 of reads before it does anything. The write outweighs the reads until a
token has been re-read 40 times, so the write dominates a short session's
bill and the reads dominate a long one's. Both scale with what enters the
context.

A subagent's reading is written at the 5-minute TTL (1.25×) and ends with the
agent. The agent starts from its own base context, 38K-104K in #548's runs.

**#548's measurement**: three `/pr-review` runs, with per-request `usage` from
the transcripts, de-duplicated by message id. The script is in #548's body.
Output is excluded, because agent transcripts record it only partially.

| run | requests | cache reads | cache writes | cost (reads + writes) | per PR |
|---|---|---|---|---|---|
| 2026-09-29, 1 Opus agent, 6 PRs, read-only | 165 | 52.3M | 0.51M | $13.01 | $2.17 |
| 2026-09-30, 4 Opus agents in parallel, 6 PRs | 364 | 63.6M | 1.04M | $17.90 | $2.98 |
| 2026-09-29, 10 Sonnet `pr-conformance` agents, 4 PRs | 88 | 6.2M | 0.96M | $3.63 | $0.91 |

The Opus readers cost about half what the same reading costs mid-run in the
main session. Six PRs read in-session would have taken a 306K context to
~710K, past the 500K checkpoint. A reviewed line costs about 130 tokens of
reading (404K over ~3000 lines).

**The cost model**, #548's. Re-run here, it reproduces #548's breakeven table
to the thousand tokens:

```python
OPUS = dict(r=0.20, w5=5.00, w1h=8.00)   # $/MTok: cache read, 5-min write, 1-h write
SONNET = dict(r=0.20, w5=2.50)
M, GROWTH, REPORT = 1e6, 2_400, 3_000    # tokens of reading per request; hand-back report

def n_requests(d):
    return max(3, round(d / GROWTH))

def main_cost(d, c_main, k_after):       # read d tokens in the main session
    n = n_requests(d)
    return (n * (c_main + d / 2) * OPUS["r"] + d * OPUS["w1h"] + d * k_after * OPUS["r"]) / M

def sub_cost(d, c_main, k_after, c0, p, verify_frac=0.085):   # in an agent of base c0
    n = n_requests(d)
    v = max(2, round(verify_frac * n))
    agent = n * (c0 + d / 2) * p["r"] + (c0 + d) * p["w5"]
    main = v * c_main * OPUS["r"] + REPORT * (OPUS["w1h"] + k_after * OPUS["r"])
    return (agent + main) / M

def breakeven(c_main, k_after, c0, p):
    return next((d for d in range(1_000, 600_001, 1_000)
                 if sub_cost(d, c_main, k_after, c0, p) < main_cost(d, c_main, k_after)), None)
```

**Over WP-session shapes.** The table gives the breakeven reading size in
thousands of tokens, by main context and by requests still to come. The first
figure in each cell is an Opus general-purpose agent (70K base), the second a
Sonnet `pr-conformance` agent (38K base).

| main context | 20 later | 50 | 100 | 200 | 400 |
|---|---|---|---|---|---|
| 90K | 49 / 13 | 31 / 10 | 20 / 8 | 12 / 6 | 8 / 5 |
| 150K | 33 / 11 | 24 / 9 | 17 / 7 | 12 / 6 | 8 / 5 |
| 300K | 20 / 9 | 16 / 8 | 14 / 6 | 11 / 5 | 8 / 4 |
| 450K | 16 / 7 | 14 / 6 | 11 / 5 | 9 / 4 | 7 / 4 |

Priced per read, in dollars: main session / Opus agent / Sonnet agent.

- A 60 KB file at session start (90K context, 200 later requests): 1.41 /
  0.82 / 0.44. Carry alone is 1.00 of the main session's 1.41.
- A 150 KB file there: 3.48 / 1.33 / 0.77.
- A 60 KB diff at handover (400K context, 30 later requests): 1.18 / 0.84 /
  0.46.
- A median WP file at session start (16 KB): 0.34 / 0.60 / 0.31.

A WP session differs from a review in two ways.

- **It edits what it reads**, and delegating only pays for text the session
  needs a conclusion from. What it will edit it has to read anyway, so the
  saving there is reading by range.
- **Its bar moves with the requests still to come.** It starts small: the
  measuring session's first request carried 89K, root CLAUDE.md and tool
  schemas included. Most of its requests are then still ahead, so the carry
  term dominates. For an Opus agent the bar is ~20K tokens with 100 requests
  ahead and ~12K with 200. At handover (300-450K context, 20-50 requests
  left) it is 14-20K for an Opus agent and 6-9K for a Sonnet one. So #548's
  ~20K (~50 KB) is the commands' single bar. How many requests a WP session
  makes was not measured then, so the lower figures are left to the table
  rather than stated as a rule. The median is 212 ([measured
  since](#lanes-within-a-wp)).

**Two corollaries used by `/wp-handover`.**

- **A ranged read costs one dependent request**, since a `grep -n` comes
  first. At a 400K context that request is $0.08. The same $0.08 buys ~5.7K
  tokens (~14 KB) of whole-file read at the 1-hour write plus 30 later reads.
  So a file under ~15 KB is read whole.
- **An idle gap past the hour re-writes the whole context.** The measuring
  session sat 3 hours between two user turns, and its next request wrote
  188,925 tokens at 2×, $1.51. That is more than the 45 requests before it
  had spent on reads, $1.28.

**Bytes to tokens.** About 2.5 bytes per token through `Read`, line-number
prefixes included. Measured on the measuring session's own transcript: two command
files of 25.5 KB added ~10.5K tokens, a 10.2 KB python range ~4.1K, and a
4.0 KB file through `cat` ~1.4K. So **1 KB ≈ 400 tokens**, and the ~20K /
~10K bars are ~50 KB / ~25 KB on `wc -c`.

**What there is to read, on 2026-09-30.**

- **WP files**: 295 of them, median 15.7 KB, p90 33 KB. Nine are over 50 KB.
  In five of those the handover log is half the file or more: 1118 is 156 KB
  whole and 42 KB through its newest entry, and 1067 is 113 KB and 32 KB. In
  1130 the log is a fifth, and its head alone is 60 KB, which is why
  `/wp-start` step 2 falls back to reading by section.
- **Modules**: `refine.py` is 377 KB, `model/forward.py` 195 KB,
  `params/vector.py` 144 KB and `sequential.py` 139 KB. Read whole, any one of
  them is 55-150K tokens.
- **Records**: the v1.0 record is 340 KB.

**Measured since.** The WP-shape table above is the model's, with request
counts as parameters, because no WP session's transcript was on the measuring
box. A day later 174 were measured on the maintainer's. A session makes a
median of 212 requests and peaks at a median 374K
([Lanes within a WP](#lanes-within-a-wp)).

## Lanes within a WP

Measured 2026-10-01 over this machine's WP-session transcripts.
`python3 .claude/hooks/session_usage.py baseline` reproduces every number
below. It reads every main transcript of this repository that made a
`WP-NNNN:` commit and at least 20 requests. Re-run later, it reads whatever
transcripts the machine holds then, so its numbers move. Every model is priced at its
family's current generation, so the August sessions on Opus 5 are a
counterfactual bill at Opus 5.5 rates.

A *lane* is a subagent that does one checklist item while the main session
waits. The main session then checks the diff and commits it.

**The sessions.** There are 174, from 20 August to 30 September, with 42,315
requests. Each splits at its WP commits into items, 1,487 in all, roughly one
checklist entry each.

- A session makes a median of 212 requests (p10 75, p90 404). Its context
  peaks at a median 374K.
- The first request grew from 60K (the first ten sessions) to 78K (the last
  ten). Every later request and every agent pays that base again.
- The median item takes 15 requests (p90 65) and adds 18K tokens (p90 92K).
  It starts at 272K. Most of a session's requests run late, at a large
  context.

**The bill** is $3,604. Cache reads are 66%, cache writes and input 19%, and
output 16%. If each request had carried only its session's first context,
reads would have been 25% of what they were. The other 75% is accumulation.

**What fills the context.** `Read` results are 60%. Tool inputs the model
wrote, mostly edits, are 17%. `cat`/`sed`/`awk`/`head` are 11%, grep 5%, diffs
and logs 2%, and test output about 1%. Reading is three-quarters of what a
session carries.

**An agent's start.** An Opus 5.5 agent's first request is 65K (median of 26).
None of it is read from the cache, so consecutive agents share no cached
prefix.

**The replay.** Each item is kept in the main session or sent to a lane.

- A kept item pays its measured growth on top of the main context, as the
  replay has left it.
- A lane starts from 64K, plus the WP file (6.3K), plus the files it edits
  that an earlier item read and it did not, plus *u*. Those carried files come
  to a median of 0 and a p90 of 1K, because an item mostly reads what it
  edits. *u* is the code an earlier item read only to understand the problem,
  which a lane must read again. No transcript shows it, so the table spans
  0-40K.
- A lane makes 3 orientation requests. The main session pays 5 requests at
  its own context to dispatch and check it, then carries 8K of report and
  diff.

With nothing laned, the replay reproduces every request's context.

| policy | items laned | *u* = 0 | *u* = 20K | *u* = 40K |
|---|---|---|---|---|
| lane every item | 1,487 | −20% | −8% | +4% |
| lane when main > 200K | 1,034 | −16% | −9% | −2% |
| lane when main > 150K and item ≥ 20 requests | 403 | −28% | −23% | −19% |
| same, 10 main requests and 20K left per lane | 403 | −21% | −17% | −12% |
| same, one lane in five redone | 403 | −22% | −17% | −11% |

The percentages are of the modelled reads and writes, $2,819. At *u* = 20K
the selective policy saves $650, 18% of the whole bill. Laning every item
turns on *u*, and at 40K it costs more than it saves. The selective policy
holds under every variation tried.

The saving sits in the long sessions. Under the selective policy at *u* =
20K, sessions peaking under 300K save 1%. Those peaking at 300-450K save 17%,
and those above 450K save 31%.

**The crossover.** A lane saves the main context minus its own base, on each
of its requests. Its fixed cost is its base written at the 5-minute rate,
three orientation requests, the main session's five requests, the 8K carried
afterwards and one dispatch prompt. So the item length at which a lane breaks
even falls as the main context grows:

| lane base | main 150K | 200K | 250K | 300K | 400K | 500K |
|---|---|---|---|---|---|---|
| 80K | 50 requests | 31 | 24 | 19 | 15 | 13 |
| 110K | 109 | 51 | 35 | 27 | 19 | 16 |

A laned item also stops adding its growth to the main session, which lowers
these lengths a little for the requests still to come. Sonnet lanes would add
little. Sonnet's cache reads cost the same $0.20, so only writes and output
get cheaper.

**The trial.** The replay assumed three numbers: *u*, the main session's
requests per lane, and what a lane leaves in the main context. It also assumed
that a session can tell a long item before starting it, and that a lane's
work holds up. `/wp-lanes` ran the selective policy in a real WP session, and
`session_usage.py lanes` measures all five. One row per session that ran
lanes, the ten trial sessions first:

| date | session | lanes | kept | re-read (*u*) | main requests per lane | left in main | actual / estimated requests | lanes fixed / redone | saved | of the session |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-01 | ec2ca17f | 2 | 4 | 5K | 6 | 11K | 1.22 | 0 / 0 | +2.77 | +21% |
| 2026-10-02 | 46f97a56 | 5 | 2 | 15K | 8 | 14K | 2.27 | 2 / 0 | +16.73 | +39% |
| 2026-10-02 | c77ba4ec | 1 | 5 | 0K | 11 | 39K | 0.62 | 0 / 0 | +5.17 | +24% |
| 2026-10-03 | 6dc4faa1 | 1 | 2 | 4K | 10 | 18K | 1.67 | 1 / 0 | +1.32 | +12% |
| 2026-10-03 | e6ef1126 | 6 | 3 | 0K | 7 | 15K | 0.83 | 3 / 2 | +17.77 | +31% |
| 2026-10-03 | 0433c291 | 5 | 1 | 0K | 10 | 16K | 1.91 | 2 / 0 | +38.56 | +41% |
| 2026-10-03 | 38257a74 | 1 | 1 | 74K | 27 | 72K | 2.18 | 1 / 0 | +5.17 | +18% |
| 2026-10-04 | d1d1ba33 | 2 | 1 | 3K | 11 | 27K | 1.60 | 2 / 0 | +3.23 | +19% |
| 2026-10-06 | 23ba0bb7 | 1 | 0 | 0K | 5 | 9K | 0.64 | 0 / 0 | +0.10 | +1% |
| 2026-10-07 | f69c397c | 2 | 2 | 0K | 6 | 17K | 1.10 | 1 / 0 | +0.78 | +8% |
| 2026-10-09 | b4bfff73 | 2 | 0 | 0K | 6 | 9K | 1.45 | 0 / 0 | +2.28 | +9% |
| 2026-10-09 | 1df3e4b8 | 3 | 1 | 7K | 17 | 55K | 2.18 | 3 / 0 | +4.83 | +14% |
| 2026-10-10 | 1d554b12 | 1 | 1 | 0K | 2 | 5K | 2.69 | 1 / 0 | +8.61 | +25% |
| 2026-10-10 | c9c0a10d | 3 | 0 | 16K | 5 | 11K | 2.49 | 2 / 0 | +8.38 | +30% |

Session 38257a74 (WP-1523) resumed its one lane by `SendMessage` with a
revised design after the first report. The tool counts that as no redo, and the
lane's 182 requests span both rounds.

Session f69c397c (WP-1907) is entered as kept 2 and fixed 1 where the tool
printed 0 and 0. It kept two items under written `lanes: keep` lines, and it
fixed the second lane's workflow (a model input) by a Python rewrite. The tool
did not count that edit.

**The decision: adopted** (2026-10-08,
[WP-1903](../wp/1903-the-lane-trial-decides.md)). The rule is now `/wp-start`
step 6c, with its thresholds unchanged: lane an item once the main context is
over 150K and the item's estimate is 20 requests or more. `/wp-lanes` is
deleted. `/wp-handover` step 3b and `session_usage.py` stay, so every session
that lanes still adds a row above.

The trial cleared the bar WP-1903 proposed. That bar asked for a saving of at
least 10% from the re-run's selective row, at most one lane in five redone,
and review findings on lane code no worse than usual. Nobody confirmed the bar
before the decision, and the quality leg has no measured baseline for
"usual".

- *Rows.* Ten sessions sent 26 items to lanes. Every session came out ahead,
  by a median 20% and $91.60 in total. Two lanes were redone, both in
  e6ef1126.
- *Re-measured.* Seven of the first nine sessions were measured again with the
  script at `2d6e632a`. The two cloud sessions, c77ba4ec and d1d1ba33, kept
  no transcript. Each of the seven came out larger than its row. 46f97a56 and
  23ba0bb7 were measured on 2026-10-07 and the other five on 2026-10-08.
  Those five matched their rows in every column but the saving and its
  share. The script changed after the rows were written, so the rows stay as
  committed. The tenth, f69c397c, landed after the re-measure was planned and
  was not re-measured. The re-measured figures, as saved $ and share of the
  session: ec2ca17f +3.58 (+23%), 46f97a56 +23.08,
  6dc4faa1 +1.88 (+13%), e6ef1126 +21.77 (+34%), 0433c291 +46.34 (+44%),
  38257a74 +7.42 (+22%), 23ba0bb7 +0.41.
- *Re-run.* The trial's medians were *u* 3K, 10 main requests a lane and 16K
  left in main. On 2026-10-08 the replay over one machine's 195 WP sessions
  (2026-08-20 to 2026-10-04) put the selective rule at −20%, −17% and −12% for
  *u* = 3K, 20K and 40K. At *u* = 20K it gave −8% with *mo* doubled and 20K
  left in main, and −11% with one lane in five redone. The other machine's 46
  sessions gave −18%, −15% and −12% on 2026-10-07. The measured inputs move
  the crossover up: at an 80K lane base, an item at 150K now breaks even at
  65 requests, against the table's 50.
- *Threshold.* The saving is flat across nearby thresholds. On the 195
  sessions, at *u* = 20K:

  | policy, on the item's actual requests | items laned | saving | *mo* doubled, 20K left |
  |---|---|---|---|
  | main > 150K, item ≥ 20 | 424 | −16.6% | −8.3% |
  | main > 150K, item ≥ 30 | 276 | −17.5% | −12.0% |
  | main > 150K, item ≥ 40 | 175 | −15.9% | −12.4% |
  | main > 200K, item ≥ 20 | 359 | −15.2% | −7.3% |
  | main > 100K, item ≥ 20 | — | −18.2% | −9.6% |
  | item ≥ its crossover length | 246 | −17.7% | −12.4% |

  The replay reads an item's actual length. A session reads its estimate,
  and the trial's estimates ran short by a median 1.6×. An estimate of 20 is
  therefore an item of about 30, which is the row that holds up best. The
  rule keeps its 20.
- *Quality.* The handover reviews found two correctness bugs in lane code. In
  WP-1534 a phase released mid-stage skipped the new probe, on a second entry
  path the prompt had not named. In WP-1527 the TOPAS writer dropped a
  magnetic site's ion. A WP-1510 lane died on the 600 s stream watchdog during
  a long test run, under a memory rule a lane cannot see. Step 6c's prompt
  now names every code path the change reaches, restates the memory rules
  that bear on the item with the command-length one always among them, and
  asks for a decision line on every item.

Two things stay unmeasured. The *fixed / redone* column closes at the lane's
commit, so a fix the handover review lands later is not in it. It also sees
only the Edit-family tools, so a fix written through Bash reads 0 (f69c397c's
note above). And the review
findings are the only evidence on whether lane code is as good as the main
session's.
