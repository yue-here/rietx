"""WP-1343 — the synthetic k != 0 round trip: CrSBr, k = (0, 0, 1/2).

Issue #277: a k != 0 constant-wavelength pattern from rietx's own forward model
with a planted ``magnetic_lor_size`` and moment (Poisson noise, seeded), and a
nuclear-only control at the same settings.  The structure is the published one
named in ``tests/_synthetic_crsbr.py`` (López-Paz et al., *Nat. Commun.* 13,
4745 (2022), doi:10.1038/s41467-022-32290-4, CC BY 4.0; Supplementary Table 1,
1.8 K).  This answers WP-1343's "Tests + obs/calc/diff PNGs" line and the k != 0
fallback of its acceptance 4; it does **not** close the "synthetic k = 0 no-esd
case" line.  It tests recovery and the diagnostic, not the model: the data come
from the model being fitted.

Why this file is in the fast tier: the whole file adds 7.6 s locally
(``tests.added_test_times``, Mac, -n 4; at most 15 s is the bar), most of it the
shared fixture's fits and PNG drawing.

Interpretation table (written before the test bodies)
-----------------------------------------------------
=========  ===========  ===============================  ====================================
arm        data         fit                              if it fails, it means
=========  ===========  ===============================  ====================================
A1         broad        ``magnetic_width`` preset + ties  size or moment off by > 2 sigma or
                        from m = 2.0, widths 0           5 %, or strain invented
A1'        broad        same run                         releasing the width did not move the
                                                         moment (predicted ~44 esd)
A2 bias    broad        stage 1 only                     the moment is not biased low by a
                                                         missing width
A2 diag    broad        stage 1 only                     ``MAGNETIC_WIDTH_UNMODELLED`` misses
                                                         the case it exists for (was
                                                         ``xfail``: see below)
A2-4x      broad, 4x    stage 1 only                     the diagnostic does not fire at 4x
                        counts                           counts either
C1 (a)     sharp        stage 1 only                     the diagnostic false-fires, or the
                                                         A2 bias is not caused by the width
C1 (b)     sharp        full preset                      a width found where none was planted
C2         paramagnetic full preset + ties, m = 2.0      an ordered moment or a width is
                                                         invented from nuclear-only data
=========  ===========  ===============================  ====================================

Planted: ``magnetic_lor_size`` 0.20 deg, moment 3.09 mu_B, strongest magnetic
line (child (0 0 1), 2theta 8.9) at 5 000 counts above a 50-count background,
seeds 1343 (broad), 1344 (sharp), 1345 (paramagnetic), fixed before any run and
never changed because a test failed.  Predict-only sensitivity with the real
coordinates (``planning`` check, one-step linearised, not a refinement):
esd(size) 0.0026 deg (1.3 %), esd(m) 0.0165 mu_B, one-step moment shift with the
width omitted -0.68 mu_B (-22 %, ~48 esd).

**Tolerance: 2 sigma and 5 %, never 1 sigma alone.**  On one noise draw 1 sigma
fails about one time in three for no reason but the seed, and picking a passing
seed makes the test meaningless; the 5 % bar is the one that catches a real
bias, since it does not shrink with counts.  The count level is the MnF2 round
trip's argument too: at 5 000 counts the window-truncation floor of the width
term (PR #524: ~1.2 % low) is ~0.8 esd; at 1e5 counts it would be 6 esd and the
bar would test the floor.  The sigma is rietx's quoted esd (Berar-Lelann already
applied), read from the untied dof0 of the Cr pair.

**A2 diagnostic: a recorded finding, then a fix.**  On seed 1343 the moment
held-width fit lands 25 % low (2.317 against 3.09), and
``MAGNETIC_WIDTH_UNMODELLED`` stayed silent at z = 2.99 against its 3.0 bar,
because the misfit inflated the pooled-scatter noise the statistic was divided
by (s = 2.57).  On seeds 1346-1350 it fired on 4 of 5; at 2x counts on 5 of 6,
at 4x on 6 of 6.  ``test_a2_the_diagnostic_fires_at_5000_counts`` was
``xfail(strict=False)`` for that.  The noise is now the scatter of the
nuclear-only channels alone (s = 0.99), which the magnetic misfit does not
enter, and the same fit reads z = 7.76 (6.9-8.2 on seeds 1343 and 1346-1352,
measured 2026-10-20), so the arm is an ordinary pass with its margin.
``A2-4x`` is the same arm at 4x counts (seed 1343; z = 4.10 under the pooled
scatter, 17.0 now) and stays.  **4x gives up the truncation-floor argument
above for this arm only**: it is a diagnostic test, and it asserts no width
or moment recovery.

What each negative arm can catch: C1 holds the same moment and counts as A2 and
only the width differs, so it is the arm that can fail for ``UNMODELLED``.  C2's
silence of ``UNMODELLED`` is weak (with no magnetic intensity the magnetic-only
set may be empty, and the test prints what it is); its real teeth are the
moment-support and width-not-quoted assertions.

Left out on purpose: no preferred orientation (the paper refined March, Nor =
1), no axial asymmetry, no absorption, no second phase, a synthetic instrument
(u = 0.05, w = 0.03; not HRPT's), 1.8 K values only.

PNGs go to ``tests/output/`` (gitignored, not committed), stems
``crsbr_k00half_{a1,a2,c1,c2}`` with ``_mag001`` (5-14 deg) and ``_magmid``
(38-55 deg) zooms.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import gemmi
import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.supercell import anti_translation_residual
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.magnetic import _classified_reflections
from rietx.report.schemas import MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA
from rietx.strategy.staged import PLAN_PRESETS
from tests import _synthetic_crsbr as G

pytestmark = pytest.mark.xdist_group("magnetic-width-k-half")

TRUTH_SIZE, TRUTH_M = G.SIZE, G.MOMENT
UNMODELLED = "MAGNETIC_WIDTH_UNMODELLED"


def _fit(data, plan, count_factor=1.0):
    ref = rx.Refinement(G.start_structure(count_factor=count_factor),
                        G.instrument())
    G.apply_ties(ref)
    res = ref.fit(data, plan=plan)
    assert anti_translation_residual(ref.structure.phases[0]) == pytest.approx(
        0.0, abs=1e-9)
    return ref, res


def _rows(res):
    return {p.path: p for p in res.parameters}


def _codes(res):
    return {d.code for d in res.diagnostics}


def _draw(res, stem):
    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(res, path=str(out / f"crsbr_k00half_{stem}.png"))
    for tag, rng in (("mag001", (5.0, 14.0)), ("magmid", (38.0, 55.0))):
        plot_result(res, path=str(out / f"crsbr_k00half_{stem}_{tag}.png"),
                    two_theta_range=rng)


@pytest.fixture(scope="module")
def arms():
    plan = PLAN_PRESETS["magnetic_width"]()
    stage1 = rx.RefinementPlan(stages=[plan.stages[0]])
    broad, sharp = G.pattern("broad"), G.pattern("sharp")
    para = G.pattern("paramagnetic")
    out = {"broad": broad, "sharp": sharp, "para": para}
    out["a1"] = _fit(broad, plan)
    out["a2"] = _fit(broad, stage1)
    out["a2_4x"] = _fit(G.pattern("broad", count_factor=4.0), stage1,
                        count_factor=4.0)
    out["c1a"] = _fit(sharp, stage1)
    out["c1b"] = _fit(sharp, plan)
    out["c2"] = _fit(para, plan)
    nuc = rx.Refinement(rx.Structure(phases=[G.nuclear_phase()]), G.instrument())
    out["c2_nuc"] = nuc.fit(para, plan=rx.RefinementPlan(stages=[
        rx.Stage("nuclear", ["phases.*.scale", "instrument.background.c*"])]))
    for stem, key in (("a1", "a1"), ("a2", "a2"), ("c1", "c1a"), ("c2", "c2")):
        _draw(out[key][1], stem)
    return out


# --------------------------------------------------------------- the fixture

def test_the_published_structure_expands_to_cr2s2br2_with_sensible_bonds():
    """Setting check (module docstring of ``_synthetic_crsbr``): the paper's
    "Pmnm" does not reproduce the published composition, ``P m m n:2`` does."""
    a, b, c = G.CELL
    cell = np.array(G.CELL)

    def expand(symbol):
        ops = gemmi.SpaceGroup(symbol).operations()
        pts = []
        for el, (x, y, z, _b) in G.SITES.items():
            seen = {tuple(round(v % 1.0, 4) % 1.0 for v in op.apply_to_xyz([x, y, z]))
                    for op in ops}
            pts += [(el, *p) for p in seen]
        return pts

    pts = expand(G.SPACE_GROUP)
    for el in G.SITES:
        assert sum(p[0] == el for p in pts) == 2, el          # Z = 2
    cr = next(p for p in pts if p[0] == "Cr")
    near = sorted((round(float(np.linalg.norm((np.array(q[1:]) + sh
                                               - np.array(cr[1:])) * cell)), 3), q[0])
                  for q in pts if q[0] != "Cr"
                  for sh in itertools.product((-1, 0, 1), repeat=3)
                  if np.linalg.norm((np.array(q[1:]) + sh - np.array(cr[1:])) * cell) < 3.0)
    print("Cr neighbours under 3 A:", near)
    assert [e for _d, e in near].count("S") == 4
    assert [e for _d, e in near].count("Br") == 2
    assert all(2.3 < d < 2.6 for d, _e in near)
    # layers perpendicular to c: the two Br sheets of one layer are 2.3 A apart
    # along c, and the van der Waals gap to the next layer's is over 5 A
    zs = sorted(p[3] * c for p in pts if p[0] == "Br")
    assert zs[1] - zs[0] < 3.0 and zs[0] + c - zs[1] > 5.0, zs
    # the paper's symbol does not give Z = 2 (documented, not relied on)
    assert sum(p[0] == "Cr" for p in expand("P m n m:2")) != 2
    assert a < b < c


def test_the_child_is_a_type_with_moments_along_b():
    st = G.child()
    ph = st.phase
    assert st.bns_number == "62.450" if hasattr(st, "bns_number") else True
    assert ph.cell.c.value == pytest.approx(2 * G.CELL[2])
    cr = [a for a in ph.atoms if a.moment is not None]
    assert len(cr) == 2
    assert G.is_a_type_along_b(ph)
    sites = G._p1_moments(ph)
    print("P1 expansion:", sites)
    assert len(sites) == 4
    assert all(abs(m[1]) == pytest.approx(TRUTH_M) and m[0] == 0 and m[2] == 0
               for _r, m in sites)


def test_the_strongest_magnetic_line_has_no_nuclear_intensity():
    ph = G.child_phase(size=TRUTH_SIZE)
    st = rx.Structure(phases=[ph])
    ins = G.instrument()
    model = compile_model(st, ins, G.blank(), mode="rietveld")
    tab = ParameterTable(st, ins)
    v = tab.decode(tab.x0())
    cp = model.phases[0]
    d = np.asarray(cp.reflections.d)
    cellv = tuple(v[f"phases.0.cell.{k}"] for k in
                  ("a", "b", "c", "alpha", "beta", "gamma"))
    f_nuc = np.asarray(model._nuclear_f2(0, d, v, cellv))
    (_ip, mag, _nuc, pos, _fwhm), = _classified_reflections(model, v)
    hkl = {tuple(int(x) for x in cp.reflections.hkl[k]): k for k in mag}
    assert (0, 0, 1) in hkl
    assert f_nuc[hkl[(0, 0, 1)]] < 1e-20 * f_nuc.max()     # zero to rounding
    assert pos[hkl[(0, 0, 1)]] == pytest.approx(8.9, abs=0.1)


def test_the_scale_puts_the_strongest_magnetic_line_at_5000_counts():
    mag = G.mean_counts(G.child_phase()) - G.mean_counts(G.nuclear_phase())
    assert mag.max() == pytest.approx(5000.0, rel=0.01)
    assert G.TWO_THETA[int(np.argmax(mag))] == pytest.approx(8.9, abs=0.1)


# ------------------------------------------------------------------ the arms

def test_a1_the_planted_width_and_moment_are_recovered(arms):
    _ref, res = arms["a1"]
    rows = _rows(res)
    w = rows["phases.0.magnetic_lor_size"]
    t = rows["phases.0.magnetic_lor_strain"]
    m = rows["phases.0.atoms.0.moment.dof0"]            # the untied dof0
    assert w.stderr is not None and m.stderr is not None
    print(f"A1 size {w.value:.4f}+-{w.stderr:.4f} "
          f"(|d|/s = {abs(w.value - TRUTH_SIZE) / w.stderr:.2f}); "
          f"moment {abs(m.value):.4f}+-{m.stderr:.4f} "
          f"(|d|/s = {abs(abs(m.value) - TRUTH_M) / m.stderr:.2f})")
    assert abs(w.value - TRUTH_SIZE) < 2.0 * w.stderr
    assert abs(w.value - TRUTH_SIZE) < 0.05 * TRUTH_SIZE
    assert abs(abs(m.value) - TRUTH_M) < 2.0 * m.stderr
    assert abs(abs(m.value) - TRUTH_M) < 0.05 * TRUTH_M
    # strain was not planted: it must not come back as a measured width
    assert (t.stderr is None or t.value < 2.0 * t.stderr
            or "MAGNETIC_WIDTH_UNMEASURED" in _codes(res))


def test_a1_prime_releasing_the_width_moves_the_moment(arms):
    _ref, res = arms["a1"]
    hits = [d for d in res.diagnostics if d.code == "MAGNETIC_WIDTH_MOVED_MOMENT"]
    assert len(hits) == 1, sorted(_codes(res))
    print(f"A1' moved-moment statistic {hits[0].value:.1f}x")
    assert hits[0].value > MAGNETIC_WIDTH_MOMENT_SHIFT_SIGMA
    assert any("magnetic_lor" in q for q in hits[0].where)


def test_a2_without_the_width_the_moment_is_biased_low(arms):
    _ref, res = arms["a2"]
    m = _rows(res)["phases.0.atoms.0.moment.dof0"]
    bias = (TRUTH_M - abs(m.value)) / TRUTH_M
    print(f"A2 moment {abs(m.value):.3f}+-{m.stderr:.3f}, {100 * bias:.1f} % low")
    assert abs(m.value) < TRUTH_M - 3.0 * m.stderr
    assert bias > 0.10


def test_a2_the_diagnostic_fires_at_5000_counts(arms):
    """Was ``xfail``: z = 2.99 under the pooled scatter.  Its noise is now the
    nuclear-only channels' scatter, and z = 7.76 here."""
    _ref, res = arms["a2"]
    hits = [d for d in res.diagnostics if d.code == UNMODELLED]
    assert len(hits) == 1, sorted(_codes(res))
    print(f"A2 UNMODELLED z = {hits[0].value:.2f}")
    assert "biased low" in hits[0].message
    assert "(0 0 1)" in hits[0].message


