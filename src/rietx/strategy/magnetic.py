"""From a nuclear fit with unexplained intensity to a ranked list of magnetic structures.

``solve_magnetic`` is a **strategy**, not a new physics term: every step below
is a verb this package already has, and the module's job is the order they run
in, the criterion the answers are ranked by, and the sentence that comes out
when the powder cannot separate two of them.

The chain, and who owns each link:

1. **k** — the satellite arm of the unexplained-intensity report
   (:mod:`rietx.report.satellites`, WP-1326) sorts the positive residual peaks
   into the three places one can be.  Peaks on a reciprocal-lattice point the
   *nuclear* structure factor forbids are the **k = 0 signature** and are never
   scored against a candidate k: no nuclear model, right or wrong, puts
   intensity at a systematic absence, and a magnetic space group generally
   drops the parent's glides and screws, so that excess *is* the hypothesis.
   Only the peaks at neither a calculated line nor a forbidden lattice point
   need a propagation vector, and those are what the ranked candidate list is
   scored on.  Neither → the workflow abstains and says which.
2. **candidates** — :func:`rietx.crystallography.magnetic.isotropy.candidates`
   (M-7) enumerates, for each magnetic site, every order-parameter direction of
   every small irrep with a non-zero multiplicity, and gives each one as a
   magnetic space group in its own cell.
3. **one trial refinement per powder-equivalence class** — never one per
   candidate.  :func:`~rietx.crystallography.magnetic.isotropy.equivalence_classes`
   is Shirane's rule (1959) made mechanical: members of a class are models a
   powder pattern to this d limit cannot separate, so refining each of them
   would spend N fits to produce N copies of one number and then invite a
   reader to rank them.  The class is the unit; its members are *named* in the
   result and the powder's inability to separate them is the finding.
4. **ranking, and abstention** — see :data:`SOLVE_TIE_DELTA_BIC`.  Never Rwp:
   a candidate with more free amplitudes always reaches a lower Rwp, so an Rwp
   ordering is a freedom ordering wearing a fit's clothes.

**What the ranking is.**  ΔBIC (:func:`rietx.report.layer2.delta_bic`,
Schwarz 1978 — the package's one BIC form), computed against a nuclear
reference refined *under the same stage list minus the moment paths*, so the
only difference between the two models is the moment block and ``n_added`` is
exactly the moment DOFs that stayed free.  The observation count is the
reference's effective one, as :func:`rietx.report.compare_freed` charges it
(issue #270; WP-2002, B12):

    ΔBIC = N_eff·ln(χ²_nuclear / χ²_trial) − n_added·ln N_eff,
    N_eff = N / f²,

N the fitted channels and f the Bérar-Lelann factor (Bérar & Lelann, 1991,
J. Appl. Cryst. 24, 1) the reference's solve multiplied its esds by.
Neighbouring channels of one peak share their residual's sign, so N counts
the same misfit several times, and at raw N any χ² gain outvotes the penalty
(:func:`~rietx.optimize.statistics.effective_sample_size`).  BIC is where
parsimony enters: ``−n_added·ln N_eff`` charges every extra amplitude, which
is why a nested triple of groups reaching the same profile comes out in the
order the smallest group first.  The **magnetic-only R**
(:attr:`MagneticTrial.r_magnetic`) is reported beside it, a profile R over
exactly the channels the nuclear model puts nothing on — WP-1326's buckets 2
and 3 — where 1.0 is "explains none of it" and 0 is "explains all of it".  It
ranks nothing.  A gap under :data:`SOLVE_TIE_DELTA_BIC` is **not** a ΔBIC
ranking: the classes inside it are tied *on ΔBIC*, and the verdict is an
abstention naming every tied class with its R_mag.  The tied classes come
first in the published list with the fewest moment parameters first, the
order of the highest-symmetry convention, and the reason says so.  Until 1.10
two keys broke a tie: an R_mag gap of more than 2 %, a margin chosen and never
measured, and a smaller moment-parameter count, which counted a cost the ΔBIC
already charges and declared a winner the data had not chosen.  Both are gone
(WP-2002, B12 and the ruling of 2026-10-20).

**The null test is a gate, not a column.**  A trial whose every moment comes
back unsupported (WP-1327 D4: below the floor *or* below
``MOMENT_SUPPORT_SIGMA`` of its own esd, because the null does not land at zero
— 0.0666 μ_B with an esd of 0.878 on a real 150 K pattern) cannot win, whatever
its ΔBIC.  When no trial has a supported moment the verdict is that there is
nothing to solve.  A powder-degenerate pair (``MOMENT_PAIR_DEGENERATE``) is tested as the pair: each
modulus alone rides a flat direction and fails the ratio however large it is,
so the gate reads the quadrature sum the powder does measure
(:attr:`MomentRow.pair_supported`).

**What it refuses.**  An X-ray histogram, by name: the *position* of a magnetic
satellite and of a superstructure reflection are the same and the inference is
not, and a moment refined against X-rays has no gradient anywhere
(:func:`rietx.model.forward.magnetic_wanted`).  A histogram whose report shows
no unexplained intensity is not refused — it is answered, with the reason.

**Provisional.**  The chain is stable; the ranking criterion is not.  M-10
(mode amplitudes) changes what a trial refines, M-11 (incommensurate k) adds a
branch this module abstains on today, and WP-1329's temperature series is a
discriminator none of the numbers here can be.  See the compatibility chapter.

References
----------
Shirane, G. (1959). *Acta Cryst.* **12**, 282 — what a powder average
determines of a moment direction; the degeneracies that make a class.

Schwarz, G. (1978). *Ann. Stat.* **6**, 461 — the Bayesian information
criterion the ranking is ordered by.

Bérar, J.-F. & Lelann, P. (1991). *J. Appl. Cryst.* **24**, 1 — the
serial-correlation factor f behind the effective count N/f².

Kass, R. E. & Raftery, A. E. (1995). *J. Am. Stat. Assoc.* **90**, 773 — the
evidence scale :data:`SOLVE_TIE_DELTA_BIC` is read off.

Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — FullProf; the
propagation-vector description of a commensurate magnetic structure.

Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L., de la Flor, G. &
Aroyo, M. I. (2015). *Annu. Rev. Mater. Res.* **45**, 217 — magnetic symmetry
as the refinable object, and the MAGNDATA description this module writes out.

Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
*J. Appl. Cryst.* **39**, 607 — parent + irrep + order-parameter direction as
the enumeration the candidates come from.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path

import numpy as np

from ..crystallography.magnetic import isotropy as _isotropy
from ..crystallography.magnetic import moments as _moments
from ..crystallography.magnetic.form_factor import (
    assumed_lande_g,
    magnetic_ions,
    needs_explicit_g,
    resolve_assumed_ion,
)
from ..crystallography.magnetic.isotropy import MagneticCandidate, analyse
from ..crystallography.magnetic.moments import tilted_seed, warm_seed
from ..crystallography.magnetic.supercell import (
    anti_translation_residual,
    anti_translation_ties,
    magnetic_supercell,
)
from ..crystallography.symmetry import resolve_group
from ..schemas.common import Diagnostic
from ..schemas.plan import CLOSING_WINDOW_TOL
from ..schemas.structure import MagneticSymmetry, Moment, Structure
from .staged import RefinementPlan, Stage

#: ΔBIC below which two classes are **tied** and the workflow abstains rather
#: than ranking them.  6.0 is "strong" on the Kass & Raftery (1995) scale and
#: is the same bar ``PEAK_KEEP_COMPONENT_MIN_DELTA_BIC`` uses one subsystem
#: over: a determination that names a winner on weaker evidence than that is
#: the confident wrong singleton the indexing rule (WP-1043) exists to stop.
#: It is the *width of the tie*, quoted in the result, never a threshold a
#: caller is invited to tune down until an answer appears.  The band is Kass
#: and Raftery's; the ΔBIC it is applied to charges N/f² observations, which is
#: rietx's own count (WP-2002, B12).
SOLVE_TIE_DELTA_BIC = 6.0

#: How many candidate propagation vectors the ranked list is carried down to
#: when the excess indexes as satellites.  A list, never a singleton: the top
#: row is a hypothesis worth testing.
SOLVE_TOP_K = 3

#: How many of the ranked candidate k's (already capped by ``top_k``) get a
#: full trial refinement of their own, not merely a fallback tried when an
#: earlier one's classes all refuse to be stated as a model.  1 is the
#: behaviour before runner-up k's were fitted — only the first testable k
#: is ever fitted.  2 (the
#: default) also fits the runner-up when it is within
#: :data:`SOLVE_K_OFFSET_MARGIN_DEG` of the winner's satellite fit, because a
#: satellite match alone cannot separate two k's that index the same peaks
#: equally well — measured on Ba₂FeSbSe₅ at 1.5 K (the published
#: k = (½,0,½) pattern of Phys. Rev. B **103**, 054115, not vendored), where
#: k=(1/2,0,1/2) and k=(1/2,1/2,0) both index the same 11 peaks (worst offsets 0.100 deg and
#: 0.181 deg) and only the moment refinement's intensity can tell them apart.
SOLVE_K_TRIALS = 2

#: Named offset margin deciding which runner-up k's are "close enough" on the
#: satellite step alone to be worth a second full trial refinement.  Two
#: candidates that index the same number of satellites (``matched``) and
#: whose worst offset differs by no more than this are not separated by the
#: satellite step; the Ba₂FeSbSe₅ pair above are 0.081 deg apart, comfortably
#: inside it.
SOLVE_K_OFFSET_MARGIN_DEG = 0.5

#: ΔBIC gap below which the top two *k-vector* trials (not two candidate
#: classes of the *same* k, which is :data:`SOLVE_TIE_DELTA_BIC`) are not
#: separated by intensity either, and ``K_VECTOR_UNSEPARATED`` is reported.
#: Wider than the intra-k tie width on purpose: two different propagation
#: vectors are two different models of the data, not two descriptions of one
#: model the way a class's members are, so the bar for calling them
#: indistinguishable is a coarser one.
SOLVE_K_TIE_DELTA_BIC = 10.0

#: d limit, in Å, for M-7's powder-equivalence test.  The classes are a
#: statement about *a powder pattern to a d limit*, so the limit is a
#: parameter of the answer and is quoted in the result.
SOLVE_D_MIN = 1.5

#: Seed modulus, μ_B, for a trial refinement's moment.  A seed, not a claim:
#: WP-1327 measured that four in-plane seeds on Cr₂WO₆ reach the same answer,
#: and the direction of the seed is always **inside the candidate's own allowed
#: subspace** (:func:`~rietx.crystallography.magnetic.moments.tilted_seed`,
#: mostly along the allowed basis's first row and, since issue #390's tilt,
#: with a small nonzero component on every other row too when the basis has
#: more than one — see :data:`~rietx.crystallography.magnetic.moments.
#: SEED_TILT`), which is the one thing a seed here must not get wrong.
SOLVE_SEED_MU_B = 2.0

#: Alias of :data:`~rietx.crystallography.magnetic.moments.SEED_TILT`, kept
#: here under the name this module's own docstrings and tests already use;
#: see that constant's docstring for the mechanism and :func:`_seed`.
SOLVE_SEED_TILT = _moments.SEED_TILT

#: The stage list a trial refines under on a **constant-wavelength** histogram,
#: unless a caller supplies a plan, named by :data:`SOLVE_STAGE_NAMES`.  Moment
#: + scale + background first — the block that has to climb out of the noise
#: before anything else is allowed to move — then the fuller stage.
#:
#: **The moduli climb before the angles turn** (WP-1938 D12).  A moment's angle
#: columns scale with its modulus, and vanish at a direction the symmetry fixes,
#: where only the curvature Gauss-Newton drops determines the angle.  LM scales
#: each column to unit norm, so such an angle takes the largest step, and λ
#: grows until every parameter crawls.  Measured on the two-site Pnma set of
#: ``tests/test_pair_diagnostic_class.py`` (macOS arm64): a site released at
#: 0.1 μ_B stopped at χ² 454 660 under λ ≈ 1e8, reporting ``converged``, where
#: TRF reached 2555.8.  Freed modulus-only first, the same start reached
#: 2556.06 under LM.
#:
#: **The widths are the instrument's alone.**  The stage frees U and X and not
#: the specimen's ``gauss_strain`` and ``lor_size``, which share their angular
#: shapes, so a pattern sees only each pair's sum.  Freed together they are
#: what WP-2002's width twin hold holds U and X against, leaving the ranking's
#: widths on the instrument the caller handed in plus a specimen term floored
#: at 0; freed alone, the instrument carries the whole width.  GSAS-II leaves
#: its sample size and microstrain flags off by default (``docs/practice.md``),
#: so its fits read their widths this way too.  A calibrated instrument is
#: moved off its calibration here; whether that changes a ranking is
#: unmeasured (the generality judge, WP-2002 9th session).
#:
#: **Coordinates are deliberately absent.**  Freeing them lets each candidate's
#: *nuclear* model absorb a different amount of the magnetic intensity, which
#: is precisely the confound a ranking must not have; and for a supercell
#: statement the child asymmetric unit is larger than the parent's, so its
#: coordinates are the parameters the magnetic-supercell rung (WP-1327)
#: measured as the unstable ones.
SOLVE_STAGE_PATHS: tuple[tuple[str, ...], ...] = (
    ("phases.*.atoms.*.moment.dof0", "phases.*.scale",
     "instrument.background.c*"),
    ("phases.*.atoms.*.moment.dof*", "phases.*.scale",
     "instrument.background.c*"),
    ("phases.*.atoms.*.moment.dof*", "phases.*.scale",
     "instrument.background.c*", "phases.*.cell.*", "instrument.zero_shift",
     "phases.*.atoms.*.biso", "instrument.profile.u", "instrument.profile.x"),
)

#: The names of :data:`SOLVE_STAGE_PATHS`' stages, in order.
SOLVE_STAGE_NAMES: tuple[str, ...] = ("moduli", "moment", "all")

#: Fraction of a site's own seed that an *absent* moment is restored at when a
#: one-site start releases the rest.  Small enough that the released amplitudes
#: start near the submodel the leg converged to, non-zero because |F_m|² ∝ m²
#: makes an exactly-zero moment a dead column (WP-1327).  The value is the one
#: the Ba₆Co₆ measurement used (the GSAS-II Magnetic-III tutorial pattern,
#: not vendored).
SOLVE_RELEASE_FRACTION = 0.05

#: Relative Rwp separation above which two starts of one candidate are counted
#: as **different minima** rather than the same one reached twice.
SOLVE_MINIMUM_RTOL = 1e-4

#: How many times :func:`_fit` continues a fit that stopped on its iteration
#: budget (``max_iter``), each continuation from where the last one stopped,
#: with everything the plan freed by its end and the last stage's budget and
#: tolerance.  A runaway guard, never a timer: it bounds a fit that is not
#: going anywhere, and a fit still short after it is listed and not ranked
#: (:attr:`MagneticTrial.fit_status`).  **Measured** on Cr₂WO₆ at 150 K (the
#: tree's tutorial data, review of #592), where the default stages stop every
#: fit on TRF's 400 evaluations: the nuclear reference needed 5
#: continuations and the two refined classes 3 and 7, and the budget stops had
#: left the reference 27.6 χ² and one class 18.2 χ² above their minima.
SOLVE_MAX_CONTINUATIONS = 10

_MOMENT_GLOB = "moment.dof"


# ---------------------------------------------------------------------------
# the answer
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MomentRow:
    """One site's refined moment inside one trial.

    ``magnitude`` is |m| under the crystal-axis cosine metric and ``esd`` is
    the esd of the *modulus* DOF, which is where WP-1327 puts a moment's
    uncertainty and the only place it exists — the three components are written
    back from the DOFs and carry no ``stderr``.  It is Bérar-Lelann-inflated
    like every other esd this package quotes.

    ``unmeasured_directions`` are the direction DOFs the powder average does
    not determine, held rather than given a small esd.  A non-empty list here
    is a **result**: it is the workflow saying which part of the structure this
    measurement could not see.
    """

    label: str
    ion: str
    magnitude: float
    esd: float | None
    crystalaxis: tuple[float, float, float]
    supported: bool
    unmeasured_directions: tuple[str, ...] = ()
    #: dot-path(s) of the other site(s) this modulus is powder-degenerate
    #: with (``MOMENT_PAIR_DEGENERATE``, ``MomentEvidence.paired_with``) —
    #: empty for an ordinary row.
    paired_with: tuple[str, ...] = ()
    #: the quadrature sum over the pair and its esd from the fit's own
    #: covariance, when :attr:`paired_with` is non-empty; ``None`` otherwise.
    paired_magnitude: float | None = None
    paired_magnitude_esd: float | None = None

    @property
    def sigma(self) -> float | None:
        """|m| in units of its own esd — WP-1327 D4's ratio, or None."""
        if self.esd is None or self.esd <= 0.0:
            return None
        return abs(self.magnitude) / self.esd

    @property
    def pair_supported(self) -> bool:
        """Whether this row's degenerate pair survives WP-1327's null test *as a pair*.

        A powder-degenerate pair (:attr:`paired_with`) has each modulus
        undetermined on its own — the two ride a flat direction |ρ| → 1, so
        each row's esd is the length of that valley and :attr:`supported`
        fails however large the moment is — while the quadrature sum the
        powder does measure can be many esds clear of zero.  Measured on a
        two-site entry of issue #458's MAGNDATA sweep: each modulus at 0.4× its own esd
        ("unsupported"), their quadrature sum at 63× its esd (re-measured with
        ρ and both σ's read from the answer stage's covariance, as
        :func:`_moment_correlations` now does: unchanged, and 63–82× across
        the seeds and re-fit rounds where the pair folds), and the solve
        said "nothing to solve" because the gate read the rows (with the
        coordinates also free, the published group lost the same way to a
        class whose ΔBIC was 7× lower — see :func:`_moment_correlations`).  The
        same test as the row's (above the floor and more than
        ``MOMENT_SUPPORT_SIGMA`` of its own esd), applied to the number that
        is measured; False for an ordinary row.
        """
        from ..report.schemas import MOMENT_SUPPORT_SIGMA
        from ..schemas.structure import MOMENT_FLOOR_MU_B

        m, esd = self.paired_magnitude, self.paired_magnitude_esd
        if not self.paired_with or m is None or m <= MOMENT_FLOOR_MU_B:
            return False
        return esd is None or m > MOMENT_SUPPORT_SIGMA * esd


