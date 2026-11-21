"""Bound coherent neutron scattering lengths.

The tests worth having here are the ones that pin the three ways neutron
scattering differs from X-ray, because each one breaks an assumption the X-ray
path is entitled to make: b can be negative, b depends on isotope, and the
table is thermal-only. A test that merely re-read a number out of the file it
was loaded from would pin nothing.
"""

from __future__ import annotations

import math

import pytest

from rietx.crystallography.neutron import (
    RESONANT_ABSORBERS,
    b_coh,
    is_resonant_absorber,
    normalize_species,
    properties,
)


# Values quoted from Sears (1992) Neutron News 3(3), 26-37 / International
# Tables C Table 4.4.4.1. Written out here rather than read from the data file
# so that a corrupted or truncated table fails this test instead of agreeing
# with itself.
@pytest.mark.parametrize("species, expected_fm", [
    ("Al", 3.449),      # the BT-1 Al2O3 standard, with O below
    ("O", 5.803),
    ("Cr", 3.635),
    ("V", -0.3824),     # negative, and near-null: the standard sample can
    ("Ti", -3.438),     # negative
    ("Mn", -3.73),      # negative
    ("H", -3.7390),     # negative, natural abundance
    ("2H", 6.671),      # positive, and a different nucleus
])
def test_tabulated_scattering_lengths(species, expected_fm):
    assert b_coh(species) == pytest.approx(expected_fm, abs=5e-4)


def test_scattering_length_may_be_negative():
    """A 180-degree phase shift, not an error state.

    Anything that takes abs() or sqrt() of a single species' amplitude is wrong
    for neutrons, so the sign has to survive the lookup.
    """
    assert b_coh("V") < 0.0
    assert b_coh("Ti") < 0.0
    assert b_coh("Mn") < 0.0
    assert b_coh("Li") < 0.0
    assert b_coh("Al") > 0.0          # and the common case is still positive


def test_isotope_is_the_identity_not_the_element():
    """b(1H) and b(2H) differ in sign, which is why deuteration is routine.

    This is the opposite convention to dispersion.normalize_element, where an
    ion resolves to its element because f'/f'' is a core-level effect. Here the
    nucleus *is* the scatterer, so the mass number must not be discarded.
    """
    assert b_coh("1H") < 0.0
    assert b_coh("2H") > 0.0
    assert b_coh("H") * b_coh("D") < 0.0
    # and the natural-abundance average is not either isotope
    assert b_coh("H") != pytest.approx(b_coh("2H"), abs=1e-3)


def test_ionic_charge_is_discarded_but_mass_number_is_kept():
    """Both charge spellings, since TOPAS writes sign-first."""
    assert normalize_species("Fe3+") == "Fe"
    assert normalize_species("Fe+3") == "Fe"
    assert normalize_species("O2-") == "O"
    assert normalize_species("O-2") == "O"
    assert b_coh("Fe3+") == b_coh("Fe")
    # a mass number selects a different nucleus and must survive
    assert normalize_species("2H") == "2H"
    assert normalize_species("D") == "2H"
    assert normalize_species("157Gd") == "157Gd"


def test_an_element_first_isotope_is_refused_naming_the_mass_first_spelling():
    """``Li7`` is refused at evaluation, and the refusal names ``7Li`` (WP-1532).

    Issue #661: an agent wrote lithium-7 element-first and the message said
    only that it could not read the species.  A label that is no such slip
    gets no hint: ``O1`` is a site label and ``Fe3`` an unsigned charge, and
    naming ``1O`` or ``3Fe`` would invent a nuclide.  Where the nuclide is
    tabulated the spelling may still be a site label (``N15`` in an organic
    structure), so the hint names both readings: 15N, and natural N.
    """
    with pytest.raises(KeyError, match="mass-first, 7Li"):
        normalize_species("Li7")
    with pytest.raises(KeyError) as label:
        normalize_species("N15")
    assert "mass-first, 15N" in str(label.value)
    assert "site label) write N" in str(label.value)
    for label in ("123", "O1", "Fe3"):    # no nuclide to name: a site label, a charge
        with pytest.raises(KeyError) as plain:
            normalize_species(label)
        assert "mass-first" not in str(plain.value), label


