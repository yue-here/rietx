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


#: The floor :func:`_floor_sigma` raises a zero or negative esd to, as a
#: fraction of the column's median positive esd (#650).  Such a channel then
#: weighs about a million times its neighbours; WP-1952 replaces it with a
#: dropped channel and a reader warning (WP-2002, B5).
SIGMA_FLOOR_RELATIVE = 1e-3
#: The count under which the Poisson fallback stops falling: σ = √max(y, 1),
#: so a channel that counted zero is weighted as one count, as TOPAS weights
#: a file without esds, 1/Max(Yobs, 1) (Technical Reference § 6.2).
POISSON_FLOOR_COUNTS = 1.0


def _floor_sigma(s: np.ndarray) -> np.ndarray:
    """``s`` with zero and negative esds raised to a floor, so no channel takes
    an infinite weight.

    The floor is a thousandth of the column's median positive esd, and nothing
    else. It used to be ``max(1e-3, …)`` as well — an absolute number in
    whatever units the intensity happened to be in, which never binds on counts
    (median esd ≥ 1) and silently raised every esd of a normalised pattern,
    whose esds sit near 1e-3 and below, to 1e-3 (#650). A column with no
    positive entry has no scale to be relative to, and keeps 1.0.

    One rule for :meth:`PatternData.sig` and
    :meth:`~rietx.schemas.results.RefinementResult.sig`, so the two cannot
    drift apart.
    """
    floor = (float(np.median(s[s > 0])) * SIGMA_FLOOR_RELATIVE if np.any(s > 0)
             else 1.0)
    return np.maximum(s, floor)


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
        """Per-point σ, applying the Poisson fallback where needed."""
        if self.sigma is not None:
            return _floor_sigma(np.asarray(self.sigma, dtype=np.float64))
        y = self.y()
        return np.sqrt(np.maximum(y, POISSON_FLOOR_COUNTS))

    def in_range_mask(self) -> np.ndarray:
        """True for points kept in the fit (excluded_regions removed).

        On the axis as measured: an excluded region is a span of *channels*, so
        it is quoted in whatever the abscissa is — degrees on a CW pattern,
        microseconds on a TOF one.
        """
        from .project import check_interval

        x = self.x()
        mask = np.ones(x.shape, dtype=bool)
        for lo, hi in self.excluded_regions:
            # again here: ``excluded_regions.append(...)`` reaches no validator
            check_interval("an excluded region", lo, hi)
            mask &= ~((x >= lo) & (x <= hi))
        return mask

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
