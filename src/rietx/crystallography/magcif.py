"""magCIF: the magnetic half of a CIF, read and written (WP-1328).

**What this module is for.** A magnetic structure reaches a user as a magCIF —
MAGNDATA, ISODISTORT, k-SUBGROUPSMAG and Bilbao's mcif2vesta all emit one — and
:mod:`rietx.schemas.structure` stores exactly what such a file states: the
operator list with its time-reversal signs, the (anti)centrings, and the
moments in crystal-axis components (WP-1327).  So the reader is a translation
and not an interpretation, and this module is the vocabulary that translation
speaks.  It sits beside :mod:`.cif` rather than inside it because the magnetic
tag set is its own dictionary — the COMCIFS ``magnetic_dic`` (``cif_mag.dic``,
tags checked against the 2026-06-03 revision) — and because "which tags does
rietx know?" has to be answerable as a *list* (:data:`READ_TAGS`,
:data:`IGNORED_TAGS`, :data:`WRITTEN_TAGS`, :data:`REFUSED_TAGS`), not as
whatever the code happens to branch on.  That is `io/CLAUDE.md`'s report-or-refuse rule applied to a
dictionary: a magnetic item this reader has no model for is **named**, never
dropped.

**The three tag spellings.**  ``cif_mag.dic`` defines each item twice — the DDLm
``_definition.id`` (``_atom_site_moment.crystalaxis_x``) and the DDL1
``_alias.definition_id`` (``_atom_site_moment_crystalaxis_x``) — and producers
disagree: MAGNDATA writes the dotted form, older tools the flat one.  Both are
read; the dotted form is written, because it is the dictionary's own
``_definition.id`` and what every current producer emits.

**What is *not* in ``cif_mag.dic``.**  Two quantities the model needs have no
magnetic-dictionary item at all: the **ion** whose form factor the moment
scatters with (``Cr3+`` — ``_atom_site_type_symbol`` states the *nuclear*
species and MAGNDATA writes a bare ``Cr``) and the **Landé g** a 4f moment
needs.  They are written under the ``_rietx_atom_site_moment.`` category —
declared here in :data:`PRIVATE_TAGS`, namespaced so no dictionary can collide
with them, and named in the round-trip test — because the alternative is a
round trip that silently loses which form factor was refined against.

References
----------
- COMCIFS ``magnetic_dic`` — github.com/COMCIFS/magnetic_dic, ``cif_mag.dic``:
  the definitions of every ``_atom_site_moment``, ``_space_group_symop_magn``
  and ``_space_group_magn`` item quoted below.
- González-Platas, Katcho & Rodríguez-Carvajal (2021), *J. Appl. Cryst.* **54**,
  338 — "Extension of Hall symbols of crystallographic space groups to magnetic
  space groups": the magnetic-group notation.
- Perez-Mato, Gallego, Tasci, Elcoro, de la Flor & Aroyo (2015),
  *Annu. Rev. Mater. Res.* **45**, 217 — the BNS/OG settings and the
  parent-to-magnetic-cell transform these tags carry.
"""

from __future__ import annotations

import math
import re

import numpy as np

from ..schemas.common import Diagnostic, Parameter
from ..schemas.structure import Moment

# ---------------------------------------------------------------------------
# the tag vocabulary
# ---------------------------------------------------------------------------

#: The magnetic items this reader takes into the model, as their
#: ``cif_mag.dic`` ``_definition.id``.  The flat DDL1 alias of each is read too
#: (:func:`_flat`), and every one of these is *also* the writer's vocabulary
#: except where noted in :data:`WRITTEN_TAGS`.
READ_TAGS: tuple[str, ...] = (
    "_space_group_symop_magn_operation.xyz",
    "_space_group_symop_magn_centering.xyz",
    "_space_group_magn.number_BNS",
    "_space_group_magn.name_BNS",
    "_space_group_magn.number_OG",
    "_space_group_magn.transform_BNS_Pp_abc",
    "_parent_space_group.name_H-M_alt",
    "_parent_space_group.child_transform_Pp_abc",
    "_parent_propagation_vector.kxkykz",
    "_atom_site_moment.label",
    "_atom_site_moment.crystalaxis_x",
    "_atom_site_moment.crystalaxis_y",
    "_atom_site_moment.crystalaxis_z",
    "_atom_site_moment.crystalaxis_x_su",
    "_atom_site_moment.crystalaxis_y_su",
    "_atom_site_moment.crystalaxis_z_su",
    "_atom_site_moment.Cartn_x",
    "_atom_site_moment.Cartn_y",
    "_atom_site_moment.Cartn_z",
    "_atom_site_moment.spherical_modulus",
    "_atom_site_moment.spherical_polar",
    "_atom_site_moment.spherical_azimuthal",
    "_atom_site_moment.magnitude",
    "_atom_site_moment.magnitude_su",
    "_atom_site_moment.symmform",
    "_atom_site_moment.modulation_flag",
)

#: Magnetic items this reader **knows and deliberately does not take**, each
#: with the reason it changes nothing that is built.  Kept apart from
#: :data:`READ_TAGS` so that list's claim — "the reader takes this into the
#: model" — stays true item by item (review of #478, item 3; root
#: ``CLAUDE.md``'s rule that a declared name is a claim), while the vocabulary
#: stays complete: a file carrying one of these has had a stance taken on it,
#: and it is this one.
IGNORED_TAGS: tuple[tuple[str, str], ...] = (
    ("_space_group_magn.name_OG",
     "the OG symbol of the group the operator loops already state; "
     "MagneticSymmetry keeps one symbol, the BNS name, and the OG *number* "
     "is read, so the name has no field and no consumer"),
    ("_parent_space_group.IT_number",
     "a second statement of the parent's type beside name_H-M_alt; the "
     "symbol is only a hint, whose setting is checked against the file's own "
     "operators (resolve_nuclear_symmetry), so a number contradicting it "
     "could change nothing that is built — the operators decide"),
    ("_parent_space_group.transform_Pp_abc",
     "how the parent symbol's reference setting relates to the file's own; "
     "the nuclear group is derived from the file's own operators in the "
     "file's own setting, and whether the cell is a supercell is the child "
     "transform's determinant (refuse_a_magnetic_supercell), never this one's"),
    ("_atom_site_moment.refinement_flags_magnetic",
     "which moment components the producer refined — a plan, not a model "
     "value; what a rietx fit frees is the caller's stage globs, and a "
     "file's flags free nothing"),
)

#: The magnetic items the writer emits.  A subset of :data:`READ_TAGS` — the
#: reader takes the spherical and Cartesian moment forms and the parent-cell
#: block, the writer states the crystal-axis form only, because that is the
#: form :class:`~rietx.schemas.structure.Moment` stores and writing a second
#: spelling of the same vector is two places for a rounding to disagree.
WRITTEN_TAGS: tuple[str, ...] = (
    "_space_group_symop_magn_operation.id",
    "_space_group_symop_magn_operation.xyz",
    "_space_group_symop_magn_centering.id",
    "_space_group_symop_magn_centering.xyz",
    "_space_group_magn.number_BNS",
    "_space_group_magn.name_BNS",
    "_space_group_magn.number_OG",
    "_space_group_magn.transform_BNS_Pp_abc",
    "_atom_site_moment.label",
    "_atom_site_moment.crystalaxis_x",
    "_atom_site_moment.crystalaxis_y",
    "_atom_site_moment.crystalaxis_z",
    "_atom_site_moment.crystalaxis_x_su",
    "_atom_site_moment.crystalaxis_y_su",
    "_atom_site_moment.crystalaxis_z_su",
    "_atom_site_moment.magnitude",
    "_atom_site_moment.magnitude_su",
)

#: The two items the model needs and no magnetic dictionary defines — the
#: form-factor ion and the Landé g.  Namespaced ``_rietx_`` so they cannot
#: collide with a future ``cif_mag.dic`` item, and enumerated here so the
#: round-trip test can assert that these two, and only these two, are the
#: non-dictionary tags this writer emits.
PRIVATE_TAGS: tuple[str, ...] = (
    "_rietx_atom_site_moment.label",
    "_rietx_atom_site_moment.ion",
    "_rietx_atom_site_moment.g",
)

#: Magnetic constructs this model has no shape for, each refused **by name**
#: when a file states it.  Every one describes a *modulated* structure — a
#: moment whose magnitude or direction varies from cell to cell — which is a
#: (3+d)-dimensional model and outside every rung of this track (WP-1328
#: non-goals; WP-1326's incommensurate fence).  Matched as tag **prefixes**, so
#: ``_atom_site_moment_Fourier_param.modulus`` is caught by its category.
REFUSED_TAGS: tuple[tuple[str, str], ...] = (
    ("_cell_wave_vector",
     "a modulation wave vector of the cell"),
    ("_atom_site_Fourier_wave_vector",
     "a modulation wave vector the site amplitudes are indexed by"),
    ("_atom_site_moment_Fourier",
     "the moment as Fourier amplitudes per wave vector"),
    ("_atom_site_moment_special_func",
     "a sawtooth or other special modulation function on the moment"),
    ("_atom_site_displace_Fourier",
     "a displacive modulation of the site"),
    ("_atom_site_displace_special_func",
     "a special displacive modulation function"),
    ("_atom_site_occ_Fourier",
     "an occupational modulation of the site"),
    ("_atom_site_occ_special_func",
     "a special occupational modulation function"),
    ("_atom_site_rot_Fourier",
     "a modulated rigid-body rotation of the site"),
    ("_atom_site_rotation",
     "a rigid-body rotation carried on the site"),
    ("_atom_sites_moment_Fourier",
     "the axes the moment's Fourier amplitudes are stated in"),
    ("_space_group_symop_magn_ssg",
     "a superspace-group operator list"),
    ("_superspace_group",
     "a superspace group"),
)


#: Tag families of the magnetic-CIF draft that ``cif_mag.dic`` replaced (issue
#: #1063, item 3), each refused **by name** when a file states it.  The
#: dictionary defines none of them under any name or alias (0.9.9, whose
#: revision history opens at 0.1.0, 2016-05-24, "Initial automatic conversion
#: from draft magCIF format"), and no source this package holds maps them onto
#: its items, so a file written in them is not read: as an ordinary CIF it
#: finds no atom sites, or reads its nuclear half and drops the moments in
#: silence.  Matched as case-blind tag **prefixes**.  Other ``_magnetic_``
#: spellings (``_magnetic_space_group_standard_setting``,
#: ``_magnetic_propagation_vector_``) are not in this list and refuse nothing:
#: they are written beside the dictionary's own items in files that read.
DRAFT_TAGS: tuple[tuple[str, str], ...] = (
    ("_magnetic_atom_site_", "the sites or their moments"),
    ("_magnetic_cell_", "the cell"),
    ("_magnetic_space_group_symop_operation_", "the magnetic operators"),
)


class MagCifError(ValueError):
    """Raised naming the file, the construct and what would make it readable.

    A separate class from :class:`ValueError` so a caller can tell "this CIF
    states a magnetic structure rietx cannot carry" from "this CIF is broken",
    which are different things to do about.
    """


def _flat(tag: str) -> str:
    """The DDL1 alias of a DDLm ``_definition.id``: the dot becomes ``_``.

    ``cif_mag.dic`` carries both spellings for every item — the dotted one as
    ``_definition.id`` and this one as ``_alias.definition_id`` — and real
    files are written in both, so the reader takes either.
    """
    return tag.replace(".", "_")


# ---------------------------------------------------------------------------
# numbers with standard uncertainties
# ---------------------------------------------------------------------------

#: A CIF number with an optional su.  The mantissa deliberately admits a
#: **trailing point** (``1.``): MAGNDATA writes exactly that for a normalised
#: moment component (entry 0.75's Cr moment is ``0.0 1. 0.0``), and a reader
#: that refused it would refuse the file over its punctuation.
_SU = re.compile(r"^\s*([+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
                 r"(?:\(([0-9]+)\))?\s*$")


