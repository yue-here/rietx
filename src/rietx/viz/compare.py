"""Side-by-side comparison of refinement *settings* on the bundled standards.

The question this answers is the one that comes up every time a new correction
lands: **does it actually make the fit better, and where?**  That is hard to
read off two Rietveld panels drawn next to each other — the eye is poor at
differencing two difference curves — and it is not answerable from Rwp alone,
because some corrections provably cannot move Rwp at all (capillary absorption
is an exact reparameterisation of the scale and Biso; see
:mod:`rietx.model.absorption`) while others improve it by absorbing physics
that belongs elsewhere.

So this module runs the same standard under several variants and renders three
views, in increasing order of how much they actually settle:

1. **obs + one calculated curve per variant** — the familiar panel, for
   orientation only.
2. **weighted residual (y_obs − y_calc)/σ per variant, overlaid** — same
   vertical scale for every variant, so "smaller is better" is literal.
3. **cumulative Δχ² against the reference variant** — Σ_{2θ' ≤ 2θ}
   (δ²_variant − δ²_reference), plotted against 2θ.  A *falling* curve is a
   variant winning; a rising one is losing; a flat one is a variant doing
   nothing.  The slope localises the improvement to the angles that produced
   it, which is the difference between "this correction helped" and "this
   correction helped *at the low-angle reflections, as its physics says it
   should*".  A correction that improves Rwp by rising sharply somewhere and
   falling elsewhere is absorbing something, not modelling it.

Alongside them go the statistics **and the structured diagnostics**, because a
variant can win panel 3 and still be inadmissible (`STEPHENS_STRAIN_NOT_POSITIVE`,
`ROUGHNESS_UNCONSTRAINED`, `BACKGROUND_ABSORPTION` …).  See the agent skill
§7-8 (`docs/skill/rietx/references/diagnostics.md` and `surprises.md`).

The standards mirror the acceptance suites' protocols exactly — same phases,
same instrument, same staged plan — because a comparison run under a different
protocol is not comparable to the recorded acceptance numbers.
``tests/test_compare_ui.py`` asserts that equality field by field, so the two
cannot drift.

Datasets live in ``tests/data`` and are **not** shipped in the wheel; every
standard self-skips when its files are absent, exactly as the acceptance tests
do.  Pass ``data_dir`` to point elsewhere.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..schemas.instrument import (
    CAPILLARY_OFFSETS,
    HUMP_FWHM_MIN,
    BackgroundChebyshev,
    BackgroundPSpline,
    Dispersion,
    EmissionLine,
    HumpComponent,
    Instrument,
    RoughnessPitschke,
    RoughnessSuortti,
    Source,
)
from ..schemas.structure import (
    Parameter,
    Phase,
    PreferredOrientation,
    StephensStrain,
    Structure,
)
from ..strategy.staged import RefinementPlan, Stage


def default_data_dir() -> Path:
    """``tests/data`` of a source checkout, or the cwd as a last resort."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "tests" / "data"
        if candidate.is_dir():
            return candidate
    return Path.cwd()


# ----------------------------------------------------------------------
# standards
# ----------------------------------------------------------------------
@dataclass
class StandardInputs:
    """Everything one comparison run needs, before any variant is applied."""

    data: object                       # PatternData
    structure: Structure
    instrument: Instrument
    plan: RefinementPlan
    two_theta_limits: tuple[float, float] | None = None


@dataclass(frozen=True)
class Standard:
    key: str
    title: str
    #: what the dataset is and what it anchors — shown in the UI, so it is the
    #: place a user learns that SRM 660c is an *absolute* accuracy anchor while
    #: the GSAS-II fluorapatite is only a cross-code consistency check
    description: str
    files: tuple[str, ...]
    #: which of ``files`` is the *measurement*, and the reader call that claims
    #: it.  Declared rather than inferred, for the reason ``DataRef`` records a
    #: reader call at all: ``files[0]`` is only a convention, and a pdCIF
    #: carrying a ``_meas`` and a ``_calc`` block is a different pattern
    #: depending on ``block``.  A consumer building a *project* from a standard
    #: (``rietx.examples``) has to state the call rather than inherit whichever
    #: block a default happens to pick.
    pattern: str
    build: Callable[[Path], StandardInputs]
    geometry: str                      # "bragg_brentano" | "debye_scherrer"
    reader_options: tuple[tuple[str, str], ...] = ()

    def available(self, data_dir: Path) -> bool:
        return all((data_dir / f).exists() for f in self.files)


def _p(v: float, **kw) -> Parameter:
    return Parameter(value=v, **kw)


def _qarr_phase(name, sg, cell, atoms, **kw) -> Phase:
    a, b, c, al, be, ga = cell
    from ..schemas.structure import Atom, Cell

    return Phase(
        name=name, space_group=sg,
        cell=Cell(a=_p(a), b=_p(b), c=_p(c),
                  alpha=_p(al), beta=_p(be), gamma=_p(ga)),
        atoms=[Atom(label=lab, species=sp, x=_p(x), y=_p(y), z=_p(z),
                    biso=_p(biso, min=0.0, max=25.0))
               for lab, sp, x, y, z, biso in atoms],
        scale=_p(1e-3, min=0.0, transform="softplus"),
        lor_size=_p(0.02, min=0.0, transform="softplus"),
        lor_strain=_p(0.0, min=0.0, transform="softplus"),
        **kw)


def qarr_instrument() -> Instrument:
    """CPD round-robin instrument: Philips Bragg-Brentano, R = 173 mm, Cu Kα
    doublet, diffracted-beam graphite monochromator (2θ_m = 26.6°)."""
    ins = Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=173.0,
                                    monochromator_two_theta=26.6)
    # dispersion DECLINED, not inherited: these standards mirror the
    # acceptance suites' protocols (tests/test_compare_ui.py pins that
    # field by field), and those pin the pre-v1.0 dispersion-off
    # baseline so the *comparison* is against a fixed reference.  The
    # `dispersion` variant below is what turns it on.
    ins.source.dispersion = None
    ins.background = BackgroundChebyshev.with_terms(6)
    return ins


