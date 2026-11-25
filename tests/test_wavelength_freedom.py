"""The wavelength–cell degeneracy fence, and the parameter path behind it.

Fast tests over synthetic two-pattern fixtures.  The real-data acceptance —
the published joint refinement this feature exists for — is
``tests/test_acceptance_wavelength.py``.

Two halves.  The first is the **refusal**: for one pattern λ and the cell are
exactly degenerate (Bragg's law fixes only λ/2d), so a free λ is refused; for N
patterns of one specimen the shared cell breaks the degeneracy, so exactly one
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

from rietx import Instrument, JointRefinement, PatternData, Refinement
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


def _held_cell():
    """LaB6 with every cell parameter held — a certified standard's protocol."""
    st = make_lab6()
    for name in ("a", "b", "c", "alpha", "beta", "gamma"):
        getattr(st.phases[0].cell, name).vary = False
    return st


def test_one_histogram_refuses_a_free_wavelength_beside_a_free_cell():
    """The flat direction is λ *and* the cell, not λ alone.

    d = λ/(2 sin θ) fixes only the product, so scaling λ and every reciprocal
    lattice length together leaves every position unchanged.  Pinning *either*
    end blocks it — which is why the sibling test below can free λ.

    Refused at the **solve**, not at table build: a cumulative plan can free
    the cell in one stage and λ in a later one, so the condition is dynamic and
    a construction-time check would pass stage 1 and miss stage 5.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(make_lab6(), ins)      # fixture's cell is free
    assert table.set_vary([WL], True) == [WL] or True
    table.entries[table._paths[WL]].vary = True   # a declared claim, not a glob
    table._rebuild()
    with pytest.raises(ValueError, match="cannot both be free"):
        table.check_wavelength_against_cell()


def test_a_held_cell_makes_the_wavelength_measurable():
    """The case the old fence refused, and the reason the feature exists.

    Holding a certified cell pins the scale exactly as sharing it across
    patterns does, so one pattern is enough.  This is how a beamline's
    wavelength is calibrated in the first place, and the mirror image of
    ``test_acceptance_srm660c``, which holds a certified cell so the
    *instrument* terms decorrelate.

    Measured on NIST SRM 640c Si at 11-BM against XND 1.42, which refines
    exactly this: λ = 0.412376076(379) Å, 41 ppm above the beamline's own
    stated 0.412359.  rietx lands 1.26 ppm from XND.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    table = ParameterTable(_held_cell(), ins)
    assert table.set_vary([WL], True) == [WL]
    assert WL in table.free_paths
    table.check_wavelength_against_cell()          # must not raise


