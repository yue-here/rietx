"""Tabulated ionic, covalent and metallic radii: Shannon (1976), Pyykkö & Atsumi (2009), Pauling (1960).

Three tables, for three different kinds of contact, and none is the bond table.

* **Ionic and crystal radii** — Shannon, R. D. (1976). *Acta Cryst.* A**32**,
  751–767, doi:10.1107/S0567739476001551, Table 1 (pp. 752–753), bundled as
  ``r_ion_Shannon.dat``. A radius belongs to an *ion in a coordination*: the
  element, its formal oxidation state, the coordination number and, for some
  3d ions, the spin state. Shannon prints two scales that differ by exactly
  0.14 Å (pp. 759–760): the effective **ionic** radius on r(ᵛᴵO²⁻) = 1.40 Å,
  kept "for comparison of unit-cell volumes and interatomic distances", and
  the **crystal** radius on r(ᵛᴵO²⁻) = 1.26 Å, which he says corresponds "more
  closely to the physical size of ions in a solid" (p. 760). A caller names
  the scale it wants; a sum of radii is only meaningful within one.
* **Covalent radii** — Pyykkö, P. & Atsumi, M. (2009a). *Chem. Eur. J.*
  **15**, 186–197, doi:10.1002/chem.200800987 (single bonds, r₁, Fig. 2), and
  (2009b) **15**, 12770–12779, doi:10.1002/chem.200901472 (double bonds, r₂,
  Fig. 3), bundled as ``r_cov_Pyykko.dat``. Additive radii,
  R(AB) = r(A) + r(B), fitted to molecular bond lengths — so they describe a
  *covalent bond in a molecule or a molecular fragment* (a rigid body), not a
  contact in an extended inorganic solid.
* **Metallic radii** — Pauling, L. (1960). *The Nature of the Chemical Bond*,
  3rd ed., Cornell University Press, Table 11-1 (p. 403), bundled as
  ``r_metal_Pauling.dat``: the metallic valence v, the radius for ligancy 12,
  R(L12), and the single-bond metallic radius R₁, for 72 elements. These
  describe *metal–metal contacts*, and the boride-type frameworks Pauling
  treats with the same scheme, in intermetallic and anion-free phases.

**The bond table does not read either.** :mod:`rietx.model.geometry` perceives
bonds with Cordero et al. (2008) covalent radii through gemmi's
``Element.covalent_r``, fitted to the contacts of the Cambridge Structural
Database, which is the question that table answers. Pyykkö's radii are smaller
for nearly every d- and f-block metal, so substituting them would turn long
cation–oxygen bonds into contacts; they are here for the places a single- or
double-bond *length* is the quantity wanted. Pauling's metallic radii are for
the contacts neither of the other two describes.

Three rules every lookup keeps, because a radius table is easy to make lie:

1. **No interpolation and no nearest row.** A coordination number Shannon did
   not tabulate is refused, naming the ones he did. Radius rises with CN almost
   everywhere, but not everywhere (Sb³⁺: IR(V) 0.80 > IR(VI) 0.76, printed so),
   so a fill-in rule would invent numbers the paper does not hold.
2. **No silent spin choice.** Where Shannon prints both a high- and a low-spin
   radius, the caller says which; the two differ by up to 0.17 Å (Co²⁺ VI).
3. **Flags travel with the value.** Shannon marks how each radius was derived
   and how reliable it is (``E``: estimated, which "implies poor or
   nonexistent structural data"; ``*``: at least five structures agree within
   ±0.01 Å). :class:`IonicRadius` carries them so a caller can see an
   estimate for what it is.
"""

from __future__ import annotations

import math
import operator
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal

from .species import _parse_species, element_symbol

_SHANNON_FILE = "r_ion_Shannon.dat"
_PYYKKO_FILE = "r_cov_Pyykko.dat"
_PAULING_FILE = "r_metal_Pauling.dat"

_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII",
          8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII", 13: "XIII",
          14: "XIV"}
_ARABIC = {v: k for k, v in _ROMAN.items()}

#: Shannon's two CN suffixes (Table 1 caption): square planar and pyramidal.
_CN_SUFFIX = {"SQ": "square planar", "PY": "pyramidal"}

#: A charge written after the element, either digit-first (``"Fe3+"``, the
#: CIF form) or sign-first (``"Fe+3"``, which TOPAS writes) — the two
#: spellings :func:`rietx.crystallography.neutron.normalize_species` accepts.
_CHARGE_RE = re.compile(r"^\s*\d*[A-Za-z]+(?:(?P<n>\d*)(?P<s>[+-])|(?P<s2>[+-])(?P<n2>\d+))?\s*$")


