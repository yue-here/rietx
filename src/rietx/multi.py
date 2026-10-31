"""Multi-histogram joint refinement (WP-0308).

Refine one shared :class:`~rietx.schemas.structure.Structure` against several
patterns at once — different wavelengths, geometries or temperatures — each with
its own :class:`~rietx.schemas.instrument.Instrument`.  The histograms are
stacked into one residual (Von Dreele, 1997, J. Appl. Cryst. 30, 517): shared
structural parameters (cell, coordinates, occupancies, ADPs …) draw information
from every pattern, while each pattern keeps its own scale, background, zero and
resolution.  See :mod:`rietx.params.multi` for the parameter-sharing map and
:func:`rietx.optimize.least_squares.run_multi_least_squares` for the stacked
solve.

Rietveld mode only: Le Bail / Pawley intensities are per-pattern empirical
extractions, not shared quantities, so a multi-histogram fit of them is just
independent single fits — not the joint-residual point of this module.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import re
from contextlib import contextmanager

import numpy as np

from . import runs
from .backend.api import backend_dtype_note
from .crystallography.symmetry import reflection_label_row
from .crystallography.twins import merge_site_twins
from .history.events import _attach_progress, as_event_stream
from .model.components import EXTRA_TICK_KEY
from .model.forward import (
    PHASE_SUPPORT_SIGMA,
    compile_model,
    recorded_window_tol,
    window_loss,
)
from .model.microstructure import microstructure_table
from .optimize.blocked import BlockJacobian
from .optimize.cancel import RefinementCancelled
from .optimize.least_squares import (
    DEFAULT_SOLVER,
    SOLVERS,
    _longest_line_wavelength,
    _multi_closures,
    covariance_jacobian,
    rechart_outcome,
    run_multi_least_squares,
)
from .optimize.statistics import (
    background_absorption,
    compute_statistics,
    roughness_absorption,
)
from .params.multi import (
    SIZE_LAMBDA_POWER,
    MultiParameterTable,
    SharingMap,
    _longest_wavelength,
    _unscoped,
)
from .params.parametric import (
    FORM_TEST_LEVEL,
    coefficient_rows,
    form_tests,
    parametric_equation,
)
from .params.vector import is_variable_path
from .refine import (
    _DISPLACEMENT_PATH,
    _PHASE_PREFIX,
    _VERSION,
    _WAVELENGTH_PINNED_BY_HELD_HISTOGRAM,
    SCALE_B_SEPARATION_FLOOR,
    SCALE_B_STEP,
    CellReset,
    _absorption_diagnostics,
    _absorption_record,
    _air_scatter_undeclared_diagnostics,
    _axis_in_crystal_axes,
    _capillary_offset_diagnostics,
    _cell_runaway_diagnostic,
    _cell_runaway_withheld,
    _column_separation,
    _constraint_diagnostics,
    _covariance_diagnostics,
    _data_support_diagnostics,
    _declared_wavelengths,
    _degenerate_cell_diagnostics,
    _dispersion_diagnostics,
    _displacement_columns,
    _escaped_cell_paths,
    _extra_peak_diagnostics,
    _extra_peak_tick_support,
    _far_from_data_diagnostics,
    _fixed_literal_diagnostics,
    _flat_moment_scan,
    _frozen_compile_diagnostics,
    _guard_diagnostics,
    _harmonic_diagnostics,
    _held_scale_phases,
    _judge_magnetic_groups,
    _lineless_phases,
    _low_angle_diagnostics,
    _max_iter_diagnostics,
    _occupancy_flag_diagnostics,
    _onto_flat_meridian,
    _origin_diagnostics,
    _phase_agreement,
    _phase_support_diagnostics,
    _quantify_phases,
    _radiation,
    _reflection_tick_support,
    _refuse_without_phases,
    _reported_support_sigma,
    _resolve_specimen_absorption,
    _resonant_absorber_diagnostics,
    _restore_phase_cells,
    _restrained_scale_phases,
    _roughness_regime_diagnostics,
    _scale_b_ridge_diagnostics,
    _site,
    _size_flag_diagnostics,
    _species_fallback_diagnostics,
    _strain_flag_diagnostics,
    _symmetry_silence_diagnostics,
    _uncorrected,
    _unknown_path_diagnostics,
    _unmeasured_phases,
    _utcnow,
    _vars_driven_cell_escapes,
    _wavelength_calibration_diagnostics,
    _width_census_diagnostics,
    _width_twin_flats,
    _window_loss_diagnostics,
)
from .report.magnetic import moment_angle_stationary_diagnostics
from .report.schemas import THRESHOLDS_VERSION
from .schemas.common import Diagnostic, Provenance
from .schemas.instrument import Instrument
from .schemas.parametric import (
    CoordinateTable,
    ParametricEquation,
    ParametricFormReading,
    ParametricFormTest,
)
from .schemas.pattern import PatternData, require_two_theta
from .schemas.plan import check_phase_support_sigma
from .schemas.results import (
    HistogramResult,
    Identifiability,
    RefinedParameter,
    RefinementResult,
    StageResult,
)
from .schemas.structure import Structure
from .strategy.staged import (
    BACKGROUND_ABSORPTION_GUARD,
    FLAT_DIRECTION_RHO,
    PLAN_PRESETS,
    ROUGHNESS_ABSORPTION_GUARD,
    GuardFinding,
    GuardReport,
    RefinementPlan,
    _exact_active_bounds,
    bound_findings,
    check_adp_positive_definite,
    check_biso_negative,
    check_biso_plausible,
    check_discarded_directions,
    check_hump_width,
    check_resolution_positive,
    check_resolution_supported,
    check_stephens_positive,
    check_texture_positive,
)

#: A diagnostic reported **once per histogram**, on
#: :attr:`HistogramResult.diagnostics`: a fact about one pattern — its
#: radiation, its instrument, its counts, or the fit's agreement with it.
HISTOGRAM = "histogram"
#: Reported **once, at top level**, and a fact about the shared structure:
#: one specimen, one answer, whatever radiation looks at it.
SPECIMEN = "specimen"
#: Reported **once, at top level**, and a fact about the joint solve or the
#: plan rather than about any one pattern or the structure alone.
FIT = "fit"
#: **Not computed** by a joint fit; the reason beside it says why.
ABSENT = "absent"

#: Which answer a joint fit gives each diagnostic helper (WP-1344) — the
#: diagnostics twin of :data:`~rietx.params.multi.SIZE_LAMBDA_POWER`, and data
#: for its reason: a helper added to ``refine.py`` without a row here fails
#: ``tests/test_multi_diagnostics.py``, and so does a row this module's
#: ``_build_result`` does not honour (a :data:`HISTOGRAM` helper must be called
#: inside the per-histogram loop, a :data:`SPECIMEN` or :data:`FIT` one outside
#: it, an :data:`ABSENT` one nowhere).  Keys are every ``_*_diagnostics``
#: function defined in :mod:`rietx.refine` and in this module; a helper reached
#: only through another (``_quantify_phases`` calls the two QPA ones) is
#: placed by where its caller is.  ``_guard_diagnostics`` is a converter over a
#: ``GuardReport`` and so sits at both levels, one report per level.
#:
#: The radiation-keyed rows are the reason this exists: before it the joint
#: path named ``_dispersion_diagnostics``, ``_resonant_absorber_diagnostics`` and
#: ``_species_fallback_diagnostics`` nowhere, so a mixed X-ray + neutron fit
#: raised none of the three while the vocabulary claimed the checks (WP-1076's
#: "a declared name is a claim", one rank up).  Each asks one histogram's
#: source, so each belongs to the histogram, never to the fit.
DIAGNOSTIC_SCOPES: dict[str, tuple[tuple[str, ...], str]] = {
    # -- per histogram: the pattern's radiation -------------------------------
    "_dispersion_diagnostics": (
        (HISTOGRAM,), "f'/f'' is keyed on this histogram's source kind and λ"),
    "_resonant_absorber_diagnostics": (
        (HISTOGRAM,), "a complex b matters to a neutron histogram only"),
    "_species_fallback_diagnostics": (
        (HISTOGRAM,), "the Waasmaier-Kirfel lookup is the X-ray amplitude; a "
                      "neutron histogram resolves species through another table"),
    "_harmonic_diagnostics": (
        (HISTOGRAM,), "a λ/n line is declared on one histogram's source"),
    "_wavelength_calibration_diagnostics": (
        (HISTOGRAM,), "each histogram declares and may free its own λ"),
    # -- per histogram: the pattern's instrument and specimen mount ----------
    "_absorption_diagnostics": (
        (HISTOGRAM,), "µR/µt is per wavelength and geometry"),
    "_capillary_offset_diagnostics": (
        (HISTOGRAM,), "each histogram has its own geometry and locked entries"),
    "_roughness_regime_diagnostics": (
        (HISTOGRAM,), "a roughness model is declared on one instrument and "
                      "judged over that histogram's range"),
    "_extra_peak_diagnostics": (
        (HISTOGRAM,), "a declared peak lives on one instrument's "
                      "extra_components, against that histogram's ticks"),
    "_strain_flag_diagnostics": (
        (HISTOGRAM,), "read off each histogram's own copy (λ-free, repeated "
                      "so a histogram's list is complete on its own)"),
    "_size_flag_diagnostics": (
        (HISTOGRAM,), "read against each histogram's own λ; a disagreement "
                      "between rows would mean the WP-1131 scaling came undone"),
    "_width_census_diagnostics": (
        (HISTOGRAM,), "the census is one pattern's channels against one "
                      "instrument's fitted widths (WP-1336); a joint fit that "
                      "pooled it could not say which declared profile is wrong"),
    # -- per histogram: the pattern's counts and the fit's agreement with them
    "_data_support_diagnostics": (
        (HISTOGRAM,), "the sampling and dead-channel halves are facts about one "
                      "measurement.  The ratio half (DATA_SUPPORT_LOW) is "
                      "deliberately not asked: support=None is passed, because "
                      "McCusker's observations-per-parameter has no agreed "
                      "joint definition — one histogram's reflections against "
                      "the shared columns would warn on a fit the other "
                      "histograms support (WP-1341's territory)"),
    "_far_from_data_diagnostics": (
        (HISTOGRAM,), "Rwp against one pattern; a pooled Rwp can hide one "
                      "histogram the model does not describe"),
    "_low_angle_diagnostics": (
        (HISTOGRAM,), "the region below one pattern's first reflection"),
    "_air_scatter_undeclared_diagnostics": (
        (HISTOGRAM,), "one histogram's residual against its own background"),
    "_qpa_esd_unavailable_diagnostics": (
        (HISTOGRAM,), "through _quantify_phases, which partitions one "
                      "histogram's scales"),
    "_qpa_unavailable_diagnostics": (
        (HISTOGRAM,), "through _quantify_phases, as above"),
    # -- both: a converter ----------------------------------------------------
    "_guard_diagnostics": (
        (HISTOGRAM, FIT), "a GuardReport converter: background absorption and "
                          "hump width per histogram, correlations, bounds and "
                          "ADPs for the joint solve"),
    # -- once: the shared structure ------------------------------------------
    "_symmetry_silence_diagnostics": (
        (SPECIMEN,), "a snapped site or an assumed setting is a fact about the "
                     "one structure, asked of it as declared, before any stage"),
    "_occupancy_flag_diagnostics": (
        (SPECIMEN,), "an occupancy is the one structure's, so a refined value "
                     "past a full site is told once, a per-histogram one in "
                     "each histogram that holds it (WP-2028, _occupancy_once)"),
    "_origin_diagnostics": (
        (SPECIMEN,), "each histogram's table derives the same floating-origin "
                     "hold from its copy of the one structure (WP-1912); asked "
                     "of each, through _joint_origin_findings, and a shared "
                     "coordinate told once"),
    # -- once: the joint solve and the plan ------------------------------------
    "_constraint_diagnostics": (
        (FIT,), "the answer-producing stage's one joint solve"),
    "_covariance_diagnostics": (
        (FIT,), "one covariance, of the stacked residual"),
    "_degenerate_cell_diagnostics": (
        (FIT,), "a probe count summed over the joint search"),
    "_unknown_path_diagnostics": (
        (FIT,), "a stage's globs are the plan's, matched against every table"),
    "_window_loss_diagnostics": (
        (FIT,), "one finding per stage, read off the record, which keeps the "
                "worst histogram's loss (WP-2047)"),
    "_max_iter_diagnostics": (
        (FIT,), "a stage's budget is spent by the one joint solve"),
    "_frozen_compile_diagnostics": (
        (FIT,), "one finding per fit naming the histogram whose own χ² moved "
                "most: a pooled χ² would hide one pattern (WP-1421)"),
    "_phase_support_diagnostics": (
        (FIT,), "a phase is unseen only when every histogram misses it, so the "
                "statement is joint; a phase held in some patterns only is "
                "_per_pattern_hold_diagnostics' (WP-2028)"),
    "_per_pattern_hold_diagnostics": (
        (FIT,), "joint-only (WP-2028): the answer's support hold kept a "
                "phase's hist.h structure in the patterns that cannot see "
                "it; one finding per phase, naming every such pattern, read "
                "off StageResult.held"),
    "_scale_b_ridge_diagnostics": (
        (FIT,), "the probe stacks every histogram, since a phase's scales are "
                "per histogram and its displacement parameters shared (WP-1534)"),
    "_size_sharing_diagnostics": (
        (FIT,), "joint-only: what the sharing map did to a size across λ"),
    "_unreached_histogram_diagnostics": (
        (FIT,), "joint-only, and the plan's (WP-1414): a stage's reach is "
                "decided before any histogram is compiled"),
    "_parametric_range_diagnostics": (
        (FIT,), "joint-only (WP-1325): one declaration spans its subset, so a "
                "dependent leaving its bounds is told once per declaration, "
                "naming every pattern"),
    "_parametric_form_diagnostics": (
        (FIT,), "joint-only (WP-1325): a declaration's form is tested against "
                "every pattern of its subset at once"),
    "_parametric_unseen_diagnostics": (
        (FIT,), "joint-only (WP-1325): one equation sets its target across its "
                "subset, so the patterns that cannot see it are told once per "
                "declaration, naming each"),
    "_fixed_literal_diagnostics": (
        (FIT,), "a plan read (#803, WP-1341), through _joint_fixed_literals: "
                "each histogram's table is asked under the joint matching rule, "
                "so a literal reports on a histogram where it matched a fixed "
                "row and STAGE_FREED_NOTHING on one where it matched none, "
                "never both on one histogram, and a shared row fixed in "
                "several tables is one finding"),
    # -- deliberately not computed ---------------------------------------------
    "_hold_diagnostics": (
        (ABSENT,), "a joint fit has no hold verb: the one hold its tables "
                   "carry is the floating origin's, which HOLD_BLOCKED_PLAN "
                   "leaves to _origin_diagnostics, so it would report "
                   "nothing"),
    "_pawley_unresolved_diagnostics": (
        (ABSENT,), "a joint fit is Rietveld-only (fit refuses pawley)"),
    "_pawley_off_data_diagnostics": (
        (ABSENT,), "a joint fit is Rietveld-only (fit refuses pawley)"),
    "_restraint_tension_diagnostics": (
        (ABSENT,), "soft restraints are refused in a joint fit "
                   "(run_multi_least_squares), so there is no tension to report"),
    "_restraint_pairs_stale_diagnostics": (
        (ABSENT,), "soft restraints are refused in a joint fit "
                   "(run_multi_least_squares), so there is no anti-bump list "
                   "to have gone stale (WP-1809)"),
    "_stage_order_diagnostics": (
        (ABSENT,), "not called from multi.py: the magnetic-width ordering rule "
                   "(WP-1343) is checked by Refinement.fit and run_stage, and "
                   "the joint path has no plan check for it"),
    "_held_moment_diagnostics": (
        (ABSENT,), "not called from multi.py: the plan read that names a moment no "
                   "stage frees (WP-1418) is asked by Refinement.fit, and the joint "
                   "path has no plan check for it"),
    "_moved_moment_diagnostics": (
        (ABSENT,), "not called from multi.py: the moment's shift between the "
                   "width preset's rungs (WP-1343) is read by "
                   "Refinement._run_plan, which a joint fit does not run"),
}

#: The same rule one rank down, over :class:`~rietx.strategy.staged.GuardReport`'s
#: finding lists — ``_guard_diagnostics`` sits at both levels above because it
#: converts whatever report it is handed, so *which* guards a joint fit runs is
#: decided here, per field.  Keys are every ``list[GuardFinding]`` field of the
#: report; ``tests/test_multi_diagnostics.py`` holds the set equal and reads
#: where ``multi.py`` fills each one.  Before WP-1344 five of the eleven were
#: never filled on this path (strain cone, resolution sign and support, Biso
#: plausibility, flat directions), and a sixth (roughness absorption) neither.
GUARD_SCOPES: dict[str, tuple[tuple[str, ...], str]] = {
    "background_correlations": (
        (HISTOGRAM, FIT), "one histogram's Jacobian rows against its own "
                          "background columns, scoped hist.h; the top-level "
                          "report carries the same findings, as it did before "
                          "this table"),
    "roughness_correlations": (
        (HISTOGRAM,), "a roughness model is one instrument's, screened on "
                      "that histogram's Jacobian rows as the background is"),
    "narrow_humps": (
        (HISTOGRAM,), "a declared hump is one instrument's background"),
    "nonpositive_resolution": (
        (HISTOGRAM,), "Γ_G² is one instrument's quadratic over its own range"),
    "unsupported_resolution": (
        (HISTOGRAM,), "whether a pattern is predominantly Lorentzian is a fact "
                      "about that pattern — the neutron case McCusker exempts "
                      "is one histogram, not the fit"),
    "nonpositive_adps": (
        (SPECIMEN,), "the structure's tensors, asked of every histogram's "
                     "table, since a U can be per histogram (WP-1325): one "
                     "finding per site, a per-histogram site named hist.h "
                     "(WP-2028, _specimen_once)"),
    "large_biso": (
        (SPECIMEN,), "the Lindemann bound is the cell's, and a B or a cell "
                     "can be per histogram: asked of every histogram's "
                     "compile, one finding per path (WP-2028)"),
    "negative_biso": (
        (SPECIMEN,), "the structure's B values, asked of every histogram's "
                     "compile, one finding per path, a per-histogram B named "
                     "hist.h (WP-2028)"),
    "nonpositive_strain": (
        (SPECIMEN,), "one coefficient set, but each histogram measures its own "
                     "directions: a phase is named once, from the first "
                     "histogram whose reflections leave the cone"),
    "nonpositive_texture": (
        (SPECIMEN,), "one coefficient set, sampled at each histogram's own ψ: "
                     "a phase is named once, from the first histogram where "
                     "P leaves the physical set (WP-1960)"),
    "high_correlations": ((FIT,), "one correlation matrix, of the joint solve"),
    "flat_directions": ((FIT,), "read off the same matrix, beside the correlation"),
    "discarded_directions": ((FIT,), "the joint normal matrix's own cut, read "
                                     "off the joint Jacobian"),
    "at_bounds": ((FIT,), "the joint θ's bounds"),
}


def _normalize_limits(ttl, n: int) -> list[tuple[float, float] | None]:
    if ttl is None:
        return [None] * n
    if (isinstance(ttl, tuple) and len(ttl) == 2
            and all(isinstance(x, (int, float)) for x in ttl)):
        return [ttl] * n  # one range applied to every histogram
    ttl = list(ttl)
    if len(ttl) != n:
        raise ValueError(f"two_theta_limits has {len(ttl)} entries for {n} histograms")
    return ttl


def _joint_unsupported_phases(models, mtable,
                              sigma: float | None = PHASE_SUPPORT_SIGMA
                              ) -> list[set[int]]:
    """Per histogram, the phases below support in it (WP-1301).

    **Per histogram, because a path can be** (WP-1325).  Whether the data sees
    an entry depends on where it lives, and :func:`_unseen` asks that of each
    entry a column reaches.  A shared cell lives in every histogram, so it is
    flat only where its phase is unseen in all of them: a phase invisible in
    one histogram and plain in another is seen by the joint fit that shares
    its cell, the reason ``_freeze_cell_windows_multi`` gives.  A cell made
    per-histogram (``SharingMap.per_histogram``, the series and library case)
    lives in one pattern, so it is flat wherever its own pattern cannot see
    the phase.  Decided per phase, a two-pattern joint fit held nothing of a
    phase absent from one pattern and present in the other
    (``test_a_joint_series_fit_holds_a_vanished_phase_in_its_own_pattern``).

    The screen ``CompiledModel.phase_support`` alone, at the stage start and
    at the answer alike.  The single fit's answer reads the scale's
    significance (``refine._answer_significance``, WP-1523); the joint path
    deliberately does not, because its report is WP-1341's to define.

    ``sigma`` is the plan's ``phase_support_sigma`` (WP-2002, B1).  ``None``
    calls no phase unseen anywhere, so nothing is held, released or restored.
    """
    if sigma is None:
        return [set() for _ in models]
    per_model = [m.phase_support(t.decode(t.x0()))
                 for m, t in zip(models, mtable.tables, strict=True)]
    return [{ip for ip, s in enumerate(support) if s < sigma}
            for support in per_model]


def _joint_lineless_phases(models) -> list[set[int]]:
    """Per histogram, the phases with no reflection in its fitted range
    (``refine._lineless_phases``, WP-1958)."""
    return [_lineless_phases(m) for m in models]


def _joint_flat_scales(models, mtable, lineless: list[set[int]]
                       ) -> list[set[int]]:
    """Of ``lineless``, per histogram, the phases whose scale no weighted
    ``ValueRestraint`` pulls (``refine._restrained_scale_phases``)."""
    return [n - _restrained_scale_phases(m, t)
            for m, t, n in zip(models, mtable.tables, lineless, strict=True)]


def _joint_unmeasured_phases(models, mtable,
                             stage_results: list[StageResult]
                             ) -> list[set[int]]:
    """Per histogram, the phases the answer left without a fraction.

    ``refine._unmeasured_phases``' reading per histogram, with the one thing a
    joint fit adds (#1103): **a shared scale that another histogram measures
    counts as measured everywhere it is shared**, since its value is then the
    data's.  The stage does not hold such a scale (the hold needs every
    histogram out of range), so only the answer's recount can put it here,
    and that recount drops a phase whose scale is shared and which some
    histogram has a line of.
    """
    lineless = _joint_lineless_phases(models)
    out = []
    for h, m in enumerate(models):
        own = {ip for ip in lineless[h]
               if not (mtable.sharing.is_shared(f"phases.{ip}.scale")
                       and any(ip not in lineless[g]
                               for g in range(len(models)) if g != h))}
        out.append(_unmeasured_phases(m, stage_results, hist=h, lineless=own))
    return out


def _unseen(mtable, name: str, absent: list[set[int]],
            lineless: list[set[int]] | None = None) -> bool:
    """Whether ``name``, a reached entry as the joint table spells it, is
    structure of a phase below support wherever the entry lives.

    A ``hist.{h}.`` entry lives in histogram h, a bare (shared) one in every
    histogram.  A phase's ``scale`` is unseen only where ``lineless`` puts the
    phase out of range wherever the scale lives (WP-1958); otherwise never,
    for :func:`~rietx.refine._only_moves`' reason: it is the one direction
    that is not flat.
    """
    bare = _unscoped(name)
    m = _PHASE_PREFIX.match(bare)
    if m is None:
        return False
    if bare.endswith(".scale"):
        if lineless is None:
            return False
        absent = lineless
    ip = int(m.group(1))
    owner = mtable._owner(name)
    return all(ip in a for a in (absent if owner is None else [absent[owner]]))


def _only_unseen(mtable, reached: list[str], absent: list[set[int]],
                 lineless: list[set[int]] | None = None) -> bool:
    """:func:`~rietx.refine._only_moves` for joint entries: every model entry
    the column reaches is :func:`_unseen`.  All, never any; a variable is
    dropped before the test; a column reaching no model entry is not held."""
    moved = [q for q in reached if not is_variable_path(_unscoped(q))]
    return bool(moved) and all(_unseen(mtable, q, absent, lineless)
                               for q in moved)


def _joint_column_reach(mtable) -> dict[str, list[str]]:
    """Per joint column, every entry it moves in any histogram that carries it.

    :meth:`~rietx.params.vector.ParameterTable.column_reach` across the stack
    (WP-1342's reading of **C**), each moved entry spelled as the joint result
    spells it (``mtable._canonical``): a shared column is one name in every
    table, so a parametric coefficient (WP-1325) driving each pattern's own
    cell reaches ``hist.0.phases.0.cell.a``, ``hist.1.phases.0.cell.a`` …
    rather than one bare name standing for all of them.  With no parametric equation every
    column reaches itself and its symmetry dependents, which share its phase,
    so every freeze reading this decides exactly what the old name test did.
    """
    names = mtable.free_paths
    out: dict[str, dict[str, None]] = {p: {} for p in names}
    for h, table in enumerate(mtable.tables):
        reach = table.column_reach()
        for c, k in enumerate(mtable.col_map(h)):
            local = table.free_paths[c]
            moved = out[names[int(k)]]
            for q in reach.get(local, [local]):
                moved[mtable._canonical(h, q)] = None
    return {p: list(v) for p, v in out.items()}


def _joint_reach_beyond_self(columns: list[str], reach: dict[str, list[str]]
                             ) -> dict[str, list[str]]:
    """``refine._reach_beyond_self`` for joint columns: the record half of a
    hold, read before ``set_vary`` takes the columns out of θ."""
    out = {}
    for c in columns:
        other = [q for q in reach.get(c, [c]) if q != c]
        if other:
            out[c] = other
    return out


def _joint_phases_reached(columns: list[str], reach: dict[str, list[str]]) -> set[int]:
    """Every phase a column names or moves (``refine._phases_reached``, scoped)."""
    return {int(m.group(1)) for c in columns for name in (c, *reach.get(c, ()))
            if (m := _PHASE_PREFIX.match(_unscoped(name)))}


def _unsupported_paths_multi(mtable, absent: list[set[int]],
                             reach: dict[str, list[str]] | None = None,
                             lineless: list[set[int]] | None = None) -> list[str]:
    """The joint columns that move nothing the data can see.

    ``absent`` is :func:`_joint_unsupported_phases`' answer, one set per
    histogram.  **Columns, never names** (WP-1342), the single fit's
    :func:`~rietx.refine._unsupported_phase_paths` across the stack: a
    parametric coefficient ``vars.X_j`` (WP-1325) drives a phase's cells in
    every subset histogram while its own name carries no phase, so a name
    prefix could neither hold it nor see it.  :func:`_only_unseen` decides
    over what each column reaches in **every** histogram, each entry judged
    where it lives: all, never any, the variable itself dropped first, and the
    phase's scale only where ``lineless`` (one set per histogram) puts the
    phase out of range wherever the scale lives (WP-1958).  ``absent``
    already holds every ``lineless`` phase.
    """
    if not any(absent):
        return []
    reach = _joint_column_reach(mtable) if reach is None else reach
    return [p for p in mtable.free_paths
            if _only_unseen(mtable, reach.get(p, [p]), absent, lineless)]


def _hold_unsupported_phases_multi(models, mtable,
                                   reach: dict[str, list[str]] | None = None,
                                   sigma: float | None = PHASE_SUPPORT_SIGMA
                                   ) -> tuple[list[str], list[set[int]]]:
    """Hold what :func:`_unsupported_paths_multi` finds; returns the columns
    and, per histogram, the phases judged unseen (the width-twin hold's
    ``unseen``, ``refine._hold_unsupported_phases``' third answer).

    A caller recording the hold's reach reads :func:`_joint_column_reach`
    first and passes it in, because the reach is only readable while the
    columns are still free (``refine._hold_unsupported_phases``' rule).
    ``sigma`` is :func:`_joint_unsupported_phases`' own.  A phase with no
    reflection in a histogram's range is held there whatever ``sigma`` says,
    its scale included (WP-1958, ``refine._unsupported_phase_paths``).
    """
    lineless = _joint_lineless_phases(models)
    absent = [a | n for a, n in zip(_joint_unsupported_phases(models, mtable, sigma),
                                    lineless, strict=True)]
    held = _unsupported_paths_multi(mtable, absent, reach,
                                    _joint_flat_scales(models, mtable, lineless))
    if held:
        mtable.set_vary(held, False)
    return held, absent


def _hold_width_twins_multi(mtable, unseen: list[set[int]]
                            ) -> tuple[list[str], dict[str, list[str]]]:
    """``refine._hold_width_twins`` across the stack (WP-2002): one test over
    every histogram's sums, since a shared specimen width ties them, so one
    histogram whose instrument width is held pins the rest."""
    names = mtable.free_paths
    flats = _width_twin_flats(
        [(table, np.asarray(mtable.col_map(h), dtype=np.intp), unseen[h])
         for h, table in enumerate(mtable.tables)], len(names))
    if not flats:
        return [], {}
    held = [names[c] for c in flats]
    mtable.set_vary(held, False)
    return held, {names[c]: [names[k] for k in ks] for c, ks in flats.items()}


#: ``phases.i.scale``: the one entry a column must move, and nothing else, to
#: be phase ``i``'s own scale (``refine._own_scale_is_free``'s test).
_SCALE_PATH = re.compile(r"^phases\.(\d+)\.scale$")


def _scale_b_probe_multi(models, mtable, phases: set[int] | None = None,
                         weights: list[float] | None = None
                         ) -> tuple[dict[int, float], dict[int, list[str]]]:
    """The single fit's scale-B probe (``refine._scale_b_separation``) over
    every histogram at once (WP-1534).

    A phase's scale is per histogram and its displacement parameters are
    shared, so the question is whether some combination of its scales can be
    imitated by its displacement columns across all the histograms stacked:
    the smallest angle between the two spans
    (``refine._column_separation``).  One histogram reduces to the single
    fit's reading.  A joint column is the phase's displacement column only
    where it is one in **every** histogram it reaches (all, never any), and
    the same rule picks the phase's scale columns: a scale shared across
    histograms (``SharingMap.shared``) is **one** column on every histogram
    it reaches, never one per histogram.  Each histogram's rows carry its
    weight's √w_h, as the joint residual's do.  Returns the separations and,
    per phase, the joint column names a hold would take.
    """
    reach = [t.column_reach() for t in mtable.tables]
    disp = [_displacement_columns(t, r) for t, r in zip(mtable.tables, reach,
                                                        strict=True)]
    names = mtable.free_paths
    owner: dict[int, set[int] | None] = {}
    scale_owner: dict[int, set[int] | None] = {}
    on: dict[int, set[int]] = {}
    for h, table in enumerate(mtable.tables):
        local = {p: ip for ip, cols in disp[h].items() for p in cols}
        for c, k in enumerate(mtable.col_map(h)):
            k = int(k)
            path = table.free_paths[c]
            ip = local.get(path)
            seen = owner.get(k, set())
            owner[k] = None if (seen is None or ip is None) else seen | {ip}
            moved = [q for q in reach[h].get(path, [path])
                     if not is_variable_path(q)]
            m = _SCALE_PATH.match(moved[0]) if len(moved) == 1 else None
            seen = scale_owner.get(k, set())
            scale_owner[k] = (None if (seen is None or m is None)
                              else seen | {int(m.group(1))})
            on.setdefault(k, set()).add(h)
    columns: dict[int, list[int]] = {}
    for k, ips in owner.items():
        if ips is not None and len(ips) == 1:
            columns.setdefault(next(iter(ips)), []).append(k)
    scale_cols: dict[int, list[int]] = {}
    for k, ips in scale_owner.items():
        if ips is not None and len(ips) == 1:
            scale_cols.setdefault(next(iter(ips)), []).append(k)
    if phases is not None:
        columns = {ip: c for ip, c in columns.items() if ip in phases}
    theta = mtable.x0()
    values = mtable.decode(theta)
    w = [1.0] * len(models) if weights is None else weights
    inv = [math.sqrt(wh) / np.asarray(m.sigma, dtype=np.float64)
           for m, wh in zip(models, w, strict=True)]
    out: dict[int, float] = {}
    for ip in sorted(columns):
        if ip not in scale_cols:
            continue
        base = [np.asarray(m.phase_component(ip, v), dtype=np.float64) * f
                for m, v, f in zip(models, values, inv, strict=True)]
        scales = [np.concatenate([b if g in on[k] else np.zeros_like(b)
                                  for g, b in enumerate(base)])
                  for k in sorted(scale_cols[ip])]
        stepped = []
        for k in sorted(columns[ip]):
            th = theta.copy()
            th[k] += SCALE_B_STEP
            moved = mtable.decode(th)
            stepped.append(np.concatenate(
                [np.asarray(m.phase_component(ip, v), dtype=np.float64) * f - b
                 for m, v, f, b in zip(models, moved, inv, base, strict=True)]))
        r = _column_separation(scales, stepped)
        if r is not None:
            out[ip] = r
    return out, {ip: [names[k] for k in sorted(c)] for ip, c in columns.items()}


def _hold_scale_b_ridges_multi(models, mtable, phases: set[int] | None = None,
                               weights: list[float] | None = None
                               ) -> tuple[list[str], dict[int, float]]:
    """Hold every phase's displacement columns where
    :func:`_scale_b_probe_multi` reads under ``SCALE_B_SEPARATION_FLOOR`` —
    ``refine._hold_scale_b_ridges`` for a joint fit.  Never released at the
    answer: it rests on the frozen reflection lists."""
    separation, columns = _scale_b_probe_multi(models, mtable, phases, weights)
    ridged = {ip: r for ip, r in separation.items() if r < SCALE_B_SEPARATION_FLOOR}
    held = [c for ip in sorted(ridged) for c in columns[ip]]
    if held:
        mtable.set_vary(held, False)
    return held, ridged


def _rehold_multi(models, mtable, held: list[str],
                  start_values: list[dict[str, float]],
                  held_reach: dict[str, list[str]] | None = None,
                  reach: dict[str, list[str]] | None = None,
                  sigma: float | None = PHASE_SUPPORT_SIGMA
                  ) -> tuple[list[str], list[str]]:
    """The post-solve half of the rule, for the joint path.

    Same two answers as the single-histogram runner: a held phase that has
    appeared is released, and one that collapsed while solving is put back
    where the stage found it and held.  One extra solve covers both, and there
    is never a third.

    **Columns, never names**, for the release as for the hold (WP-1342):
    ``held_reach`` is the hold's own record, read while the columns were in θ,
    and a held column is released once **any** phase it moves is seen again
    (``refine._released_phases``' rule) — read off its name alone a
    parametric coefficient would be released the moment it was held, its
    name carrying no phase.  ``reach`` is :func:`_joint_column_reach` of the
    free columns as the solve left them, read by the caller (who records the
    collapsed columns' reach from it) or here.
    """
    # one measurement, two questions — the release and the collapse are
    # complementary readings of the same joint support test, at the plan's
    # threshold (``sigma``, WP-2002 B1; ``None`` releases and restores nothing)
    # a phase with no line in range stays held whatever ``sigma`` says: its
    # count is frozen with the stage's windows (WP-1958)
    lineless = _joint_lineless_phases(models)
    absent = [a | n for a, n in zip(_joint_unsupported_phases(models, mtable, sigma),
                                    lineless, strict=True)]
    flat_scales = _joint_flat_scales(models, mtable, lineless)
    held_set = set(held)
    held_reach = held_reach or {}
    released = [p for p in held
                if not _only_unseen(mtable, [p, *held_reach.get(p, ())], absent,
                                    flat_scales)]
    collapsed = [p for p in _unsupported_paths_multi(mtable, absent, reach,
                                                     flat_scales)
                 if p not in held_set]
    if collapsed:
        for h, table in enumerate(mtable.tables):
            by_path = {e.path: e for e in table.entries}
            bare_paths = [b for scoped in collapsed
                          if (b := mtable._unscope(h, scoped)) is not None
                          and b in by_path]
            for bare in bare_paths:
                by_path[bare].value = start_values[h][bare]
            # the single runner's rule: a composed body turn lives in its
            # anchor, so the anchor is restored with the zero (WP-1805)
            table.restore_body_anchors(bare_paths)
            table.refresh_ties()
        mtable.set_vary(collapsed, False)
    if released:
        mtable.set_vary(released, True)
    return released, collapsed


def _flat_moments_multi(models, mtable, candidates: list[str] | None = None
                        ) -> tuple[list[str], dict[str, np.ndarray]]:
    """Moment directions flat in **every** histogram that carries them (#600).

    The joint form of :func:`rietx.refine._flat_moment_paths`, and the
    intersection for the reason :func:`_unseen` takes one for a shared entry:
    a direction one histogram can see is not flat, because the joint fit
    sees it through that histogram.  An X-ray histogram does not see a moment
    at all — its modulus response is exactly zero, so the per-histogram probe
    calls every direction flat there — and so leaves the neutron histograms'
    answer unchanged, which is the case the issue measured (a cubic collinear
    ferromagnet whose polar and azimuth came back at ±1.4e9 and ±1.5e10 rad
    with nothing held).

    Moment DOFs are structural, so they are shared and their scoped name is
    the bare one.  A flat *combination* (#599) carries the axis it turns
    about; one is kept only where every histogram that names an axis names
    the same one, since turning the moment about an axis one pattern does
    not find flat would move what that pattern sees.
    """
    flat_sets: list[set[str]] = []
    carried: list[set[str]] = []
    axes: dict[str, np.ndarray] = {}
    disagree: set[str] = set()
    for model, table in zip(models, mtable.tables, strict=True):
        names = {e.path for e in table.entries}
        asked = (None if candidates is None
                 else [p for p in candidates if p in names])
        flat, found = _flat_moment_scan(model, table, asked)
        flat_sets.append(set(flat))
        carried.append(names)
        for base, axis in found.items():
            if base in axes and abs(float(axes[base] @ axis)) < 1.0 - 1e-6:
                disagree.add(base)
            axes.setdefault(base, axis)
    pool = (mtable.free_paths if candidates is None else candidates)
    joint = [p for p in pool
             if any(p in names for names in carried)
             and all(p in flat for flat, names in zip(flat_sets, carried,
                                                       strict=True)
                     if p in names)]
    for base in disagree:
        axes.pop(base, None)
        joint = [p for p in joint if p != f"{base}.dof2"]
    axes = {b: a for b, a in axes.items() if f"{b}.dof2" in joint}
    return joint, axes


def _sees_moment(model, values: dict[str, float], base: str) -> bool:
    """Whether this histogram's pattern responds to the site's modulus at all.

    Deliberately its own, coarser test (a 10 % modulus step, exact ``!=``)
    beside :func:`rietx.refine._onto_flat_meridian`'s zero-response refusal:
    it only decides which histograms are *asked* for a turn.  One that sees
    the moment and refuses the turn vetoes it everywhere, the safe direction
    — turning what one pattern cannot reproduce would move what it sees.
    """
    v = dict(values)
    v[f"{base}.dof0"] = values[f"{base}.dof0"] + 0.1 * max(
        abs(values[f"{base}.dof0"]), 1e-6)
    return bool(np.any(np.asarray(model.evaluate(v), dtype=np.float64)
                       != np.asarray(model.evaluate(values), dtype=np.float64)))


def _turn_flat_axes_multi(models, mtable, axes: dict[str, np.ndarray]
                          ) -> list[str]:
    """Turn each site in ``axes`` onto its flat meridian; returns the turned.

    The joint :func:`rietx.refine._turn_onto_meridians`, and the one place a
    flat combination's moment is turned on this path (review of #624 item 1:
    every hold turns before it holds).  A turn is kept only when it
    reproduces **every** histogram's pattern, then written into every table —
    the DOF is shared, so each table holds a copy.  A site whose turn is
    refused is left where it is and is absent from the answer (``[]`` sites
    are keyed ``phases.i.atoms.j``, the key ``StageResult`` uses).
    """
    turned: list[str] = []
    if not axes:
        return turned
    # per table, from each table's own entries: ``mtable.x0()`` is the cache
    # the stage started from, and a turn after the solve (a release, a
    # collapse restore) must read the answer's polar angle, scale and
    # background, not the ones the stage began at (review of #655 item 1)
    values = [t.decode(t.x0()) for t in mtable.tables]
    for base, axis in axes.items():
        # asked of the histograms that see the moment: one that does not
        # (an X-ray pattern, a zero modulus response) cannot measure the
        # turn against a modulus scale, and cannot see it either
        turns = [_onto_flat_meridian(m, v, base, axis)
                 for m, v in zip(models, values, strict=True)
                 if f"{base}.dof2" in v and _sees_moment(m, v, base)]
        if not turns or any(t is None for t in turns) or not all(
                np.allclose(t, turns[0], rtol=0.0, atol=1e-9) for t in turns):
            continue
        for table in mtable.tables:
            by_path = {e.path: e for e in table.entries}
            if f"{base}.dof2" in by_path:
                by_path[f"{base}.dof1"].value = turns[0][0]
                by_path[f"{base}.dof2"].value = turns[0][1]
                table.refresh_ties()
        turned.append(_site(base))
    mtable._rebuild_columns()
    return turned


def _axes_in_crystal_axes(mtable, axes: dict[str, np.ndarray]
                          ) -> dict[str, list[float]]:
    """``{site: axis in crystal-axis components}``, the record's form.

    The moment frames are structural, so every table that carries a site
    carries the same one; the first is read.
    """
    out: dict[str, list[float]] = {}
    for base, axis in axes.items():
        for table in mtable.tables:
            frame = table.moment_frames().get(_site(base))
            if frame is not None:
                out[_site(base)] = _axis_in_crystal_axes(axis, frame)
                break
    return out


def _hold_flat_moments_multi(models, mtable
                             ) -> tuple[list[str], dict[str, list[float]],
                                        list[str]]:
    """Hold what :func:`_flat_moments_multi` finds.

    The single-histogram :func:`rietx.refine._hold_flat_moments`, jointly,
    with its triple: what it held, the flat axis of every site held as a
    combination (crystal-axis components), and which of those it turned
    (:func:`_turn_flat_axes_multi`) before holding the azimuth.
    """
    held, axes = _flat_moments_multi(models, mtable)
    found = _axes_in_crystal_axes(mtable, axes)
    turned = _turn_flat_axes_multi(models, mtable, axes)
    if held:
        mtable.set_vary(held, False)
    return held, found, turned


def _rehold_flat_moments_multi(models, mtable, moment_held: list[str],
                               start_values: list[dict[str, float]],
                               turned: list[str]
                               ) -> tuple[list[str], list[str],
                                          dict[str, list[float]], list[str]]:
    """The post-solve half of the moment hold, for the joint path.

    The single-histogram runner's readings of the answer: a held direction
    that is no longer flat is released, a free one that went flat while
    solving is put back where the stage found it and held, and a combination
    still held unturned — after a release, or because the stage-start turn
    was refused — is turned here (review of #624 item 1).  Returns
    ``(released, collapsed, axes found, sites turned here)``; a turn is a
    reason to solve again, as a release is.  Asked separately from
    :func:`_rehold_multi`, whose prefix test would release a direction for
    the wrong reason — a phase being visible says nothing about whether its
    moment direction is determined.

    The order differs from :meth:`MultiHistogramRefinement.fit`'s single-
    histogram counterpart on one point, kept on purpose: the phase re-hold
    (:func:`_rehold_multi`) has already run ``set_vary`` when this scans, so
    the moment directions of a phase it just released are scanned as free —
    and, if flat, restored and held, where the single path leaves them free
    for the second solve.
    """
    released: list[str] = []
    late_axes: dict[str, np.ndarray] = {}
    if moment_held:
        still, still_axes = _flat_moments_multi(models, mtable, moment_held)
        released = [p for p in moment_held if p not in set(still)]
        late_axes = {b: a for b, a in still_axes.items()
                     if _site(b) not in turned and f"{b}.dof2" in still}
    collapsed, collapse_axes = _flat_moments_multi(models, mtable)
    if collapsed:
        for h, table in enumerate(mtable.tables):
            by_path = {e.path: e for e in table.entries}
            for path in collapsed:
                if path in by_path:
                    by_path[path].value = start_values[h][path]
            table.refresh_ties()
    axes = {**late_axes, **{b: a for b, a in collapse_axes.items()
                            if f"{b}.dof2" in collapsed}}
    found = _axes_in_crystal_axes(mtable, {**late_axes, **collapse_axes})
    turned_now = _turn_flat_axes_multi(models, mtable, axes)
    if collapsed:
        mtable.set_vary(collapsed, False)
    if released:
        mtable.set_vary(released, True)
    return released, collapsed, found, turned_now


def _reset_cell_runaway_multi(mtable, start_values: list[dict[str, float]]
                              ) -> list[tuple[str, float, float]]:
    """:func:`~rietx.refine.reset_cell_runaway`, extended to the joint runner
    (review of #385 finding 2; WP-2002, B8): same shape as
    :func:`_rehold_multi` above, called the same way, after the same
    ``mtable.commit``.  Values only: the caller holds what this put back.

    A shared cell parameter is a genuinely separate :class:`Entry` in every
    histogram's own :class:`~rietx.params.vector.ParameterTable` —
    :meth:`~rietx.params.multi.MultiParameterTable.commit` writes the same
    combined-θ value into each one, never a single shared object — so every
    table's own entries are restored and its own ties refreshed individually.
    **Which phases** is asked of every histogram first and applied to all of
    them: a per-histogram cell parameter escaping in one table puts back the
    phase's shared parameters too, and restoring them in that table alone
    would leave one shared column holding two values.
    What changes for the *report*: a shared path's solved and start values are
    identical in every histogram by construction, so it is named once under
    its bare (shared) path rather than once per histogram; a per-histogram path
    is scoped (``hist.h.…``) and is never shared with another table, so it is
    never deduplicated.
    """
    escaped = [_escaped_cell_paths(table, start_values[h])
               for h, table in enumerate(mtable.tables)]
    phases = {p.split(".")[1] for paths in escaped for p in paths}
    if not phases:
        return []
    seen: dict[str, CellReset] = {}
    for h, table in enumerate(mtable.tables):
        for c in _restore_phase_cells(table, start_values[h], phases, escaped[h]):
            scoped = mtable._canonical(h, c[0])
            seen.setdefault(scoped, CellReset(scoped, c[1], c[2],
                                              escaped=c.escaped))
    return list(seen.values())


def _vars_driven_cell_escapes_multi(mtable, start_values: list[dict[str, float]]
                                    ) -> list[tuple[str, list[str]]]:
    """:func:`~rietx.refine._vars_driven_cell_escapes` for the joint runner
    (WP-2028): a cell a free ``vars.`` column drives outside its window,
    named and never reset, for that function's reasons.

    :func:`_reset_cell_runaway_multi` reads free cell columns, so a cell that
    is a dependent of a ``vars.`` coefficient (a WP-1325 parametric target,
    set per pattern through ``hist.h.`` rows) walks past it unseen.  Each
    histogram's table is asked with its own start values, and a dependent is
    spelled as the joint result spells it (bare if shared, ``hist.h.``
    otherwise).  A coefficient is one shared column, so a driver is one row
    however many histograms it reaches, its dependents merged.
    """
    merged: dict[str, list[str]] = {}
    for h, table in enumerate(mtable.tables):
        for driver, escaped in _vars_driven_cell_escapes(table, start_values[h]):
            row = merged.setdefault(mtable._canonical(h, driver), [])
            for dependent in escaped:
                scoped = mtable._canonical(h, dependent)
                if scoped not in row:
                    row.append(scoped)
    return list(merged.items())


def _merge_unresolved(first: list[tuple[str, list[str]]],
                      second: list[tuple[str, list[str]]]
                      ) -> list[tuple[str, list[str]]]:
    """Two solves' driven escapes as one record, merged by driver, so a
    driver still escaping after both is named once (``refine._run_stage``'s
    rule)."""
    merged = dict(first)
    for driver, escaped in second:
        merged[driver] = sorted(set(merged.get(driver, [])) | set(escaped))
    return list(merged.items())


def _refuse_centroid_origin(structure: Structure) -> None:
    """A joint fit refuses ``Phase.floating_origin = "centroid"`` (WP-1912).

    The restraint is one row per direction **per structure** (Flack &
    Schwarzenbach 1988, eq 9), weighted by the curvature of all the data along
    it.  The joint residual is per-histogram residuals stacked, each with its
    own row blocks, so built here it would land once per histogram, weighted
    by one pattern's curvature each, and nothing is built to place it once.
    ``"hold"`` works in a joint fit, every histogram holding the same atom.
    A non-polar phase declaring it is not refused: nothing floats there, so
    the declaration builds nothing in a single fit either.
    """
    from .crystallography.wyckoff import floating_origin_basis

    for ip, phase in enumerate(structure.phases):
        if (phase.floating_origin == "centroid"
                and len(floating_origin_basis(phase.space_group))):
            raise ValueError(
                f"phase {ip} ({phase.name!r}) declares floating_origin="
                "'centroid', which a joint fit does not build yet: the "
                "restraint is one row per structure and the joint residual "
                "would carry it once per histogram. Use floating_origin='hold' "
                "for a joint fit")


class MultiHistogramRefinement:
    """Joint Rietveld refinement of a shared structure against several patterns.

    ``instruments`` is one instrument per pattern; ``sharing`` (a
    :class:`~rietx.params.multi.SharingMap`) overrides the default
    instrument-vs-sample split.  After :meth:`fit`, :attr:`fitted_structures`
    and :attr:`fitted_instruments` hold the per-histogram refined models (their
    shared parameters are identical; scale, background, zero and resolution
    differ).

    ``structure`` may be a list, one per pattern (WP-1325): the same model
    with each pattern's own starting values, agreeing on every shared path
    (:class:`~rietx.params.multi.MultiParameterTable`).  ``parametric``
    declares parameters as functions of each pattern's ``coordinates``
    (:class:`~rietx.schemas.parametric.ParametricEquation`,
    :class:`~rietx.schemas.parametric.CoordinateTable`); every refusal is
    made here, before any solve, and :attr:`parametric` holds the
    declarations as resolved.  The answer's coefficients are
    :attr:`RefinementResult.parametric
    <rietx.schemas.results.RefinementResult.parametric>`.
    """

    def __init__(self, structure: Structure | list[Structure],
                 instruments: list[Instrument], *,
                 sharing: SharingMap | None = None,
                 coordinates: CoordinateTable | None = None,
                 parametric: list[ParametricEquation] | None = None,
                 backend: str = "numpy", solver: str = DEFAULT_SOLVER):
        if backend != "numpy":
            from .backend import resolve_backend

            try:
                resolve_backend(backend)  # fail fast with the install hint
            except ValueError as exc:
                raise NotImplementedError(str(exc)) from exc
        if solver not in SOLVERS:
            raise ValueError(f"unknown solver {solver!r}; "
                             f"available: {', '.join(SOLVERS)}")
        self._backend = backend
        self._solver = solver
        instruments = list(instruments)
        if len(instruments) < 1:
            raise ValueError("multi-histogram needs at least one instrument")
        # one structure for every pattern, or one per pattern (WP-1325); each
        # distinct one is a caller's statement and is judged as one
        starts = ([structure] * len(instruments) if isinstance(structure, Structure)
                  else list(structure))
        # twin sites meet the merge here, once per distinct structure so a
        # shared one stays shared, and are said on the first result (#1007)
        self._twin_findings: list[Diagnostic] = []
        merged = {id(s): merge_site_twins(s, diagnostics=self._twin_findings)
                  for s in {id(s): s for s in starts}.values()}
        starts = [merged[id(s)] for s in starts]
        structure = starts[0] if isinstance(structure, Structure) else starts
        for start in {id(s): s for s in starts}.values():
            _judge_magnetic_groups(start)       # a caller's statement (issue #597)
            _refuse_centroid_origin(start)
        for i, ins in enumerate(instruments):
            # Same reason as ``Refinement.__init__``: MultiParameterTable is
            # built on the next line and reaches for a wavelength a TOF bank
            # does not carry.
            require_two_theta(None, f"MultiHistogramRefinement(), instrument "
                                    f"{i} of {len(instruments)}", instrument=ins)
        self.mtable = MultiParameterTable(structure, instruments, sharing=sharing,
                                          parametric=parametric,
                                          coordinates=coordinates)
        # Resolve each histogram's specimen absorption (capillary µR or
        # flat-plate µt) from composition, exactly as the single-histogram path
        # does.  Without this a user who set ``capillary_radius_mm`` or
        # ``thickness_mm`` here would silently get no absorption correction and
        # no diagnostic saying so — the failure mode WP-0501's reporting exists
        # to prevent.  The dimensionless product is per *instrument* (each
        # histogram may be a different wavelength and geometry, hence a
        # different µ) but the composition is one model's, which is what makes
        # one loop correct; per-pattern starts share their sites, and each
        # histogram is resolved against its own.
        resolved = [_resolve_specimen_absorption(start, ins)
                    for start, ins in zip(starts, self.mtable.instruments, strict=True)]
        self._mu_r_source: list[str] = [src for src, _ in resolved]
        self._mu_r_skipped: list[str | None] = [why for _, why in resolved]
        #: λ per line as *declared*, per histogram, taken before any stage runs.
        #: The ``WAVELENGTH_CALIBRATION`` diagnostic reports the refined value
        #: against this, and it has to be snapshotted here: ``mtable`` writes
        #: refined values back into its own instrument copies at every stage, so
        #: by the time the result is built there is nothing left to compare to.
        self._declared_wavelengths: list[list[float]] = [
            _declared_wavelengths(ins) for ins in self.mtable.instruments]
        self.result_: RefinementResult | None = None
        self._models = None
        #: what :meth:`report` reads besides the models, per histogram, taken
        #: with the result it reports on (:meth:`_freeze_answer`)
        self._answer: list[dict] | None = None

    def _drain_twin_findings(self) -> list[Diagnostic]:
        """The ``SITE_TWINS_MERGED`` findings of construction, said once."""
        out, self._twin_findings = self._twin_findings, []
        return out

    @property
    def n_histograms(self) -> int:
        return self.mtable.n_histograms

    @property
    def parametric(self) -> list[ParametricEquation]:
        """The parametric declarations as resolved, reference and scale frozen.

        Resolved once, at construction, from the coordinates present then
        (WP-1325): pass these to a refit, or to a fit of a grown campaign,
        and every coefficient keeps its meaning — Φ is rebuilt from the stored
        reference and scale, never recomputed from whichever patterns are in
        it.  Empty when nothing was declared.
        """
        return [r.equation for r in self.mtable.parametric]

    @property
    def fitted_structures(self) -> list[Structure]:
        return self.mtable.structures

    @property
    def fitted_instruments(self) -> list[Instrument]:
        return self.mtable.instruments

    # ------------------------------------------------------------------
    def fit(self, data: list[PatternData], *, mode: str = "rietveld",
            plan: RefinementPlan | str = "mccusker_default",
            two_theta_limits=None, weights: list[float] | None = None,
            events=None, cancel=None, telemetry=None, label: str | None = None,
            progress=None) -> RefinementResult:
        """Run a staged joint refinement.

        ``events``, ``cancel``, ``telemetry``, ``label`` and ``progress`` mean
        what they mean on :meth:`Refinement.fit <rietx.refine.Refinement.fit>`
        (WP-1341).  The recorder is attached once for the job, here, so a
        joint fit is one run directory however many histograms it holds.
        What differs is what an event is about, since the joint solve is one
        solve:

        * every kind keeps its meaning and is emitted once per fit, stage or
          evaluation.  An ``eval`` measures the stacked residual, and its
          ``values`` align with the combined ``free_paths``
          (``hist.<h>.``-scoped where a row is one histogram's);
        * ``fit_start``, ``stage_start``, ``stage_end`` and ``fit_end`` carry
          ``n_histograms`` and ``histograms``: one row per histogram, each
          with its ``histogram_index``.  A ``stage_end`` row carries that
          histogram's Rwp at the stage's end, beside the pooled ``rwp``.  A
          ``stage_start`` row carries ``unreached``, the globs that reached
          another histogram and none of this one (WP-1414);
        * no per-stage picture is written.  The live view draws one pattern,
          and a joint fit has several.

        A cancelled stage is abandoned: the shared table and every
        histogram's models go back to where the stage found them, and
        :class:`~rietx.optimize.cancel.RefinementCancelled` carries the
        stages that completed.  ``node_id`` is ``None``, a joint fit keeping
        no history.

        **No** ``stage_reports=``.  A rung would be one report per histogram
        per stage, and a report build costs a fixed ~0.36 s (issue #245), so
        the trajectory would multiply the solo tax by the histogram count.
        WP-1335 owns that cost.  Until it lands, the stage trajectory of a
        joint fit is its event log, and :meth:`report` builds the answer's
        report per histogram.
        """
        _refuse_without_phases(self.mtable.structures[0], "refine_multi")
        data = list(data)
        n = self.n_histograms
        if len(data) != n:
            raise ValueError(f"{len(data)} patterns for {n} instruments")
        # Per histogram, and *before* the first compile: a joint fit is where a
        # TOF bank most plausibly arrives beside CW histograms of the same
        # specimen, so the refusal has to name which one of several patterns
        # it is about.
        for i, (d, ins) in enumerate(zip(data, self.mtable.instruments,
                                         strict=True)):
            require_two_theta(d, f"MultiHistogramRefinement.fit(), histogram "
                                 f"{i} of {n}", instrument=ins)
        if mode != "rietveld":
            raise NotImplementedError(
                "multi-histogram refinement is Rietveld-only in v0.3; Le Bail / "
                "Pawley intensities are per-pattern extractions, not shared, so a "
                "joint fit of them is just independent single-pattern fits")
        if isinstance(plan, str):
            try:
                plan = PLAN_PRESETS[plan]()
            except KeyError:
                raise ValueError(
                    f"unknown plan preset {plan!r}; available: {sorted(PLAN_PRESETS)}"
                ) from None
        if not plan.stages:
            # refused before an event is emitted or a run recorded, as
            # ``Refinement.fit`` refuses it (WP-1110 item 6)
            raise ValueError("a plan with no stages refines nothing: every "
                             "stage is a group of parameters to free, so an "
                             "empty list frees none")
        limits = _normalize_limits(two_theta_limits, n)
        weights = [1.0] * n if weights is None else list(weights)
        if len(weights) != n or any(w <= 0 for w in weights):
            raise ValueError("weights must be one positive number per histogram")

        stream = _attach_progress(as_event_stream(events), progress)
        # beside the caller's stream, never inside it, and once per job
        # (``Refinement._fit_pass``' rule and its reasons)
        recorder = runs.attach(stream, events, telemetry=telemetry, label=label)
        if recorder is not None and stream is None:
            stream = recorder
        cancel = runs.attach_cancel(runs.recorder_of(stream), cancel)
        try:
            if stream is not None:
                from .project import fitted_mask

                fitted = [int(fitted_mask(d, lim).sum())
                          for d, lim in zip(data, limits, strict=True)]
                stream.emit("fit_start", mode=mode,
                            stages=[s.name for s in plan.run_stages()],
                            n_points=sum(len(d.two_theta) for d in data),
                            n_fitted=sum(fitted), n_histograms=n,
                            histograms=[{"histogram_index": h,
                                         "n_points": len(d.two_theta),
                                         "n_fitted": fitted[h]}
                                        for h, d in enumerate(data)])
            try:
                (models, outcome, stage_results, cell_runaway_diags,
                 answer_runaway, opening_diags) = self._run_plan(
                    plan, mode, data, limits, weights, stream, cancel)
            except RefinementCancelled as exc:
                if stream is not None:
                    stream.emit("fit_end", status="cancelled", stage=exc.stage,
                                completed=[s.name for s in exc.completed_stages],
                                node_id=None, n_histograms=n,
                                histograms=[{"histogram_index": h}
                                            for h in range(n)])
                raise
            self._models = models
            self.result_ = self._build_result(models, outcome, weights,
                                               plan.correlation_guard,
                                               stage_results, cell_runaway_diags,
                                               answer_runaway, opening_diags,
                                               plan.phase_support_sigma)
            self._answer = self._freeze_answer()
            if stream is not None:
                stream.emit("fit_end", status=self.result_.status,
                            rwp=self.result_.statistics.rwp,
                            gof=self.result_.statistics.gof, n_histograms=n,
                            histograms=[{"histogram_index": h,
                                         "rwp": hr.statistics.rwp,
                                         "gof": hr.statistics.gof}
                                        for h, hr in enumerate(self.result_.histograms)])
            if recorder is not None:
                recorder.write_summary(self.result_)
            return self.result_
        except BaseException:
            # the single fit's rule: a raised fit is a failed run, and a
            # ``cancelled`` its ``fit_end`` already recorded survives this
            if recorder is not None:
                recorder.close("failed")
            raise
        finally:
            # on every exit, a raised fit included, as
            # ``Refinement._fit_lebail_alternation`` closes its own
            if stream is not None and stream is not events:
                stream.close()        # built here from a path or a callable
            if recorder is not None:
                recorder.close()

    def report(self, histogram: int, *, plan: RefinementPlan | str | None = None,
               **kw):
        """The :class:`~rietx.report.FitReport` for one histogram of the last fit.

        One report per histogram (WP-1341).  Every Layer 0-2 statement is
        about one pattern's residual against one compiled model, so each is
        asked of histogram ``histogram``: its curves and statistics through
        :meth:`RefinementResult.for_histogram`, its compiled model and values
        for Layers 1-2, exactly as :meth:`Refinement.report
        <rietx.refine.Refinement.report>` asks them of a single fit.  ``plan``
        supplies the Layer-2 strategy veto.

        The specimen has one crystallite size (WP-1131), and the report says
        it once.  Its microstructure block is the joint result's, read off the
        shared column at histogram 0's wavelength, so every histogram's report
        quotes the same size.  The separability caveat beside it is the
        report's own, from this histogram's 2θ range.

        The background section reads this histogram's own absorption screen.
        The identifiability section has no correlation, soft-mode or
        exchangeability table, because the joint path does not run those
        screens.

        The report reads the result's curves and models, which come from a
        compile at the answer (:meth:`_final_compiles`, WP-1421), as a single
        fit's do.  Read off the last stage's own compile, a stage that
        broadened the peaks left their tails cut at windows sized where it
        started, and Layer 0 read the cut as unmatched peaks (WP-1341).
        """
        from .report import build_report

        if self._models is None or self.result_ is None:
            raise RuntimeError("call fit() first")
        n = self.n_histograms
        if not 0 <= histogram < n:
            raise IndexError(f"histogram {histogram} of a {n}-histogram fit")
        if isinstance(plan, str):
            plan = PLAN_PRESETS[plan]()
        answer = self._answer[histogram]
        return build_report(
            self.result_.for_histogram(histogram),
            model=self._models[histogram], values=answer["values"],
            plan=plan, structure=answer["structure"],
            instrument=answer["instrument"], held=answer["held"],
            free_paths=answer["free_paths"], **kw)

    def _freeze_answer(self) -> list[dict]:
        """What :meth:`report` reads, per histogram, beside the models.

        Taken when the result is built, because the table is the working
        state and the result is not: a later fit that is cancelled puts the
        table back where its own stage found it, and a report that read the
        live table then would pair those values with this result's models.
        """
        last = self.result_.stages[-1] if self.result_.stages else None
        # a cell the last stage put back and held counts as free here, as every
        # other hold does (``Refinement._record_free_paths``)
        held_all = ([*last.held, *(last.cell_reset or [])]
                    if last is not None else [])
        out = []
        for h, (table, structure) in enumerate(
                zip(self.mtable.tables, self.mtable.structures, strict=True)):
            held = [q for p in held_all
                    if (q := self.mtable._unscope(h, p)) is not None]
            held_set = set(held)
            out.append({
                "values": table.decode(table.x0()),
                "structure": structure.model_copy(deep=True),
                "instrument": self.mtable.instruments[h].model_copy(deep=True),
                "held": held,
                # what ``Refinement._record_free_paths`` records: free, or
                # held by the last stage
                "free_paths": [e.path for e in table.entries
                               if e.vary or e.path in held_set]})
        return out

    @contextmanager
    def _abandon_on_cancel(self, cancel, stage_name: str, completed: list, stream):
        """Make "the in-flight stage is abandoned" true of a joint fit.

        ``Refinement._abandon_on_cancel``'s rule.  A stage here writes into
        ``self.mtable`` before it solves (vary flags, a seed, the models it
        writes back), and the table *is* the working state a joint fit
        returns through :attr:`fitted_structures`.  So the whole table is
        copied when a token is present and put back on a cancel.
        """
        if cancel is None:
            yield
            return
        saved = copy.deepcopy(self.mtable)
        try:
            yield
        except RefinementCancelled as exc:
            self.mtable = saved
            exc.stage = exc.stage or stage_name
            exc.completed_stages = list(completed)
            exc.node_id = None
            if stream is not None:
                # no costs and no Rwp, as on a single fit, but the rows the
                # docstring promises on every ``stage_end``
                stream.emit("stage_end", stage=exc.stage, status="cancelled",
                            n_histograms=self.n_histograms,
                            histograms=[{"histogram_index": h}
                                        for h in range(self.n_histograms)])
            raise

    def _stage_end_rows(self, models, theta) -> tuple[float, list[dict]]:
        """The pooled Rwp and each histogram's, at the values a stage ended on.

        Computed the way :meth:`_build_result` computes the answer's, from the
        outcome's θ, but on the stage's own compile: the answer is measured on
        a compile at its values (:meth:`_final_compiles`), so the last
        ``stage_end`` differs from ``fit_end`` by the frozen windows alone,
        which ``FROZEN_COMPILE_STALE`` reports past 1 % in χ².  Never from
        ``mtable.x0()``: the combined vector is
        cached, and a commit that re-charts nothing leaves it at the stage's
        start.
        """
        per = self.mtable.decode(theta)
        y_calc = [m.evaluate(v) for m, v in zip(models, per, strict=True)]
        y_bkg = [m.background(v) for m, v in zip(models, per, strict=True)]
        rows = [{"histogram_index": h,
                 "rwp": compute_statistics(m.y_obs, yc, m.sigma, n_free=0,
                                           y_background=yb).rwp}
                for h, (m, yc, yb) in enumerate(zip(models, y_calc, y_bkg, strict=True))]
        pooled = compute_statistics(
            np.concatenate([m.y_obs for m in models]), np.concatenate(y_calc),
            np.concatenate([m.sigma for m in models]), n_free=0,
            y_background=np.concatenate(y_bkg)).rwp
        return pooled, rows

    def _run_plan(self, plan, mode, data, limits, weights, stream, cancel):
        """The stage loop, cumulative like the single-histogram runner's."""
        # the single runner's read of the plan's threshold (WP-2002, B1): a
        # dataclass validates nothing, so it is checked where it is read
        phase_support_sigma = check_phase_support_sigma(plan.phase_support_sigma)
        # staged plan, cumulative like the single-histogram runner: start all
        # fixed, free each stage's globs across every histogram, recompile each
        # histogram (⇒ per-histogram frozen discreteness) and joint-solve.
        # the shared structure's own findings, asked of it as declared — the
        # single-histogram path asks them before any stage for that reason
        # (DIAGNOSTIC_SCOPES: SPECIMEN) — and the plan's literal paths the
        # model will not free, a plan read decided before any stage too (FIT)
        opening_diags = (
            self._drain_twin_findings()
            + _symmetry_silence_diagnostics(self.mtable.structures[0], mode)
            + _joint_fixed_literals(plan.stages, self.mtable))
        self.mtable.set_vary(["*"], False)
        stage_results: list[StageResult] = []
        # one CELL_RUNAWAY diagnostic per stage that fired, exactly as the
        # single-histogram runner builds one per _run_stage call (review of
        # #385 finding 2) — collected here and folded into the run-level
        # diagnostics once the loop ends, since a stage here has no
        # StageReport of its own to carry it on.
        cell_runaway_diags: list[Diagnostic] = []
        # the last stage's alone, which is what the result withholds esds on
        # — ``refine._run_plan``'s ``answer_runaway``, for its reason
        answer_runaway: list[Diagnostic] = []
        models = None
        outcome = None
        carried_hold: list[str] = []
        # the declared stages and the closing one, the single runner's
        # schedule (WP-2002, the sixth round's Q1 and Q2)
        stages = plan.run_stages()
        n_stages = len(stages)
        for index, (stage, ftol, window_tol) in enumerate(
                zip(stages, plan.stage_ftols(), plan.stage_window_tols(),
                    strict=True), start=1):
            with self._abandon_on_cancel(cancel, stage.name, stage_results, stream):
                freed = self.mtable.set_vary(stage.turn_on, True)
                # what the glob matched and a hold refused (WP-1435): here only
                # the floating-origin hold (WP-1912), which the origin
                # diagnostics report from
                blocked_by_hold = self.mtable.blocked_by_hold(stage.turn_on)
                # what the stage asked for and did not get (WP-1414): a literal
                # no histogram has or a retired spelling, and — the joint fit's
                # own case — a histogram the stage's globs reached nothing of
                # while reaching another's
                unknown_paths = self.mtable.unknown_paths(stage.turn_on)
                unreached = self.mtable.unreached_histograms(stage.turn_on)
                if carried_hold:
                    # lift the previous stage's hold before this one decides its
                    # own — the single-histogram runner's rule (``_run_stage``),
                    # and for its reason: a phase invisible then may be plain now,
                    # and a cumulative plan need not name its cell again
                    self.mtable.set_vary(carried_hold, True)
                    carried_hold = []
                seeded: dict[str, float] = {}
                if stage.seed:
                    seeded = dict.fromkeys(
                        self.mtable.seed_floored(freed, stage.seed), stage.seed)
                self.mtable.apply_to_models()
                # the single-histogram runner's rule (``_run_stage``, #598): the
                # moment frames follow the cell this stage starts from, and the
                # compile reads the DOFs in the table's frames, not its own
                self.mtable.reframe_moments()
                models = [
                    compile_model(s, ins, d, mode="rietveld", two_theta_limits=lim,
                                  moving_paths=set(tab.moving_paths),
                                  window_area_tol=recorded_window_tol(window_tol))
                    for s, ins, d, lim, tab in zip(
                        self.mtable.structures, self.mtable.instruments, data, limits,
                        self.mtable.tables, strict=True)]
                self.mtable.push_moment_frames(models)
                stage_ftol = {} if ftol is None else {"ftol": ftol}
                # A phase the data cannot see is flat here too (WP-1301), and
                # each entry is judged where it lives (``_unseen``, WP-1325): a
                # shared cell only when no histogram sees the phase, the rule
                # ``_freeze_cell_windows_multi`` applies, and a per-histogram
                # cell wherever its own pattern cannot.
                # ``freed`` is derived from this whenever the hold moves, so the
                # record's ``freed``/``held`` stay disjoint however the stage ends
                # — the single-histogram runner's rule (``_run_stage``)
                declared_freed = list(freed)
                # what each column moves, read while every one is still free:
                # the hold's record (``StageResult.held_reach``, WP-1342)
                reach = _joint_column_reach(self.mtable)
                held, unseen = _hold_unsupported_phases_multi(
                    models, self.mtable, reach, phase_support_sigma)
                held_reach = _joint_reach_beyond_self(held, reach)
                # a phase whose scales and displacement parameters the ranges
                # cannot separate (WP-1534): the single runner's probe, asked of
                # every histogram at once; kept apart from the support hold, since
                # it rests on the frozen reflection lists and is never released
                ridge_hold, scale_b_held = _hold_scale_b_ridges_multi(
                    models, self.mtable, weights=weights)
                # and a moment direction no histogram can see (WP-1327, #600):
                # the single-histogram runner's second hold, kept apart for the
                # same reason — each is asked again of the answer by its own test
                moment_hold, flat_axes, moment_turned = _hold_flat_moments_multi(
                    models, self.mtable)
                # and an instrument width whose specimen twin is free in every
                # histogram's sums (WP-2002), never asked again
                twin_hold, width_twins_held = _hold_width_twins_multi(
                    self.mtable, unseen)
                held_reach.update(_joint_reach_beyond_self(twin_hold, reach))
                support_hold = held
                held = held + ridge_hold + moment_hold + twin_hold
                if held:
                    held_set = set(held)
                    freed = [p for p in declared_freed if p not in held_set]
                self._emit_stage_start(stream, stage, index, n_stages, models,
                                       freed=freed, held=held,
                                       unknown_paths=unknown_paths,
                                       unreached=unreached)
                start_values = self.mtable.decode(self.mtable.x0())
                outcome = run_multi_least_squares(models, self.mtable, weights=weights,
                                                  max_iter=stage.max_iter,
                                                  backend=self._backend,
                                                  solver=self._solver,
                                                  events=stream, stage=stage.name,
                                                  cancel=cancel,
                                                  phase_support_sigma=phase_support_sigma,
                                                  **stage_ftol)
                signs = self.mtable.commit(outcome.theta)
                if signs is not None:
                    # a moment committed in its principal chart (#604): the
                    # combined x0 is cached, so it is rebuilt before it is read
                    self.mtable._rebuild_columns()
                    outcome = rechart_outcome(outcome, self.mtable.x0(), signs,
                                              self.mtable.free_paths)
                # A phase's own support can stay above phase_support_sigma in
                # every histogram and its shared cell still walk to nonsense — the
                # single-histogram runner's own joint-degeneracy gap
                # (CELL_SAFETY_FRACTION's docstring), unaffected by which runner
                # is asking.  Checked on the outcome, never as a bound the solver
                # saw (review of #385 finding 2); the cell goes back to where the
                # stage found it before the answer is measured below, and is held
                # for the second solve with the collapse's paths (WP-2002, B8).
                cell_runaway = _reset_cell_runaway_multi(self.mtable, start_values)
                # a cell a free coefficient drives is invisible to the reset
                # above by construction — named, never put back (WP-2028)
                unresolved = _vars_driven_cell_escapes_multi(self.mtable,
                                                             start_values)
                if cell_runaway:
                    self.mtable._rebuild_columns()
                    outcome = dataclasses.replace(outcome, theta=self.mtable.x0())
                moment_set = set(moment_hold)
                # the free columns as the solve left them, read before the
                # collapse takes any out of θ, so a collapsed column's reach is
                # on the record beside the stage-start hold's
                reach = _joint_column_reach(self.mtable)
                released, collapsed = _rehold_multi(
                    models, self.mtable, list(support_hold), start_values,
                    held_reach=held_reach, reach=reach, sigma=phase_support_sigma)
                held_reach.update(_joint_reach_beyond_self(collapsed, reach))
                # ``StageResult.collapsed``: the restored columns alone, taken
                # before the late scale-B hold joins ``collapsed`` below, since
                # that one holds a released phase's B where it stands
                restored = list(collapsed)
                if released:
                    # a phase the support hold released is asked before its second
                    # solve, or that solve runs on the ridge unflagged (the single
                    # runner's ``late_hold``); read off what each released
                    # column moves, since a parametric coefficient's own name
                    # carries no phase (WP-1342)
                    back = _joint_phases_reached(released, held_reach)
                    late, late_sep = _hold_scale_b_ridges_multi(
                        models, self.mtable, back, weights)
                    if late:
                        late_set = set(late)
                        released = [p for p in released if p not in late_set]
                        collapsed = collapsed + late
                        scale_b_held.update(late_sep)
                m_released, m_collapsed, m_axes, m_turned = _rehold_flat_moments_multi(
                    models, self.mtable, [p for p in held if p in moment_set],
                    start_values, moment_turned)
                released, collapsed = released + m_released, collapsed + m_collapsed
                restored = restored + m_collapsed
                for site, axis in m_axes.items():
                    flat_axes.setdefault(site, axis)
                moment_turned = moment_turned + m_turned
                # the reset's hold takes what the collapse left, the single
                # runner's rule: a path both reach is the collapse's, in ``held``
                collapsed_set = set(collapsed)
                reset_hold = list(dict.fromkeys(p for p, _, _ in cell_runaway
                                                if p not in collapsed_set))
                if reset_hold:
                    reset_hold = self.mtable.set_vary(reset_hold, False)
                cell_reset = list(reset_hold)
                if released or collapsed or m_turned or reset_hold:
                    released_set = set(released)
                    held = list(dict.fromkeys(p for p in held + collapsed
                                              if p not in released_set))
                    held_set = set(held)
                    freed = [p for p in declared_freed
                             if p not in held_set and p not in reset_hold]
                    # the resumed half gets its own stage_start, since its
                    # free vector differs (the single fit's rule, WP-1301)
                    self._emit_stage_start(stream, stage, index, n_stages, models,
                                           freed=list(released), held=held,
                                           released=list(released),
                                           unknown_paths=unknown_paths,
                                           unreached=unreached)
                    second = run_multi_least_squares(
                        models, self.mtable, weights=weights,
                        max_iter=stage.max_iter, backend=self._backend,
                        solver=self._solver, events=stream, stage=stage.name,
                        cancel=cancel, phase_support_sigma=phase_support_sigma,
                        **stage_ftol)
                    signs = self.mtable.commit(second.theta)
                    if signs is not None:
                        self.mtable._rebuild_columns()
                        second = rechart_outcome(second, self.mtable.x0(), signs,
                                                 self.mtable.free_paths)
                    # asked again, and with no third solve the cell goes back and
                    # stays a free column of this answer, its esd withheld (the
                    # single runner's rule)
                    second_runaway = [
                        CellReset(*c, escaped=c.escaped, held=False)
                        for c in _reset_cell_runaway_multi(self.mtable, start_values)]
                    if second_runaway:
                        self.mtable._rebuild_columns()
                        cell_runaway = cell_runaway + second_runaway
                        put_back = [p for p, _, _ in second_runaway]
                        cell_reset = cell_reset + put_back
                        freed = [p for p in freed if p not in put_back]
                        second = dataclasses.replace(second, theta=self.mtable.x0())
                    unresolved = _merge_unresolved(
                        unresolved,
                        _vars_driven_cell_escapes_multi(self.mtable, start_values))
                    outcome = dataclasses.replace(
                        second, cost_initial=outcome.cost_initial,
                        n_iterations=outcome.n_iterations + second.n_iterations,
                        n_constraint_truncations=(outcome.n_constraint_truncations
                                                  + second.n_constraint_truncations),
                        # summed for the same reason the truncations are: the stage
                        # ran twice and the count is a fact about its whole search
                        n_degenerate_cell_probes=(outcome.n_degenerate_cell_probes
                                                  + second.n_degenerate_cell_probes),
                        n_lapack_fallbacks=(outcome.n_lapack_fallbacks
                                            + second.n_lapack_fallbacks))
                runaway_diag = _cell_runaway_diagnostic(cell_runaway, unresolved)
                answer_runaway = [] if runaway_diag is None else [runaway_diag]
                if runaway_diag is not None:
                    cell_runaway_diags.append(runaway_diag)
                self.mtable.apply_to_models()
                # the reset's hold is lifted by the next stage with the others
                carried_hold = list(held) + reset_hold
                # the record of the turn (#599), for the sites still held at the
                # answer: a site in ``moment_flat_axes`` and not in
                # ``moment_turned`` was held where it was
                kept_axes = {b: a for b, a in flat_axes.items()
                             if f"{b}.moment.dof2" in set(held)}
                # the support hold's columns still held at the answer, each
                # with what else it stopped (WP-1342's record, scoped as the
                # joint result spells a row)
                still = set(held)
                # what each histogram's frozen windows drop at the answer
                # (WP-2047); the record keeps the worst
                losses = [x for x in (window_loss(m, v) for m, v in zip(
                    models, self.mtable.decode(outcome.theta), strict=True))
                    if x is not None]
                stage_results.append(StageResult(
                    name=stage.name, status=outcome.status,
                    n_iterations=outcome.n_iterations,
                    cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                    freed=freed,
                    n_constraint_truncations=outcome.n_constraint_truncations,
                    n_degenerate_cell_probes=outcome.n_degenerate_cell_probes,
                    n_lapack_fallbacks=outcome.n_lapack_fallbacks,
                    ftol=ftol, window_area_tol=window_tol,
                    held=held, released=released,
                    held_reach={c: v for c, v in held_reach.items() if c in still},
                    scale_b_held=dict(scale_b_held),
                    width_twins_held=width_twins_held,
                    moment_flat_axes=kept_axes,
                    moment_turned=[b for b in kept_axes if b in moment_turned],
                    unknown_paths=unknown_paths, unreached_histograms=unreached,
                    seeded=seeded, blocked_by_hold=blocked_by_hold,
                    moment_angle_tests=outcome.moment_angle_tests,
                    cell_reset=cell_reset, collapsed=restored,
                    window_loss=max(losses) if losses else None))
                if stream is not None:
                    rwp, rows = self._stage_end_rows(models, outcome.theta)
                    stream.emit("stage_end", stage=stage.name, status=outcome.status,
                                n_iterations=outcome.n_iterations,
                                termination=outcome.termination,
                                cost_initial=outcome.cost_initial,
                                cost_final=outcome.cost_final, rwp=rwp,
                                held=list(held), released=list(released),
                                n_histograms=self.n_histograms, histograms=rows,
                                window_loss=stage_results[-1].window_loss)

        assert models is not None and outcome is not None
        # the result's curves and statistics from a compile at the values it
        # returns, never the last stage's start-of-stage one (#272, WP-1421)
        models, recompiled = self._final_compiles(models, outcome, data, limits,
                                                  window_tol)
        opening_diags = [*opening_diags, *recompiled]
        return (models, outcome, stage_results, cell_runaway_diags,
                answer_runaway, opening_diags)

    def _final_compiles(self, models, outcome, data, limits, window_tol):
        """One compile per histogram at the values the result returns.

        ``Refinement._final_compile``'s rule, one runner over (WP-1421): each
        stage's compile froze its windows and FCJ node counts at the values
        the stage started from, so a last stage that broadened the peaks left
        their tails cut, and the joint report read the cut as unmatched peaks
        (WP-1341: 44 and 27 on the WP-1131 size pair, 0 and 0 here).  Built
        with the last stage's own discrete settings and nothing else changed.
        The solve, the covariance, every esd, the weights (the solve's σ,
        WP-1309) and the origin rows (WP-1912) stay the solve's, exactly as
        there.  ``FROZEN_COMPILE_STALE`` tests each histogram's own χ² and
        reports the worst, naming it.
        """
        values = [t.decode(th) for t, th in zip(
            self.mtable.tables, self.mtable.split(outcome.theta), strict=True)]
        fresh = [
            compile_model(s, ins, d, mode="rietveld", two_theta_limits=lim,
                          moving_paths=set(tab.moving_paths),
                          window_area_tol=recorded_window_tol(window_tol))
            for s, ins, d, lim, tab in zip(
                self.mtable.structures, self.mtable.instruments, data, limits,
                self.mtable.tables, strict=True)]
        # the solve's moment frames, never the fresh compiles' (#598)
        self.mtable.push_moment_frames(fresh)
        pairs = []
        for old, new, v in zip(models, fresh, values, strict=True):
            new.sigma = old.sigma
            new.origin = old.origin
            pairs.append((
                float(np.sum(((old.y_obs - old.evaluate(v)) / old.sigma) ** 2)),
                float(np.sum(((new.y_obs - new.evaluate(v)) / new.sigma) ** 2))))
        # each pattern's own gap, never the sum: a pooled χ² hides one pattern
        # (MODEL_FAR_FROM_DATA's reason), and a pattern's private parameters
        # are fitted by its χ² alone; one finding, naming the worst
        rel = [abs(b - a) / a if a > 0 else 0.0 for a, b in pairs]
        worst = int(np.argmax(rel))
        return fresh, _frozen_compile_diagnostics(*pairs[worst], histogram=worst)

    def _emit_stage_start(self, stream, stage, index, n_stages, models, *,
                          freed, held, unknown_paths, unreached, **extra) -> None:
        """One ``stage_start``, the single fit's fields plus the histogram rows."""
        if stream is None:
            return
        stream.emit("stage_start", stage=stage.name, turn_on=list(stage.turn_on),
                    freed=list(freed), n_free=len(self.mtable.free_paths),
                    free_paths=list(self.mtable.free_paths), held=list(held),
                    unknown_paths=list(unknown_paths),
                    n_points=sum(len(m.tt) for m in models),
                    index=index, n_stages=n_stages,
                    n_histograms=self.n_histograms,
                    histograms=[{"histogram_index": h, "n_points": len(m.tt),
                                 "unreached": list(unreached.get(h, []))}
                                for h, m in enumerate(models)],
                    **extra)

    # ------------------------------------------------------------------
    def _ticks(self, model, structure, values
               ) -> tuple[dict[str, list[float]], dict[str, list[list[int]]],
                          dict[str, list[float]]]:
        """Positions per phase, which reflection each of them is, and its
        support in σ.

        All three, from one walk.  The positions and the Miller indices are
        ``CompiledModel.reflection_positions``, the walk this shares with
        ``refine._build_result`` and ``viz.snapshot.stage_ticks`` (WP-1908), so
        a joint fit's ticks are where the model draws each peak and a joint
        fit whose ticks carried no Miller indices cannot be the one surface
        where pointing at a tick told the reader nothing (WP-1438).  The
        support is not a result field: ``_low_angle_diagnostics`` is its one
        reader, and its rule is ``refine``'s (``_reflection_tick_support``),
        so the two builders cannot disagree about which tick has anything
        behind it.
        """
        ticks: dict[str, list[float]] = {}
        tick_hkl: dict[str, list[list[int]]] = {}
        tick_support: dict[str, list[float]] = {}
        for ip in range(len(model.phases)):
            name = structure.phases[ip].name
            # (H, m), not H: a satellite is labelled by its order (WP-1326)
            pos, hkl = model.reflection_positions(ip, values)
            sup = _reflection_tick_support(
                model, ip, values, len(model.line_wavelengths))
            keep = np.isfinite(pos)
            pos, hkl, sup = pos[keep], hkl[keep], sup[keep]
            order = np.argsort(pos, kind="stable")
            ticks[name] = [float(v) for v in pos[order]]
            tick_hkl[name] = [reflection_label_row(r) for r in hkl[order]]
            tick_support[name] = [float(v) for v in sup[order]]
        # Declared sharp peaks are ticks here too (WP-1103, the member
        # contract's clause 2).  A joint fit's Layer 0 reads *this* list, so
        # without the row every declared peak comes back as an unindexed
        # impurity on every histogram — the single-histogram failure
        # ``refine._build_result`` writes the same key to prevent.  The
        # positions come from the compiled model rather than from a second
        # loop, so the two surfaces cannot drift.
        extra = model.extra_peak_tick_positions(values)
        if extra:
            # no `tick_hkl` row: a peak declared by centre has no Miller
            # index, and an empty list would claim it had none of its own
            ticks[EXTRA_TICK_KEY] = extra
            tick_support[EXTRA_TICK_KEY] = _extra_peak_tick_support(model, values)
        return ticks, tick_hkl, tick_support

    def _build_result(self, models, outcome, weights, correlation_guard,
                      stage_results, cell_runaway_diags=(),
                      answer_runaway=(), opening_diags=(),
                      phase_support_sigma: float | None = PHASE_SUPPORT_SIGMA
                      ) -> RefinementResult:
        mt = self.mtable
        # the threshold PHASE_UNCONSTRAINED and the parametric screen report
        # against: the hold's own, or the default with the hold off (WP-2002 B1)
        support_sigma = _reported_support_sigma(phase_support_sigma)
        n = mt.n_histograms
        thetas = mt.split(outcome.theta)
        stderr = outcome.stderr_internal
        corr = outcome.correlation
        n_data = [len(m.tt) for m in models]
        data_off = np.concatenate([[0], np.cumsum(n_data)]).astype(int)

        # per-histogram slices ---------------------------------------------------
        per_values, per_ycalc, per_ybkg, per_esds = [], [], [], []
        histograms: list[HistogramResult] = []
        top_bg: list[GuardFinding] = []
        absorption_table: dict[str, float] = {}
        joint_unmeasured = _joint_unmeasured_phases(models, mt, stage_results)
        for h in range(n):
            table = mt.tables[h]
            model = models[h]
            struct = mt.structures[h]
            values = table.decode(thetas[h])
            y_calc = model.evaluate(values)
            y_bkg = model.background(values)
            per_values.append(values)
            per_ycalc.append(y_calc)
            per_ybkg.append(y_bkg)

            cm = mt.col_map(h)
            s_h = stderr[cm] if stderr is not None else None
            corr_h = corr[np.ix_(cm, cm)] if corr is not None else None
            esd_h = (table.stderr_physical(thetas[h], s_h, corr_h)
                     if s_h is not None else {})
            per_esds.append(esd_h)

            n_free_h = mt.n_shared + len(mt.per_hist_paths[h])
            stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                       n_free=n_free_h, y_background=y_bkg)
            # the single fit's builder, blind-scale rule and finding included
            # (WP-1463); rows are addressed as this surface spells them
            qpa, qpa_diags = _quantify_phases(
                table, thetas[h], s_h, corr_h, struct, values, model,
                unmeasured=joint_unmeasured[h],
                held=(_held_scale_phases(stage_results[-1], h)
                      if stage_results else None),
                where_of=lambda p, h=h: (p if mt.sharing.is_shared(p)
                                         else f"hist.{h}.{p}"))

            diags: list[Diagnostic] = []
            j0, j1 = data_off[h], data_off[h] + n_data[h]
            if outcome.jac is not None and len(table.free_paths) > 1:
                # this histogram's rows against its own columns: a slice of the
                # dense matrix, or its block where the solve kept them (WP-1325)
                jh = (outcome.jac.block(h) if isinstance(outcome.jac, BlockJacobian)
                      else np.asarray(outcome.jac)[j0:j1][:, cm])
                screened = background_absorption(
                    jh, table.free_paths, model.peak_component_prefixes())
                # every screened pair, kept as evidence beside the verdicts
                # below (``Identifiability``'s rule), scoped like them
                absorption_table.update(
                    {f"hist.{h}.{p}": r2 for p, r2 in screened.items()})
                for path, r2 in sorted(screened.items(), key=lambda kv: -kv[1]):
                    if r2 > BACKGROUND_ABSORPTION_GUARD:
                        # ``hist.h.<path>`` is this surface's own addressing —
                        # the same prefix ``RefinedParameter.path`` uses for a
                        # per-histogram parameter — so the finding's paths stay
                        # resolvable against the result a client is holding.
                        finding = GuardFinding.background_absorption(
                            f"hist.{h}.{path}", r2)
                        top_bg.append(finding)
                        diags.extend(_guard_diagnostics(
                            GuardReport(background_correlations=[finding])))
                # the roughness twin, per histogram only (GUARD_SCOPES)
                rough = [GuardFinding.roughness_absorption(f"hist.{h}.{path}", r2)
                         for path, r2 in sorted(roughness_absorption(
                             jh, table.free_paths,
                             model.peak_component_prefixes()).items(),
                                                key=lambda kv: -kv[1])
                         if r2 > ROUGHNESS_ABSORPTION_GUARD]
                if rough:
                    diags.extend(_guard_diagnostics(
                        GuardReport(roughness_correlations=rough)))
            diags.extend(qpa_diags)
            # specimen absorption, per histogram — each may sit at its own
            # wavelength and geometry, hence its own µR/µt.  Only the failure
            # modes are surfaced here; the applied value lives on
            # ``fitted_instruments[h]``.
            absorption = _absorption_record(model, self._mu_r_source[h],
                                            self._mu_r_skipped[h], values)
            if absorption is not None:
                diags.extend(_absorption_diagnostics(absorption))
            # A joint fit's shared cell draws from every histogram, so a
            # capillary that could not express its eq (4) offsets folds them
            # into that one cell — the misreading WP-1073 exists to name, at its
            # worst when several radius-less capillaries pool into one number.
            # Per histogram, like the absorption and wavelength diagnostics
            # above: each has its own geometry and locked-entry table.
            diags.extend(_capillary_offset_diagnostics(model, table))
            # A declared background peak narrowing toward the resolution is a
            # disguised Bragg peak here exactly as in a single fit — and the
            # joint path is the only one that never ran the check.  Per
            # histogram (each keeps its own background and peaks), reported
            # through this histogram's diagnostics like everything else the
            # joint fit measures per pattern (HUMP_TOO_NARROW).
            narrow = check_hump_width(table, model)
            if narrow:
                diags.extend(_guard_diagnostics(
                    GuardReport(narrow_humps=narrow)))
            # this instrument's resolution function, over this histogram's
            # range (GUARD_SCOPES: HISTOGRAM)
            diags.extend(_guard_diagnostics(GuardReport(
                nonpositive_resolution=check_resolution_positive(table, model),
                unsupported_resolution=check_resolution_supported(table, model))))
            diags.extend(_wavelength_calibration_diagnostics(
                self._declared_wavelengths[h], table, values, esd_h,
                pinned_by=_WAVELENGTH_PINNED_BY_HELD_HISTOGRAM, h=h))
            # The two tier-2 flags, per histogram — without which a joint fit
            # gets the tier-1 bound (``_freeze_strain_cap_multi`` /
            # ``_freeze_size_cap_multi``) and none of the interpretation the
            # two-tier split exists for.  Per histogram rather than once,
            # because each reads this histogram's own copy against this
            # histogram's own λ.  Since WP-1131 that is a *check* rather than a
            # discrepancy: the shared column is normalised by λ, so the size
            # flag reads the same crystallite in every pattern and a
            # disagreement between two histograms' rows would mean the
            # normalisation had come undone.  Before it, one shared ``lor_size``
            # was a different apparent size in each pattern and a single reading
            # would have quoted one histogram's λ about all of them.
            # The strain flag is λ-free and repeats per histogram for the same
            # reason the absorption and wavelength rows above do — a caller
            # reads one histogram's diagnostics and must not have to know that
            # this one row lives somewhere else.
            diags.extend(_strain_flag_diagnostics(model, values, struct))
            diags.extend(_size_flag_diagnostics(model, values, struct))
            # The data-side width check (WP-1336), per histogram for the same
            # reason: its comparator is this instrument's fitted widths on this
            # pattern's channels, the one place a too-narrow declared profile
            # shows when no size or strain term is freed to give the flags above
            # a number to read.
            diags.extend(_width_census_diagnostics(model, values, struct,
                                                   sigma=support_sigma))
            # What this histogram's own radiation is owed (WP-1344): each of
            # the three asks one source, so each is this histogram's, and a
            # mixed fit raises it on the histogram it belongs to and nowhere
            # else.  ``DIAGNOSTIC_SCOPES`` is the rule; these are its rows.
            instrument = mt.instruments[h]
            diags.extend(_dispersion_diagnostics(struct, instrument))
            diags.extend(_resonant_absorber_diagnostics(struct, instrument))
            diags.extend(_species_fallback_diagnostics(struct, instrument))
            diags.extend(_harmonic_diagnostics(
                model, values, set(table.free_paths), esd_h))
            diags.extend(_roughness_regime_diagnostics(model, values))
            ticks, tick_hkl, tick_support = self._ticks(model, struct, values)
            diags.extend(_extra_peak_diagnostics(model, values, ticks, table))
            diags.extend(_far_from_data_diagnostics(model, y_calc, y_bkg, stats))
            # the measurement's half only: support=None withholds the ratio,
            # which has no joint definition (DIAGNOSTIC_SCOPES says why)
            diags.extend(_data_support_diagnostics(None, model))
            diags.extend(_low_angle_diagnostics(model, values, y_calc, stats,
                                                ticks, tick_support))
            diags.extend(_air_scatter_undeclared_diagnostics(model, values,
                                                             y_calc, stats))

            histograms.append(HistogramResult(
                label=model.meta.get("label", "") or f"hist{h}",
                weight=float(weights[h]), statistics=stats,
                two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
                y_calc=y_calc.tolist(), y_background=y_bkg.tolist(),
                sigma=model.sigma.tolist(),
                ticks=ticks, tick_hkl=tick_hkl,
                radiation=_radiation(model, values),
                qpa=qpa,
                # per histogram, like the QPA and the absorption record above:
                # the partition is of *this* pattern's counts, so a joint fit
                # has one structure R per histogram, not a pooled one
                phase_agreement=_phase_agreement(model, values, struct),
                diagnostics=diags))

        # pooled combined statistics (reported, never quoted alone) --------------
        combined = compute_statistics(
            np.concatenate([m.y_obs for m in models]),
            np.concatenate(per_ycalc),
            np.concatenate([m.sigma for m in models]),
            n_free=len(mt.free_paths),
            y_background=np.concatenate(per_ybkg))
        # the joint solve's convergence figure, copied and never derived
        # (WP-1341; ``_final_shift_over_esd_multi`` says why it is defined)
        combined.max_shift_over_esd = outcome.max_shift_over_esd

        # one bound test, two consumers: the rows' at_bound flag and the
        # BOUND_HIT/FLOOR_HIT diagnostics (WP-1076, WP-1929)
        at_bounds = bound_findings(
            mt.bounds(), mt.free_paths, outcome.theta,
            cos=outcome.residual_cosine, esd=outcome.stderr_internal,
            active=_exact_active_bounds(outcome))
        # Histogram 0's physical esds, built once in the loop above and read by
        # two consumers (WP-1131): the shared rows of ``_parameters``, and the
        # microstructure block, which reads histogram 0 because its value scale
        # is exactly 1.0.  With a correlation matrix this is a dense n x n, so
        # a second build here would double the cost for the same dict.
        esd_hist0 = per_esds[0] if per_esds else {}
        parameters = self._parameters(thetas, stderr, corr, at_bounds, esd_hist0,
                                      answer_runaway, outcome.esd_inflation)
        diagnostics = list(opening_diags) + self._top_diagnostics(
            outcome, correlation_guard, top_bg, at_bounds, models)
        # what a parametric declaration did to each pattern's dependent that
        # no bound the solve saw could stop (WP-1325, FIT)
        diagnostics = diagnostics + _parametric_range_diagnostics(mt)
        # the subset patterns that cannot see each equation's target: there the
        # value is the equation's alone, and the form test leaves them out (WP-1325)
        unseen = _parametric_unseen(models, mt, support_sigma)
        diagnostics = diagnostics + _parametric_unseen_diagnostics(mt, unseen)
        # whether each declared form survives its data, holding what the one
        # bound test found on a bound (WP-1325, FIT)
        parametric_form, form_joint = _parametric_form_tests(models, mt, at_bounds,
                                                             weights, unseen)
        coefficients = self._parametric_rows(esd_hist0)
        diagnostics = diagnostics + _parametric_form_diagnostics(mt, parametric_form,
                                                                 form_joint)
        if stage_results:
            diagnostics = diagnostics + _constraint_diagnostics(
                stage_results[-1].name, outcome)
            # the answer-producing stage only: its covariance is the one every
            # reported esd is read off (WP-1333)
            diagnostics = diagnostics + _covariance_diagnostics(
                stage_results[-1].name, outcome, answer=True)
            # the single fit's builder, off the same stage's record (WP-1929).
            # The rows carry no interval: the joint fit has no profile verb,
            # so the finding says none was computed (WP-2002)
            diagnostics = diagnostics + moment_angle_stationary_diagnostics(
                stage_results[-1], parameters)
        # Every stage, not only the last one, exactly as the single-histogram
        # path sums it (``refine._degenerate_cell_diagnostics``): a degenerate
        # probe is a fact about the search and not about the final point.
        diagnostics = diagnostics + _degenerate_cell_diagnostics(
            [(sr.name, sr.n_degenerate_cell_probes) for sr in stage_results])
        # What a stage asked for and did not get (WP-1414), read off the
        # records.  The near-miss draws on both spellings a glob can match
        # here, so a bare typo is answered bare and a scoped one scoped.
        diagnostics = diagnostics + _unknown_path_diagnostics(
            stage_results, sorted(mt.known_paths()),
            listing="[e.path for t in ref.mtable.tables for e in t.entries]")
        diagnostics = diagnostics + _unreached_histogram_diagnostics(
            stage_results, [h.label for h in histograms])
        diagnostics = diagnostics + _window_loss_diagnostics(stage_results)
        # the floating-origin hold every histogram's table derives from its
        # copy of the one structure (WP-1912): asked of each and told once
        diagnostics = diagnostics + _joint_origin_findings(stage_results,
                                                              mt)
        # a stage's budget is spent by the one joint solve (FIT)
        diagnostics = diagnostics + _max_iter_diagnostics(stage_results)
        # one CELL_RUNAWAY per stage that fired the joint reset above,
        # collected during the loop since there is no per-stage StageReport
        # here to carry it on (review of #385 finding 2)
        diagnostics = diagnostics + cell_runaway_diags
        # A phase the joint fit cannot see, and what the run did about it
        # (WP-1301).  Once for the fit rather than once per histogram, because
        # the statement is joint: the support is the phase's **strongest**
        # showing across the histograms, the line count its total, and the
        # range the union of theirs.  Before this the joint path was the only
        # one that never said it at all.
        #
        # ``max``, because the statement is about the phase: the joint fit
        # cannot see a phase at all only when it is below support in *every*
        # histogram, and that is exactly ``max(support) < σ``.  The weakest
        # showing would fire this on a phase invisible in one pattern and plain
        # in another, which is a phase the joint fit measures: a warning on a
        # healthy phase teaches a consumer to ignore the code.  Where its cell
        # is per-histogram, the patterns that cannot see it hold their own copy
        # (``_unseen``, WP-1325), and that hold is on ``StageResult.held``;
        # naming it per pattern is the joint report's, WP-1341's.
        #
        # The screen alone, never the single fit's significance (WP-1523): the
        # joint report is WP-1341's, so the message names the screen's basis.
        per_support = np.array([m.phase_support(v)
                                for m, v in zip(models, per_values, strict=True)])
        per_lines = np.array([m.phase_line_counts() for m in models])
        diagnostics = diagnostics + _phase_support_diagnostics(
            per_support.max(axis=0), per_lines.sum(axis=0),
            (min(m.tt_min for m in models), max(m.tt_max for m in models)),
            [_unscoped(p) for p in mt.free_paths],
            self.mtable.structures[0], stage_results,
            basis="with everything else held, in the histogram that shows it best",
            decided=False, sigma=support_sigma,
            quantified=models[0].mode == "rietveld")
        # the patterns where the support hold kept a phase's per-pattern
        # structure, which PHASE_UNCONSTRAINED's joint statement cannot name
        # (WP-2028): a record of the hold, read off the answer's stage
        diagnostics = diagnostics + _per_pattern_hold_diagnostics(
            stage_results, mt, self.mtable.structures[0])
        # a phase whose scales and B no histogram's range can separate, and
        # what its fraction is conditional on (WP-1534)
        diagnostics = diagnostics + _scale_b_ridge_diagnostics(
            models, per_values, self.mtable.structures[0], stage_results)
        # a refined occupancy past a full site (WP-2002, SPECIMEN): asked of
        # every histogram, since an occupancy can be per histogram (WP-2028)
        diagnostics = diagnostics + _occupancy_once(mt, per_values, per_esds)

        weight_note = ("unit (each point's esd governs)"
                       if all(w == 1.0 for w in weights)
                       else ", ".join(f"hist{h}={w:g}" for h, w in enumerate(weights)))
        provenance = Provenance(
            package_version=_VERSION, created_utc=_utcnow(),
            backend=self._backend, dtype=backend_dtype_note(self._backend),
            solver=self._solver, report_thresholds_version=THRESHOLDS_VERSION,
            notes={"n_histograms": str(n), "histogram_weights": weight_note})

        return RefinementResult(
            status=outcome.status, mode="rietveld",
            parameters=parameters, statistics=combined,
            stages=stage_results, diagnostics=diagnostics, provenance=provenance,
            # top-level arrays mirror histogram 0 so .plot() and existing
            # consumers keep working; the real per-pattern data is in histograms.
            two_theta=histograms[0].two_theta, y_obs=histograms[0].y_obs,
            y_calc=histograms[0].y_calc, y_background=histograms[0].y_background,
            sigma=histograms[0].sigma, ticks=histograms[0].ticks,
            radiation=histograms[0].radiation,
            # the ticks' labels beside them, so the mirror names its
            # reflections (WP-2028; WP-1986 found them dropped)
            tick_hkl=histograms[0].tick_hkl,
            qpa=histograms[0].qpa,
            # WP-1131: one block per phase, read off **histogram 0** — the
            # reference wavelength, whose value scale is exactly 1.0, so its
            # coefficients *are* the shared column and the size behind them is
            # the specimen's one number.  Reading any other histogram would
            # give the same size from a different coefficient; reading none
            # would leave every joint fit reporting an empty list, which says
            # "no microstructure" about the fits this correction exists for.
            microstructure=microstructure_table(
                mt.structures[0], per_values[0],
                wavelength=_longest_line_wavelength(models[0]),
                esds=esd_hist0),
            # each histogram's background screen, ``hist.<h>.``-scoped, so
            # ``for_histogram`` hands a report its own (WP-1341); ``None``
            # where nothing was screened, the single fit's empty state
            identifiability=(Identifiability(background_absorption=absorption_table)
                             if absorption_table else None),
            # the declared coefficients in user units at the reference, read
            # off histogram 0's slice of the joint covariance (a coefficient
            # is shared, so its marginal is the joint one), and each equation with
            # their covariance; ``None`` when nothing was declared (WP-1325)
            parametric=coefficients,
            parametric_form=parametric_form,
            parametric_form_joint=form_joint,
            parametric_equations=self._parametric_equations(coefficients, corr),
            histograms=histograms)

    def _parametric_equations(self, coefficients, corr):
        """Each declaration as resolved, with its coefficients' covariance.

        ``None`` when nothing was declared.  The covariance pairs the
        ``coefficients``' own esds by the joint solve's correlation ``corr``,
        the matrix those esds were read off (:func:`~rietx.params.parametric.parametric_equation`).
        """
        mt = self.mtable
        if not mt.parametric:
            return None
        index = {p: i for i, p in enumerate(mt.free_paths)}
        return [parametric_equation(r, [c for c in coefficients if c.equation == r.name],
                                    [index.get(p) for p in r.paths], corr)
                for r in mt.parametric]

    def _parametric_rows(self, esd0: dict[str, float]):
        """Every declared coefficient, in user units at the reference.

        ``None`` when no parametric equation was declared, the honest empty state.
        A coefficient's value is histogram 0's entry (every table holds the
        same shared one), its esd ``esd0``'s, which omits a row the covariance
        marks unmeasured (``ParameterTable.stderr_physical``): no pattern in
        the subset carried gradient for it.
        """
        mt = self.mtable
        if not mt.parametric:
            return None
        t0 = mt.tables[0]
        rows = []
        for r in mt.parametric:
            entries = {p: t0.entries[t0._paths[p]] for p in r.paths}
            rows.extend(coefficient_rows(
                r, {p: e.value for p, e in entries.items()}, esd0,
                {p: e.vary for p, e in entries.items()}))
        return rows

    def _parameters(self, thetas, stderr, corr, at_bounds, esd0,
                    answer_runaway=(), esd_inflation=None) -> list[RefinedParameter]:
        mt = self.mtable
        params: list[RefinedParameter] = []
        # The single-histogram rule (``refine._build_result``): a cell the
        # answer-producing stage's CELL_RUNAWAY names has its esd withheld,
        # and so does every path tied to it — asked of each histogram's own
        # table, because the ties are per table.  The finding scopes a
        # per-histogram path ``hist.h.…`` and names a shared one bare
        # (``_reset_cell_runaway_multi``), so each table reads its own names.
        named = [p for d in answer_runaway for p in d.where]
        withheld = []
        for h, table in enumerate(mt.tables):
            prefix = f"hist.{h}."
            local = [p[len(prefix):] if p.startswith(prefix) else p for p in named
                     if p.startswith(prefix) or not p.startswith("hist.")]
            withheld.append(_cell_runaway_withheld(table, local))
        # The row path is the combined path — shared rows unprefixed,
        # per-histogram rows `hist.h.…` — which is exactly how
        # `MultiParameterTable.free_paths` spells them, so the projection keys
        # on the row path and needs no second naming convention (WP-1076).
        tested = set(mt.free_paths)
        on_bound = {p for f in at_bounds for p in f.paths}
        # which equation set each row, keyed on the same row path (WP-1325)
        equations = _equation_rows(mt)
        # shared parameters reported once, from histogram 0's covariance (its
        # diagonal esd is the true combined marginal — cross-terms with the
        # other histograms' columns do not enter a single path's variance).
        for e in mt.tables[0].entries:
            if _row_shared(mt, e) and (e.vary or e.tie is not None):
                sd = None if e.path in withheld[0] else esd0.get(e.path)
                # the single fit's rule (``refine._uncorrected``, WP-2002 B4):
                # the joint solve's own factor, read off its weighted residual
                params.append(RefinedParameter(
                    path=e.path, value=e.value, vary=e.vary, stderr=sd,
                    stderr_uncorrected=_uncorrected(sd, esd_inflation),
                    at_bound=(e.path in on_bound) if e.path in tested else None,
                    equations=equations.get(e.path, [])))
        for h, table in enumerate(mt.tables):
            cm = mt.col_map(h)
            esd = (table.stderr_physical(thetas[h], stderr[cm],
                                         corr[np.ix_(cm, cm)] if corr is not None else None)
                   if stderr is not None else {})
            for e in table.entries:
                if not _row_shared(mt, e) and (e.vary or e.tie is not None):
                    row = f"hist.{h}.{e.path}"
                    sd = None if e.path in withheld[h] else esd.get(e.path)
                    params.append(RefinedParameter(
                        path=row, value=e.value, vary=e.vary, stderr=sd,
                        stderr_uncorrected=_uncorrected(sd, esd_inflation),
                        at_bound=(row in on_bound) if row in tested else None,
                        equations=equations.get(row, [])))
        return params

    def _top_diagnostics(self, outcome, correlation_guard, bg_scoped,
                         at_bounds, models) -> list[Diagnostic]:
        mt = self.mtable
        free = mt.free_paths
        report = GuardReport(background_correlations=bg_scoped)
        # the specimen's three table-reading guards (GUARD_SCOPES: SPECIMEN),
        # asked of every histogram, since a structural path can be per
        # histogram (WP-1325): one finding per path, a per-histogram one
        # named with its histogram (WP-2028)
        report.nonpositive_adps = _specimen_once(
            mt, models, lambda t, _m: check_adp_positive_definite(t))
        report.large_biso = _specimen_once(mt, models, check_biso_plausible)
        report.negative_biso = _specimen_once(mt, models, check_biso_negative)
        report.nonpositive_strain = _stephens_once(mt, models)
        report.nonpositive_texture = _texture_once(mt, models)
        if outcome.correlation is not None and len(free) > 1:
            c = np.asarray(outcome.correlation)
            for i in range(len(free)):
                for j in range(i + 1, len(free)):
                    if abs(c[i, j]) > correlation_guard:
                        report.high_correlations.append(
                            GuardFinding.correlation(free[i], free[j], c[i, j]))
                        # beside it, never instead (``check_guards``' rule)
                        if abs(c[i, j]) >= FLAT_DIRECTION_RHO:
                            report.flat_directions.append(
                                GuardFinding.flat_direction(
                                    free[i], free[j], c[i, j]))
        if outcome.jac is not None and len(free) > 1:
            try:
                # the matrix the covariance cut (``check_guards``' rule)
                report.discarded_directions = check_discarded_directions(
                    covariance_jacobian(outcome, free), free,
                    report.flat_directions)
            except np.linalg.LinAlgError:
                if getattr(outcome, "covariance_error", None) is None:
                    raise
        report.at_bounds = at_bounds
        return _guard_diagnostics(report) + _size_sharing_diagnostics(mt)


def _row_shared(mtable, entry) -> bool:
    """Whether a table entry is one column of the joint fit, or a row per
    histogram.

    An entry is shared when its own path is, and a **tied** one also needs
    every source of its tie shared: ``u11`` of an anisotropic site is a
    follower of the site's ``adp.k`` columns, so under
    ``per_histogram=["phases.*.atoms.*.adp.*"]`` it is each histogram's own
    although no glob names it (WP-2028).
    """
    share = mtable.sharing.is_shared
    if not share(entry.path):
        return False
    return entry.tie is None or all(share(src) for src, _ in entry.tie.terms)


#: the entries that move an ADP site: the free columns, and the U^ij rows
#: they drive
_ADP_LEAVES = tuple(f"adp.{k}" for k in range(6)) + (
    "u11", "u22", "u33", "u12", "u13", "u23")


def _specimen_path(mtable, h: int, path: str) -> str:
    """``path`` as the joint result spells it in histogram ``h``.

    A shared path is bare and a per-histogram one ``hist.h.``-scoped
    (:meth:`~rietx.params.multi.MultiParameterTable._canonical`).  An ADP
    finding names its site (``phases.0.atoms.1``), which is no table entry:
    the site is the histogram's own when **any** entry that moves it is
    (``adp.k`` is the column a joint fit frees, ``u11`` only its follower).
    """
    if _ADP_SITE.fullmatch(path):
        shared = all(mtable.sharing.is_shared(f"{path}.{leaf}")
                     for leaf in _ADP_LEAVES)
    else:
        shared = mtable.sharing.is_shared(path)
    return path if shared else f"hist.{h}.{path}"


#: an ADP finding's subject: a site, not an entry
_ADP_SITE = re.compile(r"phases\.\d+\.atoms\.\d+")


def _specimen_once(mtable, models, check) -> list[GuardFinding]:
    """A specimen guard asked of every histogram's table and model (WP-2028).

    Before WP-2028 ``_top_diagnostics`` asked histogram 0 alone, on the
    reason "every histogram's gives the same".  That held while the
    structure was one object.  Since WP-1325 a path can be per histogram
    (``SharingMap.per_histogram``, a parametric target), and a bad value in
    another histogram's copy fired nothing.  :func:`_stephens_once`'s shape:
    each histogram is asked, and a finding is kept once per path as the
    joint result spells it, so a shared path is one finding named bare and a
    per-histogram path one finding per histogram that holds the value, named
    ``hist.h.…``.  A histogram's finding keeps its own number; for a shared
    path the first histogram's is kept, which every table holds the same.
    """
    seen: dict[tuple[str, ...], GuardFinding] = {}
    for h, (table, model) in enumerate(zip(mtable.tables, models, strict=True)):
        for finding in check(table, model):
            paths = tuple(_specimen_path(mtable, h, p) for p in finding.paths)
            if paths != finding.paths:
                message = finding.message
                for bare, scoped in zip(finding.paths, paths, strict=True):
                    message = message.replace(bare, scoped, 1)
                finding = dataclasses.replace(finding, paths=paths,
                                              message=message)
            seen.setdefault(paths, finding)
    return list(seen.values())


def _occupancy_once(mtable, per_values, per_esds) -> list[Diagnostic]:
    """``OCCUPANCY_ABOVE_ONE`` for the joint fit, asked of every histogram.

    :func:`_specimen_once`'s shape (WP-2028).  An occupancy can be per
    histogram (``SharingMap.per_histogram``), and histogram 0's copy says
    nothing of histogram 1's.  A shared occupancy is one finding named bare,
    a per-histogram one a finding per histogram that holds a value above 1,
    named ``hist.h.…`` with its own value and esd.
    """
    seen: dict[str, Diagnostic] = {}
    for h, table in enumerate(mtable.tables):
        for d in _occupancy_flag_diagnostics(
                per_values[h], set(table.moving_paths), mtable.structures[h],
                per_esds[h] if per_esds else {}):
            (path,) = d.where
            scoped = _specimen_path(mtable, h, path)
            if scoped != path:
                d = d.model_copy(update={
                    "where": [scoped],
                    "message": f"{d.message} (histogram {h})"})
            seen.setdefault(scoped, d)
    return list(seen.values())


def _stephens_once(mtable, models) -> list[GuardFinding]:
    """``STEPHENS_STRAIN_NOT_POSITIVE`` for the joint fit, one per phase.

    The coefficients are shared but the cone is tested on *measured*
    directions (``check_stephens_positive``), and each histogram measures its
    own; a phase is named from the first histogram whose reflections leave
    the cone, so one specimen's one coefficient set is one finding.
    """
    seen: dict[tuple[str, ...], GuardFinding] = {}
    for table, model in zip(mtable.tables, models, strict=True):
        for finding in check_stephens_positive(table, model):
            seen.setdefault(tuple(finding.paths), finding)
    return list(seen.values())


def _texture_once(mtable, models) -> list[GuardFinding]:
    """``TEXTURE_NOT_POSITIVE`` for the joint fit, one per phase (WP-1960).

    :func:`_stephens_once`'s shape: the coefficients are shared, each
    histogram samples them at its own ψ, and a phase is named from the first
    histogram where P leaves the physical set.
    """
    seen: dict[tuple[str, ...], GuardFinding] = {}
    for table, model in zip(mtable.tables, models, strict=True):
        for finding in check_texture_positive(table, model):
            seen.setdefault(tuple(finding.paths), finding)
    return list(seen.values())


def _size_sharing_diagnostics(mtable) -> list[Diagnostic]:
    """``SIZE_NORMALISED_ACROSS_WAVELENGTHS`` — what a joint fit did to a size.

    An **info** row, and the WP-1076 shape is why it exists at all: before
    WP-1131 a joint fit of histograms at different wavelengths served one
    ``lor_size`` column to all of them, which is one specimen wearing as many
    crystallite sizes as it has wavelengths — the fit reported ``converged``,
    the cell came back right, and nothing named the cause.  Now the shared
    column is the coefficient at the reference wavelength and each histogram
    carries its own, so the finding is no longer a defect to warn about; it is
    an action to *state*, exactly as ``PHASE_UNCONSTRAINED`` states what was
    held.  A reader who does not know the coefficient was rescaled would read
    ``phases.0.lor_size`` as the number their second pattern shows.

    Silent unless there is something to say: no scaling declared (one
    histogram, equal wavelengths, or a source with no declared line), or every
    scaled term still sitting at zero, where the correction is 0.0 either way
    and naming it would be noise on every joint fit that never freed a width.
    """
    scales = getattr(mtable, "value_scales", None)
    if not scales or not any(scales):
        return []
    lams = [_longest_wavelength(ins) for ins in mtable.instruments]
    out: list[Diagnostic] = []
    ref = lams[0]
    for path in sorted(set().union(*(set(s) for s in scales))):
        values = [t.entries[t._paths[path]].value for t in mtable.tables
                  if path in t._paths]
        if not any(v != 0.0 for v in values):
            continue
        factors = [s.get(path, 1.0) for s in scales]
        term = path.rsplit(".", 1)[-1]
        power = "λ" if SIZE_LAMBDA_POWER[term] == 1.0 else "λ²"
        out.append(Diagnostic(
            level="info", code="SIZE_NORMALISED_ACROSS_WAVELENGTHS",
            where=[path], value=float(max(factors) / min(factors)),
            message=(
                f"{path} is a size term that goes as {power}, and this joint "
                f"fit spans λ = {min(lams):.5g}-{max(lams):.5g} Å. The shared "
                f"column is the coefficient at λ = {ref:.5g} Å "
                f"(histogram 0). Each histogram's own copy carries "
                f"{', '.join(f'{f:.4g}' for f in factors)}× it respectively: "
                f"{', '.join(f'{v:.6g}' for v in values)} deg"
                f"{'²' if term.startswith('gauss') else ''}."),
            suggestion=(
                "Read the size with rietx.model.profiles.caglioti."
                "apparent_size_from_size_coefficient and each histogram's own "
                "λ. To refine an independent size per histogram, use "
                'SharingMap(per_histogram=["phases.*.lor_size", '
                '"phases.*.gauss_size"]).'),
        ))
    return out


def _parametric_range_diagnostics(mtable) -> list[Diagnostic]:
    """``PARAMETRIC_OUT_OF_RANGE`` — a dependent the coefficients put outside
    its own bounds (WP-1325).

    The WP-1119 hazard one rank up: a pattern's target is Σ_j Φ_kj·c_j over
    unbounded coefficients, so the solve never sees the target's own
    ``min``/``max``.  A ``constant`` declaration's one coefficient carries the
    target's box itself (``MultiParameterTable._install_parametric``), but a
    sum of several terms has no box that holds it.  So the answer is read:
    one warning per declaration, naming every subset pattern whose dependent
    left its declared range, at the value it took.  ``value`` is how many.
    """
    out: list[Diagnostic] = []
    for r in mtable.parametric:
        bad = []
        for h in r.patterns:
            table = mtable.tables[h]
            e = table.entries[table._paths[r.target]]
            if not e.lo <= e.value <= e.hi:
                bad.append((h, e.value, e.lo, e.hi))
        if not bad:
            continue
        shown = "; ".join(f"histogram {h}: {v:.6g} outside [{lo:g}, {hi:g}]"
                          for h, v, lo, hi in bad[:5])
        more = f" (and {len(bad) - 5} more)" if len(bad) > 5 else ""
        out.append(Diagnostic(
            level="warning", code="PARAMETRIC_OUT_OF_RANGE",
            where=[f"hist.{h}.{r.target}" for h, *_ in bad], value=float(len(bad)),
            message=(f"Parametric equation {r.name!r} puts {r.target} outside its own "
                     f"bounds in {len(bad)} of {len(r.patterns)} patterns: "
                     f"{shown}{more}."),
            suggestion=("Narrow the subset to where the form holds, lower the "
                        "polynomial's order, or declare a design basis that "
                        "stays inside the range.")))
    return out


def _equation_rows(mtable) -> dict[str, list[str]]:
    """Per row of the joint result, the declarations whose coefficients set it.

    A row is an equation's when one of the equation's coefficients moves it, read off
    each table's :meth:`~rietx.params.vector.ParameterTable.entry_reach` (the
    WP-1342 reading of **C**, through the declarations so a held coefficient
    still counts) and spelled as ``_parameters`` spells the row
    (``mtable._canonical``).  So: the target in each subset pattern, what
    follows it there (a cubic cell's b and c), and the coefficient's own
    ``vars.`` row.  Several equations reach one row only through a caller's tie
    combining their targets, and then the row names each, in declaration
    order.  Empty when nothing was declared (WP-1325).
    """
    out: dict[str, list[str]] = {}
    if not mtable.parametric:
        return out
    for h, table in enumerate(mtable.tables):
        reach = table.entry_reach()
        for r in mtable.parametric:
            for path in r.paths:
                for q in reach.get(path, (path,)):
                    names = out.setdefault(mtable._canonical(h, q), [])
                    if r.name not in names:
                        names.append(r.name)
    return out


def _parametric_unseen(models, mtable, sigma: float = PHASE_SUPPORT_SIGMA
                       ) -> dict[str, frozenset[int]]:
    """Per declaration, the subset patterns that cannot see its target.

    :func:`_unseen`, the predicate the stage's support hold uses (WP-1301),
    asked of each subset pattern's own copy of the target at the answer.
    Empty when nothing was declared (WP-1325).  ``sigma`` is the threshold
    ``PHASE_UNCONSTRAINED`` reads (``refine._reported_support_sigma``,
    WP-2002 B1): a report, so it speaks with the hold switched off.
    """
    if not mtable.parametric:
        return {}
    absent = _joint_unsupported_phases(models, mtable, sigma)
    return {r.name: frozenset(k for k in r.patterns
                              if _unseen(mtable, f"hist.{k}.{r.target}", absent))
            for r in mtable.parametric}


def _parametric_unseen_diagnostics(mtable, unseen: dict[str, frozenset[int]]
                                   ) -> list[Diagnostic]:
    """``PARAMETRIC_TARGET_UNSEEN`` — an equation setting its target in patterns that
    cannot see it (WP-1325).

    There the target is the equation's value at the pattern's coordinates and
    nothing that pattern measured, its esd is the equation's, and the form test
    leaves the pattern out (:func:`_parametric_form_tests`), so a wrong equation
    is carried through it unchecked.  On synthetic ramps whose minor phase
    faded out, the line's interval covered a bent truth in the gaps 0.03 of
    the time (``docs/wp/1325-parametric-series.md`` § Measured: where one
    pattern cannot see the parameter).  One warning per declaration with any
    such pattern; ``where`` names each pattern's row, ``value`` counts them.
    """
    out: list[Diagnostic] = []
    for r in mtable.parametric:
        blind = sorted(unseen.get(r.name, ()))
        if not blind:
            continue
        shown = ", ".join(str(h) for h in blind[:10])
        more = f" and {len(blind) - 10} more" if len(blind) > 10 else ""
        # with every pattern blind there is no seeing pattern to carry the equation
        # from: the coefficients are held where they started (WP-1301)
        whence = ("carried from the patterns that see the phase." if
                  len(blind) < len(r.patterns) else
                  "so the equation itself is not measured: no pattern of the "
                  "subset sees the phase.")
        out.append(Diagnostic(
            level="warning", code="PARAMETRIC_TARGET_UNSEEN",
            where=[f"hist.{h}.{r.target}" for h in blind], value=float(len(blind)),
            message=(f"Parametric equation {r.name!r} sets {r.target} in {len(blind)} of "
                     f"its {len(r.patterns)} patterns that cannot see its phase "
                     f"(histograms {shown}{more}). There the value and its esd are "
                     f"the equation's, {whence}"),
            suggestion=("Quote the equation's coefficients. Narrow the subset to "
                        "the patterns that see the phase if the equation should "
                        "hold only where it is measured.")))
    return out


def _per_pattern_hold_diagnostics(stage_results: list[StageResult], mtable,
                                  structure: Structure) -> list[Diagnostic]:
    """``PHASE_HELD_IN_PATTERNS`` — a phase's per-pattern structure or scale
    held in some patterns at the answer (WP-2028).

    A record of what the fit did, never a verdict.  The answer-producing
    stage's support hold (``StageResult.held``) holds a ``hist.h.`` copy of a
    phase's structure wherever pattern h cannot see the phase
    (:func:`_unseen`, WP-1325).  ``PHASE_UNCONSTRAINED`` names only a phase
    no histogram sees, so before this nothing said "held in 12 of 33
    patterns".  One finding per phase: ``where`` is the held rows, ``value``
    the number of patterns.  A shared path held is the joint statement's,
    ``PHASE_UNCONSTRAINED``; a parametric target is ``vars.``-driven and its
    blind patterns are ``PARAMETRIC_TARGET_UNSEEN``'s, so neither is repeated
    here, and a phase held in *every* pattern is ``PHASE_UNCONSTRAINED``'s
    (a one-histogram joint fit is that case).  The scale-B ridge's displacement hold and the flat-moment hold
    are their own codes' (``SCALE_B_INSEPARABLE``, the moment record) and
    are left out.

    **A phase's own ``hist.h.…scale`` is counted too** (review of #1128, round
    2): a pattern with no line of the phase holds its scale at the value
    handed in (WP-1958, #1103), and where the joint fit sees the phase
    ``PHASE_UNCONSTRAINED`` is silent, so this is the one finding that says
    which patterns held it.  A scale-only hold is the same record with no
    structural rows, and a phase held in every pattern is still
    ``PHASE_UNCONSTRAINED``'s, which names the histograms itself.
    """
    if not stage_results:
        return []
    last = stage_results[-1]
    ridge = set(last.scale_b_held or ())
    targets = {f"hist.{k}.{r.target}" for r in mtable.parametric
               for k in r.patterns}
    by_phase: dict[int, dict[int, list[str]]] = {}
    scale_rows: dict[int, dict[int, list[str]]] = {}
    for path in last.held:
        h = mtable._owner(path)
        if h is None or path in targets:
            continue
        bare = _unscoped(path)
        m = _PHASE_PREFIX.match(bare)
        if m is None or ".moment." in bare:
            continue
        ip = int(m.group(1))
        if bare == f"phases.{ip}.scale":
            scale_rows.setdefault(ip, {}).setdefault(h, []).append(path)
            continue
        # ``refine._DISPLACEMENT_PATH`` is the one spelling of the columns the
        # ridge hold takes: ``adp.k`` is the free column of an anisotropic site
        if ip in ridge and _DISPLACEMENT_PATH.match(bare):
            continue
        by_phase.setdefault(ip, {}).setdefault(h, []).append(path)
    n = mtable.n_histograms
    out: list[Diagnostic] = []
    for ip in sorted(set(by_phase) | set(scale_rows)):
        structure_rows = by_phase.get(ip, {})
        patterns = sorted(set(structure_rows) | set(scale_rows.get(ip, {})))
        if len(patterns) == n:
            # held in every pattern is a phase no pattern sees, which is
            # ``PHASE_UNCONSTRAINED``'s statement and not repeated here
            continue
        where = [p for h in patterns for p in structure_rows.get(h, [])]
        n_structure = len(where)
        where += [p for h in patterns for p in scale_rows.get(ip, {}).get(h, [])]
        name = (structure.phases[ip].name if ip < len(structure.phases)
                else f"phase {ip}")
        clauses = []
        if n_structure:
            clauses.append(
                f"their own copies of its structure ({n_structure} "
                f"row{'' if n_structure == 1 else 's'}) keep the values the "
                f"stage started from and carry no esd")
        if len(where) > n_structure:
            clauses.append("their own scale keeps the value handed in and "
                           "is not a measurement there")
        shown = ", ".join(str(h) for h in patterns[:10])
        more = f" and {len(patterns) - 10} more" if len(patterns) > 10 else ""
        out.append(Diagnostic(
            level="info", code="PHASE_HELD_IN_PATTERNS",
            where=where, value=float(len(patterns)),
            message=(f"Phase {ip} ({name}) was held in {len(patterns)} of {n} "
                     f"patterns ({'histogram' if len(patterns) == 1 else 'histograms'} "
                     f"{shown}{more}) by stage {last.name!r}: those patterns "
                     f"cannot see it, so "
                     + "; ".join(clauses) + ".")))
    return out


def _parametric_form_tests(models, mtable, at_bounds, weights,
                           unseen: dict[str, frozenset[int]]
                           ) -> tuple[list[ParametricFormTest] | None,
                                      ParametricFormReading | None]:
    """Each declaration's lack-of-fit test at the answer, and the joint
    reading of every tested declaration at once (WP-1325).

    ``(None, None)`` when nothing was declared.  One Jacobian at the answer, blocked
    whatever layout the solve took, and :func:`~rietx.params.parametric.form_tests`
    reads it.  A pattern is left out of a declaration's alternative where
    ``unseen`` names it (:func:`_parametric_unseen`), the predicate the
    stage's support hold uses, so the alternative is the untied fit's.  The
    columns ``at_bounds`` names stay on their bounds on both sides.
    """
    if not mtable.parametric:
        return None, None
    residual, jacobian, n_data = _multi_closures(models, mtable, weights=weights,
                                                 layout="blocked")
    x = mtable.x0()
    index = {p: i for i, p in enumerate(mtable.free_paths)}
    hold = sorted({index[p] for f in at_bounds for p in f.paths if p in index})
    return form_tests(mtable.parametric, jacobian(x), residual(x), n_data,
                      mtable.free_paths, unseen, hold)


def _parametric_form_diagnostics(mtable, tests: list[ParametricFormTest] | None,
                                 joint: ParametricFormReading | None = None
                                 ) -> list[Diagnostic]:
    """``PARAMETRIC_FORM_REJECTED`` — a declaration whose data refuses its
    form (WP-1325): one warning per rejected
    :class:`~rietx.schemas.parametric.ParametricFormTest`, ``where`` its
    coefficients, whose esds assume the form, and ``value`` the statistic of
    the verdict's reading.  One more, ``where`` every tested equation's
    coefficients, when the joint reading rejects and no equation's own verdict
    does: then the data refuses the forms together and cannot say which.  It
    names each equation whose freed reading had no direction, and what that
    equation's tied reading said, because its own verdict is ``None`` and this
    warning is the only one that carries it.  A
    rejection beside another says its verdict is provisional
    (``ParametricFormTest.provisional_on``), and each tells the reader to
    read the other equations again after the refit."""
    paths = {r.name: r.paths for r in mtable.parametric}
    out: list[Diagnostic] = []
    for t in tests or []:
        if not t.rejected:
            continue
        r = t.others_freed if t.others_freed is not None else t.tied
        # the verdict is the freed reading wherever there is one; say what the
        # tied one read when it passed, since a reader comparing refits will
        # have run that one.  Tied, an equation may have had no direction to test
        # while freed it had one, so the tied statistic can be None
        how = ""
        if r is t.others_freed:
            how = " with the other equations' targets freed"
            if t.tied.statistic is None:
                how += " (with them tied it had no direction to test)"
            elif not t.tied.rejected:
                how += f" (with them tied it read {t.tied.statistic:.1f}, within the cut)"
        # every reading steps from one answer, which a rejected equation has moved
        also = ("" if not t.provisional_on else
                " The verdict is provisional: "
                + ", ".join(repr(n) for n in t.provisional_on)
                + " rejected too, and moved the answer this test steps from.")
        others = ("" if t.others_freed is None else
                  " The other equations' verdicts step from an answer this "
                  "equation has moved, so read them again after the refit.")
        out.append(Diagnostic(
            level="warning", code="PARAMETRIC_FORM_REJECTED",
            where=list(paths[t.equation]), value=r.statistic,
            message=(f"Parametric equation {t.equation!r} does not describe {t.target} across "
                     f"{t.n_patterns} of its {t.n_subset} patterns{how}: freeing "
                     f"the target in each would remove {r.statistic:.1f} times "
                     f"χ²_red of χ², past the {100 * FORM_TEST_LEVEL:g} % point "
                     f"{r.cut:.1f} of χ² for {r.dof} directions.{also}"),
            suggestion=("Add the next term to the basis and refit, or narrow the "
                        "subset to where the form holds. The chain's trajectory "
                        f"shows where it bends.{others}")))
    if joint is not None and joint.rejected and not out:
        # every equation tested at once had its own freed reading
        tested = [t for t in tests or [] if t.others_freed is not None]
        names = ", ".join(repr(t.equation) for t in tested)
        # an equation the others' targets already cover has no direction of its
        # own, so its verdict is None and only this warning carries it; say so,
        # with what its tied reading said, since that reading cannot tell its
        # misfit from theirs
        blind = [t for t in tested if t.others_freed.dof == 0]
        unseen = ""
        if blind:
            told = [f"{t.equation!r}" + ("" if t.tied is None or t.tied.statistic is None else
                                         f" (tied {t.tied.statistic:.1f} for "
                                         f"{t.tied.dof} directions, "
                                         f"{'past' if t.tied.rejected else 'within'} "
                                         f"the cut {t.tied.cut:.1f})")
                    for t in blind]
            unseen = (f" {', '.join(told)} add{'s' if len(blind) == 1 else ''} no "
                      "direction beside the other equations' targets, so no reading of "
                      f"{'its' if len(blind) == 1 else 'their'} own can test "
                      f"{'it' if len(blind) == 1 else 'them'}. The data cannot "
                      "separate that misfit from the others'.")
        out.append(Diagnostic(
            level="warning", code="PARAMETRIC_FORM_REJECTED",
            where=[p for t in tested for p in paths[t.equation]], value=joint.statistic,
            message=(f"Parametric equations {names} together do not describe their "
                     "targets: freeing every target in each pattern would remove "
                     f"{joint.statistic:.1f} times χ²_red of χ², past the "
                     f"{100 * FORM_TEST_LEVEL:g} % point {joint.cut:.1f} of χ² for "
                     f"{joint.dof} directions. No equation's own reading rejects it, so "
                     f"the data does not say which form is wrong.{unseen}"),
            suggestion=("Add the next term to one equation at a time and refit, "
                        "and compare each equation with the chain's "
                        "trajectory.")))
    return out


def _unreached_histogram_diagnostics(stage_results: list[StageResult],
                                     labels: list[str]) -> list[Diagnostic]:
    """``STAGE_FREED_NOTHING`` — a histogram a stage's globs passed over.

    Issue #265's comment: on a joint fit, a plan written with
    ``instrument.profile.*`` freed four rows on the one constant-wavelength
    histogram and none on any bank, and the joint result said ``converged``
    at Rwp 0.115 where globs naming the banks' own rows gave 0.066. Nothing a
    single-histogram fit reports could have said it, because each bank's miss
    is only a miss *beside* the histogram the same glob did reach.

    ``info``, and read off ``StageResult.unreached_histograms``, which already
    excludes the deliberate cases (a scoped glob, a declined row) and the
    healthy one (a glob matching nowhere).  What remains can still be true and
    intended — a hump declared on one histogram is reached on one side only —
    so this states what the stage did and leaves the verdict to the caller.

    One diagnostic per **histogram**, naming every stage that passed it over
    and the globs that reached elsewhere, for :func:`_hold_diagnostics`'
    reason: a cumulative plan says the same thing stage after stage. ``where``
    is those globs, the thing a caller edits; ``value`` is the histogram's
    index.
    """
    by_hist: dict[int, dict[str, list[str]]] = {}
    for sr in stage_results:
        for h, globs in (sr.unreached_histograms or {}).items():
            by_hist.setdefault(h, {})[sr.name] = list(globs)
    out: list[Diagnostic] = []
    for h in sorted(by_hist):
        stages = by_hist[h]
        where = list(dict.fromkeys(g for globs in stages.values() for g in globs))
        label = labels[h] if h < len(labels) else f"hist{h}"
        names = ", ".join(repr(s) for s in stages)
        out.append(Diagnostic(
            level="info", code="STAGE_FREED_NOTHING",
            where=where, value=float(h),
            message=(f"Stage{'' if len(stages) == 1 else 's'} {names} freed "
                     f"nothing in histogram {h} ({label}): "
                     f"{', '.join(where)} matched rows of another histogram "
                     "and none of this one."),
            suggestion=("List this histogram's parameters with "
                        f"[e.path for e in ref.mtable.tables[{h}].entries] "
                        "and add a glob that reaches them. Scope the stage "
                        "(hist.<k>.…) if one histogram was the intent."),
        ))
    return out


def _joint_fixed_literals(stages, mtable) -> list[Diagnostic]:
    """``STAGE_PATH_NOT_FREE`` for a joint plan (#803, WP-1341).

    ``refine._fixed_literal_diagnostics`` asked of each histogram's table,
    with the joint fit's second name for each row.  A literal then matches a
    row exactly when :meth:`~rietx.params.multi.MultiParameterTable.set_vary`
    would match it.  That is also the "matched" of
    :meth:`~rietx.params.multi.MultiParameterTable.unreached_histograms`, so
    on any one histogram a literal gets this finding (it matched a fixed row)
    or ``STAGE_FREED_NOTHING`` (it matched none), never both.

    A shared row is one column, so a shared path fixed in every table is one
    finding, keyed by its ``where``.  The message says which histograms' tables
    hold it.  A joint fit has no tie verb; its one caller's constraint is a
    parametric equation's target (WP-1325), spared as a single fit spares a user tie,
    since a stage naming it frees its coefficients.
    """
    found: dict[str, tuple[Diagnostic, list[int]]] = {}
    for h, table in enumerate(mtable.tables):
        for d in _fixed_literal_diagnostics(
                stages, table, mtable.parametric_targets(h),
                canonical=lambda p, h=h: mtable._canonical(h, p)):
            key = d.where[0]
            if key in found:
                found[key][1].append(h)
            else:
                found[key] = (d, [h])
    out = []
    for d, hs in found.values():
        n = mtable.n_histograms
        scope = ("every histogram" if n > 1 and len(hs) == n else
                 f"histogram{'' if len(hs) == 1 else 's'} "
                 f"{', '.join(str(h) for h in hs)}")
        out.append(d.model_copy(
            update={"message": f"{d.message.rstrip('.')} in {scope}."}))
    return out


def _joint_origin_findings(stage_results, mtable) -> list[Diagnostic]:
    """``ORIGIN_FIXED_ON_POLAR_AXIS``/``ORIGIN_NOT_FIXED`` for a joint fit (WP-1912).

    ``refine._origin_diagnostics`` asked of each histogram's table, with each
    stage's ``freed`` and ``blocked_by_hold`` cut to the names that histogram
    owns (bare shared rows and its own ``hist.<h>.`` ones, unscoped), so the
    reach test reads that table's C.  A shared coordinate is one finding,
    keyed by code and ``where``, as :func:`_joint_fixed_literals` keys a shared
    row; a sharing map that makes coordinates per histogram gets one per
    histogram, its origin being that histogram's.
    """
    found: dict[tuple[str, tuple[str, ...]], Diagnostic] = {}
    for h, table in enumerate(mtable.tables):
        prefix = f"hist.{h}."

        def own(paths, prefix=prefix):
            return [_unscoped(p) for p in paths
                    if p.startswith(prefix) or not p.startswith("hist.")]

        view = [sr.model_copy(update={"freed": own(sr.freed),
                                      "blocked_by_hold": own(sr.blocked_by_hold)})
                for sr in stage_results]
        for d in _origin_diagnostics(
                table, view, canonical=lambda p, h=h: mtable._canonical(h, p)):
            found.setdefault((d.code, tuple(d.where)), d)
    return list(found.values())


def refine_multi(data: list[PatternData], structure: Structure | list[Structure],
                 instruments: list[Instrument], *,
                 plan: RefinementPlan | str = "mccusker_default",
                 sharing: SharingMap | None = None,
                 coordinates: CoordinateTable | None = None,
                 parametric: list[ParametricEquation] | None = None,
                 two_theta_limits=None,
                 weights: list[float] | None = None,
                 backend: str = "numpy", solver: str = DEFAULT_SOLVER,
                 events=None, cancel=None, telemetry=None,
                 label: str | None = None, progress=None) -> RefinementResult:
    """One-shot joint refinement of ``structure`` against several ``data``/
    ``instruments`` pairs.  Functional wrapper over
    :class:`MultiHistogramRefinement`; ``structure`` (one, or one per
    pattern), ``coordinates`` and ``parametric`` are its constructor's
    (WP-1325), and ``events``, ``cancel``, ``telemetry``, ``label`` and
    ``progress`` its ``fit``'s."""
    ref = MultiHistogramRefinement(structure, instruments, sharing=sharing,
                                   coordinates=coordinates, parametric=parametric,
                                   backend=backend, solver=solver)
    return ref.fit(data, plan=plan, two_theta_limits=two_theta_limits, weights=weights,
                   events=events, cancel=cancel, telemetry=telemetry, label=label,
                   progress=progress)
