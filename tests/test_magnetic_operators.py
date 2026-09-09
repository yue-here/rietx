"""Magnetic space-group operators, settings, and the allowed moment subspace.

Three kinds of check, and they fail for different reasons:

* **Exhaustive, over spglib's whole database.**  Every one of the 1651 groups
  is built, closed, printed, re-parsed and identified.  Those are properties of
  the code, not of any structure, so they are asserted on all of them rather
  than on a sample.
* **A positive arm on twenty published structures.**  For each, the
  *published* moment direction is asserted to lie in the **span** of the
  derived allowed subspace — never its dimension, which is right in every
  crystal system under the wrong symmetry action (root ``CLAUDE.md``, the Rᵀ
  trap; ``test_wyckoff.py`` and ``indexing.qspace`` carry the same warning one
  tensor rank up and one subsystem over).  Ten of the twenty are stated in a
  setting the BNS standard reaches only through a transform.
* **Negative controls that must fail.**  Each of the three ways to get the
  axial action wrong — transposing R, dropping det R, dropping the
  time-reversal sign — is built on purpose and asserted to *exclude* a moment
  the correct action allows.

Provenance of the fixtures, since it decides what they can prove
----------------------------------------------------------------
No data file is vendored.  Two independent kinds of number appear:

1. **Operator strings.**  Those in :data:`TYPED_OPERATORS` are transcribed
   character for character from the published record of each structure, *not*
   generated from spglib, which is the only way to catch a database whose
   setting differs from the one a user's file is written in.  Two of the four
   are deliberately in non-standard settings.  Operator lists are mathematical
   facts about a group; the numbers below are the same facts Litvin (2013),
   *Magnetic Group Tables* (IUCr) prints.
2. **Moment directions.**  Each is transcribed as a number and cited to the
   **original paper** that measured it, with author, year, journal, volume and
   page.  The MAGNDATA entry number is given only as the record the
   transcription was checked against — never as the source of the number.

The independent oracle in :func:`test_derived_span_reproduces_the_group`
closes the loop without any published number at all: a moment taken from the
derived span is propagated over the orbit and handed to spglib's own magnetic
symmetry search, which implements the axial action in its own code and must
return the group it started from.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest
import spglib

from rietx.crystallography.magnetic.operators import (
    IDENTITY,
    N_MAGNETIC_SPACE_GROUPS,
    TIME_REVERSAL,
    UNI_NOT_IDENTIFIABLE,
    MagneticGroup,
    MagneticOperator,
    allowed_moment_basis,
    database_settings,
    format_transform,
    identify,
    in_span,
    magnetic_group,
    moment_from_cartesian,
    moment_magnitude,
    moment_to_cartesian,
    parse_transform,
)

# ---------------------------------------------------------------------------
# operator lists transcribed from the published record, not generated here
# ---------------------------------------------------------------------------
MNF2_OPS = (
    "x,y,z,+1", "x+1/2,-y+1/2,-z+1/2,+1", "-x+1/2,y+1/2,-z+1/2,+1", "-x,-y,z,+1",
    "-x,-y,-z,+1", "-x+1/2,y+1/2,z+1/2,+1", "x+1/2,-y+1/2,z+1/2,+1", "x,y,-z,+1",
    "-y+1/2,x+1/2,z+1/2,-1", "y+1/2,-x+1/2,z+1/2,-1", "y,x,-z,-1", "-y,-x,-z,-1",
    "y+1/2,-x+1/2,-z+1/2,-1", "-y+1/2,x+1/2,-z+1/2,-1", "-y,-x,z,-1", "y,x,z,-1",
)
CR2O3_OPS = (
    "x,y,z,+1", "-y,x-y,z,+1", "-x+y,-x,z,+1", "x-y,-y,-z+1/2,+1",
    "y,x,-z+1/2,+1", "-x,-x+y,-z+1/2,+1", "-x,-y,-z,-1", "y,-x+y,-z,-1",
    "x-y,x,-z,-1", "-x+y,y,z+1/2,-1", "-y,-x,z+1/2,-1", "x,x-y,z+1/2,-1",
)
CR2O3_CENTERINGS = ("x,y,z,+1", "x+1/3,y+2/3,z+2/3,+1", "x+2/3,y+1/3,z+1/3,+1")
CA3LIOSO6_OPS = (
    "x,y,z,+1", "-x,-y,-z,+1", "x-y+1/3,-y+2/3,-z+1/6,-1",
    "-x+y+1/3,y+2/3,z+1/6,-1", "x+2/3,y+1/3,z+1/3,+1", "-x+2/3,-y+1/3,-z+1/3,+1",
    "x-y,-y,-z+1/2,-1", "-x+y,y,z+1/2,-1", "x+1/3,y+2/3,z+2/3,+1",
    "-x+1/3,-y+2/3,-z+2/3,+1", "x-y+2/3,-y+1/3,-z+5/6,-1",
    "-x+y+2/3,y+1/3,z+5/6,-1",
)
MN3O4_OPS = (
    "x,y,z,+1", "-x+1/2,y+1/2,-z+1/2,+1", "-x,-y,z+1/2,+1", "x+1/2,-y+1/2,-z,+1",
    "-x,-y,-z,+1", "x+1/2,-y+1/2,z+1/2,+1", "x,y,-z+1/2,+1", "-x+1/2,y+1/2,z,+1",
    "x+1/2,y,z,-1", "-x,y+1/2,-z+1/2,-1", "-x+1/2,-y,z+1/2,-1", "x,-y+1/2,-z,-1",
    "-x+1/2,-y,-z,-1", "x,-y+1/2,z+1/2,-1", "x+1/2,y,-z+1/2,-1", "-x,y+1/2,z,-1",
)

#: (label, operation strings, centring strings, BNS number, MSG type, site,
#: published moment in crystal-axis μ_B, citation, checked-against record).
#: The strings are the published operator lists; nothing here comes from
#: spglib, which is the point — a database whose setting differs from the
#: file's still round-trips against itself, and only an outside list can say so.
TYPED_OPERATORS = [
    ("MnF2", MNF2_OPS, None, "136.499", 3, (0.0, 0.0, 0.0), (0.0, 0.0, 4.6),
     "Yamani, Tun & Ryan (2010), Can. J. Phys. 88, 771-797", "MAGNDATA #0.15"),
    ("Cr2O3", CR2O3_OPS, CR2O3_CENTERINGS, "167.106", 3, (0.0, 0.0, 0.3476),
     (0.0, 0.0, 2.48),
     "Brown, Forsyth, Lelievre-Berna & Tasset (2002), "
     "J. Phys.: Condens. Matter 14, 1957-1966", "MAGNDATA #0.59"),
    # in the trigonal *parent* cell, not the BNS standard monoclinic one
    ("Ca3LiOsO6", CA3LIOSO6_OPS, None, "15.89", 3, (0.0, 0.0, 0.0),
     (2.2, 0.0, 0.0),
     "Calder, Garlea, McMorrow, Lumsden, Stone, Lang, Yan, Cao, Wang, Qi, "
     "Sales, Mandrus, Cao & Christianson (2012), Phys. Rev. B 86, 054403",
     "MAGNDATA #0.3"),
    # type IV, and in a setting the BNS standard reaches only through (b,c,a)
    ("Mn3O4", MN3O4_OPS, None, "62.452", 4, (0.154, 0.114, 0.07),
     (3.49, 0.0, 0.0),
     "Hirai, Sanchez-Benitez, Attfield et al. (2013), Phys. Rev. B 87, 014417",
     "MAGNDATA #1.1"),
]

#: The rest of the twenty published magnetic structures, their operators taken
#: from the database by BNS number and carried into the setting each structure
#: is stated in.  One row per structure:
#: (label, BNS number, Hall number, transform_BNS_Pp_abc or None, MSG type,
#: site, published moment in crystal-axis μ_B, derived span, citation, record).
#:
#: Every moment is transcribed as a number and cited to the **original paper**
#: that measured it; the MAGNDATA entry is named only as the record the
#: transcription was checked against.  No type II (grey) row exists and none
#: can: a grey group forbids every ordered moment, so no *published magnetic
#: structure* has one — that type is covered by :data:`GREY_GROUPS` instead.
PUBLISHED_MOMENTS = [
    ("LaMnO3", "62.448", 0, None, 3, (0.0, 0.0, 0.0), (3.7, 0.0, 0.0),
     [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
     "Elemans, van Laar, van der Veen & Loopstra (1971), "
     "J. Solid State Chem. 3, 238-242", "MAGNDATA #0.642"),
    ("GdB4", "127.395", 0, None, 3, (0.31746, 0.81746, 0.0), (5.05, 5.05, 0.0),
     [[1, 1, 0]],
     "Blanco, Brown, Stunault, Katsumata, Iga & Michimura (2006), "
     "Phys. Rev. B 73, 212411", "MAGNDATA #0.9"),
    # origin choice 2: see test_setting_decides_whether_a_published_moment_fits
    ("Cd2Os2O7", "227.131", 526, None, 3, (0.0, 0.0, 0.0), (0.6, 0.6, 0.6),
     [[1, 1, 1]],
     "Yamaura, Ohgushi, Ohsumi, Hasegawa, Yamauchi, Sugimoto, Takeshita, "
     "Tokuda, Takata, Udagawa, Takigawa, Harima, Arima & Hiroi (2012), "
     "Phys. Rev. Lett. 108, 247205", "MAGNDATA #0.2"),
    # a hexagonal setting, an in-plane moment: one of the three published rows
    # where the transposed action fails the span test
    ("YMnO3", "185.197", 0, None, 1, (0.32080, 0.0, 0.0), (1.68, 3.36, 0.0),
     [[1, 2, 0]],
     "Munoz, Alonso, Martinez-Lope, Casais, Martinez & Fernandez-Diaz (2000), "
     "Phys. Rev. B 62, 9498-9510", "MAGNDATA #0.6"),
    ("ScMnO3-P63cm", "185.201", 0, None, 3, (0.33160, 0.0, 0.0),
     (-3.03, 0.0, 0.0), [[1, 0, 0], [0, 0, 1]],
     "Munoz, Alonso, Martinez-Lope, Casais, Martinez & Fernandez-Diaz (2000), "
     "Phys. Rev. B 62, 9498-9510", "MAGNDATA #0.7"),
    ("ScMnO3-P63", "173.129", 0, None, 1, (0.33160, 0.0, 0.0),
     (3.74, 3.31, 0.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
     "Munoz, Alonso, Martinez-Lope, Casais, Martinez & Fernandez-Diaz (2000), "
     "Phys. Rev. B 62, 9498-9510", "MAGNDATA #0.8"),
    ("DyFeO3-Pnpapb21", "33.148", 0, "a,c,-b;0,0,0", 3, (0.0, 0.0, 0.5),
     (1.0, 0.3, 0.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
     "Tokunaga, Iguchi, Arima & Tokura (2008), "
     "Phys. Rev. Lett. 101, 097205", "MAGNDATA #0.11"),
    ("DyFeO3-P212121", "19.25", 0, "a,b,c;0,0,1/4", 1, (0.0, 0.0, 0.5),
     (1.0, 0.3, 0.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
     "Tokunaga, Iguchi, Arima & Tokura (2008), "
     "Phys. Rev. Lett. 101, 097205", "MAGNDATA #0.10"),
    ("U3Ru4Al12", "63.461", 0, "b,-2a-b,c;0,0,0", 3, (0.60980, 0.80490, 0.25),
     (0.0, -2.5, 0.0), [[0, 1, 0]],
     "Troc, Pasturel, Tougait, Sazonov, Gukasov, Sulkowski & Noel (2012), "
     "Phys. Rev. B 85, 064412", "MAGNDATA #0.12"),
    ("Ca3Co2-xMnxO6", "161.69", 0, None, 1, (0.0, 0.0, 0.0), (0.0, 0.0, 1.93),
     [[0, 0, 1]],
     "Choi, Yi, Lee, Huang, Kiryukhin & Cheong (2008), "
     "Phys. Rev. Lett. 100, 047601", "MAGNDATA #0.13"),
    ("YBa2Cu3O6+a", "69.526", 0, "a,b,c;0,3/4,3/4", 4, (0.0, 0.0, 0.180515),
     (0.47, 0.0, 0.0), [[1, 0, 0]],
     "Shamoto, Sato, Tranquada, Sternlieb & Shirane (1993), "
     "Phys. Rev. B 48, 13817-13825", "MAGNDATA #1.5"),
    ("Gd5Ge4", "62.444", 0, None, 3, (0.2927, 0.25, 0.0022), (0.0, 0.0, 1.0),
     [[1, 0, 0], [0, 0, 1]],
     "Tan, Kreyssig, Kim, Goldman, McQueeney, Wermeille, Sieve, Lograsso, "
     "Schlagel, Budko, Pecharsky & Gschneidner (2005), "
     "Phys. Rev. B 71, 214408", "MAGNDATA #0.14"),
    ("FePO4", "19.25", 0, "a,b,c;0,1/2,3/4", 1, (0.27550, 0.25, 0.94820),
     (4.06, 0.9, 0.0), [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
     "Rousse, Rodriguez-Carvajal, Patoux & Masquelier (2003), "
     "Chem. Mater. 15, 4082-4090", "MAGNDATA #0.17"),
    ("Sr2IrO4", "54.352", 0, "c,b,-a;0,0,0", 4, (0.0, 0.25, 0.375),
     (-0.24, 0.0, 0.0), [[1, 0, 0], [0, 1, 0]],
     "Lovesey, Khalyavin, Manuel, Chapon, Cao & Qi (2012), "
     "J. Phys.: Condens. Matter 24, 496003", "MAGNDATA #1.3"),
    # |det P| = 1/8: the magnetic C-cell in the cubic parent's F-cell, so the
    # lattice completion adds 7 centrings and the order goes 16 -> 128
    ("NiO", "15.90", 0, "a/4+b/4-c/2,a/4-b/4,-a/2-b/2;0,0,0", 4, (0.0, 0.0, 0.0),
     (1.0, 1.0, -2.0), [[1, 1, 0], [0, 0, 1]],
     "Ressouche, Kernavanois, Regnault & Henry (2006), "
     "Physica B 385-386, 394-397", "MAGNDATA #1.6"),
    ("EuTiO3", "69.523", 0, "a-b,a+b,c;0,1/2,1/2", 3, (0.5, 0.0, 0.25),
     (-4.9, -4.9, 0.0), [[1, 1, 0]],
     "Scagnoli, Allieta, Walker, Scavini, Katsufuji, Sagarna, Zaharko & "
     "Mazzoli (2012), Phys. Rev. B 86, 094432", "MAGNDATA #0.16"),
]


def published_group(row) -> MagneticGroup:
    """The group of one :data:`PUBLISHED_MOMENTS` row, in its own setting."""
    _, bns, hall, transform, *_ = row
    group = magnetic_group(bns, hall_number=hall)
    return group if transform is None else group.transformed(transform)


#: Coverage of the four magnetic space-group types across every crystal system
#: that constrains a moment at all: (UNI, BNS, type, site, expected span).
#: Chosen so that each row's span is a *proper* non-empty subspace — a full
#: 3-D span asserts nothing, and an empty one is the grey-group row below.
#: Each of these is also an oracle row (:func:`test_derived_span_reproduces_the_group`).
COVERAGE = [
    (8, "3.1", 1, (0, 0, 0), [[0, 1, 0]]),
    (99, "16.1", 1, (0, 0, Fraction(1, 4)), [[0, 0, 1]]),
    (661, "75.1", 1, (0, 0, 0), [[0, 0, 1]]),
    (1231, "143.1", 1, (0, 0, 0), [[0, 0, 1]]),
    (1339, "168.109", 1, (0, 0, 0), [[0, 0, 1]]),
    (1503, "195.1", 1, (0, 0, Fraction(1, 4)), [[0, 0, 1]]),
    (1255, "150.25", 1, (Fraction(1, 2), 0, 0), [[1, 0, 0]]),
    (1259, "151.29", 1, (0, 0, 0), [[2, 1, 0]]),
    (1295, "160.65", 1, (Fraction(1, 2), 0, 0), [[1, 0, 0]]),
    (10, "3.3", 3, (0, 0, 0), [[1, 0, 0], [0, 0, 1]]),
    (101, "16.3", 3, (0, 0, 0), [[0, 1, 0]]),
    (663, "75.3", 3, (Fraction(1, 2), 0, 0), [[0, 0, 1]]),
    (1245, "147.15", 3, (0, 0, Fraction(1, 4)), [[0, 0, 1]]),
    (1341, "168.111", 3, (Fraction(1, 2), 0, 0), [[1, 0, 0], [0, 1, 0]]),
    (1518, "200.16", 3, (0, 0, Fraction(1, 4)), [[0, 0, 1]]),
    (1285, "157.55", 3, (Fraction(1, 2), 0, 0), [[1, 0, 0], [0, 0, 1]]),
    (11, "3.4", 4, (0, 0, 0), [[0, 1, 0]]),
    (102, "16.4", 4, (0, 0, Fraction(1, 4)), [[0, 0, 1]]),
    (664, "75.4", 4, (0, 0, 0), [[0, 0, 1]]),
    (1233, "143.3", 4, (0, 0, 0), [[0, 0, 1]]),
    (1342, "168.112", 4, (0, 0, 0), [[0, 0, 1]]),
    (1505, "195.3", 4, (0, 0, Fraction(1, 4)), [[0, 0, 1]]),
    (1258, "150.28", 4, (Fraction(1, 2), 0, 0), [[1, 0, 0]]),
]

#: Type II (grey) groups, one per crystal system reachable: 1' is in the group,
#: so every moment is its own negative and no site carries one.
GREY_GROUPS = [(2, "1.2"), (9, "3.2"), (100, "16.2"), (662, "75.2"),
               (1232, "143.2"), (1340, "168.110"), (1504, "195.2")]

#: (UNI, BNS, site, correct span, transposed span) — the only places the Rᵀ
#: trap is visible.  Measured over all 1651 groups against a 14-site grid: R
#: and Rᵀ give different spans for 543 of those (group, site) pairs, and
#: **every one is in a trigonal or hexagonal family** (space groups 149-194),
#: which is why no orthorhombic, tetragonal or cubic fixture can be the
#: control.  Every row here is also a row of :data:`COVERAGE`, so the direction
#: the correct action picks is confirmed by spglib's independent search and not
#: only by this module's own algebra.
TRANSPOSE_TRAP = [
    (1255, "150.25", (Fraction(1, 2), 0, 0), [[1, 0, 0]], [[2, -1, 0]]),
    (1259, "151.29", (0, 0, 0), [[2, 1, 0]], [[1, 0, 0]]),
    (1285, "157.55", (Fraction(1, 2), 0, 0), [[1, 0, 0], [0, 0, 1]],
     [[2, -1, 0], [0, 0, 1]]),
    (1295, "160.65", (Fraction(1, 2), 0, 0), [[1, 0, 0]], [[2, -1, 0]]),
    (1258, "150.28", (Fraction(1, 2), 0, 0), [[1, 0, 0]], [[2, -1, 0]]),
]

#: Which of the three wrong actions each of the twenty published fixtures can
#: catch, **measured**.  A control that cannot fail confirms whatever you
#: hoped, so this says per fixture what it is evidence for rather than leaving
#: the reader to assume every fixture is a control; see
#: ``test_each_fixture_declares_which_wrong_actions_it_can_catch``.
#:
#: Three rows catch the transposed rotation and all three are in a hexagonal
#: setting with an in-plane moment (YMnO3, ScMnO3-P63cm, U3Ru4Al12); seven
#: catch nothing at all, which is worth knowing before any of them is quoted
#: as evidence about the symmetry action.
WRONG_ACTION_BITES = {
    "MnF2": {"transpose": False, "det": True, "epsilon": True},
    "Cr2O3": {"transpose": False, "det": False, "epsilon": False},
    "Ca3LiOsO6": {"transpose": False, "det": True, "epsilon": False},
    "Mn3O4": {"transpose": False, "det": False, "epsilon": False},
    "LaMnO3": {"transpose": False, "det": True, "epsilon": False},
    "GdB4": {"transpose": False, "det": True, "epsilon": True},
    "Cd2Os2O7": {"transpose": False, "det": True, "epsilon": True},
    "YMnO3": {"transpose": True, "det": True, "epsilon": False},
    "ScMnO3-P63cm": {"transpose": True, "det": True, "epsilon": True},
    "ScMnO3-P63": {"transpose": False, "det": False, "epsilon": False},
    "DyFeO3-Pnpapb21": {"transpose": False, "det": False, "epsilon": False},
    "DyFeO3-P212121": {"transpose": False, "det": False, "epsilon": False},
    "U3Ru4Al12": {"transpose": True, "det": True, "epsilon": True},
    "Ca3Co2-xMnxO6": {"transpose": False, "det": False, "epsilon": False},
    "YBa2Cu3O6+a": {"transpose": False, "det": True, "epsilon": True},
    "Gd5Ge4": {"transpose": False, "det": True, "epsilon": True},
    "FePO4": {"transpose": False, "det": False, "epsilon": False},
    "Sr2IrO4": {"transpose": False, "det": False, "epsilon": True},
    "NiO": {"transpose": False, "det": True, "epsilon": True},
    "EuTiO3": {"transpose": False, "det": True, "epsilon": True},
}

GENERIC_SITE = (0.1234, 0.5678, 0.9137)


def _site(values) -> list[float]:
    return [float(v) for v in values]


def _probe_lattice(group: MagneticGroup) -> np.ndarray:
    """A metric the group leaves invariant, as row vectors for spglib.

    The Reynolds average of a generic metric over the point group, exactly as
    ``wyckoff._compatible_lattice`` builds one for the nuclear probe cell: it
    is compatible with whatever setting the operators are in and needs no
    per-system case table.
    """
    g0 = np.array([[1.00, 0.05, 0.02], [0.05, 1.21, 0.03], [0.02, 0.03, 1.44]])
    rots = [op.matrix.astype(np.float64) for op in group.all_operations()]
    g = sum(r.T @ g0 @ r for r in rots) / len(rots)
    return (np.linalg.cholesky(g).T * 4.0).T


# ---------------------------------------------------------------------------
# the magCIF string form
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    # the two examples the COMCIFS magnetic_dic gives for
    # _space_group_symop_magn_operation.xyz, plus the centring one
    "x+1/2,y+1/2,z,-1", "-y,x,z+1/2,-1", "-y,x,z+1/2,+1",
    "x,y,z,+1", "-x,y+1/2,-z,-1", "x-y+2/3,-y+1/3,-z+5/6,-1",
])
def test_operation_string_round_trip(text):
    op = MagneticOperator.from_xyz(text)
    assert op.xyz() == text
    assert MagneticOperator.from_xyz(op.xyz()) == op


@pytest.mark.parametrize("text, fragment", [
    ("-x,y+1/2,-z", "four"),                       # no time-reversal field
    ("-x,y+1/2,-z,0", "time-reversal field"),
    ("-x,y+1/2,-z,-1,+1", "four"),
    ("-x,y/2,-z,+1", "non-integral rotation"),
    ("-x,w,-z,+1", "not one of x, y, z"),
])
def test_operation_string_refusals_name_the_problem(text, fragment):
    with pytest.raises(ValueError, match=fragment):
        MagneticOperator.from_xyz(text)


def test_time_reversal_plus_one_is_written_with_its_sign():
    """magCIF's own examples write ``+1``; ``1`` parses and canonicalises to it."""
    assert MagneticOperator.from_xyz("x,y,z,1").xyz() == "x,y,z,+1"


