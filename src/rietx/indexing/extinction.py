"""Extinction-symbol determination: which systematic absences the pattern shows.

:func:`determine_extinction_symbol` takes an indexed lattice and the pattern it
came from and returns a **ranked list of extinction classes**, each listing the
space groups it contains.  It closes the ``index → space group → Le Bail →
Rietveld`` workflow, and its founding rule is the FitReport's one rank up, in its
sharpest form:

**The observable is the extinction symbol, not the space group.**  Only
systematic absences reach a powder pattern, so every space group sharing an
absence set produces an *identical* pattern — centrosymmetric/non-centro\
symmetric pairs, enantiomorphs, and the mirror that separates ``P 63`` from
``P 63/m`` are all invisible here **by construction, not for want of counting
time**.  So :class:`~rietx.schemas.indexing.ExtinctionCandidate` carries a
``space_groups`` *list*, ``EXTINCTION_GROUPS_NOT_SEPARABLE`` fires whenever it
holds more than one, and nothing in this module can return one space group.

**The classes are derived, never transcribed.**  Every gemmi setting whose
lattice matches the candidate is enumerated, its absence set is computed over the
hkl in range with ``ops.systematic_absences``, and the settings are grouped by
*identical* absence sets — the same discipline as ``wyckoff._compatible_lattice``
and ``stephens.strain_basis``.  It is therefore automatically right in
non-standard settings, which a transcription of *International Tables* A Table
3.2 is not: with the axes fixed by indexing, ``P n m a`` and ``P m n b`` are
different hypotheses about *this* cell, and both are enumerated.

**Three measured decisions shape the rest.**

1. *Count lines, not orbits.*  Two orbits routinely land at one 2θ (WP-1020's
   ``predicted_lines`` fix), and two reflections at one position are one
   observation and one Le Bail intensity.  Every count here — ``n_lines``,
   ``n_absent``, and the ``n_added`` of the nested comparison — is over distinct
   *positions*, which also makes the comparison immune to a class representative
   whose Laue group splits orbits more finely than the holohedry does.
2. *An absence you cannot see is not evidence.*  ``n_added`` counts only the
   **testable** forbidden lines: inside the fitted range, separated from
   every line the class still allows by ``model.forward._overlap_groups``' own
   FWHM criterion, **and left quiet by the class's own fitted pattern**
   (:func:`_model_is_quiet`, WP-1077).  Without the first two, a class whose
   extra absences all hide under allowed neighbours wins on parsimony alone —
   ΔBIC = −n·ln N with no measurement behind it — which is exactly the confident
   wrong singleton this milestone exists to prevent.  Without the third, the
   *refutation* becomes a measurement of the profile model; the story is under
   point 3.
3. *Direct absence evidence refutes; the fit only ranks — but it must be read
   against the right null model, and the plan's was wrong.*  The question is
   "does this forbidden position carry intensity nothing else explains?", and
   WP-1024's :func:`~rietx.indexing.workflow.absent_reflections` asks it
   against the fitted **background**.  That works for a lattice's phantom
   reflection, which sits in a gap; it fails here, because a forbidden position
   sits *inside* a dense predicted pattern.  Measured on the FAP lab pattern,
   whose space group is P 6₃/m: the forbidden 003 sits **0.89 FWHM** from the
   allowed (3,-1,2), which is ten times stronger, so its tail fills the window to
   **+27.6 σ** and the background test refutes the true class.  Asked against the
   class's own ``y_calc`` — background *plus every reflection the class still
   allows* — the same position reads **−3.9 σ**.  So the same function is called
   with ``y_calc`` in place of ``y_background``: one detector, one window, one
   threshold, referenced to the model that has to explain the data.  Where
   nothing is predicted nearby the two are the same test, which is why this is a
   generalisation rather than a second opinion.

   **Where something *is* predicted nearby, swapping the null model is not
   enough — the position is not evidence at all** (WP-1077).  A window filled by
   a neighbour's tail measures the accuracy of that tail, and a profile model is
   wrong there in a way counting statistics do not describe.  Measured on the
   certified corundum pattern (``tests/data/qarr/corundum.prn``, SRM 676a,
   R -3 c, 20-90°): at **sham** positions where no reflection of any kind is
   predicted, placed 1-3 FWHM from an allowed line, the same test clears 3 σ in
   **40-50 %** of cases, up to 24.7 σ — and it does so on the low-angle flank
   only (median +2.4 σ below a line against +0.1 σ above it), which names the
   cause as the unmodelled axial-divergence tail.  Freeing FCJ
   ``axial_sl``/``axial_hl`` in the shared profile fit takes Rwp 0.149 → 0.139
   and does **not** remove the refutation, so the repair is not a better
   profile.  It is :func:`_model_is_quiet`: a forbidden position is testable
   only where the class's own model predicts **less intensity than the test's
   own detection threshold**, so no error in a neighbour's tail — not even a
   total one — can manufacture a refutation.  Corundum's two flagged positions
   carry 20.0 σ and 25.7 σ of predicted neighbour tail; the seven the screen
   already read as absent carry 0.2-3.4 σ.

**Scoring is a nested model comparison, not lowest Rwp.**  A class with fewer
absences has more reflections and always fits at least as well, so Rwp ranks the
least-constrained class first every time.  ``report.layer2.delta_bic`` and
``hamilton_justified`` are imported (not reimplemented — they are the same device
Layer 2 uses before adding a parameter) with the *more*-absent class as the
restricted model, and the reported ``delta_bic`` is BIC(class) − BIC(absence-free
lattice): negative favours the class, and the difference between two classes'
values is itself a ΔBIC because both share the reference.

**Refutation is one-sided, and that is not a gap in the evidence.**  An extinction
symbol asserts *absences* and nothing else, so intensity at a forbidden position
contradicts it — while a class claiming **too few** absences asserts nothing that
the data can falsify.  ``P 1 c 1`` is a perfectly true statement about a P 2₁/c
pattern; it is merely not the most specific true one.  So a less restrictive class
is never ``refuted``, only outranked, and preferring the specific answer is exactly
what the nested comparison is for — which is also why the absence-free class always
survives to the end as the reference, and why :meth:`ExtinctionScreen.best_or_none`
needs a decisive *margin* rather than a refutation before it will answer at all.

Markvardsen, David, Johnston & Shankland (2001), *Acta Cryst.* **A57**, 47-54 is
the Bayesian formulation of this problem — a full posterior over **extinction
symbols** (their term and their unit of answer, which is the corroboration that
matters here) from the extracted intensities.  ΔBIC plus direct absence evidence
is the v1.0 form of the same logic; the posterior is a v2 fence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import gemmi
import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import (
    CellCandidate,
    ExtinctionCandidate,
    ExtinctionScreen,
    PeakList,
)
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData
from .fom import LINE_COINCIDENCE_RTOL, lattice_group
from .workflow import (
    ABSENT_SIGMA,
    ABSENT_WINDOW_FWHM,
    absent_reflections,
    structure_from_candidate,
)

#: ΔBIC below which two classes are **not** separated.  Kass & Raftery (1995),
#: *J. Am. Stat. Assoc.* **90**, 773, call a difference above 10 "very strong"
#: evidence; anything less is reported as an ambiguity rather than resolved,
#: which is the same posture ``ShiftScreen.separable`` takes one module over.
DECISIVE_DELTA_BIC = 10.0

#: Crystal systems that share one *lattice*, keyed by the candidate's system.
#: The powder determines a lattice, not a crystal system: a hexagonal metric
#: carries both the trigonal-P and the hexagonal groups, and the trigonal ones
#: own absence classes (``P 3 c 1``, ``P 31 c``) that the hexagonal ones do not.
#: Excluding them would silently remove real hypotheses.  Every other row is
#: itself — a monoclinic *group* in an orthorhombic cell is pseudosymmetry, which
#: is the Bravais screen's question and not this one's.
_LATTICE_SYSTEMS: dict[str, tuple[str, ...]] = {
    "triclinic": ("triclinic",),
    "monoclinic": ("monoclinic",),
    "orthorhombic": ("orthorhombic",),
    "tetragonal": ("tetragonal",),
    "trigonal": ("trigonal", "hexagonal"),
    "hexagonal": ("hexagonal", "trigonal"),
    "cubic": ("cubic",),
}

_GLIDES = frozenset("abcnde")
_SCREW = re.compile(r"^[2346][1-5]$")
_ROTATION = re.compile(r"^-?[12346]$")


def _is_axis(token: str) -> bool:
    return bool(_ROTATION.match(token) or _SCREW.match(token))


def _is_plane(token: str) -> bool:
    return token == "m" or token in _GLIDES


def _is_position(token: str) -> bool:
    """Is this a readable H-M position — an axis, a plane, or ``axis/plane``?"""
    parts = token.split("/")
    if len(parts) == 2:
        return _is_axis(parts[0]) and _is_plane(parts[1])
    return _is_axis(token) or _is_plane(token)


# ----------------------------------------------------------------------
# enumerating the compatible groups
# ----------------------------------------------------------------------
def _well_formed(sg: gemmi.SpaceGroup) -> bool:
    """Is this a standard H-M setting whose positions can be read?

    gemmi's table carries a handful of CCP4 origin-shifted entries whose symbols
    are not H-M at all — ``P 21212(a)``, ``C 2 2 21a)``, ``I 2 3a``.  They are
    dropped, and dropping them loses nothing: each has the same absence set as
    its standard counterpart (measured over gemmi 0.7.5's whole table), so it
    joins the same class and would only add an unreadable string to
    ``space_groups`` and defeat the symbol derivation, which reads positions.
    """
    tokens = sg.xhm().split(":")[0].split()[1:]
    return bool(tokens) and all(_is_position(t) for t in tokens)


def _unique_axis(cell: tuple[float, ...]) -> str:
    """The monoclinic unique axis, read off the cell rather than assumed.

    The package's conventional monoclinic setting is b-unique (see
    ``fom.lattice_group``), but the setting is a property of the *cell* that
    reaches this function, and enumerating the wrong unique axis would compare a
    ``P 1 21/c 1`` hypothesis against axes it does not refer to.
    """
    devs = [abs(cell[3] - 90.0), abs(cell[4] - 90.0), abs(cell[5] - 90.0)]
    return "abc"[int(np.argmax(devs))] if max(devs) > 1e-6 else "b"


def compatible_groups(system: str, centring: str,
                      cell: tuple[float, ...]) -> list[gemmi.SpaceGroup]:
    """Every gemmi setting whose lattice is this candidate's.

    Filtered by crystal system (through :data:`_LATTICE_SYSTEMS`), by centring,
    and — for monoclinic — by the unique axis the cell itself declares.  The
    rhombohedral-axes settings (``R 3:R``) are excluded because an R lattice
    reaches this package in hexagonal axes; applying one to a hexagonal cell
    describes a different lattice, which is the same class of error as handing a
    Niggli-reduced cell's input centring to a symmetry finder (WP-1024).
    """
    systems = _LATTICE_SYSTEMS.get(system)
    if systems is None:
        raise ValueError(f"unknown crystal system {system!r}")
    axis = _unique_axis(cell)
    out = []
    for sg in gemmi.spacegroup_table():
        if sg.crystal_system_str() not in systems or sg.ext == "R":
            continue
        if sg.centring_type() != (centring or "P"):
            continue
        if sg.crystal_system_str() == "monoclinic" and \
                sg.monoclinic_unique_axis() != axis:
            continue
        if not _well_formed(sg):
            continue
        out.append(sg)
    return out


def _laue_order(sg: gemmi.SpaceGroup) -> int:
    """Order of the Laue group — the point group with inversion added.

    It is what decides how finely reflections split into orbits, so the class
    representative is chosen to maximise it: the reflection list then differs
    from the absence-free lattice's *only* by the absences, which is what makes
    the comparison nested.
    """
    rots = {tuple(map(tuple, op.rot)) for op in sg.operations()}
    return len(rots | {tuple(tuple(-v for v in row) for row in r) for r in rots})


def _order(sg: gemmi.SpaceGroup) -> int:
    """Order of the space group's point group, inversion included.

    gemmi keeps the inversion out of ``sym_ops`` and in ``is_centrosymmetric``,
    so multiplying it back in is what keeps ``P m -3 m`` (48) above ``P 4 3 2``
    (24) — without it the absence-free class's representative comes out as a
    lower-symmetry member, and the reference model would stop being the lattice
    group every other part of the indexer compares against.
    """
    ops = sg.operations()
    return len(ops.sym_ops) * (2 if ops.is_centrosymmetric() else 1)


# ----------------------------------------------------------------------
# the class label
# ----------------------------------------------------------------------
def _absence_token(token: str) -> str:
    """The absence-generating part of one H-M position, or ``"-"``.

    A screw axis and a glide plane extinguish; a rotation, a rotoinversion and a
    mirror do not.  ``63/m`` therefore reduces to ``63`` and ``21/c`` stays whole.
    """
    parts = token.split("/")
    axis = parts[0] if _SCREW.match(parts[0]) else ""
    plane = parts[1] if len(parts) > 1 and parts[1] in _GLIDES else ""
    if not plane and token in _GLIDES:
        plane = token
    if axis and plane:
        return f"{axis}/{plane}"
    return axis or plane or "-"


def extinction_symbol(groups: list[gemmi.SpaceGroup], system: str,
                      centring: str) -> str:
    """An IT-style extinction symbol for a class, **derived** from its members.

    Built from the member carrying the fewest absence-generating elements — the
    one whose symbol is already the extinction symbol, which is IT's own
    convention read backwards — with every non-extinguishing position replaced by
    ``-``.  ``{P 63, P 63/m, P 63 2 2}`` → ``P 63 - -``; ``{P m 21 b, P 2 m b,
    P m m b}`` → ``P - - b``, because the 2₁'s condition is subsumed by the b
    glide's and only the glide is an independent element.  Monoclinic keeps its
    ``1`` placeholders (``P 1 21/c 1``), as IT writes them.

    **A label, not a key.**  It is derived rather than transcribed, so for an
    enantiomorphic pair — ``{P 41 3 2, P 43 3 2}`` — the choice between the two
    screw letters is arbitrary and is made by sorting the derived string;
    ``space_groups`` is the answer, and ``representative`` identifies the class.
    """
    def key(sg: gemmi.SpaceGroup):
        toks = [_absence_token(t) for t in sg.xhm().split(":")[0].split()[1:]]
        return (sum(t != "-" for t in toks), _order(sg), " ".join(toks), sg.number)

    src = min(groups, key=key)
    raw = src.xhm().split(":")[0].split()[1:]
    toks = [t if (system == "monoclinic" and t == "1") else _absence_token(t)
            for t in raw]
    n = 1 if system == "triclinic" else 3
    toks = (toks + ["-"] * n)[:n]
    return " ".join([centring or "P", *toks])


# ----------------------------------------------------------------------
# the reflection conditions
# ----------------------------------------------------------------------
#: Zones (planes through the origin) and axes the conditions are stated on, with
#: the two free indices each is parameterised by.  The list is the *derivation's*
#: vocabulary, not a table of answers: every condition is fitted to the absence
#: set and kept only if it reproduces it exactly.  The unusual-looking entries
#: are the symmetry images a fixed-axis cell makes distinct — ``h-2hl`` is the
#: hexagonal image of ``hhl`` under the threefold, ``hk-k`` a cubic image — and
#: without them a c-glide in ``P 63/m m c`` or an n-glide in ``P m -3 n`` is
#: reported half-explained.
_ZONES = (
    ("0kl", 0, ("k", "l"), (1, 2)),
    ("h0l", 1, ("h", "l"), (0, 2)),
    ("hk0", 2, ("h", "k"), (0, 1)),
    ("hhl", -1, ("h", "l"), (0, 2)),
    ("h-hl", -2, ("h", "l"), (0, 2)),
    ("hkk", -3, ("h", "k"), (0, 1)),
    ("hkh", -4, ("h", "k"), (0, 1)),
    ("hk-k", -5, ("h", "k"), (0, 1)),
    ("hk-h", -6, ("h", "k"), (0, 1)),
    ("h-2hl", -7, ("h", "l"), (0, 2)),
    ("-2hhl", -8, ("k", "l"), (1, 2)),
)
_AXES = (
    ("h00", 3, ("h",), (0,)),
    ("0k0", 4, ("k",), (1,)),
    ("00l", 5, ("l",), (2,)),
    ("hh0", 6, ("h",), (0,)),
    ("hhh", 7, ("h",), (0,)),
)
#: Linear forms tried, simplest first, against moduli 2, 3, 4 and 6.
_FORMS2 = (((1, 0), "{0}"), ((0, 1), "{1}"), ((1, 1), "{0}+{1}"),
           ((1, -1), "{0}-{1}"), ((2, 1), "2{0}+{1}"), ((1, 2), "{0}+2{1}"),
           ((2, -1), "2{0}-{1}"), ((3, 1), "3{0}+{1}"))
_FORMS1 = (((1,), "{0}"),)
_MODULI = (2, 3, 4, 6)


def _zone_mask(hkl: np.ndarray, code: int) -> np.ndarray:
    """Membership of one zone or axis, by the code in :data:`_ZONES`/:data:`_AXES`."""
    h, k, ell = hkl[:, 0], hkl[:, 1], hkl[:, 2]
    return {
        0: h == 0, 1: k == 0, 2: ell == 0,
        -1: h == k, -2: k == -h, -3: k == ell, -4: h == ell,
        -5: k == -ell, -6: h == -ell, -7: k == -2 * h, -8: h == -2 * k,
        3: (k == 0) & (ell == 0), 4: (h == 0) & (ell == 0),
        5: (h == 0) & (k == 0), 6: (h == k) & (ell == 0),
        7: (h == k) & (k == ell),
    }[code]


def _fit_condition(hkl, absent, labels, cols, forms) -> str | None:
    values = [hkl[:, c] for c in cols]
    for coefs, template in forms:
        combo = sum(c * v for c, v in zip(coefs, values))
        for m in _MODULI:
            if np.array_equal(absent, (combo % m) != 0):
                return f"{template.format(*labels)} = {m}n"
    return None


def reflection_conditions(hkl: np.ndarray, absent: np.ndarray
                          ) -> tuple[list[str], bool]:
    """Human-readable conditions for an absence set, and whether they cover it.

    Returns ``(["0kl: k = 2n", …], complete)``.  Every string is *fitted*: the
    modulus rule must reproduce the absences on its zone exactly, or it is not
    reported.  Zones are fitted off-axis (an axis inside a zone carries its own,
    stronger condition — Pbca's ``00l: l = 2n`` is not implied by ``0kl: k = 2n``)
    and a zone equivalent to one already reported is skipped, so the list reads
    like IT's rather than repeating each cubic permutation.

    ``complete`` is False when some absence no fitted rule explains remains.
    Measured over gemmi 0.7.5's whole table, that happens for **1 of 550**
    settings (``C 4 2 21``, a non-standard tetragonal C setting) — but the flag
    travels rather than being assumed away, because the absence set, not this
    prose, is what the screen actually uses.
    """
    absent = np.asarray(absent, dtype=bool)
    on_axis = np.count_nonzero(hkl == 0, axis=1) >= 2
    out: list[str] = []
    explained = np.zeros(len(hkl), dtype=bool)
    for group, forms, is_zone in ((_ZONES, _FORMS2, True),
                                  (_AXES, _FORMS1, False)):
        for name, code, labels, cols in group:
            in_zone = _zone_mask(hkl, code)
            mask = in_zone & ~on_axis if is_zone else in_zone
            if not mask.any() or not absent[mask].any():
                continue
            if not (absent[mask] & ~explained[mask]).any():
                continue                      # a symmetry image of a stated zone
            cond = _fit_condition(hkl[mask], absent[mask], labels, cols, forms)
            if cond is None:
                continue
            out.append(f"{name}: {cond}")
            explained |= mask & absent
            # the rule holds on the zone's own axes too whenever it predicts them
            # correctly — that is what makes an axial condition *implied* rather
            # than independent, and keeps ``P 1 21/c 1`` from reporting
            # ``00l: l = 2n`` beside ``h0l: l = 2n``
            axial = in_zone & on_axis
            if is_zone and axial.any() and _fit_condition(
                    hkl[axial], absent[axial], labels, cols, forms) is not None:
                explained |= axial & absent
    return out, not bool((absent & ~explained).any())


# ----------------------------------------------------------------------
# classes
# ----------------------------------------------------------------------
@dataclass
class AbsenceClass:
    """One extinction class before any fit: its groups, symbol and conditions."""

    symbol: str
    representative: str
    space_groups: list[str]
    conditions: list[str] = field(default_factory=list)
    conditions_complete: bool = True


def absence_classes(candidate: CellCandidate, wavelength: float,
                    two_theta_max: float, two_theta_min: float = 0.0,
                    ) -> list[AbsenceClass]:
    """Group every compatible space group by its absence set over the hkl in range.

    Two classes that differ only outside the measured range are **one class**
    here, and that is the honest statement: the data cannot separate them.  It is
    also why :attr:`ExtinctionScreen.two_theta_range` is part of the answer.

    The representative is the member with the largest Laue group (see
    :func:`_laue_order`); the absence-free class's representative is therefore the
    lattice group itself, which is what makes it the reference model.
    """
    groups = compatible_groups(candidate.system, candidate.centring,
                               candidate.cell)
    if not groups:
        return []
    hkl = _hkl_in_range(candidate.cell, wavelength, two_theta_max, two_theta_min)
    lattice = gemmi.find_spacegroup_by_name(
        candidate.lattice_group or lattice_group(candidate.system,
                                                 candidate.centring))
    allowed = ~np.asarray(lattice.operations().systematic_absences(hkl), dtype=bool)
    hkl_lattice = hkl[allowed]

    buckets: dict[bytes, list[gemmi.SpaceGroup]] = {}
    for sg in groups:
        key = np.asarray(sg.operations().systematic_absences(hkl_lattice),
                         dtype=bool).tobytes()
        buckets.setdefault(key, []).append(sg)

    out = []
    for key, members in buckets.items():
        rep = max(members, key=lambda s: (_laue_order(s), _order(s),
                                          s.is_reference_setting(), -s.number))
        conds, complete = reflection_conditions(
            hkl_lattice, np.frombuffer(key, dtype=bool))
        out.append(AbsenceClass(
            symbol=extinction_symbol(members, candidate.system,
                                     candidate.centring),
            representative=rep.xhm(),
            space_groups=[s.xhm() for s in sorted(members,
                                                  key=lambda s: (s.number,
                                                                 s.xhm()))],
            conditions=conds, conditions_complete=complete))
    return out


def _hkl_in_range(cell, wavelength: float, two_theta_max: float,
                  two_theta_min: float = 0.0) -> np.ndarray:
    """Every integer hkl whose d falls in range — the same box and the same 0.1 %
    boundary slack ``generate_reflections`` uses, so the two enumerations agree."""
    from ..crystallography.lattice import d_spacings

    d_min = wavelength / (2.0 * np.sin(np.radians(max(two_theta_max, 1e-6) / 2.0)))
    ranges = [np.arange(-int(np.floor(x / d_min)) - 1,
                        int(np.floor(x / d_min)) + 2) for x in cell[:3]]
    grid = np.meshgrid(*ranges, indexing="ij")
    hkl = np.column_stack([g.ravel() for g in grid]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]
    d = d_spacings(hkl, *cell)
    keep = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3)
                                                      / 2.0)))
        keep &= d <= d_max * 1.001
    return hkl[keep]


# ----------------------------------------------------------------------
# lines, and which of them a class forbids
# ----------------------------------------------------------------------
def line_index(two_theta: np.ndarray) -> tuple[np.ndarray, int]:
    """Label each reflection with the **line** it belongs to, coincidences merged.

    Two orbits at one 2θ are one line: one observation, one Le Bail intensity, one
    thing a figure of merit may count (WP-1020's ``predicted_lines``).  The
    tolerance is :data:`~rietx.indexing.fom.LINE_COINCIDENCE_RTOL`, nine orders
    below any measurement precision, so it merges exact coincidences and nothing
    else — reflections that merely *overlap* are a different question, answered by
    :func:`testable_mask`.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    order = np.argsort(tt, kind="stable")
    labels = np.empty(len(tt), dtype=np.int64)
    n, anchor = -1, None
    for i in order:
        if anchor is None or tt[i] - anchor > LINE_COINCIDENCE_RTOL * max(
                abs(tt[i]), 1e-12):
            n += 1
            anchor = tt[i]
        labels[i] = n
    return labels, n + 1


def _orbit_absences(sg: gemmi.SpaceGroup, orbits: list[np.ndarray]) -> np.ndarray:
    """Is *every* member of each orbit systematically absent under ``sg``?

    Asking the orbit rather than its representative is not pedantry.  The orbits
    come from the **holohedry**, and a class need not have holohedral symmetry:
    under ``P a -3`` the reflections 012 and 021 sit in one m-3m orbit at one 2θ,
    and one of them is extinguished while the other is not.  The *line* is present.
    """
    flat = np.vstack(orbits)
    absent = np.asarray(sg.operations().systematic_absences(flat), dtype=bool)
    offsets = np.cumsum([0] + [len(o) for o in orbits[:-1]])
    return np.logical_and.reduceat(absent, offsets) if len(flat) else absent


def testable_mask(forbidden_tt: np.ndarray, allowed_tt: np.ndarray,
                  fwhm_forbidden: np.ndarray, fwhm_allowed: np.ndarray,
                  data_tt: np.ndarray) -> np.ndarray:
    """Which forbidden positions the data can actually check.

    A forbidden position is testable when it is **covered** — the fitted pattern
    has channels within ±½ FWHM of it, so an interior exclusion or the end of the
    scan does not read as an absence — and **separable**: it shares no
    ``model.forward._overlap_groups`` group with a line the class still allows.
    The overlap criterion is imported rather than restated so "overlapped" means
    one thing package-wide, and the allowed set includes **every emission line**,
    because a Kα2 image sitting on a forbidden Kα1 position would otherwise be
    read as intensity the class forbids.
    """
    from ..model.forward import _overlap_groups

    tt = np.concatenate([np.asarray(forbidden_tt, dtype=np.float64),
                         np.asarray(allowed_tt, dtype=np.float64)])
    width = np.concatenate([np.asarray(fwhm_forbidden, dtype=np.float64),
                            np.asarray(fwhm_allowed, dtype=np.float64)])
    is_forbidden = np.zeros(len(tt), dtype=bool)
    is_forbidden[:len(forbidden_tt)] = True
    order = np.argsort(tt, kind="stable")
    blocked = np.zeros(len(tt), dtype=bool)
    for group in _overlap_groups(tt[order], width[order]):
        idx = order[group]
        if not is_forbidden[idx].all():
            blocked[idx] = True

    data = np.asarray(data_tt, dtype=np.float64)
    covered = np.array([
        bool(np.any(np.abs(data - p) <= 0.5 * max(float(w), 1e-6)))
        for p, w in zip(forbidden_tt, fwhm_forbidden)], dtype=bool)
    return covered & ~blocked[:len(forbidden_tt)]


def _model_is_quiet(two_theta: np.ndarray, y_calc: np.ndarray,
                    y_background: np.ndarray, sigma: np.ndarray,
                    positions: np.ndarray, fwhm: np.ndarray, *,
                    k_sigma: float) -> np.ndarray:
    """Which forbidden windows the class's **own model** leaves below threshold.

    The other half of testability, and the half :func:`testable_mask` cannot
    see (WP-1077; the measurement is in the module docstring, point 3).
    ``testable_mask`` asks a question about *positions* — is this one covered,
    and is it separable from its neighbours — and a position can pass both while
    the window it opens is filled by a neighbour's **tail**.  What the absence
    test then reads there is how well the profile model describes that tail, and
    it describes it badly: on real laboratory data the residual on a strong
    line's low-angle flank reaches 25 σ of counting noise at positions where no
    reflection at all is predicted.

    So the window must be quiet in the *model* at the same significance the
    observation is required to be quiet at — same ±:data:`ABSENT_WINDOW_FWHM`
    window, same propagated σ, same ``k_sigma`` as
    :func:`~rietx.indexing.workflow.absent_reflections`, which is what makes the
    pair one test rather than two thresholds.  Read the criterion as its
    consequence: a position survives only when a **total** failure of the
    neighbour's tail could not by itself clear the detection threshold, so no
    refutation this screen reports can be manufactured by the profile.

    The scaling is right rather than convenient.  The model's error in a tail is
    a fraction of that tail's intensity while the noise it is measured against
    goes as its square root, so the same fractional error is *more* significant
    on a pattern with more counts — and this gate tightens with counting time in
    exactly that way, which a fixed intensity ratio would not.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    model = (np.asarray(y_calc, dtype=np.float64)
             - np.asarray(y_background, dtype=np.float64))
    sig = np.asarray(sigma, dtype=np.float64)
    out = np.zeros(len(np.asarray(positions)), dtype=bool)
    for i, (pos, width) in enumerate(zip(np.asarray(positions, dtype=np.float64),
                                         np.asarray(fwhm, dtype=np.float64))):
        inside = np.abs(tt - pos) <= ABSENT_WINDOW_FWHM * max(float(width), 1e-6)
        if not np.any(inside):
            continue                     # outside the fitted range: not evidence
        noise = float(np.sqrt((sig[inside] ** 2).sum()))
        out[i] = float(model[inside].sum()) < k_sigma * noise
    return out


# ----------------------------------------------------------------------
# the screen
# ----------------------------------------------------------------------
def _screen_plan():
    """The one stage every class is fitted with: the background, and nothing else.

    The profile is **frozen** at the shared pre-fit's values, and that is what
    makes the comparison nested: two classes then differ only in their reflection
    set, where refitting the widths per class would let a restricted class buy
    back a missing reflection by broadening its neighbour.  The background stays
    free because removing reflections genuinely changes what the background must
    carry, and holding it would charge that difference to the class.
    """
    from ..strategy.staged import RefinementPlan, Stage

    return RefinementPlan(stages=[Stage("bkg", ["instrument.background.*"])])


def _fit_class(candidate: CellCandidate, data: PatternData, instrument: Instrument,
               symbol: str, two_theta_limits):
    from ..refine import Refinement

    ref = Refinement(structure_from_candidate(candidate, space_group=symbol),
                     instrument, history=False)
    result = ref.fit(data, mode="lebail", plan=_screen_plan(),
                     two_theta_limits=two_theta_limits)
    return ref, result


def _chi2_absolute(stats) -> float:
    """The weighted residual sum of squares ``delta_bic`` wants.

    ``Statistics.chi2`` is the *reduced* χ² (Σwd²/(N−P)), and the two models being
    compared have different P, so dividing by their own dof first would fold a
    second, unwanted ratio into the comparison.
    """
    return float(stats.chi2) * max(stats.n_points - stats.n_free_parameters, 1)


def determine_extinction_symbol(data: PatternData, candidate: CellCandidate,
                                instrument: Instrument, *,
                                peaks: PeakList | None = None,
                                two_theta_limits: tuple[float, float] | None = None,
                                k_sigma: float = ABSENT_SIGMA,
                                max_classes: int | None = None,
                                cancel=None) -> ExtinctionScreen:
    """Rank the extinction classes compatible with an indexed lattice.

    The pipeline, and the reason for each step:

    1. **one shared profile fit** of the absence-free lattice group
       (``workflow.validation_plan``: background, one shift parameter, then the
       widths) — every class is then fitted with that instrument frozen, so no
       class can compensate a missing reflection with a wider peak;
    2. **the reference fit**: the absence-free class under the same one-stage
       protocol as every other class, which is what makes the χ² values
       comparable;
    3. **one Le Bail fit per class**, weakest claim first, scored by ΔBIC and
       Hamilton against the reference (see the module docstring);
    4. **the absence test** at each class's own testable forbidden positions,
       read against **that class's own calculated pattern** — one position
       carrying intensity the class cannot account for refutes it, with the hkl
       named.

    ``candidate.system`` is taken as given, deliberately: when the Bravais screen
    reported ``INDEX_BRAVAIS_AMBIGUOUS`` its ``system`` is the *conservative*
    reading, and a screen run in the higher symmetry would enumerate classes the
    lattice may not have.

    Cost is one refinement per surviving class (~0.1 s each on a 3750-point
    pattern, after a ~2 s profile fit).  ``max_classes`` caps it; the classes left
    unfitted are reported with ``screened=False`` and, because an unasked question
    must not read as a clean answer, :meth:`ExtinctionScreen.best_or_none` then
    abstains.
    """
    from ..crystallography.symmetry import reflection_orbits
    from ..report.layer2 import delta_bic, hamilton_justified
    from .diagnostics import extinction_class_diagnostics, extinction_diagnostics
    from .peaks import predicted_fwhm
    from .workflow import seed_widths, validation_plan

    symbol = candidate.lattice_group or lattice_group(candidate.system,
                                                      candidate.centring)
    wavelength = float(instrument.source.lines[0].wavelength.value)
    screen = ExtinctionScreen(
        lattice_group=symbol, cell=candidate.cell, system=candidate.system,
        centring=candidate.centring, wavelength=wavelength)

    ins = instrument
    if peaks is not None:
        ins, _seeded = seed_widths(ins, peaks)
    from ..refine import Refinement

    # A failure *here* is about the cell, the instrument or the data — every
    # class would inherit it — so it comes back as a failed screen with a reason
    # rather than as a traceback, the same way ``validate_by_lebail`` reports a
    # candidate the physics refuses.
    try:
        pre = Refinement(structure_from_candidate(candidate, space_group=symbol),
                         ins, history=False)
        tt_max = float(np.max(np.asarray(data.two_theta)))
        if two_theta_limits is not None:
            tt_max = min(tt_max, float(two_theta_limits[1]))
        profile = pre.fit(data, mode="lebail",
                          plan=validation_plan(candidate, ins,
                                               two_theta_max=tt_max),
                          two_theta_limits=two_theta_limits)
        screen.profile_rwp = float(profile.statistics.rwp)
        frozen = pre.fitted_instrument
        ref_fit, ref_result = _fit_class(candidate, data, frozen, symbol,
                                         two_theta_limits)
    except Exception as exc:                          # noqa: BLE001
        screen.status = "failed"
        screen.diagnostics = [Diagnostic(
            level="error", code="EXTINCTION_SCREEN_FAILED",
            message=(f"the reference Le Bail fit of the lattice group {symbol} "
                     f"raised {type(exc).__name__}: {exc}, so no class could be "
                     "screened against it"),
            where=[f"{candidate.system} {candidate.centring}, cell "
                   f"{tuple(round(v, 4) for v in candidate.cell)}"],
            suggestion=("this is about the cell, the instrument or the data — "
                        "every class would fail the same way.  Validate the cell "
                        "first (index_pattern's validate_by_lebail), and check "
                        "the wavelength is not on an absorption edge"))]
        return screen

    rows = ref_fit.reflection_table()
    primary = [r for r in rows if r.line == 0]
    if not primary:
        # Reached when the cell predicts nothing in the measured range.  It used
        # to be reached by accident instead: ``generate_reflections`` raised an
        # einsum shape error on the empty hkl set and the ``except`` above dressed
        # it up as the reason.  Now that an empty range is answered rather than
        # raised, this branch is the live one — and a "failed" status carrying no
        # diagnostic is a state with no writer for its reason, so it says why.
        screen.status = "failed"
        screen.diagnostics = [Diagnostic(
            level="error", code="EXTINCTION_SCREEN_FAILED",
            message=(f"the lattice group {symbol} predicts no reflections in "
                     f"the measured 2θ range, so there is nothing for any "
                     f"absence class to be screened against"),
            where=[f"{candidate.system} {candidate.centring}, cell "
                   f"{tuple(round(v, 4) for v in candidate.cell)}"],
            suggestion=("this is about the cell and the range, not the classes — "
                        "every class would fail the same way.  Check the cell is "
                        "not far too small for the range measured, and that the "
                        "wavelength is the one the pattern was collected at"))]
        return screen
    tt_ref = np.array([r.two_theta for r in primary], dtype=np.float64)
    hkl_ref = np.array([(r.h, r.k, r.l) for r in primary], dtype=np.int64)
    labels, n_lines = line_index(tt_ref)
    orbits = reflection_orbits(symbol, hkl_ref)
    fwhm_ref = predicted_fwhm(tt_ref, frozen)
    tt_all = np.array([r.two_theta for r in rows], dtype=np.float64)
    line_of_row = _row_line_labels(rows, primary, labels)
    # one representative reflection per line, and the reduction offsets the
    # per-line "is every orbit here absent?" test uses
    by_line = np.argsort(labels, kind="stable")
    starts = np.flatnonzero(np.concatenate(
        [[True], np.diff(labels[by_line]) > 0]))
    first_row_of_line = by_line[starts]
    fwhm_all = predicted_fwhm(tt_all, frozen)
    tt_data = np.asarray(ref_result.two_theta, dtype=np.float64)

    screen.two_theta_range = (float(tt_data.min()), float(tt_data.max()))
    screen.reference_rwp = float(ref_result.statistics.rwp)
    screen.reference_chi2 = _chi2_absolute(ref_result.statistics)
    screen.reference_lines = int(n_lines)
    screen.n_points = int(ref_result.statistics.n_points)

    classes = absence_classes(candidate, wavelength, screen.two_theta_range[1],
                              screen.two_theta_range[0])
    screen.n_classes = len(classes)

    # 3a — what each class forbids, and which of those the data can test.  No
    # fit yet: this is what orders the screen and what ``n_added`` counts.
    entries: list[ExtinctionCandidate] = []
    evidence: list[dict] = []
    for cls in classes:
        sg = gemmi.find_spacegroup_by_name(cls.representative)
        orbit_absent = _orbit_absences(sg, orbits)
        absent_line = np.logical_and.reduceat(orbit_absent[by_line], starts)
        forbidden = np.flatnonzero(absent_line)
        entry = ExtinctionCandidate(
            symbol=cls.symbol, representative=cls.representative,
            space_groups=list(cls.space_groups), conditions=list(cls.conditions),
            conditions_complete=cls.conditions_complete,
            n_lines=int(n_lines - len(forbidden)), n_absent=int(len(forbidden)))
        first_of_line = first_row_of_line[forbidden]
        tt_forbidden = tt_ref[first_of_line]
        fwhm_forbidden = fwhm_ref[first_of_line]
        keep = np.zeros(len(forbidden), dtype=bool)
        if len(forbidden):
            is_forbidden_row = np.isin(line_of_row, forbidden)
            keep = testable_mask(tt_forbidden, tt_all[~is_forbidden_row],
                                 fwhm_forbidden, fwhm_all[~is_forbidden_row],
                                 tt_data)
        # ``n_testable`` is deliberately NOT set here.  Its other half asks
        # whether this class's own fitted pattern leaves the window quiet, so it
        # is not knowable until the class is fitted — and a geometric count
        # published in the meantime would be an over-estimate reading as a
        # measurement.  It stays None until 3b, which is what ``screened``
        # already says about every other number on the row.
        entries.append(entry)
        evidence.append({"keep": keep, "tt": tt_forbidden, "fwhm": fwhm_forbidden,
                         "first": first_of_line})

    # 3b — one Le Bail fit per class, weakest claim first, and the absence test
    # read against **that class's own** calculated pattern
    budget = len(entries) if max_classes is None else max(int(max_classes), 1)
    order = sorted(range(len(entries)),
                   key=lambda i: (entries[i].n_absent, entries[i].symbol))
    for rank, i in enumerate(order):
        entry, ev = entries[i], evidence[i]
        if rank >= budget or (cancel is not None and bool(cancel)):
            continue                       # left unscreened, and it says so
        if entry.n_absent == 0:                       # the reference itself
            result = ref_result
        else:
            try:
                _fit, result = _fit_class(candidate, data, frozen,
                                          entry.representative,
                                          two_theta_limits)
            except Exception as exc:                  # noqa: BLE001
                entry.screened = True
                entry.refuted = True
                entry.refuted_reason = (
                    f"the Le Bail fit of {entry.representative} raised "
                    f"{type(exc).__name__}: {exc}")
                continue
        entry.screened = True
        entry.rwp = float(result.statistics.rwp)
        entry.gof = float(result.statistics.gof)
        entry.chi2 = _chi2_absolute(result.statistics)
        # testability is settled here, not in 3a: a position is evidence only
        # where *this class's* fitted pattern leaves the window below the
        # detection threshold, so nothing but the absence can trip the test
        keep = np.asarray(ev["keep"], dtype=bool)
        if keep.any():
            keep = keep.copy()
            keep[keep] = _model_is_quiet(
                tt_data, np.asarray(result.y_calc),
                np.asarray(result.y_background), np.asarray(result.sigma),
                ev["tt"][keep], ev["fwhm"][keep], k_sigma=k_sigma)
        entry.n_testable = int(keep.sum())
        entry.delta_bic = delta_bic(entry.chi2, screen.reference_chi2,
                                    screen.n_points, entry.n_testable)
        entry.absences_rejected = hamilton_justified(
            entry.chi2, screen.reference_chi2, screen.n_points,
            entry.n_lines + int(result.statistics.n_free_parameters),
            entry.n_testable)

        if not entry.n_testable:
            continue
        # the absence test, against **this class's own** calculated pattern: the
        # null model has to contain the neighbours, and y_calc is what does
        pos = ev["tt"][keep]
        absent_tt, _ratio = absent_reflections(
            tt_data, np.asarray(result.y_obs), np.asarray(result.y_calc),
            np.asarray(result.sigma), pos, ev["fwhm"][keep], k_sigma=k_sigma)
        # each position either came back absent or did not; those that did not
        # carry intensity this class forbids, and no fit can explain them away
        quiet = set(absent_tt)
        loud = [j for j, p in enumerate(pos) if float(p) not in quiet]
        entry.n_present = len(loud)
        idx = np.flatnonzero(keep)[loud]
        entry.forbidden_two_theta = [round(float(ev["tt"][j]), 4) for j in idx]
        entry.forbidden_hkl = [tuple(int(v) for v in hkl_ref[ev["first"][j]])
                               for j in idx]
        if entry.n_present:
            entry.refuted = True
            entry.refuted_reason = (
                f"{entry.n_present} of {entry.n_testable} testable forbidden "
                f"position(s) carry intensity this class cannot account for, "
                f"first {entry.forbidden_hkl[0]} at "
                f"{entry.forbidden_two_theta[0]:.3f}°")

    screen.n_screened = sum(1 for e in entries if e.screened)
    if cancel is not None and bool(cancel):
        screen.status = "cancelled"
    for entry in entries:
        entry.diagnostics = extinction_class_diagnostics(entry)
    screen.candidates = sorted(
        entries, key=lambda e: (e.refuted, not e.screened, e.delta_bic,
                                e.n_absent))
    screen.diagnostics = extinction_diagnostics(screen)
    return screen


def _row_line_labels(rows, primary, labels) -> np.ndarray:
    """The line label of every (emission line, reflection) row.

    A Kα2 row inherits its reflection's line, which is what lets the overlap test
    see a second-emission-line image sitting on a forbidden Kα1 position.
    """
    by_hkl: dict[tuple[int, int, int], int] = {}
    for j, r in enumerate(primary):
        by_hkl[(r.h, r.k, r.l)] = int(labels[j])
    return np.array([by_hkl.get((r.h, r.k, r.l), -1) for r in rows],
                    dtype=np.int64)


__all__ = ["DECISIVE_DELTA_BIC", "AbsenceClass", "absence_classes",
           "compatible_groups", "determine_extinction_symbol",
           "extinction_symbol", "line_index", "reflection_conditions",
           "testable_mask"]
