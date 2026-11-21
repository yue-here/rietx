"""Test-side machinery for WP-2017 group K: thinning a real pattern, and the reach harness.

Two tools, neither of which decides anything for the package.

:func:`thin` takes a measured pattern down to a stated mean count per channel by binomial
thinning, which keeps the counts Poisson.  It is how a sparse-count family is made from
patterns we already hold, rather than chosen after reading the question (WP-2017,
"K, read 2026-11-16"; the maintainer's Q16a, 2026-11-17).

:func:`run_case` is WP-2086's reach harness rebuilt from that WP's prose, since its harness
and raw rows are gone.  A case is a pattern, a plan and a start error (the main phase's cell
lengths scaled by ``1 + cell_error``, and ``zero_offset`` degrees added to the zero shift),
optionally thinned and optionally with every phase scale held at 0.  The fit's row is
classed against a reference answer the caller supplies:

``reached``  usable, with no error diagnostic, and the main phase's ``a`` within ``cell_tol``
             (relative) of the reference answer's;
``error``    ``usable`` is False or an error-level diagnostic fired (the package said so);
``silent``   usable, no error diagnostic, and the cell outside the tolerance.

Every row also carries what ``MODEL_FAR_FROM_DATA``'s test compared
(``rietx.refine._far_from_data_diagnostics``): the two χ², N, the restricted model's
parameter count, ``n_added``, Hamilton's F, its denominator degrees of freedom and its upper
tail probability ``p``.  ``hamilton_justified`` returns True exactly when F exceeds the
F(n_added, dof) quantile at 1 − α, that is when ``p < α`` (for F > 0), so the diagnostic
fires when ``p >= α`` and where the test is undefined.  The quantities are read by
wrapping the call the package makes, never recomputed beside it.

The four families are the acceptance protocols of WP-2017 Q16a, each with its referent:

``corundum``  the IUCr CPD round robin's pure corundum (``qarr/corundum.prn``) under
              ``test_acceptance_srm676a``'s protocol, against SRM 676a's certified cell;
``fap``       the GSAS-II LabData tutorial fluorapatite under ``test_acceptance_fap``'s GSAS
              protocol, against GSAS's converged fit (cross-code);
``srm660c``   NIST's SRM 660c LaB₆ certification data under ``test_acceptance_srm660c``'s
              calibrated protocol, against the certified cell;
``nac``       APS 11-BM NAC with its CaF₂ impurity under ``test_acceptance_nac``'s protocol.
              Its Rietveld start is the protocol's Le Bail pass run on the *unthinned*
              pattern, so the correct start is the same model at every count level.
"""

from __future__ import annotations

import dataclasses
import functools
import importlib
import math
import time
from contextlib import contextmanager

import numpy as np

import rietx as rx
from rietx.schemas.pattern import POISSON_FLOOR_COUNTS

FAMILIES = ("corundum", "fap", "srm660c", "nac")


# -- thinning ------------------------------------------------------------------------------