def test_vanadium_is_the_standard_can():
    """Near-null coherent, overwhelmingly incoherent.

    This is *why* a V can contributes a smooth background and almost no Bragg
    peaks, and it is the quantitative form of that folklore.
    """
    v = properties("V")
    assert abs(v["b_coh_fm"]) < 0.5
    assert v["xs_inc_barn"] > 100.0 * v["xs_coh_barn"]


def test_hydrogen_is_the_incoherent_problem():
    """The reason deuterated samples exist, stated as a number."""
    h = properties("H")
    d = properties("2H")
    assert h["xs_inc_barn"] > 10.0 * d["xs_inc_barn"]


def test_resonant_absorbers_are_flagged():
    """Thermal b is incomplete, not wrong, for these — a fence not an oversight."""
    assert is_resonant_absorber("Gd")
    assert is_resonant_absorber("157Gd")
    assert is_resonant_absorber("Cd")
    assert not is_resonant_absorber("Al")
    assert not is_resonant_absorber("O")
    # every listed absorber must resolve through the same normalisation
    for species in RESONANT_ABSORBERS:
        assert is_resonant_absorber(species)


def test_ytterbium_is_a_resonant_absorber_on_this_table_s_own_numbers():
    """Issue #113 (a): Yb was missing, and the table itself is the argument.

    The claim is not that natural Yb absorbs a lot -- at 34.80 barn it absorbs
    less than a fiftieth of Cd.  It is that the absorption is wildly
    *isotope-dependent*, which is the signature of a nuclear resonance and the
    thing a single thermal number cannot express.  Asserted against the
    shipped table rather than an outside source, so this test fails if the
    data file ever stops supporting the classification.
    """
    assert is_resonant_absorber("Yb")
    assert is_resonant_absorber("168Yb")

    spread = properties("168Yb")["xs_abs_barn"] / properties("176Yb")["xs_abs_barn"]
    assert spread > 100.0, (
        f"168Yb/176Yb absorption ratio is {spread:.0f}; Yb is in "
        f"RESONANT_ABSORBERS because that spread is nearly three orders")

    # …and the ordinary isotope is not swept in with its element: the set is
    # about nuclides, and 176Yb at 2.85 barn is an unremarkable absorber.
    assert not is_resonant_absorber("176Yb")
    assert properties("176Yb")["xs_abs_barn"] < 10.0


def test_neodymium_is_not_in_the_set_and_the_table_says_why():
    """A negative control with a real candidate behind it.

    Nd is a moderate absorber that turns up in this campaign's own data, and
    it was informally called a resonant absorber while planning WP-1312. The
    table does not support that: its strongest nuclide is an order of
    magnitude below 168Yb and nearly two below 113Cd, so it sits with the
    ordinary elements. Recorded as a test rather than a comment because the
    next person to look will have the same idea.
    """
    assert not is_resonant_absorber("Nd")
    assert not is_resonant_absorber("143Nd")
    assert (properties("143Nd")["xs_abs_barn"]
            < properties("168Yb")["xs_abs_barn"] / 5.0)


def test_unknown_species_raises_naming_it():
    """A missing species is a modelling error the caller must see.

    Never a substituted zero: that would delete a site from the structure
    factor without changing the shape of anything.
    """
    with pytest.raises(KeyError, match="Xx"):
        b_coh("Xx")
    with pytest.raises(KeyError):
        b_coh("")
    with pytest.raises(KeyError):
        b_coh("Zz9")


def test_untabulated_species_raises_rather_than_returning_nan():
    """The source writes '---' for several heavy elements; nan must not leak."""
    untabulated = [s for s in ("Po", "At", "Rn", "Fr", "Ac", "Pu")
                   if not math.isfinite(properties(s)["b_coh_fm"])]
    assert untabulated, "expected at least one '---' row to exercise this"
    for species in untabulated:
        with pytest.raises(KeyError, match="not tabulated"):
            b_coh(species)


