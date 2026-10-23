"""Model-free pattern diagnostics — the structured object an agent (or the
background auto-selection) reasons over before any refinement is attempted.

Everything is computed from the raw pattern alone; nothing here linearises or
assumes a structural model.  Baseline *shape* questions (amorphous hump, air
scatter) are answered from a **rolling low-quantile envelope** rather than an
arPLS baseline: the answers must not depend on a smoothing λ that is itself
being chosen (arPLS stiff enough to be safe under peaks is too stiff to
follow a genuine hump — measured, which is why the envelope is used here).
Wavelength-dependent contamination checks (Kβ ghosts, W Lα from an aging
tube) run only when the primary wavelength is supplied.

One measure here reads the **σ column** rather than the intensities:
:func:`counting_coverage`, which asks whether every channel was observed with
the same statistical weight.  On a multi-detector instrument it is not — fewer
detectors reach the ends of the range — and the σ column is the only place that
shows.  It is the one thing in this module that a Poisson fallback σ cannot
answer at all, so it returns nothing rather than a number.

One measure is about the **range** rather than about the pattern on it, and it
is read before all the others: :func:`signal_cutoffs`, which finds leading or
trailing stretches where the instrument stopped seeing the sample.  Everything
else here is computed over the whole range it is handed, so a dead end corrupts
those answers — measured, and the numbers are in that function's docstring.  It
reads the **intensities**, and it is not :func:`counting_coverage` under another
name: measured on the pattern quoted there, σ²/y holds constant straight
through the collapse, so σ is honest and those channels are not thinly covered,
they are empty.  What σ adds is that same level re-expressed as a precision, and
:class:`SignalCutoff` carries it as a derived number rather than as a second
observation.
"""

from __future__ import annotations

import warnings
from typing import ClassVar

import numpy as np
from pydantic import Field
from scipy.ndimage import median_filter
from scipy.signal import find_peaks, peak_prominences, peak_widths

from ..optimize import lapack
from ..schemas.common import Base
from ..schemas.pattern import POISSON_FLOOR_COUNTS, PatternData, require_two_theta
from .models import chebyshev_design_matrix

#: Kβ1,3 wavelengths (Å) per anode, for contamination checks only — Kβ is never
#: a modelled emission line (see ``schemas.instrument._RADIATIONS``).  Same
#: source and column as the Kα table it is keyed against: the NIST X-ray
#: Transition Energies Database (SRD 128) direct-experimental KM3.  For the 3d
#: metals that column reports the KM2,3 *blend*, which is what a check wants;
#: for Mo and Ag it resolves Kβ1 (KM3) from Kβ3 (KM2, half the weight), and we
#: take Kβ1 rather than blending them 2:1 — the two choices differ by 3.1e-4
#: relative, i.e. Δ2θ = 2·tanθ·Δλ/λ ≤ 0.02° out to 60° 2θ, which is an order
#: inside the 0.15° matching window in :func:`_contamination_flags`.
_KBETA: dict[str, float] = {
    "CrKa": 2.0848810,
    "FeKa": 1.7566040,
    "CoKa": 1.6208260,
    "CuKa": 1.3922340,
    "MoKa": 0.632303,
    "AgKa": 0.4970817,
}

#: W Lα1 (Bearden 1967, Rev. Mod. Phys. 39, 78).  Tungsten reaches the target
#: by subliming off the *filament*, so unlike Kβ this line is a property of the
#: tube's age rather than of the anode material, and is checked for every anode.
_W_LA1 = 1.4763800

#: How close the pattern's wavelength must be to an anode's Kα1 to be treated
#: as that anode.  The closest pair in the table is Fe/Co at 0.147 Å (Mo/Ag is
#: next at 0.150), so the assignment cannot be ambiguous — but it can be
#: *absent*, and that is the case the caller has to handle.
_ANODE_MATCH_TOL = 0.01

#: Floor on the ghost-matching window in ° 2θ.  It is a *floor*, not the whole
#: budget: the predicted ghost position carries error that a fitted σ(2θ) knows
#: nothing about — the Kβ wavelength table (≈3e-4 relative for the blended 3d
#: entries, i.e. Δ2θ = 2·tanθ·Δλ/λ ≈ 0.02° at 60°) and any unmodelled 2θ shift.
#: When per-line σ(2θ) *is* supplied, :data:`GHOST_MATCH_K`·√(σ_g² + σ_p²) may
#: widen the window but never narrows it, so a poorly-determined line is matched
#: loosely and a well-determined one is not matched *more* tightly than the
#: prediction deserves.
GHOST_TOL_DEG = 0.15
#: How many combined σ the observed ghost may sit from its predicted position.
GHOST_MATCH_K = 3.0
#: Largest position esd, in ° 2θ, at which a fitted line still has a position
#: this check can use.  A line past it is neither a parent nor a candidate.
#:
#: It **is** :data:`GHOST_TOL_DEG`, because that floor is the prediction's own
#: error: once a fit knows less about where its line is than the prediction
#: does, "matched loosely" has become "matched to whatever is nearby".  That is
#: not a hypothetical.  Over the 1 108 fitted lines of the 17 monochromated
#: fixtures the position esd is 0.005° at the median and 0.019° at p90, and the
#: far tail is a cliff rather than a tail: past p99 it runs 10¹⁹ to 10⁵²
#: degrees, a singular normal matrix on an unresolved shoulder or a line with no
#: intensity.  On ``FAP.XRA`` two such fits at 64.330° carried 1 961° and
#: 11 390°, matched every parent, and produced 32 of that pattern's 35 raw
#: matches (WP-1442).
#:
#: The bar drops 22 of those 1 108 lines, 2.0 %, and with it caps the matching
#: window at ``GHOST_MATCH_K·√2·GHOST_TOL_DEG`` = 0.636°.  The σ term is at or
#: under the floor for 93.68 % of parent-line pairs anyway, so this costs
#: almost nothing a well-fitted pattern was using.
#:
#: **It is not**
#: :data:`~rietx.schemas.indexing.PEAK_POSITION_ESD_MAX_DEG`, which is 180° and
#: takes a line out of ``PeakList.usable`` altogether.  The two ask different
#: questions and the answers are properly different by three orders of
#: magnitude: that one asks whether the line has a position *at all*, so its
#: scale is the 2θ axis; this one asks whether the line can be matched against
#: **a specific prediction**, so its scale is that prediction's own error,
#: which is what :data:`GHOST_TOL_DEG` is.  A line can be far too vague to
#: confirm a Kβ position and still be a perfectly good lattice line.
GHOST_ESD_MAX_DEG = GHOST_TOL_DEG
#: Ghost/parent intensity-ratio window.
#:
#: The ceiling is the physics.  Hölzer et al. (1997) Table VI gives the
#: corrected Kβ1,3/Kα1,2 integrated-intensity ratio for the 3d anodes to better
#: than 4 %: Cu 0.141, Cr 0.139-0.147, Mn 0.140, Fe 0.143-0.152, Co 0.137,
#: Ni 0.147-0.150.  An *unfiltered* tube therefore sits near 0.15, and every
#: filter and every monochromator only cuts it, so 0.25 clears the largest
#: tabulated value by 1.6× and calls anything above a reflection.  W Lα1 comes
#: off the filament rather than the target and is weaker still, so it shares the
#: ceiling with room to spare.
#:
#: The 0.6 this shipped until WP-1442 admitted four times an unfiltered tube's
#: leak, and the "≤ ~0.2" its docstring quoted had no source.  On the 17
#: monochromated fixtures the ceiling change alone removed nothing, because the
#: joint bar (:data:`GHOST_MIN_PARENTS`) had already silenced them; what it
#: buys is that a *reported* leak_ratio is now one a tube could produce.
#:
#: **The ceiling is a cliff, not a taper**, and that part is measured: a Kβ
#: image injected into ``corundum.prn`` is found with its ratio through 0.24
#: (an injected 0.14 reads back 0.141) and returns **no flag at all** from
#: 0.26 up, which is what a clean pattern returns.  A ratio past the ceiling is
#: a reflection by construction, so that is the rule working; it is written down
#: because the distance from an unfiltered tube's 0.14 to the edge is 1.8× and
#: not obviously generous.
#:
#: **Whether the census path eats into that 1.8× is argued and not measured.**
#: Hölzer's number is Kβ1,3 over the whole Kα1,2 doublet, which is what
#: ``flag_ghosts`` divides by: :mod:`rietx.indexing.peakfit` models the emission
#: set, so one ``ObservedPeak.intensity`` is the reflection's integral over
#: every line.  :func:`diagnose` has no such model and divides by a *net height*
#: at one channel, which above the doublet's resolving angle is Kα1 alone, about
#: two thirds of the pair — so a real leak, which is one line, should read high
#: there.  **This fixture cannot show it**: the injector adds a scaled copy of
#: the whole pattern, Kα2 satellites included, so its ghost is a doublet image
#: and the height ratio comes back faithful by construction.  Demonstrating it
#: needs a leak synthesised from the emission model rather than from the
#: pattern.  Retuning on it is WP-1447's; what a reader must not do is take the
#: 1.6× as the census path's.
#:
#: The floor keeps noise-level coincidences out.  It is also the height floor
#: :func:`diagnose` admits ghost *candidates* at, because a maximum smaller than
#: it cannot pass this test against any parent.
GHOST_RATIO_RANGE = (0.005, 0.25)
#: How many of the strongest lines are searched for ghosts.  A ghost of a weak
#: line is below noise by construction.
GHOST_N_PARENTS = 8

#: How many of those parents must carry a candidate at one common ratio before
#: a contamination is reported at all.
#:
#: A leak is a property of the *beam*: whatever fraction of Kβ reaches the
#: detector reaches it for every reflection, so a real one puts a line at the
#: predicted position of every strong parent, all at the same ratio.  A
#: coincidence puts one line somewhere.  Taking each match on its own could not
#: tell those apart, and did not: on the 17 monochromated fixtures, where
#: neither Kβ nor W Lα can reach the detector, the per-line rule flagged 0.94
#: Kβ per pattern against a control fed 26 made-up wavelengths that flagged
#: 1.01 (WP-1442).
#:
#: The bar is measured rather than chosen, against a control that asks the same
#: question at wavelengths which are not an emission line of anything.  Over
#: **2 656 draws** (16 round-robin patterns × 166 such wavelengths) the count
#: reaches **4** and no more, and **0.000 %** reach 5; the real Kβ reaches 2 on
#: the worst of those patterns.  A Kβ image injected into six of them scores at
#: least 6 at r = 0.10 and at least 5 at r = 0.15, so 5 separates the two
#: populations with a margin of one count on each side.
#:
#: **The control is only fair away from Kα1.** Above ≈0.98·λ(Kα1) the predicted
#: companion lands on top of its own parent and matches the parent's own Kα2
#: partner, which is self-matching rather than coincidence: measured, the
#: control's mean jumps from 0.50 to 3.95 and its maximum from 4 to 8 inside
#: that band alone.  The band is excluded, along with ±0.01 around the real Kβ
#: and W Lα ratios, which sit at 0.904 and 0.958 and are well clear of it.  A
#: first calibration that swept into the band reported a 1.3 % false rate and
#: was wrong (WP-1442's handover has both runs).
#:
#: **The detection floor this buys is r ≈ 0.10**, not lower: over corundum,
#: zincite, cpd-1e, brucite, zircon and magnetite the minimum score at r = 0.05
#: is 2, and magnetite — 22 fitted lines — reaches only 2 there.  An unfiltered
#: tube sits at 0.14 (Hölzer 1997 Table VI), which is the case worth catching.
#: A *residual* leak past a working filter is below the floor and is reported
#: as nothing, which is the honest answer at this evidence.
#:
#: The number is calibrated on Cu Kα laboratory data from one instrument class,
#: because that is what the bundled corpus has an anode for.  A control run per
#: pattern would remove that dependence and costs ~1.4 % of the peak fit it
#: rides on; it is written up in WP-1447 rather than built, the fixed bar
#: having measured at zero false findings here (decided 2026-09-22 with the
#: maintainer).
GHOST_MIN_PARENTS = 5

