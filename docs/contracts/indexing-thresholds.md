# Indexing thresholds version history

One note per change to `INDEXING_THRESHOLDS_VERSION` (`rietx.schemas.indexing`), which `capabilities()` reports as
`indexing_thresholds_version`. The rule for when the number moves is the comment
above the constant. `tests/test_capabilities.py` fails when no note names the
constant's current value. These notes name removed things on purpose, so the
code-reference check does not read this directory.

1.0 (WP-1018): first release of the peak-list contract.

1.1 (WP-1038): ``ShiftScreen.source`` gains ``"reflection_pairs"`` and the
screen gains ``allowance_deg`` — a vocabulary member is a contract change even
when every prior value still means what it did.

1.2 (WP-1039): the lines a search is *driven* by are now the strongest
``n_search_lines`` rather than the first N in 2θ order

1.3 (WP-1110 item 14): ``PeakFlag`` gains ``no_intensity`` and
``PEAK_UNUSABLE_FLAGS`` gains it too — a component that refined onto its zero
intensity bound, which nothing could see before the covariance was
equilibrated
(:func:`rietx.indexing.engines.search_line_order`).  No field changed and no
threshold here moved — this is bumped because ``workflow._spec_notes`` records
this string beside the spec as the stamp a run is reproducible from, and two
runs with identical spec notes now answer differently.  A position-only list is
unaffected: with no measured intensities the rule is exactly the old one.

1.4 (WP-1442): ``PeakFlag`` gains ``position_unmeasured`` and
``PEAK_UNUSABLE_FLAGS`` gains it too — a component whose fitted position esd
exceeds :data:`PEAK_POSITION_ESD_MAX_DEG`, i.e. the whole span a 2θ axis can
have.  ``pick_peaks`` answers differently on any pattern carrying one.  The
same WP made the Kβ / W Lα screen ``flag_ghosts`` runs **joint**
(:data:`~rietx.background.diagnostics.GHOST_MIN_PARENTS`), which is the
larger half of the move: 20 flags over the 17 bundled monochromated patterns
became none, so a ``ghost_kbeta`` or ``ghost_tungsten`` flag — and the
``usable()`` list under it — is not comparable across the two versions.

1.5 (WP-1449): the ranking moves a candidate the data refute as a supercell
of another reported candidate directly below that parent, and grades it down
with the new refuting caveat ``supercell_refuted``.  The test is
:func:`rietx.indexing.ambiguity.supercell_chance` at
``SUPERCELL_CHANCE_ALPHA``, and ``CellCandidate.supercell_checks`` records
every pair it asked.  The same search now orders differently wherever such a
pair was reported (brucite's a × 2 supercell, 11-BM NAC's P description of
its I cell).

1.6 (WP-1518): the dedup χ² reads each candidate's covariance in the reduced
frame its A..F difference is taken in (``reduce.reduction``), so which
candidates are one lattice, their ``found_by`` and the order change wherever a
reduction moved the setting.  ``CELL_EQUALITY_CHI2`` did not move.  Two runs
with identical spec notes now answer differently: bethanechol set Db's truth
went from rank 1 to 2 behind a wrong cell two engines had found in two settings.

