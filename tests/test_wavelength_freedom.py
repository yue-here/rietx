"""The wavelength–cell degeneracy fence, and the parameter path behind it.

Fast tests over synthetic two-histogram fixtures.  The real-data acceptance —
the published joint refinement this feature exists for — is
``tests/test_acceptance_wavelength.py``.

Two halves.  The first is the **refusal**: for one histogram λ and the cell are
exactly degenerate (Bragg's law fixes only λ/2d), so a free λ is refused; for N
histograms of one specimen the shared cell breaks the degeneracy, so exactly one
held and at most N − 1 free is admitted and everything else is refused, each
case naming its own cause.  The second is the **wiring**: a parameter registered
in ``_collect_instrument`` and forgotten in ``apply_to_models`` loses its
refined value at the next recompile without failing anything, which is the
failure mode ``params/vector.py``'s own comment warns about, and a neutron
source is where it would happen — ``NeutronSource.lines`` is a property that
builds a fresh ``EmissionLine`` per access.
"""

import numpy as np
import pytest

from rietx import Instrument, MultiHistogramRefinement, PatternData, Refinement
from rietx.model.forward import compile_model
from rietx.params.multi import MultiParameterTable, SharingMap
from rietx.params.vector import (
    ParameterTable,
    _is_wavelength,
    check_wavelength_freedom,
)
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, NeutronSource
from tests.test_schemas import make_lab6

WL = "instrument.source.lines.0.wavelength"


def _blank(lo=10.0, hi=90.0, step=0.05) -> PatternData:
    tt = np.arange(lo, hi, step)
    return PatternData(two_theta=tt.tolist(),
                       intensity=np.ones_like(tt).tolist())


# --- the schema surface ---------------------------------------------------


def test_a_bare_number_is_still_a_wavelength():
    """The pre-0.6 spelling keeps working, and it means ``vary=False``.

    ``wavelength`` was a plain float through v1.1, so every construction site
    and every persisted instrument spells it as a number.  Accepting one makes
    the field's own history the migration.
    """
    line = EmissionLine(wavelength=1.5406)
    assert isinstance(line.wavelength, Parameter)
    assert line.wavelength.value == 1.5406
    assert line.wavelength.vary is False
    assert NeutronSource(wavelength=2.078).primary_wavelength == 2.078
    # and a Parameter is accepted as itself
    free = EmissionLine(wavelength=Parameter(value=1.0, min=0.5, vary=True))
    assert free.wavelength.vary is True


def test_a_nonpositive_wavelength_is_refused():
    """λ reaches the model only through λ/2d, so zero is not an off state."""
    with pytest.raises(ValueError, match="positive"):
        EmissionLine(wavelength=Parameter(value=0.0, min=-1.0))


def test_the_neutron_wavelength_is_written_through_a_property_not_lines():
    """``wavelength_parameters`` is the one authority for a write.

    ``NeutronSource.lines`` builds a fresh object per access, so a write there
    is silently lost — which is exactly what would make a refined λ vanish at
    the next stage's recompile.  Both arms of the union answer the same
    property, so ``params/vector.py`` needs no case split.
    """
    src = NeutronSource(wavelength=2.078)
    assert src.wavelength_parameters == [src.wavelength]
    assert src.wavelength_parameters[0] is src.wavelength
    # the read-only view really is a copy: writing to it changes nothing
    src.lines[0].wavelength.value = 9.9
    assert src.wavelength.value == 2.078
    xray = Instrument.bragg_brentano().source
    assert xray.wavelength_parameters[0] is xray.lines[0].wavelength
    assert len(xray.wavelength_parameters) == 2


# --- the refusals --------------------------------------------------------