def qpa_plan(*, texture: bool = False) -> RefinementPlan:
    """The QPA/round-robin protocol (mirrors ``tests/test_acceptance_qpa_roundrobin``)."""
    stages = [
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero_disp", ["instrument.zero_shift",
                            "instrument.geometry.sample_displacement"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                          "instrument.profile.x", "instrument.profile.y"]),
        Stage("sample_broadening",
              ["phases.*.lor_size", "phases.*.lor_strain",
               "phases.*.gauss_size", "phases.*.gauss_strain"], seed=1e-4),
        Stage("lines_axial", ["instrument.source.lines.*.weight",
                              "instrument.geometry.axial_sl"]),
        Stage("biso", ["phases.*.atoms.*.biso"]),
    ]
    if texture:
        stages.append(Stage("po", ["phases.*.preferred_orientation.r"]))
    return RefinementPlan(stages=stages)


def _seed_scales(structure: Structure, ins: Instrument, data) -> None:
    """Match the summed calculated intensity to the data (equal split).

    One authority, in :func:`rietx.model.forward.seed_phase_scales`, since
    WP-1306 gave it a second caller — the PowderLine recipe reader, which
    assembles a model from a foreign document whose scale carries a foreign
    normalisation.
    """
    from ..model.forward import seed_phase_scales

    seed_phase_scales(structure, ins, data)


def corundum_phase() -> Phase:
    """α-Al₂O₃, R-3c (hexagonal axes); Lewis, Schwarzenbach & Flack (1982)."""
    return _qarr_phase("corundum", "R -3 c", (4.7593, 4.7593, 12.9917, 90, 90, 120),
                       [("Al", "Al", 0.0, 0.0, 0.35216, 0.30),
                        ("O", "O", 0.30624, 0.0, 0.25, 0.30)])


def zincite_phase() -> Phase:
    """ZnO wurtzite, P6₃mc; Kihara & Donnay (1985)."""
    return _qarr_phase("zincite", "P 63 m c", (3.2499, 3.2499, 5.2066, 90, 90, 120),
                       [("Zn", "Zn", 1 / 3, 2 / 3, 0.0, 0.55),
                        ("O", "O", 1 / 3, 2 / 3, 0.3826, 0.55)])


def fluorite_phase() -> Phase:
    """CaF₂, Fm-3m; both sites fully fixed by symmetry."""
    return _qarr_phase("fluorite", "F m -3 m", (5.4631, 5.4631, 5.4631, 90, 90, 90),
                       [("Ca", "Ca", 0.0, 0.0, 0.0, 0.55),
                        ("F", "F", 0.25, 0.25, 0.25, 0.75)])


def brucite_phase(*, textured: bool = False) -> Phase:
    """Mg(OH)₂, P-3m1; Zigan & Rothbauer (1967).  H is X-ray-invisible but
    carries 3.5 % of the molar mass, so it stays in the model with Biso held."""
    kw = {}
    if textured:
        kw["preferred_orientation"] = PreferredOrientation(axis=(0, 0, 1))
    return _qarr_phase("brucite", "P -3 m 1", (3.142, 3.142, 4.766, 90, 90, 120),
                       [("Mg", "Mg", 0.0, 0.0, 0.0, 0.70),
                        ("O", "O", 1 / 3, 2 / 3, 0.2216, 0.90),
                        ("H", "H", 1 / 3, 2 / 3, 0.4303, 2.5)], **kw)


def _build_qarr(phase_fn, filename, *, textured: bool = False):
    def build(data_dir: Path) -> StandardInputs:
        from ..io.readers import read_pattern

        data = read_pattern(data_dir / filename)
        structure = Structure(phases=[phase_fn()])
        ins = qarr_instrument()
        _seed_scales(structure, ins, data)
        return StandardInputs(data=data, structure=structure, instrument=ins,
                              plan=qpa_plan(texture=textured))
    return build


def _build_srm660c(data_dir: Path) -> StandardInputs:
    """NIST SRM 660c LaB6 — the package's **absolute** cell anchor.

    NIST protocol: the divergent-beam diffractometer is angle-calibrated, so
    the zero error is *held at 0* and specimen displacement refines instead;
    LaB6 is opaque to Cu Kα so transparency is held at 0 too.
    """
    from ..io.readers import read_pdcif
    from ..schemas.structure import Atom, Cell

    data = read_pdcif(data_dir / "nist_srm660c_100a.cif", block="_meas")
    structure = Structure(phases=[Phase(
        name="LaB6", space_group="P m -3 m", cell=Cell.cubic(4.1568),
        atoms=[
            Atom(label="La", species="La", x=_p(0.0), y=_p(0.0), z=_p(0.0),
                 biso=_p(0.355, min=0.0, max=25.0)),
            Atom(label="B", species="B", x=_p(0.198), y=_p(0.5), z=_p(0.5),
                 biso=_p(0.276, min=0.0, max=25.0)),
        ],
        scale=_p(1e-4, min=0.0, transform="softplus"),
    )])
    ins = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.source.dispersion = None   # declined, not inherited (see _qarr_instrument)
    ins.profile.w.value = 2e-3
    ins.profile.x.value = 5e-3
    ins.geometry.axial_sl.value = 0.025
    ins.geometry.axial_hl.value = 0.025
    ins.background = BackgroundChebyshev.with_terms(6)
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("disp", ["instrument.geometry.sample_displacement"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                          "instrument.profile.x", "instrument.profile.y"]),
        Stage("lines_axial", ["instrument.source.lines.*.weight",
                              "instrument.geometry.axial_sl",
                              "instrument.geometry.axial_hl"]),
        Stage("biso", ["phases.*.atoms.*.biso"]),
    ])
    return StandardInputs(data=data, structure=structure, instrument=ins, plan=plan)


