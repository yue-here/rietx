"""``Refinement.profile_interval()`` result schemas and constants (WP-1929).

A row on its bound keeps its value and its marginal esd and is flagged
(``RefinedParameter.at_bound``), but a Wald esd is not a confidence interval
there: the estimate has no symmetric sampling distribution on the boundary of
the parameter space (Self & Liang, 1987, J. Am. Statist. Assoc. 82, 605).  The
profile interval is the number such a row can carry (Venzon & Moolgavkar, 1988,
Appl. Statist. 37, 87): pin the parameter, refit the rest, and read where the
data's χ² has risen by a threshold.  It answers for an interior row too, where
it shows what the esd's symmetric ± hides.

Constants live beside the models they gate, as in ``schemas/fraction.py``, so
the serialized interval explains its own search.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Base

#: The confidence level a profile interval is drawn at unless the caller says
#: otherwise.  The level is the choice and the Δχ² follows from it: 3.84 for a
#: two-sided interval at 95 %, 2.71 for a one-sided one.
PARAMETER_INTERVAL_LEVEL = 0.95

#: How many refits one side of the interval may spend before it stops and says
#: so.  Measured, a side costs 6-10 refits on the synthetic fixture
#: (``tests/test_parameter_interval.py``) and 14-30 on the BT-1 neutron fit,
#: two refits a probe at least, since the second is what says the first had
#: settled (:data:`PARAMETER_INTERVAL_SETTLE_RUNS`).  The default is twice the
#: most a side has measured.
PARAMETER_INTERVAL_MAX_REFITS = 60

#: The most refits one pinned value may take to settle.  A stage freezes its
#: peak windows at compile (root CLAUDE.md, frozen-per-stage discreteness), so
#: a refit in which a width moves far ends on windows sized for where it
#: started, and a second refit at the same pinned value recompiles them.
#: Measured on BT-1 with ``profile.x`` pinned one esd below the fit: Δχ² 28.3
#: after one refit and 16.9 after two, against a threshold of 30.3.  A probe
#: refits again while χ² falls by more than
#: :data:`PARAMETER_INTERVAL_CHI2_TOL` of the threshold, and keeps the lowest
#: χ² it reached.  Four, because a scan of 22 pinned values on BT-1 stopped
#: falling within three refits at every one, and the two intervals there used
#: the fourth only on a probe a whole esd from where its refit started.  At
#: some values the windows alternate between two compiles 0.2-3 χ² apart
#: however many refits run, which is where an end's own precision on that fit
#: stops.
PARAMETER_INTERVAL_SETTLE_RUNS = 4

#: The tolerance an interval's end is solved to, in units of the fit's esd for
#: the row.  An end is quoted to two significant figures of the esd at most,
#: so a thousandth of it is below anything a reader can see, and it moves the
#: Δχ² at the end by about 0.1 % of the threshold.
PARAMETER_INTERVAL_XTOL = 1e-3

#: The factor each probe's distance from the fit grows by while one side looks
#: for a value past the Δχ² threshold, starting one esd out.  Doubling brackets
#: an end within log₂ of its distance in esds, then the end is solved inside
#: the bracket.  Where window recompiles give the profile several crossings,
#: the growth can decide which one the bracket holds.  No stated source.
PARAMETER_INTERVAL_BRACKET_GROWTH = 2.0

#: A χ² difference the interval treats as nothing, as a fraction of the Δχ²
#: threshold.  It decides two things: whether a probe has settled
#: (:data:`PARAMETER_INTERVAL_SETTLE_RUNS`), and whether a probe that landed
#: below the fit's χ² says the fit was not at its minimum along the path.
#: **Chosen, not measured**: a minimum lower by δ moves each end by about
#: δ/(2·threshold) of its distance from the fit, so 1 % of the threshold is
#: half a percent of the interval.  A refit converging to its own ftol lands a
#: few parts in 10⁹ of χ² from the fit, far inside it.
PARAMETER_INTERVAL_CHI2_TOL = 0.01

#: Why one side of the interval stopped.  ``"threshold"``: the data's χ² rose
#: by the threshold, and the end is that root.  ``"bound"``: the side reached
#: the parameter's own limit first, so the end is the limit; a one-sided
#: interval's bounded end always reads this.  ``"refits"``: the side spent
#: its refit budget before it could say either, and has no end.
#: ``"error"``: a refit raised, and the side has no end.  ``"period"``: a
#: moment angle's side reached half a turn from the value with the χ² still
#: under the threshold, and has no end: an angle repeats every 2π, so past
#: half a turn the side only revisits directions the other side covers
#: (WP-2002; a flat azimuth, or a moment the data no longer see).
IntervalStop = Literal["threshold", "bound", "refits", "error", "period"]


class ParameterIntervalPoint(Base):
    """One pinned value and the lowest data χ² its refits reached there.

    ``chi2`` is the data's own Σ w·Δ², never the reduced figure, and
    ``delta_chi2`` is measured from :attr:`ParameterInterval.chi2_fit`, so it
    is negative where a probe found a lower χ² than the fit.  ``runs`` is how
    many refits the value took to settle
    (:data:`PARAMETER_INTERVAL_SETTLE_RUNS`), and ``status`` and ``node_id``
    belong to the one that reached ``chi2``; ``node_id`` is ``None`` where the
    refits recorded no node: the caller disabled history, or the interval is
    one a fit computed unasked (``RefinedParameter.interval``, WP-2002).  A
    refit that raised records ``error``, and the
    numbers stay ``None`` when it was the first.
    """

    value: float
    runs: int
    chi2: float | None = None
    delta_chi2: float | None = None
    status: str | None = None
    error: str | None = None
    node_id: str | None = None


class ParameterInterval(Base):
    """The profile interval for one refined parameter.

    ``value``, ``stderr`` and ``at_bound`` are the caller's last fit, copied so
    the interval reads on its own.  ``stderr`` is ``None`` for a moment angle
    the fit's covariance left out at a direction the symmetry fixes
    (``StageResult.moment_angle_tests``, WP-1929), whose profile steps from
    the half-width that record carries instead.  ``one_sided`` is ``True`` exactly when
    ``at_bound`` is: the bound is one end, and the other is where the data's
    χ² has risen by ``delta_chi2_cut``.  That threshold is ``quantile`` × χ²_red
    × f², f the fit's ``esd_inflation``, with ``quantile`` the χ²₁ point at
    ``level`` for a two-sided interval and at 2·``level`` − 1 for a one-sided
    one (3.84 and 2.71 at 95 %).

    ``lower`` and ``upper`` are the ends, and ``lower_stop`` and
    ``upper_stop`` say why each side stopped (:data:`IntervalStop`).  An end
    is ``None`` when its side stopped on ``"refits"``, ``"error"`` or ``"period"``.

    ``chi2_lowest`` is the lowest data χ² found, the fit's included.
    ``fit_is_minimum`` is ``False`` when a probe found χ² below the fit's by
    more than :data:`PARAMETER_INTERVAL_CHI2_TOL` of the threshold, which says
    the fit did not reach the minimum along this path and the ends, measured
    from the fit, are too wide.  ``points`` holds one row per pinned value in
    the order they ran, and ``n_refits`` is the refits they took, the sum of
    their ``runs``.
    """

    path: str
    value: float
    stderr: float | None
    at_bound: bool | None
    level: float
    one_sided: bool
    quantile: float
    delta_chi2_cut: float
    lower: float | None
    upper: float | None
    lower_stop: IntervalStop
    upper_stop: IntervalStop
    chi2_fit: float
    chi2_lowest: float
    fit_is_minimum: bool
    points: list[ParameterIntervalPoint] = Field(default_factory=list)
    n_refits: int