def test_one_histogram_refuses_a_free_wavelength():
    """The flat direction, named where the table can see it.

    ``ParameterTable.__init__`` sees one instrument, so it always reads the
    N = 1 case and can decide it outright — the symmetry-refusals-live-in-the
    -table rule of the root CLAUDE.md.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.source.lines[0].wavelength.vary = True
    with pytest.raises(ValueError, match="single-histogram"):
        ParameterTable(make_lab6(), ins)


def test_a_glob_cannot_free_it_in_a_single_histogram_table():
    """The lock, not the refusal, is what a *glob* meets.

    A staged plan frees by glob, and a refusal there would turn a broad plan
    into an error rather than a fit.  So the row is force-fixed in a
    single-histogram table and locked entries never match however wide the glob
    — the same treatment as a symmetry-fixed cell angle.  The refusal above is
    for a *declared* ``vary=True``, which is a claim the caller made.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(make_lab6(), ins)
    assert table.set_vary([WL], True) == []
    assert table.set_vary(["*"], True) == [] or WL not in table.free_paths
    row = next(e for e in table.entries if e.path == WL)
    assert row.locked is True


def test_only_line_zero_is_ever_refinable():
    """Within one source the lines' *ratio* is atomic physics.

    A Kα1/Kα2 pair is known to ~20 ppm and is not measurable against the cell
    it shares with line 0, so a secondary line's wavelength is force-fixed
    rather than merely unfree — the WP-1073 rule.  It is the exact mirror of the
    *weight* rule: there line 0 is the locked one, because a weight's scale
    lives inside the source and a wavelength's lives outside it.
    """
    ins = Instrument.bragg_brentano()
    table = ParameterTable(make_lab6(), ins, joint=True)
    rows = {e.path: e for e in table.entries if _is_wavelength(e.path)}
    assert len(rows) == 2
    assert rows["instrument.source.lines.0.wavelength"].locked is False
    assert rows["instrument.source.lines.1.wavelength"].locked is True
    # the weight rule, pointed the other way, in the same table
    assert next(e for e in table.entries
                if e.path == "instrument.source.lines.0.weight").locked is True
    assert next(e for e in table.entries
                if e.path == "instrument.source.lines.1.weight").locked is False


def test_two_histograms_admit_one_free_wavelength_and_refuse_two():
    """The count, and the message that states it."""
    ins = [Instrument.debye_scherrer(wavelength=0.41390),
           Instrument.debye_scherrer(wavelength=0.71070)]
    mt = MultiParameterTable(make_lab6(), list(ins))
    assert mt.set_vary([f"hist.1.{WL}"], True) == [f"hist.1.{WL}"]
    with pytest.raises(ValueError, match="2 of 2 wavelengths are free"):
        mt.set_vary([f"hist.0.{WL}"], True)
    # the bare (unscoped) glob frees both copies at once, hence the same refusal
    fresh = MultiParameterTable(make_lab6(), list(ins))
    with pytest.raises(ValueError, match="2 of 2 wavelengths are free"):
        fresh.set_vary([WL], True)


def test_three_histograms_admit_two_free_wavelengths():
    """The general N − 1 case, not just N = 2."""
    ins = [Instrument.debye_scherrer(wavelength=lam)
           for lam in (0.41390, 0.71070, 1.54060)]
    mt = MultiParameterTable(make_lab6(), ins)
    mt.set_vary([f"hist.1.{WL}", f"hist.2.{WL}"], True)
    assert sum(1 for p in mt.free_paths if p.endswith(".wavelength")) == 2
    with pytest.raises(ValueError, match="3 of 3 wavelengths are free"):
        mt.set_vary([f"hist.0.{WL}"], True)


def test_a_one_histogram_joint_fit_is_still_a_single_histogram_fit():
    """``MultiParameterTable`` accepts N = 1, and the physics does not change."""
    ins = Instrument.debye_scherrer(wavelength=0.41390)
    mt = MultiParameterTable(make_lab6(), [ins])
    with pytest.raises(ValueError, match="single-histogram"):
        mt.set_vary([f"hist.0.{WL}"], True)


