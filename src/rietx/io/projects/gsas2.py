"""GSAS-II ``.gpx`` projects: someone else's refinement, read without GSAS-II.

A ``.gpx`` is the whole GSAS-II project — the phases, the histograms, the
profile and background coefficients, the constraints, and the refine flag on
every one of them.  That last part is why this reader exists, as it is why the
``.EXP`` reader one module over does: a CIF carries converged coordinates and a
raw file carries the pattern, but neither says **which parameters were free**.

**The file is a sequence of pickles, not a container.**  GSAS-II writes one
``pickle.dump`` per top-level tree item, end to end with no header, and reads
them back by calling ``pickle.load`` until ``EOFError``.  Each item is a list
whose first element is a ``[label, data]`` pair for the item itself and whose
remaining elements are ``[label, data]`` pairs for its children; the tree is
exactly two levels deep.  So a reader needs no GSAS-II import — measured on 34
tutorial projects, every one loads with the standard library and numpy alone.

**Reading a pickle is running it, so the trust boundary is this module's
first job.**  ``pickle.load`` imports and calls whatever the stream names, which
would make opening a downloaded ``.gpx`` an arbitrary-code-execution surface —
the one thing every other reader in ``io/`` avoids by being text.  So nothing
here calls plain ``pickle.load``: :data:`ALLOWED_GLOBALS` is the whole list of
names the unpickler will resolve, every other global is **refused by name**, and
the file is refused entire rather than read in part.  ``find_class`` is pickle's
only import hook, so this closes the hole rather than narrowing it.  It is the
established shape for the problem: PyTorch's ``weights_only`` unpickler is an
allow-list with a by-name refusal, and it wraps the classes it must accept but
must not construct in a dummy, which is :class:`Gsas2Object` here.

**GSAS-II's own two classes are admitted as inert stand-ins.**  A constraint
names its variables with ``GSASIIobj.G2VarObj`` instances, and refusing that
name would refuse the whole file — 10 of the 34 tutorial projects, including
every sequential fit.  The stand-in defines no ``__reduce__`` and no
``__setstate__``, so the pickle machinery can do nothing with it but fill a
dictionary, and what lands there is what GSAS-II stored: a variable name and
three random-number ids that :func:`read_gsas2_gpx` resolves against the
project's own phases, histograms and atoms.  Nothing of GSAS-II is imported and
no behaviour of theirs is reproduced.

**Two ways this file kind is not the ``.EXP``**, both measured rather than
assumed:

* **The profile coefficients are in centidegrees, and ``Zero`` is not.**
  ``U``, ``V``, ``W`` are centidegrees² and ``X``, ``Y``, ``Z`` centidegrees, as
  in GSAS — corroborated against a file this repo already holds, since the
  ``TOF-CW Joint Refinement`` tutorial's 11-BM histogram states ``U``, ``V``,
  ``W`` of 1.163, −0.126, 0.063 and ``tests/data/11bm_gsas.prm`` states the same
  instrument's profile, which :func:`~rietx.io.instrument_profile.read_gsas_prm`
  converts to 1.163e-4, −1.26e-5, 6.3e-6 deg².  ``Zero`` is the exception: the
  specification says degrees in as many words, and the nine non-zero values in
  the corpus run 0.0004° to 0.0219°, which is a zero correction in degrees and
  an implausible one in centidegrees.
* **A python-2 rebuild name is not a python-2 file.**  ``copy_reg._reconstructor``
  and ``__builtin__.object`` appear in 6 of the 34 projects, one of them written
  by python 3.6.6, so an allow-list holding only the python-3 spellings refuses
  real files.  They are admitted with the rest; both are safe here because the
  class they rebuild has to pass this same gate first.

**What is read, reported and refused** is declared in :data:`TREE_ITEM_STANCE`
rather than left to the branches, for the reason
:mod:`~rietx.io.projects.coverage` gives: a construct nobody wrote a branch for
is otherwise invisible, and "the reader handles it" and "the reader has never
seen it" become one observable.  Constant-wavelength powder histograms are read;
time-of-flight ones keep their numbers but not their coefficient *names*, since
the TOF profile functions number their coefficients differently; images,
single-crystal data and sequential-fit results are reported by name.

Specification: the GSAS-II data tree as documented in that project's own
``docs/source/objvarorg.rst`` — § GSAS-II Data Tree for the file layout,
§ Covariance, § Phase Information, § Atom Records, § Powder Diffraction Tree
Items and § CW/TOF Instrument Parameters for the contents — read 2026-09-16 as
**specification only**, which is the licence fence ``ATTRIBUTION.md`` records
for GSAS-II.  Excluded regions are documented nowhere in that file and are taken
from GSAS-II's own ``GSASIIstrIO`` statement that ``Limits[2:]`` are the excluded
ranges and that each masks the data *inside* it.  No GSAS-II code is reproduced
here.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...schemas.common import Diagnostic
from .coverage import Stance

#: Which description of the format this reader was written against.  Stated
#: rather than implied, so extending it to another edition is declared work.
SPEC = ("GSAS-II data tree, documented in AdvancedPhotonSource/GSAS-II "
        "docs/source/objvarorg.rst (read 2026-09-16)")


class Gsas2GpxError(ValueError):
    """A ``.gpx`` this reader will not read, naming the file and the reason.

    A project reader refuses where a pattern reader would repair: its answer is
    a whole model, and a caller cannot see which part of it came from the file
    (``io/CLAUDE.md`` § Project readers).
    """


class Gsas2Object:
    """An inert stand-in for one of GSAS-II's own classes.

    Defines no ``__reduce__``, no ``__setstate__`` and no ``__init__``, so the
    only thing the pickle machinery can do with it is set attributes — which is
    the whole point.  The attributes are then GSAS-II's stored state, read as
    data.  :attr:`gsas2_class` is the name the file used, kept so a diagnostic
    can say what was found rather than that something was.
    """

    gsas2_class = "?"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{self.gsas2_class} {self.__dict__}>"


def _standin(name: str) -> type:
    """A subclass of :class:`Gsas2Object` standing in for ``GSASIIobj.<name>``."""
    return type(name, (Gsas2Object,), {"gsas2_class": name})


#: A GSAS-II variable reference, as stored in the ``Constraints`` item.  Its
#: attributes are ``name`` and the ``phase``/``histogram``/``atom`` random-number
#: ids, which :func:`read_gsas2_gpx` resolves against the project itself.
G2VarObj = _standin("G2VarObj")

#: A GSAS-II expression object, as stored by the sequential single-peak fit.  It
#: carries the expression as **text**; the compiled form is ``None`` on disk, so
#: reading one compiles nothing.  rietx refuses a parameter expression at
#: construction (``Parameter.expr``), so this has no landing site by design and
#: is reported rather than carried.
ExpressionObj = _standin("ExpressionObj")


def _numpy_globals() -> dict[tuple[str, str], Any]:
    """The numpy names a ``.gpx`` names, resolved once against this numpy.

    ``numpy.core`` is numpy's own legacy alias for ``numpy._core`` and emits a
    ``DeprecationWarning`` when touched, so the modern private module is reached
    directly and mapped *from* the legacy name the files carry.  A file names
    what numpy was called when it was written; this build resolves it to what
    the name means now, which is the same repair a reader makes on any other
    renamed field.
    """
    import numpy as np

    return {
        ("numpy", "ndarray"): np.ndarray,
        ("numpy", "dtype"): np.dtype,
        ("numpy", "float64"): np.float64,
        ("numpy", "int64"): np.int64,
        ("numpy.core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
        ("numpy.core.multiarray", "scalar"): np._core.multiarray.scalar,
        ("numpy._core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
        ("numpy._core.multiarray", "scalar"): np._core.multiarray.scalar,
        ("numpy.ma.core", "MaskedArray"): np.ma.core.MaskedArray,
        ("numpy.ma.core", "_mareconstruct"): np.ma.core._mareconstruct,
    }


#: Why each admitted name is admitted.  **The allow-list is the trust boundary**,
#: so it is data a caller can read rather than a set of branches: every
#: ``(module, name)`` pair below is resolvable by :func:`read_gsas2_gpx` and
#: every other one is refused by name.
#:
#: Measured on 34 GSAS-II tutorial projects (2026-09-16): eleven distinct globals
#: appear, and the seven beyond ``ndarray``/``dtype``/``_reconstruct`` are not
#: optional — ``numpy.ma`` appears in 19 of the 34, ``_codecs.encode`` in 12,
#: the python-2 rebuild pair in 6 and ``G2VarObj`` in 10.
ALLOWED_GLOBALS: dict[tuple[str, str], str] = {
    ("numpy", "ndarray"): "the pattern, the covariance matrix and the reflection lists",
    ("numpy", "dtype"): "an array's element type, rebuilt with the array",
    ("numpy", "float64"): "a stored scalar",
    ("numpy", "int64"): "a stored scalar",
    ("numpy.core.multiarray", "_reconstruct"): "numpy's own array rebuild hook",
    ("numpy.core.multiarray", "scalar"): "numpy's own scalar rebuild hook",
    ("numpy._core.multiarray", "_reconstruct"): "the same hook under numpy 2's spelling",
    ("numpy._core.multiarray", "scalar"): "the same hook under numpy 2's spelling",
    ("numpy.ma.core", "MaskedArray"): "a pattern with points masked out",
    ("numpy.ma.core", "_mareconstruct"): "numpy's own masked-array rebuild hook",
    ("_codecs", "encode"): "bytes inside an array written under python 2",
    ("copy_reg", "_reconstructor"): "python 2's object rebuild hook, for a class that passed this gate",
    ("__builtin__", "object"): "python 2's spelling of `object`, the base in that rebuild",
    ("GSASIIobj", "G2VarObj"): "a constraint's variable reference, read as an inert stand-in",
    ("GSASIIobj", "ExpressionObj"): "a stored expression, read as an inert stand-in",
}

#: The stand-ins and plain builtins in :data:`ALLOWED_GLOBALS`; the numpy half is
#: resolved per call by :func:`_numpy_globals`.
_STATIC_GLOBALS: dict[tuple[str, str], Any] = {
    ("_codecs", "encode"): __import__("_codecs").encode,
    ("copy_reg", "_reconstructor"): __import__("copyreg")._reconstructor,
    ("__builtin__", "object"): object,
    ("GSASIIobj", "G2VarObj"): G2VarObj,
    ("GSASIIobj", "ExpressionObj"): ExpressionObj,
}


class _RefusedGlobal(Exception):
    """Raised inside the unpickler; converted to a :class:`Gsas2GpxError`."""

    def __init__(self, module: str, name: str) -> None:
        super().__init__(f"{module}.{name}")
        self.qualified = f"{module}.{name}"


class _Restricted(pickle.Unpickler):
    """``pickle.Unpickler`` whose ``find_class`` is :data:`ALLOWED_GLOBALS`."""

    def __init__(self, stream, table: dict[tuple[str, str], Any]) -> None:
        # latin-1, because a .gpx written under python 2 stores byte strings and
        # any byte is legal in one; the alternative is a UnicodeDecodeError on a
        # file GSAS-II reads.  It is what GSAS-II's own reader asks for.
        super().__init__(stream, encoding="latin-1")
        self._table = table

    def find_class(self, module: str, name: str) -> Any:
        try:
            return self._table[(module, name)]
        except KeyError:
            raise _RefusedGlobal(module, name) from None


def _read_tree(path: Path) -> list[list]:
    """Every top-level tree item, in file order.

    The loop is the format: ``pickle.load`` until the stream is spent, one call
    per item.  A refused global stops the read entirely rather than skipping an
    item, because the item it stopped in is part of the model.
    """
    table = {**_numpy_globals(), **_STATIC_GLOBALS}
    items: list[list] = []
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise Gsas2GpxError(f"{path.name}: cannot be read ({exc})") from exc
    with handle as stream:
        while True:
            start = stream.tell()
            if not stream.read(1):
                break
            stream.seek(start)
            try:
                items.append(_Restricted(stream, table).load())
            except _RefusedGlobal as exc:
                raise Gsas2GpxError(
                    f"{path.name}: names {exc.qualified}, which this reader "
                    f"will not resolve.  A pickle names the callables used to "
                    f"rebuild it and reading one calls them, so this reader "
                    f"resolves an allow-list "
                    f"(`rietx.io.projects.gsas2.ALLOWED_GLOBALS`) and refuses "
                    f"every other name rather than running it.  The file is "
                    f"not read at all: a project half-read past a name nobody "
                    f"vouched for is not a model") from None
            except Exception as exc:
                raise Gsas2GpxError(
                    f"{path.name}: is not a readable GSAS-II project "
                    f"({type(exc).__name__}: {exc}).  A .gpx is a sequence of "
                    f"pickled tree items; this one stopped part way, so it is "
                    f"truncated or is not a .gpx at all") from exc
    if not items:
        raise Gsas2GpxError(f"{path.name}: is empty")
    return items


#: What this reader does with each kind of top-level tree item, declared rather
#: than left to the branches (``coverage.py``'s rule, whose :class:`Stance`
#: vocabulary this shares).  Every kind measured across the tutorial corpus has a
#: row; a kind absent from here is reported by name as unknown, which is the
#: honest answer for a tree item nobody has classified.
TREE_ITEM_STANCE: dict[str, tuple[Stance, str]] = {
    "PWDR": (Stance.READ, "a powder histogram with its instrument, limits, "
                          "background and sample parameters"),
    "Phases": (Stance.READ, "the phases, their cells, sites and refine flags"),
    "Covariance": (Stance.READ, "the last refinement's agreement indices and "
                                "the list of variables it refined"),
    "Constraints": (Stance.READ, "the equivalences, holds and constraint "
                                 "equations the refinement carried"),
    "Controls": (Stance.READ, "the refinement controls, of which the version "
                              "that wrote the file is kept"),
    "Notebook": (Stance.IGNORED, "the project's free-text log"),
    "Rigid bodies": (Stance.IGNORED, "the rigid-body *library*, which describes "
                                     "bodies available to insert rather than "
                                     "any phase's model"),
    "Restraints": (Stance.REPORTED, "restraints on bonds, angles and planes"),
    "Sequential results": (Stance.REPORTED, "the per-histogram results of a "
                                            "sequential fit"),
    "Sequential peak fit results": (
        Stance.REPORTED, "the per-histogram results of a sequential "
                         "single-peak fit, which is where a stored expression "
                         "lives"),
    "IMG": (Stance.REPORTED, "a detector image and its calibration"),
    "HKLF": (Stance.REPORTED, "single-crystal structure factors"),
    "PDF": (Stance.REPORTED, "a pair distribution function"),
    "SASD": (Stance.REPORTED, "small-angle scattering data"),
    "REFD": (Stance.REPORTED, "reflectometry data"),
}

#: The tree-item labels that carry a *name* after the kind, so the kind is the
#: first word.  Every other label is one word or several fixed ones
#: (``Rigid bodies``, ``Sequential peak fit results``) and is its own key: taking
#: the first word of those would look up ``Rigid``, which is in no table.
DATA_PREFIXES: tuple[str, ...] = ("PWDR", "HKLF", "IMG", "PDF", "SASD", "REFD")


def item_kind(label: str) -> str:
    """The :data:`TREE_ITEM_STANCE` key for one top-level item's label."""
    head = label.split(" ", 1)[0]
    return head if head in DATA_PREFIXES else label