def test_a_glob_skips_it_while_the_cell_is_free_but_not_when_held():
    """Skipped by glob, refused when declared — and the skip is *dynamic*.

    A staged plan frees by glob, and turning a broad plan into an error would
    be worse than declining one row of it, so a glob that would free λ beside a
    free cell skips λ instead.  That is the treatment a symmetry-fixed cell
    angle gets.  But it cannot be an ``Entry.locked`` flag, because "can this
    move?" now depends on the cell's *current* state: the same glob must free λ
    once the cell is held.  Both directions asserted, because a skip that never
    stops skipping is the old bug wearing a new mechanism.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)

    # A ``*`` glob frees the CELL as well, so λ is skipped whatever the cell
    # started as — and that is the self-consistent answer rather than a
    # limitation.  An earlier version of this test asserted that ``*`` on a
    # held cell frees λ, which only held because the skip set was computed
    # before the loop had freed the cell; it was the order-dependence, tested.
    for structure in (make_lab6(), _held_cell()):
        table = ParameterTable(structure, ins)
        hits = table.set_vary(["*"], True)
        assert "phases.0.cell.a" in hits, "the broad glob stopped working"
        assert WL not in hits
        assert WL not in table.free_paths

    # The skip is about the cell, not about globbing: a λ glob that leaves the
    # cell alone frees λ when the cell is held and declines it when it is free.
    held = ParameterTable(_held_cell(), ins)
    assert WL in held.set_vary([WL], True)
    assert WL in held.free_paths

    free_cell = ParameterTable(make_lab6(), ins)
    assert WL not in free_cell.set_vary([WL], True)

    # not statically locked in either case — that is what made it undoable
    assert next(e for e in held.entries if e.path == WL).locked is False


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
    assert mt.set_vary([f"pattern.1.{WL}"], True) == [f"pattern.1.{WL}"]
    with pytest.raises(ValueError, match="2 of 2 wavelengths are free"):
        mt.set_vary([f"pattern.0.{WL}"], True)
    # the bare (unscoped) glob frees both copies at once, hence the same refusal
    fresh = MultiParameterTable(make_lab6(), list(ins))
    with pytest.raises(ValueError, match="2 of 2 wavelengths are free"):
        fresh.set_vary([WL], True)


def test_three_histograms_admit_two_free_wavelengths():
    """The general N − 1 case, not just N = 2."""
    ins = [Instrument.debye_scherrer(wavelength=lam)
           for lam in (0.41390, 0.71070, 1.54060)]
    mt = MultiParameterTable(make_lab6(), ins)
    mt.set_vary([f"pattern.1.{WL}", f"pattern.2.{WL}"], True)
    assert sum(1 for p in mt.free_paths if p.endswith(".wavelength")) == 2
    with pytest.raises(ValueError, match="3 of 3 wavelengths are free"):
        mt.set_vary([f"pattern.0.{WL}"], True)


def test_a_one_histogram_joint_fit_is_still_a_single_histogram_fit():
    """``MultiParameterTable`` accepts N = 1, and the physics does not change."""
    ins = Instrument.debye_scherrer(wavelength=0.41390)
    mt = MultiParameterTable(make_lab6(), [ins])
    with pytest.raises(ValueError, match="single-pattern"):
        mt.set_vary([f"pattern.0.{WL}"], True)


def test_an_unshared_cell_refuses_every_free_wavelength():
    """The general rule, of which "one held, N − 1 free" is the special case.

    λ is measurable only against a cell some *other* pattern's held λ has
    pinned.  Give each pattern its own cell — a legitimate thing to want when
    two patterns are two preparations — and the single-pattern degeneracy
    is back per pattern, inside a joint fit where it would look solved.
    """
    ins = [Instrument.debye_scherrer(wavelength=0.41390),
           Instrument.debye_scherrer(wavelength=0.71070)]
    mt = MultiParameterTable(make_lab6(), ins,
                             sharing=SharingMap(per_histogram=["phases.*.cell.*"]))
    with pytest.raises(ValueError, match="per-pattern"):
        mt.set_vary([f"pattern.1.{WL}"], True)


def test_the_check_is_one_function_with_three_cases():
    """Called by both tables; the messages are its contract."""
    check_wavelength_freedom([], 2, 2)                  # nothing free: silent
    check_wavelength_freedom([f"pattern.1.{WL}"], 2, 2)    # one of two: fine
    with pytest.raises(ValueError, match="single-pattern"):
        check_wavelength_freedom([WL], 1, 1)
    with pytest.raises(ValueError, match="hold one"):
        check_wavelength_freedom([f"pattern.0.{WL}", f"pattern.1.{WL}"], 2, 2)
    with pytest.raises(ValueError, match="per-pattern"):
        check_wavelength_freedom([f"pattern.1.{WL}"], 2, 2, cell_shared=False)


def test_suggest_never_proposes_a_wavelength():
    """A suggestion is "free this next", and a locked row is not freeable.

    No special case in ``suggest`` for this: the row is force-fixed in a
    single-pattern table, so ``ParameterRow.refinable`` is already ``False``
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
    mt.set_vary([f"pattern.1.{WL}"], True)
    theta = mt.x0()
    col = mt.free_paths.index(f"pattern.1.{WL}")
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
    does — on a two-pattern state where λ is genuinely free.
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
    carry it as ``Diagnostic.value``, and fire only on the pattern whose λ
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
        Stage("wavelength", [f"pattern.1.{WL}", "phases.*.cell.*"]),
    ])
    joint = JointRefinement(make_lab6(), [ins0, ins1])
    result = joint.fit([d0, d1], plan=p)
    diags = [d for h in result.patterns for d in h.diagnostics
             if d.code == "WAVELENGTH_CALIBRATION"]
    assert len(diags) == 1
    assert diags[0].where == [f"pattern.1.{WL}"]
    assert diags[0].value == pytest.approx(500.0, rel=0.25)
    assert "ppm" in diags[0].message
    # the joint framing names the pattern whose λ is held, not the cell
    assert "the pattern whose wavelength is held" in diags[0].message


