"""Wyckoff classes derived from the operators, and composition → site-class assignments.

Expected values, and how each was checked:

* ``ITA`` below is International Tables A (Hahn ed., 2005), Part 7, typed for
  twelve types in fourteen settings (letters, multiplicities, a coordinate
  triplet).  The triplet's free letters give the free-parameter dimension.  No
  table file is held, so the same rows are checked two more ways: the letters
  against spglib as a black box (through ``wyckoff.site_constraints``, which the
  package already uses to name sites), and each triplet against the package's
  own ``site_orbit`` and ``coordinate_basis``.  ``test_every_setting_matches_spglib``
  extends the spglib check to all 564 gemmi settings.
* The assignment counts are derived by hand in each test's comment.
* Only public space groups and synthetic compositions; no archive data.
"""

from __future__ import annotations

import itertools
import re

import gemmi
import numpy as np
import pytest

from rietx.crystallography.site_classes import (
    MAX_SITE_ASSIGNMENTS,
    SiteAssignmentCapError,
    _letter_rank,
    count_site_assignments,
    holds,
    site_assignments,
    site_classes,
)
from rietx.crystallography.symmetry import OperatorGroup, get_spacegroup, site_orbit
from rietx.crystallography.wyckoff import coordinate_basis, site_constraints

# setting → [(wyckoff, ITA coordinate triplet)], International Tables order
ITA = {
    "P-1": [("1a", "0,0,0"), ("1b", "0,0,1/2"), ("1c", "0,1/2,0"), ("1d", "1/2,0,0"),
            ("1e", "1/2,1/2,0"), ("1f", "1/2,0,1/2"), ("1g", "0,1/2,1/2"),
            ("1h", "1/2,1/2,1/2"), ("2i", "x,y,z")],
    "P21/c": [("2a", "0,0,0"), ("2b", "1/2,0,0"), ("2c", "0,0,1/2"), ("2d", "1/2,0,1/2"),
              ("4e", "x,y,z")],
    "C2/m": [("2a", "0,0,0"), ("2b", "0,1/2,0"), ("2c", "0,0,1/2"), ("2d", "0,1/2,1/2"),
             ("4e", "1/4,1/4,0"), ("4f", "1/4,1/4,1/2"), ("4g", "0,y,0"), ("4h", "0,y,1/2"),
             ("4i", "x,0,z"), ("8j", "x,y,z")],
    "Pnma": [("4a", "0,0,0"), ("4b", "0,0,1/2"), ("4c", "x,1/4,z"), ("8d", "x,y,z")],
    "Imma": [("4a", "0,0,0"), ("4b", "0,0,1/2"), ("4c", "1/4,1/4,1/4"), ("4d", "1/4,1/4,3/4"),
             ("4e", "0,1/4,z"), ("8f", "x,0,0"), ("8g", "1/4,y,1/4"), ("8h", "0,y,z"),
             ("8i", "x,1/4,z"), ("16j", "x,y,z")],
    "P42/mnm": [("2a", "0,0,0"), ("2b", "0,0,1/2"), ("4c", "0,1/2,0"), ("4d", "0,1/2,1/4"),
                ("4e", "0,0,z"), ("4f", "x,x,0"), ("4g", "x,-x,0"), ("8h", "0,1/2,z"),
                ("8i", "x,y,0"), ("8j", "x,x,z"), ("16k", "x,y,z")],
    "I4/mmm": [("2a", "0,0,0"), ("2b", "0,0,1/2"), ("4c", "0,1/2,0"), ("4d", "0,1/2,1/4"),
               ("4e", "0,0,z"), ("8f", "1/4,1/4,1/4"), ("8g", "0,1/2,z"), ("8h", "x,x,0"),
               ("8i", "x,0,0"), ("8j", "x,1/2,0"), ("16k", "x,x+1/2,1/4"), ("16l", "x,y,0"),
               ("16m", "x,x,z"), ("16n", "0,y,z"), ("32o", "x,y,z")],
    "R-3m:H": [("3a", "0,0,0"), ("3b", "0,0,1/2"), ("6c", "0,0,z"), ("9d", "1/2,0,1/2"),
               ("9e", "1/2,0,0"), ("18f", "x,0,0"), ("18g", "x,0,1/2"), ("18h", "x,-x,z"),
               ("36i", "x,y,z")],
    # the same type on rhombohedral axes: one third of every multiplicity
    "R-3m:R": [("1a", "0,0,0"), ("1b", "1/2,1/2,1/2"), ("2c", "x,x,x"), ("3d", "1/2,0,0"),
               ("3e", "0,1/2,1/2"), ("6f", "x,-x,0"), ("6g", "x,-x,1/2"), ("6h", "x,x,z"),
               ("12i", "x,y,z")],
    "P63/mmc": [("2a", "0,0,0"), ("2b", "0,0,1/4"), ("2c", "1/3,2/3,1/4"),
                ("2d", "1/3,2/3,3/4"), ("4e", "0,0,z"), ("4f", "1/3,2/3,z"), ("6g", "1/2,0,0"),
                ("6h", "x,2x,1/4"), ("12i", "x,0,0"), ("12j", "x,y,1/4"), ("12k", "x,2x,z"),
                ("24l", "x,y,z")],
    "Pm-3m": [("1a", "0,0,0"), ("1b", "1/2,1/2,1/2"), ("3c", "0,1/2,1/2"), ("3d", "1/2,0,0"),
              ("6e", "x,0,0"), ("6f", "x,1/2,1/2"), ("8g", "x,x,x"), ("12h", "x,1/2,0"),
              ("12i", "0,y,y"), ("12j", "1/2,y,y"), ("24k", "0,y,z"), ("24l", "1/2,y,z"),
              ("24m", "x,x,z"), ("48n", "x,y,z")],
    # 96h: typed first as "1/4,y,-y", then "0,y,-y"; the seam test below showed
    # the first is not a 2-fold axis and the second lies on a mirror (96g) in
    # this origin; "1/8,y,-y+1/4" is the row that passes it
    "Fd-3m:1": [("8a", "0,0,0"), ("8b", "1/2,1/2,1/2"), ("16c", "1/8,1/8,1/8"),
                ("16d", "5/8,5/8,5/8"), ("32e", "x,x,x"), ("48f", "x,0,0"), ("96g", "x,x,z"),
                ("96h", "1/8,y,-y+1/4"), ("192i", "x,y,z")],
    "Fd-3m:2": [("8a", "1/8,1/8,1/8"), ("8b", "3/8,3/8,3/8"), ("16c", "0,0,0"),
                ("16d", "1/2,1/2,1/2"), ("32e", "x,x,x"), ("48f", "x,1/8,1/8"),
                ("96g", "x,x,z"), ("96h", "0,y,-y"), ("192i", "x,y,z")],
    "Ia-3d": [("16a", "0,0,0"), ("16b", "1/8,1/8,1/8"), ("24c", "1/8,0,1/4"),
              ("24d", "3/8,0,1/4"), ("32e", "x,x,x"), ("48f", "x,0,1/4"),
              ("48g", "1/8,y,-y+1/4"), ("96h", "x,y,z")],
}

