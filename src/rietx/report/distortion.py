"""What a fit on mode amplitudes reports: the irrep blocks as quantities (WP-1419 C4a).

A child stated on its parent's symmetry-adapted modes
(``crystallography.representation.distortion.displacive_statement``) refines
one absolute amplitude per mode.  The unit the reporting is about is the
**irrep block**, every mode sharing one ``(irrep, k, isotropy_group)`` over
all parent sites, fixed by symmetry before the fit (#286, 2026-09-16).  This
module computes, and decides nothing:

* at fit close, one :class:`~rietx.schemas.results.DistortionTotal` per block:
  A_τ, its esd from the block's own covariance, Hotelling's T² with m and no p,
  whether the block alone has the child's group, and the largest displacement
  (:func:`distortion_totals`);
* on call, for any blocks or sets of blocks the caller names, a refit with them
  held at 0 and the nested comparison through
  :func:`~rietx.report.compare_freed`: ΔBIC at N/f², Hamilton's Λ and its p,
  both χ², and the detectability amplitude A_det when a bar is passed
  (:func:`distortion_block_tests`);
* a restricted refit that lands below the full fit proves the full fit stopped
  short, so the full fit is refitted from there and every held set tested again
  (Kerman et al. 2012, *Acta Cryst.* A**68**, 222, p. 231: the exclusion refit
  is the profile at A_B = 0, which cannot lie below the full model's optimum).

No verdict, threshold or warning is raised here; which numbers make a block
"supported" is a heuristic built on these.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable

import numpy as np

from ..crystallography.representation import distortion as _dist
from ..schemas.results import DistortionTotal
from .schemas import DistortionBlockTest, DistortionBlockTests, DistortionRestart

# The amplitude (Å) of the one predict per mode that A_det reads λ_j at is the
# caller's (``detectability_probe``), as the bar is: λ_j(A) ∝ A^p_j holds to
# leading order only, so the probe moves A_det by the next order, and no one
# value has been shown to hold that error under a stated bar for every block.
# ``tests/test_distortion_totals.py`` measures it at 0.1 Å on two blocks of
# LaMnO₃ (Γ and zone-boundary) at one noise seed: within 2.1 % (p = 4) and
# 3.7 % (p = 2) of the bisected crossing, the bars that test enforces.
#: λ_j's exponent for a mode the pattern has no first-order term along: χ² is
#: even in it at the current structure, so Δy ∝ A² and λ ∝ A⁴ (symmetry).
EVEN_EXPONENT = 4
#: λ_j's exponent for every other mode: Δy ∝ A, so λ ∝ A² (arithmetic).
LINEAR_EXPONENT = 2

#: Printed on every :class:`~rietx.schemas.results.DistortionTotal`: what a
#: linearised esd of a norm is, whatever the block's size (the bias of a norm
#: estimated near zero is the Rice distribution's: Rice (1944), *Bell Syst.
#: Tech. J.* **23**, 282).
ESD_LABEL = "linearised; undefined at A_τ = 0 and Rice-biased below about 2 esd"
#: Which sign the amplitudes carry.  Only relative signs are measured; a lost
#: parent operation maps the structure onto a domain with the same pattern and
#: the same A_τ (Perez-Mato, Orobengoa & Aroyo 2010, *Acta Cryst.* A**66**, 558,
#: p. 570), and no canonical domain is chosen here.
SIGN_CONVENTION = ("as fitted, unmapped: the domain is the start's (displacive_statement "
                   "seeds the first mode positive); signs relative to it are measured, and "
                   "A_tau is the same in every domain")

BlockKey = tuple[str, tuple[str, str, str], str]
_AMP = "phases.{}.distortion_modes.modes.{}.amplitude"


def distortion_blocks(phase) -> dict[BlockKey, list[int]]:
    """The irrep blocks of a phase on mode amplitudes: ``(irrep, k, isotropy_group)`` → mode indices.

    In the order the record lists them (the driving irrep first, as
    ``displacive_statement`` writes it).  Empty for a phase with no
    ``distortion_modes``.
    """
    out: dict[BlockKey, list[int]] = {}
    record = getattr(phase, "distortion_modes", None)
    if record is None:
        return out
    for i, m in enumerate(record.modes):
        out.setdefault((m.irrep, tuple(m.k), m.isotropy_group), []).append(i)
    return out


def hotelling_t2(amplitudes, covariance) -> float | None:
    """Aᵀ·Cov⁻¹·A, or ``None`` where Cov is not positive definite.

    Hotelling (1931), *Ann. Math. Statist.* **2**, 360.  Reported with m and no
    p: at a block whose truth may be zero χ² is even in the amplitudes, so this
    is about 4 × the likelihood ratio there (:data:`ESD_LABEL`'s neighbour in
    ``rietx.help``).
    """
    a = np.asarray(amplitudes, dtype=np.float64)
    try:
        chol = np.linalg.cholesky(np.asarray(covariance, dtype=np.float64))
    except np.linalg.LinAlgError:
        return None
    z = np.linalg.solve(chol, a)
    return float(z @ z)


def _block_covariance(table, theta, stderr_internal, correlation, paths) -> np.ndarray:
    """The amplitudes' covariance block, as every reported esd reads it (Bérar–Lelann included)."""
    return table.physical_covariance(theta, stderr_internal, correlation, paths)