def parse_su(text: str) -> tuple[float, float | None]:
    """``"3.7(1)"`` → ``(3.7, 0.1)``; ``"0.00000"`` → ``(0.0, None)``.

    The su in a CIF number is written in units of the **last decimal place of
    the value beside it**, so ``3.7(1)`` is 0.1 and ``0.549(12)`` is 0.012 —
    the digit count of the parenthesis is *not* the exponent.  A value with no
    parenthesis has no su, and that is ``None`` rather than 0.0: a fixed
    parameter and one refined to a vanishing esd are different facts, which is
    the same tri-state :func:`~rietx.crystallography.cif.format_su` writes and
    the FullProf reader's codeword column keeps.

    ``.`` and ``?`` — CIF's inapplicable and unknown — raise, because a moment
    component that is not a number is not a moment component; the caller
    decides what an absent column means.
    """
    m = _SU.match(str(text))
    if m is None:
        raise ValueError(
            f"{text!r} is not a CIF number with an optional standard "
            f"uncertainty (as in '3.7(1)')")
    value = float(m.group(1))
    if m.group(2) is None:
        return value, None
    digits = m.group(1)
    point = digits.find(".")
    decimals = 0 if point < 0 else len(digits) - point - 1
    if "e" in digits or "E" in digits:      # 1.2e-3(4): the su rides the mantissa
        raise ValueError(
            f"{text!r} writes a standard uncertainty on a number in "
            f"exponential notation; the su's place is then ambiguous and this "
            f"reader refuses it rather than pick a decade")
    # su / 10**decimals is one correctly-rounded division, so 3.7(3) reads
    # 0.3 — the double the writer's "0.30000" reads back as; multiplying by
    # 10.0**-decimals rounds twice and lands 1 ulp off
    return value, int(m.group(2)) / 10 ** decimals


# ---------------------------------------------------------------------------
# the propagation-vector loop, which gemmi cannot tokenise
# ---------------------------------------------------------------------------

#: ``_parent_propagation_vector.kxkykz`` is written ``[0 0 0]`` — CIF2 bracket
#: syntax inside a CIF1 file.  gemmi's tokeniser splits it on whitespace into
#: three values, so a two-column loop comes back with ``k1`` / ``[0`` on one row
#: and ``0`` / ``0]`` on the next: the middle component lands in the *id*
#: column and is lost.  So this one item is read off the raw text, and only this
#: one — everything else in a magCIF tokenises correctly.
_KVEC_BLOCK = re.compile(
    r"_parent_propagation_vector[._]kxkykz\b(?P<body>(?:(?!\n\s*(?:loop_|_[A-Za-z]|data_))"
    r"[\s\S])*)")
_BRACKETED = re.compile(r"\[([^\]]*)\]")
_RATIONAL = re.compile(r"^[+-]?\d+(?:/\d+)?$")
#: A decimal that is exactly an integer — ``0.0``, ``1.00``, ``-0.`` — which a
#: producer writing k in floating point uses for a Γ component.  Only an
#: all-zero fraction qualifies: ``0.5`` is a rational *written* as a decimal and
#: ``0.128`` an incommensurate component, and telling those two apart from a
#: decimal is a judgement this reader does not make (review of #478).
_INTEGER_DECIMAL = re.compile(r"^[+-]?\d+\.0*$")


def _integer_component(text: str) -> bool:
    """A k component that is an exact integer, as a rational or a decimal."""
    if _INTEGER_DECIMAL.match(text):
        return True
    return bool(_RATIONAL.match(text)) and eval_rational(text) % 1.0 == 0.0


def propagation_vectors(text: str) -> tuple[tuple[str, str, str], ...]:
    """Every ``_parent_propagation_vector.kxkykz`` in a magCIF's raw text.

    Returned as three exact rational **strings** per vector, because k is
    exact and a float would put a tolerance where none belongs.  The reader
    uses them for one decision only — :func:`refuse_a_magnetic_supercell`
    refuses any k that is not Γ — so a file that reads states k = 0 or none,
    and nothing about k is stored.  A component that is not a rational (``0.128``, the signature of
    an incommensurate k) is returned verbatim, so the caller refuses it by name
    rather than rounding it into a commensurate one.
    """
    out: list[tuple[str, str, str]] = []
    for block in _KVEC_BLOCK.finditer(text):
        for group in _BRACKETED.finditer(block.group("body")):
            parts = group.group(1).replace(",", " ").split()
            if len(parts) == 3:
                out.append((parts[0], parts[1], parts[2]))
    return tuple(out)


def is_commensurate_zero(k: tuple[str, str, str]) -> bool:
    """Whether a k read by :func:`propagation_vectors` is Γ, 0 mod the reciprocal lattice.

    A propagation vector is only ever physically meaningful modulo the
    reciprocal lattice, so an all-integer k such as (1, 1, 1) is Γ
    identically, not a distinct nonzero vector — comparing a component's
    value against literal ``0.0`` (the previous behaviour) wrongly read every
    such file as stating a genuine k ≠ 0 supercell.  A component is read as Γ
    when it is an exact integer — a rational (``1``, ``2/2``) or a decimal
    whose fraction is all zeros (``0.0``, ``1.0``); any non-integer rational
    (including a negative one) is a genuine nonzero component, and any other
    decimal is left to the caller's refusal.
    """
    return all(_integer_component(c) for c in k)


def eval_rational(text: str) -> float:
    """``"1/2"`` → 0.5.  Raises on anything that is not an exact rational."""
    if not _RATIONAL.match(text):
        raise ValueError(f"{text!r} is not an exact rational")
    if "/" in text:
        num, den = text.split("/")
        return int(num) / int(den)
    return float(int(text))


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------


def _transform_determinant(value: str | None):
    """|P| for a ``(P, p)`` transform string — the fingerprint of a real
    **supercell**, as opposed to a setting change.

    ``None`` (the tag absent) is the identity transform and its determinant is
    exactly 1 — a file that states nothing has enlarged nothing.  A transform
    that parses is reduced to its determinant only (the origin shift plays no
    part: a shifted origin relabels the same cell's points and cannot make it
    bigger or smaller), returned as an exact :class:`~fractions.Fraction` so
    ``abs(det) == 1`` is checked without a tolerance. A transform that does
    *not* parse returns ``None`` here too, which callers must **not** treat as
    "identity" — the string states *something* this reader could not
    understand, and refusing rather than reading past it is what
    :func:`refuse_a_magnetic_supercell` already does with an unrecognised
    child transform.
    """
    if value is None:
        return 1
    from .magnetic.operators import _rational_determinant, parse_transform

    try:
        p_matrix, _origin = parse_transform(value)
    except ValueError:
        return None
    return _rational_determinant(p_matrix)


def _value(block, tag: str) -> str | None:
    """One item, in either spelling, unquoted; ``None`` for absent, ``.`` or ``?``."""
    import gemmi

    for name in (tag, _flat(tag)):
        raw = block.find_value(name)
        if raw is None:
            continue
        text = gemmi.cif.as_string(raw).strip()
        if text in ("", ".", "?"):
            return None
        return text
    return None


def _column(block, tag: str) -> list[str]:
    """Every value of a looped item, in either spelling, in file order."""
    import gemmi

    for name in (tag, _flat(tag)):
        loop = block.find_loop(name)
        values = list(loop)
        if values:
            return [gemmi.cif.as_string(v).strip() for v in values]
        single = block.find_value(name)
        if single is not None:
            return [gemmi.cif.as_string(single).strip()]
    return []


_MOMENT_OPTIONAL = (
    "crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
    "crystalaxis_x_su", "crystalaxis_y_su", "crystalaxis_z_su",
    "Cartn_x", "Cartn_y", "Cartn_z",
    "spherical_modulus", "spherical_polar", "spherical_azimuthal",
    "magnitude", "magnitude_su",
    "symmform", "refinement_flags_magnetic", "modulation_flag",
)


# The items that state a moment component.  A ``?`` or ``.`` in one of these is
# kept in the row (every other item drops it), so :func:`_components_from_row`
# can tell a component the file wrote as not-a-number from a column the loop
# does not have (#602).
_MOMENT_COMPONENT_ITEMS = (
    "crystalaxis_x", "crystalaxis_y", "crystalaxis_z",
    "Cartn_x", "Cartn_y", "Cartn_z",
    "spherical_modulus", "spherical_polar", "spherical_azimuthal",
)

# CIF's two null values (the CIF 1.1 syntax specification, Hall, Westbrook &
# Brown, *International Tables* Vol. G ch. 2.2; the COMCIFS reference parser
# reads them as distinct "unknown" and "not applicable" kinds).  cif_mag.dic defines no default for any moment
# component, so neither has a value to substitute.
_CIF_NULL_MEANING = {"?": "unknown", ".": "inapplicable"}


def _moment_table(block):
    """The ``_atom_site_moment`` loop as ``[{item: text}]``, either spelling.

    An empty, ``?`` or ``.`` cell is dropped, except in a moment-component
    item (:data:`_MOMENT_COMPONENT_ITEMS`), where ``?``/``.`` is kept as
    written: there it is a statement about a component, which
    :func:`_components_from_row` refuses rather than reads as zero.
    """
    rows: list[dict[str, str]] = []
    for prefix in ("_atom_site_moment.", "_atom_site_moment_"):
        table = block.find(prefix, ["label"] + [f"?{n}" for n in _MOMENT_OPTIONAL])
        if not len(table):
            continue
        names = ["label", *_MOMENT_OPTIONAL]
        for row in table:
            entry: dict[str, str] = {}
            for i, name in enumerate(names):
                if not row.has(i):
                    continue
                # ``row.str`` maps both nulls to "", so read the raw token for them
                raw = row[i].strip()
                text = raw if raw in _CIF_NULL_MEANING else row.str(i).strip()
                if text == "" or (text in _CIF_NULL_MEANING
                                  and name not in _MOMENT_COMPONENT_ITEMS):
                    continue
                entry[name] = text
            rows.append(entry)
        return rows
    return rows


def refuse_modulation(text: str, path: str) -> None:
    """Raise naming every modulation construct the file states.

    The refusal is by **tag**, not by a guess at what the file means: a
    ``_atom_site_moment_Fourier`` loop states a moment that varies from cell to
    cell, and reading its k = 0 amplitude as *the* moment would return a
    collinear structure for an incommensurate one — a structure that looks
    complete, which is the failure the whole coverage discipline exists to
    prevent (WP-1118).
    """
    found = [(tag, what) for tag, what in REFUSED_TAGS
             if re.search(rf"(?m)^\s*{re.escape(tag)}[._]", text)]
    if not found:
        return
    named = "; ".join(f"{tag}* ({what})" for tag, what in found)
    raise MagCifError(
        f"{path} states a modulated magnetic structure: {named}. rietx's "
        f"magnetic model is a single moment per site of one commensurate "
        f"cell (WP-1327), so a Fourier amplitude or a special function has "
        f"nowhere to go, and reading the k = 0 term alone would hand back a "
        f"collinear structure for a modulated one. What would be needed is a "
        f"(3+d)-dimensional moment model; nothing in this package has one, and "
        f"the incommensurate fence is stated in the manual's interchange "
        f"chapter.")