@dataclass(frozen=True)
class IonicRadius:
    """One printed row of Shannon (1976) Table 1, and the radius asked of it.

    ``radius`` is the column ``kind`` names, in Å: the crystal radius
    (``kind="crystal"``) or the effective ionic radius (``kind="ionic"``).
    Both are kept, so a caller that needs the other scale has it without a
    second lookup. ``cn`` is Shannon's own label — a Roman numeral, with
    ``SQ`` (square planar) or ``PY`` (pyramidal) where printed — and
    ``coordination`` its integer. ``flags`` is the derivation and reliability
    mark exactly as printed (``""`` where the row has none); see
    :attr:`estimated` and :attr:`reliable` for the two a caller most often
    needs. ``page`` is the journal page the row is printed on.
    """

    ion: str                  # "Fe", or "OH" / "D" for Shannon's two non-element rows
    charge: int               # formal oxidation state, signed
    cn: str                   # "VI", "IVSQ", "IIIPY"
    coordination: int         # 6, 4, 3
    spin: str | None          # "HS", "LS", or None where none is printed
    kind: Literal["ionic", "crystal"]
    radius: float             # Å, the column `kind` names
    ionic_radius: float       # Å, effective ionic radius (IR)
    crystal_radius: float     # Å, crystal radius (CR)
    flags: str                # as printed: "R*", "E", "", ...
    electronic_configuration: str  # Shannon's EC column, as printed
    page: int

    @property
    def estimated(self) -> bool:
        """Shannon's ``E``: estimated, "poor or nonexistent structural data"."""
        return "E" in self.flags

    @property
    def reliable(self) -> bool:
        """Shannon's ``*``: at least five structures agree within ±0.01 Å."""
        return "*" in self.flags


@lru_cache(maxsize=None)
def _shannon_rows() -> tuple[IonicRadius, ...]:
    """Parse ``r_ion_Shannon.dat`` once, in printed order (``kind`` ionic)."""
    text = (files("rietx.data") / _SHANNON_FILE).read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ion, charge, ec, cn, spin, cr, ir, flags, page, _block, _row = line.split()
        ir_value = float(ir)
        rows.append(IonicRadius(
            ion=ion, charge=int(charge), cn=cn,
            coordination=_ARABIC[cn.removesuffix("SQ").removesuffix("PY")],
            spin=None if spin == "-" else spin, kind="ionic", radius=ir_value,
            ionic_radius=ir_value, crystal_radius=float(cr),
            flags="" if flags == "-" else flags,
            electronic_configuration="" if ec == "-" else ec, page=int(page)))
    return tuple(rows)


@lru_cache(maxsize=None)
def _pyykko_rows() -> dict[str, tuple[float, float]]:
    """Parse ``r_cov_Pyykko.dat`` once: symbol → (r₁, r₂) in pm, r₂ maybe nan."""
    text = (files("rietx.data") / _PYYKKO_FILE).read_text(encoding="utf-8")
    table: dict[str, tuple[float, float]] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        symbol, _z, r1, r2, _cn = line.split()
        table[symbol] = (float(r1), float(r2))
    return table


def _ion_and_charge(species: str) -> tuple[str, int]:
    """(Shannon ion key, formal charge) of a species label such as ``"Fe3+"``.

    The element comes from :func:`rietx.crystallography.species._parse_species`,
    the package's one species parser; the charge is the trailing digit-first or
    sign-first suffix it drops (``"O2-"``, ``"F-"`` = −1, ``"Mn+4"``). Two of
    Shannon's rows are not elements and are reached by name: ``"OH-"``
    (hydroxide) and deuterium (``"D+"`` or ``"2H+"``). A label with no charge
    is refused — an ionic radius is a property of an oxidation state, and
    guessing the common one is the mistake this module exists to stop.
    """
    m = _CHARGE_RE.match(species)
    if m is None:
        raise ValueError(f"cannot read a charge from species {species!r}")
    sign = m.group("s") or m.group("s2")
    if sign is None:
        raise ValueError(
            f"species {species!r} carries no oxidation state; an ionic radius "
            f"needs one (write e.g. 'Fe3+' or 'O2-')")
    digits = m.group("n") if m.group("s") else m.group("n2")
    charge = int(digits or "1") * (1 if sign == "+" else -1)
    if charge == 0:
        raise ValueError(f"species {species!r} has charge 0; an ionic radius "
                         f"needs an oxidation state")
    s = species.strip()
    if s[:2].upper() == "OH" and not s[2:3].isalpha():
        return "OH", charge
    element, mass_number = _parse_species(species)
    if element == "H" and mass_number == 2:
        return "D", charge
    if element == "H" and mass_number not in (None, 1):
        raise KeyError(f"Shannon (1976) tabulates hydrogen and deuterium apart "
                       f"and has no row for mass number {mass_number} "
                       f"(species {species!r})")
    return element, charge


