"""The time-of-flight forward model: a pattern in microseconds from a structure.

The sibling of :mod:`rietx.model.forward`, and a **separate compiled object**
rather than a branch inside :class:`~rietx.model.forward.CompiledModel`.  That
class is an angle from end to end — its grid is ``tt``, it carries a
``wavelength`` and a ``line_wavelengths`` tuple, its positions come from
Bragg's law, its widths are Caglioti polynomials in tan θ, and its intensities
carry a polarisation factor and a Finger-Cox-Jephcoat axial quadrature.  A
time-of-flight bank shares **none** of those five and shares the rest exactly:
the reflection list, the d-spacings, |F|², the multiplicities, the background
and the parameter table are all radiation-blind, and this module reuses them
without a second copy.

What is different, and where each piece comes from
--------------------------------------------------

*Positions.*  ``T_hkl = DIFC·d + DIFA·d² + TZERO + DIFB/d``
(:func:`rietx.model.profiles.tof.tof_from_d`; Larson & Von Dreele, 2004,
LAUR 86-748, GSAS Technical Manual p. 141, whose relation is the first three
terms, plus GSAS-II's ``difB``).  The four constants are
:class:`~rietx.schemas.instrument.TOFSource` parameters, so they are read from
the decoded θ on every call and can be refined.

*Shape.*  Two back-to-back exponentials convoluted with a Gaussian (GSAS TOF
profile type 1, :func:`~rietx.model.profiles.tof.back_to_back_gaussian`) or
with a pseudo-Voigt (type 3,
:func:`~rietx.model.profiles.tof.back_to_back_pseudovoigt`) — Von Dreele,
Jorgensen & Windsor, 1982, *J. Appl. Cryst.* **15**, 581.  Which one is a
**compile-time structural** choice, taken from whether any γ coefficient is
non-zero or can move this stage, never from a θ-decoded value mid-solve.  The
four shape parameters follow the reflection's d-spacing through
:func:`~rietx.model.profiles.tof.tof_alpha`, ``tof_beta``, ``tof_sigma_sq`` and
``tof_gamma``.

*Intensity.*  ``I_hkl = S · m_hkl · |F_hkl|² · d⁴·sin θ_bank`` — the
time-of-flight Lorentz factor (GSAS Technical Manual p. 140; Larson & Von
Dreele, 2004).  ``θ_bank`` is **half the bank's fixed scattering angle**, not a
per-reflection quantity: on a TOF bank every reflection is collected at the
same angle and separated by arrival time, which is the whole structural
difference from the constant-wavelength Lorentz factor.  Getting that wrong —
using a per-reflection θ — is the single most plausible mistake here, so the
sine is computed once at compile and stored as a scalar.

*What varies with wavelength inside the histogram.*  Three corrections that a
constant-wavelength model evaluates once per emission line have to be evaluated
along the bank here, because λ is a property of the channel:

* the **incident spectrum** the moderator delivers, which the file declares in
  its ``ITYP`` record and which is a function of the **flight time** (ISIS GEM
  writes ``ITYP 0``, i.e. none — already divided out by its reduction; a
  LANSCE-style file writes ``ITYP 1`` with a full ``ICOFF`` block, i.e. its histograms still
  carry it, fifth pair P₁₀·exp(−P₁₁·T⁵) included — its exponent measured by
  conformance, :mod:`rietx.model.tof_spectrum`).  Applied **per channel**, to the calculated Bragg sum and not to
  the background — :meth:`CompiledTOFModel.incident_spectrum` and
  :mod:`rietx.model.tof_spectrum`;
* the **channel width** W(T), the other half of the same one-line relation
  (manual PAGE 127, verbatim: *"The general expressions for the intensity of
  TOF data are I_o = I'_o / W I_i … where I'_o is the number of counts
  observed in a channel of width W"*).  A calculated Bragg sum is a density,
  so a histogram holding *counts* owes it a factor of W and one already
  divided by W does not — which is a fact about the file, declared on the
  pattern (:attr:`~rietx.schemas.pattern.PatternData.intensity_basis`) and
  never inferred.  W is measured from the pattern's **own abscissa**, because
  a ``TIME_MAP`` bank's widths are tabulated in the data and are in no
  instrument file: :meth:`CompiledTOFModel.channel_width_factor`;
* **specimen absorption**, whose µ follows the 1/v law, so µR runs linearly
  with λ across the bank.  Applied **per reflection** at λ_hkl, which is where
  GSAS applies it (manual PAGE 134);
* **secondary extinction**, whose Sabine variable carries λ² and so runs as
  λ⁴-ish across the bank.  Also per reflection, through exactly the
  constant-wavelength :func:`~rietx.model.extinction.sabine_extinction` with an
  array of wavelengths where a scalar used to go.

Absorption is **computed, never refined**: the manual's own warning (PAGE 134,
verbatim) is that *"the correction is indistinguishable from thermal motion
effects and should not be refined"*, and a scalar ``Geometry.mu_r`` is refused
on this arm because it is a claim at one wavelength.  Preferred orientation,
Stephens strain and soft restraints stay refused, each naming its rung.

Units, once
-----------
Flight time and every ΔT in **microseconds**; d in Å; DIFC µs/Å, DIFA µs/Å²,
TZERO µs, DIFB µs·Å; α and β in µs⁻¹; the ``sig`` coefficients are
**variances** in µs², µs²/Å², µs²/Å⁴ (not FWHMs, and not squared again — see
:func:`~rietx.model.profiles.tof.tof_sigma_sq`); the ``gam`` coefficients are a
Lorentzian **FWHM** in µs.  ΔT = channel − peak, so β < α puts the tail at long
flight time.  A ``.iparm``'s ``ITYP`` window and its spectrum functions are in
*milli*seconds and are the one place in this track where the unit changes; the
conversion happens once, at :mod:`rietx.model.tof_spectrum`'s door, so nothing
in this module carries a millisecond.  µ is in cm⁻¹ and µR is dimensionless.

References
----------
Von Dreele, Jorgensen & Windsor (1982), *J. Appl. Cryst.* **15**, 581-589 —
the back-to-back-exponential profile.  Larson & Von Dreele (2004), *GSAS
General Structure Analysis System*, LAUR 86-748 — the four-term TOF ↔ d
relation, the coefficient conventions and the d⁴·sin θ Lorentz factor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from ..backend import get_backend
from ..crystallography.lattice import cell_volume, d_spacings
from ..crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from ..crystallography.symmetry import generate_reflections
from ..schemas.instrument import HUMP_FIELDS, Instrument
from ..schemas.pattern import IntensityBasis, PatternData
from ..schemas.structure import Structure
from .absorption import cylinder_absorption
from .extinction import sabine_extinction
from .forward import (
    CompiledPhase,
    Mode,
    background_curve,
    background_penalty_rows,
    compile_background,
    magnetic_wanted,
    window_fwhm_mult,
)
from .origin import CompiledOrigin, origin_residual
from .profiles.caglioti import microstrain_width
from .profiles.tof import (
    back_to_back_gaussian,
    back_to_back_pseudovoigt,
    tof_alpha,
    tof_beta,
    tof_from_d,
    tof_gamma,
    tof_pseudovoigt_widths,
    tof_sample_gamma,
    tof_sample_sigma_sq,
    tof_sigma_sq,
)
from .tof_spectrum import incident_spectrum, neutron_attenuation_terms

#: Where the incident spectrum is evaluated.  T-1b declared this name for a
#: seam that returned 1.0; the method now evaluates the function the file
#: declared, and the constant is kept because it is what a caller overriding
#: the spectrum — a reduction that measured its own, an ``ITYP 10``
#: point-by-point file — is pointed at.
INCIDENT_SPECTRUM_HOOK = "rietx.model.forward_tof.CompiledTOFModel.incident_spectrum"

#: The fraction of a peak this arm's frozen window may discard **on each side
#: separately**, and per component.  The flight-time arm's own tolerance, two
#: orders under :data:`~rietx.model.forward.WINDOW_AREA_TOL`, and the reason it
#: needs one is a measurement rather than a preference.
#:
#: A constant-wavelength peak is symmetric, so a 2 %-of-area window truncates
#: both sides alike and the truncation is very nearly a *scale* on the
#: reflection — which the phase scale absorbs, and which was measured as no
#: material bias.  The
#: back-to-back-exponential peak is not symmetric, and its asymmetry is a
#: function of α and β, i.e. of the very parameters a stage refines.  So the
#: truncated fraction moves *between candidate solutions*, and a window frozen
#: for the stage turns that into a term in χ² that depends on where the model
#: was compiled rather than on where it is.  Measured on a real standard's
#: bank at 2 %: the penalty at one state was some thirty times its value at a
#: neighbouring state a few mÅ away, enough to move the χ² minimum by many of
#: its own σ and to make an uphill step score as downhill.
#:
#: 1e-4 was **chosen by measurement**, on that same bank and those same two
#: states, sweeping the whole window rule (2 %, 1e-3 … 1e-6) and nothing else.
#: "Penalty" is χ²(this rule) − χ²(this rule + 500 µs of extra slack), i.e.
#: what the frozen window costs at that state.  The criterion is not the
#: penalty alone but the *difference between the two states*, which is what a
#: solver actually walks on: it falls by more than two orders of magnitude from
#: the 2 % rule to 1e-4 and is converged there (1e-6 changes it by under a
#: tenth), for about 40 % more window points and 20 % more time per
#: evaluation.  1e-3 would meet a 2-unit bar with no margin at all.
#:
#: **What it costs on the pseudo-Voigt branch, and it is not small.**  The
#: exponential wings grow like log(1/tol), which is cheap; the Lorentzian half
#: of a resolution function does not, since k ≈ η/(π·tol) — 1e-4 is ~160 FWHM
#: per unit η against the constant-wavelength rule's 1.6.  Measured on a
#: synthetic Si bank at three γ₁, shipped rule against this one:
#:
#: ======== ============= ================= ==================
#: γ₁       η(max)        ms/eval, shipped  ms/eval, this rule
#: ======== ============= ================= ==================
#: 0        0 (Gaussian)  0.15              0.14
#: 2        0.064         1.26              15.4
#: 10       0.274         1.77              43.3
#: ======== ============= ================= ==================
#:
#: So the Gaussian branch is free — the shorter exponential wings pay for the
#: wider Gaussian extent, k(0) being 1.58 here against the CW rule's 0.99 —
#: and the type-3 branch is 12-24× slower.  It is shipped that way because the
#: tolerance is the *statement*, and every real bank measured for this track
#: (the SNS NOMAD and ISIS GEM standards among them) declares γ = 0 and
#: compiles the Gaussian branch.  The remedy is a **separate, stated**
#: tolerance for the Lorentzian component — not a quiet cap on this one, which
#: is the unstated bias WP-1112 removed — and it exists as a *schedule*:
#: ``compile_tof_model``'s ``lorentz_window_tol``, set per stage by
#: ``RefinementPlan.stage_lorentz_window_tols`` (coarse in every declared
#: stage but the last, this constant in the last and in the closing stage,
#: recorded on ``StageResult``).  The number and its measurement are
#: :data:`rietx.schemas.plan.INTERMEDIATE_LORENTZ_WINDOW_TOL`'s.
TOF_WINDOW_AREA_TOL = 1e-4

#: How many e-foldings of each exponential wing a frozen window must hold —
#: **derived** from the tolerance above rather than chosen beside it, so the
#: two halves of one window cannot state two different bars.  The back-to-back
#: pulse decays as e^{−α|ΔT|} on the short-flight-time side and e^{−βΔT} on the
#: long one, and the mass beyond ``k`` e-foldings of either is at most e^{−k},
#: so ``−ln(tol)`` is exactly the sizing that leaves ``tol`` of it outside.
#:
#: The two wings are sized **separately**, which is the whole point: β < α is
#: the normal case and makes the long-flight-time tail several times the short
#: one, so a symmetric window either truncates the tail or pays for it twice.
#: And the exponential and resolution extents are **added**, which is a bound
#: and not an approximation: the profile is a convolution, so the displacement
#: is a sum of two independent ones and P(E + R > h_E + h_R) ≤ P(E > h_E) +
#: P(R > h_R).  The window therefore discards at most ``2·TOF_WINDOW_AREA_TOL``
#: per side, and that is a *stated* bound rather than an accident of the
#: margin — which is what the 2 %-of-area rule was here.
TAIL_EFOLDS = -math.log(TOF_WINDOW_AREA_TOL)

#: Absolute slack in µs added to every window half-width, and the fraction of
#: the peak's own flight time added beside it.  Movement headroom, not tail
#: coverage: windows are frozen per stage while the cell, DIFC and TZERO move
#: inside it, and a cell error is *relative* (0.5 % of d is 0.5 % of T, i.e.
#: 200 µs at T = 40 000 µs) while a TZERO error is *absolute*.  So the slack
#: has to be both.  A stage that starts further out than this recompiles and
#: converges on the second pass, which is what ``Refinement`` does anyway.
WINDOW_MIN_US = 3.0
WINDOW_SLACK_FRAC = 2.0e-3

#: A bank whose α or β is not positive cannot make a peak: the back-to-back
#: pulse has amplitude αβ/(α+β) and infinite width at either limit.  An
#: all-zero :class:`~rietx.schemas.instrument.ProfileTOF` is a real state — it
#: is what a ``.iparm`` whose ``PRCF`` block was declined leaves behind (T-1's
#: D2) — so this is refused by name at compile rather than producing a pattern
#: of zeros nobody can explain.
_MIN_RATE = 1e-12


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def sample_broadening_terms(ip: int, values: dict[str, float]) -> tuple:
    """``(size_L, strain_L, size_var, strain_var)`` for one phase, on a bank.

    The four :class:`~rietx.schemas.structure.Phase` sample-width parameters
    read as the **specimen quantities** a time-of-flight bank can use:
    ``size_*`` is K/L in Å⁻¹ and ``strain_*`` is Δd/d, both FWHMs, both free
    of any wavelength and any angle
    (:func:`~rietx.model.profiles.tof.tof_sample_gamma`,
    :func:`~rietx.model.profiles.tof.tof_sample_sigma_sq`).

    **The two pairs are stored differently, and the asymmetry is WP-1131's.**
    A microstrain coefficient is λ-free: ``lor_strain`` is the same number of
    degrees on every instrument, so a bank reads the stored coefficient
    through the constant-wavelength arm's own conversion and the two arms
    share one column with one meaning.  A *size* coefficient is not: it is
    (180/π)·K·λ/L, so a number of degrees is a length only through a
    wavelength, and a bank has none —
    :attr:`CompiledTOFModel.wavelength` refuses to invent one.  So on a
    ``neutron_tof`` table ``lor_size`` holds K/L in Å⁻¹ and ``gauss_size``
    its square in Å⁻², the d-space form
    (:func:`~rietx.model.profiles.caglioti.apparent_size_from_d_size_coefficient`).
    A joint fit sharing one size column between a bank and a scan has to
    convert between the two units; that fit is not written yet, and
    ``MultiHistogramRefinement`` refuses a bank by name.

    The Gaussian pair are **variances** in both arms' units and are handed on
    as variances: (K/L)² in Å⁻² and (Δd/d)², which is what
    :func:`~rietx.model.profiles.tof.tof_sample_sigma_sq` takes.  Squaring the
    *coefficient* rather than the width is what keeps a square root out of the
    residual, and (5) being linear is what makes the strain variance a plain
    multiple of ``gauss_strain``.

    ``.get`` rather than ``[]`` for :meth:`CompiledTOFModel.phase_peaks`'s
    reason: it is public and is called with hand-built value dicts by plots,
    exporters and replay, and a dict that does not mention a sample width
    means a phase that declares none — which is rietx's default and is an
    exact zero, not a missing number.

    **Unconditional arithmetic, through the backend.**  No branch on a value:
    this runs inside the residual on every traced backend, where a value is a
    tracer and a python ``float()`` or a ``> 0.0`` is not available, and where
    a branch on a parameter would bake one side of it into the trace.  Every
    term is exactly zero at rietx's zero defaults, so the branch would buy
    nothing anyway — which is the purity rule
    :func:`~rietx.model.profiles.caglioti.gaussian_fwhm` states one module
    over.  ``maximum(·, 0.0)`` guards only the square roots, and only against a
    value the softplus transform's floor already excludes.
    """
    base = f"phases.{ip}."
    size_l = values.get(base + "lor_size", 0.0)
    size_var = values.get(base + "gauss_size", 0.0)
    strain_l = microstrain_width(values.get(base + "lor_strain", 0.0))
    # Δd/d is (π/360)·c, linear in the coefficient, so the variance of the one
    # is (π/360)² times the variance of the other — ``microstrain_width(1.0)``
    # is that factor, read from the function that owns the relation rather
    # than re-typed as a number.
    strain_var = microstrain_width(1.0) ** 2 * values.get(
        base + "gauss_strain", 0.0)
    return size_l, strain_l, size_var, strain_var


@dataclass
class CompiledTOFModel:
    """One time-of-flight bank frozen for one refinement stage.

    The field names say which quantity they hold.  ``tt``, ``tt_min`` and
    ``tt_max`` are **properties that raise** — the mirror of
    :meth:`rietx.schemas.pattern.PatternData.tt`, and for the same reason: a
    consumer that wants an angle must fail here rather than read microseconds
    and return a confident wrong answer.  Axis-blind consumers read
    :attr:`grid`, :attr:`x_min`, :attr:`x_max` and :attr:`n_points`.
    """

    #: The fit grid: flight time in µs, in-range points only.
    tof: np.ndarray
    y_obs: np.ndarray
    sigma: np.ndarray
    tof_min: float
    tof_max: float

    #: The bank's fixed scattering angle in degrees, and ``sin(θ_bank)``
    #: computed from it once — the Lorentz factor's angular half.  A scalar,
    #: never a per-reflection array: see the module docstring.
    two_theta_bank_deg: float
    sin_theta_bank: float

    mode: Mode
    phases: list[CompiledPhase]

    #: The background, compiled by the shared
    #: :func:`~rietx.model.forward.compile_background` on this grid — a
    #: Chebyshev polynomial in **microseconds** over the fit window.
    fixed_background: np.ndarray | None
    bkg_paths: tuple[str, ...]
    bkg_design: np.ndarray
    bkg_penalty: np.ndarray | None
    component_paths: tuple[tuple[str, str, str], ...] = ()

    #: Which GSAS ``ITYP`` incident-spectrum function this bank declared, and
    #: the parameter paths of its coefficients in the order the manual numbers
    #: them.  ``0`` and ``()`` mean **no spectrum** — the state every already
    #: normalised reduction (ISIS GEM, SNS NOMAD, POWGEN) leaves behind — and
    #: :meth:`incident_spectrum` then returns ``None`` rather than an array of
    #: ones, so such a bank is bit-identical to the build before T-3.
    spectrum_itype: int = 0
    spectrum_paths: tuple[str, ...] = ()

    #: What one channel of ``y_obs`` **holds** — the pattern's own declaration,
    #: carried onto the compiled model so a consumer reading the model alone
    #: can say what was applied.  ``None`` is "the file did not say", and it is
    #: the state every fit before this field ran in.
    intensity_basis: IntensityBasis | None = None

    #: W(T) on this model's grid in µs, or ``None`` when the calculated Bragg
    #: sum is **not** multiplied by it (a declared ``"density"``, an
    #: undeclared basis, and the whole constant-wavelength arm).  ``None``
    #: rather than an array of ones for :meth:`incident_spectrum`'s reason: a
    #: bank that owes no width factor multiplies by nothing at all, which is
    #: bit-identical to the build before this field rather than merely equal.
    channel_width: np.ndarray | None = None

    #: ``(a, b)`` with **µR(λ) = a·λ + b**, the packed specimen's absorption
    #: parameter as a function of the wavelength a reflection arrived on, or
    #: ``None`` when no specimen dimension was declared and the correction is
    #: off.  Affine because absorption follows the 1/v law and scattering does
    #: not (:func:`~rietx.model.tof_spectrum.neutron_attenuation_terms`), so
    #: the two constants freeze at compile exactly as the constant-wavelength
    #: model's single ``mu_r`` does while λ stays per reflection.
    absorption_terms: tuple[float, float] | None = None

    #: ``(d_min, d_max)`` in Å: the fitted flight-time window read through the
    #: calibration this stage froze, window slack included — the same pair
    #: every refusal in :func:`compile_tof_model` quotes.  Carried because the
    #: tier-1 width caps are stated *from* it (T-1d): a strain cannot exceed
    #: the fitted d range's own fractional width, and that range is a frozen
    #: per-stage fact exactly as the windows are.  ``None`` is **no claim
    #: made** — the state a table starts in, and what a model built without a
    #: calibration would honestly say — and the caps then declare nothing.
    d_range: tuple[float, float] | None = None
    #: DIFC in µs/Å at stage compile.  The one calibration constant the width
    #: laws use (ΔT = DIFC·ε·d and DIFC·(K/L)·d²,
    #: :func:`~rietx.model.profiles.tof.tof_sample_gamma`), so a cap derived
    #: from a flight-time extent needs it to reach a d.  Frozen here rather
    #: than read from a value dict for the reason :attr:`d_range` is.
    difc_stage: float | None = None

    #: ``(µR at the shortest λ, µR at the longest λ)`` the fitted window
    #: reaches, or ``None`` with the correction off.  Reported rather than
    #: enforced (see :func:`_absorption_terms`), and reported as a **pair**
    #: because that is the statement a constant-wavelength µR cannot make: the
    #: same specimen can be inside the Rouse domain at one end of a bank and
    #: outside it at the other.
    mu_r_range: tuple[float, float] | None = None

    #: ``"gaussian"`` (GSAS TOF profile type 1) or ``"pseudovoigt"`` (type 3).
    #: Compile-time structural, like ``CompiledModel.shape``: taken from
    #: whether any γ coefficient is non-zero or can move this stage, so the
    #: branch never sees a decoded value and the residual stays smooth.
    profile_kind: str = "gaussian"

    #: One ``(point_index, reflection_index)`` pair of flat int arrays per
    #: phase: every frozen window concatenated, so the whole phase is one Ω
    #: evaluation and one ``bincount``.  Built at compile from ``win`` and
    #: nothing else — a frozen index layout, exactly like
    #: :class:`~rietx.model.forward.BatchLayout`, and it holds no value that
    #: can move.
    flat_windows: list[tuple[np.ndarray, np.ndarray]] = field(default_factory=list)

    #: The per-side area fraction the **Lorentzian component** of every window
    #: was sized to leave outside, as compiled: :data:`TOF_WINDOW_AREA_TOL` under
    #: the one-rule default, the stage's ``lorentz_window_tol`` when one was
    #: passed, and ``None`` on the Gaussian branch, which has no Lorentzian
    #: component to size.  What ``StageResult.lorentz_window_tol`` reports: the
    #: tolerance a stage **ran** at, read off the model it ran on.
    lorentz_window_tol: float | None = None

    restraints: object | None = None
    restraint_weight_scale: float = 1.0
    #: Pawley is not wired on this arm (see :func:`compile_tof_model`); the
    #: field exists because every consumer tests it for ``None``.
    pawley: None = None
    #: The ``"centroid"`` floating-origin rows (WP-1912), as on the
    #: constant-wavelength model and written by the same stage runner
    #: (``refine._attach_origin``).  They are a statement about site positions
    #: alone, and their weights are read off :meth:`evaluate` and ``sigma``,
    #: so nothing in them knows which axis the grid is.
    origin: "CompiledOrigin | None" = None
    meta: dict = field(default_factory=dict)

    # -- the protocol the shared machinery reads -------------------------
    #: Which abscissa this model's grid carries — the discriminator a shared
    #: consumer branches on, spelled exactly as ``PatternData.axis`` spells it.
    axis: ClassVar[str] = "tof"
    #: **No analytic Jacobian columns on this arm.**  Every analytic branch in
    #: ``optimize.least_squares`` chains through per-emission-line planes, a
    #: pseudo-Voigt ``_profile_basis`` and an FCJ node set, none of which this
    #: model has; the finite-difference fallback that module already carries is
    #: exact for what it computes and is what this rung uses.  Read through
    #: ``getattr(model, "analytic_jacobian", True)``, so the
    #: constant-wavelength model is untouched and its columns are unchanged.
    analytic_jacobian: ClassVar[bool] = False
    #: A white beam is a continuum: there is no line list and no primary λ.
    #: Empty rather than absent, because ``_longest_line_wavelength`` reads it
    #: with ``getattr(..., ()) or ()`` and answers "this source states no
    #: wavelength", which is the true answer.
    line_wavelengths: ClassVar[tuple[float, ...]] = ()
    #: The source's kind, as :class:`~rietx.model.forward.CompiledModel`
    #: carries it: what a result's ``radiation`` records, and the table
    #: ``optimize.qpa`` would read µ from (it has none for a bank, and says so).
    source_kind: ClassVar[str] = "neutron_tof"
    #: No constant-wavelength window fraction: a bank's windows are sized per
    #: side by :data:`TOF_WINDOW_AREA_TOL` at compile, in every stage.  ``None``
    #: is the "records no window fraction" state ``report`` reads, so the
    #: report judges this model as compiled rather than building a 2θ twin.
    window_area_tol: ClassVar[None] = None
    harmonic_orders: ClassVar[dict[int, int]] = {}
    #: Declared sharp peaks (``PeakComponent``), CW-only so far —
    #: ``compile_tof_model`` never builds a ``CompiledExtraPeak`` for a bank.
    #: Empty rather than absent: shared
    #: callers (``refine._build_result``'s ``EXTRA_PEAK_*`` diagnostics,
    #: ``peak_component_prefixes``) read it with a plain truthiness/iteration
    #: test on every compiled model, CW or TOF.
    peak_components: ClassVar[tuple] = ()
    #: **There is no scalar µR on this arm, and 0.0 is the true answer to
    #: the question this field asks**, not a stand-in for one.  Specimen
    #: absorption *is* applied here when a capillary radius is declared — see
    #: :attr:`absorption_terms` and :meth:`absorption` — but µR is a function
    #: of λ and λ is a property of the channel, so "the µR of this histogram"
    #: has no value.  The shared diagnostics read this field to decide whether
    #: a *frozen scalar* correction ran, and on this arm none did.
    mu_r: ClassVar[float] = 0.0
    mu_t: ClassVar[None] = None
    roughness: ClassVar[None] = None
    radius_mm: ClassVar[None] = None
    #: **Deliberately not one of the constant-wavelength geometry kinds.**  The
    #: obvious value here is ``"debye_scherrer"`` — a can of powder in a beam is
    #: what a TOF diffractometer holds — and it is the wrong one, because
    #: ``geometry_kind`` is not read as a description of the specimen: it is
    #: read as a *key*.  ``report.layer1.POSITION_TEMPLATES`` indexes it to
    #: choose which 2θ regression templates a misfit is attributed against, and
    #: a key that resolves would hand a time-of-flight fit the sample-
    #: displacement and transparency shapes of a Bragg-Brentano goniometer and
    #: report the answer.  A key that does not resolve raises there instead,
    #: which is the same choice :attr:`tt` makes one field up.  Every site in
    #: ``refine.py`` that compares this string is inside the absorption or
    #: capillary path, and both are off on this arm (``mu_r`` 0.0, ``mu_t``
    #: None, ``radius_mm`` None), so nothing in this build reads it at all.
    geometry_kind: ClassVar[str] = "neutron_tof_bank"
    shape: ClassVar[str] = "tof_back_to_back"

    # ------------------------------------------------------------------
    # the axis: honest names, and refusals where an angle was expected
    # ------------------------------------------------------------------
    @property
    def grid(self) -> np.ndarray:
        """The fit abscissa as measured — µs here, degrees on the CW model."""
        return self.tof

    @property
    def x_min(self) -> float:
        return self.tof_min

    @property
    def x_max(self) -> float:
        return self.tof_max

    @property
    def n_points(self) -> int:
        return len(self.tof)

    def _no_angle(self, name: str) -> "ValueError":
        return ValueError(
            f"{name} is a 2θ-only accessor and this compiled model is a "
            f"time-of-flight bank: its grid is a flight time in microseconds, "
            f"not an angle in degrees. Time and angle are related by the "
            f"bank's DIFC/DIFA/TZERO/DIFB, which are parameters of the "
            f"neutron_tof source — use .grid (the axis as measured), "
            f".tof/.tof_min/.tof_max to say so explicitly, or .n_points where "
            f"only the channel count was wanted.")

    @property
    def tt(self) -> np.ndarray:
        raise self._no_angle("CompiledTOFModel.tt")

    @property
    def tt_min(self) -> float:
        raise self._no_angle("CompiledTOFModel.tt_min")

    @property
    def tt_max(self) -> float:
        raise self._no_angle("CompiledTOFModel.tt_max")

    @property
    def wavelength(self) -> float:
        raise ValueError(
            "CompiledTOFModel.wavelength: a time-of-flight bank sees the whole "
            "moderator spectrum, so λ is a property of the channel and not of "
            "the source — there is no primary wavelength to read. A consumer "
            "that needs one (a Scherrer size, a sin²θ/λ² trend template) has "
            "no answer on this arm and must say so rather than pick a number.")

    def line_lambdas(self, values: dict[str, float]) -> list:
        """No emission lines: a white beam has none.  Empty, never ``[0.0]``."""
        return []

    # ------------------------------------------------------------------
    # the shared, axis-blind blocks
    # ------------------------------------------------------------------
    def background(self, values: dict[str, float]) -> np.ndarray:
        """The declared background on the µs grid — the shared implementation."""
        return background_curve(self.tof, self.bkg_paths, self.bkg_design,
                                self.fixed_background, self.component_paths,
                                values)

    def penalty_residual(self, values: dict[str, float]) -> np.ndarray | None:
        return background_penalty_rows(self.bkg_penalty, self.bkg_paths, values)

    def peak_component_prefixes(self) -> frozenset[str]:
        """Dot-path prefixes of the components that are **not** background.

        Always empty here: a bank's ``component_paths`` are hump-kind members
        only (``compile_tof_model`` never builds a ``CompiledExtraPeak`` for a
        TOF instrument — a sharp ticked peak is CW-only so far), so there is
        nothing for ``background_absorption``/``extra_peak_absorption`` to
        exclude or include on this arm.  Present for the same reason
        :meth:`CompiledModel.peak_component_prefixes` is: callers shared
        between both arms (``multi.py``, ``strategy.staged``) call it
        unconditionally.
        """
        return frozenset()

    def extra_peak_tick_positions(self, values: dict[str, float]) -> list[float]:
        """Where every declared sharp peak's images sit. Always empty here —
        see :meth:`peak_component_prefixes`, the same TOF-has-no-``PeakComponent``
        reason. Present because ``refine._tick_rows`` calls it unconditionally
        on every compiled model, CW or TOF."""
        return []

    def reflection_positions(self, ip: int, values: dict[str, float]
                             ) -> tuple[np.ndarray, np.ndarray]:
        """Every reflection of phase ``ip`` where this model draws its peak.

        The flight-time twin of
        :meth:`rietx.model.forward.CompiledModel.reflection_positions`, the one
        walk every tick builder shares (WP-1908), with the same ``(pos, hklm)``
        contract.  A bank has one row, not one per emission line: every
        reflection reaches the bank's one angle and is placed by the four-term
        calibration (:meth:`positions`), which holds TZERO, so there is no zero
        shift to add.  The cell is read off ``values``, so a refined cell moves
        the ticks with the peaks.
        """
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        pos = np.asarray(self.positions(d_spacings(cp.reflections.hkl, *cell),
                                        values), dtype=np.float64)
        return pos, np.asarray(cp.reflections.hklm)

    def restraint_residual(self, values: dict) -> np.ndarray | None:
        """No restraints on this arm (refused at compile); always ``None``."""
        return None

    def mag_split(self, ip: int) -> bool:
        """Always ``False``: no phase draws a magnetic component on a bank
        (``forward.magnetic_wanted`` refuses a moment there), so there is no
        second frozen family (WP-1343)."""
        return False

    def texture_summary(self, ip: int, values: dict[str, float]) -> None:
        """Always ``None``: no phase carries a compiled texture on this arm,
        which :func:`compile_tof_model` refuses by name."""
        return None

    def origin_residual(self, values: dict) -> np.ndarray | None:
        """The origin rows, as :meth:`rietx.model.forward.CompiledModel.
        origin_residual` evaluates them, or ``None`` when there are none."""
        if self.origin is None:
            return None
        return origin_residual(self.origin, values)

    def evaluate(self, values: dict[str, float],
                 intensities: list[np.ndarray] | None = None) -> np.ndarray:
        """y_calc on the fit grid: background + every phase's Bragg sum."""
        return self.background(values) + self.bragg_component(values, intensities)

    def evaluate_with_background(self, values: dict[str, float]
                                 ) -> tuple[np.ndarray, np.ndarray]:
        """``(evaluate(values), background(values))`` for one background pass,
        as :meth:`rietx.model.forward.CompiledModel.evaluate_with_background`.
        The sum is :meth:`evaluate`'s in its own association order, so the
        curve is bit-identical to it."""
        y_bkg = self.background(values)
        return y_bkg + self.bragg_component(values), y_bkg

    def bragg_component(self, values: dict[str, float],
                        intensities: list[np.ndarray] | None = None) -> np.ndarray:
        y = get_backend().zeros_like(self.tof)
        for ip in range(len(self.phases)):
            y = y + self.phase_component(
                ip, values, None if intensities is None else intensities[ip])
        return y

    # ------------------------------------------------------------------
    # the time-of-flight physics
    # ------------------------------------------------------------------
    def calibration(self, values: dict[str, float]) -> tuple:
        """``(DIFC, DIFA, TZERO, DIFB)`` as decoded values, in file order."""
        return (values["instrument.source.difc"],
                values["instrument.source.difa"],
                values["instrument.source.tzero"],
                values["instrument.source.difb"])

    def positions(self, d, values: dict[str, float]):
        """Flight times in µs for d-spacings in Å, through the four-term map."""
        difc, difa, tzero, difb = self.calibration(values)
        return tof_from_d(d, difc, difa, tzero, difb)

    def shape_parameters(self, d, values: dict[str, float],
                         ip: int | None = None) -> tuple:
        """``(α, β, σ, γ)`` at each d — the GSAS d-dependence laws.

        σ is the Gaussian **standard deviation** in µs, i.e. the square root of
        :func:`~rietx.model.profiles.tof.tof_sigma_sq`'s variance; γ is the
        Lorentzian **FWHM** in µs.  Both are what
        :func:`~rietx.model.profiles.tof.back_to_back_gaussian` and its
        pseudo-Voigt sibling take, so no caller converts.

        ``ip`` names the phase whose **sample** broadening is folded in, or
        ``None`` for the instrument alone.  The specimen's crystallite size
        and microstrain enter here, into γ and into σ², **before** the
        Thompson-Cox-Hastings mixing that
        :func:`~rietx.model.profiles.tof.back_to_back_pseudovoigt` does — which
        is the only place they can enter and still be a convolution: a
        Lorentzian FWHM adds to a Lorentzian FWHM and a Gaussian variance to a
        Gaussian variance, and a width added to the *mixed* Γ would be a width
        of neither shape.  ``None`` and a phase with no sample broadening reach
        identical arithmetic: the sample terms are an exact ``+0.0``.
        """
        xp = get_backend()
        p = "instrument.source.profile_tof."
        alpha = tof_alpha(d, values[p + "alpha0"], values[p + "alpha1"])
        beta = tof_beta(d, values[p + "beta0"], values[p + "beta1"])
        var = tof_sigma_sq(d, values[p + "sig0"], values[p + "sig1"],
                           values[p + "sig2"])
        gamma = tof_gamma(d, values[p + "gam0"], values[p + "gam1"],
                          values[p + "gam2"])
        if ip is not None:
            difc = values["instrument.source.difc"]
            size_l, strain_l, size_var, strain_var = sample_broadening_terms(
                ip, values)
            gamma = gamma + tof_sample_gamma(d, difc, size_l, strain_l)
            var = var + tof_sample_sigma_sq(d, difc, size_var, strain_var)
        sigma = xp.sqrt(xp.maximum(var, 0.0))
        return alpha, beta, sigma, gamma

    def lorentz(self, d):
        """L_TOF = d⁴·sin θ_bank (GSAS manual p. 140).

        ``sin θ_bank`` is a frozen scalar, and it is the *bank's* half-angle:
        every reflection in a time-of-flight histogram is collected at the same
        scattering angle.  It is exactly degenerate with the phase scale on a
        single bank, and it is kept anyway, because across banks of one
        instrument the ratio is what makes one structure fit all of them with
        one set of scales.
        """
        xp = get_backend()
        dd = xp.asarray(d, dtype=np.float64)
        return dd ** 4 * self.sin_theta_bank

    def wavelength_of(self, d):
        """λ = 2·d·sin θ_bank — the wavelength that reflection arrived on.

        A time-of-flight bank sorts a white beam by arrival time, so λ is a
        property of the *channel*: every reflection in the histogram has its
        own, fixed by Bragg's law at the bank's one angle.  This is the
        quantity every λ-dependent correction (the incident spectrum, specimen
        absorption, detector efficiency) is a function of, and it is why none
        of them can be frozen to a scalar per stage the way the
        constant-wavelength model freezes µR.
        """
        xp = get_backend()
        return 2.0 * xp.asarray(d, dtype=np.float64) * self.sin_theta_bank

    def absorption(self, d):
        """A(λ_hkl) per reflection, or ``None`` when the correction is off.

        **Per reflection at the reflection's own wavelength**, which is where
        GSAS applies it too — the manual's PAGE 134 absorption parameter is
        written ``A_B = µR/λ`` precisely because the quantity that is constant
        across a time-of-flight bank is µR *per ångström*, not µR.

        The angle is the bank's, fixed, so the whole λ dependence is in µR: a
        reflection at 4 Å sees roughly four times the absorbing cross-section
        one at 1 Å does, and since long λ means long d on a fixed-angle bank,
        the correction suppresses the **long**-d end.  That is the opposite
        end from the Debye-Waller factor, which is why leaving it out biases
        a refined Biso rather than disappearing into the scale.

        :func:`~rietx.model.absorption.cylinder_absorption` unchanged, with an
        array of µR where the constant-wavelength path passes a scalar — the
        Rouse expression is arithmetic in µR and broadcasts.
        """
        if self.absorption_terms is None:
            return None
        a, b = self.absorption_terms
        return cylinder_absorption(self.two_theta_bank_deg,
                                   a * self.wavelength_of(d) + b)

    def incident_spectrum(self, values: dict[str, float]):
        """I_i on this bank's channels, or ``None`` when the file declares none.

        **Per channel, and a function of the flight time rather than of λ.**
        The GSAS ``ITYP`` functions take T in milliseconds directly
        (:mod:`rietx.model.tof_spectrum`, which quotes the manual's three
        independent statements of it), so this needs no inverse of the
        calibration and no wavelength: the abscissa *is* the argument, once
        divided by a thousand.

        **``None`` rather than an array of ones** when ``spectrum_itype`` is 0.
        A bank whose reduction already divided by a vanadium spectrum then
        multiplies by nothing at all, which is bit-identical rather than
        merely equal — and it is what ISIS GEM, SNS NOMAD and POWGEN write.
        A LANSCE-style file writes ``ITYP 1`` with a full ``ICOFF`` block,
        i.e. its histograms still carry the moderator's own output, and
        without this factor a smooth envelope in λ and an isotropic
        displacement parameter are nearly the same shape, so a fit that
        leaves it out gives the envelope to Biso.

        The coefficients come out of ``values``, so a stage that frees them
        moves them; :meth:`phase_component` is where the result is applied.
        """
        if self.spectrum_itype == 0:
            return None
        return incident_spectrum(self.spectrum_itype,
                                 [values[p] for p in self.spectrum_paths],
                                 self.tof)

    def channel_width_factor(self):
        """W(T) on this bank's channels, or ``None`` when none is owed.

        The second factor of GSAS's ``I_o = I'_o / (W·I_i)`` (manual PAGE 127).
        A calculated Bragg sum is an **intensity density** — a unit-area
        profile times a reflection intensity — while a histogram channel that
        was never divided by its own width holds a *number of counts*.  The two
        differ by W(T), and on a real bank W(T) is not a constant: an ISIS GEM
        ``RALF`` bank is Δt/t = 0.004 throughout, i.e. W exactly proportional
        to T, and a ``TIME_MAP`` bank — constant Δt at short flight times, then
        pseudo-constant Δt/t — rises by a factor of several across one fitted
        window.  So it is a **slope in flight time**, not a scale: a fit
        without it does not
        absorb it into the phase scale, it charges it to whatever else has a
        smooth shape in d — which is the isotropic displacement parameter.

        **Frozen at compile, from the pattern's own abscissa.**  Nothing about
        the instrument knows it: a ``TIME_MAP`` bank's widths are *tabulated*
        in the data file, and a ``RALF`` bank's stated coefficients reproduce
        its own x column only to ~10⁻⁵ of the flight time (T-1's measurement).
        The channel's edges are taken at the **midpoints of its neighbours**,
        which is the convention that makes the edges of adjacent channels
        agree: e_i = (T_{i-1} + T_i)/2, and the two ends of the pattern get
        the half-width of their one neighbour.  W_i = e_{i+1} − e_i is then
        (T_{i+1} − T_{i-1})/2 in the interior — ``numpy.gradient`` exactly,
        which is what this is.

        Returns ``None`` where no factor is owed, so a declared ``"density"``
        bank and an unstated one both take the same code path they always
        took.  The factor carries a **microsecond**, and it is deliberately
        not normalised out: the manual's relation is written in the file's own
        units, and dividing by W at some chosen channel would put a hidden
        reference flight time into the phase scale.
        """
        return self.channel_width

    def phase_peaks(self, ip: int, values: dict[str, float],
                    hkl_intensity: np.ndarray | None = None) -> list[tuple]:
        """``[(pos, α, β, σ, γ, intensity)]`` — one tuple, for the one "line".

        A list of one because a time-of-flight bank has no emission lines and
        the shared consumers index ``[0]`` for "the primary"; a **six**-tuple
        because the back-to-back shape needs four width parameters where the
        constant-wavelength pseudo-Voigt needs two.  Slot 0 is the position in
        every arm, which is the contract the callers that read
        ``phase_peaks(ip, values)[0][0]`` actually rely on.
        """
        xp = get_backend()
        cp = self.phases[ip]
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        d = d_spacings(cp.reflections.hkl, *cell)
        pos = self.positions(d, values)
        # ``ip``: the widths of a bank are the instrument's **plus this
        # phase's** since T-3c — a crystallite size and a microstrain are
        # properties of the specimen, so they are per phase where α, β and the
        # instrument's σ², γ are per bank.
        alpha, beta, sigma, gamma = self.shape_parameters(d, values, ip)

        if self.mode in ("lebail", "pawley"):
            intensity = cp.hkl_intensity if hkl_intensity is None else hkl_intensity
            intensity = xp.asarray(intensity, dtype=np.float64)
        else:
            # ⟨|F|²⟩ **before** the Lorentz factor and before the per-channel
            # spectrum and width factors ``phase_component`` applies.
            f2 = structure_factors_squared(
                cp.reflections.hkl, d, cp.sites,
                *self._site_values(ip, values, cell))
            mult = xp.asarray(cp.reflections.multiplicity, dtype=np.float64)
            intensity = (values[f"phases.{ip}.scale"] * mult * f2
                         * self.lorentz(d))
            absorption = self.absorption(d)
            if absorption is not None:
                intensity = intensity * absorption
            if not cp.skip_extinction:
                # Sabine's secondary extinction, per reflection at **its own**
                # wavelength — the constant-wavelength function unchanged, with
                # an array of λ where a scalar per emission line used to go.
                # The λ dependence is real and steep: x carries (λ/V)², and the
                # angular factor is the bank's, fixed, so E runs monotonically
                # across the histogram in a way a single-wavelength scan never
                # shows.  ``skip_extinction`` is the same compile-time
                # structural gate the constant-wavelength model uses, so
                # ext = 0 is skipped rather than evaluated to ones.
                intensity = intensity * sabine_extinction(
                    f2, self.wavelength_of(d), cell_volume(*cell),
                    self.two_theta_bank_deg,
                    values[f"phases.{ip}.extinction"])
        return [(pos, alpha, beta, sigma, gamma, intensity)]

    def _site_values(self, ip: int, values: dict[str, float], cell: tuple):
        """(xyz, occ, biso, U^ij, a*) for the structure-factor call.

        The same block :class:`~rietx.model.forward.CompiledModel` builds, and
        deliberately the same code — |F|² is radiation-blind and the neutron
        scattering-length branch is chosen at ``compile_phase_sites``, not
        here.
        """
        from .forward import CompiledModel

        return CompiledModel._site_values(self, ip, values, cell)

    def profile(self, dt, alpha, beta, sigma, gamma):
        """Ω(ΔT), the unit-area peak shape.  ΔT = channel − peak, in µs."""
        if self.profile_kind == "gaussian":
            return back_to_back_gaussian(dt, alpha, beta, sigma)
        return back_to_back_pseudovoigt(dt, alpha, beta, sigma, gamma)

    def profile_at(self, x, alpha, beta, sigma, gamma):
        """The public reader of the shape dispatch — the peer of
        :meth:`rietx.model.forward.CompiledModel.profile_at`.

        Same body as :meth:`profile`; a separate name because it is the one an
        axis-blind consumer outside this module calls with a
        :meth:`phase_peaks` width tuple, and because the constant-wavelength
        twin has a distinction to draw there (its ``profile_at`` is the
        *symmetric* shape, with the FCJ axial convolution applied elsewhere).
        This arm has no axial convolution, so the two are the same function
        and the docstring says so rather than leaving a reader to wonder which
        of the two shapes came back.
        """
        return self.profile(x, alpha, beta, sigma, gamma)

    def phase_component(self, ip: int, values: dict[str, float],
                        hkl_intensity: np.ndarray | None = None) -> np.ndarray:
        """One phase's Bragg contribution, summed over its frozen windows.

        Batched on numpy, the per-reflection loop on every traced backend —
        the same split :meth:`~rietx.model.forward.CompiledModel.phase_component`
        makes, for the same reason: the scatter is a ``bincount`` and the loop
        is the oracle that says the two agree.  Measured on a real bank of a
        large-cell cubic standard: the batched build is about 4x faster per
        phase than the loop, and the two arrays agree with ``max|delta| = 0.0``
        -- bit for bit, not to rounding, because the ``bincount`` scatters the
        same terms the windowed adds do.  4x matters here because a
        finite-difference Jacobian is one evaluation per free parameter per
        iteration.

        **The incident spectrum and the channel width are applied here, once,
        to the summed Bragg contribution**, and they are the only place in this
        class where a correction is per *channel* rather than per reflection.
        They have to be: GSAS's own operation is a point-by-point division of
        the observed counts (manual PAGE 127, ``I_o = I'_o / W·I_i``), so the
        faithful multiplication is point by point too, and a peak whose Δd/d is
        a per cent sits across a per cent of the envelope.  The two are the two
        factors of that one relation, and they are applied together here for
        that reason rather than being spread over two call sites.

        The background is deliberately **not** multiplied by either — it is
        fitted in the observed space, so whatever they do to it is already in
        the coefficients the background refines, and applying the shape there
        as well would apply it twice.
        """
        if get_backend().name == "numpy":
            y = self._phase_component_batched(ip, values, hkl_intensity)
        else:
            y = self._phase_component_scalar(ip, values, hkl_intensity)
        spectrum = self.incident_spectrum(values)
        if spectrum is not None:
            y = y * spectrum
        width = self.channel_width_factor()
        return y if width is None else y * width

    def _phase_component_batched(self, ip: int, values: dict[str, float],
                                 hkl_intensity: np.ndarray | None = None
                                 ) -> np.ndarray:
        """Every window of the phase flattened into one Ω evaluation."""
        idx, seg = self.flat_windows[ip]
        if len(idx) == 0:
            return np.zeros(self.n_points, dtype=np.float64)
        (pos, alpha, beta, sigma, gamma, intensity), = self.phase_peaks(
            ip, values, hkl_intensity)
        pos = np.asarray(pos, dtype=np.float64)
        omega = self.profile(self.tof[idx] - pos[seg], np.asarray(alpha)[seg],
                             np.asarray(beta)[seg], np.asarray(sigma)[seg],
                             np.asarray(gamma)[seg])
        return np.bincount(idx, weights=np.asarray(intensity)[seg] * omega,
                           minlength=self.n_points)

    def _phase_component_scalar(self, ip: int, values: dict[str, float],
                                hkl_intensity: np.ndarray | None = None
                                ) -> np.ndarray:
        """The per-reflection loop: the traced backends' path, and the oracle."""
        xp = get_backend()
        cp = self.phases[ip]
        y = xp.zeros_like(self.tof)
        grid = xp.asarray(self.tof, dtype=np.float64)
        (pos, alpha, beta, sigma, gamma, intensity), = self.phase_peaks(
            ip, values, hkl_intensity)
        for k in range(len(cp.reflections.hkl)):
            i0, i1 = int(cp.win[0, k, 0]), int(cp.win[0, k, 1])
            if i1 <= i0:
                # the frozen empty window: a reflection outside the fitted
                # range.  A compile-time structural branch, never one on θ.
                continue
            omega = self.profile(grid[i0:i1] - pos[k], alpha[k], beta[k],
                                 sigma[k], gamma[k])
            y = xp.window_add(y, i0, i1, intensity[k] * omega)
        return y

    def peak_fwhm(self, alpha, beta, sigma, gamma) -> np.ndarray:
        """An estimate of the peak's full width at half maximum, in µs.

        The exponential pair contributes ≈ ln2·(1/α + 1/β) between its own
        half-height points and the resolution function contributes its
        pseudo-Voigt Γ; added in quadrature, which is an *estimate* and is
        labelled one — it is used for window sizing and for reporting a width,
        never inside the residual.
        """
        xp = get_backend()
        fwhm_pv, _eta, _s = tof_pseudovoigt_widths(sigma, gamma)
        expo = math.log(2.0) * (1.0 / xp.maximum(alpha, _MIN_RATE)
                                + 1.0 / xp.maximum(beta, _MIN_RATE))
        return xp.sqrt(expo ** 2 + fwhm_pv ** 2)

    # ------------------------------------------------------------------
    # the shared diagnostics' small surface
    # ------------------------------------------------------------------
    def phase_support(self, values: dict[str, float]) -> np.ndarray:
        """Each phase's strongest modelled point, in σ of the observation noise."""
        sigma = np.asarray(self.sigma, dtype=np.float64)
        out = np.zeros(len(self.phases), dtype=np.float64)
        for ip in range(len(self.phases)):
            y = np.asarray(self.phase_component(ip, values), dtype=np.float64)
            out[ip] = float(np.max(y / sigma)) if len(y) else 0.0
        return out

    def phase_line_counts(self) -> np.ndarray:
        """How many frozen windows of each phase cover a point at all."""
        out = np.zeros(len(self.phases), dtype=np.int64)
        for ip, cp in enumerate(self.phases):
            out[ip] = int(np.count_nonzero(cp.win[:, :, 1] > cp.win[:, :, 0]))
        return out

    def scalar_chain_supported(self, path: str) -> bool:
        """No analytic scalar chain on this arm — see :attr:`analytic_jacobian`."""
        return False

    def derivative_bases(self, values, intensities=None, *,
                         axial_derivs: bool = True,
                         profile_derivs: bool = True):
        """No analytic bases on this arm.

        Raises rather than returning ``None``: a caller reaching here has
        already decided to build an analytic column, and a ``None`` would come
        back as a *short* column — the WP-1070 failure this package names by
        hand.  The gate is :attr:`analytic_jacobian`, above the call.
        """
        raise ValueError(
            "CompiledTOFModel has no analytic derivative bases: every analytic "
            "Jacobian column in this package chains through per-emission-line "
            "planes, a pseudo-Voigt profile basis and an FCJ node set, and a "
            "time-of-flight bank has none of the three. The finite-difference "
            "fallback is the path for this arm and is selected by "
            "model.analytic_jacobian being False; reaching this function means "
            "that gate was not asked.")

    def structure_intensity_partition(self, values: dict[str, float]) -> list:
        """(I_obs, I_calc) per reflection — not evaluated on this arm.

        The constant-wavelength partition divides the observed profile between
        overlapping reflections using their calculated shapes; it is well
        defined here too, and it is not written yet.  Returning empty pairs
        would report "no reflections", which is a different and false claim, so
        this says so instead.
        """
        raise ValueError(
            "structure_intensity_partition is not implemented for a "
            "time-of-flight bank: the observed/calculated per-reflection "
            "partition needs the same profile decomposition the "
            "constant-wavelength model does, and it is a later rung of the "
            "time-of-flight track (yue-here/rietx issue #193). The fitted "
            "curve, Rwp and the refined parameters are all available.")


