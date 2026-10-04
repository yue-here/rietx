"""The structure as drawable geometry — symmetry expansion, bonds, ellipsoids.

WP-1015.  Everything here is *crystallography*, and that is the whole reason the
module exists on this side of the wire: the browser receives Cartesian points,
3×3 matrices and index pairs, and draws them.  It never sees a space group, a
metric tensor or a U^ij.  The rule is WP-1010's one rank up — the frontend does
not re-derive what the package already computes, because two answers to "where
is this atom" is one more than a viewer may have.

Three things are computed here that ``GET /api/structure`` cannot say, which is
what earns the route its place beside it (WP-1008's test for a new route):

* **the orbit** — every symmetry image of every asymmetric-unit atom, from
  :func:`~rietx.crystallography.symmetry.expand_orbit`, *with* the rotation
  that produced it, because a displacement ellipsoid transforms as
  U\\* → R·U\\*·Rᵀ and an image drawn with its parent's tensor is drawn wrong
  in every non-orthogonal setting;
* **bonds**, by a radius-sum cutoff over the 27 nearest lattice translations, so
  a bond that leaves the cell is drawn leaving it rather than silently missing;
* **the cell frame**, as eight Cartesian corners and the twelve index pairs that
  join them.

**The ellipsoid is a diagnostic, not decoration.**  Its axes are refined
quantities: an over-flexible background inflates ADPs (CLAUDE.md's block
projection R², which Rwp *improves* through), and that arrives here as balloons.
A tensor that is not positive definite — the existing
``ADP_NOT_POSITIVE_DEFINITE`` diagnostic — is a physical impossibility rather
than a large number, so it is flagged and its non-positive semi-axes are drawn
at **zero**: the ellipsoid collapses to a disc or a needle, which is visibly
degenerate and is not a NaN.  ``√(negative)`` would be, and a NaN vertex takes
the whole mesh with it.

Representations follow ``crystallography/adp.py`` exactly: stored **U^ij**,
fractional **U\\***, and **U_cart** where the eigenvalues are the physical
mean-square displacements.  The isotropic limit is written out here rather than
routed through :func:`~rietx.crystallography.adp.isotropic_u6` because it is
exactly a sphere and the algebra says so: U^ij = Uiso·G*ᵢⱼ/(a*ᵢa*ⱼ) gives
U\\* = Uiso·G*, and U_cart = M·(Uiso·G*)·Mᵀ = Uiso·M·(MᵀM)⁻¹·Mᵀ = Uiso·I.
"""

from __future__ import annotations

import math
import time
from collections.abc import Sequence
from typing import Any

import gemmi
import numpy as np

from ..crystallography.adp import cartesian_basis, reciprocal_axis_lengths, ustar_from_ucif
from ..crystallography.symmetry import expand_orbit, resolve_group

#: Semi-axes are drawn at ``k(p)·√λ``.  ``k`` is the radius of the sphere of
#: probability ``p`` for a trivariate normal, i.e. ``√χ²₃(p)`` — the ORTEP
#: convention (Johnson, 1965, ORNL-3794).  Offered as a table rather than a free
#: number because these are the levels crystallography quotes, and because the
#: client can then change level without a refetch.
PROBABILITY_LEVELS: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90, 0.99)

DEFAULT_PROBABILITY = 0.50

#: A bond is drawn when ``d ≤ BOND_TOLERANCE·(r_i + r_j)`` on gemmi's covalent
#: radii.  1.15 is the usual slack: it keeps ionic contacts (Na–Cl at 2.82 Å
#: against a 2.68 Å radius sum) while staying below the second coordination
#: shell.  Not refinable, not physics — a **drawing threshold**, which is why it
#: rides on the query string and is echoed back in the payload: a large-radius
#: cation makes any fixed value wrong somewhere (LaB6 at 1.15 draws La–B at
#: 3.05 Å and looks like a hairball; at 1.00 it draws the B₆ octahedra alone),
#: and the honest answer to that is a control, not a better constant.
BOND_TOLERANCE = 1.15

#: Segments, not pairs — see :func:`_bonds`.  Reported in ``note`` and counted
#: in ``cut["segments"]`` when it bites.
MAX_BONDS = 4000

#: Below this, two "atoms" are the same atom (a duplicated boundary image, or a
#: disordered pair sharing a site) and no stick is drawn between them.
BOND_MIN = 0.4

#: Two non-metals closer than this fraction of their radius sum are one atom
#: split over two positions, and never bonded (WP-1466, P10).  The shortest real
#: bonds between non-metals, N≡N and NO⁺, are 0.77 of it; hydroxyfluorapatite's
#: split O/F pair is 0.39 and high cristobalite's split O pairs 0.34-0.68.  A
#: pair with a metal has :data:`METAL_SPLIT_FLOOR`, since uranyl's U=O is 0.67.
#: It is VESTA's positive minimum bond length for a split-atom model, set from
#: the radii rather than by hand.
SPLIT_FLOOR = 0.7

#: The same floor for a pair with a metal in it (WP-1468).  Measured on COD,
#: the shortest real bonds to a metal are U≡N at 0.65 of the radius sum and
#: uranyl's U=O at 0.67, and a disordered uranyl's minor part (COD 1508149)
#: at 0.70.  Split pairs span that: hydrated β-alumina's Li and a water O
#: (1529595) at 0.32, Ag β-alumina's Ag and O4 (2105331-2105335) at 0.35 and
#: from 0.59 to 0.70.  So no floor separates them, and this one sits a quarter
#: below the shortest bond, taking the two closest pairs.  The file's
#: disorder groups are what separates the rest.
METAL_SPLIT_FLOOR = 0.5

#: Ball-and-stick spheres are drawn at this fraction of the covalent radius.
#: 0.4 is VESTA's ball-and-stick fraction, and the number is only comparable
#: because both ends of the comparison are stated: VESTA scales its *atomic*
#: radii, these are gemmi's **covalent** ones, which are smaller — so this is
#: the more conservative ball of the two.  It is bounded on both sides.  Balls
#: cannot merge: two of them touch at ``0.4·(r_i + r_j)``, which is 0.35× the
#: 1.15 bond cutoff, so no *bonded* pair can ever overlap.  And it must exceed
#: the client's stick radius (0.08 Å) for the smallest atom there is, or
#: hydrogen (r = 0.31 Å) would be a lump on a rod.
BALL_FRACTION = 0.40

#: Two principal values closer than this, relative to the largest, are one.
#: A site on a 3-, 4- or 6-fold axis has an exactly uniaxial tensor whose equal
#: pair differs by rounding: at most 4.5e-16 relative on NAC, whose nearest real
#: gap is 7.8 % (Al1; WP-1462's gate).
DEGENERATE_RTOL = 1e-9

#: The direction each principal axis is turned to face.  Its components are
#: 1, e and π, so an axis a site's symmetry fixes meets it at a right angle
#: only for special cell parameters.  There the sign is the solver's again,
#: which moves the payload's bytes and no drawn ring.
_FACING = np.array([1.0, math.e, math.pi])

#: How many drawn atoms (symmetry images and boundary duplicates included) the
#: payload will carry.  A cap rather than a promise: it is reported in ``note``
#: and counted in ``cut`` when it bites, because a silently truncated cell reads
#: as a wrong structure.  It is the GUI's viewer's (WP-1502); a Python caller
#: passes a larger one.
MAX_ATOMS = 400

#: The extent ``build`` draws by default: the one cell (WP-1502).
DEFAULT_EXTENT = ((0, 1), (0, 1), (0, 1))

#: Keys an atom carries while the payload is built and never sends.
_PRIVATE = ("_turn", "_orbit")

#: Fractional tolerance for "this atom is on the cell boundary", which is what
#: earns it a duplicate at the far face — the corner atom that appears eight
#: times in every textbook drawing of a unit cell.
BOUNDARY_TOL = 1e-3

#: A coordination shell ends at the largest gap in its ligand distances, and
#: it is drawn only when that gap is at least this ratio (WP-1466, P3 and P4).
#: Brunner & Schwarzenbach (1971) found no structure whose largest gap was
#: smaller: 1.15 was their least, β-Pu averaged over its sites, and each
#: single site's was larger.  On 21 phases (``docs/wp/1466-measure``) every
#: shell's gap is 1.21 or more (baryte's BaO₁₂), and the default picture is
#: the same for any value up to 1.47, the smallest gap of a shell drawn by
#: default.
POLYHEDRON_GAP = 1.15

#: A centre's ligands are searched out to this multiple of its shortest ligand
#: distance, and the shell ends at the largest gap among all of them (P3).
#: Brunner & Schwarzenbach (1971) computed every distance out to at least three
#: times the shortest and took the largest gap of the whole sequence.  No cap
#: on the shell's size: LaB6's La has 24 B at one distance and then a gap of
#: 1.45.  A shell whose next ligand lies beyond the window takes the window's
#: edge as that next distance, which can only understate the gap.
SHELL_REACH = 3.0

#: The images the ligands are searched among reach at least this far, in Å.
#: It covers the bond search that decides which non-metals are cations, and it
#: grows when a large cation's window reaches further (Cs in CsCl, 10.7 Å).
SHELL_RADIUS = 6.0

#: A second gap is a rival to the largest when its logarithm is at least this
#: fraction of the largest's (WP-1468).  Brunner & Schwarzenbach (1971, Table 1)
#: call Ni₂In's gaps "approximately equal" at 1.22 against 1.15, where the
#: fraction is 0.70, and β-Sn's at 1.18 against 1.17 (0.95).  α-Mn's Mn(3),
#: 1.23 against 1.11 (0.50), they read as one clear gap.  A log, since equal
#: quotients are equal gaps on the logarithmic histogram they read.
RIVAL_GAP = 0.7

#: Shells of these sizes are drawn by default: the tetrahedra and octahedra a
#: chemist reads first (WP-1466, P5).  Larger ones qualify and start hidden,
#: because with NAC's CaF₈ and NaF₇ shown its cell fills with overlapping
#: polyhedra.
DEFAULT_SHELLS = range(4, 7)

#: A centre this close to a face plane, in Å, is on it and not inside.  The
#: scale is a CIF coordinate's rounding, 1e-4 of a 10 Å cell.
INSIDE_TOL = 1e-3

#: Atoms of two sites closer than this, in Å, share one position (a mixed
#: site), and count once as a centre and once as a ligand (WP-1466, P9).
SAME_POSITION = 0.01

#: What the viewer draws of a structure whose file states disorder groups:
#: every alternative, or one, each assembly's most occupied group (WP-1468).
#: A drawing choice, so it rides on the query string as the bond tolerance
#: does.  Mercury hides a CSD entry's minor positions, and CrystalMaker shows
#: each alternative as its own structure.
DISORDER_VIEWS = ("all", "major")

