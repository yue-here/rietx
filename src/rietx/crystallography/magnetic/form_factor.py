"""Magnetic form factors in the dipole approximation.

The neutron sees the *magnetization density* of an ion, not a point, so the
magnetic scattering amplitude falls off with angle through a form factor
f(s), s = sinθ/λ = 1/2d.  In the **dipole approximation** — the one this
package offers, and the one every powder Rietveld code uses —

    f(s) = ⟨j₀⟩(s) + (2/g − 1)·⟨j₂⟩(s)

with g the Landé factor of the ion and ⟨jₙ⟩ the radial integrals of the 4f/3d
wavefunction, for most ions fitted to the analytic form (Brown, P. J.,
*International Tables for Crystallography* Vol. C, § 4.4.5)

    ⟨j₀⟩(s) = A·e^(−a·s²) + B·e^(−b·s²) + C·e^(−c·s²) + D
    ⟨jₙ⟩(s) = s²·[A·e^(−a·s²) + B·e^(−b·s²) + C·e^(−c·s²) + D]   (n ≥ 2)

**The s² factor on ⟨j₂⟩ is not decoration**: it is what makes ⟨j₂⟩(0) = 0, so
f(0) = ⟨j₀⟩(0) = 1 for every ion and the moment refined from the low-angle
data is the moment, whatever g is.  Dropping it multiplies the rare-earth form
factor by roughly 1/s² near the origin.

**Why (2/g − 1) and not (1 − 2/g).**  In the dipole approximation the
amplitude is [⟨j₀⟩·(L + 2S) + ⟨j₂⟩·L] / (L + 2S) with the normalisation
f(0) = 1.  For a J-multiplet ⟨L⟩ = (2 − g)J and ⟨S⟩ = (g − 1)J, so
L + 2S = gJ and L = (2 − g)J, giving f = ⟨j₀⟩ + ((2 − g)/g)·⟨j₂⟩.  The
coefficient is **2/g − 1**.  ``periodictable``'s module docstring writes
"(1 − 2/g)" and then says of its own pre-combined ``J`` table that it "does
not seem to be the case in practice"; only the ⟨jₙ⟩ coefficients are taken
from it here, never the combined table, and the combination is done in
:func:`magnetic_form_factor` from the expression above.

**g is an input, and for a 4f or 5f ion it is required.**  For a spin-only 3d
ion g = 2, the ⟨j₂⟩ coefficient vanishes identically and f = ⟨j₀⟩ — so g = 2
is the default *there*.  For a rare earth or an actinide the orbital moment is
not quenched, g ≠ 2, and the ⟨j₂⟩ term is the difference between FullProf's
``MHO3`` and ``JHO3`` for the same ion (FullProf manual, § form factors).
Defaulting g to 2 for those would silently drop a term of order 10-30 % at
high angle, so :func:`magnetic_form_factor` **refuses by name** instead
(issue #257 A5).

**An ion the table does not carry is refused by name, never mapped to a
neighbour** (issue #202's rule for a new data table): Fe³⁺ and Fe²⁺ have
visibly different form factors and "the nearest ion" is how a moment comes out
5 % wrong with a small esd.

Provenance
----------
The coefficients are Brown's ITC Vol. C § 4.4.5 tabulation (3rd ed., 2004,
Tables 4.4.5.1-4.4.5.8, pp. 454-457).  Most rows were transcribed from the
public-domain ``periodictable`` package, which carries the CrysFML Fortran
table; ``ATTRIBUTION.md`` carries the row, and ``periodictable`` is **not** a
dependency of this package — the numbers are here, in source.

**Verified 2026-10-01 (#593), whole table.** Every ⟨j₀⟩ and ⟨j₂⟩ row
was compared, as curves on Brown's fit ranges, with two independent
renderings of Brown's fits: the 2004 print (read from the page image) and P.
J. Brown's own data file (signed "Jane Brown", dated 2013-09-19, mirrored in
the McPhase manual at
http://www2.cpfs.mpg.de/~rotter/homepage_mcphase/manual/node137.html; the
ILL "ffacts" pages are gone). The file was read for verification only and
nothing is copied from it (``ATTRIBUTION.md``). Of the 190 rows the print
carries, 188 agree with both renderings to the print's rounding. Two did
not: **Ni³⁺ ⟨j₀⟩ and ⟨j₂⟩**. Those rows were CrysFML's, and both of Brown's
renderings disagree with them (CrysFML's Ni³⁺ ⟨j₂⟩ is Brown's Ni⁴⁺ row digit
for digit). The physics agrees with Brown: with CrysFML's rows the ⟨r²⟩
steps Ni²⁺ → Ni³⁺ → Ni⁴⁺ are −25 to −28 % and then 0 to +1 %, where every
other 3d element steps −14 to −19 % and then −11 to −15 %. Ni³⁺ is now the
print's row, and so is V ⟨j₂⟩. CrysFML's V ⟨j₂⟩ is a refit that differs from
the print by at most 5 × 10⁻⁴ in f, and it was aligned with the print so
that the citation covers it. Both rows carry the print's three decimals on
the exponents. The rare-earth rows also reproduce the Dirac-Fock values
Brown fitted (Freeman & Desclaux 1979, *J. Magn. Magn. Mater.* **12**,
11-21, Table 7) to his printed fit error. The table is pinned by a
fingerprint and a self-consistency battery in
``tests/test_magnetic_form_factor_table.py``.

**Ce³⁺ is Brown's row printed as "Ce²⁺"** (issue #626, 2026-10-01).  The
row ITC Vol. C labels Ce²⁺ in Tables 4.4.5.3/.7/.11/.13 reproduces Freeman &
Desclaux's (1979, *J. Magn. Magn. Mater.* **12**, 11-21, Table 7) Dirac-Fock
**Ce³⁺** values at Brown's own printed fit error in all four orders.  Freeman
& Desclaux computed no Ce²⁺, and the row's ⟨r²⟩ (1.29 a.u., their Ce³⁺ is
1.31) lies below Nd²⁺'s, where a Ce²⁺ would lie above.  The label is a
misprint, carried by Brown's own data file too.  So the row is stored here
under ``"Ce3+"``, and ``"Ce2+"`` is refused by name with that reason
(:data:`_RETIRED`): no Ce²⁺ form factor is tabulated in any source this
module holds, and serving Ce³⁺ physics under a Ce²⁺ key would be silent.

Cross-checked against published rows: Fe³⁺ ⟨j₀⟩ against Gupta *et al.*
(arXiv:1309.3683), which cites Dianoux & Lander's *Neutron Data Booklet*, and
Mn²⁺ ⟨j₀⟩ against the MnF₂ polarised-neutron study of 2025 — seven of seven
coefficients each.

**Pr³⁺ and Pu³⁺ are computed tables, not published rows** (rietx #1804,
#1691).  ITC Vol. C carries no Pr row of any charge; the Pr³⁺ row this
table held until 2026-11 was Lisher & Forsyth's (1971) 5-parameter fit to
non-relativistic Hartree-Fock values, off the Dirac-Fock footing of every
other rare-earth row (its ⟨j₀⟩ misses a Dirac-Fock Pr³⁺ curve by 23 times its
printed fit error).  Brown's printed Pu³⁺ rows are fits to the **Pu⁵⁺** curve:
against Desclaux & Freeman's (1978, *J. Magn. Magn. Mater.* **8**, 119-129,
Table 6) Pu³⁺ block they score 20.6 (⟨j₀⟩) and 12.3 (⟨j₂⟩) times his printed
fit error, against a Dirac-Fock Pu⁵⁺ curve computed for rietx about 1 (their
Pu⁵⁺ block was not read), and ⟨j₀⟩(0.2 Å⁻¹) is 0.627
against 0.574.  Both ions are served from the computed Dirac-Fock tables
below, on their neighbours' footing; the Pu³⁺ table reproduces Desclaux &
Freeman's printed Pu³⁺ block to within 5.3 × 10⁻⁵ in all 84 cells.

**A bare element symbol is the neutral atom**, and its row says which
configuration it is.  Brown's bare ``Mo``, ``Tc``, ``Ru``, ``Rh`` and ``Pd``
rows are fits to singly charged M⁺ curves (each matches an M⁺ 4dⁿ⁻³5s²
configuration to his printed fit error and the neutral ground configuration
to nothing), so all five are served from computed neutral-atom tables
(Hartree-Fock for the Hund's-rule term, Brown's own footing): ``Mo``, ``Tc``,
``Ru`` and ``Rh`` in the ground configuration, ``Pd`` in the excited 4d⁹5s
³D, since the 4d¹⁰ ¹S ground state has no open shell to carry a moment (its
⟨jₙ⟩ curves exist all the same; ⟨j₀⟩ at s = 0.2 Å⁻¹ is 0.4646 against
0.4965).  The other bare rows are kept, and
:func:`approximation_name` names what each is: ``Sc`` and ``Nb`` are neutral
atoms in an excited configuration, ``Ti`` the ground configuration in the
non-Hund term ¹G (a state Clementi & Roetti 1974 list), ``V``, ``Mn``,
``Fe``, ``Co``, ``Cu`` and ``Y`` configuration averages, and ``Cr`` and
``Ni`` match no configuration tried (footing not identified).

Computed curves
---------------
:data:`COMPUTED_FILE` (``rietx/data/mff_computed.dat``) holds every curve
this package computed for itself, and its header says so: **computed for
rietx, not peer-reviewed**.  Each block names its code (Cowan's RCN, Mod
36.2.5; GRASP2018), its footing and its configuration, and the repository's
``tools/magnetic_form_factors/`` holds the decks and scripts that regenerate
and check it.  Two kinds of block, both ⟨jₙ⟩ on s = 0.01 Å⁻¹ steps to
:data:`TABLE_S_MAX` = 6 Å⁻¹, read with one cubic spline
(:func:`tabulated_spline`):

* **tables**, s = 0-6, which serve an ion on their own (:data:`_TABLE_KEY`):
  the ten high-charge 4d ions Ru³⁺-Ru⁶⁺, Rh⁴⁺, Tc⁴⁺, Mo³⁺-Mo⁵⁺, Nb⁴⁺ (Cowan
  HFR, the method of Kobayashi, Nagao & Ito 2011, on the configuration
  average);
  the neutral Mo, Tc, Ru, Rh and Pd atoms; Pr³⁺ and Pu³⁺ (GRASP2018
  Dirac-Fock).
  They carry ⟨j₄⟩ too, which nothing here evaluates.
* **tails**, from the end of Brown's fitted range to s = 6, one per Brown
  row, on that row's own footing: Hartree-Fock for the 3d and 4d rows
  (Brown's own, Clementi & Roetti's), Dirac-Fock for the rare earths and
  actinides (Freeman & Desclaux 1979; Desclaux & Freeman 1978).

Fitted ranges and tails
-----------------------
**Every Brown row is a least-squares fit over a stated range of s, and past
that range it is not a form factor** (Mn²⁺ ⟨j₀⟩ carries e^(+0.609·s²) and
reached 1.01 at s = 3 Å⁻¹ and 1.4 × 10⁷ at s = 6, rietx #1796).  Brown
fitted the 3d and 4d rows over s = 0-1.5 Å⁻¹, the rare-earth rows over
0-1.2 Å⁻¹ and the actinide rows out to 1.5 Å⁻¹ (ITC Vol. C § 4.4.5,
p. 461).  So a Brown row is his analytic form exactly up to that end
(:func:`fitted_range`), then blended onto its computed tail over
:data:`TAIL_BLEND_WIDTH` = 0.2 Å⁻¹ by the C² quintic 10t³ − 15t⁴ + 6t⁵, and
the tail beyond.  A fit whose reflections pass a Brown row's range carries
``MAGNETIC_FORM_FACTOR_COMPUTED_TAIL`` once (:func:`past_fitted_range` is
the one comparison).  Past s = 6 Å⁻¹ every row is refused, before any work,
by :func:`j0`, :func:`j2`, :func:`magnetic_form_factor` and the forward
model's stage compile alike (:func:`past_table_end`).

**Every curve here is a free-ion curve.**  Beyond about s = 1.2 Å⁻¹ a
crystal's form factor departs from any free-ion one: covalency expands the
radial density, and the aspherical ⟨j₄⟩ term the dipole approximation drops
can exceed ⟨j₀⟩ there.  The manual's section on the dipole approximation
states the sizes.

``periodictable`` also carries a pre-combined "J" entry for Ce²⁺, Ce³⁺ and
Pr³⁺ (``add_form_factor("J", ...)``) that looks, at first glance, like it
could supply a Ce³⁺ row — but its own module docstring says the combination
it uses does not actually follow the ⟨j₀⟩ + (2/g − 1)⟨j₂⟩ (or any stated)
formula "in practice", and a single combined curve cannot be decomposed back
into separate ⟨j₀⟩(s) and ⟨j₂⟩(s) without knowing which g it assumed. It was
not used here for that reason either.

References
----------
* Brown, P. J. *International Tables for Crystallography* Vol. C, § 4.4.5 —
  the ⟨jₙ⟩ coefficients and the analytic form.
* Freeman, A. J. & Desclaux, J. P. (1979). *J. Magn. Magn. Mater.* **12**,
  11-21 — the Dirac-Fock ⟨jₙ⟩ values Brown fitted for the rare-earth rows;
  the evidence that his "Ce²⁺" row is Ce³⁺.
* Desclaux, J. P. & Freeman, A. J. (1978). *J. Magn. Magn. Mater.* **8**,
  119-129 — the Dirac-Fock actinide values Brown fitted; Table 6's Pu³⁺ block
  checks the computed Pu³⁺ table and shows his printed Pu³⁺ row is not Pu³⁺
  (it matches a Pu⁵⁺ curve computed for rietx).
* Clementi, E. & Roetti, C. (1974). *At. Data Nucl. Data Tables* **14**,
  177-478 — the Hartree-Fock wavefunctions Brown fitted the 3d/4d rows to.
* Cowan, R. D. (1981). *The Theory of Atomic Structure and Spectra*
  (University of California Press) — RCN, the code of the 3d/4d curves.
* Froese Fischer, C., Gaigalas, G., Jönsson, P. & Bieroń, J. (2019).
  *Comput. Phys. Commun.* **237**, 184-187 — GRASP2018, the code of the
  4f/5f curves.
* Kobayashi, K., Nagao, T. & Ito, M. (2011). *Acta Cryst.* A **67**, 473-480
  — HFR, the method of the high-charge 4d tables.
* Halpern, O. & Johnson, M. H. (1939). *Phys. Rev.* **55**, 898 — magnetic
  neutron scattering by an atom with a magnetization density.
* Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
  manual's § form factors is where the ⟨j₀⟩-only and ⟨j₀⟩ + c₂⟨j₂⟩ spellings
  of the same ion are named apart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal

import numpy as np
from scipy.interpolate import CubicSpline

from ...backend import get_backend

#: (A, a, B, b, C, c, D) of one Brown-shaped ⟨jₙ⟩ fit.
Coefficients = tuple[float, float, float, float, float, float, float]

#: Atomic numbers whose ions need an explicit ``g``: the lanthanides (Ce-Lu)
#: and the actinides (Th-Cm).  Not "f block" as a shell-filling statement — it
#: is the list of elements in this table whose ⟨j₂⟩ term is not negligible,
#: and La (Z 57) is excluded because nothing here carries a La row anyway.
_G_REQUIRED_Z = frozenset(range(58, 72)) | frozenset(range(90, 97))

_ION = re.compile(r"^([A-Z][a-z]?)(?:(\d+)([+-]))?$")

#: ⟨j₀⟩ coefficients, keyed by ion (``"Cr"``, ``"Cr3+"``).  89 rows: the 3d
#: and 4d transition series, the 4f rare earths and the 5f actinides Brown's
#: table carries, less the rows served from a computed table instead
#: (:data:`_TABLE_KEY`: his Pu³⁺, and his bare Mo, Tc, Ru, Rh and Pd, which
#: are M⁺ curves).
_J0: dict[str, Coefficients] = {
    "Sc": (0.2512, 90.0296, 0.329, 39.4021, 0.4235, 14.3222, -0.0043),
    "Sc1+": (0.4889, 51.1603, 0.5203, 14.0764, -0.0286, 0.1792, 0.0185),
    "Sc2+": (0.5048, 31.4035, 0.5186, 10.9897, -0.0241, 1.1831, 0.0),
    "Ti": (0.4657, 33.5898, 0.549, 9.8791, -0.0291, 0.3232, 0.0123),
    "Ti1+": (0.5093, 36.7033, 0.5032, 10.3713, -0.0263, 0.3106, 0.0116),
    "Ti2+": (0.5091, 24.9763, 0.5162, 8.7569, -0.0281, 0.916, 0.0015),
    "Ti3+": (0.3571, 22.8413, 0.6688, 8.9306, -0.0354, 0.4833, 0.0099),
    "V": (0.4086, 28.8109, 0.6077, 8.5437, -0.0295, 0.2768, 0.0123),
    "V1+": (0.4444, 32.6479, 0.5683, 9.0971, -0.2285, 0.0218, 0.215),
    "V2+": (0.4085, 23.8526, 0.6091, 8.2456, -0.1676, 0.0415, 0.1496),
    "V3+": (0.3598, 19.3364, 0.6632, 7.6172, -0.3064, 0.0296, 0.2835),
    "V4+": (0.3106, 16.816, 0.7198, 7.0487, -0.0521, 0.302, 0.0221),
    "Cr": (0.1135, 45.199, 0.3481, 19.4931, 0.5477, 7.3542, -0.0092),
    "Cr1+": (-0.0977, 0.047, 0.4544, 26.0054, 0.5579, 7.4892, 0.0831),
    "Cr2+": (1.2024, -0.0055, 0.4158, 20.5475, 0.6032, 6.956, -1.2218),
    "Cr3+": (-0.3094, 0.0274, 0.368, 17.0355, 0.6559, 6.5236, 0.2856),
    "Cr4+": (-0.232, 0.0433, 0.3101, 14.9518, 0.7182, 6.1726, 0.2042),
    "Mn": (0.2438, 24.9629, 0.1472, 15.6728, 0.6189, 6.5403, -0.0105),
    "Mn1+": (-0.0138, 0.4213, 0.4231, 24.668, 0.5905, 6.6545, -0.001),
    "Mn2+": (0.422, 17.684, 0.5948, 6.005, 0.0043, -0.609, -0.0219),
    "Mn3+": (0.4198, 14.2829, 0.6054, 5.4689, 0.9241, -0.0088, -0.9498),
    "Mn4+": (0.376, 12.5661, 0.6602, 5.1329, -0.0372, 0.563, 0.0011),
    "Fe": (0.0706, 35.0085, 0.3589, 15.3583, 0.5819, 5.5606, -0.0114),
    "Fe1+": (0.1251, 34.9633, 0.3629, 15.5144, 0.5223, 5.5914, -0.0105),
    "Fe2+": (0.0263, 34.9597, 0.3668, 15.9435, 0.6188, 5.5935, -0.0119),
    "Fe3+": (0.3972, 13.2442, 0.6295, 4.9034, -0.0314, 0.3496, 0.0044),
    "Fe4+": (0.3782, 11.38, 0.6556, 4.592, -0.0346, 0.4833, 0.0005),
    "Co": (0.4139, 16.1616, 0.6013, 4.7805, -0.1518, 0.021, 0.1345),
    "Co1+": (0.099, 33.1252, 0.3645, 15.1768, 0.547, 5.0081, -0.0109),
    "Co2+": (0.4332, 14.3553, 0.5857, 4.6077, -0.0382, 0.1338, 0.0179),
    "Co3+": (0.3902, 12.5078, 0.6324, 4.4574, -0.15, 0.0343, 0.1272),
    "Co4+": (0.3515, 10.7785, 0.6778, 4.2343, -0.0389, 0.2409, 0.0098),
    "Ni": (-0.0172, 35.7392, 0.3174, 14.2689, 0.7136, 4.5661, -0.0143),
    "Ni1+": (0.0705, 35.8561, 0.3984, 13.8042, 0.5427, 4.3965, -0.0118),
    "Ni2+": (0.0163, 35.8826, 0.3916, 13.2233, 0.6052, 4.3388, -0.0133),
    "Ni3+": (0.0012, 35.000, 0.3468, 11.987, 0.6667, 4.252, -0.0148),   # ITC-C 2004 T 4.4.5.1, p. 454
    "Ni4+": (-0.009, 35.8614, 0.2776, 11.7904, 0.7474, 4.2011, -0.0163),
    "Cu": (0.0909, 34.9838, 0.4088, 11.4432, 0.5128, 3.8248, -0.0124),
    "Cu1+": (0.0749, 34.9656, 0.4147, 11.7642, 0.5238, 3.8497, -0.0127),
    "Cu2+": (0.0232, 34.9686, 0.4023, 11.564, 0.5882, 3.8428, -0.0137),
    "Cu3+": (0.0031, 34.9074, 0.3582, 10.9138, 0.6531, 3.8279, -0.0147),
    "Cu4+": (-0.0132, 30.6817, 0.2801, 11.1626, 0.749, 3.8172, -0.0165),
    "Y": (0.5915, 67.6081, 1.5123, 17.9004, -1.113, 14.1359, 0.008),
    "Zr": (0.4106, 59.9961, 1.0543, 18.6476, -0.4751, 10.54, 0.0106),
    "Zr1+": (0.4532, 59.5948, 0.7834, 21.4357, -0.2451, 9.036, 0.0098),
    "Nb": (0.3946, 49.2297, 1.3197, 14.8216, -0.7269, 9.6156, 0.0129),
    "Nb1+": (0.4572, 49.9182, 1.0274, 15.7256, -0.4962, 9.1573, 0.0118),
    "Mo1+": (0.35, 48.0354, 1.0305, 15.0604, -0.3929, 7.479, 0.0139),
    "Tc1+": (0.2674, 48.9566, 0.9569, 15.1413, -0.2387, 5.4578, 0.016),
    "Ru1+": (0.441, 33.3086, 1.4775, 9.5531, -0.9361, 6.722, 0.0176),
    "Rh1+": (0.3342, 29.7564, 1.2209, 9.4384, -0.5755, 5.332, 0.021),
    "Pd1+": (0.5033, 24.5037, 1.9982, 6.9082, -1.524, 5.5133, 0.0213),
    "Ce3+": (0.2953, 17.6846, 0.2923, 6.7329, 0.4313, 5.3827, -0.0194),   # printed "Ce2+"
    "Nd2+": (0.1645, 25.0453, 0.2522, 11.9782, 0.6012, 4.9461, -0.018),
    "Nd3+": (0.054, 25.0293, 0.3101, 12.102, 0.6575, 4.7223, -0.0216),
    "Sm2+": (0.0909, 25.2032, 0.3037, 11.8562, 0.625, 4.2366, -0.02),
    "Sm3+": (0.0288, 25.2068, 0.2973, 11.8311, 0.6954, 4.2117, -0.0213),
    "Eu2+": (0.0755, 25.296, 0.3001, 11.5993, 0.6438, 4.0252, -0.0196),
    "Eu3+": (0.0204, 25.3078, 0.301, 11.4744, 0.7005, 3.942, -0.022),
    "Gd2+": (0.0636, 25.3823, 0.3033, 11.2125, 0.6528, 3.7877, -0.0199),
    "Gd3+": (0.0186, 25.3867, 0.2895, 11.1421, 0.7135, 3.752, -0.0217),
    "Tb2+": (0.0547, 25.5086, 0.3171, 10.5911, 0.649, 3.5171, -0.0212),
    "Tb3+": (0.0177, 25.5095, 0.2921, 10.5769, 0.7133, 3.5122, -0.0231),
    "Dy2+": (0.1308, 18.3155, 0.3118, 7.6645, 0.5795, 3.1469, -0.0226),
    "Dy3+": (0.1157, 15.0732, 0.327, 6.7991, 0.5821, 3.0202, -0.0249),
    "Ho2+": (0.0995, 18.1761, 0.3305, 7.8556, 0.5921, 2.9799, -0.023),
    "Ho3+": (0.0566, 18.3176, 0.3365, 7.688, 0.6317, 2.9427, -0.0248),
    "Er2+": (0.1122, 18.1223, 0.3462, 6.9106, 0.5649, 2.7614, -0.0235),
    "Er3+": (0.0586, 17.9802, 0.354, 7.0964, 0.6126, 2.7482, -0.0251),
    "Tm2+": (0.0983, 18.3236, 0.338, 6.9178, 0.5875, 2.6622, -0.0241),
    "Tm3+": (0.0581, 15.0922, 0.2787, 7.8015, 0.6854, 2.7931, -0.0224),
    "Yb2+": (0.0855, 18.5123, 0.2943, 7.3734, 0.6412, 2.6777, -0.0213),
    "Yb3+": (0.0416, 16.0949, 0.2849, 7.8341, 0.6961, 2.6725, -0.0229),
    "U3+": (0.5058, 23.2882, 1.3464, 7.0028, -0.8724, 4.8683, 0.0192),
    "U4+": (0.3291, 23.5475, 1.0836, 8.454, -0.434, 4.1196, 0.0214),
    "U5+": (0.365, 19.8038, 3.2199, 6.2818, -2.6077, 5.301, 0.0233),
    "Np3+": (0.5157, 20.8654, 2.2784, 5.893, -1.8163, 4.8457, 0.0211),
    "Np4+": (0.4206, 19.8046, 2.8004, 5.9783, -2.2436, 4.9848, 0.0228),
    "Np5+": (0.3692, 18.19, 3.151, 5.85, -2.5446, 4.9164, 0.0248),
    "Np6+": (0.2929, 17.5611, 3.4866, 5.7847, -2.8066, 4.8707, 0.0267),
    "Pu4+": (0.4934, 16.8355, 1.6394, 5.6384, -1.1581, 4.1399, 0.0248),
    "Pu5+": (0.3888, 16.5592, 2.0362, 5.6567, -1.4515, 4.2552, 0.0267),
    "Pu6+": (0.3172, 16.0507, 3.4654, 5.3507, -2.8102, 4.5133, 0.0281),
    "Am2+": (0.4743, 21.7761, 1.58, 5.6902, -1.0779, 4.1451, 0.0218),
    "Am3+": (0.4239, 19.5739, 1.4573, 5.8722, -0.9052, 3.9682, 0.0238),
    "Am4+": (0.3737, 17.8625, 1.3521, 6.0426, -0.7514, 3.7199, 0.0258),
    "Am5+": (0.2956, 17.3725, 1.4525, 6.0734, -0.7755, 3.6619, 0.0277),
    "Am6+": (0.2302, 16.9533, 1.4864, 6.1159, -0.7457, 3.5426, 0.0294),
    "Am7+": (0.3601, 12.7299, 1.964, 5.1203, -1.356, 3.7142, 0.0316),
}

#: ⟨j₂⟩ coefficients, same keys: every ion of :data:`_J0`.
_J2: dict[str, Coefficients] = {
    "Sc": (10.8172, 54.327, 4.7353, 14.847, 0.6071, 4.218, 0.0011),
    "Sc1+": (8.5021, 34.285, 3.2116, 10.994, 0.4244, 3.605, 0.0009),
    "Sc2+": (4.3683, 28.654, 3.7231, 10.823, 0.6074, 3.668, 0.0014),
    "Ti": (4.3583, 36.056, 3.823, 11.133, 0.6855, 3.469, 0.002),
    "Ti1+": (6.1567, 27.275, 2.6833, 8.983, 0.407, 3.052, 0.0011),
    "Ti2+": (4.3107, 18.348, 2.096, 6.797, 0.2984, 2.548, 0.0007),
    "Ti3+": (3.3717, 14.444, 1.8258, 5.713, 0.247, 2.265, 0.0005),
    "V": (3.7600, 21.831, 2.4026, 7.546, 0.4464, 2.663, 0.0017),   # ITC-C 2004 T 4.4.5.5, p. 456
    "V1+": (4.7474, 23.323, 2.3609, 7.808, 0.4105, 2.706, 0.0014),
    "V2+": (3.4386, 16.53, 1.9638, 6.141, 0.2997, 2.267, 0.0009),
    "V3+": (2.3005, 14.682, 2.0364, 6.13, 0.4099, 2.382, 0.0014),
    "V4+": (1.8377, 12.267, 1.8247, 5.458, 0.3979, 2.248, 0.0012),
    "Cr": (3.4085, 20.127, 2.1006, 6.802, 0.4266, 2.394, 0.0019),
    "Cr1+": (3.7768, 20.346, 2.1028, 6.893, 0.401, 2.411, 0.0017),
    "Cr2+": (2.6422, 16.06, 1.9198, 6.253, 0.4446, 2.372, 0.002),
    "Cr3+": (1.6262, 15.066, 2.0618, 6.284, 0.5281, 2.368, 0.0023),
    "Cr4+": (1.0293, 13.95, 1.9933, 6.059, 0.5974, 2.346, 0.0027),
    "Mn": (2.6681, 16.06, 1.7561, 5.64, 0.3675, 2.049, 0.0017),
    "Mn1+": (3.2953, 18.695, 1.8792, 6.24, 0.3927, 2.201, 0.0022),
    "Mn2+": (2.0515, 15.556, 1.8841, 6.063, 0.4787, 2.232, 0.0027),
    "Mn3+": (1.2427, 14.997, 1.9567, 6.118, 0.5732, 2.258, 0.0031),
    "Mn4+": (0.7879, 13.886, 1.8717, 5.743, 0.5981, 2.182, 0.0034),
    "Fe": (1.9405, 18.473, 1.9566, 6.323, 0.5166, 2.161, 0.0036),
    "Fe1+": (2.629, 18.66, 1.8704, 6.331, 0.469, 2.163, 0.0031),
    "Fe2+": (1.649, 16.559, 1.9064, 6.133, 0.5206, 2.137, 0.0035),
    "Fe3+": (1.3602, 11.998, 1.5188, 5.003, 0.4705, 1.991, 0.0038),
    "Fe4+": (1.5582, 8.275, 1.1863, 3.279, 0.1366, 1.107, -0.0022),
    "Co": (1.9678, 14.17, 1.4911, 4.948, 0.3844, 1.797, 0.0027),
    "Co1+": (2.4097, 16.161, 1.578, 5.46, 0.4095, 1.914, 0.0031),
    "Co2+": (1.9049, 11.644, 1.3159, 4.357, 0.3146, 1.645, 0.0017),
    "Co3+": (1.7058, 8.859, 1.1409, 3.309, 0.1474, 1.09, -0.0025),
    "Co4+": (1.311, 8.025, 1.1551, 3.179, 0.1608, 1.13, -0.0011),
    "Ni": (1.0302, 12.252, 1.4669, 4.745, 0.4521, 1.744, 0.0036),
    "Ni1+": (2.104, 14.866, 1.4302, 5.071, 0.4031, 1.778, 0.0034),
    "Ni2+": (1.708, 11.016, 1.2147, 4.103, 0.315, 1.533, 0.0018),
    "Ni3+": (1.4683, 8.671, 0.1794, 1.106, 1.1068, 3.257, -0.0023),   # ITC-C 2004 T 4.4.5.5, p. 456
    "Ni4+": (1.1612, 7.7, 1.0027, 3.263, 0.2719, 1.378, 0.0025),
    "Cu": (1.9182, 14.49, 1.3329, 4.73, 0.3842, 1.639, 0.0035),
    "Cu1+": (1.8814, 13.433, 1.2809, 4.545, 0.3646, 1.602, 0.0033),
    "Cu2+": (1.5189, 10.478, 1.1512, 3.813, 0.2918, 1.398, 0.0017),
    "Cu3+": (1.2797, 8.45, 1.0315, 3.28, 0.2401, 1.25, 0.0015),
    "Cu4+": (0.9568, 7.448, 0.9099, 3.396, 0.3729, 1.494, 0.0049),
    "Y": (14.4084, 44.658, 5.1045, 14.904, -0.0535, 3.319, 0.0028),
    "Zr": (10.1378, 35.337, 4.7734, 12.545, -0.0489, 2.672, 0.0036),
    "Zr1+": (11.8722, 34.92, 4.0502, 12.127, -0.0632, 2.828, 0.0034),
    "Nb": (7.4796, 33.179, 5.0884, 11.571, -0.0281, 1.564, 0.0047),
    "Nb1+": (8.7735, 33.285, 4.6556, 11.605, -0.0268, 1.539, 0.0044),
    "Mo1+": (7.2367, 28.128, 4.0705, 9.923, -0.0317, 1.455, 0.0049),
    "Tc1+": (6.4056, 24.824, 3.54, 8.611, -0.0366, 1.485, 0.0044),
    "Ru1+": (5.2826, 23.683, 3.5813, 8.152, -0.0257, 0.426, 0.0131),
    "Rh1+": (4.026, 18.95, 3.1663, 7.0, -0.0296, 0.486, 0.0127),
    "Pd1+": (4.2749, 17.9, 2.7021, 6.354, -0.0258, 0.7, 0.0071),
    "Ce3+": (0.9809, 18.063, 1.8413, 7.769, 0.9905, 2.845, 0.012),   # printed "Ce2+"
    "Nd2+": (1.453, 18.34, 1.6196, 7.285, 0.8752, 2.622, 0.0126),
    "Nd3+": (0.6751, 18.342, 1.6272, 7.26, 0.9644, 2.602, 0.015),
    "Sm2+": (1.036, 18.425, 1.4769, 7.032, 0.881, 2.437, 0.0152),
    "Sm3+": (0.4707, 18.43, 1.4261, 7.034, 0.9574, 2.439, 0.0182),
    "Eu2+": (0.897, 18.443, 1.3769, 7.005, 0.906, 2.421, 0.019),
    "Eu3+": (0.3985, 18.451, 1.3307, 6.956, 0.9603, 2.378, 0.0197),
    "Gd2+": (0.7756, 18.469, 1.3124, 6.899, 0.8956, 2.338, 0.0199),
    "Gd3+": (0.3347, 18.476, 1.2465, 6.877, 0.9537, 2.318, 0.0217),
    "Tb2+": (0.6688, 18.491, 1.2487, 6.822, 0.8888, 2.275, 0.0215),
    "Tb3+": (0.2892, 18.497, 1.1678, 6.797, 0.9437, 2.257, 0.0232),
    "Dy2+": (0.5917, 18.511, 1.1828, 6.747, 0.8801, 2.214, 0.0229),
    "Dy3+": (0.2523, 18.517, 1.0914, 6.736, 0.9345, 2.208, 0.025),
    "Ho2+": (0.5094, 18.515, 1.1234, 6.706, 0.8727, 2.159, 0.0242),
    "Ho3+": (0.2188, 18.516, 1.024, 6.707, 0.9251, 2.161, 0.0268),
    "Er2+": (0.4693, 18.528, 1.0545, 6.649, 0.8679, 2.12, 0.0261),
    "Er3+": (0.171, 18.534, 0.9879, 6.625, 0.9044, 2.1, 0.0278),
    "Tm2+": (0.4198, 18.542, 0.9959, 6.6, 0.8593, 2.082, 0.0284),
    "Tm3+": (0.176, 18.542, 0.9105, 6.579, 0.897, 2.062, 0.0294),
    "Yb2+": (0.3852, 18.55, 0.9415, 6.551, 0.8492, 2.043, 0.0301),
    "Yb3+": (0.157, 18.555, 0.8484, 6.54, 0.888, 2.037, 0.0318),
    "U3+": (4.1582, 16.534, 2.4675, 5.952, -0.0252, 0.765, 0.0057),
    "U4+": (3.7449, 13.894, 2.6453, 4.863, -0.5218, 3.192, 0.0009),
    "U5+": (3.0724, 12.546, 2.3076, 5.231, -0.0644, 1.474, 0.0035),
    "Np3+": (3.717, 15.133, 2.3216, 5.503, -0.0275, 0.8, 0.0052),
    "Np4+": (2.9203, 14.646, 2.5979, 5.559, -0.0301, 0.367, 0.0141),
    "Np5+": (2.3308, 13.654, 2.7219, 5.494, -0.1357, 0.049, 0.1224),
    "Np6+": (1.8245, 13.18, 2.8508, 5.407, -0.1579, 0.044, 0.1438),
    "Pu4+": (2.7244, 12.926, 2.3387, 5.163, -0.13, 0.046, 0.1177),
    "Pu5+": (2.1409, 12.832, 2.5664, 5.152, -0.1338, 0.046, 0.121),
    "Pu6+": (1.7262, 12.324, 2.6652, 5.066, -0.1695, 0.041, 0.155),
    "Am2+": (3.5237, 15.955, 2.2855, 5.195, -0.0142, 0.585, 0.0033),
    "Am3+": (2.8622, 14.733, 2.4099, 5.144, -0.1326, 0.031, 0.1233),
    "Am4+": (2.4141, 12.948, 2.3687, 4.945, -0.249, 0.022, 0.2371),
    "Am5+": (2.0109, 12.053, 2.4155, 4.836, -0.2264, 0.027, 0.2128),
    "Am6+": (1.6778, 11.337, 2.4531, 4.725, -0.2043, 0.034, 0.1892),
    "Am7+": (1.8845, 9.161, 2.0746, 4.042, -0.1318, 1.723, 0.002),
}

#: Keys this table refuses with a reason rather than the generic "no row".
_RETIRED: dict[str, str] = {
    "Ce2+": ("ITC Vol. C prints a row labelled Ce2+, but it is a Ce3+ "
             "calculation: it reproduces Freeman & Desclaux's (1979) "
             "Dirac-Fock Ce3+ values at Brown's own fit error, and they "
             "computed no Ce2+. No Ce2+ magnetic form factor is tabulated in "
             "any source this table holds, so the key is refused rather than "
             "serve Ce3+ physics under a Ce2+ name. Write 'Ce3+' if the site "
             "is Ce3+"),
}


def _element(ion: str) -> tuple[str, int]:
    """``("Cr3+")`` → ``("Cr", 3)``; raises on anything this table cannot key."""
    m = _ION.match(ion.strip())
    if m is None:
        raise ValueError(
            f"{ion!r} is not a magnetic-ion spelling. Write the element symbol "
            f"with its charge — 'Cr3+', 'Fe2+', 'Ho3+' — or the neutral atom "
            f"'Cr'. Available: {', '.join(magnetic_ions())}")
    sym, n, sign = m.groups()
    charge = 0 if n is None else int(n) * (1 if sign == "+" else -1)
    return sym, charge


def magnetic_ions() -> tuple[str, ...]:
    """Every ion the table serves, Brown's rows and the computed tables, sorted."""
    return tuple(sorted(set(_J0) | set(_TABLE_KEY)))


