"""Refinement result schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Base, Diagnostic, Mode, Provenance


class RefinedParameter(Base):
    path: str
    value: float
    stderr: float | None = None
    initial: float | None = None
    vary: bool = True
    at_bound: bool = False


class Statistics(Base):
    """Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67.

    ``rwp_background_subtracted`` re-evaluates Rwp with the background removed
    from both y_obs and y_calc, which Toby recommends as the more meaningful
    number when the background is a large fraction of the signal.

    ``esd_inflation`` is the Bérar-Lelann serial-correlation factor
    (Bérar & Lelann, 1991, J. Appl. Cryst. 24, 1) — reported parameter esds
    have already been multiplied by it.  The estimator is conservative: even
    perfectly white residuals land at ≈1.51 (chance same-sign runs — see
    ``optimize.statistics.berar_lelann_factor``); lab data with unmodelled
    profile detail typically lands at 2-4.  Divide it out for raw
    χ²·(JᵀJ)⁻¹ esds.
    """

    rwp: float
    rp: float
    rexp: float
    chi2: float
    gof: float
    rwp_background_subtracted: float | None = None
    durbin_watson: float | None = None
    esd_inflation: float | None = None
    n_points: int
    n_free_parameters: int


class IterationRecord(Base):
    stage: str
    iteration: int
    cost: float
    grad_norm: float | None = None
    step_norm: float | None = None


class StageResult(Base):
    name: str
    status: Literal["converged", "max_iter", "diverged", "skipped"]
    n_iterations: int
    cost_initial: float
    cost_final: float
    freed: list[str] = Field(default_factory=list)


class RefinementResult(Base):
    status: Literal["converged", "max_iter", "diverged"]
    mode: Mode
    parameters: list[RefinedParameter]
    statistics: Statistics
    correlation_warnings: list[str] = Field(default_factory=list)
    stages: list[StageResult] = Field(default_factory=list)
    history: list[IterationRecord] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    provenance: Provenance

    # Where this result sits in the refinement history DAG (None when the
    # refinement was run with history disabled).
    node_id: str | None = None
    tree_id: str | None = None

    # Arrays for plotting/export (kept as lists for JSON round-trip; use
    # the exporters for column files).
    two_theta: list[float] = Field(default_factory=list)
    y_obs: list[float] = Field(default_factory=list)
    y_calc: list[float] = Field(default_factory=list)
    y_background: list[float] = Field(default_factory=list)
    # per-point σ actually used in the fit (file esds when present, Poisson
    # fallback otherwise) — the FitReport weights with these, never re-derives
    sigma: list[float] = Field(default_factory=list)
    # per-phase reflection tick positions (deg 2θ)
    ticks: dict[str, list[float]] = Field(default_factory=dict)

    def plot(self, path: str | None = None, **kw):
        from ..viz.plots import plot_result

        return plot_result(self, path=path, **kw)

    def parameter(self, path: str) -> RefinedParameter:
        for p in self.parameters:
            if p.path == path:
                return p
        raise KeyError(path)