1.7 (WP-1510): ``PeakFlag`` gains ``duplicate_line`` and
``PEAK_UNUSABLE_FLAGS`` gains it too — a component of one group sitting on
the line a neighbouring group fitted, found where a re-seed pass in the first
window proposed what the second group already owned.  ``pick_peaks`` answers
differently on any pattern carrying one: on the 16 IUCr round-robin lab patterns
4-35 components of 18-116 are flagged where any are (``cpd-4`` offered 113
usable lines and now offers 78), and none of the lab lists keeps two usable
lines within 0.02° of each other. ``INDEX_IMPURITY_LINES`` counted the copies
as lines no candidate explained.  The same WP raised ``INDEX_PRIOR_USED``
from ``info`` to ``warning`` when a prior lies outside the axis box, and
added the opt-in ``formula=`` check, ``INDEX_Z_NOT_INTEGER`` at
``Z_INTEGER_TOLERANCE``, which a run without a formula never meets.  And it
added the mirror of 1.5's re-rank: a candidate whose ``SupercellCheck``
reads ``"supported"`` moves directly above that parent, unless another check
refutes it (``consensus.above_supported_parents``).  ``"supported"`` now
counts only the extras seen on lines the parent's own lattice leaves
unexplained (``SupercellCheck.n_seen_unexplained``), at the same p₀ and α;
an extra seen only beside a parent line leaves the pair ``"undecided"``.  No
``"refuted"`` verdict moved.  Over the 13 acceptance searches one order
changed: SRM 676a's certified cell, found by one engine, rose from eighth to
first above its c/2 subcell (8 of 18 extras seen, all unexplained,
p = 0.0027), in both corundum searches.  Two pseudo-tetragonal LaB6
descriptions went from ``"supported"`` to ``"undecided"`` over the
half-volume rival, their seen extras all on the rival's lines.

Also in 1.7: ``no_intensity`` is raised for a component whose fitted intensity
is under :data:`PEAK_NO_INTENSITY_SIGMA` of its own esd, not only for one at
its zero bound, so ``usable()`` drops 6 of 798 lines across the 16 IUCr
round-robin lab patterns, all with I/σ_I < 1 (``cpd-4`` 78 → 77).

