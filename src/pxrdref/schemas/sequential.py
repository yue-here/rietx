"""Schemas for a sequential (in-situ / parametric) refinement series.

A series is N separate refinements, ordered, each warm-started from its
predecessor — not one joint residual (that is the multi-histogram path,
``pxrdref.multi``).  What the user wants back is therefore not N unrelated
results but a **trajectory**: a(T), Biso(t), the weight fractions against the
series coordinate, with esds, and with the per-pattern status of the fit that
produced each point.

Following the history DAG's rule (see :mod:`pxrdref.schemas.history`), a
:class:`SeriesResult` stores **summaries, not curves**.  Nine 7251-point
patterns' worth of ``y_obs``/``y_calc``/``y_background``/``sigma`` is ~2 MB of
JSON that is already on disk as the input files; the refined values, their
esds, the agreement indices and the diagnostics are what a series is *for*, and
they are a few kB.  The full :class:`~pxrdref.schemas.results.RefinementResult`
of each pattern stays reachable in memory on the
:class:`~pxrdref.sequential.SequentialRefinement` that produced it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Base, Diagnostic, Mode, Provenance
from .results import QuantitativePhaseAnalysis, RefinedParameter, Statistics


class SeriesEntry(Base):
    """One pattern's place in the series: what was fitted and how it went."""

    index: int
    label: str = ""
    #: The series coordinate — temperature, time, pressure, composition.
    #: ``None`` when the caller gave none, in which case ``index`` is the axis.
    x: float | None = None

    status: Literal["converged", "max_iter", "diverged"] = "converged"
    statistics: Statistics | None = None
    parameters: list[RefinedParameter] = Field(default_factory=list)
    qpa: QuantitativePhaseAnalysis | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    #: Total least-squares iterations over every stage of this pattern's fit.
    #: The headline warm-start number: it is what a warm start actually buys,
    #: and it is measured rather than assumed (see WP-0505's acceptance).
    n_iterations: int = 0
    #: True when the warm start was rejected and this pattern was refitted from
    #: the initial models (see ``SEQUENTIAL_RESEED``).  A reseeded point is
    #: still a good fit — but it is *not* evidence that the trajectory is
    #: continuous there, because its starting point did not come from its
    #: neighbour.
    reseeded: bool = False
    #: Rwp the warm-started fit reached, set whenever a cold restart was tried
    #: at all.  With ``reseeded`` it says which of the two was kept: both set
    #: means the restart rescued the pattern, ``rwp_warm`` alone means the
    #: guard fired but the warm fit was still the better one — worth seeing,
    #: since it marks a pattern the series found hard for a reason the restart
    #: could not fix.
    rwp_warm: float | None = None

    #: Where this pattern's own history lives (one tree per pattern — a tree is
    #: pinned to one pattern by its data fingerprint).
    node_id: str | None = None
    tree_id: str | None = None

    def value(self, path: str) -> float | None:
        for p in self.parameters:
            if p.path == path:
                return p.value
        return None

    def stderr(self, path: str) -> float | None:
        for p in self.parameters:
            if p.path == path:
                return p.stderr
        return None


class Trajectory(Base):
    """One parameter's path across the series, with its per-point esds.

    ``x`` is the series coordinate when one was given and the pattern index
    otherwise; ``x_label`` says which, so a plot axis is never mislabelled.
    ``value``/``stderr`` are aligned with it, and ``stderr`` entries are
    ``None`` wherever that pattern did not estimate one (a parameter that was
    not free in that fit, or a stage that returned no covariance).
    """

    path: str
    x: list[float] = Field(default_factory=list)
    x_label: str = "index"
    value: list[float] = Field(default_factory=list)
    stderr: list[float | None] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.value)

    def arrays(self):
        """``(x, value, stderr)`` as float arrays; missing esds become NaN."""
        import numpy as np

        return (np.asarray(self.x, dtype=float),
                np.asarray(self.value, dtype=float),
                np.asarray([np.nan if s is None else s for s in self.stderr],
                           dtype=float))