def refuse_draft_tags(text: str, path: str) -> None:
    """Raise naming every :data:`DRAFT_TAGS` tag the file states.

    A refusal and not a read: mapping the draft's items onto the dictionary's
    needs a source for what each meant, and this package has none.  Run before
    the reader decides whether the file has atom sites at all, because a file
    written wholly in these tags has none under the dictionary's names and was
    refused as "no atom sites found", which names the wrong cause.
    """
    found = sorted({match.group(1) for tag, _what in DRAFT_TAGS
                    for match in re.finditer(
                        rf"(?mi)^\s*({re.escape(tag)}[A-Za-z0-9_.\-]*)", text)})
    if not found:
        return
    families = "; ".join(f"{tag}* ({what})" for tag, what in DRAFT_TAGS
                         if any(t.lower().startswith(tag) for t in found))
    shown = ", ".join(found[:4]) + (f" and {len(found) - 4} more"
                                    if len(found) > 4 else "")
    raise MagCifError(
        f"{path} uses the pre-2016 draft magnetic-CIF tags: {shown}. "
        f"cif_mag.dic, which replaced that draft in 2016, defines none of "
        f"{families} under any name or alias, and this reader has no source "
        f"mapping them onto its items, so the file is refused rather than read "
        f"without its magnetic structure. Re-export it with the dictionary's "
        f"tags: _space_group_symop_magn_operation.xyz, the _atom_site_moment "
        f"loop, and the ordinary _cell_ and _atom_site_ items.")


def read_magnetic_symmetry(block, text: str, path: str, *,
                           diagnostics: list[Diagnostic] | None = None):
    """The magnetic space group a magCIF block states, or ``None``.

    Returns a :class:`~rietx.schemas.structure.MagneticSymmetry` built from
    ``_space_group_symop_magn_operation.xyz`` and
    ``_space_group_symop_magn_centering.xyz`` **verbatim** — the strings are
    stored as the file wrote them, which is what makes a write/read round trip
    bit-identical rather than merely equivalent — with the BNS/OG numbers and
    names and the ``transform_BNS_Pp_abc`` string carried as the metadata they
    are.  The parent k is not stored: a file that reaches here states k = 0 or
    none (:func:`refuse_a_magnetic_supercell` refuses every other k first).

    ``uni_number`` is *derived* rather than read: no magCIF states one and
    MAGNDATA does not either, but it is a deterministic function of the
    operator list through spglib
    (:func:`~rietx.crystallography.magnetic.operators.identify`), so filling it
    here makes the field the same on both sides of a round trip.  A group
    spglib cannot match to itself — there are three in its 2.7.0 database —
    leaves it ``None`` on both sides, which round-trips too.

    A file with no ``_space_group_symop_magn_centering`` loop is read as the
    trivial centring ``x,y,z,+1`` and ``CIF_MAGNETIC_CENTERING_ASSUMED`` says
    so: MAGNDATA always writes the loop, so this is a hand-written file, and a
    forgotten anti-centring (``x,y,z+1/2,-1``) would otherwise be a different
    magnetic group read in silence (review of #478, follow-up).
    """
    from ..schemas.structure import MagneticSymmetry
    from .magnetic.operators import MagneticGroup, identify

    operations = _column(block, "_space_group_symop_magn_operation.xyz")
    if not operations:
        return None
    centerings = _column(block, "_space_group_symop_magn_centering.xyz")
    if not centerings:
        # magCIF's centring loop is not optional in practice, but a file that
        # omits it is stating the trivial one rather than nothing: the coset
        # representatives alone are already a group when the lattice is P.
        centerings = ["x,y,z,+1"]
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_CENTERING_ASSUMED",
                where=["phases.0.magnetic_symmetry.centerings"],
                message=(f"{path} states no "
                         f"_space_group_symop_magn_centering.xyz loop, so the "
                         f"magnetic group is its operation list with the "
                         f"trivial centring x,y,z,+1 alone."),
                suggestion=("Add the loop if the group has a centring or an "
                            "anti-centring (for example x,y,z+1/2,-1).")))
    found = None
    try:
        found = identify(MagneticGroup.from_xyz(operations, centerings))
    except (ValueError, KeyError):
        found = None
    bns = _value(block, "_space_group_magn.number_BNS")
    og = _value(block, "_space_group_magn.number_OG")
    symbol = _value(block, "_space_group_magn.name_BNS")
    if found is not None:
        bns, og, symbol = _check_stated_numbers(
            found, bns, og, symbol, path, len(centerings),
            diagnostics=diagnostics)
    return MagneticSymmetry(
        operations=list(operations),
        centerings=list(centerings),
        bns_number=bns,
        og_number=og,
        symbol=symbol,
        setting=_value(block, "_space_group_magn.transform_BNS_Pp_abc"),
        uni_number=None if found is None else found.uni_number,
    )


def _check_stated_numbers(found, bns: str | None, og: str | None,
                          symbol: str | None, path: str, n_centerings: int, *,
                          diagnostics: list[Diagnostic] | None):
    """The BNS/OG numbers and BNS name to store, checked against the operators (#605).

    ``found`` is what :func:`~rietx.crystallography.magnetic.operators.identify`
    makes of the file's own operator list.  A BNS or OG number is a label of
    the group's *type*, the same in every setting, so a stated number that is
    not ``found``'s contradicts the operators beside it.  The operators are the
    model (D-4) and the numbers metadata, so the operators' own numbers are
    stored and ``CIF_MAGNETIC_NUMBER_MISMATCH`` (warning) names both.  The
    stated ``name_BNS`` is kept only while every stated number agrees: no
    dependency here maps a symbol to a group, so a name cannot be checked on
    its own, and one written beside a contradicted number is no more
    trustworthy than the number.  A number the file does not state is left
    unstated, which keeps the stored record what the file said wherever it
    agrees with itself.

    The reader cannot tell which side is wrong.  A mistyped number (136.498
    beside the 136.499 operators) leaves the operators right; a forgotten
    anti-centring in the centring loop leaves the number right and the
    operators a different, smaller group (12.62 stated, 10.46 read).  So the
    message says both, and a group that cannot be named (``identify`` raises)
    is not checked at all.
    """
    stated = {"number_BNS": (bns, found.bns_number),
              "number_OG": (og, found.og_number)}
    wrong = {tag: pair for tag, pair in stated.items()
             if pair[0] is not None and pair[0] != pair[1]}
    if not wrong:
        return bns, og, symbol
    if diagnostics is not None:
        named = "; ".join(f"_space_group_magn.{tag} {s!r} against {d!r}"
                          for tag, (s, d) in wrong.items())
        dropped = (f" and the stated name_BNS {symbol!r} is dropped"
                   if symbol is not None else "")
        diagnostics.append(Diagnostic(
            level="warning", code="CIF_MAGNETIC_NUMBER_MISMATCH",
            where=["phases.0.magnetic_symmetry.bns_number"],
            message=(f"{path} states a magnetic group its own operators are "
                     f"not: {named} (the operators' own, BNS "
                     f"{found.bns_number}, UNI {found.uni_number}). The "
                     f"operators' numbers are stored{dropped}."),
            suggestion=(
                "Check the operator and centring loops against the source "
                f"of the file (this file lists {n_centerings} centring "
                f"translation{'' if n_centerings == 1 else 's'}).")))
    return found.bns_number, found.og_number, None


def refuse_a_magnetic_supercell(block, text: str, path: str) -> None:
    """Raise where the file states its structure in a **supercell** of the parent.

    This is the k ≠ 0 case, and the refusal is a statement about WP-1327's
    model rather than about magCIF.  A supercell file — ``child_transform_Pp_abc
    '2a,b,c;0,0,0'`` with ``_parent_propagation_vector.kxkykz [1/2 0 0]``, the
    generic commensurate k ≠ 0 record — lists the asymmetric unit of the
    *magnetic* group in the *magnetic* cell, and that unit is generally larger
    than the nuclear one: one nuclear orbit splits into two or more magnetic
    sites carrying different moments.  WP-1327 stores **one moment per atom of
    the nuclear asymmetric unit** and propagates it over the site's magnetic
    orbit, so it cannot express two independent moments on one nuclear orbit —
    and building the phase from the magnetic asymmetric unit under a nuclear
    space group would count those atoms twice in |F_N|².

    So the construct is named and refused rather than half-read.  What would be
    needed is stated in the message and in the report: the nuclear space group
    of the supercell (derivable from the magnetic group with ε discarded,
    carried through ``MagneticGroup.transformed``) *and* a moment model that
    admits several moments on one nuclear orbit.  Neither is this rung's.

    **The predicate is about the *child* transform and k, never the parent
    one.**  ``_parent_space_group.transform_Pp_abc`` records how the parent
    symbol's *reference* setting relates to the file's own — a fact about
    which axes and origin the symbol was tabulated at, stated for every
    ordinary MAGNDATA entry in a non-standard setting (e.g. a Pnma structure
    printed as its ``P c m n`` permutation) whether or not the file is a
    supercell of anything.  A |det| = 1 transform there is a setting change,
    read by deriving the nuclear group from the file's own magnetic operators
    rather than from a symbol lookup (:mod:`rietx.crystallography.cif`'s
    :func:`~rietx.crystallography.magcif.resolve_nuclear_symmetry`) — so it is
    no longer this function's business at all.  What *does* make the magnetic
    cell larger than the nuclear one is the **child** transform's determinant:
    an enlargement multiplies the number of lattice points, which is exactly
    what |det| > 1 measures, while a permutation of the child's own axes
    (|det| = 1, non-identity) is a setting choice on the magnetic cell and not
    an enlargement of it.
    """
    child = _value(block, "_parent_space_group.child_transform_Pp_abc")
    kvectors = propagation_vectors(text)
    nonzero = [k for k in kvectors if not is_commensurate_zero(k)]
    child_det = _transform_determinant(child)
    is_supercell_transform = child_det is None or abs(child_det) != 1
    if not is_supercell_transform and not nonzero:
        return
    reason = []
    if is_supercell_transform:
        reason.append(f"_parent_space_group.child_transform_Pp_abc {child!r}")
    if nonzero:
        reason.append("_parent_propagation_vector.kxkykz "
                      + ", ".join("[" + " ".join(k) + "]" for k in nonzero))
    incommensurate = [k for k in nonzero
                      if any(not (_RATIONAL.match(c) or _INTEGER_DECIMAL.match(c))
                             for c in k)]
    fence = (" The k stated here is not a rational, so this is an "
             "incommensurate structure and no commensurate cell exists to read "
             "it in."
             if incommensurate else
             " A commensurate k ≠ 0 structure is stated in its magnetic "
             "supercell, and the asymmetric unit of the magnetic group in that "
             "cell generally splits one nuclear orbit into several sites with "
             "different moments.")
    raise MagCifError(
        f"{path} states its magnetic structure in a cell that is not the "
        f"parent cell: {'; '.join(reason)}.{fence} rietx stores one moment per "
        f"atom of the nuclear asymmetric unit and propagates it over that "
        f"site's magnetic orbit (WP-1327), so this file's moments have nowhere "
        f"to go and building the phase from them would count the nuclear atoms "
        f"more than once. What would be needed: the nuclear space group of the "
        f"supercell and a moment model admitting several moments on one "
        f"nuclear orbit. The file is not misread and it is not dropped — it is "
        f"named here.")


#: The parent symbol's tag as FullProf writes it (issue #1063, item 2).
#: ``cif_mag.dic`` 0.9.9 defines ``_parent_space_group.name_H-M_alt`` and no
#: alias of it, so this spelling is read only where that item is absent, and
#: named when it is.
PARENT_HM_UNDEFINED = "_parent_space_group.name_H-M"


def _same_symbol(one: str, two: str) -> bool:
    """Whether two H-M symbols name one setting: the same text up to spacing,
    or one gemmi entry, looked up as :func:`resolve_nuclear_symmetry` does."""
    from .symmetry import get_spacegroup

    if "".join(one.split()) == "".join(two.split()):
        return True
    try:
        return (get_spacegroup(one.replace("_", "")).hall
                == get_spacegroup(two.replace("_", "")).hall)
    except ValueError:
        return False