def _labelled(item: Any) -> tuple[str, Any] | None:
    """One top-level item's ``(label, payload)``, or ``None`` if it has none.

    **One test, read by every pass over the tree.**  A truncated or hand-edited
    project can hold an item that is not the ``[[label, data], *children]``
    shape, and a pass that assumed the shape after another had already reported
    it unlabelable raised a bare ``TypeError`` out of the reader — the one
    thing ``io/CLAUDE.md`` forbids, since the answer must be a refusal naming
    the file.
    """
    if not (isinstance(item, list) and item
            and isinstance(item[0], (list, tuple)) and len(item[0]) == 2):
        return None
    return str(item[0][0]), item[0][1]


#: The histogram types this reader names coefficients for, from the
#: specification's own CW table.
CW_TYPES: tuple[str, ...] = ("PXC", "PNC")

#: What each histogram type code means, in this package's words.  A code absent
#: from here is carried verbatim and reported as unknown rather than guessed at.
HISTOGRAM_TYPES: dict[str, str] = {
    "PXC": "constant-wavelength X-ray",
    "PNC": "constant-wavelength neutron",
    "PNT": "time-of-flight neutron",
}

#: Power of centidegrees each CW coefficient carries, for the conversion to
#: degrees.  A width or a Lorentzian coefficient is 1, a Gaussian variance term
#: is 2.  A name absent from here is **not** a centidegree quantity and its
#: :attr:`Gsas2Term.degrees` is ``None``: ``Zero`` is already in degrees (the
#: specification says so and the corpus's magnitudes agree), ``SH/L`` and
#: ``Polariz.`` are ratios, and ``Lam`` is a wavelength.
CW_CENTIDEGREE_POWER: dict[str, int] = {
    "U": 2, "V": 2, "W": 2, "X": 1, "Y": 1, "Z": 1,
}

