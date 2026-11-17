"""Anomalous scattering factors f′, f″ from the Cromer-Liberman tabulation.

The atomic scattering factor at a wavelength near an absorption edge is

    f(s, λ) = f₀(s) + f′(λ) + i·f″(λ)

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

**Above 70 keV the rows are computed, not read** (WP-1925).  70 keV is the
upper limit of the original tabulation, and high-energy beamlines run to 130
keV and beyond, where the K edges of Pt to U lie.  Between 70 keV and
:data:`CEILING_EV` f″ is gemmi's Cromer-Liberman and f′ follows from it by
the dispersion relation, anchored on the bundled table (``_continuation``
says how, and why gemmi's own f′ is not used there).  Z = 93-98 keep the
3-70 keV band.

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

from .._about import DATA_PACKAGE as _DATA_PACKAGE
from .attenuation import _HC_EV_ANGSTROM

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
    text = (resources.files(_DATA_PACKAGE) / _DATA_FILE).read_text(encoding="utf-8")
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
    asymmetry between the two lookups is physical, not an oversight. An
    isotope reads as its element (``scattering.xray_scatterer``), so ``"D"``
    and ``"2H"`` → ``"H"``, and ``"7Li1+"`` → ``"Li"``.
    """
    from .scattering import xray_scatterer

    s = xray_scatterer(species)
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


@lru_cache(maxsize=None)
def _table_for(sym: str) -> np.ndarray:
    """The bundled 3-70 keV rows, continued to :data:`CEILING_EV` where
    :func:`_continuation` can (Z <= 92); the bundled rows are returned as
    read, so every number inside 3-70 keV is the file's own."""
    table = _load_table()
    if sym not in table:
        raise KeyError(
            f"no Cromer-Liberman dispersion data for element {sym!r} "
            f"(the tabulation covers Z = 3-98)")
    rows = table[sym]
    extra = _continuation(sym, rows)
    return rows if extra is None else np.vstack([rows, extra])


def bundled_band(element: str) -> tuple[float, float]:
    """(E_lo, E_hi) in eV of the rows read from the bundled file for this
    element, without the computed continuation above it (3-70 keV).  H, D
    and He have no edge anywhere and are zero at every energy, so their band
    is unbounded."""
    sym = normalize_element(element)
    if sym in _ZERO_DISPERSION:
        return 0.0, float("inf")
    _table_for(sym)                       # the same KeyError for Z outside it
    rows = _load_table()[sym]
    return float(rows[0, 0]), float(rows[-1, 0])


#: Upper end of the served band.  The bundled table stops at 70 keV, the limit
#: of the original tabulation; above it rows are computed (see
#: :func:`_continuation`) up to here, which covers the high-energy powder
#: beamlines (#792 names 130 keV).  f″ there is checked against the McMaster
#: photoelectric cross section only to 120 keV, where that table stops.
CEILING_EV = 200_000.0

#: The f″ samples behind the dispersion integral: log-spaced, 100 eV to
#: 10 MeV, at this ratio, with a node pair placed on each absorption edge.
#: Below 100 eV and above 10 MeV the integrand's share of f′ between 70 and
#: 200 keV is under 1e-3 e and is absorbed by the anchoring constant.
_KK_SAMPLES = (100.0, 1.0e7, 1.002)


def _kk_samples(z: int) -> tuple[np.ndarray, np.ndarray]:
    """(ε, f″(ε)) from gemmi's Cromer-Liberman, with every edge resolved.

    Each rise of f″ between two samples is bisected to 0.01 eV and a sample
    placed either side, so the trapezoid integral sees an edge as a step
    rather than a ramp 0.2 % wide (which costs up to 0.05 e of f′ within a
    few keV of a K edge).  Below about 400 eV gemmi's f″ also rises gently
    for the heaviest elements; bisecting those adds samples, nothing else.
    """
    import gemmi

    lo, hi, ratio = _KK_SAMPLES
    eps = np.exp(np.arange(np.log(lo), np.log(hi), np.log(ratio)))

    def f2(e: float) -> float:
        return gemmi.cromer_liberman(z=z, energy=float(e))[1]

    vals = np.array([f2(e) for e in eps])
    nodes: list[tuple[float, float]] = []
    for i in np.flatnonzero(np.diff(vals) > 0.0):
        a, b, fa = float(eps[i]), float(eps[i + 1]), float(vals[i])
        while b - a > 0.01:
            m = 0.5 * (a + b)
            if f2(m) > fa:
                b = m
            else:
                a, fa = m, f2(m)
        nodes += [(a, f2(a)), (b, f2(b))]
    if nodes:
        extra = np.array(nodes)
        eps = np.concatenate([eps, extra[:, 0]])
        vals = np.concatenate([vals, extra[:, 1]])
        order = np.argsort(eps, kind="stable")
        eps, vals = eps[order], vals[order]
    return eps, vals