def parent_space_group(block, path: str, *,
                       diagnostics: list[Diagnostic] | None = None) -> str | None:
    """The nuclear space-group symbol a magCIF states, or ``None``.

    ``_parent_space_group.name_H-M_alt`` is where a magCIF puts it: the
    magnetic block replaces ``_space_group_name_H-M_alt`` entirely, so
    ``gemmi.read_small_structure`` returns no space group for a MAGNDATA file
    and the ordinary reader's fallback finds nothing.  Only meaningful once
    :func:`refuse_a_magnetic_supercell` has established that the file's cell
    *is* the parent cell.

    FullProf writes the item as :data:`PARENT_HM_UNDEFINED`, which no
    dictionary defines and which can mean nothing else.  Where ``_alt`` is
    absent that tag is read and ``CIF_MAGNETIC_PARENT_TAG_UNDEFINED`` (info)
    names it.  Where both are present and name different settings the file
    contradicts itself, and the reader cannot tell which is wrong, so it
    raises :class:`MagCifError` quoting both.
    """
    stated = _value(block, "_parent_space_group.name_H-M_alt")
    other = _value(block, PARENT_HM_UNDEFINED)
    if other is None:
        return stated
    if stated is None:
        # the tag as the file spells it: gemmi matches tags case-blind
        pairs = (block.find_pair(name)
                 for name in (PARENT_HM_UNDEFINED, _flat(PARENT_HM_UNDEFINED)))
        tag = next(pair[0] for pair in pairs if pair is not None)
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_PARENT_TAG_UNDEFINED",
                where=["phases.0.space_group"],
                message=(f"{path} names its parent space group {other!r} "
                         f"under {tag}, which cif_mag.dic does not define; "
                         f"it was read as _parent_space_group.name_H-M_alt, "
                         f"the item that tag can only mean.")))
        return other
    if not _same_symbol(stated, other):
        raise MagCifError(
            f"{path} names two parent space groups: "
            f"_parent_space_group.name_H-M_alt {stated!r} and "
            f"{PARENT_HM_UNDEFINED} {other!r}. The file contradicts itself and "
            f"the reader cannot tell which is wrong; remove the one that does "
            f"not describe the structure.")
    return stated


def nuclear_operations(magnetic_symmetry) -> tuple[str, ...]:
    """The nuclear (family) group's ``x,y,z`` operators, from the file's own
    magnetic ones with time reversal dropped.

    Every ``_space_group_symop_magn_operation.xyz`` times every
    ``_space_group_symop_magn_centering.xyz`` is one element of the full
    magnetic group (:meth:`~rietx.crystallography.magnetic.operators.
    MagneticGroup.all_operations`); dropping its ε leaves a plain coordinate
    operation.  For the commensurate (k = 0) structures this reader carries, a
    type-I magnetic group's operators already have ε = +1 throughout, and a
    type-III one splits into an ε = +1 unitary half **H** (index 2 in the
    nuclear group **N**) and an ε = −1 coset **N − H** — so dropping ε returns
    every element of H once (as itself) and every element of N − H once (as
    the plain operation the primed one carries): together, and with no
    duplicate and no omission, exactly **N**, the nuclear space group
    (Perez-Mato, Gallego, Tasci, Elcoro, de la Flor & Aroyo 2015, *Annu. Rev.
    Mater. Res.* **45**, 217).

    That is what makes the result the authority on the setting rather than
    only a hint: it is already closed under composition, already contains the
    identity, and — because it is read off the very strings the atoms'
    coordinates and moments are stated against — it is guaranteed to share
    their setting.  A symbol looked up in gemmi's table is not: gemmi's
    canonical operator set for a given Hermann-Mauguin symbol can sit at a
    different origin than a MAGNDATA file's own (measured on Ima2/space group
    46 — the two 8-operator sets disagree pointwise), so building the phase
    from the symbol alone would silently attach the wrong coordinate frame to
    a right-looking name. See :func:`resolve_nuclear_symmetry`, which turns it
    into the tabulated group a phase on this tree can carry.
    """
    from .magnetic.operators import MagneticGroup, MagneticOperator

    group = MagneticGroup.from_xyz(magnetic_symmetry.operations,
                                   magnetic_symmetry.centerings)
    # the file's own order first — operation loop times centring loop, as
    # written — because a tier-3 phase carries this list and a symmetry code
    # indexes it; ``MagneticGroup`` stores its operations canonically sorted,
    # so its closure only fills in anything the loops left implicit
    stated = [MagneticOperator.from_xyz(c) * MagneticOperator.from_xyz(o)
              for o in magnetic_symmetry.operations
              for c in (magnetic_symmetry.centerings or ("x,y,z,+1",))]
    out: list[str] = []
    seen: set[tuple] = set()
    for op in (*stated, *group.all_operations()):
        key = (op.rotation, op.translation)
        if key in seen:
            continue
        seen.add(key)
        out.append(op.xyz().rsplit(",", 1)[0])
    return tuple(out)


def _orbit_size(ops, xyz) -> int:
    """How many distinct positions (mod 1) the operations ``ops`` carry ``xyz`` to."""
    point = np.asarray(xyz, dtype=np.float64)
    images: list[np.ndarray] = []
    for op in ops:
        image = (np.asarray(op.rot, dtype=np.float64) @ point
                 + np.asarray(op.tran, dtype=np.float64)) / op.DEN
        image = image - np.floor(image)
        if not any(np.max(np.abs((image - q) - np.round(image - q))) < 1e-3
                   for q in images):
            images.append(image)
    return len(images)


def _orbit_mismatch(parent_ops, own_ops, sites) -> tuple[str, int, int] | None:
    """The first site whose parent orbit is not its orbit under the file's own group.

    ``sites`` is ``[(label, xyz)]`` as the file lists them.  A magCIF lists
    the asymmetric unit of the **magnetic** group, so the atoms the file
    states are the orbits of its own nuclear group (the magnetic operators
    with time reversal dropped).  Built under the parent instead, a site whose
    parent orbit is larger than that gets atoms the file does not state: either
    the parent orbit's other half is listed as a second site too, and that
    orbit is counted twice in |F_N|², or it is not, and the phase carries atoms
    the file never placed.  Equal multiplicity for every site is exactly the
    condition under which the two builds are the same set of atoms.
    """
    for label, xyz in sites:
        n_parent = _orbit_size(parent_ops, xyz)
        n_own = _orbit_size(own_ops, xyz)
        if n_parent != n_own:
            return label, n_parent, n_own
    return None


#: The values ``structure_from_cif(nuclear_group=...)`` takes: which group a
#: magCIF's atom positions refine under (:func:`resolve_nuclear_symmetry`).
NUCLEAR_GROUP_CHOICES = ("auto", "parent", "file")


def _magnetic_group_phrase(magnetic_symmetry) -> str:
    """How the diagnostics name the group the moments refine under."""
    symbol = getattr(magnetic_symmetry, "symbol", None)
    bns = getattr(magnetic_symmetry, "bns_number", None)
    named = " ".join(part for part in (
        repr(symbol) if symbol else "",
        f"(BNS {bns})" if bns else "") if part)
    return "the file's magnetic group" + (f" {named}" if named else "")


#: The note inside the bracket of a tier-3 label
#: (:func:`~rietx.crystallography.symmetry.unnamed_label`): the same words the
#: ``Phase`` validator suggests for a list no symbol generates in its cell.
UNNAMED_NOTE = "unnamed in this cell"


def _unnamed_nuclear_group(triplets: tuple[str, ...], path: str, why: str):
    """Tier 3: the file's own nuclear operations as an ``OperatorGroup``.

    The label is :func:`~rietx.crystallography.symmetry.unnamed_label` over the
    **type** spglib identifies the list as (Togo, Shinohara & Tanaka 2024,
    *Sci. Technol. Adv. Mater. Meth.* **4**, 2384822), in its standard
    setting's symbol — a statement about the type, never about the setting,
    which is the whole reason for the bracket.  Where spglib names nothing the
    symmorphic closest type stands in (``symmetry._closest_type``), and where
    even that fails the bracket stands alone.  The list is the file's order,
    which is the order a symmetry code indexes.

    **Refused by name where the rotations themselves are in no tabulated
    orientation** — a two-fold along a face diagonal, a hexagonal group on
    rotated axes.  An ``OperatorGroup`` takes its crystal system, monoclinic
    unique axis and so its cell ties from the tabulated group with its point
    group and lattice (``symmetry._closest_type``); with no such group those
    are undefined, and the phase would fail at its first cell tie with an
    error about gemmi's table rather than about this file.  Measured on the
    MAGNDATA mirror: 91 of the 171 files tier 3 was written for, against 74 it
    reads.  Carrying them needs the metric ties derived in the file's own
    orientation, or the file restated in a conventional one.
    ``why`` is the tier-1/2 reason, quoted so the refusal says the whole story.
    """
    import gemmi
    import spglib

    from .symmetry import OperatorGroup, _closest_type, unnamed_label

    symmorphic = _closest_type(tuple(triplets))
    if symmorphic is None:
        raise MagCifError(
            f"{path}: the file's own nuclear group (its magnetic operators "
            f"with time reversal dropped) is in no tabulated setting, and its "
            f"rotations are in an axis orientation no tabulated setting has, "
            f"so the parent cannot be used ({why}) and the group cannot be "
            f"carried as an operation list either: a phase carrying "
            f"Phase.symmetry_operations takes its crystal system and cell "
            f"ties from the tabulated group with the same rotations, and "
            f"there is none. What would make this readable: the file "
            f"restated in a conventional setting of its group.")
    ops = [gemmi.Op(t) for t in triplets]
    rotations = np.array([op.rot for op in ops], dtype="intc") // gemmi.Op.DEN
    translations = np.array([op.tran for op in ops],
                            dtype=np.float64) / gemmi.Op.DEN
    # spglib says "no match" as None or as SpglibError depending on a
    # process-wide flag (magnetic.operators.identification says why)
    try:
        found = spglib.get_spacegroup_type_from_symmetry(rotations, translations)
    except spglib.error.SpglibError:
        found = None
    closest = (symmorphic.hm if found is None
               else gemmi.find_spacegroup_by_number(int(found.number)).hm)
    return OperatorGroup(label=unnamed_label(closest, UNNAMED_NOTE),
                         xyz=tuple(triplets))