def _label(ion: str, charge: int) -> str:
    """"Fe3+" from ("Fe", 3): the spelling a message should use."""
    return f"{ion}{abs(charge)}{'+' if charge > 0 else '-'}"


def _cn_label(cn: int | str) -> str:
    """Shannon's label for a CN given as an integer or a Roman string."""
    if isinstance(cn, bool):
        raise TypeError(f"coordination number must be an int or a Roman numeral, not {cn!r}")
    if not isinstance(cn, str):
        cn = operator.index(cn)  # numpy integers; TypeError for floats
    if isinstance(cn, int):
        if cn not in _ROMAN:
            raise KeyError(f"Shannon (1976) tabulates no coordination number {cn}")
        return _ROMAN[cn]
    label = cn.strip().upper()
    base = label.removesuffix("SQ").removesuffix("PY")
    if base not in _ARABIC:
        raise ValueError(f"cannot read a coordination number from {cn!r} "
                         f"(write 6 or 'VI', or 'IVSQ' / 'IIIPY' for Shannon's "
                         f"square-planar and pyramidal rows)")
    return label


def ionic_radius(species: str, cn: int | str, *, spin: str | None = None,
                 kind: Literal["ionic", "crystal"] = "ionic") -> IonicRadius:
    """Shannon (1976) radius of ``species`` in coordination ``cn``.

    ``species`` names an ion with its oxidation state, in either charge
    spelling the package reads (``"Fe3+"``, ``"Fe+3"``, ``"O2-"``, ``"F-"``).
    ``cn`` is an integer or Shannon's Roman label; ``"IVSQ"`` and ``"IIIPY"``
    select his square-planar and pyramidal rows. An integer matches every row
    at that coordination: where that is one suffixed row (Pd²⁺ at 4 is printed
    only as ``IVSQ``) it is returned with its label in :attr:`IonicRadius.cn`,
    and where it is a plain and a suffixed row (Cu²⁺ at 4: ``IV`` and
    ``IVSQ``) it is refused as ambiguous rather than resolved. ``spin`` is ``"HS"`` or ``"LS"`` and is
    required exactly where Shannon prints both. ``kind`` picks the column that
    :attr:`IonicRadius.radius` reports: ``"ionic"`` (effective ionic radius,
    r(ᵛᴵO²⁻) = 1.40 Å, the scale bond-length sums are traditionally quoted on)
    or ``"crystal"`` (r(ᵛᴵO²⁻) = 1.26 Å); both values are on the result.

    Raises :class:`KeyError` naming what Shannon does tabulate when the ion,
    the oxidation state, the CN or the spin is not in Table 1 — never a
    neighbouring row, never an interpolation — and :class:`ValueError` for a
    label it cannot read or a choice the caller has to make. The flags are
    returned, not acted on: an ``E`` (estimated) row is still Shannon's value.

        >>> r = ionic_radius("Fe3+", 6, spin="HS")
        >>> r.radius, r.crystal_radius, r.flags
        (0.645, 0.785, 'R*')
        >>> ionic_radius("O2-", "VI", kind="crystal").radius
        1.26
    """
    if kind not in ("ionic", "crystal"):
        raise ValueError(f"kind must be 'ionic' or 'crystal', not {kind!r}")
    if spin is not None and spin.upper() not in ("HS", "LS"):
        raise ValueError(f"spin must be 'HS', 'LS' or None, not {spin!r}")
    ion, charge = _ion_and_charge(species)
    label = _cn_label(cn)
    rows = _shannon_rows()

    of_ion = [r for r in rows if r.ion == ion]
    if not of_ion:
        raise KeyError(f"Shannon (1976) Table 1 has no row for {ion} "
                       f"(read from species {species!r})")
    of_charge = [r for r in of_ion if r.charge == charge]
    if not of_charge:
        charges = ", ".join(f"{c:+d}" for c in sorted({r.charge for r in of_ion}))
        raise KeyError(f"Shannon (1976) tabulates {ion} only at charge {charges}, "
                       f"not {charge:+d} (species {species!r})")

    tabulated = sorted({r.cn for r in of_charge},
                       key=lambda c: (_ARABIC[c.removesuffix("SQ").removesuffix("PY")], c))
    if not isinstance(cn, str):
        cn = operator.index(cn)
        at_cn = [r for r in of_charge if r.coordination == cn]
    else:
        at_cn = [r for r in of_charge if r.cn == label]
    if not at_cn:
        raise KeyError(f"Shannon (1976) tabulates {_label(ion, charge)} at CN "
                       f"{', '.join(tabulated)} only, not {label}; no radius is "
                       f"interpolated (species {species!r})")
    labels = sorted({r.cn for r in at_cn})
    if len(labels) > 1:
        raise ValueError(f"{_label(ion, charge)} at CN {cn} matches {' and '.join(labels)}; "
                         f"pass cn={labels[0]!r} or one of {labels[1:]!r}")

    spins = sorted({r.spin for r in at_cn if r.spin is not None})
    if spin is None:
        if len(at_cn) > 1:
            raise ValueError(f"Shannon (1976) gives {_label(ion, charge)} {labels[0]} in "
                             f"{' and '.join(spins)}; pass spin= one of {spins!r}")
        row = at_cn[0]
    else:
        match = [r for r in at_cn if r.spin == spin.upper()]
        if not match:
            printed = (f"only in {' and '.join(spins)}" if spins
                       else "with no spin state")
            raise KeyError(f"Shannon (1976) tabulates {_label(ion, charge)} {labels[0]} "
                           f"{printed}, not {spin.upper()} (species {species!r})")
        row = match[0]
    value = row.ionic_radius if kind == "ionic" else row.crystal_radius
    return IonicRadius(**{**row.__dict__, "kind": kind, "radius": value})