def _largest_displacement(record, modes, amplitudes) -> float:
    """The largest |Σ_ν A_ν·v_νj| over the listed atoms, Å in the reference metric.

    The figure ISODISPLACE reports (Campbell, Stokes, Tanner & Hatch 2006,
    *J. Appl. Cryst.* **39**, 607), in the record's reference cell.
    """
    metric = _dist._cell_metric_from(record.reference_cell)
    v = np.array([record.modes[i].vectors for i in modes], dtype=np.float64)
    d = np.tensordot(np.asarray(amplitudes, dtype=np.float64), v, axes=1)
    return float(np.sqrt(np.max(np.einsum("ni,ij,nj->n", d, metric, d)))) if len(d) else 0.0


def distortion_totals(table, theta, structure, values, *, stderr_internal=None,
                      correlation=None) -> list[DistortionTotal] | None:
    """One :class:`~rietx.schemas.results.DistortionTotal` per irrep block, at fit close.

    ``values`` is the table's decode at ``theta``.  A_τ = ‖A_B‖ (Perez-Mato,
    Orobengoa & Aroyo 2010, eqs. 5–7); its esd is √(c·Cov·cᵀ) with c = A_B/A_τ,
    and T² = A_Bᵀ·Cov⁻¹·A_B, both on
    :meth:`~rietx.params.vector.ParameterTable.physical_covariance`, the
    covariance every reported esd is read from, which already carries the
    Bérar–Lelann factor.  Both are ``None`` without a covariance, where a
    block's column is one the data cannot see (``unmeasured_rows``), where the
    block's covariance is singular (a held amplitude), or, for the esd, at
    A_τ = 0.  ``None`` when no phase carries ``distortion_modes``.
    """
    out: list[DistortionTotal] = []
    any_modes = False
    for ip, phase in enumerate(structure.phases):
        record = getattr(phase, "distortion_modes", None)
        if record is None:
            continue
        any_modes = True
        action, tried = None, False
        for (irrep, k, group), modes in distortion_blocks(phase).items():
            paths = [_AMP.format(ip, i) for i in modes]
            a = np.array([values[p] for p in paths], dtype=np.float64)
            a_tau = float(np.linalg.norm(a))
            esd = t2 = None
            if stderr_internal is not None and (correlation is not None or len(paths) == 1):
                rows = [table._paths[p] for p in paths]
                blind = table.unmeasured_rows(theta, stderr_internal, rows)
                if not any(blind):
                    cov = _block_covariance(table, theta, stderr_internal, correlation, paths)
                    t2 = hotelling_t2(a, cov)
                    if t2 is not None and a_tau > 0.0:
                        c = a / a_tau
                        esd = float(math.sqrt(max(float(c @ cov @ c), 0.0)))
            if not tried:
                # a report field never aborts the fit it describes: a record
                # whose parent operations miss the reference structure has no
                # action to read ``driving`` from, so it is unanswered
                tried = True
                try:
                    action = _dist.amplitude_action(phase)
                except RuntimeError:
                    action = None
            driving = None
            if action is not None:
                generic = np.zeros(len(record.modes))
                generic[modes] = _dist._generic_seed(len(modes))[0]
                driving = len(action.stabiliser(generic)) == action.n_child
            out.append(DistortionTotal(
                phase=ip, irrep=irrep, k=k, isotropy_group=group, modes=list(modes),
                n_modes=len(modes), a_tau=a_tau, esd=esd, esd_label=ESD_LABEL, t2=t2,
                driving=driving,
                sign_convention=SIGN_CONVENTION,
                largest_displacement=_largest_displacement(record, modes, a)))
    return out if any_modes else None