1.8 (WP-1923): a monoclinic candidate's ``cell``, ``cell_esd`` and ``af``
are reported in the conventional setting — b unique, a and c the shortest
translations normal to b, β obtuse — where they were the engine's setting
(β = 81.78° for a lattice whose conventional β is 98.22°, issue #779), and
``CellCandidate.engine_cell``/``.change_of_basis`` record what it was.
Grades, ranks and Le Bail fits are setting-invariant and do not move.  And
``reduce.reduce_cell`` returns the exact image of its input under its own
change of basis, where a near-zero entry inside ε could take the opposite
sign (issue #797), so a dedup χ² can move by that sign's ε.
1.9: the Kα2 alias screen allows one sampling step beyond its
``PEAK_ALIAS_TOL_FWHM_FRAC`` of a FWHM (``indexing.peaks._alias_tolerance``),
so ``pick_peaks(...).usable()`` drops a Kα2 maximum the 1.8 screen kept
wherever a FWHM spans fewer than about 3.3 channels: ``cpd-4`` offers 76
usable lines where 1.8 offered 77, and the corundum list loses one
``no_intensity`` component (2 → 1).  A Cu Kα rock salt at a 0.02° step went
from 7 of 9 lines indexed to all of them.
1.10: ``PeakFlag`` gains ``weak_line`` — a fitted component whose intensity
significance I/σ_I fails the pattern's own false-discovery threshold
(Benjamini–Hochberg at :data:`PEAK_FDR_Q` over the pattern's resolution
elements) — and ``pick_peaks`` reports the expected number of false lines
among those it keeps (``PEAK_EXPECTED_FALSE_LINES``).  The flag is
**reported, not refused**, so ``usable()`` is unchanged; bumped because a
list's flags are part of what this string stamps.  On #728's synthetic
silicon with a steep background it marks 24 of the 26 off-lattice usable
components and no silicon line.  Since #934 (c), inside 1.11's one bump, a
``weak_line`` line no longer drives a search (``PEAK_UNDRIVEN_FLAGS``), so
a list whose driven set, or the low-Q pool it is drawn from, held one can
answer differently; no indexing-acceptance list's did.
1.11: ``PeakFlag`` gains ``unresolved_split`` and ``width_capped`` and
``PEAK_UNUSABLE_FLAGS`` gains both — the component count by resolvability
(#934): comparable components of one group closer than Sparrow's limit for
the group's fitted shape are reported as one line with a widened σ(2θ), and
a component whose width ran into its bound is not a line.
``flag_duplicate_lines`` now reads a merged line's whole extent.  On #728's
flat-topped synthetic silicon, 34 usable components on 11 lines become 18;
over the 16 IUCr round-robin lab patterns 789 usable components become 782
(``cpd-4`` 76 → 75).

Also 1.11 (#935, one bump per release cycle): ``determine_extinction_symbol(restrict=)`` takes declared facts
(:class:`ExtinctionPrior`: Sohncke, centrosymmetric, polar) as a filter on
each class's members; ``ExtinctionCandidate`` gains ``excluded_groups`` and
``laue_classes``, ``ExtinctionScreen`` gains ``prior``, and
``LAUE_CLASS_NOT_SEPARABLE`` fires on every screen whose leading class
spans two Laue classes (a hexagonal ``P 63 - -``: 6/m and 6/mmm).  Without
a declaration no ranking and no ``best_or_none`` moves.

Also in 1.11, one number a release cycle (indexing C4, C6): a search that ends with no lattice two engines agree
on is run again under the inlier rule, so a run that returned no cell, or
single-engine cells, can now return the true one; and a picked list's search
window is its lower-quartile fitted FWHM (capped at the old 0.05 degrees)
where it was the constant, so a high-resolution list now matches within its
own widths.  A run whose first pass finds an agreed lattice, and a lab list
with lines 0.05 degrees or wider, answer as at 1.9.

Also in 1.11 (WP-1969, #933): ``indexed_fraction_low`` reads the share of the
usable lines' *intensity* a cell indexes, where it read their count, so a
cell leaving weak foreign lines unindexed can grade above ``low`` and one
missing a strong line cannot.  On SRM 660c with three or six weak impurity
lines the certified cell goes from ``low`` to ``medium``: a line count under
the bar adds the capping caveat ``indexed_lines_low`` (a vocabulary member
of ``IndexCaveat``, no new field); no other indexing acceptance row changes
grade by the intensity reading.
1.12, C3 (issue #916): the reversed questions are asked at the measured
**resolution** (``indexing.fom.RESOLUTION_FWHM``) by a candidate-independent
line screen (``indexing/screen.py``), never in the search window or of the
candidate's own fit.  ``predicted_seen_fraction`` is the screen's seen
fraction after the candidate's common shift; ``supercell_checks`` asks child
against parent by containment of the indexed observed set with the denser
line set as the child, so cubic I √2·a₀ over cubic F a₀ and a trigonal
description of a cubic truth are now asked and refuted; ``verdict`` gains
a middle band (refuted needs the extras seen no more often than chance,
``n_seen ≤ n_extra·p0``); ``LeBailValidation.predicted_but_absent`` is the
screen's count against the picker's envelope, with the uncancellable and
windowed-uncancellable counts beside it, and the ``predicted_but_absent``
caveat fires on the windowed count and **caps** rather than refutes.

Also 1.12 (#934 (c)): the picker names every bound its group fit ends on:
``PEAK_POSITION_AT_BOUND`` and ``PEAK_NO_INTENSITY`` are new, and the
``where`` entries of those two, ``PEAK_WIDTH_CAPPED`` and
``PEAK_EXPECTED_FALSE_LINES`` carry each line's bound and value.  No flag,
threshold or ``usable()`` moved; it shares C3's 1.12, the release cycle's
one bump, because a list's diagnostics are part of what this string stamps,
as its flags were at 1.10.

Also 1.12 (#939): ``determine_extinction_symbol`` refines the cell by default
(``refine_cell=True``: a cell-free ``profile_only`` Le Bail of the lattice
group, from a seeded background when the instrument's is all zero) and
abstains when its reference fit fails the ``REFERENCE_NET_RWP_MAX`` gate
(``status="unreliable"``, ``EXTINCTION_SCREEN_UNRELIABLE``);
``ExtinctionScreen`` gains ``prefit_rwp`` and ``reference_rwp_net``.
Every pinned class held (synthetic P 2₁/c, FAP, NAC, certified corundum),
with their ΔBIC moved (corundum −3434 → −1301, FAP −16 → −83); the PbSO₄
X-ray histogram at a 0.1-0.2 % cell went from an abstention to ``P c - n``.

Also 1.12 (WP-2033, #935's other half): ``ExtinctionPrior`` gains ``z``,
``density`` and ``formula`` (and ``ordered``), which name the members whose
orbits cannot hold the declared content (removing them only under
``ordered=True``) and the special positions a Z′ below one needs.  Only a screen that declares one of them can answer differently;
with none declared every screen answers as before.

Also 1.12 (WP-2033, #1140's follow-ups): under ``ordered=True`` a fractional
formula count whose atoms per cell are whole (``CaSO4·0.5H2O`` at Z = 2) is
now counted, so the screen removes groups it used to keep; ``z`` with no
formula opens ``EXTINCTION_PRIOR_APPLIED`` with "filters no group" rather
than "removed 0 space group(s)"; the collapsed special-position ``where``
line splits by note kind; an element an ordered count cannot test (atoms per
cell not whole) gets its own ``where`` line.

Also 1.12 (WP-2030): ``INDEX_DATA_INSUFFICIENT`` names an undeclared
instrument first only on a laboratory source, read off the declared source
(``diagnostics.lab_source``), and reads it from the list's own record when
no instrument is passed.  No search, rank or grade moves.  Part 2:
``SearchSpec.from_formula`` sets a ceiling only, for every formula, so a
search declared through it no longer drops the cells below 0.8 of the
formula's volume and can rank a smaller cell it used to exclude.  And
``INDEX_Z_NOT_INTEGER`` (``Z_INTEGER_TOLERANCE`` 0.08) is withdrawn: it fired
on 12 of 16 true inorganic cells, and the number it judged is now recorded
as ``CellCandidate.formula_units``.  No rank or grade moves without a formula.

Also 1.12 (WP-2011): the whole-pattern validation fits by Pawley, so every
candidate's ``lebail.rwp`` and ``unmatched_observed`` move, and a cell that
predicts every reflection of another now reads that cell's Rwp or lower.

Also 1.12 (#939's follow-ups): ``EXTINCTION_SCREEN_UNRELIABLE``'s message
says whether weak data or misfit failed the gate, from
``ExtinctionScreen.perfect_fit_rwp_net``; no threshold or verdict moved.

Also 1.12 (#1230): a containment child whose own lines are seen more often
than its parent's (``SupercellEvidence.child_seen_more``) is never
``refuted``, so a dense low-symmetry truth no longer sits below a wrong cell
that p₀ near the truth's own seen fraction let refute it.

Also 1.12 (#1263): the containment refuter's null is the seen test's own
chance rate (``PatternScreen.p0``), so ``n_seen ≤ n_extra·p0``, both
p-values and ``SupercellCheck.p0`` read the windows the count is taken in.
The assumed shift bound floors only the power check (``p0_power``, #951).

Also 1.12 (WP-2078): a run that still has no lattice two engines agree on
after the inlier retry searches again on the lines at or above
``engines.WEAK_LINE_RETRY_FLOOR`` (5 %) of the strongest, and returns that
search's ranking when it finds agreement (``INDEX_WEAK_LINE_RETRY``).  A run
that found agreement, a declared ``n_unindexed`` and a position-only list
rank exactly as before.

1.12 → 1.13 (WP-2120): ``PeakFlag`` gains ``tail_shoulder`` and
``PEAK_UNUSABLE_FLAGS`` gains it too.  It is a component carrying both
``axial_tail`` and ``position_at_bound``: a weak shoulder on a much stronger
group-mate's axial-tail side, which the fit pushed to its position bound.  On
the 16 IUCr round-robin lab patterns the eight such components leave
``usable()``.  Seven of them are 0.070-0.142 degrees from every lattice line.
Two leave on SRM 1976a and one on #916's flat synthetic silicon (0.095 degrees
off its line); SRM 660c's one was ``weak_line`` and is now out of the
false-discovery screen, which reads usable components only.  A component that
was a ``duplicate_line`` copy can now be ``tail_shoulder`` instead, unusable
either way.  Neither flag alone moves, and no threshold here moved.