def _build_fap(data_dir: Path) -> StandardInputs:
    """GSAS-II's "LabData" fluorapatite — the **cross-code** row.

    Every other standard here is measured against a certificate or a weighed
    composition.  This one is measured against another Rietveld code's own
    converged answer for the same file, so what it shows is a *convention*
    difference rather than an error: the two cells sit +116 and +113 ppm apart,
    the same relative offset on both axes, which is a d-scale disagreement and
    not a structural one.  ±300 ppm is the honest band.

    Mirrors ``tests/test_acceptance_fap`` field for field (the anti-drift test
    in ``tests/test_compare_ui`` asserts it).  Since WP-1118 both read the
    protocol from ``FAP.EXP`` through :func:`~rietx.io.projects.gsas.read_gsas_exp`
    rather than restating it, so there is **one** authority for these numbers
    and it is the file; this builder used to be the second transcription of
    them.  Three parts of the protocol are GSAS's rather than ours and matter
    more than they look:

    * the tutorial's own 1.5405/1.5443 Å doublet, not the NIST/Hölzer preset —
      a 60 ppm wavelength difference lands straight on the cell being compared;
    * zero held at 0 with the specimen **displacement** refining instead, and
      the Caglioti terms held at the ``INST_XRY.PRM`` starting values, because
      those are GSAS's own refine flags;
    * dispersion **declined**, because GSAS's converged run did not apply
      f′/f″ either.  Adopting another code's protocol means adopting what it
      did not model as much as what it did.
    """
    from ..io.projects.gsas import read_gsas_exp, to_structure
    from ..io.readers import read_pattern
    from ..schemas.pattern import PatternData

    exp = read_gsas_exp(data_dir / "FAP.EXP")
    hist = exp.histogram()
    terms = exp.profile().by_name()

    raw = read_pattern(data_dir / "FAP.XRA")
    # GSAS's own excluded region, as its ``EXC 2`` record states it.  Excluding
    # it reproduces GSAS's 5750 channels exactly, which is what makes the two
    # codes' agreement indices comparable at all.
    data = PatternData(two_theta=raw.two_theta, intensity=raw.intensity,
                       sigma=raw.sigma,
                       excluded_regions=list(hist.excluded_regions),
                       metadata=raw.metadata)
    structure = to_structure(exp)
    phase = structure.phases[0]
    phase.name = "fluorapatite"
    # the file's refine flags are not this standard's: the staged plan below
    # frees parameters in order, and a stage's globs *add* to the free set
    for name in ("a", "b", "c", "alpha", "beta", "gamma"):
        edge = getattr(phase.cell, name)
        edge.vary = False
        if name in ("a", "b", "c"):
            edge.min = 1.0
    for atom in phase.atoms:
        for name in ("x", "y", "z", "occ", "biso"):
            getattr(atom, name).vary = False
    phase.scale = _p(1e-3, min=0.0, transform="softplus")
    phase.lor_size = _p(terms["LX"].degrees, min=0.0, transform="softplus")
    phase.lor_strain = _p(terms["LY"].degrees, min=0.0, transform="softplus")

    lam1, lam2 = hist.wavelengths
    ins = Instrument.bragg_brentano()
    ins.source = Source(
        lines=[EmissionLine(wavelength=lam1),
               # the file's KRATIO field is blank, so this 0.5 is ours; the 0.5
               # it does state is the polarization below (WP-1118)
               EmissionLine(wavelength=lam2, weight=_p(0.5, min=0.0, max=1.0))],
        polarization=_p(hist.polarization, min=0.0, max=1.0),
        dispersion=None)
    ins.profile.u.value = terms["GU"].degrees     # held, as its N flag says
    ins.profile.v.value = terms["GV"].degrees
    ins.profile.w.value = terms["GW"].degrees
    # S/L and H/L are near-degenerate (see Geometry docstring); refine one
    ins.geometry.axial_sl.value = 0.02
    ins.geometry.axial_hl.value = 0.02
    ins.background = BackgroundChebyshev.with_terms(6)

    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("disp", ["instrument.geometry.sample_displacement"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("sample_lor", ["phases.*.lor_size", "phases.*.lor_strain"]),
        Stage("axial", ["instrument.geometry.axial_sl"]),
        Stage("biso", ["phases.*.atoms.*.biso"]),
    ])
    plan.intermediate_ftol = 1e-6
    return StandardInputs(data=data, structure=structure, instrument=ins,
                          plan=plan)


def _build_nac(data_dir: Path) -> StandardInputs:
    """APS 11-BM NAC + the CaF₂ impurity — synchrotron capillary geometry.

    The only standard here whose geometry can carry the cylindrical absorption
    correction, so it is the one to compare that variant on.

    The plan is ``mccusker_default`` **plus a Biso stage**, which is what
    ``tests/test_acceptance_nac`` runs — and freeing Biso is load-bearing for
    the absorption variant rather than incidental. Measured here at µR = 0.5,
    λ = 0.4139090 Å:

    * **Biso free** (this plan): Rwp 0.0930604 → 0.0930352, i.e. 2.5 × 10⁻⁵,
      and *every* displacement parameter moves by the same +0.0096 Å² — which
      is ΔB = c(µR)·λ²/2 = 0.11215 × 0.41391²/2 = 0.009606 to four decimals.
      That uniform shift is the correction's entire content. The residual
      2.5 × 10⁻⁵ in Rwp is not physics either: one impurity Biso sits on its
      lower bound and therefore cannot take its share of the shift.
    * **Biso held**: the two runs separate by 1.4 × 10⁻⁴ in Rwp — larger, and
      reading *that* as the correction working is exactly the mistake
      the agent skill §8.1 warns about. It is the leftover of an exact
      degeneracy that a frozen parameter turned into an inexact one.

    Unlike the acceptance test this goes straight to Rietveld rather than
    seeding from a Le Bail pass — one fit per variant instead of two, and it
    converges to the same place (Rwp 9.57 %).
    """
    from ..io.readers import read_pattern
    from ..schemas.structure import Atom, Cell

    data = read_pattern(data_dir / "11BM_NAC.fxye")
    structure = Structure.from_cif(str(data_dir / "cod_1000236.cif"))
    structure.phases.append(Phase(
        name="CaF2", space_group="F m -3 m", cell=Cell.cubic(5.4631),
        atoms=[
            Atom(label="Ca", species="Ca2+", x=_p(0.0), y=_p(0.0), z=_p(0.0),
                 biso=_p(0.6, min=0.0, max=25.0)),
            Atom(label="F", species="F1-", x=_p(0.25), y=_p(0.25), z=_p(0.25),
                 biso=_p(0.9, min=0.0, max=25.0)),
        ],
        scale=_p(1e-7, min=0.0, transform="softplus"),
    ))
    ins = Instrument.debye_scherrer(wavelength=0.4139090)
    ins.source.dispersion = None   # declined, not inherited (see _qarr_instrument)
    ins.profile.w.value = 2e-5
    ins.profile.x.value = 2e-3
    ins.background = BackgroundChebyshev.with_terms(6)
    plan = RefinementPlan.mccusker_default()
    plan.stages.append(Stage("biso", ["phases.*.atoms.*.biso"]))
    return StandardInputs(data=data, structure=structure, instrument=ins,
                          plan=plan, two_theta_limits=(2.0, 24.0))


