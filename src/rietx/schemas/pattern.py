"""Measured powder pattern container.

**One pattern, one abscissa, and the abscissa says which one it is.**  A
constant-wavelength measurement puts an angle on the x axis; a time-of-flight
neutron measurement (ISIS, SNS, LANSCE) puts a flight time in microseconds
there, and the two are not convertible without a per-bank calibration the
pattern does not carry.  So :class:`PatternData` holds ``two_theta`` **or**
``tof`` and never both, and every consumer asks which it has rather than
assuming — see :func:`require_two_theta`, which is how a 2θ-only path says no.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, model_validator

from .common import Base

#: The two abscissae a pattern may carry, spelled as the field that holds each.
AxisKind = Literal["two_theta", "tof"]

#: What each axis is measured in, for a message that has to name the unit.
AXIS_UNITS: dict[str, str] = {"two_theta": "degrees", "tof": "microseconds (µs)"}


#: The count under which the Poisson fallback stops falling: σ = √max(y, 1),
#: so a channel that counted zero is weighted as one count, as TOPAS weights
#: a file without esds, 1/Max(Yobs, 1) (Technical Reference § 6.2).
POISSON_FLOOR_COUNTS = 1.0

#: What a channel whose stated σ is zero or negative becomes (WP-1952, WP-2002
#: B5).  ``"exclude"``: it takes no weight, leaving the fit as an excluded
#: channel does, the rule GSAS-II's fxye reader applies to σ ≤ 0.  ``"poisson"``:
#: it is weighted by the Poisson fallback √max(y, 1), one count at a zero count,
#: for a file that wrote σ = √0 for a channel that counted nothing.
NonPositiveSigma = Literal["exclude", "poisson"]


def _poisson_where_nonpositive(s: np.ndarray, y: np.ndarray) -> np.ndarray:
    """``s``, with every entry that is not positive replaced by √max(y, 1).

    An esd of zero claims an exact intensity and a negative one has no meaning,
    so neither is a weight.  Under ``nonpositive_sigma="exclude"`` these
    channels leave the fit (:meth:`PatternData.in_range_mask`) and the value
    here is a placeholder no residual reads; it keeps every whole-pattern
    consumer finite.  Under ``"poisson"`` it is the weight.  It replaced a floor
    at a thousandth of the column's median esd, which gave such a channel about
    a million times its neighbours' weight (#650, #897).

    One rule for :meth:`PatternData.sig` and
    :meth:`~rietx.schemas.results.RefinementResult.sig`, so the two cannot
    drift apart.
    """
    return np.where(s > 0, s, np.sqrt(np.maximum(y, POISSON_FLOOR_COUNTS)))


class SigmaRule(Base):
    """Which σ rule weighted the channels a fit took, and on how many (WP-1952).

    WP-2002's B14 asked for it: by the time a result exists, a file's esd and a
    Poisson estimate are the same array of floats, so the rule that produced
    each has to be recorded where it fired.  ``n_file_sigma + n_poisson_sigma``
    is the fit's channel count.  Built by :meth:`PatternData.sigma_rule`, the
    authority on both the rule and the mask.
    """

    #: fitted channels weighted by the file's own σ
    n_file_sigma: int
    #: fitted channels weighted by the Poisson fallback √max(y, 1): every one
    #: when the pattern carries no σ, else the σ ≤ 0 channels a caller kept
    #: with ``nonpositive_sigma="poisson"``
    n_poisson_sigma: int
    #: channels inside the fitted range whose σ is zero or negative and which
    #: left the fit under ``nonpositive_sigma="exclude"``
    n_nonpositive_excluded: int


class PatternData(Base):
    """A powder pattern.

    Its abscissa is 2θ **or** a time of flight, never both.  Numbers out: ``x()``, ``y()``, ``sig()`` — numpy views of the abscissa,
    intensity and per-point σ; the fields themselves stay plain lists so the
    model round-trips through JSON.  ``tt()`` and ``tof_us()`` are the *typed*
    views: each returns the axis it names and **raises** on the other one, so a
    path that can only do trigonometry says so at the boundary instead of
    computing an angle from a microsecond.

    ``sigma`` is the per-point standard deviation of the intensity.  When it is
    absent the refinement assumes raw Poisson counting statistics,
    σᵢ = √max(yᵢ, 1) — which is *invalid* for normalised/merged/smoothed data;
    readers populate ``sigma`` from the file whenever the format carries it
    (e.g. the third column of ``.xye`` / GSAS ESD files).

    **The axis is a declaration, never an inference.**  A TOF range of
    1000-10000 µs is a perfectly plausible 10-100° scan and passes every
    monotonicity check an angle passes, so which quantity is on the x axis is
    settled by *which field a reader filled in* and by nothing else.
    """

    #: 2θ in degrees, strictly increasing.  ``None`` on a time-of-flight
    #: pattern — exactly one of this and :attr:`tof` is set.
    two_theta: list[float] | None = None
    #: Flight time in microseconds, strictly increasing.  ``None`` on a
    #: constant-wavelength pattern.  Converting it to a d-spacing needs the
    #: bank's DIFC/DIFA/TZERO/DIFB, which live on the *instrument*
    #: (:class:`rietx.schemas.instrument.TOFSource`) and not here: one file can
    #: hold several banks of the same flight times against different constants.
    tof: list[float] | None = None
    intensity: list[float]
    sigma: list[float] | None = None
    #: What a channel whose ``sigma`` is zero or negative becomes:
    #: :data:`NonPositiveSigma`.  The values stay the file's; this field says
    #: how they are weighted.  The ``nonpositive_sigma`` reader option sets it.
    nonpositive_sigma: NonPositiveSigma = "exclude"
    excluded_regions: list[tuple[float, float]] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> "PatternData":
        if (self.two_theta is None) == (self.tof is None):
            both = self.two_theta is not None
            raise ValueError(
                "a pattern carries exactly one abscissa: set two_theta (an "
                "angle in degrees) or tof (a flight time in microseconds), "
                + ("not both — the two are related by a per-bank DIFC/DIFA/"
                   "TZERO/DIFB calibration this container does not hold, so a "
                   "pattern claiming both would be claiming a conversion "
                   "nobody checked" if both else "and neither was given"))
        axis = self.axis
        x = self.two_theta if axis == "two_theta" else self.tof
        assert x is not None  # settled above; narrows the type
        n = len(x)
        if n < 2:
            raise ValueError("pattern needs at least 2 points")
        if len(self.intensity) != n:
            raise ValueError(f"{axis} and intensity differ in length")
        if self.sigma is not None and len(self.sigma) != n:
            raise ValueError(f"sigma length does not match {axis}")
        arr = np.asarray(x)
        if not np.all(np.diff(arr) > 0):
            raise ValueError(f"{axis} must be strictly increasing")
        # The project document's refusal, in its words (WP-1033). Unchecked
        # here, an inverted region masked nothing and said so nowhere (WP-1986).
        from .project import check_interval

        for lo, hi in self.excluded_regions:
            check_interval("an excluded region", lo, hi)
        # Every check above is about a *column* and holds for either quantity,
        # which is why they are written once and only their wording is per-axis.
        # A check about the quantity itself belongs in a branch on ``axis`` and
        # nowhere else: WP-1332 proposes a [0, 180] plausibility bound on the
        # axis a reader hands back, and a flight time in µs violates it by
        # construction, so when that lands it goes under
        # ``if axis == "two_theta"`` here rather than beside the three above.
        return self

    # -- the axis ----------------------------------------------------------
    @property
    def axis(self) -> AxisKind:
        """Which abscissa this pattern carries — the discriminator.

        Read off which field is set, so it cannot drift from the data.  A
        consumer that only works in one of them tests *this* and never the
        values: an ascending column is ascending in either quantity.
        """
        return "two_theta" if self.two_theta is not None else "tof"

    @property
    def axis_unit(self) -> str:
        """The unit :attr:`axis` is measured in, for messages and axis labels."""
        return AXIS_UNITS[self.axis]

    # -- numpy views -------------------------------------------------------
    def x(self) -> np.ndarray:
        """Whichever abscissa is set — the axis-blind view.

        For code that windows, masks, crops, plots or counts channels, where
        the quantity does not matter.  Anything that does *arithmetic* on the
        axis wants :meth:`tt` or :meth:`tof_us` instead, so that the wrong one
        raises rather than returning plausible nonsense.
        """
        arr = self.two_theta if self.two_theta is not None else self.tof
        return np.asarray(arr, dtype=np.float64)

    def tt(self) -> np.ndarray:
        """2θ in degrees, or an authored refusal on a time-of-flight pattern."""
        if self.two_theta is None:
            raise ValueError(
                "this pattern's abscissa is a time of flight in microseconds, "
                "not 2θ in degrees, and tt() is a 2θ-only accessor: the caller "
                "reached for an angle on a pattern that has none. Time and "
                "angle are related by the bank's DIFC/DIFA/TZERO/DIFB, which "
                "live on the instrument's neutron_tof source — use x() for the "
                "axis as measured, or tof_us() to say so explicitly.")
        return np.asarray(self.two_theta, dtype=np.float64)

    def tof_us(self) -> np.ndarray:
        """Flight time in µs, or an authored refusal on a 2θ pattern."""
        if self.tof is None:
            raise ValueError(
                "this pattern's abscissa is 2θ in degrees, not a time of "
                "flight: tof_us() is a time-of-flight-only accessor. Use tt() "
                "for the angle, or x() for the axis as measured.")
        return np.asarray(self.tof, dtype=np.float64)

    def y(self) -> np.ndarray:
        return np.asarray(self.intensity, dtype=np.float64)

    def sig(self) -> np.ndarray:
        """Per-point σ, applying the Poisson fallback where needed.

        A stated σ that is zero or negative comes back as √max(y, 1)
        (:func:`_poisson_where_nonpositive`): the weight under
        ``nonpositive_sigma="poisson"``, a placeholder the fit never reads under
        ``"exclude"``.
        """
        y = self.y()
        if self.sigma is not None:
            return _poisson_where_nonpositive(
                np.asarray(self.sigma, dtype=np.float64), y)
        return np.sqrt(np.maximum(y, POISSON_FLOOR_COUNTS))

    def nonpositive_sigma_mask(self) -> np.ndarray:
        """True per channel whose stated σ is zero or negative; all False when
        the pattern carries no σ.

        Written as "not positive", the test :func:`_poisson_where_nonpositive`
        replaces by, so a channel :meth:`sig` does not weight by the file's σ
        is never counted as the file's in :meth:`sigma_rule`."""
        if self.sigma is None:
            return np.zeros(len(self.intensity), dtype=bool)
        return ~(np.asarray(self.sigma, dtype=np.float64) > 0)

    def in_range_mask(self) -> np.ndarray:
        """True for points kept in the fit: excluded_regions removed, and under
        ``nonpositive_sigma="exclude"`` every channel whose σ is zero or
        negative (WP-1952), since such a σ states no weight.

        On the axis as measured: an excluded region is a span of *channels*, so
        it is quoted in whatever the abscissa is — degrees on a CW pattern,
        microseconds on a TOF one.
        """
        mask = self._region_mask()
        if self.nonpositive_sigma == "exclude":
            mask &= ~self.nonpositive_sigma_mask()
        return mask

    def _region_mask(self) -> np.ndarray:
        """``in_range_mask`` before the σ rule: the excluded regions alone."""
        from .project import check_interval

        x = self.x()
        mask = np.ones(x.shape, dtype=bool)
        for lo, hi in self.excluded_regions:
            # again here: ``excluded_regions.append(...)`` reaches no validator
            check_interval("an excluded region", lo, hi)
            mask &= ~((x >= lo) & (x <= hi))
        return mask

    def sigma_rule(self, within: np.ndarray | None = None) -> SigmaRule:
        """Which σ rule weights the channels a fit takes, counted
        (:class:`SigmaRule`).

        ``within`` is the fit's own window over the channels (a
        ``two_theta_limits`` cut), ``None`` for the whole pattern.  It is
        intersected with the excluded regions here, so the counts are the
        fit's: ``compile_model`` asks this with the same window it cuts by.
        """
        regions = self._region_mask()
        if within is not None:
            regions &= np.asarray(within, dtype=bool)
        nonpos = self.nonpositive_sigma_mask() & regions
        n_in = int(regions.sum())
        n_nonpos = int(nonpos.sum())
        if self.sigma is None:
            return SigmaRule(n_file_sigma=0, n_poisson_sigma=n_in,
                             n_nonpositive_excluded=0)
        if self.nonpositive_sigma == "poisson":
            return SigmaRule(n_file_sigma=n_in - n_nonpos,
                             n_poisson_sigma=n_nonpos, n_nonpositive_excluded=0)
        return SigmaRule(n_file_sigma=n_in - n_nonpos, n_poisson_sigma=0,
                         n_nonpositive_excluded=n_nonpos)

    def __str__(self) -> str:
        """The range and step on one line, then what was measured beside it
        (WP-1544). ``sigma: None`` and an empty ``excluded_regions`` are printed,
        because whether the file carried σ decides the weights."""
        from .._display import tree
        # Through ``x()``, not ``tt()``: printing a bank is the first thing a
        # caller does with one, and ``tt()`` refuses a flight-time axis.
        x = self.x()
        if self.axis == "two_theta":
            span, step_unit = f"{x[0]:g}–{x[-1]:g}° 2θ", "°"
        else:
            span, step_unit = f"{x[0]:g}–{x[-1]:g} µs time of flight", " µs"
        head = (f"PatternData of {x.size} points, {span}, "
                f"median step {float(np.median(np.diff(x))):.4g}{step_unit}")
        return tree(self, order=("intensity", "sigma", "excluded_regions", "metadata"),
                    show_empty=True, head=head)

    def plot(self, path: str | None = None, **kw):
        """Draw the pattern: :func:`rietx.viz.plots.plot_pattern`, the peer of
        :meth:`RefinementResult.plot`, forwarding ``**kw``; ``model=ref`` adds a
        :class:`~rietx.Refinement`'s reflection ticks and starting background
        before any fit, and names its radiation on the 2θ label."""
        from ..viz.plots import plot_pattern

        return plot_pattern(self, path=path, **kw)

    def crop(self, lo: float, hi: float) -> "PatternData":
        """The sub-pattern between ``lo`` and ``hi`` **on the axis as measured**.

        The axis kind is preserved: cropping a TOF pattern returns a TOF
        pattern, which is why the bounds are in µs there and in degrees here.
        """
        x = self.x()
        keep = (x >= lo) & (x <= hi)
        kept = x[keep].tolist()
        return PatternData(
            two_theta=kept if self.axis == "two_theta" else None,
            tof=kept if self.axis == "tof" else None,
            intensity=self.y()[keep].tolist(),
            sigma=None if self.sigma is None else np.asarray(self.sigma)[keep].tolist(),
            nonpositive_sigma=self.nonpositive_sigma,
            excluded_regions=self.excluded_regions,
            metadata=self.metadata,
        )