def test_table_covers_the_acceptance_datasets():
    """Every species in the CW-neutron acceptance set resolves.

    Al2O3 (BT-1 SRM 1976a), two further BT-1 oxides, ZrW2O8 (APDW),
    Ba2FeSbSe5 (LLB G4.1).
    """
    for species in ("Al", "O", "Cr", "W", "Pb", "Pd", "Zr", "Ba", "Fe", "Sb", "Se"):
        assert math.isfinite(b_coh(species))


# --- Transcription of b_Sears.dat (the uncertainty-digit defect) ------------
#
# The NIST copy the table was taken from prints an uncertainty in parentheses
# after many values: 58Fe "15.(7.)", 102Pd "7.7(7)", Gd absorption
# "49700.(125.)".  The original transcription dropped the parentheses and kept
# the uncertainty's digits as further decimals (15.7, 7.77, 49700.125).  The
# tests below pin every corrected cell, check the natural elements against an
# independent copy of Sears (1992), and state two whole-file properties that a
# digit-append breaks, each with an arm showing it can fail.

def _table_text() -> str:
    from importlib.resources import files

    return (files("rietx.data") / "b_Sears.dat").read_text(encoding="utf-8")


_COLUMNS = ("conc", "b_coh", "b_inc", "xs_coh", "xs_inc", "xs_scatt", "xs_abs")


def _rows(text: str) -> dict[str, dict[str, str]]:
    """The table's cells as the strings it prints, so digits can be counted."""
    rows = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        symbol, *cells = line.split()
        rows[symbol] = dict(zip(_COLUMNS, cells))
    return rows


def _last_digit(cell: str) -> float:
    """One unit in the last printed digit: 0.01 for "1.34", 1 for "28"."""
    mantissa = cell.lstrip("+-")
    return 10.0 ** -len(mantissa.partition(".")[2])


