"""X-ray atomic form factors.

f0(k) is the 5-Gaussian parameterisation of Waasmaier & Kirfel (1995),
Acta Cryst. A51, 416-431:

    f0(k) = Σ_{i=1..5} a_i · exp(−b_i k²) + c,     k = sin(θ)/λ  [Å⁻¹]

valid for k ≤ 6 Å⁻¹ — a wider range than the older 4-Gaussian Cromer-Mann
form.  Coefficients are read from the DABAX file ``f0_WaasKirf.dat`` (ESRF
DABAX collection; see ATTRIBUTION.md).

This module is the **angle-dependent, wavelength-independent** half of the
scattering factor.  The anomalous corrections f′ + i·f″ are angle-independent
and wavelength-dependent, live in :mod:`pxrdref.crystallography.dispersion`,
and are applied by the structure factor rather than here — which is why the
form-factor lookup is keyed by ion (``La3+``) and the dispersion lookup by
element (``La``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

import numpy as np

from ..backend import get_backend

_DATA_PACKAGE = "pxrdref.data"
_DATA_FILE = "f0_WaasKirf.dat"


@lru_cache(maxsize=1)
def _load_table() -> dict[str, np.ndarray]:
    """Parse the DABAX file into {species: [a1..a5, c, b1..b5]}."""
    text = (resources.files(_DATA_PACKAGE) / _DATA_FILE).read_text()
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
    return table


def normalize_species(species: str) -> str:
    """Map a CIF type symbol to a table key, falling back to the neutral atom.

    ``"La3+"`` stays ``"La3+"`` if tabulated; ``"LA"`` → ``"La"``;
    ``"O2-"`` falls back to ``"O"`` only if the ion is missing from the table.
    """
    table = _load_table()
    s = species.strip()
    if s in table:
        return s
    m = re.match(r"^([A-Za-z]{1,2})(\d*[+-])?$", s)
    if m:
        elem = m.group(1).capitalize()
        ion = m.group(2) or ""
        for candidate in (elem + ion, elem):
            if candidate in table:
                return candidate
    raise KeyError(f"no Waasmaier-Kirfel coefficients for species {species!r}")


def f0(species: str, k: np.ndarray) -> np.ndarray:
    """Elastic form factor at k = sin(θ)/λ (Å⁻¹).

    Waasmaier & Kirfel (1995) Eq. (1): f0(k) = Σ a_i exp(−b_i k²) + c.
    """
    xp = get_backend()
    coeffs = _load_table()[normalize_species(species)]
    a = xp.asarray(coeffs[0:5], dtype=np.float64)
    c = coeffs[5]
    # lifted, not left as a numpy view: b sits on the *left* of the broadcast
    # product below, which torch will not accept against a traced operand
    b = xp.asarray(coeffs[6:11], dtype=np.float64)
    k2 = xp.asarray(k, dtype=np.float64) ** 2
    # b ⊗ k² as a broadcast product (np.outer cannot take a traced operand)
    return xp.einsum("i,in->n", a, xp.exp(-(b[:, None] * k2[None, :]))) + c