def test_an_unshared_cell_refuses_every_free_wavelength():
    """The general rule, of which "one held, N − 1 free" is the special case.

    λ is measurable only against a cell some *other* histogram's held λ has
    pinned.  Give each histogram its own cell — a legitimate thing to want when
    two histograms are two preparations — and the single-histogram degeneracy
    is back per histogram, inside a joint fit where it would look solved.
    """
    ins = [Instrument.debye_scherrer(wavelength=0.41390),
           Instrument.debye_scherrer(wavelength=0.71070)]
    mt = MultiParameterTable(make_lab6(), ins,
                             sharing=SharingMap(per_histogram=["phases.*.cell.*"]))
    with pytest.raises(ValueError, match="per-histogram"):
        mt.set_vary([f"hist.1.{WL}"], True)


def test_the_check_is_one_function_with_three_cases():
    """Called by both tables; the messages are its contract."""
    check_wavelength_freedom([], 2, 2)                  # nothing free: silent
    check_wavelength_freedom([f"hist.1.{WL}"], 2, 2)    # one of two: fine
    with pytest.raises(ValueError, match="single-histogram"):
        check_wavelength_freedom([WL], 1, 1)
    with pytest.raises(ValueError, match="hold one"):
        check_wavelength_freedom([f"hist.0.{WL}", f"hist.1.{WL}"], 2, 2)
    with pytest.raises(ValueError, match="per-histogram"):
        check_wavelength_freedom([f"hist.1.{WL}"], 2, 2, cell_shared=False)


def test_suggest_never_proposes_a_wavelength():
    """A suggestion is "free this next", and a locked row is not freeable.

    No special case in ``suggest`` for this: the row is force-fixed in a
    single-histogram table, so ``ParameterRow.refinable`` is already ``False``
    and the enumeration drops it — which is also what makes
    ``held_because`` tell the truth about it.
    """
    ref = Refinement(make_lab6(), Instrument.debye_scherrer(wavelength=1.5406),
                     history=False)
    out = ref.suggest(_blank(), top_n=50)
    considered = {c.path for g in out.groups for c in g.members}
    assert not [p for p in considered if p.endswith(".wavelength")]


# --- the wiring ----------------------------------------------------------


def test_the_wavelength_is_a_table_row_and_survives_write_back():
    """Registered in ``_collect_instrument`` *and* ``apply_to_models``.

    The second half is what has no other test: a value written into θ and never
    written back looks refined until the next recompile silently reverts it.
    Checked on a **neutron** source, where the write has to go through
    ``wavelength_parameters`` rather than ``lines``.
    """
    structure = make_lab6()
    ins = Instrument.constant_wavelength_neutron(2.078, fwhm_deg=0.3)
    mt = MultiParameterTable(structure, [ins, ins.model_copy(deep=True)])
    mt.set_vary([f"hist.1.{WL}"], True)
    theta = mt.x0()
    col = mt.free_paths.index(f"hist.1.{WL}")
    theta[col] = 2.0800
    mt.commit(theta)
    mt.apply_to_models()
    assert mt.instruments[1].source.wavelength.value == pytest.approx(2.0800)
    assert mt.instruments[0].source.wavelength.value == pytest.approx(2.078)
    # …and the *forward model* reads it, which is the other half of the wiring
    assert mt.tables[1].decode(mt.split(theta)[1])[WL] == pytest.approx(2.0800)


def test_the_forward_model_reads_lambda_from_theta_not_from_compile():
    """A free λ must move peaks *inside* a stage.

    ``CompiledModel.line_wavelengths`` is the compile-time value the frozen
    windows were sized from; ``line_lambdas`` is what the residual reads.  The
    peak positions have to follow the second, or the Jacobian column would be
    identically zero and the parameter would sit still while reporting an esd.
    """
    structure = make_lab6()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    data = _blank()
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    base = model.phase_peaks(0, values)[0][0].copy()
    moved = dict(values)
    moved[WL] = 1.5406 * 1.001            # +1000 ppm
    shifted = model.phase_peaks(0, moved)[0][0]
    assert np.all(np.isfinite(base[:3])) and np.all(np.isfinite(shifted[:3]))
    assert np.all(shifted[:3] > base[:3])
    # Δ2θ = 2·tanθ·Δλ/λ, the doublet-splitting law applied to one line
    theta_r = np.radians(0.5 * base[:3])
    predicted = np.degrees(2.0 * np.tan(theta_r) * 1e-3)
    assert shifted[:3] - base[:3] == pytest.approx(predicted, rel=2e-3)
    # a value dict that does not mention λ falls back to the frozen tuple, so
    # every non-refinement caller (plots, exporters, replay) is unchanged
    bare = {k: v for k, v in values.items() if k != WL}
    assert model.line_lambdas(bare) == [pytest.approx(1.5406)]


