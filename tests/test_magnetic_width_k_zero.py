"""WP-1343 — the synthetic k = 0 case: a magnetic width the data barely sees.

The WP's identifiability task: "the unmeasured path named rather than quoted,
on all three regimes; a synthetic k = 0 case asserted to come back with no esd
rather than a small one".  Its three regimes (§ When the term is measurable)
are k != 0 with magnetic-only satellites, k = 0 with **every magnetic
reflection also nuclear**, and paramagnetic.  #943's
``test_magnetic_width_k_half.py`` holds the first and the third on CrSBr.  This
file adds the second, on the same published structure, the same instrument,
the same specimen and the same counting.  So the stacking of the moments is
the only thing that differs from #943's arms.

**The structure.**  CrSBr as published by López-Paz et al., *Nat. Commun.*
**13**, 4745 (2022), doi:10.1038/s41467-022-32290-4 (CC BY 4.0;
Supplementary Table 1, 1.8 K), through ``tests/_synthetic_crsbr.py``.  The
child is the **k = 0 ferromagnet with the moments along c**, BNS 59.409, on
the parent cell, picked by its P1 expansion and not by its index.  It is not
the published zero-field structure (A-type, moments along b, k = (0, 0, 1/2)).
It is the order the paper's magnetisation data reach along c above the
saturation field (2 T at base temperature, p. 3), which the paper reports but
does not refine.  It is the k = 0 child of the published structure that puts
the WP's second regime on it, and the moment keeps the paper's 3.09 μ_B.

**Why along c and not along b, and why not MnF₂.**  Both Cr of the cell
carry the same moment, so the magnetic structure factor has the Cr partial
nuclear one's geometry.  Every glide and screw extinction holds for both, and
no reflection is magnetic-only by symmetry.  It can still be magnetic-only by
accident.  Along b, the (0 0 l) lines carry magnetic intensity (Q is normal to
m), and the nuclear (0 0 1) nearly cancels between Cr, S and Br, so (0 0 1) is
97 % magnetic.  The width is measured on that one line: the scratch run below
gave it an esd of 0.018-0.022°, named on 0 of 30 draws.  Along c, Q is
parallel to m on (0 0 l), so those lines carry nothing magnetic.  Then no
reflection that carries at least 0.1 % of the strongest magnetic line is over
95 % magnetic, and the regime is the WP's second one.  MnF₂ (``test_magnetic``,
Erickson 1953) has its strongest magnetic line, (1 0 0), systematically
absent in P4₂/mnm, and ``test_a_planted_magnetic_width_and_moment_are_recovered``
recovers a planted width there to 5 %, so it is the first regime.

**What the code does today** (``report/magnetic._width_support_findings``):
an unmeasurable width comes back with a finite esd larger than its value, and
``MAGNETIC_WIDTH_UNMEASURED`` names the path.  It does not come back with an
absent esd, because with a non-zero moment the width's column is never zero.
That is the deviation #524 argued and the WP's handover accepted.  So "no esd
rather than a small one" is asserted here in the form the code has: **a wide
esd that covers the truth, and the path named, never a small esd**.

Interpretation table (written before the test bodies)
-----------------------------------------------------
=========  ==============  ============================  =========================================
arm        data            fit                           if it fails, it means
=========  ==============  ============================  =========================================
regime     k = 0 child     none (compile only)           the child has a magnetic-only line, so it
                                                         is not the WP's second regime
Kh+        k = 1/2, broad  ``magnetic_width`` preset     the positive arm cannot measure the width,
                                                         so nothing below can tell regimes apart
K0         k = 0, broad    ``magnetic_width`` preset     the width came back with a small esd: as
                                                         tight as where it is measured, or missing
                                                         the planted value
K0-sharp   k = 0, sharp    ``magnetic_width`` preset     a width nobody planted was quoted
names      all five above ``magnetic_width`` preset      a width the fit cannot measure was quoted,
                                                         or a measured one was named unmeasured
K0-held    k = 0, broad    stage 1 only                  the moment does not pay for the width at
                                                         k = 0, so the regime is not worth a test
K0-diag    k = 0, broad    stage 1 only                  xfail(strict): no report names the
                                                         missing width (see the test)
=========  ==============  ============================  =========================================

Planted: ``magnetic_lor_size`` 0.20° and moment 3.09 μ_B, #943's values.  The
scale is 4 × #943's, because the parent cell carries a quarter of the
a, b, 2c child's |F|², so the nuclear counts are #943's to rounding (asserted).
Seeds 1353 (broad) and 1354 (sharp) were fixed before the first run.  #943's
1343, 1344 and 1345 are reused for its arms.

**Where the bars come from.**  A scratch run over seeds 2000-2029 (macOS arm64,
this tree, not part of the suite) measured the k = 0 broad arm's width esd at
0.062-0.081°, against 0.0045-0.0050° on the k = 1/2 broad arm at the same
seeds: 12.4× at the closest pair.  The bar is 5×.  The width came back within
2.56 of its esd of the truth at worst (s.d. of the pulls 0.67, so the esd is
conservative), and the bar is 3.  ``MAGNETIC_WIDTH_UNMEASURED`` named it on
22 of 30 draws; on the other 8 it read 3.0-3.3 esd.  So the code is not asked
to name it on this one draw.  It is asked that the name and the ratio agree.
With no width planted it was named on 30 of 30, at most 0.56 esd.  The moment
esd was 3.6× k = 1/2's at least, and the bar is 2×.

PNGs go to ``tests/output/`` (gitignored, not committed), the
``test_magnetic_width_k_half.py`` convention: ``crsbr_k000_{free,held}`` and
the zooms ``_mag101`` (40-50°) and ``_mag021`` (60-70°).  This regime has no
magnetic-only reflection to zoom on, so the zooms frame the most magnetic
lines: (1 0 1) at 44.8°, 89 % magnetic, and (0 2 1) at 65.2°, 92 %.
#943's ``crsbr_k00half_{a1,a2}`` are the k = 1/2 pair, width free and held.

It tests recovery and reporting, not the model: the data come from the model
being fitted.  Why the fast tier: six fits of about 0.3 s each, and six PNGs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.supercell import magnetic_supercell
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.schemas import MOMENT_SUPPORT_SIGMA
from rietx.schemas.common import Parameter
from rietx.strategy.staged import PLAN_PRESETS
from tests import _synthetic_crsbr as G

pytestmark = pytest.mark.xdist_group("magnetic-width-k-zero")

TRUTH_SIZE, TRUTH_M = G.SIZE, G.MOMENT
UNMEASURED = "MAGNETIC_WIDTH_UNMEASURED"
WIDTHS = ("phases.0.magnetic_lor_size", "phases.0.magnetic_lor_strain")
K0_BNS = "59.409"
#: the parent cell holds a quarter of the a,b,2c child's |F|²
K0_SCALE = 4.0 * G.SCALE
K0_SEEDS = {"broad": 1353, "sharp": 1354}


def _k0_moments(magnitude):
    """Every Cr of a k = 0 child's P1 expansion: ``(site, moment)``."""
    cs = candidates(G.SPACE_GROUP, G.SITES["Cr"][:3], ("0", "0", "0"))
    for cand in cs.candidates:
        try:
            st = magnetic_supercell(G.parent(), cand, magnetic_species="Cr",
                                    ion="Cr3+", magnitude=magnitude)
        except Exception:  # noqa: BLE001 - a candidate the builder refuses is skipped
            continue
        yield cand.bns_number, st.phase