#: The refine-flag letters a GSAS-II atom record carries at ``ct+1``.
ATOM_REFINE_FLAGS: dict[str, str] = {
    "F": "site occupancy",
    "X": "coordinates, as permitted by symmetry",
    "U": "displacement parameters",
    "M": "magnetic moment",
}


@dataclass(frozen=True)
class Gsas2Value:
    """A number the file states with its own refine flag beside it.

    GSAS-II writes a refinable quantity as ``[value, flag]`` and an instrument
    coefficient as ``[initial, value, flag]``; both arrive here, and a flag of
    ``0`` — the format's "cannot be refined" — arrives as ``False``, which is
    what it means for the answer.
    """

    value: float
    refined: bool


@dataclass(frozen=True)
class Gsas2Term:
    """One instrument coefficient: its name, its value, and its flag.

    ``value`` is the refined number GSAS-II last held and ``initial`` the one it
    started from, which the format keeps side by side.  ``degrees`` is the same
    quantity in degrees where the unit is a power of centidegrees, and ``None``
    where it is not — never a silent identity (:data:`CW_CENTIDEGREE_POWER`).
    """

    name: str
    value: float
    initial: float
    refined: bool
    degrees: float | None = None


@dataclass(frozen=True)
class Gsas2Background:
    """The background function a histogram fitted, and its coefficients.

    ``function`` is GSAS-II's own name for it (``chebyschev``, ``cosine``,
    ``lin interpolate`` …), carried as the file's string rather than mapped onto
    a rietx background: the members are not all polynomials, and a mapping would
    be inventing a correspondence.  ``n_debye`` and ``n_peaks`` count the diffuse
    terms and fitted background peaks the second half of the record holds.
    """

    function: str
    refined: bool
    coefficients: tuple[float, ...]
    n_debye: int = 0
    n_peaks: int = 0


@dataclass(frozen=True)
class Gsas2Atom:
    """One row of a phase's ``Atoms`` list: the site, and what was free on it.

    The refine flags are the payload.  GSAS-II stores them as a string of
    letters (:data:`ATOM_REFINE_FLAGS`), and an empty string is the file saying
    *held* rather than the file saying nothing.
    """

    label: str
    species: str
    refine_flags: str
    x: float
    y: float
    z: float
    occupancy: float
    site_symmetry: str
    multiplicity: int
    adp: str
    uiso: float | None = None
    uij: tuple[float, ...] = ()

    @property
    def anisotropic(self) -> bool:
        """Whether the site's displacement is a tensor rather than one number."""
        return self.adp.upper().startswith("A")

    @property
    def refine_xyz(self) -> bool:
        return "X" in self.refine_flags

    @property
    def refine_u(self) -> bool:
        return "U" in self.refine_flags

    @property
    def refine_occupancy(self) -> bool:
        return "F" in self.refine_flags

    @property
    def refine_moment(self) -> bool:
        return "M" in self.refine_flags


@dataclass(frozen=True)
class Gsas2Phase:
    """One phase: its symmetry, its cell with the cell's own flag, its sites.

    ``kind`` is GSAS-II's ``General['Type']`` — ``nuclear``, ``magnetic``,
    ``macromolecular`` — read rather than inferred from the records present,
    because a magnetic phase's nuclear half parses perfectly.
    """

    name: str
    kind: str
    space_group: str
    cell: tuple[float, float, float, float, float, float]
    refine_cell: bool
    atoms: tuple[Gsas2Atom, ...] = ()
    volume: float | None = None
    pawley: bool = False
    #: GSAS-II's own index for the phase, the ``p`` of a ``p:h:name`` variable
    number: int | None = None
    #: the file's ``General['magPhases']`` entry, verbatim.  A nuclear phase
    #: carrying one is half of a magnetic model — the project fits magnetic
    #: scattering somewhere this reader does not follow — so the string is kept
    #: as evidence and **not** interpreted: what it names is GSAS-II's business
    #: and guessing at it is how a reader comes to describe a model it has not
    #: read.  Ten of the 34 corpus projects carry one
    magnetic_partner: str | None = None

    @property
    def magnetic(self) -> bool:
        return self.kind.lower().startswith("magnetic")


@dataclass(frozen=True)
class Gsas2Histogram:
    """One ``PWDR`` item: the machine, the range fitted, and the background.

    ``terms`` are the instrument coefficients with their flags, which with
    :attr:`Gsas2Hap.size` and :attr:`Gsas2Hap.mustrain` are where a
    constant-wavelength protocol actually lives.
    """

    number: int
    name: str
    kind: str
    terms: tuple[Gsas2Term, ...] = ()
    #: the two-theta range the refinement used, which is not the range measured
    limits: tuple[float, float] | None = None
    #: the range the file was loaded with, kept because the pair is the evidence
    #: that a range was narrowed at all
    measured_limits: tuple[float, float] | None = None
    #: ranges masked **out** of the fit, from ``Limits[2:]``
    excluded_regions: tuple[tuple[float, float], ...] = ()
    background: Gsas2Background | None = None
    #: the refinable sample parameters, keyed by GSAS-II's own name
    sample: dict[str, Gsas2Value] = field(default_factory=dict)
    #: ``Debye-Scherrer`` or ``Bragg-Brentano``
    geometry: str = ""
    gonio_radius: float | None = None
    temperature: float | None = None
    n_points: int | None = None

    def by_name(self) -> dict[str, Gsas2Term]:
        """The instrument coefficients keyed by GSAS-II's own name for them."""
        return {t.name: t for t in self.terms}

    @property
    def constant_wavelength(self) -> bool:
        return self.kind in CW_TYPES

    @property
    def wavelengths(self) -> tuple[float, ...]:
        """The emission lines this histogram states, primary first.

        A single ``Lam`` or the ``Lam1``/``Lam2`` pair of a laboratory tube;
        empty for a histogram that states neither, which is every
        time-of-flight one.
        """
        named = self.by_name()
        if "Lam" in named:
            return (named["Lam"].value,)
        pair = tuple(named[k].value for k in ("Lam1", "Lam2") if k in named)
        return pair