# ----------------------------------------------------------------------
# compilation
# ----------------------------------------------------------------------
def compile_tof_model(structure: Structure, instrument: Instrument,
                      pattern: PatternData, *, mode: Mode = "rietveld",
                      tof_limits: tuple[float, float] | None = None,
                      moving_paths: set[str] | None = None,
                      restraint_weight_scale: float = 1.0,
                      window_slack_us: float | None = None,
                      orbit_split: list | None = None,
                      lorentz_window_tol: float | None = None
                      ) -> CompiledTOFModel:
    """Freeze reflection lists and evaluation windows for one TOF stage.

    The mirror of :func:`~rietx.model.forward.compile_model`, and the pair is
    matched at the boundary: a time-of-flight pattern with a ``neutron_tof``
    instrument comes here, a 2θ pattern with a constant-wavelength instrument
    goes there, and **both mismatched pairs are refused** — by
    :func:`~rietx.schemas.pattern.require_two_theta` on the way to
    ``compile_model``, and by the two checks at the top of this function on the
    way here.

    ``tof_limits`` is a ``(lo, hi)`` window in **microseconds**, the flight-time
    spelling of ``two_theta_limits``.  ``moving_paths`` is every parameter the
    coming stage can move, or ``None`` for "no claim made"; it is used for one
    structural decision — whether the type-3 pseudo-Voigt shape is compiled in
    because a γ coefficient can move off zero this stage.  ``orbit_split`` is
    :func:`~rietx.model.forward.compile_model`'s, with the same meaning: the
    split a fit decided at its start (WP-2052), so a stage that drives a
    half-occupied atom onto a mirror keeps its multiplicity on a bank too.

    ``lorentz_window_tol`` is the per-side area fraction of each peak's
    **Lorentzian component** the windows may leave outside, or ``None`` for
    the one rule :data:`TOF_WINDOW_AREA_TOL` states for every component.  Given
    a number, the resolution extent holds the Gaussian component to
    :data:`TOF_WINDOW_AREA_TOL` and the Lorentzian to this, each separately
    (:func:`window_fwhm_mult_split`); the exponential wings are never
    loosened.  It has no effect on the Gaussian branch, whose windows are the
    one-rule windows bit for bit.  A staged plan passes a coarse value in every
    declared stage but the last (``RefinementPlan.stage_lorentz_window_tols``).

    What this refuses, by name
    --------------------------
    Specimen absorption declared as a scalar µR, preferred orientation, surface
    roughness, anisotropic (Stephens) strain and soft restraints are all
    **refused when declared**, naming T-3, rather than dropped.  Each has a
    definite reason: µ varies within one histogram because λ does (WP-1132's
    own scope note says so); March-Dollase and Stephens are both written in
    deg 2θ and would need their time-of-flight forms derived, not
    reinterpreted.  A model that silently ignored a declared correction would
    report a fit the caller did not ask for.

    """
    _require(pattern.axis == "tof",
             "compile_tof_model(): this pattern's abscissa is 2θ in degrees, "
             "not a time of flight in microseconds. A constant-wavelength "
             "pattern is compiled by rietx.model.forward.compile_model; this "
             "function is the time-of-flight arm and the pair must match.")
    _require(instrument.source.kind == "neutron_tof",
             f"compile_tof_model(): this instrument's source is "
             f"{instrument.source.kind!r}, not a neutron_tof bank, while the "
             f"pattern is a time of flight in microseconds. The flight time of "
             f"a reflection comes from the bank's DIFC/DIFA/TZERO/DIFB, which "
             f"only a neutron_tof source carries.")
    _require(restraint_weight_scale >= 0.0,
             f"restraint_weight_scale must be >= 0 "
             f"(got {restraint_weight_scale})")
    if orbit_split is not None:
        _require(len(orbit_split) == len(structure.phases),
                 f"an orbit split for {len(orbit_split)} phases was handed to "
                 f"a structure of {len(structure.phases)}")
        for phase, ops in zip(structure.phases, orbit_split, strict=True):
            _require(len(ops) == len(phase.atoms),
                     f"phase {phase.name!r}: an orbit split for {len(ops)} "
                     f"atoms was handed to a phase of {len(phase.atoms)}")
    _require(mode == "rietveld",
             f"compile_tof_model(): mode={mode!r} is not implemented for a "
             f"time-of-flight bank. Le Bail and Pawley extraction both need "
             f"the per-reflection profile partition this arm does not have "
             f"yet; they are a later rung of the time-of-flight track "
             f"(yue-here/rietx issue #193). Rietveld refinement against a "
             f"structure is what this build does.")

    src = instrument.source
    geom = instrument.geometry
    _require(geom.mu_r in (None, 0.0),
             f"compile_tof_model(): geometry.mu_r = {geom.mu_r!r} is a "
             f"dimensionless µR, i.e. an absorption **at one wavelength**, and "
             f"a time-of-flight bank has many: µ follows the 1/v law, so µR "
             f"runs linearly with λ across the histogram and the number you "
             f"declared would be right at exactly one channel. This arm "
             f"computes µ(λ) from the composition instead — declare "
             f"geometry.capillary_radius_mm (and packing_fraction) and clear "
             f"mu_r. GSAS's own warning applies either way (LAUR 86-748, "
             f"Technical Manual p. 134): the correction is indistinguishable "
             f"from thermal motion and should not be refined.")
    _require(geom.mu_t is None,
             f"compile_tof_model(): geometry.mu_t = {geom.mu_t!r} is a "
             f"flat-specimen absorption and this arm's specimen model is the "
             f"cylinder (Rouse et al., 1970). It carries the same "
             f"one-wavelength problem as mu_r and has no λ-resolved twin here "
             f"yet; the flight-time flat-plate form is a later rung of the "
             f"time-of-flight track (yue-here/rietx issue #193).")
    _require(geom.surface_roughness is None,
             "compile_tof_model(): surface roughness is declared and this arm "
             "cannot apply it — Instrument's own validator already refuses it "
             "on any non-X-ray source. Set geometry.surface_roughness = None.")
    for ip, phase in enumerate(structure.phases):
        _require(phase.preferred_orientation is None,
                 f"compile_tof_model(): phases.{ip} declares preferred "
                 f"orientation and this arm cannot apply it. March-Dollase "
                 f"averages over a reflection's symmetry orbit at the "
                 f"*measured* angle, and on a time-of-flight bank every "
                 f"reflection shares one angle — the correction has a "
                 f"different form here, not a different value. Texture on a "
                 f"bank is a later rung of the time-of-flight track "
                 f"(yue-here/rietx issue #193).")
        _require(phase.texture is None,
                 f"compile_tof_model(): phases.{ip} declares a "
                 f"spherical-harmonic texture and this arm cannot apply it: "
                 f"the correction is evaluated by the constant-wavelength "
                 f"model only, and nothing here computes it. Texture on a bank "
                 f"is a later rung of the time-of-flight track "
                 f"(yue-here/rietx issue #193); refusing rather than dropping "
                 f"it is the point.")
        # a phase with a moment asks the one dispatch authority, which refuses
        # a source it does not name rather than drawing the nuclear part alone
        magnetic_wanted(phase, src)
        _require(phase.microstrain is None,
                 f"compile_tof_model(): phases.{ip} declares a Stephens "
                 f"anisotropic-strain block and this arm cannot apply it: "
                 f"strain_width_deg returns a width in **deg 2θ** "
                 f"(crystallography/stephens.py), which is not a microsecond. "
                 f"The time-of-flight form is an hkl-dependent addition to the "
                 f"sig coefficients, which is a width law and not one of T-3's "
                 f"lambda-per-channel corrections; it is a later rung of the "
                 f"time-of-flight track (yue-here/rietx issue #193) and is not "
                 f"written.")
        _require(not phase.restraints,
                 f"compile_tof_model(): phases.{ip} declares soft restraints "
                 f"and this arm does not assemble the restraint rows yet. "
                 f"They are radiation-blind and will transfer unchanged; "
                 f"refusing rather than dropping them is the point.")

    mask = pattern.in_range_mask()
    x_all, y_all, s_all = pattern.tof_us(), pattern.y(), pattern.sig()
    if tof_limits is not None:
        lo, hi = tof_limits
        mask &= (x_all >= lo) & (x_all <= hi)
    tof, y_obs, sigma = x_all[mask], y_all[mask], s_all[mask]
    _require(len(tof) >= 10, "fewer than 10 points remain in the fit range")
    tof_min, tof_max = float(tof[0]), float(tof[-1])

    # W(T), and only where the *pattern* says one is owed.  Measured on the
    # **whole** abscissa and then masked, never on the masked grid: the widths
    # are a property of the histogram's channel layout, and taking the
    # difference across an excluded region or a fit-window edge would report
    # the gap as a channel width.  ``None`` where no factor is owed, so a
    # density and an unstated basis both take the pre-T-3b code path exactly
    # (see ``CompiledTOFModel.channel_width_factor`` for the edge convention
    # and for why it is not normalised).
    channel_width = (np.gradient(x_all)[mask]
                     if pattern.intensity_basis == "counts" else None)

    moving = set() if moving_paths is None else set(moving_paths)
    prof = src.profile_tof
    p = "instrument.source.profile_tof."
    gamma_can_move = (prof.gam0.value != 0.0 or prof.gam1.value != 0.0
                      or prof.gam2.value != 0.0
                      or any(p + g in moving for g in ("gam0", "gam1", "gam2")))
    # T-3c: a phase's Lorentzian sample broadening is a γ this bank carries,
    # so it decides the shape branch on exactly the same terms the
    # instrument's three coefficients do — a non-zero value, or a path this
    # stage can move off zero.  Without this a stage that frees ``lor_size``
    # against an all-Gaussian instrument would compile the Gaussian branch and
    # the column would move nothing, which is the silent dead column WP-1073
    # names.
    gamma_can_move = gamma_can_move or any(
        phase.lor_size.value != 0.0 or phase.lor_strain.value != 0.0
        or f"phases.{ip}.lor_size" in moving
        or f"phases.{ip}.lor_strain" in moving
        for ip, phase in enumerate(structure.phases))
    profile_kind = "pseudovoigt" if gamma_can_move else "gaussian"

    # The d range the fitted flight-time window corresponds to, at the stored
    # calibration.  Widened by the window slack so a reflection just outside the
    # ends still gets a (possibly empty) window rather than being absent from
    # the list: a peak whose tail reaches into the data must be modelled.
    edge = max(WINDOW_MIN_US, WINDOW_SLACK_FRAC * tof_max) * 4.0
    d_hi = float(src.d_from_tof(tof_max + edge))
    d_lo = float(src.d_from_tof(max(tof_min - edge, 1e-6)))
    _require(d_hi > d_lo > 0.0,
             f"compile_tof_model(): the fitted window {tof_min:.1f}-"
             f"{tof_max:.1f} µs maps to d = {d_lo:.4g}-{d_hi:.4g} Å under this "
             f"bank's calibration, which is not an increasing positive range. "
             f"A DIFC/DIFA/TZERO sign or unit is wrong.")

    # ``generate_reflections`` is radiation-free in everything but its
    # *arguments*: λ and 2θ enter only as d_min = λ/(2 sin θ_max) and
    # d_max = λ/(2 sin θ_min).  Handing it λ = 2·d_min with 2θ_max = 180°
    # reproduces exactly the d range wanted, with no second enumerator to keep
    # in step with this one.
    lam_gen = 2.0 * d_lo
    tt_gen_min = 2.0 * math.degrees(math.asin(min(d_lo / d_hi, 1.0)))

    lorentz_tol = None if lorentz_window_tol is None else float(lorentz_window_tol)
    _require(lorentz_tol is None or 0.0 < lorentz_tol < 0.5,
             f"compile_tof_model(): lorentz_window_tol = {lorentz_window_tol!r} "
             f"is a per-side fraction of a peak's area and must lie in (0, 0.5).")
    phases: list[CompiledPhase] = []
    flat_windows: list[tuple[np.ndarray, np.ndarray]] = []
    for ip, phase in enumerate(structure.phases):
        cell = phase.cell.lengths_angles()
        refl = generate_reflections(phase.space_group, cell, lam_gen,
                                    two_theta_max=180.0,
                                    two_theta_min=tt_gen_min)
        # A time-of-flight bank scatters off the same nuclei a constant-
        # wavelength neutron bank does, so the neutron scattering-length table
        # is the one that resolves — the branch T-1 already widened in
        # ``compile_phase_sites``'s caller.
        sites = compile_phase_sites(
            phase, None, neutron=True,
            ops=None if orbit_split is None else orbit_split[ip])

        n = len(refl)
        d = d_spacings(refl.hkl, *cell)
        pos = np.asarray(src.tof_from_d(d), dtype=np.float64)
        alpha = np.asarray(tof_alpha(d, prof.alpha0.value, prof.alpha1.value))
        beta = np.asarray(tof_beta(d, prof.beta0.value, prof.beta1.value))
        var = np.asarray(tof_sigma_sq(d, prof.sig0.value, prof.sig1.value,
                                      prof.sig2.value))
        gam = np.asarray(tof_gamma(d, prof.gam0.value, prof.gam1.value,
                                   prof.gam2.value))
        _require(n == 0 or (np.all(alpha > _MIN_RATE) and np.all(beta > _MIN_RATE)),
                 f"compile_tof_model(): the bank's ProfileTOF gives a "
                 f"non-positive α or β over the fitted d range "
                 f"({d_lo:.4g}-{d_hi:.4g} Å): α = α₀ + α₁/d with "
                 f"α₀ = {prof.alpha0.value:g}, α₁ = {prof.alpha1.value:g} and "
                 f"β = β₀ + β₁/d⁴ with β₀ = {prof.beta0.value:g}, "
                 f"β₁ = {prof.beta1.value:g}. Both are decay rates in µs⁻¹ and "
                 f"the back-to-back pulse has amplitude αβ/(α+β) and infinite "
                 f"width at either limit, so there is no peak to compute. An "
                 f"all-zero ProfileTOF is what a declined GSAS PRCF block "
                 f"leaves behind — seed the coefficients before refining.")
        _require(n == 0 or np.all(var >= 0.0),
                 f"compile_tof_model(): σ²(d) = sig0 + sig1·d² + sig2·d⁴ is "
                 f"negative somewhere in {d_lo:.4g}-{d_hi:.4g} Å "
                 f"(sig0={prof.sig0.value:g}, sig1={prof.sig1.value:g}, "
                 f"sig2={prof.sig2.value:g}). These are **variances**, not "
                 f"FWHMs and not quantities to be squared again.")
        # The Lorentzian twin of the check above, and it had no equivalent
        # until T-1d: ``sig2`` was caught because the variance polynomial is
        # checked, while ``gam0``/``gam1``/``gam2`` were not, and a real bank
        # converged at **gam1 = −5.749** — a negative Lorentzian FWHM
        # coefficient — with nothing refusing or warning.  A negative width is
        # not a physical peak shape either.
        #
        # A *check* rather than a bound, and for the reason the σ² check is
        # one: γ(d) ≥ 0 couples all three coefficients over the fitted range,
        # which a box cannot express, and a negative γ₁ beside a positive γ₀
        # and γ₂ is admissible (it is how a resolution function narrows and
        # then broadens again).  So the coefficients keep their signs and the
        # *polynomial* is what has to be non-negative — exactly the
        # STEPHENS_STRAIN_NOT_POSITIVE cone/box distinction one arm over.
        _require(n == 0 or np.all(gam >= 0.0),
                 f"compile_tof_model(): γ(d) = gam0 + gam1·d + gam2·d² is "
                 f"negative somewhere in {d_lo:.4g}-{d_hi:.4g} Å "
                 f"(gam0={prof.gam0.value:g}, gam1={prof.gam1.value:g}, "
                 f"gam2={prof.gam2.value:g}). These are Lorentzian **FWHMs** "
                 f"in µs, µs/Å and µs/Å², and a negative total width is not a "
                 f"peak shape. A negative single coefficient is fine — it is "
                 f"the sum over the fitted d range that must stay positive.")

        # The specimen's own width, at the values the stage starts from, so a
        # broadened peak gets a window that holds it.  Frozen here for the
        # reason every other window input is: the window is a structural
        # decision per stage, and the movement headroom the slack below adds is
        # what covers a size or strain that moves inside the stage.  A phase
        # with rietx's default of no sample broadening adds an exact ±0 and
        # leaves ``gam`` and ``var`` bit for bit.
        size_l, strain_l, size_var, strain_var = sample_broadening_terms(
            ip, {f"phases.{ip}.lor_size": phase.lor_size.value,
                 f"phases.{ip}.gauss_size": phase.gauss_size.value,
                 f"phases.{ip}.lor_strain": phase.lor_strain.value,
                 f"phases.{ip}.gauss_strain": phase.gauss_strain.value})
        gam = gam + np.asarray(tof_sample_gamma(d, src.difc.value,
                                                size_l, strain_l))
        var = var + np.asarray(tof_sample_sigma_sq(d, src.difc.value,
                                                   size_var, strain_var))

        fwhm_pv, eta, _s = tof_pseudovoigt_widths(np.sqrt(np.maximum(var, 0.0)),
                                                  gam)
        # ``window_fwhm_mult``'s tolerance is the **two-sided** discard and
        # this extent is added to each side, so the per-side fraction wanted
        # is half of what is passed.
        if lorentz_tol is None or profile_kind == "gaussian":
            resolution = np.asarray(
                window_fwhm_mult(np.asarray(eta), tol=2.0 * TOF_WINDOW_AREA_TOL)
                * np.asarray(fwhm_pv), dtype=np.float64)
        else:
            resolution = np.asarray(
                window_fwhm_mult_split(np.asarray(eta),
                                       2.0 * TOF_WINDOW_AREA_TOL,
                                       2.0 * lorentz_tol)
                * np.asarray(fwhm_pv), dtype=np.float64)
        slack = (WINDOW_MIN_US + WINDOW_SLACK_FRAC * np.abs(pos)
                 if window_slack_us is None
                 else np.full(n, float(window_slack_us)))
        # asymmetric by construction: α is the rise on the short-flight-time
        # side and β the decay on the long one, and β < α is the normal case.
        half_lo = TAIL_EFOLDS / np.maximum(alpha, _MIN_RATE) + resolution + slack
        half_hi = TAIL_EFOLDS / np.maximum(beta, _MIN_RATE) + resolution + slack

        win = np.zeros((1, n, 2), dtype=np.int64)
        valid = np.isfinite(pos)
        pos_v = np.where(valid, pos, 0.0)
        i0 = np.searchsorted(tof, pos_v - np.where(valid, half_lo, 0.0),
                             side="left")
        i1 = np.searchsorted(tof, pos_v + np.where(valid, half_hi, 0.0),
                             side="right")
        i0[~valid] = 0
        i1[~valid] = 0
        win[0, :, 0], win[0, :, 1] = i0, i1

        cp = CompiledPhase(reflections=refl, sites=sites, win=win,
                           fcj_n=np.zeros((1, n), dtype=np.int64))
        # The same off-state gate ``compile_model`` uses, and for the same
        # reason: ext = 0 makes Sabine's E exactly 1.0 in floating point, so a
        # phase that cannot move it off zero this stage skips the six-term Laue
        # series rather than multiplying by ones.  Structural, taken from a
        # value that provably cannot change before the next compile.  A phase
        # that declares none (WP-1944's ``None``) has no row to move.
        cp.skip_extinction = (phase.extinction is None
                              or (phase.extinction.value == 0.0
                                  and f"phases.{ip}.extinction" not in moving))
        phases.append(cp)
        widths = (i1 - i0).astype(np.int64)
        flat_windows.append((
            np.concatenate([np.arange(i0[k], i1[k], dtype=np.int64)
                            for k in range(n) if widths[k] > 0])
            if int(widths.sum()) else np.zeros(0, dtype=np.int64),
            np.repeat(np.arange(n, dtype=np.int64), np.maximum(widths, 0)),
        ))

    # Same gating/widening rule as ``compile_model`` (WP-1309): ``sigma`` may
    # widen here if the background carries its own counting statistics, and
    # the returned array is what ``CompiledTOFModel.sigma`` below must use.
    bkg_paths, design, fixed, penalty, sigma = compile_background(
        instrument.background, tof, tof_min, tof_max,
        gate_off_states=moving_paths is not None, moving_paths=moving,
        sigma=sigma)
    _require("instrument.background.air" not in bkg_paths,
             "compile_tof_model(): a P-spline background carries a 1/x air "
             "term, and 1/2θ is the small-angle air-scatter tail of a "
             "constant-wavelength scan — 1/TOF is not that curve and fitting "
             "it would be fitting an unnamed hyperbola. Use a Chebyshev "
             "background on a time-of-flight bank.")

    # The field names come from ``HUMP_FIELDS``, never re-typed: ``compile_model``
    # builds the same triple from the same tuple that
    # ``params.vector.extra_component_parameters`` registers, so a path cannot
    # be spelled two ways.  Re-typing them here would put a third spelling in
    # the tree and the drift would surface as a KeyError in a residual.  Only
    # the hump-kind members: a sharp ``PeakComponent`` is a windowed tick
    # (``CompiledExtraPeak``, CW-only so far), not a background term.
    component_paths = tuple(
        tuple(f"instrument.extra_components.{i}.{name}"
              for name in HUMP_FIELDS)
        for i, comp in enumerate(instrument.extra_components)
        if comp.kind == "hump")

    absorption_terms = _absorption_terms(structure, instrument, phases)

    # The incident spectrum, frozen as its type and the paths of its
    # coefficients.  The *values* are read from ``values`` on every evaluation
    # (``CompiledTOFModel.incident_spectrum``), so a stage that frees them
    # moves them; only the structural half — which function, how many terms —
    # is decided here, which is the same rule ``profile_kind`` follows.
    spec = src.incident_spectrum
    spectrum_itype = int(spec.itype)
    spectrum_paths = tuple(f"instrument.source.incident_spectrum.p{i}"
                           for i in range(1, len(spec.coefficients) + 1))

    theta_bank = math.radians(0.5 * src.two_theta_bank_deg)
    # The two ends of the fitted window in µR, for the report.  d_lo/d_hi are
    # the *widened* d range the windows were cut over rather than the fitted
    # one exactly, which overstates the span by the window slack — a few parts
    # in a thousand, and in the safe direction for a domain warning.
    if absorption_terms is None:
        mu_r_range = None
    else:
        a_mu, b_mu = absorption_terms
        s_bank = math.sin(theta_bank)
        mu_r_range = (a_mu * 2.0 * d_lo * s_bank + b_mu,
                      a_mu * 2.0 * d_hi * s_bank + b_mu)
    return CompiledTOFModel(
        intensity_basis=pattern.intensity_basis, channel_width=channel_width,
        tof=tof, y_obs=y_obs, sigma=sigma, tof_min=tof_min, tof_max=tof_max,
        two_theta_bank_deg=float(src.two_theta_bank_deg),
        sin_theta_bank=math.sin(theta_bank),
        mode=mode, phases=phases, flat_windows=flat_windows,
        fixed_background=fixed, bkg_paths=bkg_paths, bkg_design=design,
        bkg_penalty=penalty, component_paths=component_paths,
        profile_kind=profile_kind,
        spectrum_itype=spectrum_itype, spectrum_paths=spectrum_paths,
        absorption_terms=absorption_terms, mu_r_range=mu_r_range,
        d_range=(d_lo, d_hi), difc_stage=float(src.difc.value),
        restraint_weight_scale=float(restraint_weight_scale),
        lorentz_window_tol=(None if profile_kind == "gaussian"
                            else TOF_WINDOW_AREA_TOL if lorentz_tol is None
                            else lorentz_tol),
    )