def _ferro(magnitude, axis):
    """The k = 0 ferromagnet with moments along ``axis``, chosen by its P1
    expansion: every Cr carries ``+magnitude`` on that axis and nothing else."""
    for bns, ph in _k0_moments(magnitude):
        sites = G._p1_moments(ph)
        if sites and all(m[axis] > 0 and all(abs(m[i]) < 1e-9 for i in range(3)
                                                if i != axis)
                         for _r, m in sites):
            return bns, ph
    raise AssertionError(f"no k = 0 ferromagnet along axis {axis}")


def k0_phase(magnitude=TRUTH_M, *, size=0.0, scale=K0_SCALE):
    _bns, ph = _ferro(magnitude, 2)
    ph.scale.value = scale
    if size:
        ph.magnetic_lor_size = Parameter(value=size, min=0.0, unit="deg",
                                         transform="softplus")
        ph.magnetic_lor_strain = Parameter(value=0.0, min=0.0, unit="deg",
                                           transform="softplus")
    return ph


def k0_pattern(kind):
    ph = k0_phase(size=TRUTH_SIZE if kind == "broad" else 0.0)
    counts = np.random.default_rng(K0_SEEDS[kind]).poisson(
        G.mean_counts(ph)).astype(float)
    return rx.PatternData(two_theta=G.TWO_THETA.tolist(),
                          intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def _intensities(ph):
    """(hkl, ⟨|F_N|²⟩, p²⟨|F_⊥|²⟩) per reflection at the stored values."""
    st = rx.Structure(phases=[ph])
    ins = G.instrument()
    model = compile_model(st, ins, G.blank(), mode="rietveld")
    tab = ParameterTable(st, ins)
    v = tab.decode(tab.x0())
    cp = model.phases[0]
    d = np.asarray(cp.reflections.d)
    cell = tuple(v[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    hkl = [tuple(int(x) for x in row) for row in cp.reflections.hkl]
    return (hkl, np.asarray(model._nuclear_f2(0, d, v, cell)),
            np.asarray(model._magnetic_f2(0, d, v, cell)))


def _magnetic_only(ph):
    """Reflections carrying magnetic intensity and no nuclear: at least
    0.1 % of the strongest magnetic line, under 5 % nuclear.  The floor is
    what keeps rows extinct to rounding (f_mag ~1e-30) out; on the k = 0
    child it also leaves out (1 1 2), magnetic-only at 0.03 % of (1 1 0)."""
    hkl, f_n, f_m = _intensities(ph)
    real = f_m >= 1e-3 * f_m.max()
    frac = np.where(real, f_m / np.maximum(f_n + f_m, 1e-300), 0.0)
    return [hkl[k] for k in np.nonzero(real & (frac > 0.95))[0]]


def _rows(res):
    return {p.path: p for p in res.parameters}


def _named(res):
    return {d.where[0]: d for d in res.diagnostics if d.code == UNMEASURED}


def _draw(res, stem, label):
    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    title = (f"CrSBr, $k$ = 0 ferromagnet along $c$, {label}; "
             f"$\\lambda$ = {G.LAMBDA} Å")
    plot_result(res, path=str(out / f"crsbr_k000_{stem}.png"), title=title)
    for tag, rng in (("mag101", (40.0, 50.0)), ("mag021", (60.0, 70.0))):
        plot_result(res, path=str(out / f"crsbr_k000_{stem}_{tag}.png"),
                    two_theta_range=rng, title=title)


@pytest.fixture(scope="module")
def arms():
    plan = PLAN_PRESETS["magnetic_width"]()
    stage1 = rx.RefinementPlan(stages=[plan.stages[0]])

    def k_half(kind):
        ref = rx.Refinement(G.start_structure(), G.instrument())
        G.apply_ties(ref)
        return ref.fit(G.pattern(kind), plan=plan)

    def k_zero(data, p):
        ref = rx.Refinement(rx.Structure(phases=[k0_phase(2.0)]),
                            G.instrument())
        return ref.fit(data, plan=p)

    broad = k0_pattern("broad")
    out = {"kh_broad": k_half("broad"), "kh_sharp": k_half("sharp"),
           "para": k_half("paramagnetic"),
           "k0_broad": k_zero(broad, plan),
           "k0_sharp": k_zero(k0_pattern("sharp"), plan),
           "k0_held": k_zero(broad, stage1)}
    _draw(out["k0_broad"], "free", "width free")
    _draw(out["k0_held"], "held", "width held at zero")
    return out


# --------------------------------------------------------------- the regime

def test_the_k0_child_is_a_ferromagnet_along_c_on_the_parent_cell():
    bns, ph = _ferro(TRUTH_M, 2)
    assert bns == K0_BNS
    assert ph.cell.c.value == pytest.approx(G.CELL[2])
    sites = G._p1_moments(ph)
    print("P1 expansion:", sites)
    assert len(sites) == 2
    assert all(m == pytest.approx((0.0, 0.0, TRUTH_M)) for _r, m in sites)


def test_every_magnetic_reflection_of_the_k0_child_is_also_nuclear():
    """The WP's second regime, with its positive arms: the same check finds
    the accidental (0 0 1) on the b-axis ferromagnet and the satellites of
    #943's k = 1/2 child, so an empty list here is a property of the child,
    not of the check."""
    assert _magnetic_only(k0_phase()) == []
    hkl, f_n, f_m = _intensities(k0_phase())
    print("k = 0 along c, (1 1 2) share of the strongest magnetic line:",
          f_m[hkl.index((1, 1, 2))] / f_m.max())
    along_b = _magnetic_only(_ferro(TRUTH_M, 1)[1])
    print("k = 0 along b, magnetic-only:", along_b)
    assert (0, 0, 1) in along_b
    k_half = _magnetic_only(G.child_phase())
    print("k = 1/2, magnetic-only:", len(k_half), "including (0 0 1):",
          (0, 0, 1) in k_half)
    assert (0, 0, 1) in k_half


def test_the_k0_scale_is_the_same_specimen_as_the_k_half_fixture():
    bare = k0_phase()
    for a in bare.atoms:
        a.moment = None
    bare.magnetic_symmetry = None
    np.testing.assert_allclose(G.mean_counts(bare),
                               G.mean_counts(G.nuclear_phase()), rtol=1e-9)


# ------------------------------------------------------------------ the arms

def test_kh_positive_arm_the_width_is_measured_where_satellites_are_magnetic(arms):
    w = _rows(arms["kh_broad"])["phases.0.magnetic_lor_size"]
    print(f"k=1/2 size {w.value:.4f}+-{w.stderr:.4f} ({w.value / w.stderr:.1f} esd)")
    assert w.stderr is not None
    assert w.value > MOMENT_SUPPORT_SIGMA * w.stderr
    assert "phases.0.magnetic_lor_size" not in _named(arms["kh_broad"])


def test_k0_the_planted_width_comes_back_with_a_wide_esd_not_a_small_one(arms):
    """The identifiability task at k = 0.  The esd is finite (the column is
    not zero while the moment is not), wide against the measured regime's at
    the same specimen and counts, and it covers the planted value."""
    w0 = _rows(arms["k0_broad"])["phases.0.magnetic_lor_size"]
    wh = _rows(arms["kh_broad"])["phases.0.magnetic_lor_size"]
    m0 = _rows(arms["k0_broad"])["phases.0.atoms.0.moment.dof0"]
    mh = _rows(arms["kh_broad"])["phases.0.atoms.0.moment.dof0"]
    print(f"k=0 size {w0.value:.4f}+-{w0.stderr:.4f}, k=1/2 +-{wh.stderr:.4f} "
          f"({w0.stderr / wh.stderr:.1f}x); |d|/esd "
          f"{abs(w0.value - TRUTH_SIZE) / w0.stderr:.2f}; moment "
          f"{abs(m0.value):.3f}+-{m0.stderr:.3f} (k=1/2 +-{mh.stderr:.3f})")
    assert w0.stderr is not None and wh.stderr is not None
    assert w0.stderr > 5.0 * wh.stderr
    assert abs(w0.value - TRUTH_SIZE) < 3.0 * w0.stderr
    assert m0.stderr > 2.0 * mh.stderr
    assert abs(abs(m0.value) - TRUTH_M) < 3.0 * m0.stderr


@pytest.mark.parametrize("arm", ["kh_broad", "kh_sharp", "k0_broad",
                                 "k0_sharp", "para"])
def test_each_regime_names_exactly_the_widths_it_cannot_measure(arms, arm):
    """Named rather than quoted, both ways, on all three regimes: a freed
    width is named ``MAGNETIC_WIDTH_UNMEASURED`` exactly when it is back
    under ``MOMENT_SUPPORT_SIGMA`` of its esd or with none, the message
    carries the path and the reason, and no width the fit measured is
    named."""
    res = arms[arm]
    rows, named = _rows(res), _named(res)
    weak = {p for p in WIDTHS
            if rows[p].stderr is None
            or rows[p].value < MOMENT_SUPPORT_SIGMA * rows[p].stderr}
    print(arm, {p: (round(rows[p].value, 4), rows[p].stderr) for p in WIDTHS},
          "named:", sorted(named))
    assert set(named) == weak
    for p, d in named.items():
        assert d.where == [p]
        assert p in d.message
        assert ("below the 3-sigma bar" in d.message
                or "not measured" in d.message), d.message
    if arm in ("k0_sharp", "para"):
        assert weak == set(WIDTHS)          # nothing planted: both named
    if arm == "kh_broad":
        assert weak == {"phases.0.magnetic_lor_strain"}


def test_k0_without_the_width_the_moment_is_biased_low(arms):
    """The moment pays for the width at k = 0 too: 25 % low, at least 8.1
    esd over the 30 scratch draws."""
    m = _rows(arms["k0_held"])["phases.0.atoms.0.moment.dof0"]
    bias = (TRUTH_M - abs(m.value)) / TRUTH_M
    print(f"k=0 held moment {abs(m.value):.3f}+-{m.stderr:.3f}, "
          f"{100 * bias:.1f} % low")
    assert abs(m.value) < TRUTH_M - 3.0 * m.stderr
    assert bias > 0.10


@pytest.mark.xfail(strict=True, reason=(
    "WP-1343 regime 2 has no magnetic-only reflection, so "
    "MAGNETIC_WIDTH_UNMODELLED's differential statistic has nothing to read. "
    "Its classifier (report.magnetic._classified_reflections, f_mag > 0.0) "
    "returns five rows extinct to rounding ((0 1 0), (1 0 0), (1 2 0), (2 1 0), "
    "(0 3 0), with f_mag ~1e-30) plus (1 1 2) at 0.03 % of the strongest "
    "line, and the warning stays silent on 30 of 30 draws while the moment "
    "is 25 % low. Nothing in the report says the width check could not be "
    "made. Recorded for the maintainer, not fixed here."))
def test_k0_held_the_report_names_the_missing_width(arms):
    res = arms["k0_held"]
    assert any("phases.0.magnetic_lor_size" in q
               for d in res.diagnostics for q in d.where), \
        sorted(d.code for d in res.diagnostics)
