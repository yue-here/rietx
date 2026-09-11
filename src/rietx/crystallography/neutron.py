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
#: 2230.40 barn against ``176Yb``'s 2.85, a spread of nearly three orders
#: within one element, and absorption that large and that isotope-dependent
#: *is* a nuclear resonance.  ``168Yb`` sits with ``113Cd`` (20600) and the
#: two Gd nuclides rather than with its own element's thermal 34.80.
RESONANT_ABSORBERS: frozenset[str] = frozenset(
    {"Cd", "Sm", "Eu", "Gd", "Yb",
     "113Cd", "149Sm", "151Eu", "155Gd", "157Gd", "168Yb"})


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
        raise KeyError(f"cannot read a species from {species!r}")
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
