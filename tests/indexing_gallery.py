"""The pictures every indexing acceptance row leaves, and the page that indexes them.

``tests/CLAUDE.md`` carries a standing rule — *every test refinement also writes
obs/calc/diff PNGs to ``tests/output/`` for visual inspection; Rwp hides
locally-bad fits* — and until WP-1041 the whole indexing suite was its one
exception: ``grep -n "savefig" tests/test_acceptance_indexing.py`` returned
nothing, on 38 rows, several of which exist entirely to make a claim about lines
on a real pattern.  This module closes it.

Two things live here because they are one thing.  :func:`draw` writes a dataset's
gallery, and beside the PNGs it writes a small JSON **sidecar** recording what the
run actually did.  :func:`summary_html` then reads the sidecars back and renders
the one-page benchmark summary — dataset, provenance, what is asserted, what
happened, and the picture — so the summary is *generated from the measurement*
rather than maintained beside it.  A hand-written summary of a suite this size
goes stale between sessions; this one cannot say anything the run did not.

**One sidecar per dataset, never one shared file.**  The acceptance rows are
spread over five ``xdist_group``s and therefore over up to five workers, so an
appended manifest would interleave.  One writer per file has no such failure, and
the assembler is a glob.

**Why the Le Bail panel costs a second fit.**  ``index_pattern`` validates each
candidate and keeps the verdict, not the curve (``validate_by_lebail``'s docstring
has the reason: a ``LeBailValidation`` is a few hundred bytes and a
``RefinementResult`` carries y_obs/y_calc over every channel).  So a picture of
the fit means asking for one, which is exactly what ``with_result=True`` exists
for.  Measured on corundum, the refit reproduces the stored verdict *exactly* —
Rwp 0.2822 against 0.2822, 12 predicted-but-absent against 12 — which is the
property that matters: the picture cannot disagree with the number printed beside
it.  The whole gallery cost 10.2 s against that row's search, and the search is
where the time is.

Run ``python -m tests.indexing_gallery`` after an acceptance run to build the page.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

OUTPUT = pathlib.Path(__file__).parent / "output"
#: Sidecars are named so one glob finds them and nothing else in ``output/``
#: matches — that directory holds ~120 files from the refinement suites.
SIDECAR_GLOB = "indexing_*.gallery.json"

#: **What each specimen physically is.**  Declared once per specimen rather than
#: once per run, because a dataset that is indexed twice under two protocols is
#: still one mineral with one space group — and the first version of this page
#: gave it two headings and stated its identity in neither.
#:
#: ``space_group`` is the *answer* — what the phase actually is — and is shown
#: beside every result, because "trigonal R" is a lattice and R-3c is a
#: structure, and the gap between them is where half this package's caveats come
#: from (a space-group extinction refutes a correct *lattice*).
#:
#: ``tier`` says how far the reference may be trusted: ``certificate`` (a
#: certified cell), ``cross-code`` (another program's converged answer),
#: ``consistency`` (a literature cell for the mineral, not for this specimen),
#: ``published`` (a printed benchmark), ``none`` (no known cell — the claim is
#: the abstention).
SPECIMENS: dict[str, dict[str, str]] = {
    "lab6": {
        "title": "LaB\u2086 — NIST SRM 660c",
        "space_group": "P m -3 m (cubic, primitive)",
        "cell": "a = 4.156780 \u00c5 at this block's 20.85 \u00b0C",
        "tier": "certificate",
        "provenance": "NIST certification data, nist_srm660c_100a.cif "
                      "(_meas block); lab Cu K\u03b1 doublet + graphite analyzer.",
        "why": "The absolute lab anchor, and the one bundled phase whose space "
               "group has <b>no extinctions at all</b> \u2014 which makes it the "
               "control that proved a space-group absence can refute a correct "
               "cell everywhere else.",
    },
    "corundum": {
        "title": "Corundum (Al\u2082O\u2083) — NIST SRM 676a",
        "space_group": "R -3 c (trigonal, rhombohedral centring)",
        "cell": "a = 4.759355, c = 12.99231 \u00c5",
        "tier": "certificate",
        "provenance": "IUCr CPD QPA round robin, qarr/corundum.prn; Cu K\u03b1 "
                      "doublet, graphite diffracted-beam monochromator.",
        "why": "The row the indexing milestone was blocked on, twice. Its c-glide "
               "is why a <i>correct</i> cell here is refuted by "
               "<code>predicted_but_absent</code>: the lattice R knows nothing "
               "about a glide plane, so 12 reflections it allows are absent.",
    },
    "nac": {
        "title": "NAC (Na\u2082Ca\u2083Al\u2082F\u2081\u2084) — APS 11-BM",
        "space_group": "I 2\u2081 3 (cubic, body-centred)",
        "cell": "a = 10.2510 \u00c5",
        "tier": "certificate",
        "provenance": "APS 11-BM synchrotron, 11BM_NAC.fxye, \u03bb = 0.4139090 "
                      "\u00c5 from the .prm. Carries a CaF\u2082 impurity.",
        "why": "Short wavelength, 285 lines, and a second phase. The exhaustive "
               "engine cannot start here at all \u2014 at d_min = 0.43 \u00c5 a "
               "10.25 \u00c5 cell exceeds the reflection ceiling \u2014 so the "
               "other two carry it.",
    },
    "fap": {
        "title": "Fluorapatite (Ca\u2085(PO\u2084)\u2083F)",
        "space_group": "P 6\u2083/m (hexagonal, primitive)",
        "cell": "a = 9.3717, c = 6.8859 \u00c5 (GSAS's converged answer)",
        "tier": "cross-code",
        "provenance": "GSAS-II LabData tutorial, FAP.XRA; the reference is GSAS's "
                      "own fit in FAP.EXP \u2014 another program's result, not a "
                      "certificate.",
        "why": "The case the whole design exists for. The right cell was "
               "<i>reachable and ranked fourth</i> for the whole of the indexing "
               "work — three cells ~1000 ppm out score a higher M₂₀ "
               "on fewer lines — and it leads since WP-1046 without the panel "
               "being touched: those three are one engine's, this one is every "
               "engine's, and corroboration ranks first. The refusal is what did "
               "not move; the gate still promotes nothing here.",
    },
    "zincite": {
        "title": "Zincite (ZnO)",
        "space_group": "P 6\u2083 m c (hexagonal, primitive)",
        "cell": "a = 3.2499, c = 5.2066 \u00c5 (Kihara & Donnay)",
        "tier": "consistency",
        "provenance": "IUCr CPD QPA round robin, qarr/zincite.prn.",
        "why": "The cleanest recovery here \u2014 all 27 usable lines indexed, "
               "both engines agreeing. Its 6\u2083 screw and c-glide still refute "
               "it, which is the extinction blind spot on a third space group.",
    },
    "zircon": {
        "title": "Zircon (ZrSiO\u2084)",
        "space_group": "I 4\u2081/a m d (tetragonal, body-centred)",
        "cell": "a = 6.6042, c = 5.9796 \u00c5 (Hazen & Finger)",
        "tier": "consistency",
        "provenance": "IUCr CPD QPA round robin, qarr/zircon.prn.",
        "why": "The only row whose answer is a <b>centring</b>. Its primitive twin "
               "indexes <i>more</i> observed lines (60 against 59) and is wrong; "
               "only coverage scored in reverse separates them.",
    },
    "brucite": {
        "title": "Brucite (Mg(OH)\u2082)",
        "space_group": "P -3 m 1 (trigonal, primitive)",
        "cell": "a = 3.142, c = 4.766 \u00c5 (Zigan & Rothbauer)",
        "tier": "consistency",
        "provenance": "IUCr CPD QPA round robin, qarr/brucite.prn.",
        "why": "The specimen that proved a literature cell is not a specimen's "
               "cell: its <i>a</i> sits +1750 ppm from the published value, 30\u00d7 "
               "the instrument floor. Also the c\u00d72 and c\u00d73 supercell case.",
    },
    "magnetite": {
        "title": "Magnetite (Fe\u2083O\u2084)",
        "space_group": "F d -3 m (cubic, face-centred)",
        "cell": "a = 8.3941 \u00c5",
        "tier": "consistency",
        "provenance": "IUCr CPD QPA round robin, qarr/magnetit.prn.",
        "why": "Ranked right and <b>graded backwards</b>: the correct F cell is "
               "refuted by its own d-glide while its wrong primitive rival escapes "
               "clean. The sharpest illustration of the extinction blind spot.",
    },
    "fluorite": {
        "title": "Fluorite (CaF\u2082)",
        "space_group": "F m -3 m (cubic, face-centred)",
        "cell": "a = 5.4631 \u00c5",
        "tier": "consistency",
        "provenance": "IUCr CPD QPA round robin, qarr/fluorite.prn.",
        "why": "High symmetry makes a pattern easy to index right up until it "
               "makes the pattern too sparse to index at all: 18 usable lines "
               "against a floor of 20, so nothing runs.",
    },
    "cpd1a": {
        "title": "A three-phase mixture",
        "space_group": "\u2014 (corundum + zincite + fluorite)",
        "cell": "no single lattice explains it",
        "tier": "none",
        "provenance": "IUCr CPD QPA round robin, qarr/cpd-1a.prn.",
        "why": "The failure mode the prior art retracted a claim over: a coverage "
               "score cannot tell a multiphase pattern from a single-phase one of "
               "lower symmetry, so a naive indexer produces a confident list here.",
    },
    "hl2": {
        "title": "An unidentified pattern",
        "space_group": "unknown \u2014 and it stays unknown",
        "cell": "unknown",
        "tier": "none",
        "provenance": "hl2_peaks.txt \u2014 a bare position list for a phase with "
                      "no known cell. Cu K\u03b1.",
        "why": "12 candidates, M\u2082\u2080 \u2248 4.6, nothing promoted \u2014 "
               "and the verdict is identical at 15, 25 and 45 s of budget, so the "
               "silence is not a budget artefact.",
    },
    "bethanechol": {
        "title": "Bethanechol chloride — the published benchmark",
        "space_group": "P 2\u2081/n (monoclinic, primitive)",
        "cell": "a = 8.875, b = 16.408, c = 7.137 \u00c5, \u03b2 = 93.84\u00b0",
        "tier": "published",
        "provenance": "Bergmann, Le Bail, Shirley & Zlokazov (2004), Z. "
                      "Kristallogr. 219, 783 \u2014 ten peak sets at six levels of "
                      "difficulty, with eleven programs' scores printed.",
        "why": "The only externally graded benchmark any feature in this package "
               "has \u2014 and the one place we <b>decline to report a score</b>. "
               "Eleven indexing programs were run on one compound at six levels "
               "of difficulty, and both the data and every program's score were "
               "printed, so the bar is what ITO13, DICVOL91, TREOR90 and McMaille "
               "actually achieved rather than a tolerance somebody chose. What we "
               "check against it is below; <b>what we cannot</b> is that score, "
               "and the reason is a measurement, not an omission \u2014 see the "
               "note under the figure.",
    },
}

#: One entry per *run*. ``specimen`` keys into :data:`SPECIMENS` for the identity;
#: ``step`` says what this particular run did to it, which is what distinguishes
#: three runs on one mineral.
DATASETS: dict[str, dict[str, str]] = {
    "lab6_peaks": {
        "specimen": "lab6", "step": "The picked line list, before any search",
        "asserts": "the unflagged tail components escape the picker for three "
                   "different reasons, and sit on the axial-divergence side.",
    },
    "lab6": {
        "specimen": "lab6", "step": "Indexed as picked, nothing declared",
        "asserts": "the certified cubic cell is recovered with no extinction "
                   "caveat \u2014 and, since WP-1041, not uniquely: both centrings "
                   "of its a\u00b7\u221a2 supercell are found by every engine.",
    },
    "lab6_calibrated": {
        "specimen": "lab6",
        "step": "Indexed with every piece of evidence supplied",
        "asserts": "what the gate does once the off-lattice lines are removed and "
                   "the shift is measured and declared \u2014 i.e. the ceiling, not "
                   "what an unaided search reaches.",
    },
    "corundum_peaks": {
        "specimen": "corundum", "step": "The picked line list, before any search",
        "asserts": "the phantom components that blocked this dataset are flagged: "
                   "each sits ~0.17\u20130.24\u00b0 below a line 4\u00d7 stronger.",
    },
    "corundum": {
        "specimen": "corundum", "step": "Indexed with nothing declared",
        "asserts": "the certified lattice ranked first with the right centring, "
                   "both axes inside 150 ppm, graded low on three caveats that "
                   "each name something real.",
    },
    "corundum_shift": {
        "specimen": "corundum",
        "step": "Indexed with the cos\u2009\u03b8 shift template declared",
        "asserts": "declaring the <i>shape</i> of the systematic moves the cell "
                   "toward the certificate (a: +122 \u2192 \u221293 ppm).",
    },
    "nac": {
        "specimen": "nac", "step": "Indexed over the whole range",
        "asserts": "the cubic I cell is found at +19 ppm by two engines; the third "
                   "enumerates nothing, so the gate refuses to promote.",
    },
    "fap": {
        "specimen": "fap", "step": "Indexed over hexagonal and trigonal",
        "asserts": "the cross-code cell leads, inside 500 ppm, because every "
                   "engine found it \u2014 and the gate still declines it.",
    },
    "zincite": {
        "specimen": "zincite", "step": "Indexed over hexagonal and trigonal",
        "asserts": "the hexagonal lattice recovered at the level a lab d-scale "
                   "supports \u2014 lattice type and centring, never a ppm figure.",
    },
    "zircon": {
        "specimen": "zircon", "step": "Indexed over tetragonal",
        "asserts": "tetragonal <b>I</b>, not the P description of the same axes.",
    },
    "brucite": {
        "specimen": "brucite", "step": "Indexed over trigonal and hexagonal",
        "asserts": "the truth found with its c\u00d72 and c\u00d73 supercells, "
                   "which the reversed member separates; an a\u00d72 supercell "
                   "still ranks <b>first</b> (WP-1449).",
    },
    "magnetite": {
        "specimen": "magnetite", "step": "Indexed over cubic",
        "asserts": "the cubic F truth ranked first, and the gate grading it "
                   "<i>below</i> its own primitive rival.",
    },
    "fluorite": {
        "specimen": "fluorite",
        "step": "Searched on fewer lines than M₂₀ needs",
        "asserts": "fewer usable lines than PEAK_MIN_USABLE_LINES = 20, searched "
                   "anyway; the certified cell ranks first, unscored and capped "
                   "at medium.",
    },
    "cpd1a": {
        "specimen": "cpd1a", "step": "Indexed as a single phase (it is not one)",
        "asserts": "best_or_none() is None and no candidate reaches high.",
    },
    "hl2": {
        "specimen": "hl2", "step": "Indexed from a bare position list",
        "asserts": "12 candidates, nothing promoted, and the abstention is stable "
                   "across three budgets.",
    },
    "bethanechol": {
        "specimen": "bethanechol",
        "step": "The ten published peak sets, checked against the published cell",
        "asserts": "three things the paper states and never tabulates, so a "
                   "transcription error in the 200 typed numbers would break at "
                   "least one: the zeroshift arithmetic (C = A \u2212 0.100\u00b0), "
                   "the I \u2265 5 % intensity subsetting, and the paper's own "
                   "count of unexplained lines per set. Then its published "
                   "figures of merit, M(20) = 197 and F(20) = 1080, reproduce.",
    },
}



#: ``stem -> (conventional cell, centring, relative band)`` for the datasets whose
#: lattice is known.  This is what turns the gallery into the **scoreboard**: with
#: a truth declared, ``truth_rank`` records where in the ranking that lattice
#: landed, so "five put the right lattice first" is generated from the run rather
#: than retyped into three documents.  A dataset with no entry has no known cell,
#: and its rows claim an abstention rather than an answer (cpd-1a, hl2).
#:
#: **The band is each dataset's own acceptance band, and it has to be.**  The
#: obvious implementation — ``same_lattice`` alone — is wrong here, and wrong in
#: the direction that matters: without a covariance that function falls back to
#: ``CELL_EQUALITY_RELATIVE`` = 5e-3, *deliberately* an order looser than a
#: synchrotron cell so it never tightens a dedup comparison.  On FAP, whose whole
#: row is that the cross-code cell (+258 ppm, 178 of 185 lines) sits **below** one
#: 966 ppm out, 5e-3 calls both of them the truth and the scoreboard reports
#: "ranked first" for a dataset whose acceptance row asserts the opposite.  So the
#: band is quoted from the row: 150 ppm for corundum, 200 for LaB6, 500 for FAP
#: (``FAP_INDEXING_PPM``), 3e-3 for the round-robin minerals whose reference is a
#: literature cell rather than a certificate.
TRUTHS: dict[str, tuple[tuple[float, ...], str, float]] = {
    "corundum": ((4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0), "R", 1.5e-4),
    "corundum_shift": ((4.759355, 4.759355, 12.99231, 90.0, 90.0, 120.0),
                       "R", 1.5e-4),
    "lab6": ((4.156780,) * 3 + (90.0, 90.0, 90.0), "P", 2.0e-4),
    "lab6_calibrated": ((4.156780,) * 3 + (90.0, 90.0, 90.0), "P", 2.0e-4),
    "zincite": ((3.2499, 3.2499, 5.2066, 90.0, 90.0, 120.0), "P", 1.0e-3),
    "zircon": ((6.6042, 6.6042, 5.9796, 90.0, 90.0, 90.0), "I", 3.0e-3),
    "nac": ((10.2510,) * 3 + (90.0, 90.0, 90.0), "I", 2.0e-4),
    "fap": ((9.3717, 9.3717, 6.8859, 90.0, 90.0, 120.0), "P", 5.0e-4),
    "brucite": ((3.142, 3.142, 4.766, 90.0, 90.0, 120.0), "P", 3.0e-3),
    "magnetite": ((8.3941,) * 3 + (90.0, 90.0, 90.0), "F", 1.0e-3),
    "fluorite": ((5.4631,) * 3 + (90.0, 90.0, 90.0), "F", 1.0e-3),
}
#: Absolute tolerance (degrees) on the conventional cell's angles.  They are
#: symmetry-fixed on every dataset here, so this only has to reject a different
#: *setting* of the same lattice, which is a whole crystal system away.
TRUTH_ANGLE_DEG = 0.5


def truth_rank(stem: str, ranking: list[dict[str, Any]]) -> int | None:
    """1-based rank of the declared truth in a stored ``ranking``, or ``None``.

    **Two conditions, both necessary: the centring, and the dataset's own band on
    the Niggli-reduced cell.**  Reducing is what makes a *setting* change equality
    rather than a miss — the half of ``reduce.same_lattice`` worth keeping — and
    :data:`TRUTHS` has why the band is not redundant with it, with the FAP
    measurement that says so.

    **The centring is the other half, and leaving it out is the mistake this
    package has now made at three ranks**: a primitive description of a centred
    lattice reduces to the same metric with a different content, and calling that
    a match reads a wrong answer as right.  Measured: without the centring clause
    both NAC candidates scored as the truth, and only one of them is
    (``engines.solution_key`` carries the same lesson one rank down, WP-1040's
    monoclinic row a rank up).

    It reads the **stored** ranking rather than live candidates on purpose.  The
    A..F vectors are seven numbers a candidate already has, so keeping them costs
    nothing, and it means declaring a truth for a dataset later re-scores the
    scoreboard from sidecars already on disk instead of needing a 23-minute
    acceptance run — which is exactly the loop this was first written without.
    """
    if stem not in TRUTHS:
        return None
    cell, centring, rtol = TRUTHS[stem]
    return rank_of_lattice(ranking, cell, centring, rtol)


def rank_of_lattice(ranking: list[dict[str, Any]], cell: tuple[float, ...],
                    centring: str, rtol: float) -> int | None:
    """The three-condition comparison itself, for a truth declared inline.

    Split out of :func:`truth_rank` for the bethanechol benchmark
    (``tests/bethanechol_benchmark.py``), whose truth is one published cell read
    from the fixture rather than a :data:`TRUTHS` row — **so that there is one
    implementation of "is this candidate that lattice" and not two.**  Two is how
    this package has been wrong at three ranks already (the centring clause, the
    5e-3 fallback, sorted axes); a second scorer written beside this one would be
    free to drop a condition silently.

    **The band is measured on the reduced cell, and that is not a detail.**  It
    was applied to the *conventional* one until WP-1026's reopen, where the
    bethanechol benchmark caught it: the published monoclinic cell comes back as
    its ``c + a`` setting — (7.135, 16.409, 11.753, β 131.11°) for a published
    (8.875, 16.408, 7.137, β 93.84°), the same lattice and the same volume to
    0.1 Å³ — so an axis-by-axis conventional comparison called a **correct answer
    ranked first** a miss, and would have scored the benchmark −1 where the paper
    scores +1.  A monoclinic conventional setting is not unique (three
    unique-axis choices, and β free to any ``c + na``); a reduced one is.  The
    high-symmetry datasets in :data:`TRUTHS` cannot see the difference — their
    conventional setting *is* unique, which is why this survived nine of them.

    **And ``same_lattice`` itself is no longer stacked on top of the band**,
    because its fixed 5e-3 is a *componentwise relative* bound on reduced A..F,
    and on the off-diagonals that is an angle test whose tightness is set by how
    far the reduced angle sits from 90°: F ∝ cos γ\\*, so the relative error in F
    is roughly Δγ/(90° − γ), an amplification of 1/3.84° here and unbounded as a
    lattice approaches orthogonality.  Measured on bethanechol set E, whose
    answer is 1274 ppm out on lengths and 0.016° on the reduced angle — plainly
    the same lattice, and what the paper scores +1 — every diagonal component
    sits at ≤ 0.0026 and **F alone reaches 0.0063**, so ``same_lattice`` refuses
    it.  A benchmark that must accept a cell biased by an uncorrected zeropoint
    (measured below, and in ``tests/bethanechol_benchmark.py``) cannot be gated
    on a constant tuned so it never tightens a *dedup* χ².  Reduce, then apply
    the declared band: one bound, visible, per dataset.
    """
    import numpy as np

    from rietx.indexing.qspace import af_from_cell, cell_from_af
    from rietx.indexing.reduce import reduced_af

    want = cell_from_af(reduced_af(af_from_cell(cell)))
    for i, row in enumerate(ranking):
        if row.get("centring") != centring:
            continue
        af_got = np.asarray(row["af"], dtype=float)
        if not _cell_within(cell_from_af(reduced_af(af_got)), want, rtol):
            continue
        return i + 1
    return None


def _cell_within(got, want, rtol: float) -> bool:
    lengths = all(abs(g / w - 1.0) <= rtol for g, w in zip(got[:3], want[:3]))
    angles = all(abs(g - w) <= TRUTH_ANGLE_DEG
                 for g, w in zip(got[3:], want[3:]))
    return lengths and angles


def _close(fig) -> None:
    import matplotlib.pyplot as plt
    plt.close(fig)


def draw(stem: str, *, peaks, data=None, result=None, instrument=None,
         spec=None, n: int = 5, validate: bool = True,
         note: str = "") -> dict[str, Any]:
    """Write one dataset's gallery and its sidecar; return the sidecar.

    ``peaks`` is the only required input, because it is the only thing every row
    has: a peak list is what the search was *given*, and every real-data indexing
    failure this package has measured was visible there first.  ``result`` adds
    the ranked-candidate tick rows, and ``data`` + ``instrument`` add the Le Bail
    obs/calc/diff panel for the top candidate.

    **The pictures are :func:`rietx.viz.plot_indexing`'s since WP-1043** —
    this module is a consumer of that call, not the owner of the composition —
    and the matching window is therefore reconstructed from the result's own
    provenance notes.  ``spec`` is accepted for the callers that pass it and no
    longer read: the notes are written from the spec that actually ran, so the
    reconstruction cannot disagree with it.

    Never raises on a missing picture — a search that abstained has no candidates
    to rank and no fit to draw, and that is the row's *point* rather than a
    failure.  It does raise on an **undeclared stem**, which is the one thing a
    silent skip would hide: a dataset in the suite and not in the summary.
    """
    if stem not in DATASETS:
        raise KeyError(
            f"{stem!r} has no entry in indexing_gallery.DATASETS — a dataset "
            "reaching the gallery must say what it is and what is asserted "
            "about it, or the summary page silently omits it")

    from rietx.viz.indexing import plot_indexing, plot_peak_list

    OUTPUT.mkdir(exist_ok=True)
    figures: list[str] = []
    card: dict[str, Any] = {"stem": stem, **DATASETS[stem], "note": note,
                            "figures": figures}

    if result is None:
        name = f"indexing_{stem}_peaks.png"
        _close(plot_peak_list(peaks, data, path=str(OUTPUT / name)))
        figures.append(name)
    usable = peaks.usable()
    card["n_usable"] = len(usable)
    card["n_picked"] = len(peaks.peaks)
    card["wavelength"] = round(float(peaks.wavelength), 6)
    card["two_theta_range"] = [round(float(peaks.two_theta_min), 3),
                               round(float(peaks.two_theta_max), 3)]

    if result is None:
        _write(stem, card)
        return card

    cands = list(getattr(result, "candidates", ()) or ())
    card["n_candidates"] = len(cands)
    card["systems_searched"] = list(getattr(result, "systems_searched", ()) or ())
    card["validated"] = bool(getattr(result, "validated", False))
    best_or_none = result.best_or_none() if hasattr(result, "best_or_none") else None
    card["promoted"] = best_or_none is not None
    card["diagnostics"] = sorted({d.code for d in getattr(result, "diagnostics", ())})
    # each unit's own clock, which is what says whether a budget stopped it:
    # ``INDEX_SEARCH_INCOMPLETE`` also fires where a cap did (WP-1449)
    card["unit_seconds"] = {
        key.removesuffix(".seconds"): value
        for key, value in sorted(getattr(result, "engine_stats", {}).items())
        if key.endswith(".seconds")}

    # the whole ranking, compactly — seven numbers and two strings per candidate,
    # which is what lets the scoreboard be re-scored without re-running a search
    card["ranking"] = [{
        "system": c.system, "centring": c.centring,
        "af": [float(v) for v in c.af],
        "cell": [round(float(v), 5) for v in c.cell],
        "volume": round(float(c.volume), 2),
        "n_indexed": int(c.n_indexed), "confidence": c.confidence,
    } for c in cands]

    # the pictures are plot_indexing's (WP-1043).  The refit pair is computed
    # here first, because the sidecar records its numbers and checks them
    # against the verdict index_pattern stored; the drawing then reuses the
    # same fit rather than running a second one.
    pair = None
    if cands and validate and data is not None and instrument is not None:
        from rietx.indexing.workflow import validate_by_lebail

        pair = validate_by_lebail(cands[0], data, instrument, peaks=peaks,
                                  with_result=True)
    figs = plot_indexing(result, peaks, data=data, n=n, validation=pair)
    for key, fig in figs.items():
        name = f"indexing_{stem}_{key}.png"
        fig.savefig(OUTPUT / name)
        _close(fig)
        figures.append(name)

    if not cands:
        card["outcome"] = "abstained — no candidate"
        _write(stem, card)
        return card

    best = cands[0]
    card["ranked_first"] = {
        "system": best.system, "centring": best.centring,
        "cell": [round(float(v), 5) for v in best.cell],
        "volume": round(float(best.volume), 2),
        "n_indexed": int(best.n_indexed), "n_lines": int(best.n_lines),
        "found_by": list(best.found_by),
        "confidence": best.confidence,
        "caveats": list(best.confidence_caveats),
        "fom": {f.name: round(float(f.value), 4) for f in best.fom},
    }
    card["outcome"] = (
        f"{best.system} {best.centring}, {best.n_indexed}/{best.n_lines} lines, "
        f"confidence {best.confidence}"
        + (" — promoted" if best_or_none is not None else " — not promoted"))

    if best.lebail is not None:
        card["lebail"] = {
            "rwp": round(float(best.lebail.rwp), 4),
            "gof": round(float(best.lebail.gof), 3),
            "space_group": best.lebail.space_group,
            "n_reflections": int(best.lebail.n_reflections),
            "predicted_but_absent": int(best.lebail.predicted_but_absent),
            "unmatched_observed": int(best.lebail.unmatched_observed),
            "status": best.lebail.status,
        }

    if pair is not None:
        # the refit is compared against the verdict ``index_pattern`` already
        # stored.  They agree exactly when nothing is stochastic between them,
        # and a disagreement is worth knowing about rather than worth drawing
        # over — recorded in the sidecar, never asserted by a picture writer.
        validation, _vresult = pair
        card["validation_refit"] = {
            "rwp": round(float(validation.rwp), 4),
            "predicted_but_absent": int(validation.predicted_but_absent),
            "unmatched_observed": int(validation.unmatched_observed),
        }
        if best.lebail is not None:
            card["validation_refit"]["reproduces_stored"] = bool(
                validation.predicted_but_absent
                == best.lebail.predicted_but_absent
                and abs(validation.rwp - best.lebail.rwp) < 1e-9)

    _write(stem, card)
    return card


#: The scoreboard's vocabulary, and it is deliberately **four** buckets rather
#: than the three the pre-WP-1041 wording used.  "Right" and "wrong" cannot
#: absorb the case this package produces most: the true lattice is *in the list*
#: and something else leads it, which is neither a success nor a failure and is
#: what FAP and NAC both do.  Collapsing it either way is how a scoreboard gets
#: rounded up.
VERDICTS = {
    "first": "the true lattice is ranked first",
    "present": "the true lattice is found but not ranked first",
    "absent": "the true lattice is not among the candidates",
    "refused": "no engine ran — the quality gate refused the list",
    "unknown": "no cell is known for this dataset; the claim is the abstention",
}


def _verdict(card: dict[str, Any]) -> str:
    if not card.get("has_truth"):
        return "unknown"
    if not card.get("n_candidates"):
        return "refused" if not card.get("systems_searched") else "absent"
    rank = card.get("truth_rank")
    if rank == 1:
        return "first"
    return "present" if rank else "absent"


def _write(stem: str, card: dict[str, Any]) -> None:
    (OUTPUT / f"indexing_{stem}.gallery.json").write_text(
        json.dumps(card, indent=2), encoding="utf-8")


def add_figure(stem: str, filename: str) -> None:
    """Append a figure to a card :func:`draw` already wrote.

    For the pictures a *row* has and the dataset does not — a deviation plot for
    the row about tail components, say.  Silently does nothing when the card is
    absent, because that is a selection running one row without its fixture's
    sibling, not an error.
    """
    path = OUTPUT / f"indexing_{stem}.gallery.json"
    if not path.exists():
        return
    card = json.loads(path.read_text(encoding="utf-8"))
    if filename not in card.setdefault("figures", []):
        card["figures"].append(filename)
    _write(stem, card)


def draw_deviation(stem: str, name: str, two_theta, deviation, *,
                   split_deg: float | None = None, title: str = "",
                   marked=None, marked_label: str = "") -> str:
    """Signed distance from each picked line to its nearest reference position.

    The picture the LaB6 tail-component rows need and the three generic
    renderers cannot give them: those components are **unflagged**, so
    :func:`~rietx.viz.indexing.plot_peak_list` draws them exactly like the real
    lines — which is the finding, not a shortcoming.  What separates them is
    *where they sit*, and the sign is the measurement (the real lines carry the
    specimen displacement one way; the survivors sit on the other side of their
    own line below the axial-divergence crossover).
    """
    import matplotlib.pyplot as plt
    import numpy as np

    OUTPUT.mkdir(exist_ok=True)
    tt = np.asarray(two_theta, dtype=np.float64)
    dev = np.asarray(deviation, dtype=np.float64)
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=150)
    ax.axhline(0.0, lw=0.8, color="#999999", zorder=1)
    if split_deg is not None:
        ax.axvline(split_deg, lw=0.8, ls="--", color="#7a7a7a", zorder=1,
                   label=f"{split_deg:g}°")
    keep = np.ones(len(tt), dtype=bool) if marked is None else ~np.asarray(marked)
    ax.plot(tt[keep], dev[keep], "o", ms=4.5, color="#1f5fa8", zorder=3,
            label=f"on the reference lattice ({int(keep.sum())})")
    if marked is not None and (~keep).any():
        ax.plot(tt[~keep], dev[~keep], "D", ms=5.5, color="#c23b22", zorder=4,
                label=marked_label or f"off-lattice ({int((~keep).sum())})")
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_ylabel(r"signed $\Delta 2\theta$ to nearest reference line (deg)")
    ax.set_title(title or name, fontsize=10)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    fname = f"indexing_{stem}_{name}.png"
    fig.savefig(OUTPUT / fname)
    _close(fig)
    add_figure(stem, fname)
    return fname


def draw_benchmark_sets(stem: str, sets: dict, predicted: dict, *,
                        note: str = "") -> dict[str, Any]:
    """The ten published peak sets, stacked, against the cell the paper solved.

    One figure rather than ten, because the benchmark's whole shape is the
    *comparison* between its levels of difficulty — the synchrotron set where
    every line is explained, against the ICDD entries carrying a zeroshift and
    impurity lines.  Ten separate stem plots would hide exactly that.

    ``predicted`` maps a set name to the 2θ its published cell allows over that
    set's range; a line further than ``EXPLAINED_DEG`` from all of them is drawn
    as an impurity, which is the paper's own count reproduced as a picture.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    OUTPUT.mkdir(exist_ok=True)
    names = list(sets)
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(names) + 1.6), dpi=150)
    n_impurity = {}
    for row, name in enumerate(names):
        tt = np.asarray(sets[name], dtype=np.float64)
        pred = np.asarray(predicted[name], dtype=np.float64)
        gap = np.min(np.abs(tt[:, None] - pred[None, :]), axis=1)
        bad = gap > 0.08          # tests.test_acceptance_indexing.EXPLAINED_DEG
        n_impurity[name] = int(bad.sum())
        y = -float(row)
        ax.vlines(tt[~bad], y - 0.30, y + 0.30, lw=1.1, color="#1f5fa8",
                  zorder=3)
        if bad.any():
            ax.vlines(tt[bad], y - 0.34, y + 0.34, lw=1.6, color="#c23b22",
                      zorder=4)
        # labels in fixed gutters (axes coordinates), not beside each set's own
        # first line: the sets span different ranges — E and F are synchrotron —
        # so a data-relative label lands inside another set's lines
        ax.text(-0.012, y, name, fontsize=8, ha="right", va="center",
                color="#4a4a4a", transform=ax.get_yaxis_transform())
        ax.text(1.012, y, f"{int(bad.sum())} unexplained", fontsize=7.5,
                ha="left", va="center", color="#7a7a7a",
                transform=ax.get_yaxis_transform())
    ax.plot([], [], color="#1f5fa8", lw=1.1, label="explained by the published cell")
    ax.plot([], [], color="#c23b22", lw=1.6, label="unexplained (impurity)")
    ax.set_yticks([])
    ax.set_ylim(-len(names) + 0.4, 0.9)
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_title("Bergmann et al. (2004) bethanechol chloride: ten peak sets "
                 "against the published monoclinic cell", fontsize=10)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    fig.tight_layout()
    fname = f"indexing_{stem}_sets.png"
    fig.savefig(OUTPUT / fname)
    _close(fig)

    card: dict[str, Any] = {
        "stem": stem, **DATASETS[stem], "note": note, "figures": [fname],
        "two_theta_range": [
            round(min(float(np.min(v)) for v in sets.values()), 3),
            round(max(float(np.max(v)) for v in sets.values()), 3)],
        "n_lines_total": sum(len(v) for v in sets.values()),
        "n_sets": len(names),
        "unexplained_per_set": n_impurity,
        "outcome": (f"{len(names)} sets, 20 lines each; "
                    f"{sum(n_impurity.values())} lines in total are not "
                    f"explained by the published cell"),
    }
    _write(stem, card)
    return card


