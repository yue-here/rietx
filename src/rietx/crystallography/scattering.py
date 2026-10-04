"""X-ray atomic form factors.

f0(s) is the 5-Gaussian parameterisation of Waasmaier & Kirfel (1995),
Acta Cryst. A51, 416-431:

    f0(s) = Σ_{i=1..5} a_i · exp(−b_i s²) + c,     s = sin(θ)/λ  [Å⁻¹]

valid for s ≤ 6 Å⁻¹ — a wider range than the older 4-Gaussian Cromer-Mann
form.  Coefficients are read from the DABAX file ``f0_WaasKirf.dat`` (ESRF
DABAX collection; see ATTRIBUTION.md).

One ion *International Tables* Vol. C Table 6.1.1.3 lists is missing from that
file, Y³⁺.  It is carried in :data:`_ITC_IONS`, from Table 6.1.1.4's
4-Gaussian fit, which is valid for s ≤ 2 Å⁻¹ only (WP-1527).

The symbol is ``s`` in the equation and ``stol`` in python, following the
paper and cctbx respectively.  The DABAX file's own preamble writes ``k`` for
this quantity, above the line where Waasmaier & Kirfel's text begins, and the
package copied it from there for its first five versions; the authors write
``s``, as does the IUCr core dictionary's ``_refln.sin_theta_over_lambda``.
``k`` is the wavevector everywhere else, and the magnetic propagation vector
inside this subpackage (WP-1436).

This module is the **angle-dependent, wavelength-independent** half of the
scattering factor.  The anomalous corrections f′ + i·f″ are angle-independent
and wavelength-dependent, live in :mod:`rietx.crystallography.dispersion`,
and are applied by the structure factor rather than here — which is why the
form-factor lookup is keyed by ion (``La3+``) and the dispersion lookup by
element (``La``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

import gemmi
import numpy as np

from .._about import DATA_PACKAGE as _DATA_PACKAGE
from ..backend import get_backend

_DATA_FILE = "f0_WaasKirf.dat"

#: Ions *International Tables* Vol. C carries and ``f0_WaasKirf.dat`` does not,
#: as ``(a1..a4, b1..b4, c)`` of ITC eq. 6.1.1.15, f0(s) = Σ₁⁴ aᵢ·exp(−bᵢs²) + c.
#: Of the 111 ions in Table 6.1.1.3 the Waasmaier-Kirfel file lacks one, Y³⁺.
#:
#: Source: Maslen, Fox & O'Keefe, *International Tables for Crystallography*
#: Vol. C, 3rd ed. (2004), §6.1.1, Table 6.1.1.4, p. 579 (method *DS, the
#: modified Dirac-Slater calculation of Cromer & Waber 1968).  The fit is valid for
#: **0 < s < 2.0 Å⁻¹**: the table states a maximum error of 0.005 e (at
#: s = 2.00) and a mean of 0.001 e there.  Measured against Table 6.1.1.3's
#: own Y³⁺ column, 56 points from 0 to 2.0 Å⁻¹: maximum 0.0049 e at
#: s = 2.00, mean 0.0006 e, and f0(0) = 36.00005.  Past 2 Å⁻¹ ITC sends the
#: reader to the free atom (§6.1.1.3), and this fit leaves it: −0.11 e from
#: neutral Y's Waasmaier-Kirfel curve at s = 2.5, −0.57 e at 3.0, negative
#: beyond 3.86.  The printed a4 and b4 are negative; the OCR'd copy drops
#: both signs, and only −33.108 reproduces 36 electrons at s = 0 and only
#: −0.01319 reproduces the table at s = 2.  The nine numbers agree digit for
#: digit with cctbx's ``it1992`` table and GSAS-II's ``atmdata.py`` (ATTRIBUTION.md).
_ITC_IONS: dict[str, tuple[tuple[float, ...], tuple[float, ...], float]] = {
    "Y3+": ((17.9268, 9.15310, 1.76795, -33.108),
            (1.35417, 11.2145, 22.6599, -0.01319),
            40.2602),
}


@lru_cache(maxsize=1)
def _load_table() -> dict[str, np.ndarray]:
    """{species: [a1..a5, c, b1..b5]}: the DABAX file, plus :data:`_ITC_IONS`.

    An ITC row is four Gaussians, stored with a5 = b5 = 0 so :func:`f0` reads
    it unchanged (0·exp(0) adds nothing).  It never replaces a DABAX row.
    """
    text = (resources.files(_DATA_PACKAGE) / _DATA_FILE).read_text(encoding="utf-8")
    table: dict[str, np.ndarray] = {}
    species: str | None = None
    expecting = False
    for line in text.splitlines():
        if line.startswith("#S"):
            # e.g. "#S  57  La" or "#S  57  La3+"
            parts = line.split()
            species = parts[2] if len(parts) >= 3 else None
            expecting = True
        elif expecting and line.strip() and not line.startswith("#"):
            vals = np.array([float(v) for v in line.split()], dtype=np.float64)
            if species is not None and len(vals) == 11:
                table[species] = vals
            expecting = False
    if not table:
        raise RuntimeError("failed to parse Waasmaier-Kirfel coefficient table")
    for species, (a, b, c) in _ITC_IONS.items():
        if species not in table:
            table[species] = np.array([*a, 0.0, c, *b, 0.0], dtype=np.float64)
    return table


#: The two isotope symbols that are not mass-number-first. Every other isotope
#: label is written the way ``neutron.py``'s table writes it, ``"2H"``,
#: ``"7Li"``, ``"157Gd"``.
_ISOTOPE_SYMBOLS = frozenset({"D", "T"})


def xray_scatterer(species: str) -> str:
    """The X-ray scatterer behind an isotope label: ``"7Li1+"`` → ``"Li1+"``.

    X-rays scatter from the electrons, which do not see the nucleus's mass, so
    an isotope is its element to every X-ray lookup (f₀ here, f′/f″ in
    :mod:`.dispersion`): a leading mass number is dropped and ``D``/``T``
    read as ``H``, while a charge is kept, since it is the charge that changes
    f₀. It is the mirror of ``neutron.normalize_species``, which keeps the mass
    number and drops the charge (issue #552: without it a deuterated structure
    could not go on an X-ray histogram, nor into a joint X-ray + neutron fit).
    A mass number is dropped only where it names a nuclide the neutron table
    carries, so the two radiations accept the same isotope labels and a
    malformed ``"1Cu"`` still fails as it always did. Anything that is not an
    isotope label is returned as it is.

        >>> xray_scatterer("D"), xray_scatterer("2H"), xray_scatterer("7Li1+")
        ('H', 'H', 'Li1+')
    """
    from .neutron import _load_table as _nuclides

    s = species.strip()
    if m := re.fullmatch(r"(\d+)([A-Za-z]{1,2})(\d*[+-])?", s):
        mass, element, charge = m.groups()
        if f"{mass}{element.capitalize()}" in _nuclides():
            return element + (charge or "")
        return s
    if m := re.fullmatch(r"([A-Za-z])(\d*[+-])?", s):
        if m.group(1) in _ISOTOPE_SYMBOLS:
            return "H" + (m.group(2) or "")
    return s


def normalize_species(species: str) -> str:
    """Map a CIF type symbol to a table key, falling back to the neutral atom.

    ``"La3+"`` stays ``"La3+"`` if tabulated; ``"LA"`` → ``"La"``;
    ``"O2-"`` falls back to ``"O"`` only if the ion is missing from the table.
    A one-charge ion written without its digit is that ion: ``"Na+"`` →
    ``"Na1+"``, ``"Cl-"`` → ``"Cl1-"``.  The table always writes the ``1``,
    and pymatgen does not (WP-1527; through 1.6 these computed as the neutral
    atom).  ``"Fe+"`` still falls back, since no table carries ``Fe1+``.
    An isotope reads as its element (:func:`xray_scatterer`): ``"D"`` → ``"H"``,
    ``"7Li1+"`` → ``"Li1+"``.
    """
    table = _load_table()
    s = xray_scatterer(species)
    if s in table:
        return s
    m = re.match(r"^([A-Za-z]{1,2})(\d*[+-])?$", s)
    if m:
        elem = m.group(1).capitalize()
        ion = m.group(2) or ""
        candidates = [elem + ion]
        if ion in ("+", "-"):
            candidates.append(elem + "1" + ion)
        candidates.append(elem)
        for candidate in candidates:
            if candidate in table:
                return candidate
    raise KeyError(f"no Waasmaier-Kirfel coefficients for species {species!r}")


#: A well-formed ion label: 1-2 letters, an optional explicit charge digit
#: (``"1"`` in ``"Ag1+"`` is written out, never omitted, in this table's own
#: keys), then the sign.  Deliberately the same shape :func:`normalize_species`
#: parses, so a label this does not match is either a bare element (no
#: fallback is possible) or malformed (``normalize_species`` already raises on
#: those, which is not this function's job to repeat).
_ION_RE = re.compile(r"^([A-Za-z]{1,2})(\d*)([+-])$")


@dataclass(frozen=True)
class SpeciesFallback:
    """One ion :func:`normalize_species` could not find, reported instead of
    swallowed (issue #202).

    ``true_electrons`` is Z minus the signed formal charge — the ion's own
    electron count, derived rather than tabulated so nothing here duplicates
    a second copy of periodic-table data.  ``returned_electrons`` is what the
    fallback actually supplies: ``f0(element, stol=0)`` of the neutral atom the
    substitution used, which is *approximately* Z (the Gaussian fit reproduces
    the sum rule to a few parts in 10⁴, not exactly — ``f0("Y", 0) ==
    38.980795``, not ``39``) and is read off the same table `f0` reads rather
    than assumed to equal Z, so the two are on the same footing as the number
    a real refinement would see.
    """

    species: str            # the raw label, e.g. "S6+"
    element: str            # the neutral atom substituted, e.g. "S"
    charge: int             # signed formal charge parsed from `species`
    true_electrons: float   # Z - charge
    returned_electrons: float  # f0(element, 0), what the fallback supplies

    @property
    def delta_frac(self) -> float | None:
        """Fractional error the substitution puts on the scattering factor
        f (not |f|²) at s = 0.

        ``None`` when ``true_electrons`` is itself zero -- a bare proton
        (``H+``/``H1+``) or ``He2+``, where the formal charge equals Z.  The
        fraction is genuinely undefined there (division by the ion's own,
        zero, electron count), not zero, so ``None`` is the honest answer:
        the same "no single number" convention ``Diagnostic.value`` already
        documents (``schemas.common.Diagnostic``), rather than a
        ``ZeroDivisionError`` a caller three frames up (``Refinement.fit``,
        unconditionally) has no way to expect.
        """
        if self.true_electrons == 0.0:
            return None
        return (self.returned_electrons - self.true_electrons) / self.true_electrons


def detect_fallback(species: str) -> SpeciesFallback | None:
    """Whether normalizing ``species`` silently substituted the neutral atom.

    ``None`` covers every case that is *not* the #202 defect: a bare element
    (``"Fe"``), an ion the table carries in full (``"O2-"``), and a malformed
    label — ``normalize_species`` already raises cleanly on those, and this
    function never widens that: it only re-derives, from the same regex
    grammar, whether a **well-formed** ion's charge survived resolution.  Any
    exception ``normalize_species`` raises here (an element absent from the
    table under any form) is swallowed the same way, because a totally
    unknown species is a different, already-loud failure — this function's
    only job is the quiet one.
    """
    s = xray_scatterer(species)
    m = _ION_RE.match(s)
    if not m:
        return None
    elem, digits, sign = m.groups()
    elem = elem.capitalize()
    charge = int(digits or "1") * (1 if sign == "+" else -1)
    try:
        resolved = normalize_species(s)
    except KeyError:
        return None
    if resolved != elem:
        return None  # the ion itself is tabulated -- no fallback happened
    z = gemmi.Element(elem).atomic_number
    true_electrons = float(z - charge)
    returned_electrons = float(f0(elem, np.array([0.0]))[0])
    return SpeciesFallback(species=species.strip(), element=elem, charge=charge,
                           true_electrons=true_electrons,
                           returned_electrons=returned_electrons)


def written_species(species: str) -> tuple[str, SpeciesFallback | None]:
    """The species rietx computes for ``species``, as a label a writer spells.

    The project writers' one rule for a species (WP-1527, the maintainer's
    rule of 2026-10-03): write the atom rietx computed, never refuse one.
    A one-charge ion written without its digit is the tabulated ion, so
    ``"Cu+"`` → ``"Cu1+"``, the label every program's spelling starts from.
    An ion the table lacks is computed as the neutral atom (:func:`detect_fallback`),
    so ``"Fe+"`` → ``"Fe"``, returned with the fallback for the writer to
    report. A mass number is kept (``"57Fe+"`` → ``"57Fe"``), since the
    isotope is the neutron half of what rietx computed. Every other label is
    returned as it stands.

        >>> written_species("Cu+")[0], written_species("Fe+")[0]
        ('Cu1+', 'Fe')
    """
    m = re.fullmatch(r"(\d*)([A-Za-z]{1,2})(\d*)([+-])", species.strip())
    if m is None:
        return species, None
    mass, element, magnitude, sign = m.groups()
    fallback = detect_fallback(species)
    if fallback is not None:
        return mass + element, fallback
    if not magnitude:
        try:
            resolved = normalize_species(species)
        except KeyError:
            return species, None  # no species at all; the fit's own error
        if resolved.endswith("1" + sign):
            return f"{mass}{element}1{sign}", None
    return species, None


def written_neutral_diagnostics(structure, *, code: str, program: str) -> list:
    """One ``Diagnostic`` per ion label a writer wrote as its neutral atom.

    The writer-side twin of the fit's ``SPECIES_FALLBACK_NEUTRAL``: the same
    :func:`detect_fallback`, grouped by the label as written so ``where``
    lists every site carrying it. ``code`` is the writer's own, passed as a
    literal at the call so each format's code is visible where it is emitted.
    A site carrying a moment is skipped: a writer keeps its ion, which the
    magnetic form factor is computed from.
    """
    from ..schemas.common import Diagnostic

    found: dict[str, tuple[SpeciesFallback, str, list[str]]] = {}
    for i, phase in enumerate(structure.phases):
        for j, atom in enumerate(phase.atoms):
            if getattr(atom, "moment", None) is not None:
                continue
            written, fallback = written_species(atom.species)
            if fallback is not None:
                found.setdefault(fallback.species, (fallback, written, []))[2].append(
                    f"phases.{i}.atoms.{j}.species")
    out = []
    for fallback, written, where in found.values():
        sign = "+" if fallback.charge > 0 else "-"
        ion = f"{fallback.element}{abs(fallback.charge)}{sign}"
        out.append(Diagnostic(
            level="warning", code=code, where=where, value=fallback.delta_frac,
            message=(
                f"{fallback.species!r} is written to this {program} file as "
                f"neutral {written}. rietx's X-ray table has no "
                f"{ion}, so rietx computes the neutral atom for it "
                f"({fallback.returned_electrons:.4g} electrons against the "
                f"ion's {fallback.true_electrons:.0f}), and the file states "
                f"the atom rietx computed"),
            suggestion=(
                f"to refine the ion in {program}, respell the site there by "
                f"hand; a rietx fit of this structure computes neutral "
                f"{fallback.element} and says so as SPECIES_FALLBACK_NEUTRAL")))
    return out


def f0(species: str, stol: np.ndarray) -> np.ndarray:
    """Elastic form factor at ``stol`` = s = sin(θ)/λ (Å⁻¹).

    Waasmaier & Kirfel (1995) Eq. (1): f0(s) = Σ a_i exp(−b_i s²) + c.
    ``"Y3+"`` reads its four Gaussians from *International Tables* Vol. C
    (2004) Table 6.1.1.4, eq. 6.1.1.15, fitted for s ≤ 2 Å⁻¹ only
    (:data:`_ITC_IONS` has the source and the error past it).
    """
    xp = get_backend()
    coeffs = _load_table()[normalize_species(species)]
    a = xp.asarray(coeffs[0:5], dtype=np.float64)
    c = coeffs[5]
    # lifted, not left as a numpy view: b sits on the *left* of the broadcast
    # product below, which torch will not accept against a traced operand
    b = xp.asarray(coeffs[6:11], dtype=np.float64)
    s2 = xp.asarray(stol, dtype=np.float64) ** 2
    # b ⊗ s² as a broadcast product (np.outer cannot take a traced operand)
    return xp.einsum("i,in->n", a, xp.exp(-(b[:, None] * s2[None, :]))) + c
