"""The GUI's sequential-series surface — the setup, and the answer (WP-1016).

A series is N *separate* refinements chained by a warm start
(:mod:`rietx.sequential`), not one joint residual, and this module is where
that shape meets a session that owns exactly one project.  Three decisions carry
it, and each is a refusal to grow something.

**A series lives beside the project, not inside it.**  ``ProjectDoc.patterns``
stays length 1 and ``Project.open`` still refuses more, so the series' patterns
are staged uploads (WP-1014) held in the session, its per-pattern histories are
**in memory**, and its answer is session-scoped like ``Refinement.result_``.
That is not a shortcut: an upload token dies with the session
(``UploadStore.close``), so a *persisted* series would need a document to name
its files, which is exactly the schema growth the v1.0 GUI plan told this WP to
record for WP-1003 rather than perform.  What the project *does* supply is the
protocol — mode, plan, 2θ limits and excluded regions all come from
``project.json``, so one protocol is applied to N specimens and the series cannot
disagree with the single-pattern fit beside it about what is being fitted.

**The models come from the working state, and the settings from here.**  The
starting structure and instrument are the project's head — a series warm-starts
from whatever the user has already got right — while ``carry``/``refit``/
``direction``/``x_label`` are properties of the chain and have nowhere else to
live.  ``carry`` is a *control*, not a tuning knob (WP-0505 measured that
carrying everything costs 838 iterations against 904 for a narrower glob, with
identical Rwp), and :data:`CARRY_HELP` is that sentence where the editor can
show it.

**The disagreement between the two chains is reported as a number here, not as a
field on a diagnostic.**  ``SEQUENTIAL_PATH_DEPENDENT`` is a
:class:`~rietx.schemas.common.Diagnostic`, which carries ``where`` and no
magnitude — the wall WP-1012 hit displaying guard diagnostics per node, and left
to WP-1003 as a freeze question.  It does not need answering: the two chains'
trajectories are both in hand, so :func:`trajectories` recomputes the combined-σ
distance the same way :func:`sequential._path_dependence_diagnostics` does and
serves it per path.  A panel can then rank by disagreement without a schema
change.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

from ..schemas.pattern import PatternData
from ..schemas.sequential import SeriesResult
from ..sequential import (
    DIRECTIONS,
    PATH_DEPENDENCE_SIGMA,
    REFIT_MODES,
    _angle_difference,
    _noise_floor,
    unique_labels,
)
from .imports import UploadStore, preview_pattern

#: What the carry-glob editor says about itself.  A control for parameters that
#: provably must not chain — never a knob to tune — and the measurement is why
#: (WP-0505, quoted in ``_carry_into``'s docstring).
CARRY_HELP = (
    "dot-path globs naming which parameters cross the pattern boundary; "
    "everything else restarts from the model this series began at. Default "
    "['*'] — carry everything. Measured on the round-robin sample-1 series: "
    "carrying everything costs 838 iterations against 904 for a carry that "
    "excludes the phase scales, with identical Rwp and identical weight "
    "fractions, so this is a control for a parameter that provably must not "
    "chain, not a knob to tune."
)

#: The setting defaults, in one place so the GET before any PUT and the run agree.
#: They are WP-0505's measured results and are deliberately not re-litigated in
#: the UI: ``refit="single"`` (904 iterations against 1623 staged, same answer)
#: and carry everything.
DEFAULTS: dict[str, Any] = {
    "carry": ["*"],
    "refit": "single",
    "direction": "forward",
    "x_label": "index",
}


class SeriesRefused(ValueError):
    """A setting or a member was refused, carrying the field at fault.

    The field matters as much as the sentence: a form highlights what to retype,
    and a refusal of ``refit`` that reports ``patterns`` sends the user to the
    wrong control — the same reason ``GuiSession._edit`` extracts the offending
    dot-path from a ``ParameterTable`` refusal (WP-1035).
    """

    def __init__(self, message: str, where: str) -> None:
        super().__init__(message)
        self.where = where


@dataclass
class SeriesMember:
    """One staged pattern in series order, with what reading it revealed."""

    token: str
    path: Path
    filename: str
    label: str
    #: the series coordinate — temperature, time, pressure.  ``None`` means the
    #: pattern index is the axis, which is what ``x_label`` then says.
    x: float | None
    reader: str
    #: the **effective** reader keywords this member was read with, as strings —
    #: ``DataRef.options`` one layer up, and the same vocabulary
    #: (:data:`~rietx.io.readers.READER_OPTIONS`), because a member of a series
    #: is a pattern file like any other and may need one to read as intended.
    options: dict[str, str]
    n_points: int
    two_theta_range: tuple[float, float]
    #: whether the *file* carried esds.  Kept per member because a series whose
    #: files disagree is a weighting inconsistency (CLAUDE.md, Weights) that is
    #: invisible once every pattern is read — see :func:`setup_payload`.
    has_sigma: bool

    def as_dict(self) -> dict:
        return {"upload": self.token, "filename": self.filename,
                "label": self.label, "x": self.x, "reader": self.reader,
                "reader_options": dict(self.options), "n_points": self.n_points,
                "two_theta_range": list(self.two_theta_range),
                "has_sigma": self.has_sigma}


@dataclass
class SeriesSetup:
    """The staged series and the chain's own settings — session-scoped."""

    members: list[SeriesMember] = field(default_factory=list)
    carry: list[str] = field(default_factory=lambda: list(DEFAULTS["carry"]))
    refit: str = DEFAULTS["refit"]
    direction: str = DEFAULTS["direction"]
    x_label: str = DEFAULTS["x_label"]

    @property
    def labels(self) -> list[str]:
        return [m.label for m in self.members]

    @property
    def x(self) -> list[float] | None:
        """The series coordinate, or ``None`` when any member lacks one.

        All or nothing on purpose: ``SeriesResult.x`` falls back to the *index*
        per entry, so a half-filled coordinate would put three temperatures and
        two indices on one axis and label it with whichever the caller named.
        """
        xs = [m.x for m in self.members]
        if not xs or any(v is None for v in xs):
            return None
        return [float(v) for v in xs]

    @property
    def axis_label(self) -> str:
        """What the trajectory axis is actually called.

        ``x_label`` is a *setting* and the coordinate may be absent, and
        ``SequentialRefinement.fit`` only renames the axis in the other
        direction (a given ``x`` promotes a default ``"index"`` to ``"x"``). So a
        user who typed ``T`` and then cleared one temperature would get an axis
        of pattern indices labelled ``T`` — a trajectory whose x values mean
        something other than what the label says, which is the one thing a
        plotted axis may never do.
        """
        return self.x_label if self.x is not None else "index"


