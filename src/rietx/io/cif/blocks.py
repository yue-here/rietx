"""The structure block every CIF this build writes (WP-1319 C-c, issue #756 § 2.1).

One function writes a phase's block, :func:`write_structure_block`, for
:meth:`~rietx.schemas.structure.Structure.to_cif` and for the structure part of
:func:`~rietx.io.exporters.write_refinement_cif`.  What it states, beyond the
cell and the sites:

**The setting, three ways and never the stored string.**  A bare
Hermann-Mauguin symbol names 40 of gemmi's settings ambiguously (``F d -3 m``
is two origins), so the block writes the resolved ``xhm()`` under
``_space_group_name_H-M_alt``, the Hall symbol, the IT number, the crystal
system, and the whole operation loop with ids.  The dictionary's own text says
an H-M symbol cannot fix the origin and only the Hall symbol or the operations
can (ITC Vol. G ch. 4.1).  The loop's order is
:func:`~rietx.model.geometry.symmetry_operations`'s, the order a geometry
loop's symmetry codes index, and this block is the only writer of it.  The
deprecated ``_symmetry_space_group_name_H-M`` is not written (WP-1319 decision
3).  A phase carrying its own operation list states the list, its label under
``_alt``, and the crystal system its point group and lattice fix.  An IT number
and a Hall symbol are stated only where the list *is* a tabulated setting's
operation set, since otherwise nothing here can name its type.

**U, not B** (decision 5).  ``_atom_site_U_iso_or_equiv`` with
``_atom_site_adp_type`` ``Uiso`` or ``Uani``; :func:`u_from_b` picks the double
the reader turns back into the stored B.

**What the cell holds**, from the sites, their multiplicities and their
occupancies (:func:`~rietx.optimize.qpa.phase_zmv`): ``_cell_volume`` (no su:
a structure carries no covariance, decision 6), ``_cell_formula_units_Z``,
``_chemical_formula_sum`` in Hill order, ``_chemical_formula_weight`` and
``_exptl_crystal_density_diffrn``, and an ``_atom_type`` loop.  A type symbol
is the species rietx computes
(:func:`~rietx.crystallography.scattering.written_species`): ``Cu+`` is
written ``Cu1+``, and an ion the table lacks is written as the neutral atom
with ``_atom_type_description`` saying so, the one channel a file has for it.

**What wrote it**: ``_audit_creation_date``, ``_audit_creation_method`` and
the ``_audit_conform`` loop naming the dictionaries and versions the tags were
checked against (``tests/test_cif_registry.py``), with no location item since
a path is not portable (ITC Vol. G ch. 3.1).

A refusal in the structure half raises before anything is set on the block:
every value is formatted first (:mod:`rietx.io.cif.numbers`).  The magnetic
half reads the cell back off the block, so it runs after that half is set and
a refusal there leaves the structure items in place; every caller here then
discards the document, so no file is written.

References
----------
- Hall, Allen & Brown (1991), *Acta Cryst.* **A47**, 655: the CIF format.
- Hall, S. R. (1981), *Acta Cryst.* **A37**, 517: the Hall symbol.
- Hall, S. R. et al. (2006), *International Tables for Crystallography* Vol. G,
  ch. 4.1, pp. 254-255: the symmetry items and the operation loop.
- McMahon, B. (2006), ITC Vol. G, ch. 3.1, § 3.1.8, pp. 85-87:
  ``_audit_conform``.
- COMCIFS ``cif_core.dic`` 3.3.0, doi:10.1107/cifdic_core_3.3.0;
  ``cif_pd.dic`` 2.5.0; ``cif_mag.dic`` 0.9.9: every tag's name and contents.
- Hill, E. A. (1900), *J. Am. Chem. Soc.* **22**, 478: the formula order
  ``cif_core.dic``'s CHEMICAL_FORMULA rule (5) prescribes.
- Willis, B. T. M. & Pryor, A. W. (1975), *Thermal Vibrations in
  Crystallography*: B = 8π²U.
"""

from __future__ import annotations

import datetime
import math
import re

import gemmi

from .numbers import number, text

#: The CIF 1.1 magic line, the first line of every file this module writes.
MAGIC = "#\\#CIF_1.1"