def has_ion(ion: str) -> bool:
    """Whether the table carries a ⟨j₀⟩ row for this exact ion string.

    ``ion`` is matched verbatim (``"Dy"`` and ``"Dy3+"`` are different keys) —
    used to decide whether a bare element symbol resolves *neutrally* before
    :func:`resolve_assumed_ion` is tried (issue-magnetic-form-factor D1).
    A Brown row and a computed table both count.
    """
    return ion in _J0 or ion in _TABLE_KEY


#: The majority oxidation state that is **magnetic**, for a bare element
#: symbol whose neutral atom this table cannot resolve (every lanthanide and
#: actinide it carries: only ionic ⟨jₙ⟩ curves exist for them, Brown, *ITC*
#: Vol. C § 4.4.5).  Keyed by element, not by ion, and deliberately not "the
#: commonest state in general chemistry" — Ce⁴⁺ and Eu³⁺ are both extremely
#: common, and neither is what a magnetically ordered site of that element is
#: reported against.  One reason per row; an element absent here has no
#: sensible default and the caller's original refusal is unchanged
#: (issue-magnetic-form-factor option (b); WP-1327 D1).
_ASSUMED_ION: dict[str, tuple[str, str]] = {
    # Lanthanides: Ln3+ is the ion reported for the overwhelming majority of
    # magnetically ordered rare-earth sites (Ce and the two exceptions below
    # are the only members where the 3+ ion is *not* the one this generality
    # would predict).
    "Pr": ("Pr3+", "Ln3+ default; Pr3+ (4f2) is the reported magnetic state"),
    "Nd": ("Nd3+", "Ln3+ default; Nd3+ (4f3) is the reported magnetic state"),
    "Sm": ("Sm3+", "Ln3+ default; Sm2+ is 4f6 (J=0, non-magnetic)"),
    "Gd": ("Gd3+", "Ln3+ default; Gd3+ (4f7, S=7/2) is the reported magnetic state"),
    "Tb": ("Tb3+", "Ln3+ default; Tb3+ (4f8) is the reported magnetic state"),
    "Dy": ("Dy3+", "Ln3+ default; Dy3+ (4f9) is the reported magnetic state"),
    "Ho": ("Ho3+", "Ln3+ default; Ho3+ (4f10) is the reported magnetic state"),
    "Er": ("Er3+", "Ln3+ default; Er3+ (4f11) is the reported magnetic state"),
    "Tm": ("Tm3+", "Ln3+ default; Tm3+ (4f12) is the reported magnetic state"),
    # The three lanthanides where the plain Ln3+ rule needs its own line,
    # because a *different* oxidation state of the same element is at least
    # as common and is the one with no unpaired 4f electron:
    "Ce": ("Ce3+", "Ce4+ is 4f0 (non-magnetic); Ce3+ (4f1) is the reported "
                    "magnetic state"),
    "Eu": ("Eu2+", "Eu3+ is 4f6 (J=0, non-magnetic); Eu2+ (4f7, S=7/2) is the "
                    "state reported for magnetically ordered Eu compounds "
                    "(EuO, EuS, EuTe and similar)"),
    "Yb": ("Yb3+", "Yb2+ is 4f14 (closed shell, non-magnetic); Yb3+ (4f13) is "
                    "the reported magnetic state"),
    # Actinides: only the ions Brown's table itself carries ⟨j0⟩/⟨j2⟩ rows
    # for are offered, and only the majority state among those.
    "U": ("U4+", "the common default in actinide oxide/intermetallic "
                  "magnetism (e.g. UO2); U3+ and U5+ occur but less often"),
    "Np": ("Np4+", "the common default in actinide oxide/intermetallic "
                    "magnetism, by analogy with U4+"),
    "Pu": ("Pu3+", "the majority oxidation state reported for magnetically "
                    "ordered Pu intermetallics/pnictides (PuSb, PuAs); Pu4+ "
                    "dominates only in oxides"),
}