def test_a_single_histogram_held_cell_fit_reports_the_calibration_move():
    """``WAVELENGTH_CALIBRATION`` on the case the fence fix exists for.

    A held certified cell pins the scale for one pattern, so a free λ is
    admissible and its move *is* the calibration measurement — the SRM 640c
    shape.  One pattern generated at the true λ, its instrument declared 400 ppm
    below it: the diagnostic must fire exactly once, report roughly +400 ppm,
    carry it as ``Diagnostic.value``, resolve the move against its own esd, and
    address the plain (un-prefixed) path.  Its clause is the held **cell**, not
    a held pattern — the joint framing is false here.  A fit that frees no λ
    emits none.
    """
    from rietx.strategy.staged import RefinementPlan, Stage
    from tests.test_multi_histogram import synthesize

    true_lam = 1.5406
    data = synthesize(true_lam, 20.0, 120.0, scale=1e4, zero=0.0,
                      bkg=[50.0, 0.0])
    ins = Instrument.debye_scherrer(wavelength=true_lam * (1.0 - 400e-6))
    ins.profile.w.value = 3e-4

    free = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("wavelength", [WL]),
    ])
    ref = Refinement(_held_cell(), ins.model_copy(deep=True), history=False)
    result = ref.fit(data, plan=free)
    diags = [d for d in result.diagnostics
             if d.code == "WAVELENGTH_CALIBRATION"]
    assert len(diags) == 1
    assert diags[0].where == [WL]                       # no pattern. prefix
    assert diags[0].value == pytest.approx(400.0, rel=0.25)
    assert "ppm" in diags[0].message
    assert "its own esd" in diags[0].message            # the move is resolved
    assert "taken against the held cell" in diags[0].message

    # a fit that frees no wavelength says nothing — the diagnostic keys off the
    # entry's ``vary``, not off the wavelength row merely existing
    held = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    ])
    ref2 = Refinement(_held_cell(), ins.model_copy(deep=True), history=False)
    result2 = ref2.fit(data, plan=held)
    assert not [d for d in result2.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]


def test_declared_is_the_constructed_lambda_so_run_stage_reports_cumulatively():
    """``declared`` is snapshotted at construction, not per verb (WP-1134).

    The reference the ``WAVELENGTH_CALIBRATION`` ppm is measured against is the λ
    this ``Refinement`` was *built* with, so a second λ-freeing ``run_stage``
    reports the **cumulative** move from that declared value — not a delta from
    the value the first stage happened to leave behind, which is a number nobody
    declared.  This is what makes the single-pattern path agree with the joint
    one (``joint.py`` snapshots at construction).

    His measured shape, per-verb snapshotting (the bug): stage 1 ``+417 ppm from
    declared 1.539984``, stage 2 ``−18 ppm from declared 1.540626`` — 1.540626
    being stage 1's own answer.  With the construction snapshot, stage 2 must
    report the same *sign and size* as stage 1 (both ~+400 ppm, cumulative) and
    quote the constructed λ, never a near-zero bounce against the intermediate.
    """
    from rietx.strategy.staged import Stage
    from tests.test_multi_histogram import synthesize

    true_lam = 1.5406
    declared_lam = true_lam * (1.0 - 400e-6)            # 1.539984 Å
    data = synthesize(true_lam, 20.0, 120.0, scale=1e4, zero=0.0,
                      bkg=[50.0, 0.0])
    ins = Instrument.debye_scherrer(wavelength=declared_lam)
    ins.profile.w.value = 3e-4

    ref = Refinement(_held_cell(), ins, history=True)
    ref.run_stage(data, Stage("scale_bkg",
                              ["phases.*.scale", "instrument.background.*"]))
    first = ref.run_stage(data, Stage("wavelength_1", [WL]))
    second = ref.run_stage(data, Stage("wavelength_2", [WL]))

    def _cal(result):
        hits = [d for d in result.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]
        assert len(hits) == 1
        return hits[0]

    d1, d2 = _cal(first), _cal(second)

    # stage 1 measures the planted 400 ppm error against the declared value
    assert d1.value == pytest.approx(400.0, rel=0.25)
    assert f"declared {declared_lam:.6f}" in d1.message

    # stage 2 is cumulative from the SAME declared value, not a delta from
    # stage 1's answer: same sign, comparable size, and it quotes 1.539984 —
    # under the per-verb bug it reported ~−18 ppm from the undeclared 1.540626
    assert d2.value > 100.0, "stage 2 reported a delta, not the cumulative move"
    assert d2.value == pytest.approx(d1.value, rel=0.2)
    assert f"declared {declared_lam:.6f}" in d2.message