def test_composition_follows_the_coordinate_action():
    a = MagneticOperator.from_xyz("-y,x,z+1/2,-1")       # 4_2 screw along c
    b = MagneticOperator.from_xyz("x+1/2,y+1/2,z+1/2,+1")  # I centring
    x = np.array([0.1, 0.2, 0.3])
    assert np.allclose((a * b).act_on_site(x), a.act_on_site(b.act_on_site(x)))
    assert (a * b).time_reversal == a.time_reversal * b.time_reversal


# ---------------------------------------------------------------------------
# the axial action
# ---------------------------------------------------------------------------
def test_a_moment_is_axial_and_a_displacement_is_not():
    """The signature of an axial vector, on the two operations that show it.

    Under a mirror ⊥ c (``x,y,-z``) a *displacement* along c reverses and a
    *moment* along c does not: det(R) = −1 undoes the sign.  Under a 2-fold
    along c (``-x,-y,z``) both are unchanged.  Time reversal flips the moment
    and leaves the displacement alone.  Halpern & Johnson (1939), Phys. Rev.
    55, 898.
    """
    mirror = MagneticOperator.from_xyz("x,y,-z,+1")
    two_fold = MagneticOperator.from_xyz("-x,-y,z,+1")
    primed = MagneticOperator.from_xyz("x,y,z,-1")
    c = np.array([0.0, 0.0, 1.0])
    assert np.allclose(mirror.matrix @ c, [0, 0, -1])       # displacement
    assert np.allclose(mirror.act_on_moment(c), [0, 0, 1])  # moment
    assert np.allclose(two_fold.matrix @ c, [0, 0, 1])
    assert np.allclose(two_fold.act_on_moment(c), [0, 0, 1])
    assert np.allclose(primed.act_on_moment(c), [0, 0, -1])