# ----------------------------------------------------------------------
# the setup
# ----------------------------------------------------------------------
def members_from(entries: Any, uploads: UploadStore,
                 known: list[SeriesMember] | None = None) -> list[SeriesMember]:
    """Resolve ``[{upload, label?, x?}, …]`` against the session's staged files.

    Every member is *read* here, not at run time, which is WP-1014's two-phase
    property applied to N files: a file that does not parse is a message about
    that file, not a series that dies half way through a chain.  The description
    comes from :func:`preview_pattern` verbatim (reader, point count, range,
    ``has_sigma``), so the series list and the import wizard cannot disagree
    about what a file is.

    ``known`` is the list this one replaces, and a member already described in it
    is **not re-read**: a staged upload is immutable (its bytes are on disk under
    a token nothing rewrites), so the reader, the point count and ``has_sigma``
    cannot have changed.  It matters because the order *is* the series — every
    reorder, every typed coordinate is a whole-list PUT — and re-reading forty
    patterns per keystroke would make the editor unusable while proving nothing.
    """
    def _key(token: str, options: dict) -> tuple:
        return (token, tuple(sorted(options.items())))

    # keyed on the *effective* options, which is also what ``as_dict`` reports:
    # the panel sends back the list it was given, so a member it did not touch
    # keys identically and is not re-read.
    cached = {_key(m.token, m.options): m for m in (known or [])}
    if not isinstance(entries, list):
        raise SeriesRefused("'patterns' must be a list of "
                            "{upload: token, label?: str, x?: number}",
                            "patterns")
    out: list[SeriesMember] = []
    raw_labels: list[str] = []
    for i, entry in enumerate(entries):
        if isinstance(entry, str):
            entry = {"upload": entry}
        if not isinstance(entry, dict):
            raise SeriesRefused(f"patterns[{i}] must be an object with an "
                                "'upload' token", f"patterns.{i}")
        token = str(entry.get("upload") or "")
        if not token:
            raise SeriesRefused(f"patterns[{i}] has no 'upload' token",
                                f"patterns.{i}.upload")
        staged = uploads.get(token, "pattern")   # UploadRefused names the token
        # an empty string is a cleared control, not a request; anything else
        # goes through untouched so that a *typo* is refused in
        # ``reader_options_for``'s words rather than silently dropped here
        requested = {k: v for k, v in (entry.get("reader_options") or {}).items()
                     if v not in (None, "")}
        x = entry.get("x")
        if x is not None:
            try:
                x = float(x)
            except (TypeError, ValueError):
                raise SeriesRefused(f"patterns[{i}].x={x!r} is not a number",
                                    f"patterns.{i}.x") from None
        label = str(entry.get("label") or "").strip() or Path(staged.filename).stem
        raw_labels.append(label)
        seen = cached.get(_key(token, requested))
        if seen is None:
            preview = preview_pattern(staged, reader_options=requested)
            seen = SeriesMember(
                token=token, path=staged.path, filename=staged.filename,
                label=label, x=x, reader=preview["format"]["name"],
                options=dict(preview["reader_options"]),
                n_points=int(preview["n_points"]),
                two_theta_range=tuple(preview["two_theta_range"]),
                has_sigma=bool(preview["has_sigma"]))
        out.append(replace(seen, label=label, x=x))
    # the names the run will use, shown before it runs (``unique_labels``)
    for member, label in zip(out, unique_labels(raw_labels), strict=True):
        member.label = label
    return out


