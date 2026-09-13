"""The PowderLine recipe: an interchange format this package did not invent.

`PowderLine <https://github.com/NSLS2/PowderLine>`_ (BSD-3-Clause, D. Olds,
NSLS-II beamline 28-ID-1) is a **file-less JSON recipe** — one document carrying
the pattern, the instrument, the phases, the background and a refine flag per
parameter — dispatched to one of several engines behind a single result shape.
:func:`read_recipe` turns such a document into the four objects this package
refines with, and :func:`write_recipe_tables` writes a
:class:`~rietx.RefinementResult` back out as their four tables.  Together they
are what an upstream ``src/powderline/rietx/`` engine branch would call.

**Why adopt someone else's JSON contract rather than define one.**  The rule
this package carries from WP-1303 is that a dedicated tool surface earns its
place only where it gates, renders, audits or parallelises.  A recipe does the
last of those: PowderLine's whole point is running one specimen through several
engines and comparing, which is a job no python API can do for a code it cannot
import.  So the format is worth speaking, and speaking *theirs* — their rule 3
(an engine translates the existing recipe, it does not define its own) is what
makes the comparison mean anything.

**What the fixtures are worth, and it is more than the format.**  Two committed
examples carry the same pattern refined by **two** independent engines, GSAS-II
and TOPAS, with both outputs in the repository.  That is the ``FAP.EXP``
cross-code check with a second opinion attached, and the second opinion
disagrees: on the DRX_33 cathode the two engines' cubic ``a`` differ by
**2 665 ppm**, because the recipe co-refines size and strain on a pattern where
GSAS-II itself reports two SVD singularities and a 100 % correlation.
``tests/data/README.md`` § v1.3 has the table.  Read that as the calibration for
any cross-code claim made through this format: **the cells are the comparable
quantity and the broadening coefficients are not.**

Conventions
-----------

Every unit conversion below was **measured against the committed LaB6 GSAS-II
output before this module was written**, never adopted from a docstring:
their peak list's ``sigma_squared`` column reproduces ``U tan²θ + V tanθ + W``
to six decimals on all 49 reflections, its ``gamma`` exceeds the instrument-only
``X/cosθ + Y tanθ + Z`` by exactly the GSAS-II default size and strain terms, and
the drawn FWHM of their own ``y_calc − y_bkg`` matches √(8ln2)·√sig/100 to
0.1-0.9 % (the residue is the SH/L asymmetry, absent from the check).  The
constants agree with upstream's own second engine
(``powderline/topas/conversions.py``), which is corroboration rather than the
source.  The full table, row by row and with how each was established, is
``tests/data/README.md`` § The convention table.

Two rows are not measurable from any committed recipe and are handled
differently *because* of it:

``Zero``
    **Refused when non-zero.**  Upstream states its unit twice and disagrees
    with itself — ``easydiff/conversions.py`` converts it as centidegrees,
    ``config_loader.py`` annotates it "degrees 2theta" — and the two readings
    differ by 100×, which is a wrong cell rather than a slightly wrong one.
    Every committed recipe has ``Zero = 0``, where the readings coincide, so
    nothing real is refused today.  This is the ``CIF_CELL_ANGLE_CORRECTED``
    rule of the root ``CLAUDE.md``: where two statements contradict each other,
    choosing is the caller's.

``SH/L``
    **Adopted, not measured**: ``axial_sl = axial_hl = SH/L / 2``, the symmetric
    Finger-Cox-Jephcoat reading of GSAS-II's combined ``(S+H)/L``.  At the
    fixtures' ``SH/L = 5e-4`` on 0.027° peaks the two candidate splits are
    indistinguishable in the drawn profile, which ``test_recipe.py`` asserts
    rather than assumes — so the row is honest about being a convention.

What is refused, and why each
-----------------------------

Upstream's rule 4 is that an engine rejects loudly what it cannot represent,
and never silently ignores a refine flag.  This reader refuses by name:

* ``schema_name`` other than ``GSASII_Rietveld`` — ``GSASII_SPF`` is single-peak
  fitting, which this package does as :func:`~rietx.indexing.fit_peaks` and not
  as a recipe: a recipe describes a refinement, and ``fit_peaks`` refines
  nothing;
* ``Type`` other than ``PXC`` (constant-wavelength X-ray);
* a ``size_broadening``/``strain_broadening`` ``model`` other than
  ``isotropic`` — upstream raises ``NotImplementedError`` on these itself;
* a non-zero ``Zero``, and a non-zero ``Z``;
* a background peak whose Lorentzian γ the Gaussian-only
  :class:`~rietx.schemas.instrument.BackgroundPeak` cannot express.

A **fixed** value the model reaches its identity at is *dropped* rather than
refused, with a ``RECIPE_FIELD_DROPPED`` diagnostic naming it: ``Z = 0`` is no
constant Lorentzian, and a background peak's γ below one 2θ step of the
recipe's own pattern is a width the data cannot hold.  That split — a fixed
identity is a report, a live value is a contradiction — is the reader-repair
rule of the root ``CLAUDE.md`` applied one format over.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..crystallography.dispersion import dispersion
from ..crystallography.lattice import cell_volume
from ..model.forward import seed_phase_scales
from ..model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from ..params.vector import background_parameters, background_peak_parameters
from ..schemas.common import Diagnostic, Parameter
from ..schemas.instrument import (
    BackgroundChebyshev,
    BackgroundPeak,
    EmissionLine,
    Geometry,
    Instrument,
    ProfileTCHZ,
    Source,
)
from ..schemas.pattern import PatternData
from ..schemas.structure import Atom, Cell, Phase, Structure
from ..strategy.staged import RefinementPlan, Stage

__all__ = ["Recipe", "RecipeError", "read_recipe", "write_recipe_tables"]


# --- measured conversion constants ------------------------------------------
#
# Each is one number and it is written once.  The measurement that fixed it is
# in this module's docstring and in ``tests/data/README.md``; the test that
# keeps it true is ``test_recipe.py::test_conventions_reproduce_the_reference``,
# which recomputes the reference peak list's own columns from the recipe.

#: GSAS-II Gaussian variance (centideg²) → a Caglioti FWHM² term (deg²).
#: 8·ln2 turns a variance into a FWHM², 1e-4 turns centideg² into deg².
GAUSS_CENTIDEG2_TO_DEG2 = 8.0 * math.log(2.0) * 1e-4

#: GSAS-II Lorentzian FWHM (centideg) → deg.
CENTIDEG_TO_DEG = 1e-2

#: Coefficient of λ[Å]/(D[µm]·cosθ) in the GSAS-II isotropic size FWHM, in
#: degrees.  Equivalently a Scherrer constant of exactly 1: 0.018/180·π⁻¹·… —
#: see the module docstring's measurement.
SIZE_COEF_DEG = 1.8 / 100.0

#: Coefficient of µ[1e-6 Δd/d]·tanθ in the GSAS-II isotropic strain FWHM, deg.
STRAIN_COEF_DEG = SIZE_COEF_DEG / 100.0

#: Uiso (Å²) → Biso (Å²).
EIGHT_PI_SQ = 8.0 * math.pi**2

#: The schema versions this reader has been checked against.  A recipe
#: declaring anything else is *read anyway* with ``RECIPE_SCHEMA_UNTESTED``
#: rather than refused: upstream's models are ``extra="allow"`` for schema
#: evolution, and refusing a minor bump would make this reader the strictest
#: consumer of a format designed to be lenient.  A version whose *shape* has
#: actually moved fails at the field it moved, naming it.
KNOWN_SCHEMA_VERSIONS = ("0.26.0",)

#: The one ``schema_name`` this reader speaks.
RIETVELD_SCHEMA = "GSASII_Rietveld"


class RecipeError(ValueError):
    """A recipe this reader refuses, naming the field that caused it."""


@dataclass(frozen=True)
class Recipe:
    """One PowderLine recipe, resolved into what this package refines with.

    ``structure``/``instrument``/``pattern`` go straight to
    :class:`~rietx.Refinement` and :meth:`~rietx.Refinement.fit`; ``plan`` and
    ``limits`` are the recipe's own refinement intent, so a caller reproducing
    the recipe passes both rather than picking a preset::

        recipe = read_recipe("input.json")
        ref = rx.Refinement(recipe.structure, recipe.instrument)
        result = ref.fit(recipe.pattern, plan=recipe.plan,
                         two_theta_limits=recipe.limits)

    ``diagnostics`` carries every field dropped, every convention assumed and
    every value re-seeded — it is the channel the refusals' quieter half goes
    down, and a caller that ignores it is not being told what was changed.
    """

    structure: Structure
    instrument: Instrument
    pattern: PatternData
    plan: RefinementPlan
    #: ``payload.fit_range``, inclusive at both ends (upstream's own mask), or
    #: ``None`` where the recipe states none.
    limits: tuple[float, float] | None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    #: ``schema_name`` and ``schema_version`` as the document declared them.
    schema_name: str = RIETVELD_SCHEMA
    schema_version: str = KNOWN_SCHEMA_VERSIONS[0]
    #: the recipe's own phase-name order, which the four tables are written in.
    phase_names: tuple[str, ...] = ()


# --- the [value, refine_flag, min, max] 4-tuple ------------------------------


def _spec(entry: Any, path: str) -> tuple[float | None, bool, float | None,
                                          float | None]:
    """One ``[value, refine_flag, min, max]`` entry, or the all-absent state.

    ``None`` for the whole entry, and ``[null, false, null, null]``, both mean
    "this parameter is not spoken about" — the recipes use them
    interchangeably.  A ``value`` of ``None`` beside ``refine_flag=true`` means
    "refine, from whatever the structure or the instrument block already says",
    which is how every committed recipe spells a freed cell parameter.
    """
    if entry is None:
        return (None, False, None, None)
    if not isinstance(entry, (list, tuple)) or len(entry) != 4:
        raise RecipeError(
            f"{path}: a refinement parameter is [value, refine_flag, min, max], "
            f"four elements; got {entry!r}")
    value, flag, lo, hi = entry
    if flag is not None and not isinstance(flag, bool):
        raise RecipeError(
            f"{path}: refine_flag must be true, false or null; got {flag!r}")
    return (None if value is None else float(value), bool(flag),
            None if lo is None else float(lo),
            None if hi is None else float(hi))


def _apply(param: Parameter, entry: Any, path: str, *,
           diagnostics: list[Diagnostic], scale: float = 1.0,
           allow_bounds: bool = True) -> Parameter:
    """Write one 4-tuple onto an existing :class:`Parameter`, in rietx units.

    ``scale`` converts the recipe's unit to this package's.  The recipe's
    ``min``/``max`` are carried even though upstream documents them as "not
    implemented in GSAS-II": honouring a stated bound is the conservative
    reading, and it is recorded as a difference rather than silently dropped.
    """
    value, flag, lo, hi = _spec(entry, path)
    if value is not None:
        param.value = value * scale
    param.vary = flag
    if allow_bounds and (lo is not None or hi is not None):
        if lo is not None:
            param.min = lo * scale
        if hi is not None:
            param.max = hi * scale
        diagnostics.append(Diagnostic(
            level="info", code="RECIPE_BOUND_HONOURED",
            message=(
                f"{path} declares min/max, which PowderLine documents as not "
                f"implemented in GSAS-II; this refinement honours them, so a "
                f"bound hit here is a difference from the reference engine, "
                f"not a bug"),
            where=[path]))
    return param


def _is_off(entry: Any) -> bool:
    """True when a 4-tuple says nothing at all — absent, or null and unfree."""
    value, flag, lo, hi = _spec(entry, "<probe>")
    return value is None and not flag and lo is None and hi is None


# --- the reader --------------------------------------------------------------


def read_recipe(source: str | Path | dict,
                *, diagnostics: list[Diagnostic] | None = None) -> Recipe:
    """Read a PowderLine ``GSASII_Rietveld`` recipe.

    ``source`` is a path to the recipe file or an already-parsed dict.  **Pass
    the path** wherever one exists: the format is file-less by design, so a
    recipe carries its whole pattern inline and a 4 096-channel one is 0.4 MB
    of JSON.  That is upstream's contract and not this package's to change, but
    it is a payload that should cross a filesystem rather than anything else.

    ``diagnostics`` is the same opt-in channel
    :func:`~rietx.io.read_pattern` and
    :func:`~rietx.structure_from_cif` take: pass a list to receive every
    dropped field, honoured bound and assumed convention.  The returned
    :class:`Recipe` carries them too, so the argument is for a caller
    accumulating across several reads.

    Raises :class:`RecipeError` — a ``ValueError`` — naming the field, for
    anything this package cannot represent.  See the module docstring for the
    list and the reason behind each.
    """
    diags: list[Diagnostic] = [] if diagnostics is None else diagnostics
    doc = _load(source)

    name = doc.get("schema_name")
    if name != RIETVELD_SCHEMA:
        raise RecipeError(
            f"schema_name: this reader speaks {RIETVELD_SCHEMA!r}; got {name!r}. "
            + ("GSASII_SPF is single-peak fitting. Call rietx.fit_peaks(data, "
               "instrument, positions) for that — it fits the peaks you name "
               "and refines nothing, so there is no recipe to run."
               if name == "GSASII_SPF" else
               "The recipe must declare a schema_name; PowderLine accepts "
               "'GSASII_Rietveld' and 'GSASII_SPF'."))
    version = str(doc.get("schema_version", ""))
    if version not in KNOWN_SCHEMA_VERSIONS:
        diags.append(Diagnostic(
            level="warning", code="RECIPE_SCHEMA_UNTESTED",
            message=(
                f"recipe declares schema_version {version!r}; this reader was "
                f"checked against {', '.join(KNOWN_SCHEMA_VERSIONS)}. Reading "
                f"it anyway — PowderLine's models allow extra fields on "
                f"purpose — but a field whose meaning moved will be read with "
                f"its old meaning"),
            where=["schema_version"]))

    payload = doc.get("payload")
    if not isinstance(payload, dict):
        raise RecipeError("payload: missing, or not an object")

    pattern, limits = _read_pattern(payload, diags)
    instrument = _read_instrument(payload, pattern, limits, diags)
    structure, phase_names = _read_phases(payload, instrument, diags)
    _decline_dispersion_off_table(instrument, structure, diags)
    _seed_scales(structure, instrument, pattern, limits, diags)
    plan = _read_plan(payload, structure, instrument, diags)

    _refuse_single_peak_fitting(payload, diags)

    return Recipe(structure=structure, instrument=instrument, pattern=pattern,
                  plan=plan, limits=limits, diagnostics=diags,
                  schema_name=name, schema_version=version,
                  phase_names=tuple(phase_names))


def _load(source: str | Path | dict) -> dict:
    if isinstance(source, dict):
        return source
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RecipeError(f"{path}: cannot be read ({exc.strerror})") from exc
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecipeError(
            f"{path}: not valid JSON — {exc.msg} at line {exc.lineno} "
            f"column {exc.colno}") from exc
    if not isinstance(doc, dict):
        raise RecipeError(f"{path}: the top level of a recipe is an object, "
                          f"got {type(doc).__name__}")
    return doc


def _read_pattern(payload: dict,
                  diags: list[Diagnostic]) -> tuple[PatternData,
                                                    tuple[float, float] | None]:
    """``xrd_data`` → :class:`PatternData`, and ``fit_range`` → the limits.

    σ = 1/√w, which is the weights' own definition (w = 1/σ²) and what
    upstream's second engine does.  A **zero** weight is upstream's way of
    excluding a channel, and it has no finite σ, so those channels become an
    ``excluded_regions`` entry rather than an infinity — the two codes exclude
    the same points by different mechanisms and the mechanism is this package's
    to choose.
    """
    xrd = payload.get("xrd_data")
    if not isinstance(xrd, dict):
        raise RecipeError("payload.xrd_data: missing, or not an object")
    try:
        tth = np.asarray(xrd["tth"], dtype=float)
        obs = np.asarray(xrd["Itth"], dtype=float)
        w = np.asarray(xrd["Itth_weights"], dtype=float)
    except KeyError as exc:
        raise RecipeError(
            f"payload.xrd_data.{exc.args[0]}: missing; a recipe's pattern is "
            f"tth, Itth and Itth_weights") from exc
    if not (len(tth) == len(obs) == len(w)):
        raise RecipeError(
            f"payload.xrd_data: tth, Itth and Itth_weights must be the same "
            f"length; got {len(tth)}, {len(obs)}, {len(w)}")
    if len(tth) == 0:
        raise RecipeError("payload.xrd_data: the pattern is empty")

    excluded: list[tuple[float, float]] = []
    zero = w <= 0.0
    if zero.any():
        sigma = np.where(zero, 1.0, 1.0 / np.sqrt(np.where(zero, 1.0, w)))
        for lo, hi in _runs(tth, zero):
            excluded.append((lo, hi))
        diags.append(Diagnostic(
            level="info", code="RECIPE_ZERO_WEIGHT_EXCLUDED",
            message=(
                f"{int(zero.sum())} channel(s) carry weight 0, which is how a "
                f"recipe excludes a point; they are carried as "
                f"{len(excluded)} excluded region(s) rather than as an "
                f"infinite sigma"),
            value=float(zero.sum())))
    else:
        sigma = 1.0 / np.sqrt(w)

    metadata: dict[str, str] = {}
    for key in ("filename", "UID"):
        if xrd.get(key):
            metadata[key] = str(xrd[key])

    pattern = PatternData(two_theta=tth.tolist(), intensity=obs.tolist(),
                          sigma=sigma.tolist(), excluded_regions=excluded,
                          metadata=metadata)

    limits = None
    rng = payload.get("fit_range")
    if rng is not None:
        if not isinstance(rng, (list, tuple)) or len(rng) != 2:
            raise RecipeError(
                f"payload.fit_range: two elements [min, max]; got {rng!r}")
        lo = float(tth[0]) if rng[0] is None else float(rng[0])
        hi = float(tth[-1]) if rng[1] is None else float(rng[1])
        if not lo < hi:
            raise RecipeError(
                f"payload.fit_range: [{lo}, {hi}] is empty or inverted")
        limits = (lo, hi)
        _report_fitted_channels(tth, w, limits, diags)
    return pattern, limits


def _report_fitted_channels(tth: np.ndarray, w: np.ndarray,
                            limits: tuple[float, float],
                            diags: list[Diagnostic]) -> None:
    """Say how many channels ``fit_range`` actually selects, and which.

    A Rwp is a number over a denominator, and this package's rule for comparing
    against another code is to check the channel count matches *before*
    believing the comparison (root ``CLAUDE.md`` § Conventions).  A recipe's
    ``fit_range`` is a pair of angles, not a channel set, and the two are not
    the same statement: on the committed fixtures the inclusive mask this
    package applies selects **3 767** channels where GSAS-II's own
    ``fit_profile.txt`` shows it fitted **3 768** — it keeps the first channel
    *past* the upper limit (15.001 32° for a limit of 15°).

    One channel in 3 768 moves no Rwp anybody would read, but the fact belongs
    in the open rather than in a footnote, and **the rule that produced their
    extra channel is not inferable from two files on one grid** — so nothing is
    snapped here.  A caller reproducing another engine's residual exactly
    passes that engine's own channel set as ``two_theta_limits``.
    """
    mask = (tth >= limits[0]) & (tth <= limits[1]) & (w > 0.0)
    n = int(mask.sum())
    if n < 10:
        raise RecipeError(
            f"payload.fit_range {list(limits)} leaves {n} channel(s) of "
            f"{tth.size}; there is nothing to fit in that range")
    inside = tth[mask]
    diags.append(Diagnostic(
        level="info", code="RECIPE_FIT_RANGE_CHANNELS",
        message=(
            f"fit_range {list(limits)} selects {n} of {tth.size} channels, "
            f"{inside[0]:.6f} to {inside[-1]:.6f} deg, on an inclusive mask at "
            f"both ends. A recipe states angles and an engine fits channels, "
            f"and the two need not agree to the channel — check this count "
            f"against the reference engine's before comparing any Rwp"),
        where=["payload.fit_range"], value=float(n)))


def _runs(x: np.ndarray, mask: np.ndarray) -> list[tuple[float, float]]:
    """Contiguous runs of ``mask`` as closed 2θ intervals of ``x``."""
    out: list[tuple[float, float]] = []
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return out
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[breaks + 1]))
    ends = np.concatenate((idx[breaks], [idx[-1]]))
    step = float(np.median(np.diff(x))) if x.size > 1 else 0.0
    for s, e in zip(starts, ends):
        out.append((float(x[s]) - 0.5 * step, float(x[e]) + 0.5 * step))
    return out


def _read_instrument(payload: dict, pattern: PatternData,
                     limits: tuple[float, float] | None,
                     diags: list[Diagnostic]) -> Instrument:
    inst = payload.get("instrument")
    if not isinstance(inst, dict):
        raise RecipeError(
            "payload.instrument: missing; a GSASII_Rietveld recipe requires it")
    init = inst.get("initialization")
    if not isinstance(init, list) or not init or not isinstance(init[0], dict):
        raise RecipeError(
            "payload.instrument.initialization: a list of two dicts "
            "[Iparm1, Iparm2]")
    iparm = init[0]

    kind = _iparm(iparm, "Type")
    if kind != "PXC":
        raise RecipeError(
            f"payload.instrument.initialization[0].Type: {kind!r}. This reader "
            f"handles 'PXC' — constant-wavelength X-ray — only; 'PNC' neutron "
            f"and every time-of-flight type put a different quantity on the "
            f"x axis than PatternData holds")

    par = inst.get("parameterization") or {}
    lam_entry = (par.get("wavelength")
                 if not _is_off(par.get("wavelength")) else None)
    lam = _iparm(iparm, "Lam")
    if lam is None:
        raise RecipeError(
            "payload.instrument.initialization[0].Lam: missing; a PXC recipe "
            "must state its wavelength")
    line = EmissionLine(wavelength=Parameter(value=float(lam), unit="A"))
    if lam_entry is not None:
        _apply(line.wavelength, lam_entry,
               "payload.instrument.parameterization.wavelength", diagnostics=diags)
        if line.wavelength.vary:
            raise RecipeError(
                "payload.instrument.parameterization.wavelength: flagged for "
                "refinement. For one histogram λ and the cell enter only as the "
                "product d = λ/(2 sin θ), so a free λ beside a free cell is a "
                "flat direction and this package refuses it — calibrate λ "
                "against a standard with its cell held instead")

    pol = _iparm(iparm, "Polariz.")
    source = Source(lines=[line],
                    polarization=Parameter(
                        value=0.99 if pol is None else float(pol),
                        min=0.0, max=1.0))
    if not _is_off(par.get("polarization")):
        _apply(source.polarization, par["polarization"],
               "payload.instrument.parameterization.polarization",
               diagnostics=diags)

    profile = ProfileTCHZ()
    broadening = (par.get("broadening") or {})
    for letter, attr, scale in (("U", "u", GAUSS_CENTIDEG2_TO_DEG2),
                                ("V", "v", GAUSS_CENTIDEG2_TO_DEG2),
                                ("W", "w", GAUSS_CENTIDEG2_TO_DEG2),
                                ("X", "x", CENTIDEG_TO_DEG),
                                ("Y", "y", CENTIDEG_TO_DEG)):
        raw = _iparm(iparm, letter)
        path = f"payload.instrument.parameterization.broadening.{letter}"
        param = getattr(profile, attr)
        # Checked *before* assignment: ``Base`` validates on assignment, so a
        # negative value would come back as pydantic's bounds error naming a
        # field rather than as the refusal that names the recipe's own letter.
        declared, _, _, _ = _spec(broadening.get(letter), path)
        if declared is None and raw is not None:
            declared = float(raw)
        if declared is not None:
            _refuse_negative_width(letter, attr, param, declared, scale)
            param.min = min(param.min, declared * scale)
            param.value = declared * scale
        _apply(param, broadening.get(letter), path, diagnostics=diags,
               scale=scale)
        _widen(param, f"instrument.profile.{attr}")

    _refuse_constant_lorentzian(iparm, broadening, diags)

    geometry = Geometry(kind="debye_scherrer")
    shl = _iparm(iparm, "SH/L")
    if shl:
        half = 0.5 * float(shl)
        geometry.axial_sl = Parameter(value=half, min=0.0, max=0.2)
        geometry.axial_hl = Parameter(value=half, min=0.0, max=0.2)
        diags.append(Diagnostic(
            level="info", code="RECIPE_CONVENTION_ASSUMED",
            message=(
                f"SH/L = {float(shl):g} is GSAS-II's combined (S+H)/L; it is "
                f"split evenly into axial_sl = axial_hl = {half:g}, the "
                f"symmetric Finger-Cox-Jephcoat reading. No committed recipe "
                f"can distinguish that from an uneven split"),
            where=["instrument.geometry.axial_sl",
                   "instrument.geometry.axial_hl"],
            value=half))
    axial = (par.get("corrections") or {}).get("axial_divergence")
    if not _is_off(axial):
        _apply(geometry.axial_sl, axial,
               "payload.instrument.parameterization.corrections."
               "axial_divergence", diagnostics=diags, scale=0.5)
        _apply(geometry.axial_hl, axial,
               "payload.instrument.parameterization.corrections."
               "axial_divergence", diagnostics=diags, scale=0.5)

    instrument = Instrument(source=source, geometry=geometry, profile=profile)
    _read_zero_shift(iparm, par, instrument, diags)
    _read_background(payload, pattern, limits, instrument, diags)
    return instrument


def _decline_dispersion_off_table(instrument: Instrument, structure: Structure,
                                  diags: list[Diagnostic]) -> None:
    """Anomalous scattering, where the bundled table does not reach.

    ``Source.dispersion`` is on by default since v1.0 because species and λ are
    all it needs — but the bundled Cromer-Liberman tabulation covers the 3-70
    keV powder band, and a PDF-beamline recipe is outside it: λ = 0.1665 Å is
    74.5 keV.  Declining it there is not a loss.  f′ and f″ are edge effects and
    every edge of every element in these recipes is more than an order of
    magnitude below 74 keV, so f → f₀ is the correct limit rather than a
    concession; what would be wrong is extrapolating a table past its band.

    Declined **only** on the exception the table itself raises, and only for the
    species this structure actually has — a recipe inside the band keeps
    dispersion on and stays bit-identical to a hand-built model.
    """
    if instrument.source.dispersion is None:
        return
    lam = instrument.source.lines[0].wavelength.value
    species = sorted({a.species for ph in structure.phases for a in ph.atoms})
    try:
        for sym in species:
            dispersion(sym, lam)
    except ValueError as exc:
        instrument.source.dispersion = None
        diags.append(Diagnostic(
            level="info", code="RECIPE_DISPERSION_DECLINED",
            message=(
                f"anomalous scattering is declined for this recipe and f = f0 "
                f"is used: {exc}. Every absorption edge of these species is far "
                f"below this energy, so f' and f'' are negligible there and the "
                f"table's band is the limit rather than the physics — but the "
                f"result carries DISPERSION_NEGLECTED, as any dispersion=None "
                f"fit does"),
            where=["instrument.source.dispersion"]))


def _iparm(iparm: dict, key: str):
    """One ``initialization[0]`` entry: GSAS-II's ``[current, value, flag]``.

    The **second** element is the value, which is what GSAS-II calls the
    "reference" and what every committed recipe fills; the first is a working
    copy that a round trip may have moved.  Reading element 1 rather than 0 is
    what makes a recipe written back out by an engine read the same as the one
    the author typed.
    """
    entry = iparm.get(key)
    if entry is None:
        return None
    if isinstance(entry, (list, tuple)):
        if len(entry) < 2:
            raise RecipeError(
                f"payload.instrument.initialization[0].{key}: GSAS-II writes "
                f"[current, value, refine_flag]; got {entry!r}")
        return entry[1]
    return entry


def _refuse_negative_width(letter: str, attr: str, param: Parameter,
                           declared: float, scale: float) -> None:
    """A width this package transforms through softplus cannot start negative.

    ``ProfileTCHZ``'s W, X and Y are softplus-bounded at zero because a
    Lorentzian or Gaussian FWHM contribution is a width, and a negative one is
    not a shape.  GSAS-II bounds none of them, and it matters here rather than
    hypothetically: **both** committed LaB6 reference outputs converge to a
    negative Y (GSAS-II −15.81 centideg, TOPAS −8.97), so a recipe seeded from
    a previous fit will carry one.

    The failure it would cause is the silent kind.  ``to_internal`` clamps a
    non-positive value to 1e-12 before taking the inverse softplus, so a
    declared −15.81 would arrive as ~0 and the fit would answer from a model
    the recipe did not describe.  Refused by name instead.
    """
    if param.transform != "softplus" or declared >= 0.0:
        return
    raise RecipeError(
        f"instrument {letter} = {declared:g} converts to "
        f"instrument.profile.{attr} = {declared * scale:g}, and this package's "
        f"{'Gaussian variance' if attr == 'w' else 'Lorentzian FWHM'} term is "
        f"softplus-bounded at zero — a width is not a shape when it is "
        f"negative. GSAS-II bounds none of U V W X Y Z, so a recipe seeded "
        f"from a converged GSAS-II or TOPAS fit can carry a negative one (both "
        f"committed LaB6 references converge to a negative Y). Reading it "
        f"would silently give ~0 rather than the declared value, so it is "
        f"refused: start from a non-negative width, or refine X and Y from "
        f"this package's own zero")


def _widen(param: Parameter, path: str) -> None:
    """Let a recipe's starting value sit outside this package's default bounds.

    ``ProfileTCHZ`` seeds its bounds for a *lab* pattern; a 28-ID-1 recipe
    arrives with U = 18.7 centideg² (0.0104 deg²) and V = 0.60, both legal and
    both outside the seeded box.  A stored bound is the caller's claim
    everywhere else in this package, and here the caller is the recipe: so the
    default box is widened to admit the declared value rather than the value
    being clipped to the box.

    A softplus parameter's **lower** bound is never lowered past zero — that
    bound is the transform's own domain, not a seeded guess, and
    :func:`_refuse_negative_width` has already refused anything that would want
    it moved.
    """
    if param.value < param.min:
        floor = param.value - abs(param.value) - 1.0
        param.min = max(floor, 0.0) if param.transform == "softplus" else floor
    if param.value > param.max:
        param.max = param.value + abs(param.value) + 1.0


def _refuse_constant_lorentzian(iparm: dict, broadening: dict,
                                diags: list[Diagnostic]) -> None:
    """``Z`` — a constant Lorentzian term this package's profile has not got.

    **Magnitude decides, and the flag does not.**  Z = 0 is the identity: the
    recipe's width and this package's coincide exactly where the recipe starts,
    and all that is lost is a direction the fit cannot travel in — a report, so
    it is dropped and said.  A **non-zero** Z is a contradiction: the declared
    profile is already a width this one cannot express, and running it would
    answer a question nobody asked, so it is refused.

    A flagged Z at zero is dropped at ``warning`` rather than ``info``, because
    the fit then has one free parameter fewer than the reference engine and the
    difference lands in X and Y.  Upstream's rule 4 forbids ignoring a refine
    flag *silently*; this is the loud half of it.  (Their own engines differ
    here too: the TOPAS branch carries Z, the easydiffraction one converts only
    X and Y.)
    """
    raw = _iparm(iparm, "Z")
    value = 0.0 if raw is None else float(raw)
    spec_value, flag, _, _ = _spec(
        broadening.get("Z"),
        "payload.instrument.parameterization.broadening.Z")
    if spec_value is not None:
        value = spec_value
    if value != 0.0:
        raise RecipeError(
            f"payload.instrument.initialization[0].Z = {value:g}: GSAS-II's Z "
            f"is a constant term in the Lorentzian FWHM and this package's "
            f"profile has none — its width is X/cosθ + Y·tanθ, so a non-zero Z "
            f"is a peak width there is nowhere to put. Set Z to 0 (its "
            f"identity, which is dropped with a warning) and let X and Y carry "
            f"the Lorentzian")
    if raw is None and not flag:
        return
    if flag:
        diags.append(Diagnostic(
            level="warning", code="RECIPE_FLAG_DROPPED",
            message=(
                "instrument Z is flagged for refinement and this package's "
                "Lorentzian width has no constant term (X/cosθ + Y·tanθ), so "
                "the flag is not honoured: this fit runs one free parameter "
                "short of the reference engine's and whatever Z would have "
                "absorbed lands in X and Y. Z = 0 is the identity, so the "
                "starting model is unchanged"),
            where=["instrument.profile.x", "instrument.profile.y"]))
    else:
        diags.append(Diagnostic(
            level="info", code="RECIPE_FIELD_DROPPED",
            message=(
                "instrument Z = 0 fixed is no constant Lorentzian term at all, "
                "so it is dropped rather than translated; this package's "
                "Lorentzian width is X/cosθ + Y·tanθ with no constant"),
            where=["payload.instrument.initialization[0].Z"]))


def _read_zero_shift(iparm: dict, par: dict, instrument: Instrument,
                     diags: list[Diagnostic]) -> None:
    """``Zero``: the one row whose unit the format states two ways."""
    raw = _iparm(iparm, "Zero")
    value = 0.0 if raw is None else float(raw)
    entry = (par.get("corrections") or {}).get("zero_shift")
    spec_value, flag, _, _ = _spec(
        entry, "payload.instrument.parameterization.corrections.zero_shift")
    if spec_value is not None:
        value = spec_value
    if value != 0.0:
        raise RecipeError(
            f"instrument Zero = {value:g}: PowderLine states this field's unit "
            f"twice and the two statements disagree — its easydiffraction "
            f"engine converts Zero as centidegrees "
            f"(src/powderline/easydiff/conversions.py) while its config loader "
            f"annotates it 'degrees 2theta' (src/powderline/config_loader.py). "
            f"The two readings differ by 100x, which is a wrong cell rather "
            f"than a slightly wrong one, and no committed recipe carries a "
            f"non-zero Zero to settle it. Refuse rather than guess: set Zero "
            f"to 0 and refine instrument.zero_shift from this package, or ask "
            f"upstream which reading is theirs")
    instrument.zero_shift.vary = flag


def _read_background(payload: dict, pattern: PatternData,
                     limits: tuple[float, float] | None,
                     instrument: Instrument,
                     diags: list[Diagnostic]) -> None:
    bg = payload.get("background") or {}
    cheb = bg.get("chebyshev")
    if cheb is not None:
        n = int(cheb.get("num_coefficients", len(cheb.get("coefficients", []))))
        if n <= 0:
            raise RecipeError(
                f"payload.background.chebyshev.num_coefficients: {n}; a "
                f"Chebyshev background needs at least one term")
        vary = bool(cheb.get("refine_flag", False))
        instrument.background = BackgroundChebyshev.with_terms(n, vary=vary)
        diags.append(Diagnostic(
            level="info", code="RECIPE_BACKGROUND_RESEEDED",
            message=(
                f"the recipe's {n} Chebyshev coefficients are carried as a "
                f"count and a refine flag, not as values: the two codes scale "
                f"the polynomial's domain differently, so the numbers are not "
                f"the same numbers. They start at zero and refine"),
            where=["instrument.background"], value=float(n)))

    peaks = bg.get("single_peaks")
    if peaks:
        instrument.background_peaks = _read_background_peaks(
            peaks, pattern, limits, diags)


def _read_background_peaks(peaks: dict, pattern: PatternData,
                           limits: tuple[float, float] | None,
                           diags: list[Diagnostic]) -> list[BackgroundPeak]:
    """``background.single_peaks`` → :class:`BackgroundPeak`, γ permitting.

    The recipe's background peak is a pseudo-Voigt (position, intensity, σ, γ);
    this package's is a Gaussian, deliberately and with the reason on the
    class.  So the Lorentzian half has to go somewhere, and the honest split is
    by magnitude: a γ whose Lorentzian FWHM is under **one 2θ step of the
    recipe's own pattern** is a width the model could not express against these
    data whatever it did with it, and is dropped; anything larger is a real
    share of the peak's shape and is refused by name.
    """
    positions = peaks.get("positions") or []
    intensities = peaks.get("intensities") or []
    sigmas = peaks.get("pv_gaussian_sigma") or []
    gammas = peaks.get("pv_lorentzian_gamma") or []
    n = max(len(positions), len(intensities), len(sigmas), len(gammas))
    tth = np.asarray(pattern.two_theta, dtype=float)
    step = float(np.median(np.diff(tth))) if tth.size > 1 else 0.0
    lo, hi = limits if limits is not None else (tth[0], tth[-1])
    span = float(min(hi, tth[-1]) - max(lo, tth[0]))

    out: list[BackgroundPeak] = []
    for i in range(n):
        base = "payload.background.single_peaks"
        pos, pos_vary, _, _ = _spec(_at(positions, i), f"{base}.positions[{i}]")
        height, h_vary, _, _ = _spec(_at(intensities, i),
                                     f"{base}.intensities[{i}]")
        sig, s_vary, _, _ = _spec(_at(sigmas, i),
                                  f"{base}.pv_gaussian_sigma[{i}]")
        gam, g_vary, _, _ = _spec(_at(gammas, i),
                                  f"{base}.pv_lorentzian_gamma[{i}]")
        if pos is None and height is None and sig is None and gam is None:
            # the all-null peak every recipe writes as a placeholder
            continue

        gam_fwhm = 0.0 if gam is None else abs(gam) * CENTIDEG_TO_DEG
        if gam_fwhm > step:
            raise RecipeError(
                f"{base}.pv_lorentzian_gamma[{i}] = {gam:g} centideg is a "
                f"Lorentzian FWHM of {gam_fwhm:.4g} deg, wider than the "
                f"pattern's own {step:.4g} deg step. This package's background "
                f"peak is a Gaussian only — a broad feature sits on a "
                f"polynomial that can already absorb the difference between a "
                f"Gaussian and a pseudo-Voigt, so no mixing parameter exists "
                f"to put this in. Describe the feature with sigma alone, or "
                f"refine it as a phase")
        if gam_fwhm > 0.0:
            diags.append(Diagnostic(
                level="info", code="RECIPE_FIELD_DROPPED",
                message=(
                    f"background peak {i}'s Lorentzian gamma is a FWHM of "
                    f"{gam_fwhm:.3g} deg, under the pattern's {step:.3g} deg "
                    f"step, so it is dropped: this package's background peak "
                    f"is Gaussian and nothing narrower than a channel could "
                    f"be seen anyway"),
                where=[f"instrument.background_peaks.{i}"], value=gam_fwhm))
        if g_vary:
            diags.append(Diagnostic(
                level="warning", code="RECIPE_FLAG_DROPPED",
                message=(
                    f"background peak {i}'s Lorentzian gamma is flagged for "
                    f"refinement and has no counterpart here, so that flag is "
                    f"not honoured; the Gaussian fwhm carries the width"),
                where=[f"instrument.background_peaks.{i}.fwhm"]))

        fwhm = (5.0 if sig is None
                else max(abs(sig) * math.sqrt(8.0 * math.log(2.0))
                         * CENTIDEG_TO_DEG, 1e-3))
        peak = BackgroundPeak(
            position=Parameter(value=0.0 if pos is None else float(pos),
                               vary=pos_vary, unit="deg"),
            height=Parameter(value=0.0 if height is None else abs(float(height)),
                             vary=h_vary, min=0.0, unit="counts",
                             transform="softplus"),
            label=f"recipe background peak {i}")
        peak.fwhm.value = max(fwhm, peak.fwhm.min)
        peak.fwhm.vary = s_vary
        _warn_peak_is_a_polynomial(i, peak, span, diags)
        out.append(peak)
    return out


def _warn_peak_is_a_polynomial(i: int, peak: BackgroundPeak, span: float,
                               diags: list[Diagnostic]) -> None:
    """A Gaussian wider than its window is a low-order polynomial in disguise.

    Not a tuned threshold and not this reader's opinion:
    :class:`~rietx.schemas.instrument.BackgroundPeak`'s own record measured it
    — on a 16-term polynomial the same peak walked to 24.8° wide, "becomes a
    low-order background term in all but name", and the fit returned 617
    ``HIGH_CORRELATION`` findings.  The rule it states is *declare a peak
    instead of extra polynomial terms, never on top of them*.

    A peak whose FWHM reaches the fitted span never falls to half height inside
    the window, so over that window it carries no more curvature than the
    polynomial already has.  The LaB6 recipe declares exactly this: σ = 1000
    centideg is a 23.5° FWHM on a 14° range, refined **alongside** six
    Chebyshev terms.  Both reference engines confirm it from opposite ends —
    GSAS-II's peak ran to 8.77e10 °2θ at esd 0, TOPAS's stayed at 1.63° with a
    12.3° width and an esd 51× its own value.

    Reported, not repaired.  The recipe asked for the peak, so it gets the
    peak; what this cannot do is let a caller read the answer without knowing.
    """
    if span <= 0.0 or peak.fwhm.value < span:
        return
    diags.append(Diagnostic(
        level="warning", code="RECIPE_BACKGROUND_PEAK_DEGENERATE",
        message=(
            f"background peak {i} starts at a FWHM of {peak.fwhm.value:.3g} "
            f"deg over a fitted range of {span:.3g} deg, so it never reaches "
            f"half height inside the window and carries no curvature the "
            f"Chebyshev terms have not got. Expect it to correlate with the "
            f"low-order background at |rho| = 1 and the stage to spend its "
            f"whole budget walking that valley — both reference engines did, "
            f"in opposite directions. A background peak is a substitute for "
            f"polynomial terms, not an addition to them"),
        where=[f"instrument.background_peaks.{i}.fwhm"],
        value=peak.fwhm.value))


def _at(seq, i):
    return seq[i] if i < len(seq) else None


def _read_phases(payload: dict, instrument: Instrument,
                 diags: list[Diagnostic]) -> tuple[Structure, list[str]]:
    phases = payload.get("phases")
    if not isinstance(phases, dict) or not phases:
        raise RecipeError(
            "payload.phases: a GSASII_Rietveld recipe needs at least one phase")
    lam = instrument.source.lines[0].wavelength.value
    built: list[Phase] = []
    names: list[str] = []
    for key, block in phases.items():
        phase, name = _read_phase(key, block, lam, diags)
        built.append(phase)
        names.append(name)
    return Structure(phases=built), names


def _read_phase(key: str, block: dict, lam: float,
                diags: list[Diagnostic]) -> tuple[Phase, str]:
    st = (block or {}).get("structure")
    if not isinstance(st, dict):
        raise RecipeError(f"payload.phases.{key}.structure: missing")
    name = str(st.get("phase_name") or key)
    sg = st.get("space_group")
    if not sg:
        raise RecipeError(f"payload.phases.{key}.structure.space_group: missing")
    cell_values = st.get("unit_cell")
    if not isinstance(cell_values, dict):
        raise RecipeError(f"payload.phases.{key}.structure.unit_cell: missing")
    par = block.get("parameterization") or {}

    cell = Cell(**{
        axis: Parameter(value=float(cell_values[axis]),
                        unit="A" if axis in "abc" else "deg")
        for axis in ("a", "b", "c", "alpha", "beta", "gamma")})
    cell_par = par.get("unit_cell") or {}
    for axis in ("a", "b", "c", "alpha", "beta", "gamma"):
        _apply(getattr(cell, axis), cell_par.get(axis),
               f"payload.phases.{key}.parameterization.unit_cell.{axis}",
               diagnostics=diags)

    atoms = _read_atoms(key, st, par, diags)
    phase = Phase(name=name, space_group=str(sg), cell=cell, atoms=atoms)

    scale_entry = (par.get("scale"))
    _, scale_vary, _, _ = _spec(scale_entry,
                                f"payload.phases.{key}.parameterization.scale")
    phase.scale.vary = scale_vary

    _read_broadening(key, par.get("peak_broadening") or {}, phase, lam, diags)
    return phase, name


def _read_atoms(key: str, st: dict, par: dict,
                diags: list[Diagnostic]) -> list[Atom]:
    sites = st.get("atoms")
    if not isinstance(sites, dict) or not sites:
        raise RecipeError(f"payload.phases.{key}.structure.atoms: missing")
    atom_par = par.get("atoms") or {}
    out: list[Atom] = []
    for label, site in sites.items():
        base = f"payload.phases.{key}.structure.atoms.{label}"
        element = site.get("element")
        if not element:
            raise RecipeError(f"{base}.element: missing")
        adp = str(site.get("ADP") or "Uiso")
        if adp == "Uaniso":
            raise RecipeError(
                f"{base}.ADP = 'Uaniso': anisotropic displacement through a "
                f"recipe is not read yet. This package refines U^ij as "
                f"site-symmetry-allowed patterns (Atom.aniso), so a recipe's "
                f"six free components need the symmetry check that builds "
                f"them; set ADP to 'Uiso' or refine the structure through the "
                f"python API")
        if adp != "Uiso":
            raise RecipeError(
                f"{base}.ADP = {adp!r}: PowderLine's vocabulary is 'Uiso' or "
                f"'Uaniso'")
        uiso = site.get("Uiso")
        atom = Atom(label=str(label), species=str(element),
                    x=Parameter(value=float(site.get("x", 0.0))),
                    y=Parameter(value=float(site.get("y", 0.0))),
                    z=Parameter(value=float(site.get("z", 0.0))),
                    occ=Parameter(value=float(site.get("occupancy", 1.0)),
                                  min=0.0, max=1.5),
                    biso=Parameter(
                        value=0.5 if uiso is None
                        else EIGHT_PI_SQ * float(uiso),
                        min=0.0, max=25.0, unit="A^2"))
        spec = atom_par.get(label) or {}
        pbase = f"payload.phases.{key}.parameterization.atoms.{label}"
        for axis in ("x", "y", "z"):
            _apply(getattr(atom, axis), spec.get(axis), f"{pbase}.{axis}",
                   diagnostics=diags)
        _apply(atom.occ, spec.get("occupancy"), f"{pbase}.occupancy",
               diagnostics=diags)
        _apply(atom.biso, spec.get("Uiso"), f"{pbase}.Uiso",
               diagnostics=diags, scale=EIGHT_PI_SQ)
        if spec.get("Uaniso"):
            raise RecipeError(
                f"{pbase}.Uaniso: anisotropic displacement through a recipe is "
                f"not read yet — see the ADP refusal above")
        out.append(atom)
    return out


def _read_broadening(key: str, block: dict, phase: Phase, lam: float,
                     diags: list[Diagnostic]) -> None:
    """Isotropic size and strain, split into this package's four parameters.

    GSAS-II carries **one** magnitude per effect plus a Lorentzian share
    ``LG_eta``; this package carries a Lorentzian and a Gaussian parameter per
    effect and no share.  So the translation is a split, not a rename: η of the
    magnitude becomes the Lorentzian coefficient and (1 − η) the Gaussian one —
    which is what upstream's own TOPAS engine writes as two convolutions.

    ``lor_*`` is a FWHM coefficient and ``gauss_*`` a **variance**, so the
    Gaussian half is squared on the way in.
    """
    for which in ("size_broadening", "strain_broadening"):
        spec = block.get(which)
        if spec is None:
            continue
        model = str(spec.get("model", "isotropic"))
        if model != "isotropic":
            raise RecipeError(
                f"payload.phases.{key}.parameterization.peak_broadening."
                f"{which}.model = {model!r}: PowderLine itself raises "
                f"NotImplementedError for this, so no engine reads it. Use "
                f"'isotropic'; this package's anisotropic strain is the "
                f"Stephens block on Phase.microstrain, reachable from the "
                f"python API")

    _split(key, block.get("size_broadening"), "size_broadening",
           "isotropic_size", phase,
           lor_attr="lor_size", gauss_attr="gauss_size",
           coefficient=lambda size: SIZE_COEF_DEG * lam / (math.pi * size),
           diags=diags)
    _split(key, block.get("strain_broadening"), "strain_broadening",
           "isotropic_strain", phase,
           lor_attr="lor_strain", gauss_attr="gauss_strain",
           coefficient=lambda mu: STRAIN_COEF_DEG * mu / math.pi,
           diags=diags)


def _split(key: str, spec: dict | None, block_key: str, magnitude_key: str,
           phase: Phase, *, lor_attr: str, gauss_attr: str, coefficient,
           diags) -> None:
    """One GSAS-II (magnitude, ``LG_eta``) pair → this package's two halves.

    The dead-column question, and why the answer is not a seed.  Both halves
    are softplus-bounded with ``min=0``, and softplus's slope *is* its value
    (dp/du = 1 − e⁻ᵖ ≈ p), so a coefficient at exactly zero has a gradient of
    1e-12 and TRF cannot move it — a free parameter nothing can change, which
    is the shape WP-1076 exists to keep out of a result.  ``Stage.seed`` would
    lift it, but only to a number this reader would have to invent, and the two
    reference engines disagree about η by more than any seed would decide (one
    returns η = 0.078, the other 1.5e4, outside [0, 1] entirely).

    So a half that starts at its off state is left **fixed and said**, not
    freed: the recipe's own η stands, the magnitude refines, and the fit runs
    one parameter short of the reference with a ``warning`` naming it.  A
    caller who wants the split explored sets the coefficient themselves — it is
    an ordinary parameter on the phase.
    """
    if spec is None:
        return
    base = (f"payload.phases.{key}.parameterization.peak_broadening."
            f"{block_key}")
    magnitude, mag_vary, _, _ = _spec(spec.get(magnitude_key),
                                      f"{base}.{magnitude_key}")
    eta, eta_vary, _, _ = _spec(spec.get("LG_eta"), f"{base}.LG_eta")
    if magnitude is None:
        _report_engine_default(base, magnitude_key, mag_vary, diags)
        return
    if magnitude <= 0.0:
        raise RecipeError(
            f"{base}.{magnitude_key} = {magnitude:g}: a crystallite size or a "
            f"microstrain must be positive")
    share = 1.0 if eta is None else float(eta)
    if not 0.0 <= share <= 1.0:
        raise RecipeError(
            f"{base}.LG_eta = {share:g}: the Lorentzian share is a fraction of "
            f"one effect's magnitude, so it lies in [0, 1]. (GSAS-II does not "
            f"bound its own `;mx` and the committed reference output has it at "
            f"1.5e4, which is a runaway rather than a share — do not copy a "
            f"refined value back into a recipe without checking it)")

    total = coefficient(magnitude)
    lor = getattr(phase, lor_attr)
    gauss = getattr(phase, gauss_attr)
    lor.value = share * total
    gauss.value = ((1.0 - share) * total) ** 2

    free = mag_vary or eta_vary
    lor.vary = free and lor.value > 0.0
    gauss.vary = free and gauss.value > 0.0
    for attr, param in ((lor_attr, lor), (gauss_attr, gauss)):
        if free and not param.vary:
            diags.append(Diagnostic(
                level="warning", code="RECIPE_FLAG_DROPPED",
                message=(
                    f"{base} is flagged for refinement, but LG_eta = {share:g} "
                    f"puts phases.*.{attr} at exactly its off state, where a "
                    f"softplus parameter's gradient is its own value and TRF "
                    f"cannot move it. It is held rather than declared free and "
                    f"left standing still; the other half refines, so this fit "
                    f"has one free parameter fewer than the reference engine's"),
                where=[f"phases.*.{attr}"]))
    if eta_vary and lor.vary and gauss.vary:
        diags.append(Diagnostic(
            level="info", code="RECIPE_FLAG_TRANSLATED",
            message=(
                f"{base}.LG_eta is flagged for refinement; this package has no "
                f"single mixing parameter, so the recipe's (magnitude, eta) "
                f"pair becomes two free coefficients — phases.*.{lor_attr} and "
                f"phases.*.{gauss_attr} — which is the same two degrees of "
                f"freedom written differently"),
            where=[f"phases.*.{lor_attr}", f"phases.*.{gauss_attr}"]))


def _seed_scales(structure: Structure, instrument: Instrument,
                 pattern: PatternData, limits: tuple[float, float] | None,
                 diags: list[Diagnostic]) -> None:
    """The recipe's ``scale`` is a start in another code's units, so re-seed it.

    Every code normalises the phase scale differently, and the committed
    fixtures show how differently: for one specimen GSAS-II converges to
    3.77e-2 where TOPAS converges to 2.61e-6, four orders apart, and every
    recipe simply declares ``scale = 1``.  Carrying that 1 across would be a
    number that looks like a measurement and is not one — the
    ``RECIPE_BACKGROUND_RESEEDED`` case again, on the other linear parameter.
    """
    trimmed = pattern
    if limits is not None:
        tth = np.asarray(pattern.two_theta, dtype=float)
        keep = (tth >= limits[0]) & (tth <= limits[1])
        if keep.any():
            sigma = (None if pattern.sigma is None
                     else np.asarray(pattern.sigma)[keep].tolist())
            trimmed = PatternData(
                two_theta=tth[keep].tolist(),
                intensity=np.asarray(pattern.intensity)[keep].tolist(),
                sigma=sigma)
    ratio = seed_phase_scales(structure, instrument, trimmed)
    diags.append(Diagnostic(
        level="info", code="RECIPE_SCALE_RESEEDED",
        message=(
            f"the recipe's phase scale(s) are re-seeded to match the summed "
            f"calculated intensity to the data (factor {ratio:.4g}, split "
            f"evenly): a scale factor's normalisation is each code's own — on "
            f"the committed fixtures GSAS-II and TOPAS converge four orders of "
            f"magnitude apart for the same specimen — so a recipe's scale is a "
            f"start, never a value to carry across"),
        where=["phases.*.scale"], value=ratio))


#: What GSAS-II puts in a size/strain block whose magnitude the recipe leaves
#: null, **measured** off the committed LaB6 reference rather than read from a
#: manual: the peak list's ``gamma`` exceeds the instrument-only
#: ``X/cosθ + Y·tanθ + Z`` by exactly ``1.8·λ/(π·D·cosθ) + 0.018·µ·tanθ/π``
#: centidegrees at these two values, on every reflection.  Two free constants
#: landing on round numbers across 49 reflections is not a coincidence.
GSASII_DEFAULT_SIZE_UM = 1.0
GSASII_DEFAULT_MICROSTRAIN = 1000.0


def _report_engine_default(base: str, magnitude_key: str, mag_vary: bool,
                           diags: list[Diagnostic]) -> None:
    """A block that exists with a null magnitude is not a block that says zero.

    The LaB6 recipe carries ``{"model": "isotropic", "isotropic_size": null,
    "LG_eta": null}`` — the block is present and states no value — and GSAS-II
    fills that with its own project defaults, 1 µm and 1000 × 10⁻⁶ Δd/d.  On
    that pattern the strain default alone is 0.057° × tanθ against peaks 0.027°
    wide: a quarter of the width at the top of the range, not a rounding.

    **The defaults are not adopted**, and the reason is the same one that keeps
    a reader from inventing a convention: an engine's project default is an
    artefact of that engine, the recipe says nothing, and this package's
    silence is zero.  Adopting them would put broadening into the model that no
    document asked for.  What *is* owed is saying so, because it is a stated
    model difference and it explains a stated part of any Rwp gap.
    """
    default = (GSASII_DEFAULT_SIZE_UM if magnitude_key == "isotropic_size"
               else GSASII_DEFAULT_MICROSTRAIN)
    unit = "µm" if magnitude_key == "isotropic_size" else "×1e-6 Δd/d"
    diags.append(Diagnostic(
        level="info", code="RECIPE_ENGINE_DEFAULT_DECLINED",
        message=(
            f"{base}.{magnitude_key} is present but null, which GSAS-II fills "
            f"with its own project default of {default:g} {unit} (measured off "
            f"the committed LaB6 reference peak list). This package reads a "
            f"null as silence and leaves the sample broadening at zero rather "
            f"than adopting another engine's default — so this fit's model has "
            f"no sample broadening where the reference engine's has some, and "
            f"the instrument terms will differ by however much that was"
            + ("; the recipe also flags it for refinement, which needs a "
               "non-zero start" if mag_vary else "")),
        where=[base], value=default))


def _read_plan(payload: dict, structure: Structure, instrument: Instrument,
               diags: list[Diagnostic]) -> RefinementPlan:
    """One stage freeing every flagged path — the recipe's own semantics.

    PowderLine runs a single refinement pass over everything flagged, so the
    faithful translation is a one-stage plan, and a one-stage plan is all
    endpoint: :meth:`RefinementPlan.stage_ftols` loosens nothing, which is the
    right reading of a recipe that declares no order.

    ``refinement_cycles`` is **not** translated.  It is GSAS-II's cycle count,
    and this package's :attr:`Stage.max_iter` is a runaway guard rather than a
    schedule — mapping one onto the other would make a recipe's "5 cycles" look
    like a stopping rule it is not.
    """
    controls = payload.get("refinement_controls") or {}
    cycles = controls.get("refinement_cycles")
    if cycles is not None:
        diags.append(Diagnostic(
            level="info", code="RECIPE_FIELD_DROPPED",
            message=(
                f"refinement_controls.refinement_cycles = {cycles} is not "
                f"translated: it is GSAS-II's cycle count, while a Stage's "
                f"max_iter here is a runaway guard and the stopping rule is "
                f"the solver's ftol. The fit converges rather than counting"),
            where=["payload.refinement_controls.refinement_cycles"],
            value=float(cycles)))
    algorithm = controls.get("refinement_algorithm")
    if algorithm:
        diags.append(Diagnostic(
            level="warning", code="RECIPE_FIELD_DROPPED",
            message=(
                f"refinement_controls.refinement_algorithm = {algorithm!r} is "
                f"not read; this fit runs the package's own solver "
                f"(scipy TRF by default, `solver=\"lm\"` for the bounded "
                f"Levenberg-Marquardt)"),
            where=["payload.refinement_controls.refinement_algorithm"]))

    flagged = _flagged_paths(structure, instrument)
    if not flagged:
        diags.append(Diagnostic(
            level="warning", code="RECIPE_NOTHING_REFINED",
            message=(
                "no parameter in this recipe is flagged for refinement, so the "
                "plan has one stage that frees nothing — a simulation. The "
                "answer is the model evaluated at its declared values"),
            where=["payload"]))
        return RefinementPlan(stages=[Stage("recipe", [])])

    stages: list[Stage] = []
    remaining = set(flagged)
    for name, keys in _RECIPE_STAGE_ORDER:
        group = sorted(p for p in remaining if _group_of(p) in keys)
        if group:
            stages.append(Stage(name, group))
            remaining -= set(group)
    if remaining:  # a group nobody claimed — free it last rather than lose it
        stages.append(Stage("rest", sorted(remaining)))
    if len(stages) > 1:
        diags.append(Diagnostic(
            level="info", code="RECIPE_PLAN_STAGED",
            message=(
                f"the recipe's {len(flagged)} flagged parameters are freed over "
                f"{len(stages)} stages ({', '.join(s.name for s in stages)}) "
                f"in the McCusker (1999) turn-on order, not all at once. "
                f"Staging here is cumulative — every stage keeps what the "
                f"earlier ones freed — so the last stage *is* the recipe's "
                f"single pass over everything flagged, reached by a route that "
                f"survives a cold start. A recipe declares which parameters "
                f"refine; the order is the engine's, and this one measured a "
                f"two-phase recipe walk a monoclinic cell to a = 4 231 A when "
                f"freed in one step"),
            where=["payload.refinement_controls"], value=float(len(stages))))
    return RefinementPlan(stages=stages)


#: McCusker *et al.* (1999) turn-on order, restricted to the groups a recipe
#: can flag.  One entry per stage: a name and the parameter groups it frees.
#: Nothing here is a *selection* — every flagged path is freed by the end and
#: staging is cumulative, so the final free set is exactly the recipe's.  The
#: order is `RefinementPlan.mccusker_structural`'s, minus the corrections no
#: recipe carries; keeping it in one table rather than in the function body is
#: so the two can be read against each other.
_RECIPE_STAGE_ORDER: tuple[tuple[str, frozenset[str]], ...] = (
    ("scale_bkg", frozenset({"scale", "background"})),
    ("zero", frozenset({"zero"})),
    ("cell", frozenset({"cell"})),
    ("profile_w", frozenset({"profile_w"})),
    ("profile", frozenset({"profile", "axial", "polarization"})),
    ("background_peaks", frozenset({"background_peak"})),
    ("sample_broadening", frozenset({"broadening"})),
    ("coordinates", frozenset({"dof"})),
    ("displacement", frozenset({"biso", "occ"})),
)


def _group_of(path: str) -> str:
    """Which turn-on group a dot-path belongs to.

    Prefix matching on the paths this reader itself builds, so it is a closed
    vocabulary rather than a guess about arbitrary paths — anything unmatched
    falls to the ``rest`` stage instead of being dropped.
    """
    if path == "instrument.zero_shift":
        return "zero"
    if path == "instrument.profile.w":
        return "profile_w"
    if path.startswith("instrument.profile."):
        return "profile"
    if path.startswith("instrument.geometry.axial"):
        return "axial"
    if path == "instrument.source.polarization":
        return "polarization"
    if path.startswith("instrument.background_peaks."):
        return "background_peak"
    if path.startswith("instrument.background."):
        return "background"
    if path.endswith(".scale"):
        return "scale"
    if ".cell." in path:
        return "cell"
    if path.endswith((".lor_size", ".lor_strain",
                      ".gauss_size", ".gauss_strain")):
        return "broadening"
    if ".dof." in path:
        return "dof"
    if path.endswith(".biso"):
        return "biso"
    if path.endswith(".occ"):
        return "occ"
    return "rest"


def _flagged_paths(structure: Structure, instrument: Instrument) -> set[str]:
    """Exact dot-paths for every parameter the recipe flagged.

    Exact paths rather than globs on purpose: a recipe states a flag per
    parameter, so a glob would free something the recipe held.  The one
    concession is that fnmatch treats a literal path as a pattern matching
    itself, which is what makes an exact path legal in ``Stage.turn_on``.
    """
    paths: set[str] = set()
    if instrument.zero_shift.vary:
        paths.add("instrument.zero_shift")
    for attr in ("u", "v", "w", "x", "y"):
        if getattr(instrument.profile, attr).vary:
            paths.add(f"instrument.profile.{attr}")
    for attr in ("axial_sl", "axial_hl"):
        if getattr(instrument.geometry, attr).vary:
            paths.add(f"instrument.geometry.{attr}")
    if instrument.source.polarization.vary:
        paths.add("instrument.source.polarization")
    for sub, param in background_parameters(instrument.background):
        if param.vary:
            paths.add(f"instrument.background.{sub}")
    for sub, param in background_peak_parameters(instrument.background_peaks):
        if param.vary:
            paths.add(f"instrument.background_peaks.{sub}")
    for ip, phase in enumerate(structure.phases):
        if phase.scale.vary:
            paths.add(f"phases.{ip}.scale")
        for axis in ("a", "b", "c", "alpha", "beta", "gamma"):
            if getattr(phase.cell, axis).vary:
                paths.add(f"phases.{ip}.cell.{axis}")
        for attr in ("lor_size", "lor_strain", "gauss_size", "gauss_strain"):
            if getattr(phase, attr).vary:
                paths.add(f"phases.{ip}.{attr}")
        for ia, atom in enumerate(phase.atoms):
            if atom.occ.vary:
                paths.add(f"phases.{ip}.atoms.{ia}.occ")
            if atom.biso.vary:
                paths.add(f"phases.{ip}.atoms.{ia}.biso")
            if atom.x.vary or atom.y.vary or atom.z.vary:
                paths.add(f"phases.{ip}.atoms.{ia}.dof.*")
    return paths


def _refuse_single_peak_fitting(payload: dict,
                                diags: list[Diagnostic]) -> None:
    """The top-level ``single_peaks`` block, which is not the background one."""
    peaks = payload.get("single_peaks")
    if not peaks:
        return
    live = [k for k, v in peaks.items()
            if isinstance(v, list) and any(not _is_off(e) for e in v)]
    if not live:
        return
    raise RecipeError(
        f"payload.single_peaks: free-standing peak fitting ({', '.join(live)}) "
        f"is not part of a refinement here — rietx.fit_peaks(data, instrument, "
        f"positions) fits peaks you name, on its own. Note this is the "
        f"*top-level* single_peaks block; background.single_peaks, which "
        f"describes a broad background feature, is read")


# ============================================================================
# Writing the four tables back
# ============================================================================
#
# Three of the four headers are a real contract and one is not, which is a
# measurement rather than an opinion: on the committed fixtures GSAS-II and
# TOPAS write byte-identical headers for ``refined_parameters.csv``,
# ``<phase>_unit_cell_report.csv`` and ``fit_profile.txt``, and *different*
# ones for the peak list (GSAS-II's 15 columns against TOPAS's 11, agreeing on
# only nine).  So the first three are reproduced byte for byte and the peak
# list carries the columns this package can honestly fill — which is what the
# two reference engines already do.

#: ``refined_parameters.csv``, both engines, byte for byte.
REFINED_PARAMETERS_HEADER = (
    "parameter_name", "descriptive_name", "phase_name", "phase_idx",
    "atom_name", "atom_idx", "value", "esd", "category")

#: ``<phase>_unit_cell_report.csv``, both engines, byte for byte.
UNIT_CELL_HEADER = ("parameter", "value", "esd")

#: ``fit_profile.txt``, both engines, byte for byte, tab separated.
FIT_PROFILE_HEADER = ("two_theta", "y_obs", "y_weights", "y_calc", "y_diff",
                      "y_bkg", "q_values", "d_spacings")

#: ``<phase>_peak_list_report.csv``.  **Not** a contract — the two reference
#: engines disagree — so this is the columns they share, plus GSAS-II's
#: ``sigma_squared``/``gamma`` written back in its own centidegree convention,
#: minus ``F_obs_squared``.  That last omission is deliberate: an observed |F|²
#: from a Rietveld fit is I(calc) times the reflection's own obs/calc count
#: ratio, so it flatters whatever model partitioned it, and the root
#: ``CLAUDE.md`` forbids shipping one as evidence.  An absent column is honest
#: where a derived one would not be (WP-1076).
PEAK_LIST_HEADER = ("h", "k", "l", "multiplicity", "d_spacing", "2theta",
                    "sigma_squared", "gamma", "F_calc_squared", "phase")

#: ``descriptive_name`` and ``category`` per parameter family.  Where the two
#: reference engines disagree on a name, TOPAS's is taken: it says ``cell_a``
#: and ``cell`` where GSAS-II says ``phase_1_reciprocal_metric_tensor_A11`` and
#: ``reciprocal_metric_tensor``, and this package refines the direct cell, so
#: the reciprocal spelling would describe a parameter that is not here.
#: GSAS-II's ``other`` bucket for size and strain is not used either — TOPAS's
#: ``size_broadening`` / ``strain_broadening`` name the thing.
_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("scale", "phase_{ip}_scale_factor", "scale"),
    ("cell", "cell_{sub}", "cell"),
    ("lor_size", "size_lorentzian_deg", "size_broadening"),
    ("gauss_size", "size_gaussian_deg2", "size_broadening"),
    ("lor_strain", "strain_lorentzian_deg", "strain_broadening"),
    ("gauss_strain", "strain_gaussian_deg2", "strain_broadening"),
    ("biso", "atom_displacement_biso", "atom_displacement_isotropic"),
    ("occ", "atom_occupancy", "atom_occupancy"),
    ("dof", "atom_coordinate_dof_{sub}", "atom_position"),
)


def write_recipe_tables(refinement, out_dir: str | Path, *,
                        phase_names: dict[str, str] | None = None
                        ) -> dict[str, Path]:
    """Write a finished refinement as PowderLine's four output tables.

    Takes the :class:`~rietx.Refinement`, not its ``RefinementResult``, and the
    reason is the peak list: a result carries the fitted *curve* but not the
    compiled model, so the per-reflection widths and |F|² have to be read off
    the refinement — the same split that keeps a history node storing state
    rather than curves.  Everything else comes from ``refinement.result_``.

    ``phase_names`` maps this package's phase names to the recipe's own keys
    where they differ, because the file names are
    ``<phase>_unit_cell_report.csv`` and PowderLine's consumer looks them up by
    the key the recipe used.  Left ``None``, each phase's own name is used —
    which is what :attr:`Recipe.phase_names` already holds for a recipe read
    here.

    Returns ``{name: path}`` for every file written.  Nothing else is:
    ``dummy.gpx`` and ``dummy.lst`` are GSAS-II artefacts, and a project in
    this package is a ``.rex`` directory (:class:`rietx.Project`).
    """
    result = getattr(refinement, "result_", None)
    if result is None:
        raise RuntimeError(
            "write_recipe_tables needs a finished refinement: call fit() first")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = phase_names or {}

    written: dict[str, Path] = {}
    written["refined_parameters"] = _write_refined_parameters(
        result, refinement.fitted_structure, out)
    for ip, phase in enumerate(refinement.fitted_structure.phases):
        key = names.get(phase.name, phase.name)
        written[f"unit_cell:{key}"] = _write_unit_cell(result, phase, ip, key,
                                                       out)
    for key, path in _write_peak_lists(refinement, names, out).items():
        written[f"peak_list:{key}"] = path
    written["fit_profile"] = _write_fit_profile(refinement, result, out)
    return written


def _num(x: float | None) -> str:
    """One number, or an empty field where there is none.

    Empty rather than ``0``: a zero esd in these tables means *held*, which is
    a different statement from *unmeasurable*, and the two must not collapse
    (WP-1076 — a defaulted number is a claim nothing checked).
    """
    return "" if x is None else f"{float(x):.8e}"


def _write_refined_parameters(result, structure: Structure, out: Path) -> Path:
    path = out / "refined_parameters.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(REFINED_PARAMETERS_HEADER)
        for row in result.parameters:
            if not row.vary:
                continue
            desc, category, phase_name, phase_idx, atom_name, atom_idx = \
                _describe(row.path, structure)
            w.writerow([row.path, desc, phase_name,
                        "" if phase_idx is None else phase_idx,
                        atom_name, "" if atom_idx is None else atom_idx,
                        _num(row.value), _num(row.stderr), category])
    return path


def _describe(path: str, structure: Structure):
    """``(descriptive_name, category, phase, phase_idx, atom, atom_idx)``.

    Built from the dot-path, which is this package's own vocabulary, so nothing
    here becomes a second authority on what a parameter *is* — ``help.py``
    stays the one place a name is explained, and this fills the recipe format's
    four label columns and nothing else.
    """
    parts = path.split(".")
    if path.startswith("instrument.profile."):
        return (f"instrument_broadening_{parts[-1].upper()}",
                "instrument_broadening", "", None, "", None)
    if path == "instrument.zero_shift":
        return ("zero_point_correction", "instrument_correction", "", None,
                "", None)
    if path.startswith("instrument.geometry.axial"):
        return (f"axial_divergence_{parts[-1]}", "instrument_correction", "",
                None, "", None)
    if path == "instrument.source.polarization":
        return ("polarization_correction", "instrument_correction", "", None,
                "", None)
    if path.startswith("instrument.background_peaks."):
        return (f"background_peak_{parts[2]}_{parts[3]}", "background_peak",
                "", None, "", None)
    if path.startswith("instrument.background."):
        sub = parts[-1]
        n = sub[1:] if sub.startswith("c") and sub[1:].isdigit() else sub
        return (f"background_coefficient_{n}", "background", "", None, "",
                None)
    if not path.startswith("phases."):
        return (path, "other", "", None, "", None)

    ip = int(parts[1])
    phase = structure.phases[ip] if ip < len(structure.phases) else None
    phase_name = phase.name if phase is not None else ""
    atom_name, atom_idx = "", None
    if len(parts) > 3 and parts[2] == "atoms":
        atom_idx = int(parts[3])
        if phase is not None and atom_idx < len(phase.atoms):
            atom_name = phase.atoms[atom_idx].label
    tail = parts[2] if len(parts) > 2 else ""
    sub = parts[-1]
    for key, template, category in _CATEGORIES:
        if key == tail or (tail == "atoms" and key in parts):
            return (template.format(ip=ip, sub=sub), category, phase_name, ip,
                    atom_name, atom_idx)
    return (path, "other", phase_name, ip, atom_name, atom_idx)


def _write_unit_cell(result, phase: Phase, ip: int, key: str,
                     out: Path) -> Path:
    esds = {row.path: row.stderr for row in result.parameters}
    path = out / f"{key}_unit_cell_report.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(UNIT_CELL_HEADER)
        for axis in ("a", "b", "c", "alpha", "beta", "gamma"):
            # 0 rather than empty for a cell parameter with no esd row: every
            # cell parameter is *in* the model, so no row means held — by the
            # recipe or by symmetry — and 0 is what both reference engines
            # write for exactly that.  The volume below is the different case.
            esd = esds.get(f"phases.{ip}.cell.{axis}")
            w.writerow([f"cell_{axis}",
                        _num(getattr(phase.cell, axis).value),
                        _num(0.0 if esd is None else esd)])
        # The volume's esd needs the free cell block's covariance through
        # dV/d(a,b,c,alpha,beta,gamma), which nothing here propagates yet. Left
        # empty rather than written as 0: a 0 in this column means *held*, and
        # the volume of a refined cell is not held.
        w.writerow(["cell_volume",
                    _num(cell_volume(*phase.cell.lengths_angles())), ""])
    return path


def _write_peak_lists(refinement, names: dict[str, str],
                      out: Path) -> dict[str, Path]:
    rows = refinement.reflection_table()
    instrument = refinement.fitted_instrument
    by_phase: dict[str, list] = {}
    for row in rows:
        if row.line != 0:   # the primary line, which is what both engines write
            continue
        by_phase.setdefault(row.phase, []).append(row)

    written: dict[str, Path] = {}
    for phase in refinement.fitted_structure.phases:
        key = names.get(phase.name, phase.name)
        path = out / f"{key}_peak_list_report.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(PEAK_LIST_HEADER)
            for row in by_phase.get(phase.name, []):
                sig2, gam = _gsas_widths(instrument, phase, row.two_theta)
                w.writerow([row.h, row.k, row.l, row.multiplicity,
                            _num(row.d), _num(row.two_theta),
                            _num(sig2), _num(gam),
                            _num(row.f_squared), phase.name])
        written[key] = path
    return written


def _gsas_widths(instrument: Instrument, phase: Phase,
                 two_theta: float) -> tuple[float, float]:
    """This fit's widths at one reflection, in GSAS-II's own units.

    The inverse of the read conversions through the *same* constants, so the
    two directions cannot drift: a Gaussian FWHM in degrees back to a variance
    in centidegrees², a Lorentzian FWHM in degrees back to centidegrees.  The
    widths come from :mod:`rietx.model.profiles.caglioti`, the authority the
    residual itself uses, rather than being recomputed here.
    """
    theta = np.asarray([0.5 * two_theta])
    p = instrument.profile
    fwhm_g = float(gaussian_fwhm(theta, p.u.value, p.v.value, p.w.value,
                                 phase.gauss_size.value,
                                 phase.gauss_strain.value)[0])
    fwhm_l = float(lorentzian_fwhm(theta,
                                   p.x.value + phase.lor_size.value,
                                   p.y.value + phase.lor_strain.value)[0])
    sig2 = (fwhm_g / CENTIDEG_TO_DEG) ** 2 * 1e-4 / GAUSS_CENTIDEG2_TO_DEG2
    return sig2, fwhm_l / CENTIDEG_TO_DEG


def _write_fit_profile(refinement, result, out: Path) -> Path:
    """The fitted curve, on the channels the fit actually used.

    GSAS-II writes the whole scan with zeros outside the range and TOPAS writes
    only what it fitted; this writes the fitted channels, which is the set
    ``result.two_theta`` holds and the one every other number in the file
    belongs to.
    """
    path = out / "fit_profile.txt"
    lam = refinement.fitted_instrument.source.lines[0].wavelength.value
    tth = np.asarray(result.two_theta, dtype=float)
    obs = np.asarray(result.y_obs, dtype=float)
    calc = np.asarray(result.y_calc, dtype=float)
    bkg = np.asarray(result.y_background, dtype=float)
    sigma = np.asarray(result.sigma, dtype=float)
    with np.errstate(divide="ignore"):
        weights = np.where(sigma > 0, 1.0 / np.square(sigma), 0.0)
    theta = np.radians(0.5 * tth)
    s = np.sin(theta)
    q = 4.0 * math.pi * s / lam
    with np.errstate(divide="ignore"):
        d = np.where(s > 0, lam / (2.0 * s), np.inf)
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("\t".join(FIT_PROFILE_HEADER) + "\n")
        for i in range(tth.size):
            fh.write("\t".join(f"{v:.8f}" for v in (
                tth[i], obs[i], weights[i], calc[i], obs[i] - calc[i],
                bkg[i], q[i], d[i])) + "\n")
    return path