def assumed_ion_for_element(element: str) -> tuple[str, str] | None:
    """The declared majority-magnetic-oxidation-state default for ``element``.

    Returns ``(ion, reason)`` from :data:`_ASSUMED_ION`, or ``None`` when this
    table declares no default for it at all.  This is the *declared* table —
    it does not check that the declared ion actually has a ⟨j₀⟩ row;
    :func:`resolve_assumed_ion` is the one that checks and is what a caller
    should use.
    """
    return _ASSUMED_ION.get(element)


def resolve_assumed_ion(element: str) -> tuple[str, str] | None:
    """:func:`assumed_ion_for_element`, but only when the default resolves.

    ``None`` both when ``element`` has no declared default at all (every 3d/4d
    element, and every f-block element this table's ionic rows do not cover)
    and when it has one that does not resolve — a designed-but-unavailable
    default must come back exactly like "no default", never silently succeed
    for a different ion than the one recorded as the reason.
    """
    entry = assumed_ion_for_element(element)
    if entry is None:
        return None
    ion, _reason = entry
    return entry if has_ion(ion) else None


def lande_g(S: float, L: float, J: float) -> float:
    """The free-ion Landé g-factor, from Hund's-rule (S, L, J).

        g_J = 1 + [J(J+1) + S(S+1) - L(L+1)] / [2·J(J+1)]

    the standard result for a single J-multiplet (Ashcroft & Mermin,
    *Solid State Physics* (1976), ch. 31, eq. 31.27). ``J = 0`` (a non-magnetic
    ground state, e.g. Sm2+ or Eu3+) has no g of its own; the caller should
    never reach here for one, so this raises rather than dividing by zero.
    """
    if J <= 0.0:
        raise ValueError(
            f"g_J is undefined for J = {J!r} (a J = 0 ground state carries no "
            f"magnetic moment, let alone a g-factor)")
    return 1.0 + (J * (J + 1) + S * (S + 1) - L * (L + 1)) / (2.0 * J * (J + 1))