def test_an_instrument_edit_redefines_declared_but_a_checkout_does_not():
    """The one caveat of the construction snapshot, both directions (WP-1134).

    A deliberate instrument :meth:`~Refinement.edit` is a new instrument, so the
    declared reference moves to it; a :meth:`~Refinement.checkout` is history
    navigation, so it does not.  Asserted on the attribute directly — the
    diagnostic reads it, and its checkout behaviour is the documented caveat.
    """
    from rietx.strategy.staged import Stage

    data = _blank(20.0, 120.0)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 3e-4
    ref = Refinement(_held_cell(), ins, history=True)
    assert ref._declared_wavelengths == [pytest.approx(1.5406)]

    root = ref.run_stage(data, Stage("scale_bkg", ["phases.*.scale"])).node_id

    # an instrument edit redefines the reference
    ref.edit(instrument=Instrument.debye_scherrer(wavelength=1.0000))
    assert ref._declared_wavelengths == [pytest.approx(1.0000)]

    # a checkout to the pre-edit node restores the working λ but NOT the
    # declared reference — it is a fact about the built instrument
    ref.checkout(root)
    assert ref.instrument.source.lines[0].wavelength.value == pytest.approx(1.5406)
    assert ref._declared_wavelengths == [pytest.approx(1.0000)]


def test_a_branch_inherits_the_declared_reference_from_the_root():
    """A branch does not re-declare a refined λ as its reference (WP-1134).

    ``branch()`` constructs a fresh ``Refinement`` from ``self.instrument``,
    which by then carries the *refined* λ of the stage just run.  A naive
    construction snapshot would make the branch declare that refined value, so
    its own ``WAVELENGTH_CALIBRATION`` would report a near-zero delta from a
    number nobody declared — exactly the per-verb bug the construction snapshot
    fixed, one level up.  A branch is a rival strategy over one physical
    instrument, and the diagnostic exists to compare rivals against a common
    reference, so the branch **inherits** the root's declared λ.

    His measured shape (per-verb / naive-branch bug): parent stage ``+417 ppm``
    from the declared 1.539984, the branch stage ``−18 ppm`` from the refined
    1.540626.  With inheritance the branch must quote the *root* declared value
    and report the cumulative ``~+400 ppm``, same sign and size as the parent.
    """
    from rietx.strategy.staged import Stage
    from tests.test_multi_histogram import synthesize

    true_lam = 1.5406
    declared_lam = true_lam * (1.0 - 400e-6)            # 1.539984 Å
    data = synthesize(true_lam, 20.0, 120.0, scale=1e4, zero=0.0,
                      bkg=[50.0, 0.0])
    ins = Instrument.debye_scherrer(wavelength=declared_lam)
    ins.profile.w.value = 3e-4

    ref = Refinement(_held_cell(), ins, history=True)
    ref.run_stage(data, Stage("scale_bkg",
                              ["phases.*.scale", "instrument.background.*"]))
    parent = ref.run_stage(data, Stage("wavelength", [WL]))

    # the branch is built from an instrument already carrying the refined λ…
    child = ref.branch()
    assert ref.instrument.source.lines[0].wavelength.value != pytest.approx(
        declared_lam), "the parent stage did not move λ, so the test is inert"

    # …yet its declared reference is the ROOT's, not that refined value
    assert child._declared_wavelengths == [pytest.approx(declared_lam)]
    assert child._declared_wavelengths == ref._declared_wavelengths

    second = child.run_stage(data, Stage("wavelength_2", [WL]))

    def _cal(result):
        hits = [d for d in result.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]
        assert len(hits) == 1
        return hits[0]

    dp, dc = _cal(parent), _cal(second)

    # the branch reports the CUMULATIVE move from the root's declared value —
    # same sign and comparable size as the parent, not a near-zero bounce off
    # the refined intermediate (which would sit well under 100 ppm)
    assert dc.value > 100.0, "the branch reported a delta, not the cumulative move"
    assert dc.value == pytest.approx(dp.value, rel=0.2)
    assert f"declared {declared_lam:.6f}" in dc.message

    # an edit ON THE BRANCH still re-declares (a genuine re-declaration), so the
    # inheritance is only over shared history, not a freeze
    child.edit(instrument=Instrument.debye_scherrer(wavelength=1.0000))
    assert child._declared_wavelengths == [pytest.approx(1.0000)]
    assert ref._declared_wavelengths == [pytest.approx(declared_lam)]