@dataclass(frozen=True)
class Gsas2Broadening:
    """A ``Size`` or ``Mustrain`` row: the model, its numbers and its flags.

    ``kind`` is GSAS-II's own (``isotropic``, ``uniaxial``, ``generalized``);
    ``values`` are the direct numbers with their flags and ``terms`` the
    hkl-dependent coefficients a generalized model carries.  The format writes
    **both** rows whatever the model, so ``terms`` on an isotropic row is the
    unused default rather than a second opinion: read ``kind`` first.  Sizes are
    in µm and microstrains in units of 1e-6, which is the format's convention
    and not converted here.
    """

    kind: str
    values: tuple[Gsas2Value, ...] = ()
    axis: tuple[int, int, int] = (0, 0, 1)
    terms: tuple[Gsas2Value, ...] = ()


@dataclass(frozen=True)
class Gsas2Hap:
    """What one phase did in one histogram.

    The sample broadening and the preferred orientation are refined per
    phase-and-histogram pair, so they are here rather than on either side.
    """

    phase: str
    histogram: str
    scale: Gsas2Value | None = None
    size: Gsas2Broadening | None = None
    mustrain: Gsas2Broadening | None = None
    hstrain: tuple[Gsas2Value, ...] = ()
    #: ``(model, value, refined, axis)`` — ``MD`` is March-Dollase, ``SH`` the
    #: spherical-harmonic texture this build does not model
    preferred_orientation: tuple[str, float, bool, tuple[int, int, int]] | None = None
    extinction: Gsas2Value | None = None
    #: whether this pair's intensities were extracted rather than calculated
    lebail: bool = False
    used: bool = True


@dataclass(frozen=True)
class Gsas2Constraint:
    """One row of the ``Constraints`` item, with its variables resolved.

    ``kind`` is the format's own letter: ``e`` a set of equivalent variables,
    ``c`` a constraint equation summing to :attr:`value`, ``h`` a variable held,
    ``f`` a new variable defined as the sum.  ``terms`` are
    ``(multiplier, name)`` pairs where the name is GSAS-II's ``p:h:var:at``
    spelling, resolved from the random-number ids the file stores.
    """

    kind: str
    group: str
    terms: tuple[tuple[float, str], ...]
    value: float | str | None = None
    vary: bool | None = None

    @property
    def is_equivalence(self) -> bool:
        """An ``e`` row, which is the one shape ``tie_equal`` reproduces."""
        return self.kind == "e"

    def __str__(self) -> str:
        body = " + ".join(f"{m:g}·{n}" for m, n in self.terms)
        if self.kind == "h":
            return f"hold {body}"
        if self.kind == "c":
            return f"{body} = {self.value}"
        if self.kind == "f":
            return f"new variable = {body}"
        return f"equivalent: {body}"


@dataclass(frozen=True)
class Gsas2Model:
    """What a ``.gpx`` states.

    Deliberately not a :class:`~rietx.schemas.Structure` yet — the file states a
    whole project, and which phase a caller wants is the caller's question.  A
    value the file omits arrives as ``None`` rather than as a default, because a
    default reads as an answer (WP-1076): ``n_variables`` really is absent from
    some files' ``Rvals``.
    """

    phases: tuple[Gsas2Phase, ...] = ()
    histograms: tuple[Gsas2Histogram, ...] = ()
    #: keyed ``(phase name, histogram name)``, GSAS-II's own keys
    hap: dict[tuple[str, str], Gsas2Hap] = field(default_factory=dict)
    constraints: tuple[Gsas2Constraint, ...] = ()
    #: the variables the last refinement actually refined, in GSAS-II's own
    #: ``p:h:var:at`` spelling — the protocol, stated by the file itself
    vary_list: tuple[str, ...] = ()
    #: standard uncertainties, ordered to match :attr:`vary_list`
    esds: tuple[float, ...] = ()
    rwp: float | None = None
    #: GSAS-II's ``GOF``, which is the **square root** of reduced χ² (measured:
    #: it matches ``sqrt(chisq / (Nobs - Nvars))`` to six figures on all six
    #: corpus files stating the four numbers)
    gof: float | None = None
    #: GSAS-II's ``chisq``, which is Σw(Io−Ic)² and not a reduced χ²
    chi2: float | None = None
    n_observations: int | None = None
    n_variables: int | None = None
    converged: bool | None = None
    #: the GSAS-II revision that last wrote the file, from ``Controls``
    version: str | None = None
    #: where GSAS-II last saved it, which is not where it is now
    saved_as: str | None = None
    path: str | None = None
    #: One line per thing the **read** could not carry across, in this package's
    #: words, kept on the model whether or not a ``diagnostics=`` list was passed
    unsupported: tuple[str, ...] = ()

    def histogram(self, name: str | int | None = None) -> Gsas2Histogram:
        """One histogram by name or number, or the only one there is.

        Raises rather than picking when a file carries several and the caller
        named none: which histogram's wavelength is "the" wavelength is not a
        question this reader may answer for someone.
        """
        if name is not None:
            for h in self.histograms:
                if name in (h.name, h.number):
                    return h
            have = ", ".join(f"{h.number}:{h.name!r}" for h in self.histograms)
            raise Gsas2GpxError(
                f"{self.path or '<model>'}: no histogram {name!r} — this file "
                f"carries {have or 'none'}")
        if len(self.histograms) == 1:
            return self.histograms[0]
        if not self.histograms:
            raise Gsas2GpxError(
                f"{self.path or '<model>'}: states no powder histograms — "
                f"there is no wavelength, no range and no profile to read.  "
                f"The phases are on `model.phases`")
        have = ", ".join(f"{h.number}:{h.name!r}" for h in self.histograms)
        raise Gsas2GpxError(
            f"{self.path or '<model>'}: {len(self.histograms)} histograms "
            f"({have}) and none named — pass histogram=<name or number>")

    def phase(self, name: str | int | None = None) -> Gsas2Phase:
        """One phase by name or number, or the only one there is."""
        if name is not None:
            for p in self.phases:
                if name in (p.name, p.number):
                    return p
            have = ", ".join(f"{p.number}:{p.name!r}" for p in self.phases)
            raise Gsas2GpxError(
                f"{self.path or '<model>'}: no phase {name!r} — this file "
                f"carries {have or 'none'}")
        if len(self.phases) == 1:
            return self.phases[0]
        if not self.phases:
            raise Gsas2GpxError(
                f"{self.path or '<model>'}: states no phases")
        have = ", ".join(f"{p.number}:{p.name!r}" for p in self.phases)
        raise Gsas2GpxError(
            f"{self.path or '<model>'}: {len(self.phases)} phases ({have}) and "
            f"none named — pass phase=<name or number>")


# --------------------------------------------------------------------------
# reading


def _float(value: Any) -> float | None:
    """A stored number as a plain float, or ``None`` where it is not one."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool:
    """GSAS-II's refine flag: ``True``, ``False`` or ``0`` for "cannot be"."""
    return bool(value)


def _sequence(value: Any) -> tuple:
    """A stored list or array as a tuple, and ``None`` as an empty one.

    Written out rather than spelled ``value or ()`` because half of these come
    back as numpy arrays, whose truth value raises rather than answering.
    """
    if value is None:
        return ()
    try:
        return tuple(value)
    except TypeError:
        return ()


def _value(entry: Any) -> Gsas2Value | None:
    """A ``[value, flag]`` pair, which is how a sample parameter is stored."""
    if not isinstance(entry, (list, tuple)) or not entry:
        return None
    number = _float(entry[0])
    if number is None:
        return None
    return Gsas2Value(number, _flag(entry[1]) if len(entry) > 1 else False)