#: How far two parents' ratios may differ and still be called one leak, as a
#: factor.  The physical ratio is constant; what varies is the fitted intensity
#: of a weak line sitting on a strong one's flank, which is tens of percent.
#:
#: Measured at 1.3, 1.5, 2.0 and 3.0 against the control
#: :data:`GHOST_MIN_PARENTS` describes: the control's maximum is **4 at every
#: one of them**, so widening costs no specificity at all, while an injected
#: leak at r = 0.10 scores 5 at 1.3 and 1.5 against 6 at 2.0 and 3.0.  The
#: tolerance buys detection for nothing.  2.0 is the widest at which "a common
#: ratio" still means something, which is where it stops being a measurement
#: and becomes a judgement (decided 2026-09-22; WP-1442).
GHOST_RATIO_TOL = 2.0

#: The sampling band of McCusker, Von Dreele, Cox, Louër & Scardi (1999) §2:
#: "There should be at least five steps (but generally not more than ten)
#: across the top of each peak (i.e. step size = FWHM/5)".  The two ends are
#: **not** the same kind of statement — below the minimum the integrated
#: intensities were never measured and no refinement can recover them, while
#: above the maximum the experiment merely spent longer than it needed to.  So
#: only the lower one is ever flagged; the upper is here because a reader
#: comparing against the guideline needs both halves of the sentence.
STEPS_PER_FWHM_MIN = 5.0
STEPS_PER_FWHM_MAX = 10.0

#: How far a maximum must rise above its flanking saddles, in σ, before the
#: sampling measurement treats it as a *resolved* peak rather than a bump.
#: Without it the measurement inverts on exactly the patterns it exists to
#: judge: on an undersampled synthetic LaB6 (17 reflections, 3.2 steps per
#: FWHM by construction) plain 5σ detection returns **49** peaks and a median
#: width of 1.38 steps, because Poisson noise on a 10⁵-count peak puts several
#: 5σ maxima across its own jagged top.  A spurious maximum's *prominence*
#: above the saddle beside it is small, which is what separates the two.
#: Measured at 5 and at 20: identical answers on all four grids of the sweep in
#: WP-1071's handover, so the number is a floor and not a tuning.
SAMPLING_PROMINENCE_SIGMA = 5.0

#: The second floor under both sampling bars, as a fraction of the pattern's
#: near-maximum net signal — the 99.9th percentile that
#: :attr:`PatternDiagnostics.signal_to_background` already calls by that name,
#: rather than ``max``, which is one channel and can be a cosmic ray.
#:
#: It is here because a bar in σ alone asks the wrong question of a pattern
#: whose σ is *right* and smaller than √y.  What the peak finder thresholds is
#: not noise: it is the envelope's own tracking error, which is a fraction of
#: the intensity and does not shrink when the counting gets better.  So a file
#: whose σ is 0.289·√y — most constant-wavelength neutron data, monitor
#: normalised and propagated — measures that error at 3.46× its honest
#: significance.  Measured on the 27 pattern fixtures the suite carries, by
#: scaling the declared σ alone and leaving the data untouched: today's
#: selection moves the answer by a median factor of **5.45** and up to 78×
#: across σ ×1.0 → ×0.05, and every fixture lands at 1.5-2.5 steps per FWHM
#: at the D1B ratio, i.e. ``PATTERN_UNDERSAMPLED`` on all of them.  With this
#: floor the median factor is **1.000** (worst 1.037), because the binding bar
#: is no longer in σ.
#:
#: **It is a selection width, not a floor**, and is quoted as one: the value
#: decides how many lines the median covers, so unlike
#: :data:`SAMPLING_PROMINENCE_SIGMA` the answer does move with it — up to 18 %
#: between 0.02 and 0.05 on the fixtures.  What is flat is the thing it is for:
#: σ-scale invariance is exact from 0.015 upwards, so 0.03 carries 2× margin.
#: Chosen with that margin and for leaving the shipped answer alone where σ is
#: honest (median 0.998 of today's over the fixtures, worst 0.678, and **no**
#: fixture crosses :data:`STEPS_PER_FWHM_MIN` in either direction).  The sweep
#: is in WP-1415's handover.
SAMPLING_HEIGHT_FRACTION = 0.03

#: Median-filter width, in ° 2θ, applied to the variance-inflation ratio before
#: any region is cut out of it (:func:`counting_coverage`).  It is what makes the
#: threshold below mean anything: measured on the two BT-1 patterns quoted there,
#: the *per-channel* ratio through the quiet middle of the scan (60-145°) makes
#: single-channel excursions to 2.27 and 2.43 — higher than the genuine steps the
#: measure exists to find — and **every one of them is exactly one channel long**
#: (3 and 4 such channels respectively), while a median over 11 channels leaves
#: nothing above even 1.3 there.  Measured at 11, 21 and 41 channels: the regions
#: come back the same, so the width is a floor and not a tuning.  1.0° is
#: ``int(1.0 / 0.05)`` = 20 channels at those files' 0.05° step — an even width,
#: so ``median_filter`` takes the lower of the two central values, half a channel
#: below centre.  Neither the count nor the off-by-half moves a reported region.
COVERAGE_SMOOTH_DEG = 1.0

#: How many times the plateau's variance-per-count a smoothed channel must carry
#: before it counts as thinly covered.  Set from the gap between the two things
#: it has to separate, on a NIST BT-1 pattern (3.00-166.25° at 0.05°,
#: 3266 points, σ from the file): the smoothed ratio *drifts* over 1.11-1.37
#: through 149-161°, then **steps** to 2.25 in a single channel at 161.30° and
#: holds it to the end of the scan.  1.5 sits between the two with ≈1.4× margin
#: on each side.  Not tuned to taste: neither BT-1 pattern's plateau reaches it
#: anywhere (smoothed maximum 1.3 over 60-145°), and the region that matters —
#: the one past the step — is identical at 1.3, 1.5 and 1.75.
COVERAGE_INFLATION_THRESHOLD = 1.5

#: How far below the interior level a run must sit to be a *collapse* rather
#: than a falling background (:func:`signal_cutoffs`).  Swept 0.15 to 0.40 on
#: the three private constant-wavelength neutron PSD scans quoted there,
#: watching the reported boundary: the **trailing** cliff barely moves (a
#: fraction of a degree over a 2.7× change in the constant) because it is
#: steep, while the **leading** boundary is flat over 0.20-0.30 and then breaks
#: outward by degrees at 0.35 and 0.40, because the leading end is a graded
#: climb that has reached only about a third of the interior level a few
#: degrees in, so a threshold much above 0.30 swallows the climb itself and
#: the walk-back starts from inside live data.  0.25 sits in the middle of the
#: flat stretch, with margin to the break above and to the 0.15 that puts the
#: run's inner edge below the low-angle halo bump.  It is also what keeps the
#: sample-free scan of the set silent at the low end (it fires there at 0.30
#: and above), which is the one file in the set with no low-angle answer to
#: get right.
CUTOFF_FRACTION = 0.25

#: The fraction of the local plateau at which the collapse is declared to have
#: *begun*, which is the 2θ actually reported.  The floor is not the boundary a
#: fit range wants: on the private scans the trailing level is still near the
#: interior level a few tenths of a degree before the cliff, a quarter of it
#: a degree later and a few per cent from about two degrees on, so reporting
#: where it reaches the floor would hand back some two degrees of unfittable
#: transition inside the range.  Swept 0.80 to 0.99 on the two sample scans,
#: it is the gentlest of these constants and the only monotone one: each
#: boundary moves steadily, by tenths of a degree across the sweep, with no
#: break anywhere.  At 0.90 the leading boundary falls within half a degree of
#: the window the data owner's own TOPAS refinements declare.  The trailing
#: boundary falls a little further out.  A caller who wants the boundary
#: further out or further in should pass ``onset_fraction`` rather than
#: expect a different default to be more correct.
CUTOFF_ONSET_FRACTION = 0.90

#: Shortest collapse, in ° 2θ, that is reported at all.  Twice
#: :data:`CUTOFF_SMOOTH_DEG` and for that reason: a run the smoothing cannot
#: resolve is not evidence, so the shortest reportable feature follows the
#: window it was measured through rather than being a second tunable of its
#: own.  A shorter run at an edge is a dip or a gap in the first channels, not
#: an instrument that stopped.
CUTOFF_MIN_DEG = 1.0

#: Rolling-median width, in ° 2θ, that turns the intensities into a *level*.
#: It is there to stop one spike or one dropped channel opening or closing a
#: run, not to remove peaks — the plateau window below is what averages over
#: those.  Measured at 0.3, 0.5, 1.0 and 2.0° on the three private scans: 0.3
#: and 0.5 give identical boundaries at both edges, and 1.0-2.0 move the
#: trailing one by a single channel, so 0.5 is a floor rather than a tuning.
CUTOFF_SMOOTH_DEG = 0.5

#: Width, in ° 2θ, of the window just inside a collapse whose median level is
#: the "local plateau" the onset is measured against.  It has to clear the
#: cliff without being taken over by one strong peak, and both failures were
#: measured on the private scans: at 0.5° the window sits *inside* the
#: collapse, the plateau reads well under half of interior and the reported
#: trailing boundary lands half-way down the cliff; at 3° it reaches back over
#: a peak above the interior level, reads more than 1, and walks out into live
#: data.  Between 1 and 3° the answer moves under 1° for a 3× change, and every
#: one of those lies between the last full-level channel and the floor — the
#: data owner's own TOPAS ``finish_X`` sits just inside all three, so the
#: decision this supports is insensitive even where the number is not.
CUTOFF_PLATEAU_DEG = 2.0

#: The central fraction of the range whose median level is "the interior".  It
#: must exclude both dead ends, and 0.70 clears them with ≈2× margin on the
#: files measured (each dead end is under a tenth of the channels).  A
#: pattern whose dead ends exceed 15 % of the channels drags the
#: interior median down towards them, the threshold with it, and the measure
#: under-reports — silence rather than a false claim, which is the direction to
#: fail in.
CUTOFF_INTERIOR_FRACTION = 0.70

#: How far below the local background level a channel must sit to be a
#: candidate for *dead* rather than quiet (:func:`dead_channels`).  A detector
#: cell that is not seeing anything reads a Poisson sample of nothing — single
#: counts where its neighbours carry thousands — so the gap this straddles is
#: orders of magnitude, not a factor of two.  It is only the first of two
#: tests, and the weaker one: on the bundled fixtures it alone selects 248
#: runs, every one of them a channel that legitimately counted zero, and
#: :data:`DEAD_WEIGHT_RATIO_MIN` is what rejects all 248.  Swept 0.02 to 0.30
#: against a synthetic carrying issue #274's pair: the run is found identically
#: over the whole range, and no fixture survives the second test anywhere in
#: it, so the value is set from the physics — a decade below the background —
#: rather than from a boundary the data show.
DEAD_LEVEL_FRACTION = 0.10

#: How far a run must outvote its neighbours before it is reported — the
#: second test, and the one that means something.  Weights are 1/σ², so the
#: question a dead cell poses is not "is this channel low" but "does this
#: channel outvote the pattern", and the two are answered by different columns.
#: A channel that legitimately counted zero carries *less* weight than a live
#: one, not more.  A dead cell's σ collapsed with its intensity, so it carries
#: more, and the gap between the two is not a close call: measured over the
#: bundled fixtures, all 248 of the level-only candidates land between **0.94
#: and 3.00**, while a synthetic D1B carrying issue #274's own pair — y = 3
#: and 5 at σ = 1.000 and 1.414, beside background at 39 066 and σ = 57.1 —
#: reads **2243**.  100 sits between them with 33× margin below and 22× above,
#: and the answer on both sets is identical anywhere from 3 to 1000, so this
#: one *is* a floor rather than a tuning.
DEAD_WEIGHT_RATIO_MIN = 100.0

#: Width, in ° 2θ, of :func:`background_envelope`'s rolling window: wider than
#: any Bragg FWHM, so the low quantile inside it lands on background channels
#: (v0.2; WP-1018 reused it for peak picking, WP-1028 repaired its edges).
ENVELOPE_WINDOW_DEG = 3.0
#: The percentile of each window :func:`background_envelope` takes: low enough
#: to land under the peaks.  It sits 1.28σ under the mean of pure noise, a bias
#: ``indexing.peaks._debiased_envelope`` removes.
ENVELOPE_QUANTILE = 10.0
#: Chebyshev terms of the smooth envelope fit the air-scatter gain is measured
#: against: a cubic, then the cubic plus a 1/(2θ) column (v0.2's nested test).
AIR_GAIN_CHEBYSHEV_TERMS = 4

