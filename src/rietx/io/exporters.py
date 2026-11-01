"""Export a finished refinement in the forms other codes and people consume.

Three artefacts, all built from state the refinement already computed and would
otherwise discard:

- a **reflection table** — one row per (emission line, reflection): hkl, d, 2θ,
  |F|², integrated intensity, multiplicity, phase, line.  Every emission line
  gets its own rows (never only λ₁): the calculated pattern really has a peak at
  each Kα₂ position, and a λ₁-only table would misrepresent the model — the same
  reasoning that makes ``RefinementResult.ticks`` carry every line.
- a **refinement CIF** — the structure with refined values *and* standard
  uncertainties, plus R-factors, wavelength and a profile/background
  description, and the observed/calculated pattern as a pdCIF loop.  The pattern
  loop uses the tags ``io.readers.read_pdcif`` reads, so the package round-trips
  against itself (export → re-read is the cheapest correctness test).
- a **QPA table** — the Hill-Howard weight fractions, carrying the
  "crystalline modelled content only" caveat into the file, not just the API.

References
----------
- Hall, Allen & Brown (1991) Acta Cryst. A47, 655 — CIF.
- Toby (2003) J. Appl. Cryst. 36, 1285 — pdCIF / powder diffraction tags.
- Toby (2006) Powder Diffraction 21, 67 — R-factor definitions.
- Hill & Howard (1987) J. Appl. Cryst. 20, 467 — ZMV weight fractions.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import gemmi
import numpy as np

# format_su is imported from here by the manual's export chapter
from ..crystallography.cif import format_su  # noqa: F401
from ..crystallography.lattice import d_spacings
from ..model.components import COMPONENT_AGGREGATE
from ..model.forward import CompiledModel
from ..optimize.qpa import unmeasured_reason
from ..schemas.instrument import (
    BackgroundChebyshev,
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    Instrument,
)
from ..schemas.pattern import PatternData, require_two_theta
from ..schemas.results import (
    PhaseAgreement,
    QuantitativePhaseAnalysis,
    RefinementResult,
)
from ..schemas.structure import Structure
from .cif.blocks import block_name, write_document, write_structure_block
from .cif.numbers import LINE_MAX, number, text
from .cif.powder import write_pattern_block, write_reflection_loop

_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")


def _cell(values: dict[str, float], ip: int) -> tuple[float, ...]:
    return tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_KEYS)


def _g(x: float) -> str:
    """A compact float string for the CSV tables; a CIF's numbers go through
    :func:`rietx.io.cif.numbers.number` instead."""
    return f"{x:.8g}"


# ======================================================================
# reflection table
# ======================================================================


@dataclass(frozen=True)
class ReflectionRow:
    """One (emission line, reflection) row of a reflection table.

    ``two_theta`` is the *apparent* position the model places the peak at
    (Bragg angle + zero shift + sample-displacement/transparency), matching the
    tick list — not the ideal Bragg angle.  ``f_squared`` is ``None`` in Le
    Bail/Pawley mode, where the per-reflection intensity is extracted or refined
    rather than computed from the structure.  ``intensity`` is the modelled
    integrated intensity of this (line, reflection): in Rietveld mode
    scale·multiplicity·|F|²·P·(line weight)·Lp·extinction·absorption·roughness.

    **On a phase carrying moments, ``f_squared`` is not that |F|²** (issue
    #613).  The intensity is built from ⟨|F_N|²⟩ + p²⟨|F_⊥|²⟩, and on a
    ``"total"`` row — every row of a phase whose magnetic width is at its off
    state — ``f_squared`` is the **nuclear** ⟨|F_N|²⟩ alone.  A magnetic-only
    reflection (a nuclear absence the magnetic group allows: MnF₂'s (1 0 0) under
    136.499) therefore carries ``f_squared == 0`` beside one of the pattern's
    largest intensities.  The magnetic share is in ``intensity``; it gets its
    own row, ``component == "magnetic"`` with ``f_squared`` = p²⟨|F_⊥|²⟩, only
    where the phase's magnetic width is active.

    With anomalous scattering on, ``f_squared`` is the **Friedel-averaged**
    ⟨|F|²⟩ = ½(|F(h)|² + |F(−h)|²) that the powder peak actually contains, not
    the representative reflection's own |F(h)|² — the two differ in a
    non-centrosymmetric group, and only the average is observable in a powder
    (see ``crystallography.structure_factor``).
    """

    phase: str
    line: int              # emission-line index (0 = primary)
    wavelength: float      # Å
    h: int
    k: int
    l: int  # noqa: E741 - the crystallographic Miller index
    d: float               # Å
    two_theta: float       # deg, apparent position
    multiplicity: int
    f_squared: float | None
    intensity: float
    #: m of Q = H + m·k for a satellite of a phase carrying a propagation
    #: vector (WP-1326); 0 on every nuclear reflection, which is every row of
    #: a phase that declares no k.  ``h``/``k``/``l`` stay the **parent**
    #: reciprocal-lattice vector, so a satellite row is read as H and m
    #: together — the (3+1)-index spelling — and ``d`` is the satellite's own.
    satellite_order: int = 0
    #: which contribution this row carries: ``"total"`` for a phase whose
    #: magnetic width is at its off state (:meth:`CompiledModel.mag_split`
    #: false — every phase before WP-1343, and every non-magnetic one since),
    #: or ``"nuclear"``/``"magnetic"`` where the second frozen family is
    #: built, one row of each per (line, reflection) rather than one row
    #: silently carrying the nuclear share alone (WP-1343).
    component: str = "total"
    #: the phase's index in the structure: a link that holds where two phases
    #: share a name (WP-1933, the refinement CIF's ``_pd_refln_phase_id``)
    phase_index: int = 0


REFLECTION_COLUMNS = (
    "phase", "line", "wavelength", "h", "k", "l", "d",
    "two_theta", "multiplicity", "f_squared", "intensity", "satellite_order",
    "component",
)


def reflection_table(model: CompiledModel, values: dict[str, float],
                     structure: Structure) -> list[ReflectionRow]:
    """Reflection rows for every (emission line, reflection) of every phase.

    ``model`` is the compiled model of the finished refinement,
    ``values = ParameterTable(structure, instrument).decode(x0())`` its refined
    parameter dict (see :meth:`rietx.Refinement.reflection_table`, which wires
    this up).  Reflections whose 2θ is non-physical at a given line's wavelength
    (``sinθ > 1``) are dropped for that line only.

    A phase whose magnetic width is active (:meth:`CompiledModel.mag_split`,
    WP-1343) draws its nuclear and magnetic contributions on two separate
    frozen families with, in general, different widths — so this emits one
    row of each, labelled by :attr:`ReflectionRow.component`, rather than a
    single row that would read only the nuclear share — the component-0
    default of :meth:`CompiledModel.phase_peaks`, which is the nuclear
    component alone wherever the magnetic one is drawn separately.  A
    phase with no second family — every phase before WP-1343 — still gets
    exactly one ``"total"`` row per (line, reflection), unchanged.
    """
    rows: list[ReflectionRow] = []
    for ip, cp in enumerate(model.phases):
        name = structure.phases[ip].name
        cell = _cell(values, ip)
        hkl = cp.reflections.hkl
        mult = cp.reflections.multiplicity
        # the parent H labels the row; the *position* is the satellite index
        # H + m·k (WP-1326), which is what the d-spacing and every angle below
        # must be computed from
        order = cp.reflections.satellite_order
        d = d_spacings(cp.reflections.index, *cell)

        def _emit(peaks, f2, component: str) -> None:
            for il, (pos, _gamma, _eta, intensity) in enumerate(peaks):
                lam = float(model.line_wavelengths[il])
                for j in range(len(hkl)):
                    if not np.isfinite(pos[j]):
                        continue
                    rows.append(ReflectionRow(
                        phase=name, line=il, wavelength=lam,
                        h=int(hkl[j][0]), k=int(hkl[j][1]), l=int(hkl[j][2]),
                        d=float(d[j]), two_theta=float(pos[j]),
                        multiplicity=int(mult[j]),
                        f_squared=None if f2 is None else float(f2[j]),
                        intensity=float(intensity[j]),
                        satellite_order=0 if order is None else int(order[j]),
                        component=component, phase_index=ip,
                    ))

        if model.mag_split(ip):
            # WP-1343: two frozen families, one ``base`` each — the same
            # split ``phase_peaks`` itself draws (component 0 = nuclear
            # alone, component 1 = magnetic alone); a single default-argument
            # call here is exactly the bug, silently keeping the nuclear share
            # only.
            f2_nuc = model._nuclear_f2(ip, d, values, cell)
            f2_mag = model._magnetic_f2(ip, d, values, cell)
            _emit(model.phase_peaks(ip, values, component=0), f2_nuc, "nuclear")
            _emit(model.phase_peaks(ip, values, component=1), f2_mag, "magnetic")
        else:
            if model.mode == "rietveld":
                # a satellite carries no nuclear structure factor, and this is
                # the same masked quantity the forward model folded into the
                # intensity
                f2 = model._nuclear_f2(ip, d, values, cell)
            else:  # Le Bail / Pawley: intensity is extracted/refined, not from |F|²
                f2 = None
            _emit(model.phase_peaks(ip, values), f2, "total")
    return rows


def write_reflection_table(rows: list[ReflectionRow], path: str | Path, *,
                           delimiter: str | None = None) -> None:
    """Write reflection rows to CSV/TSV (delimiter inferred from suffix)."""
    p = Path(path)
    if delimiter is None:
        delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=delimiter)
        w.writerow(REFLECTION_COLUMNS)
        for r in rows:
            w.writerow([
                r.phase, r.line, _g(r.wavelength), r.h, r.k, r.l, _g(r.d),
                _g(r.two_theta), r.multiplicity,
                "" if r.f_squared is None else _g(r.f_squared), _g(r.intensity),
                r.satellite_order, r.component,
            ])


# ======================================================================
# QPA table
# ======================================================================


QPA_COLUMNS = (
    "phase", "weight_fraction", "weight_fraction_esd",
    "weight_fraction_corrected", "scale", "cell_mass", "cell_volume", "zmv",
    "mu_r", "brindley_tau", "particle_radius_um",
)


def _qpa_caveats(qpa: QuantitativePhaseAnalysis) -> list[str]:
    lines = [
        "Quantitative phase analysis — Hill & Howard (1987) ZMV weight "
        "fractions.",
        "SCOPE: fractions of the modelled CRYSTALLINE content only. An "
        "unmodelled amorphous fraction or a missing phase still makes these "
        "sum to 1.",
        f"method={qpa.method} crystalline_only={qpa.crystalline_only}",
    ]
    if qpa.unmeasured_phases:
        lines.append(
            "Fractions are relative to the phases measured; "
            + "; ".join(f"{n} not measured ({unmeasured_reason(qpa, n)}, so "
                        "no weight_fraction)" for n in qpa.unmeasured_phases)
            + ".")
    if qpa.microabsorption is not None:
        m = qpa.microabsorption
        lines.append(
            f"Brindley spherical microabsorption correction applied "
            f"(mu_mean={m.mu_mean_cm:.4g} 1/cm at lambda={m.wavelength:.6g} A); "
            "weight_fraction stays the UNCORRECTED Hill-Howard value, "
            "weight_fraction_corrected reported alongside. The corrected value "
            "inherits the (systematic, non-statistical) uncertainty of the "
            "supplied particle radii; the esd column belongs to the "
            "uncorrected fraction. Brindley's treatment is valid for mu_r <= "
            "0.05 — check the mu_r column.")
    elif qpa.microabsorption_skipped is not None:
        lines.append("Microabsorption correction skipped: "
                     f"{qpa.microabsorption_skipped}")
    return lines


def qpa_table_csv(qpa: QuantitativePhaseAnalysis, *, delimiter: str = ",") -> str:
    """The QPA table as CSV text, caveats carried in leading ``#`` comments.

    The crystalline-only scope and any microabsorption status are written into
    the file itself — a weight fraction quoted without them is misleading, so
    they travel with the artefact, not only the API docstring.
    """
    import io as _io

    buf = _io.StringIO()
    for line in _qpa_caveats(qpa):
        buf.write(f"# {line}\n")
    w = csv.writer(buf, delimiter=delimiter)
    w.writerow(QPA_COLUMNS)
    for q in qpa.phases:
        w.writerow([
            q.name, "" if q.weight_fraction is None else _g(q.weight_fraction),
            "" if q.weight_fraction_stderr is None else _g(q.weight_fraction_stderr),
            "" if q.weight_fraction_corrected is None else _g(q.weight_fraction_corrected),
            _g(q.scale), _g(q.cell_mass), _g(q.cell_volume), _g(q.zmv),
            "" if q.mu_r is None else _g(q.mu_r),
            "" if q.brindley_tau is None else _g(q.brindley_tau),
            "" if q.particle_radius_um is None else _g(q.particle_radius_um),
        ])
    return buf.getvalue()


def write_qpa_table(qpa: QuantitativePhaseAnalysis, path: str | Path, *,
                    delimiter: str | None = None) -> None:
    """Write the QPA table to CSV/TSV (delimiter inferred from suffix)."""
    p = Path(path)
    if delimiter is None:
        delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
    # newline="" is not optional and not cosmetic: qpa_table_csv builds its rows
    # with csv.writer, which emits \r\n per the CSV spec, so writing that string
    # through text mode translates each \n again and every line ends \r\r\n —
    # a file with a blank line between every row.  Invisible on POSIX, corrupt
    # on Windows, and measured there (WP-1002).  write_reflection_table above
    # already opens this way; this one did not.
    with p.open("w", newline="", encoding="utf-8") as fh:
        fh.write(qpa_table_csv(qpa, delimiter=delimiter))


# ======================================================================
# refinement CIF
# ======================================================================


#: Each per-phase sample-broadening parameter the profile text names; its
#: unit is the parameter's own (the Gaussian pair are variances, deg²).
_SAMPLE_BROADENING = (("gauss_size", "Gaussian size"), ("gauss_strain", "Gaussian strain"),
                      ("lor_size", "Lorentzian size"), ("lor_strain", "Lorentzian strain"))


def _wrapped(paragraphs: list[str]) -> str:
    """CIF text lines no longer than 80 characters with the field's ";" (PLAT802)."""
    import textwrap

    return "\n".join(textwrap.fill(p, width=LINE_MAX - 1, break_long_words=False)
                     for p in paragraphs)


def _value(p, tag: str = "_pd_proc_ls_profile_function") -> str:
    """A parameter's value with its su in parentheses where it has one."""
    return number(tag, p.value, p.stderr)


def _profile_description(instrument: Instrument, structure: Structure | None = None
                         ) -> str:
    """The profile function as CIF text, every value with its su.

    The shape is the one the fit computed (``ProfileTCHZ.shape``), and each
    phase's sample broadening is stated beside the instrument's, since the
    widths add (Gaussian variances, Lorentzian FWHMs).
    """
    prof, geom = instrument.profile, instrument.geometry
    shape = ("Voigt (exact convolution)" if prof.shape == "voigt" else
             "TCHZ pseudo-Voigt (Thompson, Cox & Hastings 1987)")
    lines = [
        f"{shape} with Finger, Cox & Jephcoat (1994) axial divergence.",
        f"Caglioti Gaussian FWHM^2 in deg^2: U={_value(prof.u)}, "
        f"V={_value(prof.v)}, W={_value(prof.w)}.",
        f"Lorentzian FWHM in deg: X={_value(prof.x)}, Y={_value(prof.y)}.",
        f"Axial divergence: S/L={_value(geom.axial_sl)}, H/L={_value(geom.axial_hl)}.",
    ]
    for phase in (structure.phases if structure is not None else []):
        terms = [f"{label}={_value(getattr(phase, name))} {getattr(phase, name).unit}"
                 for name, label in _SAMPLE_BROADENING
                 if getattr(phase, name).vary or getattr(phase, name).value != 0.0]
        if terms:
            lines.append(f"Phase {phase.name}, sample broadening: "
                         + ", ".join(terms) + ".")
    return _wrapped(lines)


def _background_description(instrument: Instrument) -> str:
    """The background model as a CIF phrase, **including any explicit peaks**.

    A declared background peak is part of the background this fit used, so the
    deposited file has to say so — "4 terms" and "4 terms + 1 explicit Gaussian
    background peak" are different models, and one of them carries three more
    free parameters with an unconstrained position.

    Only the **background-landing** members are counted, read from
    ``model.components.COMPONENT_AGGREGATE`` rather than off the list's length
    (the member contract's clause 2).  Since v1.4 the same list may also hold a
    :class:`~rietx.schemas.instrument.PeakComponent`, which is a declared sharp
    reflection and not background at all; counting it here would deposit a
    sentence saying this fit granted background flexibility it never granted.
    """
    bkg = instrument.background
    if isinstance(bkg, BackgroundChebyshev):
        base = f"shifted-Chebyshev polynomial, {len(bkg.coefficients)} terms"
    elif isinstance(bkg, BackgroundFixedPlusChebyshev):
        # The curve is an estimate or a measurement, and only the model can say
        # which: ``fixed_source`` is the claim, so the word "measured" appears
        # here exactly when somebody named the measurement (WP-1309).  Saying
        # "estimated" of a blank capillary scan would put an assertion nobody
        # made into a file other people read.
        curve = (f"measured curve ({bkg.fixed_source})" if bkg.fixed_source
                 else "fixed estimated curve")
        scale = ("refined scale" if bkg.scale.vary
                 else f"scale held at {bkg.scale.value:.6g}")
        base = (f"{curve}, {scale} + shifted-Chebyshev, "
                f"{len(bkg.chebyshev.coefficients)} terms")
    elif isinstance(bkg, BackgroundPSpline):
        # the unit travels with the number: an intensity-unit λ and a
        # dimensionless one are different stiffnesses (WP-1454)
        base = (f"penalized cubic P-spline, {len(bkg.breakpoints)} knots, "
                f"lambda_smooth={bkg.lambda_smooth:.4g} ({bkg.lambda_units})")
    else:
        base = type(bkg).__name__
    n = sum(1 for c in instrument.extra_components
            if COMPONENT_AGGREGATE[c.kind] == "background")
    if n:
        base += f" + {n} explicit Gaussian background peak{'s' if n > 1 else ''}"
    return base


#: ``_pd_calc_method`` per fit mode (``cif_pd.dic`` gives it as free text).
_CALC_METHOD = {"rietveld": "Rietveld Refinement",
                "lebail": "Le Bail profile decomposition",
                "pawley": "Pawley profile decomposition"}

#: ``_pd_instr_geometry`` per ``Geometry.kind``.
_INSTR_GEOMETRY = {"bragg_brentano": "Bragg-Brentano, flat-plate reflection",
                   "debye_scherrer": "Debye-Scherrer, capillary transmission",
                   "flat_plate_transmission": "flat-plate transmission"}

#: ``_exptl_absorpt_correction_type`` per ``AbsorptionCorrection.method``: the
#: dictionary's enumeration, and the source of each expression.
_ABSORPTION = {
    "rouse_cylinder": ("cylinder", "Rouse, Cooper, York & Chakera (1970) cylinder"),
    "flat_plate_reflection": ("analytical", "flat plate in reflection, ITC C Table "
                              "6.3.3.1 case (2)"),
    "flat_plate_transmission": ("analytical", "flat plate in transmission, ITC C "
                                "Table 6.3.3.1 case (3a)"),
}


def _wavelengths(instrument: Instrument) -> list[tuple[str, str]]:
    """Each line's wavelength and relative weight, through the number rule."""
    source = instrument.source
    if source.kind == "neutron_cw":
        return [(_value(source.wavelength, "_diffrn_radiation_wavelength"),
                 "1.0")]
    return [(_value(line.wavelength, "_diffrn_radiation_wavelength"),
             _value(line.weight, "_diffrn_radiation_wavelength_wt"))
            for line in source.lines]


def _special_details(result: RefinementResult, structure: Structure) -> list[str]:
    """``_pd_proc_ls_special_details``: what no item states, one sentence each.

    The esd method, McCusker et al. (1999) § 10: "In any publication, the
    method used to calculate the e.s.d.'s should be stated."  The inflation
    factor alone does not state it, so the base estimator is named first and
    the factor second.  Written only when the result carries esds: describing
    a method nothing used is a claim.  A March-Dollase correction, whose items
    ``cif_pd.dic`` 2.5 defines only in dotted form (``_pd_pref_orient_March_
    Dollase.*``) and whose flat ``_pd_proc_ls_pref_orient_corr`` it deprecates
    (issue #756 § 3).  And the Rwp with the background removed, which no item
    holds.
    """
    st = result.statistics
    out = []
    if any(p.stderr is not None for p in result.parameters):
        esd = ("Standard uncertainties are the square roots of the diagonal of "
               "chi^2_red (J^T J)^-1, J the Jacobian of the weighted residual at "
               "convergence")
        # the factor the written su carry, read off the rows: it can differ
        # from ``Statistics.esd_inflation`` (0.07-4 %, WP-2002), and a reader
        # dividing by the quoted factor must land on the uncorrected su
        # (one solve's rows share one factor to an ulp, so compare unrounded:
        # rounding first split a factor on a 3-digit boundary into a range)
        carried = [p.stderr / p.stderr_uncorrected for p in result.parameters
                   if p.stderr is not None and p.stderr_uncorrected]
        if carried:
            lo, hi = min(carried), max(carried)
            factor = (f"{lo:.3g}" if hi - lo <= 1e-9 * hi
                      or f"{lo:.3g}" == f"{hi:.3g}" else f"{lo:.3g} to {hi:.3g}")
        else:
            factor = (None if st.esd_inflation is None
                      else f"{st.esd_inflation:.3g}")
        if factor is not None:
            esd += (", multiplied by the Berar-Lelann serial-correlation factor "
                    f"{factor} (Berar & Lelann 1991, J. Appl. Cryst. 24, 1, eqs "
                    "10-12). Divided by it, they are the uncorrected su, as "
                    "GSAS-II prints them and FullProf prints them beside its "
                    "SCOR; the TOPAS Technical Reference describes no such "
                    "factor")
        out.append(esd + ".")
    for phase in structure.phases:
        po = phase.preferred_orientation
        if po is not None and (po.r.vary or po.r.value != 1.0):
            hkl = " ".join(str(i) for i in po.axis)
            out.append(f"Preferred orientation of {phase.name}: March-Dollase "
                       f"(Dollase 1986), axis the normal to ({hkl}), r="
                       f"{_value(po.r, '_pd_proc_ls_special_details')}.")
        tex = phase.texture
        terms = [f"{name}={_value(c, '_pd_proc_ls_special_details')}"
                 for name, c in (tex.coefficients.items() if tex else ())
                 if c.vary or c.value != 0.0]
        if terms:
            out.append(f"Preferred orientation of {phase.name}: spherical "
                       f"harmonics (Von Dreele 1997) to order {tex.order}, "
                       f"cylindrical sample symmetry, {', '.join(terms)}.")
    if st.rwp_background_subtracted is not None:
        out.append("Rwp with the background subtracted: "
                   f"{st.rwp_background_subtracted:.4f}.")
    return out


def _write_refinement_metadata(block, result: RefinementResult,
                               instrument: Instrument,
                               structure: Structure) -> None:
    """The refinement's scalars and the experiment's, on the pattern block.

    R factors per Toby (2006), the pdCIF profile tags so a powder reader finds
    them.  Every value is formatted before the first is set, so a refused value
    leaves the block as it was.
    """
    from .._about import DIST_NAME
    from ..refine import _VERSION

    st = result.statistics
    pairs = [(tag, number(tag, value)) for tag, value in (
        ("_pd_proc_ls_prof_wR_factor", st.rwp),
        ("_pd_proc_ls_prof_R_factor", st.rp),
        ("_pd_proc_ls_prof_wR_expected", st.rexp),
        ("_refine_ls_goodness_of_fit_all", st.gof))]
    pairs += [
        ("_refine_ls_number_parameters", str(st.n_free_parameters)),
        ("_refine_ls_number_restraints",
         str(result.restraints.n_restraints
             if result.restraints is not None and result.restraints.n_restraints
             else 0)),
    ]
    if st.max_shift_over_esd is not None:
        pairs.append(("_refine_ls_shift/su_max",
                      number("_refine_ls_shift/su_max", st.max_shift_over_esd)))
    pairs += [
        ("_computing_structure_refinement",
         text("_computing_structure_refinement", f"{DIST_NAME} {_VERSION}")),
        ("_pd_calc_method", text("_pd_calc_method", _CALC_METHOD[result.mode])),
        ("_pd_instr_geometry",
         text("_pd_instr_geometry", _INSTR_GEOMETRY[instrument.geometry.kind])),
        ("_diffrn_radiation_probe", "neutron" if instrument.source.kind == "neutron_cw"
         else "x-ray"),
    ]
    absorption = result.absorption
    if absorption is not None and absorption.skipped is None:
        kind, source = _ABSORPTION[absorption.method]
        pairs += [("_exptl_absorpt_correction_type", kind),
                  ("_exptl_absorpt_process_details", text(
                      "_exptl_absorpt_process_details",
                      f"{source}, mu*length = {absorption.mu_r:.4g} "
                      f"({absorption.mu_r_source})"))]
    else:
        pairs.append(("_exptl_absorpt_correction_type", "none"))
    details = _special_details(result, structure)
    if details:
        pairs.append(("_pd_proc_ls_special_details",
                      text("_pd_proc_ls_special_details", _wrapped(details))))
    pairs += [
        ("_pd_proc_ls_profile_function",
         text("_pd_proc_ls_profile_function",
              _profile_description(instrument, structure))),
        ("_pd_proc_ls_background_function",
         text("_pd_proc_ls_background_function",
              _wrapped([_background_description(instrument)]))),
    ]
    lines = _wavelengths(instrument)
    for tag, value in pairs:
        block.set_pair(tag, value)
    if len(lines) == 1:
        block.set_pair("_diffrn_radiation_wavelength", lines[0][0])
    else:
        loop = block.init_loop("_diffrn_radiation_wavelength", ["", "_id", "_wt"])
        for i, (lam, wt) in enumerate(lines, start=1):
            loop.add_row([lam, str(i), wt])


def _write_extinction(block, phase) -> None:
    """``_refine_ls_extinction_*`` on a phase's block, when its fit used one.

    The coefficient is :attr:`~rietx.schemas.structure.Phase.extinction`, the
    squared mosaic-block size in µm² of Sabine's (1988) primary-extinction
    model (``model/extinction.py``), and the method text says so, since the
    dictionary leaves a coefficient's meaning to its method.  Nothing is
    written for a phase that neither refined it nor set it off zero.
    """
    ext = phase.extinction
    if not ext.vary and ext.value == 0.0:
        return
    pairs = [("_refine_ls_extinction_method", text(
                 "_refine_ls_extinction_method",
                 "Sabine (1988) primary extinction; coefficient D^2 in um^2")),
             ("_refine_ls_extinction_coef",
              _value(ext, "_refine_ls_extinction_coef"))]
    for tag, value in pairs:
        block.set_pair(tag, value)


def _write_phase_agreement(block, row: PhaseAgreement | None) -> None:
    """R_Bragg and R_F under their dictionary tags, on one phase's block.

    Tag names checked against the COMCIFS core dictionary rather than
    remembered.  ``_refine_ls_R_I_factor`` is the one whose own definition
    names it — "most often calculated in Rietveld refinements of powder data,
    where it is referred to as R~B~ or R~Bragg~"; ``_refine_ls_R_factor_all``
    is "the conventional R factor", sum|F(meas) − F(calc)| / sum|F(meas)|,
    which is McCusker eq (13) exactly.  ``_all`` rather than ``_gt`` because
    every partitionable reflection is summed: there is no intensity threshold
    (no ``_reflns_threshold_expression`` to point at).  For the same reason
    ``_refine_ls_number_reflns`` — "number of unique reflections used in the
    least-squares refinement" — is the count that entered the sums: unique
    (one per hkl orbit; GSAS's ``NFOBS`` counts (line, reflection) pairs
    instead, measured 654 against our 329 orbits on the same FAP pattern) and
    short of the phase's list only by reflections off the Ewald sphere, which
    the refinement did not use either.

    Nothing is written outside Rietveld mode, where the row is absent for
    cause — an omitted tag says "not measured", a zero would be a claim.
    """
    if row is None:
        return
    if row.r_bragg is not None:
        block.set_pair("_refine_ls_R_I_factor",
                       number("_refine_ls_R_I_factor", row.r_bragg))
    if row.r_f is not None:
        block.set_pair("_refine_ls_R_factor_all",
                       number("_refine_ls_R_factor_all", row.r_f))
    if row.n_reflections:
        block.set_pair("_refine_ls_number_reflns", str(row.n_reflections))


def _write_geometry_loops(block, result: RefinementResult, ip: int) -> None:
    """``_geom_bond`` / ``_geom_contact`` / ``_geom_angle`` for one phase.

    Tag names are the COMCIFS core dictionary's, checked rather than
    remembered (as WP-1069 did for the R factors): the ``_geom_bond.*``,
    ``_geom_contact.*`` and ``_geom_angle.*`` categories, written in the flat
    DDL1 alias spelling the rest of this block uses.  McCusker §11 asks for
    "both bonding and nonbonding" distances, which is exactly the split
    between the first two categories; ``_geom_angle`` carries only the bonded
    ones, because an angle between two contacts is not a shape anybody reads.
    A bonded row and an angle carry ``publ_flag yes`` and a contact ``no``,
    the dictionary's default (ITC Vol. G ch. 4.1, pp. 236-238).

    :class:`~rietx.schemas.results.GeometryTable` lists every atom's whole
    environment, so a bond between two sites is in it twice, once from each
    end.  **One direction is dropped here**: the CIF convention is that a bond
    appears once, and a consumer summing rows per atom (bond valences, say)
    would double-count otherwise.  Which direction survives is the atoms'
    order in the phase, and a same-site pair keeps both rows because they are
    two different bonds rather than one bond twice.

    A ``_geom_*_site_symmetry_*`` code is an index into a **listed** operation
    order.  The structure block (:func:`rietx.io.cif.blocks.write_structure_block`)
    writes that list on every block, in
    :func:`~rietx.model.geometry.symmetry_operations`' order over the group
    :func:`~rietx.crystallography.symmetry.resolve_group` returns, which is the
    order the bond search indexed.  So this writes no second loop.  The codes
    are part of each category's key in ``cif_core.dic``, and a key cannot be
    unknown, so a row whose image needs a lattice shift the one-digit code
    cannot express is left out of the loop and counted in
    ``_geom_special_details`` (issue #756 § 6), where it was ``?`` before.

    Standard uncertainties ride in the value as ``1.8548(12)``, the notation
    :func:`~rietx.crystallography.cif.format_su` writes for every other
    refined number here — never a separate ``_su`` column that a reader may or
    may not pick up.  A row whose esd is ``None`` (nothing it depends on was
    refined, or symmetry fixes it) is written as a plain number rather than an
    invented zero, its shortest ``repr`` (:func:`rietx.io.cif.numbers.number`),
    and ``_geom_special_details`` says so with the method (McCusker et al. 1999
    § 10).
    """
    geometry = result.geometry
    if geometry is None:
        return
    distances = [d for d in geometry.distances
                 if d.phase_index == ip and d.atom_index_1 <= d.atom_index_2]
    angles = [a for a in geometry.angles if a.phase_index == ip]
    if not distances and not angles:
        return
    codable = [d for d in distances if d.symmetry_1 and d.symmetry_2]
    angles_codable = [a for a in angles
                      if a.symmetry_1 and a.symmetry_2 and a.symmetry_3]
    dropped = len(distances) - len(codable) + len(angles) - len(angles_codable)
    loops = []
    for tag, rows, flag in (("_geom_bond_", [d for d in codable if d.bonded], "yes"),
                            ("_geom_contact_", [d for d in codable if not d.bonded],
                             "no")):
        if rows:
            loops.append((tag, ["atom_site_label_1", "atom_site_label_2", "distance",
                                "site_symmetry_1", "site_symmetry_2", "publ_flag"],
                          [[text(f"{tag}atom_site_label_1", d.atom_1),
                            text(f"{tag}atom_site_label_2", d.atom_2),
                            number(f"{tag}distance", d.distance, d.stderr),
                            d.symmetry_1, d.symmetry_2, flag] for d in rows]))
    if angles_codable:
        # the angle *value* is the one tag here whose flat DDL1 alias is not
        # ``<category>_<object>``: ``_geom_angle.value`` aliases to a bare
        # ``_geom_angle``, so this loop cannot share a prefix with its columns
        loops.append(("", [
            "_geom_angle_atom_site_label_1", "_geom_angle_atom_site_label_2",
            "_geom_angle_atom_site_label_3", "_geom_angle",
            "_geom_angle_site_symmetry_1", "_geom_angle_site_symmetry_2",
            "_geom_angle_site_symmetry_3", "_geom_angle_publ_flag"],
            [[*(text(f"_geom_angle_atom_site_label_{k}", label)
                for k, label in enumerate((a.atom_1, a.atom_2, a.atom_3), start=1)),
              number("_geom_angle", a.angle, a.stderr),
              a.symmetry_1, a.symmetry_2, a.symmetry_3, "yes"] for a in angles_codable]))
    # each sentence only where a written row is what it describes: stating
    # a method no row used is a claim (_special_details' rule)
    sus = [r.stderr for r in codable] + [a.stderr for a in angles_codable]
    details = []
    if any(su is not None for su in sus):
        details.append(
            "Standard uncertainties of distances and angles are propagated "
            "through the full covariance of the refined parameters, cell "
            "included (McCusker et al. 1999, J. Appl. Cryst. 32, 36, section 10)"
            + (", with the Berar-Lelann factor" if result.statistics.esd_inflation
               is not None else "") + ".")
    if any(su is None for su in sus):
        details.append("A value written without su depends on nothing refined, "
                       "or is fixed by symmetry.")
    if dropped:
        details.append(f"{dropped} row{'s' if dropped > 1 else ''} whose image "
                       "needs a lattice translation beyond the one-digit symmetry "
                       f"code {'are' if dropped > 1 else 'is'} left out.")
    special = text("_geom_special_details", _wrapped(details)) if details else None
    for tag, columns, rows in loops:
        loop = block.init_loop(tag, columns)
        for row in rows:
            loop.add_row(row)
    if special is not None:
        block.set_pair("_geom_special_details", special)


#: ``_atom_type_scat_dispersion_source`` for the bundled table and for a
#: caller's measured pair (``Dispersion.overrides``).  Author and year, for
#: :data:`~rietx.io.cif.blocks.SCAT_SOURCE_MAX`'s reason.
_DISPERSION_SOURCE = "Cromer & Liberman (1981)"
_DISPERSION_GIVEN = "given (Dispersion.overrides)"


def _dispersion(instrument: Instrument, phase) -> dict[str, tuple[float, float, str]] | None:
    """{species: (f′, f″, source)} at the source's wavelength, as the fit used them.

    :func:`~rietx.crystallography.dispersion.resolve` is the forward model's own
    call, so the file states the numbers the fit computed with.  ``None`` where
    the fit applied no dispersion: a neutron source, or ``dispersion=None``.
    Rounded to the four decimals the table states.  Cromer & Liberman (1970,
    1981) for the table.
    """
    from ..crystallography.dispersion import normalize_element, resolve

    source = instrument.source
    if source.kind == "neutron_cw" or source.dispersion is None or not phase.atoms:
        return None
    overrides = source.dispersion.overrides or {}
    species = [a.species for a in phase.atoms]
    values = resolve(species, tuple(line.wavelength.value for line in source.lines),
                     overrides)
    # four decimals, the table's own precision: an interpolation has no su to
    # state, and its seventeen-digit repr pushed a type row past 80 columns
    return {sp: (round(f.real, 4), round(f.imag, 4),
                 _DISPERSION_GIVEN if normalize_element(sp) in overrides
                 else _DISPERSION_SOURCE)
            for sp, f in values.items()}


def _moment_esds(result: RefinementResult, ip: int,
                 phase) -> dict[str, float]:
    """A refined moment's esd, per site label, for the magCIF ``magnitude_su``.

    A moment's uncertainty lives on the **modulus** DOF and nowhere else
    (WP-1327): the three crystal-axis components are written back from the DOFs
    at the end of a stage and their ``stderr`` stays ``None``, because the
    quantity the powder measures is |m| and a direction the powder cannot
    determine is *held* rather than given a small esd.  So the number that
    belongs in ``_atom_site_moment.magnitude_su`` is the esd of
    ``phases.i.atoms.j.moment.dof0``, read from
    :attr:`~rietx.schemas.results.RefinementResult.parameters` — the one writer
    (WP-1076), never recomputed here.

    A site whose moment did not refine is simply absent, and the writer puts a
    CIF ``.`` there rather than a zero.
    """
    esds: dict[str, float] = {}
    if not getattr(phase, "magnetic_symmetry", None):
        return esds
    by_path = {p.path: p for p in result.parameters}
    for j, atom in enumerate(phase.atoms):
        if atom.moment is None:
            continue
        row = by_path.get(f"phases.{ip}.atoms.{j}.moment.dof0")
        if row is not None and row.stderr is not None:
            esds[atom.label] = float(row.stderr)
    return esds


def refinement_cif_doc(result: RefinementResult, structure: Structure,
                       instrument: Instrument, *,
                       pattern: PatternData | None = None,
                       reflections: list[ReflectionRow] | None = None
                       ) -> gemmi.cif.Document:
    """Build the refinement CIF as a gemmi document (see :func:`write_refinement_cif`)."""
    require_two_theta(pattern, "refinement_cif_doc()", instrument=instrument)
    doc = gemmi.cif.Document()
    agreement = {row.name: row for row in result.phase_agreement}
    probe = "neutron" if instrument.source.kind == "neutron_cw" else "xray"
    taken: set[str] = set()
    volume_su = {row.phase_index: row.stderr for row in result.cell_volumes or []}
    for ip, phase in enumerate(structure.phases):
        block = doc.add_new_block(block_name(phase.name, ip, taken))
        # the structure block, its operation loop included: the geometry
        # loops' symmetry codes below index it
        # outside rietveld the atoms are a scaffold, so the block states no
        # composition read off them
        write_structure_block(block, phase, kind="refinement", probe=probe,
                              moment_magnitude_esds=_moment_esds(result, ip, phase),
                              composition=result.mode == "rietveld",
                              cell_volume_su=volume_su.get(ip),
                              dispersion=_dispersion(instrument, phase))
        # Structure-sensitive R factors, on the phase's *own* block: both tags
        # are core-dictionary `_refine_ls` items, whose scope is the structure
        # in the block, not the pattern.  So a multi-phase export gives each
        # phase its own pair, which is how they are read.
        _write_phase_agreement(block, agreement.get(phase.name))
        _write_extinction(block, phase)
        # Bonding geometry, on the phase's own block for the same reason the R
        # factors are: the labels a _geom_ loop names are that block's
        # _atom_site labels, and a code is resolved against that block's symop
        # loop.  Nothing is written when the fit produced no table.
        _write_geometry_loops(block, result, ip)
        if ip == 0:
            # refinement scalars + the pattern loop live on the first block, so
            # a single-phase export is one self-contained block that both
            # read_pdcif (pattern) and structure_from_cif (structure) re-read
            _write_refinement_metadata(block, result, instrument, structure)
            write_pattern_block(block, result,
                                instrument.source.primary_wavelength, pattern)
            if reflections:
                write_reflection_loop(block, reflections, structure)
    return doc


def write_refinement_cif(result: RefinementResult, structure: Structure,
                         instrument: Instrument, path: str | Path, *,
                         pattern: PatternData | None = None) -> None:
    """Write a refinement CIF: structure, fit and pattern.

    The structure carries its esds.  The fit is its R factors, wavelength,
    and profile and background models.

    ``structure`` must carry the refined values and their ``stderr`` (a fit
    leaves them on ``Refinement.fitted_structure``).  The pattern loop uses the
    pdCIF tags :func:`rietx.read_pdcif` reads and the structure block the tags
    :func:`rietx.Structure.from_cif` reads, so a **single-phase** file
    round-trips through the package's own readers — the claim is narrowed to
    single-phase on purpose (WP-1003, ratifying 0309): a multi-phase export
    writes one block per phase and each re-reads as a structure, but the
    pattern loop and refinement scalars live on the first block only, and
    nothing reassembles N blocks into one refinement.

    ``pattern`` is the pattern the fit was given.  With it the profile loop
    carries every measured point, a weight of 0 marking each the fit did not
    use; without it, only the fitted points (:mod:`rietx.io.cif.powder`).
    :meth:`~rietx.Refinement.write_cif` also writes the ``_refln`` loop, from
    the reflection table only a fit's compiled model can build
    (:func:`refinement_cif_doc`'s ``reflections``).
    """
    require_two_theta(pattern, "write_refinement_cif()", instrument=instrument)
    write_document(refinement_cif_doc(result, structure, instrument,
                                      pattern=pattern), path)
