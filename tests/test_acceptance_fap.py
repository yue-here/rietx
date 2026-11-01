"""v0.2 second lab acceptance: fluorapatite, GSAS-II "LabData" tutorial.

Cu Kα doublet on a conventional laboratory Bragg-Brentano diffractometer,
15-130° 2θ, 5753 points, counts only (Poisson σ).  Unlike the SRM 660c test —
which anchors to a NIST *certificate* — this one is a **cross-code
consistency check** against GSAS's own converged refinement of the same data,
with tolerances that respect legitimate inter-code convention differences
(docs/DESIGN.md, "Testing & validation policy").

**The protocol is read from ``FAP.EXP``, not transcribed from it** (WP-1118).
Every number below — the cell, the seven sites, the space group, the
wavelengths, the polarization, the held Caglioti terms, the excluded region and
GSAS's own Rwp and esds — comes from ``rx.read_gsas_exp``.  Before that they
were constants somebody had read off the file by hand, which is the failure
mode the reader exists to remove: a mistyped coordinate stays symmetry-valid,
so what comes out is a plausible wrong answer rather than an error.

What the file says, and what this test does with it:

* the specimen **displacement** refines and the zero point is held at 0
  (``ICONS``' zero field carries no refine flag);
* the instrument Caglioti ``GU, GV, GW`` are held at the values the file
  states, whose flags are ``N``;
* the **sample** Lorentzian ``LX``, ``LY`` refine (flags ``Y``) — the
  instrument ⊕ sample profile split this milestone added;
* 2θ > 130° is excluded (``EXC 2``), which reproduces GSAS's point count of
  5750 exactly, so the agreement indices are computed over the same channels.

**Two things the file states that this test does not do**, named here because
reading the protocol is what made them visible:

* GSAS refined the **coordinates** of all seven sites (twelve site-symmetry
  DOFs; its ``X`` flag means "as permitted by symmetry").  This plan does not
  free them, so it refines 20 parameters against GSAS's 28.  That is a real
  difference in protocol and ``test_the_file_states_a_wider_free_set_than_this_plan``
  is where it is recorded rather than implied.
* GSAS fitted its background function 5, a reciprocal-Q expansion for air
  scatter, which has no rietx counterpart; a 6-term Chebyshev is used instead.
  So an Rwp comparison here is between two different background models, which
  is one more reason the band below is a consistency band and not a tolerance.

**Measured result** (2026-07-22, recorded in docs/milestones/v0.2.md):
Rwp = 9.73 % against GSAS's 10.05 % and Rp = 7.76 % against its 7.66 %, on an
identical 5750 channels — the two codes agree on fit quality to ~1 % relative.
Refined sample broadening: Lorentzian size 0.0246° against GSAS's
LX = 0.0335°.  That gap is the axial-divergence model GSAS's function 2 does
not have (see ``test_fap_lorentzian_matches_gsas_lx_on_gsas_own_model``, which
removes it and lands within 3 % of LX).  The cell is a = 9.372807 Å, c = 6.886642 Å against GSAS's
9.371724(36) and 6.885867(37): **+116 and +113 ppm**.  That the two axes are
offset by the *same relative* amount is the diagnostic — a uniform d-scale
(peak-position convention) difference, not a shape or structural disagreement;
GSAS's ``shft`` converges to the opposite sign from our refined displacement,
which is the same statement seen from the other side.  ±300 ppm is therefore
the honest consistency band here.  Certificate-grade accuracy is claimed only
by the SRM 660c test; neither code's cell is "truth" for this specimen.
"""

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.projects.gsas import gaussian_fwhm_squared_degrees, to_structure
from rietx.schemas.instrument import BackgroundChebyshev, EmissionLine, Source

DATA = Path(__file__).parent / "data"
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("fap")]

#: GSAS's converged refinement of this dataset, read once.  Every reference
#: value and the whole refine protocol below come off this object, so there is
#: one authority for them and it is the file.
EXP = rx.read_gsas_exp(DATA / "FAP.EXP")
_PHASE = EXP.phases[0]
_HIST = EXP.histogram()
_TERMS = EXP.profile().by_name()