#: Width, in ° 2θ, of the median window that turns the background envelope into
#: the *local level* a dead channel is judged against.  It is
#: :func:`background_envelope`'s own window for the reason that function gives
#: for it — wider than any Bragg FWHM — and the median is taken over the
#: envelope rather than over the intensities so a peak cannot be the level its
#: own flanks are compared with.  Three degrees is also comfortably wider than
#: the longest run this function will report (:data:`CUTOFF_MIN_DEG`), which is
#: what stops a dropout from dragging down the level that is meant to expose
#: it: at 0.1° steps that is 10 channels inside a 30-channel median.
DEAD_LEVEL_WINDOW_DEG = ENVELOPE_WINDOW_DEG

#: How many times :func:`dead_channels` re-derives which channels to withhold
#: from its level estimate before taking the mask as settled.  Each pass walks
#: the mask one median-window further into a long dropout, so the cap bounds a
#: dropout this converges on at roughly that many windows; past it the run is
#: declined by the length test anyway, which is the outcome the cap exists to
#: reach *cleanly* rather than to avoid.  Not a tuning: on every fixture and
#: every synthetic measured the mask settles on pass 2 or 3.
_DEAD_REPAIR_PASSES = 6


class ContaminationFlag(Base):
    """One line of a contamination finding that is **joint across parents**.

    A flag is never emitted on its own evidence.  The rule gathers candidates
    for every one of the strongest parents, finds the ratio the most of them
    agree on, and emits nothing at all unless :data:`GHOST_MIN_PARENTS` of them
    do.  Each flag then names one ghost line of that finding, and carries the
    finding's own numbers beside its own: ``leak_ratio`` is the ratio fitted
    across the supporting parents, ``n_parents`` how many supported it, and
    ``n_parents_searched`` how many were in range to be asked.

    So ``intensity_ratio`` is this line's, and ``leak_ratio`` is the
    pattern's.  A reader wanting to know whether the beam carries Kβ reads the
    second.  The three finding-level fields repeat across every flag of one
    finding, which is what lets a caller drop a line without losing the
    evidence for it.
    """

    kind: str                  # "kbeta" | "tungsten_la"
    two_theta: float           # where this ghost sits
    parent_two_theta: float    # the strong Kα parent it is a ghost of
    intensity_ratio: float     # this ghost/parent intensity
    leak_ratio: float          # the ratio fitted across the supporting parents
    n_parents: int             # parents supporting the finding
    n_parents_searched: int    # parents whose ghost position was in range


class SignalCutoff(Base):
    """An end of the pattern where the instrument stopped seeing the sample.

    Not a verdict and not applied anywhere: :func:`signal_cutoffs` reports, and
    the caller decides what the fit range is.  The five numbers are five
    separate questions a caller has to answer before it can decide.

    ``edge`` is which end, and it is not cosmetic — the two ends fail for
    different reasons and carry different arguments (both measured, in
    :func:`signal_cutoffs`).  A ``"high"`` cutoff is the detector's active area
    running out: there is no diffraction information past it at all.  A
    ``"low"`` one is a beamstop or its halo, where there *is* structure — a
    direct-beam shoulder, a shadowed floor, a broad bump at an angle no lattice
    plane could put one — and it is structure that does not belong to the
    specimen.

    ``two_theta`` is the boundary, and it is the **onset** of the collapse
    rather than where the level reaches its floor, because the onset is what a
    fit range should stop at.  It is a channel that is still at level, so a
    caller trimming to it keeps it: ``n_channels`` is exactly what such a trim
    would drop, which is why the count is reported rather than the region's own
    width — the channels a trim drops are the fact, and a width in degrees is
    not.

    ``floor_fraction`` is how dead: the region's median level over the interior
    level.  A **median**, so it summarises rather than resolves, and the two
    ends of the same file are different shapes underneath the same kind of
    number (a few per cent trailing, a genuine floor; several times that
    leading, an average over a shadowed floor below it and a halo bump above
    it).  It is also the number that separates "there is nothing here" from
    "there is less here", which is a judgement this function declines to make
    for the caller.

    ``relative_error_ratio`` is the implied precision penalty — the region's
    median σ/y over the interior's — and it is **derived, not a second
    observation**.  Where σ²/y is constant, as it is on every pattern measured
    here, σ/y = √(σ²/y) / √y, so the ratio is 1/√``floor_fraction`` and nothing
    more: measured on the private scan, the derived ratio and the directly
    measured one agree to within a few per cent at both edges.  It is carried
    because it is the language the person who took the data uses ("the data
    quality steps below the cutoff") and because saying so once here is what
    stops a third measure of the same fact being added later.  ``None`` when σ
    was not measured: under the Poisson fallback the ratio is *identically*
    1/√``floor_fraction``, so reporting it would be reporting the fallback.
    """

    edge: str                       # "low" | "high"
    two_theta: float                # the boundary — the onset of the collapse
    floor_fraction: float           # the region's median level / the interior level
    n_channels: int                 # channels outside the boundary
    relative_error_ratio: float | None = None   # median σ/y there, over interior


class DeadChannelRun(Base):
    """A short run of channels the detector was not seeing the sample through.

    A dead or masked PSD cell, a gap between detector banks, a channel the
    electronics dropped.  Not a verdict and **applied nowhere**: this reports,
    and which channels a run fits is ``project.fitted_mask``'s answer built
    from the caller's ``excluded_regions`` (WP-1033).  What the finding owes a
    caller is the interval to exclude, which is why the two 2θ bounds are the
    first two fields.

    It is :class:`SignalCutoff`'s peer and the two do not overlap by
    construction: a collapse of :data:`CUTOFF_MIN_DEG` or longer is an
    instrument that stopped and belongs to :func:`signal_cutoffs`, and anything
    shorter is this — "a dip or a gap in the first channels", which is what
    that function's own docstring calls the case it declines — **at either
    end of the range or in the interior** (WP-1415): a short dropout is judged
    by its weight-ratio signature, not by where it sits, and that signature is
    what tells it apart from a genuine edge cliff (measured on the public D1B
    file and a private Mythen operando set, with a wide margin either side of
    :data:`DEAD_WEIGHT_RATIO_MIN` — see :func:`dead_channels`).

    ``weight_ratio`` is why a two-channel dropout is worth a diagnostic at all,
    and it is the number to lead with.  Weights are 1/σ², so a channel whose
    intensity collapsed *and* whose σ collapsed with it does not merely
    contribute nothing — it outvotes the pattern.  On the ILL D1B file of issue
    #274 two cells at σ = 1.0 sit beside live channels at σ = 55.1, so each
    carries the weight of about 3 000 live ones, and a 12-term Chebyshev
    background is dragged through zero to reach them: Rwp 0.087 against 0.0074
    with the same channels excluded, the Caglioti terms at their bounds and
    every Biso pinned at zero.  None of the fourteen bound hits is the problem,
    which is the whole reason this is reported where the cause is rather than
    left to be read off the symptoms.  It is **required**, not optional: the
    census answers nothing without a measured σ, so there is no run whose
    ratio is unknown.  An optional one would be a state with no writer.
    """

    two_theta_min: float
    two_theta_max: float
    n_channels: int
    #: the run's median intensity over the local background level
    level_fraction: float
    #: (local σ / the run's σ)² — how many live channels one of these outvotes
    weight_ratio: float


class CoverageRegion(Base):
    """A stretch of pattern whose σ carries more variance per count than the
    bulk of the scan does — fewer independent observations behind each channel.

    Purely **descriptive**, and deliberately so.  If σ is right then weighted
    least squares already gives these channels the weight they deserve, which is
    the whole job σ has; the region is a fact about *the experiment's coverage*,
    not a verdict on the data.  What it tells a caller is that the pattern's
    statistical weight is not uniform across its range — which is about how many
    detectors saw each angle, and about nothing to do with the specimen.

    The four numbers are the four separate questions: where it is, how much
    variance per count it carries relative to the bulk (``inflation``), how wide
    it is (``n_channels`` — a 3-channel region and a 700-channel one are
    different facts about the same ratio; and it is the region's *span*, bridged
    sub-threshold gaps included, not a count of channels each over the
    threshold), and *where in the range* it sits.  ``edge`` is not a hint to do
    anything and it is not a diagnosis of the cause: it says only whether the run
    reached an end of the range or sat inside it.  The causes it does **not**
    separate are several.  An end region can be the detector bank's coverage
    running out (a quantised falloff, detectors being integers) *or* a smooth
    high-angle taper of a synchrotron analyser bank (11-BM rises over its last
    third rather than stepping); an interior one can be a dead or excluded
    detector, two scans stitched together, a variable counting-time or slit
    schedule (a non-monotonic ladder, as SRM 660c shows), or mere
    threshold-crossing chatter a channel or two wide.  ``counting_coverage`` and
    the manual carry the bundled-pattern readings; ``edge`` is the coarse
    location and nothing finer.  Both ends cannot be one region, because the
    plateau is measured in the middle.

    ``inflation`` is a **median** over the region, so it summarises rather than
    resolves: a region can hold finer steps of its own (on that same pattern the
    low-angle region runs ≈5× below 8°, ≈2.2× from 8-11°, ≈4× over 11.3-13°, then
    ≈2.2× tapering to 1× by ≈55°), and the levels are not even monotonic in 2θ.
    """

    two_theta_min: float
    two_theta_max: float
    inflation: float           # median σ²/max(y,1) in the region, over the plateau
    n_channels: int
    edge: str                  # "low" | "high" | "interior"