def resolve_nuclear_symmetry(hm_symbol: str | None, magnetic_symmetry,
                             path: str, *,
                             sites=(),
                             diagnostics: list[Diagnostic] | None = None,
                             nuclear_group: str = "auto",
                             ):
    """The group a magCIF's nuclear phase is built under.

    A ``gemmi.SpaceGroup`` for tiers 1 and 2, an
    :class:`~rietx.crystallography.symmetry.OperatorGroup` for tier 3; either
    way ``.xhm()`` is what ``Phase.space_group`` takes, and an
    ``OperatorGroup``'s ``.xyz`` is ``Phase.symmetry_operations``.

    ``hm_symbol`` — ``_parent_space_group.name_H-M_alt``, or the undefined
    spelling :func:`parent_space_group` reads where it is absent — names the
    parent type; the **setting** is checked against the file's own operators, never
    taken on trust from the symbol: see :func:`nuclear_operations` for why a
    symbol lookup can silently disagree with the setting the file's
    coordinates and moments are stated in.  ``sites`` is ``[(label, xyz)]``
    from the file's ``_atom_site`` loop.  The rule is the **highest tabulated
    group the file's atoms satisfy** (issue #457), in three tiers tried in
    order, and none of them is silent:

    * **tier 1, the parent**, in the symbol's own tabulated setting, when every
      one of the file's magnetic operators with time reversal dropped is an
      operation of it *and* every site has the same multiplicity under it as
      under the file's own operators (:func:`_orbit_mismatch`).  This is WP-1327's model — a nuclear phase under the parent
      group carrying moments under a magnetic group that may be a subgroup of
      it (Cr₂WO₆'s ``Pn'nm`` in ``P4₂/mnm``) — and it is bit-identical to
      reading the symbol alone.  One ``CIF_MAGNETIC_NUCLEAR_GROUP`` (info)
      names the group the positions refine under, the file's own family
      group, the index between them where it is not 1, and the magnetic group
      the moments refine under — the positions then carry constraints the
      file's own operators do not impose, and that is a choice to be seen;
    * **tier 2, the file's own nuclear group**, when one tabulated setting has
      exactly its operations (the family group of the magnetic group, in the
      setting the file states it): that setting is taken, and one
      ``CIF_MAGNETIC_NUCLEAR_SETTING`` (info) names the substitution and why —
      the same rule ``CIF_SPECIES_NORMALISED`` follows one column over.  This
      is the case of a parent symbol at a different origin or axis choice
      from gemmi's table (measured on Ima2/space group 46), and of a
      symmetry-lowering magnetic group under which some site's orbit is
      smaller than its parent orbit — built under the parent that site would
      gain atoms the file does not state, or, where the file lists the rest of
      the parent orbit as a second site, one orbit counted twice;
    * **tier 3, the file's own nuclear group as its operation list**, when no
      tabulated setting has exactly its operations — an origin or axis choice
      gemmi's table does not hold: the phase carries the list itself
      (``Phase.symmetry_operations``) under a bracketed label naming the
      closest type (:func:`_unnamed_nuclear_group`), and
      ``CIF_MAGNETIC_NUCLEAR_SETTING`` says so.  Every consumer reads the
      operations through ``symmetry.resolve_group``, so nothing downstream
      reads the label as a symbol.  On the MAGNDATA mirror 171 files were
      refused here before this tier; 74 now read under it, and 91 are
      refused by :func:`_unnamed_nuclear_group` for their axis orientation.

    ``nuclear_group`` overrides the choice (one of
    :data:`NUCLEAR_GROUP_CHOICES`): ``"auto"`` is the rule above,
    ``"file"`` skips tier 1 (tier 2, else tier 3), and ``"parent"``
    forces tier 1 and raises :class:`MagCifError` by name where the parent
    cannot carry the file's atoms, rather than falling through.

    ``hm_symbol=None`` is a file that names **no** parent — a TOPAS ``str``
    stating only ``mag_space_group``, whose atoms TOPAS generates with the
    magnetic group's own operators. Tier 1 has nothing to try, so it is tier 2
    or tier 3 (``"parent"`` is refused outright), and **no diagnostic is
    appended**: the caller knows why no parent was named and says so on its
    own channel (``TOPAS_MAGNETIC_GROUP_READ``).
    """
    import gemmi

    from .symmetry import get_spacegroup, operator_key

    if nuclear_group not in NUCLEAR_GROUP_CHOICES:
        raise ValueError(
            f"nuclear_group={nuclear_group!r}: expected one of "
            f"{', '.join(map(repr, NUCLEAR_GROUP_CHOICES))}")

    def keys(ops) -> frozenset:
        return frozenset(
            operator_key(np.asarray(op.rot, dtype=np.float64) / op.DEN,
                         np.asarray(op.tran, dtype=np.float64) / op.DEN)
            for op in ops)

    own_triplets = nuclear_operations(magnetic_symmetry)
    if hm_symbol is None:
        derived = keys(gemmi.Op(o) for o in own_triplets)
        if nuclear_group == "parent":
            raise MagCifError(
                f"{path}: nuclear_group='parent' asks for the positions to "
                f"refine under the parent space group, and the file names "
                f"none — only its magnetic group")
        taken = next((other for other in gemmi.spacegroup_table()
                      if keys(other.operations()) == derived), None)
        if taken is None:
            return _unnamed_nuclear_group(
                own_triplets, path, "the file names no parent")
        return taken

    # MAGNDATA writes the IUCr screw-axis subscript with an underscore
    # (``P 2_1/c``), a perfectly standard spelling gemmi's lookup table does
    # not normalise (``find_spacegroup_by_name("P 2_1/c")`` -> ``None``,
    # ``"P 21/c"`` resolves) -- unlike species (normalize_cif_species) and
    # cell angles (_correct_symmetry_angles), which both go through an
    # explicit rietx-owned normaliser before being trusted. The underscore is
    # stripped only for the lookup; ``hm_symbol`` (the file's own spelling)
    # is what every message below still names.
    raw_hm = str(hm_symbol).strip("'\"")
    try:
        sg = get_spacegroup(raw_hm.replace("_", ""))
    except ValueError as exc:
        raise ValueError(f"unrecognised space group {hm_symbol!r} in {path}") from exc
    own_ops = [gemmi.Op(o) for o in own_triplets]
    derived = keys(own_ops)
    parent_keys = keys(sg.operations())
    contained = derived <= parent_keys
    mismatch = (_orbit_mismatch(list(sg.operations()), own_ops, list(sites))
                if contained else None)

    def family():
        # scanned only when a message or the fallback needs it: ~560 settings
        return next((other for other in gemmi.spacegroup_table()
                     if keys(other.operations()) == derived), None)

    moments = _magnetic_group_phrase(magnetic_symmetry)
    # "file" asks for the file's own group, which *is* the parent when the two
    # are the same operations (a type-III group's family group is its parent)
    if contained and mismatch is None and (nuclear_group != "file"
                                           or derived == parent_keys):
        if diagnostics is not None:
            index = len(parent_keys) // len(derived)
            taken = family() if index != 1 else sg
            if taken is None:
                relation = (f"index {index} over the file's own group, which "
                            f"no tabulated setting names")
            elif keys(taken.operations()) == parent_keys:
                relation = "the file's own group"
            else:
                relation = f"index {index} over the file's own {taken.xhm()!r}"
            diagnostics.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_NUCLEAR_GROUP",
                where=["phases.0.space_group"], value=float(index),
                message=(
                    f"{path}: positions refine under {sg.xhm()!r}, "
                    f"{relation}; moments under {moments}. The parent the "
                    f"file names is {hm_symbol!r}."),
                suggestion=(
                    "Pass nuclear_group='file' to Structure.from_cif to "
                    "refine the positions under the file's own group."
                    if index != 1 else None)))
        return sg
    if mismatch is not None:
        why = (f"site {mismatch[0]!r} has {mismatch[1]} images under "
               f"{sg.xhm()!r} and {mismatch[2]} under the file's own "
               f"operators, so building the phase under the parent would "
               f"place atoms the file does not state or count one orbit twice")
    elif not contained:
        why = (f"the file's operators are not all operations of gemmi's "
               f"tabulated setting {sg.xhm()!r}")
    else:
        why = "the caller asked for it (nuclear_group='file')"
    taken = family()
    if nuclear_group == "parent":
        instead = (f"nuclear_group='auto' would have taken the file's own "
                   f"group {taken.xhm()!r}" if taken is not None else
                   "nuclear_group='auto' would have taken the file's own "
                   "group as its operation list, no tabulated setting having "
                   "exactly its operations")
        raise MagCifError(
            f"{path}: nuclear_group='parent' asks for the positions to refine "
            f"under {hm_symbol!r}, and they cannot: {why}. {instead}.")
    if taken is not None:
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_NUCLEAR_SETTING",
                where=["phases.0.space_group"],
                message=(
                    f"{path}: positions refine under {taken.xhm()!r}, the "
                    f"file's own group, instead of the parent "
                    f"{hm_symbol!r} it names, because {why}; moments under "
                    f"{moments}."),
                suggestion=None))
        return taken
    unnamed = _unnamed_nuclear_group(own_triplets, path, why)
    if diagnostics is not None:
        diagnostics.append(Diagnostic(
            level="info", code="CIF_MAGNETIC_NUCLEAR_SETTING",
            where=["phases.0.space_group"],
            message=(
                f"{path}: positions refine under the file's own group, "
                f"carried as its own list of {len(unnamed.xyz)} operations "
                f"under {unnamed.label!r} (no tabulated symbol names this "
                f"setting), instead of the parent {hm_symbol!r} it names, "
                f"because {why}; moments under {moments}."),
            suggestion=(
                "Write this phase to a CIF. A CIF carries the operation "
                "list, and a format that states a group only as a symbol "
                "refuses it.")))
    return unnamed


def _components_from_row(row: dict[str, str], label: str, cell, path: str
                         ) -> tuple[tuple[float, float, float],
                                    tuple[float | None, float | None, float | None],
                                    str]:
    """One row's moment as crystal-axis components + esds, and which form it came in.

    magCIF states a moment three ways and this reader takes all three, because
    a form it did not read would be a moment silently dropped:

    * **crystal axes** — the stored form, taken verbatim;
    * **spherical** — modulus, polar and azimuthal *in the Cartesian frame
      where x ‖ a and z ‖ c\\** (``cif_mag.dic``), which is exactly
      ``adp.cartesian_basis``'s Cholesky frame, so the conversion is
      :func:`~rietx.crystallography.magnetic.operators.moment_from_cartesian`
      of (sinθcosφ, sinθsinφ, cosθ)·|m| and needs no second convention;
    * **Cartesian** — the same frame, converted the same way.

    Standard uncertainties follow the form the moment is taken from.  The
    crystal-axis ones are the components' own.  A Cartesian row's go through
    the conversion, which is **linear**, so the propagation is exact to first
    order and needs no point to linearise at (:func:`_cartesian_esds`).  A
    spherical row's do not: (modulus, polar, azimuth) → components is
    nonlinear and singular on the pole, so they are not propagated, the
    components keep ``stderr=None``, and ``CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED``
    says what was dropped (:func:`magnetic_diagnostics`) — the same stance the
    modulus su takes (review of #478, item 4).

    Where a file states more than one they must agree to
    :data:`MOMENT_FORM_AGREEMENT_MU_B`; disagreement is refused naming the site,
    because choosing one of two contradictory statements of the same vector is
    not a reader's call.
    """
    from .magnetic.operators import moment_from_cartesian, moment_magnitude

    _refuse_null_components(row, label, path)
    row = _stated_items(row)
    forms: dict[str, np.ndarray] = {}
    esds: list[float | None] = [None, None, None]
    raw_component_text: list[str] | None = None
    axes = ("x", "y", "z")
    if any(f"crystalaxis_{a}" in row for a in axes):
        values, su, texts = [], [], []
        for a in axes:
            text = row.get(f"crystalaxis_{a}", "0")
            v, s = parse_su(text)
            explicit = row.get(f"crystalaxis_{a}_su")
            if explicit is not None:
                s2, _ = parse_su(explicit)
                if s is not None and not math.isclose(s, s2, rel_tol=1e-6,
                                                      abs_tol=1e-12):
                    raise MagCifError(
                        f"{path}: site {label!r} states crystalaxis_{a} = "
                        f"{text!r} with an inline standard uncertainty and "
                        f"crystalaxis_{a}_su = {explicit!r} as well, and the "
                        f"two disagree ({s} against {s2}). One of them is the "
                        f"esd of this component and this reader will not "
                        f"choose.")
                s = s2
            values.append(v)
            su.append(s)
            texts.append(text)
        forms["crystal axes"] = np.array(values, dtype=float)
        esds = su
        raw_component_text = texts
    if all(f"spherical_{n}" in row for n in ("modulus", "polar", "azimuthal")):
        modulus, _ = parse_su(row["spherical_modulus"])
        polar, _ = parse_su(row["spherical_polar"])
        azimuth, _ = parse_su(row["spherical_azimuthal"])
        theta, phi = math.radians(polar), math.radians(azimuth)
        cartesian = modulus * np.array([
            math.sin(theta) * math.cos(phi),
            math.sin(theta) * math.sin(phi),
            math.cos(theta)], dtype=float)
        forms["spherical"] = moment_from_cartesian(cartesian, cell)
    if any(f"Cartn_{a}" in row for a in axes):
        parsed = [parse_su(row.get(f"Cartn_{a}", "0")) for a in axes]
        cartesian = np.array([v for v, _s in parsed], dtype=float)
        forms["Cartesian"] = moment_from_cartesian(cartesian, cell)
        if not forms.keys() - {"Cartesian"}:     # the form the moment is taken from
            esds = _cartesian_esds([s for _v, s in parsed], cell)
    if not forms:
        raise MagCifError(
            f"{path}: site {label!r} has a row in the _atom_site_moment loop "
            f"but states no moment in any of the three forms cif_mag.dic "
            f"defines (crystalaxis_*, spherical_*, Cartn_*). A moment row with "
            f"no moment in it is refused rather than read as zero, because a "
            f"zero moment is a claim the file did not make.")
    names = list(forms)
    for other in names[1:]:
        gap = float(np.max(np.abs(forms[names[0]] - forms[other])))
        if gap > MOMENT_FORM_AGREEMENT_MU_B:
            raise MagCifError(
                f"{path}: site {label!r} states its moment in the "
                f"{names[0]} and {other} forms and they disagree by "
                f"{gap:.4g} mu_B per component "
                f"({np.array2string(forms[names[0]], precision=5)} against "
                f"{np.array2string(forms[other], precision=5)}). Both are the "
                f"same vector in cif_mag.dic, so the file contradicts itself "
                f"and this reader will not pick a side.")
    components = forms[names[0]]
    stated = row.get("magnitude")
    if stated is not None:
        magnitude, inline_su = parse_su(stated)
        derived = moment_magnitude(components, cell)
        su_text = row.get("magnitude_su")
        explicit_su = (parse_su(su_text)[0]
                      if su_text not in (None, ".", "?") else None)
        su = inline_su if inline_su is not None else explicit_su
        mag_tolerance = su if su is not None else _last_digit_half(stated)
        # The derived norm is itself only as precise as the components it was
        # computed from: a magnitude quoted to N figures compared against a
        # norm built from *also-rounded* components can disagree by more than
        # half the magnitude's own last digit alone (measured: 7/540 loaded
        # entries this session, e.g. 0.1095's Mn1, components 0.346/0.500/
        # 0.146 -> derived 0.62533 against a stated 0.626, gap 0.00067 past a
        # magnitude-only tolerance of 0.0005). Each component's own
        # imprecision -- its su where stated, else half its own last printed
        # digit -- is propagated through the metric by a numerical gradient
        # of moment_magnitude and summed (an L1, first-order worst-case
        # bound, not an RSS: generous on purpose, since two independent
        # roundings essentially never cancel exactly).
        component_tolerance = 0.0
        if raw_component_text is not None:
            comp_tol = [e if e is not None else _last_digit_half(t)
                       for e, t in zip(esds, raw_component_text)]
            h = 1e-5
            for i in range(3):
                plus, minus = list(components), list(components)
                plus[i] += h
                minus[i] -= h
                grad_i = ((moment_magnitude(plus, cell)
                          - moment_magnitude(minus, cell)) / (2 * h))
                component_tolerance += abs(grad_i * comp_tol[i])
        tolerance = mag_tolerance + component_tolerance
        # a *negative* stated magnitude is a sign convention (antiparallel to
        # the reference direction), not a mismatch against the derived norm,
        # which is never negative -- so both sides are compared as moduli
        gap = abs(abs(magnitude) - derived)
        if gap > tolerance:
            mag_source = "su" if su is not None else "last printed digit"
            component_clause = (
                f", {component_tolerance:.4g} propagated from the "
                f"components' own rounding" if component_tolerance else "")
            raise MagCifError(
                f"{path}: site {label!r} states _atom_site_moment.magnitude = "
                f"{magnitude:.5g} mu_B while its components give "
                f"{derived:.5g} mu_B under the crystal-axis metric "
                f"|m| = sqrt(m.G.m) that cif_mag.dic defines. The gap is "
                f"{gap:.4g} mu_B, past this file's own stated precision "
                f"({tolerance:.4g} mu_B: {mag_tolerance:.4g} from the "
                f"magnitude's own {mag_source}{component_clause}); "
                f"on an oblique cell the Euclidean norm sqrt(sum m_i^2) is "
                f"*not* the magnitude and quoting it here is the commonest "
                f"way this line goes wrong.")
    return (tuple(float(c) for c in components), tuple(esds), names[0])