#: (S, L, J) Hund's-rule ground-term quantum numbers for every ion
#: :data:`_ASSUMED_ION` can produce, keyed by the *assumed ion* (not the bare
#: element) so a caller need not re-derive the term itself.  Source: the
#: standard rare-earth 4fⁿ ground terms tabulated in Ashcroft & Mermin,
#: *Solid State Physics* (1976) Table 31.3 (S, L, J and g_J for every
#: trivalent lanthanide plus Eu2+/Gd3+'s shared 4f7 term); the actinide 5fⁿ
#: rows are not in that table -- they follow by the same Hund's-rule
#: construction applied to the isoelectronic 5fⁿ configuration (5f2, 5f3, 5f5
#: parallel 4f2, 4f3, 4f5 exactly: the (S, L, J) triple depends on n and the
#: orbital degeneracy of an f shell, not on the principal quantum number).
#: This is a declared table, deliberately **not** copying a pre-combined g_J
#: column from anywhere: :func:`lande_g` recomputes g from (S, L, J) here, so
#: the two can never silently disagree the way a hand-typed g could drift
#: from its own quantum numbers.
_ASSUMED_ION_SLJ: dict[str, tuple[float, float, float]] = {
    # Ln3+, 4f^n ground terms (Hund's rules: maximise S, then L, then
    # J = |L-S| for a shell under half full, J = L+S over half full).
    "Ce3+": (0.5, 3.0, 2.5),   # 4f1,  2F5/2
    "Pr3+": (1.0, 5.0, 4.0),   # 4f2,  3H4
    "Nd3+": (1.5, 6.0, 4.5),   # 4f3,  4I9/2
    "Sm3+": (2.5, 5.0, 2.5),   # 4f5,  6H5/2
    "Eu2+": (3.5, 0.0, 3.5),   # 4f7,  8S7/2  (half-filled shell: L = 0)
    "Gd3+": (3.5, 0.0, 3.5),   # 4f7,  8S7/2  (same configuration as Eu2+)
    "Tb3+": (3.0, 3.0, 6.0),   # 4f8,  7F6    (over half full: J = L+S)
    "Dy3+": (2.5, 5.0, 7.5),   # 4f9,  6H15/2
    "Ho3+": (2.0, 6.0, 8.0),   # 4f10, 5I8
    "Er3+": (1.5, 6.0, 7.5),   # 4f11, 4I15/2
    "Tm3+": (1.0, 5.0, 6.0),   # 4f12, 3H6
    "Yb3+": (0.5, 3.0, 3.5),   # 4f13, 2F7/2
    # An3+/An4+, 5f^n ground terms -- same (S, L, J) as the isoelectronic 4f^n
    # ion above (5f2/4f2, 5f3/4f3, 5f5/4f5 share a shell degeneracy, so Hund's
    # rules place them at the same term).
    "U4+": (1.0, 5.0, 4.0),    # 5f2,  3H4    (== Pr3+'s term)
    "Np4+": (1.5, 6.0, 4.5),   # 5f3,  4I9/2  (== Nd3+'s term)
    "Pu3+": (2.5, 5.0, 2.5),   # 5f5,  6H5/2  (== Sm3+'s term)
}


