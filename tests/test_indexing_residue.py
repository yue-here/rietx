"""The second pass on the residue (WP-1969, issue #933): ``index_residue``.

Interpretation, written before the runs:

==============================  ==========================================  ===========================
arm                             expected                                    if not
==============================  ==========================================  ===========================
synthetic Si + MgO (0.3 scale)  the second result ranks cF 4.2112 first,    the pass cannot find a
                                carries no cell of the Si lattice, and      second phase: the feature
                                the first result is untouched               does not work
synthetic Si alone              no candidate, ``INDEX_DATA_INSUFFICIENT``   misfit or picker junk is
                                                                            reported as a phase
SRM 660c LaB6 (real), cubic     no candidate                                the same, on real data
Si with its cell stretched 1 %  nothing picked (width-law guard), no        a residue of a cell that
                                candidate                                   does not fit is read
a first result with no cell     ``ValueError`` naming ``candidate=``        —
==============================  ==========================================  ===========================

The two phases are public structures (Si F d -3 m, a = 5.4311 Å; MgO F m -3 m,
a = 4.2112 Å) on a synthetic pattern, so every number here may be quoted.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

import rietx as rx
from rietx.indexing import index_pattern, index_residue
from rietx.indexing.engines import SearchSpec
from rietx.indexing.qspace import af_from_cell
from rietx.indexing.reduce import same_lattice

LAM, LIMITS = 0.825739, (10.0, 80.0)
SI_A, MGO_A = 5.4311, 4.2112

_CIF = ("data_{name}\n_cell_length_a {a}\n_cell_length_b {a}\n_cell_length_c {a}\n"
        "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
        "_space_group_IT_number {number}\n_symmetry_space_group_name_H-M '{symbol}'\n"
        "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
        "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n{atoms}")
SI_CIF = _CIF.format(name="Si", a=SI_A, number=227, symbol="F d -3 m",
                     atoms="Si1 Si 0.125 0.125 0.125 0.5\n")
MGO_CIF = _CIF.format(name="MgO", a=MGO_A, number=225, symbol="F m -3 m",
                      atoms="Mg1 Mg 0 0 0 0.3\nO1 O 0.5 0.5 0.5 0.4\n")


def _phase(cif: str):
    with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as f:
        f.write(cif)
    try:
        return rx.Structure.from_cif(f.name).phases[0]
    finally:
        os.unlink(f.name)


def _pattern(mgo_scale: float | None, seed: int = 1):
    """Si, and MgO at ``mgo_scale`` of its scale, on a synchrotron-width
    Debye-Scherrer pattern with Poisson noise over a flat background."""
    phases = [_phase(SI_CIF)]
    if mgo_scale is not None:
        mgo = _phase(MGO_CIF)
        mgo.scale.value = phases[0].scale.value * mgo_scale
        phases.append(mgo)
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    tt = np.round(np.arange(LIMITS[0] - 0.2, LIMITS[1] + 0.2, 0.004), 3)
    y = rx.Refinement(rx.Structure(phases=phases), ins, history=False).predict(
        two_theta=tt)
    obs = np.random.default_rng(seed).poisson(y / y.max() * 1.0e6 + 5000.0)
    obs = obs.astype(float)
    data = rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1.0))))
    return ins, data


def _passes(mgo_scale: float | None):
    ins, data = _pattern(mgo_scale)
    spec = SearchSpec(systems=("cubic",), budget_seconds=60.0)
    first = index_pattern(data=data, instrument=ins, two_theta_limits=LIMITS,
                          spec=spec, preset="full")
    before = first.model_dump(mode="json")
    second = index_residue(first, data, ins, two_theta_limits=LIMITS,
                           spec=spec, preset="full")
    assert first.model_dump(mode="json") == before     # never changes `first`
    return first, second


def _is(cand, a: float) -> bool:
    return same_lattice(np.asarray(cand.af),
                        af_from_cell((a, a, a, 90.0, 90.0, 90.0)))[0] \
        and cand.centring == "F"


def test_a_result_with_no_cell_has_nothing_to_subtract():
    from rietx import IndexingResult
    from rietx.schemas.common import Provenance

    ins, data = _pattern(None)
    empty = IndexingResult(provenance=Provenance(package_version="t"))
    with pytest.raises(ValueError, match="candidate="):
        index_residue(empty, data, ins)


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-residue")
def test_the_second_phase_is_indexed_from_what_the_first_cell_leaves():
    """Positive arm: MgO at 0.3 of the Si scale.  The first pass ranks Si's
    cell first (graded down by the MgO lines, which is why the default first
    cell is rank 1 at any grade); its residue gives MgO's cell back first."""
    from tests.test_acceptance_indexing import _skip_unless_finished

    first, second = _passes(0.3)
    _skip_unless_finished(first, second)       # the rank below reads the order
    assert _is(first.candidates[0], SI_A), first.candidates[0].cell
    assert second.diagnostics[0].code == "INDEX_RESIDUE_PASS"
    assert second.candidates, [d.code for d in second.diagnostics]
    # the misfit lines are flagged, not dropped (they are scored, so they sit
    # in M20's first twenty lines and the √2·a₀ cI sibling can rank above the
    # truth): the truth is in the top two, and no candidate is the Si cell
    assert any(_is(c, MGO_A) for c in second.candidates[:2]), \
        [c.cell[0] for c in second.candidates]
    assert not any(_is(c, SI_A) for c in second.candidates)
    note = second.diagnostics[0]
    assert note.where and "flagged residue_misfit" in note.message


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-residue")
def test_a_single_phase_pattern_leaves_no_second_result():
    """Negative arm: Si alone leaves nothing the picker keeps once the misfit
    standing on Si's own profile is dropped, so the second result abstains."""
    first, second = _passes(None)
    assert _is(first.candidates[0], SI_A)
    assert not second.candidates
    assert second.n_usable_lines == 0
    codes = [d.code for d in second.diagnostics]
    assert codes[0] == "INDEX_RESIDUE_PASS"
    assert "INDEX_DATA_INSUFFICIENT" in codes


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-residue")
def test_the_certified_lab6_pattern_leaves_no_second_result():
    """Negative arm on real data: SRM 660c, searched cubic as the acceptance
    rows search it.  Its residue is the first fit's misfit and nothing else."""
    from rietx.indexing.pick import pick_peaks
    from tests.test_acceptance_indexing import (
        REAL_DATA_BUDGET_SECONDS,
        _lab6_inputs,
    )

    data, ins = _lab6_inputs()
    spec = SearchSpec(systems=("cubic",), max_volume=300.0,
                      budget_seconds=REAL_DATA_BUDGET_SECONDS)
    first = index_pattern(pick_peaks(data, ins), data=data, instrument=ins,
                          spec=spec, preset="full")
    second = index_residue(first, data, ins, spec=spec, preset="full")
    assert not second.candidates, [(c.system, c.cell) for c in second.candidates]
    assert second.diagnostics[0].code == "INDEX_RESIDUE_PASS"


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-residue")
def test_a_cell_that_does_not_fit_the_pattern_leaves_no_residue():
    """The width-law guard: Si's own cell stretched by 1 % misplaces every
    line, its Le Bail fit buys the misfit with widths far past the list's, and
    nothing is picked.  Without the guard the picker ran at those widths (145 s
    on #933's reproducer, whose first cell is a wrong cubic I one)."""
    ins, data = _pattern(None)
    spec = SearchSpec(systems=("cubic",), budget_seconds=60.0)
    first = index_pattern(data=data, instrument=ins, two_theta_limits=LIMITS,
                          spec=spec, preset="full")
    a = first.candidates[0].cell[0] * 1.01
    wrong = first.candidates[0].model_copy(
        update={"cell": (a, a, a, 90.0, 90.0, 90.0)})
    second = index_residue(first, data, ins, candidate=wrong,
                           two_theta_limits=LIMITS, spec=spec, preset="full")
    assert not second.candidates
    note = second.diagnostics[0]
    assert note.code == "INDEX_RESIDUE_PASS"
    assert note.message.startswith("No residue was picked"), note.message