A_GSAS, A_GSAS_ESD = _PHASE.cell.a, _PHASE.cell.esd_a
C_GSAS, C_GSAS_ESD = _PHASE.cell.c, _PHASE.cell.esd_c
RWP_GSAS, RP_GSAS = EXP.rwp, EXP.rp


def _held(structure: rx.Structure) -> rx.Structure:
    """``structure`` with every parameter held, for the staged plan to free.

    ``to_structure`` hands back the file's own refine flags, and a stage's
    ``turn_on`` globs **add** to the free set rather than replacing it — so
    passing those flags in would free every site from the first stage and make
    the staging mean nothing.  The flags are not discarded: they are what
    :func:`gsas_free_paths` reads, and the plan is checked against them.
    """
    for phase in structure.phases:
        for name in ("a", "b", "c", "alpha", "beta", "gamma"):
            getattr(phase.cell, name).vary = False
        for atom in phase.atoms:
            for name in ("x", "y", "z", "occ", "biso"):
                getattr(atom, name).vary = False
    return structure


def gsas_free_paths() -> set[str]:
    """The structural parameters GSAS left free, as rietx dot-paths.

    Read off the refine flags ``to_structure`` carries across, before
    :func:`_held` clears them.
    """
    ref = rx.Refinement(to_structure(EXP), rx.Instrument.bragg_brentano())
    return {row.path for row in ref.parameters() if row.refinable and row.vary}


def build_fap_inputs():
    """(data, structure, instrument) for the GSAS-II tutorial protocol.

    Plain function as well as fixture, for the reason ``build_srm_inputs`` is
    one: ``test_acceptance_indexing`` rebuilds this exact state — in particular
    the tutorial's own 1.5405/1.5443 Å doublet rather than our NIST/Hölzer
    preset, a 60 ppm difference that would land straight on any cell compared
    against GSAS's.
    """
    path = DATA / "FAP.XRA"
    if not path.exists():
        pytest.skip("GSAS-II LabData tutorial dataset not present")
    raw = rx.read_pattern(path)
    data = rx.PatternData(
        two_theta=raw.two_theta, intensity=raw.intensity, sigma=raw.sigma,
        # GSAS's own excluded region, as the file states it.  Its 130.000 lower
        # bound removes the same three channels the hand-written 129.99 did,
        # because rietx's exclusion is closed at both ends and the file's last
        # channels are 130.00, 130.02 and 130.04.
        excluded_regions=list(_HIST.excluded_regions),
        metadata=raw.metadata)

    # the cell, the sites and the space group, from the file's own records
    structure = _held(to_structure(EXP))
    phase = structure.phases[0]
    phase.name = "fluorapatite"
    for name in ("a", "b", "c"):
        getattr(phase.cell, name).min = 1.0
    phase.scale = rx.Parameter(value=1e-3, min=0.0, transform="softplus")
    # GSAS's converged LX and LY, in degrees, as this refinement's start
    phase.lor_size = rx.Parameter(value=_TERMS["LX"].degrees, min=0.0,
                                  transform="softplus")
    phase.lor_strain = rx.Parameter(value=_TERMS["LY"].degrees, min=0.0,
                                    transform="softplus")

    instrument = rx.Instrument.bragg_brentano()
    lam1, lam2 = _HIST.wavelengths
    instrument.source = Source(
        # the tutorial's own wavelengths, not our NIST/Hölzer preset: a 60 ppm
        # wavelength difference would map straight onto the cell being compared
        lines=[EmissionLine(wavelength=lam1),
               # the file's KRATIO field is **blank**, so this 0.5 is this
               # test's own convention and not GSAS's.  The 0.5 the file does
               # state sits one field earlier and is the polarization below;
               # both quantities are conventionally 0.5, which is how reading
               # the wrong one stays invisible on this file (WP-1118).
               EmissionLine(wavelength=lam2,
                            weight=rx.Parameter(value=0.5, min=0.0, max=1.0))],
        polarization=rx.Parameter(value=_HIST.polarization, min=0.0, max=1.0),
        # Dispersion DECLINED (WP-1001 made it the package default): this is
        # the cross-code row, and GSAS's converged FAP.EXP did not apply f′/f″
        # either.  Adopting another code's protocol means adopting what it did
        # NOT model as much as what it did — the v0.2 lesson.
        dispersion=None)
    # GSAS GU, GV, GW — held, as their N flags say
    # GU GV GW are a Gaussian variance; u v w the Gaussian FWHM² (#735)
    instrument.profile.u.value = gaussian_fwhm_squared_degrees(_TERMS["GU"])
    instrument.profile.v.value = gaussian_fwhm_squared_degrees(_TERMS["GV"])
    instrument.profile.w.value = gaussian_fwhm_squared_degrees(_TERMS["GW"])
    # S/L and H/L are near-degenerate (see Geometry docstring); refine one
    instrument.geometry.axial_sl.value = 0.02
    instrument.geometry.axial_hl.value = 0.02
    # GSAS fitted its background function 5, which has no counterpart here
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument

@pytest.fixture(scope="module")
def fap_inputs():
    return build_fap_inputs()


def _gsas_protocol_plan() -> rx.RefinementPlan:
    """The parameter set GSAS refined for this tutorial (see module docstring)."""
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("disp", ["instrument.geometry.sample_displacement"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("sample_lor", ["phases.*.lor_size", "phases.*.lor_strain"]),
        rx.Stage("axial", ["instrument.geometry.axial_sl"]),
        rx.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])
    # WP-1123: the shipped convergence schedule, named rather than inherited.
    # Every stage but the last stops at 1e-6 and the last at the solver's own
    # 1e-9, which is what a user's own run does — so these numbers are the
    # ones the package actually produces.  None here would converge every
    # stage; measured cost of the schedule on this protocol is <= 0.02 esd.
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    return plan


@pytest.fixture(scope="module")
def fap_fit(fap_inputs):
    """The GSAS-protocol refinement, computed once for the rows that read it.

    Module-scoped because two tests need the same numbers and it costs ~6 s;
    the module carries the matching ``xdist_group`` so a second worker cannot
    quietly refit it.  Callers must not mutate the returned ``Refinement`` —
    the constraint row below builds its own.
    """
    data, structure, instrument = fap_inputs
    ref = rx.Refinement(structure, instrument)
    return ref, ref.fit(data, plan=_gsas_protocol_plan())