#: ``(dict_name, dict_version)`` per dictionary the written tags conform to:
#: the vendored files ``tests/test_cif_registry.py`` checks every tag against.
CORE_DICTIONARY = ("cif_core.dic", "3.3.0")
POWDER_DICTIONARY = ("cif_pd.dic", "2.5.0")
MAGNETIC_DICTIONARY = ("cif_mag.dic", "0.9.9")

#: The output kinds this block serves: a structure CIF and a refinement CIF.
BLOCK_KINDS = ("structure", "refinement")

#: The sources of the scattering tables a fit computes with, for
#: ``_atom_type_scat_source``: Waasmaier & Kirfel (1995), *Acta Cryst.* A51,
#: 416 for :mod:`rietx.crystallography.scattering`'s X-ray f0; ITC Vol. C
#: (2004) Table 6.1.1.4 for its tabulated ions; Sears (1992), *Neutron News*
#: 3(3), 26 for :mod:`rietx.crystallography.neutron`'s b; Waasmaier & Kirfel's
#: own fit to Rez, Rez & Grant (1994), *Acta Cryst.* A50, 481, Table 2 for the
#: ``O2-`` row, which their 1995 paper does not print (#1039).  Author and year
#: only, because checkCIF's PLATON stops reading the whole block at a long
#: one: a 113-character value left every computed-against-reported row empty
#: on 2026-10-09, and 40 characters did not (``SCAT_SOURCE_MAX``).
_XRAY_SOURCE = "Waasmaier & Kirfel (1995)"
_XRAY_ITC_SOURCE = "ITC C (2004) 6.1.1.4"
_XRAY_O2_SOURCE = "W&K, Rez et al. (1994)"
_NEUTRON_SOURCE = "Sears (1992)"

#: The longest ``_atom_type_scat_source`` value written, held by test.
SCAT_SOURCE_MAX = 40


def _today() -> str:
    """The ``_audit_creation_date``; a test making two files equal patches it."""
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# B and U
# ---------------------------------------------------------------------------

def b_from_u(u: float) -> float:
    """B = 8π²U (Willis & Pryor 1975), in the one spelling the reader uses.

    :func:`~rietx.crystallography.cif.structure_from_cif` calls this, so
    :func:`u_from_b` can choose its U against the exact arithmetic that reads it
    back.
    """
    return u * 8.0 * math.pi ** 2


def u_from_b(b: float) -> float:
    """The U written for a stored B: the double :func:`b_from_u` takes back to it.

    ``b / 8π²`` alone reads back one ulp off for 12.6 % of B values (measured
    on 400 000, uniform on [0, 5) Å² and rounded to one to four decimals), and
    for those no double reads back exactly.  Two or three neighbouring doubles
    can also read back as the same B.  So the candidates are ``b / 8π²`` and
    two neighbours each side, and the one read back nearest ``b`` is kept, the
    shortest ``repr`` and then the smallest on a tie.  B → U → B is then exact
    wherever any U reaches B and one ulp off elsewhere; a U read from a file
    is written back as the file spelled it (``0.01385``, never its neighbour
    ``0.013849999999999998``); and a written file is a fixed point of a read
    and a second write, because the U chosen for B is also the one chosen for
    the B it reads back as.
    """
    b = float(b)
    u = b / (8.0 * math.pi ** 2)
    if not math.isfinite(u):
        return u
    candidates = {u}
    for direction in (-math.inf, math.inf):
        c = u
        for _ in range(2):
            c = math.nextafter(c, direction)
            candidates.add(c)
    return min(candidates,
               key=lambda c: (abs(b_from_u(c) - b), len(repr(c)), c))


# ---------------------------------------------------------------------------
# block names
# ---------------------------------------------------------------------------

def block_name(name: str, index: int, taken: set[str]) -> str:
    """One CIF data-block name, unique within the document.

    A block name is a **key**, and ``\\W+`` collapses distinct phase names onto
    one: ``"ph 1"`` and ``"ph-1"`` both become ``ph_1``, and a two-phase
    mixture of one material under one name needs no collapsing at all.  gemmi
    answers a duplicate with a bare ``RuntimeError``, so neither reached a
    file.  The phase's index distinguishes them, being the one thing a phase
    carries that is unique by construction; the reader names a phase after its
    block, so the respelled name is what comes back.  The class is ASCII: a
    CIF 1.1 block name is ASCII only, and ``data_α_Fe`` behind the magic line
    is a file :func:`~rietx.crystallography.cif.structure_from_cif` refuses.
    Hall, Allen & Brown (1991) for the block-name rule.
    """
    stem = re.sub(r"\W+", "_", name, flags=re.ASCII) or f"phase_{index}"
    chosen, suffix = stem, index
    # CIF block names are case-insensitive, and so is gemmi's duplicate check
    while chosen.lower() in taken:
        chosen = f"{stem}_{suffix}"
        suffix += 1
    taken.add(chosen.lower())
    return chosen