def test_moment_matrix_is_untransposed():
    """The Rᵀ trap, stated as an assertion rather than as a comment.

    A trigonal 2-fold along **a** is not a symmetric matrix, so R and Rᵀ are
    different matrices — and both are perfectly good group elements, which is
    the whole difficulty.
    """
    op = MagneticOperator.from_xyz("x-y,-y,-z,+1")
    assert not np.array_equal(op.matrix, op.matrix.T)
    assert np.array_equal(op.moment_matrix(), op.determinant * op.matrix)


# ---------------------------------------------------------------------------
# the whole database
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def all_groups():
    """Every one of the 1651 magnetic space groups, built once.

    Building one runs the closure check, so this fixture *is* the closure
    assertion for the whole database; ``test_every_group_closes`` states it.
    """
    return [magnetic_group(uni) for uni in range(1, N_MAGNETIC_SPACE_GROUPS + 1)]


def test_every_group_closes_and_splits_into_the_two_magcif_loops(all_groups):
    assert len(all_groups) == 1651
    for uni, group in enumerate(all_groups, 1):
        ops, centerings = group.xyz_strings()
        assert IDENTITY in group.centerings, uni
        assert group.order == len(ops) * len(centerings), uni
        # from_operations already refused a non-closed list; re-stating the
        # split here is what pins the *loops* rather than only the group
        assert MagneticGroup.from_xyz(ops, centerings).all_operations() == \
            group.all_operations()