def test_fap_lab_rietveld_matches_gsas(fap_inputs, fap_fit):
    data, structure, instrument = fap_inputs
    assert len(data.two_theta) == 5753
    assert data.sigma is None            # counts only ⇒ Poisson fallback

    ref, result = fap_fit

    assert result.status == "converged"
    # the exclusion reproduces GSAS's channel count exactly, so the agreement
    # indices below are computed over the same data GSAS used
    assert result.statistics.n_points == 5750
    # both indices within 10 % (relative) of GSAS's on identical channels
    assert result.statistics.rwp == pytest.approx(RWP_GSAS, rel=0.10)
    assert result.statistics.rp == pytest.approx(RP_GSAS, rel=0.10)
    assert result.statistics.gof < 2.0

    phase = ref.fitted_structure.phases[0]
    a, c = phase.cell.a.value, phase.cell.c.value
    # cross-code consistency band, NOT a certificate: see module docstring
    assert abs(a / A_GSAS - 1.0) < 3e-4
    assert abs(c / C_GSAS - 1.0) < 3e-4
    # hexagonal tie: b tracks a exactly, c is independent
    assert phase.cell.b.value == pytest.approx(a, rel=1e-12)
    assert abs(c / a - C_GSAS / A_GSAS) < 1e-4

    # the offset is a uniform d-scale difference, not an axis-specific one —
    # this is the assertion that distinguishes "convention" from "wrong"
    assert abs((a / A_GSAS) - (c / C_GSAS)) < 1e-4

    # Refined sample broadening against GSAS's LX (its LY is split differently
    # between the two codes' strain conventions, so only the physical range is
    # checked there).  This fit carries axial divergence (S/L refined) and the
    # preset's instrument Lorentzian X = 0.001, neither of which GSAS's
    # function 2 has, so rietx's lor_size sits below LX by what they absorb:
    # 0.0246 against 0.0335.  The like-for-like comparison, with both removed,
    # is test_fap_lorentzian_matches_gsas_lx_on_gsas_own_model.
    assert phase.lor_size.value == pytest.approx(0.0335, rel=0.30)
    assert 0.0 <= phase.lor_strain.value < 0.15
    # the instrument resolution function was held, as in GSAS
    assert ref.fitted_instrument.profile.u.value == pytest.approx(2e-4 * 8.0 * math.log(2.0))
    assert ref.fitted_instrument.profile.w.value == pytest.approx(5e-4 * 8.0 * math.log(2.0))
    assert ref.fitted_instrument.zero_shift.value == 0.0

    # esds are Bérar-Lelann inflated; GSAS's are not, so ours must be larger
    a_esd = result.parameter("phases.0.cell.a").stderr
    assert a_esd is not None and A_GSAS_ESD < a_esd < 20 * A_GSAS_ESD
    assert result.statistics.esd_inflation > 1.0

    # FitReport must digest a real lab pattern end to end
    report = ref.report(plan=_gsas_protocol_plan())
    assert report.summary and report.n_regions_total > 10

    from rietx.viz.plots import plot_for_vlm, plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "fap_fit.png"))
    plot_result(result, path=str(out / "fap_fit_lowangle.png"),
                two_theta_range=(15.0, 35.0))
    plot_for_vlm(result, report, path=str(out / "fap_vlm.png"))


#: The three phosphate oxygens (``O5``, ``O6``, ``O7`` in FAP.EXP's atom
#: order).  One chemical environment — the corners of the PO₄ tetrahedron —
#: which is what §7's "constrain the thermal parameters of similar atoms to be
#: equal" is about; the Ca, P and F sites are deliberately left free.
PHOSPHATE_OXYGENS = [f"phases.0.atoms.{i}.biso" for i in (4, 5, 6)]