# ----------------------------------------------------------------------
# the one-page summary
# ----------------------------------------------------------------------
#: The order datasets appear on the page.  Certified anchors first, then the
#: consistency-tier minerals, then the rows whose claim is an abstention, then
#: the published benchmark — which is the order of how much a reader may
#: conclude from each, not the order the suite happens to run them in.
PAGE_ORDER = ("lab6_peaks", "lab6", "lab6_calibrated", "corundum_peaks",
              "corundum", "corundum_shift", "nac",
              "fap", "zincite", "zircon", "brucite", "magnetite",
              "cpd1a", "fluorite", "hl2", "bethanechol")

#: Specimen order on the page — by how much may be concluded from each, which is
#: not the order the suite runs them in.
SPECIMEN_ORDER = ("lab6", "corundum", "nac", "fap", "zincite", "zircon",
                  "brucite", "magnetite", "cpd1a", "fluorite", "hl2",
                  "bethanechol")

#: The scoreboard's datasets, one row each — the **known-cell** ones plus
#: fluorite, whose whole result is that it is refused before any engine starts.
#: ``corundum_shift`` and ``lab6_calibrated`` are deliberately absent: they are
#: the *second step* of a two-step protocol on a dataset already counted, and
#: counting a dataset twice is how the pre-WP-1041 scoreboard came to name nine
#: datasets under a total of eight.
SCOREBOARD_STEMS = ("lab6", "corundum", "nac", "fap", "zincite", "zircon",
                    "brucite", "magnetite", "fluorite")


