"""WP-2037 — the purpose table: which parameter paths each purpose's result numbers depend on.

A purpose is what a caller declares a fit is *for*, the name
``Refinement.summary(deliverable=…)`` takes.  Each row declares, as
``fnmatch`` globs over the parameter dot-paths (:data:`rietx.help.PARAMETER_HELP`
holds the families), the paths its result numbers depend on, and cites the
physics that couples the number to the path.

A diagnostic's level under a purpose is **derived** from this table and its
code's audit row (``rietx._audit.Row.response``), never authored per code per
purpose: the code's response where any of its ``where`` paths matches the
purpose's globs, ``info`` elsewhere; a code that carries no ``where`` declares
the purposes it bears on in its row's ``scope``.  That is clause 2 of
``docs/milestones/generality.md`` § The rule, "Attention is a cost".  So a new
purpose is one row here, never a level written onto each code.

:data:`RESULT_NUMBERS` and :data:`PLAN_OUTCOMES` are the words a ``warning``
row's sentence is checked for (``tests/test_audit_table.py``), a lexical
tripwire for the clause that a warning is owed before quoting a result number
or where the plan did not reach what it asked.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Purpose:
    """One purpose: the path globs its result numbers depend on, and why."""

    depends: tuple[str, ...]
    why: str


PURPOSES: dict[str, Purpose] = {
    "phase_id": Purpose(
        depends=("phases.*.scale", "phases.*.cell.*", "instrument.zero_shift",
                 "instrument.geometry.sample_displacement",
                 "instrument.geometry.sample_transparency",
                 "instrument.geometry.capillary_offset_*"),
        why=("A phase is identified by where its lines fall, set by its cell and by the "
             "zero and specimen-position corrections that shift every line, and by "
             "whether its scale is significant: a scale under 3 sigma of its "
             "counting-noise esd reads as absent (refine._answer_significance, WP-1523)."),
    ),
    "qpa": Purpose(
        depends=("phases.*.scale", "phases.*.cell.*", "phases.*.atoms.*.x",
                 "phases.*.atoms.*.y", "phases.*.atoms.*.z", "phases.*.atoms.*.dof.*",
                 "phases.*.atoms.*.occ", "phases.*.atoms.*.biso", "phases.*.atoms.*.u*",
                 "phases.*.atoms.*.adp.*",
                 "phases.*.extinction", "phases.*.preferred_orientation.*",
                 "phases.*.texture.*", "instrument.background.*", "instrument.polarization",
                 "instrument.geometry.surface_roughness.*"),
        why=("A weight fraction is W = S·ZMV over the phases (Hill & Howard 1987, J. Appl. "
             "Cryst. 20, 467), so it moves with the scale and with the cell volume V; "
             "the coordinates and occupancies set |F|² and the cell's content, "
             "displacement parameters and every angle-dependent intensity "
             "factor (polarisation, roughness, extinction) trade against the scale, "
             "texture redistributes the intensity the scale is read from, and a flexible "
             "background absorbs it (WP-1055)."),
    ),
    "structure": Purpose(
        depends=("phases.*.atoms.*.x", "phases.*.atoms.*.y", "phases.*.atoms.*.z",
                 "phases.*.atoms.*.dof.*", "phases.*.atoms.*.occ",
                 "phases.*.atoms.*.biso", "phases.*.atoms.*.u*",
                 "phases.*.atoms.*.adp.*", "phases.*.rigid_bodies.*", "phases.*.scale",
                 "phases.*.cell.*",
                 "phases.*.extinction", "phases.*.preferred_orientation.*",
                 "phases.*.texture.*", "instrument.background.*", "instrument.polarization",
                 "instrument.geometry.surface_roughness.*"),
        why=("Coordinates, occupancies and displacement parameters are read off the "
             "integrated intensities through |F|² (Rietveld 1969, J. Appl. Cryst. 2, 65), "
             "which the phase scale, extinction, texture, the angle-dependent intensity "
             "factors and the background each also move; a flexible background biases "
             "the ADPs up (WP-1055); the cell places every reflection and turns the "
             "coordinates into distances (model.geometry)."),
    ),
    "series": Purpose(
        depends=("*",),
        why=("A series reports the trajectory of every parameter its chain frees, so no "
             "path lies outside what its result numbers are (sequential.SeriesResult)."),
    ),
    "cell": Purpose(
        depends=("phases.*.cell.*", "instrument.zero_shift",
                 "instrument.geometry.sample_displacement",
                 "instrument.geometry.sample_transparency",
                 "instrument.geometry.capillary_offset_*", "instrument.geometry.axial_*",
                 "instrument.source.lines.*.wavelength", "instrument.source.difc",
                 "instrument.source.difa", "instrument.source.difb",
                 "instrument.source.tzero"),
        why=("A d-spacing is read from a peak position through Bragg's law and the "
             "wavelength, or the TOF conversion, and the zero and specimen-position "
             "corrections shift 2θ so they exchange with the cell (McCusker et al. 1999, "
             "J. Appl. Cryst. 32, 36, §5; report.identifiability measures the exchange); "
             "axial divergence moves a low-angle peak's maximum (Finger, Cox & Jephcoat "
             "1994, J. Appl. Cryst. 27, 892)."),
    ),
    "microstructure": Purpose(
        depends=("instrument.profile.*", "instrument.source.profile_tof.*",
                 "instrument.geometry.axial_*", "phases.*.lor_*", "phases.*.gauss_*",
                 "phases.*.microstrain.*"),
        why=("Sample broadening is what remains of the width after the instrument's "
             "(Caglioti, Paoletti & Ricci 1958, Nucl. Instrum. 3, 223): Gaussian "
             "variances add and Lorentzian FWHMs add (WP-1131), so a size or strain "
             "moves with every instrument width term; the anisotropic strain is Stephens "
             "1999, J. Appl. Cryst. 32, 281."),
    ),
    "calibration": Purpose(
        depends=("instrument.zero_shift", "instrument.polarization", "instrument.geometry.*",
                 "instrument.profile.*", "instrument.source.*", "phases.*.lor_*",
                 "phases.*.gauss_*"),
        why=("An instrument calibration's result numbers are the instrument parameters "
             "themselves: the zero, the wavelength or TOF constants, the specimen "
             "position and the profile widths (Caglioti, Paoletti & Ricci 1958, Nucl. "
             "Instrum. 3, 223), read with the standard's certified cell held fixed; the "
             "standard's own size and strain add to those widths (WP-1131), so they trade "
             "against them."),
    ),
    "magnetic": Purpose(
        depends=("phases.*.atoms.*.moment.*", "phases.*.magnetic_lor_*", "phases.*.scale",
                 "phases.*.atoms.*.x", "phases.*.atoms.*.y", "phases.*.atoms.*.z",
                 "phases.*.atoms.*.dof.*", "phases.*.atoms.*.occ",
                 "phases.*.atoms.*.biso", "phases.*.atoms.*.u*",
                 "phases.*.atoms.*.adp.*",
                 "phases.*.extinction", "phases.*.preferred_orientation.*",
                 "phases.*.texture.*", "instrument.background.*", "instrument.polarization",
                 "instrument.geometry.surface_roughness.*"),
        why=("A moment is measured against the nuclear intensity through the phase scale "
             "the two share (Halpern & Johnson 1939, Phys. Rev. 55, 898), so every term "
             "that sets the nuclear intensity the scale is read from moves it, as under "
             "qpa: the coordinates and occupancies through |F|², and the displacement "
             "parameters, extinction, texture, the angle-dependent intensity factors and "
             "the background, which trade against the scale; the magnetic coherence length "
             "is a width term of its own (WP-1343)."),
    ),
}

#: Stems a ``warning`` row's ``responds`` sentence names one of: a result
#: number (lower case, matched as a substring of the lower-cased sentence).
RESULT_NUMBERS: tuple[str, ...] = (
    "cell", "fraction", "coordinate", "adp", "biso", "occupanc", "size", "strain",
    "width", "intensit", "moment", "scale", "density",
)

#: Stems for the other half of a warning: the plan did not reach what it asked.
PLAN_OUTCOMES: tuple[str, ...] = ("plan", "stage", "converge", "reach")