def check_settings(carry: Any, refit: Any, direction: Any) -> None:
    """Refuse a setting the chain would refuse, in the same words.

    ``REFIT_MODES``/``DIRECTIONS`` are :mod:`rietx.sequential`'s own tuples, so
    a menu offering a value the validator rejects is not expressible.
    """
    if not isinstance(carry, list) or not carry or not all(
            isinstance(g, str) and g for g in carry):
        raise SeriesRefused("'carry' is a non-empty list of dot-path globs; "
                            "['*'] carries everything", "carry")
    if refit not in REFIT_MODES:
        raise SeriesRefused(f"refit must be one of {REFIT_MODES}", "refit")
    if direction not in DIRECTIONS:
        raise SeriesRefused(f"direction must be one of {DIRECTIONS}", "direction")


def read_members(setup: SeriesSetup,
                 excluded_regions: list[tuple[float, float]]) -> list[PatternData]:
    """Read the staged files as the chain will fit them.

    The project's excluded regions are applied to **every** member: a series is
    one protocol over N specimens, and a region excluded because the sample
    holder scatters there is excluded in all of them.  The 2θ limits are the
    other half and travel as ``fit``'s own argument, since that is where the
    library takes them.  A member's own exclusions (a pdCIF's zero-weight
    points) stay: the project's regions are added to them, never put in place
    of them.
    """
    from ..io.readers import read_pattern

    out = []
    for member in setup.members:
        data = read_pattern(member.path, **member.options)
        data.excluded_regions = list(data.excluded_regions) + [
            tuple(r) for r in excluded_regions
            if tuple(r) not in data.excluded_regions]
        out.append(data)
    return out


def setup_payload(setup: SeriesSetup, *, running: bool, has_result: bool,
                  mode: str, plan_preset: str | None, n_stages: int) -> dict:
    """The staged list, the settings, and the protocol the run will inherit.

    ``sigma_mixed`` is the one judgement here rather than a description: a series
    whose files disagree about carrying esds is fitted under two weighting
    policies, which is a correctness property invisible once the files are read
    (CLAUDE.md, Weights) and worth surfacing *before* the chain runs rather than
    as a footnote on its trajectories.
    """
    members = [m.as_dict() for m in setup.members]
    sigma = {m.has_sigma for m in setup.members}
    return {
        "patterns": members,
        "n_patterns": len(members),
        "settings": {"carry": list(setup.carry), "refit": setup.refit,
                     "direction": setup.direction, "x_label": setup.x_label},
        "choices": {"refit": list(REFIT_MODES), "direction": list(DIRECTIONS)},
        "carry_help": CARRY_HELP,
        "defaults": dict(DEFAULTS),
        # the protocol is the project's, quoted so a panel never re-derives it
        "protocol": {"mode": mode, "plan": plan_preset, "n_stages": n_stages},
        "has_x": setup.x is not None,
        "sigma_mixed": len(sigma) > 1,
        "has_result": has_result,
        "running": running,
    }