# generic values for the free letters of a triplet: no special relation between them
_GENERIC = {"x": 0.0831, "y": 0.1907, "z": 0.3163}


def _dof(triplet: str) -> int:
    return len(set(re.findall("[xyz]", triplet)))


def _evaluate(triplet: str) -> np.ndarray:
    out = []
    for part in triplet.split(","):
        expr = part
        for v, val in _GENERIC.items():
            expr = re.sub(rf"(\d)({v})", rf"\1*{val}", expr).replace(v, repr(val))
        out.append(eval(expr, {"__builtins__": {}}))   # the table's own literals only
    return np.array(out, dtype=np.float64) % 1.0


@pytest.mark.parametrize("setting", list(ITA))
def test_classes_match_international_tables(setting):
    classes = site_classes(setting)
    assert [(c.wyckoff, c.dof) for c in classes] == [(w, _dof(t)) for w, t in ITA[setting]]
    assert [c.multiplicity for c in classes] == [int(w[:-1]) for w, _ in ITA[setting]]
    # the general position is last, with every operation of the conventional cell
    assert classes[-1].dof == 3
    assert classes[-1].multiplicity == len(get_spacegroup(setting).operations())



#: One space group per crystal class (WP-2033): the Wyckoff multiplicities in
#: letter order, a first, as International Tables A prints them in the
#: Positions block, with the printed page.  Read from the page images of
#: Vol. A, 5th ed. (Hahn ed., 2002, the held copy), unique axis b and cell
#: choice 1 for the monoclinic groups, origin choice 2 for I 4₁/a m d, hexagonal
#: axes for R -3.  The derivation reads none of this; the transcription's
#: record (two readings, five planted-error checks) is kept outside the tree.
ITA_BY_CLASS = {
    "P 1": (113, (1,)),
    "P -1": (115, (1, 1, 1, 1, 1, 1, 1, 1, 2)),
    "C 1 2 1": (125, (2, 2, 4)),
    "C 1 m 1": (145, (2, 4)),
    "P 1 21/m 1": (165, (2, 2, 2, 2, 2, 4)),
    "F 2 2 2": (213, (4, 4, 4, 4, 8, 8, 8, 8, 8, 8, 16)),
    "C m m 2": (239, (2, 2, 4, 4, 4, 8)),
    "C m c m": (301, (4, 4, 4, 8, 8, 8, 8, 16)),
    "P 4": (332, (1, 1, 2, 4)),
    "P -4": (341, (1, 1, 1, 1, 2, 2, 2, 4)),
    "I 4/m": (357, (2, 2, 4, 4, 4, 8, 8, 8, 16)),
    "I 4 2 2": (379, (2, 2, 4, 4, 4, 8, 8, 8, 8, 8, 16)),
    "P 4 m m": (383, (1, 1, 2, 4, 4, 4, 8)),
    "P -4 21 m": (411, (2, 2, 2, 4, 4, 8)),
    "I 41/a m d:2": (485, (4, 4, 8, 8, 8, 16, 16, 16, 32)),
    "P 3": (491, (1, 1, 1, 3)),
    "R -3:H": (501, (3, 3, 6, 9, 9, 18)),
    "P 3 2 1": (507, (1, 1, 2, 2, 3, 3, 6)),
    "P 3 m 1": (521, (1, 1, 1, 3, 6)),
    "P -3 m 1": (541, (1, 1, 2, 2, 3, 3, 6, 6, 6, 12)),
    "P 6": (553, (1, 2, 3, 6)),
    "P -6": (561, (1, 1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 6)),
    "P 6/m": (563, (1, 1, 2, 2, 2, 3, 3, 4, 6, 6, 6, 12)),
    "P 6 2 2": (567, (1, 1, 2, 2, 2, 3, 3, 4, 6, 6, 6, 6, 6, 12)),
    "P 6 m m": (579, (1, 2, 3, 6, 6, 12)),
    "P -6 m 2": (587, (1, 1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 6, 6, 6, 12)),
    "P 6/m m m": (595, (1, 1, 2, 2, 2, 3, 3, 4, 6, 6, 6, 6, 6, 12, 12, 12, 12, 24)),
    "F 2 3": (605, (4, 4, 4, 4, 16, 24, 24, 48)),
    "P a -3": (631, (4, 4, 8, 24)),
    "P 43 3 2": (649, (4, 4, 8, 12, 24)),
    "F -4 3 m": (659, (4, 4, 4, 4, 16, 24, 24, 48, 96)),
    "I a -3 d": (717, (16, 16, 24, 24, 32, 48, 48, 96)),
}