def scoreboard(cards: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The known-cell scoreboard, counted from the sidecars.

    The pre-WP-1041 wording was "five right, one refused, two fail" over "eight
    known-cell datasets", and it had two defects this replaces rather than
    reproduces.  **Its arithmetic did not close**: 5 + 1 + 2 = 8 while *nine*
    datasets are named across the buckets, because NAC was described inside the
    failure bucket without being counted, and FAP was counted as putting the
    right lattice first by a sentence that says in the same breath it is second.
    And **two of its rows were prose**: brucite and magnetite were measured
    before WP-1030's prunes landed and were never test rows, so the scoreboard
    quoted numbers no run reproduced.

    Both are structural, so the fix is structural: the buckets are
    :data:`VERDICTS`, computed per dataset from ``truth_rank``, and this
    function is the only place that counts them.
    """
    cards = load_cards() if cards is None else cards
    by_stem = {c["stem"]: c for c in cards}
    rows, counts = [], dict.fromkeys(VERDICTS, 0)
    for stem in SCOREBOARD_STEMS:
        card = by_stem.get(stem)
        if card is None:
            continue
        verdict = card.get("verdict", "unknown")
        counts[verdict] += 1
        rows.append({
            "stem": stem, "verdict": verdict,
            "truth_rank": card.get("truth_rank"),
            "n_candidates": card.get("n_candidates", 0),
            "promoted": bool(card.get("promoted")),
            "outcome": card.get("outcome", ""),
        })
    return {"rows": rows, "counts": counts, "n": len(rows),
            "n_promoted": sum(r["promoted"] for r in rows),
            "missing": [s for s in SCOREBOARD_STEMS if s not in by_stem]}


def load_cards() -> list[dict[str, Any]]:
    """Every sidecar the last run left, in :data:`PAGE_ORDER`, re-scored.

    ``truth_rank`` and ``verdict`` are computed **here**, not stored, so a truth
    added to :data:`TRUTHS` takes effect on the sidecars already on disk.
    """
    cards = {}
    for path in sorted(OUTPUT.glob(SIDECAR_GLOB)):
        card = json.loads(path.read_text(encoding="utf-8"))
        # **The declaration is re-read from the live tables, never trusted from
        # the sidecar.**  ``draw`` copies DATASETS into the card at write time,
        # so a sidecar holds a *snapshot* of what the page said when the suite
        # last ran — and editing a title or regrouping the page would then take
        # effect only after a 23-minute acceptance run.  The measurement is the
        # sidecar's; the prose is always the module's.
        card.update(DATASETS.get(card["stem"], {}))
        card["has_truth"] = card["stem"] in TRUTHS
        card["truth_rank"] = truth_rank(card["stem"], card.get("ranking", []))
        card["verdict"] = _verdict(card)
        cards[card["stem"]] = card
    ordered = [cards[s] for s in PAGE_ORDER if s in cards]
    ordered += [c for s, c in sorted(cards.items()) if s not in PAGE_ORDER]
    return ordered


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


#: What `index_pattern` actually does, in the order it does it — the section a
#: reader needs *before* any result means anything, and the one this page did not
#: have when it was first written.  Each step names the module that owns it so the
#: page is an entry point into the code rather than a substitute for it.
PIPELINE = (
    ("1. Pick the peaks",
     "<code>indexing/pick.py</code>",
     "A search never sees the pattern — it sees a <b>peak list</b>, which has "
     "already thrown most of the measurement away. Every real-data indexing "
     "failure this package has measured was visible here first, which is why the "
     "first figure of every dataset below is the picked list and why lines the "
     "picker distrusts are drawn faint. <b>This is the figure to check for "
     "autopicking mistakes.</b>"),
    ("2. Refuse lists that cannot support an answer",
     "<code>indexing/quality.py</code>",
     "M₂₀ and Smith's volume envelope are <i>defined</i> on twenty lines, and "
     "F_N is scored on the same twenty here, so below that the package would "
     "be reporting figures of merit outside the list they are about. Fluorite "
     "abstains here, before any engine starts, on 18 usable lines."),
    ("3. Measure the 2θ shift, before searching",
     "<code>indexing/pairs.py</code>",
     "Harmonic reflection pairs — planes that are integer multiples — give one "
     "equation in the shift and none in the cell, so the <i>magnitude</i> of a "
     "systematic is knowable from the peak list alone, with no reference. This "
     "sizes the matching window. It is a correctness parameter: a fitted σ is "
     "the right weight and the <b>wrong</b> window, and on corundum the lines "
     "sit a median 0.060° from the true positions against a fitted σ of 0.0056° "
     "— an 11σ systematic, at which the true cell indexes zero lines."),
    ("4. Search, with three engines that fail differently",
     "<code>indexing/dichotomy.py</code>, <code>trial_error.py</code>, "
     "<code>svd.py</code>",
     "Confidence comes from engines <i>agreeing</i>, so they have to be capable "
     "of disagreeing: a wide domain defeats the exhaustive dichotomy, a bad base "
     "line poisons the exact-solve trial-and-error, and a bad starting basin "
     "defeats the stochastic SVD method. Adding an engine therefore <i>raises</i> "
     "the bar rather than diluting it."),
    ("5. Merge, and rank on a panel of seven",
     "<code>indexing/consensus.py</code>, <code>fom.py</code>",
     "Candidates are merged on the reduced cell (a lattice, not a tuple), and "
     "ranked by Borda count over <b>seven</b> figures of merit — M₂₀, F_N, three "
     "coverage fractions, and Oishi-Tomiyasu's M<sup>Rev</sup>/M<sup>Sym</sup>. "
     "Coverage is scored in <b>both directions</b> because a supercell indexes "
     "every observed line exactly and only loses on the reversed members: it "
     "predicts a forest that is not there. In the tick-row figures below, that is "
     "the row which is mostly faint."),
    ("6. Validate against the whole profile (Le Bail)",
     "<code>indexing/workflow.py</code> — <code>validate_by_lebail</code>",
     "The panel sees ≤ 20 lines and <b>cannot see reflections predicted where "
     "there is no intensity</b>, so every surviving candidate is fitted to the "
     "full pattern. This is a <b>Le Bail</b> extraction, not Pawley, and "
     "single-phase by construction — two phases were measured at Rwp "
     "742-9281 % against 7.5-24.8 % for one, because the intensity partition has "
     "nothing to arbitrate two phases claiming the same channel. It reports two "
     "detectors: <span class='sw' style='background:#f2c14e'></span> predicted "
     "but absent, and <span class='sw' style='background:#7a1fa8'></span> "
     "observed but unmatched. They catch opposite failures — an oversized cell "
     "and a wrong metric — and Rwp separates neither reliably."),
    ("7. Grade, and usually refuse",
     "<code>indexing/consensus.py</code> — <code>grade</code>",
     "The governing rule is that an indexer must <b>never hand back one cell "
     "confidently</b>. <code>IndexingResult</code> has no <code>.cell</code>: "
     "only a gated <code>best_or_none()</code>, which returns <code>None</code> "
     "unless the answer is <code>high</code> — and <code>high</code> requires "
     "<i>zero</i> caveats and <i>every</i> engine that ran finding the lattice. "
     "That is why the scoreboard below shows six correct answers and zero "
     "promotions: <b>never wrong, and silent more often than right</b> — on a "
     "corpus of high-symmetry lattices (see the scoreboard's qualifier)."),
)


#: Every term this page uses that is not standard crystallography.  It exists
#: because the first version used *promoted*, *first/present*, *truth rank*,
#: *flagged*, *Borda* and *caveat* without defining any of them — all six are
#: this package's own vocabulary, and a reader who has not read the source has no
#: way to recover them.
GLOSSARY = (
    ("Flagged (a peak)",
     "The peak fitter's own verdict on a line it found. Nine flags exist; the "
     "ones that <b>remove</b> a line from the search are <code>ghost_kbeta</code> "
     "and <code>ghost_tungsten</code> (contamination — flagged and excluded, "
     "never subtracted, because Rachinger stripping redistributes the noise), "
     "<code>fit_failed</code>, <code>excluded</code> (you removed it), and "
     "<code>not_separable</code> (the component improves the group's <i>shape</i> "
     "but is not believable as a <i>line</i>). Flags that stay in the search: "
     "<code>unresolved_shoulder</code>, <code>sigma_assumed</code>, "
     "<code>position_at_bound</code> and <code>asymmetry_unmodelled</code> — "
     "these lines are weaker evidence, and their σ says so. In the picked-peak "
     "figures, faint ticks are flagged lines."),
    ("Caveat",
     "A named reservation attached to a candidate cell. Six are "
     "<b>refuting</b> — they say something is wrong with this cell "
     "(<code>predicted_but_absent</code>, <code>indexed_fraction_low</code>, "
     "<code>geometric_ambiguity</code>, <code>fom_panel_disagrees</code>, "
     "<code>volume_unphysical</code>, <code>validation_failed</code>) — and the "
     "rest merely <b>cap</b>, meaning the evidence is incomplete rather than "
     "against you (<code>not_validated</code>, <code>search_incomplete</code>, "
     "<code>shift_allowance_assumed</code>, <code>engines_disagree</code>, "
     "<code>bravais_ambiguous</code>)."),
    ("Confidence: low / medium / high",
     "Four lines of logic, no thresholds. <b>low</b> — fewer than two engines "
     "found this lattice, <i>or</i> any refuting caveat stands. <b>high</b> — "
     "every engine that ran found it and there is <i>nothing</i> to qualify. "
     "<b>medium</b> — everything else. Caveat <i>count</i> deliberately does not "
     "separate medium from low: two capping caveats are the ordinary state of a "
     "peaks-only run, and counting them would make every answer low."),
    ("Promoted",
     "Whether <code>best_or_none()</code> returned a cell. It returns one only "
     "at <b>high</b> confidence — otherwise <code>None</code>. This is the "
     "package's governing rule made structural: <code>IndexingResult</code> has "
     "no <code>.cell</code> attribute at all, so there is no way to read \"the "
     "answer\" without passing the gate. You always get the ranked list; "
     "promotion is the separate claim that the top of it is trustworthy "
     "unattended."),
    ("Truth rank, and first / present / absent / refused",
     "Only meaningful for the datasets whose lattice is known independently. "
     "<b>Truth rank</b> is where the known lattice landed in the ranked list — "
     "1 is the top. The verdicts: <b>first</b> = rank 1; <b>present</b> = found "
     "but something else leads; <b>absent</b> = not in the list at all; "
     "<b>refused</b> = no engine ran, because the quality gate rejected the peak "
     "list. Matching is a <code>same_lattice</code> test on the reduced A..F "
     "vector, <i>and</i> the centring, <i>and</i> that dataset's own accuracy "
     "band."),
    ("Borda count",
     "How the seven figures of merit are combined into one ranking. Each "
     "candidate is <i>ranked</i> within each figure, and the ranks are summed; "
     "ties share an averaged rank. Ranks rather than values because the panel "
     "mixes a dimensionless ratio, an inverse-degrees quantity and three "
     "fractions — summing those directly would weight each member by its own "
     "dynamic range, which was measured and is why a magnitude-aware aggregate "
     "was tried and rejected."),
    ("The seven figures of merit",
     "<b>M₂₀</b> (de Wolff) = Q₂₀ / (2·⟨ΔQ⟩·N_poss) — how tightly the observed "
     "lines sit on predicted ones, penalised by how many lines the cell could "
     "have produced. <b>F_N</b> (Smith &amp; Snyder) = (1/⟨|Δ2θ|⟩)·(N_obs/N_poss) "
     "— the same idea in 2θ. <b>indexed_fraction</b> and "
     "<b>indexed_intensity_fraction</b> — the share of observed lines, and of "
     "observed intensity, the lattice explains. <b>predicted_seen_fraction</b> — "
     "the reverse: the share of the lattice's own predicted lines that are "
     "actually there. <b>M^Rev</b> and <b>M^Sym</b> (Oishi-Tomiyasu 2013) — M₂₀ "
     "run backwards as an unbounded ratio, and its product with M₂₀. The reverse "
     "direction is what catches a supercell, which indexes every observed line "
     "and predicts a forest that is not there."),
    ("Le Bail, not Pawley",
     "Both extract intensities without a structural model. <b>Pawley</b> refines "
     "each reflection's intensity as a least-squares parameter alongside the "
     "cell; <b>Le Bail</b> instead re-partitions the observed intensity among "
     "overlapping reflections each cycle, which needs no extra parameters and "
     "cannot go singular on overlaps — and a candidate cell can predict hundreds "
     "of reflections on a 25-line pattern. That is the whole reason validation "
     "here is <b>Le Bail</b>: it is cheaper and better conditioned. <b>Neither "
     "constrains the intensities</b> — both leave one free per reflection, "
     "answerable to no structure — which is why the evidence is the two detector "
     "counts and not the fit's Rwp. It is also single-phase by construction: two "
     "phases were measured at Rwp 742–9281 % against 7.5–24.8 % for one. The "
     "package does have a Pawley mode — it is just not what validates a "
     "candidate."),
)


def _glossary_html() -> str:
    items = "".join(f"<dt>{_esc(term)}</dt><dd>{body}</dd>"
                    for term, body in GLOSSARY)
    return (f'<section id="glossary"><h2>What the words mean</h2>'
            f'<p class="lede">This page uses several terms that are this '
            f'package\'s own, not standard crystallography.</p>'
            f'<dl class="glossary">{items}</dl></section>')


def _pipeline_html() -> str:
    steps = "".join(
        f'<li><b>{_esc(title)}</b> <span class="mod">{module}</span><br>{body}</li>'
        for title, module, body in PIPELINE)
    return f"""<section id="pipeline"><h2>How indexing works here</h2>
<p class="lede">Seven steps, in order. Each names the module that owns it — this
page is an entry point into the code, not a substitute for it. The three figures
every dataset below carries correspond to steps 1, 5 and 6.</p>
<ol class="pipeline">{steps}</ol>
<p class="lede"><b>Reading the figures.</b> In a tick-row plot a
<i>solid</i> tick is a line the candidate predicts with an observed line under
it, and a <i>faint</i> one is a prediction with nothing there — so "indexes
everything by predicting a forest" is visible without trusting any number. In a
picked-peak plot, faint ticks are lines the picker itself flagged; the lines that
have caused real failures here were usually <i>unflagged</i>, which is why LaB6
also gets a plot of each line's distance from its certified position.</p>
</section>"""


def _img_src(name: str, inline: bool) -> str:
    """The figure's ``src`` — a sibling filename, or the PNG itself.

    ``inline=True`` base64s each PNG into the page so it survives being moved,
    mailed or published; the payload is ~4.7 MB of PNG, i.e. ~6.3 MB encoded.
    Off by default because the local page sits beside its figures and reloading
    them is what makes it cheap to regenerate after every run.
    """
    if not inline:
        return _esc(name)
    path = OUTPUT / name
    if not path.exists():
        return _esc(name)
    import base64
    return ("data:image/png;base64,"
            + base64.b64encode(path.read_bytes()).decode("ascii"))


def summary_html(cards: list[dict[str, Any]] | None = None, *,
                 inline: bool = False) -> str:
    """The one-page benchmark summary, generated from the sidecars.

    HTML rather than markdown because the last column is a *picture*, and a
    summary whose pictures are links is a summary nobody looks at — which is the
    failure mode the whole plotting rule exists to prevent.
    """
    cards = load_cards() if cards is None else cards
    missing = [s for s in PAGE_ORDER
               if s not in {c["stem"] for c in cards}]
    rows = []
    for card in cards:
        figs = "".join(
            f'<figure><img src="{_img_src(f, inline)}" alt="{_esc(f)}">'
            f'<figcaption>{_esc(f)}</figcaption></figure>'
            for f in card.get("figures", ()))
        facts = []
        if "n_usable" in card:
            facts.append(f"<b>{card['n_usable']}</b> usable of "
                         f"{card['n_picked']} picked lines, λ = "
                         f"{card['wavelength']} Å")
        if "n_sets" in card:
            facts.append(f"<b>{card['n_sets']}</b> sets, "
                         f"{card['n_lines_total']} lines; unexplained per set: "
                         + ", ".join(f"{k} {v}" for k, v in
                                     card["unexplained_per_set"].items()))
        facts.append(f"{card['two_theta_range'][0]}–"
                     f"{card['two_theta_range'][1]}° 2θ")
        if "n_candidates" in card:
            facts.append(f"{card['n_candidates']} candidates; "
                         f"searched {', '.join(card['systems_searched']) or '—'}")
        rf = card.get("ranked_first")
        if rf:
            facts.append(
                f"ranked first <b>{rf['system']} {rf['centring']}</b> "
                f"a={rf['cell'][0]:.5f} V={rf['volume']:.1f} Å³, "
                f"{rf['n_indexed']}/{rf['n_lines']} indexed, found by "
                f"{', '.join(rf['found_by']) or '—'}")
            caveats = ", ".join(rf["caveats"]) or "none"
            facts.append(f"confidence <b>{rf['confidence']}</b>; caveats: {caveats}")
        lb = card.get("lebail")
        if lb:
            facts.append(
                f"Le Bail {lb['space_group']}: Rwp={lb['rwp']}, "
                f"{lb['predicted_but_absent']}/{lb['n_reflections']} predicted "
                f"but absent, {lb['unmatched_observed']} unmatched observed")
        refit = card.get("validation_refit")
        if refit and "reproduces_stored" in refit:
            facts.append("the drawn fit reproduces the stored verdict"
                         if refit["reproduces_stored"] else
                         "<b>the drawn fit differs from the stored verdict</b>")
        if card.get("note"):
            facts.append(_esc(card["note"]))
        rows.append((card, (
            f'<div class="run"><h3>{_esc(card.get("step", card["stem"]))}</h3>'
            f'<p class="asserts"><b>Asserted.</b> {card["asserts"]}</p>'
            f'<p class="outcome"><b>Measured.</b> '
            f'{_esc(card.get("outcome", "peak list only — no search here"))}'
            f'</p><ul>' + "".join(f"<li>{f}</li>" for f in facts) + "</ul>"
            f'<div class="figs">{figs}</div></div>')))

    rows = _group_by_specimen(rows)
    warn = (f'<p class="warn">Not in this run: {", ".join(missing)}. '
            f'Run the full acceptance selection to fill the page.</p>'
            if missing else "")
    board = _scoreboard_html(cards)
    return f"""<!doctype html>
<meta charset="utf-8"><title>rietx indexing benchmark gallery</title>
<style>
/* Palette taken from the package's own plot inks (viz/indexing.py), so the page
   and the figures on it are drawn in one language.  Verdict colours are separate
   from the accent and always carry a shape as well, never colour alone. */
:root {{
  --obs: #1f5fa8; --calc: #c23b22; --absent: #f2c14e; --unmatched: #7a1fa8;
  --ground: #fcfcfb; --raised: #ffffff; --ink: #16191d; --ink-2: #414852;
  --ink-3: #6b7480; --rule: #e2e4e8; --rule-2: #eef0f3;
  --ok: #1c6b45; --warn-ink: #8a5a00; --bad: #9c2740;
  --measure: 68ch;
  --serif: ui-serif, Charter, "Bitstream Charter", "Iowan Old Style", Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --ground: #14161a; --raised: #1b1e24; --ink: #e8eaee; --ink-2: #b3bac4;
    --ink-3: #858e9a; --rule: #2b2f37; --rule-2: #23272e;
    --obs: #6ba3e0; --calc: #e8785c; --unmatched: #b678db;
    --ok: #56b686; --warn-ink: #d9a441; --bad: #e0748e;
  }}
}}
:root[data-theme="dark"] {{
  --ground: #14161a; --raised: #1b1e24; --ink: #e8eaee; --ink-2: #b3bac4;
  --ink-3: #858e9a; --rule: #2b2f37; --rule-2: #23272e;
  --obs: #6ba3e0; --calc: #e8785c; --unmatched: #b678db;
  --ok: #56b686; --warn-ink: #d9a441; --bad: #e0748e;
}}
:root[data-theme="light"] {{
  --ground: #fcfcfb; --raised: #ffffff; --ink: #16191d; --ink-2: #414852;
  --ink-3: #6b7480; --rule: #e2e4e8; --rule-2: #eef0f3;
  --obs: #1f5fa8; --calc: #c23b22; --unmatched: #7a1fa8;
  --ok: #1c6b45; --warn-ink: #8a5a00; --bad: #9c2740;
}}
* {{ box-sizing: border-box; }}
body {{ background: var(--ground); color: var(--ink); font-family: var(--sans);
        font-size: 16px; line-height: 1.6; margin: 0; padding: 3rem 1.25rem 6rem; }}