# ----------------------------------------------------------------------
# species → element, colour, radius
# ----------------------------------------------------------------------
#: The elements the **CPK convention** actually names (Corey & Pauling, 1953,
#: Rev. Sci. Instrum. 24, 621; Koltun, 1965, US Patent 3,170,246): hydrogen
#: white, carbon black, nitrogen blue, oxygen red, sulfur yellow, phosphorus
#: orange, halogens green, noble gases cyan, and iron a dark orange.  The
#: *assignments* are that convention; the hex values are chosen here for
#: contrast against both a light and a dark page — pure white and pure black
#: both vanish into one of them — so nothing is transcribed from another
#: implementation's table (CLAUDE.md, Licensing).
_CPK: dict[str, str] = {
    "H": "#d8d8d8", "C": "#383838", "N": "#3050f8", "O": "#e02020",
    "F": "#48d860", "Cl": "#28c828", "Br": "#a02020", "I": "#8020c0",
    "He": "#40e0e0", "Ne": "#40c8d8", "Ar": "#40b8d0", "Kr": "#3ca8c0",
    "Xe": "#3898b0", "P": "#ff8000", "S": "#e8d040", "B": "#e0a080",
    "Fe": "#c05000", "Ti": "#909090", "Na": "#8040e0", "Ca": "#40c060",
}


def element_symbol(species: str) -> str:
    """The bare element of a scattering species: ``"La3+"`` → ``"La"``.

    The engine's own parser,
    :func:`rietx.crystallography.species.element_symbol` — a charge is a
    scattering detail, while radius and colour are properties of the element.  So a nuclide is drawn as its element (``"D"``, ``"2H"`` →
    ``"H"``, ``"7Li"`` → ``"Li"``) and a valence label as its atom (``"Cval"``
    → ``"C"``), as the composition reads them; a parser of its own here passed
    ``D`` through and drew ``2H`` as unknown (#576 review, follow-up 2).  A
    species that parser refuses is ``"X"``.
    """
    from ..crystallography.species import element_symbol as _engine_element

    try:
        return _engine_element(species)
    except ValueError:
        return "X"


#: The colour for a species no form-factor grammar resolves to an element.
#:
#: Deliberately not a grey.  It was ``#909090``, which is *exactly* titanium's
#: entry above — so an unparseable species was drawn as titanium, silently, and
#: a picture of a typo looked like a picture of a structure.  An unknown is now
#: a colour no element convention claims, so it reads as the question it is.
UNKNOWN_COLOR = "#d040b0"

#: Elements whose colour is famous enough that moving it would be worse than a
#: collision: the CPK assignments people recognise without a legend.  Everything
#: else may be nudged by :func:`phase_palette` — including entries of ``_CPK``,
#: because distinguishability is a property of the *set being drawn* and not of
#: the table.  ``X`` is anchored so an unknown always looks like one.
ANCHORS = frozenset({"H", "C", "N", "O", "S", "P", "F", "Cl", "Fe", "X"})

#: The smallest OKLab distance two colours in one phase may sit at.
#:
#: Measured against the three collisions a user reported (WP-1029): F ``#48d860``
#: against Ca ``#40c060`` — *both in NAC* — is **0.070**, Si against Cl 0.078,
#: Na against La 0.099.  0.13 clears all three, while staying small enough that
#: a phase of many elements does not have to spread its hues past the point
#: where the CPK families stop being recognisable.  For scale, the fixed
#: fallback against titanium (the fourth collision, which was *exact*) is 0.218
#: once :data:`UNKNOWN_COLOR` replaces the grey.
MIN_SEPARATION = 0.13


def element_color(element: str) -> str:
    """A stable colour for an element: CPK where the convention names one.

    Everything else is **derived** rather than looked up — hue at the golden
    angle in the atomic number, at a fixed saturation and lightness that reads
    on both themes.  A derived fallback is the same device ``capabilities()``
    uses for its ``features`` flags: it cannot go stale, and a new element is
    never an unrendered atom.

    This is the colour of an element *considered alone*.  What a picture
    actually draws comes from :func:`phase_palette`, which is the one that knows
    what else is on screen.
    """
    if element in _CPK:
        return _CPK[element]
    z = gemmi.Element(element).atomic_number
    if not z:
        return UNKNOWN_COLOR
    hue = (z * 137.508) % 360.0
    return _hsl_hex(hue, 0.42, 0.55)


def phase_palette(elements: Sequence[str]) -> dict[str, str]:
    """Colours for one phase's elements, separated so they can be told apart.

    **Distinguishability is a property of the set being drawn, not of the
    element table.**  A global table can only avoid the collisions someone
    noticed; the phase in front of you is what decides whether two colours are
    the same colour.  Three real ones were reported at once (WP-1029): F against
    Ca — *both in NAC* — Si against Cl, and Na against La, plus a fallback grey
    identical to titanium (now :data:`UNKNOWN_COLOR`).

    So the anchors of :data:`ANCHORS` keep their colours and everything else is
    rotated in hue until it clears :data:`MIN_SEPARATION` from every colour
    already placed.  Hue only: lightness and chroma carry the "reads on both
    themes" property the table was built for, and rotating hue at constant
    OKLCh keeps it.

    Placement order decides *which* of a colliding pair moves, and it is
    **anchors, then the table, then the derived**: a ``_CPK`` entry was chosen
    for an element, a golden-angle hue was chosen for nobody, so Na keeps its
    purple and La is the one that shifts.  Within each tier the order is by
    symbol, so the same phase always gets the same palette — a picture that
    re-coloured itself on reload would be worse than one with a collision in it.

    sRGB has no perceptual distance, so the whole comparison happens in OKLab
    (Ottosson 2020), where a Euclidean distance is approximately perceptual.
    """
    seen: list[str] = []
    for element in elements:                     # dedupe, keeping first order
        if element not in seen:
            seen.append(element)
    palette: dict[str, str] = {}
    placed: list[tuple[float, float, float]] = []

    def place(element: str, colour: str) -> None:
        palette[element] = colour
        placed.append(_oklab(colour))

    rest = [e for e in seen if e not in ANCHORS]
    for element in seen:
        if element in ANCHORS:
            place(element, element_color(element))
    for tier in (sorted(e for e in rest if e in _CPK),
                 sorted(e for e in rest if e not in _CPK)):
        for element in tier:
            place(element, _separated(element_color(element), placed))
    return palette


def _separated(colour: str, placed: Sequence[tuple[float, float, float]]) -> str:
    """The nearest hue rotation of ``colour`` that clears every placed colour.

    Sweeps a full turn in 5° steps and takes the *first* that clears, so a
    colour that already does is returned unchanged and one that does not moves
    as little as it can.  If nothing clears — many elements in one phase — the
    rotation with the largest minimum distance wins, because a crowded picture
    should still be as separated as it can be rather than falling back to the
    collision it started with.
    """
    if not placed:
        return colour
    best, best_gap = colour, -1.0
    for step in range(0, 360, 5):
        candidate = colour if step == 0 else _rotate_hue(colour, float(step))
        lab = _oklab(candidate)
        gap = min(_oklab_distance(lab, other) for other in placed)
        if gap >= MIN_SEPARATION:
            return candidate
        if gap > best_gap:
            best, best_gap = candidate, gap
    return best


def _hsl_hex(hue: float, sat: float, light: float) -> str:
    def channel(n: float) -> int:
        k = (n + hue / 30.0) % 12.0
        a = sat * min(light, 1.0 - light)
        return round(255 * (light - a * max(-1.0, min(k - 3.0, 9.0 - k, 1.0))))

    return "#{:02x}{:02x}{:02x}".format(channel(0), channel(8), channel(4))


# --- OKLab (Ottosson 2020, https://bottosson.github.io/posts/oklab/) --------
#
# The one colour space in this file, and it is here because sRGB does not have
# a distance: `#48d860` and `#40c060` differ by 8 and 24 in two channels and are
# indistinguishable on a screen, which is the whole complaint.

_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def _oklab(colour: str) -> tuple[float, float, float]:
    """``#rrggbb`` → OKLab ``(L, a, b)``."""
    srgb = np.array([int(colour[i:i + 2], 16) / 255.0 for i in (1, 3, 5)])
    linear = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
    lms = np.cbrt(_M1 @ linear)
    return tuple(float(v) for v in _M2 @ lms)  # type: ignore[return-value]


def _oklab_hex(lab: tuple[float, float, float]) -> str:
    """OKLab ``(L, a, b)`` → ``#rrggbb``, clipped to the sRGB cube."""
    lms = np.linalg.solve(_M2, np.asarray(lab, dtype=np.float64)) ** 3
    linear = np.linalg.solve(_M1, lms)
    srgb = np.where(linear <= 0.0031308, linear * 12.92,
                    1.055 * np.abs(linear) ** (1 / 2.4) - 0.055)
    channels = np.clip(np.round(srgb * 255.0), 0, 255).astype(int)
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _oklab_distance(one: tuple[float, float, float],
                    two: tuple[float, float, float]) -> float:
    """Euclidean distance in OKLab — approximately perceptual, which is the point."""
    return float(math.dist(one, two))


def _rotate_hue(colour: str, degrees: float) -> str:
    """Turn a colour's hue, keeping its lightness and chroma.

    Constant L and C is what preserves the property the table was built for:
    every value reads against both a light and a dark page, and a rotation that
    changed lightness would quietly undo that for one element.
    """
    lightness, a, b = _oklab(colour)
    angle = math.radians(degrees)
    return _oklab_hex((lightness,
                       a * math.cos(angle) - b * math.sin(angle),
                       a * math.sin(angle) + b * math.cos(angle)))


def element_radius(element: str) -> float:
    """gemmi's covalent radius (Å) — the bond cutoff's and the ball's scale."""
    return float(gemmi.Element(element).covalent_r)


def is_metal(element: str) -> bool:
    """gemmi's metal flag — the one chemical distinction the bond rule needs."""
    return bool(gemmi.Element(element).is_metal)


def bonds_between_metals(elements) -> bool:
    """Whether metal–metal contacts should be drawn as bonds in this phase.

    A pure radius-sum rule draws the wrong picture at both ends of chemistry,
    and the failure is not subtle: gemmi's covalent radius for lanthanum is
    2.07 Å, so in LaB6 (a = 4.158 Å) *every cell edge* becomes an La–La stick
    and the boron framework disappears into a cage.

    The distinction that fixes it is chemical rather than geometric — in a
    structure that contains a non-metal, a metal–metal contact is a lattice
    distance and not a bond, while in one that does not (an alloy, an
    elemental metal) it is the only bond there is.  So the rule is: bond metals
    to metals **only when the phase has no non-metal in it**.  Stated as a
    predicate over the phase rather than a per-pair exception, because that is
    what makes it answerable — and derived from the composition, so an
    intermetallic never has to be special-cased by hand.
    """
    return all(is_metal(element) for element in elements)


def is_ligand(center: str, element: str) -> bool:
    """Whether an atom of ``element`` can sit at a vertex of ``center``'s polyhedron.

    The element half of WP-1466's P2: a ligand is a non-metal of another
    element, other than hydrogen.  The site half is :func:`_cation_sites`,
    since whether P or Si is a cation depends on what it is bonded to.  It is
    Mercury's ligand list derived rather than declared.  The radius-sum bond
    rule reaches metals too: fluorapatite's P has 4 Ca at 3.1-3.2 Å beside
    its 4 O.  Hydrogen is excluded because a hydroxide's cation reaches it
    next: counting it drops brucite's Mg gap ratio from 1.80 to 1.28.
    """
    info = gemmi.Element(element)
    # ``X``, a species no grammar resolved, is no element and so no ligand
    return (element != center and info.atomic_number > 0 and not info.is_metal
            and not info.is_hydrogen)


