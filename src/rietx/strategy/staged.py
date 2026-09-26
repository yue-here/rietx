"""Minimal staged refinement runner.

Encodes the IUCr-guideline practice of turning parameter groups on
cumulatively in a stable order (McCusker, Von Dreele, Cox, Louër & Scardi,
1999, J. Appl. Cryst. 32, 36): scale + background first, then peak positions
(zero/cell), then profile widths.  Each stage runs the bounded least squares
to convergence before the next group is freed; the reflection list and
evaluation windows are regenerated between stages (the differentiability
invariant — they stay frozen *within* a stage).
"""

from __future__ import annotations

import dataclasses
import functools
import re
from dataclasses import dataclass, field

from .._nearmiss import did_you_mean
from ..schemas.common import Mode

# INTERMEDIATE_FTOL is defined beside the mirror because the pydantic field
# needs it at class-definition time and this module is the *upper* layer; it is
# re-exported here, where plan policy is read.
from ..schemas.plan import INTERMEDIATE_FTOL, PlanSpec

#: ``phases.i.atoms.j.u11`` … — the stored anisotropic components, grouped by
#: site for the positive-definiteness guard.
_ADP_COMPONENT = re.compile(r"^(phases\.\d+\.atoms\.\d+)\.u(11|22|33|12|13|23)$")
_U_ORDER = {"11": 0, "22": 1, "33": 2, "12": 3, "13": 4, "23": 5}

#: The displacement-parameter stage frees whichever representation each site
#: actually uses.  Both globs are always safe: an isotropic site has no
#: ``adp.k`` entries, and an anisotropic one has its ``biso`` locked, so
#: neither can free a parameter that does not reach the model.
_DISPLACEMENT_GLOBS = ["phases.*.atoms.*.biso", "phases.*.atoms.*.adp.*"]


#: pydantic's *instance* surface — what a caller reaches for on any other object
#: in this package, and the two types here are the exception.
_PYDANTIC_SURFACE = frozenset({
    "model_dump", "model_dump_json", "model_validate", "model_validate_json",
    "model_fields", "model_copy", "model_json_schema", "model_fields_set",
})


def _ask_the_mirror(name: str, owner: str, call: str) -> AttributeError:
    """The AttributeError a dataclass raises when asked for pydantic (WP-1110).

    These two are the package's only **schema-shaped** objects that are not
    pydantic models: unlike ``Refinement`` or ``Project``, which are plainly
    machines, a plan is a record of fields sitting beside ``PlanSpec``, which
    mirrors it one for one.  So ``stage.model_dump()`` is the natural next
    keystroke, and the bare ``'Stage' object has no attribute 'model_dump'``
    says nothing about where serialization actually lives.  An error message is
    the documentation an agent reads: the round behind this WP measured agents
    discovering this package by ``dir()`` and by reading installed source, not
    by opening the chapter that already explains it.
    """
    return AttributeError(
        f"{owner} is a dataclass, not a pydantic model, so it has no "
        f"{name!r} — it is constructed positionally, which is what makes a "
        f"plan pleasant to write. Its serializable mirror is the pydantic "
        f"half of the same fact: {call}. See rietx.schemas.plan.")


#: One cross-class confusion worth naming directly (WP-1302): "free" reads
#: naturally as "what a stage freed", which is on the *result*, not the
#: *declaration* — a ``Stage`` says what it *may* turn on, ``StageResult.freed``
#: says what a solve actually did.
_CROSS_CLASS_HINTS: dict[tuple[str, str], str] = {
    ("Stage", "free"): "what a stage freed is StageResult.freed",
}


def _dataclass_attr_hint(cls: type, name: str) -> AttributeError:
    """A wrong dataclass field name answered with the right one (WP-1302).

    ``Stage``/``RefinementPlan`` are the package's non-pydantic schema-shaped
    types, so they get the ``Base.__getattr__`` treatment (``schemas/common.py``)
    by hand, over ``dataclasses.fields`` rather than ``model_fields``: the
    closest own-field match, or — for these small dataclasses — the field list
    outright.
    """
    fields = [f.name for f in dataclasses.fields(cls)]
    plain = f"{cls.__name__!r} object has no attribute {name!r}"
    hint = did_you_mean(name, fields)
    if hint:
        msg = f"{plain}; {hint}"
    elif len(fields) <= 12:
        msg = f"{plain}; its fields are {fields}"
    else:
        msg = plain
    extra = _CROSS_CLASS_HINTS.get((cls.__name__, name))
    if extra:
        msg = f"{msg}; {extra}"
    return AttributeError(msg)


@dataclass
class Stage:
    """One turn-on group of a staged plan — a declaration, not a result.

    What a stage *did* comes back as a ``StageResult`` (``StageResult.freed``,
    ``.rwp``, ``.n_iterations``, …) on ``RefinementResult.stages``, never on
    this object, which is unchanged by running it.
    """

    name: str
    turn_on: list[str]  # path globs, e.g. "phases.*.cell.*"
    #: solver iterations this stage may take.  Approximate rather than exact:
    #: scipy's TRF caps *evaluations*, not iterations, so this becomes
    #: ``max_iter x optimize.least_squares.NFEV_PER_ITERATION`` — sized from
    #: the measured worst-case trial-point rejection rate so a stage needing
    #: max_iter genuine iterations is never cut short.  A runaway guard, never
    #: a timer: every converging fit measured stays an order of magnitude
    #: inside it, and a stage that hits it reports STAGE_MAX_ITER.
    max_iter: int = 100
    #: this stage's own ftol (relative cost-decrease termination), overriding
    #: whatever schedule the plan sets.  ``None`` = take it from the plan
    #: (:attr:`RefinementPlan.intermediate_ftol` for every stage but the last,
    #: the solver's 1e-9 for the last) — which is why the two cannot be told
    #: apart here and a plan is where the schedule is declared.  Set it to say
    #: that *this* stage is different: an early stage whose seed the next one
    #: is unusually sensitive to, or a one-stage validation fit that must
    #: converge as hard as an endpoint.
    ftol: float | None = None
    lebail_cycles: int = 3  # intensity-partitioning refreshes (lebail mode)
    #: lift any softplus-bounded parameter this stage frees off the exact-zero
    #: floor to this value before solving, so TRF sees a live gradient (the
    #: softplus map's slope at p≈0 is ≈0, so a coefficient starting at 0 would
    #: never move).  0 = no seed.  The extinction stage uses it; unlike the FCJ
    #: AXIAL_SIZING_FLOOR (an identity-transform bound, movable off zero on its
    #: own) a softplus coefficient genuinely needs the value nudge.
    seed: float = 0.0
    #: microstrain (ppm of ΔM/M) to put a freed but still all-zero Stephens
    #: block on before solving.  ``seed`` cannot serve: the S_HKL DOFs are
    #: identity-transform, and their pathology at zero is the *exploding*
    #: gradient of √Σ rather than the softplus's dead one.  0 = no seed.
    strain_seed: float = 0.0
    #: c_w of McCusker eq (7), S = S_y + c_w·S_G: how heavily this stage weights
    #: the geometric 'observations' (every soft restraint the phases declare)
    #: against the diffraction data.  The paper's prescription is a *schedule* —
    #: "set high at the beginning of a refinement when the structure is
    #: incomplete or only approximately correct … then reduced during the course
    #: of the refinement as the structural model improves" — and a stage is what
    #: this package changes a discrete quantity between, so the schedule is one
    #: scalar per stage.  Constant within the stage, applied at its compile:
    #: frozen-per-stage discreteness as designed, not an exception to it.
    #: 1.0 is the identity (every pre-WP-1074 fit); 0.0 keeps the rows in the
    #: layout at zero magnitude rather than removing them, so the row count —
    #: and the statistics exclusion built on it — does not change mid-plan.
    restraint_weight_scale: float = 1.0
    #: absolute slack (°2θ) added to every evaluation-window half-width this
    #: stage compiles, replacing the default ``forward.WINDOW_MIN_DEG``.  The
    #: window has two jobs the WP-1112 area criterion split apart: tail
    #: coverage, which k(η)·Γ handles, and **capture range** — a peak must
    #: stay inside its frozen window wherever the stage's start error puts
    #: it.  The default slack covers ordinary refinement (a cold zero error
    #: is ~0.1°); a fit that *tests a hypothesis it must not walk toward* —
    #: the indexing Le Bail validation, whose candidate may be metrically
    #: wrong by design — declares the capture range its verdict needs
    #: (``indexing.workflow.VALIDATION_WINDOW_SLACK_DEG``).  ``None`` = the
    #: default; frozen at stage compile like every other discrete choice.
    window_slack_deg: float | None = None

    def __getattr__(self, name: str):
        if name in _PYDANTIC_SURFACE:
            raise _ask_the_mirror(name, "Stage",
                                  "rietx.StageSpec.from_stage(stage)")
        raise _dataclass_attr_hint(Stage, name)


#: Surface roughness (WP-0502) goes **last** in every plan that carries it.
#: It is the most degenerate correction in the package: a low-angle intensity
#: depression is exactly what an inflated Biso/ADP, a shrunken scale or a
#: flexible background will each happily absorb, and unlike extinction it has no
#: |F|²-dependence to distinguish it.  Letting the structure settle first leaves
#: roughness only its own (θ-only, low-angle-weighted) signature to fit — and
#: whatever is left over is what the ROUGHNESS_ABSORPTION guard measures.
#:
#: The glob matches only instruments that declared a block, so it is safe in
#: any plan (same property as the preferred-orientation stage).  The seed lifts
#: the softplus strength parameter (Suortti ``b``, Pitschke ``c``) off the zero
#: floor where dp/du → 0; 0.3 is chosen from the measured sensitivity peak of
#: the Suortti model, which sits near b ≈ 0.17 for data from 5° 2θ and b ≈ 0.46
#: from 20° — not at a token 1e-3, which for ``b`` is not merely a dead
#: *internal* gradient but a genuinely dead *correction* (see
#: RoughnessSuortti: both b → 0 and b → ∞ are the identity).
_ROUGHNESS_STAGE = (
    Stage("roughness", ["instrument.geometry.surface_roughness.*"], seed=0.3),
)


