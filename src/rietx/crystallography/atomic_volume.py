"""Average atomic volumes in molecular crystals, and the volume of one formula
unit they predict (Hofmann 2002).

A chemist who knows the formula knows roughly how much room one formula unit
takes in a crystal.  Kempster & Lipson (1972, *Acta Cryst.* B28, 3674) put it
at about 18 Å³ per C, N or O atom, hydrogen excluded.  They fitted that on
forty crystals and quote it as accurate to about 10 %, "only for a first
estimate".  Hofmann (2002) replaced the one number with an average volume per
element, fitted to 182 239 structures in the Cambridge Structural Database.
On that set the standard deviation of V_obs/V_est is 4.00 % for his table and
9.04 % for the 18 Å³ rule (§ 3).  So this module carries Hofmann's table, and
the 18 Å³ rule is cited only as its predecessor.

**The table** is Hofmann's Table 2, transcribed from the published PDF and
checked against the page image.  The page footer misprints the volume as B57.
:data:`HOFMANN_VOLUMES` maps an element to (v̄, Δv) in Å³ at 298 K.  Δv is the
mean error of the average (his eq. 11), never the scatter of one crystal.
Sixteen elements are absent, because the table prints a dash for each: He, Ne,
Ar, Kr, Pm, Po, At, Rn, Fr, Ra, Pu, Cm, Bk, Cf, Es and Fm.  Ac (74 Å³) and
Am (17 Å³) carry a volume and no mean error, since each occurs in one
structure (§ 3).  A formula holding either therefore has no esd.  Am's 17 Å³ is
small beside its neighbours, and it is kept as printed.  The table's other two
columns, Mighell et al. (1987) and their difference, are not Hofmann's values
and are not carried.

**Temperature.**  Eq. (1) writes V = Σ nᵢ v̄ᵢ (1 + ᾱT), with
ᾱ = (0.95 ± 0.03) × 10⁻⁴ K⁻¹ (§ 3).  The regression behind it, eqs (6) and
(7), folds the intercept at T = 0 into the volumes, so T there is absolute.
Table 2's caption and § 3 state the tabulated volumes at 298 K.  This module
therefore scales a tabulated volume by (1 + ᾱT)/(1 + ᾱ·298 K).  Reading the
table itself as the T = 0 volumes would make every 298 K volume 2.8 % larger.

**Two uncertainties, for two questions.**  The esd of a formula-unit volume is
eq. (13)'s: the mean errors add linearly, as Σ nᵢ Δvᵢ, and the expansion term
adds in quadrature.  It says how well the average is known, about 0.5 % for an
organic.  One crystal scatters about that average by far more.  The standard
deviation of V_obs/V_est is 4.00 % over the structures within 20 % of the
estimate (§ 3, Fig. 1).  Only 6049 of sample 1's 9112 structures lie within 5 %
(Table 1).  :data:`VOLUME_SCATTER` is that 4.00 %, and a check on one crystal
uses it.

**Scope.**  The table is fitted to organic and metal-organic crystals.  Hofmann
found 496 structures overestimated by 25-75 %, often highly ionic with small
cells, and says the volumes may not apply to inorganic substances (§ 3 (iii)).
Solvent the formula leaves out makes a cell larger than the estimate (513
structures underestimated by 25-75 %, § 3 (ii)).

**The window.**  :data:`VOLUME_RATIO_BOUNDS` is the 25 % boundary of § 3,
V_obs/V_est from 0.8 to 1.25 (Table 3's caption defines the lower edge).
1746 of the 182 239 structures lie beyond it.  737 of those are off by more
than 75 %, mainly because the database's Z was wrong.  A search window must not
exclude the true cell, so it takes this wide boundary rather than the 4 %
scatter.
"""

from __future__ import annotations

import math
import re