def test_tying_the_similar_atoms_bisos_buys_precision(fap_inputs, fap_fit):
    """McCusker et al. (1999) §7, measured on the cross-code lab protocol.

    A constraint reduces parameters where a restraint adds observations, and
    the return is precision on the parameters that remain.  The evidence is
    therefore the recorded parameter count and the esds, **not** Rwp — which is
    also what Rwp does here: it moves by +0.05 % relative, i.e. the constraint
    costs no fit quality and could not have shown that it bought anything.

    Measured 2026-10-08, ``[dev]`` on darwin/arm64, with the esds carrying
    Bérar & Lelann's eqs (10)-(12) factor (#674; fits are deterministic, only
    the wall clock is machine state):

    ==========================  ============  ============
    ..                          free          tied
    ==========================  ============  ============
    free parameters             20            18
    Rwp                         0.092498      0.092546
    B(O5) / Å²                  0.3647(1513)  0.5150(754)
    B(O6) / Å²                  0.6016(1590)  0.5150(754)
    B(O7) / Å²                  0.5377(1078)  0.5150(754)
    ==========================  ============  ============

    The three free values are mutually consistent — they sit 0.99, 0.54 and
    0.21 of their own esds from the tied value — which is the premise §7 asks
    the experimenter to check before constraining.  (Under the pre-1.6 run-sum
    factor, whose esds were 27 % wider here, every interval contained it.)  The
    tied esd 0.0754 is tighter than the best of the three free ones (0.1078)
    and slightly tighter than their inverse-variance combination (0.0769),
    because the constrained fit uses the correlations between the three sites
    and a naive weighted mean does not.
    """
    data, structure, instrument = fap_inputs
    _, free = fap_fit

    ref = rx.Refinement(structure, instrument)
    assert ref.tie_equal(PHOSPHATE_OXYGENS) == PHOSPHATE_OXYGENS[1:]
    tied = ref.fit(data, plan=_gsas_protocol_plan())
    assert tied.status == "converged"

    # the reduction is the recorded fact, on the same channels
    assert tied.statistics.n_points == free.statistics.n_points == 5750
    assert tied.statistics.n_free_parameters == free.statistics.n_free_parameters - 2

    rows = {r.path: r for r in ref.parameters()}
    common = rows[PHOSPHATE_OXYGENS[0]]
    assert common.esd is not None
    for path in PHOSPHATE_OXYGENS[1:]:
        # one parameter, three sites: same value, same esd, and the dependents
        # say where it comes from
        assert rows[path].value == pytest.approx(common.value, rel=1e-12)
        assert rows[path].esd == pytest.approx(common.esd, rel=1e-12)
        assert rows[path].tie.sources == [PHOSPHATE_OXYGENS[0]]

    # §7's premise: the free values agreed within their own esds, so the
    # constraint asserts nothing the free refinement contradicts
    esds = []
    for path in PHOSPHATE_OXYGENS:
        p = free.parameter(path)
        assert p.stderr is not None
        assert abs(p.value - common.value) < 1.5 * p.stderr, path
        esds.append(p.stderr)

    # ...and the return: tighter than the best free one, and at least as tight
    # as combining the three by inverse variance
    combined = 1.0 / np.sqrt(sum(1.0 / e**2 for e in esds))
    assert common.esd < min(esds)
    assert common.esd < 1.05 * combined

    # the sites left free are undisturbed — the constraint acts where it was
    # declared and nowhere else
    for i in (0, 1, 2, 3):
        path = f"phases.0.atoms.{i}.biso"
        p = free.parameter(path)
        assert abs(rows[path].value - p.value) < 0.5 * p.stderr, path

    # Rwp is reported, never relied on: stated so the record shows it did not
    # move, not because a move would have meant anything either way
    assert tied.statistics.rwp == pytest.approx(free.statistics.rwp, rel=2e-3)

    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(tied, path=str(out / "fap_tied_bisos.png"))
    plot_result(tied, path=str(out / "fap_tied_bisos_lowangle.png"),
                two_theta_range=(15.0, 35.0))


def _fit_on_gsas_own_model(gaussian_variance_read_as_fwhm_squared: bool):
    """The FAP protocol with the two things GSAS's function 2 lacks removed:
    axial divergence (S/L, H/L held at 0 and not refined) and the preset's
    instrument Lorentzian X = Y = 0.  What is left is the model the file's
    ``GU GV GW LX LY`` were fitted under, so ``lor_size`` is comparable to LX.
    """
    data, structure, instrument = build_fap_inputs()
    instrument.geometry.axial_sl.value = 0.0
    instrument.geometry.axial_hl.value = 0.0
    instrument.profile.x.value = 0.0
    instrument.profile.y.value = 0.0
    if not gaussian_variance_read_as_fwhm_squared:
        # the pre-#735 reading: GU GV GW taken as the Gaussian FWHM^2 itself
        instrument.profile.u.value = _TERMS["GU"].degrees
        instrument.profile.v.value = _TERMS["GV"].degrees
        instrument.profile.w.value = _TERMS["GW"].degrees
    plan = _gsas_protocol_plan()
    plan.stages = [s for s in plan.stages if s.name != "axial"]
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, plan=plan)
    return ref.fitted_structure.phases[0].lor_size.value, result.statistics.rwp