def test_string_round_trip_is_byte_stable_over_the_whole_database(all_groups):
    total = 0
    for group in all_groups:
        for op in group.all_operations():
            text = op.xyz()
            assert MagneticOperator.from_xyz(text).xyz() == text
            total += 1
    assert total == 38307, "the database's operation count moved"


def test_identification_round_trips_except_three_broken_database_entries(
        all_groups):
    """operators → UNI number, for every group, with the exceptions named.

    Three of spglib 2.7.0's own database entries cannot be matched back to
    themselves.  Asserting the exact set fails in **both** directions: a fourth
    failure is a regression, and the set emptying means spglib fixed the
    database and this test should be simplified.  See
    ``UNI_NOT_IDENTIFIABLE`` for the evidence that these are database defects
    (282 and 284 are labelled BNS 37.x, the Ccc2 family, while their unprimed
    subgroups identify as Cmc2_1) and not a convention this module should
    absorb.
    """
    failures = []
    for uni, group in enumerate(all_groups, 1):
        try:
            if group.identify().uni_number != uni:
                failures.append(uni)
        except ValueError:
            failures.append(uni)
    assert tuple(failures) == UNI_NOT_IDENTIFIABLE


def test_the_broken_entries_are_broken_in_the_way_recorded():
    """Why :data:`UNI_NOT_IDENTIFIABLE` is spglib's problem and not ours.

    For a **type IV** group the unprimed subgroup *is* the family space group,
    so its number must be the first part of the BNS number.  Over the 977 type
    I/II/IV entries that holds everywhere except UNI 282 and 284.
    """
    mismatched = []
    for uni in range(1, N_MAGNETIC_SPACE_GROUPS + 1):
        t = spglib.get_magnetic_spacegroup_type(uni)
        if t.type == 3:      # type III's unprimed part is an index-2 subgroup
            continue
        data = spglib.get_magnetic_symmetry_from_database(uni)
        keep = ~np.asarray(data["time_reversals"], dtype=bool)
        st = spglib.get_spacegroup_type_from_symmetry(
            data["rotations"][keep], data["translations"][keep],
            lattice=np.diag([5.0, 7.0, 11.0]))
        if st is None or int(st.number) != int(t.number):
            mismatched.append(uni)
    assert mismatched == [282, 284]