def block_comparison(chi2_restricted: float, chi2_full: float, n_points: int, m: int, *,
                     esd_inflation_restricted: float | None,
                     esd_inflation_full: float | None,
                     chi2_red_full: float) -> tuple[float, float, float]:
    """(ΔBIC, Λ, Λ's p) for m parameters held at 0, from the two fits' numbers.

    ΔBIC is :func:`~rietx.report.delta_bic` at N_eff = N/f², f the
    **restricted** fit's ``esd_inflation``, as :func:`~rietx.report.compare_freed`
    charges it (Schwarz 1978, *Ann. Statist.* **6**, 461; Kass & Raftery 1995,
    *J. Am. Stat. Assoc.* **90**, 773).  Λ = (χ²_r − χ²_f)/(χ²_red·f²) with
    χ²_red and f both of the **full** fit: Hamilton's (1965, *Acta Cryst.*
    **18**, 502) F form, the χ² difference on rietx's esd scale, read against
    χ²_m for its upper-tail p.  Both χ² are the unreduced Σw·Δ².
    """
    from scipy.stats import chi2 as chi2_dist

    from ..optimize.statistics import effective_sample_size
    from .layer2 import delta_bic

    n_eff = effective_sample_size(n_points, esd_inflation_restricted)
    dbic = delta_bic(chi2_restricted, chi2_full, n_points, m, n_effective=n_eff)
    f_full = 1.0 if esd_inflation_full is None else float(esd_inflation_full)
    lam = (chi2_restricted - chi2_full) / (chi2_red_full * f_full * f_full)
    return dbic, lam, float(chi2_dist.sf(lam, m))


def detectability_target(chi2_red_full: float, esd_inflation: float | None, n_points: int,
                         m: int, bar: float) -> float:
    """The λ a block of m modes needs for its ΔBIC to reach ``bar``: χ²_red·f²·(m·ln N_eff + bar).

    To first order ΔBIC ≈ λ/(χ²_red·f²) − m·ln N_eff with λ on the file's σ
    (N_eff = N/f², f the restricted fit's, as the block's ΔBIC charges it; the
    penalty is Schwarz 1978, *Ann. Statist.* **6**, 461).  Its N_eff floor of 2
    is :func:`~rietx.report.delta_bic`'s own, so target and row charge one penalty.
    """
    from ..optimize.statistics import effective_sample_size

    f = 1.0 if esd_inflation is None else float(esd_inflation)
    n_eff = effective_sample_size(n_points, esd_inflation)
    return chi2_red_full * f * f * (m * math.log(max(n_eff, 2.0)) + bar)