def element_list(values: Sequence[str], what: str = "elements") -> list[str]:
    """``values`` as sorted, unique element symbols, or ``ValueError`` naming
    the one that is none.  A charge is dropped, as :func:`element_symbol` drops
    it, so ``"O2-"`` asks for O."""
    out = set()
    for value in values:
        symbol = element_symbol(str(value))
        if symbol == "X":
            raise ValueError(f"{what}: {value!r} names no element")
        out.add(symbol)
    return sorted(out)


#: Pauling electronegativities of gemmi's non-metals, for the one question the
#: polyhedra ask of them: which of two bonded non-metals is the cation.  An
#: element with no value (He, Ne, Ar, Rn, Ts, Og) is never the more
#: electronegative of a pair.  Fourteen are Allred's (1961, J. Inorg. Nucl.
#: Chem. 17, 215, Table 3), checked against it.  His table has none for Te,
#: At, Kr or Xe.  Theirs agree with the Pauling-scale table of the CRC
#: Handbook (84th ed., 2003, § 9), which cites Pauling (1960, The Nature of
#: the Chemical Bond, 3rd ed.) and Allen (1989, J. Am. Chem. Soc. 111, 9003),
#: and with WebElements and Lange's Handbook (15th ed., 1999, Table 4.5).
#: That check is second-hand: all three as quoted on Wikipedia's
#: "Electronegativities of the elements (data page)", read 2026-10-03; no
#: handbook was opened.  Te needs one: without it a tellurate's Te would be an
#: anion, and a ligand of the metals beside it.  Deuterium needs no row:
#: :func:`element_symbol` reads ``D`` as hydrogen, so a neutron structure draws
#: as its protonated twin does.
ELECTRONEGATIVITY: dict[str, float] = {
    "H": 2.20, "B": 2.04, "C": 2.55, "N": 3.04, "O": 3.44, "F": 3.98, "Si": 1.90,
    "P": 2.19, "S": 2.58, "Cl": 3.16, "As": 2.18, "Se": 2.55, "Br": 2.96, "Kr": 3.00,
    "Te": 2.10, "I": 2.66, "Xe": 2.60, "At": 2.20,
}


def _cation_sites(sites: list[dict], orbit: dict[str, Any], basis: np.ndarray,
                  codes: tuple[np.ndarray, ...] | None = None) -> set[int]:
    """The sites whose atoms are cations: every metal, and every non-metal bonded
    to a more electronegative non-metal, as P is in PO₄ and Si in SiO₄.

    Only a cation is a centre, and a cation is never a ligand (WP-1466, P2).
    That is CrystalNN's "no cation–cation bonds" (Pan et al., 2021, Inorg.
    Chem., doi:10.1021/acs.inorgchem.0c02996) carried from the metals to the
    non-metals.  Counted as ligands, forsterite's Si at 2.69 Å cut Mg's gap to
    1.26 and grossular's Ca took 2 Si into a shell of 10.  Counted as
    centres, gypsum's water O drew five S and andalusite's OA four Si.

    A **donor** is the exception (WP-1468): a non-metal whose stronger
    partners are one atom, and which a metal is bonded to, is that metal's
    ligand.  A cyanide's or a carbonyl's C is one.  As a cation it had made
    Cu₃[Co(CN)₆]₂ (COD 4002391) draw CoN₆ from the N at 3.03 Å, past the C at
    1.89.  An oxyanion's centre has three or four stronger partners, so a
    metal bonded to it keeps it a cation: fluorapatite's P has 4 Ca inside
    the bond cutoff.  Partners closer than :data:`BOND_MIN` to each other are
    one atom split, as Prussian blue's N and water O are, 0.10 Å apart.
    Its known miss is a nitro group, whose N has two O.  ``codes`` is
    :func:`_disorder_codes`', and a partner that is an alternative of the site
    is not one.

    Bonded is the viewer's radius-sum rule at :data:`BOND_TOLERANCE`, the
    default rather than the query's, so the polyhedra do not move with the
    bond slider.  A partner closer than :data:`SPLIT_FLOOR` of the radius sum
    is a split site and no bond: hydroxyfluorapatite's OH oxygen, 0.48 Å from
    a half-occupied F, had made itself a cation and left every Ca shell.
    ``orbit`` is :func:`_orbit`'s.
    """
    cations = {j for j, site in enumerate(sites) if site["metal"]}
    elements, owner, source = orbit["elements"], orbit["owner"], orbit["source"]
    # per orbit atom, then read through ``source``: never a string per image
    radius = np.array([element_radius(e) for e in elements], dtype=np.float64)
    strength = np.array([ELECTRONEGATIVITY.get(e, 0.0) for e in elements],
                        dtype=np.float64)
    metal = np.array([is_metal(e) for e in elements], dtype=bool)[source]
    # each row's ``(site, turn)``, for the file's disorder groups
    them = (None if codes is None
            else np.stack([np.asarray(owner)[source], orbit["turn"][source]], axis=-1))
    for j, site in enumerate(sites):
        mine = ELECTRONEGATIVITY.get(site["element"])
        if j in cations or mine is None or j not in owner:
            continue
        rows = (strength > mine)[source]
        if codes is not None:
            # a partner the file's disorder groups keep from this site is none
            me = np.array([j, orbit["turn"][owner.index(j)]])
            rows &= ~_apart(codes, me, them)
        if not rows.any():
            continue
        here = orbit["frac"][owner.index(j)] @ basis.T
        reach = np.linalg.norm(orbit["cart"][rows] - here, axis=1)
        # both are non-metals, so a split partner is no bond (P10)
        partners = orbit["cart"][rows][bonded(reach, site["radius"] + radius[source[rows]],
                                              nonmetals=True)]
        if not len(partners):
            continue
        # a donor atom: its stronger partners are one atom, perhaps split, and a
        # metal is bonded to it, as cyanide's C is to Fe (WP-1468)
        if (np.linalg.norm(partners - partners[0], axis=1) < BOND_MIN).all():
            near = np.linalg.norm(orbit["cart"][metal] - here, axis=1)
            if bonded(near, site["radius"] + radius[source[metal]], nonmetals=False).any():
                continue
        cations.add(j)
    return cations


def bonded(distance, radius_sum, nonmetals, tolerance: float = BOND_TOLERANCE) -> np.ndarray:
    """Whether two atoms ``distance`` Å apart are bonded, by the viewer's one test.

    Bonded is ``distance ≤ tolerance·radius_sum`` on gemmi's covalent radii,
    and at least :func:`split_floor`, below which two atoms are one split over
    two positions (P10).  The sticks (:func:`_bonds`) and the cation test
    (:func:`_cation_sites`) both ask here, so a change to either bound
    reaches both.  Which *pairs* may bond at all is chemistry, and
    :func:`_bonds` decides it.  Every argument broadcasts.
    """
    radius_sum = np.asarray(radius_sum, dtype=np.float64)
    return ((distance >= split_floor(radius_sum, nonmetals))
            & (distance <= float(tolerance) * radius_sum))


def split_floor(radius_sum, nonmetals) -> np.ndarray:
    """The distance under which two atoms are one split over two positions:
    :data:`SPLIT_FLOOR` of the radius sum between two non-metals,
    :data:`METAL_SPLIT_FLOOR` of it with a metal, and never under
    :data:`BOND_MIN`.  The sticks and the shells both read it."""
    radius_sum = np.asarray(radius_sum, dtype=np.float64)
    fraction = np.where(nonmetals, SPLIT_FLOOR, METAL_SPLIT_FLOOR)
    return np.maximum(fraction * radius_sum, BOND_MIN)


def shell_gap(distances: np.ndarray) -> tuple[int, float]:
    """``(n, ratio)``: the shell ends after ``n`` ligands, at a gap of ``ratio``.

    The largest gap in the sorted distances, as Daams & Villars (1993) apply
    Brunner & Schwarzenbach (1971, Z. Kristallogr. 133, 127).  A gap is judged
    by the quotient of the two distances bounding it, as they judge it.  The
    caller sets the window (:data:`SHELL_REACH`).  One ligand or none gives
    ``(len, 1.0)``, a shell with no gap.
    """
    d = np.asarray(distances, dtype=np.float64)
    if len(d) < 2:
        return len(d), 1.0
    ratios = d[1:] / d[:-1]
    n = int(np.argmax(ratios)) + 1
    return n, float(ratios[n - 1])


def rival_gap(distances: np.ndarray, n: int) -> tuple[int, float] | None:
    """``(n2, ratio)``: the largest gap other than the one after ``n``, when it
    rivals it (:data:`RIVAL_GAP`) and would close a polyhedron of its own, else
    ``None`` (WP-1468).

    Would close one means P4's size and gap: four ligands or more and a ratio of
    :data:`POLYHEDRON_GAP` or more.  Daams & Villars (1993) broke a tie between
    "equal or practically equal maximum gaps" by keeping a structure type's
    number of environment types small.  That is a hand rule, for intermetallic
    structure types, with no number for "practically"; the rival is reported
    beside the shell instead.  Real ones: COD 1509685's Ag2 closes after 6 at
    1.166 against 1.152 after 4, and a hollandite's Ba (1525610) after 8 at
    1.225 against 1.220 after 12.
    """
    d = np.asarray(distances, dtype=np.float64)
    if len(d) < 3:
        return None
    ratios = d[1:] / d[:-1]
    largest = float(ratios[n - 1])
    ratios[n - 1] = 0.0
    k = int(np.argmax(ratios))
    if (k + 1 < 4 or ratios[k] < POLYHEDRON_GAP
            or math.log(ratios[k]) < RIVAL_GAP * math.log(largest)):
        return None
    return k + 1, float(ratios[k])


def probability_scale(probability: float) -> float:
    """``k(p) = √χ²₃(p)`` — the ellipsoid's semi-axis scale at probability ``p``.

    50 % is 1.5382 and 90 % is 2.5003, the numbers ORTEP prints.  scipy is a
    core dependency, so this is a lookup rather than a table of magic constants
    that would have to be checked by hand.
    """
    from scipy.stats import chi2

    p = float(probability)
    if not 0.0 < p < 1.0:
        raise ValueError(f"probability must be in (0, 1), not {probability!r}")
    return float(math.sqrt(chi2.ppf(p, 3)))