#: Source text, the old (wrong) cell and the corrected cell, for every cell the
#: correction touched.  The source text is the NIST copy's, as retrieved through
#: the Internet Archive (snapshot 2026-06-08) because the NIST URL now
#: redirects elsewhere.  The corrected value is the number before the
#: parenthesis, except 147Sm xs_inc: the copy prints "143(19.)", a misprint of
#: Sears's 14(19) -- Rauch & Waschkowski (2003) give 14.0(19.0), and only 14
#: makes 25 (coh) + 14 (inc) = 39 (scatt) in the same row.
_CORRECTED_CELLS = """\
He     b_coh    3.26(3)           3.263    3.26
3He    xs_abs   5333.(7.)        5333.7    5333
6Li    xs_abs   940.(4.)          940.4     940
B      xs_abs   767.(8.)          767.8     767
10B    xs_abs   3835.(9.)        3835.9    3835
36S    b_coh    3.(1.)              3.1       3
38Ar   xs_coh   1.5(3.1)           1.53     1.5
38Ar   xs_scatt 1.5(3.1)           1.53     1.5
40K    b_coh    3.(1.)              3.1       3
40K    xs_abs   35.(8.)            35.8      35
50V    xs_coh   7.3(1.1)           7.31     7.3
50V    xs_scatt 7.8(1.0)           7.81     7.8
50V    xs_abs   60.(40.)          60.40      60
53Cr   xs_abs   18.1(1.5)         18.11    18.1
58Fe   b_coh    15.(7.)            15.7      15
58Fe   xs_scatt 28.(26.)          28.26      28
70Zn   b_coh    6.(1.)              6.1       6
70Zn   xs_scatt 4.5(1.5)           4.51     4.5
76Ge   xs_coh   8.(3.)              8.3       8
76Ge   xs_scatt 8.(3.)              8.3       8
74Se   xs_abs   51.8(1.2)         51.81    51.8
76Se   xs_abs   85.(7.)            85.7      85
77Se   xs_abs   42.(4.)            42.4      42
Kr     xs_abs   25.(1.)            25.1      25
82Kr   xs_abs   29.(20.)          29.20      29
83Kr   xs_abs   185.(30.)        185.30     185
84Sr   b_coh    7.(1.)              7.1       7
84Sr   xs_coh   6.(2.)              6.2       6
84Sr   xs_scatt 6.(2.)              6.2       6
87Sr   xs_abs   16.(3.)            16.3      16
Tc     xs_abs   20.(1.)            20.1      20
99Ru   xs_abs   6.9(1.0)           6.91     6.9
102Pd  b_coh    7.7(7)             7.77     7.7
102Pd  xs_coh   7.5(1.4)           7.51     7.5
102Pd  xs_scatt 7.5(1.4)           7.51     7.5
104Pd  b_coh    7.7(7)             7.77     7.7
104Pd  xs_coh   7.5(1.4)           7.51     7.5
104Pd  xs_scatt 7.5(1.4)           7.51     7.5
105Pd  b_inc    -2.6(1.6)         -2.61    -2.6
105Pd  xs_scatt 4.6(1.1)           4.61     4.6
105Pd  xs_abs   20.(3.)            20.3      20
110Pd  b_coh    7.7(7)             7.77     7.7
110Pd  xs_coh   7.5(1.4)           7.51     7.5
110Pd  xs_scatt 7.5(1.4)           7.51     7.5
107Ag  xs_abs   37.6(1.2)         37.61    37.6
109Ag  xs_abs   91.0(1.0)         91.01    91.0
Cd     xs_abs   2520.(50.)      2520.50    2520
106Cd  b_coh    5.(2.)              5.2       5
106Cd  xs_scatt 3.1(2.5)           3.12     3.1
113Cd  xs_abs   20600.(400.)  20600.400   20600
In     xs_abs   193.8(1.5)       193.81   193.8
113In  xs_abs   12.0(1.1)         12.01    12.0
115In  xs_abs   202.(2.)          202.2     202
112Sn  b_coh    6.(1.)              6.1       6
112Sn  xs_coh   4.5(1.5)           4.51     4.5
112Sn  xs_scatt 4.5(1.5)           4.51     4.5
115Sn  b_coh    6.(1.)              6.1       6
115Sn  xs_coh   4.5(1.5)           4.51     4.5
115Sn  xs_scatt 4.8(1.5)           4.81     4.8
115Sn  xs_abs   30.(7.)            30.7      30
123Te  xs_abs   418.(30.)        418.30     418
124Te  xs_abs   6.8(1.3)           6.81     6.8
Xe     xs_abs   23.9(1.2)         23.91    23.9
124Xe  xs_abs   165.(20.)        165.20     165
129Xe  xs_abs   21.(5.)            21.5      21
131Xe  xs_abs   85.(10.)          85.10      85
Cs     xs_abs   29.0(1.5)         29.01    29.0
130Ba  xs_abs   30.(5.)            30.5      30
134Ba  xs_abs   2.0(1.6)           2.01     2.0
138La  b_coh    8.(2.)              8.2       8
138La  xs_coh   8.(4.)              8.4       8
138La  xs_scatt 8.5(4.0)           8.54     8.5
138La  xs_abs   57.(6.)            57.6      57
136Ce  xs_abs   7.3(1.5)           7.31     7.3
Nd     xs_abs   50.5(1.2)         50.51    50.5
143Nd  b_coh    14.(2.)            14.2      14
143Nd  xs_coh   25.(7.)            25.7      25
143Nd  xs_inc   55.(7.)            55.7      55
143Nd  xs_scatt 80.(2.)            80.2      80
143Nd  xs_abs   337.(10.)        337.10     337
145Nd  b_coh    14.(2.)            14.2      14
145Nd  xs_coh   25.(7.)            25.7      25
145Nd  xs_inc   5.(5.)              5.5       5
145Nd  xs_scatt 30.(9.)            30.9      30
145Nd  xs_abs   42.(2.)            42.2      42
Pm     xs_coh   20.0(1.3)         20.01    20.0
Pm     xs_inc   1.3(2.0)           1.32     1.3
Pm     xs_scatt 21.3(1.5)         21.31    21.3
Pm     xs_abs   168.4(3.5)       168.43   168.4
Sm     xs_inc   39.(3.)            39.3      39
Sm     xs_scatt 39.(3.)            39.3      39
Sm     xs_abs   5922.(56.)      5922.56    5922
144Sm  b_coh    -3.(4.)            -3.4      -3
144Sm  xs_coh   1.(3.)              1.3       1
144Sm  xs_scatt 1.(3.)              1.3       1
147Sm  b_coh    14.(3.)            14.3      14
147Sm  xs_coh   25.(11.)          25.11      25
147Sm  xs_inc   143(19.)          14319      14
147Sm  xs_scatt 39.(16.)          39.16      39
147Sm  xs_abs   57.(3.)            57.3      57
148Sm  b_coh    -3.(4.)            -3.4      -3
148Sm  xs_coh   1.(3.)              1.3       1
148Sm  xs_scatt 1.(3.)              1.3       1
149Sm  xs_inc   137.(5.)          137.5     137
149Sm  xs_scatt 200.(5.)          200.5     200
149Sm  xs_abs   42080.(400.)  42080.400   42080
150Sm  b_coh    14.(3.)            14.3      14
150Sm  xs_coh   25.(11.)          25.11      25
150Sm  xs_scatt 25.(11.)          25.11      25
150Sm  xs_abs   104.(4.)          104.4     104
152Sm  xs_abs   206.(6.)          206.6     206
154Sm  xs_coh   11.(2.)            11.2      11
154Sm  xs_scatt 11.(2.)            11.2      11
Eu     xs_abs   4530.(40.)      4530.40    4530
151Eu  xs_abs   9100.(100.)    9100.100    9100
153Eu  xs_abs   312.(7.)          312.7     312
Gd     xs_inc   151.(2.)          151.2     151
Gd     xs_scatt 180.(2.)          180.2     180
Gd     xs_abs   49700.(125.)  49700.125   49700
152Gd  b_coh    10.(3.)            10.3      10
152Gd  xs_coh   13.(8.)            13.8      13
152Gd  xs_scatt 13.(8.)            13.8      13
152Gd  xs_abs   735.(20.)        735.20     735
154Gd  b_coh    10.(3.)            10.3      10
154Gd  xs_coh   13.(8.)            13.8      13
154Gd  xs_scatt 13.(8.)            13.8      13
154Gd  xs_abs   85.(12.)          85.12      85
155Gd  xs_inc   25.(6.)            25.6      25
155Gd  xs_scatt 66.(6.)            66.6      66
155Gd  xs_abs   61100.(400.)  61100.400   61100
156Gd  xs_abs   1.5(1.2)           1.51     1.5
157Gd  xs_coh   650.(4.)          650.4     650
157Gd  xs_inc   394.(7.)          394.7     394
157Gd  xs_scatt 1044.(8.)        1044.8    1044
157Gd  xs_abs   259000.(700.) 259000.700  259000
158Gd  b_coh    9.(2.)              9.2       9
158Gd  xs_coh   10.(5.)            10.5      10
158Gd  xs_scatt 10.(5.)            10.5      10
Dy     xs_inc   54.4(1.2)         54.41    54.4
Dy     xs_abs   994.(13.)        994.13     994
156Dy  xs_abs   33.(3.)            33.3      33
158Dy  b_coh    6.(4.)              6.4       6
158Dy  xs_coh   5.(6.)              5.6       5
158Dy  xs_scatt 5.(6.)              5.6       5
158Dy  xs_abs   43.(6.)            43.6      43
160Dy  xs_abs   56.(5.)            56.5      56
161Dy  xs_inc   3.(1.)              3.1       3
161Dy  xs_scatt 16.(1.)            16.1      16
161Dy  xs_abs   600.(25.)        600.25     600
162Dy  xs_abs   194.(10.)        194.10     194
163Dy  xs_abs   124.(7.)          124.7     124
164Dy  xs_coh   307.(3.)          307.3     307
164Dy  xs_scatt 307.(3.)          307.3     307
164Dy  xs_abs   2840.(40.)      2840.40    2840
Ho     xs_abs   64.7(1.2)         64.71    64.7
Er     xs_abs   159.(4.)          159.4     159
162Er  xs_abs   19.(2.)            19.2      19
164Er  xs_abs   13.(2.)            13.2      13
166Er  xs_abs   19.6(1.5)         19.61    19.6
167Er  xs_abs   659.(16.)        659.16     659
170Er  xs_scatt 11.6(1.2)         11.61    11.6
Tm     xs_abs   100.(2.)          100.2     100
168Yb  xs_abs   2230.(40.)      2230.40    2230
170Yb  xs_abs   11.4(1.0)         11.41    11.4
171Yb  xs_abs   48.6(2.5)         48.62    48.6
173Yb  xs_abs   17.1(1.3)         17.11    17.1
174Yb  xs_abs   69.4(5.0)         69.45    69.4
Lu     xs_abs   74.(2.)            74.2      74
175Lu  xs_abs   21.(3.)            21.3      21
176Lu  xs_abs   2065.(35.)      2065.35    2065
174Hf  b_coh    10.9(1.1)         10.91    10.9
174Hf  xs_coh   15.(3.)            15.3      15
174Hf  xs_scatt 15.(3.)            15.3      15
174Hf  xs_abs   561.(35.)        561.35     561
176Hf  xs_abs   23.5(3.1)         23.53    23.5
177Hf  b_coh    0.8(1.0)           0.81     0.8
177Hf  xs_abs   373.(10.)        373.10     373
178Hf  xs_abs   84.(4.)            84.4      84
179Hf  xs_abs   41.(3.)            41.3      41
180Hf  xs_scatt 21.9(1.0)         21.91    21.9
180Ta  b_coh    7.(2.)              7.2       7
180Ta  xs_scatt 7.(4.)              7.4       7
180Ta  xs_abs   563.(60.)        563.60     563
180W   b_coh    5.(3.)              5.3       5
180W   xs_coh   3.(4.)              3.4       3
180W   xs_scatt 3.(4.)              3.4       3
180W   xs_abs   30.(20.)          30.20      30
Re     xs_abs   89.7(1.)          89.71    89.7
185Re  xs_abs   112.(2.)          112.2     112
187Re  xs_abs   76.4(1.)          76.41    76.4
184Os  b_coh    10.(2.)            10.2      10
184Os  xs_coh   13.(5.)            13.5      13
184Os  xs_scatt 13.(5.)            13.5      13
184Os  xs_abs   3000.(150.)    3000.150    3000
186Os  b_coh    11.6(1.7)         11.61    11.6
186Os  xs_coh   17.(5.)            17.5      17
186Os  xs_scatt 17.(5.)            17.5      17
186Os  xs_abs   80.(13.)          80.13      80
187Os  b_coh    10.(2.)            10.2      10
187Os  xs_coh   13.(5.)            13.5      13
187Os  xs_scatt 13.(5.)            13.5      13
187Os  xs_abs   320.(10.)        320.10     320
189Os  xs_abs   25.(4.)            25.4      25
192Os  xs_scatt 16.6(1.2)         16.61    16.6
Ir     xs_inc   0.(3.)              0.3       0
Ir     xs_scatt 14.(3.)            14.3      14
Ir     xs_abs   425.(2.)          425.2     425
191Ir  xs_abs   954.(10.)        954.10     954
193Ir  xs_abs   111.(5.)          111.5     111
190Pt  xs_coh   10.(2.)            10.2      10
190Pt  xs_scatt 10.(2.)            10.2      10
190Pt  xs_abs   152.(4.)          152.4     152
192Pt  xs_coh   12.3(1.2)         12.31    12.3
192Pt  xs_scatt 12.3(1.2)         12.31    12.3
192Pt  xs_abs   10.0(2.5)         10.02    10.0
195Pt  xs_abs   27.5(1.2)         27.51    27.5
Hg     xs_abs   372.3(4.0)       372.34   372.3
196Hg  b_coh    30.3(1.0)         30.31    30.3
196Hg  xs_coh   115.(8.)          115.8     115
196Hg  xs_scatt 115.(8.)          115.8     115
196Hg  xs_abs   3080.(180.)    3080.180    3080
199Hg  xs_coh   36.(2.)            36.2      36
199Hg  xs_inc   30.(3.)            30.3      30
199Hg  xs_scatt 66.(2.)            66.2      66
199Hg  xs_abs   2150.(48.)      2150.48    2150
201Hg  xs_abs   7.8(2.0)           7.82     7.8
Ra     b_coh    10.0(1.0)         10.01    10.0
Ra     xs_coh   13.(3.)            13.3      13
Ra     xs_scatt 13.(3.)            13.3      13
Ra     xs_abs   12.8(1.5)         12.81    12.8
Pa     xs_inc   0.1(3.3)           0.13     0.1
Pa     xs_scatt 10.5(3.2)         10.53    10.5
Pa     xs_abs   200.6(2.3)       200.62   200.6
233U   xs_abs   574.7(1.0)       574.71   574.7
234U   xs_abs   100.1(1.3)       100.11   100.1
235U   xs_abs   680.9(1.1)       680.91   680.9
Np     xs_abs   175.9(2.9)       175.92   175.9
238Pu  xs_coh   25.0(1.8)         25.01    25.0
238Pu  xs_scatt 25.0(1.8)         25.01    25.0
238Pu  xs_abs   558.(7.)          558.7     558
239Pu  xs_abs   1017.3(2.1)     1017.32  1017.3
240Pu  xs_abs   289.6(1.4)       289.61   289.6
Am     xs_scatt 9.0(2.6)           9.02     9.0
Am     xs_abs   75.3(1.8)         75.31    75.3
244Cm  xs_abs   16.2(1.2)         16.21    16.2
"""