def detectability_amplitude(lambdas, exponents, target: float, *,
                            probe: float) -> float | None:
    """A_det = min_j probe·(target/λ_j)^(1/p_j), Å; ``None`` where no mode moves the pattern.

    ``lambdas[j]`` is Σ((y(A_j = probe) − y)/σ)² for mode j, one predict
    each, and ``exponents[j]`` is p_j, 4 (:data:`EVEN_EXPONENT`) or 2
    (:data:`LINEAR_EXPONENT`).  Since λ_j(A) = λ_j(probe)·(A/probe)^p_j to
    leading order, each term is the amplitude at which mode j alone reaches
    ``target`` (:func:`detectability_target`), and the block's is the smallest.
    A ``target`` at or below 0 is reached at 0.  No published formula is
    ported: this is arithmetic on a leading power of the amplitude, whose
    exponents come from symmetry (Perez-Mato, Orobengoa & Aroyo 2010, *Acta
    Cryst.* A**66**, 558) and whose target is the BIC penalty (Schwarz 1978).
    """
    if target <= 0.0:
        return 0.0
    terms = [probe * (target / lam) ** (1.0 / p)
             for lam, p in zip(lambdas, exponents, strict=True) if lam > 0.0]
    return min(terms) if terms else None


# --------------------------------------------------------------------------
# the call
# --------------------------------------------------------------------------

def _is_key(item) -> bool:
    """A block key: a tuple, or the list a ``model_dump(mode="json")`` read back gives."""
    return isinstance(item, DistortionTotal) or (
        isinstance(item, (tuple, list)) and len(item) == 3 and isinstance(item[0], str)
        and isinstance(item[1], (tuple, list)))


def _resolve(structure, item) -> tuple[int, BlockKey]:
    """(phase index, key) for one block named by key or by its DistortionTotal."""
    if isinstance(item, DistortionTotal):
        key = (item.irrep, tuple(item.k), item.isotropy_group)
        if not 0 <= item.phase < len(structure.phases):
            raise ValueError(f"the DistortionTotal names phase {item.phase}, but this "
                             f"refinement has {len(structure.phases)}; it is from another fit")
        phases = [item.phase]
    else:
        irrep, k, group = item
        key = (str(irrep), tuple(str(c) for c in k), str(group))
        phases = [ip for ip, ph in enumerate(structure.phases) if key in distortion_blocks(ph)]
        if len(phases) > 1:
            raise ValueError(
                f"block {key} is in phases {phases}; name it by its DistortionTotal, "
                "which carries the phase")
    if not phases or key not in distortion_blocks(structure.phases[phases[0]]):
        known = sorted({b for ph in structure.phases for b in distortion_blocks(ph)})
        raise ValueError(f"no irrep block {key}; the blocks are {known}")
    return phases[0], key


def held_sets(structure, hold, free=None) -> list[tuple[int, list[BlockKey]]]:
    """The held sets a ``hold`` argument names, each as (phase, keys).

    ``hold`` is ``None`` (every block of every phase that is not all
    parent-invariant and whose amplitudes all varied in the fit, i.e. every
    path of it in ``free``, each alone) or a list whose items are a block or a
    set of blocks held together; a block is a ``(irrep, k, isotropy_group)``
    key (a tuple, or the list a JSON round trip gives) or its
    :class:`~rietx.schemas.results.DistortionTotal`.  With ``free=None`` every
    amplitude counts as varied.
    """
    if hold is None:
        out = []
        for ip, ph in enumerate(structure.phases):
            for key, modes in distortion_blocks(ph).items():
                if all(ph.distortion_modes.modes[i].parent_invariant for i in modes):
                    continue
                if free is not None and not all(_AMP.format(ip, i) in free for i in modes):
                    continue
                out.append((ip, [key]))
        return out
    out = []
    for item in hold:
        members = [item] if _is_key(item) else list(item)
        if not members:
            raise ValueError("an empty set of blocks holds nothing")
        resolved = [_resolve(structure, b) for b in members]
        phases = {p for p, _ in resolved}
        if len(phases) != 1:
            raise ValueError(f"a held set spans phases {sorted(phases)}; hold one phase's blocks")
        keys = list(dict.fromkeys(k for _, k in resolved))
        out.append((phases.pop(), keys))
    return out


def _free_paths(result) -> list[str]:
    return [p.path for p in result.parameters if p.vary]


def _fit_one_stage(ref, data, free: Iterable[str], *, mode, limits, name: str):
    from ..strategy.staged import RefinementPlan, Stage

    plan = RefinementPlan(stages=[Stage(name=name, turn_on=list(free))])
    return ref.fit(data, mode=mode, plan=plan, two_theta_limits=limits, telemetry=False)