def assumed_lande_g(ion: str) -> float | None:
    """The free-ion Hund's-rule g_J for ``ion``, or ``None`` if not declared.

    Declared only for the ions :func:`resolve_assumed_ion` can produce (WP-1327
    D-lande-g): a bare lanthanide/actinide site whose ion this module itself
    assumed has no way to state a Landé g either (magCIF carries no item for
    it, exactly as it carries none for the ion), so the same "assume it from
    the physics rather than refuse" choice applies to g once it already
    applies to the ion. **Not** offered for an ion a caller *stated*
    explicitly (``moment_ions={"Dy1": "Dy3+"}``) -- there the absent g is a
    caller who supplied one fact and not the other, unrelated to this default
    (issue #257 A5 continues to require it explicitly), and offering a silent
    g there would be the wrong-shaped fix for a different gap.
    """
    slj = _ASSUMED_ION_SLJ.get(ion)
    if slj is None:
        return None
    return lande_g(*slj)


#: Every ion served from a whole computed table, public label -> key in
#: ``mff_computed.dat`` (module docstring, "Computed curves").  The ten
#: high-charge 4d ions (rietx #1691), the neutral Mo, Tc, Ru, Rh and Pd
#: atoms (keyed ``Mo0`` ... in the file; the bare symbol is the public label),
#: Pr³⁺ and Pu³⁺ (#1804).  Held equal to the file's ``table`` blocks by test.
_TABLE_KEY: dict[str, str] = {
    "Mo": "Mo0", "Tc": "Tc0", "Ru": "Ru0", "Rh": "Rh0", "Pd": "Pd0",
    "Ru3+": "Ru3+", "Ru4+": "Ru4+", "Ru5+": "Ru5+", "Ru6+": "Ru6+",
    "Rh4+": "Rh4+", "Tc4+": "Tc4+", "Mo3+": "Mo3+", "Mo4+": "Mo4+",
    "Mo5+": "Mo5+", "Nb4+": "Nb4+", "Pr3+": "Pr3+", "Pu3+": "Pu3+",
}