def test_the_by_class_list_has_one_group_per_crystal_class():
    classes = [get_spacegroup(s).point_group_hm() for s in ITA_BY_CLASS]
    assert len(set(classes)) == len(classes) == 32


@pytest.mark.parametrize("setting", list(ITA_BY_CLASS))
def test_orbit_sizes_match_international_tables_on_every_crystal_class(setting):
    page, expected = ITA_BY_CLASS[setting]
    derived = [c.multiplicity for c in site_classes(setting)]
    # site_classes lists the general position last, ITA's letter order
    assert tuple(derived) == expected, f"ITA A p. {page}"


def test_holds_is_a_placement_existing():
    """``holds`` answers what :func:`count_site_assignments` counts, for every
    count up to twice the general multiplicity: the existence question needs
    no count."""
    for setting in ("F m -3 m", "P 1 21/m 1", "I 21 3", "P 6/m m m", "P -1"):
        classes = site_classes(setting)
        top = 2 * max(c.multiplicity for c in classes)
        for n in range(1, top + 1):
            assert holds(classes, n) == (
                count_site_assignments(classes, {"Si": n}) > 0), (setting, n)

@pytest.mark.parametrize("setting", list(ITA))
def test_ita_triplets_through_the_existing_site_seam(setting):
    """Each tabulated triplet, at generic x,y,z, has the row's multiplicity and dof.

    This checks the typed table against ``site_orbit`` and ``coordinate_basis``
    independently of the grid derivation, so a typo in ``ITA`` shows up here
    and not only as a class-list mismatch.
    """
    for wyckoff, triplet in ITA[setting]:
        orbit = site_orbit(get_spacegroup(setting), _evaluate(triplet))
        assert orbit.multiplicity == int(wyckoff[:-1]), (wyckoff, triplet)
        assert coordinate_basis(list(orbit.stabilizer)).shape[0] == _dof(triplet)