def _cartesian_esds(sus, cell) -> list[float | None]:
    """Cartesian component esds → crystal-axis component esds, through the
    linear map :func:`~.magnetic.operators.moment_from_cartesian` applies.

    m_axes = J·m_cart with J the inverse of the crystal-axis-to-Cartesian
    matrix, so σ_i² = Σ_j J_ij²·σ_j² — the diagonal propagation, because a CIF
    row states each component's su and no correlation between them.  A
    crystal-axis component is given an esd only where every Cartesian
    component it draws on has one: a component with no parenthesis states no
    esd (as on the crystal-axis form), and treating it as exact would put a
    known-exactly claim into the sum.
    """
    from .magnetic.operators import moment_from_cartesian

    if all(s is None for s in sus):
        return [None, None, None]
    jac = np.column_stack([moment_from_cartesian(np.eye(3)[j], cell)
                           for j in range(3)])
    out: list[float | None] = []
    for i in range(3):
        reach = [j for j in range(3) if abs(jac[i, j]) > 1e-12]
        if any(sus[j] is None for j in reach):
            out.append(None)
            continue
        out.append(float(math.sqrt(sum((jac[i, j] * sus[j]) ** 2
                                       for j in reach))))
    return out


def _stated_items(row: dict[str, str]) -> dict[str, str]:
    """``row`` without its ``?``/``.`` component cells (:func:`_moment_table`)."""
    return {k: v for k, v in row.items() if v not in _CIF_NULL_MEANING}


_MOMENT_FORMS = (
    ("crystal-axis", ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z")),
    ("Cartesian", ("Cartn_x", "Cartn_y", "Cartn_z")),
    ("spherical", ("spherical_modulus", "spherical_polar",
                   "spherical_azimuthal")),
)


def _refuse_null_components(row: dict[str, str], label: str, path: str) -> None:
    """Raise where a row states a moment form with a ``?``/``.`` component (#602).

    A form whose cells are *all* ``?``/``.`` is a form this row does not use —
    a loop that carries both crystal-axis and Cartesian columns fills the one a
    row does not state with ``.`` — and is skipped, as an absent column is.  A
    form with a number in one cell and ``?`` or ``.`` in another is a moment
    with a component the file says it does not know (``?``) or that has no
    value (``.``).  Neither is zero, and a ``Moment`` has no unknown component
    to carry it in, so the row is refused by site and item.  A component that
    is zero by symmetry is written ``0`` in a magCIF, as MAGNDATA does.
    """
    for form, items in _MOMENT_FORMS:
        nulls = [(i, row[i]) for i in items if row.get(i) in _CIF_NULL_MEANING]
        numbers = [i for i in items
                   if i in row and row[i] not in _CIF_NULL_MEANING]
        if not nulls or not numbers:
            continue
        named = ", ".join(f"_atom_site_moment.{i} = {v!r} "
                          f"({_CIF_NULL_MEANING[v]})" for i, v in nulls)
        raise MagCifError(
            f"{path}: site {label!r} states its moment in the {form} form "
            f"with {named}. In CIF '?' means the value is unknown and '.' that "
            f"it is inapplicable; neither is 0 mu_B, and cif_mag.dic gives a "
            f"moment component no default to fall back on. rietx stores a "
            f"moment as three numbers and has no unknown component to carry "
            f"this in, so the row is refused rather than read with that "
            f"component set to zero. Write the number, or 0 where the "
            f"component is zero by symmetry.")


def _spherical_su_dropped(row: dict[str, str]) -> list[str]:
    """The spherical items of a row whose su is not carried: every one with an
    inline su, where the spherical form is the one the moment was taken from
    (no crystal-axis item in the row; the spherical form outranks a Cartesian
    one in :func:`_components_from_row`)."""
    row = _stated_items(row)
    if any(f"crystalaxis_{a}" in row for a in ("x", "y", "z")):
        return []
    names = ("modulus", "polar", "azimuthal")
    if not all(f"spherical_{n}" in row for n in names):
        return []
    return [f"spherical_{n} = {row[f'spherical_{n}']}" for n in names
            if parse_su(row[f"spherical_{n}"])[1] is not None]


def _last_digit_half(text: str) -> float:
    """Half the value of the last printed decimal place of a plain CIF number.

    D5: a magnitude stated to fewer significant figures than its components
    imply (``magnitude = 4`` against components giving 4.0497) is not a
    contradiction, just an imprecise rounding -- the file cannot state more
    than it committed to in print.  This is the same "how many figures did
    the file actually commit to" question :func:`~.cif.format_su` answers for
    writing, read here for the opposite direction: a bare number with no su
    at all still bounds how far its own rounding can be from the truth.
    """
    m = _SU.match(str(text))
    if m is None:
        raise ValueError(
            f"{text!r} is not a CIF number with an optional standard "
            f"uncertainty (as in '3.7(1)')")
    digits = m.group(1)
    if "e" in digits or "E" in digits:
        return 0.0  # exponential notation states its own full precision
    point = digits.find(".")
    decimals = 0 if point < 0 else len(digits) - point - 1
    return 0.5 * 10.0 ** (-decimals)


#: How far two statements of the same moment may differ before the file is
#: refused as self-contradictory (μ_B per crystal-axis component).  Sized by
#: what a file *writes*, not by floating point: magCIF moments are quoted to
#: five decimals at best and MAGNDATA rounds the spherical form to two, so a
#: genuine round-off gap is ~1e-3 μ_B while a real contradiction — a moment
#: stated along **a** in one form and along **b** in the other — is order the
#: moment itself.  Two orders of margin sit between them.
MOMENT_FORM_AGREEMENT_MU_B = 0.02


def moment_within_print(moment, row: dict[str, str], basis
                        ) -> tuple[tuple[float, float, float], float] | None:
    """The stated moment on its site's allowed subspace, where the print admits it.

    A file prints each crystal-axis component to some number of decimals, so
    the true moment lies anywhere in the box of half a unit in the last
    printed place around the printed one (:func:`_last_digit_half`).  A
    moment the operators constrain — m_y = 2·m_x on a site whose stabiliser
    holds a two-fold along [1 2 0] — printed as 2.045, 4.089 is that box
    around a point of the allowed line (2.0445, 4.089), and refusing it says
    the file and its group disagree when they do not.

    A bare ``0`` has a half-width of 0.5 μ_B, which would let a component the
    file states as zero move by half a magnetic moment, so the box is also
    capped: no component moves by more than
    :data:`MOMENT_FORM_AGREEMENT_MU_B`, the size of a gap this module already
    reads as round-off rather than contradiction.  Past it the file and its
    group disagree and the refusal stands.

    Returns ``(components, largest shift)`` for the point of the allowed
    subspace nearest the printed moment in the box's own units (a Chebyshev
    fit, solved exactly as a linear programme), or ``None`` where nothing is
    to be moved — the moment already lies in the subspace, the row states no
    crystal-axis components (a spherical or Cartesian row's precision is not
    a box on these components), or no point of the subspace lies inside the
    box and the cap, which leaves the refusal to the phase's own check
    (:class:`~rietx.schemas.structure.Phase`, rule 2) exactly as before.
    """
    from scipy.optimize import linprog

    from .magnetic.operators import in_span

    m = np.asarray(moment.values(), dtype=np.float64)
    b = np.asarray(basis, dtype=np.float64).reshape(-1, 3)
    if in_span(b, m):
        return None
    row = _stated_items(row)
    if not all(f"crystalaxis_{a}" in row for a in ("x", "y", "z")):
        return None
    half = np.array([_last_digit_half(row[f"crystalaxis_{a}"])
                     for a in ("x", "y", "z")])
    if np.any(half <= 0.0):
        return None
    k = len(b)
    if k == 0:
        target = np.zeros(3)
        ratio = float(np.max(np.abs(m) / half))
        if float(np.max(np.abs(m))) > MOMENT_FORM_AGREEMENT_MU_B:
            return None
    else:
        # minimise t subject to |(Bᵀc − m)_i| <= t·half_i and <= the cap
        cap = MOMENT_FORM_AGREEMENT_MU_B
        a_ub = np.vstack([np.hstack([b.T, -half[:, None]]),
                          np.hstack([-b.T, -half[:, None]]),
                          np.hstack([b.T, np.zeros((3, 1))]),
                          np.hstack([-b.T, np.zeros((3, 1))])])
        b_ub = np.concatenate([m, -m, m + cap, cap - m])
        cost = np.zeros(k + 1)
        cost[-1] = 1.0
        fit = linprog(cost, A_ub=a_ub, b_ub=b_ub,
                      bounds=[(None, None)] * k + [(0.0, None)],
                      method="highs")
        if not fit.success:
            return None
        target = b.T @ fit.x[:k]
        ratio = float(fit.x[-1])
    if ratio > 1.0 + 1e-9:
        return None
    return (tuple(float(v) for v in target),
            float(np.max(np.abs(target - m))))


def read_moments(block, cell, path: str, *,
                 ions: dict[str, str] | None = None,
                 g_factors: dict[str, float] | None = None,
                 ) -> dict[str, tuple[Moment, dict[str, str]]]:
    """Every ``_atom_site_moment`` row, keyed by ``_atom_site_moment.label``.

    Returns the built :class:`~rietx.schemas.structure.Moment` beside the raw
    row, so the caller can report what the row said and this module does not
    have to own the diagnostics channel.  ``ions`` and ``g_factors`` are the
    caller's per-label statements of the two quantities no magnetic dictionary
    carries; where ``ions`` says nothing the site's own type symbol is used and
    the caller reports it.
    """
    out: dict[str, tuple[Moment, dict[str, str]]] = {}
    for row in _moment_table(block):
        label = row["label"]
        if row.get("modulation_flag", "no").lower() in ("y", "yes"):
            raise MagCifError(
                f"{path}: site {label!r} carries "
                f"_atom_site_moment.modulation_flag = "
                f"{row['modulation_flag']!r}, which states that this moment is "
                f"modulated. Its amplitudes live in an "
                f"_atom_site_moment_Fourier loop rietx has no model for; the "
                f"stated components are the average moment, not the moment, "
                f"and reading them would return a collinear structure for a "
                f"modulated one.")
        if label in out:
            raise MagCifError(
                f"{path}: the _atom_site_moment loop has two rows for site "
                f"{label!r}. Two moments on one site is a magnetic supercell "
                f"stated in the parent cell, which rietx does not carry — one "
                f"moment per site of the asymmetric unit is the model.")
        components, esds, _form = _components_from_row(row, label, cell, path)
        ion = (ions or {}).get(label)
        moment = Moment(
            crystalaxis_x=Parameter(value=components[0], stderr=esds[0],
                                    unit="mu_B"),
            crystalaxis_y=Parameter(value=components[1], stderr=esds[1],
                                    unit="mu_B"),
            crystalaxis_z=Parameter(value=components[2], stderr=esds[2],
                                    unit="mu_B"),
            ion=ion or "",                      # filled by the caller from the site
            g=(g_factors or {}).get(label),
        )
        out[label] = (moment, row)
    return out


def symmform_rank(symmform: str) -> int | None:
    """How many free parameters an ``_atom_site_moment.symmform`` states.

    ``"mx,my,0"`` → 2, ``"mx,mx,0"`` → 1, ``"0,0,mz"`` → 1.  Returns ``None``
    for a form this cannot read rather than a guess, because the number is used
    only as a *cross-check* against the subspace M-5 derives from the operators
    (which is authoritative — the operators are the model, ``planning`` D-4) and
    a cross-check that invents a number is worse than none.

    Counting the distinct symbols is deliberately a **dimension** test, which
    root ``CLAUDE.md`` warns is the weak form of a span test.  It is the right
    one here for a reason that does not apply there: the two sides come from
    *independent* sources — the file's producer and this package's own operator
    algebra — so agreement is evidence about the file, and the moment's own
    membership of the derived span is checked exactly, by the schema, one layer
    up.
    """
    parts = [p.strip() for p in str(symmform).split(",")]
    if len(parts) != 3:
        return None
    symbols: set[str] = set()
    for part in parts:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]*", part):
            symbols.add(token.lower())
        if re.fullmatch(r"[-+0-9./*\s]*", part) is None and not symbols:
            return None
    return len(symbols)


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------