def _structure_and_peaks():
    ins, data = _pattern(None)
    from rietx.indexing.pick import pick_peaks
    return ins, data, pick_peaks(data, ins, two_theta_range=LIMITS)


def test_a_setup_error_raises_where_a_fit_error_is_a_refuted_candidate(monkeypatch):
    """The setup is outside the guard: a bug in it raises (as on main), and only
    the fit's own failure becomes ``INDEX_VALIDATION_FAILED``."""
    from rietx.indexing import validate_by_lebail, workflow

    ins, data, peaks = _structure_and_peaks()
    cell = (SI_A,) * 3 + (90.0,) * 3
    from rietx.schemas.indexing import CellCandidate
    cand = CellCandidate(system="cubic", centring="F", cell=cell,
                         af=list(af_from_cell(cell)), cell_esd=(0.0,) * 6,
                         volume=SI_A ** 3, volume_esd=0.0)

    def boom(*a, **k):
        raise RuntimeError("setup bug")

    monkeypatch.setattr(workflow, "validation_plan", boom)
    with pytest.raises(RuntimeError, match="setup bug"):
        validate_by_lebail(cand, data, ins, peaks=peaks)
    monkeypatch.undo()
    monkeypatch.setattr(workflow, "_lebail_fit", boom)
    out = validate_by_lebail(cand, data, ins, peaks=peaks)
    assert out.status == "failed"
    assert out.diagnostics[0].code == "INDEX_VALIDATION_FAILED"


@pytest.mark.slow
@pytest.mark.xdist_group("indexing-residue")
def test_assumed_widths_neither_seed_nor_refuse_the_pass():
    """A ``from_positions`` list carries one assumed 0.1° width on every line;
    against synchrotron lines near 0.01° the width-ratio test refused Si's own,
    correct cell.  Skipped, and said so."""
    from rietx.schemas.indexing import PeakList

    ins, data, peaks = _structure_and_peaks()
    spec = SearchSpec(systems=("cubic",), budget_seconds=60.0)
    first = index_pattern(peaks, data=data, instrument=ins,
                          two_theta_limits=LIMITS, spec=spec, preset="full")
    handed = PeakList.from_positions(
        np.array([p.two_theta for p in peaks.usable()]), LAM)
    assert handed.source == "positions"
    second = index_residue(first, data, ins, peaks=handed,
                           two_theta_limits=LIMITS, spec=spec, preset="full")
    note = second.diagnostics[0]
    assert note.code == "INDEX_RESIDUE_PASS"
    assert not note.message.startswith("No residue was picked"), note.message
    assert "assumed" in note.message