#: Hofmann (2002), Table 2: element → (v̄, Δv), Å³ at 298 K.  Δv is ``None``
#: where the table prints a volume and no mean error (Ac, Am).
HOFMANN_VOLUMES: dict[str, tuple[float, float | None]] = {
    "H": (5.08, 0.04), "Li": (22.6, 0.9), "Be": (36.0, 4.0),
    "B": (13.24, 0.17), "C": (13.87, 0.05), "N": (11.8, 0.3),
    "O": (11.39, 0.17), "F": (11.17, 0.15), "Na": (26.0, 3.0),
    "Mg": (36.0, 4.0), "Al": (39.6, 1.3), "Si": (37.3, 0.3),
    "P": (29.5, 0.2), "S": (25.2, 0.3), "Cl": (25.8, 0.3),
    "K": (36.0, 3.0), "Ca": (45.0, 6.0), "Sc": (42.0, 6.0),
    "Ti": (27.3, 1.8), "V": (24.0, 1.8), "Cr": (28.1, 1.5),
    "Mn": (31.9, 0.9), "Fe": (30.4, 0.7), "Co": (29.4, 1.3),
    "Ni": (26.0, 2.0), "Cu": (26.9, 1.0), "Zn": (39.0, 3.0),
    "Ga": (37.8, 1.5), "Ge": (41.6, 1.3), "As": (36.4, 1.3),
    "Se": (30.3, 1.1), "Br": (32.7, 0.6), "Rb": (42.0, 5.0),
    "Sr": (47.0, 4.0), "Y": (44.0, 3.0), "Zr": (27.0, 2.0),
    "Nb": (37.0, 2.0), "Mo": (38.0, 2.0), "Tc": (38.0, 5.0),
    "Ru": (37.3, 0.9), "Rh": (31.2, 1.0), "Pd": (35.0, 3.0),
    "Ag": (35.0, 2.0), "Cd": (51.0, 3.0), "In": (55.0, 3.0),
    "Sn": (52.8, 1.3), "Sb": (48.0, 1.6), "Te": (46.7, 1.9),
    "I": (46.2, 0.4), "Xe": (45.0, 8.0), "Cs": (46.0, 2.0),
    "Ba": (66.0, 4.0), "La": (58.0, 5.0), "Ce": (54.0, 5.0),
    "Pr": (57.0, 7.0), "Nd": (50.0, 4.0), "Sm": (50.0, 4.0),
    "Eu": (53.0, 4.0), "Gd": (56.0, 5.0), "Tb": (45.0, 7.0),
    "Dy": (50.0, 7.0), "Ho": (42.0, 5.0), "Er": (54.0, 5.0),
    "Tm": (49.0, 6.0), "Yb": (59.0, 4.0), "Lu": (35.0, 4.0),
    "Hf": (40.0, 4.0), "Ta": (43.0, 2.0), "W": (38.8, 1.6),
    "Re": (42.7, 1.8), "Os": (41.9, 0.6), "Ir": (34.3, 0.9),
    "Pt": (38.0, 2.0), "Au": (43.0, 2.0), "Hg": (38.0, 1.4),
    "Tl": (54.0, 4.0), "Pb": (52.0, 4.0), "Bi": (60.0, 4.0),
    "Ac": (74.0, None), "Th": (56.0, 5.0), "Pa": (60.0, 30.0),
    "U": (58.0, 4.0), "Np": (45.0, 6.0), "Am": (17.0, None),
}
#: The elements Table 2 lists with a dash: no structure gave a volume.
_NO_VOLUME = frozenset({"He", "Ne", "Ar", "Kr", "Pm", "Po", "At", "Rn", "Fr",
                        "Ra", "Pu", "Cm", "Bk", "Cf", "Es", "Fm"})
#: ᾱ and its mean error, K⁻¹ (Hofmann 2002, § 3).
THERMAL_EXPANSION = 0.95e-4
THERMAL_EXPANSION_ESD = 0.03e-4
#: The temperature Table 2 is quoted at, K.
TABLE_TEMPERATURE = 298.0
#: Standard deviation of V_obs/V_est for one crystal (Hofmann 2002, § 3).
VOLUME_SCATTER = 0.04
#: V_obs/V_est at the 25 % boundary of Hofmann (2002), § 3.
VOLUME_RATIO_BOUNDS = (0.8, 1.25)

_TOKEN = re.compile(r"([A-Z][a-z]?)|([(\[])|([)\]])|(\d+(?:\.\d+)?)|(\s+)")
_LEADING_COUNT = re.compile(r"\s*(\d+(?:\.\d+)?)")
#: A count written ``n.m`` straight after an element or a bracket and straight
#: before the next element or bracket, with ``n`` not zero.  The string reads two
#: ways: the decimal count n.m (``Fe2.95O4``), or a hydrate written with a full
#: stop, n of the first part and m of the second (``CuSO4.5H2O``).  Both readings
#: are grammatical and they differ, so the formula is refused.  ``n = 0`` reads
#: one way only (``Mg0.5SiO3``), because no formula writes a count of zero.
_DOT_TWO_WAYS = re.compile(r"(?<=[A-Za-z)\]])(\d+)\.(\d+)(?=[A-Z(\[])")


def _element(symbol: str, formula: str) -> str:
    if symbol in HOFMANN_VOLUMES:
        return symbol
    if symbol in _NO_VOLUME:
        raise ValueError(f"{formula!r}: Hofmann (2002) gives no average volume "
                         f"for {symbol}, so this formula has no estimate")
    raise ValueError(f"{formula!r}: {symbol!r} is not an element symbol")


