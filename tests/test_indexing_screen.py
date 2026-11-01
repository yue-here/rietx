"""The line screen, the containment refuter and the windowed cap (C3, issue #916).

Synthetic only: the two control patterns of the C3 design record, regenerated
here from their seeds — Si (F d -3 m, a = 5.4311 Å, 16 lines at λ = 0.8257 Å,
the "flat17" repro of #916) and a tetragonal P cell with c/a = 1.01 (60
lines), each with the derivative and descent cells the design measured.  Every
arm below has a reading pre-registered in that record's interpretation table;
the negative arms are the ones that would have refuted the build.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

import rietx as rx
from rietx.indexing.ambiguity import SupercellEvidence
from rietx.indexing.consensus import caveats_for, grade
from rietx.indexing.engines import absence_window, engine_names, match_window
from rietx.indexing.fom import RESOLUTION_FWHM, fom_panel
from rietx.indexing.pick import pick_peaks
from rietx.model import compiled
from rietx.schemas.indexing import (
    INDEX_REFUTING_CAVEATS,
    BravaisOpinion,
    CellCandidate,
    FigureOfMerit,
    LeBailValidation,
)

# The module fixtures ``si`` and ``tet`` (a synthesis plus ``pick_peaks``) are shared by
# most tests below, so the module stays on one worker (tests/CLAUDE.md § Shared fixtures).
pytestmark = pytest.mark.xdist_group("indexing-screen")

A0, LAM, LIM = 5.4311, 0.825739, (12.1, 60.0)
R2 = float(np.sqrt(2.0))
AT, CT = 3.90, 3.939

_SI = ("data_Si\n_cell_length_a 5.4311\n_cell_length_b 5.4311\n_cell_length_c 5.4311\n"
       "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
       "_space_group_IT_number 227\n_symmetry_space_group_name_H-M 'F d -3 m'\n"
       "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
       "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
       "Si1 Si 0.125 0.125 0.125 0.5\n")
_TET = (f"data_t\n_cell_length_a {AT}\n_cell_length_b {AT}\n_cell_length_c {CT}\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
        "_space_group_IT_number 123\n_symmetry_space_group_name_H-M 'P 4/m m m'\n"
        "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
        "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
        "Ba1 Ba 0 0 0 0.5\nTi1 Ti 0.5 0.5 0.5 0.5\n")


def _synth(cif: str, scale: float, bg: float, seed: int) -> rx.PatternData:
    with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as f:
        f.write(cif)
    try:
        s = rx.Structure.from_cif(f.name)
    finally:
        os.unlink(f.name)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value = 3e-4, 5e-4
    ins.profile.x.value = 5e-3
    tt = np.round(np.arange(12.088, 62.0, 0.004), 3)
    y = rx.Refinement(s, ins, history=False).predict(two_theta=tt)
    obs = np.random.default_rng(seed).poisson(y / y.max() * scale + bg).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1.0))))


def _instrument() -> rx.Instrument:
    return rx.Instrument.debye_scherrer(wavelength=LAM)


_ANGLES = {"trigonal": (90.0, 90.0, 120.0)}


def _cell(system: str, abc) -> tuple[float, ...]:
    return tuple(float(v) for v in abc) + _ANGLES.get(system, (90.0, 90.0, 90.0))


#: the Si controls: name → (system, centring, cell).  The truth first.
SI_CELLS = {
    "truth cF": ("cubic", "F", _cell("cubic", (A0,) * 3)),
    "tI same lattice": ("tetragonal", "I", _cell("tetragonal", (A0 / R2, A0 / R2, A0))),
    "hR rank-1 of #916": ("trigonal", "R", _cell("trigonal", (3.8450, 3.8450, 9.3904))),
    "cI sqrt2 a0": ("cubic", "I", _cell("cubic", (R2 * A0,) * 3)),
    "cP a0": ("cubic", "P", _cell("cubic", (A0,) * 3)),
    "cP 2a0": ("cubic", "P", _cell("cubic", (2 * A0,) * 3)),
    "tI rank-3 of #916": ("tetragonal", "I", _cell("tetragonal", (3.8424, 3.8424, 5.4091))),
}
TET_CELLS = {
    "truth tP": ("tetragonal", "P", _cell("tetragonal", (AT, AT, CT))),
    "oP resolved split": ("orthorhombic", "P", _cell("orthorhombic", (AT, 1.003 * AT, CT))),
    "oP unresolved split": ("orthorhombic", "P", _cell("orthorhombic", (AT, 1.0003 * AT, CT))),
    "tP c x2": ("tetragonal", "P", _cell("tetragonal", (AT, AT, 2 * CT))),
}


@pytest.fixture(scope="module")
def si():
    data = _synth(_SI, 1.3e6, 7700.0, 1)
    ins = _instrument()
    peaks = pick_peaks(data, ins, two_theta_range=LIM)
    return data, ins, peaks


@pytest.fixture(scope="module")
def tet():
    # Poisson seed 2: a pick on the noise can land on one of the resolved split's
    # seven extras by chance (p0 = 0.06), and one seen extra is 'undecided', not
    # 'refuted' (seeds 1, 3, 7, 8 of 1-8 do; 2, 4, 5, 6 read 0 seen).
    data = _synth(_TET, 1.0e6, 5000.0, 2)
    ins = _instrument()
    peaks = pick_peaks(data, ins, two_theta_range=LIM)
    return data, ins, peaks


def _screens(data, ins, peaks, cells):
    from rietx.indexing.screen import PatternScreen, screen_candidate

    pattern = PatternScreen.from_peaks(peaks, q_match=absence_window(peaks),
                                       data=data, instrument=ins)
    return pattern, {name: screen_candidate(pattern, cell, system, centring)
                     for name, (system, centring, cell) in cells.items()}


# ----------------------------------------------------------------------
# the refuter: containment of the indexed set, judged against chance
# ----------------------------------------------------------------------
def test_the_refuter_reaches_the_cells_the_sublattice_relation_could_not(si):
    """P1: the three cells issue #916 could not refute, and the trigonal
    description that outranked the truth, are refuted as children of the
    truth — extras seen no more often than chance.

    Cubic I √2·a₀ has a primitive volume 5.66× the truth's and cubic P 2a₀
    32×, so neither is an index-2-to-4 sublattice pair; the hR cell has the
    *same* primitive volume.  Containment of the indexed set reaches all of
    them (pre-registered: 0 of 12, 0 of 8, 0 of 85, 0 of 2 seen).
    """
    from rietx.indexing.screen import containment_evidence

    pattern, s = _screens(*si, SI_CELLS)
    assert len(si[2].usable()) == 16
    truth = s["truth cF"]
    expect = {"cI sqrt2 a0": ("containment", 0), "cP a0": ("sublattice", 4),
              "cP 2a0": ("containment", 0), "hR rank-1 of #916": ("containment", 0),
              "tI rank-3 of #916": ("containment", 0)}
    for name, (relation, index) in expect.items():
        ev = containment_evidence(pattern, s[name], truth)
        assert ev is not None, name
        assert ev.verdict() == "refuted", (name, ev.n_seen, ev.n_extra, ev.p_value)
        assert ev.n_seen <= ev.n_extra * ev.p0
        assert (ev.relation, ev.index) == (relation, index), name
    # the one the old relation reached is reached the same way, and the
    # strongest refutation is the densest cell
    assert containment_evidence(pattern, s["cP 2a0"], truth).n_extra >= 80
    assert containment_evidence(pattern, s["cI sqrt2 a0"], truth).n_extra >= 10


def test_a_truth_is_never_refuted_and_a_second_description_is_a_tie(si):
    """N1: the truth as a child of every other cell is never refuted, and the
    tetragonal I description of the same lattice is undecided both ways (no
    extra line at the resolution).  Either reading failing refutes the
    containment relation on its own motivating pattern.
    """
    from rietx.indexing.screen import containment_evidence, contains

    pattern, s = _screens(*si, SI_CELLS)
    truth = s["truth cF"]
    for name, other in s.items():
        if name == "truth cF":
            continue
        ev = containment_evidence(pattern, truth, other)
        assert ev is None or ev.verdict() != "refuted", (name, ev)
    same = s["tI same lattice"]
    asked = [containment_evidence(pattern, same, truth),
             containment_evidence(pattern, truth, same)]
    assert any(ev is not None for ev in asked)
    for ev in asked:
        if ev is not None:
            assert ev.n_extra == 0 and ev.verdict() == "undecided"
    # the direction: the denser line set is the child, never the sparser
    assert contains(s["cI sqrt2 a0"], truth) and not contains(truth, s["cI sqrt2 a0"])


def test_two_cells_of_equal_density_and_volume_do_not_contain_each_other(si):
    """``below_refuting_parents`` waits a child on its parent on the ground that
    a parent is strictly smaller, so the relation must be antisymmetric: two
    screens with equal line counts and equal volume contain neither way."""
    from rietx.indexing.screen import contains

    _pattern, s = _screens(*si, SI_CELLS)
    twin = _screens(*si, {"twin": SI_CELLS["truth cF"]})[1]["twin"]
    truth = s["truth cF"]
    assert truth.n_lines == twin.n_lines
    assert not contains(truth, twin) and not contains(twin, truth)
    assert not contains(truth, truth)


def test_a_resolved_split_is_refuted_and_an_unresolved_one_is_a_tie(tet):
    """P2/N2: on the tetragonal set the b × 1.003 orthorhombic cell (partners
    0.04–0.09° apart at a 0.023° FWHM) is refuted as a child of the truth,
    while b × 1.0003 (partners inside one FWHM everywhere) merges to the
    truth's own line set, has no extra, and is undecided.  Refuting the
    unresolved split is the reading that would refute the resolution
    constant; at 0.5 FWHM it did.

    Seed 2 is the worked example, where the resolved split reads ``refuted``.
    That reading is not every draw's: across Poisson seeds 1–8 it is ``refuted``
    on four (2, 4, 5, 6) and ``undecided`` on four (1, 3, 7, 8), one or two of
    its seven extras landing on a pick by chance — the property of k ≤ n·p₀
    when n·p₀ < 1.  What holds on every draw is pinned by the next test.
    """
    from rietx.indexing.screen import containment_evidence

    pattern, s = _screens(*tet, TET_CELLS)
    truth = s["truth tP"]
    resolved = containment_evidence(pattern, s["oP resolved split"], truth)
    assert resolved is not None and resolved.verdict() == "refuted"
    assert resolved.n_seen == 0 and resolved.n_extra >= 5
    unresolved = s["oP unresolved split"]
    assert unresolved.n_lines <= truth.n_lines     # merged into the truth's lines
    for child, parent in ((unresolved, truth), (truth, unresolved)):
        ev = containment_evidence(pattern, child, parent)
        if ev is not None:
            assert ev.n_extra == 0 and ev.verdict() == "undecided"
    assert unresolved.seen_fraction == pytest.approx(truth.seen_fraction)
    # the ordinary index-2 supercell is still refuted, as WP-1449 did
    doubled = containment_evidence(pattern, s["tP c x2"], truth)
    assert doubled is not None and doubled.verdict() == "refuted"
    assert (doubled.relation, doubled.index) == ("sublattice", 2)


@pytest.mark.parametrize("seed", range(1, 9))
def test_a_split_reads_the_same_on_every_poisson_draw(seed):
    """P2/N2 across Poisson seeds 1–8 (Yue's ruling, 2026-10-24): what holds on
    every draw, not the one a seed happens to give.  The resolved split is
    never ``supported`` (``refuted`` on seeds 2, 4, 5, 6; ``undecided`` on
    1, 3, 7, 8) and sees about half its lines against the truth's all, a
    reading taken at ``RESOLUTION_FWHM`` too, so it still catches a resolution
    constant grown large enough to merge the partners.  The unresolved split
    holds every assertion of the seed-2 test on all eight draws, and the c × 2
    cell is ``refuted`` as a ``sublattice`` of index 2 on all eight."""
    from rietx.indexing.screen import containment_evidence

    data = _synth(_TET, 1.0e6, 5000.0, seed)
    ins = _instrument()
    peaks = pick_peaks(data, ins, two_theta_range=LIM)
    pattern, s = _screens(data, ins, peaks, TET_CELLS)
    truth = s["truth tP"]
    assert truth.seen_fraction == pytest.approx(1.0)
    resolved = containment_evidence(pattern, s["oP resolved split"], truth)
    assert resolved is not None and resolved.verdict() in ("refuted", "undecided")
    assert resolved.n_extra >= 5 and resolved.n_seen <= 2
    assert 0.4 < s["oP resolved split"].seen_fraction < 0.7
    unresolved = s["oP unresolved split"]
    assert unresolved.n_lines <= truth.n_lines
    for child, parent in ((unresolved, truth), (truth, unresolved)):
        ev = containment_evidence(pattern, child, parent)
        if ev is not None:
            assert ev.n_extra == 0 and ev.verdict() == "undecided"
    assert unresolved.seen_fraction == pytest.approx(truth.seen_fraction)
    doubled = containment_evidence(pattern, s["tP c x2"], truth)
    assert doubled is not None and doubled.verdict() == "refuted"
    assert (doubled.relation, doubled.index) == ("sublattice", 2)


# ----------------------------------------------------------------------
# the cap: the windowed uncancellable absent count
# ----------------------------------------------------------------------
def test_the_windowed_uncancellable_count_separates_the_truths_from_the_wrong_cells(si, tet):
    """P3/N3: every truth reads 0 absences that no extinction could remove
    inside de Wolff's window; cubic I √2·a₀ reads ≥ 7 (pre-registered; the
    record measured 11–12), cubic P 2a₀ ≥ 50.  The truth's d-glide absences
    are counted (full range) and cancellable, so they never reach the cap.
    """
    _p, s = _screens(*si, SI_CELLS)
    truth = s["truth cF"]
    assert truth.n_absent_uncancellable_in_window == 0
    assert truth.n_absent_uncancellable == 0
    assert truth.n_absent >= 3                      # the d-glide, cancellable
    assert s["cI sqrt2 a0"].n_absent_uncancellable_in_window >= 7
    assert s["cP a0"].n_absent_uncancellable_in_window >= 5
    assert s["cP 2a0"].n_absent_uncancellable_in_window >= 50
    _p, t = _screens(*tet, TET_CELLS)
    assert t["truth tP"].n_absent_uncancellable_in_window == 0
    assert t["oP unresolved split"].n_absent_uncancellable_in_window == 0


def _candidate(system, centring, cell, **over) -> CellCandidate:
    """A hand-built candidate that passes the gate unless ``over`` breaks it."""
    from rietx.indexing.fom import lattice_group

    kw = dict(cell=cell, cell_esd=(1e-4,) * 6, system=system, centring=centring,
              lattice_group=lattice_group(system, centring),
              volume=float(np.prod(cell[:3])), n_indexed=17, n_lines=17,
              fom=[FigureOfMerit(name="indexed_fraction", value=1.0, n_lines=17,
                                 n_possible=15, k_sigma=3.0)],
              bravais=BravaisOpinion(system=system, system_loosest=system,
                                     system_gemmi=system, system_spglib=system),
              found_by=sorted(engine_names()), supercell_checks=[], ambiguity=[])
    kw.update(over)
    return CellCandidate(**kw)


def test_the_absent_caveat_caps_on_the_windowed_count():
    """The caveat reads the windowed uncancellable count and is capping: a
    cell carrying it alone grades ``medium``, never ``low``.  A validation
    written without a screen (no peak list) keeps firing on the plain count,
    capping too."""
    assert "predicted_but_absent" not in INDEX_REFUTING_CAVEATS
    kw = dict(engines_run=sorted(engine_names()), panel_disagrees=False,
              validated=True, search_complete={"cubic": True},
              shift_allowance_assumed=False, checked=True)
    truth_like = LeBailValidation(
        rwp=0.3, gof=2.0, space_group="F m -3 m", n_reflections=15,
        predicted_but_absent=4, predicted_but_absent_uncancellable=0,
        predicted_but_absent_uncancellable_in_window=0, absent_source="line_screen")
    cand = _candidate("cubic", "F", SI_CELLS["truth cF"][2], lebail=truth_like)
    caveats = caveats_for(cand, **kw)
    assert "predicted_but_absent" not in caveats
    assert grade(caveats, cand.found_by, kw["engines_run"]) == "high"
    wrong = truth_like.model_copy(update={
        "predicted_but_absent": 29, "predicted_but_absent_uncancellable": 12,
        "predicted_but_absent_uncancellable_in_window": 12})
    cand = _candidate("cubic", "I", SI_CELLS["cI sqrt2 a0"][2], lebail=wrong)
    caveats = caveats_for(cand, **kw)
    assert caveats == ["predicted_but_absent"]
    assert grade(caveats, cand.found_by, kw["engines_run"]) == "medium"
    legacy = LeBailValidation(rwp=0.4, gof=2.4, space_group="P m -3 m",
                              n_reflections=153, predicted_but_absent=117)
    cand = _candidate("cubic", "P", SI_CELLS["cP 2a0"][2], lebail=legacy)
    caveats = caveats_for(cand, **kw)
    assert caveats == ["predicted_but_absent"]
    assert grade(caveats, cand.found_by, kw["engines_run"]) == "medium"


# ----------------------------------------------------------------------
# the rank member at the resolution
# ----------------------------------------------------------------------
def test_the_reversed_member_is_asked_at_the_resolution(si, tet):
    """P4: with the peak list's widths the panel's ``predicted_seen_fraction``
    reads the hR cell below the truth (0.34 against 0.73 in the record) and
    the resolved split at or below 0.7, where in the search window both read
    *above* the truth — the inversion issue #916 reports, in the member that
    was supposed to prevent it.  The unresolved split reads as the truth.
    """
    def member(peaks, system, centring, cell, *, resolution: bool):
        # the window the record was measured in: the assumed bound, since the
        # width-set search window (indexing C6) is narrower on this list and
        # no longer shows the inversion the build removes
        usable = peaks.usable()
        fwhm = np.array([p.fwhm for p in usable]) if resolution else None
        panel = fom_panel(peaks.q(), peaks.q_esd(), peaks.intensity(),
                          peaks.two_theta(), peaks.two_theta_esd(), cell,
                          system, centring, peaks.wavelength,
                          q_match=absence_window(peaks), fwhm_obs=fwhm)
        return next(f.value for f in panel if f.name == "predicted_seen_fraction")

    peaks = si[2]
    truth = member(peaks, *SI_CELLS["truth cF"], resolution=True)
    hr = member(peaks, *SI_CELLS["hR rank-1 of #916"], resolution=True)
    assert hr < 0.6 * truth, (hr, truth)
    # the window it replaced could not see it: this is what changed
    assert member(peaks, *SI_CELLS["hR rank-1 of #916"], resolution=False) \
        >= member(peaks, *SI_CELLS["truth cF"], resolution=False)
    peaks = tet[2]
    assert member(peaks, *TET_CELLS["oP resolved split"], resolution=True) <= 0.7
    # within one merged line of the truth's (49 of 50 against 50 of 51)
    assert member(peaks, *TET_CELLS["oP unresolved split"], resolution=True) \
        == pytest.approx(member(peaks, *TET_CELLS["truth tP"], resolution=True),
                         abs=0.025)
    assert RESOLUTION_FWHM == 1.0


# ----------------------------------------------------------------------
# the verdict's three bands
# ----------------------------------------------------------------------
def _evidence(k: int, n: int, p0: float, *, k_unexplained: int | None = None,
              index: int = 2) -> SupercellEvidence:
    from scipy.stats import binom

    seen = tuple(i < k for i in range(n))
    alone = seen if k_unexplained is None else tuple(i < k_unexplained for i in range(n))
    p_all = 1.0 if n == 0 else float(binom.sf(k - 1, n, p0))
    p_un = 1.0 if n == 0 else float(binom.sf(sum(alone) - 1, n, p0))
    return SupercellEvidence(index=index, extra_hkl=((1, 0, 0),) * n,
                             extra_q=tuple(0.1 * (i + 1) for i in range(n)),
                             extra_seen=seen, p0=p0, p_value=p_all,
                             extra_seen_unexplained=alone, p_value_unexplained=p_un)


def test_the_verdict_has_three_bands():
    """Refuted means seen **no more often than chance**, with power; supported
    means beyond chance on unexplained lines; everything between is
    undecided.  The middle band is corundum's own cell as a child of its c/2
    subcell at the resolution: 8 of 18 at p₀ = 0.21, p = 0.019 — above chance,
    not significant, and the two-band rule called it refuted."""
    assert _evidence(8, 18, 0.21).verdict() == "undecided"
    assert _evidence(0, 12, 0.02).verdict() == "refuted"
    assert _evidence(1, 33, 0.17).verdict() == "refuted"          # magnetite's rival
    assert _evidence(2, 25, 0.105).verdict() == "refuted"         # brucite's a × 2
    assert 0.01 < _evidence(8, 18, 0.21).p_value < 0.05       # not significant
    assert _evidence(8, 14, 0.21).verdict() == "supported"
    assert _evidence(0, 0, 0.1).verdict() == "undecided"           # no extra
    assert _evidence(0, 2, 0.3).verdict() == "undecided"           # no power


def test_a_child_seen_more_often_than_its_parent_is_never_refuted():
    """#1230: the refuted band needs the child's own lines seen no more often
    than the parent's.  The aP1 truth against the 2 % larger wrong cell that
    ranked above it on ``main`` had 112 of 183 extras seen at p₀ 0.628, which is
    in the refuted band.  Its own seen fraction was 0.625 against the parent's
    0.372, so it reads undecided.  An equal fraction is still refuted, and
    support is untouched."""
    from dataclasses import replace

    truth = replace(_evidence(112, 183, 0.628, index=0), relation="containment")
    assert truth.verdict() == "refuted"          # what main read
    seen = replace(truth, child_seen_fraction=0.625, parent_seen_fraction=0.372)
    assert seen.child_seen_more and seen.verdict() == "undecided"
    tie = replace(truth, child_seen_fraction=0.5, parent_seen_fraction=0.5)
    assert not tie.child_seen_more and tie.verdict() == "refuted"
    assert replace(_evidence(8, 14, 0.21), child_seen_fraction=0.9,
                   parent_seen_fraction=0.1).verdict() == "supported"
    # not measured (the sublattice route) leaves the verdict as it was
    assert not _evidence(0, 12, 0.02).child_seen_more


def test_the_seen_guard_keeps_every_refutation_of_941(si, tet):
    """The positive arm of #1230's guard: every child #941's Acceptance table
    refutes is seen less often than its truth, so each stays refuted.  The Si
    children read 0.08–0.31 against the truth's 0.73, and the tetragonal set's
    resolved split and c × 2 cell read 0.54–0.57 against 1.0."""
    from rietx.indexing.screen import containment_evidence

    for data, cells, truth_name, children in (
            (si, SI_CELLS, "truth cF",
             ("cI sqrt2 a0", "cP a0", "cP 2a0", "hR rank-1 of #916", "tI rank-3 of #916")),
            (tet, TET_CELLS, "truth tP", ("oP resolved split", "tP c x2"))):
        pattern, s = _screens(*data, cells)
        truth = s[truth_name]
        for name in children:
            ev = containment_evidence(pattern, s[name], truth)
            assert ev is not None and not ev.child_seen_more, name
            assert ev.child_seen_fraction < ev.parent_seen_fraction - 0.2, name
            assert ev.verdict() == "refuted", name


#: #1230's dense case, regenerated: a triclinic P -1 cell with six random
#: atoms, Cu Kα1 Bragg-Brentano from 5 to 90°, 291 picked lines.
_AP = ("data_aP\n_cell_length_a 8.90\n_cell_length_b 10.40\n_cell_length_c 12.60\n"
       "_cell_angle_alpha 97.3\n_cell_angle_beta 101.9\n_cell_angle_gamma 106.6\n"
       "_space_group_IT_number 2\n_symmetry_space_group_name_H-M 'P -1'\n"
       "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
       "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_occupancy\n_atom_site_B_iso_or_equiv\n"
       "Ba1 Ba 0.82112 0.62901 0.16214 1.0 0.8\nZr2 Zr 0.25773 0.26863 0.64348 1.0 0.8\n"
       "Fe3 Fe 0.65139 0.00581 0.60516 1.0 0.8\nS4 S 0.87556 0.22759 0.84248 1.0 0.8\n"
       "O5 O 0.49404 0.99393 0.72217 1.0 0.8\nO6 O 0.17744 0.08554 0.79221 1.0 0.8\n")
AP_TRUTH = (8.90, 10.40, 12.60, 97.3, 101.9, 106.6)
#: a monoclinic P cell six times the truth's volume that ranked above it in a
#: ``preset="full"`` search of this pattern on ``main``
AP_RIVAL = (24.82003914, 8.46150771, 31.15817502, 90.0, 100.59625625, 90.0)


@pytest.fixture(scope="module")
def dense_ap():
    from rietx.indexing.engines import DEFAULT_UNKNOWN_SHIFT_DEG
    from rietx.indexing.fom import MATCH_SIGMA
    from rietx.indexing.screen import PatternScreen

    with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as f:
        f.write(_AP)
    try:
        s = rx.Structure.from_cif(f.name)
    finally:
        os.unlink(f.name)
    ins = rx.Instrument.bragg_brentano(radiation="CuKa1")
    # declare the two defaults the margins would otherwise ride on
    ins.source.dispersion = None
    tt = np.round(np.arange(5.0, 90.0 + 1e-9, 0.01), 4)
    was = compiled.set_enabled(False)
    try:
        y = np.asarray(rx.Refinement(s, ins, history=False).predict(tt), float)
    finally:
        compiled.set_enabled(was)
    obs = np.random.default_rng(35).poisson(y / y.max() * 2e4 + 100.0).astype(float)
    data = rx.PatternData(two_theta=tt, intensity=obs, sigma=np.sqrt(np.maximum(obs, 1.0)))
    peaks = pick_peaks(data, ins, two_theta_range=(5.0, 90.0))
    # the run's own screen: the assumed shift bound floors p0 (#951)
    pattern = PatternScreen.from_peaks(peaks, q_match=absence_window(peaks), data=data,
                                       instrument=ins,
                                       p0_floor_deg=MATCH_SIGMA * DEFAULT_UNKNOWN_SHIFT_DEG)
    return peaks, pattern


def test_a_dense_triclinic_truth_is_not_refuted_by_a_cell_six_times_its_volume(dense_ap):
    """#1230, the aP2 kind.  On 291 dense lines the rival's predicted lines
    merge into fewer resolved positions than the truth's, so containment's
    density order makes the **truth** the child of a cell six times its
    primitive volume.  The truth indexes every line the rival does, and p₀ is
    0.64, near the truth's own seen fraction, so its extras sit well inside the
    refuted band: about 130 of 360 seen against n·p₀ ≈ 230.  ``main`` refuted
    it and ranked it below the rival.  The truth's own lines are seen far more
    often than the rival's (0.43 against 0.27), which no oversized
    description can do, so the pair is undecided and the truth stays first.
    """
    from rietx.indexing.ambiguity import SUPERCELL_CHANCE_ALPHA
    from rietx.indexing.consensus import below_refuting_parents, supercell_checks
    from rietx.indexing.screen import (
        _primitive_volume,
        containment_evidence,
        contains,
        screen_candidate,
    )

    peaks, pattern = dense_ap
    assert len(peaks.usable()) > 250
    truth = screen_candidate(pattern, AP_TRUTH, "triclinic", "P")
    rival = screen_candidate(pattern, AP_RIVAL, "monoclinic", "P")
    assert contains(truth, rival) and truth.n_lines > rival.n_lines
    assert _primitive_volume(rival) > 5.0 * _primitive_volume(truth)
    ev = containment_evidence(pattern, truth, rival)
    # main's rule alone would refute it, by a wide margin
    assert ev.p_floor < SUPERCELL_CHANCE_ALPHA
    assert ev.n_seen < 0.75 * ev.n_extra * ev.p0, (ev.n_seen, ev.n_extra, ev.p0)
    assert ev.child_seen_fraction > ev.parent_seen_fraction + 0.1
    assert ev.child_seen_more and ev.verdict() == "undecided"
    # and the order: nothing moves the truth below the rival
    cands = [_candidate("triclinic", "P", AP_TRUTH), _candidate("monoclinic", "P", AP_RIVAL)]
    supercell_checks(cands, peaks, q_match=absence_window(peaks), k_sigma=3.0, screen=pattern)
    (check,) = cands[0].supercell_checks
    assert check.relation == "containment" and check.verdict == "undecided"
    assert below_refuting_parents(cands)[0] is cands[0]


# ----------------------------------------------------------------------
# consensus and validation read the screen
# ----------------------------------------------------------------------
def test_supercell_checks_ask_containment_and_refute_the_root2_cell(si):
    """The consensus check that grades: cubic I √2·a₀ carries a refuting
    check against the truth with ``relation="containment"`` and index 0, so
    ``supercell_refuted`` puts it at ``low``; the truth carries no refuting
    check."""
    from rietx.indexing.consensus import supercell_checks

    peaks = si[2]
    cands = [_candidate(*SI_CELLS["truth cF"]), _candidate(*SI_CELLS["cI sqrt2 a0"]),
             _candidate(*SI_CELLS["cP a0"])]
    supercell_checks(cands, peaks, q_match=match_window(peaks), k_sigma=3.0)
    truth, root2, prim = cands
    assert all(c.verdict != "refuted" for c in truth.supercell_checks)
    (check,) = [c for c in root2.supercell_checks if c.parent_centring == "F"]
    assert check.verdict == "refuted" and check.relation == "containment"
    assert check.index == 0 and check.n_seen == 0 and check.n_extra >= 10
    assert check.absent_two_theta and all(LIM[0] < t < LIM[1]
                                          for t in check.absent_two_theta)
    (check,) = [c for c in prim.supercell_checks if c.parent_centring == "F"]
    assert check.verdict == "refuted" and check.relation == "sublattice"
    assert check.index == 4
    kw = dict(engines_run=sorted(engine_names()), panel_disagrees=False,
              validated=False, search_complete={"cubic": True},
              shift_allowance_assumed=False, checked=True)
    assert "supercell_refuted" in caveats_for(root2, **kw)
    assert grade(caveats_for(root2, **kw), root2.found_by, kw["engines_run"]) == "low"


@pytest.mark.slow
def test_validation_reads_the_screen_and_freezes_the_profile(si):
    """S1: ``validate_by_lebail`` with a peak list reports the screen's counts
    (``absent_source="line_screen"``), the truth at 0 in the window and the
    doubled cell at most of its lines; without a peak list the
    fitted-background detector is what an older caller gets.  The plan keeps
    its four stages either way, and drops the two width stages only on
    ``freeze_profile=True`` (off by default, measured in ``validation_plan``)."""
    from rietx.indexing.workflow import validate_by_lebail, validation_plan

    data, ins, peaks = si
    truth = _candidate(*SI_CELLS["truth cF"])
    v = validate_by_lebail(truth, data, ins, peaks=peaks)
    assert v.status == "converged" and v.absent_source == "line_screen"
    assert v.predicted_but_absent_uncancellable_in_window == 0
    assert v.predicted_but_absent_uncancellable == 0
    assert v.predicted_but_absent >= 3 and len(v.predicted_but_absent_two_theta) \
        == v.predicted_but_absent
    assert v.n_stages == 4
    frozen = validate_by_lebail(truth, data, ins, peaks=peaks, freeze_profile=True)
    assert frozen.n_stages == 2 and frozen.predicted_but_absent == v.predicted_but_absent
    doubled = validate_by_lebail(_candidate(*SI_CELLS["cP 2a0"]), data, ins, peaks=peaks)
    assert doubled.predicted_but_absent_uncancellable_in_window >= 50
    # the screen's share is of merged lines, not of the fit's reflections
    assert doubled.n_lines_screened is not None
    assert doubled.predicted_but_absent > 0.5 * doubled.n_lines_screened
    assert doubled.n_lines_screened < doubled.n_reflections
    assert v.n_lines_screened == 15
    # the density: the windowed count over the window's screened lines
    assert v.predicted_but_absent_density_in_window == 0.0
    assert 0 < doubled.n_lines_screened_in_window <= doubled.n_lines_screened
    assert doubled.predicted_but_absent_density_in_window == pytest.approx(
        doubled.predicted_but_absent_uncancellable_in_window
        / doubled.n_lines_screened_in_window)
    legacy = validate_by_lebail(truth, data, ins)
    assert legacy.absent_source == "fitted_background"
    assert legacy.predicted_but_absent_uncancellable_in_window is None
    assert legacy.n_stages == 4
    assert [s.name for s in validation_plan(truth, ins, 60.0, freeze_profile=True).stages] \
        == ["bkg", "shift"]


def test_a_direct_validation_screens_the_fitted_range_and_the_search_window(si, monkeypatch):
    """A direct ``validate_by_lebail`` call builds its own screen: over the
    call's ``two_theta_limits`` (lines the fit never covered are not absent) and
    with the search's matching window, not each line's own σ."""
    from rietx.indexing import screen as screen_mod
    from rietx.indexing.workflow import validate_by_lebail

    data, ins, peaks = si
    seen = {}
    real = screen_mod.PatternScreen.from_peaks.__func__

    def spy(cls, *a, **kw):
        out = real(cls, *a, **kw)
        seen["screen"] = out
        return out

    monkeypatch.setattr(screen_mod.PatternScreen, "from_peaks", classmethod(spy))
    truth = _candidate(*SI_CELLS["truth cF"])
    full = validate_by_lebail(truth, data, ins, peaks=peaks)
    assert full.n_lines_screened == 15
    limits = (LIM[0], 30.0)
    cut = validate_by_lebail(truth, data, ins, peaks=peaks, two_theta_limits=limits)
    assert cut.absent_source == "line_screen"
    assert cut.n_lines_screened < full.n_lines_screened
    assert all(t <= limits[1] for t in cut.predicted_but_absent_two_theta)
    pattern = seen["screen"]
    assert pattern.two_theta_max == limits[1]
    assert np.allclose(pattern.q_match, absence_window(peaks))
    assert not np.allclose(pattern.q_match, peaks.q_esd())


def test_the_screens_pseudo_voigt_is_the_models():
    from rietx.indexing.screen import _pseudo_voigt
    from rietx.model.profiles.pseudovoigt import pseudo_voigt

    x = np.linspace(-0.5, 0.5, 41)
    for eta in (0.0, 0.4, 1.0):
        assert np.allclose(_pseudo_voigt(x, 0.05, eta), pseudo_voigt(x, 0.05, eta),
                           rtol=1e-12, atol=0.0)


# ----------------------------------------------------------------------
# #941's round-1 follow-ups
# ----------------------------------------------------------------------
def test_the_panel_and_the_screen_share_one_definition_of_seen(tet):
    """Given the screen's positions and common shift, the panel's member reads
    the screen's seen fraction, on every control cell; and both read the width
    law at the **shifted** merged line.  Where the widths change fast across a
    shift, the old reading (the unshifted group's mean width) called a line
    unseen that the screen saw."""
    from rietx.indexing.fom import (
        LINE_COINCIDENCE_RTOL,
        lattice_reflections,
        predicted_seen_fraction_at_resolution,
        two_theta_of_q,
    )

    data, ins, peaks = tet
    pattern, screens = _screens(data, ins, peaks, TET_CELLS)
    for name, (system, centring, cell) in TET_CELLS.items():
        s = screens[name]
        _h, q, _m = lattice_reflections(cell, system, centring, pattern.wavelength,
                                        pattern.two_theta_max,
                                        two_theta_min=pattern.two_theta_min)
        keep = np.ones(len(q), dtype=bool)
        keep[1:] = np.diff(q) > LINE_COINCIDENCE_RTOL * q[1:]
        tt = two_theta_of_q(q[keep], pattern.wavelength)
        member = predicted_seen_fraction_at_resolution(
            pattern.obs_tt, pattern.obs_esd, pattern.obs_fwhm, tt,
            shift=s.shift_deg, k_sigma=pattern.k_sigma)
        assert member.value == pytest.approx(s.seen_fraction, abs=1e-12), name
        assert member.n_possible == s.n_lines, name
    # widths 0.02° at 30° and 0.20° at 31°; one line predicted at 30.5° and
    # shifted +0.33° to 30.83°, 0.17° from the 31° component: at the shifted
    # line the law reads 0.169° and the half-width 0.185° (seen); the
    # unshifted 0.11° gave 0.155° (unseen)
    obs = np.array([30.0, 31.0])
    member = predicted_seen_fraction_at_resolution(
        obs, np.full(2, 1e-4), np.array([0.02, 0.20]), np.array([30.5]),
        shift=0.33)
    assert member.value == 1.0


def test_absences_are_paired_with_their_lines_by_index():
    """``absent_mask`` answers per position in the order given (the root
    rulebook's tick rule: a position is not a key); a position in a gap of the
    scan is not absent, its ratio NaN; ``absent_reflections`` is its selection."""
    from rietx.indexing.workflow import absent_mask, absent_reflections

    tt = np.concatenate([np.arange(20.0, 30.0, 0.01), np.arange(40.0, 50.0, 0.01)])
    y = np.full(len(tt), 100.0)
    y[np.abs(tt - 25.0) < 0.05] += 400.0
    bkg = np.full(len(tt), 100.0)
    sigma = np.full(len(tt), 10.0)
    pos = np.array([25.0, 27.0, 35.0, 27.0, 45.0])
    bad, ratio = absent_mask(tt, y, bkg, sigma, pos, np.full(len(pos), 0.05))
    assert bad.tolist() == [False, True, False, True, True]
    assert np.isnan(ratio[2]) and not np.isnan(ratio).any(where=bad)
    listed, ratios = absent_reflections(tt, y, bkg, sigma, pos, np.full(len(pos), 0.05))
    assert listed == [27.0, 27.0, 45.0]
    assert ratios == pytest.approx(list(ratio[bad]))


def test_a_candidate_is_screened_once_per_run_and_the_refuter_skips_the_grid(
        si, monkeypatch):
    """``supercell_checks`` reads only seen / indexed / uncancellable, so it
    asks no absence question of the pattern; the validation's request for the
    absences then recomputes once, and every later request is the memo's."""
    from rietx.indexing import workflow
    from rietx.indexing.consensus import supercell_checks
    from rietx.indexing.screen import PatternScreen, screen_for

    data, ins, peaks = si
    pattern = PatternScreen.from_peaks(peaks, q_match=absence_window(peaks),
                                       data=data, instrument=ins)
    calls = []
    real = workflow.absent_mask

    def spy(*a, **kw):
        calls.append(1)
        return real(*a, **kw)

    monkeypatch.setattr(workflow, "absent_mask", spy)
    cands = [_candidate(*SI_CELLS[n]) for n in ("truth cF", "cI sqrt2 a0", "cP 2a0")]
    supercell_checks(cands, peaks, q_match=absence_window(peaks), k_sigma=3.0,
                     screen=pattern)
    supercell_checks(cands, peaks, q_match=absence_window(peaks), k_sigma=3.0,
                     screen=pattern)
    assert calls == []
    assert len(pattern._memo) == 3
    full = screen_for(pattern, cands[1], peaks)
    assert full.absent is not None and len(calls) == 1
    assert screen_for(pattern, cands[1], peaks) is full
    assert screen_for(pattern, cands[1], peaks, absence=False) is full
    assert len(calls) == 1
    assert any(k.verdict == "refuted" for k in cands[1].supercell_checks)


def test_the_absent_code_reads_the_counts_not_the_caveat():
    """INDEX_PREDICTED_BUT_ABSENT fires from the validation's counts: before
    the gate has run (no caveats yet), at warning inside de Wolff's window;
    at info, capping nothing, when every uncancellable absence is above it;
    silent at zero and on a failed or diverged fit."""
    from rietx.indexing.diagnostics import candidate_diagnostics

    def code(lebail):
        cand = _candidate("cubic", "F", SI_CELLS["truth cF"][2], lebail=lebail)
        assert cand.confidence_caveats == []
        found = [d for d in candidate_diagnostics(cand)
                 if d.code == "INDEX_PREDICTED_BUT_ABSENT"]
        return found[0] if found else None

    base = LeBailValidation(
        rwp=0.3, gof=2.0, space_group="F m -3 m", n_reflections=15,
        predicted_but_absent=6, predicted_but_absent_uncancellable=2,
        predicted_but_absent_uncancellable_in_window=2, absent_source="line_screen",
        predicted_but_absent_two_theta=[40.1, 49.7])
    assert code(base).level == "warning"
    above = base.model_copy(update={"predicted_but_absent_uncancellable_in_window": 0})
    d = code(above)
    assert d.level == "info" and "caps nothing" in d.message
    assert code(above.model_copy(update={"predicted_but_absent_uncancellable": 0})) is None
    assert code(base.model_copy(update={"status": "failed"})) is None
    # a diverged fit is unread too, as consensus.caveats_for reads it
    assert code(base.model_copy(update={"status": "diverged"})) is None


def test_the_excess_reads_the_density_against_the_cleanest_candidate():
    """The windowed count compared across candidates (#941's follow-up),
    on the counts the acceptance sweep measured: magnetite's true F cell and
    its P rival (2 of 36 window lines, 28 of 88), and the synthetic LaB₆ run's
    truth and a√2 I cell (0 of 19, 2 of 20).  The raw count reads 2 for the
    true F cell and for the wrong I cell alike; the excess reads 0 and 2."""
    from rietx.indexing.consensus import absence_excess

    def screened(system, centring, cell, a, n):
        lebail = LeBailValidation(
            rwp=0.3, gof=2.0, space_group="P 1", n_reflections=n,
            predicted_but_absent=a, predicted_but_absent_uncancellable=a,
            predicted_but_absent_uncancellable_in_window=a,
            absent_source="line_screen", n_lines_screened=n,
            n_lines_screened_in_window=n,
            predicted_but_absent_density_in_window=a / n)
        return _candidate(system, centring, cell, lebail=lebail)

    a_m = (8.3913,) * 3 + (90.0, 90.0, 90.0)
    truth, rival = screened("cubic", "F", a_m, 2, 36), screened("cubic", "P", a_m, 28, 88)
    absence_excess([truth, rival])
    assert truth.lebail.predicted_but_absent_excess_in_window == 0.0
    assert rival.lebail.predicted_but_absent_excess_in_window == pytest.approx(
        28 - 88 * 2 / 36)
    a_l = (4.1568,) * 3 + (90.0, 90.0, 90.0)
    a_i = (4.1568 * R2,) * 3 + (90.0, 90.0, 90.0)
    lab6, root2 = screened("cubic", "P", a_l, 0, 19), screened("cubic", "I", a_i, 2, 20)
    unscreened = _candidate("cubic", "P", a_l)
    absence_excess([lab6, root2, unscreened])
    assert lab6.lebail.predicted_but_absent_excess_in_window == 0.0
    assert root2.lebail.predicted_but_absent_excess_in_window == 2.0
    assert unscreened.lebail is None
    # a lone candidate is its own cleanest: the excess cannot stand in for the cap
    alone = screened("cubic", "I", a_i, 2, 20)
    absence_excess([alone])
    assert alone.lebail.predicted_but_absent_excess_in_window == 0.0