def _amplitudes(phase) -> np.ndarray:
    return np.array([m.amplitude.value for m in phase.distortion_modes.modes], dtype=np.float64)


def _a_det(restricted, phase: int, modes: list[int], target: float,
           probe_amplitude: float) -> float | None:
    """A_det of ``modes`` at the restricted optimum: one predict per mode at the probe."""
    result = restricted.result_
    tt = np.asarray(result.two_theta)
    sigma = np.asarray(result.sigma)
    y0 = np.asarray(restricted.predict(tt))
    even = _dist.amplitude_action(restricted.structure.phases[phase]).even(
        _amplitudes(restricted.structure.phases[phase]))
    lambdas, exponents = [], []
    probe = restricted._trial(record=False)
    for i in modes:
        path = _AMP.format(phase, i)
        probe.set_values({path: probe_amplitude})
        y = np.asarray(probe.predict(tt))
        probe.set_values({path: 0.0})
        lambdas.append(float(np.sum(((y - y0) / sigma) ** 2)))
        exponents.append(EVEN_EXPONENT if even[i] else LINEAR_EXPONENT)
    return detectability_amplitude(lambdas, exponents, target, probe=probe_amplitude)


def _test_one(full, data, phase: int, keys: list[BlockKey], bar: float | None,
              probe: float | None = None):
    """One held set's row, and the restricted refinement it came from."""
    from .layer2 import compare_freed

    result = full.result_
    blocks = distortion_blocks(full.structure.phases[phase])
    modes = sorted(i for k in keys for i in blocks[k])
    paths = [_AMP.format(phase, i) for i in modes]
    free = _free_paths(result)
    missing = [p for p in paths if p not in free]
    if missing:
        raise ValueError(
            f"the full fit did not free {missing[0]}"
            + (f" and {len(missing) - 1} more" if len(missing) > 1 else "")
            + f" of block(s) {keys}, so holding them at 0 compares nothing; free every "
            "amplitude of a block the full fit is to be compared on")
    restricted = full._trial(record=False)
    restricted.set_values({p: 0.0 for p in paths})
    t0 = time.perf_counter()
    _fit_one_stage(restricted, data, [p for p in free if p not in set(paths)],
                   mode=result.mode, limits=full._two_theta_limits, name="restricted")
    wall = time.perf_counter() - t0
    cmp = compare_freed(restricted, full)
    fs = result.statistics
    dbic, lam, p = block_comparison(
        cmp.chi2_restricted, cmp.chi2_full, cmp.n_points, cmp.n_added,
        esd_inflation_restricted=cmp.esd_inflation, esd_inflation_full=fs.esd_inflation,
        chi2_red_full=fs.chi2)
    a_det = None
    if bar is not None:
        target = detectability_target(fs.chi2, cmp.esd_inflation, cmp.n_points,
                                      len(modes), bar)
        a_det = _a_det(restricted, phase, modes, target, probe)
    row = DistortionBlockTest(
        phase=phase, held=[(i, k, g) for i, k, g in keys], m=cmp.n_added,
        n_points=cmp.n_points, chi2_restricted=cmp.chi2_restricted, chi2_full=cmp.chi2_full,
        esd_inflation_restricted=cmp.esd_inflation, esd_inflation_full=fs.esd_inflation,
        chi2_red_full=fs.chi2, delta_bic=dbic, lambda_=lam, lambda_p=p, a_det=a_det,
        wall_s=wall)
    return row, restricted


def _restart(full, restricted, data, phase: int, keys: list[BlockKey]):
    """The full model refitted from ``restricted``'s optimum, the held blocks re-seeded."""
    blocks = distortion_blocks(restricted.structure.phases[phase])
    seed = {}
    for key in keys:
        modes = blocks[key]
        direction = _dist._generic_seed(len(modes))[0] * _dist.DISTORTION_SEED
        seed.update({_AMP.format(phase, i): float(v) for i, v in zip(modes, direction)})
    new = restricted._trial(record=False)
    new.set_values(seed)
    _fit_one_stage(new, data, _free_paths(full.result_), mode=full.result_.mode,
                   limits=full._two_theta_limits, name="restart")
    return new