def test_fap_lorentzian_matches_gsas_lx_on_gsas_own_model():
    """The one GSAS-I reference output in the tree, read both ways (#739 review).

    GSAS held ``GU GV GW`` and refined ``LX``, so with the rest of the model
    matched, the Lorentzian rietx needs is GSAS's ``LX`` only if the held
    Gaussian is the same width.  Measured (macOS arm64, 2026-10-06):

    ============================  ==========  ===========  ======
    ``GU GV GW`` read as          lor_size    vs LX 0.0335  Rwp
    ============================  ==========  ===========  ======
    variance (8 ln 2, the manual) 0.0326      -2.7 %        0.0953
    FWHM² (before #735)           0.0497      +48 %         0.1090
    ============================  ==========  ===========  ======

    The old reading's 5 % agreement on the full protocol was a coincidence of
    two errors: the axial-divergence term and the preset X, which GSAS has no
    counterpart for, absorbed what the too-narrow Gaussian left over.
    """
    lor_variance, rwp_variance = _fit_on_gsas_own_model(True)
    lor_fwhm2, rwp_fwhm2 = _fit_on_gsas_own_model(False)
    lx = _TERMS["LX"].degrees
    assert lx == pytest.approx(0.0335, rel=1e-3)
    assert lor_variance == pytest.approx(lx, rel=0.05)
    assert abs(lor_fwhm2 / lx - 1.0) > 0.25          # the old reading is not LX
    assert rwp_variance < rwp_fwhm2


def test_the_file_states_a_wider_free_set_than_this_plan(fap_inputs, fap_fit):
    """GSAS refined the coordinates; this plan does not, and that is recorded.

    Reading the protocol instead of transcribing it is what made this visible.
    The hand-written module docstring claimed "both codes refine the same
    parameter set", and they do not: GSAS's ``X`` flag is set on all seven
    sites, which is twelve site-symmetry DOFs, and no stage here frees them.

    The row asserts the difference rather than the agreement, so that closing
    it later is a deliberate change carrying its own measurement instead of a
    silent one.  ``GsasModel.n_variables`` is the file's own count and the
    reader reproduces it exactly from the flags
    (``tests/test_projects_gsas.py``), so the arithmetic below is checkable
    from both ends.
    """
    _, result = fap_fit
    free_here = {p.path for p in result.parameters if p.vary}
    free_in_gsas = gsas_free_paths()

    coordinates = {p for p in free_in_gsas if ".dof." in p}
    assert len(coordinates) == 12, "the file frees twelve coordinate DOFs"
    assert not (coordinates & free_here), "this plan frees none of them"

    # everything else the file frees, this plan frees too
    assert (free_in_gsas - coordinates) <= free_here

    # and the counts reconcile against the file's own stated total
    assert EXP.n_variables == 28
    assert len(free_in_gsas) == 21          # 2 cell + 12 DOF + 7 Biso
    assert result.statistics.n_free_parameters == 20

    # The file's other seven are the histogram's scale, three background terms
    # and LX, LY, shft.  This plan frees their counterparts, plus four the file
    # does not: axial_sl, which GSAS held, and three more background terms
    # (a six-term Chebyshev against function 5's three).
    beyond_the_structure = free_here - free_in_gsas
    assert beyond_the_structure == {
        "phases.0.scale", "phases.0.lor_size", "phases.0.lor_strain",
        "instrument.geometry.sample_displacement", "instrument.geometry.axial_sl",
        *(f"instrument.background.c{k}" for k in range(6))}
    assert EXP.profile().refined_names == ("LX", "LY", "shft")


def test_a_pawley_fit_past_the_bvls_cut_converges_every_stage(fap_inputs):
    """WP-1953: the default plan's Pawley fit solves 335-343 columns, past
    ``lm.BVLS_MAX_COLUMNS``.  Under BCCG's step the ``profile`` stage ran to
    its 400-evaluation cap at Rwp 0.08036, 236 of its 635 steps promising no
    descent.  The projected-CG step converges every stage, in TRF's basin:
    Rwp 0.0782443 under LM, 0.0783830 under TRF (macOS arm64).  The exact
    BVLS step converges too, at 0.0802866, because its eigenvalue cut drops
    near-null directions that still carry gradient."""
    from rietx.optimize import lm

    data, structure, instrument = fap_inputs
    ref = rx.Refinement(structure, instrument)
    result = ref.fit(data, mode="pawley")
    assert ref._model.pawley.n > lm.BVLS_MAX_COLUMNS
    assert [s.status for s in result.stages] == ["converged"] * len(result.stages)
    assert result.statistics.rwp < 0.0790
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    result.plot(path=str(out / "fap_pawley.png"))
    import matplotlib.pyplot as plt
    plt.close("all")