#: numpy >= 2 names it ``trapezoid``; 1.26, which pyproject still admits, has
#: only ``trapz``.
_trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")  # noqa: B009


def _dispersion_integral(energies: np.ndarray, eps: np.ndarray,
                         f2: np.ndarray) -> np.ndarray:
    """(2/π)·P∫ ε f″(ε) / (E² − ε²) dε at each E, over the sampled range.

    The principal value is taken by subtracting g(E) = E·f″(E) from the
    integrand, which leaves it finite at ε = E; the subtracted term is
    integrated in closed form over the sampled range [ε₀, ε₁], which is
    minus the integral outside it, since P∫₀^∞ dε/(E² − ε²) = 0.
    """
    g = eps * f2
    e0, e1 = eps[0], eps[-1]
    out = np.empty(len(energies))
    for k, energy in enumerate(energies):
        g_e = float(np.interp(energy, eps, g))
        den = energy ** 2 - eps ** 2
        with np.errstate(divide="ignore", invalid="ignore"):
            integrand = (g - g_e) / den
        bad = ~np.isfinite(integrand)
        if bad.any():
            integrand[bad] = np.interp(eps[bad], eps[~bad], integrand[~bad])
        inside = (np.log((e1 + energy) / (e1 - energy))
                  - np.log((energy + e0) / (energy - e0))) / (2.0 * energy)
        out[k] = _trapezoid(integrand, eps) + g_e * inside
    return 2.0 / np.pi * out


def _continuation(sym: str, rows: np.ndarray) -> np.ndarray | None:
    """Rows above the bundled table, on its own log spacing, to the ceiling.

    f″ is gemmi's Cromer-Liberman, the same calculation the bundled table
    holds (they agree to 1e-4 e inside it).  f′ is **not** gemmi's: above a
    K edge at Z >= 79 its f′ has spurious excursions of tens of electrons
    (Pb −32.8 e at 100 keV, U −10.2 e at 130 keV, where the neighbouring
    energies give about −1.6 and −2), so f′ is computed here from f″ by the
    dispersion (Kramers-Kronig) relation

        f′(E) = C + (2/π)·P∫ ε f″(ε) / (E² − ε²) dε

    with C the energy-independent part, taken from the bundled table itself:
    the median of f′_table − integral over its rows from half its top energy
    up.  The continuation therefore continues the table rather than replacing
    it.  Measured 2026-11-17: the integral plus C reproduces the bundled f′
    over 35-70 keV to ≤ 0.01 e for every element more than 1 keV from an
    edge, and C equals the high-energy limit the table carries (−0.015 e at
    Si, −0.99 at Pb, −1.31 at U).

    None where gemmi has no Cromer-Liberman data (Z > 92), so those elements
    keep the bundled band.
    """
    import gemmi

    z = gemmi.Element(sym).atomic_number
    top = float(rows[-1, 0])
    if not 0 < z <= 92 or top >= CEILING_EV:
        return None
    if gemmi.cromer_liberman(z=z, energy=CEILING_EV) == (0.0, 0.0):
        return None
    ratio = (rows[-1, 0] / rows[0, 0]) ** (1.0 / (len(rows) - 1))
    n = int(np.ceil(np.log(CEILING_EV / top) / np.log(ratio)))
    new_e = top * ratio ** np.arange(1, n + 1)
    new_e[-1] = min(new_e[-1], CEILING_EV)
    eps, f2 = _kk_samples(z)
    anchor = rows[rows[:, 0] >= 0.5 * top]
    c = float(np.median(anchor[:, 1]
                        - _dispersion_integral(anchor[:, 0], eps, f2)))
    fp = c + _dispersion_integral(new_e, eps, f2)
    fpp = np.array([gemmi.cromer_liberman(z=z, energy=float(e))[1]
                    for e in new_e])
    return np.column_stack([new_e, fp, fpp])


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
            f"the tabulated {e[0] / 1e3:.0f}-{e[-1] / 1e3:.0f} keV band for "
            f"{sym}; supply a measured pair through Dispersion.overrides, or "
            "set Source.dispersion = None to model without the correction "
            "(a fit then reports it as not sized)")
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