#: The shipped data file of computed curves (module docstring, "Computed
#: curves"): computed for rietx, not peer-reviewed, and says so in its header.
COMPUTED_FILE = "mff_computed.dat"

#: Every computed curve, table or tail, ends here: s = sinθ/λ in Å⁻¹ (rietx
#: #1691, ruling D46 (c)).  Past it every row is refused.
TABLE_S_MAX = 6.0
#: The s step of every computed curve, Å⁻¹ (D46 (c)).
TABLE_STEP = 0.01
#: Width in s, Å⁻¹, of the blend from a Brown row onto its computed tail,
#: starting at the end of his fitted range (D46 (d1)).
TAIL_BLEND_WIDTH = 0.2

#: Upper end, s = sinθ/λ in Å⁻¹, of the range Brown fitted his rows over, and
#: so where each row's computed tail begins.  Brown, ITC Vol. C § 4.4.5
#: (2004), p. 461: the 3d and 4d rows are fits to Clementi & Roetti's form
#: factors "in the range (sin θ)/λ = 0 to 1.5 Å⁻¹"; the rare-earth rows to
#: Freeman & Desclaux's values over 0-0.5 and 0.5-1.2 Å⁻¹; for the actinides
#: "the calculations extend to 1.5 Å⁻¹".
S_MAX_BROWN_3D_4D = 1.5
S_MAX_BROWN_RARE_EARTH = 1.2
S_MAX_BROWN_ACTINIDE = 1.5

#: Element symbols of Brown's rare-earth tables (4.4.5.3/.7) and actinide
#: tables (4.4.5.4/.8), so a row's range is read off its element without
#: importing gemmi.
_RARE_EARTHS = frozenset({"Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb",
                          "Dy", "Ho", "Er", "Tm", "Yb", "Lu"})
_ACTINIDES = frozenset({"Th", "Pa", "U", "Np", "Pu", "Am", "Cm"})

_BROWN = "Brown, ITC Vol. C § 4.4.5 (2004), p. 461"


def _range_of(ion: str) -> float:
    sym, _ = _element(ion)
    if sym in _RARE_EARTHS:
        return S_MAX_BROWN_RARE_EARTH
    if sym in _ACTINIDES:
        return S_MAX_BROWN_ACTINIDE
    return S_MAX_BROWN_3D_4D


#: ``{ion: s_end}`` for every Brown row: where his fit ends and its computed
#: tail begins.
_FITTED_RANGE: dict[str, float] = {ion: _range_of(ion) for ion in sorted(_J0)}