def _term(name: str, entry: Any) -> Gsas2Term | None:
    """An instrument coefficient's ``[initial, value, flag]`` triple.

    A two-element entry is one the format declares unrefinable (``Source`` is
    a string pair), and one whose value is not a number is skipped rather than
    coerced — ``Type`` states the histogram kind and is read from there.
    """
    if not isinstance(entry, (list, tuple)) or len(entry) < 2:
        return None
    initial, value = _float(entry[0]), _float(entry[1])
    if value is None:
        return None
    power = CW_CENTIDEGREE_POWER.get(name)
    degrees = None if power is None else value / 100.0 ** power
    return Gsas2Term(
        name=name, value=value,
        initial=initial if initial is not None else value,
        refined=_flag(entry[2]) if len(entry) > 2 else False,
        degrees=degrees)


def _pair(entry: Any) -> tuple[float, float] | None:
    """A two-element numeric range, however the file spells the container."""
    if not isinstance(entry, (list, tuple)) or len(entry) < 2:
        return None
    low, high = _float(entry[0]), _float(entry[1])
    if low is None or high is None:
        return None
    return (low, high)


def _background(entry: Any) -> Gsas2Background | None:
    """``[[function, flag, n, *coefficients], {debye and peak terms}]``."""
    if not isinstance(entry, (list, tuple)) or not entry:
        return None
    head = entry[0]
    if not isinstance(head, (list, tuple)) or len(head) < 3:
        return None
    coefficients = tuple(
        c for c in (_float(v) for v in head[3:]) if c is not None)
    extra = entry[1] if len(entry) > 1 and isinstance(entry[1], dict) else {}
    return Gsas2Background(
        function=str(head[0]), refined=_flag(head[1]),
        coefficients=coefficients,
        n_debye=int(extra.get("nDebye", 0) or 0),
        n_peaks=int(extra.get("nPeaks", 0) or 0))


def _broadening(entry: Any) -> Gsas2Broadening | None:
    """``[kind, values, flags, axis, coefficients, coefficient flags]``."""
    if not isinstance(entry, (list, tuple)) or len(entry) < 3:
        return None
    values = tuple(
        Gsas2Value(v, _flag(f))
        for v, f in zip((_float(x) for x in entry[1]), entry[2])
        if v is not None)
    axis = (0, 0, 1)
    if len(entry) > 3 and isinstance(entry[3], (list, tuple)) and len(entry[3]) == 3:
        axis = tuple(int(v) for v in entry[3])  # type: ignore[assignment]
    terms: tuple[Gsas2Value, ...] = ()
    if len(entry) > 5 and isinstance(entry[4], (list, tuple)):
        terms = tuple(
            Gsas2Value(v, _flag(f))
            for v, f in zip((_float(x) for x in entry[4]), entry[5])
            if v is not None)
    return Gsas2Broadening(kind=str(entry[0]), values=values, axis=axis,
                           terms=terms)


def _atom(row: list, pointers: tuple[int, int, int, int]) -> Gsas2Atom | None:
    """One atom record, read through the phase's own ``AtomPtrs``.

    The pointers are the format's way of saying where the columns are — a
    macromolecular phase carries three more of them before the label, and a
    magnetic one three moment columns after the occupancy — so every field is
    read relative to them rather than from a fixed index.
    """
    cx, ct, cs, cia = pointers
    if len(row) <= max(cx + 3, cs + 1, cia + 1):
        return None
    coords = [_float(row[cx + i]) for i in range(3)]
    if any(c is None for c in coords):
        return None
    uij = tuple(
        v for v in (_float(row[cia + 2 + i]) for i in range(6)) if v is not None
    ) if len(row) > cia + 7 else ()
    return Gsas2Atom(
        label=str(row[ct - 1]), species=str(row[ct]),
        refine_flags=str(row[ct + 1]).strip(),
        x=coords[0], y=coords[1], z=coords[2],  # type: ignore[arg-type]
        occupancy=_float(row[cx + 3]) or 0.0,
        site_symmetry=str(row[cs]), multiplicity=int(_float(row[cs + 1]) or 0),
        adp=str(row[cia]), uiso=_float(row[cia + 1]), uij=uij)


def _phase(name: str, data: dict) -> Gsas2Phase:
    """One entry of the ``Phases`` item."""
    general = data.get("General", {}) if isinstance(data, dict) else {}
    cell_row = general.get("Cell", [])
    numbers = [_float(v) for v in cell_row[1:7]] if len(cell_row) >= 7 else []
    if len(numbers) != 6 or any(v is None for v in numbers):
        raise Gsas2GpxError(
            f"phase {name!r} states no readable cell — its General['Cell'] is "
            f"{cell_row!r}")
    pointers = tuple(int(v) for v in general.get("AtomPtrs", (3, 1, 7, 9)))
    if len(pointers) != 4:
        raise Gsas2GpxError(
            f"phase {name!r} states {len(pointers)} atom column pointers "
            f"rather than the four the format defines, so its atom records "
            f"cannot be read by column")
    atoms = tuple(
        a for a in (_atom(row, pointers)  # type: ignore[arg-type]
                    for row in data.get("Atoms", []) if isinstance(row, list))
        if a is not None)
    return Gsas2Phase(
        name=str(general.get("Name", name)),
        kind=str(general.get("Type", "")),
        space_group=str(general.get("SGData", {}).get("SpGrp", "")).strip(),
        cell=tuple(numbers),  # type: ignore[arg-type]
        refine_cell=_flag(cell_row[0]) if cell_row else False,
        atoms=atoms,
        volume=_float(cell_row[7]) if len(cell_row) > 7 else None,
        pawley=bool(general.get("doPawley", False)),
        number=data.get("pId") if isinstance(data.get("pId"), int) else None,
        magnetic_partner=(str(data["magPhases"])
                          if data.get("magPhases") else None))


#: The sample parameters GSAS-II stores as ``[value, flag]``, which is the set a
#: protocol is read from.  The rest of that dict is the run's description —
#: goniometer angles, the sample's materials, free-text names — and is not a
#: refinable quantity, so it is not collected here.
SAMPLE_PARAMETERS: tuple[str, ...] = (
    "Scale", "Absorption", "DisplaceX", "DisplaceY", "Shift", "Transparency",
    "SurfRoughA", "SurfRoughB", "Layer Disp",
)


def _histogram(label: str, payload: Any, children: dict[str, Any]) -> Gsas2Histogram:
    """One ``PWDR`` item and its children."""
    data = payload[0] if isinstance(payload, (list, tuple)) and payload else {}
    arrays = payload[1] if isinstance(payload, (list, tuple)) and len(payload) > 1 else None
    instrument = children.get("Instrument Parameters", [{}])
    values = instrument[0] if isinstance(instrument, (list, tuple)) and instrument else {}
    kind = ""
    if isinstance(values, dict) and isinstance(values.get("Type"), (list, tuple)):
        kind = str(values["Type"][0]).strip()
    terms = tuple(
        t for t in (_term(name, entry) for name, entry in values.items()
                    if name != "Type")
        if t is not None) if isinstance(values, dict) else ()

    limits = children.get("Limits", [])
    measured = _pair(limits[0]) if isinstance(limits, (list, tuple)) and limits else None
    used = _pair(limits[1]) if isinstance(limits, (list, tuple)) and len(limits) > 1 else None
    excluded = tuple(
        p for p in (_pair(row) for row in (limits[2:] if isinstance(limits, (list, tuple)) else []))
        if p is not None)

    sample = children.get("Sample Parameters", {})
    sample = sample if isinstance(sample, dict) else {}
    collected = {}
    for name in SAMPLE_PARAMETERS:
        entry = _value(sample.get(name))
        if entry is not None:
            collected[name] = entry

    n_points = None
    if arrays is not None:
        try:
            n_points = int(len(arrays[0]))
        except (TypeError, IndexError):
            n_points = None

    return Gsas2Histogram(
        number=int(data.get("hId", -1)) if isinstance(data, dict) else -1,
        name=label, kind=kind, terms=terms,
        limits=used, measured_limits=measured, excluded_regions=excluded,
        background=_background(children.get("Background")),
        sample=collected,
        geometry=str(sample.get("Type", "")),
        gonio_radius=_float(sample.get("Gonio. radius")),
        temperature=_float(sample.get("Temperature")),
        n_points=n_points)