@pytest.mark.parametrize("setting", ["C2/m", "P42/mnm", "R-3m:H", "P63/mmc", "Fd-3m:2"])
def test_every_point_of_a_class_is_that_class(setting):
    """The letter and multiplicity belong to the whole subspace, not the representative.

    At generic u, x(u) must have the class's multiplicity and letter under the
    existing ``site_constraints``.  Every orbit image must also be the same
    class, the ``multiplicity`` images must be distinct, and they must be what
    ``site_orbit`` expands x(u) to.  Each basis
    vector must be fixed exactly by every stabiliser rotation.
    """
    sg = get_spacegroup(setting)
    rng = np.random.default_rng(7)
    for c in site_classes(setting):
        for r in c.stabilizer:
            assert np.array_equal(c.basis @ r.T, c.basis)
        u = rng.uniform(0.05, 0.2, c.dof)
        x = c.position(u)
        sc = site_constraints(sg, x)
        assert (sc.wyckoff, sc.multiplicity, sc.coord_basis.shape[0]) == (
            c.wyckoff, c.multiplicity, c.dof)
        images = c.orbit(u)
        assert images.shape == (c.multiplicity, 3)
        d = np.abs(images[:, None] - images[None]) % 1.0
        d = np.minimum(d, 1.0 - d).max(axis=2)
        assert np.all(d[~np.eye(len(images), dtype=bool)] > 1e-6)
        assert site_constraints(sg, images[-1]).wyckoff == c.wyckoff
        # and they are the orbit of x(u) itself, as the existing seam expands it
        expected = site_orbit(sg, x).images
        d = np.abs(images[:, None] - expected[None]) % 1.0
        assert np.all(np.minimum(d, 1.0 - d).max(axis=2).min(axis=1) < 1e-9)


@pytest.mark.slow
def test_every_setting_matches_spglib():
    """All 564 gemmi settings: our classes carry spglib's letters a, b, … exactly once each.

    spglib names the position of any point it is handed.  So if a class is
    missing, a later letter is skipped; if one class is split in two, a letter
    repeats.  Either breaks the contiguous sequence asserted here.  Measured
    2026-09-30: 564 of 564 pass, about 18 s serial on an M4 Mac.
    """
    failures = []
    for sg in gemmi.spacegroup_table():
        classes = site_classes(sg.xhm())
        ranks = [_letter_rank(c.wyckoff) for c in classes]
        if ranks != list(range(len(classes))) or classes[-1].multiplicity != len(
                sg.operations()):
            failures.append((sg.xhm(), [c.wyckoff for c in classes]))
    assert failures == []


