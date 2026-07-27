"""Anomalous scattering factors f′, f″ from the Cromer-Liberman tabulation.

The atomic scattering factor at a wavelength near an absorption edge is

    f(k, λ) = f₀(k) + f′(λ) + i·f″(λ)

with f₀ the elastic form factor of ``scattering.py``.  f′ and f″ (the real and
imaginary *dispersion corrections*, in electrons) depend on the photon energy
and not on the scattering angle — they are core-level resonance effects, so
they are tabulated per **element** and are essentially independent of valence.
f″ ≥ 0 in this convention.

Values are read from ``f1f2_CromerLiberman.dat``, an energy-trimmed extract of
the ESRF DABAX file of the same name (see ATTRIBUTION.md), generated with
D. T. Cromer's FPRIME program.  The **Kissel & Pratt (1990) high-energy-limit
correction is included** — they showed Cromer-Liberman's relativistic term
(5/3)·E_tot/mc² should carry a coefficient of 1, and the difference reaches
−1.3 e at uranium.  That is verified rather than taken on trust: gemmi computes
Cromer-Liberman with the same correction from an independent code path, and
agrees with this table to 1e-4 e in f′ for every element checked including U.

Cromer-Liberman is chosen for two reasons, neither of which is "best
available".  It is the crystallographic *reference* calculation — what
*International Tables* Vol. C §4.2.6 tabulates and what GSAS-II computes at
runtime — so a disagreement with another Rietveld code is attributable rather
than mysterious, which is this project's cross-code rule applied to a data
table.  And it is redistributable: the Chantler/NIST-FFAST tabulation is
better physics but is NIST Standard Reference Data, the statutory *exception*
to US-Government-works-are-public-domain, and the DABAX copy of it carries an
ESRF-only use restriction.

Its known weaknesses, recorded so they are not rediscovered as bugs:

* **Near an edge it is wrong in principle.** From DABAX's own header, it "does
  not account for the effects of neighboring atoms, which can be critical near
  an absorption edge" — within a few tens of eV the true f″ is the XANES of
  the *compound*, which no atomic table knows.  Hence :data:`NEAR_EDGE_EV` and
  the ``overrides`` escape hatch on the schema block.
* **It produces occasional spurious f′** at the extremes of its range;
  xraylarch, which ships both, recommends Chantler over it wherever the two
  differ.  Between edges in the 3–70 keV powder band the two agree closely,
  which is the regime this package models.

**Edges are not interpolated across.**  f″ falls smoothly with energy between
edges and jumps by nearly an order of magnitude at one (Fe K: 0.47 → 3.95 e
across a single grid interval), so a rise across the bracketing interval means
an edge sits inside it, and the request is refused rather than smeared — the
same policy, detected the same way, as ``attenuation.total_cross_section``.

Reference
---------
Cromer, D. T. & Liberman, D. (1970). *J. Chem. Phys.* **53**, 1891–1898.
Cromer, D. T. & Liberman, D. (1981). *Acta Cryst.* **A37**, 267–268.
Kissel, L. & Pratt, R. H. (1990). *Acta Cryst.* **A46**, 170–175.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

import numpy as np

from .attenuation import _HC_EV_ANGSTROM

_DATA_PACKAGE = "pxrdref.data"
_DATA_FILE = "f1f2_CromerLiberman.dat"

#: Z = 1, 2 are absent from the Cromer-Liberman tabulation.  Hydrogen and
#: helium have no absorption edge anywhere in the X-ray band (the H K edge is
#: 13.6 eV), so their dispersion corrections are ~1e-3 electrons on a form
#: factor of 1-2: exactly zero is a better answer than a refusal, and it lets a
#: hydrous phase (brucite, fluorapatite) refine with dispersion on.
_ZERO_DISPERSION = frozenset({"H", "D", "He"})

#: Within this distance of an absorption edge the *tabulation* is wrong in
#: principle, not merely coarsely sampled: f″ there is the near-edge structure
#: of the compound, which depends on coordination and oxidation state.  Values
#: are still returned (they are the best atomic estimate available) but the
#: caller is expected to warn, and to prefer a measured override.
NEAR_EDGE_EV = 50.0


@lru_cache(maxsize=1)
def _load_table() -> dict[str, np.ndarray]:
    """Parse the DABAX extract into {element: (n, 3) [E_eV, f′, f″]}."""
    text = (resources.files(_DATA_PACKAGE) / _DATA_FILE).read_text()
    table: dict[str, np.ndarray] = {}
    element: str | None = None
    rows: list[list[float]] = []
    for line in text.splitlines():
        if line.startswith("#S"):
            if element is not None and rows:
                table[element] = np.array(rows, dtype=np.float64)
            parts = line.split()
            element = parts[2] if len(parts) >= 3 else None
            rows = []
        elif element is not None and line.strip() and not line.startswith("#"):
            rows.append([float(v) for v in line.split()])
    if element is not None and rows:
        table[element] = np.array(rows, dtype=np.float64)
    if not table:
        raise RuntimeError("failed to parse the Cromer-Liberman f′/f″ table")
    return table


def normalize_element(species: str) -> str:
    """Strip an ionic charge from a species label: ``"Zn2+"`` → ``"Zn"``.

    Deliberately *not* ``scattering.normalize_species``, which keeps the ion
    when an ionic f₀ is tabulated.  f′/f″ come from core levels that the
    valence electrons barely perturb, so every tabulation is per element; the
    asymmetry between the two lookups is physical, not an oversight.
    """
    s = species.strip()
    m = re.match(r"^([A-Za-z]{1,2})(\d*[+-])?$", s)
    if not m:
        raise KeyError(f"cannot read an element symbol from species {species!r}")
    return m.group(1).capitalize()


@lru_cache(maxsize=None)
def edge_intervals(element: str) -> tuple[tuple[float, float], ...]:
    """Grid intervals (E_lo, E_hi) that contain an absorption edge.

    Detected from f″, which decreases monotonically with energy between edges
    and jumps upward at one.  These are exactly the intervals in which the
    tabulation cannot be interpolated.
    """
    sym = normalize_element(element)
    if sym in _ZERO_DISPERSION:
        return ()
    grid = _table_for(sym)
    rise = np.flatnonzero(np.diff(grid[:, 2]) > 0.0)
    return tuple((float(grid[i, 0]), float(grid[i + 1, 0])) for i in rise)


def edges(element: str) -> tuple[float, ...]:
    """Absorption-edge energies (eV) inside the tabulated band.

    Each is the geometric midpoint of the grid interval the jump falls in, so
    it is only located to the ~0.4 % grid spacing — enough to say "the
    wavelength is near an edge", not enough to quote as an edge energy.
    """
    return tuple(float(np.sqrt(lo * hi)) for lo, hi in edge_intervals(element))


def _table_for(sym: str) -> np.ndarray:
    table = _load_table()
    if sym not in table:
        raise KeyError(
            f"no Cromer-Liberman dispersion data for element {sym!r} "
            f"(the tabulation covers Z = 3-98)")
    return table[sym]


def near_edge(element: str, wavelength: float,
              window_ev: float = NEAR_EDGE_EV) -> float | None:
    """The absorption edge within ``window_ev`` of this wavelength, or None."""
    energy = _HC_EV_ANGSTROM / wavelength
    for e in edges(element):
        if abs(energy - e) <= window_ev:
            return e
    return None


def dispersion(element: str, wavelength: float) -> tuple[float, float]:
    """(f′, f″) in electrons at ``wavelength`` (Å).

    f′ is interpolated linearly in log E and f″ log-log, matching how each
    behaves: f″ is a near-power-law between edges (as the photoelectric cross
    section it is proportional to is), while f′ changes sign and cannot be
    logged.  On the 0.4 %-spaced grid the choice is worth < 1e-4 e either way;
    it is stated because a coarser table would make it matter.

    Raises ``KeyError`` for an untabulated element and ``ValueError`` outside
    the tabulated band or inside a grid interval containing an edge.
    """
    sym = normalize_element(element)
    if sym in _ZERO_DISPERSION:
        return 0.0, 0.0
    grid = _table_for(sym)
    energy = _HC_EV_ANGSTROM / wavelength
    e = grid[:, 0]
    if not (e[0] <= energy <= e[-1]):
        raise ValueError(
            f"wavelength {wavelength} A (E = {energy / 1e3:.3f} keV) is outside "
            f"the tabulated {e[0] / 1e3:.0f}-{e[-1] / 1e3:.0f} keV band for {sym}")
    i = int(np.searchsorted(e, energy)) - 1
    i = max(0, min(i, len(e) - 2))
    if grid[i + 1, 2] > grid[i, 2]:
        raise ValueError(
            f"E = {energy / 1e3:.4f} keV falls in the tabulation interval "
            f"[{e[i] / 1e3:.4f}, {e[i + 1] / 1e3:.4f}] keV that contains an "
            f"absorption edge of {sym}; f' and f'' cannot be interpolated "
            "there (f' has a cusp and f'' a step), and the tabulated atomic "
            "values would be wrong anyway — supply a measured pair through "
            "the source's dispersion overrides")
    t = (np.log(energy) - np.log(e[i])) / (np.log(e[i + 1]) - np.log(e[i]))
    fp = (1.0 - t) * grid[i, 1] + t * grid[i + 1, 1]
    fpp = np.exp((1.0 - t) * np.log(grid[i, 2]) + t * np.log(grid[i + 1, 2]))
    return float(fp), float(fpp)


def photoabsorption_barn(f_double_prime: float, wavelength: float) -> float:
    """Photoelectric cross section (barn/atom) implied by f″ — optical theorem.

        σ_photo = 2·r_e·λ·f″,   r_e = 2.8179403262e-5 Å,  1 Å² = 1e8 barn

    Only the *photoelectric* part: a total-attenuation table (Rayleigh +
    Compton included, as ``attenuation.total_cross_section`` returns) is larger
    by the elastic/inelastic scattering share — a few per cent, and largest for
    light elements, since photoabsorption grows about as Z⁴ and Rayleigh as Z².
    That is why µ is *not* re-sourced from f″; the two tables cross-check each
    other instead.
    """
    return 2.0 * 2.8179403262e-5 * wavelength * f_double_prime * 1e8


def dispersion_map(species: list[str], wavelength: float) -> dict[str, complex]:
    """{species label: f′ + i·f″} for every distinct label given.

    Keyed by the **raw** ``Atom.species`` string (``"Zn2+"``), which is what
    ``structure_factor.compile_phase_sites`` looks up, even though the lookup
    behind it is per element.
    """
    return {s: complex(*dispersion(s, wavelength)) for s in dict.fromkeys(species)}


#: A single |F|² is shared across the source's emission lines, so f′/f″ are
#: evaluated at the primary line only.  Cu Kα1 and Kα2 are 20 eV apart, which
#: is nothing unless an edge lands between them — but a modelled Kβ line sits
#: ~860 eV away, and there the assumption fails.  A line whose f′ or f″ differs
#: from the primary's by more than this fraction of Z is refused rather than
#: averaged.  (The fix, if a real dataset ever needs one, is cheap: the orbit
#: sums in ``structure_factor`` are line-independent, so a per-line |F|² costs
#: one extra combine per line, not a re-evaluation.)
LINE_DISPERSION_TOL = 0.01


def resolve(species: list[str], wavelengths: tuple[float, ...],
            overrides: dict[str, tuple[float, float]] | None = None
            ) -> dict[str, complex]:
    """{species label: f′ + i·f″} at the primary line, with the line guard.

    ``overrides`` maps an element symbol to a measured (f′, f″) pair; those
    elements skip both the table lookup and the guard, which is the point —
    an override is how a user supplies a value the table cannot give.
    """
    import gemmi

    overrides = overrides or {}
    out: dict[str, complex] = {}
    for label in dict.fromkeys(species):
        sym = normalize_element(label)
        if sym in overrides:
            out[label] = complex(*overrides[sym])
            continue
        primary = dispersion(sym, wavelengths[0])
        z = float(gemmi.Element(sym).atomic_number) or 1.0
        for lam in wavelengths[1:]:
            other = dispersion(sym, lam)
            drift = max(abs(other[0] - primary[0]), abs(other[1] - primary[1]))
            if drift > LINE_DISPERSION_TOL * z:
                raise ValueError(
                    f"{sym} dispersion differs by {drift:.3f} e between the "
                    f"source's {wavelengths[0]} A and {lam} A lines "
                    f"({LINE_DISPERSION_TOL:.0%} of Z = {z:.0f} is the limit), "
                    "so one structure factor cannot serve both: an absorption "
                    "edge lies between them.  Refine the lines as separate "
                    "histograms, drop the distant line, or supply a measured "
                    "pair through the source's dispersion overrides")
        out[label] = complex(*primary)
    return out