def covalent_radius(element: str, order: Literal[1, 2] = 1) -> float:
    """Pyykkö & Atsumi (2009) covalent radius of ``element``, in Å.

    ``order=1`` is the single-bond radius r₁ (2009a, Fig. 2; Z = 1–118) and
    ``order=2`` the double-bond radius r₂ (2009b, Fig. 3; 108 elements). A
    bond length is estimated as r(A) + r(B) at the bond order both atoms take
    part in. A charge or mass number in ``element`` is dropped
    (:func:`rietx.crystallography.species.element_symbol`): these are radii
    of neutral atoms in covalent bonds.

    **For covalent bonds — molecules, molecular fragments, rigid bodies — and
    not for the bond table.** :mod:`rietx.model.geometry` perceives bonds in
    extended solids with Cordero et al. (2008) radii through gemmi, and these
    radii do not replace them: Pyykkö's are smaller for nearly every d- and
    f-block metal, which would turn long cation–oxygen bonds into contacts.

    Raises :class:`KeyError` naming the element where the paper prints no
    radius at that order (r₂ of H, He, Fm, No, Nh–Og).

        >>> covalent_radius("C"), covalent_radius("C", order=2)
        (0.75, 0.67)
    """
    try:
        order_ok = not isinstance(order, bool) and operator.index(order) in (1, 2)
    except TypeError:
        order_ok = False
    if not order_ok:
        raise ValueError(f"order must be 1 (single bond) or 2 (double bond), not {order!r}")
    symbol = element_symbol(element)
    row = _pyykko_rows().get(symbol)
    value = None if row is None else row[operator.index(order) - 1]
    if value is None or not math.isfinite(value):
        source = "2009a (single bonds)" if order == 1 else "2009b (double bonds)"
        raise KeyError(f"Pyykkö & Atsumi {source} print no r{order} for {symbol} "
                       f"(read from {element!r})")
    return value / 100.0


@dataclass(frozen=True)
class MetallicRadius:
    """One entry of Pauling (1960) Table 11-1, and the radius asked of it.

    ``radius`` is the column ``ligancy`` names, in Å: R₁, the single-bond
    metallic radius (``ligancy=1``), or R(L12), the radius for ligancy 12
    (``ligancy=12``). Both are kept, with the metallic valence ``valence``
    that relates them. ``flags`` is ``()`` for a cell as printed, or names
    what differs: ``v_assumed`` (valence printed in parentheses: P, S, Se,
    Te), ``v_corrected`` (Eu), ``r12_corrected`` (Gd), ``label_corrected``
    (Sr, printed "Sn") and ``r12_off_relation`` (Pm, kept as printed);
    ``as_printed`` holds the cell a correction replaced. ``page`` is the
    book page of the table.
    """

    element: str
    ligancy: Literal[1, 12]
    radius: float              # Å, the column `ligancy` names
    r1: float                  # Å, R₁
    r12: float                 # Å, R(L12)
    valence: float             # metallic valence v
    flags: tuple[str, ...]
    as_printed: str            # "" or e.g. "r12=2.804"
    page: int