def _build_lab6_capillary(data_dir: Path) -> StandardInputs:
    """APS 11-BM SRM 660a LaB₆ — the documented-bore capillary standard.

    Mirrors ``tests/test_acceptance_capillary`` field for field (the anti-drift
    test in ``tests/test_compare_ui`` asserts it), which is what makes the
    numbers in the UI the same numbers the acceptance asserts.

    This is the standard the capillary-absorption variant exists for.  Measured
    at µR = 0.674 over 2-60° 2θ: Rwp 0.0884883 → 0.0884884 and a moves 8e-12 Å,
    while **both** displacement parameters move by +0.0166542 Å² — exactly
    ΔB = c(µR)·λ²/2.  Compare that against ``nac``, where one impurity Biso sits
    on its bound and cannot take its share, leaving a spurious 2.5e-5 in Rwp.
    """
    from ..io.readers import read_pattern

    data = read_pattern(data_dir / "11BM_LaB6_660a.fxye")
    structure = Structure.from_cif(str(data_dir / "cod_1000055.cif"))
    structure.phases[0].scale = _p(1e-4, min=0.0, transform="softplus")
    for atom in structure.phases[0].atoms:
        atom.biso = _p(0.3, min=0.0, max=5.0)
    ins = Instrument.debye_scherrer(wavelength=0.4131280)
    ins.source.dispersion = None   # declined, not inherited (see _qarr_instrument)
    ins.profile.w.value = 2e-5
    ins.profile.x.value = 2e-3
    ins.background = BackgroundChebyshev.with_terms(8)
    plan = RefinementPlan.mccusker_default()
    plan.stages.append(Stage("biso", ["phases.*.atoms.*.biso"]))
    return StandardInputs(data=data, structure=structure, instrument=ins,
                          plan=plan, two_theta_limits=(2.0, 60.0))