@dataclass(frozen=True)
class MagneticTrial:
    """One powder-equivalence class, refined once, with what the data said.

    ``members`` names every candidate in the class — the models this pattern,
    to :attr:`MagneticSolution.d_min`, **cannot separate**.  They are not
    alternatives that were rejected; they are one answer with several
    descriptions, and a report that prints only the representative has hidden
    the ambiguity rather than measured it.

    ``status`` is ``"refined"`` or ``"refused"``; a refusal carries its own
    message in ``refusal`` and is listed rather than dropped, because "this
    candidate's magnetic orbit cannot cover the nuclear one" is information
    about the candidate set and not a failure of the run.
    """

    class_index: int
    representative: str
    members: tuple[str, ...]
    site: str
    irrep: str
    direction: str
    bns_number: str
    uni_number: int | None
    msg_type: int | None
    #: amplitudes the **representative site's** family has before any data is
    #: looked at.  On a parent with several magnetic sites this is per site and
    #: is not the model's parameter count — that is
    #: :attr:`n_moment_parameters`, and it is what orders a tie
    free_amplitudes: int
    #: ``None`` on a refused trial: the powder determines nothing about a model
    #: that was never stated, which is not the same as "determines none"
    determinable_amplitudes: int | None
    status: str
    refusal: str | None = None
    rwp: float | None = None
    gof: float | None = None
    delta_bic: float | None = None
    r_magnetic: float | None = None
    #: ``None`` on a refused trial (no fit ran), like the three fields below
    n_moment_parameters: int | None = None
    n_free_parameters: int | None = None
    moments: tuple[MomentRow, ...] = ()
    held: tuple[str, ...] = ()
    anti_translation_drift: float | None = None
    #: how many seeds the moment stage was started from — one for a class with
    #: a single magnetic site, one per site plus the flat start otherwise
    n_starts: int | None = None
    #: how many *distinct* converged minima those starts found.  More than one
    #: is a reportable fact about the candidate and not about the run: it says
    #: the moment stage of this model is multimodal, so the answer below is the
    #: best of several and a different seed would have reported another
    n_minima: int | None = None
    #: which start won, named
    start: str | None = None
    #: the winning start's ``RefinementResult.status`` — ``"converged"``,
    #: ``"max_iter"`` or ``"diverged"``, the fit's own vocabulary.  A fit that
    #: stops on its iteration budget is continued from where it stopped, up to
    #: :data:`SOLVE_MAX_CONTINUATIONS` times (:func:`_fit`); one still not
    #: converged after that is listed with its numbers but is **not eligible** (:func:`_eligible_trials`), because its
    #: ΔBIC is the budget's and not the data's.  ``None`` only on a trial this
    #: module did not fit.
    fit_status: str | None = None
    #: the ``status`` of the nuclear reference this trial's ΔBIC was measured
    #: against, after the same continuations.  A reference stopped short has a
    #: χ² too high and inflates the ΔBIC of every trial measured against it by
    #: the same amount, in the direction that turns "nothing to solve" into
    #: "solved" — so a trial against one is treated exactly like a trial whose
    #: own fit stopped short (:func:`_converged`).  ``None`` on a refused trial.
    reference_status: str | None = None
    _structure: Structure | None = field(default=None, repr=False, compare=False)
    _result: object | None = field(default=None, repr=False, compare=False)
    #: the winning start's refinement and the plan it ran, which
    #: :func:`_close` continues from
    _refinement: object | None = field(default=None, repr=False, compare=False)
    _plan: RefinementPlan | None = field(default=None, repr=False, compare=False)

    @property
    def supported(self) -> bool:
        """Whether any site's moment — or any degenerate pair's quadrature sum
        (:attr:`MomentRow.pair_supported`) — survived WP-1327's null test."""
        return any(m.supported or m.pair_supported for m in self.moments)

    @property
    def label(self) -> str:
        """What the table prints in the class column."""
        return f"{self.bns_number} {self.representative}"

    @property
    def stopped_short(self) -> str | None:
        """What stopped short of a minimum, in words, or ``None``.

        Either this trial's own fit or the nuclear reference its ΔBIC is
        measured against (:attr:`reference_status`): both are the budget's
        answer and not the data's.
        """
        if self.fit_status not in (None, "converged"):
            return f"the fit stopped at {self.fit_status!r}"
        if self.reference_status not in (None, "converged"):
            return (f"its nuclear reference stopped at "
                    f"{self.reference_status!r}")
        return None


@dataclass(frozen=True)
class KTrialSummary:
    """One propagation vector's own trial refinement (:data:`SOLVE_K_TRIALS`).

    ``MagneticSolution.trials`` is the *winning* k's classes only — this is
    the one row per k actually carried into a refinement, win or not, so a
    reader can see what the runner-up k reached without re-running it.
    ``matched``/``worst_offset_deg`` are the satellite step's own numbers for
    this k (``None`` when the k was not scored by it — a given ``k=`` or the
    forbidden-lattice-point route).  ``best_delta_bic`` is the best eligible
    class's ΔBIC (:func:`_rank`'s own eligibility: refined and converged, a
    supported moment, ΔBIC > 0), or ``None`` if this k reached no eligible class.
    """

    k: tuple[str, str, str]
    matched: int | None
    worst_offset_deg: float | None
    best_delta_bic: float | None
    n_refined: int


@dataclass(frozen=True)
class SubgroupAudit:
    """One maximal magnetic subgroup of the winner, refit and compared.

    Issue #390's descent audit: after :func:`_rank` picks a winner, it
    looks one step down its own group-subgroup lattice — among the classes
    already enumerated *at the winner's own k*, whichever have a magnetic
    group that is a genuine operator-list subgroup of the winner's, keeping
    only the maximal ones (:func:`_maximal_subgroups`) — and refits each from
    the winner's own converged solution plus a symmetry-breaking perturbation
    on the newly-freed DOFs (:func:`~rietx.crystallography.magnetic.moments.
    warm_seed`), never from zero (the same stationary-point reason
    :data:`~rietx.crystallography.magnetic.moments.SEED_TILT` exists for).

    ``delta_bic_over_winner`` is :func:`~rietx.report.layer2.delta_bic` with
    the **winner** as the restricted model, so a positive number favours the
    subgroup; ``None`` when the subgroup refused (``status="refused"``,
    ``refusal`` says why) rather than being ranked and losing.
    """

    bns_number: str
    label: str
    #: ``None`` on a refused row: no fit ran, so no moment was counted
    n_moment_parameters: int | None
    delta_bic_over_winner: float | None
    status: str
    refusal: str | None = None


@dataclass(frozen=True)
class MagneticSolution:
    """The ranked list, the criterion, and the verdict or the abstention.

    ``verdict`` is one of:

    ``"solved"``
        one class is ahead of every other by more than :attr:`tie_width`.
    ``"abstained"``
        the top classes are inside the tie width, or the k step could not
        choose, or a fit that would have mattered stopped on its budget;
        ``tied`` names the classes and ``reason`` says which it is, with each
        tied class's R_mag.  A ΔBIC tie lists the fewest moment parameters
        first, the highest-symmetry convention's order.
    ``"nothing to solve"``
        the pattern carries no unexplained intensity a magnetic model would
        explain, or no candidate's moment survived the null test.  This is an
        answer about the specimen, not a failure of the run — it is the shape
        the 150 K arm of a two-temperature acceptance takes.

    ``__str__`` prints the classic table.  Nothing is written to disk unless
    :meth:`write_magcifs` is called or ``cif_dir=`` was passed.
    """

    verdict: str
    reason: str
    criterion: str
    phase: str
    space_group: str
    k: tuple[str, str, str] | None
    k_route: str
    #: why the k step chose what it chose, in a sentence.  Separate from
    #: ``reason``, which is the *verdict's*: a solved determination still has to
    #: be able to say how its propagation vector was arrived at, and folding the
    #: two into one string loses whichever the last writer did not need.
    k_reason: str
    k_candidates: tuple[tuple[str, int, int], ...]
    sites: tuple[str, ...]
    n_residual_peaks: int
    n_on_nuclear_lines: int
    n_on_forbidden_lattice_points: int
    n_unexplained: int
    trials: tuple[MagneticTrial, ...]
    tied: tuple[int, ...]
    tie_width: float
    d_min: float
    nuclear_rwp: float | None
    nuclear_gof: float | None
    nuclear_r_magnetic: float | None
    n_magnetic_channels: int
    caveats: tuple[str, ...] = ()
    #: every propagation vector ``k_trials`` actually refined (win or not),
    #: one row each, in the order tried — see :class:`KTrialSummary`.  Length
    #: 1 whenever only one k was testable, or the runner-up fell outside
    #: :data:`SOLVE_K_OFFSET_MARGIN_DEG` or ``k_trials`` was left at 1.
    k_trials: tuple[KTrialSummary, ...] = ()
    #: structured diagnostics (``K_VECTOR_UNSEPARATED`` when the top two
    #: entries of :attr:`k_trials` are within :data:`SOLVE_K_TIE_DELTA_BIC`)
    #: — separate from :attr:`caveats`, which stays plain sentences, because a
    #: caller filtering by code should not have to parse one.
    diagnostics: tuple[Diagnostic, ...] = ()
    #: Issue #390's descent audit: the winner's own maximal magnetic subgroups (at its
    #: own k, among the classes already enumerated), each refit from the
    #: winner's converged solution and compared by ΔBIC — see
    #: :class:`SubgroupAudit`.  Empty when the k was not zero (not
    #: warm-started today) or the winner had no such subgroup among the
    #: classes already tried; :attr:`subgroup_note` says which.
    subgroup_audit: tuple[SubgroupAudit, ...] = ()
    #: one sentence: "no subgroup supported at ΔBIC < *width*", the beaten
    #: subgroup's own name and margin, or why the audit was not attempted —
    #: always set on a solved verdict, empty on an abstention (there is no
    #: winner to descend from).
    subgroup_note: str = ""
    #: the instrument the trials were refined with; the magCIF writer's only
    #: use for it, and never part of the answer
    _instrument: object | None = field(default=None, repr=False, compare=False)

    @property
    def best(self) -> MagneticTrial | None:
        """The winning class, or ``None`` — an abstention has no winner."""
        return self.trials[0] if self.verdict == "solved" and self.trials else None

    @property
    def margin(self) -> float | None:
        """The winner's ΔBIC over the best *other eligible* class, or ``None``.

        ``None`` when there is no winner (an abstention) or no second
        eligible class to compare against.  The winner is ``trials[0]``, the
        top-ΔBIC class, so the margin is positive and above
        :attr:`tie_width`.

        **Why this exists** (issue #390, measured on two entries of its
        MAGNDATA sweep): a caller diffing
        ``trials[0].delta_bic - trials[1].delta_bic`` naively is comparing
        the winner to whichever class :func:`_rank` printed *second*, and
        that is only the true runner-up when it is itself eligible.
        :attr:`MagneticSolution.trials` is ``eligible`` (sorted best first)
        **then** ``rest`` — every refused, unsupported or non-improving
        class, each sorted by its own raw ΔBIC — so whenever the winner has
        no eligible rival, ``trials[1]`` is drawn from ``rest`` and can carry
        a ΔBIC *higher* than the winner's: an unsupported model's fit can
        happen to reach a lower χ² by chance (WP-1327's null test judges
        each moment, not the model's ΔBIC), and BIC alone does not know that
        the null test disqualified it.  Diffing against it produces a
        negative number that reads as a ranking failure; it is a reporting
        artifact of picking the wrong rival, not a defect in :func:`_rank`,
        which never considered that class a competitor in the first place.
        """
        if self.verdict != "solved" or not self.trials:
            return None
        winner = self.trials[0]
        others = [t.delta_bic for t in _eligible_trials(self.trials)
                  if t is not winner]
        if not others:
            return None
        return winner.delta_bic - max(others)

    def __str__(self) -> str:
        head = [
            f"solve_magnetic — {self.phase} ({self.space_group})",
            f"  k           : {'—' if self.k is None else '(' + ', '.join(self.k) + ')'}"
            f"   [{self.k_route}]",
            f"  because     : {self.k_reason}",
            f"  residual    : {self.n_residual_peaks} peaks — "
            f"{self.n_on_nuclear_lines} on a nuclear line, "
            f"{self.n_on_forbidden_lattice_points} on a forbidden lattice point, "
            f"{self.n_unexplained} unexplained",
            f"  criterion   : {self.criterion}",
            f"  verdict     : {self.verdict.upper()} — {self.reason}",
        ]
        if not self.trials:
            return "\n".join(head)
        cols = ("class", "BNS", "irrep/dir", "site", "free", "det",
                "Rwp", "GoF", "dBIC", "R_mag", "|m| (mu_B)", "held")
        widths = (5, 10, 14, 6, 4, 3, 8, 6, 10, 6, 20, 10)
        rows = ["", "  ".join(c.ljust(w) for c, w in zip(cols, widths))]
        for trial in self.trials:
            if trial.status != "refined":
                rows.append("  ".join(str(v).ljust(w) for v, w in zip(
                    (trial.class_index, trial.bns_number,
                     f"{trial.irrep}{trial.direction}", trial.site,
                     trial.free_amplitudes, trial.determinable_amplitudes,
                     "refused", "-", "-", "-",
                     (trial.refusal or "")[:20], "-"), widths)))
                continue
            best = max(trial.moments, key=lambda m: abs(m.magnitude),
                       default=None)
            moment = "-" if best is None else (
                f"{abs(best.magnitude):.3f} ± "
                + ("-" if best.esd is None else f"{best.esd:.3f}")
                + ("" if best.supported else " (unsupported)"))
            rows.append("  ".join(str(v).ljust(w) for v, w in zip(
                (trial.class_index, trial.bns_number,
                 f"{trial.irrep}{trial.direction}", trial.site,
                 trial.free_amplitudes, trial.determinable_amplitudes,
                 f"{trial.rwp:.5f}", f"{trial.gof:.3f}",
                 f"{trial.delta_bic:.1f}" if trial.delta_bic is not None else "-",
                 f"{trial.r_magnetic:.3f}" if trial.r_magnetic is not None else "-",
                 moment, str(len(trial.held)) + " dof"), widths)))
        rows.append("")
        for trial in self.trials:
            if trial.status == "refined" and not _converged(trial):
                rows.append(f"  class {trial.class_index}: "
                            f"{trial.stopped_short}, not 'converged', so it is "
                            f"listed and not ranked")
        for trial in self.trials:
            if len(trial.members) > 1:
                rows.append(f"  class {trial.class_index}: the powder cannot "
                            f"separate {', '.join(trial.members)}")
        for trial in self.trials:
            for m in trial.moments:
                if m.unmeasured_directions:
                    rows.append(
                        f"  class {trial.class_index}, {m.label}: the powder "
                        f"average does not determine "
                        f"{', '.join(m.unmeasured_directions)}")
        if self.nuclear_rwp is not None:
            line = f"  nuclear reference: Rwp {self.nuclear_rwp:.5f}"
            if self.nuclear_r_magnetic is not None:
                line += (f", R_mag {self.nuclear_r_magnetic:.3f} over "
                         f"{self.n_magnetic_channels} channels")
            rows.append(line)
        if len(self.tied) > 1:
            rows.append("")
            rows.append("  descent among the tied classes (operator-list "
                       "containment, not the DOF-count proxy):")
            rows.extend(f"  {line}" for line in _tie_lattice_lines(
                self.trials, self.tied))
        if self.subgroup_note:
            rows.append(f"  subgroup descent: {self.subgroup_note}")
        for note in self.caveats:
            rows.append(f"  ! {note}")
        return "\n".join(head + rows)

    def write_magcifs(self, directory) -> list[str]:
        """Write one magCIF per refined class, and return the paths.

        WP-1328's writer, through the refinement exporter, so each file carries
        the operator list, the BNS metadata, the parent k where there is one,
        the moments with the modulus's esd in ``_atom_site_moment.magnitude_su``
        and the R-factors of the trial that produced it.  One file per **class**
        — the members a powder cannot separate share a structure factor, so
        writing one file each would be N copies of one model.
        """
        from ..io.exporters import write_refinement_cif

        out: list[str] = []
        base = Path(directory)
        base.mkdir(parents=True, exist_ok=True)
        for trial in self.trials:
            if trial.status != "refined" or trial._result is None:
                continue
            name = (f"class{trial.class_index}_"
                    f"{trial.bns_number.replace('.', '_')}.mcif")
            path = base / name
            write_refinement_cif(trial._result, trial._structure,
                                 self._instrument, path)
            out.append(str(path))
        return out