# ---------------------------------------------------------------------------
# resolving a number
# ---------------------------------------------------------------------------
def test_uni_bns_and_og_numbers_reach_the_same_group():
    by_uni = magnetic_group(1159)
    assert by_uni.bns_number == "136.499"
    assert magnetic_group("136.499").all_operations() == by_uni.all_operations()
    assert magnetic_group(by_uni.og_number).all_operations() == \
        by_uni.all_operations()
    assert magnetic_group("1159").all_operations() == by_uni.all_operations()


def test_a_shubnikov_symbol_is_refused_by_name_not_guessed():
    with pytest.raises(ValueError, match="never a Shubnikov symbol"):
        magnetic_group("P4_2'/mnm'")


@pytest.mark.parametrize("spec", [0, 1652, "999.999"])
def test_a_number_outside_the_tables_is_refused(spec):
    with pytest.raises(ValueError):
        magnetic_group(spec)


# ---------------------------------------------------------------------------
# canonicalisation refusals
# ---------------------------------------------------------------------------
def test_an_unclosed_list_is_refused_and_the_missing_product_is_named():
    # the first three of P4_2'/mnm' are not a subgroup (the first four are, so
    # a truncation is not automatically a counter-example)
    ops = [MagneticOperator.from_xyz(s) for s in MNF2_OPS[:3]]
    with pytest.raises(ValueError, match="not closed.*-x,-y,z"):
        MagneticGroup.from_operations(ops)


def test_a_list_without_the_identity_is_refused():
    ops = [op for op in magnetic_group("136.499").all_operations()
           if op != IDENTITY]
    with pytest.raises(ValueError, match="no identity"):
        MagneticGroup.from_operations(ops)


def test_a_rotation_in_the_centring_loop_is_refused():
    with pytest.raises(ValueError, match="centring loop"):
        MagneticGroup.from_xyz(("x,y,z,+1",), ("x,y,z,+1", "-x,-y,z,+1"))


# ---------------------------------------------------------------------------
# settings and the (P, p) transform
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "a,b,c;0,0,0",
    "-a/3-2b/3-2c/3,-a,a/3+2b/3-c/3;0,1/2,0",
    "b,c,a;0,0,0",
    "-a,b,-a-c;0,0,0",
    "-a+b,c,a+b;1/2,1,1/2",
])
def test_transform_string_round_trip(text):
    p, shift = parse_transform(text)
    assert format_transform(p, shift) == text
    assert parse_transform(format_transform(p, shift)) == (p, shift)


def test_transform_refusals():
    with pytest.raises(ValueError, match="no ';'"):
        parse_transform("a,b,c")
    with pytest.raises(ValueError, match="singular"):
        parse_transform("a,b,a;0,0,0")
    with pytest.raises(ValueError, match="mentions a basis vector"):
        parse_transform("a,b,c;a,0,0")


def test_the_transform_reproduces_a_published_operator_list():
    """BNS standard → the setting a published magCIF is written in.

    Ca₃LiOsO₆ is stated under BNS 15.89 (C2'/c') in the *trigonal parent* cell
    of R-3c, with ``transform_BNS_Pp_abc`` carrying the two apart.  Carrying
    spglib's BNS-setting operators through that transform must give back the
    published twelve operations exactly — a check on the conjugation, on the
    origin shift, and on the lattice completion at once, since |det P| = 2/3
    and the two cells hold different numbers of lattice points.

    Calder et al. (2012), Phys. Rev. B 86, 054403; record MAGNDATA #0.3.
    """
    published = MagneticGroup.from_xyz(CA3LIOSO6_OPS)
    carried = magnetic_group("15.89").transformed(
        "-a/3-2b/3-2c/3,-a,a/3+2b/3-c/3;0,1/2,0")
    assert set(carried.all_operations()) == set(published.all_operations())
    assert carried.order == 12 and magnetic_group("15.89").order == 8


