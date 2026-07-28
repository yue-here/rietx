"""Side-by-side comparison of refinement *settings* on the bundled standards.

The question this answers is the one that comes up every time a new correction
lands: **does it actually make the fit better, and where?**  That is hard to
read off two Rietveld panels drawn next to each other — the eye is poor at
differencing two difference curves — and it is not answerable from Rwp alone,
because some corrections provably cannot move Rwp at all (capillary absorption
is an exact reparameterisation of the scale and Biso; see
:mod:`pxrdref.model.absorption`) while others improve it by absorbing physics
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
`ROUGHNESS_UNCONSTRAINED`, `BACKGROUND_ABSORPTION` …).  See
`docs/AGENT_PROTOCOL.md` §7-8.

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
    BackgroundChebyshev,
    BackgroundPSpline,
    Dispersion,
    Instrument,
    RoughnessPitschke,
    RoughnessSuortti,
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
    build: Callable[[Path], StandardInputs]
    geometry: str                      # "bragg_brentano" | "debye_scherrer"

    def available(self, data_dir: Path) -> bool:
        return all((data_dir / f).exists() for f in self.files)


def _p(v: float, **kw) -> Parameter:
    return Parameter(value=v, **kw)


def _qarr_phase(name, sg, cell, atoms, **kw) -> Phase:
    a, b, c, al, be, ga = cell
    from ..schemas.structure import Atom, Cell

    return Phase(
        name=name, space_group=sg,
        cell=Cell(a=_p(a, min=1.0), b=_p(b, min=1.0), c=_p(c, min=1.0),
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

    Deterministic, and keeps TRF's first stage inside the softplus transform's
    live range — a scale that starts orders of magnitude off is the most common
    reason a first stage goes nowhere.
    """
    from ..model.forward import compile_model
    from ..params.vector import ParameterTable

    model = compile_model(structure, ins, data, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    obs = np.asarray(data.intensity)
    ratio = float((obs.sum() - obs.min() * len(obs)) / max(float(y.sum()), 1e-9))
    for ph in structure.phases:
        ph.scale.value *= ratio / len(structure.phases)


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
      `docs/AGENT_PROTOCOL.md` §8.1 warns about. It is the leftover of an exact
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
    ins.profile.w.value = 2e-5
    ins.profile.x.value = 2e-3
    ins.background = BackgroundChebyshev.with_terms(6)
    plan = RefinementPlan.mccusker_default()
    plan.stages.append(Stage("biso", ["phases.*.atoms.*.biso"]))
    return StandardInputs(data=data, structure=structure, instrument=ins,
                          plan=plan, two_theta_limits=(2.0, 24.0))


STANDARDS: tuple[Standard, ...] = (
    Standard(
        key="srm660c", title="NIST SRM 660c — LaB₆ (lab CuKα)",
        description=("Certified line-profile standard on the NIST divergent-beam "
                     "diffractometer. The package's **absolute** cell anchor "
                     "(a = 4.156895(25) Å, +28 ppm). Zero held at 0, displacement "
                     "refined — the NIST protocol."),
        files=("nist_srm660c_100a.cif",), build=_build_srm660c,
        geometry="bragg_brentano"),
    Standard(
        key="corundum", title="SRM 676a corundum — α-Al₂O₃ (lab CuKα)",
        description=("IUCr CPD round-robin pure phase, also the SRM 676a cell "
                     "anchor. c/a is the certificate-grade assertion (+30 ppm); "
                     "the absolute axes carry a ≈−300 ppm lab d-scale offset."),
        files=("qarr/corundum.prn",), build=_build_qarr(corundum_phase, "qarr/corundum.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="zincite", title="Zincite — ZnO (lab CuKα)",
        description=("Round-robin pure phase. The sharpest demonstration of "
                     "neglected anomalous scattering: applying f′/f″ barely moves "
                     "Rwp but takes B(O) from 0.02 to 0.43 Å² — a displacement "
                     "parameter that had been spending itself on Zn's missing f′."),
        files=("qarr/zincite.prn",), build=_build_qarr(zincite_phase, "qarr/zincite.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="fluorite", title="Fluorite — CaF₂ (lab CuKα)",
        description=("Round-robin pure phase; both sites fully fixed by symmetry, "
                     "so displacement parameters are the only structural freedom "
                     "and intensity-correction degeneracies show up cleanly."),
        files=("qarr/fluorite.prn",), build=_build_qarr(fluorite_phase, "qarr/fluorite.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="brucite", title="Brucite — Mg(OH)₂ (lab CuKα)",
        description=("Round-robin pure phase and its designated preferred-orientation "
                     "specimen: strongly platy on (001). The anisotropic-strain test "
                     "case — where the improvement is real, passes ΔBIC, and is still "
                     "rejected by the positivity cone."),
        files=("qarr/brucite.prn",), build=_build_qarr(brucite_phase, "qarr/brucite.prn"),
        geometry="bragg_brentano"),
    Standard(
        key="nac", title="APS 11-BM — NAC + CaF₂ (synchrotron capillary)",
        description=("Na₂Ca₃Al₂F₁₄ with a fluorite impurity, λ = 0.4139090 Å, fitted "
                     "2-24° 2θ. The only debye_scherrer standard here, so the only "
                     "one where the capillary absorption variant applies."),
        files=("11BM_NAC.fxye", "cod_1000236.cif"), build=_build_nac,
        geometry="debye_scherrer"),
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

    Fixed rather than estimated so the comparison is reproducible: the 11-BM
    deposited metadata does not carry a bore diameter, and µR is *not*
    refinable by construction (it is an exactly singular direction alongside
    the scale and Biso).  Expect Rwp to be **identical** to the baseline and
    Biso to move by ΔB = c(µR)·λ²/2 — that is the whole content of the
    correction, and the reason the results table shows Biso next to Rwp.
    """
    inputs.instrument.geometry.mu_r = 0.5


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

    idx = _decimation_index(tt, [y_obs, y_calc, delta], max_points)
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


def _decimation_index(tt: np.ndarray, curves: list[np.ndarray],
                      max_points: int) -> np.ndarray:
    """Indices keeping each bucket's min AND max of every curve.

    Never plain striding: at 4000 points from a 40 000-point pattern, striding
    drops peak tops and the "which fit is better" comparison would be decided
    by which variant happened to be sampled at a maximum.  The cumulative-χ²
    curve is monotone, so sampling it on the same index set is exact at those
    points and loses only the within-bucket path.
    """
    n = len(tt)
    if n <= max_points:
        return np.arange(n)
    n_buckets = max(max_points // 2, 1)
    edges = np.linspace(0, n, n_buckets + 1, dtype=int)
    keep = {0, n - 1}
    for y in curves:
        for a, b in zip(edges[:-1], edges[1:]):
            if b > a:
                keep.add(a + int(np.argmin(y[a:b])))
                keep.add(a + int(np.argmax(y[a:b])))
    return np.array(sorted(keep))


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