def _hap(phase: str, histogram: str, data: dict) -> Gsas2Hap:
    """One phase-and-histogram entry, from a phase's ``Histograms`` dict."""
    prefo = data.get("Pref.Ori.")
    preferred = None
    if isinstance(prefo, (list, tuple)) and len(prefo) >= 4:
        axis = prefo[3] if isinstance(prefo[3], (list, tuple)) else (0, 0, 1)
        preferred = (str(prefo[0]), _float(prefo[1]) or 1.0, _flag(prefo[2]),
                     tuple(int(v) for v in axis))
    hstrain: tuple[Gsas2Value, ...] = ()
    row = data.get("HStrain")
    if isinstance(row, (list, tuple)) and len(row) >= 2:
        hstrain = tuple(
            Gsas2Value(v, _flag(f))
            for v, f in zip((_float(x) for x in row[0]), row[1])
            if v is not None)
    return Gsas2Hap(
        phase=phase, histogram=histogram,
        scale=_value(data.get("Scale")),
        size=_broadening(data.get("Size")),
        mustrain=_broadening(data.get("Mustrain")),
        hstrain=hstrain,
        preferred_orientation=preferred,  # type: ignore[arg-type]
        extinction=_value(data.get("Extinction")),
        lebail=bool(data.get("LeBail", False)),
        used=bool(data.get("Use", True)))


def _variable_name(ref: Any, phases: dict[int, str], histograms: dict[int, int],
                   atoms: dict[int, tuple[str, int]]) -> str:
    """A ``G2VarObj`` stand-in as GSAS-II's own ``p:h:var:at`` spelling.

    The stored ids are random numbers rather than indices, which is what makes
    them survive a phase being renamed or reordered, so each is looked up in the
    project's own tables.  An id the file does not define is printed as ``?``
    rather than dropped: a constraint naming something this reader could not
    find is exactly the thing a caller must see.
    """
    if isinstance(ref, str):
        return ref
    if not isinstance(ref, Gsas2Object):
        return str(ref)
    phase = getattr(ref, "phase", None)
    histogram = getattr(ref, "histogram", None)
    atom = getattr(ref, "atom", None)
    name = str(getattr(ref, "name", "?"))

    def _look(value, table):
        if value is None:
            return ""
        if value == "*":
            return "*"
        found = table.get(value)
        return "?" if found is None else str(found)

    spelled = f"{_look(phase, phases)}:{_look(histogram, histograms)}:{name}"
    if atom is not None:
        label = atoms.get(atom) if not isinstance(atom, str) else None
        if isinstance(atom, str):
            spelled += f":{atom}"
        elif label is None:
            spelled += ":?"
        else:
            spelled += f":{label[1]}"
    return spelled


def _constraints(payload: Any, phases: dict[int, str], histograms: dict[int, int],
                 atoms: dict[int, tuple[str, int]]) -> tuple[Gsas2Constraint, ...]:
    """The ``Constraints`` item, resolved into readable variable names.

    The format is ``[[mult, var], …, fixed value, vary flag, type letter]``, one
    row per constraint, grouped by what the variables belong to.  The keys
    beginning with an underscore are the sequential-fit modes, which are about
    how a *run* applies these rows rather than about the rows, so they are not
    constraints and are skipped here.
    """
    if not isinstance(payload, dict):
        return ()
    rows: list[Gsas2Constraint] = []
    for group, entries in payload.items():
        if group.startswith("_") or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, (list, tuple)) or len(entry) < 4:
                continue
            kind = str(entry[-1])
            terms = tuple(
                (_float(pair[0]) or 0.0,
                 _variable_name(pair[1], phases, histograms, atoms))
                for pair in entry[:-3]
                if isinstance(pair, (list, tuple)) and len(pair) == 2)
            value = entry[-3]
            rows.append(Gsas2Constraint(
                kind=kind, group=str(group), terms=terms,
                value=value if isinstance(value, str) else _float(value),
                vary=None if entry[-2] is None else bool(entry[-2])))
    return tuple(rows)


def read_gsas2_gpx(path: str | Path, *,
                   diagnostics: list[Diagnostic] | None = None) -> Gsas2Model:
    """Read a GSAS-II ``.gpx`` project file.

    Returns what the file states — phases with their refine flags, histograms
    with their instrument coefficients and ranges, the sample broadening each
    phase fitted in each histogram, the constraints, and the variable list the
    last refinement used.  Call :func:`to_structure` for a
    :class:`~rietx.schemas.Structure`; the instrument facts stay on the model,
    because a ``Structure`` cannot hold them and inventing fields for them would
    be the union-with-blanks that ``ProjectModel`` exists to avoid.

    ``diagnostics`` collects what the reader **could not carry across**, by
    name: an image, a single-crystal histogram, a time-of-flight profile whose
    coefficients this build does not name, restraints.  Nothing is dropped in
    silence.

    Raises :class:`Gsas2GpxError` naming the file and the reason — including for
    a global outside :data:`ALLOWED_GLOBALS`, which refuses the file entire
    rather than reading part of a project.
    """
    p = Path(path)
    items = _read_tree(p)

    phases: list[Gsas2Phase] = []
    histograms: list[Gsas2Histogram] = []
    hap: dict[tuple[str, str], Gsas2Hap] = {}
    hap_source: list[tuple[str, dict]] = []
    reported: list[str] = []
    constraints_payload: Any = None
    covariance: dict = {}
    controls: dict = {}

    for item in items:
        headed = _labelled(item)
        if headed is None:
            reported.append("a tree item this reader could not label")
            continue
        label, payload = headed
        children = {str(c[0]): c[1] for c in item[1:]
                    if isinstance(c, (list, tuple)) and len(c) == 2}
        kind = item_kind(label)
        stance, what = TREE_ITEM_STANCE.get(kind, (None, ""))

        if kind == "PWDR":
            histograms.append(_histogram(label, payload, children))
        elif kind == "Phases":
            for child_label, data in children.items():
                if isinstance(data, dict):
                    phase = _phase(child_label, data)
                    phases.append(phase)
                    for hist_label, entry in (data.get("Histograms") or {}).items():
                        if isinstance(entry, dict):
                            hap_source.append((phase.name, (hist_label, entry)))  # type: ignore[arg-type]
        elif kind == "Covariance":
            covariance = payload if isinstance(payload, dict) else {}
        elif kind == "Constraints":
            constraints_payload = payload
        elif kind == "Controls":
            controls = payload if isinstance(payload, dict) else {}
        elif kind == "Restraints":
            if isinstance(payload, dict) and any(
                    bool(v) for v in payload.values() if isinstance(v, dict)):
                reported.append(
                    "the project states restraints, which this reader does not "
                    "carry; rietx has its own restraint model and the file's "
                    "targets and weights are not translated")
        elif stance is Stance.REPORTED:
            reported.append(f"{label!r} is {what}, which this reader does not carry")
        elif stance is None:
            reported.append(
                f"{label!r} is a tree item this reader has no stance on, so "
                f"nothing of it reached the model")

    for phase_name, (hist_label, entry) in hap_source:
        hap[(phase_name, str(hist_label))] = _hap(phase_name, str(hist_label), entry)

    for hist in histograms:
        if hist.constant_wavelength:
            continue
        named = HISTOGRAM_TYPES.get(hist.kind)
        if named is None:
            reported.append(
                f"histogram {hist.name!r} states the type {hist.kind!r}, which "
                f"this reader cannot name, so its coefficients are carried "
                f"under the file's own keys and nothing is assumed about them")
        else:
            reported.append(
                f"histogram {hist.name!r} is {named} rather than "
                f"constant-wavelength; its coefficients are on the model under "
                f"the file's own names, but they are a different profile "
                f"function from the one this build fits")

    ran_phases = {}
    ran_atoms: dict[int, tuple[str, int]] = {}
    for item in items:
        headed = _labelled(item)
        if headed is not None and headed[0] == "Phases":
            for child in item[1:]:
                if not (isinstance(child, (list, tuple)) and len(child) == 2):
                    continue
                data = child[1]
                if not isinstance(data, dict):
                    continue
                number = data.get("pId")
                if isinstance(data.get("ranId"), int):
                    ran_phases[data["ranId"]] = number if number is not None else child[0]
                for index, row in enumerate(data.get("Atoms", [])):
                    if isinstance(row, list) and row and isinstance(row[-1], int):
                        ran_atoms[row[-1]] = (str(child[0]), index)
    ran_histograms = {}
    for hist_item in items:
        headed = _labelled(hist_item)
        if headed is None or not headed[0].startswith("PWDR"):
            continue
        payload = headed[1]
        data = payload[0] if isinstance(payload, (list, tuple)) and payload else {}
        if isinstance(data, dict) and isinstance(data.get("ranId"), int):
            ran_histograms[data["ranId"]] = data.get("hId", "?")

    rvals = covariance.get("Rvals", {}) if isinstance(covariance, dict) else {}
    model = Gsas2Model(
        phases=tuple(phases),
        histograms=tuple(histograms),
        hap=hap,
        constraints=_constraints(constraints_payload, ran_phases, ran_histograms,
                                 ran_atoms),
        vary_list=tuple(str(v) for v in _sequence(covariance.get("varyList"))),
        esds=tuple(
            v for v in (_float(x) for x in _sequence(covariance.get("sig")))
            if v is not None),
        rwp=_float(rvals.get("Rwp")),
        gof=_float(rvals.get("GOF")),
        chi2=_float(rvals.get("chisq")),
        n_observations=int(rvals["Nobs"]) if rvals.get("Nobs") is not None else None,
        n_variables=int(rvals["Nvars"]) if rvals.get("Nvars") is not None else None,
        converged=(None if rvals.get("converged") is None
                   else bool(rvals["converged"])),
        version=(str(controls["LastSavedUsing"])
                 if controls.get("LastSavedUsing") is not None else None),
        saved_as=(str(controls["LastSavedAs"])
                  if controls.get("LastSavedAs") is not None else None),
        path=str(p),
        unsupported=tuple(reported))

    if diagnostics is not None:
        _report(model, diagnostics)
    return model