# ----------------------------------------------------------------------
# the trace's vocabulary (WP-1317)
# ----------------------------------------------------------------------
#: Every mark the series trace draws, and what it reads, written **once**.
#:
#: The rule this table keeps is issue #141's: the flag list and the event
#: markers are one vocabulary, read from the :class:`SeriesResult`, never a
#: second set invented view-side.  So each row names the field it is read from,
#: and :func:`trace` is the only code that reads it; the route serves the table
#: beside the trace, the panel draws what it is told, and the GUI guide's table
#: is held to these rows both ways by ``tests/test_gui_series_trace.py``.
#:
#: Three sources, in order of how much the library has already judged:
#:
#: - a **series verdict on a pattern**: a ``SeriesResult.diagnostics`` row whose
#:   ``where`` names one pattern, as the per-pattern fences all do
#:   (``where=[entry.label or str(entry.index)]``).  The codes are an open
#:   vocabulary (root ``CLAUDE.md``, Guards), so a code this table has no row for
#:   is still drawn, with :data:`OTHER_MARK` and its own name.  A series-level
#:   row with no pattern in ``where`` (``SEQUENTIAL_PATH_DEPENDENT``,
#:   ``…_PERSISTENT_FINDING``, ``…_CANCELLED``) stays the panel's banner and
#:   Fences strip: it says something about the chain, not about a point of it.
#: - the **pattern's own findings**: each ``SeriesEntry.diagnostics`` code,
#:   counted per pattern.  A count and not a glyph per code, because a fit's own
#:   codes include the ones that fire on every pattern, and those raise every
#:   bar alike while a cluster still stands out above them.
#: - the **largest step** of the parameter on show: its first row in
#:   ``SeriesResult.steps``, which is sorted largest first.  A rank, not a
#:   threshold — the field calls no step a jump (WP-2003), so neither does the
#:   trace; it says where that parameter moved most.
TRACE_VOCABULARY: tuple[dict[str, str], ...] = (
    {"key": "SERIES_PATTERN_FAILED", "mark": "bar", "label": "failed",
     "source": "SeriesResult.diagnostics",
     "means": "every rung of the ladder raised, so this pattern has no fit and "
              "no point on any trajectory"},
    {"key": "SEQUENTIAL_UNRECOVERED", "mark": "cross", "label": "unrecovered",
     "source": "SeriesResult.diagnostics",
     "means": "the fit diverged on every rung: its values are not a "
              "measurement, and it seeded no successor"},
    {"key": "SEQUENTIAL_RWP_OUTLIER", "mark": "square", "label": "above the fence",
     "source": "SeriesResult.diagnostics",
     "means": "every rung left Rwp above the series' fence; a run of these is "
              "where the model stopped describing the data"},
    {"key": "SEQUENTIAL_RESEED", "mark": "ring", "label": "reseeded",
     "source": "SeriesResult.diagnostics",
     "means": "a good fit reached from the initial model, not from its "
              "neighbour, so it is no evidence the trajectory is continuous here"},
    {"key": "findings", "mark": "count", "label": "findings",
     "source": "SeriesEntry.diagnostics",
     "means": "how many codes this pattern's own fit raised; a cluster of tall "
              "bars is where the fits changed character"},
    {"key": "largest_step", "mark": "band", "label": "largest step",
     "source": "SeriesResult.steps",
     "means": "the pair of patterns between which the parameter on show moved "
              "most, in its esds; a rank, never a verdict"},
)

#: The mark a series verdict gets when :data:`TRACE_VOCABULARY` has no row for
#: its code: drawn and named by its code rather than dropped.
OTHER_MARK = "tick"