def test_a_held_wavelength_leaves_the_fit_bit_identical():
    """The default is the identity, and identity means the bit.

    Nothing about a fit that frees no wavelength may move: the new row's only
    effect is one more entry in the table and one more constant in every memo
    key.  Measured against a fresh evaluation of the same state, which is where
    a changed memo key would show up.
    """
    structure = make_lab6()
    ins = Instrument.bragg_brentano()
    data = _blank(20.0, 100.0)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    values = table.decode(table.x0())
    first = model.evaluate(values)
    # a cell column's worth of memo traffic between the two evaluations, which
    # is what a two-deep slot is for; the answer must be bit-identical anyway
    perturbed = dict(values)
    perturbed["phases.0.cell.a"] = values["phases.0.cell.a"] * 1.0001
    model.evaluate(perturbed)
    assert np.array_equal(first, model.evaluate(values))


def test_the_analytic_column_matches_finite_differences():
    """λ rides the peak-chain branch, and its reach claim is checkable.

    ``scalar_chain_supported`` claims that everything λ touches is one of the
    four per-peak scalars.  Here that claim meets a whole-model finite
    difference — the column that decodes through C exactly as the residual
    does — on a two-histogram state where λ is genuinely free.
    """
    from rietx.optimize.least_squares import _make_jacobian, _make_residual

    structure = make_lab6()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    data = _blank(20.0, 100.0)
    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins, joint=True)   # joint ⇒ λ may be free
    table.set_vary(["phases.*.scale", WL, "instrument.zero_shift"], True)
    c = table.free_paths.index(WL)
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)[:, c]
    residual = _make_residual(model, table)
    h = 1e-7
    lo, hi = theta.copy(), theta.copy()
    lo[c] -= h
    hi[c] += h
    fd = (residual(hi) - residual(lo)) / (2.0 * h)
    assert np.linalg.norm(jac) > 0.0, "the λ column came back identically zero"
    assert (np.linalg.norm(jac - fd) / np.linalg.norm(fd)) < 5e-3


def test_a_joint_fit_reports_the_calibration_move_in_ppm():
    """``WAVELENGTH_CALIBRATION`` on a synthetic pair with a planted error.

    Two patterns of one crystal, the second's λ declared 500 ppm below the
    value it was generated at.  The diagnostic must report roughly +500 ppm,
    carry it as ``Diagnostic.value``, and fire only on the histogram whose λ
    was freed.
    """
    from rietx.strategy.staged import RefinementPlan, Stage
    from tests.test_multi_histogram import synthesize

    true_lam = 1.5406
    d0 = synthesize(0.7107, 8.0, 60.0, scale=1e4, zero=0.0, bkg=[50.0, 0.0])
    d1 = synthesize(true_lam, 20.0, 120.0, scale=1e4, zero=0.0, bkg=[50.0, 0.0])
    ins0 = Instrument.debye_scherrer(wavelength=0.7107)
    ins1 = Instrument.debye_scherrer(wavelength=true_lam * (1.0 - 500e-6))
    for ins in (ins0, ins1):
        ins.profile.w.value = 3e-4
    p = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("wavelength", [f"hist.1.{WL}", "phases.*.cell.*"]),
    ])
    joint = MultiHistogramRefinement(make_lab6(), [ins0, ins1])
    result = joint.fit([d0, d1], plan=p)
    diags = [d for h in result.histograms for d in h.diagnostics
             if d.code == "WAVELENGTH_CALIBRATION"]
    assert len(diags) == 1
    assert diags[0].where == [f"hist.1.{WL}"]
    assert diags[0].value == pytest.approx(500.0, rel=0.25)
    assert "ppm" in diags[0].message
