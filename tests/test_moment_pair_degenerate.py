"""Q5: a powder-degenerate moment pair folds into one quadrature number.

Synthetic construction (not from ``isotropy.analyse``, whose own
``determinable_amplitudes`` is measured *per site* in this codebase, see the
report's note on this test's scope): two Mn atoms **coincident** in position
(same phase for every reflection) with their moments fixed along orthogonal
crystal axes and only the modulus DOF freed on each.  The powder-averaged
magnetic intensity of a fixed vector moment depends on |M|^2 alone regardless
of its direction, so M = m1*x + m2*y gives |M|^2 = m1^2 + m2^2 exactly (an
orthogonal sum, Pythagorean) with no cross term -- the quadrature invariant
Q5's formula assumes, engineered rather than found, because a real two-site
isotropy candidate with this exact shape was not located in the time
available (flagged in the report).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.report.magnetic import _pair_degenerate_moments, moment_pair_diagnostics
from rietx.report.schemas import MOMENT_PAIR_RHO_MIN, MomentEvidence
from rietx.schemas.common import Parameter
from rietx.schemas.results import CorrelationPair
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase

LAMBDA_CW = 2.4
GRID = np.arange(8.0, 130.0, 0.05)
TRUE_M1, TRUE_M2 = 2.0, 1.5
TRUE_QUADRATURE = math.sqrt(TRUE_M1 ** 2 + TRUE_M2 ** 2)


def _cell(a, b, c):
    return Cell(a=Parameter(value=a), b=Parameter(value=b), c=Parameter(value=c),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def degenerate_pair_phase(m1: float, m2: float) -> Phase:
    """Two coincident Mn atoms, moments along orthogonal axes."""
    return Phase(
        name="pair", space_group="P 1", cell=_cell(5.0, 5.0, 5.0),
        atoms=[Atom(label="Mn1", species="Mn", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.5),
                    biso=Parameter(value=0.4),
                    moment=Moment.from_values((m1, 0.0, 0.0), "Mn3+")),
               Atom(label="Mn2", species="Mn", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.5),
                    biso=Parameter(value=0.4),
                    moment=Moment.from_values((0.0, m2, 0.0), "Mn3+")),
               Atom(label="O1", species="O", x=Parameter(value=0.5),
                    y=Parameter(value=0.5), z=Parameter(value=0.5),
                    biso=Parameter(value=0.6))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.35)


def simulate(phase, instrument, *, background=40.0, seed=20260909):
    ref = rx.Refinement(rx.Structure(phases=[phase]), instrument)
    y = np.asarray(ref.predict(GRID)) + background
    rng = np.random.default_rng(seed)
    y = y + rng.normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    # only the modulus DOFs -- the two fixed, orthogonal directions stay held
    rx.Stage("moment", ["phases.*.atoms.*.moment.dof0"])])


@pytest.fixture(scope="module")
def degenerate_pattern():
    truth = degenerate_pair_phase(TRUE_M1, TRUE_M2)
    return simulate(truth, neutron())


def _fit_from(m1_start, m2_start, data):
    structure = rx.Structure(phases=[degenerate_pair_phase(m1_start, m2_start)])
    ref = rx.Refinement(structure, neutron())
    ref.fit(data, plan=PLAN)
    return ref, ref.result_


def single_moment_phase(m: float) -> Phase:
    """The pair's two sites as one at occupancy 2: the nuclear part is the
    pair's, and the magnetic amplitude is 2m, so the powder sees exactly the
    pair's pattern at m = √(m1² + m2²)/2 and 2·σ(m) is the sum's own esd."""
    phase = degenerate_pair_phase(m, 0.0)
    phase.atoms[0].occ.value = 2.0
    del phase.atoms[1]
    return phase


@pytest.mark.slow
def test_two_starting_splits_report_the_same_quadrature_number(degenerate_pattern):
    """A 50/50-ish split and a lopsided split of the same total: both must
    converge to (near enough) the true total modulus and, more to Q5's
    point, both must report the *same* quadrature number within 1 sigma via
    the pairing mechanism, even though m1 and m2 themselves may differ
    between the two runs (the flat direction the pairing exists for).

    Since WP-2219 neither modulus has an esd (they lie on a discarded
    direction), and since WP-2230 the sum keeps one through the fit's live
    covariance, within 10 % of the esd a fit of one site carrying the
    quadrature modulus gives."""
    ref_a, result_a = _fit_from(1.75, 1.75, degenerate_pattern)
    ref_b, result_b = _fit_from(2.4, 0.3, degenerate_pattern)

    for ref, result, tag in ((ref_a, result_a, "a"), (ref_b, result_b, "b")):
        assert result.status == "converged", (tag, result.status)
        assert result.identifiability is not None, tag
        rhos = {frozenset([c.path_a, c.path_b]): c.rho
               for c in result.identifiability.top_correlations}
        pair_key = frozenset(["phases.0.atoms.0.moment.dof0",
                              "phases.0.atoms.1.moment.dof0"])
        assert pair_key in rhos, (tag, rhos)
        assert abs(rhos[pair_key]) >= MOMENT_PAIR_RHO_MIN, (tag, rhos[pair_key])

    from rietx.params.vector import ParameterTable
    from rietx.report.magnetic import analyse_moments

    def quadrature_of(ref, result):
        table = ParameterTable(ref.structure, ref.instrument)
        values = table.decode(table.x0())
        rows = analyse_moments(
            ref._model, values, ref.structure,
            esd={p.path: p.stderr for p in result.parameters
                if p.stderr is not None},
            correlations=result.identifiability.top_correlations,
            covariance=ref._answer_covariance)
        paired = [r for r in rows if r.paired_with]
        assert len(paired) == 2, rows
        return paired[0]

    row_a = quadrature_of(ref_a, result_a)
    row_b = quadrature_of(ref_b, result_b)

    assert row_a.paired_magnitude is not None and row_a.paired_magnitude_esd
    assert row_b.paired_magnitude is not None and row_b.paired_magnitude_esd
    assert row_a.paired_magnitude == pytest.approx(TRUE_QUADRATURE, abs=0.3)
    combined_sigma = math.sqrt(row_a.paired_magnitude_esd ** 2
                               + row_b.paired_magnitude_esd ** 2)
    assert abs(row_a.paired_magnitude - row_b.paired_magnitude) <= combined_sigma, (
        row_a.paired_magnitude, row_a.paired_magnitude_esd,
        row_b.paired_magnitude, row_b.paired_magnitude_esd)

    # each modulus on its own has none, as WP-2219 rules for a column
    for result in (result_a, result_b):
        rows = {p.path: p for p in result.parameters}
        for path in pair_key:
            assert rows[path].stderr is None, path
    # the report folds the pair through the same live covariance
    paired = [r for r in ref_a.report().magnetic if r.paired_with]
    assert len(paired) == 2
    assert paired[0].paired_magnitude_esd == pytest.approx(row_a.paired_magnitude_esd)

    one = rx.Refinement(rx.Structure(phases=[single_moment_phase(2.0)]), neutron())
    one.fit(degenerate_pattern, plan=PLAN)
    alone = one.result_.parameter("phases.0.atoms.0.moment.dof0")
    assert 2 * abs(alone.value) == pytest.approx(row_a.paired_magnitude,
                                                 abs=2 * alone.stderr)
    for row in (row_a, row_b):
        assert row.paired_magnitude_esd == pytest.approx(2 * alone.stderr, rel=0.1)


def test_pair_degenerate_moments_quadrature_and_esd_are_correct():
    """Direct check of the arithmetic against hand computation: with a known
    rho, sqrt(m_a^2+m_b^2) and its covariance-propagated esd match a
    from-scratch formula."""
    a = MomentEvidence(phase="p", atom="Mn1", ion="Mn3+",
                       path="phases.0.atoms.0.moment.dof0",
                       magnitude=3.0, magnitude_esd=0.2,
                       crystalaxis=[3.0, 0.0, 0.0], approximation="MHO3")
    b = MomentEvidence(phase="p", atom="Mn2", ion="Mn3+",
                       path="phases.0.atoms.1.moment.dof0",
                       magnitude=4.0, magnitude_esd=0.3,
                       crystalaxis=[0.0, 4.0, 0.0], approximation="MHO3")
    rho = 0.97
    corr = [CorrelationPair(path_a=a.path, path_b=b.path, rho=rho)]

    out = _pair_degenerate_moments([a, b], corr, {a.path: 3.0, b.path: 4.0})
    ra, rb = out
    m = math.sqrt(3.0 ** 2 + 4.0 ** 2)
    cov_ab = rho * 0.2 * 0.3
    var = ((3.0 / m) ** 2 * 0.2 ** 2 + (4.0 / m) ** 2 * 0.3 ** 2
          + 2.0 * (3.0 / m) * (4.0 / m) * cov_ab)
    esd = math.sqrt(var)

    assert ra.paired_with == [b.path]
    assert rb.paired_with == [a.path]
    assert ra.paired_magnitude == pytest.approx(m)
    assert rb.paired_magnitude == pytest.approx(m)
    assert ra.paired_magnitude_esd == pytest.approx(esd)
    assert rb.paired_magnitude_esd == pytest.approx(esd)
    assert "not separately determined" in ra.note
    assert "MOMENT_PAIR_DEGENERATE" in ra.note

    diags = moment_pair_diagnostics(out)
    assert len(diags) == 1
    assert diags[0].code == "MOMENT_PAIR_DEGENERATE"
    assert diags[0].value == pytest.approx(m)
    assert set(diags[0].where) == {a.path, b.path}


@pytest.mark.parametrize("d_b, rho", [(2.0, -0.999), (-2.0, 0.999)])
def test_the_paired_esd_uses_the_signed_moduli(d_b, rho):
    """gᵀCg at g = d/m, signs included — the antiparallel case is the one that bites.

    Review of #433, finding 4.  Two sites stated **antiparallel**
    (d_a = +2, d_b = −2) have their powder-degenerate direction along (1, 1),
    so ρ of the signed columns → +1 and the cross term −σ² cancels the
    diagonal: the quadrature sum is well determined.  Built from |dof0| the
    cross term flipped sign and the esd came out √2·σ = 0.1414 against a
    linearised truth of 0.0032.  The parallel case (ρ → −1) agreed either
    way, which is why the arithmetic test above never saw it.
    """
    sigma = 0.1
    a = MomentEvidence(phase="p", atom="Mn1", ion="Mn3+", path="a.dof0",
                       magnitude=2.0, magnitude_esd=sigma,
                       crystalaxis=[2.0, 0.0, 0.0], approximation="MHO3")
    b = MomentEvidence(phase="p", atom="Mn2", ion="Mn3+", path="b.dof0",
                       magnitude=abs(d_b), magnitude_esd=sigma,
                       crystalaxis=[0.0, abs(d_b), 0.0], approximation="MHO3")
    corr = [CorrelationPair(path_a="a.dof0", path_b="b.dof0", rho=rho)]
    out = _pair_degenerate_moments([a, b], corr, {"a.dof0": 2.0, "b.dof0": d_b})

    d = np.array([2.0, d_b])
    m = float(np.hypot(*d))
    g = d / m
    cov = sigma ** 2 * np.array([[1.0, rho], [rho, 1.0]])
    truth = math.sqrt(float(g @ cov @ g))
    assert out[0].paired_magnitude == pytest.approx(m)
    assert out[0].paired_magnitude_esd == pytest.approx(truth, rel=1e-12)
    assert out[0].paired_magnitude_esd < 0.01


def test_below_the_rho_bar_nothing_is_paired():
    a = MomentEvidence(phase="p", atom="Mn1", ion="Mn3+", path="a.dof0",
                       magnitude=3.0, magnitude_esd=0.2,
                       crystalaxis=[3.0, 0.0, 0.0], approximation="MHO3")
    b = MomentEvidence(phase="p", atom="Mn2", ion="Mn3+", path="b.dof0",
                       magnitude=4.0, magnitude_esd=0.3,
                       crystalaxis=[0.0, 4.0, 0.0], approximation="MHO3")
    corr = [CorrelationPair(path_a="a.dof0", path_b="b.dof0", rho=0.5)]
    out = _pair_degenerate_moments([a, b], corr, {"a.dof0": 3.0, "b.dof0": 4.0})
    assert out[0].paired_with == [] and out[1].paired_with == []
    assert not moment_pair_diagnostics(out)


def test_no_correlations_leaves_rows_unpaired():
    from rietx.report.magnetic import analyse_moments
    # analyse_moments itself, with correlations=None (the default) and no
    # compiled model, must not call the pairing step at all -- the honest
    # empty-for-cause state, unaffected by Q5
    assert analyse_moments(None, {}) == []
