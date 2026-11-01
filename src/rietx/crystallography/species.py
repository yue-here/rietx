"""The element and the nuclide a scattering-species string names.

One parser for every caller that reads a species: the composition and the
mass in :mod:`rietx.optimize.qpa`, the covalent radius in
:mod:`rietx.model.geometry`, the colour and radius in
:mod:`rietx.gui.structure3d`, and the tabulated ionic, covalent and metallic
radii in :mod:`rietx.crystallography.radii`.  It needs only gemmi's element table, so it
sits here rather than in ``optimize.qpa``, which the structure viewer would
otherwise import whole (#590 review, before-merge 1).
"""

from __future__ import annotations

import re

import gemmi

_ELEMENT_RE = re.compile(r"^(\d*)([A-Za-z]+)")

#: The two hydrogen nuclides with symbols of their own; every other nuclide is
#: written mass-number-first (``"2H"``, ``"7Li"``, ``"157Gd"``), as the neutron
#: table (:mod:`rietx.crystallography.neutron`) spells them.
_HYDROGEN_NUCLIDE_MASS_NUMBER = {"D": 2, "T": 3}


def _parse_species(species: str) -> tuple[str, int | None]:
    """(element symbol, mass number or ``None``) of a scattering species.

    The element is the leading alphabetic run resolved against gemmi's table,
    trying the two-letter prefix before the one-letter one.  A plain greedy
    two-letter parse mis-reads the valence-labelled species that are legal
    Waasmaier-Kirfel keys — ``"Cval"`` would become the non-element ``"Cv"``;
    here it falls back to ``"C"``, while ``"Siva"`` → ``"Si"`` and ``"Fe3+"``
    → ``"Fe"`` resolve directly.  A leading mass number (``"7Li"``) names a
    nuclide, and so do ``D`` and ``T``, which resolve to hydrogen.
    """
    m = _ELEMENT_RE.match(species.strip())
    if m is None:
        raise ValueError(f"cannot parse an element from species {species!r}")
    digits, letters = m.groups()
    mass_number = int(digits) if digits else None
    for n in (2, 1):
        if len(letters) >= n:
            candidate = letters[:n].capitalize()
            if candidate in _HYDROGEN_NUCLIDE_MASS_NUMBER:
                if mass_number is not None:
                    raise ValueError(f"species {species!r} gives a mass number "
                                     f"to {candidate!r}, which already names one")
                return "H", _HYDROGEN_NUCLIDE_MASS_NUMBER[candidate]
            if gemmi.Element(candidate).atomic_number != 0:
                return candidate, mass_number
    raise ValueError(f"unrecognised element in species {species!r}")


def element_symbol(species: str) -> str:
    """Element symbol from a scattering-species string (``"Fe3+"`` → ``"Fe"``).

    See :func:`_parse_species` for the grammar.  A nuclide resolves to its
    **element** — ``"7Li"`` → ``"Li"``, ``"D"`` and ``"2H"`` → ``"H"`` —
    because every caller of this function asks an element's question: the
    X-ray attenuation (an electron-cloud property the nucleus's mass does not
    change), a covalent radius, a formula.  The two questions whose answer
    depends on the nucleus read the nuclide themselves: the mass
    (:func:`rietx.optimize.qpa.atomic_weight`) and the neutron attenuation,
    which reads :attr:`rietx.optimize.qpa.ZMV.species_counts`.  The ionic
    charge is dropped.
    """
    return _parse_species(species)[0]
