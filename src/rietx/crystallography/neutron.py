"""Bound coherent neutron scattering lengths.

The neutron analogue of :mod:`rietx.crystallography.scattering`, and the
difference between them is the whole point: an X-ray form factor f(Q) falls off
with angle because the electron cloud has spatial extent, while a nucleus is a
point scatterer on this scale, so **b is independent of Q**. One number per
species, not a five-Gaussian expansion.

Source: Sears, V. F. (1992). *Neutron News* **3**(3), 26–37; and the same
author's tabulation in *International Tables for Crystallography* Vol. C,
ch. 4.4.4, Table 4.4.4.1 — the crystallographic reference of record, and the
volume this package already relies on for dispersion (§4.2.6), flat-plate
absorption (Table 6.3.3.1) and the Lorentz-polarisation factor (§6.2).

Three properties have no X-ray counterpart and each one breaks an assumption
the X-ray path is entitled to make:

* **b can be negative** — H, Li, Ti, V, Mn among the natural-abundance
  elements. It is a 180° phase shift on scattering, not an error state. |F|²
  stays positive; individual terms in the sum do not, so anything that takes
  ``abs()`` or ``sqrt()`` of a single species' amplitude is wrong here.
* **b depends on isotope, not just element** — b(¹H) = −3.7406 fm against
  b(²H) = +6.671 fm is a sign change. That is why deuteration is routine, and
  why this lookup resolves an isotope to *its own* row rather than to the
  element. It is the opposite of the convention in
  :func:`rietx.crystallography.dispersion.normalize_element`, where an ion
  resolves to its element because f′/f″ is a core-level effect: there, the
  element is the identity; here, the isotope is.
* **The table is thermal** — no energy dependence. For the resonant absorbers
  (Cd, Sm, Eu, Gd, and notably ¹¹³Cd, ¹⁵⁷Gd) b is complex and varies with
  wavelength near a resonance, the neutron analogue of an X-ray edge. At one
  constant wavelength a single thermal value is the right number. A
  time-of-flight bank spans a range of wavelengths and would need b(λ), which
  this table cannot give — recorded here because that is a fence, not an
  oversight.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files

import numpy as np

_DATA_FILE = "b_Sears.dat"

#: Species spellings that mean an isotope rather than an element. Deuterium and
#: tritium have their own long-standing symbols; everything else is written
#: mass-number-first, as the source table does (``"2H"``, ``"7Li"``, ``"157Gd"``).
_ISOTOPE_ALIAS: dict[str, str] = {"D": "2H", "T": "3H"}

#: Resonant absorbers whose b is complex and wavelength-dependent near a
#: resonance. The thermal value in the table is not wrong so much as
#: *incomplete* for these, and silently using it near a resonance is the
#: neutron version of interpolating an X-ray table across an edge. Callers that
#: care are expected to ask; see :func:`is_resonant_absorber`.
#:
#: Natural **Yb** and ``168Yb`` are here on the strength of this table's own
#: numbers rather than an outside claim (issue #113 (a)): ``168Yb`` absorbs
#: 2230 barn against ``176Yb``'s 2.85, a spread of nearly three orders
#: within one element, and absorption that large and that isotope-dependent
#: *is* a nuclear resonance.  ``168Yb`` sits with ``113Cd`` (20600) and the
#: two Gd nuclides rather than with its own element's thermal 34.80.
RESONANT_ABSORBERS: frozenset[str] = frozenset(
    {"Cd", "Sm", "Eu", "Gd", "Yb",
     "113Cd", "149Sm", "151Eu", "155Gd", "157Gd", "168Yb"})

#: Energy (eV) of the **lowest positive-energy resonance** of each nuclide that
#: makes it a resonant absorber, from the resolved-resonance parameters of
#: ENDF/B-VIII.0 (Brown et al. 2018, *Nucl. Data Sheets* **148**, 1; files
#: ``n-048_Cd_113`` to ``n-070_Yb_168``, read from MF2/MT151).  The lowest one
#: is the one that sets how far a thermal wavelength sits from the resonance.
#: ``149Sm`` and ``151Eu`` also carry a bound (negative-energy) level, at
#: -1.127 and -0.0609 eV, which is not a resonance a beam can sit on and is
#: left out.  Checked against Mughabghab, *Atlas of Neutron Resonances*
#: (2006) for ``113Cd`` (0.178 eV), ``149Sm`` (0.0973 eV) and ``168Yb``
#: (0.597 eV).  The copy to hand lacks the ``155Gd`` and ``157Gd`` pages and
#: ``151Eu`` was not located, so those three rest on ENDF alone.
RESONANCE_ENERGY_EV: dict[str, float] = {
    "113Cd": 0.1787, "149Sm": 0.0973, "151Eu": 0.321,
    "155Gd": 0.0268, "157Gd": 0.0314, "168Yb": 0.597}

#: The nuclides that carry each resonant *element's* resonance.  Natural Gd has
#: two (¹⁵⁵Gd and ¹⁵⁷Gd, 14.8 % and 15.6 % of the element), the others one.
_RESONANCE_CARRIERS: dict[str, tuple[str, ...]] = {
    "Cd": ("113Cd",), "Sm": ("149Sm",), "Eu": ("151Eu",),
    "Gd": ("155Gd", "157Gd"), "Yb": ("168Yb",)}

#: λ(Å) = NEUTRON_LAMBDA_EV_ANGSTROM / sqrt(E / eV): h / sqrt(2 m_n E) with
#: CODATA 2018 h, m_n and e.  It gives 1.798 Å at 25.3 meV, the 2200 m/s
#: wavelength of :data:`SIGMA_ABS_REFERENCE_WAVELENGTH`.
NEUTRON_LAMBDA_EV_ANGSTROM = 0.286014


@lru_cache(maxsize=None)
def _load_table() -> dict[str, dict]:
    """Parse ``b_Sears.dat`` once. Keys are exactly the source's symbols."""
    text = (files("rietx.data") / _DATA_FILE).read_text(encoding="utf-8")
    table: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        symbol, *values = parts[:8]
        conc, b_coh, b_inc, xs_coh, xs_inc, xs_scatt, xs_abs = (
            float(v) for v in values)
        table[symbol] = {
            "concentration_pct": conc, "b_coh_fm": b_coh, "b_inc_fm": b_inc,
            "xs_coh_barn": xs_coh, "xs_inc_barn": xs_inc,
            "xs_scatt_barn": xs_scatt, "xs_abs_barn": xs_abs,
        }
    return table