# ----------------------------------------------------------------------
# the payload
# ----------------------------------------------------------------------
def build(structure, phase: int = 0, *, probability: float = DEFAULT_PROBABILITY,
          bond_tolerance: float = BOND_TOLERANCE,
          max_atoms: int = MAX_ATOMS, disorder: str = "all",
          centres: Sequence[str] | None = None,
          ligands: Sequence[str] | None = None,
          extent: Sequence[Sequence[int]] | None = None) -> dict[str, Any]:
    """Drawable geometry for one phase of ``structure``.

    The returned dict is the wire format of ``GET /api/structure3d``; its shape
    is documented field by field in the sections below, and every coordinate in
    it is **Cartesian in Å** unless the name says ``frac``.  ``disorder`` is
    one of :data:`DISORDER_VIEWS`; ``"major"`` draws no image of a site
    :func:`minor_sites` names.  The payload lists those in ``minor_sites``
    in either view, so a client knows whether there is a choice to offer.

    ``centres`` and ``ligands`` are Mercury's two lists (WP-1468): element
    symbols that replace the chemistry's choice of which atoms a polyhedron
    is drawn round and which sit at its corners.  ``None`` keeps the rule
    (:func:`_cation_sites`, :func:`is_ligand`).  A list may name a metal as a
    ligand or an anion as a centre, which is how an intermetallic's
    environments and an anion-centred OCa₄ are asked for.  The payload
    echoes both and lists the elements in use as ``centre_elements`` and
    ``ligand_elements``.

    ``extent`` is ``((a0, a1), (b0, b1), (c0, c1))``, the block of whole cells
    to draw as a half-open box in cell units (WP-1502); ``None`` is the one
    cell, ``((0, 1),) * 3``.  Every atom carries ``image`` = ``[orbit index,
    [n1, n2, n3]]``, which atom of the cell it is and by which lattice
    translation it is moved, so two images of one atom are told apart from two
    atoms.  The cell is built once and the block is that result translated,
    matched by image, so the cost grows with the atoms drawn.  The block holds
    each atom once, the atoms on its lower faces again on the opposite ones (the
    cell's own rule), every bond of an atom in it, and every polyhedron whose
    centre is in it, whole.  ``max_atoms`` then bounds the block and raises
    past it, as a block cannot be trimmed without cutting bonds.

    The one cell is trimmed instead, since ``max_atoms``' default of
    :data:`MAX_ATOMS` serves the GUI's viewer.  The cell's images past the cap
    are left out, and so are the bonded neighbours and polyhedron ligands that
    would take the drawing past it, whose bonds then end in mid-air.  ``cut``
    counts each loss: ``atoms`` the cell's images left out, ``neighbours`` the
    bonded neighbours outside the cell left out, ``segments`` the bond
    segments past :data:`MAX_BONDS`, and ``polyhedra`` the polyhedra
    ``polyhedra_dropped`` lists.  ``note`` says the same in words.
    ``rietx.viz.render_structure`` never draws a trimmed cell from a
    structure: it raises past its own ``max_atoms``, as the block does.
    """
    box = _extent(extent)
    if box != DEFAULT_EXTENT:
        started = time.perf_counter()
        home = build(structure, phase, probability=probability, bond_tolerance=bond_tolerance,
                     max_atoms=_UNCAPPED, disorder=disorder, centres=centres, ligands=ligands)
        return _tile(home, box, max_atoms, started)
    if disorder not in DISORDER_VIEWS:
        raise ValueError(f"disorder must be one of {', '.join(DISORDER_VIEWS)}, "
                         f"not {disorder!r}")
    centres = None if centres is None else element_list(centres, "centres")
    ligands = None if ligands is None else element_list(ligands, "ligands")
    phases = list(structure.phases)
    if not phases:
        # Phrased for the state, not for a bad index: a pattern-only project
        # has no phase *yet* (WP-1207), which is a different thing from asking
        # for phase 7 of a three-phase model, and the client hides the viewer
        # on it rather than reporting an error.
        raise IndexError("this project has no phase to draw yet — index the "
                         "pattern and adopt a cell, or add a phase")
    if not 0 <= phase < len(phases):
        raise IndexError(f"no phase {phase} (this structure has {len(phases)})")
    ph = phases[phase]
    cell = ph.cell.lengths_angles()
    basis = cartesian_basis(*cell)            # lattice vectors as columns, Å
    astar = reciprocal_axis_lengths(*cell)
    # ``resolve_group``, not ``get_spacegroup``: a phase whose group no
    # Hermann-Mauguin symbol names in its cell carries a bracketed *label*
    # here and its operations in ``symmetry_operations``, and handing the
    # label to gemmi raises "Unknown space-group name" out of a viewer
    # endpoint (M-3 item 5b).  ``OperatorGroup`` carries the same
    # ``operations()``/``xhm()`` surface the two readers below use.
    sg = resolve_group(ph.space_group, ph.symmetry_operations)

    minor = minor_sites(ph)
    left_out = minor if disorder == "major" else set()
    sites, atoms, notes, every = _expand(ph, phase, sg, basis, astar, max_atoms, left_out)
    n_cell = len(atoms)
    # what the caps leave out, as numbers beside the words in ``note``: the
    # figure's report reads these and never parses ``note`` (#665)
    cut = {"atoms": len(every) - n_cell, "neighbours": 0, "segments": 0, "polyhedra": 0}
    # the colours are decided *here*, over the phase's own element list, because
    # two of them being the same colour is a fact about this picture and not
    # about the element table (WP-1029)
    palette = phase_palette([s["element"] for s in sites])
    for site in sites:
        site["color"] = palette[site["element"]]
    positions = np.array([a["pos"] for a in atoms], dtype=np.float64).reshape(-1, 3)
    radii = np.array([sites[a["site"]]["radius"] for a in atoms], dtype=np.float64)
    metal = np.array([sites[a["site"]]["metal"] for a in atoms], dtype=bool)
    alloy = bonds_between_metals(s["element"] for s in sites)
    orbit = _orbit(sites, every, basis)
    codes = _disorder_codes(sites)
    cations = _cation_sites(sites, orbit, basis, codes)
    cation = np.array([a["site"] in cations for a in atoms], dtype=bool)
    occupancy = np.array([sites[a["site"]]["occ"] for a in atoms], dtype=np.float64)
    held = np.array([[a["site"], a["_turn"]] for a in atoms], dtype=int).reshape(-1, 2)
    apart = None if codes is None else _apart(codes, held[:, None, :], held[None, :, :])
    bonds = _bonds(positions, radii, basis, bond_tolerance,
                   None if alloy else metal, cation, occupancy, apart)
    if len(bonds) > MAX_BONDS:
        notes.append(f"{len(bonds)} bond segments trimmed to {MAX_BONDS}; lower "
                     "the bond tolerance to see a picture rather than a cage")
        cut["segments"] = len(bonds) - MAX_BONDS
        bonds = bonds[:MAX_BONDS]
    partners = _partners(atoms, bonds, basis)
    room = max(max_atoms - len(atoms), 0)
    if len(partners) > room:
        notes.append(f"{len(partners) - room} bonded neighbour(s) outside the cell "
                     "are not drawn; their bonds end in mid-air")
        cut["neighbours"] = len(partners) - room
        partners = partners[:room]
    atoms.extend(partners)
    polyhedra, corners, dropped = _polyhedra(sites, orbit, cations, atoms, n_cell, bonds,
                                             basis, max(max_atoms - len(atoms), 0), codes,
                                             centres, ligands)
    if dropped:
        notes.append(f"{len(dropped)} coordination polyhedra not drawn: their ligands "
                     f"would take the drawing past {max_atoms} atoms")
        cut["polyhedra"] = len(dropped)
    atoms.extend(corners)
    _flag_outside_centres(atoms, n_cell, bonds, polyhedra)

    corners = _corners(basis)
    orbit_frac = orbit["frac"]
    return {
        "phase": phase,
        "phases": [p.name for p in phases],
        "name": ph.name,
        "space_group": sg.xhm(),
        "cell": list(cell),
        "volume": float(abs(np.linalg.det(basis))),
        "lattice": basis.T.tolist(),          # rows a, b, c as Cartesian vectors
        "corners": corners.tolist(),
        "extent": [list(b) for b in DEFAULT_EXTENT],
        # twelve index pairs into ``corners``, so "12 edges" is a fact of the
        # payload and not of whichever line convention the renderer happens to use
        "edges": _EDGES,
        "sites": sites,
        # an image's symmetry operation is the server's own business (it says
        # which images of a negative disorder group coexist), so it stays here
        "atoms": [{**{k: v for k, v in a.items() if k not in _PRIVATE},
                   "image": _image(a, orbit_frac)} for a in atoms],
        # the first ``n_cell`` atoms are the block's own images and their
        # boundary duplicates, the only ones a polyhedron is centred on
        "n_cell": n_cell,
        "bonds": bonds,
        # vertices, bonds and the centre are indices into ``atoms`` and
        # ``bonds``; faces and edges index the polyhedron's own vertices
        "polyhedra": polyhedra,
        # the polyhedra the atom cap turned away, each its centre's site and
        # its ligands' elements, so the legend can name what it cannot draw
        "polyhedra_dropped": dropped,
        "probability": float(probability),
        "probability_levels": {f"{p:g}": probability_scale(p)
                               for p in PROBABILITY_LEVELS},
        "scale": probability_scale(probability),
        "ball_fraction": BALL_FRACTION,
        "bond_tolerance": float(bond_tolerance),
        "bond_metals": alloy,
        "disorder": disorder,
        # the sites ``disorder="major"`` draws no image of, in either view
        "minor_sites": sorted(minor),
        # the two lists as asked for (``None`` is the chemistry's), and the
        # elements in use either way
        "centres": centres,
        "ligands": ligands,
        "centre_elements": (sorted({sites[j]["element"] for j in cations - left_out})
                            if centres is None else centres),
        "ligand_elements": (sorted({s["element"] for j, s in enumerate(sites)
                                    if j not in cations and j not in left_out
                                    and is_ligand("", s["element"])})
                            if ligands is None else ligands),
        # the cell's images, bond segments and polyhedra the caps left out;
        # ``rietx.viz.keep`` adds what it cuts to the same counts
        "cut": cut,
        "note": " · ".join(notes),
    }


#: The twelve edges of a parallelepiped, as index pairs into the eight corners
#: ``_corners`` emits (in binary order over the a, b, c coefficients).
_EDGES: list[list[int]] = [[i, i ^ bit] for bit in (1, 2, 4)
                           for i in range(8) if not i & bit]


def _corners(basis: np.ndarray, box=DEFAULT_EXTENT) -> np.ndarray:
    """The eight corners of ``box`` in Cartesian Å, in binary (a, b, c) order."""
    lo = np.array([b[0] for b in box], dtype=np.float64)
    span = np.array([b[1] - b[0] for b in box], dtype=np.float64)
    frac = np.array([[(i >> 0) & 1, (i >> 1) & 1, (i >> 2) & 1] for i in range(8)],
                    dtype=np.float64)
    return (lo + frac * span) @ basis.T


#: A cap no phase reaches, for the cell an extent is built from.
_UNCAPPED = 1 << 40


def _extent(extent) -> tuple[tuple[int, int], ...]:
    """``extent`` as three ``(lo, hi)`` whole-cell pairs, or a ``ValueError``."""
    if extent is None:
        return DEFAULT_EXTENT
    try:
        pairs = [tuple(pair) for pair in extent]
        ok = len(pairs) == 3 and all(len(pair) == 2 for pair in pairs)
        ok = ok and all(isinstance(v, (int, np.integer)) and not isinstance(v, bool)
                        for pair in pairs for v in pair)
    except TypeError:
        ok = False
    if not ok:
        raise ValueError(f"extent {extent!r}: three (low, high) pairs of whole cells, "
                         "as ((0, 2), (0, 2), (0, 1))")
    box = tuple((int(lo), int(hi)) for lo, hi in pairs)
    if any(hi <= lo for lo, hi in box):
        raise ValueError(f"extent {extent!r}: each pair needs high above low; the box "
                         "is half-open, so (0, 1) is the one cell")
    return box