def _moment_number(tag: str, value: float, where: str | None = None) -> str:
    """A moment quantity as the shortest text that reads back as the same double.

    ``repr``, and *not* the ``value(su)`` notation
    :func:`~rietx.crystallography.cif.format_su` uses for every number in a
    rietx CIF that carries its su — this is the one place that convention is
    the wrong one, for a measured reason.  A refined moment's esd is routinely
    0.05-0.9 μ_B (WP-1327: 2.0785 ± 0.0655 on Cr₂WO₆, 0.0666 ± 0.878 on the null arm), so two
    significant figures of su leaves the *value* quoted to one or two decimals
    — ``0.1(9)`` for a modulus of 0.0666.  The dictionary's own ``_su`` items
    carry the uncertainty instead, which is what they are for.

    Nor a fixed number of decimals, which is what this was until it refused its
    own writer's file: the reader tests the moment's membership of the site's
    allowed span at 1e-6 μ_B (:func:`~.magnetic.operators.in_span`, through
    the ``Phase`` validator), and five decimals rounds each component by up to
    5e-6 *independently*, so a moment along a tied direction such as
    ``mx,2mx,0`` stops being on it — (0.1456956, 0.2913912) prints as
    ``0.14570 0.29139``, 4e-6 off the line (measured 2026-09-23 on
    ``MagneticSolution.write_magcifs``' own output).  Loosening the span test
    to the writer's rounding would pass a real disagreement of that size from
    any other file; writing the double exactly keeps the moment the validator
    already accepted, so write → read returns it bit for bit and
    read → write → read is a fixed point from the first read on.  The Landé g
    was fixed the same way.

    Since WP-1319 that is the rule for every number written without an su, so
    this is :func:`rietx.io.cif.numbers.number` with none, refusing a
    non-finite value by ``tag`` and ``where`` (Hall, Allen & Brown 1991).
    """
    from ..io.cif.numbers import number

    return number(tag, value, where=where)


def write_magnetic_block(block, phase, *,
                         magnitude_esds: dict[str, float] | None = None) -> None:
    """Write a phase's magnetic space group and moments into a gemmi CIF block.

    Nothing is written for a phase with no ``magnetic_symmetry``, so every
    existing fixture's bytes are untouched — the one property a writer change
    inside a shared function has to have.

    What is written, and why exactly this:

    * the two operator loops **verbatim** from
      :class:`~rietx.schemas.structure.MagneticSymmetry`, because they are the
      stored form and re-deriving them through the group would canonicalise the
      order and break bit-identity for no gain;
    * the BNS/OG numbers, the BNS name and ``transform_BNS_Pp_abc`` as the
      metadata they are — after checking the numbers against the operators
      (:func:`refuse_contradicting_numbers`), so a file this writes never
      states a group its own loops are not (#605).  **What is not carried:** a
      ``setting`` that is not a (P,p) transform (prose a project saved before
      #610 or a hand-built ``MagneticSymmetry`` holds) is left out of the file,
      because this function has no diagnostics channel to say so; it reads back
      as ``setting=None`` (:func:`_transform_or_none`);
    * one ``_atom_site_moment`` row per site carrying a moment: the crystal-axis
      components and their ``_su`` columns (see :func:`_moment_number` for why
      neither ``value(su)`` nor a fixed number of decimals), and ``magnitude``
      computed **once**, from the components under the cosine metric
      ``cif_mag.dic`` defines, so the file cannot carry a magnitude that
      disagrees with its own components — and computed on the cell **as this
      block prints it** (:func:`_printed_cell`), never on the unrounded cell
      in memory, so the file is consistent for any reader and not only for
      one that knows the cell had more digits;
    * ``magnitude_su`` where ``magnitude_esds`` supplies it — the esd of the
      *modulus*, which is where WP-1327 puts a moment's uncertainty (the
      component ``stderr`` of a refined moment is ``None`` by design, because
      the components are written back from the DOFs and the DOF that carries
      the esd is the modulus).  Keyed by site label;
    * the ion and the Landé g under :data:`PRIVATE_TAGS`, which no magnetic
      dictionary defines and without which a round trip loses which form factor
      the refinement used.
    """
    from ..io.cif.numbers import text
    from .magnetic.operators import moment_magnitude

    magnetic = getattr(phase, "magnetic_symmetry", None)
    if magnetic is None:
        return
    refuse_contradicting_numbers(magnetic, getattr(phase, "name", "?"))
    # every value of this half is formatted before its first is set, so a
    # refused moment leaves no operator loop behind it
    operations = [[str(i), text("_space_group_symop_magn_operation.xyz", xyz)]
                  for i, xyz in enumerate(magnetic.operations, start=1)]
    centerings = [[str(i), text("_space_group_symop_magn_centering.xyz", xyz)]
                  for i, xyz in enumerate(magnetic.centerings, start=1)]
    metadata = [(tag, text(tag, str(value))) for tag, value in (
            ("_space_group_magn.number_BNS", magnetic.bns_number),
            ("_space_group_magn.name_BNS", magnetic.symbol),
            ("_space_group_magn.number_OG", magnetic.og_number),
            ("_space_group_magn.transform_BNS_Pp_abc",
             _transform_or_none(magnetic.setting))) if value]
    sites = [a for a in phase.atoms if a.moment is not None]
    cell6 = _printed_cell(block, phase)
    esds = magnitude_esds or {}
    axes = ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z")
    rows, private = [], []
    for atom in sites:
        m, where = atom.moment, atom.label
        components = [getattr(m, n) for n in axes]
        rows.append(
            [text("_atom_site_moment.label", where)]
            + [_moment_number(f"_atom_site_moment.{n}", p.value, where)
               for n, p in zip(axes, components, strict=True)]
            + [_number_or_dot(p.stderr) for p in components]
            + [_moment_number("_atom_site_moment.magnitude",
                              moment_magnitude(m.values(), cell6), where),
               _number_or_dot(esds.get(atom.label))])
        private.append([
            text("_rietx_atom_site_moment.label", where),
            text("_rietx_atom_site_moment.ion", m.ion, where=where),
            "." if m.g is None
            else _moment_number("_rietx_atom_site_moment.g", m.g, where)])
    loop = block.init_loop("_space_group_symop_magn_operation.", ["id", "xyz"])
    for row in operations:
        loop.add_row(row)
    loop = block.init_loop("_space_group_symop_magn_centering.", ["id", "xyz"])
    for row in centerings:
        loop.add_row(row)
    for tag, value in metadata:
        block.set_pair(tag, value)
    if not sites:
        return
    loop = block.init_loop("_atom_site_moment.", [
        "label", *axes, *(f"{n}_su" for n in axes), "magnitude", "magnitude_su"])
    for row in rows:
        loop.add_row(row)
    loop = block.init_loop("_rietx_atom_site_moment.", ["label", "ion", "g"])
    for row in private:
        loop.add_row(row)


def refuse_contradicting_numbers(magnetic, phase_name: str) -> None:
    """Raise where a ``MagneticSymmetry``'s numbers are not its operators' (#605).

    A BNS, OG or UNI number is a label of the group's type, the same in every
    setting, so it can be checked against
    :func:`~rietx.crystallography.magnetic.operators.identify` of the stored
    operator list.  A phase read from a magCIF already agrees
    (:func:`read_magnetic_symmetry` stores the operators' own numbers), and so
    does one built from a number or by ``magnetic_supercell``; a
    ``MagneticSymmetry`` built by hand with a wrong number is the case left,
    and writing it would put a group into the file that its own loops
    contradict.  The writer will not choose between them, so it refuses naming
    both.  A list spglib cannot name is not checked.
    """
    from .magnetic.operators import identification

    found = identification(magnetic.group()).group_id
    if found is None:
        return
    wrong = [f"{name} {stated!r} (the operators are {derived!r})"
             for name, stated, derived in (
                 ("bns_number", magnetic.bns_number, found.bns_number),
                 ("og_number", magnetic.og_number, found.og_number),
                 ("uni_number", magnetic.uni_number, found.uni_number))
             if stated is not None and stated != derived]
    if wrong:
        raise MagCifError(
            f"phase {phase_name!r}: magnetic_symmetry states "
            f"{'; '.join(wrong)}. A magCIF written from it would carry a "
            f"_space_group_magn number its own operator loops contradict, and "
            f"the operators are what is refined. Correct the number (or set it "
            f"to None), or the operator list if that is what is wrong.")


