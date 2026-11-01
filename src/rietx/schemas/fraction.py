"""``Refinement.profile_fraction()`` result schemas and gates (WP-1320).

A weight fraction's esd is the curvature of χ² where the fit stopped, so it
describes one basin.  A trace phase's scale trades against its width until its
peaks are background, and that ridge can hold several basins at one χ² (issue
#203: 1.41 ± 0.65 wt% on a pattern admitting 0 %, ~1.5 % and 98.7 % within
0.011 pp of Rwp).  The profile pins the phase's width on a grid, refits the
rest, and reports every fraction the data admits: a *range*, beside the answer
rather than inside it, with the grid carried so the range can be checked.

Constants live beside the models they gate, as in ``schemas/suggest.py``, so the
serialized profile explains its own gate.
"""

from __future__ import annotations

from pydantic import Field

from .common import Base, Diagnostic

#: The Δχ² for one parameter at 95 % (χ²₁'s 0.95 quantile, 1.96²).  The
#: confidence level is the choice; the number follows from it.  It is scaled by
#: the fit's χ²_red and the square of its Bérar-Lelann factor, the calibration
#: every reported esd already carries, so on a single quadratic basin the
#: admissible set reproduces W ± 1.96 esd (measured: the control patterns in
#: ``tests/test_qpa_multimodal.py`` land at 0.46-0.79 of that half-width).
FRACTION_PROFILE_DCHI2 = 3.84

#: The default grid, as the phase's own FWHM contribution in degrees 2θ at the
#: middle of the fitted range: 0 (instrument only), then this many values
#: spaced logarithmically from :data:`FRACTION_PROFILE_FWHM_MIN` to half the
#: fitted span.  Half, because on the whole span a pinned width outruns the
#: peak windows frozen at stage compile (``FROZEN_COMPILE_STALE`` fired at
#: 85° on the fixture's 85° range and not at 60°).  A chosen coarse grid,
#: ~2.3× per step on an 85° range: the profile is a scan, not a solve.
FRACTION_PROFILE_N_FWHM = 11

#: The smallest nonzero FWHM on the default grid, degrees 2θ — below a lab
#: instrument's own width and near a synchrotron's, so the grid starts where
#: sample broadening stops being visible at all.
FRACTION_PROFILE_FWHM_MIN = 0.01

#: The largest FWHM on the default grid, as a fraction of the fitted span in
#: degrees 2θ.  Half, because on the whole span a pinned width outruns the peak
#: windows frozen at stage compile (WP-1320; the reason above).
FRACTION_PROFILE_FWHM_MAX_SPAN = 0.5


class FractionProfilePoint(Base):
    """One pinned width and what the refit made of the fraction there.

    ``value`` is the pinned parameter in its own units; ``fwhm`` is the same
    value read as the phase's FWHM contribution at the middle of the fitted
    range, degrees 2θ, which is what makes axes of different units comparable.
    ``chi2`` is the data's own Σ w·Δ², never the reduced figure, and
    ``delta_chi2`` is measured from :attr:`FractionProfile.chi2_best`.  A refit
    that raised records ``error`` and leaves the numbers ``None``, and one whose
    scales could form no fraction records ``error`` beside its χ²: a point that
    could not be measured is absent, never admissible.
    """

    axis: str
    value: float
    fwhm: float
    admissible: bool
    weight_fraction: float | None = None
    chi2: float | None = None
    delta_chi2: float | None = None
    rwp: float | None = None
    status: str | None = None
    error: str | None = None
    node_id: str | None = None


class FractionProfile(Base):
    """Every fraction of one phase the pattern admits along its width.

    ``weight_fraction`` and ``weight_fraction_stderr`` are the caller's fit,
    copied so the profile reads on its own.  A point is **admissible** when its
    ``delta_chi2`` is at most ``delta_chi2_cut`` (:data:`FRACTION_PROFILE_DCHI2`
    × χ²_red × f², f the fit's ``esd_inflation``).  ``range_low`` and
    ``range_high`` span the admissible points and the fit itself when it is
    admissible, so they are an **inner** bound on the 95 % profile set: a
    coarser grid can only narrow them.

    ``fit_admissible`` is ``False`` when a pinned refit found χ² lower than the
    fit's by more than the cut, which says the fit did not reach the lowest
    basin along this ridge.  ``excess`` is the farthest admissible fraction
    from the fit's, in units of the esd's 95 % half-width (1.96 esd), ``None``
    where the fit carries no esd.  ``diagnostics`` holds one
    ``QPA_FRACTION_RANGE`` info record stating the range and ``excess``
    wherever ``excess`` is defined, and nothing otherwise.  Until 1.10 it held
    ``QPA_FRACTION_UNDETERMINED``, a warning only past an excess of 2, a
    number chosen rather than measured (WP-2002, B12).
    """

    phase: str
    phase_index: int
    axes: list[str]
    weight_fraction: float
    weight_fraction_stderr: float | None = None
    chi2_fit: float
    chi2_best: float
    delta_chi2_cut: float
    fit_admissible: bool
    points: list[FractionProfilePoint] = Field(default_factory=list)
    range_low: float
    range_high: float
    excess: float | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)