def _report(model: Gsas2Model, diagnostics: list[Diagnostic]) -> None:
    """Append one diagnostic per thing the read could not carry across."""
    named = model.path or "<model>"
    for text in model.unsupported:
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS2_GPX_ITEM_NOT_READ",
            message=f"{named}: {text}"))
    for hist in model.histograms:
        if hist.background is None:
            continue
        diagnostics.append(Diagnostic(
            level="info", code="GSAS2_GPX_BACKGROUND_NOT_CARRIED",
            message=(
                f"{named}: histogram {hist.name!r} fitted GSAS-II's "
                f"{hist.background.function!r} background with "
                f"{len(hist.background.coefficients)} terms"
                + (f", {hist.background.n_debye} Debye term(s)"
                   if hist.background.n_debye else "")
                + (f" and {hist.background.n_peaks} fitted peak(s)"
                   if hist.background.n_peaks else "")
                + " — the coefficients are on `model.histograms[…].background` "
                  "and the background to fit with is yours to choose"),
            where=[f"histograms.{hist.number}.background"]))
    for phase in model.phases:
        if phase.magnetic:
            diagnostics.append(Diagnostic(
                level="warning", code="GSAS2_GPX_PHASE_MAGNETIC",
                message=(
                    f"{named}: phase {phase.name!r} is a magnetic phase "
                    f"(GSAS-II phase type {phase.kind!r}) and rietx has no "
                    f"magnetic scattering model"),
                where=[f"phases.{phase.number}"]))
        elif phase.magnetic_partner:
            diagnostics.append(Diagnostic(
                level="warning", code="GSAS2_GPX_PHASE_MAGNETIC",
                message=(
                    f"{named}: phase {phase.name!r} is nuclear, and the "
                    f"project states a magnetic partner for it "
                    f"({phase.magnetic_partner!r}).  The sites and cell import "
                    f"correctly; what does not is the magnetic scattering the "
                    f"file's own Rwp includes, so a fit of this structure is "
                    f"not comparable with the file's figures"),
                where=[f"phases.{phase.number}"]))
    if model.constraints:
        equivalences = sum(1 for c in model.constraints if c.is_equivalence)
        diagnostics.append(Diagnostic(
            level="warning", code="GSAS2_GPX_CONSTRAINT_NOT_CARRIED",
            message=(
                f"{named}: the refinement carried {len(model.constraints)} "
                f"constraint(s), of which {equivalences} are equivalences that "
                f"`Refinement.tie_equal` could restore one call each.  None is "
                f"applied by `to_structure`, because a tie between parameters "
                f"this build has not built yet is not a tie — they are on "
                f"`model.constraints`, each printing as the relation it states"),
            where=["constraints"]))


#: Uiso (Å²) → Biso (Å²).  GSAS-II stores U on the atom record and rietx's
#: ``Atom.biso`` is B, so this factor is the whole conversion.
EIGHT_PI_SQUARED = 8.0 * 3.141592653589793 ** 2