def has_j2(ion: str) -> bool:
    """Whether the table carries ⟨j₂⟩ for this ion (every row it serves does)."""
    return ion in _J2 or ion in _TABLE_KEY


def needs_explicit_g(ion: str) -> bool:
    """Whether ``g`` must be supplied for this ion rather than defaulted to 2.

    True for the lanthanides and actinides, whose orbital moment is not
    quenched: there g ≠ 2, the ⟨j₂⟩ term does not vanish, and a silent g = 2
    would drop it (issue #257 A5).  False for the 3d and 4d ions, where the
    spin-only g = 2 is the physical default and makes the ⟨j₂⟩ coefficient
    exactly zero.
    """
    import gemmi

    sym, _ = _element(ion)
    try:
        z = gemmi.Element(sym).atomic_number
    except Exception:  # pragma: no cover - _element already validated the symbol
        return False
    return z in _G_REQUIRED_Z


def _no_row_error(ion: str) -> KeyError:
    """The "no row for this ion" refusal: names the ion, lists what the table
    carries for its element, and gives the reason for a retired key."""
    if ion in _RETIRED:
        return KeyError(f"no magnetic form factor for {ion!r}: {_RETIRED[ion]}")
    sym, _ = _element(ion)
    near = sorted(k for k in magnetic_ions() if _element(k)[0] == sym)
    hint = (f" This table carries {', '.join(near)} for {sym}."
            if near else f" It carries no {sym} at all.")
    return KeyError(
        f"no magnetic form factor for {ion!r}.{hint} A magnetic ion absent "
        f"from the table is refused rather than mapped to a neighbour: "
        f"Fe2+ and Fe3+ are visibly different form factors and the "
        f"substitution would come back as a wrong moment with a small esd")


def _require_row(ion: str) -> None:
    """Refuse an ion the table does not serve, before any work is done."""
    if ion not in _J0 and ion not in _TABLE_KEY:
        raise _no_row_error(ion)


def coefficients(ion: str) -> tuple[Coefficients, Coefficients]:
    """``(⟨j₀⟩ coefficients, ⟨j₂⟩ coefficients)`` in Brown's 7-parameter form,
    for one ion.

    Refuses an ion the table does not carry **by name**, listing the ions of
    the same element that are carried — the useful reply when someone typed
    ``Fe4+`` for a table that stops at Fe⁴⁺, or ``Mn3`` for ``Mn3+``.  An ion
    served from a computed table (:data:`_TABLE_KEY`) is refused too: it has
    no coefficients, and :func:`j0`/:func:`j2` evaluate it.
    """
    if ion not in _J0:
        if ion in _TABLE_KEY:
            raise KeyError(
                f"{ion!r} is served from a computed table ({COMPUTED_FILE}), "
                f"not Brown's 7-parameter form, so it has no coefficients: "
                f"use j0/j2 to evaluate it")
        raise _no_row_error(ion)
    return _J0[ion], _J2[ion]


def fitted_range(ion: str) -> float | None:
    """The upper end, s = sinθ/λ in Å⁻¹, of the range Brown fitted ``ion``'s
    rows over, where its computed tail begins; ``None`` for an ion served from
    a computed table, which nothing was fitted to (module docstring,
    "Computed curves").  Both orders of one ion share it."""
    _require_row(ion)
    return _FITTED_RANGE.get(ion)


# --------------------------------------------------------- the computed curves

@dataclass(frozen=True)
class ComputedCurve:
    """One block of :data:`COMPUTED_FILE`: a whole table or a tail.

    ``stol`` is its grid (s = sinθ/λ, Å⁻¹), ``values`` maps ``"j0"``,
    ``"j2"`` (and ``"j4"`` on a table) to the ⟨jₙ⟩ on it, and the three
    strings are the block's own provenance lines; ``row`` is empty except on
    a bare (neutral-labelled) Brown row.
    """

    key: str
    kind: Literal["table", "tail"]
    stol: np.ndarray
    values: dict
    footing: str
    configuration: str
    row: str = ""


@lru_cache(maxsize=None)
def computed_curves() -> dict[str, ComputedCurve]:
    """Parse :data:`COMPUTED_FILE` once: ``{key: ComputedCurve}``.

    Each block's grid is checked to be s = s_first, s_first + 0.01, ..., 6, so
    a malformed file fails here and never as a wrong value.
    """
    text = (files("rietx.data") / COMPUTED_FILE).read_text(encoding="utf-8")
    out: dict[str, ComputedCurve] = {}
    for chunk in text.split("\n@ ")[1:]:
        head, *body = chunk.split("\n")
        key, kind, *orders = head.split()
        meta = {}
        rows = []
        for line in body:
            if line.startswith("% "):
                name, _, value = line[2:].partition(": ")
                meta[name] = value
            elif line.strip() and not line.startswith("#"):
                rows.append(line)
        data = np.array(" ".join(rows).split(), dtype=np.float64).reshape(
            len(rows), 1 + len(orders))
        stol = data[:, 0]
        k0 = round(stol[0] / TABLE_STEP)
        want = np.round(np.arange(k0, round(TABLE_S_MAX / TABLE_STEP) + 1)
                        * TABLE_STEP, 2)
        if stol.shape != want.shape or not np.array_equal(stol, want):
            raise ValueError(f"{COMPUTED_FILE}: block {key!r} is not on "
                             f"s = {stol[0]:g}-{TABLE_S_MAX:g} at {TABLE_STEP:g}")
        out[key] = ComputedCurve(
            key=key, kind=kind, stol=stol,
            values={o: data[:, 1 + i] for i, o in enumerate(orders)},
            footing=meta["footing"], configuration=meta["configuration"],
            row=meta.get("row", ""))
    return out


def tabulated_spline(stol, values) -> CubicSpline:
    """The one interpolant of a tabulated ⟨jₙ⟩(s): a cubic spline through
    every point (not-a-knot end conditions; scipy's ``CubicSpline``).

    ``stol`` is the grid, s = sinθ/λ in Å⁻¹, strictly increasing, and
    ``values`` the ⟨jₙ⟩ on it.  On the shipped 0.01 Å⁻¹ grid the spline errs
    by at most 1.5 × 10⁻⁶ between the points on s = 0-1.5 and 8 × 10⁻¹¹
    beyond (measured against the same curves computed at 0.005 Å⁻¹, rietx
    #1691); a linear interpolant on a 0.05 grid errs by up to 0.011 in ⟨j₀⟩.
    The spline is C², so a refined cell moving s moves the value smoothly.
    The caller keeps s inside the grid: this evaluates nothing outside it.
    """
    x = np.asarray(stol, dtype=np.float64)
    y = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or x.shape != y.shape or len(x) < 4:
        raise ValueError(f"a tabulated form factor needs matching 1-D s and "
                         f"value arrays of at least 4 points; got {x.shape} "
                         f"and {y.shape}")
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        raise ValueError("a tabulated form factor must be finite everywhere")
    if not np.all(np.diff(x) > 0.0):
        raise ValueError("a tabulated form factor's s grid must be strictly "
                         "increasing")
    return CubicSpline(x, y)


@lru_cache(maxsize=None)
def _spline(key: str, order: str) -> CubicSpline:
    curve = computed_curves()[key]
    return tabulated_spline(curve.stol, curve.values[order])


def _smoothstep(t):
    """The C² quintic 10t³ − 15t⁴ + 6t⁵ on [0, 1]: 0 → 1 with zero first and
    second derivatives at both ends, so the blended curve is C² wherever its
    two parts are."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def _blend_onto_tail(ion: str, order: int, stol: np.ndarray, brown) -> np.ndarray:
    """Brown's value where s ≤ s_end, his row blended onto its computed tail
    over [s_end, s_end + :data:`TAIL_BLEND_WIDTH`], the tail beyond."""
    s_end = _FITTED_RANGE[ion]
    out = np.array(brown, dtype=np.float64)
    shape = out.shape
    out = np.atleast_1d(out)
    s = np.atleast_1d(stol)
    past = s > s_end
    w = _smoothstep((s[past] - s_end) / TAIL_BLEND_WIDTH)
    tail = _spline(ion, f"j{order}")(s[past])
    out[past] = np.where(w < 1.0, (1.0 - w) * out[past] + w * tail, tail)
    return out.reshape(shape)


def _value(ion: str, order: int, stol):
    """⟨j_order⟩(s), unchecked: the one evaluator of every row."""
    key = _TABLE_KEY.get(ion)
    if key is not None:
        return _spline(key, f"j{order}")(np.asarray(stol, dtype=np.float64))
    coef = (_J0 if order == 0 else _J2).get(ion)
    if coef is None:
        raise _no_row_error(ion)
    xp = get_backend()
    s = xp.asarray(stol, dtype=np.float64)
    brown = _jn(coef, s * s, stol2_factor=order > 0)
    s_np = np.asarray(stol, dtype=np.float64)
    if not np.any(s_np > _FITTED_RANGE[ion]):
        return brown
    return _blend_onto_tail(ion, order, s_np, brown)


@dataclass(frozen=True)
class PastFittedRange:
    """One Brown row asked for past the range he fitted it over, where its
    value is the blend onto (then) its computed tail.

    ``stol`` is the largest s = sinθ/λ requested, ``s_max`` where Brown's fit
    ends, ``footing`` the tail's code and footing.
    """

    ion: str
    order: int
    s_max: float
    stol: float
    footing: str

    @property
    def d_min(self) -> float:
        """The smallest d spacing, Å, inside Brown's fitted range."""
        return 1.0 / (2.0 * self.s_max)