def test_a_transform_that_forgets_the_lattice_is_refused():
    """|G| and the cell volume pin each other, so a partial transform raises.

    The failure this guards is silent otherwise: conjugating the operators
    without adding the images of the new basis vectors gives a *subgroup*
    wearing the right symbol, and every site multiplicity derived from it is
    wrong by the index.
    """
    group = magnetic_group("15.89")
    with pytest.raises(ValueError, match="not a cell of this group"):
        # three times the cell along c is not a cell of this group
        group.transformed("a,b,3c;0,0,0")


def test_setting_decides_whether_a_published_moment_fits():
    """The origin-choice trap, measured on a published structure.

    Cd₂Os₂O₇ orders all-in-all-out under BNS 227.131 (Fd-3m') with the Os
    moment along [111] at (0,0,0) — which is **origin choice 2**.  spglib's
    database default for that group is origin choice 1, where (0,0,0) has site
    symmetry -43m and carries no moment at all.  Nothing in the operator round
    trip can see this: spglib identifies its own output as 227.131 in either
    setting.  Only the moment does.

    This is the magnetic twin of the spinel origin-choice trap the nuclear side
    already carries (``symmetry.setting_alternatives``, issue #217).

    Yamaura et al. (2012), Phys. Rev. Lett. 108, 247205; record MAGNDATA #0.2.
    """
    settings = database_settings("227.131")
    assert [(s.choice, s.is_default) for s in settings] == [("1", True),
                                                            ("2", False)]
    default = magnetic_group("227.131")
    choice_two = magnetic_group("227.131", hall_number=526)
    assert default.identify().bns_number == choice_two.identify().bns_number

    moment = (0.6, 0.6, 0.6)
    assert len(default.allowed_moment_basis((0, 0, 0))) == 0
    assert not in_span(default.allowed_moment_basis((0, 0, 0)), moment)
    assert in_span(choice_two.allowed_moment_basis((0, 0, 0)), moment)


def test_database_settings_names_the_alternatives():
    assert [s.choice for s in database_settings("167.106")] == ["H", "R"]
    assert [s.hall_number for s in database_settings("136.499")] == [419]


# ---------------------------------------------------------------------------
# the positive arm: published operators, published moments
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "label, ops, centerings, bns, msg_type, site, moment, citation, record",
    TYPED_OPERATORS,
    ids=[row[0] for row in TYPED_OPERATORS])
def test_typed_operator_list_identifies_as_the_published_group(
        label, ops, centerings, bns, msg_type, site, moment, citation, record):
    """Operator strings from outside this package, identified.

    The list was transcribed from the published record rather than generated
    from spglib, which is what makes this a check on the *database's* setting
    and not on its self-consistency.  Two of the four (Ca₃LiOsO₆, Mn₃O₄) are
    in settings the BNS standard reaches only through a transform, so if
    spglib's identification were setting-bound they would fail here.
    """
    group = MagneticGroup.from_xyz(ops, centerings)
    ident = group.identify()
    assert ident.bns_number == bns, citation
    assert ident.msg_type == msg_type


@pytest.mark.parametrize(
    "label, ops, centerings, bns, msg_type, site, moment, citation, record",
    TYPED_OPERATORS,
    ids=[row[0] for row in TYPED_OPERATORS])
def test_published_moment_lies_in_the_derived_span_typed(
        label, ops, centerings, bns, msg_type, site, moment, citation, record):
    """**Span, never dimension** — the assertion the whole module turns on."""
    group = MagneticGroup.from_xyz(ops, centerings)
    basis = group.allowed_moment_basis(site)
    assert in_span(basis, moment), (
        f"{label}: the moment {moment} μ_B measured by {citation} (record "
        f"{record}) is not in the span {basis.tolist()} derived from its own "
        f"published operator list")


@pytest.mark.parametrize("row", PUBLISHED_MOMENTS,
                         ids=[row[0] for row in PUBLISHED_MOMENTS])
def test_published_moment_lies_in_the_derived_span_from_the_database(row):
    """Sixteen more published structures, in the settings they are stated in.

    Ten of the sixteen carry a non-identity ``transform_BNS_Pp_abc``, so the
    span is derived in the *file's* setting and not in the database's — which
    is the case a round trip against spglib alone cannot reach.
    """
    label, bns, hall, transform, msg_type, site, moment, span, citation, record \
        = row
    group = published_group(row)
    assert group.identify().bns_number == bns
    assert group.identify().msg_type == msg_type
    basis = group.allowed_moment_basis(site)
    assert basis.tolist() == span
    assert in_span(basis, moment), (
        f"{label}: {citation} (record {record}) puts the moment at {moment} "
        f"μ_B, outside the derived span {basis.tolist()}")


PUBLISHED_TRANSPOSE_CONTROLS = [row for row in PUBLISHED_MOMENTS
                                if WRONG_ACTION_BITES[row[0]]["transpose"]]


@pytest.mark.parametrize("row", PUBLISHED_TRANSPOSE_CONTROLS,
                         ids=[row[0] for row in PUBLISHED_TRANSPOSE_CONTROLS])
def test_a_published_moment_is_excluded_by_the_transposed_action(row):
    """The Rᵀ negative control on published structures, with the numbers.

    All three are hexagonal with an in-plane moment, which is the only shape
    where the trap is visible at all: YMnO₃'s Mn is allowed along [1 2 0] and
    the transposed action offers [0 1 0] instead, so the measured
    (1.68, 3.36, 0) μ_B is outside it.  Same for ScMnO₃ ([1 0 0] against
    [2 -1 0]) and U₃Ru₄Al₁₂ ([0 1 0] against [1 -2 0]).

    The dimension is identical in every case, so a degrees-of-freedom check
    passes with the wrong action; only the span fails.
    """
    label, bns, hall, transform, msg_type, site, moment, span, citation, record \
        = row
    group = published_group(row)
    stabilizer = group.site_stabilizer(site)
    correct = allowed_moment_basis(stabilizer)
    transposed = allowed_moment_basis(stabilizer, transpose=True)
    assert len(correct) == len(transposed), "the trap keeps the dimension"
    assert in_span(correct, moment)
    assert not in_span(transposed, moment), (
        f"{label}: the transposed action still admits the moment "
        f"{moment} μ_B of {citation}, so this row is not a control")


