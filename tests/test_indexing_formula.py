"""WP-1510 — what the chemist knows reaches the search: a formula's volume.

Three things are pinned.  A formula-unit volume is Hofmann's (2002) sum of
average atomic volumes, with its esd.  ``SearchSpec.from_formula`` turns it
into a volume window the caller declares.  And ``index_pattern(formula=...)``
reports a candidate whose volume holds a fractional number of formula units,
without removing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rietx.crystallography.atomic_volume import (
    HOFMANN_VOLUMES,
    VOLUME_RATIO_BOUNDS,
    formula_unit_volume,
)
from rietx.indexing import index_pattern
from rietx.indexing.diagnostics import Z_INTEGER_TOLERANCE, candidate_diagnostics
from rietx.indexing.engines import DEFAULT_MIN_VOLUME, SearchSpec
from rietx.schemas.indexing import CellCandidate
from tests.test_indexing_engines import synthetic_peaks

#: Benzoic acid, C7H6O2, from Hofmann's Table 2 at 298 K:
#: 7 × 13.87 + 6 × 5.08 + 2 × 11.39 Å³, and eq. (13)'s esd
#: 7 × 0.05 + 6 × 0.04 + 2 × 0.17 Å³.
BENZOIC = "C7H6O2"
BENZOIC_V = 150.35
BENZOIC_ESD = 0.93


def test_a_formula_unit_volume_is_hofmanns_sum_with_its_esd():
    volume, esd = formula_unit_volume(BENZOIC)
    assert volume == pytest.approx(BENZOIC_V, abs=1e-9)
    assert esd == pytest.approx(BENZOIC_ESD, abs=1e-9)
    # a CIF _chemical_formula_sum reads the same
    assert formula_unit_volume("C7 H6 O2") == (volume, esd)
    # eq. (1): (1 + ᾱT)/(1 + ᾱ·298 K) with ᾱ = 0.95e-4 K⁻¹, so 1.8 % smaller
    # at 100 K, and the expansion term now adds to the esd
    cold, cold_esd = formula_unit_volume(BENZOIC, temperature=100.0)
    assert cold == pytest.approx(BENZOIC_V * (1 + 0.95e-2) / (1 + 0.95e-4 * 298))
    assert cold_esd > BENZOIC_ESD * cold / BENZOIC_V
    # Kempster & Lipson's rule puts 18 Å³ on each non-hydrogen atom, and the
    # table lands near it
    assert 15.0 < volume / 9 < 18.0


def test_an_element_with_no_mean_error_has_no_esd():
    assert HOFMANN_VOLUMES["Am"] == (17.0, None)
    volume, esd = formula_unit_volume("AcCl3")
    assert volume == pytest.approx(74.0 + 3 * 25.8)
    assert esd is None


@pytest.mark.parametrize("formula,expected", [
    ("CH3CH2OH", {"C": 2, "H": 6, "O": 1}),
    ("Cu(C2H3O2)2", {"Cu": 1, "C": 4, "H": 6, "O": 4}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
])
def test_brackets_and_adducts_count(formula, expected):
    volume, _ = formula_unit_volume(formula)
    assert volume == pytest.approx(
        sum(n * HOFMANN_VOLUMES[el][0] for el, n in expected.items()))


@pytest.mark.parametrize("formula,named", [
    ("He", "no average volume for He"),
    ("Xx2", "'Xx' is not an element"),
    ("C(H2", "never closed"),
    ("", "empty part"),
])
def test_a_formula_the_table_cannot_read_raises_naming_why(formula, named):
    with pytest.raises(ValueError, match=named):
        formula_unit_volume(formula)


def test_the_window_holds_z_units_widened_to_hofmanns_bounds():
    low, high = VOLUME_RATIO_BOUNDS
    assert (low, high) == (0.8, 1.25)
    spec = SearchSpec.from_formula(BENZOIC, z=4, max_d_axis=32.0)
    assert spec.min_volume == pytest.approx(4 * BENZOIC_V * 0.8)
    assert spec.max_volume == pytest.approx(4 * BENZOIC_V * 1.25)
    assert spec.max_d_axis == 32.0
    ranged = SearchSpec.from_formula(BENZOIC, z=(2, 8))
    assert (ranged.min_volume, ranged.max_volume) == pytest.approx(
        (2 * BENZOIC_V * 0.8, 8 * BENZOIC_V * 1.25))
    # no Z: the floor of one formula unit, and the envelope keeps the ceiling
    floor_only = SearchSpec.from_formula(BENZOIC)
    assert floor_only.min_volume == pytest.approx(BENZOIC_V * 0.8)
    assert floor_only.max_volume is None
    # two lower bounds, the larger binds
    assert SearchSpec.from_formula("H2").min_volume == DEFAULT_MIN_VOLUME


@pytest.mark.parametrize("z", [0, (4, 2), 2.5])
def test_a_z_that_is_not_a_whole_count_raises(z):
    with pytest.raises(ValueError, match="whole number"):
        SearchSpec.from_formula(BENZOIC, z=z)


def _candidate(volume: float) -> CellCandidate:
    a = volume ** (1.0 / 3.0)
    return CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(0.0,) * 6,
                         system="cubic", volume=volume)


def _z_checks(volume: float, formula: str | None = BENZOIC):
    return [d for d in candidate_diagnostics(_candidate(volume), formula=formula)
            if d.code == "INDEX_Z_NOT_INTEGER"]


@pytest.mark.parametrize("z", [8 / 3, 2.5, 0.6])
def test_the_z_check_fires_on_a_fractional_cell(z):
    (diag,) = _z_checks(z * BENZOIC_V)
    assert diag.level == "warning"
    assert diag.value == pytest.approx(z)
    assert f"{z:.2f} formula units of {BENZOIC}" in diag.message
    assert f"formula {BENZOIC}" in diag.where


@pytest.mark.parametrize("z", [4.0, 4.0 * 1.07, 2.8])
def test_the_z_check_is_silent_within_twice_the_scatter(z):
    # 2.8 sits 6.7 % from 3, inside the 8 % that twice Hofmann's 4.00 %
    # scatter of one crystal allows, so it is not evidence of a fractional Z
    assert Z_INTEGER_TOLERANCE == pytest.approx(0.08)
    assert _z_checks(z * BENZOIC_V) == []


def test_no_formula_no_z_check():
    assert _z_checks(2.5 * BENZOIC_V, formula=None) == []


def test_index_pattern_reports_the_z_and_keeps_the_candidate():
    # methanol's 45.58 Å³ against the synthetic cubic cell's 71.8 Å³: Z = 1.58,
    # 21 % from 2, so the true cell is reported and still ranked
    peaks, true_cell = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, shift_allowance_deg=1e-9)
    res = index_pattern(peaks, spec=spec, preset="full",
                        engines=("trial_error",), formula="CH3OH")
    truth = next(c for c in res.candidates
                 if c.cell[0] == pytest.approx(true_cell[0], rel=1e-3))
    (diag,) = [d for d in truth.diagnostics if d.code == "INDEX_Z_NOT_INTEGER"]
    v_fu, _ = formula_unit_volume("CH3OH")
    assert diag.value == pytest.approx(truth.volume / v_fu)


def test_index_pattern_refuses_a_bad_formula_before_any_work():
    peaks, _ = synthetic_peaks("cubic")
    with pytest.raises(ValueError, match="not an element"):
        index_pattern(peaks, formula="Qq2")


# ----------------------------------------------------------------------
# WP-2030: the window and the Z check against known cells, measured
# ----------------------------------------------------------------------
def _volume(a, b, c, al=90.0, be=90.0, ga=90.0):
    import math

    ca, cb, cg = (math.cos(math.radians(x)) for x in (al, be, ga))
    return a * b * c * math.sqrt(1 - ca * ca - cb * cb - cg * cg + 2 * ca * cb * cg)


_DATA = Path(__file__).parent / "data"
#: NIST certifies SRM 640c's and SRM 676a's cells at 22.5 °C
#: (``tests/data/README.md``, both certificates).
_NIST_CERTIFIED_K = 273.15 + 22.5


def _gallery(key: str) -> float:
    """The volume of a cell in ``tests/indexing_gallery.TRUTHS``, the tree's
    one copy of the round-robin and standards cells: imported, not retyped."""
    from tests.indexing_gallery import TRUTHS

    return _volume(*TRUTHS[key][0])


def _si640c() -> float:
    from tests.test_acceptance_si640c import A_CERT

    return _volume(A_CERT, A_CERT, A_CERT)


def _cif(name: str) -> tuple[int, float, float]:
    """(Z, V, T) as a vendored COD CIF states them: ``_cell_formula_units_Z``,
    ``_cell_volume`` and the cell's measurement temperature (the
    diffraction temperature where the file gives no other), else 298 K."""
    import re

    text = (_DATA / name).read_text(encoding="utf-8")

    def item(tag):
        m = re.search(rf"^{tag}\s+'?([-0-9.]+)", text, re.M)
        return None if m is None else float(m.group(1))

    t = item("_cell_measurement_temperature") or item("_diffrn_ambient_temperature")
    return int(item("_cell_formula_units_Z")), item("_cell_volume"), t or 298.0


#: Known cells, each with its source: ``(formula, Z, V_true Å³, T K, organic)``.
#: The inorganic rows are every inorganic standard in ``tests/data/`` with a
#: certified, published or cross-code cell (``tests/data/README.md`` and
#: ``tests/indexing_gallery.py`` name each), plus halite.  The organic and
#: metal-organic rows are the published cells in ``tests/data/`` and one more.
#: Each value is read from where the tree already holds it, the gallery, the
#: SRM 640c test or a vendored CIF, never retyped.  T is the cell's own
#: temperature where its source states one, else 298 K.
KNOWN_CELLS: dict[str, tuple[str, int, float, float, bool]] = {
    # NIST SRM 660c certificate, nist_srm660c_100a.cif's _meas block, at 20.85 °C
    "LaB6": ("LaB6", 1, _gallery("lab6"), 294.0, False),
    # NIST SRM 640c certificate, a = 5.4311946 Å at 22.5 °C
    "Si": ("Si", 8, _si640c(), _NIST_CERTIFIED_K, False),
    # NIST SRM 676a certificate, a = 4.759355, c = 12.99231 Å at 22.5 °C
    "corundum": ("Al2O3", 6, _gallery("corundum"), _NIST_CERTIFIED_K, False),
    # 11-BM NAC's cell (gallery); Z from COD 1000236 (cod_1000236.cif,
    # Courbion & Férey 1988, J. Solid State Chem.)
    "NAC": ("Na2Ca3Al2F14", _cif("cod_1000236.cif")[0], _gallery("nac"), 298.0, False),
    # GSAS's converged cell in FAP.EXP (cross-code)
    "fluorapatite": ("Ca5P3O12F", 2, _gallery("fap"), 298.0, False),
    # the IUCr CPD round robin's literature cells (indexing_gallery.SPECIMENS)
    "zincite": ("ZnO", 2, _gallery("zincite"), 298.0, False),
    "zircon": ("ZrSiO4", 4, _gallery("zircon"), 298.0, False),
    "brucite": ("Mg(OH)2", 1, _gallery("brucite"), 298.0, False),
    "magnetite": ("Fe3O4", 8, _gallery("magnetite"), 298.0, False),
    "fluorite": ("CaF2", 4, _gallery("fluorite"), 298.0, False),
    # COD 9003308 (cod_9003308.cif): Walker et al. (2004), Am. Mineral. 89,
    # 204, a = 5.6401 Å at 25 °C
    "halite": ("NaCl", *_cif("cod_9003308.cif"), False),
    # cubic BN in 11BM_LaB6_cBN_mg2044: TOPAS's cell (test_acceptance_lab6_cbn.py)
    "cBN": ("BN", 4, _volume(3.616463, 3.616463, 3.616463), 295.0, False),
    # GSAS-II's converged cells in the vendored tutorial projects
    "anglesite": ("PbSO4", 4, _volume(8.480443, 5.398619, 6.960131), 298.0, False),
    "hausmannite": ("Mn3O4", 4, _volume(5.763447, 5.763447, 9.452202), 10.0, False),
    "LCMO": ("La0.8Ca0.2MnO3", 4, _volume(5.482827, 5.466795, 7.724880), 50.0, False),
    # COD 9007744 (cod_9007744.cif, Acta Cryst. C 1990), which states no
    # temperature
    "YBCO": ("Ba2 Cu2.941 O6.822 Y", *_cif("cod_9007744.cif"), False),
    # COD 2104364 (cod_2104364.cif) at 100 K
    "paracetamol": ("C8H9NO2", *_cif("cod_2104364.cif"), True),
    # COD 7252065 (cod_7252065.cif) at 298 K: Rajput & Dalvi (2026),
    # CrystEngComm, doi:10.1039/D6CE00164E
    "benzoic acid": ("C7H6O2", *_cif("cod_7252065.cif"), True),
    # Bergmann, Le Bail, Shirley & Zlokazov (2004), Z. Kristallogr. 219, 783
    "bethanechol chloride": ("C7H17ClN2O2", 4,
                             _volume(8.875, 16.408, 7.137, 90.0, 93.84, 90.0), 298.0, True),
    # COD 4002052 (cod_4002052.cif) at 273 K: HKUST-1, a porous framework
    # written without its pore contents
    "HKUST-1": ("C18H6Cu3O12", *_cif("cod_4002052.cif"), True),
    # COD 4003235 (cod_4003235.cif) at 293 K, a hybrid lead iodide
    "hybrid iodide": ("C10H36I10N4Pb3", *_cif("cod_4003235.cif"), True),
}

#: Measured on this tree (WP-2030, 2026-10-23): V_true / (Z × V_est), the
#: ratio Hofmann (2002, § 3) bounds at 0.8-1.25, and whether the window at the
#: true Z and the floor at ``z=None`` hold the true cell.  Every inorganic cell
#: but halite's lies under 0.8, at 0.375-0.649, so the window's floor excludes
#: it; at ``z=None`` the floor of one formula unit still excludes the three
#: Z = 1 cells.  HKUST-1 lies above 1.25 the other way: its formula leaves the
#: pores' contents out, Hofmann's § 3 (ii).  Pinned so that the window rule
#: WP-2030's part 2 adds moves these numbers visibly.
MEASURED: dict[str, tuple[float, bool, bool]] = {
    "LaB6": (0.523, False, False), "Si": (0.537, False, True),
    "corundum": (0.375, False, True), "NAC": (0.637, False, True),
    "fluorapatite": (0.568, False, True), "zincite": (0.473, False, True),
    "zircon": (0.593, False, True), "brucite": (0.591, False, False),
    "magnetite": (0.541, False, True), "fluorite": (0.605, False, True),
    "halite": (0.866, True, True), "cBN": (0.472, False, True),
    "anglesite": (0.649, False, True), "hausmannite": (0.571, False, True),
    "LCMO": (0.488, False, True), "YBCO": (0.523, False, False),
    "paracetamol": (1.000, True, True), "benzoic acid": (1.026, True, True),
    "bethanechol chloride": (1.014, True, True), "HKUST-1": (2.283, False, True),
    "hybrid iodide": (1.044, True, True),
}


@pytest.mark.parametrize("name", sorted(KNOWN_CELLS))
def test_the_window_against_known_cells_is_measured(name):
    formula, z, v_true, t, _organic = KNOWN_CELLS[name]
    ratio, inside, inside_floor = MEASURED[name]
    v_fu, _ = formula_unit_volume(formula, t)
    assert v_true / (z * v_fu) == pytest.approx(ratio, abs=5e-4)
    spec = SearchSpec.from_formula(formula, z=z, temperature=t)
    assert (spec.min_volume <= v_true <= spec.max_volume) is inside
    floor = SearchSpec.from_formula(formula, temperature=t)
    assert (v_true >= floor.min_volume) is inside_floor


def test_a_ceiling_alone_would_hold_every_inorganic_cell_measured():
    """The first of WP-2030's three candidate rules, as arithmetic: every
    inorganic cell measured lies under 1.25 × Z × V_est, so a window with no
    floor holds them all.  The rule itself is part 2's to choose."""
    high = VOLUME_RATIO_BOUNDS[1]
    for name, (formula, z, v_true, t, organic) in KNOWN_CELLS.items():
        if not organic:
            v_fu, _ = formula_unit_volume(formula, t)
            assert v_true <= z * v_fu * high, name