class SeriesResult(Base):
    """The result of a sequential refinement over an ordered set of patterns.

    Iterating it yields :class:`SeriesEntry` in series order.  Series-level
    diagnostics (path dependence, discontinuities, reseeds) sit on
    :attr:`diagnostics`; per-pattern ones stay on their entry.
    """

    mode: Mode = "rietveld"
    entries: list[SeriesEntry] = Field(default_factory=list)
    x_label: str = "index"
    #: ``"forward"``/``"backward"``: the chain direction whose fits are
    #: reported in :attr:`entries`.  ``"both"`` means the series was run twice
    #: and the two trajectories compared — the reported entries are the forward
    #: ones, and the comparison is in :attr:`diagnostics`.
    direction: Literal["forward", "backward", "both"] = "forward"
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    provenance: Provenance | None = None

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):  # type: ignore[override]
        return iter(self.entries)

    def __getitem__(self, i: int) -> SeriesEntry:
        return self.entries[i]

    @property
    def labels(self) -> list[str]:
        return [e.label for e in self.entries]

    @property
    def x(self) -> list[float]:
        """The series axis: the given coordinate, or the pattern index."""
        return [float(e.index) if e.x is None else e.x for e in self.entries]

    @property
    def rwp(self) -> list[float]:
        return [e.statistics.rwp if e.statistics else float("nan")
                for e in self.entries]

    @property
    def n_iterations(self) -> int:
        """Total least-squares iterations over the whole series."""
        return sum(e.n_iterations for e in self.entries)

    def trajectory(self, path: str) -> Trajectory:
        """One parameter's trajectory across the series.

        Patterns where the path is absent are skipped rather than filled — a
        gap in a trajectory is a real thing (a phase that was not in the model
        yet, a stage that did not run) and inventing a value for it would be
        exactly the confident-wrong-singleton failure the FitReport gates
        against.
        """
        traj = Trajectory(path=path, x_label=self.x_label)
        for e, xv in zip(self.entries, self.x, strict=True):
            found = next((p for p in e.parameters if p.path == path), None)
            if found is None:
                continue
            traj.x.append(xv)
            traj.value.append(found.value)
            traj.stderr.append(found.stderr)
            traj.labels.append(e.label)
        return traj

    def paths(self, *, varied_only: bool = False) -> list[str]:
        """Every parameter path present in the series, in first-seen order.

        A :class:`~pxrdref.schemas.results.RefinementResult` records the
        parameters the fit *determined* — free ones and the tied ones that
        follow them (a hexagonal ``cell.b`` is not free but is every bit as
        measured as ``cell.a``), so the default keeps both.  ``varied_only``
        drops the tied ones.
        """
        out: list[str] = []
        seen: set[str] = set()
        for e in self.entries:
            for p in e.parameters:
                if varied_only and not p.vary:
                    continue
                if p.path not in seen:
                    seen.add(p.path)
                    out.append(p.path)
        return out

    def qpa_trajectory(self, phase: str) -> Trajectory:
        """A phase's weight fraction (as a percentage) across the series."""
        traj = Trajectory(path=f"qpa.{phase}", x_label=self.x_label)
        for e, xv in zip(self.entries, self.x, strict=True):
            if e.qpa is None:
                continue
            row = next((r for r in e.qpa.phases if r.name == phase), None)
            if row is None:
                continue
            traj.x.append(xv)
            traj.value.append(100.0 * row.weight_fraction)
            traj.stderr.append(None if row.weight_fraction_stderr is None
                               else 100.0 * row.weight_fraction_stderr)
            traj.labels.append(e.label)
        return traj

    # -- tabular export ------------------------------------------------
    def to_table(self, *, paths: list[str] | None = None
                 ) -> tuple[list[str], list[list]]:
        """``(header, rows)``: one row per pattern, value + esd per parameter.

        The wide form is what gets plotted or pasted into a paper; the columns
        are ``index, label, x, status, rwp, gof, <path>, <path>_esd, …``.
        """
        paths = self.paths() if paths is None else list(paths)
        header = ["index", "label", self.x_label, "status", "rwp", "gof"]
        for p in paths:
            header += [p, f"{p}_esd"]
        rows: list[list] = []
        for e, xv in zip(self.entries, self.x, strict=True):
            row: list = [e.index, e.label, xv, e.status,
                         e.statistics.rwp if e.statistics else None,
                         e.statistics.gof if e.statistics else None]
            for p in paths:
                row += [e.value(p), e.stderr(p)]
            rows.append(row)
        return header, rows

    def write_csv(self, path, *, delimiter: str | None = None,
                  paths: list[str] | None = None) -> None:
        """Write :meth:`to_table` to CSV/TSV (delimiter inferred from suffix)."""
        import csv
        from pathlib import Path as _Path

        p = _Path(path)
        if delimiter is None:
            delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
        header, rows = self.to_table(paths=paths)
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter=delimiter)
            w.writerow(header)
            for row in rows:
                w.writerow(["" if v is None else v for v in row])

    def plot(self, paths: list[str] | str, *, path=None, **kw):
        """Plot one or more trajectories against the series axis."""
        from ..viz.plots import plot_trajectory

        return plot_trajectory(self, paths, path=path, **kw)