# ---------------------------------------------------------------------------
# the magnetic-only region
# ---------------------------------------------------------------------------
def _peak_positions_and_widths(model, values) -> tuple[np.ndarray, np.ndarray]:
    """(positions, FWHM) of every modelled peak, on the model's own abscissa.

    ``phase_peaks`` yields ``(position, *width_parameters, intensity)`` and
    ``peak_fwhm`` takes those width parameters, so unpacking by position rather
    than by arity is what keeps one window builder correct as the profile's
    parameter count changes.
    """
    pos: list[np.ndarray] = []
    fwhm: list[np.ndarray] = []
    for ip in range(len(model.phases)):
        for row in model.phase_peaks(ip, values):
            p = np.asarray(row[0], dtype=np.float64)
            good = np.isfinite(p)
            pos.append(p[good])
            fwhm.append(np.asarray(model.peak_fwhm(*row[1:-1]),
                                   dtype=np.float64)[good])
    if not pos:
        return np.zeros(0), np.zeros(0)
    return np.concatenate(pos), np.concatenate(fwhm)


def magnetic_channels(model, values, result, *,
                      min_peak_sigma: float = 5.0) -> np.ndarray:
    """Boolean mask of the channels the **nuclear** model puts nothing on.

    WP-1326's buckets 2 and 3, as channels rather than as counts: every
    positive residual peak of the nuclear-only fit that is *not* within the
    report's own validity radius of a calculated reflection, widened to that
    same radius.  Bucket 1 — a residual peak sitting on a nuclear line — is
    excluded on purpose, and it is the whole reason this region is worth
    defining: intensity there is a nuclear misfit or a k = 0 structure and this
    route cannot separate them, so scoring a magnetic model on it would reward
    a candidate for absorbing somebody else's error.

    One radius decides both halves, exactly as
    :mod:`rietx.report.satellites` argues: reusing a tighter tick tolerance for
    the exclusion and a wider one for the window would let a peak 0.10° from a
    nuclear line be called unexplained and then explained.
    """
    from ..report import _resid_norm
    from ..report.layer0 import residual_peak_indices
    from ..report.satellites import _FWHM_FALLBACK_DEG
    from ..report.schemas import VALIDITY_RADIUS_FWHM

    x = np.asarray(result.two_theta, dtype=np.float64)
    mask = np.zeros(x.size, dtype=bool)
    idx = residual_peak_indices(_resid_norm(result),
                                min_peak_sigma=min_peak_sigma)
    if idx.size == 0:
        return mask
    peaks = x[idx]
    pos, fwhm = _peak_positions_and_widths(model, values)
    if pos.size == 0:
        radius = np.full(peaks.size, VALIDITY_RADIUS_FWHM * _FWHM_FALLBACK_DEG)
    else:
        nearest = np.argmin(np.abs(peaks[:, None] - pos[None, :]), axis=1)
        radius = VALIDITY_RADIUS_FWHM * fwhm[nearest]
    ticks = np.asarray([t for positions in result.ticks.values()
                        for t in positions], dtype=np.float64)
    if ticks.size:
        on_tick = np.min(np.abs(peaks[:, None] - ticks[None, :]),
                         axis=1) <= radius
    else:
        on_tick = np.zeros(peaks.size, dtype=bool)
    for peak, r, drop in zip(peaks, radius, on_tick):
        if drop:
            continue
        mask |= np.abs(x - peak) <= r
    return mask


def r_magnetic(result, mask: np.ndarray) -> float | None:
    """Profile R over the magnetic-only channels: 1 explains none, 0 explains all.

    Σ|y_obs − y_calc| / Σ|y_obs − y_bkg| over :func:`magnetic_channels`'s mask.
    The denominator is the intensity *above the background* the region carries,
    so the number answers "how much of the intensity the nuclear model left
    there does this model account for" and is comparable between candidates
    fitted to the same pattern — which a whole-pattern Rwp, dominated by the
    nuclear lines, is not.

    ``None`` when the region is empty or carries no intensity above background,
    which is the honest empty state and never a zero.
    """
    if not mask.any():
        return None
    obs_all = np.asarray(result.y_obs, dtype=np.float64)
    if obs_all.size != mask.size:
        raise ValueError(
            f"solve_magnetic(): the magnetic-only region has {mask.size} "
            f"channels and this fit has {obs_all.size}. The region is a mask on "
            f"the nuclear fit's own grid, so every trial has to be fitted over "
            f"the same channels — see _fit()'s ``limits``. This is a bug, not "
            f"a condition to handle.")
    obs = obs_all[mask]
    calc = np.asarray(result.y_calc, dtype=np.float64)[mask]
    bkg = np.asarray(result.y_background, dtype=np.float64)[mask]
    denominator = float(np.sum(np.abs(obs - bkg)))
    if denominator <= 0.0:
        return None
    return float(np.sum(np.abs(obs - calc))) / denominator


# ---------------------------------------------------------------------------
# the pieces of the workflow
# ---------------------------------------------------------------------------
def _refuse_non_neutron(instrument, phase_name: str) -> None:
    kind = getattr(getattr(instrument, "source", None), "kind", None)
    if kind == "neutron_cw":
        return
    raise ValueError(
        f"solve_magnetic(): the histogram's source is {kind!r} and a moment "
        f"reaches a neutron histogram and nothing else "
        f"(model.forward.magnetic_wanted). On an X-ray pattern of "
        f"{phase_name!r} the position of a magnetic satellite and of a "
        f"superstructure reflection are the same and the inference is not: "
        f"the excess is a superlattice, a second phase or a nuclear misfit, "
        f"and refining a moment against it would fit a parameter with no "
        f"gradient anywhere. Bring a neutron pattern of the same specimen.")


def _magnetic_sites(phase, sites, species, ion, g=None) -> tuple[
        list[tuple[int, str, str]], dict[str, float | None],
        dict[str, tuple[str, str]], dict[str, float]]:
    """``([(atom index, label, form-factor key)], g_map, ion_assumed, g_assumed)``.

    A species is magnetic here when the form-factor table has a key for it;
    the *ion* is the key, and it is not ``Atom.species`` — the nuclear
    scattering length is keyed by nuclide and the form factor by oxidation
    state.  Where the species is itself a key (``"Mn"``, the neutral atom) it
    is used and the caveat says so; where it is not, the caller must name the
    ion, and the refusal lists the keys the table actually has for that
    element rather than picking one — *unless* the bare element resolves
    through :func:`~.crystallography.magnetic.form_factor.resolve_assumed_ion`
    (WP-1327), the same fallback
    :func:`~rietx.crystallography.cif.structure_from_cif` applies at read,
    which this candidate builder never called before.

    ``g_map`` is ``{label: g or None}`` for every site in the returned list —
    what to pass as ``Moment.g`` for it.  A caller-stated ``g`` (mirroring
    ``ion``: one float for every site, or a mapping from label or species)
    always wins.  Otherwise, when the site's ion was **not** itself stated by
    the caller (it came from the table directly, or from
    ``resolve_assumed_ion`` above) and needs an explicit Landé g
    (:func:`~.crystallography.magnetic.form_factor.needs_explicit_g`), its
    free-ion Hund's-rule g_J
    (:func:`~.crystallography.magnetic.form_factor.assumed_lande_g`) is used
    — mirroring issue #257 A5's rule that an absent g beside a *caller-stated*
    ion is the caller's own gap, unrelated to this default.  ``None``
    everywhere else, bit-identical to never having passed a ``g`` at all.

    ``ion_assumed``/``g_assumed`` are ``{label: (ion, reason)}``/
    ``{label: g}`` for exactly the sites this call defaulted, so the caller
    can report ``MAGNETIC_ION_ASSUMED``/``LANDE_G_ASSUMED`` the same way
    :func:`~.crystallography.magcif.magnetic_diagnostics` does for the CIF
    reader.
    """
    table = set(magnetic_ions())
    keys = None if ion is None or isinstance(ion, str) else dict(ion)
    g_keys = None if g is None or isinstance(g, (int, float)) else dict(g)
    labels = {a.label for a in phase.atoms}
    species_present = {a.species for a in phase.atoms}
    # a name that matches nothing is a *typo*, and saying "no site carries a
    # magnetic form factor" would send the caller looking at the form-factor
    # table instead of at the label they mistyped
    unknown = sorted(set(sites or ()) - labels)
    if unknown:
        raise ValueError(
            f"solve_magnetic(): sites={unknown} name no atom of "
            f"{phase.name!r}, whose labels are {sorted(labels)}. Labels come "
            f"from the structure as it was read — a CIF's own "
            f"_atom_site_label, not the element symbol.")
    unknown = sorted(set(species or ()) - species_present)
    if unknown:
        raise ValueError(
            f"solve_magnetic(): species={unknown} is not a species of "
            f"{phase.name!r}, which has {sorted(species_present)}.")
    chosen: list[tuple[int, str, str]] = []
    g_map: dict[str, float | None] = {}
    ion_assumed: dict[str, tuple[str, str]] = {}
    g_assumed: dict[str, float] = {}
    for j, atom in enumerate(phase.atoms):
        if sites is not None and atom.label not in sites:
            continue
        if species is not None and atom.species not in species:
            continue
        key = None
        caller_stated_ion = False
        if keys is not None and atom.label in keys:
            key = keys[atom.label]
            caller_stated_ion = True
        elif keys is not None and atom.species in keys:
            key = keys[atom.species]
            caller_stated_ion = True
        elif isinstance(ion, str) and (sites is not None or species is not None):
            key = ion
            caller_stated_ion = True
        elif atom.species in table:
            key = atom.species
        else:
            assumed = resolve_assumed_ion(atom.species)
            if assumed is not None:
                key, reason = assumed
                ion_assumed[atom.label] = (key, reason)
        if key is None:
            if sites is not None or species is not None:
                element = "".join(c for c in atom.species if c.isalpha())
                offered = sorted(k for k in table if k.startswith(element))
                raise ValueError(
                    f"solve_magnetic(): {atom.label!r} was named as a magnetic "
                    f"site but its species {atom.species!r} is not a magnetic "
                    f"form-factor key. Pass ion= with the oxidation state; the "
                    f"table has {offered or 'nothing for this element'}.")
            continue
        chosen.append((j, atom.label, key))
        if g_keys is not None and atom.label in g_keys:
            g_map[atom.label] = float(g_keys[atom.label])
        elif g_keys is not None and atom.species in g_keys:
            g_map[atom.label] = float(g_keys[atom.species])
        elif isinstance(g, (int, float)):
            g_map[atom.label] = float(g)
        elif not caller_stated_ion and needs_explicit_g(key):
            default_g = assumed_lande_g(key)
            if default_g is not None:
                g_map[atom.label] = default_g
                g_assumed[atom.label] = default_g
            else:
                g_map[atom.label] = None
        else:
            g_map[atom.label] = None
    if not chosen:
        raise ValueError(
            "solve_magnetic(): no site of this phase carries a magnetic form "
            "factor. Name the sites with sites=['Mn1'] or the species with "
            "species=['Mn'], and the form-factor key with ion='Mn3+'.")
    return chosen, g_map, ion_assumed, g_assumed


def _k_from_the_report(evidence, top_k: int):
    """The k step: what WP-1326's arm says, and which of the three routes it is.

    Returns ``(list of k, route, reason)``.  An empty list is an abstention and
    the reason says why.  The forbidden-lattice-point bucket is checked
    **first** and short-circuits the candidate ranking entirely: that excess is
    the k = 0 signature and scoring it against a candidate k would rank a
    hypothesis against evidence that is not about it.
    """
    if evidence is None:
        return [], "no satellite arm", (
            "the report carried no satellite arm for this phase — give the "
            "propagation vector with k=")
    if evidence.excess_on_absent_lattice_lines > 0:
        return [(Fraction(0), Fraction(0), Fraction(0))], "forbidden lattice points", (
            f"{evidence.excess_on_absent_lattice_lines} residual peak(s) sit on "
            f"a reciprocal-lattice point the nuclear structure factor forbids. "
            f"No nuclear model, right or wrong, puts intensity at a systematic "
            f"absence, so this is the k = 0 signature stated positively and the "
            f"candidate-k ranking is not consulted")
    scored = [c for c in evidence.candidates if c.matched > 0]
    if scored:
        return ([tuple(Fraction(v) for v in c.k) for c in scored[:top_k]],
                "satellite ranking",
                f"{evidence.n_unexplained} unexplained peak(s); the top "
                f"candidate {scored[0].vector} accounts for {scored[0].matched} "
                f"of them ({evidence.generator})")
    if evidence.n_unexplained == 0 and evidence.excess_on_nuclear_lines == 0:
        return [], "nothing to solve", (
            f"{evidence.n_residual_peaks} positive residual peak(s) and none of "
            f"them is unexplained: the nuclear model accounts for the pattern "
            f"and there is no magnetic intensity to model")
    if evidence.n_unexplained == 0:
        return [], "nothing to solve", (
            f"every one of the {evidence.excess_on_nuclear_lines} residual "
            f"peak(s) sits on a calculated reflection. That is a nuclear "
            f"misfit or a k = 0 structure and this route cannot separate them "
            f"(WP-1326); a pattern of the same specimen above its ordering "
            f"temperature is what separates them. Nothing here is a magnetic "
            f"hypothesis on its own")
    return [], "no candidate k", (
        f"{evidence.n_unexplained} peak(s) are unexplained and no candidate of "
        f"{evidence.generator} indexes any of them. The candidate set is "
        f"enumerated, so an incommensurate k, or any commensurate k the "
        f"generator does not list, is outside it by construction — pass k= or "
        f"another generator=")