def _image(atom: dict, orbit_frac: np.ndarray) -> list:
    """``[orbit index, [n1, n2, n3]]``: which atom of the cell ``atom`` is an image
    of, and the lattice translation that moved it."""
    o = atom["_orbit"]
    n = np.rint(np.asarray(atom["frac"], dtype=np.float64) - orbit_frac[o]).astype(int)
    return [int(o), n.tolist()]


def _tile(home: dict, box: tuple, max_atoms: int, started: float) -> dict:
    """``home``, the one cell's geometry, instantiated over the cells of ``box``.

    Every atom is found by its image ``(orbit index, n)``, which is exact where
    a position needs rounding, so the block is a translation of the cell's
    bond search and is never searched again (WP-1502).  The cell's atoms and
    their boundary duplicates, translated over the cells and taken once each,
    are the block's own (the cell's rule, as it reads on a face of the block);
    every bond of one of them is the cell's bond translated, taken once; a
    bond's far end outside them is a neighbour drawn as :func:`_partners` does,
    and a polyhedron is its centre's in the cell, translated, with the ligands
    no stick reached added as :func:`_polyhedra` does.
    """
    atoms = home["atoms"]
    basis = np.asarray(home["lattice"], dtype=np.float64).T
    inverse = np.linalg.inv(basis)
    n_cell = home["n_cell"]
    shift = np.array([[a["image"][1]] for a in atoms], dtype=np.int64).reshape(-1, 3)
    orbit_of = [a["image"][0] for a in atoms]
    frac_of: dict[int, np.ndarray] = {}
    template: dict[int, dict] = {}
    for a, n, o in zip(atoms, shift, orbit_of):
        if o not in frac_of:
            frac_of[o] = np.asarray(a["frac"], dtype=np.float64) - n
            template[o] = a
    real = [a for a in range(n_cell) if not atoms[a]["boundary"]]
    copies = [a for a in range(n_cell) if atoms[a]["boundary"]]
    # the block holds at least one image of every atom per cell, so the cap is
    # known before any cell is built, and a large extent raises at once
    n_cells = math.prod(hi - lo for lo, hi in box)
    if n_cells * len(real) > max_atoms:
        raise ValueError(f"extent {box}: at least {n_cells * len(real)} atoms in the block, "
                         f"past max_atoms={max_atoms}; pass a larger max_atoms")
    cells = np.stack(np.meshgrid(*[np.arange(lo, hi) for lo, hi in box], indexing="ij"),
                     axis=-1).reshape(-1, 3)
    out: list[dict] = []
    at: dict[tuple, int] = {}

    def place(o: int, n: np.ndarray, *, boundary: bool, vertex_only: bool = False) -> int:
        key = (o, *(int(v) for v in n))
        if key not in at:
            frac = frac_of[o] + n
            at[key] = len(out)
            out.append({**template[o], "frac": frac.tolist(), "pos": (basis @ frac).tolist(),
                        "boundary": boundary, "vertex_only": vertex_only,
                        "image": [o, [int(v) for v in n]]})
        return at[key]

    for t in cells:
        for a in real:
            place(orbit_of[a], t + shift[a], boundary=False)
    for t in cells:
        for a in copies:
            place(orbit_of[a], t + shift[a], boundary=True)
    if len(out) > max_atoms:
        raise ValueError(f"extent {box}: {len(out)} atoms in the block, past max_atoms="
                         f"{max_atoms}; pass a larger max_atoms")
    n_block = len(out)

    def far(bond: dict) -> tuple[int, np.ndarray]:
        o = orbit_of[bond["j"]]
        return o, np.rint(inverse @ np.asarray(bond["b"]) - frac_of[o]).astype(np.int64)

    bonds: list[dict] = []
    seen: dict[tuple, int] = {}
    bond_at = np.empty((len(cells), len(home["bonds"])), dtype=np.int64)
    ends = [(orbit_of[b["i"]], shift[b["i"]], *far(b)) for b in home["bonds"]]
    for c, t in enumerate(cells):
        for k, (bond, (o, n, p, m)) in enumerate(zip(home["bonds"], ends)):
            one = (o, *(int(v) for v in n + t))
            two = (p, *(int(v) for v in m + t))
            key = (one, two) if one <= two else (two, one)
            if key not in seen:
                seen[key] = len(bonds)
                i = at[one]
                j = place(p, m + t, boundary=True)
                bonds.append({**bond, "i": i, "j": j, "a": out[i]["pos"], "b": out[j]["pos"]})
            bond_at[c, k] = seen[key]
    polyhedra: list[dict] = []
    centred: set[tuple] = set()
    for c, t in enumerate(cells):
        for poly in home["polyhedra"]:
            centre = (orbit_of[poly["center"]], *(int(v) for v in shift[poly["center"]] + t))
            if centre in centred:
                continue
            centred.add(centre)
            vertices = [place(orbit_of[v], shift[v] + t, boundary=True, vertex_only=True)
                        for v in poly["vertices"]]
            polyhedra.append({**poly, "center": at[centre], "vertices": vertices,
                              "bonds": [int(bond_at[c, k]) for k in poly["bonds"]]})
    polyhedra.sort(key=lambda p: p["center"])
    _flag_outside_centres(out, n_block, bonds, polyhedra)
    label = "×".join(str(hi - lo) for lo, hi in box)
    note = f"extent {label} · {len(out)} atoms · built in {1e3 * (time.perf_counter() - started):.0f} ms"
    return {**home, "atoms": out, "bonds": bonds, "polyhedra": polyhedra, "polyhedra_dropped": [],
            "n_cell": n_block, "extent": [list(b) for b in box],
            "corners": _corners(basis, box).tolist(),
            "note": " · ".join(x for x in (home["note"], note) if x)}


def _expand(ph, phase: int, sg, basis: np.ndarray, astar: np.ndarray,
            max_atoms: int, left_out: set[int] = frozenset(),
            ) -> tuple[list[dict], list[dict], list[str], list[dict]]:
    """The asymmetric unit → per-site records and every drawn image of each.

    Two kinds of image are drawn and the payload distinguishes them, because
    only one of them counts: a **symmetry** image is a member of the orbit, so
    the number of non-``boundary`` atoms on a site *is* its multiplicity, while
    a **boundary** duplicate is the same atom seen at the opposite face and is
    there so a corner atom appears at all eight corners.  Each image carries the
    number of the rotation that made it under ``_turn``, which :func:`build`
    keeps off the wire.  :func:`_partners` adds
    a third kind under the same flag — a bonded neighbour just outside the cell —
    for the same reason: it is an image, not a cell member.  :func:`_polyhedra`
    adds a fourth, a ligand no stick reached, flagged ``vertex_only`` as well,
    and the client draws it only while one of its polyhedra is drawn.

    The last item returned is every image before the ``max_atoms`` trim, since
    a polyhedron's ligands are searched over the whole orbit.  A site in
    ``left_out`` keeps its record, so every index into ``sites`` is still its
    atom's, and draws no image.
    """
    sites: list[dict] = []
    atoms: list[dict] = []
    notes: list[str] = []
    # each image's rotation, numbered: an image of a site and an image of
    # another share one when one operation made both (WP-1468)
    turns: dict[tuple, int] = {}
    # which atom of the cell an image is, counting the ones no boundary rule made
    n_orbit = 0
    for j, atom in enumerate(ph.atoms):
        element = element_symbol(atom.species)
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value], dtype=np.float64)
        orbit = expand_orbit(sg, xyz)
        uiso = atom.biso.value / (8.0 * math.pi ** 2)
        ustar = (None if atom.aniso is None
                 else ustar_from_ucif(np.asarray(atom.aniso.values()), astar))
        site = {
            "index": j,
            # the atom's own dot-path, so a click here reaches the row the
            # parameter table already owns rather than a second identity for it
            "path": f"phases.{phase}.atoms.{j}",
            "label": atom.label,
            "species": atom.species,
            "element": element,
            # replaced by `phase_palette` once every site is known — the colour
            # depends on what else is in the phase, which this loop cannot say
            "color": element_color(element),
            "radius": element_radius(element),
            "metal": is_metal(element),
            "occ": float(atom.occ.value),
            "biso": float(atom.biso.value),
            "u_iso": float(uiso),
            "aniso": atom.aniso is not None,
            "multiplicity": len(orbit),
            "special": len(orbit) < len(sg.operations()),
            "npd": False,
            "disorder_assembly": atom.disorder_assembly,
            "disorder_group": atom.disorder_group,
        }
        sites.append(site)
        if j in left_out:
            continue
        for frac, rot in orbit:
            turn = turns.setdefault(tuple(int(v) for v in np.rint(rot).ravel()), len(turns))
            transform, rms, npd = _ellipsoid(ustar, uiso, rot, basis)
            site["npd"] = site["npd"] or npd
            for shift in _boundary_shifts(frac):
                image = frac + shift
                n_orbit += not shift.any()
                atoms.append({
                    "site": j,
                    "frac": image.tolist(),
                    "pos": (basis @ image).tolist(),
                    "boundary": bool(shift.any()),
                    "vertex_only": False,
                    "ellipsoid": transform.tolist(),
                    "rms": rms.tolist(),
                    "npd": npd,
                    "_turn": turn,
                    "_orbit": n_orbit - 1,
                })
    every = atoms
    if len(atoms) > max_atoms:
        notes.append(f"{len(atoms)} drawn atoms trimmed to {max_atoms}; "
                     "the cell is larger than this viewer draws")
        atoms = atoms[:max_atoms]
    if any(s["npd"] for s in sites):
        notes.append("a displacement tensor is not positive definite — its "
                     "non-positive axes are drawn at zero, so that ellipsoid is "
                     "flat by construction")
    return sites, atoms, notes, every


def _partners(atoms: list[dict], bonds: list[dict], basis: np.ndarray) -> list[dict]:
    """The atoms a bond leaves the cell to reach, so no stick ends on nothing.

    Found by looking at the picture rather than at the payload: a bond drawn to
    a translated image is *correct* and reads as broken, because the eye sees a
    stick going into empty space.  So each out-of-cell endpoint gets its atom
    drawn — flagged ``boundary``, since it is an image and not a cell member, so
    the multiplicity count is untouched.

    Exactly **one** level, and that is a stopping rule rather than an omission:
    completing the added atoms' own bonds would complete theirs in turn, which
    is a packing diagram (this WP's explicit non-goal).  What one level buys is
    the property that matters — every atom of the cell shows its full
    coordination.  A partner that would be a polyhedron's centre is drawn
    only while its polyhedra are hidden, as VESTA's default search would not
    add it (:func:`_flag_outside_centres`, WP-1529).
    """
    known = set(_keys([a["pos"] for a in atoms]))
    inverse = np.linalg.inv(basis)
    out: list[dict] = []
    for bond, key in zip(bonds, _keys([b["b"] for b in bonds])):
        if key in known:
            continue
        known.add(key)
        source = atoms[bond["j"]]
        # a lattice translation moves an atom and leaves its tensor alone, so
        # the image carries the source's ellipsoid unchanged; the fractional
        # coordinate is recovered rather than left blank, because it is what
        # says *which* image the hover is over (−0.20 rather than 0.80)
        out.append({**source, "pos": list(bond["b"]), "boundary": True,
                    "frac": (inverse @ np.asarray(bond["b"])).tolist()})
    return out