def _printed_cell(block, phase) -> tuple[float, ...]:
    """The cell as the block states it, which is the cell every reader sees.

    ``write_structure_block`` prints a cell angle to its esd's precision, so a
    refined β = 100.123456789(12) goes out as ``100.1235(12)``.  A magnitude computed on the unrounded angle then
    disagrees with the components on the printed one: 1.8e-6 μ_B on a
    (3.12, 0, 3.12) moment, where a ``repr``-precision magnitude and repr
    components state a precision of 6e-11 μ_B, so the reader refused its own
    writer's file (review of #478, item 1).  Reading the six numbers back off
    the block through gemmi's own number parser — the one
    ``read_small_structure`` uses — makes the magnitude exactly what a reader
    recomputes, with no tolerance widened.  A block with no cell (a caller
    writing the magnetic half alone) falls back on the phase's own.
    """
    import gemmi

    tags = [f"_cell_length_{n}" for n in ("a", "b", "c")] + [
        f"_cell_angle_{n}" for n in ("alpha", "beta", "gamma")]
    values = [block.find_value(t) for t in tags]
    if any(v is None for v in values):
        return phase.cell.lengths_angles()
    return tuple(gemmi.cif.as_number(v) for v in values)


def _number_or_dot(value: float | None) -> str:
    """A moment esd, or CIF's ``.`` for one there is no value of.

    ``.`` is *inapplicable*, which is the right word: a component written back
    from a modulus DOF has no esd of its own (WP-1327), and writing ``0`` there
    would state a moment known exactly.  :func:`rietx.io.cif.numbers.su_or_dot`
    (Hall, Allen & Brown 1991).
    """
    from ..io.cif.numbers import su_or_dot

    return su_or_dot(value)


def _transform_or_none(setting: str | None) -> str | None:
    """``setting`` where it is a ``transform_BNS_Pp_abc`` value, else ``None`` (#610).

    ``cif_mag.dic`` defines the item as the (P,p) carrying the basis and origin
    of the **current** setting to those of the BNS setting, in coreCIF's
    ``transform_Pp_abc`` notation with a semicolon between the two parts
    (``'a,b,c;0,0,0'``).  ``MagneticSymmetry.setting`` held provenance prose
    from two builders before #610 ("BNS standard setting (spglib magnetic
    database, …)", "child cell a,b,2c;0,0,0 of P 4/m m m"), and a stored or
    hand-built phase can still carry it; that is not a value of the item, so
    the tag is omitted rather than written with text no reader can parse.  The
    test is :func:`~rietx.crystallography.magnetic.operators.parse_transform`,
    the same parser the rest of the package reads the item with.
    """
    from .magnetic.operators import parse_transform

    if not setting:
        return None
    try:
        parse_transform(setting)
    except ValueError:
        return None
    return setting


def read_private_moment_items(block) -> tuple[dict[str, str], dict[str, float]]:
    """The ion and g this package writes under :data:`PRIVATE_TAGS`.

    Returns ``(ions, g_factors)`` keyed by site label, both empty for a file
    that does not carry them — which is every magCIF from anywhere else, and
    why the caller must have another way to state an ion.
    """
    ions: dict[str, str] = {}
    g_factors: dict[str, float] = {}
    table = block.find("_rietx_atom_site_moment.", ["label", "?ion", "?g"])
    for row in table:
        label = row.str(0).strip()
        if row.has(1) and row.str(1).strip() not in ("", ".", "?"):
            ions[label] = row.str(1).strip()
        if row.has(2) and row.str(2).strip() not in ("", ".", "?"):
            g_factors[label] = float(row.str(2))
    return ions, g_factors


def magnetic_diagnostics(path: str, moments, magnetic, atoms_by_label,
                         cell, *, assumed_ions: dict[str, tuple[str, str]] | None = None,
                         assumed_g: dict[str, float] | None = None
                         ) -> list[Diagnostic]:
    """What the magnetic read did that the model cannot show on its own.

    Each a fact a caller would otherwise have to reconstruct from the file:

    * ``CIF_MAGNETIC_ION_UNCHARGED`` — the form-factor ion was taken from
      ``_atom_site_type_symbol`` and that symbol states no oxidation state.
      MAGNDATA writes a bare ``Mn`` for a site that is chemically Mn³⁺, and
      ⟨j₀⟩ for the two differs, so the substitution is *reported* rather than
      guessed at in silence — the same rule ``CIF_SPECIES_NORMALISED`` follows
      one column over.
    * ``MAGNETIC_ION_ASSUMED`` — the site's bare element has **no** neutral-atom
      row at all (every lanthanide/actinide this table carries: only ionic
      ⟨jₙ⟩ curves exist for them), so the fallback went one step further, to
      the element's majority oxidation state that is *magnetic*
      (:func:`~.magnetic.form_factor.resolve_assumed_ion`, WP-1327 D1). Fires
      instead of ``CIF_MAGNETIC_ION_UNCHARGED`` for these labels, since this is
      a stronger substitution than the neutral-atom one — ``label`` is in
      ``assumed_ions`` exactly when :func:`.cif.structure_from_cif` used it.
    * ``LANDE_G_ASSUMED`` — the site's ion was itself just assumed
      (``MAGNETIC_ION_ASSUMED`` fired on the same label) and that ion needs an
      explicit Landé g (:func:`~.magnetic.form_factor.needs_explicit_g`), which
      magCIF has no item for either. Its free-ion Hund's-rule
      g_J (:func:`~.magnetic.form_factor.assumed_lande_g`) was used instead of
      refusing on a quantity the file could never have carried — ``label`` is
      in ``assumed_g`` exactly when :func:`.cif.structure_from_cif` used it.
      Never fires for a site whose ion was *stated* (``moment_ions=``): there
      an absent g is unrelated to this default and still refuses, unchanged
      (issue #257 A5).
    * ``CIF_MAGNETIC_SYMMFORM`` — ``_atom_site_moment.symmform`` is a record of
      the producer's own constraint, and rietx derives its constraint from the
      operators instead (D-4).  Where the two disagree in the number of free
      parameters the diagnostic is a **warning**, because that is the file and
      this package's symmetry algebra disagreeing about the same site.
    * ``CIF_MAGNETIC_UNIDENTIFIED`` — the operator list did not resolve to one
      of spglib's 1651 groups, so ``uni_number`` is absent.
    * ``CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED`` and
      ``CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED`` — a standard uncertainty the
      file states and the ``Structure`` does not carry: the modulus su, which
      has no field, and the spherical form's, which a nonlinear conversion
      does not propagate (:func:`_components_from_row`).
    """
    from .magnetic.operators import allowed_moment_basis

    out: list[Diagnostic] = []
    group = magnetic.group()
    assumed_ions = assumed_ions or {}
    assumed_g = assumed_g or {}
    for label, (moment, row) in moments.items():
        atom = atoms_by_label.get(label)
        if atom is None:
            continue
        index = atom[0]
        if label in assumed_ions:
            assumed_ion, reason = assumed_ions[label]
            element = re.match(r"[A-Za-z]{1,2}", assumed_ion).group(0)
            out.append(Diagnostic(
                level="info", code="MAGNETIC_ION_ASSUMED",
                where=[f"phases.0.atoms.{index}.moment.ion"],
                message=(f"{path} states no oxidation state for the magnetic "
                         f"site {label!r}, and this table has no neutral-atom "
                         f"⟨j0⟩ for {element!r}. Its form factor defaulted to "
                         f"{assumed_ion!r} ({reason})."),
                suggestion=(f"Pass moment_ions={{{label!r}: '<ion>'}} to "
                            f"Structure.from_cif to state the ion.")))
            if label in assumed_g:
                g_value = assumed_g[label]
                out.append(Diagnostic(
                    level="info", code="LANDE_G_ASSUMED",
                    where=[f"phases.0.atoms.{index}.moment.g"],
                    value=g_value,
                    message=(f"{path} states no Landé g for the magnetic site "
                             f"{label!r}. The assumed ion {assumed_ion!r} "
                             f"needs one, so its free-ion Hund's-rule "
                             f"g_J = {g_value:g} was used."),
                    suggestion=(f"Pass moment_g={{{label!r}: {g_value:g}}} to "
                                f"Structure.from_cif to state g.")))
        elif re.fullmatch(r"[A-Za-z]{1,2}", moment.ion):
            from .magnetic.form_factor import magnetic_ions

            near = [i for i in magnetic_ions()
                    if i.startswith(moment.ion) and i != moment.ion]
            out.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_ION_UNCHARGED",
                where=[f"phases.0.atoms.{index}.moment.ion"],
                message=(f"{path} states no oxidation state for the magnetic "
                         f"site {label!r}, so its form factor is the neutral "
                         f"atom {moment.ion!r}."),
                suggestion=(f"Pass moment_ions={{{label!r}: '<ion>'}} to "
                            f"state the ion. This table carries "
                            f"{', '.join(near)} for {moment.ion}."
                            if near else
                            "Pass moment_ions= to state the ion.")))
        if row.get("magnitude_su") is not None:
            out.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED",
                where=[f"phases.0.atoms.{index}.moment"],
                value=parse_su(row["magnitude_su"])[0],
                message=(f"{path} states _atom_site_moment.magnitude_su = "
                         f"{row['magnitude_su']} mu_B for site {label!r}. A "
                         f"Structure has nowhere to put it, so it is not "
                         f"carried."),
                suggestion="Read the refined esd from "
                           "FitReport.magnetic[i].magnitude_esd."))
        dropped = _spherical_su_dropped(row)
        if dropped:
            out.append(Diagnostic(
                level="info", code="CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED",
                where=[f"phases.0.atoms.{index}.moment"],
                message=(f"{path} states site {label!r}'s moment in the "
                         f"spherical form only, with standard uncertainties "
                         f"({'; '.join(dropped)}). They are not propagated, "
                         f"so the crystal-axis components carry no esd."),
                suggestion="Restate the row in the crystal-axis or Cartesian "
                           "form, whose su this reader keeps."))
        symmform = row.get("symmform")
        if symmform:
            stated = symmform_rank(symmform)
            xyz = (atom[1].x.value, atom[1].y.value, atom[1].z.value)
            derived = int(allowed_moment_basis(
                group.site_stabilizer(xyz)).shape[0])
            level = "info" if stated in (None, derived) else "warning"
            out.append(Diagnostic(
                level=level, code="CIF_MAGNETIC_SYMMFORM",
                where=[f"phases.0.atoms.{index}.moment"],
                value=None if stated is None else float(stated),
                message=(f"{path} states symmform {symmform!r} for site "
                         f"{label!r} ({'unreadable' if stated is None else stated} "
                         f"free parameter"
                         f"{'' if stated == 1 else 's'}). The subspace derived "
                         f"from this file's own operators has {derived}."),
                suggestion=(None if level == "info" else
                            "Check that the operator loop and the symmform in "
                            "this file describe the same site symmetry.")))
    if magnetic.uni_number is None:
        out.append(Diagnostic(
            level="info", code="CIF_MAGNETIC_UNIDENTIFIED",
            where=["phases.0.magnetic_symmetry.uni_number"],
            message=(f"{path}'s operator list did not resolve to one of the "
                     f"1651 magnetic space groups in spglib's database, so no "
                     f"UNI number is recorded."),
            suggestion=None))
    return out