/* one measure for prose; figures and the table break out wider */
body > *, section > *, .run > * {{ max-width: var(--measure);
  margin-inline: auto; }}
h1 {{ font-family: var(--serif); font-size: clamp(1.9rem, 4vw, 2.6rem);
      font-weight: 600; line-height: 1.15; letter-spacing: -.015em;
      text-wrap: balance; margin: 0 0 .4rem; }}
h2 {{ font-family: var(--serif); font-size: 1.35rem; font-weight: 600;
      line-height: 1.25; text-wrap: balance; letter-spacing: -.01em;
      margin: 0 0 .1rem; padding-right: 7rem; }}
section {{ border-top: 1px solid var(--rule); padding-top: 1.6rem;
           margin-top: 2.6rem; position: relative; }}
p {{ margin: .45rem 0; }}
.lede {{ color: var(--ink-2); }}
.prov, .asserts {{ color: var(--ink-2); font-size: .95rem; }}
.outcome {{ color: var(--obs); font-weight: 500; }}
b, strong {{ font-weight: 650; }}
.tier {{ position: absolute; right: max(0px, calc(50% - var(--measure) / 2));
         top: 1.7rem; font-family: var(--mono); font-size: .68rem;
         letter-spacing: .08em; text-transform: uppercase; color: var(--ink-3);
         border: 1px solid var(--rule); border-radius: 999px;
         padding: .15rem .6rem; background: var(--raised); }}