def normalize_species(species: str) -> str:
    """Reduce a species label to the key this table uses.

    An ionic charge is discarded — the nucleus does not care about valence
    electrons, which is exactly why b has no Q dependence — while a **mass
    number is kept**, because it selects a different nucleus and therefore a
    different scatterer. Both charge spellings are accepted, digit-first
    (``"Fe3+"``) and sign-first (``"Fe+3"``, which TOPAS writes).

        >>> normalize_species("Fe3+"), normalize_species("D"), normalize_species("2H")
        ('Fe', '2H', '2H')
    """
    s = re.sub(r"\s+", "", species)
    s = re.sub(r"(\d*[+-]|[+-]\d*)$", "", s)          # drop an ionic charge
    if s in _ISOTOPE_ALIAS:
        return _ISOTOPE_ALIAS[s]
    m = re.fullmatch(r"(\d*)([A-Za-z]{1,2})", s)
    if not m:
        # An element-then-mass label is the one misspelling with a fix to
        # name: an agent wrote 'Li7' for lithium-7 and met only the refusal
        # (issue #661, WP-1532).  Named only where that nuclide is tabulated,
        # so 'O1' or an unsigned charge ('Fe3') gets no invented isotope.
        # Where it is tabulated the same spelling is also a common site
        # label ('H1', 'C13', 'N15', 'O18' in organic structures), so the
        # hint names both readings and never only the isotope (WP-1532
        # review): following an isotope-only hint for a label passed as the
        # species would swap natural N (9.36 fm) for 15N (6.44 fm) silently.
        flipped = re.fullmatch(r"([A-Za-z]{1,2})(\d+)", s)
        element = flipped[1].capitalize() if flipped else None
        nuclide = f"{flipped[2]}{element}" if flipped else None
        hint = (f"; for the isotope write it mass-first, {nuclide}; for the "
                f"natural element (if {s!r} is a site label) write {element}"
                if nuclide in _load_table() else "")
        raise KeyError(f"cannot read a species from {species!r}{hint}")
    mass, element = m.groups()
    return f"{mass}{element.capitalize()}" if mass else element.capitalize()