def trace(series: SeriesResult,
          coordinates: list[float | None] | None = None) -> dict:
    """The series on its own axis: one point per pattern, with its marks.

    Every pattern the chain was given is a point, a failed one included, in
    index order — the order the chain is numbered in, which is the scrubber's
    axis.  ``x`` is the pattern's series coordinate, the entry's own
    (``SeriesEntry.x``), and for a failed pattern, which has no entry, the
    one ``coordinates`` (the staged members' ``x``) gives at its index, or
    ``None``.  ``marks`` are the codes of the series verdicts naming the
    pattern, and ``findings`` its own fit's codes with their worst level,
    both as :data:`TRACE_VOCABULARY` says.

    The largest steps are served per path, so the panel marks the parameter
    on show without a round trip when the reader picks another.  A path with
    no esd on any step has none, as ``steps`` ranks only measured ones first.
    """
    points: dict[int, dict] = {}
    names: dict[str, int] = {}
    for entry in series.entries:
        stats = entry.statistics
        levels: dict[str, str] = {}
        for d in entry.diagnostics:
            if _LEVEL_RANK[d.level] > _LEVEL_RANK.get(levels.get(d.code, ""), -1):
                levels[d.code] = d.level
        points[entry.index] = {
            "index": entry.index, "label": entry.label, "x": entry.x,
            "status": entry.status,
            "rwp": stats.rwp if stats is not None else None,
            "marks": [],
            "findings": [{"code": c, "level": v} for c, v in sorted(levels.items())]}
        names[entry.label or str(entry.index)] = entry.index
    for failure in series.failures:
        at = (coordinates[failure.index]
              if coordinates is not None and failure.index < len(coordinates)
              else None)
        points.setdefault(failure.index, {
            "index": failure.index, "label": failure.label, "x": at,
            "status": "failed", "rwp": None, "marks": [], "findings": []})
        names.setdefault(failure.label or str(failure.index), failure.index)
    for d in series.diagnostics:
        if d.where and d.where[0] in names:
            point = points[names[d.where[0]]]
            # ``direction="both"`` adds the backward chain's failures here too,
            # naming a pattern whose reported (forward) fit stands: that one
            # has a point on every trajectory, so "failed" would be false of it
            if d.code == "SERIES_PATTERN_FAILED" and point["status"] != "failed":
                continue
            if d.code not in point["marks"]:
                point["marks"].append(d.code)
    largest: dict[str, dict] = {}
    for s in series.steps or []:
        if s.size_esd is not None and s.path not in largest:
            largest[s.path] = {"indices": list(s.indices),
                               "size_esd": s.size_esd,
                               "cold_ratio": s.cold_ratio}
    return {
        "x_label": series.x_label,
        "points": [points[i] for i in sorted(points)],
        "largest_steps": largest,
        "vocabulary": [dict(row) for row in TRACE_VOCABULARY],
        "other_mark": OTHER_MARK,
    }


#: a diagnostic level's rank, for keeping a code's worst level per pattern
_LEVEL_RANK = {"info": 0, "warning": 1, "error": 2}


# ----------------------------------------------------------------------
# the answer
# ----------------------------------------------------------------------
def trajectories(series: SeriesResult,
                 backward: SeriesResult | None = None,
                 relative: frozenset[str] = frozenset(),
                 angles: frozenset[str] = frozenset()) -> list[dict]:
    """Every parameter's path across the series, plus the QPA fractions.

    One entry per dot-path in first-seen order, then one ``qpa.<phase>`` per
    phase a Rietveld fit weighed.  ``path_dependent`` is read off the series'
    **own** diagnostics rather than recomputed — the fence is the library's
    judgement — and ``discontinuous`` off its ``steps``: true where a step of
    that path was re-measured cold (``fit(verify_steps=k)``), the plot's
    shading rule, since ``steps`` calls no step a jump (WP-2003).  ``n_sigma``
    is computed here because no diagnostic carries a magnitude (see the module
    docstring).

    ``relative`` paths keep their backward values and get no ``n_sigma``,
    because the fence abstains on them (``sequential._relative_paths``): a
    coordinate DOF is the step from where each fit began, and the two chains
    begin a pattern from opposite neighbours, so its disagreement would rank
    top on a series whose coordinates agree (WP-1333).

    ``angles`` paths are compared modulo a turn, as the fence compares them
    (``sequential._angle_paths``, #604).
    """
    unstable = {d.where[0] for d in series.diagnostics
                if d.code == "SEQUENTIAL_PATH_DEPENDENT" and d.where}
    jumps = {s.path for s in series.steps or [] if s.cold_ratio is not None}
    names = list(series.paths(varied_only=False))
    phases = []
    for entry in series.entries:
        for row in (entry.qpa.phases if entry.qpa is not None else []):
            if row.name not in phases:
                phases.append(row.name)

    # R_Bragg per phase, beside the QPA rows.  A phase can carry one without
    # carrying a QPA — QPA needs Z and a molar mass, a structure R does not —
    # so this is gathered separately rather than reusing ``phases`` above.
    agreement = [f"r_bragg.{name}" for name in series.agreement_phases()]

    out = []
    for path in names + [f"qpa.{name}" for name in phases] + agreement:
        traj = series.resolve_trajectory(path)
        if not len(traj):
            continue
        row = {"path": path, "x": list(traj.x), "x_label": traj.x_label,
               "value": list(traj.value), "stderr": list(traj.stderr),
               "labels": list(traj.labels),
               "path_dependent": path in unstable,
               "discontinuous": path in jumps,
               "backward": None, "n_sigma": None}
        # Only an ordinary parameter path gets a forward/backward comparison.
        # A prefixed one is derived, not refined: ``_disagreement`` divides by
        # a combined σ, and a QPA's is a propagated one while an agreement
        # index has none at all, so both would be a different question wearing
        # the same answer's shape.  Asked of the resolver via ``is_derived_path``
        # so a fourth kind cannot be added without this line seeing it.
        if backward is not None and not series.is_derived_path(path):
            other = backward.trajectory(path)
            if len(other) == len(traj):
                row["backward"] = list(other.value)
                if path not in relative:
                    row["n_sigma"] = _disagreement(traj, other,
                                                   angle=path in angles)
        out.append(row)
    return out