# ---------------------------------------------------------------------------
# the parts
# ---------------------------------------------------------------------------

def cell_pairs(phase) -> list[tuple[str, str]]:
    """The six cell items, each through the number rule with its su."""
    c = phase.cell
    return ([(f"_cell_length_{n}", _parameter(f"_cell_length_{n}", getattr(c, n)))
             for n in ("a", "b", "c")]
            + [(f"_cell_angle_{n}", _parameter(f"_cell_angle_{n}", getattr(c, n)))
               for n in ("alpha", "beta", "gamma")])


def _parameter(tag: str, p, where: str | None = None) -> str:
    return number(tag, p.value, p.stderr, where=where)


def symmetry_items(phase) -> tuple[list[tuple[str, str]], list[str]]:
    """The space-group pairs and the operation triplets, in the codes' order.

    The group is :func:`~rietx.crystallography.symmetry.resolve_group`'s, so a
    phase carrying its own list is that list.  ITC Vol. G ch. 4.1 (Hall et al.
    2006) for which item fixes what; Hall (1981) for the Hall symbol.
    """
    from ...crystallography.symmetry import OperatorGroup, resolve_group
    from ...model.geometry import symmetry_operations

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    triplets = symmetry_operations(sg)
    if isinstance(sg, OperatorGroup):
        # the list is the group: a tabulated setting with exactly these
        # operations names its type and its Hall symbol, and nothing else can
        named = gemmi.find_spacegroup_by_ops(sg.operations())
    else:
        named = sg
    pairs = [("_space_group_crystal_system",
              text("_space_group_crystal_system", sg.crystal_system_str()))]
    if named is not None:
        pairs.append(("_space_group_IT_number", str(int(named.number))))
    pairs.append(("_space_group_name_H-M_alt",
                  text("_space_group_name_H-M_alt", sg.xhm())))
    if named is not None:
        pairs.append(("_space_group_name_Hall",
                      text("_space_group_name_Hall", named.hall)))
    return pairs, [text("_space_group_symop_operation_xyz", t) for t in triplets]


def _multiplicities(phase) -> list[int]:
    """Each site's multiplicity, |G|/|G_x| (:func:`~rietx.crystallography.symmetry.site_orbit`)."""
    import numpy as np

    from ...crystallography.symmetry import resolve_group, site_orbit

    sg = resolve_group(phase.space_group, phase.symmetry_operations)
    return [site_orbit(sg, np.array([a.x.value, a.y.value, a.z.value],
                                    dtype=np.float64)).multiplicity
            for a in phase.atoms]


def _types(phase) -> tuple[list[str], dict[str, str]]:
    """Each site's written type symbol, and a description per substituted one.

    :func:`~rietx.crystallography.scattering.written_species` is the one rule
    (WP-1527): the atom rietx computes.  An ion the table lacks is written as
    its neutral atom, and ``_atom_type_description`` names the label it was
    written for, since a CIF has no diagnostics channel.
    """
    from ...crystallography.scattering import written_species

    symbols: list[str] = []
    replaced: dict[str, list[str]] = {}
    for atom in phase.atoms:
        written, fallback = written_species(atom.species)
        symbols.append(written)
        if fallback is not None and fallback.species not in replaced.get(written, []):
            replaced.setdefault(written, []).append(fallback.species)
    notes = {
        sym: (f"written for {', '.join(originals)}: rietx's X-ray table has no "
              f"such ion, so a fit computes the neutral atom")
        for sym, originals in replaced.items()}
    return symbols, notes


def _scat_source(symbol: str, probe: str | None) -> str:
    """Where the scattering factor of ``symbol`` comes from, for ``probe``."""
    from ...crystallography.scattering import _ITC_IONS, normalize_species

    try:
        key = normalize_species(symbol)
    except KeyError:
        key = None
    if key in _ITC_IONS:
        xray = _XRAY_ITC_SOURCE
    elif key == "O2-":
        xray = _XRAY_O2_SOURCE
    else:
        xray = _XRAY_SOURCE
    if probe == "xray":
        return xray
    if probe == "neutron":
        return _NEUTRON_SOURCE
    return f"{xray}; {_NEUTRON_SOURCE}"