ul {{ margin: .5rem 0 .9rem; padding-left: 1.15rem; color: var(--ink-2);
      font-size: .93rem; }}
li {{ margin-bottom: .2rem; }}
ol.pipeline {{ margin: .8rem auto 1rem; padding-left: 1.4rem; }}
ol.pipeline li {{ margin-bottom: .9rem; color: var(--ink-2); }}
ol.pipeline b {{ color: var(--ink); }}
.mod {{ font-family: var(--mono); font-size: .72rem; color: var(--ink-3); }}
.mod code {{ background: none; padding: 0; font-size: 1em; }}
code {{ font-family: var(--mono); font-size: .86em; background: var(--rule-2);
        padding: .05em .3em; border-radius: 3px; }}
.sw {{ display: inline-block; width: .72em; height: .72em; border-radius: 2px;
       vertical-align: baseline; }}
/* figures break the measure — they are wide and are the point of the page */
.figs {{ max-width: min(1180px, 100%); display: flex; flex-direction: column;
         gap: 1rem; margin: 1.1rem auto 0; }}
figure {{ margin: 0; }}
figcaption {{ font-family: var(--mono); font-size: .7rem; color: var(--ink-3);
              margin-top: .3rem; }}
/* the plots are white-ground documents; keep them so in either theme */
img {{ display: block; width: 100%; height: auto; background: #fff;
       border: 1px solid var(--rule); border-radius: 4px; }}