#: The Z check on the true cells above, measured on this tree (WP-2030): it
#: fires on twelve of the sixteen inorganic cells, and the four it spares
#: imply a whole number that is not their Z (silicon reads 4.30 for its 8, cBN
#: 1.89 for 4, LCMO 1.95 for 4, zincite 0.95 for 2).  Silent on every organic
#: and metal-organic cell.  Pinned for part 2, whose window rule decides which
#: formulas the check may read Hofmann's table for.
Z_CHECK_FIRES = {"LaB6", "corundum", "NAC", "fluorapatite", "zircon", "brucite",
                 "magnetite", "fluorite", "halite", "anglesite", "hausmannite",
                 "YBCO"}


def test_the_z_check_against_known_cells_is_measured():
    fired = set()
    for name, (formula, _z, v_true, t, _organic) in KNOWN_CELLS.items():
        diags = candidate_diagnostics(_candidate(v_true), formula=formula,
                                      temperature=t)
        if any(d.code == "INDEX_Z_NOT_INTEGER" for d in diags):
            fired.add(name)
    assert fired == Z_CHECK_FIRES


# ----------------------------------------------------------------------
# WP-2030: a hydrate written with a full stop
# ----------------------------------------------------------------------
def test_a_full_stop_hydrate_is_refused_naming_the_raised_dot():
    # read as a decimal it would be CuS O4.5 H10 O5, 39 % low (WP-1510's review)
    with pytest.raises(ValueError, match="·") as err:
        formula_unit_volume("CuSO4.5H2O")
    assert "the count 4.5" in str(err.value)
    assert "CuSO4 · 5H2O" in str(err.value)


