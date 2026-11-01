"""HIGH_CORRELATION deduplication and the per-fit cap (WP-1302).

Mostly unit-level: the mechanism is pure list processing over ``Diagnostic``
objects, and a persistently correlated real pair
(``tests/test_capillary_displacement.py``,
``tests/test_acceptance_lab6_cbn.py``) is expensive to reproduce on every run
just to re-check dedup arithmetic already covered here.

**One real fit at the end, and it covers what none of the unit tests can**
(WP-1310): that the stage loop still routes correlations through the dedup at
all.  ``_run_plan`` treats ``HIGH_CORRELATION`` unlike every other code — it
collects into ``correlation_hits`` rather than extending ``diagnostics`` — so
losing that branch restores issue #106 in full with every unit test below
still green.  0.27 s, which is what makes it affordable here rather than in
the slow selection.
"""

from __future__ import annotations

from rietx.refine import _dedup_high_correlations
from rietx.schemas.common import Diagnostic
from rietx.schemas.results import HIGH_CORRELATION_MAX, _cap_high_correlation


def _corr(a: str, b: str, rho: float) -> Diagnostic:
    return Diagnostic(level="warning", code="HIGH_CORRELATION",
                      message=f"{a} ~ {b} (ρ={rho:+.3f})",
                      where=[a, b], value=rho,
                      suggestion="consider fixing one of the correlated parameters")


def test_a_persistent_pair_across_five_stages_yields_one_diagnostic():
    """The acceptance line, literally: five stages, one pair, one finding."""
    a, b = "phases.0.cell.a", "instrument.zero_shift"
    hits = {frozenset((a, b)): [
        (f"stage{i}", _corr(a, b, rho))
        for i, rho in enumerate([0.981, 0.983, 0.986, 0.990, 0.991], start=1)
    ]}
    out = _dedup_high_correlations(hits)
    assert len(out) == 1
    assert out[0].value == 0.991  # the worst |rho|, not the last stage's
    assert "stage1" in out[0].message and "stage5" in out[0].message


def test_a_pair_seen_once_keeps_the_original_message_untouched():
    a, b = "phases.0.cell.a", "phases.0.scale"
    hits = {frozenset((a, b)): [("cell", _corr(a, b, 0.99))]}
    out = _dedup_high_correlations(hits)
    assert out[0].message == "phases.0.cell.a ~ phases.0.scale (ρ=+0.990)"


def test_where_stays_in_the_order_the_message_names_them():
    """``where`` must not be rebuilt from the ``frozenset`` dict key — its
    iteration order is hash-randomized per process, so ``list(pair)`` could
    name the two paths in the opposite order from the one already baked
    into ``message`` (found by code review).
    """
    a, b = "instrument.zero_shift", "instrument.geometry.sample_displacement"
    hits = {frozenset((a, b)): [
        ("stage1", _corr(a, b, 0.996)), ("stage2", _corr(a, b, 0.999))]}
    out = _dedup_high_correlations(hits)
    assert out[0].where == [a, b]
    assert out[0].message.startswith(f"{a} ~ {b}")


def test_distinct_pairs_stay_distinct_and_sort_worst_first():
    hits = {
        frozenset(("a", "b")): [("s1", _corr("a", "b", 0.90))],
        frozenset(("c", "d")): [("s1", _corr("c", "d", -0.99))],
    }
    out = _dedup_high_correlations(hits)
    assert [d.value for d in out] == [-0.99, 0.90]


def test_cap_passes_a_short_list_through_unchanged():
    diags = [_corr(f"a{i}", f"b{i}", 0.9) for i in range(HIGH_CORRELATION_MAX)]
    assert _cap_high_correlation(diags) == diags


def test_cap_keeps_the_worst_ten_and_names_the_rest():
    diags = [_corr(f"a{i}", f"b{i}", 0.90 + i * 0.001) for i in range(15)]
    out = _cap_high_correlation(diags)

    kept = [d for d in out if d.code == "HIGH_CORRELATION"]
    omitted = [d for d in out if d.code == "HIGH_CORRELATION_OMITTED"]
    assert len(kept) == HIGH_CORRELATION_MAX
    assert len(omitted) == 1
    assert omitted[0].level == "info"
    assert omitted[0].value == 5.0
    assert "result.identifiability" in omitted[0].suggestion
    # worst first, and nothing below the cap survived
    assert [round(d.value, 3) for d in kept] == sorted(
        (round(d.value, 3) for d in kept), reverse=True)
    assert min(d.value for d in kept) > max(
        (d.value for d in diags if d not in kept), default=0.0) - 1e-9


def test_cap_leaves_every_other_code_untouched():
    other = Diagnostic(level="warning", code="BOUND_HIT", message="x refined to its bound",
                       where=["x"], value=None, suggestion="widen the bound")
    diags = [other, *[_corr(f"a{i}", f"b{i}", 0.9) for i in range(12)]]
    out = _cap_high_correlation(diags)
    assert other in out
    assert sum(1 for d in out if d.code == "HIGH_CORRELATION") == HIGH_CORRELATION_MAX
    assert sum(1 for d in out if d.code == "HIGH_CORRELATION_OMITTED") == 1