#: Additive background peaks (:class:`~rietx.schemas.instrument.HumpComponent`)
#: are freed **after the profile and before the structure**, in
#: ``mccusker_structural`` only.
#:
#: The glob matches nothing unless the caller declared a peak, so the stage is
#: safe in any plan — the preferred-orientation and roughness property.  What
#: decides *where* is which mistake it is preventing.  A hump the background
#: cannot describe is absorbed by whatever can, and the candidates are the
#: displacement parameters and the scale, so the hump should already be
#: described when ``biso`` opens — which puts this stage before
#: ``coordinates``.  Stated as an ordering argument rather than as a measured
#: effect on purpose: on the BT-1 neutron case
#: (:class:`~rietx.schemas.instrument.HumpComponent` has the table) declaring
#: the peak did **not** move that phase's first Biso back to a physical value,
#: and the stage
#: sits here because this is the order that gives it the chance, not because
#: the chance was measured to be taken.
#:
#: **The stage is not free on an instrument with no peak.**  Staging is
#: cumulative, so an inert stage still re-solves everything already freed and
#: re-emits that solve's guard diagnostics: measured on the P-spline arm of the
#: case above, the answer is unchanged to five figures while the
#: ``HIGH_CORRELATION`` count goes 110 → 145.  The ``_ROUGHNESS_STAGE``
#: precedent above pays the same price for the same reason.
#:
#: Not in ``scale_bkg``, which is stage 1: a free *position* over a pattern
#: whose peaks have not been placed yet is a peak hunting for whatever misfit
#: the wrong zero and cell are producing.  By this stage the widths and
#: positions are settled, which is what makes a broad feature distinguishable
#: from a mis-modelled reflection at all — and the
#: ``HUMP_TOO_NARROW`` guard is only meaningful once the resolution
#: function it compares against has been refined.
#:
#: Only ``mccusker_structural``, deliberately.  The profile-only plans have no
#: displacement parameter for a hump to bias, so a stage there would buy a
#: solve for nothing; and the lab plans' users declare their own peaks
#: alongside their own stages.  **No plan ever *adds* a peak** — the glob frees
#: what the caller declared and nothing more, which is the whole safety
#: property of a feature whose parameters would otherwise improve any Rwp.
_EXTRA_COMPONENT_STAGE = (
    Stage("extra_components", ["instrument.extra_components.*"]),
)