STANDARDS: tuple[Standard, ...] = (
    Standard(
        key="srm660c", title="NIST SRM 660c — LaB₆ (lab CuKα)",
        description=("Certified line-profile standard on the NIST divergent-beam "
                     "diffractometer. The package's **absolute** cell anchor "
                     "(a = 4.156895(25) Å, +28 ppm). Zero held at 0, displacement "
                     "refined — the NIST protocol."),
        files=("nist_srm660c_100a.cif",), pattern="nist_srm660c_100a.cif",
        reader_options=(("block", "_meas"),), build=_build_srm660c,
        geometry="bragg_brentano"),
    Standard(
        key="corundum", title="SRM 676a corundum — α-Al₂O₃ (lab CuKα)",
        description=("IUCr CPD round-robin pure phase, also the SRM 676a cell "
                     "anchor. c/a is the certificate-grade assertion (+30 ppm); "
                     "the absolute axes carry a ≈−300 ppm lab d-scale offset."),
        files=("qarr/corundum.prn",), pattern="qarr/corundum.prn",
        build=_build_qarr(corundum_phase, "qarr/corundum.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="zincite", title="Zincite — ZnO (lab CuKα)",
        description=("Round-robin pure phase. The sharpest demonstration of "
                     "neglected anomalous scattering: applying f′/f″ barely moves "
                     "Rwp but takes B(O) from 0.02 to 0.43 Å² — a displacement "
                     "parameter that had been spending itself on Zn's missing f′."),
        files=("qarr/zincite.prn",), pattern="qarr/zincite.prn",
        build=_build_qarr(zincite_phase, "qarr/zincite.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="fluorite", title="Fluorite — CaF₂ (lab CuKα)",
        description=("Round-robin pure phase; both sites fully fixed by symmetry, "
                     "so displacement parameters are the only structural freedom "
                     "and intensity-correction degeneracies show up cleanly."),
        files=("qarr/fluorite.prn",), pattern="qarr/fluorite.prn",
        build=_build_qarr(fluorite_phase, "qarr/fluorite.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="brucite", title="Brucite — Mg(OH)₂ (lab CuKα)",
        description=("Round-robin pure phase and its designated preferred-orientation "
                     "specimen: strongly platy on (001). The anisotropic-strain test "
                     "case — where the improvement is real, passes ΔBIC, and is still "
                     "rejected by the positivity cone."),
        files=("qarr/brucite.prn",), pattern="qarr/brucite.prn",
        build=_build_qarr(brucite_phase, "qarr/brucite.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="fap", title="GSAS-II LabData — fluorapatite (lab CuKα doublet)",
        description=("The **cross-code** row: measured against GSAS's own "
                     "converged refinement of the same file rather than a "
                     "certificate. Seven sites with real coordinate freedom, "
                     "counts only (Poisson σ), and GSAS's 130° exclusion, so "
                     "the two codes' agreement indices cover the same 5750 "
                     "channels. The cells sit +116 and +113 ppm apart — the "
                     "same relative offset on both axes, which is a d-scale "
                     "convention difference, not a structural one."),
        files=("FAP.XRA", "FAP.EXP"), pattern="FAP.XRA", build=_build_fap,
        geometry="bragg_brentano"),
    Standard(
        key="nac", title="APS 11-BM — NAC + CaF₂ (synchrotron capillary)",
        description=("Na₂Ca₃Al₂F₁₄ with a fluorite impurity, λ = 0.4139090 Å, fitted "
                     "2-24° 2θ. The only debye_scherrer standard here, so the only "
                     "one where the capillary absorption variant applies."),
        files=("11BM_NAC.fxye", "cod_1000236.cif"), pattern="11BM_NAC.fxye",
        build=_build_nac,
        geometry="debye_scherrer"),
    Standard(
        key="lab6_capillary", title="APS 11-BM — NIST SRM 660a LaB₆ (capillary)",
        description=("The only standard here whose specimen container is "
                     "documented: 11-BM's mail-in 0.81 mm Kapton tube, giving "
                     "µR ≈ 0.5-0.7 from the composition. λ = 0.4131280 Å was "
                     "calibrated at the beamline against LaB₆ itself, so the "
                     "cell is circular here and is not an anchor — the "
                     "absorption variant's Biso shift is what this one shows."),
        files=("11BM_LaB6_660a.fxye", "cod_1000055.cif"),
        pattern="11BM_LaB6_660a.fxye",
        build=_build_lab6_capillary, geometry="debye_scherrer"),
)

STANDARD_BY_KEY = {s.key: s for s in STANDARDS}


# ----------------------------------------------------------------------
# variants — the "settings" axis
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Variant:
    key: str
    title: str
    #: what to *look* for, not just what it does — a variant whose whole point
    #: is that it cannot move Rwp needs to say so where the user reads it
    description: str
    apply: Callable[[StandardInputs], None]
    #: geometry kinds this variant is meaningful for; empty = all
    geometries: tuple[str, ...] = ()

    def applies_to(self, standard: Standard) -> bool:
        return not self.geometries or standard.geometry in self.geometries


def _noop(_inputs: StandardInputs) -> None:
    pass


def _with_dispersion(inputs: StandardInputs) -> None:
    inputs.instrument.source.dispersion = Dispersion()


def _with_voigt(inputs: StandardInputs) -> None:
    inputs.instrument.profile.shape = "voigt"


def _with_pspline(inputs: StandardInputs) -> None:
    lo, hi = inputs.two_theta_limits or (None, None)
    tt = np.asarray(inputs.data.two_theta)
    lo = float(tt.min()) if lo is None else lo
    hi = float(tt.max()) if hi is None else hi
    inputs.instrument.background = BackgroundPSpline.for_range(lo, hi,
                                                               knot_step_deg=8.0)


def _with_hump(inputs: StandardInputs) -> None:
    """Declare one broad Gaussian at the low-angle third of the range and free it.

    Placed at 1/3 of the fitted range and 6° wide because that is where a
    diffuse hump lives on a real pattern (the motivating BT-1 case is 5.8° wide
    at 14.4° over 5-152°), and because the *comparison* has to be reproducible
    across standards that share no 2θ range.  **None of these standards has a
    known hump**, which is what makes this variant informative in the honest
    direction: three free parameters over a background that is already right
    should buy essentially nothing, and the panel that says so is
    BACKGROUND_ABSORPTION plus HUMP_TOO_NARROW — not Rwp, which a
    free peak can always improve.

    The stage is appended rather than merged into ``scale_bkg`` for the reason
    ``strategy/staged._EXTRA_COMPONENT_STAGE`` gives: a free position over
    peaks that have not been placed yet hunts the wrong misfit.
    """
    lo, hi = inputs.two_theta_limits or (None, None)
    tt = np.asarray(inputs.data.two_theta)
    lo = float(tt.min()) if lo is None else lo
    hi = float(tt.max()) if hi is None else hi
    y = np.asarray(inputs.data.intensity, dtype=float)
    inputs.instrument.extra_components = [HumpComponent(
        label="comparison hump",
        position=Parameter(value=lo + (hi - lo) / 3.0, unit="deg"),
        height=Parameter(value=0.05 * float(np.median(y)), min=0.0,
                         unit="counts", transform="softplus"),
        fwhm=Parameter(value=6.0, min=HUMP_FWHM_MIN, unit="deg",
                       transform="softplus"))]
    inputs.plan.stages.append(
        Stage("extra_components", ["instrument.extra_components.*"]))


def _with_roughness_suortti(inputs: StandardInputs) -> None:
    inputs.instrument.geometry.surface_roughness = RoughnessSuortti()
    inputs.plan.stages.append(
        Stage("roughness", ["instrument.geometry.surface_roughness.*"], seed=0.3))


def _with_roughness_pitschke(inputs: StandardInputs) -> None:
    inputs.instrument.geometry.surface_roughness = RoughnessPitschke()
    inputs.plan.stages.append(
        Stage("roughness", ["instrument.geometry.surface_roughness.*"], seed=0.3))


def _with_extinction(inputs: StandardInputs) -> None:
    inputs.plan.stages.append(
        Stage("extinction", ["phases.*.extinction"], seed=1e-3))


def _with_preferred_orientation(inputs: StandardInputs) -> None:
    for phase in inputs.structure.phases:
        if phase.preferred_orientation is None:
            phase.preferred_orientation = PreferredOrientation(
                axis=_dominant_axis(phase))
    inputs.plan.stages.append(
        Stage("preferred_orientation", ["phases.*.preferred_orientation.r"]))


def _dominant_axis(phase: Phase) -> tuple[int, int, int]:
    """(001) for a hexagonal/trigonal/tetragonal cell, (100) otherwise.

    A guess, and labelled one in the UI: the March axis is a property of the
    crystallite habit, not of the cell.  It is the right guess for the layered
    and prismatic minerals here (brucite plates on (001)) and a harmless one
    elsewhere, because r ≡ 1 is the exact identity — a PO block that finds no
    texture simply stays at 1.
    """
    cell = phase.cell
    if abs(cell.gamma.value - 120.0) < 1e-6 or (
            abs(cell.a.value - cell.b.value) < 1e-9
            and abs(cell.c.value - cell.a.value) > 1e-6):
        return (0, 0, 1)
    return (1, 0, 0)


def _with_stephens(inputs: StandardInputs) -> None:
    """Attach an isotropic-seeded Stephens block and free it *in* the
    sample-broadening stage.

    Not in a stage of its own, and this is not a style choice: a microstrain
    block **locks** ``lor_strain`` (its isotropic direction is literally that
    residual column), so a later stage would leave the isotropic width
    unrefined right up to the moment several correlated patterns turn on at
    once — the worst possible starting point.  See ``strategy/staged.py``'s
    ``lab_sample_refine``, which is built the same way.
    """
    for phase in inputs.structure.phases:
        if phase.microstrain is None:
            phase.microstrain = StephensStrain.isotropic(1000.0, phase.cell)
    _extend_broadening_stage(inputs.plan, ["phases.*.microstrain.dof.*"],
                             strain_seed=1000.0)


def _extend_broadening_stage(plan: RefinementPlan, globs: list[str],
                             **kw) -> None:
    """Add ``globs`` to the plan's sample-broadening stage, or append one."""
    for stage in plan.stages:
        if stage.name in ("sample_broadening", "sample_profile"):
            stage.turn_on = list(stage.turn_on) + globs
            for name, value in kw.items():
                setattr(stage, name, value)
            return
    plan.stages.append(Stage("sample_broadening", globs, **kw))


def _with_capillary_absorption(inputs: StandardInputs) -> None:
    """µR = 0.5 for an 0.8 mm-bore capillary at typical packing.

    Fixed rather than estimated so the comparison is reproducible across
    standards, and because µR is *not* refinable by construction (it is an
    exactly singular direction alongside the scale and Biso).  Expect Rwp to be
    **identical** to the baseline and Biso to move by ΔB = c(µR)·λ²/2 — that is
    the whole content of the correction, and the reason the results table shows
    Biso next to Rwp.  (The ``lab6_capillary`` standard is the one whose real
    bore is documented — 0.81 mm — so 0.5 there is a round number near the
    composition estimate of 0.67 rather than a stand-in for a missing one.)
    """
    inputs.instrument.geometry.mu_r = 0.5


def _with_capillary_displacement(inputs: StandardInputs) -> None:
    """Free McCusker eq (4)'s two offsets beside the zero shift.

    A *displacement* variant, so unlike the absorption one it is meant to move
    Rwp: the correction adds two position degrees of freedom the baseline
    holds at zero.  What it is really for is the trio — the offsets and
    ``zero_shift`` span {sin2θ, cos2θ, 1} over the measured range, so the
    identifiability panel's correlations and the Δχ² curve together say
    whether this instrument's range *can* separate them, which is the question
    §12.3 asks and no single Rwp answers.

    R = 1000 mm where none is declared: 11-BM's diffraction circle is metres,
    and the offsets are only ever read as x/R, so an R off by a factor moves
    the fitted millimetres by that factor and nothing else.  It is a *declared
    assumption of the comparison*, which is why the panel shows the fitted
    values rather than only the agreement indices.
    """
    geom = inputs.instrument.geometry
    if not geom.goniometer_radius_mm:
        geom.goniometer_radius_mm = 1000.0
    for stage in inputs.plan.stages:
        if "instrument.zero_shift" in stage.turn_on:
            stage.turn_on = list(stage.turn_on) + [
                f"instrument.geometry.{n}" for n in CAPILLARY_OFFSETS]
            return
    inputs.plan.stages.insert(1, Stage("capillary_displacement",
                                       [f"instrument.geometry.{n}"
                                        for n in CAPILLARY_OFFSETS]))


def _with_flat_plate_absorption(inputs: StandardInputs) -> None:
    """µt = 0.5: a *finite-thickness* reflection specimen, ITC (2).

    The one flat-plate variant whose baseline is not "off but harmless": every
    Bragg-Brentano standard here is a thick back-packed mount, for which ITC
    (1a) gives an exactly angle-independent A, so the baseline is the physically
    right model and this variant deliberately mis-declares the specimen.  What
    it demonstrates is the *size* of the mistake in the other direction — a
    genuinely thin mount fitted as though it were thick — and that is large:
    ΔBiso runs to −1.5 Å² at µt = 0.2 over a Cu Kα range, an order of magnitude
    past the capillary case, and unlike the capillary it moves Rwp too.
    """
    inputs.instrument.geometry.mu_t = 0.5


VARIANTS: tuple[Variant, ...] = (
    Variant("baseline", "Baseline",
            "The standard's own acceptance protocol, unmodified. Every other "
            "variant is this plus one change, and the Δχ² panel is measured "
            "against whichever variant you mark as the reference.",
            _noop),
    Variant("dispersion", "+ anomalous f′, f″",
            "Cromer-Liberman dispersion on every species. Watch the displacement "
            "parameters and (multi-phase) the QPA fractions, not Rwp — measured "
            "on the round robin this took QPA RMS error 2.26 → 0.69 wt %.",
            _with_dispersion),
    Variant("voigt", "+ true Voigt peak shape",
            "Exact Gaussian⊗Lorentzian instead of the TCHZ pseudo-Voigt "
            "approximation, on identical U,V,W,X,Y. Differences should be "
            "concentrated in the peak flanks.",
            _with_voigt),
    Variant("pspline", "+ P-spline background",
            "Penalised spline (8° knots) instead of Chebyshev-6. If Rwp improves "
            "a lot, check BACKGROUND_ABSORPTION before believing it — a "
            "background flexible enough to imitate peaks biases ADPs up and "
            "scales down while Rwp falls.",
            _with_pspline),
    Variant("hump", "+ one explicit hump",
            "One broad Gaussian (6° FWHM, a third of the way up the range) "
            "added on top of the standard's own background, freed in a late "
            "stage. None of these standards has a known hump, so the expected "
            "answer is 'buys nothing': read BACKGROUND_ABSORPTION and "
            "HUMP_TOO_NARROW, never Rwp — three free parameters "
            "with an unconstrained position improve Rwp whether or not there "
            "is anything there, which is why the width guard exists.",
            _with_hump),
    Variant("roughness_suortti", "+ surface roughness (Suortti)",
            "Low-angle intensity depression, Suortti (1972). Bounded ≤ 1 "
            "everywhere. Note b is bimodal — both b → 0 and b → ∞ are the "
            "identity — so read ROUGHNESS_UNCONSTRAINED, not the value of b.",
            _with_roughness_suortti, geometries=("bragg_brentano",)),
    Variant("roughness_pitschke", "+ surface roughness (Pitschke)",
            "The same aberration, Pitschke et al. (1993). Empirical below "
            "sinθ = 2τ and *amplifying* below sinθ = τ, which is what "
            "ROUGHNESS_OUTSIDE_REGIME reports.",
            _with_roughness_pitschke, geometries=("bragg_brentano",)),
    Variant("extinction", "+ secondary extinction",
            "Sabine polycrystalline blend on the strongest low-angle reflections. "
            "Correlates with the scale at ρ ≈ 0.97 — a genuine degeneracy, so "
            "expect HIGH_CORRELATION and treat any 'improvement' sceptically.",
            _with_extinction),
    Variant("preferred_orientation", "+ March-Dollase texture",
            "Single-axis March-Dollase on a guessed axis ((001) for hexagonal/"
            "trigonal/tetragonal cells, (100) otherwise). r ≡ 1 is the exact "
            "identity, so an untextured specimen simply stays there.",
            _with_preferred_orientation),
    Variant("stephens", "+ Stephens anisotropic strain",
            "hkl-dependent Lorentzian widths, seeded on the isotropic ray. "
            "Judge with ΔBIC, not Hamilton's R-ratio (useless at 7000 channels) "
            "— and check STEPHENS_STRAIN_NOT_POSITIVE, which rejects the "
            "coefficients whatever the statistics say.",
            _with_stephens),
    Variant("absorption", "+ capillary absorption (µR = 0.5)",
            "Rouse cylinder transmission. It is an exact reparameterisation of "
            "{scale, Biso}, so **Rwp cannot change** — if it does, something is "
            "wrong. The whole effect is the Biso column of the results table.",
            _with_capillary_absorption, geometries=("debye_scherrer",)),
    Variant("capillary_displacement", "+ capillary displacement (eq 4)",
            "McCusker eq (4): the capillary off the centre of the 2θ circle, "
            "sin2θ along the beam and cos2θ across it, freed beside the zero "
            "shift. Read the correlations, not only Rwp — the three span "
            "{sin2θ, cos2θ, 1} and a short range cannot separate them. At a "
            "synchrotron with a crystal analyser the expected answer is "
            "'both ≈ 0'.",
            _with_capillary_displacement, geometries=("debye_scherrer",)),
    Variant("flat_plate", "+ finite specimen thickness (µt = 0.5)",
            "ITC (2) flat-plate absorption — declares a thin layer where the "
            "baseline assumes an infinitely thick mount. Unlike the capillary "
            "case it is *not* an exact reparameterisation, so Rwp moves too; the "
            "point is the scale of the Biso shift a mis-declared thickness "
            "causes, which reaches Å².",
            _with_flat_plate_absorption, geometries=("bragg_brentano",)),
)

VARIANT_BY_KEY = {v.key: v for v in VARIANTS}


# ----------------------------------------------------------------------
# running
# ----------------------------------------------------------------------
@dataclass
class RunRecord:
    """One (standard, variant) refinement, reduced to what the UI needs."""

    standard: str
    variant: str
    status: str
    seconds: float
    rwp: float
    rp: float
    gof: float
    chi2: float
    n_free: int
    n_points: int
    durbin_watson: float | None
    esd_inflation: float | None
    two_theta: list[float]
    y_obs: list[float]
    y_calc: list[float]
    y_background: list[float]
    #: weighted residual δ = (y_obs − y_calc)/σ, full resolution before decimation
    delta: list[float]
    #: cumulative Σδ² — the reference-independent half of the Δχ² panel, so the
    #: client can re-reference to any variant without a server round trip
    cumulative_chi2: list[float]
    ticks: dict[str, list[float]] = field(default_factory=dict)
    diagnostics: list[dict] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)
    error: str | None = None


#: parameters worth showing next to Rwp.  Deliberately includes the displacement
#: parameters: several variants here are *designed* to move Biso without moving
#: Rwp, and a table that showed only agreement indices would report them as
#: doing nothing.
_REPORT_PATHS = (
    ".cell.a", ".cell.b", ".cell.c", ".biso", ".scale",
    "instrument.zero_shift", "instrument.geometry.sample_displacement",
    "instrument.geometry.capillary_offset",
    "instrument.geometry.surface_roughness", ".extinction",
    ".preferred_orientation.r",
)


def _reported_parameters(result) -> list[dict]:
    out = []
    for p in result.parameters:
        if not p.vary:
            continue
        if not any(k in p.path for k in _REPORT_PATHS):
            continue
        out.append({"path": p.path, "value": p.value, "stderr": p.stderr})
    return out


def run(standard_key: str, variant_key: str, *,
        data_dir: Path | None = None, max_points: int = 4000) -> RunRecord:
    """Refine one standard under one variant and reduce it for the UI.

    Never raises on a refinement failure: a variant that blows up is a *result*
    (it means the correction is not usable on this specimen), so the record
    comes back with ``error`` set and the UI shows it beside the ones that
    worked.  Programming errors in the registry itself still propagate.
    """
    from ..refine import Refinement

    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    standard = STANDARD_BY_KEY[standard_key]
    variant = VARIANT_BY_KEY[variant_key]
    if not standard.available(data_dir):
        missing = [f for f in standard.files if not (data_dir / f).exists()]
        raise FileNotFoundError(
            f"standard {standard_key!r} needs {missing} under {data_dir}")

    started = time.perf_counter()
    inputs = standard.build(data_dir)
    variant.apply(inputs)

    ref = Refinement(inputs.structure, inputs.instrument, history=False)
    try:
        result = ref.fit(inputs.data, plan=inputs.plan,
                         two_theta_limits=inputs.two_theta_limits)
    except Exception as exc:  # a failed variant is a finding, not a crash
        return RunRecord(
            standard=standard_key, variant=variant_key, status="failed",
            seconds=time.perf_counter() - started,
            rwp=float("nan"), rp=float("nan"), gof=float("nan"),
            chi2=float("nan"), n_free=0, n_points=0,
            durbin_watson=None, esd_inflation=None,
            two_theta=[], y_obs=[], y_calc=[], y_background=[],
            delta=[], cumulative_chi2=[],
            error=f"{type(exc).__name__}: {exc}")

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    y_bkg = np.asarray(result.y_background)
    sigma = np.asarray(result.sigma)
    delta = (y_obs - y_calc) / np.where(sigma > 0.0, sigma, 1.0)
    cumulative = np.cumsum(delta ** 2)

    idx = decimation_index(tt, [y_obs, y_calc, delta], max_points)
    stats = result.statistics
    return RunRecord(
        standard=standard_key, variant=variant_key, status=result.status,
        seconds=time.perf_counter() - started,
        rwp=stats.rwp, rp=stats.rp, gof=stats.gof, chi2=stats.chi2,
        n_free=stats.n_free_parameters, n_points=stats.n_points,
        durbin_watson=stats.durbin_watson, esd_inflation=stats.esd_inflation,
        two_theta=tt[idx].tolist(),
        y_obs=y_obs[idx].tolist(), y_calc=y_calc[idx].tolist(),
        y_background=y_bkg[idx].tolist(),
        delta=delta[idx].tolist(), cumulative_chi2=cumulative[idx].tolist(),
        ticks={k: v for k, v in result.ticks.items()},
        diagnostics=[{"level": d.level, "code": d.code, "where": list(d.where),
                      "message": d.message, "suggestion": d.suggestion or ""}
                     for d in result.diagnostics],
        parameters=_reported_parameters(result),
    )


def decimation_index(tt: np.ndarray, curves: list[np.ndarray],
                     max_points: int) -> np.ndarray:
    """Indices keeping each bucket's min AND max of every curve.

    Never plain striding: at 4000 points from a 40 000-point pattern, striding
    drops peak tops and the "which fit is better" comparison would be decided
    by which variant happened to be sampled at a maximum.  The cumulative-χ²
    curve is monotone, so sampling it on the same index set is exact at those
    points and loses only the within-bucket path.

    Public because a second consumer arrived: the GUI's ``/api/result/window``
    route (WP-1008) sends a 2θ window to a browser under the same budget, and a
    second implementation would be a second answer to "which points survive" —
    the one question a plot must not disagree with the comparison UI about.

    **The index set is the contract, not the way it is found** (WP-1413).  Three
    consumers read it and a plot that disagreed with the comparison UI about
    which points it drew would be a picture of a different fit, so the segmented
    scan below is held to returning what the ``argmin``/``argmax`` loop it
    replaced returned, element for element, by
    ``test_decimation_is_the_loop_it_replaced``.  The loop cost 6.5-6.8 ms a
    snapshot on every pattern size, because its work is ``2000`` buckets of
    python rather than anything the data does.
    """
    n = len(tt)
    if n <= max_points:
        return np.arange(n)
    n_buckets = max(max_points // 2, 1)
    edges = np.linspace(0, n, n_buckets + 1, dtype=int)
    # Distinct edges are the non-empty buckets: ``reduceat`` reduces
    # ``starts[i]:starts[i+1]`` and the last one to the end, which is the
    # ``b > a`` guard the loop spelled out.
    starts = np.unique(edges[:-1])
    widths = np.diff(np.append(starts, n))
    positions = np.arange(n)
    keep = [np.array([0, n - 1])]
    for y in curves:
        y = np.asarray(y)
        if np.isnan(y).any():
            # ``argmin`` returns the first NaN; ``minimum.reduceat`` propagates
            # it and the equality below then matches nothing.  Rare enough to
            # pay the loop for rather than to reproduce.
            keep.append(_extrema_by_loop(y, starts, n))
            continue
        for reduction in (np.minimum, np.maximum):
            best = np.repeat(reduction.reduceat(y, starts), widths)
            # first index attaining it, which is what argmin/argmax return: a
            # tie keeps the earliest, so the sentinel is n and the reduce is min
            keep.append(np.minimum.reduceat(
                np.where(y == best, positions, n), starts))
    return np.unique(np.concatenate(keep))


def _extrema_by_loop(y: np.ndarray, starts: np.ndarray, n: int) -> np.ndarray:
    """Each bucket's ``argmin`` and ``argmax``, one bucket at a time.

    The NaN path of :func:`decimation_index`, kept because it is also the
    statement of what that function's vectorised body has to reproduce.
    """
    stops = np.append(starts[1:], n)
    out = []
    for a, b in zip(starts, stops):
        out.append(int(a) + int(np.argmin(y[a:b])))
        out.append(int(a) + int(np.argmax(y[a:b])))
    return np.array(out, dtype=np.int64)


def catalog(data_dir: Path | None = None) -> dict:
    """The UI's menu: standards (with availability) and applicable variants."""
    data_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    return {
        "data_dir": str(data_dir),
        "standards": [
            {"key": s.key, "title": s.title, "description": s.description,
             "geometry": s.geometry, "available": s.available(data_dir),
             "variants": [v.key for v in VARIANTS if v.applies_to(s)]}
            for s in STANDARDS
        ],
        "variants": [
            {"key": v.key, "title": v.title, "description": v.description,
             "geometries": list(v.geometries)}
            for v in VARIANTS
        ],
    }