@pytest.mark.parametrize("formula,expected", [
    # a count under 1 cannot be the first half of an adduct: no formula
    # writes a count of zero
    ("Mg0.5SiO3", {"Mg": 0.5, "Si": 1, "O": 3}),
    ("CuSO4·5H2O", {"Cu": 1, "S": 1, "O": 9, "H": 10}),
    ("CuSO4·2.5H2O", {"Cu": 1, "S": 1, "O": 6.5, "H": 5}),
    # a space after the decimal count, as a CIF _chemical_formula_sum writes it
    ("Fe2.95 O4", {"Fe": 2.95, "O": 4}),
    ("Ba2 Cu2.941 O6.822 Y", {"Ba": 2, "Cu": 2.941, "O": 6.822, "Y": 1}),
    # doped oxides and cathodes written with no spaces: a decimal count whose
    # tail is not an adduct molecule reads one way (the 1.9.0 reading)
    ("Fe2.95O4", {"Fe": 2.95, "O": 4}),
    ("Li1.05Mn1.95O4", {"Li": 1.05, "Mn": 1.95, "O": 4}),
    ("Fe1.05S", {"Fe": 1.05, "S": 1}),
    ("Li1.2Mn0.54Ni0.13Co0.13O2",
     {"Li": 1.2, "Mn": 0.54, "Ni": 0.13, "Co": 0.13, "O": 2}),
    ("Ca9.5(PO4)6F2", {"Ca": 9.5, "P": 6, "O": 24, "F": 2}),
    ("Sr1.5La0.5MnO4", {"Sr": 1.5, "La": 0.5, "Mn": 1, "O": 4}),
    ("Ba2Cu2.941O6.822Y", {"Ba": 2, "Cu": 2.941, "O": 6.822, "Y": 1}),
])
def test_a_formula_that_reads_one_way_is_unchanged(formula, expected):
    volume, _ = formula_unit_volume(formula)
    assert volume == pytest.approx(
        sum(n * HOFMANN_VOLUMES[el][0] for el, n in expected.items()))