def _hill(counts: dict[str, float], z: int, reduced: bool) -> str:
    """``_chemical_formula_sum``: per formula unit, Hill order (Hill 1900).

    Carbon first and hydrogen next when there is carbon, every other element
    alphabetically, a count of one left out (``cif_core.dic``
    CHEMICAL_FORMULA rule 5).  A composition that does not reduce to integers
    (a partial occupancy) states its counts to four decimals.
    """
    order = sorted(counts)
    if "C" in counts:
        order = ["C", *(["H"] if "H" in counts else []),
                 *(e for e in order if e not in ("C", "H"))]
    parts = []
    for element in order:
        n = counts[element] / z
        if reduced:
            k = int(round(n))
            parts.append(element if k == 1 else f"{element}{k}")
        elif n > 0.0:
            count = f"{n:.4f}".rstrip("0").rstrip(".")
            parts.append(element if count == "1" else f"{element}{count}")
    return " ".join(parts)


def _reduces(counts: dict[str, float], tol: float = 0.02) -> bool:
    """Whether every count is a positive integer to ``tol``, ``_formula_units``' test."""
    return all(round(n) > 0 and abs(n - round(n)) <= tol for n in counts.values())


def site_rows(phase, *, adp: str, types: list[str] | None = None
              ) -> tuple[list[str], list[list[str]], list[list[str]]]:
    """The ``_atom_site`` columns and rows, and the ``_atom_site_aniso`` rows.

    ``adp`` is ``"U"`` (``_atom_site_U_iso_or_equiv``, the structure block) or
    ``"B"`` (``_atom_site_B_iso_or_equiv``, the GSAS-II phase CIF, whose
    import was measured on B).  An anisotropic site's isotropic column carries
    U_eq of its tensor (Fischer & Tillmanns 1988, *Acta Cryst.* **C44**, 775),
    so a reader ignoring the aniso loop still sees its magnitude.  The two
    disorder columns appear only when a site declares one.
    """
    from ...crystallography.adp import U_NAMES, u_equivalent

    cell6 = phase.cell.lengths_angles()
    types = types if types is not None else [a.species for a in phase.atoms]
    iso_tag = f"_atom_site_{adp}_iso_or_equiv"
    disorder = [k for k in ("disorder_assembly", "disorder_group")
                if any(getattr(a, k) is not None for a in phase.atoms)]
    columns = ["label", "type_symbol", "fract_x", "fract_y", "fract_z",
               "occupancy", f"{adp}_iso_or_equiv", "adp_type", *disorder]
    rows = []
    for j, a in enumerate(phase.atoms):
        if a.aniso is not None:
            u_eq = u_equivalent(a.aniso.values(), cell6)
            iso = number(iso_tag, u_eq if adp == "U" else b_from_u(u_eq), where=a.label)
            kind = "Uani"
        elif adp == "U":
            su = None if a.biso.stderr is None else a.biso.stderr / (8.0 * math.pi ** 2)
            iso, kind = number(iso_tag, u_from_b(a.biso.value), su, where=a.label), "Uiso"
        else:
            iso, kind = _parameter(iso_tag, a.biso, a.label), "Biso"
        rows.append([
            text("_atom_site_label", a.label),
            text("_atom_site_type_symbol", types[j], where=a.label),
            *(_parameter(f"_atom_site_fract_{n}", getattr(a, n), a.label) for n in "xyz"),
            _parameter("_atom_site_occupancy", a.occ, a.label), iso, kind,
            *("." if getattr(a, k) is None
              else text(f"_atom_site_{k}", getattr(a, k), where=a.label)
              for k in disorder),
        ])
    aniso = [[text("_atom_site_aniso_label", a.label)]
             + [_parameter(f"_atom_site_aniso_U_{n[1:]}", getattr(a.aniso, n), a.label)
                for n in U_NAMES]
             for a in phase.atoms if a.aniso is not None]
    return columns, rows, aniso


def write_sites(block, columns: list[str], rows: list[list[str]],
                aniso: list[list[str]]) -> None:
    """Set :func:`site_rows`' loops on ``block``."""
    loop = block.init_loop("_atom_site_", columns)
    for row in rows:
        loop.add_row(row)
    if aniso:
        uloop = block.init_loop("_atom_site_aniso_", [
            "label", "U_11", "U_22", "U_33", "U_12", "U_13", "U_23"])
        for row in aniso:
            uloop.add_row(row)