def b_coh(species: str) -> float:
    """Bound coherent scattering length in **femtometres**, possibly negative.

    An isotope resolves to its own row; a bare element to the natural-abundance
    average. Raises :class:`KeyError` naming the species — a missing species is
    a modelling error the caller must see, never a silently-substituted zero,
    which would delete a whole site from the structure factor without changing
    the shape of anything.

        >>> round(b_coh("Al"), 3), round(b_coh("O"), 3)
        (3.449, 5.803)
        >>> b_coh("V") < 0        # negative is physical, not an error
        True
        >>> b_coh("H") * b_coh("D") < 0   # H and D differ in sign
        True
    """
    key = normalize_species(species)
    table = _load_table()
    row = table.get(key)
    if row is None:
        raise KeyError(
            f"no neutron scattering length tabulated for species {species!r} "
            f"(read as {key!r})")
    value = row["b_coh_fm"]
    if not np.isfinite(value):
        raise KeyError(
            f"neutron scattering length for {species!r} (read as {key!r}) is "
            f"not tabulated in Sears (1992) — the source records it as '---'")
    return value


def properties(species: str) -> dict:
    """Every tabulated column for one species, cross-sections included.

    Provided because the cross-sections answer questions the scattering length
    cannot: ``xs_inc_barn`` is what makes a vanadium can a flat background and
    a hydrogenous sample a hopeless one, and ``xs_abs_barn`` is what makes a
    Cd or Gd sample absorb the beam rather than diffract it.
    """
    key = normalize_species(species)
    row = _load_table().get(key)
    if row is None:
        raise KeyError(f"no neutron data tabulated for species {species!r} "
                       f"(read as {key!r})")
    return dict(row, symbol=key)


def is_resonant_absorber(species: str) -> bool:
    """True where the thermal b in this table is incomplete rather than wrong.

    See :data:`RESONANT_ABSORBERS`. A constant-wavelength refinement may use
    the thermal value; a caller spanning a range of wavelengths may not.
    """
    return normalize_species(species) in RESONANT_ABSORBERS


def resonance_wavelengths(species: str) -> dict[str, tuple[float, float]]:
    """Where a resonant absorber's lowest resonance sits: ``{nuclide: (E_eV, λ_Å)}``.

    The wavelength is the neutron's own, λ = h/√(2 m_n E)
    (:data:`NEUTRON_LAMBDA_EV_ANGSTROM`), so it can be set beside an
    instrument's wavelength.  Energies are :data:`RESONANCE_ENERGY_EV`.  An
    element lists the nuclide or nuclides carrying its resonance, and a species
    that is not a resonant absorber returns ``{}``.

        >>> {k: (v[0], round(v[1], 2)) for k, v in resonance_wavelengths("Gd").items()}
        {'155Gd': (0.0268, 1.75), '157Gd': (0.0314, 1.61)}
    """
    key = normalize_species(species)
    nuclides = _RESONANCE_CARRIERS.get(key, (key,) if key in RESONANCE_ENERGY_EV else ())
    return {n: (RESONANCE_ENERGY_EV[n],
                NEUTRON_LAMBDA_EV_ANGSTROM / RESONANCE_ENERGY_EV[n] ** 0.5)
            for n in nuclides}


#: Wavelength (Å) at which the table's ``xs_abs_barn`` is quoted: neutrons at
#: the conventional thermal velocity of 2200 m/s, the velocity Sears (1992)
#: quotes absorption cross-sections for.  The absorption cross-section of a
#: nucleus far from a resonance follows the **1/v law** — the time the neutron
#: spends near the nucleus — so σ_abs(λ) = σ_abs(1.798 Å) · λ / 1.798:
#: *linear* in λ, where an X-ray µ/ρ rises roughly as λ³ (falls as E⁻³)
#: between edges.
SIGMA_ABS_REFERENCE_WAVELENGTH = 1.798