def test_a2_4x_the_diagnostic_fires_at_four_times_the_counts(arms):
    """Same arm, 4x counts, seed 1343 (z = 17.0).  Gives up the truncation-floor
    argument for this arm only; no recovery is asserted here."""
    _ref, res = arms["a2_4x"]
    m = _rows(res)["phases.0.atoms.0.moment.dof0"]
    print(f"A2-4x moment {abs(m.value):.3f}+-{m.stderr:.3f} "
          f"({100 * (TRUTH_M - abs(m.value)) / TRUTH_M:.1f} % low)")
    assert abs(m.value) < TRUTH_M - 3.0 * m.stderr
    hits = [d for d in res.diagnostics if d.code == UNMODELLED]
    assert len(hits) == 1, sorted(_codes(res))
    print(f"A2-4x UNMODELLED z = {hits[0].value:.2f}")
    assert "biased low" in hits[0].message
    assert "magnetic_lor_size" in hits[0].where[0]
    assert "(0 0 1)" in hits[0].message


def test_c1a_the_sharp_twin_is_silent_and_unbiased(arms):
    _ref, res = arms["c1a"]
    m = _rows(res)["phases.0.atoms.0.moment.dof0"]
    assert UNMODELLED not in _codes(res)
    assert abs(abs(m.value) - TRUTH_M) < 2.0 * m.stderr
    assert abs(abs(m.value) - TRUTH_M) < 0.05 * TRUTH_M


