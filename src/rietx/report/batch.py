"""Diagnostics over a batch of results, as counts (WP-2037).

One refinement's diagnostics are read row by row.  A batch's are read as a
table: how often each code fires, how many warnings a result carries for
each purpose, and which codes make up most of the warning load.  The last is
the alarm-management "bad actor" Pareto (ISA-18.2, EEMUA 191): the few codes
that account for most alarms, ranked so a person can rationalise them first.

The aggregate decides nothing and reports numbers (DESIGN.md § Rules 1, kind
3).  It serves two readers with one function: a pipeline triaging its own
batch, and the package's audit, which reads the same table over the
acceptance suites as a prompt (``tests/suite_alarms.py``) and never as a
verdict, since a code firing on every one of rietx's own fits may mean every
one of those fits has the fault.

Every level counted here is a row's level in
:func:`rietx.schemas.results.diagnostic_view`, the one filter every renderer
calls, so a count can never disagree with what a printed summary shows.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import Field

from ..schemas.common import Base
from ..schemas.results import (
    _NAMED_PURPOSES,
    RefinementResult,
    _check_deliverable,
    _check_levels,
    diagnostic_view,
)


class CodeTally(Base):
    """One code's firing over a batch.

    ``n_results`` counts the results it fired on (one row or more), and
    ``rate`` is that over the batch's size.  ``n_rows`` counts every row of the
    code, and ``n_error``, ``n_warning`` and ``n_info`` split them by the level
    :func:`~rietx.schemas.results.diagnostic_view` gives each: under the
    summary's deliverable when it has one, else the level the row was raised
    at, with a caller's ``levels=`` word applied either way.
    """

    code: str
    n_results: int
    rate: float
    n_rows: int
    n_error: int
    n_warning: int
    n_info: int


class ParetoRow(Base):
    """One code's share of a batch's warning rows, in Pareto order.

    ``share`` is ``n_warning`` over every warning row in the batch, and
    ``cumulative`` the running sum of the shares down the ranking, so the last
    row reads 1.0.
    """

    code: str
    n_warning: int
    share: float
    cumulative: float


class DiagnosticsSummary(Base):
    """The diagnostics of a batch of results as counts, from
    :func:`diagnostics_summary`.

    ``codes`` holds every code that fired, most results first.
    ``warnings_per_result`` is the mean number of warning rows a result
    carries, keyed by purpose: the one deliverable when the summary was given
    one, else every purpose of :data:`rietx.purposes.PURPOSES` but ``series``.
    ``pareto`` ranks the codes that raised a warning row by their share of
    all of them, under the deliverable when there is one and else at the
    level each row was raised at.  A code that fired only as ``info`` or
    ``error`` is in ``codes`` and not in ``pareto``.  ``levels`` is the
    caller's override map the counts were taken under, empty when none was
    given.  An empty batch gives empty tallies.
    """

    n_results: int
    deliverable: str | None = None
    levels: dict[str, str] = Field(default_factory=dict)
    codes: list[CodeTally] = Field(default_factory=list)
    warnings_per_result: dict[str, float] = Field(default_factory=dict)
    pareto: list[ParetoRow] = Field(default_factory=list)

    def __str__(self) -> str:
        """A header, the Pareto table, the codes with no warning row, and the
        warnings a result carries per purpose."""
        from .._display import table_text

        under = (f"under {self.deliverable}" if self.deliverable
                 else "no deliverable, rows at their raised level")
        set_by = f", {len(self.levels)} code(s) set by levels=" if self.levels else ""
        lines = [f"DiagnosticsSummary: {self.n_results} result(s), {under}{set_by}"]
        fired = {t.code: t for t in self.codes}
        if self.pareto:
            rows = [(p.code, f"{fired[p.code].n_results}/{self.n_results}",
                     str(p.n_warning), f"{p.cumulative:.0%}") for p in self.pareto]
            lines += table_text(("code", "fired on", "warnings", "cumulative"), rows, "  ")
        else:
            lines.append("  no warning rows")
        quiet = [t for t in self.codes if t.n_warning == 0]
        if quiet:
            lines.append("  fired with no warning row: " + ", ".join(
                f"{t.code} {t.n_results}/{self.n_results}" for t in quiet))
        if self.warnings_per_result:
            lines.append("  warnings per result: " + ", ".join(
                f"{p} {m:.2g}" for p, m in self.warnings_per_result.items()))
        return "\n".join(lines)


def diagnostics_summary(results: Iterable[RefinementResult],
                        deliverable: str | None = None,
                        levels: dict[str, str] | None = None) -> DiagnosticsSummary:
    """The diagnostics of a batch of results as counts: each code's firing
    rate, the warning rows a result carries per purpose, and the codes ranked
    by their share of the warnings (WP-2037).

    ``results`` is any iterable of objects carrying ``.diagnostics``, such as
    a list of :class:`~rietx.schemas.results.RefinementResult`.  A
    :class:`~rietx.schemas.sequential.SeriesResult` counts as one result, with
    its own series rows.  ``deliverable`` and ``levels`` mean what they mean
    to ``summary()``, and an unknown deliverable, code or level word is
    refused the same way, even on an empty batch.  The counts are a prompt:
    a code that fires on most of a batch is a statement about the model or
    the plan the batch shares, which the batch's own data cannot settle.
    """
    if deliverable is not None:
        _check_deliverable(deliverable)
    levels = _check_levels(levels)
    batch = list(results)
    n = len(batch)
    purposes = (deliverable,) if deliverable is not None else _NAMED_PURPOSES

    fired: Counter[str] = Counter()
    by_level: dict[str, Counter[str]] = {}
    warnings: Counter[str] = Counter()
    for result in batch:
        rows = diagnostic_view(result.diagnostics, deliverable, levels)
        for row in rows:
            by_level.setdefault(row.diagnostic.code, Counter())[row.level] += 1
        fired.update({row.diagnostic.code for row in rows})
        if deliverable is not None:
            warnings[deliverable] += sum(row.level == "warning" for row in rows)
        else:
            # a row's ``warning_under`` is the purposes its level under each is
            # a warning, override included, so one view answers all seven
            for row in rows:
                warnings.update(row.warning_under)

    codes = [CodeTally(code=code, n_results=fired[code], rate=fired[code] / n,
                       n_rows=sum(counts.values()), n_error=counts["error"],
                       n_warning=counts["warning"], n_info=counts["info"])
             for code, counts in by_level.items()]
    codes.sort(key=lambda t: (-t.n_results, -t.n_rows, t.code))

    ranked = sorted((t for t in codes if t.n_warning),
                    key=lambda t: (-t.n_warning, -t.n_results, t.code))
    total = sum(t.n_warning for t in ranked)
    pareto, running = [], 0
    for t in ranked:
        running += t.n_warning
        pareto.append(ParetoRow(code=t.code, n_warning=t.n_warning,
                                share=t.n_warning / total, cumulative=running / total))

    per_result = {p: warnings[p] / n for p in purposes} if n else {}
    return DiagnosticsSummary(n_results=n, deliverable=deliverable, levels=levels,
                              codes=codes, warnings_per_result=per_result, pareto=pareto)