def window_fwhm_mult_split(eta, tol_gauss: float, tol_lorentz: float) -> np.ndarray:
    """k(η): FWHM multiples holding each pseudo-Voigt component to its own bar.

    :func:`~rietx.model.forward.window_fwhm_mult` bounds the *sum* of the two
    components' discards, D(k) = η·(2/π)·arctan(1/2k) + (1−η)·erfc(2√ln2·k) ≤
    tol.  This bounds each term separately — (1−η)·erfc(2√ln2·k) ≤
    ``tol_gauss`` and η·(2/π)·arctan(1/2k) ≤ ``tol_lorentz`` (the Gaussian and
    Lorentzian tail masses beyond ±k·Γ, both components sharing Γ by the TCH
    construction; Thompson, Cox & Hastings 1987, *J. Appl. Cryst.* **20**, 79)
    — and returns the larger of the two roots, both closed-form.  Both
    tolerances are **two-sided**, as ``window_fwhm_mult``'s is.  It exists so
    the Lorentzian tail, the one that is ~η/(π·tol) FWHM long, can be given a
    stated tolerance of its own without the Gaussian one moving.
    """
    from scipy.special import erfcinv

    eta = np.clip(np.asarray(eta, dtype=np.float64), 0.0, 1.0)
    c = 2.0 * math.sqrt(math.log(2.0))
    gauss_w = 1.0 - eta
    with np.errstate(divide="ignore", invalid="ignore"):
        k_g = np.where(gauss_w > tol_gauss,
                       erfcinv(np.minimum(tol_gauss / np.maximum(gauss_w, 1e-300),
                                          1.0)) / c, 0.0)
        # (2/π)·arctan(1/2k) = t/η  ⇔  k = 1 / (2·tan(π·t / 2η))
        k_l = np.where(eta > tol_lorentz,
                       0.5 / np.tan(0.5 * np.pi * tol_lorentz
                                    / np.maximum(eta, 1e-300)), 0.0)
    return np.maximum(k_g, k_l)