@dataclass
class RefinementPlan:
    stages: list[Stage]
    correlation_guard: float = 0.98
    #: the tolerance every stage but the last runs at, unless that stage
    #: declares its own :attr:`Stage.ftol`.  ``None`` = the solver default
    #: (1e-9) everywhere, which is what every fit before WP-1123 did and what
    #: it still does, bit for bit.  See :meth:`stage_ftols` for the rule and
    #: :data:`INTERMEDIATE_FTOL` for what the number is and costs.
    intermediate_ftol: float | None = INTERMEDIATE_FTOL

    def stage_ftols(self) -> list[float | None]:
        """The tolerance each stage runs at, in order — the one authority.

        Both runners ask this rather than reading ``stage.ftol``
        (``Refinement._run_stage`` through ``fit``, ``MultiRefinement.fit``),
        because the answer needs a fact no stage has: **whether it is the
        last**.  A plan is the only object that knows, so the rule lives here
        and is applied once per fit instead of restated per call site.

        Three inputs, in precedence order: a stage's own ``ftol`` wins; the
        last stage takes the solver default, because it is the one that
        produces the answer; everything else takes
        :attr:`intermediate_ftol`.

        A single-stage plan is therefore all endpoint and nothing is loosened
        — which is the right reading of a warm series pattern collapsed to one
        stage, and of the indexing validation fit, neither of which has a
        successor to seed.
        """
        last = len(self.stages) - 1
        return [s.ftol if s.ftol is not None
                else (None if i == last else self.intermediate_ftol)
                for i, s in enumerate(self.stages)]

    def __getattr__(self, name: str):
        if name in _PYDANTIC_SURFACE:
            raise _ask_the_mirror(name, "RefinementPlan",
                                  "rietx.PlanSpec.from_plan(plan)")
        raise _dataclass_attr_hint(RefinementPlan, name)

    @classmethod
    def mccusker_default(cls) -> "RefinementPlan":
        """Default staged plan for a Rietveld run (McCusker et al., 1999)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def mccusker_structural(cls) -> "RefinementPlan":
        """The McCusker order continued into the structural parameters:
        atomic coordinates once the profile is stable, then displacement
        parameters.  Coordinates refine as site-symmetry DOFs
        (``phases.*.atoms.*.dof.*`` — WP-0301 constraint block; a special
        position contributes only its allowed directions, a fully fixed one
        contributes none, so the glob is always safe).  The displacement
        stage frees ``biso`` on isotropic sites and the ``adp.*`` patterns on
        anisotropic ones, whichever each site declares.  Kept separate from
        :meth:`mccusker_default` so profile-only workflows never free
        structural parameters by accident."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            *_EXTRA_COMPONENT_STAGE,
            Stage("coordinates", ["phases.*.atoms.*.dof.*"]),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
            # March-Dollase preferred orientation (WP-0307) turns on *after* the
            # displacement stage: r, occupancies and ADPs all rescale intensity
            # in Q-dependent ways, so letting the structure settle first leaves
            # PO with its own axis-angle signature to fit.  The glob matches only
            # phases that declared a PO block; r ≡ 1 is the identity, so a start
            # from 1.0 perturbs nothing until the data pull it off.
            Stage("preferred_orientation", ["phases.*.preferred_orientation.r"]),
            # secondary extinction (WP-0506) comes *after* the displacement
            # stage on purpose: ext, Biso and the ADPs all attenuate high-Q
            # intensity, so letting the structure/ADPs settle first leaves
            # extinction with only its (different, low-angle-weighted)
            # signature to fit.  The coefficient starts at exactly 0 on the
            # softplus floor, so the stage seeds it to lift TRF off the zero.
            Stage("extinction", ["phases.*.extinction"], seed=1e-3),
            *_ROUGHNESS_STAGE,
        ])

    @classmethod
    def lab_bragg_brentano(cls) -> "RefinementPlan":
        """Lab flat-plate plan: adds sample displacement (with zero), then the
        Kα2/Kα1 intensity ratio and FCJ axial-divergence parameters last —
        the McCusker ordering extended by the v0.2 lab-instrument physics.
        Sample transparency stays fixed (free it explicitly for low-absorbing
        samples)."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero_disp", ["instrument.zero_shift",
                                "instrument.geometry.sample_displacement"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("lines_axial", ["instrument.source.lines.*.weight",
                                  "instrument.geometry.axial_sl",
                                  "instrument.geometry.axial_hl"]),
            *_ROUGHNESS_STAGE,
        ])

    @classmethod
    def lab_calibrate(cls) -> "RefinementPlan":
        """Calibrate the instrument on a **certified line-profile standard**
        (NIST SRM 660c LaB6): the certified cell is *held fixed* — that is
        what pins the dispersion axis and decorrelates the otherwise-sloppy
        {zero (const), displacement (cosθ), cell (tanθ)} triple — while zero,
        displacement, the resolution function, the Kα2 ratio and the axial
        ratios refine.  Export the result with ``save_instrument_profile``;
        refine unknowns against it with the ``lab_sample_refine`` plan.

        **No roughness stage here, deliberately.**  A certified line-profile
        standard is a carefully prepared specimen, and this plan's job is to
        measure the *goniometer*; freeing a mount property against a fixed
        certified cell would let specimen preparation contaminate the
        calibration that every later sample inherits.  ``save_instrument_profile``
        strips any roughness block for the same reason."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("zero_disp", ["instrument.zero_shift",
                                "instrument.geometry.sample_displacement"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
            Stage("lines_axial", ["instrument.source.lines.*.weight",
                                  "instrument.geometry.axial_sl",
                                  "instrument.geometry.axial_hl"]),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
        ])

    @classmethod
    def lab_sample_refine(cls) -> "RefinementPlan":
        """Refine a *sample* against a **calibrated, frozen instrument**
        (the calibrate-on-standard → freeze → refine-sample workflow; see
        ``rietx.io.instrument_profile``).

        Only sample-side parameters move: scale/background, specimen
        displacement (a property of the mount, not the instrument), cell,
        the four sample broadening terms (Lorentzian + Gaussian size/strain
        — the instrument U V W X Y stay at their calibrated values), then
        Biso.  Never frees zero, axial ratios or emission-line weights."""
        return cls(stages=[
            Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
            Stage("disp", ["instrument.geometry.sample_displacement"]),
            Stage("cell", ["phases.*.cell.*"]),
            # Stephens anisotropic strain (WP-0503) is freed *in* the
            # sample-broadening stage, not after it.  A microstrain block locks
            # lor_strain — its isotropic direction is that same column — so a
            # later stage would leave the isotropic width unrefined right up to
            # the moment four correlated patterns are turned on at once, which
            # is the worst possible starting point.  The glob matches only
            # phases that declared a block, and the seed puts an all-zero one
            # on the isotropic ray (Λ ∝ √Σ has unbounded slope at Σ = 0).
            Stage("sample_profile", ["phases.*.lor_size", "phases.*.lor_strain",
                                     "phases.*.gauss_size", "phases.*.gauss_strain",
                                     "phases.*.microstrain.dof.*"],
                  strain_seed=1000.0),
            Stage("biso", list(_DISPLACEMENT_GLOBS)),
            *_ROUGHNESS_STAGE,
        ])

    @classmethod
    def profile_only(cls) -> "RefinementPlan":
        """Le Bail-style plan: no structural parameters exist to free."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])

    @classmethod
    def pawley_default(cls) -> "RefinementPlan":
        """Pawley whole-pattern plan: cell + profile, same order as
        :meth:`profile_only`.  The per-hkl intensities are *not* named globs —
        they are refined as an implicit block every stage (see
        ``model.forward.PawleyBlock``), so no ``turn_on`` frees them."""
        return cls(stages=[
            Stage("bkg", ["instrument.background.*"]),
            Stage("zero", ["instrument.zero_shift"]),
            Stage("cell", ["phases.*.cell.*"]),
            Stage("profile_w", ["instrument.profile.w"]),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"]),
        ])


class _PlanFactory:
    """One entry of :data:`PLAN_PRESETS`: the builder, and ``.stages`` refusing.

    The registry maps a name to the function that *builds* the plan, never to a
    plan, because :class:`RefinementPlan` is a mutable dataclass meant to be
    edited — a shared instance in a module-level dict would let one caller's
    edit reach every later caller.  That is the right trade and it has a cost:
    ``PLAN_PRESETS["mccusker_default"].stages`` is the obvious keystroke and it
    answered ``'function' object has no attribute 'stages'``, which names
    neither the registry nor the call (WP-1110 item 4).

    So the value is a callable that says so.  ``functools.update_wrapper``
    carries the builder's ``__name__``, ``__doc__``, ``__module__`` and
    ``__wrapped__``, so ``help()``, ``inspect.signature`` and ``inspect.getdoc``
    reach the classmethod exactly as before — the round behind this WP had an
    agent leave for the source because a wrapper *without* ``wraps`` showed it
    the wrapper instead of the thing.
    """

    def __init__(self, build):
        functools.update_wrapper(self, build)
        self._build = build

    def __call__(self) -> RefinementPlan:
        return self._build()

    def __repr__(self) -> str:
        return f"<plan preset {self.__name__!r}: call it to build a RefinementPlan>"

    def __getattr__(self, name: str):
        if name in {f.name for f in dataclasses.fields(RefinementPlan)}:
            raise AttributeError(
                f"PLAN_PRESETS[{self.__name__!r}] is the function that builds "
                f"the plan, not the plan, so it has no {name!r}: call it — "
                f"PLAN_PRESETS[{self.__name__!r}]() — and read .{name} off "
                "what comes back. Each call returns a fresh RefinementPlan, "
                "because a plan is a mutable dataclass you are meant to edit.")
        raise AttributeError(name)


PLAN_PRESETS = {
    name: _PlanFactory(build) for name, build in {
        "mccusker_default": RefinementPlan.mccusker_default,
        "mccusker_structural": RefinementPlan.mccusker_structural,
        "lab_bragg_brentano": RefinementPlan.lab_bragg_brentano,
        "lab_calibrate": RefinementPlan.lab_calibrate,
        "lab_sample_refine": RefinementPlan.lab_sample_refine,
        "profile_only": RefinementPlan.profile_only,
        "pawley_default": RefinementPlan.pawley_default,
    }.items()
}


def resolve_plan(plan: "RefinementPlan | PlanSpec | str", mode: Mode) -> RefinementPlan:
    """A preset name, a plan or its serializable mirror, as a concrete plan.

    ``"mccusker_default"`` is the name every caller passes without thinking, and
    it means something different per mode: Le Bail has no structure to refine so
    it becomes ``profile_only``, and Pawley refines its intensities off-table so
    it becomes ``pawley_default``.  That mapping decides what actually ran, so it
    lives here beside the registry rather than in each caller — four now want it
    (``Refinement.fit``, ``sequential``, ``agent``, and the GUI, which must show
    a user the stages that a run *will* have before it starts).

    **A ``PlanSpec`` is converted here rather than tolerated** (WP-1110 item 15).
    It is what a project file, a history header and an agent request each hold,
    so a caller reading one back and passing it to ``fit`` is the ordinary
    thing to do — and until this line it *appeared to work*, because
    ``PlanSpec``/``StageSpec`` share every field name with the dataclasses and
    the plan is only ever read.  Measured on this tree: a five-stage
    ``profile_only`` fit driven by a ``PlanSpec`` returned a bit-identical
    answer to the same fit driven by the plan.  That is an accident of two
    types agreeing, not a contract, and it ends the first time a stage grows a
    field or a consumer calls a method; converting states it instead.
    ``PlanSpec._accept_the_dataclass`` is this crossing in the other direction.
    """
    if isinstance(plan, PlanSpec):
        return plan.to_plan()
    if not isinstance(plan, str):
        return plan
    name = plan
    if name == "mccusker_default" and mode == "lebail":
        name = "profile_only"
    elif name == "mccusker_default" and mode == "pawley":
        name = "pawley_default"
    try:
        return PLAN_PRESETS[name]()
    except KeyError:
        raise ValueError(f"unknown plan preset {plan!r}; "
                         f"available: {sorted(PLAN_PRESETS)}") from None


@dataclass(frozen=True)
class PlanInfo:
    """What a preset is for, in the words a chooser needs.

    Beside the registry rather than in a UI, a docs page or a capabilities
    module, because every one of those consumers needs the same four facts and
    the presets are what they describe: a preset added without a row here is a
    preset nobody can be told when to use.  ``tests/test_params_surface.py``
    fails on a missing or extra key (the WP-0602 registry-meta-test pattern).

    ``modes`` lists the intensity modes the plan is meaningful in — plural,
    because ``profile_only`` is both the Le Bail plan and the way to fit a
    profile in Rietveld mode without touching the structure.
    """

    title: str
    description: str
    modes: tuple[Mode, ...]
    when_to_use: str


#: Per-preset guidance.  Keys are held in bijection with PLAN_PRESETS by a test.
PLAN_INFO: dict[str, PlanInfo] = {
    "mccusker_default": PlanInfo(
        title="Standard (profile only)",
        description=(
            "The IUCr-guideline turn-on order (McCusker et al., 1999): scale + "
            "background, zero shift, cell, then the profile widths. Leaves every "
            "structural parameter fixed."),
        modes=("rietveld",),
        when_to_use=(
            "The default first fit of a known structure, and the plan to reach "
            "for whenever a structural refinement has gone wrong — it converges "
            "the parameters everything else depends on."),
    ),
    "mccusker_structural": PlanInfo(
        title="Standard + structure",
        description=(
            "The standard order continued into the structure: coordinates as "
            "site-symmetry DOFs, then displacement parameters (biso or the "
            "anisotropic patterns, whichever each site declares), then preferred "
            "orientation, extinction and surface roughness where declared."),
        modes=("rietveld",),
        when_to_use=(
            "A structure worth refining against data good enough to carry it. "
            "Run the profile-only plan first if the fit is not already close."),
    ),
    "lab_bragg_brentano": PlanInfo(
        title="Lab diffractometer (one pass)",
        description=(
            "Bragg-Brentano flat-plate order: the sample displacement and "
            "transparency corrections join the zero shift, and the axial "
            "(Finger-Cox-Jephcoat) apertures refine with the widths."),
        modes=("rietveld",),
        when_to_use=(
            "A single lab pattern with no instrument calibration to hand — it "
            "refines specimen and instrument effects together, so read the "
            "correlation guards before quoting a width."),
    ),
    "lab_calibrate": PlanInfo(
        title="Lab: calibrate on a standard",
        description=(
            "Step 1 of the two-step lab workflow. Refines the instrument "
            "profile and the position corrections on a line-position standard "
            "**with its certified cell held fixed** — which is what decorrelates "
            "zero shift, displacement and cell."),
        modes=("rietveld",),
        when_to_use=(
            "On a standard (LaB6, Si, corundum), once per instrument "
            "configuration. Follow it with save_instrument_profile."),
    ),
    "lab_sample_refine": PlanInfo(
        title="Lab: refine a specimen",
        description=(
            "Step 2 of the two-step lab workflow. The instrument profile is "
            "held at its calibrated values and only the sample's own broadening "
            "(size and strain, isotropic or Stephens-anisotropic) refines, "
            "instrument ⊕ sample."),
        modes=("rietveld",),
        when_to_use=(
            "Any specimen measured on a calibrated instrument, and the only "
            "plan whose size/strain numbers mean what they say — an "
            "uncalibrated fit absorbs the instrument into them."),
    ),
    "profile_only": PlanInfo(
        title="Cell + profile, no structure",
        description=(
            "Background, zero shift, cell and widths only. In Le Bail mode the "
            "per-hkl intensities are extracted by iterated partitioning instead "
            "of being computed from a structure."),
        modes=("lebail", "rietveld"),
        when_to_use=(
            "A known cell with an unknown or untrusted structure — indexing "
            "checks, extracted intensities for structure solution, or a "
            "cell/width measurement you want independent of any structural model."),
    ),
    "pawley_default": PlanInfo(
        title="Pawley whole-pattern",
        description=(
            "The same order as the Le Bail plan, but the per-hkl intensities "
            "are refined *inside* the least squares, so they carry esds. "
            "Overlapped groups are conditioned by an equal-split restraint and "
            "come back flagged rather than confidently split."),
        modes=("pawley",),
        when_to_use=(
            "Extracted intensities that need uncertainties — feeding structure "
            "solution or a peak-shape study. Read PAWLEY_OVERLAP_UNRESOLVED "
            "before using an intensity from an overlapped group."),
    ),
}


@dataclass(frozen=True)
class GuardFinding:
    """One guard hit, as data: which parameters, which number, which code.

    Until v1.0 these were formatted strings, and every consumer that needed a
    part of one had to take it apart again — ``refine._guard_diagnostics`` did
    ``msg.split(" ")[0]`` to recover a path, which silently produced *nothing*
    for a correlation (two paths, no leading one) and so left
    ``Diagnostic.where`` empty on the one finding a client most wants to click.
    A GUI panel reads :attr:`paths` and :attr:`value`; nobody regexes prose.

    ``__str__`` is today's formatted text, byte for byte, because the rendered
    string is what the diagnostics' messages are built from and those are a
    published surface.  Every format string that used to be written at three
    different call sites now lives in one constructor here.

    ``code`` is an **open** vocabulary of strings, deliberately not a ``Literal``
    closed over today's six: WP-1028 adds guards (a stage returning ``converged``
    at Rwp = 7225 %, a ``max_iter`` outcome, an hkl-range refusal), and a closed
    type would have to be reopened for each.  It is the *same* vocabulary as
    ``Diagnostic.code`` rather than a second one — the finding now carries the
    code, so the mapping from guard to diagnostic is data instead of six
    hand-written loops.
    """

    code: str
    paths: tuple[str, ...]
    #: the headline number — ρ, block R², a min eigenvalue, the worst σ²(M),
    #: the worst Γ_G².  ``None`` where the finding has no number (a parameter
    #: at its bound).
    value: float | None
    #: rendered form, identical to the pre-v1.0 list entry
    message: str
    #: a clause a *diagnostic* appends to its own sentence, already rendered.
    #: Written only by :meth:`at_bound` and read only where ``BOUND_HIT``
    #: builds its ``Diagnostic`` (WP-1434 gives that finding evidence to
    #: carry; WP-1076 wants both ends of a new field named).  It is
    #: deliberately not part of :meth:`__str__`, which is the pre-v1.0 text
    #: byte for byte and is what the other diagnostics are built from.
    detail: str = ""

    def __str__(self) -> str:
        return self.message

    # -- constructors: one place per format string ----------------------
    @classmethod
    def correlation(cls, a: str, b: str, rho: float) -> "GuardFinding":
        return cls("HIGH_CORRELATION", (a, b), float(rho),
                   f"{a} ~ {b} (ρ={rho:+.3f})")

    @classmethod
    def at_bound(cls, path: str, cos: float | None = None,
                 gap_over_esd: float | None = None) -> "GuardFinding":
        """``cos`` is the evidence that the limit carried load, not that the
        value sits near one — see :func:`bound_findings`.  Both are ``None``
        on the fallback path, where no solve stood behind the test, and the
        finding then renders exactly as it did before WP-1434.
        """
        if cos is None:
            return cls("BOUND_HIT", (path,), None, path)
        gap = ("" if gap_over_esd is None
               else f", {gap_over_esd:.1e} esd from the limit")
        return cls("BOUND_HIT", (path,), float(cos), path,
                   detail=f" (ρ={cos:+.3f}{gap})")

    @classmethod
    def background_absorption(cls, path: str, r2: float) -> "GuardFinding":
        return cls("BACKGROUND_ABSORPTION", (path,), float(r2),
                   f"{path} (R²={r2:.2f})")

    @classmethod
    def roughness_absorption(cls, path: str, r2: float) -> "GuardFinding":
        return cls("ROUGHNESS_ABSORPTION", (path,), float(r2),
                   f"{path} (R²={r2:.2f})")

    @classmethod
    def nonpositive_adp(cls, site: str, min_eigenvalue: float) -> "GuardFinding":
        return cls("ADP_NOT_POSITIVE_DEFINITE", (site,), float(min_eigenvalue),
                   f"{site} (min eigenvalue {min_eigenvalue:+.2e} Å²)")

    @classmethod
    def nonpositive_strain(cls, path: str, n_bad: int, n_total: int,
                           worst: float, hkl: str) -> "GuardFinding":
        return cls("STEPHENS_STRAIN_NOT_POSITIVE", (path,), float(worst),
                   f"{path} ({n_bad} of {n_total} reflections, "
                   f"worst σ²(M) {worst:+.2e} at {hkl})")

    @classmethod
    def unsupported_resolution(cls, freed: tuple[str, ...], share: float,
                               n_lorentzian: int, n_total: int) -> "GuardFinding":
        names = ", ".join(path.rsplit(".", 1)[1].upper() for path in freed)
        return cls("RESOLUTION_UNCONSTRAINED", freed, float(share),
                   f"{names} refined on a predominantly Lorentzian pattern "
                   f"(Γ_L exceeds Γ_G at {n_lorentzian} of {n_total} fitted "
                   f"points; the Gaussian carries {share:.0%} of the width)")

    @classmethod
    def flat_direction(cls, a: str, b: str, rho: float) -> "GuardFinding":
        return cls("FLAT_DIRECTION", (a, b), float(rho),
                   f"{a} ~ {b} (ρ={rho:+.3f}; the data does not separate them)")

    @classmethod
    def large_biso(cls, path: str, biso: float, b_melt: float) -> "GuardFinding":
        return cls("BISO_UNUSUALLY_LARGE", (path,), float(biso),
                   f"{path} (B = {biso:.2f} Å², {biso / b_melt:.1f}× the "
                   f"{b_melt:.2f} Å² Lindemann melting bound for this cell)")

    @classmethod
    def nonpositive_resolution(cls, n_bad: int, n_total: int, worst: float,
                               two_theta: float) -> "GuardFinding":
        return cls("RESOLUTION_NOT_POSITIVE",
                   ("instrument.profile.u", "instrument.profile.v",
                    "instrument.profile.w"),
                   float(worst),
                   f"the Caglioti resolution function ({n_bad} of {n_total} "
                   f"fitted points, worst Γ_G² {worst:+.2e} deg² at "
                   f"{two_theta:.3f}° 2θ)")

    @classmethod
    def narrow_hump(cls, path: str, fwhm: float, gamma_inst: float,
                               position: float) -> "GuardFinding":
        ratio = fwhm / gamma_inst if gamma_inst > 0.0 else float("inf")
        return cls("HUMP_TOO_NARROW", (path,), float(ratio),
                   f"{path} (FWHM {fwhm:.3f}° = {ratio:.1f}× the instrumental "
                   f"{gamma_inst:.3f}° at {position:.3f}° 2θ)")


@dataclass
class GuardReport:
    """The guards a stage tripped, grouped by kind — see :class:`GuardFinding`.

    The six *finding* field names from v0.2 are unchanged; what they hold is
    findings rather than strings.  ``str(finding)`` is the old entry, so a
    consumer that only ever printed them needs no change.
    ``nonpositive_resolution``, ``large_biso``, ``unsupported_resolution`` and
    ``flat_directions`` are the eighth to eleventh — ``narrow_humps`` (WP-1103)
    is the seventh — added by WP-1311; their
    writers are :func:`check_resolution_positive`, :func:`check_biso_plausible`,
    :func:`check_resolution_supported` and the correlation loop in
    :func:`check_guards`.

    ``measured_background_absorption`` is the one field that is **not**
    findings, and it is here rather than beside them so that the number a
    report quotes and the bit a guard fires on come from one measurement
    (WP-1055).  It carries every screened (path, R²) pair the block projection
    produced — the guard keeps those over
    :data:`BACKGROUND_ABSORPTION_GUARD` as ``background_correlations``, and
    :class:`~rietx.schemas.results.Identifiability` carries all of them onto
    the result, because a fired/not-fired bit is a verdict and 0.46-vs-0.08 is
    evidence.

    The three ``measured_*`` fields after it (WP-1056) are the same
    discipline for the parameter-space evidence: ``measured_top_correlations``
    is read from the same matrix in the same call as ``high_correlations``,
    ``measured_soft_modes`` from the same final Jacobian, and
    ``measured_exchangeability`` from one extra evaluate-only Jacobian at the
    converged values (built only on the answer-producing stage — the caller
    passes ``scan_exchangeability``).  They hold the
    :mod:`~rietx.schemas.results` rows verbatim; no guard thresholds them,
    the report does.
    """

    high_correlations: list[GuardFinding] = field(default_factory=list)
    at_bounds: list[GuardFinding] = field(default_factory=list)
    # structural parameters the background block could largely reproduce —
    # the background-eats-the-structure failure mode, measured as a multiple
    # correlation R² rather than a pairwise ρ (see check_guards)
    background_correlations: list[GuardFinding] = field(default_factory=list)
    # anisotropic displacement tensors that are no longer ellipsoids
    nonpositive_adps: list[GuardFinding] = field(default_factory=list)
    # phases whose Stephens strain coefficients have left the physical cone
    nonpositive_strain: list[GuardFinding] = field(default_factory=list)
    # the instrument resolution function dipping below zero somewhere in the
    # fitted range — a variance the forward model then clamps to a floor
    # (see check_resolution_positive)
    nonpositive_resolution: list[GuardFinding] = field(default_factory=list)
    # isotropic displacement parameters past the Lindemann melting bound for
    # their own cell (see check_biso_plausible)
    large_biso: list[GuardFinding] = field(default_factory=list)
    # the Gaussian resolution terms refined on a pattern whose peaks are
    # predominantly Lorentzian, where they are not determined
    # (see check_resolution_supported)
    unsupported_resolution: list[GuardFinding] = field(default_factory=list)
    # pairs whose |ρ| is 1.000 to the precision the report states it in — a
    # rank statement about the data, reported beside the correlation rather
    # than instead of it (see FLAT_DIRECTION_RHO)
    flat_directions: list[GuardFinding] = field(default_factory=list)
    # two-way surface-roughness degeneracy (WP-0502): either roughness is not
    # identifiable from this data, or a displacement parameter is now hiding
    # in it.  Same block-R² statistic as background_correlations.
    roughness_correlations: list[GuardFinding] = field(default_factory=list)
    # declared background peaks that are no longer describing a *broad* feature
    # — a fitted width approaching the instrumental resolution is a reflection
    # being eaten, not diffuse scattering (see check_hump_width)
    narrow_humps: list[GuardFinding] = field(default_factory=list)
    # not findings: the full screened (path, R²) table the background guard
    # decided from — see the class docstring
    measured_background_absorption: dict[str, float] = field(default_factory=dict)
    #: R^2 of each structural column on the span of the **declared sharp
    #: peaks** (WP-1103) — the same statistic as the field above, asked of
    #: the seam's other member.  Reported, never thresholded: nothing has
    #: measured what separates a healthy declared peak from a parasitic one,
    #: and the 0.25 above was measured for background blocks.  Empty when no
    #: peak component is declared or freed.
    measured_extra_peak_absorption: dict[str, float] = field(default_factory=dict)
    # not findings either (WP-1056): the parameter-space evidence, as
    # schemas.results rows — CorrelationPair / SoftMode / ExchangeRow
    measured_top_correlations: list = field(default_factory=list)
    measured_soft_modes: list = field(default_factory=list)
    measured_exchangeability: list = field(default_factory=list)

    def findings(self) -> list[GuardFinding]:
        """Every finding, in the order the diagnostics are emitted in
        (``refine._guard_diagnostics``): narrow peaks come *before* the
        background/roughness absorption findings, matching that loop order.

        **Every** ``list[GuardFinding]`` field reaches this list, which
        ``tests/test_capabilities.py`` holds true by ``dataclasses.fields``
        rather than by a second hand-written order: a new field that a writer
        fills and this method drops is invisible — the report carries it, the
        diagnostics carry it, and only this projection is empty (WP-1076's
        rule, since a declared name whose reader is missing fails no test)."""
        return [*self.high_correlations, *self.at_bounds, *self.nonpositive_adps,
                *self.nonpositive_strain, *self.unsupported_resolution,
                *self.flat_directions, *self.large_biso,
                *self.nonpositive_resolution, *self.narrow_humps,
                *self.background_correlations, *self.roughness_correlations]


#: R² beyond which the background block is reported as able to imitate a
#: structural parameter (see ``optimize.statistics.background_absorption``).
#: Measured separation: sane backgrounds (Chebyshev-6, the default 8°-knot
#: penalized spline) sit at 0.01-0.03 even against broad peaks, while a
#: 1°-knot unpenalized spline reaches 0.46.
BACKGROUND_ABSORPTION_GUARD = 0.25

#: R² beyond which surface roughness and the displacement parameters are
#: reported as mutually substitutable (see
#: ``optimize.statistics.roughness_absorption``, which projects out the scale
#: and background first — without that every number saturates near 0.96).
#: Measured on a synthetic large-cell lab pattern, varying only the low-angle
#: cutoff: R²(Suortti b) = 0.06 with the fit reaching 7° 2θ (20 reflections
#: below 40°), 0.62 from 15°, then 0.91 / 0.93 / 0.95 from 20° / 30° / 45° —
#: the crossing happens exactly as the low-angle reflections that give the
#: depression its lever arm drop out of range.  0.9 sits in that gap.
#:
#: Deliberately looser than BACKGROUND_ABSORPTION_GUARD: a background imitating
#: a peak is always pathological, whereas roughness genuinely *is* a Q-dependent
#: intensity trend, so partial overlap with the ADPs is expected physics and
#: only near-total overlap is a finding.
ROUGHNESS_ABSORPTION_GUARD = 0.9


#: The multiple of the **instrumental** FWHM at its own position below which a
#: declared background peak is reported as not describing a background feature
#: (:func:`check_hump_width`).
#:
#: This is the physical content of :class:`~rietx.schemas.instrument.HumpComponent`,
#: not a numerical guard.  A free position, height and width *is* a Bragg peak
#: with no cell and no structure factor behind it, and three of those will
#: improve any Rwp — which this package's own rule ("a new correction ships with
#: a record field or a diagnostic that states what it changed, never an Rwp
#: comparison as its evidence") says is no evidence at all.  What makes the term
#: a background term is that its width comes from *disorder* rather than from
#: the goniometer, and disorder is many times the resolution.
#:
#: 4 is chosen from the corpus rather than from taste.  The measured case this
#: feature exists for is a 5.81° FWHM feature at 14.4° 2θ on NIST BT-1, where
#: the instrumental lines are 0.25-0.30° — a factor of ~20, so 4 leaves a
#: margin of 5× to the real thing while still excluding everything
#: resolution-limited by a wide margin of its own.  1.5 would not: TCH mixing
#: alone moves the total FWHM by tens of percent, so a 1.5× "hump" is a
#: reflection.
#:
#: **It rests on one case, and that is the weakest joint here** (WP-1102).  No
#: paper states a width ratio separating a diffuse feature from a reflection, so
#: this is a measurement rather than a quotation — of a single specimen.  The
#: repo's rule is that a threshold is quoted or measured and never *tuned*, and
#: this one is measured, but a sample of one cannot say where inside the 3-5
#: band the boundary really sits, only that ~20 is comfortably above it and 1.5
#: is below.  What would move it is a width ladder over several specimens
#: carrying known diffuse features, which has not been run; what would settle it
#: is a published ratio, which does not appear to exist.  Read a firing
#: accordingly: at 4.3× it is a weak statement and at 1.2× a strong one, and the
#: diagnostic carries ``value`` as the measured multiple so a reader can make
#: that distinction rather than taking the boundary as sharp.
#:
#: **Why a guard and not a bound.** The threshold is a function of U, V, W, X, Y
#: *and* of the peak's own position, so it is not a box the solver can be handed
#: — the :data:`STEPHENS_CONE_TOL` situation, and resolved the same way: report,
#: never refuse.  A firing means "these background peaks are not quotable", and
#: the honest fix is a model change (a second phase, a size-broadened phase) not
#: a tighter number.  The static half of the pair is
#: :data:`~rietx.schemas.instrument.HUMP_FWHM_MIN`, which is a
#: ``MARCH_R_MIN``-style pole floor and nothing more — it cannot express this
#: bound, because a schema cannot see the resolution function.
HUMP_MIN_WIDTH_MULT = 4.0


def check_hump_width(table, model) -> list[GuardFinding]:
    """Declared background peaks whose fitted width is not a *background* width.

    Reports every peak with

        Γ_peak  <  HUMP_MIN_WIDTH_MULT · Γ_instrument(2θ₀)

    with Γ_instrument the TCH total FWHM of the resolution function alone
    (``CompiledModel.instrument_fwhm_deg`` — instrument U,V,W,X,Y, no phase size
    or strain, because the question is how narrow a *real* reflection can be at
    that angle).

    Evidence, never refusal, and never a seed: nothing in this package adds a
    background peak on its own.  ``auto_background`` sizes the polynomial or the
    spline and is untouched by this feature; the *diagnostics* may say a hump is
    present (``background.diagnostics``' ``amorphous_hump_score``) but declaring
    a peak stays the caller's act, because a model that grows its own free peaks
    is the failure this guard exists to make visible.

    Needs the compiled model for the frozen peak paths, so it returns ``[]``
    without one — the ``check_stephens_positive`` convention one function up.

    **Abstains where the resolution is not evaluable.**  Γ_instrument is only a
    real width while the Caglioti quadratic Γ_G² = U·tan²θ + V·tanθ + W stays
    positive; a schema-legal but ill-conditioned refinement can drive it
    negative at some angle, and ``gaussian_fwhm`` then clamps Γ_G² to the
    numerical floor ``caglioti._MIN_GAMMA_G2`` (≈ (1e-4°)²) to keep the forward
    model's √ real.  A background peak sitting at such an angle would be judged
    against a resolution of ~1e-4° — a threshold any real width clears, so the
    guard would silently *endorse* a peak it cannot actually assess.  That is a
    guess, and this package's rule is report-or-abstain, never guess: when the
    total Γ_instrument has collapsed to the floor (both the Gaussian quadratic
    floored *and* no Lorentzian X/Y left to carry a physical width), the peak is
    skipped rather than passed.  The instrument model being unphysical at that
    angle is a separate, more fundamental defect and not this guard's to name.
    """
    from ..model.profiles.caglioti import _MIN_GAMMA_G2

    # Ten times the Γ_G² floor's own √ — a decade above the numerical floor
    # (1e-4°) and a decade below the finest real resolution (~1e-2° at a
    # synchrotron), so it fires only when nothing physical survived.
    resolution_floor = 10.0 * (_MIN_GAMMA_G2 ** 0.5)

    if model is None or not model.component_paths:
        return []
    values = {e.path: e.value for e in table.entries}
    out: list[GuardFinding] = []
    for pos_path, _height_path, fwhm_path in model.component_paths:
        position = values.get(pos_path)
        fwhm = values.get(fwhm_path)
        if position is None or fwhm is None:
            continue
        gamma = float(model.instrument_fwhm_deg(position, values))
        if gamma <= resolution_floor:
            # not evaluable here — abstain, do not endorse (see docstring)
            continue
        if fwhm < HUMP_MIN_WIDTH_MULT * gamma:
            out.append(GuardFinding.narrow_hump(
                fwhm_path, float(fwhm), gamma, float(position)))
    return out


def check_adp_positive_definite(table) -> list[GuardFinding]:
    """Anisotropic sites whose U tensor is not positive definite.

    An unconstrained U can leave the physical cone, and the resulting
    Debye-Waller factor *grows* without bound along the offending direction
    as |h| increases — the fit does not merely become wrong, it diverges at
    high Q.  The test runs on the stored CIF U^ij matrix rather than on
    U_cart: the two are related by a congruence, so by Sylvester's law of
    inertia the eigenvalue *signs* are the same and no cell is needed here
    (magnitudes would need one — see ``crystallography.adp``).
    """
    import numpy as np

    from ..crystallography.adp import min_eigenvalue

    values = {e.path: e.value for e in table.entries}
    sites: dict[str, list[float]] = {}
    for e in table.entries:
        m = _ADP_COMPONENT.match(e.path)
        if m:
            sites.setdefault(m.group(1), [np.nan] * 6)
            sites[m.group(1)][_U_ORDER[m.group(2)]] = values[e.path]
    out = []
    for base, u6 in sorted(sites.items()):
        if not np.isnan(u6).any() and min_eigenvalue(u6) <= 0.0:
            out.append(GuardFinding.nonpositive_adp(base, min_eigenvalue(u6)))
    return out


#: relative tolerance below which a σ²(M) counts as *on* the cone rather than
#: outside it (WP-0601).  The boundary is part of the physical set — σ² = 0 is
#: a direction with no strain broadening, not an impossible variance — and two
#: legitimate states land exactly there: the all-zero block (documented as the
#: exact no-broadening identity) and the optimum of an inequality-constrained
#: solve, which the bounded-LM driver drives onto the face by construction.
#: The tolerance is relative to the largest σ² in the same phase, because the
#: constrained solve and this guard reach σ² by different association orders
#: and disagree in the last bits.
STEPHENS_CONE_TOL = 1e-9


def check_stephens_positive(table, model) -> list[GuardFinding]:
    """Phases whose Stephens σ²(M) is **negative** on some fitted reflection.

    σ² is a variance, so a negative value is not a large anisotropy but an
    unphysical set of coefficients — the width law's √ has nothing to take and
    the model quietly reports zero broadening for that direction.  The
    constraint is a *cone* coupling all fifteen coefficients (like ADP positive
    definiteness), which is why it cannot be a box bound and has to be a guard
    under the default TRF driver.  ``solver="lm"`` can carry it as a linear
    inequality instead (``optimize/lm.py``), and then this guard falls silent
    because there is nothing left to report — which is the point.

    Zero is *inside* the physical set, and the test is one-sided for that
    reason: an all-zero block is the exact no-broadening identity, and a
    constrained optimum sits on the face by construction.  Before WP-0601 the
    test read ``σ² ≤ 0``, so an inert all-zero block reported itself as
    unphysical in every stage before the one that frees it.

    Tested on the frozen reflection list rather than over all integer hkl: the
    cone condition off the measured directions is unobservable, and flagging it
    would be a claim the data cannot support.  Needs the compiled model for
    that list, so it returns ``[]`` when none is supplied.
    """
    import numpy as np

    from ..crystallography.stephens import S_NAMES, sigma2_m
    from ..crystallography.symmetry import reflection_label

    if model is None:
        return []
    values = {e.path: e.value for e in table.entries}
    out: list[GuardFinding] = []
    for ip, cp in enumerate(model.phases):
        if cp.strain_monomials is None:
            continue
        base = f"phases.{ip}.microstrain"
        s = np.array([values.get(f"{base}.{n}", 0.0) for n in S_NAMES])
        sigma2 = np.asarray(sigma2_m(cp.strain_monomials, s))
        scale = max(float(np.max(np.abs(sigma2))), 1.0)
        bad = sigma2 < -STEPHENS_CONE_TOL * scale
        if bad.any():
            k = int(np.argmin(sigma2))
            hkl = reflection_label(cp.reflections.hklm[k])
            out.append(GuardFinding.nonpositive_strain(
                base, int(bad.sum()), len(sigma2), float(sigma2[k]), hkl))
    return out


#: The three Gaussian resolution terms, in the order a message names them.
#: Data rather than three literals, because the guard below, its message and
#: its test all have to mean the same three.
GAUSSIAN_RESOLUTION_PATHS = ("instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.w")


def check_resolution_supported(table, model) -> list[GuardFinding]:
    """U, V, W refined on a pattern whose peaks are predominantly Lorentzian.

    McCusker et al. (1999, J. Appl. Cryst. 32, 36) § Synchrotron states both
    the failure and its remedy: "because of the predominantly Lorentzian
    character of high-resolution data, refinement of the Lorentzian half-width
    parameters X and Y is usually straightforward, but unconstrained refinement
    of the Gaussian parameters U, V and W may lead to nonphysical results, or
    at worst, complete failure of the refinement.  In such cases, some kind of
    constraint function should be applied, or the parameters fixed at the
    instrumental values."

    So the question this asks is **not how wide the widths are**.  A size test
    would need a number, and the same paper rules one out in the next
    paragraph: for constant-wavelength neutron data the instrument dominates
    the profile and "U, V and W are easily determined by Rietveld refinement",
    so one threshold would have to be wrong for one technique or the other.
    What the paper makes testable is *character*, and "predominantly" is a
    comparison rather than a constant: the pattern is predominantly Lorentzian
    where Γ_L exceeds Γ_G, and predominantly so where that holds at more than
    half the fitted points.  No free constant enters, which is why this guard
    has no tunable of its own.

    Fires only on terms this table can actually **move**.  Held at a measured
    instrumental profile they are exactly what the paper prescribes, so
    reporting them would flag the remedy as the fault (the WP-1073 lesson: a
    map that suggests a force-fixed parameter is reporting its own blindness).

    ``moving_paths`` rather than ``free_paths``, which is the root CLAUDE.md
    rule and not a detail here.  A tie carries its coefficient on the free
    column it follows, so a ``U`` reaching the fit through
    :meth:`~rietx.refine.Refinement.tie` is refined on this pattern without
    ever being a column of θ.  It is exactly as undetermined as a free one and
    exactly as unquotable, so asking which entries are *columns* would let a
    tie buy silence.

    The instrument terms alone, no phase size or strain, for the reason
    ``CompiledModel.instrument_fwhm_deg`` gives.  Needs the compiled model for
    the fitted axis, so it returns ``[]`` without one.
    """
    import numpy as np

    from ..model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm

    if model is None:
        return []
    moving = set(table.moving_paths)
    freed = tuple(p for p in GAUSSIAN_RESOLUTION_PATHS if p in moving)
    if not freed:
        return []
    tt = np.asarray(model.tt, dtype=np.float64)
    if tt.size == 0:
        return []
    values = {e.path: e.value for e in table.entries}
    try:
        theta = 0.5 * tt
        g = np.asarray(gaussian_fwhm(theta, values["instrument.profile.u"],
                                     values["instrument.profile.v"],
                                     values["instrument.profile.w"]))
        lo = np.asarray(lorentzian_fwhm(theta, values["instrument.profile.x"],
                                        values["instrument.profile.y"]))
    except KeyError:
        return []

    lorentzian = lo > g
    if lorentzian.sum() * 2 <= tt.size:      # not predominantly, so no claim
        return []
    share = float(np.median(g / (g + lo))) if np.all(g + lo > 0.0) else 0.0
    return [GuardFinding.unsupported_resolution(
        freed, share, int(lorentzian.sum()), int(tt.size))]


#: |ρ| at or above which a correlated pair is reported as a **flat direction**
#: as well as a high correlation (WP-1311, issue #106).
#:
#: Derived from the report rather than chosen.  ``GuardFinding.correlation``
#: renders ρ to three decimals, so 0.9995 and 1.0 are the same number as far as
#: anything downstream can see, and 1 − 5e-4 is exactly the half-width of that
#: rounding.  The claim the finding makes is therefore one the report can
#: actually support: "ρ is 1.000 to the precision this message states it in".
#: A tighter bar would assert a distinction the message cannot print, a looser
#: one would call a genuine 0.997 degenerate.
FLAT_DIRECTION_RHO = 1.0 - 5e-4


#: Lindemann critical ratio ρ = √⟨u²⟩ / r, the fraction of the nearest-neighbour
#: distance the root-mean-square vibration amplitude reaches at melting
#: (Gilvarry, J. J., 1956, Phys. Rev. 102, 308, eq 8).  **The most generous of
#: the four ratios that paper quotes**, so a finding is past *every* criterion
#: in the source rather than past one reading of it: Gilvarry's own averages
#: are 0.072 and 0.076 (his Table III), and he calls those "significantly
#: below" the 0.085 and "somewhat less than" 0.105 he attributes to Grüneisen.
#: Picking the loosest is what keeps this a flag with no tuned constant in it.
LINDEMANN_RHO = 0.105


def biso_melting_bound(volume_a3: float, n_atoms: float) -> float:
    """Isotropic B at which an atom in this cell reaches the Lindemann bound.

    Three equations from Gilvarry (1956), and no fourth.  Eq (1) writes the
    Debye-Waller exponent as ``M = 8π²(sinθ/λ)²⟨u²⟩`` with ⟨u²⟩ "the
    mean-square amplitude, **normal to the plane of reflection**" — which is
    the crystallographic ``B = 8π²·Uiso`` exactly, the same one-dimensional
    quantity this package stores, so no convention is being converted here.
    Eq (8) is the criterion, ⟨u²⟩ = ρ²r² at fusion with r the
    nearest-neighbour distance.  Eq (9) gets r from the volume per atom,
    ``v = r³/√2``, stated for close-packed lattices with the paper's own
    licence to use it more widely: "for other lattice types, the variation of
    v/r³ from the close-packed value is too small to consider here".

    Together: ``B_melt = 8π²ρ²(√2·v)^(2/3)``.

    **The domain is stated in the source and it is narrower than this
    package's**: Gilvarry restricts to isotropic monatomic solids and says the
    theory "is not directly applicable to elements with complex lattices",
    where ρ may itself depend on lattice type.  Extrapolating it to an
    arbitrary crystal is why this reports and never bounds — a cap resting on
    an extrapolation would refuse fits the source cannot speak about.

    Measured at :data:`LINDEMANN_RHO` on ordinary inorganic solids (WP-1311):
    corundum 4.6, LaB₆ 5.2, fluorapatite 5.9, Si 8.1, NaCl 8.7 Å², over
    8.5-22.4 Å³ per atom.  Two consequences worth carrying.  ``help.py``'s
    long-standing "a refined B above about 5 Å² for a heavy atom usually means
    an absorption or background error" sits inside that band, which is an
    independent line arriving at the same place.  And ``Atom.biso``'s 25 Å²
    schema ceiling needs 109-338 Å³ per atom to be reachable below melting,
    five to twenty times any ordinary packing, so it bounds nothing physical
    and this guard is what actually speaks.
    """
    import numpy as np

    if volume_a3 <= 0.0 or n_atoms <= 0:
        return float("inf")
    v = volume_a3 / n_atoms
    r_squared = (np.sqrt(2.0) * v) ** (2.0 / 3.0)
    return float(8.0 * np.pi ** 2 * LINDEMANN_RHO ** 2 * r_squared)


def check_biso_plausible(table, model) -> list[GuardFinding]:
    """Isotropic B values past the Lindemann melting bound for their own cell.

    A flag and never a cap, which is what the IUCr round robin asked for:
    "it may also be possible to build more 'intelligence' into Rietveld codes
    and issue more warnings for potentially serious errors — (a) atom and
    overall thermal parameters which are physically unrealistic (negative,
    zero or large positive values)" (Madsen et al., 2001, J. Appl. Cryst. 34,
    409, § 6.2).  The other two warnings named there are already built:
    non-standard settings (``SPACE_GROUP_SETTING_ASSUMED``) and the
    occupancy/ZMV check.  Why a warning rather than a bound is Watkin
    (2008, J. Appl. Cryst. 41, 491): a false atom's "ADP will rise to a very large
    value, indicating that it should be removed from the model", so the number
    is *evidence about the model* and clamping it destroys the evidence.

    The threshold is computed per phase from that phase's own cell rather than
    fixed, because :func:`biso_melting_bound` moves by a factor 4.5 across
    ordinary packing densities and one constant would be wrong at one end.
    The low side needs nothing: readers refuse a negative B, the schema floors
    at zero, and PR #206 made that floor bind a caller-supplied ``Parameter``.

    Anisotropic sites are skipped.  Their ``biso`` is an inert record of the
    starting estimate (``schemas.structure.Atom``), so testing it would report
    a number no stage can move.

    Needs the compiled model for the site multiplicities, so it returns ``[]``
    without one — the ``check_stephens_positive`` convention.  The atom count
    those multiplicities feed is weighted by occupancy, since the bound is per
    atom rather than per site.
    """
    from ..crystallography.lattice import cell_volume

    if model is None:
        return []
    values = {e.path: e.value for e in table.entries}
    out: list[GuardFinding] = []
    for ip, cp in enumerate(model.phases):
        base = f"phases.{ip}"
        try:
            volume = cell_volume(
                values[f"{base}.cell.a"], values[f"{base}.cell.b"],
                values[f"{base}.cell.c"], values[f"{base}.cell.alpha"],
                values[f"{base}.cell.beta"], values[f"{base}.cell.gamma"])
        except KeyError:  # defensive: every phase carries all six cell entries
            continue
        # occupancy-weighted, because the bound divides the cell volume by the
        # number of *atoms* in it and not by the number of sites.  A site at
        # occ = 0.25 — a cavity cation, a disordered water — puts a quarter of
        # an atom in the cell, and counting it whole shrinks v and so the
        # bound, which is the one direction this guard must not err in (its
        # whole design is the loosest criterion the source quotes).
        n_atoms = sum(values.get(f"{base}.atoms.{j}.occ", 1.0) * len(rot)
                      for j, (rot, _tran) in enumerate(cp.sites.ops))
        bound = biso_melting_bound(volume, n_atoms)
        for j, is_aniso in enumerate(cp.sites.aniso):
            if is_aniso:
                continue
            path = f"{base}.atoms.{j}.biso"
            biso = values.get(path)
            if biso is not None and biso > bound:
                out.append(GuardFinding.large_biso(path, biso, bound))
    return out


#: relative tolerance below which a Γ_G² counts as *on* zero rather than below
#: it (WP-1311) — the :data:`STEPHENS_CONE_TOL` situation one seam over, and
#: resolved the same way.  Zero is inside the physical set: U = V = W = 0 is an
#: instrument with no Gaussian broadening at all, which is the state every
#: profile starts from before a resolution stage frees anything.  Relative to
#: the largest |Γ_G²| over the same fitted range, because the quadratic is
#: evaluated here and inside ``gaussian_fwhm`` in different association orders
#: and the two disagree in the last bits.
RESOLUTION_CONE_TOL = 1e-9


def check_resolution_positive(table, model) -> list[GuardFinding]:
    """The Caglioti resolution function dipping below zero in the fitted range.

    Γ_G² = U·tan²θ + V·tanθ + W is a **variance**, so the physical constraint
    is on the quadratic as a whole and not on its three coefficients: U, V and
    W each legitimately go negative on real instruments (Caglioti et al., 1958;
    a negative V is the usual sign of a focusing geometry), and the schema
    bounds allow that.  What cannot happen is the sum going negative somewhere
    a peak is actually being fitted.

    When it does, nothing raises.  ``gaussian_fwhm`` clamps Γ_G² to
    ``caglioti._MIN_GAMMA_G2`` (≈ (1e-4°)²) to keep its √ real, so the forward
    model reports a resolution four orders finer than any real goniometer and
    the fit carries on converging.  ``check_hump_width`` already meets the
    consequence and abstains rather than endorsing a peak it cannot judge; its
    docstring says the instrument being unphysical there "is a separate, more
    fundamental defect and not this guard's to name".  This is the guard that
    names it.

    Measured on the motivating configuration (WP-1311, from PR #115's review):
    schema-legal U = 0.05, V = −0.5, W = 0.001 puts the two roots of the
    quadratic at 0.229° and 168.577° 2θ, so Γ_G² is negative across **every**
    point of an ordinary scan and Γ_G is reported as the 1e-4° floor
    throughout — not, as the issue had it, only at the high-angle end.

    Tested over the frozen fitted axis rather than over all θ: a dip outside
    the measured range is unobservable, and flagging it would be a claim the
    data cannot support (the ``check_stephens_positive`` convention).  Needs
    the compiled model for that axis, so it returns ``[]`` without one.

    The **instrument** quadratic alone, with no phase size or strain term, for
    the reason ``CompiledModel.instrument_fwhm_deg`` gives: the question is
    about the goniometer, and its answer must not depend on which phase one
    happens to ask about.  A sample term large enough to lift the total back
    over zero does not make U, V, W quotable.  Read a firing as "this
    resolution function is not quotable", never as a verdict on the sample.
    """
    import numpy as np

    if model is None:
        return []
    tt = np.asarray(model.tt, dtype=np.float64)
    if tt.size == 0:
        return []
    values = {e.path: e.value for e in table.entries}
    try:
        u = values["instrument.profile.u"]
        v = values["instrument.profile.v"]
        w = values["instrument.profile.w"]
    except KeyError:  # defensive: ParameterTable always adds the five profile
        return []     # entries, so nothing in-tree reaches this

    tan = np.tan(np.radians(0.5 * tt))
    g2 = u * tan * tan + v * tan + w
    scale = max(float(np.max(np.abs(g2))), 1.0)
    bad = g2 < -RESOLUTION_CONE_TOL * scale
    if not bad.any():
        return []
    k = int(np.argmin(g2))
    return [GuardFinding.nonpositive_resolution(
        int(bad.sum()), int(g2.size), float(g2[k]), float(tt[k]))]


#: a free column counts as "on its bound" within this fraction of **the closest
#: bound's own magnitude**, floored at 1 — scipy's ``rtol`` from
#: ``optimize._lsq.common.find_active_constraints``, which is the test TRF
#: itself uses to fill ``OptimizeResult.active_mask``.  Quoted rather than
#: chosen: the diagnostic and the solver then cannot hold different opinions
#: about the same column, and the value is calibrated to how far
#: ``make_strictly_feasible`` pushes an iterate off a bound it is sitting on.
#:
#: Relative it must be, because the free vector is *internal*: a softplus width
#: and an identity-transform cell edge share no scale.  Relative to the **span**
#: — what this was until WP-1110 — is the version that misfires, and widely: a
#: caller's ``Parameter(min=1e-14, max=1e14)`` scale gives a span of 1e14, hence
#: a tolerance of 1e6, so a scale of 1.0 sitting fourteen orders of magnitude
#: from either bound reports ``BOUND_HIT`` at every stage.  The magnitude of the
#: bound the value is near is the quantity that does not grow with how generous
#: the *other* bound was.
BOUND_HIT_RTOL = 1e-10

#: the **loose** half of WP-1434's conjunction: how close to its limit a value
#: must sit, as a fraction of that parameter's own esd.  A distance is
#: meaningless on its own — TRF keeps its iterates strictly feasible, so where
#: a boundary solution lands is a function of when the solver stopped — but it
#: is what separates a bound that is carrying load from a stage that simply
#: stopped early while still heading towards one, which the gradient cannot do
#: (both push outward).  Measured: over 32 genuinely-binding cases on FAP and
#: Si SRM 640c, with ``ftol`` swept 1e-9 … 1e-3, the largest gap was 7.7e-4
#: esd; the early-stopped row of the WP's ``make_lab6`` sweep sits at 2.36 esd
#: and a free optimum at 2.4e+3.  1e-2 is inside that window with 13x margin
#: below and 236x above, and it reads as the physical statement it is: the
#: limit and the value are the same number to a hundredth of an esd.
BOUND_HIT_ESD_FRAC = 1e-2

#: the **binding** half: how far the residual must be from orthogonal to a
#: column before the limit holding it is called active
#: (:attr:`~rietx.optimize.least_squares.LSQOutcome.residual_cosine`).  The
#: sign alone does not discriminate, because at a free optimum the gradient is
#: small and its direction arbitrary — measured, "pushes outward" reads true
#: there too.  Measured: 1.5e-2 … 2.1e-1 over the 32 binding cases against
#: 5.0e-10 at a free optimum, so 1e-4 sits 145x below the weakest binding case
#: and 2e+5 above the free one.
BOUND_HIT_COS_MIN = 1e-4


def bound_findings(bounds, free: list[str], theta, *,
                   cos=None, esd=None) -> list[GuardFinding]:
    """Free paths whose bound **carried load** — the one place this happens.

    ``bounds`` is the ``(lo, hi)`` pair from a
    :class:`~rietx.params.vector.ParameterTable` or a
    :class:`~rietx.params.multi.MultiParameterTable`, ``free`` its free paths
    in column order, ``theta`` the solved internal vector.

    Two consumers, and they must not be able to disagree: the ``BOUND_HIT``
    diagnostics built from these findings, and
    :attr:`~rietx.schemas.results.RefinedParameter.at_bound`, which is the same
    list projected onto the result rows (WP-1076).  Before that WP the loop was
    written out twice — here and in ``multi.py`` — which is a duplicate a joint
    refinement would have had to keep in step by hand.

    Only *free* paths are testable.  A tied path is not in ``theta`` and is
    never seen here, so a consumer must report it as unmeasured rather than as
    not-at-a-bound; that is what the flag's third state is for.

    **The question is "did the limit change the answer", never "is the value
    near the limit"** (WP-1434, issue #273).  TRF keeps its iterates strictly
    feasible, so how close a boundary solution lands is a function of the
    stage's ``ftol``: on the issue's own fixtures nine of 32 genuinely-binding
    cases ended 1e-10 to 1.6e-6 inside their limit, ``converged``, with
    ordinary esds and no flag.  No tolerance fixes that, because the distance
    it would have to admit is four orders wide across one set of fixtures.

    So the test is a **conjunction**, and each half covers what the other
    cannot.  *Near the limit*, measured in the parameter's own esd
    (:data:`BOUND_HIT_ESD_FRAC`) — this is what keeps a stage that stopped
    early while still travelling towards a bound from being reported as
    having reached one.  *And still pushed into it*: the residual is not
    orthogonal to that column (:data:`BOUND_HIT_COS_MIN`) and the sign says
    the solver would leave the feasible set if it could.  At an unconstrained
    stationary point the normal equations force orthogonality on every free
    column, so a column that keeps an angle is being held by something, and at
    a limit that something is the limit (Nocedal & Wright, *Numerical
    Optimization* 2nd ed. ch. 12, 16 — an active set is identified by the
    multiplier, never by proximity).

    ``cos`` is
    :attr:`~rietx.optimize.least_squares.LSQOutcome.residual_cosine` and
    ``esd`` its ``stderr_internal``, both in the same column order as
    ``free``.  **Both are optional and the fallback is the pre-WP-1434 test**,
    a bare distance against :data:`BOUND_HIT_RTOL`: a caller with no solve
    behind it (or a stage whose covariance was not computed) still gets an
    answer, and the same answer it used to get.  A non-finite or non-positive
    esd falls back per column, which is what a direction the data cannot
    measure has (``ParameterTable.unmeasured_rows``); its cosine is ~0, so the
    conjunction declines it either way.

    Either path keeps the clause making a bound active only when it is the
    **nearer** of the two: on a narrow interval both thresholds can cover the
    whole span, and without it which bound gets reported is decided by the
    order the branches are written in rather than by where the value sits.
    """
    import numpy as np

    lo, hi = bounds
    out: list[GuardFinding] = []
    for k, path in enumerate(free):
        t = theta[k]
        below, above = t - lo[k], hi[k] - t
        # the nearer limit is the only candidate; ``None`` where it is infinite
        if below <= above:
            gap, limit, sign = below, lo[k], +1.0
        else:
            gap, limit, sign = above, hi[k], -1.0
        if not np.isfinite(limit):
            continue

        e = None if esd is None else esd[k]
        # the esd window is the *loose* half and is only ever evaluated as
        # half of the conjunction: without ``cos`` there is nothing to pair it
        # with, so the fallback is the pre-WP-1434 distance, exactly as this
        # docstring promises.  Widening the window without the binding test
        # would report every column within a hundredth of an esd of a limit.
        if cos is not None and e is not None and np.isfinite(e) and e > 0.0:
            near, scaled = gap <= BOUND_HIT_ESD_FRAC * e, gap / e
        else:
            near, scaled = gap <= BOUND_HIT_RTOL * max(1.0, abs(limit)), None
        if not near:
            continue

        if cos is None:
            out.append(GuardFinding.at_bound(path))
            continue
        c = float(cos[k])
        # ``sign`` is +1 at a lower limit, where a solver still pressing
        # outward would be *lowering* θ, i.e. g > 0; −1 at an upper one
        if sign * c > 0.0 and abs(c) >= BOUND_HIT_COS_MIN:
            out.append(GuardFinding.at_bound(path, c, scaled))
    return out


def check_guards(table, outcome, threshold: float,
                 background_threshold: float = BACKGROUND_ABSORPTION_GUARD,
                 roughness_threshold: float = ROUGHNESS_ABSORPTION_GUARD,
                 model=None, scan_exchangeability: bool = False) -> GuardReport:
    """Correlation, bound, background/roughness-absorption, ADP-, strain- and
    resolution-shape guards.

    ``scan_exchangeability`` additionally runs the WP-1056 held-parameter
    scan (one extra evaluate-only Jacobian), which only the answer-producing
    stage should pay for — ``_run_stage`` passes ``stage_index == n_stages``.
    """
    import numpy as np

    from ..optimize.identifiability import exchangeability_scan, soft_modes, top_correlations
    from ..optimize.statistics import (
        background_absorption,
        extra_peak_absorption,
        roughness_absorption,
    )

    report = GuardReport()
    report.nonpositive_adps = check_adp_positive_definite(table)
    report.nonpositive_strain = check_stephens_positive(table, model)
    report.nonpositive_resolution = check_resolution_positive(table, model)
    report.large_biso = check_biso_plausible(table, model)
    report.unsupported_resolution = check_resolution_supported(table, model)
    report.narrow_humps = check_hump_width(table, model)
    free = table.free_paths

    if outcome.correlation is not None and len(free) > 1:
        corr = np.asarray(outcome.correlation)
        for i in range(len(free)):
            for j in range(i + 1, len(free)):
                if abs(corr[i, j]) > threshold:
                    report.high_correlations.append(
                        GuardFinding.correlation(free[i], free[j], corr[i, j]))
                    # |ρ| = 1.000 is a rank statement, not a strong
                    # correlation, and saying so in the same vocabulary as
                    # ρ = 0.96 undersells it.  Reported *beside* the
                    # correlation rather than instead of it: the
                    # SEQUENTIAL_PERSISTENT_FINDING precedent, where the
                    # sharper finding rides alongside the ones it sharpens,
                    # so no existing consumer loses a row it counts on.
                    if abs(corr[i, j]) >= FLAT_DIRECTION_RHO:
                        report.flat_directions.append(
                            GuardFinding.flat_direction(
                                free[i], free[j], corr[i, j]))
        # measured once (WP-1056): the same matrix the loop above thresholds
        report.measured_top_correlations = top_correlations(corr, free)

    if outcome.jac is not None and len(free) > 1:
        # measured once: the screened table travels to the result (WP-1055)
        # and the threshold decides only which rows become findings
        peak_prefixes = (model.peak_component_prefixes() if model is not None
                         else frozenset())
        report.measured_background_absorption = background_absorption(
            outcome.jac, free, peak_prefixes)
        report.measured_extra_peak_absorption = extra_peak_absorption(
            outcome.jac, free, peak_prefixes)
        try:
            report.measured_soft_modes = soft_modes(outcome.jac, free)
        except np.linalg.LinAlgError:
            # the unit-column Gram is the matrix the esd computation already
            # failed to eigensolve (WP-1333, issue #225): the stage has said so
            # through ``COVARIANCE_UNAVAILABLE``, and a second raise of the
            # same failure here would discard the answer that guard kept.
            # Anywhere the covariance *did* form, this stays loud.
            if getattr(outcome, "covariance_error", None) is None:
                raise
        if scan_exchangeability and model is not None:
            report.measured_exchangeability = exchangeability_scan(model, table)
        for path, r2 in sorted(report.measured_background_absorption.items(),
                               key=lambda kv: -kv[1]):
            if r2 > background_threshold:
                report.background_correlations.append(
                    GuardFinding.background_absorption(path, r2))
        for path, r2 in sorted(roughness_absorption(
                outcome.jac, free, peak_prefixes).items(),
                               key=lambda kv: -kv[1]):
            if r2 > roughness_threshold:
                report.roughness_correlations.append(
                    GuardFinding.roughness_absorption(path, r2))

    report.at_bounds = bound_findings(
        table.bounds(), free, outcome.theta,
        cos=getattr(outcome, "residual_cosine", None),
        esd=getattr(outcome, "stderr_internal", None))
    return report