# ---------------------------------------------------------------------------
# the block
# ---------------------------------------------------------------------------

def write_structure_block(block, phase, *, kind: str = "structure",
                          probe: str | None = None,
                          moment_magnitude_esds: dict[str, float] | None = None,
                          created: str | None = None,
                          composition: bool = True,
                          cell_volume_su: float | None = None,
                          dispersion: dict[str, tuple[float, float, str]] | None = None
                          ) -> None:
    """Write one phase's structure block into a gemmi CIF ``block``.

    ``kind`` is ``"structure"`` or ``"refinement"``, which adds ``cif_pd.dic``
    to the ``_audit_conform`` loop; ``probe`` (``"xray"``, ``"neutron"`` or
    ``None`` for a file that names no experiment) chooses what
    ``_atom_type_scat_source`` cites; ``created`` overrides today's date.
    ``composition=False`` leaves out everything read off the sites as
    chemistry (formula, Z, Mr, density, the ``_atom_type`` loop): a Le Bail or
    Pawley phase's atoms are a scaffold, and ``C8`` from its dummy carbon is a
    fiction (``refine._symmetry_silence_diagnostics``), so its sites are
    marked ``_atom_site_calc_flag dum`` instead.  ``cell_volume_su`` is the
    volume's esd through the cell covariance
    (:func:`~rietx.model.geometry.cell_volumes`), which a refinement has and a
    structure does not (decision 6).  ``dispersion`` maps each site's species to
    the (f′, f″, source) a fit computed with, written into the ``_atom_type``
    loop.  A
    magnetic phase adds the magCIF half (:mod:`rietx.crystallography.magcif`)
    and ``cif_mag.dic``.  The module docstring says what is written and why;
    the references are there.
    """
    from ..._about import DIST_NAME
    from ...crystallography import magcif
    from ...optimize.qpa import phase_zmv
    from ...refine import _VERSION

    if kind not in BLOCK_KINDS:
        raise ValueError(f"kind={kind!r}: expected one of {BLOCK_KINDS}")
    # every value is formatted before the first is set, so a refusal leaves
    # the block, and the file, unwritten
    dictionaries = [CORE_DICTIONARY, *([POWDER_DICTIONARY] if kind == "refinement" else []),
                    *([MAGNETIC_DICTIONARY] if phase.magnetic_symmetry is not None else [])]
    pairs = [
        ("_audit_creation_date", text("_audit_creation_date", created or _today())),
        ("_audit_creation_method",
         text("_audit_creation_method", f"{DIST_NAME} {_VERSION}")),
    ]
    conform = [[text("_audit_conform_dict_name", name),
                text("_audit_conform_dict_version", version)]
               for name, version in dictionaries]
    cell = cell_pairs(phase)
    types, notes = _types(phase)
    # the site values are refused before an orbit is asked of them: a NaN
    # coordinate is the number rule's to name, not the orbit's
    columns, rows, aniso = site_rows(phase, adp="U", types=types)
    symmetry, triplets = symmetry_items(phase)
    multiplicities = _multiplicities(phase)
    at = columns.index("adp_type") + 1
    columns.insert(at, "site_symmetry_multiplicity")
    for row, m in zip(rows, multiplicities, strict=True):
        row.insert(at, str(m))

    chemistry: list[tuple[str, str]] = []
    after_cell: list[tuple[str, str]] = []
    type_rows: list[list[str]] = []
    anomalous: dict[str, list[str]] = {}
    zmv = phase_zmv(None, phase.cell.lengths_angles(),
                    [(a.species, a.x.value, a.y.value, a.z.value, a.occ.value)
                     for a in phase.atoms], multiplicities=multiplicities)
    after_cell.append(("_cell_volume",
                       number("_cell_volume", zmv.cell_volume, cell_volume_su)))
    # WP-1810: a phase with a rigid body states which coordinates the body
    # placed, cif_core's _atom_site_refinement_flags_posn ``G`` (rigid group)
    # or ``R`` (riding), and _atom_site_calc_flag ``calc`` for a riding H.
    # Only such a phase writes the columns, so every other block is unchanged.
    bodies = phase.rigid_bodies
    group = {lab for b in bodies for lab in b.atoms}
    riding = {lab for b in bodies for lab in b.riding}
    if bodies:
        columns.append("refinement_flags_posn")
        for row, a in zip(rows, phase.atoms, strict=True):
            row.append(("R" if a.label in riding else "G") if a.label in group else ".")
    if not composition:
        columns.append("calc_flag")
        for row in rows:
            row.append("dum")
    elif bodies:
        columns.append("calc_flag")
        for row, a in zip(rows, phase.atoms, strict=True):
            row.append("calc" if a.label in riding else "d")
    if phase.atoms and composition:
        # zmv.z is already 1 for a composition that does not reduce
        # (qpa._formula_units), so its molar mass is the cell's
        z = zmv.z
        chemistry = [
            ("_chemical_formula_sum",
             text("_chemical_formula_sum",
                  _hill(zmv.element_counts, z, _reduces(zmv.element_counts)))),
            ("_chemical_formula_weight",
             number("_chemical_formula_weight", zmv.molar_mass)),
        ]
        after_cell.append(("_cell_formula_units_Z", str(z)))
        symmetry = [*symmetry, ("_exptl_crystal_density_diffrn",
                                number("_exptl_crystal_density_diffrn", zmv.density))]
        in_cell: dict[str, float] = {}
        for sym, atom, m in zip(types, phase.atoms, multiplicities, strict=True):
            in_cell[sym] = in_cell.get(sym, 0.0) + atom.occ.value * m
            if dispersion is not None:
                fp, fpp, source = dispersion[atom.species]
                anomalous.setdefault(sym, [
                    number("_atom_type_scat_dispersion_real", fp, where=sym),
                    number("_atom_type_scat_dispersion_imag", fpp, where=sym),
                    text("_atom_type_scat_dispersion_source", source)])
        for sym, count in in_cell.items():
            type_rows.append([
                text("_atom_type_symbol", sym),
                number("_atom_type_number_in_cell", count, where=sym),
                # ``.`` unquoted: inapplicable, where a quoted one is text
                *([text("_atom_type_description", notes[sym]) if sym in notes else "."]
                  if notes else []),
                text("_atom_type_scat_source", _scat_source(sym, probe)),
                *anomalous.get(sym, []),
            ])

    for tag, value in [*pairs]:
        block.set_pair(tag, value)
    loop = block.init_loop("_audit_conform_", ["dict_name", "dict_version"])
    for row in conform:
        loop.add_row(row)
    for tag, value in [*chemistry, *cell, *after_cell, *symmetry]:
        block.set_pair(tag, value)
    ops = block.init_loop("_space_group_symop_", ["id", "operation_xyz"])
    for idx, triplet in enumerate(triplets):
        ops.add_row([str(idx + 1), triplet])
    if type_rows:
        tloop = block.init_loop("_atom_type_", [
            "symbol", "number_in_cell", *(["description"] if notes else []),
            "scat_source", *(["scat_dispersion_real", "scat_dispersion_imag",
                              "scat_dispersion_source"] if anomalous else [])])
        for row in type_rows:
            tloop.add_row(row)
    write_sites(block, columns, rows, aniso)
    # The magnetic half, when the phase carries one: the operator and centring
    # loops, the BNS/OG metadata and the moments with their esds
    # (``crystallography.magcif``).  Not the parent k: a supercell phase is
    # written as a k = 0 structure in its own cell, and
    # ``MagneticSymmetry.propagation_vector_parent`` does not survive the file
    # (``test_a_magnetic_supercell_phase_round_trips_in_its_own_cell``).
    magcif.write_magnetic_block(block, phase, magnitude_esds=moment_magnitude_esds)


def structure_document(structure, *, created: str | None = None) -> gemmi.cif.Document:
    """One block per phase, each named uniquely (:func:`block_name`)."""
    doc = gemmi.cif.Document()
    taken: set[str] = set()
    for i, phase in enumerate(structure.phases):
        write_structure_block(doc.add_new_block(block_name(phase.name, i, taken)),
                              phase, created=created)
    return doc


def write_document(doc: gemmi.cif.Document, path) -> None:
    """Write ``doc`` with the CIF 1.1 magic line first (Hall, Allen & Brown 1991)."""
    import os
    from pathlib import Path

    Path(os.fspath(path)).write_text(f"{MAGIC}\n{doc.as_string()}", encoding="utf-8")