def _seed(group, position, cell, magnitude):
    """A seed moment inside the candidate's own allowed subspace, or ``None``.

    ``moment_frame``'s rows are an orthonormal basis of the subspace under the
    crystal-axis cosine metric, so a unit-coefficient combination of them has
    modulus 1 and ``magnitude`` is the modulus in μ_B, not a component.
    Seeding outside the family would state a structure the candidate forbids
    and let the first stage walk back into it, which is a fit of a different
    model than the one the row is labelled with — so every coefficient below
    is a combination of the candidate's *own* rows, never a component stated
    directly.

    **Every row beyond the first gets a small, deterministic, nonzero
    coefficient** (:data:`SOLVE_SEED_TILT`), not zero.  A basis of rank 1 (the
    ordinary case: one copy, one free real amplitude) is unaffected — there is
    only one row, and the prior behaviour (the whole magnitude on it) is
    exact.  A basis of rank ≥ 2 (a multi-copy irrep merged across sites, or a
    genuinely general/kernel direction, both real and enumerated by
    :func:`~rietx.crystallography.magnetic.isotropy.candidates`) used to place
    the whole magnitude on row 0 alone and leave every other DOF starting at
    the exact point of pointing along it — :data:`SOLVE_SEED_TILT`'s own
    docstring names why that is not simply "a smaller seed" but a stationary
    one for several of these groups.  Normalised so the combined vector still
    has modulus exactly ``magnitude``, since the rows are metric-orthonormal
    and a coefficient vector of unit Euclidean norm therefore gives a unit
    modulus automatically.
    """
    basis = group.allowed_moment_basis(position)
    if len(basis) == 0:
        return None
    return tuple(float(v) for v in tilted_seed(basis, cell, magnitude,
                                               tilt=SOLVE_SEED_TILT))


def _state_k0(parent_phase, candidate: MagneticCandidate, magnetic, magnitude,
              g_map=None):
    """The candidate as a k = 0 magnetic phase in the parent's own cell."""
    ops, cent = candidate.group.xyz_strings()
    cell = parent_phase.cell.lengths_angles()
    atoms = list(parent_phase.atoms)
    g_map = g_map or {}
    placed = 0
    for j, label, ion in magnetic:
        atom = atoms[j]
        seed = _seed(candidate.group,
                     (atom.x.value, atom.y.value, atom.z.value), cell, magnitude)
        if seed is None:
            continue
        atoms[j] = atom.model_copy(update={
            "moment": Moment.from_values(seed, ion, g=g_map.get(label), vary=True)})
        placed += 1
    if not placed:
        return None
    return parent_phase.model_copy(update={
        "atoms": atoms,
        "magnetic_symmetry": MagneticSymmetry(
            operations=list(ops), centerings=list(cent),
            bns_number=candidate.identification.bns_number
            if candidate.identification else None,
            uni_number=candidate.identification.uni_number
            if candidate.identification else None,
            og_number=candidate.identification.og_number
            if candidate.identification else None)})


def _state_k0_warm(parent_phase, candidate: MagneticCandidate, magnetic,
                   winner_structure, g_map=None):
    """Like :func:`_state_k0`, seeded from ``winner_structure``'s own
    converged moments rather than a flat magnitude (issue #390's descent
    audit).

    ``candidate`` is a subgroup of the winner by construction here
    (:func:`_maximal_subgroups` only ever returns one), so the winner's own
    moment at each atom already lies inside ``candidate``'s larger allowed
    span exactly and :func:`~rietx.crystallography.magnetic.moments.
    warm_seed` keeps it, tilting only the genuinely new DOFs off zero.
    """
    ops, cent = candidate.group.xyz_strings()
    cell = parent_phase.cell.lengths_angles()
    atoms = list(parent_phase.atoms)
    g_map = g_map or {}
    winner_moments = {a.label: a.moment.values()
                      for a in winner_structure.phases[0].atoms
                      if a.moment is not None}
    placed = 0
    for j, label, ion in magnetic:
        atom = atoms[j]
        basis = candidate.group.allowed_moment_basis(
            (atom.x.value, atom.y.value, atom.z.value))
        if len(basis) == 0:
            continue
        preferred = winner_moments.get(label, (0.0, 0.0, 0.0))
        seed = warm_seed(basis, cell, preferred)
        atoms[j] = atom.model_copy(update={
            "moment": Moment.from_values(seed, ion, g=g_map.get(label), vary=True)})
        placed += 1
    if not placed:
        return None
    return parent_phase.model_copy(update={
        "atoms": atoms,
        "magnetic_symmetry": MagneticSymmetry(
            operations=list(ops), centerings=list(cent),
            bns_number=candidate.identification.bns_number
            if candidate.identification else None,
            uni_number=candidate.identification.uni_number
            if candidate.identification else None,
            og_number=candidate.identification.og_number
            if candidate.identification else None)})


def _operator_set(group) -> frozenset:
    """A magnetic group's own operator list, as a hashable set of magCIF xyz
    strings — the same representation :func:`_merge_classes` already uses to
    test two candidates' groups for equality, reused here to test one for
    *containment* in another (issue #390's descent audit and tie lattice)."""
    ops, cent = group.xyz_strings()
    return frozenset(ops) | frozenset(cent)


def _maximal_subgroups(winner_candidate: MagneticCandidate, classes):
    """Every *other* class at the winner's own k whose magnetic group is a
    genuine operator-list subgroup of the winner's, keeping only the maximal
    ones (issue #390's descent audit).

    "Maximal" is with respect to the other subgroups found here, not to every
    conceivable subgroup of the winner: one properly contained in another
    found subgroup is dropped, because refitting it would only ever repeat
    what the larger one already tests.
    """
    winner_ops = _operator_set(winner_candidate.group)
    found = []
    for index, (members, candidate, site_label) in enumerate(classes):
        if candidate is winner_candidate:
            continue
        ops = _operator_set(candidate.group)
        if ops < winner_ops:
            found.append((index, members, candidate, site_label, ops))
    maximal = []
    for i, row in enumerate(found):
        if any(j != i and row[4] < found[j][4] for j in range(len(found))):
            continue
        maximal.append(row[:4])
    return maximal


def _descend(parent, winner_trial: "MagneticTrial",
            winner_candidate: MagneticCandidate, classes, magnetic, g_map,
            plan, instrument, data, limits, tie_width: float, zero: bool
            ) -> tuple[tuple["SubgroupAudit", ...], str, tuple[Diagnostic, ...]]:
    """Issue #390's descent audit: one step down the winner's own group-subgroup
    lattice, refit from its solution, reported against it by ΔBIC.

    Only a k = 0 statement is warm-started today — a k != 0 supercell's
    child cell can differ in atom count between two candidates, and matching
    them up is future work, flagged rather than attempted.
    """
    from ..report.layer2 import delta_bic

    if not zero:
        return (), ("descent audit not attempted: only a k = 0 statement is "
                    "warm-started from the winner today"), ()
    maximal = _maximal_subgroups(winner_candidate, classes)
    if not maximal:
        return (), (f"no subgroup supported at ΔBIC < {tie_width:.1f} (none "
                    f"of the classes already enumerated at this k is a "
                    f"genuine operator-list subgroup of the winner)"), ()
    owners = [label for _j, label, _i in magnetic]
    chi2_winner = _chi2_absolute(winner_trial._result.statistics)
    n_points = int(winner_trial._result.statistics.n_points)
    # the winner is the restricted model here, so its count is charged
    n_effective = _effective_count(winner_trial._result)
    audits: list[SubgroupAudit] = []
    beat: list[tuple[float, MagneticCandidate]] = []
    #: subgroups whose refit stopped short of a minimum: their χ² is an upper
    #: bound, so a margin that beats the winner still does, and one that does
    #: not is the budget's answer rather than the data's
    short: list[str] = []
    for _index, _members, candidate, _site_label in maximal:
        try:
            child = _state_k0_warm(parent, candidate, magnetic,
                                   winner_trial._structure, g_map)
            if child is None:
                audits.append(SubgroupAudit(
                    bns_number=candidate.bns_number, label=candidate.label,
                    n_moment_parameters=None, delta_bic_over_winner=None,
                    status="refused",
                    refusal="forbids a moment on every named site"))
                continue
            child_structure = Structure(phases=[child])
            (_start, ref, result), _n_starts, _n_minima = _best_start(
                _starts(child_structure, instrument, data, plan, True,
                       owners, limits))
        except Exception as exc:      # noqa: BLE001 - reported, never swallowed
            audits.append(SubgroupAudit(
                bns_number=candidate.bns_number, label=candidate.label,
                n_moment_parameters=None, delta_bic_over_winner=None,
                status="refused", refusal=f"{type(exc).__name__}: {exc}"))
            continue
        _moments, n_moment, _pair = _moment_rows(ref, result, ref.fitted_structure)
        chi2_sub = _chi2_absolute(result.statistics)
        margin = delta_bic(chi2_winner, chi2_sub, n_points,
                           n_moment - winner_trial.n_moment_parameters,
                           n_effective=n_effective)
        audits.append(SubgroupAudit(
            bns_number=candidate.bns_number, label=candidate.label,
            n_moment_parameters=n_moment, delta_bic_over_winner=margin,
            status="refined"))
        if result.status != "converged":
            short.append(f"{candidate.label} ({result.status!r})")
        if margin > tie_width:
            beat.append((margin, candidate))
    if beat:
        beat.sort(key=lambda row: -row[0])
        margin, candidate = beat[0]
        diagnostics = (Diagnostic(
            level="warning", code="MAGNETIC_SUBGROUP_PREFERRED",
            message=(f"The descent audit found {candidate.label} "
                     f"({candidate.bns_number}), a subgroup of the winner "
                     f"{winner_trial.label} ({winner_trial.bns_number}), "
                     f"that beats it by {margin:.1f} BIC (tie width "
                     f"{tie_width:.1f}) once refit from the winner's own "
                     f"converged solution."),
            suggestion="Choose between the two groups by hand.",
            value=margin),)
        note = (f"MAGNETIC_SUBGROUP_PREFERRED: {candidate.label} "
                f"({candidate.bns_number}) beats the winner by {margin:.1f} BIC")
        return tuple(audits), note, diagnostics
    refined_margins = [a.delta_bic_over_winner for a in audits
                       if a.delta_bic_over_winner is not None]
    best = max(refined_margins) if refined_margins else None
    note = (f"no subgroup supported at ΔBIC < {tie_width:.1f}" if best is None
            else f"no subgroup beats the winner beyond the tie width of "
                 f"{tie_width:.1f} (best {best:.1f})")
    if short:
        note += (f"; not settled for {', '.join(short)}, whose refit stopped "
                 f"short of a minimum after {SOLVE_MAX_CONTINUATIONS} "
                 f"continuations of its budget")
    return tuple(audits), note, ()


def _tie_lattice_lines(trials, tied) -> list[str]:
    """Issue #390's tie lattice: which tied class is a subgroup of which, by the
    operator lists the trials themselves already carry — data only, never a
    new ranking rule.  ``tied`` is :attr:`MagneticSolution.tied`.
    """
    by_index = {t.class_index: t for t in trials}
    rows = [by_index[i] for i in tied if i in by_index]
    groups: dict[int, frozenset] = {}
    for t in rows:
        if t._structure is None:
            continue
        msym = t._structure.phases[0].magnetic_symmetry
        if msym is None:
            continue
        groups[t.class_index] = frozenset(msym.operations) | frozenset(msym.centerings)
    lines = []
    for a_i, a in enumerate(rows):
        for b in rows[a_i + 1:]:
            ga, gb = groups.get(a.class_index), groups.get(b.class_index)
            if ga is None or gb is None:
                lines.append(f"class {a.class_index} ({a.label}), class "
                            f"{b.class_index} ({b.label}): not comparable "
                            f"(no stored operator list)")
            elif ga == gb:
                lines.append(f"class {a.class_index} ({a.label}) = class "
                            f"{b.class_index} ({b.label}): the same magnetic "
                            f"group")
            elif ga < gb:
                lines.append(f"class {a.class_index} ({a.label}) is a "
                            f"subgroup of class {b.class_index} ({b.label})")
            elif gb < ga:
                lines.append(f"class {b.class_index} ({b.label}) is a "
                            f"subgroup of class {a.class_index} ({a.label})")
            else:
                lines.append(f"class {a.class_index} ({a.label}), class "
                            f"{b.class_index} ({b.label}): unrelated")
    return lines


def _supercell(parent, candidate, *, species, ions, magnitude, nuclear_group,
               g=None):
    """The supercell statement, falling back to the magnetic group's nuclear part.

    ``nuclear_group="parent"`` is right whenever the child lattice is invariant
    under the parent's point group, and it keeps every constraint the parent's
    symmetry puts on the nuclear model.  For a k that **lowers the crystal
    class** there is no such option: the parent group is not a group of the
    child cell at all, and ``MagneticGroup.transformed``'s integrality guard
    says so by name.  WP-1327's supercell rung names the remedy — state the
    child under the magnetic
    group's own nuclear part — and this is that remedy taken automatically,
    because a workflow that abstained here would abstain on a whole family of
    propagation vectors for a reason that has a documented answer.

    Returns ``(statement, which setting was used)`` so the caller can say which
    it was; the fallback is never silent.
    """
    try:
        return (magnetic_supercell(
            parent, candidate, magnetic_species=species, ion=ions, g=g,
            magnitude=magnitude, nuclear_group=nuclear_group), nuclear_group)
    except ValueError as exc:
        # Two refusals have this remedy: the child lattice is not invariant
        # under the parent point group ("onto a lattice"), and the parent's
        # operations carry a translation the child cell cannot write in any
        # Hermann-Mauguin setting ("no Hermann-Mauguin symbol reproduces" —
        # Pnma at k = (1/2, 0, 1/2), as in Ba₂FeSbSe₅, where a glide's half becomes
        # a quarter).  Anything else is a real refusal and propagates.
        recoverable = ("onto a lattice" in str(exc)
                       or "no Hermann-Mauguin symbol reproduces" in str(exc)
                       # the child of an unnamed group is now *stated*
                       # rather than refused, so what stops the ``parent``
                       # route for a class-lowering k is the refusal that was
                       # always underneath the symbol one — the magnetic orbit
                       # being smaller than the nuclear one.  Same remedy, so
                       # the same fallback: ``magnetic_supercell`` refuses it at
                       # build for exactly this reason.
                       or "determines no moment for that atom" in str(exc))
        if nuclear_group != "parent" or not recoverable:
            raise
    return (magnetic_supercell(
        parent, candidate, magnetic_species=species, ion=ions, g=g,
        magnitude=magnitude, nuclear_group="magnetic"), "magnetic")


def _fit(structure, instrument, data, plan, ties=None, limits=None, hold=()):
    """One trial fit, with the anti-centring ties applied before anything moves.

    ``limits`` is the incoming nuclear fit's own 2θ range, and passing it is a
    **correctness** requirement rather than tidiness: the magnetic-only region
    is a channel mask taken on that fit, and ΔBIC compares two χ² over the same
    observations.  A trial fitted over a wider range than its reference would
    be compared with a different N on different data, and the mask would not
    even line up — measured, as a shape error, on a pattern whose first two
    detector channels were excluded.

    ``hold`` is a list of globs the fit may not move, whatever a stage names
    (``Refinement.hold``): a plan's own spelling of one cannot free it, the
    continuation fits included.
    """
    from ..refine import Refinement

    ref = Refinement(structure, instrument.model_copy(deep=True))
    # a trial, so no automatic profile interval either (WP-2002): ``_fit``
    # cannot tell the winner's fit from the rest, and each interval costs
    # 20-32 refits an angle left out of the covariance
    ref._auto_intervals = False
    if hold:
        ref.hold(list(hold))
    for target, source, scale, offset in (ties or ()):
        ref.tie(target, source, scale=scale, offset=offset)
    # ``telemetry=False`` on every fit here: a fit whose result the package
    # discards (the reference, the losing starts, each continuation, every
    # audit refit) is a trial, not a run, and ``_fit`` cannot tell the
    # winner's fit from the rest (root CLAUDE.md, "Every fit records itself").
    result = ref.fit(data, plan=plan, two_theta_limits=limits,
                     telemetry=False)
    # A budget stop is the budget's answer, not the data's, and ΔBIC compares
    # two of them: continued from where it stopped, with everything the plan
    # freed by its end (staging is cumulative) and the last stage's budget and
    # tolerance, at most SOLVE_MAX_CONTINUATIONS times.  Whatever status the
    # last one returns is the fit's (``MagneticTrial.fit_status``).
    last = plan.stages[-1]
    freed = list(dict.fromkeys(g for st in plan.stages for g in st.turn_on))
    for _n in range(SOLVE_MAX_CONTINUATIONS):
        if result.status != "max_iter":
            break
        # the plan's absent-phase hold and correlation guard carry into the
        # continuation, or a trial run with the hold off would be continued
        # under the default (WP-2002)
        result = ref.fit(data, plan=RefinementPlan(stages=[Stage(
            f"{last.name} (continued)", freed, max_iter=last.max_iter,
            ftol=last.ftol)], phase_support_sigma=plan.phase_support_sigma,
            correlation_guard=plan.correlation_guard,
            # and its closing stage, so a continued trial ends on the windows
            # every other trial's χ² was measured on (WP-2002)
            closing_window_tol=plan.closing_window_tol),
            two_theta_limits=limits, telemetry=False)
    return ref, result