.warn {{ background: color-mix(in srgb, var(--absent) 16%, var(--ground));
         border-left: 3px solid var(--absent); color: var(--ink);
         padding: .6rem .9rem; border-radius: 0 4px 4px 0; }}
.tablewrap {{ max-width: min(1180px, 100%); margin: 1rem auto 0;
              overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: .88rem;
         font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: .45rem .7rem; vertical-align: top;
          border-bottom: 1px solid var(--rule-2); }}
th {{ font-family: var(--mono); font-size: .68rem; font-weight: 500;
      text-transform: uppercase; letter-spacing: .08em; color: var(--ink-3);
      border-bottom: 1px solid var(--rule); white-space: nowrap; }}
td:first-child {{ font-family: var(--mono); font-size: .84rem; white-space: nowrap; }}
.chip {{ display: inline-block; font-family: var(--mono); font-size: .7rem;
         letter-spacing: .04em; padding: .1rem .5rem; border-radius: 999px;
         border: 1px solid currentColor; white-space: nowrap; }}
.v-first {{ color: var(--ok); }}
.v-present {{ color: var(--warn-ink); }}
.v-absent {{ color: var(--bad); }}
.v-refused, .v-unknown {{ color: var(--ink-3); }}
@media (prefers-reduced-motion: no-preference) {{ html {{ scroll-behavior: smooth; }} }}
h3 {{ font-family: var(--sans); font-size: .95rem; font-weight: 650;
      letter-spacing: .01em; margin: 0 0 .3rem; color: var(--ink); }}