def _corrections() -> list[tuple[str, str, str, str, str]]:
    return [tuple(line.split()) for line in _CORRECTED_CELLS.splitlines()]


def test_every_corrected_cell_holds_the_value_sears_printed():
    rows = _rows(_table_text())
    corrections = _corrections()
    assert len(corrections) == 245
    for symbol, column, printed, old, new in corrections:
        cell = rows[symbol][column]
        assert float(cell) == float(new), (symbol, column, cell, printed)
        assert float(cell) != float(old), (symbol, column)
        if (symbol, column) != ("147Sm", "xs_inc"):
            assert float(new) == float(printed.partition("(")[0]), (symbol, column)


def test_every_corrected_b_coh_moves_by_less_than_its_printed_uncertainty():
    """The correction removes digits; it never moves a value outside its error.

    Checked on the scattering lengths, the column a refinement reads: each
    old value is the corrected one plus at most the stated uncertainty.  A
    check on the list above, not on the file, so it passes on either.
    """
    for symbol, column, printed, old, new in _corrections():
        if column != "b_coh":
            continue
        value, _, uncertainty = printed.rstrip(")").partition("(")
        sigma = (float(uncertainty) if "." in uncertainty
                 else int(uncertainty) * _last_digit(value.rstrip(".")))
        assert abs(float(old) - float(new)) <= sigma, (symbol, old, new, printed)