def _close(trial: MagneticTrial, data, limits, mask) -> MagneticTrial:
    """The winner, its fit ended in a closing stage (WP-2002, ruled 2026-10-22).

    The trials a package-chosen plan ranks run at the declared stages'
    windows and stop there, because ΔBIC compares their χ² with a reference's
    at one precision.  The winner's moments are the answer, and at those
    windows their esds carry the misfit of the peak tails the windows drop:
    1.61× the closing stage's on the two-site Pnma test, 0.00242 against
    0.00151 μ_B.  So the winner continues from its own fit with the closing
    stage its plan would have run (``RefinementPlan.closing_stage``, every
    glob the plan freed, at ``CLOSING_WINDOW_TOL``), and its Rwp, GoF, R_mag,
    moments, held list and status are that fit's.  Its ΔBIC stays the
    ranking's.
    """
    plan = replace(trial._plan, closing_window_tol=CLOSING_WINDOW_TOL)
    ref = trial._refinement
    result = ref.run_stage(data, plan.closing_stage(), two_theta_limits=limits,
                           correlation_guard=plan.correlation_guard,
                           phase_support_sigma=plan.phase_support_sigma,
                           telemetry=False)
    moments, _n, _pairs = _moment_rows(ref, result, ref.fitted_structure)
    # measured on the moments it is reported beside, where the trial took one
    drift = (None if trial.anti_translation_drift is None
             else anti_translation_residual(ref.fitted_structure.phases[0]))
    return replace(trial, rwp=float(result.statistics.rwp),
                   gof=float(result.statistics.gof),
                   r_magnetic=r_magnetic(result, mask), moments=moments,
                   held=tuple(result.stages[-1].held) if result.stages else (),
                   anti_translation_drift=drift,
                   fit_status=result.status, _structure=ref.fitted_structure,
                   _result=result)


def _moment_owner(label: str, owners: Sequence[str]) -> str | None:
    """Which parent site a child atom's label belongs to.

    A supercell statement names a child atom after the parent site it came from
    (``Co3`` → ``Co3_1``, ``Co3_2``), so the prefix is the link between the
    child's independent moment DOFs and the parent orbit a one-site start is
    about.  Longest match first, because ``Co1`` is a prefix of nothing but
    ``Co1x`` would be.
    """
    for owner in sorted(owners, key=len, reverse=True):
        if label == owner or label.startswith(owner + "_"):
            return owner
    return None


def _keep_only(structure, owners: Sequence[str], keep: str):
    """The same structure with every magnetic site but ``keep``'s moment absent.

    ``moment=None``, not a small moment: the measurement that made this
    necessary showed that seeding the other amplitudes small does **not**
    escape the minimum — with a Co3 seed the flat-start fit returns the same
    Rwp to five decimals.  The other amplitudes have to be *absent while the
    rest of the model converges*, and only then released.
    """
    phase = structure.phases[0]
    atoms = []
    for atom in phase.atoms:
        owner = (None if atom.moment is None
                 else _moment_owner(atom.label, owners))
        atoms.append(atom if owner in (None, keep)
                     else atom.model_copy(update={"moment": None}))
    return Structure(phases=[phase.model_copy(update={"atoms": atoms})])


def _release(fitted, seeded):
    """Put the absent moments back, at a fraction of their original seed.

    ``fitted`` is the one-site leg's converged structure and ``seeded`` the
    full statement it was cut down from; the sites that were held out come back
    at :data:`SOLVE_RELEASE_FRACTION` of the seed they would have started at,
    which is near the submodel the leg reached rather than at the flat point
    the sweep exists to get away from.
    """
    original = {a.label: a.moment for a in seeded.phases[0].atoms
                if a.moment is not None}
    phase = fitted.phases[0]
    atoms = []
    for atom in phase.atoms:
        block = original.get(atom.label)
        if atom.moment is not None or block is None:
            atoms.append(atom)
            continue
        atoms.append(atom.model_copy(update={"moment": Moment.from_values(
            tuple(SOLVE_RELEASE_FRACTION * v for v in block.values()),
            block.ion, g=block.g, vary=True)}))
    return Structure(phases=[phase.model_copy(update={"atoms": atoms})])


def _parent_site_ties(statement) -> tuple[tuple[str, str, float, float], ...]:
    """Ties that make every child Biso the Biso of the first child atom of the
    same parent atom (``SupercellStatement.site_map``), as ``_fit`` takes them.

    The one derivation is ``representation.distortion.parent_site_ties``,
    which ``displacive_statement`` calls too (Yue, #724: "the derivation should
    be written once")."""
    from ..crystallography.representation.distortion import parent_site_ties

    return parent_site_ties([parent_atom for parent_atom, _coset in statement.site_map])


def _without_cell(plan: RefinementPlan) -> RefinementPlan:
    """``plan`` with every ``phases.*.cell.*`` entry left out of every stage.

    Only the exact spelling: a plan naming the cell another way is held by
    ``_fit(hold=_CELL_HOLD)``, which is what actually keeps it fixed.  Every
    other field of the plan is kept.
    """
    return replace(plan, stages=[
        replace(stage, turn_on=[p for p in stage.turn_on
                                if p != "phases.*.cell.*"])
        for stage in plan.stages])


#: the globs a tied (``tie_to_parent``) trial holds, whatever its plan names
_CELL_HOLD = ("phases.*.cell.*",)


def _starts(child_structure, instrument, data, plan, zero: bool,
            owners: Sequence[str], limits=None, extra_ties=()):
    """Every start for one candidate, converged; the flat one plus one per site.

    **Why a sweep at all.**  A moment stage with several magnetic sites is not
    a convex problem, and the flat unit-magnitude seed can land in a minimum
    that is *provably* not the optimum: measured on Ba₆Co₆ (the GSAS-II
    Magnetic-III tutorial pattern, not vendored) under a nuclear model as
    complete as the tutorial's, the three-amplitude fit reaches
    Rwp 0.08952 while its own **one-amplitude submodel** reaches 0.08867 — a
    superset model cannot fit worse at the true minimum, so the superset was
    not at one.  Released from the one-site solution the same three-amplitude
    model reaches 0.08752, on the other site, which is the published answer.

    That is fatal to a *ranking* and not merely to a fit: candidates compared
    at non-optimal points are compared at whatever minimum their seed happened
    to fall into, and the ΔBIC ordering then measures the seed.  So a class
    with more than one magnetic site is refined from every one-site start as
    well as the flat one, and the best converged minimum is the one reported.

    A single-site class has one start, because there is nothing to hold out.
    """
    ties = None if zero else anti_translation_ties(child_structure.phases[0], 0)
    if extra_ties:
        ties = list(ties or ()) + list(extra_ties)
    hold = _CELL_HOLD if extra_ties else ()
    out = [("flat", *_fit(child_structure, instrument, data, plan, ties,
                          limits, hold))]
    if len(owners) < 2:
        return out
    for keep in owners:
        reduced = _keep_only(child_structure, owners, keep)
        cut_ties = (None if zero
                    else anti_translation_ties(reduced.phases[0], 0))
        if extra_ties:
            cut_ties = list(cut_ties or ()) + list(extra_ties)
        leg, _first = _fit(reduced, instrument, data, plan, cut_ties, limits, hold)
        released = _release(leg.fitted_structure, child_structure)
        out.append((f"{keep} only, then released",
                    *_fit(released, instrument, data, plan, ties, limits, hold)))
    return out


def _best_start(starts):
    """The lowest-χ² start, and how many distinct minima the sweep found.

    Every start ends with the same free set on the same data, so the absolute
    weighted residual sum of squares compares them directly — this is one model
    at several minima, not two models.
    """
    ranked = sorted(starts, key=lambda s: _chi2_absolute(s[2].statistics))
    rwps = sorted(float(s[2].statistics.rwp) for s in starts)
    minima = 1 if not rwps else 1 + sum(
        1 for a, b in zip(rwps, rwps[1:])
        if abs(b - a) > SOLVE_MINIMUM_RTOL * max(abs(a), 1e-12))
    return ranked[0], len(starts), minima


def _dead_globs(plan, result) -> tuple[str, ...]:
    """Stage free-list globs that freed nothing — reported, never silent.

    A ``Stage`` entry matching no parameter is accepted without a word, and the
    two ways that happens are a typo and a term this histogram's forward model
    does not read, which changes Rwp in no digit.  In a
    ranking that is not a wasted line: it makes the models that were compared
    differ from the ones the caller believes were compared, so it goes in the
    answer's caveats.
    """
    import fnmatch

    freed = [p.path for p in result.parameters if p.vary]
    dead = []
    for stage in plan.stages:
        for glob in stage.turn_on:
            if not any(fnmatch.fnmatch(path, glob) for path in freed):
                dead.append(glob)
    return tuple(dict.fromkeys(dead))


def _moment_rows(ref, result, structure
                 ) -> tuple[tuple[MomentRow, ...], int, tuple[Diagnostic, ...]]:
    """The report's moment arm as rows, how many moment DOFs stayed free, and
    any ``MOMENT_PAIR_DEGENERATE`` diagnostic the pairing found."""
    from ..report.magnetic import analyse_moments, moment_pair_diagnostics

    n_moment = sum(1 for p in result.parameters
                   if _MOMENT_GLOB in p.path and p.vary)
    # ``analyse_moments`` rather than ``ref.report()``: this is the one arm the
    # workflow needs and a whole Layer-0/1/2 report per trial would cost more
    # than the fit that produced it.  WP-1327's own writer either way — the
    # ``supported`` ratio, the held directions and the degenerate pairing are not
    # recomputed here.
    evidence = analyse_moments(
        ref._model, _values_of(ref), structure,
        held=list(result.stages[-1].held) if result.stages else [],
        esd={p.path: p.stderr for p in result.parameters
             if p.stderr is not None},
        correlations=_moment_correlations(ref, result))
    rows = [
        MomentRow(label=e.atom, ion=e.ion, magnitude=float(e.magnitude),
                  esd=None if e.magnitude_esd is None
                  else float(e.magnitude_esd),
                  crystalaxis=tuple(float(v) for v in e.crystalaxis),
                  supported=bool(e.supported),
                  unmeasured_directions=tuple(e.unmeasured_directions),
                  paired_with=tuple(e.paired_with),
                  paired_magnitude=e.paired_magnitude,
                  paired_magnitude_esd=e.paired_magnitude_esd)
        for e in evidence]
    return tuple(rows), n_moment, tuple(moment_pair_diagnostics(evidence))


def _named_for_class(diagnostics, class_index: int, k) -> tuple[Diagnostic, ...]:
    """``diagnostics`` of one class's moment rows, each message opening with the
    class (and the propagation vector when it is not Γ) it came from.

    The solution carries the pairs of **every** class of every k tried, and a
    pair's ``where`` is two parameter paths that two classes share, so without
    the class a pair found for a rival reads as the winner's (#742)."""
    where = f"class {class_index}"
    if any(c != 0 for c in k):
        where += " (k = (" + ", ".join(str(c) for c in k) + "))"
    return tuple(d.model_copy(update={"message": f"{where}: {d.message}"})
                 for d in diagnostics)


def _moment_correlations(ref, result):
    """The correlated pairs the degenerate-pair fold reads: every pair of free
    moment moduli, with ρ taken from the covariance their σ's came from.

    The fold multiplies ρ by the two rows' esds, and the pair esd is a
    cancellation of order (1 − |ρ|), so ρ and the σ's must come from one
    compile — the answer-producing stage's, which
    :attr:`~rietx.Refinement._answer_covariance` keeps beside the result.

    **Two sources this used to read, and why neither is enough.**
    ``identifiability.top_correlations`` is final-stage but only the worst
    :data:`~rietx.optimize.identifiability.TOP_CORRELATIONS_K` pairs of the
    whole fit, and a fit that also frees coordinates (or a child cell with
    exactly degenerate Biso twins) can fill every slot with ρ = 1 pairs:
    measured on a two-Co-site entry of issue #458's MAGNDATA sweep with the
    coordinates free, the moment pair at ρ = −1.000 was absent from the list
    and the fold never ran.  The stored ``HIGH_CORRELATION``/``FLAT_DIRECTION``
    findings carry such a pair, but ``_dedup_high_correlations`` keeps the
    **worst |ρ| across every stage** ("flagged in stages: moment, all"), and an
    earlier stage, with fewer parameters free, typically has the larger |ρ|.
    Measured on Cr₂WO₆ at 150 K (the tree's tutorial data, review of #592):
    the moment stage's ρ = −0.99821 against the final stage's −0.98591, and
    the final σ's with the moment stage's ρ gave a pair esd of 0.089 μ_B where
    the final stage's own covariance gives 0.247 — a 2.8× error toward false
    support.  So neither is read for a moment pair.

    Only **free** moduli are paired: a tied row shares its source's column and
    would correlate at ±1 by construction, which is a tie and not a powder
    degeneracy.  ``None`` when the fit kept no covariance (no esds, or
    ``ref`` holds another result's), exactly as before: a fit whose
    covariance was not measured reports each modulus on its own.
    """
    from ..schemas.results import CorrelationPair

    kept = getattr(ref, "_answer_covariance", None)
    if kept is None or kept[0] is not result or kept[3] is None:
        return None
    _result, table, theta, stderr_internal, correlation = kept
    paths = [p.path for p in result.parameters
             if p.vary and p.stderr is not None and _MOMENT_GLOB in p.path
             and p.path.endswith(".dof0")]
    if len(paths) < 2:
        return None
    cov = table.physical_covariance(theta, stderr_internal, correlation, paths)
    var = np.diag(cov)
    pairs = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            if var[i] > 0.0 and var[j] > 0.0:
                pairs.append(CorrelationPair(
                    path_a=paths[i], path_b=paths[j],
                    rho=float(cov[i, j] / math.sqrt(var[i] * var[j]))))
    return pairs or None


def _values_of(ref):
    """The decoded parameter values of a refinement's fitted state."""
    from ..params.vector import ParameterTable

    table = ParameterTable(ref.structure, ref.instrument)
    return table.decode(table.x0())


def _chi2_absolute(stats) -> float:
    """The weighted residual sum of squares ``delta_bic`` wants.

    ``Statistics.chi2`` is the reduced χ² and the two models have different P,
    so dividing by their own degrees of freedom first would fold a second,
    unwanted ratio into the comparison.  The same reasoning, and the same
    arithmetic, as ``indexing.extinction._chi2_absolute``; imported rather than
    rewritten so the package keeps one form.
    """
    from ..indexing.extinction import _chi2_absolute as absolute

    return absolute(stats)


def _solve_inflation(result) -> float | None:
    """The Bérar-Lelann factor ``result``'s solve multiplied its esds by.

    Read off a row, because the result carries the solve's factor nowhere
    else: ``RefinedParameter.stderr_uncorrected`` is ``stderr`` divided by
    ``LSQOutcome.esd_inflation``, so their ratio on any row is that factor to
    rounding.  ``Statistics.esd_inflation`` is not it: it is measured again on
    the result's own compile, and differs by up to 4 % (WP-2002, B4).
    ``None`` where no row carries both esds, as on a fit with no covariance.
    """
    for row in result.parameters:
        if row.stderr is not None and row.stderr_uncorrected:
            return row.stderr / row.stderr_uncorrected
    return None


def _effective_count(result) -> float:
    """N/f², the observation count a ΔBIC against ``result`` charges.

    N is the fitted channel count and f is :func:`_solve_inflation`, the
    restricted fit's factor, as :func:`rietx.report.compare_freed` takes it.
    Every trial measured against one nuclear reference therefore charges one
    count, so their ΔBICs rank on one scale (issue #270; WP-2002, B12).
    """
    from ..optimize.statistics import effective_sample_size

    return effective_sample_size(int(result.statistics.n_points),
                                 _solve_inflation(result))