def distortion_block_tests(refinement, data, *, hold=None,
                           detectability_bar: float | None = None,
                           detectability_probe: float | None = None) -> DistortionBlockTests:
    """Refit with blocks held at 0 and compare, for any blocks or sets the caller names.

    ``refinement`` has been fitted on ``data`` with the blocks' amplitudes
    free.  Each held set gets one restricted refit: its amplitudes set to 0,
    everything else the full fit freed free again, from the full optimum, one
    stage.  The row reads it against the full fit through
    :func:`~rietx.report.compare_freed` (:func:`block_comparison` for the
    numbers).  With ``detectability_bar`` the row also carries A_det at that
    bar (:func:`detectability_amplitude`; λ_j at the restricted optimum, p_j
    from the symmetry of that structure, :meth:`AmplitudeAction.even
    <rietx.crystallography.representation.distortion.AmplitudeAction.even>`),
    and ``None`` computes none: the bar has no default.  ``detectability_probe``
    (Å) is the amplitude each mode's one predict is made at; it is the
    caller's, **required with a bar** (``ValueError`` otherwise), because
    λ_j ∝ A^p_j holds to leading order only and no one value has been shown to
    hold the error under a stated bar for every block.  ``hold=None`` holds
    every block that is not parent-invariant **and that the fit freed
    throughout**; a named block the fit did not free raises.

    **Restart.**  If any restricted χ² lies below the full χ² by more than the
    solver's own stopping tolerance (a relative ``ftol``,
    :data:`rietx.optimize.lm.FTOL`, the scale two converged fits of one model
    agree to; on a block whose true amplitude is zero the restricted fit lands
    within it, often just below), the full fit had not reached its optimum.  The full model is refitted from the lowest such
    restricted optimum with its held blocks re-seeded (``DISTORTION_SEED``
    along a generic direction of each block, the statement's rule), and every
    held set is tested again against it.  The full χ² falls by more than that
    tolerance at each restart, so the loop ends (it has no cap); a restart that
    does not lower it is recorded and ends the loop, the rows then standing
    against the fit they were measured on.
    """
    from ..optimize.lm import FTOL

    if refinement.result_ is None:
        raise RuntimeError("run a fit with the blocks free before comparing them")
    if detectability_bar is not None and detectability_probe is None:
        raise ValueError("detectability_bar needs detectability_probe, the amplitude (Å) of "
                         "the one predict per mode A_det is read from; it has no default")
    sets = held_sets(refinement.structure, hold, set(_free_paths(refinement.result_)))
    full = refinement
    restarts: list[DistortionRestart] = []
    restarted = None
    while True:
        rows, refits = [], []
        for phase, keys in sets:
            row, restricted = _test_one(full, data, phase, keys, detectability_bar,
                                        detectability_probe)
            rows.append(row)
            refits.append((restricted, phase, keys))
        below = [(r, f) for r, f in zip(rows, refits)
                 if r.chi2_restricted < r.chi2_full * (1.0 - FTOL)]
        if not below:
            break
        row, (restricted, phase, keys) = min(below, key=lambda x: x[0].chi2_restricted)
        new = _restart(full, restricted, data, phase, keys)
        from ..optimize.statistics import _chi2_absolute

        after = _chi2_absolute(new.result_.statistics)
        lowered = after < row.chi2_full * (1.0 - FTOL)
        restarts.append(DistortionRestart(
            held=row.held, chi2_full_before=row.chi2_full,
            chi2_restricted=row.chi2_restricted, chi2_full_after=after, lowered=lowered))
        if not lowered:
            break
        full = new
        restarted = new.result_
    return DistortionBlockTests(tests=rows, restarts=restarts,
                                detectability_bar=detectability_bar,
                                detectability_probe=detectability_probe,
                                restarted_result=restarted)