def _flag_outside_centres(atoms: list[dict], n_cell: int, bonds: list[dict],
                          polyhedra: list[dict]) -> None:
    """Flag ``outside_centre`` on every atom and bond, in place.

    An outside centre is an atom past the first ``n_cell`` whose site centres a
    polyhedron in this drawing and which is no polyhedron's vertex: a bond from
    a ligand reached it, and a polyhedron is centred only on the first
    ``n_cell`` atoms, so it carries none.  Rutile drew 2 Ti that way,
    fluorapatite 4 P and calcite 8 Ca, and an agent reading "the polyhedra
    are whole" saw a centre without one (WP-1529).  VESTA's default bond search adds a ligand
    outside the boundary but never a centre: "A1 atoms lying outside the
    boundary are never searched" (Momma & Izumi, VESTA manual § 8.2.1).  So
    the client draws such an atom, and every bond whose far end ``b`` is one,
    only while no drawn polyhedron is centred on its site (``drawnWith``).  The
    atom stays in the payload, since while its shell is hidden the bond to it
    is the ligand's own coordination: NAC's F3 has no other bond while NaF₇
    and CaF₈ are hidden.

    A bond's near end ``a`` is always one of the first ``n_cell``, so only
    ``b`` is read.  :func:`_tile` calls this again on a block, whose atoms and
    bonds are copies carrying the cell's flags, so an interior bond of the
    block would otherwise keep one.
    """
    centring = {atoms[p["center"]]["site"] for p in polyhedra}
    vertices = {v for p in polyhedra for v in p["vertices"]}
    for k, atom in enumerate(atoms):
        atom["outside_centre"] = (k >= n_cell and atom["site"] in centring
                                  and k not in vertices)
    outside = set(_keys([a["pos"] for a in atoms if a["outside_centre"]]))
    for bond, key in zip(bonds, _keys([b["b"] for b in bonds])):
        bond["outside_centre"] = key in outside


def _boundary_shifts(frac: np.ndarray) -> list[np.ndarray]:
    """``[0]`` plus the +1 translations along every axis this atom sits on.

    An atom at x ≈ 0 is also at x = 1: the same atom, drawn twice, which is what
    puts a corner site at all eight corners and a face site at both faces.
    """
    axes = [k for k in range(3) if frac[k] < BOUNDARY_TOL]
    shifts = [np.zeros(3)]
    for mask in range(1, 1 << len(axes)):
        shift = np.zeros(3)
        for bit, axis in enumerate(axes):
            if mask >> bit & 1:
                shift[axis] = 1.0
        shifts.append(shift)
    return shifts


def _ellipsoid(ustar: np.ndarray | None, uiso: float, rot: np.ndarray,
               basis: np.ndarray) -> tuple[np.ndarray, np.ndarray, bool]:
    """``(T, rms, npd)`` for one image: ``pos + k·T·v`` over the unit sphere ``v``.

    ``T = V·diag(√λ)`` from the eigen-decomposition of U_cart, so its columns
    are the principal axes at one RMS displacement and the client's only job is
    a matrix-vector product.  The rotation is the **fractional** R
    (U\\* → R·U\\*·Rᵀ), which is the representation that transforms that way —
    see ``adp.py``.

    Isotropic sites take the closed form rather than the eigen path: U_cart is
    exactly Uiso·I there (module docstring), so ``T = √Uiso·I`` and no symmetry
    image can rotate a sphere.

    ``V`` is pinned by :func:`_pin_axes`, since the client draws a principal
    ellipse round each of T's columns (WP-1462's D6). The site's own tensor is
    pinned, and an image turns that T by its Cartesian rotation M·R·M⁻¹, which
    takes U_cart to the image's. So equivalent atoms wear equivalent rings.
    Pinned image by image, NAC's images drew theirs up to 60° apart.
    """
    if ustar is None:
        rms = np.full(3, math.sqrt(max(uiso, 0.0)))
        return np.diag(rms), rms, False
    u_cart = basis @ ustar @ basis.T
    values, vectors = np.linalg.eigh(u_cart)
    npd = bool(values[0] <= 0.0)
    # √(negative) is NaN and one NaN vertex loses the whole mesh; zero is the
    # honest value — "no positive mean-square displacement along this axis" —
    # and it collapses the ellipsoid visibly instead
    rms = np.sqrt(np.clip(values, 0.0, None))
    turn = basis @ rot @ np.linalg.inv(basis)
    return turn @ (_pin_axes(values, vectors, basis) * rms), rms, npd


def _pin_axes(values: np.ndarray, vectors: np.ndarray, basis: np.ndarray) -> np.ndarray:
    """``vectors`` with each choice ``eigh`` was free to make, made one way.

    Any column's sign is free, and so is any orthonormal basis of a plane of
    equal principal values. Every such choice gives the same U = V·Λ·Vᵀ, so a
    LAPACK build may return any of them. On NAC's Na1, which is uniaxial by
    symmetry, a Mac and an x86 runner drew its free rings as an X and a +
    (WP-1462's gate). ORTEP, PLATON and Jmol draw all three rings wherever
    their solver puts them, and no manual or paper documents a tie-break, so
    this one is ours:

    * each lone axis faces :data:`_FACING`;
    * an equal pair's first axis is the shadow on their plane of the lattice
      vector nearest it (a ties before b before c), and the second completes
      it about the lone axis, so one ring's plane holds that lattice vector;
    * three equal values, a sphere, take a, b and c orthonormalised in turn.
    """
    scale = float(np.abs(values).max())
    lattice = basis / np.linalg.norm(basis, axis=0)
    out = np.array(vectors, dtype=float)
    groups, start = [], 0
    for k in range(1, 4):
        if k == 3 or values[k] - values[k - 1] > DEGENERATE_RTOL * scale:
            groups.append(list(range(start, k)))
            start = k
    for group in groups:
        if len(group) == 1:
            k = group[0]
            out[:, k] *= 1.0 if out[:, k] @ _FACING >= 0.0 else -1.0
    for group in groups:
        if len(group) == 2:
            plane = out[:, group]
            shadows = plane @ (plane.T @ lattice)
            reach = np.linalg.norm(shadows, axis=0)
            first = int(np.argmax(reach >= reach.max() * (1.0 - DEGENERATE_RTOL)))
            (lone,) = set(range(3)) - set(group)
            out[:, group[0]] = shadows[:, first] / reach[first]
            out[:, group[1]] = np.cross(out[:, lone], out[:, group[0]])
        elif len(group) == 3:
            a, b = lattice[:, 0], lattice[:, 1]
            b = b - (b @ a) * a
            b /= np.linalg.norm(b)
            out = np.column_stack([a, b, np.cross(a, b)])
    return out


def _bonds(positions: np.ndarray, radii: np.ndarray, basis: np.ndarray,
           tolerance: float = BOND_TOLERANCE,
           metal: np.ndarray | None = None,
           cation: np.ndarray | None = None,
           occupancy: np.ndarray | None = None,
           apart: np.ndarray | None = None) -> list[dict]:
    """Bond **segments** between drawn atoms, over the 27 nearest translations.

    Segments rather than pairs, and the distinction is the design: a bond that
    leaves the cell is emitted with its far end outside, so an atom shows every
    contact it has instead of only those whose partner happens to be drawn
    inside the box.  The same contact therefore appears twice — once leaving
    each partner — which is what makes both atoms look correctly coordinated.

    Deduplication is therefore on the **endpoints**, not on the atom pair: two
    segments that leave in opposite directions are two different sticks and both
    are wanted, while the same stick reached twice (once as a home-cell pair and
    once as a translation onto that pair's own boundary duplicate) is one.  A
    count of segments is only honest if the second case is collapsed.

    ``metal`` suppresses metal–metal sticks (see :func:`bonds_between_metals`);
    ``None`` draws them, which is the alloy case.  ``cation`` widens that to
    every stick between a metal and a cation (:func:`_cation_sites`), as
    forsterite's 36 Mg–Si sticks at 2.69-2.79 Å and grossular's 90 Ca–Si
    were (WP-1466).  Two cationic non-metals keep their stick, or an organic
    would lose every C–C and C–H bond.  The distance test is :func:`bonded`.

    Two partly occupied non-metals that are one atom split, by P9's test
    (:func:`one_atom`), get no stick (WP-1468).  ``occupancy`` is per atom,
    and ``None`` reads every atom as full.  Nor do two atoms the file's
    disorder groups say are never occupied together (``apart``, per pair,
    from :func:`_apart`).
    """
    n = len(positions)
    if n == 0:
        return []
    reach = radii[:, None] + radii[None, :]
    # ``metal`` is None only for a phase with no non-metal in it
    nonmetals = False if metal is None else ~metal[:, None] & ~metal[None, :]
    allowed = np.ones((n, n), dtype=bool)
    if metal is not None:
        pair = metal[:, None] & (metal if cation is None else cation)[None, :]
        allowed = ~(pair | pair.T)
    if apart is not None:
        allowed &= ~apart
    shifts = np.array([[i - 1, j - 1, k - 1] for i in range(3) for j in range(3)
                       for k in range(3)], dtype=np.float64) @ basis.T
    out: list[dict] = []
    seen: set[tuple] = set()
    near = _keys(positions)
    for shift in shifts:
        home = not shift.any()
        delta = (positions[None, :, :] + shift) - positions[:, None, :]
        dist = np.sqrt((delta ** 2).sum(axis=2))
        hit = allowed & bonded(dist, reach, nonmetals, tolerance)
        if home:
            hit &= np.triu(np.ones_like(hit, dtype=bool), 1)  # each pair once
        rows, cols = np.nonzero(hit)
        far = positions[cols] + shift
        for i, j, b, end in zip(rows, cols, far, _keys(far)):
            key = tuple(sorted((near[i], end)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"i": int(i), "j": int(j), "a": positions[i].tolist(), "b": b.tolist(),
                        "d": float(dist[i, j])})
    if occupancy is None or metal is None:
        return out
    cation = np.zeros(n, dtype=bool) if cation is None else cation
    # every image within one translation, built once for all the bonds
    images = (positions[None, :, :] + shifts[:, None, :]).reshape(-1, 3)
    radius = np.tile(radii, len(shifts))
    nonmetal = ~np.tile(metal, len(shifts))
    return [bond for bond in out if not _split_stick(bond, radii, metal, cation, occupancy,
                                                     images, radius, nonmetal)]


#: Disorder groups that mean an ordered site: the CIF's nulls, and SHELX's
#: PART 0, which SHELXL writes as ``.`` and other programs as ``0``.
ORDERED_GROUPS = frozenset({"", ".", "?", "0"})