.run {{ margin-top: 1.8rem; padding-left: 1rem;
        border-left: 2px solid var(--rule); }}
.run:first-of-type {{ margin-top: 1.2rem; }}
.why {{ color: var(--ink-2); margin: .7rem 0 0; }}
dl.ident {{ display: grid; grid-template-columns: max-content 1fr;
            gap: .2rem .9rem; margin: .8rem 0 0; font-size: .9rem; }}
dl.ident dt {{ font-family: var(--mono); font-size: .68rem; letter-spacing: .08em;
               text-transform: uppercase; color: var(--ink-3); padding-top: .15rem; }}
dl.ident dd {{ margin: 0; color: var(--ink); }}
dl.glossary {{ margin: 1rem 0 0; }}
dl.glossary dt {{ font-weight: 650; margin-top: 1rem; }}
dl.glossary dd {{ margin: .2rem 0 0; color: var(--ink-2); font-size: .95rem; }}
:focus-visible {{ outline: 2px solid var(--obs); outline-offset: 2px; }}
</style>
<h1>Indexing benchmark gallery</h1>
<p class="lede">Every unit-cell indexing result <code>rietx</code> is held to,
with the picked peaks, the ranked candidate lattices and the Le&nbsp;Bail
validation fit behind each one. Generated from the sidecars
<code>{SIDECAR_GLOB}</code> that <code>tests/test_acceptance_indexing.py</code>
writes, so nothing here is maintained by hand and nothing can say more than the
run did. Datasets are ordered by how much may be concluded from each — certified
cells first, then literature cells for a mineral, then the rows whose whole claim
is an abstention.</p>
{warn}
{_pipeline_html()}
{_glossary_html()}
{board}
{"".join(rows)}
"""


def _group_by_specimen(rendered: list[tuple[dict[str, Any], str]]) -> list[str]:
    """One ``<section>`` per specimen, its runs as ``<h3>`` steps inside it.

    The first version of this page emitted one section per *run*, so LaB6 and
    corundum each got three headings and stated their identity in none of them —
    a reader could not tell that "indexed as picked" and "with the shift template
    declared" were the same mineral, and the space group appeared nowhere.
    """
    by_specimen: dict[str, list[str]] = {}
    for card, html in rendered:
        by_specimen.setdefault(card.get("specimen", card["stem"]), []).append(html)
    order = [s for s in SPECIMEN_ORDER]
    order += [k for k in SPECIMENS if k not in order]
    # anything left over gets its own section rather than vanishing: a run the
    # page cannot place is a run a reader must still see, and the first version
    # of this function dropped four of them in silence
    order += [k for k in by_specimen if k not in order]
    out = []
    for key in order:
        runs = by_specimen.get(key)
        if not runs:
            continue
        spec = SPECIMENS.get(key, {})
        ident = (
            f'<dl class="ident">'
            f'<dt>Space group</dt><dd>{_esc(spec.get("space_group", "—"))}</dd>'
            f'<dt>Reference cell</dt><dd>{_esc(spec.get("cell", "—"))}</dd>'
            f'<dt>Data</dt><dd>{_esc(spec.get("provenance", "—"))}</dd>'
            f'</dl>')
        out.append(
            f'<section><h2>{_esc(spec.get("title", key))}'
            f'<span class="tier">{_esc(spec.get("tier", ""))}</span></h2>'
            f'{ident}'
            f'<p class="why">{spec.get("why", "")}</p>'
            + "".join(runs) + '</section>')
    return out


def _scoreboard_html(cards: list[dict[str, Any]]) -> str:
    board = scoreboard(cards)
    if not board["rows"]:
        return ""
    counted = ", ".join(f"<b>{board['counts'][v]}</b> {v}"
                        for v in VERDICTS if board["counts"][v])
    body = "".join(
        f'<tr><td>{_esc(r["stem"])}</td>'
        f'<td><span class="chip v-{r["verdict"]}">{_esc(r["verdict"])}</span></td>'
        f'<td>{r["truth_rank"] if r["truth_rank"] else "—"} '
        f'of {r["n_candidates"]}</td>'
        f'<td>{"yes" if r["promoted"] else "no"}</td>'
        f'<td>{_esc(r["outcome"])}</td></tr>'
        for r in board["rows"])
    miss = (f'<p class="warn">Not measured in this run: '
            f'{", ".join(board["missing"])}.</p>' if board["missing"] else "")
    return f"""<section id="scoreboard"><h2>The known-cell scoreboard</h2>