def test_an_operator_group_gets_the_same_classes_without_letters():
    sg = get_spacegroup("Fd-3m:2")
    xyz = tuple(op.triplet() for op in sg.operations())
    ops = site_classes(OperatorGroup(label="Fd-3m:2 [as a list]", xyz=xyz))
    named = site_classes("Fd-3m:2")
    assert all(c.wyckoff == "" and c.site_symmetry == "" for c in ops)
    assert sorted((c.multiplicity, c.dof) for c in ops) == sorted(
        (c.multiplicity, c.dof) for c in named)


def test_every_representable_translation_is_on_the_grid():
    """gemmi stores translations in units of Op.DEN = 24, the grid the classes use.

    That makes ``SITE_CLASSES_GRID`` unreachable today (gemmi refuses ``z+1/5``
    before a group exists).  The day gemmi changes its denominator, this fails
    first, before the guard is needed.
    """
    assert gemmi.Op.DEN == 24
    with pytest.raises(Exception, match="denominator"):
        OperatorGroup(label="P1 [fifths]", xyz=("x,y,z", "x,y,z+1/5")).operations()


def test_an_operator_list_with_a_special_position_off_the_grid_is_refused():
    """-x+1/24 fixes x = 1/48: the translation is on the 1/24 grid, its centre is
    not, and the scan used to return the general position alone, silently."""
    with pytest.raises(ValueError, match="SITE_CLASSES_GRID"):
        site_classes(OperatorGroup(label="P-1 [1/24]", xyz=("x,y,z", "-x+1/24,-y,-z")))


_P3 = ("x,y,z", "-y{t},x-y,z", "-x+y{t},-x{t},z")


def _p3(t: str) -> OperatorGroup:
    shifted = tuple(op.format(t=t) for op in _P3)
    return OperatorGroup(label=f"P3 [t={t or 0}]", xyz=shifted)


@pytest.mark.parametrize("t", ["+1/24", "+1/12", "+1/3"])
def test_a_three_fold_axis_off_the_grid_is_refused_whatever_the_translation(t):
    """-y+t, x-y, z fixes (2t/3, t/3): the denominator of a special position is
    set by the rotation as well as the translation, so every translation here is
    on the 1/24 grid and the axis is on neither grid (review round 3)."""
    with pytest.raises(ValueError, match="SITE_CLASSES_GRID"):
        site_classes(_p3(t))


def test_plain_p3_and_a_shifted_p3_with_its_axis_on_the_grid_give_four_classes():
    """The positive arm: t = 0 is P3, and t = (I - R)s for a grid origin s is the
    same group moved, with 1a, 1b, 1c and the general position."""
    plain = site_classes(_p3(""))
    assert sorted(c.multiplicity for c in plain) == [1, 1, 1, 3]
    moved = OperatorGroup(label="P3 [origin 1/24]", xyz=(
        "x,y,z", "-y+1/24,x-y-1/24,z", "-x+y+1/12,-x+1/24,z"))
    assert sorted(c.multiplicity for c in site_classes(moved)) == [1, 1, 1, 3]


def test_the_same_inversion_on_the_grid_gives_all_nine_classes():
    """The positive arm: -x+1/12 puts every centre on the 1/24 grid."""
    classes = site_classes(OperatorGroup(label="P-1 [1/12]", xyz=("x,y,z", "-x+1/12,-y,-z")))
    assert sorted(c.multiplicity for c in classes) == [1] * 8 + [2]


# --------------------------------------------------------------------------
# origin choice