def test_natural_element_scattering_lengths_match_gemmi_sears_1992():
    """Every natural element against gemmi's independent copy of Sears (1992).

    gemmi's ``neutron92`` carries b_c for the elements only, so this covers
    the 89 element rows with a b_coh and no isotope.  He (3.263) and Ra
    (10.01) were the two element rows the digit-append reached.
    """
    gemmi = pytest.importorskip("gemmi")
    compared = []
    for symbol, row in _rows(_table_text()).items():
        if not symbol.isalpha() or row["b_coh"] == "nan":
            continue
        expected = gemmi.Element(symbol).neutron92.get_coefs()[0]
        assert float(row["b_coh"]) == pytest.approx(expected, abs=1e-9), symbol
        compared.append(symbol)
    assert len(compared) == 89
    assert {"He", "Ra"} <= set(compared)
    assert b_coh("He") == 3.26 and b_coh("Ra") == 10.0


#: Rows where the source itself does not add up to within its printed digits.
#: Eu: 6.57 + 2.5 = 9.07 against 9.2 in Sears and in Rauch & Waschkowski
#: (2003) alike, so it is the measurement, not the transcription.
_SUM_RULE_EXEMPT = frozenset({"Eu"})


def _sum_rule_violations(text: str) -> list[str]:
    """Rows where xs_scatt != xs_coh + xs_inc beyond one unit of the coarsest digit."""
    bad = []
    for symbol, row in _rows(text).items():
        cells = row["xs_coh"], row["xs_inc"], row["xs_scatt"]
        if "nan" in cells or symbol in _SUM_RULE_EXEMPT:
            continue
        coh, inc, scatt = (float(c) for c in cells)
        if abs(coh + inc - scatt) > max(_last_digit(c) for c in cells) + 1e-9:
            bad.append(symbol)
    return bad