def past_fitted_range(ion: str, stol, g: float | None = None,
                      *, orders: tuple[int, ...] | None = None,
                      ) -> tuple[PastFittedRange, ...]:
    """Every Brown row ``ion`` uses that ``stol`` (a scalar or an array, Å⁻¹)
    reaches past his fitted range, so onto its computed tail.

    The one comparison of an s with a row's range.  ``orders`` defaults to the
    rows :func:`magnetic_form_factor` evaluates at this ``g``: ⟨j₀⟩ always,
    ⟨j₂⟩ when g ≠ 2.  Empty when every s is inside the range, and always for
    an ion served from a computed table.  Raises nothing for s ≤ 6.
    """
    _require_row(ion)
    s_max = _FITTED_RANGE.get(ion)
    s_hi = float(np.max(np.asarray(stol, dtype=np.float64)))
    if s_max is None or not s_hi > s_max:
        return ()
    if orders is None:
        orders = (0,) if resolve_g(ion, g) == 2.0 else (0, 2)
    footing = computed_curves()[ion].footing
    return tuple(PastFittedRange(ion=ion, order=order, s_max=s_max,
                                 stol=s_hi, footing=footing)
                 for order in orders)


def past_table_end(ion: str, stol) -> str | None:
    """The fact, without a fix, when ``stol`` reaches past s = 6 Å⁻¹, where
    every curve this table serves ends; ``None`` inside.  The caller names
    the fix, since only it knows how the s arose."""
    s_hi = float(np.max(np.asarray(stol, dtype=np.float64)))
    if not s_hi > TABLE_S_MAX:
        return None
    return (f"the {ion} magnetic form factor is asked for at s = sinθ/λ = "
            f"{s_hi:.3g} Å⁻¹ (d = {1.0 / (2.0 * s_hi):.3g} Å), past "
            f"s = {TABLE_S_MAX:g} Å⁻¹, where every curve the form-factor "
            f"table serves ends; no value is served beyond it.")


def _checked(ion: str, stol) -> None:
    """The direct evaluators' range check: an unknown ion, then s past the
    table's end, each refused before any value is computed."""
    _require_row(ion)
    msg = past_table_end(ion, stol)
    if msg is not None:
        raise ValueError(
            f"{msg} Evaluate it only at s ≤ {TABLE_S_MAX:g} Å⁻¹ "
            f"(d ≥ {1.0 / (2.0 * TABLE_S_MAX):.4g} Å).")


def _jn(coef: Coefficients, stol2, *, stol2_factor: bool):
    """Brown's analytic form, ITC Vol. C § 4.4.5 eq. (4.4.5.2)."""
    xp = get_backend()
    a0, a1, b0, b1, c0, c1, d = coef
    out = (a0 * xp.exp(-a1 * stol2) + b0 * xp.exp(-b1 * stol2)
           + c0 * xp.exp(-c1 * stol2) + d)
    return stol2 * out if stol2_factor else out


def j0(ion: str, stol):
    """⟨j₀⟩(s) for ``ion``; ``stol`` = s = sinθ/λ in Å⁻¹.  ⟨j₀⟩(0) = 1.

    A Brown row is his analytic form up to the end of his fitted range, then
    blended onto its computed tail; a computed-table ion is the table's cubic
    spline (module docstring, "Computed curves").  Past s = 6 Å⁻¹, where
    every curve ends, it raises before computing anything.
    """
    _checked(ion, stol)
    return _value(ion, 0, stol)


def _j0_value(ion: str, stol):
    """:func:`j0` without the range check: the forward model's hot path, whose
    reflections were checked once at stage compile."""
    return _value(ion, 0, stol)


def j2(ion: str, stol):
    """⟨j₂⟩(s), **including its s² factor** on a Brown row, so ⟨j₂⟩(0) = 0
    exactly.  Evaluated and range-checked as :func:`j0` is."""
    _checked(ion, stol)
    return _value(ion, 2, stol)


def _j2_value(ion: str, stol):
    """:func:`j2` without the range check (see :func:`_j0_value`)."""
    return _value(ion, 2, stol)


#: What ``magnetic_form_factor`` used, for the report and the diagnostics: the
#: string is the approximation *in force*, not a label chosen per call site.
#: :func:`approximation_name` adds the row's footing after a "; ".
J0_ONLY = "dipole, <j0> only (g = 2)"
J0_J2 = "dipole, <j0> + (2/g - 1)<j2>"

#: Said of every computed curve wherever it is named (Yue, rietx #1691,
#: 2026-11-21: the computed rows ship labelled).
COMPUTED_LABEL = "computed for rietx, not peer-reviewed"


def _short_footing(footing: str) -> str:
    """A block's footing line without its parenthesised run settings."""
    return re.sub(r" \([^)]*\)", "", footing)


def footing_name(ion: str) -> str:
    """What the row ``ion`` is, as :func:`approximation_name` names it: a
    computed table's code and footing, or Brown's row with its computed tail's
    footing, plus, for a bare (neutral-labelled) row, which configuration it
    is.  Reads the data file's own provenance lines."""
    _require_row(ion)
    key = _TABLE_KEY.get(ion)
    if key is not None:
        c = computed_curves()[key]
        return (f"computed table ({_short_footing(c.footing)}, "
                f"{c.configuration}; {COMPUTED_LABEL})")
    c = computed_curves()[ion]
    out = (f"Brown ITC Vol. C § 4.4.5 to s = {_FITTED_RANGE[ion]:g} Å⁻¹, "
           f"computed tail beyond ({_short_footing(c.footing)}; "
           f"{COMPUTED_LABEL})")
    return out + (f"; row: {c.row}" if c.row else "")


def approximation_name(ion: str, g: float | None) -> str:
    """The name of the approximation :func:`magnetic_form_factor` will use,
    and the footing of the row it uses (:func:`footing_name`).

    Resolved without evaluating anything, so a report can name it before a fit
    runs and a caller can compare two species' treatment.  Every result that
    uses a row carries this name, so a computed row, a bare row that is not
    the neutral ground state, and a row whose footing is not identified are
    each said where the moment is reported (rietx #1691).
    """
    gg = resolve_g(ion, g)
    name = J0_ONLY if gg == 2.0 else f"{J0_J2}, g = {gg:g}"
    return f"{name}; {footing_name(ion)}"


def resolve_g(ion: str, g: float | None) -> float:
    """``g`` with the 3d default applied, or a refusal naming the ion.

    ``None`` on a 3d/4d ion is the spin-only g = 2.  ``None`` on a 4f or 5f
    ion raises: see :func:`needs_explicit_g`.
    """
    if g is not None:
        if not np.isfinite(g) or g <= 0.0:
            raise ValueError(
                f"g = {g!r} for {ion!r} is not a Landé factor; it must be a "
                f"finite positive number (2 for a spin-only ion)")
        return float(g)
    if needs_explicit_g(ion):
        raise ValueError(
            f"{ion!r} is a 4f/5f ion, so its Landé g factor is not 2 and the "
            f"⟨j2⟩ term of the dipole approximation does not vanish. Give g "
            f"explicitly (Atom.moment.g); defaulting it to 2 would silently "
            f"drop a term worth tens of percent at high angle")
    return 2.0


def magnetic_form_factor(ion: str, stol, g: float | None = None):
    """f(s) = ⟨j₀⟩ + (2/g − 1)·⟨j₂⟩ — the dipole approximation.

    ``stol`` is s = sinθ/λ = 1/2d in Å⁻¹, the same argument the X-ray form factor and
    the Debye-Waller factor take (``crystallography.structure_factor``); it is
    **not** Q, and it is not Q/4π expressed in some other unit.

    At g = 2 the ⟨j₂⟩ coefficient is exactly zero and the term is not
    evaluated at all, so a 3d ion's f is ⟨j₀⟩ bit-for-bit.  An unknown ion and
    an s past 6 Å⁻¹ are refused before anything is evaluated.
    """
    _checked(ion, stol)
    gg = resolve_g(ion, g)
    c2_weight = 2.0 / gg - 1.0
    f = _value(ion, 0, stol)
    if c2_weight == 0.0:
        return f
    return f + c2_weight * _value(ion, 2, stol)