class PatternDiagnostics(Base):
    """Agent-readable observations about a raw pattern (no model involved).

    **Read ``signal_cutoffs`` first.**  Every other field here is computed over
    the whole range this object was handed, so where a cutoff exists they are
    measurements of a range that includes channels the instrument was not
    seeing the sample through, and they say so.  Measured on the private
    constant-wavelength neutron PSD scan of :func:`signal_cutoffs` (the full
    range against the window the data owner's own TOPAS refinements of it
    declare): the dead tail inflates ``amorphous_hump_score`` nearly twofold,
    **hides** the low-angle air-scatter rise altogether (``air_scatter_gain``
    understated by more than an order of magnitude), and moves
    ``baseline_lambda`` by two decades.  Nothing is re-run on a trimmed range
    and no field's value depends on the cutoffs — a diagnostic that quietly
    reported numbers for a range the caller did not ask about would be worse
    than one that says which range it used.  The ordering is the handling: read
    the cutoffs, decide the range, ask again if you changed it.

    * ``peak_fraction`` — fraction of channels more than 3σ above the
      envelope.  **Read it as the σ-relative statement it is, not as how much
      of the pattern is peak**: the bar is in σ, so a file whose σ is right and
      smaller than √y has genuinely more channels significantly above
      background and this number rises without the pattern changing.  Measured
      by rescaling the declared σ alone over the bundled fixtures, ×1.0 to
      ×0.15: a median factor of 2.92 and up to 9.57 (WP-1415, which left the
      definition alone rather than redefine a shipped number — the two measures
      below were the ones making a claim about *lines*, and they no longer move
      at all).
    * ``peak_density_per_deg`` — ``n_peaks`` per degree 2θ.  Its census takes
      :data:`SAMPLING_HEIGHT_FRACTION`'s floor, so it counts lines rather than
      the envelope's tracking error and does not move with the declared σ.  It
      keeps no prominence bar, so it over-counts (27 on a 13-line synthetic
      pattern, :func:`diagnose`), and nothing in the package reads it.
    * ``signal_to_background`` — near-maximum net signal (99.9th percentile)
      over the median background level.
    * ``air_scatter_gain`` — fraction of the cubic-fit residual variance of
      the background envelope explained by adding a 1/(2θ) column, i.e. a
      nested-model test for the low-angle air-scatter rise.  ≳0.3 triggers
      the 1/x background term.
    * ``amorphous_hump_score`` — RMS residual of the envelope *after* the
      cubic **and** the 1/x term, relative to the median level: what is left
      is genuinely broad non-polynomial structure (amorphous content,
      capillary glass).  ≳0.05 calls for a more flexible background.
    * ``contamination`` — Kβ / W Lα ghost candidates.  Needs ``wavelength``,
      and an *empty list means nothing was flagged or nothing was checked*:
      the Kβ position is anode-specific, so a wavelength that matches no
      tabulated Kα1 (:func:`identify_anode`) is silently skipped.
      ``contamination_searches`` tells the two apart.
    * ``contamination_searches`` — the ghost searches the screen ran,
      ``"kbeta"`` and ``"tungsten_la"``.  ``[]`` means it ran none, so an
      empty ``contamination`` is *not checked*: no ``wavelength``, one
      matching no tabulated Kα1, a source whose beam carries neither line
      (:func:`ghost_searches`), or no peak to search from.  ``None`` is an
      object written before the field existed (WP-2037), which cannot say.
    * ``baseline_lambda`` — the arPLS stiffness the whiteness rule selects
      for this pattern (:func:`rietx.background.select_arpls_lambda`).
    * ``steps_per_fwhm`` / ``n_peaks_measured`` — how finely the peaks were
      sampled, and over how many of them
      (:func:`sampling_steps_per_fwhm`).  ``None`` when no peak was
      measurable.  This is the one number here about the *experiment* rather
      than the pattern: below :data:`STEPS_PER_FWHM_MIN` no refinement can
      repair it, because the counts were never collected.
    * ``coverage_plateau`` — the bulk pattern's σ²/max(y, 1), the median over
      the middle half of the range.  1.0 is pure Poisson counting; a value
      away from 1 means the file's σ is something else (merged detectors, a
      monitor normalisation), which is a fact worth having on its own.
      ``None`` means σ was *not measured* and nothing below was checked.
    * ``coverage_regions`` — stretches carrying more variance per count than
      that plateau (:func:`counting_coverage`), i.e. fewer independent
      observations per channel.  Says the pattern's statistical weight is not
      uniform across its range, and how; triggers **nothing**, because a
      correct σ is already the whole handling.  Empty and
      ``coverage_plateau`` set means checked and uniform; empty with
      ``coverage_plateau`` ``None`` means not checkable.
    * ``signal_cutoffs`` — ends of the range where the instrument stopped
      seeing the sample (:func:`signal_cutoffs`), each a :class:`SignalCutoff`.
      Empty means the pattern's own ends are at its own interior level, which
      is the ordinary case and the one every other field here assumes.
    * ``dead_channels`` — short interior runs that measure nothing and outvote
      the pattern while doing it (:func:`dead_channels`), each a
      :class:`DeadChannelRun`.  Empty means none was found **or none could
      be**: the test needs a measured σ, so a pattern under the Poisson
      fallback answers empty for the second reason.  ``coverage_plateau``
      ``None`` is how to tell the two apart.
    """

    n_points: int
    two_theta_min: float
    two_theta_max: float
    baseline_lambda: float
    noise_sigma_median: float
    peak_fraction: float
    n_peaks: int
    peak_density_per_deg: float
    signal_to_background: float
    amorphous_hump_score: float
    air_scatter_gain: float
    steps_per_fwhm: float | None = None
    n_peaks_measured: int = 0
    contamination: list[ContaminationFlag] = Field(default_factory=list)
    contamination_searches: list[str] | None = None
    coverage_plateau: float | None = None
    coverage_regions: list[CoverageRegion] = Field(default_factory=list)
    signal_cutoffs: list[SignalCutoff] = Field(default_factory=list)
    dead_channels: list[DeadChannelRun] = Field(default_factory=list)

    #: The headings ``print`` shows the fields under, in reading order
    #: (WP-2037, the maintainer's choice of 2026-10-23): what anyone refining
    #: checks, what matters on some instruments, and the numbers rietx
    #: measures for its own use.  Every field appears once, the range in the
    #: head and ``contamination_searches`` inside the ``contamination`` row
    #: (``tests/test_display.py``).
    _READING_ORDER: ClassVar[tuple[tuple[str, tuple[str, ...]], ...]] = (
        ("checked on every pattern",
         ("signal_cutoffs", "steps_per_fwhm", "n_peaks_measured", "contamination",
          "signal_to_background")),
        ("matters on some instruments",
         ("dead_channels", "coverage_plateau", "coverage_regions", "air_scatter_gain",
          "amorphous_hump_score")),
        ("rietx's own measurements",
         ("baseline_lambda", "noise_sigma_median", "peak_fraction", "n_peaks",
          "peak_density_per_deg")),
    )

    def __str__(self) -> str:
        """Every field under its heading in :attr:`_READING_ORDER`, each bare
        number to three significant figures.  An empty field says whether its
        check ran: ``none`` where it ran and found nothing, ``not checked``
        where it could not run.  Which it was is read off fields:
        ``coverage_plateau`` is ``None`` without a measured σ, and
        ``contamination_searches`` lists the searches that ran."""
        from .._display import significant, tree
        head = (f"PatternDiagnostics of {self.n_points} points, "
                f"{self.two_theta_min:g}–{self.two_theta_max:g}° 2θ")
        values = {name: significant(value) for name in type(self).model_fields
                  if isinstance(value := getattr(self, name), float)}
        if self.coverage_plateau is None:
            unmeasured = "not checked (no measured σ)"
            values["coverage_plateau"] = unmeasured
            for name in ("dead_channels", "coverage_regions"):
                if not getattr(self, name):
                    values[name] = unmeasured
        if self.steps_per_fwhm is None:
            values["steps_per_fwhm"] = "not measured (no peak measurable)"
        if not self.contamination and self.contamination_searches == []:
            values["contamination"] = "not checked"
        elif not self.contamination and self.contamination_searches is None:
            values["contamination"] = "none, or not checked (not recorded)"
        return tree(self, groups=self._READING_ORDER, show_empty=True, head=head,
                    values=values)