def test_a_published_moment_propagates_consistently_over_its_orbit():
    """MnF₂: the two Mn are antiparallel because the symmetry says so.

    Erickson (1953), Phys. Rev. 90, 779, established the rutile-fluoride
    ordering; the moment magnitude and the operator list are as the record
    MAGNDATA #0.15 states them, from Yamani, Tun & Ryan (2010), Can. J. Phys.
    88, 771-797.  Nothing here is fitted: the orbit is generated from the
    operators, and the *sign* on the body-centre site is the test.
    """
    group = MagneticGroup.from_xyz(MNF2_OPS)
    positions, moments = group.site_orbit((0, 0, 0), (0, 0, 4.6))
    assert len(positions) == 2
    order = np.argsort(positions[:, 0])
    assert np.allclose(positions[order], [[0, 0, 0], [0.5, 0.5, 0.5]])
    assert np.allclose(moments[order], [[0, 0, 4.6], [0, 0, -4.6]])


def test_a_moment_outside_the_span_is_refused_rather_than_averaged():
    group = MagneticGroup.from_xyz(MNF2_OPS)
    with pytest.raises(ValueError, match="outside the allowed subspace"):
        group.site_orbit((0, 0, 0), (4.6, 0, 0))


# ---------------------------------------------------------------------------
# the positive arm without any published number: spglib as an outside oracle
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("uni, bns, msg_type, site, span", COVERAGE,
                         ids=[f"{row[1]}-type{row[2]}" for row in COVERAGE])
def test_derived_span_reproduces_the_group(uni, bns, msg_type, site, span):
    """Derived subspace → a magnetic structure → the same UNI number.

    The independent arm.  A moment is taken from the derived span, propagated
    over the site orbit by *this* module's axial action, converted to the
    Cartesian frame spglib expects, and handed with a generic dummy orbit to
    ``spglib.get_magnetic_symmetry_dataset``, which implements the axial action
    in its own C code and knows nothing of the span.  It must come back with
    the group we started from: a subspace derived with the wrong action does
    not survive this, because the moment it offers cannot even be assigned
    consistently to the orbit.

    Twenty-three rows: all four magnetic space-group types except grey (which
    allows no moment at all — ``test_a_grey_group_forbids_every_moment``),
    over every crystal system whose site symmetry constrains a moment.
    """
    group = magnetic_group(uni)
    assert group.bns_number == bns
    assert group.identify().msg_type == msg_type
    basis = group.allowed_moment_basis(_site(site))
    assert basis.tolist() == span
    assert 0 < len(basis) < 3

    weights = np.array([1.0, 0.37, 0.11])[:len(basis)]
    moment = weights @ basis.astype(np.float64)
    positions, moments = group.site_orbit(_site(site), moment)
    dummy, _ = group.site_orbit(GENERIC_SITE)

    lattice = _probe_lattice(group)
    columns = lattice.T
    unit = np.diag(1.0 / np.linalg.norm(columns, axis=0))
    cartesian = (columns @ unit @ moments.T).T
    dataset = spglib.get_magnetic_symmetry_dataset(
        (lattice, np.vstack([positions, dummy]),
         [1] * len(positions) + [2] * len(dummy),
         np.vstack([cartesian, np.zeros((len(dummy), 3))])),
        is_axial=True, symprec=1e-5)
    assert dataset is not None
    assert dataset.uni_number == uni


def test_the_coverage_table_spans_the_four_msg_types():
    assert {row[2] for row in COVERAGE} | {2} == {1, 2, 3, 4}
    # twenty published magnetic structures, each cited to its original paper
    assert len(TYPED_OPERATORS) + len(PUBLISHED_MOMENTS) == 20
    published_types = ({row[4] for row in TYPED_OPERATORS}
                       | {row[4] for row in PUBLISHED_MOMENTS})
    # no published row is type II and none can be: a grey group forbids every
    # ordered moment, so GREY_GROUPS carries that type instead
    assert published_types == {1, 3, 4}
    assert {row[1] for row in GREY_GROUPS} and all(
        magnetic_group(uni).is_grey for uni, _ in GREY_GROUPS)


@pytest.mark.parametrize("uni, bns", GREY_GROUPS, ids=[r[1] for r in GREY_GROUPS])
def test_a_grey_group_forbids_every_moment(uni, bns):
    """Type II carries 1', so a moment equals its own negative everywhere."""
    group = magnetic_group(uni)
    assert group.bns_number == bns
    assert group.is_grey
    assert TIME_REVERSAL in group.all_operations()
    for site in [(0, 0, 0), (0.25, 0.25, 0.25), GENERIC_SITE]:
        assert len(group.allowed_moment_basis(site)) == 0


# ---------------------------------------------------------------------------
# the negative controls: each wrong action must exclude a real moment
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("label, bites", list(WRONG_ACTION_BITES.items()))
def test_each_fixture_declares_which_wrong_actions_it_can_catch(label, bites):
    """What each published fixture *can* prove about the action, measured.

    A control that cannot fail confirms whatever you hoped, so the reach of
    each fixture is written down and asserted rather than assumed.  The
    striking rows are the ones that catch **nothing**: Cr₂O₃'s 12c stabiliser
    is a single 3-fold about c, and Mn₃O₄'s magnetic site is general, so their
    derived subspaces are identical under all three wrong actions.  A suite
    whose only magnetic fixtures were those two would pass with the moment
    treated as a polar, time-even vector.

    Asserted exactly, so a fixture that starts or stops discriminating shows
    up here rather than silently weakening a control elsewhere.
    """
    lookup = dict(
        [(row[0], (MagneticGroup.from_xyz(row[1], row[2]), row[5]))
         for row in TYPED_OPERATORS]
        + [(row[0], (published_group(row), row[5]))
           for row in PUBLISHED_MOMENTS])
    group, site = lookup[label]
    stabilizer = group.site_stabilizer(site)
    right = allowed_moment_basis(stabilizer)
    measured = {
        "transpose": not np.array_equal(
            right, allowed_moment_basis(stabilizer, transpose=True)),
        "det": not np.array_equal(
            right, allowed_moment_basis(stabilizer, use_determinant=False)),
        "epsilon": not np.array_equal(
            right, allowed_moment_basis(stabilizer, use_time_reversal=False)),
    }
    assert measured == bites


def test_dropping_the_determinant_forbids_the_published_mnf2_moment():
    """The negative control, on a named entry, with the number it excludes.

    Under P4₂'/mnm' the Mn 2a stabiliser fixes the moment along c; treating the
    moment as a *polar* vector (dropping det R) leaves no allowed direction at
    all, so the 4.6 μ_B along c that Yamani, Tun & Ryan (2010), Can. J. Phys.
    88, 771-797 report is refused.  Same for dropping ε.
    """
    group = MagneticGroup.from_xyz(MNF2_OPS)
    stabilizer = group.site_stabilizer((0, 0, 0))
    published = (0.0, 0.0, 4.6)
    assert in_span(allowed_moment_basis(stabilizer), published)
    for wrong in ({"use_determinant": False}, {"use_time_reversal": False}):
        basis = allowed_moment_basis(stabilizer, **wrong)
        assert len(basis) == 0
        assert not in_span(basis, published)