def _within_k_offset_margin(satellite_score: dict, reference_k, candidate_k,
                            margin: float = SOLVE_K_OFFSET_MARGIN_DEG) -> bool:
    """Whether ``candidate_k`` is close enough to ``reference_k`` on the
    satellite step alone to be worth its own full trial refinement.

    Both keys index ``satellite_score`` (a ``k -> SatelliteCandidate`` map,
    e.g. ``solve_magnetic``'s own, built only on the "satellite ranking"
    route).  ``False`` whenever either k was not scored at all — a route with
    no satellite scoring (a given ``k=``, or the k = 0 forbidden-lattice-point
    signature) never has a second k to compare against in the first place.
    """
    ref, cand = satellite_score.get(reference_k), satellite_score.get(candidate_k)
    if ref is None or cand is None:
        return False
    if ref.worst_offset_deg is None or cand.worst_offset_deg is None:
        return False
    return (cand.matched == ref.matched
            and abs(cand.worst_offset_deg - ref.worst_offset_deg) <= margin)


def _eligible_trials(trials) -> list["MagneticTrial"]:
    """Every trial ``_rank`` would let compete for the win: refined to a
    converged fit, a supported moment, ΔBIC > 0.

    The one definition of "eligible" in this module — :func:`_rank`,
    :func:`_best_eligible_delta_bic` and :attr:`MagneticSolution.margin` all
    call this rather than repeating the filter, because the
    three had drifted apart once already (issue #390): a caller
    reading ``trials[1]`` as "the runner-up" without checking eligibility can
    land on a *disqualified* trial whose raw ΔBIC is not penalised by
    whatever excluded it and can exceed the true winner's — see
    :attr:`MagneticSolution.margin`'s docstring for the measured case.
    """
    return [t for t in trials if t.status == "refined" and _converged(t)
           and t.supported and t.delta_bic is not None and t.delta_bic > 0.0]


def _converged(trial) -> bool:
    """Whether a refined trial's fit, and the nuclear reference its ΔBIC is
    measured against, reached a minimum (``fit_status``, ``reference_status``)."""
    return trial.stopped_short is None


def _budget_rivals(trials, floor: float) -> list["MagneticTrial"]:
    """Trials kept out of the ranking only by a budget stop, whose ΔBIC would
    have put them above ``floor`` — the ones a converged fit could have made
    the winner or a tie, so the ranking must not be read without them."""
    return [t for t in trials if t.status == "refined" and not _converged(t)
            and t.supported and t.delta_bic is not None
            and t.delta_bic > max(floor, 0.0)]


def _best_eligible_delta_bic(trials) -> float | None:
    """The best ΔBIC among one k's eligible trials, or ``None``.

    "Eligible" matches :func:`_rank` exactly (refined and converged, a
    supported moment, ΔBIC > 0) so a k with no eligible class here is exactly a k ``_rank``
    itself would report as having no winner.
    """
    eligible = [t.delta_bic for t in _eligible_trials(trials)]
    return max(eligible) if eligible else None


def _score_k_trials(k_runs: list[tuple[tuple, list["MagneticTrial"]]],
                    satellite_score: dict, k_tie_width: float, phase_name: str):
    """Rank the k's the walk actually refined against each other (by their
    own best eligible ΔBIC — see :func:`_best_eligible_delta_bic`), and build
    the reporting ``k_trials`` adds: the winning ``(kk, trials)`` pair to carry into
    :func:`_rank`, one :class:`KTrialSummary` per k tried, any
    ``K_VECTOR_UNSEPARATED`` diagnostic, and the caveat sentence(s) saying
    which k won and by how much (or that only one reached an eligible class).

    A k with no eligible class sorts last, never first — the winner is always
    a k that produced *something*, when any did — and among such k's the one
    with more *refined* classes comes first, so a k whose every class refused
    never speaks for a k that was fitted.  Only then does the first walked win
    (Python's sort is stable, and ``k_runs`` is in walk order).
    """
    scored = [(k_i, trials_i, _best_eligible_delta_bic(trials_i))
              for k_i, trials_i in k_runs]
    # a k that refined something outranks one whose every class refused, even
    # when neither reached an eligible class: its verdict is about the data,
    # the other's about what could be modelled
    scored.sort(key=lambda row: (
        row[2] if row[2] is not None else -math.inf,
        sum(1 for t in row[1] if t.status == "refined")), reverse=True)
    kk, trials, _ = scored[0]

    def _label(k_i) -> str:
        return "(" + ", ".join(str(c) for c in k_i) + ")"

    k_trial_rows = tuple(
        KTrialSummary(
            k=tuple(str(c) for c in k_i),
            matched=(satellite_score[k_i].matched
                    if k_i in satellite_score else None),
            worst_offset_deg=(satellite_score[k_i].worst_offset_deg
                              if k_i in satellite_score else None),
            best_delta_bic=score,
            n_refined=sum(1 for t in trials_i if t.status == "refined"))
        for k_i, trials_i, score in scored)

    diagnostics: list[Diagnostic] = []
    caveats: list[str] = []
    if len(scored) > 1:
        top, runner = scored[0], scored[1]
        if top[2] is not None:
            if runner[2] is not None:
                gap = top[2] - runner[2]
                caveats.append(
                    f"k = {_label(top[0])} won over k = {_label(runner[0])} by "
                    f"{gap:.1f} BIC ({top[2]:.1f} against {runner[2]:.1f})")
                if gap <= k_tie_width:
                    diagnostics.append(Diagnostic(
                        level="info", code="K_VECTOR_UNSEPARATED",
                        message=(
                            f"k = {_label(top[0])} (ΔBIC {top[2]:.1f}) and "
                            f"k = {_label(runner[0])} (ΔBIC {runner[2]:.1f}) "
                            f"are within {k_tie_width:.1f} BIC of each other, "
                            "and the satellite step could not separate them "
                            "either."),
                        where=[f"phases.{phase_name}"], value=gap))
            else:
                caveats.append(
                    f"k = {_label(top[0])} was the only one of {len(scored)} "
                    f"tried k's to reach an eligible class "
                    f"(ΔBIC {top[2]:.1f})")
    return kk, trials, k_trial_rows, tuple(diagnostics), tuple(caveats)


def _n_k_tried(k_runs) -> int:
    """How many of the k's walked so far were actually *tried*: a k whose
    every class refused ran no fit and uses up no ``k_trials`` slot."""
    return sum(1 for _k, ts in k_runs
               if any(t.status == "refined" for t in ts))


def _reported_reference(reference_of, references, kk, ordered, tied=()):
    """The nuclear reference the reported ``nuclear_*`` numbers come from.

    The one the **leading trial** was measured against: ``kk`` is the winning
    k and ``ordered[0]`` the winner.  On a ΔBIC tie the tied classes lead the
    list fewest moment parameters first (WP-2002, 2026-10-20), so the lead is
    the tied class with the highest ΔBIC, the one ``ordered[0]`` was before
    that order.  Taking the first child cell's reference that was built instead
    reports the losing k's numbers whenever two k's have different child cells
    and the second wins.  Falls back to any reference built at ``kk``, then to
    any at all, and is ``None`` only when none was.
    """
    lead = ordered[0] if ordered else None
    if len(tied) > 1:
        lead = max((t for t in ordered if t.class_index in tied
                    and t.delta_bic is not None),
                   key=lambda t: t.delta_bic, default=lead)
    reference = (reference_of.get((kk, lead.class_index))
                 if lead is not None else None)
    if reference is None:
        reference = next((v for (k_i, _i), v in reference_of.items()
                          if k_i == kk), None)
    if reference is None:
        reference = next(iter(references.values()), None)
    return reference


def _rank(trials: list[MagneticTrial], tie_width: float):
    """ΔBIC, and abstain on a tie, the tie listed fewest parameters first.

    Nothing breaks a ΔBIC tie (WP-2002).  The magnetic-only R is reported in
    an abstention's reason and decides nothing: the 2 % R gap that once broke
    a tie was chosen, never measured (B12).  Nor does the moment-parameter
    count, which the ΔBIC already charges at ln N_eff a parameter; it orders
    the tied classes, the order of the highest-symmetry convention, and the
    reason names it (ruled 2026-10-20).  Returns ``(ordered trials, tied class indices, verdict, reason)``.  Every
    trial is in the returned order, refusals and unsupported models included,
    because a ranked list is published whole; only the *eligible* ones — a
    refined fit that converged, a supported moment and evidence in favour of
    the fuller model — can win or tie.  A trial kept out only by a budget stop
    (:func:`_budget_rivals`) whose ΔBIC would have reached the winner's tie
    width, or would have been the only eligible one, makes the answer an
    abstention: the budget, not the data, would otherwise have decided.
    """
    def parsimony(t: MagneticTrial) -> int:
        """The count parsimony is about: free moment DOFs of the whole model.

        **Not** ``free_amplitudes``, which is the *representative site's*
        family size.  On a parent with several magnetic sites the two differ —
        Ba₆Co₆'s classes each show one amplitude per site and three sites — and
        ranking by the per-site number would compare models by a quantity that
        is not the number of parameters either of them spends.
        """
        return (t.n_moment_parameters if t.status == "refined"
                else t.free_amplitudes)

    def key(t: MagneticTrial):
        return (-(t.delta_bic if t.delta_bic is not None else -math.inf),
                parsimony(t), t.bns_number)

    eligible = _eligible_trials(trials)
    chosen = {id(t) for t in eligible}
    rest = [t for t in trials if id(t) not in chosen]
    eligible.sort(key=key)
    rest.sort(key=lambda t: (t.status != "refined",
                             -(t.delta_bic if t.delta_bic is not None
                               else -math.inf)))
    ordered = eligible + rest
    rivals = _budget_rivals(
        trials, eligible[0].delta_bic - tie_width if eligible else 0.0)
    if rivals:
        names = ", ".join(f"class {t.class_index} ({t.label}, ΔBIC "
                          f"{t.delta_bic:.1f}, {t.stopped_short})"
                          for t in rivals)
        return (tuple(ordered), (), "abstained",
                f"{len(rivals)} trial fit(s) stopped short of a minimum after "
                f"{SOLVE_MAX_CONTINUATIONS} continuations of the iteration "
                f"budget and would have "
                f"{'tied or beaten the leader' if eligible else 'been eligible'}"
                f": {names}. Their ΔBIC is where the solver stopped, not a "
                f"measurement, so the ranking is not stated; raise the stages' "
                f"max_iter (plan=) and solve again")
    if not eligible:
        # Three different states reach "no winner", and saying the wrong one is
        # a diagnostic that is true of an intermediate state and false of the
        # reported one.  A refused candidate never had a modulus to test, so
        # "its moment did not survive the null test" would be a claim about a
        # fit that never ran.
        refined = [t for t in trials if t.status == "refined"]
        if trials and not refined:
            reasons = sorted({(t.refusal or "").split(":", 1)[-1].strip()[:160]
                              for t in trials})
            plural = "class" if len(trials) == 1 else "classes"
            return (tuple(ordered), (), "abstained",
                    f"none of the {len(trials)} candidate {plural} could be "
                    f"stated as a refinable model, so nothing was tested "
                    f"against the data — this is not a result about the "
                    f"specimen: {'; '.join(reasons)}")
        short = [t for t in refined if not _converged(t)]
        # said in the sentence, not only in the caveats: a verdict read off a
        # fit that stopped short is a statement about where the solver
        # stopped (the diagnostic-tense rule)
        stopped = ("" if not short else
                   f" ({len(short)} of the {len(refined)} stopped short of a "
                   f"minimum on the iteration budget, so for "
                   f"{'it' if len(short) == 1 else 'them'} this is where the "
                   f"solver stopped: "
                   + ", ".join(f"class {t.class_index}" for t in short) + ")")
        if refined and not any(t.supported for t in refined):
            return (tuple(ordered), (), "nothing to solve",
                    f"{len(refined)} candidate(s) refined and not one came "
                    f"back with a supported moment — every modulus (and "
                    f"every degenerate pair's quadrature sum) is at its "
                    f"floor or below MOMENT_SUPPORT_SIGMA of its own esd, "
                    f"which is what an unmagnetised pattern looks like under a "
                    f"magnetic model{stopped}")
        n_supported = sum(1 for t in refined if t.supported)
        return (tuple(ordered), (), "nothing to solve",
                f"{n_supported} of {len(refined)} refined candidate(s) came back "
                f"with a supported moment but none improved on the nuclear "
                f"model (every ΔBIC ≤ 0), so "
                f"the moment is buying no agreement and there is nothing here "
                f"a magnetic model explains{stopped}")
    best = eligible[0]
    tie = [t for t in eligible if best.delta_bic - t.delta_bic <= tie_width]
    if len(tie) == 1:
        return (tuple(ordered), (best.class_index,), "solved",
                f"class {best.class_index} ({best.label}) leads on ΔBIC by "
                f"{best.delta_bic - eligible[1].delta_bic:.1f} "
                f"({best.delta_bic:.1f} against {eligible[1].delta_bic:.1f}), "
                f"more than the tie width of {tie_width:.1f}"
                if len(eligible) > 1 else
                f"class {best.class_index} ({best.label}) is the only class "
                f"with a supported moment and evidence in its favour "
                f"(ΔBIC {best.delta_bic:.1f})")
    spread = best.delta_bic - tie[-1].delta_bic
    # the convention's order, fewest moment parameters first, ΔBIC after
    tie = sorted(tie, key=lambda t: (parsimony(t), -t.delta_bic, t.bns_number))
    in_tie = {id(t) for t in tie}
    ordered = tie + [t for t in ordered if id(t) not in in_tie]

    def r_mag(t: MagneticTrial) -> str:
        return "-" if t.r_magnetic is None else f"{t.r_magnetic:.3f}"

    names = ", ".join(f"class {t.class_index} ({t.label}, ΔBIC "
                      f"{t.delta_bic:.1f}, {parsimony(t)} moment parameter(s), "
                      f"R_mag {r_mag(t)})" for t in tie)
    return (tuple(ordered), tuple(t.class_index for t in tie), "abstained",
            f"{len(tie)} classes are tied: {names}. Their ΔBIC spread of "
            f"{spread:.1f} is inside the tie width of {tie_width:.1f}, and the "
            f"ΔBIC already charges each moment parameter, so neither the count "
            f"nor R_mag ranks them. This powder pattern does not choose between "
            f"them; a pattern to a smaller d, a single crystal, or a temperature "
            f"series (WP-1329) would. They are listed fewest moment parameters "
            f"first, the order of the convention that reports the highest "
            f"symmetry the data allow")