def _disagreement(forward, backward, *, angle: bool = False) -> float | None:
    """The largest forward/backward difference in combined σ, or ``None``.

    Deliberately the same arithmetic as
    :func:`sequential._path_dependence_diagnostics` — combined σ, the relative
    noise floor, ``nanargmax`` — so the number a panel sorts by is the number the
    fence fired on.  ``None`` where the fence itself abstains: a parameter with
    no esd in either chain cannot be judged this way, and reporting 0 would read
    as agreement it has not earned.  ``angle`` takes the difference modulo a
    turn, the fence's ``_angle_difference``.
    """
    _, vf, sf = forward.arrays()
    _, vb, sb = backward.arrays()
    # the fence judges a pattern only where both chains measured an esd
    comparable = np.isfinite(sf) & np.isfinite(sb)
    combined = np.sqrt(np.nan_to_num(sf) ** 2 + np.nan_to_num(sb) ** 2)
    if not np.any(comparable & (combined > 0.0)):
        return None
    gap = np.abs(_angle_difference(vf - vb) if angle else vf - vb)
    with np.errstate(divide="ignore", invalid="ignore"):
        n_sigma = gap / np.where(combined > 0.0, combined, np.nan)
    n_sigma = np.where(gap > _noise_floor(vf, vb), n_sigma, 0.0)
    n_sigma = np.where(comparable, n_sigma, 0.0)
    value = float(np.nanmax(n_sigma))
    return value if np.isfinite(value) else None


def result_payload(series: SeriesResult, backward: SeriesResult | None, *,
                   running: bool, curves: list[bool],
                   relative: frozenset[str] = frozenset(),
                   angles: frozenset[str] = frozenset(),
                   coordinates: list[float | None] | None = None) -> dict:
    """The series answer as a client needs it: entries, trajectories, fences,
    and the trace the panel scrubs along (:func:`trace`).

    ``curves`` says per entry whether this session still holds that pattern's
    full :class:`~rietx.schemas.results.RefinementResult` — a
    :class:`SeriesResult` stores summaries, not curves (its module docstring), so
    the per-pattern plot is served from the runner in memory and a panel must
    know which rows it may open.

    ``path_dependent`` is hoisted to the top level because it is the **headline**
    and not a footnote: a smooth curve is exactly what a poisoned chain produces
    (WP-0505's measured lesson), so the one check that separates a measured
    trajectory from an ordering artefact cannot be something a user has to scroll
    to.

    ``relative`` is the runner's ``sequential._relative_paths``, and
    ``angles`` its ``sequential._angle_paths``, both passed on to
    :func:`trajectories`.  ``coordinates`` are the staged members' ``x``, which
    place a failed pattern on the trace (:func:`trace`).
    """
    return {
        "result": series.model_dump(mode="json"),
        "trajectories": trajectories(series, backward, relative, angles),
        "trace": trace(series, coordinates),
        "path_dependent": sorted({d.where[0] for d in series.diagnostics
                                  if d.code == "SEQUENTIAL_PATH_DEPENDENT"
                                  and d.where}),
        "path_dependence_sigma": PATH_DEPENDENCE_SIGMA,
        "has_backward": backward is not None,
        "n_iterations": series.n_iterations,
        "curves": list(curves),
        "running": running,
    }