@lru_cache(maxsize=None)
def _pauling_rows() -> dict[str, MetallicRadius]:
    """Parse ``r_metal_Pauling.dat`` once: symbol → entry (``ligancy`` 1)."""
    text = (files("rietx.data") / _PAULING_FILE).read_text(encoding="utf-8")
    table: dict[str, MetallicRadius] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        symbol, v, r12, r1, page, flags, printed = line.split()
        table[symbol] = MetallicRadius(
            element=symbol, ligancy=1, radius=float(r1), r1=float(r1),
            r12=float(r12), valence=float(v),
            flags=() if flags == "-" else tuple(flags.split(",")),
            as_printed="" if printed == "-" else printed, page=int(page))
    return table


def metallic_radius(element: str, *, ligancy: Literal[1, 12] = 1) -> MetallicRadius:
    """Pauling (1960) metallic radius of ``element``, Table 11-1 (p. 403).

    ``ligancy=1`` gives R₁, "the metallic radius" (p. 404): the radius for a
    bond of bond number 1, from which Pauling builds a contact of bond number
    n as D(n) = D(1) − 0.600 log n (Eq. 11-1, p. 400). ``ligancy=12`` gives
    R(L12), the radius in a twelve-coordinated metal; the two are related by
    R(L12) = R₁ + 0.300 log(12/v) (p. 412). Ligancy is Pauling's word for
    coordination number, and only these two columns are printed — no other
    value is interpolated.

    **For metal–metal contacts in intermetallic and anion-free phases**, and
    for boride-type frameworks, which Pauling treats in the same scheme
    (pp. 365–366). Not for a cation–anion contact, which is Shannon's
    (:func:`ionic_radius`), nor a bond in a molecule (:func:`covalent_radius`).
    Not the bond table: :mod:`rietx.model.geometry` stays on Cordero et al.
    (2008) through gemmi. A mass number in ``element`` is dropped; a charge
    is refused, since an ion has no metallic radius.

    Three cells of the printed table are misprints, corrected in the bundled
    file with the printed value kept on the result (:attr:`MetallicRadius.as_printed`):
    Gd R(L12) (printed 2.804, 1.804 by Pauling's own relation and the 1947
    table), Eu v (printed 3, 2 by its radii and the 1947 table) and the Sr
    cell labelled "Sn". Pm R(L12) breaks the relation by 0.020 Å and is
    returned as printed, flagged ``r12_off_relation``.

    Raises :class:`ValueError` for a ligancy other than 1 or 12 or a charged
    species, and :class:`KeyError` naming the elements Table 11-1 prints when
    ``element`` is not among them (C, N, O, the halogens, the noble gases,
    Fr–Ac and every actinide but Th and U).

        >>> metallic_radius("La").radius, metallic_radius("La", ligancy=12).radius
        (1.69, 1.871)
    """
    try:
        ligancy_ok = not isinstance(ligancy, bool) and operator.index(ligancy) in (1, 12)
    except TypeError:
        ligancy_ok = False
    if not ligancy_ok:
        raise ValueError(f"ligancy must be 1 (R1, bond number 1) or 12 (R(L12)), "
                         f"the two Pauling (1960) Table 11-1 prints, not {ligancy!r}")
    m = _CHARGE_RE.match(element)
    if m is not None and (m.group("s") or m.group("s2")):
        raise ValueError(f"species {element!r} carries a charge; a metallic radius "
                         f"belongs to a neutral metal atom (use ionic_radius for an ion)")
    symbol = element_symbol(element)
    table = _pauling_rows()
    row = table.get(symbol)
    if row is None:
        raise KeyError(f"Pauling (1960) Table 11-1 prints no metallic radius for "
                       f"{symbol} (read from {element!r}); it prints "
                       f"{' '.join(table)}")
    if operator.index(ligancy) == 1:
        return row
    return MetallicRadius(**{**row.__dict__, "ligancy": 12, "radius": row.r12})