# ---------------------------------------------------------------------------
# the call
# ---------------------------------------------------------------------------
def solve_magnetic(refinement, data, *, phase: int = 0,
                   sites: Sequence[str] | None = None,
                   species: Sequence[str] | None = None,
                   ion: str | dict[str, str] | None = None,
                   g: float | dict[str, float] | None = None,
                   k=None, top_k: int = SOLVE_TOP_K,
                   d_min: float = SOLVE_D_MIN,
                   magnitude: float = SOLVE_SEED_MU_B,
                   plan: RefinementPlan | None = None,
                   nuclear_group: str = "parent",
                   generator=None,
                   tie_width: float = SOLVE_TIE_DELTA_BIC,
                   k_trials: int = SOLVE_K_TRIALS,
                   k_tie_width: float = SOLVE_K_TIE_DELTA_BIC,
                   cif_dir=None,
                   tie_to_parent: bool = False) -> MagneticSolution:
    """Determine a magnetic structure from a converged nuclear fit, or abstain.

    ``refinement`` is a :class:`rietx.Refinement` that has **already fitted**
    ``data`` with a nuclear model; its fitted structure and instrument are the
    starting point, so the nuclear reference below starts converged rather than
    being re-derived.

    ``sites`` (labels) or ``species`` name the sites that carry a moment; with
    neither, every site whose species is a magnetic form-factor key is taken.
    ``ion`` is that key — ``"Mn3+"``, or a mapping from label or species to one
    — and is **not** ``Atom.species``.  Where a site's ion is not stated by the
    caller here, the same fallback :func:`~rietx.crystallography.cif.
    structure_from_cif` applies at read is applied to the candidate builder
    too (WP-1327): a bare element with no neutral-atom ``<j0>``
    resolves through :func:`~.crystallography.magnetic.form_factor.
    resolve_assumed_ion` to its majority magnetic oxidation state, reported as
    ``MAGNETIC_ION_ASSUMED`` on :attr:`MagneticSolution.diagnostics`.

    ``g`` is the Landé factor that ion needs — one float for every magnetic
    site, or a mapping from label or species to one, mirroring ``ion``.
    ``None`` (the default) is the spin-only 2 for a 3d/4d ion and is
    **refused** for a 4f/5f one (:func:`~.crystallography.magnetic.
    form_factor.needs_explicit_g`) *unless* that ion was itself not stated by
    the caller (came from the table directly, or from the
    ``resolve_assumed_ion`` fallback above) — there its free-ion Hund's-rule
    g_J (:func:`~.crystallography.magnetic.form_factor.assumed_lande_g`) is
    used instead of leaving every 4f/5f candidate to abstain with no route
    around it, reported as ``LANDE_G_ASSUMED``.  A caller-stated ``ion`` or
    ``g`` always wins over both defaults (issue #257 A5's rule, carried over
    from the CIF reader), and neither default ever changes a non-4f/5f site's
    behaviour.

    ``k`` skips the propagation-vector step and states the vector: useful when
    a k is known from a single crystal.  Otherwise the arm decides, and the
    result records which of its three routes it took.

    ``plan`` overrides :data:`SOLVE_STAGE_PATHS` for both the trials and the
    nuclear reference; pass one whose stages differ only by the moment paths,
    or ΔBIC stops meaning what it says.  Without one, the trials and the
    reference run no closing stage, and the winner then runs one
    (:func:`_close`), so its moments and their esds are measured on peaks with
    their tails; a caller's plan keeps its own ``closing_window_tol`` for every
    fit, the winner's included.

    ``tie_to_parent=True`` (default ``False``, which is the behaviour above
    unchanged) takes a k ≠ 0 trial's nuclear freedom from the parent: the child
    cell is held at the parent-derived cell (``phases.*.cell.*`` leaves every
    stage) and the child Biso of one parent atom are tied to one another
    (``SupercellStatement.site_map``), for the trial **and** for the nuclear
    reference it is scored against, so ΔBIC still compares models that free the
    same set.  A k = 0 trial is not touched.  Reported as
    ``SOLVE_B_TIED_PER_PARENT_SITE`` (info) on the solution.  Proposed in #724.

    ``cif_dir`` writes one magCIF per refined class (:meth:`
    MagneticSolution.write_magcifs`).  Nothing is written without it.

    ``k_trials`` is how many of the ranked candidate k's get their own
    full trial refinement rather than being carried only as a fallback for
    when an earlier k's classes all refuse — see :data:`SOLVE_K_TRIALS` and
    :data:`SOLVE_K_OFFSET_MARGIN_DEG`.  ``k_tie_width`` is the ΔBIC gap below
    which the top two such k's are reported as not separated by intensity
    either (``K_VECTOR_UNSEPARATED``, in :attr:`MagneticSolution.diagnostics`)
    — see :data:`SOLVE_K_TIE_DELTA_BIC`.  Every k actually tried is reported
    in :attr:`MagneticSolution.k_trials`, whether it won or not.

    Refuses by name on a non-neutron histogram.  Everything else — no
    unexplained intensity, no candidate k, a tie at the top — is *reported*,
    which is the 1043/1301 rule this workflow inherits: a determination stage
    returns a ranked list with a stated criterion and an abstention reason,
    never a confident wrong singleton.
    """
    from ..crystallography.satellites import zone_boundary_candidates
    from ..params.vector import ParameterTable
    from ..report.layer2 import delta_bic
    from ..schemas.pattern import require_two_theta

    require_two_theta(data, "solve_magnetic()")

    if refinement.result_ is None or refinement._model is None:
        raise RuntimeError(
            "solve_magnetic(): call fit() on the nuclear model first — the "
            "workflow starts from a converged nuclear refinement and reads its "
            "unexplained intensity")
    structure = refinement.fitted_structure
    instrument = refinement.fitted_instrument
    parent = structure.phases[phase]
    _refuse_non_neutron(instrument, parent.name)
    # An unnamed (bracketed-label) parent used to be refused here
    # by name, on the grounds that
    # the small representations of a k-vector come from tables keyed on the
    # space-group *number* and an operator list in a non-standard cell has
    # none to key on.  That reasoning does not hold for this engine: M-6
    # (WP-1418) builds every small irrep from the little group's
    # own operators, projectively, with no tabulated-number lookup anywhere
    # in ``crystallography.representation.irreps``/``crystallography.magnetic.isotropy`` — measured by
    # inspection (grep) and by the tests below, not merely asserted.  What is
    # actually needed is an object exposing the group's operations, which
    # ``resolve_group`` already builds for exactly this case (the same
    # ``OperatorGroup`` :attr:`Phase.symmetry_operations` uses everywhere
    # else a phase's own group is asked for), so the parent's group is
    # resolved once here and threaded into the candidate enumeration and the
    # k != 0 supercell statement below, instead of refusing before either is
    # tried.
    parent_group = resolve_group(parent.space_group, parent.symmetry_operations)
    if parent.magnetic_symmetry is not None:
        raise ValueError(
            f"solve_magnetic(): phase {parent.name!r} already declares a "
            f"magnetic space group. This workflow determines one; pass the "
            f"nuclear phase, or refine the stated model directly.")
    if parent.propagation_vector is not None:
        raise ValueError(
            f"solve_magnetic(): phase {parent.name!r} declares a propagation "
            f"vector {parent.propagation_vector!r}. That is WP-1326's "
            f"hypothesis tool — satellites, no moments — and a moment model "
            f"cannot sit beside it. Drop it and pass k= instead, which states "
            f"the same k for this workflow to build a supercell from.")
    caveats: list[str] = []
    magnetic, g_map, ion_assumed, g_assumed = _magnetic_sites(
        parent, sites, species, ion, g)
    for _j, label, key in magnetic:
        if key == parent.atoms[_j].species and key.isalpha():
            caveats.append(
                f"{label}: the neutral-atom form factor {key!r} was used "
                f"because no oxidation state was named; pass "
                f"ion={{{label!r}: 'X3+'}} if the ion's own coefficients matter")
    ion_g_diagnostics: list[Diagnostic] = []
    for _j, label, _key in magnetic:
        if label in ion_assumed:
            assumed_ion, reason = ion_assumed[label]
            ion_g_diagnostics.append(Diagnostic(
                level="info", code="MAGNETIC_ION_ASSUMED",
                where=[f"phases.{phase}.atoms.{_j}.moment.ion"],
                message=(f"solve_magnetic(): site {label!r} states no "
                         f"oxidation state and this table has no "
                         f"neutral-atom ⟨j0⟩ for it. Its form factor "
                         f"defaulted to {assumed_ion!r} ({reason})."),
                suggestion=(f"Pass ion={{{label!r}: '<ion>'}} to "
                            f"solve_magnetic() to state the ion.")))
        if label in g_assumed:
            g_value = g_assumed[label]
            ion_g_diagnostics.append(Diagnostic(
                level="info", code="LANDE_G_ASSUMED",
                where=[f"phases.{phase}.atoms.{_j}.moment.g"],
                value=g_value,
                message=(f"solve_magnetic(): site {label!r} states no Landé "
                         f"g and its ion was not stated by the caller. Its "
                         f"free-ion Hund's-rule g_J = {g_value:g} was used."),
                suggestion=(f"Pass g={{{label!r}: {g_value:g}}} to "
                            f"solve_magnetic() to state g.")))

    if refinement.result_.status != "converged":
        caveats.append(
            f"the nuclear refinement this determination starts from stopped at "
            f"{refinement.result_.status!r}, not 'converged'. Every ΔBIC below "
            f"is measured against it, so a nuclear model still moving makes the "
            f"whole ranking provisional: converge it first")

    # --- the magnetic-only region, defined on the nuclear fit ---------------
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    mask = magnetic_channels(refinement._model, values, refinement.result_)
    # every trial and every reference is fitted over exactly these channels —
    # the ones the mask was taken on and the ones ΔBIC's N counts
    axis = refinement.result_.two_theta
    limits = (float(min(axis)), float(max(axis)))

    # --- the k step ---------------------------------------------------------
    evidence = None
    if k is None:
        # WP-1326's own arm, called directly rather than through a whole
        # ``FitReport``: the workflow needs this one section, the generator is
        # a *parameter* of it (issue #257 A1) and ``build_report`` does not
        # take one.
        if refinement.result_.two_theta is not None:
            from ..report import _resid_norm
            from ..report.layer0 import residual_peak_indices
            from ..report.satellites import analyse_satellites

            tt = np.asarray(refinement.result_.two_theta, dtype=np.float64)
            ticks = np.asarray([t for positions in
                                refinement.result_.ticks.values()
                                for t in positions], dtype=np.float64)
            resid = _resid_norm(refinement.result_)
            peak_idx = residual_peak_indices(resid, min_peak_sigma=5.0)
            evidence = analyse_satellites(
                refinement._model, values,
                residual_two_theta=tt[peak_idx],
                ticks=ticks, structure=structure,
                generator=generator or zone_boundary_candidates,
                residual_height_over_sigma=resid[peak_idx],
            )[phase]
        ks, route, reason = _k_from_the_report(evidence, top_k)
    else:
        ks = [tuple(Fraction(str(v)) for v in k)]
        route = "given by the caller"
        reason = f"k = {tuple(str(v) for v in ks[0])} was stated, not determined"
    k_candidates = tuple(
        (c.vector, int(c.matched), int(c.n_satellites))
        for c in (evidence.candidates[:top_k] if evidence is not None else ()))
    counts = (int(evidence.n_residual_peaks) if evidence else 0,
              int(evidence.excess_on_nuclear_lines) if evidence else 0,
              int(evidence.excess_on_absent_lattice_lines) if evidence else 0,
              int(evidence.n_unexplained) if evidence else 0)
    # The satellite step's own (matched, worst_offset_deg) for each ranked
    # k, keyed by the same Fraction tuple ``ks`` uses — ``None`` for a route
    # with no such scoring (a given k=, or the forbidden-lattice-point k = 0
    # signature), where k_trials beyond the first is therefore never reached
    # (there is only ever one k on those routes).
    satellite_score = {
        tuple(Fraction(v) for v in c.k): c
        for c in (evidence.candidates if evidence is not None else ())
        if c.matched > 0
    } if route == "satellite ranking" else {}

    def _empty(verdict: str, why: str) -> MagneticSolution:
        return MagneticSolution(
            verdict=verdict, reason=why, criterion=_CRITERION,
            phase=parent.name, space_group=parent.space_group, k=None,
            k_route=route, k_reason=reason, k_candidates=k_candidates,
            sites=tuple(label for _j, label, _i in magnetic),
            n_residual_peaks=counts[0], n_on_nuclear_lines=counts[1],
            n_on_forbidden_lattice_points=counts[2], n_unexplained=counts[3],
            trials=(), tied=(), tie_width=tie_width, d_min=d_min,
            nuclear_rwp=float(refinement.result_.statistics.rwp),
            nuclear_gof=float(refinement.result_.statistics.gof),
            nuclear_r_magnetic=r_magnetic(refinement.result_, mask),
            n_magnetic_channels=int(mask.sum()),
            caveats=tuple(caveats), diagnostics=tuple(ion_g_diagnostics),
            _instrument=instrument)

    if not ks:
        return _empty("nothing to solve" if route == "nothing to solve"
                      else "abstained", reason)
    skipped: list[str] = []

    # --- the candidates, per site, merged into classes -----------------------
    # the trials the package fits and ranks by ΔBIC pay for no closing stage
    # when it chose the plan, and the winner then runs one (_close); a
    # caller's plan keeps its own (WP-2002)
    package_plan = plan is None
    plan = plan or RefinementPlan(stages=[
        Stage(name, list(paths))
        for name, paths in zip(SOLVE_STAGE_NAMES, SOLVE_STAGE_PATHS, strict=True)],
        closing_window_tol=None)
    # A stage that differed from its predecessor only by moment paths repeats
    # it here, and is dropped: the default's moduli and moment stages would
    # otherwise refit the reference twice under one free set, and move it.
    nuclear_stages: list[Stage] = []
    for stage in plan.stages:
        turn_on = [p for p in stage.turn_on if _MOMENT_GLOB not in p]
        if nuclear_stages and turn_on == nuclear_stages[-1].turn_on:
            continue
        nuclear_stages.append(Stage(stage.name, turn_on))
    # the trials' absent-phase hold and correlation guard, so the reference a
    # ΔBIC compares them with is fitted under the same rule (WP-2002, B1)
    nuclear_plan = RefinementPlan(stages=nuclear_stages,
                                  phase_support_sigma=plan.phase_support_sigma,
                                  correlation_guard=plan.correlation_guard,
                                  closing_window_tol=plan.closing_window_tol)

    def enumerate_for(k_try):
        """Candidate classes for one k, or a sentence saying why there are none."""
        sets = []
        for j, label, _ion in magnetic:
            atom = parent.atoms[j]
            try:
                cs = _isotropy.candidates(
                    parent_group,
                    (atom.x.value, atom.y.value, atom.z.value), k_try)
            except ValueError as exc:
                return None, (f"the candidate enumeration refuses it at site "
                              f"{label}: {exc}")
            # candidates() flags a failing family rather than raising on
            # it, so a caller ranking models filters to the verified view —
            # unchanged behaviour on every site where nothing failed.
            sets.append((label, analyse(cs.verified_only(), d_min=d_min)))
        merged = _merge_classes(sets)
        if not merged:
            return None, ("no order-parameter direction at it puts a moment on "
                          "any named site")
        return (sets, merged), None

    # **The ranked list is walked, not just its head.**  WP-1326 publishes a
    # ranked candidate set and the top row is a hypothesis, not an answer; a k
    # whose classes cannot be *stated* as refinable models has not been tested
    # against the data, so stopping there would report "no answer" when the
    # next hypothesis in the caller's own top_k was never tried.  The first k
    # that yields something testable is used, and every k passed over is named
    # with the reason it was.
    enumerated = []
    for k_try in ks:
        built, why_not = enumerate_for(k_try)
        spelled = "(" + ", ".join(str(c) for c in k_try) + ")"
        if built is None:
            skipped.append(f"k = {spelled}: {why_not}")
            continue
        enumerated.append((k_try, *built))
    if not enumerated:
        return _empty("abstained",
                      "no candidate propagation vector yielded a magnetic model "
                      "that could be enumerated: " + "; ".join(skipped))

    # --- the nuclear reference, one per child cell --------------------------
    references: dict[tuple, tuple] = {}
    #: the MOMENT_PAIR_DEGENERATE rows, across every class of every k tried
    #: (``run_k`` extends this) — merged into the result's own diagnostics
    #: below, beside K_VECTOR_UNSEPARATED.
    pair_diagnostics: list[Diagnostic] = []
    #: the one ``SOLVE_B_TIED_PER_PARENT_SITE`` row, once a trial has been tied
    tied_note: list[Diagnostic] = []

    #: (k, class index) → the reference tuple that class's ΔBIC was measured
    #: against, so the reported nuclear numbers are the winner's, not whichever
    #: child cell happened to be built first
    reference_of: dict[tuple, tuple] = {}

    def reference_for(child_structure, extra_ties=()) -> tuple:
        child = child_structure.phases[0]
        key = (child.space_group, tuple(round(v, 9)
                                        for v in child.cell.lengths_angles()),
               len(child.atoms), tuple(extra_ties))
        if key not in references:
            bare = Structure(phases=[child.model_copy(update={
                "atoms": [a.model_copy(update={"moment": None})
                          for a in child.atoms],
                "magnetic_symmetry": None})])
            _r, res = _fit(bare, instrument, data,
                           _without_cell(nuclear_plan) if extra_ties
                           else nuclear_plan,
                           list(extra_ties) or None, limits=limits,
                           hold=_CELL_HOLD if extra_ties else ())
            if res.status != "converged":
                caveats.append(
                    f"the nuclear reference of a {len(child.atoms)}-atom "
                    f"{child.space_group} cell stopped at {res.status!r} after "
                    f"{SOLVE_MAX_CONTINUATIONS} continuations of its iteration "
                    f"budget; every trial measured against it is listed and "
                    f"not ranked")
            references[key] = (_chi2_absolute(res.statistics),
                               int(res.statistics.n_free_parameters),
                               float(res.statistics.rwp),
                               float(res.statistics.gof),
                               r_magnetic(res, mask),
                               res.status,
                               _effective_count(res),
                               int(res.statistics.n_points))
        return references[key]

    def run_k(kk, sets, classes):
        """Every class of one k, refined.  Returns the trials, in class order."""
        zero = all(c == 0 for c in kk)
        trials: list[MagneticTrial] = []
        for index, (members, representative, site_label) in enumerate(classes):
            candidate = representative
            drift = None
            extra = ()
            try:
                if zero:
                    child = _state_k0(parent, candidate, magnetic, magnitude,
                                      g_map)
                    if child is None:
                        raise ValueError(
                            f"{candidate.bns_number} forbids a moment on every "
                            f"named site: its allowed subspace there is empty")
                    child_structure = Structure(phases=[child])
                else:
                    statement, used = _supercell(
                        parent, candidate,
                        species=[parent.atoms[j].label for j, _l, _i in magnetic],
                        ions={parent.atoms[j].label: key
                              for j, _l, key in magnetic},
                        g={parent.atoms[j].label: g_map.get(label)
                           for j, label, _i in magnetic},
                        magnitude=magnitude, nuclear_group=nuclear_group)
                    if used != nuclear_group:
                        caveats.append(
                            f"class {index}: the parent's own group is not a group "
                            f"of the magnetic cell (k lowers the crystal class), so "
                            f"the child phase is stated under the magnetic group's "
                            f"nuclear part instead — nuclear_group={used!r}. Its "
                            f"asymmetric unit is larger than the parent's and its "
                            f"coordinates are correspondingly less constrained; "
                            f"they are held here, as they must be")
                    child_structure = Structure(phases=[statement.phase])
                    if tie_to_parent:
                        extra = _parent_site_ties(statement)
                        if not tied_note:
                            tied_note.append(Diagnostic(
                                level="info", code="SOLVE_B_TIED_PER_PARENT_SITE",
                                message=(
                                    "tie_to_parent: a k != 0 trial holds the "
                                    "child cell at the parent-derived cell and "
                                    "ties the child Biso of one parent atom to "
                                    "one another, in the trial and in its "
                                    "nuclear reference. Coordinates stay held "
                                    "as before.")))
                trial_plan = _without_cell(plan) if extra else plan
                reference_of[(kk, index)] = reference_for(child_structure, extra)
                chi2_ref, p_ref = reference_of[(kk, index)][:2]
                owners = [label for _j, label, _i in magnetic
                          if any(a.moment is not None
                                 and _moment_owner(a.label, [label]) == label
                                 for a in child_structure.phases[0].atoms)]
                (start, ref, result), n_starts, n_minima = _best_start(
                    _starts(child_structure, instrument, data, trial_plan, zero,
                            owners, limits, extra))
                moments, n_moment, pair_diag = _moment_rows(
                    ref, result, ref.fitted_structure)
                pair_diagnostics.extend(
                    _named_for_class(pair_diag, index, kk))
                dead = _dead_globs(trial_plan, result)
                if dead:
                    caveats.append(
                        f"class {index}: the stage free list names "
                        f"{', '.join(dead)}, which freed no parameter of this "
                        f"model — a Stage entry that matches nothing is accepted "
                        f"silently, so the model that was ranked is not the one "
                        f"the plan describes")
                if n_minima > 1:
                    caveats.append(
                        f"class {index}: {n_starts} starts found {n_minima} "
                        f"distinct minima of the moment stage (best from "
                        f"{start!r}); this candidate's moment problem is "
                        f"multimodal and a single seed would have reported a "
                        f"different answer")
                if not zero:
                    drift = anti_translation_residual(
                        ref.fitted_structure.phases[0])
            except Exception as exc:      # noqa: BLE001 - reported, never swallowed
                trials.append(MagneticTrial(
                    class_index=index, representative=candidate.label,
                    members=tuple(members), site=site_label,
                    irrep=candidate.irrep_label,
                    direction=candidate.direction.label,
                    bns_number=candidate.bns_number,
                    uni_number=(candidate.identification.uni_number
                                if candidate.identification else None),
                    msg_type=candidate.msg_type,
                    free_amplitudes=candidate.free_amplitudes,
                    determinable_amplitudes=None,
                    status="refused", refusal=f"{type(exc).__name__}: {exc}"))
                continue
            n_free = int(result.statistics.n_free_parameters)
            if n_free - p_ref != n_moment:
                caveats.append(
                    f"class {index}: the trial freed {n_free - p_ref} parameters "
                    f"more than its nuclear reference but only {n_moment} of them "
                    f"are moment DOFs, so ΔBIC's n_added is the moment count and "
                    f"the rest are unaccounted; the cell constraints of the two "
                    f"models differ")
            trials.append(MagneticTrial(
                class_index=index, representative=candidate.label,
                members=tuple(members), site=site_label,
                irrep=candidate.irrep_label, direction=candidate.direction.label,
                bns_number=candidate.bns_number,
                uni_number=(candidate.identification.uni_number
                            if candidate.identification else None),
                msg_type=candidate.msg_type,
                free_amplitudes=candidate.free_amplitudes,
                determinable_amplitudes=_determinable(sets, site_label, candidate),
                status="refined",
                rwp=float(result.statistics.rwp),
                gof=float(result.statistics.gof),
                delta_bic=delta_bic(chi2_ref, _chi2_absolute(result.statistics),
                                    int(result.statistics.n_points), n_moment,
                                    n_effective=reference_of[(kk, index)][6]),
                r_magnetic=r_magnetic(result, mask),
                n_moment_parameters=n_moment, n_free_parameters=n_free,
                moments=moments,
                held=tuple(result.stages[-1].held) if result.stages else (),
                anti_translation_drift=drift,
                n_starts=n_starts, n_minima=n_minima, start=start,
                fit_status=result.status,
                reference_status=reference_of[(kk, index)][5],
                _structure=ref.fitted_structure, _result=result,
                _refinement=ref, _plan=trial_plan))
            if result.status != "converged":
                caveats.append(
                    f"class {index}: the trial fit stopped at "
                    f"{result.status!r} after {SOLVE_MAX_CONTINUATIONS} "
                    f"continuations of its iteration budget, so its ΔBIC "
                    f"({trials[-1].delta_bic:.1f}) measures where the solver "
                    f"stopped rather than a minimum; it is listed and not "
                    f"ranked")
            if reference_of[(kk, index)][5] != "converged":
                caveats.append(
                    f"class {index}: its nuclear reference stopped at "
                    f"{reference_of[(kk, index)][5]!r}, so its ΔBIC "
                    f"({trials[-1].delta_bic:.1f}) is inflated by the "
                    f"reference's own distance from a minimum; it is listed "
                    f"and not ranked")

        return trials

    # **The ranked list is walked, not just its head.**  WP-1326 publishes a
    # ranked candidate set and its top row is a hypothesis, not an answer.  A k
    # whose classes cannot be *stated* as refinable models has not been tested
    # against the data at all, so stopping there would report "no answer" where
    # the next hypothesis in the caller's own top_k was simply never tried —
    # measured on a face-centred parent, where k = (1/2,1/2,1/2) gives a child
    # cell no Hermann-Mauguin symbol reproduces and every class refuses before
    # a single fit runs.  The first k that produces a refined trial is walked
    # to on refusal exactly as before; once one has, ``k_trials`` decides
    # whether a *further* k is worth its own full refinement too — only when
    # it is within :data:`SOLVE_K_OFFSET_MARGIN_DEG` of the k already tried
    # (measured on Ba₂FeSbSe₅, PRB 103, 054115: k=(1/2,0,1/2) and k=(1/2,1/2,0) both index the
    # same 11 peaks and only the moment refinement's intensity tells them
    # apart), never merely because the caller's ``top_k`` ranked it.
    kk, sets, classes = enumerated[0]
    trials = run_k(kk, sets, classes)
    k_runs: list[tuple[tuple, list[MagneticTrial]]] = [(kk, trials)]
    for k_next, sets_next, classes_next in enumerated[1:]:
        if any(t.status == "refined" for t in trials):
            # a k whose every class refused was never *tried*, so it uses up
            # no ``k_trials`` slot
            if _n_k_tried(k_runs) >= max(1, k_trials) or not _within_k_offset_margin(
                    satellite_score, kk, k_next):
                break
        else:
            skipped.append(
                "k = (" + ", ".join(str(c) for c in kk) + "): every candidate "
                "class refused to be stated as a refinable model")
        kk, sets, classes = k_next, sets_next, classes_next
        trials = run_k(kk, sets, classes)
        k_runs.append((kk, trials))
    if skipped:
        caveats.append("candidate k passed over before this one — "
                       + "; ".join(skipped))
    if len(ks) > len(k_runs):
        caveats.append(
            f"{len(ks)} candidate k were ranked and {len(k_runs)} carried "
            f"into a trial refinement; the rest are in k_candidates and are "
            f"a hypothesis this call did not test")

    kk, trials, k_trial_rows, k_diagnostics, k_caveats = _score_k_trials(
        k_runs, satellite_score, k_tie_width, parent.name)
    caveats.extend(k_caveats)

    ordered, tied, verdict, why = _rank(trials, tie_width)

    # Issue #390's descent audit: after the winner is chosen, look one step down its
    # own group-subgroup lattice among the classes already enumerated at its
    # own k, and say plainly whether the ranking above missed a subgroup the
    # data actually prefers.
    subgroup_audit: tuple[SubgroupAudit, ...] = ()
    subgroup_note = ""
    descent_diagnostics: tuple[Diagnostic, ...] = ()
    if verdict == "solved" and ordered:
        winner_trial = ordered[0]
        winner_classes = next(
            (classes_i for k_try, _sets_i, classes_i in enumerated
             if k_try == kk), None)
        if (winner_classes is not None
                and 0 <= winner_trial.class_index < len(winner_classes)):
            winner_candidate = winner_classes[winner_trial.class_index][1]
            zero = all(c == 0 for c in kk)
            subgroup_audit, subgroup_note, descent_diagnostics = _descend(
                parent, winner_trial, winner_candidate, winner_classes,
                magnetic, g_map, plan, instrument, data, limits, tie_width,
                zero)
    if package_plan and verdict == "solved" and ordered:
        try:
            closed = _close(ordered[0], data, limits, mask)
        except Exception as exc:      # noqa: BLE001 - reported, never swallowed
            caveats.append(
                f"class {ordered[0].class_index}, the winner: its closing stage "
                f"raised {type(exc).__name__}: {exc}, so its Rwp, GoF, R_mag and "
                f"moments are the ranked fit's, at the declared stages' windows")
        else:
            ordered = (closed, *ordered[1:])
            caveats.append(
                f"class {closed.class_index}, the winner: its Rwp, GoF, R_mag "
                f"and moments are from a closing stage at windows dropping "
                f"{CLOSING_WINDOW_TOL:g} of each peak, run after the ranking; its "
                f"ΔBIC, the other rows and the nuclear reference are at the "
                f"declared stages' windows, where every trial was ranked")
            if closed.fit_status != "converged":
                caveats.append(
                    f"class {closed.class_index}, the winner: its closing stage "
                    f"stopped at {closed.fit_status!r}, so its moments and their "
                    f"esds measure where the solver stopped rather than a "
                    f"minimum")
    # the refinements only the close continues from: a solution that kept
    # them would hold every trial's compiled model alive
    ordered = tuple(replace(t, _refinement=None, _plan=None) for t in ordered)

    reference = _reported_reference(reference_of, references, kk, ordered, tied)
    if reference is not None:
        n_eff, n_raw = reference[6], reference[7]
        if n_eff >= n_raw:
            # f is floored at 1, and ``_effective_count`` reads N unchanged
            # where the reference carried no row with both esds (issue #270)
            caveats.append(
                f"ΔBIC charges the raw {n_raw} fitted channels: the nuclear "
                f"reference's fit gave no Bérar-Lelann factor above 1, or no "
                f"esd to measure one on, so the count is not corrected for "
                f"neighbouring channels sharing their misfit")
        else:
            caveats.append(
                f"ΔBIC charges {n_eff:.0f} observations, not the {n_raw} "
                f"fitted channels: N/f², with f = "
                f"{math.sqrt(n_raw / n_eff):.2f} the Bérar-Lelann factor of "
                f"the nuclear reference's fit (issue #270). Neighbouring "
                f"channels of one peak share the sign of their misfit, so the "
                f"raw count would charge the same misfit several times and let "
                f"any χ² gain outvote the parameter penalty")
    solution = MagneticSolution(
        verdict=verdict, reason=why, criterion=_CRITERION, phase=parent.name,
        space_group=parent.space_group,
        k=tuple(str(c) for c in kk), k_route=route, k_reason=reason,
        k_candidates=k_candidates,
        sites=tuple(label for _j, label, _i in magnetic),
        n_residual_peaks=counts[0], n_on_nuclear_lines=counts[1],
        n_on_forbidden_lattice_points=counts[2], n_unexplained=counts[3],
        trials=ordered, tied=tied, tie_width=tie_width, d_min=d_min,
        nuclear_rwp=reference[2] if reference else None,
        nuclear_gof=reference[3] if reference else None,
        nuclear_r_magnetic=reference[4] if reference else None,
        n_magnetic_channels=int(mask.sum()), caveats=tuple(caveats),
        k_trials=k_trial_rows,
        diagnostics=k_diagnostics + tuple(pair_diagnostics)
                   + tuple(ion_g_diagnostics) + descent_diagnostics
                   + tuple(tied_note),
        subgroup_audit=subgroup_audit, subgroup_note=subgroup_note,
        _instrument=instrument)
    if cif_dir is not None:
        solution.write_magcifs(cif_dir)
    return solution