def require_two_theta(pattern: PatternData | None, where: str, *,
                      instrument: object | None = None) -> None:
    """Refuse a time-of-flight pattern at a 2θ-only entry point, in words.

    **One helper, called at the boundary**, rather than a check per consumer:
    most modules of this package assume the abscissa is an angle, and what a
    user must not see is the *consequence* of that assumption — an ``arcsin``
    of a number in the thousands, a "2θ outside [0, 180]" complaint about a
    flight time, or a cell refined from microseconds read as degrees.  Those
    are all plausible-looking wrong answers, and the axis is exactly the kind
    of fact a reader established and a consumer must not re-derive.

    ``where`` names the entry point the caller actually used, so the message
    says which door closed rather than pointing at an internal function.
    ``instrument`` is checked too when given: a ``neutron_tof`` source on a 2θ
    pattern is the same mistake seen from the other side, and it would
    otherwise surface as an ``AttributeError`` for a wavelength the source does
    not have.  A caller with no pattern in hand passes ``pattern=None`` and
    gets the instrument arm alone.

    **In this build every entry that computes a pattern is 2θ-only**: a
    time-of-flight bank is read (:mod:`rietx.io.instrument_tof`, the GSAS and
    Mantid pattern readers) and has a parameter table, and no forward model
    for it exists yet.  So the refusal says what *is* available — the
    readers — rather than pointing at a route that is not there.
    """
    kind = getattr(getattr(instrument, "source", None), "kind", None)
    axis = "two_theta" if pattern is None else pattern.axis
    if axis == "two_theta" and kind != "neutron_tof":
        return
    if axis == "tof":
        what = ("this pattern's abscissa is a time of flight in microseconds, "
                "not 2θ in degrees")
    else:
        seen = ("while the pattern is in 2θ degrees" if pattern is not None
                else "and this entry point has no time-of-flight path")
        what = ("this instrument's source is a neutron_tof bank, whose peak "
                f"positions are flight times in microseconds, {seen}")
    raise ValueError(
        f"{where}: {what}. Every position, width, Lorentz, absorption and "
        f"extinction term reached from here is a function of an angle, so "
        f"running it on a flight time would not fail — it would return a "
        f"confidently wrong answer. This build reads a time-of-flight bank "
        f"(the pattern lands on pattern.tof in µs, the calibration on "
        f"instrument.source with kind='neutron_tof') and refines none: no "
        f"flight-time forward model exists here yet, and adding one is "
        f"tracked on yue-here/rietx issue #193.")