def _absorption_terms(structure: Structure, instrument: Instrument,
                      phases: list[CompiledPhase]) -> tuple[float, float] | None:
    """``(a, b)`` with µR(λ) = a·λ + b for the packed specimen, or ``None``.

    ``None`` — the correction off — when the geometry declares no capillary
    radius, which is what "nobody asked" looks like and is the same gate the
    constant-wavelength path uses (``refine._resolve_specimen_absorption`` only
    acts when a specimen dimension is declared).

    Three things are decided here rather than per evaluation, and each is
    frozen for the stage exactly as the constant-wavelength model freezes its
    scalar µR:

    **The composition, from the compiled orbits.**  Site multiplicities come
    from ``PhaseSites.ops`` — the orbits the *forward model* used — rather than
    from a second symmetry expansion, so µ can never be computed over a
    different cell content than |F|² was.  **Species are kept whole**: a
    neutron's cross-section depends on the isotope (¹H at 80.27 barn incoherent
    against ²H at 2.05), so the counts are keyed on the species label and not
    reduced to an element the way an X-ray composition legitimately is.

    **The volume fractions, from the scales and the cell volumes, with no
    masses involved.**  Hill-Howard gives W_p ∝ S_p·(ZMV)_p with ZMV = cell
    mass × cell volume, and a volume fraction is W_p/ρ_p with ρ_p ∝ cell
    mass/cell volume — so the cell mass cancels exactly and **v_p ∝ S_p·V_p²**.
    That is the whole weighting, and it needs no atomic weights, no formula
    units and no import from ``optimize.qpa`` (whose ``element_counts`` reduce
    isotopes to elements and would be wrong here for the reason above).  All
    scales zero — a model that has not been scaled yet — falls back to equal
    volumes, which is what ``qpa`` does and says.

    **The domain is reported, not enforced.**  Rouse et al. (1970) fit the
    cylinder integral over 0 ≤ µR ≤ 1 and past that the two-term exponential is
    an extrapolation with no stated error — but a Gd or Cd specimen really is
    that absorbing, and refusing to fit one would be a harder line than the
    constant-wavelength path takes with the same expression
    (``ABSORPTION_MU_R_OUT_OF_RANGE`` is a *warning* there).  So the model
    carries :attr:`CompiledTOFModel.mu_r_range` — µR at the two ends of the
    fitted window — and ``refine`` reports it, with the same warning at the
    same threshold.  What is new here is that **the two ends differ**: µ rises
    with λ, so a bank can be well inside the domain at 1 Å and outside it at
    4 Å, which a single number cannot say.

    Larson & Von Dreele (2004), LAUR 86-748, GSAS Technical Manual PAGE 134,
    for A_B = µR/λ and for the warning that the correction must not be
    refined; the µ(λ) formula is WP-1132's over Sears (1992).
    """
    geom = instrument.geometry
    if geom.capillary_radius_mm is None:
        return None
    _require(geom.kind == "debye_scherrer",
             f"compile_tof_model(): geometry.capillary_radius_mm is declared "
             f"on a {geom.kind!r} specimen. The cylinder absorption factor "
             f"this arm applies (Rouse et al., 1970) is a capillary's; a "
             f"radius on another shape is a field that would be read as one.")

    mus, volumes = [], []
    for ip, phase in enumerate(structure.phases):
        counts: dict[str, float] = {}
        for j, atom in enumerate(phase.atoms):
            multiplicity = len(phases[ip].sites.ops[j][0])
            counts[atom.species] = (counts.get(atom.species, 0.0)
                                    + float(atom.occ.value) * multiplicity)
        volume = float(cell_volume(*phase.cell.lengths_angles()))
        try:
            mus.append(neutron_attenuation_terms(counts, volume))
        except KeyError as exc:
            raise ValueError(
                f"compile_tof_model(): phases.{ip} declares a capillary radius, "
                f"so specimen absorption was asked for, and its composition "
                f"reaches a species the neutron cross-section table does not "
                f"carry — {exc}. Sears (1992) is the table "
                f"(crystallography/neutron.py); clear "
                f"geometry.capillary_radius_mm to refine with no absorption "
                f"correction rather than with a µ missing one element.") from None
        volumes.append(float(phase.scale.value) * volume ** 2)

    total = sum(volumes)
    weights = ([v / total for v in volumes] if total > 0.0
               else [1.0 / len(volumes)] * len(volumes))
    scale = geom.packing_fraction * geom.capillary_radius_mm / 10.0  # mm → cm
    a = scale * sum(w * m[0] for w, m in zip(weights, mus))
    b = scale * sum(w * m[1] for w, m in zip(weights, mus))

    return (a, b)
