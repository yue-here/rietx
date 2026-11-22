"""Issue #1692: a mixed-occupancy position is judged by its moment per position.

Ruled by Mike on #1692: where magnetic atoms share one position the powder
measures only Σ occ_j·f_j·m_j there, so the null test (the same floor, the
same ``MOMENT_SUPPORT_SIGMA``) reads that combination, with its esd from the
fit's own covariance, and each atom's modulus is reported as not separately
determined.  Form factors are taken at Q → 0, so the combination is the linear
sum Σ occ·m — never the quadrature sum a powder-degenerate pair of *distinct*
sites is read by.

Synthetic, typed here: two atoms on one general position of a cubic P 1 cell,
moments stated along one crystal axis, only the moduli freed.  Two fixtures
answer two questions.  Fe³⁺/Cr³⁺ (unequal form factors) is the real-data
shape: each modulus rides a near-flat valley and fails the ratio on its own
while the position's moment is tens of esds clear.  Mn³⁺/Mn³⁺ (equal form
factors) is exactly degenerate, so the pseudo-inverse drops the valley and the
per-site esd comes out *small*: at a true moment of zero each modulus then
passes the ratio on its own, the negative arm the per-site test fails.

Each fit arm pins a decision on one seeded pattern, and each assertion is
chosen so that it goes red under one of the two mistakes the ruling rejects:
the per-site test returning, or the quadrature sum replacing the linear one.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.moments import _coefficients
from rietx.crystallography.magnetic.scattering import cosited_groups
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.magnetic import (
    _coefficient_jacobian,
    analyse_moments,
    cosited_moments,
    moment_unsupported_diagnostics,
)
from rietx.report.schemas import MOMENT_SUPPORT_SIGMA
from rietx.schemas.common import Parameter
from rietx.schemas.results import CorrelationPair
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase
from rietx.strategy.magnetic import MagneticTrial, _moment_rows, _rank

LAMBDA_CW = 2.4
GRID = np.arange(8.0, 130.0, 0.05)
SEED = 20261120
PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    # only the moduli: the stated direction is held on both atoms
    rx.Stage("moment", ["phases.*.atoms.*.moment.dof0"])])
PAIR = ("phases.0.atoms.0.moment.dof0", "phases.0.atoms.1.moment.dof0")


def _cell():
    return Cell(a=Parameter(value=5.0), b=Parameter(value=5.0), c=Parameter(value=5.0),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))


def _atom(label, species, xyz, *, ion=None, moment=(0.0, 0.0, 0.0), occ=1.0):
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=0.4), occ=Parameter(value=occ),
                moment=None if ion is None else Moment.from_values(moment, ion))


def mixed(m1, m2, ions=("Fe3+", "Cr3+"), *, occ=(0.5, 0.5),
          second=(0.0, 0.0, 0.5), directions=((1, 0, 0), (1, 0, 0))) -> Phase:
    """Two magnetic ions on one position (or at ``second``), and an oxygen."""
    sp = [i.rstrip("0123456789+-") for i in ions]
    return Phase(
        name="mixed", space_group="P 1", cell=_cell(),
        atoms=[_atom(f"{sp[0]}1", sp[0], (0.0, 0.0, 0.5), ion=ions[0], occ=occ[0],
                     moment=tuple(m1 * np.asarray(directions[0], float))),
               _atom(f"{sp[1]}2", sp[1], second, ion=ions[1], occ=occ[1],
                     moment=tuple(m2 * np.asarray(directions[1], float))),
               _atom("O1", "O", (0.5, 0.5, 0.5))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))


def neutron():
    return rx.Instrument.constant_wavelength_neutron(LAMBDA_CW, fwhm_deg=0.35)


def simulate(phase):
    ref = rx.Refinement(rx.Structure(phases=[phase]), neutron())
    y = np.asarray(ref.predict(GRID)) + 40.0
    y = y + np.random.default_rng(SEED).normal(scale=np.sqrt(np.maximum(y, 1.0)))
    return rx.PatternData(two_theta=GRID.tolist(), intensity=y.tolist())


def fit(truth: Phase, start: Phase):
    ref = rx.Refinement(rx.Structure(phases=[start]), neutron())
    ref.fit(simulate(truth), plan=PLAN)
    assert ref.result_.status == "converged"
    return ref


class _Paths:
    """Every path is a row, in the order asked."""

    def __init__(self, paths=None):
        self.paths = paths

    def __contains__(self, q):
        return self.paths is None or q in self.paths

    def __getitem__(self, q):
        return q


class _Table:
    """The three members of ``ParameterTable`` the moment arm reads, over an
    arbitrary covariance ``block(paths)`` (the answer tuple's shape, WP-2230)."""

    free_paths = ()

    def __init__(self, block, paths=None):
        self._block = block
        self._paths = _Paths(paths)

    def unmeasured_functions(self, *args, **kw):
        return [False]

    def physical_covariance(self, theta, stderr, correlation, paths, **kw):
        return self._block(paths)


def answer_tuple(block, paths=None):
    """``Refinement._answer_covariance``'s tuple around an arbitrary block."""
    return (None, _Table(block, paths), None, np.ones(1), None)


def compiled(phase: Phase):
    structure = rx.Structure(phases=[phase])
    grid = rx.PatternData(two_theta=GRID.tolist(), intensity=[0.0] * len(GRID))
    model = compile_model(structure, neutron(), grid)
    table = ParameterTable(structure, neutron())
    return model, table.decode(table.x0())


def per_site_ratio(row) -> float:
    return abs(row.magnitude) / row.magnitude_esd


# ===================================================== recognition, at compile

def test_two_moments_on_one_position_are_one_group():
    model, _ = compiled(mixed(2.0, 1.0))
    assert model.phases[0].magnetic.cosited == ((0, 1),)


def test_a_lattice_translation_is_the_same_position():
    model, _ = compiled(mixed(2.0, 1.0, second=(1.0, 0.0, -0.5 + 1.0)))
    assert model.phases[0].magnetic.cosited == ((0, 1),)


def test_distinct_positions_are_never_grouped():
    model, _ = compiled(mixed(2.0, 1.0, second=(0.0, 0.0, 0.25)))
    assert model.phases[0].magnetic.cosited == ()


def test_a_nonmagnetic_atom_on_the_position_joins_no_group():
    """The oxygen is moved onto the shared position: it carries no moment, so
    the group is still the two magnetic atoms and nothing else."""
    phase = mixed(2.0, 1.0)
    phase.atoms[2].x.value, phase.atoms[2].y.value, phase.atoms[2].z.value = 0.0, 0.0, 0.5
    model, _ = compiled(phase)
    assert model.phases[0].magnetic.cosited == ((0, 1),)


def test_grouping_refuses_images_that_do_not_coincide():
    """Same coordinates, different axial matrices: no combination is formed."""
    pos = [np.zeros(3), np.zeros(3)]
    rot = np.eye(3)[None]
    ops = [(rot, np.zeros((1, 3))), (rot, np.zeros((1, 3)))]
    frames = [np.eye(3), np.eye(3)]
    assert cosited_groups(pos, [rot, rot], frames, ops) == ((0, 1),)
    assert cosited_groups(pos, [rot, -rot], frames, ops) == ()


# ================================================= the combination, by hand

@pytest.mark.parametrize("n", [1, 2, 3])
def test_the_coefficient_jacobian_is_the_derivative(n):
    rng = np.random.default_rng(n)
    d = np.concatenate([[2.3], rng.uniform(0.2, 2.8, n - 1)])
    h = 1e-6
    fd = np.column_stack([(_coefficients(d + h * e) - _coefficients(d - h * e)) / (2 * h)
                          for e in np.eye(n)])
    assert np.allclose(_coefficient_jacobian(d), fd, atol=1e-8)


@pytest.mark.parametrize("m1, m2", [(3.0, 2.0), (2.0, -1.0), (1.0, 1.0)])
def test_the_moment_per_position_is_the_linear_sum_with_its_propagated_esd(m1, m2):
    """|Σ occ·m| against the stated crystal-axis moments in a cubic cell, and
    gᵀCg against a gradient taken by finite differences over every modulus,
    angle and occupancy of the group, for an arbitrary covariance."""
    occ = (0.6, 0.4)
    model, values = compiled(mixed(m1, m2, occ=occ,
                                   directions=((1, 0, 0), (0.6, 0.8, 0))))
    truth = np.linalg.norm(occ[0] * m1 * np.array([1, 0, 0])
                           + occ[1] * m2 * np.array([0.6, 0.8, 0]))
    paths = [f"phases.0.atoms.{j}.{q}" for j in (0, 1)
             for q in ("moment.dof0", "moment.dof1", "moment.dof2", "occ")]
    rng = np.random.default_rng(7)
    a = rng.normal(size=(len(paths), len(paths)))
    cov = a @ a.T * 1e-3

    def magnitude(vals):
        (c,) = cosited_moments(model, vals, {})
        return c.magnitude

    h = 1e-6
    g = []
    for p in paths:
        up, dn = dict(values), dict(values)
        up[p] += h
        dn[p] -= h
        g.append((magnitude(up) - magnitude(dn)) / (2 * h))
    g = np.asarray(g)

    def block(asked):
        idx = [paths.index(p) for p in asked]
        return cov[np.ix_(idx, idx)]

    (c,) = cosited_moments(model, values, {p: 1.0 for p in PAIR},
                           answer_tuple(block, paths))
    assert c.paths == PAIR
    assert c.magnitude == pytest.approx(truth, rel=1e-12)
    assert c.esd == pytest.approx(math.sqrt(g @ cov @ g), rel=1e-6)


def test_no_covariance_means_no_esd_and_no_verdict():
    model, values = compiled(mixed(3.0, 2.0))
    (c,) = cosited_moments(model, values, {p: 0.1 for p in PAIR}, None)
    assert c.magnitude == pytest.approx(2.5)
    assert c.esd is None and c.supported is None


def test_a_modulus_without_an_esd_leaves_the_position_untested():
    """A held modulus has no esd of its own: the combination over it is not
    tested, never certified."""
    model, values = compiled(mixed(3.0, 2.0))
    (c,) = cosited_moments(model, values, {PAIR[0]: 0.1},
                           answer_tuple(lambda paths: np.eye(len(paths)) * 1e-4))
    assert c.esd is None and c.supported is None


# ============================================== the fit arms (seeded, pinned)

@pytest.fixture(scope="module")
def weak_fe_cr():
    """Fe³⁺ 1.2 and Cr³⁺ 0.8 μ_B at half occupancy each, collinear: 1.0 μ_B a position."""
    return fit(mixed(1.2, 0.8), mixed(2.0, 1.0))


@pytest.fixture(scope="module")
def cancelling_fe_cr():
    """Fe³⁺ +2 and Cr³⁺ −1 μ_B: 0.5 μ_B a position, √(1² + 0.5²) = 1.118 in quadrature."""
    return fit(mixed(2.0, -1.0), mixed(2.0, 1.0))


@pytest.fixture(scope="module")
def null_mn_mn():
    """Two Mn³⁺ on one position, no moment on either: the negative arm."""
    ions = ("Mn3+", "Mn3+")
    return fit(mixed(0.0, 0.0, ions), mixed(2.0, 1.0, ions))


@pytest.fixture(scope="module")
def null_fe_cr():
    return fit(mixed(0.0, 0.0), mixed(2.0, 1.0))


def _rows(ref):
    return {r.path: r for r in ref.report().magnetic}


def _trial(ref):
    rows, n_moment, _ = _moment_rows(ref, ref.result_, ref.structure)
    return MagneticTrial(
        class_index=0, representative="S0(a)", members=("1.1 S0(a)",),
        site="Fe1", irrep="S0", direction="(a)", bns_number="1.1",
        uni_number=None, msg_type=1, free_amplitudes=n_moment,
        determinable_amplitudes=1, status="refined", rwp=0.1, gof=1.0,
        delta_bic=500.0, r_magnetic=0.1, n_moment_parameters=n_moment,
        n_free_parameters=n_moment + 5, moments=rows)


def test_a_position_whose_atoms_each_fail_is_supported_by_its_moment(weak_fe_cr):
    """The real-data shape (the six MAGNDATA labels of #1692): each modulus
    under ``MOMENT_SUPPORT_SIGMA`` of its own esd, the position's moment many
    esds clear.  Red if the per-site test returns."""
    rows = _rows(weak_fe_cr)
    for p in PAIR:
        assert per_site_ratio(rows[p]) < MOMENT_SUPPORT_SIGMA, rows[p]
        assert rows[p].supported is True
        assert rows[p].cosited_with == [q for q in PAIR if q != p]
        assert "not separately determined" in rows[p].note
        assert rows[p].cosited_magnitude / rows[p].cosited_magnitude_esd > 10
    trial = _trial(weak_fe_cr)
    assert trial.supported
    _o, _t, verdict, _r = _rank([trial], 6.0)
    assert verdict != "nothing to solve"
    assert not [d for d in weak_fe_cr.result_.diagnostics
                if d.code == "MOMENT_UNSUPPORTED"]


def test_the_position_is_read_by_the_linear_sum_never_the_quadrature_sum(
        weak_fe_cr, cancelling_fe_cr):
    """Σ occ·m against the truth, with the two quadrature readings far outside
    its esd — red if either replaced the linear sum."""
    for ref, linear, moduli in ((weak_fe_cr, 1.0, (1.2, 0.8)),
                                (cancelling_fe_cr, 0.5, (2.0, -1.0))):
        row = _rows(ref)[PAIR[0]]
        m, esd = row.cosited_magnitude, row.cosited_magnitude_esd
        assert m == pytest.approx(linear, abs=4 * esd), (m, esd)
        weighted = math.hypot(0.5 * moduli[0], 0.5 * moduli[1])
        bare = math.hypot(*moduli)
        assert abs(m - weighted) > 4 * esd and abs(m - bare) > 4 * esd
        # and its moduli correlate, but no quadrature pair is formed with them
        assert row.paired_with == [] and row.paired_magnitude is None


def test_a_position_with_no_moment_fails_though_each_atom_passes(null_mn_mn):
    """The negative arm.  Equal form factors make the pair exactly degenerate,
    the pseudo-inverse drops the flat direction, and each modulus comes back
    *above* ``MOMENT_SUPPORT_SIGMA`` of its own esd on a pattern with no
    magnetic intensity: the per-site test would call it supported.  The
    position's moment is what fails."""
    rows = _rows(null_mn_mn)
    assert all(per_site_ratio(rows[p]) > MOMENT_SUPPORT_SIGMA for p in PAIR)
    assert all(rows[p].supported is False for p in PAIR)
    assert not _trial(null_mn_mn).supported
    _o, _t, verdict, reason = _rank([_trial(null_mn_mn)], 6.0)
    assert verdict == "nothing to solve"
    assert "mixed-occupancy position's moment" in reason
    (d,) = [d for d in null_mn_mn.result_.diagnostics if d.code == "MOMENT_UNSUPPORTED"]
    assert set(d.where) == set(PAIR)
    assert "share one position" in d.message


def test_a_position_with_no_moment_fails_with_unequal_form_factors(null_fe_cr):
    rows = _rows(null_fe_cr)
    assert all(rows[p].supported is False for p in PAIR)
    assert not _trial(null_fe_cr).supported


def test_the_series_reads_the_position_verdict(null_mn_mn, weak_fe_cr):
    """The sequential hold (and every trajectory) reads ``supported`` off the
    same arm, so a series floors an unsupported position and keeps a
    supported one whose atoms each fail."""
    from rietx.sequential import _moment_evidence

    for ref, verdict in ((null_mn_mn, False), (weak_fe_cr, True)):
        rows = {r.path: r for r in _moment_evidence(ref, ref.result_)}
        assert all(rows[p].supported is verdict for p in PAIR)


# ============================================== the arithmetic of the verdict

def test_the_diagnostic_names_the_group_and_its_numbers():
    from rietx.report.magnetic import CositedMoment

    bad = CositedMoment(PAIR, 0.09, 0.13)
    good = CositedMoment(("a.dof0", "b.dof0"), 2.5, 0.01)
    (d,) = moment_unsupported_diagnostics([], [bad, good])
    assert d.where == list(PAIR)
    assert d.value == pytest.approx(0.09 / 0.13)
    assert "0.09 ± 0.13" in d.message and "this moment" in d.message
    assert moment_unsupported_diagnostics([], [good]) == []


def test_a_cosited_pair_is_not_quadrature_paired_even_at_rho_one():
    model, values = compiled(mixed(3.0, 2.0))
    corr = [CorrelationPair(path_a=PAIR[0], path_b=PAIR[1], rho=-0.999)]
    rows = analyse_moments(model, values, esd={p: 0.4 for p in PAIR},
                           correlations=corr,
                           covariance=answer_tuple(lambda paths: np.eye(len(paths)) * 1e-4))
    assert all(r.paired_with == [] for r in rows)
    assert all(r.cosited_magnitude == pytest.approx(2.5) for r in rows)