def thin(pattern: rx.PatternData, mean_counts: float, seed: int, *,
         two_theta_limits: tuple[float, float] | None = None) -> rx.PatternData:
    """``pattern`` binomially thinned to ``mean_counts`` counts a channel, on average.

    Each channel's count n is replaced by a draw from Binomial(n, p), with one p for the
    whole pattern, chosen so the mean thinned count over the fitted channels (the pattern's
    ``in_range_mask``, inside ``two_theta_limits`` when given) is ``mean_counts``.  Thinning
    a Poisson count by a fixed probability leaves it Poisson, with its mean times p, so the
    result is a counting pattern at the lower count and the same shape.

    **Effective counts.**  Where σ is not √I (11-BM's summed and normalised analyser
    channels, a rescaled pattern, NIST's SRM 660c file), the count thinned is the
    effective count c = (I/σ)², the count a Poisson channel with that I/σ would hold, and
    the channel's gain g = I/σ² carries it back.  On a pattern with no stated σ, rietx
    weights by √max(I, 1) and c = I where I ≥ 1.  A non-integer c is rounded at random to
    an adjacent integer, with the probability that keeps its mean, before the draw.

    **The result** keeps the pattern's intensity scale, so a protocol's start values
    (scales, background coefficients) mean what they meant: I' = c'/(g·p) and
    σ' = √max(c', 1)/(g·p), with c' the thinned count.  So (I'/σ')² = c', σ is √counts
    in count units, and a channel that thins to zero counts takes rietx's own Poisson
    floor (:data:`~rietx.schemas.pattern.POISSON_FLOOR_COUNTS`, one count) rather than a
    zero σ that ``nonpositive_sigma="exclude"`` would drop.  Channels outside the fit
    (excluded regions, a non-positive stated σ) pass through unchanged.

    ``seed`` is the integer handed to :func:`numpy.random.default_rng`, never a hash.
    Raises :class:`ValueError` where the pattern holds fewer counts than asked for.
    """
    if not mean_counts > 0:
        raise ValueError(f"mean_counts must be positive, got {mean_counts!r}")
    y = pattern.y()
    sig = pattern.sig()
    live = pattern.in_range_mask() & (y > 0) & (sig > 0)
    fitted = pattern.in_range_mask()
    if two_theta_limits is not None:
        x = pattern.x()
        fitted = fitted & (x >= two_theta_limits[0]) & (x <= two_theta_limits[1])
    c = np.zeros_like(y)
    c[live] = (y[live] / sig[live]) ** 2
    gain = np.ones_like(y)
    gain[live] = y[live] / sig[live] ** 2
    mean_c = float(c[fitted].mean())
    p = mean_counts / mean_c
    if not 0.0 < p <= 1.0:
        raise ValueError(f"the pattern holds {mean_c:.4g} effective counts a channel, "
                         f"fewer than the {mean_counts:g} asked for")
    rng = np.random.default_rng(int(seed))
    whole = np.floor(c)
    n = whole + (rng.random(c.shape) < (c - whole))
    thinned = rng.binomial(n.astype(np.int64), p).astype(np.float64)
    keep = pattern.in_range_mask()
    unit = gain * p
    y_new = np.where(keep, thinned / unit, y)
    s_new = np.where(keep, np.sqrt(np.maximum(thinned, POISSON_FLOOR_COUNTS)) / unit, sig)
    meta = dict(pattern.metadata)
    meta["thinned"] = f"binomial to {mean_counts:g} counts a channel, p = {p:.6g}, seed {seed}"
    return pattern.model_copy(update={"intensity": y_new.tolist(), "sigma": s_new.tolist(),
                                      "metadata": meta})


def mean_effective_counts(pattern: rx.PatternData, *,
                          two_theta_limits: tuple[float, float] | None = None) -> float:
    """The mean of (I/σ)² over the fitted channels, the count :func:`thin` reads."""
    y, sig = pattern.y(), pattern.sig()
    fitted = pattern.in_range_mask()
    if two_theta_limits is not None:
        x = pattern.x()
        fitted = fitted & (x >= two_theta_limits[0]) & (x <= two_theta_limits[1])
    c = np.where((y > 0) & (sig > 0), (y / np.where(sig > 0, sig, 1.0)) ** 2, 0.0)
    return float(c[fitted].mean())


# -- the four protocols --------------------------------------------------------------------


@dataclasses.dataclass
class Protocol:
    """One family's acceptance protocol: its pattern, start model, plan and fit keywords."""

    family: str
    data: rx.PatternData
    structure: rx.Structure
    instrument: rx.Instrument
    plan: rx.RefinementPlan
    fit_kwargs: dict


@functools.lru_cache(maxsize=1)
def _nac_seed() -> tuple[str, str]:
    """The NAC protocol's Le Bail pass on the unthinned pattern, as JSON (cached)."""
    from tests.test_acceptance_nac import LIMITS, build_nac_inputs

    data, st, ins = build_nac_inputs()
    lb = rx.Refinement(st, ins, history=False)
    lb.fit(data, mode="lebail", two_theta_limits=LIMITS)
    return (lb.fitted_structure.model_dump_json(), lb.fitted_instrument.model_dump_json())