def background_envelope(two_theta: np.ndarray, y: np.ndarray, *,
                        window_deg: float = ENVELOPE_WINDOW_DEG,
                        quantile: float = ENVELOPE_QUANTILE
                        ) -> np.ndarray:
    """Rolling low-quantile envelope of the pattern — a peak-robust,
    λ-free stand-in for the background level.

    Windows are wider than any Bragg FWHM, so the low quantile inside each
    lands on background channels; the per-window values are interpolated back
    onto the grid.  Unlike a Whittaker/arPLS baseline this has no smoothing
    parameter to choose, which is what makes it usable *for* choosing one.

    **Each knot's x is its window's centre, so the outermost knots sit half a
    window inside the data and the edges must be extrapolated, not clamped**
    (WP-1028 §(i)).  ``np.interp`` clamps flat outside its knot range; against
    a falling background that clamp sits far under the truth, and the whole
    first half-window reads as positive net — enough for the peak picker to
    find a line on the pattern's rising left edge.  Measured across the seven
    bundled round-robin patterns: ``y[0]`` was 1.5-2× ``env[0]``, putting
    z = 4.7-6.9σ on the very first channel against a 5σ bar, and **five** such
    false lines survived to ``PeakList.usable()``.  So a knot is anchored at
    each *data edge*, linearly extrapolated from the two nearest — no new
    tunable, and no cropping, which would discard a real low-angle line on a
    specimen that has one.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    step = float(np.median(np.diff(tt)))
    w = max(int(window_deg / max(step, 1e-12)), 5)
    xs, ys = [], []
    for s in range(0, len(yy), max(w // 2, 1)):
        seg = yy[s:s + w]
        if len(seg) < 3:
            continue
        xs.append(float(tt[s:s + w].mean()))
        ys.append(float(np.percentile(seg, quantile)))
    if len(xs) < 2:
        return np.full_like(tt, float(np.median(yy)))
    xs, ys = _extrapolate_to_edges(xs, ys, float(tt[0]), float(tt[-1]))
    return np.interp(tt, np.asarray(xs), np.asarray(ys))


def envelope_measured_span(two_theta: np.ndarray, *,
                           window_deg: float = ENVELOPE_WINDOW_DEG
                           ) -> tuple[float, float]:
    """The 2θ range over which :func:`background_envelope` *interpolates*.

    Outside it the envelope is extrapolated from the two nearest knots, so a
    line standing there has its prominence measured over a background level
    nobody observed.  Same window arithmetic as the envelope itself, kept
    beside it so the two cannot drift apart; the span is the first and last
    window *centres*, which is exactly where the knots are.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    if len(tt) < 3:
        return float(tt[0]), float(tt[-1])
    step = float(np.median(np.diff(tt)))
    w = max(int(window_deg / max(step, 1e-12)), 5)
    stride = max(w // 2, 1)
    centres = [float(tt[s:s + w].mean()) for s in range(0, len(tt), stride)
               if len(tt[s:s + w]) >= 3]
    if len(centres) < 2:
        return float(tt[0]), float(tt[-1])
    return centres[0], centres[-1]


def _extrapolate_to_edges(xs: list[float], ys: list[float],
                          lo: float, hi: float) -> tuple[list[float], list[float]]:
    """Anchor a knot at each data edge, linearly from the two nearest knots.

    Only extends — an edge already covered by a knot is left alone, so this is
    a no-op on a pattern whose windows happen to reach the ends.
    """
    if lo < xs[0]:
        slope = (ys[1] - ys[0]) / (xs[1] - xs[0]) if xs[1] != xs[0] else 0.0
        xs = [lo, *xs]
        ys = [ys[0] + slope * (lo - xs[1]), *ys]
    if hi > xs[-1]:
        slope = ((ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
                 if xs[-1] != xs[-2] else 0.0)
        ys = [*ys, ys[-1] + slope * (hi - xs[-1])]
        xs = [*xs, hi]
    return xs, ys


def _median_steps_per_fwhm(net: np.ndarray, sigma: np.ndarray
                           ) -> tuple[float | None, int]:
    """Median channels across the half-height width of ``net``'s peaks.

    ``scipy.signal.peak_widths`` returns the width in **samples**, which is
    already the quantity §2 asks for — "steps across the top of each peak" —
    with no conversion and no assumption that the 2θ grid is uniform.  It
    measures at half the peak's *prominence*, so for an isolated peak on a
    removed background this is the FWHM, and for one shoulder of an overlapped
    pair it is the width above the saddle, which is the part of that peak the
    steps actually resolve.

    Peaks are selected here rather than taken from :func:`diagnose`'s census
    because the two need different things: a peak *count* wants every line the
    pattern shows, while a peak *width* wants only lines that are resolved —
    hence :data:`SAMPLING_PROMINENCE_SIGMA`, without which the measurement
    reads the noise on a strong peak's own top.

    **Both bars are the larger of a σ floor and a dynamic-range floor**
    (:data:`SAMPLING_HEIGHT_FRACTION`), because the two floors answer different
    questions and only one of them is σ's.  "Is this maximum significant" is
    the σ question.  "Is it a line rather than the envelope failing to track
    the background" is a question about the pattern's own scale, and asking it
    in σ is what made the measurement a function of the declared σ rather than
    of the experiment: on a file whose σ is right and 3.46× smaller than √y the
    σ bar reads the envelope's tracking error as 5σ of significance.  With the
    second floor the answer is invariant under a rescale of the declared σ,
    measured on every fixture the suite carries (that constant's note).

    The median rather than the mean: one clipped width from a peak sitting on
    a neighbour's flank should not move the answer, and the guideline is about
    the pattern rather than about its worst line.
    """
    pos = np.where(net > 0, net, 0.0)
    if not len(pos):
        return None, 0
    # the same "near-maximum net signal" ``signal_to_background`` reports, and
    # a percentile rather than ``max`` for the same reason: one hot channel
    # would otherwise set what counts as a line (measured — anchoring on
    # ``max`` lets a single injected spike move 16 of 26 fixtures by over 5 %,
    # one of them by 66 %; on the percentile, 3 of 26 and none past 9 %).
    floor = SAMPLING_HEIGHT_FRACTION * float(np.percentile(pos, 99.9))
    idx, _ = find_peaks(pos, distance=3,
                        height=np.maximum(5.0 * sigma, floor),
                        prominence=np.maximum(
                            SAMPLING_PROMINENCE_SIGMA * sigma, floor))
    if not len(idx):
        return None, 0
    with warnings.catch_warnings():
        # scipy warns that some peak has zero width or zero prominence, which
        # is exactly the case dropped on the next line — the filter *is* the
        # handling, so the warning is noise rather than news.  Matched on the
        # message because ``PeakPropertyWarning`` is not exported from
        # ``scipy.signal`` (checked on 1.18): a private import would be the
        # more fragile half.  Both wordings, because scipy raises the width one
        # on a synthetic pattern and the prominence one on real 11-BM data.
        warnings.filterwarnings(
            "ignore", message=r"some peaks have a (width|prominence) of 0")
        widths = peak_widths(np.maximum(net, 0.0), idx, rel_height=0.5)[0]
    usable = widths[np.isfinite(widths) & (widths > 0.0)]
    if not len(usable):
        return None, 0
    return float(np.median(usable)), int(len(usable))


def sampling_steps_per_fwhm(two_theta: np.ndarray, y: np.ndarray,
                            sigma: np.ndarray | None = None
                            ) -> tuple[float | None, int]:
    """``(steps per FWHM, peaks measured)`` for a pattern — the one authority.

    McCusker et al. (1999) §2 leads with this because undersampling is a
    data-collection error that no refinement can repair: at fewer than
    :data:`STEPS_PER_FWHM_MIN` steps across a peak, the integrated intensity of
    that reflection was never measured, whatever is done to the model
    afterwards.

    Model-free, like everything else in this module — the peaks are found on
    the pattern's own net signal over a rolling low-quantile envelope, never
    from a reflection list.  Two callers share it so the number cannot come
    out twice differently: :func:`diagnose`, which reports it before any
    refinement, and ``refine``, which reports it on the **fitted** channels and
    raises ``PATTERN_UNDERSAMPLED`` from it.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    counts = np.asarray(y, dtype=np.float64)
    if len(tt) < 3:
        return None, 0
    sig = (np.sqrt(np.maximum(counts, POISSON_FLOOR_COUNTS)) if sigma is None
           else np.asarray(sigma, dtype=np.float64))
    return _median_steps_per_fwhm(counts - background_envelope(tt, counts), sig)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive ``(start, end)`` index pairs of the True runs in ``mask``."""
    padded = np.concatenate(([False], mask.astype(bool), [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(a), int(b) - 1) for a, b in zip(edges[::2], edges[1::2])]


def _finite_median(values: np.ndarray) -> float | None:
    """Median over the finite entries, or ``None`` when there are none."""
    usable = values[np.isfinite(values)]
    return float(np.median(usable)) if len(usable) else None


def signal_cutoffs(
    two_theta: np.ndarray, y: np.ndarray, sigma: np.ndarray | None = None, *,
    cutoff_fraction: float = CUTOFF_FRACTION,
    onset_fraction: float = CUTOFF_ONSET_FRACTION,
    min_deg: float = CUTOFF_MIN_DEG,
    smooth_deg: float = CUTOFF_SMOOTH_DEG,
    plateau_deg: float = CUTOFF_PLATEAU_DEG,
    interior_fraction: float = CUTOFF_INTERIOR_FRACTION,
) -> list[SignalCutoff]:
    """Ends of the range where the pattern's level collapsed and stayed down —
    channels the instrument was not seeing the sample through.

    Detector active area running out, a beamstop or its halo, sample-environment
    shielding: whatever the cause, these channels carry no diffraction
    information and **must be excluded rather than fitted**.  This reports them
    and applies nothing; the range is the caller's decision.

    **The evidence.**  A private constant-wavelength neutron PSD scan (σ from
    the file).  The two ends are different shapes, which is why one rule has to
    describe both:

    * **Trailing — a cliff, then a floor.**  From above the interior level to
      a few per cent of it within a couple of degrees, then flat at that floor
      for the remaining several degrees of the range.  A factor of tens in a
      couple of degrees, and past it nothing.
    * **Leading — a graded degradation.**  A direct-beam shoulder in the first
      channels, a shadowed floor of a few per cent over the next degrees, a
      *bump* peaking at a modest fraction of interior — at the instrument's
      wavelength that is d ≈ 30 Å, so it is not sample diffraction — then a
      monotone climb that reaches the interior level only tens of degrees in.

    So the two ends carry different arguments, and only the first is "there is
    nothing here".  At the low end there *is* structure; it is a beamstop halo
    and air scatter rather than the specimen, measured at several times the
    interior's fractional error, and fitting a background through it means
    describing non-specimen structure at poor precision.  Both are reasons to
    exclude, and they are not the same reason.

    **σ is not the story.**  σ²/y holds constant to within a few per cent
    straight through both transitions, so the file's σ is honest and this is
    not a variance or weighting problem — it is a region with no information
    in it.  Do not read a :class:`SignalCutoff` as a :class:`CoverageRegion`
    or merge the two measures: that one counts detectors, this one counts
    photons.  The precision penalty a caller reads (σ/y several times the
    interior's inside either collapse) is a *consequence* of the level and is
    reported as :attr:`SignalCutoff.relative_error_ratio`, derived.

    **Why exclusion and not a more flexible background.**  A Chebyshev or a
    P-spline asked to span a cliff of a factor of tens has no such shape
    available: it either rings across the whole pattern or splits the
    difference, and both distort the background *under the real peaks*.  That
    is CLAUDE.md's "background flexibility is a correctness question, not a
    cosmetic one" one step earlier — before the background model is chosen, not
    after it has been asked to do something it cannot.

    **And it is read before the other diagnostics, because it corrupts them.**
    Measured on that file, :func:`diagnose` over the full range against the
    data owner's TOPAS window: ``amorphous_hump_score`` inflated nearly
    twofold by the dead tail, ``air_scatter_gain`` understated by more than an
    order of magnitude (the real low-angle rise **masked entirely**, because
    the envelope's 1/x column is spent on the leading collapse instead), and
    ``baseline_lambda`` moved by two decades (the arPLS stiffness selection).

    **The method**, and every constant it uses carries its own measurement:

    1. ``lvl`` — a rolling median of ``y`` over :data:`CUTOFF_SMOOTH_DEG`.
    2. ``interior`` — the median of ``lvl`` over the central
       :data:`CUTOFF_INTERIOR_FRACTION` of the range.
    3. A candidate run is ``lvl < cutoff_fraction · interior``, extended outward
       through channels still below the onset level (below), and it must **reach
       the first or last channel** — that is what makes it a cutoff rather than
       an interior gap, and the extension is what lets a first channel sitting a
       hair above the threshold belong to the collapse behind it (measured: two
       of the three private scans start a hair either side of the 0.25
       threshold, and the same region follows both).
    4. It must span at least ``min_deg``, or it is a dip and not an instrument.
    5. The **local plateau** is the median of ``lvl`` over the
       :data:`CUTOFF_PLATEAU_DEG` just inside the run; walking inward from the
       run's edge, the first channel back at ``onset_fraction`` × that plateau
       is the boundary reported.  The walk cannot run away: half of the plateau
       window is at or above the plateau by construction, so it stops inside it.

    **A pattern that is entirely below the threshold cannot happen, and that is
    deliberate.**  The threshold is a fraction of the pattern's *own* interior
    median, so at least half the central portion is by construction at or above
    it; there is no input for which this returns "the whole pattern is dead".
    The cost is the honest one: a pattern whose collapse consumed the middle too
    drags the interior level down with it and comes back **empty**.  Silence
    where the evidence is gone, never a claim over the whole range.

    Degenerate inputs return an empty list rather than raising: a pattern too
    short to hold an interior and a collapse, an all-zero pattern (nothing to be
    a fraction of — a dead *pattern* is the reader's problem, not this measure's),
    and one with no finite channel at all.  A non-finite channel elsewhere is
    filled from its finite neighbours before smoothing, so it neither opens a
    run nor closes one: a channel that says nothing must not be heard saying
    something, in either direction.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    counts = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(counts)
    n = len(tt)
    if n < 4 or not finite.any():
        return []
    steps = np.diff(tt)
    steps = steps[np.isfinite(steps) & (steps > 0.0)]
    if not len(steps):
        return []
    step = float(np.median(steps))
    width = max(int(smooth_deg / step), 3)
    # A pattern shorter than three smoothing windows has no interior to compare
    # an edge against — the measurement is a comparison, so too few channels is
    # "not measurable" and not "no cutoff".  Both read as an empty list; the
    # caller that needs the difference has ``n_points``.
    if n < 3 * width:
        return []
    # A non-finite channel is filled from its finite neighbours, which is the
    # level it would have carried had it said anything, so it neither opens a
    # run nor closes one.  (:func:`counting_coverage` fills with its plateau for
    # the same reason: the neutral value of a *ratio* is 1, the neutral value of
    # a *level* is the level beside it.  Filling with a global median instead
    # would put a live channel at a dead edge and hide the cutoff behind it.)
    filled = np.interp(tt, tt[finite], counts[finite])
    lvl = median_filter(filled, size=width, mode="nearest")
    margin = int(n * (1.0 - interior_fraction) / 2.0)
    interior = float(np.median(lvl[margin:n - margin]))
    if not interior > 0.0:
        return []
    plateau_width = max(int(plateau_deg / step), 3)

    cutoffs: list[SignalCutoff] = []
    rel = rel_interior = None
    if sigma is not None:
        with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
            rel = np.asarray(sigma, dtype=np.float64) / np.maximum(filled, 1.0)
        rel_interior = _finite_median(rel[margin:n - margin])
        if not rel_interior:
            rel = None      # σ that is not measurable here derives nothing
    for lo, hi in _runs(lvl < cutoff_fraction * interior):
        # Unreachable while ``interior`` is the pattern's own median (see the
        # docstring), and cheap to say out loud: a run over every channel is a
        # statement about the whole pattern, which this measure never makes.
        if lo == 0 and hi == n - 1:
            continue
        # Each run is tried as both edges; an interior one answers to neither,
        # and no run can answer to both without covering the middle.  ``inward``
        # is the direction from the collapse towards the live pattern.
        for edge, inner, outer, inward in (("low", hi, lo, 1), ("high", lo, hi, -1)):
            window = (lvl[inner + 1:inner + 1 + plateau_width] if inward > 0
                      else lvl[max(inner - plateau_width, 0):inner])
            if not len(window):
                continue
            onset = onset_fraction * float(np.median(window))
            k = outer
            while 0 < k < n - 1 and lvl[k - inward] < onset:
                k -= inward
            if k != (0 if inward > 0 else n - 1):
                continue                      # an interior gap, not a cutoff
            if abs(tt[inner] - tt[k]) < min_deg:
                continue                      # a dip in the first channels
            boundary = inner
            while 0 <= boundary + inward < n and lvl[boundary] < onset:
                boundary += inward
            # The floor is measured over the channels that are actually at it,
            # never over the transition the outward extension picked up.
            floor = float(np.median(lvl[lo:hi + 1]) / interior)
            here = None if rel is None else _finite_median(rel[lo:hi + 1])
            cutoffs.append(SignalCutoff(
                edge=edge, two_theta=float(tt[boundary]), floor_fraction=floor,
                n_channels=int(boundary if inward > 0 else n - 1 - boundary),
                relative_error_ratio=(None if here is None
                                      else here / rel_interior)))
    # Two runs at one edge are one collapse with a bump in it — the outward
    # extension has already crossed a stretch that never got back to level — so
    # the usable range starts after the *last* of them and the innermost
    # boundary is the answer.  At most one cutoff per edge, low first.
    return [max((c for c in cutoffs if c.edge == edge),
                key=lambda c: c.n_channels)
            for edge in ("low", "high") if any(c.edge == edge for c in cutoffs)]


def dead_channels(
    two_theta: np.ndarray, y: np.ndarray, sigma: np.ndarray | None = None, *,
    level_fraction: float = DEAD_LEVEL_FRACTION,
    weight_ratio_min: float = DEAD_WEIGHT_RATIO_MIN,
    window_deg: float = DEAD_LEVEL_WINDOW_DEG,
    max_run_deg: float = CUTOFF_MIN_DEG,
) -> list[DeadChannelRun]:
    """Short runs inside the range that outvote the pattern while measuring
    nothing — a dead detector cell, a masked channel, a gap between banks.

    Model-free, like everything else here, and it **reports and applies
    nothing**: the interval it names is the caller's to exclude, because
    ``project.fitted_mask`` is the one authority on which channels a run fits
    (WP-1033).

    **It needs a measured σ and returns nothing without one**, which is the
    load-bearing part rather than a limitation.  "This channel is low" does not
    separate a dead cell from a channel that legitimately counted zero — both
    are low, and the bundled fixtures carry 217 of the second kind.  What
    separates them is the σ column: a channel that counted zero honestly
    carries *less* weight than a live one, while a dead cell's error bar
    collapsed along with its intensity and it carries thousands of times more.
    Under the Poisson fallback σ = √max(y, 1) that distinction does not exist —
    every low channel would look dead — so answering at all would be reporting
    the fallback rather than the file, the same refusal
    :func:`counting_coverage` makes and for the same reason.

    Why the *level* is a median of the envelope rather than of the
    intensities: the comparison a dead channel has to lose is against its own
    background, and on any pattern with peaks a median of ``y`` over a window
    centred on a strong line *is* that line, which would make the line's own
    flanks read as dead.  :func:`background_envelope` is already the module's
    peak-robust stand-in for the background, and a median over
    :data:`DEAD_LEVEL_WINDOW_DEG` of it removes the local dip the dropout
    itself puts in the envelope.

    **A short run touching an edge is admitted too (WP-1415), on the same
    weight-ratio test as an interior one — measured on issue #274's own D1B
    file (public; Sparks et al. 2019, *Phys. Rev. B* **99**, 104104) and a
    private Mythen operando set, and separately checked against unpublished
    neutron PSD holds; neither private set is quoted here.**
    D1B (`300q-300K.dat`, the issue's own fixture) carries a two-channel dead
    pair at *each* end (0.79-0.89°, y≈4-7, σ≈1; and 128.59-128.69°, y=3-5,
    σ=1.0-1.414 — the latter is the file's literal last two channels, nothing
    recorded beyond them).  Both read a weight ratio against their single
    live neighbour of **1520 and 2286** — the same signature
    :data:`DEAD_WEIGHT_RATIO_MIN` already gates on in the interior, 15-23×
    over it.  The private Mythen set is the negative control: its edges are
    cliffs of the kind :func:`signal_cutoffs` reports, and read the same way
    they give weight ratios of order unity or below — nearly two orders of
    magnitude under the threshold and nowhere near the D1B signature,
    because a cliff's σ falls **with** its level (honest counting statistics)
    while a dead cell's σ collapses **against** it.  The private neutron PSD
    holds :func:`signal_cutoffs`' docstring draws on agree in direction —
    private, unpublished data, so no figure from either private set is
    repeated here, only the agreement.  So the
    rule is the interior rule, unchanged, with one relaxation — an
    edge-touching run is judged **against whichever side has a neighbour**
    rather than declined outright, and a run touching both ends (the whole
    pattern) still has none and is still declined.  A run of
    :data:`CUTOFF_MIN_DEG` or longer in the **middle** is still declined: the
    level a long run is judged against cannot survive it — a dropout wider
    than :data:`DEAD_LEVEL_WINDOW_DEG` drags down the very estimate meant to
    expose it, and the honest failure there is silence rather than the
    spurious one-channel run the length test alone produced.  That case stays
    owned by nobody today; only the edge case was #274's second ask.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    counts = np.asarray(y, dtype=np.float64)
    if sigma is None or len(tt) < 3:
        return []
    sig = np.asarray(sigma, dtype=np.float64)
    step = float(np.median(np.diff(tt)))
    if not np.isfinite(step) or step <= 0:
        return []

    width = max(int(window_deg / step), 5)

    # Two passes, because a level computed from the channels it is judging is
    # not a level.  ``background_envelope`` anchors a knot at each data edge
    # and extrapolates linearly from the two nearest (WP-1028), so a dropout
    # near an end drags those knots down and the extrapolation carries the
    # envelope *negative* — measured on a synthetic D1B with #274's own pair
    # four channels from the top of the range: the envelope reads −4.6 where
    # the background is 78, over the last 30 channels, and the run is missed.
    # Which is the case the issue reports, so it is the case to get right.
    # Pass 1 is a median of the intensities, which needs no knots and no
    # extrapolation; it is not peak-robust, and does not need to be, because
    # all it decides is which channels are withheld from pass 2.  It is run to
    # a fixed point because one pass only reaches a run's outer channels once
    # the run approaches the median's own window: the interior's window is
    # itself all dropout, so the median there is dead and the channel is not
    # flagged.  Iterating on the repaired series walks the mask inward until
    # it stops growing — without it a 1.9° dropout left the level collapsed
    # across its middle, which made every later test read the wrong number
    # there rather than decline.
    # ``mode="reflect"`` here, not ``"nearest"`` (WP-1415, measured on #274's
    # real file rather than the synthetic above): a run that sits at the
    # *literal* last channels of the array — D1B's trailing pair is exactly
    # this, nothing recorded beyond 128.69° — has ``"nearest"`` pad the window
    # past the edge by repeating the dropout's own value, which drags
    # ``coarse`` down to the dropout itself (measured: 5.0 against an interior
    # ~37 000) and ``found`` never fires, so the repair never runs and the
    # channel is silently missed regardless of the edge-admission below.
    # ``"reflect"`` instead mirrors the true samples back past the edge, so at
    # most the two dropout channels themselves re-appear in the padding before
    # it recovers to the interior level (measured: coarse tail 37 123, the
    # correct neighbouring value).  A synthetic four channels from the top (the
    # comment above) never exercised this because real data still existed
    # beyond the dropout there; #274's own file does not have that luxury.
    repaired = counts
    suspect = np.zeros(len(counts), bool)
    for _ in range(_DEAD_REPAIR_PASSES):
        coarse = median_filter(repaired, size=width, mode="reflect")
        with np.errstate(invalid="ignore"):
            found = (coarse > 0) & (counts < level_fraction * coarse)
        if found.all() or not found.any() or np.array_equal(found, suspect):
            break
        suspect = found
        repaired = counts.copy()
        repaired[suspect] = np.interp(
            tt[suspect], tt[~suspect], counts[~suspect])
    level = median_filter(background_envelope(tt, repaired), size=width,
                          mode="reflect")
    with np.errstate(invalid="ignore"):
        low = (level > 0) & (counts < level_fraction * level)
    if not low.any() or not (~low).any():
        return []

    out: list[DeadChannelRun] = []
    for a, b in _runs(low):
        if tt[b] - tt[a] >= max_run_deg:
            continue                      # too long — see the docstring
        # Bounded by a live channel at the level on every side it *has* one,
        # or declined.  A run touching both ends is the whole pattern and has
        # no neighbour anywhere — declined, as always.  A run touching one
        # end (WP-1415, issue #274's second ask) is judged against the side
        # it has: the array simply ending is not evidence either way, and the
        # weight-ratio test below is what actually separates a dead edge pair
        # from a signal_cutoffs-shaped cliff (measured on the public D1B file
        # and a private Mythen operando set, and separately checked against
        # private neutron PSD holds — see the docstring).  For a genuinely *interior* run this is unchanged and
        # still load-bearing: one long enough to drag the level down is one
        # whose own edge channel is the only one still reading below it.
        # Without some bound a 1.9° interior dropout came back as a spurious
        # *one-channel* run rather than as nothing.
        touches_low_edge = a == 0
        touches_high_edge = b == len(tt) - 1
        if touches_low_edge and touches_high_edge:
            continue                      # the whole pattern — not this measure's
        if not touches_low_edge and not (
                counts[a - 1] >= level_fraction * level[a - 1]):
            continue
        if not touches_high_edge and not (
                counts[b + 1] >= level_fraction * level[b + 1]):
            continue
        run_sigma = _finite_median(sig[a:b + 1])
        if not run_sigma or run_sigma <= 0:
            continue
        # against the run's own neighbours, not the whole pattern: the pull a
        # dead channel exerts is on the background *there*, and a median σ
        # taken over the whole range would be a different instrument's answer
        # on a pattern whose counting statistics vary along it.
        near = np.zeros(len(tt), bool)
        near[max(a - width, 0):b + 1 + width] = True
        near &= ~low
        live_sigma = _finite_median(sig[near]) if near.any() else None
        if not live_sigma or live_sigma <= 0:
            continue
        ratio = float((live_sigma / run_sigma) ** 2)
        if ratio < weight_ratio_min:
            continue
        here = _finite_median(level[a:b + 1])
        frac = (float(np.median(counts[a:b + 1])) / here
                if here and here > 0 else 0.0)
        out.append(DeadChannelRun(
            two_theta_min=float(tt[a]), two_theta_max=float(tt[b]),
            n_channels=int(b - a + 1), level_fraction=float(frac),
            weight_ratio=ratio))
    return out


#: Decimals both ``PATTERN_DEAD_CHANNELS`` messages quote an interval to.
_DEAD_INTERVAL_DECIMALS = 3


def _dead_interval(run: DeadChannelRun) -> tuple[float, float]:
    """The interval to exclude for ``run``, at the precision it is printed at.

    The bounds are **widened outward**, never rounded to nearest, and that is
    the whole content.  ``PatternData.in_range_mask`` drops
    ``lo <= 2θ <= hi`` against the stored doubles, so a bound printed to
    :data:`_DEAD_INTERVAL_DECIMALS` and read back has to *contain* the run.
    Nearest does not: a 0.1° grid built by accumulation puts the first dead
    channel at 64.99999999999979, which prints as ``65.000``, and a caller
    following the message verbatim leaves that very channel in the fit
    (measured — one of the two channels of the D1B pair survived the
    exclusion the finding asked for).  Widening costs at most one extra
    channel a side, and a live channel beside a dead one is worth nothing.
    """
    return _exclusion_interval(run.two_theta_min, run.two_theta_max)


def _exclusion_interval(lo: float, hi: float) -> tuple[float, float]:
    """``(lo, hi)`` widened outward to :data:`_DEAD_INTERVAL_DECIMALS`, and
    never empty.

    :func:`_dead_interval` says why outward.  A single point prints as
    ``(x, x)``, which ``schemas.project.check_interval`` refuses as empty, so
    the upper bound then moves one printed step up and the interval still
    contains the point.
    """
    scale = 10.0 ** _DEAD_INTERVAL_DECIMALS
    a = float(np.floor(lo * scale))
    b = max(float(np.ceil(hi * scale)), a + 1.0)
    return a / scale, b / scale


def counting_coverage(
    two_theta: np.ndarray, y: np.ndarray, sigma: np.ndarray | None, *,
    threshold: float = COVERAGE_INFLATION_THRESHOLD,
    smooth_deg: float = COVERAGE_SMOOTH_DEG,
    min_channels: int | None = None,
) -> tuple[list[CoverageRegion], float | None]:
    """``(regions, plateau)`` — where this pattern's σ implies fewer independent
    observations per channel than the bulk of the scan does.

    The statistic is the **variance inflation** v = σ²/max(y, 1), which is 1 for
    pure Poisson counting and proportional to 1/n_eff for a channel averaged over
    n_eff independent observations.  Its bulk level (``plateau``, the median over
    the middle half of the range) is the reference, and a region is a run of
    channels whose smoothed v/plateau exceeds ``threshold``.  Nothing here looks
    at the intensities except through that ratio: no baseline, no peak list, no
    model.

    **Empty when σ was not measured**, signalled by ``sigma=None`` — the spelling
    :func:`sampling_steps_per_fwhm` already uses, and the fact
    :meth:`PatternData.sig` and ``DataRef.has_sigma`` are the authorities for
    (CLAUDE.md, Weights).  Under the Poisson fallback σ = √max(y, 1) the ratio is
    *identically* 1 by construction, so the measure carries no information at
    all; an answer computed from it would be an answer about the fallback rather
    than about the experiment, and ``plateau`` comes back ``None`` to say so.
    Handing the fallback array in explicitly is therefore also empty, but for the
    weaker reason that a constant ratio crosses no threshold.

    **What a region means.** On an instrument with a bank of detectors on a
    circle, the number contributing to a given 2θ falls off at both ends of the
    range, and v ∝ 1/n_eff counts them.  Measured on two NIST BT-1
    constant-wavelength neutron patterns (3.00-166.25° at 0.05°, 3266 points,
    σ from the file, plateau v = 0.837 and 0.826): both show the same ladder —
    ≈5× below ≈8°, ≈2.2-2.6× from 8° to
    ≈15°, tapering to 1× by ≈55°, 1× through the middle, and a step back to
    ≈2.2× within one channel at 161.30°, held to the end of the scan.  The levels
    are *quantised* because detectors are integers, which is what makes a step
    a step rather than a gradual falloff, and they are not monotonic in 2θ
    (one of them sits at ≈4× over 11.3-13.0°, between two ≈2.2× stretches).
    Neither pattern's plateau contains a region at all.

    **Where it fires on the bundled patterns**, and why a detector-count reading
    of ``edge`` is too narrow for all of them (pinned in ``test_background_auto``,
    tabulated in the manual).  Three of the repo's patterns with a measured σ
    fire, none of them a plain detector-bank falloff.  The two 11-BM synchrotron
    scans (``11BM_NAC.fxye`` high 46-60°, 2.80×; ``11BM_LaB6_660a.fxye`` high
    53-67°, 2.82×) rise *smoothly* over the last third — an analyser bank tapering
    out, not the quantised step the BT-1 ends show, so "detectors are integers"
    is the wrong mechanism there.  ``nist_srm660c_100a.cif`` fires on a broad low
    region (20.3-62.5°, 5.50×) and two interior ones (66.7-75.0°, 2.74×;
    140.5-147.5°, 1.58×); its ladder is non-monotonic in both directions, which
    reads as a variable counting-time or slit schedule rather than detector
    count, and the two interior regions are the same threshold-crossing chatter
    the measure declares elsewhere.  The measure is right that σ is structured on
    all three; ``edge`` locates the structure and does not name its cause, and
    the manual's table is where a reader gets the cause.  It stays silent on the
    one other σ-bearing bundled pattern (``panalytical_attenuator.xrdml``) and
    returns ``None`` on the two with no σ column.

    **What it is for, and what it is not.** It reports that the pattern's
    statistical weight is not uniform across its range — a fact about the
    experiment's coverage, not about the specimen — and it is the model-free
    confirmation that a file's σ column is real and structured rather than
    fabricated, since a fabricated or fallback σ cannot show this at all.  It is
    *not* an argument for trimming the range: if σ is right, weighted least
    squares already weights those channels correctly, which is what σ is for.
    Where it disagrees with a hand-chosen fit range that is information about the
    range, in both directions and with no recommendation attached.

    **One caveat, unhandled on purpose.** v also rises where the *intensity*
    collapses — a scan or a detector that stops leaves near-empty channels with a
    finite σ, and max(y, 1) in the denominator then makes v large for a reason
    that has nothing to do with detector count.  This function cannot tell the
    two apart from σ alone and does not try; a region reported at the very end of
    a pattern whose counts fall to nothing there is that other phenomenon.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    if sigma is None or len(tt) < 4:
        return [], None
    counts = np.asarray(y, dtype=np.float64)
    sig = np.asarray(sigma, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        v = sig ** 2 / np.maximum(counts, 1.0)
    finite = np.isfinite(v)

    n = len(tt)
    middle = v[n // 4:n - n // 4]
    usable = middle[np.isfinite(middle) & (middle > 0.0)]
    if not len(usable):
        return [], None
    # positive and finite by that filter, so the division below is safe
    plateau = float(np.median(usable))

    # A non-finite channel makes no claim rather than a false one: it is set to
    # the plateau, so it neither starts a region nor breaks the median filter.
    ratio = np.where(finite, v, plateau) / plateau

    steps = np.diff(tt)
    steps = steps[np.isfinite(steps) & (steps > 0.0)]
    if not len(steps):
        return [], plateau
    # The smoothing window doubles as the minimum region width and as the widest
    # gap that gets closed, both from one sentence: the statistic cannot resolve a
    # feature narrower than the window it was smoothed over, so a shorter run is
    # not evidence and a shorter gap is not a boundary.  One rule, no second
    # tunable — ``min_channels`` overrides only the first, since the second is a
    # property of the smoother rather than a choice about what counts.
    width = max(int(smooth_deg / float(np.median(steps))), 5)
    floor = width if min_channels is None else max(int(min_channels), 1)
    smoothed = median_filter(ratio, size=width, mode="nearest")

    merged: list[tuple[int, int]] = []
    for lo, hi in _runs(smoothed > threshold):
        if merged and lo - merged[-1][1] - 1 < width:
            merged[-1] = (merged[-1][0], hi)
        else:
            merged.append((lo, hi))

    regions: list[CoverageRegion] = []
    for lo, hi in merged:
        if hi - lo + 1 < floor:
            continue
        edge = "low" if lo == 0 else "high" if hi == n - 1 else "interior"
        regions.append(CoverageRegion(
            two_theta_min=float(tt[lo]), two_theta_max=float(tt[hi]),
            # the raw ratio, not the smoothed one: smoothing is what found the
            # boundaries, and a median over the region needs no help from it
            inflation=float(np.median(ratio[lo:hi + 1])),
            n_channels=int(hi - lo + 1), edge=edge))
    return regions, plateau


def diagnose(data: PatternData, *, wavelength: float | None = None,
             baseline_lambda: float | None = None,
             source: object | None = None) -> PatternDiagnostics:
    """:class:`PatternDiagnostics` of a raw pattern.

    ``source`` is the declared beam, which the contamination screen asks what
    it can carry (:func:`ghost_searches`); ``None`` leaves the screen to the
    wavelength alone, as before.  A neutron source skips it.

    2θ only.  Every number below is an angle or is derived through one — the
    amorphous-hump position, the air-scatter gain, the signal cutoffs are all
    quoted in degrees, and :class:`PatternDiagnostics` has ``two_theta_min`` /
    ``two_theta_max`` fields to put them in.  So a TOF pattern is refused here
    rather than silently relabelled.
    """
    require_two_theta(data, "background.diagnose()")
    from .select import select_arpls_lambda

    mask = data.in_range_mask()
    tt = data.tt()[mask]
    y = data.y()[mask]
    sigma = data.sig()[mask]
    span = float(tt[-1] - tt[0])

    # First, and computed first so the order is visible: everything below is
    # measured over the whole supplied range, and a dead end moves those
    # numbers by up to two decades (:class:`PatternDiagnostics` has the table).
    # σ rides along only to derive the precision penalty, and only where it was
    # *measured* — under the Poisson fallback that ratio is a function of the
    # level it was derived from and would say nothing.
    cutoffs = signal_cutoffs(tt, y, sigma if data.sigma is not None else None)
    # the same σ-measured test, and for a sharper reason: without the file's
    # own σ this one cannot separate a dead cell from a channel that counted
    # zero at all, so it answers empty rather than guessing
    dead = dead_channels(tt, y, sigma if data.sigma is not None else None)

    env = background_envelope(tt, y)
    net = y - env
    med_env = float(np.median(env))

    # its own 3σ over the envelope: the order scan's mask is another rule
    # (``select.PEAK_MASK_SIGMA``, over an arPLS baseline)
    peak_channels = net > 3.0 * sigma
    # The census wants every line the pattern shows, so it keeps no prominence
    # bar — but its height bar takes the same dynamic-range floor the width
    # measurement does (:data:`SAMPLING_HEIGHT_FRACTION`), and for the same
    # reason: in σ alone it counted the envelope's tracking error as lines, and
    # harder the better the counting statistics were.  Measured over the
    # fixtures: 1558 "peaks" on 11-BM NAC at the file's own σ and 9403 at a
    # σ 3.46× smaller, against 96 at every scale with the floor; on a synthetic
    # 13-line CW-neutron pattern, 79 rising to 201 over σ ×1.0 to ×0.05,
    # against 27 at every one of them.  27 rather than 13 because this census
    # keeps no prominence bar and a strong peak's own noisy top carries more
    # than one maximum — which is what :data:`SAMPLING_PROMINENCE_SIGMA` is
    # for, and what a *count* deliberately does not apply.  The defect fixed
    # here is the scale dependence, not the over-count.
    # One ``find_peaks`` call serves the census and the ghost search, read at
    # two floors off the same near-maximum, because the census bar cannot also
    # be the ghost bar: a ghost is accepted down to ``GHOST_RATIO_RANGE[0]`` =
    # 0.5 % of its parent, which is six times *under* the census floor, so a
    # single 3 % bar deletes the Kβ and W Lα leaks this check exists to find
    # (measured: four injected 1 % Kβ ghosts, all four flagged at the σ bar and
    # none at the census floor).  Below ``ghost_bar`` no candidate can pass the
    # ratio test anyway, so it is the widest bar the ghost search has any use
    # for.  The census is the subset above its own bar, which is the set a
    # second ``find_peaks`` at that bar returns: ``distance`` keeps the tallest
    # of a cluster, and a peak admitted by a *lower* floor can never displace a
    # taller one (checked equal on every bundled fixture at σ ×1, ×0.289 and
    # ×0.05).
    pos_net = np.where(net > 0, net, 0.0)
    near_max = float(np.percentile(pos_net, 99.9))
    census_bar = np.maximum(5.0 * sigma, SAMPLING_HEIGHT_FRACTION * near_max)
    ghost_bar = np.maximum(5.0 * sigma, GHOST_RATIO_RANGE[0] * near_max)
    candidates, _ = find_peaks(pos_net, distance=3, height=ghost_bar)
    idx = candidates[pos_net[candidates] >= census_bar[candidates]]

    # Where the two part is *prominence*, and they part because they are asked
    # different questions (WP-1442).  A count wants every line the pattern
    # shows, so the census keeps no prominence bar and says so above.  The
    # ghost search asks whether several strong parents carry a line at one
    # ratio, and the answer is decided by how many *coincidences* the pool can
    # supply: on the demo notebook's Kapton-hump pattern the 291 candidates
    # here let a made-up wavelength gather 6 supporting parents, and 5 of the
    # 16 bundled fixtures did the same — over ``GHOST_MIN_PARENTS``, so the
    # real wavelengths landing at 0-3 was luck rather than margin.  A genuine
    # ghost on a background is a resolved maximum with full prominence above
    # its flanking saddles; a ripple on a hump has none, which is the same
    # separation :data:`SAMPLING_PROMINENCE_SIGMA` was added for one rank down.
    # Gated, the chance consensus tops out at 4 over every fixture and the demo
    # (means 1.3 → 0.25), while an injected leak at r ≥ 0.02 still gathers 5-8.
    # Computed off the shared candidates rather than by a second ``find_peaks``,
    # since a peak's prominence is a property of the signal and not of the
    # selection it was found under.
    prominence = peak_prominences(pos_net, candidates)[0]
    ghost_idx = candidates[
        prominence >= SAMPLING_PROMINENCE_SIGMA * sigma[candidates]]

    # nested envelope fits: cubic, then cubic + 1/(2θ) air-scatter column
    design = chebyshev_design_matrix(tt, AIR_GAIN_CHEBYSHEV_TERMS, float(tt[0]),
                                     float(tt[-1]))
    coef, *_ = lapack.lstsq(design.T, env, rcond=None)
    r_cubic = env - coef @ design
    design_air = np.vstack([design, 1.0 / np.maximum(tt, 1e-3)])
    coef_air, *_ = lapack.lstsq(design_air.T, env, rcond=None)
    r_air = env - coef_air @ design_air
    rss_cubic = float(r_cubic @ r_cubic)
    air_gain = float(1.0 - (r_air @ r_air) / rss_cubic) if rss_cubic > 0 else 0.0
    hump = float(np.sqrt(np.mean(r_air ** 2)) / max(med_env, 1e-12))

    # Which searches ran is recorded beside the flags, because an empty list of
    # flags reads the same for "looked, and clean" and "never looked".
    searches: tuple[str, ...] = ()
    flags: list[ContaminationFlag] = []
    if wavelength is not None and len(ghost_idx):
        searches = _searches_run(wavelength, source)
        flags = _contamination_flags(tt, net, sigma, ghost_idx, wavelength,
                                     source=source)

    lam = (select_arpls_lambda(data).selected if baseline_lambda is None
           else baseline_lambda)

    # the same envelope and net signal this function already computed, so the
    # sampling number is measured on exactly the pattern reported above
    steps, n_measured = _median_steps_per_fwhm(net, sigma)

    # ``data.sigma is not None`` is the σ-measured test at this rank — the
    # PatternData-level peer of ``DataRef.has_sigma``, and the same branch
    # ``sig()`` itself takes.  Passing ``sigma`` unconditionally would hand the
    # Poisson fallback to a measure that reads it as a flat answer.
    coverage, plateau = counting_coverage(
        tt, y, sigma if data.sigma is not None else None)

    return PatternDiagnostics(
        n_points=len(tt),
        two_theta_min=float(tt[0]), two_theta_max=float(tt[-1]),
        baseline_lambda=float(lam),
        noise_sigma_median=float(np.median(sigma)),
        peak_fraction=float(np.mean(peak_channels)),
        n_peaks=int(len(idx)),
        peak_density_per_deg=float(len(idx) / max(span, 1e-12)),
        signal_to_background=float(np.percentile(net, 99.9) / max(med_env, 1e-12)),
        amorphous_hump_score=hump,
        air_scatter_gain=max(air_gain, 0.0),
        steps_per_fwhm=steps,
        n_peaks_measured=n_measured,
        contamination=flags,
        contamination_searches=list(searches),
        coverage_plateau=plateau,
        coverage_regions=coverage,
        signal_cutoffs=cutoffs,
        dead_channels=dead,
    )


def ghost_searches(source: object | None) -> tuple[str, ...]:
    """Which ghost searches a declared source leaves worth running (WP-1445).

    ``source`` is an :class:`~rietx.schemas.instrument.Source` or
    ``NeutronSource``, or ``None`` for a caller with none to give.  ``None`` and
    an undeclared X-ray source (``kbeta is None``) get both searches, which is
    what the screen did before the optics could be declared.  Anything less is
    a **skip**, and a skip is the same kind of silence as
    :func:`identify_anode`'s ``None``: not checked, never clean.

    * neutron: both skipped, since neither a Kβ nor a tungsten line is in the
      beam; ``identify_anode`` matches on wavelength alone and called a 1.5404 Å
      neutron pattern ``"CuKa"``.
    * ``kbeta="monochromator"``: both skipped (WP-1442 measured that neither
      reaches the detector behind one).
    * ``kbeta="filter"`` and ``"mirror"``: both kept.  A skip would discard
      real detections: an image injected into corundum and zincite at
      r = 0.14, 0.10, 0.05 and 0.02 was flagged at every rung (6-8 lines,
      WP-1445), so a leak past a working filter is findable.  Narrowing the
      ceiling needs a filtered-leak ratio this tree has no measurement of.
    """
    if source is None:
        return ("kbeta", "tungsten_la")
    if getattr(source, "kind", None) != "xray_cw":
        return ()
    kbeta = getattr(source, "kbeta", None)
    if kbeta == "monochromator":
        return ()
    return ("kbeta", "tungsten_la")


def identify_anode(wavelength: float) -> str | None:
    """The anode whose Kα1 this wavelength is, or ``None``.

    ``None`` means "not a tabulated characteristic wavelength" — synchrotron,
    an anode we do not carry, or a Kα2-referenced pattern.  Callers must treat
    it as *not checked*, never as *clean*.
    """
    from ..schemas.instrument import _KA_DOUBLETS

    for name, (ka1, _) in _KA_DOUBLETS.items():
        if abs(wavelength - ka1) <= _ANODE_MATCH_TOL:
            return name
    return None


def _searches_run(wavelength: float, source: object | None) -> tuple[str, ...]:
    """The ghost searches the screen runs at ``wavelength``: those
    :func:`ghost_searches` leaves for ``source``, and none when
    :func:`identify_anode` names no anode.  One decision, read by the screen
    and recorded by :func:`diagnose` as ``contamination_searches``."""
    return ghost_searches(source) if identify_anode(wavelength) is not None else ()


def contamination_flags_from_peaks(
    two_theta: np.ndarray, intensity: np.ndarray,
    two_theta_esd: np.ndarray | None, wavelength: float, *,
    intensity_esd: np.ndarray | None = None,
    tt_range: tuple[float, float] | None = None,
    tol_deg: float = GHOST_TOL_DEG, k_sigma: float = GHOST_MATCH_K,
    source: object | None = None,
) -> list[ContaminationFlag]:
    """Ghost lines at the Kβ / W Lα positions of the strongest lines in a
    **peak list** — the one implementation of the ghost rule in this package.

    Same d-spacing, different λ:  sinθ_ghost = sinθ_parent · λ_ghost/λ_parent.
    A candidate must be a *weaker* line near the predicted position, with
    ghost/parent intensity inside :data:`GHOST_RATIO_RANGE`.

    Which ghosts are looked for follows the anode: Kβ is anode-specific, W Lα1
    is filament-derived and so applies to any of them.  An unrecognised
    wavelength yields no flags, which is a *silence*, not a clean bill — the
    caller sees the same empty list either way, and that asymmetry is why
    every anode this package can build a source for has a Kβ entry.

    Two arguments are optional because the two callers know different things.
    ``two_theta_esd`` is the per-line **position** esd; when given, the matching
    window becomes ``max(tol_deg, k_sigma·√(σ_ghost² + σ_parent²))`` — see
    :data:`GHOST_TOL_DEG` for why σ can only widen it.  ``intensity_esd``
    switches on a ``intensity > 5σ`` significance test, which a fitted peak list
    does not need (its lines cleared a σ-normalised detection threshold already)
    but a raw channel-index census does.  ``intensity`` should be an
    *integrated* intensity where one exists; net height is a fallback that
    biases the ratio test by the ghost/parent width ratio.

    The finding is **joint**: see :data:`GHOST_MIN_PARENTS` for why a single
    match is no evidence and what the bar was measured against.  An empty list
    therefore means "no leak this rule can see", which on a pattern with fewer
    than :data:`GHOST_MIN_PARENTS` parents in range is a silence rather than a
    clean bill, exactly as an unrecognised wavelength is.
    """
    searches = _searches_run(wavelength, source)
    anode = identify_anode(wavelength)
    if anode is None or not searches:
        return []
    tt = np.asarray(two_theta, dtype=np.float64)
    inten = np.asarray(intensity, dtype=np.float64)
    if not len(tt):
        return []
    lo, hi = (float(tt.min()), float(tt.max())) if tt_range is None else tt_range
    esd = None if two_theta_esd is None else np.asarray(two_theta_esd, dtype=np.float64)
    flags: list[ContaminationFlag] = []
    for kind, lam_ghost in (("kbeta", _KBETA[anode]), ("tungsten_la", _W_LA1)):
        if kind not in searches:
            continue
        cands, n_searched = _ghost_candidates(
            tt, inten, esd, intensity_esd, lam_ghost / wavelength, lo, hi,
            tol_deg=tol_deg, k_sigma=k_sigma)
        support, leak, chosen = _ghost_consensus(cands)
        if support < GHOST_MIN_PARENTS:
            continue
        # One flag per ghost *line*.  The consensus is keyed on parents, and two
        # of them can predict the same line: a Kα1/Kα2 pair fitted as two lines
        # put their Kβ images 0.04° apart, inside any matching window, and the
        # pre-WP-1442 rule flagged that line once per parent (cpd-1b 31.716°,
        # cpd-4 33.737°).  The count of *parents* is the evidence and stays on
        # every flag; the list is per line because ``usable()`` drops lines.
        # Keep the entry whose ratio is nearest the finding's, so the flag a
        # reader sees is the one the leak was fitted from.
        per_line: dict[int, tuple[int, int, float]] = {}
        for cand in chosen:
            ig = cand[1]
            if (ig not in per_line
                    or abs(np.log(cand[2] / leak))
                    < abs(np.log(per_line[ig][2] / leak))):
                per_line[ig] = cand
        for ip, ig, r in sorted(per_line.values(), key=lambda c: c[1]):
            flags.append(ContaminationFlag(
                kind=kind, two_theta=float(tt[ig]),
                parent_two_theta=float(tt[ip]), intensity_ratio=r,
                leak_ratio=leak, n_parents=support,
                n_parents_searched=n_searched))
    return flags


def _ghost_candidates(
    tt: np.ndarray, inten: np.ndarray, esd: np.ndarray | None,
    intensity_esd: np.ndarray | None, ratio: float, lo: float, hi: float,
    *, tol_deg: float, k_sigma: float,
) -> tuple[list[tuple[int, int, float]], int]:
    """Every ``(parent, ghost, ratio)`` the position and ratio windows admit.

    Returns them with the number of parents whose predicted ghost position fell
    inside the pattern — the denominator the consensus count is read against,
    and not the same as :data:`GHOST_N_PARENTS` on a pattern whose range cuts
    some of the predictions off.

    A line whose position esd exceeds :data:`GHOST_ESD_MAX_DEG` is dropped
    before anything else, as a parent and as a candidate, so the ranking that
    picks the parents is over lines that have a position at all.
    """
    r_lo, r_hi = GHOST_RATIO_RANGE
    out: list[tuple[int, int, float]] = []
    n_searched = 0
    placed = (np.ones(len(tt), dtype=bool) if esd is None
              else np.isfinite(esd) & (esd <= GHOST_ESD_MAX_DEG))
    rank = np.argsort(np.where(placed, inten, -np.inf))[::-1][:GHOST_N_PARENTS]
    for ip in rank:
        if not placed[ip]:
            continue
        s = np.sin(np.radians(tt[ip] / 2.0)) * ratio
        if s >= 1.0:
            continue
        tt_ghost = 2.0 * np.degrees(np.arcsin(s))
        if not (lo <= tt_ghost <= hi):
            continue
        n_searched += 1
        if esd is None:
            window = np.full(len(tt), tol_deg)
        else:
            window = np.maximum(
                tol_deg, k_sigma * np.sqrt(esd ** 2 + esd[ip] ** 2))
        for ig in np.flatnonzero(placed & (np.abs(tt - tt_ghost) < window)):
            r = float(inten[ig] / max(inten[ip], 1e-12))
            if not (r_lo < r < r_hi):
                continue
            if (intensity_esd is not None
                    and inten[ig] <= 5.0 * intensity_esd[ig]):
                continue
            out.append((int(ip), int(ig), r))
    return out, n_searched


def _ghost_consensus(
    cands: list[tuple[int, int, float]],
) -> tuple[int, float, list[tuple[int, int, float]]]:
    """The ratio the most **distinct parents** support, within a factor.

    Parents rather than ghost lines, because the question is how many
    *independent* reflections agree, and one parent with several in-window
    candidates would otherwise supply its own corroboration.

    That is an argument rather than a measurement, and the measurement does not
    decide it: against the control :data:`GHOST_MIN_PARENTS` describes, both
    rules separate cleanly (parent-counted, control maximum 4 against an
    injection minimum of 6 at r = 0.10; ghost-counted, 3 against 5).  An
    earlier note here claimed the ghost-counted statistic overlapped its own
    control; that was measured against a control contaminated near λ(Kα1) and
    is withdrawn.  Parents are kept on the independence argument alone
    (decided 2026-09-22; WP-1442).

    The returned list holds one candidate per supporting parent, the one whose
    ratio is nearest the consensus, so a caller emitting one flag per entry
    cannot report the same parent twice.
    """
    best: tuple[int, float, list[tuple[int, int, float]]] = (0, 0.0, [])
    for seed in cands:
        lo, hi = seed[2] / GHOST_RATIO_TOL, seed[2] * GHOST_RATIO_TOL
        keep = [c for c in cands if lo <= c[2] <= hi]
        n = len({c[0] for c in keep})
        if n <= best[0]:
            continue
        per: dict[int, tuple[int, int, float]] = {}
        for c in keep:
            if (c[0] not in per
                    or abs(np.log(c[2] / seed[2]))
                    < abs(np.log(per[c[0]][2] / seed[2]))):
                per[c[0]] = c
        chosen = sorted(per.values(), key=lambda c: c[1])
        best = (n, float(np.median([c[2] for c in chosen])), chosen)
    return best


def _contamination_flags(tt: np.ndarray, net: np.ndarray, sigma: np.ndarray,
                         peak_idx: np.ndarray, wavelength: float,
                         *, tol_deg: float = GHOST_TOL_DEG,
                         source: object | None = None
                         ) -> list[ContaminationFlag]:
    """Channel-index view of :func:`contamination_flags_from_peaks`.

    This is the pre-WP-1018 surface, kept because :func:`diagnose` works from
    ``find_peaks`` channel indices and has neither a fitted position esd nor an
    integrated intensity: it passes net height for both the ranking and the
    ratio test, and no σ(2θ), so the window is the flat ``tol_deg``.
    """
    return contamination_flags_from_peaks(
        tt[peak_idx], net[peak_idx], None, wavelength,
        intensity_esd=sigma[peak_idx], tt_range=(float(tt[0]), float(tt[-1])),
        tol_deg=tol_deg, source=source)