def to_structure(model: Gsas2Model, *, phase: str | int | None = None,
                 diagnostics: list[Diagnostic] | None = None):
    """Build a :class:`~rietx.schemas.Structure` from a parsed ``.gpx``.

    **The refine flags come across**, which is the point: the cell carries
    GSAS-II's single ``Cell[0]`` flag, and each site's coordinates, occupancy
    and displacement carry the ``X``, ``F`` and ``U`` letters from its own atom
    record.  An empty flag string is the file saying *held*, not the file saying
    nothing, so it maps onto ``vary=False`` rather than onto a schema default.

    ``Uiso`` becomes ``Biso`` through :data:`EIGHT_PI_SQUARED`.  Species are
    normalised to IUCr spelling (``Mn+3`` → ``Mn3+``), reported as
    ``GSAS2_GPX_SPECIES_NORMALISED`` where ``diagnostics=`` is passed.

    ``phase`` picks one of a multi-phase file by name or by GSAS-II's own phase
    number; with several phases and none named this raises rather than taking
    the first, following ``read_pattern``'s ``scan=`` rule that a selection is
    the caller's.

    Four refusals, each naming what it would otherwise have dropped:

    * **A magnetic phase.**  rietx has no magnetic scattering model, so the
      nuclear half is all that could be imported and it would look complete —
      the stance :mod:`~rietx.io.projects.coverage` declares for the sibling
      readers, reached here through the same sentence.
    * **A macromolecular phase**, whose atom records carry three more columns
      before the label than this reader reads.
    * **An anisotropic site.**  The six ``Uij`` are on the model, but which
      off-diagonal convention they follow is not settled by any file in this
      repo, and a wrong factor of two is a silently wrong Debye-Waller factor at
      high Q.  Lifting this needs one measurement rather than an opinion: feed
      the tensors through ``crystallography.wyckoff.adp_basis`` and see whether
      they lie in the site-symmetry subspace, which a wrong convention would
      break.  The ``.EXP`` reader makes the same refusal for the same reason.
    * **A Pawley phase**, whose intensities are the model and are not carried
      here; the cell and the extraction's own reflections stay on the file.

    And two the corpus taught rather than the specification: a phase with **no
    sites**, which GSAS-II fits by extracting intensities, and a **negative
    Uiso**, which a real refinement reaches and which no structure can hold.
    Both name the phase; a schema refusal that got past them would name a
    ``Parameter`` and never the file, so the final build converts one.
    """
    import gemmi
    import numpy as np

    import rietx as rx

    from ...crystallography.wyckoff import coordinate_basis, stabilizer_rotations
    from .fullprof import normalize_species

    named = model.path or "<model>"
    if not model.phases:
        raise Gsas2GpxError(
            f"{named}: states no phases — a project written before any phase "
            f"was entered carries histograms alone")
    chosen = model.phase(phase)

    if chosen.magnetic:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} is magnetic (GSAS-II phase type "
            f"{chosen.kind!r}) and rietx has no magnetic scattering model.  "
            f"Importing its nuclear half would hand back a structure that "
            f"looks complete while the magnetic contribution went unmentioned. "
            f" The numbers are on `model.phases`")
    if chosen.kind.lower().startswith("macro"):
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} is macromolecular (GSAS-II phase "
            f"type {chosen.kind!r}), whose atom records carry residue and "
            f"chain columns this reader does not read — so the phase would "
            f"arrive with the wrong columns rather than with none")
    if chosen.pawley:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} is a Pawley phase, whose refined "
            f"quantities are the reflection intensities rather than the sites. "
            f" Building a structure from its atoms would describe a model the "
            f"file did not fit.  rietx has its own Pawley mode "
            f"(`mode='pawley'`); the cell is on `model.phases`")
    aniso = [a.label for a in chosen.atoms if a.anisotropic]
    if aniso:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} has {len(aniso)} anisotropic "
            f"site(s) ({', '.join(aniso)}).  The six Uij values are on "
            f"`model.phases[…].atoms[…].uij`, but which off-diagonal "
            f"convention GSAS-II wrote them in is not settled by any file in "
            f"this repo, and a wrong factor of two is a silently wrong "
            f"Debye-Waller factor at high Q")
    if not chosen.atoms:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} states no sites.  GSAS-II fits a "
            f"phase with none by extracting its intensities, and rietx's own "
            f"Le Bail mode needs one dummy site to hang the phase on, so there "
            f"is no structure here to build — the cell and symmetry are on "
            f"`model.phases`")
    negative = [(a.label, a.uiso) for a in chosen.atoms
                if a.uiso is not None and a.uiso < 0.0]
    if negative:
        worst = min(negative, key=lambda row: row[1])
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} states a negative Uiso on "
            f"{len(negative)} site(s), the largest on {worst[0]!r} at "
            f"{worst[1]:.5g} Å².  A refinement really can end there and "
            f"GSAS-II really does store it, but exp(-B·s²) with B < 0 grows "
            f"without bound at high Q, so the value is carried on "
            f"`model.phases[…].atoms[…].uiso` and not built into a structure.  "
            f"Deciding what it should have been is yours")
    if not chosen.space_group:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} states no space-group symbol, so "
            f"there is no symmetry to build the structure under")
    try:
        sg = gemmi.SpaceGroup(chosen.space_group)
    except (ValueError, RuntimeError) as exc:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} states the space-group symbol "
            f"{chosen.space_group!r}, which is not one this build resolves "
            f"({exc}).  The cell and sites are on `model.phases`") from exc

    rewrites: dict[str, tuple[str, list[str]]] = {}
    frozen: list[str] = []
    sites: list[dict] = []
    for i, atom in enumerate(chosen.atoms):
        species = normalize_species(atom.species)
        if species != atom.species:
            rewrites.setdefault(atom.species, (species, []))[1].append(
                f"phases.0.atoms.{i}.species")
        # GSAS-II's X flag means "refine as permitted by symmetry", and rietx
        # models exactly that: coordinates enter θ as site-symmetry DOFs and a
        # site with none of them refuses a vary request outright.  So the flag
        # is carried through the same basis GSAS-II was speaking about rather
        # than onto x/y/z directly — the ``.EXP`` reader's rule, and it fires on
        # the same kind of site.
        movable = len(coordinate_basis(stabilizer_rotations(
            sg, np.array([atom.x, atom.y, atom.z])))) > 0
        if atom.refine_xyz and not movable:
            frozen.append(atom.label)
        sites.append(dict(
            label=atom.label, species=species, xyz=(atom.x, atom.y, atom.z),
            vary_xyz=atom.refine_xyz and movable,
            occupancy=atom.occupancy, vary_occupancy=atom.refine_occupancy,
            biso=(atom.uiso or 0.0) * EIGHT_PI_SQUARED, vary_biso=atom.refine_u))

    # Every schema object the conversion builds is built **here**, inside one
    # try, rather than as it goes.  The two shapes the corpus contains are
    # refused by name above; this is the class rather than a third instance,
    # because a schema refusal that reached a caller would name a ``Parameter``
    # and never the file — the one thing ``io/CLAUDE.md`` forbids a reader, and
    # a thing WP-1118 has already paid for once in ``read_gsas_prm``.
    try:
        a, b, c, alpha, beta, gamma = chosen.cell
        varies = chosen.refine_cell
        structure = rx.Structure(phases=[rx.Phase(
            name=chosen.name or "phase",
            space_group=chosen.space_group,
            cell=rx.Cell(
                a=rx.Parameter(value=a, min=1.0, vary=varies),
                b=rx.Parameter(value=b, min=1.0, vary=varies),
                c=rx.Parameter(value=c, min=1.0, vary=varies),
                alpha=rx.Parameter(value=alpha, vary=varies),
                beta=rx.Parameter(value=beta, vary=varies),
                gamma=rx.Parameter(value=gamma, vary=varies)),
            atoms=[rx.Atom(
                label=site["label"], species=site["species"],
                x=rx.Parameter(value=site["xyz"][0], vary=site["vary_xyz"]),
                y=rx.Parameter(value=site["xyz"][1], vary=site["vary_xyz"]),
                z=rx.Parameter(value=site["xyz"][2], vary=site["vary_xyz"]),
                occ=rx.Parameter(value=site["occupancy"], min=0.0, max=1.5,
                                 vary=site["vary_occupancy"]),
                biso=rx.Parameter(value=site["biso"], min=0.0, max=25.0,
                                  vary=site["vary_biso"]))
                for site in sites],
            scale=rx.Parameter(value=1e-3, min=0.0, transform="softplus"))])
    except ValueError as exc:
        raise Gsas2GpxError(
            f"{named}: phase {chosen.name!r} states values this build's "
            f"schema refuses ({exc}).  The file's own numbers are on "
            f"`model.phases`") from exc

    if diagnostics is not None:
        for raw, (canonical, wheres) in rewrites.items():
            diagnostics.append(Diagnostic(
                level="info", code="GSAS2_GPX_SPECIES_NORMALISED",
                message=(f"species {raw!r} in {named} read as {canonical!r} — "
                         f"GSAS-II writes an ionic charge sign first; "
                         f"normalised to IUCr spelling"),
                where=wheres))
        if frozen:
            diagnostics.append(Diagnostic(
                level="info", code="GSAS2_GPX_COORDINATES_SYMMETRY_FIXED",
                message=(
                    f"{named}: {len(frozen)} site(s) carry GSAS-II's X refine "
                    f"flag but sit on fully fixed special positions "
                    f"({', '.join(frozen)}), so nothing of them was free in "
                    f"GSAS-II either — its flag means 'refine as permitted by "
                    f"symmetry', and symmetry permits none"),
                where=[f"phases.0.atoms.{i}.x"
                       for i, a in enumerate(chosen.atoms)
                       if a.label in frozen]))
        diagnostics.append(Diagnostic(
            level="info", code="GSAS2_GPX_SCALE_NOT_COMPARABLE",
            message=(
                f"{named}: phase {chosen.name!r}'s scale is seeded at 1e-3 and "
                f"not taken from the file.  GSAS-II's histogram scale and its "
                f"per-phase scale fold their own normalisation into one "
                f"number, so neither is a rietx scale — refine it rather than "
                f"trusting a converted value.  The file's own numbers are on "
                f"`model.histograms[…].sample['Scale']` and "
                f"`model.hap[…].scale`"),
            where=["phases.0.scale"]))
    return structure