def test_c1b_no_width_is_found_where_none_was_planted(arms):
    _ref, res = arms["c1b"]
    w = _rows(res)["phases.0.magnetic_lor_size"]
    codes = _codes(res)
    assert (w.stderr is None or w.value < 2.0 * w.stderr
            or "MAGNETIC_WIDTH_UNMEASURED" in codes)
    assert "MAGNETIC_WIDTH_MOVED_MOMENT" not in codes


def test_c2_above_tn_finds_no_moment_and_no_width(arms):
    ref, res = arms["c2"]
    nuc = arms["c2_nuc"]
    rows = ref.report().magnetic
    assert rows
    for row in rows:
        assert row.supported is False, (row.magnitude, row.magnitude_esd, row.note)
        assert row.magnitude < 3.0 * row.magnitude_esd
        assert "unsupported, not as a small moment" in row.note
    w = _rows(res)["phases.0.magnetic_lor_size"]
    assert (w.stderr is None or w.value < 2.0 * w.stderr
            or "MAGNETIC_WIDTH_UNMEASURED" in _codes(res))
    # weak evidence: the magnetic-only set may be empty with no moment; say what it is
    model = compile_model(ref.structure, ref.instrument, arms["para"],
                          mode="rietveld")
    tab = ParameterTable(ref.structure, ref.instrument)
    sets = [(len(mag), len(nu)) for _ip, mag, nu, _p, _f in
            _classified_reflections(model, tab.decode(tab.x0()))]
    print("C2 classified (magnetic-only, nuclear-only) counts:", sets)
    assert UNMODELLED not in _codes(res), f"classified sets {sets}"
    assert res.statistics.rwp == pytest.approx(nuc.statistics.rwp, rel=1e-3)