@pytest.mark.parametrize("uni, bns, site, right, wrong", TRANSPOSE_TRAP,
                         ids=[r[1] for r in TRANSPOSE_TRAP])
def test_the_transposed_rotation_fails_the_span_test(uni, bns, site, right,
                                                     wrong):
    """Rᵀ instead of R: same dimension, different subspace, named entries.

    The allowed direction under the correct action is **a** ([1,0,0]-type) and
    under Rᵀ it is the reciprocal-axis direction ([2,-1,0]-type) — the two are
    59.999…° apart in a hexagonal cell and identical in dimension, which is why
    a degrees-of-freedom count passes with the wrong action and only a span
    test fails.

    That the correct one is correct is not asserted from this module's own
    algebra: :func:`test_derived_span_reproduces_the_group` hands the same
    moment to spglib's independent search, and BNS 150.25 and 157.55 are rows
    of that table.
    """
    group = magnetic_group(uni)
    assert group.bns_number == bns
    stabilizer = group.site_stabilizer(_site(site))
    correct = allowed_moment_basis(stabilizer)
    transposed = allowed_moment_basis(stabilizer, transpose=True)
    assert correct.tolist() == right
    assert transposed.tolist() == wrong
    assert len(correct) == len(transposed), "the trap keeps the dimension"
    allowed = np.asarray(right, dtype=np.float64)[0]
    assert in_span(correct, allowed)
    assert not in_span(transposed, allowed)


def test_the_transpose_trap_is_invisible_outside_trigonal_and_hexagonal():
    """Why the control above has to be one of the three hexagonal rows.

    Measured over all 1651 groups against a 14-site grid: R and Rᵀ give the
    same allowed subspace everywhere outside the trigonal and hexagonal
    families.  A suite whose magnetic fixtures were only rutile-, perovskite-
    or spinel-shaped would pass with the rotation transposed — which is exactly
    how WP-1020 built the whole indexing metric subspace from Rᵀ and satisfied
    its own criterion.  Seventeen of the twenty published fixtures here are in
    that blind region; this test pins two of them as blind, so a future fixture
    set that quietly dropped the hexagonal rows would not look like a control.
    """
    for ops, centerings in [(MNF2_OPS, None), (MN3O4_OPS, None)]:
        group = MagneticGroup.from_xyz(ops, centerings)
        for site in [(0, 0, 0), (0.25, 0.25, 0.25), (0.154, 0.114, 0.07)]:
            stabilizer = group.site_stabilizer(site)
            assert np.array_equal(allowed_moment_basis(stabilizer),
                                  allowed_moment_basis(stabilizer,
                                                       transpose=True))


# ---------------------------------------------------------------------------
# crystal-axis ⇄ Cartesian (decision D-3)
# ---------------------------------------------------------------------------
CELLS = [
    (4.87, 4.87, 3.31, 90.0, 90.0, 90.0),        # MnF2, tetragonal
    (4.95, 4.95, 13.58, 90.0, 90.0, 120.0),      # Cr2O3, hexagonal axes
    (5.53, 7.70, 5.53, 90.0, 90.0, 90.0),        # LaMnO3, orthorhombic
    (7.0, 8.0, 9.0, 78.0, 95.0, 103.0),          # triclinic, nothing cancels
]


@pytest.mark.parametrize("cell", CELLS, ids=[f"{c[0]}-{c[5]}" for c in CELLS])
@pytest.mark.parametrize("moment", [(0.0, 0.0, 2.48), (1.0, 1.0, 0.0),
                                    (-0.7, 2.1, 0.35)])
def test_moment_basis_round_trip(cell, moment):
    cartesian = moment_to_cartesian(moment, cell)
    assert np.allclose(moment_from_cartesian(cartesian, cell), moment,
                       atol=1e-12)
    assert np.isclose(np.linalg.norm(cartesian), moment_magnitude(moment, cell))


def test_the_crystal_axis_magnitude_is_not_the_euclidean_norm():
    """|m| = √(mᵀGm) with the *unit-vector* metric, per the COMCIFS definition.

    On hexagonal axes a moment written (1, 1, 0) is 1 μ_B, not √2: â and b̂ are
    120° apart.  Getting this wrong scales every reported moment by up to √3,
    silently, and only on non-orthogonal cells.
    """
    hexagonal = (4.95, 4.95, 13.58, 90.0, 90.0, 120.0)
    assert np.isclose(moment_magnitude((1.0, 1.0, 0.0), hexagonal), 1.0)
    assert np.isclose(moment_magnitude((0.0, 0.0, 2.48), hexagonal), 2.48)
    cubic = (4.0, 4.0, 4.0, 90.0, 90.0, 90.0)
    assert np.isclose(moment_magnitude((1.0, 1.0, 0.0), cubic), np.sqrt(2.0))


def test_gdb4_magnitude_matches_the_published_scalar():
    """A published |M| the components must reproduce, on a tetragonal cell.

    Blanco, Brown, Stunault, Katsumata, Iga & Michimura (2006), Phys. Rev. B
    73, 212411 give the Gd moment as (5.05, 5.05, 0) μ_B with |M| = 7.14 μ_B
    (record MAGNDATA #0.9); on orthogonal axes the crystal-axis metric is the
    identity and the two statements are the same number.
    """
    cell = (7.1447, 7.1447, 4.0499, 90.0, 90.0, 90.0)
    assert np.isclose(moment_magnitude((5.05, 5.05, 0.0), cell), 7.14,
                      atol=5e-3)


# ---------------------------------------------------------------------------
# identification of a bare list, and the refusal
# ---------------------------------------------------------------------------
def test_identify_accepts_a_bare_operator_list():
    ops = magnetic_group("136.499").all_operations()
    assert identify(ops).bns_number == "136.499"


def test_identify_refuses_by_name_rather_than_returning_a_wrong_group():
    """When spglib cannot match, the caller is told, and told what it means.

    UNI 283 is the entry spglib cannot match even to itself, so it is the one
    list in reach that exercises the refusal.  The message names the count and
    the known-broken set, because a refusal here is not necessarily the
    caller's fault.
    """
    group = magnetic_group(283)
    with pytest.raises(ValueError, match="did not match.*282, 283, 284"):
        group.identify()