_CRITERION = (
    "ΔBIC against a nuclear reference refined under the same stages minus the "
    "moment paths (n_added = the moment DOFs left free), charged at the "
    "reference's N/f² observations; a supported moment (WP-1327's null test) "
    "is a precondition, and classes inside the tie width are an abstention, "
    "never a winner, listed fewest moment parameters first. The "
    "magnetic-only R, over the channels the nuclear model puts nothing on, is "
    "reported and ranks nothing. Never Rwp alone")


def _determinable(sets, site_label, candidate) -> int:
    for label, cs in sets:
        if label != site_label:
            continue
        for i, other in enumerate(cs):
            if other is candidate:
                return int(cs.determinable[i]) if cs.determinable else 0
    return 0


def _merge_classes(sets):
    """Global powder-equivalence classes over every named site's candidate set.

    Two links, and both are needed.  **Within** one site M-7's
    ``equivalence_classes`` is the authority: it is the Shirane test, run on
    the shell intensities of the two families.  **Across** sites the link is
    *identity of the magnetic space group*: the group is the refinable object
    (WP-1418 § Goal) and every site's moment family follows from it through
    ``allowed_moment_basis``, so the same operator list reached from two sites'
    representations is one candidate model and must be refined once.

    The representative of a class is its **smallest** family — fewest free
    amplitudes, then the BNS number for determinism — because that is the model
    a trial should state when several describe the same pattern.

    **What this does not detect** is a degeneracy that exists only *jointly*:
    two groups that no single site's powder average separates but whose
    combination over two sites does, or vice versa.  A joint-representation
    treatment is M-10's; here the classes are per-site and merged, and a class
    with members from more than one site is named as such in the report.
    """
    entries: list[tuple[str, int, MagneticCandidate]] = []
    for label, cs in sets:
        for i, candidate in enumerate(cs):
            entries.append((label, i, candidate))
    parent = list(range(len(entries)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    position = {(label, i): n for n, (label, i, _c) in enumerate(entries)}
    for label, cs in sets:
        for members in cs.classes:
            for other in members[1:]:
                union(position[(label, members[0])], position[(label, other)])
    signature: dict[tuple, int] = {}
    for n, (_label, _i, candidate) in enumerate(entries):
        ops, cent = candidate.group.xyz_strings()
        key = (frozenset(ops), frozenset(cent))
        if key in signature:
            union(signature[key], n)
        else:
            signature[key] = n

    groups: dict[int, list[int]] = {}
    for n in range(len(entries)):
        groups.setdefault(find(n), []).append(n)
    out = []
    for members in sorted(groups.values(), key=lambda m: m[0]):
        rows = [entries[n] for n in members]
        rows.sort(key=lambda r: (r[2].free_amplitudes, r[2].bns_number,
                                 r[2].label))
        label, _i, candidate = rows[0]
        names = tuple(f"{c.bns_number} {c.label}"
                      + (f" @{site}" if len(sets) > 1 else "")
                      for site, _n, c in rows)
        out.append((names, candidate, label))
    return out