def protocol(family: str) -> Protocol:
    """``family``'s acceptance protocol, built as its suite builds it (fresh objects)."""
    if family == "corundum":
        from tests.test_acceptance_qpa_roundrobin import (
            DATA,
            corundum_phase,
            qarr_instrument,
            qpa_plan,
        )
        data = rx.read_pattern(DATA / "corundum.prn")
        st = rx.Structure(phases=[corundum_phase()])
        return Protocol(family, data, st, qarr_instrument(), qpa_plan(), {})
    if family == "fap":
        from tests.test_acceptance_fap import _gsas_protocol_plan, build_fap_inputs
        data, st, ins = build_fap_inputs()
        return Protocol(family, data, st, ins, _gsas_protocol_plan(), {})
    if family == "srm660c":
        from tests.test_acceptance_srm660c import _nist_calibrated_plan, build_srm_inputs
        data, st, ins = build_srm_inputs()
        return Protocol(family, data, st, ins, _nist_calibrated_plan(), {})
    if family == "nac":
        from tests.test_acceptance_nac import LIMITS, _caf2_phase, build_nac_inputs
        data = build_nac_inputs()[0]
        st_json, ins_json = _nac_seed()
        st = rx.Structure.model_validate_json(st_json)
        ins = rx.Instrument.model_validate_json(ins_json)
        st.phases[0].scale.value = 1e-6
        st.phases.append(_caf2_phase())
        plan = rx.RefinementPlan.mccusker_default()
        plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
        plan.intermediate_ftol = 1e-6
        plan.closing_window_tol = 1e-3
        return Protocol(family, data, st, ins, plan, {"two_theta_limits": LIMITS})
    raise ValueError(f"unknown family {family!r}; one of {FAMILIES}")