def _overprecise_cells(text: str, limit: int = 6) -> list[str]:
    """Cells printed with more significant digits than any Sears entry carries."""
    bad = []
    for symbol, row in _rows(text).items():
        for column in _COLUMNS[1:]:
            cell = row[column]
            if cell == "nan":
                continue
            digits = cell.lstrip("+-").replace(".", "").lstrip("0")
            if len(digits) > limit:
                bad.append(f"{symbol}.{column}")
    return bad


def test_scattering_cross_sections_add_up_in_every_row():
    """sigma_scatt = sigma_coh + sigma_inc, to the digits the table prints.

    A digit-append breaks it in 14 rows of the old file, 143Nd for one:
    25.7 + 55.7 = 81.4 against 80.2, where Sears prints 25 + 55 = 80.  It
    cannot see an append smaller than the row's coarsest digit (58Fe's
    28 + 0 against 28.26), which is what the pinned cells above are for.
    """
    assert _sum_rule_violations(_table_text()) == []


def test_no_cell_is_printed_to_more_than_six_significant_digits():
    """Sears's most precise entries carry six (Cl 11.5257, 157Gd 259000).

    The digit-append made absorption cross-sections like 49700.125 and
    259000.700, eight and nine digits on a thermal measurement.
    """
    assert _overprecise_cells(_table_text()) == []


def _with_cell(text: str, symbol: str, column: str, value: str) -> str:
    """``text`` with one cell rewritten, the rest of the file untouched."""
    lines = text.splitlines(keepends=True)
    for k, line in enumerate(lines):
        fields = line.split()
        if fields and fields[0] == symbol:
            fields[1 + _COLUMNS.index(column)] = value
            lines[k] = " ".join(fields) + "\n"
            return "".join(lines)
    raise KeyError(symbol)


def test_the_whole_file_checks_catch_a_digit_append():
    """Positive arm: put the old cells back and each check must name them."""
    text = _table_text()
    old_143nd = _with_cell(_with_cell(text, "143Nd", "xs_coh", "25.7"),
                           "143Nd", "xs_inc", "55.7")
    assert "143Nd" in _sum_rule_violations(
        _with_cell(old_143nd, "143Nd", "xs_scatt", "80.2"))
    assert "Gd.xs_abs" in _overprecise_cells(
        _with_cell(text, "Gd", "xs_abs", "49700.125"))
