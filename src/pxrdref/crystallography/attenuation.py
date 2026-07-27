"""X-ray attenuation coefficients from the McMaster compilation.

Total photon-atom cross sections (photoelectric + coherent + incoherent) are
read from ``mu_McMaster.dat``, an energy-trimmed extract of the ESRF DABAX
file ``CrossSec_McMaster.dat`` tabulating McMaster, Del Grande, Mallett &
Hubbell (1969), *Compilation of X-ray Cross Sections*, UCRL-50174 Sec. II
Rev. 1 (see ATTRIBUTION.md).  The linear attenuation coefficient of a
crystalline phase follows directly from its cell contents:

    mu [1/cm] = sum_atoms occ * multiplicity * sigma_total[barn] / V[A^3]

(1 barn = 1e-24 cm^2 and 1 A^3 = 1e-24 cm^3, so the exponents cancel.)
Attenuation here means beam *removal*, so the total cross section including
coherent and incoherent scattering is used — the same convention as the NIST
tabulations of Hubbell & Seltzer (1995), NISTIR 5632.

The table is a ~2 %-spaced logarithmic energy grid, which cannot represent
the discontinuity at an absorption edge: an edge falls *inside* a grid
interval, and interpolating across that interval would smear a factor-of-
several jump.  Such intervals are detected from the photoelectric column
(the only component that jumps at an edge — it otherwise falls smoothly with
energy) and rejected with a :class:`ValueError` rather than returning a
number that could be wrong by a large factor.  Physically, a wavelength that
close (within ~2 %) above an edge of a constituent element also means strong
fluorescence, so a refusal is more honest than any interpolated value.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import numpy as np

_DATA_PACKAGE = "pxrdref.data"
_DATA_FILE = "mu_McMaster.dat"

#: hc in eV*Angstrom (CODATA); E[eV] = _HC_EV_ANGSTROM / wavelength[A].
_HC_EV_ANGSTROM = 12398.4198

#: Avogadro constant scaled for barn/atom -> cm^2/g conversion:
#: mu/rho = sigma[barn] * 1e-24 * N_A / A = sigma * _NA_BARN / A.
_NA_BARN = 0.602214076

#: Z=84,85,87,88,89,91,93 are absent from the McMaster compilation.
_MCMASTER_GAPS = frozenset({"Po", "At", "Fr", "Ra", "Ac", "Pa", "Np"})


@lru_cache(maxsize=1)
def _load_table() -> dict[str, np.ndarray]:
    """Parse the DABAX extract into {element: (n, 3) [E_eV, photo, total]}."""
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
        raise RuntimeError("failed to parse the McMaster cross-section table")
    return table


def _interpolate(element: str, wavelength: float, column: int) -> float:
    """Log-log interpolate one column of the McMaster grid (barn/atom)."""
    sym = element.strip().capitalize()
    table = _load_table()
    if sym not in table:
        extra = (" (absent from the McMaster compilation)"
                 if sym in _MCMASTER_GAPS else "")
        raise KeyError(f"no attenuation data for element {sym!r}{extra}")
    energy = _HC_EV_ANGSTROM / wavelength
    grid = table[sym]
    e = grid[:, 0]
    if not (e[0] <= energy <= e[-1]):
        raise ValueError(
            f"wavelength {wavelength} A (E = {energy / 1e3:.3f} keV) is outside "
            f"the tabulated {e[0] / 1e3:.0f}-{e[-1] / 1e3:.0f} keV band")
    i = int(np.searchsorted(e, energy)) - 1
    i = max(0, min(i, len(e) - 2))
    # Photoelectric absorption falls monotonically with energy between edges;
    # a *rise* across the bracketing interval means an edge sits inside it.
    if grid[i + 1, 1] > grid[i, 1]:
        raise ValueError(
            f"E = {energy / 1e3:.3f} keV falls in the tabulation interval "
            f"[{e[i] / 1e3:.3f}, {e[i + 1] / 1e3:.3f}] keV that contains an "
            f"absorption edge of {sym}; mu cannot be interpolated there (and "
            "the sample would fluoresce strongly at this wavelength)")
    t = (np.log(energy) - np.log(e[i])) / (np.log(e[i + 1]) - np.log(e[i]))
    return float(np.exp((1.0 - t) * np.log(grid[i, column])
                        + t * np.log(grid[i + 1, column])))


def total_cross_section(element: str, wavelength: float) -> float:
    """Total photon-atom cross section (barn/atom) at ``wavelength`` (A).

    Log-log linear interpolation on the McMaster et al. (1969) grid.  Raises
    ``KeyError`` for elements absent from the compilation and ``ValueError``
    when the wavelength falls outside the tabulated 2-120 keV band or inside
    a grid interval containing an absorption edge (see module docstring).
    """
    return _interpolate(element, wavelength, 2)


def photoelectric_cross_section(element: str, wavelength: float) -> float:
    """Photoelectric cross section alone (barn/atom) at ``wavelength`` (A).

    This is the component the optical theorem ties to the imaginary dispersion
    correction, sigma_photo = 2*r_e*lambda*f'' (see
    ``crystallography.dispersion.photoabsorption_barn``), so it is what makes
    this 1969 compilation and the Cromer-Liberman f'' table check each other.
    It is *not* what an attenuation correction wants -- beam removal needs the
    total, coherent and incoherent scattering included.
    """
    return _interpolate(element, wavelength, 1)


def mass_attenuation(element: str, wavelength: float) -> float:
    """Mass attenuation coefficient mu/rho (cm^2/g) at ``wavelength`` (A).

    sigma[barn] * 1e-24 cm^2 * N_A / A with A the IUPAC standard atomic
    weight (via gemmi).  Matches the NIST Hubbell & Seltzer (1995) values to
    within a few percent away from absorption edges.
    """
    import gemmi

    sym = element.strip().capitalize()
    weight = float(gemmi.Element(sym).weight)
    if gemmi.Element(sym).atomic_number == 0:
        raise KeyError(f"unrecognised element {element!r}")
    return total_cross_section(sym, wavelength) * _NA_BARN / weight


def linear_attenuation(element_counts: dict[str, float], volume: float,
                       wavelength: float) -> float:
    """Linear attenuation coefficient mu (1/cm) of one crystalline phase.

    ``element_counts`` maps element symbols to occupancy-weighted atom counts
    per unit cell (the composition the refinement actually converged to, not
    a nominal formula); ``volume`` is the cell volume in A^3.
    """
    if volume <= 0.0:
        raise ValueError(f"cell volume must be positive, got {volume}")
    sigma = sum(count * total_cross_section(sym, wavelength)
                for sym, count in element_counts.items())
    return sigma / volume