def total_cross_section_neutron(species: str, wavelength: float) -> float:
    """Total neutron cross-section (barn/atom) of one species at ``wavelength`` (Å).

    σ_tot(λ) = σ_abs · λ / 1.798 + σ_coh + σ_inc, from Sears (1992),
    *Neutron News* **3**(3), 26–37 / *International Tables* C Table 4.4.4.1:
    absorption scaled by the 1/v law from its 2200 m/s value
    (:data:`SIGMA_ABS_REFERENCE_WAVELENGTH`), both scattering cross-sections
    wavelength-independent, since b is a point-nucleus constant.

    Attenuation here means beam **removal**, so both scattering terms count,
    as the X-ray total in :mod:`rietx.crystallography.attenuation` does.  They
    are the *bound* (Sears) values, taken as λ-independent — the free-atom
    cross-section is (A/(A+1))² of the bound one, a quarter for hydrogen — and
    for hydrogen the bound value approximates an effective cross-section that
    in a real solid depends on λ and on the proton's dynamics.  In a
    polycrystal the coherent part is Bragg scattering, whose removal of the
    beam depends on λ against the largest d-spacing, and that dependence is
    not modelled.  For hydrogen the incoherent term dominates everything else
    in the table (80.26 barn), which is why a hydrous specimen X-rays call
    transparent is the one a neutron beam struggles through.

    An isotope resolves to its own row (``"D"`` is ²H, 2.05 barn incoherent
    against ¹H's 80.26), as :func:`b_coh` does.

    Raises :class:`KeyError` naming the species when it is untabulated or a
    needed column reads ``---``, and :class:`ValueError` for a **resonant
    absorber** (:data:`RESONANT_ABSORBERS`): near a nuclear resonance σ_abs
    leaves the 1/v law, so the thermal value scaled by λ is wrong in
    principle rather than imprecise — the neutron twin of an X-ray wavelength
    whose tabulation interval straddles an absorption edge, and refused for
    the same reason.  The lowest resonance energy of each is
    tabulated (:data:`RESONANCE_ENERGY_EV`), but "near" also needs the
    resonance's width and strength, which this package does not carry, so
    the refusal covers **every** listed absorber at every wavelength rather
    than guess which are far enough away.  An explicit ``Geometry.mu_r`` /
    ``mu_t`` is how such a specimen gets its correction.

        >>> round(total_cross_section_neutron("V", 1.798), 4)   # abs + coh + inc
        10.1784
    """
    if not wavelength > 0.0:
        raise ValueError(f"wavelength must be positive, got {wavelength}")
    row = properties(species)
    key = row["symbol"]
    if key in RESONANT_ABSORBERS:
        raise ValueError(
            f"{species!r} (read as {key!r}) is a resonant neutron absorber, "
            f"whose absorption leaves the 1/v law near a nuclear resonance; "
            f"the thermal cross-section scaled to {wavelength:g} A is not an "
            f"estimate there, and how far this wavelength is from the resonance is not "
            f"modelled (resonance_wavelengths gives where it sits)")
    parts = (row["xs_abs_barn"], row["xs_coh_barn"], row["xs_inc_barn"])
    if not all(np.isfinite(v) for v in parts):
        raise KeyError(
            f"neutron cross-sections for {species!r} (read as {key!r}) are "
            f"not all tabulated in Sears (1992) — the source records '---' "
            f"for one of sigma_abs, sigma_coh, sigma_inc")
    sigma_abs, sigma_coh, sigma_inc = parts
    return (sigma_abs * wavelength / SIGMA_ABS_REFERENCE_WAVELENGTH
            + sigma_coh + sigma_inc)


def linear_attenuation_neutron(element_counts: dict[str, float], volume: float,
                               wavelength: float) -> float:
    """Linear attenuation coefficient µ (1/cm) of one crystalline phase, neutrons.

    The neutron twin of
    :func:`rietx.crystallography.attenuation.linear_attenuation`, same
    arguments and same unit, so the packing and geometry half
    (:func:`~rietx.crystallography.attenuation.packed_mu_r`,
    ``packed_mu_t``) is shared unchanged:

        µ [1/cm] = Σ_i n_i · σ_tot,i(λ) [barn] / V [Å³]

    with n_i the occupancy-weighted count of species i per cell and σ_tot from
    :func:`total_cross_section_neutron` (Sears 1992).  1 barn = 10⁻²⁴ cm² and
    1 Å³ = 10⁻²⁴ cm³, so barn/Å³ is exactly 1/cm.

    Raises what :func:`total_cross_section_neutron` raises, for the reasons it
    gives — a caller that must not raise catches both.
    """
    if volume <= 0.0:
        raise ValueError(f"cell volume must be positive, got {volume}")
    sigma = sum(count * total_cross_section_neutron(sym, wavelength)
                for sym, count in element_counts.items())
    return sigma / volume