def _disorder_codes(sites: list[dict]) -> tuple[np.ndarray, ...] | None:
    """Per site ``(ordered, assembly, group, negative)`` as arrays, or ``None``
    when no site declares a group (WP-1468).

    An absent assembly is the one assembly a file needs no name for (the CIF
    core dictionary), so every site without one shares it.
    """
    groups = [(site.get("disorder_group") or "").strip() for site in sites]
    if all(g in ORDERED_GROUPS for g in groups):
        return None
    assemblies = [(site.get("disorder_assembly") or "").strip() for site in sites]

    def numbered(values: list[str]) -> np.ndarray:
        index: dict[str, int] = {}
        return np.array([index.setdefault(v, len(index)) for v in values], dtype=int)

    return (np.array([g in ORDERED_GROUPS for g in groups]), numbered(assemblies),
            numbered(groups), np.array([g.startswith("-") for g in groups]))


def minor_sites(phase) -> set[int]:
    """The atoms of ``phase`` that ``disorder="major"`` draws no image of.

    Every site in a group of its assembly other than the most occupied one,
    by the mean occupancy of the group's sites; a tie goes to the group the
    file declares first.  A negative group is left alone: its alternatives
    are one site's symmetry copies, and leaving a site out would hide both.
    """
    groups: dict[str, dict[str, list[int]]] = {}
    for j, atom in enumerate(phase.atoms):
        group = (atom.disorder_group or "").strip()
        if group in ORDERED_GROUPS or group.startswith("-"):
            continue
        groups.setdefault((atom.disorder_assembly or "").strip(), {}).setdefault(
            group, []).append(j)
    out: set[int] = set()
    for members in groups.values():
        occupied = {g: float(np.mean([phase.atoms[j].occ.value for j in js]))
                    for g, js in members.items()}
        major = max(members, key=occupied.__getitem__)
        out |= {j for g, js in members.items() if g != major for j in js}
    return out


def _apart(codes: tuple[np.ndarray, ...], one: np.ndarray, two: np.ndarray) -> np.ndarray:
    """Whether two atoms are never occupied together, by the file's disorder
    groups (the CIF core dictionary; WP-1468).

    ``one`` and ``two`` hold ``(site, turn)`` in their last axis and broadcast
    against each other, the turn being the image's rotation (:func:`_expand`).
    Two sites in different groups of one assembly are alternatives.  So are
    two images in one negative group made by different rotations: a minus
    prefix marks a site disordered about a special position, which SHELX
    writes as PART -n and draws no bond to its symmetry copies.  An ordered
    site is an alternative of nothing.
    """
    ordered, assembly, group, negative = codes
    s1, t1, s2, t2 = one[..., 0], one[..., 1], two[..., 0], two[..., 1]
    return (~ordered[s1] & ~ordered[s2] & (assembly[s1] == assembly[s2])
            & ((group[s1] != group[s2]) | (negative[s1] & (t1 != t2))))


def one_atom(apart, near_one, near_two) -> np.ndarray:
    """Whether two partly occupied atoms ``apart`` Å from each other are one
    atom over two positions, given their distances to a neighbour they share.

    P9 (WP-1466): they are when they sit closer to each other than either
    does to that neighbour, so the angle between them there is under 60°.
    The polyhedra ask it of two ligands and their centre, and the sticks of
    two bonded non-metals and any atom a stick could join to both (WP-1468).
    A real three-membered ring meets its apex at 60°.  Measured split pairs
    sit at half that: α-K₂SO₄'s split O (COD 1000049) at 19.6° round K, and
    orientationally disordered NaNO₃'s (COD 8103616, 9007558-9007567) at
    27-32° round Na.  No bound on the distance alone separates them: those
    pairs sit 0.787 and 0.89-0.99 of their radius sum apart, while real bonds
    reach down to N≡N at 0.773.  Every argument broadcasts, and the occupancy
    test is the caller's.
    """
    return np.asarray(apart) < np.minimum(near_one, near_two)


def _split_stick(bond: dict, radii: np.ndarray, metal: np.ndarray, cation: np.ndarray,
                 occupancy: np.ndarray, images: np.ndarray, radius: np.ndarray,
                 nonmetal: np.ndarray) -> bool:
    """Whether ``bond`` joins two positions of one split non-metal
    (:func:`one_atom`), judged over every image within one translation.

    The shared neighbour is bonded to both at :data:`BOND_TOLERANCE`, the
    default rather than the slider's, so a split does not come and go with
    the slider.  It is one a stick could join to both, so a metal shares no
    pair with a cation in it: a partly occupied SO₄ whose S and O a K sits
    beside would otherwise lose its S–O stick at a thin angle round the K.
    Metals are left out of the pair itself, since a split site with a metal
    in it is measured before it is ruled on (WP-1468).  ``images``, ``radius``
    and ``nonmetal`` are every atom under every shift, tiled once by
    :func:`_bonds` for all its bonds.
    """
    i, j = bond["i"], bond["j"]
    if metal[i] or metal[j] or occupancy[i] >= 1.0 - 1e-6 or occupancy[j] >= 1.0 - 1e-6:
        return False
    near_a = np.linalg.norm(images - np.asarray(bond["a"]), axis=1)
    near_b = np.linalg.norm(images - np.asarray(bond["b"]), axis=1)
    shared = ((nonmetal | ~(cation[i] | cation[j]))
              & bonded(near_a, radii[i] + radius, nonmetal)
              & bonded(near_b, radii[j] + radius, nonmetal))
    return bool(one_atom(bond["d"], near_a[shared], near_b[shared]).any())


#: Where the bins of a position key start, as a fraction of their 1e-6 Å step
#: (:func:`_keys`).  It is 2 − φ.  That lies far from every fraction with a
#: small denominator.
_KEY_PHASE = 0.3819660112501051


def _keys(points) -> list[tuple]:
    """Each point's 1e-6 Å bin, the key two drawn positions are matched by.

    The bins start :data:`_KEY_PHASE` of a step off the decimal grid, because
    a CIF's positions lie on that grid.  A short coordinate times a short cell
    length is a short decimal.  LaB6's B is at 0.5 × 4.157597 = 2.0787985 Å,
    and an I of (BA)₂(MA)₂Pb₃I₁₀ at 0.0605 × 51.959 = 3.1435195 Å.  Each lies
    on a half step of 1e-6 Å.  There rounding lets the last bit of the
    arithmetic choose the side.  A bond's far end and the polyhedron vertex at
    that point are two computations of it.  On the I they differ by 4e-15 Å,
    and they had rounded to two keys.  So the polyhedron left that bond off
    its ``bonds``, and the renderer drew it as a stick through the faces.  A
    second atom was also drawn at that corner.  This hit 3 of the cell's 17
    PbI₆ and 4 of LaB6's 8 polyhedra (issue #664).  A position given to nine
    decimals now lies at least 3e-11 Å from an edge.

    Binned as one array rather than point by point, which is the same
    arithmetic at a fraction of the cost (WP-1468).
    """
    bins = np.floor(np.asarray(points, dtype=np.float64).reshape(-1, 3) * 1e6 + _KEY_PHASE)
    return [tuple(row) for row in bins.astype(np.int64).tolist()]


# ----------------------------------------------------------------------
# coordination polyhedra (WP-1466)
# ----------------------------------------------------------------------
def _orbit(sites: list[dict], every: list[dict], basis: np.ndarray,
           radius: float = SHELL_RADIUS) -> dict[str, Any]:
    """Each position of the orbit once, and its images out to ``radius`` Å.

    ``every`` is the untrimmed image list, and its ``boundary`` duplicates are
    the same atoms again, so they are left out.  ``cart`` holds every image
    under every translation that can bring it within the radius of a point
    anywhere in the cell: |Δf_i| ≤ R·|a*_i|, the image in [0, 1) and the
    centre in [0, 1 + :data:`BOUNDARY_TOL`), so a translation of at most
    1 + ⌊R·|a*_i| + tol⌋.  ``source`` maps each row of ``cart`` back to its image.
    """
    orbit = [a for a in every if not a["boundary"]]
    frac = np.array([a["frac"] for a in orbit], dtype=np.float64).reshape(-1, 3)
    reach = np.floor(radius * np.linalg.norm(np.linalg.inv(basis), axis=1)
                     + BOUNDARY_TOL)
    grid = np.stack(np.meshgrid(*[np.arange(-r - 1, r + 2) for r in reach],
                                indexing="ij"), axis=-1).reshape(-1, 3)
    return {
        "atoms": orbit,
        "radius": radius,
        "elements": [sites[a["site"]]["element"] for a in orbit],
        "owner": [a["site"] for a in orbit],
        "turn": np.array([a.get("_turn", 0) for a in orbit], dtype=int),
        "occupancy": np.array([sites[a["site"]]["occ"] for a in orbit], dtype=np.float64),
        "frac": frac,
        "cart": ((frac[None, :, :] + grid[:, None, :]) @ basis.T).reshape(-1, 3),
        "source": np.tile(np.arange(len(orbit)), len(grid)),
    }


