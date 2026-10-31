"""WP-1327: the analytic moment Jacobian, held to exact oracles.

Everything here is **synthetic** — one or two Mn sites on a small
orthorhombic or tetragonal cell, neutron CW, patterns from rietx's own
forward model — so nothing about a real specimen is asserted.

**What is new.**  ``_make_jacobian`` used to send every ``…moment.dof<k>``
column to the peak-chain finite difference, which re-runs ``phase_peaks`` at
a perturbed θ.  ``_moment_column`` now builds a **modulus** column from
``scattering.d_magnetic_f2_d_dofs`` (∂|F_⊥|² = 2·Re[(P·F)ᴴ·∂F], with ∂F the
forward orbit sum of one atom at ∂m/∂d) chained through the same intensity
factors as the coordinate columns.  The derivation is in the WP-1327
PR #1206's description (and, once written, the WP-1327 handover).

**Angles are built and checked here, and not dispatched.**  The derivative
covers them (the same function returns their rows), and every test below
holds the angle columns ``_moment_column`` builds to the same oracle.  The
dispatch declines them by name (``_moment_reach_ok``'s docstring), because
an exact angle column is zero at a symmetry-fixed seed and a solver cannot
leave it where it is a maximum, which the forward difference escaped only by
its truncation; ``test_an_exact_angle_column_cannot_leave_a_symmetric_seed``
pins that measured reason, so the decline cannot outlive it unnoticed.

**Why the oracle is exact, not a forward difference.**  F is linear in every
moment, the moment is linear in the modulus and in (cos α, sin α) for each
angle α, and with extinction off y is linear in |F_⊥|².  So a residual
column is a quadratic in a modulus — whose *central* difference is exact at
any step — and a trigonometric polynomial of degree two in an angle, whose
central difference at step h is Σ_ν a_ν·sin(νh)/(νh), ν = 1, 2: two steps
solve for both harmonics exactly.  An FD comparison only bounds the
truncation it shares (root CLAUDE.md, the branch-oracle rule; WP-1121), so
the bars below sit at roundoff, measured, with the measured value beside
each.

**Positive arms.**  A doubled ∂m/∂μ, a sign-flipped ∂m/∂angle and a
projection taken along the wrong axis must each fail the oracle bar, and the
replaced peak-chain column must too — a bar that cannot fail would certify
anything.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import WINDOW_AREA_TOL, compile_model
from rietx.optimize import least_squares as lsq
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import VAR_PREFIX, AffineTie, ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase
from tests.test_cross_backend import _central_fd_jacobian

LAMBDA = 2.4
PLANE = ("x,y,z,+1", "x,y,-z,-1")      # {1, m_z'}: the moment lies in ab, n = 2
ANY = ("x,y,z,+1",)                     # {1}: any direction, n = 3

#: the exact-oracle bar on a moment column, relative L2.  Measured
#: 2026-10-28 (darwin/arm64, [dev,jax]) at 2.6e-14 worst over the eleven
#: moment columns of the five exact states (roundoff of a residual
#: differenced at h = 0.05 and 0.1); ~10× margin.  The planted errors below
#: land at ≥ 7e-2, eleven decades above it.
ORACLE_BAR = 3e-13
#: the bar against the package's own central differences (the cross-backend
#: matrix's ``fd`` opinion, O(h²) truncation) on an **analytic** column.
#: Measured worst 1.4e-9 (an angle of ``extinction_live``); ~10× margin.
CENTRAL_FD_BAR = 2e-8


def _atom(label, species, xyz, biso, moment=None):
    return Atom(label=label, species=species, x=P(value=xyz[0]),
                y=P(value=xyz[1]), z=P(value=xyz[2]), occ=P(value=1.0),
                biso=P(value=biso, unit="A^2"), moment=moment)


def _ortho(moments, operations, *, extinction=0.0) -> Phase:
    """Pmmm with Mn on the origin and, given two moments, on (½, 0, 0).

    Both sites have site symmetry mmm, so one image each; the declared
    magnetic group decides the allowed subspace (``PLANE``: ab, ``ANY``: all).
    """
    sites = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0)]
    atoms = [_atom(f"Mn{i + 1}", "Mn", sites[i], 0.3,
                   Moment.from_values(m, "Mn2+", vary=True))
             for i, m in enumerate(moments)]
    atoms.append(_atom("O", "O", (0.5, 0.5, 0.5), 0.4))
    phase = Phase(name="ortho", space_group="P m m m",
                  cell=Cell(a=P(value=4.0), b=P(value=4.4), c=P(value=5.0),
                            alpha=P(value=90.0), beta=P(value=90.0),
                            gamma=P(value=90.0)),
                  scale=P(value=0.05, min=0.0),
                  atoms=atoms,
                  magnetic_symmetry=MagneticSymmetry(operations=list(operations)))
    if extinction:
        phase.extinction.value = extinction
    return phase


def _mnf2_width(*, extinction=0.0) -> Phase:
    """MnF₂ with both magnetic widths on: the split draw (WP-1343)."""
    from tests.test_magnetic_width import _mnf2

    phase = _mnf2(size=0.20, strain=0.08)
    phase.scale.value = 0.05
    if extinction:
        phase.extinction.value = extinction
    return phase


def _build(phase, free, *, ties=(), variables=()):
    structure = rx.Structure(phases=[phase])
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.profile.x.value = 0.04
    ins.background = BackgroundChebyshev.with_terms(2)
    ins.background.coefficients[0].value = 20.0
    grid = np.arange(8.0, 140.0, 0.05)
    empty = rx.PatternData(two_theta=grid.tolist(),
                           intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, ins, empty, mode="rietveld",
                        window_area_tol=WINDOW_AREA_TOL)
    sim_table = ParameterTable(structure, ins)
    y = np.asarray(sim.evaluate(sim_table.decode(sim_table.x0())))
    # off the expansion point, so the residual is not zero and no column is
    # dead by construction
    pattern = rx.PatternData(two_theta=sim.tt.tolist(),
                             intensity=(y * 1.03 + 2.0).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for name, value in variables:
        table.add_parameter(f"{VAR_PREFIX}{name}", value, vary=True)
    for path, tie in ties:
        table.set_tie(path, tie)
    table.refresh_ties()
    for path in free:
        assert table.set_vary([path], True), path
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths),
                          window_area_tol=WINDOW_AREA_TOL)
    return model, table


M0 = "phases.0.atoms.0.moment"
M1 = "phases.0.atoms.1.moment"


def _state(name):
    """The configurations, one per parameterisation and per reach shape."""
    if name == "n1_mnf2":
        from tests.test_magnetic import _mnf2

        phase = _mnf2(biso=0.4)
        phase.scale.value = 0.05
        return _build(phase, [f"{M0}.dof0", "phases.0.scale",
                              "instrument.background.c0"])
    if name == "n2_plane":
        return _build(_ortho([(2.0, 1.0, 0.0)], PLANE),
                      [f"{M0}.dof0", f"{M0}.dof1", "phases.0.scale"])
    if name == "n3_any":
        return _build(_ortho([(2.0, 1.0, 0.7)], ANY),
                      [f"{M0}.dof0", f"{M0}.dof1", f"{M0}.dof2",
                       "phases.0.cell.a"])
    if name == "two_sites_tied":
        # site 1's modulus follows site 0's (−0.8, + 0.3) **and** a named
        # variable MU (0.5), so a variable drives a modulus beside the own
        # column that reaches it; a second variable drives both azimuths at 1
        return _build(_ortho([(2.0, 1.0, 0.0), (-1.0, 1.5, 0.0)], PLANE),
                      [f"{M0}.dof0"],
                      ties=[(f"{M1}.dof0",
                             AffineTie(terms=((f"{M0}.dof0", -0.8),
                                              (f"{VAR_PREFIX}MU", 0.5)),
                                       const=0.3)),
                            (f"{M0}.dof1", AffineTie.identity(f"{VAR_PREFIX}PHI")),
                            (f"{M1}.dof1", AffineTie.identity(f"{VAR_PREFIX}PHI"))],
                      variables=[("PHI", 0.7), ("MU", 0.4)])
    if name == "extinction_live":
        return _build(_ortho([(2.0, 1.0, 0.7)], ANY, extinction=0.8),
                      [f"{M0}.dof0", f"{M0}.dof1", f"{M0}.dof2",
                       "phases.0.extinction"])
    if name == "split":
        return _build(_mnf2_width(), [f"{M0}.dof0", "phases.0.magnetic_lor_size",
                                      "phases.0.scale"])
    if name == "split_extinction_live":
        return _build(_mnf2_width(extinction=0.8),
                      [f"{M0}.dof0", "phases.0.extinction", "phases.0.scale"])
    raise KeyError(name)


#: states where y is linear in |F_⊥|², so the oracle below is exact
EXACT_STATES = ["n1_mnf2", "n2_plane", "n3_any", "two_sites_tied", "split"]
ALL_STATES = [*EXACT_STATES, "extinction_live", "split_extinction_live"]


def _moment_columns(table):
    """The free columns that move moment DOFs: ``(index, kind, reach)``, kind
    ``"modulus"`` or ``"angle"`` — read off what the column reaches."""
    out = []
    extras = lsq._column_extras(table)
    for c, path in enumerate(table.free_paths):
        doms = [q for q in [path, *extras[c]] if lsq._MOMENT_PATH.match(q)]
        if not doms:
            continue
        kind = "modulus" if all(q.endswith(".dof0") for q in doms) else "angle"
        out.append((c, kind, doms))
    return out


def _built_column(model, table, theta, c, reach):
    """The residual column ``_moment_column`` builds, bypassing the dispatch —
    how the angle columns, which the dispatch declines, are held to the
    oracle.  Zero below the data rows, which a moment cannot reach."""
    values = table.decode(theta)
    bases = model.derivative_bases(values, None, axial_derivs=False,
                                   profile_derivs=False)
    col = np.zeros(len(_make_residual(model, table)(theta)))
    col[:len(model.tt)] = -(1.0 / model.sigma) * lsq._moment_column(
        model, table, bases, values, c, 0, reach,
        model.moment_f2_grads(0, values))
    return col


def _sinc(x):
    return np.sin(x) / x


def _oracle_column(residual, theta, c, kind, h=0.05):
    """The exact derivative of the residual along θ_c (module docstring)."""
    def central(step):
        tp, tm = theta.copy(), theta.copy()
        tp[c] += step
        tm[c] -= step
        return (residual(tp) - residual(tm)) / (2.0 * step)

    if kind == "modulus":
        return central(h)
    d1, d2 = central(h), central(2.0 * h)
    # D(h) = a·sinc(h) + b·sinc(2h);  D(2h) = a·sinc(2h) + b·sinc(4h)
    m = np.array([[_sinc(h), _sinc(2 * h)], [_sinc(2 * h), _sinc(4 * h)]])
    a, b = np.linalg.solve(m, np.vstack([d1, d2]))
    return a + b


def _rel(a, b):
    return float(np.linalg.norm(a - b) / max(np.linalg.norm(a), np.linalg.norm(b)))


_CACHE: dict[str, tuple] = {}


def _cached(name):
    if name not in _CACHE:
        _CACHE[name] = _state(name)
    return _CACHE[name]


def _oracle_errors(name):
    """``(path, kind, error)`` of every built moment column against the oracle."""
    model, table = _cached(name)
    theta = table.x0()
    residual = _make_residual(model, table)
    return [(table.free_paths[c], kind,
             _rel(_oracle_column(residual, theta, c, kind),
                  _built_column(model, table, theta, c, reach)))
            for c, kind, reach in _moment_columns(table)]


# ======================================================== the branch is taken

@pytest.mark.parametrize("name", ALL_STATES)
def test_the_dispatch_takes_the_branch_exactly_where_it_claims(name):
    """Which columns the analytic branch claims, asserted — not inferred
    from agreement, which a peak-chain column would also give: every
    modulus column of a supported phase, no angle, nothing on a split draw
    with live extinction.  And a claimed column *is* the built one."""
    model, table = _cached(name)
    supported = model.moment_grad_supported(0)
    assert supported is (name != "split_extinction_live")
    if name.startswith("split"):
        assert model.mag_split(0)
    taken = []
    real = lsq._moment_column

    def spy(*args, **kwargs):
        taken.append(args[4])
        return real(*args, **kwargs)

    lsq._moment_column = spy
    try:
        J = _make_jacobian(model, table)(table.x0())
    finally:
        lsq._moment_column = real
    cols = _moment_columns(table)
    want = [c for c, kind, _ in cols if kind == "modulus"] if supported else []
    assert sorted(taken) == want, (taken, want)
    for c, _kind, reach in cols:
        if c in want:
            np.testing.assert_array_equal(
                J[:, c], _built_column(model, table, table.x0(), c, reach))


# ======================================================== the exact oracle

@pytest.mark.parametrize("name", EXACT_STATES)
def test_every_moment_column_meets_the_exact_oracle(name):
    errs = _oracle_errors(name)
    assert errs, "no moment column in the state — the test would prove nothing"
    print(f"{name}: " + ", ".join(f"{p.rsplit('.', 1)[-1]} {e:.1e}" for p, _, e in errs))
    for path, kind, err in errs:
        assert err < ORACLE_BAR, (path, kind, err)


def test_the_replaced_peak_chain_column_fails_the_same_oracle():
    """The point of the branch, measured, and the oracle's positive arm: the
    forward-difference peak-chain column carries O(h) truncation the oracle
    sees, measured 5.0e-7 (modulus) and 7.5e-7 (azimuth)."""
    model, table = _cached("n2_plane")
    theta = table.x0()
    residual = _make_residual(model, table)
    model.moment_grad_supported = lambda ip: False      # the pre-branch dispatch
    try:
        old = _make_jacobian(model, table)(theta)
    finally:
        del model.moment_grad_supported
    for c, kind, reach in _moment_columns(table):
        truth = _oracle_column(residual, theta, c, kind)
        e_new = _rel(truth, _built_column(model, table, theta, c, reach))
        e_old = _rel(truth, old[:, c])
        print(f"{table.free_paths[c]}: built {e_new:.1e}, peak chain {e_old:.1e}")
        assert e_new < ORACLE_BAR
        assert e_old > 1e3 * ORACLE_BAR


@pytest.mark.parametrize("name", ALL_STATES)
def test_every_built_column_meets_central_differences(name):
    """Against the cross-backend matrix's ``fd`` opinion — the check on the
    two extinction states, where the oracle is not exact.  On the split
    draw with live extinction the dispatch declines the branch, and the
    built column is still right: the declined case is a cross-component
    extinction term nobody needs, not an error."""
    model, table = _cached(name)
    theta = table.x0()
    fd = _central_fd_jacobian(name, model, table)(theta)
    if name == "split_extinction_live":
        pytest.skip("the built column omits the cross-component extinction "
                    "term on purpose; the dispatch declines this state")
    for c, kind, reach in _moment_columns(table):
        err = _rel(fd[:, c], _built_column(model, table, theta, c, reach))
        assert err < CENTRAL_FD_BAR, (table.free_paths[c], kind, err)


# ======================================================== positive arms

def _planted(kind):
    """A deliberately wrong ``d_moment_d_dofs``, by name."""
    from rietx.crystallography.magnetic import moments as mom

    real_dm = mom.d_moment_d_dofs

    def bad(frame, dofs):
        out = real_dm(frame, dofs).copy()
        if kind == "modulus_factor":
            out[0] *= 2.0
        else:
            out[1:] *= -1.0
        return out
    return mom, "d_moment_d_dofs", bad


@pytest.mark.parametrize("kind,name", [("modulus_factor", "n2_plane"),
                                       ("angle_sign", "n2_plane"),
                                       ("angle_sign", "n3_any"),
                                       ("modulus_factor", "two_sites_tied")])
def test_a_planted_error_fails_the_oracle(kind, name, monkeypatch):
    module, attr, bad = _planted(kind)
    monkeypatch.setattr(module, attr, bad)
    hit = [(p, e) for p, k, e in _oracle_errors(name)
           if (k == "modulus") == (kind == "modulus_factor")]
    assert hit
    for path, err in hit:
        print(f"planted {kind} on {path}: rel-L2 {err:.2e}")
        assert err > 1e3 * ORACLE_BAR, (path, err)


def test_a_wrong_projection_fails_the_oracle(monkeypatch):
    """The perpendicular projection is the step easiest to get subtly wrong
    (it is the only place Q enters the derivative).  Project along the Q̂ of a
    cell with its axes permuted — a plausible frame mix-up — in the
    derivative alone, leaving the forward model the oracle differentiates
    untouched, and the oracle must see it."""
    from rietx.crystallography.magnetic import scattering as sc

    real = sc.d_magnetic_f2_d_dofs
    orig = sc.reciprocal_cartesian_basis

    def misprojected(*args):
        sc.reciprocal_cartesian_basis = (
            lambda cell: orig((cell[1], cell[2], cell[0], *cell[3:])))
        try:
            return real(*args)
        finally:
            sc.reciprocal_cartesian_basis = orig

    monkeypatch.setattr("rietx.model.forward.d_magnetic_f2_d_dofs", misprojected)
    errs = [e for _p, _k, e in _oracle_errors("n3_any")]
    print("wrong projection:", [f"{e:.2e}" for e in errs])
    assert max(errs) > 1e3 * ORACLE_BAR, errs


# ======================================================== why angles decline

def test_an_exact_angle_column_cannot_leave_a_symmetric_seed():
    """The measured reason ``_moment_reach_ok`` declines an angle.

    ``test_magnetic_moment_frame``'s fixture (P 1 2/m 1, n = 3, the moment
    seeded at its truth (2.5, 0, 2.5), so the azimuth starts at exactly 0,
    a direction the b-axis mirror makes the pattern even about).  There the
    exact azimuth column is roundoff — measured 2.3e-16 of the modulus
    column — so a solver driven by it has nothing to move the azimuth with
    (whether round-off alone does depends on the platform, below), while
    the peak chain's forward difference reads ½·r″·h, measured 7.6e-7 of it,
    and walks off.  With the analytic azimuth dispatched (measured
    2026-10-28 on darwin/arm64, before the decline), that file's fits from
    β₀ = 101.1° and 103.0° stopped at φ = 0 with χ² 10.9 and 3.7 above the
    minima at φ = ±0.047 the peak chain reaches, and failed its pinned |m|.
    On linux/x86-64 the round-off column walked off unaided, so the stall is
    the platform's and the decline's reason is that it can happen.  When an angle is seeded
    off its stationary point before the stage that frees it, this test is
    the one to change, and the angle can join the branch.
    """
    import tests.test_magnetic_moment_frame as T

    instrument = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25)
    data, scale = T._simulate(instrument, seed=7)
    structure = rx.Structure(phases=[T._phase(101.0, scale=scale)])
    table = ParameterTable(structure, instrument)
    table.set_vary(["*"], False)
    table.set_vary(T.BASE + T.MOMENT, True)
    model = compile_model(structure, instrument, data,
                          moving_paths=set(table.moving_paths))
    theta = table.x0()
    free = table.free_paths
    base = "phases.0.atoms.0.moment"
    azimuth, modulus = free.index(f"{base}.dof2"), free.index(f"{base}.dof0")
    assert abs(theta[azimuth]) < 1e-15        # 0 up to the frame's rounding
    cols = {c: reach for c, _k, reach in _moment_columns(table)}
    built = _built_column(model, table, theta, azimuth, cols[azimuth])
    norm = np.linalg.norm(_built_column(model, table, theta, modulus,
                                        cols[modulus]))
    fd = _make_jacobian(model, table)(theta)[:, azimuth]
    print(f"azimuth/modulus: exact {np.linalg.norm(built) / norm:.1e}, "
          f"peak chain {np.linalg.norm(fd) / norm:.1e}")
    assert np.linalg.norm(built) < 1e-13 * norm
    assert np.linalg.norm(fd) > 1e-9 * norm


# ======================================================== a whole fit

def _fit_arm(analytic: bool):
    """A noisy synthetic fit of a determinable in-plane moment, two sites,
    with the moment columns built analytically or by the pre-branch peak
    chain (``moment_grad_supported`` forced off, the dispatch's only gate)."""
    from rietx.model.forward import CompiledModel

    truth = _ortho([(2.0, 1.0, 0.0), (-1.0, 1.5, 0.0)], PLANE)
    start = _ortho([(1.6, 1.3, 0.0), (-0.7, 1.8, 0.0)], PLANE)
    ins = rx.Instrument.constant_wavelength_neutron(LAMBDA)
    ins.profile.u.value, ins.profile.w.value = 0.05, 0.03
    ins.profile.x.value = 0.04
    tt = np.arange(8.0, 140.0, 0.05)
    s = rx.Structure(phases=[truth])
    sim = compile_model(s, ins, rx.PatternData(two_theta=tt.tolist(),
                                               intensity=np.zeros_like(tt).tolist()))
    t = ParameterTable(s, ins)
    y = np.asarray(sim.evaluate(t.decode(t.x0()))) + 50.0
    y = y + np.random.default_rng(1327).normal(size=y.size) * np.sqrt(y)
    real = CompiledModel.moment_grad_supported
    if not analytic:
        CompiledModel.moment_grad_supported = lambda self, ip: False
    try:
        ref = rx.Refinement(rx.Structure(phases=[start]), ins, history=False)
        result = ref.fit(
            rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist()),
            plan=rx.RefinementPlan(stages=[
                rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
                rx.Stage("moment", ["phases.*.scale", "instrument.background.c*",
                                    "phases.*.atoms.*.moment.dof*"])]))
    finally:
        CompiledModel.moment_grad_supported = real
    return result