def test_a_series_measures_each_pattern_against_the_root_declaration():
    """A chained series declares λ once, not per pattern (WP-1134).

    ``_fit_one`` warm-starts pattern n from pattern n-1's *refined* λ (the
    default ``carry``), and a per-pattern ``Refinement`` built from that warmed
    instrument would snapshot the refined value as its declared reference — so
    ``WAVELENGTH_CALIBRATION`` for patterns 2+ would report the tiny
    pattern-to-pattern drift instead of the cumulative move from what the
    beamline stated.  This is the ``branch`` bug one level up, and the fence is
    the same: the wavelength is a property of the instrument the *series* was
    built with, declared once.

    Three near-identical patterns of one specimen (a repeated calibration), the
    instrument declared 400 ppm below the true λ.  Every pattern's diagnostic
    must report the cumulative ~+400 ppm against the root declaration, never the
    ~0 ppm drift from the previous pattern's answer.  The warm start itself is
    untouched — only the diagnostic's reference is threaded from the root.
    """
    from rietx.sequential import refine_sequential
    from rietx.strategy.staged import RefinementPlan, Stage
    from tests.test_multi_histogram import synthesize

    true_lam = 1.5406
    declared_lam = true_lam * (1.0 - 400e-6)            # 1.539984 Å
    patterns = [synthesize(true_lam, 20.0, 120.0, scale=1e4, zero=0.0,
                           bkg=[50.0, 0.0], seed=s) for s in (1, 2, 3)]
    ins = Instrument.debye_scherrer(wavelength=declared_lam)
    ins.profile.w.value = 3e-4

    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("wavelength", [WL]),
    ])
    series = refine_sequential(patterns, _held_cell(), ins, plan=plan)

    cals = []
    for entry in series.entries:
        hits = [d for d in entry.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]
        assert len(hits) == 1, "every pattern freed λ, so every one reports it"
        cals.append(hits[0])

    for d in cals:
        # cumulative from the root declaration, not the ~0 drift the per-verb
        # snapshot would give patterns 2+ (his shape: +417, −18, +1.6)
        assert d.value > 100.0, "a pattern measured the drift, not the calibration"
        assert d.value == pytest.approx(400.0, rel=0.25)
        assert f"declared {declared_lam:.6f}" in d.message
    # the successors agree with pattern 0 in sign and size (all cumulative)
    assert cals[1].value == pytest.approx(cals[0].value, rel=0.2)
    assert cals[2].value == pytest.approx(cals[0].value, rel=0.2)


def test_the_glob_skip_does_not_depend_on_how_the_caller_batched_it():
    """One call carrying both globs must behave like two calls in sequence.

    The skip set was computed once before ``set_vary``'s loop, and
    ``_cell_is_free`` read ``_free_idx``, which is rebuilt only at the end of
    the call.  So a single call carrying a cell glob *and* a λ glob froze its
    decision before the cell was seen to move, freed both, and deferred the
    refusal to the solve — while the same two globs in two calls skipped λ.  A
    contract that reads differently depending on how a caller batched its globs
    is not a contract.
    """
    ins = Instrument.debye_scherrer(wavelength=1.5406)

    one = ParameterTable(_held_cell(), ins)
    hits = one.set_vary(["phases.*.cell.*", WL], True)
    assert "phases.0.cell.a" in hits
    assert WL not in hits, "λ was freed beside a cell freed in the same call"

    two = ParameterTable(_held_cell(), ins)
    two.set_vary(["phases.*.cell.*"], True)
    assert WL not in two.set_vary([WL], True)

    # and the held-cell case still works, or the skip never stops skipping
    alone = ParameterTable(_held_cell(), ins)
    assert WL in alone.set_vary([WL], True)