def _origin_shift(s1, s2) -> np.ndarray:
    """A shift s with every (R, t) of s1 becoming (R, t + (I − R)s) of s2, on the grid."""
    def key(r, t):
        return (tuple(r.ravel()), tuple(np.rint(t * 24).astype(int) % 24))
    ops2 = {key(np.array(o.rot) // gemmi.Op.DEN, np.array(o.tran) / gemmi.Op.DEN)
            for o in s2.operations()}
    ops1 = [(np.array(o.rot) // gemmi.Op.DEN, np.array(o.tran) / gemmi.Op.DEN)
            for o in s1.operations()]
    for s in itertools.product(range(24), repeat=3):
        s = np.array(s) / 24
        if all(key(r, (t + (np.eye(3) - r) @ s) % 1.0) in ops2 for r, t in ops1):
            return s
    raise AssertionError("no origin shift on the grid")


@pytest.mark.parametrize("pair,composition", [
    (("Fd-3m:1", "Fd-3m:2"), {"Mg": 8, "Al": 16, "O": 32}),        # spinel
    (("Fd-3m:1", "Fd-3m:2"), {"Y": 16, "Ti": 16, "O": 56}),        # pyrochlore
    (("Pn-3m:1", "Pn-3m:2"), {"Cu": 4, "O": 2}),                   # cuprite
    (("I41/amd:1", "I41/amd:2"), {"Ti": 4, "O": 8}),               # TiO2, the I41/amd polymorph
])
def test_origin_choice_changes_nothing(pair, composition):
    s1, s2 = (get_spacegroup(s) for s in pair)
    c1, c2 = site_classes(pair[0]), site_classes(pair[1])
    signature = [(c.wyckoff, c.multiplicity, c.dof, c.site_symmetry) for c in c1]
    assert signature == [(c.wyckoff, c.multiplicity, c.dof, c.site_symmetry) for c in c2]
    # geometry, not labels: each class of one origin, moved by the shift that
    # takes one operation list to the other, is a point of the other origin
    # with that multiplicity and dof
    shift = _origin_shift(s1, s2)
    for c in c1:
        x2 = (c.position(np.full(c.dof, 0.0917)) + shift) % 1.0
        sc = site_constraints(s2, x2)
        assert (sc.multiplicity, sc.coord_basis.shape[0]) == (c.multiplicity, c.dof)
    a1 = site_assignments(c1, composition)
    a2 = site_assignments(c2, composition)
    assert len(a1) == len(a2) > 0
    as_letters = [[tuple((sp, c1[i].wyckoff) for sp, i in a.sites) for a in a1],
                  [tuple((sp, c2[i].wyckoff) for sp, i in a.sites) for a in a2]]
    assert as_letters[0] == as_letters[1]


# --------------------------------------------------------------------------
# composition → assignments


def _letters(classes, assignment):
    return [(sp, classes[i].wyckoff) for sp, i in assignment.sites]


def test_rutile_by_hand():
    """TiO₂ in P4₂/mnm, Z = 2: Ti 2, O 4.

    Ti fills a fixed 2-fold class: 2a or 2b.  O fills 4 as one of 4c, 4d (fixed)
    or 4e, 4f, 4g (one free parameter each), or as 2a + 2b, which Ti always
    blocks.  So 2 × 5 = 10.  The true structure (Ti 2a, O 4f) is one of them.
    """
    classes = site_classes("P42/mnm")
    got = site_assignments(classes, {"O": 4, "Ti": 2})
    assert len(got) == 10
    assert [_letters(classes, a) for a in got] == [
        [("Ti", t), ("O", o)] for t in ("2a", "2b") for o in ("4c", "4d", "4e", "4f", "4g")]
    assert [a.dof for a in got] == [0, 0, 1, 1, 1] * 2


def test_spinel_by_hand():
    """MgAl₂O₄ in Fd-3m, Z = 8: Mg 8, Al 16, O 32.

    Mg takes 8a or 8b.  Al takes 16c or 16d; 8a + 8b is blocked by Mg.  O would
    take 32e, 16c + 16d, or 8a + 8b + 16c/d, but every option except 32e shares
    a fixed class with Mg or Al.  So 2 × 2 × 1 = 4.
    """
    for setting in ("Fd-3m:1", "Fd-3m:2"):
        classes = site_classes(setting)
        got = site_assignments(classes, {"Mg": 8, "Al": 16, "O": 32})
        assert len(got) == 4
        assert all(dict(_letters(classes, a))["O"] == "32e" for a in got)


def test_perovskite_by_hand():
    """SrTiO₃ in Pm-3m, Z = 1: Sr 1, Ti 1, O 3.

    Sr and Ti take 1a and 1b in either order.  O takes 3c or 3d: 1 + 1 + 1 has
    only two 1-fold classes.  So 2 × 2 = 4.  LaB₆ (La 1, B 6): La takes 1a or 1b;
    B takes 6e, 6f or 3c + 3d.  So 2 × 3 = 6, the spike's count.
    """
    classes = site_classes("Pm-3m")
    assert len(site_assignments(classes, {"Sr": 1, "Ti": 1, "O": 3})) == 4
    assert len(site_assignments(classes, {"La": 1, "B": 6})) == 6


def test_a_free_class_is_reused_and_a_fixed_one_is_not():
    """Pnma, 8 O: 4c twice, 4a + 4c, 4b + 4c, 4a + 4b or 8d.  So 5, and 4a is never doubled."""
    classes = site_classes("Pnma")
    got = [sorted(classes[i].wyckoff for _, i in a.sites)
           for a in site_assignments(classes, {"O": 8})]
    assert sorted(got) == sorted([["4c", "4c"], ["4a", "4c"], ["4b", "4c"],
                                  ["4a", "4b"], ["8d"]])


def test_heavy_atoms_come_first():
    classes = site_classes("Fd-3m:2")
    got = site_assignments(classes, {"O": 56, "Y": 16, "Ti": 16})
    assert all([sp for sp, _ in a.sites][:2] == ["Y", "Ti"] for a in got)
    heavy = [a.sites[0][1] for a in got]
    assert heavy == sorted(heavy)         # grouped by the heaviest species' placement


def _brute_force(classes, composition, max_sites):
    """Independent enumerator: multisets by itertools, filters stated plainly."""
    per_species = []
    for sp, n in composition.items():
        options = set()
        for k in range(1, (n if max_sites is None else max_sites) + 1):
            for combo in itertools.combinations_with_replacement(range(len(classes)), k):
                if sum(classes[i].multiplicity for i in combo) != n:
                    continue
                fixed = [i for i in combo if classes[i].dof == 0]
                if len(fixed) != len(set(fixed)):
                    continue
                options.add(combo)
        per_species.append(options)
    total = 0
    for choice in itertools.product(*per_species):
        fixed = [i for combo in choice for i in combo if classes[i].dof == 0]
        total += len(fixed) == len(set(fixed))
    return total


@pytest.mark.parametrize("setting,composition,max_sites", [
    ("P42/mnm", {"Ti": 2, "O": 4}, None),
    ("P42/mnm", {"Sn": 2, "W": 2, "O": 8}, None),
    ("Pm-3m", {"La": 1, "B": 6}, None),
    ("Pm-3m", {"Ca": 1, "O": 12}, 3),
    ("C2/m", {"Na": 4, "O": 8}, None),
    ("P-1", {"Si": 6}, None),
    ("R-3m:H", {"Li": 3, "Co": 3, "O": 6}, None),
    ("Fd-3m:2", {"Mg": 8, "Al": 16, "O": 32}, 2),
])
def test_count_equals_enumeration_equals_brute_force(setting, composition, max_sites):
    classes = site_classes(setting)
    n = count_site_assignments(classes, composition, max_sites_per_species=max_sites)
    listed = site_assignments(classes, composition, max_sites_per_species=max_sites)
    assert n == len(listed) == _brute_force(classes, composition, max_sites)
    assert len({a.sites for a in listed}) == len(listed)        # no duplicates


def test_the_cap_refuses_with_the_count():
    classes = site_classes("Pm-3m")
    composition = {"Ca": 1, "O": 24}
    n = count_site_assignments(classes, composition)
    assert len(site_assignments(classes, composition, max_assignments=n)) == n
    with pytest.raises(SiteAssignmentCapError, match="SITE_ASSIGNMENTS_EXCEED_CAP") as err:
        site_assignments(classes, composition, max_assignments=n - 1)
    assert err.value.count == n and err.value.cap == n - 1
    assert str(n) in str(err.value)


def test_a_large_one_species_cell_is_refused_not_truncated():
    """β-boron-like: 315 atoms of one species in R-3m:H, the case the spike refused."""
    classes = site_classes("R-3m:H")
    n = count_site_assignments(classes, {"B": 315})
    assert n > MAX_SITE_ASSIGNMENTS
    with pytest.raises(SiteAssignmentCapError) as err:
        site_assignments(classes, {"B": 315})
    assert err.value.count == n


def test_no_placement_is_an_empty_answer_and_bad_counts_raise():
    classes = site_classes("Fm-3m")
    assert site_assignments(classes, {"Na": 3}) == ()   # no 3-fold combination of 4, 8, 24, …
    with pytest.raises(ValueError, match="positive integers"):
        site_assignments(classes, {"Na": 0})


def test_an_unplaceable_species_does_not_enumerate_the_others():
    """Cs has no 1-fold class in R-3m:H, so the joint count is 0 however many B there are.

    The cap is checked on the joint count, so a species with no placement must
    not leave another one's placements to be built unbounded first.  1 000 B
    took 35 s that way; the 15 s is a runaway guard, not a timer.
    """
    import time

    classes = site_classes("R-3m:H")
    start = time.perf_counter()
    assert site_assignments(classes, {"Cs": 1, "B": 1000}) == ()
    assert time.perf_counter() - start < 15


def test_enumeration_never_walks_a_branch_that_cannot_finish():
    """A positive arm for the prune: a placeable pair still comes back complete."""
    classes = site_classes("R-3m:H")
    composition = {"Cs": 3, "B": 36}
    listed = site_assignments(classes, composition)
    assert listed and len(listed) == count_site_assignments(classes, composition)
    assert all(sum(classes[ci].multiplicity for sp, ci in a.sites if sp == "B") == 36
               for a in listed)


def test_an_empty_composition_is_refused_in_the_count_and_the_list():
    classes = site_classes("Fm-3m")
    for call in (count_site_assignments, site_assignments):
        with pytest.raises(ValueError, match="no species"):
            call(classes, {})


@pytest.mark.parametrize("bad", [0, -1, 1.5])
def test_max_sites_per_species_must_be_a_positive_integer_or_none(bad):
    classes = site_classes("Fm-3m")
    for call in (count_site_assignments, site_assignments):
        with pytest.raises(ValueError, match="max_sites_per_species"):
            call(classes, {"Na": 4}, max_sites_per_species=bad)


def test_crystallography_does_not_import_optimize():
    import ast
    from pathlib import Path

    import rietx.crystallography.site_classes as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    assert imported and not [m for m in imported if "optimize" in m.split(".")]


def _fields(classes):
    return [(c.wyckoff, c.site_symmetry, c.multiplicity, c.point.tobytes(),
             c.basis.tobytes(), c.stabilizer.tobytes(), c.coset_rot.tobytes(),
             c.coset_tran.tobytes()) for c in classes]


@pytest.mark.parametrize("symbol", ["F d -3 m:2", "P 63/m m c", "I 41/a m d:2"])
def test_the_scan_chunk_and_the_cache_size_do_not_change_the_classes(symbol, monkeypatch):
    """``_CHUNK`` and ``_CACHE_SIZE`` are answer-invariant (WP-2001's class): a
    chunk only partitions the grid scan and the cache only skips a rederivation,
    so a 7-point chunk and a one-entry cache give the same classes to the bit."""
    import rietx.crystallography.site_classes as sc

    want = _fields(site_classes(symbol))
    monkeypatch.setattr(sc, "_CHUNK", 7)
    monkeypatch.setattr(sc, "_CACHE_SIZE", 1)
    monkeypatch.setattr(sc, "_CACHE", {})
    assert _fields(site_classes("P -1")) != want
    assert _fields(site_classes(symbol)) == want
    assert len(sc._CACHE) == 1