<p class="prov">{board['n']} datasets whose lattice is known independently:
{counted}. <b>{board['n_promoted']}</b> of {board['n']} were promoted — a cell
handed back as <em>the answer</em> rather than as a ranked candidate.</p>
{miss}
<div class="tablewrap"><table><thead><tr><th>dataset</th><th>verdict</th>
<th>truth rank</th><th>promoted</th><th>measured</th></tr></thead>
<tbody>{body}</tbody></table></div>
<p class="lede">Read the shape rather than the count: this feature is
<b>never wrong, and silent more often than right</b>. Every verdict here is
computed from the run — the truth's rank is a <code>same_lattice</code> test on
the reduced A..F vector, <em>and</em> the centring, <em>and</em> the dataset's own
accuracy band. Drop any of the three and a wrong answer reads as right.</p>
<p class="warn">One qualifier travels with every claim on this board (WP-1043):
nine of ten known-cell datasets sit at &le; 2 free metric parameters (4 cubic;
0 orthorhombic, 1 monoclinic, 0 triclinic), so "never wrong" is a statement
about <b>high-symmetry lattices</b> — the engines meet low symmetry only
synthetically until the corpus moves, which is post-v1.</p>
</section>"""


def write_summary(path: pathlib.Path | None = None, *,
                  inline: bool = False) -> pathlib.Path:
    out = path or (OUTPUT / ("indexing_gallery_standalone.html" if inline
                             else "indexing_gallery.html"))
    out.parent.mkdir(exist_ok=True)
    out.write_text(summary_html(inline=inline), encoding="utf-8")
    return out


if __name__ == "__main__":       # pragma: no cover - operator entry point
    import sys

    inline = "--inline" in sys.argv
    written = write_summary(inline=inline)
    n = len(load_cards())
    size = written.stat().st_size / 1e6
    print(f"{written}  ({n} of {len(PAGE_ORDER)} datasets, {size:.1f} MB"
          + (", self-contained)" if inline else ")"))
