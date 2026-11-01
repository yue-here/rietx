"""Shannon (1976) ionic/crystal radii, Pyykkö & Atsumi (2009) covalent radii
and Pauling (1960) metallic radii.

The spot values below are written out from the printed pages, not read from
the bundled files, so a corrupted or truncated table fails here instead of
agreeing with itself. Three of them are cells where a widely used digital copy
is wrong, so a table rebuilt from that copy fails too. The whole-file checks
are Shannon's own relation between his two scales and the printed row counts,
each with an arm showing it can fail.
"""

from __future__ import annotations

from collections import Counter
from importlib.resources import files

import numpy as np
import pytest

from rietx.crystallography import radii
from rietx.crystallography.radii import (
    IonicRadius,
    MetallicRadius,
    covalent_radius,
    ionic_radius,
    metallic_radius,
)


def _text(name: str) -> str:
    return (files("rietx.data") / name).read_text(encoding="utf-8")


def _shannon_cells(text: str) -> list[list[str]]:
    return [line.split() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


# --- spot rows against the page ---------------------------------------------
#
# (species, cn, spin, CR, IR, flags), from Shannon (1976) Table 1, pp. 752-753,
# each read off the page image. The first three are where a digital copy
# disagrees with the page: the Imperial College database prints Cr2+ VI HS as
# R*, and Wikipedia's "Ionic radius" gives Pa3+ VI CR 1.16 and Gd3+ VI IR
# 0.935.
_PAGE_ROWS = [
    ("Cr2+", "VI", "HS", 0.94, 0.80, "R"),       # Imperial DB: R*
    ("Pa3+", "VI", None, 1.18, 1.04, "E"),       # Wikipedia CR: 1.16
    ("Gd3+", "VI", None, 1.078, 0.938, "R"),     # Wikipedia IR: 0.935
    ("Cs+", "XII", None, 2.02, 1.88, ""),
    ("Cu2+", "IVSQ", None, 0.71, 0.57, "*"),
    ("Fe3+", "VI", "HS", 0.785, 0.645, "R*"),
    ("Mn3+", "VI", "LS", 0.72, 0.58, "R"),
    ("N5+", "III", None, 0.044, -0.104, ""),     # the one row off the 0.14 rule
    ("No2+", "VI", None, 1.24, 1.1, "E"),        # IR printed with one decimal
    ("Ni3+", "VI", "LS", 0.70, 0.56, "R*"),
    ("O2-", "VI", None, 1.26, 1.40, ""),         # the scale's own anchor
    ("Sb3+", "V", None, 0.94, 0.80, ""),         # IR(V) > IR(VI) 0.76, printed so
    ("Zr4+", "VIII", None, 0.98, 0.84, "*"),
]


@pytest.mark.parametrize("species, cn, spin, cr, ir, flags", _PAGE_ROWS)
def test_shannon_rows_match_the_printed_page(species, cn, spin, cr, ir, flags):
    ionic = ionic_radius(species, cn, spin=spin)
    crystal = ionic_radius(species, cn, spin=spin, kind="crystal")
    assert (ionic.radius, ionic.crystal_radius, ionic.flags) == (ir, cr, flags)
    assert (crystal.radius, crystal.ionic_radius, crystal.kind) == (cr, ir, "crystal")


def test_the_digital_copies_errors_are_not_in_the_table():
    """The three cells where a copy is wrong, stated as the wrong value."""
    assert ionic_radius("Cr2+", 6, spin="HS").flags != "R*"
    assert ionic_radius("Pa3+", 6, kind="crystal").radius != 1.16
    assert ionic_radius("Gd3+", 6).radius != 0.935


# (element, r1 pm, r2 pm or None), Pyykkö & Atsumi (2009a) Fig. 2 and
# (2009b) Fig. 3, read off the figures.
_PYYKKO = [
    ("H", 32, None), ("B", 85, 78), ("C", 75, 67), ("O", 63, 57),
    ("Na", 155, 160),        # r2 > r1, one of the paper's "apparent anomalies"
    ("Fe", 116, 109), ("La", 180, 139), ("Cn", 122, 137), ("Og", 157, None),
]


@pytest.mark.parametrize("element, r1, r2", _PYYKKO)
def test_pyykko_radii_match_the_printed_figures(element, r1, r2):
    assert covalent_radius(element) == pytest.approx(r1 / 100, abs=1e-12)
    if r2 is None:
        with pytest.raises(KeyError, match=f"no r2 for {element}"):
            covalent_radius(element, order=2)
    else:
        assert covalent_radius(element, order=2) == pytest.approx(r2 / 100, abs=1e-12)


# --- whole-table checks -----------------------------------------------------


def test_shannon_row_counts_match_the_print():
    """497 rows, in six column blocks of 83 except the last (82)."""
    cells = _shannon_cells(_text("r_ion_Shannon.dat"))
    assert len(cells) == len(radii._shannon_rows()) == 497
    assert Counter(c[9] for c in cells) == {
        "2.1": 83, "2.2": 83, "2.3": 83, "3.1": 83, "3.2": 83, "3.3": 82}
    assert Counter(c[8] for c in cells) == {"752": 249, "753": 248}
    # the CN distribution, which the Imperial College copy shares exactly
    assert Counter(c[3] for c in cells) == {
        "VI": 197, "VIII": 73, "IV": 63, "VII": 35, "IX": 32, "V": 25,
        "XII": 18, "X": 13, "II": 10, "IVSQ": 10, "III": 9, "XI": 5,
        "IIIPY": 3, "IVPY": 2, "I": 1, "XIV": 1}
    keys = [(c[0], c[1], c[3], c[4]) for c in cells]
    assert len(set(keys)) == len(keys)


def test_pyykko_row_counts_match_the_print():
    table = radii._pyykko_rows()
    assert len(table) == 118
    assert sum(r2 == r2 for _, r2 in table.values()) == 108      # nan != nan
    zs = [int(line.split()[1]) for line in _text("r_cov_Pyykko.dat").splitlines()
          if line.strip() and not line.startswith("#")]
    assert zs == list(range(1, 119))


def _off_the_014_rule(text: str) -> list[tuple[str, int, str, float]]:
    """Rows breaking CR = IR + 0.14 (cations) / IR - 0.14 (anions), to the
    printed digits (Shannon pp. 759-760)."""
    off = []
    for ion, charge, _ec, cn, _spin, cr, ir, *_ in _shannon_cells(text):
        gap = (float(cr) - float(ir)) * (1 if int(charge) > 0 else -1)
        if round(gap, 4) != 0.14:
            off.append((ion, int(charge), cn, round(gap, 4)))
    return off


def test_crystal_and_ionic_radii_differ_by_014_except_where_printed():
    """Shannon: "crystal radii differ from traditional radii only by a
    constant factor of 0.14 A". One printed row breaks it, N5+ III
    (.044 / -.104), and it is pinned as the exception it is."""
    assert _off_the_014_rule(_text("r_ion_Shannon.dat")) == [("N", 5, "III", 0.148)]


def test_the_014_check_catches_a_digit_swap():
    """Positive arm: the commonest OCR error on this table, a 4 read as 6,
    in one cell (Fe3+ VI HS IR 0.645 -> 0.665) is caught."""
    text = _text("r_ion_Shannon.dat")
    line = next(row for row in text.splitlines() if row.startswith("Fe    3") and " HS " in row
                and "0.785" in row)
    broken = text.replace(line, line.replace("0.645", "0.665"))
    assert ("Fe", 3, "VI", 0.12) in _off_the_014_rule(broken)


def test_each_data_file_states_its_source_and_status_where_it_ships():
    """A file entering the wheel says what it is (CLAUDE.md, licensing)."""
    for name, dois in (("r_ion_Shannon.dat", ["10.1107/S0567739476001551"]),
                       ("r_cov_Pyykko.dat", ["10.1002/chem.200800987",
                                             "10.1002/chem.200901472"]),
                       ("r_metal_Pauling.dat", ["10.1021/ja01195a024"])):
        head = _text(name).split("\n\n")[0]
        assert "# CITE:" in head and "# STATUS:" in head
        for doi in dois:
            assert doi in head


# --- lookups ----------------------------------------------------------------


def test_charge_spellings_resolve_to_one_row():
    assert ionic_radius("Fe+3", 6, spin="HS") == ionic_radius("Fe3+", 6, spin="HS")
    assert ionic_radius("F-", 6).radius == ionic_radius("F1-", 6).radius == 1.33
    assert ionic_radius("OH-", 4).ion == "OH"
    assert ionic_radius("Os4+", 6).ion == "Os"
    assert ionic_radius("D+", 2) == ionic_radius("2H+", 2)
    assert ionic_radius("D+", 2).radius == -0.10           # printed negative
    assert ionic_radius("H+", 2).radius == -0.18


def test_an_integer_cn_reaches_a_lone_suffixed_row():
    """Pd2+ at 4 is printed only as IVSQ, and the label says so."""
    r = ionic_radius("Pd2+", 4)
    assert (r.cn, r.coordination, r.radius) == ("IVSQ", 4, 0.64)


def test_flags_travel_with_the_value():
    estimated = ionic_radius("Pa3+", 6)
    assert isinstance(estimated, IonicRadius)
    assert estimated.estimated and not estimated.reliable
    assert ionic_radius("Zr4+", 8).reliable
    assert ionic_radius("Cs+", 12).flags == ""


# --- refusals ---------------------------------------------------------------


def test_an_untabulated_cn_is_refused_naming_the_tabulated_ones():
    # VII sits between two tabulated CNs; it is not interpolated
    with pytest.raises(KeyError, match=r"Fe3\+ at CN IV, V, VI, VIII only, not VII"):
        ionic_radius("Fe3+", 7)
    with pytest.raises(KeyError, match="no radius is interpolated"):
        ionic_radius("La3+", "XIV")


def test_a_spin_shannon_does_not_print_is_refused():
    with pytest.raises(KeyError, match=r"Mn4\+ VI with no spin state, not HS"):
        ionic_radius("Mn4+", 6, spin="HS")
    with pytest.raises(KeyError, match=r"Fe2\+ IV only in HS, not LS"):
        ionic_radius("Fe2+", "IV", spin="LS")


def test_where_both_spins_are_printed_the_caller_chooses():
    with pytest.raises(ValueError, match=r"Co2\+ VI in HS and LS"):
        ionic_radius("Co2+", 6)
    assert ionic_radius("Co2+", 6, spin="LS").radius == 0.65
    assert ionic_radius("Co2+", 6, spin="HS").radius == 0.745


def test_a_plain_and_a_suffixed_row_at_one_cn_is_ambiguous():
    with pytest.raises(ValueError, match="IV and IVSQ"):
        ionic_radius("Cu2+", 4)
    assert ionic_radius("Cu2+", "IV").radius == 0.57


@pytest.mark.parametrize("species, error, match", [
    ("Fe", ValueError, "no oxidation state"),
    ("Fe7+", KeyError, r"Fe only at charge \+2, \+3, \+4, \+6, not \+7"),
    ("He2+", KeyError, "no row for He"),
    ("Xx3+", ValueError, "unrecognised element"),
])
def test_an_ion_shannon_does_not_tabulate_is_refused(species, error, match):
    with pytest.raises(error, match=match):
        ionic_radius(species, 6)


def test_bad_arguments_are_refused():
    with pytest.raises(ValueError, match="kind"):
        ionic_radius("O2-", 6, kind="effective")
    with pytest.raises(ValueError, match="spin"):
        ionic_radius("Fe3+", 6, spin="high")
    with pytest.raises(ValueError, match="coordination number"):
        ionic_radius("O2-", "six")
    with pytest.raises(ValueError, match="order"):
        covalent_radius("C", order=3)


@pytest.mark.parametrize("species", ["T+", "3H+"])
def test_tritium_does_not_borrow_hydrogens_row(species):
    """Shannon tabulates D apart from H and prints no tritium row."""
    with pytest.raises(KeyError, match="mass number 3"):
        ionic_radius(species, 2)
    assert ionic_radius("D+", 2).ion == "D"
    assert ionic_radius("1H+", 2).ion == "H"


def test_numpy_integers_are_integers_to_the_lookup():
    """Consumers count neighbours in numpy."""
    want = ionic_radius("Fe3+", 6, spin="HS")
    assert ionic_radius("Fe3+", np.int64(6), spin="HS") == want
    assert covalent_radius("C", order=np.int64(2)) == covalent_radius("C", order=2)
    with pytest.raises(TypeError):
        ionic_radius("Fe3+", 6.0, spin="HS")


@pytest.mark.parametrize("order", [1.0, 2.0, 0, "1"])
def test_a_non_integer_bond_order_names_the_allowed_orders(order):
    with pytest.raises(ValueError, match="order must be 1"):
        covalent_radius("C", order=order)


# --- Pauling (1960) metallic radii ------------------------------------------
#
# (element, v, R(L12), R1), Pauling (1960) Table 11-1, p. 403, each read off
# the page image; one or more from every printed row of the table.
_PAULING_ROWS = [
    ("Li", 1, 1.549, 1.225), ("B", 3, 0.98, 0.80),   # B R1 printed ".80"
    ("Al", 3, 1.429, 1.248), ("K", 1, 2.349, 2.025),
    ("Fe", 6, 1.260, 1.170), ("Cu", 5.56, 1.276, 1.176),
    ("Ge", 2.56, 1.444, 1.242), ("Te", 2, 1.60, 1.37),  # v printed "(2)"
    ("Pd", 6, 1.373, 1.283), ("Sn", 2.56, 1.623, 1.421),
    ("La", 3, 1.871, 1.690), ("W", 6, 1.394, 1.304),
    ("Pb", 2.56, 1.704, 1.502), ("Bi", 1.56, 1.776, 1.510),
    ("U", 6, 1.516, 1.426), ("Yb", 2, 1.933, 1.699),
]


@pytest.mark.parametrize("element, v, r12, r1", _PAULING_ROWS)
def test_pauling_rows_match_the_printed_page(element, v, r12, r1):
    one = metallic_radius(element)
    twelve = metallic_radius(element, ligancy=12)
    assert isinstance(one, MetallicRadius)
    assert (one.radius, one.r1, one.r12, one.valence, one.ligancy) == (r1, r1, r12, v, 1)
    assert (twelve.radius, twelve.r1, twelve.ligancy) == (r12, r1, 12)
    assert one.page == 403 and one.as_printed == ""


def test_pauling_misprints_are_corrected_with_the_printed_cell_kept():
    gd = metallic_radius("Gd", ligancy=12)
    assert (gd.radius, gd.r1, gd.flags, gd.as_printed) == (
        1.804, 1.623, ("r12_corrected",), "r12=2.804")
    eu = metallic_radius("Eu")
    assert (eu.valence, eu.r12, eu.r1, eu.flags, eu.as_printed) == (
        2, 2.084, 1.850, ("v_corrected",), "v=3")
    sr = metallic_radius("Sr")
    assert (sr.valence, sr.r12, sr.r1, sr.flags, sr.as_printed) == (
        2, 2.148, 1.914, ("label_corrected",), "label=Sn")
    assert metallic_radius("Sn").r1 == 1.421          # Sn's own cell is untouched
    pm = metallic_radius("Pm", ligancy=12)             # flagged, kept as printed
    assert (pm.radius, pm.r1, pm.flags, pm.as_printed) == (
        1.834, 1.633, ("r12_off_relation",), "")
    assert {r.element for r in radii._pauling_rows().values() if "v_assumed" in r.flags} \
        == {"P", "S", "Se", "Te"}


def test_pauling_corrections_carry_their_evidence_in_the_file():
    head = _text("r_metal_Pauling.dat").split("\n\n")[0]
    for needle in ("printed 2.804, corrected to 1.804", "printed 3, corrected to 2",
                   'labelled "Sn"', "printed 1.834", "p. 412", "1947 table"):
        assert needle in head


def _pauling_cells(text: str) -> list[list[str]]:
    return [line.split() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _off_the_pauling_relation(cells: list[list[str]]) -> list[str]:
    """Rows breaking R(L12) = R1 + 0.300 log(12/v) (p. 412) beyond the
    rounding of the printed digits (half a unit in the last place of each)."""
    off = []
    for symbol, v, r12, r1, *_ in cells:
        tol = sum(0.5 * 10.0 ** -len(x.split(".")[1]) for x in (r12, r1)) + 1e-4
        if abs(float(r12) - float(r1) - 0.300 * np.log10(12 / float(v))) > tol:
            off.append(symbol)
    return off


def _as_printed(cells: list[list[str]]) -> list[list[str]]:
    """The table as the page prints it: each correction undone."""
    printed = []
    for symbol, v, r12, r1, page, flags, cell in cells:
        for undo in ([] if cell == "-" else cell.split(";")):
            key, value = undo.split("=")
            if key == "v":
                v = value
            elif key == "r12":
                r12 = value
        printed.append([symbol, v, r12, r1, page, flags, cell])
    return printed


def test_pauling_relation_holds_except_at_the_misprints():
    """Pauling's own ligancy-12 correction, on every row (all print both
    radii). As printed it breaks at the three misprints; as shipped only Pm,
    kept as printed, still breaks it."""
    cells = _pauling_cells(_text("r_metal_Pauling.dat"))
    assert _off_the_pauling_relation(cells) == ["Pm"]
    assert _off_the_pauling_relation(_as_printed(cells)) == ["Pm", "Eu", "Gd"]


def test_the_pauling_relation_catches_a_one_digit_slip():
    """Positive arm: one 3 read as 8 (Re R(L12) 1.373 -> 1.873, the slip one
    copy's OCR made) is caught."""
    cells = _pauling_cells(_text("r_metal_Pauling.dat"))
    re_row = next(c for c in cells if c[0] == "Re")
    re_row[2] = "1.873"
    assert "Re" in _off_the_pauling_relation(cells)


def test_pauling_row_counts_match_the_print():
    """72 entries in the printed order of Table 11-1's seven rows."""
    symbols = [c[0] for c in _pauling_cells(_text("r_metal_Pauling.dat"))]
    blocks = ["Li Be B", "Na Mg Al Si P S",
              "K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se",
              "Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te",
              "Cs Ba La Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi", "Th U",
              "Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu"]
    assert [len(b.split()) for b in blocks] == [3, 6, 16, 16, 15, 2, 14]
    assert symbols == " ".join(blocks).split()
    assert len(radii._pauling_rows()) == 72


@pytest.mark.parametrize("ligancy", [2, 6, 8, 0, 1.0, 12.0, "12", True])
def test_a_ligancy_pauling_does_not_print_is_refused(ligancy):
    with pytest.raises(ValueError, match="ligancy must be 1 .* or 12"):
        metallic_radius("Fe", ligancy=ligancy)


@pytest.mark.parametrize("element", ["C", "O", "Cl", "Ar", "Ac", "Pu"])
def test_an_element_not_in_table_11_1_is_refused_naming_the_table(element):
    with pytest.raises(KeyError, match=f"no metallic radius for {element} .*Li Be B Na"):
        metallic_radius(element)


def test_a_charged_species_has_no_metallic_radius():
    with pytest.raises(ValueError, match="carries a charge"):
        metallic_radius("Fe3+")
    with pytest.raises(ValueError, match="carries a charge"):
        metallic_radius("La+3")
    assert metallic_radius("7Li") == metallic_radius("Li")
    assert metallic_radius("Fe", ligancy=np.int64(12)).radius == 1.260