def _polyhedra(sites: list[dict], orbit: dict[str, Any], cations: set[int],
               atoms: list[dict], n_cell: int, bonds: list[dict], basis: np.ndarray,
               room: int, codes: tuple[np.ndarray, ...] | None = None,
               centres: Sequence[str] | None = None, ligands: Sequence[str] | None = None,
               ) -> tuple[list[dict], list[dict], list[dict]]:
    """``(polyhedra, partners, dropped)`` for the first ``n_cell`` drawn atoms.

    A centre is a cation and its ligands are anions (:func:`_cation_sites`,
    :func:`is_ligand`).  The ligands are searched over the whole orbit
    (:func:`_orbit`), untrimmed, out to :data:`SHELL_REACH` times the centre's
    shortest ligand distance, and matched by **position**: the server can find
    a contact from a translated copy of the centre, and a shell collected by
    atom index came out short on 6 of 18 Ca in NAC (WP-1462's spike).  The
    orbit is rebuilt once when a window passes its radius.  The shell ends at
    :func:`shell_gap`, and it is drawn only when it is a polyhedron (P4): at
    least four ligands, a gap of :data:`POLYHEDRON_GAP` or more, every ligand
    at a vertex of the convex hull and the centre strictly inside it.  That is
    Daams & Villars' (1993) convex-volume condition, and it turns away a planar
    CO₃.  A shell holding two partly occupied ligands closer to each other than
    to the centre is a split site and is not drawn (P9).  So is one holding
    two sites the file's disorder groups say are never occupied together
    (``codes``, :func:`_disorder_codes`), and neither is a ligand of a centre
    it is an alternative of (WP-1468).

    A non-metal bonded to a non-metal ligand the centre is bonded to, and
    behind it, is screened out before the gap is found (WP-1468).  Behind
    means the angle at that ligand is obtuse, so |MX|² > |MY|² + |XY|², by
    more than rounding: Cu₃Au's Au sits at exactly 90° past a Cu, and noise
    had screened it round some Au and not others.  A cyanide's N, 3.03 Å
    from Co behind its C at 1.89, had closed Co's shell after 12, C₆N₆.  An
    η²-peroxide or a Cp ring is not screened, since its ligands meet the
    centre at acute angles, and metals form no ligand unit to screen with.
    One step only: through LaB6's boron framework every B would screen the
    next.  On the 21 phases it moves two gaps and no shell: pyrite's Fe from
    1.52 to 1.60 and LaB6's La from 1.45 to 1.90.

    ``centres`` and ``ligands`` replace the rule by element (:func:`build`):
    a centre is then any site of a listed element, and a ligand any atom of
    one, metals and the centre's own element included.

    A vertex outside the drawn atoms becomes a partner, flagged ``boundary``
    as :func:`_partners`' are, so no polyhedron is cut off (P7).  It is also
    flagged ``vertex_only``, and the client draws it only while one of its
    polyhedra is drawn: at the default bond tolerance NAC's hidden NaF₇ and
    CaF₈ put 12 F in the picture with no stick and no face.  One whose partners
    would pass ``room`` is not drawn, and the shells drawn by default claim
    the room first.  It is listed in ``dropped`` by its centre's site and its
    ligands' elements, which is what the legend needs to show its formula as
    unavailable (WP-1468).
    """
    from scipy.spatial import ConvexHull, QhullError, cKDTree

    if not orbit["atoms"] or n_cell == 0:
        return [], [], []
    # a centre is a cation and a ligand is an anion (P2), unless the caller's
    # lists say otherwise (WP-1468)
    anion = np.array([j not in cations for j in orbit["owner"]])
    elements = orbit["elements"]
    centre_sites = (cations if centres is None
                    else {j for j, site in enumerate(sites) if site["element"] in centres})

    # per orbit atom and per centre element, found once: the orbit's atoms
    # outlive its rebuild, so only ``source`` differs between the two readers
    eligible: dict[str, np.ndarray] = {}

    def ligand_rows(element: str, orbit: dict[str, Any]) -> np.ndarray:
        if element not in eligible:
            eligible[element] = (
                anion & np.array([is_ligand(element, e) for e in elements], dtype=bool)
                if ligands is None else np.array([e in ligands for e in elements], dtype=bool))
        return np.nonzero(eligible[element][orbit["source"]])[0]

    # per orbit atom, read through ``source``: a metal is a ligand only on a
    # caller's list, so the P10 floor is per pair
    radius_of = np.array([element_radius(e) for e in elements], dtype=np.float64)
    nonmetal_of = ~np.array([is_metal(e) for e in elements], dtype=bool)

    def floor(site: dict, rows: np.ndarray, orbit: dict[str, Any]) -> np.ndarray:
        return split_floor(site["radius"] + radius_of[orbit["source"][rows]],
                           nonmetal_of[orbit["source"][rows]] & (not site["metal"]))

    # every centre's window must lie inside the orbit, and the images of one
    # site all see the same shortest distance
    reach = 0.0
    for j in sorted(centre_sites & set(orbit["owner"])):
        here = orbit["frac"][orbit["owner"].index(j)] @ basis.T
        rows = ligand_rows(sites[j]["element"], orbit)
        dist = np.linalg.norm(orbit["cart"][rows] - here, axis=1)
        dist = dist[dist >= floor(sites[j], rows, orbit)]
        if len(dist):
            reach = max(reach, SHELL_REACH * float(dist.min()))
    if reach > orbit["radius"]:
        orbit = _orbit(sites, orbit["atoms"], basis, reach)
    occupancy, cart, source = orbit["occupancy"], orbit["cart"], orbit["source"]
    radius, nonmetal = radius_of[source], nonmetal_of[source]
    # each row's ``(site, turn)``, for the file's disorder groups
    held_by = np.stack([np.asarray(orbit["owner"], dtype=int)[source],
                        orbit["turn"][source]], axis=-1)

    known = {key: k for k, key in enumerate(_keys([a["pos"] for a in atoms]))}
    segments: dict[tuple, list[int]] = {}
    for k, ends in enumerate(zip(_keys([b["a"] for b in bonds]), _keys([b["b"] for b in bonds]))):
        segments.setdefault(tuple(sorted(ends)), []).append(k)
    inverse = np.linalg.inv(basis)
    # rows of ``cart`` an element's centre may take as ligands, found once
    ligand_of: dict[str, np.ndarray] = {}
    centres = np.empty((n_cell, 3))
    n_centres = 0
    found: list[tuple] = []
    out: list[dict] = []
    partners: list[dict] = []
    dropped: list[dict] = []
    for c in range(n_cell):
        atom = atoms[c]
        if atom["site"] not in centre_sites:
            continue
        element = sites[atom["site"]]["element"]
        if element not in ligand_of:
            ligand_of[element] = ligand_rows(element, orbit)
        index = ligand_of[element]
        if not len(index):
            continue
        centre = np.asarray(atom["pos"], dtype=np.float64)
        own, metallic = sites[atom["site"]]["radius"], sites[atom["site"]]["metal"]
        # a mixed site is one centre, drawn in its first site's colour (P9)
        if (np.linalg.norm(centres[:n_centres] - centre, axis=1) < SAME_POSITION).any():
            continue
        centres[n_centres] = centre
        n_centres += 1
        dist = np.linalg.norm(cart[index] - centre, axis=1)
        # a ligand closer than the split floor is the centre itself, split
        kept = dist >= floor(sites[atom["site"]], index, orbit)
        index, dist = index[kept], dist[kept]
        if codes is not None:
            # the file's alternatives of this centre are none of its ligands
            mine = ~_apart(codes, np.array([atom["site"], atom["_turn"]]), held_by[index])
            index, dist = index[mine], dist[mine]
        if not len(dist):
            continue
        # Brunner & Schwarzenbach's window (P3)
        window = min(SHELL_REACH * float(dist.min()), orbit["radius"])
        index, dist = index[dist <= window], dist[dist <= window]
        order = np.argsort(dist, kind="stable")
        index, dist = index[order], dist[order]
        # a non-metal bonded to one of the centre's own non-metal ligands, and
        # beyond it as the centre sees them (the angle there obtuse, by more
        # than rounding), belongs to that ligand: cyanide's N behind the C a
        # metal holds, or pyrite's second S.  Metals form no such unit, and a
        # right angle is beside: Cu₃Au's Au sits at exactly 90° past a Cu,
        # and rounding had screened it round some of the Au and not others
        held = index[nonmetal[index]
                     & bonded(dist, own + radius[index], nonmetals=nonmetal[index] & (not metallic))]
        if len(held):
            apart = np.linalg.norm(cart[index][:, None, :] - cart[held][None, :, :], axis=2)
            near = np.linalg.norm(cart[held] - centre, axis=1)
            obtuse = dist[:, None] ** 2 - near[None, :] ** 2 - apart ** 2
            behind = (nonmetal[index][:, None]
                      & bonded(apart, radius[index][:, None] + radius[held][None, :],
                               nonmetals=True)
                      & (obtuse > 1e-9 * dist[:, None] ** 2))
            if codes is not None:
                behind &= ~_apart(codes, held_by[index][:, None, :], held_by[held][None, :, :])
            behind = behind.any(axis=1)
            index, dist = index[~behind], dist[~behind]
        # atoms of two sites at one position are one ligand, their
        # occupancies summed, so a mixed O/F site is full and a split one is not;
        # each joins its twin nearest the centre, the rows being sorted by distance
        root = np.arange(len(index))
        for i, j in sorted(cKDTree(cart[index]).query_pairs(SAME_POSITION)):
            root[j] = min(root[j], root[i])
        total = np.bincount(root, weights=occupancy[source[index]], minlength=len(index))
        kept = [[index[k], dist[k], total[k]] for k in np.nonzero(root == np.arange(len(root)))[0]]
        sequence = np.array([row[1] for row in kept] + [window])
        n, gap = shell_gap(sequence)
        if n < 4 or gap < POLYHEDRON_GAP:
            continue
        rival = rival_gap(sequence, n)
        shell = kept[:n]
        if codes is not None:
            # a shell holding two of the file's alternatives is split, as P9's is
            members = held_by[[row[0] for row in shell]]
            if _apart(codes, members[:, None, :], members[None, :, :]).any():
                continue
        vertices = np.array([cart[row[0]] for row in shell])
        partial = [row[2] < 1.0 - 1e-6 for row in shell]
        if any(partial[i] and partial[j]
               and one_atom(np.linalg.norm(vertices[i] - vertices[j]), shell[i][1], shell[j][1])
               for i in range(n) for j in range(i)):
            continue
        try:
            hull = ConvexHull(vertices - centre)
        except QhullError:                         # planar, or collinear
            continue
        if len(hull.vertices) < n or (hull.equations[:, 3] > -INSIDE_TOL).any():
            continue
        found.append((c, atom["site"], centre, n, gap, shell, vertices, hull, rival))
    # a shell drawn by default claims room under the atom cap first, so a
    # hidden one never costs the default picture a polyhedron
    for c, site, centre, n, gap, shell, vertices, hull, rival in sorted(
            found, key=lambda f: f[3] not in DEFAULT_SHELLS):
        corners = _keys(vertices)
        needed = [k for k in range(n) if corners[k] not in known]
        if len(partners) + len(needed) > room:
            dropped.append({"site": site, "drawn_by_default": n in DEFAULT_SHELLS,
                            "ligands": [elements[source[row[0]]] for row in shell]})
            continue
        for k in needed:
            origin = orbit["atoms"][source[shell[k][0]]]
            known[corners[k]] = len(atoms) + len(partners)
            partners.append({**origin, "pos": vertices[k].tolist(), "boundary": True,
                             "frac": (inverse @ vertices[k]).tolist(), "vertex_only": True})
        members = [known[key] for key in corners]
        simplices = hull.simplices.copy()
        corner = vertices[simplices]
        wound = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
        inward = np.einsum("ij,ij->i", wound, hull.equations[:, :3]) < 0
        simplices[inward] = simplices[inward][:, [0, 2, 1]]      # wind outward
        # a square face comes out as two triangles, so an edge is drawn only
        # where its two faces are not coplanar; the face opposite vertex m of
        # a simplex shares the other two
        folded = ~np.isclose(hull.equations[:, None, :], hull.equations[hull.neighbors],
                             atol=1e-6).all(axis=2)
        edges = {tuple(sorted((int(hull.simplices[f, (m + 1) % 3]),
                               int(hull.simplices[f, (m + 2) % 3]))))
                 for f, m in zip(*np.nonzero(folded))}
        (centre_key,) = _keys(centre)
        hidden = sorted(k for key in corners
                        for k in segments.get(tuple(sorted((centre_key, key))), []))
        out.append({
            "center": c,
            "site": site,
            "vertices": members,
            "faces": simplices.tolist(),
            "edges": [list(e) for e in sorted(edges)],
            # the centre's sticks to its own vertices, which the drawn
            # polyhedron replaces (P6)
            "bonds": hidden,
            "coordination": n,
            "mean_distance": float(np.mean([row[1] for row in shell])),
            "gap": gap,
            # a second gap that would close a polyhedron too, ``[n2, ratio]``
            "rival": None if rival is None else list(rival),
            "drawn_by_default": n in DEFAULT_SHELLS,
        })
    out.sort(key=lambda p: p["center"])
    return out, partners, dropped