def _parse_part(part: str, formula: str) -> dict[str, float]:
    stack: list[dict[str, float]] = [{}]
    last: dict[str, float] | None = None
    pos = 0
    while pos < len(part):
        m = _TOKEN.match(part, pos)
        if m is None:
            raise ValueError(f"cannot read {formula!r} at {part[pos:]!r}")
        pos = m.end()
        symbol, opening, closing, count, _space = m.groups()
        if symbol:
            el = _element(symbol, formula)
            stack[-1][el] = stack[-1].get(el, 0.0) + 1.0
            last = {el: 1.0}
        elif opening:
            stack.append({})
            last = None
        elif closing:
            if len(stack) == 1:
                raise ValueError(f"{formula!r}: a closing bracket with no opening one")
            last = stack.pop()
            for el, n in last.items():
                stack[-1][el] = stack[-1].get(el, 0.0) + n
        elif count:
            if last is None:
                raise ValueError(f"{formula!r}: the count {count} follows no "
                                 "element or bracket")
            for el, n in last.items():
                stack[-1][el] += n * (float(count) - 1.0)
            last = None
    if len(stack) != 1:
        raise ValueError(f"{formula!r}: an opening bracket is never closed")
    return stack[0]


def _parse_formula(formula: str) -> dict[str, float]:
    """Element counts of a chemical formula; the grammar is in
    :func:`formula_unit_volume`."""
    for m in _DOT_TWO_WAYS.finditer(formula):
        if int(m.group(1)) != 0:
            raise ValueError(
                f"{formula!r} reads two ways: the count {m.group(0)}, or the "
                f"adduct {formula[:m.end(1)]} · {formula[m.start(2):]}. Write "
                "an adduct with '·' (\"CuSO4·5H2O\"), and put a space after "
                "a decimal count (\"Fe2.95 O4\")")
    counts: dict[str, float] = {}
    for part in re.split(r"[·•*]", formula):
        m = _LEADING_COUNT.match(part)
        factor = float(m.group(1)) if m else 1.0
        body = part[m.end():] if m else part
        if not body.strip():
            raise ValueError(f"{formula!r}: an empty part")
        for el, n in _parse_part(body, formula).items():
            counts[el] = counts.get(el, 0.0) + factor * n
    counts = {el: n for el, n in counts.items() if n != 0.0}
    if not counts or any(n < 0.0 for n in counts.values()):
        raise ValueError(f"{formula!r} holds no positive element count")
    return counts


def formula_unit_volume(formula: str,
                        temperature: float = TABLE_TEMPERATURE
                        ) -> tuple[float, float | None]:
    """Volume one formula unit takes in a crystal (Å³), with its esd.

    The sum of average atomic volumes, Hofmann, D. W. M. (2002), *Acta Cryst.*
    B58, 489-493, eq. (1) with Table 2, at ``temperature`` in K.

    ``formula`` is written as a chemist writes it (``"C7H6O2"``).  Spaces are
    ignored, so a CIF ``_chemical_formula_sum`` (``"C7 H6 O2"``) reads too.
    Brackets take a count, ``·`` or ``*`` joins an adduct with an optional
    leading count (``"CuSO4·5H2O"``), and counts may be decimal.  A full stop
    that reads both as a decimal count and as a hydrate's dot raises, naming
    ``·`` (``"CuSO4.5H2O"``: 4.5 O, or CuSO4 with 5 H2O); a decimal count
    under 1 reads one way (``"Mg0.5SiO3"``), and a space after a decimal count
    ends the doubt (``"Fe2.95 O4"``).  A symbol that
    is not an element, or one the table has no volume for, raises naming it.  The esd is
    eq. (13)'s: the table's mean errors summed as Σ nᵢ Δvᵢ, and the expansion
    coefficient's error in quadrature, measured from the 298 K the table is
    quoted at.  It is ``None`` when an element has no mean error (Ac, Am).

    The esd says how well the average is known.  One crystal scatters about it
    by :data:`VOLUME_SCATTER`, 4.00 %, which is the number a check on a
    candidate cell must use.  The module docstring has both, the temperature
    reading and the scope: organic and metal-organic crystals.
    """
    if not temperature > 0.0:
        raise ValueError(f"temperature must be positive kelvin, got {temperature!r}")
    counts = _parse_formula(formula)
    a, t0 = THERMAL_EXPANSION, TABLE_TEMPERATURE
    tabulated = sum(n * HOFMANN_VOLUMES[el][0] for el, n in counts.items())
    volume = tabulated * (1.0 + a * temperature) / (1.0 + a * t0)
    errors = [HOFMANN_VOLUMES[el][1] for el in counts]
    if any(e is None for e in errors):
        return volume, None
    table_part = sum(n * e for n, e in zip(counts.values(), errors)) / tabulated
    expansion_part = THERMAL_EXPANSION_ESD * abs(
        temperature / (1.0 + a * temperature) - t0 / (1.0 + a * t0))
    return volume, volume * math.hypot(table_part, expansion_part)


__all__ = ["HOFMANN_VOLUMES", "TABLE_TEMPERATURE", "THERMAL_EXPANSION",
           "THERMAL_EXPANSION_ESD", "VOLUME_RATIO_BOUNDS", "VOLUME_SCATTER",
           "formula_unit_volume"]