def test_a_fit_reaches_the_same_minimum_and_esds_either_way():
    """Not bit-identical, and not expected to be: the peak chain's column
    carries its forward difference's O(h) truncation (5e-7 of the column,
    measured above), which moves the solver's steps and therefore where it
    stops inside its tolerance.  What must agree is what the data decides —
    χ², the values on the scale of their esds, and the esds.

    Measured on two platforms ([dev,jax], Python 3.12; the linux run three
    times, identical each time), χ² / values / esds:

    * darwin/arm64, 2026-10-28: 2.1e-16 relative, 1.0e-9 esd, 5.9e-7 relative;
    * linux/x86-64 (numpy 2.5.3, scipy 1.18.1), 2026-10-31: 4.1e-9 esd for the
      values, 6.0e-7 relative for the esds.

    The esds agree across platforms to 2 %, so the esd bar sits at 10× the
    larger; the values differ by 4× between platforms and both are four
    decades under their bar.  The χ²
    and value bars are wider on purpose: the difference between two
    converged fits senses where each solver stopped (tests/CLAUDE.md
    § Budgets in tests), so they are set at what "the same minimum" means —
    1e-9 of χ², 1e-4 of an esd — rather than at 10× a stopping accident.
    Where the normal matrix is near-singular the esds move by more (the
    near-flat measurement in PR #1206's description), which is the analytic column
    being exact where the forward difference is not — not a disagreement
    this test should absorb, so its fixture is a determinable two-site
    moment.
    """
    a, b = _fit_arm(True), _fit_arm(False)
    assert abs(a.statistics.chi2 - b.statistics.chi2) / a.statistics.chi2 < 1e-9
    ra = {p.path: p for p in a.parameters}
    rb = {p.path: p for p in b.parameters}
    assert ra.keys() == rb.keys()
    moments = [k for k in ra if ".moment.dof" in k]
    assert len(moments) == 4
    dv = de = 0.0
    for k, p in ra.items():
        q = rb[k]
        assert (p.stderr is None) == (q.stderr is None), k
        if p.stderr is None:
            continue
        dv = max(dv, abs(p.value - q.value) / p.stderr)
        de = max(de, abs(p.stderr - q.stderr) / p.stderr)
    print(f"max |dv|/esd {dv:.1e}, max rel d(esd) {de:.1e}")
    assert dv < 1e-4
    assert de < 6e-6
