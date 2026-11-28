"""A phase's profile coefficients read as a coherent domain size and a Δd/d.

WP-1131's reporting half, and the peer of :mod:`rietx.model.geometry`: that one
turns refined coordinates into bond lengths with esds, this one turns refined
widths into a length and a dimensionless strain with esds.  Both are
**evidence, never a verdict** — nothing here says a domain size is reasonable.

Three rules, all of them borrowed rather than invented:

* **The conversions live in one place and it is not here.**
  :mod:`rietx.model.profiles.caglioti` owns Scherrer and the tanθ law in both
  directions; this module calls them and states no constant of its own.
* **A quantity that cannot be measured is absent, not zero** (WP-1072).  A
  coefficient at its off state, a source with no wavelength and a column that
  measured nothing are three different absences and each names itself in
  ``MicrostructureTerm.unavailable``.  "At its off state" is the stored zero
  *or* the bound test's ``FLOOR_HIT`` (WP-1914), so the driver that solved the
  fit cannot change the reading.
* **The propagation is exact and single-parameter.**  Each reading is a
  function of one coefficient — ``L = (180/π)·K·λ/x`` and
  ``Δd/d = (π/360)·y`` — so J·Cov·Jᵀ is one variance and there is no
  cross-term to drop.  That is *why* the Gaussian and Lorentzian readings are
  reported separately and compared rather than combined into one number: a
  combined size is a function of two correlated columns, and this module would
  then be quoting a covariance it is not given.

**What the size is a size of.**  The phase's *own* coefficient, not
``instrument.profile.x + phases.N.lor_size``: under the instrument ⊕ sample
split the instrument terms are calibrated on a standard and frozen, so the
sample term is the specimen's whole contribution and reading it alone is the
point of the split.  A fit that never calibrated the instrument has put
instrument width into the sample term, and the size that comes back is a lower
bound — which is Scherrer's usual caveat, not a new one.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Iterable

from ..schemas.results import MicrostructureTerm, PhaseMicrostructure
from ..schemas.structure import Structure
from .profiles.caglioti import (
    SCHERRER_K,
    apparent_size_from_d_size_coefficient,
    apparent_size_from_size_coefficient,
    microstrain_from_strain_coefficient,
)

#: coefficient name → (kind, whether the stored number is a *variance*).  The
#: Gaussian pair are variances, so the FWHM coefficient behind them is the
#: square root and an esd carries the factor 2 that differentiating it gives.
_TERMS = {
    "lor_size": ("size", False),
    "gauss_size": ("size", True),
    "lor_strain": ("strain", False),
    "gauss_strain": ("strain", True),
}


def _reading(kind: str, coefficient: float, variance: bool,
             sigma: float | None, wavelength: float | None,
             k: float, tof: bool = False, *, on_floor: bool = False
             ) -> tuple[float | None, float | None, str | None]:
    """(value, esd, unavailable) for one coefficient.

    ``on_floor`` is the bound test's verdict that this coefficient's floor of
    zero carried load (``FLOOR_HIT``), and it reads as ``at_zero`` whatever
    the stored number is.  The default LM driver lands such a row exactly on
    0.0, so the two tests agree there.  ``solver="trf"`` keeps its iterates
    strictly inside the box and stops a hair above it: 3.4e-24 deg² on
    notebook 04's ``gauss_size``, which Scherrer turns into 4.3e13 Å with an
    esd twenty orders larger (WP-1914).  The floor is that test's, read off
    :func:`~rietx.strategy.staged.bound_findings`, never a proximity of this
    module's own.

    ``coefficient`` is the stored number — a FWHM coefficient, or its square
    for the Gaussian pair.  The relative esd is where the two shapes differ and
    it is one line: for a FWHM coefficient ``σ_value/value = σ_c/c``, and for a
    variance ``σ_value/value = σ_v/(2v)``, because the FWHM behind it is √v.
    Both readings are inversely proportional (size) or proportional (strain) to
    that FWHM, so the *relative* esd is the same either way and the sign never
    matters — an esd is a magnitude.

    ``tof`` says the stored size pair is in the **d-space** units a bank holds
    them in (K/L in Å⁻¹, and its square), where the size reads with no
    wavelength at all — the relative esd, and therefore this function's whole
    second half, is unchanged, because L = K/c is inversely proportional to c
    exactly as L = (180/π)·K·λ/c is.
    """
    if on_floor or not coefficient > 0.0:
        return None, None, "at_zero"
    if kind == "size":
        fwhm_coefficient = math.sqrt(coefficient) if variance else coefficient
        if tof:
            value = apparent_size_from_d_size_coefficient(fwhm_coefficient, k)
        elif wavelength is None or not wavelength > 0.0:
            return None, None, "no_wavelength"
        else:
            value = apparent_size_from_size_coefficient(fwhm_coefficient,
                                                        wavelength, k)
    else:
        fwhm_coefficient = math.sqrt(coefficient) if variance else coefficient
        value = microstrain_from_strain_coefficient(fwhm_coefficient)
    if sigma is None or not sigma >= 0.0:
        return value, None, "not_measured"
    relative = sigma / (2.0 * coefficient) if variance else sigma / coefficient
    return value, value * relative, None


def floored_paths(table, named: Iterable[str]) -> set[str]:
    """The paths ``FLOOR_HIT`` named, and every entry that follows them to zero.

    A free column carries a bound finding, and so does a tied width the LM
    step held on its own floor (WP-1325, ``staged.tied_bound_findings``).  A
    width tied to a floored source, or driven by a floored ``vars.X``, is
    never named itself.  It sits at zero exactly when its tie has no constant
    and every source is floored: ``value = Σ c·source + 0``.  Transitive, as a tie chain is, and the
    closure :func:`~rietx.refine._cell_runaway_withheld` builds for an esd
    one rank over.  ``table`` is any object with
    :class:`~rietx.params.vector.ParameterTable`'s ``entries``.
    """
    floored = set(named)
    grew = bool(floored)
    while grew:
        grew = False
        for e in table.entries:
            if (e.tie is not None and e.path not in floored
                    and e.tie.const == 0.0 and e.tie.terms
                    and all(src in floored for src, _ in e.tie.terms)):
                floored.add(e.path)
                grew = True
    return floored


def microstructure_table(structure: Structure, values: dict[str, float], *,
                         wavelength: float | None,
                         esds: dict[str, float] | None = None,
                         floors: Collection[str] = (),
                         k: float = SCHERRER_K,
                         tof: bool = False) -> list[PhaseMicrostructure]:
    """One :class:`PhaseMicrostructure` per phase, in phase order.

    ``values`` is a decoded parameter dict (the forward model's own), ``esds``
    the *physical* esds ``ParameterTable.stderr_physical`` returns — which
    already omits every row that measured nothing, so a missing key here is
    the WP-1110 answer "this column has no esd" and arrives as
    ``unavailable="not_measured"`` rather than as a zero.

    ``wavelength`` is the caller's, because "which emission line" is decided
    once for the whole package in
    :func:`~rietx.optimize.least_squares._longest_line_wavelength` and this
    module must not have a second opinion.  ``None`` is a source that declares
    none: the strains still read, the sizes do not.

    ``floors`` holds the paths whose ``FLOOR_HIT`` finding fired in the
    answer-producing stage, closed over ties by :func:`floored_paths` and
    spelled as ``values`` spells them.  Each reads as ``at_zero``.  It is the
    third projection of that one bound test, beside the diagnostic and
    ``RefinedParameter.at_bound`` (WP-1076's rule).  ``FLOOR_HIT`` is a lower
    limit of zero, or one under the 1e-8 Γ_G² clamp
    (``staged._at_zero_floor``), so a caller's floor that small reads as no
    broadening too.  Empty is "no test was recorded", and a coefficient then
    reads at zero only where it is stored as zero.

    ``tof`` says the values came off a **time-of-flight bank**, where the size
    pair is stored as K/L in Å⁻¹ rather than as a width in deg 2θ
    (:func:`~rietx.model.forward_tof.sample_broadening_terms`).  It changes
    only which inverse is taken: the block's ``wavelength`` is then ``None``
    and stays ``None`` — a bank has no primary wavelength and this module must
    not report one — while all four rows read, because L in Å and Δd/d are
    axis-free.  Until T-3c a bank abstained on both size rows with
    ``no_wavelength``, which was true of the *coefficient* it was handed and is
    not true of the specimen.

    Never raises on a phase whose coefficients are all at zero — the common
    case, since none of them is freed by default — it returns four terms each
    saying ``at_zero``, which is the honest empty state and is not the same
    statement as "no microstructure block".

    A phase carrying a Stephens block has no ``lor_strain`` term (WP-1467):
    the block replaces it and the width law reads zero for it
    (``CompiledModel.lor_strain_term``), so its stored value is no reading,
    and ``strain_agreement`` is ``None`` there.
    """
    esds = esds or {}
    out: list[PhaseMicrostructure] = []
    for ip, phase in enumerate(structure.phases):
        terms: list[MicrostructureTerm] = []
        for name, (kind, variance) in _TERMS.items():
            path = f"phases.{ip}.{name}"
            if name == "lor_strain" and phase.microstrain is not None:
                continue
            coefficient = values.get(path)
            if coefficient is None:
                continue
            value, esd, why = _reading(kind, float(coefficient), variance,
                                       esds.get(path), wavelength, k, tof,
                                       on_floor=path in floors)
            terms.append(MicrostructureTerm(
                path=path, kind=kind, coefficient=float(coefficient),
                value=value, esd=esd, unavailable=why))
        block = PhaseMicrostructure(
            phase_index=ip, phase_name=phase.name,
            wavelength=wavelength, scherrer_k=k, terms=terms)
        block.size_agreement = _agreement(block, "gauss_size", "lor_size")
        block.strain_agreement = _agreement(block, "gauss_strain", "lor_strain")
        out.append(block)
    return out


def _agreement(block: PhaseMicrostructure, numerator: str,
               denominator: str) -> float | None:
    """Gaussian reading ÷ Lorentzian reading, or ``None`` if either is absent.

    WP-1131 Finding 5: rietx registers the Gaussian and Lorentzian halves of
    each mechanism as **independent** columns, where GSAS-II refines one
    magnitude and a mixing coefficient that splits it.  The independent model
    is the more general one and this module does not argue against it — it
    measures the consistency the constrained model would have imposed, which
    was previously unmeasured.  Far from 1 means the two describe different
    specimens and neither is quotable alone.
    """
    top, bottom = block.term(numerator), block.term(denominator)
    if top is None or bottom is None:
        return None
    if top.value is None or bottom.value is None or not bottom.value > 0.0:
        return None
    return top.value / bottom.value