def test_the_cap_is_never_applied_to_a_stored_diagnostics_list():
    """The cap is display-only (WP-1302, moved after code review): a pair
    ranked outside the top ten in every pattern of a series must still be
    countable by ``sequential._persistent_diagnostics`` as "N of M" — which
    reads straight off ``RefinementResult.diagnostics``/``SeriesEntry.diagnostics``,
    never a rendered view. Only ``_diagnostic_lines`` (schemas/results.py,
    what ``str(result)`` calls) applies :func:`_cap_high_correlation`.
    """
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult, Statistics, _diagnostic_lines

    many = [_corr(f"a{i}", f"b{i}", 0.9 - i * 0.001) for i in range(15)]
    result = RefinementResult(
        status="converged", mode="rietveld", parameters=[], diagnostics=many,
        statistics=Statistics(rwp=0.1, rp=0.08, rexp=0.05, chi2=4.0, gof=2.0,
                              n_points=100, n_free_parameters=5),
        provenance=Provenance(package_version="0.0.0+test"))

    # the stored list carries all 15 — nothing was dropped from the data
    assert sum(1 for d in result.diagnostics if d.code == "HIGH_CORRELATION") == 15

    # only the rendered view is bounded; the header counts the stored list
    # (WP-2037: no deliverable, so each warning prints as one line)
    text = str(result)
    assert text.count("    HIGH_CORRELATION at ") == HIGH_CORRELATION_MAX
    assert "HIGH_CORRELATION_OMITTED" in text
    assert "diagnostics: 15 rows, 0 errors;" in text

    # under a deliverable each prints in full, and the count is still the stored one
    lines = _diagnostic_lines(result.diagnostics, "structure")
    assert lines[0] == "  diagnostics under structure: 15 warnings, 0 errors, 0 info"
    assert sum(1 for ln in lines if "[HIGH_CORRELATION]:" in ln) == HIGH_CORRELATION_MAX
    assert "    info[HIGH_CORRELATION_OMITTED]: 5 more correlated pair(s)" in "\n".join(lines)


# --- the routing (WP-1310) -----------------------------------------------
#
# Everything above tests ``_dedup_high_correlations`` as a function.  Nothing
# above tests that the stage loop still *calls* it: ``_run_plan`` collects
# ``HIGH_CORRELATION`` into ``correlation_hits`` instead of extending
# ``diagnostics`` like every other code, and a regression that dropped that
# branch would restore issue #106 with every unit test above still green.
# Hence one real fit, kept as cheap as a real fit can be (~1 s).


def _lab6_pattern():
    """LaB6 over a range wide enough for the axial pair to be measurable.

    The pattern carries S/L = H/L = 0.02, so the pair's minimum is inside its
    box.  Simulated at the default 0, the LM driver puts H/L exactly on its
    floor, where S/L's column is zero, and the last stage no longer measures
    the pair (WP-1938)."""
    import numpy as np

    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import Instrument
    from rietx.schemas.pattern import PatternData
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = 0.02
    tt = np.arange(15.0, 110.0, 0.02)
    empty = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, empty, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 80.0
    rng = np.random.default_rng(11)
    return PatternData(
        two_theta=model.tt.tolist(),
        intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def test_a_real_plan_reports_a_persistent_pair_once_naming_every_stage():
    """Issue #106 end to end: four stages measure the pair, one entry survives.

    ``axial_sl ~ axial_hl`` is the ρ = −1.000 pair the issue named, and the
    FCJ axial pair is exactly degenerate on a well-centred specimen, so it
    fires on every stage that re-measures the Jacobian after it goes free.
    The plan is **cumulative**, which is what makes that happen: the pair is
    freed in stage 2 and stays free, so stages 3, 4 and 5 each re-measure it.

    The assertion is on the *stored* list, never ``str(result)`` — the render
    cap would bound the count either way and so could not tell dedup from
    truncation.
    """
    import collections

    import rietx as rx
    from rietx.schemas.instrument import Instrument
    from rietx.strategy.staged import RefinementPlan, Stage
    from tests.test_schemas import make_lab6

    sl, hl = "instrument.geometry.axial_sl", "instrument.geometry.axial_hl"
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("axial", [sl, hl]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile", ["instrument.profile.w"]),
        Stage("biso", ["phases.*.atoms.*.biso"]),
    ])
    ref = rx.Refinement(make_lab6(),
                        Instrument.debye_scherrer(wavelength=1.5406),
                        history=False)
    result = ref.fit(_lab6_pattern(), plan=plan)

    corr = [d for d in result.diagnostics if d.code == "HIGH_CORRELATION"]
    pairs = collections.Counter(frozenset(d.where) for d in corr)
    assert pairs, "the axial pair raised no HIGH_CORRELATION at all"
    assert max(pairs.values()) == 1, (
        "a pair is reported more than once — the stage loop is no longer "
        f"routing through _dedup_high_correlations: {[d.message for d in corr]}")

    axial = [d for d in corr if set(d.where) == {sl, hl}]
    assert len(axial) == 1
    # the four stages that re-measured it are named, which is what makes one
    # entry as informative as the four it replaces
    assert "Flagged in stages:" in axial[0].message
    for stage in ("axial", "cell", "profile", "biso"):
        assert stage in axial[0].message