# -- the harness ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    """One fit of the reach harness.

    ``plan`` is ``"protocol"`` (the family's acceptance plan) or a preset name
    (``rx.RefinementPlan.<plan>()``).  ``cell_error`` scales the main phase's cell lengths
    by ``1 + cell_error``; ``zero_offset`` is added to ``instrument.zero_shift`` (degrees).
    ``mean_counts`` ``None`` fits the pattern as measured, otherwise :func:`thin` at
    ``seed``.  ``scale_zero`` holds every phase scale at 0, the full collapse by
    construction.
    """

    family: str
    plan: str = "protocol"
    cell_error: float = 0.0
    zero_offset: float = 0.0
    mean_counts: float | None = None
    seed: int = 0
    scale_zero: bool = False

    @property
    def name(self) -> str:
        counts = "full" if self.mean_counts is None else f"{self.mean_counts:g}c_s{self.seed}"
        parts = [self.family, self.plan, f"{self.cell_error:+.2%}", counts]
        if self.zero_offset:
            parts.append(f"z{self.zero_offset:+g}")
        if self.scale_zero:
            parts.append("scale0")
        return "/".join(parts)


@contextmanager
def far_from_data_spy(records: list[dict]):
    """Record what each ``MODEL_FAR_FROM_DATA`` test compared, one dict per call.

    Wraps ``rietx.refine._far_from_data_diagnostics`` (looked up as a module global at
    its call site) and, only while it runs, ``rietx.report.layer2.hamilton_justified``
    (imported inside it at call time), so the numbers are the ones the package tested.
    """
    from scipy.stats import f as f_dist

    rf = importlib.import_module("rietx.refine")   # ``rietx.refine`` the name is the function
    l2 = importlib.import_module("rietx.report.layer2")
    inner, inner_h = rf._far_from_data_diagnostics, l2.hamilton_justified

    def hamilton(chi2_r, chi2_f, n, n_r, n_added, *, alpha=0.05, n_effective=None):
        rec = records[-1]
        rec.update(chi2_bkg=float(chi2_r), chi2_full=float(chi2_f), n=int(n),
                   n_bkg=int(n_r), n_added=int(n_added), alpha=float(alpha))
        test = l2._hamilton_f(chi2_r, chi2_f, n, n_r, n_added, n_effective=n_effective)
        if test is None:
            rec.update(F=None, dof=None, p=None)
        else:
            f, dof = test
            rec.update(F=float(f), dof=float(dof),
                       p=float(f_dist.sf(max(f, 0.0), n_added, dof)))
        verdict = inner_h(chi2_r, chi2_f, n, n_r, n_added, alpha=alpha,
                          n_effective=n_effective)
        rec["justified"] = bool(verdict)
        return verdict

    def spy(model, y_calc, y_bkg, stats, values=None, free_paths=None):
        records.append({"rwp": float(stats.rwp)})
        l2.hamilton_justified = hamilton
        try:
            out = inner(model, y_calc, y_bkg, stats, values, free_paths)
        finally:
            l2.hamilton_justified = inner_h
        records[-1]["flagged"] = bool(out)
        return out

    rf._far_from_data_diagnostics = spy
    try:
        yield records
    finally:
        rf._far_from_data_diagnostics = inner


def start_for(case: Case) -> Protocol:
    """The case's protocol with its data thinned and its start displaced, as the fit sees it."""
    proto = protocol(case.family)
    if case.mean_counts is not None:
        proto.data = thin(proto.data, case.mean_counts, case.seed,
                          two_theta_limits=proto.fit_kwargs.get("two_theta_limits"))
    if case.plan != "protocol":
        proto.plan = getattr(rx.RefinementPlan, case.plan)()
    cell = proto.structure.phases[0].cell
    for name in ("a", "b", "c"):
        getattr(cell, name).value *= 1.0 + case.cell_error
    proto.instrument.zero_shift.value += case.zero_offset
    if case.family == "corundum":
        from tests.test_acceptance_qpa_roundrobin import seed_scales
        seed_scales(proto.structure, proto.instrument, proto.data)
    return proto


def run_case(case: Case) -> dict:
    """Fit ``case`` and return its row (see the module docstring); never classes it."""
    proto = start_for(case)
    ref = rx.Refinement(proto.structure, proto.instrument, history=False)
    if case.scale_zero:
        for ph in proto.structure.phases:
            ph.scale.value = 0.0
        ref = rx.Refinement(proto.structure, proto.instrument, history=False)
        ref.hold("phases.*.scale")
    records: list[dict] = []
    t0 = time.perf_counter()
    with far_from_data_spy(records):
        result = ref.fit(proto.data, plan=proto.plan, **proto.fit_kwargs)
    seconds = time.perf_counter() - t0
    fitted = ref.fitted_structure
    main = fitted.phases[0]
    test = records[-1] if records else {}
    scales = [float(ph.scale.value) for ph in fitted.phases]
    scale_esd = []
    for k in range(len(fitted.phases)):
        row = result.parameter(f"phases.{k}.scale") if not case.scale_zero else None
        scale_esd.append(None if row is None or row.stderr is None else float(row.stderr))
    return {
        "case": case.name, **dataclasses.asdict(case),
        "status": result.status, "usable": bool(result.usable),
        "codes": sorted({d.code for d in result.diagnostics}),
        "error_codes": sorted({d.code for d in result.diagnostics if d.level == "error"}),
        "rwp": float(result.statistics.rwp), "n_points": int(result.statistics.n_points),
        "a": float(main.cell.a.value), "c": float(main.cell.c.value),
        "scales": scales, "scale_esds": scale_esd,
        "far_from_data": test, "n_tests": len(records), "seconds": seconds,
    }


def classify(row: dict, reference_a: float, cell_tol: float = 1e-3) -> str:
    """``reached``, ``error`` or ``silent`` (module docstring) against ``reference_a``."""
    if not row["usable"] or row["error_codes"]:
        return "error"
    return "reached" if abs(row["a"] / reference_a - 1.0) <= cell_tol else "silent"


def flagged(row: dict) -> bool:
    """Whether the row's ``MODEL_FAR_FROM_DATA`` test fired (its code is in the row)."""
    return "MODEL_FAR_FROM_DATA" in row["codes"]


def p_value(row: dict) -> float:
    """The row's Hamilton p; an undefined test reads 1 (it fires there, as at p = 1)."""
    p = row["far_from_data"].get("p")
    return 1.0 if p is None or (isinstance(p, float) and math.isnan(p)) else float(p)