@pytest.mark.parametrize("formula", [
    "Na2CO3.10H2O", "CuSO4.5 H2O", "MgSO4.7 H2O", "CuSO4.5H2O·H2O",
    "CoCl2.6H2O", "ZnSO4.6NH3",
    # any whitespace before the molecule, and inside it: a copy from a PDF or a
    # web page brings a non-breaking space, and a CIF sum writes H2 O
    "CuSO4.5  H2O", "CuSO4.5\u00a0H2O", "CuSO4.5 H2 O", "CuSO4.5\tH2O",
    "CuSO4.5 \u00a0H2 O ", "CoCl2.6 H2 O"])
def test_every_full_stop_that_reads_two_ways_is_refused(formula):
    with pytest.raises(ValueError, match="reads two ways"):
        formula_unit_volume(formula)


# ----------------------------------------------------------------------
# WP-2030: the result records the formula its Z check read
# ----------------------------------------------------------------------
def test_the_result_records_the_formula_and_temperature_it_checked():
    from rietx.schemas.indexing import IndexingResult

    peaks, _ = synthetic_peaks("cubic")
    spec = SearchSpec(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
                      max_volume=1500.0, shift_allowance_deg=1e-9)
    res = index_pattern(peaks, spec=spec, preset="full",
                        engines=("trial_error",), formula="CH3OH",
                        temperature=150.0)
    assert (res.formula, res.temperature) == ("CH3OH", 150.0)
    back = IndexingResult.model_validate_json(res.model_dump_json())
    assert (back.formula, back.temperature) == ("CH3OH", 150.0)

    # no formula: no check was made, and nothing claims one was
    bare = index_pattern(peaks, spec=spec, preset="full",
                         engines=("trial_error",))
    assert (bare.formula, bare.temperature) == (None, None)
    with pytest.raises(ValueError, match="needs a formula"):
        IndexingResult.model_validate({**bare.model_dump(), "temperature": 298.0})

    # the abstention path records it too: four lines support no search
    short = peaks.model_copy(update={"peaks": peaks.peaks[:4]})
    abstained = index_pattern(short, spec=spec, formula="CH3OH")
    assert abstained.candidates == []
    assert (abstained.formula, abstained.temperature) == ("CH3OH", 298.0)


def test_the_cli_hands_the_formula_to_index_pattern(monkeypatch, capsys):
    import rietx.indexing as indexing
    from rietx.cli import main

    seen = {}

    class _Result:
        def __str__(self):
            return "stub"

        def best_or_none(self):
            return None

    def fake(**kwargs):
        seen.update(kwargs)
        return _Result()

    monkeypatch.setattr(indexing, "index_pattern", fake)
    pattern = str(Path(__file__).parent / "data" / "qarr" / "zincite.prn")
    rc = main(["index", pattern, "--wavelength", "1.5405929",
               "--formula", "ZnO", "--temperature", "100"])
    assert rc == 1
    assert (seen["formula"], seen["temperature"]) == ("ZnO", 100.0)
    main(["index", pattern, "--wavelength", "1.5405929"])
    assert (seen["formula"], seen["temperature"]) == (None, 298.0)
